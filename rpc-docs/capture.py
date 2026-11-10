#!/usr/bin/env python3
"""Snapshot one node release's RPC surface into rpc-docs/versions/<version>/.

    rpc-docs/capture.py v6.22.0-rc1 --node-repo ../ycash6 --image ghcr.io/boyfromcave/ycashd:ycash6-<sha12>
    rpc-docs/capture.py v6.22.0-rc1 --node-repo ../ycash6 --bin-dir ~/ycash/src --commit <sha>

Starts a throwaway regtest node (wallet on, the vault upgrade and a placeholder YED attestor set
configured, so every RPC category registers), writes the output of `help` and of `help <method>`
for each method, copies the RPC contracts from the release tag, and records where all of it came
from in source.json. The node, its datadir and any fetched binaries are deleted afterwards.

The binaries must be built from the tag's commit. If they are not (no image of the tag exists yet),
--allow-commit-mismatch REASON records why the capture still describes the tag.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_image  # noqa: E402

CONTRACTS = ["doc/vault-rpc-contract.json", "doc/yellowback-rpc-contract.json"]
METHOD_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+(-(beta|rc)\d+)?$")
IMAGE_COMMIT_RE = re.compile(r"-([0-9a-f]{12,40})$")

# Regtest activates nothing by itself: the six Ycash upgrades at 1, then the vault upgrade.
# Yellowback's RPCs register only on a node with the vault upgrade and a YED attestor set
# configured (ycash6 src/yellowback/params.h IsConfigured); the set id need not exist on chain.
NODE_CONF = """regtest=1
listen=0
dnsseed=0
rpcbind=127.0.0.1
rpcallowip=127.0.0.1
rpcport={rpcport}
port={port}
rpcuser=rpcdocs
rpcpassword=rpcdocs
nuparams=5ba81b19:1
nuparams=76b809bb:1
nuparams=374d694f:1
nuparams=8e471bd6:1
nuparams=66314da3:1
nuparams=19bd2d2f:1
nuparams=6d5b7a31:10
yellowbackattestorset={attestorset}
"""
PLACEHOLDER_SET = "01" * 32


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def parse_help_index(text):
    """`help` output -> [(category, [method, ...]), ...] in the node's order."""
    groups, current = [], None
    for line in text.splitlines():
        if line.startswith("== ") and line.endswith(" =="):
            current = (line[3:-3], [])
            groups.append(current)
        elif line.strip() and current is not None:
            name = line.split()[0]
            if not METHOD_RE.match(name):
                raise SystemExit("capture: unexpected method name %r in help output" % name)
            current[1].append(name)
    if not groups:
        raise SystemExit("capture: help printed no categories")
    return groups


class Node:
    def __init__(self, bin_dir, workdir):
        self.ycashd = os.path.join(bin_dir, "ycashd")
        self.cli = os.path.join(bin_dir, "ycash-cli")
        self.datadir = os.path.join(workdir, "datadir")
        os.makedirs(self.datadir)
        with open(os.path.join(self.datadir, "ycash.conf"), "w") as f:
            f.write(NODE_CONF.format(rpcport=free_port(), port=free_port(), attestorset=PLACEHOLDER_SET))
        self.proc = None

    def __enter__(self):
        self.proc = subprocess.Popen([self.ycashd, "-datadir=" + self.datadir, "-printtoconsole=0"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        deadline = time.time() + 180
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise SystemExit("capture: ycashd exited: %s" % self.proc.stderr.read().decode(errors="replace"))
            r = subprocess.run([self.cli, "-datadir=" + self.datadir, "getblockchaininfo"], capture_output=True)
            if r.returncode == 0:
                return self
            time.sleep(1)
        raise SystemExit("capture: ycashd did not answer RPC within 180 s")

    def __exit__(self, *exc):
        if self.proc and self.proc.poll() is None:
            subprocess.run([self.cli, "-datadir=" + self.datadir, "stop"], capture_output=True)
            try:
                self.proc.wait(timeout=120)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()

    def rpc(self, *args):
        r = subprocess.run([self.cli, "-datadir=" + self.datadir, *args], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit("capture: ycash-cli %s failed: %s" % (" ".join(args), r.stderr.strip()))
        return r.stdout


def daemon_version(bin_dir):
    r = subprocess.run([os.path.join(bin_dir, "ycashd"), "--version"], capture_output=True, text=True)
    return r.stdout.splitlines()[0].strip() if r.stdout else ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("version", help="the release tag, e.g. v6.22.0-beta1")
    ap.add_argument("--node-repo", required=True, help="a clone of the node repository holding the tag")
    ap.add_argument("--line", default="ycash6", help="the node line the version belongs to")
    ap.add_argument("--tag", help="the git tag to read the contracts from (default: the version)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", help="a public image holding usr/local/bin/ycashd and ycash-cli")
    src.add_argument("--bin-dir", help="a directory holding ycashd and ycash-cli")
    ap.add_argument("--commit", help="the commit the --bin-dir binaries were built from")
    ap.add_argument("--allow-commit-mismatch", metavar="REASON",
                    help="accept binaries built from another commit than the tag's, recording why")
    ap.add_argument("--out", default=os.path.join(HERE, "versions"))
    ap.add_argument("--force", action="store_true", help="replace an existing snapshot")
    args = ap.parse_args(argv)

    if not VERSION_RE.match(args.version):
        raise SystemExit("capture: %r is not a release version (vX.Y.Z, vX.Y.Z-betaN, vX.Y.Z-rcN)" % args.version)
    tag = args.tag or args.version
    tag_commit = git(args.node_repo, "rev-parse", tag + "^{commit}").strip()
    dest = os.path.join(args.out, args.version)
    if os.path.exists(dest) and not args.force:
        raise SystemExit("capture: %s exists; published versions are immutable (--force to redo)" % dest)

    with tempfile.TemporaryDirectory(prefix="rpc-docs-") as work:
        binary = {}
        if args.image:
            bin_dir = os.path.join(work, "bin")
            m = IMAGE_COMMIT_RE.search(args.image)
            commit_hint = args.commit or (m.group(1) if m else None)
            with open(os.path.join(work, "image.json"), "w") as out:
                saved, sys.stdout = sys.stdout, out
                try:
                    fetch_image.main([args.image, bin_dir, "usr/local/bin/ycashd", "usr/local/bin/ycash-cli"])
                finally:
                    sys.stdout = saved
            with open(os.path.join(work, "image.json")) as f:
                binary.update(json.load(f))
        else:
            bin_dir = os.path.abspath(args.bin_dir)
            commit_hint = args.commit
        if not commit_hint:
            raise SystemExit("capture: give --commit (the commit the binaries were built from)")
        binary["commit"] = git(args.node_repo, "rev-parse", commit_hint + "^{commit}").strip()
        binary["version"] = daemon_version(bin_dir)
        mismatch = None
        if binary["commit"] != tag_commit:
            if not args.allow_commit_mismatch:
                raise SystemExit("capture: the binaries are from %s, the tag %s is %s; "
                                 "--allow-commit-mismatch REASON if the RPC surface is the same"
                                 % (binary["commit"][:12], tag, tag_commit[:12]))
            mismatch = args.allow_commit_mismatch

        staging = os.path.join(work, "snapshot")
        os.makedirs(os.path.join(staging, "help"))
        with Node(bin_dir, work) as node:
            index = node.rpc("help")
            groups = parse_help_index(index)
            with open(os.path.join(staging, "help", "_index.txt"), "w") as f:
                f.write(index)
            for _, methods in groups:
                for name in methods:
                    with open(os.path.join(staging, "help", name + ".txt"), "w") as f:
                        f.write(node.rpc("help", name))

        contracts = []
        os.makedirs(os.path.join(staging, "contracts"))
        for path in CONTRACTS:
            r = subprocess.run(["git", "-C", args.node_repo, "show", "%s:%s" % (tag, path)],
                               capture_output=True)
            if r.returncode == 0:
                json.loads(r.stdout)
                with open(os.path.join(staging, "contracts", os.path.basename(path)), "wb") as f:
                    f.write(r.stdout)
                contracts.append(path)

        source = {
            "version": args.version,
            "line": args.line,
            "tag": tag,
            "tagCommit": tag_commit,
            "binary": binary,
            "commitMismatch": mismatch,
            "contracts": contracts,
            "capturedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "methods": sum(len(m) for _, m in groups),
        }
        with open(os.path.join(staging, "source.json"), "w") as f:
            json.dump(source, f, indent=2)
            f.write("\n")
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(staging, dest)
    print("capture: %s, %d methods in %d categories -> %s" % (args.version, source["methods"], len(groups), dest))


if __name__ == "__main__":
    main()

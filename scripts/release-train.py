#!/usr/bin/env python3
"""The release train: every component of a Ycash Yellowback (YED) node release at one named commit.

In plain words: a release candidate of the node is only tested together with the programs around it
(the wallets, the light-wallet server, the pool, the visualizer, the bridge attestor). This file is
the list of exactly which version of each of them the candidate was tested with, and the checker
makes sure the list is real: every commit exists on its repository's main line, the clients carry
the same RPC contract as the node, and everything states the same RPC version.

  scripts/release-train.py check [--online] [FILE ...]   validate trains (default: releases/v*.yaml)
  scripts/release-train.py pins FILE                      print the train as KEY=VALUE lines (rc-qualify)

Testnet plan §5.4. One file per release, releases/v<version>.yaml, in the flat shape of repos.yaml
(unindented `section:` lines, two-space `key: value` fields, `# comment`s stripped, nothing else):

  release:        version (6.22.N, 6.22.N-rcM or 6.22.N-betaM), rpcversion (the node's
                  YELLOWBACK_RPC_VERSION), workspace (the workspace commit whose generated spec and
                  contract copies the clients carry)
  testnet:        fast-vault-height, fast-set-id, slow-vault-height, slow-set-id, bundle-height
                  (H_B of the state bundle the release pins); `none` when not set
  <component>:    commit (40 hex), and for ycash6 / ycash-dd also tag (v<version> /
                  vault-params/v<version>). Components: every repository of repos.yaml that a release
                  is qualified with (COMPONENTS below); each must be present.

`check` (offline) validates the shape: every field present and well formed, the file named after its
version, tags matching the version, a final release naming both testnet-yb networks. `check --online`
also clones each component (commit graph only, plus the few files read) and checks:
  - every commit is on that repository's upgrade/vault (repos.yaml `branch`);
  - a tag, when it already exists, names the train's commit (a train is written before the tag);
  - rpcversion: the node lines' YELLOWBACK_RPC_VERSION and every client contract copy's top-level
    "rpcversion" equal the train's;
  - the contract copies: the workspace at `workspace` runs its scripts/extract_spec.py check for
    that rpcversion's line against ycash-dd, ycash6, yecwallet-dd and lightwalletd-dd at their
    train commits (the `make spec-check` logic);
  - hawkeye's pinned wyec commit (eth/tools/fetch-wyec.sh WYEC_COMMIT) is the train's wyec commit.

`pins` prints TRAIN_<SECTION>_<KEY>=<value> lines (upper case, '-' as '_'), every value validated,
for rc-qualify to read in place of the push tier's YOLO_COMMIT / CHAINVIZ_COMMIT / LWD_COMMIT /
YB_WORKSPACE_COMMIT env pins. Python 3 standard library and git only.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPOS_FILE = os.environ.get("REPOS_FILE") or os.path.join(ROOT, "repos.yaml")
RELEASES = os.path.join(ROOT, "releases")
# The workspace repository itself (not in repos.yaml: it is the manifest's own home).
WORKSPACE_URL = os.environ.get("RELEASE_TRAIN_WORKSPACE_URL") or "https://github.com/boyfromcave/yellowback.git"

# Components a node release is qualified with (testnet plan §5.4), in the order they are reported.
COMPONENTS = ("ycash6", "ycash-dd", "librustzcash6", "lightwalletd-dd", "yecwallet-dd", "yew", "yolo",
              "chain-viz", "x402-ycash", "hawkeye", "wyec")
TAGGED = {"ycash6": "v{version}", "ycash-dd": "vault-params/v{version}"}
SECTIONS = {
    "release": ("version", "rpcversion", "workspace"),
    "testnet": ("fast-vault-height", "fast-set-id", "slow-vault-height", "slow-set-id", "bundle-height"),
}
# rpcversion -> the extract_spec.py check of that line (scripts/extract_spec.py THE ... LINE).
SPEC_MODE = {5: "--check-upgrade", 6: "--check-in-term", 7: "--check-quantum", 8: "--check-fees"}
# Where each spec repository keeps what extract_spec.py reads, and its override variable.
SPEC_TREES = {
    "ycash-dd": ("EXTRACT_SPEC_NODE_DIR", ["doc"]),
    "ycash6": ("EXTRACT_SPEC_NODE6_DIR", ["doc"]),
    "yecwallet-dd": ("EXTRACT_SPEC_WALLET_DIR", ["docs"]),
    "lightwalletd-dd": ("EXTRACT_SPEC_LWD_DIR", ["testdata"]),
}
CLIENT_CONTRACTS = {
    "ycash-dd": "doc/yellowback-rpc-contract.json",
    "ycash6": "doc/yellowback-rpc-contract.json",
    "yecwallet-dd": "docs/yellowback-rpc-contract.json",
    "lightwalletd-dd": "testdata/yellowback/contract.json",
}
NODE_RPC_SOURCE = "src/rpc/yellowback.cpp"
HAWKEYE_WYEC_PIN = "eth/tools/fetch-wyec.sh"

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
VERSION = re.compile(r"^6\.22\.\d+(?:-(?:rc|beta)[1-9]\d*)?$")
HEIGHT = re.compile(r"^[1-9]\d{0,8}$")


class TrainError(Exception):
    pass


def parse_flat(text, where):
    """The repos.yaml shape: {section: {key: value}}; anything else is an error, never ignored."""
    out, section = {}, None
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.-]*):\s*(#.*)?$", line)
        if m:
            section = m.group(1)
            if section in out:
                raise TrainError("%s:%d: section %s twice" % (where, n, section))
            out[section] = {}
            continue
        m = re.match(r"^  ([a-z][a-z0-9-]*):\s*(\S.*?)?\s*$", line)
        if not m or section is None:
            raise TrainError("%s:%d: not `section:` or `  key: value`: %r" % (where, n, raw))
        key, value = m.group(1), re.sub(r"\s+#.*$", "", m.group(2) or "").strip()
        if key in out[section]:
            raise TrainError("%s:%d: %s.%s twice" % (where, n, section, key))
        out[section][key] = value
    return out


def repos():
    with open(REPOS_FILE, encoding="utf-8") as fh:
        return parse_flat(fh.read(), os.path.basename(REPOS_FILE))


def validate(train, filename=None):
    """Offline shape checks; returns the list of problems (empty when the train is well formed)."""
    problems = []
    for section, keys in SECTIONS.items():
        got = train.get(section)
        if got is None:
            problems.append("missing section %s" % section)
            continue
        for key in keys:
            if key not in got:
                problems.append("missing %s.%s" % (section, key))
        for key in sorted(set(got) - set(keys)):
            problems.append("unknown field %s.%s" % (section, key))
    for name in COMPONENTS:
        got = train.get(name)
        if got is None:
            problems.append("missing component %s" % name)
            continue
        want = {"commit", "tag"} if name in TAGGED else {"commit"}
        for key in sorted(want - set(got)):
            problems.append("missing %s.%s" % (name, key))
        for key in sorted(set(got) - want):
            problems.append("unknown field %s.%s" % (name, key))
        if "commit" in got and not HEX40.match(got["commit"]):
            problems.append("%s.commit is not a full 40-hex commit: %r" % (name, got["commit"]))
    for section in sorted(set(train) - set(SECTIONS) - set(COMPONENTS)):
        problems.append("unknown section %s" % section)
    if problems:
        return problems
    rel, net = train["release"], train["testnet"]
    version = rel["version"]
    if not VERSION.match(version):
        problems.append("release.version %r is not a 6.22.x release version" % version)
    if not re.match(r"^[1-9]\d*$", rel["rpcversion"]) or int(rel["rpcversion"]) not in SPEC_MODE:
        problems.append("release.rpcversion %r is not one of %s" % (rel["rpcversion"], sorted(SPEC_MODE)))
    if not HEX40.match(rel["workspace"]):
        problems.append("release.workspace is not a full 40-hex commit: %r" % rel["workspace"])
    for key in ("fast-vault-height", "slow-vault-height", "bundle-height"):
        if net[key] != "none" and not HEIGHT.match(net[key]):
            problems.append("testnet.%s is not a height or none: %r" % (key, net[key]))
    for key in ("fast-set-id", "slow-set-id"):
        if net[key] != "none" and not (HEX64.match(net[key]) and set(net[key]) != {"0"}):
            problems.append("testnet.%s is not a 64-hex set id or none: %r" % (key, net[key]))
    # The node's own R7 for the testnet (qa/yellowback-vault-params.py): a set only with its height;
    # fast is launched by every rc and final release; a final release names slow's set too.
    for net_name in ("fast", "slow"):
        if net["%s-set-id" % net_name] != "none" and net["%s-vault-height" % net_name] == "none":
            problems.append("testnet.%s-set-id without testnet.%s-vault-height" % (net_name, net_name))
    stage = "beta" if "-beta" in version else "rc" if "-rc" in version else "final"
    if stage in ("rc", "final") and "none" in (net["fast-vault-height"], net["fast-set-id"]):
        problems.append("an %s names testnet-yb-fast's vault height and set id" % stage)
    if stage == "final" and "none" in (net["slow-vault-height"], net["slow-set-id"]):
        problems.append("a final release names testnet-yb-slow's vault height and set id")
    for name, pattern in TAGGED.items():
        if train[name]["tag"] != pattern.format(version=version):
            problems.append("%s.tag must be %s" % (name, pattern.format(version=version)))
    if filename is not None and os.path.basename(filename) != "v%s.yaml" % version:
        problems.append("the file of release %s is releases/v%s.yaml" % (version, version))
    return problems


def load(path):
    with open(path, encoding="utf-8") as fh:
        train = parse_flat(fh.read(), path)
    problems = validate(train, path)
    if problems:
        raise TrainError("%s:\n  %s" % (path, "\n  ".join(problems)))
    return train


def pins(train):
    lines = []
    for section in list(SECTIONS) + list(COMPONENTS):
        for key, value in train[section].items():
            lines.append("TRAIN_%s_%s=%s" % (section.upper().replace("-", "_"), key.upper().replace("-", "_"), value))
    return lines


# ------------------------------------------------------------------------------------------- online

def git(*args, cwd=None, check=True):
    proc = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True,
                          env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    if check and proc.returncode != 0:
        raise TrainError("git %s: %s" % (" ".join(args), proc.stderr.strip()[-400:]))
    return proc


class Remote:
    """One component: its commit graph (tree:0 partial clone of the branch) and lazily read files."""

    def __init__(self, name, url, branch, scratch):
        self.name, self.url, self.branch = name, url, branch
        self.dir = os.path.join(scratch, name + ".git")
        git("clone", "-q", "--bare", "--filter=tree:0", "--single-branch", "--branch", branch, url, self.dir)

    def on_branch(self, commit):
        if git("cat-file", "-e", commit + "^{commit}", cwd=self.dir, check=False).returncode != 0:
            return False
        return git("merge-base", "--is-ancestor", commit, "refs/heads/" + self.branch,
                   cwd=self.dir, check=False).returncode == 0

    def tag_commit(self, tag):
        out = git("ls-remote", self.url, "refs/tags/%s" % tag, "refs/tags/%s^{}" % tag).stdout.split("\n")
        found = dict(reversed(line.split("\t")) for line in out if "\t" in line)
        return found.get("refs/tags/%s^{}" % tag) or found.get("refs/tags/%s" % tag)

    def show(self, commit, path):
        proc = git("show", "%s:%s" % (commit, path), cwd=self.dir, check=False)
        return proc.stdout if proc.returncode == 0 else None

    def materialize(self, commit, paths, dest):
        """A sparse working tree of PATHS at COMMIT (for extract_spec.py)."""
        git("clone", "-q", "--filter=blob:none", "--no-checkout", "--sparse", "--depth", "1",
            "--single-branch", "--branch", self.branch, self.url, dest)
        git("fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", commit, cwd=dest)
        git("sparse-checkout", "set", *paths, cwd=dest)
        git("checkout", "-q", "--detach", commit, cwd=dest)
        return dest


def node_rpcversion(text):
    m = re.search(r"static const int YELLOWBACK_RPC_VERSION\s*=\s*(\d+)\s*;", text or "")
    return int(m.group(1)) if m else None


def contract_rpcversion(text):
    try:
        value = json.loads(text or "").get("rpcversion")
    except (ValueError, AttributeError):
        return None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def wyec_pin(text):
    m = re.search(r"^WYEC_COMMIT=([0-9a-f]{40})\s*$", text or "", flags=re.M)
    return m.group(1) if m else None


def spec_check(workspace_dir, mode, trees):
    """Run the workspace's extract_spec.py at the train's workspace commit; returns (ok, output)."""
    env = dict(os.environ)
    env.update(trees)
    proc = subprocess.run([sys.executable, os.path.join(workspace_dir, "scripts", "extract_spec.py"), mode],
                          capture_output=True, text=True, env=env, cwd=workspace_dir)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def check_online(train, scratch, log=print):
    problems = []
    manifest = repos()
    rpc = int(train["release"]["rpcversion"])
    remotes = {}
    for name in COMPONENTS:
        entry = manifest.get(name) or {}
        url, branch = entry.get("url"), entry.get("branch")
        if not url or not branch:
            problems.append("%s: no url/branch in repos.yaml" % name)
            continue
        commit = train[name]["commit"]
        remote = remotes[name] = Remote(name, url, branch, scratch)
        if not remote.on_branch(commit):
            problems.append("%s: %s is not on %s" % (name, commit, branch))
            continue
        log("ok   %-16s %s on %s" % (name, commit[:12], branch))
        if name in TAGGED:
            tag = train[name]["tag"]
            tagged = remote.tag_commit(tag)
            if tagged is None:
                log("note %-16s %s is not tagged yet (a train is written before its tag)" % (name, tag))
            elif tagged != commit:
                problems.append("%s: tag %s names %s, the train says %s" % (name, tag, tagged, commit))
    if problems:
        return problems
    for name in ("ycash-dd", "ycash6"):
        got = node_rpcversion(remotes[name].show(train[name]["commit"], NODE_RPC_SOURCE))
        if got != rpc:
            problems.append("%s: YELLOWBACK_RPC_VERSION is %s, the train says %d" % (name, got, rpc))
    for name, path in CLIENT_CONTRACTS.items():
        got = contract_rpcversion(remotes[name].show(train[name]["commit"], path))
        if got != rpc:
            problems.append("%s: %s states rpcversion %s, the train says %d" % (name, path, got, rpc))
    pinned = wyec_pin(remotes["hawkeye"].show(train["hawkeye"]["commit"], HAWKEYE_WYEC_PIN))
    if pinned != train["wyec"]["commit"]:
        problems.append("hawkeye: %s pins wyec %s, the train says %s" % (HAWKEYE_WYEC_PIN, pinned, train["wyec"]["commit"]))
    if problems:
        return problems
    ws = Remote("workspace", WORKSPACE_URL, "upgrade/vault", scratch)
    if not ws.on_branch(train["release"]["workspace"]):
        return ["workspace: %s is not on upgrade/vault" % train["release"]["workspace"]]
    ws_dir = ws.materialize(train["release"]["workspace"], ["scripts", "docs"], os.path.join(scratch, "workspace"))
    trees = {}
    for name, (var, paths) in SPEC_TREES.items():
        trees[var] = remotes[name].materialize(train[name]["commit"], paths, os.path.join(scratch, name + "-tree"))
    ok, output = spec_check(ws_dir, SPEC_MODE[rpc], trees)
    for line in output.splitlines():
        log("     | " + line)
    if not ok:
        problems.append("the contract and spec copies differ from the workspace's (extract_spec.py %s)" % SPEC_MODE[rpc])
    else:
        log("ok   contract and spec copies (extract_spec.py %s at workspace %s)" % (SPEC_MODE[rpc], train["release"]["workspace"][:12]))
    return problems


def main(argv):
    if not argv or argv[0] not in ("check", "pins"):
        print(__doc__.split("\n\n")[2], file=sys.stderr)
        return 2
    if argv[0] == "pins":
        if len(argv) != 2:
            print("usage: release-train.py pins FILE", file=sys.stderr)
            return 2
        try:
            train = load(argv[1])
        except (TrainError, OSError) as e:
            print("release-train: %s" % e, file=sys.stderr)
            return 1
        print("\n".join(pins(train)))
        return 0
    online = "--online" in argv[1:]
    files = [a for a in argv[1:] if a != "--online"]
    if not files:
        files = sorted(os.path.join(RELEASES, f) for f in os.listdir(RELEASES)
                       if re.match(r"^v.*\.yaml$", f)) if os.path.isdir(RELEASES) else []
        if not files:
            print("release-train: no releases/v*.yaml yet; nothing to check")
            return 0
    bad = 0
    for path in files:
        try:
            train = load(path)
        except (TrainError, OSError) as e:
            print("FAIL %s" % e)
            bad += 1
            continue
        print("ok   %s: release %s (shape)" % (path, train["release"]["version"]))
        if online:
            with tempfile.TemporaryDirectory(prefix="release-train-") as scratch:
                try:
                    problems = check_online(train, scratch)
                except TrainError as e:
                    problems = [str(e)]
            for problem in problems:
                print("FAIL %s: %s" % (path, problem))
            bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
# Copyright (c) 2026 The Ycash developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://www.opensource.org/licenses/mit-license.php .

"""Self-tests of the release-candidate qualification harness (qualify/README.md; testnet plan §5.3):
qualify/rc-qualify.sh (install, pins, train), qualify/rc-crossline.py (the argument filter, the
configuration file, the fail-fast wait) and qualify/rc-record.py (step 1's evidence, the record).
No node runs: the "binaries" are shell stubs; the trains are the real releases/v*.yaml."""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(HERE)
SCRIPT = os.path.join(HERE, "rc-qualify.sh")


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


crossline = load("crossline", "rc-crossline.py")
rc_record = load("rc_record", "rc-record.py")
rc_suites = load("rc_suites", "rc-suites.py")

# The shape of ycash6's yellowback-tests.yml that rc-suites.py reads (its top-level env block).
WORKFLOW = """name: yellowback tests
on: push
env:
  # the merge-gate lists
  YELLOWBACK_SCRIPTS: a b c d e f g
  SANITIZER_SCRIPTS: x
  YOLO_COMMIT: ${{ inputs.yolo_commit || '%s' }}
  CHAINVIZ_COMMIT: ${{ inputs.chainviz_commit || '%s' }}  # a comment
  LWD_COMMIT: ${{ inputs.lwd_commit || '%s' }}
  YB_WORKSPACE_COMMIT: ${{ inputs.workspace_commit || '%s' }}
  STOCK_BASELINE: s1 s2 s3
  STOCK_BASELINE_MINEBLOCK: 'txn_doublespend.py --mineblock'
jobs:
  build:
    env:
      YELLOWBACK_SCRIPTS: not this one
""" % ("1" * 40, "2" * 40, "3" * 40, "4" * 40)


def run(*args):
    proc = subprocess.run(["bash", SCRIPT] + list(args), capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rc-qualify-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.pkgdir = os.path.join(self.tmp, "pkg")
        self.tree = os.path.join(self.tmp, "tree")
        os.makedirs(self.pkgdir)

    def package(self, version="6.22.0-rc1", banner=None, sums=True, tamper=False, missing=None):
        name = "ycashd_v%s_linux_x86_64" % version
        stage = os.path.join(self.tmp, "stage", name)
        os.makedirs(stage)
        for b in ("ycashd", "ycash-cli", "ycash-tx"):
            if b == missing:
                continue
            with open(os.path.join(stage, b), "w", encoding="utf-8") as fh:
                fh.write("#!/bin/sh\necho 'Ycash Daemon version %s'\n" % (banner or "v" + version))
            os.chmod(os.path.join(stage, b), 0o700)   # owner only: the stub need not be world-readable
        path = os.path.join(self.pkgdir, name + ".tar.gz")
        with tarfile.open(path, "w:gz") as tar:
            tar.add(stage, arcname=name)
        if sums:
            with open(path, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            if tamper:
                digest = "0" * 64
            with open(os.path.join(self.pkgdir, "SHA256SUMS"), "w", encoding="utf-8") as fh:
                fh.write("%s  %s\n%s  ycashd_v%s_windows.zip\n" % (digest, name + ".tar.gz", "1" * 64, version))
        return path

    def test_installs_a_checked_package(self):
        self.package()
        code, out = run("install", self.pkgdir, self.tree)
        self.assertEqual(code, 0, out)
        self.assertIn("installed ycashd_v6.22.0-rc1_linux_x86_64.tar.gz", out)
        for b in ("ycashd", "ycash-cli", "ycash-tx"):
            self.assertTrue(os.access(os.path.join(self.tree, "src", b), os.X_OK))

    def test_refuses_a_package_that_does_not_match(self):
        self.package(tamper=True)
        code, out = run("install", self.pkgdir, self.tree)
        self.assertEqual(code, 1, out)
        self.assertIn("does not match SHA256SUMS", out)

    def test_refuses_without_sums_or_with_a_wrong_banner(self):
        self.package(sums=False)
        code, out = run("install", self.pkgdir, self.tree)
        self.assertEqual(code, 1, out)
        self.assertIn("no SHA256SUMS", out)
        shutil.rmtree(self.pkgdir)
        os.makedirs(self.pkgdir)
        shutil.rmtree(os.path.join(self.tmp, "stage"))
        self.package(banner="v6.22.0-rc2")
        code, out = run("install", self.pkgdir, self.tree)
        self.assertEqual(code, 1, out)
        self.assertIn("not v6.22.0-rc1", out)

    def test_refuses_a_package_without_a_binary_or_a_version(self):
        self.package(missing="ycash-tx")
        code, out = run("install", self.pkgdir, self.tree)
        self.assertEqual(code, 1, out)
        self.assertIn("has no ycash-tx", out)
        shutil.rmtree(self.pkgdir)
        os.makedirs(self.pkgdir)
        shutil.rmtree(os.path.join(self.tmp, "stage"))
        self.package(version="6.22.0-rc0")
        code, out = run("install", self.pkgdir, self.tree)
        self.assertEqual(code, 1, out)
        self.assertIn("does not name a release version", out)


class Pins(unittest.TestCase):
    def write(self, text):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        self.addCleanup(os.unlink, path)
        return path

    def test_pin_lines_pass_and_anything_else_fails(self):
        good = "TRAIN_RELEASE_VERSION=6.22.0-rc1\nTRAIN_YOLO_COMMIT=%s\nTRAIN_YCASH_DD_TAG=vault-params/v6.22.0-rc1\n" % ("a" * 40)
        code, out = run("pins", self.write(good))
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines(), good.splitlines())
        for bad in ("TRAIN_X=$(id)\n", "PATH=/tmp\n", "TRAIN_X=a b\n", "TRAIN_X=\n", ""):
            code, out = run("pins", self.write(bad))
            self.assertEqual(code, 1, repr(bad) + out)


class Train(unittest.TestCase):
    """`train FILE`: the release train read through scripts/release-train.py pins, then checked as `pins`."""

    def test_reads_the_beta2_train(self):
        code, out = run("train", os.path.join(WORKSPACE, "releases", "v6.22.0-beta2.yaml"))
        self.assertEqual(code, 0, out)
        lines = out.splitlines()
        self.assertIn("TRAIN_RELEASE_VERSION=6.22.0-beta2", lines)
        self.assertIn("TRAIN_YCASH6_COMMIT=fbc9f625c657eca50ddc09e5065e8ed0d3a33a48", lines)
        self.assertIn("TRAIN_YCASH6_TAG=v6.22.0-beta2", lines)
        self.assertIn("TRAIN_YCASH_DD_COMMIT=00247d5c3e4e6be3c563ec031b6d639a1f47c62c", lines)
        self.assertTrue(all(line.startswith("TRAIN_") for line in lines), out)

    def test_reads_the_beta3_train(self):
        code, out = run("train", os.path.join(WORKSPACE, "releases", "v6.22.0-beta3.yaml"))
        self.assertEqual(code, 0, out)
        lines = out.splitlines()
        self.assertIn("TRAIN_RELEASE_VERSION=6.22.0-beta3", lines)
        self.assertIn("TRAIN_YCASH6_COMMIT=8bfd4621e4f4d023314a00d4a5fb31655e019fe1", lines)
        self.assertIn("TRAIN_YCASH6_TAG=v6.22.0-beta3", lines)
        self.assertIn("TRAIN_YCASH_DD_COMMIT=7c4d8af68acc6638904e82c35058be7c1cea5cb2", lines)
        self.assertTrue(all(line.startswith("TRAIN_") for line in lines), out)

    def test_refuses_a_skeleton(self):
        # The beta3 train with its ycash6 commit put back to `placeholder`: the skeleton it was before the cut.
        with open(os.path.join(WORKSPACE, "releases", "v6.22.0-beta3.yaml"), encoding="utf-8") as fh:
            text = fh.read()
        skeleton = text.replace("commit: 8bfd4621e4f4d023314a00d4a5fb31655e019fe1", "commit: placeholder", 1)
        self.assertNotEqual(skeleton, text)
        directory = tempfile.mkdtemp(prefix="rc-train-")
        self.addCleanup(shutil.rmtree, directory)
        path = os.path.join(directory, "v6.22.0-beta3.yaml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(skeleton)
        code, out = run("train", path)
        self.assertEqual(code, 1, out)
        self.assertIn("is a skeleton", out)
        self.assertIn("ycash6.commit", out)
        self.assertNotIn("TRAIN_", out)

    def test_refuses_the_beta4_skeleton_until_it_is_filled_in(self):
        # rpcversion 11 (beta4) is a known line; the train is not qualifiable while placeholders remain.
        code, out = run("train", os.path.join(WORKSPACE, "releases", "v6.22.0-beta4.yaml"))
        self.assertEqual(code, 1, out)
        self.assertIn("is a skeleton", out)
        self.assertIn("ycash6.commit", out)
        self.assertNotIn("TRAIN_", out)

    def test_refuses_a_missing_file_and_bad_usage(self):
        code, out = run("train", os.path.join(WORKSPACE, "releases", "v6.22.0-rc99.yaml"))
        self.assertEqual(code, 1, out)
        self.assertEqual(run("train")[0], 1)
        self.assertEqual(run("no-such-command")[0], 1)


class CrossLine(unittest.TestCase):
    def test_chain_args_keep_rules_and_drop_local_ones(self):
        args = ["-nuparams=6d5b7a31:200", "-yellowbackattestorset=" + "ab" * 32, "-pqfalconheight=200",
                "-port=1234", "-rpcport=1235", "-connect=127.0.0.1:1", "-zmqpubhashblock=tcp://x", "-mineraddress=x",
                "-insightexplorer", "-txindex=1", "-nurejectoldversions=false", "-debug=yellowback"]
        self.assertEqual(crossline.chain_args(args), ["-nuparams=6d5b7a31:200", "-yellowbackattestorset=" + "ab" * 32,
                                                      "-pqfalconheight=200", "-nurejectoldversions=false"])


    def test_the_configuration_file_is_written_empty(self):
        datadir = tempfile.mkdtemp(prefix="rc-crossline-")
        self.addCleanup(shutil.rmtree, datadir)
        with open(os.path.join(datadir, "ycash.conf"), "w", encoding="utf-8") as fh:
            fh.write("rpcport=1\n")         # left by an earlier run: emptied, not kept or appended to
        path = crossline.empty_conf(datadir)
        self.assertEqual(os.path.getsize(path), 0)

    def test_a_dead_node_fails_the_wait_at_once(self):
        # ycash-dd's stdout.log and kogany's zakurad.log alike: the exit and the log's tail, not a timeout.
        datadir = tempfile.mkdtemp(prefix="rc-crossline-")
        self.addCleanup(shutil.rmtree, datadir)
        log = os.path.join(datadir, "zakurad.log")
        with open(log, "w", encoding="utf-8") as fh:
            fh.write("error: address in use\n")
        proc = subprocess.Popen([sys.executable, "-c", "raise SystemExit(3)"])
        proc.wait()
        with self.assertRaises(SystemExit) as caught:
            crossline.wait("kogany0 answers RPC", lambda: crossline.running(proc, log) and False, 30)
        self.assertIn("exited (3)", str(caught.exception))
        self.assertIn("address in use", str(caught.exception))
        live = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.addCleanup(live.wait)
        self.addCleanup(live.kill)
        self.assertTrue(crossline.running(live, log))

    def test_the_framework_is_the_node_tree_s(self):
        os.environ.pop("RC_FRAMEWORK", None)
        old = os.environ.get("WS")
        os.environ["WS"] = "/w"
        try:
            self.assertEqual(crossline.default_framework(), "/w/ycash6/qa/rpc-tests")
        finally:
            if old is None:
                os.environ.pop("WS")
            else:
                os.environ["WS"] = old


class Suites(unittest.TestCase):
    """rc-suites.py: the node's own lists, sharded as its functional job does."""

    def test_shards_are_round_robin_as_the_node_job(self):
        env = rc_suites.workflow_env(WORKFLOW)
        self.assertEqual(env["YELLOWBACK_SCRIPTS"], "a b c d e f g")
        self.assertEqual(rc_suites.shard(env, "yellowback", 1, 4), ["a", "e"])
        self.assertEqual(rc_suites.shard(env, "yellowback", 4, 4), ["d"])
        allof = sum((rc_suites.shard(env, "yellowback", n, 4) for n in range(1, 5)), [])
        self.assertEqual(sorted(allof), list("abcdefg"))
        self.assertEqual(rc_suites.shard(env, "stock", 1, 2), ["s1", "s3"])
        self.assertEqual(rc_suites.shard(env, "stock", 2, 2), ["s2", "txn_doublespend.py --mineblock"])
        for bad in (("other", 1, 2), ("stock", 3, 2), ("stock", 0, 2)):
            with self.assertRaises(ValueError):
                rc_suites.shard(env, *bad)

    def test_a_continued_or_block_value_is_an_error_not_a_shorter_list(self):
        wrapped = WORKFLOW.replace("  YELLOWBACK_SCRIPTS: a b c d e f g\n", "  YELLOWBACK_SCRIPTS: a b c\n    d e f g\n")
        with self.assertRaises(ValueError):
            rc_suites.workflow_env(wrapped)
        block = WORKFLOW.replace("  YELLOWBACK_SCRIPTS: a b c d e f g\n", "  YELLOWBACK_SCRIPTS: >-\n    a b c d e f g\n")
        with self.assertRaises(ValueError):
            rc_suites.workflow_env(block)

    def test_the_stock_suite_needs_its_mineblock_entry(self):
        env = rc_suites.workflow_env(WORKFLOW.replace("  STOCK_BASELINE_MINEBLOCK: 'txn_doublespend.py --mineblock'\n", ""))
        self.assertEqual(rc_suites.shard(env, "stock", 1, 2), ["s1", "s3"])   # only the last shard runs it
        with self.assertRaises(ValueError):
            rc_suites.shard(env, "stock", 2, 2)

    def test_the_real_ycash6_lists_read(self):
        # The workspace's ycash6 clone, when this runs in a wt/ worktree of a laptop workspace; skipped in CI.
        tree = os.path.join(WORKSPACE, "..", "..", "ycash6")
        path = os.path.join(tree, ".github", "workflows", "yellowback-tests.yml")
        if not os.path.exists(path):
            self.skipTest("no ycash6 tree beside the workspace")
        with open(path, encoding="utf-8") as fh:
            env = rc_suites.workflow_env(fh.read())
        self.assertIn("yellowback_index", rc_suites.shard(env, "yellowback", 1, 4))

    def test_tests_config_is_written_for_the_tree(self):
        template = ("SRCDIR=@abs_top_srcdir@\nBUILDDIR=@abs_top_builddir@\nEXEEXT=@EXEEXT@\n"
                    "@ENABLE_WALLET_TRUE@ENABLE_WALLET=true\n@BUILD_BITCOIN_UTILS_TRUE@ENABLE_UTILS=true\n"
                    "@BUILD_BITCOIND_TRUE@ENABLE_BITCOIND=true\n@ENABLE_ZMQ_TRUE@ENABLE_ZMQ=true\n")
        out = rc_suites.config(template, "/t")
        self.assertIn("SRCDIR=/t\nBUILDDIR=/t\nEXEEXT=\n", out)
        self.assertIn("\nENABLE_ZMQ=true", out)
        self.assertIn("#ENABLE_ZMQ=true", rc_suites.config(template, "/t", zmq=False))
        with self.assertRaises(ValueError):
            rc_suites.config(template + "@NEW_FLAG@\n", "/t")

    def test_default_pins(self):
        env = rc_suites.workflow_env(WORKFLOW)
        self.assertEqual(rc_suites.default_pin(env["CHAINVIZ_COMMIT"]), "2" * 40)
        self.assertIsNone(rc_suites.default_pin("${{ inputs.x }}"))


class NodeShard(unittest.TestCase):
    """`node-shard`: the node tree's own lists and rpc-tests.py, the release binary in its src/ (stubs)."""

    def test_runs_the_shard_with_the_node_s_runner(self):
        ws = tempfile.mkdtemp(prefix="rc-shard-")
        self.addCleanup(shutil.rmtree, ws)
        tree = os.path.join(ws, "ycash6")
        files = {
            ".github/workflows/yellowback-tests.yml": WORKFLOW,
            "qa/pull-tester/tests_config.ini.in": "SRCDIR=@abs_top_srcdir@\n@ENABLE_ZMQ_TRUE@ENABLE_ZMQ=true\n",
            # the stub runner records its arguments and the config it found
            "qa/pull-tester/rpc-tests.py": "#!/bin/sh\n{ cat qa/pull-tester/tests_config.ini; echo \"ARGS $*\"; } > %s/ran\n" % ws,
            "src/ycashd": "#!/bin/sh\necho 'Ycash Daemon version v6.22.0-beta2'\n",
        }
        for rel, text in files.items():
            path = os.path.join(tree, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            if rel.endswith(("rpc-tests.py", "ycashd")):
                os.chmod(path, 0o700)
        env = dict(os.environ, WS=ws, RC_OUT=os.path.join(ws, "out"), PYTHON=sys.executable)
        proc = subprocess.run(["bash", SCRIPT, "node-shard", "stock", "2", "2"], capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        with open(os.path.join(ws, "ran"), encoding="utf-8") as fh:
            ran = fh.read()
        self.assertIn("SRCDIR=%s" % tree, ran)
        self.assertIn("#ENABLE_ZMQ=true", ran)         # the stub's --help names no -zmqpub
        self.assertIn("ARGS --fail-on-skip -j4 --nocleanup s2 txn_doublespend.py --mineblock", ran)
        # a yellowback shard that names yellowback_chainviz needs the sidecar, or it fails before running
        with open(os.path.join(tree, ".github/workflows/yellowback-tests.yml"), "w", encoding="utf-8") as fh:
            fh.write(WORKFLOW.replace("a b c d e f g", "yellowback_chainviz"))
        env.pop("CHAINVIZ_BIN", None)
        proc = subprocess.run(["bash", SCRIPT, "node-shard", "yellowback", "1", "4"], capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("would SKIP", proc.stderr)


class Record(unittest.TestCase):
    A, B = "a" * 40, "b" * 40

    def run_json(self, **over):
        run = {"id": 7, "repository": {"full_name": "boyfromcave/ycash6"}, "path": ".github/workflows/yellowback-tests.yml",
               "head_sha": self.A, "status": "completed", "conclusion": "success"}
        run.update(over)
        return run

    def jobs(self, **over):
        names = {"build": "success", "push tier": "success", "nightly": "success", "weekly-fuzz": "skipped"}
        names.update(over)
        return [{"name": n, "conclusion": c} for n, c in names.items()]

    def test_node_suites_evidence(self):
        self.assertEqual(rc_record.node_suites(self.run_json(), self.jobs(), [self.A]), [])
        self.assertEqual(rc_record.node_suites(self.run_json(head_sha=self.B), self.jobs(), [self.A, self.B]), [])
        for run, jobs, want in ((self.run_json(head_sha=self.B), self.jobs(), "not the train's commit"),
                                (self.run_json(path=".github/workflows/rc-qualify.yml"), self.jobs(), "not .github/workflows/yellowback-tests.yml"),
                                (self.run_json(repository={"full_name": "someone/ycash6"}), self.jobs(), "not boyfromcave/ycash6"),
                                (self.run_json(conclusion="failure"), self.jobs(), "not completed/success"),
                                (self.run_json(), self.jobs(nightly="skipped"), "'nightly' is ['skipped']"),
                                (self.run_json(), [j for j in self.jobs() if j["name"] != "push tier"], "'push tier' is absent")):
            problems = rc_record.node_suites(run, jobs, [self.A])
            self.assertTrue(any(want in p for p in problems), (want, problems))

    def test_the_ci_build_run_must_carry_the_train_s_pins(self):
        pins = {"TRAIN_YOLO_COMMIT": "1" * 40, "TRAIN_CHAIN_VIZ_COMMIT": "2" * 40,
                "TRAIN_LIGHTWALLETD_DD_COMMIT": "3" * 40, "TRAIN_RELEASE_WORKSPACE": "4" * 40}
        self.assertEqual(rc_record.pin_problems(WORKFLOW, pins), [])
        problems = rc_record.pin_problems(WORKFLOW, dict(pins, TRAIN_YOLO_COMMIT="9" * 40))
        self.assertEqual(len(problems), 1)
        self.assertIn("YOLO_COMMIT=" + "1" * 40, problems[0])
        self.assertEqual(len(rc_record.pin_problems(WORKFLOW.replace("LWD_COMMIT", "LWD_X"), pins)), 1)

    def test_the_record_names_a_pin_mismatch(self):
        tmp = tempfile.mkdtemp(prefix="rc-record-")
        self.addCleanup(shutil.rmtree, tmp)
        files = {"run.json": json.dumps(self.run_json()), "jobs.json": json.dumps({"jobs": self.jobs()}),
                 "wf.yml": WORKFLOW, "pins.env": "TRAIN_YOLO_COMMIT=%s\nTRAIN_CHAIN_VIZ_COMMIT=%s\n"
                 "TRAIN_LIGHTWALLETD_DD_COMMIT=%s\nTRAIN_RELEASE_WORKSPACE=%s\n" % ("9" * 40, "2" * 40, "3" * 40, "4" * 40)}
        for name, text in files.items():
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        j = lambda name: os.path.join(tmp, name)
        proc = subprocess.run([sys.executable, os.path.join(HERE, "rc-record.py"), "node-suites", "--run", j("run.json"),
                               "--jobs", j("jobs.json"), "--commit", self.A, "--workflow", j("wf.yml"),
                               "--pins", j("pins.env"), "--out", j("ev.json")], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("YOLO_COMMIT", proc.stdout)
        proc = subprocess.run([sys.executable, os.path.join(HERE, "rc-record.py"), "record", "--pins", j("pins.env"),
                               "--evidence", j("ev.json")], capture_output=True, text=True,
                              env=dict(os.environ, R_NODE="failure"))
        rec = json.loads(proc.stdout)
        self.assertFalse(rec["qualified"])
        self.assertEqual(len(rec["node_suites_ci_build_problems"]), 1)
        self.assertIn("YOLO_COMMIT", rec["node_suites_ci_build_problems"][0])

    def test_paginated_jobs_are_read(self):
        fd, path = tempfile.mkstemp()
        self.addCleanup(os.unlink, path)
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps({"total_count": 2, "jobs": self.jobs()[:2]}) + "\n" + json.dumps({"jobs": self.jobs()[2:]}))
        self.assertEqual([j["name"] for j in rc_record.load_jobs(path)], ["build", "push tier", "nightly", "weekly-fuzz"])

    def test_the_record_names_node_and_harness_commits(self):
        env = {"R_TRAIN": "success", "R_CANDIDATE": "success", "R_NODE": "success", "R_NODE_PACKAGE": "success",
               "R_ECO": "success",
               "R_CROSS": "success", "R_CEREMONY": "success", "HARNESS_COMMIT": self.B, "BUILT_COMMIT": self.A,
               "GITHUB_REPOSITORY": "boyfromcave/yellowback", "GITHUB_RUN_ID": "9", "DRAFT": "false",
               "TRAIN_FILE": "releases/v6.22.0-beta2.yaml"}
        pins = {"TRAIN_YCASH6_COMMIT": self.A, "TRAIN_YCASH6_TAG": "v6.22.0-beta2", "TRAIN_RELEASE_VERSION": "6.22.0-beta2"}
        rec = rc_record.record(env, pins)
        self.assertTrue(rec["qualified"])
        self.assertEqual((rec["commit"], rec["harness_commit"], rec["tag"]), (self.A, self.B, "v6.22.0-beta2"))
        self.assertEqual(rec["run"], "https://github.com/boyfromcave/yellowback/actions/runs/9")
        self.assertFalse(rc_record.record(dict(env, R_NODE="skipped"), pins)["qualified"])
        self.assertFalse(rc_record.record(dict(env, R_NODE_PACKAGE="failure"), pins)["qualified"])
        self.assertEqual(rec["node_suites_binary"]["1-node-suites-package"], "package")
        self.assertEqual(rec["node_suites_binary"]["1-node-suites-ci-build"], "ci-build")
        self.assertFalse(rc_record.record({k: v for k, v in env.items() if k != "R_CEREMONY"}, pins)["qualified"])


if __name__ == "__main__":
    unittest.main()

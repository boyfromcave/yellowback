#!/usr/bin/env python3
"""Unit tests for scripts/release-train.py (testnet plan §5.4). Offline: the online checks run against
local fixture repositories over file://, never the network."""
import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("release_train", os.path.join(HERE, "release-train.py"))
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)

ATT = "ab" * 32


def train_text(version="6.22.0-rc1", commits=None, extra="", **net):
    commits = commits or {}
    values = {"fast-vault-height": "510400", "fast-set-id": ATT, "slow-vault-height": "none",
              "slow-set-id": "none", "bundle-height": "none"}
    values.update({k.replace("_", "-"): v for k, v in net.items()})
    out = ["# a release train", "release:", "  version: %s" % version, "  rpcversion: 8",
           "  workspace: %s" % commits.get("workspace", "1" * 40), "testnet:"]
    out += ["  %s: %s   # comment" % (k, v) for k, v in values.items()]
    for name in rt.COMPONENTS:
        out.append("%s:" % name)
        out.append("  commit: %s" % commits.get(name, "2" * 40))
        if name in rt.TAGGED:
            out.append("  tag: %s" % rt.TAGGED[name].format(version=version))
    return "\n".join(out) + "\n" + extra


def git(cwd, *args):
    return subprocess.run(["git"] + list(args), cwd=cwd, check=True, capture_output=True, text=True,
                          env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                                   GIT_COMMITTER_EMAIL="t@t")).stdout.strip()


def make_repo(path, files, branch="upgrade/vault"):
    os.makedirs(path)
    git(path, "init", "-q", "-b", branch)
    git(path, "config", "uploadpack.allowFilter", "true")
    git(path, "config", "uploadpack.allowAnySHA1InWant", "true")
    for rel, text in files.items():
        full = os.path.join(path, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(text)
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "c")
    return git(path, "rev-parse", "HEAD")


class Shape(unittest.TestCase):
    def check(self, text, name="v6.22.0-rc1.yaml"):
        return rt.validate(rt.parse_flat(text, name), name)

    def test_a_good_rc_train(self):
        self.assertEqual(self.check(train_text()), [])
        lines = rt.pins(rt.parse_flat(train_text(), "x"))
        self.assertIn("TRAIN_RELEASE_VERSION=6.22.0-rc1", lines)
        self.assertIn("TRAIN_TESTNET_FAST_SET_ID=" + ATT, lines)
        self.assertIn("TRAIN_CHAIN_VIZ_COMMIT=" + "2" * 40, lines)
        self.assertIn("TRAIN_YCASH_DD_TAG=vault-params/v6.22.0-rc1", lines)

    def test_every_component_and_field_is_required(self):
        text = train_text().replace("hawkeye:\n  commit: %s\n" % ("2" * 40), "")
        self.assertIn("missing component hawkeye", self.check(text))
        self.assertIn("missing release.workspace", self.check(train_text().replace("  workspace: " + "1" * 40 + "\n", "")))
        self.assertIn("unknown section extra", self.check(train_text(extra="extra:\n  a: b\n")))
        self.assertIn("unknown field yolo.tag", self.check(train_text().replace("yolo:\n", "yolo:\n  tag: x\n")))

    def test_values_are_checked(self):
        self.assertTrue(any("not a full 40-hex" in p for p in self.check(train_text(commits={"yew": "abc"}))))
        self.assertTrue(any("not a 6.22.x" in p for p in self.check(train_text(version="6.21.0-rc1"), "v6.21.0-rc1.yaml")))
        self.assertTrue(any("64-hex set id" in p for p in self.check(train_text(fast_set_id="0" * 64))))
        self.assertTrue(any("not a height" in p for p in self.check(train_text(bundle_height="-5"))))
        self.assertIn("the file of release 6.22.0-rc1 is releases/v6.22.0-rc1.yaml", self.check(train_text(), "v6.22.0-rc2.yaml"))
        bad_tag = train_text().replace("tag: v6.22.0-rc1", "tag: v6.22.0-rc2")
        self.assertIn("ycash6.tag must be v6.22.0-rc1", self.check(bad_tag))

    def test_stage_rules_follow_the_node_guard(self):
        # rc and final name fast; final names slow too; a set only with its height; beta needs nothing.
        self.assertIn("an rc names testnet-yb-fast's vault height and set id", self.check(train_text(fast_set_id="none")))
        self.assertEqual(self.check(train_text(slow_vault_height="520000")), [])
        self.assertIn("testnet.slow-set-id without testnet.slow-vault-height", self.check(train_text(slow_set_id=ATT)))
        final = train_text(version="6.22.0")
        self.assertIn("a final release names testnet-yb-slow's vault height and set id", self.check(final, "v6.22.0.yaml"))
        final = train_text(version="6.22.0", slow_vault_height="520000", slow_set_id=ATT)
        self.assertEqual(self.check(final, "v6.22.0.yaml"), [])
        beta = train_text(version="6.22.0-beta1", fast_vault_height="none", fast_set_id="none")
        self.assertEqual(self.check(beta, "v6.22.0-beta1.yaml"), [])

    def test_the_flat_shape_is_strict(self):
        for bad in ("release:\n version: x\n", "release:\n  version: a\n  version: b\n", "  orphan: x\n",
                    "release:\nrelease:\n"):
            with self.assertRaises(rt.TrainError):
                rt.parse_flat(bad, "x")

    def test_readers(self):
        self.assertEqual(rt.node_rpcversion("static const int YELLOWBACK_RPC_VERSION = 8;   // 8: fees"), 8)
        self.assertIsNone(rt.node_rpcversion("nothing"))
        self.assertEqual(rt.contract_rpcversion('{"rpcversion": 8}'), 8)
        self.assertIsNone(rt.contract_rpcversion('{"rpcversion": true}'))
        self.assertIsNone(rt.contract_rpcversion("not json"))
        self.assertEqual(rt.wyec_pin("x\nWYEC_COMMIT=%s\n" % ("e" * 40)), "e" * 40)


class Online(unittest.TestCase):
    """check_online against file:// fixtures: every component a one-commit repository."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="release-train-test-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.wyec = make_repo(os.path.join(self.tmp, "src", "wyec"), {"README": "wyec\n"})
        node = {"src/rpc/yellowback.cpp": "static const int YELLOWBACK_RPC_VERSION = 8;\n",
                "doc/yellowback-rpc-contract.json": '{"rpcversion": 8}\n'}
        files = {
            "ycash6": node, "ycash-dd": node,
            "yecwallet-dd": {"docs/yellowback-rpc-contract.json": '{"rpcversion": 8}\n'},
            "lightwalletd-dd": {"testdata/yellowback/contract.json": '{"rpcversion": 8}\n'},
            "hawkeye": {"eth/tools/fetch-wyec.sh": "WYEC_COMMIT=%s\n" % self.wyec},
        }
        self.commits = {"wyec": self.wyec}
        manifest = ["wyec:", "  url: file://%s/src/wyec" % self.tmp, "  branch: upgrade/vault"]
        for name in rt.COMPONENTS:
            if name == "wyec":
                continue
            self.commits[name] = make_repo(os.path.join(self.tmp, "src", name), files.get(name, {"README": name + "\n"}))
            manifest += ["%s:" % name, "  url: file://%s/src/%s" % (self.tmp, name), "  branch: upgrade/vault"]
        self.commits["workspace"] = make_repo(os.path.join(self.tmp, "src", "workspace"),
                                              {"scripts/extract_spec.py": "", "docs/x.md": ""})
        repos_file = os.path.join(self.tmp, "repos.yaml")
        with open(repos_file, "w", encoding="utf-8") as fh:
            fh.write("\n".join(manifest) + "\n")
        self.saved = rt.REPOS_FILE, rt.WORKSPACE_URL, rt.spec_check
        rt.REPOS_FILE, rt.WORKSPACE_URL = repos_file, "file://%s/src/workspace" % self.tmp
        self.spec_calls = []
        rt.spec_check = lambda ws, mode, trees: (self.spec_calls.append((ws, mode, trees)) or (True, "spec ok"))

    def tearDown(self):
        rt.REPOS_FILE, rt.WORKSPACE_URL, rt.spec_check = self.saved

    def run_check(self, text):
        train = rt.parse_flat(text, "x")
        self.assertEqual(rt.validate(train), [])
        scratch = tempfile.mkdtemp(dir=self.tmp)
        with contextlib.redirect_stdout(io.StringIO()):
            return rt.check_online(train, scratch, log=lambda *_: None)

    def test_a_consistent_train_passes(self):
        self.assertEqual(self.run_check(train_text(commits=self.commits)), [])
        (ws, mode, trees), = self.spec_calls
        self.assertEqual(mode, "--check-fees")
        self.assertTrue(os.path.isfile(os.path.join(trees["EXTRACT_SPEC_WALLET_DIR"], "docs", "yellowback-rpc-contract.json")))
        self.assertTrue(os.path.isfile(os.path.join(ws, "scripts", "extract_spec.py")))

    def test_a_commit_off_the_branch_is_refused(self):
        side = os.path.join(self.tmp, "src", "yolo")
        git(side, "checkout", "-q", "-b", "side")
        with open(os.path.join(side, "x"), "w", encoding="utf-8") as fh:
            fh.write("x")
        git(side, "add", "x")
        git(side, "commit", "-q", "-m", "side")
        off = git(side, "rev-parse", "HEAD")
        git(side, "checkout", "-q", "upgrade/vault")
        problems = self.run_check(train_text(commits=dict(self.commits, yolo=off)))
        self.assertTrue(any(p.startswith("yolo: %s is not on upgrade/vault" % off) for p in problems), problems)

    def test_a_tag_on_another_commit_is_refused(self):
        repo = os.path.join(self.tmp, "src", "ycash6")
        with open(os.path.join(repo, "y"), "w", encoding="utf-8") as fh:
            fh.write("y")
        git(repo, "add", "y")
        git(repo, "commit", "-q", "-m", "later")
        git(repo, "tag", "-a", "v6.22.0-rc1", "-m", "rc1")
        problems = self.run_check(train_text(commits=self.commits))
        self.assertTrue(any("tag v6.22.0-rc1 names" in p for p in problems), problems)

    def test_rpcversion_and_wyec_disagreements(self):
        repo = os.path.join(self.tmp, "src", "lightwalletd-dd")
        with open(os.path.join(repo, "testdata/yellowback/contract.json"), "w", encoding="utf-8") as fh:
            fh.write('{"rpcversion": 7}\n')
        git(repo, "commit", "-q", "-am", "old contract")
        commits = dict(self.commits, **{"lightwalletd-dd": git(repo, "rev-parse", "HEAD")})
        problems = self.run_check(train_text(commits=commits))
        self.assertEqual(problems, ["lightwalletd-dd: testdata/yellowback/contract.json states rpcversion 7, the train says 8"])
        # A wyec commit on its branch but not the one hawkeye fetches.
        wyec = os.path.join(self.tmp, "src", "wyec")
        with open(os.path.join(wyec, "z"), "w", encoding="utf-8") as fh:
            fh.write("z")
        git(wyec, "add", "z")
        git(wyec, "commit", "-q", "-m", "newer")
        newer = git(wyec, "rev-parse", "HEAD")
        problems = self.run_check(train_text(commits=dict(self.commits, wyec=newer)))
        self.assertEqual(problems, ["hawkeye: eth/tools/fetch-wyec.sh pins wyec %s, the train says %s" % (self.wyec, newer)])
        self.assertEqual(self.spec_calls, [])

if __name__ == "__main__":
    unittest.main()

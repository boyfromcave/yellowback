#!/usr/bin/env python3
# Copyright (c) 2026 The Ycash developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://www.opensource.org/licenses/mit-license.php .

"""The two judgements of rc-qualify that read GitHub's answers rather than run a program (qualify/README.md).

In plain words: step 1 of a qualification is the node's own test suites. Their functional shards run
here against the release package (rc-qualify.sh node-shard); the tiers that need a build of their
own (the unit tests, the nightly, the instrumented variants) run in the node's repository, and this
checks that the run it is given really is that: green, at the train's commit, with the train's
client pins. The record is the run's result: what was qualified (the node and client commits of the train), by which
harness commit, and whether every step passed.

  rc-record.py node-suites --run RUN.json --jobs JOBS.json --commit SHA [--commit SHA]
                          --workflow YELLOWBACK-TESTS.yml --pins rc-train.env
      RUN.json  = gh api repos/boyfromcave/ycash6/actions/runs/<id>
      JOBS.json = gh api repos/boyfromcave/ycash6/actions/runs/<id>/jobs --paginate (one object per page)
      Passes when the run is ycash6's yellowback-tests.yml, completed/success, at one of the --commit
      values (the train's ycash6 commit, or the commit that built the candidate), with tier "all":
      its "push tier" and "nightly" jobs both succeeded. And --workflow (ycash6's yellowback-tests.yml
      at the run's commit) with --pins: the workflow's default client pins (YOLO_COMMIT,
      CHAINVIZ_COMMIT, LWD_COMMIT, YB_WORKSPACE_COMMIT) must be the train's: a dispatch cannot
      change them, so a run with other pins tested other clients.

  rc-record.py record --pins rc-train.env
      Prints the record JSON from the environment the record job sets (see .github/workflows/rc-qualify.yml).

Python 3 standard library only.
"""
import argparse
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

NODE_REPO = "boyfromcave/ycash6"
NODE_SUITES = ".github/workflows/yellowback-tests.yml"
# Tier "all" = the push tier and the nightly tier (yellowback-tests.yml); each ends in one job of this name.
TIER_ALL_JOBS = ("push tier", "nightly")
# The node workflow's pin -> the train's pin line.
PIN_TRAIN = {"YOLO_COMMIT": "TRAIN_YOLO_COMMIT", "CHAINVIZ_COMMIT": "TRAIN_CHAIN_VIZ_COMMIT",
             "LWD_COMMIT": "TRAIN_LIGHTWALLETD_DD_COMMIT", "YB_WORKSPACE_COMMIT": "TRAIN_RELEASE_WORKSPACE"}
STEPS = (("train", "R_TRAIN"), ("candidate", "R_CANDIDATE"), ("1-node-suites-package", "R_NODE_PACKAGE"),
         ("1-node-suites-ci-build", "R_NODE"),
         ("2-ecosystem", "R_ECO"), ("3-cross-line", "R_CROSS"), ("4-ceremony", "R_CEREMONY"))


def load_jobs(path):
    """`gh api --paginate` prints one JSON object per page; accept those, or one list of jobs."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    jobs, decoder, at = [], json.JSONDecoder(), 0
    while True:
        while at < len(text) and text[at].isspace():
            at += 1
        if at >= len(text):
            return jobs
        page, at = decoder.raw_decode(text, at)
        jobs.extend(page["jobs"] if isinstance(page, dict) else page)


def node_suites(run, jobs, commits):
    """The problems with RUN as step 1's evidence (empty: it is)."""
    problems = []
    repo = (run.get("repository") or {}).get("full_name")
    if repo != NODE_REPO:
        problems.append("run %s is in %s, not %s" % (run.get("id"), repo, NODE_REPO))
    if run.get("path") != NODE_SUITES:
        problems.append("run %s is %s, not %s" % (run.get("id"), run.get("path"), NODE_SUITES))
    if run.get("head_sha") not in commits:
        problems.append("run %s tested %s, not the train's commit (%s)" % (run.get("id"), run.get("head_sha"), ", ".join(commits)))
    if (run.get("status"), run.get("conclusion")) != ("completed", "success"):
        problems.append("run %s is %s/%s, not completed/success" % (run.get("id"), run.get("status"), run.get("conclusion")))
    by_name = {}
    for job in jobs:
        by_name.setdefault(job.get("name"), []).append(job.get("conclusion"))
    for name in TIER_ALL_JOBS:
        got = by_name.get(name)
        if got != ["success"]:
            problems.append("run %s: job %r is %s, not success (tier all runs it)" % (run.get("id"), name, got or "absent"))
    return problems


def suites_module():
    spec = importlib.util.spec_from_file_location("rc_suites", os.path.join(HERE, "rc-suites.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pin_problems(workflow_text, pins):
    """The node workflow's default client pins that are not the train's."""
    suites = suites_module()
    env = suites.workflow_env(workflow_text)
    problems = []
    for name, train_key in PIN_TRAIN.items():
        got, want = suites.default_pin(env.get(name, "")), pins.get(train_key)
        if got != want:
            problems.append("the node's yellowback-tests.yml pins %s=%s, the train %s=%s" % (name, got, train_key, want))
    return problems


def read_pins(path):
    pins = {}
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                key, _, value = line.strip().partition("=")
                if key:
                    pins[key] = value
    return pins


def record(env, pins):
    steps = {name: env.get(var) or "absent" for name, var in STEPS}
    server = env.get("GITHUB_SERVER_URL", "https://github.com")
    return {
        "train_file": env.get("TRAIN_FILE"),
        "version": env.get("VERSION") or pins.get("TRAIN_RELEASE_VERSION"),
        "stage": env.get("STAGE"),
        "tag": pins.get("TRAIN_YCASH6_TAG"),
        # The node under qualification: the train's ycash6 commit (the tag's) and the commit that built
        # the package (the same on a tag; a proving run's may be an ancestor, qa/doc/.github apart).
        "commit": pins.get("TRAIN_YCASH6_COMMIT"),
        "built_commit": env.get("BUILT_COMMIT"),
        # The harness that ran the steps: this workspace's commit. A harness fix moves only this.
        "harness_repository": env.get("GITHUB_REPOSITORY"),
        "harness_commit": env.get("HARNESS_COMMIT"),
        "linux_x86_64_sha256": env.get("PACKAGE_SHA256"),
        "draft": env.get("DRAFT") == "true",
        "proving_run": env.get("DRAFT") == "proving",
        "release_run": env.get("RELEASE_RUN") or None,
        "node_suites_run": env.get("NODE_SUITES_RUN") or None,
        # Which binary each half of step 1 ran: the functional shards the package's (this run), the
        # node's own tier-all run (unit, nightly, instrumented variants) a CI build of the same commit.
        "node_suites_binary": {"1-node-suites-package": "package", "1-node-suites-ci-build": "ci-build"},
        "run": "%s/%s/actions/runs/%s" % (server, env.get("GITHUB_REPOSITORY"), env.get("GITHUB_RUN_ID")),
        "steps": steps,
        "train": pins,
        # A step switched off, or not given its evidence, is "skipped": the record is then not a qualification.
        "qualified": all(v == "success" for v in steps.values()),
    }


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    ns = sub.add_parser("node-suites")
    ns.add_argument("--run", required=True)
    ns.add_argument("--jobs", required=True)
    ns.add_argument("--commit", action="append", required=True)
    ns.add_argument("--workflow", required=True)
    ns.add_argument("--pins", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("--pins")
    args = ap.parse_args(argv)
    if args.command == "node-suites":
        commits = [c for c in args.commit if c]
        if not commits or not all(re.match(r"^[0-9a-f]{40}$", c) for c in commits):
            print("FAIL --commit takes full 40-hex commits: %s" % args.commit)
            return 1
        with open(args.run, encoding="utf-8") as fh:
            run = json.load(fh)
        problems = node_suites(run, load_jobs(args.jobs), commits)
        if args.workflow:
            with open(args.workflow, encoding="utf-8") as fh:
                problems += pin_problems(fh.read(), read_pins(args.pins))
        for problem in problems:
            print("FAIL " + problem)
        if not problems:
            print("ok   step 1: %s run %s, tier all, green at %s" % (NODE_SUITES, run["id"], run["head_sha"]))
        return 1 if problems else 0
    print(json.dumps(record(os.environ, read_pins(args.pins)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

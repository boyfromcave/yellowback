#!/usr/bin/env python3
# Copyright (c) 2026 The Ycash developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://www.opensource.org/licenses/mit-license.php .

"""Step 1 of rc-qualify against the package: the node's own functional lists, read from the node tree.

In plain words: the node's merge gate runs its functional test scripts in shards (ycash6
.github/workflows/yellowback-tests.yml, job `functional`). The qualification runs the same scripts,
in the same shards, against the release package's binaries. The lists are never copied here: they
are read from the workflow file of the ycash6 tree under qualification, so they are always that
commit's own.

  rc-suites.py lists WORKFLOW SUITE SHARD OF
      print the scripts of shard SHARD of OF of SUITE (yellowback: YELLOWBACK_SCRIPTS; stock:
      STOCK_BASELINE, its last shard also STOCK_BASELINE_MINEBLOCK), round-robin as the job does,
      one per line
  rc-suites.py config TEMPLATE TREE [--no-zmq]
      print qa/pull-tester/tests_config.ini for TREE from its tests_config.ini.in (what configure
      writes: SRCDIR = BUILDDIR = TREE, no EXEEXT, wallet, utils and daemon enabled; zmq unless
      --no-zmq)
  rc-suites.py pins WORKFLOW
      print the workflow's default client pins as TRAIN-style KEY=VALUE lines (YOLO_COMMIT,
      CHAINVIZ_COMMIT, LWD_COMMIT, YB_WORKSPACE_COMMIT)

Python 3 standard library only.
"""
import re
import sys

SUITES = {"yellowback": "YELLOWBACK_SCRIPTS", "stock": "STOCK_BASELINE"}
PINS = ("YOLO_COMMIT", "CHAINVIZ_COMMIT", "LWD_COMMIT", "YB_WORKSPACE_COMMIT")


def workflow_env(text):
    """The top-level `env:` block of a workflow, as {NAME: value} (one-line values, quotes removed).
    Anything else in the block (a value continued on the next line, a block scalar) is an error, never
    a shorter list."""
    env, inside = {}, False
    for n, line in enumerate(text.splitlines(), 1):
        if re.match(r"^env:\s*(#.*)?$", line):
            inside = True
            continue
        if inside and re.match(r"^\S", line):
            break
        if not inside or not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^  ([A-Z][A-Z0-9_]*):\s*(.*?)\s*$", line)
        if not m:
            raise ValueError("workflow line %d: not a one-line `  NAME: value` env entry (a continued value?): %r" % (n, line))
        value = m.group(2)
        if not value or value[:1] in "|>":
            raise ValueError("workflow line %d: %s has no one-line value (a block or continued value?)" % (n, m.group(1)))
        if value[:1] in "'\"":
            end = value.find(value[0], 1)
            value = value[1:end] if end > 0 else value[1:]
        else:
            value = re.sub(r"\s+#.*$", "", value)
        env[m.group(1)] = value
    return env


def default_pin(value):
    """`${{ inputs.x || '<40-hex>' }}` -> the 40-hex default; a bare 40-hex value as is."""
    m = re.search(r"'([0-9a-f]{40})'", value) or re.match(r"^([0-9a-f]{40})$", value)
    return m.group(1) if m else None


def shard(env, suite, n, of):
    if suite not in SUITES:
        raise ValueError("suite is yellowback or stock, not %r" % suite)
    if not 1 <= n <= of:
        raise ValueError("shard %d of %d" % (n, of))
    names = env.get(SUITES[suite], "").split()
    if not names:
        raise ValueError("the workflow has no %s" % SUITES[suite])
    sel = [name for i, name in enumerate(names) if i % of == n - 1]
    if suite == "stock" and n == of:
        if not env.get("STOCK_BASELINE_MINEBLOCK"):
            raise ValueError("the workflow has no STOCK_BASELINE_MINEBLOCK (the stock suite's last shard runs it)")
        sel.append(env["STOCK_BASELINE_MINEBLOCK"])
    return sel


def config(template, tree, zmq=True):
    out = template.replace("@abs_top_srcdir@", tree).replace("@abs_top_builddir@", tree).replace("@EXEEXT@", "")
    for flag in ("ENABLE_WALLET", "BUILD_BITCOIN_UTILS", "BUILD_BITCOIND"):
        out = out.replace("@%s_TRUE@" % flag, "")
    out = out.replace("@ENABLE_ZMQ_TRUE@", "" if zmq else "#")
    left = re.findall(r"@[A-Za-z_]+@", out)
    if left:
        raise ValueError("tests_config.ini.in has substitutions this does not know: %s" % ", ".join(sorted(set(left))))
    return out


def main(argv):
    if len(argv) == 5 and argv[0] == "lists":
        with open(argv[1], encoding="utf-8") as fh:
            env = workflow_env(fh.read())
        print("\n".join(shard(env, argv[2], int(argv[3]), int(argv[4]))))
        return 0
    if len(argv) in (3, 4) and argv[0] == "config" and argv[3:] in ([], ["--no-zmq"]):
        with open(argv[1], encoding="utf-8") as fh:
            sys.stdout.write(config(fh.read(), argv[2], zmq=argv[3:] != ["--no-zmq"]))
        return 0
    if len(argv) == 2 and argv[0] == "pins":
        with open(argv[1], encoding="utf-8") as fh:
            env = workflow_env(fh.read())
        for name in PINS:
            print("%s=%s" % (name, default_pin(env.get(name, "")) or ""))
        return 0
    print(__doc__.split("\n\n")[2], file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except ValueError as error:
        print("rc-suites: %s" % error, file=sys.stderr)
        sys.exit(1)

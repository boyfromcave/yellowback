#!/usr/bin/env python3
# Copyright (c) 2026 The Ycash developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://www.opensource.org/licenses/mit-license.php .
"""Relative-link sanity check for the workspace's tracked Markdown (the workspace CI).

Every `[text](path)` link in a tracked *.md file whose target is a relative path must name a file
or directory that exists in this repository. Skipped: URLs (`scheme:`), in-page anchors, links
inside fenced code blocks, and targets inside the nested clones listed in repos.yaml or under
wt/ (they are not part of this repository, so a fresh checkout does not have them).

Exit 0 when every checked link resolves; 1 with one `file: target` line per broken link.
Standard library only.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"^(```|~~~).*?^\1", re.S | re.M)


def nested_clones():
    out = {"wt"}
    with open(os.path.join(ROOT, "repos.yaml"), encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^([\w./-]+):\s*(#.*)?$", line)
            if m:
                out.add(m.group(1).rstrip("/"))
    return out


def main():
    os.chdir(ROOT)
    files = subprocess.run(["git", "ls-files", "*.md"], capture_output=True, text=True, check=True).stdout.split()
    skip = nested_clones()
    checked, broken = 0, []
    for name in files:
        with open(name, encoding="utf-8") as f:
            text = FENCE.sub("", f.read())
        for m in LINK.finditer(text):
            target = m.group(1)
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target) or target.startswith("#"):
                continue
            path = target.split("#", 1)[0]
            if not path:
                continue
            full = os.path.normpath(os.path.join(os.path.dirname(name), path))
            if full.startswith(".."):
                broken.append((name, target))
                continue
            if any(full == n or full.startswith(n + os.sep) for n in skip):
                continue
            checked += 1
            if not os.path.exists(full):
                broken.append((name, target))
    for name, target in broken:
        print("%s: %s" % (name, target))
    print("check-md-links: %d files, %d relative links checked, %d broken" % (len(files), checked, len(broken)))
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
r"""Publish the normative parts of the Yellowback v2 plan through a tool, not a copy (plan Phase 0; N29, P4, P7).

Run through scripts/extract-spec.sh (`make spec` / `make spec-check`), always with the workspace venv.

READS
  docs/plans/yellowback-v2-development-plan.md       the plan (the wording of record)
  docs/plans/yellowback-v3-development-plan.md       optional: the v3 delta plan (Phase A0+); its section 3 is
                                                     appended to the spec and its 4.5 heading supplies rpcversion
  ycash-dd/doc/yellowback-rpc.md                     optional: the fork's RPC contract document (Phase 3+); from
                                                     Phase A0 its "Error identifiers" tables are the error table
  ycash6/doc/yellowback-rpc.md                       the same for the 6.20.0 node line (its contract is built from it)
  docs/plans/yellowback-upgrade-plan.md              the upgrade line only (below): its section 10 trust statement and
                                                     its section 15 are that line's spec; must have its `### 15.10`
                                                     heading, which the contract cites as sectionUpgrade

WRITES (`--write`) or COMPARES (`--check`, exit 1 when any copy is missing or stale)
  docs/spec/yellowback-spec.md                       the spec: header + body (below)
  ycash-dd/doc/yellowback-spec.md                    byte-identical copy the fork's CI can see (P4)
  ycash6/doc/yellowback-spec.md                      byte-identical copy for the 6.20.0 node line
  ycash-dd/doc/yellowback-rpc-contract.json          the RPC contract (P7)
  yecwallet-dd/docs/yellowback-rpc-contract.json     byte-identical copy for the wallet fork
  lightwalletd-dd/testdata/yellowback/contract.json  byte-identical copy for the light-client server (its offline suite's fixture)
  ycash6/doc/yellowback-rpc-contract.json            the 6.20.0 line's contract, from ycash6/doc/yellowback-rpc.md (its
                                                     6.20.0 notes differ in places; everything else matches ycash-dd's)

THE SPEC FILE
  line 1      `Source: yellowback-v2-development-plan.md revision N; sha256: <64 hex>`
              (with the v3 plan present: `… revision N + yellowback-v3-development-plan.md revision M; sha256: …`)
  line 2      a "generated, do not edit" note (never the bare string `---`)
  line 3      `---`
  body        the plan's lines from the line `## 3. …` up to (not including) the line `## 4. …`,
              then one blank line, then the lines from `### 8.1 …` up to (not including) `### 8.2 …`,
              verbatim, each line terminated by "\n";  then, when the v3 plan exists, one blank line, a
              `## v3 delta …` heading line written by this script, and the v3 plan's lines from `## 3. …`
              up to (not including) `## 4. …` (its 3.1–3.10; v2 rules where it is silent).
              With the v3 plan present, §8.1 above is v2's §8.1 followed by the v3 plan's §8.1 **with its
              heading dropped** — one heading-free block, because doc/yellowback.md's Trust statement must
              match it byte for byte and the fork's check reads only up to the next `#` (P4).
  N is the highest `### Revision N` heading of the plan's §0.  The sha256 is over exactly the body
  bytes, so the fork-local check   sed '1,/^---$/d' FILE | sha256sum   reproduces it (§6.0 item 6).

THE UPGRADE SPEC FILE  (the upgrade line's doc/yellowback-spec.md, both node lines; never docs/spec)
  line 1      `Source: yellowback-upgrade-plan.md revision N; sha256: <64 hex>`, N the highest `**Revision N`
              paragraph opening of the upgrade plan; lines 2-3 as above (the sha256 check is the same)
  body        a `## Vault upgrade specification - …` line written by this script (the marker the upgrade-line
              checks grep for, in place of `## v3 delta`), a blank line, a `### 8.1 Trust statement …` heading
              written by this script, a blank line, the upgrade plan's section 10 trust statement -- the lines
              after `**Trust statement (replaces hardening …` up to (not including) `**What is given up:**`,
              blank edges trimmed -- one blank line, then the plan's `## 15. …` up to the next `## ` heading or
              the end of the file (all of 15.0-15.10), blank edges trimmed, each line terminated by "\n".
              8.1 comes first and carries no `#` line, so the forks' §8.1 / `## Trust statement` check reads
              exactly the trust statement; doc/yellowback.md's Trust statement must match it byte for byte.
  Nothing of the v2 or v3 plan is in it: the v2 §3 + v3 delta spec is the harden line's.

THE CONTRACT JSON  (sorted keys, 2-space indent, trailing newline; identical in both forks)
  {
    "rpcversion": <int>,            from the §4.5 heading "(`rpcversion = N`)" — of the v3 plan when it exists —
                                    unless the rpc doc's title line names one ("…, rpcversion N"): the doc wins,
                                    as it does for shapes and args (hardening H-9.3 bumped it to 4 in the doc alone)
    "source": {"plan": "...", "revision": N, "section": "4.5", "rpcdoc": <path or null>,
               "planV3": <path or null>, "revisionV3": <M or null>},
    "errors": {"<identifier>": {"raisedBy": ["yed_…", …], "when": "…"}, …},   the §4.5 error table, then every
                                    table under the rpc doc's `## Error identifiers` heading merged over it
                                    (identifier by identifier; the doc wins) — the v3 identifiers live only there
    "yed_<name>": {"args": "<argument list as written, may be empty>", "returns": <shape>},  one per command
  }
  <shape> is a JSON object mapping each documented field name to
      ""             a scalar with no annotation,
      "<text>"       the annotation after the field name (e.g. "2" for `rpcversion: 2`, "null when undefined"),
      {…}            a nested object (same rules),
      [{…}]          an array of such objects,   [ "<text>", … ]   an array of scalars,
  or a one-element JSON array [ <object> ] when the command returns a list of rows.  {} means
  §4.5 names the command but gives no shape ("unchanged").  Parenthesised asides inside a shape are
  dropped; `\|` becomes `|`.  Field ORDER is not preserved (keys are sorted) — the contract is about
  names and nesting, not order.

  Source of the shapes, in precedence order:
    1. ycash-dd/doc/yellowback-rpc.md, when it exists: every fenced block opened by a line that
       starts with ```json whose nearest preceding non-blank line contains a `yed_<name>` in
       backticks (the first such span on that line) is parsed as JSON and becomes that command's
       "returns" verbatim (an example value is a shape too: field names and nesting are what
       matter).  A list result is written as a one-element array in the doc as well.  Phase 3
       writes the node context of that document in this form; Phase 6 the wallet context.  A
       command heading `### `yed_<name> <args>`` in that document supplies "args" (the doc wins
       over the plan; Phase A0 changed `yed_mint`'s and added commands the v2 plan never named).
    2. Plan §4.5, deterministically: the text from the `### 4.5` heading up to the line that
       starts `**Error identifiers` is scanned for backtick spans in order.  A span matching
       `yed_<name>` optionally followed by whitespace and arguments names the current command
       (its first such span supplies "args"; dotted references like `yed_getinfo.abandoned` do
       not switch the command).  A span beginning with `{` or `[{` is the current command's
       shape unless it already has one.  Two idioms are recognised: `yed_A` + `{…}` merges A's
       shape with the braces into the command named before A ("`yed_listpositions` rows =
       `yed_getvault` + `{…}`"), and "(same return shape)" right after a command copies the
       shape most recently assigned.  The word "row"/"rows" between the command and its shape
       marks a list result.
  The wallet's field names (yecwallet-dd/src/yellowbackrpc.h) are checked against this file by
  the `wallet` CI job from Phase 7b; the node's registered `yed_*` names must all be keys (`audit`).

TWO LINES  (upgrade plan findings (39), (44))
  Each contract is generated for the line its rpc doc belongs to.  The line is `upgrade` when the doc's
  title states rpcversion >= 5 (the `upgrade/vault` branches: UPGRADE_VAULT, YED on the primitive) and
  `harden` otherwise; EXTRACT_SPEC_LINE=harden|upgrade forces it.  The harden line is generated exactly as
  described above.  On the upgrade line the node's rpc doc is the WHOLE contract: its `### `yed_*``
  headings and ```json blocks are the command list and its `## Error identifiers` tables are the error
  table, and nothing is taken from v2's §4.5 (v2/v3 commands and errors the upgrade retired --
  `yed_sweep`, `sweep-*`, `mintpol-participation` -- would otherwise come back from the plan).  The
  plans then supply only the `source` metadata, which gains
      "planUpgrade": "docs/plans/yellowback-upgrade-plan.md", "sectionUpgrade": "15.10".
  The doc must state rpcversion and give every command both a heading and a JSON block.

THE IN-TERM LINE  (`upgrade/vault-in-term`, docs/plans/yellowback-in-term-claims-plan.md; `--write-in-term` /
  `--check-in-term`, `make spec-in-term` / `make spec-check-in-term`)
  The line is `interm` when the rpc doc's title states rpcversion >= 6 (EXTRACT_SPEC_LINE=interm forces it); a tree
  on it is skipped by --check-upgrade/--write-upgrade, and the upgrade line's output is unchanged by anything here.
  Spec   line 1 `Source: yellowback-upgrade-plan.md revision N + yellowback-in-term-claims-plan.md revision M; sha256: …`
         (M the highest `**Revision M` paragraph opening of the in-term plan); lines 2-3 as above.  Body: the upgrade
         spec body (above) with two changes -- its marker line names the overlay, and in the 8.1 trust statement the
         bullet that opens `- Collateral` is replaced by `- ` + the in-term plan's IT-8 promise (the text between
         `**"` and `"**` in the `- **IT-8` bullet, whitespace collapsed, wrapped at 100 columns with a two-space
         continuation indent, never breaking before `%`) -- then one blank line, an `## In-term claims delta …` line
         written by this script, a blank line and the in-term plan's lines from `## 3. ` up to (not including)
         `## 5. ` (its parameters, rules IT-1..IT-9 and the 4.1 contract delta), blank edges trimmed.
  Contract  the upgrade-line contract of the tree's rpc doc (above), then the in-term plan's `### 4.1` section
         applied: `rpcversion` from its heading (the doc's title must state the same), every ```json block (named
         by the nearest non-blank line above it, as in the rpc doc; a `#### `yed_x <args>`` heading gives args)
         deep-merged into that command's `returns` (objects key by key, a one-element row array into its row,
         anything else replaced; the plan wins on values); a command or field the delta names that the doc lacks
         is an error (the doc and the plan cannot drift), as are differing args.  `source` gains
         "planInTerm": "docs/plans/yellowback-in-term-claims-plan.md", "revisionInTerm": M, "sectionInTerm": "4.1".
  Trees  EXTRACT_SPEC_NODE_DIR (default ycash-dd, the main tree on upgrade/vault); EXTRACT_SPEC_NODE6_DIR,
         EXTRACT_SPEC_WALLET_DIR and EXTRACT_SPEC_LWD_DIR (defaults ycash6, yecwallet-dd, lightwalletd-dd, the
         main trees).  A tree that does not exist or is not on the in-term line is
         skipped and said so.

WORKTREES
  EXTRACT_SPEC_NODE_DIR / EXTRACT_SPEC_NODE6_DIR / EXTRACT_SPEC_WALLET_DIR / EXTRACT_SPEC_LWD_DIR override `ycash-dd` /
  `ycash6` / `yecwallet-dd` / `lightwalletd-dd` (absolute paths), so
  an agent working in wt/<name> can write and check the copies of its own worktree.  Unset = the main trees.
  `--check-upgrade` (`make spec-check-upgrade`) checks the upgrade line's copies (the upgrade spec above and the
  upgrade contract), and `--write-upgrade` (`make spec-upgrade`) writes them: the same variables, defaulting
  to the main trees ycash-dd, ycash6, yecwallet-dd and lightwalletd-dd (relative to the
  workspace); a tree that does not exist, or whose node doc is not yet on the upgrade line, is skipped and
  said so.  The docs/spec copy is the harden check's, not this one's.
"""
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.path.join(ROOT, "docs", "plans", "yellowback-v2-development-plan.md")
PLAN_V3 = os.path.join(ROOT, "docs", "plans", "yellowback-v3-development-plan.md")
PLAN_UPGRADE = os.path.join(ROOT, "docs", "plans", "yellowback-upgrade-plan.md")
SECTION_UPGRADE = "15.10"
UPGRADE_RPCVERSION = 5   # the first rpcversion of the upgrade line (finding (38))
PLAN_INTERM = os.path.join(ROOT, "docs", "plans", "yellowback-in-term-claims-plan.md")
SECTION_INTERM = "4.1"
INTERM_RPCVERSION = 6    # the first rpcversion of the in-term line (in-term plan IT-7)
NODE_DIR = os.environ.get("EXTRACT_SPEC_NODE_DIR") or os.path.join(ROOT, "ycash-dd")
WALLET_DIR = os.environ.get("EXTRACT_SPEC_WALLET_DIR") or os.path.join(ROOT, "yecwallet-dd")
LWD_DIR = os.environ.get("EXTRACT_SPEC_LWD_DIR") or os.path.join(ROOT, "lightwalletd-dd")
# The 6.20.0 node line carries the same overlay; its copies are generated too, so the two lines
# cannot drift apart (they did before 2026-10-04: a stale revisionV3 and hand-edited MINTPOL texts).
NODE6_DIR = os.environ.get("EXTRACT_SPEC_NODE6_DIR") or os.path.join(ROOT, "ycash6")
RPCDOC = os.path.join(NODE_DIR, "doc", "yellowback-rpc.md")
RPCDOC6 = os.path.join(NODE6_DIR, "doc", "yellowback-rpc.md")

SPEC_OUT = [
    os.path.join(ROOT, "docs", "spec", "yellowback-spec.md"),
    os.path.join(NODE_DIR, "doc", "yellowback-spec.md"),
    os.path.join(NODE6_DIR, "doc", "yellowback-spec.md"),
]
JSON_OUT = [
    os.path.join(NODE_DIR, "doc", "yellowback-rpc-contract.json"),
    os.path.join(WALLET_DIR, "docs", "yellowback-rpc-contract.json"),
    os.path.join(LWD_DIR, "testdata", "yellowback", "contract.json"),
]
# ycash6's contract is generated from ycash6's own RPC document (its prose differs in places).
JSON6_OUT = os.path.join(NODE6_DIR, "doc", "yellowback-rpc-contract.json")


def die(msg):
    sys.stderr.write("extract-spec: %s\n" % msg)
    sys.exit(2)


# ── the plan ───────────────────────────────────────────────────────────────────────────────

def read_plan(path=PLAN):
    with open(path, encoding="utf-8") as f:
        return f.read().split("\n")


def read_plan_v3():
    """The v3 delta plan's lines, or None before Phase A0."""
    return read_plan(PLAN_V3) if os.path.exists(PLAN_V3) else None


def revision(lines):
    revs = [int(m.group(1)) for l in lines for m in [re.match(r"### Revision (\d+)\b", l)] if m]
    if not revs:
        die("no '### Revision N' heading in the plan")
    return max(revs)


def section(lines, start_re, end_re):
    """Lines from the first line matching start_re up to (not including) the next matching end_re."""
    start = next((i for i, l in enumerate(lines) if re.match(start_re, l)), None)
    if start is None:
        die("heading %r not found" % start_re)
    end = next((i for i in range(start + 1, len(lines)) if re.match(end_re, lines[i])), None)
    if end is None:
        die("end heading %r not found after %r" % (end_re, start_re))
    return lines[start:end]


def spec_body(lines, lines_v3=None):
    s3 = section(lines, r"## 3\. ", r"## 4\. ")
    s81 = section(lines, r"### 8\.1 ", r"### 8\.2 ")
    body = "\n".join(s3) + "\n\n" + "\n".join(s81) + "\n"
    if lines_v3 is not None:
        # The trust-statement delta is spliced into section 8.1 itself, with its own heading dropped,
        # not appended after the v3 section 3. The fork's `Documents` audit compares
        #   section('^### 8\.1 ', spec)  with  section('^## Trust statement', doc/yellowback.md)
        # and that helper stops at the next line beginning with '#', so anything past the next heading
        # is invisible to it -- and a v3 node's users are told something v2's 8.1 does not say. The
        # delta's body carries no headings, so 8.1 stays one block (workspace 2026-09-20).
        d81 = section(lines_v3, r"### 8\.1 ", r"### 8\.2 ")[1:]
        body = "\n".join(s3) + "\n\n" + "\n".join(s81 + d81) + "\n"
        d3 = section(lines_v3, r"## 3\. ", r"## 4\. ")
        body += (
            "\n## v3 delta - bond-weighted price attestation (yellowback-v3-development-plan.md revision %d, "
            "section 3; its section 8.1 is spliced into 8.1 above; v2 rules where it is silent)\n\n"
            % revision(lines_v3)
        ) + "\n".join(d3) + "\n"
    return body


UPGRADE_SPEC_MARKER = "## Vault upgrade specification"   # the upgrade spec's first body line starts with it
TRUST_UPGRADE_RE = r"\*\*Trust statement \(replaces hardening"   # upgrade plan section 10
GIVEN_UP_RE = r"\*\*What is given up:\*\*"


def revision_upgrade(lines):
    """The upgrade plan's revision: the highest `**Revision N (...)` paragraph opening at its top."""
    revs = [int(m.group(1)) for l in lines for m in [re.match(r"\*\*Revision (\d+)\b", l)] if m]
    if not revs:
        die("no '**Revision N' paragraph in %s" % os.path.relpath(PLAN_UPGRADE, ROOT))
    return max(revs)


def strip_blank_edges(block):
    while block and not block[0].strip():
        block = block[1:]
    while block and not block[-1].strip():
        block = block[:-1]
    return block


def spec_body_upgrade(lines_up):
    """The upgrade line's spec body (see THE UPGRADE SPEC FILE above)."""
    trust = section(lines_up, TRUST_UPGRADE_RE, GIVEN_UP_RE)[1:]
    trust = strip_blank_edges(trust)
    if not trust or any(l.startswith("#") for l in trust):
        die("the upgrade plan's section 10 trust statement is empty or contains a heading")
    start = next((i for i, l in enumerate(lines_up) if re.match(r"## 15\. ", l)), None)
    if start is None:
        die("heading '## 15. ' not found in the upgrade plan")
    end = next((i for i in range(start + 1, len(lines_up)) if re.match(r"## ", lines_up[i])), len(lines_up))
    s15 = strip_blank_edges(lines_up[start:end])
    if not any(l.startswith("### %s " % SECTION_UPGRADE) for l in s15):
        die("the upgrade plan's section 15 has no '### %s' heading" % SECTION_UPGRADE)
    head = [
        "%s - yellowback-upgrade-plan.md revision %d (its section 10 trust statement as 8.1, "
        "then section 15 in full; the hardening and v3 plans where it is silent)" % (UPGRADE_SPEC_MARKER, revision_upgrade(lines_up)),
        "",
        "### 8.1 Trust statement (yellowback-upgrade-plan.md section 10; replaces hardening section 6)",
        "",
    ]
    return "\n".join(head + trust + [""] + s15) + "\n"


def spec_text_upgrade(lines_up):
    body = spec_body_upgrade(lines_up)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return (
        "Source: yellowback-upgrade-plan.md revision %d; sha256: %s\n"
        "Generated by scripts/extract-spec.sh --write-upgrade (make spec-upgrade) from "
        "docs/plans/yellowback-upgrade-plan.md section 10 (trust statement) and section 15"
        " - do not edit this file, edit the plan and rerun; "
        "verify with: sed '1,/^---$/d' FILE | sha256sum\n"
        "---\n" % (revision_upgrade(lines_up), digest)
    ) + body


def spec_text(lines, lines_v3=None):
    body = spec_body(lines, lines_v3)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    src = "yellowback-v2-development-plan.md revision %d" % revision(lines)
    frm = "docs/plans/yellowback-v2-development-plan.md section 3 and section 8.1"
    if lines_v3 is not None:
        src += " + yellowback-v3-development-plan.md revision %d" % revision(lines_v3)
        frm += " and docs/plans/yellowback-v3-development-plan.md sections 3 and 8.1"
    header = (
        "Source: %s; sha256: %s\n"
        "Generated by scripts/extract-spec.sh (make spec) from %s"
        " - do not edit this file, edit the plan and rerun; "
        "verify with: sed '1,/^---$/d' FILE | sha256sum\n"
        "---\n" % (src, digest, frm)
    )
    return header + body


# ── §4.5 shape parser ──────────────────────────────────────────────────────────────────────

OPEN, CLOSE = "{[(", "}])"


def strip_asides(s):
    """Drop parenthesised asides that contain no braces/brackets, and markdown's escaped pipe."""
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\s*\([^(){}\[\]]*\)", "", s)
    return s.replace("\\|", "|")


def split_top(s, sep=","):
    """Split s on sep at nesting depth 0 (braces, brackets, parentheses, double quotes)."""
    out, depth, cur, q = [], 0, [], False
    for ch in s:
        if ch == '"':
            q = not q
        if not q:
            if ch in OPEN:
                depth += 1
            elif ch in CLOSE:
                depth -= 1
        if ch == sep and depth == 0 and not q:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return [p.strip() for p in out if p.strip()]


def matching(s, i):
    """Index of the bracket closing s[i]."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] in OPEN:
            depth += 1
        elif s[j] in CLOSE:
            depth -= 1
            if depth == 0:
                return j
    return len(s) - 1


def parse_value(v):
    v = v.strip()
    if v.startswith("{"):
        return parse_object(v[1:matching(v, 0)])
    if v.startswith("["):
        inner = v[1:matching(v, 0)].strip()
        if inner.startswith("{"):
            return [parse_object(inner[1:matching(inner, 0)])]
        return [x for x in split_top(inner)]
    return v


def parse_object(inner):
    obj = {}
    for item in split_top(inner):
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*(.*)$", item, re.S)
        if not m:
            continue
        key, rest = m.group(1), m.group(2).strip()
        if rest.startswith(":"):
            obj[key] = parse_value(rest[1:])
        else:
            obj[key] = rest
    return obj


def parse_shape(span):
    s = strip_asides(span.strip())
    if s.startswith("[") and s[1:].lstrip().startswith("{"):
        return [parse_object(s[s.index("{") + 1:matching(s, s.index("{"))])]
    if s.startswith("{"):
        return parse_object(s[1:matching(s, 0)])
    return None


CMD_RE = re.compile(r"^(yed_[a-z]+)(?:\s+(.*))?$", re.S)


def rpc_section(lines):
    sec = section(lines, r"### 4\.5 ", r"^##")
    m = re.search(r"rpcversion\s*=\s*(\d+)", sec[0])
    if not m:
        die("the 4.5 heading does not state rpcversion")
    return int(m.group(1)), sec


def commands_from_plan(sec):
    end = next((i for i, l in enumerate(sec) if l.startswith("**Error identifiers")), len(sec))
    text = " ".join(sec[1:end])
    cmds = {}
    order = []
    cur = prev = last_assigned = None
    pos = 0
    for m in re.finditer(r"`([^`]+)`", text):
        between = text[pos:m.start()]
        span = m.group(1)
        cm = CMD_RE.match(span.strip())
        if cm:
            name = cm.group(1)
            if name not in cmds:
                cmds[name] = {"args": (cm.group(2) or "").strip(), "returns": {}, "_set": False, "_since": m.end()}
                order.append(name)
            elif cm.group(2) and not cmds[name]["args"]:
                cmds[name]["args"] = cm.group(2).strip()
            prev, cur = cur, name
            after = text[m.end():m.end() + 40]
            if re.match(r"\s*\(same return shape\)", after) and last_assigned and not cmds[name]["_set"]:
                cmds[name]["returns"] = json.loads(json.dumps(cmds[last_assigned]["returns"]))
                cmds[name]["_set"] = True
            if not cmds[name]["_set"]:
                cmds[name]["_since"] = m.end()
        elif span.lstrip().startswith(("{", "[{")) and cur:
            shape = parse_shape(span)
            if shape is None:
                pass
            elif re.search(r"\+\s*$", between) and prev and cmds[cur]["_set"] and not cmds[prev]["_set"]:
                base = cmds[cur]["returns"]
                base = base[0] if isinstance(base, list) else base
                merged = dict(base)
                merged.update(shape if isinstance(shape, dict) else shape[0])
                since = text[cmds[prev]["_since"]:m.start()]
                cmds[prev]["returns"] = [merged] if re.search(r"\brows?\b", since) else merged
                cmds[prev]["_set"] = True
                last_assigned = prev
            elif not cmds[cur]["_set"]:
                since = text[cmds[cur]["_since"]:m.start()]
                if isinstance(shape, dict) and re.search(r"\brows?\b", since):
                    shape = [shape]
                cmds[cur]["returns"] = shape
                cmds[cur]["_set"] = True
                last_assigned = cur
        pos = m.end()
    for c in cmds.values():
        c.pop("_set", None)
        c.pop("_since", None)
    return cmds


def errors_from_table(lines, stop_at_first_table=True):
    """Identifier rows of the markdown table(s) in lines: `| ids | raised by | when |`."""
    errors = {}
    for l in lines:
        if not l.startswith("|"):
            if errors and stop_at_first_table:
                break
            continue
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0].startswith("Identifier") or set(cells[0]) <= set("-: "):
            continue
        ids = re.findall(r"`([^`]+)`", cells[0])
        # The yed_* names when the cell is only names, separators and (parenthetical notes); otherwise the
        # cell itself, so a mixed cell ("every signing command; on 6.20.0 also `yed_getnewaddress`")
        # keeps its meaning.
        names = re.findall(r"`(yed_[a-z]+)`", cells[1])
        rest = re.sub(r"`yed_[a-z]+`|\([^)]*\)|[,/]|\band\b|\bor\b", "", cells[1]).strip()
        raised = names if names and not rest else [cells[1]]
        when = cells[2].replace("`", "")
        for ident in ids:
            errors[ident] = {"raisedBy": raised, "when": when}
    return errors


def errors_from_plan(sec):
    start = next((i for i, l in enumerate(sec) if l.startswith("**Error identifiers")), None)
    return errors_from_table(sec[start:]) if start is not None else {}


def errors_from_rpcdoc(path):
    """Every table under the rpc doc's `## Error identifiers` heading (up to the next `## `)."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    start = next((i for i, l in enumerate(lines) if l.startswith("## Error identifiers")), None)
    if start is None:
        return {}
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return errors_from_table(lines[start:end], stop_at_first_table=False)


RPCDOC_REL = "ycash-dd/doc/yellowback-rpc.md"   # the recorded path is the canonical one, whatever tree was read
RPCDOC6_REL = "ycash6/doc/yellowback-rpc.md"


def rpcdoc_version(path):
    """The rpcversion the rpc doc's title line states (`# … rpcversion N`), or None."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        first = f.readline()
    m = re.match(r"^# .*\brpcversion (\d+)\s*$", first)
    return int(m.group(1)) if m else None


def commands_from_rpcdoc(path, rel=RPCDOC_REL):
    """Fenced ```json blocks whose nearest preceding non-blank line names a `yed_*` command,
    and the heading `### `yed_<name> <args>`` of each command (args = the text after the name)."""
    out = {}
    args = {}
    if not os.path.exists(path):
        return None, out, args
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    for l in lines:
        m = re.match(r"^### `(yed_[a-z]+)((?: [^`]*)?)`", l)
        if m and m.group(1) not in args:
            args[m.group(1)] = m.group(2).strip()
    i = 0
    while i < len(lines):
        if lines[i].startswith("```json"):
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            m = re.search(r"`(yed_[a-z]+)", lines[j]) if j >= 0 else None
            k = i + 1
            while k < len(lines) and not lines[k].startswith("```"):
                k += 1
            if m:
                try:
                    out[m.group(1)] = json.loads("\n".join(lines[i + 1:k]))
                except ValueError as e:
                    die("%s: bad JSON in the block for %s: %s" % (path, m.group(1), e))
            i = k
        i += 1
    return rel, out, args


def doc_line(rpcdoc_path):
    """`upgrade` or `harden`: EXTRACT_SPEC_LINE when set, else from the rpc doc's title rpcversion."""
    forced = os.environ.get("EXTRACT_SPEC_LINE")
    if forced:
        if forced not in ("harden", "upgrade", "interm"):
            die("EXTRACT_SPEC_LINE must be harden, upgrade or interm, not %r" % forced)
        return forced
    v = rpcdoc_version(rpcdoc_path)
    if v is not None and v >= INTERM_RPCVERSION:
        return "interm"
    return "upgrade" if v is not None and v >= UPGRADE_RPCVERSION else "harden"


def contract_text_upgrade(lines, lines_v3, rpcdoc_path, rpcdoc_rel):
    """The upgrade line: the rpc doc is the whole contract (commands, args, shapes, errors)."""
    ver = rpcdoc_version(rpcdoc_path)
    if ver is None:
        die("%s: an upgrade-line rpc doc must state rpcversion in its title" % rpcdoc_path)
    if not os.path.exists(PLAN_UPGRADE):
        die("the upgrade line needs %s" % os.path.relpath(PLAN_UPGRADE, ROOT))
    if not any(l.startswith("### %s " % SECTION_UPGRADE) for l in read_plan(PLAN_UPGRADE)):
        die("%s has no '### %s' heading" % (os.path.relpath(PLAN_UPGRADE, ROOT), SECTION_UPGRADE))
    rpcdoc, shapes, doc_args = commands_from_rpcdoc(rpcdoc_path, rpcdoc_rel)
    if not shapes:
        die("%s: no yed_* commands" % rpcdoc_path)
    missing = sorted(set(shapes) ^ set(doc_args))
    if missing:
        die("%s: every command needs a ### heading and a ```json block on the upgrade line; unpaired: %s"
            % (rpcdoc_path, ", ".join(missing)))
    doc = {
        "rpcversion": ver,
        "source": {"plan": os.path.relpath(PLAN, ROOT), "revision": revision(lines), "section": "4.5", "rpcdoc": rpcdoc,
                   "planV3": os.path.relpath(PLAN_V3, ROOT) if lines_v3 is not None else None,
                   "revisionV3": revision(lines_v3) if lines_v3 is not None else None,
                   "planUpgrade": os.path.relpath(PLAN_UPGRADE, ROOT), "sectionUpgrade": SECTION_UPGRADE},
        "errors": errors_from_rpcdoc(rpcdoc_path),
    }
    for name in shapes:
        doc[name] = {"args": doc_args[name], "returns": shapes[name]}
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def contract_text(lines, lines_v3=None, rpcdoc_path=RPCDOC, rpcdoc_rel=RPCDOC_REL):
    line = doc_line(rpcdoc_path)
    if line == "interm":
        return contract_text_interm(lines, lines_v3, rpcdoc_path, rpcdoc_rel)
    if line == "upgrade":
        return contract_text_upgrade(lines, lines_v3, rpcdoc_path, rpcdoc_rel)
    ver, sec = rpc_section(lines)
    cmds = commands_from_plan(sec)
    rev_v3 = None
    if lines_v3 is not None:
        ver, _ = rpc_section(lines_v3)  # the v3 heading states the current rpcversion (W14)
        rev_v3 = revision(lines_v3)
    rpcdoc, overrides, doc_args = commands_from_rpcdoc(rpcdoc_path, rpcdoc_rel)
    doc_ver = rpcdoc_version(rpcdoc_path)
    if doc_ver is not None:
        ver = doc_ver
    for name, shape in overrides.items():
        cmds.setdefault(name, {"args": "", "returns": {}})["returns"] = shape
    for name, a in doc_args.items():
        if name in cmds:
            cmds[name]["args"] = a
    errors = errors_from_plan(sec)
    errors.update(errors_from_rpcdoc(rpcdoc_path))
    doc = {
        "rpcversion": ver,
        "source": {"plan": os.path.relpath(PLAN, ROOT), "revision": revision(lines), "section": "4.5", "rpcdoc": rpcdoc,
                   "planV3": os.path.relpath(PLAN_V3, ROOT) if lines_v3 is not None else None, "revisionV3": rev_v3},
        "errors": errors,
    }
    doc.update(cmds)
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# ── the in-term line (upgrade/vault-in-term) ─────────────────────────────────────────────────

INTERM_MARKER_TAIL = "with the in-term claims overlay"
IT8_RE = r"- \*\*IT-8\b"


def read_plan_interm():
    if not os.path.exists(PLAN_INTERM):
        die("the in-term line needs %s" % os.path.relpath(PLAN_INTERM, ROOT))
    return read_plan(PLAN_INTERM)


def revision_interm(lines_it):
    revs = [int(m.group(1)) for l in lines_it for m in [re.match(r"\*\*Revision (\d+)\b", l)] if m]
    if not revs:
        die("no '**Revision N' paragraph in %s" % os.path.relpath(PLAN_INTERM, ROOT))
    return max(revs)


def it8_promise(lines_it):
    """The IT-8 promise: the text between **" and "** in the `- **IT-8` bullet, whitespace collapsed."""
    start = next((i for i, l in enumerate(lines_it) if re.match(IT8_RE, l)), None)
    if start is None:
        die("the in-term plan has no '- **IT-8' rule")
    block = [lines_it[start]]
    for l in lines_it[start + 1:]:
        if not l.strip() or l.startswith("- ") or l.startswith("#"):
            break
        block.append(l)
    m = re.search(r'\*\*"(.+?)"\*\*', " ".join(x.strip() for x in block), re.S)
    if not m:
        die('the in-term plan\'s IT-8 rule carries no **"..."** promise')
    return " ".join(m.group(1).split())


def wrap_bullet(text, width=100):
    """`- ` + text, wrapped at `width` with a two-space continuation; a `%` never starts a line."""
    import textwrap
    guard = "\u0000"
    lines = textwrap.wrap(text.replace(" %", guard + "%"), width=width, initial_indent="- ", subsequent_indent="  ",
                          break_long_words=False, break_on_hyphens=False)
    return [l.replace(guard, " ") for l in lines]


def spec_body_interm(lines_up, lines_it):
    body = spec_body_upgrade(lines_up).split("\n")
    if body and body[-1] == "":
        body = body[:-1]
    if not body[0].startswith(UPGRADE_SPEC_MARKER):
        die("the upgrade spec body does not open with its marker")
    body[0] = "%s - yellowback-upgrade-plan.md revision %d %s (yellowback-in-term-claims-plan.md revision %d: its IT-8 " \
              "promise replaces the section 10 trust statement's collateral paragraph, its sections 3 and 4 follow " \
              "section 15 and amend it where they differ)" % (UPGRADE_SPEC_MARKER, revision_upgrade(lines_up),
                                                                INTERM_MARKER_TAIL, revision_interm(lines_it))
    body[2] = "### 8.1 Trust statement (yellowback-upgrade-plan.md section 10, its collateral paragraph replaced by " \
              "yellowback-in-term-claims-plan.md IT-8; replaces hardening section 6)"
    # the trust statement is body[4:] up to the first `## 15.` line (minus the blank before it)
    end = next((i for i, l in enumerate(body) if l.startswith("## 15. ")), None)
    if end is None:
        die("the upgrade spec body has no section 15")
    starts = [i for i in range(4, end) if body[i].startswith("- Collateral")]
    if len(starts) != 1:
        die("the upgrade plan's trust statement must have exactly one bullet opening '- Collateral' (found %d)" % len(starts))
    a = starts[0]
    b = next((i for i in range(a + 1, end) if body[i].startswith("- ") or not body[i].strip()), end)
    body[a:b] = wrap_bullet(it8_promise(lines_it))
    d = section(lines_it, r"## 3\. ", r"## 5\. ")
    if not any(l.startswith("### %s " % SECTION_INTERM) for l in d):
        die("the in-term plan's section 4 has no '### %s' heading" % SECTION_INTERM)
    body += ["", "## In-term claims delta - yellowback-in-term-claims-plan.md revision %d (sections 3 and 4: parameters, "
             "rules IT-1..IT-9, the RPC contract delta)" % revision_interm(lines_it), ""] + strip_blank_edges(d)
    return "\n".join(body) + "\n"


def spec_text_interm(lines_up, lines_it):
    body = spec_body_interm(lines_up, lines_it)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return (
        "Source: yellowback-upgrade-plan.md revision %d + yellowback-in-term-claims-plan.md revision %d; sha256: %s\n"
        "Generated by scripts/extract-spec.sh --write-in-term (make spec-in-term) from "
        "docs/plans/yellowback-upgrade-plan.md sections 10 and 15 and docs/plans/yellowback-in-term-claims-plan.md"
        " sections 3 and 4 - do not edit this file, edit the plans and rerun; "
        "verify with: sed '1,/^---$/d' FILE | sha256sum\n"
        "---\n" % (revision_upgrade(lines_up), revision_interm(lines_it), digest)
    ) + body


def interm_delta(lines_it):
    """The in-term plan's 4.1: (rpcversion, {cmd: returns-delta}, {cmd: args})."""
    start = next((i for i, l in enumerate(lines_it) if l.startswith("### %s " % SECTION_INTERM)), None)
    if start is None:
        die("the in-term plan has no '### %s' heading" % SECTION_INTERM)
    end = next((i for i in range(start + 1, len(lines_it)) if re.match(r"(## |### )", lines_it[i])), len(lines_it))
    sec = lines_it[start:end]
    m = re.search(r"rpcversion`?\s*=?\s*(\d+)", sec[0])
    if not m:
        die("the in-term plan's %s heading does not state rpcversion" % SECTION_INTERM)
    deltas, args = {}, {}
    i = 1
    while i < len(sec):
        if sec[i].startswith("```json"):
            j = i - 1
            while j >= 0 and not sec[j].strip():
                j -= 1
            name = re.search(r"`(yed_[a-z]+)((?: [^`]*)?)`", sec[j]) if j >= 1 else None
            k = i + 1
            while k < len(sec) and not sec[k].startswith("```"):
                k += 1
            if not name:
                die("in-term plan %s: a json block names no yed_* command" % SECTION_INTERM)
            try:
                deltas[name.group(1)] = json.loads("\n".join(sec[i + 1:k]))
            except ValueError as e:
                die("in-term plan %s: bad JSON for %s: %s" % (SECTION_INTERM, name.group(1), e))
            if sec[j].startswith("#") and name.group(2).strip():   # a heading that states args (a bare name states none)
                args[name.group(1)] = name.group(2).strip()
            i = k
        i += 1
    if not deltas:
        die("the in-term plan's %s has no json blocks" % SECTION_INTERM)
    return int(m.group(1)), deltas, args


def merge_delta(base, delta, path, missing):
    """Deep-merge delta into base (a copy); record every path of delta that base lacks."""
    if isinstance(delta, dict):
        if not isinstance(base, dict):
            missing.append(path + " (not an object in the doc)")
            return delta
        out = dict(base)
        for k, v in delta.items():
            if k not in base:
                missing.append("%s.%s" % (path, k))
                out[k] = v
            else:
                out[k] = merge_delta(base[k], v, "%s.%s" % (path, k), missing)
        return out
    if isinstance(delta, list) and len(delta) == 1 and isinstance(delta[0], dict):
        if not (isinstance(base, list) and len(base) == 1 and isinstance(base[0], dict)):
            missing.append(path + " (not a row list in the doc)")
            return delta
        return [merge_delta(base[0], delta[0], path + "[]", missing)]
    return delta


def contract_text_interm(lines, lines_v3, rpcdoc_path, rpcdoc_rel):
    """The in-term line: the upgrade-line contract of the doc with the in-term plan's 4.1 delta applied."""
    lines_it = read_plan_interm()
    ver, deltas, args = interm_delta(lines_it)
    doc_ver = rpcdoc_version(rpcdoc_path)
    if doc_ver != ver:
        die("%s states rpcversion %s; the in-term plan's %s states %d" % (rpcdoc_path, doc_ver, SECTION_INTERM, ver))
    doc = json.loads(contract_text_upgrade(lines, lines_v3, rpcdoc_path, rpcdoc_rel))
    missing = []
    for name in sorted(deltas):
        if name not in doc:
            missing.append(name)
            continue
        if name in args and args[name] != doc[name]["args"]:
            die("%s: %s args %r, the in-term plan's %s says %r" % (rpcdoc_path, name, doc[name]["args"], SECTION_INTERM, args[name]))
        doc[name]["returns"] = merge_delta(doc[name]["returns"], deltas[name], name, missing)
    if missing:
        die("%s lags the in-term plan's %s; missing: %s" % (rpcdoc_path, SECTION_INTERM, ", ".join(missing)))
    doc["rpcversion"] = ver
    doc["source"].update({"planInTerm": os.path.relpath(PLAN_INTERM, ROOT), "revisionInTerm": revision_interm(lines_it),
                          "sectionInTerm": SECTION_INTERM})
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


INTERM_TREES = {   # env override -> default tree (relative to the workspace): the main trees, which carry
    # upgrade/vault, fast-forwarded to the in-term line on 2026-10-09 (owner); a tree not on it is skipped
    "EXTRACT_SPEC_NODE_DIR": "ycash-dd",
    "EXTRACT_SPEC_NODE6_DIR": "ycash6",
    "EXTRACT_SPEC_WALLET_DIR": "yecwallet-dd",
    "EXTRACT_SPEC_LWD_DIR": "lightwalletd-dd",
}


def check_interm(lines, lines_v3, write=False):
    """`--check-in-term` / `--write-in-term`: the in-term line's copies in the trees named (see THE IN-TERM LINE)."""
    d = {k: os.environ.get(k) or (os.path.join(ROOT, v) if v else None) for k, v in INTERM_TREES.items()}
    node, node6, wallet, lwd = (d[k] for k in INTERM_TREES)
    rel = lambda p: os.path.relpath(p, ROOT)
    spec = spec_text_interm(read_plan(PLAN_UPGRADE), read_plan_interm())
    checks, skipped = [], []

    def node_line(tree):
        doc = os.path.join(tree, "doc", "yellowback-rpc.md")
        if not os.path.isdir(tree):
            skipped.append("%s (no such tree)" % rel(tree))
            return None
        if doc_line(doc) != "interm":
            skipped.append("%s (its rpc doc is rpcversion %s, not the in-term line)" % (rel(tree), rpcdoc_version(doc)))
            return None
        return doc

    doc = node_line(node) if node else None
    if doc is not None:
        text = contract_text(lines, lines_v3, doc, RPCDOC_REL)
        checks += [(os.path.join(node, "doc", "yellowback-spec.md"), spec),
                   (os.path.join(node, "doc", "yellowback-rpc-contract.json"), text)]
        for tree, sub in ((wallet, ("docs", "yellowback-rpc-contract.json")),
                          (lwd, ("testdata", "yellowback", "contract.json"))):
            if tree is None:
                continue
            if os.path.isdir(tree):
                checks.append((os.path.join(tree, *sub), text))
            else:
                skipped.append("%s (no such tree)" % rel(tree))
    if node6:
        doc6 = node_line(node6)
        if doc6 is not None:
            checks += [(os.path.join(node6, "doc", "yellowback-spec.md"), spec),
                       (os.path.join(node6, "doc", "yellowback-rpc-contract.json"),
                        contract_text(lines, lines_v3, doc6, RPCDOC6_REL))]
    if write:
        for s_ in skipped:
            print("spec-in-term: skipped %s" % s_)
        for path, text in checks:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            print("wrote %s" % rel(path))
        if not checks:
            print("spec-in-term: no in-term tree found; nothing written")
        return 0
    stale = []
    for path, text in checks:
        ok = compare(path, text)
        if not ok:
            stale.append(rel(path) + (" (missing)" if ok is None else ""))
    for s_ in skipped:
        print("spec-check-in-term: skipped %s" % s_)
    if stale:
        print("spec-check-in-term: STALE — regenerate with the same EXTRACT_SPEC_*_DIR and `scripts/extract-spec.sh --write-in-term`:\n  "
              + "\n  ".join(stale))
        return 1
    if not checks:
        print("spec-check-in-term: no in-term tree found; nothing checked")
        return 0
    print("spec-check-in-term: %d in-term copies match (%s)" % (len(checks), ", ".join(rel(p) for p, _ in checks)))
    return 0


# ── main ───────────────────────────────────────────────────────────────────────────────────

UPGRADE_TREES = {   # env override -> default tree (relative to the workspace): the main trees, on upgrade/vault since 2026-10-06
    "EXTRACT_SPEC_NODE_DIR": "ycash-dd",
    "EXTRACT_SPEC_NODE6_DIR": "ycash6",
    "EXTRACT_SPEC_WALLET_DIR": "yecwallet-dd",
    "EXTRACT_SPEC_LWD_DIR": "lightwalletd-dd",
}


def compare(path, text):
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return f.read() == text
    except OSError:
        return None


def check_upgrade(lines, lines_v3, write=False):
    """`--check-upgrade`: the upgrade line's copies in the integration worktrees that exist;
    `--write-upgrade` (write=True): write those same copies instead of comparing them."""
    d = {k: os.environ.get(k) or os.path.join(ROOT, v) for k, v in UPGRADE_TREES.items()}
    node, node6, wallet, lwd = (d[k] for k in UPGRADE_TREES)
    rel = lambda p: os.path.relpath(p, ROOT)
    if not os.path.exists(PLAN_UPGRADE):
        die("the upgrade line needs %s" % rel(PLAN_UPGRADE))
    spec = spec_text_upgrade(read_plan(PLAN_UPGRADE))
    checks, skipped = [], []

    def node_line(tree):
        doc = os.path.join(tree, "doc", "yellowback-rpc.md")
        if not os.path.isdir(tree):
            skipped.append("%s (no such tree)" % rel(tree))
            return None
        if doc_line(doc) != "upgrade":
            skipped.append("%s (its rpc doc is rpcversion %s, not yet the upgrade line)" % (rel(tree), rpcdoc_version(doc)))
            return None
        return doc

    doc = node_line(node)
    if doc is not None:
        text = contract_text(lines, lines_v3, doc, RPCDOC_REL)
        checks += [(os.path.join(node, "doc", "yellowback-spec.md"), spec),
                   (os.path.join(node, "doc", "yellowback-rpc-contract.json"), text)]
        for tree, sub in ((wallet, ("docs", "yellowback-rpc-contract.json")),
                          (lwd, ("testdata", "yellowback", "contract.json"))):
            if os.path.isdir(tree):
                checks.append((os.path.join(tree, *sub), text))
            else:
                skipped.append("%s (no such tree)" % rel(tree))
    else:
        skipped.append("%s and %s (their contract is ycash-dd's upgrade-line contract)" % (rel(wallet), rel(lwd)))
    doc6 = node_line(node6)
    if doc6 is not None:
        checks += [(os.path.join(node6, "doc", "yellowback-spec.md"), spec),
                   (os.path.join(node6, "doc", "yellowback-rpc-contract.json"),
                    contract_text(lines, lines_v3, doc6, RPCDOC6_REL))]
    if write:
        for s in skipped:
            print("spec-upgrade: skipped %s" % s)
        for path, text in checks:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            print("wrote %s" % rel(path))
        if not checks:
            print("spec-upgrade: no upgrade-line tree found; nothing written")
        return 0
    stale = []
    for path, text in checks:
        ok = compare(path, text)
        if not ok:
            stale.append(rel(path) + (" (missing)" if ok is None else ""))
    for s in skipped:
        print("spec-check-upgrade: skipped %s" % s)
    if stale:
        print("spec-check-upgrade: STALE — regenerate with the same EXTRACT_SPEC_*_DIR and `scripts/extract-spec.sh --write-upgrade`:\n  "
              + "\n  ".join(stale))
        return 1
    if not checks:
        print("spec-check-upgrade: no upgrade-line tree found; nothing checked")
        return 0
    print("spec-check-upgrade: %d upgrade-line copies match (%s)" % (len(checks), ", ".join(rel(p) for p, _ in checks)))
    return 0


def main(argv):
    mode = argv[1] if len(argv) > 1 else "--write"
    if mode not in ("--write", "--check", "--check-workspace", "--check-upgrade", "--write-upgrade", "--check-in-term", "--write-in-term"):
        die("usage: extract_spec.py [--write|--check|--check-workspace|--check-upgrade|--write-upgrade|--check-in-term|--write-in-term]")
    lines = read_plan()
    lines_v3 = read_plan_v3()
    if mode in ("--check-upgrade", "--write-upgrade"):
        return check_upgrade(lines, lines_v3, write=mode == "--write-upgrade")
    if mode in ("--check-in-term", "--write-in-term"):
        return check_interm(lines, lines_v3, write=mode == "--write-in-term")
    # Each node tree gets the spec of the line it is on (its rpc doc's rpcversion: >= 5 = the vault upgrade),
    # as its contract copies already do; docs/spec in this repo is always the harden line's.
    spec_h = spec_text(lines, lines_v3)
    spec_u = None

    def spec_for(path):
        nonlocal spec_u
        tree = os.path.dirname(os.path.dirname(path))
        if os.path.relpath(path, ROOT).startswith("docs" + os.sep):
            return spec_h
        line = doc_line(os.path.join(tree, "doc", "yellowback-rpc.md"))
        if line == "interm":
            return spec_text_interm(read_plan(PLAN_UPGRADE), read_plan_interm())
        if line != "upgrade":
            return spec_h
        if spec_u is None:
            spec_u = spec_text_upgrade(read_plan(PLAN_UPGRADE))
        return spec_u

    outputs = [(p, spec_for(p)) for p in SPEC_OUT] + [(p, contract_text(lines, lines_v3)) for p in JSON_OUT]
    outputs.append((JSON6_OUT, contract_text(lines, lines_v3, RPCDOC6, RPCDOC6_REL)))
    workspace_only = mode == "--check-workspace"
    if workspace_only:
        # The workspace CI has no nested clones: compare only the copies that live in this repo.
        outputs = [(p, t) for p, t in outputs if os.path.relpath(p, ROOT).startswith("docs" + os.sep)]
        mode = "--check"
    stale = []
    for path, text in outputs:
        rel = os.path.relpath(path, ROOT)
        if mode == "--write":
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            print("wrote %s" % rel)
        else:
            try:
                with open(path, encoding="utf-8", newline="") as f:
                    current = f.read()
            except OSError:
                current = None
            if current != text:
                stale.append(rel + (" (missing)" if current is None else ""))
    if mode == "--check":
        if stale:
            print("spec-check: STALE — run `make spec`:\n  " + "\n  ".join(stale))
            return 1
        rev = "revision %d%s" % (revision(lines), "" if lines_v3 is None else "; v3 revision %d" % revision(lines_v3))
        if workspace_only:
            print("spec-check: docs/spec copy matches the plan (%s); the fork copies were not checked" % rev)
        else:
            print("spec-check: docs/spec, %s/doc, %s/doc, %s/docs and %s/testdata copies match the plan (%s)" % (
                os.path.relpath(NODE_DIR, ROOT), os.path.relpath(NODE6_DIR, ROOT), os.path.relpath(WALLET_DIR, ROOT),
                os.path.relpath(LWD_DIR, ROOT), rev))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

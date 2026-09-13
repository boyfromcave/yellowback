#!/usr/bin/env python3
r"""Publish the normative parts of the Yellowback v2 plan through a tool, not a copy (plan Phase 0; N29, P4, P7).

Run through scripts/extract-spec.sh (`make spec` / `make spec-check`), always with the workspace venv.

READS
  docs/plans/yellowback-v2-development-plan.md       the plan (the wording of record)
  docs/plans/yellowback-v3-development-plan.md       optional: the v3 delta plan (Phase A0+); its section 3 is
                                                     appended to the spec and its 4.5 heading supplies rpcversion
  ycash-dd/doc/yellowback-rpc.md                     optional: the fork's RPC contract document (Phase 3+); from
                                                     Phase A0 its "Error identifiers" tables are the error table

WRITES (`--write`) or COMPARES (`--check`, exit 1 when any copy is missing or stale)
  docs/spec/yellowback-spec.md                       the spec: header + body (below)
  ycash-dd/doc/yellowback-spec.md                    byte-identical copy the fork's CI can see (P4)
  ycash-dd/doc/yellowback-rpc-contract.json          the RPC contract (P7)
  yecwallet-dd/docs/yellowback-rpc-contract.json     byte-identical copy for the wallet fork

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
  N is the highest `### Revision N` heading of the plan's §0.  The sha256 is over exactly the body
  bytes, so the fork-local check   sed '1,/^---$/d' FILE | sha256sum   reproduces it (§6.0 item 6).

THE CONTRACT JSON  (sorted keys, 2-space indent, trailing newline; identical in both forks)
  {
    "rpcversion": <int>,            from the §4.5 heading "(`rpcversion = N`)" — of the v3 plan when it exists
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

WORKTREES
  EXTRACT_SPEC_NODE_DIR / EXTRACT_SPEC_WALLET_DIR override `ycash-dd` / `yecwallet-dd` (absolute paths), so
  an agent working in wt/<name> can write and check the copies of its own worktree.  Unset = the main trees.
"""
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.path.join(ROOT, "docs", "plans", "yellowback-v2-development-plan.md")
PLAN_V3 = os.path.join(ROOT, "docs", "plans", "yellowback-v3-development-plan.md")
NODE_DIR = os.environ.get("EXTRACT_SPEC_NODE_DIR") or os.path.join(ROOT, "ycash-dd")
WALLET_DIR = os.environ.get("EXTRACT_SPEC_WALLET_DIR") or os.path.join(ROOT, "yecwallet-dd")
RPCDOC = os.path.join(NODE_DIR, "doc", "yellowback-rpc.md")

SPEC_OUT = [
    os.path.join(ROOT, "docs", "spec", "yellowback-spec.md"),
    os.path.join(NODE_DIR, "doc", "yellowback-spec.md"),
]
JSON_OUT = [
    os.path.join(NODE_DIR, "doc", "yellowback-rpc-contract.json"),
    os.path.join(WALLET_DIR, "docs", "yellowback-rpc-contract.json"),
]


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
        d3 = section(lines_v3, r"## 3\. ", r"## 4\. ")
        body += (
            "\n## v3 delta - bond-weighted price attestation (yellowback-v3-development-plan.md revision %d, "
            "section 3; v2 above rules where it is silent)\n\n" % revision(lines_v3)
        ) + "\n".join(d3) + "\n"
    return body


def spec_text(lines, lines_v3=None):
    body = spec_body(lines, lines_v3)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    src = "yellowback-v2-development-plan.md revision %d" % revision(lines)
    frm = "docs/plans/yellowback-v2-development-plan.md section 3 and section 8.1"
    if lines_v3 is not None:
        src += " + yellowback-v3-development-plan.md revision %d" % revision(lines_v3)
        frm += " and docs/plans/yellowback-v3-development-plan.md section 3"
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
        raised = re.findall(r"`(yed_[a-z]+)`", cells[1]) or [cells[1]]
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


def commands_from_rpcdoc(path):
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
    return RPCDOC_REL, out, args


def contract_text(lines, lines_v3=None):
    ver, sec = rpc_section(lines)
    cmds = commands_from_plan(sec)
    rev_v3 = None
    if lines_v3 is not None:
        ver, _ = rpc_section(lines_v3)  # the v3 heading states the current rpcversion (W14)
        rev_v3 = revision(lines_v3)
    rpcdoc, overrides, doc_args = commands_from_rpcdoc(RPCDOC)
    for name, shape in overrides.items():
        cmds.setdefault(name, {"args": "", "returns": {}})["returns"] = shape
    for name, a in doc_args.items():
        if name in cmds:
            cmds[name]["args"] = a
    errors = errors_from_plan(sec)
    errors.update(errors_from_rpcdoc(RPCDOC))
    doc = {
        "rpcversion": ver,
        "source": {"plan": os.path.relpath(PLAN, ROOT), "revision": revision(lines), "section": "4.5", "rpcdoc": rpcdoc,
                   "planV3": os.path.relpath(PLAN_V3, ROOT) if lines_v3 is not None else None, "revisionV3": rev_v3},
        "errors": errors,
    }
    doc.update(cmds)
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# ── main ───────────────────────────────────────────────────────────────────────────────────

def main(argv):
    mode = argv[1] if len(argv) > 1 else "--write"
    if mode not in ("--write", "--check"):
        die("usage: extract_spec.py [--write|--check]")
    lines = read_plan()
    lines_v3 = read_plan_v3()
    outputs = [(p, spec_text(lines, lines_v3)) for p in SPEC_OUT] + [(p, contract_text(lines, lines_v3)) for p in JSON_OUT]
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
        print("spec-check: docs/spec, %s/doc and %s/docs copies match the plan (revision %d%s)" % (
            os.path.relpath(NODE_DIR, ROOT), os.path.relpath(WALLET_DIR, ROOT), revision(lines),
            "" if lines_v3 is None else "; v3 revision %d" % revision(lines_v3)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

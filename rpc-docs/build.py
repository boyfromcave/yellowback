#!/usr/bin/env python3
"""Build the RPC documentation site (rpc.ycash.team) from the committed snapshots.

    rpc-docs/build.py [--out rpc-docs/_site]

Every directory under rpc-docs/versions/ is one release, written by capture.py and never edited.
Each becomes /<version>/ with one page per method, a contracts page and a "changes since the
previous version" page. The channels are copies of a version's pages: /beta/ is the newest release
of any stage, /rc/ the newest release candidate or general release, /stable/ the newest general
release, and / serves stable (or, before the first general release, the newest release).
site.json "channels" pins a channel to a version instead.
"""
import argparse
import difflib
import html
import json
import os
import re
import shutil
import string

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)(?:-(beta|rc)(\d+))?$")
STAGE_RANK = {"beta": 0, "rc": 1, "stable": 2}
CHANNELS = ("beta", "rc", "stable")
STAGE_LABEL = {"beta": "Beta", "rc": "Release candidate", "stable": "General release"}


def esc(s):
    return html.escape(str(s), quote=True)


# --- versions ---------------------------------------------------------------------------------

def parse_version(v):
    m = VERSION_RE.match(v)
    if not m:
        raise SystemExit("build: %r is not a release version" % v)
    stage = m.group(4) or "stable"
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), STAGE_RANK[stage], int(m.group(5) or 0)), stage


def stage_of(v):
    return parse_version(v)[1]


def sort_versions(versions):
    return sorted(versions, key=lambda v: parse_version(v)[0])


def resolve_channels(versions, pins=None):
    """versions (any order) -> {channel: version}; a channel with no release is absent."""
    ordered = sort_versions(versions)
    out = {}
    for channel in CHANNELS:
        floor = STAGE_RANK[channel]
        eligible = [v for v in ordered if STAGE_RANK[stage_of(v)] >= floor]
        if eligible:
            out[channel] = eligible[-1]
    for channel, v in (pins or {}).items():
        if channel not in CHANNELS:
            raise SystemExit("build: site.json pins unknown channel %r" % channel)
        if v not in versions:
            raise SystemExit("build: site.json pins %s to %s, which has no snapshot" % (channel, v))
        out[channel] = v
    return out


def default_channel(channels):
    return "stable" if "stable" in channels else ("beta" if "beta" in channels else None)


# --- snapshots --------------------------------------------------------------------------------

def parse_help_index(text):
    groups, current = [], None
    for line in text.splitlines():
        if line.startswith("== ") and line.endswith(" =="):
            current = (line[3:-3], [])
            groups.append(current)
        elif line.strip() and current is not None:
            current[1].append(line.split()[0])
    return groups


def summary_of(text):
    """The first description line of a method's help (the line after its signature)."""
    lines = text.splitlines()
    for line in lines[1:]:
        s = line.strip()
        if s:
            if s.lower().startswith(("arguments", "result", "examples")):
                return ""
            return s
    return ""


class Snapshot:
    def __init__(self, version, path):
        self.version = version
        self.stage = stage_of(version)
        with open(os.path.join(path, "source.json")) as f:
            self.source = json.load(f)
        with open(os.path.join(path, "help", "_index.txt")) as f:
            self.index_text = f.read()
        self.groups = parse_help_index(self.index_text)
        self.help = {}
        self.category = {}
        for cat, methods in self.groups:
            for name in methods:
                with open(os.path.join(path, "help", name + ".txt")) as f:
                    self.help[name] = f.read().rstrip("\n")
                self.category[name] = cat
        self.contracts = {}
        cdir = os.path.join(path, "contracts")
        if os.path.isdir(cdir):
            for fn in sorted(os.listdir(cdir)):
                if fn.endswith(".json"):
                    with open(os.path.join(cdir, fn)) as f:
                        self.contracts[fn] = json.load(f)

    @property
    def methods(self):
        return [m for _, ms in self.groups for m in ms]

    def contract_entry(self, name):
        """(contract file, kind, entry) for a method the contracts describe, else None."""
        for fn, c in self.contracts.items():
            if isinstance(c.get("methods"), dict) and name in c["methods"]:
                return fn, "typed", c["methods"][name]
            if name in c and isinstance(c[name], dict) and ("args" in c[name] or "returns" in c[name]):
                return fn, "example", c[name]
        return None

    def errors_for(self, name):
        rows = []
        for fn, c in self.contracts.items():
            errs = c.get("errors")
            if isinstance(errs, list):
                for e in errs:
                    if name in e.get("raisedBy", []):
                        rows.append((str(e.get("code", "")), e.get("message", ""), e.get("provokedBy", "")))
            elif isinstance(errs, dict):
                for reason, e in errs.items():
                    if name in e.get("raisedBy", []):
                        rows.append(("", reason, e.get("when", "")))
        return rows


def load_snapshots(versions_dir):
    snaps = {}
    for v in os.listdir(versions_dir):
        path = os.path.join(versions_dir, v)
        if os.path.isdir(path):
            parse_version(v)
            snaps[v] = Snapshot(v, path)
    if not snaps:
        raise SystemExit("build: no snapshots under %s" % versions_dir)
    return snaps


# --- contract rendering -----------------------------------------------------------------------

def inline_md(s):
    """Escape, then render `code` and **bold** spans, the only Markdown the contracts use."""
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)


def render_type(t, contract_href, depth=0):
    """A contract type expression as compact, linked HTML (TypeScript-like)."""
    pad = "  " * depth
    if "ref" in t:
        return '<a href="%s#shape-%s">%s</a>' % (contract_href, esc(t["ref"]), esc(t["ref"]))
    if "const" in t:
        return '<span class="t-const">%s</span>' % esc(json.dumps(t["const"]))
    if "oneOf" in t:
        return " | ".join(render_type(x, contract_href, depth) for x in t["oneOf"])
    kind = t.get("type")
    if kind == "object":
        optional = set(t.get("optional", []))
        fields = t.get("fields", {})
        if not fields:
            return "{}"
        rows = ["%s  %s%s: %s" % (pad, esc(k), "?" if k in optional else "", render_type(v, contract_href, depth + 1))
                for k, v in fields.items()]
        return "{\n" + ",\n".join(rows) + "\n" + pad + "}"
    if kind == "array":
        inner = render_type(t.get("items", {}), contract_href, depth)
        return ("(%s)[]" if " | " in inner else "%s[]") % inner
    return '<span class="t-prim">%s</span>' % esc(kind or "any")


def render_contract_block(snap, name, contract_href):
    hit = snap.contract_entry(name)
    errors = snap.errors_for(name)
    if not hit and not errors:
        return ""
    out = ['<section class="contract"><h2>Contract</h2>']
    if hit:
        fn, kind, entry = hit
        out.append('<p class="muted">From <a href="%s">%s</a> at <code>%s</code>.</p>'
                   % (contract_href, esc(fn), esc(snap.source.get("tag", snap.version))))
        if kind == "typed":
            out.append('<p><code class="sig">%s</code> &middot; %s</p>'
                       % (esc(entry.get("signature", name)),
                          "needs the wallet" if entry.get("wallet") else "no wallet needed"))
            params = entry.get("params", [])
            if params:
                out.append('<table><thead><tr><th>#</th><th>Parameter</th><th>Type</th><th></th></tr></thead><tbody>')
                for i, p in enumerate(params, 1):
                    out.append("<tr><td>%d</td><td><code>%s</code></td><td><pre class=\"type\">%s</pre></td><td>%s</td></tr>"
                               % (i, esc(p["name"]), render_type(p.get("type", {}), contract_href),
                                  "required" if p.get("required") else "optional"))
                out.append("</tbody></table>")
            else:
                out.append("<p>No parameters.</p>")
            out.append('<h3>Result</h3><pre class="type">%s</pre>' % render_type(entry.get("result", {}), contract_href))
        else:
            args = entry.get("args", "")
            out.append("<p><code class=\"sig\">%s %s</code></p>" % (esc(name), esc(args)) if args else "<p>No arguments.</p>")
            if "returns" in entry:
                out.append('<h3>Example result</h3><pre class="json">%s</pre>' % esc(json.dumps(entry["returns"], indent=2)))
    if errors:
        out.append('<h3>Errors</h3><table><thead><tr><th>Code</th><th>Reason</th><th>When</th></tr></thead><tbody>')
        for code, reason, when in errors:
            out.append("<tr><td>%s</td><td><code>%s</code></td><td>%s</td></tr>" % (esc(code), esc(reason), inline_md(when)))
        out.append("</tbody></table>")
    out.append("</section>")
    return "\n".join(out)


def render_contracts_page(snap):
    out = ['<h1>RPC contracts</h1><p class="lede">The machine-readable contracts the node release ships '
           '(<code>doc/*-rpc-contract.json</code> at <code>%s</code>). Clients test against these; the '
           'method pages show the entry for each method.</p>' % esc(snap.source.get("tag", snap.version))]
    if not snap.contracts:
        out.append("<p>This release ships no RPC contracts.</p>")
    for fn, c in snap.contracts.items():
        out.append('<section class="contract"><h2 id="%s">%s</h2>' % (esc(fn), esc(fn)))
        out.append('<p><a class="button" href="contracts/%s" download>Download JSON</a></p>' % esc(fn))
        meta = {k: c[k] for k in ("contract", "branchid", "rpcversion") if k in c}
        if meta:
            out.append("<p>%s</p>" % " &middot; ".join("%s <code>%s</code>" % (esc(k), esc(v)) for k, v in meta.items()))
        if isinstance(c.get("types"), dict):
            out.append("<h3>Types</h3><table><thead><tr><th>Type</th><th>JSON</th><th>Meaning</th></tr></thead><tbody>")
            for k, v in c["types"].items():
                out.append("<tr><td><code>%s</code></td><td>%s</td><td>%s</td></tr>"
                           % (esc(k), esc(v.get("json", "")), inline_md(v.get("meaning", ""))))
            out.append("</tbody></table>")
        if isinstance(c.get("shapes"), dict):
            out.append("<h3>Shapes</h3>")
            for k, v in c["shapes"].items():
                out.append('<h4 id="shape-%s"><code>%s</code></h4><pre class="type">%s</pre>' % (esc(k), esc(k), render_type(v, "")))
        errs = c.get("errors")
        if errs:
            out.append("<h3>Errors</h3><table><thead><tr><th>Code</th><th>Reason</th><th>Raised by</th><th>When</th></tr></thead><tbody>")
            items = ([(str(e.get("code", "")), e.get("message", ""), e.get("raisedBy", []), e.get("provokedBy", "")) for e in errs]
                     if isinstance(errs, list) else
                     [("", r, e.get("raisedBy", []), e.get("when", "")) for r, e in errs.items()])
            for code, reason, by, when in items:
                links = ", ".join('<a href="%s.html">%s</a>' % (esc(b), esc(b)) if b in snap.help else esc(b) for b in by)
                out.append("<tr><td>%s</td><td><code>%s</code></td><td>%s</td><td>%s</td></tr>" % (esc(code), esc(reason), links, inline_md(when)))
            out.append("</tbody></table>")
        out.append("</section>")
    return "\n".join(out)


# --- changes ----------------------------------------------------------------------------------

def contract_view(snap, name):
    hit = snap.contract_entry(name)
    return json.dumps(hit[2], sort_keys=True) if hit else None


def compute_changes(prev, cur):
    if prev is None:
        return None
    added = [m for m in cur.methods if m not in prev.help]
    removed = [m for m in prev.methods if m not in cur.help]
    changed = []
    for m in cur.methods:
        if m in prev.help:
            text = prev.help[m] != cur.help[m]
            contract = contract_view(prev, m) != contract_view(cur, m)
            moved = prev.category[m] != cur.category[m]
            if text or contract or moved:
                changed.append((m, text, contract, moved))
    return {"added": added, "removed": removed, "changed": changed}


def render_changes_page(prev, cur, changes):
    out = ["<h1>Changes in %s</h1>" % esc(cur.version)]
    if changes is None:
        out.append('<p class="lede">The first published version: there is nothing to compare it with.</p>')
        return "\n".join(out)
    out.append('<p class="lede">Compared with <a href="../%s/index.html">%s</a>: %d added, %d removed, %d changed.</p>'
               % (esc(prev.version), esc(prev.version), len(changes["added"]), len(changes["removed"]), len(changes["changed"])))
    if not any(changes.values()):
        out.append("<p>No RPC changed: every method's help text and contract entry are identical.</p>")
    if changes["added"]:
        out.append("<h2>Added</h2><ul class=\"methods\">%s</ul>" % "".join(
            '<li><a href="%s.html">%s</a> <span class="muted">%s</span></li>' % (esc(m), esc(m), esc(cur.category[m])) for m in changes["added"]))
    if changes["removed"]:
        out.append("<h2>Removed</h2><ul class=\"methods\">%s</ul>" % "".join(
            '<li><a href="../%s/%s.html">%s</a></li>' % (esc(prev.version), esc(m), esc(m)) for m in changes["removed"]))
    if changes["changed"]:
        out.append("<h2>Changed</h2>")
        for m, text, contract, moved in changes["changed"]:
            what = [w for w, on in (("help text", text), ("contract", contract), ("category", moved)) if on]
            out.append('<h3><a href="%s.html">%s</a> <span class="muted">%s</span></h3>' % (esc(m), esc(m), esc(", ".join(what))))
            if moved:
                out.append("<p>Moved from %s to %s.</p>" % (esc(prev.category[m]), esc(cur.category[m])))
            if text:
                diff = difflib.unified_diff(prev.help[m].splitlines(), cur.help[m].splitlines(),
                                            prev.version, cur.version, lineterm="", n=2)
                out.append('<pre class="diff">%s</pre>' % "\n".join(diff_line(l) for l in diff))
            if contract:
                diff = difflib.unified_diff(
                    json.dumps(json.loads(contract_view(prev, m) or "null"), indent=2).splitlines(),
                    json.dumps(json.loads(contract_view(cur, m) or "null"), indent=2).splitlines(),
                    prev.version + " contract", cur.version + " contract", lineterm="", n=2)
                out.append('<pre class="diff">%s</pre>' % "\n".join(diff_line(l) for l in diff))
    return "\n".join(out)


def diff_line(line):
    cls = {"+": "add", "-": "del", "@": "hunk"}.get(line[:1], "")
    if line.startswith(("+++", "---")):
        cls = "hunk"
    return '<span class="%s">%s</span>' % (cls, esc(line)) if cls else esc(line)


SUPPORT_LABEL = {"supported": "Supported", "deprecated": "Deprecated"}


def support_badge(kind):
    label = SUPPORT_LABEL.get(kind, kind)
    return '<span class="support support-%s">%s</span>' % (esc(kind), esc(label))


def cli_block(steps):
    if not steps:
        return ""
    return '<pre class="cmd">%s</pre>' % "\n".join(esc(s.get("cli", "")) for s in steps)


def block_mentions(block, name):
    if not block:
        return False
    if block.get("method") == name:
        return True
    return any(s.get("method") == name for s in block.get("steps", []))


def in_range(version, entry):
    """True when version lies in entry's optional "since" / "until" range (both ends included)."""
    key = parse_version(version)[0]
    if entry.get("since") and key < parse_version(entry["since"])[0]:
        return False
    if entry.get("until") and key > parse_version(entry["until"])[0]:
        return False
    return True


def text_for(value, snap):
    """A curated text as snap's release reads it. A string holds for every release. A list holds variants,
    {"text", "since"?, "until"?, "helpSays"?, "pending"?}; the ones whose range holds snap.version are joined."""
    if value is None or isinstance(value, str):
        return value or ""
    return " ".join(v["text"] for v in value if in_range(snap.version, v))


def steps_for(steps, snap):
    return [s for s in (steps or []) if in_range(snap.version, s)]


def check_help_quotes(config, snap):
    """A note that says what the node's help says must name the words ("helpSays"), and the help of the call it
    is under must contain them in every release the note is shown for: a reworded help fails the build."""
    for group, kind in address_entries(config):
        use = kind.get("use") or {}
        note = use.get("note")
        if not isinstance(note, list):
            continue
        for v in note:
            if v.get("helpSays") and in_range(snap.version, v) and v["helpSays"] not in snap.help.get(use.get("method"), ""):
                raise SystemExit("build: site.json note of %s quotes %r, which the %s help of %s does not contain"
                                 % (kind["id"], v["helpSays"], snap.version, use.get("method")))


def address_entries(config):
    """(group or None, type) for every receive type and every non-receive key."""
    out = []
    for group in config.get("receive", []):
        for kind in group.get("types", []):
            out.append((group, kind))
    for kind in config.get("otherKeys", []):
        out.append((None, kind))
    return out


def entries_mentioning(config, name):
    return [(g, t) for g, t in address_entries(config) if block_mentions(t.get("use"), name) or block_mentions(t.get("deprecated"), name)]


def render_type_block(snap, group, kind):
    coin = group["coin"] if group else ""
    heading = "%s · %s" % (coin, kind["name"]) if coin else kind["name"]
    anchor = kind["id"]
    use = kind.get("use") or {}
    dep = kind.get("deprecated") or {}
    out = ['<section class="addr-type" id="%s">' % esc(anchor)]
    out.append("<h3>%s %s</h3>" % (esc(heading), support_badge(kind.get("support", "supported"))))
    out.append("<p>%s</p>" % esc(text_for(kind.get("summary"), snap)))
    if use:
        returns = use.get("method", "")
        link = '<a href="%s.html"><code>%s</code></a>' % (esc(returns), esc(returns)) if returns in snap.help else "<code>%s</code>" % esc(returns)
        out.append("<p>Call %s.</p>" % link)
        out.append(cli_block(steps_for(use.get("steps"), snap)))
        note = text_for(use.get("note"), snap)
        if note:
            out.append('<p class="note">%s</p>' % esc(note))
    if dep:
        out.append('<div class="deprecated-call"><h4>Deprecated call</h4>')
        out.append("<p>%s</p>" % esc(dep.get("why", "")))
        out.append(cli_block(dep.get("steps")))
        out.append("</div>")
    out.append("</section>")
    return "\n".join(out)


def render_addresses_page(config, snap):
    out = ['<h1>Addresses</h1>',
           '<p class="lede">Create an address that can receive YEC, or one that can hold YED. '
           'Each type is listed once. The call under the type is the one to use on Ycash. Where this '
           'release\'s help calls it deprecated, the note says why it is still the call to use.</p>',
           '<p>If the wallet is encrypted, run <code>walletpassphrase</code> first.</p>']
    if moving_shown(config, snap):
        out.append('<p><a href="moving.html">%s</a> says which call moves YEC from one address type to another, '
                   'how to fund a vault from each, and how to read balances by type.</p>'
                   % esc(config["moving"].get("title", "Moving YEC")))
    for group in config.get("receive", []):
        out.append('<section class="addr-coin" id="%s"><h2>Receive %s</h2><p>%s</p>'
                   % (esc(group["id"]), esc(group["coin"]), esc(group.get("lead", ""))))
        for kind in group.get("types", []):
            out.append(render_type_block(snap, group, kind))
        out.append("</section>")
    others = config.get("otherKeys", [])
    if others:
        out.append('<section class="addr-coin" id="other-keys"><h2>Other keys</h2>'
                   '<p>These calls create a key. The result is not an address for receiving YEC or YED.</p>')
        for kind in others:
            out.append(render_type_block(snap, None, kind))
        out.append("</section>")
    gone = config.get("unavailable") or {}
    methods = [m for m in gone.get("methods", []) if m in snap.help]
    if methods:
        out.append('<section class="addr-coin" id="unavailable"><h2>%s</h2><p>%s</p><p>%s</p></section>'
                   % (esc(gone.get("title", "Not available")),
                      ", ".join('<a href="%s.html"><code>%s</code></a>' % (esc(m), esc(m)) for m in methods),
                      esc(gone.get("reason", ""))))
    return "\n".join(out)


def moving_shown(config, snap):
    """The "moving YEC" page is shown from the release named by its "since" (and never without one)."""
    moving = config.get("moving")
    return bool(moving and moving.get("since") and in_range(snap.version, moving))


def pending_markers(config):
    """Every "pending" marker in the curated config: a statement that depends on work not yet merged. The build
    prints them so a maintainer flips each one when that work lands."""
    found = []

    def walk(v, where):
        if isinstance(v, dict):
            if v.get("pending"):
                found.append((where, v["pending"]))
            for k, x in v.items():
                walk(x, where + "." + k)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, "%s[%d]" % (where, i))

    walk(config, "site")
    return found


def render_moving_page(config, snap):
    m = config["moving"]
    out = ['<h1>%s</h1>' % esc(m.get("title", "Moving YEC")), '<p class="lede">%s</p>' % inline_md(text_for(m.get("lede"), snap))]
    for sec in m.get("sections", []):
        if not in_range(snap.version, sec):
            continue
        out.append('<section class="addr-coin" id="%s"><h2>%s</h2>' % (esc(sec["id"]), esc(sec["title"])))
        if sec.get("pending") and sec.get("pendingText"):
            out.append('<p class="note pending"><strong>Not in every release yet.</strong> %s</p>' % inline_md(sec["pendingText"]))
        for p in sec.get("paragraphs", []):
            text = text_for(p, snap) if isinstance(p, list) else p
            if text:
                out.append("<p>%s</p>" % inline_md(text))
        for t in sec.get("tables", []):
            if t.get("caption"):
                out.append("<h3>%s</h3>" % inline_md(t["caption"]))
            out.append('<div class="table-scroll"><table><thead><tr>%s</tr></thead><tbody>'
                       % "".join("<th>%s</th>" % inline_md(c) for c in t["columns"]))
            for row in t["rows"]:
                if len(row) != len(t["columns"]):
                    raise SystemExit("build: site.json moving table %r has a row of %d cells for %d columns"
                                     % (t.get("caption", sec["id"]), len(row), len(t["columns"])))
                out.append("<tr>%s</tr>" % "".join("<td>%s</td>" % inline_md(c) for c in row))
            out.append("</tbody></table></div>")
            for n in t.get("notes", []):
                out.append('<p class="note">%s</p>' % inline_md(n))
        out.append("</section>")
    return "\n".join(out)


def render_unavailable_callout(config, name):
    gone = config.get("unavailable") or {}
    if name not in gone.get("methods", []):
        return ""
    return ('<aside class="addr-callout unavailable"><h2>%s <span class="support support-unavailable">Refused</span></h2>'
            '<p>%s The help text below is inherited from Zcash.</p>'
            '<p><a href="addresses.html">Addresses</a> lists the calls that create an address.</p></aside>'
            % (esc(gone.get("title", "Not available")), esc(gone.get("reason", ""))))


def render_address_callout(config, snap, name):
    hits = entries_mentioning(config, name)
    if not hits:
        return ""
    out = ['<aside class="addr-callout"><p class="callout-kicker"><a href="addresses.html">Addresses</a></p>']
    for group, kind in hits:
        coin = group["coin"] if group else "Other keys"
        use = kind.get("use") or {}
        dep = kind.get("deprecated") or {}
        if use.get("method") == name:
            role = "returns this address"
        elif dep.get("method") == name:
            role = "is a deprecated way to create this address"
        else:
            role = "is one step in creating this address"
        marks = support_badge(kind.get("support", "supported"))
        if dep.get("method") == name and use.get("method") != name:
            marks += ' <span class="support support-deprecated">Deprecated call</span>'
        out.append('<h2 id="addr-%s">%s · %s %s</h2>' % (esc(kind["id"]), esc(coin), esc(kind["name"]), marks))
        out.append("<p><code>%s</code> %s. %s <a href=\"addresses.html#%s\">Full steps</a>.</p>"
                   % (esc(name), role, esc(text_for(kind.get("summary"), snap)), esc(kind["id"])))
        note = text_for(use.get("note"), snap)
        if use.get("method") == name and note:
            out.append('<p class="note">%s</p>' % esc(note))
        if dep.get("method") == name and use.get("method") != name:
            out.append("<p>%s</p>" % esc(dep.get("why", "")))
            prefer = use.get("method", "")
            if prefer:
                prefer_html = '<a href="%s.html"><code>%s</code></a>' % (esc(prefer), esc(prefer)) if prefer in snap.help else "<code>%s</code>" % esc(prefer)
                out.append("<p>The call to use is %s.</p>" % prefer_html)
    out.append("</aside>")
    return "\n".join(out)


# --- pages ------------------------------------------------------------------------------------

class Site:
    def __init__(self, src_dir, out_dir):
        self.src = src_dir
        self.out = out_dir
        with open(os.path.join(src_dir, "site.json")) as f:
            self.config = json.load(f)
        with open(os.path.join(src_dir, "template.html")) as f:
            self.template = string.Template(f.read())
        self.snaps = load_snapshots(os.path.join(src_dir, "versions"))
        self.order = sort_versions(self.snaps)
        self.channels = resolve_channels(self.snaps, self.config.get("channels"))
        self.default = default_channel(self.channels)
        self.changes = {}
        for i, v in enumerate(self.order):
            prev = self.snaps[self.order[i - 1]] if i else None
            self.changes[v] = (prev, compute_changes(prev, self.snaps[v]))

    def sections_for(self, snap):
        """Featured groups. A method is listed in the first section that names it, so the overview shows it once."""
        out = []
        seen = set()
        for s in self.config.get("sections", []):
            if "methods" in s:
                methods = [m for m in s["methods"] if m in snap.help]
            else:
                methods = [m for cat, ms in snap.groups if cat in s.get("categories", []) for m in ms]
            methods = [m for m in methods if m not in seen]
            seen.update(methods)
            if methods:
                out.append((s, methods))
        return out

    def page(self, rel_dir, title, body, snap, label, canonical=None, nav=""):
        depth = rel_dir.count("/") + 1 if rel_dir else 0
        root = "../" * depth
        stage = snap.stage if snap else ""
        sel = label or (self.default if snap else "")
        options = []
        for ch in CHANNELS[::-1]:
            if ch in self.channels:
                options.append('<option value="%s"%s>%s (%s)</option>'
                               % (ch, " selected" if sel == ch else "", ch, esc(self.channels[ch])))
        for v in reversed(self.order):
            options.append('<option value="%s"%s>%s</option>' % (esc(v), " selected" if sel == v else "", esc(v)))
        if sel not in CHANNELS and sel not in self.snaps:
            options.insert(0, '<option value="" disabled selected>Version</option>')
        banner = ""
        if snap and label in CHANNELS + ("",):
            channel = label or self.default
            banner = ('<div class="banner">You are reading the <strong>%s</strong> channel, currently <strong>%s</strong>. '
                      'Permanent link: <a href="%s%s/%s">%s/%s</a></div>'
                      % (esc(channel), esc(snap.version), root, esc(snap.version), esc(canonical or "index.html"),
                         esc(snap.version), esc(canonical or "")))
        return self.template.substitute(
            title=esc(title), site_title=esc(self.config.get("title", "RPC")), root=root,
            home=root + "index.html", version_options="\n".join(options),
            current=esc(label), stage=esc(stage), stage_label=esc(STAGE_LABEL.get(stage, "")),
            version=esc(snap.version if snap else ""), banner=banner, nav=nav, body=body,
            page=esc(canonical or ""), layout="docs" if nav else "plain",
            canonical=('<link rel="canonical" href="https://%s/%s/%s">' % (esc(self.config["domain"]), esc(snap.version), esc(canonical or "")))
            if snap and self.config.get("domain") else "",
            repository=esc(self.config.get("repository", "")))

    def nav(self, snap, current=None):
        parts = ['<input type="search" class="filter" placeholder="Filter methods" aria-label="Filter methods">',
                 '<ul class="nav-top"><li><a href="addresses.html"%s>Addresses</a></li>'
                 '<li><a href="index.html">Overview</a></li><li><a href="changes.html">Changes</a></li>'
                 '<li><a href="contracts.html">Contracts</a></li></ul>']
        parts[1] = parts[1] % (' aria-current="page"' if current == "addresses" else "")
        if moving_shown(self.config, snap):
            parts[1] = parts[1].replace("</li>", '</li><li><a href="moving.html"%s>Moving YEC</a></li>' %
                                        (' aria-current="page"' if current == "moving" else ""), 1)
        for cat, methods in snap.groups:
            parts.append('<details open><summary>%s</summary><ul>' % esc(cat))
            for m in methods:
                parts.append('<li><a href="%s.html"%s>%s</a></li>' % (esc(m), ' aria-current="page"' if m == current else "", esc(m)))
            parts.append("</ul></details>")
        return "\n".join(parts)

    def method_body(self, snap, name):
        prev, changes = self.changes[snap.version]
        badges = ['<span class="badge">%s</span>' % esc(snap.category[name])]
        for s, methods in self.sections_for(snap):
            if name in methods:
                badges.append('<a class="badge badge-%s" href="index.html#%s">%s</a>' % (esc(s["id"]), esc(s["id"]), esc(s["title"])))
        if changes is not None:
            if name in changes["added"]:
                badges.append('<a class="badge badge-new" href="changes.html">new in %s</a>' % esc(snap.version))
            elif any(c[0] == name for c in changes["changed"]):
                badges.append('<a class="badge badge-changed" href="changes.html#%s">changed in %s</a>' % (esc(name), esc(snap.version)))
        callout = render_address_callout(self.config, snap, name)
        callout += render_unavailable_callout(self.config, name)
        return ('<h1 class="method">%s</h1><p class="badges">%s</p>%s<pre class="help">%s</pre>\n%s'
                % (esc(name), " ".join(badges), callout, esc(snap.help[name]), render_contract_block(snap, name, "contracts.html")))

    def index_body(self, snap):
        src = snap.source
        prev, changes = self.changes[snap.version]
        out = ['<h1>Ycash %s RPC <span class="stage stage-%s">%s</span></h1>' % (esc(snap.version), esc(snap.stage), esc(STAGE_LABEL[snap.stage]))]
        facts = ["%d methods" % len(snap.methods), "node line <code>%s</code>" % esc(src.get("line", ""))]
        if src.get("tagCommit"):
            facts.append("tag <code>%s</code> at <code>%s</code>" % (esc(src.get("tag", "")), esc(src["tagCommit"][:12])))
        if changes is not None:
            facts.append('<a href="changes.html">%d added, %d removed, %d changed since %s</a>'
                         % (len(changes["added"]), len(changes["removed"]), len(changes["changed"]), esc(prev.version)))
        out.append('<p class="lede">The help text of every RPC as <code>ycashd</code> %s prints it, with the '
                   'vault and Yellowback contracts beside it. %s. '
                   '<a href="addresses.html">Addresses</a> says which call receives YEC and which holds YED.</p>'
                   % (esc(snap.version), " &middot; ".join(facts)))
        out.append('<div class="cards">')
        if self.config.get("receive"):
            links = "".join('<li><a href="addresses.html#%s">Receive %s</a> <span class="muted">%s</span></li>'
                            % (esc(g["id"]), esc(g["coin"]), esc(", ".join(t["name"] for t in g.get("types", []))))
                            for g in self.config["receive"])
            out.append('<section class="card card-addresses" id="addresses"><h2><a href="addresses.html">Addresses</a></h2>'
                       '<p>One list of the address types this release can create, and the call that creates each one on Ycash.</p>'
                       '<ul class="methods">%s</ul></section>' % links)
        for s, methods in self.sections_for(snap):
            out.append('<section class="card" id="%s"><h2>%s</h2><p>%s</p><ul class="methods">%s</ul></section>'
                       % (esc(s["id"]), esc(s["title"]), esc(s.get("intro", "")),
                          "".join('<li><a href="%s.html">%s</a> <span class="muted">%s</span></li>'
                                  % (esc(m), esc(m), esc(summary_of(snap.help[m]))) for m in methods)))
        out.append("</div><h2>All methods</h2>")
        for cat, methods in snap.groups:
            out.append('<section class="category"><h3 id="cat-%s">%s</h3><ul class="methods">%s</ul></section>'
                       % (esc(cat.lower()), esc(cat),
                          "".join('<li><a href="%s.html">%s</a> <span class="muted">%s</span></li>'
                                  % (esc(m), esc(m), esc(summary_of(snap.help[m]))) for m in methods)))
        return "\n".join(out)

    def write(self, rel, content):
        path = os.path.join(self.out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    def write_version(self, snap, rel_dir, label):
        prefix = rel_dir + "/" if rel_dir else ""
        prev, changes = self.changes[snap.version]
        check_help_quotes(self.config, snap)
        if moving_shown(self.config, snap):
            self.write(prefix + "moving.html", self.page(rel_dir, "Moving YEC, Ycash %s RPC" % snap.version,
                                                        render_moving_page(self.config, snap), snap, label,
                                                        "moving.html", self.nav(snap, "moving")))
        self.write(prefix + "index.html", self.page(rel_dir, "Ycash %s RPC" % snap.version, self.index_body(snap), snap, label,
                                                   "index.html", self.nav(snap)))
        self.write(prefix + "addresses.html", self.page(rel_dir, "Addresses, Ycash %s RPC" % snap.version,
                                                       render_addresses_page(self.config, snap), snap, label,
                                                       "addresses.html", self.nav(snap, "addresses")))
        self.write(prefix + "changes.html", self.page(rel_dir, "Changes in %s" % snap.version, render_changes_page(prev, snap, changes),
                                                     snap, label, "changes.html", self.nav(snap)))
        self.write(prefix + "contracts.html", self.page(rel_dir, "RPC contracts, %s" % snap.version, render_contracts_page(snap),
                                                       snap, label, "contracts.html", self.nav(snap)))
        for fn in snap.contracts:
            os.makedirs(os.path.join(self.out, prefix, "contracts"), exist_ok=True)
            shutil.copyfile(os.path.join(self.src, "versions", snap.version, "contracts", fn),
                            os.path.join(self.out, prefix, "contracts", fn))
        for m in snap.methods:
            self.write(prefix + m + ".html", self.page(rel_dir, "%s, Ycash %s RPC" % (m, snap.version), self.method_body(snap, m),
                                                      snap, label, m + ".html", self.nav(snap, m)))

    def versions_body(self):
        out = ['<h1>Versions</h1><p class="lede">Every published release keeps its pages at <code>/&lt;version&gt;/</code>. '
               'The channels follow the newest release of their stage: <code>/beta/</code> the newest of any stage, '
               '<code>/rc/</code> the newest release candidate or general release, <code>/stable/</code> the newest general release.</p>']
        if self.channels:
            out.append("<table><thead><tr><th>Channel</th><th>Version</th></tr></thead><tbody>")
            for ch in CHANNELS[::-1]:
                if ch in self.channels:
                    out.append('<tr><td><a href="%s/index.html">/%s/</a></td><td><a href="%s/index.html">%s</a></td></tr>'
                               % (ch, ch, esc(self.channels[ch]), esc(self.channels[ch])))
            out.append("</tbody></table>")
        out.append("<table><thead><tr><th>Version</th><th>Stage</th><th>Methods</th><th>Tag commit</th><th>Changes</th></tr></thead><tbody>")
        for v in reversed(self.order):
            s = self.snaps[v]
            prev, ch = self.changes[v]
            summary = "first published" if ch is None else "+%d &minus;%d ~%d" % (len(ch["added"]), len(ch["removed"]), len(ch["changed"]))
            out.append('<tr><td><a href="%s/index.html">%s</a></td><td><span class="stage stage-%s">%s</span></td><td>%d</td>'
                       '<td><code>%s</code></td><td><a href="%s/changes.html">%s</a></td></tr>'
                       % (esc(v), esc(v), esc(s.stage), esc(STAGE_LABEL[s.stage]), len(s.methods),
                          esc(s.source.get("tagCommit", "")[:12]), esc(v), summary))
        out.append("</tbody></table>")
        return "\n".join(out)

    def build(self):
        if os.path.exists(self.out):
            shutil.rmtree(self.out)
        os.makedirs(self.out)
        shutil.copytree(os.path.join(self.src, "assets"), os.path.join(self.out, "assets"))
        for v in self.order:
            self.write_version(self.snaps[v], v, v)
        for ch, v in self.channels.items():
            self.write_version(self.snaps[v], ch, ch)
        if self.default:
            self.write_version(self.snaps[self.channels[self.default]], "", "")
        self.write("versions.html", self.page("", "Versions", self.versions_body(), None, "versions"))
        self.write("404.html", self.page("", "Not found", '<h1>Not found</h1><p>No such page. '
                                         'The <a href="/index.html">overview</a> lists every method, '
                                         'and <a href="/versions.html">versions</a> every release.</p>', None, ""))
        manifest = {"default": self.default, "channels": self.channels,
                    "versions": {v: {"stage": self.snaps[v].stage, "methods": self.snaps[v].methods} for v in reversed(self.order)}}
        self.write("versions.json", json.dumps(manifest, indent=1) + "\n")
        if self.config.get("domain"):
            self.write("CNAME", self.config["domain"] + "\n")
        self.write(".nojekyll", "")
        return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", default=HERE)
    ap.add_argument("--out", default=os.path.join(HERE, "_site"))
    args = ap.parse_args(argv)
    site = Site(args.src, args.out)
    manifest = site.build()
    for where, what in pending_markers(site.config):
        print("build: pending (flip when it merges): %s: %s" % (where, what))
    print("build: %d versions, channels %s, / = %s -> %s" % (
        len(manifest["versions"]), ", ".join("%s=%s" % kv for kv in sorted(manifest["channels"].items())) or "none",
        manifest["default"], args.out))


if __name__ == "__main__":
    main()

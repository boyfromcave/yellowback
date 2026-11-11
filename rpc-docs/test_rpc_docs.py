#!/usr/bin/env python3
"""Unit tests for rpc-docs/build.py and capture.py. Offline: synthetic snapshots, no node."""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build  # noqa: E402
import capture  # noqa: E402

INDEX = """== Blockchain ==
getblockcount
getinfo

== Vault ==
vault_getinfo
vault_lock {params}
"""

VAULT_CONTRACT = {
    "contract": "vault-rpc", "branchid": "6d5b7a31",
    "types": {"hash": {"json": "string", "meaning": "32 bytes"}},
    "shapes": {"Recipient": {"type": "object", "fields": {"amount": {"type": "yec"}}, "optional": []}},
    "methods": {
        "vault_getinfo": {"wallet": False, "signature": "vault_getinfo", "params": [],
                          "result": {"type": "object", "fields": {"active": {"type": "bool"},
                                                                  "dbtip": {"oneOf": [{"type": "hash"}, {"type": "null"}]}},
                                     "optional": ["dbtip"]}},
        "vault_lock": {"wallet": True, "signature": "vault_lock {params}",
                       "params": [{"name": "params", "required": True,
                                   "type": {"type": "array", "items": {"ref": "Recipient"}}}],
                       "result": {"const": "ok"}},
    },
    "errors": [{"code": -5, "message": "unknown set", "raisedBy": ["vault_lock"], "provokedBy": "`vault_lock` of <a random id>"}],
}


def make_snapshot(root, version, index=INDEX, help_overrides=None, contract=VAULT_CONTRACT):
    d = os.path.join(root, "versions", version)
    os.makedirs(os.path.join(d, "help"))
    os.makedirs(os.path.join(d, "contracts"))
    with open(os.path.join(d, "help", "_index.txt"), "w") as f:
        f.write(index)
    for _, methods in build.parse_help_index(index):
        for m in methods:
            text = (help_overrides or {}).get(m, "%s\n\nDoes %s things.\n\nResult:\nn\n" % (m, m))
            with open(os.path.join(d, "help", m + ".txt"), "w") as f:
                f.write(text)
    if contract is not None:
        with open(os.path.join(d, "contracts", "vault-rpc-contract.json"), "w") as f:
            json.dump(contract, f)
    with open(os.path.join(d, "source.json"), "w") as f:
        json.dump({"version": version, "line": "ycash6", "tag": version, "tagCommit": "ab" * 20}, f)


def make_site(root, sections=None, channels=None):
    for fn in ("template.html",):
        shutil.copy(os.path.join(HERE, fn), root)
    shutil.copytree(os.path.join(HERE, "assets"), os.path.join(root, "assets"))
    with open(os.path.join(root, "site.json"), "w") as f:
        json.dump({"title": "Ycash RPC", "domain": "rpc.example", "repository": "https://example/rpc-docs",
                   "channels": channels or {},
                   "sections": sections if sections is not None else [
                       {"id": "vault", "title": "Vault primitive", "intro": "x", "categories": ["Vault"]},
                       {"id": "post-quantum", "title": "Post-quantum", "methods": ["getinfo", "absent_method"]}]}, f)


def read(root, rel):
    with open(os.path.join(root, "_site", rel)) as f:
        return f.read()


class Versions(unittest.TestCase):
    def test_order_puts_beta_before_rc_before_release(self):
        vs = ["v6.22.0", "v6.22.0-rc1", "v6.22.0-beta2", "v6.22.0-beta10", "v6.21.3", "v6.22.1-beta1"]
        self.assertEqual(build.sort_versions(vs),
                         ["v6.21.3", "v6.22.0-beta2", "v6.22.0-beta10", "v6.22.0-rc1", "v6.22.0", "v6.22.1-beta1"])

    def test_rejects_non_release_names(self):
        for bad in ("6.22.0", "v6.22", "v6.22.0-alpha1", "v6.22.0-beta", "latest"):
            with self.assertRaises(SystemExit):
                build.parse_version(bad)

    def test_channels_are_monotone(self):
        ch = build.resolve_channels(["v6.22.0-beta1", "v6.22.0-beta2"])
        self.assertEqual(ch, {"beta": "v6.22.0-beta2"})
        self.assertEqual(build.default_channel(ch), "beta")
        ch = build.resolve_channels(["v6.22.0-beta2", "v6.22.0-rc1", "v6.22.0", "v6.22.1-beta1"])
        self.assertEqual(ch, {"beta": "v6.22.1-beta1", "rc": "v6.22.0", "stable": "v6.22.0"})
        self.assertEqual(build.default_channel(ch), "stable")

    def test_pins_override_and_are_checked(self):
        ch = build.resolve_channels(["v6.22.0", "v6.22.1"], {"stable": "v6.22.0"})
        self.assertEqual(ch["stable"], "v6.22.0")
        with self.assertRaises(SystemExit):
            build.resolve_channels(["v6.22.0"], {"stable": "v6.23.0"})
        with self.assertRaises(SystemExit):
            build.resolve_channels(["v6.22.0"], {"nightly": "v6.22.0"})


class Rendering(unittest.TestCase):
    def test_type_expression(self):
        t = VAULT_CONTRACT["methods"]["vault_getinfo"]["result"]
        out = build.render_type(t, "contracts.html")
        self.assertIn("active: <span class=\"t-prim\">bool</span>", out)
        self.assertIn("dbtip?: <span class=\"t-prim\">hash</span> | <span class=\"t-prim\">null</span>", out)
        arr = build.render_type({"type": "array", "items": {"ref": "Recipient"}}, "contracts.html")
        self.assertEqual(arr, '<a href="contracts.html#shape-Recipient">Recipient</a>[]')
        self.assertEqual(build.render_type({"type": "array", "items": {"oneOf": [{"const": 1}, {"const": 2}]}}, ""),
                         '(<span class="t-const">1</span> | <span class="t-const">2</span>)[]')

    def test_inline_markdown_escapes_first(self):
        self.assertEqual(build.inline_md("`a<b>` **x** <i>"), "<code>a&lt;b&gt;</code> <strong>x</strong> &lt;i&gt;")

    def test_summary_is_the_first_description_line(self):
        self.assertEqual(build.summary_of("getinfo\n\nReturns state.\nMore.\n"), "Returns state.")
        self.assertEqual(build.summary_of("stop\n\nResult:\nx"), "")


class Site(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        make_site(self.root)

    def tearDown(self):
        shutil.rmtree(self.root)

    def build(self):
        return build.Site(self.root, os.path.join(self.root, "_site")).build()

    def test_single_version_layout(self):
        make_snapshot(self.root, "v6.22.0-beta1")
        m = self.build()
        self.assertEqual(m["channels"], {"beta": "v6.22.0-beta1"})
        for rel in ("index.html", "vault_lock.html", "v6.22.0-beta1/index.html", "v6.22.0-beta1/vault_lock.html",
                    "beta/vault_lock.html", "v6.22.0-beta1/changes.html", "v6.22.0-beta1/contracts.html",
                    "v6.22.0-beta1/contracts/vault-rpc-contract.json", "versions.html", "versions.json",
                    "404.html", "CNAME", ".nojekyll", "assets/site.css"):
            self.assertTrue(os.path.exists(os.path.join(self.root, "_site", rel)), rel)
        self.assertFalse(os.path.exists(os.path.join(self.root, "_site", "stable")))
        self.assertIn("first published version", read(self.root, "v6.22.0-beta1/changes.html"))
        self.assertEqual(read(self.root, "CNAME"), "rpc.example\n")

    def test_method_page_has_help_contract_errors_and_sections(self):
        make_snapshot(self.root, "v6.22.0-beta1")
        self.build()
        page = read(self.root, "v6.22.0-beta1/vault_lock.html")
        self.assertIn('<pre class="help">vault_lock\n\nDoes vault_lock things.', page)
        self.assertIn("needs the wallet", page)
        self.assertIn('href="contracts.html#shape-Recipient"', page)
        self.assertIn("unknown set", page)
        self.assertIn("<code>vault_lock</code> of &lt;a random id&gt;", page)
        self.assertIn('class="badge badge-vault"', page)
        self.assertNotIn('class="badge badge-post-quantum"', page)
        self.assertIn('href="../assets/site.css"', page)
        self.assertIn('<link rel="canonical" href="https://rpc.example/v6.22.0-beta1/vault_lock.html">', page)
        self.assertNotIn("You are reading", page)

    def test_channel_and_root_pages_link_to_the_pinned_version(self):
        make_snapshot(self.root, "v6.22.0-beta1")
        self.build()
        beta = read(self.root, "beta/vault_lock.html")
        self.assertIn("You are reading the <strong>beta</strong> channel", beta)
        self.assertIn('href="../v6.22.0-beta1/vault_lock.html"', beta)
        rootpage = read(self.root, "vault_lock.html")
        self.assertIn('href="assets/site.css"', rootpage)
        self.assertIn('href="v6.22.0-beta1/vault_lock.html"', rootpage)
        self.assertIn('<option value="beta" selected>', rootpage)

    def test_curated_section_skips_methods_the_version_lacks(self):
        make_snapshot(self.root, "v6.22.0-beta1")
        self.build()
        index = read(self.root, "v6.22.0-beta1/index.html")
        self.assertIn('id="post-quantum"', index)
        self.assertNotIn("absent_method", index)

    def test_changes_between_versions(self):
        make_snapshot(self.root, "v6.22.0-beta1")
        index2 = "== Blockchain ==\ngetblockcount\n\n== Vault ==\nvault_getinfo\nvault_lock {params}\nvault_send \"hex\"\n"
        make_snapshot(self.root, "v6.22.0-rc1", index=index2,
                      help_overrides={"vault_getinfo": "vault_getinfo\n\nDoes more vault things.\n"},
                      contract=dict(VAULT_CONTRACT, methods=dict(VAULT_CONTRACT["methods"], vault_lock=dict(
                          VAULT_CONTRACT["methods"]["vault_lock"], wallet=False))))
        m = self.build()
        self.assertEqual(m["channels"], {"beta": "v6.22.0-rc1", "rc": "v6.22.0-rc1"})
        self.assertEqual(list(m["versions"]), ["v6.22.0-rc1", "v6.22.0-beta1"])
        changes = read(self.root, "v6.22.0-rc1/changes.html")
        self.assertIn("1 added, 1 removed, 2 changed", changes)
        self.assertIn('href="vault_send.html"', changes)
        self.assertIn('href="../v6.22.0-beta1/getinfo.html"', changes)
        self.assertIn('<span class="add">+Does more vault things.</span>', changes)
        self.assertIn("vault_lock</a> <span class=\"muted\">contract</span>", changes)
        self.assertIn("badge-new", read(self.root, "v6.22.0-rc1/vault_send.html"))
        self.assertIn("badge-changed", read(self.root, "v6.22.0-rc1/vault_getinfo.html"))
        self.assertTrue(os.path.exists(os.path.join(self.root, "_site", "v6.22.0-beta1", "getinfo.html")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "_site", "rc", "getinfo.html")))

    def test_help_text_is_escaped(self):
        make_snapshot(self.root, "v6.22.0-beta1", help_overrides={"getinfo": "getinfo\n\n<script>alert(1)</script> & \"q\"\n"})
        self.build()
        page = read(self.root, "v6.22.0-beta1/getinfo.html")
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;q&quot;", page)

    def test_versions_without_contracts_build(self):
        make_snapshot(self.root, "v6.22.0", contract=None)
        self.build()
        self.assertIn("ships no RPC contracts", read(self.root, "v6.22.0/contracts.html"))
        self.assertIn("General release", read(self.root, "index.html"))


class AddressGuide(unittest.TestCase):
    def test_each_receive_call_is_listed_once_and_the_guide_names_the_call(self):
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out)
        build.Site(HERE, out).build()
        index = read_at(out, "v6.22.0-beta1/index.html")
        cards = index.split('<div class="cards">', 1)[1].split("<h2>All methods</h2>")[0]
        self.assertEqual(cards.count('href="yed_getnewaddress.html"'), 1)
        self.assertEqual(cards.count('href="getnewaddress.html"'), 0)
        self.assertIn('href="addresses.html#yec"', cards)
        self.assertIn('href="addresses.html#yed"', cards)
        self.assertNotIn('id="post-quantum"', cards)
        page = read_at(out, "v6.22.0-beta1/addresses.html")
        for text in ("Receive YEC", "Receive YED", "Transparent, ECC", "Sapling", "Post-quantum",
                     "pqslh", "yed_getnewaddress", "ycash-cli getnewaddress</pre>",
                     "z_getnewaddress sapling", "Ycash has no unified addresses", "Vault owner",
                     "not an address for receiving", "Not available on Ycash"):
            self.assertIn(text, page, text)
        # The calls the guide tells a reader to run are ones a Ycash node answers.
        cmds = "".join(re.findall(r'<pre class="cmd">(.*?)</pre>', page, re.S))
        for refused in ("z_getnewaccount", "z_getaddressforaccount"):
            self.assertNotIn(refused, cmds, refused)
        self.assertNotIn("Deprecated call", page)
        gna = read_at(out, "v6.22.0-beta1/getnewaddress.html")
        self.assertEqual(gna.count("returns this address"), 2)
        self.assertNotIn("deprecated way to create this address", gna)
        self.assertNotIn("The call to use is", gna)
        self.assertIn("getnewaddress is the supported call", gna)
        zna = read_at(out, "v6.22.0-beta1/z_getnewaddress.html")
        self.assertIn("returns this address", zna)
        self.assertIn("z_getnewaddress is the supported call", zna)
        for name in ("z_getnewaccount", "z_getaddressforaccount", "z_listaccounts", "z_getbalanceforaccount"):
            refused = read_at(out, "v6.22.0-beta1/%s.html" % name)
            self.assertIn("Not available on Ycash", refused, name)
            self.assertIn("which is not active on Ycash", refused, name)
            self.assertNotIn("returns this address", refused, name)
        yed = read_at(out, "v6.22.0-beta1/yed_getnewaddress.html")
        self.assertEqual(yed.count("returns this address"), 3)
        self.assertNotIn("deprecated way", yed)
        owner = read_at(out, "v6.22.0-beta1/vault_getnewowner.html")
        self.assertIn("Other keys", owner)
        self.assertIn("not an address for receiving", owner.lower())


def read_at(root, rel):
    with open(os.path.join(root, rel)) as f:
        return f.read()


class Capture(unittest.TestCase):
    def test_parse_help_index(self):
        groups = capture.parse_help_index(INDEX)
        self.assertEqual(groups, [("Blockchain", ["getblockcount", "getinfo"]), ("Vault", ["vault_getinfo", "vault_lock"])])

    def test_parse_help_index_rejects_odd_names(self):
        with self.assertRaises(SystemExit):
            capture.parse_help_index("== X ==\n../etc/passwd\n")
        with self.assertRaises(SystemExit):
            capture.parse_help_index("")

    def test_rejects_non_release_version_before_touching_anything(self):
        with self.assertRaises(SystemExit) as cm:
            capture.main(["v6.22.0-nightly", "--node-repo", "/nonexistent", "--bin-dir", "/nonexistent"])
        self.assertIn("not a release version", str(cm.exception))

    def test_image_reference_parsing(self):
        import fetch_image
        self.assertEqual(fetch_image.parse_ref("ghcr.io/boyfromcave/ycashd:ycash6-a8120c787aa4"),
                         ("ghcr.io", "boyfromcave/ycashd", "ycash6-a8120c787aa4"))
        self.assertEqual(fetch_image.parse_ref("ghcr.io/o/n"), ("ghcr.io", "o/n", "latest"))
        self.assertEqual(capture.IMAGE_COMMIT_RE.search("ghcr.io/o/ycashd:ycash6-a8120c787aa4").group(1), "a8120c787aa4")


if __name__ == "__main__":
    unittest.main()

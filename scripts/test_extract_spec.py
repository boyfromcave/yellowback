#!/usr/bin/env python3
# Copyright (c) 2026 The Ycash developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://www.opensource.org/licenses/mit-license.php .
"""Unit tests for scripts/extract_spec.py's prefix line (D-9): the client-copy skip of plain --check, the
```reshaped fence, and the prefix line's rpcversion check. Standard library only:

    python3 scripts/test_extract_spec.py -v
"""
import contextlib
import importlib.util
import io
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("extract_spec", os.path.join(HERE, "extract_spec.py"))
es = importlib.util.module_from_spec(spec)
spec.loader.exec_module(es)

PATH = "yed_getinfo.params.pqAddressVersion"
NEW = {"1": "5715aa", "2": "571444"}


def dies(fn, *args):
    """Whether fn(*args) stops through extract_spec.die (SystemExit), with stderr swallowed."""
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            fn(*args)
        except SystemExit:
            return True
    return False


def contract(value):
    return {"yed_getinfo": {"args": "", "returns": {"rpcversion": 9, "params": {"pqAddressVersion": value}}}}


class ClientCopySkip(unittest.TestCase):
    def test_only_exactly_one_version_behind_is_skipped(self):
        self.assertTrue(es.client_copy_lags_by_one(8, 9))
        self.assertFalse(es.client_copy_lags_by_one(7, 9))      # two behind: checked, fails as before
        self.assertFalse(es.client_copy_lags_by_one(9, 9))      # equal: checked
        self.assertFalse(es.client_copy_lags_by_one(10, 9))     # ahead: checked
        self.assertFalse(es.client_copy_lags_by_one(None, 9))   # missing or unparsable copy: checked
        self.assertFalse(es.client_copy_lags_by_one("8", 9))    # a string is not a version
        self.assertFalse(es.client_copy_lags_by_one(8, None))   # node doc without a version: checked

    def test_copy_version_reads_only_an_integer(self):
        with tempfile.TemporaryDirectory() as d:
            for text, want in (('{"rpcversion": 8}', 8), ('{"rpcversion": "8"}', None), ('{"rpcversion": true}', None),
                               ("not json", None)):
                p = os.path.join(d, "c.json")
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(text)
                self.assertEqual(es.copy_version(p), want, text)
            self.assertIsNone(es.copy_version(os.path.join(d, "missing.json")))


class Reshaped(unittest.TestCase):
    def deltas(self, value=None):
        return {"yed_getinfo": {"params": {"pqAddressVersion": NEW if value is None else value}}}

    def test_the_documents_object_replaces_the_earlier_string(self):
        doc = contract("5710")
        es.reshape_from_doc(doc, contract(dict(NEW)), self.deltas(), [PATH], "t")
        self.assertEqual(doc["yed_getinfo"]["returns"]["params"]["pqAddressVersion"], NEW)

    def test_a_string_where_an_object_is_required(self):
        self.assertTrue(dies(es.reshape_from_doc, contract("5710"), contract("5710"), self.deltas(), [PATH], "t"))

    def test_a_missing_key(self):
        self.assertTrue(dies(es.reshape_from_doc, contract("5710"), contract({"1": "5715aa"}), self.deltas(), [PATH], "t"))

    def test_an_extra_key(self):
        own = contract(dict(NEW, **{"3": "000000"}))
        self.assertTrue(dies(es.reshape_from_doc, contract("5710"), own, self.deltas(), [PATH], "t"))

    def test_a_path_the_doc_does_not_document(self):
        other = "yed_getinfo.params.pq.plainAddressVersion"
        self.assertTrue(dies(es.reshape_from_doc, contract("5710"), contract(dict(NEW)), self.deltas(), [other], "t"))

    def test_a_reshaped_path_without_a_json_block(self):
        self.assertTrue(dies(es.reshape_from_doc, contract("5710"), contract(dict(NEW)), {"yed_getinfo": {}}, [PATH], "t"))

    def test_the_fence_is_parsed(self):
        lines = ["### 4.99 delta (`rpcversion` 9)", "", "```reshaped", PATH, "```", "",
                 "#### `yed_getinfo`", "", "```json", '{"params": {"pqAddressVersion": {"1": "x", "2": "y"}}}', "```"]
        ver, deltas, args, removed, vault, reshaped = es.overlay_delta(lines, os.path.join(es.ROOT, "x.md"), "4.99")
        self.assertEqual((ver, reshaped, removed), (9, [PATH], []))
        self.assertIn("yed_getinfo", deltas)


class PrefixLineVersion(unittest.TestCase):
    def test_a_doc_stating_8_under_a_forced_prefix_line_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            doc = os.path.join(d, "yellowback-rpc.md")
            with open(doc, "w", encoding="utf-8") as fh:
                fh.write("# Yellowback RPC contract (`yed_*`), rpcversion 8\n")
            saved = os.environ.get("EXTRACT_SPEC_LINE")
            os.environ["EXTRACT_SPEC_LINE"] = "prefix"
            try:
                self.assertEqual(es.doc_line(doc), "prefix")
                self.assertTrue(dies(es.contract_text_prefix, es.read_plan(), es.read_plan_v3(), doc, es.RPCDOC_REL))
            finally:
                if saved is None:
                    del os.environ["EXTRACT_SPEC_LINE"]
                else:
                    os.environ["EXTRACT_SPEC_LINE"] = saved

    def test_the_line_follows_the_title(self):
        with tempfile.TemporaryDirectory() as d:
            doc = os.path.join(d, "yellowback-rpc.md")
            for v, line in ((8, "fees"), (9, "prefix"), (10, "prefix")):
                with open(doc, "w", encoding="utf-8") as fh:
                    fh.write("# Yellowback RPC contract (`yed_*`), rpcversion %d\n" % v)
                self.assertEqual(es.doc_line(doc), line)


if __name__ == "__main__":
    unittest.main()

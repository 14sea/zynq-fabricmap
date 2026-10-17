"""b4/hypothesis/ff_behaviour_v0.2.json and b4/host/b4_ff_hypothesis.py — the behaviour hypothesis is held to
its shape (status unverified, the eleven flags, the seven decoded semantics with machine-enum readings, sources
of every kind each naming what it adopts); `load()` ALWAYS re-hashes every named source (an absent or changed
source is a refusal, never a skip, and there is no switch); a hypothesis that is not the committed file enters
only through `fixture()` and is marked; the decode goes through the hypothesis's readings by equality (an
unrecognised reading is refused by name at load and at decode, never read as a default); clock_mode is decoded
by storage context (the latch probe's finding); a swap is another, marked object with its own digest. No skip."""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402


class TheFile(unittest.TestCase):
    def test_it_loads_and_every_source_hashes(self):
        h = hy.load()
        self.assertEqual(h.doc["status"], "unverified")
        self.assertEqual(h.version, "0.2.0")
        self.assertEqual((h.path, h.fixture), (hy.HYPOTHESIS_REL, False))
        self.assertEqual(hy.source_findings(h.doc), [])
        kinds = [s["kind"] for s in h.doc["sources"]]
        self.assertEqual(kinds.count("vendor_primitive"), 6)
        self.assertEqual(kinds.count("repository_document"), 1)
        self.assertEqual({s["primitive"] for s in h.doc["sources"] if s["kind"] == "vendor_primitive"}, {"FDRE", "FDSE", "FDCE", "FDPE", "LDCE", "LDPE"})
        cert = next(s for s in h.doc["sources"] if s["kind"] == "certificate_mapping")
        self.assertEqual(cert["sha256"], bm.site_mapping().certificate_sha256)
        for s in h.doc["sources"]:
            self.assertTrue(s.get("adopted") or s.get("items"), s["kind"])

    def test_every_flag_is_read_through_the_object(self):
        h = hy.load()
        for f in hy.FLAGS:
            self.assertIs(h.flag(f), True)
        with self.assertRaises(hy.HypothesisRefusal):
            h.flag("not_a_flag")

    def test_the_decode_of_the_base_configuration(self):
        h, m = hy.load(), bm.site_mapping()
        base = {a: 0 for a in m.addresses}
        for a, e in m.entries.items():
            if e.semantic in ("ff_srval", "ce_mode", "sr_mode", "sr_kind"):
                base[a] = 1
        d = h.decode(base, m)
        self.assertTrue(d.in_domain)
        for e in bm.ELEMENTS:
            c = d[e]
            self.assertEqual((c.applicable, c.primitive, c.init, c.srval, c.ce_driven, c.sr_driven, c.sync, c.latch, c.clk_inverted),
                             (True, "FDRE", 1, 0, True, True, True, False, False), e)
        base[m.address_of("AFF", "ff_init")] = 1          # ZINI: INIT = 0
        base[m.address_of("BFF", "ff_srval")] = 0         # ZRST cleared: SRVAL = 1 -> FDSE
        base[m.address_of(None, "sr_kind")] = 0           # asynchronous
        d = h.decode(base, m)
        self.assertEqual((d["AFF"].init, d["AFF"].primitive), (0, "FDCE"))
        self.assertEqual((d["BFF"].srval, d["BFF"].primitive), (1, "FDPE"))
        base[m.address_of(None, "storage_kind")] = 1      # latch, clock_mode bit still 0: NO attested reading
        d = h.decode(base, m)
        self.assertEqual((d["AFF"].primitive, d["BFF"].primitive, d["AFF"].sync), ("LDCE", "LDPE", False))
        self.assertEqual([d[e].applicable for e in bm.ELEMENTS], [True, False, True, False, True, False, True, False])
        self.assertEqual(d["A5FF"].primitive, None)
        self.assertFalse(d.in_domain)
        self.assertEqual(d.unknown_readings, (("clock_mode", "latch", 0),))
        self.assertIsNone(d["AFF"].clk_inverted)
        base[m.address_of(None, "clock_mode")] = 1        # the attested LDCE endpoint: CLKINV = 1 with IS_G_INVERTED = 0
        d = h.decode(base, m)
        self.assertTrue(d.in_domain)
        self.assertIs(d["AFF"].clk_inverted, False, "under a latch the CLKINV bit does not mean an inverted gate")
        base[m.address_of(None, "storage_kind")] = 0      # a flip-flop with the same bit: inverted
        self.assertIs(h.decode(base, m)["AFF"].clk_inverted, True)
        with self.assertRaises(hy.HypothesisRefusal):
            h.decode({}, m)

    def test_a_swapped_reading_decodes_differently_and_is_another_object(self):
        h, m = hy.load(), bm.site_mapping()
        base = {a: 0 for a in m.addresses}
        h2 = h.with_reading("ff_init", "init_1", "init_0", "test")
        self.assertNotEqual(h2.sha256, h.sha256)
        self.assertEqual((h2.version, h2.fixture, h.fixture), ("0.2.0+test", True, False))
        self.assertEqual(h.decode(base, m)["AFF"].init, 1)
        self.assertEqual(h2.decode(base, m)["AFF"].init, 0)
        h3 = h.with_flag("x5ff_not_storage_when_latch", False, "t")
        base[m.address_of(None, "storage_kind")] = 1
        self.assertFalse(h.decode(base, m)["A5FF"].applicable)
        self.assertTrue(h3.decode(base, m)["A5FF"].applicable)
        self.assertIs(h.flag("x5ff_not_storage_when_latch"), True, "the swap did not touch the original")
        with self.assertRaises(hy.HypothesisRefusal) as cm:
            h.with_reading("ff_init", "not an INIT reading", "init_0", "bad")
        self.assertIn("'not an INIT reading' is not one of", str(cm.exception))
        with self.assertRaises(hy.HypothesisRefusal):
            h.with_reading("clock_mode", "inverted", "not_inverted", "ctx")          # clock_mode needs a storage context
        h4 = h.with_reading("clock_mode", "inverted", "not_inverted", "ctx", context="latch")
        self.assertEqual(h4.doc["decode"]["clock_mode"]["by_storage_context"]["flipflop"], h.doc["decode"]["clock_mode"]["by_storage_context"]["flipflop"])

    def test_a_fixture_hypothesis_is_marked_and_the_default_entry_has_no_switch(self):
        doc = json.loads(hy.HYPOTHESIS.read_text())
        doc["sources"][0]["path"] = "DOES_NOT_EXIST.v"
        f = hy.fixture(doc, "missing-source")
        self.assertTrue(f.fixture)
        self.assertEqual(f.path, "fixture:missing-source")
        with self.assertRaises(hy.HypothesisRefusal):
            hy.fixture(doc, "")
        import inspect
        self.assertEqual(list(inspect.signature(hy.load).parameters), ["path"], "load() takes a path and nothing that could skip a check")


class Refusals(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="b4_hyp_"))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.doc = json.loads(hy.HYPOTHESIS.read_text())

    def refused(self, needle: str, edit) -> None:
        doc = copy.deepcopy(self.doc)
        edit(doc)
        p = self.d / "h.json"
        p.write_text(json.dumps(doc))
        with self.assertRaises(hy.HypothesisRefusal) as cm:
            hy.load(p)
        self.assertIn(needle, str(cm.exception))

    def test_shape(self):
        self.refused("is not 'unverified'", lambda d: d.__setitem__("status", "verified"))
        self.refused("exactly the flags", lambda d: d["behaviour"].pop("ce_gates_capture"))
        self.refused("exactly the flags", lambda d: d["behaviour"].__setitem__("ce_gates_capture", "yes"))
        self.refused("decode must carry exactly", lambda d: d["decode"].pop("clock_mode"))
        self.refused("lack a 'vendor_primitive' entry", lambda d: d.__setitem__("sources", [s for s in d["sources"] if s["kind"] != "vendor_primitive"]))
        self.refused("states nothing adopted", lambda d: d["sources"][0].__setitem__("adopted", []))
        self.refused("lacks a path or a 64-hex sha256", lambda d: d["sources"][0].__setitem__("sha256", "0" * 10))
        self.refused("applicable_semantics is absent", lambda d: d.pop("applicable_semantics"))
        self.refused("must list executing_side_visible and host_only_diagnostics", lambda d: d["observation_context"].pop("host_only_diagnostics"))
        self.refused("has an unknown kind 'web_page'", lambda d: d["sources"].append({"kind": "web_page", "adopted": ["x"]}))

    def test_an_unrecognised_reading_is_refused_at_load_never_defaulted(self):
        self.refused("decode.ff_init.bit_one: 'not an INIT reading' is not one of ('init_0', 'init_1')", lambda d: d["decode"]["ff_init"].__setitem__("bit_one", "not an INIT reading"))
        self.refused("decode.clock_mode.latch.bit_zero: 'maybe' is not one of", lambda d: d["decode"]["clock_mode"]["by_storage_context"]["latch"].__setitem__("bit_zero", "maybe"))
        self.refused("decode.ff_srval.bit_zero: 'unknown' is not one of ('srval_0', 'srval_1')", lambda d: d["decode"]["ff_srval"].__setitem__("bit_zero", "unknown"))
        self.refused("must carry by_storage_context for exactly flipflop and latch", lambda d: d["decode"]["clock_mode"]["by_storage_context"].pop("latch"))
        self.refused("decode.ff_init.meaning must give the human meaning", lambda d: d["decode"]["ff_init"]["meaning"].pop("init_0"))

    def test_sources_are_rehashed_by_the_default_entry(self):
        self.refused("FDRE.v does not hash to the recorded digest", lambda d: d["sources"][0].__setitem__("sha256", "0" * 64))
        self.refused("DOES_NOT_EXIST.v is absent at", lambda d: d["sources"][0].__setitem__("path", "DOES_NOT_EXIST.v"))
        self.refused("docs/ff_latch_probe.md does not hash", lambda d: next(s for s in d["sources"] if s["kind"] == "repository_document").__setitem__("sha256", "1" * 64))


if __name__ == "__main__":
    unittest.main()

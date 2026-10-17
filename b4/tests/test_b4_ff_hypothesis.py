"""b4/hypothesis/ff_behaviour_v0.1.json and b4/host/b4_ff_hypothesis.py — the behaviour hypothesis is held to
its shape (status unverified, the eleven flags, the seven decoded semantics with both readings, sources of all
three kinds each naming what it adopts), every vendor and certificate source is re-hashed from disk (an absent
source is a FAILURE, never a skip: the file names what it was written from), the decode goes through the
hypothesis's readings (a swapped reading decodes differently), and a swap gives a different object with its own
digest. No skip."""
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
        h = hy.load(check_sources=True)
        self.assertEqual(h.doc["status"], "unverified")
        self.assertEqual(h.version, "0.1.0")
        self.assertEqual(h.path, hy.HYPOTHESIS_REL)
        self.assertEqual(hy.source_findings(h.doc), [])
        kinds = [s["kind"] for s in h.doc["sources"]]
        self.assertEqual(kinds.count("vendor_primitive"), 6)
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
        base[m.address_of(None, "storage_kind")] = 1      # latch
        d = h.decode(base, m)
        self.assertEqual((d["AFF"].primitive, d["BFF"].primitive, d["AFF"].sync), ("LDCE", "LDPE", False))
        self.assertEqual([d[e].applicable for e in bm.ELEMENTS], [True, False, True, False, True, False, True, False])
        self.assertEqual(d["A5FF"].primitive, None)
        with self.assertRaises(hy.HypothesisRefusal):
            h.decode({}, m)

    def test_a_swapped_reading_decodes_differently_and_is_another_object(self):
        h, m = hy.load(), bm.site_mapping()
        base = {a: 0 for a in m.addresses}
        h2 = h.with_reading("ff_init", "INIT = 1", "INIT = 0", "test")
        self.assertNotEqual(h2.sha256, h.sha256)
        self.assertEqual(h2.version, "0.1.0+test")
        self.assertEqual(h.decode(base, m)["AFF"].init, 1)
        self.assertEqual(h2.decode(base, m)["AFF"].init, 0)
        h3 = h.with_flag("x5ff_not_storage_when_latch", False, "t")
        base[m.address_of(None, "storage_kind")] = 1
        self.assertFalse(h.decode(base, m)["A5FF"].applicable)
        self.assertTrue(h3.decode(base, m)["A5FF"].applicable)
        self.assertIs(h.flag("x5ff_not_storage_when_latch"), True, "the swap did not touch the original")


class Refusals(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="b4_hyp_"))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.doc = json.loads(hy.HYPOTHESIS.read_text())

    def refused(self, needle: str, edit, check_sources: bool = False) -> None:
        doc = copy.deepcopy(self.doc)
        edit(doc)
        p = self.d / "h.json"
        p.write_text(json.dumps(doc))
        with self.assertRaises(hy.HypothesisRefusal) as cm:
            hy.load(p, check_sources=check_sources)
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

    def test_sources_are_rehashed(self):
        self.refused("FDRE.v does not hash to the recorded digest", lambda d: d["sources"][0].__setitem__("sha256", "0" * 64), check_sources=True)
        self.refused("is absent at", lambda d: d["sources"][0].__setitem__("path", "NOPE.v"), check_sources=True)


if __name__ == "__main__":
    unittest.main()

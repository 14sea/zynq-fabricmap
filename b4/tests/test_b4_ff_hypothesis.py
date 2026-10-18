"""b4/hypothesis/ff_behaviour_v0.3.json and b4/host/b4_ff_hypothesis.py — the behaviour hypothesis is held to
its shape (status unverified, the eleven flags, the seven decoded semantics with machine-enum readings, sources
of every kind each naming what it adopts); `load()` takes NO path, reads the committed file only against the
pinned HYPOTHESIS_SHA256 and ALWAYS re-hashes every named source (an absent or changed source is a refusal,
never a skip, and there is no switch); a hypothesis that is not the committed file — a changed copy, a VALID
copy at another path, a document built in a test — enters only through `fixture()` / `fixture_file()` and is
marked; `unknown` is a reading in clock_mode's latch context only (v0.3 uses it nowhere: every assignment of the 21 bits is in its domain;
the superseded v0.2 file is kept byte for byte and enters only as the marked v021_hole fixture, whose domain has the 0.2.1 hole); the
decode goes through the hypothesis's readings by equality (an
unrecognised reading is refused by name at load and at decode, never read as a default); clock_mode is decoded
by storage context (the latch probe's finding); a swap is another, marked object with its own digest. No skip."""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host", R / "b4/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
from b4_test_fixtures import V021_REL, V021_SHA256, v021_hole_hypothesis  # noqa: E402


class TheFile(unittest.TestCase):
    def test_it_loads_and_every_source_hashes(self):
        h = hy.load()
        self.assertEqual(h.doc["status"], "unverified")
        self.assertEqual(h.version, "0.3.0")
        self.assertEqual((h.path, h.fixture, h.sha256), (hy.HYPOTHESIS_REL, False, hy.HYPOTHESIS_SHA256))
        self.assertEqual(hy.HYPOTHESIS_REL, "b4/hypothesis/ff_behaviour_v0.3.json")
        self.assertEqual(hy.source_findings(h.doc), [])
        kinds = [s["kind"] for s in h.doc["sources"]]
        self.assertEqual(kinds.count("vendor_primitive"), 6)
        self.assertEqual(kinds.count("repository_document"), 2, "docs/ff_latch_probe.md and the D1' probe report")
        self.assertEqual([s["path"] for s in h.doc["sources"] if s["kind"] == "repository_document"],
                         ["docs/ff_latch_probe.md", "evidence/b4/unit_d1prime_latch_ginv_attempt2_2026_10_18/probe_report.json"])
        items = next(s for s in h.doc["sources"] if s["kind"] == "project_decode_assumption")["items"]
        self.assertEqual([t[:2] for t in items if t[:1] == "G" and t[1:2].isdigit()], ["G1", "G2", "G3", "G4", "G5", "G6"], "the six generalisation assumptions, each its own item")
        self.assertEqual(h.doc["decode"]["clock_mode"]["by_storage_context"], {"flipflop": {"bit_one": "inverted", "bit_zero": "not_inverted"},
                                                                               "latch": {"bit_one": "not_inverted", "bit_zero": "inverted"}})
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
        base[m.address_of(None, "storage_kind")] = 1      # latch, clock_mode bit still 0: v0.3 reads the gate INVERTED (the D1' pair)
        d = h.decode(base, m)
        self.assertEqual((d["AFF"].primitive, d["BFF"].primitive, d["AFF"].sync), ("LDCE", "LDPE", False))
        self.assertEqual([d[e].applicable for e in bm.ELEMENTS], [True, False, True, False, True, False, True, False])
        self.assertEqual(d["A5FF"].primitive, None)
        self.assertTrue(d.in_domain)
        self.assertEqual(d.unknown_readings, ())
        self.assertIs(d["AFF"].clk_inverted, True, "v0.3: under a latch the CLKINV bit clear means the gate is the slice clock inverted")
        hole = v021_hole_hypothesis()                     # the 0.2.1 reading, kept as a marked fixture: the same configuration is outside ITS domain
        d0 = hole.decode(base, m)
        self.assertFalse(d0.in_domain)
        self.assertEqual(d0.unknown_readings, (("clock_mode", "latch", 0),))
        self.assertIsNone(d0["AFF"].clk_inverted)
        base[m.address_of(None, "clock_mode")] = 1        # the attested LDCE endpoint: CLKINV = 1 with IS_G_INVERTED = 0
        d = h.decode(base, m)
        self.assertTrue(d.in_domain)
        self.assertIs(d["AFF"].clk_inverted, False, "under a latch the CLKINV bit does not mean an inverted gate")
        self.assertIs(hole.decode(base, m)["AFF"].clk_inverted, False, "the bit-1 reading is the same in 0.2.1 and 0.3.0")
        base[m.address_of(None, "storage_kind")] = 0      # a flip-flop with the same bit: inverted
        self.assertIs(h.decode(base, m)["AFF"].clk_inverted, True)
        with self.assertRaises(hy.HypothesisRefusal):
            h.decode({}, m)

    def test_every_assignment_is_in_the_v03_domain_and_the_v02_file_is_kept_as_a_marked_fixture(self):
        """v0.3 declares no unknown reading, so no decode can leave the domain (held table by table, not by sampling); the kept
        v0.2 file hashes to the 0.2.1 digest, is never the formal hypothesis, and enters as the marked v021_hole fixture whose
        only unknown is the latch's bit 0."""
        h, m = hy.load(), bm.site_mapping()
        for semantic, entry in h.doc["decode"].items():
            tables = entry["by_storage_context"].values() if semantic == "clock_mode" else [entry]
            for t in tables:
                self.assertNotIn("unknown", (t["bit_one"], t["bit_zero"]), semantic)
        rng = random.Random(5)
        latch, clk = m.address_of(None, "storage_kind"), m.address_of(None, "clock_mode")
        for _ in range(64):
            c = {a: rng.randint(0, 1) for a in m.addresses}
            c[latch], c[clk] = 1, 0                                  # the 0.2.1 hole, with the 19 free bits random
            self.assertTrue(h.decode(c, m).in_domain)
            self.assertFalse(v021_hole_hypothesis().decode(c, m).in_domain)
        raw = (R / V021_REL).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), V021_SHA256, "the kept v0.2 file is byte for byte the 0.2.1 file")
        self.assertNotEqual(V021_SHA256, hy.HYPOTHESIS_SHA256)
        hole = v021_hole_hypothesis()
        self.assertEqual((hole.version, hole.fixture, hole.path, hole.sha256), ("0.2.1", True, "fixture:v021_hole", V021_SHA256))
        self.assertEqual(hole.doc["decode"]["clock_mode"]["by_storage_context"]["latch"], {"bit_one": "not_inverted", "bit_zero": "unknown"})
        self.assertEqual({k: v for k, v in hole.doc["behaviour"].items()}, h.doc["behaviour"], "the eleven flags are the same in 0.2.1 and 0.3.0")
        with mock.patch.object(hashlib, "sha256", side_effect=lambda b: hashlib.sha3_256(b)):
            with self.assertRaises(AssertionError):
                v021_hole_hypothesis()                             # a kept file that does not hash to the 0.2.1 digest is an error, not another fixture

    def test_a_swapped_reading_decodes_differently_and_is_another_object(self):
        h, m = hy.load(), bm.site_mapping()
        base = {a: 0 for a in m.addresses}
        h2 = h.with_reading("ff_init", "init_1", "init_0", "test")
        self.assertNotEqual(h2.sha256, h.sha256)
        self.assertEqual((h2.version, h2.fixture, h.fixture), ("0.3.0+test", True, False))
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

    def test_a_fixture_hypothesis_is_marked_and_the_formal_entry_takes_no_path(self):
        doc = json.loads(hy.HYPOTHESIS.read_text())
        doc["sources"][0]["path"] = "DOES_NOT_EXIST.v"
        f = hy.fixture(doc, "missing-source")
        self.assertTrue(f.fixture)
        self.assertEqual(f.path, "fixture:missing-source")
        with self.assertRaises(hy.HypothesisRefusal):
            hy.fixture(doc, "")
        self.assertEqual(list(inspect.signature(hy.load).parameters), [], "load() takes nothing: no path, no switch")

    def test_a_valid_external_copy_is_a_fixture_never_the_formal_hypothesis(self):
        """The owner's probe on b91162c: a valid copy with ce_gates_capture flipped must not come back as formal."""
        d = Path(tempfile.mkdtemp(prefix="b4_ext_"))
        self.addCleanup(shutil.rmtree, d, True)
        doc = json.loads(hy.HYPOTHESIS.read_text())
        p = d / "copy.json"
        p.write_bytes(hy.HYPOTHESIS.read_bytes())                 # byte-identical
        f = hy.fixture_file(p, "copy")
        self.assertTrue(f.fixture, "even a byte-identical copy at another path is a fixture")
        self.assertEqual(f.sha256, hy.HYPOTHESIS_SHA256)
        doc["behaviour"]["ce_gates_capture"] = False
        p.write_text(json.dumps(doc))
        altered = hy.fixture_file(p, "altered")
        self.assertTrue(altered.fixture)
        self.assertIs(altered.flag("ce_gates_capture"), False)
        with self.assertRaises(TypeError):
            hy.load(p)                                             # there is no such call
        import b4_ff_model as fm
        t = fm.Fabric(bm.site_mapping(), altered).observe({a: 0 for a in bm.site_mapping().addresses}, [fm.init()])
        self.assertIs(t["hypothesis"]["fixture"], True, "a trace under an external document says fixture")

    def test_the_formal_entry_holds_the_committed_file_to_its_pinned_digest(self):
        d = Path(tempfile.mkdtemp(prefix="b4_pin_"))
        self.addCleanup(shutil.rmtree, d, True)
        p = d / "h.json"
        p.write_text(json.dumps(json.loads(hy.HYPOTHESIS.read_text())))   # same content, other bytes
        patch = mock.patch.object(hy, "HYPOTHESIS", p)
        patch.start()
        self.addCleanup(patch.stop)
        with self.assertRaises(hy.HypothesisRefusal) as cm:
            hy.load()
        self.assertIn("not the pinned", str(cm.exception))
        patch.stop()
        self.assertEqual(hy.load().sha256, hy.HYPOTHESIS_SHA256)

    def test_the_formal_entry_consults_the_source_rehash(self):
        patch = mock.patch.object(hy, "source_findings", return_value=["source FDRE.v does not hash to the recorded digest"])
        patch.start()
        self.addCleanup(patch.stop)
        with self.assertRaises(hy.HypothesisRefusal) as cm:
            hy.load()
        self.assertIn("FDRE.v does not hash", str(cm.exception))


class Refusals(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="b4_hyp_"))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.doc = json.loads(hy.HYPOTHESIS.read_text())

    def refused(self, needle: str, edit) -> None:
        """The shape is held at the fixture boundary (the only entry for a document that is not the committed file)
        and, for the committed file, by load(); the findings are the same function's."""
        doc = copy.deepcopy(self.doc)
        edit(doc)
        with self.assertRaises(hy.HypothesisRefusal) as cm:
            hy.fixture(doc, "probe")
        self.assertIn(needle, str(cm.exception))
        self.assertEqual(hy.shape_findings(doc), hy.shape_findings(doc), "deterministic")
        self.assertTrue(any(needle in f for f in hy.shape_findings(doc)))

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
        self.refused("decode.clock_mode.flipflop.bit_one: unknown is allowed only where no attestation exists — clock_mode under a latch", lambda d: d["decode"]["clock_mode"]["by_storage_context"]["flipflop"].__setitem__("bit_one", "unknown"))
        self.refused("domain_refusal is absent", lambda d: d.pop("domain_refusal"))
        self.refused("formal_input is absent", lambda d: d.pop("formal_input"))
        self.refused("must carry by_storage_context for exactly flipflop and latch", lambda d: d["decode"]["clock_mode"]["by_storage_context"].pop("latch"))
        self.refused("decode.ff_init.meaning must give the human meaning", lambda d: d["decode"]["ff_init"]["meaning"].pop("init_0"))

    def test_sources_are_rehashed_by_name(self):
        def findings(edit):
            doc = copy.deepcopy(self.doc); edit(doc); return hy.source_findings(doc)
        self.assertEqual(findings(lambda d: None), [])
        self.assertIn("source FDRE.v does not hash to the recorded digest", findings(lambda d: d["sources"][0].__setitem__("sha256", "0" * 64)))
        self.assertTrue(any("DOES_NOT_EXIST.v is absent at" in f for f in findings(lambda d: d["sources"][0].__setitem__("path", "DOES_NOT_EXIST.v"))))
        self.assertIn("source docs/ff_latch_probe.md does not hash to the recorded digest", findings(lambda d: next(s for s in d["sources"] if s["kind"] == "repository_document").__setitem__("sha256", "1" * 64)))


if __name__ == "__main__":
    unittest.main()

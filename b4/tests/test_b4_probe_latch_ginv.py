"""The latch_ginv probe's pure parts, without Vivado: the per-cell verification of a readback (every
cell, not the first; an unresolved property is a finding, never filled in), the structural comparison
of the pair, the expectation over the site's bits and the diff buckets, the build-cache refusals, and
the recipe's fixed facts (the mine site, one mode, the pair differing in GINV alone, the original
recipe files untouched)."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("probe_latch_ginv", REPO / "b4/probes/latch_ginv/probe_latch_ginv.py")
P = importlib.util.module_from_spec(_spec)
sys.modules["probe_latch_ginv"] = P
_spec.loader.exec_module(P)


def good_readback(ginv: int) -> dict[str, str]:
    rb = {"part": "xc7z010clg400-1", "vivado_version": "2025.2", "mode": "7", "requested_site": "SLICE_X2Y25",
          "requested_ginv": str(ginv), "storage_count": "4", "lut_count": "8"}
    for n, bel in enumerate(("AFF", "BFF", "CFF", "DFF")):
        rb[f"store.{n}.name"] = f"g_full.g_store[{n}].g_used.g_latch.s"
        rb[f"store.{n}.ref"] = "LDCE"
        rb[f"store.{n}.loc"] = "SLICE_X2Y25"
        rb[f"store.{n}.bel"] = f"SLICEL.{bel}"
        rb[f"store.{n}.init"] = "1'b0"
        for p in P.INVERSION_PROPS:
            rb[f"store.{n}.prop.{p}"] = ""
        rb[f"store.{n}.prop.IS_G_INVERTED"] = "1'b1" if ginv else "1'b0"
        rb[f"store.{n}.prop.IS_CLR_INVERTED"] = "1'b0"
        for pin, net in (("G", "clk_g"), ("GE", "ce_IBUF"), ("CLR", "rst_IBUF"), ("D", f"g_full.o6[{n}]"), ("Q", f"g_full.qb[{n}]")):
            rb[f"store.{n}.pin.{pin}.net"] = net
            rb[f"store.{n}.pin.{pin}.belpin"] = f"SLICE_X2Y25/{bel}/{pin}"
            rb[f"store.{n}.pin.{pin}.route_status"] = "ROUTED"
    for n in range(8):
        rb[f"lut.{n}.name"] = f"lut{n}"; rb[f"lut.{n}.ref"] = "LUT5"; rb[f"lut.{n}.loc"] = "SLICE_X2Y25"; rb[f"lut.{n}.bel"] = f"SLICEL.{'ABCD'[n % 4]}{'6' if n < 4 else '5'}LUT"
    for n, bel in enumerate(("A6LUT", "B6LUT", "C6LUT", "D6LUT", "A5LUT", "B5LUT", "C5LUT", "D5LUT", "AFF", "BFF", "CFF", "DFF")):
        rb[f"occupied.{n}.bel"] = f"SLICE_X2Y25/{bel}"; rb[f"occupied.{n}.ref"] = "LUT5" if "LUT" in bel else "LDCE"
    rb["anchor.0.name"] = "g_anchor.anchor_ff"; rb["anchor.0.loc"] = "SLICE_X4Y20"; rb["anchor.0.bel"] = "SLICEL.AFF"
    return rb


class Cells(unittest.TestCase):
    def test_a_good_readback_has_no_finding_for_either_endpoint(self):
        self.assertEqual(P.cell_findings(good_readback(0), 0), [])
        self.assertEqual(P.cell_findings(good_readback(1), 1), [])

    def test_the_requested_inversion_is_checked_on_every_cell_not_the_first(self):
        rb = good_readback(1)
        rb["store.3.prop.IS_G_INVERTED"] = "1'b0"                       # the LAST cell is wrong
        f = P.cell_findings(rb, 1)
        self.assertEqual(len(f), 1)
        self.assertIn("cell 3", f[0]); self.assertIn("IS_G_INVERTED is \"1'b0\"", f[0])

    def test_an_unresolved_property_is_a_finding_never_filled_in(self):
        rb = good_readback(0)
        rb["store.1.prop.IS_G_INVERTED"] = ""
        self.assertTrue(any("cell 1" in f and "unresolved" in f for f in P.cell_findings(rb, 0)))
        del rb["store.2.prop.IS_CLR_INVERTED"]
        self.assertTrue(any("cell 2" in f and "IS_CLR_INVERTED unresolved" in f for f in P.cell_findings(rb, 0)))

    def test_primitive_loc_bel_pins_and_count(self):
        rb = good_readback(0); rb["store.0.ref"] = "FDCE"
        self.assertTrue(any("cell 0" in f and "primitive" in f for f in P.cell_findings(rb, 0)))
        rb = good_readback(0); rb["store.2.loc"] = "SLICE_X3Y25"
        self.assertTrue(any("cell 2" in f and "LOC" in f for f in P.cell_findings(rb, 0)))
        rb = good_readback(0); rb["store.1.bel"] = "SLICEL.AFF"           # duplicate BEL
        self.assertTrue(any("exactly once" in f for f in P.cell_findings(rb, 0)))
        rb = good_readback(0); rb["store.3.pin.GE.net"] = ""
        self.assertTrue(any("cell 3" in f and "pin GE has no net" in f for f in P.cell_findings(rb, 0)))
        rb = good_readback(0); rb["store.0.pin.D.route_status"] = "UNROUTED"
        self.assertTrue(any("cell 0" in f and "route status" in f for f in P.cell_findings(rb, 0)))
        rb = good_readback(0); rb["store.2.pin.CLR.net"] = "other_net"
        self.assertTrue(any("pin CLR is driven by different nets" in f for f in P.cell_findings(rb, 0)))
        rb = good_readback(0); rb["storage_count"] = "3"
        self.assertTrue(any("storage_count is 3" in f for f in P.cell_findings(rb, 0)))
        rb = good_readback(0); rb["requested_ginv"] = "1"
        self.assertTrue(any("requested_ginv" in f for f in P.cell_findings(rb, 0)))


class Structure(unittest.TestCase):
    def test_the_pair_differing_in_the_gate_inversion_alone_is_structurally_equal(self):
        self.assertEqual(P.structure_findings(good_readback(0), good_readback(1)), [])

    def test_any_other_difference_is_named(self):
        b = good_readback(1); b["occupied.11.bel"] = "SLICE_X2Y25/D5FF"
        self.assertEqual(P.structure_findings(good_readback(0), b), ["occupied differs between the endpoints"])
        b = good_readback(1); b["anchor.0.loc"] = "SLICE_X5Y20"
        self.assertEqual(P.structure_findings(good_readback(0), b), ["anchors differs between the endpoints"])
        b = good_readback(1); b["store.0.prop.IS_CLR_INVERTED"] = "1'b1"
        self.assertEqual(P.structure_findings(good_readback(0), b), ["cells differs between the endpoints"])


class Expectation(unittest.TestCase):
    L, C = "30_32", "01_51"

    def mover(self, token, before, after):
        return {"segbit": token, "before": before, "after": after, "direction": f"{before}->{after}"}

    def test_met_only_by_latch_kept_and_clkinv_alone_moving_1_to_0(self):
        e = P.expectation({self.L: 1, self.C: 1}, {self.L: 1, self.C: 0}, [self.mover(self.C, 1, 0)],
                          {"in_scope": 1, "frame_ecc": 9, "db_attributed": 0, "ownership_unknown": 0, "unattributed": 0}, self.L, self.C, 0)
        self.assertTrue(e["met"]); self.assertEqual(e["clkinv_values"], [1, 0])

    def test_every_miss_names_its_clause(self):
        base = ({self.L: 1, self.C: 1}, {self.L: 1, self.C: 0}, [self.mover(self.C, 1, 0)],
                {"in_scope": 1, "frame_ecc": 9, "db_attributed": 0, "ownership_unknown": 0, "unattributed": 0})
        a, b, mv, counts = base
        e = P.expectation({self.L: 0, self.C: 1}, b, mv, counts, self.L, self.C)
        self.assertFalse(e["met"]); self.assertFalse(e["clauses"]["latch_set_in_both"])
        e = P.expectation(a, {self.L: 1, self.C: 1}, [], {**counts, "in_scope": 0}, self.L, self.C)
        self.assertFalse(e["clauses"]["clkinv_moves_1_to_0"]); self.assertFalse(e["clauses"]["clkinv_is_the_only_same_class_mover"])
        self.assertFalse(e["clauses"]["clkinv_in_scope_once"])
        e = P.expectation(a, b, mv + [self.mover("00_48", 1, 0)], {**counts, "db_attributed": 1}, self.L, self.C, 1)
        self.assertFalse(e["clauses"]["clkinv_is_the_only_same_class_mover"]); self.assertFalse(e["clauses"]["no_class_claim_out_of_scope"])
        e = P.expectation(a, b, mv, {**counts, "ownership_unknown": 1}, self.L, self.C)
        self.assertFalse(e["clauses"]["no_bucket_but_in_scope_and_ecc"])
        e = P.expectation({self.L: 1, self.C: 0}, {self.L: 1, self.C: 1}, [self.mover(self.C, 0, 1)], counts, self.L, self.C)
        self.assertFalse(e["met"]); self.assertFalse(e["clauses"]["clkinv_moves_1_to_0"])   # wrong direction


class Cache(unittest.TestCase):
    def test_refusals_and_states(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "main_latch"
            self.assertEqual(P.cache_state(d, "main_latch")[0], "build")
            d.mkdir(); (d / "spec.bit").write_bytes(b"x")
            self.assertEqual(P.cache_state(d, "main_latch")[0], "refuse")      # artifacts without a stamp
            stamp = {"completed": True, "endpoint": "main_latch", "mode": 7, "ginv": 0, "site": "SLICE_X2Y25",
                     "recipe": P.recipe_hashes(), "artifacts": {}}
            (d / "stamp.json").write_text(json.dumps({**stamp, "ginv": 1}))
            self.assertIn("ginv", P.cache_state(d, "main_latch")[1])
            (d / "stamp.json").write_text(json.dumps({**stamp, "recipe": {}}))
            self.assertIn("recipe hash", P.cache_state(d, "main_latch")[1])
            (d / "stamp.json").write_text(json.dumps({**stamp, "completed": False}))
            self.assertEqual(P.cache_state(d, "main_latch")[0], "failed")
            (d / "stamp.json").write_text(json.dumps({**stamp, "artifacts": {"spec.bit": P.sha256_file(d / "spec.bit")}}))
            self.assertIn("missing", P.cache_state(d, "main_latch")[1])     # readback.tsv / base.dcp absent
            for name in P.ARTIFACTS:
                (d / name).write_bytes(b"x")
            full = {**stamp, "artifacts": {n: P.sha256_file(d / n) for n in P.ARTIFACTS}}
            (d / "stamp.json").write_text(json.dumps(full))
            self.assertEqual(P.cache_state(d, "main_latch")[0], "reuse")
            (d / "spec.bit").write_bytes(b"y")
            self.assertIn("does not match", P.cache_state(d, "main_latch")[1])


class Recipe(unittest.TestCase):
    def test_fixed_facts(self):
        self.assertEqual(P.MINE_SITE, "SLICE_X2Y25")
        self.assertEqual({e["mode"] for e in P.ENDPOINTS.values()}, {7})
        self.assertEqual([P.ENDPOINTS[n]["ginv"] for n in P.PAIR], [0, 1])
        self.assertEqual(P.EXPECTED_CLKINV_DIRECTION, "1->0")

    def test_the_original_recipe_is_the_one_the_old_evidence_pins(self):
        m = json.loads((REPO / "evidence/ff_latch_probe_2026_08_04/manifest.json").read_text())
        self.assertEqual(P.originals_hashes(), m["recipe"])

    def test_the_derived_sources_carry_the_gate_inversion_and_nothing_is_read_from_the_old_path(self):
        v = P.SOURCE.read_text(); t = P.TCL.read_text()
        self.assertEqual(v.count(".IS_G_INVERTED(GINV_BIT)"), 2)
        self.assertIn("-generic GINV=$ginv", t)
        self.assertIn("read_verilog $here/specimen_ff_latch_ginv.v", t)
        self.assertNotIn("specimen_ff_probe.v\n", t)
        self.assertIn("store.$n.prop.$prop", t)


if __name__ == "__main__":
    unittest.main()

"""b4/host/b4_snapshot.py — the map rebuilt from the ledger: a HAND q-grid ledger with versions and states derived by hand
(the commitments alone are digests the cartographer computes), then real runs (budget 24, the formal v0.3 hypothesis, the
exposed seeds 7 / 11) for every arm mode, with tampered records (not the last one), an F whose search records pretend to
learn, an X with the wrong permutation, and an injected control failure that does not reproduce. Mechanics only. No skip."""
from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host", R / "b4/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_carto as bc  # noqa: E402
import b4_controls as ctl  # noqa: E402
import b4_engine as be  # noqa: E402
import b4_execution as ex  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402
import b4_landscape as bl  # noqa: E402
import b4_snapshot as sn  # noqa: E402

L, O, B = 7, 11, 24
A, Bg, C = [[0, 0]], [[1, 0]], [[0, 1]]      # one-step, two-element q grids
STIM = "s" * 64


def copy(d):
    return json.loads(json.dumps(d))


def hand_ledger():
    """Three addresses. By hand: seq1 base g=0 A; seq2 g=1 B (bit 0: cells {(0,0)} -> effect_seen, v1); seq3 g=2 A (bit 1 vs base:
    no cells -> no_effect_seen, v2; vs g=1 multi-bit); seq4 g=3 B ((1,3): bit 1, B vs B no effect, pairs_without 2; (2,3): bit 0,
    A vs B effect, pairs_with 2; v3); seq5 g=4 C (bit 2: cells {(0,1)} effect_seen, v4; the rest multi-bit); seq6 g=5 C ((1,5):
    bit 2, B vs C cells; (4,5): bit 0, C vs C NO effect -> bit 0 becomes context_dependent; v5)."""
    rows = [("base", 0, A), ("search", 1, Bg), ("search", 2, A), ("search", 3, Bg), ("search", 4, C), ("search", 5, C)]
    carto = bc.ObservationCarto(3)
    ledger = []
    for seq, (phase, g, grid) in enumerate(rows, start=1):
        vb = carto.version
        carto.ingest(seq, g, STIM, grid)
        ledger.append({"seq": seq, "phase": phase, "genome": g, "stimulus_sha256": STIM, "q_grid": [list(r) for r in grid],
                       "map_version_before": vb, "map_version_after": carto.version, "map_commitment_after": carto.commitment()})
    return ledger, carto


def hand_result(ledger, carto):
    return {"arm": "O", "given_view": None, "ledger": ledger, "x_perm": None, "control_failure": None,
            "map_version_final": carto.version, "map_commitment_final": carto.commitment(),
            "map_specimens_final": len(carto.specimens), "map_multi_bit_pairs_final": carto.multi_bit_pairs, "frozen_view": None}


class HandLedger(unittest.TestCase):
    def setUp(self):
        self.ledger, self.carto = hand_ledger()
        self.task = types.SimpleNamespace(addresses=("a", "b", "c"))
        self.result = hand_result(self.ledger, self.carto)

    def test_versions_by_hand(self):
        self.assertEqual([e["map_version_after"] for e in self.ledger], [0, 1, 2, 3, 4, 5], "the cartographer agrees with the hand derivation")
        self.assertEqual(self.carto.multi_bit_pairs, 1 + 1 + 3 + 3)

    def test_the_prefix_states_by_hand(self):
        p2 = sn.prefix_states(self.result, self.task, 2)
        self.assertEqual((p2["records"], p2["findings"], p2["map_version"]), (3, [], 2))
        self.assertEqual(p2["states"], {"unknown": 1, "effect_seen": 1, "no_effect_seen": 1, "context_dependent": 0})
        self.assertEqual(p2["not_unknown"], 2)
        self.assertEqual(p2["relations"]["0"]["state"], "effect_seen")
        p5 = sn.prefix_states(self.result, self.task, 5)
        self.assertEqual(p5["states"], {"unknown": 0, "effect_seen": 1, "no_effect_seen": 1, "context_dependent": 1})
        self.assertEqual(p5["relations"]["0"]["state"], "context_dependent")
        self.assertEqual(p5["map_version"], 5)
        self.assertEqual(sum(p5["states"].values()), 3)

    def test_a_prefix_beyond_the_ledger_or_of_the_wrong_shape_is_a_finding_not_a_count(self):
        p = sn.prefix_states(self.result, self.task, 6)
        self.assertIsNone(p["states"])
        self.assertIn("fewer", p["findings"][0])
        bad = copy(self.result)
        bad["ledger"][2]["phase"] = "probe"
        self.assertIn("not the base followed by search", sn.prefix_states(bad, self.task, 3)["findings"][0])
        with self.assertRaises(ValueError):
            sn.prefix_states(dict(self.result, arm="R"), self.task, 2)
        with self.assertRaises(ValueError):
            sn.prefix_states(self.result, self.task, 0)

    def test_a_tampered_middle_record_is_found_where_it_lies(self):
        bad = copy(self.result)
        bad["ledger"][2]["q_grid"] = [[1, 1]]
        p = sn.prefix_states(bad, self.task, 5)
        self.assertTrue(any("seq 3" in f for f in p["findings"]), p["findings"])
        self.assertEqual(sn.prefix_states(bad, self.task, 1)["findings"], [], "a prefix before the tampered record is clean")
        rc = sn.recompute_findings(bad, self.task)
        self.assertTrue(any("seq 3" in f for f in rc["findings"]))
        bad = copy(self.result)
        bad["ledger"][3]["map_version_after"] += 1
        self.assertTrue(any("seq 4" in f for f in sn.recompute_findings(bad, self.task)["findings"]))
        bad = copy(self.result)
        bad["map_commitment_final"] = "0" * 64
        self.assertTrue(any("final map" in f for f in sn.recompute_findings(bad, self.task)["findings"]))
        self.assertEqual(sn.recompute_findings(self.result, self.task)["findings"], [])


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m, cls.h = bm.site_mapping(), hy.load()
        cls.fab = fm.Fabric(cls.m, cls.h)
        cls.task = bl.make_task(L, cls.m.addresses)
        P = lambda: ex.ObservationPort(cls.fab)  # noqa: E731
        cls.R = be.run("R", cls.task, P(), O, B).as_dict()
        cls.F = be.run("F", cls.task, P(), O, B).as_dict()
        cls.O = be.run("O", cls.task, P(), O, B).as_dict()
        cls.X = be.run("X", cls.task, P(), O, B, control_seed=ctl.x_control_seed(L, O)).as_dict()
        dv, _ = ctl.d_view(cls.F, cls.task)
        cls.D = be.run("F", cls.task, P(), O, B, view=dv).as_dict()
        cls.Om = be.run("F", cls.task, P(), O, B, view=bc.oracle_view(cls.m)).as_dict()
        cls.A0 = be.run("F", cls.task, P(), O, B, view=bc.address_only_view(cls.m.addresses)).as_dict()


class RealRuns(Base):
    def test_every_arm_mode_rebuilds_without_a_finding(self):
        want = {"R": ("none", False), "F": ("learned_frozen", True), "O": ("online", True), "X": ("relabelled", True),
                "D": ("given", False), "Om": ("given", False), "A0": ("given", False)}
        for name, r in (("R", self.R), ("F", self.F), ("O", self.O), ("X", self.X), ("D", self.D), ("Om", self.Om), ("A0", self.A0)):
            rc = sn.recompute_findings(r, self.task)
            self.assertEqual((rc["mode"], rc["applicable"], rc["findings"]), (*want[name], []), name)
            st = sn.arm_states(r, self.task)
            if rc["applicable"]:
                self.assertEqual(sum(rc["states"].values()), 21, name)
                self.assertEqual((rc["map_version"], rc["map_commitment"]), (r["map_version_final"], r["map_commitment_final"]), name)
                self.assertIsNotNone(rc["relations_final"])
                self.assertEqual(st["not_unknown"], 21 - rc["states"]["unknown"])
            else:
                self.assertIsNone(rc["states"]); self.assertIsNone(rc["relations_final"]); self.assertIsNone(st["not_unknown"])
        self.assertEqual(sn.recompute_findings(self.F, self.task)["states"]["unknown"], 0, "21 probes from the base leave no address unknown")

    def test_o_s_prefix_at_every_grid_budget_up_to_its_evals(self):
        prev = -1
        for b in (8, 16, 24):
            p = sn.prefix_states(self.O, self.task, b)
            self.assertEqual((p["records"], p["findings"]), (b + 1, []), b)
            self.assertEqual(sum(p["states"].values()), 21)
            self.assertGreaterEqual(p["not_unknown"], prev, "coverage never falls along the prefix")
            prev = p["not_unknown"]
            self.assertEqual(p["map_commitment"], self.O["ledger"][b]["map_commitment_after"], "the prefix's map is the record's at that evaluation")
        self.assertEqual(sn.prefix_states(self.O, self.task, 24)["map_commitment"], self.O["map_commitment_final"])
        self.assertIn("not the base followed by search", sn.prefix_states(self.O, self.task, 25)["findings"][0], "the holdout record is never part of a prefix")
        self.assertIn("fewer", sn.prefix_states(self.O, self.task, 26)["findings"][0])

    def test_an_f_whose_search_pretends_to_learn_is_found(self):
        bad = copy(self.F)
        s = next(e for e in bad["ledger"] if e["phase"] == "search")
        s["map_version_after"] += 1
        rc = sn.recompute_findings(bad, self.task)
        self.assertTrue(any("frozen map" in f for f in rc["findings"]), rc["findings"])
        bad = copy(self.F)
        bad["frozen_view"] = bad["frozen_view"][1:]
        self.assertTrue(any("frozen_view" in f for f in sn.recompute_findings(bad, self.task)["findings"]))

    def test_x_with_the_wrong_permutation_or_the_true_genome_is_found(self):
        bad = copy(self.X)
        n = len(self.task.addresses)
        bad["x_perm"] = [(i + 2) % n for i in range(n)]
        rc = sn.recompute_findings(bad, self.task)
        self.assertTrue(rc["findings"], "a different relabelling does not reproduce the recorded commitments")
        with mock.patch.object(bc, "relabel_genome", lambda g, perm: g):
            rc = sn.recompute_findings(self.X, self.task)
        self.assertTrue(rc["findings"], "feeding the true genome to X's cartographer does not reproduce the record")
        self.assertEqual(sn.recompute_findings(self.X, self.task)["findings"], [])

    def test_a_given_view_record_that_moves_is_found(self):
        bad = copy(self.D)
        bad["ledger"][5]["map_commitment_after"] = "0" * 64
        self.assertTrue(any("seq 6" in f for f in sn.recompute_findings(bad, self.task)["findings"]))
        bad = copy(self.R)
        bad["ledger"][3]["map_version_after"] = 1
        self.assertTrue(any("seq 4" in f for f in sn.recompute_findings(bad, self.task)["findings"]))

    def test_an_injected_control_failure_does_not_reproduce_from_the_ledger(self):
        real = bc.isomorphic_addresses
        calls = {"n": 0}

        def fake(x, shadow, perm):
            calls["n"] += 1
            return ["injected"] if calls["n"] == 5 else real(x, shadow, perm)
        with mock.patch.object(bc, "isomorphic_addresses", fake):
            r = be.run("X", self.task, ex.ObservationPort(self.fab), O, B, control_seed=ctl.x_control_seed(L, O)).as_dict()
        self.assertIsNotNone(r["control_failure"])
        rc = sn.recompute_findings(r, self.task)
        self.assertTrue(any("control failure" in f for f in rc["findings"]), rc["findings"])


if __name__ == "__main__":
    unittest.main()

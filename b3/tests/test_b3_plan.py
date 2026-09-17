"""b3/host/b3_plan.py — the gate's numbers, the seed exclusion (every archived set plus the B3 gate's
own pairs), the split rule with the 0.85 margin, the arm order, the record arithmetic, the prediction's
determinism and structure, B3Q's frozen experiment, and the stop rule."""
from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    sys.path.insert(0, str(p))
import b2_maps as bmaps  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_plan as pl  # noqa: E402

GATE = R / "evidence/b3/gate/gate_report.json"


class GateAndSeeds(unittest.TestCase):
    def test_gate_inputs_are_run_1s(self):
        g = pl.gate_inputs(GATE)
        self.assertEqual((g["fitness"], g["budget_per_arm"], g["pairs"]), ("F1", 1000, 9))
        self.assertTrue(g["H9_claim_condition"])
        self.assertEqual(g["seeds"]["label"], "b3-gate")

    def test_session_seeds_avoid_every_archived_set_including_the_gates(self):
        master, seeds, sources, excl = pl.session_seeds(9, GATE)
        self.assertEqual(master, bs.master_seed("b3-session", pl.INSTRUMENT_COMMIT))
        self.assertEqual(len(seeds), 9)
        flat = {s for p in seeds for s in p}
        self.assertFalse(flat & excl)
        self.assertTrue(any("B3 gate" in k for k in sources))
        raw = json.loads((R / "evidence/b3/gate/raw_F1.json").read_text())["rows"]
        gate_flat = {row["landscape_seed"] for row in raw} | {row["operator_seed"] for row in raw}
        self.assertFalse(flat & gate_flat)
        m = json.loads((R / "manifests/b2_manifest.json").read_text())
        self.assertFalse(flat & {s for p in m["seeds"]["pairs"] for s in p})
        q = pl.qualification_seeds(seeds, GATE)
        self.assertEqual(len(q), 1)
        self.assertFalse({s for p in q for s in p} & (flat | excl))


class SplitAndArithmetic(unittest.TestCase):
    def test_records(self):
        self.assertEqual(pl.records_per_pair(1000), 3003)
        self.assertEqual(pl.session_records(9, 1000), 2 + 27027)
        self.assertEqual(pl.records_per_pair(40), 123)
        self.assertEqual(pl.session_records(1, 40), 125)

    def test_arm_order_is_prefix_balanced(self):
        seq = [pl.arm_order(r) for r in range(9)]
        self.assertEqual(["".join(s) for s in seq[:6]], ["RFO", "FOR", "ORF", "ROF", "OFR", "FRO"])
        for n in (3, 6, 9):
            counts = {(arm, pos): 0 for arm in "RFO" for pos in range(3)}
            for r in range(n):
                for pos, arm in enumerate(pl.arm_order(r)):
                    counts[(arm, pos)] += 1
            self.assertEqual(len(set(counts.values())), 1, n)          # equal exactly when N is a multiple of 3
        counts = {(arm, pos): 0 for arm in "RFO" for pos in range(3)}
        for r in range(8):
            for pos, arm in enumerate(pl.arm_order(r)):
                counts[(arm, pos)] += 1
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)

    def test_split_rule_with_the_margin(self):
        u = pl.session_split(9, 1000, None)
        self.assertTrue(u["status"].startswith("UNDETERMINED"))
        self.assertEqual(u["calibration_margin"], 0.85)
        d = pl.session_split(9, 1000, 3000.0)
        self.assertEqual(d["status"], "DETERMINED")
        self.assertAlmostEqual(d["rate_for_split"], 2550.0)
        # at 2 550 / h the expected span of p pairs is (2 + 3003 p) x 3600 / 2550: p = 1 -> 4 242 s fits, p = 2 -> 8 482 s does not
        self.assertEqual(d["pairs_per_session_max"], 1)
        self.assertEqual(len(d["sessions"]), 9)
        self.assertEqual(d["total_records"], 9 * (2 + 3003))
        self.assertAlmostEqual(d["sessions"][0]["deadline_s"], 1.25 * 3005 * 3600 / 2550 + 600)
        # the margin is what decides: without it 2 pairs would fit at 3 000 / h ... (2 + 6006) x 3600 / 3000 = 7 209.6 s — no, still 1; at 3 100 / h: 2 pairs
        self.assertEqual(pl.session_split(9, 1000, 3100.0 / 0.85)["pairs_per_session_max"], 2)
        self.assertEqual(pl.session_split(9, 1000, 3100.0)["pairs_per_session_max"], 1)
        inf = pl.session_split(9, 1000, 1000.0)
        self.assertEqual(inf["status"], "INFEASIBLE")
        for bad in (0, -1.0, float("nan"), float("inf"), True, "3000"):
            with self.assertRaises(pl.RateInvalid):
                pl.session_split(9, 1000, bad)


class Prediction(unittest.TestCase):
    def test_deterministic_and_structured_on_a_small_budget(self):
        _m, seeds, _s, _e = pl.session_seeds(2, GATE)
        a = pl.build_prediction("F1", 12, seeds)
        b = pl.build_prediction("F1", 12, seeds)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual(a["fitness_sequence_length"], 2 * (3 * 12 + 3))
        for p in a["pairs"]:
            self.assertEqual(set(p["runs"]), {"R", "F", "O"})
            self.assertEqual(p["runs"]["O"]["wrong_decodes"], 0)
            self.assertEqual(p["runs"]["O"]["anomalies"], 0)
            self.assertEqual(p["runs"]["O"]["ledger_entries"], 12)
            self.assertEqual(p["delta1_O_minus_R"], p["runs"]["O"]["best_train"] - p["runs"]["R"]["best_train"])
            self.assertEqual(p["delta2_O_minus_endtoend_F"], p["runs"]["O"]["best_train"] - p["runs"]["F"]["end_to_end_at_budget"])
            self.assertEqual(p["runs"]["F"]["end_to_end_at_budget"], p["base_train_fitness"])   # 12 <= 333: the base
        self.assertIn("predicted_primary_2", a)

    def test_the_stop_rule_names_a_primary_below_alpha(self):
        pred = {"predicted_primary_1": {"sign_test_p": 0.002, "alpha": 0.05, "positives": 9, "negatives": 0, "ties": 0},
                "predicted_primary_2": {"sign_test_p": 0.36, "alpha": 0.05, "positives": 5, "negatives": 3, "ties": 1}}
        f = pl.stop_rule_findings(pred)
        self.assertEqual(len(f), 1)
        self.assertIn("predicted_primary_2", f[0])
        pred["predicted_primary_2"]["sign_test_p"] = 0.01
        self.assertEqual(pl.stop_rule_findings(pred), [])

    def test_the_trial_prediction_on_the_fixed_seeds_triggers_the_stop_rule(self):
        """The trial of 2026-09-17 (evidence/b3/plan_trial_2026_09_17): primary 1 at p = 0.00195, primary 2
        at p = 0.363 on the nine fixed session pairs — the stop rule's finding, kept as evidence."""
        d = R / "evidence/b3/plan_trial_2026_09_17"
        if not d.is_dir():
            self.skipTest("no trial evidence")
        pred = json.loads((d / "prediction.json").read_text())
        f = pl.stop_rule_findings(pred)
        self.assertEqual(len(f), 1)
        self.assertIn("predicted_primary_2", f[0])
        self.assertEqual(pred["predicted_primary_1"]["positives"], 9)


class Qualification(unittest.TestCase):
    def test_b3q_numbers(self):
        _m, seeds, _s, _e = pl.session_seeds(9, GATE)
        q = pl.build_qualification_plan("F1", bmaps.sha256_of(bmaps.load_self_map()), seeds, GATE)
        self.assertEqual(q["budget_per_arm"], 40)
        self.assertEqual(q["records"], {"per_pair": 123, "search": 120, "holdout": 3, "ledger_entries": 40, "baselines": 2, "total": 125})
        self.assertEqual(q["session"], "B3Q")
        self.assertAlmostEqual(q["planning_bound"]["session_timeout_s"], 1.25 * 125 * 3600 / pl.QUAL_PLANNING_RATE_PER_HOUR + 600)


if __name__ == "__main__":
    unittest.main()

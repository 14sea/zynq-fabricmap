"""B2 plan / prediction: reproducible from the rule, disjoint from the gate's seeds, and
the prediction equals a fresh run of the reference (docs/b2_preregistration.md §2–§3)."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_model as bm  # noqa: E402
import b2_gate as bg  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_search as bs  # noqa: E402

PLAN = R / "evidence/b2/plan.json"
PRED = R / "evidence/b2/prediction.json"


@unittest.skipUnless(PLAN.exists() and PRED.exists(), "no committed B2 plan / prediction")
class Committed(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(PLAN.read_text())
        self.pred = json.loads(PRED.read_text())

    def test_seeds_follow_the_rule_and_avoid_the_gate(self):
        master = bs.master_seed(bp.SESSION_LABEL, bp.INSTRUMENT_COMMIT)
        self.assertEqual(self.plan["seed_derivation"]["master_seed"], master)
        pairs = bs.pair_seeds(master, self.plan["pairs"])
        self.assertEqual([(p["landscape_seed"], p["operator_seed"]) for p in self.pred["pairs"]], pairs)
        gate = json.loads((R / "evidence/b2/gate/gate_report.json").read_text())
        gate_seeds = {x for p in bs.pair_seeds(gate["seeds"]["master_seed"], gate["seeds"]["count"]) for x in p}
        self.assertFalse(gate_seeds & {x for p in pairs for x in p})
        self.assertNotIn(master, bs.EXCLUDED_SEEDS)

    def test_fitness_budget_pairs_are_the_gates(self):
        gate = json.loads((R / "evidence/b2/gate/gate_report.json").read_text())
        fid = gate["selected_fitness"]
        self.assertEqual(self.plan["fitness"], fid)
        self.assertEqual(self.plan["budget_per_arm"], gate["results"][fid]["b_star"])
        self.assertEqual(self.plan["pairs"], gate["results"][fid]["criteria"]["G5"]["required_pairs_N"])
        self.assertEqual(self.plan["gate"]["sha256"], hashlib.sha256((R / "evidence/b2/gate/gate_report.json").read_bytes()).hexdigest())

    def test_record_count(self):
        n, b = self.plan["pairs"], self.plan["budget_per_arm"]
        self.assertEqual(self.plan["records"]["total"], 1 + n * 2 * b + n * 2 + 1)
        self.assertEqual(self.pred["fitness_sequence_length"], n * 2 * b + n * 2)

    def test_prediction_pinned_in_plan(self):
        self.assertEqual(self.plan["prediction_sha256"], hashlib.sha256(PRED.read_bytes()).hexdigest())

    def test_prediction_equals_a_fresh_reference_run(self):
        truth = bm.truth_mapping()
        masks = bl.universe_mask(truth)
        fabric = bs.ModelFabric(truth)
        view = bmaps.MapView(bmaps.load_self_map(), bl.train_vectors())
        self.assertEqual(self.plan["map"]["sha256"], view.sha256)
        for p in self.pred["pairs"][:3]:          # three pairs: the full set is the plan tool's job
            land = bl.Landscape(self.plan["fitness"], p["landscape_seed"], masks=masks, truth=truth)
            a = bs.run(bs.ARM_RANDOM_SAFE, land, None, p["operator_seed"], self.plan["budget_per_arm"], fabric)
            b = bs.run(bs.ARM_MAP_GUIDED, land, view, p["operator_seed"], self.plan["budget_per_arm"], fabric)
            self.assertEqual(p["runs"]["A"]["best_train"], a.best_trace[-1])
            self.assertEqual(p["runs"]["B"]["best_train"], b.best_trace[-1])
            self.assertEqual(p["runs"]["A"]["champion_holdout"], a.champion_holdout)
            self.assertEqual(p["runs"]["B"]["champion_holdout"], b.champion_holdout)
            self.assertEqual(p["delta_B_minus_A"], b.best_trace[-1] - a.best_trace[-1])

    def test_primary_is_the_sign_test_over_the_deltas(self):
        d = bp.decision(self.pred["deltas"])
        self.assertEqual(d, self.pred["predicted_primary"])
        p, pos, neg, ties = bg.sign_test_p(self.pred["deltas"])
        self.assertEqual((pos, neg, ties), (d["positives"], d["negatives"], d["ties"]))

    def test_arm_order_alternates(self):
        for p in self.pred["pairs"]:
            self.assertEqual(p["arm_order"], ["A", "B"] if p["pair"] % 2 == 0 else ["B", "A"])


if __name__ == "__main__":
    unittest.main()

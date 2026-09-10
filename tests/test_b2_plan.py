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
        gate = json.loads((R / self.plan["gate"]["path"]).read_text())
        fid = gate["selected_fitness"]
        self.assertEqual(self.plan["fitness"], fid)
        self.assertEqual(self.plan["budget_per_arm"], gate["results"][fid]["b_star"])
        self.assertEqual(self.plan["pairs"], gate["results"][fid]["criteria"]["G5"]["required_pairs_N"])
        self.assertEqual(self.plan["gate"]["sha256"], hashlib.sha256((R / self.plan["gate"]["path"]).read_bytes()).hexdigest())
        self.assertEqual(self.plan["gate"]["rules_version"], bg.THRESHOLDS["rules_version"])

    def test_record_count_and_split_arithmetic(self):
        n, b = self.plan["pairs"], self.plan["budget_per_arm"]
        self.assertEqual(self.plan["records"]["single_session_total"], 1 + n * 2 * b + n * 2 + 1)
        self.assertEqual(self.plan["records"]["per_pair"], 2 * b + 2)
        self.assertEqual(self.pred["fitness_sequence_length"], n * 2 * b + n * 2)
        self.assertEqual(self.plan["audit_policy"], "all-self-reporting")
        self.assertEqual(self.plan["session_split"]["status"][:12], "UNDETERMINED")
        # the split rule: with a measured rate, whole pairs per session within the two-hour expected span
        s = bp.session_split(9, 600, 2500.0)
        self.assertEqual(s["pairs_per_session_max"], 4)
        self.assertEqual([len(x["pairs"]) for x in s["sessions"]], [4, 4, 1])
        self.assertEqual(s["total_records"], 3 * 2 + 9 * 1202)
        self.assertTrue(all(x["expected_span_s"] <= bp.SESSION_SPAN_MAX_S for x in s["sessions"]))
        s2 = bp.session_split(9, 600, 2807.0)     # the last B1 mapping's observed rate: still 4 per session
        self.assertEqual(s2["pairs_per_session_max"], 4)
        s3 = bp.session_split(9, 600, 500.0)      # a very slow rate: one pair per session, never zero
        self.assertEqual(s3["pairs_per_session_max"], 1)

    def test_seed_exclusion_is_explicit_and_covers_every_archived_set(self):
        excl, sources = bp.frozen_seed_exclusion()
        self.assertEqual(set(sources), set(bp.FROZEN_SEED_SETS))
        self.assertEqual(self.plan["seed_derivation"]["excluded_values_total"], len(excl | set(bs.EXCLUDED_SEEDS)))
        mine = {x for p in self.pred["pairs"] for x in (p["landscape_seed"], p["operator_seed"])}
        self.assertFalse(mine & excl)

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

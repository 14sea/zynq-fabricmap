"""B2 gate: the statistics and one negative per criterion, driven through evaluate()
(docs/b2_architecture.md §7). The gate's numbers over the real engine live in
evidence/b2/gate; here the criteria are exercised on synthetic rows so that every row is
shown to be able to FAIL."""
from __future__ import annotations

import math
import random
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b2_gate as bg  # noqa: E402
import b2_landscape as bl  # noqa: E402


def synthetic_rows(S=200, seed=0, ceiling=160, base=27, a_level=100, gain=None, spread=8):
    """Rows shaped like the gate's: arm A around a_level, B/C/Q arms above it by the given
    gains (per q), D / E at A. gain: dict arm -> mean gain at every grid budget."""
    rng = random.Random(seed)
    gain = gain or {"B": 12, "C": 12, "D": 0, "E": 0, "Q25": 9, "Q50": 6, "Q75": 3}
    rows = []
    for r in range(S):
        a = [min(ceiling, a_level + rng.randint(-spread, spread)) for _ in bg.GRID]
        arms = {"A": {"at_grid": a, "champion_holdout": 0, "column_moves": 0, "mapped_bits_in_train": 0}}
        for arm in bg.ARMS[1:]:
            g = gain[arm]
            vals = [min(ceiling, a_level + g + rng.randint(-spread, spread)) for _ in range(len(bg.GRID))]
            arms[arm] = {"at_grid": vals, "champion_holdout": 0, "column_moves": 0, "mapped_bits_in_train": 0}
        rows.append({"r": r, "landscape_seed": r, "operator_seed": r, "base_fit": base, "arms": arms})
    return rows


class Statistics(unittest.TestCase):
    def test_sign_test(self):
        self.assertAlmostEqual(bg.sign_test_p([1] * 10)[0], 1 / 1024)
        self.assertEqual(bg.sign_test_p([0, 0, 0]), (1.0, 0, 0, 3))
        p, pos, neg, ties = bg.sign_test_p([1, 1, -1, 0])
        self.assertEqual((pos, neg, ties), (2, 1, 1))
        self.assertAlmostEqual(p, 0.5)

    def test_percentile_and_cohen(self):
        self.assertEqual(bg.percentile([1, 2, 3, 4, 5], 50), 3)
        self.assertEqual(bg.percentile([1, 2, 3, 4, 5], 100), 5)
        self.assertAlmostEqual(bg.cohen_d([1, 1, 1, 1]), math.inf)
        self.assertAlmostEqual(bg.cohen_d([2, 0, 2, 0]), 1 / math.sqrt(4 / 3))

    def test_required_pairs_grows_with_a_smaller_effect(self):
        strong = [3] * 90 + [-1] * 10
        weak = [1] * 60 + [-1] * 40
        n_strong, _ = bg.required_pairs(strong, 0.05, 0.9, 300, 1, 8, 100)
        n_weak, _ = bg.required_pairs(weak, 0.05, 0.9, 300, 1, 8, 100)
        self.assertIsNotNone(n_strong)
        self.assertTrue(n_weak is None or n_weak > n_strong)


class Criteria(unittest.TestCase):
    def test_pass(self):
        res = bg.evaluate("F2", synthetic_rows())
        self.assertTrue(res["pass"], {k: v for k, v in res["criteria"].items() if not v["pass"]})
        self.assertEqual(res["b_star"], 100)

    def test_G1_saturation_fails(self):
        rows = synthetic_rows(a_level=150, gain={"B": 20, "C": 20, "D": 0, "E": 0, "Q25": 15, "Q50": 10, "Q75": 5})
        res = bg.evaluate("F2", rows)
        self.assertFalse(res["criteria"]["G1"]["pass"])
        self.assertFalse(res["pass"])

    def test_G1_random_arm_must_move(self):
        rows = synthetic_rows(base=100, spread=0)
        self.assertFalse(bg.evaluate("F2", rows)["criteria"]["G1"]["pass"])

    def test_G2_sign_locked_fails(self):
        rows = synthetic_rows(spread=0)     # every delta exactly +20: P(delta<0) = 0
        res = bg.evaluate("F2", rows)
        self.assertFalse(res["criteria"]["G2"]["pass"])
        self.assertFalse(res["criteria"]["G6"]["pass"])   # var = 0: the round-1' tie

    def test_G3_shuffled_profits_fails(self):
        rows = synthetic_rows(gain={"B": 20, "C": 20, "D": 10, "E": 0, "Q25": 15, "Q50": 10, "Q75": 5})
        self.assertFalse(bg.evaluate("F2", rows)["criteria"]["G3"]["pass"])

    def test_G4_oracle_solves_or_self_below_oracle_fails(self):
        rows = synthetic_rows(a_level=130, gain={"B": 25, "C": 25, "D": 0, "E": 0, "Q25": 15, "Q50": 10, "Q75": 5})
        self.assertFalse(bg.evaluate("F2", rows)["criteria"]["G4"]["pass"])
        rows = synthetic_rows(gain={"B": 10, "C": 20, "D": 0, "E": 0, "Q25": 8, "Q50": 6, "Q75": 3})
        self.assertFalse(bg.evaluate("F2", rows)["criteria"]["G4"]["pass"])

    def test_G5_small_effect_fails(self):
        rows = synthetic_rows(gain={"B": 2, "C": 2, "D": 0, "E": 0, "Q25": 1, "Q50": 1, "Q75": 0}, spread=6)
        self.assertFalse(bg.evaluate("F2", rows)["criteria"]["G5"]["pass"])

    def test_G5_session_budget_fails(self):
        old = bg.THRESHOLDS["G5_session_evals_max"]
        try:
            bg.THRESHOLDS["G5_session_evals_max"] = 100
            self.assertFalse(bg.evaluate("F2", synthetic_rows())["criteria"]["G5"]["pass"])
        finally:
            bg.THRESHOLDS["G5_session_evals_max"] = old

    def test_G6_too_few_seeds_fails(self):
        self.assertFalse(bg.evaluate("F2", synthetic_rows(S=50))["criteria"]["G6"]["pass"])

    def test_G7_dose_response_fails(self):
        rows = synthetic_rows(gain={"B": 20, "C": 20, "D": 0, "E": 0, "Q25": 5, "Q50": 15, "Q75": 5})
        self.assertFalse(bg.evaluate("F2", rows)["criteria"]["G7"]["pass"])
        rows = synthetic_rows(gain={"B": 20, "C": 20, "D": 0, "E": 0, "Q25": 19, "Q50": 18, "Q75": 17})
        self.assertFalse(bg.evaluate("F2", rows)["criteria"]["G7"]["pass"])

    def test_G8_lut_membership_profits_fails(self):
        rows = synthetic_rows(gain={"B": 20, "C": 20, "D": 0, "E": 10, "Q25": 15, "Q50": 10, "Q75": 5})
        self.assertFalse(bg.evaluate("F2", rows)["criteria"]["G8"]["pass"])

    def test_budget_rule_unreachable(self):
        rows = synthetic_rows(a_level=30, gain={"B": 5, "C": 5, "D": 0, "E": 0, "Q25": 4, "Q50": 3, "Q75": 1})
        res = bg.evaluate("F2", rows)
        self.assertIsNone(res["b_star"])
        self.assertFalse(res["pass"])

    def test_thresholds_are_the_architecture_documents(self):
        text = (R / "docs/b2_architecture.md").read_text()
        for needle in ("60 %", "95th percentile", "10 %", "90 %", "0.8", "6 000", "S = 200", "25 %", "½ · arm B"):
            self.assertIn(needle, text, needle)
        self.assertEqual(bg.THRESHOLDS["budget_rule_oracle_median_fraction"], 0.60)
        self.assertEqual(bg.THRESHOLDS["G5_session_evals_max"], 6000)
        self.assertEqual(bg.SEEDS_DEFAULT, 200)
        self.assertEqual(bg.GRID, (100, 200, 300, 400, 600, 800, 1000, 1500, 2000))
        self.assertEqual(bl.FITNESS_IDS, ("F2", "F1", "F3"))


if __name__ == "__main__":
    unittest.main()

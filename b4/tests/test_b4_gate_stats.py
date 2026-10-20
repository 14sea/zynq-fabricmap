"""b4/host/b4_gate_stats.py — the statistics copied from host/b2_gate.py: compared BY IMPORT of the pinned original (read-only;
B4 code never imports it), and held to hand values: the sign test's direction, ties excluded from n, all ties -> p = 1,
the interpolated percentile at its edges, Cohen's d at +inf and at a single value, the discrete bootstrap, the complete
ascending scan with and without a solution, the chunked scan equal to the unchunked one, the JSON encoding of a non-finite
statistic. No skip."""
from __future__ import annotations

import inspect
import json
import math
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host", R / "host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_gate_stats as gs  # noqa: E402
import b2_gate as original  # noqa: E402  (the pinned original, read-only, for the comparison only)
from b4_deadline import StopWork  # noqa: E402


class TheCopy(unittest.TestCase):
    def test_the_source_text_of_every_copied_function_is_the_original_s(self):
        for name in gs.COPIED:
            self.assertEqual(inspect.getsource(getattr(gs, name)), inspect.getsource(getattr(original, name)), name)

    def test_the_module_imports_no_pinned_module(self):
        text = (R / "b4/host/b4_gate_stats.py").read_text()
        for bad in ("import b2_gate", "import b1_", "import b3_", "from b2_", "from host"):
            self.assertNotIn(bad, text)


class SignTest(unittest.TestCase):
    def test_by_hand(self):
        self.assertEqual(gs.sign_test_p([1, 1, -1]), (0.5, 2, 1, 0), "C(3,2)+C(3,3) over 8")
        self.assertEqual(gs.sign_test_p([2, 0, 0, -1, 3]), (0.5, 2, 1, 2), "ties excluded from n, counted")
        self.assertEqual(gs.sign_test_p([0, 0, 0]), (1.0, 0, 0, 3), "all ties: p = 1, no evidence either way")
        self.assertEqual(gs.sign_test_p([]), (1.0, 0, 0, 0))
        self.assertEqual(gs.sign_test_p([-1, -1, -1]), (1.0, 0, 3, 0), "the direction: negatives never reject")
        self.assertEqual(gs.sign_test_p([1] * 8)[0], 1 / 256)
        self.assertAlmostEqual(gs.sign_test_p([1, 1, 1, 1, -1])[0], 6 / 32)

    def test_conditional_form(self):
        p_with_ties, *_ = gs.sign_test_p([1, 1, 1, 0, 0, 0, 0, 0])
        p_without, *_ = gs.sign_test_p([1, 1, 1])
        self.assertEqual(p_with_ties, p_without, "H1 is P(Δ > 0 | Δ ≠ 0) > 1/2: ties do not dilute n")


class Percentile(unittest.TestCase):
    def test_by_hand_at_the_edges(self):
        self.assertAlmostEqual(gs.percentile([1, 2, 3, 4], 95), 3.85)
        self.assertEqual(gs.percentile([4, 1, 3, 2], 0), 1)
        self.assertEqual(gs.percentile([4, 1, 3, 2], 100), 4)
        self.assertEqual(gs.percentile([7], 50), 7)
        self.assertAlmostEqual(gs.percentile([10, 20], 50), 15)
        with self.assertRaises(ValueError):
            gs.percentile([], 50)
        self.assertEqual(gs.median([3, 1, 2]), 2)
        self.assertEqual(gs.mean([1, 2, 3, 6]), 3.0)


class CohenD(unittest.TestCase):
    def test_by_hand_including_infinity(self):
        self.assertAlmostEqual(gs.cohen_d([1, 2, 3]), 2.0)
        self.assertEqual(gs.cohen_d([1, 1, 1]), math.inf, "all equal and positive: +inf, legitimate")
        self.assertEqual(gs.cohen_d([0, 0]), 0.0)
        self.assertEqual(gs.cohen_d([-2, -2]), 0.0, "all equal and not positive: 0.0 (the original's rule)")
        self.assertEqual(gs.cohen_d([5]), 0.0)
        self.assertAlmostEqual(gs.cohen_d([1, -1]), 0.0)

    def test_encoding_for_json(self):
        self.assertEqual(gs.encode_stat(math.inf), {"value": None, "special": "+inf"})
        self.assertEqual(gs.encode_stat(-math.inf), {"value": None, "special": "-inf"})
        self.assertEqual(gs.encode_stat(float("nan")), {"value": None, "special": "nan"})
        self.assertEqual(gs.encode_stat(2.5), {"value": 2.5, "special": None})
        self.assertEqual(gs.encode_stat(3), {"value": 3, "special": None})
        self.assertEqual(gs.encode_stat(None), {"value": None, "special": "none"})
        with self.assertRaises(ValueError):
            gs.encode_stat(True)
        with self.assertRaises(ValueError):
            json.dumps({"d": math.inf}, allow_nan=False)
        json.dumps({"d": gs.encode_stat(math.inf)}, allow_nan=False)
        self.assertEqual(gs.finite_findings({"a": [1.0, {"b": math.inf}]}), ["$.a[1].b: inf is not finite; encode it with encode_stat"])
        self.assertEqual(gs.finite_findings({"a": [1, 2.5, None, "x"]}), [])


class Bootstrap(unittest.TestCase):
    def test_equal_to_the_original_and_deterministic(self):
        deltas = [3, 1, -1, 2, 0, 4, -2, 1, 1, 2, 0, 3]
        for n, seed in ((8, 1 + 8), (10, 7), (12, 1 + 12)):
            a = gs.bootstrap_reject_rate(deltas, n, 0.05, 200, seed)
            self.assertEqual(a, original.bootstrap_reject_rate(deltas, n, 0.05, 200, seed))
            self.assertEqual(a, gs.bootstrap_reject_rate(deltas, n, 0.05, 200, seed), "same seed, same rate")
        self.assertEqual(gs.bootstrap_reject_rate([1] * 5, 8, 0.05, 50, 7), 1.0, "all positive: every resample rejects (p = 1/256)")
        self.assertEqual(gs.bootstrap_reject_rate([0] * 5, 8, 0.05, 50, 7), 0.0, "all ties: p = 1, never rejects")

    def test_required_pairs_the_complete_ascending_scan(self):
        self.assertEqual(gs.required_pairs([1] * 10, 0.05, 0.9, 100, 1, 8, 20), (8, 1.0))
        self.assertEqual(gs.required_pairs([0] * 10, 0.05, 0.9, 100, 1, 8, 12), (None, 0.0), "no N: an ordinary result, not an error")
        deltas = [3, 1, -1, 2, 0, 4, -2, 1, 1, 2, 0, 3]
        self.assertEqual(gs.required_pairs(deltas, 0.05, 0.9, 300, 1, 8, 40), original.required_pairs(deltas, 0.05, 0.9, 300, 1, 8, 40))

    def test_the_chunked_scan_equals_the_unchunked_one_and_stops_between_n(self):
        deltas = [3, 1, -1, 2, 0, 4, -2, 1, 1, 2, 0, 3]
        n, last = gs.required_pairs(deltas, 0.05, 0.9, 300, 1, 8, 40)
        calls = {"n": 0}

        def never():
            calls["n"] += 1
        n2, last2, rec = gs.required_pairs_scan(deltas, 0.05, 0.9, 300, 1, 8, 40, check=never)
        self.assertEqual((n2, last2, rec["complete"]), (n, last, True))
        self.assertEqual(calls["n"], len(rec["scanned"]), "one check before each N")
        self.assertEqual(rec["scanned"][-1], [n, last])
        self.assertEqual(gs.required_pairs_scan(deltas, 0.05, 0.9, 300, 1, 8, 40)[:2], (n, last), "no check: identical")
        budget = {"left": 3}

        def three():
            if budget["left"] == 0:
                raise StopWork("expired")
            budget["left"] -= 1
        n3, last3, rec3 = gs.required_pairs_scan(deltas, 0.05, 0.9, 300, 1, 8, 40, check=three)
        self.assertEqual((n3, rec3["complete"], rec3["stopped_before_n"], len(rec3["scanned"])), (None, False, 11, 3))
        self.assertEqual(rec3["scanned"], rec["scanned"][:3], "the chunks computed are the unchunked values")


if __name__ == "__main__":
    unittest.main()

"""b4/host/b4_stats.py — the four-corner index as a pure computation: an additive fitness gives I = 0 on every pair, an
interacting one does not; an illegal corner makes the pair not comparable with the corner named; the four per-seed
outcomes with tau a parameter (no default), tau = 0 leaving the nonzero-below-threshold class empty by definition;
every seed in the denominator over S. No skip."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_ff_model as fm  # noqa: E402
import b4_stats as st  # noqa: E402


def additive(g: int) -> int:
    return sum((g >> i) & 1 for i in range(8)) * 3


def interacting(g: int) -> int:
    return additive(g) + (5 if (g & 0b11) == 0b11 else 0)


def illegal_when_bit2_set_without_bit3(g: int) -> int:
    if (g >> 2) & 1 and not (g >> 3) & 1:
        raise fm.DomainRefusal()
    return additive(g)


class FourCorner(unittest.TestCase):
    def test_additive_is_zero_everywhere_and_interaction_shows(self):
        for a in range(8):
            for b in range(a + 1, 8):
                self.assertEqual(st.four_corner(additive, 0b1010, a, b)["index"], 0)
        r = st.four_corner(interacting, 0b11111100, 0, 1)
        self.assertEqual((r["comparable"], r["index"], r["values"]), (True, 5, {"00": 18, "01": 21, "10": 21, "11": 29}))
        self.assertEqual(st.four_corner(interacting, 0, 2, 5)["index"], 0, "only the pair (0, 1) interacts")

    def test_the_corners_differ_in_a_and_b_only(self):
        seen = []
        st.four_corner(lambda g: seen.append(g) or 0, 0b11111111, 1, 6)
        self.assertEqual(sorted(seen), sorted([0b10111101, 0b10111111, 0b11111101, 0b11111111]))

    def test_an_illegal_corner_is_not_comparable_and_named(self):
        r = st.four_corner(illegal_when_bit2_set_without_bit3, 0, 2, 3)
        self.assertEqual((r["comparable"], r["illegal_corners"], r["index"]), (False, ["10"], None))
        r = st.four_corner(illegal_when_bit2_set_without_bit3, 0b100, 0, 1)     # bit 2 set, bit 3 clear in every corner
        self.assertEqual((r["comparable"], r["illegal_corners"]), (False, ["00", "01", "10", "11"]))
        with self.assertRaises(ValueError):
            st.four_corner(additive, 0, 3, 3)

    def test_the_four_outcomes_and_the_denominator(self):
        self.assertEqual(st.classify(None, 0.5), st.NOT_ASSESSABLE)
        self.assertEqual(st.classify(0, 0.5), st.NO_INTERACTION_SEEN)
        self.assertEqual(st.classify(0.3, 0.5), st.NONZERO_BELOW_THRESHOLD)
        self.assertEqual(st.classify(0.5, 0.5), st.NONZERO_BELOW_THRESHOLD, "at the threshold is not above it")
        self.assertEqual(st.classify(0.7, 0.5), st.INTERACTING)
        self.assertEqual(st.classify(0.3, 0), st.INTERACTING, "with tau = 0 anything nonzero interacts")
        for bad in (-1, None, True):
            with self.assertRaises(ValueError):
                st.classify(1, bad)
        s = st.summarise([None, 0, 0.3, 0.7, 2], 0.5, 5)
        self.assertEqual(s["counts"], {st.INTERACTING: 2, st.NONZERO_BELOW_THRESHOLD: 1, st.NO_INTERACTION_SEEN: 1, st.NOT_ASSESSABLE: 1})
        self.assertEqual(s["fraction_interacting_over_S"], 2 / 5, "the not-assessable seed stays in the denominator")
        s0 = st.summarise([None, 0, 0.3, 0.7, 2], 0, 5)
        self.assertEqual(s0["counts"][st.NONZERO_BELOW_THRESHOLD], 0)
        with self.assertRaises(ValueError):
            st.summarise([0, 0], 0.5, 3)
        m, counts = st.seed_max([st.four_corner(interacting, 0b11111100, 0, 1), st.four_corner(illegal_when_bit2_set_without_bit3, 0, 2, 3)])
        self.assertEqual((m, counts["comparable_pairs"], counts["not_comparable_pairs"], counts["illegal_corners"]), (5, 1, 1, ["10"]))
        self.assertEqual(st.seed_max([st.four_corner(illegal_when_bit2_set_without_bit3, 0, 2, 3)])[0], None)


if __name__ == "__main__":
    unittest.main()

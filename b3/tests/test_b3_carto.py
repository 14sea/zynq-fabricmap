"""b3/host/b3_carto.py — the B3 cartographer copy: the frozen reference's own cases (ported), the
state commitment, and step-for-step equivalence with the B2-pinned `host/b3_online.SpecimenCarto`
over a seeded specimen stream (the oracle is imported, never edited)."""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    sys.path.insert(0, str(p))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b3_carto as b3  # noqa: E402
import b3_online as frozen  # noqa: E402  (host/b3_online.py: B2-pinned, the equivalence oracle)

TRUTH = bm.truth_mapping()
P, Q, RR, T, U = (0, 0), (0, 1), (0, 2), (0, 3), (0, 4)


class Ported(unittest.TestCase):
    def test_single_bit_specimen_decodes_directly(self):
        c = b3.SpecimenCarto()
        k, v = TRUTH["mapping"][5]
        self.assertEqual(c.observe([5], [(k, v)]), [5])
        self.assertEqual(c.decoded[5], (k, v))
        self.assertEqual(c.version, 1)

    def test_multi_bit_specimens_narrow_then_decode(self):
        c = b3.SpecimenCarto()
        pa, pb, pd = TRUTH["mapping"][1], TRUTH["mapping"][2], TRUTH["mapping"][3]
        self.assertEqual(c.observe([1, 2], [pa, pb]), [])
        self.assertEqual(sorted(c.observe([1, 3], [pa, pd])), [1, 2, 3])
        self.assertEqual(c.version, 1)

    def test_refusals_are_atomic_and_counted(self):
        c = b3.SpecimenCarto()
        c.observe([0, 2], [P, Q])
        c.observe([1, 3], [RR, T])
        before = c.snapshot()
        self.assertEqual(c.observe([0, 1], [P, U]), [])
        self.assertEqual(c.anomalies, 1)
        self.assertEqual(c.snapshot(), before)
        for moved, delta in (([0, 0], [P, Q]), ([0], [(6, 0)]), ([0], [(0, 64)]), ([0, 1], [P, P]), ([], []), ([999], [P])):
            self.assertEqual(c.observe(moved, delta), [])
            self.assertEqual(c.snapshot(), before)
        self.assertEqual(c.anomalies, 7)

    def test_closure_conflict_is_refused_atomically(self):
        c = b3.SpecimenCarto()
        c.observe([0, 1], [P, Q])
        c.observe([2, 3], [P, Q])
        before = c.snapshot()
        self.assertEqual(c.observe([0], [P]), [])
        self.assertEqual(c.anomalies, 1)
        self.assertEqual(c.snapshot(), before)

    def test_positions_of(self):
        self.assertEqual(b3.positions_of([0b101, 0, 0, 0, 1 << 63, 0]), [(0, 0), (0, 2), (4, 63)])


class Commitment(unittest.TestCase):
    def test_state_text_is_the_documented_projection(self):
        c = b3.SpecimenCarto()
        self.assertEqual(c.state_text(), f"{b3.CARTO_VERSION}|0|0||")
        c.observe([4, 7], [P, Q])                       # narrowed: candidates, nothing decoded
        self.assertEqual(c.state_text(), f"{b3.CARTO_VERSION}|0|0||4:0.0,0.1;7:0.0,0.1")
        c.observe([4], [P])                             # 4 at P (its candidate set intersected to {P}), 7 at Q by exclusion
        self.assertEqual(c.state_text(), f"{b3.CARTO_VERSION}|1|0|4:0:0;7:0:1|4:0.0;7:0.0,0.1")
        self.assertEqual(len(c.state_sha256()), 64)

    def test_equal_states_commit_equally_and_a_refusal_changes_only_the_count(self):
        a, b = b3.SpecimenCarto(), b3.SpecimenCarto()
        for c in (a, b):
            c.observe([1], [TRUTH["mapping"][1]])
        self.assertEqual(a.state_sha256(), b.state_sha256())
        before = a.state_sha256()
        a.observe([1], [Q])                             # contradiction: anomaly only
        self.assertNotEqual(a.state_sha256(), before)
        self.assertTrue(a.state_text().split("|")[2] == "1")


class EquivalenceWithTheFrozenReference(unittest.TestCase):
    """Step for step, the copy and B2's pinned reference decode, refuse and version identically."""

    def test_seeded_specimen_stream(self):
        rng = random.Random(20260917)
        mine, ref = b3.SpecimenCarto(), frozen.SpecimenCarto()
        for step in range(1500):
            k = rng.choice([1, 1, 2, 3, 4])
            moved = rng.sample(range(bc.N), k)
            delta = [TRUTH["mapping"][i] for i in moved]
            r = rng.random()
            if r < 0.05:                                # a wrong delta (contradiction / empty intersection)
                delta[0] = (rng.randrange(6), rng.randrange(64))
            elif r < 0.08:                              # malformed
                delta = delta[:-1]
            a, b = mine.observe(moved, delta), ref.observe(moved, delta)
            self.assertEqual(sorted(a), sorted(b), step)
            self.assertEqual(mine.snapshot(), ref.snapshot(), step)
            self.assertEqual(mine.anomalies, ref.anomalies, step)
        self.assertGreater(mine.anomalies, 0)
        self.assertGreater(len(mine.decoded), 200)


if __name__ == "__main__":
    unittest.main()

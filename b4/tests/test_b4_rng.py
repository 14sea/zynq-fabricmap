"""b4/host/b4_rng.py is a derived copy of host/b1_carto.Rng: behaviourally identical (next32, uniform, sample) over many
seeds — compared here BY IMPORT of the pinned original (read-only; B4 code itself never imports it). No skip."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host", R / "host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_rng  # noqa: E402
import b1_carto as original  # noqa: E402  (the pinned original, read-only, for the comparison only)


class TheCopy(unittest.TestCase):
    def test_sequences_uniform_and_sample_are_identical(self):
        for seed in (0, 1, 7, 11, 0xFFFFFFFF, 981420253, 3776596183):
            a, b = b4_rng.Rng(seed), original.Rng(seed)
            self.assertEqual([a.next32() for _ in range(64)], [b.next32() for _ in range(64)], seed)
            self.assertEqual([a.uniform(n) for n in (2, 3, 8, 21, 255, 1000)], [b.uniform(n) for n in (2, 3, 8, 21, 255, 1000)], seed)
            self.assertEqual(a.sample(list(range(21)), 21), b.sample(list(range(21)), 21), seed)
            self.assertEqual(a.x, b.x)
        self.assertEqual((b4_rng.GOLDEN, b4_rng.MASK64, b4_rng.MASK32), (original.GOLDEN, original.MASK64, original.MASK32))

    def test_the_state_is_the_generator_s_word(self):
        a = b4_rng.Rng(5)
        s0 = a.state(); a.next32()
        self.assertNotEqual(a.state(), s0)


if __name__ == "__main__":
    unittest.main()

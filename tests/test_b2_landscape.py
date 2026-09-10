"""B2 landscape: the universe mask, the public target rule, the train / holdout split and
the fitness family — known answers and invariants (docs/b2_architecture.md §3)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402

TRUTH = bm.truth_mapping()
MASKS = bl.universe_mask(TRUTH)
FAB = bm.Fabric(TRUTH["mapping"])


class Mask(unittest.TestCase):
    def test_292_positions_per_lut_counts(self):
        counts = [bin(m).count("1") for m in MASKS]
        self.assertEqual(counts, [49, 49, 49, 51, 50, 44])
        self.assertEqual(sum(counts), bc.N)

    def test_mask_is_the_readout_of_the_all_ones_genome(self):
        self.assertEqual(FAB((1 << bc.N) - 1), MASKS)


class Split(unittest.TestCase):
    def test_train_is_the_carrier_order_prefix(self):
        c = json.loads(bl.CARRIER_CONSTANTS.read_text())
        self.assertEqual(bl.train_vectors(), [int(x) for x in c["order"][:40]])
        self.assertEqual(bl.holdout_vectors(), [int(x) for x in c["order"][40:]])
        self.assertEqual(sorted(bl.train_vectors() + bl.holdout_vectors()), list(range(64)))

    def test_writable_positions_in_train_columns(self):
        train = sum(1 << v for v in bl.train_vectors())
        self.assertEqual(sum(bin(m & train).count("1") for m in MASKS), 183)

    def test_refuses_foreign_constants(self):
        c = json.loads(bl.CARRIER_CONSTANTS.read_text())
        bad = dict(c, order=list(range(64)), train_count=32)
        with self.assertRaises(ValueError):
            bl.vector_order(bad)


class Target(unittest.TestCase):
    def test_masked_to_the_universe_and_seed_dependent(self):
        t1 = bl.target_tables(1000, MASKS)
        t2 = bl.target_tables(1001, MASKS)
        for k in range(6):
            self.assertEqual(t1[k] & ~MASKS[k], 0)
        self.assertNotEqual(t1, t2)
        self.assertEqual(t1, bl.target_tables(1000, MASKS))

    def test_optimum_is_reachable_and_unique(self):
        for fid in bl.FITNESS_IDS:
            land = bl.Landscape(fid, 4242, masks=MASKS, truth=TRUTH)
            g = land.optimum()
            self.assertEqual(FAB(g), land.target)
            self.assertEqual(land.train_fitness(FAB(g)), land.ceiling)
            self.assertEqual(land.holdout_fitness(FAB(g)), {"F1": 24, "F2": 96, "F3": 192}[fid])
            # flipping any set bit of the optimum leaves the target
            for i in range(bc.N):
                if g >> i & 1:
                    self.assertNotEqual(FAB(g ^ (1 << i)), land.target)
                    break

    def test_target_stream_is_the_instrument_rng(self):
        rng = bc.Rng(77)
        bits = [rng.next32() & 1 for _ in range(6 * 64)]
        t = bl.target_tables(77, MASKS)
        for k in range(6):
            for v in range(64):
                want = bits[k * 64 + v] & (MASKS[k] >> v & 1)
                self.assertEqual(t[k] >> v & 1, want)


class Fitness(unittest.TestCase):
    def test_known_answers_on_the_base(self):
        land = bl.Landscape("F2", 4242, masks=MASKS, truth=TRUTH)
        base = FAB(0)
        # a column with no target ones scores g(0) = 4; the count of such train columns is what F1 says
        f1 = bl.f1_exact_word(base, land.target, land.train)
        f2 = bl.f2_graded_word(base, land.target, land.train)
        ones = [bin(bl.column_word(land.target, v)).count("1") for v in land.train]
        self.assertEqual(f1, sum(1 for d in ones if d == 0))
        self.assertEqual(f2, sum(4 for d in ones if d == 0) + sum(1 for d in ones if d == 1))

    def test_f2_is_not_additive_over_bits(self):
        land = bl.Landscape("F2", 4242, masks=MASKS, truth=TRUTH)
        g = land.optimum()
        # two bits of one column: the loss of flipping both is not the sum of the single losses
        v = next(v for v in land.train if bin(bl.column_word(land.target, v)).count("1") >= 2)
        bits = [i for i in range(bc.N) if TRUTH["mapping"][i][1] == v and g >> i & 1][:2]
        full = land.train_fitness(FAB(g))
        l1 = full - land.train_fitness(FAB(g ^ (1 << bits[0])))
        l2 = full - land.train_fitness(FAB(g ^ (1 << bits[1])))
        l12 = full - land.train_fitness(FAB(g ^ (1 << bits[0]) ^ (1 << bits[1])))
        self.assertEqual((l1, l2, l12), (3, 3, 4))

    def test_f1_is_the_exact_block_count(self):
        land = bl.Landscape("F1", 4242, masks=MASKS, truth=TRUTH)
        g = land.optimum()
        i = next(i for i in range(bc.N) if g >> i & 1 and TRUTH["mapping"][i][1] in land.train)
        self.assertEqual(land.train_fitness(FAB(g ^ (1 << i))), 39)

    def test_f3_trajectory_prefix(self):
        land = bl.Landscape("F3", 4242, masks=MASKS, truth=TRUTH)
        self.assertEqual(land.train_fitness(FAB(land.optimum())), 320)
        # a table equal to the target except at one state reached at step 1 from some start loses steps after it
        self.assertLess(land.train_fitness(FAB(0)), 320)

    def test_ceilings(self):
        self.assertEqual(bl.CEILING, {"F1": 40, "F2": 160, "F3": 320})
        self.assertEqual(bl.FITNESS_IDS, ("F2", "F1", "F3"))


if __name__ == "__main__":
    unittest.main()

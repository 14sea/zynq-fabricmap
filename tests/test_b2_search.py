"""B2 search: the engine and the operators (docs/b2_architecture.md §4–§5) — determinism,
the prefix property, operator invariants, the random-safe endpoint, seeds."""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_search as bs  # noqa: E402

TRUTH = bm.truth_mapping()
MASKS = bl.universe_mask(TRUTH)
FAB = bs.ModelFabric(TRUTH)
TRAIN = bl.train_vectors()
ORACLE = bmaps.oracle_map(TRUTH)
VIEW = bmaps.MapView(ORACLE, TRAIN)
LAND = bl.Landscape("F2", 31337, masks=MASKS, truth=TRUTH)


class Fabric(unittest.TestCase):
    def test_toggle_equals_from_scratch(self):
        r = random.Random(1)
        for _ in range(100):
            g = r.getrandbits(bc.N)
            bits = r.sample(range(bc.N), r.randint(1, 4))
            self.assertEqual(FAB.toggle(FAB(g), bits), FAB(bs.apply_move(g, bits)))


class Operators(unittest.TestCase):
    def test_random_safe_moves(self):
        rng = bc.Rng(5)
        sizes = set()
        for _ in range(500):
            m = bs.random_safe_move(rng)
            self.assertEqual(m, sorted(set(m)))
            self.assertTrue(all(0 <= i < bc.N for i in m))
            sizes.add(len(m))
        self.assertEqual(sizes, {1, 2, 3, 4})

    def test_column_moves_stay_inside_one_train_column(self):
        rng = bc.Rng(6)
        for _ in range(500):
            m = bs.column_move(rng, VIEW)
            cols = {TRUTH["mapping"][i][1] for i in m}
            self.assertEqual(len(cols), 1)
            self.assertIn(cols.pop(), TRAIN)
            self.assertTrue(1 <= len(m) <= bs.KMAX)

    def test_map_guided_is_a_half_mixture(self):
        rng = bc.Rng(7)
        kinds = [bs.map_guided_move(rng, VIEW)[1] for _ in range(2000)]
        frac = kinds.count("column") / len(kinds)
        self.assertTrue(0.45 < frac < 0.55, frac)

    def test_empty_map_is_the_random_safe_endpoint(self):
        empty = bmaps.MapView(None, TRAIN)
        a = bs.run(bs.ARM_RANDOM_SAFE, LAND, None, 99, 400, FAB)
        b = bs.run(bs.ARM_MAP_GUIDED, LAND, empty, 99, 400, FAB)
        self.assertEqual(a.best_trace, b.best_trace)
        self.assertEqual(a.champion.genome, b.champion.genome)
        self.assertEqual(b.column_moves, 0)


class Engine(unittest.TestCase):
    def test_deterministic(self):
        x = bs.run(bs.ARM_MAP_GUIDED, LAND, VIEW, 11, 300, FAB, log_moves=True)
        y = bs.run(bs.ARM_MAP_GUIDED, LAND, VIEW, 11, 300, FAB, log_moves=True)
        self.assertEqual(x.best_trace, y.best_trace)
        self.assertEqual(x.moves, y.moves)
        self.assertEqual(x.champion.genome, y.champion.genome)

    def test_prefix_property(self):
        short = bs.run(bs.ARM_MAP_GUIDED, LAND, VIEW, 11, 300, FAB)
        long = bs.run(bs.ARM_MAP_GUIDED, LAND, VIEW, 11, 1000, FAB)
        self.assertEqual(long.best_trace[:300], short.best_trace)

    def test_trace_monotone_and_champion_is_the_best(self):
        r = bs.run(bs.ARM_RANDOM_SAFE, LAND, None, 12, 500, FAB)
        self.assertEqual(len(r.best_trace), 500)
        self.assertTrue(all(a <= b for a, b in zip(r.best_trace, r.best_trace[1:])))
        self.assertEqual(r.champion.fit, r.best_trace[-1])
        self.assertEqual(r.champion.fit, max(r.population_fit))
        self.assertEqual(len(r.population_fit), bs.MU)
        self.assertEqual(LAND.train_fitness(FAB(r.champion.genome)), r.champion.fit)
        self.assertEqual(LAND.holdout_fitness(FAB(r.champion.genome)), r.champion_holdout)

    def test_every_child_is_one_move_from_a_parent(self):
        r = bs.run(bs.ARM_MAP_GUIDED, LAND, VIEW, 13, 64, FAB, log_moves=True)
        self.assertEqual(len(r.moves), 64)
        for m in r.moves:
            self.assertTrue(1 <= len(m["bits"]) <= bs.KMAX)
            self.assertTrue(0 <= m["parent"] < bs.MU)
            self.assertIn(m["kind"], ("random", "column"))

    def test_budget_zero_is_the_base(self):
        r = bs.run(bs.ARM_RANDOM_SAFE, LAND, None, 1, 0, FAB)
        self.assertEqual(r.best_trace, [])
        self.assertEqual(r.champion.genome, 0)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            bs.run("other", LAND, None, 1, 10, FAB)
        with self.assertRaises(ValueError):
            bs.run(bs.ARM_MAP_GUIDED, LAND, None, 1, 10, FAB)


class Seeds(unittest.TestCase):
    def test_pair_seeds_distinct_excluded_and_reproducible(self):
        s = bs.pair_seeds(bs.master_seed("b2-gate", "deadbeef"), 50)
        flat = [x for p in s for x in p]
        self.assertEqual(len(set(flat)), 100)
        self.assertFalse(set(flat) & bs.EXCLUDED_SEEDS)
        self.assertEqual(s, bs.pair_seeds(bs.master_seed("b2-gate", "deadbeef"), 50))
        self.assertNotEqual(s, bs.pair_seeds(bs.master_seed("b2-session", "deadbeef"), 50))
        self.assertIn(1123460948, bs.EXCLUDED_SEEDS)     # B1's master seed

    def test_gate_and_session_labels_are_disjoint(self):
        g = {x for p in bs.pair_seeds(bs.master_seed("b2-gate", "c0ffee"), 200) for x in p}
        s = {x for p in bs.pair_seeds(bs.master_seed("b2-session", "c0ffee"), 50) for x in p}
        self.assertFalse(g & s)


if __name__ == "__main__":
    unittest.main()

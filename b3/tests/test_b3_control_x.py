"""b3/host/b3_control_x.py — control X exactly as docs/b3_architecture.md v0.2.3 §9 states it: the
seed rule, the PRNG, rejection sampling from the identity on one continuing stream, the digest, the
delta mapping, and the shadow-cartographer isomorphism (positive and negative)."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    sys.path.insert(0, str(p))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_carto as carto_mod  # noqa: E402
import b3_control_x as cx  # noqa: E402
import b3_online_arm as oa  # noqa: E402

TRUTH = bm.truth_mapping()
MASKS = bl.universe_mask(TRUTH)
FAB = bs.ModelFabric(TRUTH)
LAND = bl.Landscape("F1", 2468, masks=MASKS, truth=TRUTH)


class Derangement(unittest.TestCase):
    def test_seed_rule_is_the_b_line_rule(self):
        commit = bp.INSTRUMENT_COMMIT
        want = int.from_bytes(hashlib.sha256(f"b3-gate-x|{commit}".encode()).digest()[:4], "big")
        self.assertEqual(cx.seed_x(commit), want)
        self.assertEqual(cx.seed_x(commit), bs.master_seed("b3-gate-x", commit))

    def test_a_permutation_without_fixed_points_deterministic(self):
        a, b = cx.derangement(12345), cx.derangement(12345)
        self.assertEqual(a, b)
        self.assertEqual(sorted(a), list(range(cx.N_POS)))
        self.assertTrue(all(a[i] != i for i in range(cx.N_POS)))
        self.assertNotEqual(cx.derangement(12346), a)
        self.assertEqual(cx.permutation_sha256(a), hashlib.sha256(json.dumps(a, separators=(",", ":")).encode()).hexdigest())

    def test_rejection_restarts_from_the_identity_on_the_continuing_stream(self):
        """For the pinned instrument commit the first attempt has fixed points, so the rejection path is
        exercised; the other reading of the old text (re-shuffling the previous attempt's array) gives a
        different permutation — the text now excludes it. No digest is asserted (the gate report records it)."""
        seed = cx.seed_x(bp.INSTRUMENT_COMMIT)
        log = []
        pi = cx.derangement(seed, log=log)
        self.assertGreater(len(log), 1, "the first attempt had no fixed point: the rejection path was not exercised")
        self.assertTrue(log[0])
        self.assertEqual(log[-1], [])
        # the excluded reading: continue from the previous attempt's array
        rng = bc.Rng(seed)
        p = list(range(cx.N_POS))
        while True:
            for i in range(cx.N_POS - 1, 0, -1):
                j = rng.uniform(i + 1)
                p[i], p[j] = p[j], p[i]
            if all(p[i] != i for i in range(cx.N_POS)):
                break
        self.assertNotEqual(p, pi)
        # the documented reading, re-derived here independently
        rng = bc.Rng(seed)
        while True:
            q = list(range(cx.N_POS))
            for i in range(cx.N_POS - 1, 0, -1):
                j = rng.uniform(i + 1)
                q[i], q[j] = q[j], q[i]
            if all(q[i] != i for i in range(cx.N_POS)):
                break
        self.assertEqual(q, pi)

    def test_map_delta_touches_positions_only(self):
        pi = cx.derangement(7)
        delta = [(0, 0), (5, 63)]
        mapped = cx.map_delta(delta, pi)
        self.assertEqual(mapped, [cx.index_pos(pi[0]), cx.index_pos(pi[383])])
        self.assertNotEqual(mapped, delta)


class Shadow(unittest.TestCase):
    def test_x_is_isomorphic_to_the_shadow_under_pi_and_wrong_everywhere(self):
        pi = cx.derangement(cx.seed_x(bp.INSTRUMENT_COMMIT))
        res = oa.run_online(LAND, 9, 400, FAB, delta_perm=pi, shadow=True)
        self.assertEqual(res.shadow_findings, [])
        self.assertEqual(res.anomalies, 0)                                  # self-consistent
        self.assertGreater(len(res.carto.decoded), 50)                       # it grows
        wrong = sum(1 for i, pos in res.carto.decoded.items() if tuple(TRUTH["mapping"][i]) != pos)
        self.assertEqual(wrong, len(res.carto.decoded))                     # and names the wrong position for every address
        self.assertEqual(res.perm_sha256, cx.permutation_sha256(pi))
        o = oa.run_online(LAND, 9, 400, FAB)
        self.assertNotEqual(o.best_trace, res.best_trace)                   # the scrambled map drives X's own moves

    def test_a_wrong_isomorphism_is_named(self):
        pi = cx.derangement(1)
        other = cx.derangement(2)
        x, shadow = carto_mod.SpecimenCarto(), carto_mod.SpecimenCarto()
        moved = [3]
        delta = [TRUTH["mapping"][3]]
        x.observe(moved, cx.map_delta(delta, pi))
        shadow.observe(moved, delta)
        self.assertEqual(cx.isomorphism_findings(x, shadow, pi), [])
        self.assertTrue(cx.isomorphism_findings(x, shadow, other))
        x.observe([3], [(0, 0)])                                             # an anomaly on X only
        self.assertTrue(any("anomalies" in f for f in cx.isomorphism_findings(x, shadow, pi)))


if __name__ == "__main__":
    unittest.main()

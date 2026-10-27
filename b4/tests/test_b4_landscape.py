"""b4/host/b4_landscape.py — the public task, task-v0.3 (docs/b4_architecture.md section 7.2; the owner's ruling of 2026-10-27 on the
slice-wide CE / SR stimulus: one control value per set step, CE high with probability 1/2, SR with 1/4, independent, each broadcast as
0xFF / 0x00; d per element; the shape held by `stimulus_findings`; the carrier's STEP_IN mapping and `realisable` never refusing it) and,
unchanged from task-v0.2 (section 7.1; the owner's rulings of 2026-10-20):
the public parts from the landscape seed alone (the module imports neither the mapping nor the hypothesis), deterministic; the
PLANTED flip-flop configuration by the fixed rule — the storage_kind bit 0, the other 20 bits drawn ONCE, the all-zero base
included, nothing redrawn; the targets read from a planted trace (a None cell is a TargetRefusal, never a narrowed mask); the
PublicTask carries no seed and no planted genome and its digest covers the target's source commitment; the scoring unchanged
(a 0/1 match counts, None scores nothing and is counted, the ceiling never moves, None == None is not a hit). No skip."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_execution as ex  # noqa: E402
import b4_landscape as bl  # noqa: E402
import b4_ff_model as fm  # noqa: E402
from b4_rng import Rng  # noqa: E402

ADDR = tuple(f"0x{0x400a00 + i:08x}/1/{i}" for i in range(21))     # any 21 address strings: the generator never reads them
SK = 10                                                              # a storage_kind bit index for the hand tests (the real one is the mapping's, read by the harness)


def hand_task(seed: int = 7, sk: int = SK, grids=None) -> ex.PublicTask:
    """A task from the public parts and a hand-made planted trace: the target is the grid's cells (all 0 unless given)."""
    parts = bl.public_parts(seed)
    g_s = grids[0] if grids else [[0] * 8 for _ in parts["stimulus"]]
    g_h = grids[1] if grids else [[0] * 8 for _ in parts["holdout_stimulus"]]
    return bl.make_task(ADDR, parts, bl.targets_from_grid(g_s, parts["mask"]), bl.targets_from_grid(g_h, parts["holdout_mask"]), "a" * 64)


class TheGenerator(unittest.TestCase):
    def test_it_reads_no_mapping_and_no_hypothesis(self):
        """By the code, not the prose: the module's imports and attribute names (an AST scan, docstrings excluded)."""
        import ast
        tree = ast.parse((R / "b4/host/b4_landscape.py").read_text())
        imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | \
                   {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        for forbidden in ("b4_ff_mapping", "b4_ff_hypothesis", "b4_ff_model", "b4_target"):
            self.assertNotIn(forbidden, imported, f"the task generator must not import {forbidden}")
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        for forbidden in ("diagnose", "decode", "step_diagnostics", "entries", "address_of", "effect", "observe"):
            self.assertNotIn(forbidden, attrs, f"the task generator must not touch {forbidden}")

    def test_the_public_parts_are_deterministic_and_shaped(self):
        p1, p2 = bl.public_parts(7), bl.public_parts(7)
        self.assertEqual(p1, p2)
        self.assertNotEqual(p1["stimulus"], bl.public_parts(8)["stimulus"])
        self.assertEqual(p1["stimulus"][0], {"kind": "init"})
        self.assertEqual(len(p1["stimulus"]), 1 + bl.K_DEFAULT + bl.LEVEL_STEPS)
        clocks = [s["clock"] for s in p1["stimulus"][1:1 + bl.K_DEFAULT]]
        self.assertEqual(clocks, [1, 0] * (bl.K_DEFAULT // 2), "the clock steps alternate: K edges")
        for s in p1["stimulus"][1:]:
            fm.validate_step(s)
        self.assertEqual(len(p1["mask"]), (len(p1["stimulus"]) - 1) * 8); self.assertEqual(set(p1["weights"]), {1}); self.assertEqual(sum(p1["weights"]), 64)
        self.assertNotEqual(p1["holdout_stimulus"], p1["stimulus"]); self.assertEqual(len(p1["holdout_stimulus"]), 1 + bl.K_HOLDOUT + bl.LEVEL_STEPS); self.assertEqual(sum(p1["holdout_weights"]), 80)
        self.assertNotIn("target", p1, "the public parts carry no target: the target is the planted configuration's observed trace")
        for bad in (-1, True, 2 ** 32, "7"):
            with self.assertRaises(ValueError):
                bl.public_parts(bad)

    def test_the_planted_rule_by_hand(self):
        """T-i: storage_kind bit 0; the other 20 bits from the first uniform(1 << 20) of Rng((seed ^ SALT_TARGET) & 0xffffffff), onto the
        non-storage_kind bits in address order; one draw; deterministic; the base not excluded."""
        for seed in (7, 8, 3, 5, 0, 0xFFFFFFFF):
            draw = Rng((seed ^ bl.SALT_TARGET) & 0xFFFFFFFF).uniform(1 << 20)
            free = [b for b in range(21) if b != SK]
            want = sum(((draw >> i) & 1) << b for i, b in enumerate(free))
            g = bl.planted_genome(seed, SK)
            self.assertEqual(g, want, seed)
            self.assertEqual((g >> SK) & 1, 0, "a flip-flop configuration")
            self.assertEqual(g, bl.planted_genome(seed, SK), "deterministic")
            self.assertLess(g, 1 << 21)
        self.assertNotEqual(bl.planted_genome(7, SK), bl.planted_genome(7, 3), "the storage_kind bit decides the mapping of the draw")
        self.assertEqual(bl.SALT_TARGET, 0x54415247)
        self.assertIn("0x54415247", bl.PLANTED_RULE); self.assertIn("nothing redrawn", bl.PLANTED_RULE)
        # the base is a possible outcome and is not excluded: the generator does not redraw for it
        import unittest.mock as mock
        with mock.patch.object(bl, "Rng", lambda s: type("Z", (), {"uniform": lambda self, n: 0})()):
            self.assertEqual(bl.planted_genome(7, SK), 0, "a zero draw IS the base: kept, never redrawn")
        for bad in ((7, -1), (7, 21), (7, True), (-1, SK)):
            with self.assertRaises(ValueError):
                bl.planted_genome(*bad)

    def test_the_targets_are_read_from_the_planted_trace_and_a_none_is_refused(self):
        parts = bl.public_parts(7)
        steps = len(parts["stimulus"])
        grid = [[(s * 8 + e) % 2 for e in range(8)] for s in range(steps)]
        t = bl.targets_from_grid(grid, parts["mask"])
        self.assertEqual(len(t), len(parts["mask"]))
        self.assertEqual(list(t), [grid[s][e] for (s, e) in parts["mask"]])
        bad = [row[:] for row in grid]; bad[2][3] = None
        with self.assertRaises(bl.TargetRefusal) as cm:
            bl.targets_from_grid(bad, parts["mask"])
        self.assertIn("None", str(cm.exception)); self.assertIn("not narrowed", str(cm.exception))
        bad = [row[:] for row in grid]; bad[1][0] = 2
        with self.assertRaises(bl.TargetRefusal):
            bl.targets_from_grid(bad, parts["mask"])
        bad = [row[:] for row in grid]; bad[1][0] = True
        with self.assertRaises(bl.TargetRefusal):
            bl.targets_from_grid(bad, parts["mask"])
        with self.assertRaises(bl.TargetRefusal):
            bl.targets_from_grid(grid[:-1], parts["mask"])
        with self.assertRaises(bl.TargetRefusal):
            bl.targets_from_grid("x", parts["mask"])

    def test_the_public_task_carries_no_seed_and_its_digest_covers_the_source_commitment(self):
        t = hand_task(7)
        self.assertFalse(hasattr(t, "seed"), "the executing side's input carries no landscape seed (H)")
        self.assertEqual((t.version, t.base_genome, t.addresses, t.ceiling, t.holdout_ceiling), (bl.TASK_VERSION, 0, ADDR, 64, 80))
        self.assertEqual(t.digest(), hand_task(7).digest())
        parts = bl.public_parts(7)
        other = bl.make_task(ADDR, parts, t.target, t.holdout_target, "b" * 64)
        self.assertNotEqual(t.digest(), other.digest(), "the target's source commitment is in the digest")
        self.assertNotEqual(t.digest(), hand_task(8).digest())
        with self.assertRaises(ValueError):
            bl.make_task(ADDR, parts, t.target[:-1], t.holdout_target, "a" * 64)
        with self.assertRaises(ValueError):
            bl.make_task(ADDR, parts, t.target, t.holdout_target, "zz")
        with self.assertRaises(ValueError):
            bl.make_task(ADDR, parts, tuple([2] * len(t.target)), t.holdout_target, "a" * 64)


class TheSliceWideStimulus(unittest.TestCase):
    """task-v0.3 (section 7.2): the shape, the two probabilities by hand from the generator's own draws, the independence of the two
    draws, d per element, the validator, the carrier mapping. No value of any production label is derived (exposed seeds only)."""
    SEEDS = (3, 5, 7, 8, 11, 12, 13)                                 # already-exposed values (section 9.2); nothing production-like

    def test_every_set_step_is_a_broadcast_and_d_is_per_element(self):
        seen_d_non_broadcast = False
        for seed in self.SEEDS:
            parts = bl.public_parts(seed)
            for name in ("stimulus", "holdout_stimulus"):
                self.assertEqual(bl.stimulus_findings(parts[name]), [], (seed, name))
                for s in parts[name][1:]:
                    self.assertIn(s["ce"], (0x00, 0xFF)); self.assertIn(s["sr"], (0x00, 0xFF)); self.assertEqual(type(s["ce"]), int); self.assertEqual(type(s["sr"]), int)
                    self.assertEqual(bl.slice_wide_controls(s), (1 if s["ce"] == 0xFF else 0, 1 if s["sr"] == 0xFF else 0))
                    seen_d_non_broadcast = seen_d_non_broadcast or s["d"] not in (0x00, 0xFF)
        self.assertTrue(seen_d_non_broadcast, "d stays a per-element draw: not every d is a broadcast")
        self.assertEqual(bl.TASK_VERSION, "task-v0.3"); self.assertEqual(bl.PREVIOUS_TASK_VERSION, "task-v0.2")
        self.assertEqual((bl.CE_HIGH_ONE_IN, bl.SR_HIGH_ONE_IN, bl.BROADCAST), (2, 4, {0: 0x00, 1: 0xFF}))
        self.assertEqual((bl.broadcast(0), bl.broadcast(1)), (0x00, 0xFF))
        for bad in (2, -1, True, "1"):
            with self.assertRaises(ValueError):
                bl.broadcast(bad)
        self.assertTrue(bl.is_broadcast(0) and bl.is_broadcast(255)); self.assertFalse(bl.is_broadcast(0x80) or bl.is_broadcast(True) or bl.is_broadcast(255.0))

    def test_the_two_probabilities_and_the_draw_order_by_hand(self):
        """The same generator stream, replayed by hand: per set step ce = [uniform(2) == 0], then sr = [uniform(4) == 0], then d = uniform(256);
        a step's ce / sr equal the broadcast of those draws. The rates over the exposed seeds are near 1/2 and 1/4 (a sanity bound, not a
        statistic): the rule is the draw, not the rate."""
        hi_ce = hi_sr = n = 0
        for seed in self.SEEDS:
            rng = Rng(seed)
            parts = bl.public_parts(seed)
            for s in parts["stimulus"][1:]:
                ce = 1 if rng.uniform(2) == 0 else 0
                sr = 1 if rng.uniform(4) == 0 else 0
                d = rng.uniform(256)
                self.assertEqual((s["ce"], s["sr"], s["d"]), (bl.broadcast(ce), bl.broadcast(sr), d), seed)
                hi_ce += ce; hi_sr += sr; n += 1
            hrng = Rng(seed ^ bl.HOLDOUT_SALT)
            for s in parts["holdout_stimulus"][1:]:
                ce = 1 if hrng.uniform(2) == 0 else 0
                sr = 1 if hrng.uniform(4) == 0 else 0
                d = hrng.uniform(256)
                self.assertEqual((s["ce"], s["sr"], s["d"]), (bl.broadcast(ce), bl.broadcast(sr), d), seed)
                hi_ce += ce; hi_sr += sr; n += 1
        self.assertEqual(n, len(self.SEEDS) * (bl.K_DEFAULT + bl.K_HOLDOUT + 2 * bl.LEVEL_STEPS))
        self.assertTrue(0.3 < hi_ce / n < 0.7, hi_ce / n); self.assertTrue(0.1 < hi_sr / n < 0.45, hi_sr / n)
        # the two draws are independent draws of one stream: swapping the order would change the step (the rule fixes ce, sr, d)
        rng = Rng(7); sr_first = 1 if rng.uniform(4) == 0 else 0; ce_second = 1 if rng.uniform(2) == 0 else 0
        s1 = bl.public_parts(7)["stimulus"][1]
        self.assertTrue((s1["ce"], s1["sr"]) != (bl.broadcast(ce_second), bl.broadcast(sr_first)) or (s1["ce"] == s1["sr"]), "the draw order is part of the rule")

    def test_the_validator_names_a_per_element_vector_and_every_other_shape_defect(self):
        parts = bl.public_parts(7)
        self.assertEqual(bl.stimulus_findings(parts["stimulus"]), [])
        bad = [dict(s) for s in parts["stimulus"]]; bad[2]["ce"] = 0x80
        f = bl.stimulus_findings(bad); self.assertEqual(len(f), 1); self.assertIn("step 2: ce = 128", f[0]); self.assertIn("broadcast", f[0])
        bad = [dict(s) for s in parts["stimulus"]]; bad[3]["sr"] = 0x01
        self.assertTrue(any("step 3: sr = 1" in x for x in bl.stimulus_findings(bad)))
        bad = [dict(s) for s in parts["stimulus"]]; bad[1]["ce"] = True
        self.assertTrue(bl.stimulus_findings(bad), "a bool is not the int 0 / 1 broadcast")
        bad = [dict(s) for s in parts["stimulus"]]; bad[1]["d"] = 256
        self.assertTrue(any("d 256" in x for x in bl.stimulus_findings(bad)))
        bad = [dict(s) for s in parts["stimulus"]]; bad[0] = {"kind": "set", "clock": 0, "ce": 0, "sr": 0, "d": 0}
        self.assertTrue(any("step 0" in x for x in bl.stimulus_findings(bad)))
        bad = [dict(s) for s in parts["stimulus"]]; bad.insert(4, {"kind": "init"})
        self.assertTrue(any("step 4" in x and "init" in x for x in bl.stimulus_findings(bad)))
        bad = [dict(s) for s in parts["stimulus"]]; bad[5]["clock"] = 2
        self.assertTrue(any("clock 2" in x for x in bl.stimulus_findings(bad)))
        bad = [dict(s) for s in parts["stimulus"]]; bad[5]["extra"] = 1
        self.assertTrue(any("keys" in x for x in bl.stimulus_findings(bad)))
        self.assertTrue(bl.stimulus_findings([])); self.assertTrue(bl.stimulus_findings("x")); self.assertTrue(bl.stimulus_findings([{"kind": "init"}, 3]))
        with self.assertRaises(ValueError):
            bl.slice_wide_controls({"kind": "set", "clock": 0, "ce": 0x80, "sr": 0, "d": 0})
        with self.assertRaises(ValueError):
            bl.slice_wide_controls({"kind": "init"})
        # the task-v0.2 shape (per-element ce, sparse sr) is NOT a task-v0.3 stimulus: the validator refuses it
        rng = Rng(7); old = [{"kind": "init"}] + [{"kind": "set", "clock": c, "ce": rng.uniform(256), "sr": sum(1 << i for i in range(8) if rng.uniform(4) == 0), "d": rng.uniform(256)} for c in (1, 0, 1, 0, 1, 0, 0, 0)]
        self.assertTrue(bl.stimulus_findings(old), "the previous task's shape is refused by name")

    def test_the_common_grammar_and_the_carrier_mapping(self):
        """The model accepts every task-v0.3 step as handed (the 8-bit grammar is the common one); the carrier's STEP_IN word packs it and
        `realisable` is an invariant task-v0.3 never violates (host/b4carrier_regmap, read-only: the carrier unit is accepted and unchanged)."""
        sys.path.insert(0, str(R / "host"))
        import b4carrier_regmap as rm
        for seed in self.SEEDS:
            parts = bl.public_parts(seed)
            for name in ("stimulus", "holdout_stimulus"):
                for s in parts[name][1:]:
                    fm.validate_step(s)
                    self.assertTrue(rm.realisable(s["ce"], s["sr"]), "task-v0.3 never produces a vector the carrier refuses")
                    w = rm.step_word(s["d"], s["ce"], s["sr"], s["clock"])
                    self.assertEqual(rm.decode_applied(w), {"d": s["d"], "ce": s["ce"], "sr": s["sr"], "clock": s["clock"]}, "the word round-trips the step unchanged")
        self.assertFalse(rm.realisable(0x80, 0x00)); self.assertFalse(rm.realisable(0x00, 0x01))


class TheScoring(unittest.TestCase):
    def test_hits_nones_and_the_ceiling(self):
        t = hand_task(3)
        steps = len(t.stimulus)
        full = {"steps": [{"q_after": [None] * 8} for _ in range(steps)]}
        for (s, e), tv in zip(t.mask, t.target):
            full["steps"][s]["q_after"][e] = tv
        self.assertEqual(bl.score(full, t), (t.ceiling, 0))
        full["steps"][1]["q_after"][0] = None
        full["steps"][2]["q_after"][5] = None
        self.assertEqual(bl.score(full, t), (t.ceiling - 2, 2), "None scores nothing, is counted, and the ceiling did not move")
        wrong = {"steps": [{"q_after": [0] * 8} for _ in range(steps)]}
        for (s, e), tv in zip(t.mask, t.target):
            wrong["steps"][s]["q_after"][e] = 1 - tv
        self.assertEqual(bl.score(wrong, t), (0, 0))
        grid = [st["q_after"] for st in full["steps"]]
        self.assertEqual(bl.score_grid(grid, t), bl.score(full, t))
        with self.assertRaises(ValueError):
            bl.score({"steps": full["steps"][:-1]}, t)

    def test_none_equals_none_is_not_a_hit(self):
        t = hand_task(3)
        trace = {"steps": [{"q_after": [None] * 8} for _ in range(len(t.stimulus))]}
        self.assertEqual(bl.score(trace, t), (0, len(t.mask)))

    def test_holdout_scoring_is_its_own(self):
        t = hand_task(3)
        trace = {"steps": [{"q_after": [None] * 8} for _ in range(len(t.holdout_stimulus))]}
        for (s, e), tv in zip(t.holdout_mask, t.holdout_target):
            trace["steps"][s]["q_after"][e] = tv
        self.assertEqual(bl.score_holdout(trace, t), (t.holdout_ceiling, 0))
        self.assertEqual(bl.score_holdout_grid([st["q_after"] for st in trace["steps"]], t), (t.holdout_ceiling, 0))
        with self.assertRaises(ValueError):
            bl.score(trace, t)

    def test_the_planted_trace_scores_the_ceiling_by_construction(self):
        """The target IS the planted trace: scoring that trace gives the ceiling with no None (T-i: a None would have refused the target)."""
        parts = bl.public_parts(5)
        g_s = [[(s + e) % 2 for e in range(8)] for s in range(len(parts["stimulus"]))]
        g_h = [[(s * e) % 2 for e in range(8)] for s in range(len(parts["holdout_stimulus"]))]
        t = hand_task(5, grids=(g_s, g_h))
        self.assertEqual(bl.score_grid(g_s, t), (64, 0)); self.assertEqual(bl.score_holdout_grid(g_h, t), (80, 0))


if __name__ == "__main__":
    unittest.main()

"""b4/host/b4_landscape.py — the public task: generated from the landscape seed and the addresses alone (the module
imports neither the mapping nor the hypothesis), deterministic, the same for every arm; the base all-zero (declared);
the mask covers every readout cell after the init step with weight 1, so the ceiling is the cell count; the holdout
stimulus is its own derivation; the scoring counts a 0/1 match, counts None without scoring it, never moves the
ceiling, never scores None == None; the replay scoring over a q grid equals the trace scoring. No skip."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_landscape as bl  # noqa: E402
import b4_ff_model as fm  # noqa: E402

ADDR = tuple(f"0x{0x400a00 + i:08x}/1/{i}" for i in range(21))     # any 21 address strings: the generator never reads them


class TheGenerator(unittest.TestCase):
    def test_it_reads_no_mapping_and_no_hypothesis(self):
        """By the code, not the prose: the module's imports and attribute names (an AST scan, docstrings excluded)."""
        import ast
        tree = ast.parse((R / "b4/host/b4_landscape.py").read_text())
        imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | \
                   {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        for forbidden in ("b4_ff_mapping", "b4_ff_hypothesis", "b4_ff_model"):
            self.assertNotIn(forbidden, imported, f"the task generator must not import {forbidden}")
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        for forbidden in ("diagnose", "decode", "step_diagnostics", "entries", "address_of", "effect"):
            self.assertNotIn(forbidden, attrs, f"the task generator must not touch {forbidden}")

    def test_determinism_and_shape(self):
        t1, t2 = bl.make_task(7, ADDR), bl.make_task(7, ADDR)
        self.assertEqual(t1, t2)
        self.assertEqual(t1.digest(), t2.digest())
        self.assertNotEqual(t1.digest(), bl.make_task(8, ADDR).digest())
        self.assertEqual((t1.version, t1.base_genome, t1.addresses), (bl.TASK_VERSION, 0, ADDR))
        self.assertEqual(t1.stimulus[0], {"kind": "init"})
        self.assertEqual(len(t1.stimulus), 1 + bl.K_DEFAULT + bl.LEVEL_STEPS)
        clocks = [s["clock"] for s in t1.stimulus[1:1 + bl.K_DEFAULT]]
        self.assertEqual(clocks, [1, 0] * (bl.K_DEFAULT // 2), "the clock steps alternate: K edges")
        for s in t1.stimulus[1:]:
            fm.validate_step(s)
        self.assertEqual(len(t1.mask), (len(t1.stimulus) - 1) * 8)
        self.assertEqual(set(t1.weights), {1})
        self.assertEqual(t1.ceiling, len(t1.mask))
        self.assertTrue(all(t in (0, 1) for t in t1.target))
        self.assertNotEqual(t1.holdout_stimulus, t1.stimulus)
        self.assertEqual(len(t1.holdout_stimulus), 1 + bl.K_HOLDOUT + bl.LEVEL_STEPS)
        with self.assertRaises(ValueError):
            bl.make_task(-1, ADDR)
        with self.assertRaises(ValueError):
            bl.make_task(True, ADDR)


class TheScoring(unittest.TestCase):
    def test_hits_nones_and_the_ceiling(self):
        t = bl.make_task(3, ADDR)
        steps = len(t.stimulus)
        # a trace that equals the target everywhere: the ceiling; then None in two cells; then everything wrong
        full = {"steps": [{"q_after": [None] * 8} for _ in range(steps)]}
        for (s, e), tv in zip(t.mask, t.target):
            full["steps"][s]["q_after"][e] = tv
        self.assertEqual(bl.score(full, t), (t.ceiling, 0))
        full["steps"][1]["q_after"][0] = None
        full["steps"][2]["q_after"][5] = None
        self.assertEqual(bl.score(full, t), (t.ceiling - 2, 2), "None scores nothing, is counted, and the ceiling did not move")
        self.assertEqual(t.ceiling, len(t.mask))
        wrong = {"steps": [{"q_after": [1 - tv if True else tv for tv in [0] * 8]} for _ in range(steps)]}
        for (s, e), tv in zip(t.mask, t.target):
            wrong["steps"][s]["q_after"][e] = 1 - tv
        self.assertEqual(bl.score(wrong, t), (0, 0))
        grid = [st["q_after"] for st in full["steps"]]
        self.assertEqual(bl.score_grid(grid, t), bl.score(full, t))
        with self.assertRaises(ValueError):
            bl.score({"steps": full["steps"][:-1]}, t)

    def test_none_equals_none_is_not_a_hit(self):
        t = bl.make_task(3, ADDR)
        trace = {"steps": [{"q_after": [None] * 8} for _ in range(len(t.stimulus))]}
        self.assertEqual(bl.score(trace, t), (0, len(t.mask)))

    def test_holdout_scoring_is_its_own(self):
        t = bl.make_task(3, ADDR)
        trace = {"steps": [{"q_after": [None] * 8} for _ in range(len(t.holdout_stimulus))]}
        for (s, e), tv in zip(t.holdout_mask, t.holdout_target):
            trace["steps"][s]["q_after"][e] = tv
        self.assertEqual(bl.score_holdout(trace, t), (t.holdout_ceiling, 0))
        with self.assertRaises(ValueError):
            bl.score(trace, t)


if __name__ == "__main__":
    unittest.main()

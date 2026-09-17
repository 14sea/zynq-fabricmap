"""b3/host/b3_gate.py (lifecycle 2) — the criteria on synthetic rows (a passing set, and each criterion
made to fail for its own reason), the budget rule and its tie-break, H9 as a pure diagnostic (no pass,
no claim condition; N2(B) and delta2's power at the gate's N by B2's functions), the lifecycle-2
constants (label, rules version, output path), the seed exclusion sources including lifecycle 1's gate
run 1 and its nine trial pairs, the pins the report carries, the renderer (never "H9 holds / fails",
lifecycle 1's report refused), the refusal to overwrite lifecycle 1's outputs, and a small real run of
the whole pipeline into a temp directory."""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import time
import contextlib
import io
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host", R / "b3/tests"):
    sys.path.insert(0, str(p))
import b2_gate as bg  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_control_x as cx  # noqa: E402
import b3_gate as g  # noqa: E402
import b3_gate_report_md as md  # noqa: E402
from b3_test_fixtures import FIXTURE_HEAD, rewrite_report, synthetic_rows, write_gate_fixture  # noqa: E402

G = list(g.GRID)


def synthetic_report(results: dict, label="synthetic") -> dict:
    """A report shaped like main()'s, around evaluate()'s results — for the renderer."""
    return {"schema": "b3_gate_report", "schema_version": "2.0.0", "lifecycle": g.LIFECYCLE, "label": label,
            "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "head_at_run": "0" * 40, "worktree_dirty_at_start": False,
            "architecture": {"path": "docs/b3_architecture.md", "sha256": "a" * 64, "last_commit": "b" * 40}, "thresholds": g.THRESHOLDS,
            "engine": {"version": bs.ENGINE_VERSION, "mu": bs.MU, "lambda": bs.LAMBDA, "kmax": bs.KMAX}, "carto_version": "x",
            "control_x": {"seed_x": 1, "attempts": 1, "permutation_sha256": "c" * 64},
            "seeds": {"label": g.GATE_LABEL, "master_seed": 1, "count": 200, "excluded_values_total": 0, "excluded_sources": {}},
            "map": {"path": "maps/x", "sha256": "d" * 64}, "gate_fitness": "F1", "results": results, "wall_s": 0.0}


class Lifecycle2Constants(unittest.TestCase):
    """Preregistration v0.3 §10 (ii): the label, the rules version, the output paths — and lifecycle 1's
    never overwritten."""
    def test_label_rules_version_and_paths(self):
        self.assertEqual(g.GATE_LABEL, "b3-gate-2")
        self.assertEqual(g.THRESHOLDS["rules_version"], "architecture v0.3 §9")
        self.assertEqual(g.OUT_DEFAULT, "evidence/b3/gate_2")
        self.assertEqual(g.LIFECYCLE, 2)
        self.assertEqual(md.REPORT_DEFAULT, "evidence/b3/gate_2/gate_report.json")
        self.assertEqual(md.OUT_DEFAULT, "docs/b3_gate_2_report.md")
        self.assertNotEqual(g.GATE_LABEL, g.LIFECYCLE1_GATE_LABEL)
        self.assertNotEqual(bs.master_seed(g.GATE_LABEL, "x"), bs.master_seed(g.LIFECYCLE1_GATE_LABEL, "x"))

    def test_the_gate_refuses_lifecycle_1s_directories_and_everything_under_them_before_touching_anything(self):
        """Hermetic: lifecycle 1's directories are temp COPIES here (the constants patched), so a broken
        guard can damage only the copies — the first version of this test ran against the real evidence
        and a guard-removed mutant overwrote evidence/b3/gate/ (restored from HEAD, 2026-09-17). The
        owner's P2: the exact path alone was refused; a descendant (evidence/b3/gate/child) was written."""
        t = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, t, True)
        d = t / "evidence/b3/gate"; shutil.copytree(g.LIFECYCLE1_GATE_DIR, d)
        tr = t / "evidence/b3/plan_trial_2026_09_17"; shutil.copytree(g.LIFECYCLE1_TRIAL_DIR, tr)
        snap = lambda p: sorted((x.relative_to(p).as_posix(), x.stat().st_size, x.stat().st_mtime_ns) for x in p.rglob("*"))  # noqa: E731
        before, before_tr = snap(d), snap(tr)
        real_before = snap(g.LIFECYCLE1_GATE_DIR) + snap(g.LIFECYCLE1_TRIAL_DIR)
        with mock.patch.object(g, "LIFECYCLE1_GATE_DIR", d), mock.patch.object(g, "LIFECYCLE1_TRIAL_DIR", tr), \
             mock.patch.object(g, "git_dirty", return_value=False), mock.patch.object(g, "git_head", return_value=FIXTURE_HEAD):
            for out in (str(d), str(t / "evidence/b3/../b3/gate"), str(d) + "/", str(d / "child"), str(d / "a/b/c"), str(tr), str(tr / "gate_2")):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    rc = g.main(["--seeds", "1", "--workers", "1", "--fitness", "F1", "--out", out])
                self.assertEqual(rc, 2, out)
                self.assertTrue(err.getvalue().startswith("REFUSED: "), err.getvalue())
                self.assertIn("never overwritten", err.getvalue())
        self.assertEqual(snap(d), before); self.assertEqual(snap(tr), before_tr)
        self.assertEqual(snap(g.LIFECYCLE1_GATE_DIR) + snap(g.LIFECYCLE1_TRIAL_DIR), real_before)
        # the guard is a function the plan tool uses too
        with mock.patch.object(g, "LIFECYCLE1_GATE_DIR", d):
            with self.assertRaises(g.Refusal):
                g.refuse_lifecycle1_path(d / "x" / "y")
            g.refuse_lifecycle1_path(t / "evidence/b3/gate_2")                 # a sibling is fine

    def test_the_gate_refuses_a_dirty_tree_or_no_head_before_writing_anything(self):
        """The owner's P2: the report pins HEAD and the architecture bytes, so a run on a dirty tree or
        without a commit is refused (REFUSED:, exit 2) and no output directory is created."""
        t = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, t, True)
        out = t / "gate_2"
        for head, dirty, what in ((None, False, "no HEAD"), ("abc", False, "no HEAD"), (FIXTURE_HEAD, True, "dirty")):
            err = io.StringIO()
            with mock.patch.object(g, "git_dirty", return_value=dirty), mock.patch.object(g, "git_head", return_value=head), contextlib.redirect_stderr(err):
                rc = g.main(["--seeds", "1", "--workers", "1", "--fitness", "F1", "--out", str(out)])
            self.assertEqual(rc, 2, what)
            self.assertTrue(err.getvalue().startswith("REFUSED: "), err.getvalue())
            self.assertIn(what, err.getvalue())
            self.assertFalse(out.exists(), what)
        # F1 absent from --fitness: refused too
        err = io.StringIO()
        with mock.patch.object(g, "git_dirty", return_value=False), mock.patch.object(g, "git_head", return_value=FIXTURE_HEAD), contextlib.redirect_stderr(err):
            self.assertEqual(g.main(["--seeds", "1", "--workers", "1", "--fitness", "F2", "--out", str(out)]), 2)
        self.assertIn("F1", err.getvalue()); self.assertFalse(out.exists())

    def test_the_renderer_refuses_lifecycle_1s_output_path_and_descendants(self):
        """Hermetic as above: the output constant patched to a temp copy of docs/b3_gate_report.md and
        the gate directory to a temp copy. The positive path (a valid fixture rendered to the lifecycle-2
        path) is in Renderer.test_the_cli_renders_only_a_validated_report."""
        t = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, t, True)
        p = t / "docs/b3_gate_report.md"; p.parent.mkdir(parents=True)
        shutil.copy(md.LIFECYCLE1_OUT, p)
        d = t / "evidence/b3/gate"; shutil.copytree(g.LIFECYCLE1_GATE_DIR, d)
        before = (p.stat().st_mtime_ns, p.stat().st_size); before_d = sorted(x.name for x in d.iterdir())
        with mock.patch.object(md, "LIFECYCLE1_OUT", p), mock.patch.object(g, "LIFECYCLE1_GATE_DIR", d):
            for out in (str(p), str(t / "docs/../docs/b3_gate_report.md"), str(d / "report.md"), str(d / "x/report.md")):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    self.assertEqual(md.main(["--report", str(d / "gate_report.json"), "--out", out]), 2, out)
                self.assertTrue(err.getvalue().startswith("REFUSED: "), err.getvalue())
        self.assertEqual((p.stat().st_mtime_ns, p.stat().st_size), before)
        self.assertEqual(sorted(x.name for x in d.iterdir()), before_d)


class Criteria(unittest.TestCase):
    """The bootstrap experiment count is lowered to 100 for these synthetic evaluations only (the
    production 1 000 makes every full ascending scan to N = 200 cost minutes; the rule under test is
    the same); it is restored afterwards and the real-run test below uses the production value."""
    @classmethod
    def setUpClass(cls):
        cls._saved = g.THRESHOLDS["H2_bootstrap_experiments"]
        g.THRESHOLDS["H2_bootstrap_experiments"] = 100
        cls.rows = synthetic_rows()
        cls.res = g.evaluate("F1", cls.rows)

    @classmethod
    def tearDownClass(cls):
        g.THRESHOLDS["H2_bootstrap_experiments"] = cls._saved

    def test_the_synthetic_set_passes_and_names_a_budget(self):
        res = self.res
        self.assertTrue(res["pass"], {k: v["pass"] for k, v in res["criteria"].items()})
        self.assertIn(res["b_star"], G)
        cands = res["criteria"]["budget_rule"]["candidates"]
        eligible = [c for c in cands if c["H1"] and c["N"] is not None]
        self.assertEqual(res["b_star"], min(eligible, key=lambda c: (c["cost"], c["budget"]))["budget"])
        self.assertEqual(res["criteria"]["H5"]["search_evaluations"], res["criteria"]["H5"]["required_pairs_N"] * 3 * res["b_star"])
        self.assertEqual(set(res["criteria"]), {"budget_rule", "H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8"})

    def test_each_criterion_fails_for_its_own_reason(self):
        def with_rows(mutate):
            rows = copy.deepcopy(self.rows)
            mutate(rows)
            return g.evaluate("F1", rows)
        # H1: O saturates at the ceiling everywhere
        r = with_rows(lambda rows: [row["arms"]["O"].__setitem__("at_grid", [40] * len(G)) for row in rows])
        self.assertFalse(r["pass"]); self.assertIsNone(r["b_star"]); self.assertIsNone(r["diagnostics"]["H9"])
        # H3: X profits like O
        r = with_rows(lambda rows: [row["arms"]["X"].__setitem__("at_grid", list(row["arms"]["O"]["at_grid"])) for row in rows])
        self.assertFalse(r["criteria"]["H3"]["pass"]); self.assertFalse(r["criteria"]["H2"]["pass"])
        # H4: end-to-end F above O everywhere — H4 fails; H9 reports it and decides nothing
        r = with_rows(lambda rows: [row["arms"]["F"].__setitem__("end_to_end_at_grid", [v + 5 for v in row["arms"]["O"]["at_grid"]]) for row in rows])
        self.assertFalse(r["criteria"]["H4"]["pass"]); self.assertNotIn("H9", r["criteria"])
        self.assertTrue(all(row["sign_test_p"] > g.THRESHOLDS["H9_alpha"] for row in r["diagnostics"]["H9"]["delta2_by_budget_from_b_star"]))
        # H7: one wrong decode anywhere
        r = with_rows(lambda rows: rows[3]["arms"]["O"].__setitem__("wrong_decodes", 1))
        self.assertFalse(r["criteria"]["H7"]["pass"])
        r = with_rows(lambda rows: rows[3]["arms"]["O"].__setitem__("online_map_ok", False))
        self.assertFalse(r["criteria"]["H7"]["pass"])
        # H8: a replay finding, a schema finding, a shadow finding — each alone
        for key, arm in (("replay_findings", "O"), ("ledger_schema_findings", "O"), ("shadow_findings", "X")):
            r = with_rows(lambda rows, key=key, arm=arm: rows[7]["arms"][arm].__setitem__(key, ["x"]))
            self.assertFalse(r["criteria"]["H8"]["pass"], key)
        # H6: too few seeds
        r = g.evaluate("F1", copy.deepcopy(self.rows[:150]))
        self.assertFalse(r["criteria"]["H6"]["pass"])
        # H2: Δ1 never both signs within one budget (O = R + 1 everywhere)
        r = with_rows(lambda rows: [row["arms"]["O"].__setitem__("at_grid", [v + 1 for v in row["arms"]["R"]["at_grid"]]) for row in rows])
        self.assertFalse(r["criteria"]["H2"]["pass"])
        self.assertEqual(r["criteria"]["H2"]["budgets_with_both_signs"], [])

    def test_the_statistics_are_b2s_by_import(self):
        d = [1, 2, -1, 3, 0]
        self.assertEqual(g._stats(d)["sign_test_p"], bg.sign_test_p(d)[0])
        self.assertIs(g.bg, bg)
        self.assertEqual(g.THRESHOLDS["H5_power_scan_seed"], 1)
        self.assertEqual(g.THRESHOLDS["H2_control_bootstrap_seed"], 7)
        self.assertEqual(g.THRESHOLDS["b1_map_cost"], 333)


class LoadBearingGuards(unittest.TestCase):
    """The owner's read-only mutant of 2026-09-17 (H5's pass forced True) and the v0.3 change of H9's
    role: these cases discriminate them."""
    @classmethod
    def setUpClass(cls):
        cls._saved = g.THRESHOLDS["H2_bootstrap_experiments"]
        g.THRESHOLDS["H2_bootstrap_experiments"] = 100

    @classmethod
    def tearDownClass(cls):
        g.THRESHOLDS["H2_bootstrap_experiments"] = cls._saved

    def test_h5_fails_on_the_cap_alone_when_the_effect_is_strong(self):
        """Random-safe held at the base below 1 500 (H1 false there), so the budget rule lands on
        1 500 with N = 8: cost 36 000 > 30 000 while d is large and every other row passes. With the
        cap raised to 40 000 the same rows pass — the cap is what decides."""
        import random
        rng = random.Random(3)
        rows = synthetic_rows()
        for row in rows:
            for k, b in enumerate(G):
                if b < 1500:
                    row["arms"]["R"]["at_grid"][k] = row["base_fit"]          # R never above the base: H1 fails below 1 500
                    row["arms"]["X"]["at_grid"][k] = row["base_fit"]
            row["arms"]["O"]["at_grid"][0] = row["base_fit"] + rng.choice([-1, 1, 2])   # both signs of Δ1 at budget 100 (H2's condition is over any budget)
        res = g.evaluate("F1", rows)
        self.assertEqual(res["b_star"], 1500)
        c = res["criteria"]
        self.assertFalse(c["H5"]["pass"])
        self.assertGreater(c["H5"]["search_evaluations"], g.THRESHOLDS["H5_search_evaluation_cap"])
        self.assertGreaterEqual(c["H5"]["cohen_d"], g.THRESHOLDS["H5_cohen_d_min"])
        self.assertTrue(all(c[k]["pass"] for k in ("budget_rule", "H1", "H2", "H3", "H4", "H6", "H7", "H8")), {k: v["pass"] for k, v in c.items()})
        self.assertFalse(res["pass"])
        saved = g.THRESHOLDS["H5_search_evaluation_cap"]
        try:
            g.THRESHOLDS["H5_search_evaluation_cap"] = 40000
            res2 = g.evaluate("F1", rows)
            self.assertTrue(res2["criteria"]["H5"]["pass"])
            self.assertTrue(res2["pass"])
        finally:
            g.THRESHOLDS["H5_search_evaluation_cap"] = saved

    def test_h9_is_a_diagnostic_at_every_budget_from_b_star_and_decides_nothing(self):
        """v0.3 §9 / preregistration §10 (ii): H9 is neither a criterion nor a claim condition. Δ2 ≤ 0 at
        the largest budget: the gate still passes, nothing carries a pass for H9, the diagnostic reports
        every budget ≥ B* with the last one above α, N2(B) and Δ2's power at the gate's N by B2's own
        functions (seed 1 + N)."""
        base = synthetic_rows()
        res0 = g.evaluate("F1", base)
        b_star = res0["b_star"]
        above = [b for b in G if b > b_star]
        self.assertTrue(above)
        rows = copy.deepcopy(base)
        k = G.index(above[-1])
        for row in rows:
            row["arms"]["F"]["end_to_end_at_grid"][k] = row["arms"]["O"]["at_grid"][k] + 3
        res = g.evaluate("F1", rows)
        self.assertEqual(res["b_star"], b_star)
        self.assertTrue(res["criteria"]["H4"]["pass"])
        self.assertTrue(res["pass"])
        self.assertNotIn("H9", res["criteria"])
        self.assertNotIn("H9_claim_condition", res)
        self.assertNotIn("H9_claim_condition", json.dumps(res))
        h9 = res["diagnostics"]["H9"]
        self.assertNotIn("pass", h9)
        self.assertNotIn("claim_condition", h9)
        self.assertEqual(h9["gate_N"], res["criteria"]["H5"]["required_pairs_N"])
        drows = h9["delta2_by_budget_from_b_star"]
        self.assertEqual([r["budget"] for r in drows], [b for b in G if b >= b_star])
        self.assertGreater(drows[-1]["sign_test_p"], h9["alpha"])
        self.assertLessEqual(drows[0]["sign_test_p"], h9["alpha"])
        for r in drows:
            self.assertNotIn("pass", r)
            for key in ("mean", "median", "cohen_d", "positives", "negatives", "ties", "required_pairs_N2", "power_at_N2", "power_delta2_at_gate_N"):
                self.assertIn(key, r)
        # N2(B) and the power at the gate's N are B2's functions on delta2, the declared seeds
        T = g.THRESHOLDS
        n_gate = h9["gate_N"]
        for r in drows:
            d2 = g.deltas_at(rows, G.index(r["budget"]))["d2"]
            n2, p2 = bg.required_pairs(d2, T["H9_alpha"], T["H5_power_min"], T["H2_bootstrap_experiments"], T["H5_power_scan_seed"], T["H5_pairs_min"], len(rows))
            self.assertEqual((r["required_pairs_N2"], r["power_at_N2"]), (n2, p2 if n2 else None))   # no N2 -> no "power at N2"
            self.assertEqual(r["power_delta2_at_gate_N"], bg.bootstrap_reject_rate(d2, n_gate, T["H9_alpha"], T["H2_bootstrap_experiments"], T["H5_power_scan_seed"] + n_gate))
        # the owner's P2: when no N2 exists, "power at N2" is null — required_pairs' second value is then the power at the
        # scan's LAST N (= S), reported under its own name with that N; when N2 exists the scan stopped there
        last = drows[-1]
        self.assertIsNone(last["required_pairs_N2"])                       # Δ2 ≤ 0 there: no N reaches power 0.9
        self.assertIsNone(last["power_at_N2"])
        self.assertEqual(last["scan_max_N"], len(rows))
        self.assertEqual(last["power_delta2_at_scan_max_N"], bg.bootstrap_reject_rate(g.deltas_at(rows, G.index(last["budget"]))["d2"], len(rows), T["H9_alpha"], T["H2_bootstrap_experiments"], T["H5_power_scan_seed"] + len(rows)))
        self.assertLess(last["power_delta2_at_scan_max_N"], 0.5)
        self.assertLess(last["power_delta2_at_gate_N"], 0.5)
        first = drows[0]
        self.assertIsNotNone(first["required_pairs_N2"])
        self.assertGreaterEqual(first["power_at_N2"], T["H5_power_min"])
        self.assertIsNone(first["power_delta2_at_scan_max_N"])
        # the same discipline for delta1 in per_budget: no N(B) -> no "power at N"
        for t in res["per_budget"]:
            self.assertEqual(t["power_at_N"] is None, t["required_pairs_N"] is None, t["budget"])
            self.assertEqual(t["power_delta1_at_scan_max_N"] is None, t["required_pairs_N"] is not None, t["budget"])
            self.assertEqual(t["power_at_N2"] is None, t["required_pairs_N2"] is None, t["budget"])
            self.assertEqual(t["scan_max_N"], len(rows))
        # a budget where no N(B) exists: delta1 flat -> power_at_N null, the scan-max power present and named
        rows_flat = copy.deepcopy(base)
        for row in rows_flat:
            row["arms"]["O"]["at_grid"][0] = row["arms"]["R"]["at_grid"][0]
        t0 = g.per_budget(rows_flat, 40)[0]
        self.assertIsNone(t0["required_pairs_N"]); self.assertIsNone(t0["power_at_N"]); self.assertIsNone(t0["search_evaluations"])
        self.assertEqual(t0["power_delta1_at_scan_max_N"], bg.bootstrap_reject_rate(g.deltas_at(rows_flat, 0)["d1"], len(rows_flat), T["H5_alpha"], T["H2_bootstrap_experiments"], T["H5_power_scan_seed"] + len(rows_flat)))
        # a pass forced into the diagnostic would be a defect: the gate's pass is H1–H8 only
        self.assertEqual(res["pass"], all(res["criteria"][k]["pass"] for k in ("budget_rule", "H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8")))


class Renderer(unittest.TestCase):
    """docs/b3_gate_2_report.md is rendered from a gate_report.json of the lifecycle-2 shape: never
    "H9 holds" / "H9 fails", the H9 diagnostic table with N2(B) and the power at the gate's N, p-values
    keep their exponent and never round to 0, nested values are complete; a lifecycle-1 report is refused."""
    @classmethod
    def setUpClass(cls):
        cls._saved = g.THRESHOLDS["H2_bootstrap_experiments"]
        g.THRESHOLDS["H2_bootstrap_experiments"] = 100
        rows = synthetic_rows()
        k = G.index(G[-1])
        for row in rows:
            row["arms"]["F"]["end_to_end_at_grid"][k] = row["arms"]["O"]["at_grid"][k] + 3
        cls.rep = synthetic_report({"F1": g.evaluate("F1", rows)})
        cls.text = md.render(cls.rep)

    @classmethod
    def tearDownClass(cls):
        g.THRESHOLDS["H2_bootstrap_experiments"] = cls._saved

    def test_h9_is_rendered_as_a_diagnostic_never_holds_or_fails(self):
        t = self.text
        for phrase in ("H9 holds", "H9 fails", "H9 {'holds'", "claim condition", "condition on the claim"):
            self.assertNotIn(phrase, t)
        self.assertNotIn("| H9 |", t)                                        # not a criterion row
        self.assertIn("H9 diagnostic (decides nothing)", t)
        self.assertIn("| budget | p | mean Δ2 | median Δ2 | pos/neg/ties | Cohen's d | N₂(B) | power at N₂ | Δ2 power at the scan's last N (no N₂) | Δ2 power at the gate's N |", t)
        h9 = self.rep["results"]["F1"]["diagnostics"]["H9"]
        seen_none = False
        for r in h9["delta2_by_budget_from_b_star"]:
            self.assertIn(f"| {r['budget']} | {md.fmt_p(r['sign_test_p'])} |", t)
            line = next(l for l in t.splitlines() if l.startswith(f"| {r['budget']} | {md.fmt_p(r['sign_test_p'])} |"))
            if r["required_pairs_N2"] is None:
                seen_none = True
                self.assertIn(f"| — | — | {md.fmt_p(r['power_delta2_at_scan_max_N'])} at N = {r['scan_max_N']} | {md.fmt_p(r['power_delta2_at_gate_N'])} |", line)
            else:
                self.assertIn(f"| {r['required_pairs_N2']} | {md.fmt_p(r['power_at_N2'])} | — | {md.fmt_p(r['power_delta2_at_gate_N'])} |", line)
        self.assertTrue(seen_none)                                            # the largest budget has no N2 in this fixture
        self.assertIn("| N₂(B) | Δ2 power at N(B) |", t)                      # the per-budget table carries them too
        self.assertIn("lifecycle 2", t)
        self.assertIn("B* = ", t)

    def test_p_values_keep_their_exponent_and_never_round_to_zero(self):
        f1 = self.rep["results"]["F1"]["criteria"]
        p_h4 = f1["H4"]["delta2"]["sign_test_p"]
        self.assertLess(p_h4, 1e-6)
        self.assertIn(md.fmt_p(p_h4), self.text)
        self.assertIn("e-", md.fmt_p(p_h4))
        for r in self.rep["results"]["F1"]["diagnostics"]["H9"]["delta2_by_budget_from_b_star"]:
            self.assertNotEqual(md.fmt_p(r["sign_test_p"]), "0")
            self.assertNotIn(f"| {r['budget']} | 0.00 |", self.text)
        self.assertEqual(md.fmt_p(0.0024), "0.0024")
        self.assertEqual(md.fmt_p(3.793677e-09), "3.79e-09")
        self.assertEqual(md.fmt_p(1.0), "1")
        self.assertEqual(md.fmt_p(None), "—")

    def test_nested_values_are_complete(self):
        self.assertIn("Budget rule candidates", self.text)
        d2 = self.rep["results"]["F1"]["criteria"]["H4"]["delta2"]
        line = next(l for l in self.text.splitlines() if l.startswith("| H4 |"))
        for k in d2:
            self.assertIn(f"{k}:", line)
        self.assertTrue(line.rstrip().endswith("} |"), line)              # the dict is closed: nothing was cut
        self.assertIn(f"sign_test_p: {md.fmt_p(d2['sign_test_p'])}}}", line)
        self.assertNotIn("[:120]", (R / "b3/host/b3_gate_report_md.py").read_text())

    def test_the_cli_renders_only_a_validated_report_and_refuses_by_name(self):
        """The CLI reads a report only through b3_gate.validate_report (the plan's validator): a valid
        fixture renders to the lifecycle-2 path; lifecycle 1's report, a tampered fixture and a missing /
        malformed file are REFUSED: (exit 2, no output) — never a traceback (the owner's P3)."""
        t = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, t, True)
        fx = write_gate_fixture(t / "gate_2")
        out = t / "docs/b3_gate_2_report.md"; out.parent.mkdir()
        self.assertEqual(md.main(["--report", str(fx), "--out", str(out)]), 0)
        text = out.read_text()
        self.assertIn("H9 diagnostic (decides nothing)", text); self.assertIn(FIXTURE_HEAD[:7], text); self.assertNotIn("H9 holds", text)
        cases = {"lifecycle-1": (R / "evidence/b3/gate/gate_report.json", "schema_version"),
                 "missing": (t / "nowhere.json", "cannot be read"), "malformed": (t / "bad.json", "not JSON")}
        (t / "bad.json").write_text("{")
        tampered = t / "tampered"; shutil.copytree(t / "gate_2", tampered)
        rewrite_report(tampered / "gate_report.json", lambda r: r["results"]["F1"].__setitem__("b_star", 3000))
        cases["tampered B*"] = (tampered / "gate_report.json", "results.F1.b_star")
        for name, (rep_path, needle) in cases.items():
            out2 = t / f"out_{name}.md"
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = md.main(["--report", str(rep_path), "--out", str(out2)])
            self.assertEqual(rc, 2, name)
            self.assertTrue(err.getvalue().startswith("REFUSED: "), (name, err.getvalue()))
            self.assertIn(needle, err.getvalue(), name)
            self.assertFalse(out2.exists(), name)

    def test_a_lifecycle_1_report_is_refused_not_rendered(self):
        rep1 = json.loads((R / "evidence/b3/gate/gate_report.json").read_text())
        self.assertIn("H9", rep1["results"]["F1"]["criteria"])
        self.assertFalse(g.is_lifecycle2_report(rep1))
        with self.assertRaises(ValueError):
            md.render(rep1)
        # the lifecycle-2 shape with H9 smuggled back as a criterion, or a claim condition, is refused too
        for mutate in (lambda r: r["results"]["F1"]["criteria"].__setitem__("H9", {"pass": True}),
                       lambda r: r["results"]["F1"].__setitem__("H9_claim_condition", True),
                       lambda r: r["results"]["F1"].pop("diagnostics"),
                       lambda r: r.__setitem__("lifecycle", 1)):
            rep = copy.deepcopy(self.rep)
            mutate(rep)
            self.assertFalse(g.is_lifecycle2_report(rep))
            with self.assertRaises(ValueError):
                md.render(rep)
        self.assertTrue(g.is_lifecycle2_report(self.rep))


class Validator(unittest.TestCase):
    """b3_gate.validate_report — the authority the plan and the renderer read a report through (the
    owner's P2): a fixture built by the tool's own builder is accepted; every provenance, binding, raw
    and result tamper is refused by name; lifecycle 1's report is refused."""
    @classmethod
    def setUpClass(cls):
        cls._saved = g.THRESHOLDS["H2_bootstrap_experiments"]
        g.THRESHOLDS["H2_bootstrap_experiments"] = 100
        cls.t = Path(tempfile.mkdtemp())
        cls.fx = write_gate_fixture(cls.t / "gate_2")

    @classmethod
    def tearDownClass(cls):
        g.THRESHOLDS["H2_bootstrap_experiments"] = cls._saved
        shutil.rmtree(cls.t, True)

    def copy_fixture(self) -> Path:
        d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, d, True)
        shutil.copy(self.fx, d / "gate_report.json"); shutil.copy(self.fx.parent / "raw_F1.json", d / "raw_F1.json")
        return d / "gate_report.json"

    def refused(self, path: Path, needle: str, what: str):
        with self.assertRaises(g.Refusal, msg=what) as cm:
            g.validate_report(path)
        self.assertIn(needle, str(cm.exception), what)
        self.assertTrue(str(cm.exception).startswith("gate report "), str(cm.exception))

    def test_the_fixture_is_accepted_and_the_numbers_are_evaluates(self):
        rep = g.validate_report(self.fx)
        raw = json.loads((self.fx.parent / "raw_F1.json").read_text())
        res = g.evaluate("F1", raw["rows"]); res["wall_s"] = 0.0
        self.assertEqual(json.dumps(rep["results"]["F1"], sort_keys=True), json.dumps(res, sort_keys=True))
        self.assertEqual(rep["seeds"]["master_seed"], bs.master_seed(g.GATE_LABEL, FIXTURE_HEAD))
        self.assertEqual(rep["architecture"]["sha256"], g.sha256_bytes((R / "docs/b3_architecture.md").read_bytes()))
        self.assertIn("F1", rep["raw_files"])

    def test_lifecycle_1s_report_is_refused_by_name(self):
        self.refused(R / "evidence/b3/gate/gate_report.json", "schema_version '1.0.0'", "lifecycle 1")

    def test_every_provenance_and_binding_tamper_is_refused_by_name(self):
        tampers = [
            ("schema_version", lambda r: r.__setitem__("schema_version", "1.0.0"), "schema_version '1.0.0'"),
            ("lifecycle", lambda r: r.__setitem__("lifecycle", 1), "lifecycle 1"),
            ("H9 as a criterion", lambda r: r["results"]["F1"]["criteria"].__setitem__("H9", {"pass": True}), "lifecycle-2 shape"),
            ("claim condition", lambda r: r["results"]["F1"].__setitem__("H9_claim_condition", True), "lifecycle-2 shape"),
            ("head null", lambda r: r.__setitem__("head_at_run", None), "head_at_run None"),
            ("head short", lambda r: r.__setitem__("head_at_run", "f159dee"), "head_at_run 'f159dee'"),
            ("dirty", lambda r: r.__setitem__("worktree_dirty_at_start", True), "worktree_dirty_at_start True"),
            ("dirty null", lambda r: r.__setitem__("worktree_dirty_at_start", None), "worktree_dirty_at_start None"),
            ("thresholds", lambda r: r["thresholds"].__setitem__("H5_search_evaluation_cap", 40000), "thresholds.H5_search_evaluation_cap"),
            ("rules version", lambda r: r["thresholds"].__setitem__("rules_version", "architecture v0.2.3 §9"), "thresholds.rules_version"),
            ("label", lambda r: r["seeds"].__setitem__("label", "b3-gate"), "seeds.label 'b3-gate'"),
            ("master seed", lambda r: r["seeds"].__setitem__("master_seed", r["seeds"]["master_seed"] + 1), "seeds.master_seed"),
            ("architecture digest", lambda r: r["architecture"].__setitem__("sha256", "0" * 64), "architecture.sha256"),
            ("architecture path", lambda r: r["architecture"].__setitem__("path", "docs/b2_architecture.md"), "architecture.path"),
            ("control permutation", lambda r: r["control_x"].__setitem__("permutation_sha256", "0" * 64), "control_x.permutation_sha256"),
            ("control seed", lambda r: r["control_x"].__setitem__("seed_x", 1), "control_x.seed_x"),
            ("gate fitness", lambda r: r.__setitem__("gate_fitness", "F2"), "gate_fitness 'F2'"),
            ("raw_files absent", lambda r: r.pop("raw_files"), "raw_files"),
            ("raw digest", lambda r: r["raw_files"]["F1"].__setitem__("sha256", "0" * 64), "raw_files.F1.sha256"),
            ("raw rows count", lambda r: r["raw_files"]["F1"].__setitem__("rows", 7), "rows, expected seeds.count"),
        ]
        for what, mutate, needle in tampers:
            p = self.copy_fixture()
            rewrite_report(p, mutate)
            self.refused(p, needle, what)

    def test_every_result_tamper_is_refused_by_its_path(self):
        """A modified statistic, criterion, B*, N or pass — evaluate() re-run on the raw rows names it."""
        tampers = [
            ("B*", lambda r: r["results"]["F1"].__setitem__("b_star", 3000), "results.F1.b_star"),
            ("N", lambda r: r["results"]["F1"]["criteria"]["H5"].__setitem__("required_pairs_N", 9), "results.F1.criteria.H5.required_pairs_N"),
            ("pass", lambda r: r["results"]["F1"].__setitem__("pass", not r["results"]["F1"]["pass"]), "results.F1.pass"),
            ("a criterion's pass", lambda r: r["results"]["F1"]["criteria"]["H3"].__setitem__("pass", False), "results.F1.criteria.H3.pass"),
            ("a per-budget statistic", lambda r: r["results"]["F1"]["per_budget"][2]["delta1_O_minus_R"].__setitem__("mean", 99.0), "results.F1.per_budget[2].delta1_O_minus_R.mean"),
            ("the H9 diagnostic", lambda r: r["results"]["F1"]["diagnostics"]["H9"]["delta2_by_budget_from_b_star"][0].__setitem__("sign_test_p", 0.5), "results.F1.diagnostics.H9.delta2_by_budget_from_b_star[0].sign_test_p"),
            ("an added field", lambda r: r["results"]["F1"].__setitem__("H9_ok", True), "results.F1.H9_ok: unexpected"),
        ]
        for what, mutate, needle in tampers:
            p = self.copy_fixture()
            rewrite_report(p, mutate)
            self.refused(p, needle, what)

    def test_raw_tampers_are_refused(self):
        """The raw file's digest, its seeds and its rows are bound: a changed byte (digest), a swapped seed
        with the digest refreshed (the seeds re-derived), a changed value with the digest refreshed (the
        re-evaluation), a missing or malformed raw file."""
        def with_raw(mutate_raw, refresh_digest=True):
            p = self.copy_fixture()
            raw = json.loads((p.parent / "raw_F1.json").read_text())
            mutate_raw(raw)
            b = json.dumps(raw, separators=(",", ":")).encode()
            (p.parent / "raw_F1.json").write_bytes(b)
            if refresh_digest:
                rewrite_report(p, lambda r: r["raw_files"]["F1"].__setitem__("sha256", g.sha256_bytes(b)))
            return p
        self.refused(with_raw(lambda raw: raw["rows"][0]["arms"]["O"]["at_grid"].__setitem__(5, 1), refresh_digest=False), "raw_files.F1.sha256", "digest")
        self.refused(with_raw(lambda raw: raw["rows"][3].__setitem__("operator_seed", raw["rows"][3]["operator_seed"] + 1)), "do not carry the seeds", "seeds")
        self.refused(with_raw(lambda raw: raw["rows"].pop()), "rows, expected seeds.count", "row count")
        self.refused(with_raw(lambda raw: raw["rows"][0]["arms"]["O"]["at_grid"].__setitem__(5, 1)), "differs from evaluate() re-run", "value")
        self.refused(with_raw(lambda raw: raw.__setitem__("fitness", "F2")), "fitness / grid", "fitness")
        p = self.copy_fixture(); (p.parent / "raw_F1.json").unlink()
        self.refused(p, "cannot be read", "missing raw")
        p = self.copy_fixture(); (p.parent / "raw_F1.json").write_text("{")
        self.refused(p, "raw_files.F1.sha256", "malformed raw, stale digest: the digest catches it first")
        rewrite_report(p, lambda r: r["raw_files"]["F1"].__setitem__("sha256", g.sha256_bytes(b"{")))
        self.refused(p, "not JSON", "malformed raw with its digest refreshed")
        p = self.copy_fixture(); p.write_text("nope")
        with self.assertRaises(g.Refusal) as cm:
            g.validate_report(p)
        self.assertIn("not JSON", str(cm.exception))
        with self.assertRaises(g.Refusal) as cm:
            g.validate_report(self.t / "absent.json")
        self.assertIn("cannot be read", str(cm.exception))

    def test_deep_findings_names_paths(self):
        e = {"a": [1, {"b": 2}], "c": 3}
        self.assertEqual(g.deep_findings(e, {"a": [1, {"b": 2}], "c": 3}), [])
        self.assertEqual(g.deep_findings(e, {"a": [1, {"b": 3}], "c": 3}), ["a[1].b: 3, expected 2"])
        self.assertEqual(g.deep_findings(e, {"a": [1], "c": 3}), ["a: 1 entries, expected 2"])
        self.assertEqual(g.deep_findings(e, {"c": 3, "d": 1}), ["a: absent", "d: unexpected"])
        self.assertEqual(g.deep_findings(e, {"a": (1, {"b": 2}), "c": 3}), [])              # JSON-normalised
        self.assertEqual(g.deep_findings({"x": 1}, {"x": 1.0}), ["x: 1.0, expected 1"])       # a float is not an int


class SeedsAndPins(unittest.TestCase):
    def test_exclusion_names_every_archived_source_including_lifecycle_1s(self):
        excl, where = g.gate_exclusion()
        for k in ("evidence/b3/sim/sim_report.json", "evidence/b2/gate/gate_report.json"):
            self.assertIn(k, where)
        self.assertTrue(any("B2 session pairs" in k for k in where))
        self.assertTrue(any("B2Q pairs" in k for k in where))
        m = json.loads((R / "manifests/b2_manifest.json").read_text())
        for pair in m["seeds"]["pairs"]:
            self.assertTrue(set(pair) <= excl)
        self.assertIn(m["seeds"]["master_seed"], excl)
        # lifecycle 1's gate run 1: its 200 pairs (from its raw rows) and its master
        g1 = json.loads((R / "evidence/b3/gate/gate_report.json").read_text())
        raw = json.loads((R / "evidence/b3/gate/raw_F1.json").read_text())["rows"]
        self.assertEqual(len(raw), 200)
        self.assertTrue({row["landscape_seed"] for row in raw} | {row["operator_seed"] for row in raw} <= excl)
        self.assertIn(g1["seeds"]["master_seed"], excl)
        k1 = "evidence/b3/gate/gate_report.json (lifecycle 1 gate run 1, pilot)"
        self.assertEqual(where[k1], {"master_seed": g1["seeds"]["master_seed"], "count": 200, "values": 401})
        # lifecycle 1's nine trial pairs and their master
        t_plan = json.loads((R / "evidence/b3/plan_trial_2026_09_17/plan.json").read_text())["seed_derivation"]
        t_pred = json.loads((R / "evidence/b3/plan_trial_2026_09_17/prediction.json").read_text())
        self.assertEqual(len(t_pred["pairs"]), 9)
        self.assertTrue({p["landscape_seed"] for p in t_pred["pairs"]} | {p["operator_seed"] for p in t_pred["pairs"]} <= excl)
        self.assertIn(t_plan["master_seed"], excl)
        k2 = "evidence/b3/plan_trial_2026_09_17/prediction.json (lifecycle 1 trial session pairs, pilot)"
        self.assertEqual(where[k2], {"master_seed": t_plan["master_seed"], "count": 9, "values": 19})
        # lifecycle 1's exclusion is a strict subset: the two lifecycle-1 sets are what lifecycle 2 adds
        excl1, where1 = g.lifecycle1_exclusion()
        self.assertTrue(excl1 < excl)
        self.assertEqual(set(where) - set(where1), {k1, k2})
        self.assertEqual(len(excl - excl1), 401 + 19)
        seeds = bs.pair_seeds(bs.master_seed(g.GATE_LABEL, "deadbeef"), 20, exclude=frozenset(excl))
        self.assertFalse({s for p in seeds for s in p} & excl)

    def test_architecture_pin_and_control_x(self):
        pin = g.architecture_pin()
        self.assertEqual(pin["path"], "docs/b3_architecture.md")
        self.assertEqual(len(pin["sha256"]), 64)
        self.assertEqual(cx.seed_x(bp.INSTRUMENT_COMMIT), bs.master_seed("b3-gate-x", bp.INSTRUMENT_COMMIT))


class SmallRun(unittest.TestCase):
    def test_the_pipeline_runs_end_to_end_into_a_temp_dir(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        head = g.git_head() if g.git_head() and g.HEX40.match(g.git_head()) else FIXTURE_HEAD
        with mock.patch.object(g, "git_dirty", return_value=False), mock.patch.object(g, "git_head", return_value=head):   # the tree may be dirty while developing
            rc = g.main(["--seeds", "3", "--workers", "3", "--fitness", "F1", "--out", str(d), "--label", "test"])
        self.assertEqual(rc, 0)
        rep = json.loads((d / "gate_report.json").read_text())
        raw = json.loads((d / "raw_F1.json").read_text())
        self.assertEqual(len(raw["rows"]), 3)
        row = raw["rows"][0]["arms"]
        self.assertEqual(row["O"]["replay_findings"], [])
        self.assertEqual(row["O"]["ledger_schema_findings"], [])
        self.assertTrue(row["O"]["online_map_ok"])
        self.assertEqual(row["O"]["wrong_decodes"], 0)
        self.assertEqual(row["X"]["shadow_findings"], [])
        self.assertGreater(row["X"]["wrong_decodes"], 0)
        self.assertEqual(row["X"]["perm_sha256"], rep["control_x"]["permutation_sha256"])
        self.assertEqual(rep["seeds"]["count"], 3)
        self.assertEqual(rep["seeds"]["label"], "b3-gate-2")
        self.assertEqual(rep["lifecycle"], 2)
        self.assertEqual(rep["thresholds"]["rules_version"], "architecture v0.3 §9")
        self.assertIn("evidence/b3/gate/gate_report.json (lifecycle 1 gate run 1, pilot)", rep["seeds"]["excluded_sources"])
        self.assertIn("evidence/b3/plan_trial_2026_09_17/prediction.json (lifecycle 1 trial session pairs, pilot)", rep["seeds"]["excluded_sources"])
        excl, _ = g.gate_exclusion()
        self.assertFalse(({r["landscape_seed"] for r in raw["rows"]} | {r["operator_seed"] for r in raw["rows"]}) & excl)
        res = rep["results"]["F1"]
        self.assertIsNone(res["b_star"])                                        # 3 seeds: N(B) cannot exist (N >= 8), and the report says so
        self.assertFalse(res["criteria"]["budget_rule"]["pass"])
        self.assertFalse(res["pass"])
        self.assertNotIn("H9_claim_condition", res)
        self.assertIsNone(res["diagnostics"]["H9"])
        self.assertTrue(g.is_lifecycle2_report(rep))
        self.assertEqual(rep["raw_files"], {"F1": {"path": "raw_F1.json", "sha256": g.sha256_bytes((d / "raw_F1.json").read_bytes()), "rows": 3}})
        self.assertEqual(rep["head_at_run"], head); self.assertFalse(rep["worktree_dirty_at_start"])
        self.assertEqual(g.validate_report(d / "gate_report.json")["seeds"]["count"], 3)      # the real run's report passes the production validator
        text = md.render(rep)
        self.assertIn("FAIL", text)
        self.assertIn("H9 diagnostic: no B*, nothing to report.", text)
        self.assertIn(rep["architecture"]["sha256"], text)


if __name__ == "__main__":
    unittest.main()

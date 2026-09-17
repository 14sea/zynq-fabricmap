"""b3/host/b3_gate.py — the criteria on synthetic rows (a passing set, and each criterion made to fail
for its own reason), the budget rule and its tie-break, the seed exclusion sources, the pins the
report carries, and a small real run of the whole pipeline into a temp directory."""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    sys.path.insert(0, str(p))
import b2_gate as bg  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_control_x as cx  # noqa: E402
import b3_gate as g  # noqa: E402

G = list(g.GRID)


def synthetic_rows(S=200, seed=1):
    """Rows shaped like the gate's: O beats R from 600 on with both signs early, F above O in search
    accounting, F end-to-end below O, X ≈ R and wrong everywhere, O decoding well, all obligations clean."""
    import random
    rng = random.Random(seed)
    rows = []
    for r in range(S):
        base = 2
        Rt, Ft, Ot, Xt, Fe, dec = [], [], [], [], [], []
        for b in G:
            rv = min(39, base + int(b ** 0.5 / 2) + rng.randint(-1, 1))
            fv = min(39, rv + 3 + b // 300 + rng.randint(-1, 1))
            ov = min(39, rv + (b // 150 - 2) + rng.randint(-2, 2))          # negative-ish below 300, positive from 600
            xv = min(39, rv + rng.randint(-1, 1))
            fe = base if b <= 333 else max(0, fv - 6)                       # the charged frozen arm: below O from 600 on
            Rt.append(rv); Ft.append(fv); Ot.append(ov); Xt.append(xv); Fe.append(fe)
            dec.append(min(292, b // 3))                                       # decoded count: 200 at 600, complete by 900
        rows.append({"r": r, "landscape_seed": 1000 + r, "operator_seed": 5000 + r, "base_fit": base,
                     "arms": {"R": {"at_grid": Rt, "champion_holdout": 1, "column_moves": 0},
                              "F": {"at_grid": Ft, "champion_holdout": 1, "column_moves": 100, "end_to_end_at_grid": Fe},
                              "O": {"at_grid": Ot, "champion_holdout": 1, "column_moves": 90, "decoded_at_grid": dec, "versions_final": 100,
                                    "anomalies": 0, "wrong_decodes": 0, "evals_to_full_map": 1500, "ledger_entries": 3000, "ledger_schema_findings": [],
                                    "replay_findings": [], "online_map_ok": True, "online_map_findings": [], "online_map_sha256": "0" * 64, "final_state_sha256": "0" * 64},
                              "X": {"at_grid": Xt, "champion_holdout": 1, "column_moves": 90, "decoded_at_grid": dec, "anomalies": 0, "wrong_decodes": 200,
                                    "decoded_final": 200, "shadow_findings": [], "perm_sha256": "0" * 64}}})
    return rows


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

    def test_each_criterion_fails_for_its_own_reason(self):
        def with_rows(mutate):
            rows = copy.deepcopy(self.rows)
            mutate(rows)
            return g.evaluate("F1", rows)
        # H1: O saturates at the ceiling everywhere
        r = with_rows(lambda rows: [row["arms"]["O"].__setitem__("at_grid", [40] * len(G)) for row in rows])
        self.assertFalse(r["pass"]); self.assertIsNone(r["b_star"])
        # H3: X profits like O
        r = with_rows(lambda rows: [row["arms"]["X"].__setitem__("at_grid", list(row["arms"]["O"]["at_grid"])) for row in rows])
        self.assertFalse(r["criteria"]["H3"]["pass"]); self.assertFalse(r["criteria"]["H2"]["pass"])
        # H4: end-to-end F above O everywhere
        r = with_rows(lambda rows: [row["arms"]["F"].__setitem__("end_to_end_at_grid", [v + 5 for v in row["arms"]["O"]["at_grid"]]) for row in rows])
        self.assertFalse(r["criteria"]["H4"]["pass"]); self.assertFalse(r["criteria"]["H9"]["pass"])
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
    """The owner's two read-only mutants of 2026-09-17 — H5's pass forced True, and H9's scope
    narrowed to B* — survived the criteria tests. These cases discriminate them."""
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

    def test_h9_must_hold_at_every_budget_from_b_star_up_not_only_at_b_star(self):
        base = synthetic_rows()
        res0 = g.evaluate("F1", base)
        b_star = res0["b_star"]
        above = [b for b in G if b > b_star]
        below = [b for b in G if b < b_star]
        self.assertTrue(above and below)
        # Δ2 ≤ 0 at the LARGEST budget only: H4 (at B*) passes, H9 must fail
        rows = copy.deepcopy(base)
        k = G.index(above[-1])
        for row in rows:
            row["arms"]["F"]["end_to_end_at_grid"][k] = row["arms"]["O"]["at_grid"][k] + 3
        res = g.evaluate("F1", rows)
        self.assertEqual(res["b_star"], b_star)
        self.assertTrue(res["criteria"]["H4"]["pass"])
        self.assertFalse(res["criteria"]["H9"]["pass"])
        self.assertFalse(res["H9_claim_condition"])
        self.assertTrue(res["pass"])                                      # H9 is the claim condition, not a pass row
        rows_p = [r for r in res["criteria"]["H9"]["delta2_by_budget_from_b_star"]]
        self.assertEqual([r[0] for r in rows_p], [b for b in G if b >= b_star])
        self.assertGreater(rows_p[-1][1], g.THRESHOLDS["H9_alpha"])
        # Δ2 ≤ 0 at a budget BELOW B* only: outside H9's scope, H9 holds
        rows = copy.deepcopy(base)
        k = G.index(below[0])
        for row in rows:
            row["arms"]["F"]["end_to_end_at_grid"][k] = row["arms"]["O"]["at_grid"][k] + 3
        res = g.evaluate("F1", rows)
        self.assertEqual(res["b_star"], b_star)
        self.assertTrue(res["criteria"]["H9"]["pass"])


class Renderer(unittest.TestCase):
    """docs/b3_gate_report.md is rendered from the committed gate_report.json: p-values keep their
    exponent, small p-values do not round to 0, nested values are complete, H9's detail is present."""
    @classmethod
    def setUpClass(cls):
        import b3_gate_report_md as md
        cls.md = md
        cls.rep = json.loads((R / "evidence/b3/gate/gate_report.json").read_text())
        cls.text = md.render(cls.rep)

    def test_p_values_keep_their_exponent_and_never_round_to_zero(self):
        f1 = self.rep["results"]["F1"]["criteria"]
        p_h4 = f1["H4"]["delta2"]["sign_test_p"]
        self.assertLess(p_h4, 1e-6)
        self.assertIn(self.md.fmt_p(p_h4), self.text)                     # e.g. 3.79e-09
        self.assertIn("e-", self.md.fmt_p(p_h4))
        for b, pv, mn, mdn in f1["H9"]["delta2_by_budget_from_b_star"]:
            self.assertIn(f"| {b} | {self.md.fmt_p(pv)} |", self.text)
            self.assertNotEqual(self.md.fmt_p(pv), "0")
            self.assertNotIn(f"| {b} | 0.00 |", self.text)
        f2 = self.rep["results"]["F2"]["criteria"]["H4"]["delta2"]["sign_test_p"]
        self.assertIn(self.md.fmt_p(f2), self.text)
        self.assertEqual(self.md.fmt_p(0.0024), "0.0024")
        self.assertEqual(self.md.fmt_p(3.793677e-09), "3.79e-09")
        self.assertEqual(self.md.fmt_p(1.0), "1")

    def test_nested_values_are_complete_and_h9_detail_is_present(self):
        self.assertIn("H9 detail", self.text)
        self.assertIn("Budget rule candidates", self.text)
        d2 = self.rep["results"]["F1"]["criteria"]["H4"]["delta2"]
        line = next(l for l in self.text.splitlines() if l.startswith("| H4 |"))
        for k in d2:
            self.assertIn(f"{k}:", line)
        self.assertIn("ties: " + str(d2["ties"]) + "}", line)             # the dict is closed: nothing was cut
        self.assertNotIn("[:120]", (R / "b3/host/b3_gate_report_md.py").read_text())


class SeedsAndPins(unittest.TestCase):
    def test_exclusion_names_every_archived_source(self):
        excl, where = g.gate_exclusion()
        for k in ("evidence/b3/sim/sim_report.json", "evidence/b2/gate/gate_report.json"):
            self.assertIn(k, where)
        self.assertTrue(any("B2 session pairs" in k for k in where))
        self.assertTrue(any("B2Q pairs" in k for k in where))
        m = json.loads((R / "manifests/b2_manifest.json").read_text())
        for pair in m["seeds"]["pairs"]:
            self.assertTrue(set(pair) <= excl)
        self.assertIn(m["seeds"]["master_seed"], excl)
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
        res = rep["results"]["F1"]
        self.assertIsNone(res["b_star"])                                        # 3 seeds: N(B) cannot exist (N >= 8), and the report says so
        self.assertFalse(res["criteria"]["budget_rule"]["pass"])
        self.assertFalse(res["pass"])
        self.assertIsNone(res["H9_claim_condition"])
        import b3_gate_report_md as md
        text = md.render(rep)
        self.assertIn("FAIL", text)
        self.assertIn(rep["architecture"]["sha256"], text)


if __name__ == "__main__":
    unittest.main()

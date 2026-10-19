"""b4/host/b4_gate.py, b4/host/b4_gate_verify.py — the formal gate tool (unit 2b-4, the gate-tool half; the owner's ruling of
2026-10-19) on HERMETIC repository copies, MECHANICS FIXTURE SCHEDULES and SYNTHETIC SUMMARIES only. NO PRODUCTION SET IS
DERIVED HERE: for every class `b4_seeds.master_seed` and `b4_seeds.pair_seeds` are replaced by guards that raise, and the
class's teardown asserts they were never called. No b4-gate-1 set, no new b4-sim set. The real repository's namespaces are
never written. The committed S = 32 exploration report is read once, read-only, as a descriptive reference.

The judge (pure, on synthetic summaries): the PASS path with every row PASS; every row's FAIL on its own number, including
the boundaries written with an equal sign (K2 0.90, K4 57.6, K9 0.50, K10 0.50) and a +inf Cohen's d; no B* (the budget
rule FAILS, K1–K5 and K7 not assessable, K6 not assessable at S = 200, the gate cannot PASS); invalid / incomplete batches;
a summary that breaks its contract (invalid, never judged); the formal flag's reasons. End to end (hermetic): a valid FAIL
archive without B*, a synthetic PASS, an invalid archive (DOMAIN), an incomplete one (the deadline) — each judged into a
gate directory, verified in process and by the verifier CLI in a fresh process; the tampering negatives with every digest
refreshed, including the coordinated tamper that makes a gate report internally consistent but unsupported by the archive;
the refusals (labels, S, existing directories, exploration archives, production labels on synthetic evidence); the CLI's
guards. No K value is read as a result. No skip."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host", R / "b4/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_execution as ex  # noqa: E402
import b4_gate as bg  # noqa: E402
import b4_gate_verify as gv  # noqa: E402
import b4_k9 as k9  # noqa: E402
import b4_seeds as bs  # noqa: E402
import b4_sim as sim  # noqa: E402
import b4_sim_schema as sc  # noqa: E402
import b4_sim_verify as sv  # noqa: E402
import b4_thresholds as th  # noqa: E402
from b4_test_fixtures import InjectingPort  # noqa: E402
from test_b4_sim import SCHED1, Clock, build_hermetic, entry, git, production_derivation_reached, reindex  # noqa: E402

GRID = th.GRID
SIM3_REPORT = R / "evidence/b4/sim/b4-sim-3_20261019T121833Z/sim_report.json"      # the committed S = 32 exploration: read-only reference
SYN_LABEL = "b4-mech-7"


# ------------------------------------------------------------------ a synthetic summary shaped like summarise_batch's output
def _delta(mean, d, pos, neg, ties, p, var=4.0):
    return {"n": pos + neg + ties, "mean": mean, "median": mean, "positives": pos, "negatives": neg, "ties": ties, "sign_test_p": p,
            "population_variance": var, "cohen_d": {"value": d, "special": None}}


def _ratio(num, den):
    if den <= 0:
        return {"numerator": num, "denominator": den, "ratio": None, "readable": False, "note": "a non-positive denominator cannot be read as a ratio condition"}
    return {"numerator": num, "denominator": den, "ratio": num / den, "readable": True, "note": None}


def synthetic_summary(S=200, b_star=64, N=16, power=0.95) -> dict:
    """A PASS-shaped summary: K1 eligible at every budget, an N only at `b_star` (so it is the one eligible budget), delta1 with a
    clear positive effect, controls flat, Omega within the margin, K9 / K10 full. Every number is invented: it is a fixture of
    the judge's paths, never data."""
    T = th.THRESHOLDS
    per_budget = {}
    for B in GRID:
        n = N if B == b_star else None
        scan = [[k, 0.3] for k in range(8, S + 1)] if n is None else [[k, 0.3] for k in range(8, n)] + [[n, power]]
        per_budget[str(B)] = {
            "budget": B,
            "arm_values": {role: {"mean": 12.0, "median": 12.0, "min": 8, "max": 16} for role in sc.ROLES} | {"Omega": {"mean": 30.0, "median": 30.0, "min": 20, "max": 40}},
            "base": {"mean": 4.0, "median": 4.0}, "f_end_to_end": {"mean": 11.0, "median": 11.0, "mapping_in_progress": B <= 21},
            "deltas": {"delta1_O_minus_R": _delta(5.0, 0.9, 150, 20, 30, 1e-20), "delta2_O_minus_endtoend_F": _delta(1.0, 0.2, 90, 80, 30, 0.2),
                       "F_minus_R": _delta(5.0, 0.2, 150, 20, 30, 1e-20), "X_minus_R": _delta(0.1, 0.03, 60, 70, 70, 0.8), "D_minus_R": _delta(0.1, 0.03, 60, 70, 70, 0.6),
                       "Omega_minus_R": _delta(8.0, 1.5, 190, 5, 5, 1e-40), "A0_minus_R": _delta(0.0, 0.0, 50, 50, 100, 0.5)},
            "k1": {"omega_best_p95": 40.0, "median_best_R": 12.0, "median_base": 4.0, "eligibility": True},
            "required_pairs": {"N": n, "power_at_N_or_last": power if n is not None else 0.3, "scan": scan, "n_min": T["K5"]["n_min"], "n_max": S},
            "cost_N_x_3_x_B": None if n is None else n * 3 * B,
            "k7_O_prefix_not_unknown": {"values": [15] * S, "median": 15.0}}
    eligible = [B for B in GRID if per_budget[str(B)]["k1"]["eligibility"] and per_budget[str(B)]["required_pairs"]["N"] is not None]
    pb = per_budget[str(b_star)]
    dl = pb["deltas"]
    at = {"B_star": b_star, "N": N, "cost_N_x_3_x_B_star": pb["cost_N_x_3_x_B"],
          "k2": {"population_variance_delta1": 4.0, "budgets_with_both_signs": list(GRID), "x_minus_r_bootstrap_nonrejection": 0.97,
                 "bootstrap": {"N": N, "experiments": 1000, "alpha": 0.05, "seed": 7}},
          "k3": {"D_over_F": _ratio(dl["D_minus_R"]["mean"], dl["F_minus_R"]["mean"]), "X_over_O": _ratio(dl["X_minus_R"]["mean"], dl["delta1_O_minus_R"]["mean"]),
                 "D_sign_test_p": dl["D_minus_R"]["sign_test_p"], "X_sign_test_p": dl["X_minus_R"]["sign_test_p"]},
          "k4": {"median_best_Omega": 30.0, "mean_Omega_minus_R": 8.0, "mean_F_minus_R": 5.0, "F_over_Omega": _ratio(5.0, 8.0)},
          "k5": {"cohen_d_delta1": dl["delta1_O_minus_R"]["cohen_d"], "N": N, "cost": pb["cost_N_x_3_x_B"]},
          "k7": {"median_O_prefix_not_unknown": 15.0, "values": [15] * S}}
    k9s = {s: {"seeds_with_positive_control": S, "not_assessable_seeds": 0, "median_coverage_over_all_S": 1.0, "median_rule": T["K9"]["median_population"], "conditional_on_A8": s == "ff_init"}
           for s in k9.SEMANTICS}
    return {"S": S, "grid": list(GRID), "per_budget": per_budget, "eligible_budgets": eligible,
            "candidate_B_star": {"value": b_star, "reason_if_none": None, "note": T["B_star"]["no_eligible_budget"]}, "at_candidate_B_star": at,
            "k9": {"per_semantic": k9s, "seeds_with_all_seven_positive_controls": S, "fraction_of_S": 1.0},
            "k10": {"tau": 2, "S": S, "counts": {"interacting": S, "nonzero_below_threshold": 0, "no_interaction_seen_among_tested_comparisons": 0, "not_assessable": 0},
                    "fraction_interacting_over_S": 1.0, "note": "synthetic"},
            "thresholds_for_reference": T, "standing": "SYNTHETIC: invented numbers shaped like the harness's summary; a fixture of the judge's paths, never data"}


def no_b_star(summary: dict) -> dict:
    """The same summary with no N anywhere: the budget rule's candidate does not exist."""
    for B in GRID:
        v = summary["per_budget"][str(B)]
        v["required_pairs"]["N"] = None; v["required_pairs"]["power_at_N_or_last"] = 0.3; v["required_pairs"]["scan"] = [[k, 0.3] for k in range(8, summary["S"] + 1)]
        v["cost_N_x_3_x_B"] = None
    summary["eligible_budgets"] = []
    summary["candidate_B_star"] = {"value": None, "reason_if_none": "no grid budget has both K1 eligibility and an N: the budget rule's candidate does not exist on this S (not invented)", "note": th.THRESHOLDS["B_star"]["no_eligible_budget"]}
    summary["at_candidate_B_star"] = None
    return summary


def synthetic_doc(summary: dict | None, label=SYN_LABEL, S=200, status="complete", fixture=True) -> dict:
    return {"schema": bg.SYNTHETIC_SCHEMA[0], "schema_version": bg.SYNTHETIC_SCHEMA[1], "label": label, "fixture": fixture, "count": S, "status": status, "head": None,
            "summary": summary, "note": "SYNTHETIC summary: invented numbers shaped like the harness's pooled summary, a fixture of the judge's paths; never data, never a gate result",
            "generated_utc": "2026-10-19T00:00:00Z"}


def rows_by_id(j: dict) -> dict:
    return {r["id"]: r for r in j["rows"]}


# ------------------------------------------------------------------ the judge, pure
class TheJudge(unittest.TestCase):
    def test_a_pass_shaped_synthetic_summary_passes_every_row_but_is_never_formal(self):
        j = bg.judge(synthetic_doc(synthetic_summary()), "synthetic_summary")
        self.assertEqual([r["status"] for r in j["rows"]], ["PASS"] * 10)
        self.assertEqual([r["id"] for r in j["rows"]], list(bg.K_IDS))
        self.assertEqual((j["budget_rule"]["status"], j["budget_rule"]["B_star"], j["budget_rule"]["N"], j["budget_rule"]["cost_N_x_3_x_B_star"]), ("PASS", 64, 16, 3072))
        self.assertEqual(j["verdict"]["status"], "PASS")
        self.assertFalse(j["formal"]); self.assertIn("NOT a gate result", j["verdict"]["reason"])
        self.assertEqual(len(j["formal_reasons"]), 3, j["formal_reasons"])          # the evidence kind, the fixture, the label
        self.assertTrue(any("synthetic_summary" in x for x in j["formal_reasons"]) and any("fixture" in x for x in j["formal_reasons"]) and any("pinned gate label" in x for x in j["formal_reasons"]))
        rows = rows_by_id(j)
        self.assertEqual(rows["K5"]["value"]["N"], 16); self.assertEqual(rows["K5"]["value"]["cohen_d_delta1"], {"value": 0.9, "special": None})
        self.assertEqual(rows["K6"]["value"], {"S_planned": 200, "N": 16})
        for r in j["rows"]:
            self.assertTrue(r["method"] and r["criterion"] and r["reason"], r["id"])

    def test_the_formal_identity_on_a_pure_document(self):
        """The judge's formal flag on a document that carries the production identity (no file is involved: the verifier binds the files)."""
        d = synthetic_doc(synthetic_summary(), label=bg.PINNED_GATE_LABEL, fixture=False)
        j = bg.judge(d, "batch_archive")
        self.assertTrue(j["formal"]); self.assertEqual(j["formal_reasons"], []); self.assertEqual(j["verdict"]["status"], "PASS"); self.assertNotIn("NOT", j["verdict"]["reason"])
        for kind, over in (("synthetic_summary", {}), ("batch_archive", {"fixture": True}), ("batch_archive", {"label": "b4-gate-2"}), ("batch_archive", {"count": 199}), ("batch_archive", {"status": "invalid"})):
            dd = dict(d, **over)
            self.assertFalse(bg.judge(dd, kind)["formal"], (kind, over))

    def test_each_row_fails_on_its_own_number_and_the_verdict_names_it(self):
        def case(mutate, rid, reason_part):
            s = synthetic_summary()
            mutate(s)
            j = bg.judge(synthetic_doc(s), "synthetic_summary")
            self.assertEqual(j["contract_findings"], [], (rid, reason_part))
            rows = rows_by_id(j)
            self.assertEqual(rows[rid]["status"], "FAIL", (rid, reason_part, rows[rid]["reason"]))
            self.assertIn(reason_part, rows[rid]["reason"], rid)
            self.assertEqual([r["id"] for r in j["rows"] if r["status"] != "PASS"], [rid], (rid, reason_part))
            self.assertEqual(j["verdict"]["status"], "FAIL"); self.assertIn(f"{rid} FAILS", j["verdict"]["reason"]); self.assertIn("no threshold is adjusted", j["verdict"]["reason"])
        at = lambda s: s["at_candidate_B_star"]  # noqa: E731
        case(lambda s: at(s)["k2"].__setitem__("population_variance_delta1", 0.0), "K2", "variance")
        case(lambda s: at(s)["k2"].__setitem__("budgets_with_both_signs", []), "K2", "both positive and negative")
        case(lambda s: at(s)["k2"].__setitem__("x_minus_r_bootstrap_nonrejection", 0.899), "K2", "non-rejection")
        case(lambda s: at(s)["k3"].__setitem__("D_over_F", _ratio(0.6, 5.0)), "K3", "D / F ratio")
        case(lambda s: at(s)["k3"].__setitem__("D_over_F", _ratio(-0.1, 0.0)), "K3", "non-positive denominator")
        case(lambda s: at(s)["k3"].__setitem__("X_over_O", _ratio(0.6, 5.0)), "K3", "X / O ratio")
        case(lambda s: at(s)["k3"].__setitem__("D_sign_test_p", 0.05), "K3", "D_sign_test_p")
        case(lambda s: at(s)["k3"].__setitem__("X_sign_test_p", 0.01), "K3", "X_sign_test_p")
        case(lambda s: at(s)["k4"].__setitem__("median_best_Omega", 57.7), "K4", "57.6")
        case(lambda s: at(s)["k4"].__setitem__("F_over_Omega", _ratio(3.9, 8.0)), "K4", "F / Omega ratio")
        case(lambda s: at(s)["k4"].__setitem__("F_over_Omega", _ratio(5.0, 0.0)), "K4", "non-positive denominator")
        case(lambda s: at(s)["k5"].__setitem__("cohen_d_delta1", {"value": 0.49, "special": None}), "K5", "Cohen's d")
        case(lambda s: at(s)["k5"].__setitem__("cohen_d_delta1", {"value": None, "special": "-inf"}), "K5", "-inf")
        case(lambda s: s["per_budget"]["64"]["required_pairs"].__setitem__("power_at_N_or_last", 0.899), "K5", "power")
        case(lambda s: at(s)["k7"].__setitem__("median_O_prefix_not_unknown", 10.0), "K7", "< 11")
        case(lambda s: s["k9"].__setitem__("fraction_of_S", 0.899), "K9", "(a)")
        case(lambda s: s["k9"]["per_semantic"]["ff_srval"].__setitem__("median_coverage_over_all_S", 0.4270833), "K9", "ff_srval 0.427083")
        case(lambda s: s["k9"]["per_semantic"]["sr_kind"].update(median_coverage_over_all_S=None, not_assessable_seeds=3), "K9", "not assessable: sr_kind (3 seeds")
        case(lambda s: (s["k10"].__setitem__("fraction_interacting_over_S", 0.495), s["k10"]["counts"].update(interacting=99, not_assessable=101)), "K10", "< 0.50")
        # the cap: N = 21 at B* = 64 is 4 032 search evaluations
        def cap(s):
            v = s["per_budget"]["64"]; v["required_pairs"]["N"] = 21; v["required_pairs"]["scan"] = [[k, 0.3] for k in range(8, 21)] + [[21, 0.95]]; v["cost_N_x_3_x_B"] = 21 * 3 * 64
            at(s).update(N=21, cost_N_x_3_x_B_star=21 * 3 * 64); at(s)["k5"].update(N=21, cost=21 * 3 * 64); at(s)["k2"]["bootstrap"]["N"] = 21
        case(cap, "K5", "4 000")

    def test_the_boundaries_written_with_an_equal_sign_pass_and_an_infinite_d_passes(self):
        s = synthetic_summary()
        at = s["at_candidate_B_star"]
        at["k2"]["x_minus_r_bootstrap_nonrejection"] = 0.90
        at["k4"]["median_best_Omega"] = 57.6; at["k4"]["F_over_Omega"] = _ratio(4.0, 8.0)
        at["k3"]["D_over_F"] = _ratio(0.5, 5.0); at["k3"]["X_over_O"] = _ratio(0.5, 5.0)
        at["k5"]["cohen_d_delta1"] = {"value": None, "special": "+inf"}
        s["per_budget"]["64"]["required_pairs"]["power_at_N_or_last"] = 0.90
        at["k7"]["median_O_prefix_not_unknown"] = 11.0
        s["k9"]["fraction_of_S"] = 0.90; s["k9"]["seeds_with_all_seven_positive_controls"] = 180
        for sem in k9.SEMANTICS:
            s["k9"]["per_semantic"][sem]["median_coverage_over_all_S"] = 0.5
        s["k10"]["fraction_interacting_over_S"] = 0.5; s["k10"]["counts"].update(interacting=100, not_assessable=100)
        j = bg.judge(synthetic_doc(s), "synthetic_summary")
        self.assertEqual(j["contract_findings"], [])
        self.assertEqual([r["status"] for r in j["rows"]], ["PASS"] * 10, [(r["id"], r["reason"]) for r in j["rows"] if r["status"] != "PASS"])
        self.assertEqual(j["verdict"]["status"], "PASS")
        self.assertEqual(rows_by_id(j)["K5"]["value"]["cohen_d_delta1"], {"value": None, "special": "+inf"}, "a legitimate +inf d is kept as such, never as 0")

    def test_k5_is_delta1_o_minus_r_not_f_minus_r(self):
        s = synthetic_summary()
        s["per_budget"]["64"]["deltas"]["F_minus_R"]["cohen_d"] = {"value": 0.1, "special": None}        # F - R weak, delta1 strong: K5 PASSES
        j = bg.judge(synthetic_doc(s), "synthetic_summary")
        self.assertEqual(rows_by_id(j)["K5"]["status"], "PASS")
        s["at_candidate_B_star"]["k5"]["cohen_d_delta1"] = {"value": 0.1, "special": None}                 # delta1 weak: K5 FAILS whatever F - R
        s["per_budget"]["64"]["deltas"]["delta1_O_minus_R"]["cohen_d"] = {"value": 0.1, "special": None}
        s["per_budget"]["64"]["deltas"]["F_minus_R"]["cohen_d"] = {"value": 2.0, "special": None}
        self.assertEqual(rows_by_id(bg.judge(synthetic_doc(s), "synthetic_summary"))["K5"]["status"], "FAIL")

    def test_k6_fails_when_s_is_not_the_planned_200(self):
        j = bg.judge(synthetic_doc(synthetic_summary(S=199), S=199), "synthetic_summary")
        rows = rows_by_id(j)
        self.assertEqual((rows["K6"]["status"], rows["K6"]["value"]), ("FAIL", {"S_planned": 199, "N": 16})); self.assertIn("199", rows["K6"]["reason"])
        self.assertEqual(j["verdict"]["status"], "FAIL"); self.assertIn("K6 FAILS", j["verdict"]["reason"])
        self.assertIn("S = 199 is not the planned 200", j["formal_reasons"])

    def test_no_b_star_leaves_the_dependent_rows_not_assessable_and_the_gate_cannot_pass(self):
        j = bg.judge(synthetic_doc(no_b_star(synthetic_summary())), "synthetic_summary")
        self.assertEqual(j["contract_findings"], [])
        br = j["budget_rule"]
        self.assertEqual((br["status"], br["B_star"], br["N"], br["cost_N_x_3_x_B_star"], br["eligible_budgets"]), ("FAIL", None, None, None, []))
        self.assertIn("not invented", br["reason"]); self.assertIn("cannot PASS", br["reason"])
        self.assertEqual(br["k1_eligibility_by_budget"], {str(B): True for B in GRID}); self.assertEqual(br["N_by_budget"], {str(B): None for B in GRID})
        st = {r["id"]: r["status"] for r in j["rows"]}
        self.assertEqual(st, {"K1": "not_assessable", "K2": "not_assessable", "K3": "not_assessable", "K4": "not_assessable", "K5": "not_assessable", "K6": "not_assessable",
                              "K7": "not_assessable", "K8": "PASS", "K9": "PASS", "K10": "PASS"})
        rows = rows_by_id(j)
        self.assertIn("no B*", rows["K2"]["reason"]); self.assertIn("(b) needs B*", rows["K7"]["reason"]); self.assertEqual(rows["K7"]["value"]["a_recomputation_mismatches"], 0)
        self.assertIn("N does not exist", rows["K6"]["reason"]); self.assertEqual(rows["K6"]["value"], {"S_planned": 200, "N": None})
        self.assertEqual(j["verdict"]["status"], "FAIL"); self.assertIn("budget rule FAILS", j["verdict"]["reason"]); self.assertIn("not assessable: K1, K2, K3, K4, K5, K6, K7", j["verdict"]["reason"])
        # with S != 200 and no B*, K6 FAILS outright
        j2 = bg.judge(synthetic_doc(no_b_star(synthetic_summary(S=32)), S=32), "synthetic_summary")
        self.assertEqual(rows_by_id(j2)["K6"]["status"], "FAIL")

    def test_an_invalid_or_incomplete_batch_is_that_verdict_with_nothing_judged(self):
        for status in ("invalid", "incomplete"):
            j = bg.judge(synthetic_doc(None, status=status), "synthetic_summary")
            self.assertEqual(j["verdict"]["status"], status, status)
            self.assertEqual([r["status"] for r in j["rows"]], ["not_assessable"] * 10)
            self.assertEqual(j["budget_rule"]["status"], "not_assessable"); self.assertFalse(j["formal"])
            self.assertIn(status, j["rows"][0]["reason"])
        self.assertIn("contract break", bg.judge(synthetic_doc(None, status="invalid"), "synthetic_summary")["verdict"]["reason"])
        self.assertIn("unfinished", bg.judge(synthetic_doc(None, status="incomplete"), "synthetic_summary")["verdict"]["reason"])

    def test_a_summary_that_breaks_its_contract_is_invalid_never_judged(self):
        def case(mutate, part):
            s = synthetic_summary()
            mutate(s)
            j = bg.judge(synthetic_doc(s), "synthetic_summary")
            self.assertEqual(j["verdict"]["status"], "invalid", part)
            self.assertTrue(any(part in x for x in j["contract_findings"]), (part, j["contract_findings"]))
            self.assertEqual([r["status"] for r in j["rows"]], ["not_assessable"] * 10, part)
        case(lambda s: s["per_budget"]["64"].__setitem__("cost_N_x_3_x_B", 3000), "N x 3 x B")
        case(lambda s: s["per_budget"]["32"]["k1"].__setitem__("eligibility", False) or s["per_budget"]["32"]["k1"].__setitem__("omega_best_p95", 40.0), "eligibility is not the one of its own numbers")
        case(lambda s: s["candidate_B_star"].__setitem__("value", 32), "cheapest eligible")
        case(lambda s: s["at_candidate_B_star"].__setitem__("N", 15), "B* / N / cost")
        case(lambda s: s.__setitem__("eligible_budgets", [64, 96]), "eligible_budgets")
        case(lambda s: s["per_budget"].pop("8"), "exactly the grid budgets")
        case(lambda s: s["k10"]["counts"].__setitem__("interacting", 150), "do not sum to S")
        case(lambda s: s["k9"]["per_semantic"]["ff_init"].__setitem__("median_coverage_over_all_S", None), "exactly when a seed is not assessable")
        case(lambda s: s.__setitem__("S", 201), "summary.S")
        def two(s):
            s["per_budget"]["32"]["required_pairs"]["N"] = 8; s["per_budget"]["32"]["required_pairs"]["scan"] = [[8, 0.95]]; s["per_budget"]["32"]["cost_N_x_3_x_B"] = 8 * 3 * 32   # cheaper (768) than 64's 3 072
            s["eligible_budgets"] = [32, 64]
        case(two, "cheapest eligible budget 32")
        j = bg.judge(synthetic_doc({"S": 200}), "synthetic_summary")
        self.assertEqual(j["verdict"]["status"], "invalid"); self.assertTrue(j["contract_findings"])
        j = bg.judge(synthetic_doc(None, status="complete"), "synthetic_summary")
        self.assertEqual(j["verdict"]["status"], "invalid")
        with self.assertRaises(ValueError):
            bg.judge(synthetic_doc(synthetic_summary()), "other")

    def test_the_committed_exploration_report_as_a_read_only_reference(self):
        """The S = 32 exploration of 2026-10-19 judged in memory: not formal (an exploration label, S = 32), the budget rule FAILS (no N),
        K6 FAILS on S, K9 FAILS on ff_srval's median 0.427083, K8 / K10 PASS. Nothing is written; the archive is not touched."""
        before = SIM3_REPORT.read_bytes()
        j = bg.judge(json.loads(before), "batch_archive")
        self.assertEqual(SIM3_REPORT.read_bytes(), before)
        self.assertFalse(j["formal"]); self.assertEqual(len(j["formal_reasons"]), 2)
        self.assertEqual(j["contract_findings"], [])
        self.assertEqual(j["budget_rule"]["status"], "FAIL"); self.assertEqual(j["budget_rule"]["k1_eligibility_by_budget"], {str(B): True for B in GRID})
        st = {r["id"]: r["status"] for r in j["rows"]}
        self.assertEqual(st, {"K1": "not_assessable", "K2": "not_assessable", "K3": "not_assessable", "K4": "not_assessable", "K5": "not_assessable", "K6": "FAIL",
                              "K7": "not_assessable", "K8": "PASS", "K9": "FAIL", "K10": "PASS"})
        rows = rows_by_id(j)
        self.assertIn("ff_srval 0.427083", rows["K9"]["reason"]); self.assertNotIn("sr_kind", rows["K9"]["reason"], "sr_kind's median 0.5 meets the >= 0.50 written with an equal sign")
        self.assertEqual(rows["K9"]["value"]["per_semantic"]["sr_kind"]["median_coverage_over_all_S"], 0.5)
        self.assertEqual(rows["K10"]["value"]["counts"]["interacting"], 32)
        self.assertEqual(j["verdict"]["status"], "FAIL")

    def test_standing_for_the_harness_s_labels(self):
        self.assertEqual(sim.standing_for("b4-sim-3"), sim.STANDING); self.assertEqual(sim.standing_for("b4-mech-1"), sim.STANDING)
        self.assertEqual(sim.standing_for("b4-gate-1"), sim.STANDING_GATE); self.assertNotEqual(sim.STANDING_GATE, sim.STANDING)
        self.assertIn("not a gate verdict", sim.STANDING_GATE); self.assertIn("b4_gate.py", sim.STANDING_GATE)
        self.assertIn("v0.1.15", sim.STANDING, "the archived explorations' text is never edited")
        self.assertEqual(sc.report_findings(json.loads(SIM3_REPORT.read_bytes())), [], "the committed exploration report still validates")

    def test_the_synthetic_summary_s_own_findings(self):
        d = synthetic_doc(synthetic_summary())
        self.assertEqual(bg.synthetic_findings(d), [])
        self.assertTrue(any("b4-mech" in x for x in bg.synthetic_findings(dict(d, label=bg.PINNED_GATE_LABEL))))
        self.assertTrue(any("b4-mech" in x for x in bg.synthetic_findings(dict(d, label="b4-sim-9"))))
        self.assertTrue(bg.synthetic_findings(dict(d, fixture=False)))
        self.assertTrue(any("synthetic" in x for x in bg.synthetic_findings(dict(d, note="numbers"))))
        self.assertTrue(bg.synthetic_findings(dict(d, status="done")))
        self.assertTrue(bg.synthetic_findings(dict(d, summary=None)))
        self.assertTrue(bg.synthetic_findings(dict(d, status="invalid")))
        self.assertTrue(bg.synthetic_findings({k: v for k, v in d.items() if k != "note"}))


# ------------------------------------------------------------------ end to end on a hermetic copy
class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guards = [mock.patch.object(bs, "master_seed", side_effect=production_derivation_reached), mock.patch.object(bs, "pair_seeds", side_effect=production_derivation_reached)]
        cls.guard_mocks = [g.start() for g in cls.guards]
        cls.tmp = tempfile.TemporaryDirectory(prefix="b4gate_")
        cls.root = build_hermetic(Path(cls.tmp.name))
        cls.ns = cls.root / sim.SIM_REL
        cls.gns = cls.root / bg.GATE_REL
        cls.counter = 0

    @classmethod
    def tearDownClass(cls):
        try:
            calls = [m.call_count for m in cls.guard_mocks]
            for g in cls.guards:
                g.stop()
            assert calls == [0, 0], f"a production derivation was attempted from {cls.__name__}: {calls}"
        finally:
            cls.tmp.cleanup()

    @classmethod
    def commit(cls):
        if git(cls.root, "status", "--porcelain").strip():
            git(cls.root, "add", "-A"); git(cls.root, "commit", "-q", "-m", "archive")

    def tearDown(self):
        self.commit()

    def nxt(self, label="b4-mech-1") -> str:
        type(self).counter += 1
        return f"{label}_t{type(self).counter:03d}"

    @staticmethod
    def fresh(gate_dir: Path, shallow=False) -> tuple[int, dict]:
        p = subprocess.run([sys.executable, "-B", str(R / "b4/host/b4_gate_verify.py"), str(gate_dir)] + (["--shallow"] if shallow else []), capture_output=True, text=True)
        try:
            return p.returncode, json.loads(p.stdout)
        except ValueError:
            return p.returncode, {"stdout": p.stdout, "stderr": p.stderr}


def regate(gate_dir: Path) -> None:
    """After a tamper of gate_report.json: re-render the markdown and refresh the file index, so the verifier's finding, if any,
    comes from the contract and not from a stale digest (the owner's probe method)."""
    doc = json.loads((gate_dir / bg.REPORT_JSON).read_text())
    (gate_dir / bg.REPORT_MD).write_bytes(bg.render_md(doc).encode("utf-8"))
    doc["files"] = [entry(gate_dir / e["path"], e["path"]) for e in doc["files"]]
    (gate_dir / bg.REPORT_JSON).write_bytes(sim.json_text(doc))


class EndToEnd(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.a = bg.run_gate(cls.root, "b4-mech-1", 2, 3600, out_batch=cls.ns / "b4-mech-1_fail", out_gate=cls.gns / "b4-mech-1_fail", schedule=SCHED1)
        cls.commit()
        cls.b = bg.judge_synthetic(cls.root, synthetic_doc(synthetic_summary()), cls.gns / f"{SYN_LABEL}_pass")
        cls.commit()

        def domain(fabric, role, pair):
            return InjectingPort(fabric, 30) if (pair, role) == (1, "O") else ex.ObservationPort(fabric)
        cls.c = bg.run_gate(cls.root, "b4-mech-1", 2, 3600, out_batch=cls.ns / "b4-mech-1_invalid", out_gate=cls.gns / "b4-mech-1_invalid", schedule=SCHED1, port_factory=domain)
        cls.commit()
        cls.d = bg.run_gate(cls.root, "b4-mech-1", 2, 60, out_batch=cls.ns / "b4-mech-1_incomplete", out_gate=cls.gns / "b4-mech-1_incomplete", schedule=SCHED1, clock=Clock(step=1.0))
        cls.commit()
        cls.originals = {}
        for res in (cls.a, cls.b, cls.c, cls.d):
            if res.get("gate_out"):
                g = Path(res["gate_out"])
                cls.originals[g] = {p.name: p.read_bytes() for p in g.iterdir() if p.is_file()}
        ba = cls.ns / "b4-mech-1_fail"
        cls.originals[ba] = {str(p.relative_to(ba)): p.read_bytes() for p in ba.rglob("*") if p.is_file()}

    def restore(self, d: Path):
        for rel, b in self.originals[d].items():
            p = d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists() or p.read_bytes() != b:
                p.write_bytes(b)
        for p in list(d.rglob("*")):
            if p.is_file() and str(p.relative_to(d)) not in self.originals[d]:
                p.unlink()

    def findings(self, gate_dir: Path, *restore: Path, deep=True) -> dict:
        try:
            return gv.verify_gate_dir(gate_dir, deep=deep)
        finally:
            for d in (gate_dir,) + restore:
                self.restore(d)

    def test_a_valid_fail_archive_without_b_star_is_judged_fail_and_verifies_clean(self):
        res = self.a
        self.assertEqual((res["status"], res["exit_code"]), ("FAIL", 0), res.get("reason"))
        self.assertEqual(res["batch"]["status"], "complete")
        g, b = Path(res["gate_out"]), Path(res["out"])
        self.assertEqual(sorted(p.name for p in g.iterdir()), [bg.REPORT_JSON, bg.REPORT_MD])
        doc = json.loads((g / bg.REPORT_JSON).read_text())
        self.assertEqual(bg.gate_report_findings(doc), [])
        self.assertEqual((doc["verdict"]["status"], doc["formal"], doc["fixture"], doc["evidence_kind"], doc["label"], doc["S"]), ("FAIL", False, True, "batch_archive", "b4-mech-1", 2))
        self.assertIn("NOT A GATE RESULT", doc["standing"]); self.assertEqual(doc["scope"], bg.SCOPE)
        self.assertEqual(doc["batch"]["path"], str(b.relative_to(self.root))); self.assertEqual(doc["batch"]["sha256"], sim.sha_file(b / "sim_report.json"))
        self.assertEqual((doc["batch"]["seeds_sha256"], doc["batch"]["manifest_sha256"]), (sim.sha_file(b / "seeds.json"), sim.sha_file(b / "manifest.json")))
        self.assertEqual(doc["budget_rule"]["status"], "FAIL"); self.assertEqual(doc["budget_rule"]["N_by_budget"], {str(B): None for B in GRID})
        st = {r["id"]: r["status"] for r in doc["rows"]}
        self.assertEqual(st["K8"], "PASS"); self.assertEqual(st["K6"], "FAIL"); self.assertEqual(st["K1"], "not_assessable"); self.assertEqual(st["K5"], "not_assessable")
        self.assertIn(st["K9"], ("PASS", "FAIL")); self.assertIn(st["K10"], ("PASS", "FAIL"))            # values of the model on two fixture pairs: read as the tool's path, never as a result
        self.assertEqual(doc["self_validation"], {}); self.assertEqual(doc["contract_findings"], [])
        self.assertTrue(doc["clean_tree"], "the tree carried nothing but the batch's own output when the judgement was written")
        self.assertEqual(doc["thresholds"], th.THRESHOLDS); self.assertEqual(doc["identity"]["hypothesis_sha256"], th.THRESHOLDS["anchor"]["hypothesis_sha256"])
        self.assertEqual([e["path"] for e in doc["files"]], [bg.REPORT_MD]); self.assertEqual(doc["files"][0]["sha256"], sim.sha_file(g / bg.REPORT_MD))
        self.assertEqual((g / bg.REPORT_MD).read_bytes(), bg.render_md(doc).encode("utf-8"))
        md = (g / bg.REPORT_MD).read_text()
        self.assertIn("**FAIL** (NOT A GATE RESULT)", md); self.assertIn("| K9 |", md); self.assertIn("no threshold is adjusted", md)
        # the batch archive is a harness archive: the exploration standing for a mechanics label, no verdict key, the verifier clean
        rep = json.loads((b / "sim_report.json").read_text())
        self.assertEqual(rep["standing"], sim.STANDING); self.assertEqual(sc.report_findings(rep), []); self.assertEqual(sv.verify_run_dir(b, deep=True), {})
        self.assertEqual(gv.verify_gate_dir(g, deep=True), {})
        code, out = self.fresh(g)
        self.assertEqual((code, out.get("clean"), out.get("findings")), (0, True, {}), out)
        self.assertIn("never a gate result", out["limit"])
        self.assertEqual([m.call_count for m in self.guard_mocks], [0, 0])

    def test_a_synthetic_pass_is_judged_pass_never_formal_and_verifies_clean(self):
        res = self.b
        self.assertEqual((res["status"], res["exit_code"]), ("PASS", 0), res.get("reason"))
        g = Path(res["gate_out"])
        self.assertEqual(sorted(p.name for p in g.iterdir()), [bg.REPORT_JSON, bg.REPORT_MD, bg.SYNTHETIC_JSON])
        doc = json.loads((g / bg.REPORT_JSON).read_text())
        self.assertEqual(bg.gate_report_findings(doc), [])
        self.assertEqual((doc["verdict"]["status"], doc["formal"], doc["fixture"], doc["evidence_kind"], doc["label"], doc["S"]), ("PASS", False, True, "synthetic_summary", SYN_LABEL, 200))
        self.assertEqual([r["status"] for r in doc["rows"]], ["PASS"] * 10)
        self.assertIn("NOT A GATE RESULT", doc["standing"]); self.assertIn("NOT a gate result", doc["verdict"]["reason"])
        self.assertEqual(doc["batch"]["path"], f"{bg.GATE_REL}/{g.name}/{bg.SYNTHETIC_JSON}"); self.assertEqual(doc["batch"]["sha256"], sim.sha_file(g / bg.SYNTHETIC_JSON))
        self.assertEqual((doc["batch"]["seeds_sha256"], doc["batch"]["manifest_sha256"]), (None, None))
        self.assertEqual([e["path"] for e in doc["files"]], [bg.REPORT_MD, bg.SYNTHETIC_JSON])
        self.assertIn("**PASS** (NOT A GATE RESULT)", (g / bg.REPORT_MD).read_text())
        self.assertEqual(gv.verify_gate_dir(g), {})
        code, out = self.fresh(g)
        self.assertEqual((code, out["findings"]), (0, {}), out)

    def test_an_invalid_and_an_incomplete_batch_are_those_verdicts(self):
        c, d = self.c, self.d
        self.assertEqual((c["status"], c["exit_code"], c["batch"]["status"]), ("invalid", 1, "invalid"), c.get("reason"))
        self.assertEqual((d["status"], d["exit_code"], d["batch"]["status"]), ("incomplete", 3, "incomplete"), d.get("reason"))
        for res, status in ((c, "invalid"), (d, "incomplete")):
            g = Path(res["gate_out"])
            doc = json.loads((g / bg.REPORT_JSON).read_text())
            self.assertEqual(bg.gate_report_findings(doc), [])
            self.assertEqual((doc["verdict"]["status"], doc["batch"]["status"], doc["formal"]), (status, status, False))
            self.assertEqual([r["status"] for r in doc["rows"]], ["not_assessable"] * 10); self.assertEqual(doc["budget_rule"]["status"], "not_assessable")
            self.assertEqual(doc["diagnostics"].get("per_budget"), None, "no pooled summary: no per-budget diagnostics")
            self.assertEqual(gv.verify_gate_dir(g), {}, "an archive that recorded its own stop verifies as the archive of that state; the judgement follows")
            code, out = self.fresh(g)
            self.assertEqual((code, out["findings"]), (0, {}), out)
            rep = json.loads((Path(res["out"]) / "sim_report.json").read_text())
            self.assertEqual(rep["status"], status); self.assertIsNone(rep["summary"])
        self.assertEqual(json.loads((Path(c["out"]) / "sim_report.json").read_text())["stopped"]["kind"], "domain")
        self.assertEqual(json.loads((Path(d["out"]) / "sim_report.json").read_text())["stopped"]["kind"], "deadline")

    def test_every_tamper_of_the_gate_report_is_named_with_the_digests_refreshed(self):
        g = Path(self.a["gate_out"])
        load = lambda: json.loads(self.originals[g][bg.REPORT_JSON])  # noqa: E731

        def put(doc):
            (g / bg.REPORT_JSON).write_bytes(sim.json_text(doc)); regate(g)

        def tamper(mutate, where_part, msg_part, deep=False):
            doc = load(); mutate(doc); put(doc)
            f = self.findings(g, deep=deep)
            self.assertTrue(f, (where_part, msg_part))
            self.assertTrue(any(where_part in k and any(msg_part in m for m in v) for k, v in f.items()), (where_part, msg_part, f))
        # a row's status alone (the verdict kept): the rows are recomputed
        tamper(lambda d: d["rows"][8].__setitem__("status", "PASS"), bg.REPORT_JSON, "rows are not the ones recomputed")
        # the verdict alone: PASS with a failing row is refused by the validator; FAIL -> incomplete by the validator
        tamper(lambda d: d["verdict"].__setitem__("status", "PASS"), bg.REPORT_JSON, "verdict PASS with")
        tamper(lambda d: d["verdict"].__setitem__("status", "incomplete"), bg.REPORT_JSON, "incomplete on a complete batch")
        # the coordinated internal tamper: every row PASS, the budget rule PASS with invented B* / N, the verdict PASS — internally consistent, refused by the recomputation
        def coordinated(d):
            for r in d["rows"]:
                r["status"] = "PASS"
            d["budget_rule"].update(status="PASS", B_star=64, N=16, cost_N_x_3_x_B_star=3072, eligible_budgets=[64])
            d["verdict"] = {"status": "PASS", "reason": "x"}
        tamper(coordinated, bg.REPORT_JSON, "budget rule is not the one recomputed")
        # formal claimed: the validator refuses a fixture as formal; reasons emptied with the flag: still a fixture
        tamper(lambda d: d.update(formal=True, formal_reasons=[]), bg.REPORT_JSON, "a formal judgement is a production batch archive")
        tamper(lambda d: d.update(formal_reasons=["x"]), bg.REPORT_JSON, "formal / formal_reasons are not the ones recomputed")
        tamper(lambda d: d.__setitem__("standing", bg.STANDING_FORMAL), bg.REPORT_JSON, "standing")
        tamper(lambda d: d["thresholds"]["K9"].__setitem__("median_coverage_per_semantic_min", 0.40), bg.REPORT_JSON, "thresholds")
        tamper(lambda d: d["batch"].__setitem__("sha256", "0" * 64), "batch", "does not hash")
        tamper(lambda d: d["batch"].__setitem__("seeds_sha256", "1" * 64), "batch", "seeds.json does not hash")
        tamper(lambda d: d["batch"].__setitem__("generated_utc", "2026-01-01T00:00:00Z"), "batch", "identity")
        tamper(lambda d: d["batch"].__setitem__("path", f"{sim.SIM_REL}/b4-mech-1_invalid"), "batch", "does not hash")
        tamper(lambda d: d["batch"].__setitem__("path", f"{sim.SIM_REL}/b4-sim-9_x"), "batch", "with the judged label")
        tamper(lambda d: d.__setitem__("rows", d["rows"][::-1]), bg.REPORT_JSON, "K1 .. K10 in order")
        tamper(lambda d: d.__setitem__("self_validation", {"x": ["y"]}), bg.REPORT_JSON, "self-validation")
        tamper(lambda d: d["diagnostics"].__setitem__("per_budget", {}), bg.REPORT_JSON, "diagnostics")
        tamper(lambda d: d.__setitem__("evidence_kind", "synthetic_summary"), bg.REPORT_JSON, "evidence record")
        # a self-validation record with the verdict made invalid consistently: never clean
        def self_inv(d):
            d["self_validation"] = {"batch: x": ["y"]}; d["verdict"] = {"status": "invalid", "reason": "self"}
        tamper(self_inv, bg.REPORT_JSON, "never clean")
        # the markdown alone, an extra file, a .part, a missing markdown
        (g / bg.REPORT_MD).write_bytes(self.originals[g][bg.REPORT_MD] + b"\n")
        f = self.findings(g); self.assertIn("digest / size are not the index's", f[bg.REPORT_MD][0])
        (g / bg.REPORT_MD).write_bytes(self.originals[g][bg.REPORT_MD] + b"\n")                       # the same with the index refreshed: the rendering is bound
        doc = load(); doc["files"] = [entry(g / e["path"], e["path"]) for e in doc["files"]]; (g / bg.REPORT_JSON).write_bytes(sim.json_text(doc))
        f = self.findings(g); self.assertEqual(f, {bg.REPORT_MD: ["not the rendering of gate_report.json"]})
        (g / "note.txt").write_text("x"); f = self.findings(g); self.assertIn("not a file of a gate directory", f["note.txt"][0])
        (g / "gate_report.json.1.part").write_text("x"); f = self.findings(g); self.assertIn("unfinished", f["gate_report.json.1.part"][0])
        (g / bg.REPORT_MD).unlink(); f = self.findings(g); self.assertEqual(f[bg.REPORT_MD], ["missing"])
        (g / bg.REPORT_JSON).unlink(); f = self.findings(g); self.assertEqual(f[bg.REPORT_JSON], ["missing"])
        self.assertEqual(gv.verify_gate_dir(g), {}, "restored")

    def test_the_coordinated_tamper_of_the_evidence_is_caught_by_the_archive_re_verification(self):
        """The batch's pooled summary changed (K10 to 0 / 2 interacting), every digest refreshed, the gate report re-judged from the
        tampered report so that it is internally consistent: the shallow verification is clean, the deep one names the archive —
        clean evidence and a passing (or failing) criterion are two different things."""
        g, b = Path(self.a["gate_out"]), self.ns / "b4-mech-1_fail"
        rep = json.loads(self.originals[b]["sim_report.json"])
        rep["summary"]["k10"]["counts"].update(interacting=0, not_assessable=2); rep["summary"]["k10"]["fraction_interacting_over_S"] = 0.0
        (b / "sim_report.json").write_bytes(sim.json_text(rep)); reindex(b)
        rep = json.loads((b / "sim_report.json").read_text())
        j = bg.judge(rep, "batch_archive")
        self.assertEqual(rows_by_id(j)["K10"]["status"], "FAIL")
        doc = json.loads(self.originals[g][bg.REPORT_JSON])
        doc.update(budget_rule=j["budget_rule"], rows=j["rows"], verdict=j["verdict"], diagnostics=bg._diagnostics(rep, "batch_archive"))
        doc["batch"].update(sha256=sim.sha_file(b / "sim_report.json"), generated_utc=rep["generated_utc"])
        (g / bg.REPORT_JSON).write_bytes(sim.json_text(doc)); regate(g)
        shallow = gv.verify_gate_dir(g, deep=False)
        self.assertEqual(shallow, {}, "internally consistent: the shallow verification cannot tell")
        deep = self.findings(g, b, deep=True)
        self.assertTrue(any(k.startswith("batch: ") and any("summary is not the one recomputed" in m for m in v) for k, v in deep.items()), deep)
        self.assertEqual(gv.verify_gate_dir(g, deep=True), {}, "restored")
        # a tampered raw readout inside the archive (a curve value) with the pair index and the report index refreshed: named under batch:
        cv = json.loads(self.originals[b]["pair_000/curves.json"]); cv["best_at_grid"]["O"][-1] += 1
        (b / "pair_000/curves.json").write_bytes(sim.json_text(cv)); reindex(b)
        doc = json.loads(self.originals[g][bg.REPORT_JSON]); doc["batch"]["sha256"] = sim.sha_file(b / "sim_report.json")
        (g / bg.REPORT_JSON).write_bytes(sim.json_text(doc)); regate(g)
        deep = self.findings(g, b, deep=True)
        self.assertTrue(any(k.startswith("batch: ") for k in deep), deep)
        # the standing of the batch's report is bound to its label
        rep = json.loads(self.originals[b]["sim_report.json"]); rep["standing"] = sim.STANDING_GATE
        (b / "sim_report.json").write_bytes(sim.json_text(rep)); reindex(b)
        f = sv.verify_run_dir(b, deep=False); self.restore(b)
        self.assertTrue(any("standing text is not the one of the label" in m for v in f.values() for m in v), f)

    def test_the_synthetic_evidence_is_bound_and_re_judged(self):
        g = Path(self.b["gate_out"])
        syn = json.loads(self.originals[g][bg.SYNTHETIC_JSON])
        syn["summary"]["k10"]["fraction_interacting_over_S"] = 0.4; syn["summary"]["k10"]["counts"].update(interacting=80, not_assessable=120)
        raw = sim.json_text(syn); (g / bg.SYNTHETIC_JSON).write_bytes(raw)
        doc = json.loads(self.originals[g][bg.REPORT_JSON]); doc["batch"]["sha256"] = sim.sha_file(g / bg.SYNTHETIC_JSON)
        (g / bg.REPORT_JSON).write_bytes(sim.json_text(doc)); regate(g)
        f = self.findings(g)
        self.assertTrue(any("rows are not the ones recomputed" in m for m in f.get(bg.REPORT_JSON, [])), f)
        # a production label in the synthetic file: refused by name
        syn = json.loads(self.originals[g][bg.SYNTHETIC_JSON]); syn["label"] = bg.PINNED_GATE_LABEL
        (g / bg.SYNTHETIC_JSON).write_bytes(sim.json_text(syn))
        doc = json.loads(self.originals[g][bg.REPORT_JSON]); doc["batch"]["sha256"] = sim.sha_file(g / bg.SYNTHETIC_JSON)
        (g / bg.REPORT_JSON).write_bytes(sim.json_text(doc)); regate(g)
        f = self.findings(g)
        self.assertTrue(any("b4-mech" in m for m in f.get(bg.SYNTHETIC_JSON, [])), f)
        self.assertEqual(gv.verify_gate_dir(g), {}, "restored")

    def test_refusals_write_nothing_and_the_derivation_is_never_reached(self):
        before_g = sorted(p.name for p in self.gns.iterdir())
        before_s = sorted(p.name for p in self.ns.iterdir())
        # the production path: another label, S != 200 — refused before any tree is read
        with mock.patch.object(sim, "porcelain", side_effect=AssertionError("the tree was read")):
            r = bg.run_gate(self.root, "b4-gate-2", 200, 60); self.assertEqual(r["status"], "refused"); self.assertIn("pinned", r["reason"])
            r = bg.run_gate(self.root, "b4-gate-1", 2, 60); self.assertEqual(r["status"], "refused"); self.assertIn("S = 200", r["reason"])
            r = bg.run_gate(self.root, "b4-sim-3", 32, 60); self.assertEqual(r["status"], "refused")
            r = bg.run_gate(self.root, "b4-mech-1", 2, 60); self.assertEqual(r["status"], "refused"), "a mechanics label without a schedule is a production label mismatch"
        # a fixture batch under an exploration-mode harness is still refused the gate label; mode gate refuses exploration labels
        r = sim.run_batch(self.root, "b4-gate-1", 2, 60, self.ns / "b4-gate-1_x"); self.assertEqual(r["status"], "refused"); self.assertIn("mode gate only", r["reason"])
        r = sim.run_batch(self.root, "b4-sim-3", 2, 60, self.ns / "b4-sim-3_x", mode="gate"); self.assertEqual(r["status"], "refused"); self.assertIn("not a gate label", r["reason"])
        r = sim.run_batch(self.root, "b4-mech-1", 2, 60, self.ns / "b4-mech-1_x", schedule=SCHED1, mode="other"); self.assertEqual(r["status"], "refused"); self.assertIn("mode", r["reason"])
        # the gate directory: existing, a symlink, elsewhere, misnamed
        existing = self.gns / "b4-mech-1_exists"; existing.mkdir(parents=True, exist_ok=True)
        r = bg.run_gate(self.root, "b4-mech-1", 2, 60, out_gate=existing, schedule=SCHED1); self.assertEqual(r["status"], "refused"); self.assertIn("exists", r["reason"]); existing.rmdir()
        r = bg.run_gate(self.root, "b4-mech-1", 2, 60, out_gate=Path(self.tmp.name) / "elsewhere" / "b4-mech-1_x", schedule=SCHED1); self.assertEqual(r["status"], "refused"); self.assertIn("directly under", r["reason"])
        r = bg.run_gate(self.root, "b4-mech-1", 2, 60, out_gate=self.gns / "other_x", schedule=SCHED1); self.assertEqual(r["status"], "refused"); self.assertIn("begin with", r["reason"])
        link = self.gns / "b4-mech-1_link"; link.symlink_to(Path(self.tmp.name))
        r = bg.run_gate(self.root, "b4-mech-1", 2, 60, out_gate=link, schedule=SCHED1); self.assertEqual(r["status"], "refused"); link.unlink()
        # a dirty tree: the harness refuses the batch, the gate writes nothing
        (self.root / "dirty.txt").write_text("x")
        r = bg.run_gate(self.root, "b4-mech-1", 2, 60, schedule=SCHED1); self.assertEqual((r["status"], r["gate_out"]), ("refused", None)); self.assertIn("not clean", r["reason"])
        (self.root / "dirty.txt").unlink()
        # judge_batch: not under evidence/b4/sim/, no report, an exploration label, a misnamed directory
        r = bg.judge_batch(self.root, Path(self.tmp.name) / "nowhere"); self.assertEqual(r["status"], "refused")
        empty = self.ns / "b4-mech-1_empty"; empty.mkdir()
        r = bg.judge_batch(self.root, empty); self.assertEqual(r["status"], "refused"); self.assertIn("no sim_report.json", r["reason"]); empty.rmdir()
        src = self.ns / "b4-mech-1_fail"
        for name, label, part in (("b4-mech-1_copy", "b4-sim-9", "never judged"), ("b4-mech-2_copy", "b4-mech-1", "not named after")):
            dst = self.ns / name
            shutil.copytree(src, dst)
            rep = json.loads((dst / "sim_report.json").read_text()); rep["label"] = label
            (dst / "sim_report.json").write_bytes(sim.json_text(rep))
            r = bg.judge_batch(self.root, dst); self.assertEqual(r["status"], "refused", name); self.assertIn(part, r["reason"])
            shutil.rmtree(dst)
        # judge_synthetic: a production or gate label, fixture false, an unmarked note
        for over in ({"label": bg.PINNED_GATE_LABEL}, {"label": "b4-sim-4"}, {"fixture": False}, {"note": "numbers"}):
            r = bg.judge_synthetic(self.root, dict(synthetic_doc(synthetic_summary()), **over)); self.assertEqual(r["status"], "refused", over); self.assertIn("refused", r["reason"])
        self.assertEqual(sorted(p.name for p in self.gns.iterdir()), before_g, "a refusal creates no gate directory")
        self.assertEqual(sorted(p.name for p in self.ns.iterdir()), before_s, "a refusal creates no batch directory")
        self.assertFalse(git(self.root, "status", "--porcelain").strip())
        self.assertEqual([m.call_count for m in self.guard_mocks], [0, 0], "no refusal reached a derivation")

    def test_a_second_judgement_of_the_same_archive_is_a_new_gate_directory_with_the_same_rows(self):
        b = self.ns / "b4-mech-1_fail"
        r = bg.judge_batch(self.root, b, self.gns / "b4-mech-1_again")
        self.assertEqual((r["status"], r["exit_code"]), ("FAIL", 0), r.get("reason"))
        d1 = json.loads(self.originals[Path(self.a["gate_out"])][bg.REPORT_JSON]); d2 = json.loads((Path(r["gate_out"]) / bg.REPORT_JSON).read_text())
        self.assertEqual((d1["rows"], d1["budget_rule"], d1["verdict"], d1["batch"]), (d2["rows"], d2["budget_rule"], d2["verdict"], d2["batch"]))
        self.assertTrue(d2["clean_tree"], "the archive is committed: the tree is clean")
        self.assertEqual(gv.verify_gate_dir(Path(r["gate_out"])), {})
        r2 = bg.judge_batch(self.root, b, self.gns / "b4-mech-1_again"); self.assertEqual(r2["status"], "refused"); self.assertIn("exists", r2["reason"])

    def test_the_cli_is_production_only_with_no_fixture_path(self):
        # no --schedule / --allow-dirty / --fixture anywhere in the parser
        import inspect
        src = inspect.getsource(bg.main)
        for bad in ("allow-dirty", "--schedule", "--fixture", "--mode"):
            self.assertNotIn(bad, src, bad)
        with mock.patch.object(sim, "porcelain", side_effect=AssertionError("the tree was read")), mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            self.assertEqual(bg.main(["run", "--label", "b4-mech-1", "--seeds", "2", "--deadline-s", "60"]), 2)
            self.assertEqual(bg.main(["run", "--label", "b4-gate-1", "--seeds", "2", "--deadline-s", "60"]), 2)
            self.assertEqual(bg.main(["run", "--label", "b4-gate-2", "--seeds", "200", "--deadline-s", "60"]), 2)
            with self.assertRaises(SystemExit):
                bg.main(["run", "--label", "b4-gate-1", "--seeds", "200"])                       # --deadline-s has no default
        with mock.patch.object(sim, "porcelain", return_value=[" M x"]), mock.patch("sys.stdout"):
            self.assertEqual(bg.main(["judge", str(self.ns / "b4-mech-1_fail")]), 2, "a dirty tree refuses the judgement")
        with mock.patch.object(sim, "porcelain", return_value=[]), mock.patch("sys.stdout"):
            self.assertEqual(bg.main(["judge", str(self.ns / "b4-mech-1_fail")]), 2, "the CLI judges the production archive only")
        self.assertEqual(sorted(p.name for p in self.gns.iterdir()), sorted(p.name for p in self.gns.iterdir()))
        self.assertEqual([m.call_count for m in self.guard_mocks], [0, 0])

    def test_the_verifier_cli_names_a_wrong_directory(self):
        code, out = self.fresh(Path(self.tmp.name) / "nowhere")
        self.assertEqual(code, 1); self.assertIn("gate directory", out["findings"])
        code, out = self.fresh(self.ns / "b4-mech-1_fail")
        self.assertEqual(code, 1); self.assertTrue(any("not directly under" in m for v in out["findings"].values() for m in v), out)
        code, out = self.fresh(Path(self.a["gate_out"]), shallow=True)
        self.assertEqual((code, out["findings"]), (0, {}))


if __name__ == "__main__":
    unittest.main()

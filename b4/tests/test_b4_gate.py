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
import math
import os
import shutil
import statistics
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
import b4_gate_stats as gs  # noqa: E402
import b4_gate_verify as gv  # noqa: E402
import b4_k9 as k9  # noqa: E402
import b4_seeds as bs  # noqa: E402
import b4_sim as sim  # noqa: E402
import b4_protocol as bp  # noqa: E402
import b4_sim_schema as sc  # noqa: E402
import b4_sim_verify as sv  # noqa: E402
import b4_stats as st  # noqa: E402
import b4_thresholds as th  # noqa: E402
from b4_test_fixtures import InjectingPort  # noqa: E402
from test_b4_sim import SCHED1, Clock, build_hermetic, entry, git, production_derivation_reached, reindex  # noqa: E402

GRID = th.GRID
SIM3_REPORT = R / "evidence/b4/sim/b4-sim-3_20261019T121833Z/sim_report.json"      # the committed S = 32 exploration: read-only reference
SYN_LABEL = "b4-mech-7"


# ------------------------------------------------------------------ a synthetic summary shaped like summarise_batch's output, COHERENT by construction
def _fit(pos, neg, ties, S):
    """The count primitives (given for S = 200) scaled to S by the largest-remainder rule (so that a small S keeps a non-tied pair)."""
    total = pos + neg + ties
    if total == S:
        return pos, neg, ties
    exact = [pos * S / total, neg * S / total, ties * S / total]
    out = [int(x) for x in exact]
    for i in sorted(range(3), key=lambda i: exact[i] - int(exact[i]), reverse=True)[:S - sum(out)]:
        out[i] += 1
    return tuple(out)


def _delta(mean, pos, neg, ties, var, S):
    """A delta record from primitives, coherent under the summary contract: counts summing to S, the exact sign-test p of the counts,
    Cohen's d with the sign of the mean (finite when the variance is positive; +inf when all deltas are equal and positive, 0.0 when
    equal and not positive)."""
    pos, neg, ties = _fit(pos, neg, ties, S)
    if var == 0:
        pos, neg, ties = (S, 0, 0) if mean > 0 else (0, S, 0) if mean < 0 else (0, 0, S)
    assert pos + neg + ties == S, (pos, neg, ties, S)
    d = bg.implied_cohen_d(mean, var, S)                   # the production convention: mean / the SAMPLE standard deviation (the owner's review of a8f2da1)
    return {"n": S, "mean": mean, "median": mean, "positives": pos, "negatives": neg, "ties": ties, "sign_test_p": bg._sign_p(pos, neg), "population_variance": var, "cohen_d": d}


def _arm(mean, spread=5.0):
    return {"mean": mean, "median": mean, "min": mean - spread, "max": mean + spread}


def synthetic_summary(S=200, b_star=64, N=16, power=0.95, *, d1=(5.0, 150, 20, 30), f=(5.0, 150, 20, 30), x=(0.1, 60, 70, 70), d=(0.1, 60, 70, 70),
                      om=(8.0, 190, 5, 5), a0=(0.0, 50, 50, 100), var=4.0, var1=None, r_mean=12.0, base=4.0, omega_p95=None, k7_median=15, k9_medians=None, k9_na=None,
                      k9_all=None, nonreject=0.97, k10=None, f_end=11.0, k9_medians_all_panel=None) -> dict:
    """A PASS-shaped summary built from primitives so that every binding of the summary contract holds: the arm means from the deltas,
    the delta records from (mean, positives, negatives, ties) and the common variance, K1 from the arm values, the N scan from N and the
    power, the eligible list and B* by the budget rule, the at-B* record copied from the per-budget originals, K9 / K10 from their counts.
    Every number is invented: a fixture of the judge's paths, never data. A parameter outside the PASS region makes exactly the row it
    belongs to fail — coherently."""
    import copy
    T = copy.deepcopy(th.THRESHOLDS)                                   # a copy: a test that mutates the table in a summary never touches the module's
    var1 = var if var1 is None else var1
    k9_all = S if k9_all is None else k9_all
    k10 = (S, 0, 0, 0) if k10 is None else k10
    k9_medians = dict.fromkeys(k9.SEMANTICS, 1.0) | (k9_medians or {})
    k9_medians_all = dict(k9_medians) | (k9_medians_all_panel or {})          # the all-panel (b) record beside the judged (b'); equal unless given (the SR semantics may differ)
    k9_na = dict.fromkeys(k9.SEMANTICS, 0) | (k9_na or {})
    means = {"R": r_mean, "O": r_mean + d1[0], "F": r_mean + f[0], "X": r_mean + x[0], "D": r_mean + d[0], "Omega": r_mean + om[0], "A0": r_mean + a0[0]}
    per_budget = {}
    for B in GRID:
        n = N if B == b_star else None
        if S < T["K5"]["n_min"]:
            scan, last = [], None
        elif n is None:
            scan = [[k, 0.3] for k in range(T["K5"]["n_min"], S + 1)]; last = 0.3
        else:
            scan = [[k, 0.3] for k in range(T["K5"]["n_min"], n)] + [[n, power]]; last = power
        fe_mean = base if B <= th.PROBES else f_end
        arm_values = {role: _arm(means[role]) for role in sc.ROLES}
        p95 = omega_p95 if omega_p95 is not None else arm_values["Omega"]["max"]
        k1 = {"omega_best_p95": p95, "median_best_R": arm_values["R"]["median"], "median_base": base,
              "eligibility": bool(p95 < T["K1"]["omega_best_p95_lt"] and arm_values["R"]["median"] > base)}
        per_budget[str(B)] = {
            "budget": B, "arm_values": arm_values, "base": {"mean": base, "median": base},
            "f_end_to_end": {"mean": fe_mean, "median": fe_mean, "mapping_in_progress": B <= th.PROBES},
            "deltas": {"delta1_O_minus_R": _delta(d1[0], d1[1], d1[2], d1[3], var1, S), "delta2_O_minus_endtoend_F": _delta(means["O"] - fe_mean, 90, 80, 30, var, S),
                       "F_minus_R": _delta(f[0], f[1], f[2], f[3], var, S), "X_minus_R": _delta(x[0], x[1], x[2], x[3], var, S), "D_minus_R": _delta(d[0], d[1], d[2], d[3], var, S),
                       "Omega_minus_R": _delta(om[0], om[1], om[2], om[3], var, S), "A0_minus_R": _delta(a0[0], a0[1], a0[2], a0[3], var, S)},
            "k1": k1, "required_pairs": {"N": n, "power_at_N_or_last": last, "scan": scan, "n_min": T["K5"]["n_min"], "n_max": S},
            "cost_N_x_3_x_B": None if n is None else n * 3 * B,
            "k7_O_prefix_not_unknown": {"values": [k7_median] * S, "median": statistics.median([k7_median] * S)}}       # the production median's own type
    eligible = [B for B in GRID if per_budget[str(B)]["k1"]["eligibility"] and per_budget[str(B)]["required_pairs"]["N"] is not None]
    both = [B for B in GRID if per_budget[str(B)]["deltas"]["delta1_O_minus_R"]["positives"] > 0 and per_budget[str(B)]["deltas"]["delta1_O_minus_R"]["negatives"] > 0]
    if eligible:
        bs_ = min(eligible, key=lambda B: (per_budget[str(B)]["cost_N_x_3_x_B"], B))
        pb = per_budget[str(bs_)]; dl = pb["deltas"]
        at = {"B_star": bs_, "N": pb["required_pairs"]["N"], "cost_N_x_3_x_B_star": pb["cost_N_x_3_x_B"],
              "k2": {"population_variance_delta1": dl["delta1_O_minus_R"]["population_variance"], "budgets_with_both_signs": both, "x_minus_r_bootstrap_nonrejection": nonreject,
                     "bootstrap": {"N": pb["required_pairs"]["N"], "experiments": T["K2"]["bootstrap_experiments"], "alpha": T["K2"]["alpha"], "seed": T["K2"]["bootstrap_seed"]}},
              "k3": {"D_over_F": sim._ratio(dl["D_minus_R"]["mean"], dl["F_minus_R"]["mean"]), "X_over_O": sim._ratio(dl["X_minus_R"]["mean"], dl["delta1_O_minus_R"]["mean"]),
                     "D_sign_test_p": dl["D_minus_R"]["sign_test_p"], "X_sign_test_p": dl["X_minus_R"]["sign_test_p"]},
              "k4": {"median_best_Omega": pb["arm_values"]["Omega"]["median"], "mean_Omega_minus_R": dl["Omega_minus_R"]["mean"], "mean_F_minus_R": dl["F_minus_R"]["mean"],
                     "F_over_Omega": sim._ratio(dl["F_minus_R"]["mean"], dl["Omega_minus_R"]["mean"])},
              "k5": {"cohen_d_delta1": dl["delta1_O_minus_R"]["cohen_d"], "N": pb["required_pairs"]["N"], "cost": pb["cost_N_x_3_x_B"]},
              "k7": {"median_O_prefix_not_unknown": pb["k7_O_prefix_not_unknown"]["median"], "values": pb["k7_O_prefix_not_unknown"]["values"]}}
        cb = {"value": bs_, "reason_if_none": None, "note": T["B_star"]["no_eligible_budget"]}
    else:
        at = None
        cb = {"value": None, "reason_if_none": "no grid budget has both K1 eligibility and an N: the budget rule's candidate does not exist on this S (not invented)", "note": T["B_star"]["no_eligible_budget"]}
    k9s = {s: {"seeds_with_positive_control": S, "not_assessable_seeds": k9_na[s], "median_coverage_over_all_S": None if k9_na[s] > 0 else k9_medians[s],
               "median_rule": T["K9"]["median_population"], "conditional_on_A8": s == "ff_init"} for s in k9.SEMANTICS}
    k9s_all = {s: {"seeds_with_positive_control": S, "not_assessable_seeds": k9_na[s], "median_coverage_over_all_S": None if k9_na[s] > 0 else k9_medians_all[s],
                   "median_rule": T["K9"]["median_population"], "conditional_on_A8": s == "ff_init"} for s in k9.SEMANTICS}
    counts = dict(zip(st.OUTCOMES, k10))
    return {"S": S, "grid": list(GRID), "per_budget": per_budget, "eligible_budgets": eligible, "candidate_B_star": cb, "at_candidate_B_star": at,
            "k9": {"judged_estimand": k9.JUDGED_ESTIMAND, "per_semantic": k9s, "per_semantic_all_panel": k9s_all, "seeds_with_all_seven_positive_controls": k9_all, "fraction_of_S": k9_all / S},
            "k10": {"tau": T["K10"]["tau"], "S": S, "counts": counts, "fraction_interacting_over_S": counts[st.INTERACTING] / S, "note": bg.K10_NOTE},
            "thresholds_for_reference": T, "standing": sim.STANDING}


def no_b_star(summary: dict) -> dict:
    """The same summary with no N anywhere: the budget rule's candidate does not exist (rebuilt coherently)."""
    return synthetic_summary(S=summary["S"], N=None, b_star=None) if False else _no_b_star(summary)


def _no_b_star(summary: dict) -> dict:
    S = summary["S"]
    for B in GRID:
        v = summary["per_budget"][str(B)]
        v["required_pairs"]["N"] = None; v["cost_N_x_3_x_B"] = None
        if S < th.THRESHOLDS["K5"]["n_min"]:
            v["required_pairs"]["scan"], v["required_pairs"]["power_at_N_or_last"] = [], None
        else:
            v["required_pairs"]["scan"] = [[k, 0.3] for k in range(th.THRESHOLDS["K5"]["n_min"], S + 1)]; v["required_pairs"]["power_at_N_or_last"] = 0.3
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


def paths_of(obj, prefix=()):
    """Every path (as a tuple of keys / indexes) to every node of a JSON structure, containers included."""
    yield prefix, obj
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from paths_of(v, prefix + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from paths_of(v, prefix + (i,))


def with_replaced(obj, path, value):
    """A deep copy of obj with the node at `path` replaced by `value`."""
    import copy
    o = copy.deepcopy(obj)
    if not path:
        return value
    node = o
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    return o


def finite_ratio_overflow(s: dict) -> None:
    """Every input finite; the derived D / F ratio at B* overflows: D − R mean 1e308 over F − R mean 5e-324 (the arm values and the deltas'
    own statistics kept coherent so that only the derived quotient objects)."""
    v = s["per_budget"]["64"]
    v["arm_values"]["D"] = {"mean": 1e308, "median": 1e308, "min": 1e308, "max": 1e308}
    v["deltas"]["D_minus_R"] = _delta(1e308, 60, 70, 70, 4.0, 200)
    v["arm_values"]["F"] = {"mean": 12.0 + 5e-324, "median": 12.0, "min": 7.0, "max": 17.0}
    v["deltas"]["F_minus_R"] = _delta(5e-324, 150, 20, 30, 4.0, 200)
    s["at_candidate_B_star"]["k3"]["D_over_F"] = {"numerator": 1e308, "denominator": 5e-324, "ratio": 1.0, "readable": True, "note": None}
    s["at_candidate_B_star"]["k4"]["mean_F_minus_R"] = 5e-324
    s["at_candidate_B_star"]["k4"]["F_over_Omega"] = sim._ratio(5e-324, 8.0)


def overflowing_implied_d(s: dict) -> None:
    """Every input finite; the implied d of delta1 at B* overflows (mean 1e308, population variance 5e-324) and a finite −0.9 is recorded."""
    v = s["per_budget"]["64"]
    v["arm_values"]["O"] = {"mean": 1e308, "median": 1e308, "min": 1e308, "max": 1e308}
    d = v["deltas"]["delta1_O_minus_R"]
    d.update(mean=1e308, median=1e308, population_variance=5e-324, cohen_d={"value": -0.9, "special": None})
    v["deltas"]["delta2_O_minus_endtoend_F"].update(mean=1e308, median=1e308, cohen_d=bg.implied_cohen_d(1e308, 4.0, 200))
    s["at_candidate_B_star"]["k2"]["population_variance_delta1"] = 5e-324
    s["at_candidate_B_star"]["k3"]["X_over_O"] = sim._ratio(0.1, 1e308)
    s["at_candidate_B_star"]["k5"]["cohen_d_delta1"] = {"value": -0.9, "special": None}


# ------------------------------------------------------------------ the judge, pure
class TheJudge(unittest.TestCase):
    def test_the_synthetic_summary_is_coherent_under_the_contract_and_passes_every_row_but_is_never_formal(self):
        s = synthetic_summary()
        self.assertEqual(bg.summary_contract_findings(s, 200), [])
        j = bg.judge(synthetic_doc(s), "synthetic_summary")
        self.assertEqual([r["status"] for r in j["rows"]], ["PASS"] * 10)
        self.assertEqual([r["id"] for r in j["rows"]], list(bg.K_IDS))
        self.assertEqual((j["budget_rule"]["status"], j["budget_rule"]["B_star"], j["budget_rule"]["N"], j["budget_rule"]["cost_N_x_3_x_B_star"]), ("PASS", 64, 16, 3072))
        self.assertEqual(j["verdict"]["status"], "PASS")
        self.assertFalse(j["formal"]); self.assertIn("NOT a gate result", j["verdict"]["reason"])
        self.assertEqual(len(j["formal_reasons"]), 3, j["formal_reasons"])          # the evidence kind, the fixture, the label
        self.assertTrue(any("synthetic_summary" in x for x in j["formal_reasons"]) and any("fixture" in x for x in j["formal_reasons"]) and any("pinned gate label" in x for x in j["formal_reasons"]))
        rows = rows_by_id(j)
        self.assertEqual(rows["K5"]["value"]["N"], 16); self.assertEqual(rows["K5"]["value"]["cohen_d_delta1"], bg.implied_cohen_d(5.0, 4.0, 200))
        self.assertAlmostEqual(rows["K5"]["value"]["cohen_d_delta1"]["value"], 5.0 / math.sqrt(4.0 * 200 / 199), places=15)
        self.assertEqual(rows["K6"]["value"], {"S_planned": 200, "N": 16})
        for r in j["rows"]:
            self.assertTrue(r["method"] and r["criterion"] and r["reason"], r["id"])

    def test_the_formal_identity_on_a_pure_document(self):
        """The judge's formal flag on a document that carries the production identity (no file is involved: the verifier binds the files)."""
        d = synthetic_doc(synthetic_summary(), label=bg.PINNED_GATE_LABEL, fixture=False)
        j = bg.judge(d, "batch_archive")
        self.assertTrue(j["formal"]); self.assertEqual(j["formal_reasons"], []); self.assertEqual(j["verdict"]["status"], "PASS"); self.assertNotIn("NOT", j["verdict"]["reason"])
        for kind, over in (("synthetic_summary", {}), ("batch_archive", {"fixture": True}), ("batch_archive", {"label": "b4-gate-3"}), ("batch_archive", {"count": 199}), ("batch_archive", {"status": "invalid"})):
            dd = dict(d, **over)
            if "count" in over:
                dd["summary"] = synthetic_summary(S=199)
            self.assertFalse(bg.judge(dd, kind)["formal"], (kind, over))

    def test_each_row_fails_on_its_own_number_and_the_verdict_names_it(self):
        """Every FAIL is produced COHERENTLY (the summary passes the contract) by one primitive outside the PASS region; where coherence
        forces a second row to fail with it (a non-positive denominator shared by K3 and K4; a zero variance shared by K2 and the +inf d),
        that row is listed."""
        def case(kw, rid, reason_part, also=()):
            s = synthetic_summary(**kw)
            self.assertEqual(bg.summary_contract_findings(s, s["S"]), [], (rid, reason_part))
            j = bg.judge(synthetic_doc(s, S=s["S"]), "synthetic_summary")
            self.assertEqual(j["contract_findings"], [], (rid, reason_part))
            rows = rows_by_id(j)
            self.assertEqual(rows[rid]["status"], "FAIL", (rid, reason_part, rows[rid]["reason"]))
            self.assertIn(reason_part, rows[rid]["reason"], rid)
            self.assertEqual(sorted(r["id"] for r in j["rows"] if r["status"] != "PASS"), sorted({rid, *also}), (rid, reason_part))
            self.assertEqual(j["verdict"]["status"], "FAIL"); self.assertIn(f"{rid} FAILS", j["verdict"]["reason"]); self.assertIn("no threshold is adjusted", j["verdict"]["reason"])
        case({"var1": 0.0}, "K2", "variance")                                                  # all delta1 equal and positive: variance 0 (K5's d is +inf and PASSES)
        case({"d1": (5.0, 170, 0, 30)}, "K2", "both positive and negative")
        case({"nonreject": 0.899}, "K2", "non-rejection")
        case({"d": (0.6, 60, 70, 70)}, "K3", "D / F ratio")
        case({"f": (-0.1, 20, 150, 30)}, "K3", "non-positive denominator", also=("K4",))          # F - R ≤ 0: D / F unreadable, and F / Omega < 0.50
        case({"x": (0.6, 60, 70, 70)}, "K3", "X / O ratio")
        case({"d": (0.1, 120, 50, 30)}, "K3", "D_sign_test_p")
        case({"x": (0.1, 120, 50, 30)}, "K3", "X_sign_test_p")
        case({"om": (45.7, 190, 5, 5), "omega_p95": 60.0}, "K4", "57.6")                        # Omega mean 57.7 (R 12 + 45.7), p95 60 < 64 keeps K1
        case({"f": (3.9, 150, 20, 30)}, "K4", "F / Omega ratio")
        case({"om": (-1.0, 5, 190, 5)}, "K4", "non-positive denominator")
        case({"d1": (1.0, 150, 20, 30), "var1": 4.0}, "K5", "Cohen's d")                      # the owner's boundary numbers: mean 1, population variance 4, S 200 → d 0.4987… < 0.5
        case({"k7_median": 10}, "K7", "< 11")
        case({"k9_all": 179}, "K9", "(a)")
        case({"k9_medians": {"ff_srval": 0.4270833}}, "K9", "ff_srval 0.427083")
        case({"k9_medians": {"sr_kind": 0.25}, "k9_medians_all_panel": {"sr_kind": 0.5}}, "K9", "(b') conditional median coverage below 0.50: sr_kind 0.25")
        case({"k9_na": {"sr_kind": 3}}, "K9", "not assessable: sr_kind (3 seeds")
        case({"k10": (99, 0, 0, 101)}, "K10", "< 0.50")
        case({"N": 21}, "K5", "4 000")                                                          # N = 21 at B* = 64: 4 032 search evaluations

    def test_the_boundaries_written_with_an_equal_sign_pass_and_an_infinite_d_passes(self):
        s = synthetic_summary(nonreject=0.90, om=(45.6, 190, 5, 5), omega_p95=60.0, f=(22.8, 150, 20, 30), d=(2.28, 60, 70, 70), x=(0.1, 60, 70, 70), power=0.90, k7_median=11,
                              k9_all=180, k9_medians=dict.fromkeys(k9.SEMANTICS, 0.5), k10=(100, 0, 0, 100), d1=(1.0, 150, 20, 30), var1=3.9)   # d = 1 / sqrt(3.9 · 200 / 199) = 0.5051… ≥ 0.5
        self.assertEqual(bg.summary_contract_findings(s, 200), [])
        self.assertGreaterEqual(s["at_candidate_B_star"]["k5"]["cohen_d_delta1"]["value"], 0.5); self.assertLess(s["at_candidate_B_star"]["k5"]["cohen_d_delta1"]["value"], 0.51)
        at = s["at_candidate_B_star"]
        self.assertEqual((at["k4"]["median_best_Omega"], at["k4"]["F_over_Omega"]["ratio"], at["k3"]["X_over_O"]["ratio"]), (57.6, 0.5, 0.1))
        self.assertAlmostEqual(at["k3"]["D_over_F"]["ratio"], 0.1, places=12); self.assertLessEqual(at["k3"]["D_over_F"]["ratio"], 0.1)
        j = bg.judge(synthetic_doc(s), "synthetic_summary")
        self.assertEqual(j["contract_findings"], [])
        self.assertEqual([r["status"] for r in j["rows"]], ["PASS"] * 10, [(r["id"], r["reason"]) for r in j["rows"] if r["status"] != "PASS"])
        self.assertEqual(j["verdict"]["status"], "PASS")
        # a legitimate +inf d (all delta1 equal and positive) PASSES K5 — coherently it also means a zero variance, which FAILS K2
        s = synthetic_summary(var1=0.0)
        self.assertEqual(bg.summary_contract_findings(s, 200), [])
        rows = rows_by_id(bg.judge(synthetic_doc(s), "synthetic_summary"))
        self.assertEqual((rows["K5"]["status"], rows["K5"]["value"]["cohen_d_delta1"], rows["K2"]["status"]), ("PASS", {"value": None, "special": "+inf"}, "FAIL"), "a legitimate +inf d is kept as such, never as 0")

    def test_k9_judges_the_conditional_record_and_carries_the_all_panel_one_beside_it(self):
        """Protocol v0.2.0 (the owner's choice 4): the judged (b') is the conditional record; the all-panel (b) is reported in the row's value and
        never judged — a summary whose all-panel ff_srval median is the gate-1 value 0.40625 PASSES K9 when the conditional median is ≥ 0.50,
        and the row says so; a non-SR semantic whose two records disagree breaks the contract."""
        s = synthetic_summary(k9_medians={"ff_srval": 0.8125, "sr_kind": 1.0}, k9_medians_all_panel={"ff_srval": 0.40625, "sr_kind": 0.5})
        self.assertEqual(bg.summary_contract_findings(s, 200), [])
        j = bg.judge(synthetic_doc(s), "synthetic_summary")
        row = rows_by_id(j)["K9"]
        self.assertEqual(row["status"], "PASS", row["reason"]); self.assertIn("(b')", row["reason"]); self.assertIn("not judged", row["reason"])
        self.assertEqual(row["value"]["judged_estimand"], k9.JUDGED_ESTIMAND)
        self.assertEqual(row["value"]["per_semantic_conditional_judged"]["ff_srval"]["median_coverage_over_all_S"], 0.8125)
        self.assertEqual(row["value"]["per_semantic_all_panel_descriptive"]["ff_srval"]["median_coverage_over_all_S"], 0.40625)
        self.assertEqual(row["threshold"]["judged_estimand"], "conditional_sr_driven"); self.assertIn("applicable_conditional", row["threshold"]["applicability_judged"])
        self.assertIn("(b')", row["method"]); self.assertIn("all-panel", row["method"])
        s = synthetic_summary(k9_medians={"ff_srval": 0.4}, k9_medians_all_panel={"ff_srval": 0.9})
        self.assertEqual(rows_by_id(bg.judge(synthetic_doc(s), "synthetic_summary"))["K9"]["status"], "FAIL", "the all-panel record cannot rescue a failing conditional one")
        s = synthetic_summary(k9_medians={"ce_mode": 0.9}, k9_medians_all_panel={"ce_mode": 1.0})
        self.assertTrue(any("non-SR semantic" in x for x in bg.summary_contract_findings(s, 200)), "the conditional rule changes ff_srval / sr_kind only")
        s = synthetic_summary(); s["k9"]["judged_estimand"] = "all_panel"
        self.assertTrue(any("judged_estimand" in x for x in bg.summary_contract_findings(s, 200)))
        s = synthetic_summary(); del s["k9"]["per_semantic_all_panel"]
        self.assertTrue(bg.summary_contract_findings(s, 200), "both records are required")

    def test_k5_is_delta1_o_minus_r_not_f_minus_r(self):
        s = synthetic_summary(f=(0.2, 110, 60, 30))                                                 # F - R weak, delta1 strong: K5 PASSES
        self.assertEqual(bg.summary_contract_findings(s, 200), [])
        j = bg.judge(synthetic_doc(s), "synthetic_summary")
        self.assertEqual(rows_by_id(j)["K5"]["status"], "PASS")
        s = synthetic_summary(d1=(0.2, 110, 60, 30), f=(8.0, 190, 5, 5))                            # delta1 weak: K5 FAILS whatever F - R
        self.assertEqual(bg.summary_contract_findings(s, 200), [])
        self.assertEqual(rows_by_id(bg.judge(synthetic_doc(s), "synthetic_summary"))["K5"]["status"], "FAIL")

    def test_k6_fails_when_s_is_not_the_planned_200(self):
        j = bg.judge(synthetic_doc(synthetic_summary(S=199), S=199), "synthetic_summary")
        rows = rows_by_id(j)
        self.assertEqual((rows["K6"]["status"], rows["K6"]["value"]), ("FAIL", {"S_planned": 199, "N": 16})); self.assertIn("199", rows["K6"]["reason"])
        self.assertEqual(j["verdict"]["status"], "FAIL"); self.assertIn("K6 FAILS", j["verdict"]["reason"])
        self.assertIn("S = 199 is not the planned 200", j["formal_reasons"])

    def test_no_b_star_leaves_the_dependent_rows_not_assessable_and_the_gate_cannot_pass(self):
        s = no_b_star(synthetic_summary())
        self.assertEqual(bg.summary_contract_findings(s, 200), [])
        j = bg.judge(synthetic_doc(s), "synthetic_summary")
        self.assertEqual(j["contract_findings"], [])
        br = j["budget_rule"]
        self.assertEqual((br["status"], br["B_star"], br["N"], br["cost_N_x_3_x_B_star"], br["eligible_budgets"]), ("FAIL", None, None, None, []))
        self.assertIn("not invented", br["reason"]); self.assertIn("cannot PASS", br["reason"])
        self.assertEqual(br["k1_eligibility_by_budget"], {str(B): True for B in GRID}); self.assertEqual(br["N_by_budget"], {str(B): None for B in GRID})
        st_ = {r["id"]: r["status"] for r in j["rows"]}
        self.assertEqual(st_, {"K1": "not_assessable", "K2": "not_assessable", "K3": "not_assessable", "K4": "not_assessable", "K5": "not_assessable", "K6": "not_assessable",
                               "K7": "not_assessable", "K8": "PASS", "K9": "PASS", "K10": "PASS"})
        rows = rows_by_id(j)
        self.assertIn("no B*", rows["K2"]["reason"]); self.assertIn("(b) needs B*", rows["K7"]["reason"]); self.assertEqual(rows["K7"]["value"]["a_recomputation_mismatches"], 0)
        self.assertIn("N does not exist", rows["K6"]["reason"]); self.assertEqual(rows["K6"]["value"], {"S_planned": 200, "N": None})
        self.assertEqual(j["verdict"]["status"], "FAIL"); self.assertIn("budget rule FAILS", j["verdict"]["reason"]); self.assertIn("not assessable: K1, K2, K3, K4, K5, K6, K7", j["verdict"]["reason"])
        # with S != 200 and no B*, K6 FAILS outright; with S = 2 < n_min the scan is empty and the power null, as the harness writes it
        j2 = bg.judge(synthetic_doc(no_b_star(synthetic_summary(S=32)), S=32), "synthetic_summary")
        self.assertEqual(j2["contract_findings"], []); self.assertEqual(rows_by_id(j2)["K6"]["status"], "FAIL")
        s2 = no_b_star(synthetic_summary(S=2))
        self.assertEqual(bg.summary_contract_findings(s2, 2), []); self.assertEqual(s2["per_budget"]["8"]["required_pairs"], {"N": None, "power_at_N_or_last": None, "scan": [], "n_min": 8, "n_max": 2})

    def test_an_invalid_or_incomplete_batch_is_that_verdict_with_nothing_judged(self):
        for status in ("invalid", "incomplete"):
            j = bg.judge(synthetic_doc(None, status=status), "synthetic_summary")
            self.assertEqual(j["verdict"]["status"], status, status)
            self.assertEqual([r["status"] for r in j["rows"]], ["not_assessable"] * 10)
            self.assertEqual(j["budget_rule"]["status"], "not_assessable"); self.assertFalse(j["formal"])
            self.assertIn(status, j["rows"][0]["reason"])
        self.assertIn("contract break", bg.judge(synthetic_doc(None, status="invalid"), "synthetic_summary")["verdict"]["reason"])
        self.assertIn("unfinished", bg.judge(synthetic_doc(None, status="incomplete"), "synthetic_summary")["verdict"]["reason"])

    def test_an_incoherent_or_malformed_summary_is_invalid_never_judged_and_never_an_exception(self):
        """R1 / R2 of the owner's review of 4cdc0c1: the four accepted contradictions and the two exceptions, each now a named contract
        finding and an invalid judgement; plus one case per binding the contract makes."""
        def case(mutate, part):
            s = synthetic_summary()
            mutate(s)
            f = bg.summary_contract_findings(s, 200)
            self.assertTrue(any(part in x for x in f), (part, f))
            j = bg.judge(synthetic_doc(s), "synthetic_summary")
            self.assertEqual(j["verdict"]["status"], "invalid", part)
            self.assertEqual(j["contract_findings"], f, part)
            self.assertEqual([r["status"] for r in j["rows"]], ["not_assessable"] * 10, part)
            self.assertEqual(j["budget_rule"]["status"], "not_assessable", part)
        at = lambda s: s["at_candidate_B_star"]  # noqa: E731
        pb = lambda s, B="64": s["per_budget"][B]  # noqa: E731
        # the owner's reproductions
        case(lambda s: at(s)["k3"].__setitem__("D_over_F", None), "k3.D_over_F: not an object")
        case(lambda s: s["candidate_B_star"].__setitem__("value", 64.0), "is not the cheapest eligible budget")
        case(lambda s: pb(s)["required_pairs"].__setitem__("scan", []), "the scan does not end at N")
        case(lambda s: pb(s)["deltas"]["delta1_O_minus_R"].__setitem__("cohen_d", {"value": -1.0, "special": None}), "is not the production statistic")
        case(lambda s: (pb(s)["deltas"]["delta1_O_minus_R"].__setitem__("cohen_d", {"value": -100, "special": "+inf"}), at(s)["k5"].__setitem__("cohen_d_delta1", {"value": -100, "special": "+inf"})), "special +inf carries a null value")
        case(lambda s: s["k9"].__setitem__("fraction_of_S", 2.0), "fraction_of_S is not")
        # the at-B* copies bound to their originals
        case(lambda s: at(s)["k5"].__setitem__("cohen_d_delta1", {"value": 0.9, "special": None}), "k5.cohen_d_delta1 is not delta1's")
        case(lambda s: at(s)["k2"].__setitem__("population_variance_delta1", 1.0), "k2.population_variance_delta1")
        case(lambda s: at(s)["k2"].__setitem__("budgets_with_both_signs", [64]), "budgets_with_both_signs")
        case(lambda s: at(s)["k2"]["bootstrap"].__setitem__("seed", 8), "k2.bootstrap")
        case(lambda s: at(s)["k3"].__setitem__("D_over_F", sim._ratio(0.0, 5.0)), "k3.D_over_F is not the harness's ratio")
        case(lambda s: at(s)["k3"].__setitem__("X_sign_test_p", 0.5), "sign-test p values")
        case(lambda s: at(s)["k4"].__setitem__("median_best_Omega", 30.5), "k4's medians")
        case(lambda s: at(s)["k4"].__setitem__("F_over_Omega", sim._ratio(5.0, 8.1)), "k4.F_over_Omega")
        case(lambda s: at(s)["k5"].__setitem__("N", 15), "k5's N / cost")
        case(lambda s: at(s)["k7"].__setitem__("median_O_prefix_not_unknown", 14.0), "k7 at B*")
        case(lambda s: at(s).__setitem__("N", 15), "B* / N / cost")
        # the scan and the budget rule
        case(lambda s: pb(s)["required_pairs"]["scan"].__setitem__(-1, [16, 0.5]), "N is not the first n whose rate reaches")
        case(lambda s: pb(s)["required_pairs"]["scan"].pop(3), "complete ascending scan")
        case(lambda s: pb(s)["required_pairs"].__setitem__("power_at_N_or_last", 0.94), "power_at_N_or_last is not the rate at N")
        case(lambda s: pb(s, "32")["required_pairs"]["scan"].__setitem__(0, [8, 0.95]), "no N although a scanned rate reaches")
        case(lambda s: pb(s, "32")["required_pairs"]["scan"].pop(), "no N needs every n")
        case(lambda s: pb(s).__setitem__("cost_N_x_3_x_B", 3000), "N x 3 x B")
        case(lambda s: pb(s, "32").__setitem__("cost_N_x_3_x_B", 0), "is not null without N")
        case(lambda s: s.__setitem__("eligible_budgets", [64, 96]), "eligible_budgets")
        case(lambda s: pb(s, "32")["k1"].__setitem__("eligibility", False), "eligibility is not the one of its own numbers")
        case(lambda s: pb(s)["k1"].__setitem__("median_best_R", 13.0), "median_best_R is not arm R's median")
        case(lambda s: pb(s)["k1"].__setitem__("omega_best_p95", 70.0), "lies outside Omega's values")
        case(lambda s: s["candidate_B_star"].__setitem__("reason_if_none", "x"), "reason_if_none is not null")
        # the deltas
        case(lambda s: pb(s)["deltas"]["delta1_O_minus_R"].__setitem__("sign_test_p", 0.5), "sign_test_p is not the one-sided exact p")
        case(lambda s: pb(s)["deltas"]["delta1_O_minus_R"].__setitem__("positives", 151), "positives + negatives + ties")
        case(lambda s: pb(s)["deltas"]["delta1_O_minus_R"].__setitem__("n", 199), ".n is not S")
        case(lambda s: pb(s)["deltas"]["F_minus_R"].__setitem__("mean", 5.5), "difference of the arm means")
        case(lambda s: pb(s)["deltas"]["F_minus_R"].__setitem__("cohen_d", {"value": None, "special": "-inf"}), "not an encoding the copied cohen_d produces")
        case(lambda s: pb(s)["deltas"]["F_minus_R"].__setitem__("cohen_d", {"value": None, "special": None}), "special null needs a finite value")
        case(lambda s: pb(s)["deltas"]["F_minus_R"].__setitem__("population_variance", -1.0), "variance ≥ 0")
        # the arm values, the base, F end to end, K7
        case(lambda s: pb(s)["arm_values"]["R"].__setitem__("min", 20.0), "min ≤ median, mean ≤ max")
        case(lambda s: pb(s)["arm_values"].pop("A0"), "arm_values: keys")
        case(lambda s: pb(s, "8")["f_end_to_end"].__setitem__("mean", 5.0), "mapping in progress means F's base score")
        case(lambda s: pb(s)["f_end_to_end"].__setitem__("mapping_in_progress", True), "mapping_in_progress exactly when")
        case(lambda s: pb(s)["k7_O_prefix_not_unknown"].__setitem__("median", 14.0), "their median")
        case(lambda s: pb(s)["k7_O_prefix_not_unknown"]["values"].__setitem__(0, 22), "ints in [0, 21]")
        # K9 / K10
        case(lambda s: s["k9"].__setitem__("seeds_with_all_seven_positive_controls", 201), "int in [0, S]")
        case(lambda s: s["k9"]["per_semantic"]["ff_init"].__setitem__("median_coverage_over_all_S", None), "leaves no median" if False else "not a number in [0, 1]")
        case(lambda s: s["k9"]["per_semantic"]["ff_init"].__setitem__("median_coverage_over_all_S", 1.5), "not a number in [0, 1]")
        case(lambda s: s["k9"]["per_semantic"]["ff_init"].update(not_assessable_seeds=2), "a not-assessable seed leaves no median")
        case(lambda s: s["k9"]["per_semantic"]["ff_init"].__setitem__("seeds_with_positive_control", 100), "fewer seeds with a positive control")
        case(lambda s: s["k9"]["per_semantic"]["ff_init"].__setitem__("conditional_on_A8", False), "conditional_on_A8")
        case(lambda s: s["k9"]["per_semantic"]["ce_mode"].__setitem__("median_rule", "x"), "median_rule")
        case(lambda s: s["k10"]["counts"].__setitem__("interacting", 150), "summing to S")
        case(lambda s: s["k10"]["counts"].__setitem__("interacting", None), "non-negative ints")
        case(lambda s: s["k10"].__setitem__("fraction_interacting_over_S", 0.99), "interacting / S")
        case(lambda s: s["k10"].__setitem__("note", "x"), "k10.note")
        case(lambda s: s["k10"].__setitem__("tau", 3), "tau / S")
        # the frame
        case(lambda s: s.__setitem__("S", 201), "summary.S")
        case(lambda s: s.__setitem__("S", True), "summary.S")
        case(lambda s: s.__setitem__("grid", [8.0, 16, 24, 32, 48, 64, 96, 128, 192, 256]), "fixed grid")
        case(lambda s: s["per_budget"].pop("8"), "exactly the grid budgets")
        case(lambda s: s["thresholds_for_reference"]["K9"].__setitem__("median_coverage_per_semantic_min", 0.4), "thresholds_for_reference")
        case(lambda s: s.__setitem__("standing", None), "standing")
        # identity fields and the frame of the document itself
        for over in ({"count": 200.0}, {"count": True}, {"count": 0}, {"status": "done"}, {"label": 5}, {"fixture": "yes"}, {"label": "B4 gate"}):
            j = bg.judge(dict(synthetic_doc(synthetic_summary()), **over), "synthetic_summary")
            self.assertEqual(j["verdict"]["status"], "invalid", over); self.assertTrue(j["contract_findings"], over); self.assertFalse(j["formal"], over)
        for doc in (None, [], "x", {"status": "complete"}, {"status": "complete", "label": "b4-mech-7", "fixture": True, "count": 200}, {"status": "complete", "label": "b4-mech-7", "fixture": True, "count": 200, "summary": []}):
            j = bg.judge(doc, "synthetic_summary")
            self.assertEqual(j["verdict"]["status"], "invalid", doc)
        with self.assertRaises(ValueError):
            bg.judge(synthetic_doc(synthetic_summary()), "other")

    def test_the_contract_is_total_every_node_replaced_by_every_foreign_value(self):
        """Totality: every node of a coherent summary (containers included) replaced by None / a string / a bool / a float / an empty list /
        an empty object: the judge never raises; a null in place of any non-null node is a named finding (the summary has no optional field
        whose absence is not bound elsewhere); every other foreign value either breaks the contract or leaves a coherent, judgeable summary."""
        base = synthetic_summary()
        n_paths, n_null_invalid = 0, 0
        for path, node in list(paths_of(base)):
            if not path:
                continue
            if len(path) > 1 and path[0] == "per_budget" and path[1] not in ("8", "64"):
                continue                                                 # the ten budgets share one structure: one below the probes, the B* one
            n_paths += 1
            for value in (None, "x", True, 1.5, [], {}, 10 ** 400, float("inf"), float("nan")):
                if value == node and type(value) is type(node):
                    continue
                s = with_replaced(base, path, value)
                try:
                    j = bg.judge(synthetic_doc(s), "synthetic_summary")
                except Exception as exc:  # noqa: BLE001
                    self.fail(f"the judge raised {type(exc).__name__}: {exc} at {path} with {value!r}")
                self.assertIn(j["verdict"]["status"], bg.VERDICTS, (path, value))
                if value is None and node is not None:
                    self.assertEqual(j["verdict"]["status"], "invalid", (path, "null"))
                    self.assertTrue(j["contract_findings"], (path, "null"))
                    n_null_invalid += 1
        self.assertGreater(n_paths, 500)
        self.assertGreater(n_null_invalid, 400)

    def test_cohen_s_d_is_bound_by_magnitude_under_the_production_sample_variance_convention(self):
        """The owner's review of a8f2da1, P2 1: (a) a concrete 200-value delta sequence — the production function (mean / statistics.stdev,
        the SAMPLE standard deviation) against the value implied by its recorded mean and POPULATION variance: equal to 1e-12 relative
        (the archives agree to ~1e-16); (b) the owner's boundary: mean 1, population variance 4, S 200 gives 0.4987… (FAIL side), not the
        population-formula 0.5; (c) the special cases S < 2 and zero variance; (d) the coordinated two-copy edit — both copies of d at B*
        set to 0.9 over a mean of 0.5 and a variance of 4 — is a named contract finding and an invalid judgement, not a PASS."""
        import random
        rng = random.Random(11)
        deltas = [rng.choice([-3, -1, 0, 1, 2, 4, 7]) for _ in range(200)]
        d_prod = gs.cohen_d(deltas)
        want = bg.implied_cohen_d(gs.mean(deltas), statistics.pvariance(deltas), 200)["value"]
        self.assertLessEqual(abs(d_prod - want), bg.D_REL_TOL * max(1.0, abs(want)))
        self.assertAlmostEqual(d_prod, gs.mean(deltas) / statistics.stdev(deltas), places=15)
        b = bg.implied_cohen_d(1, 4, 200)
        self.assertAlmostEqual(b["value"], 0.49874843358150006, places=15); self.assertLess(b["value"], 0.5)
        self.assertAlmostEqual(bg.implied_cohen_d(1, 4.5, 200)["value"], 0.47022453265552955, places=14)
        self.assertEqual(bg.implied_cohen_d(5.0, 0, 200), {"value": None, "special": "+inf"}); self.assertEqual(bg.implied_cohen_d(-5.0, 0, 200), {"value": 0.0, "special": None})
        self.assertEqual(bg.implied_cohen_d(5.0, 0, 1), {"value": 0.0, "special": None}, "S < 2: the production function returns 0.0")
        self.assertEqual(gs.cohen_d([5]), 0.0); self.assertEqual(gs.cohen_d([5, 5]), math.inf); self.assertEqual(gs.cohen_d([-5, -5]), 0.0)
        # (c) a one-pair summary must record d = 0.0 whatever its mean; +inf there is a finding
        s1 = no_b_star(synthetic_summary(S=1))
        self.assertEqual(bg.summary_contract_findings(s1, 1), [])
        self.assertEqual(s1["per_budget"]["64"]["deltas"]["delta1_O_minus_R"]["cohen_d"], {"value": 0.0, "special": None})
        s1["per_budget"]["64"]["deltas"]["delta1_O_minus_R"]["cohen_d"] = {"value": None, "special": "+inf"}
        self.assertTrue(any("S < 2" in x for x in bg.summary_contract_findings(s1, 1)))
        # (d) the coordinated two-copy edit over the owner's base (mean 0.5, variance 4: K5 FAILS on its own numbers)
        s = synthetic_summary(d1=(0.5, 110, 60, 30), var1=4.0)
        self.assertEqual(bg.summary_contract_findings(s, 200), [])
        self.assertEqual(rows_by_id(bg.judge(synthetic_doc(s), "synthetic_summary"))["K5"]["status"], "FAIL")
        s["per_budget"]["64"]["deltas"]["delta1_O_minus_R"]["cohen_d"] = {"value": 0.9, "special": None}
        s["at_candidate_B_star"]["k5"]["cohen_d_delta1"] = {"value": 0.9, "special": None}
        f = bg.summary_contract_findings(s, 200)
        self.assertTrue(any("is not the production statistic of its mean 0.5" in x and "sample standard deviation" in x for x in f), f)
        j = bg.judge(synthetic_doc(s), "synthetic_summary")
        self.assertEqual(j["verdict"]["status"], "invalid"); self.assertEqual([r["status"] for r in j["rows"]], ["not_assessable"] * 10)
        # a d within the tolerance of its implied value is accepted; one 1e-9 away is not
        s = synthetic_summary()
        w = s["per_budget"]["64"]["deltas"]["delta1_O_minus_R"]["cohen_d"]["value"]
        for budget in GRID:
            s["per_budget"][str(budget)]["deltas"]["delta1_O_minus_R"]["cohen_d"] = {"value": w * (1 + 1e-14), "special": None}
        s["at_candidate_B_star"]["k5"]["cohen_d_delta1"] = {"value": w * (1 + 1e-14), "special": None}
        self.assertEqual(bg.summary_contract_findings(s, 200), [])
        for budget in GRID:
            s["per_budget"][str(budget)]["deltas"]["delta1_O_minus_R"]["cohen_d"] = {"value": w * (1 + 1e-9), "special": None}
        s["at_candidate_B_star"]["k5"]["cohen_d_delta1"] = {"value": w * (1 + 1e-9), "special": None}
        self.assertTrue(bg.summary_contract_findings(s, 200))

    def test_numerically_equal_foreign_types_and_numeric_edges_are_findings_never_exceptions(self):
        """The owner's review of a8f2da1, P2 2: the five aliases (8.0 for n_min, 7.0 for the bootstrap seed, 2.0 for tau, 16.0 for the at-B* N,
        15.0 in the at-B* K7 values) and bool aliases are named findings; a decoded integer beyond 2^63, an infinite literal (1e400) and a NaN at
        any path — the thresholds table included — are findings before any serialisation or arithmetic, never exceptions; then the fuzz: every
        int leaf of a coherent summary replaced by its float alias, and every 0 / 1 leaf by its bool alias, is invalid."""
        def case(mutate, part):
            s = synthetic_summary(); mutate(s)
            f = bg.summary_contract_findings(s, 200)
            self.assertTrue(any(part in x for x in f), (part, f))
            j = bg.judge(synthetic_doc(s), "synthetic_summary")
            self.assertEqual(j["verdict"]["status"], "invalid", part); self.assertEqual([r["status"] for r in j["rows"]], ["not_assessable"] * 10, part)
        at = lambda s: s["at_candidate_B_star"]  # noqa: E731
        case(lambda s: s["per_budget"]["64"]["required_pairs"].__setitem__("n_min", 8.0), "n_min / n_max")
        case(lambda s: at(s)["k2"]["bootstrap"].__setitem__("seed", 7.0), "k2.bootstrap")
        case(lambda s: s["k10"].__setitem__("tau", 2.0), "tau / S")
        case(lambda s: at(s)["k5"].__setitem__("N", 16.0), "k5's N / cost")
        case(lambda s: at(s)["k7"].__setitem__("values", [15.0] * 200), "k7 at B*")
        case(lambda s: s["per_budget"]["64"]["k7_O_prefix_not_unknown"].__setitem__("values", [15.0] * 200), "ints in [0, 21]")
        case(lambda s: s["per_budget"]["64"]["required_pairs"].__setitem__("N", 16.0), "required_pairs.N")
        case(lambda s: s["k10"]["counts"].__setitem__("nonzero_below_threshold", False), "non-negative ints")
        case(lambda s: s["k9"]["per_semantic"]["ff_init"].__setitem__("not_assessable_seeds", False), "counts are ints")
        case(lambda s: s.__setitem__("eligible_budgets", [64.0]), "eligible_budgets")
        case(lambda s: s["per_budget"]["64"].__setitem__("budget", 64.0), ".budget is")
        case(lambda s: s["per_budget"]["64"]["k1"].__setitem__("omega_best_p95", 10 ** 400), "beyond ±2^63")
        case(lambda s: s["thresholds_for_reference"]["K10"].__setitem__("tau", float("inf")), "is not finite")
        case(lambda s: s["per_budget"]["8"]["deltas"]["F_minus_R"].__setitem__("mean", float("nan")), "is not finite")
        case(lambda s: s["k10"].__setitem__("S", 2 ** 70), "beyond ±2^63")
        for over in ({"count": 10 ** 400}, {"count": 2 ** 64}, {"count": bg.S_MAX + 1}):
            j = bg.judge(dict(synthetic_doc(synthetic_summary()), **over), "synthetic_summary")
            self.assertEqual(j["verdict"]["status"], "invalid", over); self.assertTrue(j["contract_findings"], over)
        self.assertTrue(bg.synthetic_findings(dict(synthetic_doc(synthetic_summary()), head=None, count=10 ** 400)))
        self.assertTrue(bg.numeric_findings({"a": [1, {"b": float("-inf")}]}) and bg.numeric_findings(10 ** 19) and not bg.numeric_findings({"a": [1, 2.5, True, "x", None, 2 ** 62]}))
        # the alias fuzz
        base = synthetic_summary()
        n_int, n_bool = 0, 0
        for path, node in list(paths_of(base)):
            if not path or (len(path) > 1 and path[0] == "per_budget" and path[1] not in ("8", "64")):
                continue
            if type(node) is int:
                j = bg.judge(synthetic_doc(with_replaced(base, path, float(node))), "synthetic_summary")
                self.assertEqual(j["verdict"]["status"], "invalid", (path, "float alias")); n_int += 1
                if node in (0, 1):
                    j = bg.judge(synthetic_doc(with_replaced(base, path, bool(node))), "synthetic_summary")
                    self.assertEqual(j["verdict"]["status"], "invalid", (path, "bool alias")); n_bool += 1
            elif type(node) is float and node in (0.0, 1.0):
                j = bg.judge(synthetic_doc(with_replaced(base, path, bool(node))), "synthetic_summary")
                self.assertEqual(j["verdict"]["status"], "invalid", (path, "bool alias of a float")); n_bool += 1
        self.assertGreater(n_int, 100); self.assertGreater(n_bool, 10)

    def test_derived_arithmetic_is_guarded_finite_inputs_that_overflow_are_named_findings(self):
        """The owner's review of b49b2ec, section 1: (1a) 1e308 / 5e-324 is +inf — the ratio record is a named finding, never a ValueError
        from the canonical serialisation; (1b) mean 1e308 with population variance 5e-324 implies an unrepresentable d — a recorded −0.9 is a
        named finding, never accepted through inf > inf; the same through a whole, otherwise finite summary, the judge and the artifact path;
        the production special cases kept."""
        f = []; bg._ratio_findings(sim._ratio(1.0, 2.0), f, "r", 1e308, 5e-324)
        self.assertTrue(any("not representable" in x for x in f), f)
        f = []; bg._stat_findings({"value": -0.9, "special": None}, f, "d", 1e308, 5e-324, 200)
        self.assertTrue(any("not representable" in x for x in f), f)
        self.assertEqual(bg.implied_cohen_d(1e308, 5e-324, 200), {"value": None, "special": bg.UNREPRESENTABLE})
        self.assertEqual(bg.implied_cohen_d(1.0, 1e308, 200), {"value": None, "special": bg.UNREPRESENTABLE}, "the sample variance overflows: never a silent 0.0")
        self.assertEqual(bg.implied_cohen_d(1.0, 5e-324, 200)["special"], None, "a representable tiny variance keeps its finite d")
        self.assertEqual(bg.implied_cohen_d(5.0, 0, 200), {"value": None, "special": "+inf"}); self.assertEqual(bg.implied_cohen_d(5.0, 0, 1), {"value": 0.0, "special": None})
        for name, mutate, part in (("finite_ratio_overflow", finite_ratio_overflow, "not representable (overflow)"),
                                   ("overflowing_implied_d", overflowing_implied_d, "not representable (overflow / underflow)")):
            s = synthetic_summary(); mutate(s)
            self.assertEqual(bg.numeric_findings(s), [], name)                       # every input finite: only the derived arithmetic can object
            f = bg.summary_contract_findings(s, 200)
            self.assertTrue(any(part in x for x in f), (name, f))
            j = bg.judge(synthetic_doc(s), "synthetic_summary")
            self.assertEqual(j["verdict"]["status"], "invalid", name); self.assertEqual([r["status"] for r in j["rows"]], ["not_assessable"] * 10, name)

    def test_the_tolerance_is_a_consistency_check_not_a_criterion_the_boundary_limit_disclosed(self):
        """The owner's review of b49b2ec, section 2, recorded as a limit: the integer delta sequence [20, −18, 7, −5, 2, 0] + [1] × 194 has mean 1,
        population variance 3.98 and the production d exactly 0.5; a synthetic summary with those statistics PASSES K5; both recorded copies of
        d moved to 0.5 − 5e-13 stay within D_REL_TOL (no contract finding) and K5 and the verdict become FAIL. The tolerance validates the
        consistency of a summary with its own statistics; it is not the K5 threshold, no epsilon is added to K5, and a production archive's d is
        bound to its raw delta sequence by the archive-wide verifier's exact recomputation, which this summary-only check does not replace."""
        deltas = [20, -18, 7, -5, 2, 0] + [1] * 194
        self.assertEqual((gs.mean(deltas), statistics.pvariance(deltas), gs.cohen_d(deltas)), (1.0, 3.98, 0.5))
        self.assertEqual(bg.implied_cohen_d(1.0, 3.98, 200), {"value": 0.5, "special": None})
        s = synthetic_summary(d1=(1.0, 150, 20, 30), var1=3.98)
        self.assertEqual(bg.summary_contract_findings(s, 200), [])
        self.assertEqual(s["at_candidate_B_star"]["k5"]["cohen_d_delta1"], {"value": 0.5, "special": None})
        self.assertEqual(rows_by_id(bg.judge(synthetic_doc(s), "synthetic_summary"))["K5"]["status"], "PASS")
        below = {"value": 0.5 - 5e-13, "special": None}
        for B in GRID:
            s["per_budget"][str(B)]["deltas"]["delta1_O_minus_R"]["cohen_d"] = dict(below)
        s["at_candidate_B_star"]["k5"]["cohen_d_delta1"] = dict(below)
        self.assertEqual(bg.summary_contract_findings(s, 200), [], "within the consistency tolerance: no finding — the disclosed limit")
        j = bg.judge(synthetic_doc(s), "synthetic_summary")
        self.assertEqual((rows_by_id(j)["K5"]["status"], j["verdict"]["status"], j["formal"]), ("FAIL", "FAIL", False))
        self.assertEqual(th.THRESHOLDS["K5"]["cohen_d_min"], 0.5, "the frozen threshold, unchanged: no epsilon")

    def test_the_committed_v0_1_16_archives_are_another_method_version_never_judged_here(self):
        """Protocol v0.2.0: the committed S = 32 exploration and the production gate-1 archive were written by the v0.1.16 tool. Their summaries
        do not carry K9's two records, so the judge's contract refuses them (invalid, nothing judged) and `judge_batch` refuses them BY NAME
        before anything is written (no protocol identity; the re-verification procedure named). Nothing is touched; their verdicts stand
        as the records of their own version (docs/b4_archive_reverification.md)."""
        for path in (SIM3_REPORT, R / "evidence/b4/sim/b4-gate-1_20261020T102526Z/sim_report.json"):
            before = path.read_bytes()
            rep = json.loads(before)
            self.assertTrue(bg.summary_contract_findings(rep["summary"], rep["count"]), "a v0.1.16 summary breaks the v0.2.0 contract (the K9 records)")
            j = bg.judge(rep, "batch_archive")
            self.assertEqual(j["verdict"]["status"], "invalid"); self.assertTrue(j["contract_findings"]); self.assertEqual([r["status"] for r in j["rows"]], ["not_assessable"] * 10)
            r = bg.judge_batch(R, path.parent)
            self.assertEqual((r["status"], r["gate_out"]), ("refused", None)); self.assertIn("no protocol identity", r["reason"]); self.assertIn("b4_archive_reverification", r["reason"])
            self.assertEqual(path.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in (R / bg.GATE_REL).iterdir()), ["b4-gate-1_20261020T102526Z"], "nothing was written to the repository's gate namespace")

    def test_standing_for_the_harness_s_labels(self):
        self.assertEqual(sim.standing_for("b4-sim-3"), sim.STANDING); self.assertEqual(sim.standing_for("b4-mech-1"), sim.STANDING)
        self.assertEqual(sim.standing_for("b4-gate-1"), sim.STANDING_GATE); self.assertNotEqual(sim.STANDING_GATE, sim.STANDING)
        self.assertIn("not a gate verdict", sim.STANDING_GATE); self.assertIn("b4_gate.py", sim.STANDING_GATE)
        self.assertIn("protocol v0.3.0", sim.STANDING); self.assertIn("task-v0.3", sim.STANDING); self.assertIn("(b')", sim.STANDING)
        self.assertTrue(any(bp.RECORD_SCHEMAS["b4_sim_report"][0] in x for x in sc.report_findings(json.loads(SIM3_REPORT.read_bytes()))), "the committed v0.1.16 report is another schema version: not this tool's")

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
        self.assertTrue(bg.synthetic_findings(None)); self.assertTrue(bg.synthetic_findings([]))


# ------------------------------------------------------------------ end to end on a hermetic copy
class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guards = [mock.patch.object(bs, "master_seed", side_effect=production_derivation_reached), mock.patch.object(bs, "pair_seeds", side_effect=production_derivation_reached)]
        cls.guard_mocks = [g.start() for g in cls.guards]
        try:
            cls.tmp = tempfile.TemporaryDirectory(prefix="b4gate_")
            cls.root = build_hermetic(Path(cls.tmp.name))
            cls.ns = cls.root / sim.SIM_REL
            cls.gns = cls.root / bg.GATE_REL
            cls.counter = 0
            cls.setup_fixtures()
        except BaseException:
            for g in cls.guards:                                     # a failed set-up never leaks the guards into other modules
                g.stop()
            raise

    @classmethod
    def setup_fixtures(cls):
        pass

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
    def setup_fixtures(cls):
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
        import b4_protocol as bp
        self.assertEqual(doc["identity"]["protocol_sha256"], bp.protocol_sha256(bp.identity())); self.assertEqual(doc["identity"]["architecture_revision"], th.ARCHITECTURE_REVISION)
        self.assertEqual(doc["identity"]["gate_label"], "b4-gate-2")
        bm_ = json.loads((b / "manifest.json").read_text()); self.assertEqual(bm_["protocol"]["protocol_sha256"], doc["identity"]["protocol_sha256"], "the judgement and its evidence are of one method version")
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
        tamper(lambda d: d["rows"][5].__setitem__("status", "PASS"), bg.REPORT_JSON, "rows are not the ones recomputed")       # K6 (FAIL at S = 2) flipped; K9 PASSES on the fixture under (b')
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
        tamper(lambda d: d["identity"].__setitem__("protocol_sha256", "0" * 64), "protocol", "not this tool's")
        tamper(lambda d: d["identity"].__setitem__("architecture_revision", 7), bg.REPORT_JSON, "identity")
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
        syn["summary"]["k10"]["fraction_interacting_over_S"] = 0.4; syn["summary"]["k10"]["counts"].update(interacting=80, not_assessable=120)   # coherent: K10 FAILS
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

    def test_an_incoherent_synthetic_summary_cannot_be_made_a_clean_pass_by_refreshed_hashes(self):
        """R2 of the owner's review: the four accepted contradictions and the two exceptions, each written over the committed synthetic PASS
        evidence with the PASS report kept, every digest refreshed and the markdown re-rendered — the fresh-process verifier names it (the
        re-judgement is invalid, not PASS). The positive control: judged directly, each is an invalid report that verifies clean."""
        g = Path(self.b["gate_out"])
        cases = {"empty_N_scan": lambda s: s["per_budget"]["64"]["required_pairs"].__setitem__("scan", []),
                 "contradictory_delta1_d": lambda s: s["per_budget"]["64"]["deltas"]["delta1_O_minus_R"].__setitem__("cohen_d", {"value": -1.0, "special": None}),
                 "inconsistent_positive_infinity": lambda s: (s["per_budget"]["64"]["deltas"]["delta1_O_minus_R"].__setitem__("cohen_d", {"value": -100, "special": "+inf"}),
                                                              s["at_candidate_B_star"]["k5"].__setitem__("cohen_d_delta1", {"value": -100, "special": "+inf"})),
                 "K9_fraction_above_one": lambda s: s["k9"].__setitem__("fraction_of_S", 2.0),
                 "D_over_F_null": lambda s: s["at_candidate_B_star"]["k3"].__setitem__("D_over_F", None),
                 "B_star_as_float": lambda s: s["candidate_B_star"].__setitem__("value", 64.0),
                 "coordinated_false_cohen_pass": lambda s: (s["per_budget"]["64"]["deltas"]["delta1_O_minus_R"].__setitem__("cohen_d", {"value": 0.9, "special": None}),
                                                            s["at_candidate_B_star"]["k5"].__setitem__("cohen_d_delta1", {"value": 0.9, "special": None})),
                 "float_scan_n_min": lambda s: s["per_budget"]["64"]["required_pairs"].__setitem__("n_min", 8.0),
                 "float_at_k7_values": lambda s: s["at_candidate_B_star"]["k7"].__setitem__("values", [15.0] * 200),
                 "huge_json_integer": lambda s: s["per_budget"]["64"]["k1"].__setitem__("omega_best_p95", 10 ** 400),
                 "infinite_literal_in_thresholds": lambda s: s["thresholds_for_reference"]["K10"].__setitem__("tau", float("inf")),
                 "finite_ratio_overflow": finite_ratio_overflow, "overflowing_implied_d": overflowing_implied_d}
        refused = {"huge_json_integer", "infinite_literal_in_thresholds"}                   # a number no judgement could carry: refused at the evidence boundary, never written
        for name, mutate in cases.items():
            syn = json.loads(self.originals[g][bg.SYNTHETIC_JSON])
            if name == "coordinated_false_cohen_pass":
                syn["summary"] = synthetic_summary(d1=(0.5, 110, 60, 30), var1=4.0)         # the owner's base: K5 FAILS on its own numbers
                self.assertEqual(bg.summary_contract_findings(syn["summary"], 200), [])
            mutate(syn["summary"])
            self.assertTrue(bg.summary_contract_findings(syn["summary"], 200), name)
            (g / bg.SYNTHETIC_JSON).write_bytes((json.dumps(syn, indent=1, sort_keys=True) + "\n").encode())    # allow_nan: the infinite literal is written as the decoder reads it
            doc = json.loads(self.originals[g][bg.REPORT_JSON]); doc["batch"]["sha256"] = sim.sha_file(g / bg.SYNTHETIC_JSON)
            (g / bg.REPORT_JSON).write_bytes(sim.json_text(doc)); regate(g)
            code, out = self.fresh(g)
            self.restore(g)
            self.assertEqual(code, 1, name)
            msgs = [m for v in out["findings"].values() for m in v]
            self.assertTrue(any("not the ones recomputed" in m or "verdict PASS is not the recomputed invalid" in m or "beyond ±2^63" in m or "is not finite" in m for m in msgs), (name, out["findings"]))
            # the positive control: the same evidence judged directly is an invalid report, cleanly verifiable, exit 1 — or, for a number no
            # judgement could carry, a named refusal with nothing written
            r = bg.judge_synthetic(self.root, syn, self.gns / f"{SYN_LABEL}_neg_{name}")
            if name in refused:
                self.assertEqual((r["status"], r["gate_out"]), ("refused", None), name); self.assertTrue(("finite" in r["reason"]) or ("2^63" in r["reason"]), r["reason"])
                self.assertFalse((self.gns / f"{SYN_LABEL}_neg_{name}").exists())
                continue
            self.assertEqual((r["status"], r["exit_code"]), ("invalid", 1), name)
            d = json.loads((Path(r["gate_out"]) / bg.REPORT_JSON).read_text())
            self.assertEqual(d["verdict"]["status"], "invalid"); self.assertTrue(d["contract_findings"]); self.assertEqual([x["status"] for x in d["rows"]], ["not_assessable"] * 10)
            self.assertEqual(gv.verify_gate_dir(Path(r["gate_out"])), {}, name)
            self.commit()
        self.assertEqual(gv.verify_gate_dir(g), {}, "restored")

    def test_refusals_write_nothing_and_the_derivation_is_never_reached(self):
        before_g = sorted(p.name for p in self.gns.iterdir())
        before_s = sorted(p.name for p in self.ns.iterdir())
        # the production path: another label, S != 200 — refused before any tree is read
        with mock.patch.object(sim, "porcelain", side_effect=AssertionError("the tree was read")):
            r = bg.run_gate(self.root, "b4-gate-3", 200, 60); self.assertEqual(r["status"], "refused"); self.assertIn("pinned", r["reason"])
            r = bg.run_gate(self.root, "b4-gate-1", 200, 60); self.assertEqual(r["status"], "refused"); self.assertIn("consumed", r["reason"])
            r = bg.run_gate(self.root, "b4-gate-2", 2, 60); self.assertEqual(r["status"], "refused"); self.assertIn("S = 200", r["reason"])
            r = bg.run_gate(self.root, "b4-sim-3", 32, 60); self.assertEqual(r["status"], "refused")
            r = bg.run_gate(self.root, "b4-sim-4", 32, 60); self.assertEqual(r["status"], "refused"); self.assertIn("pinned", r["reason"])
            r = bg.run_gate(self.root, "b4-mech-1", 2, 60); self.assertEqual(r["status"], "refused"), "a mechanics label without a schedule is a production label mismatch"
        # a fixture batch under an exploration-mode harness is still refused the gate label; mode gate refuses exploration labels
        r = sim.run_batch(self.root, "b4-gate-2", 2, 60, self.ns / "b4-gate-2_x"); self.assertEqual(r["status"], "refused"); self.assertIn("mode gate only", r["reason"])
        r = sim.run_batch(self.root, "b4-sim-4", 2, 60, self.ns / "b4-sim-4_x", mode="gate"); self.assertEqual(r["status"], "refused"); self.assertIn("not a gate label", r["reason"])
        with mock.patch.object(sim, "porcelain", side_effect=AssertionError("the tree was read")):
            r = sim.run_batch(self.root, "b4-gate-1", 200, 60, None, mode="gate"); self.assertEqual(r["status"], "refused"); self.assertIn("consumed", r["reason"])
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
            self.assertEqual(bg.main(["run", "--label", "b4-gate-1", "--seeds", "200", "--deadline-s", "60"]), 2)
            self.assertEqual(bg.main(["run", "--label", "b4-gate-2", "--seeds", "2", "--deadline-s", "60"]), 2)
            self.assertEqual(bg.main(["run", "--label", "b4-gate-3", "--seeds", "200", "--deadline-s", "60"]), 2)
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

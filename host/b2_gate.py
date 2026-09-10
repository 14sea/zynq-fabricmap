#!/usr/bin/env python3
"""B2 — the discriminability gate (docs/b2_architecture.md §7), host simulation, before
any board time.

    b2_gate.py [--seeds 200] [--workers N] [--out evidence/b2/gate] [--fitness F2,F1,F3]

For every fitness of the family, every arm / control of §5 and S landscape seeds, one run
to the largest grid budget (best-so-far is a prefix property), then the criteria G1–G8 at
the frozen budget rule's B*, then the frozen selection rule (the first of F2, F1, F3 that
passes every row). Writes `gate_report.json` (the criteria, the numbers, the curves, the
pins: the architecture document's sha256 and the commit that fixed it, the maps' hashes,
the seeds' derivation) and `raw_<fid>.json` (every per-seed value the statistics used).
A criterion that fails is reported, never tuned here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_search as bs  # noqa: E402

ARCHITECTURE = REPO_ROOT / "docs/b2_architecture.md"
GATE_LABEL = "b2-gate"
SEEDS_DEFAULT = 200
GRID = (100, 200, 300, 400, 600, 800, 1000, 1500, 2000)
B_MAX = GRID[-1]
ARMS = ("A", "B", "C", "D", "E", "Q25", "Q50", "Q75")
CONTROL_ARMS = ("T", "W")                      # v0.3 §7a: train-membership-only, within-train column scramble
ARM_TEXT = {"A": "random-safe", "B": "self-map (B1)", "C": "oracle-map", "D": "shuffled-map", "E": "within-LUT shuffled",
            "Q25": "degraded q=1/4", "Q50": "degraded q=1/2", "Q75": "degraded q=3/4",
            "T": "train-membership only", "W": "within-train column scramble"}
Q_OF = {"Q25": 0.25, "Q50": 0.5, "Q75": 0.75}
THRESHOLDS = {
    "rules_version": "v0.3",
    "budget_rule": "min N(B) x 2 x B over grid budgets with G1 and finite N(B)",
    "G1_saturation_percentile": 95, "G2_bootstrap_experiments": 1000, "G2_null_nonreject_min": 0.90,
    "G3_shuffled_fraction_max": 0.10, "G3_alpha": 0.05,
    "G4_oracle_median_fraction_max": 0.90, "G4_self_vs_oracle_min": 0.90,
    "G5_cohen_d_min": 0.8, "G5_alpha": 0.05, "G5_power_min": 0.90, "G5_pairs_min": 8,
    "G5_total_evals_max": 13000,                   # a PLANNING bound on the experiment's total evaluations (v0.3: not a session-fit claim)
    "G5_session_evals_all_self_reporting": 6000,   # reported alongside: what one session at B1's all-self-reporting rate would hold
    "G9_alpha": 0.05,                              # the predeclared control comparison (architecture v0.3 §7a)
    "G6_seeds_min": 200,
    "G7_q75_fraction_max": 0.50,
    "G8_lut_shuffled_fraction_max": 0.25,
}
SAMPLED_AUDIT_RATE_PER_HOUR = 12570 / 6763.9 * 3600      # zynq-psoracle S #3: 12 570 records in 6 763.9 s
ALL_SELF_REPORTING_RATE_PER_HOUR = 3367.75                # evidence/b1/plan.json rate_C2_planning (the slower of the two)

# ------------------------------------------------------------------ statistics (integer-safe, dependency-free)


def median(xs):
    return statistics.median(xs)


def percentile(xs, p):
    s = sorted(xs)
    if not s:
        raise ValueError("empty")
    k = (len(s) - 1) * p / 100.0
    f, c = math.floor(k), math.ceil(k)
    return s[f] if f == c else s[f] + (s[c] - s[f]) * (k - f)


def mean(xs):
    return sum(xs) / len(xs)


def cohen_d(deltas):
    if len(deltas) < 2:
        return 0.0
    sd = statistics.stdev(deltas)
    return mean(deltas) / sd if sd > 0 else (math.inf if mean(deltas) > 0 else 0.0)


def sign_test_p(deltas) -> tuple[float, int, int, int]:
    """One-sided exact sign test, H1: P(delta > 0) > 1/2. Returns (p, positives, negatives, ties)."""
    pos = sum(1 for d in deltas if d > 0)
    neg = sum(1 for d in deltas if d < 0)
    n = pos + neg
    if n == 0:
        return 1.0, pos, neg, len(deltas)
    p = sum(math.comb(n, i) for i in range(pos, n + 1)) / 2 ** n
    return p, pos, neg, len(deltas) - n


def bootstrap_reject_rate(deltas, n_pairs: int, alpha: float, experiments: int, seed: int) -> float:
    rng = random.Random(seed)
    rejects = 0
    for _ in range(experiments):
        sample = [deltas[rng.randrange(len(deltas))] for _ in range(n_pairs)]
        if sign_test_p(sample)[0] <= alpha:
            rejects += 1
    return rejects / experiments


def required_pairs(deltas, alpha: float, power_min: float, experiments: int, seed: int, n_min: int, n_max: int):
    """The smallest N in [n_min, n_max] whose bootstrap power reaches power_min — EVERY N
    scanned in ascending order (the declared rule). Bootstrap power is not monotone in N
    (discrete rejection regions, simulation noise), so no bracketing or n_max shortcut may
    skip a candidate: the owner's review of 2026-09-10 found the earlier geometric sweep
    returning N = 91 where N = 89 already had power 0.906 (F3, budget 300)."""
    last = None
    for n in range(n_min, n_max + 1):
        last = bootstrap_reject_rate(deltas, n, alpha, experiments, seed + n)
        if last >= power_min:
            return n, last
    return None, last


# ------------------------------------------------------------------ the runs

_CTX: dict = {}


def _init_worker(fid: str):
    truth = bm.truth_mapping()
    _CTX["truth"] = truth
    _CTX["masks"] = bl.universe_mask(truth)
    _CTX["fabric"] = bs.ModelFabric(truth)
    _CTX["self_map"] = bmaps.load_self_map()
    _CTX["oracle"] = bmaps.oracle_map(truth)
    _CTX["fid"] = fid
    _CTX["train"] = bl.train_vectors()


def _arm_docs(r: int) -> dict:
    sm = _CTX["self_map"]
    return {"A": None, "B": sm, "C": _CTX["oracle"], "D": bmaps.shuffled_map(sm, r), "E": bmaps.lut_shuffled_map(sm, r),
            "Q25": bmaps.degraded_map(sm, 0.25, r), "Q50": bmaps.degraded_map(sm, 0.5, r), "Q75": bmaps.degraded_map(sm, 0.75, r)}


def _one_seed(args) -> dict:
    r, l_seed, o_seed = args
    fid = _CTX["fid"]
    land = bl.Landscape(fid, l_seed, masks=_CTX["masks"], truth=_CTX["truth"])
    out = {"r": r, "landscape_seed": l_seed, "operator_seed": o_seed, "base_fit": land.train_fitness(_CTX["fabric"](0)), "arms": {}}
    for arm, doc in _arm_docs(r).items():
        view = bmaps.MapView(doc, _CTX["train"])
        res = bs.run(bs.ARM_RANDOM_SAFE if arm == "A" else bs.ARM_MAP_GUIDED, land, view, o_seed, B_MAX, _CTX["fabric"])
        out["arms"][arm] = {"at_grid": [res.best_trace[b - 1] for b in GRID], "champion_holdout": res.champion_holdout,
                            "column_moves": res.column_moves, "mapped_bits_in_train": view.mapped_bits()}
    return out


def run_fitness(fid: str, seeds: list[tuple[int, int]], workers: int) -> list[dict]:
    jobs = [(r, l, o) for r, (l, o) in enumerate(seeds)]
    with Pool(workers, initializer=_init_worker, initargs=(fid,)) as pool:
        rows = pool.map(_one_seed, jobs, chunksize=4)
    rows.sort(key=lambda x: x["r"])
    return rows


# ------------------------------------------------------------------ the criteria


def per_budget(rows: list[dict]) -> list[dict]:
    """For every grid budget: the arms' medians, arm B's paired-difference statistics,
    N(B) by bootstrap power, the session cost, and whether G1 holds there."""
    T = THRESHOLDS
    S = len(rows)
    base = [row["base_fit"] for row in rows]
    out = []
    for i, b in enumerate(GRID):
        at = {arm: [row["arms"][arm]["at_grid"][i] for row in rows] for arm in ARMS}
        dB = [at["B"][j] - at["A"][j] for j in range(S)]
        p, pos, neg, ties = sign_test_p(dB)
        n_req, power = required_pairs(dB, T["G5_alpha"], T["G5_power_min"], T["G2_bootstrap_experiments"], 1, T["G5_pairs_min"], S)
        out.append({"budget": b, "median": {a: median(at[a]) for a in ARMS}, "oracle_p95": None, "mean_delta_B": mean(dB),
                    "cohen_d_B": cohen_d(dB), "positives": pos, "negatives": neg, "ties": ties, "sign_test_p_full_S": p,
                    "required_pairs_N": n_req, "power_at_N": power, "session_evaluations": (n_req * 2 * b) if n_req else None,
                    "random_median_above_base": median(at["A"]) > median(base)})
    return out


def evaluate(fid: str, rows: list[dict]) -> dict:
    T = THRESHOLDS
    ceiling = bl.CEILING[fid]
    S = len(rows)
    base = [row["base_fit"] for row in rows]
    table = per_budget(rows)
    for i, t in enumerate(table):
        at_c = [row["arms"]["C"]["at_grid"][i] for row in rows]
        t["oracle_p95"] = percentile(at_c, T["G1_saturation_percentile"])
        t["G1"] = t["oracle_p95"] < ceiling and t["random_median_above_base"]
    curves = {arm: [t["median"][arm] for t in table] for arm in ARMS}
    eligible = [t for t in table if t["G1"] and t["session_evaluations"] is not None]
    if not eligible:
        return {"fitness": fid, "ceiling": ceiling, "seeds": S, "grid": list(GRID), "curves_median": curves, "per_budget": table,
                "b_star": None, "criteria": {"budget_rule": {"pass": False, "note": "no grid budget has both G1 and a finite N(B)"}},
                "pass": False}
    best = min(eligible, key=lambda t: (t["session_evaluations"], t["budget"]))
    b_star = best["budget"]
    b_index = GRID.index(b_star)
    at = {arm: [row["arms"][arm]["at_grid"][b_index] for row in rows] for arm in ARMS}
    delta = {arm: [at[arm][i] - at["A"][i] for i in range(S)] for arm in ARMS if arm != "A"}
    md = {arm: mean(delta[arm]) for arm in delta}
    crit: dict[str, dict] = {}
    crit["budget_rule"] = {"b_star": b_star, "session_evaluations": best["session_evaluations"], "rule": "min N(B) x 2 x B over budgets with G1 and finite N(B)",
                           "candidates": [{"budget": t["budget"], "N": t["required_pairs_N"], "cost": t["session_evaluations"], "G1": t["G1"]} for t in table],
                           "pass": True}

    c_p95 = best["oracle_p95"]
    crit["G1"] = {"oracle_p95": c_p95, "ceiling": ceiling, "random_median": median(at["A"]), "base_median": median(base),
                  "pass": c_p95 < ceiling and median(at["A"]) > median(base)}

    d_B = cohen_d(delta["B"])
    p_B, pos_B, neg_B, ties_B = sign_test_p(delta["B"])
    n_req = best["required_pairs_N"]
    session_evals = best["session_evaluations"]
    crit["G5"] = {"cohen_d": d_B, "mean_delta": md["B"], "sd_delta": statistics.stdev(delta["B"]) if S > 1 else 0.0,
                  "sign_test_p_full_S": p_B, "positives": pos_B, "negatives": neg_B, "ties": ties_B,
                  "required_pairs_N": n_req, "power_at_N": best["power_at_N"], "total_evaluations": session_evals,
                  "planning_hours_at_sampled_audit_rate_S3": session_evals / SAMPLED_AUDIT_RATE_PER_HOUR,
                  "planning_hours_at_all_self_reporting_rate_B1plan": session_evals / ALL_SELF_REPORTING_RATE_PER_HOUR,
                  "fits_one_session_at_all_self_reporting_planning_rate": session_evals <= T["G5_session_evals_all_self_reporting"],
                  "note": "v0.3: the bound is on TOTAL evaluations; how many sessions they take is decided by the B2Q-measured "
                          "all-self-reporting rate (preregistration §2), never by these planning rates",
                  "pass": d_B >= T["G5_cohen_d_min"] and session_evals <= T["G5_total_evals_max"]}

    var_delta = statistics.pvariance(delta["B"]) if S > 1 else 0.0
    both_signs_somewhere = any(t["positives"] > 0 and t["negatives"] > 0 for t in table)
    null_nonreject = 1.0 - bootstrap_reject_rate(delta["D"], n_req, T["G5_alpha"], T["G2_bootstrap_experiments"], 7)
    crit["G2"] = {"var_delta": var_delta, "both_signs_at_some_budget": both_signs_somewhere,
                  "signs_by_budget": [[t["budget"], t["positives"], t["negatives"], t["ties"]] for t in table],
                  "N_used": n_req, "shuffled_nonreject_rate": null_nonreject,
                  "pass": var_delta > 0 and both_signs_somewhere and null_nonreject >= T["G2_null_nonreject_min"]}

    p_D = sign_test_p(delta["D"])[0]
    crit["G3"] = {"mean_delta_shuffled": md["D"], "mean_delta_self": md["B"],
                  "fraction": (md["D"] / md["B"]) if md["B"] > 0 else None, "sign_test_p_shuffled": p_D,
                  "pass": md["B"] > 0 and md["D"] <= T["G3_shuffled_fraction_max"] * md["B"] and p_D > T["G3_alpha"]}

    c_med = median(at["C"])
    crit["G4"] = {"oracle_median": c_med, "ceiling": ceiling, "mean_delta_oracle": md["C"], "mean_delta_self": md["B"],
                  "self_vs_oracle": (md["B"] / md["C"]) if md["C"] > 0 else None,
                  "pass": c_med <= T["G4_oracle_median_fraction_max"] * ceiling and md["C"] > 0 and md["B"] >= T["G4_self_vs_oracle_min"] * md["C"]}

    crit["G6"] = {"seeds": S, "var_delta": var_delta, "pairs_min": T["G5_pairs_min"], "N": n_req,
                  "pass": S >= T["G6_seeds_min"] and var_delta > 0 and n_req >= T["G5_pairs_min"]}

    dose = [md["B"], md["Q25"], md["Q50"], md["Q75"]]
    monotone = all(dose[i] >= dose[i + 1] for i in range(len(dose) - 1))
    crit["G7"] = {"mean_delta_by_q": {"0": md["B"], "0.25": md["Q25"], "0.5": md["Q50"], "0.75": md["Q75"], "1 (reported)": 0.0},
                  "monotone_non_increasing_0_to_3q": monotone, "q75_below_random_safe": md["Q75"] < 0,
                  "pass": monotone and md["B"] > 0 and md["Q75"] <= T["G7_q75_fraction_max"] * md["B"]}

    crit["G8"] = {"mean_delta_lut_shuffled": md["E"], "mean_delta_self": md["B"],
                  "fraction": (md["E"] / md["B"]) if md["B"] > 0 else None,
                  "pass": md["B"] > 0 and md["E"] <= T["G8_lut_shuffled_fraction_max"] * md["B"]}

    holdout = {arm: median([row["arms"][arm]["champion_holdout"] for row in rows]) for arm in ARMS}
    column_moves = {arm: mean([row["arms"][arm]["column_moves"] for row in rows]) for arm in ARMS}
    return {"fitness": fid, "ceiling": ceiling, "seeds": S, "grid": list(GRID), "b_star": b_star,
            "curves_median": curves, "per_budget": table, "at_b_star_median": {a: median(at[a]) for a in ARMS},
            "mean_delta_vs_A_at_b_star": md, "champion_holdout_median": holdout, "column_moves_mean_to_B_max": column_moves,
            "criteria": crit, "pass": all(c["pass"] for c in crit.values())}


# ------------------------------------------------------------------ the predeclared control comparison (v0.3 §7a)


def _control_docs(r: int) -> dict:
    sm = _CTX["self_map"]
    return {"T": ("membership", sm), "W": ("doc", bmaps.within_train_scrambled_map(sm, r, _CTX["train"]))}


def _one_seed_controls(args) -> dict:
    r, l_seed, o_seed = args
    land = bl.Landscape(_CTX["fid"], l_seed, masks=_CTX["masks"], truth=_CTX["truth"])
    out = {"r": r, "landscape_seed": l_seed, "operator_seed": o_seed, "arms": {}}
    for arm, (kind, doc) in _control_docs(r).items():
        view = bmaps.train_membership_view(doc, _CTX["train"]) if kind == "membership" else bmaps.MapView(doc, _CTX["train"])
        res = bs.run(bs.ARM_MAP_GUIDED, land, view, o_seed, B_MAX, _CTX["fabric"])
        out["arms"][arm] = {"at_grid": [res.best_trace[b - 1] for b in GRID], "champion_holdout": res.champion_holdout,
                            "column_moves": res.column_moves, "mapped_bits_in_train": view.mapped_bits(),
                            "train_membership": bmaps.membership_counts(view, _CTX["truth"], _CTX["train"])}
    return out


def run_controls(fid: str, rows: list[dict], workers: int) -> list[dict]:
    jobs = [(row["r"], row["landscape_seed"], row["operator_seed"]) for row in rows]
    with Pool(workers, initializer=_init_worker, initargs=(fid,)) as pool:
        out = pool.map(_one_seed_controls, jobs, chunksize=4)
    out.sort(key=lambda x: x["r"])
    return out


def evaluate_controls(fid: str, rows: list[dict], control_rows: list[dict], b_star: int) -> dict:
    """G9 (predeclared, architecture v0.3 §7a): at the recomputed B*, the self-map arm beats
    BOTH the train-membership-only arm (T) and the within-train column scramble (W) —
    one-sided sign tests, alpha 0.05 — so the benefit is correct column grouping beyond
    train membership and beyond the column-size / move-size distribution. Neither control
    is required to lose to random-safe; their Δ vs A is reported."""
    T = THRESHOLDS
    if [row["r"] for row in rows] != [row["r"] for row in control_rows]:
        raise ValueError("control rows do not pair with the main rows")
    i = GRID.index(b_star)
    S = len(rows)
    a = [row["arms"]["A"]["at_grid"][i] for row in rows]
    b = [row["arms"]["B"]["at_grid"][i] for row in rows]
    out = {"fitness": fid, "b_star": b_star, "seeds": S, "arms": {}, "per_budget": {}}
    for arm in CONTROL_ARMS:
        x = [row["arms"][arm]["at_grid"][i] for row in control_rows]
        d_bx = [b[j] - x[j] for j in range(S)]
        d_xa = [x[j] - a[j] for j in range(S)]
        p_bx, pos, neg, ties = sign_test_p(d_bx)
        out["arms"][arm] = {"text": ARM_TEXT[arm], "median": median(x), "mean_delta_vs_A": mean(d_xa), "mean_delta_B_minus_arm": mean(d_bx),
                            "cohen_d_B_minus_arm": cohen_d(d_bx), "positives": pos, "negatives": neg, "ties": ties, "sign_test_p_B_gt_arm": p_bx,
                            "fraction_of_B_benefit_retained": (mean(d_xa) / mean([b[j] - a[j] for j in range(S)])) if mean([b[j] - a[j] for j in range(S)]) else None,
                            "train_membership": control_rows[0]["arms"][arm]["train_membership"],
                            "pass": p_bx <= T["G9_alpha"]}
        out["per_budget"][arm] = [{"budget": GRID[k], "median": median([row["arms"][arm]["at_grid"][k] for row in control_rows]),
                                   "mean_delta_B_minus_arm": mean([rows[j]["arms"]["B"]["at_grid"][k] - control_rows[j]["arms"][arm]["at_grid"][k] for j in range(S)])}
                                  for k in range(len(GRID))]
    out["G9"] = {"pass": all(out["arms"][arm]["pass"] for arm in CONTROL_ARMS), "alpha": T["G9_alpha"],
                 "rule": "B > T and B > W at B*, one-sided exact sign tests, alpha 0.05 (architecture v0.3 §7a, predeclared before the run)"}
    return out


# ------------------------------------------------------------------ the report


def git_head() -> str | None:
    p = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def git_dirty() -> bool:
    p = subprocess.run(["git", "-C", str(REPO_ROOT), "status", "--porcelain"], capture_output=True, text=True)
    return bool(p.stdout.strip())


def architecture_pin() -> dict:
    text = ARCHITECTURE.read_bytes()
    p = subprocess.run(["git", "-C", str(REPO_ROOT), "log", "-n", "1", "--format=%H", "--", "docs/b2_architecture.md"],
                       capture_output=True, text=True)
    return {"path": "docs/b2_architecture.md", "sha256": hashlib.sha256(text).hexdigest(),
            "last_commit": p.stdout.strip() or None}


def load_rows(src: Path) -> dict:
    """The stored raw rows of a gate run, by fitness, with the run's report."""
    report = json.loads((src / "gate_report.json").read_text())
    rows = {fid: json.loads((src / f"raw_{fid}.json").read_text())["rows"] for fid in report["results"]}
    return {"report": report, "rows": rows}


def recompute(src: Path, out: Path, label: str) -> dict:
    """Re-evaluate the stored raw rows of a run under the CURRENT rules and code, into a
    separately labelled directory; the source report is not touched."""
    stored = load_rows(src)
    results = {fid: evaluate(fid, rows) for fid, rows in stored["rows"].items()}
    order = [f for f in bl.FITNESS_IDS if f in results]
    selected = next((f for f in order if results[f]["pass"]), None)
    rep = {"schema": "b2_gate_recomputation", "schema_version": "1.0.0", "label": label,
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "head_at_run": git_head(),
           "source": {"path": str(src.relative_to(REPO_ROOT)), "gate_report_sha256": hashlib.sha256((src / "gate_report.json").read_bytes()).hexdigest(),
                      "raw_sha256": {fid: hashlib.sha256((src / f"raw_{fid}.json").read_bytes()).hexdigest() for fid in stored["rows"]},
                      "seeds": stored["report"]["seeds"], "rules_version_at_source": stored["report"]["thresholds"].get("rules_version")},
           "architecture": architecture_pin(), "thresholds": THRESHOLDS, "selection_order": list(bl.FITNESS_IDS), "selected_fitness": selected,
           "results": results}
    out.mkdir(parents=True, exist_ok=True)
    (out / "gate_report.json").write_text(json.dumps(rep, indent=1, sort_keys=True))
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", nargs="?", default="run", choices=["run", "recompute", "controls"])
    ap.add_argument("--from", dest="src", default="evidence/b2/gate", help="recompute/controls: the stored run to reuse (rows and seeds)")
    ap.add_argument("--label", default="")
    ap.add_argument("--seeds", type=int, default=SEEDS_DEFAULT)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--out", default="evidence/b2/gate")
    ap.add_argument("--fitness", default=",".join(bl.FITNESS_IDS))
    args = ap.parse_args(argv)
    out = REPO_ROOT / args.out
    if args.command == "recompute":
        rep = recompute(REPO_ROOT / args.src, out, args.label)
        for fid, x in rep["results"].items():
            print(f"[{fid}] B*={x.get('b_star')} pass={x['pass']} { {k: v['pass'] for k, v in x['criteria'].items()} }")
        print(f"selected fitness: {rep['selected_fitness']}; {out / 'gate_report.json'}")
        return 0
    if args.command == "controls":
        src = REPO_ROOT / args.src
        stored = load_rows(src)
        rec = json.loads((out / "gate_report.json").read_text()) if (out / "gate_report.json").is_file() else None
        if rec is None:
            raise SystemExit("controls: run `recompute` into --out first (B* is taken from the recomputed report)")
        fids = [f for f in args.fitness.split(",") if f]
        res = {}
        for fid in fids:
            b_star = rec["results"][fid]["b_star"]
            if b_star is None:
                res[fid] = {"fitness": fid, "b_star": None, "G9": {"pass": False, "note": "no B*"}}
                continue
            t0 = time.time()
            crow = run_controls(fid, stored["rows"][fid], args.workers)
            (out / f"raw_controls_{fid}.json").write_text(json.dumps({"fitness": fid, "grid": list(GRID), "rows": crow}, separators=(",", ":")))
            res[fid] = evaluate_controls(fid, stored["rows"][fid], crow, b_star)
            res[fid]["wall_s"] = round(time.time() - t0, 1)
            print(f"[{fid}] G9={res[fid]['G9']['pass']} " + " ".join(f"{a}: B-{a} {res[fid]['arms'][a]['mean_delta_B_minus_arm']:+.2f} p={res[fid]['arms'][a]['sign_test_p_B_gt_arm']:.2e}" for a in CONTROL_ARMS), flush=True)
        rep = {"schema": "b2_gate_controls", "schema_version": "1.0.0", "label": args.label, "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "head_at_run": git_head(), "worktree_dirty_at_start": git_dirty(), "architecture": architecture_pin(), "thresholds": THRESHOLDS,
               "source": {"path": str(src.relative_to(REPO_ROOT)), "seeds": stored["report"]["seeds"]}, "results": res}
        (out / "controls_report.json").write_text(json.dumps(rep, indent=1, sort_keys=True))
        print(out / "controls_report.json")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    head = git_head()
    dirty_at_start = git_dirty()          # before this run writes anything into the tree
    master = bs.master_seed(GATE_LABEL, head or "no-commit")
    seeds = bs.pair_seeds(master, args.seeds)
    fids = [f for f in args.fitness.split(",") if f]
    for f in fids:
        if f not in bl.FITNESS:
            raise SystemExit(f"unknown fitness {f}")
    started = time.time()
    results = {}
    for fid in fids:
        t0 = time.time()
        rows = run_fitness(fid, seeds, args.workers)
        (out / f"raw_{fid}.json").write_text(json.dumps({"fitness": fid, "grid": list(GRID), "rows": rows}, separators=(",", ":")))
        results[fid] = evaluate(fid, rows)
        results[fid]["wall_s"] = round(time.time() - t0, 1)
        print(f"[{fid}] B*={results[fid].get('b_star')} pass={results[fid]['pass']} "
              f"{ {k: v['pass'] for k, v in results[fid]['criteria'].items()} } {results[fid]['wall_s']}s", flush=True)
    order = [f for f in bl.FITNESS_IDS if f in results]
    selected = next((f for f in order if results[f]["pass"]), None)
    sm = bmaps.load_self_map()
    oracle = bmaps.oracle_map()
    agree, compared = bmaps.relations_equal(sm, oracle)
    report = {
        "schema": "b2_gate_report", "schema_version": "1.0.0",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "head_at_run": head, "worktree_dirty_at_start": dirty_at_start,
        "architecture": architecture_pin(), "thresholds": THRESHOLDS, "engine": {"version": bs.ENGINE_VERSION, "mu": bs.MU, "lambda": bs.LAMBDA, "kmax": bs.KMAX},
        "seeds": {"label": GATE_LABEL, "master_seed": master, "derivation": f"first 4 bytes of sha256('{GATE_LABEL}|' + HEAD), pairs from one Rng stream, excluded seeds skipped",
                  "count": args.seeds, "excluded": sorted(bs.EXCLUDED_SEEDS)},
        "maps": {"self_map": {"path": str(bmaps.SELF_MAP.relative_to(REPO_ROOT)), "sha256": bmaps.sha256_of(sm), "cartographer": sm["cartographer"]},
                 "oracle": {"sha256": bmaps.sha256_of(oracle), "relations_agree_with_self_map": [agree, compared]}},
        "selection_order": list(bl.FITNESS_IDS), "selected_fitness": selected,
        "results": results, "wall_s": round(time.time() - started, 1),
    }
    (out / "gate_report.json").write_text(json.dumps(report, indent=1, sort_keys=True))
    print(f"selected fitness: {selected}; report {out / 'gate_report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
ARM_TEXT = {"A": "random-safe", "B": "self-map (B1)", "C": "oracle-map", "D": "shuffled-map", "E": "within-LUT shuffled",
            "Q25": "degraded q=1/4", "Q50": "degraded q=1/2", "Q75": "degraded q=3/4"}
Q_OF = {"Q25": 0.25, "Q50": 0.5, "Q75": 0.75}
THRESHOLDS = {
    "budget_rule_oracle_median_fraction": 0.60,
    "G1_saturation_percentile": 95, "G2_bootstrap_experiments": 1000, "G2_null_nonreject_min": 0.90,
    "G3_shuffled_fraction_max": 0.10, "G3_alpha": 0.05,
    "G4_oracle_median_fraction_max": 0.90, "G4_self_vs_oracle_min": 0.90,
    "G5_cohen_d_min": 0.8, "G5_alpha": 0.05, "G5_power_min": 0.90, "G5_session_evals_max": 6000, "G5_pairs_min": 8,
    "G6_seeds_min": 200,
    "G7_q75_fraction_max": 0.50,
    "G8_lut_shuffled_fraction_max": 0.25,
}
EVIDENCED_RATE_PER_HOUR = 3367.75      # evidence/b1/plan.json rate_C2_planning (the slower of the two)

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
    for n in range(n_min, n_max + 1):
        power = bootstrap_reject_rate(deltas, n, alpha, experiments, seed + n)
        if power >= power_min:
            return n, power
    return None, bootstrap_reject_rate(deltas, n_max, alpha, experiments, seed + n_max)


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


def evaluate(fid: str, rows: list[dict]) -> dict:
    T = THRESHOLDS
    ceiling = bl.CEILING[fid]
    S = len(rows)
    curves = {arm: [median([row["arms"][arm]["at_grid"][i] for row in rows]) for i in range(len(GRID))] for arm in ARMS}
    b_index = next((i for i, m in enumerate(curves["C"]) if m >= T["budget_rule_oracle_median_fraction"] * ceiling), None)
    if b_index is None:
        return {"fitness": fid, "ceiling": ceiling, "seeds": S, "curves": {a: c for a, c in curves.items()}, "grid": list(GRID),
                "b_star": None, "criteria": {"budget_rule": {"pass": False, "note": "the oracle arm's median never reaches the fraction on the grid"}},
                "pass": False}
    b_star = GRID[b_index]
    at = {arm: [row["arms"][arm]["at_grid"][b_index] for row in rows] for arm in ARMS}
    base = [row["base_fit"] for row in rows]
    delta = {arm: [at[arm][i] - at["A"][i] for i in range(S)] for arm in ARMS if arm != "A"}
    md = {arm: mean(delta[arm]) for arm in delta}
    crit: dict[str, dict] = {}

    c_p95 = percentile(at["C"], T["G1_saturation_percentile"])
    crit["G1"] = {"oracle_p95": c_p95, "ceiling": ceiling, "random_median": median(at["A"]), "base_median": median(base),
                  "pass": c_p95 < ceiling and median(at["A"]) > median(base)}

    p_pos = sum(1 for d in delta["B"] if d > 0) / S
    p_neg = sum(1 for d in delta["B"] if d < 0) / S
    # G5 first (N is needed by G2)
    d_B = cohen_d(delta["B"])
    p_B, pos_B, neg_B, ties_B = sign_test_p(delta["B"])
    n_req, power_at_n = required_pairs(delta["B"], T["G5_alpha"], T["G5_power_min"], T["G2_bootstrap_experiments"], 1, T["G5_pairs_min"], S)
    session_evals = (n_req * 2 * b_star) if n_req else None
    crit["G5"] = {"cohen_d": d_B, "mean_delta": md["B"], "sd_delta": statistics.stdev(delta["B"]) if S > 1 else 0.0,
                  "sign_test_p_full_S": p_B, "positives": pos_B, "negatives": neg_B, "ties": ties_B,
                  "required_pairs_N": n_req, "power_at_N": power_at_n, "session_evaluations": session_evals,
                  "session_hours_at_evidenced_rate": (session_evals / EVIDENCED_RATE_PER_HOUR) if session_evals else None,
                  "pass": d_B >= T["G5_cohen_d_min"] and n_req is not None and session_evals <= T["G5_session_evals_max"]}

    n_for_g2 = n_req if n_req else T["G5_pairs_min"]
    null_nonreject = 1.0 - bootstrap_reject_rate(delta["D"], n_for_g2, T["G5_alpha"], T["G2_bootstrap_experiments"], 7)
    crit["G2"] = {"p_delta_pos": p_pos, "p_delta_neg": p_neg, "N_used": n_for_g2, "shuffled_nonreject_rate": null_nonreject,
                  "pass": 0 < p_pos < 1 and p_neg > 0 and null_nonreject >= T["G2_null_nonreject_min"]}

    p_D = sign_test_p(delta["D"])[0]
    crit["G3"] = {"mean_delta_shuffled": md["D"], "mean_delta_self": md["B"],
                  "fraction": (md["D"] / md["B"]) if md["B"] > 0 else None, "sign_test_p_shuffled": p_D,
                  "pass": md["B"] > 0 and md["D"] <= T["G3_shuffled_fraction_max"] * md["B"] and p_D > T["G3_alpha"]}

    c_med = median(at["C"])
    crit["G4"] = {"oracle_median": c_med, "ceiling": ceiling, "mean_delta_oracle": md["C"], "mean_delta_self": md["B"],
                  "self_vs_oracle": (md["B"] / md["C"]) if md["C"] > 0 else None,
                  "pass": c_med <= T["G4_oracle_median_fraction_max"] * ceiling and md["C"] > 0 and md["B"] >= T["G4_self_vs_oracle_min"] * md["C"]}

    var_delta = statistics.pvariance(delta["B"]) if S > 1 else 0.0
    crit["G6"] = {"seeds": S, "var_delta": var_delta, "pairs_min": T["G5_pairs_min"],
                  "pass": S >= T["G6_seeds_min"] and var_delta > 0 and (n_req is None or n_req >= T["G5_pairs_min"])}

    dose = [md["B"], md["Q25"], md["Q50"], md["Q75"], 0.0]
    monotone = all(dose[i] >= dose[i + 1] for i in range(len(dose) - 1))
    crit["G7"] = {"mean_delta_by_q": {"0": md["B"], "0.25": md["Q25"], "0.5": md["Q50"], "0.75": md["Q75"], "1": 0.0},
                  "monotone_non_increasing": monotone,
                  "pass": monotone and md["B"] > 0 and md["Q75"] <= T["G7_q75_fraction_max"] * md["B"]}

    crit["G8"] = {"mean_delta_lut_shuffled": md["E"], "mean_delta_self": md["B"],
                  "fraction": (md["E"] / md["B"]) if md["B"] > 0 else None,
                  "pass": md["B"] > 0 and md["E"] <= T["G8_lut_shuffled_fraction_max"] * md["B"]}

    crit["budget_rule"] = {"b_star": b_star, "oracle_median_at_b_star": c_med, "fraction_of_ceiling": c_med / ceiling, "pass": True}
    holdout = {arm: median([row["arms"][arm]["champion_holdout"] for row in rows]) for arm in ARMS}
    column_moves = {arm: mean([row["arms"][arm]["column_moves"] for row in rows]) for arm in ARMS}
    return {"fitness": fid, "ceiling": ceiling, "seeds": S, "grid": list(GRID), "b_star": b_star,
            "curves_median": curves, "at_b_star_median": {a: median(at[a]) for a in ARMS},
            "mean_delta_vs_A_at_b_star": md, "champion_holdout_median": holdout, "column_moves_mean_to_B_max": column_moves,
            "criteria": crit, "pass": all(c["pass"] for c in crit.values())}


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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=SEEDS_DEFAULT)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--out", default="evidence/b2/gate")
    ap.add_argument("--fitness", default=",".join(bl.FITNESS_IDS))
    args = ap.parse_args(argv)
    out = REPO_ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    head = git_head()
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
        "head_at_run": head, "worktree_dirty_at_run": git_dirty(),
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

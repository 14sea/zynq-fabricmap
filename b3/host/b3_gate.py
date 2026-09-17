#!/usr/bin/env python3
"""B3 lifecycle 1 — the B3 discriminability gate (docs/b3_architecture.md v0.2.3 §9), host simulation
before any board time.

    b3_gate.py [--seeds 200] [--workers N] [--fitness F1,F2] [--out evidence/b3/gate]

For every fitness (F1 is the gate's; F2 is reported for information), S landscape seeds under the
label `b3-gate` (every archived seed set excluded explicitly: B2's gate runs, the B3 simulation, B2's
nine session pairs and its B2Q pair), the four arms R / F / O / X to the largest grid budget, with
the O arm's ledger replayed and its online map verified per seed, and X's shadow isomorphism checked
per specimen. Then the per-budget statistics, N(B) by B2's bootstrap power scan (`b2_gate.required_pairs`
by import, seed 1 + N), the frozen budget rule min N(B) × 3 × B, and the criteria H1–H9 at B*.
Writes gate_report.json (the criteria with the numbers, the pins: this architecture document's
sha256 and last commit, the control-X seed and permutation digest, the seeds' derivation and every
exclusion source) and raw_<fid>.json (every per-seed value the statistics used). A criterion that
fails is reported, never tuned here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "host", REPO_ROOT / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_gate as bg  # noqa: E402            (sign_test_p, required_pairs, bootstrap_reject_rate, cohen_d, mean, median, percentile — by import)
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_carto as carto_mod  # noqa: E402
import b3_control_x as cx  # noqa: E402
import b3_online_arm as oa  # noqa: E402
import b3_online_map as om  # noqa: E402

ARCHITECTURE = REPO_ROOT / "docs/b3_architecture.md"
LEDGER_SCHEMA = REPO_ROOT / "b3/schemas/specimen_ledger.schema.json"
GATE_LABEL = "b3-gate"
SEEDS_DEFAULT = 200
GRID = (100, 200, 300, 400, 600, 800, 1000, 1500, 2000, 3000)
B_MAX = GRID[-1]
ARMS = ("R", "F", "O", "X")
ARM_TEXT = {"R": "random-safe (no map)", "F": "frozen B1 self-map", "O": "online map from specimens", "X": "control: scrambled specimens"}
THRESHOLDS = {
    "rules_version": "architecture v0.2.3 §9",
    "budget_rule": "min N(B) x 3 x B over grid budgets with H1 and finite N(B); ties to the smaller budget",
    "H1_saturation_percentile": 95,
    "H2_bootstrap_experiments": 1000, "H2_null_nonreject_min": 0.90, "H2_control_bootstrap_seed": 7,
    "H3_x_fraction_max": 0.10, "H3_alpha": 0.05,
    "H4_o_over_f_median_min": 0.80, "H4_alpha": 0.05,
    "H5_cohen_d_min": 0.5, "H5_alpha": 0.05, "H5_power_min": 0.90, "H5_pairs_min": 8, "H5_power_scan_seed": 1,
    "H5_search_evaluation_cap": 30000,
    "H6_seeds_min": 200,
    "H7_decoded_median_min": 146,
    "H9_alpha": 0.05,
    "b1_map_cost": oa.B1_MAP_COST,
}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------ the runs

_CTX: dict = {}


def _init_worker(fid: str, perm: list[int]):
    truth = bm.truth_mapping()
    _CTX.update(truth=truth, masks=bl.universe_mask(truth), fabric=bs.ModelFabric(truth), fid=fid, train=bl.train_vectors(),
                view=bmaps.MapView(bmaps.load_self_map(), bl.train_vectors()), perm=perm, schema=json.loads(LEDGER_SCHEMA.read_text()))


def _ledger_doc(res, l_seed: int, o_seed: int, fid: str, budget: int) -> dict:
    return {"schema": "specimen_ledger", "schema_version": oa.LEDGER_SCHEMA_VERSION,
            "binding": {"token": "00" * 16, "universe_sha256": "00" * 32, "image_sha256_lo32": "00000000", "landscape_seed": l_seed},
            "seed": o_seed, "fitness": fid, "budget": budget, "anomalies": res.anomalies, "final_map_version": res.version_trace[-1],
            "entries": res.ledger}


def _ledger_schema_findings(doc: dict) -> list[str]:
    import jsonschema
    cls = jsonschema.validators.validator_for(_CTX["schema"])
    return [f"{e.json_path}: {e.message}" for e in cls(_CTX["schema"]).iter_errors(doc)][:3]


def _one_seed(args) -> dict:
    r, l_seed, o_seed = args
    fid, truth, fab = _CTX["fid"], _CTX["truth"], _CTX["fabric"]
    land = bl.Landscape(fid, l_seed, masks=_CTX["masks"], truth=truth)
    base = land.train_fitness(fab(0))
    R = bs.run(bs.ARM_RANDOM_SAFE, land, None, o_seed, B_MAX, fab)
    F = bs.run(bs.ARM_MAP_GUIDED, land, _CTX["view"], o_seed, B_MAX, fab)
    O = oa.run_online(land, o_seed, B_MAX, fab, keep_ledger=True)
    X = oa.run_online(land, o_seed, B_MAX, fab, keep_ledger=False, delta_perm=_CTX["perm"], shadow=True)
    # the O arm's obligations, per seed: ledger schema, production replay with the commitments, the online map verified
    ledger_findings = _ledger_schema_findings(_ledger_doc(O, l_seed, o_seed, fid, B_MAX))
    _, replay_findings = oa.replay(O.ledger, O.search_state_trace, O.state_trace)
    online_doc = om.render(O.carto, {"landscape_seed": l_seed, "operator_seed": o_seed, "fitness": fid, "budget": B_MAX}, O.ledger)
    verdict = om.verify(online_doc, O.ledger, truth)
    wrong_o = sum(1 for e in O.ledger for i, k, v in e["decoded"] if tuple(truth["mapping"][i]) != (k, v))
    wrong_x = sum(1 for i, pos in X.carto.decoded.items() if tuple(truth["mapping"][i]) != pos)
    at = lambda trace, b: trace[b - 1]  # noqa: E731
    return {"r": r, "landscape_seed": l_seed, "operator_seed": o_seed, "base_fit": base,
            "arms": {"R": {"at_grid": [at(R.best_trace, b) for b in GRID], "champion_holdout": R.champion_holdout, "column_moves": R.column_moves},
                     "F": {"at_grid": [at(F.best_trace, b) for b in GRID], "champion_holdout": F.champion_holdout, "column_moves": F.column_moves,
                           "end_to_end_at_grid": [oa.end_to_end_frozen(F.best_trace, base, b) for b in GRID]},
                     "O": {"at_grid": [at(O.best_trace, b) for b in GRID], "champion_holdout": O.champion_holdout, "column_moves": O.column_moves,
                           "decoded_at_grid": [O.decoded_trace[b - 1] for b in GRID], "versions_final": O.version_trace[-1],
                           "anomalies": O.anomalies, "wrong_decodes": wrong_o,
                           "evals_to_full_map": next((i + 1 for i, d in enumerate(O.decoded_trace) if d == bc.N), None),
                           "ledger_entries": len(O.ledger), "ledger_schema_findings": ledger_findings, "replay_findings": replay_findings,
                           "online_map_ok": verdict["ok"], "online_map_findings": verdict["findings"][:3],
                           "online_map_sha256": om.canonical_sha256(online_doc), "final_state_sha256": O.state_trace[-1]},
                     "X": {"at_grid": [at(X.best_trace, b) for b in GRID], "champion_holdout": X.champion_holdout, "column_moves": X.column_moves,
                           "decoded_at_grid": [X.decoded_trace[b - 1] for b in GRID], "anomalies": X.anomalies, "wrong_decodes": wrong_x,
                           "decoded_final": len(X.carto.decoded), "shadow_findings": X.shadow_findings[:3], "perm_sha256": X.perm_sha256}}}


def run_fitness(fid: str, seeds: list[tuple[int, int]], workers: int, perm: list[int]) -> list[dict]:
    jobs = [(r, l, o) for r, (l, o) in enumerate(seeds)]
    with Pool(workers, initializer=_init_worker, initargs=(fid, perm)) as pool:
        rows = pool.map(_one_seed, jobs, chunksize=2)
    rows.sort(key=lambda x: x["r"])
    return rows


# ------------------------------------------------------------------ the statistics and the criteria


def deltas_at(rows: list[dict], i: int) -> dict:
    """Paired by landscape at grid index i: Δ1 = O − R, Δ2 = O − end-to-end F, ΔX = X − R, ΔF = F − R."""
    S = len(rows)
    g = lambda arm, key="at_grid": [row["arms"][arm][key][i] for row in rows]  # noqa: E731
    R, F, O, X, Fe = g("R"), g("F"), g("O"), g("X"), g("F", "end_to_end_at_grid")
    return {"R": R, "F": F, "O": O, "X": X, "F_end_to_end": Fe,
            "d1": [O[j] - R[j] for j in range(S)], "d2": [O[j] - Fe[j] for j in range(S)],
            "dX": [X[j] - R[j] for j in range(S)], "dF": [F[j] - R[j] for j in range(S)]}


def _stats(d: list) -> dict:
    p, pos, neg, ties = bg.sign_test_p(d)
    return {"mean": bg.mean(d), "median": bg.median(d), "cohen_d": bg.cohen_d(d), "positives": pos, "negatives": neg, "ties": ties, "sign_test_p": p}


def per_budget(rows: list[dict], ceiling: int) -> list[dict]:
    T = THRESHOLDS
    S = len(rows)
    base_med = bg.median([row["base_fit"] for row in rows])
    out = []
    for i, b in enumerate(GRID):
        d = deltas_at(rows, i)
        n_req, power = bg.required_pairs(d["d1"], T["H5_alpha"], T["H5_power_min"], T["H2_bootstrap_experiments"], T["H5_power_scan_seed"], T["H5_pairs_min"], S)
        o_p95 = bg.percentile(d["O"], T["H1_saturation_percentile"])
        r_med = bg.median(d["R"])
        out.append({"budget": b, "median": {a: bg.median(d[a]) for a in ARMS}, "median_F_end_to_end": bg.median(d["F_end_to_end"]),
                    "delta1_O_minus_R": _stats(d["d1"]), "delta2_O_minus_endtoend_F": _stats(d["d2"]),
                    "deltaX_X_minus_R": _stats(d["dX"]), "deltaF_F_minus_R": _stats(d["dF"]),
                    "decoded_median_O": bg.median([row["arms"]["O"]["decoded_at_grid"][i] for row in rows]),
                    "decoded_median_X": bg.median([row["arms"]["X"]["decoded_at_grid"][i] for row in rows]),
                    "O_p95": o_p95, "random_median": r_med, "base_median": base_med,
                    "H1": o_p95 < ceiling and r_med > base_med,
                    "required_pairs_N": n_req, "power_at_N": power, "search_evaluations": (n_req * 3 * b) if n_req else None})
    return out


def evaluate(fid: str, rows: list[dict]) -> dict:
    T = THRESHOLDS
    ceiling = bl.CEILING[fid]
    S = len(rows)
    table = per_budget(rows, ceiling)
    curves = {a: [t["median"][a] for t in table] for a in ARMS}
    curves["F_end_to_end"] = [t["median_F_end_to_end"] for t in table]
    eligible = [t for t in table if t["H1"] and t["search_evaluations"] is not None]
    common = {"fitness": fid, "ceiling": ceiling, "seeds": S, "grid": list(GRID), "curves_median": curves, "per_budget": table}
    if not eligible:
        return {**common, "b_star": None, "criteria": {"budget_rule": {"pass": False, "note": "no grid budget has both H1 and a finite N(B) (N(B) needs S >= 8 and power 0.9)"}},
                "pass": False, "H9_claim_condition": None}
    best = min(eligible, key=lambda t: (t["search_evaluations"], t["budget"]))
    b_star = best["budget"]
    bi = GRID.index(b_star)
    d = deltas_at(rows, bi)
    n_req = best["required_pairs_N"]
    cost = best["search_evaluations"]
    crit: dict[str, dict] = {}
    crit["budget_rule"] = {"b_star": b_star, "search_evaluations": cost, "rule": T["budget_rule"],
                           "candidates": [{"budget": t["budget"], "N": t["required_pairs_N"], "cost": t["search_evaluations"], "H1": t["H1"]} for t in table], "pass": True}
    crit["H1"] = {"O_p95": best["O_p95"], "ceiling": ceiling, "random_median": best["random_median"], "base_median": best["base_median"], "pass": best["H1"]}
    var1 = statistics.pvariance(d["d1"]) if S > 1 else 0.0
    both = [t["budget"] for t in table if t["delta1_O_minus_R"]["positives"] > 0 and t["delta1_O_minus_R"]["negatives"] > 0]
    mean_sign_change = any(table[k]["delta1_O_minus_R"]["mean"] < 0 for k in range(len(table))) and any(table[k]["delta1_O_minus_R"]["mean"] > 0 for k in range(len(table)))
    x_nonreject = 1.0 - bg.bootstrap_reject_rate(d["dX"], n_req, T["H5_alpha"], T["H2_bootstrap_experiments"], T["H2_control_bootstrap_seed"])
    crit["H2"] = {"var_delta1": var1, "budgets_with_both_signs": both, "mean_delta1_changes_sign_across_budgets (reported)": mean_sign_change,
                  "signs_by_budget": [[t["budget"], t["delta1_O_minus_R"]["positives"], t["delta1_O_minus_R"]["negatives"], t["delta1_O_minus_R"]["ties"]] for t in table],
                  "N_used": n_req, "control_X_nonreject_rate": x_nonreject,
                  "pass": var1 > 0 and bool(both) and x_nonreject >= T["H2_null_nonreject_min"]}
    s1, sX = _stats(d["d1"]), _stats(d["dX"])
    crit["H3"] = {"mean_deltaX": sX["mean"], "mean_delta1": s1["mean"], "fraction": (sX["mean"] / s1["mean"]) if s1["mean"] > 0 else None,
                  "sign_test_p_X_vs_R": sX["sign_test_p"], "decoded_median_X_at_b_star": best["decoded_median_X"], "decoded_median_O_at_b_star": best["decoded_median_O"],
                  "pass": s1["mean"] > 0 and sX["mean"] <= T["H3_x_fraction_max"] * s1["mean"] and sX["sign_test_p"] > T["H3_alpha"]}
    s2 = _stats(d["d2"])
    o_med, f_med = bg.median(d["O"]), bg.median(d["F"])
    crit["H4"] = {"O_median": o_med, "F_median": f_med, "O_over_F": (o_med / f_med) if f_med > 0 else None, "delta2": s2,
                  "pass": f_med > 0 and o_med >= T["H4_o_over_f_median_min"] * f_med and s2["sign_test_p"] <= T["H4_alpha"]}
    crit["H5"] = {"cohen_d": s1["cohen_d"], "mean_delta1": s1["mean"], "sd_delta1": statistics.stdev(d["d1"]) if S > 1 else 0.0,
                  "sign_test_p_full_S": s1["sign_test_p"], "positives": s1["positives"], "negatives": s1["negatives"], "ties": s1["ties"],
                  "required_pairs_N": n_req, "power_at_N": best["power_at_N"], "search_evaluations": cost,
                  "note": "a SEARCH-EVALUATION cap: holdout evaluations, baselines and the session record totals are accounted by the plan",
                  "pass": s1["cohen_d"] >= T["H5_cohen_d_min"] and cost <= T["H5_search_evaluation_cap"]}
    crit["H6"] = {"seeds": S, "var_delta1": var1, "pairs_min": T["H5_pairs_min"], "N": n_req, "exclusions": "see report.seeds",
                  "pass": S >= T["H6_seeds_min"] and var1 > 0 and n_req >= T["H5_pairs_min"]}
    wrong = sum(row["arms"]["O"]["wrong_decodes"] for row in rows)
    anomalies = sum(row["arms"]["O"]["anomalies"] for row in rows)
    complete = sum(1 for row in rows if row["arms"]["O"]["evals_to_full_map"])
    crit["H7"] = {"wrong_decodes_total": wrong, "anomalies_total": anomalies, "decoded_median_at_b_star": best["decoded_median_O"],
                  "full_map_within_b_max": complete, "evals_to_full_map_median": bg.median([row["arms"]["O"]["evals_to_full_map"] or B_MAX + 1 for row in rows]),
                  "online_map_verified_all": all(row["arms"]["O"]["online_map_ok"] for row in rows),
                  "pass": wrong == 0 and anomalies == 0 and best["decoded_median_O"] >= T["H7_decoded_median_min"] and all(row["arms"]["O"]["online_map_ok"] for row in rows)}
    replay_bad = [row["r"] for row in rows if row["arms"]["O"]["replay_findings"]]
    schema_bad = [row["r"] for row in rows if row["arms"]["O"]["ledger_schema_findings"]]
    shadow_bad = [row["r"] for row in rows if row["arms"]["X"]["shadow_findings"]]
    crit["H8"] = {"seeds_with_replay_findings": replay_bad[:10], "seeds_with_ledger_schema_findings": schema_bad[:10],
                  "seeds_with_X_shadow_findings (a defect, not a result)": shadow_bad[:10],
                  "pass": not replay_bad and not schema_bad and not shadow_bad}
    from_b = [t for t in table if t["budget"] >= b_star]
    crit["H9"] = {"alpha": T["H9_alpha"], "delta2_by_budget_from_b_star": [[t["budget"], t["delta2_O_minus_endtoend_F"]["sign_test_p"], t["delta2_O_minus_endtoend_F"]["mean"], t["delta2_O_minus_endtoend_F"]["median"]] for t in from_b],
                  "claim_condition": "not a pass criterion: if it fails the preregistration's final claim is primary 1 alone (the resolution rule)",
                  "pass": all(t["delta2_O_minus_endtoend_F"]["sign_test_p"] <= T["H9_alpha"] for t in from_b)}
    holdout = {a: bg.median([row["arms"][a]["champion_holdout"] for row in rows]) for a in ARMS}
    gate_pass = all(crit[k]["pass"] for k in ("budget_rule", "H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8"))
    return {**common, "b_star": b_star, "at_b_star_median": {a: bg.median(d[a]) for a in ARMS}, "at_b_star_median_F_end_to_end": bg.median(d["F_end_to_end"]),
            "champion_holdout_median": holdout, "criteria": crit, "pass": gate_pass, "H9_claim_condition": crit["H9"]["pass"]}


# ------------------------------------------------------------------ pins, seeds, main


def git_head() -> str | None:
    p = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def git_dirty() -> bool:
    p = subprocess.run(["git", "-C", str(REPO_ROOT), "status", "--porcelain"], capture_output=True, text=True)
    return bool(p.stdout.strip())


def architecture_pin() -> dict:
    p = subprocess.run(["git", "-C", str(REPO_ROOT), "log", "-n", "1", "--format=%H", "--", "docs/b3_architecture.md"], capture_output=True, text=True)
    return {"path": "docs/b3_architecture.md", "sha256": sha256_bytes(ARCHITECTURE.read_bytes()), "last_commit": p.stdout.strip() or None}


def gate_exclusion() -> tuple[set[int], dict]:
    """Every archived seed set, explicitly: B2's frozen sets (its two gate runs and the B3 simulation),
    B2's nine session pairs and master, B2Q's pair and master."""
    excl, where = bp.frozen_seed_exclusion()
    m = json.loads((REPO_ROOT / "manifests/b2_manifest.json").read_text())
    b2_pairs = [tuple(x) for x in m["seeds"]["pairs"]]
    b2_master = m["seeds"]["master_seed"]
    q = json.loads((REPO_ROOT / "evidence/b2/b2q_plan.json").read_text())["seed_derivation"]
    b2q_pairs = [tuple(x) for x in q["pairs"]]
    where["manifests/b2_manifest.json seeds (B2 session pairs)"] = {"master_seed": b2_master, "count": len(b2_pairs), "values": len({s for p in b2_pairs for s in p} | {b2_master})}
    where["evidence/b2/b2q_plan.json seed_derivation (B2Q pairs)"] = {"master_seed": q["master_seed"], "count": len(b2q_pairs), "values": len({s for p in b2q_pairs for s in p} | {q["master_seed"]})}
    excl = set(excl) | {s for p in b2_pairs for s in p} | {b2_master} | {s for p in b2q_pairs for s in p} | {q["master_seed"]}
    return excl, where


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", type=int, default=SEEDS_DEFAULT)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--fitness", default="F1,F2")
    ap.add_argument("--out", default="evidence/b3/gate")
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    out = REPO_ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    head = git_head()
    dirty = git_dirty()
    master = bs.master_seed(GATE_LABEL, head or "no-commit")
    excl, sources = gate_exclusion()
    seeds = bs.pair_seeds(master, a.seeds, exclude=frozenset(excl))
    seed_x = cx.seed_x(bp.INSTRUMENT_COMMIT)
    attempts: list = []
    perm = cx.derangement(seed_x, log=attempts)
    started = time.time()
    results = {}
    for fid in [f for f in a.fitness.split(",") if f]:
        t0 = time.time()
        rows = run_fitness(fid, seeds, a.workers, perm)
        (out / f"raw_{fid}.json").write_text(json.dumps({"fitness": fid, "grid": list(GRID), "rows": rows}, separators=(",", ":")))
        results[fid] = evaluate(fid, rows)
        results[fid]["wall_s"] = round(time.time() - t0, 1)
        print(f"[{fid}] B*={results[fid].get('b_star')} pass={results[fid]['pass']} H9={results[fid].get('H9_claim_condition')} "
              f"{ {k: v['pass'] for k, v in results[fid]['criteria'].items()} } {results[fid]['wall_s']}s", flush=True)
    sm = bmaps.load_self_map()
    report = {"schema": "b3_gate_report", "schema_version": "1.0.0", "label": a.label,
              "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "head_at_run": head, "worktree_dirty_at_start": dirty, "architecture": architecture_pin(), "thresholds": THRESHOLDS,
              "engine": {"version": bs.ENGINE_VERSION, "mu": bs.MU, "lambda": bs.LAMBDA, "kmax": bs.KMAX}, "carto_version": carto_mod.CARTO_VERSION,
              "control_x": {"instrument_commit": bp.INSTRUMENT_COMMIT, "seed_x": seed_x, "seed_rule": "b2_search.master_seed('b3-gate-x', instrument commit)",
                            "prng": "b1_carto.Rng(seed_x); Fisher-Yates i=383..1, j=rng.uniform(i+1); rejection from the identity on the continuing stream",
                            "attempts": len(attempts), "fixed_points_per_attempt": attempts, "permutation_sha256": cx.permutation_sha256(perm)},
              "seeds": {"label": GATE_LABEL, "master_seed": master, "derivation": f"first 4 bytes of sha256('{GATE_LABEL}|' + HEAD), pairs from one Rng stream, every excluded seed skipped",
                        "count": a.seeds, "excluded_fixed": sorted(bs.EXCLUDED_SEEDS), "excluded_sources": sources, "excluded_values_total": len(excl | set(bs.EXCLUDED_SEEDS))},
              "map": {"path": str(bmaps.SELF_MAP.relative_to(REPO_ROOT)), "sha256": bmaps.sha256_of(sm)},
              "gate_fitness": "F1", "results": results, "wall_s": round(time.time() - started, 1)}
    (out / "gate_report.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(out / "gate_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

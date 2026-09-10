#!/usr/bin/env python3
"""B3 — the three-arm host simulation and its report (docs/b3_architecture.md §5).

    b3_sim.py [--seeds 200] [--workers N] [--fitness F1,F2] [--out evidence/b3/sim]

Per landscape seed and fitness: R (random-safe), F (frozen B1 map), O (online-updating
map from specimens), each to the largest grid budget. Reported per grid budget:
  * search accounting   — best-so-far at B evaluations of each arm's own search;
  * end-to-end accounting — best-so-far at total budget T where the frozen arm is charged
    B1's 333 mapping probes first (its search value at T is its trace at T - 333, or the
    base fitness when T <= 333); R and O are charged nothing (O's map costs no probe).
Plus the online map's growth (decoded addresses, map versions, anomalies, wrong decodes
against the truth — a host-only audit the board never sees).
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_model as bm  # noqa: E402
import b2_gate as bg  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_online as b3  # noqa: E402

LABEL = "b3-sim"
GRID = (100, 200, 300, 400, 600, 800, 1000, 1500, 2000, 3000)
B_MAX = GRID[-1]
_CTX: dict = {}


def _init(fid: str):
    truth = bm.truth_mapping()
    _CTX.update(truth=truth, masks=bl.universe_mask(truth), fabric=bs.ModelFabric(truth), fid=fid,
                view=bmaps.MapView(bmaps.load_self_map(), bl.train_vectors()))


def _one(args) -> dict:
    r, l_seed, o_seed = args
    land = bl.Landscape(_CTX["fid"], l_seed, masks=_CTX["masks"], truth=_CTX["truth"])
    fab = _CTX["fabric"]
    base = land.train_fitness(fab(0))
    R = bs.run(bs.ARM_RANDOM_SAFE, land, None, o_seed, B_MAX, fab)
    F = bs.run(bs.ARM_MAP_GUIDED, land, _CTX["view"], o_seed, B_MAX, fab)
    O = b3.run_online(land, o_seed, B_MAX, fab, keep_ledger=True)
    wrong = sum(1 for e in O.ledger for i, k, v in e["decoded"] if _CTX["truth"]["mapping"][i] != (k, v))
    single = sum(1 for e in O.ledger if len(e["intervention"]) == 1)
    def at(trace, b):
        return trace[b - 1]
    def f_end_to_end(t):
        s = t - b3.B1_MAP_COST
        return base if s <= 0 else at(F.best_trace, s)
    return {"r": r, "landscape_seed": l_seed, "operator_seed": o_seed, "base_fit": base,
            "search": {"R": [at(R.best_trace, b) for b in GRID], "F": [at(F.best_trace, b) for b in GRID], "O": [at(O.best_trace, b) for b in GRID]},
            "end_to_end": {"R": [at(R.best_trace, b) for b in GRID], "F": [f_end_to_end(b) for b in GRID], "O": [at(O.best_trace, b) for b in GRID]},
            "online": {"decoded_at_grid": [O.decoded_trace[b - 1] for b in GRID], "versions_final": O.version_trace[-1], "anomalies": O.anomalies,
                       "wrong_decodes": wrong, "single_bit_specimens": single, "column_moves": O.column_moves,
                       "evals_to_full_map": next((i + 1 for i, d in enumerate(O.decoded_trace) if d == bl.bc.N), None)},
            "holdout": {"R": R.champion_holdout, "F": F.champion_holdout, "O": O.champion_holdout}}


def summarise(fid: str, rows: list[dict]) -> dict:
    S = len(rows)
    out = {"fitness": fid, "ceiling": bl.CEILING[fid], "seeds": S, "grid": list(GRID), "accounting": {}}
    for acc in ("search", "end_to_end"):
        med = {arm: [statistics.median(row[acc][arm][i] for row in rows) for i in range(len(GRID))] for arm in ("R", "F", "O")}
        stats = {}
        for pair in (("O", "R"), ("F", "R"), ("O", "F")):
            a, b = pair
            per_b = []
            for i in range(len(GRID)):
                d = [row[acc][a][i] - row[acc][b][i] for row in rows]
                p, pos, neg, ties = bg.sign_test_p(d)
                per_b.append({"budget": GRID[i], "mean_delta": bg.mean(d), "cohen_d": bg.cohen_d(d), "positives": pos, "negatives": neg, "ties": ties, "sign_test_p": p})
            stats[f"{a}-{b}"] = per_b
        out["accounting"][acc] = {"median": med, "paired": stats}
    out["online_map"] = {"decoded_median_at_grid": [statistics.median(row["online"]["decoded_at_grid"][i] for row in rows) for i in range(len(GRID))],
                         "evals_to_full_map_median": statistics.median([row["online"]["evals_to_full_map"] or B_MAX + 1 for row in rows]),
                         "full_map_within_budget": sum(1 for row in rows if row["online"]["evals_to_full_map"]),
                         "wrong_decodes_total": sum(row["online"]["wrong_decodes"] for row in rows),
                         "anomalies_total": sum(row["online"]["anomalies"] for row in rows),
                         "versions_final_median": statistics.median(row["online"]["versions_final"] for row in rows)}
    out["holdout_median"] = {arm: statistics.median(row["holdout"][arm] for row in rows) for arm in ("R", "F", "O")}
    return out


def git_head() -> str | None:
    p = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=200)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--fitness", default="F1,F2")
    ap.add_argument("--out", default="evidence/b3/sim")
    ap.add_argument("--master-seed", type=int, default=None, help="reuse a stored run's master seed instead of deriving one from HEAD (identity re-runs)")
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    out = REPO_ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    head = git_head()
    dirty = bool(subprocess.run(["git", "-C", str(REPO_ROOT), "status", "--porcelain"], capture_output=True, text=True).stdout.strip())
    master = a.master_seed if a.master_seed is not None else bs.master_seed(LABEL, head or "no-commit")
    seeds = bs.pair_seeds(master, a.seeds)
    report = {"schema": "b3_sim_report", "schema_version": "1.0.0", "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "label": a.label, "carto_version": b3.CARTO_VERSION,
              "head_at_run": head, "worktree_dirty_at_start": dirty,
              "seeds": {"label": LABEL, "master_seed": master, "count": a.seeds, "reused": a.master_seed is not None},
              "accounting_note": "an EVALUATION-COUNT model: F is charged B1's 333 probes; baselines, setup, qualification, audits and compute time are not counted",
              "b1_map_cost": b3.B1_MAP_COST, "engine": {"version": bs.ENGINE_VERSION, "mu": bs.MU, "lambda": bs.LAMBDA, "kmax": bs.KMAX},
              "map": {"path": str(bmaps.SELF_MAP.relative_to(REPO_ROOT)), "sha256": bmaps.sha256_of(bmaps.load_self_map())}, "results": {}}
    for fid in [f for f in a.fitness.split(",") if f]:
        t0 = time.time()
        jobs = [(r, l, o) for r, (l, o) in enumerate(seeds)]
        with Pool(a.workers, initializer=_init, initargs=(fid,)) as pool:
            rows = pool.map(_one, jobs, chunksize=4)
        rows.sort(key=lambda x: x["r"])
        (out / f"raw_{fid}.json").write_text(json.dumps({"fitness": fid, "grid": list(GRID), "rows": rows}, separators=(",", ":")))
        report["results"][fid] = summarise(fid, rows)
        report["results"][fid]["wall_s"] = round(time.time() - t0, 1)
        s = report["results"][fid]
        print(f"[{fid}] search medians R {s['accounting']['search']['median']['R']} F {s['accounting']['search']['median']['F']} O {s['accounting']['search']['median']['O']}")
        print(f"[{fid}] end-to-end F {s['accounting']['end_to_end']['median']['F']}; online decoded {s['online_map']['decoded_median_at_grid']}, "
              f"full map median at {s['online_map']['evals_to_full_map_median']}, wrong {s['online_map']['wrong_decodes_total']}, anomalies {s['online_map']['anomalies_total']}", flush=True)
    (out / "sim_report.json").write_text(json.dumps(report, indent=1, sort_keys=True))
    print(out / "sim_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

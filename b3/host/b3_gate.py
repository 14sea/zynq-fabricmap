#!/usr/bin/env python3
"""B3 lifecycle 2 — the B3 discriminability gate (docs/b3_architecture.md v0.3 §9), host simulation
before any board time.

    b3_gate.py [--seeds 200] [--workers N] [--fitness F1,F2] [--out evidence/b3/gate_2]

For every fitness (F1 is the gate's; F2 is reported for information), S landscape seeds under the
label `b3-gate-2` (every archived seed set excluded explicitly: B2's gate runs, the B3 simulation,
B2's nine session pairs and its B2Q pair, and lifecycle 1's gate run 1 under `b3-gate` and its nine
`b3-session` pairs — pilot / design evidence, preregistration §8b), the four arms R / F / O / X to the
largest grid budget, with the O arm's ledger replayed and its online map verified per seed, and X's
shadow isomorphism checked per specimen. Then the per-budget statistics, N(B) by B2's bootstrap power
scan (`b2_gate.required_pairs` by import, seed 1 + N), the frozen budget rule min N(B) × 3 × B, the
criteria H1–H8 at B*, and H9 as a pure diagnostic: the sign test on Δ2 at every budget ≥ B* with, next
to it, N₂(B) by the same bootstrap rule and Δ2's power at the gate's N — reported, deciding nothing.
Writes gate_report.json (the criteria with the numbers, the diagnostic, the pins: this architecture
document's sha256 and last commit, the control-X seed and permutation digest, the seeds' derivation and
every exclusion source) and raw_<fid>.json (every per-seed value the statistics used). A criterion
that fails is reported, never tuned here. Lifecycle 1's `evidence/b3/gate/` is never overwritten:
the tool refuses that output directory — and any existing --out: the outputs are built outside the
repository, staged beside --out after the end-of-run check and published by one directory rename.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import statistics
import shutil
import subprocess
import sys
import tempfile
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
LIFECYCLE = 2
GATE_LABEL = "b3-gate-2"
OUT_DEFAULT = "evidence/b3/gate_2"
REPORT_SCHEMA_VERSION = "2.0.0"
HEX40 = re.compile(r"^[0-9a-f]{40}$")


class Refusal(ValueError):
    """A named refusal of an input, a shape, a path or an I/O condition — the CLIs print it as
    `REFUSED: ...` and exit 2, writing nothing. Any other exception is an INTERNAL ERROR (a traceback)."""


# lifecycle 1 (branch b3-lifecycle-1, tag b3-lifecycle-1-stopped-2026-09-17): historical evidence, excluded, never overwritten
LIFECYCLE1_GATE_LABEL = "b3-gate"
LIFECYCLE1_GATE_DIR = REPO_ROOT / "evidence/b3/gate"
LIFECYCLE1_SESSION_LABEL = "b3-session"
LIFECYCLE1_TRIAL_DIR = REPO_ROOT / "evidence/b3/plan_trial_2026_09_17"
SEEDS_DEFAULT = 200
GRID = (100, 200, 300, 400, 600, 800, 1000, 1500, 2000, 3000)
B_MAX = GRID[-1]
ARMS = ("R", "F", "O", "X")
ARM_TEXT = {"R": "random-safe (no map)", "F": "frozen B1 self-map", "O": "online map from specimens", "X": "control: scrambled specimens"}
THRESHOLDS = {
    "rules_version": "architecture v0.3 §9",
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
    "H9_role": "diagnostic (architecture v0.3 §9): the sign test on delta2 at every budget >= B*, with N2(B) by the same bootstrap "
               "rule (required_pairs, seed 1 + N) and delta2's power at the gate's N (bootstrap_reject_rate, seed 1 + N); reported, decides nothing",
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
        # required_pairs returns (N, power at N) when some N in [8, S] reaches the power, else (None, the power at the
        # scan's last N = S): that second value is NOT "the power at N" — it is reported under its own name
        n_req, p1 = bg.required_pairs(d["d1"], T["H5_alpha"], T["H5_power_min"], T["H2_bootstrap_experiments"], T["H5_power_scan_seed"], T["H5_pairs_min"], S)
        # H9 diagnostic (v0.3): the same bootstrap rule applied to delta2 — N2(B), and delta2's power at the gate's N(B)
        n_req2, p2 = bg.required_pairs(d["d2"], T["H9_alpha"], T["H5_power_min"], T["H2_bootstrap_experiments"], T["H5_power_scan_seed"], T["H5_pairs_min"], S)
        power2_at_n = bg.bootstrap_reject_rate(d["d2"], n_req, T["H9_alpha"], T["H2_bootstrap_experiments"], T["H5_power_scan_seed"] + n_req) if n_req else None
        scan_max = S if S >= T["H5_pairs_min"] else None                      # the scan's last N (none when S < 8: nothing was scanned)
        o_p95 = bg.percentile(d["O"], T["H1_saturation_percentile"])
        r_med = bg.median(d["R"])
        out.append({"budget": b, "median": {a: bg.median(d[a]) for a in ARMS}, "median_F_end_to_end": bg.median(d["F_end_to_end"]),
                    "delta1_O_minus_R": _stats(d["d1"]), "delta2_O_minus_endtoend_F": _stats(d["d2"]),
                    "deltaX_X_minus_R": _stats(d["dX"]), "deltaF_F_minus_R": _stats(d["dF"]),
                    "decoded_median_O": bg.median([row["arms"]["O"]["decoded_at_grid"][i] for row in rows]),
                    "decoded_median_X": bg.median([row["arms"]["X"]["decoded_at_grid"][i] for row in rows]),
                    "O_p95": o_p95, "random_median": r_med, "base_median": base_med,
                    "H1": o_p95 < ceiling and r_med > base_med,
                    "required_pairs_N": n_req, "power_at_N": p1 if n_req else None, "search_evaluations": (n_req * 3 * b) if n_req else None,
                    "scan_max_N": scan_max,
                    "power_delta1_at_scan_max_N": None if n_req else (p1 if scan_max else None),
                    "required_pairs_N2": n_req2, "power_at_N2": p2 if n_req2 else None,
                    "power_delta2_at_scan_max_N": None if n_req2 else (p2 if scan_max else None),
                    "power_delta2_at_gate_N": power2_at_n})
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
                "pass": False, "diagnostics": {"H9": None}}
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
    # H9 (v0.3): a diagnostic, not a criterion — no "pass", nothing downstream reads it as a condition
    from_b = [t for t in table if t["budget"] >= b_star]
    h9 = {"alpha": T["H9_alpha"], "role": T["H9_role"], "gate_N": n_req, "power_min": T["H5_power_min"],
          "delta2_by_budget_from_b_star": [{"budget": t["budget"], **t["delta2_O_minus_endtoend_F"],
                                            "required_pairs_N2": t["required_pairs_N2"], "power_at_N2": t["power_at_N2"],
                                            "scan_max_N": t["scan_max_N"], "power_delta2_at_scan_max_N": t["power_delta2_at_scan_max_N"],
                                            "power_delta2_at_gate_N": t["power_delta2_at_gate_N"]} for t in from_b]}
    holdout = {a: bg.median([row["arms"][a]["champion_holdout"] for row in rows]) for a in ARMS}
    gate_pass = all(crit[k]["pass"] for k in ("budget_rule", "H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8"))
    return {**common, "b_star": b_star, "at_b_star_median": {a: bg.median(d[a]) for a in ARMS}, "at_b_star_median_F_end_to_end": bg.median(d["F_end_to_end"]),
            "champion_holdout_median": holdout, "criteria": crit, "pass": gate_pass, "diagnostics": {"H9": h9}}


# ------------------------------------------------------------------ pins, seeds, main


def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True)


def git_head() -> str | None:
    p = _git("rev-parse", "HEAD")
    return p.stdout.decode().strip() if p.returncode == 0 else None


def git_dirty() -> bool:
    return bool(_git("status", "--porcelain").stdout.strip())


def commit_exists(head) -> bool:
    """True iff `head` is a 40-hex id of a commit object in this repository."""
    return isinstance(head, str) and bool(HEX40.match(head)) and _git("cat-file", "-e", f"{head}^{{commit}}").returncode == 0


def git_show_bytes(head: str, rel: str) -> bytes | None:
    """The bytes of `rel` at commit `head`, or None when the commit does not carry it."""
    p = _git("show", f"{head}:{rel}")
    return p.stdout if p.returncode == 0 else None


def architecture_pin(head: str) -> dict:
    """The architecture document as commit `head` carries it: its bytes' sha256 and the last commit that
    touched it as of `head` (deterministic in `head`; None when the commit lacks the file)."""
    b = git_show_bytes(head, "docs/b3_architecture.md")
    last = _git("log", "-n", "1", "--format=%H", head, "--", "docs/b3_architecture.md").stdout.decode().strip()
    return {"path": "docs/b3_architecture.md", "sha256": sha256_bytes(b) if b is not None else None, "last_commit": last or None}


def lifecycle1_exclusion() -> tuple[set[int], dict]:
    """What lifecycle 1's gate excluded: B2's frozen sets (its two gate runs and the B3 simulation),
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


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def gate_exclusion() -> tuple[set[int], dict]:
    """Every archived seed set, explicitly: lifecycle 1's exclusion (B2's frozen sets, B2's session
    pairs, B2Q's pair), plus lifecycle 1's own two sets — gate run 1's 200 pairs and master (re-derived
    from its report's master and count under lifecycle 1's exclusion and checked against its raw rows)
    and the nine trial session pairs and master (re-derived from the trial plan's master under gate run
    1's exclusion and checked against the trial prediction) — pilot / design evidence, never a draw
    (preregistration §8b, architecture v0.3 H6)."""
    excl, where = lifecycle1_exclusion()
    g1 = json.loads((LIFECYCLE1_GATE_DIR / "gate_report.json").read_text())
    if g1["seeds"]["label"] != LIFECYCLE1_GATE_LABEL:
        raise ValueError(f"lifecycle 1's gate report carries the label {g1['seeds']['label']!r}, not {LIFECYCLE1_GATE_LABEL!r}")
    g1_seeds = bs.pair_seeds(g1["seeds"]["master_seed"], g1["seeds"]["count"], exclude=frozenset(excl))
    raw = json.loads((LIFECYCLE1_GATE_DIR / f"raw_{g1['gate_fitness']}.json").read_text())["rows"]
    if [(row["landscape_seed"], row["operator_seed"]) for row in raw] != [tuple(x) for x in g1_seeds]:
        raise ValueError("lifecycle 1's gate rows do not carry the seeds its master and count re-derive")
    g1_flat = {s for p in g1_seeds for s in p} | {g1["seeds"]["master_seed"]}
    where[_rel(LIFECYCLE1_GATE_DIR / "gate_report.json") + " (lifecycle 1 gate run 1, pilot)"] = {"master_seed": g1["seeds"]["master_seed"], "count": g1["seeds"]["count"], "values": len(g1_flat)}
    excl = excl | g1_flat
    t_plan = json.loads((LIFECYCLE1_TRIAL_DIR / "plan.json").read_text())["seed_derivation"]
    t_pred = json.loads((LIFECYCLE1_TRIAL_DIR / "prediction.json").read_text())
    if t_plan["label"] != LIFECYCLE1_SESSION_LABEL:
        raise ValueError(f"lifecycle 1's trial plan carries the label {t_plan['label']!r}, not {LIFECYCLE1_SESSION_LABEL!r}")
    t_pairs = [(p["landscape_seed"], p["operator_seed"]) for p in t_pred["pairs"]]
    if bs.pair_seeds(t_plan["master_seed"], len(t_pairs), exclude=frozenset(excl)) != t_pairs:
        raise ValueError("lifecycle 1's trial pairs are not the ones its master re-derives under gate run 1's exclusion")
    t_flat = {s for p in t_pairs for s in p} | {t_plan["master_seed"]}
    where[_rel(LIFECYCLE1_TRIAL_DIR / "prediction.json") + " (lifecycle 1 trial session pairs, pilot)"] = {"master_seed": t_plan["master_seed"], "count": len(t_pairs), "values": len(t_flat)}
    return excl | t_flat, where


def control_x_draw() -> tuple[int, list[int], list]:
    """seed_X and the derangement pi (architecture §9), with the attempt log."""
    seed_x = cx.seed_x(bp.INSTRUMENT_COMMIT)
    attempts: list = []
    perm = cx.derangement(seed_x, log=attempts)
    return seed_x, perm, attempts


def provenance_blocks(head: str, count: int) -> dict:
    """Every deterministic block of a report, computed afresh from `head`, the current inputs (the
    thresholds, the engine, the cartographer, the self-map, the exclusion sources, control X) and the
    seed count. The run writes them; the validator recomputes them and requires equality; the run
    recomputes them at its end and requires that nothing moved."""
    excl, sources = gate_exclusion()
    seed_x, perm, attempts = control_x_draw()
    sm = bmaps.load_self_map()
    return {"schema": "b3_gate_report", "schema_version": REPORT_SCHEMA_VERSION, "lifecycle": LIFECYCLE,
            "architecture": architecture_pin(head), "thresholds": copy.deepcopy(THRESHOLDS),
            "engine": {"version": bs.ENGINE_VERSION, "mu": bs.MU, "lambda": bs.LAMBDA, "kmax": bs.KMAX}, "carto_version": carto_mod.CARTO_VERSION,
            "control_x": {"instrument_commit": bp.INSTRUMENT_COMMIT, "seed_x": seed_x, "seed_rule": "b2_search.master_seed('b3-gate-x', instrument commit)",
                          "prng": "b1_carto.Rng(seed_x); Fisher-Yates i=383..1, j=rng.uniform(i+1); rejection from the identity on the continuing stream",
                          "attempts": len(attempts), "fixed_points_per_attempt": attempts, "permutation_sha256": cx.permutation_sha256(perm)},
            "seeds": {"label": GATE_LABEL, "master_seed": bs.master_seed(GATE_LABEL, head),
                      "derivation": f"first 4 bytes of sha256('{GATE_LABEL}|' + HEAD), pairs from one Rng stream, every excluded seed skipped",
                      "count": count, "excluded_fixed": sorted(bs.EXCLUDED_SEEDS), "excluded_sources": sources, "excluded_values_total": len(excl | set(bs.EXCLUDED_SEEDS))},
            "map": {"path": str(bmaps.SELF_MAP.relative_to(REPO_ROOT)), "sha256": bmaps.sha256_of(sm)},
            "gate_fitness": "F1"}


PROVENANCE_KEYS = ("schema", "schema_version", "lifecycle", "architecture", "thresholds", "engine", "carto_version", "control_x", "seeds", "map", "gate_fitness")


def build_report(label: str, head: str, dirty: bool, count: int, results: dict, raw_files: dict, wall_s: float, provenance: dict | None = None) -> dict:
    """The report document: the provenance blocks (recomputed unless given), HEAD and the dirty flag at
    the start, every result, every raw file's digest. Built here so a test fixture and the run write
    the same shape."""
    prov = provenance if provenance is not None else provenance_blocks(head, count)
    return {**copy.deepcopy(prov), "label": label, "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "head_at_run": head, "worktree_dirty_at_start": dirty, "raw_files": raw_files, "results": results, "wall_s": wall_s}


def raw_bytes(fid: str, rows: list[dict]) -> bytes:
    return json.dumps({"fitness": fid, "grid": list(GRID), "rows": rows}, separators=(",", ":")).encode()


def refuse_lifecycle1_path(out: Path) -> None:
    """Lifecycle 1's directories are historical evidence: neither they nor anything under them is written."""
    r = out.resolve()
    for d in (LIFECYCLE1_GATE_DIR, LIFECYCLE1_TRIAL_DIR):
        if r == d.resolve() or r.is_relative_to(d.resolve()):
            raise Refusal(f"{_rel(out)} is lifecycle 1's {_rel(d)} or under it — never overwritten (write to {OUT_DEFAULT})")


def io_refusal(what: str):
    """An expected OSError on a read / write / mkdir becomes a named Refusal (never a traceback)."""
    import contextlib

    @contextlib.contextmanager
    def cm():
        try:
            yield
        except OSError as e:
            raise Refusal(f"{what} ({e.__class__.__name__}: {e})") from None
    return cm()


def refuse_bad_out(out: Path, kind: str = "directory") -> None:
    """--out must be creatable as a `kind` ("directory" or "file"): an existing path of the other kind,
    or a nearest existing ancestor that is not a directory, is a named Refusal before any work."""
    if out.exists():
        if kind == "directory" and not out.is_dir():
            raise Refusal(f"--out {_rel(out)} exists and is not a directory")
        if kind == "file" and out.is_dir():
            raise Refusal(f"--out {_rel(out)} is a directory")
        return
    for anc in out.parents:
        if anc.exists():
            if not anc.is_dir():
                raise Refusal(f"--out {_rel(out)}: {_rel(anc)} exists and is not a directory")
            return


def tree_state() -> tuple[str, bool]:
    """HEAD and the dirty flag, refused unless a clean tree at an existing commit."""
    head, dirty = git_head(), git_dirty()
    if not commit_exists(head):
        raise Refusal("no HEAD commit: the gate runs only on a committed tree (the report pins HEAD)")
    if dirty:
        raise Refusal("the working tree is dirty: the gate runs only on a clean committed tree (the report pins HEAD and the architecture bytes)")
    return head, dirty


def run(a) -> Path:
    out = REPO_ROOT / a.out
    refuse_lifecycle1_path(out)
    head, dirty = tree_state()
    fitnesses = [f for f in a.fitness.split(",") if f]
    if "F1" not in fitnesses:
        raise Refusal("the gate fitness F1 must be among --fitness")
    refuse_no_clobber(out)
    prov0 = provenance_blocks(head, a.seeds)
    if prov0["architecture"]["sha256"] is None or prov0["architecture"]["sha256"] != sha256_bytes(ARCHITECTURE.read_bytes()):
        raise Refusal("docs/b3_architecture.md in the working tree is not the one HEAD carries")
    master = prov0["seeds"]["master_seed"]
    excl, _ = gate_exclusion()
    seeds = bs.pair_seeds(master, a.seeds, exclude=frozenset(excl))
    _, perm, _ = control_x_draw()
    tmp = Path(tempfile.mkdtemp(prefix="b3_gate_"))                    # outside the repository until the end-of-run check passes
    try:
        started = time.time()
        results, raw_files = {}, {}
        for fid in fitnesses:
            t0 = time.time()
            rows = run_fitness(fid, seeds, a.workers, perm)
            b = raw_bytes(fid, rows)
            with io_refusal(f"cannot write the raw file for {fid}"):
                (tmp / f"raw_{fid}.json").write_bytes(b)
            raw_files[fid] = {"path": f"raw_{fid}.json", "sha256": sha256_bytes(b), "rows": len(rows)}
            results[fid] = evaluate(fid, rows)
            results[fid]["wall_s"] = round(time.time() - t0, 1)
            print(f"[{fid}] B*={results[fid].get('b_star')} pass={results[fid]['pass']} "
                  f"{ {k: v['pass'] for k, v in results[fid]['criteria'].items()} } {results[fid]['wall_s']}s", flush=True)
        # the end-of-run check: HEAD, the tree and every deterministic input exactly as at the start, or nothing is published
        head1, dirty1 = git_head(), git_dirty()
        if head1 != head or dirty1:
            raise Refusal(f"the tree changed during the run (HEAD {head[:7]} -> {(head1 or 'none')[:7]}, dirty {dirty1}): the report is not published")
        moved = deep_findings(prov0, provenance_blocks(head, a.seeds), "provenance")
        if moved:
            raise Refusal("an input changed during the run: " + "; ".join(moved[:5]) + " — the report is not published")
        if prov0["architecture"]["sha256"] != sha256_bytes(ARCHITECTURE.read_bytes()):
            raise Refusal("docs/b3_architecture.md changed during the run: the report is not published")
        report = build_report(a.label, head, dirty, a.seeds, results, raw_files, round(time.time() - started, 1), provenance=prov0)
        report_bytes = (json.dumps(report, indent=1, sort_keys=True) + "\n").encode()
        with io_refusal("cannot write the report"):
            (tmp / "gate_report.json").write_bytes(report_bytes)
        expected = {"gate_report.json": sha256_bytes(report_bytes), **{rf["path"]: rf["sha256"] for rf in raw_files.values()}}
        publish(tmp, out, expected)
    finally:
        shutil.rmtree(tmp, True)
    return out / "gate_report.json"


def refuse_no_clobber(out: Path) -> None:
    """The gate never writes into an existing path: --out must not exist (a directory, a file, anything),
    and its nearest existing ancestor must be a directory. Named, before any work."""
    if out.exists() or out.is_symlink():
        raise Refusal(f"--out {_rel(out)} exists: the gate never overwrites an output (choose a new --out)")
    refuse_bad_out(out)


_copyfile = shutil.copyfile         # module-level so a test can make the second file's copy fail


def _read_staged(p: Path) -> bytes:  # module-level so a test can make the read-back fail
    return p.read_bytes()


def _rename_noreplace(src: str, dst: str) -> None:
    """rename(2) with RENAME_NOREPLACE: atomic, and it never replaces an existing `dst` of any kind — an
    empty directory included, which a plain os.rename would silently replace (the TOCTOU the owner
    injected between an exists() check and the rename). FileExistsError when dst exists; OSError
    otherwise (a filesystem without the flag gives EINVAL: no fallback to a replacing rename)."""
    import ctypes
    import errno
    libc = ctypes.CDLL(None, use_errno=True)
    if not hasattr(libc, "renameat2"):
        raise OSError(errno.ENOSYS, "renameat2 is not available: no atomic no-replace rename on this system")
    libc.renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    AT_FDCWD, RENAME_NOREPLACE = -100, 1
    if libc.renameat2(AT_FDCWD, os.fsencode(src), AT_FDCWD, os.fsencode(dst), RENAME_NOREPLACE) != 0:
        e = ctypes.get_errno()
        if e in (errno.EEXIST, errno.ENOTEMPTY):
            raise FileExistsError(e, os.strerror(e), src, None, dst)
        raise OSError(e, os.strerror(e), src, None, dst)


_rename = _rename_noreplace         # module-level so a test can make the final rename fail


def publish(built: Path, out: Path, expected: dict[str, str]) -> None:
    """No-clobber, atomic: the built files are copied into a staging directory created beside --out (the
    same filesystem), the staged set is read back and verified to be exactly `expected` (name ->
    sha256), and the staging directory becomes --out by ONE rename with RENAME_NOREPLACE — the
    kernel refuses to replace anything that exists at --out at that instant (no exists() check can
    close that window). On any failure — a copy, the read-back, the verification, the rename, a path
    that appeared — the staging directory is removed, --out is whatever it was (never ours), and
    nothing else under out.parent is touched."""
    if out.exists() or out.is_symlink():
        raise Refusal(f"--out {_rel(out)} appeared during the run: the gate never overwrites an output")
    with io_refusal(f"cannot create {_rel(out.parent)}"):
        out.parent.mkdir(parents=True, exist_ok=True)
    staging = None
    try:
        with io_refusal(f"cannot create a staging directory beside {_rel(out)}"):
            staging = Path(tempfile.mkdtemp(prefix=f".{out.name}.staging_", dir=out.parent))
        for name in sorted(expected):
            with io_refusal(f"cannot stage {name}"):
                _copyfile(str(built / name), str(staging / name))
        with io_refusal("cannot read back the staged files"):
            staged = {f.name: sha256_bytes(_read_staged(f)) for f in staging.iterdir()}
        if staged != expected:
            raise Refusal(f"the staged set is not the built set: {sorted(staged)} vs {sorted(expected)} (or a digest differs) — nothing published")
        try:
            _rename(str(staging), str(out))
        except FileExistsError:
            raise Refusal(f"--out {_rel(out)} appeared during the run: the gate never overwrites an output (the rename refused to replace it)") from None
        except OSError as e:
            raise Refusal(f"cannot publish {_rel(out)} (rename) ({e.__class__.__name__}: {e})") from None
        staging = None
    finally:
        if staging is not None:
            shutil.rmtree(staging, True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", type=int, default=SEEDS_DEFAULT)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--fitness", default="F1,F2")
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    try:
        print(run(a))
    except Refusal as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    return 0


# ------------------------------------------------------------------ the production validator (the plan and the renderer read a report only through it)


def shape_findings(rep) -> list[str]:
    """The lifecycle-2 report shape, type by type from the top: a dict with results = {fid: dict} each
    carrying criteria (a dict of dicts with a bool pass) and diagnostics (a dict), never H9 as a
    criterion nor H9_claim_condition; the provenance blocks dicts; raw_files a dict of dicts. Every
    problem is named; nothing here raises on a wrong type."""
    f: list[str] = []
    if not isinstance(rep, dict):
        return [f"the report is {type(rep).__name__}, not an object"]
    if rep.get("schema") != "b3_gate_report":
        f.append("schema is not b3_gate_report")
    if rep.get("lifecycle") != LIFECYCLE:
        f.append(f"lifecycle {rep.get('lifecycle')!r}, expected {LIFECYCLE}")
    for k in ("architecture", "thresholds", "engine", "control_x", "seeds", "map", "raw_files"):
        if not isinstance(rep.get(k), dict):
            f.append(f"{k}: {type(rep.get(k)).__name__}, not an object")
    results = rep.get("results")
    if not isinstance(results, dict):
        return f + [f"results: {type(results).__name__}, not an object"]
    for fid, res in results.items():
        if not isinstance(res, dict):
            f.append(f"results.{fid}: {type(res).__name__}, not an object"); continue
        crit = res.get("criteria")
        if not isinstance(crit, dict) or not all(isinstance(c, dict) and isinstance(c.get("pass"), bool) for c in crit.values()):
            f.append(f"results.{fid}.criteria: not an object of criteria each with a bool pass")
        elif "H9" in crit:
            f.append(f"results.{fid}.criteria.H9: H9 is a diagnostic, never a criterion")
        if "H9_claim_condition" in res:
            f.append(f"results.{fid}.H9_claim_condition: no claim condition in lifecycle 2")
        if not isinstance(res.get("diagnostics"), dict):
            f.append(f"results.{fid}.diagnostics: {type(res.get('diagnostics')).__name__}, not an object")
        if not isinstance(res.get("pass"), bool):
            f.append(f"results.{fid}.pass: not a bool")
    return f


def is_lifecycle2_report(rep) -> bool:
    """True for a report this tool writes: the lifecycle-2 shape (shape_findings empty)."""
    return not shape_findings(rep)


def deep_findings(expected, actual, path: str = "") -> list[str]:
    """Field for field, entry for entry: every difference between two JSON documents, each named by
    its path (`results.F1.criteria.H5.required_pairs_N`, `pairs[3].runs.O.ledger[17].decoded`, ...).
    Both sides are JSON-normalised first (a tuple and a list are the same entry)."""
    def norm(x):
        return json.loads(json.dumps(x, sort_keys=True))

    def walk(e, a, at):
        if isinstance(e, dict) and isinstance(a, dict):
            out = []
            for k in e:
                sub = f"{at}.{k}" if at else str(k)
                out.extend([f"{sub}: absent"] if k not in a else walk(e[k], a[k], sub))
            out.extend(f"{at}.{k}: unexpected" if at else f"{k}: unexpected" for k in a if k not in e)
            return out
        if isinstance(e, list) and isinstance(a, list):
            out = []
            if len(e) != len(a):
                out.append(f"{at}: {len(a)} entries, expected {len(e)}")
            for i in range(min(len(e), len(a))):
                out.extend(walk(e[i], a[i], f"{at}[{i}]"))
            return out
        if e != a or type(e) is not type(a):
            return [f"{at}: {a!r}, expected {e!r}"]
        return []
    return walk(norm(expected), norm(actual), path)


def load_json(path: Path, what: str) -> dict:
    try:
        return json.loads(path.read_bytes())
    except OSError as e:
        raise Refusal(f"{what} {_rel(path)}: cannot be read ({e.__class__.__name__}: {e})") from None
    except json.JSONDecodeError as e:
        raise Refusal(f"{what} {_rel(path)}: not JSON ({e})") from None


_EVAL_CACHE: dict = {}      # (sha256 of the raw bytes actually read, the thresholds) -> evaluate()'s result: the only thing cached


def evaluate_raw(fid: str, b: bytes, rows: list[dict]) -> dict:
    """evaluate() on rows read from raw bytes `b`, cached by the bytes' digest and the current
    thresholds — the expensive step only; nothing about a verdict is remembered."""
    key = (sha256_bytes(b), json.dumps(THRESHOLDS, sort_keys=True))
    if key not in _EVAL_CACHE:
        _EVAL_CACHE[key] = evaluate(fid, rows)
    return copy.deepcopy(_EVAL_CACHE[key])


def validate_report(path: Path) -> dict:
    """The gate report as an authority, or a named Refusal — re-read and re-checked on EVERY call (no
    verdict is cached; only evaluate() is, by the raw bytes' digest): the shape, type by type; the
    provenance — head_at_run an existing commit, a clean tree at the start, and every deterministic
    block (architecture at that commit, thresholds, engine, cartographer, control X, the seeds'
    derivation and every exclusion source, the map, the gate fitness) equal to what provenance_blocks
    computes now; the architecture bytes at that commit equal to the current file's; every raw file
    present with its recorded digest, its rows carrying the seeds the master and count re-derive
    under the current exclusion; and evaluate() re-run from every raw file with every field of the
    recorded result equal (a modified statistic, criterion, B* or N is named by its path)."""
    path = Path(path)
    rep = load_json(path, "the gate report")

    def need(cond: bool, msg: str):
        if not cond:
            raise Refusal(f"gate report {_rel(path)}: {msg}")
    shape = shape_findings(rep)
    need(not shape, "not the lifecycle-2 shape: " + "; ".join(shape[:5]))
    need(rep.get("schema_version") == REPORT_SCHEMA_VERSION, f"schema_version {rep.get('schema_version')!r}, expected {REPORT_SCHEMA_VERSION!r}")
    head = rep.get("head_at_run")
    need(commit_exists(head), f"head_at_run {head!r} is not a commit of this repository")
    need(rep.get("worktree_dirty_at_start") is False, f"worktree_dirty_at_start {rep.get('worktree_dirty_at_start')!r}: the gate must have run on a clean tree")
    seeds = rep["seeds"]
    need(isinstance(seeds.get("count"), int) and not isinstance(seeds.get("count"), bool) and seeds["count"] > 0, "seeds.count is not a positive integer")
    prov = provenance_blocks(head, seeds["count"])
    need(prov["architecture"]["sha256"] is not None, f"docs/b3_architecture.md is not in commit {head[:7]}")
    diff = deep_findings({k: prov[k] for k in PROVENANCE_KEYS}, {k: rep.get(k) for k in PROVENANCE_KEYS})
    need(not diff, "the provenance differs from the current derivation: " + "; ".join(diff[:5]) + (f" (+{len(diff) - 5} more)" if len(diff) > 5 else ""))
    with io_refusal("docs/b3_architecture.md cannot be read"):
        current_arch = sha256_bytes(ARCHITECTURE.read_bytes())
    need(current_arch == prov["architecture"]["sha256"], f"docs/b3_architecture.md in the working tree is not the one commit {head[:7]} carries (the report's binding)")
    results, raw_files = rep["results"], rep["raw_files"]
    need("F1" in results, "no result for the gate fitness F1")
    need(set(raw_files) == set(results), "raw_files must name exactly one raw file per result")
    excl, _ = gate_exclusion()
    expected_seeds = [tuple(x) for x in bs.pair_seeds(seeds["master_seed"], seeds["count"], exclude=frozenset(excl))]
    for fid, res in results.items():
        rf = raw_files[fid]
        need(isinstance(rf, dict) and rf.get("path") == f"raw_{fid}.json", f"raw_files.{fid}.path must be raw_{fid}.json")
        rp = path.parent / rf["path"]
        try:
            b = rp.read_bytes()
        except OSError as e:
            raise Refusal(f"gate report {_rel(path)}: raw file {rf['path']} cannot be read ({e.__class__.__name__})") from None
        need(sha256_bytes(b) == rf.get("sha256"), f"raw_files.{fid}.sha256 does not match {rf['path']}")
        try:
            raw = json.loads(b)
        except json.JSONDecodeError as e:
            raise Refusal(f"gate report {_rel(path)}: raw file {rf['path']} is not JSON ({e})") from None
        need(isinstance(raw, dict) and raw.get("fitness") == fid and raw.get("grid") == list(GRID), f"raw file {rf['path']}: fitness / grid are not this fitness and grid")
        rows = raw.get("rows")
        need(isinstance(rows, list) and all(isinstance(r, dict) for r in rows), f"raw file {rf['path']}: rows is not a list of objects")
        need(len(rows) == seeds["count"] and rf.get("rows") == len(rows), f"raw file {rf['path']}: {len(rows)} rows, expected seeds.count {seeds['count']}")
        need([(r.get("landscape_seed"), r.get("operator_seed")) for r in rows] == expected_seeds,
             f"raw file {rf['path']}: the rows do not carry the seeds the master and count re-derive under the current exclusion")
        recomputed = evaluate_raw(fid, b, rows)
        recorded = {k: v for k, v in res.items() if k != "wall_s"}
        diff = deep_findings(recomputed, recorded, f"results.{fid}")
        need(not diff, "the recorded result differs from evaluate() re-run on the raw rows: " + "; ".join(diff[:5]) + (f" (+{len(diff) - 5} more)" if len(diff) > 5 else ""))
    return rep


if __name__ == "__main__":
    sys.exit(main())

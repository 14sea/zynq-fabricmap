#!/usr/bin/env python3
"""B2 — the session plan and the preregistered prediction (host-only).

    b2_plan.py [--out evidence/b2]

Seeds: master = first 4 bytes of sha256('b2-session|' + the instrument commit) — the B1
rule under a new label — then N (landscape, operator) pairs from one Rng stream, skipping
the excluded seeds (B1's master and qualification seeds included). The gate's seeds come
from a different label and a moving commit, so they are disjoint by construction.

Prediction: the reference engine over the fabric model for every pair and both arms at
the gate-selected fitness and budget — the per-record fitness sequence (hashed), every
pair's paired difference, the champions and their holdout known answers. On a correct
instrument the board reproduces these bytes; the primary verdict is then the sign test
over the N pairs as preregistered, computed here in advance so that nobody moves a
goalpost after the run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_gate as bg  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_search as bs  # noqa: E402

INSTRUMENT_COMMIT = "689dde1dad374536c625bbe2b05986ee89eb4c94"
SESSION_LABEL = "b2-session"
GATE_REPORT = REPO_ROOT / "evidence/b2/gate/recomputed_2026_09_10/gate_report.json"      # v0.3 rules over run 3's rows
GATE_RUN_REPORT = REPO_ROOT / "evidence/b2/gate/gate_report.json"                         # run 3 as run (the rows' provenance)
ALPHA = 0.05
AUDIT_POLICY = "all-self-reporting"      # the owner's decision of 2026-09-10 for the first B2 image
SESSION_SPAN_MAX_S = 7200                # the registered two-hour criterion, applied per session to the EXPECTED span
DEADLINE_FORMULA = "1.25 x records x 3600 / rate + 600 (the instrument's l6_schedule.session_timeout_s)"
# every frozen seed set a new draw must avoid (explicit exclusion; different labels do not guarantee disjointness)
FROZEN_SEED_SETS = ("evidence/b2/gate/v0.1_2026-09-10/gate_report.json", "evidence/b2/gate/gate_report.json", "evidence/b3/sim/sim_report.json")


def frozen_seed_exclusion() -> tuple[set[int], dict]:
    """The union of every archived run's (landscape, operator) seeds, re-derived from each
    report's master seed and count, plus the master seeds themselves."""
    excl: set[int] = set()
    where = {}
    for rel in FROZEN_SEED_SETS:
        r = json.loads((REPO_ROOT / rel).read_text())
        seeds = bs.pair_seeds(r["seeds"]["master_seed"], r["seeds"]["count"])
        flat = {x for p in seeds for x in p} | {r["seeds"]["master_seed"]}
        where[rel] = {"master_seed": r["seeds"]["master_seed"], "count": r["seeds"]["count"], "values": len(flat)}
        excl |= flat
    return excl, where


def session_split(n_pairs: int, budget: int, rate_per_hour: float | None) -> dict:
    """The frozen split rule (preregistration §2): a session holds as many whole pairs as
    keep its EXPECTED span (records x 3600 / rate) within SESSION_SPAN_MAX_S, at least one;
    pairs are assigned in order; every session has its own opening and closing baseline.
    Without a measured rate (before B2Q) the split is UNDETERMINED and only the record
    arithmetic per candidate split is reported."""
    per_pair = 2 * budget + 2                     # both arms' search + both champions' holdout evaluations
    def records(p):
        return 2 + p * per_pair
    if rate_per_hour is None:
        return {"status": "UNDETERMINED until B2Q measures the all-self-reporting rate", "records_per_pair": per_pair,
                "candidates": {f"{p} pairs/session": {"records": records(p), "sessions": -(-n_pairs // p),
                                                       "total_records": sum(records(min(p, n_pairs - i * p)) for i in range(-(-n_pairs // p)))}
                               for p in range(1, n_pairs + 1)}}
    p_max = max(1, max((p for p in range(1, n_pairs + 1) if records(p) * 3600 / rate_per_hour <= SESSION_SPAN_MAX_S), default=1))
    sessions = []
    left = n_pairs
    while left > 0:
        p = min(p_max, left)
        sessions.append({"pairs": list(range(n_pairs - left, n_pairs - left + p)), "records": records(p),
                         "expected_span_s": records(p) * 3600 / rate_per_hour,
                         "deadline_s": 1.25 * records(p) * 3600 / rate_per_hour + 600})
        left -= p
    return {"status": "DETERMINED", "rate_per_hour": rate_per_hour, "pairs_per_session_max": p_max, "sessions": sessions,
            "total_records": sum(s["records"] for s in sessions)}


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def decision(deltas: list[int]) -> dict:
    p, pos, neg, ties = bg.sign_test_p(deltas)
    return {"positives": pos, "negatives": neg, "ties": ties, "sign_test_p": p, "alpha": ALPHA,
            "verdict": "map-guided > random-safe SUPPORTED" if p <= ALPHA else "NOT SUPPORTED"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="evidence/b2")
    ap.add_argument("--rate-per-hour", type=float, default=None,
                    help="the B2Q-measured all-self-reporting rate from the manifest's calibration (S3); without it the split is UNDETERMINED")
    ap.add_argument("--gate-report", default=None, help="override the gate report path (tests)")
    args = ap.parse_args(argv)
    gate_report = Path(args.gate_report) if args.gate_report else GATE_REPORT
    out = REPO_ROOT / args.out
    gate = json.loads(gate_report.read_text())
    if gate["thresholds"].get("rules_version") != bg.THRESHOLDS["rules_version"]:
        raise SystemExit(f"the gate report's rules ({gate['thresholds'].get('rules_version')}) are not the current ones ({bg.THRESHOLDS['rules_version']})")
    fid = gate["selected_fitness"]
    if fid is None:
        raise SystemExit("the gate selected no fitness: no plan")
    res = gate["results"][fid]
    budget = res["b_star"]
    n_pairs = res["criteria"]["G5"]["required_pairs_N"]
    master = bs.master_seed(SESSION_LABEL, INSTRUMENT_COMMIT)
    exclusion, exclusion_sources = frozen_seed_exclusion()
    seeds = bs.pair_seeds(master, n_pairs, exclude=exclusion)
    truth = bm.truth_mapping()
    masks = bl.universe_mask(truth)
    fabric = bs.ModelFabric(truth)
    self_map = bmaps.load_self_map()
    view = bmaps.MapView(self_map, bl.train_vectors())
    pairs = []
    fitness_sequence: list[int] = []
    for r, (l_seed, o_seed) in enumerate(seeds):
        land = bl.Landscape(fid, l_seed, masks=masks, truth=truth)
        order = ("A", "B") if r % 2 == 0 else ("B", "A")     # the arm order alternates by pair
        runs = {}
        for arm in order:
            rr = bs.run(bs.ARM_RANDOM_SAFE if arm == "A" else bs.ARM_MAP_GUIDED, land, view if arm == "B" else None, o_seed, budget, fabric, log_moves=True)
            fitness_sequence.extend(m["fit"] for m in rr.moves)
            runs[arm] = {"best_train": rr.best_trace[-1], "champion_genome_sha256": hashlib.sha256(bc.genome_to_hex(rr.champion.genome).encode()).hexdigest(),
                         "champion_holdout": rr.champion_holdout, "column_moves": rr.column_moves,
                         "moves_sha256": sha256_json([[m["parent"], m["kind"], m["bits"], m["fit"]] for m in rr.moves])}
        for arm in order:
            fitness_sequence.append(runs[arm]["champion_holdout"])
        pairs.append({"pair": r, "landscape_seed": l_seed, "operator_seed": o_seed, "arm_order": list(order),
                      "target": [f"{t:016x}" for t in land.target], "base_train_fitness": land.train_fitness(fabric(0)),
                      "runs": runs, "delta_B_minus_A": runs["B"]["best_train"] - runs["A"]["best_train"]})
    deltas = [p["delta_B_minus_A"] for p in pairs]
    records = 1 + n_pairs * 2 * budget + n_pairs * 2 + 1
    rate_sampled = bg.SAMPLED_AUDIT_RATE_PER_HOUR
    rate_all = bg.ALL_SELF_REPORTING_RATE_PER_HOUR
    plan = {
        "schema": "b2_plan", "schema_version": "1.0.0", "session": "B2", "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fitness": fid, "budget_per_arm": budget, "pairs": n_pairs, "engine": {"version": bs.ENGINE_VERSION, "mu": bs.MU, "lambda": bs.LAMBDA, "kmax": bs.KMAX},
        "carrier": "the qualified B1 carrier (docs/b2_architecture.md D1)",
        "map": {"path": str(bmaps.SELF_MAP.relative_to(REPO_ROOT)), "sha256": bmaps.sha256_of(self_map), "view": view.describe()},
        "seed_derivation": {"label": SESSION_LABEL, "commit": INSTRUMENT_COMMIT, "master_seed": master,
                            "rule": "first 4 bytes of sha256(label + '|' + instrument commit); pairs from one Rng stream; the fixed excluded "
                                    "seeds AND every archived run's seed set skipped (explicit exclusion — disjointness is enforced, not assumed)",
                            "excluded_fixed": sorted(bs.EXCLUDED_SEEDS), "excluded_frozen_sets": exclusion_sources,
                            "excluded_values_total": len(exclusion | set(bs.EXCLUDED_SEEDS))},
        "gate": {"path": str(gate_report.relative_to(REPO_ROOT)) if gate_report.is_relative_to(REPO_ROOT) else str(gate_report), "sha256": sha256_file(gate_report), "head_at_run": gate["head_at_run"],
                 "rules_version": gate["thresholds"]["rules_version"], "rows_from": gate.get("source"),
                 "run_report": {"path": str(GATE_RUN_REPORT.relative_to(REPO_ROOT)), "sha256": sha256_file(GATE_RUN_REPORT)}},
        "audit_policy": AUDIT_POLICY,
        "records": {"per_pair": 2 * budget + 2, "single_session_total": records,
                    "note": "one opening and one closing baseline PER SESSION; the total depends on the split (session_split)"},
        "arm_order": "pair r runs A then B when r is even, B then A when r is odd",
        "session_split": session_split(n_pairs, budget, args.rate_per_hour),
        "session_span_max_s": SESSION_SPAN_MAX_S, "deadline_formula": DEADLINE_FORMULA,
        "planning_rates_NOT_calibration": {"sampled_audit_S3_per_hour": rate_sampled, "all_self_reporting_B1plan_per_hour": rate_all,
                                           "last_B1_mapping_observed_per_hour": 2807,
                                           "note": "older P3/B1 rates, shown for planning only; the B2 rate is measured by B2Q and written into "
                                                   "the manifest before the split is determined (preregistration §6, §8)"},
        "primary": {"statistic": "one-sided exact sign test over the N pairs' delta (best-so-far train fitness at the budget, self-map minus random-safe)",
                    "alpha": ALPHA, "ties": "excluded from n, counted"},
        "architecture": {"path": "docs/b2_architecture.md", "sha256": sha256_file(REPO_ROOT / "docs/b2_architecture.md")},
    }
    prediction = {
        "schema": "b2_prediction", "schema_version": "1.0.0", "fitness": fid, "budget_per_arm": budget, "pairs": pairs,
        "deltas": deltas, "predicted_primary": decision(deltas),
        "fitness_sequence_sha256": sha256_json(fitness_sequence), "fitness_sequence_length": len(fitness_sequence),
        "note": "every value is the reference engine over the fabric model; on a correct instrument the board reproduces them byte for byte",
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "plan.json").write_text(json.dumps(plan, indent=1, sort_keys=True))
    (out / "prediction.json").write_text(json.dumps(prediction, indent=1, sort_keys=True))
    plan["prediction_sha256"] = sha256_file(out / "prediction.json")
    (out / "plan.json").write_text(json.dumps(plan, indent=1, sort_keys=True))
    print(json.dumps({"fitness": fid, "budget": budget, "pairs": n_pairs, "master_seed": master, "records": records,
                      "deltas": deltas, "predicted_primary": prediction["predicted_primary"],
                      "audit_policy": AUDIT_POLICY, "excluded_values": plan["seed_derivation"]["excluded_values_total"],
                      "session_split": plan["session_split"]["status"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

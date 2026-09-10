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
GATE_REPORT = REPO_ROOT / "evidence/b2/gate/gate_report.json"
ALPHA = 0.05


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
    args = ap.parse_args(argv)
    out = REPO_ROOT / args.out
    gate = json.loads(GATE_REPORT.read_text())
    fid = gate["selected_fitness"]
    if fid is None:
        raise SystemExit("the gate selected no fitness: no plan")
    res = gate["results"][fid]
    budget = res["b_star"]
    n_pairs = res["criteria"]["G5"]["required_pairs_N"]
    master = bs.master_seed(SESSION_LABEL, INSTRUMENT_COMMIT)
    seeds = bs.pair_seeds(master, n_pairs)
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
                            "rule": "first 4 bytes of sha256(label + '|' + instrument commit); pairs from one Rng stream; excluded seeds skipped",
                            "excluded": sorted(bs.EXCLUDED_SEEDS)},
        "gate": {"path": str(GATE_REPORT.relative_to(REPO_ROOT)), "sha256": sha256_file(GATE_REPORT), "head_at_run": gate["head_at_run"],
                 "seeds_master": gate["seeds"]["master_seed"], "rules_version": gate["thresholds"]["rules_version"]},
        "records": {"opening_baseline": 1, "search": n_pairs * 2 * budget, "champion_holdout": n_pairs * 2, "closing_baseline": 1, "total": records},
        "arm_order": "pair r runs A then B when r is even, B then A when r is odd",
        "session_time": {"sampled_audit_rate_per_hour": rate_sampled, "all_self_reporting_rate_per_hour": rate_all,
                         "expected_span_s_sampled_audit": records * 3600 / rate_sampled, "expected_span_s_all_self_reporting": records * 3600 / rate_all,
                         "deadline_formula": "1.25 x records x 3600 / rate + 600 (the instrument's l6_schedule.session_timeout_s)",
                         "deadline_s_sampled_audit": 1.25 * records * 3600 / rate_sampled + 600,
                         "deadline_s_all_self_reporting": 1.25 * records * 3600 / rate_all + 600},
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
                      "span_h_sampled": plan["session_time"]["expected_span_s_sampled_audit"] / 3600,
                      "span_h_all": plan["session_time"]["expected_span_s_all_self_reporting"] / 3600}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

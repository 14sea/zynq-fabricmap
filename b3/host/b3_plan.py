#!/usr/bin/env python3
"""B3 lifecycle 2 — the session plan and the preregistered prediction (host-only; preregistration
DRAFT v0.3 §2–§3, §6a, §8).

    b3_plan.py [--out evidence/b3] [--rate-per-hour R] [--gate-report P] [--qualification]

Seeds: master = first 4 bytes of sha256('b3-session-2|' + the instrument commit), N pairs from one Rng
stream, skipping the fixed excluded seeds AND every value of every archived set — B2's two gate
runs, the B3 simulation, B2's nine session pairs and master, B2Q's pair and master, lifecycle 1's gate
run 1 and its nine trial pairs (pilot, §8b), and the lifecycle-2 gate's 200 pairs and master
(`b3_gate.gate_exclusion` plus the gate report's own seeds). Disjointness is ENFORCED by explicit
exclusion and every source is recorded in the plan. The gate report must be the lifecycle-2 one
(label `b3-gate-2`, the current rules version); lifecycle 1's is refused by name.

Prediction: the reference engine over the fabric model for every pair and the three arms in the
pair's prefix-balanced order — the per-record fitness sequence (hashed), every arm's best, champion
and holdout known answer, the O arm's EVERY ledger entry embedded in the document (`pairs[r].runs.O.ledger`,
specimen_ledger 1.1.0, B* entries per run — §8's first P2: a digest and a count are not enough), its
final map (digest), map version and anomaly count, and the two paired deltas Δ1 = O − R and
Δ2 = O − end-to-end F (333 charged from F's own trace). ONE confirmatory primary (Δ1, one-sided exact
sign test, α = 0.05) is predicted in advance; Δ2 is the SECONDARY OUTCOME, reported (positives /
negatives / ties, exact p, mean, median, Cohen's d) with no threshold (v0.3, the owner's ruling).
`prediction_findings` compares two prediction documents field for field and entry for entry, naming
the path of every difference — the comparison `plan_findings` and the adjudicator use.

Stop rule (§8's second P2): evaluated on the prediction BEFORE any canonical write — if the predicted
primary does not reach α, nothing is written under `evidence/b3/` (plan.json, prediction.json), the
CLI exits 3 naming the primary; a trial run can write only to an explicit NON-canonical `--out`.
The seeds are not redrawn and N is not raised.

Session split: the frozen rule with the calibration margin — a session holds the largest whole number
of pairs whose expected span records × 3600 / (0.85 × R_measured) ≤ 7 200 s; INFEASIBLE is a named
state; without a rate the split is UNDETERMINED (the committed-plan stage rule).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "host", REPO_ROOT / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_gate as bg  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_carto as carto_mod  # noqa: E402
import b3_gate as b3g  # noqa: E402
import b3_online_arm as oa  # noqa: E402
import b3_online_map as om  # noqa: E402

INSTRUMENT_COMMIT = bp.INSTRUMENT_COMMIT
LIFECYCLE = 2
SESSION_LABEL = "b3-session-2"
QUAL_LABEL = "b3-qualification-2"
QUAL_BUDGET = 40                        # preregistration §6a (the owner's choice): one pair at budget 40 in all three arms
QUAL_PAIRS = 1
GATE_REPORT = REPO_ROOT / b3g.OUT_DEFAULT / "gate_report.json"
PLAN_DIR = REPO_ROOT / "evidence/b3"    # the canonical output: plan.json / prediction.json live here and only after the stop rule passes
SCHEMA_VERSION = "2.0.0"                # plan and prediction: one primary + a secondary outcome, the ledger embedded (lifecycle 2)
ALPHA = 0.05
AUDIT_POLICY = "all-self-reporting"
SESSION_SPAN_MAX_S = 7200
CALIBRATION_MARGIN = 0.85               # preregistration §2: R_cal = 0.85 x R_measured (B2's sessions ran at 0.87 / 0.90 of its B2Q rate)
DEADLINE_FORMULA = "1.25 x records x 3600 / rate_for_split + 600 (rate_for_split = 0.85 x the B3Q-measured rate)"
ARM_SEQUENCE = ("RFO", "FOR", "ORF", "ROF", "OFR", "FRO")     # pair r runs ARM_SEQUENCE[r % 6]; position counts differ by <= 1, equal iff N % 3 == 0
QUAL_PLANNING_RATE_PER_HOUR = 2630.433828050359               # the slowest archived OBSERVED rate: B2 session 1 (evidence/b2/b2_17A6_2026-09-16-01)
QUAL_PLANNING_RATE_RULE = "the slowest archived observed all-self-reporting rate (B2 session 1); B3Q MEASURES the real one"
PLANNING_RATES = {"B2_calibration_B2Q_per_hour": 3016.3995578641097, "B2_session_1_observed_per_hour": 2630.433828050359,
                  "B2_session_2_observed_per_hour": 2723.7861917937157,
                  "note": "B2's rates, for planning only; the B3 rate is measured by B3Q (ledger bytes on every O-arm search record) and "
                          "written into the manifest's calibration before the split is determined; the 0.85 margin is frozen, not a calibration"}
PLAN_NON_OPERATIONAL = ("generated_utc", "prediction_sha256")


class RateInvalid(ValueError):
    pass


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def records_per_pair(budget: int) -> int:
    return 3 * budget + 3


def session_records(pairs: int, budget: int) -> int:
    return 2 + pairs * records_per_pair(budget)


def arm_order(r: int) -> tuple[str, ...]:
    return tuple(ARM_SEQUENCE[r % len(ARM_SEQUENCE)])


def session_split(n_pairs: int, budget: int, rate_measured: float | None) -> dict:
    per_pair = records_per_pair(budget)

    def records(p):
        return 2 + p * per_pair
    if rate_measured is None:
        return {"status": "UNDETERMINED until B3Q measures the all-self-reporting rate", "records_per_pair": per_pair,
                "calibration_margin": CALIBRATION_MARGIN,
                "candidates": {f"{p} pairs/session": {"records": records(p), "sessions": -(-n_pairs // p),
                                                       "total_records": sum(records(min(p, n_pairs - i * p)) for i in range(-(-n_pairs // p)))}
                               for p in range(1, n_pairs + 1)}}
    if isinstance(rate_measured, bool) or not isinstance(rate_measured, (int, float)) or not math.isfinite(rate_measured) or rate_measured <= 0:
        raise RateInvalid(f"rate_measured must be a finite positive number, got {rate_measured!r}")
    rate = CALIBRATION_MARGIN * rate_measured
    feasible = [p for p in range(1, n_pairs + 1) if records(p) * 3600 / rate <= SESSION_SPAN_MAX_S]
    if not feasible:
        return {"status": "INFEASIBLE", "rate_measured": rate_measured, "calibration_margin": CALIBRATION_MARGIN, "rate_for_split": rate,
                "records_per_pair": per_pair, "one_pair_expected_span_s": records(1) * 3600 / rate, "session_span_max_s": SESSION_SPAN_MAX_S,
                "min_feasible_rate_for_split_per_hour": records(1) * 3600 / SESSION_SPAN_MAX_S,
                "note": "not even one pair with its baselines fits the registered expected span at the margined rate: no S3 plan"}
    p_max = max(feasible)
    sessions, left = [], n_pairs
    while left > 0:
        p = min(p_max, left)
        sessions.append({"pairs": list(range(n_pairs - left, n_pairs - left + p)), "records": records(p),
                         "expected_span_s": records(p) * 3600 / rate, "deadline_s": 1.25 * records(p) * 3600 / rate + 600})
        left -= p
    return {"status": "DETERMINED", "rate_measured": rate_measured, "calibration_margin": CALIBRATION_MARGIN, "rate_for_split": rate,
            "pairs_per_session_max": p_max, "sessions": sessions, "total_records": sum(s["records"] for s in sessions)}


def decision(deltas: list[int], verdict_text: str) -> dict:
    """The primary: one-sided exact sign test against alpha, with a verdict."""
    p, pos, neg, ties = bg.sign_test_p(deltas)
    return {"positives": pos, "negatives": neg, "ties": ties, "sign_test_p": p, "alpha": ALPHA,
            "verdict": f"{verdict_text} SUPPORTED" if p <= ALPHA else "NOT SUPPORTED"}


def secondary_report(deltas: list[int]) -> dict:
    """The secondary outcome (preregistration v0.3 §4): every value reported, EXACT to the prediction on
    the board, no significance threshold and no verdict."""
    p, pos, neg, ties = bg.sign_test_p(deltas)
    return {"positives": pos, "negatives": neg, "ties": ties, "sign_test_p": p,
            "mean": bg.mean(deltas), "median": bg.median(deltas), "cohen_d": bg.cohen_d(deltas),
            "threshold": None, "note": "reported secondary outcome: no significance threshold, no verdict (preregistration v0.3 §4)"}


# ------------------------------------------------------------------ the gate's numbers and the seeds


def gate_inputs(gate_report: Path = GATE_REPORT) -> dict:
    """The gate's numbers, read only through the production validator (`b3_gate.validate_report`:
    schema 2.0.0, provenance, the architecture binding, every raw file's digest and seeds, evaluate()
    re-run from the raw rows) — a Refusal names whatever fails; B* and N are trusted only after that."""
    gate = b3g.validate_report(gate_report)
    fid = gate["gate_fitness"]
    res = gate["results"][fid]
    if not res["pass"] or res["b_star"] is None:
        raise b3g.Refusal(f"the gate did not pass for {fid}: no plan")
    return {"fitness": fid, "budget_per_arm": res["b_star"], "pairs": res["criteria"]["H5"]["required_pairs_N"],
            "head_at_run": gate["head_at_run"],
            "rules_version": gate["thresholds"]["rules_version"], "architecture_sha256": gate["architecture"]["sha256"],
            "control_x_permutation_sha256": gate["control_x"]["permutation_sha256"],
            "seeds": {"label": gate["seeds"]["label"], "master_seed": gate["seeds"]["master_seed"], "count": gate["seeds"]["count"]}}


def session_exclusion(gate_report: Path = GATE_REPORT) -> tuple[set[int], dict]:
    """Every archived set the gate excluded, plus the gate's own seeds (the validator has already
    checked that the raw rows carry the seeds the master and count re-derive; they are read back from
    the validated report's raw file)."""
    excl, sources = b3g.gate_exclusion()
    gi = gate_inputs(gate_report)
    gseeds = bs.pair_seeds(gi["seeds"]["master_seed"], gi["seeds"]["count"], exclude=frozenset(excl))
    flat = {s for p in gseeds for s in p} | {gi["seeds"]["master_seed"]}
    sources[_rel(gate_report) + " (the B3 gate's pairs)"] = {"master_seed": gi["seeds"]["master_seed"], "count": gi["seeds"]["count"], "values": len(flat)}
    return excl | flat, sources


def session_seeds(n_pairs: int, gate_report: Path = GATE_REPORT) -> tuple[int, list[tuple[int, int]], dict, set]:
    master = bs.master_seed(SESSION_LABEL, INSTRUMENT_COMMIT)
    exclusion, sources = session_exclusion(gate_report)
    return master, bs.pair_seeds(master, n_pairs, exclude=frozenset(exclusion)), sources, exclusion


def qualification_master() -> int:
    return bs.master_seed(QUAL_LABEL, INSTRUMENT_COMMIT)


def qualification_seeds(b3_pairs: list, gate_report: Path = GATE_REPORT) -> list[tuple[int, int]]:
    exclusion, _ = session_exclusion(gate_report)
    used = {int(s) for pair in b3_pairs for s in pair}
    return bs.pair_seeds(qualification_master(), QUAL_PAIRS, exclude=frozenset(exclusion) | used)


# ------------------------------------------------------------------ the prediction

_PREDICT_CACHE: dict = {}


def predict(fid: str, budget: int, seeds: list[tuple[int, int]], map_sha256: str | None = None) -> dict:
    """The reference over the fabric model for the pairs, three arms in the pair's order. Pure: the
    same inputs give the same bytes."""
    self_map = bmaps.load_self_map()
    if map_sha256 is not None and bmaps.sha256_of(self_map) != map_sha256:
        raise ValueError("the committed self-map is not the one the caller expects")
    key = (fid, budget, tuple(tuple(x) for x in seeds), bmaps.sha256_of(self_map))
    if key in _PREDICT_CACHE:
        return copy.deepcopy(_PREDICT_CACHE[key])
    truth = bm.truth_mapping()
    masks = bl.universe_mask(truth)
    fabric = bs.ModelFabric(truth)
    view = bmaps.MapView(self_map, bl.train_vectors())
    pairs, fitness_sequence = [], []
    for r, (l_seed, o_seed) in enumerate(seeds):
        land = bl.Landscape(fid, l_seed, masks=masks, truth=truth)
        base = land.train_fitness(fabric(0))
        order = arm_order(r)
        runs = {}
        for arm in order:
            if arm == "R":
                rr = bs.run(bs.ARM_RANDOM_SAFE, land, None, o_seed, budget, fabric, log_moves=True)
                fitness_sequence.extend(m["fit"] for m in rr.moves)
                runs[arm] = {"best_train": rr.best_trace[-1], "champion_genome_sha256": hashlib.sha256(bc.genome_to_hex(rr.champion.genome).encode()).hexdigest(),
                             "champion_holdout": rr.champion_holdout, "column_moves": rr.column_moves,
                             "moves_sha256": sha256_json([[m["parent"], m["kind"], m["bits"], m["fit"]] for m in rr.moves])}
            elif arm == "F":
                rr = bs.run(bs.ARM_MAP_GUIDED, land, view, o_seed, budget, fabric, log_moves=True)
                fitness_sequence.extend(m["fit"] for m in rr.moves)
                runs[arm] = {"best_train": rr.best_trace[-1], "champion_genome_sha256": hashlib.sha256(bc.genome_to_hex(rr.champion.genome).encode()).hexdigest(),
                             "champion_holdout": rr.champion_holdout, "column_moves": rr.column_moves,
                             "moves_sha256": sha256_json([[m["parent"], m["kind"], m["bits"], m["fit"]] for m in rr.moves]),
                             "end_to_end_at_budget": oa.end_to_end_frozen(rr.best_trace, base, budget)}
            else:
                oo = oa.run_online(land, o_seed, budget, fabric, keep_ledger=True)
                fitness_sequence.extend(e["fitness"] for e in oo.ledger)
                doc = om.render(oo.carto, {"landscape_seed": l_seed, "operator_seed": o_seed, "fitness": fid, "budget": budget}, oo.ledger)
                v = om.verify(doc, oo.ledger, truth)
                if not v["ok"]:
                    raise ValueError(f"the model's own online map does not verify for pair {r}: {v['findings'][:2]}")
                runs[arm] = {"best_train": oo.best_trace[-1], "champion_genome_sha256": hashlib.sha256(bc.genome_to_hex(oo.champion.genome).encode()).hexdigest(),
                             "champion_holdout": oo.champion_holdout, "column_moves": oo.column_moves,
                             "moves_sha256": sha256_json([[e["parent_born"], e["move_kind"], e["intervention"], e["fitness"]] for e in oo.ledger]),
                             "budget": budget, "ledger_schema_version": oa.LEDGER_SCHEMA_VERSION,
                             "ledger": json.loads(json.dumps(oo.ledger)),      # EVERY entry, embedded (preregistration v0.3 §3 / §8); JSON-normalised so bytes compare
                             "ledger_sha256": om.canonical_sha256(oo.ledger), "ledger_entries": len(oo.ledger),
                             "decoded_final": len(oo.carto.decoded), "map_version_final": oo.carto.version, "anomalies": oo.anomalies,
                             "wrong_decodes": v["accuracy"]["wrong"], "final_state_sha256": oo.state_trace[-1],
                             "online_map_sha256": om.canonical_sha256(doc)}
        for arm in order:
            fitness_sequence.append(runs[arm]["champion_holdout"])
        pairs.append({"pair": r, "landscape_seed": l_seed, "operator_seed": o_seed, "arm_order": list(order),
                      "target": [f"{t:016x}" for t in land.target], "base_train_fitness": base, "runs": runs,
                      "delta1_O_minus_R": runs["O"]["best_train"] - runs["R"]["best_train"],
                      "delta2_O_minus_endtoend_F": runs["O"]["best_train"] - runs["F"]["end_to_end_at_budget"]})
    out = {"pairs": pairs, "deltas1": [p["delta1_O_minus_R"] for p in pairs], "deltas2": [p["delta2_O_minus_endtoend_F"] for p in pairs],
           "fitness_sequence_sha256": sha256_json(fitness_sequence), "fitness_sequence_length": len(fitness_sequence),
           "map_sha256": bmaps.sha256_of(self_map), "view": view.describe()}
    _PREDICT_CACHE[key] = copy.deepcopy(out)
    return out


def build_prediction(fid: str, budget: int, seeds: list[tuple[int, int]], map_sha256: str | None = None) -> dict:
    pr = predict(fid, budget, seeds, map_sha256)
    return {"schema": "b3_prediction", "schema_version": SCHEMA_VERSION, "lifecycle": LIFECYCLE, "fitness": fid, "budget_per_arm": budget, "pairs": pr["pairs"],
            "deltas1": pr["deltas1"], "deltas2": pr["deltas2"],
            "predicted_primary": decision(pr["deltas1"], "online > random-safe"),
            "secondary_outcome": secondary_report(pr["deltas2"]),
            "fitness_sequence_sha256": pr["fitness_sequence_sha256"], "fitness_sequence_length": pr["fitness_sequence_length"],
            "b1_map_cost": oa.B1_MAP_COST, "carto_version": carto_mod.CARTO_VERSION,
            "note": "every value is the reference engine and cartographer over the fabric model, every O-arm ledger entry included; on a correct "
                    "instrument the board reproduces them byte for byte, decode for decode; one confirmatory primary (delta1), delta2 a reported "
                    "secondary outcome with no threshold (preregistration v0.3 §1, §3, §4)"}


def stop_rule_findings(prediction: dict) -> list[str]:
    """Preregistration v0.3 §3: the predicted PRIMARY (delta1 alone) on the fixed seeds must reach alpha,
    or the line stops — the seeds are not redrawn and N is not raised. The secondary outcome has no
    threshold and never stops the line. A named finding, or none."""
    d = prediction["predicted_primary"]
    if d["sign_test_p"] > d["alpha"]:
        return [f"predicted_primary: p = {d['sign_test_p']:.6g} > alpha {d['alpha']} ({d['positives']}/{d['negatives']}/{d['ties']}) — the line stops under the stop rule"]
    return []


def prediction_findings(expected: dict, actual: dict, path: str = "") -> list[str]:
    """Field for field, entry for entry: every difference between two prediction documents, each
    named by its path (`pairs[3].runs.O.ledger[17].decoded`, ...) — `b3_gate.deep_findings`, the
    same walk the gate validator uses. The comparison `plan_findings` and the adjudicator use — a
    digest alone would say only that something differs (§8's first P2)."""
    return b3g.deep_findings(expected, actual, path)


def build_plan(rate_measured: float | None, gate_report: Path | None = None, root: Path = REPO_ROOT) -> dict:
    gate_report = gate_report or GATE_REPORT
    g = gate_inputs(gate_report)
    fid, budget, n_pairs = g["fitness"], g["budget_per_arm"], g["pairs"]
    master, seeds, sources, exclusion = session_seeds(n_pairs, gate_report)
    self_map = bmaps.load_self_map()
    view = bmaps.MapView(self_map, bl.train_vectors())
    return {
        "schema": "b3_plan", "schema_version": SCHEMA_VERSION, "lifecycle": LIFECYCLE, "session": "B3",
        "fitness": fid, "budget_per_arm": budget, "pairs": n_pairs,
        "engine": {"version": bs.ENGINE_VERSION, "mu": bs.MU, "lambda": bs.LAMBDA, "kmax": bs.KMAX},
        "carto_version": carto_mod.CARTO_VERSION, "b1_map_cost": oa.B1_MAP_COST,
        "carrier": "the qualified B1 carrier (docs/b2_architecture.md D1; docs/b3_architecture.md §7)",
        "map": {"path": str(bmaps.SELF_MAP.relative_to(root)), "sha256": bmaps.sha256_of(self_map), "view": view.describe(),
                "note": "arm F's map; arm O starts empty and has no map pin"},
        "seed_derivation": {"label": SESSION_LABEL, "commit": INSTRUMENT_COMMIT, "master_seed": master,
                            "rule": "first 4 bytes of sha256(label + '|' + instrument commit); pairs from one Rng stream; the fixed excluded seeds AND every "
                                    "archived set skipped, the B3 gate's own pairs included (explicit exclusion — disjointness is enforced, not assumed)",
                            "excluded_fixed": sorted(bs.EXCLUDED_SEEDS), "excluded_sources": sources,
                            "excluded_values_total": len(exclusion | set(bs.EXCLUDED_SEEDS))},
        "gate": {"path": str(gate_report.relative_to(root)) if gate_report.is_relative_to(root) else str(gate_report), "sha256": sha256_file(gate_report),
                 "head_at_run": g["head_at_run"], "rules_version": g["rules_version"], "architecture_sha256": g["architecture_sha256"],
                 "control_x_permutation_sha256": g["control_x_permutation_sha256"],
                 "H9": "a gate diagnostic (architecture v0.3 §9): reported in the gate report, it decides nothing here"},
        "audit_policy": AUDIT_POLICY,
        "records": {"per_pair": records_per_pair(budget), "ledger_entries_per_pair": budget, "single_session_total": session_records(n_pairs, budget),
                    "note": "one opening and one closing baseline PER SESSION; the total depends on the split (session_split)"},
        "arm_order": {"sequence": list(ARM_SEQUENCE), "rule": "pair r runs sequence[r mod 6]; position counts differ by at most 1, equal exactly when N is a multiple of 3",
                      "per_pair": ["".join(arm_order(r)) for r in range(n_pairs)]},
        "session_split": session_split(n_pairs, budget, rate_measured),
        "calibration_margin": CALIBRATION_MARGIN, "session_span_max_s": SESSION_SPAN_MAX_S, "deadline_formula": DEADLINE_FORMULA,
        "planning_rates_NOT_calibration": PLANNING_RATES,
        "primary": {"statistic": "one-sided exact sign test over the N pairs' delta1 (best-so-far train fitness at the budget, online minus random-safe)",
                    "alpha": ALPHA, "ties": "excluded from n, counted", "pooled": "across sessions",
                    "pass": "p <= alpha and equal to the predicted p (preregistration v0.3 §4)",
                    "stop_rule": "if the predicted primary does not reach alpha the line stops before any canonical write; seeds are not redrawn, N is not raised"},
        "secondary_outcome": {"statistic": "the N pairs' delta2 (online at the budget minus the frozen arm's own trace at budget - 333): "
                                           "positives / negatives / ties, the exact one-sided p, mean, median, Cohen's d",
                              "pooled": "across sessions", "threshold": None,
                              "pass": "every value EXACT to the prediction; no significance threshold (preregistration v0.3 §4, the owner's ruling)"},
        "architecture": {"path": "docs/b3_architecture.md", "sha256": sha256_file(root / "docs/b3_architecture.md")},
    }


def build_qualification_plan(fid: str, map_sha256: str, b3_pairs: list, gate_report: Path = GATE_REPORT) -> dict:
    exclusion, sources = session_exclusion(gate_report)
    seeds = qualification_seeds(b3_pairs, gate_report)
    total = session_records(QUAL_PAIRS, QUAL_BUDGET)
    return {"schema": "b3_plan", "schema_version": SCHEMA_VERSION, "lifecycle": LIFECYCLE, "session": "B3Q", "fitness": fid,
            "budget_per_arm": QUAL_BUDGET, "pairs": QUAL_PAIRS, "carto_version": carto_mod.CARTO_VERSION,
            "map": {"path": str(bmaps.SELF_MAP.relative_to(REPO_ROOT)), "sha256": map_sha256},
            "seed_derivation": {"label": QUAL_LABEL, "commit": INSTRUMENT_COMMIT, "master_seed": qualification_master(),
                                "pairs": [list(x) for x in seeds], "excluded_sources": sources,
                                "excluded_b3_pairs": [list(x) for x in b3_pairs],
                                "excluded_values_total": len(exclusion | set(bs.EXCLUDED_SEEDS) | {int(s) for pair in b3_pairs for s in pair}),
                                "rule": "first 4 bytes of sha256(label|instrument commit); every archived set AND every B3 pair seed excluded"},
            "arm_order": {"sequence": list(ARM_SEQUENCE), "per_pair": ["".join(arm_order(r)) for r in range(QUAL_PAIRS)]},
            "records": {"per_pair": records_per_pair(QUAL_BUDGET), "search": 3 * QUAL_BUDGET, "holdout": 3, "ledger_entries": QUAL_BUDGET,
                        "baselines": 2, "total": total},
            "audit_policy": AUDIT_POLICY,
            "planning_bound": {"rate_per_hour": QUAL_PLANNING_RATE_PER_HOUR, "rule": QUAL_PLANNING_RATE_RULE, "deadline_formula": "1.25 x records x 3600 / rate + 600",
                               "session_timeout_s": 1.25 * total * 3600 / QUAL_PLANNING_RATE_PER_HOUR + 600},
            "note": "B3Q's frozen experiment (preregistration §6a): 120 search + 3 holdout = 123 fitness values, 40 ledger entries, 2 baselines, 125 records. "
                    "It MEASURES the all-self-reporting rate; the planning bound only bounds its own deadline and is never a calibration"}


def build_qualification_prediction(fid: str, map_sha256: str, b3_pairs: list, gate_report: Path = GATE_REPORT) -> dict:
    return build_prediction(fid, QUAL_BUDGET, qualification_seeds(b3_pairs, gate_report), map_sha256)


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def write(out: Path, plan: dict, prediction: dict) -> tuple[Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    pred_path, plan_path = out / "prediction.json", out / "plan.json"
    pred_path.write_text(json.dumps(prediction, indent=1, sort_keys=True) + "\n")
    plan = dict(plan, generated_utc=plan.get("generated_utc") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                prediction_sha256=sha256_file(pred_path))
    plan_path.write_text(json.dumps(plan, indent=1, sort_keys=True) + "\n")
    return plan_path, pred_path


def write_qualification(out: Path, plan: dict, prediction: dict) -> tuple[Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    pp, qp = out / "b3q_plan.json", out / "b3q_prediction.json"
    plan = {**plan, "prediction_sha256": sha256_json(prediction)}
    pp.write_text(json.dumps(plan, indent=1, sort_keys=True) + "\n")
    qp.write_text(json.dumps(prediction, indent=1, sort_keys=True) + "\n")
    return pp, qp


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="evidence/b3")
    ap.add_argument("--rate-per-hour", type=float, default=None, help="the B3Q-MEASURED rate (the 0.85 margin is applied here); without it the split is UNDETERMINED")
    ap.add_argument("--gate-report", default=None)
    ap.add_argument("--qualification", action="store_true", help="write B3Q's frozen experiment (b3q_plan.json, b3q_prediction.json) instead")
    a = ap.parse_args(argv)
    try:
        return run(a)
    except b3g.Refusal as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2


def run(a) -> int:
    gate_report = Path(a.gate_report) if a.gate_report else GATE_REPORT
    out = REPO_ROOT / a.out
    b3g.refuse_lifecycle1_path(out)                               # lifecycle 1's gate and trial directories: never written
    g = gate_inputs(gate_report)
    map_sha = bmaps.sha256_of(bmaps.load_self_map())
    if a.qualification:
        _m, seeds, _s, _e = session_seeds(g["pairs"], gate_report)
        qplan = build_qualification_plan(g["fitness"], map_sha, seeds, gate_report)
        qpred = build_qualification_prediction(g["fitness"], map_sha, seeds, gate_report)
        pp, qp = write_qualification(out, qplan, qpred)
        print(json.dumps({"plan": _rel(pp), "prediction": _rel(qp), "pair_seeds": qplan["seed_derivation"]["pairs"],
                          "records": qplan["records"], "deltas1": qpred["deltas1"], "deltas2": qpred["deltas2"]}, indent=1))
        return 0
    plan = build_plan(a.rate_per_hour, gate_report)
    _m, seeds, _s, _e = session_seeds(g["pairs"], gate_report)
    prediction = build_prediction(g["fitness"], g["budget_per_arm"], seeds, map_sha)
    # the stop rule BEFORE any canonical write (preregistration v0.3 §3, §8): on a stop the canonical
    # paths stay absent; only an explicit non-canonical --out may hold a trial
    findings = stop_rule_findings(prediction)
    canonical = out.resolve() == PLAN_DIR.resolve()
    summary = {"fitness": plan["fitness"], "budget_per_arm": plan["budget_per_arm"], "pairs": plan["pairs"], "master_seed": plan["seed_derivation"]["master_seed"],
               "split": plan["session_split"]["status"], "deltas1": prediction["deltas1"], "deltas2": prediction["deltas2"],
               "primary": prediction["predicted_primary"], "secondary_outcome": prediction["secondary_outcome"],
               "fitness_sequence_length": prediction["fitness_sequence_length"], "stop_rule_findings": findings}
    if findings and canonical:
        print(json.dumps({**summary, "plan": None, "prediction": None,
                          "written": f"nothing: the stop rule fired and {_rel(PLAN_DIR)} is the canonical path (a trial may write only to an explicit non-canonical --out)"}, indent=1))
        return 3
    plan_path, pred_path = write(out, plan, prediction)
    print(json.dumps({**summary, "plan": _rel(plan_path), "prediction": _rel(pred_path),
                      "written": "canonical" if canonical else "non-canonical (a trial)"}, indent=1))
    return 0 if not findings else 3


if __name__ == "__main__":
    sys.exit(main())

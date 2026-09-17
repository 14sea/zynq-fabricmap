#!/usr/bin/env python3
"""B3 lifecycle 2 — adjudication of a run's sessions: the host's recomputation from the SERVED
readouts (pure; re-runnable; nothing here touches a board). B2's `host/b2_adjudicate.py` is the
template; docs/b3_architecture.md v0.3 §8, preregistration v0.3.1 §4–§6.

    b3_adjudicate.py --run-log <run_log.json> [--run-log …] [--plan …] [--prediction …]
                     [--scope run|session] [--out …]

The sessions are consumed in session order (their declared pair slices) and inside a session in
seq order, exactly as the board produced them. Three layers, deliberately separate:

  records       `b3_records.validate_run_log` over every session (the identity 1.6.0, every
                loop_record 1.4.0, the ledger sub-block on O-arm search records only, the order,
                the counts, every ledger entry against the prediction). A session it names is
                a HOLD, and the stateful replay does not run over it at all.
  measurement   ONE finding per record, independent of every other record: the six served
                readout words; F1 over the train columns of THAT readout equals the record's
                self-reported `search.fitness`; a champion's re-measured holdout record's F1 over
                the holdout columns equals its `search.holdout`; the PL scorer's additive
                `scores` equal the additive count of the same readout; a baseline's readout is
                all-zero. A served readout contradicting a self-report is a KILL, per record.
  replay        the reference engine, fed those same served readouts, must reproduce what the
                board did in all three arms: every parent draw, move and kind, child genome,
                best-so-far and column-move counters, generation, population after selection,
                which record closed a generation, the champion, its re-measured holdout and the
                `state_sha256` of every record. For the O arm the reference cartographer is fed
                the intervention and the behaviour delta RECOMPUTED from the served child and
                parent readouts — never the board's self-reported delta, which is itself checked
                against that recomputation (a contradiction is a KILL) — and must reproduce every
                `map_version`, every `decoded`, every `map_version_after`, the running anomaly
                count and the combined search + cartographer commitment, record by record. The
                replay is STATEFUL, so it stops at the first divergence and names it. A board that
                did not follow the algorithm on its own observations is a HOLD.

Then the decode audit and the metrics against the pinned prediction: every O run's final online
map is rendered from the REPLAY's cartographer and verified (`b3_online_map.verify`, the B1 truth
mapping = the certificate, host-only, after the fact); a wrong decode the replay reproduced from
verified readouts is a KILL (preregistration §5 item 2: a certificate / fabric / model
contradiction, not an image defect — an image defect shows as a replay divergence, a HOLD); an
anomaly the replay reproduces is a HOLD (a finding about the fabric under this carrier). Per pair
and per arm the predicted values must match EXACTLY (best, holdout, column moves, champion and
move digests; F's end-to-end value; O's ledger entry by entry, its digests, its decoded count, map
version, anomalies, final commitment and online-map digest). Only the RUN scope — every
preregistered pair covered exactly once — computes the fitness-sequence digest, Δ1 = O − R with the
one-sided exact sign test (the primary), and Δ2 = O − F@(B* − 333) with the full secondary report
(no significance threshold; every value EXACT to the prediction). A SESSION scope of a longer run
never claims any of them. A B3Q plan verifies the qualification session — 123 fitness values, 40
ledger entries, two baselines, against its own prediction — and never declares a primary.

What this module is NOT. It does not verify the B3 manifest's pins or the B2 authority behind
them, the carrier's qualification chain, the instrument's rate / deadline / CRC budgets, the
evidence directory's exports or the ruling binding — the runner's and the manifest's layers, whose
absence is stated in the result. It never uses the fabric model to produce a readout: every
fitness and every delta it recomputes comes from the bytes the board served.

Outcome: PASS (no findings), HOLD (a named finding), KILL (a served readout contradicts a
self-report, or a wrong decode reproduced from verified readouts), REFUSED (the inputs are not a
run this module can adjudicate at all — a malformed plan, prediction or record document).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "host", REPO_ROOT / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_carto as carto_mod  # noqa: E402
import b3_gate as b3g  # noqa: E402
import b3_online_arm as oa  # noqa: E402
import b3_online_map as om  # noqa: E402
import b3_plan as pl  # noqa: E402
import b3_records as brec  # noqa: E402
import b3_session as bsess  # noqa: E402

TOOL_VERSION = "b3_adjudicate.py/0.1.0"
SESSIONS = ("B3", "B3Q")
LUTS = bl.LUTS
MAX_NAMED_PER_PASS = 20          # a finding per record, but a wall of them is a summary line
BLANK_GENOME = bc.genome_to_hex(0)
HEX64 = re.compile(r"[0-9a-f]{64}")
UINT32 = 1 << 32
ARMS = "RFO"
ARM_WIRE = brec.ARM_WIRE                                  # letter -> the record's arm
RUN_COUNTS = ("best_train", "champion_holdout", "column_moves")
RUN_DIGESTS = ("champion_genome_sha256", "moves_sha256")
O_COUNTS = ("budget", "ledger_entries", "decoded_final", "map_version_final", "anomalies", "wrong_decodes")
O_DIGESTS = ("ledger_sha256", "final_state_sha256", "online_map_sha256")
PRIMARY_COUNTS = ("positives", "negatives", "ties")
NOT_CHECKED_HERE = ("manifest pins and the B2 authority behind them", "carrier qualification",
                    "instrument rate / deadline / CRC budgets", "evidence exports", "ruling binding")


class Refusal(Exception):
    """The inputs are not a run this module can adjudicate — not a verdict about a board."""


def _int(v) -> bool:
    """A JSON integer. `True` is not one, and neither is 2.0."""
    return isinstance(v, int) and not isinstance(v, bool)


def _real(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _hex64(v) -> bool:
    return isinstance(v, str) and HEX64.fullmatch(v) is not None


def records_of(log: dict) -> list:
    if not isinstance(log, dict):
        return []
    recs = log.get("loop_records")
    return recs if isinstance(recs, list) else []


# ------------------------------------------------------------------ the inputs, as values


def check_plan(plan: dict) -> None:
    """The plan fields this module consumes, checked as VALUES — type first, then domain — before
    anything uses them; a wrong one is a refusal, not a finding about a board. The per-session
    context (`b3_records.context_from`) checks the rest."""
    if not isinstance(plan, dict):
        raise Refusal("the plan is not a JSON object")
    if plan.get("schema") != "b3_plan":
        raise Refusal(f"the plan's schema {plan.get('schema')!r} is not b3_plan")
    if plan.get("schema_version") != pl.SCHEMA_VERSION or plan.get("lifecycle") != pl.LIFECYCLE:
        raise Refusal(f"the plan is not schema {pl.SCHEMA_VERSION} of lifecycle {pl.LIFECYCLE} "
                      f"({plan.get('schema_version')!r}, {plan.get('lifecycle')!r})")
    if plan.get("session") not in SESSIONS:
        raise Refusal(f"the plan's session {plan.get('session')!r} is not one of {list(SESSIONS)}")
    for key in ("budget_per_arm", "fitness", "pairs", "seed_derivation", "map", "carto_version", "b1_map_cost"):
        if key not in plan:
            raise Refusal(f"the plan carries no {key!r}")
    if not _int(plan["budget_per_arm"]) or plan["budget_per_arm"] <= 0:
        raise Refusal(f"the plan's budget_per_arm {plan['budget_per_arm']!r} is not a positive integer")
    if not isinstance(plan["fitness"], str):                    # BEFORE any lookup
        raise Refusal(f"the plan's fitness {plan['fitness']!r} is not a string")
    if plan["fitness"] != bsess.PREREGISTERED_FITNESS:
        raise Refusal(f"the plan's fitness {plan['fitness']!r} is not the preregistered {bsess.PREREGISTERED_FITNESS!r}")
    if not _int(plan["pairs"]) or not (0 < plan["pairs"] <= bsess.MAX_PAIRS):
        raise Refusal(f"the plan's pairs {plan['pairs']!r} is not 1..{bsess.MAX_PAIRS}")
    if plan["session"] == "B3Q" and plan["pairs"] != pl.QUAL_PAIRS:
        raise Refusal(f"a B3Q plan has {pl.QUAL_PAIRS} pair, not {plan['pairs']}")
    if plan["session"] == "B3Q" and plan["budget_per_arm"] != pl.QUAL_BUDGET:
        raise Refusal(f"a B3Q plan runs at budget {pl.QUAL_BUDGET}, not {plan['budget_per_arm']}")
    if not isinstance(plan["map"], dict) or not _hex64(plan["map"].get("sha256")):
        raise Refusal("the plan's map sha256 is not 64 lower-case hex")
    sd = plan["seed_derivation"]
    if not isinstance(sd, dict) or not _int(sd.get("master_seed")) or not (0 <= sd["master_seed"] < UINT32):
        raise Refusal("the plan's seed_derivation carries no 32-bit master_seed")
    if plan["carto_version"] != carto_mod.CARTO_VERSION:
        raise Refusal(f"the plan's carto_version {plan['carto_version']!r} is not {carto_mod.CARTO_VERSION!r}")
    if plan["b1_map_cost"] != oa.B1_MAP_COST:
        raise Refusal(f"the plan's b1_map_cost {plan['b1_map_cost']!r} is not {oa.B1_MAP_COST}")


def check_prediction(prediction: dict, plan: dict) -> None:
    """The prediction fields this module compares against — every one typed and its domain checked
    before a comparison. The pair identities must cover the experiment exactly once IN ORDER, every
    run's values must be in domain, the deltas must account for their own runs, the primary must be
    the sign test over its own Δ1 and the secondary report the one over its own Δ2. The ledger
    entries' shape is the context's business (`b3_records.context_from`)."""
    if not isinstance(prediction, dict) or prediction.get("schema") != "b3_prediction":
        raise Refusal("the prediction is not a b3_prediction document")
    if prediction.get("schema_version") != pl.SCHEMA_VERSION or prediction.get("lifecycle") != pl.LIFECYCLE:
        raise Refusal("the prediction is not schema %s of lifecycle %s" % (pl.SCHEMA_VERSION, pl.LIFECYCLE))
    if prediction.get("fitness") != plan["fitness"]:
        raise Refusal(f"the prediction's fitness ({prediction.get('fitness')!r}) is not the plan's ({plan['fitness']!r})")
    if not _int(prediction.get("budget_per_arm")) or prediction["budget_per_arm"] != plan["budget_per_arm"]:
        raise Refusal(f"the prediction's budget_per_arm ({prediction.get('budget_per_arm')!r}) is not the plan's ({plan['budget_per_arm']!r})")
    entries = prediction.get("pairs")
    if not isinstance(entries, list) or not entries:
        raise Refusal("the prediction carries no array of pairs")
    train_ceiling = bl.CEILING[plan["fitness"]]
    holdout_ceiling = train_ceiling // bl.TRAIN_COUNT * bl.HOLDOUT_COUNT
    budget = plan["budget_per_arm"]
    ids = []
    for entry in entries:
        if not isinstance(entry, dict) or not _int(entry.get("pair")):
            raise Refusal("a prediction pair is not an object naming an integer pair")
        ids.append(entry["pair"])
    if ids != list(range(plan["pairs"])):
        raise Refusal(f"the prediction's pair identities are {ids if len(ids) <= 12 else str(ids[:12]) + '...'}, "
                      f"not the experiment's 0..{plan['pairs'] - 1} exactly once in order")
    for entry in entries:
        r = entry["pair"]
        runs = entry.get("runs")
        if not isinstance(runs, dict) or any(not isinstance(runs.get(a), dict) for a in ARMS):
            raise Refusal(f"the prediction's pair {r} carries no R, F and O run objects")
        if not _int(entry.get("base_train_fitness")) or not (0 <= entry["base_train_fitness"] <= train_ceiling):
            raise Refusal(f"the prediction's pair {r}: base_train_fitness {entry.get('base_train_fitness')!r} is not in 0..{train_ceiling}")
        for a in ARMS:
            run = runs[a]
            for k in RUN_COUNTS:
                if not _int(run.get(k)):
                    raise Refusal(f"the prediction's pair {r} arm {a}: {k} {run.get(k)!r} is not an integer")
            for k, ceiling in (("best_train", train_ceiling), ("champion_holdout", holdout_ceiling), ("column_moves", budget)):
                if not (0 <= run[k] <= ceiling):
                    raise Refusal(f"the prediction's pair {r} arm {a}: {k} {run[k]} is outside 0..{ceiling}")
            for k in RUN_DIGESTS:
                if not _hex64(run.get(k)):
                    raise Refusal(f"the prediction's pair {r} arm {a}: {k} {run.get(k)!r} is not 64 lower-case hex")
        f_run, o_run = runs["F"], runs["O"]
        if not _int(f_run.get("end_to_end_at_budget")) or not (0 <= f_run["end_to_end_at_budget"] <= train_ceiling):
            raise Refusal(f"the prediction's pair {r} arm F: end_to_end_at_budget {f_run.get('end_to_end_at_budget')!r} is not in 0..{train_ceiling}")
        for k in O_COUNTS:
            if not _int(o_run.get(k)) or o_run[k] < 0:
                raise Refusal(f"the prediction's pair {r} arm O: {k} {o_run.get(k)!r} is not a count")
        for k in O_DIGESTS:
            if not _hex64(o_run.get(k)):
                raise Refusal(f"the prediction's pair {r} arm O: {k} {o_run.get(k)!r} is not 64 lower-case hex")
        if o_run["budget"] != budget or o_run["ledger_entries"] != budget:
            raise Refusal(f"the prediction's pair {r} arm O: budget / ledger_entries {o_run['budget']} / {o_run['ledger_entries']} are not {budget}")
        if o_run.get("ledger_schema_version") != oa.LEDGER_SCHEMA_VERSION:
            raise Refusal(f"the prediction's pair {r} arm O: ledger_schema_version {o_run.get('ledger_schema_version')!r} is not {oa.LEDGER_SCHEMA_VERSION}")
        if not isinstance(o_run.get("ledger"), list) or len(o_run["ledger"]) != budget:
            raise Refusal(f"the prediction's pair {r} arm O: the ledger is not {budget} entries")
        if o_run["ledger_sha256"] != om.canonical_sha256(o_run["ledger"]):
            raise Refusal(f"the prediction's pair {r} arm O: ledger_sha256 is not the digest of its own ledger")
        check_prediction_ledger(r, o_run, budget, train_ceiling)
        for k, want in (("delta1_O_minus_R", o_run["best_train"] - runs["R"]["best_train"]),
                        ("delta2_O_minus_endtoend_F", o_run["best_train"] - f_run["end_to_end_at_budget"])):
            if not _int(entry.get(k)):
                raise Refusal(f"the prediction's pair {r}: {k} {entry.get(k)!r} is not an integer")
            if entry[k] != want:
                raise Refusal(f"the prediction's pair {r}: {k} does not account for its own runs ({want})")
    for name, key in (("deltas1", "delta1_O_minus_R"), ("deltas2", "delta2_O_minus_endtoend_F")):
        deltas = prediction.get(name)
        if not isinstance(deltas, list) or any(not _int(d) for d in deltas):
            raise Refusal(f"the prediction's {name} are not an array of integers")
        if deltas != [e[key] for e in entries]:
            raise Refusal(f"the prediction's {name} are not its pairs' {key}")
    primary = prediction.get("predicted_primary")
    if not isinstance(primary, dict):
        raise Refusal("the prediction carries no predicted_primary object")
    for k in PRIMARY_COUNTS:
        if not _int(primary.get(k)) or primary[k] < 0:
            raise Refusal(f"the prediction's primary {k} {primary.get(k)!r} is not a count")
    if sum(primary[k] for k in PRIMARY_COUNTS) != plan["pairs"]:
        raise Refusal(f"the prediction's primary counts do not account for {plan['pairs']} pairs")
    for k in ("sign_test_p", "alpha"):
        if not _real(primary.get(k)) or not (0 <= primary[k] <= 1):
            raise Refusal(f"the prediction's primary {k} {primary.get(k)!r} is not a probability")
    if primary != pl.decision(prediction["deltas1"], "online > random-safe"):
        raise Refusal("the prediction's predicted_primary is not the sign test over its own deltas1")
    secondary = prediction.get("secondary_outcome")
    if not isinstance(secondary, dict):
        raise Refusal("the prediction carries no secondary_outcome object")
    if secondary != pl.secondary_report(prediction["deltas2"]):
        raise Refusal("the prediction's secondary_outcome is not the report over its own deltas2")
    if not _hex64(prediction.get("fitness_sequence_sha256")):
        raise Refusal("the prediction's fitness_sequence_sha256 is not 64 lower-case hex")
    want_len = plan["pairs"] * pl.records_per_pair(budget)
    if not _int(prediction.get("fitness_sequence_length")) or prediction["fitness_sequence_length"] != want_len:
        raise Refusal(f"the prediction's fitness_sequence_length {prediction.get('fitness_sequence_length')!r} is not the "
                      f"{want_len} values {plan['pairs']} pairs at budget {budget} produce")


def check_prediction_ledger(r: int, o_run: dict, budget: int, train_ceiling: int) -> None:
    """The prediction's O ledger for pair r, entry by entry — the shape, the type of every value, its
    domain and the run's continuity (the rules `b3_records` holds a board's entries to) — and the
    summary's arithmetic against it: decoded_final, map_version_final and anomalies are what the
    ledger produced, wrong_decodes cannot exceed the decodes, moves_sha256 is the digest of the
    ledger's own moves. A prediction that fails here is REFUSED by name before any record is judged;
    it is never a finding about a board."""
    where0 = f"the prediction's pair {r} arm O"
    ledger = o_run["ledger"]
    after, anomalies, decoded_all, taken = 0, 0, set(), set()
    for n, e in enumerate(ledger, start=1):
        where = f"{where0} ledger entry {n}"
        if not isinstance(e, dict):
            raise Refusal(f"{where} is not a JSON object")
        if sorted(e) != sorted(brec.LEDGER_ENTRY_KEYS):
            raise Refusal(f"{where}: the keys are not exactly {list(brec.LEDGER_ENTRY_KEYS)}")
        types = brec.ledger_type_findings(e, where)
        if types:
            raise Refusal(types[0])
        bits = e["intervention"]
        if not (1 <= len(bits) <= bs.KMAX) or sorted(set(bits)) != bits or any(not (0 <= b < brec.UNIVERSE) for b in bits):
            raise Refusal(f"{where}: intervention is not 1..{bs.KMAX} distinct sorted universe indices")
        if e["move_kind"] not in ("random", "column"):
            raise Refusal(f"{where}: move_kind {e['move_kind']!r}")
        delta = [tuple(x) for x in e["behaviour_delta"]]
        if len(set(delta)) != len(delta) or any(not (0 <= k < brec.LUTS and 0 <= v < brec.VECTORS) for k, v in delta):
            raise Refusal(f"{where}: behaviour_delta is not a set of distinct (lut, vector) positions")
        if e["confidence"] != (2 if len(bits) == 1 else 1):
            raise Refusal(f"{where}: confidence {e['confidence']} is not {2 if len(bits) == 1 else 1} for a {len(bits)}-bit specimen")
        if not (0 <= e["fitness"] <= train_ceiling):
            raise Refusal(f"{where}: fitness {e['fitness']} is outside 0..{train_ceiling}")
        if e["parent_born"] < 0 or e["map_version"] < 0 or e["map_version_after"] < 0 or e["anomalies"] < 0:
            raise Refusal(f"{where}: a counter is negative")
        if e["seq"] != n:
            raise Refusal(f"{where}: seq {e['seq']} is not {n}")
        if e["map_version"] != after:
            raise Refusal(f"{where}: map_version {e['map_version']} is not the previous entry's map_version_after {after}")
        dec = [tuple(x) for x in e["decoded"]]
        addrs = [i for i, _, _ in dec]
        if len(set(addrs)) != len(addrs) or any(not (0 <= i < brec.UNIVERSE and 0 <= k < brec.LUTS and 0 <= v < brec.VECTORS) for i, k, v in dec):
            raise Refusal(f"{where}: decoded is not a set of distinct (address, lut, vector) relations")
        d_anom = e["anomalies"] - anomalies
        if d_anom not in (0, 1):
            raise Refusal(f"{where}: anomalies {anomalies} -> {e['anomalies']} (one specimen is at most one anomaly, never fewer)")
        if d_anom == 1 and (dec or e["map_version_after"] != e["map_version"]):
            raise Refusal(f"{where}: a refused specimen changes nothing else")
        if e["map_version_after"] != e["map_version"] + (1 if dec else 0):
            raise Refusal(f"{where}: map_version_after {e['map_version_after']} is not map_version {e['map_version']}"
                          f"{' + 1 for a specimen that decoded' if dec else ' for a specimen that decoded nothing'}")
        for i, k, v in dec:
            if i in decoded_all:
                raise Refusal(f"{where}: address {i} decoded twice")
            if (k, v) in taken:
                raise Refusal(f"{where}: position ({k}, {v}) taken twice")
            decoded_all.add(i)
            taken.add((k, v))
        after, anomalies = e["map_version_after"], e["anomalies"]
    want = {"decoded_final": len(decoded_all), "map_version_final": after, "anomalies": anomalies}
    for k, v in want.items():
        if o_run[k] != v:
            raise Refusal(f"{where0}: {k} {o_run[k]} is not the {v} its own ledger produces")
    if o_run["wrong_decodes"] > o_run["decoded_final"]:
        raise Refusal(f"{where0}: wrong_decodes {o_run['wrong_decodes']} exceed the {o_run['decoded_final']} decodes")
    moves = pl.sha256_json([[e["parent_born"], e["move_kind"], e["intervention"], e["fitness"]] for e in ledger])
    if o_run["moves_sha256"] != moves:
        raise Refusal(f"{where0}: moves_sha256 is not the digest of its own ledger's moves")


def structure_findings(log) -> list[str]:
    """What the record layer, the readout map and the replay need of a session document before any
    of them touches it: an object with an app_identity object and an array of record objects, each
    with an integer seq. Anything else is a malformed document — a refusal, never a finding."""
    if not isinstance(log, dict):
        return [f"a session log is {type(log).__name__}, not a JSON object"]
    if not isinstance(log.get("app_identity"), dict):
        return ["a session log carries no app_identity object"]
    recs = log.get("loop_records")
    if recs is None:
        return ["the log carries no loop_records"]
    if not isinstance(recs, list):
        return [f"loop_records is {type(recs).__name__}, not an array"]
    f = []
    for i, rec in enumerate(recs):
        if not isinstance(rec, dict):
            f.append(f"record {i + 1} is not a JSON object")
        elif not _int(rec.get("seq")):
            f.append(f"record {i + 1} carries seq {rec.get('seq')!r}, which is not an integer")
    return f


# ------------------------------------------------------------------ the served readout


def readout_words(rec: dict) -> list[int] | None:
    """The six 64-bit words the board served for THIS record, or None if the record does not carry
    them in the shape the carrier contract fixes. Never falls back to a model."""
    ev = rec.get("evidence")
    if not isinstance(ev, dict):
        return None
    score = ev.get("score")
    if not isinstance(score, dict):
        return None
    words = score.get("functional_readout")
    if not isinstance(words, list) or len(words) != LUTS:
        return None
    out = []
    for w in words:
        if not isinstance(w, str) or len(w) != 16 or any(c not in "0123456789abcdef" for c in w):
            return None
        out.append(int(w, 16))
    return out


def served_scores(rec: dict) -> list[int] | None:
    score = (rec.get("evidence") or {}).get("score") if isinstance(rec.get("evidence"), dict) else None
    if not isinstance(score, dict):
        return None
    got = score.get("scores")
    if not isinstance(got, list) or len(got) != LUTS or any(not _int(x) for x in got):
        return None
    return got


def additive_scores(tables: list[int], consts: dict) -> list[int]:
    """The PL scorer's own per-LUT count over the carrier's fixed target — the instrument's free
    per-record known answer. A pure function of the served readout."""
    n = consts["train_count"]
    vecs = consts["order"][:n]
    return [sum(1 for v in vecs if (t >> v) & 1 == (lut["target"] >> v) & 1) for t, lut in zip(tables, consts["luts"])]


def instrument_constants() -> dict:
    """The carrier constants as the INSTRUMENT holds them (the PL that produced the scores)."""
    import claimb_r1p_instrument as inst
    inst.bind(inst.DEFAULT_ROOT, require_git=False)
    import p3_oracle as po
    return po.load_constants()


# ------------------------------------------------------------------ what one session declares


@dataclass
class SessionInput:
    log: dict
    pair_first: int
    pair_count: int
    index: int = 0
    ctx: brec.Context | None = None

    @property
    def pairs(self) -> range:
        return range(self.pair_first, self.pair_first + self.pair_count)


def session_slice(log: dict) -> tuple[int, int]:
    ident = log["app_identity"]
    first, count = ident.get("pair_first"), ident.get("pair_count")
    if not _int(first) or not _int(count) or first < 0 or count <= 0:
        raise Refusal(f"a session's identity declares the slice ({first!r}, {count!r})")
    return first, count


def order_sessions(logs: list[dict]) -> list[SessionInput]:
    """Session order is the order of the pair slices; two sessions claiming one pair is a refusal."""
    sessions = []
    for log in logs:
        f = structure_findings(log)
        if f:
            raise Refusal("a session document is malformed: " + f[0])
        first, count = session_slice(log)
        sessions.append(SessionInput(log, first, count))
    sessions.sort(key=lambda s: s.pair_first)
    seen: set[int] = set()
    for i, s in enumerate(sessions):
        s.index = i
        for r in s.pairs:
            if r in seen:
                raise Refusal(f"pair {r} is claimed by two sessions")
            seen.add(r)
    return sessions


# ------------------------------------------------------------------ the per-record measurement pass


@dataclass
class Measurement:
    kills: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    checked: int = 0
    readouts: dict[tuple[int, int], list[int]] = field(default_factory=dict)   # (session, position) -> words


def measurement_pass(sessions: list[SessionInput], landscape_of, consts: dict) -> Measurement:
    """One finding per record, each independent of every other: the served readout's shape, the
    train F1 (or the holdout F1 of a champion's re-measurement) against the record's own claim, the
    additive scores, and a baseline's all-zero readout. The O arm's behaviour delta needs the
    parent's readout and is recomputed in the replay, where the parent is known."""
    m = Measurement()
    for s in sessions:
        for position, rec in enumerate(records_of(s.log)):
            seq = rec.get("seq")
            where = f"session {s.index} record {seq if _int(seq) else position + 1}"
            block = rec.get("search")
            tables = readout_words(rec)
            if tables is None:
                m.findings.append(f"{where}: no six-word functional_readout was served")
                continue
            m.readouts[(s.index, position)] = tables
            got_scores = served_scores(rec)
            if got_scores is None:
                m.findings.append(f"{where}: the record serves no six per-LUT scores")
            elif got_scores != additive_scores(tables, consts):
                m.kills.append(f"{where}: the PL's additive scores {got_scores} are not the additive count "
                               f"{additive_scores(tables, consts)} of the readout it served")
            if not isinstance(block, dict):                  # a baseline bracket
                if any(tables):
                    m.findings.append(f"{where}: a baseline's readout is not all-zero")
                continue
            pair = block.get("pair")
            if not _int(pair):
                m.findings.append(f"{where}: the block names no pair, so no landscape can be built")
                continue
            land = landscape_of(pair)
            if land is None:
                m.findings.append(f"{where}: pair {pair} is not one this run adjudicates")
                continue
            m.checked += 1
            if block.get("holdout") is not None:
                want = land.holdout_fitness(tables)
                if block["holdout"] != want:
                    m.kills.append(f"{where}: the champion's holdout {block['holdout']!r} is not {want}, "
                                   f"the holdout F1 of the readout the board served for it")
            else:
                want = land.train_fitness(tables)
                if block.get("fitness") != want:
                    m.kills.append(f"{where}: fitness {block.get('fitness')!r} is not {want}, the train F1 "
                                   f"of the readout the board served for it")
    return m


# ------------------------------------------------------------------ the replay


@dataclass
class ArmReplay:
    pair: int
    letter: str                                  # R | F | O
    best_train: int = 0
    base_fit: int = 0
    champion_genome: int = 0
    champion_born: int = 0
    champion_fit: int = 0
    champion_holdout: int | None = None
    column_moves: int = 0
    moves: list[list] = field(default_factory=list)          # R / F: [parent index, kind, bits, fitness]; O: [parent_born, kind, bits, fitness]
    fits: list[int] = field(default_factory=list)
    best_trace: list[int] = field(default_factory=list)
    population: list[bs.Individual] = field(default_factory=list)
    evals: int = 0
    generation: int = 0
    # the O arm
    ledger: list[dict] = field(default_factory=list)         # the REPLAYED entries
    carto: carto_mod.SpecimenCarto | None = None
    commitments: list[str] = field(default_factory=list)


class Divergence(Exception):
    """The board's records stopped agreeing with the reference; the replay state is now
    meaningless, so the walk ends here."""


class Replay:
    """The reference engine driven BY the records: every observation is the readout the board
    served, every decision is the reference's own, and the two are compared at each step."""

    def __init__(self, plan: dict, view: bmaps.MapView, masks: list[int], truth: dict, readouts: dict, seeds: list):
        self.budget = plan["budget_per_arm"]
        self.fid = plan["fitness"]
        self.pairs_total = plan["pairs"]
        self.seeds = [tuple(x) for x in seeds]
        self.view = view
        self.masks = masks
        self.truth = truth
        self.readouts = readouts
        self.findings: list[str] = []
        self.kills: list[str] = []
        self.arms: dict[tuple[int, str], ArmReplay] = {}
        self._land: dict[int, bl.Landscape] = {}
        self.replayed = 0
        self.train = bl.train_vectors()

    def landscape(self, pair: int) -> bl.Landscape | None:
        if not (0 <= pair < self.pairs_total):
            return None
        if pair not in self._land:
            self._land[pair] = bl.Landscape(self.fid, self.seeds[pair][0], masks=self.masks, truth=self.truth)
        return self._land[pair]

    # -------------------------------------------------- the walk

    def run(self, sessions: list[SessionInput]) -> None:
        try:
            for s in sessions:
                self._session(s)
        except Divergence as exc:
            self.findings.append(str(exc))

    def _session(self, s: SessionInput) -> None:
        self.cursor = 0
        self.recs = records_of(s.log)
        self.sindex = s.index
        base, base_pos = self._take("the opening baseline")
        base_tables = self._readout(base, base_pos)
        if base.get("search") is not None:
            raise Divergence(f"session {s.index}: the opening record carries a search block")
        if base.get("genome") != BLANK_GENOME:
            raise Divergence(f"session {s.index}: the opening baseline's genome is {_short(base.get('genome'))}, not the blank genome")
        for r in s.pairs:
            land = self.landscape(r)
            if land is None:
                raise Divergence(f"session {s.index}: pair {r} is outside the experiment's {self.pairs_total} pairs")
            order = bsess.arm_order(r)
            for a in order:
                self.arms[(r, a)] = self._online(r, land, base_tables) if a == "O" else self._search(r, a, land, base_tables)
            for a in order:
                self._holdout(r, a, land)
        closing, _ = self._take("the closing baseline")
        if closing.get("search") is not None:
            raise Divergence(f"session {s.index}: the closing record carries a search block")
        if closing.get("genome") != BLANK_GENOME:
            raise Divergence(f"session {s.index}: the closing baseline's genome is {_short(closing.get('genome'))}, not the blank genome")
        if self.cursor != len(self.recs):
            raise Divergence(f"session {s.index}: {len(self.recs) - self.cursor} records follow the closing baseline")

    def _take(self, what: str) -> tuple[dict, int]:
        if self.cursor >= len(self.recs):
            raise Divergence(f"session {self.sindex}: the records end before {what}")
        rec, position = self.recs[self.cursor], self.cursor
        self.cursor += 1
        if rec.get("outcome") != "SCORED":
            raise Divergence(f"session {self.sindex} record {rec.get('seq')}: outcome {rec.get('outcome')!r} — "
                             f"the replay stops at the first record that is not SCORED")
        return rec, position

    def _readout(self, rec: dict, position: int) -> list[int]:
        tables = self.readouts.get((self.sindex, position))
        if tables is None:
            raise Divergence(f"session {self.sindex} record {rec.get('seq')}: no served readout to replay from")
        return tables

    def _take_search(self, pair: int, letter: str, evals: int, genome: int, parent, bits, kind) -> tuple[dict, int, str]:
        rec, position = self._take(f"evaluation {evals + 1} of pair {pair} arm {letter}")
        where = f"session {self.sindex} record {rec.get('seq')} (pair {pair} arm {letter} eval {evals + 1})"
        if rec.get("arm") != ARM_WIRE[letter]:
            raise Divergence(f"{where}: the record's arm is {rec.get('arm')!r}")
        if rec.get("genome") != bc.genome_to_hex(genome):
            raise Divergence(f"{where}: the board evaluated a genome the reference would not have proposed from parent "
                             f"born {parent.born} under this move (autonomy replay failed)")
        block = rec.get("search")
        if not isinstance(block, dict):
            raise Divergence(f"{where}: a scored search record carries no search block")
        if block.get("move") != {"bits": list(bits), "kind": kind}:
            raise Divergence(f"{where}: the board's move {_short(block.get('move'))} is not the reference's "
                             f"{{'bits': {list(bits)}, 'kind': {kind!r}}}")
        if block.get("parent_born") != parent.born:
            raise Divergence(f"{where}: the board names parent born {block.get('parent_born')!r}; the reference drew born {parent.born}")
        return rec, position, where

    # -------------------------------------------------- arms R and F (B2's search, verbatim in shape)

    def _search(self, pair: int, letter: str, land: bl.Landscape, base_tables: list[int]) -> ArmReplay:
        arm = ARM_WIRE[letter]
        arm_n = 0 if letter == "R" else 1
        block_letter = brec.ARM_LETTER[arm]
        oseed = self.seeds[pair][1]
        out = ArmReplay(pair=pair, letter=letter)
        rng = bc.Rng(oseed)
        base_fit = land.train_fitness(base_tables)
        out.base_fit = base_fit
        pop = [bs.Individual(0, base_tables, base_fit, born=i) for i in range(bs.MU)]
        born, evals, best, generation, column_moves = bs.MU, 0, base_fit, 0, 0
        while evals < self.budget:
            children, pending, taken = [], [], []
            pop_before = list(pop)
            for _ in range(bs.LAMBDA):
                if evals == self.budget:
                    break
                pidx = rng.uniform(bs.MU)
                parent = pop[pidx]
                if letter == "R":
                    bits, kind = bs.random_safe_move(rng), "random"
                else:
                    bits, kind = bs.map_guided_move(rng, self.view)
                if kind == "column":
                    column_moves += 1
                genome = bs.apply_move(parent.genome, bits)
                rec, position, _where = self._take_search(pair, letter, evals, genome, parent, bits, kind)
                tables = self._readout(rec, position)
                fit = land.train_fitness(tables)
                children.append(bs.Individual(genome, tables, fit, born))
                born += 1
                evals += 1
                if fit > best:
                    best = fit
                out.fits.append(fit)
                out.best_trace.append(best)
                out.moves.append([pidx, kind, list(bits), fit])
                pending.append({"eval": evals, "fit": fit, "parent_born": parent.born, "bits": bits, "kind": kind,
                                "best": best, "column_moves": column_moves})
                taken.append(rec)
            pool = pop + children
            pool.sort(key=lambda ind: (-ind.fit, ind.born))
            pop = pool[:bs.MU]
            generation += 1
            for j, (m, rec) in enumerate(zip(pending, taken)):
                closed = (j == len(pending) - 1)
                want = bs.record_block(arm_n, block_letter, pair, land.seed, oseed, self.budget, m["eval"],
                                       generation if closed else generation - 1, m["best"], m["column_moves"],
                                       pop if closed else pop_before, m["eval"], m["fit"], m["parent_born"],
                                       m["bits"], m["kind"], closed, None)
                self._compare_block(rec, json.loads(want), pair, letter)
                self.replayed += 1
        self._finish(out, pop, evals, best, column_moves, generation)
        return out

    # -------------------------------------------------- arm O: the search AND the cartographer, from the served readouts

    def _online(self, pair: int, land: bl.Landscape, base_tables: list[int]) -> ArmReplay:
        oseed = self.seeds[pair][1]
        out = ArmReplay(pair=pair, letter="O")
        rng = bc.Rng(oseed)
        carto = carto_mod.SpecimenCarto()
        view = carto.map_view(self.train)
        base_fit = land.train_fitness(base_tables)
        out.base_fit = base_fit
        pop = [bs.Individual(0, base_tables, base_fit, born=i) for i in range(bs.MU)]
        born, evals, best, generation, column_moves = bs.MU, 0, base_fit, 0, 0
        while evals < self.budget:
            children, pending, taken = [], [], []
            pop_before = list(pop)
            for _ in range(bs.LAMBDA):
                if evals == self.budget:
                    break
                pidx = rng.uniform(bs.MU)
                parent = pop[pidx]
                bits, kind = bs.map_guided_move(rng, view)
                if kind == "column":
                    column_moves += 1
                genome = bs.apply_move(parent.genome, bits)
                rec, position, where = self._take_search(pair, "O", evals, genome, parent, bits, kind)
                block = rec["search"]
                entry = block.get("ledger")
                if not isinstance(entry, dict):
                    raise Divergence(f"{where}: an O-arm search record carries no ledger sub-block")
                tables = self._readout(rec, position)
                fit = land.train_fitness(tables)
                # the behaviour delta from the SERVED child and parent readouts — the board's own delta is a self-report
                delta = carto_mod.positions_of([tables[k] ^ parent.tables[k] for k in range(LUTS)])
                claimed = entry.get("behaviour_delta")
                if claimed != [[k, v] for k, v in delta]:
                    self.kills.append(f"{where}: the ledger's behaviour_delta {_short(claimed)} is not the child ⊕ parent readout the "
                                      f"board served, {_short([[k, v] for k, v in delta])}")
                    raise Divergence(f"{where}: the cartographer cannot be replayed past a behaviour delta the served readouts contradict")
                version_before = carto.version
                newly = carto.observe(bits, delta)
                replayed_entry = oa.ledger_entry(evals + 1, version_before, parent.born, bits, kind, delta, fit, newly, carto)
                for k in ("map_version", "decoded", "map_version_after", "anomalies"):
                    if entry.get(k) != replayed_entry[k]:
                        raise Divergence(f"{where}: the ledger's {k} is {_short(entry.get(k))}, the reference cartographer's is "
                                         f"{_short(replayed_entry[k])} (ledger replay failed)")
                if newly:
                    view = carto.map_view(self.train)
                children.append(bs.Individual(genome, tables, fit, born))
                born += 1
                evals += 1
                if fit > best:
                    best = fit
                out.fits.append(fit)
                out.best_trace.append(best)
                out.moves.append([parent.born, kind, list(bits), fit])
                out.ledger.append(replayed_entry)
                pending.append({"eval": evals, "fit": fit, "parent_born": parent.born, "bits": bits, "kind": kind,
                                "best": best, "column_moves": column_moves, "carto_text": carto.state_text(), "entry": replayed_entry})
                taken.append(rec)
            pool = pop + children
            pool.sort(key=lambda ind: (-ind.fit, ind.born))
            pop = pool[:bs.MU]
            generation += 1
            for j, (m, rec) in enumerate(zip(pending, taken)):
                closed = (j == len(pending) - 1)
                gen = generation if closed else generation - 1
                pop_at = pop if closed else pop_before
                stext = oa.search_state_text(oa.ARM_CODE, land.seed, oseed, self.budget, m["eval"], gen, m["best"], pop_at)
                commitment = oa.state_sha256(stext, m["carto_text"])
                out.commitments.append(commitment)
                want = oa.record_block(pair, land.seed, oseed, gen, m["best"], m["column_moves"], pop_at, m["eval"], m["fit"],
                                       m["parent_born"], m["bits"], m["kind"], closed, None, commitment, m["entry"])
                self._compare_block(rec, json.loads(want), pair, "O")
                self.replayed += 1
        self._finish(out, pop, evals, best, column_moves, generation)
        out.carto = carto
        return out

    def _finish(self, out: ArmReplay, pop, evals, best, column_moves, generation) -> None:
        out.best_train = best
        out.column_moves = column_moves
        out.evals = evals
        out.generation = generation
        out.population = pop
        champion = min(pop, key=lambda ind: (-ind.fit, ind.born))
        out.champion_genome = champion.genome
        out.champion_born = champion.born
        out.champion_fit = champion.fit

    # -------------------------------------------------- one champion's re-measured holdout

    def _holdout(self, pair: int, letter: str, land: bl.Landscape) -> None:
        a = self.arms[(pair, letter)]
        oseed = self.seeds[pair][1]
        rec, position = self._take(f"the champion holdout of pair {pair} arm {letter}")
        where = f"session {self.sindex} record {rec.get('seq')} (pair {pair} arm {letter} holdout)"
        if rec.get("arm") != ARM_WIRE[letter]:
            raise Divergence(f"{where}: the record's arm is {rec.get('arm')!r}")
        if rec.get("genome") != bc.genome_to_hex(a.champion_genome):
            raise Divergence(f"{where}: the board re-measured a genome that is not the champion the replayed selection left (born {a.champion_born})")
        tables = self._readout(rec, position)
        if land.train_fitness(tables) != a.champion_fit:
            self.findings.append(f"{where}: the champion's re-measured readout gives train F1 {land.train_fitness(tables)}, not the "
                                 f"{a.champion_fit} the same genome measured when it was evaluated")
        a.champion_holdout = land.holdout_fitness(tables)
        if letter == "O":
            want = oa.record_block(pair, land.seed, oseed, a.generation, a.best_train, a.column_moves, a.population, a.evals,
                                   None, None, None, None, False, a.champion_holdout, a.commitments[-1], None)
        else:
            want = bs.record_block(0 if letter == "R" else 1, brec.ARM_LETTER[ARM_WIRE[letter]], pair, land.seed, oseed, self.budget,
                                   a.evals, a.generation, a.best_train, a.column_moves, a.population, a.evals, None, None, None, None,
                                   False, a.champion_holdout)
        self._compare_block(rec, json.loads(want), pair, letter)
        self.replayed += 1

    # -------------------------------------------------- the block comparison

    def _compare_block(self, rec: dict, want: dict, pair: int, letter: str) -> None:
        got = rec.get("search")
        where = f"session {self.sindex} record {rec.get('seq')} (pair {pair} arm {letter})"
        if not isinstance(got, dict):
            raise Divergence(f"{where}: no search block to compare with the replay")
        for k in sorted(want):
            if got.get(k) != want[k]:
                if k == "ledger" and isinstance(got.get(k), dict):
                    diffs = b3g.deep_findings(want[k], got[k], "ledger")
                    raise Divergence(f"{where}: {diffs[0] if diffs else 'the ledger sub-block differs'} — the replay's entry")
                raise Divergence(f"{where}: the block's {k} is {_short(got.get(k))}, the replay's is {_short(want[k])}")
        for k in got:
            if k not in want:
                raise Divergence(f"{where}: the block carries {k!r}, which the replay does not produce for this record")


def _short(v) -> str:
    text = json.dumps(v, sort_keys=True) if not isinstance(v, str) else repr(v)
    return text if len(text) <= 72 else text[:69] + "..."


# ------------------------------------------------------------------ the decode audit and the metrics against the prediction


def online_map_of(a: ArmReplay, fid: str, budget: int, seeds: tuple[int, int]) -> dict:
    """Every O run's final online map, rendered from the REPLAY's cartographer and the replayed ledger."""
    return om.render(a.carto, {"landscape_seed": seeds[0], "operator_seed": seeds[1], "fitness": fid, "budget": budget}, a.ledger)


def decode_audit(arms: dict, pairs: list[int], fid: str, budget: int, seeds: list, truth: dict) -> tuple[list[str], list[str], dict]:
    """The decode audit (architecture §8 items 5–6; preregistration §5 item 2) over the REPLAYED
    cartographer: the online map verified against the certificate. Returns (kills, findings, maps).
    A wrong decode here was reproduced by the reference from readouts the measurement pass verified
    — a certificate / fabric / model contradiction: KILL. A reproduced anomaly is a HOLD."""
    kills, findings, maps = [], [], {}
    for r in pairs:
        a = arms[(r, "O")]
        doc = online_map_of(a, fid, budget, seeds[r])
        maps[r] = doc
        v = om.verify(doc, a.ledger, truth)
        acc = v["accuracy"] or {}
        for gb in acc.get("wrong_entries", []):
            e = next(x for x in doc["entries"] if x["genome_bit"] == gb)
            kills.append(f"pair {r} arm O: wrong decode reproduced from verified readouts — address {gb} at "
                         f"({e['relation']['lut_index']}, {e['relation']['init_index']}), the certificate says {tuple(truth['mapping'][gb])}: "
                         f"a certificate / fabric / model contradiction (preregistration §5 item 2)")
        if a.carto.anomalies:
            findings.append(f"pair {r} arm O: {a.carto.anomalies} anomaly(ies) reproduced by the reference cartographer from the served "
                            f"readouts — a finding about the fabric under this carrier (predicted 0)")
        for x in v["findings"]:
            if not x.startswith("wrong decode") and not x.startswith("anomalies "):
                findings.append(f"pair {r} arm O: the online map does not verify: {x}")
    return kills, findings, maps


def prediction_findings(arms: dict, prediction: dict, pairs_covered: list[int], maps: dict, budget: int, truth: dict) -> list[str]:
    """Per pair and per arm, every predicted value the prediction carries. `truth` is the ONE
    certificate snapshot the adjudication read (the decode audit used the same one)."""
    f: list[str] = []
    by_pair = {p["pair"]: p for p in prediction["pairs"]}
    for r in pairs_covered:
        want_pair = by_pair[r]
        for letter in ARMS:
            a = arms.get((r, letter))
            want = want_pair["runs"][letter]
            if a is None:
                f.append(f"pair {r} arm {letter}: nothing was replayed for it")
                continue
            got = {"best_train": a.best_train, "champion_holdout": a.champion_holdout, "column_moves": a.column_moves,
                   "champion_genome_sha256": hashlib.sha256(bc.genome_to_hex(a.champion_genome).encode()).hexdigest(),
                   "moves_sha256": pl.sha256_json(a.moves)}
            if letter == "F":
                got["end_to_end_at_budget"] = oa.end_to_end_frozen(a.best_trace, a.base_fit, budget)
            if letter == "O":
                doc = maps[r]
                got.update({"budget": budget, "ledger_entries": len(a.ledger), "ledger_sha256": om.canonical_sha256(a.ledger),
                            "decoded_final": len(a.carto.decoded), "map_version_final": a.carto.version, "anomalies": a.carto.anomalies,
                            "wrong_decodes": om.accuracy(doc, truth)["wrong"],
                            "final_state_sha256": a.commitments[-1], "online_map_sha256": om.canonical_sha256(doc)})
            for k in got:
                if got[k] != want.get(k):
                    f.append(f"pair {r} arm {letter}: {k} is {_short(got[k])}, the prediction's is {_short(want.get(k))}")
            if letter == "O":
                f += [f"pair {r} arm O: {x} — the replayed ledger against the prediction's" for x in
                      b3g.deep_findings(want["ledger"], a.ledger, "ledger")[:3]]
        if want_pair.get("base_train_fitness") != arms[(r, "R")].base_fit:
            f.append(f"pair {r}: the base train fitness is {arms[(r, 'R')].base_fit}, the prediction's is {want_pair.get('base_train_fitness')}")
    return f


def fitness_sequence(arms: dict, pairs: list[int]) -> list[int]:
    """The run's fitness sequence in the preregistered order: per pair, the three arms' evaluation
    fitnesses in the pair's arm order, then the three champions' holdout values."""
    seq: list[int] = []
    for r in pairs:
        order = bsess.arm_order(r)
        for a in order:
            seq.extend(arms[(r, a)].fits)
        for a in order:
            seq.append(arms[(r, a)].champion_holdout)
    return seq


def deltas_of(arms: dict, pairs: list[int], budget: int) -> tuple[list[int], list[int]]:
    d1 = [arms[(r, "O")].best_train - arms[(r, "R")].best_train for r in pairs]
    d2 = [arms[(r, "O")].best_train - oa.end_to_end_frozen(arms[(r, "F")].best_trace, arms[(r, "F")].base_fit, budget) for r in pairs]
    return d1, d2


# ------------------------------------------------------------------ the adjudication


def adjudicate(logs: list[dict], plan: dict, prediction: dict, consts: dict | None = None,
               common: bool = True, scope: str = "run") -> dict:
    """`logs` are the run's session logs in any order — ordered here by their declared pair slices.
    `consts` defaults to the INSTRUMENT's carrier constants; pass them only to test this module.

    `scope` is "run" — the whole experiment, which must cover every preregistered pair exactly once
    and which is the only scope that reports the fitness-sequence digest, Δ1 / Δ2, the primary and
    the secondary report — or "session", one or more sessions of a longer run, where covering a
    subset is the point and NOT a finding, and none of those is ever claimed. A B3Q plan verifies
    the qualification session and never declares a primary under either scope."""
    out = {"tool": TOOL_VERSION, "session": None, "scope": scope, "outcome": None, "findings": [], "kills": [],
           "not_checked_here": list(NOT_CHECKED_HERE)}
    try:
        if scope not in ("run", "session"):
            raise Refusal(f"scope {scope!r} is neither 'run' nor 'session'")
        if not logs:
            raise Refusal("no session log was given")
        check_plan(plan)
        out["session"] = plan["session"]
        check_prediction(prediction, plan)
        sessions = order_sessions(logs)
        for s in sessions:
            try:
                s.ctx = brec.context_from(plan, prediction, s.pair_first, s.pair_count)
            except brec.ContextError as exc:
                raise Refusal(f"session {s.index}: {exc}") from None
        consts = consts if consts is not None else instrument_constants()
        seeds = sessions[0].ctx.seeds                              # the prediction's, the same for every session
        truth = bm.truth_mapping()
        masks = bl.universe_mask(truth)
        view = bmaps.MapView(bmaps.load_self_map(), bl.train_vectors())
        rp = Replay(plan, view, masks, truth, {}, seeds)

        findings: list[str] = []
        refused_sessions: list[int] = []
        for s in sessions:                                   # the record layer, session by session
            f = brec.validate_run_log(s.log, s.ctx, common=common)
            findings += [f"session {s.index}: {x}" for x in _capped(f, "record-layer")]
            if f:
                refused_sessions.append(s.index)

        m = measurement_pass(sessions, rp.landscape, consts)
        rp.readouts = m.readouts

        covered = sorted(r for s in sessions for r in s.pairs)
        out["sessions"] = [{"index": s.index, "pair_first": s.pair_first, "pair_count": s.pair_count,
                            "records": len(records_of(s.log))} for s in sessions]
        out["measurement"] = {"records_checked": m.checked, "readouts_served": len(m.readouts)}
        out["pair_seeds"] = [list(x) for x in seeds]
        findings += _capped(m.findings, "measurement")
        kills = list(m.kills)

        if refused_sessions:
            out["replay"] = {"not_run": f"the record layer refused session(s) {refused_sessions}; a stateful replay over "
                                        f"records it named proves nothing about the board"}
        else:
            rp.run(sessions)
            out["replay"] = {"records_replayed": rp.replayed, "pairs": covered}
            findings += rp.findings
            kills += rp.kills

        qualification = plan["session"] == "B3Q"
        complete = covered == list(range(plan["pairs"]))
        if scope == "run" and not complete:
            findings.append(f"the sessions cover pairs {covered}, not the preregistered {list(range(plan['pairs']))}: "
                            f"no primary is computed from a partial run")
        replayed_all = not refused_sessions and not rp.findings and not rp.kills and \
            all((r, a) in rp.arms and rp.arms[(r, a)].champion_holdout is not None for r in covered for a in ARMS)
        budget = plan["budget_per_arm"]
        maps: dict = {}
        if replayed_all:                                     # the decode audit is the last source of kills
            k2, f2, maps = decode_audit(rp.arms, covered, plan["fitness"], budget, seeds, truth)
            kills += k2
            findings += f2
        # Every kill — measurement, replay, decode audit — is now collected. Nothing derived (the online
        # maps, the qualification block, the digest, the deltas, the primary, the secondary report, the
        # comparison with the prediction) is published once anything was killed (the owner's P2 on 537c144).
        if replayed_all and not kills:
            out["online_maps"] = {str(r): {"decoded": len(rp.arms[(r, 'O')].carto.decoded), "map_version": rp.arms[(r, 'O')].carto.version,
                                           "anomalies": rp.arms[(r, 'O')].carto.anomalies, "sha256": om.canonical_sha256(maps[r])} for r in covered}
            findings += prediction_findings(rp.arms, prediction, covered, maps, budget, truth)
            if qualification and complete:
                seq = fitness_sequence(rp.arms, covered)
                out["qualification"] = {"fitness_values": len(seq), "ledger_entries": sum(len(rp.arms[(r, "O")].ledger) for r in covered),
                                        "baselines": 2 * len(sessions), "fitness_sequence_sha256": pl.sha256_json(seq)}
                if pl.sha256_json(seq) != prediction["fitness_sequence_sha256"] or len(seq) != prediction["fitness_sequence_length"]:
                    findings.append("the qualification session's fitness values do not hash to the preregistered sequence")
            elif scope == "run" and complete:
                seq = fitness_sequence(rp.arms, covered)
                out["fitness_sequence_length"] = len(seq)
                out["fitness_sequence_sha256"] = pl.sha256_json(seq)
                if out["fitness_sequence_sha256"] != prediction["fitness_sequence_sha256"]:
                    findings.append("the run's fitness sequence does not hash to the preregistered one")
                if len(seq) != prediction["fitness_sequence_length"]:
                    findings.append(f"the run's fitness sequence is {len(seq)} values, the prediction's {prediction['fitness_sequence_length']}")
                d1, d2 = deltas_of(rp.arms, covered, budget)
                out["deltas1"] = d1
                out["deltas2"] = d2
                out["primary"] = pl.decision(d1, "online > random-safe")
                out["secondary_outcome"] = pl.secondary_report(d2)
                if d1 != prediction["deltas1"]:
                    findings.append("the run's per-pair delta1 values are not the preregistered ones")
                if d2 != prediction["deltas2"]:
                    findings.append("the run's per-pair delta2 values are not the preregistered ones")
                if out["primary"] != prediction["predicted_primary"]:
                    findings.append(f"the run's primary {out['primary']} is not the preregistered {prediction['predicted_primary']}")
                if out["secondary_outcome"] != prediction["secondary_outcome"]:
                    findings.append("the run's secondary outcome report is not the preregistered one (reported, EXACT; no threshold)")
        out["findings"] = findings
        out["kills"] = _capped(kills, "measurement / audit")
        if out["kills"]:
            out["outcome"] = "KILL: " + "; ".join(out["kills"][:4])
        elif findings:
            out["outcome"] = "HOLD: " + "; ".join(findings[:6])
        else:
            out["outcome"] = "PASS"
    except Refusal as exc:
        out["outcome"] = f"REFUSED: {exc}"
        out["refusal"] = str(exc)
    return out


def _capped(items: list[str], what: str) -> list[str]:
    if len(items) <= MAX_NAMED_PER_PASS:
        return list(items)
    return items[:MAX_NAMED_PER_PASS] + [f"... and {len(items) - MAX_NAMED_PER_PASS} more {what} findings"]


# ------------------------------------------------------------------ the command line


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-log", type=Path, action="append", default=[], help="one session's run_log.json; repeat for a multi-session run")
    ap.add_argument("--evidence", type=Path, action="append", default=[], help="an evidence directory holding run_log.json")
    ap.add_argument("--plan", type=Path, default=pl.PLAN_DIR / "plan.json")
    ap.add_argument("--prediction", type=Path, default=pl.PLAN_DIR / "prediction.json")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-common", action="store_true", help="skip the instrument's common validator")
    ap.add_argument("--scope", choices=("run", "session"), default="run",
                    help="'run' (default) is the whole experiment and the only scope that reports a primary; "
                         "'session' adjudicates one or more sessions of a longer run")
    a = ap.parse_args(argv)
    paths = list(a.run_log) + [d / "run_log.json" for d in a.evidence]
    if not paths:
        print("no --run-log and no --evidence", file=sys.stderr)
        return 2

    def load(path: Path):
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise Refusal(f"{path} is not readable JSON: {exc}") from None

    try:
        res = adjudicate([load(p) for p in paths], load(a.plan), load(a.prediction), common=not a.no_common, scope=a.scope)
    except Refusal as exc:
        res = {"tool": TOOL_VERSION, "session": None, "outcome": f"REFUSED: {exc}", "refusal": str(exc), "findings": [], "kills": []}
    except Exception as exc:              # a defect in THIS module: not an input refusal, but the result is still written
        import traceback
        res = {"tool": TOOL_VERSION, "session": None, "outcome": f"INTERNAL ERROR: {type(exc).__name__}: {exc}",
               "internal_error": traceback.format_exc(), "findings": [], "kills": []}
    res["inputs"] = [str(p) for p in paths]
    text = json.dumps(res, indent=2, sort_keys=True)
    if a.out:
        a.out.write_text(text + "\n")
    print(text)
    if "internal_error" in res:
        return 3
    return 0 if res["outcome"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

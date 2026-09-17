#!/usr/bin/env python3
"""B3 lifecycle 2 — the record validator: everything the instrument's validator does NOT check
(B2's `host/b2_records.py` is the template; docs/b3_architecture.md v0.3 §7, preregistration v0.3.1 §2
"records" and §4).

The instrument's validator (`host/b1_records.py`) checks the common envelope and ignores unknown
extension fields, so every B3 field and every cross-record binding is checked here. Three layers,
each a pure function returning NAMED findings (empty = nothing to report), plus the context they need:

  context_from        the frozen experiment of ONE session from the committed plan and prediction
                      documents (`b3_plan` 2.0.0): the seeds, the budget, the arm order per pair and,
                      for every pair, the predicted O-arm ledger (every entry) and the predicted final
                      state commitment. A plan or prediction that is not the shape this module reads
                      is a `ContextError` (a refusal of the inputs, never a finding about a board).
  identity_findings   `app_identity` 1.6.0: B2's 1.5.0 fields (engine, map digest, fitness, budget,
                      slice, master seed, carrier) plus `carto_version`, `arms` ("RFO") and
                      `b1_map_cost` (333); `probe_budget` must be ABSENT (this image issues no probe).
  record_findings     one `loop_record` 1.4.0 against what the order says it must be: B2's `search`
                      block, its exact shape and every value that must agree with the session — and
                      the `ledger` sub-block (one `specimen_ledger` 1.1.0 entry) that an O-arm SEARCH
                      record must carry and that no other record may carry: not an O champion's
                      holdout record (it evaluates a finished genome and does not update the map), not
                      an R / F search record, not a holdout, not a baseline. On an O-arm search record
                      the entry is bound to the block (seq = eval, intervention = the move's bits,
                      move_kind = the move's kind, fitness, parent), to the run's continuity (the
                      map version chains entry to entry, the version bumps exactly on a decode, the
                      anomaly count runs and an anomaly changes nothing else, no address decoded twice,
                      no position taken twice) and — field for field — to the prediction's entry for
                      that evaluation; the record's `state_sha256` (the search + cartographer combined
                      commitment, architecture §7) must equal the predicted final commitment on the
                      last search record and on the champion's holdout record.
  session_findings    the whole run: the candidate ORDER the orchestrator must have produced for the
                      declared slice (opening baseline; per pair the three searches in the pair's
                      prefix-balanced order, then the three champions' holdout evaluations in the same
                      order; closing baseline), the record count, the seq run, the per-run evaluation
                      and ledger-entry counts, and that the identity's slice is the one the records use.

Every value's JSON TYPE is checked before anything compares, indexes, sorts, hashes or counts it
(`identity_type_findings`, `block_type_findings`, `ledger_type_findings`): a malformed document comes
back as a named finding, never as an incidental Python exception, and a JSON boolean is never an
integer (B2's rule). `validate_run_log` runs the instrument's common validation first and then all
three layers. It is a validator, not the adjudicator: it never recomputes a fitness or a behaviour
delta from a readout and never replays a search or the ledger — that is the adjudicator's work
(architecture §8), and this module deliberately does not pretend to do it.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "host", REPO_ROOT / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b2_search as bs  # noqa: E402
import b3_carto as carto_mod  # noqa: E402
import b3_gate as b3g  # noqa: E402
import b3_online_arm as oa  # noqa: E402
import b3_plan as pl  # noqa: E402

IDENTITY_SCHEMA_VERSION = "1.6.0"
RECORD_SCHEMA_VERSION = "1.4.0"
LEDGER_SCHEMA_VERSION = oa.LEDGER_SCHEMA_VERSION            # "1.1.0"
PLAN_SCHEMA_VERSION = pl.SCHEMA_VERSION                      # "2.0.0"
LIFECYCLE = pl.LIFECYCLE
BLOCK_KEYS = ("arm", "best", "column_moves", "eval", "fitness", "generation", "holdout",
              "landscape_seed", "move", "operator_seed", "pair", "parent_born", "population",
              "selected", "state_sha256", "version")
LEDGER_KEY = "ledger"
LEDGER_ENTRY_KEYS = ("seq", "map_version", "parent_born", "intervention", "move_kind", "behaviour_delta",
                     "fitness", "confidence", "decoded", "map_version_after", "anomalies")
IDENTITY_B2_KEYS = ("search_version", "map_sha256", "fitness_id", "budget_per_arm",
                    "pairs_total", "pair_first", "pair_count")
IDENTITY_B3_KEYS = ("carto_version", "arms", "b1_map_cost")
IDENTITY_FORBIDDEN = ("probe_budget",)
ARMS = "RFO"
ARM_WIRE = {"R": bs.ARM_RANDOM_SAFE, "F": bs.ARM_MAP_GUIDED, "O": oa.ARM_ONLINE}       # letter -> the record's `arm`
ARM_LETTER = {bs.ARM_RANDOM_SAFE: "A", bs.ARM_MAP_GUIDED: "B", oa.ARM_ONLINE: oa.ARM_LETTER}   # the record's `arm` -> the block's letter
WIRE_TEXT = {bs.ARM_RANDOM_SAFE: "random-safe", bs.ARM_MAP_GUIDED: "frozen-map", oa.ARM_ONLINE: "online"}
# Matched with fullmatch(), never match(): Python's `$` also matches before a final newline, so
# `^...$` accepts a 65-character digest (B2, the owner's P3 of 2026-09-11).
HEX64 = re.compile(r"[0-9a-f]{64}")
CARRIER_VARIANT = "0x42310001"
UNIVERSE = 292
LUTS, VECTORS = 6, 64
SEED_MAX = 0xFFFFFFFF


class ContextError(ValueError):
    """The plan or the prediction is not the shape this module reads: a refusal of the inputs."""


def _int(v) -> bool:
    """A JSON integer. `True` is not one, whatever `isinstance(True, int)` says."""
    return isinstance(v, int) and not isinstance(v, bool)


def _str(v) -> bool:
    return isinstance(v, str)


def _bool(v) -> bool:
    return isinstance(v, bool)


def _int_or_null(v) -> bool:
    return v is None or _int(v)


def _int_list(v) -> bool:
    return isinstance(v, list) and all(_int(x) for x in v)


def _int_pairs(v) -> bool:
    return isinstance(v, list) and all(isinstance(x, list) and len(x) == 2 and all(_int(y) for y in x) for x in v)


def _int_triples(v) -> bool:
    return isinstance(v, list) and all(isinstance(x, list) and len(x) == 3 and all(_int(y) for y in x) for x in v)


# (field, predicate, what it must be) — the JSON type of every value this module reads.
IDENTITY_TYPES = (("schema_version", _str, "a string"), ("search_version", _str, "a string"),
                  ("map_sha256", _str, "a string"), ("operator_data_sha256", _str, "a string"),
                  ("fitness_id", _str, "a string"), ("carrier_variant", _str, "a string"),
                  ("protocol", _str, "a string"), ("control_plane", _str, "a string"),
                  ("budget_per_arm", _int, "an integer"), ("master_seed", _int, "an integer"),
                  ("pairs_total", _int, "an integer"), ("pair_first", _int, "an integer"),
                  ("pair_count", _int, "an integer"),
                  ("carto_version", _str, "a string"), ("arms", _str, "a string"), ("b1_map_cost", _int, "an integer"))
BLOCK_TYPES = (("version", _str, "a string"), ("arm", _str, "a string"),
               ("state_sha256", _str, "a string"), ("pair", _int, "an integer"),
               ("eval", _int, "an integer"), ("best", _int, "an integer"),
               ("column_moves", _int, "an integer"), ("generation", _int, "an integer"),
               ("landscape_seed", _int, "an integer"), ("operator_seed", _int, "an integer"),
               ("selected", _bool, "a boolean"), ("holdout", _int_or_null, "an integer or null"),
               ("fitness", _int_or_null, "an integer or null"),
               ("parent_born", _int_or_null, "an integer or null"))
LEDGER_TYPES = (("seq", _int, "an integer"), ("map_version", _int, "an integer"),
                ("parent_born", _int, "an integer"), ("move_kind", _str, "a string"),
                ("fitness", _int, "an integer"), ("confidence", _int, "an integer"),
                ("map_version_after", _int, "an integer"), ("anomalies", _int, "an integer"),
                ("intervention", _int_list, "a list of integers"),
                ("behaviour_delta", _int_pairs, "a list of [lut, vector] integer pairs"),
                ("decoded", _int_triples, "a list of [address, lut, vector] integer triples"))


@dataclass(frozen=True)
class Context:
    """What the session was supposed to be: the frozen experiment plus this session's slice, and the
    prediction every O-arm ledger entry and commitment is held to."""
    master_seed: int
    budget: int
    pairs_total: int
    pair_first: int
    pair_count: int
    fitness: str
    map_sha256: str
    pair_seeds: tuple[tuple[int, int], ...]
    prediction: dict = field(repr=False, compare=False)
    engine: str = bs.ENGINE_VERSION
    carto_version: str = carto_mod.CARTO_VERSION
    b1_map_cost: int = oa.B1_MAP_COST
    arms: str = ARMS

    @property
    def seeds(self) -> list[tuple[int, int]]:
        """The pairs' seeds, as the committed plan / prediction carry them — the derivation and its
        exclusion sets are the plan tool's and are re-derived by `plan_findings` at S3, not here."""
        return [tuple(x) for x in self.pair_seeds]

    @property
    def records(self) -> int:
        return pl.session_records(self.pair_count, self.budget)

    def predicted_o(self, pair: int) -> dict:
        return self.prediction["pairs"][pair]["runs"]["O"]


def arm_order(pair: int) -> tuple[str, ...]:
    """The pair's arm letters in the frozen prefix-balanced order (b3_plan.ARM_SEQUENCE[r mod 6])."""
    return pl.arm_order(pair)


def context_from(plan: dict, prediction: dict, pair_first: int, pair_count: int) -> Context:
    """The context of ONE session from the committed plan and prediction (`b3_plan` 2.0.0 documents,
    B3 or B3Q). Every value this module later reads is checked here as a VALUE — type first, then
    domain — and a wrong one is a `ContextError` naming it: the seeds, the budget, the arm order and
    the predicted O-arm ledgers are what the records are held to, so a malformed input is refused
    before any record is judged."""
    def need(doc, key, ok, what, where):
        if not isinstance(doc, dict) or key not in doc:
            raise ContextError(f"{where}: no {key!r}")
        if not ok(doc[key]):
            raise ContextError(f"{where}: {key} is not {what}")
        return doc[key]

    if not isinstance(plan, dict):
        raise ContextError("the plan is not a JSON object")
    if not isinstance(prediction, dict):
        raise ContextError("the prediction is not a JSON object")
    if plan.get("schema") != "b3_plan":
        raise ContextError(f"the plan's schema {plan.get('schema')!r} is not b3_plan")
    if prediction.get("schema") != "b3_prediction":
        raise ContextError(f"the prediction's schema {prediction.get('schema')!r} is not b3_prediction")
    for name, doc in (("the plan", plan), ("the prediction", prediction)):
        if doc.get("schema_version") != PLAN_SCHEMA_VERSION:
            raise ContextError(f"{name}'s schema_version {doc.get('schema_version')!r} is not {PLAN_SCHEMA_VERSION}")
        if doc.get("lifecycle") != LIFECYCLE:
            raise ContextError(f"{name}'s lifecycle {doc.get('lifecycle')!r} is not {LIFECYCLE}")
    budget = need(plan, "budget_per_arm", _int, "an integer", "the plan")
    if budget <= 0:
        raise ContextError(f"the plan's budget_per_arm {budget} is not positive")
    fitness = need(plan, "fitness", _str, "a string", "the plan")
    pairs_total = need(plan, "pairs", _int, "an integer", "the plan")
    if pairs_total <= 0:
        raise ContextError(f"the plan's pairs {pairs_total} is not positive")
    master = need(need(plan, "seed_derivation", lambda v: isinstance(v, dict), "an object", "the plan"),
                  "master_seed", _int, "an integer", "the plan's seed_derivation")
    map_sha = need(need(plan, "map", lambda v: isinstance(v, dict), "an object", "the plan"),
                   "sha256", _str, "a string", "the plan's map")
    if not HEX64.fullmatch(map_sha):
        raise ContextError("the plan's map sha256 is not 64 hex")
    carto_version = need(plan, "carto_version", _str, "a string", "the plan")
    b1_map_cost = need(plan, "b1_map_cost", _int, "an integer", "the plan")
    if prediction.get("fitness") != fitness:
        raise ContextError(f"the prediction's fitness {prediction.get('fitness')!r} is not the plan's {fitness!r}")
    if prediction.get("budget_per_arm") != budget:
        raise ContextError(f"the prediction's budget_per_arm {prediction.get('budget_per_arm')!r} is not the plan's {budget}")
    if prediction.get("carto_version") != carto_version:
        raise ContextError(f"the prediction's carto_version {prediction.get('carto_version')!r} is not the plan's {carto_version!r}")
    if prediction.get("b1_map_cost") != b1_map_cost:
        raise ContextError(f"the prediction's b1_map_cost {prediction.get('b1_map_cost')!r} is not the plan's {b1_map_cost}")
    ppairs = need(prediction, "pairs", lambda v: isinstance(v, list), "a list", "the prediction")
    if len(ppairs) != pairs_total:
        raise ContextError(f"the prediction has {len(ppairs)} pairs, the plan {pairs_total}")
    seeds: list[tuple[int, int]] = []
    for r, pp in enumerate(ppairs):
        where = f"the prediction's pair {r}"
        if not isinstance(pp, dict):
            raise ContextError(f"{where} is not a JSON object")
        if need(pp, "pair", _int, "an integer", where) != r:
            raise ContextError(f"{where} carries pair {pp['pair']}")
        l_seed = need(pp, "landscape_seed", _int, "an integer", where)
        o_seed = need(pp, "operator_seed", _int, "an integer", where)
        if not (0 <= l_seed <= SEED_MAX and 0 <= o_seed <= SEED_MAX):
            raise ContextError(f"{where}: a seed is outside 0..2^32-1")
        order = need(pp, "arm_order", lambda v: isinstance(v, list) and all(_str(x) for x in v), "a list of strings", where)
        if tuple(order) != arm_order(r):
            raise ContextError(f"{where}: arm_order {order} is not the frozen sequence's {''.join(arm_order(r))}")
        runs = need(pp, "runs", lambda v: isinstance(v, dict), "an object", where)
        for a in ARMS:
            if not isinstance(runs.get(a), dict):
                raise ContextError(f"{where}: no run for arm {a}")
        o = runs["O"]
        if need(o, "budget", _int, "an integer", f"{where}'s O run") != budget:
            raise ContextError(f"{where}'s O run: budget {o['budget']} is not {budget}")
        if need(o, "ledger_schema_version", _str, "a string", f"{where}'s O run") != LEDGER_SCHEMA_VERSION:
            raise ContextError(f"{where}'s O run: ledger_schema_version {o['ledger_schema_version']!r} is not {LEDGER_SCHEMA_VERSION}")
        ledger = need(o, "ledger", lambda v: isinstance(v, list) and all(isinstance(e, dict) for e in v),
                      "a list of objects", f"{where}'s O run")
        if len(ledger) != budget:
            raise ContextError(f"{where}'s O run: {len(ledger)} ledger entries, the budget is {budget}")
        final = need(o, "final_state_sha256", _str, "a string", f"{where}'s O run")
        if not HEX64.fullmatch(final):
            raise ContextError(f"{where}'s O run: final_state_sha256 is not 64 hex")
        seeds.append((l_seed, o_seed))
    if not _int(pair_first) or not _int(pair_count) or pair_first < 0 or pair_count <= 0 or pair_first + pair_count > pairs_total:
        raise ContextError(f"the slice ({pair_first}, {pair_count}) does not lie inside the experiment's {pairs_total} pairs")
    return Context(master_seed=master, budget=budget, pairs_total=pairs_total, pair_first=pair_first,
                   pair_count=pair_count, fitness=fitness, map_sha256=map_sha, pair_seeds=tuple(seeds),
                   prediction=prediction, carto_version=carto_version, b1_map_cost=b1_map_cost)


def expected_order(ctx: Context) -> list[tuple[int, str, bool] | None]:
    """The candidate order the orchestrator must produce: None for each baseline bracket, and
    (pair, arm, holdout) for every other candidate, in sequence — per pair the three searches in
    the pair's prefix-balanced order, then the three champions' holdout evaluations in that order."""
    out: list[tuple[int, str, bool] | None] = [None]
    for i in range(ctx.pair_count):
        r = ctx.pair_first + i
        order = arm_order(r)
        for a in order:
            out += [(r, ARM_WIRE[a], False)] * ctx.budget
        for a in order:
            out.append((r, ARM_WIRE[a], True))
    out.append(None)
    return out


# ------------------------------------------------------------------ the identity


def identity_type_findings(ident: dict) -> list[str]:
    """The JSON type of every identity field that is PRESENT; an absent one is the presence
    check's business, not this one's."""
    return [f"identity: {k} is not {what}" for k, ok, what in IDENTITY_TYPES
            if k in ident and not ok(ident[k])]


def identity_findings(ident: dict, ctx: Context) -> list[str]:
    f: list[str] = []
    if not isinstance(ident, dict):
        return ["identity: not a JSON object"]
    if ident.get("schema") != "app_identity":
        return ["identity: not an app_identity"]
    if ident.get("schema_version") != IDENTITY_SCHEMA_VERSION:
        f.append(f"identity: schema_version {ident.get('schema_version')!r} is not {IDENTITY_SCHEMA_VERSION}")
    for k in IDENTITY_B2_KEYS:
        if k not in ident:
            f.append(f"identity: the B2 field {k!r} is absent")
    for k in IDENTITY_B3_KEYS:
        if k not in ident:
            f.append(f"identity: the B3 field {k!r} is absent")
    for k in IDENTITY_FORBIDDEN:
        if k in ident:
            f.append(f"identity: {k!r} is declared, but this image issues no probes (the online map is built from specimens)")
    types = identity_type_findings(ident)
    if types:                     # nothing below may compare or add a value of unknown type
        return f + types
    if ident.get("search_version") != ctx.engine:
        f.append(f"identity: search_version {ident.get('search_version')!r} is not {ctx.engine!r}")
    if ident.get("map_sha256") != ctx.map_sha256:
        f.append("identity: map_sha256 is not the map arm F is bound to")
    if ident.get("operator_data_sha256") != ctx.map_sha256:
        f.append("identity: operator_data_sha256 must be the map digest")
    if ident.get("fitness_id") != ctx.fitness:
        f.append(f"identity: fitness_id {ident.get('fitness_id')!r} is not {ctx.fitness!r}")
    if ident.get("budget_per_arm") != ctx.budget:
        f.append(f"identity: budget_per_arm {ident.get('budget_per_arm')!r} is not {ctx.budget}")
    if ident.get("master_seed") != ctx.master_seed:
        f.append("identity: master_seed is not the frozen one")
    if ident.get("pairs_total") != ctx.pairs_total:
        f.append(f"identity: pairs_total {ident.get('pairs_total')!r} is not the preregistered {ctx.pairs_total}")
    first, count = ident.get("pair_first"), ident.get("pair_count")
    if (first, count) != (ctx.pair_first, ctx.pair_count):
        f.append(f"identity: the pair slice ({first}, {count}) is not this session's ({ctx.pair_first}, {ctx.pair_count})")
    if not isinstance(first, int) or not isinstance(count, int) or first < 0 or count <= 0 \
            or first + count > (ident.get("pairs_total") or 0):
        f.append("identity: the pair slice does not lie inside the experiment")
    if ident.get("carrier_variant") != CARRIER_VARIANT:
        f.append(f"identity: carrier_variant {ident.get('carrier_variant')!r} is not the qualified carrier's")
    if ident.get("protocol") != "rel-v4":
        f.append(f"identity: protocol {ident.get('protocol')!r} is not rel-v4")
    if ident.get("control_plane") != "standalone":
        f.append("identity: control_plane is not standalone")
    if ident.get("carto_version") != ctx.carto_version:
        f.append(f"identity: carto_version {ident.get('carto_version')!r} is not {ctx.carto_version!r}")
    if ident.get("arms") != ctx.arms:
        f.append(f"identity: arms {ident.get('arms')!r} is not {ctx.arms!r}")
    if ident.get("b1_map_cost") != ctx.b1_map_cost:
        f.append(f"identity: b1_map_cost {ident.get('b1_map_cost')!r} is not the constant {ctx.b1_map_cost} the accounting charges")
    return f


# ------------------------------------------------------------------ one record


def block_type_findings(block: dict, where: str) -> list[str]:
    """The JSON type of every value in the search block (the ledger sub-block aside), checked BEFORE
    anything compares, indexes, sorts, hashes or counts it. Called only once the key set is known
    to be exact, so every name is present."""
    f = [f"{where}: {k} is not {what}" for k, ok, what in BLOCK_TYPES if not ok(block[k])]
    move = block["move"]
    if move is not None:
        if not isinstance(move, dict) or sorted(move) != ["bits", "kind"]:
            f.append(f"{where}: the move must be bits and kind")
        else:
            if not _str(move["kind"]):
                f.append(f"{where}: the move's kind is not a string")
            if not _int_list(move["bits"]):
                f.append(f"{where}: the move's bits are not a list of integers")
    pop = block["population"]
    if not isinstance(pop, list) or len(pop) != bs.MU \
            or any(not isinstance(p, dict) or sorted(p) != ["born", "fit"] for p in pop):
        f.append(f"{where}: the population must be {bs.MU} entries of born and fit")
    elif any(not _int(p["born"]) or not _int(p["fit"]) for p in pop):
        f.append(f"{where}: a population entry's born and fit are not integers")
    return f


def ledger_type_findings(entry: dict, where: str) -> list[str]:
    """The JSON type of every value in a ledger entry, checked before anything else reads it.
    Called only once the key set is known to be exact."""
    return [f"{where}: ledger.{k} is not {what}" for k, ok, what in LEDGER_TYPES if not ok(entry[k])]


def _new_run_state() -> dict:
    return {"evals": 0, "best": None, "column_moves": None, "generation": None, "holdout_seen": False,
            "ledger": {"entries": 0, "after": 0, "anomalies": 0, "decoded": set(), "taken": set()}}


def ledger_findings(entry, block: dict, ctx: Context, pair: int, st: dict, where: str) -> list[str]:
    """One `specimen_ledger` 1.1.0 entry on an O-arm SEARCH record: its shape, its binding to the
    block it rides on, the run's continuity, and — field for field — the prediction's entry for this
    evaluation. `st` is the (pair, "O") run state; its `ledger` counters advance here."""
    if not isinstance(entry, dict):
        return [f"{where}: the ledger sub-block is not a JSON object"]
    if sorted(entry) != sorted(LEDGER_ENTRY_KEYS):
        return [f"{where}: the ledger entry's keys are not exactly {list(LEDGER_ENTRY_KEYS)}"]
    types = ledger_type_findings(entry, where)
    if types:                     # nothing below may compare, index, sort or count it
        return types
    f: list[str] = []
    L = st["ledger"]
    L["entries"] += 1
    n = L["entries"]                                    # this entry's position in the run = the record's position
    # -- the entry's own domain
    bits = entry["intervention"]
    if not (1 <= len(bits) <= bs.KMAX) or sorted(set(bits)) != bits or any(not (0 <= b < UNIVERSE) for b in bits):
        f.append(f"{where}: ledger.intervention is not 1..{bs.KMAX} distinct sorted universe indices")
    if entry["move_kind"] not in ("random", "column"):
        f.append(f"{where}: ledger.move_kind {entry['move_kind']!r}")
    delta = [tuple(x) for x in entry["behaviour_delta"]]
    if len(set(delta)) != len(delta) or any(not (0 <= k < LUTS and 0 <= v < VECTORS) for k, v in delta):
        f.append(f"{where}: ledger.behaviour_delta is not a set of distinct (lut 0..{LUTS - 1}, vector 0..{VECTORS - 1}) positions")
    if entry["confidence"] != (2 if len(bits) == 1 else 1):
        f.append(f"{where}: ledger.confidence {entry['confidence']} is not {2 if len(bits) == 1 else 1} for a {len(bits)}-bit specimen")
    decoded = [tuple(x) for x in entry["decoded"]]
    addrs = [i for i, _, _ in decoded]
    if len(set(addrs)) != len(addrs) or any(not (0 <= i < UNIVERSE and 0 <= k < LUTS and 0 <= v < VECTORS) for i, k, v in decoded):
        f.append(f"{where}: ledger.decoded is not a set of distinct (address, lut, vector) relations")
    if entry["anomalies"] < 0 or entry["map_version"] < 0 or entry["map_version_after"] < 0:
        f.append(f"{where}: a ledger counter is negative")
    # -- the binding to the block it rides on
    if entry["seq"] != block["eval"]:
        f.append(f"{where}: ledger.seq {entry['seq']} is not the record's eval {block['eval']}")
    move = block["move"]
    if isinstance(move, dict) and sorted(move) == ["bits", "kind"] and _int_list(move["bits"]) and _str(move["kind"]):
        if list(bits) != list(move["bits"]):
            f.append(f"{where}: ledger.intervention {bits} is not the move's bits {move['bits']}")
        if entry["move_kind"] != move["kind"]:
            f.append(f"{where}: ledger.move_kind {entry['move_kind']!r} is not the move's kind {move['kind']!r}")
    if entry["fitness"] != block["fitness"]:
        f.append(f"{where}: ledger.fitness {entry['fitness']} is not the record's fitness {block['fitness']}")
    if entry["parent_born"] != block["parent_born"]:
        f.append(f"{where}: ledger.parent_born {entry['parent_born']} is not the record's parent_born {block['parent_born']}")
    # -- the run's continuity
    if entry["seq"] != n:
        f.append(f"{where}: ledger.seq {entry['seq']} is not this run's entry {n}")
    if n == 1 and entry["map_version"] != 0:
        f.append(f"{where}: the first ledger entry's map_version {entry['map_version']} is not 0 (the online map starts empty)")
    elif n > 1 and entry["map_version"] != L["after"]:
        f.append(f"{where}: ledger.map_version {entry['map_version']} is not the previous entry's map_version_after {L['after']}")
    d_anom = entry["anomalies"] - L["anomalies"]
    if d_anom < 0:
        f.append(f"{where}: ledger.anomalies went backwards ({L['anomalies']} -> {entry['anomalies']})")
    elif d_anom > 1:
        f.append(f"{where}: ledger.anomalies jumped ({L['anomalies']} -> {entry['anomalies']}); one specimen is at most one anomaly")
    elif d_anom == 1:
        f.append(f"{where}: an anomaly — the board's cartographer refused this specimen (anomalies {L['anomalies']} -> {entry['anomalies']})")
        if decoded or entry["map_version_after"] != entry["map_version"]:
            f.append(f"{where}: a refused specimen changes nothing else, but this entry decodes {addrs} / bumps the version to {entry['map_version_after']}")
    if decoded:
        if entry["map_version_after"] != entry["map_version"] + 1:
            f.append(f"{where}: ledger.map_version_after {entry['map_version_after']} is not map_version {entry['map_version']} + 1 for a specimen that decoded")
    elif entry["map_version_after"] != entry["map_version"]:
        f.append(f"{where}: ledger.map_version_after {entry['map_version_after']} is not map_version {entry['map_version']} for a specimen that decoded nothing (the version bumps only on a decode)")
    for i, k, v in decoded:
        if i in L["decoded"]:
            f.append(f"{where}: address {i} decoded twice in this run")
        if (k, v) in L["taken"]:
            f.append(f"{where}: position ({k}, {v}) taken twice in this run")
        L["decoded"].add(i)
        L["taken"].add((k, v))
    L["after"] = entry["map_version_after"]
    L["anomalies"] = entry["anomalies"]
    # -- field for field against the prediction's entry for this evaluation
    if 1 <= n <= ctx.budget:
        want = ctx.predicted_o(pair)["ledger"][n - 1]
        f += [f"{where}: {x} — not the predicted entry" for x in b3g.deep_findings(want, entry, LEDGER_KEY)]
    return f


def record_findings(rec: dict, ctx: Context, want: tuple[int, str, bool] | None, state: dict) -> list[str]:
    """`want` is what the order says this candidate must be (None = a baseline bracket);
    `state` carries the per-(pair, arm) counters this function advances."""
    if not isinstance(rec, dict):
        return ["record: not a JSON object"]
    f: list[str] = []
    seq = rec.get("seq")
    where = f"record {seq}"
    if rec.get("schema") != "loop_record":
        f.append(f"{where}: schema {rec.get('schema')!r} is not loop_record")
    if rec.get("schema_version") != RECORD_SCHEMA_VERSION:
        f.append(f"{where}: schema_version {rec.get('schema_version')!r} is not {RECORD_SCHEMA_VERSION}")
    if "carto" in rec:
        f.append(f"{where}: a `carto` block belongs to stage B1")
    if LEDGER_KEY in rec:
        f.append(f"{where}: a top-level `ledger`: the ledger sub-block lives inside an O-arm search record's search block")
    block, arm = rec.get("search"), rec.get("arm")
    if want is None:                                   # a baseline bracket
        if block is not None:
            f.append(f"{where}: a baseline carries no search block")
        if arm is not None:
            f.append(f"{where}: a baseline carries no arm")
        return f
    pair, want_arm, holdout = want
    if arm != want_arm:
        f.append(f"{where}: arm {arm!r} is not the {want_arm!r} the order requires")
    if rec.get("outcome") != "SCORED":
        return f + [f"{where}: only a SCORED candidate carries a search block"] if block is not None else f
    if not isinstance(block, dict):
        f.append(f"{where}: a scored candidate must carry a search block")
        return f
    has_ledger = LEDGER_KEY in block
    if sorted(k for k in block if k != LEDGER_KEY) != sorted(BLOCK_KEYS):
        f.append(f"{where}: the search block's keys are not exactly {list(BLOCK_KEYS)}"
                 f"{' plus ledger' if want_arm == oa.ARM_ONLINE and not holdout else ''}")
        return f
    ledger_due = want_arm == oa.ARM_ONLINE and not holdout
    if ledger_due and not has_ledger:
        f.append(f"{where}: an O-arm search record must carry its ledger sub-block (specimen_ledger {LEDGER_SCHEMA_VERSION})")
    if has_ledger and not ledger_due:
        kind = ("an O champion's holdout record" if want_arm == oa.ARM_ONLINE
                else f"a {WIRE_TEXT[want_arm]} champion's holdout record" if holdout
                else f"a {WIRE_TEXT[want_arm]} search record")
        f.append(f"{where}: a ledger sub-block on {kind} (only O-arm search records carry one)")
    types = block_type_findings(block, where)
    if types:                     # nothing below may compare, index, sort, hash or count it
        return f + types
    if block["version"] != ctx.engine:
        f.append(f"{where}: the block's version {block['version']!r} is not {ctx.engine!r}")
    if block["arm"] != ARM_LETTER.get(want_arm):
        f.append(f"{where}: the block's arm {block['arm']!r} disagrees with the record's {arm!r}")
    if block["pair"] != pair:
        f.append(f"{where}: the block's pair {block['pair']!r} is not {pair}")
    if not (ctx.pair_first <= block["pair"] < ctx.pair_first + ctx.pair_count):
        f.append(f"{where}: pair {block['pair']!r} is outside this session's slice")
    elif block["pair"] >= ctx.pairs_total:
        f.append(f"{where}: pair {block['pair']!r} is outside the experiment's {ctx.pairs_total} pairs")
    else:
        lseed, oseed = ctx.seeds[block["pair"]]
        if block["landscape_seed"] != lseed or block["operator_seed"] != oseed:
            f.append(f"{where}: the block's seeds are not pair {block['pair']}'s seeds")
    if not HEX64.fullmatch(block["state_sha256"]):
        f.append(f"{where}: state_sha256 is not 64 hex")
    key = (pair, ARM_LETTER[want_arm])
    st = state.setdefault(key, _new_run_state())
    if holdout:
        if block["holdout"] is None:
            f.append(f"{where}: a champion's holdout record must carry its holdout value")
        if block["move"] is not None or block["fitness"] is not None or block["parent_born"] is not None:
            f.append(f"{where}: a holdout record carries no move, fitness or parent")
        if block["selected"]:
            f.append(f"{where}: a holdout record closes no generation")
        if block["eval"] != ctx.budget:
            f.append(f"{where}: the holdout record's eval {block['eval']!r} is not the budget {ctx.budget}")
        if st["holdout_seen"]:
            f.append(f"{where}: a second holdout record for {key}")
        st["holdout_seen"] = True
        if want_arm == oa.ARM_ONLINE and HEX64.fullmatch(block["state_sha256"]):
            final = ctx.predicted_o(pair)["final_state_sha256"]
            if block["state_sha256"] != final:
                f.append(f"{where}: the O champion's holdout record's state_sha256 {block['state_sha256'][:12]}… is not the "
                         f"predicted final commitment {final[:12]}… (the holdout evaluation changes neither the search nor the map)")
    else:
        if block["holdout"] is not None:
            f.append(f"{where}: a search record carries no holdout value")
        move = block["move"]
        if move is None:
            f.append(f"{where}: a search record must carry its move, bits and kind")
        else:
            if move["kind"] not in ("random", "column"):
                f.append(f"{where}: move kind {move['kind']!r}")
            bits = move["bits"]
            if not (1 <= len(bits) <= bs.KMAX) or sorted(set(bits)) != bits \
                    or any(not (0 <= b < UNIVERSE) for b in bits):
                f.append(f"{where}: the move's bits are not 1..{bs.KMAX} distinct sorted universe indices")
            if move["kind"] == "column" and block["arm"] == "A":
                f.append(f"{where}: a column move on the random-safe arm")
        if block["fitness"] is None:
            f.append(f"{where}: a search record must carry its fitness")
        if block["parent_born"] is None:
            f.append(f"{where}: a search record must name its parent")
        st["evals"] += 1
        if block["eval"] != st["evals"]:
            f.append(f"{where}: eval {block['eval']!r} is not {st['evals']} for {key}")
        if st["evals"] > ctx.budget:
            f.append(f"{where}: more than {ctx.budget} evaluations for {key}")
        if st["holdout_seen"]:
            f.append(f"{where}: a search record after this arm's holdout")
        if ledger_due and has_ledger:
            f += ledger_findings(block[LEDGER_KEY], block, ctx, pair, st, where)
            if st["evals"] == ctx.budget and HEX64.fullmatch(block["state_sha256"]):
                final = ctx.predicted_o(pair)["final_state_sha256"]
                if block["state_sha256"] != final:
                    f.append(f"{where}: the final O-arm state_sha256 {block['state_sha256'][:12]}… is not the predicted "
                             f"search + cartographer commitment {final[:12]}…")
    for name in ("best", "column_moves", "generation"):
        prev = st[name]
        cur = block[name]
        if prev is not None and cur < prev:
            f.append(f"{where}: {name} went backwards ({prev} -> {cur})")
        else:
            st[name] = cur
    if block["arm"] == "A" and block["column_moves"] != 0:
        f.append(f"{where}: the random-safe arm made {block['column_moves']} column moves")
    return f


# ------------------------------------------------------------------ the session


def session_findings(log: dict, ctx: Context) -> list[str]:
    if not isinstance(log, dict):
        return ["session: not a JSON object"]
    f: list[str] = []
    ident = log.get("app_identity") or {}
    f += identity_findings(ident, ctx)
    records = log.get("loop_records") or []
    if not isinstance(records, list):
        return f + ["session: loop_records is not an array"]
    order = expected_order(ctx)
    if len(records) != len(order):
        f.append(f"session: {len(records)} records, the order requires {len(order)} ({ctx.records} for this slice)")
    state: dict = {}
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            f.append(f"session: record {i + 1} is not a JSON object")
            continue
        if rec.get("seq") != i + 1:
            f.append(f"session: record {i + 1} carries seq {rec.get('seq')!r}")
        f += record_findings(rec, ctx, order[i] if i < len(order) else None, state)
    if len(records) == len(order):
        # Every run the slice EXPECTS is enumerated here — never only the runs the records happened
        # to create: a whole arm replaced by non-SCORED records without a search block creates no
        # state and would otherwise pass in silence (the owner's P2 on 989bac5).
        for i in range(ctx.pair_count):
            r = ctx.pair_first + i
            for a in ARMS:
                key = (r, ARM_LETTER[ARM_WIRE[a]])
                st = state.get(key)
                if st is None:
                    f.append(f"session: {key} has no records at all — the whole {WIRE_TEXT[ARM_WIRE[a]]} run of pair {r} is missing "
                             f"(no SCORED search record, no champion holdout record)")
                    continue
                if st["evals"] != ctx.budget:
                    f.append(f"session: {key} ran {st['evals']} evaluations, not {ctx.budget}")
                if not st["holdout_seen"]:
                    f.append(f"session: {key} has no champion holdout record")
                if a == "O" and st["ledger"]["entries"] != ctx.budget:
                    f.append(f"session: {key} carries {st['ledger']['entries']} ledger entries, not {ctx.budget}")
    return f


def validate_run_log(log: dict, ctx: Context, common: bool = True) -> list[str]:
    """The instrument's common validation (optional, so a synthetic B3 fixture can be checked
    without the instrument bound) and then every B3 rule."""
    if not isinstance(log, dict):
        return ["session: not a JSON object"]
    f: list[str] = []
    if common:
        import b1_records as br
        for name in ("app_identity",):
            if name in log:
                try:
                    br.validate(log[name])
                except Exception as exc:                    # the instrument's own refusal
                    f.append(f"common envelope: {name}: {exc}")
        records = log.get("loop_records") or []
        for rec in records if isinstance(records, list) else []:
            try:
                br.validate(rec)
            except Exception as exc:
                seq = rec.get("seq") if isinstance(rec, dict) else "?"
                f.append(f"common envelope: record {seq}: {exc}")
    return f + session_findings(log, ctx)

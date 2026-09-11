#!/usr/bin/env python3
"""B2 — the record validator: everything the instrument's validator does NOT check.

The instrument's validator, reached through `b1_records`, checks the common envelope and
**ignores unknown extension fields**. The owner's core review of 2026-09-10 demonstrated
what that means for B2: deleting `REC.search` still validates, and so does an identity with
an invalid map digest, a zero budget and an impossible pair slice. Common-envelope
compatibility is therefore all that `tests/test_b2_wire.py` may claim, and every B2 field
and every cross-record binding is checked here instead.

Three layers, each a pure function returning named findings (empty = nothing to report):

  identity_findings   the `app_identity` 1.5.0 fields: the engine, the map digest, the
                      fitness, the per-arm budget, this session's pair slice, the master
                      seed, the carrier variant — and that the B1 fields this image has no
                      business declaring (`carto_version`, `probe_budget`) are ABSENT.
  record_findings     one `loop_record` 1.3.0: whether it may carry a `search` block at all,
                      the block's exact shape, and every value that must agree with the
                      session it belongs to — the arm letter, the pair, the pair's derived
                      seeds, the evaluation index, the monotone counters, and the shape a
                      champion's holdout record must have instead of a move.
  session_findings    the whole run: the candidate ORDER the orchestrator must have
                      produced for the declared slice, the record count, the seq run, and
                      that the identity's slice is the one the records actually use.

Every one of them checks a value's JSON TYPE before anything compares, indexes, sorts,
hashes or counts it (`identity_type_findings`, `block_type_findings`): a malformed document
must come back as a named finding, never as an incidental Python exception, and a JSON
boolean is never an integer (the owner's initial review of 2026-09-11).

`validate_run_log` runs the instrument's common validation first and then all three. It is
a validator, not the adjudicator: it never recomputes a fitness from a readout and never
replays the search — that is `b2_adjudicate`'s work, and this module deliberately does not
pretend to do it.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b2_maps as bmaps  # noqa: E402
import b2_search as bs  # noqa: E402
import b2_session as bsess  # noqa: E402

IDENTITY_SCHEMA_VERSION = "1.5.0"
RECORD_SCHEMA_VERSION = "1.3.0"
BLOCK_KEYS = ("arm", "best", "column_moves", "eval", "fitness", "generation", "holdout",
              "landscape_seed", "move", "operator_seed", "pair", "parent_born", "population",
              "selected", "state_sha256", "version")
IDENTITY_B2_KEYS = ("search_version", "map_sha256", "fitness_id", "budget_per_arm",
                    "pairs_total", "pair_first", "pair_count")
IDENTITY_FORBIDDEN = ("carto_version", "probe_budget")
ARM_WIRE = {bs.ARM_RANDOM_SAFE: "random_safe", bs.ARM_MAP_GUIDED: "map_guided"}
ARM_LETTER = {"random_safe": "A", "map_guided": "B"}
# Matched with fullmatch(), never match(): Python's `$` also matches before a final
# newline, so `^...$` accepts a 65-character digest (the owner's P3 of 2026-09-11).
HEX64 = re.compile(r"[0-9a-f]{64}")
CARRIER_VARIANT = "0x42310001"
UNIVERSE = 292


def _int(v) -> bool:
    """A JSON integer. `True` is not one, whatever `isinstance(True, int)` says."""
    return isinstance(v, int) and not isinstance(v, bool)


def _str(v) -> bool:
    return isinstance(v, str)


def _bool(v) -> bool:
    return isinstance(v, bool)


def _int_or_null(v) -> bool:
    return v is None or _int(v)


# (field, predicate, what it must be) — the JSON type of every value this module reads.
IDENTITY_TYPES = (("schema_version", _str, "a string"), ("search_version", _str, "a string"),
                  ("map_sha256", _str, "a string"), ("operator_data_sha256", _str, "a string"),
                  ("fitness_id", _str, "a string"), ("carrier_variant", _str, "a string"),
                  ("protocol", _str, "a string"), ("control_plane", _str, "a string"),
                  ("budget_per_arm", _int, "an integer"), ("master_seed", _int, "an integer"),
                  ("pairs_total", _int, "an integer"), ("pair_first", _int, "an integer"),
                  ("pair_count", _int, "an integer"))
BLOCK_TYPES = (("version", _str, "a string"), ("arm", _str, "a string"),
               ("state_sha256", _str, "a string"), ("pair", _int, "an integer"),
               ("eval", _int, "an integer"), ("best", _int, "an integer"),
               ("column_moves", _int, "an integer"), ("generation", _int, "an integer"),
               ("landscape_seed", _int, "an integer"), ("operator_seed", _int, "an integer"),
               ("selected", _bool, "a boolean"), ("holdout", _int_or_null, "an integer or null"),
               ("fitness", _int_or_null, "an integer or null"),
               ("parent_born", _int_or_null, "an integer or null"))


@dataclass(frozen=True)
class Context:
    """What the session was supposed to be: the frozen experiment plus this session's slice."""
    master_seed: int
    budget: int
    pairs_total: int
    pair_first: int
    pair_count: int
    fitness: str
    map_sha256: str
    engine: str = bs.ENGINE_VERSION
    pair_seeds: tuple[tuple[int, int], ...] | None = None

    @property
    def seeds(self) -> list[tuple[int, int]]:
        """The pairs' derived seeds. `pair_seeds` replaces the derivation for a session whose
        seed RULE is not B2's — B2Q draws under its own label and excludes B2's own set
        (preregistration §6a) — and is never a way to choose seeds for a B2 session: the
        caller that supplies it is responsible for deriving it by the rule that session
        preregistered."""
        if self.pair_seeds is not None:
            return [tuple(x) for x in self.pair_seeds]
        return bsess.pair_seeds(self.master_seed, self.pairs_total)

    @property
    def records(self) -> int:
        return bsess.records(self.pair_count, self.budget)


def context_from(plan: dict, pair_first: int, pair_count: int,
                 pair_seeds: list | None = None) -> Context:
    """The context of ONE session: the plan's frozen experiment and this session's slice.
    `pair_seeds` is for a session whose seed rule is not B2's (see `Context.seeds`)."""
    return Context(master_seed=plan["seed_derivation"]["master_seed"], budget=plan["budget_per_arm"],
                   pairs_total=plan["pairs"], pair_first=pair_first, pair_count=pair_count,
                   fitness=plan["fitness"], map_sha256=plan["map"]["sha256"],
                   pair_seeds=None if pair_seeds is None else tuple(tuple(x) for x in pair_seeds))


def expected_order(ctx: Context) -> list[tuple[int, str, bool] | None]:
    """The candidate order the orchestrator must produce: None for each baseline bracket, and
    (pair, arm, holdout) for every other candidate, in sequence."""
    out: list[tuple[int, str, bool] | None] = [None]
    for i in range(ctx.pair_count):
        r = ctx.pair_first + i
        order = bsess.arm_order(r)
        for arm in order:
            out += [(r, bsess.arm_wire_name(arm), False)] * ctx.budget
        for arm in order:
            out.append((r, bsess.arm_wire_name(arm), True))
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
    for k in IDENTITY_FORBIDDEN:
        if k in ident:
            f.append(f"identity: {k!r} is declared, but this image runs no cartographer and issues no probes")
    types = identity_type_findings(ident)
    if types:                     # nothing below may compare or add a value of unknown type
        return f + types
    if ident.get("search_version") != ctx.engine:
        f.append(f"identity: search_version {ident.get('search_version')!r} is not {ctx.engine!r}")
    if ident.get("map_sha256") != ctx.map_sha256:
        f.append("identity: map_sha256 is not the map this experiment is bound to")
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
    return f


# ------------------------------------------------------------------ one record


def block_type_findings(block: dict, where: str) -> list[str]:
    """The JSON type of every value in the search block, checked BEFORE anything compares,
    indexes, sorts, hashes or counts it. Called only once the key set is known to be exact,
    so every name is present."""
    f = [f"{where}: {k} is not {what}" for k, ok, what in BLOCK_TYPES if not ok(block[k])]
    move = block["move"]
    if move is not None:
        if not isinstance(move, dict) or sorted(move) != ["bits", "kind"]:
            f.append(f"{where}: the move must be bits and kind")
        else:
            if not _str(move["kind"]):
                f.append(f"{where}: the move's kind is not a string")
            if not isinstance(move["bits"], list) or any(not _int(b) for b in move["bits"]):
                f.append(f"{where}: the move's bits are not a list of integers")
    pop = block["population"]
    if not isinstance(pop, list) or len(pop) != bs.MU \
            or any(not isinstance(p, dict) or sorted(p) != ["born", "fit"] for p in pop):
        f.append(f"{where}: the population must be {bs.MU} entries of born and fit")
    elif any(not _int(p["born"]) or not _int(p["fit"]) for p in pop):
        f.append(f"{where}: a population entry's born and fit are not integers")
    return f


def record_findings(rec: dict, ctx: Context, want: tuple[int, str, bool] | None, state: dict) -> list[str]:
    """`want` is what the order says this candidate must be (None = a baseline bracket);
    `state` carries the per-(pair, arm) counters this function advances."""
    if not isinstance(rec, dict):
        return ["record: not a JSON object"]
    f: list[str] = []
    seq = rec.get("seq")
    where = f"record {seq}"
    if rec.get("schema_version") != RECORD_SCHEMA_VERSION:
        f.append(f"{where}: schema_version {rec.get('schema_version')!r} is not {RECORD_SCHEMA_VERSION}")
    if "carto" in rec:
        f.append(f"{where}: a `carto` block belongs to stage B1")
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
    if sorted(block) != sorted(BLOCK_KEYS):
        f.append(f"{where}: the search block's keys are not exactly {list(BLOCK_KEYS)}")
        return f
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
            f.append(f"{where}: the block's seeds are not pair {block['pair']}'s derived seeds")
    if not HEX64.fullmatch(block["state_sha256"]):
        f.append(f"{where}: state_sha256 is not 64 hex")
    key = (block["pair"], block["arm"])
    st = state.setdefault(key, {"evals": 0, "best": None, "column_moves": None, "generation": None, "holdout_seen": False})
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
            if move["kind"] == "column" and block["arm"] != "B":
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
        for key, st in state.items():
            if st["evals"] != ctx.budget:
                f.append(f"session: {key} ran {st['evals']} evaluations, not {ctx.budget}")
            if not st["holdout_seen"]:
                f.append(f"session: {key} has no champion holdout record")
    return f


def validate_run_log(log: dict, ctx: Context, common: bool = True) -> list[str]:
    """The instrument's common validation (optional, so a synthetic B2 fixture can be checked
    without the instrument bound) and then every B2 rule."""
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

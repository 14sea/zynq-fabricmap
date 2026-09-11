#!/usr/bin/env python3
"""B2 — adjudication of a run's sessions: the host's recomputation from the SERVED readouts
(pure; re-runnable; nothing here touches a board).

    b2_adjudicate.py --run-log <run_log.json> [--run-log …] [--plan …] [--prediction …]
                     [--scope run|session] [--out …]

The preregistration's acceptance conditions (§4) that concern the records themselves, each a
named finding. The sessions are consumed **in session order**, and inside a session in seq
order, exactly as the board produced them.

Two passes, deliberately separate:

  measurement   ONE finding per record, independent of every other record: the six served
                readout words; F1 over the train columns of THAT readout equals the record's
                self-reported `search.fitness`; for a champion's re-measured holdout record,
                F1 over the holdout columns equals its `search.holdout`; the PL scorer's
                additive `scores` equal the additive count derived from the same readout
                (the carrier's free known answer); a baseline's readout is all-zero.
                A served readout contradicting a self-report is a KILL, per record.
  replay        the reference engine, fed those same served readouts, must reproduce what the
                board did: every parent draw, every move and its kind, the child genome, the
                best-so-far and column-move counters, the generation, the population after
                selection, which record closed a generation, the champion, and the running
                commitment `state_sha256` of every record. The replay is STATEFUL, so it stops
                at the first divergence and names it — everything after it would be noise.
                A board that did not follow the algorithm on its own observations is a HOLD.

Then the run's metrics against the pinned prediction (`evidence/b2/prediction.json`), per pair
and per arm: the best-so-far train fitness at the budget, the champion's genome digest, its
holdout value, the column-move count, and the move sequence digest — and, when the sessions
together cover every preregistered pair exactly once, the whole run's fitness-sequence digest
and the primary: the one-sided exact sign test over the pairs' Δ, pooled across sessions.

What this module is NOT. It does not verify the manifest's pins, the carrier's qualification
chain, the instrument's rate/deadline/CRC budgets or the evidence directory's exports — those
are the runner's and `b2_pins`' layers, and their absence is stated in the result rather than
silently passed. It never uses the fabric model to produce a readout: every fitness it
recomputes comes from the bytes the board served. The model appears only where the
preregistration already committed it — inside the pinned prediction, which was written before
any board contact.

Outcome: PASS (no findings), HOLD (a named finding), KILL (a served readout contradicts a
self-report), REFUSED (the inputs are not a run this module can adjudicate at all).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_records as brec  # noqa: E402
import b2_search as bs  # noqa: E402
import b2_session as bsess  # noqa: E402

TOOL_VERSION = "b2_adjudicate.py/0.1.0"
SESSION = "B2"
LUTS = bl.LUTS
MAX_NAMED_PER_PASS = 20          # a finding per record, but a wall of them is a summary line
BLANK_GENOME = bc.genome_to_hex(0)
HEX64 = re.compile(r"[0-9a-f]{64}")
UINT32 = 1 << 32
RUN_COUNTS = ("best_train", "champion_holdout", "column_moves")
RUN_DIGESTS = ("champion_genome_sha256", "moves_sha256")
PRIMARY_COUNTS = ("positives", "negatives", "ties")
NOT_CHECKED_HERE = ("manifest pins", "carrier qualification", "instrument rate / deadline / CRC budgets",
                    "evidence exports", "ruling binding")


class Refusal(Exception):
    """The inputs are not a run this module can adjudicate — not a verdict about a board."""


def _int(v) -> bool:
    """A JSON integer. `True` is not one, and neither is 2.0 — Python would compare both equal
    to the counts this module checks, so the type is established before any comparison."""
    return isinstance(v, int) and not isinstance(v, bool)


def _real(v) -> bool:
    """A JSON number. `True` is not one."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _hex64(v) -> bool:
    return isinstance(v, str) and HEX64.fullmatch(v) is not None


def records_of(log: dict) -> list:
    """The session's records, or an empty list when the document does not carry an array of
    them — never an object this module would then iterate or index blindly."""
    if not isinstance(log, dict):
        return []
    recs = log.get("loop_records")
    return recs if isinstance(recs, list) else []


def check_plan(plan: dict) -> None:
    """The plan fields this module consumes, checked as VALUES — type first, then domain —
    before anything uses them: the replay derives the seeds and the landscapes from them and
    `b2_records` binds the slice to them, so a wrong one here is a refusal, not a finding about
    a board. Every membership test and every lookup below is reached only after the value's
    type is established (the owner's input review of 2026-09-11)."""
    if not isinstance(plan, dict):
        raise Refusal("the plan is not a JSON object")
    for key in ("budget_per_arm", "fitness", "pairs", "seed_derivation", "map"):
        if key not in plan:
            raise Refusal(f"the plan carries no {key!r}")
    if not _int(plan["budget_per_arm"]) or plan["budget_per_arm"] <= 0:
        raise Refusal(f"the plan's budget_per_arm {plan['budget_per_arm']!r} is not a positive integer")
    if not isinstance(plan["fitness"], str):                    # BEFORE the membership lookup
        raise Refusal(f"the plan's fitness {plan['fitness']!r} is not a string")
    if plan["fitness"] not in bl.FITNESS:
        raise Refusal(f"the plan's fitness {plan['fitness']!r} is not one of {sorted(bl.FITNESS)}")
    if not _int(plan["pairs"]) or not (0 < plan["pairs"] <= bsess.MAX_PAIRS):
        raise Refusal(f"the plan's pairs {plan['pairs']!r} is not 1..{bsess.MAX_PAIRS}, the identity "
                      f"page's slice field")
    if not isinstance(plan["map"], dict):
        raise Refusal("the plan's map is not a JSON object")
    if not _hex64(plan["map"].get("sha256")):
        raise Refusal(f"the plan's map sha256 {plan['map'].get('sha256')!r} is not 64 lower-case hex")
    sd = plan["seed_derivation"]
    if not isinstance(sd, dict) or "master_seed" not in sd:
        raise Refusal("the plan's seed_derivation carries no master_seed")
    if not _int(sd["master_seed"]):
        raise Refusal(f"the plan's master_seed {sd['master_seed']!r} is not an integer")
    if not (0 <= sd["master_seed"] < UINT32):
        raise Refusal(f"the plan's master_seed {sd['master_seed']!r} is outside 0..2**32-1: the rule "
                      f"draws four bytes and the instrument's Rng masks to 32 bits, so an out-of-range "
                      f"declaration would silently replay another number's stream")


def check_prediction(prediction: dict, plan: dict) -> None:
    """The prediction fields this module compares against — every one of them typed and its
    domain checked before a comparison, because Python's numeric equality would otherwise
    accept `True` for 1 and `2.0` for 2 in the counts this module reports as EXACT. The pair
    identities must cover the experiment exactly once IN ORDER before any lookup is built from
    them, so a duplicate cannot be silently overwritten and an out-of-range entry cannot sit
    unvisited. This is not the manifest's canonical-plan verifier and does not replace it."""
    if not isinstance(prediction, dict) or prediction.get("schema") != "b2_prediction":
        raise Refusal("the prediction is not a b2_prediction document")
    if not isinstance(prediction.get("fitness"), str) or prediction["fitness"] != plan["fitness"]:
        raise Refusal(f"the prediction's fitness ({prediction.get('fitness')!r}) is not the plan's "
                      f"({plan['fitness']!r})")
    if not _int(prediction.get("budget_per_arm")) or prediction["budget_per_arm"] != plan["budget_per_arm"]:
        raise Refusal(f"the prediction's budget_per_arm ({prediction.get('budget_per_arm')!r}) is not the "
                      f"plan's ({plan['budget_per_arm']!r})")
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
    if ids != list(range(plan["pairs"])):        # BEFORE any lookup is built from them
        raise Refusal(f"the prediction's pair identities are {ids if len(ids) <= 12 else str(ids[:12]) + '...'}, "
                      f"not the experiment's 0..{plan['pairs'] - 1} exactly once in order")
    for entry in entries:
        runs = entry.get("runs")
        if not isinstance(runs, dict) or any(not isinstance(runs.get(k), dict) for k in ("A", "B")):
            raise Refusal(f"the prediction's pair {entry['pair']} carries no A and B run objects")
        for letter in ("A", "B"):
            run = runs[letter]
            for k in RUN_COUNTS:
                if not _int(run.get(k)):
                    raise Refusal(f"the prediction's pair {entry['pair']} arm {letter}: {k} "
                                  f"{run.get(k)!r} is not an integer")
            for k, ceiling in (("best_train", train_ceiling), ("champion_holdout", holdout_ceiling),
                               ("column_moves", budget)):
                if not (0 <= run[k] <= ceiling):
                    raise Refusal(f"the prediction's pair {entry['pair']} arm {letter}: {k} {run[k]} is "
                                  f"outside 0..{ceiling}")
            for k in RUN_DIGESTS:
                if not _hex64(run.get(k)):
                    raise Refusal(f"the prediction's pair {entry['pair']} arm {letter}: {k} "
                                  f"{run.get(k)!r} is not 64 lower-case hex")
    deltas = prediction.get("deltas")
    if not isinstance(deltas, list) or any(not _int(d) for d in deltas):
        raise Refusal("the prediction's deltas are not an array of integers")
    if len(deltas) != plan["pairs"]:
        raise Refusal(f"the prediction carries {len(deltas)} deltas for {plan['pairs']} pairs")
    for entry, delta in zip(entries, deltas):
        want = entry["runs"]["B"]["best_train"] - entry["runs"]["A"]["best_train"]
        if "delta_B_minus_A" in entry and not _int(entry["delta_B_minus_A"]):
            # Redundant beside `deltas`, but a field that is present is a field that is typed:
            # `false` and `0.0` both compare equal to 0 (the owner's P3 of 2026-09-11).
            raise Refusal(f"the prediction's pair {entry['pair']}: delta_B_minus_A "
                          f"{entry['delta_B_minus_A']!r} is not an integer")
        if delta != want or ("delta_B_minus_A" in entry and entry["delta_B_minus_A"] != want):
            raise Refusal(f"the prediction's pair {entry['pair']}: the delta does not account for its own "
                          f"B and A best_train ({want})")
    primary = prediction.get("predicted_primary")
    if not isinstance(primary, dict):
        raise Refusal("the prediction carries no predicted_primary object")
    for k in PRIMARY_COUNTS:
        if not _int(primary.get(k)) or primary[k] < 0:
            raise Refusal(f"the prediction's primary {k} {primary.get(k)!r} is not a count")
    if sum(primary[k] for k in PRIMARY_COUNTS) != plan["pairs"]:
        raise Refusal(f"the prediction's primary counts {[primary[k] for k in PRIMARY_COUNTS]} do not "
                      f"account for {plan['pairs']} pairs")
    for k in ("sign_test_p", "alpha"):
        if not _real(primary.get(k)) or not (0 <= primary[k] <= 1):
            raise Refusal(f"the prediction's primary {k} {primary.get(k)!r} is not a probability")
    if not isinstance(primary.get("verdict"), str):
        raise Refusal(f"the prediction's primary verdict {primary.get('verdict')!r} is not a string")
    if primary != bp.decision(deltas):
        raise Refusal("the prediction's predicted_primary is not the sign test over its own deltas")
    if not _hex64(prediction.get("fitness_sequence_sha256")):
        raise Refusal(f"the prediction's fitness_sequence_sha256 "
                      f"{prediction.get('fitness_sequence_sha256')!r} is not 64 lower-case hex")
    want_len = plan["pairs"] * (2 * budget + 2)
    if not _int(prediction.get("fitness_sequence_length")) or prediction["fitness_sequence_length"] != want_len:
        raise Refusal(f"the prediction's fitness_sequence_length "
                      f"{prediction.get('fitness_sequence_length')!r} is not the {want_len} values "
                      f"{plan['pairs']} pairs at budget {budget} produce")


def check_seeds(seeds, pairs: int) -> None:
    """The explicit pair-seed list, checked as a CONTAINER first and a value second: the outer
    array, then every pair's container and arity, then every value's type and 32-bit domain —
    all before anything iterates, converts or indexes it."""
    if not isinstance(seeds, list):
        raise Refusal(f"the pair seeds are {type(seeds).__name__}, not an array")
    if len(seeds) != pairs:
        raise Refusal(f"{len(seeds)} pair seeds were given for {pairs} pairs")
    for i, pair in enumerate(seeds):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise Refusal(f"pair seed {i} is not a [landscape, operator] array of two values")
        for v in pair:
            if not _int(v) or not (0 <= v < UINT32):
                raise Refusal(f"pair seed {i}: {v!r} is not a 32-bit value")


def structure_findings(s: "SessionInput") -> list[str]:
    """What the replay and the readout map need of a session before either touches it: an
    array of record objects, each with an integer seq. A record this names never enters the
    replay, and nothing here is used as a dictionary key."""
    f: list[str] = []
    recs = s.log.get("loop_records")
    if recs is None:
        return ["the log carries no loop_records"]
    if not isinstance(recs, list):
        return [f"loop_records is {type(recs).__name__}, not an array"]
    for i, rec in enumerate(recs):
        if not isinstance(rec, dict):
            f.append(f"record {i + 1} is not a JSON object")
        elif not _int(rec.get("seq")):
            f.append(f"record {i + 1} carries seq {rec.get('seq')!r}, which is not an integer")
    return f


# ------------------------------------------------------------------ the served readout


def readout_words(rec: dict) -> list[int] | None:
    """The six 64-bit words the board served for THIS record, or None if the record does not
    carry them in the shape the carrier contract fixes. Never falls back to a model."""
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
    if not isinstance(got, list) or len(got) != LUTS or any(not isinstance(x, int) or isinstance(x, bool) for x in got):
        return None
    return got


def additive_scores(tables: list[int], consts: dict) -> list[int]:
    """The PL scorer's own per-LUT count over the carrier's fixed target — the instrument's
    free per-record known answer. A pure function of the served readout."""
    n, k = consts["train_count"], consts["holdout_count"]
    vecs = consts["order"][:n]
    return [sum(1 for v in vecs if (t >> v) & 1 == (lut["target"] >> v) & 1)
            for t, lut in zip(tables, consts["luts"])]


def instrument_constants() -> dict:
    """The carrier constants as the INSTRUMENT holds them (the PL that produced the scores),
    not this repository's copy."""
    import claimb_r1p_instrument as inst
    inst.bind(inst.DEFAULT_ROOT, require_git=False)
    import p3_oracle as po
    return po.load_constants()


# ------------------------------------------------------------------ what one session declares


@dataclass
class SessionInput:
    """One session's run log, with the slice its identity declares."""
    log: dict
    pair_first: int
    pair_count: int
    index: int = 0

    @property
    def pairs(self) -> range:
        return range(self.pair_first, self.pair_first + self.pair_count)


def session_slice(log: dict) -> tuple[int, int]:
    if not isinstance(log, dict):
        raise Refusal(f"a session log is {type(log).__name__}, not a JSON object")
    ident = log.get("app_identity")
    if not isinstance(ident, dict):
        raise Refusal("a session log carries no app_identity object")
    first, count = ident.get("pair_first"), ident.get("pair_count")
    ok = lambda v: isinstance(v, int) and not isinstance(v, bool)      # noqa: E731
    if not ok(first) or not ok(count) or first < 0 or count <= 0:
        raise Refusal(f"a session's identity declares the slice ({first!r}, {count!r})")
    return first, count


def order_sessions(logs: list[dict]) -> list[SessionInput]:
    """Session order is the order of the pair slices, and the slices must tile a prefix of the
    experiment without overlap or gap — an ambiguous order is a refusal, not a finding."""
    sessions = []
    for log in logs:
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
    """What the readouts alone say, before any replay."""
    kills: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    checked: int = 0
    readouts: dict[tuple[int, int], list[int]] = field(default_factory=dict)   # (session, position) -> words


def measurement_pass(sessions: list[SessionInput], ctx_of, consts: dict) -> Measurement:
    """One finding per record, each independent of every other: the served readout's shape, the
    train F1 (or the holdout F1 of a champion's re-measurement) against the record's own claim,
    the additive scores, and a baseline's all-zero readout."""
    m = Measurement()
    for s in sessions:
        for position, rec in enumerate(records_of(s.log)):
            if not isinstance(rec, dict):
                m.findings.append(f"session {s.index} record {position + 1}: not a JSON object")
                continue
            seq = rec.get("seq")
            where = f"session {s.index} record {seq if _int(seq) else position + 1}"
            block = rec.get("search")
            tables = readout_words(rec)
            if tables is None:
                m.findings.append(f"{where}: no six-word functional_readout was served")
                continue
            m.readouts[(s.index, position)] = tables    # the POSITION: a wire value is never a key
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
            if not isinstance(pair, int) or isinstance(pair, bool):
                m.findings.append(f"{where}: the block names no pair, so no landscape can be built")
                continue
            land = ctx_of(pair)
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
    arm: str
    letter: str
    best_train: int = 0
    champion_genome: int = 0
    champion_born: int = 0
    champion_fit: int = 0
    champion_holdout: int | None = None
    column_moves: int = 0
    moves: list[list] = field(default_factory=list)          # [parent index, kind, bits, fitness]
    fits: list[int] = field(default_factory=list)
    population: list[bs.Individual] = field(default_factory=list)
    evals: int = 0


class Divergence(Exception):
    """The board's records stopped agreeing with the reference; the replay state is now
    meaningless, so the walk ends here."""


class Replay:
    """The reference engine driven BY the records: every observation is the readout the board
    served, every decision is the reference's own, and the two are compared at each step."""

    def __init__(self, plan: dict, view: bmaps.MapView, masks: list[int], truth: dict, readouts: dict,
                 seeds: list | None = None):
        self.budget = plan["budget_per_arm"]
        self.fid = plan["fitness"]
        self.master = plan["seed_derivation"]["master_seed"]
        self.pairs_total = plan["pairs"]
        # `seeds` has already been checked by `check_seeds`; this constructor converts, it
        # does not validate (the owner's input review of 2026-09-11 found the reverse).
        self.seeds = [tuple(x) for x in seeds] if seeds is not None else \
            bsess.pair_seeds(self.master, self.pairs_total)
        self.view = view
        self.masks = masks
        self.truth = truth
        self.readouts = readouts
        self.findings: list[str] = []
        self.arms: dict[tuple[int, str], ArmReplay] = {}
        self._land: dict[int, bl.Landscape] = {}
        self.replayed = 0

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
        # The records are taken in the order the session wrote them. `structure_findings` has
        # already established that they are objects with integer seqs, and `b2_records` that
        # the seq run is 1..n, so the position IS the order; a wire value orders nothing here.
        self.cursor = 0
        self.recs = records_of(s.log)
        self.sindex = s.index
        base, base_pos = self._take("the opening baseline")
        base_tables = self._readout(base, base_pos)
        if base.get("search") is not None:
            raise Divergence(f"session {s.index}: the opening record carries a search block")
        if base.get("genome") != BLANK_GENOME:
            raise Divergence(f"session {s.index}: the opening baseline's genome is {_short(base.get('genome'))}, "
                             f"not the blank genome — the starting population every arm of this session is "
                             f"replayed from, and what the firmware's genome_clear() writes at this bracket")
        for r in s.pairs:
            land = self.landscape(r)
            if land is None:
                raise Divergence(f"session {s.index}: pair {r} is outside the experiment's {self.pairs_total} pairs")
            order = bsess.arm_order(r)
            for arm in order:
                self.arms[(r, arm)] = self._arm(r, arm, land, base_tables)
            for arm in order:
                self._holdout(r, arm, land)
        closing, _ = self._take("the closing baseline")
        if closing.get("search") is not None:
            raise Divergence(f"session {s.index}: the closing record carries a search block")
        if closing.get("genome") != BLANK_GENOME:
            raise Divergence(f"session {s.index}: the closing baseline's genome is {_short(closing.get('genome'))}, "
                             f"not the blank genome, so the bracket is not the restoration it claims")
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

    # -------------------------------------------------- one arm's search

    def _arm(self, pair: int, arm: str, land: bl.Landscape, base_tables: list[int]) -> ArmReplay:
        letter = bsess.arm_letter(arm)
        arm_n = 0 if arm == bs.ARM_RANDOM_SAFE else 1
        oseed = self.seeds[pair][1]
        out = ArmReplay(pair=pair, arm=arm, letter=letter)
        rng = bc.Rng(oseed)
        base_fit = land.train_fitness(base_tables)
        pop = [bs.Individual(0, base_tables, base_fit, born=i) for i in range(bs.MU)]
        born, evals, best, generation, column_moves = bs.MU, 0, base_fit, 0, 0
        while evals < self.budget:
            children: list[bs.Individual] = []
            pending: list[dict] = []
            pop_before = list(pop)
            taken: list[dict] = []
            for _ in range(bs.LAMBDA):
                if evals == self.budget:
                    break
                pidx = rng.uniform(bs.MU)
                parent = pop[pidx]
                if arm == bs.ARM_RANDOM_SAFE:
                    bits, kind = bs.random_safe_move(rng), "random"
                else:
                    bits, kind = bs.map_guided_move(rng, self.view)
                if kind == "column":
                    column_moves += 1
                genome = bs.apply_move(parent.genome, bits)
                rec, position = self._take(f"evaluation {evals + 1} of pair {pair} arm {letter}")
                where = f"session {self.sindex} record {rec.get('seq')} (pair {pair} arm {letter} eval {evals + 1})"
                if rec.get("arm") != bsess.arm_wire_name(arm):
                    raise Divergence(f"{where}: the record's arm is {rec.get('arm')!r}")
                if rec.get("genome") != bc.genome_to_hex(genome):
                    raise Divergence(f"{where}: the board evaluated a genome the reference would not have "
                                     f"proposed from parent born {parent.born} under this move (autonomy replay failed)")
                block = rec.get("search")
                if not isinstance(block, dict):
                    raise Divergence(f"{where}: a scored search record carries no search block")
                if block.get("move") != {"bits": list(bits), "kind": kind}:
                    raise Divergence(f"{where}: the board's move {block.get('move')!r} is not the reference's "
                                     f"{{'bits': {list(bits)}, 'kind': {kind!r}}}")
                if block.get("parent_born") != parent.born:
                    raise Divergence(f"{where}: the board names parent born {block.get('parent_born')!r}; the "
                                     f"reference drew index {pidx}, born {parent.born}")
                tables = self._readout(rec, position)
                fit = land.train_fitness(tables)
                children.append(bs.Individual(genome, tables, fit, born))
                born += 1
                evals += 1
                if fit > best:
                    best = fit
                out.fits.append(fit)
                out.moves.append([pidx, kind, list(bits), fit])
                pending.append({"eval": evals, "fit": fit, "parent_born": parent.born, "bits": bits, "kind": kind,
                                "best": best, "column_moves": column_moves})
                taken.append(rec)
            pool = pop + children
            pool.sort(key=lambda ind: (-ind.fit, ind.born))
            pop = pool[:bs.MU]
            generation += 1
            for j, (m, rec) in enumerate(zip(pending, taken)):
                closed = (j == len(pending) - 1)             # the image selects on the last child of the generation
                want = bs.record_block(arm_n, letter, pair, land.seed, oseed, self.budget, m["eval"],
                                       generation if closed else generation - 1, m["best"], m["column_moves"],
                                       pop if closed else pop_before, m["eval"], m["fit"], m["parent_born"],
                                       m["bits"], m["kind"], closed, None)
                self._compare_block(rec, json.loads(want), pair, letter)
                self.replayed += 1
        out.best_train = best
        out.column_moves = column_moves
        out.evals = evals
        out.population = pop
        champion = min(pop, key=lambda ind: (-ind.fit, ind.born))
        out.champion_genome = champion.genome
        out.champion_born = champion.born
        out.champion_fit = champion.fit
        return out

    # -------------------------------------------------- one champion's re-measured holdout

    def _holdout(self, pair: int, arm: str, land: bl.Landscape) -> None:
        a = self.arms[(pair, arm)]
        arm_n = 0 if arm == bs.ARM_RANDOM_SAFE else 1
        oseed = self.seeds[pair][1]
        rec, position = self._take(f"the champion holdout of pair {pair} arm {a.letter}")
        where = f"session {self.sindex} record {rec.get('seq')} (pair {pair} arm {a.letter} holdout)"
        if rec.get("arm") != bsess.arm_wire_name(arm):
            raise Divergence(f"{where}: the record's arm is {rec.get('arm')!r}")
        if rec.get("genome") != bc.genome_to_hex(a.champion_genome):
            raise Divergence(f"{where}: the board re-measured a genome that is not the champion the "
                             f"replayed selection left (born {a.champion_born})")
        tables = self._readout(rec, position)
        if land.train_fitness(tables) != a.champion_fit:
            self.findings.append(f"{where}: the champion's re-measured readout gives train F1 "
                                 f"{land.train_fitness(tables)}, not the {a.champion_fit} the same genome "
                                 f"measured when it was evaluated")
        a.champion_holdout = land.holdout_fitness(tables)
        want = bs.record_block(arm_n, a.letter, pair, land.seed, oseed, self.budget, a.evals, self.generation_of(a),
                               a.best_train, a.column_moves, a.population, a.evals, None, None, None, None,
                               False, a.champion_holdout)
        self._compare_block(rec, json.loads(want), pair, a.letter)
        self.replayed += 1

    def generation_of(self, a: ArmReplay) -> int:
        """The generation counter the arm's last selection left."""
        full, rest = divmod(a.evals, bs.LAMBDA)
        return full + (1 if rest else 0)

    # -------------------------------------------------- the block comparison

    def _compare_block(self, rec: dict, want: dict, pair: int, letter: str) -> None:
        got = rec.get("search")
        where = f"session {self.sindex} record {rec.get('seq')} (pair {pair} arm {letter})"
        if not isinstance(got, dict):
            raise Divergence(f"{where}: no search block to compare with the replay")
        for k in sorted(want):
            if got.get(k) != want[k]:
                raise Divergence(f"{where}: the block's {k} is {_short(got.get(k))}, the replay's is "
                                 f"{_short(want[k])}")


def _short(v) -> str:
    text = json.dumps(v, sort_keys=True) if not isinstance(v, str) else repr(v)
    return text if len(text) <= 72 else text[:69] + "..."


# ------------------------------------------------------------------ the metrics against the prediction


def prediction_findings(arms: dict, prediction: dict, pairs_covered: list[int]) -> list[str]:
    """Per pair and per arm, the five predicted values — and the run's fitness sequence when
    the sessions together cover every preregistered pair."""
    f: list[str] = []
    by_pair = {p["pair"]: p for p in prediction["pairs"]}          # shapes checked by check_prediction
    for r in pairs_covered:
        want_pair = by_pair.get(r)
        if want_pair is None:
            f.append(f"pair {r}: the prediction has no such pair")
            continue
        for arm, letter in ((bs.ARM_RANDOM_SAFE, "A"), (bs.ARM_MAP_GUIDED, "B")):
            a = arms.get((r, arm))
            want = want_pair["runs"].get(letter)
            if a is None or want is None:
                f.append(f"pair {r} arm {letter}: nothing was replayed for it")
                continue
            got = {"best_train": a.best_train, "champion_holdout": a.champion_holdout,
                   "column_moves": a.column_moves,
                   "champion_genome_sha256": hashlib.sha256(bc.genome_to_hex(a.champion_genome).encode()).hexdigest(),
                   "moves_sha256": bp.sha256_json(a.moves)}
            for k in ("best_train", "champion_holdout", "column_moves", "champion_genome_sha256", "moves_sha256"):
                if got[k] != want.get(k):
                    f.append(f"pair {r} arm {letter}: {k} is {_short(got[k])}, the prediction's is {_short(want.get(k))}")
    return f


def fitness_sequence(arms: dict, pairs: list[int]) -> list[int]:
    """The run's fitness sequence in the preregistered order: per pair, both arms' evaluation
    fitnesses in the pair's arm order, then both champions' holdout values."""
    seq: list[int] = []
    for r in pairs:
        order = bsess.arm_order(r)
        for arm in order:
            seq.extend(arms[(r, arm)].fits)
        for arm in order:
            seq.append(arms[(r, arm)].champion_holdout)
    return seq


def deltas_of(arms: dict, pairs: list[int]) -> list[int]:
    return [arms[(r, bs.ARM_MAP_GUIDED)].best_train - arms[(r, bs.ARM_RANDOM_SAFE)].best_train for r in pairs]


# ------------------------------------------------------------------ the adjudication


def adjudicate(logs: list[dict], plan: dict, prediction: dict, consts: dict | None = None,
               common: bool = True, scope: str = "run", seeds: list | None = None) -> dict:
    """`logs` are the run's session logs in any order — they are ordered here by their declared
    pair slices. `consts` defaults to the INSTRUMENT's carrier constants (the PL that produced
    the scores); pass them only to test this module.

    `scope` is "run" — the whole experiment, which must cover every preregistered pair exactly
    once and which is the only scope that reports a primary — or "session", one or more
    sessions of a longer run, where covering a subset is the point and NOT a finding. A session
    scope never claims a primary, a fitness-sequence digest or the deltas, whatever it covers:
    the pooled primary is a property of the run, and this parameter must never be able to turn
    a partial run into the experiment's verdict. Every other check is identical.

    `seeds` replaces the pairs' DERIVED seeds for a session whose seed RULE is not B2's — B2Q
    draws under its own label and excludes B2's own set (preregistration §6a). It is never a way
    to choose seeds for a B2 session: the caller that supplies it owes that session's own rule,
    and the seeds actually used come back in the result."""
    out = {"tool": TOOL_VERSION, "session": SESSION, "scope": scope, "outcome": None, "findings": [],
           "kills": [], "not_checked_here": list(NOT_CHECKED_HERE)}
    try:
        if scope not in ("run", "session"):
            raise Refusal(f"scope {scope!r} is neither 'run' nor 'session'")
        if not logs:
            raise Refusal("no session log was given")
        check_plan(plan)
        check_prediction(prediction, plan)
        sessions = order_sessions(logs)
        consts = consts if consts is not None else instrument_constants()

        if seeds is not None:
            check_seeds(seeds, plan["pairs"])          # BEFORE anything converts or indexes it
        truth = bm.truth_mapping()
        masks = bl.universe_mask(truth)
        view = bmaps.MapView(bmaps.load_self_map(), bl.train_vectors())
        # The replay is built first because the measurement pass needs its per-pair landscapes;
        # the readouts that pass collects are then handed to it (it has none of its own).
        rp = Replay(plan, view, masks, truth, {}, seeds=seeds)

        findings: list[str] = []
        refused_sessions: list[int] = []
        for s in sessions:                                   # the record layer, session by session
            f = structure_findings(s)                        # first: the shapes everything below needs
            if not f:
                ctx = brec.context_from(plan, s.pair_first, s.pair_count, pair_seeds=rp.seeds)
                f = brec.validate_run_log(s.log, ctx, common=common)
            findings += [f"session {s.index}: {x}" for x in f]
            if f:
                refused_sessions.append(s.index)

        # The measurement pass is per record and independent of every other record, so it runs
        # even over a refused session: a served readout contradicting a self-report must not be
        # hidden by a shape finding elsewhere in the same log.
        m = measurement_pass(sessions, rp.landscape, consts)
        rp.readouts = m.readouts

        covered = sorted(r for s in sessions for r in s.pairs)
        out["sessions"] = [{"index": s.index, "pair_first": s.pair_first, "pair_count": s.pair_count,
                            "records": len(records_of(s.log))} for s in sessions]
        out["measurement"] = {"records_checked": m.checked, "readouts_served": len(m.readouts)}
        out["pair_seeds"] = [list(x) for x in rp.seeds]
        findings += _capped(m.findings, "measurement")

        # The replay is stateful and assumes the shape the record layer just checked; over a
        # document that layer refused it would prove nothing, so it does not run at all.
        if refused_sessions:
            out["replay"] = {"not_run": f"the record layer refused session(s) {refused_sessions}; a stateful "
                                        f"replay over records it named proves nothing about the board"}
        else:
            rp.run(sessions)
            out["replay"] = {"records_replayed": rp.replayed, "pairs": covered}
            findings += rp.findings

        complete = scope == "run" and covered == list(range(plan["pairs"]))
        if scope == "run" and not complete:
            findings.append(f"the sessions cover pairs {covered}, not the preregistered "
                            f"{list(range(plan['pairs']))}: no primary is computed from a partial run")
        if not refused_sessions and not rp.findings and all((r, arm) in rp.arms for r in covered
                                   for arm in (bs.ARM_RANDOM_SAFE, bs.ARM_MAP_GUIDED)) \
                and all(rp.arms[(r, arm)].champion_holdout is not None for r in covered
                        for arm in (bs.ARM_RANDOM_SAFE, bs.ARM_MAP_GUIDED)):
            findings += prediction_findings(rp.arms, prediction, covered)
            if complete:
                seq = fitness_sequence(rp.arms, covered)
                out["fitness_sequence_length"] = len(seq)
                out["fitness_sequence_sha256"] = bp.sha256_json(seq)
                if out["fitness_sequence_sha256"] != prediction.get("fitness_sequence_sha256"):
                    findings.append("the run's fitness sequence does not hash to the preregistered one")
                if len(seq) != prediction.get("fitness_sequence_length"):
                    findings.append(f"the run's fitness sequence is {len(seq)} values, the prediction's "
                                    f"{prediction.get('fitness_sequence_length')}")
                deltas = deltas_of(rp.arms, covered)
                out["deltas"] = deltas
                out["primary"] = bp.decision(deltas)
                if deltas != prediction.get("deltas"):
                    findings.append("the run's per-pair deltas are not the preregistered ones")
                if out["primary"] != prediction.get("predicted_primary"):
                    findings.append(f"the run's primary {out['primary']} is not the preregistered "
                                    f"{prediction.get('predicted_primary')}")
        out["findings"] = findings
        out["kills"] = _capped(m.kills, "measurement")
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
    ap.add_argument("--run-log", type=Path, action="append", default=[],
                    help="one session's run_log.json; repeat for a multi-session run")
    ap.add_argument("--evidence", type=Path, action="append", default=[],
                    help="an evidence directory holding run_log.json")
    ap.add_argument("--plan", type=Path, default=REPO_ROOT / "evidence/b2/plan.json")
    ap.add_argument("--prediction", type=Path, default=REPO_ROOT / "evidence/b2/prediction.json")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-common", action="store_true", help="skip the instrument's common validator")
    ap.add_argument("--seeds", type=Path, default=None,
                    help="a JSON array of [landscape, operator] pairs replacing the derivation, for a "
                         "session whose seed RULE is not B2's (B2Q); the derivation is used without it")
    ap.add_argument("--scope", choices=("run", "session"), default="run",
                    help="'run' (default) is the whole experiment and the only scope that reports a "
                         "primary; 'session' adjudicates one or more sessions of a longer run")
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
        res = adjudicate([load(p) for p in paths], load(a.plan), load(a.prediction),
                         common=not a.no_common, scope=a.scope,
                         seeds=None if a.seeds is None else load(a.seeds))
    except Refusal as exc:
        res = {"tool": TOOL_VERSION, "session": SESSION, "outcome": f"REFUSED: {exc}", "refusal": str(exc),
               "findings": [], "kills": []}
    except Exception as exc:              # a defect in THIS module. It is NOT reported as an
        import traceback                  # input refusal — but the result file is still written,
        res = {"tool": TOOL_VERSION, "session": SESSION,   # because a caller that gets no document
               "outcome": f"INTERNAL ERROR: {type(exc).__name__}: {exc}",   # learns nothing at all.
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

#!/usr/bin/env python3
"""B2 — adjudication of a run's sessions: the host's recomputation from the SERVED readouts
(pure; re-runnable; nothing here touches a board).

    b2_adjudicate.py --run-log <run_log.json> [--run-log …] [--plan …] [--prediction …] [--out …]

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
NOT_CHECKED_HERE = ("manifest pins", "carrier qualification", "instrument rate / deadline / CRC budgets",
                    "evidence exports", "ruling binding")


class Refusal(Exception):
    """The inputs are not a run this module can adjudicate — not a verdict about a board."""


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
    readouts: dict[int, list[int]] = field(default_factory=dict)      # (session, seq) -> words


def measurement_pass(sessions: list[SessionInput], ctx_of, consts: dict) -> Measurement:
    """One finding per record, each independent of every other: the served readout's shape, the
    train F1 (or the holdout F1 of a champion's re-measurement) against the record's own claim,
    the additive scores, and a baseline's all-zero readout."""
    m = Measurement()
    for s in sessions:
        for rec in s.log.get("loop_records") or []:
            if not isinstance(rec, dict):
                continue
            seq = rec.get("seq")
            where = f"session {s.index} record {seq}"
            block = rec.get("search")
            tables = readout_words(rec)
            if tables is None:
                m.findings.append(f"{where}: no six-word functional_readout was served")
                continue
            m.readouts[(s.index, seq)] = tables
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

    def __init__(self, plan: dict, view: bmaps.MapView, masks: list[int], truth: dict, readouts: dict):
        self.budget = plan["budget_per_arm"]
        self.fid = plan["fitness"]
        self.master = plan["seed_derivation"]["master_seed"]
        self.pairs_total = plan["pairs"]
        self.seeds = bsess.pair_seeds(self.master, self.pairs_total)
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
        recs = [r for r in (s.log.get("loop_records") or []) if isinstance(r, dict)]
        recs.sort(key=lambda r: r.get("seq") if isinstance(r.get("seq"), int) else 0)
        self.cursor = 0
        self.recs = recs
        self.sindex = s.index
        base = self._take("the opening baseline")
        base_tables = self._readout(base)
        if base.get("search") is not None:
            raise Divergence(f"session {s.index}: the opening record carries a search block")
        for r in s.pairs:
            land = self.landscape(r)
            if land is None:
                raise Divergence(f"session {s.index}: pair {r} is outside the experiment's {self.pairs_total} pairs")
            order = bsess.arm_order(r)
            for arm in order:
                self.arms[(r, arm)] = self._arm(r, arm, land, base_tables)
            for arm in order:
                self._holdout(r, arm, land)
        closing = self._take("the closing baseline")
        if closing.get("search") is not None:
            raise Divergence(f"session {s.index}: the closing record carries a search block")
        if self.cursor != len(self.recs):
            raise Divergence(f"session {s.index}: {len(self.recs) - self.cursor} records follow the closing baseline")

    def _take(self, what: str) -> dict:
        if self.cursor >= len(self.recs):
            raise Divergence(f"session {self.sindex}: the records end before {what}")
        rec = self.recs[self.cursor]
        self.cursor += 1
        if rec.get("outcome") != "SCORED":
            raise Divergence(f"session {self.sindex} record {rec.get('seq')}: outcome {rec.get('outcome')!r} — "
                             f"the replay stops at the first record that is not SCORED")
        return rec

    def _readout(self, rec: dict) -> list[int]:
        tables = self.readouts.get((self.sindex, rec.get("seq")))
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
                rec = self._take(f"evaluation {evals + 1} of pair {pair} arm {letter}")
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
                tables = self._readout(rec)
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
        rec = self._take(f"the champion holdout of pair {pair} arm {a.letter}")
        where = f"session {self.sindex} record {rec.get('seq')} (pair {pair} arm {a.letter} holdout)"
        if rec.get("arm") != bsess.arm_wire_name(arm):
            raise Divergence(f"{where}: the record's arm is {rec.get('arm')!r}")
        if rec.get("genome") != bc.genome_to_hex(a.champion_genome):
            raise Divergence(f"{where}: the board re-measured a genome that is not the champion the "
                             f"replayed selection left (born {a.champion_born})")
        tables = self._readout(rec)
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
    by_pair = {p["pair"]: p for p in prediction["pairs"]}
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
               common: bool = True) -> dict:
    """`logs` are the run's session logs in any order — they are ordered here by their declared
    pair slices. `consts` defaults to the INSTRUMENT's carrier constants (the PL that produced
    the scores); pass them only to test this module."""
    out = {"tool": TOOL_VERSION, "session": SESSION, "outcome": None, "findings": [], "kills": [],
           "not_checked_here": list(NOT_CHECKED_HERE)}
    try:
        if not logs:
            raise Refusal("no session log was given")
        for key in ("budget_per_arm", "fitness", "pairs", "seed_derivation", "map"):
            if key not in plan:
                raise Refusal(f"the plan carries no {key!r}")
        if not isinstance(plan["seed_derivation"], dict) or "master_seed" not in plan["seed_derivation"]:
            raise Refusal("the plan's seed_derivation carries no master_seed")
        if prediction.get("schema") != "b2_prediction":
            raise Refusal("the prediction is not a b2_prediction document")
        for key, want in (("fitness", plan["fitness"]), ("budget_per_arm", plan["budget_per_arm"])):
            if prediction.get(key) != want:
                raise Refusal(f"the prediction's {key} ({prediction.get(key)!r}) is not the plan's ({want!r})")
        sessions = order_sessions(logs)
        consts = consts if consts is not None else instrument_constants()

        truth = bm.truth_mapping()
        masks = bl.universe_mask(truth)
        view = bmaps.MapView(bmaps.load_self_map(), bl.train_vectors())
        # The replay is built first because the measurement pass needs its per-pair landscapes;
        # the readouts that pass collects are then handed to it (it has none of its own).
        rp = Replay(plan, view, masks, truth, {})

        findings: list[str] = []
        for s in sessions:                                   # the record layer, session by session
            ctx = brec.context_from(plan, s.pair_first, s.pair_count)
            findings += [f"session {s.index}: {x}" for x in brec.validate_run_log(s.log, ctx, common=common)]

        m = measurement_pass(sessions, rp.landscape, consts)
        rp.readouts = m.readouts
        rp.run(sessions)

        covered = sorted(r for s in sessions for r in s.pairs)
        out["sessions"] = [{"index": s.index, "pair_first": s.pair_first, "pair_count": s.pair_count,
                            "records": len(s.log.get("loop_records") or [])} for s in sessions]
        out["measurement"] = {"records_checked": m.checked, "readouts_served": len(m.readouts)}
        out["replay"] = {"records_replayed": rp.replayed, "pairs": covered}
        findings += _capped(m.findings, "measurement")
        findings += rp.findings

        complete = covered == list(range(plan["pairs"]))
        if not complete:
            findings.append(f"the sessions cover pairs {covered}, not the preregistered "
                            f"{list(range(plan['pairs']))}: no primary is computed from a partial run")
        if not rp.findings and all((r, arm) in rp.arms for r in covered
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
    a = ap.parse_args(argv)
    paths = list(a.run_log) + [d / "run_log.json" for d in a.evidence]
    if not paths:
        print("no --run-log and no --evidence", file=sys.stderr)
        return 2
    logs = [json.loads(p.read_text()) for p in paths]
    res = adjudicate(logs, json.loads(a.plan.read_text()), json.loads(a.prediction.read_text()),
                     common=not a.no_common)
    res["inputs"] = [str(p) for p in paths]
    text = json.dumps(res, indent=2, sort_keys=True)
    if a.out:
        a.out.write_text(text + "\n")
    print(text)
    return 0 if res["outcome"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

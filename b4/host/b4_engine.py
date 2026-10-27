#!/usr/bin/env python3
"""B4-FF — the search engine, a DERIVED copy of B2's (mu, lambda) = (4, 8), KMAX = 4 engine (`host/b2_search.py`,
recorded in `b4/IMPORT.json`) over the FF universe, with the execution boundary of `b4_execution` at every
observation (the revised 2b-2 scope, sections 3 and 5; the owner's rulings of 2026-10-18).

    r = run("R", task, port, operator_seed, budget)                       # random-safe
    r = run("F", task, port, operator_seed, budget)                       # frozen map LEARNED by a probe pass first
    r = run("F", task, port, operator_seed, budget, view=given_view)      # frozen map given (D / Omega / A0 — the view says what it is)
    r = run("O", task, port, operator_seed, budget)                       # online map, updated from every specimen
    r = run("X", task, port, operator_seed, budget, control_seed=c)      # control X-A: O over ADDRESSES relabelled by a fixed derangement

The arms differ in how the map is obtained and kept (R none; F learned once by single-bit probes from the base in a
seeded random order, then frozen; O learned from every specimen as it comes; X as O with the cartographer's input
relabelled, a shadow over the true input) and in the operator (random-safe, or half random-safe / half a group
move); the fitness, the population rule, the budget, the seeds, the stimulus and the termination are shared.

CONTROL X-A (the owner's ruling of 2026-10-18, section 4; `docs/b4_architecture.md` section 8). Before the base
observation, a derangement π of the n addresses is drawn ONCE from its own control RNG (`control_seed`; B3's
Fisher–Yates-with-rejection rule, every attempt recorded) — it never consumes the operator's generator and is never
redrawn or rejected after anything is learned. X's cartographer ingests each specimen with its genome's bits
relabelled through π (bit a -> bit π(a)) and the q grid untouched, so every seen effect is credited to the wrong
address; the shadow ingests the true genome. The ledger keeps the TRUE genome (what the search observed); the
cartographer's input is reconstructible from π and is never stored as if observed. After EVERY ingest the shadow
contract is checked in full (`b4_carto.isomorphic_addresses`): a difference is a CONTROL FAILURE — its own event
(`control_failure`), not DOMAIN, not a refusal, not a result. Its commit point: the observation that exposed it is
already in the ledger, scored and counted (a search child stays among the pending children); after it nothing is
drawn, observed, selected or learned, the generator is not rolled back. The residual structure (did π preserve the
operator's partition; `b4_carto.residual_structure`) is computed once at the end and reported — never read during the
run, never a reason to redraw or to select. The lane permutation of 2b-2 is not an arm: it stays as the
cartographer's symmetry test.

EVERY observation — the base, each probe, each search candidate, the holdout — goes through the one boundary. On
the first DOMAIN the run terminates: the event is recorded as it came (the state as it stood before that call), the
candidate has no fitness, no specimen, no place in the population; the generation's successful children stay
pending (no selection pretends the generation closed); nothing further is drawn, observed, scored, selected or
learned; the generator is not rolled back. The best-so-far trace is the measured prefix and nothing is added to it.
Any other refusal is recorded by its own name and stops the run likewise, never as DOMAIN. A completed run scores
its champion on the holdout stimulus once.

The ledger: one entry per successful observation, in order, with the phase, the genome, the config and stimulus
digests, the visible q grid, the fitness, the move, and the map version / commitment before and after; generation
closes with the population commitment. The engine holds the port and the task only — never a fabric, a mapping or
a hypothesis.

Provenance (the owner's P1-2 on 2eae943 and P1 on 8d2757a): the observation source's identity — the hypothesis's
path, sha256, version and fixture marker; the mapping's site, certificate and certificate sha256; the FABRIC's kind
(truth / permuted / dropout / custom), effect digest, dropout digest and count, and seed, as every trace header
carries them — is validated field by field on EVERY observation (`b4_execution.provenance_findings`: exact fields,
exact types, 64-hex digests; a malformed or missing identity is a `SourceRefusal`, recorded by that name), taken from
the first observation, required equal on every later one (a drift is a `SourceRefusal`), kept in `result.provenance`,
surfaced as `fixture` (the hypothesis) and `fabric_fixture` (the fabric is not the truth), and bound into every
ledger entry (`provenance_sha256`); a given frozen view is kept whole (`given_view`). A descriptor identifies the
input — digests only, never the effect table — and is never a licence to inspect the decode. A non-DOMAIN refusal is
recorded under one of the finite kinds `ValueError`, `ModelRefusal`, `SourceRefusal`.

The holdout (the owner's P2): the search's champion is fixed when the loop completes (`search_completed`); the
holdout observation then passes the same boundary; a DOMAIN there terminates the run with phase `holdout` — the
champion is kept as the search's result, `champion_holdout` stays None, `completed` stays False.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_carto as bc  # noqa: E402
import b4_execution as ex  # noqa: E402
import b4_landscape as bl  # noqa: E402
from b4_rng import Rng  # noqa: E402

MU = 4
LAMBDA = 8
KMAX = 4
ENGINE_VERSION = "b4-es-v0.1 (derived from b2-es-v1)"
ARMS = ("R", "F", "O", "X")


class ControlFailure(Exception):
    """Raised inside the engine when X's cartographer and its shadow stop agreeing under π: a defect of the control,
    recorded by its own name after the exposing observation is in the ledger."""

    def __init__(self, phase: str, attempt: int, seq: int, findings: list[str]):
        super().__init__("control failure")
        self.phase, self.attempt, self.seq, self.findings = phase, attempt, seq, list(findings)


@dataclass
class Individual:
    genome: int
    fit: int
    born: int


def random_safe_move(rng: Rng, n: int) -> list[int]:
    k = 1 + rng.uniform(KMAX)
    return sorted(rng.sample(list(range(n)), k))


def group_move(rng: Rng, view: bc.MapView) -> list[int]:
    g = list(view.groups[rng.uniform(len(view.groups))])
    s = 1 + rng.uniform(min(KMAX, len(g)))
    return sorted(rng.sample(g, s))


def map_guided_move(rng: Rng, view: bc.MapView | None, n: int) -> tuple[list[int], str]:
    if view is None or not view.groups:
        return random_safe_move(rng, n), "random"
    if rng.uniform(2) == 0:
        return random_safe_move(rng, n), "random"
    return group_move(rng, view), "group"


def apply_move(genome: int, bits: list[int]) -> int:
    for i in bits:
        genome ^= 1 << i
    return genome


def population_commitment(pop: list[Individual]) -> str:
    return ex.sha256_json([[i.genome, i.fit, i.born] for i in pop])


@dataclass
class RunResult:
    arm: str
    task_digest: str                          # the task by its digest only (task-v0.2 / H): the engine never holds the landscape seed
    operator_seed: int
    budget: int
    completed: bool = False
    terminal: dict | None = None
    other_refusal: dict | None = None
    observations: int = 0                     # successful observations, all phases
    evals: int = 0                            # successful search evaluations
    best_trace: list = field(default_factory=list)   # the measured prefix: best-so-far after each successful search evaluation
    base_fit: int | None = None
    champion: dict | None = None
    champion_holdout: int | None = None
    champion_holdout_nones: int | None = None
    population: list = field(default_factory=list)
    pending_children: list = field(default_factory=list)
    ledger: list = field(default_factory=list)
    generation_closes: list = field(default_factory=list)
    group_moves: int = 0
    cost: dict = field(default_factory=lambda: {"base": 0, "probes": 0, "search": 0, "holdout": 0})
    map_origin: str = "none"
    map_privileged: bool = False
    map_version_final: int = 0
    map_commitment_final: str = ""
    map_specimens_final: int = 0              # specimens the live cartographer holds: never more than the ledger learned
    map_multi_bit_pairs_final: int = 0
    frozen_view: list | None = None
    given_view: dict | None = None            # a frozen map handed in: its groups, commitment, privilege and provenance chain
    rng_state_final: int = 0
    x_isomorphism_findings: list | None = None
    provenance: dict | None = None            # the observation source's identity, from the first observation and equal for all:
                                              # the hypothesis (path, sha256, version, fixture) and the mapping (site, certificate sha256)
    search_completed: bool = False            # the search loop ran to its budget (a DOMAIN at the holdout leaves this True, completed False)
    fixture: bool | None = None               # the HYPOTHESIS fixture marker, surfaced at the top level (provenance.hypothesis.fixture)
    fabric_fixture: bool | None = None        # the FABRIC is not the truth (permuted / dropout / custom): provenance.fabric.kind != "truth"
    x_control_seed: int | None = None         # control X-A: the control RNG's seed (never the operator's)
    x_perm: list | None = None                # the derangement π drawn from it before the base observation, fixed for the run
    x_perm_attempts: list | None = None       # every Fisher–Yates attempt of the rule, the last being π (auditable, never chosen)
    x_residual: dict | None = None            # post hoc: did π preserve the operator's partition (b4_carto.residual_structure)
    control_failure: dict | None = None       # the shadow contract broken: its own event, after the exposing observation

    def as_dict(self) -> dict:
        d = dict(self.__dict__)
        return d


def run(arm: str, task: ex.PublicTask, port: ex.ObservationPort, operator_seed: int, budget: int,
        view: bc.MapView | None = None, control_seed: int | None = None) -> RunResult:
    if arm not in ARMS:
        raise ValueError(arm)
    if arm == "X" and not (isinstance(control_seed, int) and not isinstance(control_seed, bool)):
        raise ValueError("control X needs its own control seed")
    if arm != "X" and control_seed is not None:
        raise ValueError("a control seed is for control X only")
    if view is not None and arm != "F":
        raise ValueError("a given view is for the frozen arm only")
    n = len(task.addresses)
    rng = Rng(operator_seed)
    res = RunResult(arm, task.digest(), operator_seed, budget)
    x_perm: list[int] | None = None
    if arm == "X":
        # π from the CONTROL generator, before any observation; fixed for the run, every attempt kept
        attempts = bc.derangement_attempts(control_seed, n)
        x_perm = attempts[-1]
        res.x_control_seed, res.x_perm, res.x_perm_attempts = control_seed, list(x_perm), [list(p) for p in attempts]
    stim_sha = ex.sha256_json(list(task.stimulus))
    carto = bc.ObservationCarto(n) if arm in ("F", "O", "X") and view is None else None
    shadow = bc.ObservationCarto(n) if arm == "X" else None
    frozen: bc.MapView | None = view
    if view is not None:
        res.map_origin, res.map_privileged = view.origin, view.privileged
        res.frozen_view = [list(g) for g in view.groups]
        res.given_view = view.as_dict()
    pop: list[Individual] = []
    children: list[Individual] = []
    seq = 0
    attempt = 0

    def ctx() -> dict:
        return {"task_digest": res.task_digest, "operator_seed": operator_seed, "budget": budget, "successful_observations": res.observations,
                "rng_state": rng.state(), "population_commitment": population_commitment(pop),
                "map_commitment": (carto.commitment() if carto else (frozen.commitment if frozen else "")),
                "map_version": (carto.version if carto else (frozen.version if frozen else 0))}

    def observe(genome: int, stimulus, phase: str) -> dict:
        nonlocal attempt
        attempt += 1
        trace = ex.observe_candidate(port, genome, stimulus, phase, attempt, ctx())
        hdr = {k: trace.get(k) for k in ("hypothesis", "mapping", "fabric")} if isinstance(trace, dict) else None
        f = ex.provenance_findings(hdr)
        if f:
            raise ex.SourceRefusal("the observation source's identity is malformed: " + "; ".join(f))
        if res.provenance is None:
            res.provenance = hdr
            res.fixture = hdr["hypothesis"]["fixture"]
            res.fabric_fixture = hdr["fabric"]["kind"] != "truth"
        elif hdr != res.provenance:
            raise ex.SourceRefusal("the observation source's identity changed between observations")
        res.observations += 1
        return trace

    def learn(seq_: int, genome: int, grid: list) -> tuple[int, int, str, list[str]]:
        """Feed the cartographer(s); return (version_before, version_after, commitment_after, control findings)."""
        if carto is None:
            return ((frozen.version, frozen.version, frozen.commitment) if frozen else (0, 0, "")) + ([],)
        before = carto.version
        findings: list[str] = []
        if arm == "X":
            carto.ingest(seq_, bc.relabel_genome(genome, x_perm), stim_sha, grid)     # the addresses relabelled, the grid untouched
            shadow.ingest(seq_, genome, stim_sha, grid)                                # the truth, for the contract only
            findings = bc.isomorphic_addresses(carto, shadow, x_perm)                  # after EVERY ingest
        else:
            carto.ingest(seq_, genome, stim_sha, grid)
        return before, carto.version, carto.commitment(), findings

    def entry(phase: str, genome: int, trace: dict, fit: int, nones: int, **more) -> dict:
        nonlocal seq
        seq += 1
        grid = [s["q_after"] for s in trace["steps"]]
        vb, va, cm, control = learn(seq, genome, grid) if phase != "holdout" else (((frozen.version, frozen.version, frozen.commitment) if frozen else ((carto.version, carto.version, carto.commitment()) if carto else (0, 0, ""))) + ([],))
        e = {"seq": seq, "phase": phase, "genome": genome, "genome_hex": ex.genome_hex(genome, n), "config_sha256": ex.sha256_json(ex.genome_to_config(genome, task.addresses)),
             "provenance_sha256": ex.sha256_json(res.provenance), "fixture": res.fixture,
             "stimulus_sha256": ex.sha256_json(list(task.holdout_stimulus if phase == "holdout" else task.stimulus)),
             "trace_sha256": ex.sha256_json(grid), "q_grid": grid, "fitness": fit, "none_cells": nones,
             "map_version_before": vb, "map_version_after": va, "map_commitment_after": cm}
        e.update(more)
        res.ledger.append(e)
        if control:
            # the commit point of a control failure: the exposing observation is in the ledger, scored and counted
            raise ControlFailure(phase, attempt, seq, control)
        return e

    phase = "base"
    try:
        trace = observe(task.base_genome, task.stimulus, "base")
        base_fit, nones = bl.score(trace, task)
        res.base_fit = base_fit
        res.cost["base"] = 1
        entry("base", task.base_genome, trace, base_fit, nones, parent_born=None, bits=[], move_kind="base", best=base_fit)
        pop = [Individual(task.base_genome, base_fit, i) for i in range(MU)]
        born = MU
        best = base_fit
        if arm == "F" and frozen is None:
            phase = "probe"
            order = rng.sample(list(range(n)), n)             # a seeded random order; closed-book
            for a in order:
                g = task.base_genome ^ (1 << a)
                trace = observe(g, task.stimulus, "probe")
                fit, nones = bl.score(trace, task)
                res.cost["probes"] += 1
                entry("probe", g, trace, fit, nones, parent_born=None, bits=[a], move_kind="probe", best=best)
            frozen = carto.view()
            res.frozen_view = [list(g) for g in frozen.groups]
            res.map_origin = "learned"
            carto = None                                        # frozen from here: no further learning
        phase = "search"
        generation = 0
        while res.evals < budget:
            children = []
            pop_before = list(pop)
            for _ in range(LAMBDA):
                if res.evals == budget:
                    break
                pidx = rng.uniform(MU)
                parent = pop[pidx]
                if arm == "R":
                    bits, kind = random_safe_move(rng, n), "random"
                else:
                    live = frozen if arm == "F" else (carto.view() if carto else None)
                    bits, kind = map_guided_move(rng, live, n)
                if kind == "group":
                    res.group_moves += 1
                genome = apply_move(parent.genome, bits)
                trace = observe(genome, task.stimulus, "search")
                fit, nones = bl.score(trace, task)
                children.append(Individual(genome, fit, born))
                born += 1
                res.evals += 1
                res.cost["search"] += 1
                if fit > best:
                    best = fit
                res.best_trace.append(best)
                entry("search", genome, trace, fit, nones, parent_born=parent.born, bits=bits, move_kind=kind, best=best, generation=generation)
            pool = pop + children
            pool.sort(key=lambda ind: (-ind.fit, ind.born))
            pop = pool[:MU]
            children = []
            generation += 1
            res.generation_closes.append({"generation": generation, "after_seq": seq, "population_commitment": population_commitment(pop),
                                          "population": [[i.genome, i.fit, i.born] for i in pop], "before": [[i.genome, i.fit, i.born] for i in pop_before]})
        res.search_completed = True
        champion = min(pop, key=lambda ind: (-ind.fit, ind.born))
        res.champion = {"genome": champion.genome, "fit": champion.fit, "born": champion.born}    # the search's result, kept even if the holdout is refused
        phase = "holdout"
        trace = observe(champion.genome, task.holdout_stimulus, "holdout")
        res.champion_holdout, res.champion_holdout_nones = bl.score_holdout(trace, task)
        res.cost["holdout"] = 1
        entry("holdout", champion.genome, trace, res.champion_holdout, res.champion_holdout_nones, parent_born=champion.born, bits=[], move_kind="holdout", best=best)
        res.completed = True                                       # only with the holdout observed
    except ex.Terminated as t:
        res.terminal = t.event.as_dict()
        res.completed = False
    except ControlFailure as c:                                   # the shadow contract broken: its own event, never DOMAIN or a refusal
        res.control_failure = {"phase": c.phase, "attempt": c.attempt, "seq": c.seq, "findings": c.findings,
                               "successful_observations": res.observations, "rng_state": rng.state(),
                               "population_commitment": population_commitment(pop),
                               "map_version": carto.version, "map_commitment": carto.commitment(), "shadow_commitment": shadow.commitment()}
        res.completed = False
    except (ValueError, ex.fm.ModelRefusal) as e:                 # not DOMAIN (DomainRefusal is caught above as Terminated)
        res.other_refusal = ex.OtherRefusal(ex.refusal_kind(e), str(e), phase, attempt).as_dict()   # a finite kind
        res.completed = False
    res.population = [[i.genome, i.fit, i.born] for i in pop]
    res.pending_children = [[i.genome, i.fit, i.born] for i in children]
    res.rng_state_final = rng.state()
    live_carto = carto
    if live_carto is not None:
        res.map_version_final, res.map_commitment_final = live_carto.version, live_carto.commitment()
        res.map_specimens_final, res.map_multi_bit_pairs_final = len(live_carto.specimens), live_carto.multi_bit_pairs
        res.map_origin = "online" if arm in ("O", "X") else res.map_origin
        if arm == "X":
            res.x_isomorphism_findings = bc.isomorphic_addresses(live_carto, shadow, x_perm)
            res.x_residual = bc.residual_structure(live_carto.view(), shadow.view())     # post hoc only
    elif frozen is not None:
        res.map_version_final, res.map_commitment_final = frozen.version, frozen.commitment
    return res

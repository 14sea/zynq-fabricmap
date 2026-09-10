#!/usr/bin/env python3
"""B2 — the search engine shared by both arms, the two operators, and the paired run
(docs/b2_architecture.md §4–§5). Host-only; the Python reference of the future image.

Engine: (mu + lambda) evolution strategy, mu = 4, lambda = 8, truncation selection, ties by
age (older survives; every individual has a unique birth index so no further rule is
needed), initial population = mu copies of the base (all-zero). One child = one
evaluation; the budget counts evaluations. Best-so-far is a prefix property: a run with a
larger budget contains every smaller-budget run, so one run per (arm, landscape) serves
every budget of the gate's grid.

Operators (a move = 1..KMAX distinct universe bits to flip in the parent):
  random-safe : k ~ U{1..KMAX}; k bits uniform without replacement from the 292;
  map-guided  : with probability 1/2 the random-safe move; otherwise a COLUMN move — a
                train column the map names, drawn uniformly; a non-empty subset (size
                1..min(KMAX, |column|)) of the bits the map places there, drawn uniformly.
  A map that names no column reduces the map-guided operator to random-safe (q = 1).

RNG: the instrument's xorshift64 (b1_carto.Rng); every draw is `uniform` / `sample`, so
the C image can reproduce the stream exactly.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
from b2_maps import MapView  # noqa: E402

MU = 4
LAMBDA = 8
KMAX = 4
ENGINE_VERSION = "b2-es-v1"
ARM_RANDOM_SAFE = "random_safe"
ARM_MAP_GUIDED = "map_guided"


class ModelFabric:
    """The additive fabric model (b1_model.Fabric's mapping) with an incremental toggle:
    the child's tables are the parent's with the moved bits' positions flipped. Equal to
    the from-scratch readout on an additive fabric (tests/test_b2_search.py)."""

    def __init__(self, truth: dict | None = None):
        truth = truth or bm.truth_mapping()
        self.pos = [truth["mapping"][i] for i in range(bc.N)]
        self.fabric = bm.Fabric(truth["mapping"])

    def __call__(self, genome: int) -> list[int]:
        return self.fabric(genome)

    def toggle(self, tables: list[int], bits: list[int]) -> list[int]:
        t = list(tables)
        for i in bits:
            k, v = self.pos[i]
            t[k] ^= 1 << v
        return t


# ------------------------------------------------------------------ the operators

def random_safe_move(rng: bc.Rng) -> list[int]:
    k = 1 + rng.uniform(KMAX)
    return sorted(rng.sample(list(range(bc.N)), k))


def column_move(rng: bc.Rng, view: MapView) -> list[int]:
    v = view.column_keys[rng.uniform(len(view.column_keys))]
    bits = view.columns[v]
    s = 1 + rng.uniform(min(KMAX, len(bits)))
    return sorted(rng.sample(bits, s))


def map_guided_move(rng: bc.Rng, view: MapView) -> tuple[list[int], str]:
    if not view.column_keys:
        return random_safe_move(rng), "random"
    if rng.uniform(2) == 0:
        return random_safe_move(rng), "random"
    return column_move(rng, view), "column"


def apply_move(genome: int, bits: list[int]) -> int:
    for i in bits:
        genome ^= 1 << i
    return genome


# ------------------------------------------------------------------ the engine

@dataclass
class Individual:
    genome: int
    tables: list[int]
    fit: int
    born: int


@dataclass
class RunResult:
    arm: str
    budget: int
    best_trace: list[int]            # best-so-far after evaluation 1..budget
    champion: Individual
    champion_holdout: int
    moves: list[dict] = field(default_factory=list)
    population_fit: list[int] = field(default_factory=list)
    column_moves: int = 0
    population_trace: list[list[tuple[int, int]]] = field(default_factory=list)   # (fit, born) after each selection


def run(arm: str, landscape: bl.Landscape, view: MapView | None, operator_seed: int, budget: int,
        fabric: ModelFabric, log_moves: bool = False) -> RunResult:
    if arm not in (ARM_RANDOM_SAFE, ARM_MAP_GUIDED):
        raise ValueError(arm)
    if arm == ARM_MAP_GUIDED and view is None:
        raise ValueError("map_guided needs a MapView (an empty one is the random-safe endpoint)")
    rng = bc.Rng(operator_seed)
    base_tables = fabric(0)
    base_fit = landscape.train_fitness(base_tables)
    pop = [Individual(0, base_tables, base_fit, born=i) for i in range(MU)]
    born = MU
    evals = 0
    best = base_fit
    trace: list[int] = []
    moves: list[dict] = []
    population: list[list[tuple[int, int]]] = []
    column_moves = 0
    while evals < budget:
        children: list[Individual] = []
        for _ in range(LAMBDA):
            if evals == budget:
                break
            pidx = rng.uniform(MU)
            parent = pop[pidx]
            if arm == ARM_RANDOM_SAFE:
                bits, kind = random_safe_move(rng), "random"
            else:
                bits, kind = map_guided_move(rng, view)
            if kind == "column":
                column_moves += 1
            genome = apply_move(parent.genome, bits)
            tables = fabric.toggle(parent.tables, bits)
            fit = landscape.train_fitness(tables)
            children.append(Individual(genome, tables, fit, born))
            born += 1
            evals += 1
            if fit > best:
                best = fit
            trace.append(best)
            if log_moves:
                moves.append({"eval": evals, "parent": pidx, "parent_born": parent.born, "kind": kind, "bits": bits, "fit": fit})
        pool = pop + children
        pool.sort(key=lambda ind: (-ind.fit, ind.born))
        pop = pool[:MU]
        if log_moves:
            population.append([(ind.fit, ind.born) for ind in pop])
    champion = min(pop, key=lambda ind: (-ind.fit, ind.born))
    return RunResult(arm=arm, budget=budget, best_trace=trace, champion=champion,
                     champion_holdout=landscape.holdout_fitness(champion.tables), moves=moves,
                     population_fit=[ind.fit for ind in pop], column_moves=column_moves,
                     population_trace=population)


# ------------------------------------------------------------------ seeds

EXCLUDED_SEEDS = frozenset([1, 2, 3, 5, 11, 77, 99, 1234, 4321, 195948557, 324805736, 521288629, 1278624577,
                            1278628687, 1281816666, 2119807262, 3735928559, 4294967295,
                            1123460948, 176359248])          # B1's master and qualification seeds


def master_seed(label: str, commit: str) -> int:
    import hashlib
    d = hashlib.sha256(f"{label}|{commit}".encode()).digest()
    return int.from_bytes(d[:4], "big")


def pair_seeds(master: int, count: int, exclude: frozenset | set = frozenset()) -> list[tuple[int, int]]:
    """(landscape_seed, operator_seed) per pair, drawn from one stream off the master;
    every seed is 32-bit, none is an excluded seed (the fixed list plus `exclude` — the
    caller passes every frozen set the new draw must avoid: different labels give
    different streams but do NOT guarantee disjointness, so it is enforced here and the
    plan records which sets were excluded), all are distinct."""
    rng = bc.Rng(master)
    out: list[tuple[int, int]] = []
    seen: set[int] = set(EXCLUDED_SEEDS) | set(exclude)
    while len(out) < count:
        l_seed = rng.next32()
        o_seed = rng.next32()
        if l_seed in seen or o_seed in seen or l_seed == o_seed:
            continue
        seen.add(l_seed)
        seen.add(o_seed)
        out.append((l_seed, o_seed))
    return out

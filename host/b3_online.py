#!/usr/bin/env python3
"""B3 — the closed loop, host simulation (docs/b3_architecture.md).

Three arms on B2's engine, landscape and operator (nothing tuned):
  * R  random-safe            — no map, ever (B2's arm A);
  * F  frozen self-map        — B1's map, paid for up front (333 probes: B1's budget);
  * O  online-updating map    — starts EMPTY; every evaluation is a specimen: the child's
                                readout XOR the parent's is the set of positions the moved
                                bits toggled, and the specimen cartographer intersects
                                candidate sets until an address is decoded. The operator
                                is B2's map-guided operator over the CURRENT map version;
                                no dedicated probe is ever spent.

The specimen ledger (schemas/specimen_ledger.schema.json) is written by the online arm:
(map_version, seq, parent, intervention, behaviour_delta, fitness, confidence, decoded).
Two accountings are reported: search benefit at a search budget B (each arm's own
evaluations), and end-to-end benefit at a total budget T, where the frozen arm's map cost
(333) is charged first (its search starts at T = 333).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_carto as bc  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_search as bs  # noqa: E402
from b2_maps import MapView  # noqa: E402

B1_MAP_COST = 333            # B1's budget: 9 code probes + 292 confirmations + 32 pairs
LEDGER_VERSION = "specimen_ledger 1.0.0"


def positions_of(delta_tables: list[int]) -> list[tuple[int, int]]:
    out = []
    for k in range(bl.LUTS):
        t = delta_tables[k]
        while t:
            low = t & -t
            out.append((k, low.bit_length() - 1))
            t ^= low
    return out


@dataclass
class SpecimenCarto:
    """Candidate-set intersection over specimens: address i's candidate positions start as
    'unknown' (None); a specimen with moved bits M and toggled positions D (|D| = |M|)
    intersects each i in M with D; a singleton is a decode (confidence 2); a decoded
    position is removed from every other candidate set. Anomalies (|D| != |M|, an empty
    intersection) are counted and the specimen is not used."""
    candidates: dict[int, set | None] = field(default_factory=dict)
    decoded: dict[int, tuple[int, int]] = field(default_factory=dict)
    taken: set = field(default_factory=set)
    anomalies: int = 0
    version: int = 0

    def observe(self, moved: list[int], delta: list[tuple[int, int]]) -> list[int]:
        """Returns the addresses decoded by this specimen (the map version bumps once if any)."""
        if len(delta) != len(moved):
            self.anomalies += 1
            return []
        dset = set(delta) - self.taken
        newly: list[int] = []
        # single-bit specimens decode directly; multi-bit ones narrow
        pending = [i for i in moved if i not in self.decoded]
        if len(pending) == 0:
            return []
        for i in pending:
            c = self.candidates.get(i)
            c2 = set(dset) if c is None else (c & dset)
            if not c2:
                self.anomalies += 1
                return []
            self.candidates[i] = c2
        changed = True
        while changed:                      # closure over EVERY undecoded address with a candidate set
            changed = False
            for i in [i for i, c in self.candidates.items() if c is not None and i not in self.decoded]:
                c = self.candidates[i] - self.taken
                if len(c) == 1:
                    pos = next(iter(c))
                    self.decoded[i] = pos
                    self.taken.add(pos)
                    newly.append(i)
                    changed = True
                elif not c:
                    self.anomalies += 1
                    self.candidates[i] = None
        if newly:
            self.version += 1
        return newly

    def map_view(self, train_vectors: list[int]) -> MapView:
        """The current map as the operator sees it (decoded entries only)."""
        train = set(train_vectors)
        view = MapView(None, train_vectors)
        for i, (k, v) in self.decoded.items():
            if v in train:
                view.columns.setdefault(v, []).append(i)
        for v in view.columns:
            view.columns[v].sort()
        view.column_keys = sorted(view.columns)
        return view

    def self_map_entries(self) -> list[dict]:
        return [{"genome_bit": i, "relation": {"kind": "lut_init", "lut_index": k, "init_index": v}, "confidence": 2, "state": "confirmed"}
                for i, (k, v) in sorted(self.decoded.items())]


@dataclass
class OnlineResult:
    best_trace: list[int]
    decoded_trace: list[int]            # decoded addresses after evaluation 1..budget
    version_trace: list[int]
    ledger: list[dict]
    anomalies: int
    champion_holdout: int
    column_moves: int


def run_online(landscape: bl.Landscape, operator_seed: int, budget: int, fabric: bs.ModelFabric, keep_ledger: bool = True) -> OnlineResult:
    rng = bc.Rng(operator_seed)
    carto = SpecimenCarto()
    view = carto.map_view(landscape.train)
    base_tables = fabric(0)
    base_fit = landscape.train_fitness(base_tables)
    pop = [bs.Individual(0, base_tables, base_fit, born=i) for i in range(bs.MU)]
    born = bs.MU
    evals = 0
    best = base_fit
    trace, dtrace, vtrace, ledger = [], [], [], []
    column_moves = 0
    while evals < budget:
        children = []
        for _ in range(bs.LAMBDA):
            if evals == budget:
                break
            pidx = rng.uniform(bs.MU)
            parent = pop[pidx]
            bits, kind = bs.map_guided_move(rng, view)
            if kind == "column":
                column_moves += 1
            genome = bs.apply_move(parent.genome, bits)
            tables = fabric.toggle(parent.tables, bits)
            fit = landscape.train_fitness(tables)
            delta = positions_of([tables[k] ^ parent.tables[k] for k in range(bl.LUTS)])
            version_before = carto.version
            newly = carto.observe(bits, delta)
            if newly:
                view = carto.map_view(landscape.train)
            children.append(bs.Individual(genome, tables, fit, born))
            born += 1
            evals += 1
            best = max(best, fit)
            trace.append(best)
            dtrace.append(len(carto.decoded))
            vtrace.append(carto.version)
            if keep_ledger:
                ledger.append({"seq": evals, "map_version": version_before, "parent_born": parent.born, "intervention": bits,
                               "move_kind": kind, "behaviour_delta": [[k, v] for k, v in delta], "fitness": fit,
                               "confidence": 2 if len(bits) == 1 else 1, "decoded": [[i, carto.decoded[i][0], carto.decoded[i][1]] for i in newly],
                               "map_version_after": carto.version})
        pool = pop + children
        pool.sort(key=lambda ind: (-ind.fit, ind.born))
        pop = pool[:bs.MU]
    champion = min(pop, key=lambda ind: (-ind.fit, ind.born))
    return OnlineResult(trace, dtrace, vtrace, ledger, carto.anomalies, landscape.holdout_fitness(champion.tables), column_moves)

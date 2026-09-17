#!/usr/bin/env python3
"""B3 lifecycle 1 — the specimen cartographer (the B3 implementation, under b3/).

A copy of the frozen host reference `host/b3_online.SpecimenCarto` v1.1 (B2 pins that file; it is
imported by the tests as the equivalence oracle and never edited). Semantics unchanged
(docs/b3_architecture.md v0.2.3 §3): a specimen is (moved addresses M, toggled positions D);
|M| = 1 decodes directly; |M| > 1 narrows by intersection with a global closure; every check runs
on a copy and the state is committed only if the whole specimen is consistent, otherwise the
anomaly count is incremented and nothing else changes; the map version bumps on a decode.

What this copy adds (§7): the **state commitment** `state_text` / `state_sha256` — the projection
of the cartographer state the board commits to on every O-arm search record, in the pipe-text
form the C twin (`b3/firmware/b3_carto.c`, `b3_carto_state_hex`) will reproduce byte for byte:
`<carto_version>|<version>|<anomalies>|<decoded i:k:v; sorted by i>|<candidates i:k.v,k.v; sorted>`.
"""
from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "host") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_carto as bc  # noqa: E402
import b2_landscape as bl  # noqa: E402

CARTO_VERSION = "specimen-carto-v1.1"
POSITIONS = bl.LUTS * bl.VECTORS          # 384 (LUT, vector) positions; index = 64 * LUT + vector


def positions_of(delta_tables: list[int]) -> list[tuple[int, int]]:
    """The (LUT, vector) positions set in the six delta words, in (k, v) order."""
    out = []
    for k in range(bl.LUTS):
        t = delta_tables[k]
        while t:
            low = t & -t
            out.append((k, low.bit_length() - 1))
            t ^= low
    return out


class Inconsistent(Exception):
    """A specimen that contradicts the state or itself; the caller counts it and changes nothing."""


@dataclass
class SpecimenCarto:
    candidates: dict[int, set] = field(default_factory=dict)
    decoded: dict[int, tuple[int, int]] = field(default_factory=dict)
    taken: set = field(default_factory=set)
    anomalies: int = 0
    version: int = 0

    def _check(self, moved: list[int], delta: list[tuple[int, int]]):
        if len(set(moved)) != len(moved) or any(not (0 <= i < bc.N) for i in moved) or not moved:
            raise Inconsistent("malformed intervention")
        dl = [tuple(p) for p in delta]
        dset = set(dl)
        if len(dset) != len(dl) or any(not (0 <= k < bl.LUTS and 0 <= v < bl.VECTORS) for k, v in dset):
            raise Inconsistent("malformed delta")
        if len(dset) != len(moved):
            raise Inconsistent("|delta| != |intervention|")
        remaining = set(dset)
        for i in moved:
            if i in self.decoded:
                pos = self.decoded[i]
                if pos not in remaining:
                    raise Inconsistent(f"decoded address {i} at {pos} did not toggle")
                remaining.remove(pos)
        if remaining & self.taken:
            raise Inconsistent("a toggled position belongs to a decoded address that was not moved")
        pending = [i for i in moved if i not in self.decoded]
        cand = {i: set(c) for i, c in self.candidates.items()}
        for i in pending:
            c2 = set(remaining) if i not in cand else (cand[i] & remaining)
            if not c2:
                raise Inconsistent(f"empty candidate set for address {i}")
            cand[i] = c2
        decoded = dict(self.decoded)
        taken = set(self.taken)
        newly: list[int] = []
        changed = True
        while changed:
            changed = False
            for i in [i for i in cand if i not in decoded]:
                c = cand[i] - taken
                if len(c) == 1:
                    pos = next(iter(c))
                    decoded[i] = pos
                    taken.add(pos)
                    newly.append(i)
                    changed = True
                elif not c:
                    raise Inconsistent(f"closure conflict at address {i}")
        return cand, decoded, taken, newly

    def observe(self, moved: list[int], delta: list[tuple[int, int]]) -> list[int]:
        """The addresses this specimen decoded (the version bumps once if any); a refused specimen
        increments `anomalies` and changes nothing else."""
        try:
            cand, decoded, taken, newly = self._check(moved, delta)
        except Inconsistent:
            self.anomalies += 1
            return []
        self.candidates = cand
        self.decoded = decoded
        self.taken = taken
        if newly:
            self.version += 1
        return newly

    def snapshot(self) -> tuple:
        return ({i: frozenset(c) for i, c in self.candidates.items()}, dict(self.decoded), frozenset(self.taken), self.version)

    # ---- the commitment (docs/b3_architecture.md v0.2.3 §7) -------------------------------------
    def state_text(self) -> str:
        dec = ";".join(f"{i}:{k}:{v}" for i, (k, v) in sorted(self.decoded.items()))
        cand = ";".join(f"{i}:" + ",".join(f"{k}.{v}" for k, v in sorted(c)) for i, c in sorted(self.candidates.items()))
        return f"{CARTO_VERSION}|{self.version}|{self.anomalies}|{dec}|{cand}"

    def state_sha256(self) -> str:
        return hashlib.sha256(self.state_text().encode()).hexdigest()

    # ---- what the operator and the renderer see ------------------------------------------------
    def map_view(self, train_vectors: list[int]):
        from b2_maps import MapView
        train = set(train_vectors)
        view = MapView(None, train_vectors)
        for i, (k, v) in self.decoded.items():
            if v in train:
                view.columns.setdefault(v, []).append(i)
        for v in view.columns:
            view.columns[v].sort()
        view.column_keys = sorted(view.columns)
        return view

    def decoded_entries(self) -> list[dict]:
        return [{"genome_bit": i, "relation": {"kind": "lut_init", "lut_index": k, "init_index": v}, "confidence": 2, "state": "decoded"}
                for i, (k, v) in sorted(self.decoded.items())]

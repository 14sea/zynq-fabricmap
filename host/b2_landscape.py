#!/usr/bin/env python3
"""B2 — the landscape: the universe mask, the public target rule, the train / holdout
split, and the fitness family F1 / F2 / F3 (docs/b2_architecture.md §3).

Host-only; the Python reference of what the B2 image will compute on the PS from the raw
functional readout (six 64-bit truth tables). Everything is integer-only and deterministic
so that a C twin can reproduce it byte for byte (B1's discipline).

The universe mask is derived from the certificate-derived truth mapping (b1_model) — it is
the set of 292 writable (lut, init) positions, the same object the whitelist and both arms
use; it is NOT the map (the map is which address sits where; the mask is only which
positions exist). The target rule uses the mask and a seed and nothing else.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402

CARRIER_CONSTANTS = REPO_ROOT / "vivado/carrier/generated/carrier_constants.json"
LUTS = bc.LUTS
VECTORS = 64
TRAIN_COUNT = 40
HOLDOUT_COUNT = 24
F3_HORIZON = 8
FITNESS_IDS = ("F2", "F1", "F3")          # the frozen selection order (§3, §7)
MASK64 = (1 << 64) - 1


def vector_order(constants: dict | None = None) -> list[int]:
    c = constants or json.loads(CARRIER_CONSTANTS.read_text())
    order = [int(x) for x in c["order"]]
    if sorted(order) != list(range(VECTORS)) or int(c["train_count"]) != TRAIN_COUNT or int(c["holdout_count"]) != HOLDOUT_COUNT:
        raise ValueError("carrier constants: order / train / holdout are not the frozen ones")
    return order


def train_vectors(constants: dict | None = None) -> list[int]:
    return vector_order(constants)[:TRAIN_COUNT]


def holdout_vectors(constants: dict | None = None) -> list[int]:
    return vector_order(constants)[TRAIN_COUNT:]


def universe_mask(truth: dict | None = None) -> list[int]:
    """Six 64-bit masks: bit v of mask k set iff (k, v) is one of the 292 writable positions."""
    truth = truth or bm.truth_mapping()
    masks = [0] * LUTS
    for i in range(bc.N):
        k, v = truth["mapping"][i]
        if masks[k] >> v & 1:
            raise ValueError(f"position ({k},{v}) mapped twice")
        masks[k] |= 1 << v
    if sum(bin(m).count("1") for m in masks) != bc.N:
        raise ValueError("universe mask does not hold 292 positions")
    return masks


def target_tables(landscape_seed: int, masks: list[int]) -> list[int]:
    """The public target rule: the next bit of the instrument's xorshift stream per (k, v)
    in k-major order, masked to the universe (0 = the base value where not writable)."""
    rng = bc.Rng(landscape_seed)
    t = [0] * LUTS
    for k in range(LUTS):
        for v in range(VECTORS):
            bit = rng.next32() & 1
            if bit and (masks[k] >> v & 1):
                t[k] |= 1 << v
    return t


def optimum_genome(target: list[int], truth: dict | None = None) -> int:
    """The unique genome whose readout equals the (masked) target."""
    truth = truth or bm.truth_mapping()
    g = 0
    for i in range(bc.N):
        k, v = truth["mapping"][i]
        if target[k] >> v & 1:
            g |= 1 << i
    return g


def column_word(tables: list[int], v: int) -> int:
    w = 0
    for k in range(LUTS):
        w |= ((tables[k] >> v) & 1) << k
    return w


def popcount6(x: int) -> int:
    return bin(x & 0x3F).count("1")


# ------------------------------------------------------------------ the fitness family

def f1_exact_word(tables: list[int], target: list[int], vectors: list[int]) -> int:
    return sum(1 for v in vectors if column_word(tables, v) == column_word(target, v))


G2 = (4, 1, 0, 0, 0, 0, 0)


def f2_graded_word(tables: list[int], target: list[int], vectors: list[int]) -> int:
    return sum(G2[popcount6(column_word(tables, v) ^ column_word(target, v))] for v in vectors)


def f3_trajectory(tables: list[int], target: list[int], vectors: list[int], horizon: int = F3_HORIZON) -> int:
    """For each start state in `vectors`, the longest prefix (<= horizon steps) on which the
    automaton s <- W(s) agrees with the target automaton s <- T(s)."""
    total = 0
    for s0 in vectors:
        s, ts = s0, s0
        for step in range(horizon):
            s = column_word(tables, s)
            ts = column_word(target, ts)
            if s != ts:
                break
            total += 1
    return total


FITNESS = {"F1": f1_exact_word, "F2": f2_graded_word, "F3": f3_trajectory}
CEILING = {"F1": TRAIN_COUNT, "F2": 4 * TRAIN_COUNT, "F3": F3_HORIZON * TRAIN_COUNT}


def fitness(fid: str, tables: list[int], target: list[int], vectors: list[int]) -> int:
    return FITNESS[fid](tables, target, vectors)


class Landscape:
    """One landscape: a fitness id, a seed, the masked target, the train / holdout vectors."""

    def __init__(self, fid: str, landscape_seed: int, masks: list[int] | None = None, constants: dict | None = None,
                 truth: dict | None = None):
        if fid not in FITNESS:
            raise ValueError(fid)
        self.fid = fid
        self.seed = landscape_seed
        self.truth = truth or bm.truth_mapping()
        self.masks = masks or universe_mask(self.truth)
        self.target = target_tables(landscape_seed, self.masks)
        self.train = train_vectors(constants)
        self.holdout = holdout_vectors(constants)
        self.ceiling = CEILING[fid]

    def train_fitness(self, tables: list[int]) -> int:
        return fitness(self.fid, tables, self.target, self.train)

    def holdout_fitness(self, tables: list[int]) -> int:
        return fitness(self.fid, tables, self.target, self.holdout)

    def optimum(self) -> int:
        return optimum_genome(self.target, self.truth)

    def describe(self) -> dict:
        return {"fitness": self.fid, "landscape_seed": self.seed, "ceiling": self.ceiling,
                "target": [f"{t:016x}" for t in self.target], "masks": [f"{m:016x}" for m in self.masks],
                "train": list(self.train), "holdout": list(self.holdout)}

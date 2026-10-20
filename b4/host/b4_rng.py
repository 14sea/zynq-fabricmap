#!/usr/bin/env python3
"""B4 — the line's PRNG, a DERIVED COPY of `host/b1_carto.Rng` (xorshift64 over a 32-bit seed; `uniform` by rejection;
`sample` a partial Fisher–Yates), kept byte-equivalent in behaviour and recorded in `b4/IMPORT.json` with the base
path and digests. B4 never imports the pinned module; the copy's equivalence is a test (`b4/tests/test_b4_rng.py`)."""
from __future__ import annotations

MASK64 = (1 << 64) - 1
MASK32 = (1 << 32) - 1
GOLDEN = 0x9E3779B97F4A7C15


def xorshift(x: int) -> int:
    x ^= (x << 13) & MASK64
    x ^= x >> 7
    x ^= (x << 17) & MASK64
    return x & MASK64


class Rng:
    def __init__(self, seed32: int):
        x = (((seed32 & MASK32) << 32) | (seed32 & MASK32)) ^ GOLDEN
        self.x = x if x else GOLDEN
        for _ in range(4):
            self.x = xorshift(self.x)

    def next32(self) -> int:
        self.x = xorshift(self.x)
        return (self.x >> 32) & MASK32

    def uniform(self, n: int) -> int:
        limit = ((1 << 32) // n) * n
        while True:
            v = self.next32()
            if v < limit:
                return v % n

    def sample(self, population: list[int], k: int) -> list[int]:
        pool = list(population)
        out = []
        for i in range(k):
            j = i + self.uniform(len(pool) - i)
            pool[i], pool[j] = pool[j], pool[i]
            out.append(pool[i])
        return out

    def state(self) -> int:
        """The generator's state, recorded in a terminal event; never rolled back."""
        return self.x

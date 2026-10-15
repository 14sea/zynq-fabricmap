#!/usr/bin/env python3
"""B3 lifecycle 1 — control X, the scrambled-specimen online arm (docs/b3_architecture.md v0.2.3 §9,
"Control X, precisely").

One global derangement π of the 384 (LUT, vector) positions (index = 64 · LUT + vector), drawn once
per gate run: `seed_x = b2_search.master_seed("b3-gate-x", instrument_commit)` (the first 4 bytes of
sha256("b3-gate-x|" ‖ commit), big-endian — the rule every B-line seed uses); PRNG = the instrument's
`b1_carto.Rng(seed_x)`; Fisher–Yates from i = 383 down to 1 with `j = rng.uniform(i + 1)`,
rejection-sampled until no fixed point: EVERY ATTEMPT STARTS FROM THE IDENTITY ARRAY and the RNG is
not reset (it continues from the preceding attempt). π acts on one thing only — the behaviour delta
entering X's cartographer (`map_delta`). Self-consistency is proved per specimen by a shadow
cartographer fed the unpermuted deltas: `isomorphism_findings` names any way X's state is not π of
the shadow's. `permutation_sha256` = sha256 of the compact canonical JSON array [π(0), …, π(383)].
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "host") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_carto as bc  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_search as bs  # noqa: E402

LABEL = "b3-gate-x"
N_POS = bl.LUTS * bl.VECTORS


def seed_x(instrument_commit: str) -> int:
    return bs.master_seed(LABEL, instrument_commit)


def _attempt(rng: bc.Rng, n: int) -> list[int]:
    p = list(range(n))                                  # every attempt starts from the identity array
    for i in range(n - 1, 0, -1):
        j = rng.uniform(i + 1)
        p[i], p[j] = p[j], p[i]
    return p


def derangement(seed: int, n: int = N_POS, log: list | None = None) -> list[int]:
    """The unique π for `seed`: rejection sampling over Fisher–Yates attempts on ONE continuing RNG
    stream, each attempt from the identity. `log`, if given, receives each attempt's fixed points."""
    rng = bc.Rng(seed)
    while True:
        p = _attempt(rng, n)
        fixed = [i for i in range(n) if p[i] == i]
        if log is not None:
            log.append(fixed)
        if not fixed:
            return p


def permutation_sha256(perm: list[int]) -> str:
    return hashlib.sha256(json.dumps(list(perm), separators=(",", ":")).encode()).hexdigest()


def pos_index(k: int, v: int) -> int:
    return bl.VECTORS * k + v


def index_pos(idx: int) -> tuple[int, int]:
    return idx // bl.VECTORS, idx % bl.VECTORS


def map_delta(delta: list[tuple[int, int]], perm: list[int]) -> list[tuple[int, int]]:
    """π applied position-wise to a behaviour delta — the only thing π ever touches."""
    return [index_pos(perm[pos_index(k, v)]) for k, v in delta]


def isomorphism_findings(x_carto, shadow_carto, perm: list[int]) -> list[str]:
    """X's cartographer state must be π of the shadow's: same version, same anomaly count, the same
    address sets, and every decoded position / candidate set mapped through π."""
    f: list[str] = []
    if x_carto.version != shadow_carto.version:
        f.append(f"version {x_carto.version} != shadow {shadow_carto.version}")
    if x_carto.anomalies != shadow_carto.anomalies:
        f.append(f"anomalies {x_carto.anomalies} != shadow {shadow_carto.anomalies}")
    if sorted(x_carto.decoded) != sorted(shadow_carto.decoded):
        f.append("decoded address sets differ")
    else:
        for i, pos in shadow_carto.decoded.items():
            want = index_pos(perm[pos_index(*pos)])
            if x_carto.decoded[i] != want:
                f.append(f"address {i}: X decoded {x_carto.decoded[i]}, π(shadow) = {want}")
    if sorted(x_carto.candidates) != sorted(shadow_carto.candidates):
        f.append("candidate address sets differ")
    else:
        for i, cset in shadow_carto.candidates.items():
            want = {index_pos(perm[pos_index(*p)]) for p in cset}
            if set(x_carto.candidates[i]) != want:
                f.append(f"address {i}: X candidates != π(shadow candidates)")
    if set(x_carto.taken) != {index_pos(perm[pos_index(*p)]) for p in shadow_carto.taken}:
        f.append("taken positions != π(shadow taken)")
    return f

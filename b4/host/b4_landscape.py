#!/usr/bin/env python3
"""B4-FF — the PUBLIC TASK generator and the scoring (the revised 2b-2 scope, section 4.1; the owner's ruling 3 of
2026-10-18): the stimulus, the scoring mask M, the target t and the weights w come from a versioned generator and
the landscape seed ALONE — nothing here reads the certificate mapping, the hypothesis, a decode or a search arm —
and every arm of a pair receives the same task. The base is the all-zero configuration, a declared design choice
(all-one would be permutation-invariant and in the domain too; all-zero is the one chosen).

    task = make_task(seed)                       # version task-v0.1
    fit, nones = score(trace, task)              # f = sum(w[j] * [q[j] in {0,1} and q[j] == t[j]] for j in M)
    fit, nones = score_holdout(trace, task)

A None cell scores nothing and is counted; the ceiling is sum(w) and never moves with a candidate's applicability;
None == None is not a hit. Reachability of the ceiling, the base not being optimal, and interaction are NOT
guaranteed by this generator: they are claims for a separate host audit, never satisfied by choosing seeds.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_execution as ex  # noqa: E402
from b4_rng import Rng  # noqa: E402

TASK_VERSION = "task-v0.1"
ELEMENTS = 8
K_DEFAULT = 6              # clock steps of the search stimulus
K_HOLDOUT = 8              # clock steps of the holdout stimulus (its own derivation)
LEVEL_STEPS = 2            # input-only steps after the clock steps (transparency / asynchronous effects)
HOLDOUT_SALT = 0xA5A5A5A5


def _vec(rng: Rng) -> int:
    return rng.uniform(256)


def _sparse(rng: Rng) -> int:
    """SR asserted on each element with probability 1/4 — a user SR operation inside the sequence."""
    v = 0
    for i in range(ELEMENTS):
        if rng.uniform(4) == 0:
            v |= 1 << i
    return v


def _stimulus(rng: Rng, k: int) -> list[dict]:
    steps = [{"kind": "init"}]
    clock = 0
    for _ in range(k):
        clock ^= 1
        steps.append({"kind": "set", "clock": clock, "ce": _vec(rng), "sr": _sparse(rng), "d": _vec(rng)})
    for _ in range(LEVEL_STEPS):
        steps.append({"kind": "set", "clock": clock, "ce": _vec(rng), "sr": _sparse(rng), "d": _vec(rng)})
    return steps


def _mask_target(rng: Rng, n_steps: int):
    mask, target, weights = [], [], []
    for s in range(1, n_steps):                 # every readout after the init step
        for e in range(ELEMENTS):
            mask.append((s, e)); target.append(rng.uniform(2)); weights.append(1)
    return tuple(mask), tuple(target), tuple(weights)


def make_task(seed: int, addresses: tuple, k: int = K_DEFAULT, label: str = "b4-task") -> ex.PublicTask:
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= 0xFFFFFFFF:
        raise ValueError("a landscape seed is a 32-bit integer")
    rng = Rng(seed)
    stimulus = _stimulus(rng, k)
    mask, target, weights = _mask_target(rng, len(stimulus))
    hrng = Rng(seed ^ HOLDOUT_SALT)
    h_stimulus = _stimulus(hrng, K_HOLDOUT)
    h_mask, h_target, h_weights = _mask_target(hrng, len(h_stimulus))
    return ex.PublicTask(label=label, version=TASK_VERSION, seed=seed, addresses=tuple(addresses), base_genome=0,
                         stimulus=tuple(stimulus), mask=mask, target=target, weights=weights,
                         holdout_stimulus=tuple(h_stimulus), holdout_mask=h_mask, holdout_target=h_target, holdout_weights=h_weights)


def _score(trace: dict, mask, target, weights) -> tuple[int, int]:
    fit, nones = 0, 0
    steps = trace["steps"]
    for (s, e), t, w in zip(mask, target, weights):
        q = steps[s]["q_after"][e]
        if q is None:
            nones += 1
        elif q == t:
            fit += w
    return fit, nones


def score(trace: dict, task: ex.PublicTask) -> tuple[int, int]:
    """(fitness, None cells) of a search-stimulus trace; recomputable by the host from the ledger's q grid."""
    if len(trace["steps"]) != len(task.stimulus):
        raise ValueError("the trace is not of the task's stimulus")
    return _score(trace, task.mask, task.target, task.weights)


def score_holdout(trace: dict, task: ex.PublicTask) -> tuple[int, int]:
    if len(trace["steps"]) != len(task.holdout_stimulus):
        raise ValueError("the trace is not of the task's holdout stimulus")
    return _score(trace, task.holdout_mask, task.holdout_target, task.holdout_weights)


def score_grid(q_grid: list, task: ex.PublicTask) -> tuple[int, int]:
    """The same scoring over a ledger's stored q grid (q_after per step), for replay."""
    return _score({"steps": [{"q_after": row} for row in q_grid]}, task.mask, task.target, task.weights)

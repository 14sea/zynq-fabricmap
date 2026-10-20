#!/usr/bin/env python3
"""B4-FF — the PUBLIC TASK generator and the scoring, task-v0.2 (docs/b4_architecture.md section 7.1, DRAFT v0.2.0; the owner's
rulings of 2026-10-20 on the protocol-revision scope v0.2, choices 1-3): the stimulus, the scoring mask M and the weights w come
from a versioned generator and the landscape seed ALONE; the TARGET is no longer drawn — it is the observed trace of a PLANTED
flip-flop configuration g* under the task's own stimuli, obtained by the harness through the execution port (b4_target) and
handed to this module as q grids. Nothing here reads the certificate mapping, the hypothesis, a decode or a search arm; the
storage_kind bit the planted rule fixes is an integer the harness reads from the mapping and passes in. Every arm of a pair
receives the same PublicTask. The base is the all-zero configuration (declared).

    parts = public_parts(seed)                                   # stimulus, mask, weights, holdout_stimulus, holdout_mask, holdout_weights
    g = planted_genome(seed, storage_kind_bit)                   # T-i: storage_kind = flip-flop, the other 20 bits drawn ONCE (the base included)
    target = targets_from_grid(grid, parts["mask"])              # the target per mask cell from g*'s observed trace; a None cell is a TargetRefusal
    task = make_task(addresses, parts, target, holdout_target, target_source_sha256)   # the executing side's input: NO seed, NO g*
    fit, nones = score(trace, task)                              # f = sum(w[j] * [q[j] in {0,1} and q[j] == t[j]] for j in M)
    fit, nones = score_holdout(trace, task)

THE PLANTED RULE (choice 3, T-i). `Rng((seed ^ SALT_TARGET) & 0xffffffff).uniform(1 << 20)` — the first call of a generator of its
own, independent of the task's, the operator's, the controls' and K10's — is mapped onto the 20 non-storage_kind bits in address
order; the storage_kind bit is 0 (flip-flop). The all-zero base is NOT excluded and NOTHING is redrawn: not for a genotype equal
to the base, not for a trace equal to the base's, not for a low score, not for a None. The search universe stays the 21 bits;
the ceilings (64 search cells, 80 holdout cells) and "a None cell scores nothing" are unchanged. A formal target trace with a
None or a malformed cell is a TargetRefusal — `invalid` under section 9.1, never a mask narrowed or a target redrawn.

THE PUBLIC TASK carries no landscape seed, no g* and no private record (choice 2, H): what the executing side receives is the
addresses, the base, the two stimuli, masks, targets and weights, and `target_source_sha256` — the commitment to the two setup
observations (b4_target.target_source_sha256). Its digest covers exactly those fields. This is a fixed-program ACCESS CONTRACT,
not information hiding (section 7.1): the stimulus is derived from a 32-bit seed, the host process holds everything, and the
replay proves the declared program sequence, not that nothing could have leaked.

Reachability of the search ceiling by g* follows from the construction (the target IS g*'s trace); that a champion reaches it,
that the base is not already the target, and interaction are NOT guaranteed and are recorded, never arranged by choosing seeds.
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

TASK_VERSION = "task-v0.2"
ELEMENTS = 8
N_BITS = 21                # the configuration-bit universe of the certified site
K_DEFAULT = 6              # clock steps of the search stimulus
K_HOLDOUT = 8              # clock steps of the holdout stimulus (its own derivation)
LEVEL_STEPS = 2            # input-only steps after the clock steps (transparency / asynchronous effects)
HOLDOUT_SALT = 0xA5A5A5A5
SALT_TARGET = 0x54415247   # the planted generator's salt ("TARG"); an arbitrary constant fixed before any draw (section 7.1), named in the protocol identity
PLANTED_RULE = ("Rng((landscape_seed ^ 0x54415247) & 0xffffffff).uniform(1 << 20), the first call, mapped onto the 20 non-storage_kind bits in address "
                "order; the storage_kind bit fixed to 0 (flip-flop); the all-zero base included; nothing redrawn")


class TargetRefusal(ValueError):
    """A formal target trace that cannot be a target: a None or a malformed cell inside the mask (section 7.1, T-i: invalid, never narrowed)."""


def _vec(rng: Rng) -> int:
    return rng.uniform(256)


def _sparse(rng: Rng) -> int:
    """SR asserted on each element with probability 1/4 — a user SR operation inside the sequence (the rule of task-v0.1, unchanged)."""
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


def _mask_weights(n_steps: int) -> tuple[tuple, tuple]:
    """Every readout cell after the init step, weight 1: the ceiling is the cell count (64 for the search stimulus, 80 for the holdout)."""
    mask, weights = [], []
    for s in range(1, n_steps):
        for e in range(ELEMENTS):
            mask.append((s, e)); weights.append(1)
    return tuple(mask), tuple(weights)


def _check_seed(seed) -> None:
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= 0xFFFFFFFF:
        raise ValueError("a landscape seed is a 32-bit integer")


def public_parts(seed: int, k: int = K_DEFAULT) -> dict:
    """The seed-derived PUBLIC parts of a task: the search stimulus with its mask and weights, the holdout stimulus with its own
    (K_HOLDOUT, HOLDOUT_SALT). The targets are not here: they come from the planted configuration's observed traces."""
    _check_seed(seed)
    rng = Rng(seed)
    stimulus = _stimulus(rng, k)
    mask, weights = _mask_weights(len(stimulus))
    hrng = Rng(seed ^ HOLDOUT_SALT)
    h_stimulus = _stimulus(hrng, K_HOLDOUT)
    h_mask, h_weights = _mask_weights(len(h_stimulus))
    return {"stimulus": tuple(stimulus), "mask": mask, "weights": weights, "holdout_stimulus": tuple(h_stimulus), "holdout_mask": h_mask, "holdout_weights": h_weights}


def planted_genome(seed: int, storage_kind_bit: int, n_bits: int = N_BITS) -> int:
    """T-i: the storage_kind bit 0 (flip-flop); the other n_bits - 1 bits from the first `uniform(1 << (n_bits - 1))` of the
    planted generator, mapped onto the non-storage_kind bits in address (bit) order. One draw; the all-zero base included."""
    _check_seed(seed)
    if not isinstance(storage_kind_bit, int) or isinstance(storage_kind_bit, bool) or not 0 <= storage_kind_bit < n_bits:
        raise ValueError("the storage_kind bit is an index into the universe")
    draw = Rng((seed ^ SALT_TARGET) & 0xFFFFFFFF).uniform(1 << (n_bits - 1))
    free = [b for b in range(n_bits) if b != storage_kind_bit]
    g = 0
    for i, b in enumerate(free):
        if (draw >> i) & 1:
            g |= 1 << b
    return g


def targets_from_grid(grid, mask) -> tuple:
    """The target per mask cell read from a q grid (rows per step, ELEMENTS cells each). A cell that is not 0 or 1 (None: an element
    that reads nothing in that configuration; anything else: malformed) is a TargetRefusal — a formal target is never narrowed."""
    if not (isinstance(grid, list) and all(isinstance(r, list) and len(r) == ELEMENTS for r in grid)):
        raise TargetRefusal("the target trace is not a q grid of ELEMENTS cells per step")
    out = []
    for (s, e) in mask:
        if s >= len(grid):
            raise TargetRefusal(f"the target trace has {len(grid)} steps; the mask reads step {s}")
        q = grid[s][e]
        if q is None:
            raise TargetRefusal(f"the planted configuration reads None at step {s}, element {e}: not a target under T-i (invalid, not narrowed)")
        if isinstance(q, bool) or q not in (0, 1):
            raise TargetRefusal(f"the target trace carries {q!r} at step {s}, element {e}: not 0 / 1")
        out.append(q)
    return tuple(out)


def make_task(addresses: tuple, parts: dict, target: tuple, holdout_target: tuple, target_source_sha256: str, label: str = "b4-task") -> ex.PublicTask:
    """The executing side's input (H): no seed, no planted genome, no private record. The targets are the planted configuration's
    observed traces as `targets_from_grid` read them; `target_source_sha256` commits to the two setup observations."""
    if len(target) != len(parts["mask"]) or len(holdout_target) != len(parts["holdout_mask"]):
        raise ValueError("a target has one value per mask cell")
    if not all((t in (0, 1)) and not isinstance(t, bool) for t in tuple(target) + tuple(holdout_target)):
        raise ValueError("a target is 0 / 1 per cell")
    if not ex._hex64(target_source_sha256):
        raise ValueError("target_source_sha256 is a 64-hex digest")
    return ex.PublicTask(label=label, version=TASK_VERSION, addresses=tuple(addresses), base_genome=0,
                         stimulus=tuple(parts["stimulus"]), mask=tuple(parts["mask"]), target=tuple(target), weights=tuple(parts["weights"]),
                         holdout_stimulus=tuple(parts["holdout_stimulus"]), holdout_mask=tuple(parts["holdout_mask"]), holdout_target=tuple(holdout_target),
                         holdout_weights=tuple(parts["holdout_weights"]), target_source_sha256=target_source_sha256)


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


def score_holdout_grid(q_grid: list, task: ex.PublicTask) -> tuple[int, int]:
    return _score({"steps": [{"q_after": row} for row in q_grid]}, task.holdout_mask, task.holdout_target, task.holdout_weights)

#!/usr/bin/env python3
"""B4-FF — the PUBLIC TASK generator and the scoring, task-v0.3 (docs/b4_architecture.md section 7.2, DRAFT v0.3.0; the owner's
ruling of 2026-10-27 on the shared CE / SR / CLK finding of the carrier v2 unit, docs/b4_carrier_v2.md section 0): the stimulus, the
scoring mask M and the weights w come from a versioned generator and the landscape seed ALONE; the TARGET is the observed trace of a
PLANTED flip-flop configuration g* under the task's own stimuli (task-v0.2's T-i and H, unchanged), obtained by the harness through
the execution port (b4_target) and handed to this module as q grids. Nothing here reads the certificate mapping, the hypothesis, a
decode or a search arm; the storage_kind bit the planted rule fixes is an integer the harness reads from the mapping and passes in.
Every arm of a pair receives the same PublicTask. The base is the all-zero configuration (declared).

    parts = public_parts(seed)                                   # stimulus, mask, weights, holdout_stimulus, holdout_mask, holdout_weights
    g = planted_genome(seed, storage_kind_bit)                   # T-i: storage_kind = flip-flop, the other 20 bits drawn ONCE (the base included)
    target = targets_from_grid(grid, parts["mask"])              # the target per mask cell from g*'s observed trace; a None cell is a TargetRefusal
    task = make_task(addresses, parts, target, holdout_target, target_source_sha256)   # the executing side's input: NO seed, NO g*
    fit, nones = score(trace, task)                              # f = sum(w[j] * [q[j] in {0,1} and q[j] == t[j]] for j in M)
    fit, nones = score_holdout(trace, task)
    stimulus_findings(task.stimulus)                             # the task-v0.3 shape: every set step's ce / sr a slice-wide broadcast

THE STIMULUS RULE OF task-v0.3 (the owner's ruling of 2026-10-27; fixed before any draw). A 7-series slice has ONE clock-enable pin,
ONE set / reset pin and ONE clock pin shared by its eight storage elements (AMD UG474; the carrier v2 finding): a per-element `ce` /
`sr` vector is realisable only when uniform. Per `set` step the generator therefore draws ONE control value each — CE high with
probability 1/2 (`rng.uniform(2) == 0`), SR high with probability 1/4 (`rng.uniform(4) == 0`), the two draws independent — and
BROADCASTS each over the eight elements in the common 8-bit grammar: `0xFF` when high, `0x00` when low (`broadcast`). `d` stays a
per-element uniform 8-bit draw (every element has its own D pin through its LUT). The draw order per step is ce, sr, d. K = 6 / 8,
the two level steps, the mask, the weights, the ceilings 64 / 80, the holdout salt, the planted rule (T-i) and the PublicTask boundary
(H) are task-v0.2's, unchanged. The 8-bit vectors are the COMMON GRAMMAR of the model (b4_ff_model.validate_step), the observation
contract (docs/b4_observation_contract.md 2.1) and the carrier's STEP_IN word (host/b4carrier_regmap.step_word, `realisable`):
task-v0.3 only ever PRODUCES the two broadcast values, so the model's per-element evaluation (`_ce_ok` / `_sr_active` on bit i)
gives every element the same control value — the slice-wide semantics — with no change to the model's state machine; the carrier's
`F_NOT_REALISABLE` refusal path is kept as an invariant it never hits under this task. The shape is HELD, not assumed: `stimulus_findings`
names any set step whose `ce` / `sr` is not a broadcast, and the record validators and the offline reconstruction call it on every task.

THE PLANTED RULE (choice 3, T-i; unchanged). `Rng((seed ^ SALT_TARGET) & 0xffffffff).uniform(1 << 20)` — the first call of a generator
of its own, independent of the task's, the operator's, the controls' and K10's — is mapped onto the 20 non-storage_kind bits in address
order; the storage_kind bit is 0 (flip-flop). The all-zero base is NOT excluded and NOTHING is redrawn: not for a genotype equal to
the base, not for a trace equal to the base's, not for a low score, not for a None. The search universe stays the 21 bits; the
ceilings (64 search cells, 80 holdout cells) and "a None cell scores nothing" are unchanged. A formal target trace with a None or a
malformed cell is a TargetRefusal — `invalid` under section 9.1, never a mask narrowed or a target redrawn.

CEILING AND REACHABILITY, KEPT APART (the owner's ruling of 2026-10-27). The ceiling is the COUNT of scoring cells — 64 / 80 — verified
from the mask the generator writes; the planted configuration scores the ceiling on ITS OWN trace by construction (the target IS that
trace, held per pair by b4_target.setup_findings); that a SEARCH reaches it, that the base is not already the target, and interaction
are NOT guaranteed and are recorded (K1, the non-triviality record), never arranged by choosing seeds.

THE PUBLIC TASK carries no landscape seed, no g* and no private record (choice 2, H): what the executing side receives is the
addresses, the base, the two stimuli, masks, targets and weights, and `target_source_sha256` — the commitment to the two setup
observations (b4_target.target_source_sha256). Its digest covers exactly those fields. This is a fixed-program ACCESS CONTRACT,
not information hiding (section 7.1): the stimulus is derived from a 32-bit seed, the host process holds everything, and the
replay proves the declared program sequence, not that nothing could have leaked.
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

TASK_VERSION = "task-v0.3"
PREVIOUS_TASK_VERSION = "task-v0.2"   # the history: per-element ce (uniform 8-bit) and sr (each element with probability 1/4); consumed by b4-sim-4
ELEMENTS = 8
N_BITS = 21                # the configuration-bit universe of the certified site
K_DEFAULT = 6              # clock steps of the search stimulus
K_HOLDOUT = 8              # clock steps of the holdout stimulus (its own derivation)
LEVEL_STEPS = 2            # input-only steps after the clock steps (transparency / asynchronous effects)
HOLDOUT_SALT = 0xA5A5A5A5
SALT_TARGET = 0x54415247   # the planted generator's salt ("TARG"); an arbitrary constant fixed before any draw (section 7.1), named in the protocol identity
CE_HIGH_ONE_IN = 2         # task-v0.3: CE high with probability 1/2 per set step (rng.uniform(2) == 0), slice-wide
SR_HIGH_ONE_IN = 4         # task-v0.3: SR high with probability 1/4 per set step (rng.uniform(4) == 0), slice-wide; the two draws independent
BROADCAST = {0: 0x00, 1: 0xFF}   # one control value broadcast over the eight elements in the common 8-bit grammar
STIMULUS_RULE = ("task-v0.3 (the owner's ruling of 2026-10-27): per set step ONE slice-wide CE value, high with probability 1/2 (uniform(2) == 0), "
                 "and ONE slice-wide SR value, high with probability 1/4 (uniform(4) == 0), the two draws independent, each broadcast over the eight "
                 "elements as 0xFF / 0x00; d a per-element uniform 8-bit draw; the draw order ce, sr, d; K = 6 / 8, two level steps, the mask, "
                 "the weights and the ceilings 64 / 80 as task-v0.2")
MODEL_INPUT_CONTRACT = ("the 8-bit ce / sr vectors are the common grammar of the model, the observation contract and the carrier; task-v0.3 produces only "
                        "the two broadcast values, under which the model's per-element evaluation gives every element the same control value (the "
                        "slice-wide semantics) — no change to the model's state machine; the carrier's realisability refusal is an invariant never hit")
PLANTED_RULE = ("Rng((landscape_seed ^ 0x54415247) & 0xffffffff).uniform(1 << 20), the first call, mapped onto the 20 non-storage_kind bits in address "
                "order; the storage_kind bit fixed to 0 (flip-flop); the all-zero base included; nothing redrawn")


class TargetRefusal(ValueError):
    """A formal target trace that cannot be a target: a None or a malformed cell inside the mask (section 7.1, T-i: invalid, never narrowed)."""


def _vec(rng: Rng) -> int:
    """A per-element uniform 8-bit draw (d: every element has its own D pin)."""
    return rng.uniform(256)


def broadcast(bit: int) -> int:
    """One slice-wide control value in the common 8-bit grammar: 1 -> 0xFF, 0 -> 0x00."""
    if bit not in (0, 1) or isinstance(bit, bool):
        raise ValueError("a control value is 0 or 1")
    return BROADCAST[bit]


def is_broadcast(vec) -> bool:
    return type(vec) is int and vec in (0x00, 0xFF)


def slice_wide_controls(step: dict) -> tuple[int, int]:
    """The (ce, sr) control bits of a task-v0.3 set step; ValueError when either vector is not a broadcast (the step is not of this task)."""
    if not (isinstance(step, dict) and step.get("kind") == "set" and is_broadcast(step.get("ce")) and is_broadcast(step.get("sr"))):
        raise ValueError("not a task-v0.3 set step: ce / sr must be the broadcast values 0x00 / 0xFF")
    return (1 if step["ce"] == 0xFF else 0), (1 if step["sr"] == 0xFF else 0)


def _ce(rng: Rng) -> int:
    """CE high with probability 1 / CE_HIGH_ONE_IN, slice-wide, broadcast."""
    return broadcast(1 if rng.uniform(CE_HIGH_ONE_IN) == 0 else 0)


def _sr(rng: Rng) -> int:
    """SR high with probability 1 / SR_HIGH_ONE_IN, slice-wide, broadcast — a user SR operation inside the sequence."""
    return broadcast(1 if rng.uniform(SR_HIGH_ONE_IN) == 0 else 0)


def _set_step(rng: Rng, clock: int) -> dict:
    ce = _ce(rng)                                  # the draw order is fixed: ce, sr, d
    sr = _sr(rng)
    d = _vec(rng)
    return {"kind": "set", "clock": clock, "ce": ce, "sr": sr, "d": d}


def _stimulus(rng: Rng, k: int) -> list[dict]:
    steps = [{"kind": "init"}]
    clock = 0
    for _ in range(k):
        clock ^= 1
        steps.append(_set_step(rng, clock))
    for _ in range(LEVEL_STEPS):
        steps.append(_set_step(rng, clock))
    return steps


def stimulus_findings(stimulus) -> list[str]:
    """The task-v0.3 SHAPE of a stimulus, held rather than assumed: an init step at index 0 and nowhere else; every other step a set
    step whose ce and sr are the broadcast values 0x00 / 0xFF (ints), clock 0 / 1, d an int in 0..255. Total: a finding, never an exception."""
    f: list[str] = []
    if not isinstance(stimulus, (list, tuple)) or not stimulus:
        return ["the stimulus is not a non-empty list of steps"]
    for n, st in enumerate(stimulus):
        if not isinstance(st, dict):
            f.append(f"step {n}: not an object"); continue
        kind = st.get("kind")
        if n == 0:
            if st != {"kind": "init"}:
                f.append("step 0: not the init step")
            continue
        if kind != "set":
            f.append(f"step {n}: {kind!r} is not a set step (the init step is at index 0 only)"); continue
        if set(st) != {"kind", "clock", "ce", "sr", "d"}:
            f.append(f"step {n}: keys {sorted(st)}"); continue
        if type(st["clock"]) is not int or st["clock"] not in (0, 1):
            f.append(f"step {n}: clock {st['clock']!r}")
        for name in ("ce", "sr"):
            if not is_broadcast(st[name]):
                f.append(f"step {n}: {name} = {st[name]!r} is not a slice-wide broadcast (0x00 / 0xFF): not a task-{TASK_VERSION[5:]} stimulus")
        if type(st["d"]) is not int or not 0 <= st["d"] <= 0xFF:
            f.append(f"step {n}: d {st['d']!r}")
    return f[:20]


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

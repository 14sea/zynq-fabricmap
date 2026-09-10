#!/usr/bin/env python3
"""B2 — the session order, as the image's orchestrator drives it (host-only reference for
`firmware/b2/b2_orch.c`; `tests/test_b2_session.py` compares the two candidate for candidate).

The order is the preregistration's (§2, §6):

    opening baseline                     the blank genome; its MEASURED readout is the base
                                         every arm of this session starts from
    for each pair r of this session's slice:
        arm order = (A, B) when r is even, (B, A) when r is odd
        for arm in order:  `budget` evaluations                 the search
        for arm in order:  one champion evaluation              the holdout known answer
    closing baseline

A candidate that is not SCORED ends the epoch: nothing further is proposed and no closing
baseline follows. The champion's holdout evaluation is a real candidate — the champion
genome is written and read back again, and F1 is taken over the holdout columns of that
fresh readout (no `mode_holdout` flag: the arm gate sweeps all 64 vectors either way).

The pair seeds are NOT an input: they are derived here, as on the board, from the master
seed with the archived-set exclusion (`b2_plan.frozen_seed_exclusion`).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_search as bs  # noqa: E402

MAX_PAIRS = 16


@dataclass
class Candidate:
    seq: int
    is_baseline: bool
    pair: int                      # the absolute pair index, or -1 on a baseline
    arm: str | None                # "random_safe" | "map_guided", or None on a baseline
    holdout: bool
    genome: int
    block: str = ""                # the `search` block after the observation, "" on a baseline


@dataclass
class Session:
    master_seed: int
    budget: int
    pairs_total: int
    pair_first: int
    pair_count: int
    candidates: list[Candidate] = field(default_factory=list)
    ended_early: bool = False


def arm_order(pair: int) -> tuple[str, str]:
    return (bs.ARM_RANDOM_SAFE, bs.ARM_MAP_GUIDED) if pair % 2 == 0 else (bs.ARM_MAP_GUIDED, bs.ARM_RANDOM_SAFE)


def arm_letter(arm: str) -> str:
    return "A" if arm == bs.ARM_RANDOM_SAFE else "B"


def arm_wire_name(arm: str) -> str:
    return "random_safe" if arm == bs.ARM_RANDOM_SAFE else "map_guided"


def pair_seeds(master_seed: int, pairs_total: int) -> list[tuple[int, int]]:
    exclusion, _ = bp.frozen_seed_exclusion()
    return bs.pair_seeds(master_seed, pairs_total, exclude=exclusion)


def records(pairs: int, budget: int, sessions: int = 1) -> int:
    """The record arithmetic of preregistration §2: per pair 2*budget + 2, per session two
    baselines."""
    return 2 * sessions + pairs * (2 * budget + 2)


def run(master_seed: int, budget: int, pairs_total: int, pair_first: int, pair_count: int,
        fabric: bs.ModelFabric, view: bmaps.MapView, unscored_at: int | None = None,
        truth: dict | None = None, masks: list[int] | None = None) -> Session:
    """Drive the session over the fabric model; `unscored_at` makes that record's candidate
    not SCORED, which must end the epoch."""
    if not (0 < pairs_total <= MAX_PAIRS) or pair_first < 0 or pair_count <= 0 or pair_first + pair_count > pairs_total:
        raise ValueError("the session's pair slice is not inside the experiment")
    if budget <= 0:
        raise ValueError("budget")
    seeds = pair_seeds(master_seed, pairs_total)
    out = Session(master_seed, budget, pairs_total, pair_first, pair_count)
    seq = 0

    def emit(is_baseline, pair, arm, holdout, genome) -> Candidate | None:
        nonlocal seq
        seq += 1
        c = Candidate(seq, is_baseline, pair, arm_wire_name(arm) if arm else None, holdout, genome)
        out.candidates.append(c)
        if unscored_at is not None and seq == unscored_at:
            out.ended_early = True
            return None
        return c

    c = emit(True, -1, None, False, 0)
    if c is None:
        return out
    base = fabric(0)

    for i in range(pair_count):
        r = pair_first + i
        lseed, oseed = seeds[r]
        land = bl.Landscape("F1", lseed, masks=masks, truth=truth)
        order = arm_order(r)
        runs: dict[str, bs.RunResult] = {}
        for arm in order:                                   # the searches, in this pair's order
            res = bs.run(arm, land, None if arm == bs.ARM_RANDOM_SAFE else view, oseed, budget,
                         fabric, log_moves=True, pair=r)
            runs[arm] = res
            for n, blk in enumerate(res.blocks, start=1):
                c = emit(False, r, arm, False, res.moves[n - 1]["genome"])
                if c is None:
                    return out
                c.block = blk
        for arm in order:                                   # then both champions' holdout evaluations
            res = runs[arm]
            c = emit(False, r, arm, True, res.champion.genome)
            if c is None:
                return out
            c.block = res.champion_block
    c = emit(True, -1, None, False, 0)
    return out

#!/usr/bin/env python3
"""B3 lifecycle 2 — the session order, as the image's orchestrator will drive it (host-only Python
reference for the B3 orchestrator; B2's `host/b2_session.py` is the template; docs/b3_architecture.md
v0.3 §7, preregistration v0.3.1 §2 "records" / "arm order", §6).

The order, for B3 and B3Q alike:

    opening baseline                     the blank genome; its MEASURED readout is the base
    for each absolute pair r of this session's slice:
        arm order = the (r mod 6)-th of RFO, FOR, ORF, ROF, OFR, FRO     (b3_plan.ARM_SEQUENCE)
        for arm in order:  `budget` evaluations                          the three searches
        for arm in order:  one champion evaluation                       the three holdout known answers
    closing baseline

    records = 2 + pair_count × (3 × budget + 3)                          (b3_plan.session_records)

A candidate that is not SCORED ends the epoch: nothing further is proposed and no closing baseline
follows. A later slice keeps the ABSOLUTE pair index, that pair's seeds and that pair's arm order.

Every arm runs the reference model independently from the seeds — R random-safe (`b2_search.run`,
no map), F the frozen B1 self-map (`b2_search.run` over the committed map's view), O the online arm
(`b3_online_arm.run_online`, a fresh empty cartographer per pair, its ledger kept) — and nothing is
copied from a prediction: no fitness, no ledger, no genome, no commitment. The `search` block of
every candidate is the one the arm's own run produced (`RunResult.blocks` / `champion_block`,
`OnlineResult.blocks` / `champion_block`), byte for byte what the image is to write.

The pair seeds are GIVEN, never derived here: the plan tool draws them under the session's label
with its exclusion sets (`b3_plan`), and a validated `b3_records.Context` carries them
(`run_context`). This module chooses no seed.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "host", REPO_ROOT / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_online_arm as oa  # noqa: E402
import b3_plan as pl  # noqa: E402

MAX_PAIRS = 16
SEED_MAX = 0xFFFFFFFF
PREREGISTERED_FITNESS = "F1"        # preregistration v0.3.1 §2: F1, fixed by B2 and not re-selected — no other fitness runs here
ARM_WIRE = {"R": bs.ARM_RANDOM_SAFE, "F": bs.ARM_MAP_GUIDED, "O": oa.ARM_ONLINE}


@dataclass
class Candidate:
    seq: int
    is_baseline: bool
    pair: int                      # the absolute pair index, or -1 on a baseline
    arm: str | None                # "random_safe" | "map_guided" | "online", or None on a baseline
    holdout: bool
    genome: int
    block: str = ""                # the `search` block after the observation (compact JSON), "" on a baseline


@dataclass
class Session:
    budget: int
    pairs_total: int
    pair_first: int
    pair_count: int
    pair_seeds: list[tuple[int, int]]
    candidates: list[Candidate] = field(default_factory=list)
    ended_early: bool = False

    @property
    def records(self) -> int:
        return records(self.pair_count, self.budget)


def arm_order(pair: int) -> tuple[str, ...]:
    """The pair's arm letters in the frozen prefix-balanced order (b3_plan.ARM_SEQUENCE[r mod 6])."""
    return pl.arm_order(pair)


def records(pairs: int, budget: int, sessions: int = 1) -> int:
    """The record arithmetic of preregistration §2: per pair 3 × budget + 3, per session two baselines."""
    return 2 * sessions + pairs * (3 * budget + 3)


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def check_inputs(budget, pairs_total, pair_first, pair_count, pair_seeds, unscored_at=None) -> list[tuple[int, int]]:
    """Every input as a VALUE — type first, then domain — before any candidate is proposed; a wrong
    one is a named ValueError. Returns the seeds as a list of (landscape, operator) int pairs."""
    if not _int(budget) or budget <= 0:
        raise ValueError(f"budget {budget!r} is not a positive integer")
    if not _int(pairs_total) or not (0 < pairs_total <= MAX_PAIRS):
        raise ValueError(f"pairs_total {pairs_total!r} is not an integer in 1..{MAX_PAIRS}")
    if not _int(pair_first) or not _int(pair_count) or pair_first < 0 or pair_count <= 0 or pair_first + pair_count > pairs_total:
        raise ValueError(f"the session's pair slice ({pair_first!r}, {pair_count!r}) is not inside the experiment's {pairs_total} pairs")
    if not isinstance(pair_seeds, (list, tuple)):
        raise ValueError("pair_seeds is not a list")
    if len(pair_seeds) != pairs_total:
        raise ValueError(f"{len(pair_seeds)} pair seeds for {pairs_total} pairs")
    seeds = []
    for r, s in enumerate(pair_seeds):
        if not isinstance(s, (list, tuple)) or len(s) != 2 or not all(_int(x) and 0 <= x <= SEED_MAX for x in s):
            raise ValueError(f"pair {r}'s seeds {s!r} are not two integers in 0..2^32-1")
        seeds.append((int(s[0]), int(s[1])))
    if unscored_at is not None and (not _int(unscored_at) or unscored_at < 1):
        raise ValueError(f"unscored_at {unscored_at!r} is not a positive integer seq")
    return seeds


def run(budget: int, pairs_total: int, pair_first: int, pair_count: int, pair_seeds: list,
        fabric: bs.ModelFabric | None = None, view: bmaps.MapView | None = None,
        truth: dict | None = None, masks: list[int] | None = None, fitness: str = "F1",
        unscored_at: int | None = None) -> Session:
    """Drive the session over the fabric model; `unscored_at` makes that candidate (by seq) not
    SCORED, which must end the epoch. `view` is arm F's map view (the committed B1 self-map by
    default); arm O starts empty every pair and takes no view. `fitness` must be the preregistered
    F1 — a self-consistent plan / prediction / context under another fitness is refused by name
    before any arm runs: the preregistration fixed F1 and gives no licence to re-select it."""
    seeds = check_inputs(budget, pairs_total, pair_first, pair_count, pair_seeds, unscored_at)
    if fitness != PREREGISTERED_FITNESS:               # before any model or arm runs (the owner's P2 on 10733ac)
        raise ValueError(f"fitness {fitness!r} is not the preregistered {PREREGISTERED_FITNESS!r}")
    truth = truth if truth is not None else bm.truth_mapping()
    masks = masks if masks is not None else bl.universe_mask(truth)
    fabric = fabric if fabric is not None else bs.ModelFabric(truth)
    view = view if view is not None else bmaps.MapView(bmaps.load_self_map(), bl.train_vectors())
    out = Session(budget, pairs_total, pair_first, pair_count, seeds)
    seq = 0

    def emit(is_baseline, pair, arm_letter, holdout, genome) -> Candidate | None:
        nonlocal seq
        seq += 1
        c = Candidate(seq, is_baseline, pair, ARM_WIRE[arm_letter] if arm_letter else None, holdout, genome)
        out.candidates.append(c)
        if unscored_at is not None and seq == unscored_at:
            out.ended_early = True
            return None
        return c

    if emit(True, -1, None, False, 0) is None:                     # the opening baseline
        return out
    for i in range(pair_count):
        r = pair_first + i
        lseed, oseed = seeds[r]
        land = bl.Landscape(fitness, lseed, masks=masks, truth=truth)
        order = arm_order(r)
        runs: dict[str, tuple[list[str], str, list[int], int]] = {}       # arm -> (blocks, champion block, child genomes, champion genome)
        for a in order:                                            # the three searches, in this pair's order
            if a == "O":
                oo = oa.run_online(land, oseed, budget, fabric, keep_ledger=True, pair=r)
                if not oo.record_capable or len(oo.blocks) != budget or not oo.champion_block:
                    raise RuntimeError("the online run produced no record blocks: not a record-capable O run")
                runs[a] = (oo.blocks, oo.champion_block, oo.genomes, oo.champion.genome)
            else:
                res = bs.run(ARM_WIRE[a], land, None if a == "R" else view, oseed, budget, fabric, log_moves=True, pair=r)
                runs[a] = (res.blocks, res.champion_block, [m["genome"] for m in res.moves], res.champion.genome)
            blocks, _cb, genomes, _cg = runs[a]
            for n in range(budget):
                c = emit(False, r, a, False, genomes[n])
                if c is None:
                    return out
                c.block = blocks[n]
        for a in order:                                            # then the three champions' holdout evaluations
            _b, champion_block, _g, champion_genome = runs[a]
            c = emit(False, r, a, True, champion_genome)
            if c is None:
                return out
            c.block = champion_block
    emit(True, -1, None, False, 0)                                 # the closing baseline
    return out


def run_context(ctx, fabric: bs.ModelFabric | None = None, view: bmaps.MapView | None = None,
                truth: dict | None = None, masks: list[int] | None = None, unscored_at: int | None = None) -> Session:
    """The session a validated `b3_records.Context` describes (the plan's budget and slice, the
    prediction's seeds): the same `run`, with nothing chosen here."""
    return run(ctx.budget, ctx.pairs_total, ctx.pair_first, ctx.pair_count, ctx.seeds, fabric, view, truth, masks,
               ctx.fitness, unscored_at)

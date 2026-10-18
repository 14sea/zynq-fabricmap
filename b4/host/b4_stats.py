#!/usr/bin/env python3
"""B4-FF — the pure computation of the four-corner interaction index (docs/b4_architecture.md section 9, K10) and
its four per-seed outcomes. A computation; never a gate result — no threshold is set here (tau is a parameter and
has no default), and every value of a seed stays in the denominator over all S.

    r = four_corner(f, genome, a, b)             # f(genome) -> fitness, or raises DomainRefusal
    cls = classify(max_abs_index, tau)           # one of the four outcomes
    summary = summarise(per_seed_max, tau, S)

The four corners differ in (a, b) ONLY — every other bit of `genome`, the initial state and the stimulus are the
same four times (the caller's f fixes them). A pair with an illegal corner (DomainRefusal) is NOT comparable and is
recorded with the corner named.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_ff_model as fm  # noqa: E402

INTERACTING = "interacting"
NONZERO_BELOW_THRESHOLD = "nonzero_below_threshold"
NO_INTERACTION_SEEN = "no_interaction_seen_among_tested_comparisons"
NOT_ASSESSABLE = "not_assessable"
OUTCOMES = (INTERACTING, NONZERO_BELOW_THRESHOLD, NO_INTERACTION_SEEN, NOT_ASSESSABLE)


def four_corner(f, genome: int, a: int, b: int) -> dict:
    if a == b:
        raise ValueError("a pair needs two different bits")
    base = genome & ~(1 << a) & ~(1 << b)
    corners = {"00": base, "01": base | (1 << b), "10": base | (1 << a), "11": base | (1 << a) | (1 << b)}
    values, illegal = {}, []
    for name, g in corners.items():
        try:
            values[name] = f(g)
        except fm.DomainRefusal:
            illegal.append(name)
    if illegal:
        return {"a": a, "b": b, "comparable": False, "illegal_corners": illegal, "index": None, "values": values}
    index = values["11"] - values["10"] - values["01"] + values["00"]
    return {"a": a, "b": b, "comparable": True, "illegal_corners": [], "index": index, "values": values}


def classify(max_abs_index, tau: float) -> str:
    """max_abs_index: the largest |I_ab| over the seed's comparable pairs, or None when there is no comparable pair."""
    if not isinstance(tau, (int, float)) or isinstance(tau, bool) or tau < 0:
        raise ValueError("tau must be a non-negative number, fixed before the run")
    if max_abs_index is None:
        return NOT_ASSESSABLE
    if max_abs_index > tau:
        return INTERACTING
    if max_abs_index > 0:
        return NONZERO_BELOW_THRESHOLD
    return NO_INTERACTION_SEEN


def seed_max(results: list[dict]):
    """The largest |I_ab| over a seed's comparable pairs (None when none is comparable), and the counts."""
    comparable = [r for r in results if r["comparable"]]
    not_comparable = [r for r in results if not r["comparable"]]
    m = max((abs(r["index"]) for r in comparable), default=None)
    return m, {"comparable_pairs": len(comparable), "not_comparable_pairs": len(not_comparable),
               "illegal_corners": sorted({c for r in not_comparable for c in r["illegal_corners"]})}


def summarise(per_seed_max: list, tau: float, S: int) -> dict:
    """Counts of the four outcomes over ALL S seeds (per_seed_max has one entry per seed, None allowed); the
    fraction interacting over S — a computation, judged elsewhere against a threshold fixed beforehand."""
    if len(per_seed_max) != S:
        raise ValueError("one max per seed is required: S entries, None for a seed with no comparable pair")
    counts = {o: 0 for o in OUTCOMES}
    for m in per_seed_max:
        counts[classify(m, tau)] += 1
    return {"tau": tau, "S": S, "counts": counts, "fraction_interacting_over_S": counts[INTERACTING] / S if S else None,
            "note": "a seed with no comparable pair is not assessable and stays in the denominator; all comparable pairs at zero means no interaction seen among the tested comparisons, not that every context is additive; with tau = 0 the nonzero-below-threshold class is empty by definition"}

#!/usr/bin/env python3
"""B4 — the gate's STATISTICS, copied function by function from `host/b2_gate.py` (docs/b4_architecture.md section 9: "by
copy into the B4 namespace with their digests recorded, never by import across the pinned boundary"; the owner's ruling of
2026-10-18 on unit 2b-4a, section 2 item 2). The copies — `median`, `percentile`, `mean`, `cohen_d`, `sign_test_p`,
`bootstrap_reject_rate`, `required_pairs` — are the original's text; the dependencies are the standard library's
`math`, `statistics` and `random` and nothing of B4 imports the pinned module at runtime (the tests compare by import,
read-only). The PRNG of the bootstrap is Python's `random.Random(seed)`, as in B2; the power scan is the complete
ascending scan.

    p, pos, neg, ties = sign_test_p(deltas)       # one-sided exact; H1: P(Δ > 0 | Δ ≠ 0) > 1/2; all ties -> p = 1
    rate = bootstrap_reject_rate(deltas, n, alpha, experiments, seed)
    n, last = required_pairs(deltas, alpha, power_min, experiments, seed, n_min, n_max)
    n, last, scanned = required_pairs_scan(..., check=dl.check)    # the same scan, a deadline check before each N

`required_pairs_scan` is the harness's form of the scan: identical numbers (each N's bootstrap is seeded `seed + n` and
independent of the others), with a work-unit boundary before each N. `encode_stat` writes a statistic for JSON without
NaN / Infinity literals: a finite value as it is, a non-finite one as a named special with the numeric field null — a
legitimate +inf Cohen's d (all deltas equal and positive) is kept as such, never as 0 and never as a failure.
"""
from __future__ import annotations

import math
import random
import statistics

B2_GATE_REL = "host/b2_gate.py"
COPIED = ("median", "percentile", "mean", "cohen_d", "sign_test_p", "bootstrap_reject_rate", "required_pairs")


# ------------------------------------------------------------------ statistics (integer-safe, dependency-free) — host/b2_gate.py, verbatim
def median(xs):
    return statistics.median(xs)


def percentile(xs, p):
    s = sorted(xs)
    if not s:
        raise ValueError("empty")
    k = (len(s) - 1) * p / 100.0
    f, c = math.floor(k), math.ceil(k)
    return s[f] if f == c else s[f] + (s[c] - s[f]) * (k - f)


def mean(xs):
    return sum(xs) / len(xs)


def cohen_d(deltas):
    if len(deltas) < 2:
        return 0.0
    sd = statistics.stdev(deltas)
    return mean(deltas) / sd if sd > 0 else (math.inf if mean(deltas) > 0 else 0.0)


def sign_test_p(deltas) -> tuple[float, int, int, int]:
    """One-sided exact sign test, H1: P(delta > 0) > 1/2. Returns (p, positives, negatives, ties)."""
    pos = sum(1 for d in deltas if d > 0)
    neg = sum(1 for d in deltas if d < 0)
    n = pos + neg
    if n == 0:
        return 1.0, pos, neg, len(deltas)
    p = sum(math.comb(n, i) for i in range(pos, n + 1)) / 2 ** n
    return p, pos, neg, len(deltas) - n


def bootstrap_reject_rate(deltas, n_pairs: int, alpha: float, experiments: int, seed: int) -> float:
    rng = random.Random(seed)
    rejects = 0
    for _ in range(experiments):
        sample = [deltas[rng.randrange(len(deltas))] for _ in range(n_pairs)]
        if sign_test_p(sample)[0] <= alpha:
            rejects += 1
    return rejects / experiments


def required_pairs(deltas, alpha: float, power_min: float, experiments: int, seed: int, n_min: int, n_max: int):
    """The smallest N in [n_min, n_max] whose bootstrap power reaches power_min — EVERY N
    scanned in ascending order (the declared rule). Bootstrap power is not monotone in N
    (discrete rejection regions, simulation noise), so no bracketing or n_max shortcut may
    skip a candidate: the owner's review of 2026-09-10 found the earlier geometric sweep
    returning N = 91 where N = 89 already had power 0.906 (F3, budget 300)."""
    last = None
    for n in range(n_min, n_max + 1):
        last = bootstrap_reject_rate(deltas, n, alpha, experiments, seed + n)
        if last >= power_min:
            return n, last
    return None, last


# ------------------------------------------------------------------ the harness's forms (no formula changed)
def required_pairs_scan(deltas, alpha: float, power_min: float, experiments: int, seed: int, n_min: int, n_max: int, check=None):
    """`required_pairs` with a work-unit boundary before each N: `check()` is called before every N's bootstrap; a
    `StopWork` raised there ends the scan with what was scanned (`complete` False). Returns (n, last, record) where the
    record lists every (N, rate) computed in order; with no check, (n, last) equal `required_pairs`'s exactly."""
    from b4_deadline import StopWork  # local import keeps this module's statistics free of any other dependency
    scanned: list[list] = []
    last = None
    for n in range(n_min, n_max + 1):
        if check is not None:
            try:
                check()
            except StopWork as exc:
                return None, last, {"complete": False, "stopped_before_n": n, "reason": str(exc), "scanned": scanned}
        last = bootstrap_reject_rate(deltas, n, alpha, experiments, seed + n)
        scanned.append([n, last])
        if last >= power_min:
            return n, last, {"complete": True, "stopped_before_n": None, "reason": None, "scanned": scanned}
    return None, last, {"complete": True, "stopped_before_n": None, "reason": None, "scanned": scanned}


def encode_stat(x) -> dict:
    """A statistic for JSON without NaN / Infinity literals: {"value": finite number or None, "special": None / "+inf" / "-inf" / "nan"}."""
    if x is None:
        return {"value": None, "special": "none"}
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError(f"not a statistic: {x!r}")
    if isinstance(x, float):
        if math.isnan(x):
            return {"value": None, "special": "nan"}
        if math.isinf(x):
            return {"value": None, "special": "+inf" if x > 0 else "-inf"}
    return {"value": x, "special": None}


def finite_findings(obj, path: str = "$") -> list[str]:
    """Every float in a JSON-bound structure must be finite (json.dumps(allow_nan=False) would refuse otherwise)."""
    f: list[str] = []
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        f.append(f"{path}: {obj!r} is not finite; encode it with encode_stat")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            f += finite_findings(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            f += finite_findings(v, f"{path}[{i}]")
    return f

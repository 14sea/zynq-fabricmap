#!/usr/bin/env python3
"""B4 — K10's DRIVER (docs/b4_architecture.md section 9, K10; the owner's rulings of 2026-10-18 on unit 2b-3 section 5 and
on unit 2b-4a section 4.2): the four-corner interaction index over all 210 unordered address pairs in two fixed background
configurations, every corner kept whole.

    g0, g1 = backgrounds(landscape_seed)          # 0 and Rng((seed ^ 0x4C0A4E55) & 0xffffffff).uniform(1 << 21), the first call
    res = seed_k10(task, port, tau=2, check=...)  # 2 x 210 four-corner units; the per-seed max |I| and its outcome

The second background is drawn ONCE from its own generator, independent of the task, operator and control generators,
and kept even if it equals the first. The fitness of a corner is the task's score of the configuration's trace under the
task's search stimulus (`b4_landscape.score`); the four corners differ in the two addresses only (`b4_stats.four_corner`).
Every corner's genome, score and observation id are recorded; every unique observation keeps its full q grid
(`b4_observe.Memo`), so each score and each index can be recomputed offline (`recompute`). A memo hit changes the
call count only.

DOMAIN. `b4_stats.four_corner` catches a `DomainRefusal` and would go on to the remaining corners before returning
`comparable = False`; under hypothesis v0.3 every assignment is in the domain, so a refusal is not a result but the invalid
event of section 9.1 (the owner's review of 2026-10-18, F5). The driver's scoring function therefore converts the refusal
into `CornerRefused`, which `four_corner` does not catch: NO further corner is observed after the first refused one; the
corners obtained before it and the refused attempt are kept in the unit, and `K10Invalid` carries the partial result.
`b4_stats` itself is unchanged. Every other failure inside the computation (another refusal, an error, an external
interrupt) leaves the partial result on the exception as `k10_partial`.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_execution as ex  # noqa: E402
import b4_ff_model as fm  # noqa: E402
import b4_landscape as bl  # noqa: E402
import b4_stats as st  # noqa: E402
from b4_deadline import StopWork  # noqa: E402
from b4_observe import Memo  # noqa: E402
from b4_rng import Rng  # noqa: E402

SALT = 0x4C0A4E55
TAU = 2                                                             # section 9 K10: two fitness score units (the task's weights are all 1)


class K10Invalid(Exception):
    """A corner was refused (DOMAIN or another refusal) inside the K10 computation: invalid under section 9.1; the partial
    result travels with the exception."""

    def __init__(self, message: str, partial: dict):
        super().__init__(message)
        self.partial = partial


class CornerRefused(Exception):
    """Raised by the driver's scoring function in place of a `DomainRefusal`, so that `four_corner` (which catches only
    `DomainRefusal`) stops at the first refused corner instead of observing the remaining ones."""

    def __init__(self, genome: int, cause: BaseException):
        super().__init__(f"corner genome {genome} refused: {type(cause).__name__}: {cause}")
        self.genome, self.cause = genome, cause


CORNERS = ("00", "01", "10", "11")


def canonical_units() -> list[tuple[int, int, int]]:
    """The fixed order of the 420 units: background 0 then 1, the 210 unordered pairs (a < b) in lexicographic order."""
    return [(bi, a, b) for bi in (0, 1) for a in range(21) for b in range(a + 1, 21)]


def backgrounds(landscape_seed: int) -> list[int]:
    if not isinstance(landscape_seed, int) or isinstance(landscape_seed, bool) or not 0 <= landscape_seed <= 0xFFFFFFFF:
        raise ValueError("the landscape seed is a 32-bit int")
    rng = Rng((landscape_seed ^ SALT) & 0xFFFFFFFF)
    return [0, rng.uniform(1 << 21)]


def seed_k10(task: ex.PublicTask, port: ex.ObservationPort, tau: float = TAU, check=None) -> dict:
    n = len(task.addresses)
    if n != 21:
        raise ValueError("K10 is written for the 21-address universe")
    bgs = backgrounds(task.seed)
    memo = Memo(port)
    stim = list(task.stimulus)
    corner_obs: dict[str, int] = {}
    scores: dict[str, int] = {}

    def f(genome: int) -> int:
        try:
            obs_id, grid, _hit = memo.observe(genome, stim)
        except fm.DomainRefusal as exc:
            raise CornerRefused(genome, exc) from exc            # four_corner does not catch this: no further corner is observed
        corner_obs[str(genome)] = obs_id
        fit, _nones = bl.score_grid(grid, task)
        scores[str(genome)] = fit
        return fit

    def corners_of(bg: int, a: int, b: int) -> dict:
        return {k: {"genome": _corner_genome(bg, a, b, k), "score": scores.get(str(_corner_genome(bg, a, b, k))), "obs": corner_obs.get(str(_corner_genome(bg, a, b, k)))} for k in CORNERS}

    units: list[dict] = []
    stopped = None
    partial = lambda: {"landscape_seed": task.seed, "task_digest": task.digest(), "stimulus_sha256": ex.sha256_json(stim), "tau": tau,  # noqa: E731
                       "backgrounds": bgs, "backgrounds_equal": bgs[0] == bgs[1], "units_total": 2 * (n * (n - 1) // 2), "units": units,
                       "observations": memo.records(), "memo": memo.summary()}

    def invalid_partial(invalid: dict) -> dict:
        p = partial()
        p.update(complete=False, stopped=None, invalid=invalid, max_abs_index=None, comparable_pairs=None, not_comparable_pairs=None, outcome=None,
                 logical_corners=4 * len(units), note="invalid: the partial result as obtained; no outcome")
        return p

    for bi, a, b in canonical_units():
        bg = bgs[bi]
        if check is not None:
            try:
                check()
            except StopWork as exc:
                stopped = {"before_unit_index": len(units), "reason": str(exc)}
                break
        try:
            r = st.four_corner(f, bg, a, b)
        except CornerRefused as exc:
            names = [k for k in CORNERS if _corner_genome(bg, a, b, k) == exc.genome]
            units.append({"background_index": bi, "background": bg, "a": a, "b": b, "comparable": False, "illegal_corners": names, "index": None, "corners": corners_of(bg, a, b)})
            raise K10Invalid(f"K10 unit (background {bi}, {a}, {b}): corner {names} refused ({type(exc.cause).__name__}); no further corner observed",
                             invalid_partial({"unit_index": len(units) - 1, "illegal_corners": names, "exception": type(exc.cause).__name__,
                                              "reason": "a corner was refused (DOMAIN): invalid under section 9.1, never 'not comparable'; the corners obtained before it are kept"})) from exc.cause
        except BaseException as exc:  # noqa: BLE001 — another refusal, an error or an interrupt: the partial travels with it
            p = partial()
            if isinstance(exc, KeyboardInterrupt):
                p.update(complete=False, stopped={"before_unit_index": len(units), "reason": f"KeyboardInterrupt: an external interrupt inside unit {len(units)}"}, invalid=None,
                         max_abs_index=None, comparable_pairs=None, not_comparable_pairs=None, outcome=None, logical_corners=4 * len(units), note="interrupted: the partial result as obtained; no outcome")
            else:
                p = invalid_partial({"unit_index": len(units), "illegal_corners": [], "exception": type(exc).__name__, "reason": str(exc)})
            exc.k10_partial = p
            raise
        if not r["comparable"]:                                   # unreachable while f converts every DomainRefusal; kept as the fail-closed default
            units.append({"background_index": bi, "background": bg, "a": a, "b": b, "comparable": False, "illegal_corners": r["illegal_corners"], "index": None, "corners": corners_of(bg, a, b)})
            raise K10Invalid(f"K10 unit (background {bi}, {a}, {b}): corners {r['illegal_corners']} refused",
                             invalid_partial({"unit_index": len(units) - 1, "illegal_corners": r["illegal_corners"], "exception": "DomainRefusal",
                                              "reason": "a corner was refused (DOMAIN): invalid under section 9.1, never 'not comparable'"}))
        units.append({"background_index": bi, "background": bg, "a": a, "b": b, "comparable": True, "illegal_corners": [], "index": r["index"], "corners": corners_of(bg, a, b)})
    out = partial()
    complete = stopped is None
    out.update(complete=complete, stopped=stopped, invalid=None)
    if complete:
        m, counts = st.seed_max(units)
        out.update(max_abs_index=m, comparable_pairs=counts["comparable_pairs"], not_comparable_pairs=counts["not_comparable_pairs"],
                   outcome=st.classify(m, tau), logical_corners=4 * len(units))
    else:
        out.update(max_abs_index=None, comparable_pairs=None, not_comparable_pairs=None, outcome=None, logical_corners=4 * len(units))
    out["note"] = ("comparability is comparability inside the model's domain under the hypothesis — not buildable, writable or safe on a device; "
                   "a per-seed max over both backgrounds; these observations enter no ledger")
    return out


def canonical_findings(result: dict) -> list[str]:
    """The fixed comparison set: a complete record holds EXACTLY the 420 units (two backgrounds x 210 unordered pairs) in
    their order; a partial record holds a prefix; nothing is omitted, duplicated or reordered."""
    want = canonical_units()
    units = result["units"]
    f: list[str] = []
    if result["complete"] and len(units) != len(want):
        f.append(f"a complete K10 record holds {len(units)} units, the fixed set has {len(want)}")
    if len(units) > len(want):
        f.append(f"{len(units)} units recorded, more than the fixed set's {len(want)}")
    for i, (u, w) in enumerate(zip(units, want)):
        if (u["background_index"], u["a"], u["b"]) != w:
            f.append(f"unit {i}: not the fixed set's unit {i} (background {w[0]}, {w[1]}, {w[2]})"); break
    if result["units_total"] != len(want):
        f.append(f"units_total {result['units_total']} != {len(want)}")
    if result["logical_corners"] != 4 * len(units):
        f.append("logical_corners is not four per unit")
    return f


def _corner_genome(bg: int, a: int, b: int, name: str) -> int:
    base = bg & ~(1 << a) & ~(1 << b)
    return base | ((1 << a) if name[0] == "1" else 0) | ((1 << b) if name[1] == "1" else 0)


def recompute(result: dict, task: ex.PublicTask) -> list[str]:
    """Offline: every corner's score from its kept q grid under the task's mask, every index from the four scores, the
    per-seed max and outcome from the units; the backgrounds from the seed. Names every difference."""
    f: list[str] = []
    if result["backgrounds"] != backgrounds(task.seed):
        f.append("the backgrounds are not the seed's")
    f += canonical_findings(result)
    if len(result["units"]) > len(canonical_units()):
        return f
    obs = {o["id"]: o for o in result["observations"]}
    ids = sorted(obs)
    if ids != list(range(len(result["observations"]))):
        f.append("the observation ids are not unique 0 .. n-1")
    for o in obs.values():
        if ex.sha256_json(o["q_grid"]) != o["trace_sha256"]:
            f.append(f"observation {o['id']}: the q grid does not hash to its digest")
        if o["stimulus_sha256"] != result["stimulus_sha256"]:
            f.append(f"observation {o['id']}: not under the task's stimulus")
    for i, u in enumerate(result["units"]):
        bg, a, b = u["background"], u["a"], u["b"]
        if bg != result["backgrounds"][u["background_index"]]:
            f.append(f"unit {i}: the background is not the indexed one")
        scores = {}
        for k, c in u["corners"].items():
            if c["genome"] != _corner_genome(bg, a, b, k):
                f.append(f"unit {i} corner {k}: the genome is not the corner's"); continue
            if c["obs"] is None:
                if u["comparable"]:
                    f.append(f"unit {i} corner {k}: no observation on a comparable unit")
                continue
            o = obs.get(c["obs"])
            if o is None or o["genome"] != c["genome"]:
                f.append(f"unit {i} corner {k}: the observation is not of this corner"); continue
            fit, _ = bl.score_grid(o["q_grid"], task)
            if fit != c["score"]:
                f.append(f"unit {i} corner {k}: score recomputed {fit} != recorded {c['score']}")
            scores[k] = fit
        if u["comparable"]:
            if len(scores) == 4 and scores["11"] - scores["10"] - scores["01"] + scores["00"] != u["index"]:
                f.append(f"unit {i}: the index is not the four scores'")
    if result["complete"]:
        m, counts = st.seed_max(result["units"])
        if (m, counts["comparable_pairs"], counts["not_comparable_pairs"]) != (result["max_abs_index"], result["comparable_pairs"], result["not_comparable_pairs"]):
            f.append("the per-seed max / counts are not the units'")
        if st.classify(m, result["tau"]) != result["outcome"]:
            f.append("the outcome is not the classification of the max")
        if len(result["units"]) != result["units_total"]:
            f.append(f"{len(result['units'])} units recorded, {result['units_total']} planned, on a complete result")
    return f

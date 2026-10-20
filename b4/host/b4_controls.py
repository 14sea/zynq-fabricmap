#!/usr/bin/env python3
"""B4 — the CONTROL INPUTS of the exploration (docs/b4_architecture.md section 8; the owner's rulings of 2026-10-18 on
unit 2b-3 section 2 and on unit 2b-4a section 4.1): the two control generators and the frozen view control D builds on.

    sx = x_control_seed(landscape_seed, operator_seed)        # int.from_bytes(sha256('b4-x-control-1|<l>|<o>')[:4], 'big')
    sd = d_shuffle_seed(landscape_seed, operator_seed)        # int.from_bytes(sha256('b4-d-control-1|<l>|<o>')[:4], 'big')
    fv = f_frozen_view(f_result_dict, task)                   # the SAME seed's F-learned frozen MapView, REBUILT and held to the record
    dv, info = d_view(f_result_dict, task, landscape_seed)    # shuffled_view(fv, sd), with the permutation and the residual recorded (the seed is the harness's, not the task's)

Both seeds are UTF-8 decimal text with no spaces, each driving its own generator; neither consumes the task's or the
operator's stream; a coincidence of the two values is recorded, never redrawn.

`f_frozen_view` trusts no field that merely SAYS the map was learned. It accepts only a complete run of arm F with no
given view, a learned, non-privileged map origin and the FORMAL observation source (the hypothesis not a fixture, the
fabric the truth), replays the record (`b4_replay.replay`, no finding), rebuilds the frozen map from the ledger's base
observation and 21 single-flip probes with a fresh cartographer — checking every probe record's map version and
commitment as it goes — holds the search records to the frozen version and the result's final fields to the rebuilt
map, and returns the REBUILT view (groups, version, commitment; origin `learned`, provenance `("learned",)`,
privileged False). Anything else is `ControlInputRefusal`, by name.

D is that view through `b4_carto.shuffled_view` ONCE with the D shuffle seed: the parent's commitment and provenance
are kept (`("learned", "shuffled")`), the permutation actually applied is reconstructed from the same seed and
algorithm and checked against the produced groups, and the residual structure against the parent is reported — it may
be the identity or partition-preserving, and that is reported, never a reason to redraw. D's logical cost is the 21
probes obtained once by F; nothing is re-observed here.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_carto as bc  # noqa: E402
import b4_replay as br  # noqa: E402
import b4_execution as ex  # noqa: E402
from b4_rng import Rng  # noqa: E402

X_LABEL = "b4-x-control-1"
D_LABEL = "b4-d-control-1"
PROBES = 21
SEED_MAX = 0xFFFFFFFF


class ControlInputRefusal(ValueError):
    """A control input that cannot be built as specified — named, never guessed around."""


def _seed_int(v, name: str) -> int:
    if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= SEED_MAX:
        raise ValueError(f"{name} must be a 32-bit int, not {v!r}")
    return v


def _control_seed(label: str, landscape_seed: int, operator_seed: int) -> int:
    l_ = _seed_int(landscape_seed, "landscape_seed")
    o = _seed_int(operator_seed, "operator_seed")
    d = hashlib.sha256(f"{label}|{l_}|{o}".encode("utf-8")).digest()
    return int.from_bytes(d[:4], "big")


def x_control_seed(landscape_seed: int, operator_seed: int) -> int:
    return _control_seed(X_LABEL, landscape_seed, operator_seed)


def d_shuffle_seed(landscape_seed: int, operator_seed: int) -> int:
    return _control_seed(D_LABEL, landscape_seed, operator_seed)


# ------------------------------------------------------------------ F's frozen view, rebuilt
def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ControlInputRefusal(msg)


def f_frozen_view(result: dict, task: ex.PublicTask) -> bc.MapView:
    _require(isinstance(result, dict), "the F result must be a record (dict)")
    _require(result.get("arm") == "F", f"the frozen view is taken from arm F, not {result.get('arm')!r}")
    _require(result.get("given_view") is None, "a run with a given view learned nothing: not a learned F result")
    _require(result.get("completed") is True and result.get("search_completed") is True, "the F run is not complete")
    _require(result.get("terminal") is None and result.get("other_refusal") is None and result.get("control_failure") is None,
             "the F run carries a terminal event, a refusal or a control failure")
    _require(result.get("map_origin") == "learned" and result.get("map_privileged") is False, "the F result's map is not a learned, non-privileged map")
    _require(result.get("task_digest") == task.digest(), "the F result was not produced under this task")
    prov = result.get("provenance")
    _require(isinstance(prov, dict) and result.get("fixture") is False and result.get("fabric_fixture") is False
             and prov.get("hypothesis", {}).get("fixture") is False and prov.get("fabric", {}).get("kind") == "truth",
             "the F result's observation source is not the formal hypothesis on the truth fabric")
    findings = br.replay(result, task)
    _require(not findings, "the F record does not replay: " + "; ".join(findings[:5]))
    n = len(task.addresses)
    ledger = result["ledger"]
    _require(len(ledger) >= 1 + PROBES and ledger[0]["phase"] == "base" and all(e["phase"] == "probe" for e in ledger[1:1 + PROBES]),
             "the ledger does not begin with the base observation and 21 probes")
    _require(sorted(e["genome"] ^ task.base_genome for e in ledger[1:1 + PROBES]) == [1 << i for i in range(n)],
             "the probes are not one single flip of every address from the base")
    carto = bc.ObservationCarto(n)
    for e in ledger[:1 + PROBES]:
        _require(e["map_version_before"] == carto.version, f"seq {e['seq']}: map_version_before {e['map_version_before']} != rebuilt {carto.version}")
        carto.ingest(e["seq"], e["genome"], e["stimulus_sha256"], e["q_grid"])
        _require((e["map_version_after"], e["map_commitment_after"]) == (carto.version, carto.commitment()),
                 f"seq {e['seq']}: the recorded map version / commitment is not the rebuilt one")
    view = carto.view()
    for e in ledger[1 + PROBES:]:
        _require(e["phase"] in ("search", "holdout"), f"seq {e['seq']}: phase {e['phase']!r} after the probe pass")
        _require((e["map_version_before"], e["map_version_after"], e["map_commitment_after"]) == (view.version, view.version, view.commitment),
                 f"seq {e['seq']}: the map moved after the freeze")
    _require([list(g) for g in view.groups] == result["frozen_view"], "the recorded frozen_view is not the rebuilt groups")
    _require((result["map_version_final"], result["map_commitment_final"]) == (view.version, view.commitment), "the result's final map fields are not the rebuilt view's")
    return bc.MapView(view.groups, view.version, view.commitment, False, "learned", ("learned",))


# ------------------------------------------------------------------ D
def shuffle_permutation(view: bc.MapView, seed: int) -> dict:
    """The relabelling `shuffled_view` applies for this seed, reconstructed by the same algorithm (a seeded `sample` of
    the bits that appear in the view): {bit: relabelled bit}."""
    bits = sorted(b for g in view.groups for b in g)
    rng = Rng(seed)
    perm = rng.sample(bits, len(bits))
    return dict(zip(bits, perm))


def d_view(f_result: dict, task: ex.PublicTask, landscape_seed: int) -> tuple[bc.MapView, dict]:
    fv = f_frozen_view(f_result, task)
    seed = d_shuffle_seed(landscape_seed, f_result["operator_seed"])
    dv = bc.shuffled_view(fv, seed)
    relabel = shuffle_permutation(fv, seed)
    want = tuple(tuple(sorted(relabel[b] for b in g)) for g in fv.groups)
    _require(dv.groups == want, "the shuffled view's groups are not the seeded relabelling of the parent's")
    _require(dv.provenance == ("learned", "shuffled") and dv.origin == "shuffled" and dv.privileged is False
             and dv.base_commitment == fv.commitment and dv.version == fv.version, "the shuffled view does not carry its parent")
    info = {"d_shuffle_seed": seed, "parent_commitment": fv.commitment, "parent_groups": [list(g) for g in fv.groups],
            "permutation": {str(k): v for k, v in sorted(relabel.items())}, "identity": all(k == v for k, v in relabel.items()),
            "residual_structure": bc.residual_structure(dv, fv), "logical_cost_probes": PROBES, "reobserved": 0}
    return dv, info


def verify_d_view(given_view: dict, f_result: dict, task: ex.PublicTask, landscape_seed: int) -> list[str]:
    """The given view a D run recorded, held to the one `d_view` rebuilds for the same F result, task and landscape seed."""
    try:
        dv, _ = d_view(f_result, task, landscape_seed)
    except (ControlInputRefusal, ValueError) as exc:
        return [f"D's parent view cannot be rebuilt: {exc}"]
    f: list[str] = []
    if dv.as_dict() != given_view:
        f.append("the recorded given view is not the one rebuilt from F's record and the D shuffle seed")
    return f

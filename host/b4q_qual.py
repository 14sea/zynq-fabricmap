#!/usr/bin/env python3
"""B4Q — the QUALIFICATION READINGS of docs/b4_observation_contract.md computed over records (and recomputed by the verifier from
the retained records against the retained conclusions: a conclusion is never trusted from its file), exactly as the contract
fixes them, so that the plan's outcome rules are executable on evidence (the session's and the bench's) and never applied
by hand: the A5 decision table (5.6), the SR-evidence joint reading of 6.5 and the precedence-ordered A8 classification of
6.7 over a 2 x 2 cross, the A2 per-row verdict (7.1). A reading computed on the host emulation is a reading of the
hypothesis model's records — the mechanics of the rule, not a silicon result."""
from __future__ import annotations


def post_init_projection(o: dict, x: dict | None) -> dict:
    """5.6: steps[0].q_after, every field of steps[1:], X.cleanup.final_q — the pre-init state excluded in both places."""
    proj = {"init_q_after": list(o["steps"][0]["q_after"]) if o.get("steps") else None,
            "steps": [{k: s[k] for k in s if k != "step"} for s in o.get("steps", [])[1:]],
            "cleanup_final_q": (x or {}).get("cleanup", {}).get("final_q") if x else None}
    return proj


def _complete(o) -> bool:
    return isinstance(o, dict) and o.get("status") == "complete" and isinstance(o.get("steps"), list) and bool(o["steps"])


def a5_verdict(o_c1: dict, o_cprime: dict, o_c2: dict, x_c1: dict | None = None, x_c2: dict | None = None, x_cprime: dict | None = None) -> dict:
    """The decision table of 5.6, per element and for the cross: the injection witness (O_c2.initial.q vs O_c1.initial.q and
    vs O_c′.steps[-1].q_after) checked apart from the post-init projection (O_c2 vs O_c1). The projection INCLUDES the cleanup
    witness of each closed X (5.6), so a pass needs: J1 and J3 complete and CLOSED (their X with the cleanup), J2 complete and its
    X `injection_open`; anything less is `not_demonstrated` — never a pass (the owner's R3 of 2026-10-27)."""
    for name, o in (("J1", o_c1), ("J2", o_cprime), ("J3", o_c2)):
        if not _complete(o):
            return {"verdict": "not_demonstrated", "why": f"{name}'s observation is not complete", "per_element": None}
    for name, x in (("J1", x_c1), ("J3", x_c2)):
        if not (isinstance(x, dict) and x.get("status") == "closed" and isinstance(x.get("cleanup"), dict) and "final_q" in x["cleanup"]):
            return {"verdict": "not_demonstrated", "why": f"{name}'s transaction close with its cleanup witness is absent: the post-init projection cannot be compared", "per_element": None}
    if not (isinstance(x_cprime, dict) and x_cprime.get("status") == "injection_open"):
        return {"verdict": "not_demonstrated", "why": "J2's close is not injection_open: no injection was left open", "per_element": None}
    q1, q2 = o_c1.get("initial", {}).get("q"), o_c2.get("initial", {}).get("q")
    injected = o_cprime["steps"][-1]["q_after"] if o_cprime.get("steps") else None
    if q1 is None or q2 is None or injected is None:
        return {"verdict": "not_demonstrated", "why": "a pre-init sample or the injected state is absent", "per_element": None}
    arrived = (q2 != q1) and (q2 == injected)
    if not arrived:
        return {"verdict": "not_demonstrated", "why": "the injection did not reach the pre-init boundary (O_c2.initial.q equals O_c1's, or is not the injected state)",
                "per_element": [{"element": i, "c1": q1[i], "c2": q2[i], "injected": injected[i]} for i in range(8)]}
    p1, p2 = post_init_projection(o_c1, x_c1), post_init_projection(o_c2, x_c2)
    equal = p1 == p2
    diff = []
    if not equal:
        for k, (a, b) in enumerate(zip(p1["steps"], p2["steps"])):
            for i in range(8):
                if a["q_after"][i] != b["q_after"][i]:
                    diff.append({"step": k + 1, "element": i, "c1": a["q_after"][i], "c2": b["q_after"][i]})
        if p1["init_q_after"] != p2["init_q_after"]:
            diff += [{"step": 0, "element": i, "c1": p1["init_q_after"][i], "c2": p2["init_q_after"][i]} for i in range(8) if p1["init_q_after"][i] != p2["init_q_after"][i]]
    return {"verdict": "pass" if equal else "fail", "why": ("this adversarial state arrived and was cleared by the initialisation" if equal else "persistence after initialisation; the differing positions are the finding"),
            "injection_witness": {"arrived": True, "c1_initial_q": q1, "c2_initial_q": q2, "injected_state": injected}, "differing_positions": diff,
            "limit": "a pass establishes that THIS specified state does not reach the next record; not that no leftover state can"}


# ---------------------------------------------------------------- 6.5: the SR evidence of one element over the demonstration stimulus
def sr_reading(o: dict, e: int, parts: dict) -> dict:
    """`parts`: the step indices of the demonstration stimulus (1-based into O.steps) — {K0, K1, P0, R0, P1, R1}: the two reference
    captures, episode 0's prior and edge samples, episode 1's. Returns the reading of 6.5 for element e: restore(v) / capture /
    hold / inconsistent / unknown, with the six samples."""
    try:
        s = {name: o["steps"][idx]["q_after"][e] for name, idx in parts.items()}
    except (IndexError, KeyError, TypeError):
        return {"reading": "unknown", "why": "a sample is absent", "samples": None}
    if any(v is None for v in s.values()):
        return {"reading": "unknown", "why": "a sample has no value", "samples": s}
    if not (s["K0"] == 0 and s["K1"] == 1):
        return {"reading": "unknown", "why": "the reference does not discriminate (K0, K1) != (0, 1)", "samples": s}
    if not (s["P0"] == 1 and s["P1"] == 0):
        return {"reading": "unknown", "why": "the priors are not as planted (P0, P1) != (1, 0)", "samples": s}
    r0, r1 = s["R0"], s["R1"]
    if r0 == r1:
        return {"reading": "restore", "value": r0, "samples": s}
    if (r0, r1) == (0, 1):
        return {"reading": "capture", "samples": s}
    if (r0, r1) == (1, 0):
        return {"reading": "hold", "samples": s}
    return {"reading": "inconsistent", "samples": s}


# ---------------------------------------------------------------- 6.7: the cross
def a8_classify(corners: dict, e: int, parts: dict, predicted_init_dir: int = 1, predicted_srval_dir: int = 1, closes: dict | None = None) -> dict:
    """`corners`: {"00": O, "01": O, "10": O, "11": O} keyed (INIT, SRVAL) by the genome bits as written (bit = 1 reads INIT = 0 /
    SRVAL = 0 under the project's reading); `closes`: the corners' X (each must be `closed` — a corner without its closed
    transaction is not a demonstrated context, 6.7's preconditions). The quantities and the first matching row of 6.7; a context
    not observable is `unknown` whatever the row. The predicted direction: with ZINI = 1 meaning INIT = 0, i_c = 1 - bit."""
    if set(corners) != {"00", "01", "10", "11"}:
        return {"row": 0, "verdict": "not demonstrated", "why": "the four corners are not all present", "quantities": {"not_assessable": True}}
    for c in corners:
        if not _complete(corners[c]):
            return {"row": 0, "verdict": "not demonstrated", "why": f"corner {c}'s observation is not complete", "quantities": {"not_assessable": True}}
        x = (closes or {}).get(c)
        if not (isinstance(x, dict) and x.get("status") == "closed"):
            return {"row": 0, "verdict": "not demonstrated", "why": f"corner {c}'s transaction is not closed (the frame / Q-restoration witnesses of 5.4 are its X's)", "quantities": {"not_assessable": True}}
    i = {c: (corners[c]["steps"][0]["q_after"][e] if corners[c].get("steps") else None) for c in corners}
    s = {c: sr_reading(corners[c], e, parts) for c in corners}
    if any(v is None for v in i.values()) or any(s[c]["reading"] == "unknown" for c in s):
        row = 0; verdict = "not demonstrated"
        return {"row": row, "verdict": verdict, "init_samples": i, "sr_readings": s, "quantities": {"not_assessable": True}}
    exp_init = {c: 1 - int(c[0]) if predicted_init_dir else int(c[0]) for c in corners}
    init_effect = (i["00"] != i["10"] and i["01"] != i["11"] and i["00"] == exp_init["00"] and i["10"] == exp_init["10"] and i["01"] == exp_init["01"] and i["11"] == exp_init["11"])
    init_absent = (i["00"] == i["10"] and i["01"] == i["11"])
    rs = {c: s[c]["reading"] for c in s}
    vals = {c: s[c].get("value") for c in s}
    exp_srval = {c: 1 - int(c[1]) if predicted_srval_dir else int(c[1]) for c in corners}
    all_restore = all(r == "restore" for r in rs.values())
    srval_effect = all_restore and vals["00"] != vals["01"] and vals["10"] != vals["11"] and all(vals[c] == exp_srval[c] for c in corners)
    srval_absent = (all(r == "capture" for r in rs.values()) or all(r == "hold" for r in rs.values()) or (all_restore and vals["00"] == vals["01"] and vals["10"] == vals["11"]))
    cross_tracking = (i["00"] != i["01"] or i["10"] != i["11"]) or (all_restore and (vals["00"] != vals["10"] or vals["01"] != vals["11"]))
    inconsistent = (not init_effect and not init_absent) or (not srval_effect and not srval_absent) or any(r == "inconsistent" for r in rs.values())
    q = {"not_assessable": False, "init_effect": init_effect, "init_absent": init_absent, "srval_effect": srval_effect, "srval_absent": srval_absent, "cross_tracking": cross_tracking, "inconsistent": inconsistent}
    if cross_tracking or inconsistent:
        row, verdict = 1, "failed / unresolved"
    elif init_effect and srval_effect:
        row, verdict = 2, "both demonstrated"
    elif init_absent and srval_effect:
        row, verdict = 3, "SRVAL demonstrated; INIT not"
    elif init_effect and srval_absent:
        row, verdict = 4, "INIT demonstrated; SRVAL not"
    else:
        row, verdict = 5, "neither demonstrated"
    return {"row": row, "verdict": verdict, "init_samples": i, "sr_readings": s, "quantities": q,
            "limit": "a reading of the records under the fixed rule; attribution (mechanism, timing, instrumentation, model) is left to independent evidence"}


# ---------------------------------------------------------------- 7.1: A2
def a2_row(o_g0: dict | None, o_g1: dict | None, x_g0: dict | None = None, x_g1: dict | None = None) -> dict:
    """One A2 row: the two endpoints' observations under the demonstration stimulus — the readout differs at some point or does
    not; an endpoint without a valid complete, CLOSED observation is 'not assessable' (an emulation of a latch endpoint carries
    unmodelled cells: the board supplies physical values there). `differs` is the positive control; `does_not_differ` is a
    recorded negative, never a positive control."""
    if not (_complete(o_g0) and _complete(o_g1)):
        return {"verdict": "not_assessable", "why": "an endpoint has no complete observation"}
    if not all(isinstance(x, dict) and x.get("status") == "closed" for x in (x_g0, x_g1)):
        return {"verdict": "not_assessable", "why": "an endpoint's transaction is not closed"}
    g0 = [s["q_after"] for s in o_g0["steps"]]; g1 = [s["q_after"] for s in o_g1["steps"]]
    diffs = [(k, i) for k, (a, b) in enumerate(zip(g0, g1)) for i in range(8) if a[i] != b[i]]
    return {"verdict": "differs" if diffs else "does_not_differ", "differing_points": diffs[:16], "n_differing": len(diffs)}

#!/usr/bin/env python3
"""B4 — the map REBUILT FROM THE LEDGER (K7 of docs/b4_architecture.md section 9; the owner's rulings of 2026-10-18 on
unit 2b-3 section 2 and on unit 2b-4a section 4.1). Nothing in `b4_engine` or `RunResult` changes: every ledger entry
already records the map version before and after it and the commitment after it, so the relations a run learned are
recomputed here from the ledger alone and held to those records, entry by entry.

    snap = prefix_states(o_result_dict, task, B)      # K7 (b): arm O's B* search prefix — the base and the first B search
                                                      # evaluations, B + 1 records — rebuilt; the four states, summing to 21
    rec = recompute_findings(result_dict, task)       # K7 (a): the whole ledger, every arm; the final relations for the archive

What is ingested, per arm (the engine's own rule, re-stated so it cannot be bent):
  O                 the base and every search record, in order; the holdout record is not learned from;
  X                 the same records, the genome RELABELLED through the recorded π into the cartographer and the TRUE
                    genome into a shadow; the shadow contract is checked after every ingest and must agree with the
                    record (no finding, or the recorded control failure at its exposing record);
  F, no given view  the base and the 21 probe records ONLY; the map is frozen from there, and every later record must
                    carry the frozen version — the whole F ledger is never fed to a cartographer as if it were the map;
  F, a given view   (D / Ω / A0) nothing is learned; every record must carry the given view's version and commitment;
  R                 no map; every record must carry version 0 and an empty commitment.
For R and the given views the four-state counts are NOT APPLICABLE (there are no relations); nothing is invented.

A mismatch is a FINDING of the record, never a result about the fabric; the states are counts of the rebuilt relations
(`unknown` / `effect_seen` / `no_effect_seen` / `context_dependent`), and `not unknown` means neither a usable grouping
nor a decoded semantic.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_carto as bc  # noqa: E402
import b4_execution as ex  # noqa: E402

PROBES = 21
MODES = ("online", "relabelled", "learned_frozen", "given", "none")


def ledger_map_mode(result: dict) -> str:
    arm = result["arm"]
    if arm == "O":
        return "online"
    if arm == "X":
        return "relabelled"
    if arm == "F":
        return "given" if result.get("given_view") is not None else "learned_frozen"
    if arm == "R":
        return "none"
    raise ValueError(f"arm {arm!r}")


def states_of(carto: bc.ObservationCarto) -> dict:
    counts = {s: 0 for s in bc.STATES}
    for a in range(carto.n):
        counts[carto.rel[a].state] += 1
    return {"counts": counts, "not_unknown": carto.n - counts["unknown"], "n": carto.n}


def _ingest_checked(carto: bc.ObservationCarto, e: dict, genome: int, findings: list[str]) -> None:
    if e["map_version_before"] != carto.version:
        findings.append(f"seq {e['seq']}: map_version_before {e['map_version_before']} != rebuilt {carto.version}")
    carto.ingest(e["seq"], genome, e["stimulus_sha256"], e["q_grid"])
    if (e["map_version_after"], e["map_commitment_after"]) != (carto.version, carto.commitment()):
        findings.append(f"seq {e['seq']}: the recorded map version / commitment after is not the rebuilt one")


def _hold(e: dict, version: int, commitment: str, findings: list[str], what: str) -> None:
    if (e["map_version_before"], e["map_version_after"], e["map_commitment_after"]) != (version, version, commitment):
        findings.append(f"seq {e['seq']}: the record does not carry the {what} map (version {version})")


def rebuild(result: dict, task: ex.PublicTask, upto: int | None = None) -> dict:
    """Re-ingest the ledger's first `upto` records (all when None) under the arm's rule. Returns the cartographer (or
    None), the shadow (X only), the findings and the state counts (or not applicable)."""
    mode = ledger_map_mode(result)
    n = len(task.addresses)
    ledger = result["ledger"] if upto is None else result["ledger"][:upto]
    findings: list[str] = []
    carto: bc.ObservationCarto | None = None
    shadow: bc.ObservationCarto | None = None
    if mode == "none":
        for e in ledger:
            _hold(e, 0, "", findings, "absent")
        return {"mode": mode, "carto": None, "shadow": None, "findings": findings, "states": None, "applicable": False}
    if mode == "given":
        view = bc.MapView.from_dict(result["given_view"])
        for e in ledger:
            _hold(e, view.version, view.commitment, findings, "given")
        return {"mode": mode, "carto": None, "shadow": None, "findings": findings, "states": None, "applicable": False}
    carto = bc.ObservationCarto(n)
    if mode == "learned_frozen":
        learned = [e for e in ledger if e["phase"] in ("base", "probe")]
        if len(learned) > 1 + PROBES or [e["phase"] for e in learned] != ["base"] + ["probe"] * (len(learned) - 1):
            findings.append("the learned records are not the base followed by the probes")
        for e in learned:
            _ingest_checked(carto, e, e["genome"], findings)
        if len(learned) == 1 + PROBES:
            view = carto.view()
            for e in ledger[1 + PROBES:]:
                _hold(e, view.version, view.commitment, findings, "frozen")
        elif any(e["phase"] in ("search", "holdout") for e in ledger):
            findings.append("search or holdout records before the probe pass completed")
        return {"mode": mode, "carto": carto, "shadow": None, "findings": findings, "states": states_of(carto), "applicable": True}
    perm = result.get("x_perm") if mode == "relabelled" else None
    if mode == "relabelled":
        if not (isinstance(perm, list) and sorted(perm) == list(range(n))):
            return {"mode": mode, "carto": None, "shadow": None, "findings": ["control X carries no permutation over the addresses"], "states": None, "applicable": True}
        shadow = bc.ObservationCarto(n)
    cf = result.get("control_failure")
    for e in ledger:
        if e["phase"] == "holdout":
            _hold(e, carto.version, carto.commitment(), findings, "final online")
            continue
        if e["phase"] not in ("base", "search"):
            findings.append(f"seq {e['seq']}: phase {e['phase']!r} on an online arm")
            continue
        if mode == "relabelled":
            _ingest_checked(carto, e, bc.relabel_genome(e["genome"], perm), findings)
            shadow.ingest(e["seq"], e["genome"], e["stimulus_sha256"], e["q_grid"])
            iso = bc.isomorphic_addresses(carto, shadow, perm)
            exposing = cf is not None and cf["seq"] == e["seq"]
            if exposing and iso != cf["findings"]:
                findings.append(f"seq {e['seq']}: the recorded control failure's findings are not the rebuilt contract check's")
            elif not exposing and iso:
                findings.append(f"seq {e['seq']}: the rebuilt relabelled map and shadow disagree where no control failure was recorded")
        else:
            _ingest_checked(carto, e, e["genome"], findings)
    return {"mode": mode, "carto": carto, "shadow": shadow, "findings": findings, "states": states_of(carto), "applicable": True}


def prefix_states(result: dict, task: ex.PublicTask, budget: int) -> dict:
    """K7 (b): arm O's search prefix at `budget` — the base observation and the first `budget` search evaluations, exactly
    `budget + 1` ledger records — rebuilt from the true ledger; nothing from after it and nothing from the holdout."""
    if result.get("arm") != "O":
        raise ValueError("K7 (b)'s coverage is read on arm O's prefix; other arms' maps are reported by arm_states, separately")
    if not isinstance(budget, int) or isinstance(budget, bool) or budget < 1:
        raise ValueError("the budget must be a positive int")
    ledger = result["ledger"]
    records = ledger[:budget + 1]
    findings: list[str] = []
    if len(records) != budget + 1:
        findings.append(f"the ledger holds {len(ledger)} records, fewer than the {budget + 1} the prefix needs")
    elif [e["phase"] for e in records] != ["base"] + ["search"] * budget:
        findings.append("the prefix is not the base followed by search records")
    if findings:
        return {"arm": "O", "budget": budget, "records": len(records), "findings": findings, "states": None, "not_unknown": None,
                "map_version": None, "map_commitment": None, "relations": None}
    r = rebuild(result, task, upto=budget + 1)
    carto = r["carto"]
    return {"arm": "O", "budget": budget, "records": budget + 1, "findings": r["findings"], "states": r["states"]["counts"],
            "not_unknown": r["states"]["not_unknown"], "map_version": carto.version, "map_commitment": carto.commitment(),
            "relations": carto.relations_doc()}


def recompute_findings(result: dict, task: ex.PublicTask) -> dict:
    """K7 (a): the whole ledger rebuilt under the arm's rule and the result's final map fields held to it; the rebuilt
    relations returned for the archive. `applicable` False for R and the given views (no relations exist)."""
    r = rebuild(result, task)
    findings = list(r["findings"])
    carto = r["carto"]
    out = {"arm": result["arm"], "mode": r["mode"], "applicable": r["applicable"], "findings": findings, "states": None,
           "relations_final": None, "map_version": None, "map_commitment": None}
    if not r["applicable"] or carto is None:
        if r["mode"] in ("none", "given"):
            want_v = 0 if r["mode"] == "none" else result["given_view"]["version"]
            want_c = "" if r["mode"] == "none" else result["given_view"]["commitment"]
            if (result["map_version_final"], result["map_commitment_final"]) != (want_v, want_c):
                findings.append("the result's final map fields are not the absent / given map's")
        return out
    out.update({"states": r["states"]["counts"], "relations_final": carto.relations_doc(), "map_version": carto.version, "map_commitment": carto.commitment()})
    if (result["map_version_final"], result["map_commitment_final"]) != (carto.version, carto.commitment()):
        findings.append("the result's final map version / commitment is not the rebuilt one")
    if r["mode"] in ("online", "relabelled"):
        if (result["map_specimens_final"], result["map_multi_bit_pairs_final"]) != (len(carto.specimens), carto.multi_bit_pairs):
            findings.append("the result's specimen / multi-bit counts are not the rebuilt cartographer's")
    if r["mode"] == "learned_frozen":
        if result["frozen_view"] is not None and [list(g) for g in carto.view().groups] != result["frozen_view"]:
            findings.append("the recorded frozen_view is not the rebuilt groups")
    if r["mode"] == "relabelled" and r["shadow"] is not None:
        perm = result["x_perm"]
        iso = bc.isomorphic_addresses(carto, r["shadow"], perm)
        if result.get("x_isomorphism_findings") is not None and iso != result["x_isomorphism_findings"]:
            findings.append("the final isomorphism findings are not the rebuilt ones")
        if result.get("x_residual") is not None and bc.residual_structure(carto.view(), r["shadow"].view()) != result["x_residual"]:
            findings.append("the recorded residual structure is not the rebuilt one")
    return out


def arm_states(result: dict, task: ex.PublicTask) -> dict:
    """The four states of an arm's FINAL map (F: the post-probe frozen map) — reported beside K7 (b), never in its place."""
    r = recompute_findings(result, task)
    return {"arm": result["arm"], "mode": r["mode"], "applicable": r["applicable"], "states": r["states"],
            "not_unknown": (sum(r["states"].values()) - r["states"]["unknown"]) if r["states"] else None, "findings": r["findings"],
            "note": "not K7 (b): K7 (b) is read on arm O's B* prefix only"}

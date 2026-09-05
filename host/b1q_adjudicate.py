#!/usr/bin/env python3
"""B1Q — adjudication of the CARRIER QUALIFICATION session's evidence directory (pure;
re-runnable; nothing here touches a board). docs/b1_carrier_qualification.md §3.

    b1q_adjudicate.py --evidence <dir> [--manifest …] [--out …]

The qualification session is the B1 image with budget 9 on the B1 carrier: the opening
baseline, the nine code probes, the closing baseline, the closing unsigned control; every
record audited. What it establishes ON SILICON, and what this adjudicator therefore
requires, record by record:

  pins / binding   as the mapping adjudicator's (host/b1_adjudicate.py), for session "B1Q"
                   and the qualification plan pinned in the manifest (`qualification_plan`);
                   no qualification is required of the carrier for its own qualification.
  instrument       the B1 validator with the audit gate (every readout host-verified against
                   the served words), closure, controls, the closing unsigned control refused
                   F_ARM_AUTH (the authorisation half of the gate is the instrument's).
  completion       COMPLETED at seq 11.
  VARIANT          the IDENT carries the B1 gate word over the PS path (binding).
  baselines        seq 1 and seq 11: readout all zero; counters = the scorer's base for a
                   blank candidate (the scorer is unchanged); STATUS after the ARM:
                   configuration_valid_hw = 1, fault = 0, tables_match = 1 (a zero readout
                   equals the zero table words — the observation, not a gate).
  code probes      seq 2..10: SCORED; readout NOT all zero (the fabric answered);
                   configuration_valid_hw = 1, fault = 0 and **tables_match = 0** — the PL
                   ARMed and scored a candidate whose readout differs from the signed table
                   words: the noninterference contract, observed on the silicon. This is the
                   direct hardware evidence the owner ruled sufficient (2026-09-05); there is
                   no host-attested reply control on the board.
  replay           the nine probes are the reference's proposals and every block matches
                   (the orchestrator on silicon); the content equals the pinned prediction
                   (the readouts are what the certificate says they are).

Outcome PASS / HOLD / KILL / REFUSED as the mapping adjudicator's. A PASS is turned into
the carrier's qualification record by host/b1_qualification.py, which the mapping runner
and adjudicator re-verify (and re-adjudicate) every time — never a bare flag.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_adjudicate as adj  # noqa: E402
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b1_pins as pins_mod  # noqa: E402
import b1_verify as bv  # noqa: E402

TOOL_VERSION = "b1q_adjudicate.py/0.1.0"
SESSION = "B1Q"
RULING_TEXT = "whole-of-run B1 carrier qualification"
ST_FAULT, ST_CFG_VALID, ST_TABLES_MATCH = 1, 2, 10          # rtl/b1/b1_axil.v STATUS bits
Refusal = adj.Refusal


def check_q_pins(manifest: dict, plan_path: Path, prediction_path: Path, pins_path: Path | None,
                 plan: dict | None, prediction: dict | None) -> None:
    q = manifest.get("qualification_plan")
    if not q:
        raise Refusal("the manifest pins no qualification plan (b1_plan.py --qualification --write-manifest)")
    for what, path, want, obj in (("qualification plan", plan_path, q["sha256"], plan),
                                  ("qualification prediction", prediction_path, q["prediction_sha256"], prediction)):
        if not want:
            raise Refusal(f"the manifest pins no {what} sha256")
        if not Path(path).is_file() or adj.sha256_of(Path(path)) != want:
            raise Refusal(f"{path} does not hash to the manifest's {what} pin")
        if obj is not None and json.loads(Path(path).read_text()) != obj:
            raise Refusal(f"the {what} object given to the adjudicator is not the pinned file's content")
    try:
        pins_mod.verify(pins_path or pins_mod.PINS, manifest)
    except pins_mod.PinRefusal as exc:
        raise Refusal(f"instrument pins: {exc}") from None


def gate_findings(log: dict, plan: dict, prediction: dict) -> list[str]:
    """The per-record silicon observations the qualification exists to establish."""
    f: list[str] = []
    budget = plan["budget"]
    baselines = {1, budget + 2}
    base_scores = list(prediction["baseline_scores"])
    recs = sorted(log["loop_records"], key=lambda r: int(r["seq"]))
    seqs = [int(r["seq"]) for r in recs]
    if seqs != list(range(1, budget + 3)):
        f.append(f"gate: records {seqs} are not seq 1..{budget + 2}")
    for r in recs:
        seq = int(r["seq"])
        if r.get("outcome") != "SCORED":
            f.append(f"gate: seq {seq} outcome {r.get('outcome')!r}, every qualification record must be SCORED"); break
        ev = r["evidence"]
        st = int(ev["arm"]["status_after"], 16)
        tables = [int(x, 16) for x in ev["score"]["functional_readout"]]
        zero = not any(tables)
        cfg, fault, tm = (st >> ST_CFG_VALID) & 1, (st >> ST_FAULT) & 1, (st >> ST_TABLES_MATCH) & 1
        if ev["arm"].get("fault_after") != 0 or fault != 0:
            f.append(f"gate: seq {seq} ARMed with a fault (fault_after {ev['arm'].get('fault_after')}, STATUS fault bit {fault})"); break
        if cfg != 1:
            f.append(f"gate: seq {seq} STATUS configuration_valid_hw = {cfg}, the gate did not validate"); break
        if seq in baselines:
            if not zero:
                f.append(f"gate: seq {seq} (baseline) readout is not all zero"); break
            if tm != 1:
                f.append(f"gate: seq {seq} (baseline) tables_match = {tm}, a zero readout must equal the zero table words"); break
            if list(ev["score"]["scores"]) != base_scores:
                f.append(f"gate: seq {seq} (baseline) counters {ev['score']['scores']} != the scorer's base {base_scores}"); break
        else:
            if zero:
                f.append(f"gate: seq {seq} (code probe) readout is all zero — the fabric did not answer"); break
            if tm != 0:
                f.append(f"gate: seq {seq} (code probe) tables_match = {tm}: a non-zero readout cannot equal the zero table words"); break
    return f


def adjudicate(evidence: Path, manifest: dict, plan: dict, prediction: dict, manifest_sha256: str,
               instrument_root: Path | None = None, require_git: bool = True, p3_layer=None,
               plan_path: Path | None = None, prediction_path: Path | None = None, pins_path: Path | None = None) -> dict:
    out = {"tool": TOOL_VERSION, "session": SESSION, "evidence": str(evidence), "outcome": None, "findings": [], "refusal": None}
    try:
        q = manifest.get("qualification_plan") or {}
        check_q_pins(manifest, plan_path or REPO_ROOT / q.get("path", "MISSING"), prediction_path or REPO_ROOT / q.get("prediction_path", "MISSING"),
                     pins_path, plan, prediction)
        if plan.get("session") != SESSION or plan.get("budget") != bc.CODE_BITS:
            raise Refusal(f"the plan is not the qualification plan (session {plan.get('session')!r}, budget {plan.get('budget')!r})")
        log = json.loads((evidence / "run_log.json").read_text())
        out["binding"] = adj.check_binding(log, manifest, plan, manifest_sha256, SESSION, None)
        p3 = adj._p3_layer(evidence, log, manifest, plan, instrument_root, require_git) if p3_layer is None \
            else p3_layer(evidence, log, plan)
        out["p3"] = {k: v for k, v in p3.items() if k not in ("findings", "rate_report")}
        findings = list(p3["findings"])
        if p3.get("rejected"):
            out["outcome"] = p3["rejected"]; out["findings"] = findings
            return out
        end = log["session_summary"]["epoch_end"]
        if end.get("kind") != "COMPLETED":
            findings.append(f"completion: epoch ended {end.get('kind')} ({end.get('reason')}) at seq {end.get('last_seq')}")
        elif int(end.get("last_seq") or 0) != plan["budget"] + 2:
            findings.append(f"completion: COMPLETED at seq {end.get('last_seq')}, expected {plan['budget'] + 2}")
        findings += gate_findings(log, plan, prediction)
        rp = adj.replay(log, plan, manifest)
        findings += [f"replay: {x}" for x in rp["findings"]]
        if rp["probes_replayed"] != plan["budget"]:
            findings.append(f"replay: {rp['probes_replayed']} probes replayed, expected {plan['budget']}")
        findings += adj.prediction_findings(log, plan, prediction, rp)
        truth = bm.truth_mapping()
        whole = json.loads(rp["map"])
        snaps = bv.snapshots(rp["records"], truth)
        prov = snaps.get("provisional")
        if prov is None or prov["recall"] != 1.0 or prov["precision"] != 1.0:
            findings.append(f"provisional: the map after the code probes is not complete ({prov})")
        rr = p3.get("rate_report")
        if rr and rr.get("session_span_s", 0) > plan["session_timeout_s"]:
            findings.append(f"deadline: span {rr['session_span_s']:.0f} s exceeds {plan['session_timeout_s']:.0f} s")
        out["replay"] = {"probes_replayed": rp["probes_replayed"], "content_sha256": rp["content_sha256"], "findings": rp["findings"]}
        out["provisional"] = prov
        out["gate_observations"] = {str(int(r["seq"])): {"tables_match": (int(r["evidence"]["arm"]["status_after"], 16) >> ST_TABLES_MATCH) & 1,
                                                          "configuration_valid_hw": (int(r["evidence"]["arm"]["status_after"], 16) >> ST_CFG_VALID) & 1,
                                                          "readout_all_zero": not any(int(x, 16) for x in r["evidence"]["score"]["functional_readout"])}
                                    for r in log["loop_records"] if r.get("outcome") == "SCORED" and "arm" in r.get("evidence", {})}
        out["findings"] = findings
        out["outcome"] = "PASS" if not findings else "HOLD: " + "; ".join(findings[:6])
    except Refusal as exc:
        out["outcome"] = f"REFUSED: {exc}"
        out["refusal"] = str(exc)
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=adj.MANIFEST)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-git", action="store_true")
    a = ap.parse_args(argv)
    manifest = json.loads(a.manifest.read_text())
    q = manifest.get("qualification_plan") or {}
    plan_path, pred_path = REPO_ROOT / q.get("path", "MISSING"), REPO_ROOT / q.get("prediction_path", "MISSING")
    plan = json.loads(plan_path.read_text()) if plan_path.is_file() else {}
    pred = json.loads(pred_path.read_text()) if pred_path.is_file() else {}
    res = adjudicate(a.evidence, manifest, plan, pred, adj.sha256_of(a.manifest), require_git=not a.no_git)
    if a.out:
        a.out.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    print(res["outcome"])
    return 0 if res["outcome"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Claim B round 1′ — adjudication of one session's evidence directory (pure; re-runnable;
nothing here touches a board).

    claimb_r1p_adjudicate.py --evidence <dir> [--manifest …] [--plan …] [--prediction …]

Reads `run_log.json`, `audits.json`, `timeline.json` AS WRITTEN TO DISK (the instrument's
D-t2 discipline: the bytes adjudicated are the bytes hashed) and answers, in this order:

  1. binding — the run log's `l6.binding` names THIS round: session "B", the plan's master
     seed, `abba`, the pinned image, the round's frozen preregistration hash; the plan and
     the prediction hash to the manifest's pins. A log bound to anything else — an L6
     session, another seed — is REFUSED before any number is computed. That is the rule
     that makes S #3's 12 568 candidates un-adjudicable as Claim B data.
  2. the instrument's own validators, unchanged: `validate_standalone_run_log` with the audit
     gate, the sampled audit policy over the plan's seqs, the arm schedule against the
     operators' host twin (every genome), the L6 identity, the structural / baseline / REC
     and rel-v4 closure and control findings, the rate report from the three files.
  3. completion — `COMPLETED / budget` with last_seq = N + 2; anything else is a HOLD.
  4. the window — the measured span (first SIGNREQ → last REC) ≤ the plan's window, and
     every SCORED record's settle polls inside the calibration bound; heartbeat gaps; the
     CRC and bad-frame budgets (the soak's rules, minus the wall-time FLOOR, which the
     window replaces with a CEILING).
  5. the known answer — for every SCORED record, `scores` == the preregistered prediction
     for that seq (P3's predictor over the twin's genome). A mismatch is a HOLD naming the
     seqs (an instrument/oracle question), never silently a Claim B number.
  6. the preregistered metrics over the measured scores (the same `metrics()` the prediction
     used), compared with the prediction; the Claim B reading follows the primary's rule.

Outcome: `PASS` (a valid run; `claimb_result` says what the primary decided and whether it
equals the prediction), `HOLD …` (a finding), `KILL …` (a validator falsification), or
`REFUSED …` (binding). A HOLD or KILL is never argued into a PASS here or anywhere.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import claimb_r1p_instrument as inst  # noqa: E402
import claimb_r1p_model as mdl  # noqa: E402

TOOL_VERSION = "claimb_r1p_adjudicate.py/0.1.0"
SESSION = "B"


class Refusal(Exception):
    pass


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_pins(manifest: dict, plan_path: Path, prediction_path: Path) -> None:
    for key, path in (("plan", plan_path), ("model_prediction", prediction_path)):
        want = manifest[key]["sha256"]
        if not want:
            raise Refusal(f"the manifest pins no {key} sha256")
        if sha256_of(path) != want:
            raise Refusal(f"{path} does not hash to the manifest's {key} pin")


def check_binding(log: dict, manifest: dict, plan: dict) -> dict:
    b = (log.get("l6") or {}).get("binding")
    if not isinstance(b, dict):
        raise Refusal("the run log carries no binding (l6.binding): not a round 1′ log")
    want = {"session": SESSION, "schedule_mode": plan["mode"], "master_seed": plan["master_seed"],
            "image_sha256": manifest["instrument"]["image_sha256"], "protocol": manifest["protocol"]["wire"],
            "prereg_sha256": manifest["prereg"]["sha256"]}
    if not want["prereg_sha256"]:
        raise Refusal("the round's preregistration is not frozen (manifest prereg.sha256 is null): nothing can be adjudicated")
    for k, v in want.items():
        if b.get(k) != v:
            raise Refusal(f"binding {k}: the log says {b.get(k)!r}, this round needs {v!r}")
    return b


def completion_findings(log: dict, n: int) -> list[str]:
    end = log["session_summary"]["epoch_end"]
    out = []
    if end.get("kind") != "COMPLETED":
        out.append(f"epoch ended {end.get('kind')} ({end.get('reason')}) at seq {end.get('last_seq')}: not COMPLETED")
    elif int(end.get("last_seq") or 0) != n + 2:
        out.append(f"COMPLETED at seq {end.get('last_seq')}, expected N + 2 = {n + 2}")
    return out


def window_findings(rep: dict, plan: dict) -> list[str]:
    span = rep.get("session_span_s")
    if not isinstance(span, (int, float)):
        return ["no session span in the rate report"]
    w = float(plan["window_s"])
    return [f"span {span:.1f} s exceeds the window {w:.1f} s"] if span > w else []


def known_answer_findings(log: dict, pred: dict, sched_by_seq: dict[int, dict]) -> dict:
    by_seq = {int(c["seq"]): c for c in pred["candidates"]}
    base = pred["base_scores"]["train"]
    mism, checked = [], 0
    for r in log["loop_records"]:
        if r.get("outcome") != "SCORED":
            continue
        seq = int(r["seq"])
        got = r["evidence"]["score"]["scores"]
        if seq in by_seq:
            want = by_seq[seq]["scores_train"]
        elif seq not in sched_by_seq:            # a baseline bracket
            want = base
        else:
            mism.append(f"seq {seq}: no prediction"); continue
        checked += 1
        if [int(x) for x in got] != [int(x) for x in want]:
            mism.append(f"seq {seq}: scores {got} != predicted {want}")
    return {"checked": checked, "mismatches": mism}


def measured_rows(log: dict, pred: dict, sched_by_seq: dict[int, dict]) -> list[dict]:
    base_sum = pred["base_scores"]["train_sum"]
    rows = []
    for r in log["loop_records"]:
        seq = int(r["seq"])
        if r.get("outcome") != "SCORED" or seq not in sched_by_seq:
            continue
        s = sched_by_seq[seq]
        rows.append({"seq": seq, "pair": s["pair"], "arm": r["arm"], "d_train": sum(int(x) for x in r["evidence"]["score"]["scores"]) - base_sum})
    return rows


def compare_metrics(measured: dict, predicted: dict) -> dict:
    p_m, p_p = measured["primary"], predicted["primary"]
    s_m, s_p = measured["secondary"], predicted["secondary"]
    return {"primary_blocks_equal": [b["difference"] for b in p_m["blocks"]] == [b["difference"] for b in p_p["blocks"]],
            "primary_decision_equal": p_m["map_guided_better"] == p_p["map_guided_better"],
            "secondary_mean_equal": abs(s_m["mean_paired_difference"] - s_p["mean_paired_difference"]) < 1e-12,
            "secondary_signs_equal": (s_m["positive"], s_m["negative"], s_m["ties"]) == (s_p["positive"], s_p["negative"], s_p["ties"])}


def adjudicate(evidence: Path, manifest: dict, plan: dict, pred: dict, instrument_root: Path | None = None,
               require_git: bool = True, p3_layer=None) -> dict:
    """The whole adjudication. `p3_layer` (tests only) replaces the instrument's validator
    layer with a callable returning its dict; production always uses the instrument."""
    out = {"tool": TOOL_VERSION, "evidence": str(evidence), "outcome": None, "findings": [], "refusal": None}
    try:
        log = json.loads((evidence / "run_log.json").read_text())
        out["binding"] = check_binding(log, manifest, plan)
        sched_by_seq = {int(r["seq"]): r for r in _schedule(plan, instrument_root, require_git)}
        if p3_layer is None:
            p3 = _p3_layer(evidence, log, manifest, plan, sched_by_seq, instrument_root, require_git)
        else:
            p3 = p3_layer(evidence, log, plan, sched_by_seq)
        out["p3"] = {k: v for k, v in p3.items() if k not in ("findings", "rate_report")}
        findings = list(p3["findings"])
        rep = p3.get("rate_report") or {}
        if p3.get("rejected"):
            out["outcome"] = p3["rejected"]
            out["findings"] = findings
            return out
        findings += completion_findings(log, plan["n"])
        findings += window_findings(rep, plan) if rep else ["no rate report"]
        ka = known_answer_findings(log, pred, sched_by_seq)
        out["known_answer"] = {"checked": ka["checked"], "mismatches": len(ka["mismatches"]), "first": ka["mismatches"][:10]}
        if ka["mismatches"]:
            findings.append(f"known answer: {len(ka['mismatches'])} SCORED record(s) differ from the preregistered prediction "
                            f"(first: {ka['mismatches'][0]})")
        rows = measured_rows(log, pred, sched_by_seq)
        out["measured_candidates"] = len(rows)
        if not findings:
            m = mdl.metrics(rows, plan["blocks"]["block_pairs"], plan["blocks"]["blocks"], key="d_train")
            out["metrics_train"] = m
            out["prediction_comparison"] = compare_metrics(m, pred["metrics_train"])
            out["claimb_result"] = {
                "primary_map_guided_better": m["primary"]["map_guided_better"],
                "positive_blocks": m["primary"]["positive"], "ties": m["primary"]["ties"],
                "reading": ("POSITIVE: the preregistered primary supports map-guided > random-safe"
                            if m["primary"]["map_guided_better"] else
                            "NEGATIVE (falsifier 1): map-guided does not beat random-safe on the preregistered primary"),
                "equals_prediction": all(out["prediction_comparison"].values())}
        out["findings"] = findings
        out["outcome"] = "PASS" if not findings else "HOLD: " + "; ".join(findings[:6])
    except Refusal as exc:
        out["outcome"] = f"REFUSED: {exc}"
        out["refusal"] = str(exc)
    return out


def _schedule(plan: dict, root: Path | None, require_git: bool) -> list[dict]:
    inst.bind(root or inst.DEFAULT_ROOT, require_git=require_git)
    import l6_schedule as ls  # noqa: E402
    sched = ls.schedule(plan["master_seed"], plan["n"], plan["mode"])
    if hashlib.sha256(json.dumps(sched, sort_keys=True).encode()).hexdigest() != plan["schedule_sha256"]:
        raise Refusal("the regenerated schedule does not hash to the plan's schedule_sha256")
    return sched


def _p3_layer(evidence: Path, log: dict, manifest: dict, plan: dict, sched_by_seq: dict, root: Path | None,
              require_git: bool) -> dict:
    """The instrument's validators over the evidence, verbatim from what the L6 runner runs
    after a session (zynq-psoracle/host/l6_runner.py, adjudication block)."""
    inst.bind(root or inst.DEFAULT_ROOT, require_git=require_git)
    import l6_checks as lc  # noqa: E402
    import l6_operators as lo  # noqa: E402
    import l6_rate as lr  # noqa: E402
    import l6_schedule as ls  # noqa: E402
    import l5_runner as l5  # noqa: E402
    import p3_gate as g  # noqa: E402
    import p3_genome as gn  # noqa: E402
    from validators import records  # noqa: E402
    root = root or inst.DEFAULT_ROOT
    l6m = json.loads((root / "manifests/l6_manifest.json").read_text())
    phen = g.load_manifest()
    data = lo.operator_data(phen, lo.load_local_map())
    if lo.operator_data_sha256(data) != manifest["instrument"]["operator_data_sha256"]:
        raise Refusal("the operator data regenerated from local_map.json is not the pinned derivation")
    audits = json.loads((evidence / "audits.json").read_text())
    frames = json.loads((evidence / "timeline.json").read_text()).get("frames") or []
    chunks = audits.get("chunks") or []
    nonce_seed = int(l6m["instrument"]["carrier"]["nonce_seed"], 16)
    blank_commit = g.gate(g.build_streams(gn.frames_from_genome(gn.blank_genome(phen), phen), phen), phen)["candidate_sha256"]
    expected = {seq: gn.to_hex(lo.OPERATORS[row["arm"]](row["seed"], data)) for seq, row in sched_by_seq.items()}
    audit_seqs = set(plan["audit_seqs"])
    out: dict = {"findings": [], "rejected": None}
    try:
        v = records.validate_standalone_run_log(log, blank_commit, nonce_seed, chunks, phen)
        out["run_log_validation"] = {k: v[k] for k in ("scored", "audited", "chain_length")}
        out["audit_policy"] = records.check_audit_policy(log, v["marks"], plan["audit_policy"], audit_seqs)
        out["arm_check"] = records.check_arm_schedule(log, list(sched_by_seq.values()), plan["n"], expected)
        out["l6_identity"] = records.check_l6_identity(
            log["app_identity"] or {}, plan["master_seed"], plan["mode"], manifest["instrument"]["operator_data_sha256"],
            protocol=plan["protocol"], rec_retry_control=bool(plan["flags"] & ls.FLAG_REC_CONTROL),
            sign_retry_control=bool(plan["flags"] & ls.FLAG_SIGN_CONTROL))
        f = out["findings"]
        f += lc.structural_findings(log, chunks, audit_seqs, frames, protocol=plan["protocol"], hb_rule="v07")
        f += lc.baseline_findings(log)
        rec_ledgers = audits.get("recs") or []
        f += lc.rec_closure_findings(log, rec_ledgers)
        f += lc.rec_control_findings(rec_ledgers, bool(plan["flags"] & ls.FLAG_REC_CONTROL))
        # the rel-v4 ledgers live beside the pulls in audits.json under `ident`, `signs`, `term`
        f += lc.rel_closure_findings(log, audits, audits.get("pulls") or [])
        f += lc.rel_control_findings(audits.get("signs") or [], bool(plan["flags"] & ls.FLAG_SIGN_CONTROL))
        try:
            rep = lr.rate_report_from_evidence_dir(evidence, None)
            out["rate_report"] = rep
            out["rate"] = {k: rep.get(k) for k in ("candidates", "evals_per_hour", "cov", "session_span_s")}
            timeline = json.loads((evidence / "timeline.json").read_text())
            f += _soak_rules(lc, log, frames, timeline, plan, l6m, rep)
        except lr.RateError as exc:
            f.append(f"no rate report: {exc}")
        base = l5.outcome_for(log["session_summary"]["epoch_end"])
        if base != "PASS":
            f.append(f"epoch outcome {base}")
    except records.RecordError as exc:
        out["rejected"] = l5.classify_rejection(exc)
        out["run_log_validation"] = f"REJECTED: {exc}"
    return out


def _soak_rules(lc, log, frames, timeline, plan, l6m, rep) -> list[str]:
    """The soak's rules S #3 passed under, with the wall-time FLOOR removed (the window is a
    ceiling, checked separately): heartbeat gaps, CRC and bad-frame budgets, settle bound."""
    pc = l6m["pass_conditions"]
    crc = int(timeline.get("crc_dropped") or 0) if isinstance(timeline.get("crc_dropped"), int) else \
        sum(1 for fr in frames if fr.get("event") == "CRC_DROP")
    bad = int(timeline.get("bad_frames") or 0) if isinstance(timeline.get("bad_frames"), int) else \
        sum(1 for fr in frames if fr.get("event") == "BAD_FRAME")
    med = plan.get("settle_polls_median_calibration") or 16.0
    return lc.soak_findings(log, frames, crc, plan["crc_budget"], rep["session_span_s"], duration_s=0.0,
                            hb_gap_max_s=pc["hb_gap_max_s"], settle_median_calib=med,
                            settle_bound_factor=pc["settle_bound_factor"], wall_fraction_min=0.0,
                            bad_frames=bad, bad_frame_budget=plan["bad_frame_budget"])


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=inst.MANIFEST)
    ap.add_argument("--plan", type=Path, default=REPO_ROOT / "evidence/claimb_round1prime/plan.json")
    ap.add_argument("--prediction", type=Path, default=REPO_ROOT / "evidence/claimb_round1prime/model_prediction.json")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-git", action="store_true")
    a = ap.parse_args(argv)
    manifest = json.loads(a.manifest.read_text())
    try:
        check_pins(manifest, a.plan, a.prediction)
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    plan = json.loads(a.plan.read_text())
    pred = json.loads(a.prediction.read_text())
    res = adjudicate(a.evidence, manifest, plan, pred, require_git=not a.no_git)
    if a.out:
        a.out.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    print(res["outcome"])
    if res.get("claimb_result"):
        print(json.dumps(res["claimb_result"], indent=1))
    return 0 if res["outcome"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

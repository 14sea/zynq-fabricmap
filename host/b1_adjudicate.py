#!/usr/bin/env python3
"""B1 — adjudication of one session's evidence directory (pure; re-runnable; nothing here
touches a board).

    b1_adjudicate.py --evidence <dir> [--manifest …] [--plan …] [--prediction …]

Reads `run_log.json`, `audits.json`, `timeline.json` as written to disk and answers, in order:

  1. binding — the run log's `l6.binding` names THIS stage: session "B1", the plan's seed,
     the B1 image, B1's frozen preregistration; the plan and prediction hash to the
     manifest's pins; the IDENT is app_identity 1.4.0 with carto-v1, the universe digest
     and the plan's budget.
  2. the instrument's validators, unchanged (validate_standalone_run_log with the audit
     gate; the ALL-SELF-REPORTING audit policy; structural / baseline / REC and rel-v4
     closure and control findings; the rate report) — through the same code path as the
     round 1′ adjudicator.
  3. completion — COMPLETED at seq budget + 2.
  4. the autonomy replay — the host runs the reference cartographer over the readouts the
     records carry (in seq order) and requires (a) every proposal it makes to equal the
     genome the board actually probed at that seq (the board chose what the algorithm
     chooses from the same observations: no host, no other input), (b) every record's
     `carto.map_sha256` to equal the reconstruction's hash after that observation (the
     board's running commitment), (c) the closing record's hash = the reconstruction's
     final map = the board's map.
  5. the verifier — the reconstructed map (which IS the board's map, by 4b/4c) scored
     against the truth held back from the executable: precision, recall, polarity,
     calibration, sample efficiency, the holdout LUTs apart, interaction edges, anomalies.
  6. the prediction — on a correct instrument the board's probes, blocks and map bytes
     equal the preregistered prediction; a difference is a finding (an instrument or
     fabric question, or a cartographer defect), reported, never adjusted.

Outcome: PASS (a valid run; `b1_result` carries the metrics), HOLD (a finding), KILL (a
validator falsification), REFUSED (binding). The host's recomputation is an audit: it
feeds nothing back into any board decision or map.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b1_verify as bv  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

TOOL_VERSION = "b1_adjudicate.py/0.1.0"
SESSION = "B1"
MANIFEST = REPO_ROOT / "manifests/b1_manifest.json"


class Refusal(Exception):
    pass


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_pins(manifest: dict, plan_path: Path, prediction_path: Path) -> None:
    for key, path in (("plan", plan_path), ("prediction", prediction_path)):
        want = manifest[key]["sha256"]
        if not want:
            raise Refusal(f"the manifest pins no {key} sha256")
        if sha256_of(path) != want:
            raise Refusal(f"{path} does not hash to the manifest's {key} pin")


def check_binding(log: dict, manifest: dict, plan: dict) -> dict:
    b = (log.get("l6") or {}).get("binding")
    if not isinstance(b, dict):
        raise Refusal("the run log carries no binding (l6.binding): not a B1 log")
    want = {"session": SESSION, "master_seed": plan["master_seed"], "image_sha256": manifest["image"]["sha256"],
            "protocol": manifest["protocol"]["wire"], "prereg_sha256": manifest["prereg"]["sha256"]}
    if not want["prereg_sha256"]:
        raise Refusal("B1's preregistration is not frozen (manifest prereg.sha256 is null): nothing can be adjudicated")
    for k, v in want.items():
        if b.get(k) != v:
            raise Refusal(f"binding {k}: the log says {b.get(k)!r}, this stage needs {v!r}")
    ident = log.get("app_identity") or {}
    for k, v in (("carto_version", manifest["cartographer"]["version"]), ("universe_sha256", manifest["universe"]["sha256"]),
                 ("probe_budget", plan["budget"]), ("master_seed", plan["master_seed"]), ("protocol", manifest["protocol"]["wire"])):
        if ident.get(k) != v:
            raise Refusal(f"IDENT {k}: the board says {ident.get(k)!r}, the plan needs {v!r}")
    return b


def completion_findings(log: dict, budget: int) -> list[str]:
    end = log["session_summary"]["epoch_end"]
    if end.get("kind") != "COMPLETED":
        return [f"epoch ended {end.get('kind')} ({end.get('reason')}) at seq {end.get('last_seq')}: not COMPLETED"]
    if int(end.get("last_seq") or 0) != budget + 2:
        return [f"COMPLETED at seq {end.get('last_seq')}, expected budget + 2 = {budget + 2}"]
    return []


def replay(log: dict, plan: dict) -> dict:
    """The autonomy replay: the reference over the records' readouts must reproduce the
    board's probes and its running map hashes."""
    recs = sorted((r for r in log["loop_records"]), key=lambda r: int(r["seq"]))
    budget = plan["budget"]
    c = bc.Carto(plan["master_seed"], budget)
    findings, per_seq = [], []
    baseline_seqs = {1, budget + 2}
    for r in recs:
        seq = int(r["seq"])
        if r.get("outcome") != "SCORED":
            findings.append(f"seq {seq}: outcome {r.get('outcome')} — the replay stops at the first non-SCORED record")
            break
        tables = [int(x, 16) for x in r["evidence"]["score"]["functional_readout"]]
        carto = r.get("carto")
        if seq in baseline_seqs:
            if carto is None:
                findings.append(f"seq {seq}: baseline record without a carto block")
            else:
                # a baseline carries the current commitment and no observation
                c.render()
                if carto.get("map_sha256") != c.map_sha256:
                    findings.append(f"seq {seq}: baseline commitment {str(carto.get('map_sha256'))[:12]} != reconstruction {c.map_sha256[:12]}")
                if carto.get("phase") != "baseline":
                    findings.append(f"seq {seq}: baseline record phase {carto.get('phase')!r}")
            if seq == 1 and any(tables):
                findings.append("seq 1: the opening baseline's readout is not all-zero")
            continue
        nxt = c.next()
        if nxt is None:
            findings.append(f"seq {seq}: the board probed after the reference was done")
            break
        genome, kind = nxt
        if bc.genome_to_hex(genome) != r.get("genome"):
            findings.append(f"seq {seq}: the board's genome differs from the reference's proposal (autonomy replay failed)")
            break
        c.observe(seq, tables)
        block = c.record_json(kind, seq, c.changed[:8])
        if carto is None:
            findings.append(f"seq {seq}: no carto block on a probe record")
            break
        if carto.get("map_sha256") != c.map_sha256:
            findings.append(f"seq {seq}: the board's commitment {str(carto.get('map_sha256'))[:12]} != reconstruction {c.map_sha256[:12]}")
            break
        want = json.loads(block)
        for k in ("phase", "probes_issued", "anomalies", "changed"):
            if carto.get(k) != want[k]:
                findings.append(f"seq {seq}: carto.{k} differs from the reconstruction ({carto.get(k)!r} != {want[k]!r})")
                break
        per_seq.append({"seq": seq, "kind": kind, "changed_full": [c.e[i].render(i) for i in c.changed],
                        "carto": block})
        if findings:
            break
    text = c.render()
    return {"findings": findings, "map": text, "map_sha256": c.map_sha256, "carto": c,
            "records": [{"seq": p["seq"], "carto": p["carto"], "changed_full": p["changed_full"]} for p in per_seq],
            "probes_replayed": len(per_seq)}


def adjudicate(evidence: Path, manifest: dict, plan: dict, prediction: dict, instrument_root: Path | None = None,
               require_git: bool = True, p3_layer=None) -> dict:
    out = {"tool": TOOL_VERSION, "evidence": str(evidence), "outcome": None, "findings": [], "refusal": None}
    try:
        log = json.loads((evidence / "run_log.json").read_text())
        out["binding"] = check_binding(log, manifest, plan)
        p3 = _p3_layer(evidence, log, manifest, plan, instrument_root, require_git) if p3_layer is None \
            else p3_layer(evidence, log, plan)
        out["p3"] = {k: v for k, v in p3.items() if k not in ("findings", "rate_report")}
        findings = list(p3["findings"])
        if p3.get("rejected"):
            out["outcome"] = p3["rejected"]
            out["findings"] = findings
            return out
        findings += completion_findings(log, plan["budget"])
        rp = replay(log, plan)
        out["replay"] = {"probes_replayed": rp["probes_replayed"], "map_sha256": rp["map_sha256"], "findings": rp["findings"]}
        findings += rp["findings"]
        truth = bm.truth_mapping()
        compact = json.loads(rp["map"])
        score = bv.score(compact, truth, records=rp["records"])
        out["b1_result"] = {k: score[k] for k in ("precision", "recall", "claimed", "correct", "total_mapped", "polarity_errors",
                                                  "states", "anomalies", "calibration", "holdout", "train", "interaction",
                                                  "sample_efficiency")}
        out["self_map_v2"] = bv.expand(compact, truth)
        out["prediction_comparison"] = {
            "map_equal": rp["map_sha256"] == prediction["map_sha256"],
            "probe_sequence_equal": hashlib.sha256("\n".join(
                r["genome"] for r in sorted(log["loop_records"], key=lambda r: int(r["seq"]))
                if int(r["seq"]) not in (1, plan["budget"] + 2)).encode()).hexdigest() == prediction["probe_sequence_sha256"],
            "anomalies_predicted": prediction["expected_score"]["anomalies"], "anomalies_measured": score["anomalies"]}
        if not out["prediction_comparison"]["map_equal"]:
            findings.append("the board's map differs from the preregistered prediction (an instrument/fabric question or a cartographer defect — reported, not adjusted)")
        if score["anomalies"]:
            findings.append(f"{score['anomalies']} anomalies recorded by the cartographer")
        out["findings"] = findings
        out["outcome"] = "PASS" if not findings else "HOLD: " + "; ".join(findings[:6])
    except Refusal as exc:
        out["outcome"] = f"REFUSED: {exc}"
        out["refusal"] = str(exc)
    return out


def _p3_layer(evidence: Path, log: dict, manifest: dict, plan: dict, root: Path | None, require_git: bool) -> dict:
    """The instrument's validators over the evidence — the same block the round 1′
    adjudicator runs, with B1's audit policy (every seq) and no arm schedule."""
    inst.bind(root or inst.DEFAULT_ROOT, require_git=require_git)
    import l6_checks as lc  # noqa: E402
    import l6_rate as lr  # noqa: E402
    import l6_schedule as ls  # noqa: E402
    import l5_runner as l5  # noqa: E402
    import p3_gate as g  # noqa: E402
    import p3_genome as gn  # noqa: E402
    from validators import records  # noqa: E402
    root = root or inst.DEFAULT_ROOT
    l6m = json.loads((root / "manifests/l6_manifest.json").read_text())
    phen = g.load_manifest()
    audits = json.loads((evidence / "audits.json").read_text())
    timeline = json.loads((evidence / "timeline.json").read_text())
    frames = timeline.get("frames") or []
    chunks = audits.get("chunks") or []
    nonce_seed = int(l6m["instrument"]["carrier"]["nonce_seed"], 16)
    blank_commit = g.gate(g.build_streams(gn.frames_from_genome(gn.blank_genome(phen), phen), phen), phen)["candidate_sha256"]
    audit_seqs = set(plan["audit_seqs"])
    out: dict = {"findings": [], "rejected": None}
    try:
        v = records.validate_standalone_run_log(log, blank_commit, nonce_seed, chunks, phen)
        out["run_log_validation"] = {k: v[k] for k in ("scored", "audited", "chain_length")}
        out["audit_policy"] = records.check_audit_policy(log, v["marks"], "all-self-reporting", None)
        f = out["findings"]
        f += lc.structural_findings(log, chunks, audit_seqs, frames, protocol=plan["protocol"], hb_rule="v07")
        f += lc.baseline_findings(log)
        rec_ledgers = audits.get("recs") or []
        f += lc.rec_closure_findings(log, rec_ledgers)
        f += lc.rec_control_findings(rec_ledgers, bool(plan["flags"] & ls.FLAG_REC_CONTROL))
        f += lc.rel_closure_findings(log, audits, audits.get("pulls") or [])
        f += lc.rel_control_findings(audits.get("signs") or [], bool(plan["flags"] & ls.FLAG_SIGN_CONTROL))
        try:
            rep = lr.rate_report_from_evidence_dir(evidence, None)
            out["rate_report"] = rep
            out["rate"] = {k: rep.get(k) for k in ("candidates", "evals_per_hour", "cov", "session_span_s")}
            pc = l6m["pass_conditions"]
            crc = int(timeline.get("crc_dropped") or 0)
            bad = int(timeline.get("bad_frames") or 0)
            f += lc.soak_findings(log, frames, crc, plan["crc_budget"], rep["session_span_s"], duration_s=0.0,
                                  hb_gap_max_s=pc["hb_gap_max_s"], settle_median_calib=16.0,
                                  settle_bound_factor=pc["settle_bound_factor"], wall_fraction_min=0.0,
                                  bad_frames=bad, bad_frame_budget=plan["bad_frame_budget"])
            if rep["session_span_s"] > plan["session_timeout_s"]:
                f.append(f"span {rep['session_span_s']:.0f} s exceeds the plan's deadline {plan['session_timeout_s']:.0f} s")
        except lr.RateError as exc:
            f.append(f"no rate report: {exc}")
        base = l5.outcome_for(log["session_summary"]["epoch_end"])
        if base != "PASS":
            f.append(f"epoch outcome {base}")
    except records.RecordError as exc:
        out["rejected"] = l5.classify_rejection(exc)
        out["run_log_validation"] = f"REJECTED: {exc}"
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--plan", type=Path, default=REPO_ROOT / "evidence/b1/plan.json")
    ap.add_argument("--prediction", type=Path, default=REPO_ROOT / "evidence/b1/prediction.json")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-git", action="store_true")
    a = ap.parse_args(argv)
    manifest = json.loads(a.manifest.read_text())
    try:
        check_pins(manifest, a.plan, a.prediction)
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    res = adjudicate(a.evidence, manifest, json.loads(a.plan.read_text()), json.loads(a.prediction.read_text()),
                     require_git=not a.no_git)
    if a.out:
        a.out.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    print(res["outcome"])
    if res.get("b1_result"):
        r = res["b1_result"]
        print(json.dumps({k: r[k] for k in ("precision", "recall", "anomalies", "holdout", "sample_efficiency")}, indent=1))
    return 0 if res["outcome"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

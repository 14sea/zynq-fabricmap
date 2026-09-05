#!/usr/bin/env python3
"""B1 — adjudication of one session's evidence directory (pure; re-runnable; nothing here
touches a board).

    b1_adjudicate.py --evidence <dir> [--manifest …] [--plan …] [--prediction …] [--out …]

Every acceptance condition of the preregistration (§4) is ONE named check in `b1_findings`,
and every check has a negative test (tests/test_b1_adjudicate.py). In order:

  binding      the plan and prediction hash to the manifest's pins; the pin table of every
               adjudication-critical file verifies; the log's `l6.binding` names session
               "B1", the plan's seed, the B1 image, the frozen prereg, THIS manifest's sha256
               and the instrument's archive commit; the IDENT is app_identity 1.4.0 with the
               B1 carrier variant, carto-v1, the universe digest and the plan's budget.
  instrument   the B1 records validator (host/b1_records.py — the instrument's, one rule
               changed: the host attested nothing) with the audit gate; the ALL-SELF-REPORTING
               policy; structural / baseline / REC / rel-v4 closure and control findings; the
               rate report; heartbeat and CRC / bad-frame budgets; the deadline.
  completion   COMPLETED at seq budget + 2.
  replay       the reference orchestrator, bound to the session (token, universe, image),
               fed the records' readouts in seq order: every proposal = the board's genome
               (autonomy), every record's `carto` block = the reconstruction's block field
               for field (commitment: content_sha256, map_sha256, phase, probes, anomalies,
               changed sample), the closing record's hashes = the final map's.
  prediction   the probe sequence and every record's content-level block and the final
               content_sha256 equal the preregistered prediction (the binding differs by
               token; the content must not).
  verifier     the reconstructed map (= the board's) scored against the truth held back
               from the executable: precision 1.0, recall 1.0, every claim observed, 0
               anomalies, calibration, both reporting strata at 1.0, 32 pairs / 0 deviations,
               provisional snapshot at probe 9 complete, full confirmation by probe 301.

Outcome: PASS (every check holds; `b1_result` carries the metrics; `self_map_v2` the
board-authored map; `verifier_report` the truth-side judgement), HOLD (a named finding),
KILL (a validator falsification), REFUSED (binding). The host's recomputation is an audit;
it feeds nothing back to any board decision or map.
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
import b1_pins as pins_mod  # noqa: E402
import b1_verify as bv  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

TOOL_VERSION = "b1_adjudicate.py/0.2.0"
SESSION = "B1"
MANIFEST = REPO_ROOT / "manifests/b1_manifest.json"
B1_VARIANT = "0x42310001"


class Refusal(Exception):
    pass


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------ binding
def check_pins(manifest: dict, plan_path: Path, prediction_path: Path, pins_path: Path | None = None) -> None:
    for key, path in (("plan", plan_path), ("prediction", prediction_path)):
        want = manifest[key]["sha256"]
        if not want:
            raise Refusal(f"the manifest pins no {key} sha256")
        if sha256_of(path) != want:
            raise Refusal(f"{path} does not hash to the manifest's {key} pin")
    try:
        pins_mod.verify(pins_path or pins_mod.PINS, manifest)
    except pins_mod.PinRefusal as exc:
        raise Refusal(f"instrument pins: {exc}") from None


def check_binding(log: dict, manifest: dict, plan: dict, manifest_sha256: str) -> dict:
    b = (log.get("l6") or {}).get("binding")
    if not isinstance(b, dict):
        raise Refusal("the run log carries no binding (l6.binding): not a B1 log")
    want = {"session": SESSION, "master_seed": plan["master_seed"], "image_sha256": manifest["image"]["sha256"],
            "protocol": manifest["protocol"]["wire"], "prereg_sha256": manifest["prereg"]["sha256"],
            "b1_manifest_sha256": manifest_sha256, "psoracle_commit": manifest["instrument"]["psoracle_commit"]}
    if not want["prereg_sha256"]:
        raise Refusal("B1's preregistration is not frozen (manifest prereg.sha256 is null): nothing can be adjudicated")
    if not (manifest.get("carrier") or {}).get("qualified"):
        raise Refusal("the B1 carrier is not marked qualified (docs/b1_carrier_qualification.md): a mapping session on an "
                      "unqualified carrier is not adjudicable")
    for k, v in want.items():
        if b.get(k) != v:
            raise Refusal(f"binding {k}: the log says {b.get(k)!r}, this stage needs {v!r}")
    ident = log.get("app_identity") or {}
    for k, v in (("carto_version", manifest["cartographer"]["version"]), ("universe_sha256", manifest["universe"]["sha256"]),
                 ("probe_budget", plan["budget"]), ("master_seed", plan["master_seed"]), ("protocol", manifest["protocol"]["wire"]),
                 ("carrier_variant", B1_VARIANT), ("carrier_sha256", manifest["carrier"]["bitstream_sha256"])):
        if ident.get(k) != v:
            raise Refusal(f"IDENT {k}: the board says {ident.get(k)!r}, this stage needs {v!r}")
    return b


SCHEMA_PATH = REPO_ROOT / "schemas/self_map_v2.schema.json"


def schema_findings(doc: dict, schema_path: Path = SCHEMA_PATH) -> list[str]:
    """The expanded board-authored map validated against schemas/self_map_v2.schema.json
    with a real JSON-schema validator (draft 2020-12). No validator installed is itself a
    finding — never a silent pass."""
    try:
        import jsonschema
    except ImportError:
        return ["self_map_v2: no JSON-schema validator available (python3-jsonschema): the map is unvalidated"]
    schema = json.loads(schema_path.read_text())
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    errs = sorted(cls(schema).iter_errors(doc), key=lambda e: list(e.absolute_path))
    return [f"self_map_v2 schema: {'/'.join(str(x) for x in e.absolute_path) or '<root>'}: {e.message[:160]}" for e in errs[:8]]


# ------------------------------------------------------------------ the replay
def replay(log: dict, plan: dict, manifest: dict) -> dict:
    """The autonomy replay: the reference session, bound as the board was, over the records'
    readouts; the board's probes and blocks must equal it."""
    recs = sorted(log["loop_records"], key=lambda r: int(r["seq"]))
    budget = plan["budget"]
    token = (log.get("app_identity") or {}).get("token") or ""
    image_lo32 = int(manifest["image"]["sha256"][-8:], 16)
    c = bc.Carto(plan["master_seed"], budget)
    c.bind(token, manifest["universe"]["sha256"], image_lo32)
    findings, per_seq = [], []
    baseline_seqs = {1, budget + 2}

    def block_findings(seq, got, want, phase):
        out = []
        if got is None:
            return [f"seq {seq}: no carto block"]
        w = json.loads(want)
        for k in ("content_sha256", "map_sha256", "phase", "probes_issued", "anomalies", "changed", "version"):
            if got.get(k) != w[k]:
                out.append(f"seq {seq} ({phase}): carto.{k} differs from the reconstruction ({str(got.get(k))[:24]!r} != {str(w[k])[:24]!r})")
                break
        return out
    for r in recs:
        seq = int(r["seq"])
        if r.get("outcome") != "SCORED":
            findings.append(f"seq {seq}: outcome {r.get('outcome')} — the replay stops at the first non-SCORED record")
            break
        tables = [int(x, 16) for x in r["evidence"]["score"]["functional_readout"]]
        carto = r.get("carto")
        if seq in baseline_seqs:
            if any(tables):
                findings.append(f"seq {seq}: a baseline's readout is not all-zero")
            findings += block_findings(seq, carto, c.record_json(bc.PH_DONE, seq, []), "baseline")
            if findings:
                break
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
        per_seq.append({"seq": seq, "kind": kind, "carto": block, "changed_full": [c.e[i].render(i) for i in c.changed]})
        findings += block_findings(seq, carto, block, bc.PHASE_NAME[kind])
        if findings:
            break
    text = c.render()
    return {"findings": findings, "map": text, "map_sha256": c.map_sha256, "content_sha256": c.content_sha256, "carto": c,
            "records": per_seq, "probes_replayed": len(per_seq)}


# ------------------------------------------------------------------ the findings, one per condition
def b1_findings(log: dict, plan: dict, prediction: dict, rp: dict, score: dict, snaps: dict, rate_report: dict | None) -> list[str]:
    f: list[str] = []
    end = log["session_summary"]["epoch_end"]
    if end.get("kind") != "COMPLETED":
        f.append(f"completion: epoch ended {end.get('kind')} ({end.get('reason')}) at seq {end.get('last_seq')}")
    elif int(end.get("last_seq") or 0) != plan["budget"] + 2:
        f.append(f"completion: COMPLETED at seq {end.get('last_seq')}, expected budget + 2 = {plan['budget'] + 2}")
    f += [f"replay: {x}" for x in rp["findings"]]
    if rp["probes_replayed"] != plan["budget"]:
        f.append(f"replay: {rp['probes_replayed']} probes replayed, expected {plan['budget']}")
    # the prediction (content-level)
    probe_seq = hashlib.sha256("\n".join(r["genome"] for r in sorted(log["loop_records"], key=lambda r: int(r["seq"]))
                                         if int(r["seq"]) not in (1, plan["budget"] + 2)).encode()).hexdigest()
    if probe_seq != prediction["probe_sequence_sha256"]:
        f.append("prediction: the probe sequence differs from the preregistered one")
    if rp["content_sha256"] != prediction["content_sha256"]:
        f.append("prediction: the map's content differs from the preregistered prediction")
    pred_blocks = {int(x["seq"]): x["content"] for x in prediction["record_content"]}
    for r in rp["records"]:
        got = json.loads(r["carto"]); want = pred_blocks.get(r["seq"])
        if want is None or any(got[k] != want[k] for k in ("content_sha256", "phase", "probes_issued", "anomalies", "changed")):
            f.append(f"prediction: record seq {r['seq']}'s block differs from the preregistered one")
            break
    # the verifier's conditions (preregistration §4)
    if score["precision"] != 1.0:
        f.append(f"verifier: precision {score['precision']} != 1.0 ({len(score['wrong_claims'])}+ wrong claims)")
    if score["recall"] != 1.0:
        f.append(f"verifier: recall {score['recall']} != 1.0")
    if score["unobserved_claims"]:
        f.append(f"verifier: {score['unobserved_claims']} claims without an observed transition")
    if score["anomalies"]:
        f.append(f"verifier: {score['anomalies']} anomalies recorded by the cartographer")
    for c in ("1", "2"):
        acc = score["calibration"][c]["accuracy"]
        if acc is not None and acc != 1.0:
            f.append(f"verifier: calibration at confidence {c} = {acc}")
    for s in ("stratum_A", "stratum_B"):
        if score[s]["recall"] != 1.0 or score[s]["precision"] != 1.0:
            f.append(f"verifier: {s} recall/precision {score[s]['recall']}/{score[s]['precision']} != 1.0")
    if score["interaction"]["pairs_tested"] != bc.PAIRS_MAX or score["interaction"]["deviations"] != 0:
        f.append(f"verifier: interaction pairs {score['interaction']['pairs_tested']} tested, {score['interaction']['deviations']} deviations")
    if snaps["probes_to_full_recall_conf1"] != bc.CODE_BITS:
        f.append(f"verifier: full recall at confidence ≥ 1 reached at probe {snaps['probes_to_full_recall_conf1']}, expected {bc.CODE_BITS}")
    if snaps["provisional"] is None or snaps["provisional"]["recall"] != 1.0:
        f.append("verifier: the provisional snapshot after the code probes is not complete")
    if snaps["probes_to_full_confirmation"] is None:
        f.append("verifier: full confirmation never reached")
    if rate_report and rate_report.get("session_span_s", 0) > plan["session_timeout_s"]:
        f.append(f"deadline: span {rate_report['session_span_s']:.0f} s exceeds {plan['session_timeout_s']:.0f} s")
    return f


# ------------------------------------------------------------------ the instrument's layer
def _p3_layer(evidence: Path, log: dict, manifest: dict, plan: dict, root: Path | None, require_git: bool) -> dict:
    inst.bind(root or inst.DEFAULT_ROOT, require_git=require_git)
    import b1_records as records  # noqa: E402  (the B1 successor, over the bound instrument's package)
    from validators import records as _instrument_records  # noqa: E402
    import l6_checks as lc  # noqa: E402
    import l6_rate as lr  # noqa: E402
    import l6_schedule as ls  # noqa: E402
    import l5_runner as l5  # noqa: E402
    import p3_gate as g  # noqa: E402
    import p3_genome as gn  # noqa: E402
    root = root or inst.DEFAULT_ROOT
    l6m = json.loads((root / "manifests/l6_manifest.json").read_text())
    phen = g.load_manifest()
    audits = json.loads((evidence / "audits.json").read_text())
    timeline = json.loads((evidence / "timeline.json").read_text())
    frames = timeline.get("frames") or []
    chunks = audits.get("chunks") or []
    nonce_seed = int(manifest["carrier"]["nonce_seed"], 16)
    blank_commit = g.gate(g.build_streams(gn.frames_from_genome(gn.blank_genome(phen), phen), phen), phen)["candidate_sha256"]
    out: dict = {"findings": [], "rejected": None}
    try:
        v = records.validate_standalone_run_log(log, blank_commit, nonce_seed, chunks, phen)
        out["run_log_validation"] = {k: v[k] for k in ("scored", "audited", "chain_length")}
        out["audit_policy"] = records.check_audit_policy(log, v["marks"], "all-self-reporting", None)
        f = out["findings"]
        f += lc.structural_findings(log, chunks, set(plan["audit_seqs"]), frames, protocol=plan["protocol"], hb_rule="v07")
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
            f += lc.soak_findings(log, frames, int(timeline.get("crc_dropped") or 0), plan["crc_budget"], rep["session_span_s"],
                                  duration_s=0.0, hb_gap_max_s=pc["hb_gap_max_s"], settle_median_calib=16.0,
                                  settle_bound_factor=pc["settle_bound_factor"], wall_fraction_min=0.0,
                                  bad_frames=int(timeline.get("bad_frames") or 0), bad_frame_budget=plan["bad_frame_budget"])
        except lr.RateError as exc:
            f.append(f"no rate report: {exc}")
        base = l5.outcome_for(log["session_summary"]["epoch_end"])
        if base != "PASS":
            f.append(f"epoch outcome {base}")
    except _instrument_records.RecordError as exc:
        # b1_records' classes subclass the instrument's, so ONE base catches the B1 rules,
        # the instrument's audit gate (validators.audit) and its schema layer alike;
        # classify_rejection maps a Falsified of either family to KILL, the rest to HOLD
        out["rejected"] = l5.classify_rejection(exc)
        out["run_log_validation"] = f"REJECTED: {exc}"
    return out


# ------------------------------------------------------------------ the whole adjudication
def adjudicate(evidence: Path, manifest: dict, plan: dict, prediction: dict, manifest_sha256: str,
               instrument_root: Path | None = None, require_git: bool = True, p3_layer=None) -> dict:
    out = {"tool": TOOL_VERSION, "evidence": str(evidence), "outcome": None, "findings": [], "refusal": None}
    try:
        log = json.loads((evidence / "run_log.json").read_text())
        out["binding"] = check_binding(log, manifest, plan, manifest_sha256)
        p3 = _p3_layer(evidence, log, manifest, plan, instrument_root, require_git) if p3_layer is None \
            else p3_layer(evidence, log, plan)
        out["p3"] = {k: v for k, v in p3.items() if k not in ("findings", "rate_report")}
        findings = list(p3["findings"])
        if p3.get("rejected"):
            out["outcome"] = p3["rejected"]; out["findings"] = findings
            return out
        rp = replay(log, plan, manifest)
        truth = bm.truth_mapping()
        whole = json.loads(rp["map"])
        score = bv.score(whole["content"], truth)
        snaps = bv.snapshots(rp["records"], truth)
        findings += b1_findings(log, plan, prediction, rp, score, snaps, p3.get("rate_report"))
        out["replay"] = {"probes_replayed": rp["probes_replayed"], "map_sha256": rp["map_sha256"],
                         "content_sha256": rp["content_sha256"], "findings": rp["findings"]}
        out["b1_result"] = {**{k: score[k] for k in ("precision", "recall", "claimed", "correct", "total_mapped", "unobserved_claims",
                                                    "states", "anomalies", "calibration", "stratum_A", "stratum_B", "interaction")},
                            "snapshots": snaps}
        out["prediction_comparison"] = {"content_equal": rp["content_sha256"] == prediction["content_sha256"],
                                        "predicted_content_sha256": prediction["content_sha256"]}
        out["self_map_v2"] = bv.expand(whole)
        out["findings"] += schema_findings(out["self_map_v2"])
        out["verifier_report"] = bv.report(whole, rp["records"], truth)
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
                     sha256_of(a.manifest), require_git=not a.no_git)
    if a.out:
        a.out.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    print(res["outcome"])
    if res.get("b1_result"):
        r = res["b1_result"]
        print(json.dumps({k: r[k] for k in ("precision", "recall", "anomalies", "stratum_B", "snapshots")}, indent=1))
    return 0 if res["outcome"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

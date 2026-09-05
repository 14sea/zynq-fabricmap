#!/usr/bin/env python3
"""B1 — adjudication of one session's evidence directory (pure; re-runnable; nothing here
touches a board).

    b1_adjudicate.py --evidence <dir> [--manifest …] [--plan …] [--prediction …] [--out …]

Every acceptance condition of the preregistration (§4) is ONE named check in `b1_findings`,
and every check has a negative test driven through `adjudicate()` itself
(tests/test_b1_adjudicate.py). In order:

  pins         re-verified INSIDE adjudicate(), whatever the caller did earlier: the plan and
               the prediction hash to the manifest's pins and equal the objects the caller
               passed; the pin table of every adjudication-critical file verifies. A file that
               drifted between a runner's preflight and the adjudication is a REFUSED.
  binding      the log's `l6.binding` names session "B1", the plan's seed, the B1 image, the
               frozen prereg, THIS manifest's sha256 and the instrument's archive commit; the
               IDENT is app_identity 1.4.0 with the B1 carrier variant and hash, carto-v1, the
               universe digest and the plan's budget; the carrier's QUALIFICATION evidence
               (manifest carrier.qualification) re-adjudicates to PASS and binds to this
               carrier / image / prereg (host/b1_qualification.py) — a bare flag is nothing.
  instrument   the B1 records validator (host/b1_records.py — the instrument's, one rule
               changed: the host attested nothing) with the audit gate; the ALL-SELF-REPORTING
               policy; structural / baseline / REC / rel-v4 closure and control findings; the
               rate report; heartbeat and CRC / bad-frame budgets; the deadline.
  completion   COMPLETED at seq budget + 2.
  replay       the reference orchestrator, bound to the session (token, universe, image),
               fed the records' readouts in seq order: every proposal = the board's genome
               (autonomy — the probe sequence is a finding, per record), every record's
               `carto` block = the reconstruction's block field for field.
  prediction   the probe sequence, every record's content-level block and the final
               content_sha256 equal the preregistered prediction; the prediction's own
               expected score equals the preregistered constants (EXPECTED) — the gates below
               are those constants, not whatever the prediction file says.
  verifier     the reconstructed map (= the board's) scored against the truth held back
               from the executable, EXACTLY: precision 1.0, recall 1.0, 0 unobserved claims,
               0 anomalies; the probe-9 snapshot complete (precision 1.0, recall 1.0,
               confidence-1 accuracy 292/292); the final snapshot with NO confidence-1 cohort
               and confidence-2 accuracy 292/292; both strata 1.0; 32 pairs, 0 deviations,
               0 pending; full recall at confidence ≥ 1 at probe 9; full confirmation at
               probe 301.
  map          the expanded board-authored map validates under the JSON schema (a missing
               validator is a finding) and under the semantic rules (b1_verify.semantic_findings).

Outcome: PASS (every check holds; `b1_result` carries the metrics; `self_map_v2` the
board-authored map; `verifier_report` the truth-side judgement), HOLD (a named finding),
KILL (a validator falsification), REFUSED (pins / binding). The host's recomputation is
an audit; it feeds nothing back to any board decision or map.
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

TOOL_VERSION = "b1_adjudicate.py/0.3.0"
SESSION = "B1"
MANIFEST = REPO_ROOT / "manifests/b1_manifest.json"
B1_VARIANT = "0x42310001"
SCHEMA_PATH = REPO_ROOT / "schemas/self_map_v2.schema.json"

# The preregistered constants (docs/b1_preregistration.md §3–§4). The gates use THESE; the
# prediction file must agree with them (a prediction regenerated to other numbers is a
# finding, never a moved goalpost).
EXPECTED = {"addresses": bc.N, "probes_to_full_recall_conf1": bc.CODE_BITS, "probes_to_full_confirmation": bc.CODE_BITS + bc.N,
            "pairs_tested": bc.PAIRS_MAX, "deviations": 0, "pending": 0, "anomalies": 0, "unobserved_claims": 0}


class Refusal(Exception):
    pass


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------ pins
def check_pins(manifest: dict, plan_path: Path, prediction_path: Path, pins_path: Path | None = None,
               plan: dict | None = None, prediction: dict | None = None) -> None:
    """The plan and prediction files hash to the manifest's pins (and, when the caller's
    objects are given, equal the files); the pin table of every adjudication-critical file
    verifies against the tree NOW."""
    for key, path, obj in (("plan", plan_path, plan), ("prediction", prediction_path, prediction)):
        want = manifest[key]["sha256"]
        if not want:
            raise Refusal(f"the manifest pins no {key} sha256")
        if not Path(path).is_file() or sha256_of(Path(path)) != want:
            raise Refusal(f"{path} does not hash to the manifest's {key} pin")
        if obj is not None and json.loads(Path(path).read_text()) != obj:
            raise Refusal(f"the {key} object given to the adjudicator is not the pinned file's content")
    try:
        pins_mod.verify(pins_path or pins_mod.PINS, manifest)
    except pins_mod.PinRefusal as exc:
        raise Refusal(f"instrument pins: {exc}") from None


# ------------------------------------------------------------------ binding
def expected_inputs(manifest: dict, session: str = SESSION) -> dict:
    if session == SESSION:
        plan_sha, pred_sha = manifest["plan"]["sha256"], manifest["prediction"]["sha256"]
    else:
        qp = manifest.get("qualification_plan") or {}
        plan_sha, pred_sha = qp.get("sha256"), qp.get("prediction_sha256")
    return {"plan_sha256": plan_sha, "prediction_sha256": pred_sha, "pins_sha256": (manifest.get("pins") or {}).get("sha256")}


def check_binding(log: dict, manifest: dict, plan: dict, manifest_sha256: str, session: str = SESSION,
                  qualification_check=None) -> dict:
    """`qualification_check` (mapping sessions): a callable(manifest) raising on a carrier
    whose qualification evidence does not stand; None = this session needs none (B1Q)."""
    b = (log.get("l6") or {}).get("binding")
    if not isinstance(b, dict):
        raise Refusal("the run log carries no binding (l6.binding): not a B1 log")
    inputs = (log.get("l6") or {}).get("inputs")
    if not isinstance(inputs, dict):
        raise Refusal("the run log names no inputs (l6.inputs): not a B1 log")
    for k, v in expected_inputs(manifest, session).items():
        if not v or inputs.get(k) != v:
            raise Refusal(f"inputs {k}: the log says {str(inputs.get(k))[:16]!r}, this session's pinned {str(v)[:16]!r}")
    want = {"session": session, "master_seed": plan["master_seed"], "image_sha256": manifest["image"]["sha256"],
            "protocol": manifest["protocol"]["wire"], "prereg_sha256": manifest["prereg"]["sha256"],
            "b1_manifest_sha256": manifest_sha256, "psoracle_commit": manifest["instrument"]["psoracle_commit"]}
    if not want["prereg_sha256"]:
        raise Refusal("B1's preregistration is not frozen (manifest prereg.sha256 is null): nothing can be adjudicated")
    if qualification_check is not None:
        qualification_check(manifest)
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


def qualification_stands(manifest: dict) -> None:
    """The mapping session's carrier check: the pinned qualification evidence re-adjudicates
    to PASS and binds to this manifest's carrier, image and prereg (never a bare flag)."""
    import b1_qualification as bq  # noqa: E402  (lazy: it imports the B1Q adjudicator, which imports this module)
    try:
        bq.verify(manifest)
    except bq.QualificationRefusal as exc:
        raise Refusal(f"carrier qualification: {exc}") from None
    if manifest["carrier"].get("qualified") is not True:
        # the stored flag is DERIVED (b1_manifest.py); a manifest whose flag disagrees with
        # its own evidence was edited by hand or not refreshed — the runner refuses it too
        raise Refusal("carrier qualification: the manifest's carrier.qualified flag disagrees with its standing evidence (refresh the manifest)")


# ------------------------------------------------------------------ the map's validation
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


def map_findings(doc: dict, budget: int) -> list[str]:
    return schema_findings(doc) + bv.semantic_findings(doc, budget=budget)


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
def prediction_findings(log: dict, plan: dict, prediction: dict, rp: dict) -> list[str]:
    f: list[str] = []
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
    return f


def _eq(f: list[str], what: str, got, want) -> None:
    if got != want:
        f.append(f"{what} = {got!r}, preregistered {want!r}")


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
    f += prediction_findings(log, plan, prediction, rp)
    # the prediction must itself carry the preregistered constants
    es = prediction.get("expected_score") or {}
    esn = es.get("snapshots") or {}
    for what, got, want in (("prediction.expected_score.snapshots.probes_to_full_recall_conf1", esn.get("probes_to_full_recall_conf1"), EXPECTED["probes_to_full_recall_conf1"]),
                            ("prediction.expected_score.snapshots.probes_to_full_confirmation", esn.get("probes_to_full_confirmation"), EXPECTED["probes_to_full_confirmation"]),
                            ("prediction.expected_score.precision", es.get("precision"), 1.0),
                            ("prediction.expected_score.recall", es.get("recall"), 1.0)):
        _eq(f, what, got, want)
    # the verifier's conditions (preregistration §4), EXACT
    _eq(f, "verifier: precision", score["precision"], 1.0)
    _eq(f, "verifier: recall", score["recall"], 1.0)
    _eq(f, "verifier: claimed", score["claimed"], EXPECTED["addresses"])
    _eq(f, "verifier: unobserved claims", score["unobserved_claims"], EXPECTED["unobserved_claims"])
    _eq(f, "verifier: anomalies", score["anomalies"], EXPECTED["anomalies"])
    cal = score["calibration"]
    _eq(f, "verifier: final snapshot confidence-1 cohort (claimed)", cal["1"]["claimed"], 0)
    _eq(f, "verifier: final snapshot confidence-2 claimed", cal["2"]["claimed"], EXPECTED["addresses"])
    _eq(f, "verifier: final snapshot confidence-2 correct", cal["2"]["correct"], EXPECTED["addresses"])
    _eq(f, "verifier: final snapshot confidence-2 accuracy", cal["2"]["accuracy"], 1.0)
    for s in ("stratum_A", "stratum_B"):
        _eq(f, f"verifier: {s} recall", score[s]["recall"], 1.0)
        _eq(f, f"verifier: {s} precision", score[s]["precision"], 1.0)
    it = score["interaction"]
    _eq(f, "verifier: interaction pairs tested", it["pairs_tested"], EXPECTED["pairs_tested"])
    _eq(f, "verifier: interaction deviations", it["deviations"], EXPECTED["deviations"])
    _eq(f, "verifier: interaction pending", it["pending"], EXPECTED["pending"])
    _eq(f, "verifier: probes to full recall at confidence ≥ 1", snaps["probes_to_full_recall_conf1"], EXPECTED["probes_to_full_recall_conf1"])
    _eq(f, "verifier: probes to full confirmation", snaps["probes_to_full_confirmation"], EXPECTED["probes_to_full_confirmation"])
    prov = snaps.get("provisional")
    if prov is None:
        f.append("verifier: no provisional snapshot (the code probes did not complete)")
    else:
        _eq(f, "verifier: provisional snapshot precision", prov["precision"], 1.0)
        _eq(f, "verifier: provisional snapshot recall", prov["recall"], 1.0)
        pc = prov["calibration"]
        _eq(f, "verifier: provisional snapshot confidence-1 claimed", pc["1"]["claimed"], EXPECTED["addresses"])
        _eq(f, "verifier: provisional snapshot confidence-1 correct", pc["1"]["correct"], EXPECTED["addresses"])
        _eq(f, "verifier: provisional snapshot confidence-1 accuracy", pc["1"]["accuracy"], 1.0)
        _eq(f, "verifier: provisional snapshot confidence-2 cohort (claimed)", pc["2"]["claimed"], 0)
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
               instrument_root: Path | None = None, require_git: bool = True, p3_layer=None,
               plan_path: Path | None = None, prediction_path: Path | None = None, pins_path: Path | None = None,
               qualification_check=qualification_stands) -> dict:
    """`plan_path` / `prediction_path` default to the manifest's pinned paths; `pins_path` to
    the committed table; `qualification_check` to the re-adjudication of the pinned
    qualification evidence (None only for tests of the other checks — never for a runner)."""
    out = {"tool": TOOL_VERSION, "evidence": str(evidence), "outcome": None, "findings": [], "refusal": None}
    try:
        check_pins(manifest, plan_path or REPO_ROOT / manifest["plan"]["path"],
                   prediction_path or REPO_ROOT / manifest["prediction"]["path"], pins_path, plan, prediction)
        log = json.loads((evidence / "run_log.json").read_text())
        out["binding"] = check_binding(log, manifest, plan, manifest_sha256, SESSION, qualification_check)
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
        findings += map_findings(out["self_map_v2"], plan["budget"])
        out["verifier_report"] = bv.report(whole, rp["records"], truth)
        out["findings"] = findings                       # written ONCE, from the one local list
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
    ap.add_argument("--plan", type=Path, default=None)
    ap.add_argument("--prediction", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-git", action="store_true")
    a = ap.parse_args(argv)
    manifest = json.loads(a.manifest.read_text())
    plan_path = a.plan or REPO_ROOT / manifest["plan"]["path"]
    pred_path = a.prediction or REPO_ROOT / manifest["prediction"]["path"]
    res = adjudicate(a.evidence, manifest, json.loads(plan_path.read_text()), json.loads(pred_path.read_text()),
                     sha256_of(a.manifest), require_git=not a.no_git, plan_path=plan_path, prediction_path=pred_path)
    if a.out:
        a.out.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    print(res["outcome"])
    if res.get("b1_result"):
        r = res["b1_result"]
        print(json.dumps({k: r[k] for k in ("precision", "recall", "anomalies", "stratum_B", "snapshots")}, indent=1))
    return 0 if res["outcome"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

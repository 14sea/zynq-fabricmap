#!/usr/bin/env python3
"""The owner's session-contract probe cases (docs/b2_runner_correction_review_2026_09_11.md §P2-1
to §P2-3), re-run against the corrected code.

It is the review's own `probe_session_contract.py` case list, re-expressed here because that
script's closing assertions encode the PRE-correction behaviour: they assert that the binding
mutations still PASS and that a changed evidence file leaves the qualification record unchanged.
It also now stops at `reconstruct_qualification_record`, because its membership fixture writes
five of the extra files and the record pins all eleven — which is the correction itself.

Same doubling as the review's: the B1Q transcript has no B2 search blocks, so ONLY the B2 record
replay is doubled. Every instrument validator, audit gate, ledger check and rate report is real.
Not a positive B2/B2Q session, not a board qualification.
"""
import copy, json, sys, tempfile, shutil
from pathlib import Path
from unittest.mock import patch

R = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(R / "host"), str(R / "tests")]
import b2_runner as rn
import b2_manifest as bm
import claimb_r1p_instrument as inst
inst.bind(inst.DEFAULT_ROOT, require_git=False)
import test_b2_runner as tf

result = {}
source = R / "evidence/b1q/b1q_17A6_2026-09-08-01"
base = json.loads((source / "run_log.json").read_text())
plan = copy.deepcopy(base["l6"])
plan["expected_records"] = len(base["loop_records"])
plan["session"] = "B2Q"
plan["session_timeout_s"] = 1.0
plan["binding"] = copy.deepcopy(base["l6"]["binding"])          # what this invocation declares
plan["binding"]["b2_manifest_sha256"] = base["l6"]["binding"].get("b1_manifest_sha256")
plan["inputs"] = copy.deepcopy(base["l6"].get("inputs"))
for k in ("pair_first", "pair_count", "pairs_total", "master_seed", "n", "protocol"):
    plan.setdefault(k, base["l6"].get(k))

with tempfile.TemporaryDirectory(prefix="b2-contract-accept-") as temp:
    d = Path(temp)
    for name in ("run_log.json", "audits.json", "timeline.json"):
        shutil.copyfile(source / name, d / name)
    manifest = {"schema": bm.SCHEMA, "image": {"sha256": "a" * 64}, "prereg": {"sha256": "b" * 64},
                "map": {"canonical_json_sha256": "c" * 64}, "carrier": {"bitstream_sha256": "d" * 64}}
    (d / bm.MANIFEST_AT_RUN).write_text(json.dumps(manifest))
    plan["binding"]["b2_manifest_sha256"] = rn._sha(d / bm.MANIFEST_AT_RUN)

    def judge(log, man=None, archived=True):
        (d / "run_log.json").write_text(json.dumps(log))
        with patch.object(rn.adj, "adjudicate",
                          return_value={"outcome": "PASS", "findings": [], "kills": []}):
            out = rn.judge_session(d, man or manifest, plan, {}, {}, None, inst.DEFAULT_ROOT)
        return {k: out[k] for k in ("outcome", "findings", "measured_rate_per_hour", "audit_policy")}

    result["deadline_control"] = judge(base)            # span >> the 1 s limit this plan declares
    for name, fn in (("no_l6_binding", lambda x: x["l6"].pop("binding", None)),
                     ("wrong_l6_image", lambda x: x["l6"]["binding"].update(image_sha256="0" * 64)),
                     ("wrong_l6_manifest", lambda x: x["l6"]["binding"].update(b2_manifest_sha256="0" * 64)),
                     ("no_l6", lambda x: x.pop("l6", None))):
        log = copy.deepcopy(base)
        fn(log)
        result[name] = judge(log)
    result["different_manifest_argument"] = judge(base, {"schema": bm.SCHEMA, "image": {"sha256": "f" * 64},
                                                         "prereg": {"sha256": "b" * 64},
                                                         "map": {"canonical_json_sha256": "c" * 64},
                                                         "carrier": {"bitstream_sha256": "d" * 64}})
    result["no_export_seal"] = {"findings": rn.export_seal_findings(d)}

    # the same-length wrong slice the review named
    wrong_slice = copy.deepcopy(base)
    wrong_slice.setdefault("app_identity", {})
    ident_plan = dict(plan, pair_first=0, pair_count=4, pairs_total=9)
    wrong_slice["app_identity"] = dict(wrong_slice.get("app_identity") or {}, pair_first=4, pair_count=4,
                                       pairs_total=9)
    result["same_length_wrong_slice"] = {"findings": rn.binding_findings(wrong_slice, ident_plan)}

    # the qualification record's membership, through the real reconstruction
    fixture = tf.Fixture("S1")
    try:
        ev = d / "membership"
        ev.mkdir()
        (ev / bm.MANIFEST_AT_RUN).write_text(bm.render(fixture.manifest))
        (ev / "run_log.json").write_text("{}")
        (ev / "adjudication.json").write_text(json.dumps(
            {"outcome": "PASS", "session": "B2Q", "measured_rate_per_hour": 2807.0,
             "audit_policy": "all-self-reporting"}))
        partial = None
        try:
            bm.reconstruct_qualification_record(ev)
        except bm.Refusal as exc:
            partial = str(exc)
        for n in bm.QUAL_EVIDENCE_FILES:
            if not (ev / n).exists():
                (ev / n).write_text("{}")
        before = bm.reconstruct_qualification_record(ev)
        changed = {}
        for n in ("audits.json", "timeline.json", "exports.json", "console.log", "console.ts.log",
                  "summary.json", "ruling_whole_of_run.json", "ruling_provisioning.json"):
            saved = (ev / n).read_text()
            (ev / n).write_text("changed bytes")
            changed[n] = bm.reconstruct_qualification_record(ev) == before
            (ev / n).write_text(saved)
        result["qualification_record_membership"] = {
            "schema_version": bm.QUAL_SCHEMA_VERSION, "files": sorted(before["files"]),
            "incomplete_evidence_refused": partial,
            "unchanged_after_file_change": changed}
    finally:
        fixture.close()

print(json.dumps(result, indent=2))
assert result["deadline_control"]["outcome"] != "PASS"
assert all(result[n]["outcome"] != "PASS" for n in
           ("no_l6_binding", "wrong_l6_image", "wrong_l6_manifest", "no_l6", "different_manifest_argument"))
assert result["no_export_seal"]["findings"]
assert result["same_length_wrong_slice"]["findings"]
assert result["qualification_record_membership"]["incomplete_evidence_refused"]
assert not any(result["qualification_record_membership"]["unchanged_after_file_change"].values())

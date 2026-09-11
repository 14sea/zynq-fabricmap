#!/usr/bin/env python3
"""The owner's binding-completion review cases (docs/b2_binding_completion_review_2026_09_11.md),
re-run against the corrected code.

Their own `probe_binding_completion.py` now stops at `reconstruct_qualification_record`, because
that function refuses an archive it cannot parse — which is the correction — and its closing
assertions expect the pre-correction answers (`transport_control == PASS` on a relabelled B1Q
transcript whose IDENT does not satisfy the B2 identity contract). This script drives the same
cases through the production functions.

Host-only. No board, no session, no authorisation is created or consumed: the ruling archives
here are inert test envelopes.
"""
import copy, json, sys, tempfile
from pathlib import Path

R = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(R / "host"), str(R / "tests")]
import b2_manifest as bm
import b2_runner as rn
import claimb_r1p_instrument as inst
inst.bind(inst.DEFAULT_ROOT, require_git=False)
import b1_qualification as bq
import test_b2_lifecycle as tl
import test_b2_runner as tr

out = {}
f = tr.Fixture("S1")
try:
    plan = rn.qualification_session_plan(f.manifest, "ab" * 32)
    out["qualification_plan_has_inputs"] = isinstance(plan.get("inputs"), dict)
    log = {"l6": {"binding": copy.deepcopy(plan["binding"]), "inputs": copy.deepcopy(plan["inputs"])},
           "app_identity": dict(rn.expected_identity(f.manifest, plan), schema="app_identity",
                                schema_version="1.5.0")}

    def bind(mutate=None):
        doc = copy.deepcopy(log)
        if mutate:
            mutate(doc)
        return rn.binding_findings(doc, plan, f.manifest)

    out["binding_control"] = bind()
    out["ident_carrier"] = bind(lambda d: d["app_identity"].__setitem__("carrier_sha256", "0" * 64))
    out["ident_universe"] = bind(lambda d: d["app_identity"].__setitem__("universe_sha256", "0" * 64))
    out["ident_carrier_variant"] = bind(lambda d: d["app_identity"].__setitem__("carrier_variant", "0x0"))
    out["missing_inputs"] = bind(lambda d: d["l6"].pop("inputs"))
    out["wrong_inputs_manifest"] = bind(lambda d: d["l6"]["inputs"].__setitem__("b2_manifest_sha256", "0" * 64))

    b = plan["binding"]

    def body(key):
        doc = {"ruling": rn.QUAL_RULING_TEXT if key == "whole_of_run" else rn.PROVISION_RULING_TEXT,
               "boardid": "17A6", "granted_by": "t", "date": "2026-09-11", "session": b["session"],
               "prereg_sha256": b["prereg_sha256"], "image_sha256": b["image_sha256"],
               "b2_manifest_sha256": b["b2_manifest_sha256"]}
        if key == "whole_of_run":
            doc["master_seed"] = b["master_seed"]
        return doc

    def rulings(whole=None, prov=None):
        d = Path(tempfile.mkdtemp(prefix="b2acc_"))
        for key, doc in (("whole_of_run", whole if whole is not None else body("whole_of_run")),
                         ("provisioning", prov if prov is not None else body("provisioning"))):
            path = d / bq.RULING_FILES[key]
            path.write_text(doc if isinstance(doc, str) else
                            json.dumps(bq.archive_envelope(json.dumps(doc).encode())))
        return rn.archived_ruling_findings(d, plan)

    out["ruling_control"] = rulings()
    out["whole_not_json"] = rulings("not JSON")
    out["provision_not_json"] = rulings(None, "not JSON")
    for field, value in (("master_seed", b["master_seed"] ^ 1), ("image_sha256", "0" * 64),
                         ("session", "B2"), ("boardid", "OTHER"),
                         ("ruling", "whole-of-run B2 map utility")):
        doc = body("whole_of_run")
        doc[field] = value
        out["whole_wrong_" + field] = rulings(doc)

    ev = Path(tempfile.mkdtemp(prefix="b2acc_sum_"))
    (ev / bm.MANIFEST_AT_RUN).write_text(bm.render(f.manifest))
    (ev / "run_log.json").write_text(json.dumps({"session": "B2Q", "app_identity": {"token": "t" * 32}}))
    (ev / "adjudication.json").write_text(json.dumps(
        {"outcome": "PASS", "session": "B2Q", "measured_rate_per_hour": 2807.0,
         "audit_policy": "all-self-reporting"}))
    tl.fill_evidence(ev)
    summary = json.loads((ev / "summary.json").read_text())
    summary["token"] = "t" * 32
    (ev / "summary.json").write_text(json.dumps(summary))
    out["summary_control"] = bm.summary_findings(ev)
    (ev / "summary.json").write_text("not JSON")
    out["summary_not_json"] = bm.summary_findings(ev)
    (ev / "summary.json").write_text(json.dumps(dict(summary, outcome="HOLD")))
    out["summary_wrong_outcome"] = bm.summary_findings(ev)
    (ev / "summary.json").write_text(json.dumps(summary))
    (ev / bq.RULING_FILES["whole_of_run"]).write_text("not JSON")
    try:
        bm.reconstruct_qualification_record(ev)
        out["invalid_archive_record"] = "ACCEPTED"
    except bm.Refusal as exc:
        out["invalid_archive_record"] = f"REFUSED: {exc}"
finally:
    f.close()

print(json.dumps(out, indent=2))
assert out["qualification_plan_has_inputs"]
assert out["binding_control"] == [] and out["ruling_control"] == [] and out["summary_control"] == []
assert all(out[k] for k in ("ident_carrier", "ident_universe", "ident_carrier_variant",
                            "missing_inputs", "wrong_inputs_manifest", "whole_not_json",
                            "provision_not_json", "summary_not_json", "summary_wrong_outcome"))
assert all(out["whole_wrong_" + k] for k in ("master_seed", "image_sha256", "session", "boardid", "ruling"))
assert out["invalid_archive_record"].startswith("REFUSED")

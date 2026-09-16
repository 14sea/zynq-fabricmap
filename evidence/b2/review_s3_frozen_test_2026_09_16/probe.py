"""Read-only evidence for the S3/frozen-test contradiction.

This does not modify the index, pins, manifest, plan, or test. It compares the
committed S3 and correction commits with the frozen pin table and the failed
test report left by the attempted correction.
"""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sha = lambda b: hashlib.sha256(b).hexdigest()
blob = lambda rev, path: subprocess.check_output(["git", "show", f"{rev}:{path}"], cwd=ROOT)

rel = "tests/test_b2_plan.py"
pins = json.loads((ROOT / "manifests/b2_instrument_pins.json").read_text())
s3_manifest = json.loads(blob("f007f92", "manifests/b2_manifest.json"))
s3_plan = json.loads(blob("f007f92", "evidence/b2/plan.json"))
frozen_test = blob("f007f92", rel)
changed_test = blob("8319683", rel)
report_path = ROOT / "evidence/b2/tests/test_report_2026-09-16T095911Z.json"
report = json.loads(report_path.read_text())

assert pins["files"][rel] == sha(frozen_test)
assert sha(changed_test) != pins["files"][rel]
assert b'"UNDETERMINED"' in frozen_test
assert s3_plan["session_split"]["status"] == "DETERMINED"
assert sha(blob("f007f92", "evidence/b2/plan.json")) == s3_manifest["plan"]["sha256"]
assert report["head_at_run"].startswith("8319683")
assert report["clean_tree_proof"] is False
assert any("tests/test_b2_plan.py: hash differs" in x for x in report["proof_refusals"])

# The qualification transition deliberately strips only its licensed state fields.
# instrument_pins and prereg are outside that set, so either correction changes
# the identity that the archived B2Q manifest_at_run qualified.
allowed = {"qualification", "qualified", "calibration", "plan", "status", "history"}
assert "instrument_pins" not in allowed and "prereg" not in allowed

out = {
    "s3_commit": "f007f92",
    "correction_commit": "8319683",
    "frozen_test": {
        "path": rel,
        "pin_sha256": pins["files"][rel],
        "s3_blob_sha256": sha(frozen_test),
        "correction_blob_sha256": sha(changed_test),
        "asserts_undetermined": True,
    },
    "s3_plan": {
        "status": s3_plan["session_split"]["status"],
        "sha256": s3_manifest["plan"]["sha256"],
        "split": [len(x["pairs"]) for x in s3_plan["session_split"]["sessions"]],
        "total_records": s3_plan["session_split"]["total_records"],
    },
    "failed_report": {
        "path": str(report_path.relative_to(ROOT)),
        "ran": report["ran"],
        "failures": report["failures"],
        "errors": report["errors"],
        "clean_tree_proof": report["clean_tree_proof"],
        "pin_refusals": [x for x in report["proof_refusals"] if "pinned surface" in x],
    },
    "strict_transition": {
        "licensed_top_level_fields": sorted(allowed),
        "instrument_pins_is_licensed": False,
        "prereg_is_licensed": False,
        "consequence": "A repin or prereg edit is a new frozen identity and cannot reuse the existing B2Q qualification binding.",
    },
    "review_result": "The S3 plan is internally bound, but the frozen test contract requires the pre-S3 plan state. The current lifecycle cannot produce both S3 and a zero-failure clean-tree proof.",
}
print(json.dumps(out, indent=2, sort_keys=True))

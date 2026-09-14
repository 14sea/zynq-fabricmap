"""Seventh-review acceptance. Offline fake serial only; no production edits.

Runs the unchanged sixth-review probe, then requires its previously unmet export
contract and checks preservation of the cutoff and primary transport error.
Prints JSON to stdout; exits nonzero if any assertion fails.
"""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
probe = ROOT / "evidence/b1q/review_board_export_cutoff_2026_09_14/probe.py"
p = json.loads(subprocess.check_output([sys.executable, "-B", str(probe)], cwd=ROOT, text=True))
assert p["required_export_failure_contract"]["satisfied"]
c = p["cases"]
for name in ("cutoff_and_export_failure", "partial_cutoff_and_export_failure"):
    r = c[name]
    t = r["control"]["terminal"]
    assert r["exit"] == 2 and r["brief"]["stage"] == "export"
    assert t["reason"] == "tool_error" and t["phase"] == "export read_0000.bin"
    assert t["observed"]["reason"] == "exposure_seconds"
    assert len(r["commands"]) == 2 and r["brief"]["reads_compared"] == 0
    assert "read_0000.bin" not in r["files"]
    assert r["brief"]["mismatches_per_100_compared_responses"] is None
    assert r["brief"]["all_compared_responses_differ"] is None
    assert r["control"]["reads"][0]["classification"] == "unclassified"
    assert "counters_before" in r["control"] and "counters_after" in r["control"]
    assert r["entry_equals_stdout"] and r["port_close_count"] == 1
assert c["partial_cutoff_and_export_failure"]["control"]["terminal"]["observed"]["partial_bytes"] == 67
r = c["detach_and_export_failure"]
assert "synthetic detach" in r["control"]["terminal"]["detail"]
assert "read_0000.bin" in r["control"]["terminal"]["export_error"]
for name in ("read_0000.bin", "read_0001.bin"):
    r = c[name]
    assert r["control"]["terminal"]["observed"]["classification"] == "identical"
    assert r["control"]["reads"][-1]["classification"] == "identical"
    assert r["brief"]["reads_compared"] > 0
p["seventh_review_acceptance"] = "PASS"
print(json.dumps(p, indent=2, sort_keys=True))

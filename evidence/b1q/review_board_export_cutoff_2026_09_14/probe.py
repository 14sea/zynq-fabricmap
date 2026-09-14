"""Offline review of 04d4b86. No serial hardware, production edits, or rulings.

The submitted serial/clock adapter drives the production CLI. This script asserts
the corrected single-fault contracts and reports the remaining combined-fault gap.
Run from any directory with python3 -B; JSON is written to stdout.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "host")]
from test_board_transport_soak import TheConsistencyControl

results = {"head": subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "tool_sha256": hashlib.sha256((ROOT / "host/board_transport_soak.py").read_bytes()).hexdigest(),
    "cases": {}}

names = ["positive", "echo_positive", "sync.bin", "reference.bin", "reference.json",
         "read_0000.bin", "read_0001.bin", "leading_crlf", "injected_command",
         "reset_with_prompt", "partial_detach", "exposure_cutoff",
         "cutoff_and_export_failure", "detach_and_export_failure",
         "partial_cutoff", "partial_cutoff_and_export_failure"]
for name in names:
    t = TheConsistencyControl()
    t.setUp()
    try:
        kw, extra = {}, []
        if name in ("sync.bin", "reference.bin", "reference.json", "read_0000.bin", "read_0001.bin"):
            kw["fault_export"] = (name,)
        elif name == "echo_positive":
            kw["module"] = t.module(echo=True)
        elif name == "leading_crlf":
            kw["module"] = t.module(mutate=lambda i, r: b"\r\n" + r if i == 1 else r)
        elif name == "injected_command":
            command = f"md.l {t.ADDR:#010x} {len(t.WORDS):#x}".encode()
            kw["module"] = t.module(mutate=lambda i, r: r.replace(
                b"................", command + b"................") if i == 1 else r)
        elif name == "reset_with_prompt":
            kw["module"] = t.module(mutate=lambda i, r:
                b"\r\nU-Boot 2026.04 (synthetic reset)\r\nZynq> " if i == 1 else r)
        elif name in ("partial_detach", "detach_and_export_failure"):
            kw["module"] = t.module(detach_at=1)
        elif name in ("exposure_cutoff", "cutoff_and_export_failure"):
            kw["module"] = t.module(silent_from=1)
            extra = ["--seconds", "0.12"]
        elif name in ("partial_cutoff", "partial_cutoff_and_export_failure"):
            kw["module"] = t.module(mutate=lambda i, r: r[:-6] if i == 1 else r)
            extra = ["--seconds", "0.12"]
        if name in ("cutoff_and_export_failure", "detach_and_export_failure",
                    "partial_cutoff_and_export_failure"):
            kw["fault_export"] = ("read_0000.bin",)
        code, brief = t.run_cli(*extra, **kw)
        disk = json.loads((t.d / "control.json").read_text())
        row = {"exit": code, "brief": brief, "commands": t.boards[0].commands,
               "control": disk, "files": sorted(p.name for p in t.d.iterdir()),
               "entry_equals_stdout": json.loads((t.d / "entry.json").read_text()) == brief,
               "port_close_count": t.boards[0].closed}
        results["cases"][name] = row
        assert row["entry_equals_stdout"] and row["port_close_count"] == 1
    finally:
        t.doCleanups()

c = results["cases"]
for name in ("positive", "echo_positive"):
    assert c[name]["exit"] == 0 and c[name]["brief"]["identical_responses"] == 4
for name, count in (("sync.bin", 0), ("reference.bin", 1), ("reference.json", 1),
                    ("read_0000.bin", 2), ("read_0001.bin", 3)):
    r = c[name]
    assert r["exit"] == 2 and len(r["commands"]) == count
    assert r["brief"]["stage"] == "export"
    assert r["control"]["terminal"]["reason"] == "tool_error"
    assert r["control"]["terminal"]["phase"] == "export " + name
for name in ("leading_crlf", "injected_command"):
    assert c[name]["brief"]["mismatched_responses"] == 1
assert c["reset_with_prompt"]["brief"]["terminal"] == "board_reset"
assert c["reset_with_prompt"]["exit"] == 2 and len(c["reset_with_prompt"]["commands"]) == 2
for name in ("partial_detach", "exposure_cutoff", "cutoff_and_export_failure",
             "partial_cutoff", "partial_cutoff_and_export_failure"):
    b = c[name]["brief"]
    assert b["reads_compared"] == 0
    assert b["mismatches_per_100_compared_responses"] is None
    assert b["all_compared_responses_differ"] is None
assert c["exposure_cutoff"]["exit"] == 0
assert c["detach_and_export_failure"]["exit"] == 2
assert "synthetic detach" in c["detach_and_export_failure"]["control"]["terminal"]["detail"]
assert c["partial_cutoff"]["exit"] == 0
assert c["partial_cutoff"]["control"]["reads"][0]["raw_bytes"] > 0
gap = c["partial_cutoff_and_export_failure"]
assert gap["control"]["reads"][0]["raw_bytes"] > 0
results["required_export_failure_contract"] = {
    "expected_exit": 2, "expected_stage": "export", "expected_terminal": "tool_error",
    "observed_exit": gap["exit"], "observed_stage": gap["brief"]["stage"],
    "observed_terminal": gap["brief"]["terminal"],
    "satisfied": gap["exit"] == 2 and gap["brief"]["stage"] == "export"
                 and gap["brief"]["terminal"] == "tool_error"}
print(json.dumps(results, indent=2, sort_keys=True))

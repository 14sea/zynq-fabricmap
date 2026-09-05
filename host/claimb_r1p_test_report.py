#!/usr/bin/env python3
"""Claim B round 1′ — the clean-tree test report, FAIL-CLOSED (the instrument's
`host/test_report.py` discipline, for this repository).

    claimb_r1p_test_report.py [--out-dir evidence/claimb_round1prime/tests] [--no-run --log FILE --exit-status N]

Runs `python3 -m unittest discover -s tests` from a CLEAN tree — this repository's
carrier-authority gate skips 27 tests and hides 5 when any tracked file differs from HEAD,
so a dirty-tree run is recorded as such and can never stand as the package's proof — and
writes `test_report_<UTC>.json` with the counts, the result line, `head_at_run`, the
dirty flag, the instrument checkout's commit and dirty flag, and the sha256 of every
round 1′ artifact the suite pinned. Exit = the suite's status only if the report landed;
exit 3 otherwise. The report is what the board package cites as "the test reports and the
clean-tree proof" (owner 2026-09-05); a report with `worktree_dirty: true` or `skipped > 0`
is not that proof, and the package says so.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import claimb_r1p_instrument as inst  # noqa: E402

ARTIFACTS = ("manifests/claimb_round1prime_manifest.json", "manifests/claimb_round1prime_instrument_pins.json",
             "evidence/claimb_round1prime/plan.json", "evidence/claimb_round1prime/model_prediction.json",
             "docs/claimb_round1prime_preregistration.md")


def git(*args: str, cwd: Path = REPO_ROOT) -> str | None:
    p = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def run_suite() -> tuple[int, str]:
    p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=REPO_ROOT,
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def build(exit_status: int, log_text: str) -> dict:
    ran = re.search(r"^Ran (\d+)", log_text, re.M)
    result = [l for l in log_text.splitlines() if l.startswith(("OK", "FAILED"))]
    skipped = re.search(r"skipped=(\d+)", log_text)
    failures = re.search(r"failures=(\d+)", log_text); errors = re.search(r"errors=(\d+)", log_text)
    dirty = git("status", "--porcelain")
    inst_head = git("rev-parse", "HEAD", cwd=inst.DEFAULT_ROOT)
    inst_dirty = git("status", "--porcelain", cwd=inst.DEFAULT_ROOT)
    arts = {}
    for rel in ARTIFACTS:
        p = REPO_ROOT / rel
        arts[rel] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
    rep = {"schema": "claimb_r1p_test_report", "schema_version": "1.0.0",
           "at": time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()),
           "exit_status": int(exit_status), "ran": int(ran.group(1)) if ran else None,
           "result_line": result[-1] if result else None,
           "skipped": int(skipped.group(1)) if skipped else 0,
           "failures": int(failures.group(1)) if failures else 0, "errors": int(errors.group(1)) if errors else 0,
           "host": os.uname().nodename, "user": os.environ.get("USER") or str(os.getuid()),
           "head_at_run": git("rev-parse", "HEAD"), "worktree_dirty": bool(dirty) if dirty is not None else None,
           "instrument": {"root": str(inst.DEFAULT_ROOT), "head": inst_head,
                          "dirty": bool(inst_dirty) if inst_dirty is not None else None,
                          "pinned_commit": inst.load_manifest()["instrument"]["psoracle_commit"]},
           "artifacts_sha256": arts,
           "note": ("head_at_run is the HEAD when the suite ran; the commit that includes this report is necessarily "
                    "later. A clean-tree proof needs worktree_dirty false AND skipped 0 AND exit_status 0.")}
    rep["clean_tree_proof"] = (rep["worktree_dirty"] is False and rep["skipped"] == 0 and rep["exit_status"] == 0
                               and rep["failures"] == 0 and rep["errors"] == 0
                               and rep["instrument"]["head"] == rep["instrument"]["pinned_commit"]
                               and rep["instrument"]["dirty"] is False)
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "evidence/claimb_round1prime/tests")
    ap.add_argument("--no-run", action="store_true", help="build the report from --log and --exit-status")
    ap.add_argument("--log", type=Path, default=None)
    ap.add_argument("--exit-status", type=int, default=None)
    a = ap.parse_args(argv)
    if a.no_run:
        if a.log is None or a.exit_status is None:
            print("--no-run needs --log and --exit-status", file=sys.stderr); return 3
        rc, text = a.exit_status, a.log.read_text()
    else:
        rc, text = run_suite()
    rep = build(rc, text)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    out = a.out_dir / f"test_report_{rep['at']}.json"
    tmp = out.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n")
        os.replace(tmp, out)
    except OSError as exc:
        print(f"EXIT 3: the report did not land: {exc}", file=sys.stderr); return 3
    print(f"{rep['result_line']}  ran {rep['ran']} skipped {rep['skipped']} dirty {rep['worktree_dirty']} "
          f"clean_tree_proof {rep['clean_tree_proof']}\nreport: {out}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

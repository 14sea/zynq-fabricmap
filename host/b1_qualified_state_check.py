#!/usr/bin/env python3
"""B1 — the QUALIFIED-STATE suite check (host-only; owner's decision of 2026-09-06,
docs/b1q_transition_decision_2026_09_06.md §2): before any board session the whole suite
must pass with the committed manifest as it is (not qualified) AND with a manifest in
which a B1Q qualification record is pinned — the second state produced for real, on disk,
and read by the tests as the committed manifest:

  1. a modelled B1Q session (host/b1_modelled_session.py, the instrument's real host stack)
     is run BOUND TO THE COMMITTED MANIFEST'S BYTES with its own qualification plan;
  2. its evidence is adjudicated and the qualification record written as b1q_runner does;
  3. the record is pinned with the production refresh (host/b1_manifest.refresh with
     --qualification: verify() incl. re-adjudication, qualified derived) into
     manifests/b1_manifest.json IN THE WORKING TREE, temporarily;
  4. the whole suite runs against that manifest (the carrier-authority tests skip on the
     dirty tree — they do not read the manifest);
  5. the committed manifest is restored (git checkout) and the tree is left as found.
The report (evidence/b1/tests/qualified_state_report_<UTC>.json) records both the pinned
manifest's sha256 and the suite result; the clean-tree report of the committed state is
b1_test_report.py's. Nothing here touches a board, a port or a ruling.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
sys.path.insert(0, str(REPO_ROOT / "tests"))
MANIFEST = REPO_ROOT / "manifests/b1_manifest.json"


def git(*args):
    p = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "evidence/b1/tests")
    a = ap.parse_args(argv)
    rc, dirty = git("status", "--porcelain")
    if dirty:
        print("REFUSED: the working tree must be clean (the committed manifest is replaced temporarily)", file=sys.stderr)
        return 2
    head = git("rev-parse", "HEAD")[1]
    committed_text = MANIFEST.read_text()
    committed_sha = hashlib.sha256(committed_text.encode()).hexdigest()
    m = json.loads(committed_text)
    if not m["prereg"].get("frozen") or not m["image"].get("board_ready"):
        print("REFUSED: the committed manifest is not frozen / board_ready: nothing to qualify against", file=sys.stderr)
        return 2
    import b1_manifest as bmf
    from test_b1_qualification import qualify
    tmp = Path(tempfile.mkdtemp(prefix="b1_qualified_state_"))
    # 1–2: the modelled B1Q session bound to the committed manifest's bytes
    m_run = json.loads(committed_text)
    m_run["carrier"]["qualification"] = None; m_run["carrier"]["qualified"] = False
    rec, out, res, sha = qualify(tmp, m_run, "b1q", text=committed_text)
    if sha != committed_sha or res.get("outcome") != "PASS":
        print(f"REFUSED: the modelled B1Q session did not PASS against the committed manifest ({res.get('outcome')})", file=sys.stderr)
        return 2
    # 3: the production pin
    pinned = bmf.refresh(json.loads(committed_text), qualification_dir=out)
    if pinned["carrier"]["qualified"] is not True:
        print("REFUSED: the pinned manifest did not derive qualified: true", file=sys.stderr)
        return 2
    pinned_text = json.dumps(pinned, indent=1, ensure_ascii=False) + "\n"
    pinned_sha = hashlib.sha256(pinned_text.encode()).hexdigest()
    report = {"schema": "b1_qualified_state_report", "schema_version": "1.0.0", "at": time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()),
              "head": head, "committed_manifest_sha256": committed_sha, "pinned_manifest_sha256": pinned_sha,
              "modelled_b1q_evidence": str(out), "modelled_b1q_token": rec["binding"]["token"],
              "record_manifest_at_run_sha256": rec["binding"]["b1_manifest_sha256"]}
    try:
        MANIFEST.write_text(pinned_text)
        p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=REPO_ROOT, capture_output=True, text=True)
        text = p.stdout + p.stderr
        ran = re.search(r"^Ran (\d+)", text, re.M); skipped = re.search(r"skipped=(\d+)", text)
        fails = re.search(r"failures=(\d+)", text); errs = re.search(r"errors=(\d+)", text)
        report["qualified_state"] = {"exit_status": p.returncode, "ran": int(ran.group(1)) if ran else None,
                                     "skipped": int(skipped.group(1)) if skipped else 0, "failures": int(fails.group(1)) if fails else 0,
                                     "errors": int(errs.group(1)) if errs else 0,
                                     "result_line": next((l for l in text.splitlines() if l.startswith(("OK", "FAILED"))), None),
                                     "note": "the carrier-authority tests skip on the dirty tree (the temporary manifest); they do not read the manifest"}
        report["qualified_state_log_tail"] = text[-3000:]
    finally:
        MANIFEST.write_text(committed_text)
        git("checkout", "--", str(MANIFEST.relative_to(REPO_ROOT)))
    rc2, dirty2 = git("status", "--porcelain")
    report["tree_restored"] = (dirty2 == "")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    outp = a.out_dir / f"qualified_state_report_{report['at']}.json"
    outp.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    q = report["qualified_state"]
    ok = q["exit_status"] == 0 and q["failures"] == 0 and q["errors"] == 0 and report["tree_restored"]
    print(f"qualified-state suite: {q['result_line']} ran {q['ran']} skipped {q['skipped']} | pinned manifest {pinned_sha[:16]} | tree restored {report['tree_restored']}\nreport: {outp}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

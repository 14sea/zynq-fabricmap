#!/usr/bin/env python3
"""B2 — the clean-tree test report, FAIL-CLOSED (B1's `b1_test_report.py` discipline, for the B2
package; standalone — it depends on no B1 tool).

    b2_test_report.py [--out-dir evidence/b2/tests] [--focused] [--no-run --log FILE --exit-status N]

Runs the suite from a CLEAN tree and writes `test_report_<UTC>.json` (schema `b2_test_report`)
with the counts, the result line, `head_at_run`, the worktree dirty flag, the instrument
checkout's commit and dirty flag, and the sha256 of every B2 artifact the suite is pinned to —
the manifest (when it exists), both pin tables, the plan and prediction, the build evidence, the
preregistration, the architecture, the schema, the data header and the import table.

Two things it refuses to paper over, because the package quotes this file as its proof:

  * a report is a CLEAN-TREE PROOF only when the worktree is clean, nothing was skipped, the
    suite exited zero with no failures or errors, and the instrument is at its pinned commit and
    clean. Anything else is a report, not a proof, and `clean_tree_proof` says so.
  * the B2 PIN TABLE is re-verified as part of building the report. A suite that passed against
    a tree whose pinned decision surface has drifted proves nothing about the package, so the
    report records `pins_verified` and the count, and a drift is named in `pins_refusal` and
    forces `clean_tree_proof` false. The manifest is optional (it does not exist before S0), and
    the table is then verified against its own bytes.

Exit = the suite's status only if the report landed; exit 3 otherwise.
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

SCHEMA = "b2_test_report"
SCHEMA_VERSION = "1.0.0"
FOCUSED_PATTERN = "test_b[23]*.py"
B2_ARTIFACTS = ("manifests/b2_manifest.json", "manifests/b2_instrument_pins.json",
                "manifests/b1_manifest.json", "manifests/b1_instrument_pins.json",
                "evidence/b2/plan.json", "evidence/b2/prediction.json", "evidence/b2/build_evidence.json",
                "evidence/b2/gate/recomputed_2026_09_10/gate_report.json",
                "docs/b2_preregistration.md", "docs/b2_architecture.md", "docs/b2_package.md",
                "schemas/self_map_v2.schema.json", "firmware/b2/p3_data.h", "firmware/b2/IMPORT.json")


def git(*args: str, cwd: Path = REPO_ROOT) -> str | None:
    p = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def run_suite(focused: bool = False) -> tuple[int, str]:
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
    if focused:
        cmd += ["-p", FOCUSED_PATTERN]
    p = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def pin_state(root: Path = REPO_ROOT) -> dict:
    """The pinned decision surface, re-verified while the report is built. A suite that passed
    against a drifted tree proves nothing about the package."""
    import b2_pins
    manifest_path = Path(root) / "manifests/b2_manifest.json"
    out: dict = {"manifest_present": manifest_path.is_file()}
    try:
        if out["manifest_present"]:
            manifest = json.loads(manifest_path.read_text())
        else:
            # No manifest before S0: hold the table to its OWN bytes, so the files it lists are
            # still all checked. This is a weaker binding and the report says which one it used.
            table = Path(root) / "manifests/b2_instrument_pins.json"
            manifest = {"schema": "b2_manifest",
                        "instrument_pins": {"path": "manifests/b2_instrument_pins.json",
                                            "sha256": b2_pins.sha256_of(table)}}
        result = b2_pins.verify(manifest, root=root)
        out.update({"pins_verified": True, "pins_refusal": None, **result})
    except Exception as exc:                          # noqa: BLE001 — recorded, never hidden
        out.update({"pins_verified": False, "pins_refusal": f"{type(exc).__name__}: {exc}",
                    "files_verified": None, "b1_files_verified": None})
    out["bound_to"] = "the manifest's pin" if out["manifest_present"] else "the table's own bytes (no manifest before S0)"
    return out


def build(exit_status: int, log_text: str, focused: bool = False, root: Path = REPO_ROOT) -> dict:
    ran = re.search(r"^Ran (\d+)", log_text, re.M)
    result = [ln for ln in log_text.splitlines() if ln.startswith(("OK", "FAILED"))]
    skipped = re.search(r"skipped=(\d+)", log_text)
    failures = re.search(r"failures=(\d+)", log_text)
    errors = re.search(r"errors=(\d+)", log_text)
    dirty = git("status", "--porcelain")
    inst_head = git("rev-parse", "HEAD", cwd=inst.DEFAULT_ROOT)
    inst_dirty = git("status", "--porcelain", cwd=inst.DEFAULT_ROOT)
    arts = {}
    for rel in B2_ARTIFACTS:
        p = Path(root) / rel
        arts[rel] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
    pins = pin_state(root)
    rep = {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "package": "B2 v0.3",
           "at": time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()),
           "scope": "focused (test_b[23]*)" if focused else "whole suite",
           "exit_status": int(exit_status), "ran": int(ran.group(1)) if ran else None,
           "result_line": result[-1] if result else None,
           "skipped": int(skipped.group(1)) if skipped else 0,
           "failures": int(failures.group(1)) if failures else 0,
           "errors": int(errors.group(1)) if errors else 0,
           "host": os.uname().nodename, "user": os.environ.get("USER") or str(os.getuid()),
           "head_at_run": git("rev-parse", "HEAD"),
           "worktree_dirty": bool(dirty) if dirty is not None else None,
           "instrument": {"root": str(inst.DEFAULT_ROOT), "head": inst_head,
                          "dirty": bool(inst_dirty) if inst_dirty is not None else None,
                          "pinned_commit": inst.load_manifest()["instrument"]["psoracle_commit"]},
           "pins": pins, "artifacts_sha256": arts,
           "note": ("head_at_run is the HEAD when the suite ran; the commit that includes this report is "
                    "necessarily later. A clean-tree proof needs worktree_dirty false AND skipped 0 AND "
                    "exit_status 0 AND no failures or errors AND the instrument at its pinned commit and "
                    "clean AND the pinned decision surface verifying.")}
    rep["clean_tree_proof"] = (rep["worktree_dirty"] is False and rep["skipped"] == 0
                               and rep["exit_status"] == 0 and rep["failures"] == 0 and rep["errors"] == 0
                               and rep["ran"] is not None
                               and rep["instrument"]["head"] == rep["instrument"]["pinned_commit"]
                               and rep["instrument"]["dirty"] is False
                               and pins["pins_verified"] is True)
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "evidence/b2/tests")
    ap.add_argument("--focused", action="store_true",
                    help=f"run only {FOCUSED_PATTERN} instead of the whole suite (recorded in the report)")
    ap.add_argument("--no-run", action="store_true", help="build the report from --log and --exit-status")
    ap.add_argument("--log", type=Path, default=None)
    ap.add_argument("--exit-status", type=int, default=None)
    a = ap.parse_args(argv)
    if a.no_run:
        if a.log is None or a.exit_status is None:
            print("--no-run needs --log and --exit-status", file=sys.stderr)
            return 3
        rc, text = a.exit_status, a.log.read_text()
    else:
        rc, text = run_suite(a.focused)
    rep = build(rc, text, focused=a.focused)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    out = a.out_dir / f"test_report_{rep['at']}.json"
    tmp = out.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n")
        os.replace(tmp, out)
    except OSError as exc:
        print(f"EXIT 3: the report did not land: {exc}", file=sys.stderr)
        return 3
    print(f"{rep['result_line']}  ran {rep['ran']} skipped {rep['skipped']} dirty {rep['worktree_dirty']} "
          f"pins {rep['pins']['pins_verified']} clean_tree_proof {rep['clean_tree_proof']}\nreport: {out}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

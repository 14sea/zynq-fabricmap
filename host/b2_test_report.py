#!/usr/bin/env python3
"""B2 — the clean-tree test report, FAIL-CLOSED (B1's `b1_test_report.py` discipline, for the B2
package; standalone — it depends on no B1 tool).

    b2_test_report.py [--out-dir evidence/b2/tests] [--focused]
    b2_test_report.py --no-run --log FILE --exit-status N   (a report, NEVER a proof)

It takes a SNAPSHOT of everything outside the log that the verdict depends on — the repository
root, HEAD, the worktree's cleanliness, the instrument's commit and cleanliness, the pinned
decision surface and every pinned artifact's digest — **before** the suite starts and again when
it ends, and writes `test_report_<UTC>.json` (schema `b2_test_report`) holding both.

A report is a CLEAN-TREE PROOF only when every one of these holds, and `proof_refusals` names
each one that did not (the owner's review of 2026-09-12):

  * the suite was EXECUTED BY THIS TOOL. A `--no-run` report reconstructs a verdict from a log
    whose run this tool did not observe, so it is never a proof, however clean the tree is now.
  * the start and end snapshots AGREE: the same HEAD, both worktrees clean, the instrument at its
    pinned commit and clean in both, the pinned surface verifying in both, and every artifact
    digest unchanged across the run. A dirty start with a clean finish is not a clean run.
  * the log is a COMPLETE SUCCESSFUL summary: exactly one `Ran N` line with N > 0, and a result
    line that is exactly `OK`. Not "no result line", not a bare `FAILED`, not `Ran 0 tests`, not
    `OK (skipped=unknown)` — an unparsed counter is an unknown, and an unknown is not a zero.
  * the exit status is zero with no failures, errors or skips.

Exit: the suite's status when the report landed; **3** for any failure to read the log, create
the output directory or write the report.
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
SCHEMA_VERSION = "2.0.0"          # 1.0.0 -> 2.0.0: two snapshots, and a strict log contract
FOCUSED_PATTERN = "test_b[23]*.py"
B2_ARTIFACTS = ("manifests/b2_manifest.json", "manifests/b2_instrument_pins.json",
                "manifests/b1_manifest.json", "manifests/b1_instrument_pins.json",
                "evidence/b2/plan.json", "evidence/b2/prediction.json", "evidence/b2/build_evidence.json",
                "evidence/b2/gate/recomputed_2026_09_10/gate_report.json",
                "docs/b2_preregistration.md", "docs/b2_architecture.md", "docs/b2_package.md",
                "schemas/self_map_v2.schema.json", "firmware/b2/p3_data.h", "firmware/b2/IMPORT.json")


class ReportIOError(Exception):
    """An expected I/O failure at this tool's boundary — exit 3, never a traceback."""


def git(*args: str, cwd: Path = REPO_ROOT) -> str | None:
    p = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


# ------------------------------------------------------------------ the snapshot


def pin_state(root: Path = REPO_ROOT) -> dict:
    """The pinned decision surface, verified now. A suite that passed against a tree whose pinned
    surface has drifted proves nothing about the package."""
    import b2_pins
    root = Path(root)
    manifest_path = root / "manifests/b2_manifest.json"
    out: dict = {"manifest_present": manifest_path.is_file()}
    try:
        if out["manifest_present"]:
            manifest = json.loads(manifest_path.read_text())
        else:
            # No manifest before S0: hold the table to its OWN bytes, so every file it lists is
            # still checked. A weaker binding, and the report says which one it used.
            table = root / "manifests/b2_instrument_pins.json"
            manifest = {"schema": "b2_manifest",
                        "instrument_pins": {"path": "manifests/b2_instrument_pins.json",
                                            "sha256": b2_pins.sha256_of(table)}}
        out.update({"pins_verified": True, "pins_refusal": None, **b2_pins.verify(manifest, root=root)})
    except Exception as exc:                          # noqa: BLE001 — recorded, never hidden
        out.update({"pins_verified": False, "pins_refusal": f"{type(exc).__name__}: {exc}",
                    "files_verified": None, "b1_files_verified": None})
    out["bound_to"] = ("the manifest's pin" if out["manifest_present"]
                       else "the table's own bytes (no manifest before S0)")
    return out


def snapshot(root: Path = REPO_ROOT) -> dict:
    """Everything outside the log that the verdict depends on, observed at ONE instant."""
    root = Path(root)
    dirty = git("status", "--porcelain", cwd=root)
    inst_dirty = git("status", "--porcelain", cwd=inst.DEFAULT_ROOT)
    return {"at": time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()), "root": str(root),
            "head": git("rev-parse", "HEAD", cwd=root),
            "worktree_dirty": bool(dirty) if dirty is not None else None,
            "instrument": {"root": str(inst.DEFAULT_ROOT),
                           "head": git("rev-parse", "HEAD", cwd=inst.DEFAULT_ROOT),
                           "dirty": bool(inst_dirty) if inst_dirty is not None else None,
                           "pinned_commit": inst.load_manifest()["instrument"]["psoracle_commit"]},
            "pins": pin_state(root),
            "artifacts_sha256": {rel: (hashlib.sha256((root / rel).read_bytes()).hexdigest()
                                       if (root / rel).is_file() else None) for rel in B2_ARTIFACTS}}


def run_suite(focused: bool = False, root: Path = REPO_ROOT) -> dict:
    """Snapshot, run, snapshot. The start snapshot is what `head_at_run` means."""
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
    if focused:
        cmd += ["-p", FOCUSED_PATTERN]
    start = snapshot(root)
    p = subprocess.run(cmd, cwd=Path(root), capture_output=True, text=True)
    end = snapshot(root)
    return {"executed": True, "argv": cmd, "exit_status": p.returncode,
            "log": p.stdout + p.stderr, "start": start, "end": end}


# ------------------------------------------------------------------ the log contract


RAN_LINE = re.compile(r"Ran (\d+) tests? in (\d+(?:\.\d+)?)s")
RESULT_LINE = re.compile(r"(OK|FAILED)(?: \((.*)\))?")


def parse_log(text) -> dict:
    """A COMPLETE successful summary, or a named reason why it is not one.

    unittest ends a run with exactly one `Ran N tests in X.XXXs` line and then exactly one result
    line. This requires the WHOLE of both, exactly one of each, in that ORDER, with the result
    line last — a prefix match, a later line silently replacing an earlier one, or a result before
    the count are all ways a contradictory log became a proof (the owner's P2 of 2026-09-12)."""
    if not isinstance(text, str):
        return {"ran": None, "result_line": None, "skipped": None, "failures": None, "errors": None,
                "findings": [f"the log is {type(text).__name__}, not text"]}
    lines = text.splitlines()
    ran_at = [(i, m) for i, ln in enumerate(lines) if (m := RAN_LINE.fullmatch(ln.strip()))]
    res_at = [(i, ln.strip()) for i, ln in enumerate(lines) if ln.startswith(("OK", "FAILED"))]
    out: dict = {"ran": None, "result_line": res_at[-1][1] if res_at else None,
                 "skipped": None, "failures": None, "errors": None, "findings": []}
    if len(ran_at) == 1:
        out["ran"] = int(ran_at[0][1].group(1))
        out["duration_s"] = float(ran_at[0][1].group(2))
    elif not ran_at:
        out["findings"].append("the log carries no complete 'Ran N tests in X.XXXs' line")
    else:
        out["findings"].append(f"the log carries {len(ran_at)} complete run summaries: which run is this?")
    if not res_at:
        out["findings"].append("the log carries no OK or FAILED result line")
    elif len(res_at) > 1:
        out["findings"].append(f"the log carries {len(res_at)} result lines "
                               f"({[t for _, t in res_at][:3]}): which result is this?")
    if ran_at and res_at:
        if res_at[0][0] < ran_at[0][0]:
            out["findings"].append("the result line comes before the run summary")
        if res_at[-1][0] != max(i for i, ln in enumerate(lines) if ln.strip()):
            out["findings"].append("the result line is not the last thing the log says")
    if out["result_line"] == "OK":
        out.update(skipped=0, failures=0, errors=0)
    elif out["result_line"] is not None:
        m = RESULT_LINE.fullmatch(out["result_line"])
        counts: dict[str, int] = {}
        if m and m.group(2) is not None:
            for part in m.group(2).split(","):
                c = re.fullmatch(r"\s*([a-z]+)\s*=\s*(\d+)\s*", part)
                if c:
                    counts[c.group(1)] = int(c.group(2))
                else:
                    out["findings"].append(f"the result line carries an unparsed counter {part.strip()!r}")
        elif not m:
            out["findings"].append(f"the result line {out['result_line']!r} is not OK or a counted summary")
        if not out["findings"]:
            out.update(skipped=counts.get("skipped", 0), failures=counts.get("failures", 0),
                       errors=counts.get("errors", 0))
        if out["result_line"].startswith("FAILED"):
            out["findings"].append("the log's own result line says FAILED")
    if any(t.startswith("FAILED") for _, t in res_at):
        out["findings"].append("the log carries a FAILED result line")
    if out["ran"] == 0:
        out["findings"].append("the log records zero tests")
    return out


# ------------------------------------------------------------------ the verdict


def proof_refusals(rep: dict) -> list[str]:
    """Every reason this report is not a clean-tree proof. Empty = it is one. ONE definition,
    here in the tool, so a test that removes a condition fails."""
    out: list[str] = []
    run = rep["run"]
    if not run.get("executed"):
        out.append("the suite was not executed by this tool: a reconstructed report is not a proof")
    log = rep["log"]
    out += list(log["findings"])
    if log["result_line"] != "OK":
        out.append(f"the result line is {log['result_line']!r}, not exactly 'OK'")
    if not isinstance(log["ran"], int) or log["ran"] <= 0:
        out.append(f"the log records {log['ran']!r} tests, not a positive count")
    for k in ("skipped", "failures", "errors"):
        if log[k] != 0:
            out.append(f"{k} is {log[k]!r}, not zero")
    if run.get("exit_status") != 0:
        out.append(f"the suite exited {run.get('exit_status')!r}, not zero")
    start, end = run.get("start"), run.get("end")
    if not isinstance(start, dict) or not isinstance(end, dict):
        out.append("the run carries no start and end snapshots")
        return out
    for name, snap in (("start", start), ("end", end)):
        if snap.get("worktree_dirty") is not False:
            out.append(f"the worktree was {snap.get('worktree_dirty')!r} at the {name} of the run")
        if snap.get("head") is None:
            out.append(f"no HEAD was observed at the {name} of the run")
        # the nested blocks' SHAPES, before anything reads a field out of them
        i = snap.get("instrument")
        if not isinstance(i, dict):
            out.append(f"the {name} snapshot's instrument is {type(i).__name__}, not an object")
        else:
            if i.get("head") != i.get("pinned_commit"):
                out.append(f"the instrument was at {i.get('head')!r} at the {name}, not its pinned commit")
            if i.get("dirty") is not False:
                out.append(f"the instrument was {i.get('dirty')!r} at the {name} of the run")
        pins = snap.get("pins")
        if not isinstance(pins, dict):
            out.append(f"the {name} snapshot's pins is {type(pins).__name__}, not an object")
        elif pins.get("pins_verified") is not True:
            out.append(f"the pinned surface did not verify at the {name}: {pins.get('pins_refusal')}")
        if not isinstance(snap.get("artifacts_sha256"), dict):
            out.append(f"the {name} snapshot's artifacts_sha256 is "
                       f"{type(snap.get('artifacts_sha256')).__name__}, not an object")
    if start.get("head") != end.get("head"):
        out.append(f"HEAD moved during the run: {start.get('head')} -> {end.get('head')}")
    if start.get("root") != end.get("root"):
        out.append("the repository root changed during the run")
    a0, a1 = start.get("artifacts_sha256"), end.get("artifacts_sha256")
    if isinstance(a0, dict) and isinstance(a1, dict) and a0 != a1:
        moved = sorted(k for k, v in a0.items() if a1.get(k) != v)
        out.append(f"pinned artifacts changed during the run: {moved[:4]}")
    return out


def build(run: dict, focused: bool = False) -> dict:
    # Type before use: a `run` of the wrong shape is a named, never-a-proof report, not an
    # AttributeError. (A two-tuple is the pre-2.0.0 `(exit_status, log)` pair: it carries no
    # snapshots, so it can describe a run but never establish one.)
    if isinstance(run, tuple) and len(run) == 2:
        run = {"executed": False, "argv": None, "exit_status": run[0], "log": run[1],
               "start": None, "end": None, "shape": "a pre-2.0.0 (exit_status, log) pair"}
    elif not isinstance(run, dict):
        run = {"executed": False, "argv": None, "exit_status": None, "log": "",
               "start": None, "end": None, "shape": f"{type(run).__name__}, not a run record"}
    # ONE log value, used for both parsing and hashing: they parsed different things before.
    log_text = run.get("log")
    log = parse_log(log_text)
    if not isinstance(log_text, str):
        log_text = ""
    start = run.get("start") if isinstance(run.get("start"), dict) else {}
    rep = {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "package": "B2 v0.3",
           "at": time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()),
           "scope": "focused (test_b[23]*)" if focused else "whole suite",
           "run": {k: run.get(k) for k in ("executed", "argv", "exit_status", "start", "end", "shape")},
           "log": log, "log_sha256": hashlib.sha256(log_text.encode()).hexdigest(),
           "exit_status": run.get("exit_status"), "ran": log["ran"], "result_line": log["result_line"],
           "skipped": log["skipped"], "failures": log["failures"], "errors": log["errors"],
           "host": os.uname().nodename, "user": os.environ.get("USER") or str(os.getuid()),
           "head_at_run": start.get("head"), "worktree_dirty": start.get("worktree_dirty"),
           "instrument": start.get("instrument"), "pins": start.get("pins"),
           "artifacts_sha256": start.get("artifacts_sha256"),
           "note": ("head_at_run and every other provenance field are the START snapshot, taken before the "
                    "suite ran; the end snapshot is in run.end and must agree with it. The commit that "
                    "includes this report is necessarily later than head_at_run.")}
    rep["proof_refusals"] = proof_refusals(rep)
    rep["clean_tree_proof"] = not rep["proof_refusals"]
    return rep


# ------------------------------------------------------------------ the command line


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "evidence/b2/tests")
    ap.add_argument("--focused", action="store_true",
                    help=f"run only {FOCUSED_PATTERN} instead of the whole suite (recorded in the report)")
    ap.add_argument("--no-run", action="store_true",
                    help="build a REPORT (never a proof) from --log and --exit-status")
    ap.add_argument("--log", type=Path, default=None)
    ap.add_argument("--exit-status", type=int, default=None)
    a = ap.parse_args(argv)
    try:
        if a.no_run:
            if a.log is None or a.exit_status is None:
                raise ReportIOError("--no-run needs --log and --exit-status")
            try:
                text = a.log.read_text()
            except OSError as exc:
                raise ReportIOError(f"the log could not be read: {exc}") from None
            run = {"executed": False, "argv": None, "exit_status": a.exit_status, "log": text,
                   "start": None, "end": None}
        else:
            run = run_suite(a.focused)
        rep = build(run, focused=a.focused)
        try:
            a.out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ReportIOError(f"the output directory could not be created: {exc}") from None
        out = a.out_dir / f"test_report_{rep['at']}.json"
        tmp = out.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n")
            os.replace(tmp, out)
        except OSError as exc:
            raise ReportIOError(f"the report did not land: {exc}") from None
    except ReportIOError as exc:
        print(f"EXIT 3: {exc}", file=sys.stderr)
        return 3
    print(f"{rep['result_line']}  ran {rep['ran']} skipped {rep['skipped']} "
          f"dirty {rep['worktree_dirty']} clean_tree_proof {rep['clean_tree_proof']}"
          + ("" if rep["clean_tree_proof"] else f"  ({len(rep['proof_refusals'])} refusals: "
                                                f"{rep['proof_refusals'][0]})")
          + f"\nreport: {out}")
    return rep["exit_status"] if isinstance(rep["exit_status"], int) else 3


if __name__ == "__main__":
    sys.exit(main())

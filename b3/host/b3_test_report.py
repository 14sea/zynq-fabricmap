#!/usr/bin/env python3
"""B3 lifecycle 2 — the clean-tree test report, FAIL-CLOSED (B2's `b2_test_report.py` discipline, for the
B3 package; standalone — it runs B2's suite but depends on no B2 tool; preregistration v0.3.1 §8;
architecture v0.3 §6; the owner's authorisation and scope of 2026-09-27).

    b3_test_report.py [--out-dir evidence/b3/tests]

There is no --no-run, no --focused, no --log: a report is built ONLY from runs this tool executed and
observed, and every report runs the whole of both start directories and the removal control. A clean-tree
proof cannot be reconstructed from a log this tool did not run.

THREE runs, fixed, in this order, between ONE start snapshot and ONE end snapshot:

  b2_tree      python3 -B -m unittest discover -s tests            (cwd: the repository)
  b3_tree      python3 -B -m unittest discover -v -s b3/tests      (cwd: the repository)
  b3_removal   the same B3 command, cwd: a SYMLINK-SHADOW tree OUTSIDE the repository — every entry of the
               repository linked back, b3/ rebuilt with every entry linked back, b3/tests rebuilt with every
               test file linked back EXCEPT test_b3_sentinel.py — so discovery there lists one test fewer and
               nothing else differs (the audit's ruling: a copy of b3/ elsewhere breaks `parents[2]`, and an
               import failure is then counted as a test; a shadow is the same tree minus one name).

A report is a CLEAN-TREE PROOF only when EVERY one of these holds, and `proof_refusals` names each one that
did not (ONE definition, in the tool):

  * all three runs were EXECUTED BY THIS TOOL;
  * each run's log is a COMPLETE SUCCESSFUL summary under B2's strict contract — exactly one whole
    `Ran N tests in X.XXXs` line with N > 0, then exactly one result line that is exactly `OK` and is the last
    thing the log says — and each run exited 0 with zero skips / failures / errors;
  * the B3 verbose listing names the discovery sentinel exactly once and lists exactly N tests; the removal
    run's listing does not name it, lists exactly N − 1, and `Ran N − 1`;
  * the sentinel file was in the tree, the shadow was built outside the repository and removed after the run,
    the B2 and B3 runs ran in the snapshotted root and the removal run in that shadow, and the removal listing is
    EXACTLY the B3 listing minus the sentinel (membership and order, not merely the count);
  * the start and end snapshots AGREE — the same HEAD and root, both worktrees clean, the instrument at its
    pinned commit and clean in both, the pinned surface's path → digest map identical in both, every required
    artifact present in both with the same digest;
  * the pinned surface VERIFIED at both ends in the only binding that counts: the B3 pin table present, the B3
    manifest present and read through `b3_manifest.read_manifest` (the lifecycle's shared lock and its
    unresolved-transaction refusal), and `b3_pins.verify(manifest, root=root)` passing. Without the table the
    snapshot is `unbound_snapshot`; with the table and no manifest it is `table_self_bound` — a DIAGNOSTIC
    (the table held to its own bytes) recorded as such; neither is ever `pins_verified`, so no report is a
    proof before the pin table and S0 exist. That is by design: the first proof comes after them.

The snapshot (`snapshot`) is everything outside the logs that the verdict depends on, at one instant: HEAD,
the worktree's cleanliness, the instrument's commit and cleanliness against its pin, the pinned surface as
`b3_pins.snapshot` gives it (the sorted path → digest map, its count, one canonical aggregate digest, or the
refusal it raised), the binding mode above, and every required artifact's digest (the B3 manifest and table,
the preregistration, the architecture, the lifecycle-2 gate report and its two raw files, the plan and
prediction, B3Q's plan and prediction, the build evidence and the image binary, the seven frozen inputs of
`b3_manifest.FROZEN_INPUTS`, the B1 manifest and its carrier bitstream). Every file is read through
`b3_pins.read_regular` — never by name alone.

Exit: 0 when all three runs exited 0 (a report that is not a proof still exits 0 — the refusals are in the
report); otherwise the first non-zero run status; **3** for an I/O failure at this tool's boundary (the shadow,
the output directory, the report — which is published atomically and never over an existing file) and for an
implementation error (INTERNAL ERROR, with its traceback).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (REPO_ROOT / "host", REPO_ROOT / "b3/host"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import b3_manifest as bman  # noqa: E402
import b3_pins as bp  # noqa: E402
import b3_plan as pl  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

SCHEMA = "b3_test_report"
SCHEMA_VERSION = "1.0.0"
PACKAGE = "B3 lifecycle 2"
OUT_DIR_REL = "evidence/b3/tests"
B2_START, B3_START = "tests", "b3/tests"
SENTINEL_FILE = "test_b3_sentinel.py"
SENTINEL_ID = "test_b3_sentinel.Sentinel.test_b3_discovery_sentinel"
SUITES = ("b2_tree", "b3_tree", "b3_removal")
ARCHITECTURE_REL = "docs/b3_architecture.md"
GATE_RAW_RELS = ("evidence/b3/gate_2/raw_F1.json", "evidence/b3/gate_2/raw_F2.json")
B1_CARRIER_REL = "builds/b1/b1.bit"
# Every artifact the formal stages require; each must be present, and unchanged across the run, for a proof.
REQUIRED_ARTIFACTS = tuple(dict.fromkeys((
    bman.MANIFEST_REL, bman.PIN_TABLE_REL, bman.PREREG_REL, ARCHITECTURE_REL,
    bman.GATE_REL, *GATE_RAW_RELS,
    bman.PLAN_REL, bman.PREDICTION_REL, bman.QUAL_PLAN_REL, bman.QUAL_PREDICTION_REL,
    bman.BUILD_EVIDENCE_REL, bman.IMAGE_REL,
    *bman.FROZEN_INPUTS,
    bman.B1_MANIFEST_REL, B1_CARRIER_REL,
)))
MODES = ("unbound_snapshot", "table_self_bound", "manifest_bound")


class ReportIOError(Exception):
    """An expected I/O failure at this tool's boundary — exit 3, named, never a traceback."""


def suite_argv(name: str) -> list[str]:
    if name == "b2_tree":
        return [sys.executable, "-B", "-m", "unittest", "discover", "-s", B2_START]
    if name in ("b3_tree", "b3_removal"):
        return [sys.executable, "-B", "-m", "unittest", "discover", "-v", "-s", B3_START]
    raise ValueError(name)


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())


def git(*args: str, cwd: Path) -> str | None:
    try:
        p = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    except OSError:
        return None
    return p.stdout.strip() if p.returncode == 0 else None


def canonical_digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# ------------------------------------------------------------------ the snapshot


def pin_state(root: Path) -> dict:
    """The pinned surface NOW — the snapshot and, separately, its binding. `b3_pins.snapshot` is taken
    whatever exists (its refusal recorded); `pins_verified` is True ONLY in `manifest_bound` mode: the table
    present, the manifest present and read through the trusted reader, `b3_pins.verify` passing. A refusal
    the authorities declare is recorded; an implementation error propagates."""
    root = Path(root)
    out: dict = {"table_present": os.path.lexists(root / bp.PIN_TABLE_REL),
                 "manifest_present": os.path.lexists(root / bman.MANIFEST_REL),
                 "mode": None, "snapshot": None, "snapshot_refusal": None,
                 "pins_verified": False, "pins_refusal": None, "diagnostic": None,
                 "files_verified": None, "pins_sha256": None}
    try:
        digests, _ = bp.snapshot(root)
        out["snapshot"] = {"file_count": len(digests), "files": dict(sorted(digests.items())),
                           "digest": canonical_digest(dict(sorted(digests.items())))}
    except bp.PinRefusal as exc:
        out["snapshot_refusal"] = str(exc)
    if not out["table_present"]:
        out["mode"] = "unbound_snapshot"
        out["pins_refusal"] = f"unbound_snapshot: {bp.PIN_TABLE_REL} does not exist — the snapshot is bound to nothing (never a proof)"
        return out
    if not out["manifest_present"]:
        out["mode"] = "table_self_bound"
        try:
            data, _ = bp.read_regular(root / bp.PIN_TABLE_REL, bp.PIN_TABLE_REL)
            self_manifest = {"instrument_pins": {"path": bp.PIN_TABLE_REL, "sha256": hashlib.sha256(data).hexdigest()}}
            res = bp.verify(self_manifest, root=root)
            out["diagnostic"] = {"verified": True, "refusal": None, "bound_to": "the table's own bytes", **res}
        except bp.PinRefusal as exc:
            out["diagnostic"] = {"verified": False, "refusal": str(exc), "bound_to": "the table's own bytes"}
        out["pins_refusal"] = (f"table_self_bound: {bman.MANIFEST_REL} does not exist — the table is held to its own bytes only, "
                               f"a diagnostic (never a proof)")
        return out
    out["mode"] = "manifest_bound"
    try:
        manifest = json.loads(bman.read_manifest(root / bman.MANIFEST_REL).decode("utf-8"))
    except bman.Refusal as exc:
        out["pins_refusal"] = f"manifest: {exc}"
        return out
    except (ValueError, UnicodeDecodeError) as exc:
        out["pins_refusal"] = f"manifest: {bman.MANIFEST_REL} is not readable JSON: {exc}"
        return out
    except OSError as exc:                       # a directory, unreadable, …: an input condition, named
        out["pins_refusal"] = f"manifest: {bman.MANIFEST_REL} cannot be read: {exc.strerror or exc}"
        return out
    try:
        res = bp.verify(manifest, root=root)
    except bp.PinRefusal as exc:
        out["pins_refusal"] = f"instrument pins: {exc}"
        return out
    out.update(pins_verified=True, files_verified=res["files_verified"], pins_sha256=res["pins_sha256"])
    return out


def artifact_digests(root: Path) -> tuple[dict, dict]:
    """{rel: sha256 | None (absent)} for every required artifact, read through the stable reader, and
    {rel: refusal} for the ones that are present but not a readable regular file."""
    root = Path(root)
    digests: dict = {}
    refusals: dict = {}
    for rel in REQUIRED_ARTIFACTS:
        if not os.path.lexists(root / rel):
            digests[rel] = None
            continue
        try:
            data, _ = bp.read_regular(root / rel, rel)
            digests[rel] = hashlib.sha256(data).hexdigest()
        except bp.PinRefusal as exc:
            digests[rel] = None
            refusals[rel] = str(exc)
    return digests, refusals


def b1_carrier_named(root: Path) -> str | None:
    """The carrier bitstream path the B1 manifest names, or None when it cannot be read as such."""
    try:
        data, _ = bp.read_regular(Path(root) / bman.B1_MANIFEST_REL, bman.B1_MANIFEST_REL)
        doc = json.loads(data.decode("utf-8"))
    except (bp.PinRefusal, ValueError, UnicodeDecodeError):
        return None
    car = doc.get("carrier") if isinstance(doc, dict) else None
    named = car.get("bitstream") if isinstance(car, dict) else None
    return named if isinstance(named, str) else None


def snapshot(root: Path = REPO_ROOT) -> dict:
    """Everything outside the logs that the verdict depends on, observed at ONE instant."""
    root = Path(root)
    dirty = git("status", "--porcelain", cwd=root)
    inst_root = Path(inst.DEFAULT_ROOT)
    inst_dirty = git("status", "--porcelain", cwd=inst_root)
    digests, refusals = artifact_digests(root)
    return {"at": utc_now(), "root": str(root),
            "head": git("rev-parse", "HEAD", cwd=root),
            "worktree_dirty": bool(dirty) if dirty is not None else None,
            "instrument": {"root": str(inst_root), "head": git("rev-parse", "HEAD", cwd=inst_root),
                           "dirty": bool(inst_dirty) if inst_dirty is not None else None,
                           "pinned_commit": pl.INSTRUMENT_COMMIT},
            "pins": pin_state(root),
            "artifacts_sha256": digests, "artifacts_refusals": refusals,
            "b1_carrier": {"expected": B1_CARRIER_REL, "named": b1_carrier_named(root)}}


# ------------------------------------------------------------------ the runs and the shadow


def build_shadow(root: Path, shadow: Path) -> dict:
    """The symlink-shadow tree: `shadow` (an existing, empty directory OUTSIDE `root`) gets every entry of
    `root` linked back, except b3/, which is rebuilt with every entry linked back, except b3/tests, which is
    rebuilt with every regular test file linked back EXCEPT the sentinel. Returns what was linked and whether
    the sentinel was there to remove."""
    root, shadow = Path(root), Path(shadow)
    if shadow.resolve() == root.resolve() or shadow.resolve().is_relative_to(root.resolve()):
        raise ReportIOError(f"the shadow {shadow} is inside the repository {root}: the removal control must run outside it")
    try:
        if any(shadow.iterdir()):
            raise ReportIOError(f"the shadow directory {shadow} is not empty")
        for entry in sorted(root.iterdir()):
            if entry.name != "b3":
                os.symlink(entry, shadow / entry.name)
        (shadow / "b3").mkdir()
        for entry in sorted((root / "b3").iterdir()):
            if entry.name != "tests":
                os.symlink(entry, shadow / "b3" / entry.name)
        (shadow / B3_START).mkdir()
        linked, sentinel_in_tree = [], False
        for entry in sorted((root / B3_START).iterdir()):
            if entry.name == "__pycache__" or entry.name.endswith(".pyc"):
                continue
            if entry.name == SENTINEL_FILE:
                sentinel_in_tree = True
                continue
            os.symlink(entry, shadow / B3_START / entry.name)
            linked.append(entry.name)
    except OSError as exc:
        raise ReportIOError(f"the shadow could not be built: {exc}") from None
    return {"root": str(shadow), "removed": SENTINEL_FILE, "sentinel_in_tree": sentinel_in_tree, "tests_linked": linked}


def run_one(name: str, cwd: Path, runner=subprocess.run) -> dict:
    argv = suite_argv(name)
    started = utc_now()
    t0 = time.monotonic()
    p = runner(argv, cwd=str(cwd), capture_output=True, text=True)
    log = (p.stdout or "") + (p.stderr or "")
    return {"name": name, "argv": argv, "cwd": str(cwd), "started_at": started, "wall_s": round(time.monotonic() - t0, 3),
            "exit_status": p.returncode, "log": log, "log_sha256": hashlib.sha256(log.encode() if isinstance(log, str) else b"").hexdigest()}


def run_suites(root: Path = REPO_ROOT, runner=subprocess.run, shadow_parent: Path | None = None) -> dict:
    """Snapshot; b2_tree; b3_tree; the shadow built, b3_removal run in it, the shadow removed; snapshot."""
    root = Path(root)
    start = snapshot(root)
    suites = {"b2_tree": run_one("b2_tree", root, runner), "b3_tree": run_one("b3_tree", root, runner)}
    try:
        shadow_dir = Path(tempfile.mkdtemp(prefix="b3_removal_control_", dir=None if shadow_parent is None else str(shadow_parent)))
    except OSError as exc:
        raise ReportIOError(f"no directory for the shadow: {exc}") from None
    try:
        shadow = build_shadow(root, shadow_dir)
        suites["b3_removal"] = run_one("b3_removal", shadow_dir, runner)
    except BaseException:
        shutil.rmtree(shadow_dir, ignore_errors=True)        # best effort under an exception already in flight
        raise
    try:
        shutil.rmtree(shadow_dir)
    except OSError as exc:                                   # the owner's P2 on 5b12dd2: never swallowed
        raise ReportIOError(f"the shadow {shadow_dir} could not be removed after the run: {exc}") from None
    shadow["removed_after"] = not os.path.lexists(shadow_dir)
    if not shadow["removed_after"]:
        raise ReportIOError(f"the shadow {shadow_dir} still exists after its removal")
    end = snapshot(root)
    return {"executed": True, "start": start, "end": end, "suites": suites, "shadow": shadow}


# ------------------------------------------------------------------ the log contract (B2's, verbatim in meaning)


RAN_LINE = re.compile(r"Ran (\d+) tests? in (\d+(?:\.\d+)?)s")
RESULT_LINE = re.compile(r"(OK|FAILED)(?: \((.*)\))?")
# A listed test is its HEADER at column 0: `name (module.Class.name)`, followed on the same line by ` ... <status>`
# (no docstring), by ` ... ` alone (a subTest failure continues on indented lines), or by nothing (a docstring: its
# first line follows on the next line, ending in ` ... <status>`). The name must be the id's last component, which
# no docstring line satisfies; indented subTest lines are not at column 0. Measured on this interpreter (3.12).
LISTED_LINE = re.compile(r"(\S+) \(([^()\s]+\.[^()\s]+)\)(?: \.\.\.(?: .*)?)?")


def parse_log(text) -> dict:
    """A COMPLETE successful summary, or a named reason why it is not one: the WHOLE of exactly one `Ran N
    tests in X.XXXs` line and exactly one result line, in that order, the result line last."""
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
        out["findings"].append(f"the log carries {len(res_at)} result lines ({[t for _, t in res_at][:3]}): which result is this?")
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
            out.update(skipped=counts.get("skipped", 0), failures=counts.get("failures", 0), errors=counts.get("errors", 0))
        if out["result_line"].startswith("FAILED"):
            out["findings"].append("the log's own result line says FAILED")
    if any(t.startswith("FAILED") for _, t in res_at):
        out["findings"].append("the log carries a FAILED result line")
    if out["ran"] == 0:
        out["findings"].append("the log records zero tests")
    return out


def listed_tests(text) -> list[str]:
    """The test ids a verbose (-v) run listed, in order — from each test's header line at column 0, whether the
    status follows on that line (`name (id) ... ok`) or, for a test with a docstring, on the next (`name (id)` then
    `<first docstring line> ... ok`) — the owner's P1 on 5b12dd2: the one-line form alone missed every docstring
    test (363 of 454 in the real run)."""
    if not isinstance(text, str):
        return []
    out = []
    for ln in text.splitlines():
        # column 0 is enforced by the pattern itself: `\S+` at position 0 under fullmatch admits no leading
        # whitespace, so an indented subTest or traceback line never matches (a separate guard would be dead code)
        m = LISTED_LINE.fullmatch(ln.rstrip())
        if m and m.group(1) == m.group(2).rsplit(".", 1)[1]:
            out.append(m.group(2))
    return out


# ------------------------------------------------------------------ the verdict


def proof_refusals(rep: dict) -> list[str]:
    """Every reason this report is not a clean-tree proof. Empty = it is one. ONE definition, here."""
    out: list[str] = []
    run = rep["run"]
    if run.get("executed") is not True:
        out.append("the suites were not executed by this tool: a reconstructed report is not a proof")
    suites = rep["suites"]
    for name in SUITES:
        s = suites.get(name)
        if not isinstance(s, dict):
            out.append(f"{name}: no run record")
            continue
        log = s["log"]
        out += [f"{name}: {f}" for f in log["findings"]]
        if log["result_line"] != "OK":
            out.append(f"{name}: the result line is {log['result_line']!r}, not exactly 'OK'")
        # (a missing or zero `Ran N` is already among parse_log's findings — a second check here would be dead code)
        for k in ("skipped", "failures", "errors"):
            if log[k] != 0:
                out.append(f"{name}: {k} is {log[k]!r}, not zero")
        if s.get("exit_status") != 0:
            out.append(f"{name}: the run exited {s.get('exit_status')!r}, not zero")
        if s.get("argv") != suite_argv(name):
            out.append(f"{name}: the command run was {s.get('argv')!r}, not this tool's {suite_argv(name)!r}")
    # the removal control: the membership, not merely the count (the owner's P1 on 5b12dd2)
    b3, rm = suites.get("b3_tree"), suites.get("b3_removal")
    if isinstance(b3, dict) and isinstance(rm, dict):
        b3_listed, rm_listed = b3.get("listed") or [], rm.get("listed") or []
        if b3_listed.count(SENTINEL_ID) != 1:
            out.append(f"b3_tree: the verbose listing names the sentinel {b3_listed.count(SENTINEL_ID)} times, not exactly once")
        if isinstance(b3["log"]["ran"], int) and len(b3_listed) != b3["log"]["ran"]:
            out.append(f"b3_tree: the verbose listing has {len(b3_listed)} tests but the summary ran {b3['log']['ran']}")
        if SENTINEL_ID in rm_listed:
            out.append("b3_removal: the verbose listing still names the sentinel — it was not removed")
        if isinstance(rm["log"]["ran"], int) and len(rm_listed) != rm["log"]["ran"]:
            out.append(f"b3_removal: the verbose listing has {len(rm_listed)} tests but the summary ran {rm['log']['ran']}")
        if isinstance(b3["log"]["ran"], int) and isinstance(rm["log"]["ran"], int) and rm["log"]["ran"] != b3["log"]["ran"] - 1:
            out.append(f"b3_removal: ran {rm['log']['ran']}, not exactly one fewer than b3_tree's {b3['log']['ran']}")
        expected = [i for i in b3_listed if i != SENTINEL_ID]
        if rm_listed != expected:
            gone = sorted(set(expected) - set(rm_listed))
            extra = sorted(set(rm_listed) - set(expected))
            out.append("b3_removal: the verbose listing is not b3_tree's listing minus the sentinel"
                       + (f": missing {gone[:3]}" if gone else "") + (f": unexpected {extra[:3]}" if extra else "")
                       + ("" if gone or extra else ": the order differs"))
        if rm.get("cwd") == b3.get("cwd"):
            out.append("b3_removal: ran in the same directory as b3_tree, not in the shadow")
    shadow = run.get("shadow")
    if not isinstance(shadow, dict):
        out.append(f"the shadow record is {type(shadow).__name__}, not an object")
    else:
        if shadow.get("sentinel_in_tree") is not True:
            out.append(f"the sentinel {SENTINEL_FILE} was not in b3/tests: there was nothing to remove")
        if shadow.get("removed") != SENTINEL_FILE:
            out.append(f"the shadow removed {shadow.get('removed')!r}, not {SENTINEL_FILE}")
        if shadow.get("removed_after") is not True:
            out.append(f"the shadow was not removed after the run (removed_after is {shadow.get('removed_after')!r})")
        if isinstance(rm, dict) and rm.get("cwd") != shadow.get("root"):
            out.append("b3_removal did not run in the shadow that was built")
    # the snapshots
    start, end = run.get("start"), run.get("end")
    if not isinstance(start, dict) or not isinstance(end, dict):
        out.append("the run carries no start and end snapshots")
        return out
    for name, snap in (("start", start), ("end", end)):
        if snap.get("worktree_dirty") is not False:
            out.append(f"the worktree was {snap.get('worktree_dirty')!r} at the {name} of the run")
        if snap.get("head") is None:
            out.append(f"no HEAD was observed at the {name} of the run")
        i = snap.get("instrument")
        if not isinstance(i, dict):
            out.append(f"the {name} snapshot's instrument is {type(i).__name__}, not an object")
        else:
            if i.get("head") is None or i.get("head") != i.get("pinned_commit"):
                out.append(f"the instrument was at {i.get('head')!r} at the {name}, not its pinned commit")
            if i.get("dirty") is not False:
                out.append(f"the instrument was {i.get('dirty')!r} at the {name} of the run")
        pins = snap.get("pins")
        if not isinstance(pins, dict):
            out.append(f"the {name} snapshot's pins is {type(pins).__name__}, not an object")
        else:
            if not isinstance(pins.get("snapshot"), dict):
                out.append(f"the pinned surface could not be snapshotted at the {name}: {pins.get('snapshot_refusal')}")
            if pins.get("mode") != "manifest_bound":
                out.append(f"the pinned surface was not bound to the B3 manifest at the {name} ({pins.get('mode')!r}): {pins.get('pins_refusal')}")
            if pins.get("pins_verified") is not True:
                out.append(f"the pinned surface did not verify at the {name}: {pins.get('pins_refusal')}")
        arts = snap.get("artifacts_sha256")
        if not isinstance(arts, dict):
            out.append(f"the {name} snapshot's artifacts_sha256 is {type(arts).__name__}, not an object")
        else:
            missing = [rel for rel in REQUIRED_ARTIFACTS if not isinstance(arts.get(rel), str)]
            if missing:
                out.append(f"required artifacts absent at the {name}: {missing[:6]}" + (f" (+{len(missing) - 6})" if len(missing) > 6 else ""))
        refs = snap.get("artifacts_refusals")
        if isinstance(refs, dict) and refs:
            out.append(f"artifacts refused at the {name}: {dict(list(sorted(refs.items()))[:3])}")
        car = snap.get("b1_carrier")
        if not isinstance(car, dict) or car.get("named") != B1_CARRIER_REL:
            out.append(f"the B1 manifest names {car.get('named') if isinstance(car, dict) else car!r} as its carrier at the {name}, not {B1_CARRIER_REL}")
    if start.get("head") != end.get("head"):
        out.append(f"HEAD moved during the run: {start.get('head')} -> {end.get('head')}")
    if start.get("root") != end.get("root"):
        out.append("the repository root changed during the run")
    # the runs happened in THE tree that was snapshotted, and the removal outside it (the owner's P1 on 5b12dd2)
    root = start.get("root")
    if not isinstance(root, str) or not root:
        out.append(f"the start snapshot names no root ({root!r})")
    else:
        for name in ("b2_tree", "b3_tree"):
            s = suites.get(name)
            if isinstance(s, dict) and s.get("cwd") != root:
                out.append(f"{name}: ran in {s.get('cwd')!r}, not in the snapshotted root {root!r}")
        if isinstance(shadow, dict):
            sr = shadow.get("root")
            if not isinstance(sr, str) or not sr:
                out.append(f"the shadow names no root ({sr!r})")
            elif sr == root or sr.startswith(root.rstrip("/") + "/") or root.startswith(sr.rstrip("/") + "/"):
                out.append(f"the shadow {sr!r} is not outside the repository {root!r}")
    a0, a1 = start.get("artifacts_sha256"), end.get("artifacts_sha256")
    if isinstance(a0, dict) and isinstance(a1, dict) and a0 != a1:
        moved = sorted(k for k in set(a0) | set(a1) if a0.get(k) != a1.get(k))
        out.append(f"required artifacts changed during the run: {moved[:4]}")
    p0, p1 = start.get("pins"), end.get("pins")
    if isinstance(p0, dict) and isinstance(p1, dict):
        s0, s1 = p0.get("snapshot"), p1.get("snapshot")
        if isinstance(s0, dict) and isinstance(s1, dict) and s0.get("files") != s1.get("files"):
            f0, f1 = s0.get("files") or {}, s1.get("files") or {}
            moved = sorted(k for k in set(f0) | set(f1) if f0.get(k) != f1.get(k))
            out.append(f"the pinned surface changed during the run: {moved[:4]}")
    return out


def build(run) -> dict:
    """Type before use: a run record of the wrong shape is a named, never-a-proof report, not an exception."""
    if not isinstance(run, dict):
        run = {"executed": False, "start": None, "end": None, "suites": {}, "shadow": None,
               "shape": f"{type(run).__name__}, not a run record"}
    suites_in = run.get("suites") if isinstance(run.get("suites"), dict) else {}
    suites: dict = {}
    for name in SUITES:
        s = suites_in.get(name)
        if not isinstance(s, dict):
            continue
        log_text = s.get("log")
        parsed = parse_log(log_text)
        text = log_text if isinstance(log_text, str) else ""
        suites[name] = {"argv": s.get("argv"), "cwd": s.get("cwd"), "started_at": s.get("started_at"), "wall_s": s.get("wall_s"),
                        "exit_status": s.get("exit_status"), "log_text": text,
                        "log_sha256": hashlib.sha256(text.encode()).hexdigest(), "log": parsed,
                        "listed": listed_tests(log_text) if name != "b2_tree" else None}
    start = run.get("start") if isinstance(run.get("start"), dict) else {}
    rep = {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "package": PACKAGE, "at": utc_now(),
           "commands": {name: suite_argv(name) for name in SUITES},
           "run": {k: run.get(k) for k in ("executed", "start", "end", "shadow", "shape")},
           "suites": suites,
           "ran": {name: (suites[name]["log"]["ran"] if name in suites else None) for name in SUITES},
           "exit_status": {name: (suites[name]["exit_status"] if name in suites else None) for name in SUITES},
           "removal_control": {"b3_ran": suites.get("b3_tree", {}).get("log", {}).get("ran"),
                               "removal_ran": suites.get("b3_removal", {}).get("log", {}).get("ran"),
                               "sentinel_in_b3_listing": (suites.get("b3_tree", {}).get("listed") or []).count(SENTINEL_ID),
                               "sentinel_in_removal_listing": (suites.get("b3_removal", {}).get("listed") or []).count(SENTINEL_ID)},
           "host": os.uname().nodename, "user": os.environ.get("USER") or str(os.getuid()),
           "head_at_run": start.get("head"), "worktree_dirty": start.get("worktree_dirty"),
           "instrument": start.get("instrument"), "pins": start.get("pins"),
           "artifacts_sha256": start.get("artifacts_sha256"),
           "note": ("head_at_run and every other provenance field are the START snapshot, taken before the first run; the end "
                    "snapshot is in run.end and must agree with it. The commit that includes this report is necessarily later "
                    "than head_at_run. pins.mode says what the pinned surface was bound to; only manifest_bound can verify.")}
    rep["proof_refusals"] = proof_refusals(rep)
    rep["clean_tree_proof"] = not rep["proof_refusals"]
    return rep


# ------------------------------------------------------------------ publishing and the command line


def publish_once(rep: dict, out: Path) -> None:
    """Atomic, no-clobber, and BOUND TO THE INODE THIS TOOL WROTE (the owner's P1 on 3885926: a publish that
    linked the temporary NAME could publish a foreign file swapped in under that name).

    The bytes go to a temporary file beside `out` (O_EXCL, O_NOFOLLOW), are fsync'd, and the descriptor stays
    OPEN. The report is then linked from the descriptor itself — `/proc/self/fd/N`, the inode, never the name —
    so a temporary name deleted or replaced meanwhile cannot be what lands (an inode whose last name is gone is
    refused by the kernel). After the link, the name `out` must be that same regular inode (fstat of the
    descriptor against lstat of the name) and must read back, through the stable reader, to exactly the bytes
    written. Cleanup unlinks the temporary name ONLY while it is still this invocation's inode; anything else
    standing under it is left in place and named. Every I/O failure at this boundary — the descriptor's close
    and the directory's open, fsync and close included (the owner's P3) — is a ReportIOError; when the fsync
    and the close both fail, the fsync is the finding reported."""
    out = Path(out)
    data = (json.dumps(rep, indent=1, sort_keys=True) + "\n").encode()
    want = hashlib.sha256(data).hexdigest()
    tmp = out.parent / f".{out.name}.part-{os.getpid()}"
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o644)
    except OSError as exc:
        raise ReportIOError(f"the report's temporary file could not be created: {exc}") from None
    mine = None
    try:
        dfd = os.open(out.parent, os.O_RDONLY | os.O_CLOEXEC)
    except OSError as exc:
        _close_quiet(fd)
        raise ReportIOError(f"the report's directory could not be opened: {exc}" + _unlink_own(tmp, mine)) from None
    try:
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
            st = os.fstat(fd)
            mine = (st.st_dev, st.st_ino)
        except OSError as exc:
            raise ReportIOError(f"the report's bytes did not land in the temporary file: {exc}" + _unlink_own(tmp, mine)) from None
        try:
            # linkat(AT_FDCWD, "/proc/self/fd/N", dirfd, name, AT_SYMLINK_FOLLOW): the INODE this tool wrote and fsync'd,
            # reached through the descriptor's magic link — never the temporary name. (Python's os.link takes the
            # linkat path, which follows the magic link, only when a dir_fd is given; plain link(2) would not.)
            os.link(f"/proc/self/fd/{fd}", out.name, dst_dir_fd=dfd, follow_symlinks=True)
        except FileExistsError:
            raise ReportIOError(f"the report {out} already exists: a report is never overwritten" + _unlink_own(tmp, mine)) from None
        except OSError as exc:
            raise ReportIOError(f"the report did not land: {exc}" + _unlink_own(tmp, mine)) from None
        try:
            got = os.lstat(out)
        except OSError as exc:
            raise ReportIOError(f"the report {out} was linked but cannot be examined: {exc}" + _unlink_own(tmp, mine)) from None
        if not stat.S_ISREG(got.st_mode) or (got.st_dev, got.st_ino) != mine:
            raise ReportIOError(f"the file at {out} is not the inode this tool wrote and fsync'd: a foreign file stands under the "
                                f"report's name and is left in place (it is not this tool's)" + _unlink_own(tmp, mine))
        try:
            back, _ = bp.read_regular(out, str(out))
        except bp.PinRefusal as exc:
            raise ReportIOError(f"the report {out} landed but does not read back as a regular file: {exc}" + _unlink_own(tmp, mine)) from None
        if hashlib.sha256(back).hexdigest() != want:
            raise ReportIOError(f"the report {out} landed but its bytes are not the bytes this tool wrote" + _unlink_own(tmp, mine))
    except ReportIOError:
        _close_quiet(fd)                                   # the finding above is the one reported
        _close_quiet(dfd)
        raise
    try:
        os.close(fd)
    except OSError as exc:
        _close_quiet(dfd)
        raise ReportIOError(f"the report {out} landed but its descriptor could not be closed: {exc}" + _unlink_own(tmp, mine)) from None
    note = _unlink_own(tmp, mine)
    if note:
        _close_quiet(dfd)
        raise ReportIOError(f"the report {out} landed" + note)
    _sync_dir(out, dfd)


def _close_quiet(fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        pass


def _unlink_own(tmp: Path, mine: tuple | None) -> str:
    """Remove the temporary name ONLY if it still refers to this invocation's inode. Returns "" when it is
    gone or removed, else a note for the caller's finding (never a second exception over the first)."""
    try:
        st = os.lstat(tmp)
    except FileNotFoundError:
        return ""
    except OSError as exc:
        return f"; the temporary name {tmp} cannot be examined: {exc}"
    if mine is None or not stat.S_ISREG(st.st_mode) or (st.st_dev, st.st_ino) != mine:
        return f"; the temporary name {tmp} is no longer this tool's inode (it was swapped) and is left in place"
    try:
        os.unlink(tmp)
    except OSError as exc:
        return f"; the temporary file {tmp} could not be removed: {exc}"
    return ""


def _sync_dir(out: Path, dfd: int) -> None:
    """fsync the report's directory through the descriptor the link was made with, then close it. Each of fsync /
    close is named; fsync's failure is the finding even when the close then fails too (the owner's P3 on 3885926)."""
    sync_error = None
    try:
        os.fsync(dfd)
    except OSError as exc:
        sync_error = exc
    try:
        os.close(dfd)
    except OSError as exc:
        if sync_error is not None:
            raise ReportIOError(f"the report {out} landed but its directory could not be synced: {sync_error} (and its "
                                f"descriptor could not be closed: {exc})") from None
        raise ReportIOError(f"the report {out} landed and its directory was synced, but the directory's descriptor could not be closed: {exc}") from None
    if sync_error is not None:
        raise ReportIOError(f"the report {out} landed but its directory could not be synced: {sync_error}") from None


def parser() -> argparse.ArgumentParser:
    """The ONLY option is where the report lands. No run is skipped, focused, reconstructed or patterned."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", type=Path, default=None, help=f"where the report lands (default: <root>/{OUT_DIR_REL})")
    return ap


def main(argv=None, root: Path = REPO_ROOT, runner=subprocess.run) -> int:
    a = parser().parse_args(argv)
    root = Path(root)
    out_dir = root / OUT_DIR_REL if a.out_dir is None else a.out_dir
    try:
        run = run_suites(root, runner=runner)
        rep = build(run)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ReportIOError(f"the output directory could not be created: {exc}") from None
        out = out_dir / f"test_report_{rep['at']}.json"
        publish_once(rep, out)
    except ReportIOError as exc:
        print(f"EXIT 3: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:                     # noqa: BLE001 — an implementation defect stays visible
        traceback.print_exc()
        print(f"INTERNAL ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    ran = rep["ran"]
    print(f"b2_tree ran {ran['b2_tree']}  b3_tree ran {ran['b3_tree']}  b3_removal ran {ran['b3_removal']}  "
          f"dirty {rep['worktree_dirty']}  pins {rep['pins']['mode'] if isinstance(rep['pins'], dict) else None}  "
          f"clean_tree_proof {rep['clean_tree_proof']}"
          + ("" if rep["clean_tree_proof"] else f"  ({len(rep['proof_refusals'])} refusals: {rep['proof_refusals'][0]})")
          + f"\nreport: {out}")
    for name in SUITES:
        status = rep["exit_status"][name]
        if status != 0:
            return status if isinstance(status, int) and 0 < status < 256 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

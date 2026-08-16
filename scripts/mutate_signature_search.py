#!/usr/bin/env python3
"""Mutation gate for the load-bearing rules of the signature search.

Nineteen mutants, each removing one thing the search is not allowed to do without:

  * a child reads one FAR, because a process is trustworthy for exactly one read;
  * the intended frame is decided before any sweep, because it answers the question alone in
    two cases out of three and a sweep is 5,144 more chances to lose the state;
  * a failed child stops the search where it failed, because a hole in the coverage lets a
    later "not found" quietly mean "not looked at";
  * `validate_index()` refuses an index that holds a failure, on every path including
    `--judge-only`, which does not touch hardware and so has no other check;
  * `validate_index()` re-hashes the capture files and the child logs, because an index is a
    claim and the files are the evidence;
  * what is missing is recomputed from the frozen FAR set, never read from the index, because
    an interrupted run leaves an index that is silent about every frame nobody looked at;
  * a child that raises still lands a failed entry and its log, because the failure mode with
    the least evidence must not be the one that produces none.
  * a resume invalidates the previous invocation's closure before another capture can land;
  * a mismatching end marker reaches disk before the run refuses it;
  * bytes emitted before a timeout survive in the failed child's evidence.
  * a positive control is a whole known non-zero base frame at the same FAR, not merely
    non-zero data;
  * the intended frame's third state cannot bypass the control;
  * `judge_sweep()` itself cannot emit a location verdict without the control.
  * control-only reads exactly the pinned controls and has no location vocabulary;
  * acquisition mode is part of the index contract, in both directions;
  * every successful capture carries CONFIG_STATUS into the index summary.

Each probe asks a module a question about behaviour and runs it to find out. Nothing here
searches for the mutation itself.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
SOURCE = REPO / "scripts/board_signature_search.py"

A20, A21, A22 = 0x00400A20, 0x00400A21, 0x00400A22
CONTROL_FARS = [0x00400B00 + offset for offset in range(16)]
FARS = [A20, A21, A22, *CONTROL_FARS]
PLMARK = "18cc00f0fa537908"
DIGEST = "d" * 64
CONTROL_DIGEST = "c" * 64
ZERO = [0] * 101


def signature(seed: int) -> list[int]:
    words = list(ZERO)
    words[51] = seed
    words[50] = seed ^ 0x19C6
    return words


SIGNATURES = {A20: signature(0x40), A21: signature(0x41)}
BASE = {far: list(ZERO) for far in FARS}
CONTROLS = {far: signature(0x100 + offset) for offset, far in enumerate(CONTROL_FARS)}
BASE.update(CONTROLS)

MUTANTS = {
    # MUTATION ANCHOR judge_read_only: judging is a reading of evidence, never a write to it.
    "judge_only_writes_the_acquisition": [(
        '            print(json.dumps(verdict, indent=2))\n'
        '            print(f"{verdict[\'verdict\']}: {verdict[\'reading\']}")\n'
        '            print("  judged read-only; no file in the acquisition directory was written")\n'
        '            return 0',
        '            _atomic_write(args.out_dir / "verdict.json",\n'
        '                          json.dumps(verdict, indent=2) + "\\n")\n'
        '            print(f"{verdict[\'verdict\']}: {verdict[\'reading\']}")\n'
        '            return 0')],
    # MUTATION ANCHOR one_far: the child must never be handed a second frame to read.
    "two_fars_per_child": [(
        '    argv = [sys.executable, str(CHILD), "--far", f"{far:#010x}", "--out", str(out_path),',
        '    argv = [sys.executable, str(CHILD), "--far", f"{far:#010x}",\n'
        '            "--far", f"{far + 1:#010x}", "--out", str(out_path),')],
    "two_fars_no_guard": [
        ('    argv = [sys.executable, str(CHILD), "--far", f"{far:#010x}", "--out", str(out_path),',
         '    argv = [sys.executable, str(CHILD), "--far", f"{far:#010x}",\n'
         '            "--far", f"{far + 1:#010x}", "--out", str(out_path),'),
        ("    check_child_argv(argv)\n    return argv", "    return argv")],
    # MUTATION ANCHOR a20_first: the first frame's verdict gates the sweep.
    "defer_the_intended_decision": [(
        '    if decision["verdict"] != "WRITE_LANDED_AT_THE_INTENDED_FAR":',
        '    if True:  # mutant: keep reading after the intended frame answered')],
    # MUTATION ANCHOR fail_stops: a recorded failure must never become a skipped frame.
    "skip_failed_child": [(
        '            captures[far] = capture_one(far, out_dir, index, runner)\n'
        '            reads += 1',
        '            try:\n'
        '                captures[far] = capture_one(far, out_dir, index, runner)\n'
        '            except SearchStop:\n'
        '                pass  # mutant: skip the failed FAR and carry on\n'
        '            reads += 1')],
    # MUTATION ANCHOR failed_is_not_coverage: judge-only has no other check.
    "validate_ignores_failed": [(
        '    if failed:\n        raise SearchStop(f"the search holds failed captures and is not coverage: {failed}")',
        '    if failed:\n        pass  # mutant: a failure is treated as coverage')],
    # MUTATION ANCHOR recomputed_coverage: the index may not be asked what it missed.
    "missing_not_attempted_means_complete": [(
        '        _, missing = validate_index(\n'
        '            out_dir, index, digest, plmark, fars, controls, MODE_SIGNATURE_SEARCH)',
        '        missing = index.get("not_attempted", [])  # mutant: believe the index')],
    # MUTATION ANCHOR child_log_digest: the child's own record must be unaltered.
    "ignore_child_log_digest": [(
        '    if _digest_of(path) != entry.get("child_log_sha256"):\n'
        '        raise SearchStop(f"{key}: the child log has changed since it was written")',
        '    pass  # mutant: believe the index about the child log')],
    # MUTATION ANCHOR runner_exception: a raising child must still leave evidence.
    "timeout_leaves_no_failure_evidence": [(
        '    try:\n        result = runner(far, staging)\n    except Exception as raised:',
        '    if True:\n        result = runner(far, staging)\n    if False:\n        raised = None')],
    # MUTATION ANCHOR closure_epoch: a resume may not inherit an older matching end marker.
    "resume_reuses_previous_closure": [(
        '    index.pop("plmark_at_end", None)\n'
        '    _atomic_write(out_dir / "index.json", json.dumps(index, indent=2) + "\\n")',
        '    pass  # mutant: keep the previous invocation\'s closure')],
    # MUTATION ANCHOR mismatch_lands: an observed reboot must reach disk before the refusal.
    "mismatched_end_is_not_persisted": [(
        '    _atomic_write(out_dir / "index.json", json.dumps(index, indent=2) + "\\n")\n'
        '    if index["plmark_at_end"] != plmark:\n'
        '        raise SearchStop(\n'
        '            f"plmark changed from {plmark} to {index[\'plmark_at_end\']}: the board restarted "\n'
        '            "during the acquisition and every later capture is from a different PL")',
        '    if index["plmark_at_end"] != plmark:\n'
        '        raise SearchStop(\n'
        '            f"plmark changed from {plmark} to {index[\'plmark_at_end\']}: the board restarted "\n'
        '            "during the acquisition and every later capture is from a different PL")\n'
        '    _atomic_write(out_dir / "index.json", json.dumps(index, indent=2) + "\\n")')],
    # MUTATION ANCHOR timeout_streams: partial OpenOCD output is failure evidence.
    "timeout_drops_partial_output": [(
        '        partial_stdout = getattr(raised, "stdout", None)\n'
        '        if partial_stdout is None:\n'
        '            partial_stdout = getattr(raised, "output", None)\n'
        '        partial_stderr = getattr(raised, "stderr", None)',
        '        partial_stdout = None  # mutant: discard what OpenOCD emitted before timeout\n'
        '        partial_stderr = None')],
    # MUTATION ANCHOR control_exact: non-zero garbage is not a positive control.
    "any_nonzero_control_passes": [(
        "        exact = words == expected",
        "        exact = any(words)  # mutant: any non-zero garbage validates the instrument")],
    # MUTATION ANCHOR neither_control: a third state is still a location statement.
    "neither_bypasses_control": [(
        '    if decision["verdict"] != "WRITE_LANDED_AT_THE_INTENDED_FAR":',
        '    if decision["verdict"] not in ("WRITE_LANDED_AT_THE_INTENDED_FAR",\n'
        '                                   "INTENDED_FAR_IS_NEITHER"):')],
    # MUTATION ANCHOR sweep_control: callers cannot bypass the live-run ordering.
    "not_found_bypasses_control": [(
        '    if control["verdict"] != "INSTRUMENT_VALID":\n        return control',
        '    if False:  # mutant: sweep verdicts need no valid instrument\n        return control')],
    # MUTATION ANCHOR control_read_set: this mode has exactly sixteen possible children.
    "control_only_widens_read_set": [(
        '    for far in controls:\n        if far in captures:',
        '    for far in [*controls, INTENDED_FAR]:\n        if far in captures:')],
    # MUTATION ANCHOR control_vocabulary: no location result exists in this mode.
    "control_only_emits_location": [(
        '    verdict = judge_positive_controls(captures, controls)\n'
        '    require_control_only_verdict(verdict)\n'
        '    index["not_attempted"] = [f"{far:#010x}" for far in controls if far not in captures]',
        '    verdict = {"verdict": "NOT_FOUND_COMPLETE", "reading": "mutant"}\n'
        '    index["not_attempted"] = [f"{far:#010x}" for far in controls if far not in captures]')],
    # MUTATION ANCHOR mode_binding: matching files from the other mode are still inadmissible.
    "control_index_is_a_search_index": [(
        '    if index.get("mode") != mode:\n'
        '        raise SearchStop(\n'
        '            f"the index mode is {index.get(\'mode\')!r}, not {mode!r}; control-only and "\n'
        '            "location-search evidence are not interchangeable")',
        '    pass  # mutant: the two acquisition modes share an index')],
    # MUTATION ANCHOR status_summary: the classifier candidate belongs in the index.
    "drop_config_status_summary": [(
        '        "config_status": config_status,',
        '        # mutant: CONFIG_STATUS is discarded from the summary')],
    # MUTATION ANCHOR capture_digest: an index is a claim, the capture file is the evidence.
    "validate_trusts_capture_file": [(
        '        if _digest_of(path) != entry.get("capture_sha256"):\n'
        '            raise SearchStop(f"{key}: the capture file has changed since it was written")',
        '        pass  # mutant: believe the index about the file')],
}


def load(text: str, name: str):
    path = Path(tempfile.mkdtemp()) / f"mutant_{name}.py"
    path.write_text(text, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"mutant_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def capture_for(module, far: int, words: list[int], **override) -> dict:
    body = b"".join(word.to_bytes(4, "big") for word in words)
    capture = {"tool": module.CHILD_TOOL_VERSION, "verdict": "READ", "idcode": module.IDCODE,
               "config_status": "0x46107ffc",
               "frames": {f"{far:#010x}": {
                   "frame": [f"{word:08x}" for word in words],
                   "pad_frame": [f"{word:08x}" for word in ZERO],
                   "frame_sha256": hashlib.sha256(body).hexdigest()}}}
    capture.update(override)
    return capture


def runner_for(module, content: dict, asked: list[int], fail_on: int | None = None):
    def runner(far: int, out_path: Path) -> dict:
        asked.append(far)
        argv = module.child_argv(far, out_path)
        if far == fail_on:
            return {"returncode": 1, "argv": argv, "stdout": "", "stderr": "boom"}
        out_path.write_text(json.dumps(capture_for(
            module, far, content.get(far, CONTROLS.get(far, ZERO)))),
                            encoding="utf-8")
        return {"returncode": 0, "argv": argv, "stdout": "", "stderr": ""}
    return runner


def probe_argv(module) -> tuple[bool, str]:
    """Every argv a child could receive must name exactly one FAR, or be refused."""
    try:
        argv = module.child_argv(A20, Path("/tmp/mutant.json"))
    except module.SearchStop as refused:
        return True, f"the module refused to build it: {refused}"
    count = argv.count("--far")
    if count != 1:
        return True, f"it would hand a child {count} FARs with nothing to stop it"
    return False, "one FAR per child"


def probe_intended_first(module) -> tuple[bool, str]:
    """When the first frame holds the candidate, nothing else may be read."""
    asked: list[int] = []
    with tempfile.TemporaryDirectory() as name:
        module.run(Path(name), PLMARK, SIGNATURES, BASE, FARS, DIGEST,
                   CONTROLS,
                   runner=runner_for(module, {A20: SIGNATURES[A20]}, asked),
                   plmark_reader=lambda port: PLMARK)
    if asked != [A20]:
        return True, (f"it read {len(asked)} frames after the first had already answered: "
                      f"{[f'{far:#010x}' for far in asked]}")
    return False, "the first frame decided it"


def probe_failure_stops(module) -> tuple[bool, str]:
    """A failed child must stop the search there, not merely spoil the verdict later."""
    asked: list[int] = []
    with tempfile.TemporaryDirectory() as name:
        try:
            module.run(Path(name), PLMARK, SIGNATURES, BASE, FARS, DIGEST,
                       CONTROLS,
                       runner=runner_for(module, {}, asked, fail_on=A21),
                       plmark_reader=lambda port: PLMARK)
        except module.SearchStop:
            pass
    if asked != [A20, CONTROL_FARS[0], A21]:
        return True, (f"it kept reading after a failed child: "
                      f"{[f'{far:#010x}' for far in asked]}")
    return False, "the failure stopped the search at the frame that failed"


def _one_capture(module, tmp: Path) -> dict:
    """A minimal index with one good capture, written the way the module writes them."""
    asked: list[int] = []
    module.run(tmp, PLMARK, SIGNATURES, BASE, FARS, DIGEST, CONTROLS,
               runner=runner_for(module, {A20: SIGNATURES[A20]}, asked),
               plmark_reader=lambda port: PLMARK)
    return json.loads((tmp / "index.json").read_text("utf-8"))


def probe_failed_is_not_coverage(module) -> tuple[bool, str]:
    """`validate_index` must refuse an index holding a failure — judge-only relies on it."""
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        index = _one_capture(module, tmp)
        index["entries"][f"{A21:#010x}"] = {"status": "failed", "reason": "boom"}
        try:
            module.validate_index(tmp, index, DIGEST, PLMARK, FARS, CONTROLS)
        except module.SearchStop:
            return False, "a failed entry is refused"
    return True, "an index holding a failure passed validation and would reach a verdict"


def probe_capture_file_is_evidence(module) -> tuple[bool, str]:
    """A capture whose bytes changed must be refused even when its frame still matches."""
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        index = _one_capture(module, tmp)
        path = tmp / index["entries"][f"{A20:#010x}"]["capture"]
        # Preserve every indexed semantic field.  A changed CONFIG_STATUS would now be
        # caught by its own summary check, which would accidentally mask a missing file
        # digest.  This unindexed addition changes only the evidence bytes, so only the
        # capture digest can notice it.
        capture = capture_for(module, A20, SIGNATURES[A20])
        capture["unindexed_tamper"] = True
        path.write_text(json.dumps(capture), encoding="utf-8")
        try:
            module.validate_index(tmp, index, DIGEST, PLMARK, FARS, CONTROLS)
        except module.SearchStop:
            return False, "an edited capture file is refused"
    return True, "an edited capture file was accepted on the index's word"


def probe_recomputed_coverage(module) -> tuple[bool, str]:
    """One capture and an index that forgot to say so must not read as a complete search."""
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        asked: list[int] = []
        module.run(tmp, PLMARK, SIGNATURES, BASE, FARS, DIGEST, CONTROLS,
                   runner=runner_for(module, {}, asked), plmark_reader=lambda port: PLMARK,
                   max_reads=0)
        index = json.loads((tmp / "index.json").read_text("utf-8"))
        index.pop("not_attempted", None)
        (tmp / "index.json").write_text(json.dumps(index), encoding="utf-8")
        verdict = module.run(tmp, PLMARK, SIGNATURES, BASE, FARS, DIGEST,
                             CONTROLS,
                             runner=runner_for(module, {}, asked),
                             plmark_reader=lambda port: PLMARK, max_reads=1)
    if verdict["verdict"] == "NOT_FOUND_COMPLETE":
        return True, ("it called a search complete with "
                      f"{len(FARS) - 1} of {len(FARS)} frames never read")
    return False, f"it recomputed the coverage: {verdict['verdict']}"


def probe_child_log_digest(module) -> tuple[bool, str]:
    """A child log whose bytes changed must be refused, even if it still looks plausible."""
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        index = _one_capture(module, tmp)
        entry = index["entries"][f"{A20:#010x}"]
        path = tmp / entry["child_log"]
        log = json.loads(path.read_text("utf-8"))
        log["stdout"] = "tampered"
        path.write_text(json.dumps(log), encoding="utf-8")
        try:
            module.validate_index(tmp, index, DIGEST, PLMARK, FARS, CONTROLS)
        except module.SearchStop:
            return False, "an edited child log is refused"
    return True, "an edited child log was accepted on the index's word"


def probe_runner_exception_evidence(module) -> tuple[bool, str]:
    """A child that raises must still leave a failed entry and its log behind."""
    def raising(far: int, out_path: Path) -> dict:
        raise TimeoutError("the child never returned")

    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        try:
            module.run(tmp, PLMARK, SIGNATURES, BASE, FARS, DIGEST, CONTROLS,
                       runner=raising,
                       plmark_reader=lambda port: PLMARK)
        except Exception:
            pass
        index_path = tmp / "index.json"
        if not index_path.exists():
            return True, "the run left no index at all"
        entries = json.loads(index_path.read_text("utf-8")).get("entries", {})
        entry = entries.get(f"{A20:#010x}")
        if not entry or entry.get("status") != "failed":
            return True, "the run left no failed entry"
        if not (tmp / entry.get("child_log", "nothing")).exists():
            return True, "the run left no child log"
    return False, "the failure landed with its evidence"


def probe_resume_closure(module) -> tuple[bool, str]:
    """A resumed invocation is open before its closing read, even if that read raises."""
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        module.run(tmp, PLMARK, SIGNATURES, BASE, FARS, DIGEST,
                   CONTROLS,
                   runner=runner_for(module, {}, []),
                   plmark_reader=lambda port: PLMARK, max_reads=0)
        try:
            module.run(tmp, PLMARK, SIGNATURES, BASE, FARS, DIGEST,
                       CONTROLS,
                       runner=runner_for(module, {}, []),
                       plmark_reader=lambda port: (_ for _ in ()).throw(
                           RuntimeError("the UART disappeared")))
        except Exception:
            pass
        index = json.loads((tmp / "index.json").read_text("utf-8"))
        try:
            module.require_closed(index)
        except module.SearchStop:
            return False, "the rebooted resume is unclosed on disk"
    return True, "the rebooted resume inherited the previous invocation's closure"


def probe_mismatch_lands(module) -> tuple[bool, str]:
    """The mismatching end marker itself is evidence and must reach disk before refusal."""
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        module.run(tmp, PLMARK, SIGNATURES, BASE, FARS, DIGEST,
                   CONTROLS,
                   runner=runner_for(module, {}, []),
                   plmark_reader=lambda port: PLMARK, max_reads=0)
        try:
            module.run(tmp, PLMARK, SIGNATURES, BASE, FARS, DIGEST,
                       CONTROLS,
                       runner=runner_for(module, {}, []),
                       plmark_reader=lambda port: "rebooted")
        except module.SearchStop:
            pass
        index = json.loads((tmp / "index.json").read_text("utf-8"))
        if index.get("plmark_at_end") != "rebooted":
            return True, "the mismatch refusal discarded the observed end marker"
    return False, "the mismatching end marker is on disk"


def probe_timeout_streams(module) -> tuple[bool, str]:
    """Bytes emitted before a timeout must survive in the failed child's evidence."""
    stdout, stderr = b"partial-stdout\x00\xff", b"partial-stderr\r\n"

    def raising(far: int, out_path: Path) -> dict:
        import subprocess
        raise subprocess.TimeoutExpired(["openocd"], 600, output=stdout, stderr=stderr)

    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        try:
            module.run(tmp, PLMARK, SIGNATURES, BASE, FARS, DIGEST, CONTROLS,
                       runner=raising,
                       plmark_reader=lambda port: PLMARK)
        except module.SearchStop:
            pass
        index = json.loads((tmp / "index.json").read_text("utf-8"))
        entry = index["entries"][f"{A20:#010x}"]
        log = json.loads((tmp / entry["child_log"]).read_text("utf-8"))
        streams = log.get("exception_streams", {})
        try:
            got_out = base64.b64decode(streams["stdout"]["base64"])
            got_err = base64.b64decode(streams["stderr"]["base64"])
        except (KeyError, TypeError, ValueError):
            return True, "the timeout log has no lossless partial streams"
        if (got_out, got_err) != (stdout, stderr):
            return True, "the timeout log discarded or changed the partial streams"
    return False, "the timeout's partial streams landed byte-for-byte"


def probe_control_requires_exact(module) -> tuple[bool, str]:
    """Sixteen non-zero wrong frames must invalidate, not validate, the instrument."""
    wrong = {far: signature(0xD000 + offset)
             for offset, far in enumerate(CONTROL_FARS)}
    asked: list[int] = []
    with tempfile.TemporaryDirectory() as name:
        verdict = module.run(
            Path(name), PLMARK, SIGNATURES, BASE, FARS, DIGEST, CONTROLS,
            runner=runner_for(module, wrong, asked), plmark_reader=lambda port: PLMARK)
    if verdict["verdict"] != "INSTRUMENT_INVALID" or A21 in asked:
        return True, (f"non-zero wrong controls produced {verdict['verdict']} and reads "
                      f"{[f'{far:#010x}' for far in asked]}")
    return False, "only a whole same-FAR base-frame match validates the instrument"


def probe_neither_requires_control(module) -> tuple[bool, str]:
    """The intended FAR's third state may not be reported by an invalid instrument."""
    wrong = {A20: signature(0xDEAD)}
    wrong.update({far: signature(0xD000 + offset)
                  for offset, far in enumerate(CONTROL_FARS)})
    with tempfile.TemporaryDirectory() as name:
        verdict = module.run(
            Path(name), PLMARK, SIGNATURES, BASE, FARS, DIGEST, CONTROLS,
            runner=runner_for(module, wrong, []), plmark_reader=lambda port: PLMARK)
    if verdict["verdict"] == "INTENDED_FAR_IS_NEITHER":
        return True, "a third-state location verdict bypassed the failed controls"
    return False, f"the failed controls took precedence: {verdict['verdict']}"


def probe_sweep_requires_control(module) -> tuple[bool, str]:
    """Direct callers of the judge cannot manufacture a location verdict."""
    captures = {far: list(ZERO) for far in FARS}
    verdict = module.judge_sweep({}, captures, [], SIGNATURES, CONTROLS)
    if verdict["verdict"] != "INSTRUMENT_INVALID":
        return True, f"the judge emitted {verdict['verdict']} without a positive control"
    return False, "the judge failed closed on its own"


def probe_control_only_read_set(module) -> tuple[bool, str]:
    """The diagnostic mode may spawn exactly the sixteen reviewed controls."""
    asked: list[int] = []
    with tempfile.TemporaryDirectory() as name:
        try:
            module.run_control_only(
                Path(name), PLMARK, BASE, CONTROL_DIGEST, CONTROLS,
                runner=runner_for(module, {}, asked), plmark_reader=lambda port: PLMARK)
        except module.SearchStop:
            pass
    if asked != CONTROL_FARS:
        return True, f"control-only asked for {[f'{far:#010x}' for far in asked]}"
    return False, "control-only read exactly the sixteen controls"


def probe_control_only_vocabulary(module) -> tuple[bool, str]:
    """Even a valid control acquisition cannot return a location verdict."""
    with tempfile.TemporaryDirectory() as name:
        verdict = module.run_control_only(
            Path(name), PLMARK, BASE, CONTROL_DIGEST, CONTROLS,
            runner=runner_for(module, {}, []), plmark_reader=lambda port: PLMARK)
    allowed = {"INSTRUMENT_VALID", "INSTRUMENT_INVALID", "INSTRUMENT_UNVALIDATED"}
    if verdict.get("verdict") not in allowed:
        return True, f"control-only emitted {verdict.get('verdict')}"
    return False, f"the verdict stayed in the instrument vocabulary: {verdict['verdict']}"


def probe_mode_binding(module) -> tuple[bool, str]:
    """A control index with every other field acceptable is still not a search index."""
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        module.run_control_only(
            tmp, PLMARK, BASE, DIGEST, CONTROLS,
            runner=runner_for(module, {}, []), plmark_reader=lambda port: PLMARK)
        index = json.loads((tmp / "index.json").read_text("utf-8"))
        try:
            module.validate_index(
                tmp, index, DIGEST, PLMARK, FARS, CONTROLS,
                module.MODE_SIGNATURE_SEARCH)
        except module.SearchStop:
            return False, "the control index was refused as search evidence"
    return True, "a control-only index was accepted as a location-search index"


def probe_status_summary(module) -> tuple[bool, str]:
    """Every successful child contributes its CONFIG_STATUS to the index."""
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        try:
            module.run_control_only(
                tmp, PLMARK, BASE, CONTROL_DIGEST, CONTROLS,
                runner=runner_for(module, {}, []), plmark_reader=lambda port: PLMARK)
        except module.SearchStop:
            pass
        index = json.loads((tmp / "index.json").read_text("utf-8"))
    statuses = [entry.get("config_status") for entry in index["entries"].values()
                if entry.get("status") == "ok"]
    if len(statuses) != len(CONTROLS) or any(status != "0x46107ffc" for status in statuses):
        return True, f"the index summaries contain {statuses.count('0x46107ffc')}/16 statuses"
    return False, "all sixteen CONFIG_STATUS observations reached the index"



def _digests(directory: Path) -> dict:
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.iterdir()) if path.is_file()}


def probe_judge_only_writes(module) -> tuple[bool, str]:
    """Does judging an acquisition change any byte of it?

    This is what was damaged in the real evidence: `--judge-only` wrote `verdict.json` like an
    acquisition does, replacing a PUBLISHED acquisition's own `elapsed_s` with however long
    the judging took. The acquisition here is synthetic and built by the module under test, so
    the child argv recorded in each capture matches this directory — judging a *copy* of a
    real acquisition always stops on that argv check, which would mean the write branch was
    never reached and the gate would pass without testing anything.

    The repo-relative inputs are pinned to the synthetic ones for the same reason: the run has
    to reach its verdict for the write to be reachable at all. The identity mechanism they
    stand in for has its own mutants.
    """
    import contextlib
    import io
    from unittest import mock

    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        asked: list[int] = []
        module.run_control_only(
            tmp, PLMARK, BASE, CONTROL_DIGEST, CONTROLS,
            runner=runner_for(module, {}, asked), plmark_reader=lambda port: PLMARK)

        before = _digests(tmp)
        argv = ["board_signature_search.py", "--control-only", "--judge-only",
                "--out-dir", str(tmp), "--plmark", PLMARK]
        with (mock.patch.object(module, "canonical_authority", lambda: ({}, {})),
              mock.patch.object(module, "frozen_far_sequence", lambda: FARS),
              mock.patch.object(module, "base_frames", lambda: BASE),
              mock.patch.object(module, "canonical_positive_controls", lambda base: CONTROLS),
              mock.patch.object(module, "instrument_digest",
                                lambda fars, mode=None: CONTROL_DIGEST),
              mock.patch.object(sys, "argv", argv),
              contextlib.redirect_stdout(io.StringIO()) as captured):
            code = module.main()
        if code != 0:
            return False, ("the judge did not reach its verdict, so the write branch was "
                           f"never exercised: {captured.getvalue()[-200:]!r}")
        after = _digests(tmp)
        changed = sorted(set(before) ^ set(after)) + sorted(
            entry for entry in before.keys() & after.keys() if before[entry] != after[entry])
        if changed:
            return True, f"judging wrote {changed} into the acquisition"
        return False, "judging left every byte of the acquisition alone"


PROBES = {
    "judge_only_writes_the_acquisition": probe_judge_only_writes,
    "two_fars_per_child": probe_argv,
    "two_fars_no_guard": probe_argv,
    "defer_the_intended_decision": probe_intended_first,
    "skip_failed_child": probe_failure_stops,
    "validate_ignores_failed": probe_failed_is_not_coverage,
    "validate_trusts_capture_file": probe_capture_file_is_evidence,
    "missing_not_attempted_means_complete": probe_recomputed_coverage,
    "ignore_child_log_digest": probe_child_log_digest,
    "timeout_leaves_no_failure_evidence": probe_runner_exception_evidence,
    "resume_reuses_previous_closure": probe_resume_closure,
    "mismatched_end_is_not_persisted": probe_mismatch_lands,
    "timeout_drops_partial_output": probe_timeout_streams,
    "any_nonzero_control_passes": probe_control_requires_exact,
    "neither_bypasses_control": probe_neither_requires_control,
    "not_found_bypasses_control": probe_sweep_requires_control,
    "control_only_widens_read_set": probe_control_only_read_set,
    "control_only_emits_location": probe_control_only_vocabulary,
    "control_index_is_a_search_index": probe_mode_binding,
    "drop_config_status_summary": probe_status_summary,
}


def main() -> int:
    original = SOURCE.read_text(encoding="utf-8")
    baseline = load(original, "baseline")
    for name, probe in PROBES.items():
        unsafe, why = probe(baseline)
        if unsafe:
            print(f"the unmutated module already answers yes to {name} ({why}); "
                  "the gate is meaningless")
            return 1

    killed = 0
    for name, edits in MUTANTS.items():
        text = original
        for before, after in edits:
            if before not in text:
                print(f"{name}: ANCHOR MISSING — repoint it, do not loosen the gate")
                return 1
            text = text.replace(before, after)
        module = load(text, name)
        unsafe, why = PROBES[name](module)
        if unsafe:
            print(f"{name}: KILLED — {why}")
            killed += 1
        else:
            print(f"{name}: SURVIVED — {why}")

    print(f"{killed}/{len(MUTANTS)} signature-search mutants killed")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

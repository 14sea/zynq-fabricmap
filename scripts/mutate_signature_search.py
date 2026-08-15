#!/usr/bin/env python3
"""Mutation gate for the load-bearing rules of the signature search.

Twelve mutants, each removing one thing the search is not allowed to do without:

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
FARS = [A20, A21, A22]
PLMARK = "18cc00f0fa537908"
DIGEST = "d" * 64
ZERO = [0] * 101


def signature(seed: int) -> list[int]:
    words = list(ZERO)
    words[51] = seed
    words[50] = seed ^ 0x19C6
    return words


SIGNATURES = {A20: signature(0x40), A21: signature(0x41)}
BASE = {far: list(ZERO) for far in FARS}

MUTANTS = {
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
        '    if decision["sweep_needed"]:\n        reads = 0',
        '    if True:  # mutant: sweep regardless of what the first frame said\n        reads = 0')],
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
        '        _, missing = validate_index(out_dir, index, digest, plmark, fars)',
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
        '            "during the search and every capture after that is from a different PL")',
        '    if index["plmark_at_end"] != plmark:\n'
        '        raise SearchStop(\n'
        '            f"plmark changed from {plmark} to {index[\'plmark_at_end\']}: the board restarted "\n'
        '            "during the search and every capture after that is from a different PL")\n'
        '    _atomic_write(out_dir / "index.json", json.dumps(index, indent=2) + "\\n")')],
    # MUTATION ANCHOR timeout_streams: partial OpenOCD output is failure evidence.
    "timeout_drops_partial_output": [(
        '        partial_stdout = getattr(raised, "stdout", None)\n'
        '        if partial_stdout is None:\n'
        '            partial_stdout = getattr(raised, "output", None)\n'
        '        partial_stderr = getattr(raised, "stderr", None)',
        '        partial_stdout = None  # mutant: discard what OpenOCD emitted before timeout\n'
        '        partial_stderr = None')],
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
        out_path.write_text(json.dumps(capture_for(module, far, content.get(far, ZERO))),
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
                       runner=runner_for(module, {}, asked, fail_on=A21),
                       plmark_reader=lambda port: PLMARK)
        except module.SearchStop:
            pass
    if asked != [A20, A21]:
        return True, (f"it kept reading after a failed child: "
                      f"{[f'{far:#010x}' for far in asked]}")
    return False, "the failure stopped the search at the frame that failed"


def _one_capture(module, tmp: Path) -> dict:
    """A minimal index with one good capture, written the way the module writes them."""
    asked: list[int] = []
    module.run(tmp, PLMARK, SIGNATURES, BASE, [A20], DIGEST,
               runner=runner_for(module, {}, asked), plmark_reader=lambda port: PLMARK)
    return json.loads((tmp / "index.json").read_text("utf-8"))


def probe_failed_is_not_coverage(module) -> tuple[bool, str]:
    """`validate_index` must refuse an index holding a failure — judge-only relies on it."""
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        index = _one_capture(module, tmp)
        index["entries"][f"{A21:#010x}"] = {"status": "failed", "reason": "boom"}
        try:
            module.validate_index(tmp, index, DIGEST, PLMARK, [A20, A21])
        except module.SearchStop:
            return False, "a failed entry is refused"
    return True, "an index holding a failure passed validation and would reach a verdict"


def probe_capture_file_is_evidence(module) -> tuple[bool, str]:
    """A capture whose bytes changed must be refused even when its frame still matches."""
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        index = _one_capture(module, tmp)
        path = tmp / index["entries"][f"{A20:#010x}"]["capture"]
        # Same frame, different bytes: only the file digest can notice this one.
        path.write_text(json.dumps(capture_for(module, A20, ZERO,
                                               config_status="0xdeadbeef")), encoding="utf-8")
        try:
            module.validate_index(tmp, index, DIGEST, PLMARK, [A20])
        except module.SearchStop:
            return False, "an edited capture file is refused"
    return True, "an edited capture file was accepted on the index's word"


def probe_recomputed_coverage(module) -> tuple[bool, str]:
    """One capture and an index that forgot to say so must not read as a complete search."""
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        asked: list[int] = []
        module.run(tmp, PLMARK, SIGNATURES, BASE, [A20], DIGEST,
                   runner=runner_for(module, {}, asked), plmark_reader=lambda port: PLMARK)
        index = json.loads((tmp / "index.json").read_text("utf-8"))
        index.pop("not_attempted", None)
        (tmp / "index.json").write_text(json.dumps(index), encoding="utf-8")
        verdict = module.run(tmp, PLMARK, SIGNATURES, BASE, FARS, DIGEST,
                             runner=runner_for(module, {}, asked),
                             plmark_reader=lambda port: PLMARK, max_reads=0)
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
            module.validate_index(tmp, index, DIGEST, PLMARK, [A20])
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
            module.run(tmp, PLMARK, SIGNATURES, BASE, [A20], DIGEST, runner=raising,
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
                   runner=runner_for(module, {}, []),
                   plmark_reader=lambda port: PLMARK, max_reads=0)
        try:
            module.run(tmp, PLMARK, SIGNATURES, BASE, FARS, DIGEST,
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
                   runner=runner_for(module, {}, []),
                   plmark_reader=lambda port: PLMARK, max_reads=0)
        try:
            module.run(tmp, PLMARK, SIGNATURES, BASE, FARS, DIGEST,
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
            module.run(tmp, PLMARK, SIGNATURES, BASE, [A20], DIGEST, runner=raising,
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


PROBES = {
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

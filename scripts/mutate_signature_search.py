#!/usr/bin/env python3
"""Mutation gate for the load-bearing rules of the signature search.

Six mutants, each removing one thing the search is not allowed to do without:

  * a child reads one FAR, because a process is trustworthy for exactly one read;
  * the intended frame is decided before any sweep, because it answers the question alone in
    two cases out of three and a sweep is 5,144 more chances to lose the state;
  * a failed child stops the search where it failed, because a hole in the coverage lets a
    later "not found" quietly mean "not looked at";
  * `validate_index()` refuses an index that holds a failure, on every path including
    `--judge-only`, which does not touch hardware and so has no other check;
  * `validate_index()` re-hashes the capture files, because an index is a claim and the
    captures are the evidence.

Each probe asks a module a question about behaviour and runs it to find out. Nothing here
searches for the mutation itself.
"""

from __future__ import annotations

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
        '        _atomic_write(index_path, json.dumps(index, indent=2) + "\\n")\n'
        '        # Recorded, then stopped. A hole in the coverage would let a later "not found" mean\n'
        '        # "not looked at", so the search never continues past one.\n'
        '        raise',
        '        _atomic_write(index_path, json.dumps(index, indent=2) + "\\n")\n'
        '        return list(ZERO_WORDS)  # mutant: carry on past a failed child')],
    # MUTATION ANCHOR failed_is_not_coverage: judge-only has no other check.
    "validate_ignores_failed": [(
        '    if failed:\n        raise SearchStop(f"the search holds failed captures and is not coverage: {failed}")',
        '    if failed:\n        pass  # mutant: a failure is treated as coverage')],
    # MUTATION ANCHOR capture_digest: an index is a claim, the capture file is the evidence.
    "validate_trusts_capture_file": [(
        '        if _digest_of(path) != entry.get("capture_sha256"):\n'
        '            raise SearchStop(f"{key}: the capture file has changed since it was written")',
        '        pass  # mutant: believe the index about the file')],
}


def load(text: str, name: str):
    path = Path(tempfile.mkdtemp()) / f"mutant_{name}.py"
    # `skip_failed_child` needs a value to return where the reviewed code raises.
    text = text.replace("class SearchStop(Exception):",
                        "ZERO_WORDS = [0] * 101\n\n\nclass SearchStop(Exception):")
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
        if far == fail_on:
            return {"returncode": 1, "argv": [], "stdout": "", "stderr": "boom"}
        out_path.write_text(json.dumps(capture_for(module, far, content.get(far, ZERO))),
                            encoding="utf-8")
        return {"returncode": 0, "argv": [], "stdout": "", "stderr": ""}
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
            module.validate_index(tmp, index, DIGEST, PLMARK)
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
            module.validate_index(tmp, index, DIGEST, PLMARK)
        except module.SearchStop:
            return False, "an edited capture file is refused"
    return True, "an edited capture file was accepted on the index's word"


PROBES = {
    "two_fars_per_child": probe_argv,
    "two_fars_no_guard": probe_argv,
    "defer_the_intended_decision": probe_intended_first,
    "skip_failed_child": probe_failure_stops,
    "validate_ignores_failed": probe_failed_is_not_coverage,
    "validate_trusts_capture_file": probe_capture_file_is_evidence,
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

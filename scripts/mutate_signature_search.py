#!/usr/bin/env python3
"""Mutation gate for the two rules the signature search exists to keep.

One child reads one FAR, because a process is trustworthy for exactly one read. And a failed
child stops the search, because a hole in the coverage would let a later "not found" quietly
mean "not looked at".

Each probe answers one question about a module: **would this build hand a child two FARs, or
finish a search that contains a failure?** The unmutated module must answer no to every
probe; a mutant is killed when it answers yes, or when the module's own guard refuses to
produce the mutated behaviour at all. Nothing here searches for the mutation itself.
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

A20, A21 = 0x00400A20, 0x00400A21
PLMARK = "18cc00f0fa537908"
DIGEST = "d" * 64
ZERO = [0] * 101

MUTANTS = {
    # MUTATION ANCHOR one_far: the child must never be handed a second frame to read.
    "two_fars_per_child": [(
        '    argv = [sys.executable, str(CHILD), "--far", f"{far:#010x}", "--out", str(out_path)]',
        '    argv = [sys.executable, str(CHILD), "--far", f"{far:#010x}",\n'
        '            "--far", f"{far + 1:#010x}", "--out", str(out_path)]')],
    # The same, with the guard removed too: nothing then stops it at build time, and the
    # harness's own invariant has to be what notices.
    "two_fars_no_guard": [
        ('    argv = [sys.executable, str(CHILD), "--far", f"{far:#010x}", "--out", str(out_path)]',
         '    argv = [sys.executable, str(CHILD), "--far", f"{far:#010x}",\n'
         '            "--far", f"{far + 1:#010x}", "--out", str(out_path)]'),
        ("    check_child_argv(argv)\n    return argv", "    return argv")],
    # MUTATION ANCHOR fail_stops: a recorded failure must never become a skipped frame.
    "skip_failed_child": [(
        '            _atomic_write(index_path, json.dumps(index, indent=2) + "\\n")\n'
        '            # A failed FAR is recorded and then stops the run. It is never skipped:'
        ' a hole in\n'
        '            # the coverage would let a later "not found" mean "not looked at".\n'
        '            raise',
        '            _atomic_write(index_path, json.dumps(index, indent=2) + "\\n")\n'
        '            continue  # mutant: carry on past a failed child')],
}


def load(text: str, name: str):
    path = Path(tempfile.mkdtemp()) / f"mutant_{name}.py"
    path.write_text(text, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"mutant_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def capture_for(far: int) -> dict:
    body = b"".join(word.to_bytes(4, "big") for word in ZERO)
    return {"verdict": "READ", "idcode": "0x13722093", "config_status": "0x46107ffc",
            "frames": {f"{far:#010x}": {
                "frame": [f"{word:08x}" for word in ZERO],
                "pad_frame": [f"{word:08x}" for word in ZERO],
                "frame_sha256": hashlib.sha256(body).hexdigest()}}}


def probe_argv(module) -> tuple[bool, str]:
    """Every argv a child could receive must name exactly one FAR, or be refused."""
    try:
        argv = module.child_argv(A20, Path("/tmp/mutant.json"), None, None)
    except module.SearchStop as refused:
        return True, f"the module refused to build it: {refused}"
    count = argv.count("--far")
    if count != 1:
        return True, f"it would hand a child {count} FARs with nothing to stop it"
    return False, "one FAR per child"


def probe_failure_stops(module) -> tuple[bool, str]:
    """A failed child must stop the search **there**, not merely spoil its verdict later.

    Counting the children is what makes this sharp. A completeness check at the end can turn
    a carry-on into a refusal, which is worth having, but it is not the same rule: by then
    the search has gone on reading frames after a hole opened, and the operator has spent
    time and reads on a result that was already void.
    """
    asked: list[int] = []

    def runner(far: int, out_path: Path) -> int:
        asked.append(far)
        if far == A20:
            return 1
        out_path.write_text(json.dumps(capture_for(far)), encoding="utf-8")
        return 0

    with tempfile.TemporaryDirectory() as name:
        try:
            module.run_search([A20, A21], Path(name), PLMARK, DIGEST, runner=runner,
                              plmark_reader=lambda port: PLMARK)
        except module.SearchStop:
            pass
    if asked != [A20]:
        return True, (f"it kept reading after a failed child: asked for "
                      f"{[f'{far:#010x}' for far in asked]}")
    return False, "the failure stopped the search at the frame that failed"


PROBES = {
    "two_fars_per_child": probe_argv,
    "two_fars_no_guard": probe_argv,
    "skip_failed_child": probe_failure_stops,
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

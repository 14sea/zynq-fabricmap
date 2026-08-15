#!/usr/bin/env python3
"""Mutation gate for the reviewed JTAG envelope and recovery ordering.

Two mutants remove a DESYNC; the third restores the pre-R1 RCRC order. A mutant is killed
only when a checker names the resulting behaviour or `build_tcl()` refuses to emit it —
never by a string search for the mutation itself, which would only prove the patch applied.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
SOURCE = REPO / "scripts/probe_jtag_config_read.py"

FARS = [0x00400A20, 0x00400A21]

MUTANTS = {
    # MUTATION ANCHOR read_desync: the per-FAR close is what the miss was missing.
    "drop_read_desync": (
        '        close_envelope(f"FDRO {far:#010x}")',
        '        pass  # mutant: the read envelope is never closed'),
    # MUTATION ANCHOR stat_desync: the first CFG_OUT must also be inside a closed envelope.
    "drop_stat_desync": (
        '    close_envelope("STAT")',
        '    pass  # mutant: the STAT envelope is never closed'),
    # MUTATION ANCHOR r1_order: moving RCRC back before JSHUTDOWN restores the failed rung.
    "rcrc_before_jshutdown": (
        '    # -- the one JSHUTDOWN of the session, then R1\'s reordered RCRC envelope.\n'
        '    lines += [f"irscan {TAP} 0x{IR[\'JSHUTDOWN\']:02x}",\n'
        '              "runtest 12",\n'
        '              "echo \\"@@ shutdown done\\""]\n'
        '    cfg_in([DUMMY, SYNC, NOOP, t1(True, CMD_REG, 1), CMD_RCRC, NOOP, NOOP], "RCRC")\n'
        '    close_envelope("RCRC")',
        '    # mutant: restore the pre-R1 sequence.\n'
        '    cfg_in([DUMMY, SYNC, NOOP, t1(True, CMD_REG, 1), CMD_RCRC, NOOP, NOOP], "RCRC")\n'
        '    close_envelope("RCRC")\n'
        '    lines += [f"irscan {TAP} 0x{IR[\'JSHUTDOWN\']:02x}",\n'
        '              "runtest 12",\n'
        '              "echo \\"@@ shutdown done\\""]'),
}


def load_mutant(text: str, name: str):
    path = Path(tempfile.mkdtemp()) / f"mutant_{name}.py"
    path.write_text(text, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"mutant_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    original = SOURCE.read_text(encoding="utf-8")
    baseline = load_mutant(original, "baseline")
    tcl, _ = baseline.build_tcl(FARS)
    if baseline.envelope_violations(tcl):
        print("the unmutated script already violates the rule; the gate is meaningless")
        return 1

    killed = 0
    for name, (before, after) in MUTANTS.items():
        if before not in original:
            print(f"{name}: ANCHOR MISSING — repoint it, do not loosen the gate")
            return 1
        module = load_mutant(original.replace(before, after), name)
        try:
            mutant_tcl, _ = module.build_tcl(FARS)
        except Exception as refused:
            print(f"{name}: KILLED — build_tcl refused to emit it ({refused})")
            killed += 1
            continue
        problems = [*module.envelope_violations(mutant_tcl),
                    *module.recovery_order_violations(mutant_tcl)]
        if problems:
            print(f"{name}: KILLED — {problems[0]}")
            killed += 1
        else:
            print(f"{name}: SURVIVED — the rule does not catch a dropped DESYNC")

    print(f"{killed}/{len(MUTANTS)} envelope mutants killed")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

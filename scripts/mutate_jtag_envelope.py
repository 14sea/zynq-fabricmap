#!/usr/bin/env python3
"""Mutation gate for the reviewed JTAG envelope and recovery sequence.

Two baseline mutants remove a DESYNC. Three recovery mutants restore the pre-R1 RCRC order,
shorten R2's dwell, or remove R2's pre-read envelope. A mutant is killed only when a checker
names the resulting behaviour or `build_tcl()` refuses to emit it — never by a string search
for the mutation itself, which would only prove the patch applied.
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
    # MUTATION ANCHOR r1_order: moving RCRC back before JSHUTDOWN restores the old order.
    "rcrc_before_jshutdown": (
        '    # -- R2: one JSHUTDOWN, a fixed dwell, R1\'s RCRC, then a closed pre-read envelope.\n'
        '    lines += [f"irscan {TAP} 0x{IR[\'JSHUTDOWN\']:02x}",\n'
        '              f"runtest {SHUTDOWN_RTI_CYCLES}",\n'
        '              "echo \\"@@ shutdown done\\""]\n'
        '    cfg_in([DUMMY, SYNC, NOOP, t1(True, CMD_REG, 1), CMD_RCRC, NOOP, NOOP], "RCRC")\n'
        '    close_envelope("RCRC")\n'
        '    cfg_in([DUMMY, SYNC, NOOP, *DESYNC_TAIL], "pre-read DESYNC")',
        '    # mutant: restore the pre-R1 sequence.\n'
        '    cfg_in([DUMMY, SYNC, NOOP, t1(True, CMD_REG, 1), CMD_RCRC, NOOP, NOOP], "RCRC")\n'
        '    close_envelope("RCRC")\n'
        '    lines += [f"irscan {TAP} 0x{IR[\'JSHUTDOWN\']:02x}",\n'
        '              f"runtest {SHUTDOWN_RTI_CYCLES}",\n'
        '              "echo \\"@@ shutdown done\\""]\n'
        '    cfg_in([DUMMY, SYNC, NOOP, *DESYNC_TAIL], "pre-read DESYNC")'),
    # MUTATION ANCHOR r2_dwell: retain R1's old 12-TCK settling interval.
    "short_shutdown_dwell": (
        '              f"runtest {SHUTDOWN_RTI_CYCLES}",',
        '              "runtest 12",  # mutant: R2 dwell was not applied'),
    # MUTATION ANCHOR r2_desync: omit the additional closed pre-read envelope.
    "drop_pre_read_desync": (
        '    cfg_in([DUMMY, SYNC, NOOP, *DESYNC_TAIL], "pre-read DESYNC")',
        '    pass  # mutant: R2 pre-read envelope is absent'),
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

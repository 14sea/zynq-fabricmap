#!/usr/bin/env python3
"""Mutation gate for the reviewed JTAG envelope and R4 recovery sequence.

Two baseline mutants remove a DESYNC. R4 mutants damage instructions, ordering and each of
the three documented dwells. A mutant is killed only when a checker names the resulting
emitted behaviour or `build_tcl()` refuses to emit it — never by a string search for the
mutation itself, which would only prove the patch applied.
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

MUTANTS: dict[str, list[tuple[str, str]]] = {
    # MUTATION ANCHOR read_desync: the per-FAR close is what the miss was missing.
    "drop_read_desync": [(
        '        close_envelope(f"FDRO {far:#010x}")',
        '        pass  # mutant: the read envelope is never closed')],
    # MUTATION ANCHOR stat_desync: the first CFG_OUT must also be inside a closed envelope.
    "drop_stat_desync": [(
        '    close_envelope("STAT")',
        '    pass  # mutant: the STAT envelope is never closed')],
    # MUTATION ANCHOR r4_rcrc: Table 6-6's RCRC envelope is part of the fixed instrument.
    "drop_rcrc": [(
        '    cfg_in([DUMMY, SYNC, NOOP, t1(True, CMD_REG, 1), CMD_RCRC, NOOP, NOOP], "RCRC")\n'
        '    close_envelope("RCRC")',
        '    pass  # mutant: RCRC and its close are both absent')],
    # MUTATION ANCHOR r4_start: omit the newly allowlisted instruction.
    "drop_jstart": [(
        '    lines += [f"irscan {TAP} 0x{IR[\'JSTART\']:02x}",\n'
        '              f"runtest {R4_DWELLS[\'startup\'][\'cycles\']}"]',
        '    pass  # mutant: JSTART and its dwell are absent')],
    # MUTATION ANCHOR r4_leading_shutdown: omit the first half of the transition.
    "drop_leading_jshutdown": [(
        '    lines += [f"irscan {TAP} 0x{IR[\'JSHUTDOWN\']:02x}",\n'
        '              f"runtest {R4_DWELLS[\'startup_cycle_shutdown\'][\'cycles\']}"]',
        '    pass  # mutant: the leading JSHUTDOWN and dwell are absent')],
    # MUTATION ANCHOR r4_start_order: a startup after the measurement cannot affect it.
    "jstart_after_first_fdro": [
        ('    lines += [f"irscan {TAP} 0x{IR[\'JSTART\']:02x}",\n'
         '              f"runtest {R4_DWELLS[\'startup\'][\'cycles\']}"]',
         '    pass  # mutant: original JSTART position removed'),
        ('        close_envelope(f"FDRO {far:#010x}")',
         '        close_envelope(f"FDRO {far:#010x}")\n'
         '        lines += [f"irscan {TAP} 0x{IR[\'JSTART\']:02x}",\n'
         '                  f"runtest {R4_DWELLS[\'startup\'][\'cycles\']}"]'),
    ],
    # MUTATION ANCHORS r4_dwells: exact means neither shorter nor longer is reviewed.
    "wrong_leading_shutdown_dwell": [(
        'f"runtest {R4_DWELLS[\'startup_cycle_shutdown\'][\'cycles\']}"',
        '"runtest 11"')],
    "wrong_startup_dwell": [(
        'f"runtest {R4_DWELLS[\'startup\'][\'cycles\']}"',
        '"runtest 1999"')],
    "wrong_readback_shutdown_dwell": [(
        'f"runtest {R4_DWELLS[\'readback_shutdown\'][\'cycles\']}"',
        '"runtest 13"')],
    # MUTATION ANCHOR r4_table_6_6: reproduce the superseded draft's reversed ordering.
    "rcrc_after_final_jshutdown": [
        ('    cfg_in([DUMMY, SYNC, NOOP, t1(True, CMD_REG, 1), CMD_RCRC, NOOP, NOOP], "RCRC")\n'
         '    close_envelope("RCRC")',
         '    pass  # mutant: RCRC moved below'),
        ('    lines += [f"irscan {TAP} 0x{IR[\'JSHUTDOWN\']:02x}",\n'
         '              f"runtest {R4_DWELLS[\'readback_shutdown\'][\'cycles\']}"]',
         '    lines += [f"irscan {TAP} 0x{IR[\'JSHUTDOWN\']:02x}",\n'
         '              f"runtest {R4_DWELLS[\'readback_shutdown\'][\'cycles\']}"]\n'
         '    cfg_in([DUMMY, SYNC, NOOP, t1(True, CMD_REG, 1), CMD_RCRC, NOOP, NOOP], "RCRC")\n'
         '    close_envelope("RCRC")'),
    ],
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
    baseline_problems = [*baseline.envelope_violations(tcl),
                         *baseline.recovery_order_violations(tcl)]
    if baseline_problems:
        print("the unmutated script already violates the rule; the gate is meaningless: "
              + baseline_problems[0])
        return 1

    killed = 0
    for name, replacements in MUTANTS.items():
        mutated = original
        for before, after in replacements:
            if before not in mutated:
                print(f"{name}: ANCHOR MISSING — repoint it, do not loosen the gate")
                return 1
            mutated = mutated.replace(before, after, 1)
        module = load_mutant(mutated, name)
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
            print(f"{name}: SURVIVED — the reviewed recovery rule did not catch it")

    print(f"{killed}/{len(MUTANTS)} envelope mutants killed")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

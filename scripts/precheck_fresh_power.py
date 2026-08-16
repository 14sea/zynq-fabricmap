#!/usr/bin/env python3
"""READ-ONLY fresh-power-on precheck, with the complete raw console text preserved.

All five preconditions in one place, and the reason this exists as a script rather than as a
pair of scratchpad probes: the earlier runs recorded only the *decoded* values in a reading,
so the raw replies they were decoded from were not kept. Review asked for the raw output to
live in the evidence, so this writes both.

Sends `echo`, `md.l` and `printenv` and nothing else — never `mw`, never a bare CR, never a
command that touches the PL. Exits non-zero on any mismatch and does not attempt a repair:
rebuilding a fresh-power state by hand is exactly what the precheck exists to refuse.

The fifth check is the odd one. `plmark` is set by the loader with `setenv` and never saved,
so on a fresh power-on it must be *absent*; `plmark_only.py` asserts the opposite (that a
known marker survives), and cannot stand in here.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import serial  # noqa: E402

import board_serial as bs  # noqa: E402

REGS = (
    ("devcfg CTRL", 0xF8007000, 0x4E00E07F),
    ("devcfg INT_STS", 0xF800700C, 0xA802000B),
    ("devcfg STATUS", 0xF8007014, 0x40000A30),
    ("SLCR FPGA0_CLK_CTRL", 0xF8000170, 0x00400800),
)
PCFG_DONE = 1 << 2
WORD_RE = re.compile(rb"[0-9a-f]{8}:\s*([0-9a-f]{8})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", default="/dev/ebaz-uart")
    ap.add_argument("--out", type=Path, required=True,
                    help="JSON record; the raw console text is written beside it as <out>.txt")
    args = ap.parse_args()

    record: dict = {"tool": "precheck_fresh_power.py/1.0.0", "port": args.port, "checks": []}
    problems: list[str] = []
    transcript: list[str] = []

    def note(command: str, raw: bytes) -> None:
        transcript.append(f"$ {command}\n{raw.decode('ascii', 'replace')}")

    with serial.Serial(args.port, bs.BAUD, timeout=0.1) as ser:
        sync = bs.sync_prompt(ser)
        note(bs.SYNC_COMMAND, sync)
        if bs.BOOT_BANNER_RE.search(sync):
            problems.append("a boot banner came back with the sync — the board is still booting")
        elif not bs.PROMPT_RE.search(sync):
            problems.append(f"no U-Boot prompt on {args.port}")

        if problems:
            record["checks"].append({"check": "link", "passed": False})
        else:
            record["checks"].append({"check": "link", "passed": True})
            for name, addr, want in REGS:
                raw = bs.ub_cmd(ser, f"md.l {addr:#010x} 0x1", 3.0)
                note(f"md.l {addr:#010x} 0x1", raw)
                found = WORD_RE.search(raw)
                got = int(found.group(1), 16) if found else None
                ok = got == want
                entry = {"check": name, "address": f"{addr:#010x}",
                         "expected": f"{want:#010x}",
                         "observed": f"{got:#010x}" if got is not None else None,
                         "passed": ok, "raw": raw.decode("ascii", "replace")}
                if not ok:
                    problems.append(
                        f"{name} {addr:#010x} = "
                        f"{f'{got:#010x}' if got is not None else 'unreadable'} != {want:#010x}")
                if addr == 0xF800700C and got is not None:
                    done = bool(got & PCFG_DONE)
                    entry["pcfg_done"] = int(done)
                    if done:
                        problems.append("PCFG_DONE=1 — the PL is still configured")
                record["checks"].append(entry)

            raw = bs.ub_cmd(ser, "printenv plmark", 3.0)
            note("printenv plmark", raw)
            defined = re.search(rb"plmark=([0-9a-f]+)", raw)
            undefined = b"not defined" in raw
            entry = {"check": "plmark undefined", "expected": "not defined",
                     "passed": bool(undefined and not defined),
                     "raw": raw.decode("ascii", "replace")}
            if defined:
                problems.append(
                    f"plmark IS defined ({defined.group(1).decode()}) — not a fresh power-on")
            elif not undefined:
                problems.append("the plmark reply is neither a marker nor a 'not defined' error")
            record["checks"].append(entry)

    record["problems"] = problems
    record["passed"] = not problems
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix(args.out.suffix + ".txt").write_text(
        "\n".join(transcript) + "\n", encoding="utf-8")
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    for entry in record["checks"]:
        if entry["check"] == "link":
            continue
        state = "OK" if entry["passed"] else "MISMATCH"
        print(f"  {entry['check']:22s} {entry.get('observed') or entry['expected']}  {state}"
              + (f"   PCFG_DONE={entry['pcfg_done']}" if "pcfg_done" in entry else ""))
    if problems:
        print("\nPRECHECK STOP:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nPRECHECK PASS: all five fresh-power preconditions matched; raw text kept beside "
          f"{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

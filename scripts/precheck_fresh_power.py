#!/usr/bin/env python3
"""READ-ONLY fresh-power-on precheck, with every reply guarded and preserved losslessly.

All five preconditions in one place, and the reason this exists as a script rather than as a
pair of scratchpad probes: the earlier runs recorded only the *decoded* values in a reading,
so the raw replies they were decoded from were not kept.

Sends `echo`, `md.l` and `printenv` and nothing else — never `mw`, never a bare CR, never a
command that touches the PL. Exits non-zero on any problem and does not attempt a repair:
rebuilding a fresh-power state by hand is exactly what the precheck exists to refuse.

The fifth check is the odd one. `plmark` is set by the loader with `setenv` and never saved,
so on a fresh power-on it must be *absent*; `plmark_only.py` asserts the opposite (that a
known marker survives), and cannot stand in here.

What 1.0.0 got wrong
--------------------
1.0.0 checked for a boot banner **only on the opening sync**. A board that restarted midway
through the precheck would therefore still pass, because every individual register value it
had already returned was correct and nothing looked at what followed them. Demonstrated with a
scripted fake: correct `STATUS` reply, SPL banner immediately after, verdict PASS. A precheck
that can be satisfied by a board which rebooted while being checked is not a precheck, so
**every** reply is now guarded — banner rejected, prompt required — and `tests/
test_precheck_fresh_power.py` drives exactly that scenario.

1.0.0 also kept the raw text only as `ascii`-with-replacement, which silently mangles any
non-ASCII byte, and it overwrote whatever was already at `--out`. Replies are now recorded as
base64 with a SHA-256 and a byte count, the record is written atomically, and an existing
output is refused rather than replaced. The `.txt` sidecar remains for reading by eye and is
**lossy by construction** — the base64 is the record of truth.

1.0.0 is left in the history unamended: it is the version that produced the two precheck
records of the R4 replication, and those records were checked reply by reply after the fact.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import board_serial as bs  # noqa: E402

TOOL_VERSION = "precheck_fresh_power.py/1.0.1"

REGS = (
    ("devcfg CTRL", 0xF8007000, 0x4E00E07F),
    ("devcfg INT_STS", 0xF800700C, 0xA802000B),
    ("devcfg STATUS", 0xF8007014, 0x40000A30),
    ("SLCR FPGA0_CLK_CTRL", 0xF8000170, 0x00400800),
)
PCFG_DONE = 1 << 2
WORD_RE = re.compile(rb"[0-9a-f]{8}:\s*([0-9a-f]{8})")


class PrecheckStop(Exception):
    """Raised before the port is opened, for conditions no board reply could fix."""


def preserve(command: str, raw: bytes) -> dict:
    """Every byte that came back, in a form that cannot lose one."""
    return {
        "command": command,
        "byte_count": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "base64": base64.b64encode(raw).decode("ascii"),
        "text": raw.decode("ascii", "replace"),
    }


def reply_problems(command: str, raw: bytes) -> list[str]:
    """Guard applied to EVERY reply, not just the opening sync.

    A banner anywhere means the board restarted during the precheck, which invalidates every
    value read before it as a description of the state being certified. A missing prompt means
    the reply is truncated and whatever was parsed out of it is a guess.
    """
    problems = []
    if bs.BOOT_BANNER_RE.search(raw):
        problems.append(f"{command}: a boot banner came back — the board restarted mid-precheck")
    if not bs.PROMPT_RE.search(raw):
        problems.append(f"{command}: no U-Boot prompt came back — the reply is truncated")
    return problems


def run_precheck(send) -> dict:
    """`send(command) -> bytes` keeps this drivable without a serial port.

    Returns the record whether or not it passed; a failed precheck is evidence too.
    """
    record: dict = {"tool": TOOL_VERSION, "checks": [], "replies": []}
    problems: list[str] = []

    def ask(command: str) -> bytes:
        raw = send(command)
        record["replies"].append(preserve(command, raw))
        problems.extend(reply_problems(command, raw))
        return raw

    ask(bs.SYNC_COMMAND)

    for name, addr, want in REGS:
        raw = ask(f"md.l {addr:#010x} 0x1")
        found = WORD_RE.search(raw)
        got = int(found.group(1), 16) if found else None
        entry = {"check": name, "address": f"{addr:#010x}", "expected": f"{want:#010x}",
                 "observed": f"{got:#010x}" if got is not None else None,
                 "passed": got == want}
        if got != want:
            problems.append(
                f"{name} {addr:#010x} = "
                f"{f'{got:#010x}' if got is not None else 'unreadable'} != {want:#010x}")
        if addr == 0xF800700C and got is not None:
            entry["pcfg_done"] = int(bool(got & PCFG_DONE))
            if got & PCFG_DONE:
                problems.append("PCFG_DONE=1 — the PL is still configured")
        record["checks"].append(entry)

    raw = ask("printenv plmark")
    defined = re.search(rb"plmark=([0-9a-f]+)", raw)
    undefined = b"not defined" in raw
    record["checks"].append({"check": "plmark undefined", "expected": "not defined",
                             "passed": bool(undefined and not defined)})
    if defined:
        problems.append(
            f"plmark IS defined ({defined.group(1).decode()}) — not a fresh power-on")
    elif not undefined:
        problems.append("the plmark reply is neither a marker nor a 'not defined' error")

    record["problems"] = problems
    record["passed"] = not problems
    return record


def refuse_existing(out: Path) -> Path:
    """Checked BEFORE the port is opened, so a mistyped path costs no board interaction."""
    transcript = out.with_name(out.name + ".txt")
    for path in (out, transcript):
        if path.exists():
            raise PrecheckStop(
                f"{path} already exists; a precheck record is evidence and is never replaced")
    return transcript


def write_record(out: Path, transcript: Path, record: dict) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    for path, body in ((transcript, _transcript_text(record)),
                       (out, json.dumps(record, indent=2) + "\n")):
        partial = path.with_name(path.name + ".part")
        partial.write_text(body, encoding="utf-8")
        os.replace(partial, path)


def _transcript_text(record: dict) -> str:
    lines = ["# Lossy convenience view. The base64 in the JSON record is the record of truth.\n"]
    for reply in record["replies"]:
        lines.append(f"$ {reply['command']}\n{reply['text']}\n")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", default="/dev/ebaz-uart")
    ap.add_argument("--out", type=Path, required=True,
                    help="JSON record; a lossy transcript is written beside it as <out>.txt")
    args = ap.parse_args()

    try:
        transcript = refuse_existing(args.out)
    except PrecheckStop as stop:
        print(f"PRECHECK STOP: {stop}", file=sys.stderr)
        return 1

    import serial  # noqa: PLC0415 — deferred so the module imports without pyserial present

    with serial.Serial(args.port, bs.BAUD, timeout=0.1) as ser:
        record = run_precheck(lambda command: bs.ub_cmd(ser, command, 3.0))
    record["port"] = args.port
    write_record(args.out, transcript, record)

    for entry in record["checks"]:
        state = "OK" if entry["passed"] else "MISMATCH"
        print(f"  {entry['check']:22s} {entry.get('observed') or entry['expected']}  {state}"
              + (f"   PCFG_DONE={entry['pcfg_done']}" if "pcfg_done" in entry else ""))
    if record["problems"]:
        print("\nPRECHECK STOP:")
        for problem in record["problems"]:
            print(f"  - {problem}")
        return 1
    print(f"\nPRECHECK PASS: all five fresh-power preconditions matched, every reply guarded; "
          f"raw bytes preserved in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

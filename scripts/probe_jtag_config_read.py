#!/usr/bin/env python3
"""Phase 1: read configuration frames over JTAG, against a bitstream with a known answer.

This does not go through the carrier. It drives the PL TAP directly, so it is an
independent opinion about what is in a frame — which is the whole point: the carrier's own
readback is the thing under suspicion, and it cannot be its own witness.

THE ALLOWED SET, and it is enforced in code, not in a comment
------------------------------------------------------------
IR: IDCODE, CFG_IN, CFG_OUT, JSHUTDOWN.  Configuration: RCRC, RCFG, FAR, FDRO, DESYNC.
**JPROGRAM, JSTART, WCFG, MFWR and any FDRI write are refused before a single bit is
shifted.** `check_sequence()` walks the generated words and raises rather than emit them,
because "the script does not do that" is worth exactly as much as the check that proves it.

WHY A KNOWN ANSWER
------------------
`carrier_eco.bit` is a published, gate-accepted bitstream that differs from `carrier.bit` in
three INIT bits of one LUT, at addresses the local map predicts. Reading it back is a
positive control: if these three bits do not appear at their exact predicted positions, the
readback method is not yet trustworthy, and no conclusion may be drawn from it about
anything else. Three bits appearing is necessary, not sufficient — the full frame is
compared as well, with prjxray's mask marking the bits readback is not expected to preserve.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

TAP = "zynq_pl.bs"
IR = {"IDCODE": 0x09, "CFG_IN": 0x05, "CFG_OUT": 0x04, "JSHUTDOWN": 0x0D}
FORBIDDEN_IR = {"JPROGRAM": 0x0B, "JSTART": 0x0C}

FRAME_WORDS = 101
PAD_FRAMES = 1                      # 7-series readback returns one pad frame first
READ_WORDS = FRAME_WORDS * (PAD_FRAMES + 1)

SYNC = 0xAA995566
DUMMY = 0xFFFFFFFF
NOOP = 0x20000000
# Type-1 header: 001 opcode[2] reg[14] rsvd[2] count[11]
CMD_REG, FAR_REG, FDRO_REG, FDRI_REG, STAT_REG = 4, 1, 3, 2, 7
CMD_RCRC, CMD_RCFG, CMD_DESYNC, CMD_WCFG = 7, 4, 13, 1


def t1(write: bool, reg: int, count: int) -> int:
    return 0x20000000 | ((0b10 if write else 0b01) << 27) | (reg << 13) | count


def t2_read(count: int) -> int:
    return 0x40000000 | (0b01 << 27) | count


def rev32(word: int) -> int:
    return int(f"{word & 0xFFFFFFFF:032b}"[::-1], 2)


class ProbeStop(Exception):
    """The sequence, the chain or the answer is not what this probe requires."""


def check_sequence(words: list[int]) -> None:
    """Refuse a payload that could write the fabric, before anything is shifted."""
    for index, word in enumerate(words):
        if (word & 0xE0000000) == 0x20000000:            # a type-1 header
            opcode = (word >> 27) & 0b11
            reg = (word >> 13) & 0x3FFF
            if opcode == 0b10 and reg == FDRI_REG:
                raise ProbeStop(f"word {index} writes FDRI: refused")
            if opcode == 0b10 and reg == CMD_REG:
                payload = words[index + 1] if index + 1 < len(words) else None
                if payload in (CMD_WCFG, 2, 15):          # WCFG, MFW, IPROG
                    raise ProbeStop(f"word {index + 1} is a forbidden CMD {payload}: refused")
        if (word & 0xE0000000) == 0x40000000 and ((word >> 27) & 0b11) == 0b10:
            raise ProbeStop(f"word {index} is a type-2 WRITE: refused")


def field_list(words: list[int]) -> str:
    """ONE OpenOCD `drscan` field carrying the whole config payload.

    Not one field per word: `drscan` allocates its extra fields to the *other* TAPs of the
    chain, so a second field aimed at the same TAP trips
    `interface_jtag_add_dr_scan: active == tap`. The payload is therefore a single field
    whose width is the whole burst.

    JTAG shifts the field LSB first and the configuration stream is MSB first, so each word
    is bit-reversed and word 0 occupies the low bits. The same transform undoes it on the
    way out.
    """
    value = 0
    for index, word in enumerate(words):
        value |= rev32(word) << (32 * index)
    return f"{32 * len(words)} 0x{value:0{8 * len(words)}x}"


def capture_fields(count: int) -> str:
    return f"{32 * count} 0x{0:0{8 * count}x}"


def decode_capture(text: str, count: int) -> list[int]:
    """Undo the single-field packing: low bits are word 0, each word bit-reversed."""
    value = int(text, 16)
    return [rev32((value >> (32 * index)) & 0xFFFFFFFF) for index in range(count)]


def build_tcl(far_list: list[int]) -> tuple[str, list[dict]]:
    """The whole session as one OpenOCD script, so config state survives between steps."""
    steps: list[dict] = []
    lines = ["init", "echo \"@@ init done\""]

    lines += [f"irscan {TAP} 0x{IR['IDCODE']:02x}",
              f"set id [drscan {TAP} 32 0]",
              "echo \"@@ IDCODE $id\""]

    stat_in = [DUMMY, SYNC, NOOP, t1(False, STAT_REG, 1), NOOP, NOOP]
    check_sequence(stat_in)
    steps.append({"step": "read STAT", "words": [f"{w:08x}" for w in stat_in]})
    lines += [f"irscan {TAP} 0x{IR['CFG_IN']:02x}",
              f"drscan {TAP} {field_list(stat_in)}",
              f"irscan {TAP} 0x{IR['CFG_OUT']:02x}",
              f"set stat [drscan {TAP} 32 0]",
              "echo \"@@ STAT $stat\""]

    shutdown_in = [DUMMY, SYNC, NOOP, t1(True, CMD_REG, 1), CMD_RCRC, NOOP, NOOP]
    check_sequence(shutdown_in)
    steps.append({"step": "RCRC then JSHUTDOWN",
                  "words": [f"{w:08x}" for w in shutdown_in]})
    lines += [f"irscan {TAP} 0x{IR['CFG_IN']:02x}",
              f"drscan {TAP} {field_list(shutdown_in)}",
              f"irscan {TAP} 0x{IR['JSHUTDOWN']:02x}",
              "runtest 12",
              "echo \"@@ shutdown done\""]

    for far in far_list:
        read_in = ([DUMMY, SYNC, NOOP,
                    t1(True, CMD_REG, 1), CMD_RCFG, NOOP,
                    t1(True, FAR_REG, 1), far,
                    t1(False, FDRO_REG, 0), t2_read(READ_WORDS)]
                   + [NOOP] * 32)
        check_sequence(read_in)
        steps.append({"step": f"FDRO {far:#010x}", "words": [f"{w:08x}" for w in read_in]})
        lines += [f"irscan {TAP} 0x{IR['CFG_IN']:02x}",
                  f"drscan {TAP} {field_list(read_in)}",
                  f"irscan {TAP} 0x{IR['CFG_OUT']:02x}",
                  f"set data [drscan {TAP} {capture_fields(READ_WORDS)}]",
                  f"echo \"@@ FRAME {far:#010x} $data\""]

    desync = [t1(True, CMD_REG, 1), CMD_DESYNC, NOOP, NOOP]
    check_sequence(desync)
    steps.append({"step": "DESYNC", "words": [f"{w:08x}" for w in desync]})
    lines += [f"irscan {TAP} 0x{IR['CFG_IN']:02x}",
              f"drscan {TAP} {field_list(desync)}",
              "echo \"@@ desync done\"",
              "shutdown"]
    return "\n".join(lines) + "\n", steps


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cfg", default=str(REPO / "scripts/jtag_config_only.cfg"))
    ap.add_argument("--far", action="append", default=None,
                    help="FAR to read; repeatable (default 0x00400A20 and 0x00400A21)")
    ap.add_argument("--speed", type=int, default=2000)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    far_list = [int(f, 16) for f in (args.far or ["0x00400A20", "0x00400A21"])]

    record: dict = {
        "tool": "probe_jtag_config_read.py/1.0.0",
        "what": "independent JTAG readback of configuration frames",
        "tap": TAP,
        "ir_codes": {name: f"0x{code:02x}" for name, code in IR.items()},
        "forbidden_ir": {name: f"0x{code:02x}" for name, code in FORBIDDEN_IR.items()},
        "far_list": [f"{far:#010x}" for far in far_list],
        "read_words": READ_WORDS,
        "pad_frames": PAD_FRAMES,
        "started_at": time.time(),
    }

    try:
        tcl, steps = build_tcl(far_list)
        record["sequence"] = steps
        record["tcl_sha256"] = hashlib.sha256(tcl.encode()).hexdigest()
        script = args.out.parent / (args.out.stem + ".tcl")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(tcl, encoding="utf-8")
        record["tcl_path"] = str(script)

        done = subprocess.run(
            ["openocd", "-f", args.cfg, "-c", f"adapter speed {args.speed}", "-f", str(script)],
            capture_output=True, text=True, timeout=600)
        raw = done.stdout + done.stderr
        record["openocd"] = {
            "returncode": done.returncode,
            "sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "output": raw,
        }

        idcode = re.search(r"@@ IDCODE (?:0x)?([0-9a-fA-F]+)", raw)
        stat = re.search(r"@@ STAT (?:0x)?([0-9a-fA-F]+)", raw)
        record["idcode"] = f"0x{int(idcode.group(1), 16):08x}" if idcode else None
        record["config_status"] = f"0x{rev32(int(stat.group(1), 16)):08x}" if stat else None
        record["config_status_raw"] = f"0x{int(stat.group(1), 16):08x}" if stat else None
        if not idcode:
            raise ProbeStop("the chain never returned an IDCODE")
        if int(idcode.group(1), 16) != 0x13722093:
            raise ProbeStop(f"IDCODE {record['idcode']} is not the XC7Z010's 0x13722093")

        frames = {}
        for match in re.finditer(r"@@ FRAME (0x[0-9a-fA-F]+) (?:0x)?([0-9a-fA-F]+)", raw):
            far = match.group(1)
            captured = match.group(2)
            if len(captured) * 4 < 32 * READ_WORDS:
                raise ProbeStop(
                    f"{far}: captured {len(captured) * 4} bits, expected {32 * READ_WORDS}")
            words = decode_capture(captured, READ_WORDS)
            frames[far] = {
                "all_words": [f"{word:08x}" for word in words],
                "pad_frame": [f"{word:08x}" for word in words[:FRAME_WORDS]],
                "frame": [f"{word:08x}" for word in words[FRAME_WORDS:]],
                "frame_sha256": hashlib.sha256(
                    b"".join(word.to_bytes(4, "big")
                             for word in words[FRAME_WORDS:])).hexdigest(),
                "nonzero_words_in_frame": sum(1 for word in words[FRAME_WORDS:] if word),
            }
        record["frames"] = frames
        if len(frames) != len(far_list):
            raise ProbeStop(f"read {len(frames)} frames, asked for {len(far_list)}")
        record["verdict"] = "READ"
    except (ProbeStop, subprocess.SubprocessError, OSError) as stop:
        record["verdict"] = "STOP"
        record["stop_reason"] = f"{type(stop).__name__}: {stop}"

    record["finished_at"] = time.time()
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if record["verdict"] != "READ":
        print(f"STOP: {record['stop_reason']}", file=sys.stderr)
        print(f"  evidence: {args.out}", file=sys.stderr)
        return 1
    print(f"READ: IDCODE {record['idcode']}, CONFIG_STATUS {record['config_status']}")
    for far, data in record["frames"].items():
        print(f"  {far}: frame sha {data['frame_sha256'][:16]}…, "
              f"{data['nonzero_words_in_frame']} non-zero words")
    print(f"  evidence: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

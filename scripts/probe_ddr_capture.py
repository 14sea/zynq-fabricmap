#!/usr/bin/env python3
"""Read-only forensic capture of a DRAM frame slot. It never touches the carrier.

`pass2_line()` copies every readback frame to `CAPTURE_ADDR` under the readback watchdog,
so after a fault the failing frame's 101 words are still in DRAM. This tool reads that
archive and nothing else: `printenv plmark`, then one `md.l`. There is no AXI access, no
acknowledgement, no reload and no new transaction — a fault state is left exactly as it was
found, so a later analysis is looking at the run that produced it.

Why not `probe_stage_dump.py`: that one reads `board_uboot_axi.RDBACK`, which is the
carrier's own window. Reading the carrier after a fault is a different act with different
risks, and it is not what this capture needs.

The whole reply is preserved — bytes, base64, text and a sha256 — because a truncated
capture already cost this project one wrong conclusion.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import serial  # noqa: E402
import board_serial as bs  # noqa: E402

# The DRAM archive written by pass2_line(). Deliberately a literal: this tool must not
# import a module that could point it at a peripheral window instead.
CAPTURE_ADDR = 0x10100000
FRAME_WORDS = 101
SLOT_BYTES = FRAME_WORDS * 4
# `pass2_line()` archives one slot per frame of the whole transaction. A slot outside that
# range is not a frame of this run, so the tool refuses rather than reading arbitrary DRAM.
SLOTS = 15

MD_LINE = re.compile(
    rb"^([0-9a-fA-F]{8}):((?:\s+[0-9a-fA-F]{8})+)", re.MULTILINE)


class CaptureStop(Exception):
    """The board is not in the state this capture is only meaningful in."""


def parse_words(reply: bytes, base: int) -> list[int]:
    """Every word of an `md.l` dump, in address order, with the addresses checked."""
    words: list[int] = []
    for match in MD_LINE.finditer(reply):
        addr = int(match.group(1), 16)
        row = [int(w, 16) for w in match.group(2).split()]
        if addr != base + len(words) * 4:
            raise CaptureStop(
                f"md line address {addr:#010x} is not the expected "
                f"{base + len(words) * 4:#010x}; the dump is not contiguous")
        words.extend(row)
    return words


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", default="/dev/ebaz-uart")
    ap.add_argument("--plmark", required=True,
                    help="the marker the failing run set; a different one means a restart, "
                         "and a restart takes the DRAM archive's provenance with it")
    ap.add_argument("--slot", type=int, default=0,
                    help=f"which of the archived frames, 0..{SLOTS - 1} "
                         "(0 = the first, the failing one)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if not 0 <= args.slot < SLOTS:
        ap.error(f"--slot must be in 0..{SLOTS - 1}; {args.slot} is not a frame of this run")

    addr = CAPTURE_ADDR + args.slot * SLOT_BYTES
    record: dict = {
        "tool": "probe_ddr_capture.py/1.1.0",
        "what": "read-only DRAM capture of an archived readback frame",
        "slot": args.slot,
        "address": f"{addr:#010x}",
        "words_requested": FRAME_WORDS,
        "expected_plmark": args.plmark,
        "started_at": time.time(),
        "commands": [],
    }

    def record_reply(line: str, reply: bytes) -> None:
        record["commands"].append({
            "command": line,
            "bytes": len(reply),
            "sha256": hashlib.sha256(reply).hexdigest(),
            "base64": base64.b64encode(reply).decode("ascii"),
            "text": reply.decode("ascii", "replace"),
        })

    def ask(ser, line: str, timeout: float) -> bytes:
        """Send one named command, keep the whole reply, and judge it before returning.

        Every reply is recorded, including the sync: a capture that says three commands were
        sent has to be able to show all three. A banner means the board rebooted and the
        DRAM archive is gone; a missing prompt means the reply is not a complete answer, and
        neither may be read past.
        """
        reply = bs.ub_cmd(ser, line, timeout=timeout)
        record_reply(line, reply)
        if bs.BOOT_BANNER_RE.search(reply):
            raise CaptureStop(f"a boot banner came back with `{line}`: the board restarted")
        if not bs.PROMPT_RE.search(reply):
            raise CaptureStop(f"no prompt after `{line}`: {reply[-120:]!r}")
        return reply

    try:
        with serial.Serial(args.port, bs.BAUD, timeout=0.1) as ser:
            # Same named no-op `sync_prompt` uses; never a bare CR, which U-Boot would read
            # as "repeat the last command".
            ask(ser, bs.SYNC_COMMAND, 3.0)

            line = "printenv plmark"
            reply = ask(ser, line, 3.0)
            found = re.search(rb"plmark=([0-9a-f]+)", reply)
            if not found:
                raise CaptureStop(f"plmark is not set; the board restarted: {reply[-120:]!r}")
            actual = found.group(1).decode("ascii")
            record["plmark"] = actual
            if actual != args.plmark:
                raise CaptureStop(
                    f"plmark is {actual}, the failing run set {args.plmark}: this is a "
                    "different boot and the DRAM archive is not that run's")

            line = f"md.l 0x{addr:08x} 0x{FRAME_WORDS:x}"
            reply = ask(ser, line, 15.0)
            words = parse_words(reply, addr)
            if len(words) != FRAME_WORDS:
                raise CaptureStop(f"parsed {len(words)} words, expected {FRAME_WORDS}")

        record["words"] = [f"{w:08x}" for w in words]
        record["nonzero_words"] = sum(1 for w in words if w)
        record["frame_sha256"] = hashlib.sha256(
            b"".join(w.to_bytes(4, "big") for w in words)).hexdigest()
        record["verdict"] = "CAPTURED"
    except (CaptureStop, OSError) as stop:
        record["verdict"] = "STOP"
        record["stop_reason"] = f"{type(stop).__name__}: {stop}"

    record["finished_at"] = time.time()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    if record["verdict"] != "CAPTURED":
        print(f"STOP: {record['stop_reason']}", file=sys.stderr)
        print(f"  evidence: {args.out}", file=sys.stderr)
        return 1
    print(f"CAPTURED slot {args.slot} at {addr:#010x}: {FRAME_WORDS} words, "
          f"{record['nonzero_words']} non-zero, sha256 {record['frame_sha256'][:16]}…")
    print(f"  evidence: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

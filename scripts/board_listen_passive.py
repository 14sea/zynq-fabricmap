#!/usr/bin/env python3
"""Listen to the board and say nothing. A supply baseline, not an experiment.

Board 17A6 restarted on its own inside a 128-second window in which nothing touched it
(`evidence/isolate_additive_2026_08_12/`). That makes the restart rate the measurement that
decides whether any further sequencing work is worth doing, and the only way to measure it
honestly is to stop being a participant: if the host sends anything at all, a restart can
always be blamed on the host.

So this script has **no transmit path**. It never calls `write`, never sends a newline, a
keepalive or a query, and `tests/test_listen_passive.py` checks that as a property of the
source rather than as an intention. Opening the port asserts DTR/RTS, which on this board
was tested and does nothing (toggling either or both, with the port open, has no effect) —
that is the one unavoidable side effect and it is recorded rather than hidden.

What it records
---------------
Every byte, with the wall-clock and monotonic time of the chunk it arrived in; every
`U-Boot SPL` banner with the time it appeared and the interval since the previous one; every
disconnect and reconnect of the CH340, which drops off USB during a brownout and comes back
under a different `ttyUSBN`; and the listener's own state at the start and at the end.

Both clocks are kept because they answer different questions: monotonic measures intervals
and cannot jump, wall-clock lets a restart be lined up against anything else that happened.

The run always lasts its full duration. An early restart is a reason to keep listening, not
to stop: one restart gives a rate of "at least one", and only a second gives an interval.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_serial as bs  # noqa: E402

try:
    import serial
except ImportError:  # pragma: no cover - board-host dependency
    print("pyserial is required", file=sys.stderr)
    raise

TOOL_VERSION = "board_listen_passive.py/1.0.0"

# The first line the ROM's SPL prints. Anything matching this is a boot that nobody asked
# for, because this script cannot ask for one.
SPL_RE = re.compile(rb"U-Boot SPL")
UBOOT_RE = re.compile(rb"\r?\nU-Boot \d")


def now() -> dict:
    return {"wall": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "mono": round(time.monotonic(), 3)}


def listener_state(port: str, ser, what: str) -> dict:
    """The listener, not the board. Nothing here touches the far end of the cable."""
    real = os.path.realpath(port) if os.path.exists(port) else None
    return {
        "what": what,
        **now(),
        "port": port,
        "resolves_to": real,
        "port_exists": os.path.exists(port),
        "device_node_exists": bool(real and os.path.exists(real)),
        "is_open": bool(ser is not None and getattr(ser, "is_open", False)),
        "baudrate": getattr(ser, "baudrate", None),
    }


def timestamp_for_offset(chunks: list[dict], offset: int) -> dict:
    """Which chunk did the byte at `offset` arrive in? Used to date a banner."""
    seen = 0
    for chunk in chunks:
        length = len(base64.b64decode(chunk["b64"]))
        if offset < seen + length:
            return {"wall": chunk["wall"], "mono": chunk["mono"]}
        seen += length
    return {"wall": None, "mono": None}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", default=bs.PORT)
    ap.add_argument("--minutes", type=float, default=30.0)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    record: dict = {
        "tool": TOOL_VERSION,
        "what": "passive supply baseline: receive only, zero transmit",
        "port": args.port,
        "planned_minutes": args.minutes,
        "transmit": "none — this tool has no write path at all",
        "board_touched": "no: no bytes sent, no power change, no JTAG, no reset line driven",
        "caveat_dtr_rts": ("opening the port asserts DTR/RTS. On this board both were tested "
                           "with the port open and neither does anything, but the reopen "
                           "times are recorded so any correlation stays visible."),
        "events": [],
        "chunks": [],
    }

    def flush() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    def note(kind: str, **detail) -> None:
        event = {"kind": kind, **now(), **detail}
        record["events"].append(event)
        print(f"[{event['wall']}] {kind} {detail if detail else ''}", flush=True)
        flush()

    deadline = time.monotonic() + args.minutes * 60.0
    ser = None
    started = now()
    record["started"] = started

    try:
        ser = serial.Serial(args.port, 115200, timeout=0.2)
        record["listener_at_start"] = listener_state(args.port, ser, "at the start")
        note("listening", resolves_to=record["listener_at_start"]["resolves_to"])
        print(f"    receive only, {args.minutes:.0f} min, nothing will be sent", flush=True)

        while time.monotonic() < deadline:
            try:
                data = ser.read(4096)
            except (OSError, serial.SerialException) as gone:
                note("disconnected", error=str(gone))
                try:
                    ser.close()
                except Exception:                  # noqa: BLE001
                    pass
                ser = None
                # Wait for the node to come back. Polling the filesystem is not touching
                # the board.
                while time.monotonic() < deadline:
                    if os.path.exists(args.port):
                        try:
                            ser = serial.Serial(args.port, 115200, timeout=0.2)
                            note("reconnected",
                                 resolves_to=os.path.realpath(args.port))
                            break
                        except (OSError, serial.SerialException):
                            pass
                    time.sleep(0.25)
                if ser is None:
                    break
                continue

            if data:
                stamp = now()
                record["chunks"].append({**stamp, "b64": base64.b64encode(data).decode()})
                text = data.decode("ascii", "replace").strip()
                if text:
                    print(f"    <- {text[:120]!r}", flush=True)
                if SPL_RE.search(data):
                    note("SPL banner — the board booted, and nobody asked it to")
                flush()

        record["listener_at_end"] = listener_state(args.port, ser, "at the end")
        note("finished", planned_minutes=args.minutes)
    finally:
        if ser is not None:
            try:
                if "listener_at_end" not in record:
                    record["listener_at_end"] = listener_state(args.port, ser, "at the end")
                ser.close()
            except Exception:                      # noqa: BLE001
                pass

        raw = b"".join(base64.b64decode(chunk["b64"]) for chunk in record["chunks"])
        record["bytes_received"] = len(raw)
        record["raw_b64"] = base64.b64encode(raw).decode()

        restarts = [timestamp_for_offset(record["chunks"], match.start())
                    for match in SPL_RE.finditer(raw)]
        for index, restart in enumerate(restarts):
            if index and restart["mono"] is not None and restarts[index - 1]["mono"] is not None:
                restart["seconds_since_previous"] = round(
                    restart["mono"] - restarts[index - 1]["mono"], 3)
        record["restarts"] = restarts
        record["restart_count"] = len(restarts)
        record["uboot_banner_count"] = len(UBOOT_RE.findall(raw))
        record["elapsed_s"] = round(time.monotonic() - (deadline - args.minutes * 60.0), 1)
        record["disconnect_count"] = sum(
            1 for event in record["events"] if event["kind"] == "disconnected")

        intervals = [r["seconds_since_previous"] for r in restarts
                     if "seconds_since_previous" in r]
        record["restart_intervals_s"] = intervals
        flush()

        print(f"\n--- {record['elapsed_s']:.0f} s of listening, nothing sent")
        print(f"    bytes received : {record['bytes_received']}")
        print(f"    SPL banners    : {record['restart_count']}"
              + (f"  intervals {intervals} s" if intervals else ""))
        print(f"    disconnects    : {record['disconnect_count']}")
        if record["restart_count"] == 0:
            print("    NO unprompted restart in this window. That is a real result: it does "
                  "not clear the supply, it bounds the rate.")
        print(f"  record: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

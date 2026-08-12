#!/usr/bin/env python3
"""Does closing the serial port restart the board? Ten interleaved pairs, one variable.

Sixty minutes of purely passive listening produced no restart in either PL state, while both
restarts ever observed happened in or around active runs that opened and closed the port
repeatedly. That is a pattern, not a finding, and this is the experiment that can turn it
into one -- or kill it.

The pairing
-----------

**A: hold open.** The port stays open for the whole interval. Nothing is sent.

**B: close for real.** The port is closed and the interval passes with the device node held
by nobody, then it is reopened.

Interleaved, same interval, same volatile marker within a pair, so a disappearance is
attributable to the trial it followed rather than to the run as a whole.

Why nothing else may hold the tty
---------------------------------

A tty hangs up -- and DTR drops -- on the **last** close, not on any close. A second process
sitting on the same device node would keep the count above zero and make B a hold-open trial
wearing B's name, which is the one way this experiment could produce a confident wrong
answer. So `holders_of()` reads `/proc/*/fd` and B refuses to proceed unless the count is
zero after this process lets go. A udev/USB monitor may run alongside; it does not open the
node.

Reading the result
------------------

After a reopen, bytes are collected **before** the marker is asked for: a restart announces
itself with an SPL banner, and asking first would put a transmit in front of the evidence.
Either signal -- a banner, or the marker gone -- ends the run with that pair's timeline kept
whole.

What a result may be called
---------------------------

If the close/open trials show events and the hold-open trials do not, the most that may be
said is that **restarts are associated with the serial port's lifecycle**. Not that DTR/RTS
cause it: a close drops DTR *and* can hang the line up *and* can re-enumerate the CH340, and
this experiment does not separate those.

This never reads a carrier AXI address, runs no calibration, attaches no JTAG and reloads
nothing.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import secrets
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

TOOL_VERSION = "board_probe_tty_lifecycle.py/1.0.0"

SPL_RE = re.compile(rb"U-Boot SPL")
MARKER_VAR = "ttyprobe"

# The trial kinds, and the order they alternate in. A pair is one of each.
HOLD_OPEN = "A: hold the port open"
CLOSE_OPEN = "B: close the last fd, wait, reopen"


def now() -> dict:
    return {"wall": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "mono": round(time.monotonic(), 3)}


def holders_of(node: str) -> list[str]:
    """Which processes hold this device node open, by reading /proc rather than asking one.

    B is only B if the count reaches zero, so this is load-bearing rather than advisory.
    """
    held = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            for fd in (proc / "fd").iterdir():
                try:
                    if os.path.realpath(fd) == node:
                        held.append(proc.name)
                        break
                except OSError:
                    continue
        except (OSError, PermissionError):
            continue
    return held


class Console:
    """A port that can be genuinely let go of, and a marker that cannot survive a restart."""

    def __init__(self, port: str):
        self.port = port
        self.node = os.path.realpath(port)
        self.serial: serial.Serial | None = None
        self.log: list[dict] = []

    def open(self) -> None:
        self.serial = serial.Serial(self.port, 115200, timeout=0.2)
        self.node = os.path.realpath(self.port)

    def close(self) -> None:
        if self.serial is not None:
            self.serial.close()
            self.serial = None

    def drain(self, seconds: float) -> bytes:
        """Collect whatever arrives, sending nothing. This is how a restart is caught."""
        got = b""
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            waiting = self.serial.in_waiting
            if waiting:
                got += self.serial.read(waiting)
            else:
                time.sleep(0.01)
        return got

    def command(self, line: str, timeout: float = 5.0) -> bytes:
        self.serial.reset_input_buffer()
        bs.write_paced(self.serial, line.encode("ascii") + b"\r")
        buf = b""
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            waiting = self.serial.in_waiting
            if waiting:
                buf += self.serial.read(waiting)
                if bs.PROMPT_RE.search(buf):
                    break
            else:
                time.sleep(0.005)
        self.log.append({**now(), "command": line,
                         "raw_b64": base64.b64encode(buf).decode(),
                         "raw": buf.decode("ascii", "replace")})
        return buf

    def set_marker(self) -> str:
        """RAM only. `saveenv` is never called, so a restart takes the marker with it."""
        nonce = secrets.token_hex(8)
        self.command(f"setenv {MARKER_VAR} {nonce}")
        reply = self.command(f"printenv {MARKER_VAR}")
        if f"{MARKER_VAR}={nonce}".encode() not in reply:
            raise RuntimeError(f"the marker did not take: {reply!r}")
        return nonce

    def marker_survives(self, nonce: str) -> tuple[bool, bytes]:
        reply = self.command(f"printenv {MARKER_VAR}")
        return f"{MARKER_VAR}={nonce}".encode() in reply, reply


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", default=bs.PORT)
    ap.add_argument("--pairs", type=int, default=10)
    ap.add_argument("--interval", type=float, default=30.0,
                    help="seconds each trial waits — identical for A and B")
    ap.add_argument("--settle", type=float, default=2.0,
                    help="seconds of passive collection after a reopen, before any transmit")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    record: dict = {
        "tool": TOOL_VERSION,
        "what": "is a restart associated with the serial port's lifecycle?",
        "design": ("interleaved pairs; A holds the port open for the interval, B closes the "
                   "LAST fd for the same interval and reopens; one volatile marker per pair; "
                   "after a reopen, bytes are collected before the marker is asked for"),
        "not_done": "no carrier AXI read, no calibration, no JTAG, no reload, no power change",
        "port": args.port,
        "pairs_planned": args.pairs,
        "interval_s": args.interval,
        "started": now(),
        "trials": [],
    }

    def flush() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    console = Console(args.port)
    stop: str | None = None
    try:
        console.open()
        record["device_node"] = console.node
        record["holders_at_start"] = holders_of(console.node)

        for pair in range(1, args.pairs + 1):
            nonce = console.set_marker()
            print(f"\n=== pair {pair}: marker {nonce}", flush=True)

            for kind in (HOLD_OPEN, CLOSE_OPEN) if pair % 2 else (CLOSE_OPEN, HOLD_OPEN):
                trial: dict = {"pair": pair, "kind": kind, "marker": nonce,
                               "started": now()}
                collected = b""

                if kind == HOLD_OPEN:
                    collected = console.drain(args.interval)
                    trial["holders_during"] = [os.getpid()]
                else:
                    console.close()
                    held = holders_of(console.node)
                    trial["holders_after_close"] = held
                    if held:
                        trial["refused"] = (
                            "another process still holds the node, so the last fd never "
                            f"closed and this would not be a B trial: pids {held}")
                        record["trials"].append(trial)
                        stop = trial["refused"]
                        break
                    time.sleep(args.interval)
                    console.open()
                    # Collect BEFORE transmitting: a restart announces itself, and a
                    # question asked first would put a transmit ahead of the evidence.
                    collected = console.drain(args.settle)

                trial["bytes_collected"] = len(collected)
                trial["collected_b64"] = base64.b64encode(collected).decode()
                trial["spl_banner"] = bool(SPL_RE.search(collected))
                survives, reply = console.marker_survives(nonce)
                trial["marker_survives"] = survives
                trial["marker_reply"] = reply.decode("ascii", "replace")
                trial["ended"] = now()
                record["trials"].append(trial)
                print(f"    {kind}: {trial['bytes_collected']} bytes, "
                      f"SPL={int(trial['spl_banner'])}, marker={'kept' if survives else 'GONE'}",
                      flush=True)
                flush()

                if trial["spl_banner"] or not survives:
                    stop = (f"pair {pair}, {kind}: "
                            + ("an SPL banner arrived" if trial["spl_banner"]
                               else "the marker is gone")
                            + " — the board restarted")
                    break
            if stop:
                break

        record["stopped_early"] = stop
        record["verdict"] = stop or "no restart in any trial"
    finally:
        try:
            console.close()
        except Exception:                          # noqa: BLE001
            pass
        record["console_log"] = console.log
        record["ended"] = now()

        by_kind = {HOLD_OPEN: [], CLOSE_OPEN: []}
        for trial in record["trials"]:
            if "refused" not in trial:
                by_kind[trial["kind"]].append(
                    bool(trial.get("spl_banner")) or not trial.get("marker_survives", True))
        record["events_by_kind"] = {kind: {"trials": len(flags), "events": sum(flags)}
                                    for kind, flags in by_kind.items()}
        flush()

        print("\n--- events by trial kind")
        for kind, tally in record["events_by_kind"].items():
            print(f"    {kind:38s} {tally['events']} event(s) in {tally['trials']} trial(s)")
        print(f"    verdict: {record['verdict']}")
        print("    Wording: events in B and none in A would support 'restarts are ASSOCIATED "
              "WITH the port lifecycle'. It would NOT single out DTR/RTS — a close also hangs "
              "the line up and can re-enumerate the CH340.")
        print(f"  record: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

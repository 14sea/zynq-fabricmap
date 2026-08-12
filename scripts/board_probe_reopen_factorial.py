#!/usr/bin/env python3
"""Which part of a console reopen restarts the board: the short gap, the CR, or both?

Three restarts have coincided with a console close/reopen, and ten deliberate last-fd closes
produced none. The two paths differ in exactly two ways, and this varies them one at a time:

    condition   close -> open   writes b"\\r"   tcflush purge
    A                    30 s   no             no
    B              back-to-back  no             no
    C                    30 s   yes            no
    D              back-to-back  yes            no
    F              back-to-back  no             YES
    E              back-to-back  yes            YES   <- the historical production path

A-D were run first, and they varied a THIRD thing without saying so: to keep the settle
bytes, `reset_input_buffer()` had been replaced by a read. Those are not equivalent -- the
first is `tcflush(TCIFLUSH)`, a purge issued to the tty layer and the USB-serial driver --
so a null result across A-D cannot clear the historical path, because removing the purge may
have removed the trigger with it. E and F put the purge back, keeping the captured bytes as
well; E is exactly the path the three restarts went through, and F is its control, the only
way to separate the purge from the CR.

E goes LAST: it is the likeliest to fire, and a restart ends the run.

Why this imports `Probe` instead of opening a port of its own
-------------------------------------------------------------

A is meant to detect an unlisted difference between the production reopen and a hand-written
one. A hand-written reopen here would BE such a difference, and the experiment would be
measuring its own scaffolding. So the real `board_isolate_carrier.Probe` is used, with
`send_cr` the only thing this module is allowed to vary; the open, the termios setup, the
0.4 s settle and the close are production's own.

Reading the result (the user's rules, kept where they will be read again)
------------------------------------------------------------------------
* **A fires** — the Probe path differs from the A/B `Console` in some way NOT listed here.
* **B fires** — a short gap alone is sufficient.
* **C fires** — the CR / Probe-open path alone is sufficient.
* **Only D fires** — supports an interaction between the two, and only then.
* **Nothing fires** — one more non-reproduction. It does NOT clear the path, and it is NOT
  a licence to start the calibration.

The carrier is read ONCE, as a baseline, to establish that it answers. After that no AXI
address is touched: a stall would cost a power cycle and answer nothing this asks.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_isolate_carrier as iso  # noqa: E402
import board_serial as bs  # noqa: E402
import board_uboot_axi as axi  # noqa: E402
from board_probe_tty_lifecycle import SPL_RE, holders_of  # noqa: E402

TOOL_VERSION = "board_probe_reopen_factorial.py/1.0.0"

DEFAULT_RUN = REPO_ROOT / "gate_runs/claimb_round1_carrier_2026_08_11_erratum002"

# (name, seconds the node stays closed, CR on open, tcflush purge on open)
#
# A-D vary gap x CR with the purge REMOVED, which is a third variable I changed without
# saying so; a null result across them cannot clear the historical path, because removing
# the purge may have removed the trigger with it. E and F put the purge back.
#
# E is the historical production path exactly -- back-to-back, CR, purge -- and goes LAST,
# because a restart ends the run and it is the likeliest to fire. F is its control: the same
# purge with no CR, which is the only way to tell the purge and the CR apart.
CONDITIONS = [
    ("A", 30.0, False, False),
    ("B", 0.0, False, False),
    ("C", 30.0, True, False),
    ("D", 0.0, True, False),
    ("F", 0.0, False, True),
    ("E", 0.0, True, True),
]

INTERPRETATION = {
    "A": "the Probe path differs from the A/B Console in a way not listed in this experiment",
    "B": "a short close->open gap alone is sufficient",
    "C": "the CR / Probe-open path alone is sufficient",
    "D": "supports an interaction between the short gap and the CR, and only that",
    "F": "the tcflush purge alone is sufficient — the CR is not needed",
    "E": "the historical path reproduces; with F clean, the purge needs the CR beside it",
}


def now() -> dict:
    return {"wall": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "mono": round(time.monotonic(), 3)}


class UdevWatch:
    """USB/tty events, from a process that never opens the UART node."""

    HEADER_LINES = 2

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("w")
        self.proc = subprocess.Popen(
            ["udevadm", "monitor", "--udev",
             "--subsystem-match=usb", "--subsystem-match=tty"],
            stdout=self.handle, stderr=subprocess.STDOUT)
        time.sleep(0.5)

    def events(self) -> list[str]:
        self.handle.flush()
        lines = [line for line in self.path.read_text(errors="replace").splitlines()
                 if line.strip()]
        return lines[self.HEADER_LINES:]

    def stop(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:            # pragma: no cover
            self.proc.kill()
        self.handle.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--port", default=bs.PORT)
    ap.add_argument("--trials", type=int, default=5, help="per condition, at most")
    ap.add_argument("--settle", type=float, default=2.0,
                    help="passive collection after the reopen, before the marker is asked for")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    carrier = args.run_dir / "carrier.bit"
    bundle = json.loads((args.run_dir / "carrier_run.json").read_text("utf-8"))
    digest = hashlib.sha256(carrier.read_bytes()).hexdigest()

    record: dict = {
        "tool": TOOL_VERSION,
        "what": "which half of a console reopen is associated with the restart",
        "conditions": [{"name": n, "gap_s": g, "sends_cr": c, "purges": p}
                       for n, g, c, p in CONDITIONS],
        "order": "A, B, C, D, F, E — E is the historical production path and goes last",
        "interpretation": INTERPRETATION,
        "not_done": "no carrier AXI after the baseline, no calibration, no JTAG, no reload",
        "carrier_sha256": digest,
        "carrier_sha256_pinned": bundle["artifacts"]["carrier.bit"]["sha256"],
        "trials_per_condition": args.trials,
        "started": now(),
        "trials": [],
    }

    def flush() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    if digest != record["carrier_sha256_pinned"]:
        record["verdict"] = "STOP: the carrier on disk is not the published one"
        flush()
        return 1

    watch = UdevWatch(args.out.parent / "udev_monitor.txt")
    console_log: list[dict] = []
    probe = None
    stop: str | None = None
    try:
        # Load, then take ONE baseline read, then never touch the fabric again.
        record["load"] = iso.run_tool(
            [sys.executable, str(REPO_ROOT / "scripts/board_uboot_fpga_load.py"),
             "--port", args.port, "--bit", str(carrier), "--op", "loadb"],
            "fpga loadb of the published carrier")
        if record["load"]["returncode"] != 0:
            raise iso.Stalled("the load failed; nothing after it would mean anything")
        found = re.search(r"\[plmark\] ([0-9a-f]+)", record["load"]["stdout_tail"])
        marker = found.group(1) if found else None
        if not marker:
            raise iso.Stalled("the loader reported no plmark, so no restart could be detected")
        record["plmark"] = marker
        flush()

        probe = iso.Probe(args.port)
        status, _ = probe.read_word(axi.STATUS, "carrier STATUS (the one baseline read)")
        record["baseline_status"] = f"0x{status:08x}"
        print(f"    baseline STATUS = 0x{status:08x}", flush=True)
        if status != 0x00000080:
            raise iso.Stalled(
                f"the baseline read is 0x{status:08x}, not the reset state 0x00000080")
        flush()

        for name, gap, sends_cr, purges in CONDITIONS:
            print(f"\n=== condition {name}: gap {gap:.0f} s, CR = {sends_cr}, purge = {purges}",
                  flush=True)
            for attempt in range(1, args.trials + 1):
                trial: dict = {"condition": name, "attempt": attempt, "gap_planned_s": gap,
                               "sends_cr": sends_cr, "purges": purges, "started": now()}

                console_log.extend(probe.log)
                probe.log.clear()
                probe.close()
                node = str(Path(args.port).resolve())
                held = holders_of(node)
                trial["holders_after_close"] = held
                if held:
                    trial["refused"] = (f"the last fd did not close — pids {held} still hold "
                                        f"{node}, so this would not be condition {name}")
                    record["trials"].append(trial)
                    stop = trial["refused"]
                    break

                closed_at = time.monotonic()
                if gap:
                    time.sleep(gap)
                # Measured BEFORE the constructor, because Probe's own 0.4 s settle happens
                # inside it: timing after it would report a 7 ms gap as 0.407 s.
                opened_at = time.monotonic()
                probe = iso.Probe(args.port, send_cr=sends_cr, purge=purges)
                trial["gap_close_to_open_s"] = round(opened_at - closed_at, 4)
                trial["gap_close_to_ready_s"] = round(time.monotonic() - closed_at, 4)

                # Whatever the settle window would have discarded, plus a passive window.
                collected = probe.discarded_on_open
                until = time.monotonic() + args.settle
                while time.monotonic() < until:
                    waiting = probe.serial.in_waiting
                    if waiting:
                        collected += probe.serial.read(waiting)
                    else:
                        time.sleep(0.01)

                trial["collected_b64"] = base64.b64encode(collected).decode()
                trial["bytes_collected"] = len(collected)
                trial["spl_banner"] = bool(SPL_RE.search(collected))

                entry = probe.cmd("printenv plmark")
                trial["marker_survives"] = f"plmark={marker}" in entry["raw"]
                trial["marker_reply"] = entry["raw"][:400]
                trial["udev_events"] = watch.events()
                trial["ended"] = now()
                record["trials"].append(trial)
                print(f"    {name}.{attempt}: gap {trial['gap_close_to_open_s']:.4f} s, "
                      f"{trial['bytes_collected']} bytes, SPL={int(trial['spl_banner'])}, "
                      f"marker={'kept' if trial['marker_survives'] else 'GONE'}, "
                      f"udev={len(trial['udev_events'])}", flush=True)
                flush()

                if trial["spl_banner"] or not trial["marker_survives"] or trial["udev_events"]:
                    reason = ("an SPL banner arrived" if trial["spl_banner"]
                              else "the marker is gone" if not trial["marker_survives"]
                              else f"a USB/tty event fired: {trial['udev_events']}")
                    stop = (f"condition {name}, attempt {attempt}: {reason}. "
                            f"Reading: {INTERPRETATION[name]}.")
                    break
            if stop:
                break

        record["stopped_at"] = stop
        record["verdict"] = stop or "no event in any condition"
    except iso.Stalled as refusal:
        record["verdict"] = "STOP"
        record["stop_reason"] = str(refusal)
        print(f"\nSTOP: {refusal}", file=sys.stderr)
    finally:
        try:
            if probe is not None:
                console_log.extend(probe.log)
                probe.close()
        except Exception:                            # noqa: BLE001
            pass
        record["console_log"] = console_log
        record["udev_events_total"] = watch.events()
        watch.stop()
        record["ended"] = now()

        tally: dict = {}
        for trial in record["trials"]:
            if "refused" in trial:
                continue
            slot = tally.setdefault(trial["condition"], {"trials": 0, "events": 0})
            slot["trials"] += 1
            slot["events"] += int(bool(trial["spl_banner"])
                                  or not trial["marker_survives"]
                                  or bool(trial["udev_events"]))
        record["by_condition"] = tally
        flush()

        print("\n--- events by condition")
        for name, _, _, _ in CONDITIONS:
            slot = tally.get(name)
            print(f"    {name}: " + (f"{slot['events']} event(s) in {slot['trials']} trial(s)"
                                     if slot else "not reached"))
        print(f"    verdict: {record['verdict']}")
        if not stop:
            print("    Nothing fired. That is one more non-reproduction — it does not clear "
                  "the reopen path, and it is not a licence to start the calibration.")
        print(f"  record: {args.out}")
    return 0 if record["verdict"] == "no event in any condition" else 1


if __name__ == "__main__":
    sys.exit(main())

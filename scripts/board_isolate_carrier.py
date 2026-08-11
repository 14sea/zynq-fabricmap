#!/usr/bin/env python3
"""Which step stops the carrier answering? One power cycle, one answer, all of it recorded.

The calibration's first AXI read stalls. A hand-run `fpga loadb` of the same file, from the
same script, then answered `0x00000080` — `carrier_stream`'s exact reset state — through
both U-Boot and the JTAG mem_ap. So the carrier works and the failure is **sequence
dependent**, and the honest description of the root cause is *not yet known*. This runs the
steps one at a time and reads the carrier after each, so the failing step names itself.

Four things about the method, each of which came from getting it wrong first
---------------------------------------------------------------------------

**PCFG_DONE is sticky and write-1-to-clear.** Seeing it set *after* a load does not show
that *this* load produced a completion event — it may have been left over from the previous
one. The loader's check read `0x50021004` and the fabric still did not answer. So every load
here is bracketed: clear the bit, **confirm it reads 0**, load, and require it to be 1. An
edge, not a level.

**No JTAG in the main sequence.** A successful mem_ap probe is harmless, but it is another
master touching the same bus and the point of this run is to change one thing at a time.
Diagnosis by JTAG happens after the sequence has ended, never inside it.

**`board_set_fclk50.py` runs with `--verify-only`.** It is read-only when the clock is
already 50 MHz, but "is read-only in the case I expect" is not a property of a diagnostic
step. The flag makes it one.

**Every reply is kept verbatim.** A U-Boot data abort and a stalled CPU both end with no
prompt and mean opposite things — the abort is the fabric answering with an error, silence
is the fabric not answering at all. That distinction was lost once because the bytes were
discarded; here the raw reply, the elapsed time and the artifact hashes all go into the
record.

This writes nothing to the fabric. It reads the carrier's status window and clears one
write-1-to-clear interrupt bit in the PS; there is no ICAP activity and no candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_serial as bs  # noqa: E402
import board_uboot_axi as axi  # noqa: E402

try:
    import serial
except ImportError:  # pragma: no cover - board-host dependency
    print("pyserial is required", file=sys.stderr)
    raise

TOOL_VERSION = "board_isolate_carrier.py/1.0.0"

DEFAULT_RUN = REPO_ROOT / "gate_runs/claimb_round1_carrier_2026_08_11_erratum002"

# devcfg, and the PS clock/reset registers that would explain a dead slave. All PS — none of
# them can stall, unlike anything in the PL window.
DEVCFG_CTRL = 0xF8007000
DEVCFG_INT_STS = 0xF800700C
DEVCFG_STATUS = 0xF8007014
PCFG_DONE = 1 << 2
PCAP_PR = 1 << 27

PS_SURVEY = [
    (0xF8000170, "FPGA0_CLK_CTRL"),
    (0xF8000178, "FPGA0_THR_CNT (bit0 = FCLK0 gate, 1 = off)"),
    (0xF8000240, "FPGA_RST_CTRL (non-zero = FCLKRESETN held)"),
    (0xF8000900, "LVL_SHFTR_EN (0xF = PS-PL boundary open)"),
    (DEVCFG_CTRL, "devcfg CTRL (bit27 PCAP_PR, bit30 PCFG_PROG_B)"),
    (DEVCFG_INT_STS, "devcfg INT_STS (bit2 PCFG_DONE, W1C)"),
    (DEVCFG_STATUS, "devcfg STATUS"),
    (0xF8000530, "PSS_IDCODE"),
]


class Stalled(Exception):
    """The console did not come back. Nothing after this means anything."""


class Probe:
    """One open console, every exchange recorded."""

    def __init__(self, port: str):
        self.port = port
        self.serial = serial.Serial(port, 115200, timeout=0)
        self.serial.write(b"\r")
        time.sleep(0.4)
        self.serial.reset_input_buffer()
        self.log: list[dict] = []

    def cmd(self, line: str, timeout: float = 8.0) -> dict:
        self.serial.reset_input_buffer()
        started = time.time()
        self.serial.write(line.encode("ascii") + b"\r")
        buf = b""
        while time.time() - started < timeout:
            waiting = self.serial.in_waiting
            if waiting:
                buf += self.serial.read(waiting)
                if bs.PROMPT_RE.search(buf):
                    break
            else:
                time.sleep(0.001)
        entry = {
            "command": line,
            "elapsed_s": round(time.time() - started, 3),
            "prompt_returned": bool(bs.PROMPT_RE.search(buf)),
            "exception": bool(axi.ABORT_RE.search(buf)),
            "raw": buf.decode("ascii", "replace"),
        }
        self.log.append(entry)
        return entry

    def read_word(self, addr: int, what: str = "") -> tuple[int | None, dict]:
        entry = self.cmd(f"md.l 0x{addr:08x} 0x1")
        entry["what"] = what
        if not entry["prompt_returned"]:
            raise Stalled(
                f"{what or hex(addr)}: "
                + ("the CPU took an exception — the fabric ANSWERED with an error"
                   if entry["exception"] else
                   "no prompt and no exception — the fabric did not answer at all")
                + f". Received: {entry['raw']!r}")
        try:
            value = axi.parse_md(entry["raw"].encode("ascii", "replace"), addr, 1)[0]
        except axi.AxiRefusal as refusal:
            raise Stalled(f"{what or hex(addr)}: unparseable reply — {refusal}") from None
        entry["value"] = f"0x{value:08x}"
        return value, entry

    def close(self) -> None:
        self.serial.close()


def survey(probe: Probe, when: str) -> dict:
    out = {}
    print(f"\n--- PS registers {when}")
    for addr, name in PS_SURVEY:
        value, _ = probe.read_word(addr, name)
        out[f"{addr:#010x}"] = {"name": name, "value": f"0x{value:08x}"}
        print(f"    {addr:#010x} {name:44s} 0x{value:08x}")
    return out


def clear_pcfg_done(probe: Probe, when: str) -> dict:
    """Clear the sticky bit and CONFIRM it reads zero, so the next load proves an edge."""
    before, _ = probe.read_word(DEVCFG_INT_STS, "INT_STS before clear")
    probe.cmd(f"mw 0x{DEVCFG_INT_STS:08x} 0x{PCFG_DONE:08x} 1")
    after, _ = probe.read_word(DEVCFG_INT_STS, "INT_STS after clear")
    print(f"    {when}: INT_STS 0x{before:08x} -> 0x{after:08x}  "
          f"PCFG_DONE={'1' if after & PCFG_DONE else '0'}")
    if after & PCFG_DONE:
        raise Stalled(
            f"PCFG_DONE did not clear (INT_STS 0x{after:08x}); a later 1 would prove nothing")
    return {"before": f"0x{before:08x}", "after": f"0x{after:08x}"}


def read_carrier(probe: Probe, when: str) -> dict:
    """The measurement everything else exists to interpret."""
    status, entry = probe.read_word(axi.STATUS, f"carrier STATUS ({when})")
    fault, _ = probe.read_word(axi.FAULT, f"carrier FAULT ({when})")
    decoded = axi.decode_status(status)
    print(f"    {when}: STATUS=0x{status:08x} FAULT=0x{fault:08x}  "
          f"busy={int(decoded['busy'])} fault={int(decoded['fault'])} "
          f"recovery={int(decoded['recovery_required'])} "
          f"reserved=0x{decoded['reserved']:08x}")
    return {"status": f"0x{status:08x}", "fault": f"0x{fault:08x}",
            "decoded": {k: (v if not isinstance(v, bool) else int(v))
                        for k, v in decoded.items() if k != "raw"},
            "elapsed_s": entry["elapsed_s"]}


def run_tool(argv: list[str], what: str) -> dict:
    print(f"\n=== {what}")
    started = time.time()
    done = subprocess.run(argv, capture_output=True, text=True)
    print(f"    rc={done.returncode} in {time.time() - started:.1f}s")
    for line in (done.stdout or "").strip().splitlines()[-4:]:
        print(f"    | {line}")
    return {"what": what, "argv": argv[1:], "returncode": done.returncode,
            "elapsed_s": round(time.time() - started, 1),
            "stdout_tail": done.stdout[-1200:], "stderr_tail": done.stderr[-400:]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--port", default=bs.PORT)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    carrier = args.run_dir / "carrier.bit"
    bundle = json.loads((args.run_dir / "carrier_run.json").read_text("utf-8"))
    digest = hashlib.sha256(carrier.read_bytes()).hexdigest()
    pinned = bundle["artifacts"]["carrier.bit"]["sha256"]

    record: dict = {
        "tool": TOOL_VERSION,
        "what": "isolate the step that stops the carrier answering",
        "started_at": time.time(),
        "run_dir": args.run_dir.name,
        "carrier_sha256": digest,
        "carrier_sha256_pinned": pinned,
        "steps": [],
    }
    print(f"carrier {carrier.name} sha256 {digest[:16]}… "
          f"({'matches' if digest == pinned else 'DOES NOT MATCH'} the bundle pin)")
    if digest != pinned:
        record["verdict"] = "STOP: the carrier on disk is not the published one"
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return 1

    probe = Probe(args.port)
    try:
        # 1. everything as found, before anything is touched.
        record["ps_before"] = survey(probe, "as found (step 1)")

        # 2/3. clear, confirm zero, load, require the edge.
        record["steps"].append({"step": "clear PCFG_DONE (step 2)",
                                "int_sts": clear_pcfg_done(probe, "step 2")})
        probe.close()
        record["steps"].append(run_tool(
            [sys.executable, str(REPO_ROOT / "scripts/board_uboot_fpga_load.py"),
             "--port", args.port, "--bit", str(carrier), "--op", "loadb"],
            "step 3: fpga loadb of the published carrier"))
        probe = Probe(args.port)
        done_after, _ = probe.read_word(DEVCFG_INT_STS, "INT_STS after load")
        print(f"    step 3: INT_STS=0x{done_after:08x} "
              f"PCFG_DONE={'1' if done_after & PCFG_DONE else '0'}")
        record["steps"].append({"step": "PCFG_DONE after load (step 3)",
                                "int_sts": f"0x{done_after:08x}",
                                "pcfg_done": bool(done_after & PCFG_DONE)})
        if not done_after & PCFG_DONE:
            raise Stalled("PCFG_DONE did not go 0 -> 1: this load did not configure the PL")

        # 4. the first reading that matters, and then the two things that happen around
        #    every later one, separated. Step 5 used to bundle three changes — time passing,
        #    the console being closed and reopened, and a tool being run — and a step that
        #    bundles three changes cannot name a cause.
        record["steps"].append({"step": "read carrier (step 4a, right after load)",
                                "carrier": read_carrier(probe, "4a right after load")})

        time.sleep(6)
        record["steps"].append({"step": "read carrier (step 4b, +6s, same console)",
                                "carrier": read_carrier(probe, "4b after 6s")})

        probe.close()
        probe = Probe(args.port)
        record["steps"].append({"step": "read carrier (step 4c, after closing and "
                                        "reopening the console, no tool run)",
                                "carrier": read_carrier(probe, "4c after reopen")})

        # 5/6. the clock check, explicitly read-only, then read again.
        probe.close()
        record["steps"].append(run_tool(
            [sys.executable, str(REPO_ROOT / "scripts/board_set_fclk50.py"),
             "--port", args.port, "--verify-only"],
            "step 5: board_set_fclk50.py --verify-only"))
        probe = Probe(args.port)
        record["steps"].append({"step": "read carrier (step 6, after fclk50)",
                                "carrier": read_carrier(probe, "after fclk50")})

        # 7. the identity gate, then read again.
        probe.close()
        record["steps"].append(run_tool(
            [sys.executable, str(REPO_ROOT / "scripts/gate_board_identity.py"),
             "--port", args.port],
            "step 7: gate_board_identity.py"))
        probe = Probe(args.port)
        record["steps"].append({"step": "read carrier (step 7, after identity)",
                                "carrier": read_carrier(probe, "after identity")})

        # 8. a second load onto the now-configured PL, bracketed the same way.
        record["steps"].append({"step": "clear PCFG_DONE (step 8)",
                                "int_sts": clear_pcfg_done(probe, "step 8")})
        probe.close()
        record["steps"].append(run_tool(
            [sys.executable, str(REPO_ROOT / "scripts/board_uboot_fpga_load.py"),
             "--port", args.port, "--bit", str(carrier), "--op", "loadb"],
            "step 8: second fpga loadb, onto a configured PL"))
        probe = Probe(args.port)
        done_again, _ = probe.read_word(DEVCFG_INT_STS, "INT_STS after second load")
        record["steps"].append({"step": "PCFG_DONE after second load (step 8)",
                                "int_sts": f"0x{done_again:08x}",
                                "pcfg_done": bool(done_again & PCFG_DONE)})
        print(f"    step 8: INT_STS=0x{done_again:08x} "
              f"PCFG_DONE={'1' if done_again & PCFG_DONE else '0'}")
        if not done_again & PCFG_DONE:
            raise Stalled("the second load did not produce a PCFG_DONE edge")
        record["steps"].append({"step": "read carrier (step 8, after reload)",
                                "carrier": read_carrier(probe, "after reload")})

        record["ps_after"] = survey(probe, "at the end")
        record["verdict"] = "every step kept the carrier answering"
        print("\nEVERY STEP KEPT THE CARRIER ANSWERING — the failure is in none of them.")
    except Stalled as stop:
        record["verdict"] = "STOP"
        record["stop_reason"] = str(stop)
        print(f"\nSTOP: {stop}", file=sys.stderr)
    finally:
        record["console_log"] = probe.log
        try:
            probe.close()
        except Exception:                      # noqa: BLE001 - the port may be gone
            pass
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"  record: {args.out}")

    return 0 if record["verdict"] != "STOP" else 1


if __name__ == "__main__":
    sys.exit(main())

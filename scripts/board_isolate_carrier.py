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

Two modes
---------

``--mode ladder`` is the original: every step, one at a time, reading the carrier after each.

``--mode snapshot`` is shorter and answers a narrower question. A run with the ladder's
steps present stalled on the first carrier read even though every guard passed, so the
remaining question is what the PS looked like *at that instant* — and nothing was asking.
Snapshot mode does exactly: clear PCFG_DONE, load, confirm the same boot, photograph the
live PS state in ONE command line, write that to disk, and only then take the single read
that can stall.

Two things about "is the PL configured *now*", both of which had to be got wrong first:
`INT_STS.PCFG_DONE` is a sticky W1C EVENT bit and answers only about the past; and
`STATUS.PCFG_INIT`, though live, is the INIT_B pin — measured 1 on this board when
UNCONFIGURED (`0x40000A30`) *and* when configured (`0x40000F30`), so it discriminates
nothing. What this snapshot leans on instead is the empirical difference between those two
measured values, recorded as such.
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

DEFAULT_RUN = REPO_ROOT / "gate_runs/claimb_round1_carrier_2026_08_13_erratum006"

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

# --- the snapshot: live PS state, read on ONE command line, immediately before the one
# --- read that can stall. Order is the reviewer's, and it is deliberate.
#
# **`INT_STS.PCFG_DONE` cannot answer the question this snapshot exists to ask.** It is a
# sticky write-1-to-clear EVENT bit: it says "a load completed at some point since the last
# clear", which is a fact about the past, not about now.
#
# **And neither can `PCFG_INIT`** — which is the correction this file was nearly written
# without. `DEVCFG STATUS` bit 4 is live, but it is the INIT_B pin: U-Boot's own PROG_B
# sequence (`zynqpl.c`, "wait for INIT to clear" then "wait for INIT to set") uses it to mean
# *the PL has finished its internal clear and is ready to be configured*. It is 1 whether or
# not a bitstream is loaded, and this board's own measurements say so: fresh power-on and
# UNCONFIGURED reads `0x40000A30`, and CONFIGURED reads `0x40000F30` — bit 4 set in both.
# So PCFG_INIT = 0 is meaningful (the PL is mid-clear, or a configuration CRC failed) while
# PCFG_INIT = 1 discriminates NOTHING.
#
# What did move between those two measured states is bits 8 and 10. This file has no
# authority for their names — U-Boot's header defines only the four bits it uses — so they
# are recorded as an EMPIRICAL discriminator against the two reference values, and reported
# as such. An unnamed bit that demonstrably tracks the state is worth more than a named bit
# that does not, provided the record says which one it is.
#
# Every address below is in the PS. None of them can stall the CPU, unlike anything in the
# PL window — which is why the whole snapshot is taken before the carrier is touched at all.
PCFG_INIT = 1 << 4
FCLK0_GATE_OFF = 1 << 0

# Both measured on board 17A6, both recorded in evidence/isolate_2026_08_12*/record.json.
STATUS_UNCONFIGURED_REF = 0x40000A30
STATUS_CONFIGURED_REF = 0x40000F30
STATUS_CONFIG_BITS = STATUS_UNCONFIGURED_REF ^ STATUS_CONFIGURED_REF   # 0x500 — bits 8, 10

SNAPSHOT = [
    (0xF8000170, "FPGA0_CLK_CTRL"),
    (0xF8000178, "FPGA0_THR_CNT"),
    (0xF8000240, "FPGA_RST_CTRL"),
    (0xF8000900, "LVL_SHFTR_EN"),
    (DEVCFG_CTRL, "devcfg CTRL"),
    (DEVCFG_STATUS, "devcfg STATUS"),      # live PCFG_INIT — the point of the exercise
    (DEVCFG_INT_STS, "devcfg INT_STS"),    # historical event record only
]


def parse_survey(reply: bytes, addrs: list[int]) -> dict[int, int]:
    """Pull one word per address out of a reply holding several `md.l` dumps.

    `axi.parse_md` deliberately refuses a buffer whose address column does not run
    consecutively from one base, which is exactly right for a single `md.l` and exactly
    wrong here: this buffer holds seven unrelated single-word dumps. So the lines are
    indexed by their own address column and every requested address must appear exactly
    once. A duplicate is refused rather than resolved, because the obvious resolutions
    (first wins, last wins) would silently paper over an echo or a wrapped line.
    """
    seen: dict[int, list[int]] = {}
    for match in axi.MD_LINE_RE.finditer(reply):
        words = [int(token, 16) for token in match.group(2).split()]
        seen.setdefault(int(match.group(1), 16), []).extend(words)
    missing = [a for a in addrs if a not in seen]
    if missing:
        raise Stalled(
            "the snapshot line did not come back complete — no value for "
            + ", ".join(f"{a:#010x}" for a in missing)
            + f". Received: {reply[-300:]!r}")
    duplicated = [a for a in addrs if len(seen[a]) != 1]
    if duplicated:
        raise Stalled(
            "the snapshot line returned more than one value for "
            + ", ".join(f"{a:#010x}" for a in duplicated)
            + f". Received: {reply[-300:]!r}")
    return {a: seen[a][0] for a in addrs}


def judge_snapshot(values: dict[int, int]) -> dict:
    """Say what the live PS state means, and name anything that is not as it must be.

    The judgement is separated from the reading so it can be tested without a board, and so
    a future run's numbers can be re-judged without re-running the board.
    """
    clk_ctrl = values[0xF8000170]
    thr_cnt = values[0xF8000178]
    rst_ctrl = values[0xF8000240]
    lvl = values[0xF8000900]
    ctrl = values[DEVCFG_CTRL]
    status = values[DEVCFG_STATUS]
    int_sts = values[DEVCFG_INT_STS]

    judged = {
        # Live, but NOT a configured/unconfigured discriminator — see the note above.
        "pcfg_init": bool(status & PCFG_INIT),
        # The empirical one. Neither reading is proof; both are better than PCFG_INIT.
        "status": f"0x{status:08x}",
        "status_config_bits": f"0x{status & STATUS_CONFIG_BITS:03x} of 0x{STATUS_CONFIG_BITS:03x}",
        "looks_configured": (status & STATUS_CONFIG_BITS) == STATUS_CONFIG_BITS,
        "matches_configured_ref": status == STATUS_CONFIGURED_REF,
        "matches_unconfigured_ref": status == STATUS_UNCONFIGURED_REF,
        "fclk0_gated_off": bool(thr_cnt & FCLK0_GATE_OFF),
        "fpga_reset_held": rst_ctrl != 0,
        "level_shifters_open": lvl == 0xF,
        "pcap_pr": bool(ctrl & PCAP_PR),
        "pcfg_done_event": bool(int_sts & PCFG_DONE),
        "fpga0_clk_ctrl": f"0x{clk_ctrl:08x}",
    }
    problems = []
    if not judged["pcfg_init"]:
        problems.append(
            "PCFG_INIT (STATUS bit 4) is 0 — the PL is mid-clear or a configuration CRC "
            "failed. (A 1 here would have proved nothing either way.)")
    if judged["matches_unconfigured_ref"]:
        problems.append(
            f"devcfg STATUS is 0x{status:08x}, this board's measured UNCONFIGURED value — "
            "the load did not stick, whatever the sticky PCFG_DONE event bit says")
    elif not judged["looks_configured"]:
        problems.append(
            f"devcfg STATUS is 0x{status:08x}: of the bits that moved between this board's "
            f"measured unconfigured (0x{STATUS_UNCONFIGURED_REF:08x}) and configured "
            f"(0x{STATUS_CONFIGURED_REF:08x}) values, only "
            f"0x{status & STATUS_CONFIG_BITS:03x} is set")
    if judged["fclk0_gated_off"]:
        problems.append("FPGA0_THR_CNT bit0 is 1 — FCLK0 is gated OFF, so the slave has no clock")
    if judged["fpga_reset_held"]:
        problems.append(f"FPGA_RST_CTRL is 0x{rst_ctrl:08x} — FCLKRESETN is held asserted")
    if not judged["level_shifters_open"]:
        problems.append(f"LVL_SHFTR_EN is 0x{lvl:08x}, not 0xF — the PS-PL boundary is not open")
    judged["problems"] = problems
    return judged


class Stalled(Exception):
    """The console did not come back. Nothing after this means anything."""


class Probe:
    """One open console, every exchange recorded."""

    def __init__(self, port: str, *, purge: bool = True):
        """Open the console. **Nothing is transmitted here, and nothing may be.**

        This used to write a bare `\\r` to settle the console, and that CR caused three
        "spontaneous restarts". The chain is closed in source, every link checked:

        1. U-Boot declares `md` repeatable — `U_BOOT_CMD(md, 3, 1, do_mem_md)`,
           `cmd/mem.c:1318` — so an empty line RE-RUNS the last command.
        2. `do_mem_md` resumes from `addr = dp_last_addr` (`cmd/mem.c:79`), and the previous
           call left `dp_last_addr = addr + bytes` (`:110`, `:113`). After
           an `md.l` of the FAULT register that is **FAULT + 4** — not a re-read of
           FAULT, the NEXT word. (Named as an offset: the window's absolute address
           belongs to `board_uboot_axi` alone, which is a rule with a test behind it.)
        3. The carrier decodes `+0x0004` and `+0x0008` and a score window from `+0x0010`;
           `0x200c` is none of them, so it answers **SLVERR** — `carrier_axil.v:217`,
           correct and deliberate strictness.
        4. The A9 takes a data abort: `do_data_abort` → `bad_mode()` →
           `panic("Resetting CPU ...")` (`arch/arm/lib/interrupts.c:198`, `:55`).
        5. `CONFIG_PANIC_HANG` is not set in this build (`.config:1145`), so `panic_finish()`
           calls `do_reset()` — `lib/panic.c:28`. The board reboots.
        6. The settle then PURGED the "data abort" text, leaving only the SPL banner that
           arrived later. That is why it looked like an unexplained spontaneous restart.

        So the restarts were never spontaneous and never a supply fault: **the instrument
        rebooted the board and then deleted the message saying so.** If a sync is ever needed
        here, it must be a named, explicit, harmless COMPLETE command — never a bare CR,
        whose meaning depends on whatever was typed last.

        The settle bytes are KEPT in `discarded_on_open` rather than flushed away — step 6
        above is what that costs when they are not. The purge still happens after the read,
        because `reset_input_buffer()` is `tcflush(TCIFLUSH)`, an operation on the tty layer
        and the USB-serial driver, and a read is not a substitute for it; the buffer ends up
        empty either way but the driver call is not the same one.
        """
        self.port = port
        self.serial = serial.Serial(port, 115200, timeout=0)
        time.sleep(0.4)
        self.discarded_on_open = self.serial.read(self.serial.in_waiting)
        if purge:
            self.serial.reset_input_buffer()
        self.log: list[dict] = []

    def cmd(self, line: str, timeout: float = 8.0) -> dict:
        # Read before flushing. Anything already waiting here is unsolicited — a boot
        # banner, or a "data abort" register dump from the PREVIOUS command — and flushing
        # it blind was the second window through which this instrument destroyed the
        # evidence for what it was investigating.
        pending = self.serial.read(self.serial.in_waiting)
        self.serial.reset_input_buffer()
        started = time.time()
        # Paced, not a single write: U-Boot echoes with a BLOCKING putc, and while it blocks
        # on a full TX FIFO it stops draining RX and loses input. The snapshot line is the
        # longest thing this script sends.
        bs.write_paced(self.serial, line.encode("ascii") + b"\r")
        buf = b""
        while time.time() - started < timeout:
            waiting = self.serial.in_waiting
            if waiting:
                buf += self.serial.read(waiting)
                if bs.PROMPT_RE.search(buf):
                    break
            else:
                time.sleep(0.001)
        rebooted = bool(bs.BOOT_BANNER_RE.search(buf))
        entry = {
            "command": line,
            "elapsed_s": round(time.time() - started, 3),
            # A rebooted board offers a prompt indistinguishable from a good one, so the
            # banner decides first and `prompt_returned` is only meaningful without it.
            "rebooted": rebooted,
            "prompt_returned": bool(bs.PROMPT_RE.search(buf)) and not rebooted,
            "exception": bool(axi.ABORT_RE.search(buf)),
            "raw": buf.decode("ascii", "replace"),
            "pending_before": pending.decode("ascii", "replace"),
            "pending_was_an_abort": bool(axi.ABORT_RE.search(pending)),
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

    def snapshot(self) -> tuple[dict[int, int], dict]:
        """Every live PS register, in one command line, in one go.

        One line rather than seven commands because U-Boot reads a line to completion before
        executing any of it: the console cost is paid up front and the seven reads then
        happen back to back, so they describe one instant rather than seven spread over a
        second of console traffic.
        """
        line = "; ".join(f"md.l 0x{addr:08x} 0x1" for addr, _ in SNAPSHOT)
        entry = self.cmd(line)
        entry["what"] = "one-line PS snapshot"
        if not entry["prompt_returned"]:
            raise Stalled(
                "the PS snapshot line did not come back — and no PS register can stall, so "
                f"this is a console or board fault, not the fabric. Received: {entry['raw']!r}")
        values = parse_survey(entry["raw"].encode("ascii", "replace"),
                              [addr for addr, _ in SNAPSHOT])
        return values, entry

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


def read_carrier(probe: Probe, when: str, marker: str | None = None) -> dict:
    """The measurement everything else exists to interpret.

    The boot marker is checked FIRST every time: a restart clears the PL, and asking the PL
    whether it is still configured is the one question that stalls the CPU when the answer
    is no. `17A6` was observed restarting between two successful reads.
    """
    if marker is not None:
        entry = probe.cmd("printenv plmark")
        if not entry["prompt_returned"]:
            raise Stalled(f"printenv plmark did not answer: {entry['raw']!r}")
        if f"plmark={marker}" not in entry["raw"]:
            raise Stalled(
                f"THE BOARD RESTARTED before '{when}': plmark is no longer {marker} "
                f"({entry['raw'].strip()!r}). The PL is cleared; reading the carrier now "
                "would stall the CPU. This is a board restart, not a carrier fault.")
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


# The steps the snapshot run leaves OUT, in the order they are added back. Each is a thing
# the failing calibration did between the load and its first read; the snapshot run did none
# of them and the carrier answered. So the first of these that stops the carrier answering
# is the cause, and the order is chosen so that a breakage names a mechanism rather than a
# tool: a bare console close/reopen comes FIRST, because both tool steps contain one, and if
# the reopen alone is fatal then the tools are bystanders.
#
# "wait" is a control, not a step: if six seconds of nothing breaks it, no step is to blame.
ADDITIVE_STEPS = [
    ("wait 6 s on the same console (control — changes nothing)", None),
    ("close and reopen the console, no tool run", None),
    ("board_set_fclk50.py --verify-only (read-only, plus a reopen)",
     ["scripts/board_set_fclk50.py", "--verify-only"]),
    ("gate_board_identity.py (the calibration's gate, plus a reopen)",
     ["scripts/gate_board_identity.py"]),
]


def run_additive(args, record: dict) -> int:
    """Add the omitted steps back one at a time, starting from a carrier that ANSWERS.

    This does not load. It is meant to run immediately after a successful snapshot run,
    against the state that run left behind, because that state is the whole experiment: a
    reload costs three and a half minutes and, on this board, is itself a suspect.

    Every step is followed by the same two reads, and the boot marker is checked before each
    of them — a spontaneous restart clears the PL, and would otherwise be recorded as the
    step's own doing.
    """
    def flush() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    marker = args.plmark
    console_log: list[dict] = []
    probe = Probe(args.port)
    try:
        # The control: it must answer BEFORE anything is added, or the run means nothing.
        record["baseline"] = read_carrier(probe, "baseline, before any step is added", marker)
        record["verdict"] = "STOP"    # until a step proves otherwise
        flush()

        for index, (what, argv) in enumerate(ADDITIVE_STEPS, start=1):
            step: dict = {"step": f"{index}. {what}"}
            if index == 1:
                time.sleep(6)
            else:
                console_log.extend(probe.log)
                probe.log.clear()
                probe.close()
                if argv:
                    step["tool"] = run_tool(
                        [sys.executable, str(REPO_ROOT / argv[0]), "--port", args.port,
                         *argv[1:]], f"step {index}: {what}")
                probe = Probe(args.port)
            print(f"\n=== after step {index}: {what}")
            step["carrier"] = read_carrier(probe, f"after step {index}", marker)
            record["steps"].append(step)
            flush()

        record["verdict"] = "every added step kept the carrier answering"
        print("\nEVERY ADDED STEP KEPT THE CARRIER ANSWERING.")
    except Stalled as stop:
        record["verdict"] = "STOP"
        record["stop_reason"] = str(stop)
        record["broken_by"] = (record["steps"][-1]["step"] if record["steps"]
                               else "the baseline read — the carrier was already silent")
        print(f"\nSTOP: {stop}", file=sys.stderr)
        print(f"  the last step that PASSED was: {record['broken_by']}", file=sys.stderr)
    finally:
        try:
            console_log.extend(probe.log)
            probe.close()
        except Exception:                      # noqa: BLE001 - the port may be gone
            pass
        record["console_log"] = console_log
        flush()
        print(f"  record: {args.out}")
    return 0 if record["verdict"] != "STOP" else 1


class RecordingTransport:
    """Forwards to a production transport and keeps every raw reply.

    A wrapper rather than an edit: the point of this ladder is to exercise the PRODUCTION
    `SerialTransport` and `BoardSession` unchanged, so nothing here may alter them — and in
    particular nothing here may create a second device-write entrypoint. Only `command` is
    intercepted; everything else is delegated untouched.
    """

    def __init__(self, inner, log: list[dict]):
        self.inner = inner
        self.log = log

    def command(self, line: str, timeout: float = 1.5) -> bytes:
        started = time.time()
        reply = self.inner.command(line, timeout)
        self.log.append({
            "command": line,
            "elapsed_s": round(time.time() - started, 3),
            "raw": reply.decode("ascii", "replace"),
            "prompt_returned": bool(bs.PROMPT_RE.search(reply)),
        })
        return reply

    def __getattr__(self, name):
        return getattr(self.inner, name)


def run_session_ladder(args, record: dict, carrier: Path) -> int:
    """Load once, then walk from the Probe path to the production session, one step at a time.

    The calibration has never once reached its first STATUS read, and every other path does.
    Between them sit three things, and this separates them without a power cycle between
    each: the production `SerialTransport` (its own open, sync and timeout), the identity
    gate's command sequence on that same session, and an in-memory authorisation.

    Nothing is reloaded, no calibration runs, `write_sequence()` is never called and no ICAP
    address is touched. Every step re-asks `plmark` first, because a restart would otherwise
    be recorded as the step's own doing.
    """
    import gate_board_identity as ident            # noqa: PLC0415 - board-only dependency

    def flush() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    console_log: list[dict] = []
    transport_log: list[dict] = []
    probe = None
    transport = None

    def carrier_reading(where: str) -> dict:
        """STATUS and FAULT through the PRODUCTION readers, and the standing requirement."""
        status = axi.read_status(transport)
        code, name = axi.read_fault(transport)
        reading = {"where": where, "status": f"0x{status['raw']:08x}",
                   "fault": f"0x{code:08x}", "fault_name": name,
                   "decoded": {k: (int(v) if isinstance(v, bool) else v)
                               for k, v in status.items() if k != "raw"}}
        print(f"    {where}: STATUS={reading['status']} FAULT={reading['fault']}", flush=True)
        if status["raw"] != 0x00000080 or code != 0:
            raise Stalled(
                f"{where}: STATUS={reading['status']} FAULT={reading['fault']}, and this "
                "ladder requires 0x00000080 / 0x00000000 at every step")
        return reading

    try:
        record["steps"].append(run_tool(
            [sys.executable, str(REPO_ROOT / "scripts/board_uboot_fpga_load.py"),
             "--port", args.port, "--bit", str(carrier), "--op", "loadb"],
            "fpga loadb of the published carrier (no --require-unconfigured, no fclk50)"))
        if record["steps"][-1]["returncode"] != 0:
            raise Stalled("the load failed; nothing after it would mean anything")
        found = re.search(r"\[plmark\] ([0-9a-f]+)", record["steps"][-1]["stdout_tail"])
        marker = found.group(1) if found else None
        if not marker:
            raise Stalled("the loader reported no plmark, so a restart could not be detected")
        record["plmark"] = marker
        flush()

        # 1. The Probe baseline. If this load did not produce a usable carrier, the rest of
        #    the ladder would be measuring the load, not the session.
        probe = Probe(args.port)
        entry = probe.cmd("printenv plmark")
        if f"plmark={marker}" not in entry["raw"]:
            raise Stalled(f"the board restarted before the baseline: {entry['raw'].strip()!r}")
        values, snap = probe.snapshot()
        record["baseline"] = {
            "snapshot": {f"{addr:#010x}": {"name": name, "value": f"0x{values[addr]:08x}"}
                         for addr, name in SNAPSHOT},
            "judged": judge_snapshot(values),
            "carrier": read_carrier(probe, "Probe baseline", marker),
        }
        if record["baseline"]["carrier"]["status"] != "0x00000080":
            raise Stalled("this load did not establish a usable baseline; stopping here "
                          "rather than attributing it to a session step")
        console_log.extend(probe.log)
        probe.log.clear()
        probe.close()
        probe = None
        flush()

        # 2. The production transport, and nothing else yet.
        transport = RecordingTransport(ident.SerialTransport(args.port), transport_log)
        axi.same_boot(transport, marker)
        record["steps"].append({
            "step": "1. production SerialTransport opened, NO identity",
            "carrier": carrier_reading("after SerialTransport open")})
        flush()

        # 3. The identity gate, on the same session.
        session = ident.BoardSession(transport)
        identity = session.verify_identity("content")
        axi.same_boot(transport, marker)
        record["steps"].append({
            "step": "2. verify_identity on the same session",
            "identity": identity["parsed"],
            "carrier": carrier_reading("after verify_identity")})
        flush()

        # 4. In-memory authorisation only. write_sequence() is NOT called and must not be.
        authorisation = session.authorise_write()
        axi.same_boot(transport, marker)
        record["steps"].append({
            "step": "3. authorise_write() — in memory only, no write_sequence, no ICAP",
            "authorised": {k: v for k, v in authorisation.items() if k != "transport"},
            "carrier": carrier_reading("after authorise_write")})

        record["verdict"] = "every session step kept the carrier answering"
        print("\nEVERY SESSION STEP KEPT THE CARRIER ANSWERING.")
    except Exception as stop:                                       # noqa: BLE001
        # Every refusal in this ladder is a stop, whatever raised it: a marker change, a
        # stall, a reading that is not 0x80/0, or an identity failure. Naming the type in
        # the record is what tells them apart afterwards.
        record["verdict"] = "STOP"
        record["stop_reason"] = f"{type(stop).__name__}: {stop}"
        record["broken_after"] = (record["steps"][-1].get("step")
                                  if record["steps"] else "the load or the Probe baseline")
        print(f"\nSTOP: {stop}", file=sys.stderr)
    finally:
        if probe is not None:
            console_log.extend(probe.log)
        for handle in (probe, transport):
            try:
                if handle is not None:
                    handle.close()
            except Exception:                                       # noqa: BLE001
                pass
        record["console_log"] = console_log
        record["transport_log"] = transport_log
        flush()
        print(f"  record: {args.out}")
    return 0 if record["verdict"] != "STOP" else 1


def run_first_touch(args, record: dict, carrier: Path) -> int:
    """Can the production transport be the FIRST thing that ever touches this PL?

    Every successful run so far let a `Probe` read the carrier before anything else did, and
    the calibration does not: its transport's read is the first PL access after the load.
    That is the difference this cell exists to test, so it deliberately accepts an ambiguity
    the earlier cells were built to avoid — with no baseline read, a stall cannot be split
    between "this load was bad" and "the transport cannot be first". A baseline would change
    the question rather than sharpen it.

    So: the production `phase_setup` verbatim (fclk50, then the loader WITH
    `--require-unconfigured`), then `SerialTransport`, then `same_boot`, then ONE reading of
    STATUS and FAULT. No identity gate, no PS snapshot — neither is part of the calibration's
    prefix — no second read, and nothing near the ICAP.

    A missing or changed `plmark` is recorded as a RESTART, not a stall. They are different
    events and only one of them is about the transport.
    """
    import board_calibrate_noop as cal              # noqa: PLC0415 - board-only dependency
    import gate_board_identity as ident             # noqa: PLC0415

    def flush() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    transport_log: list[dict] = []
    transport = None
    bundle = json.loads((args.run_dir / "carrier_run.json").read_text("utf-8"))

    try:
        record["setup"] = cal.phase_setup(
            args.port, carrier, bundle["artifacts"]["carrier.bit"]["sha256"])
        marker = record["setup"]["plmark"]
        print(f"    plmark {marker}", flush=True)
        flush()

        opened_at = time.monotonic()
        transport = RecordingTransport(ident.SerialTransport(args.port), transport_log)
        record["transport_open_s"] = round(time.monotonic() - opened_at, 4)

        try:
            axi.same_boot(transport, marker)
        except axi.AxiRefusal as restarted:
            record["verdict"] = "RESTART"
            record["restart_reason"] = str(restarted)
            print(f"\nRESTART (not a stall): {restarted}", file=sys.stderr)
            return 1

        # The one reading this cell exists for. Nothing before it has touched the PL.
        began = time.monotonic()
        status = axi.read_status(transport)
        code, name = axi.read_fault(transport)
        record["first_touch"] = {
            "status": f"0x{status['raw']:08x}",
            "fault": f"0x{code:08x}",
            "fault_name": name,
            "seconds_from_transport_open_to_status": round(began - opened_at, 4),
            "seconds_reading": round(time.monotonic() - began, 4),
            "decoded": {k: (int(v) if isinstance(v, bool) else v)
                        for k, v in status.items() if k != "raw"},
        }
        print(f"    FIRST TOUCH: STATUS={record['first_touch']['status']} "
              f"FAULT={record['first_touch']['fault']}", flush=True)
        if status["raw"] == 0x00000080 and code == 0:
            record["verdict"] = "the production transport CAN be the first PL master"
            print("\nFIRST TOUCH SUCCEEDED — transport-first-touch is ruled out.")
        else:
            record["verdict"] = "STOP"
            record["stop_reason"] = (
                f"the first touch read STATUS={record['first_touch']['status']} "
                f"FAULT={record['first_touch']['fault']}, not 0x00000080 / 0x00000000")
            print(f"\nSTOP: {record['stop_reason']}", file=sys.stderr)
    except Exception as stop:                                       # noqa: BLE001
        record["verdict"] = "STOP"
        record["stop_reason"] = f"{type(stop).__name__}: {stop}"
        record["reading"] = (
            "first-touch cell FAILED. A single run cannot split the load from the transport; "
            "repeat it unchanged on the next fresh boot before treating the pre-first-access "
            "path as load-bearing.")
        print(f"\nSTOP: {stop}", file=sys.stderr)
    finally:
        try:
            if transport is not None:
                transport.close()
        except Exception:                                           # noqa: BLE001
            pass
        record["transport_log"] = transport_log
        flush()
        print(f"  record: {args.out}")
    return 0 if record["verdict"].startswith("the production transport") else 1


def run_identity_first_touch(args, record: dict, carrier: Path) -> int:
    """The calibration's pre-read prefix, exactly, and then the one read it never reaches.

    Everything in that prefix has now been cleared individually, and the transport has been
    cleared as a first PL master. The one combination left untested is identity WITHOUT a
    prior carrier read — every earlier success let a `Probe` read the fabric before the
    identity gate ran, and the calibration does not.

    So this is `phase_setup`, `SerialTransport`, `BoardSession`, `verify_identity`,
    `same_boot`, then STATUS — and FAULT only if STATUS is what it must be. No authority is
    built, no host gate runs, `authorise_write()` is not called, and nothing goes near the
    ICAP. Reading the carrier earlier would pre-warm away the very thing being asked about.
    """
    import board_calibrate_noop as cal              # noqa: PLC0415 - board-only dependency
    import gate_board_identity as ident             # noqa: PLC0415

    def flush() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    transport_log: list[dict] = []
    transport = None
    bundle = json.loads((args.run_dir / "carrier_run.json").read_text("utf-8"))
    marks: dict = {}

    try:
        record["setup"] = cal.phase_setup(
            args.port, carrier, bundle["artifacts"]["carrier.bit"]["sha256"])
        marks["load_done"] = time.monotonic()
        marker = record["setup"]["plmark"]
        print(f"    plmark {marker}", flush=True)
        flush()

        transport = RecordingTransport(ident.SerialTransport(args.port), transport_log)
        session = ident.BoardSession(transport)
        marks["transport_open"] = time.monotonic()

        identity = session.verify_identity("content")
        marks["identity_done"] = time.monotonic()
        record["identity"] = identity["parsed"]
        print(f"    identity: {identity['parsed'].get('boardid')} "
              f"{identity['parsed'].get('role')}", flush=True)
        flush()

        axi.same_boot(transport, marker)

        # The read the calibration has never once completed.
        status = axi.read_status(transport)
        marks["status_done"] = time.monotonic()
        record["first_status"] = {
            "status": f"0x{status['raw']:08x}",
            "decoded": {k: (int(v) if isinstance(v, bool) else v)
                        for k, v in status.items() if k != "raw"},
        }
        print(f"    FIRST STATUS: 0x{status['raw']:08x}", flush=True)
        if status["raw"] != 0x00000080:
            raise Stalled(
                f"the first STATUS is 0x{status['raw']:08x}, not the reset state 0x00000080")

        # Only now, and only because STATUS was right.
        code, name = axi.read_fault(transport)
        record["first_fault"] = {"fault": f"0x{code:08x}", "fault_name": name}
        print(f"    FAULT: 0x{code:08x} ({name})", flush=True)
        if code != 0:
            raise Stalled(f"FAULT reads 0x{code:08x} ({name}), not 0x00000000")

        record["verdict"] = "identity x first-touch also keeps the carrier answering"
        print("\nTHE CALIBRATION'S EXACT PRE-READ PREFIX SUCCEEDS.")
    except axi.AxiRefusal as refusal:
        restarted = "plmark" in str(refusal)
        record["verdict"] = "RESTART" if restarted else "STOP"
        record["stop_reason"] = f"{type(refusal).__name__}: {refusal}"
        print(f"\n{'RESTART (not a stall)' if restarted else 'STOP'}: {refusal}",
              file=sys.stderr)
    except Exception as stop:                                       # noqa: BLE001
        record["verdict"] = "STOP"
        record["stop_reason"] = f"{type(stop).__name__}: {stop}"
        print(f"\nSTOP: {stop}", file=sys.stderr)
    finally:
        try:
            if transport is not None:
                transport.close()
        except Exception:                                           # noqa: BLE001
            pass
        def span(a: str, b: str):
            if a in marks and b in marks:
                return round(marks[b] - marks[a], 4)
            return None
        record["timings_s"] = {
            "load_done_to_transport_open": span("load_done", "transport_open"),
            "transport_open_to_identity_done": span("transport_open", "identity_done"),
            "identity_done_to_status": span("identity_done", "status_done"),
            "load_done_to_status": span("load_done", "status_done"),
        }
        record["transport_log"] = transport_log
        flush()
        for name, value in record["timings_s"].items():
            print(f"    {name:34s} {value}")
        print(f"  record: {args.out}")
    return 0 if record["verdict"].startswith("identity") else 1


def jtag_mem_ap_probe(addr: int) -> dict:
    """Read one PL word through the DAP instead of the CPU. Only ever run deliberately."""
    argv = [
        "openocd", "-f", "/home/test/test_devices/scripts/ebaz4203.cfg",
        "-c", "adapter speed 500",
        "-c", "target create zynq.ahb mem_ap -dap zynq.dap -ap-num 0",
        "-c", "init", "-c", f"zynq.ahb mdw 0x{addr:08x} 1", "-c", "shutdown",
    ]
    return run_tool(argv, f"JTAG mem_ap probe of 0x{addr:08x}")


def run_snapshot(args, record: dict, carrier: Path) -> int:
    """Load the carrier, photograph the live PS state, then take the one read that can stall.

    The whole point is the ORDER. Every register in the snapshot is in the PS and none of
    them can stall, so the picture is complete and already on disk before anything touches
    the PL window. If the carrier read then stalls, the record still says what the clock,
    the reset, the level shifters and PCFG_INIT were an instant earlier.

    Nothing else happens in between. No identity gate, no clock verify, no console reopen,
    no second load, and (unless it is asked for explicitly) no JTAG — because the previous
    run failed with all of those present and a run that changes several things at once
    cannot name which one matters.
    """
    def flush() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    # The console log accumulates across the reopen the loader forces: reassigning `probe`
    # would otherwise drop everything said before the load, which is where the PCFG_DONE
    # clear is recorded.
    console_log: list[dict] = []

    # The ONE addition this cell is allowed. `board_set_fclk50.py` runs before the load in
    # the calibration and in nothing that has ever succeeded, and that correlation has stood
    # since the first stop. It was dismissed once on the argument that the script writes
    # nothing when the clock is already 50 MHz — an argument, never a measurement, and never
    # one made in this position. So it is measured here, and whether an `mw` actually went
    # out is recorded rather than assumed.
    if args.fclk50_before_load:
        step = run_tool(
            [sys.executable, str(REPO_ROOT / "scripts/board_set_fclk50.py"),
             "--port", args.port],
            "board_set_fclk50.py BEFORE the load (production invocation, not --verify-only)")
        wrote = "writing FPGA0_CLK_CTRL" in step["stdout_tail"]
        step["issued_an_mw"] = wrote
        step["how_that_is_known"] = (
            "the write branch is the only thing that prints `writing FPGA0_CLK_CTRL=`; its "
            "absence is direct evidence the branch was not taken, and before/after values "
            "are in the output for a second reading")
        record["steps"].append(step)
        print(f"    fclk50 issued an mw: {wrote}", flush=True)
        if step["returncode"] != 0:
            raise Stalled("board_set_fclk50.py failed; the cell would not be interpretable")
        flush()

    probe = Probe(args.port)
    try:
        # Bracket the load: clear the sticky event bit and confirm it reads 0, so that a 1
        # afterwards is this load's edge and not a leftover from the last one.
        record["steps"].append({"step": "clear PCFG_DONE before the load",
                                "int_sts": clear_pcfg_done(probe, "before load")})
        console_log.extend(probe.log)
        probe.log.clear()      # so the `finally` cannot re-append what is already recorded
        probe.close()

        record["steps"].append(run_tool(
            [sys.executable, str(REPO_ROOT / "scripts/board_uboot_fpga_load.py"),
             "--port", args.port, "--bit", str(carrier), "--op", "loadb"],
            "fpga loadb of the published carrier"))
        if record["steps"][-1]["returncode"] != 0:
            raise Stalled("the load failed; nothing after it would mean anything")
        found = re.search(r"\[plmark\] ([0-9a-f]+)", record["steps"][-1]["stdout_tail"])
        marker = found.group(1) if found else None
        record["plmark"] = marker
        flush()

        if args.jtag_probe_after_load:
            record["steps"].append(jtag_mem_ap_probe(axi.STATUS))
            flush()

        # From here to the end is ONE console session, with nothing between the snapshot and
        # the read it exists to interpret.
        probe = Probe(args.port)

        if marker:
            entry = probe.cmd("printenv plmark")
            record["same_boot"] = {
                "expected": marker,
                "prompt_returned": entry["prompt_returned"],
                "matched": f"plmark={marker}" in entry["raw"],
            }
            if not record["same_boot"]["matched"]:
                raise Stalled(
                    f"the board restarted since the load — plmark is no longer {marker} "
                    f"({entry['raw'].strip()!r}). The PL is cleared; this is a restart, not "
                    "a carrier fault.")

        values, entry = probe.snapshot()
        judged = judge_snapshot(values)
        record["snapshot"] = {
            "command": entry["command"],
            "elapsed_s": entry["elapsed_s"],
            "registers": {f"{addr:#010x}": {"name": name, "value": f"0x{values[addr]:08x}"}
                          for addr, name in SNAPSHOT},
            "judged": judged,
        }
        print("\n--- live PS state, one line, immediately before the carrier read")
        for addr, name in SNAPSHOT:
            print(f"    {addr:#010x} {name:16s} 0x{values[addr]:08x}")
        print(f"    looks_configured={int(judged['looks_configured'])} "
              f"(STATUS bits {judged['status_config_bits']}, empirical)  "
              f"PCFG_INIT={int(judged['pcfg_init'])} (live, but discriminates nothing)  "
              f"PCFG_DONE_event={int(judged['pcfg_done_event'])} (sticky, historical)")
        print(f"    FCLK0_gated_off={int(judged['fclk0_gated_off'])}  "
              f"reset_held={int(judged['fpga_reset_held'])}  "
              f"lvl_shftr_open={int(judged['level_shifters_open'])}  "
              f"PCAP_PR={int(judged['pcap_pr'])}")
        for problem in judged["problems"]:
            print(f"    ANOMALY: {problem}")
        flush()          # requirement: the snapshot survives a stall on the next line

        if not judged["pcfg_done_event"]:
            raise Stalled(
                "PCFG_DONE was cleared before the load and is still 0, so this load produced "
                "no completion event at all — the carrier read is not worth taking")

        record["steps"].append({"step": "read carrier STATUS (the one read that can stall)",
                                "carrier": read_carrier(probe, "after the snapshot")})
        record["verdict"] = "the carrier ANSWERED after a direct load + snapshot"
        print("\nTHE CARRIER ANSWERED. Next: add identity, FCLK verify and a console reopen "
              "back one at a time, and the first one that breaks it is the cause.")
    except Stalled as stop:
        record["verdict"] = "STOP"
        record["stop_reason"] = str(stop)
        print(f"\nSTOP: {stop}", file=sys.stderr)
    finally:
        try:
            console_log.extend(probe.log)
            probe.close()
        except Exception:                      # noqa: BLE001 - the port may be gone
            pass
        record["console_log"] = console_log
        flush()
        print(f"  record: {args.out}")
    return 0 if record["verdict"] != "STOP" else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--port", default=bs.PORT)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--plmark", help="the boot nonce the snapshot run's load printed; "
                                     "required by --mode additive, which does not load")
    ap.add_argument("--mode",
                    choices=("ladder", "snapshot", "additive", "session-ladder",
                             "first-touch", "identity-first-touch"),
                    default="ladder",
                    help="ladder: the full step-at-a-time sequence. snapshot: load, "
                         "photograph the live PS state on one line, then the single read "
                         "that can stall — and nothing else. additive: do not load; start "
                         "from a carrier that already answers and add the omitted steps "
                         "back one at a time (needs --plmark).")
    ap.add_argument("--fclk50-before-load", action="store_true",
                    help="snapshot mode only: run board_set_fclk50.py before the load. This "
                         "is the ONE thing the calibration does that no successful run does, "
                         "and it is the only difference this cell is allowed to add.")
    ap.add_argument("--jtag-probe-after-load", action="store_true",
                    help="insert a JTAG mem_ap read between the load and the snapshot. This "
                         "is the ONLY intended difference between the first snapshot run "
                         "and its repeat; leave it off for the first.")
    args = ap.parse_args()

    carrier = args.run_dir / "carrier.bit"
    marker: str | None = None
    bundle = json.loads((args.run_dir / "carrier_run.json").read_text("utf-8"))
    digest = hashlib.sha256(carrier.read_bytes()).hexdigest()
    pinned = bundle["artifacts"]["carrier.bit"]["sha256"]

    record: dict = {
        "tool": TOOL_VERSION,
        "what": "isolate the step that stops the carrier answering",
        "mode": args.mode,
        "fclk50_before_load": args.fclk50_before_load,
        "jtag_probe_after_load": args.jtag_probe_after_load,
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

    if args.mode == "snapshot":
        return run_snapshot(args, record, carrier)

    if args.mode == "identity-first-touch":
        return run_identity_first_touch(args, record, carrier)

    if args.mode == "first-touch":
        return run_first_touch(args, record, carrier)

    if args.mode == "session-ladder":
        return run_session_ladder(args, record, carrier)

    if args.mode == "additive":
        if not args.plmark:
            print("--mode additive needs --plmark: it does not load, so it cannot learn the "
                  "boot nonce itself, and without it a restart would be recorded as a step's "
                  "own doing.", file=sys.stderr)
            return 2
        record["plmark"] = args.plmark
        return run_additive(args, record)

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
        found = re.search(r"\[plmark\] ([0-9a-f]+)", record["steps"][-1]["stdout_tail"])
        marker = found.group(1) if found else None
        record["plmark"] = marker
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
                                "carrier": read_carrier(probe, "4a right after load", marker)})

        time.sleep(6)
        record["steps"].append({"step": "read carrier (step 4b, +6s, same console)",
                                "carrier": read_carrier(probe, "4b after 6s", marker)})

        probe.close()
        probe = Probe(args.port)
        record["steps"].append({"step": "read carrier (step 4c, after closing and "
                                        "reopening the console, no tool run)",
                                "carrier": read_carrier(probe, "4c after reopen", marker)})

        # 5/6. the clock check, explicitly read-only, then read again.
        probe.close()
        record["steps"].append(run_tool(
            [sys.executable, str(REPO_ROOT / "scripts/board_set_fclk50.py"),
             "--port", args.port, "--verify-only"],
            "step 5: board_set_fclk50.py --verify-only"))
        probe = Probe(args.port)
        record["steps"].append({"step": "read carrier (step 6, after fclk50)",
                                "carrier": read_carrier(probe, "after fclk50", marker)})

        # 7. the identity gate, then read again.
        probe.close()
        record["steps"].append(run_tool(
            [sys.executable, str(REPO_ROOT / "scripts/gate_board_identity.py"),
             "--port", args.port],
            "step 7: gate_board_identity.py"))
        probe = Probe(args.port)
        record["steps"].append({"step": "read carrier (step 7, after identity)",
                                "carrier": read_carrier(probe, "after identity", marker)})

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

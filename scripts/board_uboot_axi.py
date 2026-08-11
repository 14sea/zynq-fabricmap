#!/usr/bin/env python3
r"""The U-Boot AXI transport: one transaction, driven over the console.

This is the wire end of §3b. `board_carrier_exec` seals the bytes and gates them; this
module is what actually reaches the carrier, and it is reachable only through
`BoardSession.write_sequence()` — see `WRITE_CAPABILITY` below.

The window (`carrier_axil.v`; only address bits [15:0] are decoded, so the slave aliases
across the whole GP0 range and `0x43C00000` is simply where we address it):

    0x0000 .. 0x0FFF  STREAM   W  one word of the envelope, in order
    0x1000 .. 0x118F  RDBACK   R  the 101 words of the frame the engine verified
    0x2000            CTRL     W  b1 begin_txn b2 pass1 b3 pass2 b5:4 env b6 arm
                                  b7 mode_holdout b8 rb_ack
    0x2004            STATUS   R
    0x2008            FAULT    R

THE PACING PROBLEM, AND WHY THE COMMANDS LOOK LIKE THIS
-------------------------------------------------------
`carrier_stream` runs a watchdog whose top bit is the expiry: 2**20 cycles of FCLK0, and
FCLK0 is pinned at 50 MHz, so **a phase has 20.97 ms end to end**. The watchdog is loaded
at the start of a pass and at entry to readback, and is NOT reloaded per frame — so the
whole five-frame readback of an envelope, including every host acknowledgement, must fit
inside one 20.97 ms budget. Both benches ack in the cycle after `rb_frame_ready`
(`always @(posedge clk) rb_ack <= rb_frame_ready && !rb_ack`), so simulation never saw a
host that takes milliseconds to answer.

Measured on board `17A6` (2026-08-11, U-Boot 2026.04-rc5, 115200):

    a command with no output      ~5 ms round trip
    `md.l <addr> 65` (101 words)  ~152 ms   <- the printing, not the reads
    `cp.l` 536 words              ~7 ms     <- also all round trip; the copy is µs

So the obvious shape — poll STATUS, `md` the frame, write the ack, repeat — costs about
14 ms **per frame** and roughly 70 ms per envelope. It cannot fit, and it would fail as a
readback difference, which is the one outcome the calibration is defined to treat as
falsifying the carrier. It must therefore not be attempted.

What fits: hand U-Boot the whole envelope — the pass, all five frame copies and all five
acknowledgements — as ONE console line. U-Boot reads a line to completion before executing
it, so the console cost is paid up front and the execution is microseconds. The frames go
to DRAM with `cp.l` (no printing) and are read out afterwards, when no watchdog is running.
The interlock between frames is a hush poll loop, measured at ~180 µs per iteration, so
nothing races the engine: `WAIT` spins until `rb_frame_ready` **or `fault`** is set, and
the fault term is what stops it spinning forever when the engine has already given up.

The loop is written INLINE rather than stored in the environment, and that is not a style
choice. `setenv` strips one level of quoting, so the `&` that `setexpr` needs comes back out
of the variable bare — where hush reads it as "run in background". Every storable spelling
was tried on the board: `'...\&...'`, `"...\&..."` and `"...'&'..."` all store a naked `&`
and `run` answers `syntax error`. Typed inline, `'&'` survives and the loop runs. CBSIZE is
2048 on this build and the longest line here is about 750 characters.

WHY `cp.l` IS THE BULK WRITE, AND WHY IT IS SAFE HERE
-----------------------------------------------------
`cp` is `memmove()`, which for a non-overlapping forward copy is ARM's assembly `memcpy`
(`CONFIG_USE_ARCH_MEMCPY=y` in this build) — LDM/STM blocks, not a word loop. That matters
because this slave has no burst support: `AWLEN` is not even wired in `carrier_top.v`, so a
burst would deadlock the W channel and wedge the CPU.

Two things say it does not: U-Boot maps everything outside DRAM as `DCACHE_OFF`, which for
non-LPAE ARMv7 is `TEX=0 C=0 B=0` — Strongly-ordered, where accesses may not be merged; and
zynq-autoehw did exactly this copy on this hardware and read the values back
(`docs/board_results.md` step 7, `cp.l 0x1000000 0x40000000 0x10`).

It is also checked rather than trusted, and the check is free: **pass 1 never asserts
CSIB.** `icap_csib` is driven low only under `phase == P_PASS2`, and `P_EMIT` is reachable
only from there, so the first envelope streams 536 words through the whole transport with
no ICAP activity at all. If a word were dropped or duplicated the position counter would
not reach 536 and the pass would fault — before anything has been written to the fabric.
"""

from __future__ import annotations

import hashlib
import re
import struct
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_carrier_guard as guard  # noqa: E402
from board_serial import PROMPT_RE  # noqa: E402

TOOL_VERSION = "board_uboot_axi.py/1.0.0"

# --------------------------------------------------------------------------- the window
#
# These five addresses appear in this module and nowhere else in the repository, and
# `tests/test_single_write_entrypoint.py` asserts that. It is the sharpest form of "there
# is one way to reach the carrier": a second writer would have to name the window, and
# naming it fails the test until the inventory is changed in a reviewed diff.
AXI_BASE = 0x43C00000
STREAM = AXI_BASE + 0x0000
RDBACK = AXI_BASE + 0x1000
CTRL = AXI_BASE + 0x2000
STATUS = AXI_BASE + 0x2004
FAULT = AXI_BASE + 0x2008

# DRAM scratch. The board has 512 MiB and U-Boot relocates itself to the top of it.
PAYLOAD_ADDR = 0x10000000       # 6,432 bytes
CAPTURE_ADDR = 0x10100000       # 15 frames x 404 bytes

CTRL_BEGIN_TXN = 1 << 1
CTRL_PASS1 = 1 << 2
CTRL_PASS2 = 1 << 3
CTRL_ENV_SHIFT = 4
CTRL_ARM = 1 << 6
CTRL_MODE_HOLDOUT = 1 << 7
CTRL_RB_ACK = 1 << 8

ST_BUSY = 1 << 0
ST_FAULT = 1 << 1
ST_CONFIGURATION_VALID = 1 << 2
ST_SCORER_BUSY = 1 << 3
ST_SCORER_DONE = 1 << 4
ST_SCORER_ARMED = 1 << 5
ST_PASS1_COMPLETE = 1 << 6
ST_RECOVERY_REQUIRED = 1 << 7
ST_RB_FRAME_READY = 1 << 10
# bits 9:8 expect_env, 13:11 env_committed, 17:14 rb_frames_ok, 31:18 reserved and zero
ST_RESERVED = 0xFFFC0000

FAULT_NAMES = {
    0: "none", 1: "order", 2: "control", 3: "far", 4: "length", 5: "crc",
    6: "timeout", 7: "phase", 8: "readback", 9: "uncommitted", 10: "bytecount",
}

FRAME_WORDS = guard.FRAME_WORDS                       # 101
FRAMES_PER_ENVELOPE = guard.FRAMES_PER_ENVELOPE       # 5
ENVELOPES = guard.ENVELOPES                           # 3
ENVELOPE_WORDS = guard.ENVELOPE_WORDS                 # 536
TOTAL_FRAMES = ENVELOPES * FRAMES_PER_ENVELOPE        # 15

# `carrier_stream` parameters, restated here because the budget is a property of the
# transport's pacing and has to be checkable on the host side.
TIMEOUT_BITS = 21
FCLK0_HZ = 50_000_000
WATCHDOG_BUDGET_S = (1 << (TIMEOUT_BITS - 1)) / FCLK0_HZ      # 0.02097 s

# The hush interlock, inlined between frames. `0x402` is rb_frame_ready | fault: without
# the fault term this spins forever exactly when the engine has already stopped, which is
# the moment a host most needs its prompt back. `zr` is forced to 0 first so the body always
# runs at least once — a leftover 0x400 from the previous frame would otherwise walk
# straight past the wait.
WAIT_MASK = ST_RB_FRAME_READY | ST_FAULT                      # 0x402
WAIT = (f"setenv zr 0; while itest $zr -eq 0; do "
        f"setexpr.l zr *0x{STATUS:08x} '&' 0x{WAIT_MASK:x}; done")

MD_LINE_RE = re.compile(
    rb"^([0-9a-fA-F]{8}):((?:[ \t]+[0-9a-fA-F]{8}){1,4})[ \t]", re.MULTILINE)

# A U-Boot data abort prints a register dump and never returns a prompt. So does a stalled
# CPU — and they mean OPPOSITE things: an abort is the fabric ANSWERING with an error
# response, a stall is the fabric not answering at all. Both were reported as "no prompt"
# once, and the two calibration stops of 2026-08-11 could not be told apart afterwards
# because the received bytes were thrown away. They are kept now, and named.
ABORT_RE = re.compile(rb"data abort|prefetch abort|undefined instruction|"
                      rb"### ERROR ### Please RESET")

# How many `mw.l` writes share one console line while the payload is staged into DRAM.
# Staging is not on any watchdog — it happens before `begin_txn` — so this is only a
# throughput choice: 12 keeps the line near 350 characters.
STAGE_WRITES_PER_LINE = 12


class AxiRefusal(Exception):
    """A refusal on the U-Boot AXI path. Never downgraded to a warning."""


class _Capability:
    """The token `execute_transaction` demands. One instance, held by one caller."""

    __slots__ = ()


WRITE_CAPABILITY = _Capability()


# ------------------------------------------------------------------------------ decoding


def decode_status(word: int) -> dict:
    """STATUS, field by field. Reserved bits are DATA, not something to mask away."""
    return {
        "raw": word,
        "busy": bool(word & ST_BUSY),
        "fault": bool(word & ST_FAULT),
        "configuration_valid": bool(word & ST_CONFIGURATION_VALID),
        "scorer_busy": bool(word & ST_SCORER_BUSY),
        "scorer_done": bool(word & ST_SCORER_DONE),
        "scorer_armed": bool(word & ST_SCORER_ARMED),
        "pass1_complete": bool(word & ST_PASS1_COMPLETE),
        "recovery_required": bool(word & ST_RECOVERY_REQUIRED),
        "expect_env": (word >> 8) & 0x3,
        "rb_frame_ready": bool(word & ST_RB_FRAME_READY),
        "env_committed": (word >> 11) & 0x7,
        "rb_frames_ok": (word >> 14) & 0xF,
        "reserved": word & ST_RESERVED,
    }


def far_of(env: int, frame: int) -> int:
    """The FAR of one frame of one envelope, from the guard's compiled-in order.

    Taken from the guard rather than from the manifest on purpose: the guard already has to
    agree with the manifest (`check_against_manifest`), so reading it here does not add a
    third opinion about which frames these are.
    """
    if frame < FRAMES_PER_ENVELOPE - 1:
        return guard.PERMITTED_TARGET_FARS[env * (FRAMES_PER_ENVELOPE - 1) + frame]
    return guard.PERMITTED_FLUSH_FARS[env]


def capture_addr(env: int, frame: int) -> int:
    return CAPTURE_ADDR + (env * FRAMES_PER_ENVELOPE + frame) * FRAME_WORDS * 4


# ------------------------------------------------------------------- the command planner
#
# Pure: these build strings and nothing else. The device is touched only by
# `execute_transaction`, which is the single site that hands one of these to a transport.


def stage_lines(payload: bytes, addr: int = PAYLOAD_ADDR) -> list[str]:
    """`mw.l` batches that put `payload` in DRAM, in order."""
    words = struct.unpack(f">{len(payload) // 4}I", payload)
    lines, batch = [], []
    for index, word in enumerate(words):
        batch.append(f"mw.l 0x{addr + index * 4:08x} 0x{word:08x} 1")
        if len(batch) == STAGE_WRITES_PER_LINE:
            lines.append("; ".join(batch))
            batch = []
    if batch:
        lines.append("; ".join(batch))
    return lines


def pass1_line(env: int) -> str:
    """Start pass 1 for one envelope and stream it, in ONE line.

    Same line because the watchdog starts at the CTRL write: two round trips would spend
    ~10 ms of a 21 ms budget before the first word arrived.
    """
    ctrl = CTRL_PASS1 | (env << CTRL_ENV_SHIFT)
    src = PAYLOAD_ADDR + env * ENVELOPE_WORDS * 4
    return (f"mw.l 0x{CTRL:08x} 0x{ctrl:x} 1; "
            f"cp.l 0x{src:08x} 0x{STREAM:08x} 0x{ENVELOPE_WORDS:x}")


def pass2_line(env: int) -> str:
    """Pass 2 AND the whole five-frame readback, in ONE line.

    Everything after the first `cp.l` runs under the readback watchdog, so none of it may
    cost a console round trip. `run zw` is the interlock; the frames land in DRAM and are
    read out later, when nothing is being timed.
    """
    ctrl = CTRL_PASS2 | (env << CTRL_ENV_SHIFT)
    src = PAYLOAD_ADDR + env * ENVELOPE_WORDS * 4
    parts = [f"mw.l 0x{CTRL:08x} 0x{ctrl:x} 1",
             f"cp.l 0x{src:08x} 0x{STREAM:08x} 0x{ENVELOPE_WORDS:x}"]
    for frame in range(FRAMES_PER_ENVELOPE):
        parts += [
            WAIT,
            f"cp.l 0x{RDBACK:08x} 0x{capture_addr(env, frame):08x} 0x{FRAME_WORDS:x}",
            f"mw.l 0x{CTRL:08x} 0x{CTRL_RB_ACK:x} 1",
        ]
    return "; ".join(parts)


# ------------------------------------------------------------------------- reading it back


def parse_md(reply: bytes, addr: int, count: int) -> list[int]:
    """Parse `md.l` output, checking the address column rather than trusting the order.

    The ASCII column of a dump can hold eight characters that look like a hex word, so the
    words are taken only from the group the line regex captured, and every line's address
    must be the one that line should have. A mis-parse becomes a refusal instead of a
    plausible-looking list of the wrong length.
    """
    words: list[int] = []
    for match in MD_LINE_RE.finditer(reply):
        line_addr = int(match.group(1), 16)
        expected = addr + len(words) * 4
        if line_addr != expected:
            raise AxiRefusal(
                f"md output is out of order: line at {line_addr:#010x}, expected "
                f"{expected:#010x}")
        words.extend(int(token, 16) for token in match.group(2).split())
    if len(words) != count:
        raise AxiRefusal(
            f"md {addr:#010x} {count} returned {len(words)} words: {reply[-200:]!r}")
    return words


def read_words(transport, addr: int, count: int, per_command: int = 128) -> list[int]:
    """Read `count` words, in chunks, with each chunk's address column verified."""
    out: list[int] = []
    while len(out) < count:
        take = min(per_command, count - len(out))
        at = addr + len(out) * 4
        reply = command(transport, f"md.l 0x{at:08x} 0x{take:x}", timeout=8.0)
        out.extend(parse_md(reply, at, take))
    return out


def read_status(transport) -> dict:
    """STATUS, with the liveness check the reserved field gives for free.

    `carrier_axil` drives bits 31:18 to zero, so a non-zero reserved field means the reply
    did not come from the carrier — a stale buffer, a floating bus, or the wrong design in
    the PL. All-zero is refused for the same reason: `recovery_required` is set out of
    reset, so a live carrier can never read 0.
    """
    word = read_words(transport, STATUS, 1)[0]
    if word & ST_RESERVED:
        raise AxiRefusal(
            f"STATUS reads {word:#010x}; bits 31:18 are hard zeros in carrier_axil, so this "
            "is not the carrier answering")
    if word == 0:
        raise AxiRefusal(
            "STATUS reads 0x00000000; recovery_required is set out of reset, so a live "
            "carrier cannot read zero — the PL is not configured with this carrier")
    return decode_status(word)


def read_fault(transport) -> tuple[int, str]:
    code = read_words(transport, FAULT, 1)[0] & 0xF
    return code, FAULT_NAMES.get(code, f"unknown({code})")


# ------------------------------------------------------------------------ the transaction


def command(transport, line: str, timeout: float) -> bytes:
    """One console command, with "did we get the prompt back" treated as evidence.

    A missing prompt is the shape a wedge takes over a serial line: the wait loop is still
    spinning, or the CPU is stalled on an AXI access that will never complete. Returning the
    partial buffer and carrying on would turn that into a parse error three steps later,
    naming the wrong thing. `Ctrl-C` breaks a hush loop; it does not rescue a stalled AXI
    access, which needs a power cycle.
    """
    if len(line) >= 2000:
        raise AxiRefusal(
            f"the command line is {len(line)} characters; U-Boot's CBSIZE is 2048 on this "
            "build and a truncated line would execute its first half")
    reply = transport.command(line, timeout)
    if PROMPT_RE.search(reply):
        return reply
    tail = reply[-400:]
    if ABORT_RE.search(reply):
        raise AxiRefusal(
            f"`{line[:60]}…` took a CPU exception. **The fabric ANSWERED** — an abort is an "
            "AXI error response reaching the CPU, not a bus that failed to reply — so this "
            "is a slave saying no, not a slave that is absent or unclocked. U-Boot does not "
            f"return from it; the board needs a power cycle. Received: {tail!r}")
    raise AxiRefusal(
        f"no prompt within {timeout}s of `{line[:60]}…` and no exception either — the fabric "
        "did not answer at all. Send Ctrl-C to break a spinning wait loop; if that does not "
        "return a prompt the CPU is stalled on the AXI bus and the board needs a power "
        f"cycle. Received: {tail!r}")


def same_boot(transport, marker: str) -> None:
    """Refuse unless the board is still on the boot that configured the PL.

    `plmark` is set by the loader with `setenv` and never `saveenv`, so it lives in RAM and
    a restart of any kind takes it with it. This has to be asked BEFORE anything touches the
    carrier, because the question "is the PL still configured" cannot be put to the PL: if
    the answer is no, asking stalls the CPU and costs a power cycle.

    Board `17A6` was observed restarting between two successful reads — the reply to the
    second carried `U-Boot SPL … Trying to boot from MMC1`, a full cold boot nobody asked
    for. A restart clears the PL, so every later AXI access stalls, and from the console
    that is indistinguishable from a design that does not work. It is distinguishable from
    here, in one command, for free.
    """
    reply = command(transport, "printenv plmark", timeout=5.0)
    found = re.search(rb"plmark=([0-9a-f]+)", reply)
    if not found:
        raise AxiRefusal(
            "`plmark` is not set: the board has restarted since the carrier was loaded (the "
            "variable lives in RAM and was never saved), so the PL is no longer configured. "
            "Reload the carrier — do NOT read the window, which would stall the CPU.")
    actual = found.group(1).decode("ascii")
    if actual != marker:
        raise AxiRefusal(
            f"`plmark` is {actual}, the load set {marker}: this is a different boot, so the "
            "PL is not the one that was configured. Reload the carrier.")


def ps_peek(transport):
    """A reader for PS registers, for `board_carrier_guard.PcapPr`."""
    def peek(addr: int) -> int:
        return read_words(transport, addr, 1)[0]
    return peek


def ps_poke(transport):
    """A writer for PS registers. NOT a fabric write: `PCAP_PR` lives in devcfg, in the PS,
    and handing the ICAP to the PL is a precondition of a transaction rather than part of
    one."""
    def poke(addr: int, value: int) -> None:
        command(transport, f"mw 0x{addr:08x} 0x{value:08x} 1", timeout=5.0)
    return poke


def _refuse_on_fault(transport, status: dict, where: str) -> None:
    if not status["fault"]:
        return
    code, name = read_fault(transport)
    raise AxiRefusal(f"the engine faulted during {where}: fault_code {code} ({name})")


def execute_transaction(capability, transport, payload: bytes) -> dict:
    """One complete transaction: stage, pass 1 x3, pass 2 + readback x3, verdict.

    Reachable only with `WRITE_CAPABILITY`, which `BoardSession.write_sequence()` holds.
    An importable function that writes to the fabric would be a second device-write
    entrypoint however carefully its caller behaved.

    `transport` is the session's OWN open handle — never a port this module resolves — so
    the identity the session verified is the identity of the board being written.
    """
    if capability is not WRITE_CAPABILITY:
        raise AxiRefusal(
            "execute_transaction is reachable only through BoardSession.write_sequence(): "
            "an importable device write is a second entrypoint")
    if len(payload) != guard.TOTAL_BYTES:
        raise AxiRefusal(
            f"the payload is {len(payload)} bytes; the fixed envelope is "
            f"{guard.TOTAL_BYTES}")

    started = time.time()
    record: dict = {
        "tool": TOOL_VERSION,
        "axi_base": f"{AXI_BASE:#010x}",
        "watchdog_budget_s": round(WATCHDOG_BUDGET_S, 6),
        # What this transaction is *about*. Without it a caller holding a session cannot
        # tell this record from the previous candidate's, and a stale readback would be
        # read as the current one's evidence.
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "stages": [],
    }

    def note(name: str, status: dict, elapsed: float) -> None:
        record["stages"].append(
            {"stage": name, "status": status, "elapsed_s": round(elapsed, 3)})

    # -- 0. the carrier must already be there, and it must be in its reset state.
    status = read_status(transport)
    if status["busy"]:
        raise AxiRefusal("the engine is busy before the transaction started")
    if not status["recovery_required"]:
        raise AxiRefusal(
            "recovery_required is clear before any transaction: it is sticky to reset, so a "
            "carrier that has just been loaded must have it set — this PL state is not the "
            "one the run assumes")
    record["status_before"] = status

    # -- 1. stage the payload, then prove DRAM holds exactly the sealed bytes.
    t0 = time.time()
    for line in stage_lines(payload):
        command(transport, line, timeout=8.0)
    staged = read_words(transport, PAYLOAD_ADDR, len(payload) // 4)
    if struct.pack(f">{len(staged)}I", *staged) != payload:
        raise AxiRefusal(
            "the bytes in DRAM are not the bytes that were sealed — the transport would "
            "stream something the host gate never saw")
    record["staged_s"] = round(time.time() - t0, 3)

    # -- 2. hand the ICAP to the PL, then begin.
    #
    # Without this the whole transaction is theatre: devcfg reads `0x4E00E07F` on this
    # board, so `PCAP_PR` is 1, PCAP owns the configuration engine and the fabric's ICAPE2
    # is disconnected — every FDRI word would be accepted by the engine and reach nothing.
    # `PcapPr` restores the previous value on the failure path too, because a devcfg left
    # selecting the PL leaves the next PCAP user staring at a device that will not respond,
    # and the recovery for that on this board is a power cycle.
    pcap = guard.PcapPr(ps_poke(transport), ps_peek(transport),
                        report=lambda message: record.setdefault("pcap_pr", []).append(message))
    with pcap:
        _transaction_body(transport, record, note, started)
    return record


def _transaction_body(transport, record: dict, note, started: float) -> None:
    command(transport, f"mw.l 0x{CTRL:08x} 0x{CTRL_BEGIN_TXN:x} 1", timeout=5.0)
    status = read_status(transport)
    _refuse_on_fault(transport, status, "begin_txn")
    note("begin_txn", status, time.time() - started)

    # -- 3. pass 1, three envelopes. NOTHING is written to the fabric here: `icap_csib` is
    #       driven low only under P_PASS2, so this validates the whole transport first.
    for env in range(ENVELOPES):
        t0 = time.time()
        command(transport, pass1_line(env), timeout=15.0)
        status = read_status(transport)
        _refuse_on_fault(transport, status, f"pass 1 of envelope {env}")
        if status["busy"]:
            raise AxiRefusal(f"pass 1 of envelope {env} did not finish")
        if not status["env_committed"] & (1 << env):
            raise AxiRefusal(
                f"pass 1 of envelope {env} left it uncommitted (env_committed="
                f"{status['env_committed']:#05b}) — its CRCs are not authority")
        note(f"pass1_env{env}", status, time.time() - t0)
    if not status["pass1_complete"]:
        raise AxiRefusal("all three envelopes passed but pass1_complete is clear")

    # -- 4. pass 2 + readback, three envelopes. Everything after the CTRL write is inside
    #       one watchdog budget, which is why it is one console line.
    frames: dict[int, list[int]] = {}
    for env in range(ENVELOPES):
        t0 = time.time()
        command(transport, pass2_line(env), timeout=30.0)
        status = read_status(transport)
        _refuse_on_fault(transport, status, f"pass 2 of envelope {env}")
        if status["busy"]:
            raise AxiRefusal(f"pass 2 of envelope {env} did not finish")
        expected_ok = (env + 1) * FRAMES_PER_ENVELOPE
        if status["rb_frames_ok"] != expected_ok:
            raise AxiRefusal(
                f"after envelope {env} the engine reports {status['rb_frames_ok']} verified "
                f"frames, expected {expected_ok}")
        note(f"pass2_env{env}", status, time.time() - t0)

        for frame in range(FRAMES_PER_ENVELOPE):
            words = read_words(transport, capture_addr(env, frame), FRAME_WORDS)
            frames[far_of(env, frame)] = words

    # -- 5. the verdict, read from the device and not inferred from the steps.
    final = read_status(transport)
    _refuse_on_fault(transport, final, "the final status read")
    if not final["configuration_valid"]:
        raise AxiRefusal("the transaction finished but configuration_valid is clear")
    if final["recovery_required"]:
        raise AxiRefusal(
            "configuration_valid is set but recovery_required is still set: a fault happened "
            "since the carrier was loaded, and what was written before it may never be "
            "scored")
    if final["rb_frames_ok"] != TOTAL_FRAMES:
        raise AxiRefusal(
            f"only {final['rb_frames_ok']} of {TOTAL_FRAMES} frames verified")
    if len(frames) != TOTAL_FRAMES:
        raise AxiRefusal(
            f"{len(frames)} distinct FARs came back, expected {TOTAL_FRAMES}")
    if final["scorer_armed"] or final["scorer_busy"]:
        raise AxiRefusal(
            "the scorer is armed or busy after a write: arming is a separate, later "
            "decision and nothing in this transport issues it")

    record["status_after"] = final
    record["readback_frames"] = frames
    record["elapsed_s"] = round(time.time() - started, 3)

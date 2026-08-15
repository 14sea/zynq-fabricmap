#!/usr/bin/env python3
"""Phase 1: read configuration frames over JTAG, against a bitstream with a known answer.

This does not go through the carrier. It drives the PL TAP directly, so it is an
independent opinion about what is in a frame — which is the whole point: the carrier's own
readback is the thing under suspicion, and it cannot be its own witness.

THE ALLOWED SET, and it is enforced in code, not in a comment
------------------------------------------------------------
IR: IDCODE, CFG_IN, CFG_OUT, JSHUTDOWN and JSTART. Configuration: RCRC, RCFG, FAR, FDRO,
DESYNC. **JPROGRAM, WCFG, MFWR, IPROG and any FDRI write are refused before a single bit is
shifted.** `check_sequence()` walks the generated words and the emitted-Tcl checker verifies
the reviewed startup/shutdown prefix, because "the script does not do that" is worth exactly
as much as the check that proves it.

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

TOOL_VERSION = "probe_jtag_config_read.py/2.4.0"
TAP = "zynq_pl.bs"
IR = {
    "IDCODE": 0x09,
    "CFG_IN": 0x05,
    "CFG_OUT": 0x04,
    "JSHUTDOWN": 0x0D,
    "JSTART": 0x0C,
}
FORBIDDEN_IR = {"JPROGRAM": 0x0B}

# These records are evidence about the values emitted by R4, not retroactive provenance for
# historical probes. The original 12-TCK dwell happened to agree with UG470 but was written
# from general knowledge; R2's 1024-TCK experimental dwell remains chosen, not derived, and
# is deliberately absent here.
R4_DWELLS = {
    "startup_cycle_shutdown": {
        "cycles": 12,
        "document_id": "UG470",
        "version": "v1.17",
        "chapter": "6",
        "table": "6-6",
    },
    "startup": {
        "cycles": 2000,
        "document_id": "UG470",
        "version": "v1.17",
        "chapter": "10",
        "table": "10-4",
    },
    "readback_shutdown": {
        "cycles": 12,
        "document_id": "UG470",
        "version": "v1.17",
        "chapter": "6",
        "table": "6-6",
    },
}

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


DESYNC_TAIL = [t1(True, CMD_REG, 1), CMD_DESYNC, NOOP, NOOP]


def build_tcl(far_list: list[int]) -> tuple[str, list[dict]]:
    """The whole session as one OpenOCD script, so config state survives between steps.

    **Every envelope is closed where it was opened.** A `sync … DESYNC` envelope holds one
    FAR-set and one read, and never spans two.

    That is a conservative contract, and it is deliberately not a diagnosis. It was adopted
    after the 2026-08-15 session in which a second read returned an all-zero frame, on the
    hypothesis that the shared envelope caused it. **The experiment refuted that**: with one
    envelope per FAR, on a different boot, all 202 words of each read came back identical to
    the shared-envelope run. The contract stays because a closed envelope is the documented
    shape and costs nothing, not because it explains anything.

    `envelope_violations()` below is the machine-checkable form of the rule, and it is what
    the mutation harness kills a mutant with. R4 first performs the reviewed shutdown/startup
    transition, then emits UG470 Table 6-6's RCRC-before-JSHUTDOWN readback prefix. The R4
    control and post-no-op acquisition deliberately call this same function with the same
    FARs; board pre-state is not an input to the instrument.
    """
    steps: list[dict] = []
    lines = ["init", "echo \"@@ init done\""]

    lines += [f"irscan {TAP} 0x{IR['IDCODE']:02x}",
              f"set id [drscan {TAP} 32 0]",
              "echo \"@@ IDCODE $id\""]

    def cfg_in(words: list[int], label: str) -> None:
        check_sequence(words)
        steps.append({"step": label, "words": [f"{w:08x}" for w in words]})
        lines.append(f"irscan {TAP} 0x{IR['CFG_IN']:02x}")
        lines.append(f"drscan {TAP} {field_list(words)}")

    def close_envelope(label: str) -> None:
        cfg_in(list(DESYNC_TAIL), f"DESYNC after {label}")

    # -- the STAT envelope, opened and closed like every other one.
    cfg_in([DUMMY, SYNC, NOOP, t1(False, STAT_REG, 1), NOOP, NOOP], "read STAT")
    lines += [f"irscan {TAP} 0x{IR['CFG_OUT']:02x}",
              f"set stat [drscan {TAP} 32 0]",
              "echo \"@@ STAT $stat\""]
    close_envelope("STAT")

    # -- R4: complete a shutdown/startup transition, then use the documented shutdown
    # readback prefix. RCRC is before the final JSHUTDOWN (UG470 v1.17, Table 6-6).
    lines += [f"irscan {TAP} 0x{IR['JSHUTDOWN']:02x}",
              f"runtest {R4_DWELLS['startup_cycle_shutdown']['cycles']}"]
    lines += [f"irscan {TAP} 0x{IR['JSTART']:02x}",
              f"runtest {R4_DWELLS['startup']['cycles']}"]
    cfg_in([DUMMY, SYNC, NOOP, t1(True, CMD_REG, 1), CMD_RCRC, NOOP, NOOP], "RCRC")
    close_envelope("RCRC")
    lines += [f"irscan {TAP} 0x{IR['JSHUTDOWN']:02x}",
              f"runtest {R4_DWELLS['readback_shutdown']['cycles']}"]

    # -- one complete transaction per FAR: SYNC → RCFG → FAR → FDRO → CFG_OUT → DESYNC.
    for far in far_list:
        cfg_in([DUMMY, SYNC, NOOP,
                t1(True, CMD_REG, 1), CMD_RCFG, NOOP,
                t1(True, FAR_REG, 1), far,
                t1(False, FDRO_REG, 0), t2_read(READ_WORDS)] + [NOOP] * 32,
               f"FDRO {far:#010x}")
        lines += [f"irscan {TAP} 0x{IR['CFG_OUT']:02x}",
                  f"set data [drscan {TAP} {capture_fields(READ_WORDS)}]",
                  f"echo \"@@ FRAME {far:#010x} $data\""]
        close_envelope(f"FDRO {far:#010x}")

    lines += ["echo \"@@ desync done\"", "shutdown"]
    tcl = "\n".join(lines) + "\n"
    violations = envelope_violations(tcl)
    if violations:
        raise ProbeStop("the generated script leaves an envelope open: " + "; ".join(violations))
    violations = recovery_order_violations(tcl)
    if violations:
        raise ProbeStop("the generated recovery sequence is not R4: " + "; ".join(violations))
    return tcl, steps


def _payload_words(line: str) -> list[int] | None:
    """The config words a `drscan` line carries, or None if it is a capture-only scan."""
    match = re.match(rf"drscan {re.escape(TAP)} (\d+) 0x([0-9a-fA-F]+)$", line.strip())
    if not match:
        return None
    bits, value = int(match.group(1)), int(match.group(2), 16)
    if value == 0 or bits % 32:
        return None
    return [rev32((value >> (32 * i)) & 0xFFFFFFFF) for i in range(bits // 32)]


def envelope_violations(tcl: str) -> list[str]:
    """Every `sync` must be closed by a `DESYNC` before the next one, and before the end.

    Written against the emitted script rather than the builder's intentions, so a change
    that quietly drops a DESYNC is caught by reading what would actually be shifted.
    """
    problems: list[str] = []
    open_at: int | None = None
    for number, line in enumerate(tcl.splitlines(), 1):
        if line.strip() == f"irscan {TAP} 0x{IR['CFG_OUT']:02x}":
            if open_at is None:
                problems.append(f"line {number}: a CFG_OUT read outside any envelope")
            continue
        words = _payload_words(line)
        if not words:
            continue
        if SYNC in words:
            if open_at is not None:
                problems.append(
                    f"line {number}: a SYNC while the envelope opened at line {open_at} "
                    "is still open")
            open_at = number
        desync = any(words[i] == t1(True, CMD_REG, 1) and i + 1 < len(words)
                     and words[i + 1] == CMD_DESYNC for i in range(len(words)))
        if desync:
            if open_at is None:
                problems.append(f"line {number}: a DESYNC with no envelope open")
            open_at = None
    if open_at is not None:
        problems.append(f"the envelope opened at line {open_at} is never closed")
    return problems


def recovery_order_violations(tcl: str) -> list[str]:
    """Require the exact R4 startup/shutdown prefix in the emitted Tcl.

    The comparison is against semantic events recovered from the script, not builder control
    flow. It pins the three dwell values as well as ordering, so longer and shorter waits are
    both changes to the reviewed instrument rather than silently accepted variants.
    """
    events: list[tuple[str, int, int | None]] = []
    forbidden: list[tuple[int, str]] = []
    pre_read_desync_lines: list[int] = []
    for number, line in enumerate(tcl.splitlines(), 1):
        issued_ir = re.fullmatch(
            rf"irscan\s+{re.escape(TAP)}\s+(0x[0-9a-fA-F]+|\d+)", line.strip())
        if issued_ir:
            code = int(issued_ir.group(1), 0)
            if code == IR["JSHUTDOWN"]:
                events.append(("JSHUTDOWN", number, None))
            elif code == IR["JSTART"]:
                events.append(("JSTART", number, None))
            for name, forbidden_code in FORBIDDEN_IR.items():
                if code == forbidden_code:
                    forbidden.append((number, name))
        dwell = re.fullmatch(r"runtest\s+(\d+)", line.strip())
        if dwell:
            events.append(("DWELL", number, int(dwell.group(1))))
        words = _payload_words(line)
        if not words:
            continue
        has_desync = any(words[index] == t1(True, CMD_REG, 1)
                         and words[index + 1] == CMD_DESYNC
                         for index in range(len(words) - 1))
        if SYNC in words and has_desync:
            pre_read_desync_lines.append(number)
        for index in range(len(words) - 1):
            if words[index] == t1(True, CMD_REG, 1) and words[index + 1] == CMD_RCRC:
                events.append(("RCRC", number, None))
            if words[index] == t1(False, FDRO_REG, 0):
                events.append(("FDRO", number, None))

    problems: list[str] = []
    if forbidden:
        problems.extend(f"line {line}: forbidden IR {name}" for line, name in forbidden)
    if pre_read_desync_lines:
        problems.append(
            "R4 carries no self-contained pre-read SYNC...DESYNC envelope; "
            f"found {len(pre_read_desync_lines)}")

    first_fdro = next((index for index, event in enumerate(events) if event[0] == "FDRO"), None)
    if first_fdro is None:
        problems.append("no FDRO read follows the recovery prefix")
        return problems
    observed = [(name, value) for name, _, value in events[:first_fdro + 1]]
    expected = [
        ("JSHUTDOWN", None),
        ("DWELL", R4_DWELLS["startup_cycle_shutdown"]["cycles"]),
        ("JSTART", None),
        ("DWELL", R4_DWELLS["startup"]["cycles"]),
        ("RCRC", None),
        ("JSHUTDOWN", None),
        ("DWELL", R4_DWELLS["readback_shutdown"]["cycles"]),
        ("FDRO", None),
    ]
    if observed != expected:
        problems.append(f"R4 prefix is {observed!r}, expected {expected!r}")
    return problems


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
        # 2.4.0 is recovery rung R4. Older rungs use different sequences and cannot share an
        # evidence identity with this one.
        "tool": TOOL_VERSION,
        "what": "independent JTAG readback of configuration frames",
        "tap": TAP,
        "ir_codes": {name: f"0x{code:02x}" for name, code in IR.items()},
        "forbidden_ir": {name: f"0x{code:02x}" for name, code in FORBIDDEN_IR.items()},
        "r4_dwell_provenance": R4_DWELLS,
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

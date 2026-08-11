#!/usr/bin/env python3
"""The board-side guard: a fixed FAR/FDRI range that nothing at run time can widen.

Preregistration §6 item 6. The sibling `icaphw.c` took `ICAPHW_FAR_LO`, `ICAPHW_FAR_HI` and
`ICAPHW_MAX_FDRI` from the environment, and **that pattern is deliberately not carried
across**: a guard whose bounds an environment variable can move is not a guard, it is a
default. Here the bounds are module-level constants. Widening them is a source edit that
appears in a diff and in review, and `tests/test_board_carrier_guard.py` asserts the CLI
exposes nothing that could relax a requirement.

Where this sits
---------------
Round 1's control plane is **U-Boot only** (preregistration §"The control-plane boundary"),
so there is no program on the board: the executor driving the U-Boot session is the last
thing before the wire, and that is where a board-side guard has to be. It is the third
independent check of the same bytes, and the three do not share code:

  1. `gate_candidate.py` — the host gate, parses the whole serialized sequence;
  2. **this** — a narrow, compiled-in range check on the bytes about to be transmitted;
  3. `carrier_stream` in the fabric — the word-by-word control trace and FAR check, plus
     the two-pass CRC.

The constants are ALSO cross-checked against the phenotype manifest, and a disagreement
refuses. Neither can quietly widen: the manifest cannot, because these constants do not
come from it; the constants cannot, because the manifest must agree.

**It guards the bytes it is handed, in memory.** §3b's chain breaks if anything re-reads
the file between the gate and the wire, so `guard_sequence()` takes bytes, never a path.

`PCAP_PR` is restored with try/finally semantics, on the failure path too, and ICAP health
is reported rather than the device being left half-configured (§6 item 7).
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

TOOL_VERSION = "board_carrier_guard.py/1.0.0"

# ---------------------------------------------------------------- THE FIXED BOUNDS
#
# Compiled in. There is no environment variable, no CLI flag and no manifest field that
# moves any of these at run time.
#
# The 12 target FARs and the 3 flush FARs, and nothing else. The successors are the ones
# read from the device frame sequence, NOT integer FAR+1 — two of the three cross into the
# next column (`0x00400A23` -> `0x00400A80`, `0x00400C23` -> `0x00400C80`), which is exactly
# why computing them would write to a frame that does not exist.
PERMITTED_TARGET_FARS: tuple[int, ...] = (
    0x00400A20, 0x00400A21, 0x00400A22, 0x00400A23,
    0x00400C1A, 0x00400C1B, 0x00400C1C, 0x00400C1D,
    0x00400C20, 0x00400C21, 0x00400C22, 0x00400C23,
)
PERMITTED_FLUSH_FARS: tuple[int, ...] = (0x00400A80, 0x00400C1E, 0x00400C80)

# One envelope: 5 frames of 101 words written in one FDRI burst.
FRAME_WORDS = 101
FRAMES_PER_ENVELOPE = 5
MAX_FDRI_WORDS = FRAME_WORDS * FRAMES_PER_ENVELOPE          # 505
ENVELOPE_WORDS = 536
ENVELOPES = 3
TOTAL_BYTES = ENVELOPES * ENVELOPE_WORDS * 4                # 6432

# The FAR each envelope may set, in order. An envelope may set exactly one.
ENVELOPE_FAR: tuple[int, ...] = (0x00400A20, 0x00400C1A, 0x00400C20)

# Packet decode, written out here rather than imported: an independent check that borrowed
# the builder's constants would agree with the builder by construction. It is decoded from
# the documented format —
#   type 1: 001 <op:2> <reg:14> <rsvd:2> <count:11>
#   type 2: 010 <count:27>
# — and the first attempt got the type-2 header wrong (it assumed an opcode field that this
# format does not have), which the test against the REAL builder caught immediately. That
# is the independence earning its keep, not an argument against it.
_TYPE1_WRITE_FAR = 0x30002001
_TYPE1_WRITE_FDRI = 0x30004000
_TYPE2_HEADER = 2
_REG_CRC, _REG_FAR, _REG_FDRI, _REG_CMD, _REG_IDCODE = 0x00, 0x01, 0x02, 0x04, 0x0C

PCAP_PR_ADDR = 0xF8007000       # devcfg CTRL; bit 27 selects PCAP (1) or ICAP (0)
PCAP_PR_BIT = 1 << 27


class GuardRefusal(Exception):
    """A refusal. Never downgraded to a warning."""


def permitted_fars() -> frozenset[int]:
    return frozenset(PERMITTED_TARGET_FARS + PERMITTED_FLUSH_FARS)


def check_against_manifest(manifest: dict) -> list[str]:
    """The compiled-in set must equal the manifest's, or neither is an authority.

    Not "the manifest supplies the bounds" — that would make the manifest the override this
    guard exists to refuse. Two independent statements that must agree.
    """
    problems: list[str] = []
    envelope = manifest.get("write_envelope") or {}
    envelopes = envelope.get("envelopes") or []

    target: list[int] = []
    flush: list[int] = []
    far_set: list[int] = []
    for entry in envelopes:
        far_set.append(int(entry["far_set"], 16))
        target.extend(int(f, 16) for f in entry["target_fars"])
        flush.append(int(entry["flush_far"], 16))

    if tuple(sorted(target)) != tuple(sorted(PERMITTED_TARGET_FARS)):
        problems.append(
            f"the manifest's 12 target FARs are not the compiled-in set: "
            f"manifest={[hex(f) for f in sorted(target)]}")
    if tuple(sorted(flush)) != tuple(sorted(PERMITTED_FLUSH_FARS)):
        problems.append(
            f"the manifest's flush FARs are not the compiled-in set: "
            f"manifest={[hex(f) for f in sorted(flush)]}")
    if tuple(far_set) != tuple(ENVELOPE_FAR):
        problems.append(
            f"the manifest's per-envelope FAR sets are not the compiled-in order: "
            f"manifest={[hex(f) for f in far_set]}")
    if envelope.get("total_bytes") != TOTAL_BYTES:
        problems.append(
            f"the manifest's total is {envelope.get('total_bytes')} bytes, "
            f"the compiled-in envelope is {TOTAL_BYTES}")
    return problems


def guard_sequence(payload: bytes) -> None:
    """Refuse anything outside the fixed range. Takes BYTES — never a path.

    §3b: the transport must send the same in-memory bytes the host gate accepted. A guard
    that re-read the file would be guarding a different artifact with the same name.
    """
    if len(payload) != TOTAL_BYTES:
        raise GuardRefusal(
            f"the sequence is {len(payload)} bytes; the fixed envelope is {TOTAL_BYTES}")

    words = list(struct.unpack(f">{len(payload) // 4}I", payload))
    allowed = permitted_fars()

    for index in range(ENVELOPES):
        block = words[index * ENVELOPE_WORDS:(index + 1) * ENVELOPE_WORDS]

        far_writes = [i for i, w in enumerate(block) if w == _TYPE1_WRITE_FAR]
        if len(far_writes) != 1:
            raise GuardRefusal(
                f"envelope {index} contains {len(far_writes)} FAR writes, expected exactly 1")
        far = block[far_writes[0] + 1]
        if far not in allowed:
            raise GuardRefusal(
                f"envelope {index} sets FAR 0x{far:08X}, which is outside the fixed set")
        if far != ENVELOPE_FAR[index]:
            raise GuardRefusal(
                f"envelope {index} sets FAR 0x{far:08X}, not its fixed 0x{ENVELOPE_FAR[index]:08X}")

        fdri_writes = [i for i, w in enumerate(block) if w == _TYPE1_WRITE_FDRI]
        if len(fdri_writes) != 1:
            raise GuardRefusal(
                f"envelope {index} contains {len(fdri_writes)} FDRI writes, expected exactly 1")
        follower = block[fdri_writes[0] + 1]
        if (follower >> 29) != _TYPE2_HEADER:
            raise GuardRefusal(
                f"envelope {index}'s FDRI is not followed by a type-2 header: 0x{follower:08X}")
        length = follower & 0x07FFFFFF
        if length > MAX_FDRI_WORDS:
            raise GuardRefusal(
                f"envelope {index} would write {length} words, over the fixed maximum "
                f"{MAX_FDRI_WORDS}")
        if length != MAX_FDRI_WORDS:
            raise GuardRefusal(
                f"envelope {index} writes {length} words; the fixed envelope is exactly "
                f"{MAX_FDRI_WORDS} — every candidate rewrites all five frames")

        # Any OTHER register write in the block is outside the guard's remit and refused:
        # the fixed range is about which registers are written as much as which addresses.
        # The payload is not scanned: 505 arbitrary content words will contain bit
        # patterns that look like headers, and treating them as packets would refuse valid
        # candidates. The packet region is the preamble and the trailer, which is exactly
        # where a smuggled register write could do anything.
        payload_at = fdri_writes[0] + 2
        packet_positions = list(range(payload_at)) + \
                           list(range(payload_at + MAX_FDRI_WORDS, len(block)))
        for position in packet_positions:
            word = block[position]
            if (word >> 29) != 1 or ((word >> 27) & 3) != 2:
                continue                       # not a type-1 write
            register = (word >> 13) & 0x3FFF
            if register in (_REG_CRC, _REG_FAR, _REG_FDRI, _REG_CMD, _REG_IDCODE):
                continue
            raise GuardRefusal(
                f"envelope {index} word {position} writes register 0x{register:02X}, "
                "which the fixed guard does not permit")


class PcapPr:
    """Hand the ICAP to the PL, and give it back — on the failure path too.

    §6 item 7. The failure this exists for is not hypothetical: a devcfg left selecting the
    PL after an aborted write leaves the next PCAP user staring at a device that will not
    respond, and the recovery on this board is a power cycle.
    """

    def __init__(self, poke, peek, report=print):
        self._poke, self._peek, self._report = poke, peek, report
        self._previous: int | None = None

    def __enter__(self) -> "PcapPr":
        self._previous = self._peek(PCAP_PR_ADDR)
        self._poke(PCAP_PR_ADDR, self._previous & ~PCAP_PR_BIT)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if self._previous is not None:
                self._poke(PCAP_PR_ADDR, self._previous)
            health = self._peek(PCAP_PR_ADDR)
            self._report(
                f"PCAP_PR restored to 0x{self._previous:08X}; devcfg now 0x{health:08X}"
                + ("" if exc_type is None else "  (after a failure)"))
        except Exception as restore_failure:            # noqa: BLE001
            # Reported, never swallowed, and never allowed to mask the original failure.
            self._report(f"PCAP_PR RESTORE FAILED: {restore_failure}")
        return False        # exceptions propagate; a guard does not absorb them


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sequence", type=Path, required=True,
                    help="the serialized ICAP sequence to judge")
    ap.add_argument("--manifest", type=Path, required=True,
                    help="the phenotype manifest, which must AGREE with the fixed bounds")
    args = ap.parse_args()

    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read the manifest: {exc}", file=sys.stderr)
        return 3

    disagreements = check_against_manifest(manifest)
    if disagreements:
        for problem in disagreements:
            print(f"REFUSED: {problem}", file=sys.stderr)
        return 2

    try:
        guard_sequence(args.sequence.read_bytes())
    except GuardRefusal as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"cannot read the sequence: {exc}", file=sys.stderr)
        return 3

    print(f"PERMITTED: {TOTAL_BYTES} bytes, 3 envelopes, "
          f"{len(PERMITTED_TARGET_FARS)} target + {len(PERMITTED_FLUSH_FARS)} flush FARs, "
          f"{MAX_FDRI_WORDS} words each — all within the compiled-in range")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

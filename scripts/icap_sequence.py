#!/usr/bin/env python3
"""Build and parse the partial-frame ICAP write sequence for a candidate.

Preregistration §6. A candidate is applied as **three sync..DESYNC envelopes**, each one
FAR set followed by a single FDRI burst of 4 target frames plus 1 flush frame, where the
flush FAR is the successor pinned in the phenotype manifest — not `FAR + 1`, which is a
frame that does not exist for two of the three groups.

Why one FAR set per envelope, and never several
-----------------------------------------------
zynq-xpart learned this the destructive way (M7.3+, 2026-06-27): putting **multiple FAR
sets inside one sync..DESYNC envelope** mis-commits the buffered frame to the new FAR and
corrupts the array. This shape does not do that — it sets FAR once and lets the FDRI burst
auto-increment, which is exactly what a full bitstream does with its single FAR=0 burst
over 5152 frames. The 31-word overhead here is the same 31 words that envelope carried
(233 total - 202 payload).

The builder and the parser are deliberately separate
----------------------------------------------------
`build_sequence()` produces words; `parse_sequence()` reads words back into structure and
knows nothing about the builder's intentions. The candidate gate consumes the **parse**,
so what is judged is the byte stream that will reach the device rather than the operator's
description of it. A gate that inspected the builder's inputs would agree with the builder
by construction.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bitstream_frames as bf  # noqa: E402

TOOL_VERSION = "icap_sequence.py/1.0.0"

DUMMY = 0xFFFFFFFF
SYNC = 0xAA995566
NOOP = 0x20000000

# Type-1 header: 001 <op:2> <reg:14> <rsvd:2> <count:11>
REG_CRC, REG_FAR, REG_FDRI, REG_CMD, REG_IDCODE = 0, 1, 2, 4, 12
CMD_WCFG, CMD_RCRC, CMD_DESYNC = 0x00000001, 0x00000007, 0x0000000D

# Commands a candidate write must never contain. GRESTORE would reassert the global
# restore of every flip-flop and GTS would toggle the global tristate: both reach far
# outside the frames being written, and neither has any business in a content-bit edit.
FORBIDDEN_CMDS = {
    0x0000000A: "GRESTORE",
    0x0000000B: "GTS",  # SHUTDOWN/GTS family
    0x00000005: "START",
    0x00000003: "DGHIGH/LFRM",
}


def type1(op: int, reg: int, count: int) -> int:
    return (1 << 29) | (op << 27) | (reg << 13) | count


def type2(count: int) -> int:
    return (2 << 29) | count


class SequenceError(Exception):
    """A refusal."""


def build_envelope(far: int, frames: list[list[int]], idcode: int) -> list[int]:
    """One sync..DESYNC envelope: set FAR once, stream every frame in one FDRI burst."""
    for frame in frames:
        if len(frame) != bf.FRAME_WORDS:
            raise SequenceError(
                f"frame for FAR {far:#010x} has {len(frame)} words, expected "
                f"{bf.FRAME_WORDS}"
            )
    payload = [word for frame in frames for word in frame]
    return (
        [DUMMY] * 8
        + [
            SYNC,
            NOOP,
            type1(2, REG_CMD, 1), CMD_RCRC,
            NOOP, NOOP,
            type1(2, REG_IDCODE, 1), idcode,
            type1(2, REG_CMD, 1), CMD_WCFG, NOOP,
            type1(2, REG_FAR, 1), far,
            type1(2, REG_FDRI, 0), type2(len(payload)),
        ]
        + payload
        + [
            type1(2, REG_CRC, 1), 0x00000000,
            type1(2, REG_CMD, 1), CMD_DESYNC,
            NOOP, NOOP, NOOP, NOOP,
        ]
    )


def build_sequence(manifest: dict, candidate_frames: dict[int, list[int]]) -> list[list[int]]:
    """One envelope per pinned group. Returns a list of word lists, in order.

    `candidate_frames` must supply **every** target frame, not only the changed ones:
    §6 item 1. The flush frame is never taken from the caller — it comes from the manifest
    so that a candidate cannot influence it even by accident.
    """
    idcode = int(manifest["base_bitstream"]["idcode"], 16)
    pinned = {
        int(rec["far"], 16): [int(w, 16) for w in rec["words"]]
        for rec in manifest["frames"]
    }
    roles = {int(rec["far"], 16): rec["role"] for rec in manifest["frames"]}

    supplied = set(candidate_frames)
    targets = {far for far, role in roles.items() if role == "target"}
    if supplied != targets:
        missing = sorted(f"{f:#010x}" for f in targets - supplied)
        extra = sorted(f"{f:#010x}" for f in supplied - targets)
        raise SequenceError(
            f"a candidate must supply exactly the target frames — missing {missing}, "
            f"unexpected {extra}"
        )

    envelopes = []
    for env in manifest["write_envelope"]["envelopes"]:
        fars = [int(f, 16) for f in env["target_fars"]]
        flush_far = int(env["flush_far"], 16)
        # Mutation note: sourcing the flush frame from `candidate_frames` instead is an
        # equivalent mutant *while the set check above stands* — that check refuses any
        # key outside the targets, so a candidate can never carry a flush FAR to be found.
        # It is written this way so the guarantee does not depend on that check surviving.
        frames = [candidate_frames[far] for far in fars] + [pinned[flush_far]]
        envelopes.append(build_envelope(fars[0], frames, idcode))
    return envelopes


# ------------------------------------------------------------------------------- parsing


def parse_sequence(words: list[int]) -> dict:
    """Read one envelope's words back into structure, judging nothing.

    Two outputs, and the second one is why this function was rewritten. The summary lists
    (`commands`, `far_sets`, …) answer "what appears anywhere"; **`trace`** is the ordered
    sequence of non-payload packets, which answers "what exactly is sent, in what order".
    A gate built only on the summaries cannot see a MISSING command or a wrong CRC value —
    it can only see what is present and forbidden. The consumer demonstrated exactly that
    hole: removing WCFG, removing RCRC and writing a non-zero CRC each passed with zero
    findings.

    Anything not understood is recorded rather than skipped: an unknown packet is the
    single most interesting thing a gate can be told about, and a parser that ignored it
    would hand the gate a clean-looking record of a stream it did not read.
    """
    def truncated(reg, declared, available, index):
        """One rule for every payload read, type 1 and type 2 alike.

        Patching the four `payload[0]` sites would fix four symptoms of one defect: the
        parser read a declared length without proving the stream carries it. A truncated
        packet is DATA about a malformed stream — it becomes a trace entry and a record,
        never an exception. A gate that crashes has not judged anything
        (docs/claimb_preregistration.md).
        """
        entry = {
            "kind": "truncated",
            "reg": reg,
            "declared": declared,
            "available": available,
            "index": index,
        }
        record["truncated"].append(entry)
        trace.append(entry)

    record = {
        "leading_dummies": 0,
        "synced": False,
        "commands": [],
        "far_sets": [],
        "idcodes": [],
        "fdri": [],
        "crc_writes": [],
        "unknown": [],
        "truncated": [],
        "trailing_words": 0,
        "total_words": len(words),
        "trace": [],
    }
    trace = record["trace"]

    i = 0
    while i < len(words) and words[i] == DUMMY:
        record["leading_dummies"] += 1
        i += 1
    if record["leading_dummies"]:
        trace.append({"kind": "dummy", "count": record["leading_dummies"]})
    if i < len(words) and words[i] == SYNC:
        record["synced"] = True
        trace.append({"kind": "sync"})
        i += 1

    pending_fdri = None
    while i < len(words):
        word = words[i]
        if word == NOOP:
            record["trailing_words"] += 1
            trace.append({"kind": "noop"})
            i += 1
            continue
        htype = word >> 29
        if htype == 1:
            op, reg, count = (word >> 27) & 3, (word >> 13) & 0x3FFF, word & 0x7FF
            available = len(words) - (i + 1)
            if op == 2 and count > available:
                truncated(reg, count, available, i)
                break
            payload = words[i + 1: i + 1 + count] if op == 2 else []
            if op == 2 and reg == REG_CMD and count == 1:
                record["commands"].append(payload[0])
                trace.append({"kind": "cmd", "value": payload[0]})
            elif op == 2 and reg == REG_FAR and count == 1:
                record["far_sets"].append(payload[0])
                trace.append({"kind": "far", "value": payload[0]})
            elif op == 2 and reg == REG_IDCODE and count == 1:
                record["idcodes"].append(payload[0])
                trace.append({"kind": "idcode", "value": payload[0]})
            elif op == 2 and reg == REG_CRC and count == 1:
                record["crc_writes"].append(payload[0])
                trace.append({"kind": "crc", "value": payload[0]})
            elif op == 2 and reg == REG_FDRI:
                pending_fdri = {"far": record["far_sets"][-1] if record["far_sets"] else None,
                                "words": count, "start": i + 1}
                trace.append({"kind": "fdri_header", "words": count})
                if count:
                    pending_fdri["payload"] = words[i + 1: i + 1 + count]
                    record["fdri"].append(pending_fdri)
                    pending_fdri = None
            else:
                record["unknown"].append({"index": i, "word": word})
                trace.append({"kind": "write", "reg": reg, "op": op, "count": count})
            i += 1 + (count if op == 2 else 0)
        elif htype == 2:
            count = word & 0x7FFFFFF
            available = len(words) - (i + 1)
            if count > available:
                truncated(None, count, available, i)
                break
            block = {"far": record["far_sets"][-1] if record["far_sets"] else None,
                     "words": count, "start": i + 1,
                     "payload": words[i + 1: i + 1 + count]}
            if pending_fdri is not None:
                block["far"] = pending_fdri["far"]
                pending_fdri = None
            record["fdri"].append(block)
            trace.append({"kind": "fdri_data", "words": count})
            i += 1 + count
        else:
            record["unknown"].append({"index": i, "word": word})
            trace.append({"kind": "unknown", "word": word})
            i += 1

    return record


def split_frames(payload: list[int]) -> list[list[int]]:
    if len(payload) % bf.FRAME_WORDS:
        raise SequenceError(
            f"FDRI payload of {len(payload)} words is not a multiple of {bf.FRAME_WORDS}"
        )
    return [
        payload[k: k + bf.FRAME_WORDS]
        for k in range(0, len(payload), bf.FRAME_WORDS)
    ]


def to_bytes(words: list[int]) -> bytes:
    return b"".join(w.to_bytes(4, "big") for w in words)

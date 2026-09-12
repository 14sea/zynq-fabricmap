#!/usr/bin/env python3
"""B1Q transport isolation — the generator, driver and analyser (host-only, no board).

`docs/b1q_transport_plan_2026_09_07.md` §4 stage 1 asks for a generator/capture tool proved
against a separate traffic source. **This is the software half of that, and it says so**: the
plan's stage 1 also requires a physical acceptance — a second serial device or a physical
self-loopback — which has not happened and which a software pseudo-terminal cannot replace
(the owner's review of 2026-09-12, "scope correction"). Nothing here runs a condition of §3,
lifts the stop-loss, attributes anything, or touches a board.

What it supplies that the three lost B1Q sessions could not:

  * **known transmitted bytes, bound to THIS repetition** — every frame carries a token
    derived from the run id and the repetition number, and delivery is credited only on a
    byte-exact match with the frame that was generated for that repetition. A capture from an
    earlier repetition replayed into a later one is therefore not clean, it is a total loss;
  * **one loss unit** — an expected frame that was not delivered byte-exact, counted once,
    however its damage happens to parse. CRC failures, altered frames, unexpected frames,
    duplicates and reordering stay separately visible as diagnostics;
  * **a received-byte denominator** (plan §5), reported as unavailable when nothing arrived,
    never as a finite rate over bytes that were only sent;
  * **`TIOCGICOUNT` framing / parity / overrun / break counters**, before and after, which no
    session recorded and none could — it needs an open fd. Unavailable is recorded as
    unavailable with its reason, never as zero;
  * **a two-direction driver** that writes the stream frame by frame, checks every write
    completed, emits the host's commands on their own port at the points the recorded
    sessions emit them, reads incrementally with timestamps, and is bounded by a deadline
    checked around every operation;
  * **a finalisation that always lands** — raw capture, per-read timestamps, partial results,
    the stop reason and the attempted counters are exported even when the run dies, and the
    original error is preserved.

**Not a verdict input, and named so.** It adjudicates nothing. It is deliberately outside BOTH
pinned globs — `host/b1q_*.py` is B1Q's decision surface and `host/b2_*.py` is B2's, and a file
in either must be in that frozen table; B1's pin guard refused this file when it was first
written as `host/b1q_transport_rig.py`, and it was right to. Provenance comes from the run
record instead: the tool's sha256, the instrument's framing module and commit, and the run
parameters are written beside every result.
"""
from __future__ import annotations

import array
import base64
import fcntl
import hashlib
import json
import os
import sys
import time
import uuid
import zlib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import claimb_r1p_instrument as inst  # noqa: E402

sys.path.insert(0, str(inst.DEFAULT_ROOT / "host"))
import l5_notary as l5  # noqa: E402  — the instrument's real framing, read-only

MAGIC = l5.MAGIC

# The measured shape of a B1Q session, per session, as TRANSMITTED (a frame the board put on
# the wire, whether or not it survived). Derived from the committed console logs by
# `profile_from_log`; `tests/test_transport_rig.py` re-derives it and compares class by class,
# so the plan's §2 table is checked against the bytes rather than copied from the document.
SESSION_PROFILE = (
    #  type            count   min   max      (bytes per line, newline included)
    ("IDENT",              1, 1048, 1048),
    ("SIGNREQ",           12,  370,  375),
    ("HB",               176,   65,   66),
    ("REC",               12, 2610, 2915),
    ("AUDIT",             88,  304,  708),
    ("AUDIT_READY",       11,  230,  235),
    ("CLOSE",              1,  217,  217),
    ("TERM",               1,  724,  724),
)
PROFILE_SOURCE = "evidence/b1q/b1q_17A6_2026-09-08-01/console.log"
TIMELINE_SOURCE = "evidence/b1q/b1q_17A6_2026-09-08-01/timeline.json"
FRAMES_PER_PROFILE = sum(n for _, n, _, _ in SESSION_PROFILE)     # 302
RECORDS_PER_PROFILE = 11                                          # AUDIT_READY count: one per record
CHUNKS_PER_RECORD = 8                                             # 88 AUDIT / 11 records

#: The host's replies, BY THE RULE the recorded timeline shows, not by an invented cycle:
#: IDENT→IDENTACK, SIGNREQ→SIGNOK, AUDIT_READY→AUDITGET, each AUDIT→AUDITGET except the last
#: of a record's chunks→AUDITDONE, REC→RECACK, TERM→TERMACK. On the clean session that rule
#: reproduces its 125 host frames (88 AUDITGET, 11 SIGNOK, 11 AUDITDONE, 11 RECACK, 1 each of
#: IDENTACK / SIGNGET / RECGET / TERMACK — the two GETs being retries of its two forced
#: controls, which this rig does not transmit).
HOST_REPLY = {"IDENT": "IDENTACK", "SIGNREQ": "SIGNOK", "AUDIT_READY": "AUDITGET",
              "AUDIT": "AUDITGET", "REC": "RECACK", "TERM": "TERMACK"}
LAST_CHUNK_REPLY = "AUDITDONE"
#: The host's replies are REL-V4 FRAMES, not bare words: the instrument builds every one with
#: `build_line(type, seq, token, encode_payload(...))` (`l6_rec._tx`, `l6_console._rec_tx`,
#: `l5_notary.Relay`). Their lengths follow from the payload each carries — `{"seq": n}` for the
#: acknowledgements, and the signer's `sign_reply` for SIGNOK, whose shape is taken from the
#: archived `run_log.json` notary entries (commit 64 hex, six 16-hex expected tables, a 32-hex
#: tag). Built that way a SIGNOK is 469 bytes and an acknowledgement 69-72, against the 9-14
#: bytes the first version transmitted — which could not have occupied the wire as a session
#: does (the owner's P2-4).
SIGN_REPLY_SCHEMA = ("sign_reply", "1.0.0")
HOST_PAYLOAD_SOURCE = "evidence/b1q/b1q_17A6_2026-09-08-01/run_log.json"
#: Measured on the clean session's own timeline (tx → next rx): min 0.041 s, median 0.065 s.
TX_GAP_MEDIAN_S = 0.065
TX_GAP_MIN_S = 0.041

# Exposure and stopping criteria, fixed in advance (plan §5). The threshold is unchanged; what
# changed is the unit it counts, which is now one affected expected frame (see `analyse`).
EXPOSURE_REPETITIONS = 200
EXPOSURE_SECONDS = 3600.0
LOSSES_PER_REPETITION_STOP = 3
#: base64 grows four characters at a time, so an exact byte length is not always reachable.
LENGTH_TOLERANCE = 4
#: Wire time of one byte at 115200 8N1 (10 bits per character).
BYTE_TIME_S = 10 / 115200
#: A write must be bounded even when no deadline is left to bound it: an unbounded serial write
#: cannot be stopped by any check that runs after it (the owner's P2-3).
WRITE_TIMEOUT_S = 5.0

TIOCGICOUNT = 0x545D
ICOUNTER_FIELDS = ("cts", "dsr", "rng", "dcd", "rx", "tx", "frame", "overrun", "parity", "brk", "buf_overrun")

LOSS_UNIT = "one expected frame that was not delivered byte-exact, counted once"


class RigError(Exception):
    """The tool's own failure. A run that hits one STOPS (plan §5, 'any tool error') — and
    still finalises: the result and the raw capture are exported before this is raised."""

    def __init__(self, message: str, result: dict | None = None, export_dir: Path | None = None):
        super().__init__(message)
        self.result = result
        self.export_dir = export_dir


def self_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def provenance() -> dict:
    """What produced a result: this file, the instrument's framing module, its commit. Hashing
    one Python file does not describe the execution (the owner's P2-4)."""
    framing = Path(l5.__file__)
    return {"tool": "host/transport_rig.py", "tool_sha256": self_sha256(),
            "framing_module": str(framing), "framing_sha256": hashlib.sha256(framing.read_bytes()).hexdigest(),
            "instrument_root": str(inst.DEFAULT_ROOT),
            "instrument_commit": getattr(inst, "PINNED_COMMIT", None) or getattr(inst, "COMMIT", None),
            "loss_unit": LOSS_UNIT}


# ------------------------------------------------------------------ the measured profile


def profile_from_log(path: Path) -> dict:
    """The transmitted shape of one recorded session: per type, how many frames were put on the
    wire and their byte lengths. A CRC-failed line counts as transmitted — it is a frame that
    was sent and arrived damaged — and is reported separately so the two are never confused."""
    raw = Path(path).read_bytes()
    out: dict = {}
    losses: list[dict] = []
    offset = 0
    for ln in raw.split(b"\n"):
        start, offset = offset, offset + len(ln) + 1
        if not ln.startswith(MAGIC.encode() + b" "):
            continue
        parts = ln.split(b" ")
        kind, ok = "UNKNOWN", False
        if len(parts) == 6:
            body = b" ".join(parts[:5])
            ok = f"{zlib.crc32(body) & 0xFFFFFFFF:08x}".encode() == parts[5]
            try:
                cand = parts[1].decode("ascii")
            except UnicodeDecodeError:
                cand = ""
            if cand in l5.APP_TYPES or cand == "AUDIT_READY":
                kind = cand
        e = out.setdefault(kind, {"count": 0, "valid": 0, "crc_failed": 0, "min": None, "max": None})
        e["count"] += 1
        e["valid" if ok else "crc_failed"] += 1
        n = len(ln) + 1
        e["min"] = n if e["min"] is None else min(e["min"], n)
        e["max"] = n if e["max"] is None else max(e["max"], n)
        if not ok:
            seq = int(parts[2]) if len(parts) == 6 and parts[2].isdigit() else None
            losses.append({"type": kind, "seq": seq, "offset": start, "bytes": n})
    return {"file": str(path), "file_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "frames": out, "crc_failed": losses}


def host_schedule_from_timeline(path: Path) -> dict:
    """What the host actually sent in a recorded session, and when, from `timeline.json`'s two
    directions. The schedule this rig emits is the RULE this derives, not a cycle."""
    frames = json.loads(Path(path).read_text())["frames"]
    counts: dict = {}
    after: dict = {}
    gaps: list[float] = []
    for i, f in enumerate(frames):
        if f["dir"] != "tx":
            continue
        counts[f["type"]] = counts.get(f["type"], 0) + 1
        prev = next((g for g in reversed(frames[:i]) if g["dir"] == "rx"), None)
        after[f"{prev['type'] if prev else None}->{f['type']}"] = \
            after.get(f"{prev['type'] if prev else None}->{f['type']}", 0) + 1
        nxt = next((g for g in frames[i + 1:] if g["dir"] == "rx"), None)
        if nxt:
            gaps.append(nxt["t_mono"] - f["t_mono"])
    gaps.sort()
    return {"file": str(path), "tx_total": sum(counts.values()), "tx_by_type": counts,
            "rx_then_tx": after,
            "tx_to_next_rx_s": ({"n": len(gaps), "min": gaps[0], "median": gaps[len(gaps) // 2],
                                 "max": gaps[-1]} if gaps else None)}


# ------------------------------------------------------------------ the generated stream


@dataclass
class Frame:
    index: int
    kind: str
    seq: int
    target_bytes: int
    line: bytes = b""
    offset: int = 0
    record: int | None = None
    last_chunk: bool = False

    @property
    def bytes(self) -> int:
        return len(self.line)


def token_for(run_id: str, repetition: int) -> str:
    """Every frame carries the run and the repetition it belongs to, in the field rel-v4 already
    reserves for the epoch. Bytes from another repetition are therefore not merely equal-looking
    traffic: they are frames of a different epoch, and the analyser says so (the owner's P2-2 —
    a known expected byte string is not proof that those bytes were sent in THIS repetition)."""
    return hashlib.sha256(f"{run_id}|{repetition}".encode()).hexdigest()[:l5.TOKEN_HEX]


def _payload(index: int, kind: str, pad_raw: int) -> str:
    """Binary, not JSON: the shortest class on the wire is a 65-byte HB and a JSON payload does
    not fit in one. Six raw bytes (8 base64 characters) is the floor, which does."""
    seed = hashlib.sha256(f"{index}|{kind}".encode()).digest()
    head = index.to_bytes(4, "big") + seed[:2]
    pad = (seed * (pad_raw // len(seed) + 1))[:max(pad_raw, 0)] if pad_raw > 0 else b""
    return base64.urlsafe_b64encode(head + pad).decode()


def _index_of(payload: str) -> int:
    raw = base64.urlsafe_b64decode(payload.encode())
    if len(raw) < 6:
        raise ValueError("payload is shorter than the rig's header")
    return int.from_bytes(raw[:4], "big")


def build_frame(index: int, kind: str, seq: int, target: int, token: str) -> Frame:
    lo, hi = 0, target + 64
    while lo < hi:                       # the smallest pad whose line reaches the target
        mid = (lo + hi) // 2
        if len(l5.build_line(kind, seq, token, _payload(index, kind, mid)).encode()) >= target:
            hi = mid
        else:
            lo = mid + 1
    line = l5.build_line(kind, seq, token, _payload(index, kind, lo)).encode()
    if abs(len(line) - target) > LENGTH_TOLERANCE:
        raise RigError(f"frame {index} ({kind}) is {len(line)} bytes, {target} was asked for")
    return Frame(index=index, kind=kind, seq=seq, target_bytes=target, line=line)


def _targets(kind: str) -> list[int]:
    _, count, lo, hi = next(t for t in SESSION_PROFILE if t[0] == kind)
    return [lo if count == 1 else lo + round(i * (hi - lo) / (count - 1)) for i in range(count)]


def plan_frames(run_id: str = "rig", repetition: int = 0, profile=SESSION_PROFILE) -> list[Frame]:
    """One repetition = one session's worth of traffic, in a session's ORDER: IDENT, then a
    record group per record (SIGNREQ, REC, AUDIT_READY, its chunks, heartbeats between), then
    the two extra SIGNREQ/REC the measured profile carries, then CLOSE and TERM. The order
    matters because the host's schedule is derived from it, and because the real corruptions
    landed on both the longest and the shortest classes."""
    token = token_for(run_id, repetition)
    pools = {k: _targets(k) for k, _, _, _ in profile}
    frames: list[Frame] = []
    index = seq = 0

    def emit(kind: str, record=None, last_chunk=False):
        nonlocal index, seq
        f = build_frame(index, kind, seq, pools[kind].pop(0), token)
        f.record, f.last_chunk = record, last_chunk
        frames.append(f)
        index += 1
        seq += 1

    emit("IDENT")
    hb_per_record = len(pools["HB"]) // RECORDS_PER_PROFILE
    for r in range(RECORDS_PER_PROFILE):
        emit("SIGNREQ", record=r)
        for _ in range(hb_per_record // 2):
            emit("HB", record=r)
        emit("REC", record=r)
        emit("AUDIT_READY", record=r)
        for c in range(CHUNKS_PER_RECORD):
            emit("AUDIT", record=r, last_chunk=(c == CHUNKS_PER_RECORD - 1))
        for _ in range(hb_per_record - hb_per_record // 2):
            emit("HB", record=r)
    while pools["SIGNREQ"]:
        emit("SIGNREQ")
    while pools["REC"]:
        emit("REC")
    while pools["HB"]:
        emit("HB")
    emit("CLOSE")
    emit("TERM")
    offset = 0
    for f in frames:
        f.offset = offset
        offset += len(f.line)
    return frames


def stream_bytes(frames: list[Frame]) -> bytes:
    return b"".join(f.line for f in frames)


def host_payload(kind: str, seq: int) -> dict:
    """What each host reply carries. SIGNOK carries the signer's answer, whose shape is the
    archived `sign_reply`; everything else carries the sequence it acknowledges."""
    if kind != "SIGNOK":
        return {"seq": seq}
    seed = hashlib.sha256(f"sign_reply|{seq}".encode()).hexdigest()
    tables = hashlib.sha512(f"tables|{seq}".encode()).hexdigest()      # 128 hex: six 16-hex words
    return {"schema": SIGN_REPLY_SCHEMA[0], "schema_version": SIGN_REPLY_SCHEMA[1], "seq": seq,
            "commit": seed, "expected_tables": [tables[i * 16:(i + 1) * 16] for i in range(6)],
            "tag": seed[:32]}


def host_frame(kind: str, seq: int, token: str) -> bytes:
    """A real rel-v4 host frame, built by the instrument's own builder."""
    return l5.build_line(kind, seq, token, l5.encode_payload(host_payload(kind, seq))).encode()


def host_schedule(frames: list[Frame]) -> list[dict]:
    """The host's replies, placed after the frame that causes each — the rule
    `host_schedule_from_timeline` derives from a real session, applied to this stream, and
    framed the way the instrument frames them."""
    token = frames[0].line.split(b" ")[3].decode() if frames else ""
    out = []
    for i, f in enumerate(frames):
        reply = LAST_CHUNK_REPLY if (f.kind == "AUDIT" and f.last_chunk) else HOST_REPLY.get(f.kind)
        if reply:
            out.append({"after_frame": i, "frame_index": f.index, "caused_by": f.kind,
                        "reply": reply, "line": host_frame(reply, f.seq, token),
                        "gap_s": TX_GAP_MEDIAN_S})
    return out


def host_traffic_shape(frames: list[Frame]) -> dict:
    """What the host side puts on the wire for one repetition, by type and bytes — recorded so a
    run states its TX occupancy instead of implying it from a count of labels."""
    by: dict = {}
    for s in host_schedule(frames):
        e = by.setdefault(s["reply"], {"count": 0, "bytes": 0})
        e["count"] += 1
        e["bytes"] += len(s["line"])
    return {"by_type": by, "frames": sum(e["count"] for e in by.values()),
            "bytes": sum(e["bytes"] for e in by.values())}


# ------------------------------------------------------------------ what came back


def analyse(frames: list[Frame], received: bytes, expected_token: str | None = None,
            echo_ledger=None, echo_allowed: bool = False, censor_tail: bool = False) -> dict:
    """Compare what arrived against what was SENT in THIS repetition.

    One loss unit: an expected frame not delivered byte-exact, counted once. A frame damaged in
    a way that fails CRC, a frame whose payload was altered but whose CRC was rebuilt, and a
    frame deleted outright all weigh the same — one — because they are the same event: that
    frame did not arrive. CRC failures, altered frames, frames from another epoch, unexpected
    indexes, duplicates and reordering remain separately visible as diagnostics.

    Only COMPLETE lines — terminated by a newline — can be credited. An unterminated tail is a
    `fragment`, and a frame missing only its final newline is not delivered (the owner's P2-1:
    reconstructing `ln + b"\n"` for the last segment credited 302 frames over 98 598 of 98 599
    bytes). An empty line is a defect, not something to skip past.

    `echo_ledger` is a count, per line, of the host frames THIS rig SUCCESSFULLY wrote. On a
    self-loopback topology (`echo_allowed`) they come back in the capture and are neither
    transport damage nor traffic under test: each is consumed against its remaining count and
    reported as `host_echo`. A copy beyond that count, or an echo on a topology that does not
    echo, is `unexpected_echo` — a defect. Nothing else is ever normalised away.

    `censor_tail` is for a repetition cut short by a deadline or a tool error: frames whose write
    completed but whose bytes had nothing after them when the capture stopped were still in
    flight, and are reported as `censored` rather than counted as losses (the owner's P2-2: do
    not invent a definitive loss for bytes in flight at a cutoff). A frame that is missing while
    a LATER frame arrived is a real loss and stays one.
    """
    expected = stream_bytes(frames)
    by_index = {f.index: f for f in frames}
    token = expected_token if expected_token is not None else (frames[0].line.split(b" ")[3].decode() if frames else "")
    ledger = dict(echo_ledger or {})
    known_echo = frozenset(ledger)
    delivered: dict[int, int] = {}
    damaged: dict[int, str] = {}
    defects: list[dict] = []
    echoed: list[dict] = []
    order: list[int] = []
    offset = 0
    parts = received.split(b"\n")
    tail = parts[-1]                     # everything after the last newline: never a whole line
    for ln in parts[:-1]:
        start, offset = offset, offset + len(ln) + 1
        line = ln + b"\n"
        here = {"offset": start, "bytes": len(line)}
        if not ln:
            defects.append({**here, "kind": "empty_line"})
            continue
        if line in known_echo:
            if echo_allowed and ledger.get(line, 0) > 0:
                ledger[line] -= 1
                echoed.append(here)
            else:
                defects.append({**here, "kind": "unexpected_echo",
                                "note": ("more copies than were written" if echo_allowed else
                                         "this topology does not echo the host port back")})
            continue
        try:
            parsed = l5.parse_line(ln.decode("latin-1"))
        except l5.CrcError:
            defects.append({**here, "kind": "crc_failed"})
            continue
        except (l5.FrameError, ValueError):
            defects.append({**here, "kind": "malformed"})
            continue
        if parsed["token"] != token:
            defects.append({**here, "kind": "foreign_epoch", "token": parsed["token"][:12],
                            "note": "a frame from another run or repetition: not this repetition's traffic"})
            continue
        try:
            idx = _index_of(parsed["payload"])
        except Exception:                                  # noqa: BLE001
            defects.append({**here, "kind": "unreadable_payload"})
            continue
        if idx not in by_index:
            defects.append({**here, "kind": "unexpected_index", "index": idx})
            continue
        if ln + b"\n" != by_index[idx].line:
            # a valid CRC over bytes we did not send: the index alone must never credit delivery
            damaged[idx] = "altered"
            defects.append({**here, "kind": "altered", "index": idx,
                            "note": "valid frame, but not the bytes transmitted for this index"})
            continue
        delivered[idx] = delivered.get(idx, 0) + 1
        order.append(idx)
    if tail:
        defects.append({"offset": offset, "bytes": len(tail), "kind": "fragment",
                        "note": "an unterminated tail: not a complete line, so nothing in it is delivered"})
    missing = sorted(set(by_index) - set(delivered) - set(damaged))
    duplicated = sorted(i for i, n in delivered.items() if n > 1)
    out_of_order = order != sorted(order)
    censored: list[int] = []
    if censor_tail:
        last = max(delivered, default=-1)
        censored = [i for i in missing if i > last]
        missing = [i for i in missing if i <= last]
    losses = len(by_index) - len(delivered) - len(censored)   # ONE unit, counted once per frame
    unexpected = [d for d in defects if d["kind"] in ("foreign_epoch", "unexpected_index", "unreadable_payload")]
    divergence = _divergence(frames, received, expected, by_index, token, echoed)
    return {"frames_sent": len(frames), "frames_delivered": len(delivered),
            "host_echo_lines": len(echoed), "bytes_host_echo": sum(e["bytes"] for e in echoed),
            "loss_unit": LOSS_UNIT, "losses": losses,
            "missing": missing, "censored": censored, "damaged": sorted(damaged), "duplicated": duplicated,
            "out_of_order": out_of_order, "defects": defects,
            "defects_by_kind": {k: sum(1 for d in defects if d["kind"] == k) for k in {d["kind"] for d in defects}},
            "unexpected_frames": len(unexpected),
            "bytes_fragment": len(tail),
            "divergence": divergence,
            "bytes_sent": len(expected), "bytes_received": len(received),
            "clean": losses == 0 and not defects and not duplicated and not out_of_order and divergence is None}


def _divergence(frames, received: bytes, expected: bytes, by_index: dict, token: str, echoed=()):
    """Where the streams first differ, and where a VERIFIED expected frame resumes.

    The old field said `bytes_to_resync` but only found the next newline, which an inserted
    newline satisfies while the bytes after it are still the remainder of a broken frame (the
    owner's P3). Both are reported now, under names that say what each is."""
    if received == expected:
        return None
    if echoed and _without_accounted_echo(received, echoed) == expected:
        # every expected byte is present, in order, and the ONLY extra bytes are the accounted
        # echo occurrences at their own offsets — nothing else is removed (the owner's P2-1)
        return None
    n = min(len(received), len(expected))
    first = next((i for i in range(n) if received[i] != expected[i]), n)
    frame = next((f for f in frames if f.offset <= first < f.offset + len(f.line)), None)
    nl = received.find(b"\n", first)
    resync = None
    at = first
    while True:                                   # the next line that is byte-exactly an expected frame
        nxt = received.find(b"\n", at)
        if nxt < 0:
            break
        line, at = received[at:nxt + 1], nxt + 1
        head = line.split(b" ")
        if len(head) == 6 and head[3] == token.encode():
            try:
                idx = _index_of(head[4].decode())
            except Exception:                     # noqa: BLE001
                continue
            if idx in by_index and line == by_index[idx].line:
                resync = {"verified_frame_index": idx, "received_offset": nxt + 1 - len(line),
                          "expected_offset": by_index[idx].offset,
                          "bytes_after_first_divergence": (nxt + 1 - len(line)) - first}
                break
    return {"first_offset": first,
            "frame_index": None if frame is None else frame.index,
            "frame_kind": None if frame is None else frame.kind,
            "offset_in_frame": None if frame is None else first - frame.offset,
            "bytes_to_next_newline": (None if nl < 0 else nl - first + 1),
            "resynchronised_at": resync,
            "note": ("a newline is not evidence of resynchronisation; `resynchronised_at` is the next line "
                     "that is byte-exactly an expected frame of this repetition, or null if none follows"),
            "expected_bytes": len(expected), "received_bytes": len(received)}


# ------------------------------------------------------------------ the counters no session had


def _without_accounted_echo(received: bytes, echoed) -> bytes:
    """The received stream with EXACTLY the accounted echo occurrences cut out, at their own
    offsets. Nothing else is removed: a blank line, an extra copy or any other unsent byte stays
    in, so it still shows as a divergence (the owner's P2-1 — the previous version dropped any
    line that did not match, which let an echo activate a normalisation that hid bytes)."""
    keep, out = 0, bytearray()
    for e in sorted(echoed, key=lambda x: x["offset"]):
        out += received[keep:e["offset"]]
        keep = e["offset"] + e["bytes"]
    return bytes(out) + received[keep:]


def read_icounters(fd) -> dict:
    """`TIOCGICOUNT` — framing, parity, overrun and break counts, the measurement the three lost
    sessions could not supply. Unavailable is RECORDED as unavailable with its reason; it is
    never reported as zero, which would read as 'no errors'."""
    if fd is None:
        return {"available": False, "reason": "no fd supplied",
                "note": "no counter is reported; absence of a count is not a count of zero"}
    try:
        buf = array.array("i", [0] * 20)
        fcntl.ioctl(fd, TIOCGICOUNT, buf, True)
    except (OSError, AttributeError, TypeError) as exc:
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}",
                "note": "no counter is reported; absence of a count is not a count of zero"}
    return {"available": True, **{k: buf[i] for i, k in enumerate(ICOUNTER_FIELDS)}}


def counter_delta(before: dict, after: dict) -> dict:
    if not (before.get("available") and after.get("available")):
        return {"available": False, "reason": before.get("reason") or after.get("reason") or "not sampled"}
    return {"available": True, **{k: after[k] - before[k] for k in ICOUNTER_FIELDS}}


# ------------------------------------------------------------------ the transport


class Port:
    """One end of the rig's wiring, wrapping any object that can write and read bytes.

    Three roles, named separately because the conditions of plan §3 distinguish them: the
    SOURCE the generated traffic is injected into, the HOST port the replies are transmitted
    on, and the CAPTURE the bytes are read from. On a self-loopback all three are one device
    and the run record says so; on a two-device rig they are not.
    """

    def __init__(self, name: str, write=None, read=None, fd=None, takes_timeout: bool = False):
        self.name, self._write, self._read, self._fd = name, write, read, fd
        self._takes_timeout = takes_timeout

    def write(self, data: bytes, timeout: float | None = None) -> int:
        """`timeout` is the REMAINING budget, part of the transport contract: a transport that
        can bound its write must do so, because a post-operation check cannot bound a write that
        has already blocked (the owner's P2-3)."""
        try:
            n = self._write(data, timeout) if self._takes_timeout else self._write(data)
        except TypeError:                               # a writer that does not accept a budget
            self._takes_timeout = False
            n = self._write(data)
        if n is None:                                   # a transport that returns nothing
            raise RigError(f"{self.name}: write returned no count; a short write cannot be detected")
        if n != len(data):
            raise RigError(f"{self.name}: short write, {n} of {len(data)} bytes accepted")
        return n

    def read(self, timeout: float) -> bytes:
        return self._read(max(0.0, timeout)) or b""

    def fileno(self):
        return self._fd


@dataclass
class Repetition:
    """One profile repetition: what was PLANNED, what was attempted, what the transport actually
    accepted, what came back, and when.

    The four are separate because conflating them was the owner's P2-2: a run that stopped after
    one frame still reported 302 sent and 301 losses — frames that were never transmitted are
    not observed transport losses. Only `accepted` frames — those whose write completed — are
    the expected set an analysis may hold the capture to.
    """

    index: int
    frames: list = field(default_factory=list)               # planned
    attempted: list = field(default_factory=list)            # a write was started
    accepted: list = field(default_factory=list)             # the write completed in full
    uncertain: list = field(default_factory=list)            # started, outcome unknown: in flight
    received: bytearray = field(default_factory=bytearray)
    events: list = field(default_factory=list)
    host_writes: dict = field(default_factory=dict)          # line -> successful writes
    overlap: list = field(default_factory=list)
    ended: str = ""

    @property
    def bytes_accepted(self) -> int:
        return sum(f.bytes for f in self.accepted)


class Driver:
    """Writes the stream frame by frame, emits the host's replies on the host port at the points
    the recorded sessions emit them, and reads incrementally with timestamps — bounded by a
    deadline checked around every operation, not only between repetitions (the owner's P2-3)."""

    def __init__(self, source: Port, host: Port, capture: Port, tx_during_rx: bool = True,
                 read_timeout: float = 0.05, pace: bool = False, sleep=time.sleep, clock=time.monotonic):
        self.source, self.host, self.capture = source, host, capture
        self.tx_during_rx, self.read_timeout, self.pace = tx_during_rx, read_timeout, pace
        self.sleep, self.clock = sleep, clock
        self.echoes = source is host is capture
        self.topology = ("one device: source, host and capture are the same port, so this rig's own "
                         "host traffic returns in the capture and is counted as host_echo"
                         if self.echoes else
                         f"source={source.name}, host={host.name}, capture={capture.name}")

    def _remaining(self, deadline: float) -> float:
        return max(0.0, deadline - self.clock())

    def _wait(self, seconds: float, deadline: float) -> float:
        """Sleep, never past the deadline. A scheduled gap is capped by the remaining budget, so
        a run cannot overrun by waiting (the owner's P2-3)."""
        seconds = max(0.0, min(seconds, self._remaining(deadline)))
        if seconds > 0:
            self.sleep(seconds)
        return seconds

    def _drain(self, rep: Repetition, deadline: float) -> None:
        while True:
            left = self._remaining(deadline)
            if left <= 0:
                return
            chunk = self.capture.read(min(self.read_timeout, left))     # the wait is capped too
            if not chunk:
                return
            rep.received += chunk
            rep.events.append({"t": self.clock(), "op": "read", "bytes": len(chunk)})

    def run(self, rep: Repetition, deadline: float) -> Repetition:
        """One repetition, with expiry checked BEFORE every write.

        The source transmits CONTINUOUSLY: frame i+1 starts when frame i's bytes have left the
        wire, not when the host has finished replying. A reply is due the measured gap after the
        frame that causes it, which lands while the source is transmitting a LATER frame — which
        is what "host TX during RX" means, and what the recorded sessions did. The first version
        wrote a frame, slept its whole wire time and only then replied, so in a paced model all
        125 host writes happened after the source had finished: zero overlap (the owner's P2-4).
        Every host write now records whether the source was still transmitting, so a run states
        its achieved overlap instead of implying it from a count of labels.
        """
        schedule = {s["after_frame"]: s for s in host_schedule(rep.frames)} if self.tx_during_rx else {}
        source_free = self.clock()
        pending: list = []                      # (due, send) — replies the host owes

        def flush(until: float) -> None:
            """Emit every host reply whose due time has come, before the source frees up."""
            while pending and pending[0][0] <= until:
                due, send = pending.pop(0)
                self._wait(due - self.clock(), deadline)
                if self._remaining(deadline) <= 0:
                    return
                overlapping = self.clock() < source_free
                self.host.write(send["line"], self._remaining(deadline))
                rep.host_writes[send["line"]] = rep.host_writes.get(send["line"], 0) + 1
                rep.overlap.append({"t": self.clock(), "reply": send["reply"],
                                    "source_busy_until": source_free, "overlapping": overlapping})
                rep.events.append({"t": self.clock(), "op": "write_host", "caused_by": send["caused_by"],
                                   "bytes": len(send["line"]), "overlapping_source_tx": overlapping})

        for i, f in enumerate(rep.frames):
            if self._remaining(deadline) <= 0:
                rep.ended = f"deadline reached after {i} of {len(rep.frames)} frames"
                return rep
            self._wait(source_free - self.clock(), deadline)      # the source is still busy
            if self._remaining(deadline) <= 0:
                rep.ended = f"deadline reached before frame {i}"
                return rep
            start = self.clock()
            rep.attempted.append(f)
            try:
                self.source.write(f.line, self._remaining(deadline))
            except Exception:
                rep.uncertain.append(f)          # started, outcome unknown: never a definite loss
                raise
            rep.accepted.append(f)
            rep.events.append({"t": self.clock(), "op": "write_frame", "index": f.index,
                               "kind": f.kind, "bytes": f.bytes})
            source_free = start + (f.bytes * BYTE_TIME_S if self.pace else 0.0)
            send = schedule.get(i)
            if send is not None:
                pending.append((source_free + send["gap_s"], send))
            flush(source_free)                   # replies that fall inside this frame's wire time
            self._drain(rep, deadline)
        while pending and self._remaining(deadline) > 0:
            flush(pending[0][0])
            self._drain(rep, deadline)
        quiet = 0
        while quiet < 3 and self._remaining(deadline) > 0:   # bounded drain, never an open loop
            before = len(rep.received)
            self._drain(rep, deadline)
            quiet = quiet + 1 if len(rep.received) == before else 0
        if not rep.ended:
            rep.ended = "complete" if self._remaining(deadline) > 0 else "deadline reached while draining"
        return rep


# ------------------------------------------------------------------ a bounded run


@dataclass
class Run:
    """One condition, under the pre-registered exposure and stop rules of plan §5."""

    label: str
    repetitions: int = EXPOSURE_REPETITIONS
    seconds: float = EXPOSURE_SECONDS
    tx_during_rx: bool = True
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    results: list = field(default_factory=list)
    captures: list = field(default_factory=list)
    stopped: str = ""
    error: str | None = None
    topology: str = "not started"
    pace: bool = False
    read_timeout: float = 0.05

    def execute(self, source: Port, host: Port = None, capture: Port = None, fd=None,
                out_dir: Path | None = None, sleep=time.sleep, clock=time.monotonic,
                read_timeout: float = 0.05, pace: bool = False) -> dict:
        """Always produces a result and, when `out_dir` is given, always exports it — including
        the raw capture and the per-read timestamps — even when the run dies. On a tool error the
        ORIGINAL error is raised after the export, carrying the result and the export path."""
        host = host or source
        capture = capture or source
        driver = Driver(source, host, capture, self.tx_during_rx, read_timeout, pace, sleep, clock)
        self.topology, self.pace, self.read_timeout = driver.topology, pace, read_timeout
        started = clock()
        before = self._guarded(lambda: read_icounters(fd), "counters_before")
        failure: Exception | None = None
        try:
            for i in range(self.repetitions):
                if clock() - started >= self.seconds:
                    self.stopped = f"exposure: {self.seconds} s reached after {i} repetitions"
                    break
                rep = Repetition(index=i, frames=plan_frames(self.run_id, i))
                deadline = min(started + self.seconds, clock() + self.seconds)
                try:
                    driver.run(rep, deadline)
                except Exception as exc:                  # noqa: BLE001 — the PARTIAL capture is evidence
                    failure = exc
                    self.error = f"{type(exc).__name__}: {exc}"
                    self.stopped = f"tool error in repetition {i}: {self.error}"
                finally:
                    self.captures.append(rep)
                    self.results.append(self._analyse(rep, i, driver))
                res = self.results[-1]
                if failure is not None:
                    break
                if rep.ended.startswith("deadline"):
                    self.stopped = f"exposure: the deadline bounded repetition {i} ({rep.ended})"
                    break
                if res["losses"] >= LOSSES_PER_REPETITION_STOP:
                    self.stopped = (f"stop rule: {res['losses']} losses within repetition {i} "
                                    f"(>= {LOSSES_PER_REPETITION_STOP}) — the condition is reproducing the failure")
                    break
            else:
                self.stopped = f"exposure: {self.repetitions} repetitions completed"
        except Exception as exc:                          # noqa: BLE001 — anything else the run raised
            failure = failure or exc
            self.error = self.error or f"{type(exc).__name__}: {exc}"
            self.stopped = self.stopped or f"tool error: {self.error}"
        result = self._summarise(self._guarded(lambda: read_icounters(fd), "counters_after"), before)
        export = self._export(result, out_dir) if out_dir else None
        if export:
            result["exported_to"] = str(export)
        if failure is not None:
            raise RigError(self.stopped, result=result, export_dir=export) from failure
        return result

    @staticmethod
    def _guarded(fn, what: str):
        """Each finalisation component on its own: a failure here is recorded, never allowed to
        replace the run's primary error (the owner's P2-5)."""
        try:
            return fn()
        except Exception as exc:                          # noqa: BLE001
            return {"unavailable": True, "what": what, "error": f"{type(exc).__name__}: {exc}"}

    def _analyse(self, rep: Repetition, i: int, driver) -> dict:
        """Hold the capture to what the transport ACCEPTED, never to what was planned. Frames
        never attempted are not losses; a frame whose write started but did not complete is
        `uncertain`, not a definite loss (the owner's P2-2)."""
        def run_it():
            cut_short = bool(self.error) or rep.ended.startswith("deadline") or not rep.ended
            res = analyse(rep.accepted, bytes(rep.received), token_for(self.run_id, i),
                          echo_ledger=dict(rep.host_writes), echo_allowed=driver.echoes,
                          censor_tail=cut_short)
            overlapping = sum(1 for o in rep.overlap if o["overlapping"])
            res.update({"repetition": i, "ended": rep.ended,
                        "reads": sum(1 for e in rep.events if e["op"] == "read"),
                        "frames_planned": len(rep.frames), "frames_attempted": len(rep.attempted),
                        "frames_accepted": len(rep.accepted), "frames_uncertain": len(rep.uncertain),
                        "bytes_accepted": rep.bytes_accepted,
                        "incomplete": len(rep.accepted) < len(rep.frames),
                        "censored_in_flight": len(res.get("censored", [])),
                        "cut_short": cut_short,
                        "host_frames_written": sum(rep.host_writes.values()),
                        "host_writes_overlapping_source_tx": overlapping,
                        "note": ("frames never attempted are not counted as losses; an uncertain "
                                 "write is in flight, not a loss")})
            return res
        out = self._guarded(run_it, f"analysis of repetition {i}")
        if out.get("unavailable"):                        # a minimal, honest stand-in
            out.update({"repetition": i, "losses": 0, "bytes_received": len(rep.received),
                        "bytes_sent": rep.bytes_accepted, "frames_sent": len(rep.accepted),
                        "incomplete": True, "clean": False})
        return out

    def _summarise(self, after: dict, before: dict) -> dict:
        received = sum(r.get("bytes_received", 0) for r in self.results)
        losses = sum(r.get("losses", 0) for r in self.results)
        incomplete = any(r.get("incomplete") for r in self.results) or self.error is not None
        return {"label": self.label, "run_id": self.run_id, "tx_during_rx": self.tx_during_rx,
                "topology": self.topology,
                "provenance": self._guarded(provenance, "provenance"),
                "parameters": {"repetitions": self.repetitions, "seconds": self.seconds,
                               "stop_at_losses": LOSSES_PER_REPETITION_STOP,
                               "pace": self.pace, "read_timeout_s": self.read_timeout,
                               "baud": 115200, "byte_time_s": BYTE_TIME_S,
                               "tx_gap_s": TX_GAP_MEDIAN_S, "write_timeout_s": WRITE_TIMEOUT_S},
                "repetitions_run": len(self.results), "stopped": self.stopped, "error": self.error,
                # planned, attempted, accepted — never conflated
                "frames_planned": sum(r.get("frames_planned", 0) for r in self.results),
                "frames_accepted": sum(r.get("frames_accepted", 0) for r in self.results),
                "frames_uncertain": sum(r.get("frames_uncertain", 0) for r in self.results),
                "censored_in_flight": sum(r.get("censored_in_flight", 0) for r in self.results),
                "incomplete": incomplete,
                "completed_exposure": (not incomplete) and self.error is None,
                "host_frames_written": sum(r.get("host_frames_written", 0) for r in self.results),
                "host_writes_overlapping_source_tx": sum(r.get("host_writes_overlapping_source_tx", 0)
                                                         for r in self.results),
                "frames_sent": sum(r.get("frames_sent", 0) for r in self.results),
                "bytes_sent": sum(r.get("bytes_sent", 0) for r in self.results),
                # plan §5: losses per RECEIVED byte, with the denominator stated. Nothing
                # received is not a rate of zero and not a rate over what was sent: it is a
                # denominator that does not exist, and the losses are reported regardless.
                "denominator_bytes": received,
                "losses": losses,
                "losses_per_100k_bytes": (None if received == 0 else losses * 100000 / received),
                "denominator": ("received bytes, including every partial capture" if received else
                                "unavailable: nothing was received, so there is no denominator"),
                "counters_before": before, "counters_after": after,
                "counters_delta": counter_delta(before, after),
                "repetition_results": self.results,
                "scope": "a rig run under one condition; it attributes nothing, qualifies nothing, "
                         "and does not authorise a board session (plan §5, §6)"}

    def _export(self, result: dict, out_dir: Path) -> Path:
        """The finalisation that must land even when the run died — and even when part of it
        cannot be written.

        Every component is attempted INDEPENDENTLY and the summary is attempted whatever else
        failed: one outer `try` around all of them meant that failing `events_000.json` alone
        left `run.json` unwritten while the run still reported a completed exposure (the owner's
        P2-5). Secondary failures are recorded in `export_errors` and the export is marked
        incomplete; the run's primary error is never replaced.
        """
        d = Path(out_dir)
        errors: list[str] = []

        def attempt(what: str, fn):
            try:
                return fn()
            except Exception as exc:                      # noqa: BLE001
                errors.append(f"{what}: {type(exc).__name__}: {exc}")
                return None

        attempt("mkdir", lambda: d.mkdir(parents=True, exist_ok=True))
        manifest = []
        for rep in self.captures:                         # each file on its own
            raw, ev = f"capture_{rep.index:03d}.bin", f"events_{rep.index:03d}.json"
            wrote_raw = attempt(raw, lambda r=rep, n=raw: (d / n).write_bytes(bytes(r.received))) is not None
            wrote_ev = attempt(ev, lambda r=rep, n=ev: (d / n).write_text(json.dumps(r.events, indent=1) + "\n")) is not None
            manifest.append({"repetition": rep.index, "bytes": len(rep.received),
                             "capture": raw if wrote_raw else None, "events": ev if wrote_ev else None,
                             "sha256": hashlib.sha256(bytes(rep.received)).hexdigest()})
        result["captures"] = manifest
        result["export_errors"] = errors
        result["export_complete"] = not errors
        wrote = attempt("run.json", lambda: (d / "run.json").write_text(
            json.dumps(result, indent=1, sort_keys=True) + "\n"))
        if wrote is None:                                 # a minimal summary rather than none
            result["export_errors"] = errors
            result["export_complete"] = False
            attempt("run.min.json", lambda: (d / "run.min.json").write_text(json.dumps(
                {k: result.get(k) for k in ("label", "run_id", "stopped", "error", "losses",
                                            "denominator_bytes", "repetitions_run", "incomplete")}
                | {"export_errors": errors, "export_complete": False}, indent=1, sort_keys=True) + "\n"))
        return d


def callable_port(name: str, write, read, fd=None, takes_timeout: bool = False) -> Port:
    """A Port over two callables. `read(timeout)` must return what is available within the
    timeout, possibly b"" — a transport that blocks forever is not bounded by any deadline."""
    return Port(name, write=write, read=read, fd=fd, takes_timeout=takes_timeout)


def serial_port(device: str, baud: int = 115200, exclusive: bool = True) -> Port:
    """A real serial device — used by stage 2, never by this repository's tests. Opened
    EXCLUSIVELY, which is one of the plan's unexcluded hypotheses (§0.3: nothing recorded
    whether another process held the port) and is cheap to exclude."""
    import serial                                      # noqa: PLC0415 — optional dependency
    s = serial.Serial(device, baud, timeout=0.05, write_timeout=WRITE_TIMEOUT_S, exclusive=exclusive)

    def write(data, timeout=None):
        s.write_timeout = WRITE_TIMEOUT_S if timeout is None else max(0.0, min(WRITE_TIMEOUT_S, timeout))
        return s.write(data)

    def read(t):
        s.timeout = t
        return s.read(65536)
    return Port(device, write=write, read=read, fd=s.fileno(), takes_timeout=True)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--profile-from", type=Path, default=REPO_ROOT / PROFILE_SOURCE)
    ap.add_argument("--schedule-from", type=Path, default=REPO_ROOT / TIMELINE_SOURCE)
    ap.add_argument("--what", choices=["profile", "schedule", "plan"], default="profile")
    a = ap.parse_args(argv)
    if a.what == "schedule":
        print(json.dumps(host_schedule_from_timeline(a.schedule_from), indent=1, sort_keys=True))
        return 0
    if a.what == "plan":
        frames = plan_frames("cli", 0)
        by: dict = {}
        for f in frames:
            e = by.setdefault(f.kind, {"count": 0, "min": f.bytes, "max": f.bytes})
            e["count"] += 1
            e["min"], e["max"] = min(e["min"], f.bytes), max(e["max"], f.bytes)
        sched: dict = {}
        for s in host_schedule(frames):
            sched[s["line"].split(b" ")[0].decode()] = sched.get(s["line"].split(b" ")[0].decode(), 0) + 1
        print(json.dumps({"frames": len(frames), "bytes": len(stream_bytes(frames)),
                          "by_type": by, "host_schedule": sched}, indent=1, sort_keys=True))
        return 0
    print(json.dumps(profile_from_log(a.profile_from), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

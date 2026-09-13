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
import inspect
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
#: A damaged complete line of the SAME length as exactly one not-yet-observed expected frame,
#: differing from it in at most this many bytes, is an observation of that frame. Frames of one
#: repetition differ from each other in far more (seq, the index in the payload, the CRC), and
#: uniqueness is required at the time of the match, so a tie identifies nothing.
NEAR_MATCH_BYTES = 4
#: Wire time of one byte at 115200 8N1 (10 bits per character).
BYTE_TIME_S = 10 / 115200
#: A write must be bounded even when no deadline is left to bound it: an unbounded serial write
#: cannot be stopped by any check that runs after it (the owner's P2-3).
WRITE_TIMEOUT_S = 5.0

TIOCGICOUNT = 0x545D
ICOUNTER_FIELDS = ("cts", "dsr", "rng", "dcd", "rx", "tx", "frame", "overrun", "parity", "brk", "buf_overrun")

LOSS_UNIT = "one expected frame that was not delivered byte-exact, counted once"

#: Why a run ended — one of these, stated explicitly, so `completed_exposure` follows from the
#: reason and the traffic state rather than from the count of accepted writes (the owner's P2-3:
#: an early-loss stop at 1 of 200 repetitions, and a deadline that censored all 302 frames of a
#: repetition, both reported `completed_exposure: true`).
TERMINAL_REASONS = {
    "exposure_repetitions": "the registered number of repetitions ran and every one resolved",
    "exposure_seconds": "the registered time bound was reached between repetitions; every one resolved",
    "exposure_seconds_censored": "the registered time bound cut a repetition: its in-flight traffic "
                                 "is censored (or unresolved), so the exposure is reached but not complete",
    "stop_rule_losses": "the registered early-stop rule fired; the requested exposure was NOT run",
    "tool_error": "the driver raised; the run stopped there with its partial evidence",
    "analysis_unavailable": "the analyser raised: losses for that repetition are UNKNOWN, the run "
                            "stopped there (plan §5, 'any tool error'), no later repetition was started",
}


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
    completed but of which NOTHING was observed when the capture stopped were still in flight,
    and are reported as `censored` rather than counted as losses (the owner's P2-2 of the driver
    review: do not invent a definitive loss for bytes in flight at a cutoff). Observation and
    delivery are tracked separately (the owner's P2-2 of the boundary review: the frontier used
    to be `max(delivered)`, so a complete, damaged line for a frame beyond it — fully observed —
    was censored as in flight and its loss disappeared at the cutoff):

      * a frame is OBSERVED when it was delivered, when a valid frame carrying its index arrived
        altered, when a damaged complete line still identifies it by an intact header, or when
        the unterminated tail identifies it (`_identify`, deliberately conservative);
      * a missing frame at or below the observation frontier is a definitive loss — something
        later than it was observed; the frame the tail belongs to is `censored` as partial;
      * frames above the frontier are `censored` only when nothing unidentifiable arrived after
        the last identified observation. If damaged bytes that identify no frame arrived there,
        those frames are `unresolved` — reported as ambiguous, neither a loss nor in flight —
        because asserting zero damage for them would hide damage that was observed.

    A cutoff never turns bytes observed as damaged into unobserved in-flight traffic.
    """
    expected = stream_bytes(frames)
    by_index = {f.index: f for f in frames}
    token = expected_token if expected_token is not None else (frames[0].line.split(b" ")[3].decode() if frames else "")
    ledger = dict(echo_ledger or {})
    known_echo = frozenset(ledger)
    delivered: dict[int, int] = {}
    damaged: dict[int, str] = {}
    observed: dict[int, str] = {}        # index -> how it was observed, other than delivered
    unidentified: list[int] = []         # offsets of complete lines that identify no expected frame
    last_identified = -1                 # offset of the last line that identified an expected frame
    partial: int | None = None           # the frame the unterminated tail belongs to, if it says
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
            unidentified.append(start)
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
        except (l5.CrcError, l5.FrameError, ValueError) as exc:
            kind = "crc_failed" if isinstance(exc, l5.CrcError) else "malformed"
            idx, how = _identify(ln, token, _candidates(frames, delivered, observed), complete=True)
            if idx is None:
                defects.append({**here, "kind": kind})
                unidentified.append(start)
            else:                                          # observed, damaged, and known which
                defects.append({**here, "kind": kind, "index": idx, "identified_by": how})
                observed.setdefault(idx, kind)
                last_identified = start
            continue
        if parsed["token"] != token:
            defects.append({**here, "kind": "foreign_epoch", "token": parsed["token"][:12],
                            "note": "a frame from another run or repetition: not this repetition's traffic"})
            continue
        try:
            idx = _index_of(parsed["payload"])
        except Exception:                                  # noqa: BLE001
            defects.append({**here, "kind": "unreadable_payload"})
            unidentified.append(start)
            continue
        if idx not in by_index:
            defects.append({**here, "kind": "unexpected_index", "index": idx})
            unidentified.append(start)
            continue
        if ln + b"\n" != by_index[idx].line:
            # a valid CRC over bytes we did not send: the index alone must never credit delivery
            damaged[idx] = "altered"
            observed[idx] = "altered"
            last_identified = start
            defects.append({**here, "kind": "altered", "index": idx,
                            "note": "valid frame, but not the bytes transmitted for this index"})
            continue
        delivered[idx] = delivered.get(idx, 0) + 1
        last_identified = start
        order.append(idx)
    unidentified_tail = False
    if tail:
        partial, how = _identify(tail, token, _candidates(frames, delivered, observed), complete=False)
        unidentified_tail = partial is None
        defects.append({"offset": offset, "bytes": len(tail), "kind": "fragment", "index": partial,
                        "identified_by": how,
                        "note": "an unterminated tail: not a complete line, so nothing in it is delivered"})
    missing = sorted(set(by_index) - set(delivered) - set(damaged))
    duplicated = sorted(i for i, n in delivered.items() if n > 1)
    out_of_order = order != sorted(order)
    frontier = max([*delivered, *observed, *([partial] if partial is not None else [])], default=-1)
    censored: list[int] = []
    unresolved: list[int] = []
    cutoff = None
    if censor_tail:
        # bytes that identify no frame arrived AFTER the last identified observation: whatever is
        # above the frontier cannot be called in flight — some of it was observed, damaged
        ambiguous = unidentified_tail or any(o > last_identified for o in unidentified)
        resolved_missing: list[int] = []
        for i in missing:
            if partial is not None and i == partial:
                censored.append(i)               # its bytes were arriving when the capture stopped
            elif i > frontier:
                (unresolved if ambiguous else censored).append(i)
            else:
                resolved_missing.append(i)       # something later was observed: a definitive loss
        missing = resolved_missing
        cutoff = {"observation_frontier": frontier, "partial_frame": partial,
                  "unidentified_after_frontier": (sum(1 for o in unidentified if o > last_identified)
                                                  + (1 if unidentified_tail else 0)),
                  "ambiguous": ambiguous,
                  "note": ("frames above the frontier are censored only when nothing unidentifiable "
                           "arrived after the last identified observation; otherwise they are "
                           "unresolved — damage was observed there and cannot be attributed, so it is "
                           "neither a loss nor in flight")}
    # ONE unit, once per frame. `confirmed_losses` is what is DEFINITELY lost; `losses` is the total,
    # which is only known when nothing is unresolved — otherwise it is None, and the confirmed count
    # is its lower bound and confirmed + unresolved its upper bound (the owner's uncertainty review:
    # subtracting unresolved frames from `losses` let an uninterpretable capture report the same
    # unqualified zero as an intact one)
    confirmed = len(by_index) - len(delivered) - len(censored) - len(unresolved)
    losses = None if unresolved else confirmed
    unexpected = [d for d in defects if d["kind"] in ("foreign_epoch", "unexpected_index", "unreadable_payload")]
    divergence = _divergence(frames, received, expected, by_index, token, echoed)
    return {"frames_sent": len(frames), "frames_delivered": len(delivered),
            "host_echo_lines": len(echoed), "bytes_host_echo": sum(e["bytes"] for e in echoed),
            "loss_unit": LOSS_UNIT,
            "confirmed_losses": confirmed, "losses": losses, "losses_known": not unresolved,
            "losses_upper_bound": confirmed + len(unresolved),
            "missing": missing, "censored": censored, "unresolved": unresolved,
            "damaged": sorted(damaged), "duplicated": duplicated,
            # observation, separately from delivery
            "observed": sorted(set(delivered) | set(observed) | ({partial} if partial is not None else set())),
            "observed_damaged": {str(i): observed[i] for i in sorted(observed)},
            "cutoff": cutoff,
            "out_of_order": out_of_order, "defects": defects,
            "defects_by_kind": {k: sum(1 for d in defects if d["kind"] == k) for k in {d["kind"] for d in defects}},
            "unexpected_frames": len(unexpected),
            "bytes_fragment": len(tail),
            "divergence": divergence,
            "bytes_sent": len(expected), "bytes_received": len(received),
            "clean": (confirmed == 0 and not unresolved and not defects and not duplicated
                      and not out_of_order and divergence is None)}


def _candidates(frames, delivered, observed) -> list:
    """The expected frames nothing has yet been observed of — the only ones a damaged line or
    the tail can be an observation of."""
    return [f for f in frames if f.index not in delivered and f.index not in observed]


def _identify(ln: bytes, token: str, candidates: list, complete: bool) -> tuple[int | None, str | None]:
    """Which expected frame a DAMAGED complete line, or the unterminated tail, is an observation
    of — by correspondence with the known transmitted bytes — or None when that cannot be said
    defensibly. Returns (index, how).

    Three correspondences, each requiring a UNIQUE match among the frames not yet observed:

      * `prefix` — the bytes are a byte-exact prefix of exactly one candidate (a frame cut at the
        capture's end, or truncated); a prefix of several candidates identifies nothing;
      * `near` — a complete line of exactly one candidate's length, differing from it in at most
        `NEAR_MATCH_BYTES` bytes (a flip or two anywhere, the header included);
      * `header` — magic, kind, seq and token intact and agreeing with the candidate at that seq,
        the payload's own index agreeing when it still decodes, exactly one frame header in the
        line (a lost newline merges two frames: that is two frames' bytes, not one frame's), and
        a complete line not longer than the frame by more than the length tolerance.

    Anything less is unidentified, and an unidentified observation after the frontier makes the
    frames above it unresolved rather than censored.
    """
    pre = [f for f in candidates if f.line.startswith(ln)]
    if len(pre) == 1:
        return pre[0].index, "prefix"
    if len(pre) > 1:
        return None, None
    if complete:
        line = ln + b"\n"
        near = [f for f in candidates if len(f.line) == len(line)
                and sum(a != b for a, b in zip(f.line, line)) <= NEAR_MATCH_BYTES]
        if len(near) == 1:
            return near[0].index, "near"
        if len(near) > 1:
            return None, None
    magic = MAGIC.encode() + b" "
    parts = ln.split(b" ")
    if len(parts) < 5 or parts[0] != MAGIC.encode() or ln.count(magic) != 1:
        return None, None
    try:
        kind, seq, tok = parts[1].decode("ascii"), int(parts[2].decode("ascii")), parts[3].decode("ascii")
    except (UnicodeDecodeError, ValueError):
        return None, None
    f = next((c for c in candidates if c.seq == seq), None)
    if f is None or f.kind != kind or tok != token:
        return None, None
    try:
        if _index_of(parts[4].decode("ascii")) != f.index:
            return None, None
    except Exception:                                      # noqa: BLE001 — a damaged payload; the header stands
        pass
    if complete and len(ln) + 1 > len(f.line) + LENGTH_TOLERANCE:
        return None, None
    return f.index, "header"


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

    def __init__(self, name: str, write=None, read=None, fd=None, takes_timeout: bool = False, close=None):
        self.name, self._write, self._read, self._fd = name, write, read, fd
        self._takes_timeout, self._close = takes_timeout, close
        if write is not None:                           # the contract is checked BEFORE any byte moves
            fits = _signature_accepts(write, 2 if takes_timeout else 1)
            if fits is False:
                raise RigError(f"{name}: the writer is declared {'to take' if takes_timeout else 'not to take'} "
                               f"a timeout, but its signature does not accept "
                               f"{'(data, timeout)' if takes_timeout else '(data)'}; the contract is "
                               f"declared by the adapter, never probed by writing")

    def write(self, data: bytes, timeout: float | None = None) -> int:
        """`timeout` is the REMAINING budget, part of the transport contract: a transport that
        can bound its write must do so, because a post-operation check cannot bound a write that
        has already blocked (the owner's P2-3 of the driver review).

        The callback's contract is DECLARED by the adapter (`takes_timeout`) and checked against
        its signature at construction — it is never discovered by calling. An exception from an
        active write is that write's failure: it propagates unchanged, the frame becomes
        `uncertain` and the run stops. The previous version caught TypeError as "a writer that
        takes no timeout" and called the writer again; a writer that had accepted `abc` and then
        failed internally received `abcabc`, and the wrapper returned 3 with no error (the
        owner's P2-1 of the boundary review).
        """
        n = self._write(data, timeout) if self._takes_timeout else self._write(data)
        if n is None:                                   # a transport that returns nothing
            raise RigError(f"{self.name}: write returned no count; a short write cannot be detected")
        if n != len(data):
            raise RigError(f"{self.name}: short write, {n} of {len(data)} bytes accepted")
        return n

    def read(self, timeout: float) -> bytes:
        return self._read(max(0.0, timeout)) or b""

    def fileno(self):
        return self._fd

    def close(self) -> None:
        """Release the device. Declared by the adapter (`close=`); a port without one is a no-op.
        The device entry point calls this on EVERY return path (the owner's P2-2 of the
        entry-point review), so a refused preflight or a dead run never leaves an exclusive open
        behind."""
        if self._close is not None:
            self._close()


def _signature_accepts(fn, nargs: int) -> bool | None:
    """Whether `fn` can be called with `nargs` positional arguments, from its signature alone.
    None when the signature cannot be inspected (a builtin or C-implemented callable): then the
    adapter's declaration stands as declared — it is still never probed by calling."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return None
    try:
        sig.bind(*([None] * nargs))
    except TypeError:
        return False
    return True


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
    terminal: dict = field(default_factory=dict)             # {"reason": one of TERMINAL_REASONS, ...}
    secondary_errors: list = field(default_factory=list)
    topology: str = "not started"
    pace: bool = False
    read_timeout: float = 0.05

    def _end(self, reason: str, repetition: int | None, detail: str) -> None:
        """One terminal reason per run, stated once, first wins. `completed_exposure` is derived
        from it and from the traffic state in `_summarise`; nothing else sets it."""
        if not self.terminal:
            self.terminal = {"reason": reason, "meaning": TERMINAL_REASONS[reason],
                             "repetition": repetition, "detail": detail}
        if not self.stopped:
            self.stopped = detail

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
                    self._end("exposure_seconds", i, f"exposure: {self.seconds} s reached after {i} repetitions")
                    break
                rep = Repetition(index=i, frames=plan_frames(self.run_id, i))
                deadline = min(started + self.seconds, clock() + self.seconds)
                analysis_failure: Exception | None = None
                try:
                    driver.run(rep, deadline)
                except Exception as exc:                  # noqa: BLE001 — the PARTIAL capture is evidence
                    failure = exc
                    self.error = f"{type(exc).__name__}: {exc}"
                    self._end("tool_error", i, f"tool error in repetition {i}: {self.error}")
                finally:
                    self.captures.append(rep)
                    res, analysis_failure = self._analyse(rep, i, driver)
                    self.results.append(res)
                if analysis_failure is not None:
                    # plan §5, "any tool error": an analysis that raised leaves this repetition's
                    # losses UNKNOWN and the run stops HERE — no further transmission (the owner's
                    # P2-3: it used to substitute losses 0 and carry on into repetition 2)
                    text = f"{type(analysis_failure).__name__}: {analysis_failure}"
                    if failure is None:
                        failure = analysis_failure
                        self.error = text
                        self._end("analysis_unavailable", i,
                                  f"tool error: the analysis of repetition {i} is unavailable ({text}); "
                                  f"its losses are unknown and no later repetition was started")
                    else:
                        self.secondary_errors.append(f"analysis of repetition {i}: {text}")
                    break
                if failure is not None:
                    break
                if res["confirmed_losses"] >= LOSSES_PER_REPETITION_STOP:
                    # the registered threshold, on DEFINITE losses: three confirmed losses stop the
                    # run whatever else is unresolved, and however the repetition ended
                    self._end("stop_rule_losses", i,
                              f"stop rule: {res['confirmed_losses']} confirmed losses within repetition {i} "
                              f"(>= {LOSSES_PER_REPETITION_STOP}) — the condition is reproducing the failure; "
                              f"{i + 1} of {self.repetitions} requested repetitions were run")
                    break
                if rep.ended.startswith("deadline"):
                    reason = "exposure_seconds" if res.get("resolved") else "exposure_seconds_censored"
                    self._end(reason, i, f"exposure: the deadline bounded repetition {i} ({rep.ended}); "
                              + ("it resolved" if res.get("resolved") else
                                 f"{res.get('censored_in_flight', 0)} frames censored in flight, "
                                 f"{res.get('unresolved_at_cutoff', 0)} unresolved"))
                    break
            else:
                self._end("exposure_repetitions", None, f"exposure: {self.repetitions} repetitions completed")
        except Exception as exc:                          # noqa: BLE001 — anything else the run raised
            failure = failure or exc
            self.error = self.error or f"{type(exc).__name__}: {exc}"
            self._end("tool_error", None, f"tool error: {self.error}")
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

    def _analyse(self, rep: Repetition, i: int, driver) -> tuple[dict, Exception | None]:
        """Hold the capture to what the transport ACCEPTED, never to what was planned. Frames
        never attempted are not losses; a frame whose write started but did not complete is
        `uncertain`, not a definite loss (the owner's P2-2 of the driver review).

        A repetition is RESOLVED when every planned frame was accepted, nothing is uncertain, it
        was not cut short, and its analysis leaves nothing censored or unresolved; `incomplete`
        is the negation — not merely "fewer frames accepted than planned" (the owner's P2-3).
        Returns the result and, when the analysis itself raised, that exception: its losses are
        then UNKNOWN (`None`), never a numeric zero, and the caller stops the run.
        """
        cut_short = bool(self.error) or rep.ended.startswith("deadline") or not rep.ended
        counts = {"repetition": i, "ended": rep.ended, "cut_short": cut_short,
                  "reads": sum(1 for e in rep.events if e["op"] == "read"),
                  "frames_planned": len(rep.frames), "frames_attempted": len(rep.attempted),
                  "frames_accepted": len(rep.accepted), "frames_uncertain": len(rep.uncertain),
                  "bytes_accepted": rep.bytes_accepted,
                  "host_frames_written": sum(rep.host_writes.values()),
                  "host_writes_overlapping_source_tx": sum(1 for o in rep.overlap if o["overlapping"])}
        try:
            res = analyse(rep.accepted, bytes(rep.received), token_for(self.run_id, i),
                          echo_ledger=dict(rep.host_writes), echo_allowed=driver.echoes,
                          censor_tail=cut_short)
        except Exception as exc:                          # noqa: BLE001 — recorded, and it stops the run
            return {**counts, "unavailable": True, "what": f"analysis of repetition {i}",
                    "error": f"{type(exc).__name__}: {exc}", "analysis_available": False,
                    "losses": None, "confirmed_losses": None, "losses_upper_bound": None,
                    "losses_known": False, "clean": False, "resolved": False, "incomplete": True,
                    "censored_in_flight": None, "unresolved_at_cutoff": None,
                    "bytes_received": len(rep.received), "bytes_sent": rep.bytes_accepted,
                    "frames_sent": len(rep.accepted),
                    "note": ("the analysis raised: the losses of this repetition are UNKNOWN, not "
                             "zero; the raw capture is exported for a later analysis")}, exc
        resolved = (len(rep.accepted) == len(rep.frames) and not rep.uncertain and not cut_short
                    and not res["censored"] and not res["unresolved"])
        res.update({**counts, "analysis_available": True,
                    "resolved": resolved, "incomplete": not resolved,
                    "censored_in_flight": len(res["censored"]),
                    "unresolved_at_cutoff": len(res["unresolved"]),
                    "note": ("frames never attempted are not counted as losses; an uncertain "
                             "write is in flight, not a loss; unresolved frames are ambiguous "
                             "at a cutoff and are neither")})
        return res, None

    def _summarise(self, after: dict, before: dict) -> dict:
        received = sum(r.get("bytes_received", 0) for r in self.results)
        analysed = [r for r in self.results if r.get("analysis_available")]
        unanalysed = [r["repetition"] for r in self.results if not r.get("analysis_available")]
        confirmed = sum(r["confirmed_losses"] for r in analysed)
        unresolved = sum(r["unresolved_at_cutoff"] for r in analysed)
        # An unknown stays unknown, and a bound stays a bound. The TOTAL is a number only when every
        # repetition was analysed and nothing is unresolved; otherwise it is None with a named
        # reason, the confirmed count is kept as the lower bound, and — when every repetition was
        # analysed — confirmed + unresolved is the upper bound. `loss_metric` says which case this
        # is, so a result cannot be consumed as an exact zero rate (the owner's uncertainty review).
        if unanalysed:
            losses, upper = None, None
            metric = {"status": "unknown", "exact": False,
                      "reason": f"the analysis of repetition(s) {unanalysed} raised: no total and no bound; "
                                f"{confirmed} losses are confirmed in the analysed repetitions"}
        elif received == 0:
            losses, upper = confirmed, confirmed + unresolved
            metric = {"status": "no_denominator", "exact": False,
                      "reason": "nothing was received, so there is no rate; the censored state is preserved"}
        elif unresolved:
            losses, upper = None, confirmed + unresolved
            metric = {"status": "bounded", "exact": False,
                      "reason": f"{unresolved} frame(s) unresolved at a cutoff: the total is between "
                                f"{confirmed} confirmed and {confirmed + unresolved}; no exact rate"}
        else:
            losses, upper = confirmed, confirmed
            metric = {"status": "exact", "exact": True, "reason": "every repetition analysed, nothing unresolved"}
        resolved = bool(self.results) and all(r.get("resolved") for r in self.results)
        reason = self.terminal.get("reason")
        exposure_reached = reason in ("exposure_repetitions", "exposure_seconds", "exposure_seconds_censored")
        completed = exposure_reached and resolved and self.error is None and not unanalysed
        per100k = (lambda n: None if (n is None or received == 0) else n * 100000 / received)
        denominator = ("received bytes, including every partial capture" if received else
                       "unavailable: nothing was received, so there is no denominator")
        if metric["status"] != "exact":
            denominator += f"; loss metric {metric['status']}: {metric['reason']}"
        return {"label": self.label, "run_id": self.run_id, "tx_during_rx": self.tx_during_rx,
                "topology": self.topology,
                "provenance": self._guarded(provenance, "provenance"),
                "parameters": {"repetitions": self.repetitions, "seconds": self.seconds,
                               "stop_at_losses": LOSSES_PER_REPETITION_STOP,
                               "pace": self.pace, "read_timeout_s": self.read_timeout,
                               "baud": 115200, "byte_time_s": BYTE_TIME_S,
                               "tx_gap_s": TX_GAP_MEDIAN_S, "write_timeout_s": WRITE_TIMEOUT_S},
                "repetitions_run": len(self.results), "stopped": self.stopped, "error": self.error,
                "secondary_errors": list(self.secondary_errors),
                # why it ended, stated; completion is DERIVED from it and from the traffic state
                "terminal": self.terminal or {"reason": None, "meaning": "no terminal reason recorded"},
                "exposure_reached": exposure_reached,
                "traffic_resolved": resolved,
                # planned, attempted, accepted — never conflated
                "frames_planned": sum(r.get("frames_planned", 0) for r in self.results),
                "frames_accepted": sum(r.get("frames_accepted", 0) for r in self.results),
                "frames_uncertain": sum(r.get("frames_uncertain", 0) for r in self.results),
                "censored_in_flight": sum(r.get("censored_in_flight") or 0 for r in self.results),
                "unresolved_at_cutoff": sum(r.get("unresolved_at_cutoff") or 0 for r in self.results),
                "incomplete": not completed,
                "completed_exposure": completed,
                "host_frames_written": sum(r.get("host_frames_written", 0) for r in self.results),
                "host_writes_overlapping_source_tx": sum(r.get("host_writes_overlapping_source_tx", 0)
                                                         for r in self.results),
                "frames_sent": sum(r.get("frames_sent", 0) for r in self.results),
                "bytes_sent": sum(r.get("bytes_sent", 0) for r in self.results),
                # plan §5: losses per RECEIVED byte, with the denominator stated. Nothing
                # received is not a rate of zero and not a rate over what was sent: it is a
                # denominator that does not exist, and the losses are reported regardless.
                "denominator_bytes": received,
                # the TOTAL, a number only when exact; the confirmed count is always a number
                "losses": losses,
                "confirmed_losses": confirmed,
                "losses_upper_bound": upper,
                "repetitions_unanalysed": unanalysed,
                "loss_metric": metric,
                "losses_per_100k_bytes": per100k(losses),
                "confirmed_losses_per_100k_bytes": per100k(confirmed),      # a LOWER bound of the rate
                "losses_per_100k_bytes_upper_bound": per100k(upper),
                "denominator": denominator,
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
                {k: result.get(k) for k in ("label", "run_id", "stopped", "error", "losses", "confirmed_losses",
                                            "loss_metric", "denominator_bytes", "repetitions_run", "incomplete")}
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
    return Port(device, write=write, read=read, fd=s.fileno(), takes_timeout=True, close=s.close)


# ------------------------------------------------------------------ a real device (stage 1's physical half)


PREFLIGHT_TIMEOUT_S = 1.0      # how long the nonce may take to come back
PREFLIGHT_QUIET_S = 0.3        # how long the line must then be silent before exposure may start
PREFLIGHT_DEADLINE_S = 3.0     # the ABSOLUTE bound on the whole preflight: write, nonce and drain
PREFLIGHT_READ_S = 0.05


def device_identity(path: str) -> dict:
    """What the device node is, from the kernel: the resolved node and, when sysfs exposes it,
    the USB vendor:product, product string and serial. Best-effort METADATA, recorded so the run
    record shows what was opened; anything unreadable is recorded as unavailable with its reason,
    never guessed. It is not a gate by itself — the gate is `--expect-usb` (the owner's P3 of
    the entry-point review), which compares this record against the declared device BEFORE the
    port is opened."""
    out: dict = {"path": path}
    try:
        real = os.path.realpath(path)
        out["realpath"] = real
        st = os.stat(real)
        out["char_device"] = __import__("stat").S_ISCHR(st.st_mode)
        out["rdev"] = f"{os.major(st.st_rdev)}:{os.minor(st.st_rdev)}"
    except OSError as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    name = Path(real).name
    usb: dict = {}
    dev = Path("/sys/class/tty") / name / "device"
    try:
        node = dev.resolve()
        for _ in range(6):                             # walk up to the USB device with idVendor
            if (node / "idVendor").is_file():
                for k in ("idVendor", "idProduct", "manufacturer", "product", "serial", "busnum", "devnum"):
                    f = node / k
                    if f.is_file():
                        usb[k] = f.read_text().strip()
                break
            node = node.parent
        out["usb"] = usb or {"unavailable": True, "reason": f"no idVendor above {dev}"}
    except OSError as exc:
        out["usb"] = {"unavailable": True, "reason": f"{type(exc).__name__}: {exc}"}
    return out


def identity_matches(identity: dict, expected: str) -> tuple[bool, str]:
    """Does the recorded identity show the declared USB `vendor:product`? An UNAVAILABLE identity
    does not match — it cannot confirm anything — and the reason says so; it is never taken as a
    pass. Returns (matched, reason)."""
    usb = identity.get("usb") or {}
    if identity.get("error") or usb.get("unavailable") or not usb.get("idVendor"):
        why = identity.get("error") or usb.get("reason") or "no USB identity recorded"
        return False, f"identity unavailable, so {expected} cannot be confirmed: {why}"
    seen = f"{usb.get('idVendor', '')}:{usb.get('idProduct', '')}".lower()
    if seen != expected.strip().lower():
        return False, f"expected USB {expected}, the node is {seen}"
    return True, f"USB {seen} as expected"


def _attempt_counters(fd) -> dict:
    """One counter attempt, on its own: `read_icounters` reports an unavailable result itself,
    and anything else that raises is recorded the same way rather than replacing the preflight's
    primary error."""
    try:
        return read_icounters(fd)
    except Exception as exc:                              # noqa: BLE001
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}",
                "note": "no counter is reported; absence of a count is not a count of zero"}


def loopback_preflight(port: Port, clock=time.monotonic, deadline_s: float | None = None) -> dict:
    """Before spending an hour of exposure: is anything wired back at all, and is the line quiet?

    Writes one nonce line that is NOT a rel-v4 frame, waits up to `PREFLIGHT_TIMEOUT_S` for it,
    then drains until the line has been silent for `PREFLIGHT_QUIET_S` so nothing of it leaks
    into repetition 0's capture. The WHOLE of that — write, nonce and drain — is bounded by one
    absolute deadline (`PREFLIGHT_DEADLINE_S`), and every operation is capped by the remaining
    budget: a line that keeps producing bytes used to keep the drain alive indefinitely, growing
    the buffer, before `Run` had started its own clock (the owner's P2-1).

    Three outcomes are named, and nothing is inferred from an exception:
      * `refusal: "silence"` — nothing came back: the jumper is not in place, or this is not the
        port; refused rather than an hour of censored frames;
      * `refusal: "not_quiet"` — bytes were still arriving at the deadline: the exposure must
        not start with an unbounded backlog; what arrived is kept;
      * `error` — the write, a read or the port itself raised: the primary error is kept with the
        phase it struck in, and everything observed up to it is kept too.
    Anything that does come back (matched or not) is recorded byte-for-byte in `received_raw`
    (exported as `preflight_rx.bin`) and, absent a refusal or error, the run proceeds: a garbled
    preflight is evidence too. The counters are ATTEMPTED before and after, independently, on
    success and on failure; availability and its reason are recorded, never assumed (P3).
    """
    deadline_s = PREFLIGHT_DEADLINE_S if deadline_s is None else deadline_s
    nonce = f"PREFLIGHT {uuid.uuid4().hex}\n".encode()
    res: dict = {"nonce": nonce.decode(), "nonce_bytes": len(nonce),
                 "deadline_s": deadline_s, "nonce_timeout_s": PREFLIGHT_TIMEOUT_S, "quiet_s": PREFLIGHT_QUIET_S,
                 "phase": "counters_before", "failed_phase": None, "error": None,
                 "quiet": False, "refusal": None, "refused": None}
    try:
        fd = port.fileno()
    except Exception as exc:                              # noqa: BLE001 — recorded, and the counters say why
        fd, res["fileno_error"] = None, f"{type(exc).__name__}: {exc}"
    res["counters_before"] = _attempt_counters(fd)
    t0 = clock()
    got = bytearray()
    quiet_since = t0

    def remaining() -> float:
        return deadline_s - (clock() - t0)

    try:
        res["phase"] = "write"
        port.write(nonce, max(0.0, min(PREFLIGHT_TIMEOUT_S, remaining())))
        res["phase"] = "nonce"
        while remaining() > 0 and clock() - t0 < PREFLIGHT_TIMEOUT_S and nonce not in got:
            got += port.read(min(PREFLIGHT_READ_S, remaining()))
        res["phase"] = "drain"
        quiet_since = clock()
        while remaining() > 0 and clock() - quiet_since < PREFLIGHT_QUIET_S:
            chunk = port.read(min(PREFLIGHT_READ_S, remaining()))
            if chunk:
                got += chunk
                quiet_since = clock()
        res["quiet"] = clock() - quiet_since >= PREFLIGHT_QUIET_S
        res["phase"] = "done"
    except Exception as exc:                              # noqa: BLE001 — the PRIMARY error, kept as is
        res["error"] = f"{type(exc).__name__}: {exc}"
        res["failed_phase"] = res["phase"]
    finally:                                              # what was observed survives whatever happened
        res["counters_after"] = _attempt_counters(fd)
        res["counters_delta"] = counter_delta(res["counters_before"], res["counters_after"])
        res["elapsed_s"] = clock() - t0
        res["received_bytes"] = len(got)
        res["matched"] = nonce in got
        res["received_hex_head"] = bytes(got[:64]).hex()
        res["received_sha256"] = hashlib.sha256(bytes(got)).hexdigest()
        res["received_raw"] = bytes(got)
    if res["error"] is None:
        if not got:
            res["refusal"] = "silence"
            res["refused"] = ("no loopback: nothing came back within "
                              f"{PREFLIGHT_TIMEOUT_S} s — the TX→RX jumper is not in place, or this is not the port")
        elif not res["quiet"]:
            res["refusal"] = "not_quiet"
            res["refused"] = (f"not quiet: {len(got)} bytes received and still arriving at the {deadline_s} s "
                              f"preflight deadline — the exposure would start with a backlog, so it does not start")
    return res


def claim_destination(out: Path) -> tuple[int | None, str | None]:
    """Claim `out` as a FRESH evidence destination, before any port opens or any byte is written.

    A fresh directory is created; an existing directory is accepted only when it is empty. A
    nonempty one is refused with none of its bytes changed — a mistyped rerun used to overwrite
    `invocation.json`, the captures and the summary in place and leave the earlier run's extra
    captures beside them, a mixture of two acquisitions reported as `export_complete` (the owner's
    P2-3). Nothing is deleted to make room; a retry needs a new `--out`.

    The claim itself is atomic: the invocation record is created with `O_EXCL`, so two runs
    racing for the same empty directory cannot both proceed — the loser is refused here.
    Returns `(fd, None)` on success — the caller writes the invocation through that fd — or
    `(None, reason)`."""
    try:
        out.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        if not out.is_dir():
            return None, f"destination exists and is not a directory: {out}"
        try:
            entries = sorted(p.name for p in out.iterdir())
        except OSError as exc:
            return None, f"destination could not be listed: {type(exc).__name__}: {exc}"
        if entries:
            return None, (f"destination is not empty ({len(entries)} entries, e.g. {entries[:3]}): an earlier "
                          f"acquisition lives there and is left exactly as it is — use a new --out")
    except OSError as exc:
        return None, f"destination could not be created: {type(exc).__name__}: {exc}"
    try:
        return os.open(out / "invocation.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), None
    except FileExistsError:
        return None, f"destination was claimed by another run between the check and the claim: {out}"
    except OSError as exc:
        return None, f"destination could not be claimed: {type(exc).__name__}: {exc}"


def _write_evidence(path: Path, data) -> bool:
    """One evidence file. A seam: the tests fault it by name to prove each export is attempted
    on its own and that a failed export never replaces the primary error."""
    if isinstance(data, (bytes, bytearray)):
        path.write_bytes(bytes(data))
    else:
        path.write_text(data)
    return True


EXIT_MEANING = {
    0: "the run returned",
    2: "a tool error — in the preflight or in the run; the evidence that exists is exported",
    3: "refused before any exposure — the declared identity, or the preflight (silence / not quiet)",
    4: "the device would not open",
    5: "the evidence destination could not be claimed or written — nothing was spent on the device",
}


def run_device(a) -> int:
    """`run --device …`: one condition of plan §3 on a REAL serial device, under the registered
    exposure and stop rules, with everything the offline acceptance exports plus what only a
    real fd can give — the device's kernel identity and the `TIOCGICOUNT` counters, ATTEMPTED on
    it. Exit codes are the tool's state (`EXIT_MEANING`), not a verdict on the link; the tool
    adjudicates nothing.

    Order, and what each step guarantees (the owner's entry-point review, 2026-09-13):
      1. the destination is claimed, fresh and atomically, before anything else — P2-3;
      2. the invocation is recorded; with `--expect-usb`, the recorded identity is compared to
         the declared device BEFORE the port is opened, and a mismatch (or an unavailable
         identity) is a refusal — P3;
      3. the ports are opened; a failure closes whatever did open;
      4. the preflight runs inside its own guarded boundary: its record, its raw bytes and its
         counter attempts are exported independently on success and failure, a transport error
         there is exit 2 with the evidence on disk, and an export failure before the exposure is
         exit 5 rather than an hour spent without a record — P2-1, P2-2;
      5. the run; and on every return path, every opened port is closed BEFORE the brief is
         printed, so a close failure is in the brief too.
    """
    out = Path(a.out)
    export_errors: list[str] = []
    ports: list[tuple[str, Port]] = []                    # (device path, port), in the order opened

    def attempt(what: str, fn):
        try:
            return fn()
        except Exception as exc:                          # noqa: BLE001
            export_errors.append(f"{what}: {type(exc).__name__}: {exc}")
            return None

    close_errors: list[str] = []
    try:
        code, stage, more = _device_steps(a, out, ports, attempt)
    finally:                                              # every opened port, on every return path
        for name, p in reversed(ports):
            try:
                p.close()
            except Exception as exc:                      # noqa: BLE001 — reported, never masking the result
                close_errors.append(f"{name}: {type(exc).__name__}: {exc}")
    if stage == "run":                                    # complete only when the run's AND the entry's exports landed
        more["export_complete"] = bool(more.get("run_export_complete")) and not export_errors
    brief = {"label": a.label, "exit": code, "exit_meaning": EXIT_MEANING[code], "stage": stage,
             "device": a.device, "exported_to": str(out), "ports_closed": [name for name, _ in ports],
             "entry_export_errors": list(export_errors), "close_errors": close_errors, **more}
    print(json.dumps(brief, sort_keys=True))
    return code


def _device_steps(a, out: Path, ports: list, attempt) -> tuple[int, str, dict]:
    """The steps of `run_device`, returning (exit, stage, brief fields). `ports` is filled with
    (device path, port) as devices open so the caller can close exactly what opened."""
    fd, refused = claim_destination(out)
    if fd is None:
        return 5, "destination", {"refusal": "destination", "refused": refused}
    invocation = {"argv": list(a.argv), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  "label": a.label, "device": a.device, "host_device": a.host_device,
                  "capture_device": a.capture_device, "baud": a.baud,
                  "tx_during_rx": a.tx_during_rx, "repetitions": a.repetitions, "seconds": a.seconds,
                  "pace": a.pace, "read_timeout_s": a.read_timeout, "preflight": not a.no_preflight,
                  "expect_usb": a.expect_usb,
                  "identity": {"source": attempt("identity source", lambda: device_identity(a.device)),
                               **({"host": attempt("identity host", lambda: device_identity(a.host_device))}
                                  if a.host_device else {}),
                               **({"capture": attempt("identity capture", lambda: device_identity(a.capture_device))}
                                  if a.capture_device else {})},
                  "identity_note": ("the kernel's record of what was opened — metadata, not acceptance; "
                                    "the gate is `expect_usb`, when given"),
                  "provenance": attempt("provenance", provenance)}
    if a.expect_usb:
        ok, why = identity_matches(invocation["identity"]["source"] or {}, a.expect_usb)
        invocation["identity_check"] = {"expected_usb": a.expect_usb, "matched": ok, "reason": why}

    def write_invocation() -> bool:
        try:
            f = os.fdopen(fd, "w")                        # the claimed file; closes the claim fd
        except Exception:
            os.close(fd)
            raise
        with f:
            f.write(json.dumps(invocation, indent=1, sort_keys=True) + "\n")
        return True
    if attempt("invocation.json", write_invocation) is None:
        return 5, "invocation", {}
    if a.expect_usb and not invocation["identity_check"]["matched"]:
        return 3, "identity", {"refusal": "identity", "refused": invocation["identity_check"]["reason"],
                               "identity": invocation["identity"]["source"]}
    try:
        source = serial_port(a.device, a.baud)
        ports.append((a.device, source))
        host = capture = None
        if a.host_device:
            host = serial_port(a.host_device, a.baud)
            ports.append((a.host_device, host))
        if a.capture_device:
            capture = serial_port(a.capture_device, a.baud)
            ports.append((a.capture_device, capture))
    except Exception as exc:                              # noqa: BLE001 — a device that will not open
        error = f"{type(exc).__name__}: {exc}"
        attempt("open_error.json", lambda: _write_evidence(
            out / "open_error.json", json.dumps({"error": error, "device": a.device,
                                                 "opened": [name for name, _ in ports]}, indent=1) + "\n"))
        return 4, "open", {"error": error}
    if not a.no_preflight:
        if capture is None:
            pre = loopback_preflight(source)
        else:
            pre = {"skipped": True, "reason": "a two-device topology has no self-loopback to preflight",
                   "error": None, "refusal": None, "refused": None, "received_raw": b""}
        raw = pre.pop("received_raw", b"")
        wrote_raw = attempt("preflight_rx.bin", lambda: _write_evidence(out / "preflight_rx.bin", raw))
        pre["received_file"] = "preflight_rx.bin" if wrote_raw else None
        wrote = attempt("preflight.json", lambda: _write_evidence(
            out / "preflight.json", json.dumps(pre, indent=1, sort_keys=True) + "\n"))
        summary = {"preflight": {k: pre.get(k) for k in ("matched", "received_bytes", "quiet", "elapsed_s",
                                                          "failed_phase", "counters_delta", "skipped",
                                                          "received_file")}}
        if pre.get("error"):                              # the transport raised: the primary error, exit 2
            return 2, "preflight", {"error": pre["error"], "failed_phase": pre.get("failed_phase"), **summary}
        if pre.get("refused"):
            return 3, "preflight", {"refusal": pre["refusal"], "refused": pre["refused"],
                                    "counters": pre.get("counters_after"), **summary}
        if wrote is None or wrote_raw is None:            # no record of the preflight: nothing is spent
            return 5, "preflight_export", summary
    run = Run(a.label, repetitions=a.repetitions, seconds=a.seconds, tx_during_rx=a.tx_during_rx)
    code, result = 0, None
    try:
        result = run.execute(source, host=host, capture=capture, fd=source.fileno(), out_dir=out,
                             read_timeout=a.read_timeout, pace=a.pace)
    except RigError as exc:
        code, result = 2, exc.result or {"stopped": str(exc), "error": str(exc)}
    return code, "run", {
        "topology": result.get("topology"),
        "terminal": (result.get("terminal") or {}).get("reason"), "stopped": result.get("stopped"),
        "error": result.get("error"), "repetitions_run": result.get("repetitions_run"),
        "frames_accepted": result.get("frames_accepted"),
        "confirmed_losses": result.get("confirmed_losses"), "losses": result.get("losses"),
        "loss_metric": (result.get("loss_metric") or {}).get("status"),
        "denominator_bytes": result.get("denominator_bytes"),
        "losses_per_100k_bytes": result.get("losses_per_100k_bytes"),
        "censored_in_flight": result.get("censored_in_flight"),
        "unresolved_at_cutoff": result.get("unresolved_at_cutoff"),
        "counters_delta": result.get("counters_delta"), "completed_exposure": result.get("completed_exposure"),
        "run_export_complete": result.get("export_complete"),
        "run_export_errors": result.get("export_errors"),
        "export_complete": None,                          # filled by the caller once the ports are closed
    }


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("profile", help="the transmitted shape of a recorded session, from its console log")
    p.add_argument("--profile-from", type=Path, default=REPO_ROOT / PROFILE_SOURCE)
    p = sub.add_parser("schedule", help="the host's replies in a recorded session, from its timeline")
    p.add_argument("--schedule-from", type=Path, default=REPO_ROOT / TIMELINE_SOURCE)
    sub.add_parser("plan", help="what the generator emits for one repetition")
    r = sub.add_parser("run", help="one condition of plan §3 on a real serial device (stage 1's physical half)")
    r.add_argument("--device", required=True, help="the source port; on a self-loopback also host and capture")
    r.add_argument("--host-device", default=None, help="a separate port for the host's replies (two-device rig)")
    r.add_argument("--capture-device", default=None, help="a separate port the capture is read from")
    r.add_argument("--label", required=True)
    r.add_argument("--out", required=True,
                   help="evidence directory, claimed FRESH (new, or existing and empty); a nonempty one is refused")
    r.add_argument("--expect-usb", default=None, metavar="VID:PID",
                   help="refuse, before opening, unless the source node's USB identity is this (e.g. 1a86:7523); "
                        "without it the identity is recorded as metadata only")
    r.add_argument("--baud", type=int, default=115200)
    tx = r.add_mutually_exclusive_group(required=True)
    tx.add_argument("--tx-during-rx", dest="tx_during_rx", action="store_true")
    tx.add_argument("--no-tx-during-rx", dest="tx_during_rx", action="store_false")
    r.add_argument("--repetitions", type=int, default=EXPOSURE_REPETITIONS)
    r.add_argument("--seconds", type=float, default=EXPOSURE_SECONDS)
    r.add_argument("--pace", action="store_true", help="model the source's wire time between frames")
    r.add_argument("--read-timeout", type=float, default=0.05)
    r.add_argument("--no-preflight", action="store_true", help="skip the loopback nonce check")
    a = ap.parse_args(argv)
    a.argv = list(argv if argv is not None else sys.argv[1:])
    if a.cmd == "schedule":
        print(json.dumps(host_schedule_from_timeline(a.schedule_from), indent=1, sort_keys=True))
        return 0
    if a.cmd == "plan":
        frames = plan_frames("cli", 0)
        by: dict = {}
        for f in frames:
            e = by.setdefault(f.kind, {"count": 0, "min": f.bytes, "max": f.bytes})
            e["count"] += 1
            e["min"], e["max"] = min(e["min"], f.bytes), max(e["max"], f.bytes)
        sched: dict = {}
        for s_ in host_schedule(frames):
            k = s_["line"].split(b" ")[1].decode()
            sched[k] = sched.get(k, 0) + 1
        print(json.dumps({"frames": len(frames), "bytes": len(stream_bytes(frames)),
                          "by_type": by, "host_schedule": sched}, indent=1, sort_keys=True))
        return 0
    if a.cmd == "run":
        return run_device(a)
    print(json.dumps(profile_from_log(a.profile_from), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

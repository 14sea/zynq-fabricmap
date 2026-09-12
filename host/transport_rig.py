#!/usr/bin/env python3
"""B1Q transport isolation — stage 1's generator and capture tool (host-only, no board).

`docs/b1q_transport_plan_2026_09_07.md` §4 stage 1: **build the generator/capture tool and
prove it against a separate traffic source, not the Zynq.** This is that tool. It does not
run any condition of §3 (that is stage 2, and it needs a host and a rig the owner must
supply — §7's three open questions), and it attributes nothing: the plan's §6 stands,
CH340/driver, USB-IP/WSL, wiring, board UART and host handling all remain open.

What it is for, in the plan's words: *"the generator emits a deterministic, seed-derived
stream framed to the length distribution above, with a per-frame sequence number and a
per-byte position check, so any loss is localisable by offset and length rather than
inferred from a retransmission. This removes the comparison-provenance weakness of the
post-hoc analysis: the transmitted bytes are known in advance, not reconstructed."*

Four things it supplies that the three lost B1Q sessions did not have:

  * **known transmitted bytes** — the stream is generated, so a divergence is measured
    against what was sent, not against a retransmission of unknown provenance;
  * **per-byte localisation** — first divergence offset, the frame and the offset inside it,
    and the length of the divergence run before resynchronisation;
  * **`TIOCGICOUNT` framing / parity / overrun / break counters**, sampled before and after,
    which no session recorded and which cannot be read without an open fd;
  * **a pre-registered exposure and stop rule** (§5), so a run ends by its own rule.

Deliberate differences from a real session, both stated so no one reads more into a run:

  * every frame the rig transmits is **well formed**. A real B1Q session contains two
    FORCED controls (a corrupted SIGNREQ seq 1 and a corrupted REC) which are a session
    design feature, not transport. Removing them means every CRC failure a run observes is
    a transport event, with no control to subtract.
  * the payloads are the rig's own. The framing is the instrument's real rel-v4
    (`P3L5 <type> <seq> <token> <payload> <crc32>\\n`, CRC32 over the body) built with the
    instrument's own `l5_notary.build_line`, so the bytes on the wire are the real shape and
    the parser under test is the real parser.

**Not a verdict input, and named so.** It adjudicates nothing: no B1Q or B2 verdict reads it.
It is deliberately outside BOTH pinned globs — `host/b1q_*.py` is B1Q's decision surface and
`host/b2_*.py` is B2's, and a file in either must be in that frozen table. Putting an
investigation tool there would either churn a frozen manifest or quietly claim an authority it
does not have; B1's pin guard refused exactly that when this file was first written as
`host/b1q_transport_rig.py`, and it was right to.

Provenance instead of pinning: a run records this file's own sha256 beside its results
(`self_sha256`), so any result can be tied to the bytes that produced it. If a transport
measurement ever becomes an input to a verdict it must be pinned by that decision's record —
and per the plan, instrumenting a SESSION is a pinned change that lands, is reviewed and is
re-qualified BEFORE the session that counts.
"""
from __future__ import annotations

import array
import base64
import fcntl
import hashlib
import json
import sys
import time
import zlib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import claimb_r1p_instrument as inst  # noqa: E402

sys.path.insert(0, str(inst.DEFAULT_ROOT / "host"))
import l5_notary as l5  # noqa: E402  — the instrument's real framing, read-only

MAGIC = l5.MAGIC
TOKEN = "b1c0a5e7d3f24916b8e05a7c41d39f62"          # a rig token: 32 hex, never a session token

# The measured shape of a B1Q session, per session, as TRANSMITTED (a frame the board put on
# the wire, whether or not it survived). Derived from the committed console logs by
# `profile_from_log`, and `tests/test_b1q_transport_rig.py` re-derives it from the clean
# session and compares — the plan's §2 table is checked against the bytes, not copied.
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
FRAMES_PER_PROFILE = sum(n for _, n, _, _ in SESSION_PROFILE)     # 302

# The host's send bursts (plan §2): the condition "host transmitting while receiving" is one
# of the things under test, so a rig run reproduces them with the measured gap.
HOST_SENDS = ("AUDITGET", "SIGNOK", "AUDITDONE", "RECACK", "RECGET", "IDENTACK", "SIGNGET", "AUDITABORT")
TX_GAP_MEDIAN_S = 0.062
TX_GAP_MIN_S = 0.041

# Exposure and stopping criteria, fixed in advance (plan §5)
EXPOSURE_REPETITIONS = 200
EXPOSURE_SECONDS = 3600.0
LOSSES_PER_REPETITION_STOP = 3

#: base64 grows four characters at a time, so an exact byte length is not always reachable.
#: The achieved length is recorded on every frame and must lie within this of the target.
LENGTH_TOLERANCE = 4

TIOCGICOUNT = 0x545D
ICOUNTER_FIELDS = ("cts", "dsr", "rng", "dcd", "rx", "tx", "frame", "overrun", "parity", "brk", "buf_overrun")


class RigError(Exception):
    """The tool's own failure. A run that raises it STOPS (plan §5: 'any tool error')."""


# ------------------------------------------------------------------ the measured profile


def profile_from_log(path: Path) -> dict:
    """The transmitted shape of one recorded session: per type, how many frames were put on
    the wire and their byte lengths. A CRC-failed line counts as transmitted — it is a frame
    that was sent and arrived damaged — and is reported separately so the two are never
    confused. A line whose type field is itself unreadable is counted under `UNKNOWN`."""
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
            if cand in l5.APP_TYPES or cand in ("AUDIT_READY",):
                kind = cand
        e = out.setdefault(kind, {"count": 0, "valid": 0, "crc_failed": 0, "min": None, "max": None})
        e["count"] += 1
        e["valid" if ok else "crc_failed"] += 1
        n = len(ln) + 1
        e["min"] = n if e["min"] is None else min(e["min"], n)
        e["max"] = n if e["max"] is None else max(e["max"], n)
        if not ok:
            seq = None
            if len(parts) == 6 and parts[2].isdigit():
                seq = int(parts[2])
            losses.append({"type": kind, "seq": seq, "offset": start, "bytes": n})
    return {"file": str(path), "file_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "frames": out, "crc_failed": losses}


# ------------------------------------------------------------------ the generated stream


@dataclass
class Frame:
    index: int
    kind: str
    seq: int
    target_bytes: int
    line: bytes = b""
    offset: int = 0

    @property
    def bytes(self) -> int:
        return len(self.line)


def _payload(index: int, kind: str, pad_raw: int) -> str:
    """A payload that says where it belongs: the frame index, a check byte over index and
    type, and a deterministic pad derived from both — so a byte that lands in the wrong frame
    is detectable inside the payload as well as by its offset.

    Binary, not JSON: the shortest class on the wire is a 65-byte HB, and a JSON payload
    cannot fit in one. Six raw bytes (8 base64 characters) is the floor, which does fit.
    """
    seed = hashlib.sha256(f"{index}|{kind}".encode()).digest()
    head = index.to_bytes(4, "big") + seed[:2]
    pad = (seed * (pad_raw // len(seed) + 1))[:max(pad_raw, 0)] if pad_raw > 0 else b""
    return base64.urlsafe_b64encode(head + pad).decode()


def _index_of(payload: str) -> int:
    raw = base64.urlsafe_b64decode(payload.encode())
    if len(raw) < 6:
        raise ValueError("payload is shorter than the rig's header")
    return int.from_bytes(raw[:4], "big")


def build_frame(index: int, kind: str, seq: int, target: int) -> Frame:
    """A real rel-v4 line of (at least) the target length, padded deterministically. Base64
    grows in steps, so the achieved length is the first reachable one at or above the target;
    `plan_frames` only asks for targets inside the measured range and the achieved length is
    recorded, never assumed."""
    lo, hi = 0, target + 64
    while lo < hi:                       # the smallest pad whose line reaches the target
        mid = (lo + hi) // 2
        if len(l5.build_line(kind, seq, TOKEN, _payload(index, kind, mid)).encode()) >= target:
            hi = mid
        else:
            lo = mid + 1
    line = l5.build_line(kind, seq, TOKEN, _payload(index, kind, lo)).encode()
    f = Frame(index=index, kind=kind, seq=seq, target_bytes=target, line=line)
    if abs(len(line) - target) > LENGTH_TOLERANCE:
        raise RigError(f"frame {index} ({kind}) is {len(line)} bytes, {target} was asked for: "
                       f"base64 grows in steps of 4 and the floor for this type was not reachable")
    return f


def plan_frames(repetitions: int = 1, profile=SESSION_PROFILE) -> list[Frame]:
    """One repetition = one session's worth of traffic, interleaved the way a session is:
    IDENT first, TERM/CLOSE last, the rest spread so long and short frames alternate (the
    corrupted frames in the real sessions were REC, AUDIT, HB and TERM — the longest and the
    shortest classes, so a run must not put them all in one place)."""
    frames: list[Frame] = []
    index = seq = 0
    for rep in range(repetitions):
        head = [t for t in profile if t[0] == "IDENT"]
        tail = [t for t in profile if t[0] in ("CLOSE", "TERM")]
        mid = [t for t in profile if t[0] not in ("IDENT", "CLOSE", "TERM")]
        queue: list[tuple[str, int]] = []
        for kind, count, lo, hi in head + mid + tail:
            for i in range(count):
                # deterministic sweep across the measured range, endpoints included
                target = lo if count == 1 else lo + round(i * (hi - lo) / (count - 1))
                queue.append((kind, target))
        heads = [q for q in queue if q[0] == "IDENT"]
        tails = [q for q in queue if q[0] in ("CLOSE", "TERM")]
        body = [q for q in queue if q[0] not in ("IDENT", "CLOSE", "TERM")]
        body.sort(key=lambda q: (q[1] % 7, q[0], q[1]))          # interleave long and short
        for kind, target in heads + body + tails:
            frames.append(build_frame(index, kind, seq, target))
            index += 1
            seq += 1
    offset = 0
    for f in frames:
        f.offset = offset
        offset += len(f.line)
    return frames


def stream_bytes(frames: list[Frame]) -> bytes:
    return b"".join(f.line for f in frames)


def host_sends(frames: list[Frame]) -> list[dict]:
    """The host's TX bursts, placed by the measured tx→next-rx gap. Transmitted while the rig
    is receiving, which is one of the conditions under test (plan §3, A1/B1 vs A2/B2)."""
    out = []
    for i, f in enumerate(frames):
        if f.kind in ("SIGNREQ", "AUDIT_READY", "REC", "IDENT"):
            out.append({"after_frame": i, "line": f"{HOST_SENDS[i % len(HOST_SENDS)]} {f.seq}\n",
                        "gap_s": TX_GAP_MEDIAN_S})
    return out


# ------------------------------------------------------------------ what came back


def analyse(frames: list[Frame], received: bytes) -> dict:
    """Compare what arrived against what was SENT — never against a retransmission.

    Per frame: delivered / crc_failed / malformed / missing / duplicated / out_of_order.
    Per byte: the first divergence offset, which frame and which byte inside it, and how many
    bytes were skipped before the stream resynchronised. Both, because a frame-level count
    says a frame was lost and a byte-level offset says where.
    """
    expected = stream_bytes(frames)
    by_index = {f.index: f for f in frames}
    seen: dict[int, list[str]] = {}
    order: list[int] = []
    crc_failed, malformed = [], []
    offset = 0
    for ln in received.split(b"\n"):
        start, offset = offset, offset + len(ln) + 1
        if not ln:
            continue
        try:
            parsed = l5.parse_line(ln.decode("latin-1"))
        except l5.CrcError:
            crc_failed.append({"offset": start, "bytes": len(ln) + 1})
            continue
        except (l5.FrameError, ValueError):
            malformed.append({"offset": start, "bytes": len(ln) + 1})
            continue
        try:
            idx = _index_of(parsed["payload"])
        except Exception:                                  # noqa: BLE001 — a valid CRC over a payload we did not send
            malformed.append({"offset": start, "bytes": len(ln) + 1, "note": "payload is not the rig's"})
            continue
        if idx not in by_index:
            # A well-formed frame with a good CRC whose index was never transmitted. Counting it
            # as delivered would be exactly the provenance weakness this rig exists to remove:
            # the transmitted bytes are known, so a frame that is not one of them is a finding.
            malformed.append({"offset": start, "bytes": len(ln) + 1, "index": idx,
                              "note": "payload is not the rig's: index was never transmitted"})
            continue
        seen.setdefault(idx, []).append("delivered")
        order.append(idx)
    delivered = set(seen)
    missing = sorted(set(by_index) - delivered)
    duplicated = sorted(i for i, v in seen.items() if len(v) > 1)
    out_of_order = order != sorted(order)
    # the per-byte position check
    divergence = None
    if received != expected:
        n = min(len(received), len(expected))
        first = next((i for i in range(n) if received[i] != expected[i]), n)
        frame = next((f for f in frames if f.offset <= first < f.offset + len(f.line)), None)
        resync = received.find(b"\n", first)
        divergence = {"first_offset": first,
                      "frame_index": None if frame is None else frame.index,
                      "frame_kind": None if frame is None else frame.kind,
                      "offset_in_frame": None if frame is None else first - frame.offset,
                      "bytes_to_resync": (None if resync < 0 else resync - first + 1),
                      "expected_bytes": len(expected), "received_bytes": len(received)}
    losses = len(missing) + len(crc_failed) + len(malformed)
    return {"frames_sent": len(frames), "frames_delivered": len(delivered),
            "missing": missing, "duplicated": duplicated, "out_of_order": out_of_order,
            "crc_failed": crc_failed, "malformed": malformed,
            "losses": losses, "divergence": divergence,
            "bytes_sent": len(expected), "bytes_received": len(received),
            "clean": losses == 0 and not duplicated and not out_of_order and divergence is None}


# ------------------------------------------------------------------ the counters no session had


def self_sha256() -> str:
    """This file's bytes. A rig result carries it, so a measurement can be tied to the tool that
    made it without the tool sitting in a frozen pin table (see the module docstring)."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def read_icounters(fd: int) -> dict:
    """`TIOCGICOUNT` — framing, parity, overrun and break counts, the measurement the three
    lost sessions could not supply. Unavailable is RECORDED as unavailable with its reason;
    it is never reported as zero, which would read as 'no errors'."""
    try:
        buf = array.array("i", [0] * 20)
        fcntl.ioctl(fd, TIOCGICOUNT, buf, True)
    except (OSError, AttributeError) as exc:
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}",
                "note": "no counter is reported; absence of a count is not a count of zero"}
    return {"available": True, **{k: buf[i] for i, k in enumerate(ICOUNTER_FIELDS)}}


def counter_delta(before: dict, after: dict) -> dict:
    if not (before.get("available") and after.get("available")):
        return {"available": False, "reason": before.get("reason") or after.get("reason") or "not sampled"}
    return {"available": True, **{k: after[k] - before[k] for k in ICOUNTER_FIELDS}}


# ------------------------------------------------------------------ a bounded run


@dataclass
class Run:
    """One condition, under the pre-registered exposure and stop rules of plan §5."""

    label: str
    repetitions: int = EXPOSURE_REPETITIONS
    seconds: float = EXPOSURE_SECONDS
    tx_during_rx: bool = True
    results: list = field(default_factory=list)
    stopped: str = ""

    def execute(self, write, read, fd=None, sleep=time.sleep, clock=time.monotonic) -> dict:
        """`write(bytes)` and `read()` are the transport; `fd` (if given) is where the counters
        are read. Both a pty pair and an open serial port satisfy this, which is the point:
        stage 1 proves the tool without the Zynq."""
        started = clock()
        before = read_icounters(fd) if fd is not None else {"available": False, "reason": "no fd supplied"}
        for rep in range(self.repetitions):
            if clock() - started >= self.seconds:
                self.stopped = f"exposure: {self.seconds} s reached after {rep} repetitions"
                break
            frames = plan_frames(1)
            try:
                write(stream_bytes(frames))
                if self.tx_during_rx:
                    for send in host_sends(frames):
                        write(send["line"].encode())
                        if send["gap_s"]:
                            sleep(send["gap_s"])
                received = read()
            except Exception as exc:                       # noqa: BLE001 — plan §5: any tool error stops
                self.stopped = f"tool error in repetition {rep}: {type(exc).__name__}: {exc}"
                raise RigError(self.stopped) from exc
            res = analyse(frames, received)
            res["repetition"] = rep
            self.results.append(res)
            if res["losses"] >= LOSSES_PER_REPETITION_STOP:
                self.stopped = (f"stop rule: {res['losses']} losses within repetition {rep} "
                                f"(>= {LOSSES_PER_REPETITION_STOP}) — the condition is reproducing the failure")
                break
        else:
            self.stopped = f"exposure: {self.repetitions} repetitions completed"
        after = read_icounters(fd) if fd is not None else {"available": False, "reason": "no fd supplied"}
        sent = sum(r["bytes_sent"] for r in self.results)
        losses = sum(r["losses"] for r in self.results)
        return {"label": self.label, "tool": "host/transport_rig.py", "self_sha256": self_sha256(),
                "tx_during_rx": self.tx_during_rx,
                "repetitions_run": len(self.results), "stopped": self.stopped,
                "bytes_sent": sent, "frames_sent": sum(r["frames_sent"] for r in self.results),
                "losses": losses,
                # the decision rule of §5: losses per received byte, with the denominator stated
                "losses_per_100k_bytes": (None if sent == 0 else losses * 100000 / sent),
                "denominator_bytes": sent,
                "counters_before": before, "counters_after": after,
                "counters_delta": counter_delta(before, after),
                "repetition_results": self.results,
                "scope": "a rig run under one condition; it attributes nothing, qualifies nothing, "
                         "and does not authorise a board session (plan §5, §6)"}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--profile-from", type=Path, default=REPO_ROOT / PROFILE_SOURCE,
                    help="derive and print the transmitted shape of a recorded session")
    ap.add_argument("--plan", action="store_true", help="print the generated stream's shape")
    a = ap.parse_args(argv)
    if a.plan:
        frames = plan_frames(1)
        by: dict = {}
        for f in frames:
            e = by.setdefault(f.kind, {"count": 0, "min": f.bytes, "max": f.bytes})
            e["count"] += 1
            e["min"], e["max"] = min(e["min"], f.bytes), max(e["max"], f.bytes)
        print(json.dumps({"frames": len(frames), "bytes": len(stream_bytes(frames)), "by_type": by}, indent=1, sort_keys=True))
        return 0
    print(json.dumps(profile_from_log(a.profile_from), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

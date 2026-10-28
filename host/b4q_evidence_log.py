#!/usr/bin/env python3
"""B4Q — the EVIDENCE LOG adapter (docs/b4q_source_audit.md §3.3): the bytes the board application appended to its DDR log
(firmware/b4q/target/b4q_ring.c) and the host pulled through the console, parsed into the logical inputs the accepted record
builders take — the carrier-window events with the transaction marks (what host/b4carrier_records.observation consumes), the DevC
and buffer accesses (A7), the staged streams (the WR_BUF writes of each staging), the readback frames (the DST_BUF reads after each
frame DMA) and the DMA tuples (the four DEVCFG writes). Everything here is the PROGRAM's record of what it did and what it read:
the data of a read is what the A9 received, a write's response is that it completed without an abort, a digest computed here is
"the hash of the frames the PS read back", never a frame store's. The parser refuses bytes outside the record grammar; nothing is
reconstructed from an expected genome, a model or an emulator."""
from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "host", R / "b4/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4carrier_regmap as rm  # noqa: E402
import b4q_a7 as a7  # noqa: E402
import b4q_backend as bk  # noqa: E402
import b4q_frames as fr  # noqa: E402

SOURCE_KIND = "ps-evidence-log-v1"            # the versioned source this adapter derives: the records' inputs from the PS's own log

RECORD = 16
KIND_WIN, KIND_DEVC, KIND_BUF, KIND_MARK, KIND_END = 1, 2, 3, 4, 5
OP_RD, OP_WR = 0, 1
RESP_BIT = 0x8000
RUN_BIT = 0x4000
COUNT_MASK = 0x3FFF
MARKS = {1: "open", 2: "transaction_begin", 3: "P6_sealed", 4: "transaction_end", 5: "transaction_interrupted"}
DEVC_REGS = (bk.DEVCFG_CTRL, bk.DEVCFG_INT_STS, bk.DEVCFG_DMA_SRC_ADDR, bk.DEVCFG_DMA_DEST_ADDR, bk.DEVCFG_DMA_SRC_LEN, bk.DEVCFG_DMA_DEST_LEN)
STREAM_BYTES = 4 * fr.STREAM_WORDS
PAGE_ADDR, PAGE_WORDS = 0x10440000, 24


class LogRefusal(ValueError):
    pass


def parse(data: bytes) -> list[dict]:
    """The records, in order: {off, tick, kind, op, count, refused, addr, data}. A truncated tail or an unknown kind refuses."""
    if len(data) % RECORD:
        raise LogRefusal(f"the log holds {len(data)} bytes: not a whole number of {RECORD}-byte records")
    out = []
    for off in range(0, len(data), RECORD):
        tick, kind, op, count, addr, d = struct.unpack(">IBBHII", data[off:off + RECORD])
        if kind not in (KIND_WIN, KIND_DEVC, KIND_BUF, KIND_MARK, KIND_END):
            raise LogRefusal(f"record at {off}: unknown kind {kind}")
        if op not in (OP_RD, OP_WR):
            raise LogRefusal(f"record at {off}: unknown op {op}")
        n = count & COUNT_MASK
        if n == 0 and kind != KIND_END:
            raise LogRefusal(f"record at {off}: a zero count")
        if kind == KIND_MARK and addr not in MARKS:
            raise LogRefusal(f"record at {off}: unknown mark {addr}")
        if (count & RUN_BIT) and kind != KIND_BUF:
            raise LogRefusal(f"record at {off}: a run record outside the buffers")
        out.append({"off": off, "tick": tick, "kind": kind, "op": "rd" if op == OP_RD else "wr", "count": n, "run": bool(count & RUN_BIT), "refused": bool(count & RESP_BIT), "addr": addr, "data": d})
    return out


def digest(data: bytes, used: int | None = None) -> str:
    return hashlib.sha256(data if used is None else data[:used]).hexdigest()


def window_events(records: list[dict]) -> list[dict]:
    """The carrier-window trace the record builders consume: {op, addr (offset), data, resp, log} plus the marks {mark, log}; a
    compressed poll is expanded (the builders read order and data; the count is kept beside)."""
    out = []
    for r in records:
        if r["kind"] == KIND_MARK:
            out.append({"mark": MARKS[r["addr"]], "log": r["off"], "t": r["tick"]})
        elif r["kind"] == KIND_WIN:
            e = {"op": r["op"], "addr": r["addr"], "data": r["data"], "resp": 2 if r["refused"] else 0, "log": r["off"], "t": r["tick"]}
            out.append(e)
            for _ in range(r["count"] - 1):
                out.append(dict(e, repeated=True))               # a window poll expanded (never a run: runs are the buffers')
    return out


def expand(records: list[dict]):
    """Every single access of the log, the polls and the runs expanded: (record, absolute address, data)."""
    for r in records:
        if r["kind"] in (KIND_MARK, KIND_END):
            continue
        base = bk.AXI_BASE + r["addr"] if r["kind"] == KIND_WIN else r["addr"]
        for k in range(r["count"]):
            yield r, base + (4 * k if r["run"] else 0), r["data"]


def accesses(records: list[dict]) -> list[tuple]:
    """Every access as A7 takes it: (op, absolute address, resp), the polls and runs expanded."""
    return [(r["op"], a, 2 if r["refused"] else 0) for r, a, _ in expand(records)]


def dma_submissions(records: list[dict]) -> list[dict]:
    """The DMA tuples as the PS wrote them: each DEST_LEN write queues the tuple of the four registers last written (the board's
    own register order; the fake's `submit` entries are what A7's classify_tuple takes)."""
    regs = {}
    out = []
    n = 0
    for r in records:
        if r["kind"] == KIND_DEVC and r["op"] == "wr" and not r["refused"]:
            regs[r["addr"]] = r["data"]
            if r["addr"] == bk.DEVCFG_DMA_DEST_LEN and all(a in regs for a in (bk.DEVCFG_DMA_SRC_ADDR, bk.DEVCFG_DMA_DEST_ADDR, bk.DEVCFG_DMA_SRC_LEN)):
                out.append({"pcap": "submit", "n": n, "src": regs[bk.DEVCFG_DMA_SRC_ADDR], "dst": regs[bk.DEVCFG_DMA_DEST_ADDR], "src_len": regs[bk.DEVCFG_DMA_SRC_LEN],
                            "dst_len": regs[bk.DEVCFG_DMA_DEST_LEN], "log": r["off"]})
                n += 1
    return out


def stagings(records: list[dict]) -> list[dict]:
    """The streams the PS staged: every complete sequence of WR_BUF writes covering one envelope's 534 words (in address order) is a
    staged stream — {envelope, words, log_first, log_last}; the words are the program's own writes."""
    out = []
    cur = {}
    for r, addr, data in expand(records):
        if r["kind"] == KIND_BUF and r["op"] == "wr" and not r["refused"] and bk.WR_BUF <= addr < bk.WR_BUF + len(fr.ENVELOPES) * STREAM_BYTES:
            e = (addr - bk.WR_BUF) // STREAM_BYTES
            i = ((addr - bk.WR_BUF) % STREAM_BYTES) // 4
            if i == 0:
                cur[e] = {"envelope": e, "words": [], "log_first": r["off"]}
            if e in cur and len(cur[e]["words"]) == i:
                cur[e]["words"].append(data)
                if i == fr.STREAM_WORDS - 1:
                    cur[e]["log_last"] = r["off"]
                    out.append(cur.pop(e))
            else:
                cur.pop(e, None)
    return out


def readbacks(records: list[dict]) -> list[dict]:
    """Each readback the PS performed: the readback command it wrote into CMD_BUF (its FAR, parsed by equality with the pinned
    command builder), then the 202 DST_BUF words it READ after the frame DMA — the target frame is words [101:202]. The frames the
    PS read back are the only host-checkable copy of what the device returned."""
    out = []
    cmd_words, far = {}, None
    dst, prev_i, reading = {}, None, False
    frame_dma_seen = False
    for r, addr, data in expand(records):
        if r["kind"] == KIND_DEVC and r["op"] == "wr" and addr == bk.DEVCFG_DMA_DEST_LEN and data == fr.READBACK_WORDS:
            frame_dma_seen = True                               # the frame DMA was queued: the next DST_BUF reads are the program reading what the device delivered
            prev_i = None
        elif r["kind"] == KIND_BUF and r["op"] == "wr" and not r["refused"] and bk.CMD_BUF <= addr < bk.CMD_BUF + 4 * fr.READBACK_CMD_WORDS:
            i = (addr - bk.CMD_BUF) // 4
            if i == 0:
                cmd_words = {}
            cmd_words[i] = data
            if len(cmd_words) == fr.READBACK_CMD_WORDS and all(k in cmd_words for k in range(fr.READBACK_CMD_WORDS)):
                words = [cmd_words[k] for k in range(fr.READBACK_CMD_WORDS)]
                far = next((f for f in fr.TARGET_FARS + fr.FLUSH_FARS if words == fr.build_readback_command(f)), None)
        elif r["kind"] == KIND_BUF and r["op"] == "rd" and not r["refused"] and bk.DST_BUF <= addr < bk.DST_BUF + 4 * fr.READBACK_WORDS:
            i = (addr - bk.DST_BUF) // 4
            if frame_dma_seen and i == fr.FRAME_WORDS and prev_i != fr.FRAME_WORDS - 1:
                dst = {}; reading = True                        # the target frame [101:202], read directly after the frame DMA (not the sentinel sweep from word 0)
            if reading:
                dst[i] = data
                if i == fr.READBACK_WORDS - 1 and all(k in dst for k in range(fr.FRAME_WORDS, fr.READBACK_WORDS)):
                    out.append({"far": far, "frame": [dst[k] for k in range(fr.FRAME_WORDS, fr.READBACK_WORDS)], "log": r["off"]})
                    reading = False; far = None; frame_dma_seen = False
            prev_i = i
        elif r["kind"] == KIND_BUF and r["op"] == "wr" and bk.DST_BUF <= addr < bk.DST_BUF + 4 * fr.READBACK_WORDS:
            reading = False; prev_i = None; frame_dma_seen = False   # the sentinel prefill of the next readback
    return out


def readback_groups(rbs: list[dict]) -> list[dict]:
    """Consecutive readbacks of the eight target FARs (in the pinned order) form a link-3 group: its FAR-ordered digest of the frames
    the PS read back, with the log range."""
    out = []
    k = 0
    while k + len(fr.TARGET_FARS) <= len(rbs):
        g = rbs[k:k + len(fr.TARGET_FARS)]
        if [x["far"] for x in g] == list(fr.TARGET_FARS):
            frames = {x["far"]: x["frame"] for x in g}
            out.append({"frames_sha256": fr.frames_hash(frames), "log_first": g[0]["log"], "log_last": g[-1]["log"], "frames": frames})
            k += len(fr.TARGET_FARS)
        else:
            k += 1
    return out


def staging_witness(streams: list[dict]) -> str | None:
    """The staging commitment from two staged streams (the executing side's link-2 arithmetic on its own staged words)."""
    frames = {}
    for s in streams:
        parsed = fr.parse_stream(s["words"])
        if parsed is None:
            return None
        far_set, frames5 = parsed
        env = [v for v in fr.ENVELOPES if v["far_set"] == far_set][0]
        for j, far in enumerate(env["targets"]):
            frames[far] = frames5[j]
    return fr.frames_hash(frames) if set(frames) == set(fr.TARGET_FARS) else None


def split_transactions(records: list[dict]) -> list[dict]:
    """The log's transactions: {begin_off, end_off (the end mark's offset, or None when interrupted / cut), records}."""
    out, cur = [], None
    for r in records:
        if r["kind"] == KIND_MARK and MARKS[r["addr"]] == "transaction_begin":
            cur = {"begin_off": r["off"], "end_off": None, "records": []}
        elif r["kind"] == KIND_MARK and MARKS[r["addr"]] == "transaction_end" and cur is not None:
            cur["end_off"] = r["off"]; out.append(cur); cur = None
        elif cur is not None:
            cur["records"].append(r)
    if cur is not None:
        out.append(cur)
    return out


class Deriver:
    """The versioned derivation (`ps-evidence-log-v1`), INCREMENTAL: records are fed in log order, each entry is emitted at the record
    that completes it, so feeding the log in pieces yields exactly what feeding it whole yields (the trace / pcap / accesses of a
    prefix are a prefix; a link-3 group digest is amended on its eight read_frame entries when the eighth frame is read). The three
    logical inputs the accepted record / link / A7 paths consume, each entry carrying the `log` byte offset of its record —
      trace:    the carrier-window events and the marks (b4carrier_records.observation / transactions), the polls expanded;
      pcap:     the DMA activity as the PS witnessed it — `submit` at each DEST_LEN write (the tuple the PS wrote; `mode` is
                "unwitnessed": the PS does not see the device's handling), `stream_submitted` with the words the PS wrote into that
                envelope's source buffer (the latest complete staging, untouched since), `read_command` with the FAR the PS's command
                words name, `read_frame` with the frame the PS read out of the destination buffer after the frame DMA (`frame_sha256`;
                `target_frames_hash` = the FAR-ordered digest of the eight frames of a complete consecutive group — "the hash of the
                frames the PS read back", never a frame store's), `cleanup`, `other`;
      accesses: (op, absolute address, resp) for A7.
    Nothing is taken from outside the bytes: no device effect, no model, no expected genome."""

    def __init__(self):
        self.trace, self.pcap, self.accesses = [], [], []
        self.fed_bytes, self.fed_records = 0, 0
        self.dma = {bk.DEVCFG_DMA_SRC_ADDR: None, bk.DEVCFG_DMA_DEST_ADDR: None, bk.DEVCFG_DMA_SRC_LEN: None}
        self.n, self.counts = 0, {}
        self.cur_staging, self.stagings, self.touched = {}, {}, {}      # envelope -> partial staging / latest complete staging / offset of the latest write into it
        self.cmd_words, self.cmd_far = {}, None
        self.dst, self.prev_i, self.reading, self.frame_sub = {}, None, False, None
        self.open_frames = []                                             # read_frame entries not yet in a complete group, with their frames

    def feed_bytes(self, data: bytes):
        """Feed the log bytes beyond what was fed (the whole log may be passed each time)."""
        if len(data) < self.fed_bytes or data[:0] != b"":
            raise LogRefusal("the log shrank: a pulled log only grows")
        recs = parse(data[self.fed_bytes:])
        for r in recs:
            r["off"] += self.fed_bytes
        self.feed(recs)
        self.fed_bytes = len(data)

    def feed(self, records: list[dict]):
        for r in records:
            self.fed_records += 1
            if r["kind"] == KIND_MARK:
                self.trace.append({"mark": MARKS[r["addr"]], "log": r["off"], "t": r["tick"]})
                continue
            if r["kind"] == KIND_END:
                continue
            for k in range(r["count"]):
                addr = (bk.AXI_BASE + r["addr"] if r["kind"] == KIND_WIN else r["addr"]) + (4 * k if r["run"] else 0)
                self._access(r, addr, r["data"], 2 if r["refused"] else 0)

    def _access(self, r: dict, addr: int, data: int, resp: int):
        ok = resp == 0
        self.accesses.append({"op": r["op"], "addr": addr, "resp": resp})
        if r["kind"] == KIND_WIN:
            self.trace.append({"op": r["op"], "addr": r["addr"], "data": data, "resp": resp, "log": r["off"], "t": r["tick"]})
        elif r["kind"] == KIND_DEVC and r["op"] == "wr" and ok:
            if addr in self.dma:
                self.dma[addr] = data
            elif addr == bk.DEVCFG_DMA_DEST_LEN:
                self._submit(r, data)
        elif r["kind"] == KIND_BUF:
            self._buffer(r, addr, data, ok)

    def _submit(self, r: dict, dlen: int):
        src, dst, slen = self.dma[bk.DEVCFG_DMA_SRC_ADDR], self.dma[bk.DEVCFG_DMA_DEST_ADDR], self.dma[bk.DEVCFG_DMA_SRC_LEN]
        kind = a7.classify_tuple(src, dst, slen, dlen)[0] if None not in (src, dst, slen) else None
        kind = kind or "other"
        n = self.n
        self.counts[kind] = self.counts.get(kind, 0) + 1                  # n counts the submissions from 0 (the queue index, as the fake numbers them)
        self.pcap.append({"pcap": "submit", "n": n, "kind": kind, "ordinal": self.counts[kind], "src": src, "dst": dst, "src_len": slen, "dst_len": dlen, "mode": "unwitnessed", "log": r["off"]})
        if kind == "env":
            e = ((src & ~1) - bk.WR_BUF) // STREAM_BYTES
            s = self.stagings.get(e)
            if s is not None and self.touched.get(e) == s["log_last"]:
                self.pcap.append({"pcap": "stream_submitted", "n": n, "src": src, "stream_sha256": fr.words_sha256(s["words"]),
                                  "stream_words_hex": "".join(f"{w:08x}" for w in s["words"]), "log": r["off"], "staged_log": [s["log_first"], s["log_last"]]})
        elif kind == "cmd":
            self.pcap.append({"pcap": "read_command", "n": n, "far": (f"{self.cmd_far:#010x}" if self.cmd_far else None), "log": r["off"]})
        elif kind == "frame":
            self.frame_sub = {"n": n, "far": self.cmd_far}; self.prev_i = None
        elif kind == "clean":
            self.pcap.append({"pcap": "cleanup", "n": n, "log": r["off"]})
        else:
            self.pcap.append({"pcap": "other", "n": n, "log": r["off"]})
        self.n += 1

    def _buffer(self, r: dict, addr: int, data: int, ok: bool):
        if r["op"] == "wr" and bk.WR_BUF <= addr < bk.WR_BUF + len(fr.ENVELOPES) * STREAM_BYTES:
            e = (addr - bk.WR_BUF) // STREAM_BYTES
            self.touched[e] = r["off"]
            if not ok:
                self.cur_staging.pop(e, None); return
            i = ((addr - bk.WR_BUF) % STREAM_BYTES) // 4
            if i == 0:
                self.cur_staging[e] = {"words": [], "log_first": r["off"]}
            if e in self.cur_staging and len(self.cur_staging[e]["words"]) == i:
                self.cur_staging[e]["words"].append(data)
                if i == fr.STREAM_WORDS - 1:
                    self.stagings[e] = dict(self.cur_staging.pop(e), log_last=r["off"])
            else:
                self.cur_staging.pop(e, None)
        elif r["op"] == "wr" and ok and bk.CMD_BUF <= addr < bk.CMD_BUF + 4 * fr.READBACK_CMD_WORDS:
            i = (addr - bk.CMD_BUF) // 4
            if i == 0:
                self.cmd_words = {}
            self.cmd_words[i] = data
            if all(j in self.cmd_words for j in range(fr.READBACK_CMD_WORDS)):
                words = [self.cmd_words[j] for j in range(fr.READBACK_CMD_WORDS)]
                self.cmd_far = next((f for f in fr.TARGET_FARS + fr.FLUSH_FARS if words == fr.build_readback_command(f)), None)
        elif r["op"] == "rd" and ok and bk.DST_BUF <= addr < bk.DST_BUF + 4 * fr.READBACK_WORDS:
            i = (addr - bk.DST_BUF) // 4
            if self.frame_sub is not None and i == fr.FRAME_WORDS and self.prev_i != fr.FRAME_WORDS - 1:
                self.dst = {}; self.reading = True                        # the target frame [101:202] read after the frame DMA (not the sentinel sweep from word 0)
            if self.reading:
                self.dst[i] = data
                if i == fr.READBACK_WORDS - 1 and all(j in self.dst for j in range(fr.FRAME_WORDS, fr.READBACK_WORDS)):
                    frame = [self.dst[j] for j in range(fr.FRAME_WORDS, fr.READBACK_WORDS)]
                    far = self.frame_sub["far"]
                    entry = {"pcap": "read_frame", "n": self.frame_sub["n"], "far": (f"{far:#010x}" if far else None), "frame_sha256": fr.frame_sha256(frame), "target_frames_hash": None, "log": r["off"]}
                    self.pcap.append(entry)
                    self._group(entry, frame)
                    self.reading = False; self.frame_sub = None
            self.prev_i = i
        elif r["op"] == "wr" and bk.DST_BUF <= addr < bk.DST_BUF + 4 * fr.READBACK_WORDS:
            self.reading = False; self.prev_i = None; self.frame_sub = None   # the sentinel prefill of the next readback

    def _group(self, entry: dict, frame: list):
        """Link 3: a complete consecutive group of the eight target FARs (in the pinned order) hashes FAR-ordered; the digest goes on
        each of its entries. A frame out of order drops the pending prefix (the same chunking the fake's groups have: eight consecutive)."""
        self.open_frames.append((entry, frame))
        want = [f"{f:#010x}" for f in fr.TARGET_FARS]
        if [x[0]["far"] for x in self.open_frames] != want[:len(self.open_frames)]:
            self.open_frames = [] if entry["far"] != want[0] else [(entry, frame)]
        if len(self.open_frames) == len(want):
            h = fr.frames_hash({int(x[0]["far"], 16): x[1] for x in self.open_frames})
            for x in self.open_frames:
                x[0]["target_frames_hash"] = h
            self.open_frames = []


def derive(records: list[dict]) -> dict:
    """The whole-log derivation (the tools / tests): the same as feeding a Deriver once."""
    d = Deriver()
    d.feed(records)
    return {"source": SOURCE_KIND, "trace": d.trace, "pcap": d.pcap, "accesses": d.accesses}


def trace_index_at(trace: list[dict], log_off: int) -> int:
    """The trace position a log byte offset maps to: the number of trace events that come from records before `log_off`."""
    import bisect
    return bisect.bisect_left([e["log"] for e in trace], log_off)


def nonce_read(trace: list[dict], t_begin: int, t_end: int | None = None) -> str | None:
    """The PL nonce the PS read: the first NONCE_LO / NONCE_HI read pair at or after t_begin (before t_end); else the last pair before."""
    lo = hi = None
    for e in trace[t_begin:t_end]:
        if e.get("op") == "rd" and e.get("resp") == 0 and e.get("addr") == rm.NONCE_LO and lo is None:
            lo = e["data"]
        elif e.get("op") == "rd" and e.get("resp") == 0 and e.get("addr") == rm.NONCE_HI and hi is None:
            hi = e["data"]
        if lo is not None and hi is not None:
            return f"{(hi << 32) | lo:016x}"
    lo = hi = None
    for e in reversed(trace[:t_begin]):
        if e.get("op") == "rd" and e.get("resp") == 0 and e.get("addr") == rm.NONCE_LO and lo is None:
            lo = e["data"]
        elif e.get("op") == "rd" and e.get("resp") == 0 and e.get("addr") == rm.NONCE_HI and hi is None:
            hi = e["data"]
        if lo is not None and hi is not None:
            return f"{(hi << 32) | lo:016x}"
    return None


def summary(data: bytes) -> dict:
    recs = parse(data)
    return {"bytes": len(data), "records": len(recs), "sha256": digest(data), "marks": [MARKS[r["addr"]] for r in recs if r["kind"] == KIND_MARK],
            "window": sum(1 for r in recs if r["kind"] == KIND_WIN), "devc": sum(1 for r in recs if r["kind"] == KIND_DEVC), "buf": sum(1 for r in recs if r["kind"] == KIND_BUF),
            "compressed_polls": sum(r["count"] - 1 for r in recs if r["kind"] != KIND_MARK), "stagings": len(stagings(recs)), "readbacks": len(readbacks(recs)),
            "readback_groups": [g["frames_sha256"] for g in readback_groups(readbacks(recs))], "submissions": len(dma_submissions(recs))}


if __name__ == "__main__":
    import json
    print(json.dumps(summary(Path(sys.argv[1]).read_bytes()), indent=1))

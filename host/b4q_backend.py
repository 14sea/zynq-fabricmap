#!/usr/bin/env python3
"""B4Q — the HOST TRANSPORT / MMIO BACKEND the executing-side program (firmware/b4q) is driven against: one 32-bit address
space routed by region, exactly as the application's Xil_In32 / Xil_Out32 would reach the board's —

  * the carrier's AXI window (the B4 carrier v2 emulation, host/b4q_emu.CarrierEmu): every access logged as the RTL bench
    logs it, with the window offset, so host/b4carrier_records.py reads the emulation's trace as it reads the bench's;
  * the DevC configuration-port registers (CTRL, INT_STS, the four DMA tuple registers): a MINIMAL fake of the PCAP in the
    discipline of b3/tb/hostapp (the owner's 2026-10-12 scope): every DMA_DEST_LEN write is a SUBMISSION whose four
    registers are recorded; a WRITE_ENVELOPE's stream is parsed with the pinned grammar (host/b4q_frames.parse_stream) and
    its five frames stored by FAR; a READ_COMMAND names a target FAR (its words matched against the pinned readback
    command); a READ_FRAME writes the pad frame (zeros) and the target frame to its destination; the cleanup command is
    accepted. The slice's configuration follows the frame store: after every envelope write the emulated carrier is told the
    21-bit genome the target frames now hold. Fault modes (a submission that never completes, an error bit, DMA_DONE without
    D_P_DONE) exist for the negative paths and are a SIMULATION, never evidence that hardware stopped a DMA;
  * the DDR staging / command / destination buffers (plain memory);
  * the SLCR IDCODE word (read-only).

Everything the firmware reads back through the PCAP path is what this backend stored: SYMBOLIC / EMULATED — a frame
readback here proves the firmware's arithmetic and sequence, never a physical link (the owner's ruling: "symbolic / emulated
values are labelled as such and never represented as a physical link proof"). The backend keeps its own PCAP log (every
submission, every frame set, every readback with the digests the host computes) so the session can hold the firmware's
reported digests to it."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b4q_emu as emu  # noqa: E402
import b4q_frames as fr  # noqa: E402

# the PS address map the executing side uses (firmware/b1's constants, kept: the carrier window at GP0, the DevC, the buffers)
AXI_BASE = 0x43C00000
AXI_SIZE = 0x10000
DEVCFG_BASE = 0xF8007000
DEVCFG_CTRL, DEVCFG_INT_STS = DEVCFG_BASE + 0x000, DEVCFG_BASE + 0x00C
DEVCFG_DMA_SRC_ADDR, DEVCFG_DMA_DEST_ADDR, DEVCFG_DMA_SRC_LEN, DEVCFG_DMA_DEST_LEN = DEVCFG_BASE + 0x018, DEVCFG_BASE + 0x01C, DEVCFG_BASE + 0x020, DEVCFG_BASE + 0x024
SLCR_PSS_IDCODE = 0xF8000530
IDCODE_FULL = 0x13722093
PCAP_ENDPOINT = 0xFFFFFFFF
DMA_HOLD_TAG = 0x1
INT_STS_D_P_DONE, INT_STS_DMA_DONE = 1 << 12, 1 << 13
INT_STS_ERROR_MASK = 0x00F4C840
CTRL_PCAP_MASK = 0x0C000000
CMD_BUF, DST_BUF, WR_BUF = 0x10200000, 0x10300000, 0x10400000
STREAM_BYTES = 4 * fr.STREAM_WORDS
OKAY, SLVERR = 0, 2


class Memory:
    def __init__(self):
        self.words = {}

    def rd(self, a: int) -> int:
        return self.words.get(a & ~3, 0)

    def wr(self, a: int, v: int):
        self.words[a & ~3] = v & 0xFFFFFFFF


class Devc:
    """The DevC DMA and the PCAP frame store (symbolic)."""
    KINDS = ("env", "cmd", "frame", "clean", "other")

    def __init__(self, mem: Memory, base_frames: dict, on_config, pcap_log: list):
        self.mem = mem
        self.frames = {far: list(w) for far, w in base_frames.items()}     # the loaded image, by FAR (the write set and the flush frames)
        self.on_config = on_config
        self.log = pcap_log
        self.src = self.dst = self.slen = 0
        self.sts = 0
        self.queue = []                                                    # every submission
        self.cur = None
        self.read_target = None
        self.faults = {}                                                   # (kind, ordinal) -> mode: "never" | ("error", bit) | "dmadone"
        self.corrupt_frame_reads = set()                                   # frame-read ordinals whose delivered frame is corrupted (a fault knob)
        self.counts = {k: 0 for k in self.KINDS}
        self.sticky = False

    def classify(self, src, dst, slen, dlen) -> str:
        if dst == PCAP_ENDPOINT and WR_BUF <= (src & ~3) < WR_BUF + len(fr.ENVELOPES) * STREAM_BYTES and slen == fr.STREAM_WORDS:
            return "env"
        if dst == PCAP_ENDPOINT and (src & ~3) == CMD_BUF and slen == fr.READBACK_CMD_WORDS:
            return "cmd"
        if dst == PCAP_ENDPOINT and (src & ~3) == CMD_BUF and slen == fr.CLEANUP_WORDS:
            return "clean"
        if src == PCAP_ENDPOINT and (dst & ~3) == DST_BUF and dlen == fr.READBACK_WORDS:
            return "frame"
        return "other"

    def submit(self, dlen: int):
        kind = self.classify(self.src, self.dst, self.slen, dlen)
        self.counts[kind] += 1
        d = {"n": len(self.queue), "kind": kind, "ordinal": self.counts[kind], "src": self.src, "dst": self.dst, "src_len": self.slen, "dst_len": dlen,
             "mode": "ok", "polls": 0, "done": False, "data_done": False, "target": None, "effect": None}
        if self.sticky:
            d["mode"] = "never"
        else:
            d["mode"] = self.faults.get((kind, d["ordinal"]), "ok")
        self.queue.append(d); self.cur = d
        self.log.append({"pcap": "submit", **{k: d[k] for k in ("n", "kind", "ordinal", "src", "dst", "src_len", "dst_len", "mode")}})

    def data(self, d: dict):
        if d["data_done"]:
            return
        d["data_done"] = True
        if d["kind"] == "env":
            words = [self.mem.rd((d["src"] & ~3) + 4 * i) for i in range(fr.STREAM_WORDS)]
            # the staging witness: the stream as this fake reads it from the emulated DDR HERE — in its data handling, reached from the
            # executing side's first status poll after the queueing write, immediately BEFORE the emulated frame-store update — not at
            # the queueing write itself (the owner's P3 of 2026-10-27). Between the queueing write and this poll the executing side issues
            # no write, so the bytes are the ones it staged and re-read (link 2); this is an emulation witness of "before the frame update",
            # not a physical DDR re-read. A DMA that never reaches data handling (a 'never' fault, an interruption) leaves only its
            # `submit` entry and no stream_submitted entry: the host then has no staging witness for it and writes none.
            self.log.append({"pcap": "stream_submitted", "n": d["n"], "src": d["src"], "stream_sha256": fr.words_sha256(words),
                             "stream_words_hex": "".join(f"{w:08x}" for w in words)})
            parsed = fr.parse_stream(words)
            if parsed is None:
                d["effect"] = "stream refused by the grammar: nothing configured"
                self.log.append({"pcap": "envelope_refused", "n": d["n"], "stream_sha256": fr.words_sha256(words)})
                return
            far_set, frames5 = parsed
            e = [e for e in fr.ENVELOPES if e["far_set"] == far_set][0]
            for k, far in enumerate(e["targets"]):
                self.frames[far] = list(frames5[k])
            self.frames[e["flush"]] = list(frames5[4])                      # the device auto-increments into the flush frame
            d["effect"] = f"envelope {far_set:#010x} written"
            genome = fr.genome_from_frames(self.frames, self.wl)
            self.log.append({"pcap": "envelope_written", "n": d["n"], "far_set": f"{far_set:#010x}", "stream_sha256": fr.words_sha256(words),
                             "frames_sha256": {f"{far:#010x}": fr.frame_sha256(self.frames[far]) for far in e["targets"] + (e["flush"],)},
                             "target_frames_hash": fr.frames_hash(self.frames), "genome": genome})
            self.on_config(genome)
        elif d["kind"] == "cmd":
            cmd = [self.mem.rd((d["src"] & ~3) + 4 * i) for i in range(fr.READBACK_CMD_WORDS)]
            self.read_target = None
            for far in fr.TARGET_FARS + fr.FLUSH_FARS:
                if cmd == fr.build_readback_command(far):
                    self.read_target = far
            d["target"] = self.read_target
            d["effect"] = f"readback command for {self.read_target:#010x}" if self.read_target else "readback command names no frame of the write set"
            self.log.append({"pcap": "read_command", "n": d["n"], "far": (f"{self.read_target:#010x}" if self.read_target else None)})
        elif d["kind"] == "frame":
            far = self.read_target
            d["target"] = far
            words = [0] * fr.FRAME_WORDS + (list(self.frames[far]) if far in self.frames else [0] * fr.FRAME_WORDS)
            if d["ordinal"] in self.corrupt_frame_reads:                  # a fault knob (the repair's probes): one word of the delivered frame flipped
                words[fr.FRAME_WORDS + 3] ^= 1
                self.log.append({"pcap": "frame_corrupted_by_the_bench", "n": d["n"], "ordinal": d["ordinal"]})
            for i, w in enumerate(words):
                self.mem.wr((d["dst"] & ~3) + 4 * i, w)
            d["effect"] = "pad frame + target frame delivered"
            self.log.append({"pcap": "read_frame", "n": d["n"], "far": (f"{far:#010x}" if far else None), "frame_sha256": (fr.frame_sha256(self.frames[far]) if far in self.frames else None),
                             "target_frames_hash": fr.frames_hash(self.frames)})      # what a FAR-ordered readback of the write set hashes to now
        elif d["kind"] == "clean":
            d["effect"] = "desync"
            self.log.append({"pcap": "cleanup", "n": d["n"]})
        else:
            d["effect"] = "not a legal transaction"
            self.log.append({"pcap": "other", "n": d["n"]})

    def status(self) -> int:
        d = self.cur
        if d is None:
            return self.sts
        d["polls"] += 1
        m = d["mode"]
        if m == "never":
            pass
        elif isinstance(m, tuple) and m[0] == "error":
            self.sts |= 1 << m[1]
        elif m == "dmadone":
            self.sts |= INT_STS_DMA_DONE
        else:
            if not d["done"]:
                d["done"] = True; self.data(d)
            self.sts |= INT_STS_D_P_DONE | INT_STS_DMA_DONE
        return self.sts

    def rd(self, a: int) -> int:
        if a == DEVCFG_CTRL:
            return CTRL_PCAP_MASK
        if a == DEVCFG_INT_STS:
            return self.status()
        return 0

    def wr(self, a: int, v: int):
        if a == DEVCFG_INT_STS:
            self.sts &= ~v & 0xFFFFFFFF; self.cur = None
        elif a == DEVCFG_DMA_SRC_ADDR:
            self.src = v
        elif a == DEVCFG_DMA_DEST_ADDR:
            self.dst = v
        elif a == DEVCFG_DMA_SRC_LEN:
            self.slen = v
        elif a == DEVCFG_DMA_DEST_LEN:
            self.submit(v)


class Backend:
    """The one address space. `trace` is the carrier's register trace (the bench's format); `accesses` every access the
    firmware made (absolute address, for the A7 check); `pcap_log` the DevC's log."""

    def __init__(self, base: dict | None = None, wl=None, power_on: str = "init", gsr_init_effect: bool = True, nonce_seed: int = emu.NONCE_SEED):
        self.base = base or fr.load_base()
        self.wl = wl or fr.whitelist()
        self.trace, self.accesses, self.pcap_log = [], [], []
        loaded_genome = fr.genome_from_frames({f: self.base["frames"][f] for f in fr.TARGET_FARS}, self.wl)
        self.carrier = emu.CarrierEmu(genome=loaded_genome, power_on=power_on, gsr_init_effect=gsr_init_effect, nonce_seed=nonce_seed, log=self.trace)
        self.mem = Memory()
        self.devc = Devc(self.mem, self.base["frames"], self.carrier.set_genome, self.pcap_log)
        self.devc.wl = self.wl
        self.loaded_genome = loaded_genome
        self.refuse_writes = set()                                         # window offsets answered SLVERR without a change (a fault knob)
        self.refuse_reads = {}                                             # window offset -> how many of its next reads answer SLVERR (a fault knob; the data word unchanged)
        self.refuse_mem_reads = {}                                         # PS-map address (DEVCFG / DDR / SLCR) -> how many of its next reads answer SLVERR

    def provision_key(self, key: bytes):
        """The signer principal's act (never the application's): the write-once key through its window, then the commit."""
        import b4carrier_regmap as rm
        k = int.from_bytes(key, "little")
        words = [(k >> ((3 - j) * 32)) & 0xFFFFFFFF for j in range(4)]
        for j, w in enumerate(words):
            assert self.carrier.write(rm.KEY[j], w) == 0
        assert self.carrier.write(rm.CTRL, rm.ctrl_word("key_commit")) == 0
        self.carrier.t += 4

    def rd32(self, a: int):
        """(data, resp, x): an x pattern where the carrier has no value — the word carries 0 there; the trace keeps the x."""
        a &= 0xFFFFFFFF
        if AXI_BASE <= a < AXI_BASE + AXI_SIZE:
            data, x, resp = self.carrier.read(a - AXI_BASE)
            if x is not None:
                data = int("".join("0" if c in "xz" else c for c in x), 2)
            if self.refuse_reads.get(a - AXI_BASE, 0) > 0:                 # a fault knob: the response SLVERR, the word as the carrier gave it (a bench's injection, declared)
                self.refuse_reads[a - AXI_BASE] -= 1
                resp = SLVERR
                if self.trace and self.trace[-1].get("op") == "rd" and self.trace[-1].get("addr") == a - AXI_BASE:
                    self.trace[-1]["resp"] = SLVERR
            self.accesses.append(("rd", a, resp))
            return data, resp, x
        if self.refuse_mem_reads.get(a, 0) > 0:                            # a fault knob on the PS map: SLVERR answered, the word as the fake gives it
            self.refuse_mem_reads[a] -= 1
            self.accesses.append(("rd", a, SLVERR))
            if DEVCFG_BASE <= a < DEVCFG_BASE + 0x100:
                return self.devc.rd(a), SLVERR, None
            return (IDCODE_FULL if a == SLCR_PSS_IDCODE else self.mem.rd(a)), SLVERR, None
        self.accesses.append(("rd", a, OKAY))
        if DEVCFG_BASE <= a < DEVCFG_BASE + 0x100:
            return self.devc.rd(a), OKAY, None
        if a == SLCR_PSS_IDCODE:
            return IDCODE_FULL, OKAY, None
        return self.mem.rd(a), OKAY, None

    def wr32(self, a: int, v: int) -> int:
        a &= 0xFFFFFFFF
        if AXI_BASE <= a < AXI_BASE + AXI_SIZE:
            if (a - AXI_BASE) in self.refuse_writes:                        # a fault knob: SLVERR answered and the register NOT changed
                self.carrier.t += 4
                self.carrier._log({"t": self.carrier.t * 20, "op": "wr", "addr": a - AXI_BASE, "data": v & 0xFFFFFFFF, "resp": SLVERR})
                self.accesses.append(("wr", a, SLVERR))
                return SLVERR
            resp = self.carrier.write(a - AXI_BASE, v)
            self.accesses.append(("wr", a, resp))
            return resp
        self.accesses.append(("wr", a, OKAY))
        if DEVCFG_BASE <= a < DEVCFG_BASE + 0x100:
            self.devc.wr(a, v); return OKAY
        if a == SLCR_PSS_IDCODE:
            return SLVERR
        self.mem.wr(a, v)
        return OKAY

    def mark(self, what: str):
        self.carrier.mark(what)

    def current_genome(self) -> int:
        return fr.genome_from_frames(self.devc.frames, self.wl)

    def frames_hash_now(self) -> str:
        return fr.frames_hash(self.devc.frames)

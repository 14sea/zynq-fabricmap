#!/usr/bin/env python3
"""The Python reference of the B1 on-board cartographer (`firmware/b1/b1_carto.c`) —
host-only, pure; the C twin (`firmware/b1/b1_twin.c`) is checked against it probe by
probe over simulated fabrics (tests/test_b1_twin.py), and the host's AUDIT reconstruction
of a session's map (`host/b1_adjudicate.py`) runs this reference over the readouts the
records carry.

The algorithm, exactly as the C unit documents it: phase A, B1_CODE_BITS code probes
(address i carries code i + 1); decode every lit position to the address whose code it
lit under; phase B, single-address confirmations in an RNG-drawn order (undecoded
addresses first); phase C, RNG-drawn pairs of confirmed addresses, half same-LUT, half
cross-LUT, the readout expected to be the union of the singles. The RNG is
l6_operators.Rng's (xorshift64, warm-up 4, rejection sampling, partial Fisher–Yates) —
re-implemented here in twenty lines so that this module needs no instrument binding; the
equality with the instrument's class is itself a test.

Rendering is canonical (the bytes the C unit hashes): the same JSON text, no spaces, keys
in the C unit's order, and `map_sha256` = sha256 over it.
"""
from __future__ import annotations

import hashlib
import json

N = 292
LUTS = 6
CODE_BITS = 9
PAIRS_MAX = 32
VERSION = "carto-v1"
GENOME_WORDS = 10
GOLDEN = 0x9E3779B97F4A7C15
MASK64 = (1 << 64) - 1
MASK32 = (1 << 32) - 1
PH_CODE, PH_CONFIRM, PH_PAIR, PH_DONE = 0, 1, 2, 3
PHASE_NAME = {PH_CODE: "code", PH_CONFIRM: "confirm", PH_PAIR: "pair", PH_DONE: "baseline"}
ST_UNKNOWN, ST_DECODED, ST_CONFIRMED, ST_NO_EFFECT, ST_CONTRADICTION = range(5)
STATE_NAME = {ST_UNKNOWN: "unknown", ST_DECODED: "decoded", ST_CONFIRMED: "confirmed",
              ST_NO_EFFECT: "no_effect", ST_CONTRADICTION: "contradiction"}


def xorshift(x: int) -> int:
    x ^= (x << 13) & MASK64
    x ^= x >> 7
    x ^= (x << 17) & MASK64
    return x & MASK64


class Rng:
    def __init__(self, seed32: int):
        x = (((seed32 & MASK32) << 32) | (seed32 & MASK32)) ^ GOLDEN
        self.x = x if x else GOLDEN
        for _ in range(4):
            self.x = xorshift(self.x)

    def next32(self) -> int:
        self.x = xorshift(self.x)
        return (self.x >> 32) & MASK32

    def uniform(self, n: int) -> int:
        limit = ((1 << 32) // n) * n
        while True:
            v = self.next32()
            if v < limit:
                return v % n

    def sample(self, population: list[int], k: int) -> list[int]:
        pool = list(population)
        out = []
        for i in range(k):
            j = i + self.uniform(len(pool) - i)
            pool[i], pool[j] = pool[j], pool[i]
            out.append(pool[i])
        return out


def genome_to_hex(genome: int) -> str:
    words = [(genome >> (32 * w)) & MASK32 for w in range(GENOME_WORDS)]
    return "".join(f"{w:08x}" for w in words)


def genome_from_hex(text: str) -> int:
    g = 0
    for w in range(GENOME_WORDS):
        g |= int(text[8 * w:8 * w + 8], 16) << (32 * w)
    return g


def popcount_tables(t: list[int]) -> int:
    return sum(bin(x).count("1") for x in t)


class Entry:
    __slots__ = ("lut", "init", "confidence", "state", "observed", "code_mask", "confirm_seq")

    def __init__(self):
        self.lut, self.init, self.confidence, self.state = -1, -1, 0, ST_UNKNOWN
        self.observed, self.code_mask, self.confirm_seq = 0, 0, 0

    def render(self, i: int) -> str:
        return (f'[{i},{self.lut},{self.init},{self.confidence},"{STATE_NAME[self.state]}",'
                f'{self.code_mask},{self.confirm_seq},{self.observed}]')


class Carto:
    def __init__(self, seed: int, budget: int):
        self.seed, self.budget = seed, budget
        self.rng = Rng(seed)
        self.phase = PH_CODE
        self.probes_issued = 0
        self.code_p = 0
        self.lit: list[list[int]] = [[0] * LUTS for _ in range(CODE_BITS)]
        self.set_count = [0] * CODE_BITS
        self.lit_count = [0] * CODE_BITS
        self.code_seq = [0] * CODE_BITS
        self.e = [Entry() for _ in range(N)]
        self.order: list[int] = []
        self.order_i = 0
        self.pending = -1
        self.pairs: list[dict] = []
        self.pairs_i = 0
        self.pending_pair = -1
        self.anomalies = 0
        self.changed: list[int] = []
        self.map_sha256 = ""
        self.content_sha256 = ""
        self.token, self.universe, self.image_lo32 = "0" * 32, "0" * 64, 0

    def bind(self, token: str, universe: str, image_lo32: int) -> None:
        self.token, self.universe, self.image_lo32 = token[:32], universe[:64], image_lo32 & MASK32

    # ---- phase A decode -------------------------------------------------------------
    def _decode(self) -> None:
        for lut in range(LUTS):
            for v in range(64):
                code, any_ = 0, False
                for p in range(CODE_BITS):
                    if (self.lit[p][lut] >> v) & 1:
                        code |= 1 << p
                        any_ = True
                if not any_:
                    continue
                if code < 1 or code > N:
                    self.anomalies += 1
                    continue
                i = code - 1
                e = self.e[i]
                if e.state == ST_DECODED:
                    e.state, e.confidence = ST_CONTRADICTION, 0
                    self.anomalies += 1
                    self._changed_add(i)
                    continue
                e.lut, e.init, e.confidence, e.state = lut, v, 1, ST_DECODED
                e.observed, e.code_mask = 1, code
                self._changed_add(i)
        for p in range(CODE_BITS):
            if self.lit_count[p] != self.set_count[p]:
                self.anomalies += 1

    def _draw_order(self) -> None:
        unknown = [i for i in range(N) if self.e[i].state == ST_UNKNOWN]
        decoded = [i for i in range(N) if self.e[i].state == ST_DECODED]
        self.order = (self.rng.sample(unknown, len(unknown)) if unknown else []) + \
                     (self.rng.sample(decoded, len(decoded)) if decoded else [])
        self.order_i = 0

    def _draw_pairs(self) -> None:
        conf = [i for i in range(N) if self.e[i].state == ST_CONFIRMED]
        self.pairs, self.pairs_i = [], 0
        if len(conf) < 2:
            return
        tries = 0
        while len(self.pairs) < PAIRS_MAX and tries < 4096:
            a = conf[self.rng.uniform(len(conf))]
            b = conf[self.rng.uniform(len(conf))]
            want_same = (len(self.pairs) & 1) == 0
            tries += 1
            if a == b:
                continue
            if (self.e[a].lut == self.e[b].lut) != want_same:
                continue
            self.pairs.append({"a": a, "b": b, "kind": 0 if want_same else 1, "result": 0, "seq": 0})

    def _changed_add(self, i: int) -> None:
        if i not in self.changed:
            self.changed.append(i)

    # ---- next / observe -------------------------------------------------------------
    def next(self) -> tuple[int, int] | None:
        """(genome, kind) or None when done / budget exhausted."""
        if self.probes_issued >= self.budget:
            return None
        while True:
            if self.phase == PH_CODE:
                p = self.code_p
                if p >= CODE_BITS:              # the decode happened in observe(); nothing pending
                    self.phase = PH_CONFIRM
                    continue
                genome = 0
                self.set_count[p] = 0
                for i in range(N):
                    if ((i + 1) >> p) & 1:
                        genome |= 1 << i
                        self.set_count[p] += 1
                self.probes_issued += 1
                return genome, PH_CODE
            if self.phase == PH_CONFIRM:
                if self.order_i >= len(self.order):
                    self._draw_pairs()
                    self.phase = PH_PAIR
                    continue
                self.pending = self.order[self.order_i]
                self.order_i += 1
                self.probes_issued += 1
                return 1 << self.pending, PH_CONFIRM
            if self.phase == PH_PAIR:
                if self.pairs_i >= len(self.pairs):
                    self.phase = PH_DONE
                    return None
                self.pending_pair = self.pairs_i
                self.pairs_i += 1
                pr = self.pairs[self.pending_pair]
                self.probes_issued += 1
                return (1 << pr["a"]) | (1 << pr["b"]), PH_PAIR
            return None

    def observe(self, seq: int, tables: list[int]) -> None:
        self.changed = []
        if self.phase == PH_CODE:
            p = self.code_p
            self.lit[p] = list(tables)
            self.lit_count[p] = popcount_tables(tables)
            self.code_seq[p] = seq
            self.code_p += 1
            if self.code_p >= CODE_BITS:
                # the last code probe: decode now so this record's `changed` carries the decode
                self._decode()
                self._draw_order()
                self.phase = PH_CONFIRM
            return
        if self.phase == PH_CONFIRM and self.pending >= 0:
            e = self.e[self.pending]
            n = popcount_tables(tables)
            e.confirm_seq = seq
            if e.state == ST_UNKNOWN:
                if n == 0:
                    e.state, e.confidence = ST_NO_EFFECT, 2
                elif n == 1:
                    for k in range(LUTS):
                        for v in range(64):
                            if (tables[k] >> v) & 1:
                                e.lut, e.init = k, v
                    e.state, e.confidence, e.observed = ST_CONFIRMED, 1, 1
                    self.anomalies += 1
                else:
                    e.state, e.confidence = ST_CONTRADICTION, 0
                    self.anomalies += 1
            elif e.state == ST_DECODED:
                if n == 1 and (tables[e.lut] >> e.init) & 1:
                    e.state, e.confidence = ST_CONFIRMED, 2
                else:
                    e.state, e.confidence = ST_CONTRADICTION, 0
                    self.anomalies += 1
            self._changed_add(self.pending)
            self.pending = -1
            return
        if self.phase == PH_PAIR and self.pending_pair >= 0:
            pr = self.pairs[self.pending_pair]
            want = [0] * LUTS
            want[self.e[pr["a"]].lut] |= 1 << self.e[pr["a"]].init
            want[self.e[pr["b"]].lut] |= 1 << self.e[pr["b"]].init
            same = all(want[k] == tables[k] for k in range(LUTS))
            pr["result"] = 1 if same else 2
            pr["seq"] = seq
            if not same:
                self.anomalies += 1
            self._changed_add(pr["a"])
            self._changed_add(pr["b"])
            self.pending_pair = -1

    def unobserved(self) -> None:
        self.changed = []
        if self.phase == PH_CONFIRM and self.pending >= 0:
            self.order_i -= 1
            self.pending = -1
        elif self.phase == PH_PAIR and self.pending_pair >= 0:
            self.pairs_i -= 1
            self.pending_pair = -1

    # ---- rendering -------------------------------------------------------------------
    def render_content(self) -> str:
        entries = ",".join(self.e[i].render(i) for i in range(N))
        pairs = ",".join(f'[{p["a"]},{p["b"]},{p["kind"]},{p["result"]},{p["seq"]}]' for p in self.pairs)
        codes = ",".join(str(x) for x in self.code_seq)
        text = (f'{{"anomalies":{self.anomalies},"budget":{self.budget},"code_seqs":[{codes}],"entries":[{entries}],'
                f'"pairs":[{pairs}],"seed":{self.seed},"version":"{VERSION}"}}')
        self.content_sha256 = hashlib.sha256(text.encode()).hexdigest()
        return text

    def render(self) -> str:
        content = self.render_content()
        text = (f'{{"binding":{{"image_lo32":"{self.image_lo32:08x}","token":"{self.token}","universe":"{self.universe}"}},'
                f'"content":{content}}}')
        self.map_sha256 = hashlib.sha256(text.encode()).hexdigest()
        return text

    def record_json(self, kind: int, seq: int, changed: list[int]) -> str:
        self.render()
        ch = ",".join(self.e[i].render(i) for i in changed)
        return (f'{{"anomalies":{self.anomalies},"changed":[{ch}],"content_sha256":"{self.content_sha256}",'
                f'"map_sha256":"{self.map_sha256}","phase":"{PHASE_NAME[kind]}","probes_issued":{self.probes_issued},"version":"{VERSION}"}}')

    def map_dict(self) -> dict:
        """The whole map as a dict: {"binding": …, "content": …}."""
        return json.loads(self.render())

    def content_dict(self) -> dict:
        return json.loads(self.render_content())


DEFAULT_BINDING = ("0" * 32, "0" * 64, 0)


def run(seed: int, budget: int, fabric, unscored=None, first_seq: int = 2, binding=DEFAULT_BINDING) -> dict:
    """Drive the pure cartographer over `fabric(genome) -> six tables` (unscored: a callable
    (seq) -> bool marking probes the board did not score). Returns the transcript. The
    board's session (opening and closing baselines included) is `session_run`."""
    c = Carto(seed, budget)
    c.bind(*binding)
    seq = first_seq - 1
    probes, records = [], []
    while True:
        nxt = c.next()
        if nxt is None:
            break
        genome, kind = nxt
        seq += 1
        probes.append({"kind": kind, "seq": seq, "genome": genome_to_hex(genome)})
        if unscored and unscored(seq):
            c.unobserved()
            seq -= 1
            continue
        tables = fabric(genome)
        c.observe(seq, tables)
        records.append({"seq": seq, "carto": c.record_json(kind, seq, c.changed[:8]),
                        "changed_full": [c.e[i].render(i) for i in c.changed]})
    text = c.render()
    return {"probes": probes, "records": records, "map": text, "map_sha256": c.map_sha256,
            "content_sha256": c.content_sha256, "carto": c}


def session_run(seed: int, budget: int, fabric, token: str, universe: str, image_lo32: int, unscored=None) -> dict:
    """The board's whole sequence, as b1_orch drives it: seq 1 the opening baseline (blank
    genome, the cartographer already initialised and bound — its block commits to that
    state), then the probes, then the closing baseline (blank). Every candidate yields a
    record {seq, genome, is_baseline, kind, tables, carto}; a baseline learns nothing."""
    c = Carto(seed, budget)
    c.bind(token, universe, image_lo32)
    records = []
    seq = 0

    def emit(genome: int, is_baseline: bool, kind: int, tables: list[int]) -> None:
        records.append({"seq": seq, "genome": genome_to_hex(genome), "is_baseline": is_baseline, "kind": kind,
                        "tables": list(tables), "carto": c.record_json(PH_DONE if is_baseline else kind, seq, [] if is_baseline else c.changed[:8]),
                        "changed_full": [] if is_baseline else [c.e[i].render(i) for i in c.changed]})
    seq += 1
    emit(0, True, PH_DONE, fabric(0))
    stopped = False
    while True:
        nxt = c.next()
        if nxt is None:
            break
        genome, kind = nxt
        seq += 1
        if unscored and unscored(seq):
            # as the board: a candidate that was not SCORED ends the epoch — no re-issue and
            # no closing baseline; the map is what was learned before it
            c.unobserved()
            seq -= 1
            stopped = True
            break
        tables = fabric(genome)
        c.observe(seq, tables)
        emit(genome, False, kind, tables)
    if not stopped:
        seq += 1
        emit(0, True, PH_DONE, fabric(0))
    text = c.render()
    return {"records": records, "probes": [r for r in records if not r["is_baseline"]], "map": text,
            "map_sha256": c.map_sha256, "content_sha256": c.content_sha256, "carto": c, "last_seq": seq,
            "stopped": stopped}

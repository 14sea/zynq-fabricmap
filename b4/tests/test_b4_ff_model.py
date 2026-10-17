"""b4/host/b4_ff_model.py — the simulated FF fabric under a certificate mapping and a behaviour hypothesis kept
apart. Held here, every expected trace DERIVED BY HAND from the hypothesis file's adopted UNISIM lines and the
plan's bit readings (never by running the model):

  * the initialisation event and a user SR operation are two restore mechanisms with two readouts — INIT shows
    at the init readout, SRVAL at the SR readout, and the two differ on a configuration built to separate them;
  * CE gating (driven vs tied high), the capturing edge (slice clock vs inverted), synchronous SR acting only at
    the edge vs asynchronous SR acting on the level, latch transparency while the gate is high and hold when low,
    and the x5FF elements not applicable under a latch;
  * isolation: an observation starts from nothing (Q None), the init step gives it its value, and what one
    candidate left behind never reaches the next;
  * the permuted fixture is the truth with its effects dealt to other addresses — the trace of a configuration
    on it equals the truth's trace of the correspondingly re-addressed configuration — and is not the truth;
  * every hypothesis swap changes the trace of a configuration built to expose it; the model reads its hypothesis;
  * every readout carries the complete context of the hypothesis's observation_context, and a trace is
    deterministic and JSON-serialisable.
No skip."""
from __future__ import annotations

import json
import random
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402

E = bm.ELEMENTS                     # index: AFF 0, A5FF 1, BFF 2, B5FF 3, CFF 4, C5FF 5, DFF 6, D5FF 7 — bit i of ce / sr / d is element i
IDX = {e: i for i, e in enumerate(E)}
ALL = 0xFF


def base_config(m: bm.Mapping) -> dict[str, int]:
    """The certificate's base specimen as bits: INIT = 1 everywhere (ZINI 0), SRVAL = 0 (ZRST 1), CE driven,
    SR driven, synchronous, flip-flops, clock not inverted."""
    c = {a: 0 for a in m.addresses}
    for a, e in m.entries.items():
        if e.semantic in ("ff_srval", "ce_mode", "sr_mode", "sr_kind"):
            c[a] = 1
    return c


def q_after(trace: dict) -> list[list]:
    return [s["q_after"] for s in trace["steps"]]


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = bm.site_mapping()
        cls.h = hy.load()
        cls.fab = fm.Fabric(cls.m, cls.h)

    def cfg(self, **over) -> dict[str, int]:
        c = base_config(self.m)
        for key, v in over.items():
            element, semantic = (key.split("__") + [None])[:2] if "__" in key else (None, key)
            c[self.m.address_of(element, semantic)] = v
        return c


class InitAndSrAreTwoMechanisms(Base):
    def test_the_init_readout_shows_init_and_the_sr_readout_shows_srval(self):
        # AFF: INIT = 0 (ZINI set); BFF: SRVAL = 1 (ZRST cleared -> FDSE); the rest INIT 1 / SRVAL 0
        c = self.cfg(AFF__ff_init=1, BFF__ff_srval=0)
        t = self.fab.observe(c, [fm.init(), fm.set_(0, ce=ALL, d=0), *fm.pulse(ce=ALL, d=0), fm.set_(0, ce=ALL, sr=ALL, d=0), fm.set_(1, ce=ALL, sr=ALL, d=0)])
        init_readout = [0, 1, 1, 1, 1, 1, 1, 1]                     # by hand: Q := INIT at the init event
        self.assertEqual(q_after(t)[0], init_readout)
        self.assertEqual(q_after(t)[1], init_readout, "a level step without an edge changes nothing on a synchronous flip-flop")
        self.assertEqual(q_after(t)[2], [0] * 8, "the rising edge captured D = 0 with CE high")
        self.assertEqual(q_after(t)[3], [0] * 8, "the falling edge is not the capturing edge")
        self.assertEqual(q_after(t)[4], [0] * 8, "synchronous SR asserted at level: nothing until the edge")
        sr_readout = [0, 0, 1, 0, 0, 0, 0, 0]                       # by hand: at the edge SR wins, Q := SRVAL; BFF (index 2) has SRVAL 1
        self.assertEqual(q_after(t)[5], sr_readout)
        self.assertNotEqual(init_readout, sr_readout, "the two restore mechanisms are observed at different readouts and differ")
        self.assertEqual(t["decoded"]["BFF"]["primitive"], "FDSE")
        self.assertEqual(t["decoded"]["AFF"]["primitive"], "FDRE")

    def test_sr_not_driven_is_tied_low(self):
        c = self.cfg(sr_mode=0, BFF__ff_srval=0)
        t = self.fab.observe(c, [fm.init(), *fm.pulse(ce=ALL, sr=ALL, d=0)])
        self.assertEqual(q_after(t)[1], [0] * 8, "with SR tied low the edge captured D, SR had no effect")


class CeEdgeAndKind(Base):
    def test_ce_driven_gates_the_capture_and_tied_high_does_not(self):
        driven = self.fab.observe(self.cfg(), [fm.init(), *fm.pulse(ce=0, d=0)])
        self.assertEqual(q_after(driven)[1], [1] * 8, "CE driven and low: the flip-flop held INIT")
        tied = self.fab.observe(self.cfg(ce_mode=0), [fm.init(), *fm.pulse(ce=0, d=0)])
        self.assertEqual(q_after(tied)[1], [0] * 8, "CE tied high: the edge captured D = 0 whatever the CE input")
        half = self.fab.observe(self.cfg(), [fm.init(), *fm.pulse(ce=0x0F, d=0)])
        self.assertEqual(q_after(half)[1], [0, 0, 0, 0, 1, 1, 1, 1], "per-element CE")

    def test_the_capturing_edge_is_the_physical_rising_edge(self):
        plain = self.fab.observe(self.cfg(), [fm.init(), fm.set_(1, ce=ALL, d=0), fm.set_(0, ce=ALL, d=ALL)])
        self.assertEqual(q_after(plain), [[1] * 8, [0] * 8, [0] * 8], "rising captured 0; the falling edge captured nothing")
        inv = self.fab.observe(self.cfg(clock_mode=1), [fm.init(), fm.set_(1, ce=ALL, d=0), fm.set_(0, ce=ALL, d=ALL)])
        # by hand: the physical clock starts HIGH (slice clock 0 xor inverted); slice 0->1 is a physical falling edge
        # (no capture); slice 1->0 is the physical rising edge, capturing D = 1
        self.assertEqual(q_after(inv), [[1] * 8, [1] * 8, [1] * 8])
        self.assertEqual(inv["steps"][1]["physical_edge"], ["falling"] * 8)
        self.assertEqual(inv["steps"][2]["physical_edge"], ["rising"] * 8)
        self.assertEqual(inv["steps"][2]["edge"], "falling", "the slice-clock edge is recorded as it is; the physical edge per element")

    def test_asynchronous_sr_acts_on_the_level_and_synchronous_only_at_the_edge(self):
        sync = self.fab.observe(self.cfg(), [fm.init(), fm.set_(0, ce=ALL, sr=ALL, d=ALL)])
        self.assertEqual(q_after(sync)[1], [1] * 8, "synchronous: SR asserted without an edge does nothing")
        async_ = self.fab.observe(self.cfg(sr_kind=0), [fm.init(), fm.set_(0, ce=ALL, sr=ALL, d=ALL)])
        self.assertEqual(q_after(async_)[1], [0] * 8, "asynchronous: SR asserted at the level clears to SRVAL at once")
        self.assertEqual(async_["decoded"]["AFF"]["primitive"], "FDCE")
        preset = self.fab.observe(self.cfg(sr_kind=0, CFF__ff_srval=0), [fm.init(), *fm.pulse(ce=ALL, d=0), fm.set_(0, ce=ALL, sr=ALL, d=0)])
        self.assertEqual(q_after(preset)[3], [0, 0, 0, 0, 1, 0, 0, 0], "FDPE: the asynchronous preset sets CFF (index 4) to 1")
        self.assertEqual(preset["decoded"]["CFF"]["primitive"], "FDPE")


class Latches(Base):
    def test_transparent_while_the_gate_is_high_hold_when_low_and_x5ff_not_applicable(self):
        c = self.cfg(storage_kind=1)
        t = self.fab.observe(c, [fm.init(), fm.set_(1, ce=ALL, d=0x05), fm.set_(1, ce=ALL, d=0x00), fm.set_(0, ce=ALL, d=0x00), fm.set_(0, ce=ALL, d=0x55)])
        na = None
        # by hand: AFF, BFF, CFF, DFF are LDCE (indices 0, 2, 4, 6); the x5FF elements are not storage elements -> None
        self.assertEqual(q_after(t)[0], [1, na, 1, na, 1, na, 1, na], "init: INIT on the four latches, None on x5FF")
        self.assertEqual(q_after(t)[1], [1, na, 1, na, 0, na, 0, na], "gate high: Q follows D (0x05 = bits 0 and 2 -> AFF 1, BFF 1, CFF 0, DFF 0)")
        self.assertEqual(q_after(t)[2], [0, na, 0, na, 0, na, 0, na], "gate still high, D changed without an edge: Q follows")
        self.assertEqual(q_after(t)[3], [0, na, 0, na, 0, na, 0, na], "gate closed")
        self.assertEqual(q_after(t)[4], [0, na, 0, na, 0, na, 0, na], "gate low: D changed, Q holds")
        self.assertEqual(t["steps"][4]["applicable"], [True, False] * 4)
        self.assertEqual(t["decoded"]["AFF"]["primitive"], "LDCE")
        self.assertIsNone(t["decoded"]["A5FF"]["primitive"])

    def test_a_latch_with_ge_low_holds_and_its_sr_is_asynchronous(self):
        c = self.cfg(storage_kind=1, DFF__ff_srval=0)
        t = self.fab.observe(c, [fm.init(), fm.set_(1, ce=0, d=0), fm.set_(1, ce=ALL, sr=ALL, d=0)])
        self.assertEqual(q_after(t)[1], [1, None, 1, None, 1, None, 1, None], "GE low: the open gate does not pass D")
        self.assertEqual(q_after(t)[2], [0, None, 0, None, 0, None, 1, None], "SR on a latch acts at the level: CLR to 0, PRE on DFF to 1")
        self.assertEqual(t["decoded"]["DFF"]["primitive"], "LDPE")


class Isolation(Base):
    def test_an_observation_starts_from_nothing_and_init_gives_the_value(self):
        a = self.fab.observe(self.cfg(), [fm.init(), *fm.pulse(ce=ALL, d=0)])
        self.assertEqual(q_after(a)[-1], [0] * 8)
        b = self.fab.observe(self.cfg(), [fm.init()])
        self.assertEqual(q_after(b)[0], [1] * 8, "the second candidate's init readout is INIT, not what the first left")
        bare = self.fab.observe(self.cfg(), [fm.set_(0, ce=ALL, d=ALL), *fm.pulse(ce=ALL, d=ALL)])
        self.assertEqual(q_after(bare)[0], [None] * 8, "without an init step nothing is known")
        self.assertEqual(bare["initial"]["q"], [None] * 8)
        self.assertEqual(bare["steps"][0]["prev_event"], "none")

    def test_the_fabric_keeps_no_state_between_observations(self):
        one = self.fab.observe(self.cfg(), [fm.init(), *fm.pulse(ce=ALL, d=ALL)])
        again = self.fab.observe(self.cfg(), [fm.init(), *fm.pulse(ce=ALL, d=ALL)])
        self.assertEqual(one, again)
        other = fm.Fabric(self.m, self.h).observe(self.cfg(), [fm.init(), *fm.pulse(ce=ALL, d=ALL)])
        self.assertEqual(one, other, "a fresh fabric gives the same trace")


class Fixtures(Base):
    def test_permuted_is_the_truth_re_addressed_and_not_the_truth(self):
        truth = fm.fixture("truth", self.m, self.h)
        perm = fm.fixture("permuted", self.m, self.h, seed=3)
        self.assertNotEqual(perm.effect, truth.effect)
        # the re-addressing: a bit set at address a on the permuted fabric drives perm.effect[a]; on the truth that
        # target sits at mapping.address_of(*perm.effect[a])
        rng = random.Random(11)
        stim = [fm.init(), fm.set_(0, ce=0xA5, sr=0x30, d=0x5A), *fm.pulse(ce=0xA5, sr=0x30, d=0x5A), fm.set_(1, ce=ALL, d=0xC3)]
        differs = 0
        for _ in range(12):
            c = {a: rng.randint(0, 1) for a in self.m.addresses}
            c_truth = {a: 0 for a in self.m.addresses}
            for a in self.m.addresses:
                if c[a]:
                    c_truth[self.m.address_of(*perm.effect[a])] = 1
            self.assertEqual(q_after(perm.observe(c, stim)), q_after(truth.observe(c_truth, stim)))
            differs += q_after(perm.observe(c, stim)) != q_after(truth.observe(c, stim))
        self.assertGreater(differs, 0, "the permuted fabric is not the truth")

    def test_dropout_addresses_move_nothing(self):
        drop = fm.fixture("dropout", self.m, self.h, seed=1, drop=5)
        self.assertEqual(len(drop.dropout), 5)
        for a in drop.dropout:
            on = {**self.cfg(), a: 1}
            off = {**self.cfg(), a: 0}
            stim = [fm.init(), fm.set_(1, ce=ALL, sr=ALL, d=0x0F), fm.set_(0, ce=ALL, d=0xF0)]
            self.assertEqual(q_after(drop.observe(on, stim)), q_after(drop.observe(off, stim)), a)

    def test_every_hypothesis_swap_changes_a_trace_the_truth_would_not(self):
        truth = fm.fixture("truth", self.m, self.h)
        probes = {
            "ce_ungated": (self.cfg(), [fm.init(), *fm.pulse(ce=0, d=0)]),
            "init_no_effect": (self.cfg(), [fm.init()]),
            "latch_hold": (self.cfg(storage_kind=1), [fm.init(), fm.set_(1, ce=ALL, d=0)]),
            "sync_level": (self.cfg(), [fm.init(), fm.set_(0, ce=ALL, sr=ALL, d=ALL)]),
            "x5ff_storage": (self.cfg(storage_kind=1), [fm.init()]),
            "zini_polarity": (self.cfg(AFF__ff_init=1), [fm.init()]),
        }
        self.assertEqual(set(probes), set(fm.SWAPS))
        for kind, (c, stim) in probes.items():
            with self.subTest(swap=kind):
                swapped = fm.fixture(kind, self.m, self.h)
                self.assertNotEqual(swapped.hypothesis.sha256, self.h.sha256)
                self.assertNotEqual(q_after(swapped.observe(c, stim)), q_after(truth.observe(c, stim)), "the swap left the trace unchanged: the model is not reading its hypothesis")
                self.assertEqual(swapped.observe(c, stim)["hypothesis"]["version"], f"0.1.0+{kind}")

    def test_an_unknown_fixture_is_refused(self):
        with self.assertRaises(fm.ModelRefusal):
            fm.fixture("oracle", self.m, self.h)


class TheTrace(Base):
    def test_every_readout_carries_the_whole_context_and_the_trace_is_serialisable(self):
        t = self.fab.observe(self.cfg(clock_mode=1), [fm.init(), fm.set_(1, ce=0x3C, sr=0x01, d=0x81), fm.set_(1, ce=0x3C, sr=0x00, d=0x7E), fm.set_(0, ce=ALL, d=0)])
        want = {"step", "kind", "prev_event", "clock_before", "clock_after", "edge", "physical_edge", "ce", "sr", "d", "q_before", "q_after", "applicable"}
        for s in t["steps"]:
            self.assertEqual(set(s), want)
        self.assertEqual([s["prev_event"] for s in t["steps"]], ["none", "init", "edge", "level"])
        self.assertEqual([s["edge"] for s in t["steps"]], [None, "rising", None, "falling"])
        self.assertEqual(t["steps"][1]["q_before"], [1] * 8)
        self.assertEqual((t["hypothesis"]["sha256"], t["mapping"]["certificate_sha256"]), (self.h.sha256, self.m.certificate_sha256))
        self.assertEqual(len(t["config_sha256"]), 64)
        self.assertEqual(json.loads(json.dumps(t)), t)
        fields = self.h.doc["observation_context"]["fields"]
        self.assertTrue(any(f.startswith("prev_event") for f in fields) and any(f.startswith("physical_edge") for f in fields))

    def test_the_genome_order_is_the_mapping_s_and_bad_input_is_refused(self):
        c = self.fab.config_from_genome(1 << self.m.genome_bit(self.m.address_of("AFF", "ff_init")))
        self.assertEqual(sum(c.values()), 1)
        self.assertEqual(self.fab.observe(c, [fm.init()])["decoded"]["AFF"]["init"], 0)
        with self.assertRaises(fm.ModelRefusal):
            self.fab.config_from_genome(1 << 21)
        with self.assertRaises(fm.ModelRefusal):
            self.fab.observe({}, [fm.init()])
        with self.assertRaises(fm.ModelRefusal):
            self.fab.observe(self.cfg(), [{"kind": "readout"}])
        with self.assertRaises(fm.ModelRefusal):
            fm.set_(2)


if __name__ == "__main__":
    unittest.main()

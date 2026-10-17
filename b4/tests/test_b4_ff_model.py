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
  * every readout carries the complete EXECUTING-SIDE context and nothing derived from the decode (no primitive,
    INIT, SRVAL, kind, inversion, applicability or physical edge — those come only from the host-only `diagnose`
    / `step_diagnostics`); a trace is deterministic and JSON-serialisable;
  * (the owner's HOLD on 2bad829) the attested LDCE endpoint — CLKINV = 1 with IS_G_INVERTED = 0 — holds INIT
    with the gate low; a latch with the CLKINV bit clear is outside the domain and refused; `observe` validates
    the configuration, every step as handed (not only through `set_`) and the init step's context.
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
        diag = self.fab.diagnose(c)
        self.assertEqual((diag["decoded"]["BFF"]["primitive"], diag["decoded"]["AFF"]["primitive"], diag["visibility"]), ("FDSE", "FDRE", "host_only"))

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
        sd = self.fab.step_diagnostics(inv)                                  # host-only: the physical edge per element
        self.assertEqual(sd[1]["physical_edge"], ["falling"] * 8)
        self.assertEqual(sd[2]["physical_edge"], ["rising"] * 8)
        self.assertEqual(inv["steps"][2]["edge"], "falling", "the slice-clock edge is recorded as applied; the physical edge is a diagnostic")
        self.assertNotIn("physical_edge", inv["steps"][2])

    def test_asynchronous_sr_acts_on_the_level_and_synchronous_only_at_the_edge(self):
        sync = self.fab.observe(self.cfg(), [fm.init(), fm.set_(0, ce=ALL, sr=ALL, d=ALL)])
        self.assertEqual(q_after(sync)[1], [1] * 8, "synchronous: SR asserted without an edge does nothing")
        async_ = self.fab.observe(self.cfg(sr_kind=0), [fm.init(), fm.set_(0, ce=ALL, sr=ALL, d=ALL)])
        self.assertEqual(q_after(async_)[1], [0] * 8, "asynchronous: SR asserted at the level clears to SRVAL at once")
        self.assertEqual(self.fab.diagnose(self.cfg(sr_kind=0))["decoded"]["AFF"]["primitive"], "FDCE")
        preset = self.fab.observe(self.cfg(sr_kind=0, CFF__ff_srval=0), [fm.init(), *fm.pulse(ce=ALL, d=0), fm.set_(0, ce=ALL, sr=ALL, d=0)])
        self.assertEqual(q_after(preset)[3], [0, 0, 0, 0, 1, 0, 0, 0], "FDPE: the asynchronous preset sets CFF (index 4) to 1")
        self.assertEqual(self.fab.diagnose(self.cfg(sr_kind=0, CFF__ff_srval=0))["decoded"]["CFF"]["primitive"], "FDPE")


class Latches(Base):
    def test_transparent_while_the_gate_is_high_hold_when_low_and_x5ff_not_applicable(self):
        c = self.cfg(storage_kind=1, clock_mode=1)        # the attested latch endpoint carries CLKINV = 1 with IS_G_INVERTED = 0: the gate IS the slice clock
        t = self.fab.observe(c, [fm.init(), fm.set_(1, ce=ALL, d=0x05), fm.set_(1, ce=ALL, d=0x00), fm.set_(0, ce=ALL, d=0x00), fm.set_(0, ce=ALL, d=0x55)])
        na = None
        # by hand: AFF, BFF, CFF, DFF are LDCE (indices 0, 2, 4, 6); the x5FF elements are not storage elements -> None
        self.assertEqual(q_after(t)[0], [1, na, 1, na, 1, na, 1, na], "init: INIT on the four latches, None on x5FF")
        self.assertEqual(q_after(t)[1], [1, na, 1, na, 0, na, 0, na], "gate high: Q follows D (0x05 = bits 0 and 2 -> AFF 1, BFF 1, CFF 0, DFF 0)")
        self.assertEqual(q_after(t)[2], [0, na, 0, na, 0, na, 0, na], "gate still high, D changed without an edge: Q follows")
        self.assertEqual(q_after(t)[3], [0, na, 0, na, 0, na, 0, na], "gate closed")
        self.assertEqual(q_after(t)[4], [0, na, 0, na, 0, na, 0, na], "gate low: D changed, Q holds")
        self.assertNotIn("applicable", t["steps"][4])
        diag = self.fab.diagnose(c)
        self.assertEqual(diag["applicable"], [True, False] * 4)
        self.assertEqual((diag["decoded"]["AFF"]["primitive"], diag["decoded"]["A5FF"]["primitive"], diag["decoded"]["AFF"]["clk_inverted"]), ("LDCE", None, False))

    def test_the_attested_ldce_endpoint_holds_init_with_the_gate_low(self):
        """The owner's probe (docs/ff_latch_probe.md): the latch specimen has CLKINV = 1 and IS_G_INVERTED = 0. With the
        slice clock low the gate is CLOSED: GE high and D = 0 must not disturb INIT = 1. By hand: [1, None, 1, None, 1, None, 1, None]."""
        c = self.cfg(storage_kind=1, sr_kind=0, clock_mode=1)
        t = self.fab.observe(c, [fm.init(), fm.set_(0, ce=ALL, sr=0, d=0)])
        self.assertEqual(q_after(t), [[1, None, 1, None, 1, None, 1, None], [1, None, 1, None, 1, None, 1, None]])
        t2 = self.fab.observe(c, [fm.init(), fm.set_(1, ce=ALL, sr=0, d=0)])
        self.assertEqual(q_after(t2)[1], [0, None, 0, None, 0, None, 0, None], "with the slice clock high the gate opens and D = 0 passes")
        wrong = fm.fixture("latch_gate_inverted", self.m, self.h)            # the reading the probe says must NOT be applied to a latch
        self.assertEqual(q_after(wrong.observe(c, [fm.init(), fm.set_(0, ce=ALL, sr=0, d=0)]))[1], [0, None, 0, None, 0, None, 0, None])

    def test_a_latch_with_the_clkinv_bit_clear_is_outside_the_domain(self):
        c = self.cfg(storage_kind=1)                       # clock_mode bit 0 under a latch: nothing attests a reading
        with self.assertRaises(fm.ModelRefusal) as cm:
            self.fab.observe(c, [fm.init()])
        self.assertIn("outside the hypothesis's domain: no attested reading for clock_mode bit 0 under latch", str(cm.exception))
        diag = self.fab.diagnose(c)
        self.assertEqual((diag["in_domain"], diag["unknown_readings"]), (False, [["clock_mode", "latch", 0]]))

    def test_a_latch_with_ge_low_holds_and_its_sr_is_asynchronous(self):
        c = self.cfg(storage_kind=1, clock_mode=1, DFF__ff_srval=0)
        t = self.fab.observe(c, [fm.init(), fm.set_(1, ce=0, d=0), fm.set_(1, ce=ALL, sr=ALL, d=0)])
        self.assertEqual(q_after(t)[1], [1, None, 1, None, 1, None, 1, None], "GE low: the open gate does not pass D")
        self.assertEqual(q_after(t)[2], [0, None, 0, None, 0, None, 1, None], "SR on a latch acts at the level: CLR to 0, PRE on DFF to 1")
        self.assertEqual(self.fab.diagnose(c)["decoded"]["DFF"]["primitive"], "LDPE")


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
        differs = compared = 0
        for _ in range(48):
            c = {a: rng.randint(0, 1) for a in self.m.addresses}
            c_truth = {a: 0 for a in self.m.addresses}
            for a in self.m.addresses:
                if c[a]:
                    c_truth[self.m.address_of(*perm.effect[a])] = 1
            if not (perm.decode(c).in_domain and truth.decode(c_truth).in_domain and truth.decode(c).in_domain):
                continue                                     # a latch with the CLKINV bit clear is outside the domain on either side
            compared += 1
            self.assertEqual(q_after(perm.observe(c, stim)), q_after(truth.observe(c_truth, stim)))
            differs += q_after(perm.observe(c, stim)) != q_after(truth.observe(c, stim))
        self.assertGreaterEqual(compared, 12, "too few in-domain draws")
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
            "latch_hold": (self.cfg(storage_kind=1, clock_mode=1), [fm.init(), fm.set_(1, ce=ALL, d=0)]),
            "sync_level": (self.cfg(), [fm.init(), fm.set_(0, ce=ALL, sr=ALL, d=ALL)]),
            "x5ff_storage": (self.cfg(storage_kind=1, clock_mode=1), [fm.init()]),
            "zini_polarity": (self.cfg(AFF__ff_init=1), [fm.init()]),
            "latch_gate_inverted": (self.cfg(storage_kind=1, clock_mode=1), [fm.init(), fm.set_(0, ce=ALL, d=0)]),
        }
        self.assertEqual(set(probes), set(fm.SWAPS))
        for kind, (c, stim) in probes.items():
            with self.subTest(swap=kind):
                swapped = fm.fixture(kind, self.m, self.h)
                self.assertNotEqual(swapped.hypothesis.sha256, self.h.sha256)
                self.assertNotEqual(q_after(swapped.observe(c, stim)), q_after(truth.observe(c, stim)), "the swap left the trace unchanged: the model is not reading its hypothesis")
                head = swapped.observe(c, stim)["hypothesis"]
                self.assertEqual((head["version"], head["fixture"]), (f"0.2.0+{kind}", True), "a swapped hypothesis is marked in the trace")
        self.assertIs(truth.observe(self.cfg(), [fm.init()])["hypothesis"]["fixture"], False)

    def test_an_unknown_fixture_is_refused(self):
        with self.assertRaises(fm.ModelRefusal):
            fm.fixture("oracle", self.m, self.h)


class TheTrace(Base):
    def test_every_readout_carries_the_executing_side_context_only_and_the_trace_is_serialisable(self):
        t = self.fab.observe(self.cfg(clock_mode=1), [fm.init(), fm.set_(1, ce=0x3C, sr=0x01, d=0x81), fm.set_(1, ce=0x3C, sr=0x00, d=0x7E), fm.set_(0, ce=ALL, d=0)])
        want = set(fm.VISIBLE_STEP_KEYS)
        for s in t["steps"]:
            self.assertEqual(set(s), want)
        self.assertEqual([s["prev_event"] for s in t["steps"]], ["none", "init", "edge", "level"])
        self.assertEqual([s["edge"] for s in t["steps"]], [None, "rising", None, "falling"])
        self.assertEqual(t["steps"][1]["q_before"], [1] * 8)
        self.assertEqual((t["hypothesis"]["sha256"], t["mapping"]["certificate_sha256"], t["visibility"]), (self.h.sha256, self.m.certificate_sha256, "executing_side"))
        self.assertEqual(len(t["config_sha256"]), 64)
        self.assertEqual(t["stimulus"][1], {"kind": "set", "clock": 1, "ce": 0x3C, "sr": 0x01, "d": 0x81})
        self.assertEqual(json.loads(json.dumps(t)), t)
        def keys_of(o, acc):
            if isinstance(o, dict):
                acc.update(o); [keys_of(v, acc) for v in o.values()]
            elif isinstance(o, list):
                [keys_of(v, acc) for v in o]
            return acc
        for leak in ("decoded", "applicable", "physical_edge", "primitive", "srval", "clk_inverted", "ce_driven", "sr_driven", "sync", "latch", "in_domain", "unknown_readings"):
            self.assertNotIn(leak, keys_of(t, set()), f"{leak!r} is a decode-derived fact and must not be a key of an executing-side trace")
        oc = self.h.doc["observation_context"]
        self.assertTrue(any(f.startswith("prev_event") for f in oc["executing_side_visible"]))
        self.assertTrue(any(f.startswith("the physical edge") for f in oc["host_only_diagnostics"]))

    def test_an_observation_without_stimuli_hands_over_nothing(self):
        """The owner's probe: observe(config, []) used to return the whole decode. Now: no steps, no decode-derived key."""
        t = self.fab.observe(self.cfg(), [])
        self.assertEqual(t["steps"], [])
        for leak in ("decoded", "applicable", "physical_edge", "primitive"):
            self.assertNotIn(leak, json.dumps(t))

    def test_observe_validates_whatever_it_is_handed(self):
        """Steps that bypass set_() are validated at the entry (the owner's probes clock = 2 and sr = -1), and so is the configuration."""
        for bad, needle in ((dict(kind="set", clock=2, ce=255, sr=0, d=0), "clock = 2 is not an integer in [0, 1]"),
                            (dict(kind="set", clock=0, ce=0, sr=-1, d=0), "sr = -1 is not an integer in [0, 255]"),
                            (dict(kind="set", clock=True, ce=0, sr=0, d=0), "clock = True is not an integer"),
                            (dict(kind="set", clock=0, ce=0, sr=0), "a set step carries exactly"),
                            (dict(kind="init", clock=0), "an init step carries exactly"),
                            ("init", "a step must be a dict"),
                            (dict(kind="readout"), "kind 'readout' is not init / set")):
            with self.subTest(step=bad):
                with self.assertRaises(fm.ModelRefusal) as cm:
                    self.fab.observe(self.cfg(), [fm.init(), bad])
                self.assertIn(needle, str(cm.exception))
        with self.assertRaises(fm.ModelRefusal):
            self.fab.observe(self.cfg(), "init")
        c = self.cfg(); c[self.m.addresses[0]] = True
        with self.assertRaises(fm.ModelRefusal) as cm:
            self.fab.observe(c, [fm.init()])
        self.assertIn("not 0 / 1", str(cm.exception))
        c = self.cfg(); c["0x00000000/0/0"] = 0
        with self.assertRaises(fm.ModelRefusal):
            self.fab.observe(c, [fm.init()])
        with self.assertRaises(fm.ModelRefusal):
            self.fab.observe({a: 0 for a in self.m.addresses[:-1]}, [fm.init()])

    def test_the_init_step_is_allowed_only_with_the_clock_low_and_sr_de_asserted(self):
        with self.assertRaises(fm.ModelRefusal) as cm:
            self.fab.observe(self.cfg(), [fm.set_(1, ce=ALL), fm.init()])
        self.assertIn("an init step is allowed only with the slice clock low and SR de-asserted (clock 1, sr 0x00)", str(cm.exception))
        with self.assertRaises(fm.ModelRefusal):
            self.fab.observe(self.cfg(), [fm.set_(0, sr=0x01), fm.init()])
        t = self.fab.observe(self.cfg(), [fm.set_(1, ce=ALL, sr=ALL), fm.set_(0, ce=ALL, sr=0), fm.init()])
        self.assertEqual(q_after(t)[2], [1] * 8, "after the clock falls and SR is released, an init is allowed and gives INIT")

    def test_the_genome_order_is_the_mapping_s_and_bad_input_is_refused(self):
        c = self.fab.config_from_genome(1 << self.m.genome_bit(self.m.address_of("AFF", "ff_init")))
        self.assertEqual(sum(c.values()), 1)
        self.assertEqual(self.fab.diagnose(c)["decoded"]["AFF"]["init"], 0)
        self.assertEqual(q_after(self.fab.observe(c, [fm.init()]))[0], [0, 1, 1, 1, 1, 1, 1, 1])
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

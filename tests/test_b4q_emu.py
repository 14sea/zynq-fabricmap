"""B4Q — the host emulation of the carrier v2 (host/b4q_emu.py) held to the RTL and to the hypothesis model.

  * FIDELITY: the 27 archived bench traces of the carrier unit replay through the emulator with zero mismatches of data
    (or x pattern) and resp on every logged access (the heartbeat by its reset semantic); the three bus-level scenarios the
    bench drives by hand are compared up to the first unlogged handshake and say so.
  * THE FABRIC IS THE MODEL: a whole stimulus applied step by step through Fabric8 equals b4_ff_model.Fabric.observe()'s
    q_after rows on the six bench fixtures and on seeded random in-domain genomes and task-v0.3-shaped stimuli.
  * THE GATE IS THE SIGNER'S ARITHMETIC: the bench fixture's VALID1 verifies under KEY_A at the seed nonce; UNSIGNED,
    WRONG_COMMIT, a wrong key and a replay on the advanced nonce are F_ARM_AUTH; the nonce steps after every attempt.
  * x: an element the model gives no value for reads as x, and the record layer turns it into None (a carrier record then
    refuses it — the D1 rule seen from the host).
No skip: the instrument's signer library is bound read-only (gen_b4_fixture's precedent); its absence is a failure."""
from __future__ import annotations

import json
import random
import re
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "host", R / "b4/host"):
    sys.path.insert(0, str(p))
import b4q_emu as emu  # noqa: E402
import b4q_emu_fidelity as fid  # noqa: E402
import b4carrier_regmap as rm  # noqa: E402
import b4carrier_records as rec  # noqa: E402
import b4_ff_model as fm  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402

FIX = (R / "tb/b4/b4_fixture.vh").read_text()


def fixture_words(name: str) -> list[int]:
    h = re.search(rf"{name} = 768'h([0-9a-f]+);", FIX).group(1)
    return [int(h[8 * i:8 * i + 8], 16) for i in range(24)]


def key_words(name: str) -> list[int]:
    h = re.search(rf"{name} = 128'h([0-9a-f]+);", FIX).group(1)
    return [int(h[8 * i:8 * i + 8], 16) for i in range(4)]


def nonce(k: int) -> int:
    return int(re.search(rf"N{k} = 64'h([0-9a-f]+);", FIX).group(1), 16)


class Fidelity(unittest.TestCase):
    def test_every_archived_bench_trace_replays_without_a_mismatch(self):
        res = fid.run_all(emu.ENGINE_LATENCY, emu.GATE_TAG_AT)
        self.assertEqual(sorted(res), sorted(fid.SCHEDULE))
        for s, r in res.items():
            self.assertEqual(r["mismatches"], [], (s, r["mismatches"][:2]))
            self.assertGreater(r["reads"] + r["writes"], 0, s)
            if s in fid.UNLOGGED:
                self.assertEqual(r["compared_up_to"], fid.UNLOGGED[s][0])
            else:
                self.assertIsNone(r["compared_up_to"])
                self.assertEqual(r["reads"] + r["writes"], r["events_in_trace"], s)
        self.assertGreater(sum(r["reads"] for r in res.values()), 1800)
        self.assertIn("flow", res); self.assertEqual(res["flow"]["reads"] + res["flow"]["writes"], res["flow"]["events_in_trace"])


class FabricIsTheModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapping, cls.hyp = bm.site_mapping(), hy.load()
        cls.model = fm.Fabric(cls.mapping, cls.hyp)

    def run_both(self, genome: int, steps: list):
        stim = [fm.init()] + [fm.set_(c, ce, sr, d) for (c, ce, sr, d) in steps]
        want = self.model.observe(self.model.config_from_genome(genome), stim)
        f = emu.Fabric8(self.model, genome, None)
        f.init_event()
        self.assertEqual(f.q, want["steps"][0]["q_after"])
        for k, (c, ce, sr, d) in enumerate(steps, start=1):
            f.apply_controls(ce, sr, d); f.apply_clock(c)
            self.assertEqual(f.q, want["steps"][k]["q_after"], (genome, k))

    def test_the_six_bench_fixtures(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("genfix", R / "tb/b4/gen_b4_fixture.py")
        text = (R / "tb/b4/gen_b4_fixture.py").read_text()
        sched = eval(text[text.index("SCHEDULE = [") + len("SCHEDULE = "):text.index("]\n\ntraces = []") + 1])
        for name, genome, steps in sched:
            self.run_both(genome, [(c, 0xFF if ce else 0, 0xFF if sr else 0, d) for (c, ce, sr, d) in steps])

    def test_random_in_domain_genomes_under_slice_wide_stimuli(self):
        rng = random.Random(1234)
        n = 0
        while n < 60:
            g = rng.getrandbits(21)
            try:
                if not self.model.decode(self.model.config_from_genome(g)).in_domain:
                    continue
            except fm.ModelRefusal:
                continue
            steps = [(rng.getrandbits(1), 0xFF if rng.getrandbits(1) else 0, 0xFF if rng.getrandbits(2) == 0 else 0, rng.getrandbits(8)) for _ in range(7)]
            self.run_both(g, steps); n += 1

    def test_unmodelled_elements_read_as_x(self):
        e = emu.CarrierEmu(genome=0, power_on="x")
        data, x, resp = e.read(rm.Q_LIVE)
        self.assertEqual((data, resp), (None, 0)); self.assertEqual(x, "0" * 24 + "x" * 8)
        self.assertEqual(rec._cells_of({"data": None, "x": x}), [None] * 8)
        e2 = emu.CarrierEmu(genome=(1 << 10) | (1 << 6) | (1 << 4), power_on="init")       # the LATCH fixture: x5FF are not storage elements
        data, x, _ = e2.read(rm.Q_LIVE)
        self.assertIsNone(data); self.assertEqual(x[-8:], "x1x1x1x1")


class GateIsTheSigner(unittest.TestCase):
    def provision(self, e, key):
        for j, w in enumerate(key):
            self.assertEqual(e.write(rm.KEY[j], w), 0)
        self.assertEqual(e.write(rm.CTRL, rm.ctrl_word("key_commit")), 0)
        e.t += 10

    def stage_arm(self, e, words, a5=False):
        for i, w in enumerate(words[:20]):
            e.write(rm.PAYLOAD[i], w)
        for i, w in enumerate(words[20:]):
            e.write(rm.TAG[i], w)
        self.assertEqual(e.write(rm.CTRL, rm.ctrl_word("arm", a5=a5)), 0)
        e.t += 100
        return rm.decode_status(e.read(rm.STATUS)[0]), e.read(rm.FAULT)[0]

    def test_valid_unsigned_wrong_commit_wrong_key_replay(self):
        e = emu.CarrierEmu(genome=0)
        self.provision(e, key_words("KEY_A"))
        st, f = self.stage_arm(e, fixture_words("VALID1"))
        self.assertEqual((st["configuration_valid_hw"], st["tag_ok"], f), (1, 1, 0))
        self.assertEqual((e.read(rm.NONCE_LO)[0] | (e.read(rm.NONCE_HI)[0] << 32)), nonce(1))
        for i in range(8):
            self.assertEqual(e.read(rm.HW_COMMIT[i])[0], fixture_words("VALID1")[i])
        for case in ("UNSIGNED", "WRONG_COMMIT"):
            e2 = emu.CarrierEmu(genome=0); self.provision(e2, key_words("KEY_A"))
            st, f = self.stage_arm(e2, fixture_words(case))
            self.assertEqual((st["configuration_valid_hw"], st["fault"], st["recovery_required"], f), (0, 1, 1, 13), case)
        e3 = emu.CarrierEmu(genome=0); self.provision(e3, key_words("KEY_B"))
        st, f = self.stage_arm(e3, fixture_words("VALID1"))
        self.assertEqual(f, 13)
        e4 = emu.CarrierEmu(genome=0)                                           # no key: F_ARM_NOKEY, the nonce consumed
        st, f = self.stage_arm(e4, fixture_words("VALID1"))
        self.assertEqual(f, 12); self.assertEqual(e4.read(rm.NONCE_LO)[0], nonce(1) & 0xFFFFFFFF)
        # a replay of VALID1 on the advanced nonce (after a closed transaction): AUTH
        e5 = emu.CarrierEmu(genome=0, power_on="init"); self.provision(e5, key_words("KEY_A"))
        self.stage_arm(e5, fixture_words("VALID1"))
        for op in ("pre_sample", "init_req", "cleanup", "restore_init", "close"):
            self.assertEqual(e5.write(rm.CTRL, rm.ctrl_word(op)), 0, op); e5.t += 60
        self.assertEqual(rm.decode_status(e5.read(rm.STATUS)[0])["idle"], 1)
        st, f = self.stage_arm(e5, fixture_words("VALID1"))
        self.assertEqual(f, 13)

    def test_a5_context_rule_and_sequence_faults(self):
        e = emu.CarrierEmu(genome=0, power_on="init"); self.provision(e, key_words("KEY_A"))
        st, f = self.stage_arm(e, fixture_words("VALID1"), a5=True)                # the flag with no injection open
        self.assertEqual(f, 7)
        e = emu.CarrierEmu(genome=0, power_on="init"); self.provision(e, key_words("KEY_A"))
        self.stage_arm(e, fixture_words("VALID1"))
        self.assertEqual(e.write(rm.CTRL, rm.ctrl_word("step")), 0); e.t += 60       # STEP before the init event
        self.assertEqual(e.read(rm.FAULT)[0], 7)
        self.assertEqual(rm.decode_status(e.read(rm.STATUS)[0])["recovery_required"], 1)
        self.assertEqual(e.write(rm.CTRL, rm.ctrl_word("pre_sample")), 0); e.t += 60  # refused silently under recovery
        self.assertEqual(rm.decode_status(e.read(rm.STATUS)[0])["pre_sampled"], 0)

    def test_busy_and_combined_ctrl_writes_are_slverr(self):
        e = emu.CarrierEmu(genome=0, power_on="init"); self.provision(e, key_words("KEY_A"))
        self.stage_arm(e, fixture_words("VALID1"))
        self.assertEqual(e.write(rm.CTRL, rm.ctrl_word("step") | rm.ctrl_word("close")), 2)
        self.assertEqual(e.write(rm.CTRL, rm.ctrl_word("pre_sample")), 0); e.t += 60
        self.assertEqual(e.write(rm.CTRL, rm.ctrl_word("init_req")), 0)
        t_before = e.t
        self.assertEqual(e.write(rm.CTRL, rm.ctrl_word("step"), cost=1), 0)            # presented while the event is pending: HELD by the gate, served after the event — and then accepted (init_done)
        self.assertGreater(e.t, t_before + 30)                                           # the access waited at the bus for the event
        e.t += 80
        self.assertEqual(rm.decode_status(e.read(rm.STATUS)[0])["init_done"], 1)
        self.assertEqual(rm.decode_status(e.read(rm.STATUS)[0])["step_index"], 1)      # the held STEP applied after the event
        e.write(rm.STEP_IN, rm.step_word(0x5A, 0xFF, 0, 1))
        self.assertEqual(e.write(rm.CTRL, rm.ctrl_word("step")), 0)
        self.assertEqual(e.write(rm.CTRL, rm.ctrl_word("close")), 2)                    # during an in-flight step


if __name__ == "__main__":
    unittest.main()

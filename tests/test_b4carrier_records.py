"""The O / F / X / session_open records: built from the bench's own register traces (sim/b4/out/*.jsonl) and validated in
three layers — structure (closed at every level, typed, order-independent), binding to a trusted context, the chain. The
owner's counterexamples of 2026-10-21 (nested keys, empty steps, null samples, wrong kinds / types / variant, the
sorted-JSON round trip, a list for an object, a boolean fitness, a short target, a non-idle closed X, a null session_open,
an X sealed before CLOSE, a refused step dropped from the stimulus, a fabricated init step) are the negative cases."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b4carrier_records as rec  # noqa: E402
import b4carrier_regmap as rm  # noqa: E402

OUT = R / "sim/b4/out"
HAVE_SIM = shutil.which("iverilog") is not None and Path("/home/test/zynq_psoracle").is_dir()


def _h(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


INSTRUMENT = {"variant": f"{rm.VARIANT_WORD:08x}", "carrier_sha256": _h("carrier"), "image_sha256": _h("image")}
FRAMES = _h("candidate-frames")          # mechanism (b): staging = pre-event = post-event (the write, then a frame-invariant event)
STARTUP = _h("startup")                  # the pinned loaded-frame reference: read at session open, the base every transaction restores to
LINKS = {"instrument": INSTRUMENT, "nonce": _h("nonce")[:16], "commit": _h("commit"), "staging_readback_sha256": FRAMES,
         "fabric_readback_sha256_pre_event": FRAMES, "fabric_readback_sha256_post_event": FRAMES, "config": [0] * 21,
         "base_readback_sha256": STARTUP}
TIMING = {**rm.decode_timing(rm.timing_word(8, 16, 4, 4, 4)), "pulse": 2}
ROOT = {"kind": "session_root", "seq": None, "close_sha256": None}
# the TRUSTED task of the bench's context: every cell of the seven set steps scored against 0 — the fitness a bound F must
# equal when recomputed over the full physical grid (validate_bound), whatever F itself claims
TASK = {"mask": [(s, e) for s in range(1, 8) for e in range(8)], "target": [0] * 56, "weights": [1] * 56, "digest": _h("task")}
STIM7 = None   # the fixture stimuli (read from the fixture header)


def fixture_stimuli() -> list[list[dict]]:
    """The six fixtures' declared stimuli from tb/b4/b4_fixture.vh (an init step and seven set steps each)."""
    text = (R / "tb/b4/b4_fixture.vh").read_text()
    out = []
    for k in range(6):
        steps = [{"kind": "init"}]
        for j in range(7):
            w = int(text.split(f"FIX{k}_IN{j} = 25'h")[1].split(";")[0], 16)
            a = rm.decode_applied(w)
            steps.append({"kind": "set", "clock": a["clock"], "ce": a["ce"], "sr": a["sr"], "d": a["d"]})
        out.append(steps)
    return out


def ensure_traces():
    if not (OUT / "flow.jsonl").is_file():
        subprocess.run(["bash", str(R / "sim/b4/run.sh")], capture_output=True, text=True, timeout=900)


def ctx_for(stim, seq_prev_close, config=None, session="bench"):
    return {"instrument": INSTRUMENT, "session": session, "stimulus": stim, "config": config or [0] * 21, "task_digest": _h("task"), "task": TASK,
            "predecessor_close_sha256": seq_prev_close, "nonce": LINKS["nonce"], "mechanism": "b", "pulse_clocks": 2,
            "base_readback_sha256": LINKS["base_readback_sha256"]}


def roundtrip(obj):
    return json.loads(json.dumps(obj, sort_keys=True))


@unittest.skipUnless(HAVE_SIM, "iverilog or the instrument absent")
class FromTheBench(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_traces()
        cls.flow = rec.transactions(rec.load_trace(OUT / "flow.jsonl"))
        cls.stim = fixture_stimuli()

    def test_the_flow_as_a_chain(self):
        """Six transactions: the four flip-flop fixtures validate at all three layers and chain; the first one's
        pre-init sample is the model's never-initialised fabric (x -> null) and the two latch fixtures carry the model's
        null on the x5FF cells — the CARRIER validator refuses those, which is the D1 rule seen from the bench."""
        self.assertEqual(len(self.flow), 6)
        prev_close = None
        for i, evs in enumerate(self.flow, start=1):
            pred = ROOT if i == 1 else {"kind": "closed", "seq": i - 1, "close_sha256": prev_close}
            o = rec.observation(evs, LINKS, TIMING, seq=i, session="bench", predecessor=pred, declared_stimulus=self.stim[i - 1])
            self.assertEqual(o["status"], "complete", i)
            self.assertEqual(len(o["steps"]), 8, i)
            self.assertEqual(o["stimulus"], self.stim[i - 1])
            findings = rec.validate_observation(o)
            if i == 1:
                self.assertTrue(findings and all(("initial" in f or "steps[0]" in f) for f in findings), (i, findings))
                x = rec.transaction_close(evs, o, seq=i, links=LINKS)            # the close exists and is named by the next predecessor
                self.assertEqual(x["status"], "closed")
                prev_close = rec.sha256_json(x)
            elif i <= 4:
                self.assertEqual(findings, [], i)
                x = rec.transaction_close(evs, o, seq=i, links=LINKS)
                self.assertEqual(x["status"], "closed")
                self.assertEqual(x["idle_status"], 1)
                self.assertEqual(rec.validate_close(x, o), [], i)
                self.assertEqual(x["base_state_sample"], o["steps"][0]["q_after"])       # the restore event's sample on the base = the init sample
                fr = rec.fitness(o, TASK)
                self.assertEqual(rec.validate_fitness(fr, o), [])
                self.assertEqual(fr["fitness"], sum(1 for s in o["steps"][1:] for c in s["q_after"] if c == 0))
                self.assertEqual(rec.validate_bound(o, ctx_for(self.stim[i - 1], prev_close), fr, x), [], i)
                # the sorted-JSON round trip changes nothing
                self.assertEqual(rec.validate_observation(roundtrip(o)), []); self.assertEqual(rec.observation_sha256(roundtrip(o)), rec.observation_sha256(o))
                prev_close = rec.sha256_json(x)
            else:
                self.assertTrue(findings and all("bad value" in f and ("q_" in f or "initial" in f) for f in findings), (i, findings))
                x = rec.transaction_close(evs, o, seq=i, links=LINKS)
                prev_close = rec.sha256_json(x)

    def test_a_refused_step_stays_declared_and_the_prefix_is_acquired(self):
        evs = rec.load_trace(OUT / "fault_realisable.jsonl")
        declared = self.stim[0][:3] + [{"kind": "set", "clock": 0, "ce": 0x3C, "sr": 0, "d": 0xA5}]   # the third set step is the non-uniform one
        o = rec.observation(evs, LINKS, TIMING, seq=1, session="bench", predecessor=ROOT, declared_stimulus=declared)
        self.assertEqual(o["status"], "invalid")
        self.assertEqual(o["fault"], {"code": "not_realisable", "phase_reached": "P5", "step_reached": 2})
        self.assertEqual(len(o["stimulus"]), 4)                     # the declared stimulus is kept whole, the refused step included
        self.assertEqual(len(o["steps"]), 3)                        # the acquired prefix: init + two applied steps
        findings = rec.validate_observation(o)
        self.assertTrue(all(("initial" in f or "steps[0]" in f) for f in findings), findings)   # only the model's x pre-init sample
        with self.assertRaises(rec.RecordRefusal):
            rec.fitness(o, {"mask": [], "target": [], "weights": [], "digest": _h("t")})
        with self.assertRaises(rec.RecordRefusal):
            rec.transaction_close(evs, o, seq=1, links=LINKS)       # the transaction never closed

    def test_no_sample_no_step(self):
        evs = rec.load_trace(OUT / "fault_not_armed.jsonl")
        o = rec.observation(evs, LINKS, TIMING, seq=1, session="bench", predecessor=ROOT, declared_stimulus=self.stim[0])
        self.assertEqual(o["status"], "invalid"); self.assertEqual(o["steps"], []); self.assertNotIn("initial", o)
        self.assertEqual(o["fault"]["phase_reached"], "P2")

    def test_a5_injection_and_context(self):
        trace = rec.load_trace(OUT / "a5.jsonl")
        marks = [e.get("mark") for e in trace]
        j1 = rec.transactions(trace)[0]
        j2 = trace[marks.index("J2_begin"):marks.index("J2_end")]
        j3 = trace[marks.index("J3_begin"):marks.index("J3_end")]
        o1 = rec.observation(j1, LINKS, TIMING, seq=1, session="bench", predecessor=ROOT, declared_stimulus=self.stim[0])
        x1 = rec.transaction_close(j1, o1, seq=1, links=LINKS)
        cprime = [{"kind": "init"}, {"kind": "set", "clock": 1, "ce": 0xFF, "sr": 0, "d": 0}]
        o2 = rec.observation(j2, LINKS, TIMING, seq=2, session="bench", predecessor={"kind": "closed", "seq": 1, "close_sha256": rec.sha256_json(x1)}, declared_stimulus=cprime)
        self.assertEqual(rec.validate_observation(o2), [])
        x2 = rec.transaction_close(j2, o2, seq=2, links=LINKS)
        self.assertEqual(x2["status"], "injection_open"); self.assertEqual(x2["idle_status"], 0); self.assertEqual(rec.validate_close(x2, o2), [])
        o3 = rec.observation(j3, LINKS, TIMING, seq=3, session="bench", predecessor={"kind": "a5_injection", "seq": 2, "close_sha256": rec.sha256_json(x2)}, declared_stimulus=self.stim[0][:1])
        self.assertEqual(o3["initial"]["context"], "a5_injection")
        self.assertEqual((o3["initial"]["clock"], o3["initial"]["ce"], o3["initial"]["d"]), (1, 1, 0))
        self.assertEqual(o3["initial"]["q"], [0] * 8)                 # the injection arrived
        self.assertEqual(o3["steps"][0]["q_after"], [1] * 8)          # and was cleared by the event
        self.assertEqual(rec.validate_observation(o3), [])
        x3 = rec.transaction_close(j3, o3, seq=3, links=LINKS)
        self.assertEqual(x3["status"], "closed")
        chain = rec.validate_chain(rec.session_open(INSTRUMENT, _h("startup"), _h("startup")),
                                   [{"o": o1, "x": x1, "ctx": ctx_for(self.stim[0], None)},
                                    {"o": o2, "x": x2, "ctx": ctx_for(cprime, None)},
                                    {"o": o3, "x": x3, "ctx": ctx_for(self.stim[0][:1], None)}])
        self.assertTrue(all("chain[0]" in f and ("initial" in f or "steps[0]" in f) for f in chain), chain)   # only the root's never-initialised pre-init sample (the bench's fabric)

    def test_session_chain_from_the_bench_has_zero_findings(self):
        """The `session` scenario: session open -> the init-only ROOT on genome 0 -> one candidate -> close, every record
        rebuilt from its sorted-JSON serialization, validated at all three layers and as a chain with NO finding. The
        bench's fabric starts at its INIT values for this scenario (the power-up state of a configured device, set on
        the fabric, not on a record), so the root's pre-init sample is a real sample and no model null is converted."""
        txs = rec.transactions(rec.load_trace(OUT / "session.jsonl"))
        self.assertEqual(len(txs), 2)
        root = roundtrip(rec.observation(txs[0], LINKS, TIMING, seq=1, session="bench", predecessor=ROOT, declared_stimulus=[{"kind": "init"}]))
        self.assertEqual(root["status"], "complete"); self.assertEqual(len(root["steps"]), 1); self.assertEqual(root["initial"]["q"], [1] * 8)
        self.assertFalse(root["init_event"]["parameters"]["pre_init_cleanup"])
        self.assertEqual(rec.validate_observation(root), [])
        rx = roundtrip(rec.transaction_close(txs[0], root, seq=1, links=LINKS))
        self.assertEqual(rx["status"], "closed"); self.assertEqual(rec.validate_close(rx, root), [])
        self.assertEqual(rx["cleanup"]["steps"][0]["edge"], None)                     # the init step leaves the clock low: no falling edge
        pred = {"kind": "closed", "seq": 1, "close_sha256": rec.sha256_json(rx)}
        cand = roundtrip(rec.observation(txs[1], LINKS, TIMING, seq=2, session="bench", predecessor=pred, declared_stimulus=self.stim[1]))
        self.assertEqual(cand["status"], "complete"); self.assertEqual(len(cand["steps"]), 8); self.assertEqual(rec.validate_observation(cand), [])
        cx = roundtrip(rec.transaction_close(txs[1], cand, seq=2, links=LINKS)); self.assertEqual(cx["status"], "closed")
        cf = roundtrip(rec.fitness(cand, TASK)); self.assertEqual(rec.validate_fitness(cf, cand), [])
        so = roundtrip(rec.session_open(INSTRUMENT, STARTUP, STARTUP))
        chain = [{"o": root, "x": rx, "ctx": ctx_for([{"kind": "init"}], None)},
                 {"o": cand, "x": cx, "f": cf, "ctx": ctx_for(self.stim[1], rec.sha256_json(rx))}]
        self.assertEqual(rec.validate_chain(so, chain), [])
        # the same chain is refused under a foreign session_open, a wrong X.seq, a wrong predecessor seq, a wrong fitness
        foreign = copy.deepcopy(so); foreign["instrument"]["carrier_sha256"] = _h("foreign")
        self.assertTrue(any("session_open.instrument" in m for m in rec.validate_chain(foreign, chain)))
        own_ref = rec.session_open(INSTRUMENT, _h("own"), _h("own"))
        self.assertTrue(any("pinned loaded-frame reference" in m for m in rec.validate_chain(own_ref, chain)))
        bad = copy.deepcopy(chain); bad[1]["x"]["seq"] = 999
        self.assertTrue(any("X.seq" in m for m in rec.validate_chain(so, bad)))
        bad = copy.deepcopy(chain); bad[1]["o"]["predecessor"]["seq"] = 999; bad[1]["x"]["observation_sha256"] = rec.observation_sha256(bad[1]["o"])
        self.assertTrue(any("predecessor.seq" in m for m in rec.validate_chain(so, bad)))
        bad = copy.deepcopy(chain); bad[1]["f"]["fitness"] = 999
        self.assertTrue(any("recomputed" in m for m in rec.validate_chain(so, bad)))

    def test_post_p6_fault_leaves_o_sealed_and_x_faulted(self):
        """The `post_fault` scenario (the owner's reproduction): a complete observation, then CLOSE before cleanup. The
        register file answers OKAY, the engine refuses (F_SEQUENCE). O built from the whole transaction is the O sealed at
        P6 (same digest, complete), and X is the faulted close with the real stop location (P7: cleanup not done)."""
        tx = rec.transactions(rec.load_trace(OUT / "post_fault.jsonl"))[1]
        cut = next(i for i, e in enumerate(tx) if e.get("mark") == "P6_sealed")
        o_full = rec.observation(tx, LINKS, TIMING, seq=2, session="bench", predecessor=ROOT, declared_stimulus=self.stim[1])
        o_p6 = rec.observation(tx[:cut], LINKS, TIMING, seq=2, session="bench", predecessor=ROOT, declared_stimulus=self.stim[1])
        self.assertEqual(o_full["status"], "complete"); self.assertEqual(len(o_full["steps"]), 8)
        self.assertEqual(rec.observation_sha256(o_full), rec.observation_sha256(o_p6))
        self.assertEqual(rec.validate_observation(o_full), [])
        x = rec.transaction_close(tx, o_full, seq=2, links=LINKS)
        self.assertEqual(x["status"], "faulted"); self.assertEqual(x["fault"], {"code": "sequence", "phase_reached": "P7"})
        self.assertNotIn("cleanup", x); self.assertEqual(rec.validate_close(x, o_full), [])
        with self.assertRaises(rec.RecordRefusal):
            rec.transaction_close(tx[:cut], o_p6, seq=2, links=LINKS)               # nothing after P6: not closed

    def test_x_cannot_be_sealed_before_close(self):
        tx = self.flow[1]
        cut = next(i for i, e in enumerate(tx) if e.get("op") == "wr" and e.get("addr") == rm.CTRL and e.get("data") == rm.ctrl_word("close"))
        o = rec.observation(tx[:cut], LINKS, TIMING, seq=2, session="bench", predecessor=ROOT, declared_stimulus=self.stim[1])
        with self.assertRaises(rec.RecordRefusal):
            rec.transaction_close(tx[:cut], o, seq=2, links=LINKS)


class ClosedSets(unittest.TestCase):
    def _o(self):
        stim = [{"kind": "init"}, {"kind": "set", "clock": 1, "ce": 255, "sr": 0, "d": 0x5A}]
        return {"schema": rec.SCHEMA_O, "schema_version": rec.VERSION, "instrument": dict(INSTRUMENT), "session": "s", "seq": 1, "nonce": LINKS["nonce"],
                "commit": _h("c"), "staging_readback_sha256": FRAMES, "fabric_readback_sha256_pre_event": FRAMES, "fabric_readback_sha256_post_event": FRAMES,
                "init_event": {"mechanism": "gsr_startupe2", "parameters": {"assert_delay": 8, "pulse_clocks": 2, "gsr_count_after": 1, "pre_init_cleanup": False}},
                "timing": {"settle": 4, "hold": 4, "release": 16, "sample_offset": 4}, "predecessor": dict(ROOT),
                "config": [0] * 21, "config_sha256": rec.sha256_json([0] * 21), "stimulus": stim, "stimulus_sha256": rec.sha256_json(stim),
                "elements": list(rec.ELEMENTS), "initial": {"context": "idle", "clock": 0, "ce": 0, "sr": 0, "d": 0, "q": [1] * 8},
                "steps": [{"step": 0, "kind": "init", "prev_event": "none", "clock_before": 0, "clock_after": 0, "edge": None, "ce": 0, "sr": 0, "d": 0, "q_before": [1] * 8, "q_after": [1] * 8},
                          {"step": 1, "kind": "set", "prev_event": "init", "clock_before": 0, "clock_after": 1, "edge": "rising", "ce": 255, "sr": 0, "d": 0x5A, "q_before": [1] * 8, "q_after": rec.bits(0x5A)}],
                "status": "complete"}

    def _x(self, o):
        return {"schema": rec.SCHEMA_X, "schema_version": rec.VERSION, "observation_sha256": rec.observation_sha256(o), "seq": 1,
                "cleanup": {"steps": [{"clock_before": 1, "clock_after": 0, "edge": "falling", "ce": 0, "sr": 0, "d": 0, "q_after": rec.bits(0x5A)}], "final_q": rec.bits(0x5A)},
                "base_readback_sha256": STARTUP, "base_state_sample": [1] * 8, "idle_status": 1, "status": "closed"}

    def test_valid_and_round_trip(self):
        o = self._o(); self.assertEqual(rec.validate_observation(o), [])
        self.assertEqual(rec.validate_observation(roundtrip(o)), [])
        x = self._x(o); self.assertEqual(rec.validate_close(x, o), []); self.assertEqual(rec.validate_close(roundtrip(x), o), [])
        self.assertEqual(rec.validate_bound(o, ctx_for(o["stimulus"], None, session="s"), None, x), [])

    def test_owner_counterexamples_are_refused(self):
        cases = {
            "nested_instrument_answer_bits": lambda o: o["instrument"].update(answer_bits=[1]),
            "nested_init_parameters_answer_bits": lambda o: o["init_event"]["parameters"].update(answer_bits=[1]),
            "wrong_instrument_variant": lambda o: o["instrument"].update(variant="42310001"),
            "empty_complete_steps": lambda o: o.update(steps=[]),
            "invalid_complete_preinit_sample": lambda o: (o["initial"].update(q=None), o["steps"][0].update(q_before=None)),
            "wrong_step_kind_and_timing": lambda o: (o["steps"][0].update(kind="nonsense"), o["timing"].update(settle=True)),
            "wrong_predecessor_shape": lambda o: o["predecessor"].update(seq="not-an-int", close_sha256="bad"),
            "null_cell": lambda o: o["steps"][1]["q_after"].__setitem__(3, None),
            "float_cell": lambda o: o["steps"][1]["q_after"].__setitem__(3, 1.0),
            "bool_cell": lambda o: o["steps"][1]["q_after"].__setitem__(3, True),
            "applied_not_declared": lambda o: o["steps"][1].update(d=0x5B),
            "non_uniform_applied_ce": lambda o: (o["steps"][1].update(ce=0x3C), o["stimulus"][1].update(ce=0x3C)),
            "broken_chain": lambda o: o["steps"][1].update(q_before=[0] * 8),
            "top_level_extra": lambda o: o.update(answer=1),
        }
        for name, mutate in cases.items():
            o = self._o(); mutate(o)
            if name == "wrong_instrument_variant":
                self.assertEqual(rec.validate_observation(o), [], name)                      # structurally fine...
                self.assertTrue(any("VARIANT" in f for f in rec.validate_bound(o, ctx_for(o["stimulus"], None, session="s"))), name)   # ...refused by the binding layer
            else:
                self.assertTrue(rec.validate_observation(o), name)

    def test_malformed_inputs_are_findings_not_exceptions(self):
        self.assertEqual(rec.validate_observation([]), ["O: not an object"])
        self.assertEqual(rec.validate_close("x", self._o()), ["X: not an object"])
        self.assertEqual(rec.validate_fitness(None, self._o()), ["F: not an object"])
        self.assertEqual(rec.validate_session_open(3), ["session_open: not an object"])
        self.assertTrue(rec.validate_observation({"status": "complete"}))

    def test_invalid_o_phase_table(self):
        o = self._o(); o["status"] = "invalid"; o["fault"] = {"code": "not_realisable", "phase_reached": "P3", "step_reached": 0}; o["steps"] = []
        self.assertTrue(any("extra keys" in f and "post_event" in f for f in rec.validate_observation(o)))
        o.pop("fabric_readback_sha256_post_event")
        self.assertEqual(rec.validate_observation(o), [])
        o.pop("fabric_readback_sha256_pre_event")                     # a completed phase's key missing
        self.assertTrue(any("missing keys" in f for f in rec.validate_observation(o)))

    def test_fitness_dimensions_and_types(self):
        o = self._o()
        with self.assertRaises(rec.RecordRefusal):
            rec.fitness(o, {"mask": [(1, 0), (1, 1)], "target": [1], "weights": [1], "digest": _h("t")})
        with self.assertRaises(rec.RecordRefusal):
            rec.fitness(o, {"mask": [(0, 0)], "target": [1], "weights": [1], "digest": _h("t")})        # step 0 is not scored
        fr = rec.fitness(o, {"mask": [(1, 1), (1, 0)], "target": [1, 1], "weights": [1, 1], "digest": _h("t")})
        self.assertEqual(fr["fitness"], 1)
        fr["fitness"] = True
        self.assertTrue(rec.validate_fitness(fr, o))
        o2 = self._o(); o2["status"] = "invalid"; o2["fault"] = {"code": "sequence", "phase_reached": "P5", "step_reached": 1}
        with self.assertRaises(rec.RecordRefusal):
            rec.fitness(o2, {"mask": [(1, 1)], "target": [1], "weights": [1], "digest": _h("t")})

    def test_x_rules(self):
        o = self._o(); x = self._x(o)
        bad = copy.deepcopy(x); bad["cleanup"]["final_q"] = [None] * 8; bad["base_state_sample"] = [None] * 8; bad["idle_status"] = 0; bad["cleanup"]["answer_bits"] = [1]
        f = rec.validate_close(bad, o)
        self.assertTrue(any("final_q" in m for m in f) and any("base_state_sample" in m for m in f) and any("answer_bits" in m for m in f), f)
        nonidle = copy.deepcopy(x); nonidle["idle_status"] = 0
        self.assertTrue(any("ends idle" in m for m in rec.validate_close(nonidle, o)))
        faulted = {"schema": rec.SCHEMA_X, "schema_version": rec.VERSION, "observation_sha256": rec.observation_sha256(o), "seq": 1, "idle_status": 0,
                   "fault": {"code": "sequence", "phase_reached": "P9"}, "status": "faulted"}
        self.assertEqual(rec.validate_close(faulted, o), [])
        self.assertTrue(rec.validate_close(roundtrip(faulted), o) == [])

    def test_session_open_strict(self):
        so = rec.session_open(INSTRUMENT, _h("x"), _h("x")); self.assertEqual(so["status"], "open"); self.assertEqual(rec.validate_session_open(so), [])
        so = rec.session_open(INSTRUMENT, _h("x"), _h("y")); self.assertEqual(so["status"], "refused")
        so = rec.session_open({}, None, None); self.assertEqual(so["status"], "refused"); self.assertTrue(rec.validate_session_open(so))
        so = rec.session_open(INSTRUMENT, _h("x"), _h("y")); so["status"] = "open"; self.assertTrue(rec.validate_session_open(so))

    def test_round3_rules(self):
        o = self._o(); x = self._x(o)
        bad = copy.deepcopy(x); bad["seq"] = 999
        self.assertTrue(any("X.seq" in m for m in rec.validate_close(bad, o)))
        bad = copy.deepcopy(x); bad["cleanup"]["steps"][0].update(clock_before=0, edge=None)            # O's final clock is 1
        f = rec.validate_close(bad, o); self.assertTrue(any("final clock" in m for m in f) and any("edge" in m for m in f), f)
        bad = copy.deepcopy(x); bad["cleanup"]["steps"][0].update(ce=False, sr=0.0, d=False, clock_after=0.0)
        self.assertEqual(len([m for m in rec.validate_close(bad, o) if "bad value" in m]), 4)
        # pre_init_cleanup is a witness of the held-input context, not a free bit
        held = self._o(); held["initial"].update(context="a5_injection", clock=1, ce=1); held["steps"][0]["clock_before"] = 1
        self.assertTrue(any("pre_init_cleanup" in m for m in rec.validate_observation(held)))
        held["init_event"]["parameters"]["pre_init_cleanup"] = True
        self.assertEqual([m for m in rec.validate_observation(held) if "pre_init_cleanup" in m], [])
        idle = self._o(); idle["init_event"]["parameters"]["pre_init_cleanup"] = True
        self.assertTrue(any("pre_init_cleanup" in m for m in rec.validate_observation(idle)))
        # the phase table governs the acquisitions, not only the readback keys
        p2 = self._o(); p2.update(status="invalid", fault={"code": "sequence", "phase_reached": "P2", "step_reached": None}); p2.pop("initial"); p2.pop("fabric_readback_sha256_post_event")
        self.assertTrue(any("stop in P2" in m for m in rec.validate_observation(p2)))
        p2["steps"] = []; self.assertEqual(rec.validate_observation(p2), [])
        p4 = self._o(); p4.update(status="invalid", fault={"code": "sequence", "phase_reached": "P4", "step_reached": None}); p4.pop("fabric_readback_sha256_post_event")
        self.assertTrue(any("stop in P4" in m for m in rec.validate_observation(p4)))
        # a malformed chain entry is a finding, never an exception; the session is bound to the trusted context
        so = rec.session_open(INSTRUMENT, STARTUP, STARTUP); ctx = ctx_for(o["stimulus"], None, session="s")
        self.assertTrue(any("record entry" in m for m in rec.validate_chain(so, [{"o": [], "x": x, "ctx": ctx}])))
        self.assertEqual(rec.validate_chain(so, "records"), ["chain: records is not a list"])
        foreign = rec.session_open({**INSTRUMENT, "carrier_sha256": _h("foreign")}, _h("own"), _h("own"))
        f = rec.validate_chain(foreign, [{"o": o, "x": x, "ctx": ctx}])
        self.assertTrue(any("session_open.instrument" in m for m in f) and any("pinned loaded-frame reference" in m for m in f), f)
        # F is recomputed over the full grid from the TRUSTED task: an arbitrary score with the right digest is refused
        task = {"mask": [(1, 1), (1, 0)], "target": [1, 1], "weights": [1, 1], "digest": _h("task")}
        fr = rec.fitness(o, task); tctx = {**ctx, "task": task}
        self.assertEqual(rec.validate_bound(o, tctx, fr, x), [])
        fr["fitness"] = 999
        self.assertTrue(any("recomputed" in m for m in rec.validate_bound(o, tctx, fr, x)))
        self.assertTrue(any("no trusted task" in m for m in rec.validate_bound(o, {k: v for k, v in ctx.items() if k != "task"}, fr, x)))

    def test_binding_frame_invariance_and_task(self):
        o = self._o(); o["fabric_readback_sha256_post_event"] = _h("other")
        self.assertTrue(any("frame invariance" in m for m in rec.validate_bound(o, ctx_for(o["stimulus"], None, session="s"))))
        o = self._o(); fr = rec.fitness(o, {"mask": [(1, 1)], "target": [1], "weights": [1], "digest": _h("other-task")})
        self.assertTrue(any("task_digest" in m for m in rec.validate_bound(o, ctx_for(o["stimulus"], None, session="s"), fr)))


if __name__ == "__main__":
    unittest.main()

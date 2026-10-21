"""The O / F / X / session_open records built from the bench's own register traces (sim/b4/out/*.jsonl, written by
tb_b4_core) and validated against the contract's closed sets — the host side of the flow the carrier v2 unit was
asked to complete. The links the instrument's PCAP path would supply are symbolic here (the bench drives no PCAP)."""
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


LINKS = {"instrument": {"variant": f"{rm.VARIANT_WORD:08x}", "carrier_sha256": _h("carrier"), "image_sha256": _h("image")},
         "nonce": _h("nonce")[:16], "commit": _h("commit"), "staging_readback_sha256": _h("staging"),
         "fabric_readback_sha256_pre_event": _h("pre"), "fabric_readback_sha256_post_event": _h("post"),
         "config": [0] * 21, "base_readback_sha256": _h("base"), "base_state_sample": [1] * 8}
TIMING = rm.decode_timing(rm.timing_word(8, 16, 4, 4, 4))
ROOT = {"kind": "session_root", "seq": None, "close_sha256": None}


def ensure_traces():
    if not (OUT / "flow.jsonl").is_file():
        subprocess.run(["bash", str(R / "sim/b4/run.sh")], capture_output=True, text=True, timeout=900, check=True)


@unittest.skipUnless(HAVE_SIM, "iverilog or the instrument absent")
class FromTheBench(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_traces()
        cls.flow = rec.transactions(rec.load_trace(OUT / "flow.jsonl"))

    def test_six_transactions_four_validate_two_carry_the_models_null(self):
        """Fixtures 0-3 are flip-flop genomes: every cell a value, the records validate. Fixtures 4-5 are latch
        genomes: the bench's fabric (the hypothesis model) drives x on the x5FF elements, which reaches the record as
        null — and the CARRIER validator refuses it, because on silicon a carrier samples a physical value there
        (contract 3.4, D1). The refusal is the D1 rule seen from the bench, not a carrier defect."""
        self.assertEqual(len(self.flow), 6)
        pred = ROOT
        for i, evs in enumerate(self.flow, start=1):
            o = rec.observation(evs, LINKS, TIMING, seq=i, session="bench", predecessor=pred)
            self.assertEqual(o["status"], "complete", i)
            findings = rec.validate_observation(o)
            if i == 1:
                # the first transaction's pre-init sample is the model's never-initialised fabric (x): the carrier
                # validator refuses the null, and nothing else — on silicon a physical value would be there
                self.assertTrue(findings and all(f.startswith("initial.q") and "null" in f for f in findings), (i, findings))
            elif i <= 4:
                self.assertEqual(findings, [], i)
            else:
                self.assertTrue(findings and all("null" in f for f in findings), (i, findings))
                continue
            self.assertEqual(len(o["steps"]), 8)                       # the init step and seven set steps
            self.assertTrue(all(len(s["q_after"]) == 8 for s in o["steps"]))
            self.assertEqual(o["init_event"]["parameters"]["gsr_count_after"], i)
            x = rec.transaction_close(evs, o, seq=i, links=LINKS)
            self.assertEqual(x["status"], "closed"); self.assertEqual(rec.validate_close(x, o), [], i)
            mask = [(s, e) for s in range(1, 8) for e in range(8)]
            f = rec.fitness(o, task_digest=_h("task"), mask=mask, target=[0] * 56, weights=[1] * 56)
            self.assertEqual(rec.validate_fitness(f, o), [])
            self.assertEqual(f["fitness"], sum(1 for s in o["steps"][1:] for c in s["q_after"] if c == 0))
            pred = {"kind": "closed", "seq": i, "close_sha256": rec.sha256_json(x)}

    def test_the_first_transactions_initial_q_is_the_never_initialised_fabric(self):
        o = rec.observation(self.flow[0], LINKS, TIMING, seq=1, session="bench", predecessor=ROOT)
        self.assertEqual(o["initial"]["q"], [None] * 8)   # the bench's model has no value before its first init event (x)
        o2 = rec.observation(self.flow[1], LINKS, TIMING, seq=2, session="bench", predecessor=ROOT)
        self.assertTrue(all(c in (0, 1) for c in o2["initial"]["q"]))   # from the second transaction on, the previous base state

    def test_a_non_uniform_ce_stop_yields_an_invalid_o_with_the_prefix(self):
        evs = rec.load_trace(OUT / "fault_realisable.jsonl")
        o = rec.observation(evs, LINKS, TIMING, seq=1, session="bench", predecessor=ROOT)
        self.assertEqual(o["status"], "invalid")
        self.assertEqual(o["fault"], {"code": "not_realisable", "phase_reached": "P5", "step_reached": 2})
        self.assertEqual(len(o["steps"]), 3)
        findings = rec.validate_observation(o)
        self.assertTrue(all(f.startswith("initial.q") for f in findings), findings)   # a first transaction: the model's x pre-init sample only
        with self.assertRaises(rec.RecordRefusal):
            rec.fitness(o, _h("task"), [], [], [])

    def test_a5_injection_open_then_the_held_context(self):
        trace = rec.load_trace(OUT / "a5.jsonl")
        marks = [e.get("mark") for e in trace]
        self.assertIn("J2_begin", marks); self.assertIn("J3_begin", marks)
        j2 = trace[marks.index("J2_begin"):marks.index("J2_end")]
        j3 = trace[marks.index("J3_begin"):marks.index("J3_end")]
        o2 = rec.observation(j2, LINKS, TIMING, seq=2, session="bench", predecessor={"kind": "closed", "seq": 1, "close_sha256": _h("x1")})
        x2 = rec.transaction_close(j2, o2, seq=2, links=LINKS)
        self.assertEqual(x2["status"], "injection_open"); self.assertEqual(rec.validate_close(x2, o2), [])
        o3 = rec.observation(j3, LINKS, TIMING, seq=3, session="bench", predecessor={"kind": "a5_injection", "seq": 2, "close_sha256": rec.sha256_json(x2)}, context="a5_injection")
        self.assertEqual(o3["initial"]["context"], "a5_injection")
        self.assertEqual((o3["initial"]["clock"], o3["initial"]["ce"], o3["initial"]["d"]), (1, 1, 0))
        self.assertEqual(o3["initial"]["q"], [0] * 8)                     # the injection arrived
        self.assertEqual(o3["steps"][0]["q_after"], [1] * 8)              # and was cleared by the event
        self.assertEqual(rec.validate_observation(o3), [])
        bad = copy.deepcopy(o3); bad["initial"]["context"] = "idle"
        self.assertTrue(any("inputs at 0" in f for f in rec.validate_observation(bad)))


class ClosedSets(unittest.TestCase):
    def _o(self):
        ensure = {"instrument": LINKS["instrument"], "session": "s", "seq": 1, "nonce": LINKS["nonce"], "commit": _h("c"),
                  "staging_readback_sha256": _h("s"), "fabric_readback_sha256_pre_event": _h("a"), "fabric_readback_sha256_post_event": _h("b"),
                  "init_event": {"mechanism": "gsr_startupe2", "parameters": {}}, "timing": {"settle": 4, "hold": 4, "release": 16, "sample_offset": 4},
                  "predecessor": ROOT, "config": [0] * 21, "config_sha256": rec.sha256_json([0] * 21),
                  "stimulus": [{"kind": "init"}], "stimulus_sha256": rec.sha256_json([{"kind": "init"}]), "elements": list(rec.ELEMENTS),
                  "initial": {"context": "idle", "clock": 0, "ce": 0, "sr": 0, "d": 0, "q": [1] * 8},
                  "steps": [{"step": 0, "kind": "init", "prev_event": "none", "clock_before": 0, "clock_after": 0, "edge": None, "ce": 0, "sr": 0, "d": 0, "q_before": [1] * 8, "q_after": [1] * 8}],
                  "status": "complete", "schema": rec.SCHEMA_O, "schema_version": rec.VERSION}
        return ensure

    def test_a_valid_minimal_o(self):
        self.assertEqual(rec.validate_observation(self._o()), [])

    def test_an_extra_key_is_refused_by_closure(self):
        o = self._o(); o["answer_bits"] = [1, 0]
        self.assertTrue(any("extra ['answer_bits']" in f for f in rec.validate_observation(o)))

    def test_a_null_or_float_cell_is_refused(self):
        o = self._o(); o["steps"][0]["q_after"][3] = None
        self.assertTrue(any("null" in f for f in rec.validate_observation(o)))
        o = self._o(); o["steps"][0]["q_after"][3] = 1.0
        self.assertTrue(any("q_after" in f for f in rec.validate_observation(o)))

    def test_a_deny_listed_key_is_refused(self):
        o = self._o(); o["init_event"]["parameters"]["expected"] = 1
        self.assertTrue(any("deny-listed" in f for f in rec.validate_observation(o)))

    def test_an_invalid_o_may_not_carry_a_later_phase(self):
        o = self._o(); o["status"] = "invalid"; o["fault"] = {"code": "not_realisable", "phase_reached": "P3", "step_reached": 0}
        self.assertTrue(any("later phase" in f for f in rec.validate_observation(o)))
        o.pop("fabric_readback_sha256_post_event")
        self.assertEqual(rec.validate_observation(o), [])

    def test_session_open(self):
        so = rec.session_open(LINKS["instrument"], _h("x"), _h("x")); self.assertEqual(so["status"], "open"); self.assertEqual(rec.validate_session_open(so), [])
        so = rec.session_open(LINKS["instrument"], _h("x"), _h("y")); self.assertEqual(so["status"], "refused")
        so["status"] = "open"; self.assertTrue(rec.validate_session_open(so))


if __name__ == "__main__":
    unittest.main()

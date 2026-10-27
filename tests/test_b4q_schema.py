"""B4Q — the explicit schema files (b4q/schemas) held to the code validators of host/b4carrier_records.py: every record of the
bench's own register traces and of an offline session validates under both; the owner's counterexamples and tampers (an extra
key at every level, a null cell, a float cell, a missing header field, a value of a later phase on an invalid O, a non-idle
closed X, a boolean fitness, a wrong phase set) are refused by BOTH — the schema file is the reviewable artefact, the code
validator the authority (contract 4.3); a disagreement is a finding against the file. The subset validator itself refuses a
file with a keyword it does not interpret."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
sys.path.insert(0, str(R / "tests"))
import b4carrier_records as rec  # noqa: E402
import b4q_schema as sc  # noqa: E402

SMOKE = R / "build/b4q_e2e/valid"


def records_of(d: Path):
    out = []
    for td in sorted(p for p in d.iterdir() if p.is_dir() and p.name.startswith("tx_")):
        o = json.loads((td / "o.json").read_text()) if (td / "o.json").is_file() else None
        f = json.loads((td / "f.json").read_text()) if (td / "f.json").is_file() else None
        x = json.loads((td / "x.json").read_text()) if (td / "x.json").is_file() else None
        out.append((td.name, o, f, x))
    return out


class Files(unittest.TestCase):
    def test_every_file_loads_and_uses_the_subset_only(self):
        for n in sc.NAMES:
            d = sc.load(n)
            self.assertIn("$id", d); self.assertEqual(d["$id"], f"{n}.schema.json")
        with self.assertRaises(sc.SchemaRefusal):
            sc._check_keywords({"type": "object", "patternProperties": {}}, "x")

    def test_the_subset_validator_itself(self):
        s = {"type": "object", "additionalProperties": False, "required": ["a"], "properties": {"a": {"type": "integer", "minimum": 0, "maximum": 1}, "b": {"enum": ["x", None]}}}
        self.assertEqual(sc.validate({"a": 1, "b": None}, s), [])
        self.assertTrue(sc.validate({"a": 2}, s)); self.assertTrue(sc.validate({"a": True}, s)); self.assertTrue(sc.validate({"a": 1, "c": 0}, s)); self.assertTrue(sc.validate({}, s))
        self.assertTrue(sc.validate({"a": 1.0}, s))                      # type-exact: 1.0 is not an integer


class AgainstTheCodeValidators(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import b4q_fixture
        b4q_fixture.ensure(SMOKE)
        cls.recs = records_of(SMOKE)
        cls.so = json.loads((SMOKE / "session_open.json").read_text())["record"]

    def agree(self, doc, name, code_findings, what):
        sf = sc.validate_named(doc, name)
        self.assertEqual(bool(sf), bool(code_findings), (what, sf[:3], code_findings[:3]))
        return sf

    def test_session_records_valid_under_both(self):
        self.assertEqual(self.agree(self.so, "ff_session_open_v1", rec.validate_session_open(self.so), "session_open"), [])
        n = 0
        for name, o, f, x in self.recs:
            self.assertEqual(self.agree(o, "ff_observation_carrier_v1", rec.validate_observation(o), name), [])
            if f is not None:
                self.assertEqual(self.agree(f, "ff_fitness_v1", rec.validate_fitness(f, o), name), [])
            self.assertEqual(self.agree(x, "ff_transaction_close_v1", rec.validate_close(x, o), name), [])
            n += 1
        self.assertGreaterEqual(n, 4)

    def test_tampers_refused_by_both(self):
        name, o, f, x = [r for r in self.recs if r[2] is not None][0]
        cases = []
        t = copy.deepcopy(o); t["answer_bits"] = [1]; cases.append(("extra top key", t, "O"))
        t = copy.deepcopy(o); t["steps"][1]["extra"] = 1; cases.append(("extra step key", t, "O"))
        t = copy.deepcopy(o); t["instrument"]["answer"] = "x"; cases.append(("extra instrument key", t, "O"))
        t = copy.deepcopy(o); t["steps"][1]["q_after"][3] = None; cases.append(("null cell", t, "O"))
        t = copy.deepcopy(o); t["steps"][1]["q_after"][3] = 1.0; cases.append(("float cell", t, "O"))
        t = copy.deepcopy(o); del t["nonce"]; cases.append(("missing header field", t, "O"))
        t = copy.deepcopy(o); t["status"] = "invalid"; t["fault"] = {"code": "sequence", "phase_reached": "P2", "step_reached": None}; cases.append(("an invalid O carrying P3+ fields", t, "O"))
        t = copy.deepcopy(o); t["config"] = t["config"][:20]; cases.append(("20 config bits", t, "O"))
        t = copy.deepcopy(o); t["init_event"]["mechanism"] = "pcap_write"; cases.append(("unknown mechanism", t, "O"))
        t = copy.deepcopy(f); t["fitness"] = True; cases.append(("boolean fitness", t, "F"))
        t = copy.deepcopy(f); t["observation_sha256"] = "0" * 63; cases.append(("short digest", t, "F"))
        t = copy.deepcopy(x); t["idle_status"] = 0; cases.append(("non-idle closed X (code: a binding rule; file: idle_status 0 is a legal bit)", t, "X-code-only"))
        t = copy.deepcopy(x); t["status"] = "injection_open"; cases.append(("injection_open with the closed fields", t, "X"))
        t = copy.deepcopy(x); t["cleanup"]["steps"][0]["clock_after"] = 1; cases.append(("cleanup not ending low", t, "X"))
        t = copy.deepcopy(x); t["base_state_sample"] = [0] * 7; cases.append(("seven cells", t, "X"))
        for what, doc, kind in cases:
            if kind == "O":
                self.assertTrue(self.agree(doc, "ff_observation_carrier_v1", rec.validate_observation(doc), what), what)
            elif kind == "F":
                self.assertTrue(self.agree(doc, "ff_fitness_v1", rec.validate_fitness(doc, o), what), what)
            elif kind == "X":
                self.assertTrue(self.agree(doc, "ff_transaction_close_v1", rec.validate_close(doc, o), what), what)
            else:
                self.assertTrue(rec.validate_close(doc, o), what)        # the semantic rule lives in the code validator only; the file does not claim it
        t = copy.deepcopy(self.so); t["status"] = "maybe"
        self.assertTrue(self.agree(t, "ff_session_open_v1", rec.validate_session_open(t), "session_open status"))

    def test_the_bench_traces_records_validate_when_present(self):
        out = R / "sim/b4/out"
        if not (out / "flow.jsonl").is_file():
            self.skipTest("the carrier bench's traces are not generated here (tests/test_b4carrier_records.py regenerates them)")
        import re
        import b4carrier_regmap as rm
        text = (R / "tb/b4/b4_fixture.vh").read_text()
        stims = []
        for k in range(6):
            steps = [{"kind": "init"}]
            for j in range(7):
                w = int(text.split(f"FIX{k}_IN{j} = 25'h")[1].split(";")[0], 16); a = rm.decode_applied(w)
                steps.append({"kind": "set", "clock": a["clock"], "ce": a["ce"], "sr": a["sr"], "d": a["d"]})
            stims.append(steps)
        import hashlib
        h = lambda s: hashlib.sha256(s.encode()).hexdigest()
        links = {"instrument": {"variant": f"{rm.VARIANT_WORD:08x}", "carrier_sha256": h("c"), "image_sha256": h("i")}, "nonce": h("n")[:16], "commit": h("k"), "staging_readback_sha256": h("f"),
                 "fabric_readback_sha256_pre_event": h("f"), "fabric_readback_sha256_post_event": h("f"), "config": [0] * 21, "base_readback_sha256": h("b")}
        timing = {**rm.decode_timing(rm.timing_word(8, 16, 4, 4, 4)), "pulse": 2}
        flow = rec.transactions(rec.load_trace(out / "flow.jsonl"))
        for i, evs in enumerate(flow[1:4], start=2):
            o = rec.observation(evs, links, timing, seq=i, session="bench", predecessor={"kind": "closed", "seq": i - 1, "close_sha256": h("x")}, declared_stimulus=stims[i - 1])
            self.assertEqual(sc.validate_named(o, "ff_observation_carrier_v1"), [], i)


if __name__ == "__main__":
    unittest.main()

"""B4Q — the adapters of contract 3.1 / 3.2 (host/b4q_view.py) on the retained representations of record: an M-target record
and an M-ledger entry of the committed b4-sim-5 archive, the M-memo counterexample of contract 3.4 (b4-sim-4 pair_000 k10.json
id 20: 36 null cells), an M-raw return produced by the model itself, and a C-O of an offline session; every view validates
under its schema; a digest verified only under its representation's declared encoding; the source taken from the trusted
context (a record offered under the wrong branch, a descriptor that is not the trusted source, or a stimulus the digest does
not bind is refused by name). Read-only over evidence/."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "host", R / "b4/host"):
    sys.path.insert(0, str(p))
import b4q_schema as sc  # noqa: E402
import b4q_view as vw  # noqa: E402
import b4_execution as ex  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402

A5 = R / "evidence/b4/sim/b4-sim-5_20261027T170605Z/pair_000"
A4 = R / "evidence/b4/sim/b4-sim-4_20261021T065339Z/pair_000"
SMOKE = R / "build/b4q_e2e/valid"


class Adapters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = bm.site_mapping(); cls.addr = tuple(cls.m.addresses)
        cls.t5 = json.loads((A5 / "target_search.json").read_text()); cls.task5 = json.loads((A5 / "task.json").read_text())["public_task"]
        cls.src5 = cls.t5["provenance"]
        if not SMOKE.is_dir():
            subprocess.run([sys.executable, "-B", str(R / "host/b4q_e2e.py"), str(SMOKE.parent), "valid"], check=True, capture_output=True)

    def ctx(self, rep, stim=None, src=None):
        return {"representation": rep, "source": src or self.src5, "addresses": self.addr, "stimulus": stim if stim is not None else self.task5["stimulus"]}

    def test_m_target_and_m_ledger_of_the_sim5_archive(self):
        v = vw.view(self.t5, self.ctx("M-target"))
        self.assertEqual(sc.validate_named(v, "ff_observation_view_v1"), [])
        self.assertEqual((v["source"], v["genome"]["kind"], v["stimulus"]["kind"], v["record_sha256"]["kind"], v["provenance"]["kind"]), ({"kind": "model", "representation": "M-target"}, "R", "A", "A", "R"))
        self.assertEqual(v["config_sha256_raw"]["value"]["encoding"], "proj-dict-canonical")
        self.assertEqual(v["q_grid_sha256"], {"kind": "R", "value": self.t5["trace_sha256"]})
        self.assertTrue(all(s["derived_keys"] for s in v["steps"]["value"]))      # every key but q_after derived
        self.assertEqual(vw.unmodelled_cells(v), 0)
        led = json.loads((A5 / "arm_O.result.json").read_text())["result"]["ledger"][0]
        v2 = vw.view(led, self.ctx("M-ledger"))
        self.assertEqual(sc.validate_named(v2, "ff_observation_view_v1"), [])
        self.assertEqual(v2["provenance"]["kind"], "A"); self.assertEqual(v2["genome"]["value"], led["genome"])

    def test_m_memo_counterexample_of_contract_3_4(self):
        k10 = json.loads((A4 / "k10.json").read_text()); obs = [o for o in k10["observations"] if o["id"] == 20][0]
        task4 = json.loads((A4 / "task.json").read_text())["public_task"]; src4 = json.loads((A4 / "target_search.json").read_text())["provenance"]
        v = vw.view(obs, {"representation": "M-memo", "source": src4, "addresses": self.addr, "stimulus": task4["stimulus"]})
        self.assertEqual(sc.validate_named(v, "ff_observation_view_v1"), [])
        self.assertEqual(vw.unmodelled_cells(v), 36)                               # the latch configuration: the x5FF columns null at every step
        self.assertEqual(v["genome"]["value"], 1024)

    def test_m_raw_from_the_model(self):
        hyp = hy.load(); fab = fm.Fabric(self.m, hyp)
        trace = fab.observe(fab.config_from_genome(0x18), self.task5["stimulus"])
        self.assertEqual(sc.validate_named(trace, "ff_observation_model_raw_v1"), [])
        src = {"hypothesis": trace["hypothesis"], "mapping": trace["mapping"], "fabric": trace["fabric"]}
        v = vw.view(trace, self.ctx("M-raw", src=src))
        self.assertEqual(sc.validate_named(v, "ff_observation_view_v1"), [])
        self.assertEqual(v["config_sha256_raw"]["value"]["encoding"], "raw-dict-default")
        self.assertEqual(v["genome"], {"kind": "D", "value": 0x18}); self.assertEqual(v["stimulus"]["kind"], "R")
        bad = copy.deepcopy(trace); bad["config_sha256"] = ex.sha256_json(trace["config"])      # the canonical digest is NOT the raw representation's
        with self.assertRaises(vw.ViewRefusal):
            vw.view(bad, self.ctx("M-raw", src=src))

    def test_c_o_of_a_session(self):
        o = json.loads((SMOKE / "tx_002/o.json").read_text())
        v = vw.view(o, {"representation": "C-O", "instrument": o["instrument"]})
        self.assertEqual(sc.validate_named(v, "ff_observation_view_v1"), [])
        self.assertEqual((v["config_vector"]["kind"], v["stimulus"]["kind"], v["record_sha256"]["kind"], v["q_grid_sha256"]["kind"]), ("R", "R", "R", "D"))
        self.assertEqual(v["config_sha256_raw"]["value"]["encoding"], "list-canonical")
        with self.assertRaises(vw.ViewRefusal):
            vw.view(o, {"representation": "C-O", "instrument": {**o["instrument"], "image_sha256": "0" * 64}})

    def test_refusals_by_name(self):
        o = json.loads((SMOKE / "tx_002/o.json").read_text())
        with self.assertRaises(vw.ViewRefusal):
            vw.view(o, self.ctx("M-target"))                                       # a carrier record under the model branch
        with self.assertRaises(vw.ViewRefusal):
            vw.view(self.t5, {"representation": "C-O", "instrument": o["instrument"]})
        with self.assertRaises(vw.ViewRefusal):
            vw.view(self.t5, self.ctx("M-target", stim=self.task5["holdout_stimulus"]))   # not the stimulus the digest binds
        other = copy.deepcopy(self.src5); other["fabric"]["kind"] = "permuted"
        with self.assertRaises(vw.ViewRefusal):
            vw.view(self.t5, self.ctx("M-target", src=other))                      # not the trusted source
        with self.assertRaises(vw.ViewRefusal):
            vw.view(self.t5, {**self.ctx("M-target"), "representation": "M-nonsense"})
        t = copy.deepcopy(self.t5); t["trace_sha256"] = "0" * 64
        with self.assertRaises(vw.ViewRefusal):
            vw.view(t, self.ctx("M-target"))


if __name__ == "__main__":
    unittest.main()

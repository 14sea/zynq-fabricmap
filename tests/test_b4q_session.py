"""B4Q — the offline end-to-end (host/b4q_e2e.py) in a hermetic root and its fresh-process verification (host/b4q_verify.py):
the valid paths (session open / root / normal P1–P10 / A5 J1–J3 / the A8-style cross / the A2 pairs) verify with empty findings
and the executing side's fitness equals the host's; the negatives are NAMED (an invalid O at P5 with not_realisable and no X,
an invalid O at P1 with arm_auth, no O for a notary refusal / a stopped DMA / an interruption, a refused carrier record for the
unmodelled latch endpoint, the A5 fail data on the persisting fabric); the verifier and the session agree on every scenario;
the A5 / A8 / A2 readings are the contract's. No production registry, seed or board is touched."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b4q_verify as vf  # noqa: E402

_STATE: dict = {}


def setUpModule():
    p = subprocess.run(["bash", str(R / "firmware/b4q/build.sh")], capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(p.stdout + p.stderr)
    root = Path(tempfile.mkdtemp(prefix="b4q_e2e_"))
    p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_e2e.py"), str(root)], capture_output=True, text=True, timeout=900)
    if p.returncode != 0:
        raise AssertionError(p.stdout[-3000:] + p.stderr[-3000:])
    _STATE["root"] = root
    _STATE["summary"] = {s["name"]: s for s in json.loads((root / "e2e_summary.json").read_text())}
    _STATE["verify"] = {}
    for name in _STATE["summary"]:
        q = subprocess.run([sys.executable, "-B", str(R / "host/b4q_verify.py"), str(root / name), "--json", str(root / name / "verify.json")], capture_output=True, text=True, timeout=600)
        _STATE["verify"][name] = (q.returncode, json.loads((root / name / "verify.json").read_text()))


class EndToEnd(unittest.TestCase):
    def rep(self, name):
        return _STATE["verify"][name][1]

    def test_every_scenario_verifies_in_agreement_with_the_session(self):
        for name, (rc, rep) in _STATE["verify"].items():
            self.assertTrue(rep["agree"], (name, rep["session"], [(t["dir"], t.get("only_here"), t.get("only_stored")) for t in rep["transactions"] if not t["agrees"]]))
            self.assertEqual(rc, 0, name)
            self.assertEqual(rep["a7"]["findings"], [], name)

    def test_valid_paths_clean(self):
        for name in ("valid", "a5", "a5_persist", "a8_cross"):
            rep = self.rep(name)
            self.assertTrue(rep["clean"], (name, rep["session"], [t["findings"] for t in rep["transactions"]]))
            for t in rep["transactions"]:
                self.assertEqual(t["findings"], [], (name, t["dir"]))
        s = _STATE["summary"]["valid"]
        self.assertEqual([r["x"] for r in s["records"]], ["closed"] * 4)
        self.assertEqual([r["o_status"] for r in s["records"]], ["complete"] * 4)
        self.assertEqual([r["f"] for r in s["records"]], [False, True, True, True])
        for td in sorted((_STATE["root"] / "valid").glob("tx_00[234]")):
            fw = json.loads((td / "firmware_result.json").read_text()); f = json.loads((td / "f.json").read_text())
            self.assertEqual((fw["has_fitness"], fw["fitness"], fw["task_digest"]), (1, f["fitness"], f["task_digest"]), td.name)

    def test_a5_protocol_pass_and_fail_data(self):
        self.assertEqual(_STATE["summary"]["a5"]["a5"], "pass")
        self.assertEqual([r["x"] for r in _STATE["summary"]["a5"]["records"]], ["closed", "closed", "injection_open", "closed", "closed"])
        v = json.loads((_STATE["root"] / "a5/a5_verdict.json").read_text())
        self.assertTrue(v["injection_witness"]["arrived"]); self.assertEqual(v["differing_positions"], [])
        self.assertEqual(_STATE["summary"]["a5_persist"]["a5"], "fail")
        v2 = json.loads((_STATE["root"] / "a5_persist/a5_verdict.json").read_text())
        self.assertTrue(v2["injection_witness"]["arrived"]); self.assertTrue(v2["differing_positions"])
        o3 = json.loads((_STATE["root"] / "a5/tx_004/o.json").read_text())
        self.assertEqual(o3["predecessor"]["kind"], "a5_injection"); self.assertEqual(o3["initial"]["context"], "a5_injection")
        self.assertTrue(o3["init_event"]["parameters"]["pre_init_cleanup"])

    def test_a8_cross_and_a2_rows(self):
        self.assertEqual(_STATE["summary"]["a8_cross"]["a8_AFF"], "both demonstrated")
        self.assertEqual(_STATE["summary"]["a8_cross"]["a8_BFF"], "neither demonstrated")
        cross = json.loads((_STATE["root"] / "a8_cross/a8_cross.json").read_text())
        self.assertEqual(cross["AFF"]["row"], 2); self.assertTrue(all(cross["AFF"]["sr_readings"][c]["reading"] == "restore" for c in ("00", "01", "10", "11")))
        self.assertEqual(_STATE["summary"]["a2_pairs"]["a2"], {"ce_mode": "differs", "storage_kind": "not_assessable"})
        rep = self.rep("a2_pairs")
        self.assertTrue(any("bad value" in m for m in rep["transactions"][4]["findings"]))        # the latch endpoint: None cells refused (the emulation's limit)

    def test_negatives_named(self):
        s = _STATE["summary"]
        self.assertEqual((s["not_realisable"]["invalid_phase"], s["not_realisable"]["invalid_code"], s["not_realisable"]["after_status"]), ("P5", "not_realisable", 1))
        rep = self.rep("not_realisable")
        self.assertIn("O invalid at P5 (not_realisable); no X", rep["transactions"][1]["outcome"])
        self.assertEqual((s["wrong_key"]["o_status"], s["wrong_key"]["o_phase"]), ("invalid", "P1"))
        self.assertIn("arm_auth", self.rep("wrong_key")["transactions"][0]["outcome"])
        for name in ("notary_refuses", "dma_never", "interrupt"):
            self.assertFalse(s[name]["o"], name)
            self.assertTrue(any("no observation sealed" in m for m in s[name]["findings"]), name)
            self.assertIn("no observation sealed", self.rep(name)["transactions"][1]["outcome"])
        self.assertEqual(s["dma_never"]["phase"], "P2"); self.assertIn("D_P_DONE never", s["dma_never"]["reason"])
        self.assertEqual(s["interrupt"]["status"], 5); self.assertEqual(s["interrupt"]["interrupted"]["after_accesses"], 3000)
        self.assertGreater(s["latch_unmodelled"]["unmodelled_reads"], 0)
        self.assertTrue(any("bad value" in m for m in s["latch_unmodelled"]["findings"]))

    def test_tampered_evidence_is_found(self):
        import shutil
        src = _STATE["root"] / "valid"; dst = _STATE["root"] / "valid_tampered"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        o = json.loads((dst / "tx_002/o.json").read_text()); o["steps"][2]["q_after"][0] ^= 1
        (dst / "tx_002/o.json").write_text(json.dumps(o, indent=1, sort_keys=True))
        rep = vf.verify(dst)
        self.assertFalse(rep["clean"]); self.assertTrue(any("stored record is not the one rebuilt" in m for m in rep["transactions"][1]["findings"]))
        shutil.rmtree(dst); shutil.copytree(src, dst)
        f = json.loads((dst / "tx_003/f.json").read_text()); f["fitness"] += 1
        (dst / "tx_003/f.json").write_text(json.dumps(f, indent=1, sort_keys=True))
        rep = vf.verify(dst)
        self.assertTrue(any(m.startswith("F:") for m in rep["transactions"][2]["findings"]))
        shutil.rmtree(dst); shutil.copytree(src, dst)
        lines = (dst / "accesses.jsonl").read_text().splitlines(); lines.append(json.dumps({"op": "wr", "addr": 0x43C02160, "resp": 0}))
        (dst / "accesses.jsonl").write_text("\n".join(lines) + "\n")
        rep = vf.verify(dst)
        self.assertTrue(any("KEY window" in m for m in rep["a7"]["findings"]))


if __name__ == "__main__":
    unittest.main()

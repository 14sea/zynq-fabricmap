"""The carrier-qualification evidence chain (host/b1_qualification.py, host/b1q_adjudicate.py,
the QUALIFICATION runner profile): a modelled B1Q session (budget 9, eleven records) through
the instrument's real host stack → the B1Q adjudicator with the real validators → the
qualification record → `verify()` re-adjudicates it → the MAPPING adjudicator accepts the
carrier only through that chain. Negatives: a bare flag, a missing record, a tampered
evidence file, a binding to another carrier / image / prereg / seed, a HOLD record, a
code probe whose STATUS says tables_match = 1 or cfg_valid = 0, a baseline with a non-zero
readout or other counters. Nothing here touches a board, a port or the key store."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_adjudicate as adj  # noqa: E402
import b1_modelled_session as ms  # noqa: E402
import b1_qualification as bq  # noqa: E402
import b1q_adjudicate as qadj  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

HAVE = inst.DEFAULT_ROOT.is_dir()
MANIFEST = json.loads((R / "manifests/b1_manifest.json").read_text())
QPLAN = json.loads((R / "evidence/b1q/plan.json").read_text())
QPRED = json.loads((R / "evidence/b1q/prediction.json").read_text())
PLAN = json.loads((R / "evidence/b1/plan.json").read_text())
PRED = json.loads((R / "evidence/b1/prediction.json").read_text())
RULING = {"ruling": qadj.RULING_TEXT, "boardid": "17A6", "granted_by": "test", "date": "2026-09-05-T"}


def msha(m: dict) -> str:
    return hashlib.sha256(json.dumps(m, indent=1, ensure_ascii=False).encode()).hexdigest()


def frozen() -> dict:
    m = copy.deepcopy(MANIFEST)
    m["prereg"]["sha256"] = "b" * 64; m["prereg"]["frozen"] = True
    m["image"]["board_ready"] = True
    return m


def qualify(tmp: Path, m: dict, name: str = "q", **kw) -> tuple[dict, Path, dict, str]:
    """Run the modelled B1Q session against manifest `m` (unqualified), adjudicate, write the
    files the runner writes, build the record. Returns (record, evidence dir, result, msha)."""
    sha = msha(m)
    out = tmp / name
    r = ms.run_modelled(m, QPLAN, out, binding_extra={"b1_manifest_sha256": sha}, **kw)
    res = qadj.adjudicate(out, m, QPLAN, QPRED, sha, require_git=False)
    (out / "adjudication.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    (out / "summary.json").write_text(json.dumps({"outcome": res["outcome"], "token": r["token"]}) + "\n")
    rec = bq.make_record(out, m, sha, QPLAN, RULING, res, r["token"])
    return rec, out, res, sha


@unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
class Chain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.m = frozen()
        cls.rec, cls.out, cls.res, cls.sha_q = qualify(cls.tmp, cls.m)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def qualified_manifest(self) -> dict:
        m = copy.deepcopy(self.m); m["carrier"]["qualification"] = copy.deepcopy(self.rec); m["carrier"]["qualified"] = True
        return m

    def test_the_modelled_qualification_session_passes_with_the_silicon_observations(self):
        self.assertEqual(self.res["outcome"], "PASS", self.res["findings"])
        g = self.res["gate_observations"]
        self.assertEqual(g["1"], {"tables_match": 1, "configuration_valid_hw": 1, "readout_all_zero": True})
        self.assertEqual(g["11"]["tables_match"], 1)
        for s in range(2, 11):
            self.assertEqual(g[str(s)], {"tables_match": 0, "configuration_valid_hw": 1, "readout_all_zero": False}, s)
        self.assertEqual(self.res["p3"]["run_log_validation"], {"scored": 11, "audited": 11, "chain_length": 12})
        self.assertEqual(self.res["provisional"]["recall"], 1.0)
        self.assertEqual(self.rec["outcome"], "PASS"); self.assertEqual(self.rec["binding"]["session"], "B1Q")
        self.assertEqual(self.rec["binding"]["master_seed"], QPLAN["master_seed"])
        self.assertNotEqual(QPLAN["master_seed"], PLAN["master_seed"])
        self.assertIn(QPLAN["master_seed"], MANIFEST["seeds"]["excluded"]["b1_qualification"])
        self.assertIn(PLAN["master_seed"], QPLAN["seed_exclusion"]["excluded_master_seeds"])

    def test_verify_readjudicates_and_the_flag_is_derived(self):
        m = self.qualified_manifest()
        v = bq.verify(m)
        self.assertTrue(v["readjudicated"]); self.assertTrue(bq.qualified(m))
        self.assertFalse(bq.qualified(self.m))                        # no record → not qualified
        bare = copy.deepcopy(self.m); bare["carrier"]["qualified"] = True
        self.assertFalse(bq.qualified(bare))                          # a bare flag is nothing

    def test_every_break_in_the_chain_refuses(self):
        good = self.qualified_manifest()
        def refuses(mut, words):
            m = copy.deepcopy(good); mut(m)
            with self.assertRaises(bq.QualificationRefusal) as cm:
                bq.verify(m)
            self.assertIn(words, str(cm.exception))
        refuses(lambda m: m["carrier"].__setitem__("qualification", None), "no carrier.qualification")
        refuses(lambda m: m["carrier"]["qualification"].__setitem__("outcome", "HOLD: x"), "not PASS")
        refuses(lambda m: m["carrier"].__setitem__("bitstream_sha256", "a" * 64), "carrier_sha256")
        refuses(lambda m: m["image"].__setitem__("sha256", "a" * 64), "image_sha256")
        refuses(lambda m: m["prereg"].__setitem__("sha256", "c" * 64), "prereg_sha256")
        refuses(lambda m: m["instrument"].__setitem__("psoracle_commit", "0" * 40), "psoracle_commit")
        refuses(lambda m: m["qualification_plan"].__setitem__("master_seed", 5), "seed/budget")
        refuses(lambda m: m["carrier"]["qualification"]["files"].__setitem__("run_log.json", "0" * 64), "does not hash")
        refuses(lambda m: m["carrier"]["qualification"].__setitem__("evidence_dir", "/nonexistent"), "absent")

    def test_a_tampered_evidence_file_breaks_the_chain(self):
        good = self.qualified_manifest()
        d = self.tmp / "tampered"; shutil.copytree(self.out, d)
        good["carrier"]["qualification"]["evidence_dir"] = str(d)
        bq.verify(good)                                              # the copy stands
        log = json.loads((d / "run_log.json").read_text())
        log["loop_records"][3]["evidence"]["arm"]["status_after"] = "0x00000f54"      # tables_match = 1 on a code probe
        text = json.dumps(log); (d / "run_log.json").write_text(text)
        with self.assertRaises(bq.QualificationRefusal) as cm:
            bq.verify(good)
        self.assertIn("does not hash", str(cm.exception))
        # re-pin the tampered file: the RE-ADJUDICATION catches it
        good["carrier"]["qualification"]["files"]["run_log.json"] = hashlib.sha256(text.encode()).hexdigest()
        with self.assertRaises(bq.QualificationRefusal) as cm:
            bq.verify(good)
        self.assertIn("re-adjudicates", str(cm.exception))

    def test_the_gate_observations_are_required_record_by_record(self):
        log = json.loads((self.out / "run_log.json").read_text())
        def findings(mut):
            l = copy.deepcopy(log); mut(l)
            return qadj.gate_findings(l, QPLAN, QPRED)
        self.assertEqual(findings(lambda l: None), [])
        self.assertTrue(any("tables_match = 1" in f for f in findings(lambda l: l["loop_records"][2]["evidence"]["arm"].__setitem__("status_after", "0x00000f54"))))
        self.assertTrue(any("configuration_valid_hw = 0" in f for f in findings(lambda l: l["loop_records"][2]["evidence"]["arm"].__setitem__("status_after", "0x00000b50"))))
        self.assertTrue(any("fault" in f for f in findings(lambda l: l["loop_records"][2]["evidence"]["arm"].__setitem__("fault_after", 3))))
        self.assertTrue(any("(baseline) readout is not all zero" in f for f in findings(lambda l: l["loop_records"][0]["evidence"]["score"].__setitem__("functional_readout", ["1" + "0" * 15] * 6))))
        self.assertTrue(any("(baseline) tables_match = 0" in f for f in findings(lambda l: l["loop_records"][0]["evidence"]["arm"].__setitem__("status_after", "0x00000b54"))))
        self.assertTrue(any("counters" in f for f in findings(lambda l: l["loop_records"][0]["evidence"]["score"].__setitem__("scores", [0] * 6))))
        self.assertTrue(any("did not answer" in f for f in findings(lambda l: l["loop_records"][4]["evidence"]["score"].__setitem__("functional_readout", ["0" * 16] * 6))))
        self.assertTrue(any("must be SCORED" in f for f in findings(lambda l: l["loop_records"][4].__setitem__("outcome", "REFUSED_BY_PL"))))

    def test_the_b1q_adjudicator_refuses_the_mapping_plan_and_the_wrong_session(self):
        res = qadj.adjudicate(self.out, self.m, PLAN, PRED, self.sha_q, require_git=False)
        self.assertTrue(res["outcome"].startswith("REFUSED"), res["outcome"])
        m = copy.deepcopy(self.m); m["qualification_plan"]["sha256"] = "0" * 64
        res = qadj.adjudicate(self.out, m, QPLAN, QPRED, self.sha_q, require_git=False)
        self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("qualification plan", res["outcome"])

    def test_the_mapping_adjudicator_accepts_the_carrier_only_through_the_chain(self):
        m = self.qualified_manifest(); sha = msha(m)
        out = self.tmp / "mapping"
        r = ms.run_modelled(m, PLAN, out, binding_extra={"b1_manifest_sha256": sha})
        self.assertEqual(r["epoch_end"]["kind"], "COMPLETED")
        res = adj.adjudicate(out, m, PLAN, PRED, sha, require_git=False)
        self.assertEqual(res["outcome"], "PASS", res["findings"])
        bad = copy.deepcopy(m); bad["carrier"]["qualification"]["outcome"] = "HOLD: x"
        res = adj.adjudicate(out, bad, PLAN, PRED, msha(bad), require_git=False)
        self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("qualification", res["outcome"])

    def test_a_qualification_that_holds_is_recorded_as_such_and_never_qualifies(self):
        d = self.tmp / "hold"; shutil.copytree(self.out, d)
        log = json.loads((d / "run_log.json").read_text())
        log["loop_records"][2]["evidence"]["arm"]["status_after"] = "0x00000f54"
        log["loop_records"][2]["evidence"]["arm"]["settle"]["status_last"] = "0x00000f54"   # a consistent record, wrong observation
        (d / "run_log.json").write_text(json.dumps(log))
        res = qadj.adjudicate(d, self.m, QPLAN, QPRED, self.sha_q, require_git=False)
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"])
        self.assertTrue(any("tables_match = 1" in f for f in res["findings"]))
        (d / "adjudication.json").write_text(json.dumps(res)); (d / "summary.json").write_text("{}")
        rec = bq.make_record(d, self.m, self.sha_q, QPLAN, RULING, res, "00" * 16)
        self.assertTrue(rec["outcome"].startswith("HOLD"))
        m = copy.deepcopy(self.m); m["carrier"]["qualification"] = rec
        self.assertFalse(bq.qualified(m))


if __name__ == "__main__":
    unittest.main()

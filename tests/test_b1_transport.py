"""The rel-v4 transport under the B1Q budgets, through the modelled session (the instrument's
real console, relay, collector, ledgers, the soak's faulty wire): the owner's scenarios after
B1Q session 1 (2026-09-06, LOST). Both forced seq-1 controls plus a corrupt TERM followed by
the board's valid retransmission → COMPLETED and a B1Q PASS under budget 4 (and the
session-1 PROTOCOL end under the old budget 2); CRC exhaustion at the fifth drop with budget
4; malformed-frame exhaustion at the third bad frame with budget 2; the mapping plan's two
budgets at 37 and its bytes, and the frozen preregistration's bytes, unchanged."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
sys.path.insert(0, str(R / "tests"))
import claimb_r1p_instrument as inst  # noqa: E402

HAVE = inst.DEFAULT_ROOT.is_dir()
B1_PLAN_SHA = "470e18f8fe3443be1ee9f9f27ffc28f73113b2231cdbff5b62348bfb58fda8e9"
B1_PRED_SHA = "7d197a498a5ca894fbc1287b37d19cd7d288c2f26d6dbcd21fefa8679e8fd35a"
PREREG_SHA = "f995245cca13d5ac8cba8475c609a6e9f01d269cddc2d87e6a9b980f983652f2"


@unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
class Transport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import b1_modelled_session as ms, b1q_adjudicate as qadj
        from test_b1_qualification import frozen, QPLAN, QPRED
        cls.ms, cls.qadj, cls.plan, cls.pred = ms, qadj, QPLAN, QPRED
        cls.tmp = Path(tempfile.mkdtemp()); cls.m = frozen()
        cls.sha = hashlib.sha256(json.dumps(cls.m, indent=1, ensure_ascii=False).encode()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def session(self, name, **kw):
        out = self.tmp / name
        r = self.ms.run_modelled(self.m, self.plan, out, binding_extra={"b1_manifest_sha256": self.sha}, **kw)
        return out, r

    def test_the_b1q_plan_budgets_are_noise_plus_the_forced_controls(self):
        self.assertEqual(self.plan["crc_budget"], 4); self.assertEqual(self.plan["bad_frame_budget"], 2)
        self.assertEqual(self.plan["crc_budget_components"], {"noise_allowance": 2, "forced_crc_controls": 2,
                                                              "controls": ["seq-1 SIGNREQ retry control (flags bit5)", "seq-1 REC retry control (flags bit4)"]})
        m = json.loads((R / "manifests/b1_manifest.json").read_text())
        self.assertEqual((m["qualification_plan"]["crc_budget"], m["qualification_plan"]["bad_frame_budget"]), (4, 2))

    def test_both_controls_plus_a_corrupt_term_then_the_valid_retransmission_pass_under_budget_4(self):
        out, r = self.session("term_retransmit", scripted=[{"type": "TERM", "seq": 12, "kind": "crc"}])
        self.assertEqual(r["epoch_end"]["kind"], "COMPLETED", r["epoch_end"])
        self.assertEqual(r["crc_dropped"], 3)                                    # 2 controls + the TERM
        self.assertGreaterEqual(r["board_stats"]["term_attempts"], 2)           # the board resent it on the host's TERMGET
        self.assertEqual(r["session_summary_written_by"], "app")
        res = self.qadj.adjudicate(out, self.m, self.plan, self.pred, self.sha, require_git=False)
        self.assertEqual(res["outcome"], "PASS", res["findings"])

    def test_the_same_scenario_under_the_session_1_budget_is_the_session_1_loss(self):
        out, r = self.session("term_budget2", crc_budget=2, scripted=[{"type": "TERM", "seq": 12, "kind": "crc"}])
        self.assertEqual(r["epoch_end"]["kind"], "PROTOCOL"); self.assertIn("PROTOCOL_CRC_BUDGET: 3 > 2", r["epoch_end"]["reason"])
        self.assertEqual(r["records"], 11); self.assertEqual(r["exports"]["run_log.json"], "ok")

    def test_crc_exhaustion_at_the_fifth_drop_with_budget_4(self):
        scripted = [{"type": "HB", "seq": 3, "hb_i": 2, "kind": "crc"}, {"type": "HB", "seq": 4, "hb_i": 2, "kind": "crc"}]
        out, r = self.session("crc_four", scripted=scripted)
        self.assertEqual(r["epoch_end"]["kind"], "COMPLETED"); self.assertEqual(r["crc_dropped"], 4)   # exactly the budget: still fine
        scripted.append({"type": "HB", "seq": 5, "hb_i": 2, "kind": "crc"})
        out, r = self.session("crc_five", scripted=scripted)
        self.assertEqual(r["epoch_end"]["kind"], "PROTOCOL"); self.assertIn("PROTOCOL_CRC_BUDGET: 5 > 4", r["epoch_end"]["reason"])
        self.assertEqual(r["exports"]["run_log.json"], "ok"); self.assertEqual(r["session_summary_written_by"], "collector")
        res = self.qadj.adjudicate(out, self.m, self.plan, self.pred, self.sha, require_git=False)
        self.assertNotEqual(res["outcome"], "PASS")

    def test_malformed_frame_exhaustion_at_the_third_bad_frame_with_budget_2(self):
        # a deletion inside the head of an HB line leaves a MAGIC line with the wrong field
        # count — a malformed frame (FrameError, not a CRC failure), ledgered against the
        # bad-frame budget; a truncation is a torn line the reader quarantines as a fragment
        scripted = [{"type": "HB", "seq": s, "hb_i": 3, "kind": "delete_run", "offset": 8, "length": 4} for s in (3, 4)]
        out, r = self.session("bad_two", scripted=scripted)
        self.assertEqual(r["epoch_end"]["kind"], "COMPLETED"); self.assertEqual(r["bad_frames"], 2)
        scripted.append({"type": "HB", "seq": 5, "hb_i": 3, "kind": "delete_run", "offset": 8, "length": 4})
        out, r = self.session("bad_three", scripted=scripted)
        self.assertEqual(r["epoch_end"]["kind"], "PROTOCOL", r["epoch_end"]); self.assertEqual(r["bad_frames"], 3)
        self.assertIn("BAD_FRAME", r["epoch_end"]["reason"].upper())

    def test_the_mapping_budgets_plan_prediction_and_frozen_preregistration_are_unchanged(self):
        plan = json.loads((R / "evidence/b1/plan.json").read_text())
        self.assertEqual((plan["crc_budget"], plan["bad_frame_budget"]), (37, 37))
        self.assertEqual(hashlib.sha256((R / "evidence/b1/plan.json").read_bytes()).hexdigest(), B1_PLAN_SHA)
        self.assertEqual(hashlib.sha256((R / "evidence/b1/prediction.json").read_bytes()).hexdigest(), B1_PRED_SHA)
        self.assertEqual(hashlib.sha256((R / "docs/b1_preregistration.md").read_bytes()).hexdigest(), PREREG_SHA)
        m = json.loads((R / "manifests/b1_manifest.json").read_text())
        self.assertEqual(m["prereg"]["sha256"], PREREG_SHA); self.assertTrue(m["prereg"]["frozen"])


if __name__ == "__main__":
    unittest.main()

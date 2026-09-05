"""host/b1_plan.py — the B1 session plan and the preregistered prediction.

The seed rule is pure (advances past an excluded value; the trace records it); every L5,
L6 and round-1′ seed is excluded; the committed plan and prediction hash to the manifest's
pins and regenerate identically; the budget is the cartographer's own bound; every seq is
audited; the deadline follows the instrument's formula; the prediction's map is the
reference's over the truth fabric and its expected score is exact."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b1_plan as bp  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

MANIFEST = json.loads(bp.MANIFEST.read_text())
PLAN_PATH = R / "evidence/b1/plan.json"
PRED_PATH = R / "evidence/b1/prediction.json"
HAVE = inst.DEFAULT_ROOT.is_dir()


class SeedRule(unittest.TestCase):
    def test_rule_and_advancing(self):
        s = bp.master_seed_by_rule(MANIFEST)
        digest = hashlib.sha256(bp.SEED_LABEL + MANIFEST["instrument"]["psoracle_commit"].encode()).digest()
        self.assertEqual(s["master_seed"], int.from_bytes(digest[s["offset"]:s["offset"] + 4], "big"))
        m = copy.deepcopy(MANIFEST)
        m["seeds"]["excluded"]["test_only"] = [s["master_seed"]]
        s2 = bp.master_seed_by_rule(m)
        self.assertEqual(s2["offset"], s["offset"] + 4)

    def test_every_earlier_seed_is_excluded(self):
        ex = bp.excluded_seeds(MANIFEST)
        for s in (1, 1278624577, 1278628687, 1281816666):
            self.assertIn(s, ex)
        self.assertNotIn(MANIFEST["seeds"]["master_seed"], ex)


@unittest.skipUnless(HAVE and PLAN_PATH.is_file(), "the plan artifact or the instrument is absent")
class CommittedPlan(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(PLAN_PATH.read_text())
        self.pred = json.loads(PRED_PATH.read_text())

    def test_pins(self):
        self.assertEqual(hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest(), MANIFEST["plan"]["sha256"])
        self.assertEqual(hashlib.sha256(PRED_PATH.read_bytes()).hexdigest(), MANIFEST["prediction"]["sha256"])
        self.assertEqual(self.plan["prediction_sha256"], MANIFEST["prediction"]["sha256"])
        self.assertEqual(self.plan["master_seed"], MANIFEST["seeds"]["master_seed"])
        self.assertEqual(self.pred["map_sha256"], MANIFEST["prediction"]["map_sha256"])

    def test_budget_audit_and_deadline(self):
        p = self.plan
        self.assertEqual(p["budget"], bc.CODE_BITS + bc.N + bc.PAIRS_MAX)
        self.assertEqual(p["records"], p["budget"] + 2)
        self.assertEqual(p["audit_policy"], "all-self-reporting")
        self.assertEqual(p["audit_seqs"], list(range(1, p["budget"] + 3)))
        self.assertEqual(p["audited_records"], p["records"])
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        import l6_schedule as ls
        self.assertEqual(p["expected_frames"], ls.expected_frames(p["budget"], set(p["audit_seqs"]), "rel-v4"))
        self.assertEqual(p["crc_budget"], ls.crc_budget(p["expected_frames"]["total"]))
        d = p["deadline"]
        self.assertEqual(p["session_timeout_s"], ls.session_timeout_s(p["budget"], d["rate_C1_planning"], d["rate_C2_planning"]))
        self.assertGreater(p["session_timeout_s"], d["expected_span_s"])
        self.assertEqual(p["flags"], ls.flags_for("abba", watchdog=True, rec_control=True, sign_control=True))

    def test_prediction_is_the_reference_over_the_truth(self):
        sim = bm.simulate(self.plan["master_seed"], self.plan["budget"], bm.fixture("truth"))
        self.assertEqual(sim["map_sha256"], self.pred["map_sha256"])
        self.assertEqual([p["genome"] for p in sim["probes"]], [p["genome"] for p in self.pred["probes"]])
        es = self.pred["expected_score"]
        self.assertEqual((es["precision"], es["recall"], es["anomalies"]), (1.0, 1.0, 0))
        self.assertEqual(es["sample_efficiency"]["probes_to_full_recall_conf1"], bc.CODE_BITS)
        self.assertEqual(es["holdout"]["recall"], 1.0)

    def test_plan_regenerates_identically(self):
        plan, pred = bp.build_plan(MANIFEST, require_git=False)
        for k in ("master_seed", "budget", "audit_seqs", "crc_budget", "session_timeout_s", "flags", "predicted_map_sha256",
                  "predicted_probe_sequence_sha256"):
            self.assertEqual(plan[k], self.plan[k], k)
        self.assertEqual(pred["map"], self.pred["map"])

    def test_compatibility_drift_is_a_refusal(self):
        m = copy.deepcopy(MANIFEST)
        m["universe"]["local_map_sha256"] = "0" * 64
        with self.assertRaises(bp.PlanError):
            bp.build_plan(m, require_git=False)


if __name__ == "__main__":
    unittest.main()

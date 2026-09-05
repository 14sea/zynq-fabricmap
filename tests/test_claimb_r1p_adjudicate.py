"""host/claimb_r1p_adjudicate.py — the round's adjudication over an evidence directory.

The instrument's validator layer is the instrument's and is not re-tested here; it is
replaced by a stub (`p3_layer`) so that THIS round's layer is tested in isolation and in
both directions: a synthetic COMPLETED run whose scores equal the preregistered prediction
is a PASS whose result equals the prediction; one altered score is a HOLD naming the seq;
a run stopped short is a HOLD; a span past the window is a HOLD; a log bound to another
session or seed is REFUSED before any number exists; and S #3's real evidence — the one
directory that could be mistaken for Claim B data — is REFUSED on its binding."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import claimb_r1p_adjudicate as adj  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

MANIFEST = json.loads(inst.MANIFEST.read_text())
PLAN = json.loads((R / "evidence/claimb_round1prime/plan.json").read_text())
PRED = json.loads((R / "evidence/claimb_round1prime/model_prediction.json").read_text())
HAVE = inst.DEFAULT_ROOT.is_dir()
FAKE_FROZEN = "a" * 64
S3 = inst.DEFAULT_ROOT / "evidence/l6_17A6_2026-09-04-01-S"


def frozen_manifest() -> dict:
    m = copy.deepcopy(MANIFEST)
    m["prereg"]["sha256"] = FAKE_FROZEN
    return m


def synthetic_log(manifest: dict, plan: dict, pred: dict, n: int | None = None, kind: str = "COMPLETED") -> dict:
    """A run log shaped like the instrument's, with every SCORED record carrying the
    predicted scores; `n` truncates the candidates (a stopped run)."""
    n = plan["n"] if n is None else n
    base = pred["base_scores"]["train"]
    by_seq = {c["seq"]: c for c in pred["candidates"]}
    recs = [{"seq": 1, "outcome": "SCORED", "verified": "audited", "evidence": {"score": {"scores": list(base)}}}]
    for seq in range(2, n + 2):
        c = by_seq[seq]
        recs.append({"seq": seq, "arm": c["arm"], "genome": c["genome"], "outcome": "SCORED",
                     "verified": "audited" if seq in set(plan["audit_seqs"]) else "replayed-only",
                     "evidence": {"score": {"scores": list(c["scores_train"])}, "arm": {"settle": {"polls": 16}}}})
    last = n + 2 if kind == "COMPLETED" else n + 1
    if kind == "COMPLETED":
        recs.append({"seq": n + 2, "outcome": "SCORED", "verified": "audited", "evidence": {"score": {"scores": list(base)}}})
    return {"control_plane": "standalone",
            "app_identity": {"protocol": "rel-v4", "master_seed": plan["master_seed"], "schedule_mode": "abba"},
            "loop_records": recs,
            "session_summary": {"epoch_end": {"kind": kind, "reason": "budget" if kind == "COMPLETED" else "test",
                                              "last_seq": last}, "written_by": "app"},
            "l6": {"binding": {"image_sha256": manifest["instrument"]["image_sha256"], "prereg_sha256": manifest["prereg"]["sha256"],
                               "protocol": "rel-v4", "session": "B", "schedule_mode": "abba",
                               "master_seed": plan["master_seed"]}}}


def write_dir(log: dict) -> Path:
    d = Path(tempfile.mkdtemp())
    (d / "run_log.json").write_text(json.dumps(log))
    (d / "audits.json").write_text("{}")
    (d / "timeline.json").write_text(json.dumps({"frames": [], "crc_dropped": 0, "bad_frames": 0}))
    return d


def stub_layer(span_s: float = 6000.0, findings=()):
    def layer(evidence, log, plan, sched_by_seq):
        return {"findings": list(findings), "rejected": None, "rate_report": {"session_span_s": span_s}}
    return layer


@unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
class RoundLayer(unittest.TestCase):
    def setUp(self):
        self.m = frozen_manifest()

    def adjudicate(self, log, **kw):
        return adj.adjudicate(write_dir(log), self.m, PLAN, PRED, require_git=False, p3_layer=stub_layer(**kw))

    def test_a_run_equal_to_the_prediction_passes_and_reads_the_negative(self):
        res = self.adjudicate(synthetic_log(self.m, PLAN, PRED))
        self.assertEqual(res["outcome"], "PASS", res["findings"])
        self.assertEqual(res["known_answer"]["mismatches"], 0)
        self.assertEqual(res["known_answer"]["checked"], PLAN["n"] + 2)
        self.assertTrue(all(res["prediction_comparison"].values()))
        self.assertFalse(res["claimb_result"]["primary_map_guided_better"])
        self.assertTrue(res["claimb_result"]["equals_prediction"])
        self.assertIn("NEGATIVE", res["claimb_result"]["reading"])

    def test_one_altered_score_is_a_hold_naming_the_seq(self):
        log = synthetic_log(self.m, PLAN, PRED)
        log["loop_records"][500]["evidence"]["score"]["scores"][2] += 1
        res = self.adjudicate(log)
        self.assertTrue(res["outcome"].startswith("HOLD"))
        self.assertEqual(res["known_answer"]["mismatches"], 1)
        self.assertIn(f"seq {log['loop_records'][500]['seq']}", res["known_answer"]["first"][0])
        self.assertNotIn("claimb_result", res)

    def test_a_stopped_run_is_a_hold(self):
        res = self.adjudicate(synthetic_log(self.m, PLAN, PRED, n=3000, kind="STOPPED"))
        self.assertTrue(res["outcome"].startswith("HOLD"))
        self.assertTrue(any("not COMPLETED" in f for f in res["findings"]))

    def test_a_span_past_the_window_is_a_hold(self):
        res = self.adjudicate(synthetic_log(self.m, PLAN, PRED), span_s=PLAN["window_s"] + 1)
        self.assertTrue(res["outcome"].startswith("HOLD"))
        self.assertTrue(any("exceeds the window" in f for f in res["findings"]))

    def test_instrument_findings_propagate(self):
        res = self.adjudicate(synthetic_log(self.m, PLAN, PRED), findings=["missing REC for seq [7]"])
        self.assertTrue(res["outcome"].startswith("HOLD"))

    def test_a_positive_primary_is_read_as_positive(self):
        """The decision rule can also say yes: lift map-guided in ≥ 12 blocks."""
        log = synthetic_log(self.m, PLAN, PRED)
        by_seq = {c["seq"]: c for c in PRED["candidates"]}
        blocks = PLAN["blocks"]
        lifted = 0
        for r in log["loop_records"]:
            if r.get("arm") != "map_guided" or lifted >= 12:
                continue
            pair = by_seq[r["seq"]]["pair"]
            if pair % blocks["block_pairs"] == 0 and pair // blocks["block_pairs"] < 12:
                r["evidence"]["score"]["scores"][0] += 5 - by_seq[r["seq"]]["d_train"]      # best-of-block +5 > +4
                lifted += 1
        res = self.adjudicate(log)
        self.assertTrue(res["outcome"].startswith("HOLD"), "altered scores are a known-answer HOLD first")
        # the metrics layer alone, over the altered rows, decides positive
        sched = {c["seq"]: c for c in PRED["candidates"]}
        rows = adj.measured_rows(log, PRED, sched)
        import claimb_r1p_model as mdl
        m = mdl.metrics(rows, blocks["block_pairs"], blocks["blocks"])
        self.assertTrue(m["primary"]["map_guided_better"])
        self.assertEqual(m["primary"]["positive"], 12)


@unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
class Binding(unittest.TestCase):
    def test_a_draft_manifest_refuses_everything(self):
        res = adj.adjudicate(write_dir(synthetic_log(MANIFEST, PLAN, PRED)), MANIFEST, PLAN, PRED,
                             require_git=False, p3_layer=stub_layer())
        self.assertTrue(res["outcome"].startswith("REFUSED"))
        self.assertIn("not frozen", res["outcome"])

    def test_another_seed_or_session_is_refused_by_name(self):
        m = frozen_manifest()
        for key, value, word in (("master_seed", 1278628687, "master_seed"), ("session", "S", "session")):
            log = synthetic_log(m, PLAN, PRED)
            log["l6"]["binding"][key] = value
            res = adj.adjudicate(write_dir(log), m, PLAN, PRED, require_git=False, p3_layer=stub_layer())
            self.assertTrue(res["outcome"].startswith("REFUSED"), res["outcome"])
            self.assertIn(word, res["outcome"])

    @unittest.skipUnless(S3.is_dir(), "S #3's evidence is not present")
    def test_s3s_evidence_is_refused_as_claim_b_data(self):
        res = adj.adjudicate(S3, frozen_manifest(), PLAN, PRED, require_git=False)
        self.assertTrue(res["outcome"].startswith("REFUSED"), res["outcome"])
        self.assertIn("session", res["outcome"])
        self.assertNotIn("claimb_result", res)
        self.assertNotIn("metrics_train", res)


class Pins(unittest.TestCase):
    def test_pins_refuse_a_manifest_without_hashes_and_a_wrong_hash(self):
        m = copy.deepcopy(MANIFEST)
        m["plan"]["sha256"] = None
        with self.assertRaises(adj.Refusal):
            adj.check_pins(m, R / "evidence/claimb_round1prime/plan.json", R / "evidence/claimb_round1prime/model_prediction.json")
        m["plan"]["sha256"] = "0" * 64
        with self.assertRaises(adj.Refusal):
            adj.check_pins(m, R / "evidence/claimb_round1prime/plan.json", R / "evidence/claimb_round1prime/model_prediction.json")
        adj.check_pins(MANIFEST, R / "evidence/claimb_round1prime/plan.json", R / "evidence/claimb_round1prime/model_prediction.json")


if __name__ == "__main__":
    unittest.main()

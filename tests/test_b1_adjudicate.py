"""host/b1_adjudicate.py — the B1 adjudication over an evidence directory.

The instrument's validator layer is stubbed (`p3_layer`) so THIS stage's layer is tested in
isolation: a synthetic session produced by the reference cartographer over the truth
fabric (records carrying genome, readout and the board's carto block) is a PASS with exact
metrics equal to the prediction; the same session over a PERMUTED fabric is a HOLD (the
map differs from the prediction) with the metrics scored against the truth; a board that
probed a genome the algorithm would not have proposed fails the autonomy replay; a board
whose commitment hash lies fails the commitment check; a run stopped short is a HOLD; a
DRAFT manifest and a foreign binding are REFUSED."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_adjudicate as adj  # noqa: E402
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b1_plan as bp  # noqa: E402

MANIFEST = json.loads(bp.MANIFEST.read_text())
PLAN = json.loads((R / "evidence/b1/plan.json").read_text())
PRED = json.loads((R / "evidence/b1/prediction.json").read_text())
FAKE_FROZEN = "b" * 64


def frozen_manifest() -> dict:
    m = copy.deepcopy(MANIFEST)
    m["prereg"]["sha256"] = FAKE_FROZEN
    m["image"]["board_ready"] = True
    return m


def synthetic_log(manifest: dict, plan: dict, fabric, n: int | None = None, kind: str = "COMPLETED") -> dict:
    """A B1 session as the board would record it, from the reference over `fabric`."""
    budget = plan["budget"]
    sim = bm.simulate(plan["master_seed"], budget, fabric)
    c = bc.Carto(plan["master_seed"], budget)      # a second pass to render the baselines' blocks
    recs = []
    def rec(seq, genome_hex, tables, carto, verified="audited"):
        return {"seq": seq, "genome": genome_hex, "outcome": "SCORED", "verified": verified, "carto": json.loads(carto),
                "evidence": {"score": {"functional_readout": [f"{t:016x}" for t in tables], "scores": [0] * 6},
                             "arm": {"settle": {"polls": 16}}}}
    zero = [0] * 6
    c.render()
    recs.append(rec(1, bc.genome_to_hex(0), zero, c.record_json(bc.PH_DONE, 1, [])))
    for p, r in zip(sim["probes"], sim["records"]):
        g = bc.genome_from_hex(p["genome"])
        recs.append(rec(r["seq"], p["genome"], fabric(g), r["carto"]))
    last = sim["carto"]
    closing = last.record_json(bc.PH_DONE, budget + 2, [])
    if n is not None:
        recs = recs[:n + 1]
    if kind == "COMPLETED":
        recs.append(rec(budget + 2, bc.genome_to_hex(0), zero, closing))
    return {"control_plane": "standalone",
            "app_identity": {"protocol": "rel-v4", "master_seed": plan["master_seed"], "carto_version": "carto-v1",
                             "universe_sha256": manifest["universe"]["sha256"], "probe_budget": budget,
                             "rec_retry_control": True, "sign_retry_control": True, "findings": []},
            "loop_records": recs,
            "session_summary": {"epoch_end": {"kind": kind, "reason": "budget" if kind == "COMPLETED" else "test",
                                              "last_seq": recs[-1]["seq"]}, "written_by": "app"},
            "l6": {"binding": {"image_sha256": manifest["image"]["sha256"], "prereg_sha256": manifest["prereg"]["sha256"],
                               "protocol": "rel-v4", "session": "B1", "schedule_mode": "carto-v1",
                               "master_seed": plan["master_seed"]}}}


def write_dir(log: dict) -> Path:
    d = Path(tempfile.mkdtemp())
    (d / "run_log.json").write_text(json.dumps(log))
    (d / "audits.json").write_text("{}")
    (d / "timeline.json").write_text(json.dumps({"frames": [], "crc_dropped": 0, "bad_frames": 0}))
    return d


def stub_layer(findings=()):
    def layer(evidence, log, plan):
        return {"findings": list(findings), "rejected": None, "rate_report": {"session_span_s": 300.0}}
    return layer


class Stage(unittest.TestCase):
    def setUp(self):
        self.m = frozen_manifest()

    def adjudicate(self, log, **kw):
        return adj.adjudicate(write_dir(log), self.m, PLAN, PRED, require_git=False, p3_layer=stub_layer(**kw))

    def test_truth_session_passes_with_exact_metrics(self):
        res = self.adjudicate(synthetic_log(self.m, PLAN, bm.fixture("truth")))
        self.assertEqual(res["outcome"], "PASS", res["findings"])
        r = res["b1_result"]
        self.assertEqual((r["precision"], r["recall"], r["anomalies"]), (1.0, 1.0, 0))
        self.assertEqual(r["holdout"]["recall"], 1.0)
        self.assertEqual(r["sample_efficiency"]["probes_to_full_recall_conf1"], bc.CODE_BITS)
        self.assertTrue(res["prediction_comparison"]["map_equal"])
        self.assertTrue(res["prediction_comparison"]["probe_sequence_equal"])
        self.assertEqual(res["replay"]["probes_replayed"], PLAN["budget"])
        self.assertEqual(res["self_map_v2"]["schema_version"], "2.0.0")

    def test_a_permuted_fabric_is_a_hold_scored_against_the_truth(self):
        res = self.adjudicate(synthetic_log(self.m, PLAN, bm.fixture("permuted", seed=4)))
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"])
        self.assertFalse(res["prediction_comparison"]["map_equal"])
        self.assertLess(res["b1_result"]["precision"], 0.1)     # the board mapped what it measured, not the truth
        self.assertEqual(res["replay"]["findings"], [])            # and did so autonomously and consistently

    def test_a_probe_the_algorithm_would_not_propose_fails_the_replay(self):
        log = synthetic_log(self.m, PLAN, bm.fixture("truth"))
        log["loop_records"][20]["genome"] = bc.genome_to_hex(1 << 291)
        res = self.adjudicate(log)
        self.assertTrue(res["outcome"].startswith("HOLD"))
        self.assertTrue(any("autonomy replay" in f for f in res["findings"]))

    def test_a_lying_commitment_is_a_hold(self):
        log = synthetic_log(self.m, PLAN, bm.fixture("truth"))
        log["loop_records"][50]["carto"]["map_sha256"] = "0" * 64
        res = self.adjudicate(log)
        self.assertTrue(res["outcome"].startswith("HOLD"))
        self.assertTrue(any("commitment" in f for f in res["findings"]))

    def test_a_short_run_is_a_hold(self):
        res = self.adjudicate(synthetic_log(self.m, PLAN, bm.fixture("truth"), n=100, kind="STOPPED"))
        self.assertTrue(res["outcome"].startswith("HOLD"))
        self.assertTrue(any("not COMPLETED" in f for f in res["findings"]))

    def test_instrument_findings_propagate(self):
        res = self.adjudicate(synthetic_log(self.m, PLAN, bm.fixture("truth")), findings=["missing REC for seq [7]"])
        self.assertTrue(res["outcome"].startswith("HOLD"))


class Binding(unittest.TestCase):
    def test_draft_manifest_refuses(self):
        res = adj.adjudicate(write_dir(synthetic_log(MANIFEST, PLAN, bm.fixture("truth"))), MANIFEST, PLAN, PRED,
                             require_git=False, p3_layer=stub_layer())
        self.assertTrue(res["outcome"].startswith("REFUSED"))
        self.assertIn("not frozen", res["outcome"])

    def test_foreign_session_seed_or_identity_refuses(self):
        m = frozen_manifest()
        for where, key, value in (("binding", "session", "B"), ("binding", "master_seed", 1281816666),
                                  ("ident", "carto_version", "carto-v0"), ("ident", "probe_budget", 5)):
            log = synthetic_log(m, PLAN, bm.fixture("truth"))
            (log["l6"]["binding"] if where == "binding" else log["app_identity"])[key] = value
            res = adj.adjudicate(write_dir(log), m, PLAN, PRED, require_git=False, p3_layer=stub_layer())
            self.assertTrue(res["outcome"].startswith("REFUSED"), (key, res["outcome"]))
            self.assertIn(key, res["outcome"])


if __name__ == "__main__":
    unittest.main()

"""host/b1_adjudicate.py — one named check per preregistration condition, each with a
negative test. The instrument's validator layer is stubbed (`p3_layer`) so THIS stage's
layer is tested alone; the synthetic session is the reference orchestrator over a fabric,
bound as the board would be (token, universe, image), with the records shaped as the board
emits them (genome, readout, the carto block)."""
from __future__ import annotations

import copy
import hashlib
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
TOKEN = "a13f38b53355fd4c1cac3145244727f8"
MSHA = "c" * 64


def frozen_manifest() -> dict:
    m = copy.deepcopy(MANIFEST)
    m["prereg"]["sha256"] = FAKE_FROZEN
    m["image"]["board_ready"] = True
    m["carrier"]["qualified"] = True
    return m


def synthetic_log(manifest: dict, plan: dict, fabric, n: int | None = None, kind: str = "COMPLETED", token: str = TOKEN) -> dict:
    """A B1 session as the board would record it, from the reference session over `fabric`."""
    image_lo32 = int(manifest["image"]["sha256"][-8:], 16)
    sim = bm.simulate(plan["master_seed"], plan["budget"], fabric, token=token, universe=manifest["universe"]["sha256"],
                      image_lo32=image_lo32)
    recs = []
    for r in sim["records"]:
        recs.append({"seq": r["seq"], "genome": r["genome"], "outcome": "SCORED", "verified": "audited",
                     "carto": json.loads(r["carto"]),
                     "evidence": {"score": {"functional_readout": [f"{t:016x}" for t in r["tables"]], "scores": [0] * 6},
                                  "arm": {"settle": {"polls": 16}}}})
    if n is not None:
        recs = recs[:n]
    if kind != "COMPLETED":
        recs = [r for r in recs if r["seq"] != plan["budget"] + 2]
    return {"control_plane": "standalone",
            "app_identity": {"protocol": "rel-v4", "master_seed": plan["master_seed"], "carto_version": "carto-v1",
                             "universe_sha256": manifest["universe"]["sha256"], "probe_budget": plan["budget"],
                             "carrier_variant": "0x42310001", "carrier_sha256": manifest["carrier"]["bitstream_sha256"],
                             "rec_retry_control": True, "sign_retry_control": True, "findings": [], "token": token},
            "loop_records": recs,
            "session_summary": {"epoch_end": {"kind": kind, "reason": "budget" if kind == "COMPLETED" else "test",
                                              "last_seq": recs[-1]["seq"]}, "written_by": "app"},
            "l6": {"binding": {"image_sha256": manifest["image"]["sha256"], "prereg_sha256": manifest["prereg"]["sha256"],
                               "protocol": "rel-v4", "session": "B1", "schedule_mode": "carto-v1", "master_seed": plan["master_seed"],
                               "b1_manifest_sha256": MSHA, "psoracle_commit": manifest["instrument"]["psoracle_commit"]}}}


def write_dir(log: dict) -> Path:
    d = Path(tempfile.mkdtemp())
    (d / "run_log.json").write_text(json.dumps(log))
    (d / "audits.json").write_text("{}")
    (d / "timeline.json").write_text(json.dumps({"frames": [], "crc_dropped": 0, "bad_frames": 0}))
    return d


def stub_layer(span_s: float = 300.0, findings=()):
    def layer(evidence, log, plan):
        return {"findings": list(findings), "rejected": None, "rate_report": {"session_span_s": span_s}}
    return layer


class Stage(unittest.TestCase):
    def setUp(self):
        self.m = frozen_manifest()

    def adjudicate(self, log, **kw):
        return adj.adjudicate(write_dir(log), self.m, PLAN, PRED, MSHA, require_git=False, p3_layer=stub_layer(**kw))

    def test_truth_session_passes_with_the_predicted_metrics(self):
        res = self.adjudicate(synthetic_log(self.m, PLAN, bm.fixture("truth")))
        self.assertEqual(res["outcome"], "PASS", res["findings"])
        r = res["b1_result"]
        self.assertEqual((r["precision"], r["recall"], r["anomalies"], r["unobserved_claims"]), (1.0, 1.0, 0, 0))
        self.assertEqual(r["stratum_B"]["recall"], 1.0)
        self.assertEqual(r["snapshots"]["probes_to_full_recall_conf1"], bc.CODE_BITS)
        self.assertEqual(r["snapshots"]["provisional"]["recall"], 1.0)
        self.assertTrue(res["prediction_comparison"]["content_equal"])
        self.assertEqual(res["replay"]["probes_replayed"], PLAN["budget"])
        self.assertEqual(res["self_map_v2"]["binding"]["token"], TOKEN)
        self.assertEqual(res["verifier_report"]["confirmed"]["recall"], 1.0)

    def test_another_token_still_passes_because_the_prediction_is_content_level(self):
        res = self.adjudicate(synthetic_log(self.m, PLAN, bm.fixture("truth"), token="ee" * 16))
        self.assertEqual(res["outcome"], "PASS", res["findings"])

    def test_a_permuted_fabric_is_a_hold_named_by_the_verifier_and_the_prediction(self):
        res = self.adjudicate(synthetic_log(self.m, PLAN, bm.fixture("permuted", seed=4)))
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"])
        self.assertFalse(res["prediction_comparison"]["content_equal"])
        self.assertLess(res["b1_result"]["precision"], 0.1)
        self.assertEqual(res["replay"]["findings"], [])
        self.assertTrue(any(f.startswith("prediction:") for f in res["findings"]))
        self.assertTrue(any(f.startswith("verifier: precision") for f in res["findings"]))

    def test_a_foreign_probe_fails_the_autonomy_replay(self):
        log = synthetic_log(self.m, PLAN, bm.fixture("truth"))
        log["loop_records"][20]["genome"] = bc.genome_to_hex(1 << 291)
        res = self.adjudicate(log)
        self.assertTrue(any("autonomy replay" in f for f in res["findings"]))

    def test_a_lying_commitment_and_a_wrong_block_field_are_holds(self):
        for key, value in (("map_sha256", "0" * 64), ("content_sha256", "1" * 64), ("probes_issued", 999), ("phase", "pair")):
            log = synthetic_log(self.m, PLAN, bm.fixture("truth"))
            log["loop_records"][50]["carto"][key] = value
            res = self.adjudicate(log)
            self.assertTrue(res["outcome"].startswith("HOLD"), key)
            self.assertTrue(any(f"carto.{key}" in f for f in res["findings"]), (key, res["findings"]))

    def test_the_init_order_defect_is_caught_at_the_opening_record(self):
        """The regression for the first image: an opening block carrying the zero struct's
        hash (the cartographer initialised AFTER the opening baseline) is a HOLD at seq 1."""
        log = synthetic_log(self.m, PLAN, bm.fixture("truth"))
        zero = bc.Carto(0, 0); zero.render()
        log["loop_records"][0]["carto"]["map_sha256"] = zero.map_sha256
        log["loop_records"][0]["carto"]["content_sha256"] = zero.content_sha256
        res = self.adjudicate(log)
        self.assertTrue(res["outcome"].startswith("HOLD"))
        self.assertTrue(any("seq 1 (baseline)" in f for f in res["findings"]), res["findings"])

    def test_a_short_run_and_a_late_span_are_holds(self):
        res = self.adjudicate(synthetic_log(self.m, PLAN, bm.fixture("truth"), n=100, kind="STOPPED"))
        self.assertTrue(any(f.startswith("completion:") for f in res["findings"]))
        res = self.adjudicate(synthetic_log(self.m, PLAN, bm.fixture("truth")), span_s=PLAN["session_timeout_s"] + 1)
        self.assertTrue(any(f.startswith("deadline:") for f in res["findings"]))

    def test_a_dropout_fabric_fails_recall_and_names_it(self):
        res = self.adjudicate(synthetic_log(self.m, PLAN, bm.fixture("dropout", seed=2)))
        self.assertTrue(any(f.startswith("verifier: recall") for f in res["findings"]))
        self.assertTrue(any("anomalies" in f for f in res["findings"]))

    def test_instrument_findings_propagate(self):
        res = self.adjudicate(synthetic_log(self.m, PLAN, bm.fixture("truth")), findings=["missing REC for seq [7]"])
        self.assertTrue(res["outcome"].startswith("HOLD"))
        self.assertIn("missing REC for seq [7]", res["findings"])


class Binding(unittest.TestCase):
    def test_an_unqualified_carrier_refuses(self):
        m = frozen_manifest(); m["carrier"]["qualified"] = False
        res = adj.adjudicate(write_dir(synthetic_log(m, PLAN, bm.fixture("truth"))), m, PLAN, PRED, MSHA,
                             require_git=False, p3_layer=stub_layer())
        self.assertTrue(res["outcome"].startswith("REFUSED"))
        self.assertIn("qualified", res["outcome"])

    def test_draft_manifest_refuses(self):
        res = adj.adjudicate(write_dir(synthetic_log(MANIFEST, PLAN, bm.fixture("truth"))), MANIFEST, PLAN, PRED, MSHA,
                             require_git=False, p3_layer=stub_layer())
        self.assertTrue(res["outcome"].startswith("REFUSED"))
        self.assertIn("not frozen", res["outcome"])

    def test_every_binding_and_identity_field_is_checked(self):
        m = frozen_manifest()
        cases = (("binding", "session", "S"), ("binding", "master_seed", 1281816666), ("binding", "b1_manifest_sha256", "d" * 64),
                 ("binding", "psoracle_commit", "0" * 40), ("ident", "carto_version", "carto-v0"), ("ident", "probe_budget", 5),
                 ("ident", "carrier_variant", "0x00000000"), ("ident", "carrier_sha256", "e" * 64))
        for where, key, value in cases:
            log = synthetic_log(m, PLAN, bm.fixture("truth"))
            (log["l6"]["binding"] if where == "binding" else log["app_identity"])[key] = value
            res = adj.adjudicate(write_dir(log), m, PLAN, PRED, MSHA, require_git=False, p3_layer=stub_layer())
            self.assertTrue(res["outcome"].startswith("REFUSED"), (key, res["outcome"]))
            self.assertIn(key, res["outcome"])

    def test_a_manifest_sha_other_than_the_logs_refuses(self):
        m = frozen_manifest()
        log = synthetic_log(m, PLAN, bm.fixture("truth"))
        res = adj.adjudicate(write_dir(log), m, PLAN, PRED, "f" * 64, require_git=False, p3_layer=stub_layer())
        self.assertTrue(res["outcome"].startswith("REFUSED"))
        self.assertIn("b1_manifest_sha256", res["outcome"])


class Schema(unittest.TestCase):
    def test_the_expanded_map_validates_and_a_broken_one_is_named(self):
        m = frozen_manifest()
        res = adj.adjudicate(write_dir(synthetic_log(m, PLAN, bm.fixture("truth"))), m, PLAN, PRED, MSHA,
                             require_git=False, p3_layer=stub_layer())
        doc = res["self_map_v2"]
        self.assertEqual(adj.schema_findings(doc), [])
        bad = copy.deepcopy(doc); bad["entries"][0]["polarity"] = "inverted"        # no derived polarity in a v2 map
        self.assertTrue(any("entries/0" in f for f in adj.schema_findings(bad)))
        bad = copy.deepcopy(doc); bad["binding"]["token"] = "not-hex"
        self.assertTrue(any("binding/token" in f for f in adj.schema_findings(bad)))
        bad = copy.deepcopy(doc); del bad["interaction_edges"]
        self.assertTrue(any("interaction_edges" in f for f in adj.schema_findings(bad)))

    def test_no_validator_is_a_finding_not_a_pass(self):
        import builtins
        real = builtins.__import__
        def fake(name, *a, **k):
            if name == "jsonschema":
                raise ImportError("gone")
            return real(name, *a, **k)
        builtins.__import__ = fake
        try:
            out = adj.schema_findings({"schema": "self_map"})
        finally:
            builtins.__import__ = real
        self.assertEqual(len(out), 1); self.assertIn("unvalidated", out[0])


class Pins(unittest.TestCase):
    def test_check_pins_refuses_a_wrong_plan_or_pins_table(self):
        m = copy.deepcopy(MANIFEST)
        m["plan"]["sha256"] = "0" * 64
        with self.assertRaises(adj.Refusal):
            adj.check_pins(m, R / "evidence/b1/plan.json", R / "evidence/b1/prediction.json")
        m = copy.deepcopy(MANIFEST)
        m["pins"] = {"sha256": "0" * 64}
        with self.assertRaises(adj.Refusal) as cm:
            adj.check_pins(m, R / "evidence/b1/plan.json", R / "evidence/b1/prediction.json")
        self.assertIn("pins", str(cm.exception))

    def test_the_committed_pins_verify(self):
        adj.check_pins(MANIFEST, R / "evidence/b1/plan.json", R / "evidence/b1/prediction.json")


if __name__ == "__main__":
    unittest.main()

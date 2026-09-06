"""host/b1_adjudicate.py — one named check per preregistration condition, each with a
negative test driven through `adjudicate()` ITSELF (owner's review 2026-09-05: a finding
that a helper produces but the entry point drops is no finding). The instrument's validator
layer is stubbed (`p3_layer`) so THIS stage's layer is tested alone; the synthetic session
is the reference orchestrator over a fabric, bound as the board would be (token, universe,
image), with the records shaped as the board emits them. The carrier-qualification chain
has its own module test (tests/test_b1_qualification.py); here the Stage tests pass
`qualification_check=None` and one test pins that the DEFAULT refuses without a record."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_adjudicate as adj  # noqa: E402
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b1_pins as bp  # noqa: E402
import b1_plan as bpl  # noqa: E402

MANIFEST = json.loads(bpl.MANIFEST.read_text())
PLAN = json.loads((R / "evidence/b1/plan.json").read_text())
PRED = json.loads((R / "evidence/b1/prediction.json").read_text())
FAKE_FROZEN = "b" * 64
TOKEN = "a13f38b53355fd4c1cac3145244727f8"
MSHA = "c" * 64
NOQ = None          # Stage tests: the qualification chain is tested in test_b1_qualification


PREREG_DIR = Path(tempfile.mkdtemp())


def freeze_doc(m: dict, text: str = "# fixture preregistration\n") -> Path:
    """A temporary preregistration document, frozen into `m` by path and sha256 — the
    adjudicator checks the DOCUMENT's bytes, not only the digest."""
    import os
    doc = PREREG_DIR / f"prereg_{hashlib.sha256(text.encode()).hexdigest()[:8]}.md"
    doc.write_text(text)
    m["prereg"]["path"] = os.path.relpath(doc, R)
    m["prereg"]["sha256"] = hashlib.sha256(doc.read_bytes()).hexdigest()
    return doc


def frozen_manifest() -> dict:
    m = copy.deepcopy(MANIFEST)
    freeze_doc(m)
    m["image"]["board_ready"] = True
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
                                  "arm": {"settle": {"polls": 16}, "status_after": "0x00000b54" if any(r["tables"]) else "0x00000f54",
                                          "fault_after": 0}}})
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
                               "protocol": "rel-v4", "session": plan["session"], "schedule_mode": "carto-v1", "master_seed": plan["master_seed"],
                               "b1_manifest_sha256": MSHA, "psoracle_commit": manifest["instrument"]["psoracle_commit"]},
                   "inputs": adj.expected_inputs(manifest, plan["session"])}}


def write_dir(log: dict, exports_ok: bool = True) -> Path:
    import b1_session
    d = Path(tempfile.mkdtemp())
    (d / "run_log.json").write_text(json.dumps(log))
    (d / "audits.json").write_text("{}")
    (d / "timeline.json").write_text(json.dumps({"frames": [], "crc_dropped": 0, "bad_frames": 0}))
    (d / "console.log").write_bytes(b"P3L5 synthetic\n"); (d / "console.ts.log").write_bytes(b"")
    statuses = {k: "ok" for k in b1_session.REQUIRED_EXPORTS}
    if not exports_ok:
        statuses["console.log"] = "INCOMPLETE: OSError: synthetic"
    b1_session.write_exports_manifest(d, statuses)
    return d


def stub_layer(span_s: float = 300.0, findings=()):
    def layer(evidence, log, plan):
        return {"findings": list(findings), "rejected": None, "rate_report": {"session_span_s": span_s}}
    return layer


@contextmanager
def tweaked(func_name: str, path: tuple, value):
    """Run adjudicate() with ONE metric altered on its way out of the verifier: the gate
    under test must fire from the entry point, whatever produced the number."""
    real = getattr(adj.bv, func_name)
    def wrapper(*a, **k):
        out = real(*a, **k)
        d = out
        for key in path[:-1]:
            d = d[key]
        d[path[-1]] = value
        return out
    with mock.patch.object(adj.bv, func_name, wrapper):
        yield


class Stage(unittest.TestCase):
    def setUp(self):
        self.m = frozen_manifest()

    def adjudicate(self, log, m=None, **kw):
        return adj.adjudicate(write_dir(log), m or self.m, PLAN, PRED, MSHA, require_git=False, p3_layer=stub_layer(**kw),
                              qualification_check=NOQ)

    def truth(self):
        return synthetic_log(self.m, PLAN, bm.fixture("truth"))

    def test_truth_session_passes_with_the_predicted_metrics(self):
        res = self.adjudicate(self.truth())
        self.assertEqual(res["outcome"], "PASS", res["findings"])
        r = res["b1_result"]
        self.assertEqual((r["precision"], r["recall"], r["anomalies"], r["unobserved_claims"]), (1.0, 1.0, 0, 0))
        self.assertEqual(r["calibration"]["2"], {"claimed": 292, "correct": 292, "accuracy": 1.0})
        self.assertEqual(r["calibration"]["1"]["claimed"], 0)
        self.assertEqual(r["stratum_B"]["recall"], 1.0)
        s = r["snapshots"]
        self.assertEqual((s["probes_to_full_recall_conf1"], s["probes_to_full_confirmation"]), (9, 301))
        self.assertEqual(s["provisional"]["calibration"]["1"], {"claimed": 292, "correct": 292, "accuracy": 1.0})
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
        log = self.truth()
        log["loop_records"][20]["genome"] = bc.genome_to_hex(1 << 291)
        res = self.adjudicate(log)
        self.assertTrue(any("autonomy replay" in f for f in res["findings"]))

    def test_a_lying_commitment_and_a_wrong_block_field_are_holds(self):
        for key, value in (("map_sha256", "0" * 64), ("content_sha256", "1" * 64), ("probes_issued", 999), ("phase", "pair")):
            log = self.truth()
            log["loop_records"][50]["carto"][key] = value
            res = self.adjudicate(log)
            self.assertTrue(res["outcome"].startswith("HOLD"), key)
            self.assertTrue(any(f"carto.{key}" in f for f in res["findings"]), (key, res["findings"]))

    def test_the_init_order_defect_is_caught_at_the_opening_record(self):
        log = self.truth()
        zero = bc.Carto(0, 0); zero.render()
        log["loop_records"][0]["carto"]["map_sha256"] = zero.map_sha256
        log["loop_records"][0]["carto"]["content_sha256"] = zero.content_sha256
        res = self.adjudicate(log)
        self.assertTrue(res["outcome"].startswith("HOLD"))
        self.assertTrue(any("seq 1 (baseline)" in f for f in res["findings"]), res["findings"])

    def test_a_short_run_and_a_late_span_are_holds(self):
        res = self.adjudicate(synthetic_log(self.m, PLAN, bm.fixture("truth"), n=100, kind="STOPPED"))
        self.assertTrue(any(f.startswith("completion:") for f in res["findings"]))
        res = self.adjudicate(self.truth(), span_s=PLAN["session_timeout_s"] + 1)
        self.assertTrue(any(f.startswith("deadline:") for f in res["findings"]))

    def test_a_dropout_fabric_fails_recall_and_names_it(self):
        res = self.adjudicate(synthetic_log(self.m, PLAN, bm.fixture("dropout", seed=2)))
        self.assertTrue(any(f.startswith("verifier: recall") for f in res["findings"]))
        self.assertTrue(any("anomalies" in f for f in res["findings"]))

    def test_instrument_findings_propagate(self):
        res = self.adjudicate(self.truth(), findings=["missing REC for seq [7]"])
        self.assertTrue(res["outcome"].startswith("HOLD"))
        self.assertIn("missing REC for seq [7]", res["findings"])

    # ---- every exact gate, from the entry point
    def test_every_exact_metric_gate_fires_from_the_entry_point(self):
        cases = (
            ("snapshots", ("probes_to_full_confirmation",), 302, "probes to full confirmation"),
            ("snapshots", ("probes_to_full_recall_conf1",), 10, "probes to full recall"),
            ("snapshots", ("provisional", "recall"), 0.99, "provisional snapshot recall"),
            ("snapshots", ("provisional", "precision"), 0.99, "provisional snapshot precision"),
            ("snapshots", ("provisional", "calibration", "1", "accuracy"), 0.99, "provisional snapshot confidence-1 accuracy"),
            ("snapshots", ("provisional", "calibration", "1", "claimed"), 291, "provisional snapshot confidence-1 claimed"),
            ("snapshots", ("provisional", "calibration", "2", "claimed"), 1, "provisional snapshot confidence-2 cohort"),
            ("score", ("calibration", "2", "accuracy"), 0.99, "confidence-2 accuracy"),
            ("score", ("calibration", "2", "claimed"), 291, "confidence-2 claimed"),
            ("score", ("calibration", "1", "claimed"), 1, "confidence-1 cohort"),
            ("score", ("interaction", "pending"), 1, "interaction pending"),
            ("score", ("interaction", "deviations"), 1, "interaction deviations"),
            ("score", ("interaction", "pairs_tested"), 31, "interaction pairs tested"),
            ("score", ("unobserved_claims",), 1, "unobserved claims"),
            ("score", ("anomalies",), 1, "anomalies"),
            ("score", ("stratum_B", "recall"), 0.5, "stratum_B recall"),
            ("score", ("stratum_A", "precision"), 0.5, "stratum_A precision"),
            ("score", ("claimed",), 291, "claimed"),
        )
        for func, path, value, words in cases:
            with tweaked(func, path, value):
                res = self.adjudicate(self.truth())
            self.assertTrue(res["outcome"].startswith("HOLD"), (path, res["outcome"]))
            self.assertTrue(any(words in f for f in res["findings"]), (path, res["findings"]))
        with tweaked("snapshots", ("provisional",), None):
            res = self.adjudicate(self.truth())
        self.assertTrue(any("no provisional snapshot" in f for f in res["findings"]))

    def test_a_prediction_file_with_other_constants_is_a_finding(self):
        pred = copy.deepcopy(PRED)
        pred["expected_score"]["snapshots"]["probes_to_full_confirmation"] = 302
        d = Path(tempfile.mkdtemp()); pp = d / "prediction.json"
        text = json.dumps(pred, indent=1, sort_keys=True) + "\n"; pp.write_text(text)
        m = frozen_manifest(); m["prediction"]["sha256"] = hashlib.sha256(text.encode()).hexdigest()
        res = adj.adjudicate(write_dir(synthetic_log(m, PLAN, bm.fixture("truth"))), m, PLAN, pred, MSHA, require_git=False,
                             p3_layer=stub_layer(), prediction_path=pp, qualification_check=NOQ)
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"])
        self.assertTrue(any("prediction.expected_score.snapshots.probes_to_full_confirmation" in f for f in res["findings"]))

    # ---- the map's validation, from the entry point
    def test_a_schema_finding_survives_to_the_outcome(self):
        with mock.patch.object(adj, "schema_findings", lambda doc, schema_path=None: ["self_map_v2 schema: forced"]):
            res = self.adjudicate(self.truth())
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"])
        self.assertIn("self_map_v2 schema: forced", res["findings"])

    def test_no_validator_is_a_hold_from_the_entry_point(self):
        import builtins
        real = builtins.__import__
        def fake(name, *a, **k):
            if name == "jsonschema":
                raise ImportError("gone")
            return real(name, *a, **k)
        with mock.patch.object(builtins, "__import__", fake):
            res = self.adjudicate(self.truth())
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"])
        self.assertTrue(any("unvalidated" in f for f in res["findings"]))

    def test_a_broken_schema_or_semantics_is_a_hold_from_the_entry_point(self):
        real = adj.bv.expand
        def bad_expand(whole, addresses=None):
            doc = real(whole, addresses)
            doc["entries"][0]["polarity"] = "inverted"             # not in the schema
            return doc
        with mock.patch.object(adj.bv, "expand", bad_expand):
            res = self.adjudicate(self.truth())
        self.assertTrue(any("self_map_v2 schema: entries/0" in f for f in res["findings"]), res["findings"])
        def bad_sem(whole, addresses=None):
            doc = real(whole, addresses)
            doc["interaction_edges"][0]["result"] = "none"; doc["interaction_edges"][1] = dict(doc["interaction_edges"][0])
            return doc
        with mock.patch.object(adj.bv, "expand", bad_sem):
            res = self.adjudicate(self.truth())
        self.assertTrue(any("semantics" in f and "repeats pair" in f for f in res["findings"]), res["findings"])

    def test_semantic_rules_name_every_illegal_shape(self):
        res = self.adjudicate(self.truth()); doc = res["self_map_v2"]
        self.assertEqual(adj.bv.semantic_findings(doc, budget=PLAN["budget"]), [])
        def bad(mut):
            d = copy.deepcopy(doc); mut(d); return adj.bv.semantic_findings(d, budget=PLAN["budget"])
        self.assertTrue(any("entries" in f for f in bad(lambda d: d["entries"].pop())))
        self.assertTrue(any("repeated" in f for f in bad(lambda d: d["entries"].__setitem__(1, dict(d["entries"][0])))))
        self.assertTrue(any("pinned universe" in f for f in bad(lambda d: d["entries"][3].__setitem__("address", "0x0/0/0"))))
        self.assertTrue(any("illegal combination" in f for f in bad(lambda d: d["entries"][3].__setitem__("confidence", 0))))
        self.assertTrue(any("confirmed confidence vs code evidence" in f for f in bad(lambda d: d["entries"][3].__setitem__("confidence", 1))))
        self.assertTrue(any("illegal combination" in f for f in bad(lambda d: d["entries"][3].__setitem__("observed_transition", None))))
        self.assertTrue(any("relation range" in f for f in bad(lambda d: d["entries"][3]["relation"].__setitem__("init_index", 64))))
        self.assertTrue(any("code_probe_seqs" in f for f in bad(lambda d: d["code_probe_seqs"].__setitem__(0, d["code_probe_seqs"][1]))))
        self.assertTrue(any("cites a code probe" in f for f in bad(lambda d: d["entries"][3]["evidence"]["code_probe_seqs"].append(999))))
        self.assertTrue(any("interaction edges" in f for f in bad(lambda d: d["interaction_edges"].pop())))
        self.assertTrue(any("pending" in f for f in bad(lambda d: d["interaction_edges"][0].__setitem__("result", "pending"))))
        self.assertTrue(any("illegal" in f for f in bad(lambda d: d["interaction_edges"][0].__setitem__("b", d["interaction_edges"][0]["a"]))))
        self.assertTrue(any("record_seq" in f for f in bad(lambda d: d["interaction_edges"][0].__setitem__("record_seq", 1))))
        self.assertTrue(any("budget" in f for f in bad(lambda d: d.__setitem__("budget", 1))))


class Binding(unittest.TestCase):
    def test_the_default_refuses_without_a_qualification_record(self):
        m = frozen_manifest(); m["carrier"]["qualification"] = None
        res = adj.adjudicate(write_dir(synthetic_log(m, PLAN, bm.fixture("truth"))), m, PLAN, PRED, MSHA,
                             require_git=False, p3_layer=stub_layer())
        self.assertTrue(res["outcome"].startswith("REFUSED"))
        self.assertIn("qualification", res["outcome"])
        m["carrier"]["qualified"] = True                      # a bare flag changes nothing
        res = adj.adjudicate(write_dir(synthetic_log(m, PLAN, bm.fixture("truth"))), m, PLAN, PRED, MSHA,
                             require_git=False, p3_layer=stub_layer())
        self.assertTrue(res["outcome"].startswith("REFUSED"))

    def test_draft_manifest_refuses(self):
        m = copy.deepcopy(MANIFEST); m["prereg"]["sha256"] = None; m["prereg"]["frozen"] = None
        res = adj.adjudicate(write_dir(synthetic_log(m, PLAN, bm.fixture("truth"))), m, PLAN, PRED, MSHA,
                             require_git=False, p3_layer=stub_layer(), qualification_check=NOQ)
        self.assertTrue(res["outcome"].startswith("REFUSED"))
        self.assertIn("not frozen", res["outcome"])

    def test_the_committed_manifest_is_frozen_to_the_documents_bytes_and_refuses_at_the_qualification(self):
        self.assertTrue(MANIFEST["prereg"]["frozen"])
        self.assertEqual(hashlib.sha256((R / MANIFEST["prereg"]["path"]).read_bytes()).hexdigest(), MANIFEST["prereg"]["sha256"])
        res = adj.adjudicate(write_dir(synthetic_log(MANIFEST, PLAN, bm.fixture("truth"))), MANIFEST, PLAN, PRED, MSHA,
                             require_git=False, p3_layer=stub_layer())
        self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("no carrier.qualification", res["outcome"])

    def test_every_binding_and_identity_field_is_checked(self):
        m = frozen_manifest()
        cases = (("binding", "session", "S"), ("binding", "master_seed", 1281816666), ("binding", "b1_manifest_sha256", "d" * 64),
                 ("binding", "psoracle_commit", "0" * 40), ("ident", "carto_version", "carto-v0"), ("ident", "probe_budget", 5),
                 ("ident", "carrier_variant", "0x00000000"), ("ident", "carrier_sha256", "e" * 64))
        for where, key, value in cases:
            log = synthetic_log(m, PLAN, bm.fixture("truth"))
            (log["l6"]["binding"] if where == "binding" else log["app_identity"])[key] = value
            res = adj.adjudicate(write_dir(log), m, PLAN, PRED, MSHA, require_git=False, p3_layer=stub_layer(), qualification_check=NOQ)
            self.assertTrue(res["outcome"].startswith("REFUSED"), (key, res["outcome"]))
            self.assertIn(key, res["outcome"])

    def test_the_logged_inputs_must_be_the_pinned_plan_prediction_and_pin_table(self):
        m = frozen_manifest()
        for k in ("plan_sha256", "prediction_sha256", "pins_sha256"):
            log = synthetic_log(m, PLAN, bm.fixture("truth"))
            log["l6"]["inputs"][k] = "0" * 64
            res = adj.adjudicate(write_dir(log), m, PLAN, PRED, MSHA, require_git=False, p3_layer=stub_layer(), qualification_check=NOQ)
            self.assertTrue(res["outcome"].startswith("REFUSED"), (k, res["outcome"])); self.assertIn(k, res["outcome"])
        log = synthetic_log(m, PLAN, bm.fixture("truth")); del log["l6"]["inputs"]
        res = adj.adjudicate(write_dir(log), m, PLAN, PRED, MSHA, require_git=False, p3_layer=stub_layer(), qualification_check=NOQ)
        self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("inputs", res["outcome"])

    def test_a_preregistration_document_edited_after_the_freeze_refuses(self):
        m = frozen_manifest()
        log = synthetic_log(m, PLAN, bm.fixture("truth"))
        res = adj.adjudicate(write_dir(log), m, PLAN, PRED, MSHA, require_git=False, p3_layer=stub_layer(), qualification_check=NOQ)
        self.assertEqual(res["outcome"], "PASS", res["outcome"])
        (R / m["prereg"]["path"]).write_text("# fixture preregistration, edited after the freeze\n")
        res = adj.adjudicate(write_dir(log), m, PLAN, PRED, MSHA, require_git=False, p3_layer=stub_layer(), qualification_check=NOQ)
        self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("changed after the freeze", res["outcome"])
        (R / m["prereg"]["path"]).unlink()
        res = adj.adjudicate(write_dir(log), m, PLAN, PRED, MSHA, require_git=False, p3_layer=stub_layer(), qualification_check=NOQ)
        self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("absent", res["outcome"])
        freeze_doc(m)                                            # the fixture document is restored for the other tests

    def test_a_manifest_sha_other_than_the_logs_refuses(self):
        m = frozen_manifest()
        log = synthetic_log(m, PLAN, bm.fixture("truth"))
        res = adj.adjudicate(write_dir(log), m, PLAN, PRED, "f" * 64, require_git=False, p3_layer=stub_layer(), qualification_check=NOQ)
        self.assertTrue(res["outcome"].startswith("REFUSED"))
        self.assertIn("b1_manifest_sha256", res["outcome"])


class Exports(unittest.TestCase):
    """The evidence set is checked INSIDE adjudicate(): an incomplete export table, a
    missing table, a status key missing, or a file that does not hash to the table is a
    refusal — never a verdict over a subset of the evidence (owner's review of v2.4)."""

    def setUp(self):
        self.m = frozen_manifest(); self.log = synthetic_log(self.m, PLAN, bm.fixture("truth"))

    def adj(self, d):
        return adj.adjudicate(d, self.m, PLAN, PRED, MSHA, require_git=False, p3_layer=stub_layer(), qualification_check=NOQ)

    def test_a_complete_export_table_passes_and_an_incomplete_one_refuses(self):
        self.assertEqual(self.adj(write_dir(self.log))["outcome"], "PASS")
        res = self.adj(write_dir(self.log, exports_ok=False))
        self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("console.log=INCOMPLETE", res["outcome"])

    def test_a_missing_table_a_missing_status_key_and_a_drifted_file_refuse(self):
        d = write_dir(self.log); (d / "exports.json").unlink()
        res = self.adj(d); self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("no exports.json", res["outcome"])
        d = write_dir(self.log); doc = json.loads((d / "exports.json").read_text()); del doc["statuses"]["console.ts.log"]
        (d / "exports.json").write_text(json.dumps(doc))
        res = self.adj(d); self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("statuses are not exactly", res["outcome"])
        d = write_dir(self.log); doc = json.loads((d / "exports.json").read_text()); doc["complete"] = False
        (d / "exports.json").write_text(json.dumps(doc))
        res = self.adj(d); self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("complete is not true", res["outcome"])
        d = write_dir(self.log); (d / "console.log").write_bytes(b"edited after the export\n")
        res = self.adj(d); self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("console.log", res["outcome"]); self.assertIn("does not hash", res["outcome"])
        d = write_dir(self.log); (d / "audits.json").unlink()
        res = self.adj(d); self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("audits.json", res["outcome"])

    def test_the_manifest_structure_is_the_declared_schema_not_whatever_it_lists(self):
        """The owner's v2.4.1 counter-example: console.log and its entry removed, everything
        else untouched (statuses ok, complete true) — refused; an empty or absent files
        table, a malformed entry, a status table with an extra or a missing key, a wrong
        schema: each refused by name."""
        def mutate(mut, *words):
            d = write_dir(self.log); doc = json.loads((d / "exports.json").read_text()); mut(d, doc)
            (d / "exports.json").write_text(json.dumps(doc))
            res = self.adj(d); self.assertTrue(res["outcome"].startswith("REFUSED"), res["outcome"])
            for w in words:
                self.assertIn(w, res["outcome"])
        mutate(lambda d, doc: ((d / "console.log").unlink(), doc["files"].pop("console.log")), "files are not exactly")
        mutate(lambda d, doc: doc["files"].pop("console.log"), "files are not exactly")           # the file still there, the entry gone
        mutate(lambda d, doc: doc.__setitem__("files", {}), "files are not exactly")
        mutate(lambda d, doc: doc.pop("files"), "files are not exactly")
        mutate(lambda d, doc: doc["files"]["run_log.json"].__setitem__("sha256", "zz" * 32), "run_log.json is malformed")
        mutate(lambda d, doc: doc["files"]["run_log.json"].__setitem__("bytes", doc["files"]["run_log.json"]["bytes"] + 1), "run_log.json does not hash / size")
        mutate(lambda d, doc: doc["files"]["timeline.json"].__setitem__("bytes", None), "timeline.json is malformed")
        mutate(lambda d, doc: doc["files"]["audits.json"].__setitem__("status", "PARTIAL: recs"), "audits.json is malformed")
        mutate(lambda d, doc: doc["statuses"].__setitem__("extra", "ok"), "statuses are not exactly")
        mutate(lambda d, doc: doc["statuses"].pop("session_summary"), "statuses are not exactly")
        mutate(lambda d, doc: doc.__setitem__("schema_version", "0.9.0"), "not a b1_session_exports")
        mutate(lambda d, doc: doc.__setitem__("files", "nope"), "files are not exactly")


class Pins(unittest.TestCase):
    """The pins are verified INSIDE adjudicate(): a runner that checked them at preflight
    and a file that drifted since are refused at adjudication time."""

    def setUp(self):
        self.m = frozen_manifest()
        self.log = synthetic_log(self.m, PLAN, bm.fixture("truth"))

    def test_the_committed_pins_verify_through_the_entry_point(self):
        res = adj.adjudicate(write_dir(self.log), self.m, PLAN, PRED, MSHA, require_git=False, p3_layer=stub_layer(), qualification_check=NOQ)
        self.assertEqual(res["outcome"], "PASS", res["outcome"])

    def test_a_plan_that_drifted_after_preflight_is_refused(self):
        d = Path(tempfile.mkdtemp()); pp = d / "plan.json"
        drifted = copy.deepcopy(PLAN); drifted["budget"] = 332
        pp.write_text(json.dumps(drifted))
        res = adj.adjudicate(write_dir(self.log), self.m, PLAN, PRED, MSHA, require_git=False, p3_layer=stub_layer(),
                             plan_path=pp, qualification_check=NOQ)
        self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("plan pin", res["outcome"])
        # the file hashes but the object the caller holds is another
        res = adj.adjudicate(write_dir(self.log), self.m, drifted, PRED, MSHA, require_git=False, p3_layer=stub_layer(), qualification_check=NOQ)
        self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("not the pinned file", res["outcome"])

    def test_a_pin_table_that_drifted_after_preflight_is_refused(self):
        d = Path(tempfile.mkdtemp()); tbl = d / "pins.json"
        t = json.loads(bp.PINS.read_text()); t["files"]["host/b1_adjudicate.py"] = "0" * 64
        tbl.write_text(json.dumps(t, indent=1, sort_keys=True) + "\n")
        m = copy.deepcopy(self.m); m["pins"]["sha256"] = bp.sha256_of(tbl)
        res = adj.adjudicate(write_dir(self.log), m, PLAN, PRED, MSHA, require_git=False, p3_layer=stub_layer(),
                             pins_path=tbl, qualification_check=NOQ)
        self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("pins", res["outcome"])
        m["pins"]["sha256"] = "0" * 64
        res = adj.adjudicate(write_dir(self.log), m, PLAN, PRED, MSHA, require_git=False, p3_layer=stub_layer(), qualification_check=NOQ)
        self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("pins", res["outcome"])

    def test_check_pins_refuses_a_wrong_plan_or_pins_table(self):
        m = copy.deepcopy(MANIFEST)
        m["plan"]["sha256"] = "0" * 64
        with self.assertRaises(adj.Refusal):
            adj.check_pins(m, R / "evidence/b1/plan.json", R / "evidence/b1/prediction.json")
        adj.check_pins(MANIFEST, R / "evidence/b1/plan.json", R / "evidence/b1/prediction.json")


if __name__ == "__main__":
    unittest.main()

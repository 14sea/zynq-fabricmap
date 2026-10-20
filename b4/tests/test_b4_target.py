"""b4/host/b4_target.py — the target setup of task-v0.2 (docs/b4_architecture.md section 7.1; the owner's rulings of 2026-10-20,
choices 2-3 and the target-setup contract): the private plan from the seed, the rule and the mapping (deterministic; the planted
configuration a flip-flop one); the two setup observations through the execution port with the full q grid and the formal source
identity; the PublicTask rebuilt from the kept records (no seed, no planted genome; the commitment to the two observations in its
digest); the planted configuration scoring its own ceilings; the offline reconstruction naming every tamper; a None in a planted
trace refused, never narrowed. The seeds are exposed values; nothing production-like is derived. No skip."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host", R / "b4/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_execution as ex  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402
import b4_landscape as bl  # noqa: E402
import b4_sim_schema as sc  # noqa: E402
import b4_target as bt  # noqa: E402
from b4_test_fixtures import mechanics_fabric, v02_setup  # noqa: E402

L, O = 7, 11


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m, cls.h = bm.site_mapping(), hy.load()
        cls.fab = fm.Fabric(cls.m, cls.h)
        cls.task, cls.plan, cls.r1, cls.r2 = v02_setup(L, cls.fab, O)
        cls.prov = sc.formal_provenance()

    def expect(self):
        return {"pair": 0, "landscape_seed": L, "operator_seed": O}

    def digests(self):
        return {"task_setup.json": "1" * 64, "target_search.json": "2" * 64, "target_holdout.json": "3" * 64}


class ThePlan(Base):
    def test_the_plan_is_the_seed_s_the_rule_s_and_the_mapping_s(self):
        p = self.plan
        bit = self.m.genome_bit(self.m.address_of(None, "storage_kind"))
        self.assertEqual(bt.storage_kind_bit(self.m), bit)
        self.assertEqual((p["pair"], p["landscape_seed"], p["operator_seed"], p["task_version"], p["status"], p["planned"]), (0, L, O, bl.TASK_VERSION, "in_progress", ["target", "target_holdout"]))
        self.assertEqual(p["rule"], {"text": bl.PLANTED_RULE, "salt": bl.SALT_TARGET, "storage_kind_bit": bit, "storage_kind_address": self.m.addresses[bit], "n_bits": 21, "base_genome": 0})
        self.assertEqual(p["planted_genome"], bl.planted_genome(L, bit, 21))
        self.assertEqual((p["planted_genome"] >> bit) & 1, 0, "T-i: a flip-flop configuration")
        self.assertEqual(p["planted_genome_hex"], ex.genome_hex(p["planted_genome"], 21))
        self.assertEqual(p["planted_config_sha256"], ex.sha256_json(ex.genome_to_config(p["planted_genome"], self.m.addresses)))
        self.assertIs(p["planted_is_base"], p["planted_genome"] == 0)
        parts = bl.public_parts(L)
        self.assertEqual(p["public"]["stimulus_sha256"], ex.sha256_json(list(parts["stimulus"])))
        self.assertEqual((p["public"]["ceiling"], p["public"]["holdout_ceiling"], p["public"]["search_steps"], p["public"]["holdout_steps"]), (64, 80, 9, 11))
        self.assertEqual(bt.plan(0, L, O, self.m), dict(p), "deterministic")
        self.assertNotEqual(bt.plan(0, 8, O, self.m)["planted_genome"], p["planted_genome"])
        self.assertEqual(sc.task_setup_findings(dict(p, written_utc="x")), [])
        self.assertEqual(bt.SETUP_COST, {"target": 1, "target_holdout": 1}); self.assertEqual(bt.PHASES, ("target", "target_holdout"))
        self.assertEqual(bt.SETUP_FILES, ("task_setup.json", "target_search.json", "target_holdout.json", "task.json"))

    def test_the_setup_observations_carry_the_grid_and_the_formal_source(self):
        for rec, phase, stim in ((self.r1, "target", bl.public_parts(L)["stimulus"]), (self.r2, "target_holdout", bl.public_parts(L)["holdout_stimulus"])):
            self.assertEqual((rec["phase"], rec["genome"], rec["config_sha256"]), (phase, self.plan["planted_genome"], self.plan["planted_config_sha256"]))
            self.assertEqual(rec["stimulus_sha256"], ex.sha256_json(list(stim)))
            self.assertEqual(len(rec["q_grid"]), len(stim)); self.assertEqual(ex.sha256_json(rec["q_grid"]), rec["trace_sha256"])
            self.assertEqual(ex.provenance_findings(rec["provenance"]), []); self.assertEqual(ex.sha256_json(rec["provenance"]), rec["provenance_sha256"])
            self.assertEqual(rec["provenance"], self.prov, "the formal source")
            self.assertIs(rec["fixture"], False); self.assertEqual(rec["fabric_kind"], "truth")
            self.assertEqual(sc.target_observation_findings({"schema": bt.TARGET_SCHEMA[0], "schema_version": bt.TARGET_SCHEMA[1], "pair": 0, "written_utc": "x", **rec}, phase), [])
            self.assertTrue(all(c in (0, 1) for row in rec["q_grid"] for c in row), "a flip-flop configuration reads every element: no None in a planted trace")
        with self.assertRaises(ValueError):
            bt.observe_target(ex.ObservationPort(self.fab), 0, bl.public_parts(L)["stimulus"], self.m.addresses, "search")

    def test_the_task_is_rebuilt_from_the_records_and_the_planted_configuration_scores_its_ceilings(self):
        task, doc = bt.finish(self.plan, self.r1, self.r2, self.digests())
        self.assertEqual(task.digest(), self.task.digest()); self.assertEqual(task, bt.rebuild_task(self.plan, self.r1, self.r2))
        self.assertFalse(hasattr(task, "seed")); self.assertEqual(task.target_source_sha256, bt.target_source_sha256(self.r1, self.r2))
        self.assertEqual(list(task.target), [self.r1["q_grid"][s][e] for (s, e) in task.mask])
        self.assertEqual(doc["planted_search_score"], {"fitness": 64, "none_cells": 0, "ceiling": 64}); self.assertEqual(doc["planted_holdout_score"], {"fitness": 80, "none_cells": 0, "ceiling": 80})
        self.assertEqual((doc["pair"], doc["landscape_seed"], doc["operator_seed"], doc["task_digest"], doc["status"]), (0, L, O, task.digest(), "complete"))
        self.assertEqual(doc["setup_files_sha256"], self.digests())
        self.assertEqual(bt.task_from_dict(doc["public_task"]), task, "the record round-trips to the same task")
        self.assertEqual(sc.task_findings(dict(doc, written_utc="x")), [])
        self.assertNotIn("landscape_seed", doc["public_task"]); self.assertNotIn("planted_genome", doc["public_task"])
        # the typed validators of the setup records refuse by name
        bad = copy.deepcopy(doc); bad["planted_search_score"]["fitness"] = 63
        self.assertTrue(any("ceiling" in x for x in sc.task_findings(dict(bad, written_utc="x"))))
        bad = copy.deepcopy(doc); bad["task_digest"] = "0" * 64
        self.assertTrue(any("task_digest" in x for x in sc.task_findings(dict(bad, written_utc="x"))))
        bad = copy.deepcopy(self.plan); bad["planted_genome"] |= 1 << bad["rule"]["storage_kind_bit"]
        self.assertTrue(any("flip-flop" in x for x in sc.task_setup_findings(dict(bad, written_utc="x"))))
        bad = copy.deepcopy(self.plan); bad["status"] = "complete"
        self.assertTrue(any("in_progress" in x for x in sc.task_setup_findings(dict(bad, written_utc="x"))))
        rec = copy.deepcopy(self.r1); rec["provenance"]["fabric"]["kind"] = "dropout"; rec["provenance_sha256"] = ex.sha256_json(rec["provenance"]); rec["fabric_kind"] = "dropout"
        self.assertTrue(any("formal" in x for x in sc.target_observation_findings({"schema": bt.TARGET_SCHEMA[0], "schema_version": bt.TARGET_SCHEMA[1], "pair": 0, "written_utc": "x", **rec}, "target")))
        self.assertTrue(sc.target_observation_findings({"schema": bt.TARGET_SCHEMA[0], "schema_version": bt.TARGET_SCHEMA[1], "pair": 0, "written_utc": "x", **self.r1}, "target_holdout"), "the phase is bound to the file")
        src = bt.source_fields(self.r1)
        self.assertEqual(set(src), {"phase", "config_sha256", "stimulus_sha256", "trace_sha256", "provenance_sha256"}, "the commitment covers the source fields, never the grid itself")

    def test_a_none_in_a_planted_trace_is_refused_never_narrowed(self):
        r1 = copy.deepcopy(self.r1); r1["q_grid"][3][2] = None; r1["trace_sha256"] = ex.sha256_json(r1["q_grid"])
        with self.assertRaises(bl.TargetRefusal):
            bt.rebuild_task(self.plan, r1, self.r2)
        with self.assertRaises(bl.TargetRefusal):
            bt.finish(self.plan, r1, self.r2, self.digests())
        f = bt.setup_findings(self.plan, r1, self.r2, bt.finish(self.plan, self.r1, self.r2, self.digests())[1], self.m, self.prov, self.expect())
        self.assertTrue(any("cannot be rebuilt" in x for x in f), f)


class TheReturn(Base):
    """R2 / R4 of the owner's review of 04385ae: what the port RETURNS is held in full before it becomes an observation — any None (the
    init readout included), any non-0/1 cell, a malformed step, a non-object, a short grid, a malformed or drifting source identity —
    raises ReturnRefusal CARRYING the returned object (the harness quarantines it); a kept record with a None is named by the validator
    and by the offline reconstruction; the quarantine context carries the phase, the planted configuration and the digests."""

    def alter(self, mutate, phase="target", expected=None):
        class P(ex.ObservationPort):
            def observe(self_, config, stimulus):
                return mutate(super().observe(config, stimulus))
        parts = bl.public_parts(L)
        with self.assertRaises(bt.ReturnRefusal) as cm:
            bt.observe_target(P(self.fab), self.plan["planted_genome"], parts["stimulus"] if phase == "target" else parts["holdout_stimulus"], self.m.addresses, phase, expected)
        return cm.exception

    def test_every_bad_return_is_refused_with_the_object_attached(self):
        def init_none(t):
            t["steps"][0]["q_after"][0] = None; return t
        e = self.alter(init_none); self.assertTrue(any("step 0, element 0: None" in x for x in e.findings), e.findings); self.assertIsNone(e.returned["steps"][0]["q_after"][0])

        def cell2(t):
            t["steps"][3]["q_after"][4] = 2; return t
        e = self.alter(cell2); self.assertTrue(any("2 is not 0 / 1" in x for x in e.findings), e.findings)

        def float_cell(t):                                            # C1 (the owner's review of b29b0fb): 0.0 == 0 in Python; the check is type-exact
            t["steps"][0]["q_after"][0] = float(t["steps"][0]["q_after"][0]); return t
        e = self.alter(float_cell); self.assertTrue(any("is not 0 / 1 (an int)" in x for x in e.findings), e.findings); self.assertIsInstance(e.returned["steps"][0]["q_after"][0], float)

        def bool_cell(t):
            t["steps"][0]["q_after"][1] = bool(t["steps"][0]["q_after"][1]); return t
        e = self.alter(bool_cell); self.assertTrue(any("is not 0 / 1 (an int)" in x for x in e.findings), e.findings)
        parts_ = bl.public_parts(L); raw = bt.observe_raw(ex.ObservationPort(self.fab), self.plan["planted_genome"], parts_["stimulus"], self.m.addresses)
        self.assertEqual(bt.record_from_trace(raw, self.plan["planted_genome"], parts_["stimulus"], self.m.addresses, "target"), self.r1, "the three steps compose to observe_target")

        def malformed(t):
            t["steps"][1] = {"owner_raw_marker": "m"}; return t
        e = self.alter(malformed); self.assertTrue(any("no q_after" in x for x in e.findings)); self.assertEqual(e.returned["steps"][1]["owner_raw_marker"], "m")
        e = self.alter(lambda t: ["not", "an", "object"]); self.assertTrue(any("not an object" in x for x in e.findings)); self.assertEqual(e.returned, ["not", "an", "object"])

        def short(t):
            t["steps"] = t["steps"][:2]; return t
        e = self.alter(short); self.assertTrue(any("steps returned" in x for x in e.findings))

        def bad_prov(t):
            t["fabric"] = {"kind": "truth"}; return t
        e = self.alter(bad_prov); self.assertTrue(any("source identity is malformed" in x for x in e.findings))
        good = ex.sha256_json(self.r1["provenance"])

        def drift(t):
            t["fabric"] = dict(t["fabric"], effect_sha256="a" * 64); return t
        e = self.alter(drift, "target_holdout", good); self.assertTrue(any("drift" in x for x in e.findings)); self.assertEqual(e.returned["fabric"]["effect_sha256"], "a" * 64)
        parts = bl.public_parts(L)
        genuine = ex.ObservationPort(self.fab).observe(ex.genome_to_config(self.plan["planted_genome"], self.m.addresses), list(parts["stimulus"]))
        self.assertEqual(bt.observation_findings(genuine, len(parts["stimulus"]), good), [], "the genuine return is clean")
        self.assertTrue(bt.observation_findings(genuine, len(parts["stimulus"]), "0" * 64), "the same return against another expected identity: a drift")
        self.assertEqual(bt.observation_findings(None, 3), ["the returned object is not an object (NoneType)"])
        self.assertTrue(isinstance(e, ex.SourceRefusal), "a ReturnRefusal is a SourceRefusal by name")

    def test_the_quarantine_context_and_a_non_serialisable_return(self):
        parts = bl.public_parts(L)
        c = bt.quarantine_context("target", self.plan["planted_genome"], self.m.addresses, parts["stimulus"], {"steps": [1]}, "0" * 64)
        self.assertEqual(set(c), sc.QUARANTINE_CONTEXT_KEYS); self.assertEqual(c["returned_sha256"], ex.sha256_json({"steps": [1]}))
        self.assertEqual((c["config_sha256"], c["stimulus_sha256"], c["phase"], c["expected_provenance_sha256"]), (self.plan["planted_config_sha256"], self.plan["public"]["stimulus_sha256"], "target", "0" * 64))
        c = bt.quarantine_context("target_holdout", self.plan["planted_genome"], self.m.addresses, parts["holdout_stimulus"], {"x": float("nan")}, None)
        self.assertIsNone(c["returned_sha256"]); self.assertIsNone(c["expected_provenance_sha256"]); self.assertEqual(c["stimulus_sha256"], self.plan["public"]["holdout_stimulus_sha256"])

    def test_a_kept_record_with_a_none_is_named_by_the_validator_and_the_reconstruction(self):
        r1 = copy.deepcopy(self.r1); r1["q_grid"][0][0] = None; r1["trace_sha256"] = ex.sha256_json(r1["q_grid"])      # the init readout: outside the scored mask cells
        self.assertNotIn((0, 0), set(self.task.mask), "the cell is not a scored one: the mask does not narrow the check")
        self.assertTrue(any("None cell" in x for x in sc.target_observation_findings({"schema": bt.TARGET_SCHEMA[0], "schema_version": bt.TARGET_SCHEMA[1], "pair": 0, "written_utc": "x", **r1}, "target")))
        f = bt.setup_findings(self.plan, r1, self.r2, None, self.m, self.prov, self.expect())
        self.assertTrue(any("None cell" in x for x in f), f)


class TheReconstruction(Base):
    def setUp(self):
        self.task_doc = bt.finish(self.plan, self.r1, self.r2, self.digests())[1]

    def findings(self, plan=None, r1=None, r2=None, task_doc="same", prov="same", expect="same"):
        return bt.setup_findings(plan or self.plan, self.r1 if r1 is None else r1, self.r2 if r2 is None else r2,
                                 self.task_doc if task_doc == "same" else task_doc, self.m, self.prov if prov == "same" else prov, self.expect() if expect == "same" else expect)

    def test_genuine_records_reconstruct_clean_with_or_without_the_task(self):
        self.assertEqual(self.findings(), [])
        self.assertEqual(self.findings(task_doc=None), [], "a setup without its task yet (partial) is clean as far as it goes")
        self.assertEqual(bt.setup_findings(self.plan, self.r1, None, None, self.m, self.prov, self.expect()), [], "one observation so far")
        self.assertEqual(bt.setup_findings(self.plan, None, None, None, self.m, self.prov, self.expect()), [], "the plan alone")

    def test_every_tamper_is_named(self):
        def named(needle, **kw):
            f = self.findings(**kw)
            self.assertTrue(any(needle in x for x in f), (needle, f))
        p = copy.deepcopy(self.plan); p["planted_genome"] ^= 1 << 3; p["planted_genome_hex"] = ex.genome_hex(p["planted_genome"], 21)
        named("not what the seed, the rule and the mapping give", plan=p)
        p = copy.deepcopy(self.plan); bit = p["rule"]["storage_kind_bit"]; p["planted_genome"] |= 1 << bit
        named("not a flip-flop configuration", plan=p)
        p = copy.deepcopy(self.plan); p["rule"]["salt"] = 1
        named("not the fixed rule", plan=p)
        named("not the planned pair / seeds", expect={"pair": 0, "landscape_seed": 8, "operator_seed": O})
        r = copy.deepcopy(self.r1); r["q_grid"][1][0] = 1 - r["q_grid"][1][0]
        named("does not hash to trace_sha256", r1=r)
        r = copy.deepcopy(self.r1); r["q_grid"][1][0] = 1 - r["q_grid"][1][0]; r["trace_sha256"] = ex.sha256_json(r["q_grid"])
        named("not the task rebuilt from the setup records", r1=r)
        r = copy.deepcopy(self.r2); r["stimulus_sha256"] = "0" * 64
        named("not under the task's target_holdout stimulus", r2=r)
        r = copy.deepcopy(self.r1); r["genome"] ^= 1
        named("not the planted configuration", r1=r)
        r = copy.deepcopy(self.r1); r["phase"] = "target_holdout"
        named("phase", r1=r)
        r = copy.deepcopy(self.r1); r["provenance"]["fabric"]["kind"] = "dropout"; r["provenance_sha256"] = ex.sha256_json(r["provenance"]); r["fabric_kind"] = "dropout"
        named("not the formal one", r1=r)
        r = copy.deepcopy(self.r1); r["provenance"]["fabric"]["kind"] = "dropout"
        named("does not hash to provenance_sha256", r1=r)
        r = copy.deepcopy(self.r2); r["provenance_sha256"] = "0" * 64
        named("one source identity", r2=r)
        d = copy.deepcopy(self.task_doc); d["task_digest"] = "0" * 64
        named("not the rebuilt task's digest", task_doc=d)
        d = copy.deepcopy(self.task_doc); d["public_task"]["target"][0] = 1 - d["public_task"]["target"][0]
        named("not the task rebuilt from the setup records", task_doc=d)
        d = copy.deepcopy(self.task_doc); d["public_task"]["target_source_sha256"] = "0" * 64
        named("target_source_sha256 is not the commitment", task_doc=d)
        d = copy.deepcopy(self.task_doc); d["planted_search_score"]["fitness"] = 63
        named("planted scores are not the ones recomputed", task_doc=d)
        d = copy.deepcopy(self.task_doc); d["landscape_seed"] = 8
        named("not the plan's pair / seeds", task_doc=d)
        f = bt.setup_findings(self.plan, self.r1, None, self.task_doc, self.m, self.prov, self.expect())
        self.assertTrue(any("without both setup observations" in x for x in f), f)
        f = bt.setup_findings("not a plan", self.r1, self.r2, self.task_doc, self.m, self.prov, self.expect())
        self.assertTrue(f and all("raised" in x or "malformed" in x for x in f), "total: a malformed record is a finding, never an exception")

    def test_a_fixture_fabric_s_setup_is_named_against_the_formal_source(self):
        task, plan, r1, r2 = v02_setup(L, mechanics_fabric(), O)
        self.assertNotEqual(r1["provenance"], self.prov)
        f = bt.setup_findings(plan, r1, r2, None, self.m, self.prov, self.expect())
        self.assertTrue(any("not the formal one" in x for x in f), f)
        self.assertEqual(bt.setup_findings(plan, r1, r2, None, self.m, None, self.expect()), [], "with no formal source given, the records are consistent in themselves")


if __name__ == "__main__":
    unittest.main()

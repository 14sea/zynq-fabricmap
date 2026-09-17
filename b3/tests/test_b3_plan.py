"""b3/host/b3_plan.py (lifecycle 2) — the gate's numbers (a lifecycle-2 report accepted, lifecycle 1's
refused by name), the seed exclusion (every archived set, lifecycle 1's two sets, plus the gate's own
pairs), the labels, the split rule with the 0.85 margin, the arm order, the record arithmetic, the
prediction's determinism and structure with EVERY ledger entry embedded, the entry-level comparison
naming a tamper, one primary plus the secondary outcome, the stop rule on the primary alone, the CLI's
stop before any canonical write, and B3Q's frozen experiment.

The gate fixture: a report of the lifecycle-2 shape written into a temp directory, its seeds drawn
under the label `b3-gate-2` with the real exclusion (so the plan's re-derivation check holds), its
numbers the pilot's (B* = 1 000, N = 9) — a fixture, not a gate result."""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    sys.path.insert(0, str(p))
import b2_maps as bmaps  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_gate as b3g  # noqa: E402
import b3_online_arm as oa  # noqa: E402
import b3_plan as pl  # noqa: E402

LIFECYCLE1_GATE = R / "evidence/b3/gate/gate_report.json"
_TMP: Path | None = None
GATE: Path | None = None


def write_gate_fixture(d: Path, count: int = 3, b_star: int = 1000, n: int = 9, head: str = "f" * 40) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    excl, sources = b3g.gate_exclusion()
    master = bs.master_seed(b3g.GATE_LABEL, head)
    seeds = bs.pair_seeds(master, count, exclude=frozenset(excl))
    rows = [{"r": r, "landscape_seed": l, "operator_seed": o, "base_fit": 2, "arms": {}} for r, (l, o) in enumerate(seeds)]
    (d / "raw_F1.json").write_text(json.dumps({"fitness": "F1", "grid": list(b3g.GRID), "rows": rows}))
    rep = {"schema": "b3_gate_report", "schema_version": "2.0.0", "lifecycle": b3g.LIFECYCLE, "label": "fixture", "head_at_run": head,
           "thresholds": dict(b3g.THRESHOLDS), "architecture": {"path": "docs/b3_architecture.md", "sha256": "a" * 64, "last_commit": head},
           "control_x": {"permutation_sha256": "c" * 64}, "gate_fitness": "F1",
           "seeds": {"label": b3g.GATE_LABEL, "master_seed": master, "count": count, "excluded_sources": sources},
           "results": {"F1": {"pass": True, "b_star": b_star, "criteria": {"H5": {"required_pairs_N": n, "pass": True}},
                              "diagnostics": {"H9": {"alpha": 0.05, "delta2_by_budget_from_b_star": []}}}}}
    (d / "gate_report.json").write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n")
    return d / "gate_report.json"


def setUpModule():
    global _TMP, GATE
    _TMP = Path(tempfile.mkdtemp())
    GATE = write_gate_fixture(_TMP / "gate_2")


def tearDownModule():
    shutil.rmtree(_TMP, True)


class GateAndSeeds(unittest.TestCase):
    def test_lifecycle_2_labels(self):
        self.assertEqual(pl.SESSION_LABEL, "b3-session-2")
        self.assertEqual(pl.QUAL_LABEL, "b3-qualification-2")
        self.assertEqual(pl.GATE_REPORT, R / "evidence/b3/gate_2/gate_report.json")
        self.assertEqual(pl.PLAN_DIR, R / "evidence/b3")
        self.assertEqual(pl.qualification_master(), bs.master_seed("b3-qualification-2", pl.INSTRUMENT_COMMIT))

    def test_gate_inputs_accept_the_lifecycle_2_shape_and_carry_no_claim_condition(self):
        g = pl.gate_inputs(GATE)
        self.assertEqual((g["fitness"], g["budget_per_arm"], g["pairs"]), ("F1", 1000, 9))
        self.assertEqual(g["seeds"]["label"], "b3-gate-2")
        self.assertEqual(g["rules_version"], "architecture v0.3 §9")
        self.assertNotIn("H9_claim_condition", g)
        self.assertNotIn("H9", json.dumps(g))

    def test_gate_inputs_refuse_lifecycle_1s_report_by_name(self):
        with self.assertRaises(ValueError) as cm:
            pl.gate_inputs(LIFECYCLE1_GATE)
        self.assertIn("architecture v0.2.3 §9", str(cm.exception))
        # the rules version alone made current: the label still names it; the label made current too: the shape (H9 a criterion)
        rep = json.loads(LIFECYCLE1_GATE.read_text())
        rep["thresholds"]["rules_version"] = b3g.THRESHOLDS["rules_version"]
        d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, d, True)
        (d / "gate_report.json").write_text(json.dumps(rep))
        with self.assertRaises(ValueError) as cm:
            pl.gate_inputs(d / "gate_report.json")
        self.assertIn("b3-gate", str(cm.exception)); self.assertIn("b3-gate-2", str(cm.exception))
        rep["seeds"]["label"] = b3g.GATE_LABEL
        (d / "gate_report.json").write_text(json.dumps(rep))
        with self.assertRaises(ValueError) as cm:
            pl.gate_inputs(d / "gate_report.json")
        self.assertIn("lifecycle-2", str(cm.exception))
        # the fixture with its H5 pass removed: no plan
        fx = json.loads(GATE.read_text()); fx["results"]["F1"]["pass"] = False
        (d / "gate_report.json").write_text(json.dumps(fx))
        with self.assertRaises(ValueError):
            pl.gate_inputs(d / "gate_report.json")

    def test_session_seeds_avoid_every_archived_set_including_lifecycle_1s_and_the_gates(self):
        master, seeds, sources, excl = pl.session_seeds(9, GATE)
        self.assertEqual(master, bs.master_seed("b3-session-2", pl.INSTRUMENT_COMMIT))
        self.assertNotEqual(master, bs.master_seed("b3-session", pl.INSTRUMENT_COMMIT))
        self.assertEqual(len(seeds), 9)
        flat = {s for p in seeds for s in p}
        self.assertFalse(flat & excl)
        self.assertTrue(any("B3 gate" in k for k in sources))
        self.assertTrue(any("lifecycle 1 gate run 1" in k for k in sources))
        self.assertTrue(any("lifecycle 1 trial session pairs" in k for k in sources))
        raw = json.loads((GATE.parent / "raw_F1.json").read_text())["rows"]
        gate_flat = {row["landscape_seed"] for row in raw} | {row["operator_seed"] for row in raw}
        self.assertTrue(gate_flat <= excl); self.assertFalse(flat & gate_flat)
        raw1 = json.loads((R / "evidence/b3/gate/raw_F1.json").read_text())["rows"]
        self.assertFalse(flat & ({row["landscape_seed"] for row in raw1} | {row["operator_seed"] for row in raw1}))
        t_pred = json.loads((R / "evidence/b3/plan_trial_2026_09_17/prediction.json").read_text())
        pilot = {p["landscape_seed"] for p in t_pred["pairs"]} | {p["operator_seed"] for p in t_pred["pairs"]}
        self.assertTrue(pilot <= excl); self.assertFalse(flat & pilot)
        self.assertNotEqual([tuple(x) for x in seeds], [(p["landscape_seed"], p["operator_seed"]) for p in t_pred["pairs"]])
        m = json.loads((R / "manifests/b2_manifest.json").read_text())
        self.assertFalse(flat & {s for p in m["seeds"]["pairs"] for s in p})
        q = pl.qualification_seeds(seeds, GATE)
        self.assertEqual(len(q), 1)
        self.assertFalse({s for p in q for s in p} & (flat | excl))

    def test_the_gates_rows_must_carry_the_seeds_its_master_rederives(self):
        d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, d, True)
        p = write_gate_fixture(d)
        raw = json.loads((d / "raw_F1.json").read_text())
        raw["rows"][1]["operator_seed"] += 1
        (d / "raw_F1.json").write_text(json.dumps(raw))
        with self.assertRaises(ValueError):
            pl.session_seeds(9, p)


class SplitAndArithmetic(unittest.TestCase):
    def test_records(self):
        self.assertEqual(pl.records_per_pair(1000), 3003)
        self.assertEqual(pl.session_records(9, 1000), 2 + 27027)
        self.assertEqual(pl.records_per_pair(40), 123)
        self.assertEqual(pl.session_records(1, 40), 125)

    def test_arm_order_is_prefix_balanced(self):
        seq = [pl.arm_order(r) for r in range(9)]
        self.assertEqual(["".join(s) for s in seq[:6]], ["RFO", "FOR", "ORF", "ROF", "OFR", "FRO"])
        for n in (3, 6, 9):
            counts = {(arm, pos): 0 for arm in "RFO" for pos in range(3)}
            for r in range(n):
                for pos, arm in enumerate(pl.arm_order(r)):
                    counts[(arm, pos)] += 1
            self.assertEqual(len(set(counts.values())), 1, n)          # equal exactly when N is a multiple of 3
        counts = {(arm, pos): 0 for arm in "RFO" for pos in range(3)}
        for r in range(8):
            for pos, arm in enumerate(pl.arm_order(r)):
                counts[(arm, pos)] += 1
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)

    def test_split_rule_with_the_margin(self):
        u = pl.session_split(9, 1000, None)
        self.assertTrue(u["status"].startswith("UNDETERMINED"))
        self.assertEqual(u["calibration_margin"], 0.85)
        d = pl.session_split(9, 1000, 3000.0)
        self.assertEqual(d["status"], "DETERMINED")
        self.assertAlmostEqual(d["rate_for_split"], 2550.0)
        # at 2 550 / h the expected span of p pairs is (2 + 3003 p) x 3600 / 2550: p = 1 -> 4 242 s fits, p = 2 -> 8 482 s does not
        self.assertEqual(d["pairs_per_session_max"], 1)
        self.assertEqual(len(d["sessions"]), 9)
        self.assertEqual(d["total_records"], 9 * (2 + 3003))
        self.assertAlmostEqual(d["sessions"][0]["deadline_s"], 1.25 * 3005 * 3600 / 2550 + 600)
        self.assertEqual(pl.session_split(9, 1000, 3100.0 / 0.85)["pairs_per_session_max"], 2)
        self.assertEqual(pl.session_split(9, 1000, 3100.0)["pairs_per_session_max"], 1)
        inf = pl.session_split(9, 1000, 1000.0)
        self.assertEqual(inf["status"], "INFEASIBLE")
        for bad in (0, -1.0, float("nan"), float("inf"), True, "3000"):
            with self.assertRaises(pl.RateInvalid):
                pl.session_split(9, 1000, bad)


class Prediction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _m, cls.seeds, _s, _e = pl.session_seeds(2, GATE)
        cls.pred = pl.build_prediction("F1", 12, cls.seeds)

    def test_deterministic_and_structured_on_a_small_budget(self):
        a = self.pred
        b = pl.build_prediction("F1", 12, self.seeds)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual(a["fitness_sequence_length"], 2 * (3 * 12 + 3))
        self.assertEqual((a["schema_version"], a["lifecycle"]), (pl.SCHEMA_VERSION, 2))
        for p in a["pairs"]:
            self.assertEqual(set(p["runs"]), {"R", "F", "O"})
            self.assertEqual(p["runs"]["O"]["wrong_decodes"], 0)
            self.assertEqual(p["runs"]["O"]["anomalies"], 0)
            self.assertEqual(p["runs"]["O"]["ledger_entries"], 12)
            self.assertEqual(p["delta1_O_minus_R"], p["runs"]["O"]["best_train"] - p["runs"]["R"]["best_train"])
            self.assertEqual(p["delta2_O_minus_endtoend_F"], p["runs"]["O"]["best_train"] - p["runs"]["F"]["end_to_end_at_budget"])
            self.assertEqual(p["runs"]["F"]["end_to_end_at_budget"], p["base_train_fitness"])   # 12 <= 333: the base

    def test_every_ledger_entry_is_embedded(self):
        """Preregistration v0.3 §3 / §8 (a): pairs[r].runs.O.ledger holds every entry — specimen_ledger
        1.1.0, B* of them per run — not a digest and a count alone."""
        schema = json.loads((R / "b3/schemas/specimen_ledger.schema.json").read_text())
        required = schema["properties"]["entries"]["items"]["required"]
        for p in self.pred["pairs"]:
            o = p["runs"]["O"]
            self.assertEqual(o["budget"], 12)
            self.assertEqual(o["ledger_schema_version"], oa.LEDGER_SCHEMA_VERSION)
            self.assertEqual(len(o["ledger"]), 12)
            self.assertEqual(o["ledger_entries"], len(o["ledger"]))
            for k, e in enumerate(o["ledger"]):
                self.assertEqual(set(required) <= set(e), True, (k, set(required) - set(e)))
                self.assertEqual(e["seq"], k + 1)
            # the entries are what the digest digests, and the moves digest is over them
            import b3_online_map as om
            self.assertEqual(om.canonical_sha256(o["ledger"]), o["ledger_sha256"])
            self.assertEqual(pl.sha256_json([[e["parent_born"], e["move_kind"], e["intervention"], e["fitness"]] for e in o["ledger"]]), o["moves_sha256"])
            self.assertEqual(o["ledger"][-1]["map_version_after"], o["map_version_final"])
            self.assertEqual(o["ledger"][-1]["anomalies"], o["anomalies"])
        # the entries survive the JSON round trip byte for byte
        rt = json.loads(json.dumps(self.pred, sort_keys=True))
        self.assertEqual(pl.prediction_findings(self.pred, rt), [])

    def test_the_entry_level_comparison_names_a_tamper(self):
        """§8 (a): plan_findings / the adjudicator compare entry by entry — a tamper in one field of
        one entry is named by its path; a dropped entry is named; identical documents give nothing."""
        self.assertEqual(pl.prediction_findings(self.pred, copy.deepcopy(self.pred)), [])
        t = copy.deepcopy(self.pred)
        t["pairs"][1]["runs"]["O"]["ledger"][5]["fitness"] += 1
        f = pl.prediction_findings(self.pred, t)
        self.assertEqual(len(f), 1)
        self.assertTrue(f[0].startswith("pairs[1].runs.O.ledger[5].fitness: "), f[0])
        t = copy.deepcopy(self.pred)
        t["pairs"][0]["runs"]["O"]["ledger"][3]["decoded"] = list(t["pairs"][0]["runs"]["O"]["ledger"][3]["decoded"]) + [[999, 0, 0]]
        f = pl.prediction_findings(self.pred, t)
        self.assertTrue(any(x.startswith("pairs[0].runs.O.ledger[3].decoded") for x in f), f)
        t = copy.deepcopy(self.pred)
        del t["pairs"][0]["runs"]["O"]["ledger"][7]
        f = pl.prediction_findings(self.pred, t)
        self.assertIn("pairs[0].runs.O.ledger: 11 entries, expected 12", f)
        t = copy.deepcopy(self.pred)
        del t["pairs"][1]["runs"]["O"]["ledger"]
        self.assertIn("pairs[1].runs.O.ledger: absent", pl.prediction_findings(self.pred, t))
        # the same digest with a swapped pair of entries is caught by the entries, not by the digest
        t = copy.deepcopy(self.pred)
        L = t["pairs"][0]["runs"]["O"]["ledger"]
        L[2]["confidence"], L[4]["confidence"] = L[4]["confidence"], L[2]["confidence"]
        f = pl.prediction_findings(self.pred, t)
        self.assertTrue(f == [] or all(x.startswith("pairs[0].runs.O.ledger[") for x in f), f)
        t = copy.deepcopy(self.pred)
        t["extra"] = 1
        self.assertEqual(pl.prediction_findings(self.pred, t), ["extra: unexpected"])
        # a tuple and a list are the same entry (JSON-normalised)
        t = copy.deepcopy(self.pred)
        t["deltas1"] = tuple(t["deltas1"])
        self.assertEqual(pl.prediction_findings(self.pred, t), [])

    def test_one_primary_and_a_secondary_outcome_no_second_primary(self):
        """§10 (iv): predicted_primary (delta1, alpha, verdict); secondary_outcome (delta2: pos / neg /
        ties, exact p, mean, median, Cohen's d, no threshold, no verdict); nothing named primary_2 or
        both_required anywhere."""
        a = self.pred
        self.assertIn("predicted_primary", a)
        self.assertIn("secondary_outcome", a)
        for key in ("predicted_primary_1", "predicted_primary_2", "both_required", "primary_2"):
            self.assertNotIn(key, json.dumps(a))
        prim = a["predicted_primary"]
        self.assertEqual(set(prim), {"positives", "negatives", "ties", "sign_test_p", "alpha", "verdict"})
        self.assertEqual(prim["alpha"], 0.05)
        sec = a["secondary_outcome"]
        for key in ("positives", "negatives", "ties", "sign_test_p", "mean", "median", "cohen_d"):
            self.assertIn(key, sec)
        self.assertIsNone(sec["threshold"])
        self.assertNotIn("verdict", sec)
        self.assertNotIn("alpha", sec)
        import b2_gate as bg
        self.assertEqual(sec["sign_test_p"], bg.sign_test_p(a["deltas2"])[0])
        self.assertEqual(sec["cohen_d"], bg.cohen_d(a["deltas2"]))
        self.assertEqual(prim["sign_test_p"], bg.sign_test_p(a["deltas1"])[0])

    def test_the_stop_rule_is_on_the_primary_alone(self):
        pred = {"predicted_primary": {"sign_test_p": 0.36, "alpha": 0.05, "positives": 5, "negatives": 3, "ties": 1},
                "secondary_outcome": {"sign_test_p": 0.002, "positives": 9, "negatives": 0, "ties": 0}}
        f = pl.stop_rule_findings(pred)
        self.assertEqual(len(f), 1)
        self.assertTrue(f[0].startswith("predicted_primary: p = 0.36 > alpha 0.05 (5/3/1)"), f[0])
        pred["predicted_primary"]["sign_test_p"] = 0.01
        self.assertEqual(pl.stop_rule_findings(pred), [])
        # the pilot's numbers under the v0.3 rule: primary 1/512 passes, delta2 at 93/256 stops nothing
        pred = {"predicted_primary": {"sign_test_p": 1 / 512, "alpha": 0.05, "positives": 9, "negatives": 0, "ties": 0},
                "secondary_outcome": {"sign_test_p": 93 / 256, "positives": 5, "negatives": 3, "ties": 1}}
        self.assertEqual(pl.stop_rule_findings(pred), [])
        # and a document still carrying two primaries is not read by the v0.3 rule
        with self.assertRaises(KeyError):
            pl.stop_rule_findings({"predicted_primary_1": {"sign_test_p": 0.001, "alpha": 0.05}, "predicted_primary_2": {"sign_test_p": 0.5, "alpha": 0.05}})


class PlanDocument(unittest.TestCase):
    def test_the_plan_names_one_primary_and_the_secondary_no_claim_condition(self):
        plan = pl.build_plan(None, GATE)
        self.assertEqual((plan["schema_version"], plan["lifecycle"], plan["pairs"], plan["budget_per_arm"]), (pl.SCHEMA_VERSION, 2, 9, 1000))
        self.assertEqual(plan["seed_derivation"]["label"], "b3-session-2")
        text = json.dumps(plan)
        for key in ("primary_1", "primary_2", "both_required", "H9_claim_condition", "either primary"):
            self.assertNotIn(key, text)
        self.assertIn("stop_rule", plan["primary"])
        self.assertIn("before any canonical write", plan["primary"]["stop_rule"])
        self.assertEqual(plan["primary"]["alpha"], 0.05)
        self.assertIsNone(plan["secondary_outcome"]["threshold"])
        self.assertIn("diagnostic", plan["gate"]["H9"])
        self.assertTrue(plan["session_split"]["status"].startswith("UNDETERMINED"))
        self.assertTrue(any("lifecycle 1 gate run 1" in k for k in plan["seed_derivation"]["excluded_sources"]))


class StopBeforeCanonicalWrite(unittest.TestCase):
    """§8 (b): on a stop nothing is written to the canonical path and the CLI exits 3 naming the
    primary; an explicit non-canonical --out may hold the trial; a passing prediction is written to
    the canonical path. The prediction is mocked (the full one costs minutes); the canonical directory
    is redirected into a temp tree so the real evidence/b3 is never touched."""
    def setUp(self):
        self.d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.d, True)
        self.canon = self.d / "evidence/b3"
        _m, self.seeds, _s, _e = pl.session_seeds(9, GATE)

    def run_cli(self, stopping: bool, out: str) -> tuple[int, dict]:
        p = 0.36 if stopping else 0.002
        pred = {"schema": "b3_prediction", "schema_version": pl.SCHEMA_VERSION, "lifecycle": 2, "fitness": "F1", "budget_per_arm": 1000,
                "pairs": [], "deltas1": [1] * 9, "deltas2": [0] * 9,
                "predicted_primary": {"sign_test_p": p, "alpha": 0.05, "positives": 5 if stopping else 9, "negatives": 3 if stopping else 0, "ties": 1 if stopping else 0,
                                      "verdict": "NOT SUPPORTED" if stopping else "online > random-safe SUPPORTED"},
                "secondary_outcome": pl.secondary_report([0] * 9), "fitness_sequence_length": 0}
        import io, contextlib
        buf = io.StringIO()
        with mock.patch.object(pl, "PLAN_DIR", self.canon), mock.patch.object(pl, "REPO_ROOT", self.d), \
             mock.patch.object(pl, "build_prediction", return_value=pred), \
             mock.patch.object(pl, "build_plan", return_value={"schema": "b3_plan", "fitness": "F1", "budget_per_arm": 1000, "pairs": 9,
                                                                "seed_derivation": {"master_seed": 1}, "session_split": {"status": "UNDETERMINED"}}), \
             contextlib.redirect_stdout(buf):
            rc = pl.main(["--out", out, "--gate-report", str(GATE)])
        return rc, json.loads(buf.getvalue())

    def test_a_stop_writes_nothing_canonical_and_exits_3_naming_the_primary(self):
        rc, out = self.run_cli(True, "evidence/b3")
        self.assertEqual(rc, 3)
        self.assertFalse(self.canon.exists(), list(self.d.rglob("*")))
        self.assertIsNone(out["plan"]); self.assertIsNone(out["prediction"])
        self.assertEqual(len(out["stop_rule_findings"]), 1)
        self.assertTrue(out["stop_rule_findings"][0].startswith("predicted_primary: p = 0.36"))
        self.assertIn("nothing", out["written"])
        # the canonical path spelled differently is still canonical
        rc, out = self.run_cli(True, "evidence/b3/../b3")
        self.assertEqual(rc, 3); self.assertFalse(self.canon.exists()); self.assertIsNone(out["plan"])

    def test_a_trial_may_write_only_to_an_explicit_non_canonical_out(self):
        rc, out = self.run_cli(True, "evidence/b3/plan_trial_test")
        self.assertEqual(rc, 3)
        self.assertFalse((self.canon / "plan.json").exists()); self.assertFalse((self.canon / "prediction.json").exists())
        trial = self.d / "evidence/b3/plan_trial_test"
        self.assertTrue((trial / "plan.json").exists() and (trial / "prediction.json").exists())
        self.assertEqual(out["written"], "non-canonical (a trial)")
        self.assertEqual(json.loads((trial / "prediction.json").read_text())["predicted_primary"]["verdict"], "NOT SUPPORTED")

    def test_a_passing_prediction_is_written_canonically_with_exit_0(self):
        rc, out = self.run_cli(False, "evidence/b3")
        self.assertEqual(rc, 0)
        self.assertTrue((self.canon / "plan.json").exists() and (self.canon / "prediction.json").exists())
        self.assertEqual(out["stop_rule_findings"], [])
        self.assertEqual(out["written"], "canonical")
        plan = json.loads((self.canon / "plan.json").read_text())
        self.assertEqual(plan["prediction_sha256"], pl.sha256_file(self.canon / "prediction.json"))


class Qualification(unittest.TestCase):
    def test_b3q_numbers_and_label(self):
        _m, seeds, _s, _e = pl.session_seeds(9, GATE)
        q = pl.build_qualification_plan("F1", bmaps.sha256_of(bmaps.load_self_map()), seeds, GATE)
        self.assertEqual(q["budget_per_arm"], 40)
        self.assertEqual(q["records"], {"per_pair": 123, "search": 120, "holdout": 3, "ledger_entries": 40, "baselines": 2, "total": 125})
        self.assertEqual(q["session"], "B3Q")
        self.assertEqual(q["seed_derivation"]["label"], "b3-qualification-2")
        self.assertEqual(q["seed_derivation"]["master_seed"], bs.master_seed("b3-qualification-2", pl.INSTRUMENT_COMMIT))
        self.assertAlmostEqual(q["planning_bound"]["session_timeout_s"], 1.25 * 125 * 3600 / pl.QUAL_PLANNING_RATE_PER_HOUR + 600)


if __name__ == "__main__":
    unittest.main()

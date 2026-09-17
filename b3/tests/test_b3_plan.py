"""b3/host/b3_plan.py (lifecycle 2) — the gate's numbers read only through the production validator (a
lifecycle-2 fixture accepted; lifecycle 1's report and every tamper refused by name), the seed exclusion
(every archived set, lifecycle 1's two sets, plus the gate's own pairs), the labels, the split rule with
the 0.85 margin, the arm order, the record arithmetic, the prediction's determinism and structure with
EVERY ledger entry embedded, the entry-level comparison naming a tamper, one primary plus the secondary
outcome, the stop rule on the primary alone, the CLI's stop before any canonical write, the CLI's named
refusals (REFUSED:, exit 2, nothing written) and lifecycle 1's directories refused as outputs, and B3Q's
frozen experiment.

The gate fixture (b3_test_fixtures.write_gate_fixture): a report of the lifecycle-2 shape built by the
tool's own builder into a temp directory, its seeds drawn under `b3-gate-2` with the real exclusion, its
raw file digested, its results evaluate() on synthetic rows — accepted by b3_gate.validate_report under
this module's thresholds (bootstrap experiments 100, restored afterwards). Its B* / N are a fixture's,
never a gate result."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host", R / "b3/tests"):
    sys.path.insert(0, str(p))
import b2_maps as bmaps  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_gate as b3g  # noqa: E402
import b3_online_arm as oa  # noqa: E402
import b3_plan as pl  # noqa: E402
from b3_test_fixtures import FIXTURE_HEAD, NOT_A_COMMIT, rewrite_report, write_gate_fixture  # noqa: E402

LIFECYCLE1_GATE = R / "evidence/b3/gate/gate_report.json"
_TMP: Path | None = None
_SAVED: int | None = None
GATE: Path | None = None
FIX: dict = {}      # the fixture's own numbers (B*, N), read from its validated report


def setUpModule():
    global _TMP, _SAVED, GATE
    _SAVED = b3g.THRESHOLDS["H2_bootstrap_experiments"]
    b3g.THRESHOLDS["H2_bootstrap_experiments"] = 100
    _TMP = Path(tempfile.mkdtemp())
    GATE = write_gate_fixture(_TMP / "gate_2")
    rep = b3g.validate_report(GATE)
    FIX.update(b_star=rep["results"]["F1"]["b_star"], n=rep["results"]["F1"]["criteria"]["H5"]["required_pairs_N"])


def tearDownModule():
    b3g.THRESHOLDS["H2_bootstrap_experiments"] = _SAVED
    shutil.rmtree(_TMP, True)


def copy_fixture(case) -> Path:
    d = Path(tempfile.mkdtemp()); case.addCleanup(shutil.rmtree, d, True)
    shutil.copy(GATE, d / "gate_report.json"); shutil.copy(GATE.parent / "raw_F1.json", d / "raw_F1.json")
    return d / "gate_report.json"


class GateAndSeeds(unittest.TestCase):
    def test_lifecycle_2_labels(self):
        self.assertEqual(pl.SESSION_LABEL, "b3-session-2")
        self.assertEqual(pl.QUAL_LABEL, "b3-qualification-2")
        self.assertEqual(pl.GATE_REPORT, R / "evidence/b3/gate_2/gate_report.json")
        self.assertEqual(pl.PLAN_DIR, R / "evidence/b3")
        self.assertEqual(pl.qualification_master(), bs.master_seed("b3-qualification-2", pl.INSTRUMENT_COMMIT))

    def test_gate_inputs_come_from_the_validated_report_and_carry_no_claim_condition(self):
        g = pl.gate_inputs(GATE)
        self.assertEqual((g["fitness"], g["budget_per_arm"], g["pairs"]), ("F1", FIX["b_star"], FIX["n"]))
        self.assertEqual(g["seeds"]["label"], "b3-gate-2")
        self.assertEqual(g["rules_version"], "architecture v0.3 §9")
        self.assertEqual(g["head_at_run"], FIXTURE_HEAD)
        self.assertNotIn("H9_claim_condition", g)
        self.assertNotIn("H9", json.dumps(g))

    def test_gate_inputs_refuse_lifecycle_1s_report_and_every_tamper_by_name(self):
        """The owner's P2: B* and N are trusted only after b3_gate.validate_report — schema 2.0.0, a clean
        committed tree, the architecture bytes, the raw digest, evaluate() re-run from the raw rows."""
        with self.assertRaises(b3g.Refusal) as cm:
            pl.gate_inputs(LIFECYCLE1_GATE)
        self.assertIn("not the lifecycle-2 shape", str(cm.exception))
        for what, mutate, needle in (
                ("dirty", lambda r: r.__setitem__("worktree_dirty_at_start", True), "worktree_dirty_at_start True"),
                ("head null", lambda r: r.__setitem__("head_at_run", None), "head_at_run None is not a commit"),
                ("head not a commit", lambda r: r.__setitem__("head_at_run", NOT_A_COMMIT), "is not a commit"),
                ("map digest", lambda r: r["map"].__setitem__("sha256", "0" * 64), "map.sha256"),
                ("excluded sources", lambda r: r["seeds"]["excluded_sources"].popitem(), "seeds.excluded_sources"),
                ("results a list", lambda r: r.__setitem__("results", []), "results: list, not an object"),
                ("architecture", lambda r: r["architecture"].__setitem__("sha256", "0" * 64), "architecture.sha256"),
                ("label", lambda r: r["seeds"].__setitem__("label", "b3-gate"), "seeds.label"),
                ("rules", lambda r: r["thresholds"].__setitem__("rules_version", "architecture v0.2.3 §9"), "thresholds.rules_version"),
                ("N", lambda r: r["results"]["F1"]["criteria"]["H5"].__setitem__("required_pairs_N", FIX["n"] + 1), "results.F1.criteria.H5.required_pairs_N"),
                ("B*", lambda r: r["results"]["F1"].__setitem__("b_star", 3000), "results.F1.b_star"),
                ("H9 back as a criterion", lambda r: r["results"]["F1"]["criteria"].__setitem__("H9", {"pass": True}), "results.F1.criteria.H9"),
                ("raw digest", lambda r: r["raw_files"]["F1"].__setitem__("sha256", "0" * 64), "raw_files.F1.sha256")):
            p = copy_fixture(self)
            rewrite_report(p, mutate)
            with self.assertRaises(b3g.Refusal, msg=what) as cm:
                pl.gate_inputs(p)
            self.assertIn(needle, str(cm.exception), what)
        # a report that validates but did not pass: no plan
        p = copy_fixture(self)
        raw = json.loads((p.parent / "raw_F1.json").read_text())
        for row in raw["rows"]:
            row["arms"]["O"]["at_grid"] = [40] * len(b3g.GRID)           # H1 fails everywhere: no B*
        b = json.dumps(raw, separators=(",", ":")).encode(); (p.parent / "raw_F1.json").write_bytes(b)
        res = b3g.evaluate("F1", raw["rows"]); res["wall_s"] = 0.0
        rewrite_report(p, lambda r: (r["raw_files"]["F1"].__setitem__("sha256", b3g.sha256_bytes(b)), r["results"].__setitem__("F1", res)))
        self.assertFalse(b3g.validate_report(p)["results"]["F1"]["pass"])
        with self.assertRaises(b3g.Refusal) as cm:
            pl.gate_inputs(p)
        self.assertIn("did not pass", str(cm.exception))

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
        p = copy_fixture(self)
        raw = json.loads((p.parent / "raw_F1.json").read_text())
        raw["rows"][1]["operator_seed"] += 1
        b = json.dumps(raw, separators=(",", ":")).encode(); (p.parent / "raw_F1.json").write_bytes(b)
        rewrite_report(p, lambda r: r["raw_files"]["F1"].__setitem__("sha256", b3g.sha256_bytes(b)))
        with self.assertRaises(b3g.Refusal) as cm:
            pl.session_seeds(9, p)
        self.assertIn("do not carry the seeds", str(cm.exception))


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
        self.assertEqual((plan["schema_version"], plan["lifecycle"], plan["pairs"], plan["budget_per_arm"]), (pl.SCHEMA_VERSION, 2, FIX["n"], FIX["b_star"]))
        self.assertEqual(plan["gate"]["head_at_run"], FIXTURE_HEAD)
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
        pred = {"schema": "b3_prediction", "schema_version": pl.SCHEMA_VERSION, "lifecycle": 2, "fitness": "F1", "budget_per_arm": FIX["b_star"],
                "pairs": [], "deltas1": [1] * 9, "deltas2": [0] * 9,
                "predicted_primary": {"sign_test_p": p, "alpha": 0.05, "positives": 5 if stopping else 9, "negatives": 3 if stopping else 0, "ties": 1 if stopping else 0,
                                      "verdict": "NOT SUPPORTED" if stopping else "online > random-safe SUPPORTED"},
                "secondary_outcome": pl.secondary_report([0] * 9), "fitness_sequence_length": 0}
        import io, contextlib
        buf = io.StringIO()
        with mock.patch.object(pl, "PLAN_DIR", self.canon), mock.patch.object(pl, "REPO_ROOT", self.d), \
             mock.patch.object(pl, "build_prediction", return_value=pred), \
             mock.patch.object(pl, "build_plan", return_value={"schema": "b3_plan", "fitness": "F1", "budget_per_arm": FIX["b_star"], "pairs": FIX["n"],
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


class Refusals(unittest.TestCase):
    """The owner's P3: an input / shape / I/O refusal is `REFUSED: ...` on stderr, exit 2, nothing written —
    never a traceback; and the owner's P2: lifecycle 1's directories and everything under them are
    refused as --out (hermetic: the constants patched to temp copies)."""
    def cli(self, argv) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = pl.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_a_lifecycle_1_report_missing_or_malformed_input_is_refused_by_name(self):
        t = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, t, True)
        (t / "bad.json").write_text("{")
        tampered = copy_fixture(self); rewrite_report(tampered, lambda r: r.__setitem__("worktree_dirty_at_start", True))
        for what, rep, needle in (("lifecycle 1", LIFECYCLE1_GATE, "not the lifecycle-2 shape"), ("missing", t / "none.json", "cannot be read"),
                                  ("malformed", t / "bad.json", "not JSON"), ("dirty", tampered, "worktree_dirty_at_start True")):
            for extra in ((), ("--qualification",)):
                rc, out, err = self.cli(["--out", str(t / "out"), "--gate-report", str(rep), *extra])
                self.assertEqual(rc, 2, (what, extra))
                self.assertTrue(err.startswith("REFUSED: "), (what, err))
                self.assertIn(needle, err, what)
                self.assertNotIn("Traceback", err)
                self.assertEqual(out, "")
                self.assertFalse((t / "out").exists(), what)
        # --out under a regular file, or an existing file: refused by name before the gate is even read
        (t / "afile").write_text("x")
        for out_path, needle in ((t / "afile/plan", "not a directory"), (t / "afile", "not a directory")):
            for extra in ((), ("--qualification",)):
                rc, out, err = self.cli(["--out", str(out_path), "--gate-report", str(t / "none.json"), *extra])
                self.assertEqual(rc, 2); self.assertTrue(err.startswith("REFUSED: ")); self.assertIn(needle, err); self.assertNotIn("none.json", err)
        self.assertEqual((t / "afile").read_text(), "x")

    def test_lifecycle_1s_directories_are_refused_as_out_before_anything_is_read(self):
        t = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, t, True)
        d = t / "evidence/b3/gate"; shutil.copytree(b3g.LIFECYCLE1_GATE_DIR, d)
        tr = t / "evidence/b3/plan_trial_2026_09_17"; shutil.copytree(b3g.LIFECYCLE1_TRIAL_DIR, tr)
        snap = lambda p: sorted((x.name, x.stat().st_size, x.stat().st_mtime_ns) for x in p.iterdir())  # noqa: E731
        before = snap(d) + snap(tr)
        with mock.patch.object(b3g, "LIFECYCLE1_GATE_DIR", d), mock.patch.object(b3g, "LIFECYCLE1_TRIAL_DIR", tr):
            for out in (str(d), str(d / "plan"), str(tr), str(tr / "x"), str(t / "evidence/b3/gate/../plan_trial_2026_09_17/y")):
                for extra in ((), ("--qualification",)):
                    rc, so, err = self.cli(["--out", out, "--gate-report", str(GATE), *extra])
                    self.assertEqual(rc, 2, out)
                    self.assertTrue(err.startswith("REFUSED: "), err); self.assertIn("never overwritten", err)
        self.assertEqual(snap(d) + snap(tr), before)
        self.assertFalse((d / "plan").exists()); self.assertFalse((tr / "x").exists())


class Qualification(unittest.TestCase):
    def test_b3q_numbers_and_label(self):
        _m, seeds, _s, _e = pl.session_seeds(FIX["n"], GATE)
        q = pl.build_qualification_plan("F1", bmaps.sha256_of(bmaps.load_self_map()), seeds, GATE)
        self.assertEqual(q["budget_per_arm"], 40)
        self.assertEqual(q["records"], {"per_pair": 123, "search": 120, "holdout": 3, "ledger_entries": 40, "baselines": 2, "total": 125})
        self.assertEqual(q["session"], "B3Q")
        self.assertEqual(q["seed_derivation"]["label"], "b3-qualification-2")
        self.assertEqual(q["seed_derivation"]["master_seed"], bs.master_seed("b3-qualification-2", pl.INSTRUMENT_COMMIT))
        self.assertAlmostEqual(q["planning_bound"]["session_timeout_s"], 1.25 * 125 * 3600 / pl.QUAL_PLANNING_RATE_PER_HOUR + 600)


if __name__ == "__main__":
    unittest.main()

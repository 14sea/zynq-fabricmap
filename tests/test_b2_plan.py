"""B2 plan / prediction: reproducible from the rule, disjoint from the gate's seeds, and
the prediction equals a fresh run of the reference (docs/b2_preregistration.md §2–§3)."""
from __future__ import annotations

import hashlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
sys.path.insert(0, str(R / "tests"))
import b1_model as bm  # noqa: E402
import b2_gate as bg  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_search as bs  # noqa: E402

PLAN = R / "evidence/b2/plan.json"
PRED = R / "evidence/b2/prediction.json"
MANIFEST = R / "manifests/b2_manifest.json"


def split_findings(plan: dict, plan_bytes: bytes, manifest: dict | None) -> list[str]:
    """The committed plan's split, held to the stage the manifest is at — never to a constant.

    Before S3 (no manifest, or a manifest with no plan pinned) the committed plan is the
    preregistered document with the split UNDETERMINED (docs/b2_preregistration.md §2: "split
    UNDETERMINED until S2; the S3 plan is regenerated with --rate-per-hour ... and pinned"). From
    S3 on, the committed plan IS the pinned one: DETERMINED, its bytes hashing to the manifest's
    pin, its session count and record total equal to what the pin records. One rule for the
    committed tree and for the stage guard below; the hard-coded UNDETERMINED this replaces was
    frozen at S1 and could not survive the S3 transition (docs/b2_s3_frozen_test_decision_2026_09_16.md)."""
    f: list[str] = []
    split = plan.get("session_split") or {}
    status = split.get("status")
    pinned = (manifest or {}).get("plan")
    if pinned is None:
        if not isinstance(status, str) or not status.startswith("UNDETERMINED"):
            f.append(f"no plan is pinned, so the committed split must be UNDETERMINED, not {status!r}")
        return f
    if status != "DETERMINED":
        f.append(f"a plan is pinned, so the committed split must be DETERMINED, not {status!r}")
    digest = hashlib.sha256(plan_bytes).hexdigest()
    if digest != pinned.get("sha256"):
        f.append(f"the committed plan hashes to {digest[:12]}…, the manifest pins {str(pinned.get('sha256'))[:12]}…")
    if len(split.get("sessions") or []) != pinned.get("sessions"):
        f.append(f"the committed split has {len(split.get('sessions') or [])} sessions, the pin records {pinned.get('sessions')}")
    if split.get("total_records") != pinned.get("total_records"):
        f.append(f"the committed split totals {split.get('total_records')} records, the pin records {pinned.get('total_records')}")
    return f


@unittest.skipUnless(PLAN.exists() and PRED.exists(), "no committed B2 plan / prediction")
class Committed(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(PLAN.read_text())
        self.pred = json.loads(PRED.read_text())

    def test_seeds_follow_the_rule_and_avoid_the_gate(self):
        master = bs.master_seed(bp.SESSION_LABEL, bp.INSTRUMENT_COMMIT)
        self.assertEqual(self.plan["seed_derivation"]["master_seed"], master)
        pairs = bs.pair_seeds(master, self.plan["pairs"])
        self.assertEqual([(p["landscape_seed"], p["operator_seed"]) for p in self.pred["pairs"]], pairs)
        gate = json.loads((R / "evidence/b2/gate/gate_report.json").read_text())
        gate_seeds = {x for p in bs.pair_seeds(gate["seeds"]["master_seed"], gate["seeds"]["count"]) for x in p}
        self.assertFalse(gate_seeds & {x for p in pairs for x in p})
        self.assertNotIn(master, bs.EXCLUDED_SEEDS)

    def test_fitness_budget_pairs_are_the_gates(self):
        gate = json.loads((R / self.plan["gate"]["path"]).read_text())
        fid = gate["selected_fitness"]
        self.assertEqual(self.plan["fitness"], fid)
        self.assertEqual(self.plan["budget_per_arm"], gate["results"][fid]["b_star"])
        self.assertEqual(self.plan["pairs"], gate["results"][fid]["criteria"]["G5"]["required_pairs_N"])
        self.assertEqual(self.plan["gate"]["sha256"], hashlib.sha256((R / self.plan["gate"]["path"]).read_bytes()).hexdigest())
        self.assertEqual(self.plan["gate"]["rules_version"], bg.THRESHOLDS["rules_version"])

    def test_record_count_and_split_arithmetic(self):
        n, b = self.plan["pairs"], self.plan["budget_per_arm"]
        self.assertEqual(self.plan["records"]["single_session_total"], 1 + n * 2 * b + n * 2 + 1)
        self.assertEqual(self.plan["records"]["per_pair"], 2 * b + 2)
        self.assertEqual(self.pred["fitness_sequence_length"], n * 2 * b + n * 2)
        self.assertEqual(self.plan["audit_policy"], "all-self-reporting")
        manifest = json.loads(MANIFEST.read_text()) if MANIFEST.is_file() else None
        self.assertEqual(split_findings(self.plan, PLAN.read_bytes(), manifest), [])
        # the split rule: with a measured rate, whole pairs per session within the two-hour expected span
        s = bp.session_split(9, 600, 2500.0)
        self.assertEqual(s["pairs_per_session_max"], 4)
        self.assertEqual([len(x["pairs"]) for x in s["sessions"]], [4, 4, 1])
        self.assertEqual(s["total_records"], 3 * 2 + 9 * 1202)
        self.assertTrue(all(x["expected_span_s"] <= bp.SESSION_SPAN_MAX_S for x in s["sessions"]))
        s2 = bp.session_split(9, 600, 2807.0)     # the last B1 mapping's observed rate: still 4 per session
        self.assertEqual(s2["pairs_per_session_max"], 4)
        # the one-pair boundary: 1 204 records in 7 200 s needs 602 / h
        self.assertEqual(bp.session_split(9, 600, 602.0)["pairs_per_session_max"], 1)
        self.assertEqual(len(bp.session_split(9, 600, 602.0)["sessions"]), 9)
        inf = bp.session_split(9, 600, 601.0)
        self.assertEqual(inf["status"], "INFEASIBLE")
        self.assertNotIn("sessions", inf)
        self.assertAlmostEqual(inf["min_feasible_rate_per_hour"], 1204 * 3600 / 7200)
        self.assertEqual(bp.session_split(9, 600, 100.0)["status"], "INFEASIBLE")      # the review's 12-hour case
        for bad in (0, -1, float("inf"), float("nan"), True, "2500"):
            with self.assertRaises((bp.RateInvalid, TypeError)):
                bp.session_split(9, 600, bad)

    def test_seed_exclusion_is_explicit_and_covers_every_archived_set(self):
        excl, sources = bp.frozen_seed_exclusion()
        self.assertEqual(set(sources), set(bp.FROZEN_SEED_SETS))
        self.assertEqual(self.plan["seed_derivation"]["excluded_values_total"], len(excl | set(bs.EXCLUDED_SEEDS)))
        mine = {x for p in self.pred["pairs"] for x in (p["landscape_seed"], p["operator_seed"])}
        self.assertFalse(mine & excl)

    def test_prediction_pinned_in_plan(self):
        self.assertEqual(self.plan["prediction_sha256"], hashlib.sha256(PRED.read_bytes()).hexdigest())

    def test_prediction_equals_a_fresh_reference_run(self):
        truth = bm.truth_mapping()
        masks = bl.universe_mask(truth)
        fabric = bs.ModelFabric(truth)
        view = bmaps.MapView(bmaps.load_self_map(), bl.train_vectors())
        self.assertEqual(self.plan["map"]["sha256"], view.sha256)
        for p in self.pred["pairs"][:3]:          # three pairs: the full set is the plan tool's job
            land = bl.Landscape(self.plan["fitness"], p["landscape_seed"], masks=masks, truth=truth)
            a = bs.run(bs.ARM_RANDOM_SAFE, land, None, p["operator_seed"], self.plan["budget_per_arm"], fabric)
            b = bs.run(bs.ARM_MAP_GUIDED, land, view, p["operator_seed"], self.plan["budget_per_arm"], fabric)
            self.assertEqual(p["runs"]["A"]["best_train"], a.best_trace[-1])
            self.assertEqual(p["runs"]["B"]["best_train"], b.best_trace[-1])
            self.assertEqual(p["runs"]["A"]["champion_holdout"], a.champion_holdout)
            self.assertEqual(p["runs"]["B"]["champion_holdout"], b.champion_holdout)
            self.assertEqual(p["delta_B_minus_A"], b.best_trace[-1] - a.best_trace[-1])

    def test_primary_is_the_sign_test_over_the_deltas(self):
        d = bp.decision(self.pred["deltas"])
        self.assertEqual(d, self.pred["predicted_primary"])
        p, pos, neg, ties = bg.sign_test_p(self.pred["deltas"])
        self.assertEqual((pos, neg, ties), (d["positives"], d["negatives"], d["ties"]))

    def test_arm_order_alternates(self):
        for p in self.pred["pairs"]:
            self.assertEqual(p["arm_order"], ["A", "B"] if p["pair"] % 2 == 0 else ["B", "A"])


try:
    from test_b2_runner import HAVE as _HAVE_RUNNER_FIXTURE, STUB_RATE, Fixture
except ImportError:                      # the runner's suite is absent: the guard below has nothing to build with
    _HAVE_RUNNER_FIXTURE, STUB_RATE, Fixture = False, None, None


@unittest.skipUnless(_HAVE_RUNNER_FIXTURE, "the built B2 image, its build evidence or the gate report is absent")
class StageCoverage(unittest.TestCase):
    """The S3 frozen-test contradiction of 2026-09-16, inverted into a permanent guard.

    `Committed.test_record_count_and_split_arithmetic` used to assert that the committed plan is
    UNDETERMINED. That was true at S0, S1 and S2 and false at S3 by construction (the S3 plan is
    regenerated from the calibration and pinned), and the file was frozen in the pin table at S1 —
    so the first legal S3 transition produced a suite that could not be green. This drives the
    real test function, unchanged, against a real manifest file and a real plan file at every
    stage the lifecycle has, and requires it to PASS at each; then, so that passing means
    something, against three illegal pairings, requiring it to fail for each one's own reason.

    The fixtures are the runner suite's (`test_b2_runner.Fixture`): a manifest carried S0 → S3
    in a temp directory with the B2Q evidence and re-adjudicator stubbed — test readiness, never
    a qualification. Before S3 the plan file is the tool's own UNDETERMINED document
    (`bp.build_plan(None)`), exactly what `b2_plan.py` writes without `--rate-per-hour`.
    """

    TEST = "test_record_count_and_split_arithmetic"

    def drive(self, manifest_path: Path | None, plan_path: Path, pred_path: Path) -> unittest.TestResult:
        """Run the committed test against these three files; the seams are the module constants
        the test reads, patched by name."""
        with mock.patch.object(sys.modules[__name__], "PLAN", plan_path), \
                mock.patch.object(sys.modules[__name__], "PRED", pred_path), \
                mock.patch.object(sys.modules[__name__], "MANIFEST",
                                  manifest_path if manifest_path is not None else Path("/nonexistent/b2_manifest.json")):
            suite = unittest.TestSuite([Committed(self.TEST)])
            return unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)

    @staticmethod
    def undetermined_documents(f) -> tuple[Path, Path]:
        """The pre-S3 committed documents for a fixture: the plan without a rate, the prediction
        for the fixture's own seeds (what the committed prediction.json is before and after S3)."""
        plan = bp.build_plan(None)
        prediction = bp.build_prediction(plan["fitness"], plan["budget_per_arm"],
                                         [tuple(p) for p in f.manifest["seeds"]["pairs"]],
                                         f.manifest["map"]["canonical_json_sha256"])
        return bp.write(f.d / "pre_s3", plan, prediction)

    def accepts(self, stage: str) -> dict:
        f = Fixture(stage)
        try:
            if stage == "S3":
                plan_path, pred_path = f.plan_path, f.plan_path.parent / "prediction.json"
            else:
                plan_path, pred_path = self.undetermined_documents(f)
            result = self.drive(f.path(), plan_path, pred_path)
            self.assertEqual((len(result.failures), len(result.errors), len(result.skipped)), (0, 0, 0),
                             f"{stage}: " + "".join(t for _, t in result.failures + result.errors)[:2000])
            self.assertEqual(result.testsRun, 1)
            return json.loads(plan_path.read_text())["session_split"]
        finally:
            f.close()

    def rejects(self, stage: str, choose, *words: str) -> None:
        """`choose(f) -> (manifest_path | None, plan_path, pred_path)` builds the illegal pairing."""
        f = Fixture(stage)
        try:
            result = self.drive(*choose(f))
            self.assertEqual(len(result.failures) + len(result.errors), 1,
                             f"{stage}: an illegal plan/manifest pairing was accepted")
            text = "".join(t for _, t in result.failures + result.errors)
            for w in words:
                self.assertIn(w, text)
        finally:
            f.close()

    # ------------------------------------------------------------------ it survives every stage
    def test_it_passes_at_s0_s1_and_s2_with_the_undetermined_plan(self):
        for stage in ("S0", "S1", "S2"):
            with self.subTest(stage=stage):
                split = self.accepts(stage)
                self.assertTrue(split["status"].startswith("UNDETERMINED"), split["status"])

    def test_it_passes_at_s3_with_the_pinned_plan(self):
        """The transition the frozen assertion could not survive."""
        split = self.accepts("S3")
        self.assertEqual(split["status"], "DETERMINED")

    def test_it_passes_at_s3_for_every_split_a_calibration_can_give(self):
        """Synthetic fixture rates, never a calibration: four legally different S3 splits, and the
        test holds each committed plan to its own pin rather than to any one shape."""
        seen = {}
        for rate in (2807.0, 602.0, 4490.86, 6000.0):
            with self.subTest(rate=rate), mock.patch.object(sys.modules["test_b2_runner"], "STUB_RATE", rate):
                seen[rate] = len(self.accepts("S3")["sessions"])
        self.assertEqual(len(set(seen.values())), 4, f"the rates did not give different splits: {seen}")

    def test_it_passes_with_no_manifest_at_all(self):
        """The pre-image tree (before S0 there is no manifest): the committed plan is UNDETERMINED."""
        f = Fixture("S0")
        try:
            plan_path, pred_path = self.undetermined_documents(f)
            result = self.drive(None, plan_path, pred_path)
            self.assertEqual((len(result.failures), len(result.errors), result.testsRun), (0, 0, 1),
                             "".join(t for _, t in result.failures + result.errors)[:2000])
        finally:
            f.close()

    # ------------------------------------------------------------------ and still discriminates
    def test_the_old_constant_is_exactly_what_fails_at_s3(self):
        """The control for the correction itself: an UNDETERMINED plan file against an S3 manifest —
        the pairing the frozen assertion demanded — is refused, naming the pin."""
        def choose(f):
            plan_path, pred_path = self.undetermined_documents(f)
            return f.path(), plan_path, pred_path
        self.rejects("S3", choose, "a plan is pinned, so the committed split must be DETERMINED")

    def test_a_determined_split_with_nothing_pinned_is_refused(self):
        """The inverse: a DETERMINED plan (any rate) in a tree whose manifest pins no plan."""
        def choose(f):
            plan = bp.build_plan(STUB_RATE)
            prediction = bp.build_prediction(plan["fitness"], plan["budget_per_arm"],
                                             [tuple(p) for p in f.manifest["seeds"]["pairs"]],
                                             f.manifest["map"]["canonical_json_sha256"])
            plan_path, pred_path = bp.write(f.d / "early", plan, prediction)
            return f.path(), plan_path, pred_path
        self.rejects("S2", choose, "no plan is pinned, so the committed split must be UNDETERMINED")

    def test_a_pinned_plan_whose_bytes_drifted_is_refused(self):
        """S3 with the committed plan edited after pinning: same shape, different bytes."""
        def choose(f):
            doc = json.loads(f.plan_path.read_text())
            doc["generated_utc"] = "1970-01-01T00:00:00Z"
            drifted = f.d / "drifted_plan.json"
            drifted.write_text(json.dumps(doc, indent=1, sort_keys=True))
            return f.path(), drifted, f.plan_path.parent / "prediction.json"
        self.rejects("S3", choose, "the committed plan hashes to")

    # ---------------------------------------------------- the pin's own summary, one field at a time
    # (the owner's review of 2026-09-16, P2: with both comparisons removed from split_findings the
    # seven cases above still passed — the two summary guards had no discriminating negative)

    @staticmethod
    def _pinned_summary_off_by_one(field: str):
        """A valid S3 fixture whose MANIFEST summary of the pin is wrong in exactly `field`; the
        committed plan bytes are the pinned ones, untouched, so the digest still agrees."""
        def choose(f):
            f.manifest["plan"][field] += 1
            return f.path(), f.plan_path, f.plan_path.parent / "prediction.json"
        return choose

    def test_a_pin_whose_session_count_disagrees_with_the_plan_is_refused(self):
        self.rejects("S3", self._pinned_summary_off_by_one("sessions"), "sessions, the pin records")

    def test_a_pin_whose_record_total_disagrees_with_the_plan_is_refused(self):
        self.rejects("S3", self._pinned_summary_off_by_one("total_records"), "records, the pin records")

    def test_each_summary_guard_is_load_bearing(self):
        """The control for the two cases above (the review's item 3): delete either comparison from
        `split_findings` and its negative case must FAIL — otherwise the case would pass for a
        reason other than the guard it claims to exercise."""
        original = split_findings
        for needle, case in (("sessions, the pin records", "test_a_pin_whose_session_count_disagrees_with_the_plan_is_refused"),
                             ("records, the pin records", "test_a_pin_whose_record_total_disagrees_with_the_plan_is_refused")):
            with self.subTest(guard=needle):
                def without(plan, plan_bytes, manifest, _needle=needle):
                    return [x for x in original(plan, plan_bytes, manifest) if _needle not in x]
                with mock.patch.object(sys.modules[__name__], "split_findings", without):
                    suite = unittest.TestSuite([StageCoverage(case)])
                    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
                self.assertEqual((result.testsRun, len(result.failures) + len(result.errors)), (1, 1),
                                 f"{case} still passes with its guard removed: the case is not load-bearing")


if __name__ == "__main__":
    unittest.main()

"""Consumer authority tests for the Claim B reachability report.

The literal fixtures are not emitted by producer code.  In particular the second LUT
rejects k=1 and accepts k=2, so a verifier must exercise draw advancement rather than
merely validate a final target's shape.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOST = REPO_ROOT / "host"
sys.path.insert(0, str(HOST))

import verify_reachability_report as vrr  # noqa: E402

FIXTURES = REPO_ROOT / "tests/fixtures"
SPEC_PATH = FIXTURES / "reachability_spec_conformance.json"
PRODUCTION_SPEC = REPO_ROOT / "specs/reachability_spec_v1.json"
GOOD_PATH = FIXTURES / "reachability_report_conformance.json"
BAD_TARGET = FIXTURES / "reachability_report_bad_wrong_target.json"
BAD_SKIP = FIXTURES / "reachability_report_bad_skipped_draw.json"
BAD_EARLY = FIXTURES / "reachability_report_bad_early_exhaustion.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def semantic_problems(report: dict, spec: dict | None = None) -> list[str]:
    spec = load(SPEC_PATH) if spec is None else spec
    return vrr.relationship_problems(
        report,
        spec,
        spec_sha256=hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest(),
    )


class LiteralKnownAnswerTests(unittest.TestCase):
    def test_good_fixture_passes_schema_and_independent_semantics(self) -> None:
        report = load(GOOD_PATH)
        self.assertEqual(vrr.schema_problems(report), [])
        self.assertEqual(semantic_problems(report), [])

    def test_fixture_pins_literal_targets_and_rejection(self) -> None:
        report = load(GOOD_PATH)
        self.assertEqual(report["per_lut"][0]["target_truth_table"], "64'h197787B4D6152EC4")
        self.assertEqual(report["per_lut"][1]["target_truth_table"], "64'h33D53591D3EB1710")
        self.assertEqual(report["per_lut"][1]["draw_index"], 2)
        self.assertEqual(
            report["per_lut"][1]["discarded_draws"],
            [{
                "draw_index": 1,
                "attainable_ceiling": 57,
                "blocked_positions": [1, 2, 4, 5, 7, 10, 18],
            }],
        )

    def test_literal_known_answer_meets_the_independent_implementation(self) -> None:
        entries = vrr.independent_target_vector(0x0001, 0)
        self.assertEqual(vrr.truth_table(entries), "64'h197787B4D6152EC4")
        self.assertEqual(entries[:8], [0, 0, 1, 0, 0, 0, 1, 1])
        self.assertEqual(sum(entries), 32)

    def test_all_known_bad_fixtures_are_schema_valid_but_semantically_refused(self) -> None:
        cases = {
            BAD_TARGET: "target_truth_table",
            BAD_SKIP: "draw_index",
            BAD_EARLY: "status",
        }
        for path, needle in cases.items():
            with self.subTest(path=path.name):
                report = load(path)
                self.assertEqual(vrr.schema_problems(report), [])
                found = semantic_problems(report)
                self.assertTrue(any(needle in item for item in found), found)


class AuthoritySchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.report = load(GOOD_PATH)

    def assertSchemaRefused(self, needle: str) -> None:
        found = vrr.schema_problems(self.report)
        self.assertTrue(any(needle in item for item in found), found)

    def test_unknown_top_level_field_is_refused(self) -> None:
        self.report["producer_summary"] = "passed"
        self.assertSchemaRefused("Additional properties")

    def test_selected_record_cannot_use_exhaustion_nulls(self) -> None:
        self.report["per_lut"][0]["target_truth_table"] = None
        self.assertSchemaRefused("not valid under any")

    def test_exhausted_record_cannot_carry_a_target(self) -> None:
        self.report["per_lut"][0]["exhausted"] = True
        self.assertSchemaRefused("not valid under any")

    def test_duplicate_blocked_position_is_refused(self) -> None:
        self.report["per_lut"][1]["blocked_positions"] = [4, 4, 10]
        self.assertSchemaRefused("not valid under any")

    def test_spec_sha256_is_top_level_as_the_frozen_spec_requires(self) -> None:
        self.assertIn("spec_sha256", self.report)
        self.assertNotIn("sha256", self.report["spec"])


class ReportSemanticMutationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.report = load(GOOD_PATH)

    def assertRefused(self, needle: str) -> None:
        self.assertEqual(vrr.schema_problems(self.report), [])
        found = semantic_problems(self.report)
        self.assertTrue(any(needle in item for item in found), found)

    def test_wrong_spec_hash_is_refused(self) -> None:
        self.report["spec_sha256"] = "0" * 64
        self.assertRefused("spec bytes")

    def test_missing_lut_is_refused(self) -> None:
        self.report["per_lut"].pop()
        self.assertRefused("LUT records")

    def test_extra_lut_is_refused(self) -> None:
        self.report["per_lut"].append(copy.deepcopy(self.report["per_lut"][0]))
        self.assertRefused("LUT records")

    def test_duplicate_lut_is_refused(self) -> None:
        self.report["per_lut"][1] = copy.deepcopy(self.report["per_lut"][0])
        self.assertRefused("per_lut[1]")

    def test_reordered_luts_are_refused(self) -> None:
        self.report["per_lut"].reverse()
        self.assertRefused("per_lut[0]")

    def test_balanced_but_wrong_target_is_refused(self) -> None:
        self.report["per_lut"][0]["target_truth_table"] = "64'hA9DD8F8A647C04B6"
        self.assertRefused("target_truth_table")

    def test_unbalanced_target_is_refused_by_derivation_not_format(self) -> None:
        self.report["per_lut"][0]["target_truth_table"] = "64'h0000000000000000"
        self.assertRefused("target_truth_table")

    def test_skipped_draw_is_refused(self) -> None:
        second = self.report["per_lut"][1]
        second.update(
            target_truth_table="64'h10B96AFF6C35921C",
            draw_index=3,
            attainable_ceiling=61,
            blocked_positions=[2, 4, 18],
        )
        self.report["totals"]["attainable_ceiling"] = 125
        self.assertRefused("draw_index")

    def test_reordered_discards_are_refused(self) -> None:
        second = self.report["per_lut"][1]
        second["discarded_draws"].insert(
            0,
            {"draw_index": 0, "attainable_ceiling": 60, "blocked_positions": [2, 7, 10, 18]},
        )
        self.report["totals"]["discarded_draws"] = 2
        self.assertRefused("discarded_draws")

    def test_an_acceptable_draw_cannot_be_recorded_as_discarded(self) -> None:
        second = self.report["per_lut"][1]
        second["discarded_draws"].append(
            {"draw_index": 2, "attainable_ceiling": 62, "blocked_positions": [4, 10]}
        )
        self.report["totals"]["discarded_draws"] = 2
        self.assertRefused("discarded_draws")

    def test_wrong_blocked_positions_are_refused(self) -> None:
        self.report["per_lut"][1]["blocked_positions"] = [4]
        self.assertRefused("blocked_positions")

    def test_wrong_ceiling_is_refused(self) -> None:
        self.report["per_lut"][1]["attainable_ceiling"] = 63
        self.assertRefused("attainable_ceiling")

    def test_wrong_totals_are_refused(self) -> None:
        self.report["totals"]["discarded_draws"] = 0
        self.assertRefused("totals.discarded_draws")

    def test_exhaustion_before_the_cap_is_refused(self) -> None:
        report = load(BAD_EARLY)
        found = semantic_problems(report)
        self.assertTrue(any("status" in item for item in found), found)
        self.assertTrue(any("target_truth_table" in item for item in found), found)


class ExhaustionBoundaryTests(unittest.TestCase):
    """Exercise the exact cap through a synthetic impossible LUT."""

    def impossible_spec(self) -> dict:
        spec = load(SPEC_PATH)
        lut = spec["phenotype"]["luts"][0]
        fixed = list(range(40))
        mutable = list(range(40, 64))
        lut["fixed_indices"] = fixed
        lut["fixed_count"] = 40
        lut["fixed_values"] = {str(index): 0 for index in fixed}
        lut["mutable_indices"] = mutable
        lut["mutable_count"] = 24
        lut["mutable_mask"] = "64'hFFFFFF0000000000"
        spec["phenotype"]["luts"] = [lut]
        spec["phenotype"]["lut_count"] = 1
        spec["phenotype"]["total_mutable_positions"] = 24
        spec["phenotype"]["total_fixed_positions"] = 40
        spec["target_family"]["redraw_cap"] = 256
        return spec

    def test_independent_derivation_exhausts_after_exactly_256_failures(self) -> None:
        contract, found = vrr.spec_contract(self.impossible_spec())
        self.assertEqual(found, [])
        self.assertIsNotNone(contract)
        status, records, totals = vrr.expected_report_body(contract)
        self.assertEqual(status, "exhausted")
        self.assertEqual(len(records), 1)
        self.assertEqual(len(records[0]["discarded_draws"]), 256)
        self.assertTrue(totals["exhausted"])

    def test_a_success_record_after_256_failures_is_refused(self) -> None:
        spec = self.impossible_spec()
        contract, found = vrr.spec_contract(spec)
        self.assertEqual(found, [])
        _, records, totals = vrr.expected_report_body(contract)
        report = {
            "schema": "reachability_report",
            "schema_version": "1.0.0",
            "report_id": "bad_success_after_cap",
            "spec": {
                "path": "specs/synthetic.json",
                "schema_version": "1.0.0",
                "spec_id": spec["spec_id"],
            },
            "spec_sha256": "0" * 64,
            "status": "complete",
            "per_lut": records,
            "totals": totals,
            "tool_versions": {"fixture": "1"},
        }
        report["per_lut"][0].update(
            target_truth_table="64'h0000000000000000",
            draw_index=256,
            attainable_ceiling=64,
            blocked_positions=[],
            exhausted=False,
        )
        report["totals"].update(selected_luts=1, attainable_ceiling=64, exhausted=False)
        found = vrr.relationship_problems(report, spec, spec_sha256="0" * 64)
        self.assertTrue(any("status" in item for item in found), found)
        self.assertTrue(any("target_truth_table" in item for item in found), found)


class SpecAuthorityAndIndependenceTests(unittest.TestCase):
    def test_committed_production_spec_is_interpretable_without_selecting_targets(self) -> None:
        contract, found = vrr.spec_contract(load(PRODUCTION_SPEC))
        self.assertEqual(found, [])
        self.assertIsNotNone(contract)
        self.assertEqual(len(contract.luts), 6)

    def test_verifier_imports_no_producer_module(self) -> None:
        source = (HOST / "verify_reachability_report.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(any("build_reachability_spec" in name for name in imports), imports)
        self.assertFalse(any("reachability_report" in name and name != "verify_reachability_report" for name in imports), imports)

    def test_production_cli_exposes_no_alternate_repository(self) -> None:
        result = subprocess.run(
            [sys.executable, str(HOST / "verify_reachability_report.py"), "--help"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("--repo", result.stdout)
        self.assertNotIn("--allow", result.stdout)

    def test_known_answer_drift_in_the_spec_is_refused(self) -> None:
        spec = load(SPEC_PATH)
        spec["target_family"]["bit_vector_convention"]["known_answer"]["init"] = "64'h0000000000000000"
        _, found = vrr.spec_contract(spec)
        self.assertTrue(any("known_answer INIT" in item for item in found), found)

    def test_global_scope_is_refused(self) -> None:
        spec = load(SPEC_PATH)
        spec["ceiling"]["scope"] = "all_luts"
        _, found = vrr.spec_contract(spec)
        self.assertTrue(any("scope" in item for item in found), found)

    def test_lock_pins_drift_is_refused(self) -> None:
        spec = load(SPEC_PATH)
        spec["phenotype"]["luts"][0]["lock_pins"] = "I0:A2"
        _, found = vrr.spec_contract(spec)
        self.assertTrue(any("lock_pins" in item for item in found), found)

    def test_malformed_required_fields_refuses_instead_of_throwing(self) -> None:
        spec = load(SPEC_PATH)
        spec["output"]["required_fields"].append({"not": "hashable"})
        contract, found = vrr.spec_contract(spec)
        self.assertIsNone(contract)
        self.assertTrue(any("required_fields" in item for item in found), found)

    def init_repo(self) -> tuple[tempfile.TemporaryDirectory, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        repo = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
        destination = repo / "tests/fixtures"
        destination.mkdir(parents=True)
        spec_path = destination / SPEC_PATH.name
        report_path = destination / GOOD_PATH.name
        spec_path.write_bytes(SPEC_PATH.read_bytes())
        report_path.write_bytes(GOOD_PATH.read_bytes())
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
        return temporary, repo, report_path

    def test_cli_accepts_a_spec_whose_bytes_are_in_head(self) -> None:
        _, repo, report = self.init_repo()
        found = vrr.verify_path(report, repo, require_production=False)
        self.assertEqual(found, [])

    def test_cli_refuses_a_working_spec_changed_after_commit(self) -> None:
        _, repo, report = self.init_repo()
        spec = repo / "tests/fixtures" / SPEC_PATH.name
        spec.write_bytes(spec.read_bytes() + b"\n")
        found = vrr.verify_path(report, repo, require_production=False)
        self.assertTrue(any("differ from HEAD" in item for item in found), found)

    def test_cli_refuses_without_git_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            destination = repo / "tests/fixtures"
            destination.mkdir(parents=True)
            (destination / SPEC_PATH.name).write_bytes(SPEC_PATH.read_bytes())
            report = destination / GOOD_PATH.name
            report.write_bytes(GOOD_PATH.read_bytes())
            found = vrr.verify_path(report, repo, require_production=False)
            self.assertTrue(any("no HEAD authority" in item for item in found), found)

    def test_production_mode_refuses_the_conformance_spec(self) -> None:
        _, repo, report = self.init_repo()
        found = vrr.verify_path(report, repo)
        self.assertTrue(any("production report must pin" in item for item in found), found)


if __name__ == "__main__":
    unittest.main()

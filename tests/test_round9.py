from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from host.verify_certificate import frozen_codeword_collisions


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
FEATURE14_FIXTURE = REPO_ROOT / "tests/fixtures/certificate_feature14_pass.json"
# The 1.3 record run B was certified under, archived byte-for-byte when the committed
# certificate was re-emitted at 1.4. `group14_certificate()` below still derives the
# recount from 1.3 evidence, independently of whatever the producer's emitter now
# writes; `tests/test_run_b_erratum.py` is what compares the emitted artifact to it.
GROUP13_FIXTURE = REPO_ROOT / "tests/fixtures/certificate_group13_run_b.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, *arguments],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def verify_temporary(
    value: dict[str, Any],
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "certificate.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return run("host/verify_certificate.py", str(path), *arguments)


def verify_with_predictions(
    certificate: dict[str, Any],
    predictions: dict[str, Any],
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    build_dir = REPO_ROOT / "build"
    build_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=build_dir) as directory:
        temporary = Path(directory)
        predictions_path = temporary / "predictions.json"
        encoded = json.dumps(predictions, separators=(",", ":"), sort_keys=True).encode()
        predictions_path.write_bytes(encoded)
        reference = certificate["prediction_commitment"]
        reference["path"] = str(predictions_path.relative_to(REPO_ROOT))
        reference["sha256"] = hashlib.sha256(encoded).hexdigest()
        certificate_path = temporary / "certificate.json"
        certificate_path.write_text(json.dumps(certificate), encoding="utf-8")
        return run("host/verify_certificate.py", str(certificate_path), *arguments)


def group14_certificate() -> dict[str, Any]:
    """Recount the committed 1.3 group evidence without changing its observations."""

    value = load(GROUP13_FIXTURE)
    value["schema_version"] = "1.4.0"
    holdout = [item for item in value["group_results"] if item["split"] == "holdout"]
    strict = copy.deepcopy(value["bit_class"]["address_accounting"]["scope_assignment"])
    decode_pass = 0
    decode_fail = 0
    for result in value["group_results"]:
        outcomes = {item["kind"]: item for item in result["assertion_outcomes"]}
        exclusivity = outcomes["group_exclusivity"]
        exclusivity.pop("passed")
        exclusivity["classification"] = "vacuous"
        decoded = copy.deepcopy(result["decoded_members"])
        decode_passed = bool(decoded)
        result["assertion_outcomes"].append(
            {
                "kind": "decode_validity",
                "semantic": False,
                "diagnostic": True,
                "passed": decode_passed,
                "decoded_members": decoded,
            }
        )
        if result["split"] == "holdout":
            if decode_passed:
                decode_pass += 1
            else:
                decode_fail += 1
    value["bit_class"]["address_accounting"] = {
        "strict_codeword_equality": strict,
    }
    value["bit_class"]["diagnostic_accounting"] = {
        "group_exclusivity": {
            "vacuous_count": len(holdout),
            "ambiguity_count": 0,
        },
        "decode_validity": {
            "pass_count": decode_pass,
            "fail_count": decode_fail,
        },
    }
    value["bit_class"]["decision_rule"] = (
        "holdout_address_assertions: strict_codeword_equality.fail_count == 0"
    )
    return value


class Round9Feature14Tests(unittest.TestCase):
    def certificate(self) -> dict[str, Any]:
        return load(FEATURE14_FIXTURE)

    def assert_fails(self, checked: subprocess.CompletedProcess[str], text: str) -> None:
        self.assertNotEqual(checked.returncode, 0, checked.stdout)
        self.assertIn(text, checked.stdout)

    def test_candidate_b_known_answer_passes_both_complementary_states(self) -> None:
        checked = run("host/verify_certificate.py", str(FEATURE14_FIXTURE))
        self.assertEqual(checked.returncode, 0, checked.stdout)
        self.assertIn("tp=2 fp=0 fn=0", checked.stdout)

    def test_duplicate_frozen_codeword_names_are_an_ambiguity(self) -> None:
        encodings = {
            "CLKINV": {(1, 51): 1},
            "OTHER_NAME": {(1, 51): 1},
            "NOCLKINV": {(1, 51): 0},
        }
        self.assertEqual(
            frozen_codeword_collisions(encodings),
            [["CLKINV", "OTHER_NAME"]],
        )

    def test_conformance_fixture_cannot_be_mistaken_for_production(self) -> None:
        checked = run(
            "host/verify_certificate.py",
            str(FEATURE14_FIXTURE),
            "--require-production",
        )
        self.assert_fails(checked, "profile='production'")

    def test_same_address_may_pass_opposite_states_in_different_specimens(self) -> None:
        value = self.certificate()
        first, second = value["feature_results"]
        self.assertNotEqual(first["feature_specimen_id"], second["feature_specimen_id"])
        checked = verify_temporary(value)
        self.assertEqual(checked.returncode, 0, checked.stdout)

    def test_same_specimen_address_cannot_report_two_observed_values(self) -> None:
        value = self.certificate()
        shared_baseline = value["feature_results"][0]["baseline_specimen_id"]
        removed_baseline = value["feature_results"][1]["baseline_specimen_id"]
        value["feature_results"][1]["baseline_specimen_id"] = shared_baseline
        value["specimens"] = [
            specimen
            for specimen in value["specimens"]
            if specimen["specimen_id"] != removed_baseline
        ]
        value["pair_accounting"][1]["specimen_ids"][0] = shared_baseline
        self.assert_fails(verify_temporary(value), "observation inconsistency")

    def test_all_committed_feature_keys_are_mandatory(self) -> None:
        value = self.certificate()
        value["feature_results"].pop()
        value["pair_accounting"].pop()
        value["specimens"] = value["specimens"][:2]
        value["bit_class"]["split"]["holdout_features"].pop()
        value["bit_class"]["coverage"]["attested_count"] = 1
        value["bit_class"]["accounting"]["tp_count"] = 1
        self.assert_fails(verify_temporary(value), "missing=1")

    def test_holdout_tp_fn_comes_from_endpoint_transition_not_diff(self) -> None:
        value = self.certificate()
        observed = value["feature_results"][0]["observed_assignments"][0]
        observed["after_value"] = 0
        observed["observed_value"] = 0
        value["feature_results"][0]["verdict"] = "mismatched"
        value["feature_results"][0]["semantic_outcome"]["passed"] = False
        value["bit_class"]["accounting"] = {"tp_count": 1, "fp_count": 0, "fn_count": 1}
        value["bit_class"]["semantic_accounting"]["member_identity"] = {
            "pass_count": 1,
            "fail_count": 1,
        }
        value["status"] = "failed"
        value["semantic_status"] = "failed"
        value["failure_reasons"] = [
            {"code": "holdout_false_negative", "detail": "endpoint transition mismatch"}
        ]
        checked = verify_temporary(value, "--allow-failed")
        self.assertEqual(checked.returncode, 0, checked.stdout)
        self.assertIn("fn=1", checked.stdout)

    def test_same_class_out_of_scope_db_bit_is_pair_level_fp(self) -> None:
        value = self.certificate()
        accounting = value["pair_accounting"][0]
        accounting["buckets"]["db_attributed"].append(
            {"far": "0x00400A1F", "word": 51, "bit": 3}
        )
        accounting["counts"]["db_attributed"] = 1
        accounting["raw_diff_bits"] = 2
        value["bit_class"]["accounting"]["fp_count"] = 1
        value["status"] = "failed"
        value["failure_reasons"] = [
            {"code": "holdout_false_positive", "detail": "unpredicted FF-class bit"}
        ]
        checked = verify_temporary(value, "--allow-failed")
        self.assertEqual(checked.returncode, 0, checked.stdout)
        self.assertIn("fp=1", checked.stdout)

    def test_semantic_only_failure_is_loud_but_does_not_fail_address_status(self) -> None:
        value = self.certificate()
        predictions = load(REPO_ROOT / value["prediction_commitment"]["path"])
        prediction = predictions["predictions"][0]
        result = value["feature_results"][0]
        prediction["semantic_assertion"]["expected_value"] = "WRONG_MODE"
        result["semantic_assertion"]["expected_value"] = "WRONG_MODE"
        result["semantic_outcome"]["expected_value"] = "WRONG_MODE"
        result["semantic_outcome"]["passed"] = False
        value["semantic_status"] = "failed"
        value["bit_class"]["semantic_accounting"]["member_identity"] = {
            "pass_count": 1,
            "fail_count": 1,
        }
        checked = verify_with_predictions(value, predictions)
        self.assertEqual(checked.returncode, 0, checked.stdout)
        self.assertIn("status=passed", checked.stdout)
        self.assertIn("semantic_status=failed semantic_pass=1 semantic_fail=1", checked.stdout)

    def test_semantic_outcome_summary_is_not_trusted(self) -> None:
        value = self.certificate()
        value["feature_results"][0]["semantic_outcome"]["passed"] = False
        self.assert_fails(verify_temporary(value), "differs from pinned attestation rebuild")

    def test_bucket_label_is_recomputed_from_frozen_evidence(self) -> None:
        value = self.certificate()
        accounting = value["pair_accounting"][0]
        bit = accounting["buckets"]["in_scope"].pop()
        accounting["counts"]["in_scope"] = 0
        accounting["buckets"]["db_attributed"].append(bit)
        accounting["counts"]["db_attributed"] = 1
        self.assert_fails(verify_temporary(value), "requires in_scope")

    def test_partition_hole_is_rejected(self) -> None:
        value = self.certificate()
        value["pair_accounting"][0]["raw_diff_bits"] = 2
        self.assert_fails(verify_temporary(value), "union size differs")


class Round9Group14Tests(unittest.TestCase):
    def assert_fails(self, checked: subprocess.CompletedProcess[str], text: str) -> None:
        self.assertNotEqual(checked.returncode, 0, checked.stdout)
        self.assertIn(text, checked.stdout)

    def test_run_b_recount_has_only_sixteen_falsifiable_address_passes(self) -> None:
        checked = verify_temporary(group14_certificate(), "--require-production")
        self.assertEqual(checked.returncode, 0, checked.stdout)
        self.assertIn("address_pass=16 address_fail=0", checked.stdout)
        self.assertIn("vacuous=16 ambiguity=0", checked.stdout)
        self.assertIn("semantic_pass=16 semantic_fail=0", checked.stdout)

    def test_vacuous_exclusivity_cannot_be_reintroduced_as_address_pass(self) -> None:
        value = group14_certificate()
        value["bit_class"]["address_accounting"]["group_exclusivity"] = {
            "pass_count": 16,
            "fail_count": 0,
        }
        self.assert_fails(verify_temporary(value), "address_accounting mismatch")

    def test_exclusivity_outcome_must_be_labelled_vacuous_without_passed(self) -> None:
        value = group14_certificate()
        outcome = next(
            item
            for item in value["group_results"][0]["assertion_outcomes"]
            if item["kind"] == "group_exclusivity"
        )
        outcome["passed"] = True
        self.assert_fails(verify_temporary(value), "valid under each")

    def test_decode_validity_is_recomputed_but_not_counted(self) -> None:
        value = group14_certificate()
        outcome = next(
            item
            for item in value["group_results"][0]["assertion_outcomes"]
            if item["kind"] == "decode_validity"
        )
        outcome["passed"] = False
        self.assert_fails(verify_temporary(value), "decode_validity diagnostic is wrong")


if __name__ == "__main__":
    unittest.main()

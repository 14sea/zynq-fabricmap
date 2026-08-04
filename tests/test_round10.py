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


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
FEATURE14 = REPO_ROOT / "tests/fixtures/certificate_feature14_pass.json"
FEATURE15 = REPO_ROOT / "tests/fixtures/certificate_feature15_pass.json"
WRONG_COMPARISON = (
    REPO_ROOT / "tests/fixtures/certificate_feature15_wrong_comparison.json"
)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "host/verify_certificate.py", str(path)],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def verify_temporary(certificate: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "certificate.json"
        path.write_text(json.dumps(certificate), encoding="utf-8")
        return run(path)


def verify_with_predictions(
    certificate: dict[str, Any],
    predictions: dict[str, Any],
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
        return run(certificate_path)


class Round10ComparisonLifecycleTests(unittest.TestCase):
    def certificate(self) -> dict[str, Any]:
        return load(FEATURE15)

    def predictions(self) -> dict[str, Any]:
        value = self.certificate()
        return load(REPO_ROOT / value["prediction_commitment"]["path"])

    def assert_fails(self, checked: subprocess.CompletedProcess[str], text: str) -> None:
        self.assertNotEqual(checked.returncode, 0, checked.stdout)
        self.assertIn(text, checked.stdout)

    def test_feature15_known_answer_passes(self) -> None:
        checked = run(FEATURE15)
        self.assertEqual(checked.returncode, 0, checked.stdout)
        self.assertIn("tp=2 fp=0 fn=0", checked.stdout)

    def test_published_feature14_record_keeps_its_original_contract(self) -> None:
        checked = run(FEATURE14)
        self.assertEqual(checked.returncode, 0, checked.stdout)

    def test_comparison_endpoint_is_required_at_feature15(self) -> None:
        certificate = self.certificate()
        predictions = self.predictions()
        predictions["predictions"][0].pop("comparison_specimen_id")
        self.assert_fails(
            verify_with_predictions(certificate, predictions),
            "fields differ from the evidence-model contract",
        )

    def test_feature15_cannot_hide_the_new_contract_in_an_old_artifact_version(self) -> None:
        certificate = self.certificate()
        predictions = self.predictions()
        predictions["schema_version"] = "1.4.0"
        certificate["prediction_commitment"]["schema_version"] = "1.4.0"
        self.assert_fails(
            verify_with_predictions(certificate, predictions),
            "schema prediction_commitment.schema_version",
        )

    def test_comparison_endpoint_must_name_an_artifact_specimen(self) -> None:
        certificate = self.certificate()
        predictions = self.predictions()
        predictions["predictions"][0]["comparison_specimen_id"] = "not_preregistered"
        self.assert_fails(
            verify_with_predictions(certificate, predictions),
            "names an unknown comparison specimen",
        )

    def test_comparison_endpoint_must_be_distinct(self) -> None:
        certificate = self.certificate()
        predictions = self.predictions()
        prediction = predictions["predictions"][0]
        prediction["comparison_specimen_id"] = prediction["specimen_id"]
        self.assert_fails(
            verify_with_predictions(certificate, predictions),
            "compares a specimen with itself",
        )

    def test_postbuild_baseline_substitution_fixture_fails(self) -> None:
        self.assert_fails(
            run(WRONG_COMPARISON),
            "baseline endpoint differs from preregistered comparison specimen",
        )

    def test_pair_accounting_may_not_omit_a_committed_pair(self) -> None:
        certificate = self.certificate()
        certificate["pair_accounting"].pop()
        self.assert_fails(
            verify_temporary(certificate),
            "pair_accounting endpoint-pair completeness mismatch",
        )

    def test_pair_accounting_may_not_substitute_a_self_consistent_result_pair(self) -> None:
        certificate = copy.deepcopy(load(WRONG_COMPARISON))
        self.assertEqual(
            {
                frozenset(item["specimen_ids"])
                for item in certificate["pair_accounting"]
            },
            {
                frozenset(
                    (result["baseline_specimen_id"], result["feature_specimen_id"])
                )
                for result in certificate["feature_results"]
            },
        )
        self.assert_fails(
            verify_temporary(certificate),
            "endpoint-pair completeness mismatch",
        )

    def test_commitment_names_both_endpoints_before_measurement(self) -> None:
        predictions = self.predictions()
        specimen_ids = {item["specimen_id"] for item in predictions["specimens"]}
        for prediction in predictions["predictions"]:
            self.assertIn(prediction["specimen_id"], specimen_ids)
            self.assertIn(prediction["comparison_specimen_id"], specimen_ids)
            self.assertNotEqual(
                prediction["specimen_id"], prediction["comparison_specimen_id"]
            )


if __name__ == "__main__":
    unittest.main()

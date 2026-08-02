from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
CERTIFICATE_FIXTURE = REPO_ROOT / "tests/fixtures/certificate_lifecycle_pass.json"
REAL_PREDICTIONS = REPO_ROOT / "gate_runs/run_2026_08_02_a/predictions.json"
REAL_MEASUREMENT = REPO_ROOT / "gate_runs/run_2026_08_02_a/measurement.json"


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, *arguments],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def certificate() -> dict[str, object]:
    return json.loads(CERTIFICATE_FIXTURE.read_text(encoding="utf-8"))


def verify_temporary(value: dict[str, object]) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "certificate.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return run("host/verify_certificate.py", str(path), "--require-production")


class Round4Tests(unittest.TestCase):
    def assert_fails(self, result: subprocess.CompletedProcess[str], text: str) -> None:
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(text, result.stdout)

    def test_lifecycle_profile_passes_with_duplicate_feature_names(self) -> None:
        result = run(
            "host/verify_certificate.py",
            str(CERTIFICATE_FIXTURE),
            "--require-production",
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("tp=2", result.stdout)

    def test_commitment_hash_must_match(self) -> None:
        value = certificate()
        value["prediction_commitment"]["sha256"] = "0" * 64
        self.assert_fails(verify_temporary(value), "prediction commitment hash mismatch")

    def test_commitment_seed_must_match_artifact(self) -> None:
        value = certificate()
        value["prediction_commitment"]["seed"] = "different-seed"
        self.assert_fails(verify_temporary(value), "seed differs from artifact")

    def test_commitment_totals_are_not_trusted(self) -> None:
        value = certificate()
        value["prediction_commitment"]["totals"]["predictions"] = 1
        self.assert_fails(verify_temporary(value), "totals differ from artifact")

    def test_certificate_prediction_must_match_every_preregistered_field(self) -> None:
        value = certificate()
        result = value["feature_results"][0]
        result["expected_transition"]["before"] = 1
        self.assert_fails(verify_temporary(value), "differs from preregistered prediction")

    def test_all_preregistered_holdout_pairs_are_mandatory(self) -> None:
        value = certificate()
        value["feature_results"] = value["feature_results"][:1]
        value["bit_class"]["coverage"]["attested_count"] = 1
        value["bit_class"]["accounting"]["tp_count"] = 1
        self.assert_fails(verify_temporary(value), "missing=1")

    def test_pair_key_collision_is_rejected(self) -> None:
        value = certificate()
        value["feature_results"][1]["prediction_specimen_id"] = "fixture_prediction_a"
        self.assert_fails(verify_temporary(value), "duplicate feature result key")

    def test_real_run_cherry_pick_reports_261_missing_holdout_pairs(self) -> None:
        value = certificate()
        predictions = json.loads(REAL_PREDICTIONS.read_text(encoding="utf-8"))
        measurement = json.loads(REAL_MEASUREMENT.read_text(encoding="utf-8"))
        chosen = next(item for item in predictions["predictions"] if item["split"] == "holdout")

        value["prediction_commitment"] = copy.deepcopy(measurement["prediction_commitment"])
        result = value["feature_results"][0]
        result["prediction_specimen_id"] = chosen["specimen_id"]
        for field in (
            "feature",
            "split",
            "rule_file",
            "predicted_assignments",
            "expected_transition",
        ):
            result[field] = copy.deepcopy(chosen[field])
        value["feature_results"] = [result]
        value["bit_class"]["split"] = {
            "mine_features": [],
            "holdout_features": [chosen["feature"]],
        }
        value["bit_class"]["coverage"]["attested_count"] = 1
        value["bit_class"]["accounting"] = {"tp_count": 0, "fp_count": 0, "fn_count": 1}
        value["status"] = "failed"
        value["failure_reasons"] = [{"code": "incomplete_coverage", "detail": "fixture cherry-pick"}]

        checked = verify_temporary(value)
        self.assert_fails(checked, "missing=261")
        self.assertNotIn("commitment hash mismatch", checked.stdout)
        self.assertNotIn("commitment totals differ", checked.stdout)


if __name__ == "__main__":
    unittest.main()

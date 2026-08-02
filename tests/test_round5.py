from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
REAL_CERTIFICATE = REPO_ROOT / "gate_runs/run_2026_08_02_a/certificate.json"
REAL_PREDICTIONS = REPO_ROOT / "gate_runs/run_2026_08_02_a/predictions.json"


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, *arguments],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


class Round5Tests(unittest.TestCase):
    def test_first_real_certificate_passes_production_verification(self) -> None:
        result = run(
            "host/verify_certificate.py",
            str(REAL_CERTIFICATE),
            "--require-production",
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("tp=262 fp=0 fn=0", result.stdout)

    def test_self_consistent_unpadded_token_is_rejected_by_frozen_text(self) -> None:
        certificate = json.loads(REAL_CERTIFICATE.read_text(encoding="utf-8"))
        predictions = json.loads(REAL_PREDICTIONS.read_text(encoding="utf-8"))
        prediction = next(
            item
            for item in predictions["predictions"]
            if any(re.fullmatch(r"!?[0-9]{2}_0[0-9]", bit["token"]) for bit in item["predicted_assignments"])
        )
        key = prediction["specimen_id"], prediction["feature"]
        result = next(
            item
            for item in certificate["feature_results"]
            if (item["prediction_specimen_id"], item["feature"]) == key
        )

        mutated_prediction = copy.deepcopy(prediction)
        mutated_result = result
        for bit in mutated_prediction["predicted_assignments"]:
            bit["token"] = re.sub(r"_0([0-9])$", r"_\1", bit["token"])
        mutated_result["predicted_assignments"] = copy.deepcopy(mutated_prediction["predicted_assignments"])
        prediction.update(mutated_prediction)

        build_dir = REPO_ROOT / "build"
        build_dir.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build_dir) as directory:
            temporary = Path(directory)
            predictions_path = temporary / "predictions.json"
            predictions_bytes = json.dumps(predictions, indent=2).encode("utf-8") + b"\n"
            predictions_path.write_bytes(predictions_bytes)
            reference = certificate["prediction_commitment"]
            reference["path"] = predictions_path.relative_to(REPO_ROOT).as_posix()
            reference["sha256"] = hashlib.sha256(predictions_bytes).hexdigest()

            certificate_path = temporary / "certificate.json"
            certificate_path.write_text(json.dumps(certificate), encoding="utf-8")
            checked = run(
                "host/verify_certificate.py",
                str(certificate_path),
                "--require-production",
            )

        self.assertNotEqual(checked.returncode, 0, checked.stdout)
        self.assertIn("token sequence differs from frozen rule text", checked.stdout)
        self.assertNotIn("differs from preregistered prediction", checked.stdout)


if __name__ == "__main__":
    unittest.main()

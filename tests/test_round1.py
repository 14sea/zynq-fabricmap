from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, *arguments],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


class Round1Tests(unittest.TestCase):
    def assert_ok(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stdout)

    def assert_fails(self, result: subprocess.CompletedProcess[str], text: str) -> None:
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(text, result.stdout)

    def test_independent_data_verifier_accepts_freeze(self) -> None:
        self.assert_ok(run("host/verify_data.py"))

    def test_independent_data_verifier_rejects_bad_hash(self) -> None:
        manifest = json.loads((REPO_ROOT / "data/MANIFEST.json").read_text(encoding="utf-8"))
        manifest["files"][0]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "MANIFEST.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run(
                "host/verify_data.py",
                "--data-dir",
                str(REPO_ROOT / "data"),
                "--manifest",
                str(path),
            )
        self.assert_fails(result, "sha256 mismatch")

    def test_address_known_answers_are_reproduced(self) -> None:
        self.assert_ok(run("host/verify_address_fixtures.py"))

    def test_address_verifier_rejects_wrong_far(self) -> None:
        fixture = json.loads(
            (REPO_ROOT / "tests/fixtures/address_known_answers.json").read_text(encoding="utf-8")
        )
        fixture["cases"][0]["expected_assignments"][0]["address"]["far"] = "0x00400A21"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "addresses.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            result = run("host/verify_address_fixtures.py", "--fixtures", str(path))
        self.assert_fails(result, "assignment mismatch")

    def test_passing_certificate_fixture(self) -> None:
        self.assert_ok(run("host/verify_certificate.py", "tests/fixtures/certificate_pass.json"))

    def test_failed_certificate_is_a_valid_record(self) -> None:
        result = run("host/verify_certificate.py", "tests/fixtures/certificate_fail.json")
        self.assert_ok(result)
        self.assertIn("status=failed", result.stdout)

    def test_certificate_verifier_rejects_false_pass(self) -> None:
        certificate = json.loads(
            (REPO_ROOT / "tests/fixtures/certificate_fail.json").read_text(encoding="utf-8")
        )
        certificate["status"] = "passed"
        certificate["failure_reasons"] = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "false-pass.json"
            path.write_text(json.dumps(certificate), encoding="utf-8")
            result = run("host/verify_certificate.py", str(path))
        self.assert_fails(result, "holdout evidence requires failed")

    def test_certificate_verifier_rejects_stale_freeze(self) -> None:
        certificate = json.loads(
            (REPO_ROOT / "tests/fixtures/certificate_pass.json").read_text(encoding="utf-8")
        )
        certificate["frozen_inputs"]["freeze_stamp"] = "2026-08-02T00:00:00Z"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stale.json"
            path.write_text(json.dumps(certificate), encoding="utf-8")
            result = run("host/verify_certificate.py", str(path))
        self.assert_fails(result, "freeze_stamp is stale")


if __name__ == "__main__":
    unittest.main()

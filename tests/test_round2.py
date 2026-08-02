from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
PASS_FIXTURE = REPO_ROOT / "tests/fixtures/certificate_segbits_pass.json"


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, *arguments],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def verify_temporary(certificate: dict[str, object]) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "certificate.json"
        path.write_text(json.dumps(certificate), encoding="utf-8")
        return run("host/verify_certificate.py", str(path))


class Round2Tests(unittest.TestCase):
    def test_nonempty_segbits_pass_conforms(self) -> None:
        result = run("host/verify_certificate.py", str(PASS_FIXTURE))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_nonempty_segbits_failure_is_valid_record(self) -> None:
        result = run(
            "host/verify_certificate.py",
            "tests/fixtures/certificate_segbits_fail.json",
            "--allow-failed",
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("fn=1", result.stdout)

    def test_complete_rule_check_rejects_self_consistent_wrong_segbit(self) -> None:
        certificate = json.loads(PASS_FIXTURE.read_text(encoding="utf-8"))
        result = certificate["feature_results"][0]
        result["predicted_assignments"][0]["segbit"]["frame_offset"] = 32
        for evidence in (
            result["predicted_assignments"],
            result["observed_assignments"],
            result["observed_diff"],
        ):
            evidence[0]["address"]["far"] = "0x00400A20"
        checked = verify_temporary(certificate)
        self.assertNotEqual(checked.returncode, 0, checked.stdout)
        self.assertIn("prediction differs from complete frozen segbits rule", checked.stdout)

    def test_address_check_rejects_self_consistent_wrong_far(self) -> None:
        certificate = json.loads(PASS_FIXTURE.read_text(encoding="utf-8"))
        result = certificate["feature_results"][0]
        for evidence in (
            result["predicted_assignments"],
            result["observed_assignments"],
            result["observed_diff"],
        ):
            evidence[0]["address"]["far"] = "0x00400A20"
        checked = verify_temporary(certificate)
        self.assertNotEqual(checked.returncode, 0, checked.stdout)
        self.assertIn("absolute address disagrees with normative arithmetic", checked.stdout)


if __name__ == "__main__":
    unittest.main()

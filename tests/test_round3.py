from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
CERTIFICATE_FIXTURE = REPO_ROOT / "tests/fixtures/certificate_production_pass.json"
ATTESTATION_FIXTURE = REPO_ROOT / "tests/samples/specimen_attestation.sample.json"


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


def verify_with_attestation_mutation(
    mutate: Callable[[dict[str, object]], None],
) -> subprocess.CompletedProcess[str]:
    value = certificate()
    attestation = json.loads(ATTESTATION_FIXTURE.read_text(encoding="utf-8"))
    mutate(attestation)
    build_dir = REPO_ROOT / "build"
    build_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=build_dir) as directory:
        path = Path(directory) / "attestation.json"
        encoded = json.dumps(attestation, indent=2).encode("utf-8") + b"\n"
        path.write_bytes(encoded)
        reference_path = path.relative_to(REPO_ROOT).as_posix()
        reference_hash = hashlib.sha256(encoded).hexdigest()
        for specimen in value["specimens"]:
            specimen["attestation"]["path"] = reference_path
            specimen["attestation"]["sha256"] = reference_hash
        return verify_temporary(value)


class Round3Tests(unittest.TestCase):
    def assert_fails(self, result: subprocess.CompletedProcess[str], text: str) -> None:
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(text, result.stdout)

    def test_production_profile_passes(self) -> None:
        result = run(
            "host/verify_certificate.py",
            str(CERTIFICATE_FIXTURE),
            "--require-production",
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_production_mode_rejects_legacy_profile_omission(self) -> None:
        result = run(
            "host/verify_certificate.py",
            "tests/fixtures/certificate_segbits_pass.json",
            "--require-production",
        )
        self.assert_fails(result, "requires profile='production'")

    def test_production_profile_rejects_missing_attestation(self) -> None:
        value = certificate()
        del value["specimens"][0]["attestation"]
        self.assert_fails(verify_temporary(value), "'attestation' is a required property")

    def test_attestation_hash_must_match(self) -> None:
        value = certificate()
        value["specimens"][0]["attestation"]["sha256"] = "0" * 64
        self.assert_fails(verify_temporary(value), "attestation hash mismatch")

    def test_attestation_output_must_include_bitstream(self) -> None:
        value = certificate()
        value["specimens"][0]["bitstream_sha256"] = "6" * 64
        self.assert_fails(verify_temporary(value), "bitstream_sha256 is absent from attestation outputs")

    def test_attestation_resolved_loc_must_match_specimen(self) -> None:
        result = verify_with_attestation_mutation(
            lambda value: value["resolved"].__setitem__("resolved_loc", "SLICE_X3Y25")
        )
        self.assert_fails(result, "attested resolved_loc differs from loc_site")

    def test_attestation_tile_must_match_specimen(self) -> None:
        result = verify_with_attestation_mutation(
            lambda value: value["resolved"].__setitem__("tile", "CLBLL_L_X2Y24")
        )
        self.assert_fails(result, "attested tile differs from specimen tile")

    def test_lut_init_requires_attested_identity_pin_mapping(self) -> None:
        result = verify_with_attestation_mutation(
            lambda value: value["resolved"].__setitem__("pin_mapping_is_identity", False)
        )
        self.assert_fails(result, "does not attest identity LUT pin mapping")

    def test_excluded_bit_must_satisfy_ecc_rule(self) -> None:
        value = certificate()
        value["feature_results"][0]["excluded_diff"][0]["address"]["word"] = 49
        self.assert_fails(verify_temporary(value), "does not satisfy frame_ecc rule")

    def test_production_profile_rejects_missing_exclusion_evidence(self) -> None:
        value = certificate()
        del value["feature_results"][0]["exclusion_rules"]
        del value["feature_results"][0]["excluded_diff"]
        self.assert_fails(verify_temporary(value), "'exclusion_rules' is a required property")

    def test_observed_predicted_bit_cannot_also_be_excluded(self) -> None:
        value = certificate()
        excluded = value["feature_results"][0]["excluded_diff"][0]
        excluded["address"] = {"far": "0x00400A21", "word": 51, "bit": 15}
        checked = verify_temporary(value)
        self.assert_fails(checked, "is both observed and excluded")
        self.assertIn("predicted address", checked.stdout)

    def test_ecc_only_frame_is_rejected(self) -> None:
        value = certificate()
        extra = json.loads(json.dumps(value["feature_results"][0]["excluded_diff"][0]))
        extra["address"] = {"far": "0x00400A22", "word": 50, "bit": 1}
        value["feature_results"][0]["excluded_diff"].append(extra)
        self.assert_fails(verify_temporary(value), "excluded ECC-only frame 0x00400A22")

    def test_ecc_shaped_observed_diff_must_be_excluded(self) -> None:
        value = certificate()
        result = value["feature_results"][0]
        result["observed_diff"].append(
            {
                "address": {"far": "0x00400A21", "word": 50, "bit": 4},
                "before_value": 0,
                "after_value": 1,
            }
        )
        result["unattributed_diff"].append(
            {
                "address": {"far": "0x00400A21", "word": 50, "bit": 4},
                "before_value": 0,
                "after_value": 1,
                "listed_in_frozen_mask": False,
            }
        )
        self.assert_fails(verify_temporary(value), "ECC-shaped observed diff")


if __name__ == "__main__":
    unittest.main()

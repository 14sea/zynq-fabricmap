"""Consumer-side known answers for ``host/verify_local_map.py``.

The synthetic bundle is intentionally not emitted by ``build_local_map.py``.  In
particular it contains the negated polarity that the 292 real entries cannot exercise.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOST = REPO_ROOT / "host"
sys.path.insert(0, str(HOST))

import verify_local_map as vlm  # noqa: E402

FIXTURE = REPO_ROOT / "tests/fixtures/local_map_negated_bundle.json"
REAL_MAP = REPO_ROOT / "maps/clb_lut_init_v1.local_map.json"


def bundle() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def problems(value: dict) -> list[str]:
    return vlm.relationship_problems(
        value["local_map"],
        value["certificate"],
        value["frozen_manifest"],
        certificate_sha256=value["certificate_sha256"],
        manifest_sha256=value["manifest_sha256"],
    )


class LocalMapAuthorityTests(unittest.TestCase):
    def test_real_map_passes_the_independent_cli(self) -> None:
        checked = subprocess.run(
            [sys.executable, str(HOST / "verify_local_map.py"), str(REAL_MAP)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn("292 addresses, 12 frames, 6 LUTs", checked.stdout)

    def test_authority_schema_is_final_and_real_map_conforms(self) -> None:
        schema = json.loads(vlm.SCHEMA.read_text(encoding="utf-8"))
        self.assertNotIn("PROPOSAL", schema["title"])
        self.assertNotIn("PROPOSAL", schema["description"])
        real = json.loads(REAL_MAP.read_text(encoding="utf-8"))
        self.assertEqual(vlm.schema_problems(real), [])

    def test_negated_known_answer_passes(self) -> None:
        value = bundle()
        self.assertEqual(value["local_map"]["universe"]["addresses"][0]["expected_value"], 0)
        self.assertEqual(vlm.schema_problems(value["local_map"]), [])
        self.assertEqual(problems(value), [])

    def test_wrong_negated_value_is_rejected_even_when_map_and_certificate_agree(self) -> None:
        value = bundle()
        assignment = value["certificate"]["feature_results"][0]["predicted_assignments"][0]
        assignment["expected_value"] = 1
        value["certificate"]["feature_results"][0]["observed_assignments"][0]["observed_value"] = 1
        value["local_map"]["universe"]["addresses"][0]["expected_value"] = 1
        found = problems(value)
        self.assertTrue(any("segbit.negated polarity" in item for item in found), found)

    def test_token_and_structured_polarity_must_agree(self) -> None:
        value = bundle()
        value["certificate"]["feature_results"][0]["predicted_assignments"][0]["token"] = "32_15"
        found = problems(value)
        self.assertTrue(any("token spelling" in item for item in found), found)

    def test_an_unattested_entry_is_rejected_even_if_map_is_self_consistent(self) -> None:
        value = bundle()
        doc = value["local_map"]
        extra = copy.deepcopy(doc["universe"]["addresses"][1])
        extra.update(
            key="0x00400A20/51/17",
            bit=17,
            feature="CLBLL_L.SLICEL_X0.CLUT.INIT[02]",
        )
        doc["universe"]["addresses"].append(extra)
        doc["universe"]["address_count"] = 3
        doc["bit_class"]["attested_count"] = 3
        doc["index"]["by_far"]["0x00400A20"].append(extra["key"])
        doc["index"]["by_lut"]["CLBLL_L.SLICEL_X0.CLUT"] = [
            {"init_index": 2, "address_key": extra["key"]}
        ]
        found = problems(value)
        self.assertTrue(any("certificate-attested universe" in item for item in found), found)

    def test_by_lut_cannot_merge_two_truth_tables(self) -> None:
        value = bundle()
        indexes = value["local_map"]["index"]["by_lut"]
        indexes["CLBLL_L.SLICEL_X0.ALUT"].extend(indexes.pop("CLBLL_L.SLICEL_X0.BLUT"))
        found = problems(value)
        self.assertTrue(any("exact by_far/by_lut" in item for item in found), found)

    def test_wrong_certificate_hash_is_rejected(self) -> None:
        value = bundle()
        value["local_map"]["provenance"]["certificate"]["sha256"] = "c" * 64
        found = problems(value)
        self.assertTrue(any("certificate bytes" in item for item in found), found)

    def test_wrong_manifest_hash_is_rejected(self) -> None:
        value = bundle()
        value["local_map"]["provenance"]["frozen_data"]["sha256"] = "d" * 64
        found = problems(value)
        self.assertTrue(any("manifest bytes" in item for item in found), found)

    def test_failed_certificate_is_rejected(self) -> None:
        value = bundle()
        value["certificate"]["status"] = "failed"
        value["local_map"]["provenance"]["certificate"]["status"] = "failed"
        found = problems(value)
        self.assertTrue(any("status is not passed" in item for item in found), found)

    def test_conformance_certificate_is_rejected(self) -> None:
        value = bundle()
        value["certificate"]["profile"] = "conformance"
        value["local_map"]["provenance"]["certificate"]["profile"] = "conformance"
        found = problems(value)
        self.assertTrue(any("profile is not production" in item for item in found), found)

    def test_collateral_is_derived_from_every_certificate_result(self) -> None:
        value = bundle()
        value["certificate"]["feature_results"][1]["exclusion_rules"][0]["why"] = "other"
        found = problems(value)
        self.assertTrue(any("distinct frame_ecc" in item for item in found), found)

    def test_map_cannot_choose_its_own_collateral_rule(self) -> None:
        value = bundle()
        value["local_map"]["collateral"]["frame_ecc"]["bit_high"] = 13
        found = problems(value)
        self.assertTrue(any("collateral differs" in item for item in found), found)

    def test_disagreeing_reattestation_is_rejected(self) -> None:
        value = bundle()
        duplicate = copy.deepcopy(value["certificate"]["feature_results"][0])
        duplicate["predicted_assignments"][0]["address"]["bit"] = 14
        duplicate["observed_assignments"][0]["address"]["bit"] = 14
        value["certificate"]["feature_results"].append(duplicate)
        found = problems(value)
        self.assertTrue(any("re-attestation disagrees" in item for item in found), found)

    def test_round_one_refuses_a_stronger_provenance_kind(self) -> None:
        value = bundle()["local_map"]
        value["provenance"]["kind"] = "self_cartography"
        found = vlm.schema_problems(value)
        self.assertTrue(any("certificate_inherited" in item for item in found), found)


if __name__ == "__main__":
    unittest.main()

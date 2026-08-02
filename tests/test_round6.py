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
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
RUN_DIR = REPO_ROOT / "gate_runs/run_2026_08_02_b"
PREDICTIONS_PATH = RUN_DIR / "predictions.json"
MEASUREMENT_PATH = RUN_DIR / "measurement.json"
FEATURE_CERTIFICATE = REPO_ROOT / "gate_runs/run_2026_08_02_a/certificate.json"


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


def build_certificate() -> dict[str, Any]:
    """Build a consumer fixture solely from the committed Round 6 artifacts."""

    predictions = load(PREDICTIONS_PATH)
    measurement = load(MEASUREMENT_PATH)
    feature_certificate = load(FEATURE_CERTIFICATE)
    manifest = load(REPO_ROOT / "data/MANIFEST.json")
    prediction_by_key = {
        (item["specimen_id"], item["group"]): item
        for item in predictions["predictions"]
    }
    group_results = []
    for observed in measurement["results"]:
        key = observed["specimen_id"], observed["group"]
        prediction = prediction_by_key[key]
        group_results.append(
            {
                "prediction_specimen_id": observed["specimen_id"],
                "group": prediction["group"],
                "split": prediction["split"],
                "rule_file": prediction["rule_file"],
                "scope": copy.deepcopy(prediction["scope"]),
                "assertions": copy.deepcopy(prediction["assertions"]),
                "decoded_members": copy.deepcopy(observed["decoded_members"]),
                "observed_assignment": copy.deepcopy(observed["observed_assignment"]),
                "assertion_outcomes": copy.deepcopy(observed["assertion_outcomes"]),
            }
        )

    holdout_results = [item for item in group_results if item["split"] == "holdout"]
    address_accounting = {
        kind: {
            "pass_count": sum(
                outcome["passed"] is True
                for item in holdout_results
                for outcome in item["assertion_outcomes"]
                if outcome["kind"] == kind
            ),
            "fail_count": sum(
                outcome["passed"] is False
                for item in holdout_results
                for outcome in item["assertion_outcomes"]
                if outcome["kind"] == kind
            ),
        }
        for kind in ("group_exclusivity", "scope_assignment")
    }
    semantic_accounting = {
        "member_identity": {
            "pass_count": sum(
                outcome["passed"] is True
                for item in holdout_results
                for outcome in item["assertion_outcomes"]
                if outcome["kind"] == "member_identity"
            ),
            "fail_count": sum(
                outcome["passed"] is False
                for item in holdout_results
                for outcome in item["assertion_outcomes"]
                if outcome["kind"] == "member_identity"
            ),
        }
    }
    current_class = next(item for item in manifest["bit_classes"] if item["id"] == "clb_mux")
    specimens = []
    for specimen in measurement["specimens"]:
        specimens.append(
            {
                key: copy.deepcopy(specimen[key])
                for key in (
                    "specimen_id",
                    "split",
                    "site",
                    "ff_bel",
                    "ffsrc",
                    "tile",
                    "tile_type",
                    "bitstream_sha256",
                    "attestation",
                )
            }
        )

    return {
        "schema": "fabric_bit_class_certificate",
        "schema_version": "1.3.0",
        "evidence_model": "group",
        "profile": "production",
        "certificate_id": "round6_true_artifact_fixture",
        "status": "passed",
        "semantic_status": "passed",
        "failure_reasons": [],
        "claim_scope": "group_bit_set",
        "prediction_commitment": copy.deepcopy(measurement["prediction_commitment"]),
        "gate_run": {
            "gate_id": "run_2026_08_02_b",
            "started_at": "2026-08-02T10:00:00Z",
            "completed_at": "2026-08-02T10:00:00Z",
            "tool_versions": {"fixture": "round6-consumer/1.0.0"},
        },
        "target": copy.deepcopy(feature_certificate["target"]),
        "frozen_inputs": copy.deepcopy(feature_certificate["frozen_inputs"]),
        "bit_class": {
            "id": "clb_mux",
            "tier": current_class["tier"],
            "manifest_entries": current_class["entries"],
            "split": {
                "mine_groups": sorted({item["group"] for item in group_results if item["split"] == "mine"}),
                "holdout_groups": sorted(
                    {item["group"] for item in group_results if item["split"] == "holdout"}
                ),
            },
            "coverage": {
                "attested_count": len(group_results),
                "class_entry_count": current_class["entries"],
            },
            "address_accounting": address_accounting,
            "semantic_accounting": semantic_accounting,
            "decision_rule": (
                "holdout_address_assertions: group_exclusivity.fail_count == 0 and "
                "scope_assignment.fail_count == 0"
            ),
            "semantic_rule": "member_identity is reported independently and never contributes to status",
        },
        "specimens": specimens,
        "group_results": group_results,
        "pair_accounting": copy.deepcopy(measurement["accounting"]),
    }


def write_json(path: Path, value: dict[str, Any]) -> str:
    payload = json.dumps(value, indent=2).encode("utf-8") + b"\n"
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def verify_temporary(value: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    build_dir = REPO_ROOT / "build"
    build_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=build_dir) as directory:
        path = Path(directory) / "certificate.json"
        write_json(path, value)
        return run("host/verify_certificate.py", str(path), "--require-production")


def verify_with_predictions(
    value: dict[str, Any],
    predictions: dict[str, Any],
) -> subprocess.CompletedProcess[str]:
    build_dir = REPO_ROOT / "build"
    build_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=build_dir) as directory:
        temporary = Path(directory)
        predictions_path = temporary / "predictions.json"
        digest = write_json(predictions_path, predictions)
        reference = value["prediction_commitment"]
        reference["path"] = predictions_path.relative_to(REPO_ROOT).as_posix()
        reference["sha256"] = digest
        certificate_path = temporary / "certificate.json"
        write_json(certificate_path, value)
        return run("host/verify_certificate.py", str(certificate_path), "--require-production")


def inject_semantic_edge_failure(value: dict[str, Any], temporary: Path) -> None:
    """Create pinned routed evidence that disagrees only with semantic edge identity."""

    result = next(
        item
        for item in value["group_results"]
        if item["split"] == "holdout"
        and next(
            assertion for assertion in item["assertions"] if assertion["kind"] == "member_identity"
        )["netlist_basis"]
        == "FF.D driven by a package pin through the slice bypass"
    )
    specimen = next(
        item for item in value["specimens"] if item["specimen_id"] == result["prediction_specimen_id"]
    )
    attestation = load(REPO_ROOT / specimen["attestation"]["path"])
    attestation["resolved"]["ff_d_driver_ref"] = "BUFG"
    semantic = next(item for item in result["assertion_outcomes"] if item["kind"] == "member_identity")
    semantic["attested_edge"]["ff_d_driver_ref"] = "BUFG"
    semantic["netlist_basis_consistent"] = False
    semantic["passed"] = False
    value["semantic_status"] = "failed"
    semantic_count = value["bit_class"]["semantic_accounting"]["member_identity"]
    semantic_count["pass_count"] -= 1
    semantic_count["fail_count"] += 1
    attestation_path = temporary / "attestation.json"
    specimen["attestation"]["sha256"] = write_json(attestation_path, attestation)
    specimen["attestation"]["path"] = attestation_path.relative_to(REPO_ROOT).as_posix()


class Round6Tests(unittest.TestCase):
    def assert_fails(self, checked: subprocess.CompletedProcess[str], text: str) -> None:
        self.assertNotEqual(checked.returncode, 0, checked.stdout)
        self.assertIn(text, checked.stdout)

    def test_true_group_artifacts_conform(self) -> None:
        checked = verify_temporary(build_certificate())
        self.assertEqual(checked.returncode, 0, checked.stdout)
        self.assertIn("status=passed", checked.stdout)
        self.assertIn("address_pass=32 address_fail=0", checked.stdout)
        self.assertIn("semantic_status=passed semantic_pass=16 semantic_fail=0", checked.stdout)

    def test_truncated_scope_is_rejected_even_when_commitment_matches(self) -> None:
        value = build_certificate()
        predictions = load(PREDICTIONS_PATH)
        result = value["group_results"][0]
        key = result["prediction_specimen_id"], result["group"]
        prediction = next(
            item for item in predictions["predictions"] if (item["specimen_id"], item["group"]) == key
        )
        kept = {item["segbit"] for item in result["scope"][1::2]}
        result["scope"] = [item for item in result["scope"] if item["segbit"] in kept]
        result["observed_assignment"] = [
            item for item in result["observed_assignment"] if item["segbit"] in kept
        ]
        scope_assertion = next(item for item in result["assertions"] if item["kind"] == "scope_assignment")
        scope_assertion["expected_assignment"] = [
            item for item in scope_assertion["expected_assignment"] if item["segbit"] in kept
        ]
        for field in ("scope", "assertions"):
            prediction[field] = copy.deepcopy(result[field])

        checked = verify_with_predictions(value, predictions)
        self.assert_fails(checked, "declared scope is not a complete frozen bit-set group")
        self.assertNotIn("differs from preregistered prediction", checked.stdout)

    def test_group_segbit_text_requires_frozen_zero_padding(self) -> None:
        value = build_certificate()
        predictions = load(PREDICTIONS_PATH)
        result = value["group_results"][0]
        key = result["prediction_specimen_id"], result["group"]
        prediction = next(
            item for item in predictions["predictions"] if (item["specimen_id"], item["group"]) == key
        )
        padded = next(item["segbit"] for item in result["scope"] if re.search(r"_0[0-9]$", item["segbit"]))
        unpadded = re.sub(r"_0([0-9])$", r"_\1", padded)
        for collection in (
            result["scope"],
            next(
                item for item in result["assertions"] if item["kind"] == "scope_assignment"
            )["expected_assignment"],
            result["observed_assignment"],
        ):
            next(item for item in collection if item["segbit"] == padded)["segbit"] = unpadded
        prediction["scope"] = copy.deepcopy(result["scope"])
        prediction["assertions"] = copy.deepcopy(result["assertions"])

        checked = verify_with_predictions(value, predictions)
        self.assert_fails(checked, "does not match '^[0-9]{2}_[0-9]{2}$'")

    def test_every_committed_holdout_group_pair_is_required(self) -> None:
        value = build_certificate()
        removed = next(item for item in value["group_results"] if item["split"] == "holdout")
        value["group_results"].remove(removed)
        value["bit_class"]["coverage"]["attested_count"] -= 1
        checked = verify_temporary(value)
        self.assert_fails(checked, "holdout group completeness mismatch (missing=1")

    def test_group_commitment_totals_are_independently_recounted(self) -> None:
        value = build_certificate()
        predictions = load(PREDICTIONS_PATH)
        predictions["totals"]["assertions"] -= 1
        value["prediction_commitment"]["totals"] = copy.deepcopy(predictions["totals"])
        checked = verify_with_predictions(value, predictions)
        self.assert_fails(checked, "prediction artifact totals mismatch")

    def test_group_commitment_frozen_file_hash_must_match_certificate(self) -> None:
        value = build_certificate()
        predictions = load(PREDICTIONS_PATH)
        rule_file = value["group_results"][0]["rule_file"]
        predictions["frozen_inputs"]["files"][rule_file] = "0" * 64
        checked = verify_with_predictions(value, predictions)
        self.assert_fails(checked, "prediction artifact frozen file differs from certificate")

    def test_group_rule_must_match_the_specimen_site_instance(self) -> None:
        value = build_certificate()
        predictions = load(PREDICTIONS_PATH)
        result = next(
            item
            for item in value["group_results"]
            if item["prediction_specimen_id"].startswith("SLICE_X8Y25_AFF_ffsrc0")
        )
        wrong_instance = next(
            item
            for item in value["group_results"]
            if item["prediction_specimen_id"].startswith("SLICE_X9Y25_AFF_ffsrc0")
        )
        old_group = result["group"]
        for field in (
            "group",
            "rule_file",
            "scope",
            "assertions",
            "decoded_members",
            "observed_assignment",
            "assertion_outcomes",
        ):
            result[field] = copy.deepcopy(wrong_instance[field])
        prediction = next(
            item
            for item in predictions["predictions"]
            if (item["specimen_id"], item["group"])
            == (result["prediction_specimen_id"], old_group)
        )
        for field in ("group", "rule_file", "scope", "assertions"):
            prediction[field] = copy.deepcopy(result[field])

        checked = verify_with_predictions(value, predictions)
        self.assert_fails(checked, "feature does not match specimen tile/site instance")
        self.assertNotIn("differs from preregistered prediction", checked.stdout)

    def test_certificate_specimen_identity_is_pinned_by_commitment(self) -> None:
        value = build_certificate()
        value["specimens"][0]["ffsrc"] = 1
        checked = verify_temporary(value)
        self.assert_fails(checked, "differs from preregistered specimen identity")

    def test_claimed_two_member_decode_is_rejected(self) -> None:
        value = build_certificate()
        result = next(item for item in value["group_results"] if item["split"] == "holdout")
        result["decoded_members"] = ["AX", "O6"]
        exclusivity = next(
            item for item in result["assertion_outcomes"] if item["kind"] == "group_exclusivity"
        )
        exclusivity["decoded_members"] = ["AX", "O6"]
        exclusivity["passed"] = False
        semantic = next(item for item in result["assertion_outcomes"] if item["kind"] == "member_identity")
        semantic["decoded_members"] = ["AX", "O6"]
        semantic["passed"] = False
        value["status"] = "failed"
        value["failure_reasons"] = [
            {"code": "holdout_group_exclusivity", "detail": "adversarial two-member decode"}
        ]
        address = value["bit_class"]["address_accounting"]["group_exclusivity"]
        address["pass_count"] -= 1
        address["fail_count"] += 1
        value["semantic_status"] = "failed"
        semantic_count = value["bit_class"]["semantic_accounting"]["member_identity"]
        semantic_count["pass_count"] -= 1
        semantic_count["fail_count"] += 1

        checked = verify_temporary(value)
        self.assert_fails(checked, "decoded_members differs from frozen assert-iff")

    def test_semantic_only_failure_passes_address_decision_and_is_loud(self) -> None:
        value = build_certificate()
        build_dir = REPO_ROOT / "build"
        build_dir.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build_dir) as directory:
            temporary = Path(directory)
            inject_semantic_edge_failure(value, temporary)
            certificate_path = temporary / "certificate.json"
            write_json(certificate_path, value)
            checked = run(
                "host/verify_certificate.py",
                str(certificate_path),
                "--require-production",
            )

        self.assertEqual(checked.returncode, 0, checked.stdout)
        self.assertIn("status=passed", checked.stdout)
        self.assertIn("address_fail=0", checked.stdout)
        self.assertIn("semantic_status=failed", checked.stdout)
        self.assertIn("semantic_fail=1", checked.stdout)

    def test_semantic_failure_must_not_be_folded_into_address_status(self) -> None:
        value = build_certificate()
        value["status"] = "failed"
        value["failure_reasons"] = [{"code": "other", "detail": "semantic folded into address"}]

        build_dir = REPO_ROOT / "build"
        build_dir.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build_dir) as directory:
            temporary = Path(directory)
            inject_semantic_edge_failure(value, temporary)
            certificate_path = temporary / "certificate.json"
            write_json(certificate_path, value)
            checked = run(
                "host/verify_certificate.py",
                str(certificate_path),
                "--require-production",
            )

        self.assert_fails(checked, "address evidence requires passed")

    def test_producer_expected_edge_copy_is_not_trusted(self) -> None:
        value = build_certificate()
        result = value["group_results"][0]
        semantic = next(item for item in result["assertion_outcomes"] if item["kind"] == "member_identity")
        semantic["expected_edge"] = {"driver_ref": "IBUF", "requires_source_port": True}
        checked = verify_temporary(value)
        self.assert_fails(checked, "expected_edge differs from independent rebuild")

    def test_producer_consistency_boolean_is_not_trusted(self) -> None:
        value = build_certificate()
        result = value["group_results"][0]
        semantic = next(item for item in result["assertion_outcomes"] if item["kind"] == "member_identity")
        semantic["netlist_basis_consistent"] = False
        checked = verify_temporary(value)
        self.assert_fails(checked, "netlist_basis_consistent summary is wrong")

    def test_bucket_overlap_is_rejected_from_bit_identity(self) -> None:
        value = build_certificate()
        accounting = value["pair_accounting"][0]
        duplicated = copy.deepcopy(accounting["buckets"]["in_scope"][0])
        accounting["buckets"]["db_attributed"].append(duplicated)
        accounting["counts"]["db_attributed"] += 1
        accounting["partition_exact"] = False
        checked = verify_temporary(value)
        self.assert_fails(checked, "bucket overlap")

    def test_uncovered_raw_diff_bit_is_rejected(self) -> None:
        value = build_certificate()
        accounting = value["pair_accounting"][0]
        accounting["raw_diff_bits"] += 1
        accounting["partition_exact"] = False
        checked = verify_temporary(value)
        self.assert_fails(checked, "bucket union size differs from raw_diff_bits")

    def test_tile_wide_claim_fails_when_geometry_contains_unknown_bits(self) -> None:
        value = build_certificate()
        value["claim_scope"] = "tile"
        accounting = value["pair_accounting"][0]
        unknown = accounting["buckets"]["in_scope"].pop()
        accounting["counts"]["in_scope"] -= 1
        accounting["buckets"]["ownership_unknown"].append(unknown)
        accounting["counts"]["ownership_unknown"] += 1
        value["status"] = "failed"
        value["failure_reasons"] = [
            {"code": "tile_ownership_unknown", "detail": "tile-wide exactness is not established"}
        ]
        checked = verify_temporary(value)
        self.assertEqual(checked.returncode, 2, checked.stdout)
        self.assertIn("CERTIFICATION FAILED", checked.stdout)

    def test_name_derived_carry4_grouping_is_rejected(self) -> None:
        value = build_certificate()
        predictions = load(PREDICTIONS_PATH)
        result = value["group_results"][0]
        specimen = next(
            item for item in value["specimens"] if item["specimen_id"] == result["prediction_specimen_id"]
        )
        old_group = result["group"]
        carry_features = {
            f"CLBLL_L.SLICEL_X0.CARRY4.{member}"
            for member in ("ACY0", "BCY0", "CCY0", "DCY0")
        }
        rule_path = REPO_ROOT / "data" / result["rule_file"]
        tokens_by_feature = {
            fields[0]: fields[1:]
            for fields in (line.split() for line in rule_path.read_text(encoding="utf-8").splitlines())
            if fields and fields[0] in carry_features
        }
        self.assertEqual(set(tokens_by_feature), carry_features)
        tilegrid = load(REPO_ROOT / "data/prjxray/zynq7/xc7z010/tilegrid.json")
        block = tilegrid[specimen["tile"]]["bits"]["CLB_IO_CLK"]
        coordinates = sorted(
            {
                tuple(map(int, token.lstrip("!").split("_")))
                for tokens in tokens_by_feature.values()
                for token in tokens
            }
        )
        scope = []
        expected = []
        for frame, bit_offset in coordinates:
            address = {
                "far": f"0x{int(block['baseaddr'], 16) + frame:08X}",
                "word": block["offset"] + bit_offset // 32,
                "bit": bit_offset % 32,
            }
            segbit = f"{frame:02d}_{bit_offset:02d}"
            scope.append({"segbit": segbit, "address": address})
            expected.append({"segbit": segbit, "address": address, "expected_value": 1})
        new_group = "CLBLL_L.SLICEL_X0.CARRY4[ACY0|BCY0|CCY0|DCY0]"
        result["group"] = new_group
        result["scope"] = scope
        scope_assertion = next(item for item in result["assertions"] if item["kind"] == "scope_assignment")
        scope_assertion["expected_assignment"] = expected
        result["observed_assignment"] = [
            {**item, "observed_value": item["expected_value"]} for item in expected
        ]
        result["decoded_members"] = ["ACY0", "BCY0", "CCY0", "DCY0"]
        for outcome in result["assertion_outcomes"]:
            if "decoded_members" in outcome:
                outcome["decoded_members"] = copy.deepcopy(result["decoded_members"])

        prediction = next(
            item
            for item in predictions["predictions"]
            if (item["specimen_id"], item["group"])
            == (result["prediction_specimen_id"], old_group)
        )
        prediction["group"] = new_group
        prediction["scope"] = copy.deepcopy(result["scope"])
        prediction["assertions"] = copy.deepcopy(result["assertions"])
        mine_groups = value["bit_class"]["split"]["mine_groups"]
        value["bit_class"]["split"]["mine_groups"] = sorted(
            new_group if group == old_group else group for group in mine_groups
        )

        checked = verify_with_predictions(value, predictions)
        self.assert_fails(checked, "declared scope is not a complete frozen bit-set group")
        self.assertNotIn("differs from preregistered prediction", checked.stdout)


if __name__ == "__main__":
    unittest.main()

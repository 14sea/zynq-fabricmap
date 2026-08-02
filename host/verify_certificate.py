#!/usr/bin/env python3
"""Validate a fabric bit-class certificate and recompute its decision."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover - exercised only on an incomplete host
    Draft202012Validator = None  # type: ignore[assignment]
    FormatChecker = None  # type: ignore[assignment]


SUPPORTED_CERTIFICATE_MAJOR = 1


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def address_key(value: dict[str, Any]) -> tuple[str, int, int]:
    return value["far"], value["word"], value["bit"]


def safe_child(parent: Path, relative: str) -> Path:
    path = (parent / relative).resolve()
    resolved_parent = parent.resolve()
    if resolved_parent not in path.parents:
        raise ValueError(f"path escapes data directory: {relative!r}")
    return path


def schema_errors(certificate: dict[str, Any], schema_path: Path) -> list[str]:
    if Draft202012Validator is None:
        return ["Python package 'jsonschema' is required for certificate validation"]
    try:
        version = certificate.get("schema_version")
        if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
            return [f"invalid certificate schema_version {version!r}"]
        if int(version.split(".", 1)[0]) != SUPPORTED_CERTIFICATE_MAJOR:
            return [f"unsupported certificate schema major in {version!r}"]
        schema = load_json(schema_path)
        Draft202012Validator.check_schema(schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    findings: list[str] = []
    for error in sorted(validator.iter_errors(certificate), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        findings.append(f"schema {location}: {error.message}")
    return findings


def semantic_errors(certificate: dict[str, Any], repo_root: Path) -> list[str]:
    errors: list[str] = []
    data_dir = repo_root / "data"
    manifest = load_json(data_dir / "MANIFEST.json")
    spec = load_json(data_dir / "subset_spec.json")
    tilegrid = load_json(data_dir / "prjxray/zynq7/xc7z010/tilegrid.json")

    target = certificate["target"]
    for field in ("family", "device", "part"):
        if target[field] != manifest["target"][field]:
            errors.append(f"target.{field} differs from current manifest")

    frozen = certificate["frozen_inputs"]
    if frozen["manifest_schema_version"] != manifest["schema_version"]:
        errors.append("frozen_inputs.manifest_schema_version is stale")
    if frozen["freeze_stamp"] != manifest["freeze_stamp"]:
        errors.append("frozen_inputs.freeze_stamp is stale")
    pinned_spec = frozen["spec"]
    if pinned_spec["path"] != manifest["spec"]["path"]:
        errors.append("frozen_inputs.spec.path differs from manifest")
    if pinned_spec["sha256"] != manifest["spec"]["sha256"]:
        errors.append("frozen_inputs.spec.sha256 differs from manifest")
    spec_path = repo_root / manifest["spec"]["path"]
    if not spec_path.is_file() or hash_file(spec_path) != pinned_spec["sha256"]:
        errors.append("frozen_inputs.spec does not match current file bytes")

    manifest_files = {entry["path"]: entry for entry in manifest["files"]}
    pinned_paths: set[str] = set()
    for index, pinned in enumerate(frozen["files"]):
        path_text = pinned["path"]
        if path_text in pinned_paths:
            errors.append(f"frozen_inputs.files[{index}] duplicates {path_text}")
            continue
        pinned_paths.add(path_text)
        current = manifest_files.get(path_text)
        if current is None:
            errors.append(f"frozen input is absent from current manifest: {path_text}")
            continue
        if pinned["sha256"] != current["sha256"]:
            errors.append(f"frozen input hash is stale: {path_text}")
        try:
            actual_path = safe_child(data_dir, path_text)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not actual_path.is_file() or hash_file(actual_path) != pinned["sha256"]:
            errors.append(f"frozen input does not match current file bytes: {path_text}")

    class_record = certificate["bit_class"]
    current_class = next(
        (entry for entry in manifest["bit_classes"] if entry["id"] == class_record["id"]),
        None,
    )
    if current_class is None:
        errors.append(f"bit class {class_record['id']!r} is absent from current manifest")
        current_entries = class_record["manifest_entries"]
    else:
        current_entries = current_class["entries"]
        if class_record["tier"] != current_class["tier"]:
            errors.append("bit_class.tier differs from current manifest")
        if class_record["manifest_entries"] != current_entries:
            errors.append("bit_class.manifest_entries differs from current manifest")
    spec_class = next(
        (entry for entry in spec["bit_classes"] if entry["id"] == class_record["id"]),
        None,
    )

    split = class_record["split"]
    mine = split["mine_features"]
    holdout = split["holdout_features"]
    mine_set = set(mine)
    holdout_set = set(holdout)
    if mine_set & holdout_set:
        errors.append(f"mine and holdout overlap: {sorted(mine_set & holdout_set)[0]}")
    expected_features = mine_set | holdout_set

    specimens = certificate["specimens"]
    specimen_by_id: dict[str, dict[str, Any]] = {}
    for specimen in specimens:
        specimen_id = specimen["specimen_id"]
        if specimen_id in specimen_by_id:
            errors.append(f"duplicate specimen_id {specimen_id!r}")
        specimen_by_id[specimen_id] = specimen
        if specimen["part"] != target["part"]:
            errors.append(f"specimen {specimen_id}: part differs from certificate target")
        tile = tilegrid.get(specimen["tile"])
        if tile is None:
            errors.append(f"specimen {specimen_id}: unknown tile {specimen['tile']!r}")
            continue
        if specimen["tile_type"] != tile["type"]:
            errors.append(f"specimen {specimen_id}: tile_type differs from tilegrid")
        block = tile.get("bits", {}).get("CLB_IO_CLK")
        if block is None:
            errors.append(f"specimen {specimen_id}: tile lacks CLB_IO_CLK block")
        elif specimen["tile_frame_base"] != block["baseaddr"]:
            errors.append(f"specimen {specimen_id}: tile_frame_base differs from tilegrid")

    results = certificate["feature_results"]
    result_by_feature: dict[str, dict[str, Any]] = {}
    used_specimens: set[str] = set()
    computed_tp = 0
    computed_fn = 0
    computed_fp = 0
    for result in results:
        feature = result["feature"]
        if feature in result_by_feature:
            errors.append(f"duplicate feature result {feature!r}")
        result_by_feature[feature] = result
        expected_split = "mine" if feature in mine_set else "holdout" if feature in holdout_set else None
        if expected_split is None:
            errors.append(f"feature result is absent from split membership: {feature}")
        elif result["split"] != expected_split:
            errors.append(f"feature {feature}: result split disagrees with membership")

        pair: list[dict[str, Any]] = []
        for field in ("baseline_specimen_id", "feature_specimen_id"):
            specimen_id = result[field]
            used_specimens.add(specimen_id)
            specimen = specimen_by_id.get(specimen_id)
            if specimen is None:
                errors.append(f"feature {feature}: unknown {field} {specimen_id!r}")
            else:
                pair.append(specimen)
                if specimen["split"] != result["split"]:
                    errors.append(f"feature {feature}: specimen {specimen_id} has wrong split")
        if len(pair) == 2 and (pair[0]["tile"] != pair[1]["tile"] or pair[0]["tile_type"] != pair[1]["tile_type"]):
            errors.append(f"feature {feature}: specimen pair uses different tiles")

        predicted: dict[tuple[str, int, int], int] = {}
        feature_specimen = specimen_by_id.get(result["feature_specimen_id"])
        block = None
        if feature_specimen is not None:
            block = tilegrid.get(feature_specimen["tile"], {}).get("bits", {}).get("CLB_IO_CLK")
        for item in result["predicted_assignments"]:
            key = address_key(item["address"])
            if key in predicted:
                errors.append(f"feature {feature}: duplicate predicted address {key}")
            expected_from_polarity = 0 if item["segbit"]["negated"] else 1
            if item["expected_value"] != expected_from_polarity:
                errors.append(f"feature {feature}: expected_value disagrees with segbit polarity at {key}")
            if block is not None:
                frame_offset = item["segbit"]["frame_offset"]
                bit_offset = item["segbit"]["bit_offset"]
                computed_key = (
                    f"0x{int(block['baseaddr'], 16) + frame_offset:08X}",
                    block["offset"] + bit_offset // 32,
                    bit_offset % 32,
                )
                if not 0 <= frame_offset < block["frames"] or not 0 <= bit_offset < block["words"] * 32:
                    errors.append(f"feature {feature}: segbit coordinate is outside tile block")
                elif key != computed_key:
                    errors.append(f"feature {feature}: absolute address disagrees with normative arithmetic at {key}")
            predicted[key] = item["expected_value"]

        rule_file = result["rule_file"]
        rule_record = manifest_files.get(rule_file)
        if rule_file not in pinned_paths:
            errors.append(f"feature {feature}: rule_file is not pinned in frozen_inputs.files")
        if rule_record is None:
            errors.append(f"feature {feature}: rule_file is absent from current manifest")
        else:
            if spec_class is not None and rule_record.get("group") not in spec_class["from_groups"]:
                errors.append(f"feature {feature}: rule_file group is outside the certificate class")
            try:
                rule_path = safe_child(data_dir, rule_file)
                matching_payloads = []
                for line in rule_path.read_text(encoding="utf-8").splitlines():
                    fields = line.split()
                    if fields and fields[0] == feature:
                        matching_payloads.append(fields[1:])
                if len(matching_payloads) != 1:
                    errors.append(
                        f"feature {feature}: expected one frozen rule, found {len(matching_payloads)}"
                    )
                else:
                    payload = matching_payloads[0]
                    if rule_record.get("role") == "segbits":
                        frozen_coordinates = []
                        for token in payload:
                            match = re.fullmatch(r"(!?)([0-9]+)_([0-9]+)", token)
                            if match is None:
                                errors.append(f"feature {feature}: invalid frozen segbit token {token!r}")
                                continue
                            frozen_coordinates.append(
                                (int(match.group(2)), int(match.group(3)), bool(match.group(1)))
                            )
                        recorded_coordinates = [
                            (
                                item["segbit"]["frame_offset"],
                                item["segbit"]["bit_offset"],
                                item["segbit"]["negated"],
                            )
                            for item in result["predicted_assignments"]
                        ]
                        if recorded_coordinates != frozen_coordinates:
                            errors.append(f"feature {feature}: prediction differs from complete frozen segbits rule")
                    elif rule_record.get("role") == "ppips":
                        if result["predicted_assignments"]:
                            errors.append(f"feature {feature}: ppip rule must have no predicted bits")
                    else:
                        errors.append(f"feature {feature}: rule_file role is not segbits or ppips")
            except (OSError, ValueError) as exc:
                errors.append(f"feature {feature}: cannot read rule_file: {exc}")

        observed: dict[tuple[str, int, int], int] = {}
        for item in result["observed_assignments"]:
            key = address_key(item["address"])
            if key in observed:
                errors.append(f"feature {feature}: duplicate observed assignment {key}")
            observed[key] = item["observed_value"]

        diff: dict[tuple[str, int, int], tuple[int, int]] = {}
        for item in result["observed_diff"]:
            key = address_key(item["address"])
            transition = item["before_value"], item["after_value"]
            if key in diff:
                errors.append(f"feature {feature}: duplicate observed diff address {key}")
            if transition[0] == transition[1]:
                errors.append(f"feature {feature}: diff address {key} did not change")
            if key in observed and observed[key] != transition[1]:
                errors.append(f"feature {feature}: diff after_value disagrees with observed assignment at {key}")
            diff[key] = transition

        unattributed: dict[tuple[str, int, int], tuple[int, int, bool]] = {}
        for item in result["unattributed_diff"]:
            key = address_key(item["address"])
            if key in unattributed:
                errors.append(f"feature {feature}: duplicate unattributed diff address {key}")
            unattributed[key] = (
                item["before_value"],
                item["after_value"],
                item["listed_in_frozen_mask"],
            )
        expected_unattributed = {key: transition for key, transition in diff.items() if key not in predicted}
        recorded_unattributed = {key: value[:2] for key, value in unattributed.items()}
        if recorded_unattributed != expected_unattributed:
            errors.append(f"feature {feature}: unattributed_diff is not the exact unpredicted subset of observed_diff")

        if feature_specimen is not None:
            tile_type = feature_specimen["tile_type"].lower()
            mask_path = data_dir / f"prjxray/zynq7/mask_{tile_type}.db"
            mask_addresses: set[tuple[str, int, int]] = set()
            if block is not None and mask_path.is_file():
                for line in mask_path.read_text(encoding="utf-8").splitlines():
                    match = re.fullmatch(r"bit ([0-9]+)_([0-9]+)", line)
                    if match:
                        frame_offset, bit_offset = map(int, match.groups())
                        mask_addresses.add(
                            (
                                f"0x{int(block['baseaddr'], 16) + frame_offset:08X}",
                                block["offset"] + bit_offset // 32,
                                bit_offset % 32,
                            )
                        )
            for key, (_, _, listed) in unattributed.items():
                if listed != (key in mask_addresses):
                    errors.append(f"feature {feature}: frozen-mask flag is wrong at {key}")

        exact_match = observed == predicted and not expected_unattributed
        computed_verdict = "matched" if exact_match else "mismatched"
        if result["verdict"] != computed_verdict:
            errors.append(
                f"feature {feature}: verdict={result['verdict']} but evidence computes {computed_verdict}"
            )
        if result["split"] == "holdout":
            if computed_verdict == "matched":
                computed_tp += 1
            else:
                computed_fn += 1
            computed_fp += len(expected_unattributed)

    actual_features = set(result_by_feature)
    if actual_features != expected_features:
        missing = sorted(expected_features - actual_features)
        extra = sorted(actual_features - expected_features)
        errors.append(f"feature_results membership mismatch (missing={missing[:1]} extra={extra[:1]})")
    if used_specimens != set(specimen_by_id):
        errors.append("specimens must be referenced by at least one feature result")

    coverage = class_record["coverage"]
    if coverage["attested_count"] != len(expected_features):
        errors.append("coverage.attested_count differs from explicit split membership")
    if coverage["class_entry_count"] != current_entries:
        errors.append("coverage.class_entry_count differs from current manifest")
    accounting = class_record["accounting"]
    computed_accounting = {
        "tp_count": computed_tp,
        "fp_count": computed_fp,
        "fn_count": computed_fn,
    }
    recorded_accounting = {field: accounting[field] for field in computed_accounting}
    if recorded_accounting != computed_accounting:
        errors.append(f"accounting mismatch (recorded={recorded_accounting} computed={computed_accounting})")

    criterion_passed = computed_tp == len(holdout) and computed_fn == 0 and computed_fp == 0
    expected_status = "passed" if criterion_passed else "failed"
    if certificate["status"] != expected_status:
        errors.append(
            f"status={certificate['status']} but holdout evidence requires {expected_status}"
        )
    return errors


def verify(certificate_path: Path, repo_root: Path, schema_path: Path) -> list[str]:
    try:
        certificate = load_json(certificate_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]
    errors = schema_errors(certificate, schema_path)
    if errors:
        return errors
    try:
        errors.extend(semantic_errors(certificate, repo_root))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"semantic validation could not complete: {exc}")
    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificate", type=Path)
    parser.add_argument("--schema", type=Path, default=repo_root / "schemas/certificate.schema.json")
    parser.add_argument(
        "--allow-failed",
        action="store_true",
        help="return success for a well-formed failed record (schema conformance use only)",
    )
    args = parser.parse_args()
    errors = verify(args.certificate.resolve(), repo_root, args.schema.resolve())
    if errors:
        print(f"CERTIFICATE VERIFY: FAIL — {len(errors)} finding(s)", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    certificate = load_json(args.certificate)
    accounting = certificate["bit_class"]["accounting"]
    if certificate["status"] == "failed" and not args.allow_failed:
        print(
            "CERTIFICATE VERIFY: CERTIFICATION FAILED — "
            f"tp={accounting['tp_count']} fp={accounting['fp_count']} fn={accounting['fn_count']}",
            file=sys.stderr,
        )
        return 2
    print(
        f"CERTIFICATE VERIFY: OK — status={certificate['status']} "
        f"tp={accounting['tp_count']} fp={accounting['fp_count']} fn={accounting['fn_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

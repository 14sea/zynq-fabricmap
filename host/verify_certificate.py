#!/usr/bin/env python3
"""Validate a fabric bit-class certificate and recompute its decision."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from pathlib import PurePosixPath
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
    if Path(relative).is_absolute():
        raise ValueError(f"artifact path must be repository-relative: {relative!r}")
    path = (parent / relative).resolve()
    resolved_parent = parent.resolve()
    if resolved_parent not in path.parents:
        raise ValueError(f"path escapes allowed root: {relative!r}")
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


def validate_external_schema(value: dict[str, Any], schema_path: Path, label: str) -> list[str]:
    if Draft202012Validator is None:
        return ["Python package 'jsonschema' is required for attestation validation"]
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    findings: list[str] = []
    for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        findings.append(f"{label} schema {location}: {error.message}")
    return findings


PredictionKey = tuple[str, str]
GROUP_BASIS_LUT = "FF.D driven by the LUT6 output"
GROUP_BASIS_PIN = "FF.D driven by a package pin through the slice bypass"
GROUP_BUCKETS = ("in_scope", "frame_ecc", "db_attributed", "ownership_unknown", "unattributed")


def frozen_codeword_collisions(
    member_encodings: dict[str, dict[tuple[int, int], int]],
) -> list[list[str]]:
    """Return distinct frozen feature names that carry an identical full codeword."""

    by_codeword: dict[tuple[tuple[int, int, int], ...], list[str]] = {}
    for member, encoding in member_encodings.items():
        codeword = tuple(
            sorted((frame, bit, value) for (frame, bit), value in encoding.items())
        )
        by_codeword.setdefault(codeword, []).append(member)
    return [sorted(members) for members in by_codeword.values() if len(members) > 1]


def resolve_json_pointer(value: Any, pointer: str) -> Any:
    """Resolve an RFC 6901 JSON pointer without accepting array traversal."""

    current = value
    for raw_part in pointer.removeprefix("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"JSON pointer {pointer!r} does not exist")
        current = current[part]
    return current


FF_ALL_BELS = ("AFF", "A5FF", "BFF", "B5FF", "CFF", "C5FF", "DFF", "D5FF")
FF_MAIN_BELS = ("AFF", "BFF", "CFF", "DFF")
FF_LUT_BELS = ("A6LUT", "B6LUT", "C6LUT", "D6LUT", "A5LUT", "B5LUT", "C5LUT", "D5LUT")
FF_SUPPORT = {
    "anchor_lut1": ("anchor", "lut", "A6LUT"),
    "anchor_lut2": ("anchor", "lut", "B6LUT"),
    "q_reduce1": ("anchor", "lut", "C6LUT"),
    "q_reduce2": ("anchor", "lut", "D6LUT"),
    "anchor_ff": ("anchor", "storage", "AFF"),
    "anchor_ff2": ("keeper", "storage", "AFF"),
}


def bel_leaf(value: str) -> str:
    """Return the BEL leaf from either `AFF`, `SLICEL.AFF`, or a site path."""

    return value.rsplit("/", 1)[-1].rsplit(".", 1)[-1]


def logic_bit(value: str) -> str | None:
    """Normalize the Vivado scalar spellings used in routed-property readback."""

    match = re.fullmatch(r"(?:[0-9]+(?:'b|'h))?([01])", value.strip().lower())
    return match.group(1) if match else None


def tied_net(value: str) -> bool:
    text = value.strip().upper()
    return text in {"<CONST0>", "<CONST1>", "GND", "VCC"}


def ff_formal_attestation_errors(
    attestation: dict[str, Any],
    specimen: dict[str, Any],
    committed_specimen: dict[str, Any],
    commitment_reference: dict[str, Any],
    repo_root: Path,
) -> list[str]:
    """Rebuild the 2.0 FF summaries from routed multi-cell facts.

    The `/resolved/*` values are convenient semantic-pointer targets, not producer-owned
    truth.  This routine derives each one from the cell list and rejects disagreement.
    """

    errors: list[str] = []
    specimen_id = specimen["specimen_id"]
    prefix = f"specimen {specimen_id} attestation"
    if attestation.get("schema_version") != "2.0.0" or attestation.get("profile") != "ff_formal":
        return [f"{prefix}: feature 1.6 requires specimen_attestation 2.0.0 ff_formal"]
    if attestation.get("specimen_id") != specimen_id:
        errors.append(f"{prefix}: specimen_id differs from certificate")
    if attestation.get("prediction_commitment") != commitment_reference:
        errors.append(f"{prefix}: prediction commitment reference differs from certificate")

    build = attestation["source_build"]
    recipe = build["recipe"]
    sites = build["sites"]
    variant = committed_specimen.get("variant")
    if build["instance"] != specimen["loc_site"] or sites["target"] != specimen["loc_site"]:
        errors.append(f"{prefix}: source instance/target site differs from specimen loc_site")
    if build["variant"] != variant:
        errors.append(f"{prefix}: source variant differs from committed specimen")
    if recipe["commitment"] != commitment_reference["sha256"]:
        errors.append(f"{prefix}: source recipe pins a different commitment")
    if recipe["part"] != specimen["part"] or recipe["vivado_version"] != specimen["vivado_version"]:
        errors.append(f"{prefix}: source recipe part/tool differs from specimen")
    if recipe["build_seed"] != specimen["build_seed"]:
        errors.append(f"{prefix}: source recipe build_seed differs from specimen")
    for relative, expected_hash in recipe["sources"].items():
        try:
            source_path = safe_child(repo_root, relative)
            if not source_path.is_file() or hash_file(source_path) != expected_hash:
                errors.append(f"{prefix}: source recipe file differs from repository: {relative}")
        except (OSError, ValueError) as exc:
            errors.append(f"{prefix}: cannot validate source recipe file {relative!r}: {exc}")
    if build["artifacts"]["spec.bit"] != specimen["bitstream_sha256"]:
        errors.append(f"{prefix}: source stamp bitstream hash differs from specimen")
    if attestation["outputs"]["spec.bit"] != specimen["bitstream_sha256"]:
        errors.append(f"{prefix}: output bitstream hash differs from specimen")

    target = attestation["resolved"]["target"]
    if target["requested_site"] != specimen["loc_site"] or target["resolved_site"] != specimen["loc_site"]:
        errors.append(f"{prefix}: requested/resolved target site differs from specimen")
    if target["tile"] != specimen["tile"] or target["tile_type"] != specimen["tile_type"]:
        errors.append(f"{prefix}: resolved target tile differs from specimen")

    cells = attestation["resolved"]["cells"]
    seen_names: set[str] = set()
    target_storage: dict[str, dict[str, Any]] = {}
    target_luts: dict[str, dict[str, Any]] = {}
    support: dict[str, dict[str, Any]] = {}
    for cell in cells:
        name = cell["logical_name"]
        leaf = bel_leaf(cell["logical_bel"])
        if name in seen_names:
            errors.append(f"{prefix}: duplicate logical cell name {name!r}")
        seen_names.add(name)
        requested = cell["requested"]
        resolved = cell["resolved"]
        # `requested` is pinned producer intent, not another Vivado readback. These
        # comparisons reject an internally contradictory record; only `resolved` plus
        # the independently derived topology carries routed-design evidence.
        if requested["ref_name"] != resolved["ref_name"]:
            errors.append(f"{prefix}: cell {name!r} requested/resolved REF_NAME is inconsistent")
        if requested["loc"] != resolved["loc"] or requested["bel"] != bel_leaf(resolved["bel"]):
            errors.append(f"{prefix}: cell {name!r} requested/resolved placement is inconsistent")
        if leaf != bel_leaf(resolved["bel"]):
            errors.append(f"{prefix}: cell {name!r} logical_bel differs from resolved BEL")
        if cell["kind"] == "lut" and (not cell["lock_pins"] or not cell["pin_mapping"]):
            errors.append(f"{prefix}: LUT cell {name!r} lacks LOCK_PINS/pin mapping evidence")
        if cell["role"] == "target" and cell["kind"] == "storage":
            if leaf in target_storage:
                errors.append(f"{prefix}: duplicate target storage BEL {leaf}")
            target_storage[leaf] = cell
        elif cell["role"] == "target" and cell["kind"] == "lut":
            if leaf in target_luts:
                errors.append(f"{prefix}: duplicate target LUT BEL {leaf}")
            target_luts[leaf] = cell
        else:
            support[name] = cell

    expected_storage = set(FF_MAIN_BELS if variant in {"latch", "latch_base"} else FF_ALL_BELS)
    if set(target_storage) != expected_storage:
        errors.append(
            f"{prefix}: target storage cells differ from variant topology "
            f"(missing={sorted(expected_storage - set(target_storage))} "
            f"extra={sorted(set(target_storage) - expected_storage)})"
        )
    if set(target_luts) != set(FF_LUT_BELS):
        errors.append(
            f"{prefix}: target LUT cells differ from formal topology "
            f"(missing={sorted(set(FF_LUT_BELS) - set(target_luts))} "
            f"extra={sorted(set(target_luts) - set(FF_LUT_BELS))})"
        )
    if set(support) != set(FF_SUPPORT):
        errors.append(
            f"{prefix}: anchor/keeper cells differ from formal topology "
            f"(missing={sorted(set(FF_SUPPORT) - set(support))} "
            f"extra={sorted(set(support) - set(FF_SUPPORT))})"
        )
    for name, (role, kind, bel) in FF_SUPPORT.items():
        cell = support.get(name)
        if cell is None:
            continue
        expected_site = sites[role]
        if cell["role"] != role or cell["kind"] != kind or bel_leaf(cell["logical_bel"]) != bel:
            errors.append(f"{prefix}: support cell {name!r} has the wrong role/kind/BEL")
        if cell["resolved"]["loc"] != expected_site:
            errors.append(f"{prefix}: support cell {name!r} resolved at the wrong site")
    for cell in [*target_storage.values(), *target_luts.values()]:
        if cell["resolved"]["loc"] != sites["target"]:
            errors.append(f"{prefix}: target cell {cell['logical_name']!r} resolved outside target site")

    # Rebuild the semantic-pointer summaries. Unknown/mixed raw facts are an invalid
    # attestation, never a producer-selectable summary value.
    ff_init: dict[str, str] = {}
    ff_srval: dict[str, str] = {}
    ce_tied: set[bool] = set()
    sr_tied: set[bool] = set()
    sr_kinds: set[str] = set()
    storage_kinds: set[str] = set()
    clock_modes: set[str] = set()
    for bel, cell in target_storage.items():
        ref = cell["resolved"]["ref_name"].upper()
        init = logic_bit(cell["properties"].get("INIT", ""))
        if init is None:
            errors.append(f"{prefix}: storage BEL {bel} has no scalar INIT readback")
        else:
            ff_init[bel] = init
        if ref in {"FDSE", "FDPE"}:
            ff_srval[bel] = "1"
        elif ref in {"FDRE", "FDCE", "LDCE"}:
            ff_srval[bel] = "0"
        else:
            errors.append(f"{prefix}: storage BEL {bel} has unsupported REF_NAME {ref!r}")

        ce_pin = "GE" if ref == "LDCE" else "CE"
        sr_pin = "CLR" if ref in {"FDCE", "LDCE"} else ("S" if ref in {"FDSE", "FDPE"} else "R")
        if ce_pin not in cell["pins"] or sr_pin not in cell["pins"]:
            errors.append(f"{prefix}: storage BEL {bel} lacks {ce_pin}/{sr_pin} pin evidence")
        else:
            ce_tied.add(tied_net(cell["pins"][ce_pin]["net"]))
            sr_tied.add(tied_net(cell["pins"][sr_pin]["net"]))
        sr_kinds.add("ASYNC" if ref in {"FDCE", "LDCE"} else "SYNC")
        storage_kinds.add("LATCH" if ref == "LDCE" else "FF")
        if ref == "LDCE":
            clock_modes.add("LATCH")
        else:
            inverted = logic_bit(cell["properties"].get("IS_C_INVERTED", ""))
            if inverted is None:
                errors.append(f"{prefix}: storage BEL {bel} lacks scalar IS_C_INVERTED")
            else:
                clock_modes.add("CLKINV" if inverted == "1" else "NOCLKINV")

    def uniform(values: set[Any], false_value: str, true_value: str, field: str) -> str | None:
        if len(values) != 1:
            errors.append(f"{prefix}: raw cell facts do not define one {field}")
            return None
        return true_value if next(iter(values)) else false_value

    rebuilt: dict[str, Any] = {
        "ff_init": ff_init,
        "ff_srval": ff_srval,
        "ce_mode": uniform(ce_tied, "DRIVEN", "TIED", "ce_mode"),
        "sr_mode": uniform(sr_tied, "DRIVEN", "TIED", "sr_mode"),
        "sr_kind": next(iter(sr_kinds)) if len(sr_kinds) == 1 else None,
        "storage_kind": next(iter(storage_kinds)) if len(storage_kinds) == 1 else None,
        "clock_mode": next(iter(clock_modes)) if len(clock_modes) == 1 else None,
    }
    if len(sr_kinds) != 1:
        errors.append(f"{prefix}: raw cell facts do not define one sr_kind")
    if len(storage_kinds) != 1:
        errors.append(f"{prefix}: raw cell facts do not define one storage_kind")
    if len(clock_modes) != 1:
        errors.append(f"{prefix}: raw cell facts do not define one clock_mode")
    for field, expected in rebuilt.items():
        if attestation["resolved"].get(field) != expected:
            errors.append(f"{prefix}: resolved.{field} differs from independent cell rebuild")

    checkpoint = attestation["checkpoint"]
    if checkpoint["kind"] != build["node_type"]:
        errors.append(f"{prefix}: checkpoint kind differs from source node_type")
    artifact = checkpoint["artifact"]
    if build["artifacts"].get(artifact["file"]) != artifact["sha256"]:
        errors.append(f"{prefix}: checkpoint artifact differs from source stamp")
    if build["node_type"] == "derived":
        source = checkpoint.get("source", {})
        derived_from = build.get("derived_from", {})
        if source.get("specimen_id") != derived_from.get("specimen_id") or source.get(
            "sha256"
        ) != derived_from.get("base_dcp_sha256"):
            errors.append(f"{prefix}: derived checkpoint source differs from source stamp")
    return errors


def load_feature_staging(
    certificate: dict[str, Any],
    repo_root: Path,
    committed_specimens: dict[str, dict[str, Any]],
) -> tuple[list[str], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Validate and load the exact staged set selected by certificate 1.6.

    This proves what a host verifier can prove: exact set, byte hashes, embedded completed
    stamps, and checkpoint linkage. It does not claim to observe a Python function call.
    """

    errors: list[str] = []
    entries: dict[str, dict[str, Any]] = {}
    attestations: dict[str, dict[str, Any]] = {}
    reference = certificate["staging_manifest"]
    try:
        path = safe_child(repo_root, reference["path"])
        if not path.is_file():
            raise ValueError(f"staging manifest does not exist: {reference['path']}")
        if hash_file(path) != reference["sha256"]:
            raise ValueError("staging manifest hash mismatch")
        manifest = load_json(path)
        findings = validate_external_schema(
            manifest,
            repo_root / "schemas/specimen_staging.schema.json",
            "staging manifest",
        )
        errors.extend(findings)
        if findings:
            return errors, entries, attestations
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return [f"cannot validate staging manifest: {exc}"], entries, attestations

    if manifest["schema_version"] != reference["schema_version"]:
        errors.append("pinned staging schema_version differs from file")
    if manifest["run_id"] != certificate["prediction_commitment"]["run_id"]:
        errors.append("staging run_id differs from prediction commitment")
    if manifest["prediction_commitment"] != certificate["prediction_commitment"]:
        errors.append("staging prediction commitment differs from certificate")

    used_paths: set[str] = set()
    staging_roots: set[Path] = set()
    for index, entry in enumerate(manifest["specimens"]):
        specimen_id = entry["specimen_id"]
        if specimen_id in entries:
            errors.append(f"staging specimens[{index}] duplicates specimen_id {specimen_id!r}")
            continue
        entries[specimen_id] = entry
        bit_ref = entry["bitstream"]
        att_ref = entry["attestation"]
        for label, pinned, expected_name in (
            ("bitstream", bit_ref, "spec.bit"),
            ("attestation", att_ref, "attestation.json"),
        ):
            relative = pinned["path"]
            if relative in used_paths:
                errors.append(f"staging specimens[{index}] duplicates artifact path {relative!r}")
            used_paths.add(relative)
            posix = PurePosixPath(relative)
            if posix.name != expected_name or posix.parent.name != specimen_id:
                errors.append(
                    f"staging specimen {specimen_id}: {label} path must be "
                    f"<root>/{specimen_id}/{expected_name}"
                )
            try:
                artifact_path = safe_child(repo_root, relative)
                if not artifact_path.is_file():
                    raise ValueError(f"file does not exist: {relative}")
                if hash_file(artifact_path) != pinned["sha256"]:
                    raise ValueError(f"hash mismatch: {relative}")
                staging_roots.add(artifact_path.parent.parent)
            except (OSError, ValueError) as exc:
                errors.append(f"staging specimen {specimen_id}: {exc}")
        try:
            att_path = safe_child(repo_root, att_ref["path"])
            if att_path.is_file() and hash_file(att_path) == att_ref["sha256"]:
                attestation = load_json(att_path)
                if attestation.get("source_build", {}).get("completed") is not True:
                    errors.append(
                        f"staging specimen {specimen_id}: source build is not completed/verified"
                    )
                findings = validate_external_schema(
                    attestation,
                    repo_root / "schemas/specimen_attestation.schema.json",
                    f"staging specimen {specimen_id} attestation",
                )
                errors.extend(findings)
                if not findings:
                    attestations[specimen_id] = attestation
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"staging specimen {specimen_id}: cannot load attestation: {exc}")

    expected_ids = set(committed_specimens)
    if set(entries) != expected_ids:
        errors.append(
            "staging specimen completeness mismatch "
            f"(missing={len(expected_ids - set(entries))} "
            f"extra={len(set(entries) - expected_ids)})"
        )
    if len(staging_roots) != 1:
        errors.append("staging artifacts do not share one staging root")
    else:
        root = next(iter(staging_roots))
        actual_dirs = {item.name for item in root.iterdir() if item.is_dir()}
        actual_files = {item.name for item in root.iterdir() if item.is_file()}
        if actual_dirs != expected_ids or actual_files:
            errors.append(
                "staging root contents differ from committed specimen set "
                f"(missing={len(expected_ids - actual_dirs)} extra={len(actual_dirs - expected_ids)} "
                f"root_files={len(actual_files)})"
            )
        for specimen_id in actual_dirs & expected_ids:
            names = {item.name for item in (root / specimen_id).iterdir()}
            if names != {"spec.bit", "attestation.json"}:
                errors.append(
                    f"staging specimen {specimen_id}: directory must contain exactly "
                    "spec.bit and attestation.json"
                )
    return errors, entries, attestations


def load_prediction_commitment(
    certificate: dict[str, Any],
    repo_root: Path,
) -> tuple[list[str], dict[PredictionKey, dict[str, Any]], set[PredictionKey]]:
    """Load and independently validate the preregistered prediction artifact."""

    errors: list[str] = []
    committed_by_key: dict[PredictionKey, dict[str, Any]] = {}
    holdout_keys: set[PredictionKey] = set()
    group_model = certificate.get("evidence_model") == "group"
    certificate_version = tuple(
        int(part) for part in certificate.get("schema_version", "0.0.0").split(".")
    )
    feature_1_4 = not group_model and certificate_version >= (1, 4, 0)
    feature_1_5 = not group_model and certificate_version >= (1, 5, 0)
    reference = certificate.get("prediction_commitment")
    if reference is None:
        return ["production lifecycle verification requires prediction_commitment"], committed_by_key, holdout_keys

    try:
        path = safe_child(repo_root, reference["path"])
        if not path.is_file():
            raise ValueError(f"prediction artifact does not exist: {reference['path']}")
        actual_hash = hash_file(path)
        if actual_hash != reference["sha256"]:
            raise ValueError(
                f"prediction commitment hash mismatch (pinned={reference['sha256']} actual={actual_hash})"
            )
        artifact = load_json(path)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return [f"cannot validate prediction commitment: {exc}"], committed_by_key, holdout_keys

    expected_root_fields = {
        "schema",
        "schema_version",
        "bit_class",
        "seed",
        "split_policy",
        "frozen_inputs",
        "specimens",
        "predictions",
        "totals",
    }
    missing_root = sorted(expected_root_fields - set(artifact))
    if missing_root:
        return [f"prediction artifact is missing fields: {missing_root}"], committed_by_key, holdout_keys
    if artifact["schema"] != "gate_predictions":
        errors.append("prediction artifact schema is not 'gate_predictions'")
    if artifact["schema_version"] != reference["schema_version"]:
        errors.append("prediction commitment schema_version differs from artifact")
    if feature_1_5:
        artifact_version = artifact.get("schema_version")
        if (
            not isinstance(artifact_version, str)
            or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", artifact_version) is None
            or tuple(int(part) for part in artifact_version.split(".")) < (1, 5, 0)
        ):
            errors.append(
                "feature certificate 1.5 requires gate_predictions schema_version >= 1.5.0"
            )
    if artifact["seed"] != reference["seed"]:
        errors.append("prediction commitment seed differs from artifact")
    if artifact["bit_class"] != certificate["bit_class"]["id"]:
        errors.append("prediction artifact bit_class differs from certificate")

    frozen = artifact["frozen_inputs"]
    certificate_frozen = certificate["frozen_inputs"]
    if not isinstance(frozen, dict):
        errors.append("prediction artifact frozen_inputs is not an object")
    else:
        if frozen.get("manifest_freeze_stamp") != certificate_frozen["freeze_stamp"]:
            errors.append("prediction artifact manifest_freeze_stamp differs from certificate")
        if frozen.get("spec_sha256") != certificate_frozen["spec"]["sha256"]:
            errors.append("prediction artifact spec_sha256 differs from certificate")
        if group_model or feature_1_4:
            committed_files = frozen.get("files")
            certificate_files = {
                item["path"]: item["sha256"] for item in certificate_frozen["files"]
            }
            if not isinstance(committed_files, dict):
                errors.append("group prediction artifact frozen_inputs.files is not an object")
            else:
                for path_text, digest in committed_files.items():
                    if certificate_files.get(path_text) != digest:
                        errors.append(
                            f"prediction artifact frozen file differs from certificate: {path_text}"
                        )

    artifact_specimens = artifact["specimens"]
    predictions = artifact["predictions"]
    totals = artifact["totals"]
    if not isinstance(artifact_specimens, list) or not isinstance(predictions, list) or not isinstance(totals, dict):
        errors.append("prediction artifact specimens, predictions, or totals has the wrong type")
        return errors, committed_by_key, holdout_keys

    prediction_specimen_ids: set[str] = set()
    certificate_specimens = {
        specimen["specimen_id"]: specimen
        for specimen in certificate.get("specimens", [])
        if isinstance(specimen, dict) and isinstance(specimen.get("specimen_id"), str)
    }
    expected_group_specimen_fields = {
        "specimen_id",
        "site",
        "ff_bel",
        "ffsrc",
        "tile",
        "tile_type",
        "site_prefix",
        "split",
    }
    for index, specimen in enumerate(artifact_specimens):
        if not isinstance(specimen, dict) or not isinstance(specimen.get("specimen_id"), str):
            errors.append(f"prediction artifact specimens[{index}] lacks a string specimen_id")
            continue
        specimen_id = specimen["specimen_id"]
        if specimen_id in prediction_specimen_ids:
            errors.append(f"prediction artifact duplicates specimen_id {specimen_id!r}")
        prediction_specimen_ids.add(specimen_id)
        if group_model:
            if set(specimen) != expected_group_specimen_fields:
                errors.append(
                    f"prediction artifact specimens[{index}] fields differ from the group contract"
                )
                continue
            certificate_specimen = certificate_specimens.get(specimen_id)
            if certificate_specimen is None:
                errors.append(
                    f"prediction artifact specimen {specimen_id!r} is absent from certificate specimens"
                )
                continue
            preregistered_projection = {
                field: specimen[field]
                for field in ("specimen_id", "site", "ff_bel", "ffsrc", "tile", "tile_type", "split")
            }
            certificate_projection = {
                field: certificate_specimen[field]
                for field in preregistered_projection
            }
            if preregistered_projection != certificate_projection:
                errors.append(
                    f"certificate specimen {specimen_id!r} differs from preregistered specimen identity"
                )
        elif feature_1_4:
            certificate_specimen = certificate_specimens.get(specimen_id)
            if certificate_specimen is None:
                errors.append(
                    f"prediction artifact specimen {specimen_id!r} is absent from certificate specimens"
                )
                continue
            projection_fields = {
                "split": "split",
                "site": "loc_site",
                "tile": "tile",
                "tile_type": "tile_type",
            }
            for artifact_field, certificate_field in projection_fields.items():
                if (
                    artifact_field in specimen
                    and specimen[artifact_field] != certificate_specimen.get(certificate_field)
                ):
                    errors.append(
                        f"certificate specimen {specimen_id!r} differs from preregistered "
                        f"{artifact_field}"
                    )
    if group_model and prediction_specimen_ids != set(certificate_specimens):
        errors.append("certificate specimen IDs differ from preregistered specimen IDs")

    if group_model:
        expected_prediction_fields = {
            "specimen_id",
            "group",
            "split",
            "rule_file",
            "scope",
            "assertions",
        }
    else:
        expected_prediction_fields = {
            "specimen_id",
            "feature",
            "split",
            "rule_file",
            "predicted_assignments",
            "expected_transition",
        }
        if feature_1_4:
            expected_prediction_fields.add("semantic_assertion")
        if feature_1_5:
            expected_prediction_fields.add("comparison_specimen_id")
    for index, prediction in enumerate(predictions):
        if not isinstance(prediction, dict):
            errors.append(f"prediction artifact predictions[{index}] is not an object")
            continue
        if set(prediction) != expected_prediction_fields:
            errors.append(
                f"prediction artifact predictions[{index}] fields differ from the evidence-model contract"
            )
            continue
        specimen_id = prediction["specimen_id"]
        subject = prediction["group"] if group_model else prediction["feature"]
        if not isinstance(specimen_id, str) or not specimen_id or not isinstance(subject, str) or not subject:
            errors.append(f"prediction artifact predictions[{index}] has an invalid pair key")
            continue
        key = specimen_id, subject
        if key in committed_by_key:
            errors.append(f"prediction artifact duplicates pair key {key!r}")
            continue
        if specimen_id not in prediction_specimen_ids:
            errors.append(f"prediction artifact pair key {key!r} names an unknown specimen")
        if feature_1_5:
            comparison_id = prediction.get("comparison_specimen_id")
            if not isinstance(comparison_id, str) or not comparison_id:
                errors.append(
                    f"prediction artifact pair key {key!r} has an invalid comparison specimen"
                )
            elif comparison_id == specimen_id:
                errors.append(
                    f"prediction artifact pair key {key!r} compares a specimen with itself"
                )
            elif comparison_id not in prediction_specimen_ids:
                errors.append(
                    f"prediction artifact pair key {key!r} names an unknown comparison specimen"
                )
        if prediction["split"] not in ("mine", "holdout"):
            errors.append(f"prediction artifact pair key {key!r} has an invalid split")
        if group_model:
            scope = prediction["scope"]
            assertions = prediction["assertions"]
            if not isinstance(scope, list) or not scope or not isinstance(assertions, list):
                errors.append(f"prediction artifact pair key {key!r} has malformed group evidence")
        else:
            assignments = prediction["predicted_assignments"]
            if not isinstance(assignments, list) or any(
                not isinstance(item, dict)
                or set(item) != {"token", "segbit", "address", "expected_value"}
                for item in assignments
            ):
                errors.append(f"prediction artifact pair key {key!r} has malformed assignments")
            transition = prediction["expected_transition"]
            if not isinstance(transition, dict) or set(transition) != {"before", "after"}:
                errors.append(f"prediction artifact pair key {key!r} has a malformed expected_transition")
            if feature_1_4:
                semantic = prediction.get("semantic_assertion")
                required_semantic_fields = {
                    "kind",
                    "semantic",
                    "claim",
                    "predicted_member",
                    "attestation_field",
                    "expected_value",
                }
                if (
                    not isinstance(semantic, dict)
                    or set(semantic) != required_semantic_fields
                    or semantic.get("kind") != "member_identity"
                    or semantic.get("semantic") is not True
                    or semantic.get("predicted_member") != subject
                ):
                    errors.append(
                        f"prediction artifact pair key {key!r} has malformed semantic evidence"
                    )
        committed_by_key[key] = prediction
        if prediction["split"] == "holdout":
            holdout_keys.add(key)

    recomputed_totals = {
        "specimens": len(artifact_specimens),
        "predictions": len(predictions),
        "holdout_predictions": len(holdout_keys),
    }
    if group_model:
        assertion_count = sum(
            len(prediction.get("assertions", []))
            for prediction in predictions
            if isinstance(prediction, dict)
        )
        semantic_count = sum(
            1
            for prediction in predictions
            if isinstance(prediction, dict)
            for assertion in prediction.get("assertions", [])
            if isinstance(assertion, dict) and assertion.get("semantic") is True
        )
        recomputed_totals.update(
            assertions=assertion_count,
            semantic_assertions=semantic_count,
        )
    if totals != recomputed_totals:
        errors.append(
            f"prediction artifact totals mismatch (recorded={totals} computed={recomputed_totals})"
        )
    if reference["totals"] != totals:
        errors.append("prediction commitment totals differ from artifact")
    return errors, committed_by_key, holdout_keys


def parse_segbit_token(token: str) -> tuple[int, int, bool] | None:
    match = re.fullmatch(r"(!?)([0-9]+)_([0-9]+)", token)
    if match is None:
        return None
    return int(match.group(2)), int(match.group(3)), bool(match.group(1))


def group_semantic_errors(
    certificate: dict[str, Any],
    repo_root: Path,
    require_production: bool = False,
) -> list[str]:
    """Validate certificate 1.3/1.4 group evidence without consulting producer code."""

    errors: list[str] = []
    data_dir = repo_root / "data"
    manifest = load_json(data_dir / "MANIFEST.json")
    spec = load_json(data_dir / "subset_spec.json")
    tilegrid = load_json(data_dir / "prjxray/zynq7/xc7z010/tilegrid.json")

    version = tuple(int(part) for part in certificate["schema_version"].split("."))
    certificate_1_4 = version >= (1, 4, 0)
    profile = certificate.get("profile")
    if require_production and profile != "production":
        errors.append("production verification requires profile='production'")
    if profile == "production" and version < (1, 3, 0):
        errors.append("the group production profile requires certificate schema_version >= 1.3.0")

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
    if spec_class is None:
        errors.append(f"bit class {class_record['id']!r} is absent from subset spec")
        feature_pattern = None
    else:
        feature_pattern = re.compile(spec_class["feature_regex"])

    commitment_errors, committed_by_key, committed_holdout_keys = load_prediction_commitment(
        certificate,
        repo_root,
    )
    errors.extend(commitment_errors)

    specimen_by_id: dict[str, dict[str, Any]] = {}
    specimen_attestations: dict[str, dict[str, Any]] = {}
    for specimen in certificate["specimens"]:
        specimen_id = specimen["specimen_id"]
        if specimen_id in specimen_by_id:
            errors.append(f"duplicate specimen_id {specimen_id!r}")
        specimen_by_id[specimen_id] = specimen
        tile = tilegrid.get(specimen["tile"])
        if tile is None:
            errors.append(f"specimen {specimen_id}: unknown tile {specimen['tile']!r}")
            continue
        if specimen["tile_type"] != tile["type"]:
            errors.append(f"specimen {specimen_id}: tile_type differs from tilegrid")
        if specimen["site"] not in tile.get("sites", {}):
            errors.append(f"specimen {specimen_id}: site is absent from tilegrid tile")

        reference = specimen["attestation"]
        try:
            attestation_path = safe_child(repo_root, reference["path"])
            if not attestation_path.is_file():
                raise ValueError(f"attestation file does not exist: {reference['path']}")
            actual_hash = hash_file(attestation_path)
            if actual_hash != reference["sha256"]:
                raise ValueError(
                    f"attestation hash mismatch (pinned={reference['sha256']} actual={actual_hash})"
                )
            attestation = load_json(attestation_path)
            external_findings = validate_external_schema(
                attestation,
                repo_root / "schemas/specimen_attestation.schema.json",
                f"specimen {specimen_id} attestation",
            )
            errors.extend(external_findings)
            if external_findings:
                continue
            specimen_attestations[specimen_id] = attestation
            resolved = attestation["resolved"]
            if attestation["schema_version"] != reference["schema_version"]:
                errors.append(f"specimen {specimen_id}: pinned attestation schema_version differs from file")
            if resolved["resolved_loc"] != specimen["site"] or reference["resolved_loc"] != specimen["site"]:
                errors.append(f"specimen {specimen_id}: attested resolved_loc differs from site")
            if resolved["resolved_bel"] != reference["resolved_bel"]:
                errors.append(f"specimen {specimen_id}: pinned resolved_bel differs from attestation")
            if resolved["tile"] != specimen["tile"]:
                errors.append(f"specimen {specimen_id}: attested tile differs from specimen tile")
            if resolved.get("ff_loc") != specimen["site"]:
                errors.append(f"specimen {specimen_id}: attested FF LOC differs from specimen site")
            if resolved.get("ff_bel", "").rsplit(".", 1)[-1] != specimen["ff_bel"]:
                errors.append(f"specimen {specimen_id}: attested FF BEL differs from specimen FF BEL")
            if resolved["pin_mapping_is_identity"] != reference["pin_mapping_is_identity"]:
                errors.append(f"specimen {specimen_id}: pinned pin mapping summary differs from attestation")
            if attestation["checkpoint"] != reference["checkpoint"]:
                errors.append(f"specimen {specimen_id}: pinned checkpoint differs from attestation")
            if attestation["inputs"]["part"] != target["part"]:
                errors.append(f"specimen {specimen_id}: attested part differs from certificate target")
            if specimen["bitstream_sha256"] not in attestation["outputs"].values():
                errors.append(f"specimen {specimen_id}: bitstream_sha256 is absent from attestation outputs")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            errors.append(f"specimen {specimen_id}: cannot validate attestation: {exc}")

    rule_group_cache: dict[
        str,
        dict[frozenset[tuple[int, int]], dict[str, list[tuple[int, int, bool]]]],
    ] = {}
    all_rule_coordinates_cache: dict[str, set[tuple[int, int]]] = {}

    def load_rule_groups(rule_file: str) -> dict[
        frozenset[tuple[int, int]], dict[str, list[tuple[int, int, bool]]]
    ]:
        cached = rule_group_cache.get(rule_file)
        if cached is not None:
            return cached
        groups: dict[
            frozenset[tuple[int, int]], dict[str, list[tuple[int, int, bool]]]
        ] = {}
        rule_path = safe_child(data_dir, rule_file)
        for line_number, line in enumerate(rule_path.read_text(encoding="utf-8").splitlines(), 1):
            fields = line.split()
            if not fields or feature_pattern is None or feature_pattern.fullmatch(fields[0]) is None:
                continue
            parsed = [parse_segbit_token(token) for token in fields[1:]]
            if not parsed or any(item is None for item in parsed):
                errors.append(f"{rule_file}:{line_number}: invalid or empty mux segbits rule")
                continue
            tokens = [item for item in parsed if item is not None]
            coordinates = frozenset((frame, bit) for frame, bit, _ in tokens)
            groups.setdefault(coordinates, {})[fields[0]] = tokens
        rule_group_cache[rule_file] = groups
        return groups

    def load_all_rule_coordinates(rule_file: str) -> set[tuple[int, int]]:
        cached = all_rule_coordinates_cache.get(rule_file)
        if cached is not None:
            return cached
        coordinates: set[tuple[int, int]] = set()
        rule_path = safe_child(data_dir, rule_file)
        for line_number, line in enumerate(rule_path.read_text(encoding="utf-8").splitlines(), 1):
            fields = line.split()
            for token in fields[1:]:
                parsed = parse_segbit_token(token)
                if parsed is None:
                    errors.append(f"{rule_file}:{line_number}: invalid frozen segbit token {token!r}")
                    continue
                coordinates.add((parsed[0], parsed[1]))
        all_rule_coordinates_cache[rule_file] = coordinates
        return coordinates

    def computed_address(tile_name: str, frame_offset: int, bit_offset: int) -> tuple[str, int, int] | None:
        block = tilegrid.get(tile_name, {}).get("bits", {}).get("CLB_IO_CLK")
        if block is None:
            return None
        return (
            f"0x{int(block['baseaddr'], 16) + frame_offset:08X}",
            block["offset"] + bit_offset // 32,
            bit_offset % 32,
        )

    actual_holdout_keys: set[PredictionKey] = set()
    result_keys: set[PredictionKey] = set()
    used_specimens: set[str] = set()
    mine_groups: set[str] = set()
    holdout_groups: set[str] = set()
    address_counts = (
        {"strict_codeword_equality": {"pass_count": 0, "fail_count": 0}}
        if certificate_1_4
        else {
            "group_exclusivity": {"pass_count": 0, "fail_count": 0},
            "scope_assignment": {"pass_count": 0, "fail_count": 0},
        }
    )
    diagnostic_counts = {
        "group_exclusivity": {"vacuous_count": 0, "ambiguity_count": 0},
        "decode_validity": {"pass_count": 0, "fail_count": 0},
    }
    semantic_counts = {"member_identity": {"pass_count": 0, "fail_count": 0}}
    asserted_addresses_by_tile: dict[str, set[tuple[str, int, int]]] = {}
    asserted_addresses_by_specimen: dict[str, set[tuple[str, int, int]]] = {}

    for result in certificate["group_results"]:
        specimen_id = result["prediction_specimen_id"]
        key = specimen_id, result["group"]
        if key in result_keys:
            errors.append(f"duplicate group result key {key!r}")
        result_keys.add(key)
        specimen = specimen_by_id.get(specimen_id)
        if specimen is None:
            errors.append(f"group result key {key!r} names an unknown specimen")
            continue
        used_specimens.add(specimen_id)
        committed = committed_by_key.get(key)
        if committed is None:
            errors.append(f"group result key {key!r} is absent from prediction commitment")
        else:
            recorded_prediction = {
                "specimen_id": specimen_id,
                "split": result["split"],
                "group": result["group"],
                "rule_file": result["rule_file"],
                "scope": result["scope"],
                "assertions": result["assertions"],
            }
            if recorded_prediction != committed:
                errors.append(f"group result key {key!r} differs from preregistered prediction")
        if specimen["split"] != result["split"]:
            errors.append(f"group result key {key!r}: specimen split differs from result")
        if result["split"] == "holdout":
            actual_holdout_keys.add(key)
            holdout_groups.add(result["group"])
        else:
            mine_groups.add(result["group"])

        rule_file = result["rule_file"]
        rule_record = manifest_files.get(rule_file)
        if rule_file not in pinned_paths:
            errors.append(f"group result key {key!r}: rule_file is not pinned")
        if rule_record is None or rule_record.get("role") != "segbits":
            errors.append(f"group result key {key!r}: rule_file is not a frozen segbits file")
            continue
        if spec_class is not None and rule_record.get("group") not in spec_class["from_groups"]:
            errors.append(f"group result key {key!r}: rule_file group is outside the certificate class")
        expected_rule_file = f"prjxray/zynq7/segbits_{specimen['tile_type'].lower()}.db"
        if rule_file != expected_rule_file:
            errors.append(f"group result key {key!r}: rule_file does not match specimen tile type")

        declared_coordinates: set[tuple[int, int]] = set()
        declared_scope: dict[tuple[int, int], tuple[str, int, int]] = {}
        for item in result["scope"]:
            parsed = parse_segbit_token(item["segbit"])
            if parsed is None or parsed[2]:
                errors.append(f"group result key {key!r}: invalid scope segbit {item['segbit']!r}")
                continue
            coordinate = parsed[0], parsed[1]
            if coordinate in declared_coordinates:
                errors.append(f"group result key {key!r}: duplicate scope coordinate {coordinate}")
            declared_coordinates.add(coordinate)
            address = address_key(item["address"])
            declared_scope[coordinate] = address
            asserted_addresses_by_tile.setdefault(specimen["tile"], set()).add(address)
            asserted_addresses_by_specimen.setdefault(specimen_id, set()).add(address)
            expected_address = computed_address(specimen["tile"], *coordinate)
            if expected_address is None or address != expected_address:
                errors.append(f"group result key {key!r}: scope address disagrees with normative arithmetic")

        try:
            rule_groups = load_rule_groups(rule_file)
        except (OSError, ValueError) as exc:
            errors.append(f"group result key {key!r}: cannot read rule_file: {exc}")
            continue
        frozen_members = rule_groups.get(frozenset(declared_coordinates))
        if frozen_members is None:
            errors.append(
                f"group result key {key!r}: declared scope is not a complete frozen bit-set group"
            )
            continue
        if len(result["scope"]) != len(declared_coordinates):
            errors.append(f"group result key {key!r}: scope is not a unique complete bit set")
        label_match = re.search(r"\[([^]]+)\]$", result["group"])
        if label_match is None:
            errors.append(f"group result key {key!r}: group label lacks an explicit member projection")
        else:
            labelled_members = set(label_match.group(1).split("|"))
            frozen_member_names = {feature.rsplit(".", 1)[-1] for feature in frozen_members}
            if labelled_members != frozen_member_names:
                errors.append(
                    f"group result key {key!r}: group label members differ from the bit-set-derived group"
                )
        tile = tilegrid[specimen["tile"]]
        ordered_sites = sorted(
            tile.get("sites", {}),
            key=lambda site_name: int(re.search(r"_X([0-9]+)Y", site_name).group(1)),
        )
        site_index = ordered_sites.index(specimen["site"])
        expected_site_prefix = f"{tile['sites'][specimen['site']]}_X{site_index}"
        for feature in frozen_members:
            fields = feature.split(".")
            if fields[:2] != [specimen["tile_type"], expected_site_prefix]:
                errors.append(
                    f"group result key {key!r}: bit-set-derived feature does not match specimen tile/site instance"
                )
                break

        assertions = {item["kind"]: item for item in result["assertions"]}
        outcomes = {item["kind"]: item for item in result["assertion_outcomes"]}
        required_assertions = {"group_exclusivity", "scope_assignment", "member_identity"}
        required_outcomes = required_assertions | ({"decode_validity"} if certificate_1_4 else set())
        if set(assertions) != required_assertions or set(outcomes) != required_outcomes:
            errors.append(
                f"group result key {key!r}: assertion/outcome kinds are not exactly "
                f"{sorted(required_assertions)} / {sorted(required_outcomes)}"
            )
            continue

        expected_items = assertions["scope_assignment"]["expected_assignment"]
        expected_values: dict[tuple[int, int], int] = {}
        for item in expected_items:
            parsed = parse_segbit_token(item["segbit"])
            if parsed is None or parsed[2]:
                errors.append(f"group result key {key!r}: invalid expected segbit")
                continue
            coordinate = parsed[0], parsed[1]
            if coordinate in expected_values:
                errors.append(f"group result key {key!r}: duplicate expected coordinate {coordinate}")
            expected_values[coordinate] = item["expected_value"]
            if declared_scope.get(coordinate) != address_key(item["address"]):
                errors.append(f"group result key {key!r}: expected assignment address differs from scope")
        if set(expected_values) != declared_coordinates:
            errors.append(f"group result key {key!r}: expected assignment is not the complete scope")

        member_encodings: dict[str, dict[tuple[int, int], int]] = {}
        for feature, tokens in frozen_members.items():
            member_encodings[feature.rsplit(".", 1)[-1]] = {
                (frame, bit): 0 if negated else 1
                for frame, bit, negated in tokens
            }
        collisions = frozen_codeword_collisions(member_encodings)
        if certificate_1_4 and collisions:
            errors.append(
                f"group result key {key!r}: frozen-group ambiguity; distinct names share a codeword "
                f"{collisions[:1]}"
            )
        expected_matches = sorted(
            member for member, encoding in member_encodings.items() if encoding == expected_values
        )
        if not expected_matches:
            errors.append(f"group result key {key!r}: expected assignment matches no frozen member")
        claimed_member = assertions["member_identity"]["predicted_member"]
        if expected_matches != [claimed_member]:
            errors.append(
                f"group result key {key!r}: expected assignment differs from the frozen rule for the claimed member"
            )

        observed_values: dict[tuple[int, int], int] = {}
        mismatched_addresses: list[tuple[str, int, int]] = []
        for item in result["observed_assignment"]:
            parsed = parse_segbit_token(item["segbit"])
            if parsed is None or parsed[2]:
                errors.append(f"group result key {key!r}: invalid observed segbit")
                continue
            coordinate = parsed[0], parsed[1]
            if coordinate in observed_values:
                errors.append(f"group result key {key!r}: duplicate observed coordinate {coordinate}")
            observed_values[coordinate] = item["observed_value"]
            if declared_scope.get(coordinate) != address_key(item["address"]):
                errors.append(f"group result key {key!r}: observed assignment address differs from scope")
            if item["expected_value"] != expected_values.get(coordinate):
                errors.append(f"group result key {key!r}: observed expected_value differs from prediction")
            if item["observed_value"] != item["expected_value"]:
                mismatched_addresses.append(address_key(item["address"]))
        if set(observed_values) != declared_coordinates:
            errors.append(f"group result key {key!r}: observed assignment is not the complete scope")

        decoded_members = sorted(
            member
            for member, encoding in member_encodings.items()
            if all(observed_values.get(coordinate) == value for coordinate, value in encoding.items())
        )
        if result["decoded_members"] != decoded_members:
            errors.append(f"group result key {key!r}: decoded_members differs from frozen assert-iff")

        exclusivity_passed = len(decoded_members) <= 1
        decode_validity_passed = bool(decoded_members)
        scope_passed = not mismatched_addresses and set(observed_values) == declared_coordinates
        exclusivity_outcome = outcomes["group_exclusivity"]
        scope_outcome = outcomes["scope_assignment"]
        if certificate_1_4:
            if (
                exclusivity_outcome["decoded_members"] != decoded_members
                or exclusivity_outcome.get("classification") != "vacuous"
                or "passed" in exclusivity_outcome
            ):
                errors.append(f"group result key {key!r}: group_exclusivity vacuity outcome is wrong")
            decode_outcome = outcomes["decode_validity"]
            if (
                decode_outcome["decoded_members"] != decoded_members
                or decode_outcome["passed"] != decode_validity_passed
            ):
                errors.append(f"group result key {key!r}: decode_validity diagnostic is wrong")
        elif (
            exclusivity_outcome["decoded_members"] != decoded_members
            or exclusivity_outcome["passed"] != exclusivity_passed
        ):
            errors.append(f"group result key {key!r}: group_exclusivity outcome is wrong")
        recorded_mismatched = sorted(address_key(item) for item in scope_outcome["mismatched"])
        if recorded_mismatched != sorted(mismatched_addresses) or scope_outcome["passed"] != scope_passed:
            errors.append(f"group result key {key!r}: scope_assignment outcome is wrong")

        semantic_assertion = assertions["member_identity"]
        semantic_outcome = outcomes["member_identity"]
        basis = semantic_assertion["netlist_basis"]
        expected_basis = GROUP_BASIS_LUT if specimen["ffsrc"] == 0 else GROUP_BASIS_PIN
        if basis != expected_basis:
            errors.append(f"group result key {key!r}: netlist_basis disagrees with specimen ffsrc")
        if basis == GROUP_BASIS_LUT:
            rebuilt_expected_edge: dict[str, Any] = {"driver_ref": "LUT6", "driver_cell": "target"}
        elif basis == GROUP_BASIS_PIN:
            rebuilt_expected_edge = {"driver_ref": "IBUF", "requires_source_port": True}
        else:
            errors.append(f"group result key {key!r}: unrecognized netlist_basis")
            rebuilt_expected_edge = {}
        if semantic_outcome["netlist_basis"] != basis:
            errors.append(f"group result key {key!r}: outcome netlist_basis differs from prediction")
        if semantic_outcome["expected_edge"] != rebuilt_expected_edge:
            errors.append(f"group result key {key!r}: producer expected_edge differs from independent rebuild")
        attested_edge = semantic_outcome["attested_edge"]
        attestation = specimen_attestations.get(specimen_id)
        if attestation is not None:
            resolved = attestation["resolved"]
            raw_edge = {
                "ff_bel": resolved["ff_bel"],
                "ff_d_net": resolved["ff_d_net"],
                "ff_d_driver_pin": resolved["ff_d_driver_pin"],
                "ff_d_driver_cell": resolved["ff_d_driver_cell"],
                "ff_d_driver_ref": resolved["ff_d_driver_ref"],
                "ff_d_source_port": resolved["ff_d_source_port"],
                "ff_d_source_package_pin": resolved["ff_d_source_package_pin"],
                "ff_d_net_route_status": resolved["ff_d_net_route_status"],
                "checkpoint": attestation["checkpoint"],
            }
            if attested_edge != raw_edge:
                errors.append(f"group result key {key!r}: attested_edge differs from pinned attestation")
        route_ok = attested_edge["ff_d_net_route_status"] == "ROUTED"
        checkpoint_ok = attested_edge["checkpoint"] == specimen["attestation"]["checkpoint"]
        if basis == GROUP_BASIS_LUT:
            edge_consistent = (
                route_ok
                and checkpoint_ok
                and attested_edge["ff_d_driver_ref"] == "LUT6"
                and attested_edge["ff_d_driver_cell"] == "target"
            )
        elif basis == GROUP_BASIS_PIN:
            edge_consistent = (
                route_ok
                and checkpoint_ok
                and attested_edge["ff_d_driver_ref"] == "IBUF"
                and bool(attested_edge["ff_d_source_port"])
                and bool(attested_edge["ff_d_source_package_pin"])
            )
        else:
            edge_consistent = False
        identity_passed = decoded_members == [semantic_assertion["predicted_member"]]
        semantic_passed = identity_passed and edge_consistent
        if semantic_outcome["predicted_member"] != semantic_assertion["predicted_member"]:
            errors.append(f"group result key {key!r}: semantic predicted_member differs from prediction")
        if semantic_outcome["decoded_members"] != decoded_members:
            errors.append(f"group result key {key!r}: semantic decoded_members is wrong")
        if semantic_outcome["netlist_basis_consistent"] != edge_consistent:
            errors.append(f"group result key {key!r}: netlist_basis_consistent summary is wrong")
        if semantic_outcome["passed"] != semantic_passed:
            errors.append(f"group result key {key!r}: member_identity outcome is wrong")

        if result["split"] == "holdout":
            if certificate_1_4:
                address_counts["strict_codeword_equality"][
                    "pass_count" if scope_passed else "fail_count"
                ] += 1
                diagnostic_counts["group_exclusivity"][
                    "ambiguity_count" if collisions else "vacuous_count"
                ] += 1
                diagnostic_counts["decode_validity"][
                    "pass_count" if decode_validity_passed else "fail_count"
                ] += 1
            else:
                for kind, passed in (
                    ("group_exclusivity", exclusivity_passed),
                    ("scope_assignment", scope_passed),
                ):
                    address_counts[kind]["pass_count" if passed else "fail_count"] += 1
            semantic_counts["member_identity"]["pass_count" if semantic_passed else "fail_count"] += 1

    if actual_holdout_keys != committed_holdout_keys:
        missing = sorted(committed_holdout_keys - actual_holdout_keys)
        extra = sorted(actual_holdout_keys - committed_holdout_keys)
        errors.append(
            "holdout group completeness mismatch "
            f"(missing={len(missing)} {missing[:1]} extra={len(extra)} {extra[:1]})"
        )
    if result_keys != set(committed_by_key):
        errors.append("group_results do not report every committed mine/holdout pair exactly once")
    if used_specimens != set(specimen_by_id):
        errors.append("specimens must be referenced by at least one group result")

    recorded_split = class_record["split"]
    if set(recorded_split["mine_groups"]) != mine_groups:
        errors.append("bit_class.split.mine_groups differs from group_results projection")
    if set(recorded_split["holdout_groups"]) != holdout_groups:
        errors.append("bit_class.split.holdout_groups differs from group_results projection")
    coverage = class_record["coverage"]
    if coverage["attested_count"] != len(certificate["group_results"]):
        errors.append("coverage.attested_count differs from group_results count")
    if coverage["class_entry_count"] != current_entries:
        errors.append("coverage.class_entry_count differs from current manifest")

    partition_ok = True
    accounted_specimens: set[str] = set()
    unpinned_claiming_db_counts: dict[str, int] = {}

    # Index every physical CLB_IO_CLK geometry interval independently from the
    # producer's ownership labels.  CLB and INT tiles deliberately overlap in
    # this coordinate space, so all candidates must be retained.
    geometry_by_far_word: dict[tuple[int, int], list[tuple[str, str, int, int]]] = {}
    for tile_name, tile in tilegrid.items():
        block = tile.get("bits", {}).get("CLB_IO_CLK")
        if block is None:
            continue
        baseaddr = int(block["baseaddr"], 16)
        for frame_offset in range(block["frames"]):
            for word_offset in range(block["words"]):
                geometry_by_far_word.setdefault(
                    (baseaddr + frame_offset, block["offset"] + word_offset),
                    [],
                ).append((tile_name, tile["type"], frame_offset, word_offset))

    bucket_evidence_cache: dict[
        tuple[str, int, int],
        tuple[str, set[str], set[str]],
    ] = {}

    def independently_classify_bucket(
        address: tuple[str, int, int],
    ) -> tuple[str, set[str], set[str]]:
        """Return (bucket, candidate DBs, claiming DBs) for an out-of-scope bit."""

        cached = bucket_evidence_cache.get(address)
        if cached is not None:
            return cached
        far_text, word, bit = address
        candidates = geometry_by_far_word.get((int(far_text, 16), word), [])
        if not candidates:
            result = "unattributed", set(), set()
            bucket_evidence_cache[address] = result
            return result

        candidate_dbs: set[str] = set()
        claiming_dbs: set[str] = set()
        for _tile_name, tile_type, frame_offset, word_offset in candidates:
            rule_file = f"prjxray/zynq7/segbits_{tile_type.lower()}.db"
            record = manifest_files.get(rule_file)
            if (
                record is None
                or record.get("role") != "segbits"
                or not record.get("classified", False)
                or rule_file.endswith(".origin_info.db")
            ):
                continue
            candidate_dbs.add(rule_file)
            coordinate = frame_offset, word_offset * 32 + bit
            if coordinate in load_all_rule_coordinates(rule_file):
                claiming_dbs.add(rule_file)
        result = (
            "db_attributed" if claiming_dbs else "ownership_unknown",
            candidate_dbs,
            claiming_dbs,
        )
        bucket_evidence_cache[address] = result
        return result

    for index, accounting in enumerate(certificate["pair_accounting"]):
        pair_ids = accounting["specimen_ids"]
        accounted_specimens.update(pair_ids)
        pair = [specimen_by_id.get(specimen_id) for specimen_id in pair_ids]
        if any(item is None for item in pair):
            errors.append(f"pair_accounting[{index}] names an unknown specimen")
        else:
            first, second = pair
            assert first is not None and second is not None
            if first["site"] != second["site"] or first["ff_bel"] != second["ff_bel"]:
                errors.append(f"pair_accounting[{index}] does not pair one site/FF BEL")
            if {first["ffsrc"], second["ffsrc"]} != {0, 1}:
                errors.append(f"pair_accounting[{index}] does not pair ffsrc 0 and 1")
        union: set[tuple[str, int, int]] = set()
        disjoint = True
        for bucket in GROUP_BUCKETS:
            values = [address_key(item) for item in accounting["buckets"][bucket]]
            value_set = set(values)
            if len(value_set) != len(values):
                errors.append(f"pair_accounting[{index}].{bucket} duplicates a bit")
                disjoint = False
            overlap = union & value_set
            if overlap:
                errors.append(f"pair_accounting[{index}] bucket overlap at {sorted(overlap)[:1]}")
                disjoint = False
            union |= value_set
            if accounting["counts"][bucket] != len(values):
                errors.append(f"pair_accounting[{index}].counts.{bucket} differs from bit list length")
                disjoint = False
        exact = disjoint and len(union) == accounting["raw_diff_bits"]
        if len(union) != accounting["raw_diff_bits"]:
            errors.append(f"pair_accounting[{index}] bucket union size differs from raw_diff_bits")
        if accounting["partition_exact"] != exact:
            errors.append(f"pair_accounting[{index}].partition_exact summary is wrong")

        pair_scope: set[tuple[str, int, int]] = set()
        for specimen_id in pair_ids:
            pair_scope.update(asserted_addresses_by_specimen.get(specimen_id, set()))
        for recorded_bucket in GROUP_BUCKETS:
            for bit_record in accounting["buckets"][recorded_bucket]:
                address = address_key(bit_record)
                if address in pair_scope:
                    expected_bucket = "in_scope"
                    candidate_dbs: set[str] = set()
                    claiming_dbs: set[str] = set()
                elif address[1] == 50 and 0 <= address[2] <= 12:
                    expected_bucket = "frame_ecc"
                    candidate_dbs = set()
                    claiming_dbs = set()
                else:
                    expected_bucket, candidate_dbs, claiming_dbs = independently_classify_bucket(address)
                if recorded_bucket != expected_bucket:
                    errors.append(
                        f"pair_accounting[{index}] bit {address} is labelled {recorded_bucket} "
                        f"but frozen geometry/DB evidence requires {expected_bucket}"
                    )
                if expected_bucket == "db_attributed" and not (claiming_dbs & pinned_paths):
                    for rule_file in claiming_dbs:
                        unpinned_claiming_db_counts[rule_file] = (
                            unpinned_claiming_db_counts.get(rule_file, 0) + 1
                        )
                if expected_bucket == "ownership_unknown":
                    missing_candidate_dbs = candidate_dbs - pinned_paths
                    if missing_candidate_dbs:
                        errors.append(
                            f"pair_accounting[{index}] ownership_unknown bit {address} lacks pinned "
                            f"candidate frozen DBs {sorted(missing_candidate_dbs)}"
                        )
        partition_ok = partition_ok and exact
    if unpinned_claiming_db_counts:
        errors.append(
            "pair accounting consumes unpinned claiming frozen DBs "
            f"{dict(sorted(unpinned_claiming_db_counts.items()))}"
        )
    if accounted_specimens != set(specimen_by_id):
        errors.append("pair_accounting does not cover every specimen")

    if class_record["address_accounting"] != address_counts:
        errors.append(
            f"address_accounting mismatch (recorded={class_record['address_accounting']} computed={address_counts})"
        )
    if certificate_1_4 and class_record["diagnostic_accounting"] != diagnostic_counts:
        errors.append(
            "diagnostic_accounting mismatch "
            f"(recorded={class_record['diagnostic_accounting']} computed={diagnostic_counts})"
        )
    if class_record["semantic_accounting"] != semantic_counts:
        errors.append(
            f"semantic_accounting mismatch (recorded={class_record['semantic_accounting']} computed={semantic_counts})"
        )

    address_passed = partition_ok and (
        address_counts["strict_codeword_equality"]["fail_count"] == 0
        if certificate_1_4
        else address_counts["group_exclusivity"]["fail_count"] == 0
        and address_counts["scope_assignment"]["fail_count"] == 0
    )
    uncovered_by_tile: dict[str, int] = {}
    if certificate["claim_scope"] == "tile":
        for tile_name in {specimen["tile"] for specimen in specimen_by_id.values()}:
            tile_type = tilegrid.get(tile_name, {}).get("type")
            if not isinstance(tile_type, str):
                continue
            rule_file = f"prjxray/zynq7/segbits_{tile_type.lower()}.db"
            if rule_file not in pinned_paths:
                errors.append(f"tile-wide claim lacks pinned frozen DB for {tile_name}")
                continue
            try:
                required_addresses = {
                    computed_address(tile_name, frame, bit)
                    for frame, bit in load_all_rule_coordinates(rule_file)
                }
            except (OSError, ValueError) as exc:
                errors.append(f"tile-wide claim cannot read frozen DB for {tile_name}: {exc}")
                continue
            required_addresses.discard(None)
            uncovered = required_addresses - asserted_addresses_by_tile.get(tile_name, set())
            if uncovered:
                uncovered_by_tile[tile_name] = len(uncovered)
        if uncovered_by_tile:
            address_passed = False
        has_unknown = False
        for accounting in certificate["pair_accounting"]:
            blocks = [
                tilegrid.get(specimen_by_id.get(specimen_id, {}).get("tile", ""), {})
                .get("bits", {})
                .get("CLB_IO_CLK")
                for specimen_id in accounting["specimen_ids"]
            ]
            for bit in accounting["buckets"]["ownership_unknown"]:
                far = int(bit["far"], 16)
                if any(
                    block is not None
                    and int(block["baseaddr"], 16) <= far < int(block["baseaddr"], 16) + block["frames"]
                    and block["offset"] <= bit["word"] < block["offset"] + block["words"]
                    for block in blocks
                ):
                    has_unknown = True
                    break
            if has_unknown:
                break
        if has_unknown:
            address_passed = False
    expected_status = "passed" if address_passed else "failed"
    semantic_passed = semantic_counts["member_identity"]["fail_count"] == 0
    expected_semantic_status = "passed" if semantic_passed else "failed"
    if certificate["status"] != expected_status:
        detail = ""
        if certificate["claim_scope"] == "tile" and uncovered_by_tile:
            detail = f"; tile-wide DB coverage leaves uncovered addresses {uncovered_by_tile}"
        errors.append(
            f"status={certificate['status']} but address evidence requires {expected_status}{detail}"
        )
    if certificate["semantic_status"] != expected_semantic_status:
        errors.append(
            f"semantic_status={certificate['semantic_status']} but semantic evidence requires {expected_semantic_status}"
        )
    return errors


def feature_1_4_semantic_errors(
    certificate: dict[str, Any],
    repo_root: Path,
    require_production: bool = False,
) -> list[str]:
    """Validate feature evidence from 1.4 onward and derive freeze-owned facts."""

    errors: list[str] = []
    certificate_version = tuple(
        int(part) for part in certificate["schema_version"].split(".")
    )
    feature_1_5 = certificate_version >= (1, 5, 0)
    feature_1_6 = certificate_version >= (1, 6, 0)
    data_dir = repo_root / "data"
    manifest = load_json(data_dir / "MANIFEST.json")
    spec = load_json(data_dir / "subset_spec.json")
    tilegrid = load_json(data_dir / "prjxray/zynq7/xc7z010/tilegrid.json")

    if require_production and certificate.get("profile") != "production":
        errors.append("production verification requires profile='production'")

    # The formal FF profile acquired an exact staged-artifact contract in 1.6.  That
    # contract cannot be optional for a production clb_ff_config record: otherwise an
    # emitter can remove staging_manifest, label the same record 1.5, and make every
    # staging completeness check disappear.  Historical 1.5 conformance fixtures remain
    # valid; the lower bound belongs to this class's production policy, not to the generic
    # 1.x JSON grammar.
    if (
        certificate.get("profile") == "production"
        and certificate.get("bit_class", {}).get("id") == "clb_ff_config"
        and certificate_version < (1, 6, 0)
    ):
        errors.append(
            "production clb_ff_config feature evidence requires "
            "certificate schema_version >= 1.6.0"
        )

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
    if spec_class is None:
        errors.append(f"bit class {class_record['id']!r} is absent from subset spec")
        feature_pattern = None
    else:
        feature_pattern = re.compile(spec_class["feature_regex"])

    commitment_errors, committed_by_key, committed_holdout_keys = load_prediction_commitment(
        certificate,
        repo_root,
    )
    errors.extend(commitment_errors)

    committed_specimens: dict[str, dict[str, Any]] = {}
    staging_entries: dict[str, dict[str, Any]] = {}
    staged_attestations: dict[str, dict[str, Any]] = {}
    # Attestation 2.0 rebuilds requested/resolved topology against the committed
    # specimen identity, so the plan is needed from 1.5 onward even though exact staging
    # is a 1.6 rule.  Keeping both operations under `feature_1_6` made a downgraded 1.5
    # record fail accidentally with "absent from ... specimen plan" rather than because
    # production FF evidence is forbidden to downgrade.
    if feature_1_5:
        try:
            commitment_path = safe_child(
                repo_root, certificate["prediction_commitment"]["path"]
            )
            commitment_document = load_json(commitment_path)
            for item in commitment_document["specimens"]:
                specimen_id = item["specimen_id"]
                if specimen_id in committed_specimens:
                    errors.append(
                        f"prediction commitment duplicates specimen_id {specimen_id!r}"
                    )
                committed_specimens[specimen_id] = item
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"cannot load committed specimen plan: {exc}")

    if feature_1_6:
        try:
            staging_errors, staging_entries, staged_attestations = load_feature_staging(
                certificate,
                repo_root,
                committed_specimens,
            )
            errors.extend(staging_errors)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"cannot load 1.6 staged specimen contract: {exc}")

    specimens = certificate["specimens"]
    specimen_by_id: dict[str, dict[str, Any]] = {}
    attestation_cache: dict[tuple[str, str], dict[str, Any]] = {}
    specimen_attestations: dict[str, dict[str, Any]] = {}
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
            errors.append(f"specimen {specimen_id}: tile lacks CLB_IO_CLK geometry")
        elif specimen["tile_frame_base"] != block["baseaddr"]:
            errors.append(f"specimen {specimen_id}: tile_frame_base differs from tilegrid")

        reference = specimen.get("attestation")
        if certificate.get("profile") == "production" and reference is None:
            errors.append(f"specimen {specimen_id}: 1.4 production evidence requires attestation")
        if reference is None:
            continue
        if feature_1_6:
            staged = staging_entries.get(specimen_id)
            if staged is None:
                errors.append(f"specimen {specimen_id}: absent from staging manifest")
            else:
                if reference != staged["attestation"]:
                    errors.append(
                        f"specimen {specimen_id}: attestation reference differs from staging"
                    )
                if specimen["bitstream_sha256"] != staged["bitstream"]["sha256"]:
                    errors.append(
                        f"specimen {specimen_id}: bitstream hash differs from staging"
                    )
        cache_key = reference["path"], reference["sha256"]
        attestation = staged_attestations.get(specimen_id) if feature_1_6 else None
        if feature_1_6 and attestation is None:
            errors.append(f"specimen {specimen_id}: staged attestation did not validate")
            continue
        if attestation is None:
            attestation = attestation_cache.get(cache_key)
        if attestation is None:
            try:
                path = safe_child(repo_root, reference["path"])
                if not path.is_file():
                    raise ValueError(f"attestation file does not exist: {reference['path']}")
                if hash_file(path) != reference["sha256"]:
                    raise ValueError("attestation hash mismatch")
                attestation = load_json(path)
                findings = validate_external_schema(
                    attestation,
                    repo_root / "schemas/specimen_attestation.schema.json",
                    f"specimen {specimen_id} attestation",
                )
                errors.extend(findings)
                if findings:
                    attestation = None
                else:
                    attestation_cache[cache_key] = attestation
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                errors.append(f"specimen {specimen_id}: cannot validate attestation: {exc}")
                attestation = None
        if attestation is not None:
            specimen_attestations[specimen_id] = attestation
            if attestation["schema_version"] != reference["schema_version"]:
                errors.append(f"specimen {specimen_id}: pinned attestation schema_version differs from file")
            if attestation["schema_version"].startswith("1."):
                if attestation["resolved"]["resolved_loc"] != specimen["loc_site"]:
                    errors.append(f"specimen {specimen_id}: attested resolved_loc differs from loc_site")
                if attestation["resolved"]["tile"] != specimen["tile"]:
                    errors.append(f"specimen {specimen_id}: attested tile differs from specimen tile")
                if attestation["inputs"]["part"] != specimen["part"]:
                    errors.append(f"specimen {specimen_id}: attested input part differs from specimen part")
                if specimen["bitstream_sha256"] not in attestation["outputs"].values():
                    errors.append(f"specimen {specimen_id}: bitstream_sha256 is absent from attestation outputs")
            else:
                committed_specimen = committed_specimens.get(specimen_id)
                if committed_specimen is None:
                    errors.append(
                        f"specimen {specimen_id}: absent from prediction commitment specimen plan"
                    )
                else:
                    errors.extend(
                        ff_formal_attestation_errors(
                            attestation,
                            specimen,
                            committed_specimen,
                            certificate["prediction_commitment"],
                            repo_root,
                        )
                    )

    if feature_1_6 and set(specimen_by_id) != set(committed_specimens):
        errors.append(
            "certificate specimen completeness differs from prediction commitment "
            f"(missing={len(set(committed_specimens) - set(specimen_by_id))} "
            f"extra={len(set(specimen_by_id) - set(committed_specimens))})"
        )
    if feature_1_6:
        for specimen_id, attestation in specimen_attestations.items():
            if attestation.get("schema_version") != "2.0.0":
                continue
            checkpoint = attestation["checkpoint"]
            if checkpoint["kind"] != "derived":
                continue
            source = checkpoint["source"]
            source_attestation = specimen_attestations.get(source["specimen_id"])
            if source_attestation is None:
                errors.append(
                    f"specimen {specimen_id}: derived checkpoint source specimen is absent"
                )
                continue
            source_checkpoint = source_attestation.get("checkpoint", {})
            if source_checkpoint.get("kind") != "implementation" or source_checkpoint.get(
                "artifact"
            ) != {"file": source["file"], "sha256": source["sha256"]}:
                errors.append(
                    f"specimen {specimen_id}: derived source checkpoint does not match "
                    "the pinned source specimen"
                )

    rule_lines_cache: dict[str, dict[str, list[str]]] = {}
    coordinate_claims_cache: dict[str, dict[tuple[int, int], set[str]]] = {}

    def load_rule_lines(rule_file: str) -> dict[str, list[str]]:
        cached = rule_lines_cache.get(rule_file)
        if cached is not None:
            return cached
        lines: dict[str, list[str]] = {}
        path = safe_child(data_dir, rule_file)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            fields = line.split()
            if not fields:
                continue
            if fields[0] in lines:
                errors.append(f"{rule_file}:{line_number}: duplicate frozen feature {fields[0]!r}")
            lines[fields[0]] = fields[1:]
        rule_lines_cache[rule_file] = lines
        return lines

    def load_coordinate_claims(rule_file: str) -> dict[tuple[int, int], set[str]]:
        cached = coordinate_claims_cache.get(rule_file)
        if cached is not None:
            return cached
        claims: dict[tuple[int, int], set[str]] = {}
        for feature, tokens in load_rule_lines(rule_file).items():
            for token in tokens:
                parsed = parse_segbit_token(token)
                if parsed is not None:
                    claims.setdefault((parsed[0], parsed[1]), set()).add(feature)
        coordinate_claims_cache[rule_file] = claims
        return claims

    def computed_address(tile_name: str, frame_offset: int, bit_offset: int) -> tuple[str, int, int] | None:
        block = tilegrid.get(tile_name, {}).get("bits", {}).get("CLB_IO_CLK")
        if block is None:
            return None
        return (
            f"0x{int(block['baseaddr'], 16) + frame_offset:08X}",
            block["offset"] + bit_offset // 32,
            bit_offset % 32,
        )

    split = class_record["split"]
    mine_set = set(split["mine_features"])
    holdout_set = set(split["holdout_features"])
    if mine_set & holdout_set:
        errors.append(f"mine and holdout feature projections overlap: {sorted(mine_set & holdout_set)[:1]}")

    result_keys: set[PredictionKey] = set()
    actual_holdout_keys: set[PredictionKey] = set()
    actual_mine_features: set[str] = set()
    actual_holdout_features: set[str] = set()
    used_specimens: set[str] = set()
    pair_scopes: dict[frozenset[str], set[tuple[str, int, int]]] = {}
    observations: dict[tuple[str, tuple[str, int, int]], int] = {}
    computed_tp = 0
    computed_fn = 0
    semantic_counts = {"member_identity": {"pass_count": 0, "fail_count": 0}}

    # From 1.5 onward both endpoint identity and pair scope are commitment-owned.
    # Deriving them here prevents a post-build certificate from selecting a new
    # comparison endpoint and then making its accounting self-consistent with it.
    if feature_1_5:
        for key, prediction in committed_by_key.items():
            specimen_id = prediction.get("specimen_id")
            comparison_id = prediction.get("comparison_specimen_id")
            if (
                not isinstance(specimen_id, str)
                or not isinstance(comparison_id, str)
                or specimen_id == comparison_id
            ):
                continue
            pair_key = frozenset((specimen_id, comparison_id))
            if len(pair_key) != 2:
                continue
            scope = pair_scopes.setdefault(pair_key, set())
            try:
                scope.update(
                    address_key(item["address"])
                    for item in prediction["predicted_assignments"]
                )
            except (KeyError, TypeError):
                errors.append(
                    f"prediction artifact pair key {key!r} has malformed committed addresses"
                )

    def record_observation(specimen_id: str, address: tuple[str, int, int], value: int) -> None:
        key = specimen_id, address
        prior = observations.get(key)
        if prior is not None and prior != value:
            errors.append(
                f"observation inconsistency for specimen/address {key!r}: {prior} versus {value}"
            )
        observations[key] = value

    used_rule_files: set[str] = set()
    for result in certificate["feature_results"]:
        feature = result["feature"]
        key = result["prediction_specimen_id"], feature
        if key in result_keys:
            errors.append(f"duplicate feature result key {key!r}")
        result_keys.add(key)
        committed = committed_by_key.get(key)
        if committed is None:
            errors.append(f"feature result key {key!r} is absent from prediction commitment")
        else:
            projection = {
                "specimen_id": result["prediction_specimen_id"],
                "feature": feature,
                "split": result["split"],
                "rule_file": result["rule_file"],
                "predicted_assignments": result["predicted_assignments"],
                "expected_transition": result["expected_transition"],
                "semantic_assertion": result["semantic_assertion"],
            }
            committed_projection = {
                field: value
                for field, value in committed.items()
                if field != "comparison_specimen_id"
            }
            if projection != committed_projection:
                errors.append(f"feature result key {key!r} differs from preregistered prediction")
            if (
                feature_1_5
                and result["baseline_specimen_id"]
                != committed.get("comparison_specimen_id")
            ):
                errors.append(
                    f"feature result key {key!r}: baseline endpoint differs from preregistered "
                    "comparison specimen"
                )

        if result["split"] == "holdout":
            actual_holdout_keys.add(key)
            actual_holdout_features.add(feature)
        else:
            actual_mine_features.add(feature)

        baseline_id = result["baseline_specimen_id"]
        feature_id = result["feature_specimen_id"]
        baseline = specimen_by_id.get(baseline_id)
        feature_specimen = specimen_by_id.get(feature_id)
        if baseline is None or feature_specimen is None:
            errors.append(f"feature result key {key!r} names an unknown endpoint specimen")
            continue
        used_specimens.update((baseline_id, feature_id))
        if feature_id != result["prediction_specimen_id"]:
            errors.append(f"feature result key {key!r}: feature endpoint differs from prediction specimen")
        if baseline["split"] != result["split"] or feature_specimen["split"] != result["split"]:
            errors.append(f"feature result key {key!r}: endpoint split differs from result")
        if baseline["tile"] != feature_specimen["tile"]:
            errors.append(f"feature result key {key!r}: endpoints are not in the same physical tile")

        pair_key = frozenset((baseline_id, feature_id))
        if len(pair_key) != 2:
            errors.append(f"feature result key {key!r}: endpoint pair is not distinct")
        scope = (
            pair_scopes.get(pair_key, set())
            if feature_1_5
            else pair_scopes.setdefault(pair_key, set())
        )

        rule_file = result["rule_file"]
        used_rule_files.add(rule_file)
        record = manifest_files.get(rule_file)
        if rule_file not in pinned_paths:
            errors.append(f"feature result key {key!r}: rule_file is not pinned")
        if record is None or record.get("role") != "segbits" or not record.get("classified", False):
            errors.append(f"feature result key {key!r}: rule_file is not a classified frozen segbits file")
            continue
        if spec_class is not None and record.get("group") not in spec_class["from_groups"]:
            errors.append(f"feature result key {key!r}: rule_file group is outside the certificate class")
        if feature_pattern is not None and feature_pattern.fullmatch(feature) is None:
            errors.append(f"feature result key {key!r}: feature is outside the certificate class")
        try:
            frozen_tokens = load_rule_lines(rule_file).get(feature)
        except (OSError, ValueError) as exc:
            errors.append(f"feature result key {key!r}: cannot read rule_file: {exc}")
            continue
        if frozen_tokens is None:
            errors.append(f"feature result key {key!r}: feature is absent from rule_file")
            continue
        assignments = result["predicted_assignments"]
        if [item["token"] for item in assignments] != frozen_tokens:
            errors.append(f"feature result key {key!r}: prediction differs from exact frozen token sequence")

        predicted: dict[tuple[str, int, int], int] = {}
        for item in assignments:
            token = parse_segbit_token(item["token"])
            segbit = item["segbit"]
            parsed_segbit = segbit["frame_offset"], segbit["bit_offset"], segbit["negated"]
            if token is None or token != parsed_segbit:
                errors.append(f"feature result key {key!r}: token and parsed segbit disagree")
                continue
            expected_value = 0 if token[2] else 1
            if item["expected_value"] != expected_value:
                errors.append(f"feature result key {key!r}: expected polarity is wrong")
            address = address_key(item["address"])
            if address in predicted:
                errors.append(f"feature result key {key!r}: duplicate predicted address {address}")
            predicted[address] = item["expected_value"]
            if not feature_1_5:
                scope.add(address)
            expected_address = computed_address(feature_specimen["tile"], token[0], token[1])
            if expected_address is None or expected_address != address:
                errors.append(f"feature result key {key!r}: address disagrees with normative arithmetic")

        observed: dict[tuple[str, int, int], tuple[int, int]] = {}
        transition = result["expected_transition"]
        for item in result["observed_assignments"]:
            address = address_key(item["address"])
            if address in observed:
                errors.append(f"feature result key {key!r}: duplicate observed address {address}")
            before_after = item["before_value"], item["after_value"]
            observed[address] = before_after
            if item["observed_value"] != item["after_value"]:
                errors.append(f"feature result key {key!r}: observed_value is not the after endpoint value")
            record_observation(baseline_id, address, item["before_value"])
            record_observation(feature_id, address, item["after_value"])
        complete = set(observed) == set(predicted)
        transition_exact = complete and all(
            before == transition["before"]
            and after == transition["after"]
            and after == predicted[address]
            for address, (before, after) in observed.items()
        )
        computed_verdict = "matched" if transition_exact else "mismatched"
        if result["verdict"] != computed_verdict:
            errors.append(
                f"feature result key {key!r}: verdict={result['verdict']} but endpoint evidence computes "
                f"{computed_verdict}"
            )
        if result["split"] == "holdout":
            if transition_exact:
                computed_tp += 1
            else:
                computed_fn += 1

        semantic_assertion = result["semantic_assertion"]
        semantic_outcome = result["semantic_outcome"]
        if semantic_assertion["predicted_member"] != feature:
            errors.append(f"feature result key {key!r}: semantic predicted_member differs from feature")
        attestation = specimen_attestations.get(feature_id)
        if attestation is None:
            errors.append(f"feature result key {key!r}: semantic claim has no auditable attestation")
            attested_value: Any = None
            basis_consistent = False
        else:
            try:
                attested_value = resolve_json_pointer(
                    attestation,
                    semantic_assertion["attestation_field"],
                )
                basis_consistent = attested_value == semantic_assertion["expected_value"]
            except ValueError as exc:
                errors.append(f"feature result key {key!r}: {exc}")
                attested_value = None
                basis_consistent = False
        semantic_passed = transition_exact and basis_consistent
        expected_semantic_summary = {
            "kind": "member_identity",
            "semantic": True,
            "passed": semantic_passed,
            "predicted_member": feature,
            "attestation_field": semantic_assertion["attestation_field"],
            "expected_value": semantic_assertion["expected_value"],
            "observed_value": attested_value,
        }
        if semantic_outcome != expected_semantic_summary:
            errors.append(
                f"feature result key {key!r}: semantic_outcome differs from pinned attestation rebuild"
            )
        if result["split"] == "holdout":
            semantic_counts["member_identity"][
                "pass_count" if semantic_passed else "fail_count"
            ] += 1

    completeness_ok = result_keys == set(committed_by_key)
    if actual_holdout_keys != committed_holdout_keys:
        missing = sorted(committed_holdout_keys - actual_holdout_keys)
        extra = sorted(actual_holdout_keys - committed_holdout_keys)
        errors.append(
            "holdout prediction completeness mismatch "
            f"(missing={len(missing)} {missing[:1]} extra={len(extra)} {extra[:1]})"
        )
    if not completeness_ok:
        errors.append("feature_results do not report every committed mine/holdout pair exactly once")
    if actual_mine_features != mine_set or actual_holdout_features != holdout_set:
        errors.append("feature_results split projections differ from declared feature membership")
    if used_specimens != set(specimen_by_id):
        errors.append("specimens must be referenced by at least one feature result endpoint")

    # A group is freeze-derived by a shared polarity-free bit set.  Duplicate
    # codewords under distinct names are an ambiguity in the frozen format, not
    # an address pass or a producer-selectable assertion.
    for rule_file in used_rule_files:
        try:
            groups: dict[frozenset[tuple[int, int]], dict[tuple[int, ...], list[str]]] = {}
            for feature, tokens in load_rule_lines(rule_file).items():
                if feature_pattern is None or feature_pattern.fullmatch(feature) is None:
                    continue
                parsed = [parse_segbit_token(token) for token in tokens]
                if not parsed or any(item is None for item in parsed):
                    errors.append(
                        f"{rule_file}: invalid or empty frozen rule for class feature {feature!r}"
                    )
                    continue
                values = [item for item in parsed if item is not None]
                coordinates = frozenset((frame, bit) for frame, bit, _ in values)
                ordered = sorted(values, key=lambda item: (item[0], item[1]))
                codeword = tuple(0 if negated else 1 for _, _, negated in ordered)
                groups.setdefault(coordinates, {}).setdefault(codeword, []).append(feature)
            for coordinates, codewords in groups.items():
                collisions = [names for names in codewords.values() if len(names) > 1]
                if collisions:
                    errors.append(
                        f"{rule_file}: frozen-group ambiguity at {sorted(coordinates)}; "
                        f"distinct names share a codeword {collisions[:1]}"
                    )
        except (OSError, ValueError) as exc:
            errors.append(f"cannot derive group consistency from {rule_file}: {exc}")

    # Shared five-bucket accounting.  The verifier can recompute labels and the
    # frozen ownership evidence, though not raw_diff_bits without bitstreams.
    geometry_by_far_word: dict[tuple[int, int], list[tuple[str, str, int, int]]] = {}
    for tile_name, tile in tilegrid.items():
        block = tile.get("bits", {}).get("CLB_IO_CLK")
        if block is None:
            continue
        baseaddr = int(block["baseaddr"], 16)
        for frame_offset in range(block["frames"]):
            for word_offset in range(block["words"]):
                geometry_by_far_word.setdefault(
                    (baseaddr + frame_offset, block["offset"] + word_offset),
                    [],
                ).append((tile_name, tile["type"], frame_offset, word_offset))

    accounting_by_pair: dict[frozenset[str], dict[str, Any]] = {}
    partition_ok = True
    computed_fp = 0
    for index, accounting in enumerate(certificate["pair_accounting"]):
        pair_key = frozenset(accounting["specimen_ids"])
        if pair_key in accounting_by_pair:
            errors.append(f"pair_accounting[{index}] duplicates an endpoint pair")
        accounting_by_pair[pair_key] = accounting
        pair_scope = pair_scopes.get(pair_key, set())
        pair_specimens = [specimen_by_id.get(specimen_id) for specimen_id in pair_key]
        if len(pair_key) != 2 or any(item is None for item in pair_specimens):
            errors.append(f"pair_accounting[{index}] names an unknown or malformed endpoint pair")
            asserted_tiles: set[str] = set()
        else:
            asserted_tiles = {item["tile"] for item in pair_specimens if item is not None}

        union: set[tuple[str, int, int]] = set()
        disjoint = True
        for bucket in GROUP_BUCKETS:
            values = [address_key(item) for item in accounting["buckets"][bucket]]
            value_set = set(values)
            if len(value_set) != len(values):
                errors.append(f"pair_accounting[{index}].{bucket} duplicates a bit")
                disjoint = False
            overlap = union & value_set
            if overlap:
                errors.append(f"pair_accounting[{index}] bucket overlap at {sorted(overlap)[:1]}")
                disjoint = False
            union |= value_set
            if accounting["counts"][bucket] != len(values):
                errors.append(f"pair_accounting[{index}].counts.{bucket} differs from bit list length")
                disjoint = False
        exact = disjoint and len(union) == accounting["raw_diff_bits"]
        if len(union) != accounting["raw_diff_bits"]:
            errors.append(f"pair_accounting[{index}] bucket union size differs from raw_diff_bits")
        if accounting["partition_exact"] != exact:
            errors.append(f"pair_accounting[{index}].partition_exact summary is wrong")
        partition_ok = partition_ok and exact

        for recorded_bucket in GROUP_BUCKETS:
            for bit_record in accounting["buckets"][recorded_bucket]:
                address = address_key(bit_record)
                candidates = geometry_by_far_word.get((int(address[0], 16), address[1]), [])
                candidate_dbs: set[str] = set()
                claims: list[tuple[str, str, str]] = []
                for tile_name, tile_type, frame_offset, word_offset in candidates:
                    rule_file = f"prjxray/zynq7/segbits_{tile_type.lower()}.db"
                    record = manifest_files.get(rule_file)
                    if (
                        record is None
                        or record.get("role") != "segbits"
                        or not record.get("classified", False)
                        or rule_file.endswith(".origin_info.db")
                    ):
                        continue
                    candidate_dbs.add(rule_file)
                    coordinate = frame_offset, word_offset * 32 + address[2]
                    try:
                        for claiming_feature in load_coordinate_claims(rule_file).get(coordinate, set()):
                            claims.append((tile_name, rule_file, claiming_feature))
                    except (OSError, ValueError) as exc:
                        errors.append(f"pair_accounting[{index}] cannot read {rule_file}: {exc}")
                claiming_dbs = {rule_file for _, rule_file, _ in claims}
                if address in pair_scope:
                    expected_bucket = "in_scope"
                elif address[1] == 50 and 0 <= address[2] <= 12:
                    expected_bucket = "frame_ecc"
                elif claims:
                    expected_bucket = "db_attributed"
                elif candidates:
                    expected_bucket = "ownership_unknown"
                else:
                    expected_bucket = "unattributed"
                if recorded_bucket != expected_bucket:
                    errors.append(
                        f"pair_accounting[{index}] bit {address} is labelled {recorded_bucket} "
                        f"but frozen geometry/DB evidence requires {expected_bucket}"
                    )
                if expected_bucket == "db_attributed" and not (claiming_dbs & pinned_paths):
                    errors.append(
                        f"pair_accounting[{index}] db_attributed bit {address} consumes no pinned claiming DB"
                    )
                if expected_bucket == "ownership_unknown" and candidate_dbs - pinned_paths:
                    errors.append(
                        f"pair_accounting[{index}] ownership_unknown bit {address} lacks pinned candidate "
                        f"DBs {sorted(candidate_dbs - pinned_paths)}"
                    )

                if expected_bucket in {"ownership_unknown", "unattributed"}:
                    computed_fp += 1
                elif expected_bucket == "db_attributed" and address not in pair_scope:
                    same_class_asserted_claim = any(
                        tile_name in asserted_tiles
                        and feature_pattern is not None
                        and feature_pattern.fullmatch(claiming_feature) is not None
                        for tile_name, _rule_file, claiming_feature in claims
                    )
                    if same_class_asserted_claim:
                        computed_fp += 1

    accounting_complete = set(accounting_by_pair) == set(pair_scopes)
    if not accounting_complete:
        missing = set(pair_scopes) - set(accounting_by_pair)
        extra = set(accounting_by_pair) - set(pair_scopes)
        errors.append(
            "pair_accounting endpoint-pair completeness mismatch "
            f"(missing={len(missing)} extra={len(extra)})"
        )

    coverage = class_record["coverage"]
    asserted_entries = actual_mine_features | actual_holdout_features
    if coverage["attested_count"] != len(asserted_entries):
        errors.append("coverage.attested_count differs from distinct asserted class entries")
    if coverage["class_entry_count"] != current_entries:
        errors.append("coverage.class_entry_count differs from current manifest")
    computed_accounting = {
        "tp_count": computed_tp,
        "fp_count": computed_fp,
        "fn_count": computed_fn,
    }
    recorded_accounting = {
        field: class_record["accounting"][field] for field in computed_accounting
    }
    if recorded_accounting != computed_accounting:
        errors.append(
            f"accounting mismatch (recorded={recorded_accounting} computed={computed_accounting})"
        )
    if class_record["semantic_accounting"] != semantic_counts:
        errors.append(
            "semantic_accounting mismatch "
            f"(recorded={class_record['semantic_accounting']} computed={semantic_counts})"
        )

    criterion_passed = (
        completeness_ok
        and accounting_complete
        and partition_ok
        and computed_fn == 0
        and computed_fp == 0
        and computed_tp == len(committed_holdout_keys)
    )
    expected_status = "passed" if criterion_passed else "failed"
    if certificate["status"] != expected_status:
        errors.append(
            f"status={certificate['status']} but {certificate['schema_version']} feature evidence "
            f"requires {expected_status}"
        )
    semantic_passed = semantic_counts["member_identity"]["fail_count"] == 0
    expected_semantic_status = "passed" if semantic_passed else "failed"
    if certificate["semantic_status"] != expected_semantic_status:
        errors.append(
            f"semantic_status={certificate['semantic_status']} but semantic evidence requires "
            f"{expected_semantic_status}"
        )
    return errors


def semantic_errors(
    certificate: dict[str, Any],
    repo_root: Path,
    require_production: bool = False,
) -> list[str]:
    if certificate.get("evidence_model") == "group":
        return group_semantic_errors(certificate, repo_root, require_production)

    version = tuple(int(part) for part in certificate["schema_version"].split("."))
    if version >= (1, 4, 0):
        return feature_1_4_semantic_errors(certificate, repo_root, require_production)

    errors: list[str] = []
    data_dir = repo_root / "data"
    manifest = load_json(data_dir / "MANIFEST.json")
    spec = load_json(data_dir / "subset_spec.json")
    tilegrid = load_json(data_dir / "prjxray/zynq7/xc7z010/tilegrid.json")

    profile = certificate.get("profile")
    if require_production and profile != "production":
        errors.append("production verification requires profile='production'")
    if profile == "production" and version < (1, 1, 0):
        errors.append("the production profile requires certificate schema_version >= 1.1.0")
    if require_production and version < (1, 2, 0):
        errors.append("current production verification requires certificate schema_version >= 1.2.0")
    lifecycle_profile = profile == "production" and version >= (1, 2, 0)

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

    committed_by_key: dict[PredictionKey, dict[str, Any]] = {}
    committed_holdout_keys: set[PredictionKey] = set()
    if lifecycle_profile:
        commitment_errors, committed_by_key, committed_holdout_keys = load_prediction_commitment(
            certificate,
            repo_root,
        )
        errors.extend(commitment_errors)

    specimens = certificate["specimens"]
    specimen_by_id: dict[str, dict[str, Any]] = {}
    specimen_attestations: dict[str, dict[str, Any]] = {}
    attestation_cache: dict[tuple[str, str], dict[str, Any]] = {}
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
        attestation_ref = specimen.get("attestation")
        if attestation_ref is not None:
            cache_key = (attestation_ref["path"], attestation_ref["sha256"])
            attestation = attestation_cache.get(cache_key)
            if attestation is None:
                try:
                    attestation_path = safe_child(repo_root, attestation_ref["path"])
                    if not attestation_path.is_file():
                        raise ValueError(f"attestation file does not exist: {attestation_ref['path']}")
                    actual_hash = hash_file(attestation_path)
                    if actual_hash != attestation_ref["sha256"]:
                        raise ValueError(
                            f"attestation hash mismatch (pinned={attestation_ref['sha256']} actual={actual_hash})"
                        )
                    attestation = load_json(attestation_path)
                    external_findings = validate_external_schema(
                        attestation,
                        repo_root / "schemas/specimen_attestation.schema.json",
                        f"specimen {specimen_id} attestation",
                    )
                    errors.extend(external_findings)
                    if external_findings:
                        attestation = None
                    else:
                        attestation_cache[cache_key] = attestation
                except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                    errors.append(f"specimen {specimen_id}: cannot validate attestation: {exc}")
                    attestation = None
            if attestation is not None:
                specimen_attestations[specimen_id] = attestation
                if attestation["schema_version"] != attestation_ref["schema_version"]:
                    errors.append(f"specimen {specimen_id}: pinned attestation schema_version differs from file")
                if attestation["resolved"]["resolved_loc"] != specimen["loc_site"]:
                    errors.append(f"specimen {specimen_id}: attested resolved_loc differs from loc_site")
                if attestation["resolved"]["tile"] != specimen["tile"]:
                    errors.append(f"specimen {specimen_id}: attested tile differs from specimen tile")
                if attestation["inputs"]["part"] != specimen["part"]:
                    errors.append(f"specimen {specimen_id}: attested input part differs from specimen part")
                if specimen["bitstream_sha256"] not in attestation["outputs"].values():
                    errors.append(f"specimen {specimen_id}: bitstream_sha256 is absent from attestation outputs")

    results = certificate["feature_results"]
    result_by_key: dict[str | PredictionKey, dict[str, Any]] = {}
    actual_mine_features: set[str] = set()
    actual_holdout_features: set[str] = set()
    actual_holdout_keys: set[PredictionKey] = set()
    used_specimens: set[str] = set()
    computed_tp = 0
    computed_fn = 0
    computed_fp = 0
    for result in results:
        feature = result["feature"]
        if lifecycle_profile:
            prediction_key: str | PredictionKey = result["prediction_specimen_id"], feature
        else:
            prediction_key = feature
        if prediction_key in result_by_key:
            errors.append(f"duplicate feature result key {prediction_key!r}")
        result_by_key[prediction_key] = result

        committed_prediction = (
            committed_by_key.get(prediction_key)
            if lifecycle_profile and isinstance(prediction_key, tuple)
            else None
        )
        if lifecycle_profile:
            expected_split = committed_prediction["split"] if committed_prediction is not None else None
            if committed_prediction is None:
                errors.append(f"feature result key {prediction_key!r} is absent from prediction commitment")
            else:
                recorded_prediction = {
                    "specimen_id": result["prediction_specimen_id"],
                    "feature": feature,
                    "split": result["split"],
                    "rule_file": result["rule_file"],
                    "predicted_assignments": result["predicted_assignments"],
                    "expected_transition": result["expected_transition"],
                }
                if recorded_prediction != committed_prediction:
                    errors.append(
                        f"feature result key {prediction_key!r} differs from preregistered prediction"
                    )
        else:
            expected_split = "mine" if feature in mine_set else "holdout" if feature in holdout_set else None
        if expected_split is None:
            if not lifecycle_profile:
                errors.append(f"feature result is absent from split membership: {feature}")
        elif result["split"] != expected_split:
            errors.append(f"feature {feature}: result split disagrees with membership")
        if result["split"] == "mine":
            actual_mine_features.add(feature)
        else:
            actual_holdout_features.add(feature)
            if lifecycle_profile and isinstance(prediction_key, tuple):
                actual_holdout_keys.add(prediction_key)

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
        if class_record["id"] == "clb_lut_init":
            for specimen_id in (result["baseline_specimen_id"], result["feature_specimen_id"]):
                attestation = specimen_attestations.get(specimen_id)
                if attestation is not None and not attestation["resolved"]["pin_mapping_is_identity"]:
                    errors.append(
                        f"feature {feature}: specimen {specimen_id} does not attest identity LUT pin mapping"
                    )

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
                        recorded_tokens = [item.get("token") for item in result["predicted_assignments"]]
                        if any(token is not None for token in recorded_tokens) and recorded_tokens != payload:
                            errors.append(f"feature {feature}: token sequence differs from frozen rule text")
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

        excluded: dict[tuple[str, int, int], tuple[int, int]] = {}
        if "exclusion_rules" in result:
            rules = result["exclusion_rules"]
            rule_keys = {(item["reason"], item["rule"]) for item in rules}
            supported_rule = ("frame_ecc", "word == 50 and 0 <= bit <= 12")
            if rule_keys != {supported_rule} or len(rules) != 1:
                errors.append(f"feature {feature}: exclusion_rules must contain exactly the supported frame_ecc rule")
            for item in result["excluded_diff"]:
                key = address_key(item["address"])
                transition = item["before_value"], item["after_value"]
                if key in excluded:
                    errors.append(f"feature {feature}: duplicate excluded diff address {key}")
                if transition[0] == transition[1]:
                    errors.append(f"feature {feature}: excluded diff address {key} did not change")
                if (item["reason"], item["rule"]) not in rule_keys:
                    errors.append(f"feature {feature}: excluded diff at {key} cites no declared rule")
                if key[1] != 50 or not 0 <= key[2] <= 12:
                    errors.append(f"feature {feature}: excluded diff at {key} does not satisfy frame_ecc rule")
                if key in diff:
                    errors.append(f"feature {feature}: address {key} is both observed and excluded")
                if key in predicted:
                    errors.append(f"feature {feature}: predicted address {key} cannot be excluded")
                excluded[key] = transition
            for key in diff:
                if key[1] == 50 and 0 <= key[2] <= 12:
                    errors.append(f"feature {feature}: ECC-shaped observed diff at {key} must be excluded")
            observed_frames = {
                key[0] for key in diff if not (key[1] == 50 and 0 <= key[2] <= 12)
            }
            for key in excluded:
                if key[0] not in observed_frames:
                    errors.append(f"feature {feature}: excluded ECC-only frame {key[0]} has no observed diff")

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

    if lifecycle_profile:
        if actual_mine_features != mine_set or actual_holdout_features != holdout_set:
            errors.append("feature_results split projections differ from declared feature membership")
        if actual_holdout_keys != committed_holdout_keys:
            missing = sorted(committed_holdout_keys - actual_holdout_keys)
            extra = sorted(actual_holdout_keys - committed_holdout_keys)
            errors.append(
                "holdout prediction completeness mismatch "
                f"(missing={len(missing)} {missing[:1]} extra={len(extra)} {extra[:1]})"
            )
    else:
        actual_features = set(result_by_key)
        if actual_features != expected_features:
            missing = sorted(expected_features - actual_features)
            extra = sorted(actual_features - expected_features)
            errors.append(f"feature_results membership mismatch (missing={missing[:1]} extra={extra[:1]})")
    if used_specimens != set(specimen_by_id):
        errors.append("specimens must be referenced by at least one feature result")

    coverage = class_record["coverage"]
    expected_attested_count = len(results) if lifecycle_profile else len(expected_features)
    if coverage["attested_count"] != expected_attested_count:
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

    holdout_count = len(committed_holdout_keys) if lifecycle_profile else len(holdout)
    criterion_passed = computed_tp == holdout_count and computed_fn == 0 and computed_fp == 0
    expected_status = "passed" if criterion_passed else "failed"
    if certificate["status"] != expected_status:
        errors.append(
            f"status={certificate['status']} but holdout evidence requires {expected_status}"
        )
    return errors


def verify(
    certificate_path: Path,
    repo_root: Path,
    schema_path: Path,
    require_production: bool = False,
) -> list[str]:
    try:
        certificate = load_json(certificate_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]
    errors = schema_errors(certificate, schema_path)
    if errors:
        return errors
    try:
        errors.extend(semantic_errors(certificate, repo_root, require_production))
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
    parser.add_argument(
        "--require-production",
        action="store_true",
        help="reject certificates that do not claim and satisfy the production profile",
    )
    args = parser.parse_args()
    errors = verify(
        args.certificate.resolve(),
        repo_root,
        args.schema.resolve(),
        args.require_production,
    )
    if errors:
        print(f"CERTIFICATE VERIFY: FAIL — {len(errors)} finding(s)", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    certificate = load_json(args.certificate)
    if certificate.get("evidence_model") == "group":
        address = certificate["bit_class"]["address_accounting"]
        semantic = certificate["bit_class"]["semantic_accounting"]["member_identity"]
        address_pass = sum(item["pass_count"] for item in address.values())
        address_fail = sum(item["fail_count"] for item in address.values())
        version = tuple(int(part) for part in certificate["schema_version"].split("."))
        diagnostic_text = ""
        if version >= (1, 4, 0):
            diagnostics = certificate["bit_class"]["diagnostic_accounting"]
            exclusivity = diagnostics["group_exclusivity"]
            decode = diagnostics["decode_validity"]
            diagnostic_text = (
                f"vacuous={exclusivity['vacuous_count']} "
                f"ambiguity={exclusivity['ambiguity_count']} "
                f"decode_validity_pass={decode['pass_count']} "
                f"decode_validity_fail={decode['fail_count']} "
            )
        if certificate["status"] == "failed" and not args.allow_failed:
            print(
                "CERTIFICATE VERIFY: CERTIFICATION FAILED — "
                f"address_pass={address_pass} address_fail={address_fail} "
                f"{diagnostic_text}"
                f"semantic_status={certificate['semantic_status']} "
                f"semantic_pass={semantic['pass_count']} semantic_fail={semantic['fail_count']}",
                file=sys.stderr,
            )
            return 2
        print(
            f"CERTIFICATE VERIFY: OK — status={certificate['status']} "
            f"address_pass={address_pass} address_fail={address_fail} "
            f"{diagnostic_text}"
            f"semantic_status={certificate['semantic_status']} "
            f"semantic_pass={semantic['pass_count']} semantic_fail={semantic['fail_count']}"
        )
        return 0
    accounting = certificate["bit_class"]["accounting"]
    version = tuple(int(part) for part in certificate["schema_version"].split("."))
    semantic_text = ""
    if version >= (1, 4, 0):
        semantic = certificate["bit_class"]["semantic_accounting"]["member_identity"]
        semantic_text = (
            f" semantic_status={certificate['semantic_status']}"
            f" semantic_pass={semantic['pass_count']} semantic_fail={semantic['fail_count']}"
        )
    if certificate["status"] == "failed" and not args.allow_failed:
        print(
            "CERTIFICATE VERIFY: CERTIFICATION FAILED — "
            f"tp={accounting['tp_count']} fp={accounting['fp_count']} fn={accounting['fn_count']}"
            f"{semantic_text}",
            file=sys.stderr,
        )
        return 2
    print(
        f"CERTIFICATE VERIFY: OK — status={certificate['status']} "
        f"tp={accounting['tp_count']} fp={accounting['fp_count']} fn={accounting['fn_count']}"
        f"{semantic_text}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

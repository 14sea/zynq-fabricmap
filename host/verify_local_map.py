#!/usr/bin/env python3
"""Independently verify a certificate-inherited ``local_map`` 1.0.0.

This is consumer-owned code.  It deliberately does not import, invoke, or copy the
producer's ``scripts/build_local_map.py``.  The map is checked by deriving its complete
meaning again from the production certificate and frozen-data manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover - an incomplete host is a refusal in main()
    Draft202012Validator = None  # type: ignore[assignment]
    FormatChecker = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = REPO_ROOT / "schemas/local_map.schema.json"
CERTIFICATE_SCHEMA = REPO_ROOT / "schemas/certificate.schema.json"
INIT_FEATURE_RE = re.compile(
    r"^(?P<lut>.+\.[ABCD]LUT)\.INIT\[(?P<index>[0-9]{2})\]$"
)
FAR_RE = re.compile(r"0x[0-9A-F]{8}")
ECC_RULE_RE = re.compile(r"word == ([0-9]+) and ([0-9]+) <= bit <= ([0-9]+)")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_object(data: bytes, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [f"{label}: not valid UTF-8 JSON: {exc}"]
    if not isinstance(value, dict):
        return None, [f"{label}: top-level JSON must be an object"]
    return value, []


def safe_child(root: Path, relative: object, label: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError(f"{label}: not a repository-relative path: {relative!r}")
    candidate = (root / relative).resolve()
    resolved_root = root.resolve()
    if candidate == resolved_root or resolved_root not in candidate.parents:
        raise ValueError(f"{label}: path escapes the repository: {relative!r}")
    return candidate


def schema_problems(document: dict[str, Any], schema_path: Path = SCHEMA) -> list[str]:
    if Draft202012Validator is None:
        return ["Python package 'jsonschema' is required for local_map validation"]
    try:
        schema = json.loads(schema_path.read_bytes())
        Draft202012Validator.check_schema(schema)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return [f"local_map schema could not be loaded: {exc}"]
    out: list[str] = []
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        out.append(f"local_map schema {location}: {error.message}")
    return out


def canonical_address(address: object, label: str) -> tuple[str, int, int] | None:
    if not isinstance(address, dict):
        return None
    far, word, bit = address.get("far"), address.get("word"), address.get("bit")
    if not isinstance(far, str) or FAR_RE.fullmatch(far) is None:
        return None
    if not isinstance(word, int) or isinstance(word, bool) or not 0 <= word <= 100:
        return None
    if not isinstance(bit, int) or isinstance(bit, bool) or not 0 <= bit <= 31:
        return None
    return far, word, bit


def address_key(address: tuple[str, int, int]) -> str:
    return f"{address[0]}/{address[1]}/{address[2]}"


def derive_certificate(
    certificate: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    """Derive the unique writable universe and collateral rule from certificate facts."""

    problems: list[str] = []
    results = certificate.get("feature_results")
    if not isinstance(results, list) or not results:
        return [], {}, ["certificate has no non-empty feature_results array"]

    by_feature: dict[str, dict[str, Any]] = {}
    by_address: dict[str, str] = {}
    ecc_rules: set[tuple[str, str]] = set()

    for result_index, result in enumerate(results):
        label = f"certificate feature_results[{result_index}]"
        if not isinstance(result, dict):
            problems.append(f"{label}: not an object")
            continue
        feature = result.get("feature")
        if not isinstance(feature, str) or not feature:
            problems.append(f"{label}: feature is not a non-empty string")
            continue
        match = INIT_FEATURE_RE.fullmatch(feature)
        if match is None or not 0 <= int(match.group("index")) <= 63:
            problems.append(f"{label}: {feature!r} is not a canonical LUT INIT[00..63] feature")
            continue
        if result.get("verdict") != "matched":
            problems.append(f"{label}: verdict is not 'matched'")

        predicted = result.get("predicted_assignments")
        observed = result.get("observed_assignments")
        if not isinstance(predicted, list) or len(predicted) != 1:
            problems.append(f"{label}: expected exactly one predicted assignment")
            continue
        if not isinstance(observed, list) or len(observed) != 1:
            problems.append(f"{label}: expected exactly one observed assignment")
            continue
        assignment = predicted[0]
        observation = observed[0]
        if not isinstance(assignment, dict) or not isinstance(observation, dict):
            problems.append(f"{label}: assignment records must be objects")
            continue
        address = canonical_address(assignment.get("address"), label)
        observed_address = canonical_address(observation.get("address"), label)
        if address is None or observed_address is None:
            problems.append(f"{label}: assignment address is not canonical")
            continue
        if observed_address != address:
            problems.append(f"{label}: predicted and observed addresses differ")

        segbit = assignment.get("segbit")
        if not isinstance(segbit, dict) or not isinstance(segbit.get("negated"), bool):
            problems.append(f"{label}: segbit.negated is not a boolean")
            continue
        expected_value = 0 if segbit["negated"] else 1
        if assignment.get("expected_value") != expected_value:
            problems.append(
                f"{label}: expected_value does not match segbit.negated polarity"
            )
        token = assignment.get("token")
        if not isinstance(token, str) or token.startswith("!") != segbit["negated"]:
            problems.append(f"{label}: token spelling disagrees with segbit.negated")
        if observation.get("observed_value") != expected_value:
            problems.append(f"{label}: observed value does not match certified polarity")

        key = address_key(address)
        entry = {
            "key": key,
            "far": address[0],
            "word": address[1],
            "bit": address[2],
            "feature": feature,
            "expected_value": expected_value,
            "split": result.get("split"),
            "rule_file": result.get("rule_file"),
        }
        if entry["split"] not in {"mine", "holdout"}:
            problems.append(f"{label}: split is neither mine nor holdout")
        if not isinstance(entry["rule_file"], str) or not entry["rule_file"]:
            problems.append(f"{label}: rule_file is not a non-empty string")

        previous = by_feature.setdefault(feature, entry)
        if previous != entry:
            problems.append(f"{label}: re-attestation disagrees for feature {feature}")
        owner = by_address.setdefault(key, feature)
        if owner != feature:
            problems.append(f"{label}: address {key} is also claimed by {owner}")

        rules = [
            rule
            for rule in result.get("exclusion_rules", [])
            if isinstance(rule, dict) and rule.get("reason") == "frame_ecc"
        ]
        if len(rules) != 1:
            problems.append(f"{label}: expected exactly one frame_ecc exclusion rule")
        else:
            rule_text, why = rules[0].get("rule"), rules[0].get("why")
            if not isinstance(rule_text, str) or not isinstance(why, str) or not why:
                problems.append(f"{label}: incomplete frame_ecc exclusion rule")
            else:
                ecc_rules.add((rule_text, why))

    if len(ecc_rules) != 1:
        problems.append(
            f"certificate has {len(ecc_rules)} distinct frame_ecc rules; expected exactly one"
        )
        collateral: dict[str, Any] = {}
    else:
        rule_text, why = next(iter(ecc_rules))
        match = ECC_RULE_RE.fullmatch(rule_text)
        if match is None:
            problems.append(f"certificate frame_ecc rule is not expressible: {rule_text!r}")
            collateral = {}
        else:
            word, low, high = (int(part) for part in match.groups())
            if word > 100 or low > high or high > 31:
                problems.append(f"certificate frame_ecc rule is outside a frame: {rule_text!r}")
            collateral = {
                "rule": rule_text,
                "word": word,
                "bit_low": low,
                "bit_high": high,
                "why": why,
                "scope": "touched_frames_only",
            }

    addresses = sorted(by_feature.values(), key=lambda item: (item["far"], item["word"], item["bit"]))
    return addresses, collateral, problems


def derive_indexes(addresses: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    by_far: dict[str, list[str]] = {}
    by_lut: dict[str, list[dict[str, Any]]] = {}
    for entry in addresses:
        by_far.setdefault(entry["far"], []).append(entry["key"])
        match = INIT_FEATURE_RE.fullmatch(entry["feature"])
        if match is None:
            problems.append(f"cannot index non-LUT feature {entry['feature']!r}")
            continue
        by_lut.setdefault(match.group("lut"), []).append(
            {"init_index": int(match.group("index")), "address_key": entry["key"]}
        )
    for far in by_far:
        by_far[far].sort()
    for lut, bits in by_lut.items():
        bits.sort(key=lambda item: item["init_index"])
        indices = [item["init_index"] for item in bits]
        if len(indices) != len(set(indices)):
            problems.append(f"{lut}: duplicate INIT indices")
    return {
        "by_far": {far: by_far[far] for far in sorted(by_far)},
        "by_lut": {lut: by_lut[lut] for lut in sorted(by_lut)},
    }, problems


def relationship_problems(
    local_map: dict[str, Any],
    certificate: dict[str, Any],
    manifest: dict[str, Any],
    *,
    certificate_sha256: str,
    manifest_sha256: str,
) -> list[str]:
    """Check map meaning after all three documents have passed their own schemas."""

    problems: list[str] = []
    provenance = local_map["provenance"]
    cert_ref = provenance["certificate"]
    frozen_ref = provenance["frozen_data"]

    if cert_ref["sha256"] != certificate_sha256:
        problems.append("certificate bytes do not match the hash pinned by the map")
    if frozen_ref["sha256"] != manifest_sha256:
        problems.append("frozen manifest bytes do not match the hash pinned by the map")
    for field in ("schema_version", "certificate_id", "status", "profile"):
        if cert_ref[field] != certificate.get(field):
            problems.append(f"map certificate.{field} differs from the certificate")
    if certificate.get("status") != "passed":
        problems.append("source certificate status is not passed")
    if certificate.get("profile") != "production":
        problems.append("source certificate profile is not production")

    cert_class = certificate.get("bit_class")
    if not isinstance(cert_class, dict):
        return problems + ["certificate bit_class is not an object"]
    for field in ("id", "tier"):
        if local_map["bit_class"][field] != cert_class.get(field):
            problems.append(f"map bit_class.{field} differs from the certificate")
    if cert_ref["bit_class_id"] != cert_class.get("id"):
        problems.append("map provenance bit_class_id differs from the certificate")
    if local_map["target"] != certificate.get("target"):
        problems.append("map target differs from the certificate")
    manifest_target = manifest.get("target")
    if not isinstance(manifest_target, dict) or any(
        local_map["target"].get(field) != manifest_target.get(field)
        for field in ("family", "device", "part")
    ):
        problems.append("map target differs from the frozen manifest")
    if frozen_ref["freeze_stamp"] != manifest.get("freeze_stamp"):
        problems.append("map freeze_stamp differs from the frozen manifest")
    frozen_inputs = certificate.get("frozen_inputs")
    if not isinstance(frozen_inputs, dict):
        problems.append("certificate frozen_inputs is not an object")
    else:
        if frozen_inputs.get("manifest_schema_version") != manifest.get("schema_version"):
            problems.append("certificate and map manifest schema versions differ")
        if frozen_inputs.get("freeze_stamp") != manifest.get("freeze_stamp"):
            problems.append("certificate and map manifest freeze stamps differ")
        certificate_spec = frozen_inputs.get("spec")
        manifest_spec = manifest.get("spec")
        if not isinstance(certificate_spec, dict) or not isinstance(manifest_spec, dict) or any(
            certificate_spec.get(field) != manifest_spec.get(field)
            for field in ("path", "sha256")
        ):
            problems.append("certificate and map manifest pin different frozen subset specs")

    manifest_classes = manifest.get("bit_classes")
    classes = [
        item for item in manifest_classes or []
        if isinstance(item, dict) and item.get("id") == cert_class.get("id")
    ]
    if len(classes) != 1:
        problems.append("frozen manifest does not contain exactly one matching bit class")
    else:
        frozen_class = classes[0]
        if local_map["bit_class"]["tier"] != frozen_class.get("tier"):
            problems.append("map bit-class tier differs from frozen manifest")
        if local_map["bit_class"]["class_entry_count"] != frozen_class.get("entries"):
            problems.append("map class_entry_count differs from frozen manifest")

    addresses, collateral, derived_problems = derive_certificate(certificate)
    problems.extend(derived_problems)
    indexes, index_problems = derive_indexes(addresses)
    problems.extend(index_problems)
    universe = local_map["universe"]
    if universe["addresses"] != addresses:
        problems.append("map universe is not exactly the certificate-attested universe")
    if universe["address_count"] != len(addresses):
        problems.append("map universe.address_count differs from the derived universe")
    if universe["far_count"] != len({item["far"] for item in addresses}):
        problems.append("map universe.far_count differs from the derived universe")
    if universe["words"] != sorted({item["word"] for item in addresses}):
        problems.append("map universe.words differs from the derived universe")
    if local_map["bit_class"]["attested_count"] != len(addresses):
        problems.append("map attested_count differs from distinct certificate-attested addresses")
    if local_map["index"] != indexes:
        problems.append("map indexes are not the exact by_far/by_lut re-indexing")
    if local_map["collateral"].get("frame_ecc") != collateral:
        problems.append("map frame_ecc collateral differs from the certificate exclusion rule")
    return problems


def verify_path(
    map_path: Path,
    repo_root: Path = REPO_ROOT,
    *,
    certificate_checker: Callable[[Path], list[str]] | None = None,
    manifest_checker: Callable[[Path], list[str]] | None = None,
) -> list[str]:
    try:
        map_bytes = map_path.read_bytes()
    except OSError as exc:
        return [f"local_map could not be read: {exc}"]
    local_map, problems = parse_object(map_bytes, "local_map")
    if local_map is None:
        return problems
    problems.extend(schema_problems(local_map, repo_root / "schemas/local_map.schema.json"))
    if problems:
        return problems

    try:
        cert_path = safe_child(repo_root, local_map["provenance"]["certificate"]["path"], "certificate")
        manifest_path = safe_child(repo_root, local_map["provenance"]["frozen_data"]["path"], "frozen manifest")
        cert_bytes = cert_path.read_bytes()
        manifest_bytes = manifest_path.read_bytes()
    except (OSError, ValueError) as exc:
        return [str(exc)]
    certificate, cert_parse = parse_object(cert_bytes, "certificate")
    manifest, manifest_parse = parse_object(manifest_bytes, "frozen manifest")
    problems.extend(cert_parse)
    problems.extend(manifest_parse)
    if certificate is None or manifest is None:
        return problems

    if certificate_checker is None:
        host_dir = str((repo_root / "host").resolve())
        if host_dir not in sys.path:
            sys.path.insert(0, host_dir)
        import verify_certificate  # type: ignore

        certificate_checker = lambda path: verify_certificate.verify(
            path,
            repo_root,
            repo_root / "schemas/certificate.schema.json",
            True,
        )
    if manifest_checker is None:
        host_dir = str((repo_root / "host").resolve())
        if host_dir not in sys.path:
            sys.path.insert(0, host_dir)
        import verify_data  # type: ignore

        manifest_checker = lambda path: verify_data.verify(repo_root / "data", path)
    for finding in certificate_checker(cert_path):
        problems.append(f"source certificate: {finding}")
    canonical_manifest = (repo_root / "data/MANIFEST.json").resolve()
    if manifest_path != canonical_manifest:
        problems.append(
            "frozen manifest path is not the repository authority data/MANIFEST.json"
        )
    for finding in manifest_checker(manifest_path):
        problems.append(f"frozen manifest: {finding}")
    if manifest.get("schema") != "frozen_db_subset":
        problems.append("frozen manifest schema is not frozen_db_subset")
    if problems:
        return problems
    return relationship_problems(
        local_map,
        certificate,
        manifest,
        certificate_sha256=sha256_bytes(cert_bytes),
        manifest_sha256=sha256_bytes(manifest_bytes),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "map",
        type=Path,
        nargs="?",
        default=REPO_ROOT / "maps/clb_lut_init_v1.local_map.json",
    )
    args = parser.parse_args()
    problems = verify_path(args.map.resolve())
    if problems:
        print(f"LOCAL MAP VERIFY: FAIL — {len(problems)} finding(s)", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    document = json.loads(args.map.read_bytes())
    print(
        "LOCAL MAP VERIFY: OK — "
        f"{document['universe']['address_count']} addresses, "
        f"{document['universe']['far_count']} frames, "
        f"{len(document['index']['by_lut'])} LUTs"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

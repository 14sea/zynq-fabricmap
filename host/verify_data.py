#!/usr/bin/env python3
"""Independent verifier for the frozen data contract.

This implementation is intentionally based only on docs/freeze_format.md,
data/subset_spec.json, and data/MANIFEST.json. It does not import or invoke the
producer-owned extractor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SUPPORTED_SPEC_MAJOR = 1
SUPPORTED_MANIFEST_MAJOR = 1


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    return value


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def major(version: object) -> int:
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError(f"invalid schema version {version!r}")
    return int(version.split(".", 1)[0])


def safe_child(parent: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError(f"invalid relative path {relative!r}")
    candidate = (parent / relative).resolve()
    resolved_parent = parent.resolve()
    if candidate != resolved_parent and resolved_parent not in candidate.parents:
        raise ValueError(f"path escapes data directory: {relative!r}")
    return candidate


def verify(data_dir: Path, manifest_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    manifest_path = manifest_path or data_dir / "MANIFEST.json"
    spec_path = data_dir / "subset_spec.json"

    try:
        spec = load_json(spec_path)
        manifest = load_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]

    try:
        if spec.get("schema") != "prjxray_subset_spec":
            errors.append(f"spec schema is {spec.get('schema')!r}, expected 'prjxray_subset_spec'")
        if major(spec.get("schema_version")) != SUPPORTED_SPEC_MAJOR:
            errors.append(f"unsupported spec schema version {spec.get('schema_version')!r}")
        if manifest.get("schema") != "frozen_db_subset":
            errors.append(f"manifest schema is {manifest.get('schema')!r}, expected 'frozen_db_subset'")
        if major(manifest.get("schema_version")) != SUPPORTED_MANIFEST_MAJOR:
            errors.append(f"unsupported manifest schema version {manifest.get('schema_version')!r}")
    except ValueError as exc:
        errors.append(str(exc))

    raw_spec = spec_path.read_bytes()
    pinned_spec = manifest.get("spec", {})
    if pinned_spec.get("path") != "data/subset_spec.json":
        errors.append(f"manifest spec.path is {pinned_spec.get('path')!r}")
    if pinned_spec.get("spec_id") != spec.get("spec_id"):
        errors.append("manifest spec_id does not match subset_spec.json")
    if pinned_spec.get("schema_version") != spec.get("schema_version"):
        errors.append("manifest spec schema_version does not match subset_spec.json")
    actual_spec_hash = sha256_bytes(raw_spec)
    if pinned_spec.get("sha256") != actual_spec_hash:
        errors.append(
            f"subset_spec.json sha256 mismatch: manifest={pinned_spec.get('sha256')} actual={actual_spec_hash}"
        )
    if manifest.get("target") != spec.get("target"):
        errors.append("manifest target does not match subset_spec.json")

    groups_value = spec.get("groups")
    classes_value = spec.get("bit_classes")
    files_value = manifest.get("files")
    manifest_classes_value = manifest.get("bit_classes")
    if not isinstance(groups_value, list) or not isinstance(classes_value, list):
        return errors + ["spec groups and bit_classes must be arrays"]
    if not isinstance(files_value, list) or not isinstance(manifest_classes_value, list):
        return errors + ["manifest files and bit_classes must be arrays"]

    groups: dict[str, dict[str, Any]] = {}
    source_to_group: dict[str, dict[str, Any]] = {}
    for group in groups_value:
        if not isinstance(group, dict) or not isinstance(group.get("id"), str):
            errors.append("invalid group record in spec")
            continue
        group_id = group["id"]
        if group_id in groups:
            errors.append(f"duplicate group id {group_id!r}")
        groups[group_id] = group
        for source_path in group.get("files", []):
            if source_path in source_to_group:
                errors.append(f"source file belongs to multiple groups: {source_path}")
            source_to_group[source_path] = group

    compiled_classes: list[tuple[dict[str, Any], re.Pattern[str]]] = []
    class_ids: set[str] = set()
    for bit_class in classes_value:
        try:
            class_id = bit_class["id"]
            if class_id in class_ids:
                errors.append(f"duplicate bit class id {class_id!r}")
            class_ids.add(class_id)
            compiled_classes.append((bit_class, re.compile(bit_class["feature_regex"])))
        except (KeyError, TypeError, re.error) as exc:
            errors.append(f"invalid bit class record: {exc}")

    listed_paths: set[str] = set()
    class_counts: Counter[str] = Counter()
    class_features: dict[str, set[str]] = defaultdict(set)
    classified_features = 0
    provenance_features = 0
    total_bytes = 0
    unclassified: list[str] = []
    ambiguous: list[str] = []

    for record in files_value:
        if not isinstance(record, dict):
            errors.append("non-object file record in manifest")
            continue
        relative = record.get("path")
        if not isinstance(relative, str):
            errors.append("file record has no string path")
            continue
        if relative in listed_paths:
            errors.append(f"duplicate manifest file path {relative}")
            continue
        listed_paths.add(relative)
        try:
            path = safe_child(data_dir, relative)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not path.is_file():
            errors.append(f"missing frozen file: {relative}")
            continue

        raw = path.read_bytes()
        total_bytes += len(raw)
        actual_hash = sha256_bytes(raw)
        if record.get("sha256") != actual_hash:
            errors.append(f"{relative}: sha256 mismatch (manifest={record.get('sha256')} actual={actual_hash})")
        if record.get("size_bytes") != len(raw):
            errors.append(f"{relative}: size mismatch (manifest={record.get('size_bytes')} actual={len(raw)})")

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"{relative}: not UTF-8: {exc}")
            continue
        lines = text.splitlines()
        if "lines" in record and record.get("lines") != len(lines):
            errors.append(f"{relative}: line count mismatch (manifest={record.get('lines')} actual={len(lines)})")

        source_path = record.get("source_path")
        group = source_to_group.get(source_path)
        if group is None:
            errors.append(f"{relative}: source_path {source_path!r} is not declared by the spec")
            continue
        for field in ("group", "role", "tier"):
            expected = group["id"] if field == "group" else group.get(field)
            if record.get(field) != expected:
                errors.append(f"{relative}: {field}={record.get(field)!r}, expected {expected!r}")

        role = group.get("role")
        is_origin = isinstance(source_path, str) and source_path.endswith(".origin_info.db")
        expected_classified = role in {"segbits", "ppips"} and not is_origin
        is_db = isinstance(source_path, str) and source_path.endswith(".db")
        if is_db and record.get("classified") is not expected_classified:
            errors.append(
                f"{relative}: classified={record.get('classified')!r}, expected {expected_classified} from normative rule"
            )
        if not is_db and "classified" in record:
            errors.append(f"{relative}: classified is only defined for .db records")

        feature_count = 0
        per_file_counts: Counter[str] = Counter()
        if role in {"segbits", "ppips"}:
            for line_number, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                feature_count += 1
                feature = line.split()[0]
                if expected_classified:
                    matched = [
                        bit_class["id"]
                        for bit_class, regex in compiled_classes
                        if group["id"] in bit_class.get("from_groups", []) and regex.fullmatch(feature)
                    ]
                    if len(matched) == 0:
                        unclassified.append(f"{relative}:{line_number}:{feature}")
                    elif len(matched) > 1:
                        ambiguous.append(f"{relative}:{line_number}:{feature}:{','.join(matched)}")
                    else:
                        class_id = matched[0]
                        per_file_counts[class_id] += 1
                        class_counts[class_id] += 1
                        class_features[class_id].add(feature)
                        classified_features += 1
                elif is_origin:
                    provenance_features += 1
        elif role == "mask":
            for line_number, line in enumerate(lines, 1):
                if line and not re.fullmatch(r"bit [0-9]+_[0-9]+", line):
                    errors.append(f"{relative}:{line_number}: invalid mask line {line!r}")

        if "features" in record and record.get("features") != feature_count:
            errors.append(
                f"{relative}: feature count mismatch (manifest={record.get('features')} actual={feature_count})"
            )
        manifest_file_counts = record.get("bit_classes", {})
        if manifest_file_counts != dict(per_file_counts):
            errors.append(
                f"{relative}: bit_classes mismatch (manifest={manifest_file_counts} actual={dict(per_file_counts)})"
            )

    actual_paths = {
        path.relative_to(data_dir).as_posix()
        for path in (data_dir / "prjxray").rglob("*")
        if path.is_file()
    }
    for relative in sorted(actual_paths - listed_paths):
        errors.append(f"untracked frozen file: {relative}")
    for relative in sorted(listed_paths - actual_paths):
        errors.append(f"manifest path is not present under prjxray/: {relative}")

    if unclassified:
        errors.append(f"unclassified features: {len(unclassified)}; first={unclassified[0]}")
    if ambiguous:
        errors.append(f"ambiguously classified features: {len(ambiguous)}; first={ambiguous[0]}")
    if manifest.get("consistency", {}).get("unclassified_features") != len(unclassified):
        errors.append("manifest consistency.unclassified_features does not match independent recount")

    manifest_classes: dict[str, dict[str, Any]] = {
        entry.get("id"): entry for entry in manifest_classes_value if isinstance(entry, dict)
    }
    if set(manifest_classes) != class_ids:
        errors.append(
            f"manifest/spec class ids differ: manifest={sorted(manifest_classes)} spec={sorted(class_ids)}"
        )
    for bit_class, _ in compiled_classes:
        class_id = bit_class["id"]
        entry = manifest_classes.get(class_id, {})
        if entry.get("feature_regex") != bit_class.get("feature_regex"):
            errors.append(f"{class_id}: manifest feature_regex differs from spec")
        if entry.get("entries") != class_counts[class_id]:
            errors.append(
                f"{class_id}: entry count mismatch (manifest={entry.get('entries')} actual={class_counts[class_id]})"
            )
        distinct = len(class_features[class_id])
        if entry.get("distinct_features") != distinct:
            errors.append(
                f"{class_id}: distinct feature mismatch (manifest={entry.get('distinct_features')} actual={distinct})"
            )

    totals = manifest.get("totals", {})
    expected_totals = {
        "files": len(actual_paths),
        "bytes": total_bytes,
        "classified_features": classified_features,
        "provenance_features": provenance_features,
    }
    for field, actual in expected_totals.items():
        if totals.get(field) != actual:
            errors.append(f"totals.{field} mismatch (manifest={totals.get(field)} actual={actual})")

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=repo_root / "data")
    parser.add_argument("--manifest", type=Path, help="alternate manifest, useful for falsifier tests")
    args = parser.parse_args()

    errors = verify(args.data_dir.resolve(), args.manifest.resolve() if args.manifest else None)
    if errors:
        print(f"INDEPENDENT DATA VERIFY: FAIL — {len(errors)} finding(s)", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    manifest = load_json(args.manifest or args.data_dir / "MANIFEST.json")
    totals = manifest["totals"]
    print(
        "INDEPENDENT DATA VERIFY: OK — "
        f"{totals['files']} files, {totals['classified_features']} classified features, "
        f"{totals['provenance_features']} provenance features, unclassified=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

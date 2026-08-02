#!/usr/bin/env python3
"""Recompute known absolute addresses from frozen DB text and tilegrid.json."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"(!?)([0-9]+)_([0-9]+)")
SITE_RE = re.compile(r"SLICE_X([0-9]+)Y[0-9]+")
PREFIX_RE = re.compile(r"(SLICEL|SLICEM)_X([01])")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def safe_child(parent: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError(f"invalid database path {relative!r}")
    path = (parent / relative).resolve()
    resolved_parent = parent.resolve()
    if resolved_parent not in path.parents:
        raise ValueError(f"database path escapes frozen root: {relative}")
    return path


def address(block: dict[str, Any], frame_offset: int, bit_offset: int) -> dict[str, Any]:
    if not 0 <= frame_offset < block["frames"]:
        raise ValueError(f"frame offset {frame_offset} outside [0, {block['frames']})")
    if not 0 <= bit_offset < block["words"] * 32:
        raise ValueError(f"bit offset {bit_offset} outside tile's {block['words']} words")
    return {
        "far": f"0x{int(block['baseaddr'], 16) + frame_offset:08X}",
        "word": block["offset"] + bit_offset // 32,
        "bit": bit_offset % 32,
    }


def find_feature(path: Path, feature: str) -> list[str]:
    matches: list[list[str]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            fields = line.split()
            if fields and fields[0] == feature:
                matches.append(fields[1:])
    if len(matches) != 1:
        raise ValueError(f"{path}: expected one record for {feature!r}, found {len(matches)}")
    return matches[0]


def predicted_assignments(tokens: list[str], block: dict[str, Any]) -> list[dict[str, Any]]:
    assignments: list[dict[str, Any]] = []
    for token in tokens:
        match = TOKEN_RE.fullmatch(token)
        if match is None:
            raise ValueError(f"invalid segbit token {token!r}")
        negated = bool(match.group(1))
        frame_offset = int(match.group(2))
        bit_offset = int(match.group(3))
        assignments.append(
            {
                "token": token,
                "segbit": {
                    "frame_offset": frame_offset,
                    "bit_offset": bit_offset,
                    "negated": negated,
                },
                "address": address(block, frame_offset, bit_offset),
                "expected_value": 0 if negated else 1,
            }
        )
    return assignments


def feature_site(tile: dict[str, Any], feature: str) -> str | None:
    fields = feature.split(".")
    if len(fields) < 2:
        return None
    prefix = PREFIX_RE.fullmatch(fields[1])
    if prefix is None:
        return None
    expected_type, index_text = prefix.groups()
    indexed_sites: list[tuple[int, str, str]] = []
    for site, site_type in tile.get("sites", {}).items():
        match = SITE_RE.fullmatch(site)
        if match:
            indexed_sites.append((int(match.group(1)), site, site_type))
    indexed_sites.sort()
    index = int(index_text)
    if index >= len(indexed_sites):
        raise ValueError(f"feature prefix {fields[1]} has no corresponding site")
    _, site, site_type = indexed_sites[index]
    if site_type != expected_type:
        raise ValueError(f"feature prefix type {expected_type} disagrees with tile site {site}:{site_type}")
    return site


def verify(repo_root: Path, fixture_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        fixture = load_json(fixture_path)
        tilegrid = load_json(repo_root / "data/prjxray/zynq7/xc7z010/tilegrid.json")
        spec = load_json(repo_root / "data/subset_spec.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]

    if fixture.get("schema") != "address_known_answers" or fixture.get("schema_version") != "1.0.0":
        errors.append("fixture schema must be address_known_answers 1.0.0")
    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        return errors + ["fixture cases must be a nonempty array"]
    class_regex = {
        entry["id"]: re.compile(entry["feature_regex"])
        for entry in spec.get("bit_classes", [])
    }

    seen_ids: set[str] = set()
    for case in cases:
        case_id = case.get("id", "<missing-id>") if isinstance(case, dict) else "<non-object>"
        prefix = f"{case_id}: "
        if not isinstance(case, dict):
            errors.append(prefix + "case must be an object")
            continue
        if case_id in seen_ids:
            errors.append(prefix + "duplicate id")
        seen_ids.add(case_id)
        try:
            tile = tilegrid[case["tile"]]
            blocks = tile["bits"]
            if set(blocks) != {"CLB_IO_CLK"}:
                raise ValueError(f"tile blocks are {sorted(blocks)}, expected CLB_IO_CLK only")
            block = blocks["CLB_IO_CLK"]
            if block != case.get("expected_block"):
                raise ValueError(f"block mismatch: fixture={case.get('expected_block')} frozen={block}")
            db_path = safe_child(repo_root / "data/prjxray", case["database"])
            if not db_path.is_file():
                raise ValueError(f"database does not exist: {case['database']}")

            kind = case.get("kind")
            if kind in {"feature", "bitless"}:
                feature = case["feature"]
                bit_class = case["bit_class"]
                regex = class_regex.get(bit_class)
                if regex is None or regex.fullmatch(feature) is None:
                    raise ValueError(f"feature does not match declared class {bit_class}")
                tokens = find_feature(db_path, feature)
                if kind == "bitless":
                    if tokens != [case.get("expected_payload")]:
                        raise ValueError(f"ppip payload mismatch: fixture={case.get('expected_payload')} frozen={tokens}")
                    actual_assignments: list[dict[str, Any]] = []
                else:
                    actual_assignments = predicted_assignments(tokens, block)
                    site = feature_site(tile, feature)
                    if site != case.get("site"):
                        raise ValueError(f"site mismatch: fixture={case.get('site')} computed={site}")
                if actual_assignments != case.get("expected_assignments"):
                    raise ValueError(
                        f"assignment mismatch: fixture={case.get('expected_assignments')} computed={actual_assignments}"
                    )
            elif kind == "mask":
                mask_token = case["mask_token"]
                mask_lines = {line.strip() for line in db_path.read_text(encoding="utf-8").splitlines()}
                if f"bit {mask_token}" not in mask_lines:
                    raise ValueError(f"mask does not list bit {mask_token}")
                match = TOKEN_RE.fullmatch(mask_token)
                if match is None or match.group(1):
                    raise ValueError(f"invalid polarity-free mask token {mask_token!r}")
                actual_address = address(block, int(match.group(2)), int(match.group(3)))
                if actual_address != case.get("expected_address"):
                    raise ValueError(
                        f"mask address mismatch: fixture={case.get('expected_address')} computed={actual_address}"
                    )
            else:
                raise ValueError(f"unknown case kind {kind!r}")
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(prefix + str(exc))
    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=repo_root / "tests/fixtures/address_known_answers.json",
    )
    args = parser.parse_args()
    errors = verify(repo_root, args.fixtures.resolve())
    if errors:
        print(f"ADDRESS FIXTURES: FAIL — {len(errors)} finding(s)", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    count = len(load_json(args.fixtures)["cases"])
    print(f"ADDRESS FIXTURES: OK — {count} known answers reproduced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

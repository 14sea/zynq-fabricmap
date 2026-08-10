#!/usr/bin/env python3
"""Independently verify a Claim B ``reachability_report`` 1.0.0.

This is consumer-owned code.  It deliberately does not import the producer's
``build_reachability_spec`` module or a report generator.  Targets, draw advancement,
ceilings, rejected draws and exhaustion are derived again from the committed spec.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover - main refuses an incomplete host
    Draft202012Validator = None  # type: ignore[assignment]
    FormatChecker = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = REPO_ROOT / "schemas/reachability_report.schema.json"
PRODUCTION_SPEC_PATH = "specs/reachability_spec_v1.json"
PRODUCTION_SPEC_ID = "claimb_round1_reachability_v1"
MASK64 = (1 << 64) - 1
LCG_MULTIPLIER = 6364136223846793005
LCG_INCREMENT = 1442695040888963407
HEX64_RE = re.compile(r"64'h([0-9A-F]{16})")
SEED_RE = re.compile(r"0x[0-9A-Fa-f]+")


@dataclass(frozen=True)
class LutContract:
    site: str
    bel: str
    mutable_count: int
    fixed_indices: tuple[int, ...]
    base_init: int


@dataclass(frozen=True)
class SpecContract:
    seed: int
    ceiling_min: int
    redraw_cap: int
    luts: tuple[LutContract, ...]


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


def schema_problems(document: dict[str, Any], schema_path: Path = SCHEMA) -> list[str]:
    if Draft202012Validator is None:
        return ["Python package 'jsonschema' is required for reachability-report validation"]
    try:
        schema = json.loads(schema_path.read_bytes())
        Draft202012Validator.check_schema(schema)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return [f"reachability-report schema could not be loaded: {exc}"]
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    out: list[str] = []
    for error in sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        out.append(f"reachability-report schema {location}: {error.message}")
    return out


def safe_child(root: Path, relative: object, label: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError(f"{label}: not a repository-relative path: {relative!r}")
    candidate = (root / relative).resolve()
    resolved_root = root.resolve()
    if candidate == resolved_root or resolved_root not in candidate.parents:
        raise ValueError(f"{label}: path escapes the repository: {relative!r}")
    return candidate


def parse_hex64(value: object, label: str, problems: list[str]) -> int | None:
    if not isinstance(value, str) or (match := HEX64_RE.fullmatch(value)) is None:
        problems.append(f"{label}: expected canonical 64'h followed by 16 uppercase hex digits")
        return None
    return int(match.group(1), 16)


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def independent_target_vector(seed: int, draw_index: int) -> list[int]:
    """Consumer implementation of the spec's LCG/Fisher-Yates target draw."""
    state = (seed ^ (draw_index + 1)) & MASK64
    entries = [1] * 32 + [0] * 32
    for index in range(63, 0, -1):
        state = (state * LCG_MULTIPLIER + LCG_INCREMENT) & MASK64
        swap = (state >> 33) % (index + 1)
        entries[index], entries[swap] = entries[swap], entries[index]
    return entries


def truth_table(entries: list[int]) -> str:
    value = sum(bit << index for index, bit in enumerate(entries))
    return f"64'h{value:016X}"


def independent_blocked_positions(
    entries: list[int], fixed_indices: tuple[int, ...], base_init: int
) -> list[int]:
    return [
        index
        for index in fixed_indices
        if entries[index] != ((base_init >> index) & 1)
    ]


def spec_contract(
    spec: dict[str, Any],
) -> tuple[SpecContract | None, list[str]]:
    """Validate the machine contract needed for an independent derivation.

    There is intentionally no import of a producer schema or helper.  Version 1.0.0's
    algorithm is interpreted here, and its prose-like machine fields must have their
    exact frozen values before this verifier agrees to use them.
    """

    problems: list[str] = []
    if spec.get("schema") != "reachability_spec":
        problems.append("spec.schema is not reachability_spec")
    if spec.get("schema_version") != "1.0.0":
        problems.append("spec.schema_version is not 1.0.0")
    if spec.get("frozen_before_measurement") is not True:
        problems.append("spec is not marked frozen_before_measurement=true")
    if not isinstance(spec.get("spec_id"), str) or not spec["spec_id"]:
        problems.append("spec.spec_id is not a non-empty string")

    vectors = spec.get("vectors")
    seed: int | None = None
    if not isinstance(vectors, dict):
        problems.append("spec.vectors is not an object")
    else:
        seed_text = vectors.get("seed")
        if not isinstance(seed_text, str) or SEED_RE.fullmatch(seed_text) is None:
            problems.append("spec.vectors.seed is not canonical hexadecimal")
        else:
            seed = int(seed_text, 16)

    ceiling = spec.get("ceiling")
    ceiling_min: int | None = None
    if not isinstance(ceiling, dict):
        problems.append("spec.ceiling is not an object")
    else:
        if ceiling.get("scope") != "per_lut":
            problems.append("spec.ceiling.scope is not per_lut")
        value = ceiling.get("minimum_accepted")
        if not _integer(value) or not 0 <= value <= 64:
            problems.append("spec.ceiling.minimum_accepted is not an integer in 0..64")
        else:
            ceiling_min = value

    family = spec.get("target_family")
    redraw_cap: int | None = None
    if not isinstance(family, dict):
        problems.append("spec.target_family is not an object")
    else:
        if family.get("family") != "balanced 6-input Boolean functions":
            problems.append("unsupported target family")
        if family.get("definition") != "truth tables over 6 inputs with exactly 32 ones":
            problems.append("unsupported target-family definition")
        value = family.get("redraw_cap")
        if not _integer(value) or value < 1:
            problems.append("spec.target_family.redraw_cap is not a positive integer")
        else:
            redraw_cap = value

        convention = family.get("bit_vector_convention")
        expected_convention = {
            "initial_vector": "indices 0..31 = 1, indices 32..63 = 0",
            "shuffle": "Fisher-Yates swapping the values at positions i and j, i descending",
            "seed_expression": "vectors.seed XOR (k + 1)",
            "truth_table_indexing": (
                "entry v is the output for the input assignment Ij = (v >> j) & 1, "
                "which is the mapping the pinned LOCK_PINS I0:A1 … I5:A6 fixes"
            ),
            "init_integer": "sum(entry[v] << v)",
        }
        if not isinstance(convention, dict):
            problems.append("spec target bit-vector convention is not an object")
        else:
            for field, expected in expected_convention.items():
                if convention.get(field) != expected:
                    problems.append(f"spec target bit-vector convention.{field} drifted")
            known = convention.get("known_answer")
            literal = independent_target_vector(0x0001, 0)
            if not isinstance(known, dict):
                problems.append("spec target known_answer is not an object")
            else:
                if known.get("init") != truth_table(literal):
                    problems.append("spec target known_answer INIT fails the independent implementation")
                if known.get("first_eight_entries") != literal[:8]:
                    problems.append("spec target known_answer first entries fail the independent implementation")
                if known.get("ones") != sum(literal):
                    problems.append("spec target known_answer balance fails the independent implementation")

    phenotype = spec.get("phenotype")
    luts: list[LutContract] = []
    if not isinstance(phenotype, dict):
        problems.append("spec.phenotype is not an object")
    elif not isinstance(phenotype.get("luts"), list) or not phenotype["luts"]:
        problems.append("spec.phenotype.luts is not a non-empty array")
    else:
        identities: set[tuple[str, str]] = set()
        for position, value in enumerate(phenotype["luts"]):
            label = f"spec.phenotype.luts[{position}]"
            if not isinstance(value, dict):
                problems.append(f"{label} is not an object")
                continue
            site, bel = value.get("site"), value.get("bel")
            if not isinstance(site, str) or not site or not isinstance(bel, str) or not bel:
                problems.append(f"{label} has an invalid site/BEL identity")
                continue
            identity = (site, bel)
            if identity in identities:
                problems.append(f"{label} duplicates LUT {site}/{bel}")
            identities.add(identity)
            if value.get("lock_pins") != "I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6":
                problems.append(f"{label}.lock_pins is not the pinned identity mapping")

            mutable = value.get("mutable_indices")
            fixed = value.get("fixed_indices")
            if not isinstance(mutable, list) or not all(_integer(x) for x in mutable):
                problems.append(f"{label}.mutable_indices is not an integer array")
                continue
            if not isinstance(fixed, list) or not all(_integer(x) for x in fixed):
                problems.append(f"{label}.fixed_indices is not an integer array")
                continue
            if mutable != sorted(set(mutable)) or fixed != sorted(set(fixed)):
                problems.append(f"{label} mutable/fixed indices are not sorted and unique")
            if set(mutable) | set(fixed) != set(range(64)) or set(mutable) & set(fixed):
                problems.append(f"{label} mutable/fixed indices do not partition 0..63")
            if value.get("mutable_count") != len(mutable) or value.get("fixed_count") != len(fixed):
                problems.append(f"{label} mutable/fixed counts disagree with their arrays")

            base = parse_hex64(value.get("base_init"), f"{label}.base_init", problems)
            mask = parse_hex64(value.get("mutable_mask"), f"{label}.mutable_mask", problems)
            if mask is not None and mask != sum(1 << index for index in mutable):
                problems.append(f"{label}.mutable_mask disagrees with mutable_indices")
            fixed_values = value.get("fixed_values")
            if base is not None:
                expected_fixed = {str(index): (base >> index) & 1 for index in fixed}
                if fixed_values != expected_fixed:
                    problems.append(f"{label}.fixed_values disagree with base_init")
            if base is not None:
                luts.append(LutContract(site, bel, len(mutable), tuple(fixed), base))

        if phenotype.get("lut_count") != len(phenotype["luts"]):
            problems.append("spec.phenotype.lut_count disagrees with luts")
        derived_mutable_total = sum(
            len(item.get("mutable_indices"))
            for item in phenotype["luts"]
            if isinstance(item, dict) and isinstance(item.get("mutable_indices"), list)
        )
        derived_fixed_total = sum(
            len(item.get("fixed_indices"))
            for item in phenotype["luts"]
            if isinstance(item, dict) and isinstance(item.get("fixed_indices"), list)
        )
        if phenotype.get("total_mutable_positions") != derived_mutable_total:
            problems.append("spec total_mutable_positions disagrees with luts")
        if phenotype.get("total_fixed_positions") != derived_fixed_total:
            problems.append("spec total_fixed_positions disagrees with luts")

    output = spec.get("output")
    required_report_fields = {
        "spec_sha256",
        "per_lut[].site",
        "per_lut[].mutable_count",
        "per_lut[].target_truth_table",
        "per_lut[].draw_index",
        "per_lut[].discarded_draws[]",
        "per_lut[].attainable_ceiling",
        "per_lut[].blocked_positions[]",
        "totals.attainable_ceiling",
        "totals.exhausted",
    }
    if not isinstance(output, dict):
        problems.append("spec.output is not an object")
    else:
        if output.get("schema") != "reachability_report" or output.get("schema_version") != "1.0.0":
            problems.append("spec does not select reachability_report 1.0.0")
        fields = output.get("required_fields")
        if (
            not isinstance(fields, list)
            or not all(isinstance(field, str) for field in fields)
            or not required_report_fields.issubset(set(fields))
        ):
            problems.append("spec output.required_fields does not cover the authority report fields")

    if problems or seed is None or ceiling_min is None or redraw_cap is None:
        return None, problems
    if len(luts) != len(phenotype["luts"]):
        return None, problems + ["not every LUT could be interpreted"]
    return SpecContract(seed, ceiling_min, redraw_cap, tuple(luts)), []


def expected_report_body(contract: SpecContract) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """Re-derive the complete report body without producer code."""
    records: list[dict[str, Any]] = []
    draw_index = 0
    for lut in contract.luts:
        discarded: list[dict[str, Any]] = []
        accepted: dict[str, Any] | None = None
        for _ in range(contract.redraw_cap):
            entries = independent_target_vector(contract.seed, draw_index)
            blocked = independent_blocked_positions(entries, lut.fixed_indices, lut.base_init)
            ceiling = 64 - len(blocked)
            if ceiling >= contract.ceiling_min:
                accepted = {
                    "site": lut.site,
                    "bel": lut.bel,
                    "mutable_count": lut.mutable_count,
                    "target_truth_table": truth_table(entries),
                    "draw_index": draw_index,
                    "discarded_draws": discarded,
                    "attainable_ceiling": ceiling,
                    "blocked_positions": blocked,
                    "exhausted": False,
                }
                draw_index += 1
                break
            discarded.append(
                {
                    "draw_index": draw_index,
                    "attainable_ceiling": ceiling,
                    "blocked_positions": blocked,
                }
            )
            draw_index += 1
        if accepted is None:
            records.append(
                {
                    "site": lut.site,
                    "bel": lut.bel,
                    "mutable_count": lut.mutable_count,
                    "target_truth_table": None,
                    "draw_index": None,
                    "discarded_draws": discarded,
                    "attainable_ceiling": None,
                    "blocked_positions": None,
                    "exhausted": True,
                }
            )
            break
        records.append(accepted)

    exhausted = bool(records and records[-1]["exhausted"])
    selected = [record for record in records if not record["exhausted"]]
    totals = {
        "expected_luts": len(contract.luts),
        "reported_luts": len(records),
        "selected_luts": len(selected),
        "discarded_draws": sum(len(record["discarded_draws"]) for record in records),
        "attainable_ceiling": sum(record["attainable_ceiling"] for record in selected),
        "exhausted": exhausted,
    }
    return ("exhausted" if exhausted else "complete"), records, totals


def relationship_problems(
    report: dict[str, Any], spec: dict[str, Any], *, spec_sha256: str
) -> list[str]:
    """Check report meaning after the report itself passed its authority schema."""
    problems: list[str] = []
    reference = report["spec"]
    if report["spec_sha256"] != spec_sha256:
        problems.append("spec bytes do not match the hash pinned by the report")
    if reference["schema_version"] != spec.get("schema_version"):
        problems.append("report spec.schema_version differs from the spec")
    if reference["spec_id"] != spec.get("spec_id"):
        problems.append("report spec.spec_id differs from the spec")

    contract, contract_findings = spec_contract(spec)
    problems.extend(contract_findings)
    if contract is None:
        return problems

    expected_status, expected_records, expected_totals = expected_report_body(contract)
    if report["status"] != expected_status:
        problems.append(
            f"report status is {report['status']!r}; independent derivation is {expected_status!r}"
        )

    actual_records = report["per_lut"]
    if len(actual_records) != len(expected_records):
        problems.append(
            f"report has {len(actual_records)} LUT records; independent derivation has "
            f"{len(expected_records)}"
        )
    for index, (actual, expected) in enumerate(zip(actual_records, expected_records)):
        identity = f"{expected['site']}/{expected['bel']}"
        for field in (
            "site",
            "bel",
            "mutable_count",
            "target_truth_table",
            "draw_index",
            "discarded_draws",
            "attainable_ceiling",
            "blocked_positions",
            "exhausted",
        ):
            if actual[field] != expected[field]:
                problems.append(
                    f"per_lut[{index}] {identity} {field} differs from independent derivation"
                )

    for field, expected in expected_totals.items():
        if report["totals"][field] != expected:
            problems.append(f"report totals.{field} differs from independent derivation")
    return problems


def production_problems(report: dict[str, Any], spec: dict[str, Any]) -> list[str]:
    """Keep conformance fixtures from being mistaken for the Claim B production run."""
    problems: list[str] = []
    if report["spec"]["path"] != PRODUCTION_SPEC_PATH:
        problems.append(
            f"production report must pin {PRODUCTION_SPEC_PATH}, not {report['spec']['path']}"
        )
    if report["spec"]["spec_id"] != PRODUCTION_SPEC_ID:
        problems.append("production report pins the wrong spec_id")
    if spec.get("spec_id") != PRODUCTION_SPEC_ID:
        problems.append("production reachability spec has the wrong spec_id")
    phenotype = spec.get("phenotype")
    if not isinstance(phenotype, dict) or phenotype.get("lut_count") != 6:
        problems.append("production reachability spec does not govern exactly six LUTs")
    return problems


def head_blob(repo: Path, relative: str) -> tuple[bytes | None, list[str]]:
    """Read the authority bytes from HEAD; no HEAD means no frozen authority."""
    probe = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "HEAD"],
        capture_output=True,
        check=False,
    )
    if probe.returncode != 0:
        return None, ["repository has no HEAD authority for the reachability spec"]
    read = subprocess.run(
        ["git", "-C", str(repo), "show", f"HEAD:{relative}"],
        capture_output=True,
        check=False,
    )
    if read.returncode != 0:
        return None, [f"reachability spec is absent from HEAD: {relative}"]
    return read.stdout, []


def verify_path(
    report_path: Path, repo: Path = REPO_ROOT, *, require_production: bool = True
) -> list[str]:
    try:
        report_bytes = report_path.read_bytes()
    except OSError as exc:
        return [f"report could not be read: {exc}"]
    report, problems = parse_object(report_bytes, "reachability report")
    if report is None:
        return problems
    problems.extend(schema_problems(report))
    if problems:
        return problems

    relative = report["spec"]["path"]
    try:
        spec_path = safe_child(repo, relative, "report spec.path")
        spec_bytes = spec_path.read_bytes()
    except (OSError, ValueError) as exc:
        return [f"reachability spec could not be read safely: {exc}"]

    committed, authority_problems = head_blob(repo, relative)
    problems.extend(authority_problems)
    if committed is None:
        return problems
    if committed != spec_bytes:
        problems.append("working reachability spec bytes differ from HEAD")

    spec, parse_problems = parse_object(spec_bytes, "reachability spec")
    problems.extend(parse_problems)
    if spec is None:
        return problems
    problems.extend(relationship_problems(report, spec, spec_sha256=sha256_bytes(spec_bytes)))
    if require_production:
        problems.extend(production_problems(report, spec))
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("report", type=Path)
    args = parser.parse_args()

    problems = verify_path(args.report.resolve(), REPO_ROOT)
    if problems:
        print(f"REACHABILITY REPORT VERIFY: FAIL — {len(problems)} finding(s)", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    report = json.loads(args.report.read_bytes())
    totals = report["totals"]
    print(
        "REACHABILITY REPORT VERIFY: OK — "
        f"status={report['status']} selected={totals['selected_luts']}/"
        f"{totals['expected_luts']} discarded={totals['discarded_draws']} "
        f"ceiling={totals['attainable_ceiling']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Emit a `reachability_report` 1.0.0 by executing the frozen selection rules.

This is the producer entry point review v4 item 3 required and the repository did not
have: `build_reachability_spec.py` only *builds* a spec, so there was no command that
produces a report, and hand-assembling the JSON would bypass the producer contract
entirely — the report would then be an author's opinion about what the rules imply.

What this tool is, exactly
--------------------------

It executes `select_targets` and its helpers from `build_reachability_spec` — the rules
frozen at 88c927c — over a committed spec, and writes the derived record. It decides
nothing: every target, discard, ceiling and exhaustion comes from those functions.

**Parameters come from the SPEC, never from the producer's module constants.** The
production spec and a conformance fixture differ in seed, redraw cap and LUT set; a
producer that reached for `CEILING_MIN` or `REDRAW_CAP` would silently judge a conformance
spec by production numbers and still emit a schema-valid report. The spec is the authority
for its own run.

**`--profile` has no default and must agree with the spec.** Stating the profile is not an
override — it cannot widen anything, and it must match the spec's `spec_id`. It exists so
that a production emission is a thing someone typed, never something that happened because
an argument was omitted.

**There is no way to skip the consumer's gate.** `emit()` always verifies; no flag, no
parameter. An earlier version had `--no-verify` "for development", which was a
skip-authority path in a tool whose entire purpose is authority: the bytes it wrote carried
the same schema and the same production-shaped filename as a result, and nothing downstream
could recover that the flag had been used. Development wants an unchecked record in memory,
which `build_report()` already returns.

**Authority is checked BEFORE the rules run.** The preflight requires the spec to be the
unchanged HEAD blob and to satisfy the consumer's own `spec_contract` before
`select_targets` is called, so a production invocation can never execute a target stream
and only afterwards discover it read an uncommitted, mis-pathed or malformed authority —
and a malformed spec cannot reach the frozen helpers and raise a bare TypeError instead of
a refusal.

**Publication is exclusive and cleanup is unconditional.** A pre-existing output or
candidate is a refusal (a one-shot formal artifact is never overwritten), and the candidate
is removed on every path out — refusal, exception, anything — with the atomic rename
reached only after the consumer accepts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "host"))

import build_reachability_spec as rules  # noqa: E402  (producer side: the frozen rules)
import verify_reachability_report as consumer  # noqa: E402  (consumer side: the gate)

TOOL_VERSION = "gate_reachability_report.py/1.0.0"
REPORT_SCHEMA_VERSION = "1.0.0"

PRODUCTION_SPEC_ID = "claimb_round1_reachability_v1"

PROFILES = {
    "production": PRODUCTION_SPEC_ID,
    "conformance": None,  # anything that is not the production spec_id
}


class ReportError(Exception):
    """A refusal."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def truth_table(entries: list[int]) -> str:
    return f"64'h{rules.target_init(entries):016X}"


def check_profile(profile: str, spec_id: str) -> None:
    """The declared profile must match the artifact; it can never widen it."""
    if profile not in PROFILES:
        raise ReportError(f"unknown profile {profile!r}; expected one of {sorted(PROFILES)}")
    if profile == "production" and spec_id != PRODUCTION_SPEC_ID:
        raise ReportError(
            f"--profile production was declared but the spec is {spec_id!r}, not "
            f"{PRODUCTION_SPEC_ID!r}"
        )
    if profile == "conformance" and spec_id == PRODUCTION_SPEC_ID:
        raise ReportError(
            "--profile conformance was declared but this IS the production spec — "
            "emitting the Claim B result needs its own authorisation, and a profile "
            "argument is not it"
        )


def preflight(spec_path: Path, profile: str, repo: Path) -> tuple[bytes, dict]:
    """Everything that must hold BEFORE the frozen rules are allowed to run.

    Composed from the consumer's own primitives — `head_blob`, `spec_contract`,
    `parse_object` and its production constants — rather than a private reimplementation.
    A weaker producer-side copy of these checks would be exactly the self-consistent
    authority this arrangement exists to prevent.
    """
    if not spec_path.is_relative_to(repo):
        raise ReportError(f"spec is outside the repository: {spec_path}")
    relative = spec_path.relative_to(repo).as_posix()

    if profile == "production" and relative != consumer.PRODUCTION_SPEC_PATH:
        raise ReportError(
            f"a production report must be derived from {consumer.PRODUCTION_SPEC_PATH}, "
            f"not {relative}"
        )

    try:
        spec_bytes = spec_path.read_bytes()
    except OSError as exc:
        raise ReportError(f"spec could not be read: {exc}") from exc

    committed, problems = consumer.head_blob(repo, relative)
    if problems:
        raise ReportError("; ".join(problems))
    if committed != spec_bytes:
        raise ReportError(
            "the working spec differs from HEAD — a report may only be derived from the "
            "committed authority"
        )

    spec, problems = consumer.parse_object(spec_bytes, "reachability spec")
    if spec is None:
        raise ReportError("; ".join(problems))

    contract, problems = consumer.spec_contract(spec)
    # Mutation note: `problems or` is currently EQUIVALENT to `contract is None` — the
    # consumer returns (None, problems) whenever it has any. It is kept because that is
    # their invariant, not mine: if spec_contract ever returns a usable contract alongside
    # findings, this clause becomes the thing that stops us using it.
    if problems or contract is None:
        raise ReportError(
            "the consumer's spec contract refuses this spec: " + "; ".join(problems)
        )

    check_profile(profile, spec.get("spec_id", ""))

    if profile == "production" and len(contract.luts) != 6:
        raise ReportError(
            f"the production spec must carry six LUTs, not {len(contract.luts)}"
        )

    # No private scope check here on purpose: the consumer's `spec_contract` already
    # refuses a spec whose ceiling.scope is not per_lut, and a duplicate on this side
    # would be an unexercised rule sitting behind an earlier refusal — this repo's own
    # lesson about inline checks that no test can reach.
    return spec_bytes, spec


def spec_parameters(spec: dict) -> tuple[int, int, int, list[dict]]:
    """Seed, ceiling and cap read from the spec itself, not from module constants."""
    try:
        seed = int(spec["vectors"]["seed"], 16)
        ceiling_min = spec["ceiling"]["minimum_accepted"]
        cap = spec["target_family"]["redraw_cap"]
        luts = spec["phenotype"]["luts"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ReportError(f"spec is missing a required parameter: {exc}") from exc
    if not luts:
        raise ReportError("spec carries no LUTs")
    return seed, ceiling_min, cap, luts


def discard_records(lut: dict, seed: int, discarded: list[dict]) -> list[dict]:
    """Re-derive each rejected draw's blocked positions with the same frozen helpers.

    `select_target_for_lut` records a discard's index and ceiling; the schema also wants
    its blocked positions. They are recomputed here from `target_vector` and
    `blocked_positions` rather than by widening the frozen selection function, so the rules
    committed at 88c927c stay byte-identical.
    """
    fixed = lut["fixed_indices"]
    base = int(lut["base_init"].split("h")[1], 16)
    out = []
    for entry in discarded:
        entries = rules.target_vector(seed, entry["draw_index"])
        blocked = rules.blocked_positions(entries, fixed, base)
        if 64 - len(blocked) != entry["attainable_ceiling"]:
            raise ReportError(
                f"internal disagreement re-deriving discard {entry['draw_index']}: "
                f"{64 - len(blocked)} vs {entry['attainable_ceiling']}"
            )
        out.append(
            {
                "draw_index": entry["draw_index"],
                "attainable_ceiling": entry["attainable_ceiling"],
                "blocked_positions": blocked,
            }
        )
    return out


def build_report(spec_path: Path, profile: str, report_id: str,
                 repo: Path = REPO_ROOT) -> dict:
    spec_bytes, spec = preflight(spec_path, profile, repo)
    relative = spec_path.relative_to(repo).as_posix()

    seed, ceiling_min, cap, luts = spec_parameters(spec)
    outcome = rules.select_targets(luts, seed, ceiling_min, cap)

    records = []
    for assignment, lut in zip(outcome["assignments"], luts):
        discards = discard_records(lut, seed, assignment["discarded_draws"])
        if assignment["exhausted"]:
            records.append(
                {
                    "site": lut["site"],
                    "bel": lut["bel"],
                    "mutable_count": lut["mutable_count"],
                    "target_truth_table": None,
                    "draw_index": None,
                    "discarded_draws": discards,
                    "attainable_ceiling": None,
                    "blocked_positions": None,
                    "exhausted": True,
                }
            )
            continue
        entries = rules.target_vector(seed, assignment["draw_index"])
        records.append(
            {
                "site": lut["site"],
                "bel": lut["bel"],
                "mutable_count": lut["mutable_count"],
                "target_truth_table": truth_table(entries),
                "draw_index": assignment["draw_index"],
                "discarded_draws": discards,
                "attainable_ceiling": assignment["attainable_ceiling"],
                "blocked_positions": assignment["blocked_positions"],
                "exhausted": False,
            }
        )

    exhausted = bool(records and records[-1]["exhausted"])
    selected = [record for record in records if not record["exhausted"]]
    return {
        "schema": "reachability_report",
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_id": report_id,
        "spec": {
            "path": relative,
            "schema_version": spec["schema_version"],
            "spec_id": spec["spec_id"],
        },
        "spec_sha256": sha256_bytes(spec_bytes),
        "status": "exhausted" if exhausted else "complete",
        "per_lut": records,
        "totals": {
            "expected_luts": len(luts),
            "reported_luts": len(records),
            "selected_luts": len(selected),
            "discarded_draws": sum(len(r["discarded_draws"]) for r in records),
            # Mutation note: summing over `records` with a `or 0` guard is an EQUIVALENT
            # mutant. An exhausted record always carries a null ceiling (schema, and
            # pinned by test_an_exhausted_lut_reports_null_target_fields), so the guard
            # contributes 0 and the two sums are numerically identical. Written over
            # `selected` because that is what the field means, not because a test can tell.
            "attainable_ceiling": sum(r["attainable_ceiling"] for r in selected),
            "exhausted": exhausted,
        },
        "tool_versions": {
            "producer": TOOL_VERSION,
            "rules": rules.TOOL_VERSION,
        },
    }


def emit(spec_path: Path, profile: str, report_id: str, out: Path,
         repo: Path = REPO_ROOT) -> dict:
    """Derive, verify, publish — with no path that skips the middle step.

    `repo` is a function parameter and deliberately NOT a CLI flag: tests need to build a
    scratch repository to supply Git authority (a `git archive` export has no history, and
    the verifier correctly refuses to answer without one), while a command line that could
    point at another repository would let someone construct a self-consistent authority for
    a production report. The consumer's verifier draws the same line.

    Publication is exclusive: an existing `out` or `.candidate` is refused rather than
    overwritten. A formal artifact that can be silently replaced is one whose previous
    contents nobody can account for.
    """
    candidate = out.with_suffix(out.suffix + ".candidate")
    for path, what in ((out, "output"), (candidate, "candidate")):
        if path.exists():
            raise ReportError(
                f"{what} already exists and will not be overwritten: {path}"
            )

    report = build_report(spec_path, profile, report_id, repo)

    out.parent.mkdir(parents=True, exist_ok=True)
    published = False
    try:
        candidate.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        try:
            problems = consumer.verify_path(
                candidate, repo, require_production=(profile == "production")
            )
        except Exception as exc:  # noqa: BLE001 — a verifier that raises has not accepted
            raise ReportError(
                f"the consumer verifier raised {type(exc).__name__}: {exc}; no file was "
                "written"
            ) from exc
        if problems:
            raise ReportError(
                "the consumer verifier rejected the candidate; no file was written:\n  - "
                + "\n  - ".join(problems)
            )
        candidate.replace(out)
        published = True
    finally:
        if not published:
            candidate.unlink(missing_ok=True)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument(
        "--profile",
        required=True,
        choices=sorted(PROFILES),
        help="must agree with the spec; there is no default, so a production emission is "
             "always something someone typed",
    )
    ap.add_argument("--report-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    try:
        report = emit(args.spec.resolve(), args.profile, args.report_id, args.out)
    except ReportError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    totals = report["totals"]
    print(
        f"{args.out}: status={report['status']} "
        f"selected={totals['selected_luts']}/{totals['expected_luts']} "
        f"discarded={totals['discarded_draws']} ceiling={totals['attainable_ceiling']}"
    )
    for record in report["per_lut"]:
        if record["exhausted"]:
            print(f"  {record['site']}/{record['bel']:6s} EXHAUSTED after "
                  f"{len(record['discarded_draws'])} draws")
        else:
            print(f"  {record['site']}/{record['bel']:6s} k={record['draw_index']:3d} "
                  f"ceiling={record['attainable_ceiling']} "
                  f"target={record['target_truth_table']}")
    print("  verified by host/verify_reachability_report.py before being written")
    return 0


if __name__ == "__main__":
    sys.exit(main())

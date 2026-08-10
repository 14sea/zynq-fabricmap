#!/usr/bin/env python3
"""Derive a `local_map` 1.0.0 from a passing production bit-class certificate.

The map adds no knowledge. Every address, polarity and feature name in it comes from the
certificate; the only thing this tool contributes is the **inverse index** — certificates
are ordered per feature because that is what an auditor reads, and a mutation operator
needs to ask the opposite questions ("which bits share a frame", "which bits are one
truth table"). Whether that indexing measurably helps navigation is Claim B itself, so it
must be the *only* difference between the two arms and it must not smuggle in facts the
certificate never established.

What this tool refuses, and why each refusal exists
---------------------------------------------------

* **A certificate that is not `status: passed` and `profile: production`.** A failed run
  certifies nothing, and a `conformance` certificate is a self-test against synthetic
  fixtures — it says nothing about this device. Both are recorded in the map so a verifier
  re-checks the claim rather than trusting that this tool looked.

* **Predicted and observed disagreeing.** The certificate already scored that comparison,
  but a map that copies `predicted_assignments` while the certificate's own
  `observed_assignments` differ would encode an address the device did not confirm. Cheap
  to recompute, and the one place a silent inversion would survive into every candidate.

* **A feature carrying anything other than exactly one assignment.** Round 1's universe is
  1 feature ↔ 1 address. A multi-assignment feature is not an error in general — it is
  outside what this map version can express, and dropping it silently would shrink the
  universe without saying so.

* **One feature at two addresses, or one address claimed by two features.** Either breaks
  the bijection the index depends on. The 388 results cover 292 features, so features ARE
  re-attested; re-attestation must agree, and this is where that is checked.

* **A certificate whose target disagrees with the frozen manifest**, or a manifest that is
  not the one the certificate pinned. A map that mixes two freezes is stale by
  construction and nothing downstream can detect it.

`--check` re-derives from the certificate and compares against an existing map without
writing, so a drifted map is a non-zero exit rather than a silent overwrite.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

TOOL_VERSION = "build_local_map.py/1.0.0"
SCHEMA_VERSION = "1.0.0"

REPO_ROOT = Path(__file__).resolve().parent.parent

# LUT INIT feature names look like 'CLBLL_L.SLICEL_X0.ALUT.INIT[00]'. The prefix up to
# '.INIT[' is the LUT; the bracketed number is the index into its truth table.
INIT_FEATURE_RE = re.compile(r"^(?P<lut>.+)\.INIT\[(?P<index>\d+)\]$")


class MapError(Exception):
    """A refusal. Carries the reason that will be printed and returned non-zero."""


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def address_key(far: str, word: int, bit: int) -> str:
    """Canonical 'FAR/word/bit'.

    The FAR is upper-cased hex with the 0x prefix because that is how the certificate
    spells it; normalising here rather than at each use keeps the two indexes and the
    universe referring to one spelling, so a mismatch is an equality question.
    """
    return f"{far}/{word}/{bit}"


def load_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise MapError(f"not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MapError(f"not valid JSON: {path}: {exc}") from exc


def check_certificate_admissible(cert: dict, cert_path: Path) -> None:
    if cert.get("schema") != "fabric_bit_class_certificate":
        raise MapError(f"{cert_path}: not a fabric_bit_class_certificate")
    status = cert.get("status")
    if status != "passed":
        raise MapError(
            f"{cert_path}: status is {status!r}, not 'passed' — a map may not descend "
            "from a failed certification"
        )
    profile = cert.get("profile")
    if profile != "production":
        raise MapError(
            f"{cert_path}: profile is {profile!r}, not 'production' — a conformance "
            "certificate is a self-test against synthetic fixtures and says nothing "
            "about this device"
        )
    if not cert.get("feature_results"):
        raise MapError(
            f"{cert_path}: no feature_results — this map version reads the feature "
            "evidence model; a group-model certificate needs its own map version"
        )


def collateral_from_certificate(results: list) -> dict:
    """Lift the frame-ECC exclusion out of the certificate instead of hard-coding it.

    The gate must know which collateral changes are expected, and the honest source for
    that is the certificate's own `exclusion_rules` — a constant compiled into the diff
    gate would keep agreeing with itself after the certificate's rule changed.
    """
    seen = {}
    for result in results:
        for rule in result.get("exclusion_rules", []):
            if rule.get("reason") == "frame_ecc":
                seen[rule.get("rule")] = rule.get("why")
    if len(seen) != 1:
        raise MapError(
            "expected exactly one distinct frame_ecc exclusion rule across the "
            f"certificate, found {len(seen)}: {sorted(seen)}"
        )
    rule_text, why = next(iter(seen.items()))
    match = re.fullmatch(
        r"word == (\d+) and (\d+) <= bit <= (\d+)", (rule_text or "").strip()
    )
    if not match:
        raise MapError(
            f"frame_ecc rule is not in the form this map version can express: {rule_text!r}"
        )
    word, low, high = (int(g) for g in match.groups())
    return {
        "rule": rule_text,
        "word": word,
        "bit_low": low,
        "bit_high": high,
        "why": why,
        "scope": "touched_frames_only",
    }


def universe_from_certificate(results: list) -> list:
    """Collapse the feature results into one entry per address, checking the bijection."""
    by_feature: dict[str, dict] = {}
    for result in results:
        feature = result["feature"]
        assignments = result.get("predicted_assignments") or []
        if len(assignments) != 1:
            raise MapError(
                f"{feature}: {len(assignments)} predicted assignments; this map version "
                "expresses exactly one address per feature, and dropping the rest would "
                "shrink the universe silently"
            )
        assignment = assignments[0]
        addr = assignment["address"]
        entry = {
            "key": address_key(addr["far"], addr["word"], addr["bit"]),
            "far": addr["far"],
            "word": addr["word"],
            "bit": addr["bit"],
            "feature": feature,
            "expected_value": assignment["expected_value"],
            "split": result["split"],
            "rule_file": result["rule_file"],
        }

        observed = result.get("observed_assignments") or []
        if len(observed) != 1:
            raise MapError(
                f"{feature}: {len(observed)} observed assignments against 1 predicted"
            )
        obs_addr = observed[0]["address"]
        if address_key(obs_addr["far"], obs_addr["word"], obs_addr["bit"]) != entry["key"]:
            raise MapError(
                f"{feature}: predicted {entry['key']} but the certificate observed "
                f"{address_key(obs_addr['far'], obs_addr['word'], obs_addr['bit'])}"
            )
        if observed[0]["observed_value"] != entry["expected_value"]:
            raise MapError(
                f"{feature}: expected value {entry['expected_value']} but the "
                f"certificate observed {observed[0]['observed_value']}"
            )

        previous = by_feature.get(feature)
        if previous is None:
            by_feature[feature] = entry
        elif previous != entry:
            # Features are re-attested (388 results over 292 features). Re-attestation
            # that disagrees means the certificate contradicts itself about this bit.
            raise MapError(
                f"{feature}: re-attested with a different assignment "
                f"({previous['key']} vs {entry['key']})"
            )

    by_address: dict[str, str] = {}
    for feature, entry in by_feature.items():
        claimed = by_address.setdefault(entry["key"], feature)
        if claimed != feature:
            raise MapError(
                f"address {entry['key']} is claimed by two features: {claimed} and {feature}"
            )

    return sorted(by_feature.values(), key=lambda e: (e["far"], e["word"], e["bit"]))


def build_index(addresses: list) -> dict:
    by_far: dict[str, list] = {}
    for entry in addresses:
        by_far.setdefault(entry["far"], []).append(entry["key"])

    by_lut: dict[str, list] = {}
    for entry in addresses:
        match = INIT_FEATURE_RE.match(entry["feature"])
        if not match:
            raise MapError(
                f"{entry['feature']}: not a LUT INIT feature name; this map version "
                "indexes clb_lut_init only"
            )
        by_lut.setdefault(match.group("lut"), []).append(
            {"init_index": int(match.group("index")), "address_key": entry["key"]}
        )

    for lut, bits in by_lut.items():
        bits.sort(key=lambda b: b["init_index"])
        indices = [b["init_index"] for b in bits]
        if len(set(indices)) != len(indices):
            raise MapError(f"{lut}: duplicate INIT indices {indices}")

    return {
        "by_far": {far: sorted(keys) for far, keys in sorted(by_far.items())},
        "by_lut": dict(sorted(by_lut.items())),
    }


def build_map(cert_path: Path, manifest_path: Path, map_id: str) -> dict:
    cert = load_json(cert_path)
    check_certificate_admissible(cert, cert_path)

    manifest = load_json(manifest_path)
    if manifest.get("schema") != "frozen_db_subset":
        raise MapError(f"{manifest_path}: not a frozen_db_subset manifest")

    cert_target = cert.get("target") or {}
    man_target = manifest.get("target") or {}
    for field in ("family", "device", "part"):
        if cert_target.get(field) != man_target.get(field):
            raise MapError(
                f"target.{field} differs between certificate ({cert_target.get(field)!r}) "
                f"and frozen manifest ({man_target.get(field)!r}) — a map that mixes two "
                "freezes is stale by construction"
            )

    results = cert["feature_results"]
    addresses = universe_from_certificate(results)
    bit_class = cert.get("bit_class") or {}
    coverage = bit_class.get("coverage") or {}

    freeze_stamp = manifest.get("freeze_stamp")
    if not freeze_stamp:
        raise MapError(f"{manifest_path}: no freeze_stamp")

    return {
        "schema": "local_map",
        "schema_version": SCHEMA_VERSION,
        "map_id": map_id,
        "provenance": {
            "kind": "certificate_inherited",
            "certificate": {
                "path": cert_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256_of(cert_path),
                "schema_version": cert["schema_version"],
                "certificate_id": cert["certificate_id"],
                "status": cert["status"],
                "profile": cert["profile"],
                "bit_class_id": bit_class.get("id"),
            },
            "frozen_data": {
                "path": manifest_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256_of(manifest_path),
                "freeze_stamp": freeze_stamp,
            },
        },
        "target": {
            "family": cert_target["family"],
            "device": cert_target["device"],
            "part": cert_target["part"],
        },
        "bit_class": {
            "id": bit_class["id"],
            "tier": bit_class["tier"],
            "class_entry_count": coverage["class_entry_count"],
            "attested_count": len(addresses),
        },
        "universe": {
            "address_count": len(addresses),
            "far_count": len({e["far"] for e in addresses}),
            "words": sorted({e["word"] for e in addresses}),
            "addresses": addresses,
        },
        "collateral": {"frame_ecc": collateral_from_certificate(results)},
        "index": build_index(addresses),
        "tool_versions": {"builder": TOOL_VERSION},
    }


def serialise(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--certificate",
        type=Path,
        default=REPO_ROOT / "gate_runs/run_2026_08_02_a/certificate.json",
    )
    ap.add_argument("--manifest", type=Path, default=REPO_ROOT / "data/MANIFEST.json")
    ap.add_argument("--map-id", default="clb_lut_init_v1")
    ap.add_argument("--out", type=Path, help="write the map here")
    ap.add_argument(
        "--check",
        type=Path,
        help="re-derive and compare against this existing map; write nothing",
    )
    args = ap.parse_args()

    if not args.out and not args.check:
        ap.error("one of --out or --check is required")

    try:
        doc = build_map(args.certificate.resolve(), args.manifest.resolve(), args.map_id)
    except MapError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    if args.check:
        try:
            existing = load_json(args.check)
        except MapError as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
        if existing != doc:
            print(
                f"DRIFTED: {args.check} does not match a fresh derivation from "
                f"{args.certificate}",
                file=sys.stderr,
            )
            return 1
        print(f"{args.check}: matches a fresh derivation ({doc['universe']['address_count']} addresses)")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(serialise(doc), encoding="utf-8")
    universe = doc["universe"]
    print(
        f"{args.out}: {universe['address_count']} addresses over {universe['far_count']} "
        f"frames, words {universe['words']}, {len(doc['index']['by_lut'])} LUTs"
    )
    print(f"  from {doc['provenance']['certificate']['path']} ({doc['provenance']['certificate']['sha256'][:12]}…)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

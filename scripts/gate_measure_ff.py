#!/usr/bin/env python3
"""Score a `clb_ff_config` run against its committed predictions — certificate 1.4.

Refuses to score unless `predictions.json` still hashes to the committed value. That
check is the whole point of the ordering: a measurement of predictions that were edited
after the bitstreams existed measures nothing.

What 1.4 changed, and what this tool therefore does differently from `gate_measure.py`:

* **TP and FN come only from the preregistered assignment and transition.** For every
  predicted address the tool records the value in BOTH endpoints and compares the pair
  against `expected_transition`, plus the feature endpoint against the preregistered
  `expected_value`. Whether a bit shows up in the diff is not an input — a bit that was
  already at the expected value in both endpoints is a failed prediction of a
  *transition*, and the old "is it in the diff" test silently accepted it.
* **FP is fixed by the profile**, not chosen per run:

      FP = ownership_unknown u unattributed
           u {db_attributed bits in an asserted tile that this class claims and that lie
              in no preregistered scope of that pair}

  counted once per `(pair, address)`. A changed bit owned by another class — legal INT
  routing beside a CLB content assertion — is not this class's FP.
* **Observation consistency** is recorded per `(specimen, address)` so the verifier can
  reject a record that reports two values for one bit of one specimen. Opposite values
  in *different* specimens are valid and are how complementary states get certified.

Every pair in a site instance is `(base, variant)`; which of the two endpoints is
claimed to assert the feature comes from the prediction's own `specimen_id`, and which
variant forms the pair comes from the committed `pair_features` — neither is re-derived
here, because a second copy of the plan is a plan that can drift.

    scripts/gate_measure_ff.py --run gate_runs/<run> --build build/gate_ff \\
                               --expect-sha256 <committed> --out <run>/measurement.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bitstream_frames import FRAME_WORDS, column_map, device_layout, parse_frames  # noqa: E402
from decode_groups import read_tile_bits  # noqa: E402
from specimen_diff import ECC_BITS, ECC_WORD, features_using, locate, tile_index  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
TILEGRID = REPO / "data/prjxray/zynq7/xc7z010/tilegrid.json"
SPEC = REPO / "data/subset_spec.json"
BIT_CLASS = "clb_ff_config"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bit_path(build: Path, specimen: dict) -> Path:
    return build / specimen["specimen_id"] / "spec.bit"


def raw_diff(a: dict, b: dict) -> set[tuple[int, int, int]]:
    out = set()
    for far, wa in a.items():
        wb = b[far]
        if wa == wb:
            continue
        for word in range(FRAME_WORDS):
            x = wa[word] ^ wb[word]
            while x:
                bit = (x & -x).bit_length() - 1
                x &= x - 1
                out.add((far, word, bit))
    return out


def address_tuple(address: dict) -> tuple[int, int, int]:
    return int(address["far"], 16), address["word"], address["bit"]


def as_addresses(items) -> list[dict]:
    return sorted(({"far": f"0x{f:08X}", "word": w, "bit": b} for f, w, b in items),
                  key=lambda a: (a["far"], a["word"], a["bit"]))


BUCKETS = ("in_scope", "frame_ecc", "db_attributed", "ownership_unknown", "unattributed")


def classify_diff(raw, scope, index, pattern, asserted_tiles):
    """Label every changed bit into the five 1.4 buckets, plus the same-class subset.

    Returns `(buckets, class_claimed_out_of_scope)`. The second value is the part of
    `db_attributed` that this class itself claims inside a tile the pair asserted and
    that no preregistered scope covers — the only FP contribution that is not simply
    "we cannot explain this bit". Another class's changed bit, such as legal INT routing
    beside a CLB content assertion, is not this class's FP.

    Shared with `gate_build_ff.py` on purpose: an exploration that bucketed bits even
    slightly differently from the gate would answer a question nobody is going to ask.
    """
    buckets = {name: set() for name in BUCKETS}
    class_claimed_out_of_scope = set()
    for far, word, bit in raw:
        if (far, word, bit) in scope:
            buckets["in_scope"].add((far, word, bit))
            continue
        if word == ECC_WORD and bit in ECC_BITS:
            buckets["frame_ecc"].add((far, word, bit))
            continue
        hits = locate(index, far, word, bit)
        if not hits:
            buckets["unattributed"].add((far, word, bit))
        elif any(features_using(hit["type"], hit["segbit"]) for hit in hits):
            buckets["db_attributed"].add((far, word, bit))
            if any(hit["tile"] in asserted_tiles
                   and any(pattern.fullmatch(f)
                           for f in features_using(hit["type"], hit["segbit"]))
                   for hit in hits):
                class_claimed_out_of_scope.add((far, word, bit))
        else:
            buckets["ownership_unknown"].add((far, word, bit))
    return buckets, class_claimed_out_of_scope


def semantic_verdict(transition_exact: bool, observed, expected) -> bool:
    """`transition_exact and attestation_basis_consistent`, the verifier's rule.

    Kept as its own function because the producer must not invent a weaker or stronger
    semantic pass than the consumer recomputes: `host/verify_certificate.py` rebuilds
    the outcome summary and rejects the record if the copied `passed` disagrees. A
    semantic claim about a specimen whose addressing did not match is not a passing
    naming claim — it names a member the evidence did not select.
    """
    return transition_exact and observed == expected


def address_decision(totals: dict, accounting: list, address_problems: list,
                     committed_holdout: int) -> str:
    """The address decision, with semantics deliberately absent from its inputs.

    1.4 isolates the two: a semantic-only failure keeps `status: passed`, exits zero and
    reports its failure count prominently. Passing `semantic_findings` in here — or
    folding them into `address_problems` — would silently make a naming claim able to
    fail an addressing result, which is the defect this signature exists to prevent.
    """
    holdout = totals["holdout"]
    failed = (holdout["fn"] or holdout["fp"]
              or holdout["tp"] != committed_holdout
              or any(not record["partition_exact"] for record in accounting)
              or address_problems)
    return "FAIL" if failed else "PASS"


def resolve_pointer(value, pointer: str):
    """RFC 6901, objects only — the same restriction the verifier applies."""
    for raw in pointer.removeprefix("/").split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--build", type=Path, required=True)
    ap.add_argument("--expect-sha256")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    pred_path = args.run / "predictions.json"
    digest = sha256_file(pred_path)
    if args.expect_sha256 and digest != args.expect_sha256:
        raise SystemExit(f"predictions hash {digest} != committed — refusing to score")
    doc = json.loads(pred_path.read_text())
    if doc["bit_class"] != BIT_CLASS:
        raise SystemExit(f"predictions are for {doc['bit_class']}, not {BIT_CLASS}")
    print(f"predictions: {digest}"
          + ("  (matches the committed hash)" if args.expect_sha256 else ""))

    grid = json.loads(TILEGRID.read_text())
    spec = json.loads(SPEC.read_text())
    pattern = re.compile(next(c["feature_regex"] for c in spec["bit_classes"]
                              if c["id"] == BIT_CLASS))
    cols, layout = column_map(), device_layout()
    index = tile_index()
    by_id = {s["specimen_id"]: s for s in doc["specimens"]}

    # Attestations are copied into the run directory: they live under build/, which is
    # gitignored, so a record pointing at them there names evidence a fresh clone cannot
    # resolve.
    attestation_dir = args.run / "attestations"
    attestation_dir.mkdir(exist_ok=True)

    frames_cache: dict[str, dict] = {}
    attestation_cache: dict[str, dict] = {}
    address_problems: list[str] = []
    semantic_findings: list[str] = []

    def frames_of(specimen: dict) -> dict:
        path = bit_path(args.build, specimen)
        if specimen["specimen_id"] not in frames_cache:
            if not path.is_file():
                raise FileNotFoundError(path)
            frames_cache[specimen["specimen_id"]] = parse_frames(path, cols, layout)["frames"]
        return frames_cache[specimen["specimen_id"]]

    specimen_records = []
    for specimen in doc["specimens"]:
        path = bit_path(args.build, specimen)
        attestation_path = path.parent / "attestation.json"
        block = grid[specimen["tile"]]["bits"]["CLB_IO_CLK"]
        record = {
            "specimen_id": specimen["specimen_id"],
            "split": specimen["split"],
            "variant": specimen["variant"],
            "loc_site": specimen["site"],
            "tile": specimen["tile"],
            "tile_type": specimen["tile_type"],
            "tile_frame_base": block["baseaddr"],
            "bitstream": str(path.resolve().relative_to(REPO)) if path.is_file() else None,
            "bitstream_sha256": sha256_file(path) if path.is_file() else None,
        }
        if attestation_path.is_file():
            attestation = json.loads(attestation_path.read_text())
            attestation_cache[specimen["specimen_id"]] = attestation
            kept = attestation_dir / f"{specimen['specimen_id']}.json"
            kept.write_bytes(attestation_path.read_bytes())
            record["attestation"] = {
                "path": str(kept.resolve().relative_to(REPO)),
                "sha256": sha256_file(attestation_path),
                "schema_version": attestation["schema_version"],
                "resolved_loc": attestation["resolved"]["resolved_loc"],
                "checkpoint": attestation.get("checkpoint"),
            }
            record["design_source_sha256"] = attestation["inputs"].get("design_sha256")
            record["vivado_version"] = attestation["inputs"].get("vivado_version")
            record["part"] = attestation["inputs"].get("part")
            if attestation["outputs"].get(path.name) != record["bitstream_sha256"]:
                address_problems.append(f"{specimen['specimen_id']}: bitstream does not match its attestation")
        else:
            address_problems.append(f"{specimen['specimen_id']}: no attestation")
        specimen_records.append(record)

    # ---- endpoint pairs: (base, variant) per site instance ----------------------
    predictions_by_feature = {p["feature"]: p for p in doc["predictions"]}
    scopes_by_pair: dict[tuple[str, str], set[tuple[int, int, int]]] = {}
    pair_of_feature: dict[str, tuple[str, str]] = {}
    for specimen in doc["specimens"]:
        if not specimen["pair_features"]:
            continue
        base_id = f"{specimen['site']}_base"
        if base_id not in by_id:
            raise SystemExit(f"{specimen['specimen_id']}: no base specimen for its site")
        key = (base_id, specimen["specimen_id"])
        scope = scopes_by_pair.setdefault(key, set())
        for feature in specimen["pair_features"]:
            prediction = predictions_by_feature.get(feature)
            if prediction is None:
                raise SystemExit(f"{feature}: named as a pair feature but never predicted")
            pair_of_feature[feature] = key
            scope |= {address_tuple(a["address"]) for a in prediction["predicted_assignments"]}

    accounting = []
    false_positives: dict[tuple[str, str], list[dict]] = {}
    for (base_id, variant_id), scope in sorted(scopes_by_pair.items()):
        base, variant = by_id[base_id], by_id[variant_id]
        try:
            base_frames, variant_frames = frames_of(base), frames_of(variant)
        except FileNotFoundError as exc:
            address_problems.append(f"{base_id}/{variant_id}: missing bitstream {exc}")
            continue
        asserted_tiles = {base["tile"], variant["tile"]}
        raw = raw_diff(base_frames, variant_frames)
        buckets, class_claimed_out_of_scope = classify_diff(
            raw, scope, index, pattern, asserted_tiles)

        union = set().union(*buckets.values())
        overlaps = [(a, b) for i, a in enumerate(buckets) for b in list(buckets)[i + 1:]
                    if buckets[a] & buckets[b]]
        uncovered = raw - union
        if overlaps:
            address_problems.append(f"{base_id}/{variant_id}: buckets overlap {overlaps}")
        if uncovered:
            address_problems.append(f"{base_id}/{variant_id}: {len(uncovered)} raw diff bits in no bucket")
        if union - raw:
            address_problems.append(f"{base_id}/{variant_id}: {len(union - raw)} bucketed bits not in the raw diff")

        fp_bits = (buckets["ownership_unknown"] | buckets["unattributed"]
                   | class_claimed_out_of_scope)
        false_positives[(base_id, variant_id)] = as_addresses(fp_bits)
        accounting.append({
            "site": base["site"],
            "variant": variant["variant"],
            "specimen_ids": [base_id, variant_id],
            "raw_diff_bits": len(raw),
            "counts": {name: len(value) for name, value in buckets.items()},
            "buckets": {name: as_addresses(value) for name, value in buckets.items()},
            "partition_exact": not (overlaps or uncovered or (union - raw)),
            "false_positive_addresses": as_addresses(fp_bits),
        })

    # ---- per prediction: endpoint observations decide TP/FN ---------------------
    totals = {split: {"tp": 0, "fn": 0, "fp": 0,
                      "member_identity": {"pass": 0, "fail": 0}}
              for split in ("mine", "holdout")}
    observed_by_specimen: dict[str, dict[tuple[int, int, int], int]] = {}
    results = []
    for prediction in sorted(doc["predictions"], key=lambda p: (p["specimen_id"], p["feature"])):
        feature_specimen = by_id[prediction["specimen_id"]]
        pair = pair_of_feature.get(prediction["feature"])
        if pair is None:
            address_problems.append(f"{prediction['feature']}: no endpoint pair — cannot score")
            continue
        base_id, variant_id = pair
        other_id = variant_id if prediction["specimen_id"] == base_id else base_id
        try:
            feature_bits = read_tile_bits(
                frames_of(feature_specimen),
                grid[feature_specimen["tile"]]["bits"]["CLB_IO_CLK"])
            other_bits = read_tile_bits(
                frames_of(by_id[other_id]),
                grid[by_id[other_id]["tile"]]["bits"]["CLB_IO_CLK"])
        except FileNotFoundError as exc:
            address_problems.append(f"{prediction['feature']}: missing bitstream {exc}")
            continue

        split = prediction["split"]
        transition = prediction["expected_transition"]
        observed_assignments = []
        matched = True
        for item in prediction["predicted_assignments"]:
            token = item["token"].lstrip("!")
            after = feature_bits.get(token)
            before = other_bits.get(token)
            observed_assignments.append({
                "address": item["address"],
                "observed_value": after,
                "before_value": before,
                "after_value": after,
            })
            if after != item["expected_value"] or before != transition["before"] \
                    or after != transition["after"]:
                matched = False
            for specimen_id, value in ((prediction["specimen_id"], after), (other_id, before)):
                seen = observed_by_specimen.setdefault(specimen_id, {})
                key = address_tuple(item["address"])
                if seen.setdefault(key, value) != value:
                    address_problems.append(
                        f"{specimen_id}: two observed values for {item['address']}")

        assertion = prediction["semantic_assertion"]
        attestation = attestation_cache.get(prediction["specimen_id"])
        observed_semantic = (resolve_pointer(attestation, assertion["attestation_field"])
                             if attestation is not None else None)
        semantic_passed = semantic_verdict(matched, observed_semantic,
                                           assertion["expected_value"])
        if not semantic_passed:
            # A semantic finding, never an address problem. `semantic_findings` is
            # reported and carried into the record; it must not reach the address
            # decision, or a naming claim could sink an addressing result that the
            # bitstream itself confirmed. Both ways of failing are recorded, so the
            # count and the findings list cannot disagree.
            reason = (f"attestation field {assertion['attestation_field']} is "
                      f"{observed_semantic!r}, preregistered "
                      f"{assertion['expected_value']!r}"
                      if matched else
                      "the addressing did not match, so the member this names was not "
                      "the one the evidence selected")
            semantic_findings.append(
                f"{prediction['feature']}: {reason} — the naming claim is not auditable")

        totals[split]["tp" if matched else "fn"] += 1
        totals[split]["member_identity"]["pass" if semantic_passed else "fail"] += 1
        results.append({
            "prediction_specimen_id": prediction["specimen_id"],
            "feature": prediction["feature"],
            "split": split,
            "rule_file": prediction["rule_file"],
            "baseline_specimen_id": other_id if other_id != prediction["specimen_id"] else base_id,
            "feature_specimen_id": prediction["specimen_id"],
            "predicted_assignments": prediction["predicted_assignments"],
            "expected_transition": transition,
            "semantic_assertion": assertion,
            "observed_assignments": observed_assignments,
            "semantic_outcome": {
                "kind": "member_identity",
                "semantic": True,
                "passed": semantic_passed,
                "predicted_member": assertion["predicted_member"],
                "attestation_field": assertion["attestation_field"],
                "expected_value": assertion["expected_value"],
                "observed_value": observed_semantic,
            },
            "verdict": "matched" if matched else "mismatched",
        })

    # FP is a pair-level count, not a per-result one: one address wrong in one pair is
    # one FP however many features that pair carries. Charged to the pair's split.
    for (base_id, variant_id), addresses in false_positives.items():
        split = by_id[variant_id]["split"]
        totals[split]["fp"] += len(addresses)

    print(f"\n  results: {len(results)} of {len(doc['predictions'])} predictions scored")
    for split in ("mine", "holdout"):
        t = totals[split]
        print(f"    {split:<8} tp={t['tp']:>4} fn={t['fn']:>4} fp={t['fp']:>4}  "
              f"member_identity {t['member_identity']['pass']}/"
              f"{t['member_identity']['pass'] + t['member_identity']['fail']}")
    print(f"\n  pair accounting: {len(accounting)} pairs, "
          f"{sum(1 for a in accounting if not a['partition_exact'])} not exact")
    for record in accounting:
        counts = record["counts"]
        if counts["ownership_unknown"] or counts["unattributed"] or record["false_positive_addresses"]:
            print(f"    {record['site']}/{record['variant']:<12} raw={record['raw_diff_bits']:>4} "
                  f"scope={counts['in_scope']:>3} ecc={counts['frame_ecc']:>3} "
                  f"db={counts['db_attributed']:>3} unk={counts['ownership_unknown']:>3} "
                  f"unatt={counts['unattributed']:>3} FP={len(record['false_positive_addresses'])}")

    holdout = totals["holdout"]
    committed_holdout = doc["totals"]["holdout_predictions"]
    decision = address_decision(totals, accounting, address_problems, committed_holdout)
    semantic_decision = "FAIL" if holdout["member_identity"]["fail"] else "PASS"
    print(f"\n  holdout ADDRESS decision: {decision}")
    print(f"  tp={holdout['tp']}/{committed_holdout} fn={holdout['fn']} fp={holdout['fp']}")
    print(f"  holdout SEMANTIC decision (isolated, never contributes to the above): "
          f"{semantic_decision}")
    print(f"  member_identity pass={holdout['member_identity']['pass']} "
          f"fail={holdout['member_identity']['fail']}")
    for problem in address_problems[:15]:
        print(f"  ADDRESS PROBLEM {problem}")
    if len(address_problems) > 15:
        print(f"  ... and {len(address_problems) - 15} more")
    for finding in semantic_findings[:15]:
        print(f"  SEMANTIC FINDING {finding}")
    if len(semantic_findings) > 15:
        print(f"  ... and {len(semantic_findings) - 15} more")

    if args.out:
        args.out.write_text(json.dumps({
            "schema": "gate_measurement",
            "schema_version": "1.4.0",
            "bit_class": doc["bit_class"],
            "prediction_commitment": {
                "run_id": args.run.name,
                "path": str(pred_path.resolve().relative_to(REPO)),
                "sha256": digest,
                "schema_version": doc["schema_version"],
                "seed": doc["seed"],
                "totals": doc["totals"],
            },
            "split_policy": doc["split_policy"],
            "specimens": specimen_records,
            "totals": totals,
            "results": results,
            "accounting": accounting,
            "decision": decision,
            "semantic_decision": semantic_decision,
            # Two lists, deliberately. `address_problems` sinks the address decision;
            # `semantic_findings` is reported and never does. Merging them back into one
            # `problems` field would restore the isolation defect at the record level.
            "address_problems": address_problems,
            "semantic_findings": semantic_findings,
        }, indent=2) + "\n")
        print(f"  wrote {args.out}")
    # The exit code follows the ADDRESS decision. A semantic-only failure exits zero and
    # says so loudly above; that is the 1.4 contract, not leniency.
    return 0 if decision == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

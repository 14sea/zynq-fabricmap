#!/usr/bin/env python3
"""Mine-only bit-accounting DIAGNOSTIC for `clb_ff_config`. NOT a measurement.

`docs/ff_builder_design.md` §10 stops the ladder before holdout if the mine smoke
produces a false positive — but §7.6 forbids `gate_measure_ff.py` on an incomplete run,
and the smoke is incomplete by construction (15/120, 23/184). So that stop condition was
not satisfied by the smoke; it was **unevaluated**. This tool evaluates it, and nothing
else.

Three properties make it safe to run against an incomplete matrix:

* **It reuses `gate_measure_ff.py`'s bucketing and false-positive core verbatim** —
  `raw_diff`, `classify_diff`, `committed_pairs`, `as_addresses`. A second classifier
  that bucketed bits even slightly differently would answer a question nobody is going
  to ask, and would be exactly the kind of after-the-fact reclassification the ordering
  discipline exists to prevent.
* **It refuses any site whose committed split is not `mine`.** Mine evidence is already
  spent and can never score; holdout evidence is not to be looked at one convenient
  piece at a time.
* **Its output is marked `diagnostic_only: true`, `certifiable: false`,
  `complete: false`**, is written outside `gate_runs/`, and carries no
  `schema_version` — so `host/verify_certificate.py` and `gate_certify_ff.py` cannot
  consume it even by accident.

Usage:
    scripts/diag_measure_ff_mine.py --build build/gate_ff_formal \\
        --out build/gate_ff_formal/mine_diagnostic.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from bitstream_frames import column_map, device_layout, parse_frames  # noqa: E402
from decode_groups import read_tile_bits  # noqa: E402
from gate_build_ff_formal import (  # noqa: E402  — the artifact gate, not a second one
    check_instance_scope,
    check_site_mapping,
    load_commitment,
    plan_nodes,
    verified_state,
)
from gate_measure_ff import (  # noqa: E402  — the core, reused rather than reimplemented
    BUCKETS,
    address_tuple,
    as_addresses,
    classify_diff,
    committed_pairs,
    false_positive_bits,
    raw_diff,
)
from specimen_diff import tile_index  # noqa: E402

COMMITMENT = REPO / "gate_runs/run_2026_08_05_ff/predictions.json"
COMMITTED_SHA256 = "5440ef27acbd5b4f624cae54f4ffad89b3f656c1e6e5fa35b29226ff0d1b2e51"
TILEGRID = REPO / "data/prjxray/zynq7/xc7z010/tilegrid.json"
SPEC = REPO / "data/subset_spec.json"
BIT_CLASS = "clb_ff_config"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mine_site(doc: dict) -> str:
    """The one committed site whose split is `mine`, refusing anything else."""
    mine = sorted({s["site"] for s in doc["specimens"] if s["split"] == "mine"})
    if len(mine) != 1:
        raise SystemExit(f"expected exactly one mine site in the commitment, found {mine}")
    return mine[0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, required=True,
                    help="the builder's output root (…/<site>/<variant>/spec.bit)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--site", default=None, help="defaults to the committed mine site")
    args = ap.parse_args()

    # The certification path is read from and never written to. `gate_runs/` is where
    # measurement records live and where the certifier looks; a diagnostic landing there
    # is one careless `--out` away from being read as evidence.
    out = args.out.resolve()
    if out.is_relative_to((REPO / "gate_runs").resolve()):
        raise SystemExit(
            f"refusing to write a diagnostic into the certification path: {out}\n"
            "  gate_runs/ holds measurement records. This is not one.")

    # Authority A and B, the counts, and the variant-set equality — the builder's own
    # startup checks, not a second copy of them.
    doc = load_commitment()
    if doc["bit_class"] != BIT_CLASS:
        raise SystemExit(f"commitment is for {doc['bit_class']}")

    site = args.site or mine_site(doc)
    check_instance_scope(doc, site)

    # ---- every artifact passes the builder's gate before a frame is parsed ----------
    # `frames_of` used to open `spec.bit` straight off the path. That bypassed
    # `verified_state()`, which the design requires of every artifact reader on every
    # code path — so a substituted bitstream, or a stamp whose recipe had drifted from
    # the committed sources, could still have produced a confident FP=0. The nodes are
    # rebuilt from the commitment here and each one must verify before anything is read.
    mapping = check_site_mapping(doc)
    nodes = {n["specimen_id"]: n for n in plan_nodes(doc, mapping, args.build.resolve(), site)}
    if len(nodes) != 23:
        raise SystemExit(f"{site}: expected 23 committed specimens, planned {len(nodes)}")
    for node in nodes.values():
        if node["kind"] == "derived":
            base_dcp = args.build.resolve() / site / "base" / "base.dcp"
            if not base_dcp.is_file():
                raise SystemExit(f"{node['specimen_id']}: base checkpoint missing {base_dcp}")
            node["base_dcp_sha256"] = sha256_file(base_dcp)
    for specimen_id, node in sorted(nodes.items()):
        state, why = verified_state(node["outdir"], node)
        if state != "reuse":
            raise SystemExit(
                f"{specimen_id}: artifacts are {state} — {why}.\n"
                "  A diagnostic will not score artifacts the builder's own gate refuses.")

    grid = json.loads(TILEGRID.read_text())
    spec = json.loads(SPEC.read_text())
    pattern = re.compile(next(c["feature_regex"] for c in spec["bit_classes"]
                              if c["id"] == BIT_CLASS))
    cols, layout = column_map(), device_layout()
    index = tile_index()
    by_id = {s["specimen_id"]: s for s in doc["specimens"]}

    frames_cache: dict[str, dict] = {}

    def frames_of(specimen_id: str) -> dict:
        # The path comes from the verified node, never from a path convention rebuilt
        # here — the whole point of the gate above is that these are the files it
        # checked, and a second way of naming them would be a second way of being wrong.
        if specimen_id not in frames_cache:
            path = nodes[specimen_id]["outdir"] / "spec.bit"
            frames_cache[specimen_id] = parse_frames(path, cols, layout)["frames"]
        return frames_cache[specimen_id]

    scopes_by_pair, pair_of_feature = committed_pairs(doc)
    mine_pairs = {key: scope for key, scope in scopes_by_pair.items()
                  if all(by_id[i]["site"] == site for i in key)}
    mine_predictions = [p for p in doc["predictions"] if by_id[p["specimen_id"]]["site"] == site]
    if len(mine_pairs) != 21 or len(mine_predictions) != 22:
        raise SystemExit(
            f"{site}: expected 21 committed pairs and 22 predictions, "
            f"found {len(mine_pairs)} and {len(mine_predictions)}")
    covered = {i for key in mine_pairs for i in key}
    if covered != set(nodes):
        raise SystemExit(
            f"{site}: the committed pairs do not cover exactly the 23 planned specimens "
            f"(missing {sorted(set(nodes) - covered)}, extra {sorted(covered - set(nodes))})")

    problems: list[str] = []
    accounting = []
    fp_total = 0
    for (base_id, variant_id), scope in sorted(mine_pairs.items()):
        base, variant = by_id[base_id], by_id[variant_id]
        try:
            base_frames, variant_frames = frames_of(base_id), frames_of(variant_id)
        except FileNotFoundError as exc:
            problems.append(f"{base_id}/{variant_id}: missing bitstream {exc}")
            continue
        raw = raw_diff(base_frames, variant_frames)
        buckets, class_claimed_out_of_scope = classify_diff(
            raw, scope, index, pattern, {base["tile"], variant["tile"]})

        union = set().union(*buckets.values())
        overlaps = [(a, b) for i, a in enumerate(buckets) for b in list(buckets)[i + 1:]
                    if buckets[a] & buckets[b]]
        uncovered = raw - union
        extra = union - raw
        if overlaps:
            problems.append(f"{base_id}/{variant_id}: buckets overlap {overlaps}")
        if uncovered:
            problems.append(f"{base_id}/{variant_id}: {len(uncovered)} raw bits in no bucket")
        if extra:
            problems.append(f"{base_id}/{variant_id}: {len(extra)} bucketed bits not in the raw diff")

        fp_bits = false_positive_bits(buckets, class_claimed_out_of_scope)
        fp_total += len(fp_bits)
        accounting.append({
            "specimen_ids": [base_id, variant_id],
            "variants": [base["variant"], variant["variant"]],
            "raw_diff_bits": len(raw),
            "counts": {name: len(value) for name, value in buckets.items()},
            "class_claimed_out_of_scope": len(class_claimed_out_of_scope),
            "false_positive_addresses": as_addresses(fp_bits),
            "partition_exact": not (overlaps or uncovered or extra),
        })

    # ---- TP / FN from the preregistered assignment and transition ------------------
    tp = fn = 0
    observed_by_specimen: dict[str, dict[tuple[int, int, int], int]] = {}
    predictions = []
    for prediction in sorted(mine_predictions, key=lambda p: p["feature"]):
        pair = pair_of_feature.get(prediction["feature"])
        if pair is None:
            problems.append(f"{prediction['feature']}: no endpoint pair")
            continue
        other_id, asserting_id = pair
        if asserting_id != prediction["specimen_id"]:
            raise SystemExit(f"{prediction['feature']}: pair does not name its asserting specimen")
        try:
            feature_bits = read_tile_bits(
                frames_of(asserting_id),
                grid[by_id[asserting_id]["tile"]]["bits"]["CLB_IO_CLK"])
            other_bits = read_tile_bits(
                frames_of(other_id),
                grid[by_id[other_id]["tile"]]["bits"]["CLB_IO_CLK"])
        except FileNotFoundError as exc:
            problems.append(f"{prediction['feature']}: missing bitstream {exc}")
            continue
        transition = prediction["expected_transition"]
        matched = True
        for item in prediction["predicted_assignments"]:
            token = item["token"].lstrip("!")
            after, before = feature_bits.get(token), other_bits.get(token)
            if after != item["expected_value"] or before != transition["before"] \
                    or after != transition["after"]:
                matched = False
            for specimen_id, value in ((asserting_id, after), (other_id, before)):
                seen = observed_by_specimen.setdefault(specimen_id, {})
                key = address_tuple(item["address"])
                if seen.setdefault(key, value) != value:
                    problems.append(f"{specimen_id}: two observed values for {item['address']}")
        tp += 1 if matched else 0
        fn += 0 if matched else 1
        predictions.append({"feature": prediction["feature"],
                            "specimen_id": asserting_id,
                            "comparison_specimen_id": other_id,
                            "matched": matched})

    ownership_unknown = sum(a["counts"]["ownership_unknown"] for a in accounting)
    unattributed = sum(a["counts"]["unattributed"] for a in accounting)
    partition_exact = all(a["partition_exact"] for a in accounting)

    report = {
        # No `schema_version`: this must not look like a certificate to any consumer.
        "kind": "clb_ff_config mine bit-accounting diagnostic",
        "diagnostic_only": True,
        "certifiable": False,
        "complete": False,
        "not_a_measurement": (
            "Produced outside the certification path against an incomplete matrix "
            "(15/120 implementations, 23/184 specimens). It evaluates the mine stop "
            "condition of docs/ff_builder_design.md §10 and nothing else. It is not a "
            "measurement record, must not be copied into gate_runs/, and is not input "
            "to gate_certify_ff.py or host/verify_certificate.py."),
        "commitment_sha256": COMMITTED_SHA256,
        "site": site,
        "split": "mine",
        "pairs_scored": len(accounting),
        "predictions_scored": len(predictions),
        "totals": {
            "false_positives": fp_total,
            "ownership_unknown": ownership_unknown,
            "unattributed": unattributed,
            "true_positives": tp,
            "false_negatives": fn,
            "partition_exact": partition_exact,
            "accounting_problems": len(problems),
        },
        "buckets_order": list(BUCKETS),
        "accounting": accounting,
        "predictions": predictions,
        "problems": problems,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")

    stop = (fp_total or ownership_unknown or unattributed or fn
            or not partition_exact or problems)
    print(f"site {site} (split mine) — DIAGNOSTIC ONLY, not a measurement")
    print(f"  pairs scored        : {len(accounting)}")
    print(f"  predictions scored  : {len(predictions)}")
    print(f"  false positives     : {fp_total}")
    print(f"  ownership_unknown   : {ownership_unknown}")
    print(f"  unattributed        : {unattributed}")
    print(f"  TP / FN             : {tp} / {fn}")
    print(f"  partition exact     : {partition_exact}")
    print(f"  accounting problems : {len(problems)}")
    for line in problems[:20]:
        print(f"    {line}")
    print(f"\nreport: {args.out}")
    if stop:
        print("\nSTOP CONDITION MET — do not build any holdout instance.")
        return 1
    print("\nStop condition not triggered. This says nothing about the holdout instances,")
    print("and it is not a certification result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Emit a certificate 1.4 (feature evidence model) from a measured `clb_ff_config` run.

The three rules this gate has always run on, unchanged:

* **Preregistered fields are copied, never recomputed.** `feature`, `split`,
  `rule_file`, `predicted_assignments`, `expected_transition` and `semantic_assertion`
  come verbatim from `predictions.json`. Recomputing them here would let a producer bug
  agree with itself and sail through the comparison that exists to catch it.
* **Every committed holdout key is emitted, or nothing is.** Reporting the subset that
  worked is the classic failure of a gate like this, and it is exactly what a run with
  112 place-and-route steps invites.
* **`status` is the address decision only.** `semantic_status` carries
  `member_identity` on its own; a semantic failure is never laundered into an address
  failure, nor an address failure hidden behind a passing semantic result.

What 1.4 adds for this class: TP and FN are the measured endpoint verdicts, which come
from the preregistered transition rather than from diff membership; FP is the fixed
profile rule recomputed per `(pair, address)`; `coverage.attested_count` is the number
of distinct asserted class entries, not the number of result records.

    scripts/gate_certify_ff.py --run gate_runs/<run> --out gate_runs/<run>/certificate.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specimen_diff import locate, tile_index  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data/MANIFEST.json"
BIT_CLASS = "clb_ff_config"

PREREGISTERED_RESULT_FIELDS = (
    "feature", "split", "rule_file", "predicted_assignments",
    "expected_transition", "semantic_assertion",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def needed_files(manifest: dict, measurement: dict, doc: dict) -> list[dict]:
    """Every frozen file a verifier needs to recompute this record, derived from it.

    Computed from the evidence rather than hardcoded, for the reason the mux certifier
    records: a fixed list missed the INT databases the bucket labels depend on, and
    would go on missing whatever a future run happened to touch. Over-pinning is
    harmless; under-pinning silently removes an anchor the recomputation rests on.
    """
    index = tile_index()
    types: set[str] = set()
    for record in measurement["accounting"]:
        for bits in record["buckets"].values():
            for bit in bits:
                for hit in locate(index, int(bit["far"], 16), bit["word"], bit["bit"]):
                    types.add(hit["type"])

    wanted = {f"prjxray/zynq7/segbits_{name.lower()}.db" for name in types}
    wanted |= {p["rule_file"] for p in doc["predictions"]}
    by_path = {f["path"]: f for f in manifest["files"]}
    files = [{"path": path, "sha256": by_path[path]["sha256"]}
             for path in sorted(wanted) if path in by_path]
    files += [{"path": f["path"], "sha256": f["sha256"]} for f in manifest["files"]
              if f["path"].endswith(("xc7z010/tilegrid.json", "part.yaml"))]
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--gate-timestamp",
                    help="when the gate actually ran (default: now). Re-emitting an "
                         "existing run under corrected accounting must not redate it")
    args = ap.parse_args()

    pred_path = args.run / "predictions.json"
    doc = json.loads(pred_path.read_text())
    measurement = json.loads((args.run / "measurement.json").read_text())
    manifest = json.loads(MANIFEST.read_text())

    if measurement["prediction_commitment"]["sha256"] != sha256_file(pred_path):
        raise SystemExit("measurement pins a different predictions hash — refusing to emit")
    if doc["bit_class"] != BIT_CLASS:
        raise SystemExit(f"predictions are for {doc['bit_class']}, not {BIT_CLASS}")

    predicted_by = {(p["specimen_id"], p["feature"]): p for p in doc["predictions"]}
    measured_by = {(r["prediction_specimen_id"], r["feature"]): r
                   for r in measurement["results"]}
    missing = sorted(set(predicted_by) - set(measured_by))
    if missing:
        raise SystemExit(f"{len(missing)} committed keys have no measurement, "
                         f"first {missing[0]} — refusing")
    extra = sorted(set(measured_by) - set(predicted_by))
    if extra:
        raise SystemExit(f"{len(extra)} measured keys were never committed, "
                         f"first {extra[0]} — refusing")

    feature_results = []
    for key, prediction in sorted(predicted_by.items()):
        result = measured_by[key]
        projection = {field: result[field] for field in PREREGISTERED_RESULT_FIELDS}
        if projection != {field: prediction[field] for field in PREREGISTERED_RESULT_FIELDS}:
            raise SystemExit(f"{key}: measured projection differs from the preregistered "
                             "prediction — refusing to emit")
        feature_results.append({
            # preregistered projection, verbatim
            "prediction_specimen_id": prediction["specimen_id"],
            "feature": prediction["feature"],
            "split": prediction["split"],
            "rule_file": prediction["rule_file"],
            "baseline_specimen_id": result["baseline_specimen_id"],
            "feature_specimen_id": result["feature_specimen_id"],
            "predicted_assignments": prediction["predicted_assignments"],
            "expected_transition": prediction["expected_transition"],
            "semantic_assertion": prediction["semantic_assertion"],
            # measured
            "observed_assignments": result["observed_assignments"],
            "semantic_outcome": result["semantic_outcome"],
            "verdict": result["verdict"],
        })

    committed_holdout = {key for key, p in predicted_by.items() if p["split"] == "holdout"}
    reported_holdout = {(r["prediction_specimen_id"], r["feature"]) for r in feature_results
                        if r["split"] == "holdout"}
    if committed_holdout != reported_holdout:
        raise SystemExit("holdout coverage incomplete — refusing to emit")

    specimens = [{k: v for k, v in s.items()
                  if k not in ("bitstream", "variant", "pair_features")}
                 for s in measurement["specimens"]]
    pair_accounting = [{k: v for k, v in record.items()
                        if k != "false_positive_addresses"}
                       for record in measurement["accounting"]]

    holdout = measurement["totals"]["holdout"]
    accounting = {"tp_count": holdout["tp"], "fp_count": holdout["fp"],
                  "fn_count": holdout["fn"]}
    semantic = {"member_identity": {
        "pass_count": holdout["member_identity"]["pass"],
        "fail_count": holdout["member_identity"]["fail"]}}

    partition_exact = all(record["partition_exact"] for record in pair_accounting)
    # `address_problems` only. `semantic_findings` is never an input here: a semantic
    # failure keeps status=passed and shows up in semantic_status alone, and reading the
    # measurement's merged problem list would put a naming claim back into the address
    # decision one layer down from where the measurement tool already isolates it.
    address_failed = (accounting["fn_count"] or accounting["fp_count"]
                      or accounting["tp_count"] != doc["totals"]["holdout_predictions"]
                      or not partition_exact
                      or bool(measurement["address_problems"]))
    semantic_failed = bool(semantic["member_identity"]["fail_count"])

    failure_reasons = []
    if address_failed:
        if accounting["fn_count"]:
            failure_reasons.append({"code": "holdout_false_negative",
                                    "detail": f"{accounting['fn_count']} holdout keys did not "
                                              "match the preregistered transition"})
        if accounting["fp_count"]:
            failure_reasons.append({"code": "holdout_false_positive",
                                    "detail": f"{accounting['fp_count']} unpredicted changed "
                                              "bits under the fixed 1.4 FP rule"})
        if not partition_exact:
            failure_reasons.append({"code": "partition_integrity",
                                    "detail": "at least one endpoint pair is not partitioned exactly"})
        for problem in measurement["address_problems"][:8]:
            failure_reasons.append({"code": "holdout_false_negative", "detail": problem})

    entries = next(c["entries"] for c in manifest["bit_classes"] if c["id"] == BIT_CLASS)
    asserted = sorted({r["feature"] for r in feature_results})
    now = args.gate_timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    certificate = {
        "schema": "fabric_bit_class_certificate",
        "schema_version": "1.4.0",
        "evidence_model": "feature",
        "profile": "production",
        "certificate_id": f"{args.run.name}_{BIT_CLASS}",
        "status": "failed" if address_failed else "passed",
        "semantic_status": "failed" if semantic_failed else "passed",
        "failure_reasons": failure_reasons,
        "prediction_commitment": measurement["prediction_commitment"],
        "gate_run": {"gate_id": args.run.name, "started_at": now, "completed_at": now,
                     "tool_versions": {"gate": "gate_measure_ff.py/1.4.0",
                                       "bitstream_differ": "specimen_diff.py/1.0.0",
                                       "certifier": "gate_certify_ff.py/1.4.0"}},
        "target": {"family": "zynq7", "device": "xc7z010", "part": "xc7z010clg400-1"},
        "frozen_inputs": {
            "manifest_schema_version": manifest["schema_version"],
            "freeze_stamp": manifest["freeze_stamp"],
            "spec": {"path": "data/subset_spec.json", "sha256": manifest["spec"]["sha256"]},
            "files": needed_files(manifest, measurement, doc),
        },
        "bit_class": {
            "id": BIT_CLASS, "tier": "content", "manifest_entries": entries,
            "split": {
                "mine_features": sorted({p["feature"] for p in doc["predictions"]
                                         if p["split"] == "mine"}),
                "holdout_features": sorted({p["feature"] for p in doc["predictions"]
                                            if p["split"] == "holdout"}),
            },
            # distinct asserted class entries, not result records: 1.4 §"coverage"
            "coverage": {"attested_count": len(asserted), "class_entry_count": entries},
            "accounting": accounting,
            "semantic_accounting": semantic,
            "decision_rule": "holdout_assignment_transition_exact and partition_exact "
                             "and fp_count == 0 and fn_count == 0",
            "semantic_rule": "member_identity is reported independently and never "
                             "contributes to status",
        },
        "specimens": specimens,
        "feature_results": feature_results,
        "pair_accounting": pair_accounting,
    }

    args.out.write_text(json.dumps(certificate, indent=2) + "\n")
    print(f"{args.out}: {len(specimens)} specimens, {len(feature_results)} feature results "
          f"({len(reported_holdout)} holdout keys)")
    print(f"  status={certificate['status']}  semantic_status={certificate['semantic_status']}")
    print(f"  tp={accounting['tp_count']} fp={accounting['fp_count']} fn={accounting['fn_count']}"
          f"  coverage {len(asserted)}/{entries}")
    print(f"  sha256 {sha256_file(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

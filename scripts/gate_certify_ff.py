#!/usr/bin/env python3
"""Emit a certificate 1.6 (feature evidence model) from a measured `clb_ff_config` run.

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

What 1.4 added for this class: TP and FN are the measured endpoint verdicts, which come
from the preregistered transition rather than from diff membership; FP is the fixed
profile rule recomputed per `(pair, address)`; `coverage.attested_count` is the number
of distinct asserted class entries, not the number of result records.

What 1.5 adds: `baseline_specimen_id` is no longer a field the certificate is free to
fill in. It is the preregistered `comparison_specimen_id`, and the verifier rejects any
other value, rebuilds the endpoint-pair set from the commitment and requires
`pair_accounting[]` to be exactly that set. So the pairing is copied here like every
other preregistered projection, never chosen.

What 1.6 adds: the certificate names the exact staged artifact set it was measured from
------------------------------------------------------------------------------------
Only a `gate_measurement` **1.6.0** is accepted. A 1.4 or 1.5 measurement is refused even
when it is internally perfect, and that is the point: those were produced by a tool that
joined its own paths under `build/` and copied attestations into the run directory, so
their references describe files a verifier's clone does not have and hashes of copies this
side made. There is no way to tell that from inside such a record — every field agrees
with every other. The version is the only honest discriminator, so it is a hard gate
rather than a floor.

From the accepted measurement this gate copies the `staging_manifest` reference
**verbatim** — the same object, not a re-derived one — and then, independently:

* resolves it with `safe_child`, re-reads it in one read, recomputes its sha256 and
  validates it against `schemas/specimen_staging.schema.json`;
* requires the manifest's own `prediction_commitment` to equal the certificate's, and both
  to equal what `predictions.json` says right now — recomputed here, not read back from
  the measurement, because a measurement that agrees with itself proves nothing about the
  commitment it claims;
* requires the specimen set to be exactly the manifest's, exactly the commitment's, and
  exactly `totals.specimens`;
* requires every specimen's `bitstream` and `attestation` reference to equal its manifest
  entry **field for field**. `host/verify_certificate.load_feature_staging` compares those
  dicts for equality, so anything normalised, decorated or recomputed here is rejected
  there — one layer too late to be useful.

Finally the candidate is verified by the real consumer, `host/verify_certificate.py
--require-production`, **before** it is put in place. A certificate that the verifier
would reject is not written at all: not as a draft, not with a warning. The gate that
emits evidence should not be the last one to find out it is invalid.

    scripts/gate_certify_ff.py --run gate_runs/<run> --out gate_runs/<run>/certificate.json
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO))
from host.verify_certificate import safe_child, validate_external_schema  # noqa: E402
from specimen_diff import locate, tile_index  # noqa: E402

MANIFEST = REPO / "data/MANIFEST.json"
STAGING_SCHEMA = REPO / "schemas/specimen_staging.schema.json"
VERIFIER = REPO / "host/verify_certificate.py"
BIT_CLASS = "clb_ff_config"
MEASUREMENT_VERSION = "1.6.0"
CERTIFICATE_VERSION = "1.6.0"
CERTIFIER_VERSION = "1.6.0"

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


def require_measurement(measurement: dict, doc: dict, digest: str, run_id: str,
                        pred_path: Path) -> None:
    """Refuse anything that is not a 1.6.0 measurement of *this* commitment.

    The version check is deliberately an equality and not a floor. 1.4 and 1.5 records are
    not weaker 1.6 ones: their specimen references point into a gitignored build tree and
    their attestation references describe copies the measurement tool made, and no field
    inside such a record reveals that — it is consistent with itself. Accepting one
    "because it looks complete" is the exact failure this class of gate exists to prevent.
    """
    if measurement.get("schema") != "gate_measurement":
        raise SystemExit(f"{measurement.get('schema')!r} is not a gate_measurement record")
    version = measurement.get("schema_version")
    if version != MEASUREMENT_VERSION:
        raise SystemExit(
            f"measurement is schema_version {version!r}; certificate "
            f"{CERTIFICATE_VERSION} requires exactly {MEASUREMENT_VERSION}.\n"
            "  A 1.4/1.5 measurement is refused even when internally consistent: it was\n"
            "  produced by a tool that built its own artifact paths and copied\n"
            "  attestations, so its references cannot be the ones a certificate pins.\n"
            "  Re-run scripts/gate_measure_ff.py against the staging manifest.")
    if measurement.get("bit_class") != BIT_CLASS:
        raise SystemExit(f"measurement is for {measurement.get('bit_class')!r}, not {BIT_CLASS}")

    reference = measurement.get("prediction_commitment")
    if not isinstance(reference, dict):
        raise SystemExit("measurement carries no prediction_commitment — refusing")
    # Recomputed from predictions.json, never read back from the measurement.
    expected = {"run_id": run_id, "sha256": digest,
                "schema_version": doc["schema_version"], "totals": doc["totals"]}
    for field, value in expected.items():
        if reference.get(field) != value:
            raise SystemExit(f"measurement prediction_commitment.{field} is "
                             f"{reference.get(field)!r}, not {value!r} — refusing to emit")
    if str(reference.get("seed")) != str(doc["seed"]):
        raise SystemExit("measurement prediction_commitment.seed differs from predictions.json")
    try:
        pinned = safe_child(REPO, reference["path"])
    except (ValueError, KeyError) as exc:
        raise SystemExit(f"measurement prediction_commitment.path: {exc}") from None
    if pinned != pred_path.resolve():
        raise SystemExit(f"measurement pins a different predictions.json: {reference['path']}")


def load_staging(measurement: dict, run_id: str) -> tuple[dict, dict]:
    """`(reference, entries_by_id)` — the manifest the measurement names, re-verified.

    The reference is *returned as it was found* so `main()` can copy that object into the
    certificate. Everything checked here is checked against the file on disk, so the
    verbatim copy is a copy of something that was independently established, not of
    something that was trusted.
    """
    reference = measurement.get("staging_manifest")
    if not isinstance(reference, dict):
        raise SystemExit("measurement carries no staging_manifest — refusing to emit a "
                         f"certificate {CERTIFICATE_VERSION} that cannot name its artifacts")
    try:
        path = safe_child(REPO, reference["path"])
    except (ValueError, KeyError) as exc:
        raise SystemExit(f"staging_manifest.path: {exc}") from None
    if not path.is_file():
        raise SystemExit(f"staging manifest does not exist: {reference['path']}")
    # One read: the bytes that are hashed are the bytes that are parsed.
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != reference.get("sha256"):
        raise SystemExit(f"staging manifest does not match the hash the measurement pins: "
                         f"{reference['path']}")
    try:
        manifest = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"staging manifest is not JSON: {exc}") from None
    findings = validate_external_schema(manifest, STAGING_SCHEMA, "staging manifest")
    if findings:
        raise SystemExit("staging manifest does not validate:\n  " + "\n  ".join(findings[:10]))
    if manifest["schema_version"] != reference.get("schema_version"):
        raise SystemExit("staging manifest schema_version differs from the pinned reference")
    if manifest["run_id"] != run_id:
        raise SystemExit(f"staging manifest names run {manifest['run_id']!r}, not {run_id!r}")
    if manifest["prediction_commitment"] != measurement["prediction_commitment"]:
        raise SystemExit("staging manifest and measurement disagree about the prediction "
                         "commitment — the verifier requires these to be equal")

    entries: dict[str, dict] = {}
    for index, entry in enumerate(manifest["specimens"]):
        if entry["specimen_id"] in entries:
            raise SystemExit(f"staging manifest specimens[{index}] duplicates "
                             f"{entry['specimen_id']!r}")
        entries[entry["specimen_id"]] = entry
    return reference, entries


def specimen_problems(specimens: list, entries: dict, committed: dict) -> list[str]:
    """Set equality against BOTH authorities, and every reference field for field.

    Two sets rather than one: the manifest says what was staged and the commitment says
    what was promised, and a certificate is a claim about the second measured through the
    first. Checking only one of them lets a staging that is complete-and-wrong, or a
    measurement that dropped a specimen the staging carried, pass.
    """
    problems: list[str] = []
    measured = {specimen["specimen_id"]: specimen for specimen in specimens}
    if len(measured) != len(specimens):
        problems.append("the measurement lists a specimen twice")
    for label, other in (("staging manifest", set(entries)), ("commitment", set(committed))):
        missing, extra = other - set(measured), set(measured) - other
        if missing or extra:
            problems.append(
                f"measured specimens differ from the {label} "
                f"(missing {len(missing)}, extra {len(extra)}; "
                f"first missing {sorted(missing)[:2]}, first extra {sorted(extra)[:2]})")

    for specimen_id in sorted(set(measured) & set(entries)):
        specimen, entry = measured[specimen_id], entries[specimen_id]
        for label in ("bitstream", "attestation"):
            # Field for field: `load_feature_staging` compares the certificate's
            # attestation reference with this entry for equality, so a normalised or
            # decorated copy fails there instead of here.
            if specimen.get(label) != entry[label]:
                problems.append(f"{specimen_id}: {label} reference is not the staging "
                                f"entry verbatim")
        if specimen.get("bitstream_sha256") != entry["bitstream"]["sha256"]:
            problems.append(f"{specimen_id}: bitstream_sha256 is not the staged hash")

    for specimen_id in sorted(set(measured) & set(committed)):
        specimen, plan = measured[specimen_id], committed[specimen_id]
        for field, planned in (("loc_site", plan["site"]), ("tile", plan["tile"]),
                               ("tile_type", plan["tile_type"]), ("split", plan["split"]),
                               ("build_seed", plan["build_seed"])):
            if specimen.get(field) != planned:
                problems.append(f"{specimen_id}: {field} is {specimen.get(field)!r}, "
                                f"committed {planned!r}")
    return problems


def verified_in_place(certificate: dict, out: Path) -> str:
    """Write, verify as the consumer will, and only then put it in place.

    A candidate that fails leaves nothing behind — not a draft, not a `.rejected` file.
    An invalid certificate on disk is worse than none: it is the shape of a result, and
    the next reader is as likely to be a person as a tool.
    """
    candidate = out.with_name(out.name + ".candidate")
    if candidate.exists():
        raise SystemExit(f"{candidate} exists; remove it deliberately")
    payload = json.dumps(certificate, indent=2) + "\n"
    try:
        candidate.write_text(payload)
        checked = subprocess.run(
            [sys.executable, str(VERIFIER), str(candidate), "--require-production"],
            cwd=REPO, capture_output=True, text=True, check=False)
        if checked.returncode != 0:
            raise SystemExit(
                "refusing to emit: the production verifier rejects this certificate.\n"
                "  Nothing was written.\n  "
                + "\n  ".join((checked.stdout + checked.stderr).strip().splitlines()[:12]))
        candidate.replace(out)
    finally:
        candidate.unlink(missing_ok=True)
    return hashlib.sha256(payload.encode()).hexdigest()


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

    if doc["bit_class"] != BIT_CLASS:
        raise SystemExit(f"predictions are for {doc['bit_class']}, not {BIT_CLASS}")
    require_measurement(measurement, doc, sha256_file(pred_path), args.run.name, pred_path)
    staging_reference, staged = load_staging(measurement, args.run.name)
    committed_specimens = {item["specimen_id"]: item for item in doc["specimens"]}
    if len(committed_specimens) != doc["totals"]["specimens"]:
        raise SystemExit(f"the commitment lists {len(committed_specimens)} distinct "
                         f"specimens, totals says {doc['totals']['specimens']}")
    found = specimen_problems(measurement["specimens"], staged, committed_specimens)
    if found:
        raise SystemExit("refusing to emit: {} specimen problem(s):\n  {}".format(
            len(found), "\n  ".join(found[:10])))

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
        # Both endpoints are preregistered from 1.5, so a measurement that scored against
        # some other baseline is caught here rather than at the verifier: emitting a
        # record we already know the consumer rejects would waste the reviewer's time and
        # look like an attempt to see whether it slips through.
        if result["baseline_specimen_id"] != prediction["comparison_specimen_id"]:
            raise SystemExit(f"{key}: measured baseline {result['baseline_specimen_id']!r} "
                             f"is not the preregistered comparison endpoint "
                             f"{prediction['comparison_specimen_id']!r} — refusing to emit")
        if result["feature_specimen_id"] != prediction["specimen_id"]:
            raise SystemExit(f"{key}: measured feature endpoint is not the preregistered "
                             "asserting specimen — refusing to emit")
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
                  if k not in ("bitstream", "variant", "pair_features", "pair_with")}
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
        "schema_version": CERTIFICATE_VERSION,
        "evidence_model": "feature",
        "profile": "production",
        "certificate_id": f"{args.run.name}_{BIT_CLASS}",
        "status": "failed" if address_failed else "passed",
        "semantic_status": "failed" if semantic_failed else "passed",
        "failure_reasons": failure_reasons,
        "prediction_commitment": measurement["prediction_commitment"],
        # Verbatim, by construction: the object the measurement carried, deep-copied so
        # nothing below can edit it, and never rebuilt from its parts. `load_staging`
        # above established what it points at; this line does not get to improve on it.
        "staging_manifest": copy.deepcopy(staging_reference),
        "gate_run": {"gate_id": args.run.name, "started_at": now, "completed_at": now,
                     # the version that actually produced each record, not a literal
                     # kept in step by hand — these disagreed for a whole schema cycle
                     "tool_versions": {"gate": f"gate_measure_ff.py/{measurement['schema_version']}",
                                       "bitstream_differ": "specimen_diff.py/1.0.0",
                                       "certifier": f"gate_certify_ff.py/{CERTIFIER_VERSION}"}},
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

    emitted = verified_in_place(certificate, args.out)
    print(f"{args.out}: {len(specimens)} specimens, {len(feature_results)} feature results "
          f"({len(reported_holdout)} holdout keys)")
    print(f"  status={certificate['status']}  semantic_status={certificate['semantic_status']}")
    print(f"  tp={accounting['tp_count']} fp={accounting['fp_count']} fn={accounting['fn_count']}"
          f"  coverage {len(asserted)}/{entries}")
    print(f"  staging {staging_reference['path']} ({len(staged)} specimens)")
    print(f"  verified by host/verify_certificate.py --require-production before writing")
    print(f"  sha256 {emitted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

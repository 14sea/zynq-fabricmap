#!/usr/bin/env python3
"""Emit a certificate from a measured gate run, against certificate schema 1.2.

Producer side of the handshake: the schema and the verifier are author-owned, this
emitter is not allowed to reinterpret them.  Two rules follow from that and are worth
stating because they are what keep the record honest:

* **Preregistered fields are copied, never regenerated.**  The six-field projection
  the certificate must reproduce (`prediction_specimen_id`, `feature`, `split`,
  `rule_file`, `predicted_assignments`, `expected_transition`) is taken verbatim from
  `predictions.json`.  Recomputing it here would let a producer bug agree with itself
  and pass a comparison that exists precisely to catch that.
* **Every committed holdout pair is emitted.**  Reporting a convenient subset is the
  classic failure mode of a gate like this, so the emitter refuses to write a
  certificate that does not cover the commitment.

    scripts/gate_certify.py --run gate_runs/run_2026_08_02_a --build build/gate \\
                            --out gate_runs/run_2026_08_02_a/certificate.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specimen_diff import diff  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data/MANIFEST.json"
HDL = REPO / "vivado/specimen/specimen_lut.v"

PREREG_FIELDS = ("prediction_specimen_id", "feature", "split", "rule_file",
                 "predicted_assignments", "expected_transition")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def addr_key(a: dict) -> tuple:
    return (a["address"]["far"].lower(), a["address"]["word"], a["address"]["bit"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--build", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    pred_path = args.run / "predictions.json"
    meas = json.loads((args.run / "measurement.json").read_text())
    doc = json.loads(pred_path.read_text())
    manifest = json.loads(MANIFEST.read_text())

    if meas["prediction_commitment"]["sha256"] != sha256_file(pred_path):
        raise SystemExit("measurement pins a different predictions hash — refusing to emit")
    if meas["decision"] != "PASS":
        print(f"note: emitting a FAILED certificate (measurement decision "
              f"{meas['decision']})", file=sys.stderr)

    # Same reason as gate_measure_mux: build/ is gitignored, so the attestations a
    # certificate pins are copied into the run directory and referenced there.
    att_dir = args.run / "attestations"
    att_dir.mkdir(exist_ok=True)
    hdl_sha = sha256_file(HDL)
    specimens, feature_results = [], []
    diff_cache: dict[tuple[str, str], dict] = {}

    for spec in doc["specimens"]:
        d = args.build / f"{spec['site']}_{spec['bel']}"
        base_bit = d / f"spec_{spec['base_init']}.bit"
        var_bit = d / f"spec_{spec['variant_init']}.bit"
        att_path = d / "attestation.json"
        kept = att_dir / f"{spec['site']}_{spec['bel']}.json"
        kept.write_bytes(att_path.read_bytes())
        att_rel = str(kept.resolve().relative_to(REPO))
        att = json.loads(att_path.read_text())
        tile_base = json.loads((REPO / "data/prjxray/zynq7/xc7z010/tilegrid.json").read_text())
        frame_base = tile_base[spec["tile"]]["bits"]["CLB_IO_CLK"]["baseaddr"].upper().replace("0X", "0x")

        common = {
            "split": spec["split"], "design_source_sha256": hdl_sha,
            "vivado_version": att["inputs"]["vivado_version"],
            "part": att["inputs"]["part"], "loc_site": spec["site"],
            "tile": spec["tile"], "tile_type": spec["tile_type"],
            "tile_frame_base": frame_base, "build_seed": int(doc["seed"], 16) & 0xFFFF,
            "attestation": {"path": att_rel, "sha256": sha256_file(att_path),
                            "schema_version": att["schema_version"]},
        }
        base_id = f"{spec['specimen_id']}__base"
        specimens.append({"specimen_id": base_id, **common,
                          "bitstream_sha256": sha256_file(base_bit)})
        specimens.append({"specimen_id": spec["specimen_id"], **common,
                          "bitstream_sha256": sha256_file(var_bit)})
        diff_cache[spec["specimen_id"]] = {
            "d": diff(base_bit, var_bit), "base_id": base_id}

    for p in doc["predictions"]:
        sid = p["specimen_id"]
        entry = diff_cache[sid]
        d_res, base_id = entry["d"], entry["base_id"]
        wanted = {addr_key(a) for a in p["predicted_assignments"]}

        observed_assignments, observed_diff = [], []
        for rec in d_res["attributed"] + d_res["ownership_unknown"]:
            k = (rec["far"].lower(), rec["word"], rec["bit"])
            if k not in wanted:
                continue
            addr = {"far": rec["far"].upper().replace("0X", "0x"),
                    "word": rec["word"], "bit": rec["bit"]}
            observed_assignments.append({"address": addr, "observed_value": rec["after"]})
            observed_diff.append({"address": addr, "before_value": rec["before"],
                                  "after_value": rec["after"]})

        far_touched = {r["address"]["far"].lower() for r in observed_diff}
        excluded = [{"address": {"far": r["far"].upper().replace("0X", "0x"),
                                 "word": r["word"], "bit": r["bit"]},
                     "before_value": r["before"], "after_value": r["after"],
                     "reason": r["reason"], "rule": r["rule"]}
                    for r in d_res["excluded_diff"] if r["far"].lower() in far_touched]

        # the preregistered projection, copied verbatim
        prereg = {"prediction_specimen_id": sid, "feature": p["feature"],
                  "split": p["split"], "rule_file": p["rule_file"],
                  "predicted_assignments": p["predicted_assignments"],
                  "expected_transition": p["expected_transition"]}
        feature_results.append({
            **prereg,
            "baseline_specimen_id": base_id, "feature_specimen_id": sid,
            "observed_assignments": observed_assignments,
            "observed_diff": observed_diff,
            "unattributed_diff": [],
            "exclusion_rules": d_res["exclusion_rules"],
            "excluded_diff": excluded,
            "verdict": "matched" if len(observed_assignments) == len(wanted) else "mismatched",
        })

    committed_holdout = {(p["specimen_id"], p["feature"]) for p in doc["predictions"]
                         if p["split"] == "holdout"}
    reported_holdout = {(r["prediction_specimen_id"], r["feature"]) for r in feature_results
                        if r["split"] == "holdout"}
    if committed_holdout != reported_holdout:
        raise SystemExit(f"holdout coverage incomplete: {len(committed_holdout - reported_holdout)} "
                         "committed pairs would be unreported — refusing to emit")

    t = meas["totals"]["holdout"]
    cert = {
        "schema": "fabric_bit_class_certificate",
        "schema_version": "1.2.0",
        "profile": "production",
        "certificate_id": f"{args.run.name}_clb_lut_init",
        "status": "passed" if meas["decision"] == "PASS" else "failed",
        "failure_reasons": [] if meas["decision"] == "PASS" else meas["problems"],
        "prediction_commitment": meas["prediction_commitment"],
        "gate_run": {
            "gate_id": args.run.name,
            "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tool_versions": {"gate": "gate_measure.py/1.0.0",
                              "bitstream_differ": "specimen_diff.py/1.0.0"},
        },
        "target": {"family": "zynq7", "device": "xc7z010", "part": "xc7z010clg400-1"},
        "frozen_inputs": {
            "manifest_schema_version": manifest["schema_version"],
            "freeze_stamp": manifest["freeze_stamp"],
            "spec": {"path": "data/subset_spec.json", "sha256": manifest["spec"]["sha256"]},
            "files": [{"path": f["path"], "sha256": f["sha256"]} for f in manifest["files"]
                      if f["path"].endswith(("segbits_clbll_l.db", "segbits_clblm_l.db",
                                             "xc7z010/tilegrid.json", "part.yaml"))],
        },
        "bit_class": {
            "id": doc["bit_class"], "tier": "content",
            "manifest_entries": next(c["entries"] for c in manifest["bit_classes"]
                                     if c["id"] == doc["bit_class"]),
            "split": {
                "mine_features": sorted({p["feature"] for p in doc["predictions"]
                                         if p["split"] == "mine"}),
                "holdout_features": sorted({p["feature"] for p in doc["predictions"]
                                            if p["split"] == "holdout"}),
            },
            "coverage": {"attested_count": len(feature_results),
                         "class_entry_count": next(c["entries"] for c in manifest["bit_classes"]
                                                   if c["id"] == doc["bit_class"])},
            "accounting": {"tp_count": t["tp"], "fp_count": t["fp"], "fn_count": t["fn"]},
            "decision_rule": "holdout_exact_match: fp_count == 0 and fn_count == 0",
        },
        "specimens": specimens,
        "feature_results": feature_results,
    }

    args.out.write_text(json.dumps(cert, indent=2) + "\n")
    print(f"{args.out}: {len(specimens)} specimens, {len(feature_results)} results "
          f"({len(reported_holdout)} holdout pairs), status {cert['status']}")
    print(f"  sha256 {sha256_file(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Emit a certificate 1.3 (group evidence model) from a measured clb_mux run.

Producer side of `docs/round6_handoff.md`. Two rules carried over from the 1.2 emitter,
for the same reasons:

* **Preregistered fields are copied, never recomputed.** `group`, `split`, `rule_file`,
  `scope` and `assertions` come verbatim from `predictions.json`. Recomputing them here
  would let a producer bug agree with itself and sail through the comparison that
  exists to catch exactly that.
* **Every committed holdout pair is emitted**, or nothing is. Reporting the convenient
  subset is the classic failure of a gate like this.

And one rule specific to 1.3: `status` is the **address** decision only.
`semantic_status` carries `member_identity` on its own. A semantic failure must never
be laundered into an address failure, nor an address failure hidden behind a passing
semantic result.

    scripts/gate_certify_mux.py --run gate_runs/run_2026_08_02_b \\
                                --out gate_runs/run_2026_08_02_b/certificate.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data/MANIFEST.json"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    pred_path = args.run / "predictions.json"
    doc = json.loads(pred_path.read_text())
    meas = json.loads((args.run / "measurement.json").read_text())
    manifest = json.loads(MANIFEST.read_text())

    if meas["prediction_commitment"]["sha256"] != sha256_file(pred_path):
        raise SystemExit("measurement pins a different predictions hash — refusing to emit")

    pred_by = {(p["specimen_id"], p["group"]): p for p in doc["predictions"]}
    meas_by = {(r["specimen_id"], r["group"]): r for r in meas["results"]}

    missing = sorted(set(pred_by) - set(meas_by))
    if missing:
        raise SystemExit(f"{len(missing)} committed pairs have no measurement — refusing")

    group_results = []
    for key, p in sorted(pred_by.items()):
        r = meas_by[key]
        group_results.append({
            # preregistered projection, verbatim
            "prediction_specimen_id": p["specimen_id"],
            "group": p["group"],
            "split": p["split"],
            "rule_file": p["rule_file"],
            "scope": p["scope"],
            "assertions": p["assertions"],
            # measured
            "decoded_members": r["decoded_members"],
            "observed_assignment": r["observed_assignment"],
            "assertion_outcomes": r["assertion_outcomes"],
        })

    specimens = [{k: v for k, v in s.items() if k != "bitstream"}
                 for s in meas["specimens"]]

    addr = {k: {"pass_count": meas["totals"]["holdout"][k]["pass"],
                "fail_count": meas["totals"]["holdout"][k]["fail"]}
            for k in ("group_exclusivity", "scope_assignment")}
    sem = {"member_identity": {
        "pass_count": meas["totals"]["holdout"]["member_identity"]["pass"],
        "fail_count": meas["totals"]["holdout"]["member_identity"]["fail"]}}

    address_failed = any(v["fail_count"] for v in addr.values()) or bool(meas["problems"])
    semantic_failed = bool(sem["member_identity"]["fail_count"])

    committed_holdout = {k for k, p in pred_by.items() if p["split"] == "holdout"}
    reported_holdout = {(g["prediction_specimen_id"], g["group"]) for g in group_results
                        if g["split"] == "holdout"}
    if committed_holdout != reported_holdout:
        raise SystemExit("holdout coverage incomplete — refusing to emit")

    entries = next(c["entries"] for c in manifest["bit_classes"] if c["id"] == doc["bit_class"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cert = {
        "schema": "fabric_bit_class_certificate",
        "schema_version": "1.3.0",
        "evidence_model": "group",
        "profile": "production",
        "claim_scope": "group_bit_set",
        "certificate_id": f"{args.run.name}_{doc['bit_class']}",
        "status": "failed" if address_failed else "passed",
        "semantic_status": "failed" if semantic_failed else "passed",
        "failure_reasons": meas["problems"] if address_failed else [],
        "prediction_commitment": meas["prediction_commitment"],
        "gate_run": {"gate_id": args.run.name, "started_at": now, "completed_at": now,
                     "tool_versions": {"gate": "gate_measure_mux.py/1.1.0",
                                       "bitstream_differ": "specimen_diff.py/1.0.0"}},
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
            "id": doc["bit_class"], "tier": "content", "manifest_entries": entries,
            "split": {
                "mine_groups": sorted({p["group"] for p in doc["predictions"]
                                       if p["split"] == "mine"}),
                "holdout_groups": sorted({p["group"] for p in doc["predictions"]
                                          if p["split"] == "holdout"}),
            },
            "coverage": {"attested_count": len(group_results),
                         "class_entry_count": entries},
            "address_accounting": addr,
            "semantic_accounting": sem,
            "decision_rule": "holdout_address_assertions: group_exclusivity.fail_count "
                             "== 0 and scope_assignment.fail_count == 0",
            "semantic_rule": "member_identity is reported independently and never "
                             "contributes to status",
        },
        "specimens": specimens,
        "group_results": group_results,
        "pair_accounting": meas["accounting"],
    }

    args.out.write_text(json.dumps(cert, indent=2) + "\n")
    print(f"{args.out}: {len(specimens)} specimens, {len(group_results)} group results "
          f"({len(reported_holdout)} holdout pairs)")
    print(f"  status={cert['status']}  semantic_status={cert['semantic_status']}")
    print(f"  sha256 {sha256_file(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

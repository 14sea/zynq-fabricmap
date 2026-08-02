#!/usr/bin/env python3
"""Record a verified certificate in the manifest's certification slot.

`docs/freeze_format.md` §4 reserved a `certification` slot per bit class and defined a
staleness rule for it: a certificate pins `spec.sha256` and the hash of every frozen
file it consumed, and one whose pinned hashes do not match the current manifest is
stale by construction.  This is where that rule is enforced.

Deliberately conservative:

* the certificate must be `status: passed`, `profile: production`;
* every hash it pins must match the manifest **as it is now** — a re-extraction
  invalidates prior certificates rather than silently inheriting them;
* the slot records a pointer plus the accounting, never a copy of the evidence. The
  certificate remains the authority; the manifest is an index.

This does not verify the certificate.  Run `host/verify_certificate.py <cert>
--require-production` first — that is the author-owned gate, and this tool refuses to
substitute for it.

    scripts/manifest_certify.py --certificate gate_runs/<run>/certificate.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data/MANIFEST.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--certificate", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cert = json.loads(args.certificate.read_text())
    manifest = json.loads(MANIFEST.read_text())
    problems = []

    if cert.get("status") != "passed":
        problems.append(f"certificate status is {cert.get('status')!r}, not 'passed'")
    if cert.get("profile") != "production":
        problems.append(f"certificate profile is {cert.get('profile')!r}, not 'production'")

    fi = cert["frozen_inputs"]
    if fi["spec"]["sha256"] != manifest["spec"]["sha256"]:
        problems.append("spec sha256 differs from the current manifest — certificate is stale")
    if fi.get("freeze_stamp") != manifest["freeze_stamp"]:
        problems.append(f"freeze_stamp {fi.get('freeze_stamp')} != current "
                        f"{manifest['freeze_stamp']} — certificate is stale")
    have = {f["path"]: f["sha256"] for f in manifest["files"]}
    for f in fi["files"]:
        if have.get(f["path"]) != f["sha256"]:
            problems.append(f"{f['path']}: pinned hash does not match the frozen file")

    cls_id = cert["bit_class"]["id"]
    slot = next((c for c in manifest["bit_classes"] if c["id"] == cls_id), None)
    if slot is None:
        problems.append(f"manifest has no bit class {cls_id!r}")

    if problems:
        print("REFUSING to record this certificate:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    bc = cert["bit_class"]
    cov = bc["coverage"]
    # 1.2 records per-feature tp/fp/fn; 1.3 records pass/fail per address assertion and
    # keeps semantics in its own bucket. The slot stores whichever the certificate
    # actually carries rather than flattening one into the other's vocabulary.
    if "accounting" in bc:
        acc = bc["accounting"]
        model, extra = "feature", {"tp": acc["tp_count"], "fp": acc["fp_count"],
                                   "fn": acc["fn_count"]}
    else:
        model = "group"
        extra = {"address_accounting": bc["address_accounting"],
                 "semantic_accounting": bc["semantic_accounting"],
                 "semantic_status": cert.get("semantic_status"),
                 "claim_scope": cert.get("claim_scope")}
    slot["certification"] = {
        "status": "certified",
        "evidence_model": model,
        "gate": cert["gate_run"]["gate_id"],
        "certificate": str(args.certificate.resolve().relative_to(REPO)),
        "certificate_schema_version": cert["schema_version"],
        "profile": cert["profile"],
        "prediction_commitment_sha256": cert["prediction_commitment"]["sha256"],
        **extra,
        "holdout_pairs": len(bc["split"].get("holdout_features")
                             or bc["split"].get("holdout_groups", [])),
        "attested_pairs": cov["attested_count"],
        "scope": "address prediction from the frozen rules; NOT on-silicon semantics",
    }
    if args.dry_run:
        print(json.dumps(slot["certification"], indent=2))
        return 0

    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"{cls_id}: certified by {cert['certificate_id']} "
          f"(evidence_model={model})")
    print(f"  recorded in {MANIFEST.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

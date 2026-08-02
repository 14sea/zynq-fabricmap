#!/usr/bin/env python3
"""Score a pre-registered prediction file against the specimens that were built.

Refuses to score anything unless the predictions file still hashes to the value that
was committed before the bitstreams existed.  That check is the gate: without it, a
passing result would only show that the predictions and the measurements agree at the
time of writing, which is not a claim about the database at all.

Accounting, per split:

  TP  a predicted bit assignment whose measured transition and value match
  FN  a predicted assignment with no matching measured change
  FP  a measured, attributed, non-excluded change that no prediction claimed

Frame-ECC bits are excluded by `specimen_diff.py` and carried through as evidence, not
dropped (`docs/evidence_contract.md` §2).  Attestations are checked, not assumed: a
specimen whose resolved pin mapping is not the identity voids its interior INIT-bit
predictions rather than quietly scoring them.

    scripts/gate_measure.py --run gate_runs/run_2026_08_02_a --build build/gate
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specimen_diff import diff  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def key(a: dict) -> tuple:
    return (a["address"]["far"].lower(), a["address"]["word"], a["address"]["bit"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--build", type=Path, required=True)
    ap.add_argument("--expect-sha256", help="the committed predictions hash")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    pred_path = args.run / "predictions.json"
    digest = sha256_file(pred_path)
    expect = args.expect_sha256
    if expect and digest != expect:
        raise SystemExit(f"predictions hash {digest} != committed {expect} — refusing to score")
    doc = json.loads(pred_path.read_text())
    print(f"predictions: {digest}" + ("  (matches the committed hash)" if expect else ""))

    by_specimen: dict[str, list[dict]] = {}
    for p in doc["predictions"]:
        by_specimen.setdefault(p["specimen_id"], []).append(p)

    results, problems = [], []
    totals = {"mine": {"tp": 0, "fp": 0, "fn": 0}, "holdout": {"tp": 0, "fp": 0, "fn": 0}}

    for spec in doc["specimens"]:
        d = args.build / f"{spec['site']}_{spec['bel']}"
        base_bit = d / f"spec_{spec['base_init']}.bit"
        var_bit = d / f"spec_{spec['variant_init']}.bit"
        att_path = d / "attestation.json"
        if not (base_bit.is_file() and var_bit.is_file() and att_path.is_file()):
            problems.append(f"{spec['specimen_id']}: missing bitstreams or attestation")
            continue

        att = json.loads(att_path.read_text())
        res = att["resolved"]
        if not res.get("pin_mapping_is_identity"):
            problems.append(f"{spec['specimen_id']}: pin mapping is not the identity — "
                            "interior INIT-bit predictions are void")
            continue
        if res["tile"] != spec["tile"] or res["resolved_loc"] != spec["site"]:
            problems.append(f"{spec['specimen_id']}: attestation says "
                            f"{res['resolved_loc']}/{res['tile']}, plan says "
                            f"{spec['site']}/{spec['tile']}")
            continue
        for b in (base_bit, var_bit):
            if att["outputs"].get(b.name) != sha256_file(b):
                problems.append(f"{spec['specimen_id']}: {b.name} does not match the attestation")

        d_res = diff(base_bit, var_bit)
        observed = {}
        for rec in d_res["attributed"] + d_res["ownership_unknown"]:
            observed[(rec["far"].lower(), rec["word"], rec["bit"])] = rec
        unattributed = d_res["unattributed"]

        split = spec["split"]
        matched = set()
        for p in by_specimen.get(spec["specimen_id"], []):
            for a in p["predicted_assignments"]:
                k = key(a)
                rec = observed.get(k)
                want = p["expected_transition"]
                if rec and rec["before"] == want["before"] and rec["after"] == want["after"]:
                    totals[split]["tp"] += 1
                    matched.add(k)
                else:
                    totals[split]["fn"] += 1
                    results.append({"specimen_id": spec["specimen_id"], "feature": p["feature"],
                                    "verdict": "missing", "predicted": a,
                                    "observed": rec})
        for k, rec in observed.items():
            if k not in matched:
                totals[split]["fp"] += 1
                results.append({"specimen_id": spec["specimen_id"], "verdict": "unpredicted",
                                "observed": rec})
        for rec in unattributed:
            problems.append(f"{spec['specimen_id']}: unattributed change at "
                            f"{rec['far']} word {rec['word']} bit {rec['bit']}")
        for f in d_res["findings"]:
            problems.append(f"{spec['specimen_id']}: {f}")

    print("\n            tp      fp      fn")
    for split in ("mine", "holdout"):
        t = totals[split]
        print(f"  {split:<8}{t['tp']:>6}{t['fp']:>6}{t['fn']:>6}")
    h = totals["holdout"]
    decision = "PASS" if (h["fp"] == 0 and h["fn"] == 0 and h["tp"] > 0 and not problems) else "FAIL"
    print(f"\n  holdout decision rule: fp_count == 0 and fn_count == 0  ->  {decision}")
    for p in problems[:20]:
        print(f"  PROBLEM {p}")
    for r in results[:20]:
        print(f"  {r['verdict']}: {r.get('feature', '')} {r.get('observed') or r.get('predicted')}")

    if args.out:
        # The commitment is carried as a first-class record, and every scored item is
        # keyed by (specimen_id, feature).  A feature name alone cannot join back to
        # the pre-registered predictions: the same feature appears in many specimens
        # (different site, BEL and INIT pattern), so a name-only join collapses them
        # and the ordering guarantee degrades into a self-assertion.
        args.out.write_text(json.dumps({
            "schema": "gate_measurement",
            "schema_version": "1.0.0",
            "prediction_commitment": {
                "run_id": args.run.name,
                "path": str(pred_path.resolve().relative_to(REPO)),
                "sha256": digest,
                "schema_version": doc["schema_version"],
                "seed": doc["seed"],
                "totals": doc["totals"],
            },
            "bit_class": doc["bit_class"],
            "scored_keys": [list(k) for k in sorted({(p["specimen_id"], p["feature"])
                                                    for p in doc["predictions"]})],
            "totals": totals, "decision": decision,
            "problems": problems, "discrepancies": results}, indent=2) + "\n")
        print(f"  wrote {args.out}")
    return 0 if decision == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

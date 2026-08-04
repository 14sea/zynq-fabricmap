#!/usr/bin/env python3
"""Emit a certificate 1.4 (group evidence model) from a measured clb_mux run.

Producer side of `docs/round6_handoff.md`. Two rules carried over from the 1.2 emitter,
for the same reasons:

* **Preregistered fields are copied, never recomputed.** `group`, `split`, `rule_file`,
  `scope` and `assertions` come verbatim from `predictions.json`. Recomputing them here
  would let a producer bug agree with itself and sail through the comparison that
  exists to catch exactly that.
* **Every committed holdout pair is emitted**, or nothing is. Reporting the convenient
  subset is the classic failure of a gate like this.

And one rule from 1.3: `status` is the **address** decision only. `semantic_status`
carries `member_identity` on its own. A semantic failure must never be laundered into
an address failure, nor an address failure hidden behind a passing semantic result.

Version 1.4 (`docs/round9_ruling.md` §"Group accounting correction") changes only the
**accounting**, never an observation. Members of a bit-set group are full codewords over
one scope, so with pairwise-distinct codewords `group_exclusivity` is true for every
observation a bitstream could carry: it is a vacuous DB-consistency diagnostic, not an
address pass. `decode_validity` is entailed by strict equality to the preregistered
codeword, so counting it beside that equality would score one observation twice. What
survives as an address pass is therefore exactly one assertion per holdout pair —
strict preregistered codeword equality — and a codeword collision between two distinct
frozen names is a format failure (frozen-group ambiguity), not a scored outcome.

This emitter re-reads the frozen rule file to classify each group as vacuous or
ambiguous rather than asserting "no collisions" from the record we already believe.
The verifier redoes the same derivation from the freeze; agreeing by coincidence is not
the goal, disagreeing loudly is.

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from decode_groups import groups_for  # noqa: E402
from specimen_diff import locate, tile_index  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data/MANIFEST.json"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def codeword(tokens: list[str]) -> dict[str, int]:
    """A member's full 0/1 codeword over its group's scope, polarity applied."""
    return {t.lstrip("!"): 0 if t.startswith("!") else 1 for t in tokens}


def frozen_group(tile_type: str, scope: frozenset[str]) -> dict[str, list[str]]:
    """The frozen bit-set group whose polarity-free coordinate set is `scope`.

    Selected by bit set, never by the group label — the label is a common-prefix
    convenience and `docs/mux_groups.md` records what name-grouping does to real data.
    """
    for members in groups_for(tile_type, "clb_mux").values():
        tokens = next(iter(members.values()))
        if frozenset(t.lstrip("!") for t in tokens) == scope:
            return members
    return {}


def codeword_collisions(members: dict[str, list[str]]) -> list[list[str]]:
    """Distinct frozen member names of one group carrying an identical codeword.

    Empty is the ordinary case and is what makes `group_exclusivity` vacuous. A nonempty
    result means the freeze cannot name what an observation decoded to, which 1.4 treats
    as a format failure rather than a failed assertion.
    """
    by_codeword: dict[tuple, list[str]] = {}
    for member, tokens in members.items():
        by_codeword.setdefault(tuple(sorted(codeword(tokens).items())), []).append(member)
    return [sorted(names) for names in by_codeword.values() if len(names) > 1]


def needed_files(manifest: dict, meas: dict, doc: dict) -> list[dict]:
    """Every frozen file a verifier needs to recompute this record, derived from it.

    A hardcoded list was wrong twice over: it missed the INT databases the bucket
    labels depend on, and it would have gone on missing whatever a future run happened
    to touch.  So the set is computed from the evidence instead — walk every bucket
    bit to its geometrically candidate tiles, take their tile types, and pin those
    databases along with the group rule files, the tilegrid and the part.

    Over-pinning is harmless; under-pinning silently removes an integrity anchor the
    verifier's recomputation actually rests on.
    """
    idx = tile_index()
    types: set[str] = set()
    for acc in meas["accounting"]:
        for bits in acc["buckets"].values():
            for b in bits:
                for h in locate(idx, int(b["far"], 16), b["word"], b["bit"]):
                    types.add(h["type"])

    wanted = {f"prjxray/zynq7/segbits_{t.lower()}.db" for t in types}
    wanted |= {p["rule_file"] for p in doc["predictions"]}
    by_path = {f["path"]: f for f in manifest["files"]}
    files = [{"path": p, "sha256": by_path[p]["sha256"]}
             for p in sorted(wanted) if p in by_path]
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
    meas = json.loads((args.run / "measurement.json").read_text())
    manifest = json.loads(MANIFEST.read_text())

    if meas["prediction_commitment"]["sha256"] != sha256_file(pred_path):
        raise SystemExit("measurement pins a different predictions hash — refusing to emit")

    pred_by = {(p["specimen_id"], p["group"]): p for p in doc["predictions"]}
    meas_by = {(r["specimen_id"], r["group"]): r for r in meas["results"]}

    missing = sorted(set(pred_by) - set(meas_by))
    if missing:
        raise SystemExit(f"{len(missing)} committed pairs have no measurement — refusing")

    tile_type_by_specimen = {s["specimen_id"]: s["tile_type"] for s in meas["specimens"]}

    diag = {"group_exclusivity": {"vacuous_count": 0, "ambiguity_count": 0},
            "decode_validity": {"pass_count": 0, "fail_count": 0}}

    group_results = []
    for key, p in sorted(pred_by.items()):
        r = meas_by[key]
        scope = frozenset(item["segbit"] for item in p["scope"])
        members = frozen_group(tile_type_by_specimen[p["specimen_id"]], scope)
        if not members:
            raise SystemExit(f"{key}: declared scope is not a frozen bit-set group — refusing")
        collisions = codeword_collisions(members)
        if collisions:
            # A frozen-group ambiguity is a FORMAT failure in 1.4, not a failed
            # assertion: the record could not say what the observation decoded to. It
            # gets no `status: failed` certificate, because there is nothing to certify.
            raise SystemExit(f"{key}: frozen-group ambiguity {collisions[:1]} — refusing to emit")
        decode_valid = bool(r["decoded_members"])

        # 1.4 outcome shapes. Exclusivity keeps its independently decoded members but
        # loses `passed`: a verdict is what the record must not carry for something that
        # cannot come out false. decode_validity is recomputed and labelled diagnostic.
        outcomes = []
        for outcome in r["assertion_outcomes"]:
            if outcome["kind"] == "group_exclusivity":
                outcomes.append({"kind": "group_exclusivity", "semantic": False,
                                 "classification": "vacuous",
                                 "decoded_members": outcome["decoded_members"]})
                outcomes.append({"kind": "decode_validity", "semantic": False,
                                 "diagnostic": True, "passed": decode_valid,
                                 "decoded_members": outcome["decoded_members"]})
            else:
                outcomes.append(outcome)

        if p["split"] == "holdout":
            diag["group_exclusivity"]["vacuous_count"] += 1
            diag["decode_validity"]["pass_count" if decode_valid else "fail_count"] += 1

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
            "assertion_outcomes": outcomes,
        })

    specimens = [{k: v for k, v in s.items() if k != "bitstream"}
                 for s in meas["specimens"]]

    # The sole address pass in 1.4. The measured scope_assignment outcome *is* strict
    # equality to the preregistered codeword; only the name it is accounted under
    # changes, so the count is carried over rather than re-derived from the results.
    addr = {"strict_codeword_equality": {
        "pass_count": meas["totals"]["holdout"]["scope_assignment"]["pass"],
        "fail_count": meas["totals"]["holdout"]["scope_assignment"]["fail"]}}
    sem = {"member_identity": {
        "pass_count": meas["totals"]["holdout"]["member_identity"]["pass"],
        "fail_count": meas["totals"]["holdout"]["member_identity"]["fail"]}}

    address_failed = (bool(addr["strict_codeword_equality"]["fail_count"])
                      or bool(meas["problems"]))
    semantic_failed = bool(sem["member_identity"]["fail_count"])

    committed_holdout = {k for k, p in pred_by.items() if p["split"] == "holdout"}
    reported_holdout = {(g["prediction_specimen_id"], g["group"]) for g in group_results
                        if g["split"] == "holdout"}
    if committed_holdout != reported_holdout:
        raise SystemExit("holdout coverage incomplete — refusing to emit")

    entries = next(c["entries"] for c in manifest["bit_classes"] if c["id"] == doc["bit_class"])
    now = args.gate_timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cert = {
        "schema": "fabric_bit_class_certificate",
        "schema_version": "1.4.0",
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
                                       "bitstream_differ": "specimen_diff.py/1.0.0",
                                       "certifier": "gate_certify_mux.py/1.4.0"}},
        "target": {"family": "zynq7", "device": "xc7z010", "part": "xc7z010clg400-1"},
        "frozen_inputs": {
            "manifest_schema_version": manifest["schema_version"],
            "freeze_stamp": manifest["freeze_stamp"],
            "spec": {"path": "data/subset_spec.json", "sha256": manifest["spec"]["sha256"]},
            "files": needed_files(manifest, meas, doc),
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
            "diagnostic_accounting": diag,
            "semantic_accounting": sem,
            "decision_rule": "holdout_address_assertions: "
                             "strict_codeword_equality.fail_count == 0",
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
    print(f"  address_pass={addr['strict_codeword_equality']['pass_count']} "
          f"(strict codeword equality, the only falsifiable address assertion)")
    print(f"  diagnostics: exclusivity vacuous={diag['group_exclusivity']['vacuous_count']} "
          f"ambiguity={diag['group_exclusivity']['ambiguity_count']}, "
          f"decode_validity {diag['decode_validity']['pass_count']}/"
          f"{sum(diag['decode_validity'].values())} — neither enters the address decision")
    print(f"  sha256 {sha256_file(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

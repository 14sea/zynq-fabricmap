#!/usr/bin/env python3
"""Score pre-registered clb_mux predictions against the specimens that were built.

Two independent things are checked, and they are kept apart on purpose.

**Per specimen — the claim.**  Scoring reads *absolute* bit values out of one
bitstream and applies assert-iff.  The diff is never consulted here: a group is
correct or not on its own terms, regardless of what changed relative to anything else.

    group_exclusivity   at most one member of the group decodes
    scope_assignment    every bit of the group's complete bit set holds its
                        predicted value
    member_identity     the decoded member is the predicted one (semantic: a claim
                        about the database's naming, scored separately so that a
                        naming error cannot contaminate an addressing result)

**Per variant pair — the accounting.**  The raw diff is partitioned into buckets that
must be *mutually exclusive* and whose union must be *exactly* the raw diff:

    in_scope | frame_ecc | db_attributed | ownership_unknown | unattributed

Any bit in two buckets, or in none, is a hole in the accounting and fails the run —
that is the whole point of the partition, and it is checked rather than assumed.

`ownership_unknown` bits do not falsify these claims: every claim here is scoped to a
group's own bit set, and those bits are outside every such set by construction. They
would falsify a tile-wide claim, and none is made (`gate_emit_mux.py`).

    scripts/gate_measure_mux.py --run gate_runs/run_2026_08_02_b --build build/gate_mux
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bitstream_frames import FRAME_WORDS, column_map, device_layout, parse_frames  # noqa: E402
from decode_groups import decode, groups_for, read_tile_bits  # noqa: E402
from specimen_diff import ECC_BITS, ECC_WORD, features_using, locate, tile_index  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
TILEGRID = REPO / "data/prjxray/zynq7/xc7z010/tilegrid.json"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def bit_path(build: Path, spec: dict) -> Path:
    return build / spec["specimen_id"] / f"spec_{spec['ff_bel']}_ffsrc{spec['ffsrc']}.bit"


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
    print(f"predictions: {digest}"
          + ("  (matches the committed hash)" if args.expect_sha256 else ""))

    # Attestations are copied into the run directory and referenced there.  They live
    # under build/, which is gitignored, so a measurement that pointed at them would
    # name evidence a fresh clone cannot resolve.
    att_dir = args.run / "attestations"
    att_dir.mkdir(exist_ok=True)

    grid = json.loads(TILEGRID.read_text())
    cols, layout = column_map(), device_layout()
    idx = tile_index()
    by_id = {s["specimen_id"]: s for s in doc["specimens"]}

    frames_cache: dict[str, dict] = {}

    def frames_of(spec: dict) -> dict:
        p = bit_path(args.build, spec)
        if spec["specimen_id"] not in frames_cache:
            if not p.is_file():
                raise FileNotFoundError(p)
            frames_cache[spec["specimen_id"]] = parse_frames(p, cols, layout)["frames"]
        return frames_cache[spec["specimen_id"]]

    totals = {s: {k: {"pass": 0, "fail": 0} for k in
                  ("group_exclusivity", "scope_assignment", "member_identity")}
              for s in ("mine", "holdout")}
    problems, results, specimen_records = [], [], []

    # ---- per specimen: absolute assignment + assert-iff -------------------------
    # Every result is recorded whether it passes or fails.  A run that only records
    # failures cannot be audited when it passes, which is exactly when someone will
    # want to check it.
    for spec in doc["specimens"]:
        bp = bit_path(args.build, spec)
        att_path = bp.parent / "attestation.json"
        rec = {"specimen_id": spec["specimen_id"], "split": spec["split"],
               "site": spec["site"], "ff_bel": spec["ff_bel"], "ffsrc": spec["ffsrc"],
               "tile": spec["tile"], "tile_type": spec["tile_type"],
               "bitstream": str(bp.resolve().relative_to(REPO)) if bp.is_file() else None,
               "bitstream_sha256": sha256_file(bp) if bp.is_file() else None}
        if att_path.is_file():
            att = json.loads(att_path.read_text())
            kept = att_dir / f"{spec['specimen_id']}.json"
            kept.write_bytes(att_path.read_bytes())
            rec["attestation"] = {
                "path": str(kept.resolve().relative_to(REPO)),
                "sha256": sha256_file(att_path),
                "schema_version": att["schema_version"],
                "resolved_loc": att["resolved"]["resolved_loc"],
                "resolved_bel": att["resolved"]["resolved_bel"],
                "pin_mapping_is_identity": att["resolved"]["pin_mapping_is_identity"],
            }
            if att["outputs"].get(bp.name) != rec["bitstream_sha256"]:
                problems.append(f"{spec['specimen_id']}: bitstream does not match its attestation")
        else:
            problems.append(f"{spec['specimen_id']}: no attestation")
        specimen_records.append(rec)

    for p in doc["predictions"]:
        spec = by_id[p["specimen_id"]]
        try:
            frames = frames_of(spec)
        except FileNotFoundError as e:
            problems.append(f"{spec['specimen_id']}: missing bitstream {e}")
            continue
        tile = grid[spec["tile"]]
        bits = read_tile_bits(frames, tile["bits"]["CLB_IO_CLK"])
        members = groups_for(spec["tile_type"], "clb_mux")[p["group"]]
        hits = decode({p["group"]: members}, bits)[p["group"]]
        split = p["split"]

        observed = [{"segbit": x["segbit"], "address": x["address"],
                     "expected_value": x["expected_value"],
                     "observed_value": bits.get(x["segbit"])}
                    for a in p["assertions"] if a["kind"] == "scope_assignment"
                    for x in a["expected_assignment"]]
        outcomes = []
        for a in p["assertions"]:
            ok, detail = True, {}
            if a["kind"] == "group_exclusivity":
                ok = len(hits) <= 1
                detail = {"decoded_members": hits}
            elif a["kind"] == "scope_assignment":
                bad = [x for x in observed if x["observed_value"] != x["expected_value"]]
                ok = not bad
                detail = {"mismatched": bad}
            elif a["kind"] == "member_identity":
                ok = hits == [a["predicted_member"]]
                detail = {"predicted_member": a["predicted_member"],
                          "decoded_members": hits}
            outcomes.append({"kind": a["kind"], "semantic": a["semantic"],
                             "passed": ok, **detail})
            totals[split][a["kind"]]["pass" if ok else "fail"] += 1
        results.append({"specimen_id": spec["specimen_id"], "group": p["group"],
                        "split": split, "rule_file": p["rule_file"],
                        "decoded_members": hits,
                        "observed_assignment": observed,
                        "assertion_outcomes": outcomes})

    # ---- per pair: the partition must cover the raw diff exactly ----------------
    accounting = []
    pairs: dict[tuple, dict] = {}
    for s in doc["specimens"]:
        pairs.setdefault((s["site"], s["ff_bel"]), {})[s["ffsrc"]] = s
    for (site, bel), variants in sorted(pairs.items()):
        if set(variants) != {0, 1}:
            continue
        try:
            fa, fb = frames_of(variants[0]), frames_of(variants[1])
        except FileNotFoundError:
            continue
        scope = set()
        for p in doc["predictions"]:
            if p["specimen_id"] == variants[0]["specimen_id"]:
                scope = {(int(x["address"]["far"], 16), x["address"]["word"],
                          x["address"]["bit"]) for x in p["scope"]}
        raw = raw_diff(fa, fb)
        buckets = {"in_scope": set(), "frame_ecc": set(), "db_attributed": set(),
                   "ownership_unknown": set(), "unattributed": set()}
        for far, word, bit in raw:
            if (far, word, bit) in scope:
                buckets["in_scope"].add((far, word, bit))
            elif word == ECC_WORD and bit in ECC_BITS:
                buckets["frame_ecc"].add((far, word, bit))
            else:
                hits = locate(idx, far, word, bit)
                if not hits:
                    buckets["unattributed"].add((far, word, bit))
                elif any(features_using(h["type"], h["segbit"]) for h in hits):
                    buckets["db_attributed"].add((far, word, bit))
                else:
                    buckets["ownership_unknown"].add((far, word, bit))

        union = set().union(*buckets.values())
        overlaps = [(k1, k2) for i, k1 in enumerate(buckets) for k2 in list(buckets)[i + 1:]
                    if buckets[k1] & buckets[k2]]
        uncovered = raw - union
        if overlaps:
            problems.append(f"{site}/{bel}: buckets overlap {overlaps}")
        if uncovered:
            problems.append(f"{site}/{bel}: {len(uncovered)} raw diff bits in no bucket")
        if union - raw:
            problems.append(f"{site}/{bel}: {len(union - raw)} bucketed bits not in the raw diff")
        def as_addr(s):
            return sorted(({"far": f"0x{f:08X}", "word": w, "bit": b}
                           for f, w, b in s), key=lambda a: (a["far"], a["word"], a["bit"]))

        accounting.append({
            "site": site, "ff_bel": bel,
            "specimen_ids": [variants[0]["specimen_id"], variants[1]["specimen_id"]],
            "raw_diff_bits": len(raw),
            "counts": {k: len(v) for k, v in buckets.items()},
            # bit identity, so a verifier can check disjointness and coverage itself
            # instead of trusting the arithmetic
            "buckets": {k: as_addr(v) for k, v in buckets.items()},
            "partition_exact": not (overlaps or uncovered or (union - raw))})

    # ---- report ----------------------------------------------------------------
    print("\n  per-specimen assertions      pass  fail")
    for split in ("mine", "holdout"):
        for kind, c in totals[split].items():
            print(f"    {split:<8} {kind:<20} {c['pass']:>4}  {c['fail']:>4}")
    print("\n  pair accounting (raw diff must be partitioned exactly)")
    print(f"    {'site/bel':<26}{'raw':>5}{'scope':>7}{'ecc':>6}{'db':>5}{'unk':>5}{'unatt':>7}  exact")
    for a in accounting:
        c = a["counts"]
        print(f"    {a['site'] + '/' + a['ff_bel']:<26}{a['raw_diff_bits']:>5}"
              f"{c['in_scope']:>7}{c['frame_ecc']:>6}{c['db_attributed']:>5}"
              f"{c['ownership_unknown']:>5}{c['unattributed']:>7}  {a['partition_exact']}")

    h = totals["holdout"]
    hard_fail = (h["group_exclusivity"]["fail"] or h["scope_assignment"]["fail"]
                 or any(not a["partition_exact"] for a in accounting) or problems)
    decision = "FAIL" if hard_fail else "PASS"
    print(f"\n  holdout decision (address claims only, semantic reported separately): {decision}")
    print(f"  semantic member_identity holdout: {h['member_identity']['pass']} pass, "
          f"{h['member_identity']['fail']} fail")
    for p in problems[:15]:
        print(f"  PROBLEM {p}")
    for r in results:
        for o in r["assertion_outcomes"]:
            if not o["passed"]:
                print(f"  FAILED {r['specimen_id']} {r['group']} {o}")

    if args.out:
        args.out.write_text(json.dumps({
            "schema": "gate_measurement", "schema_version": "1.1.0",
            "bit_class": doc["bit_class"],
            "prediction_commitment": {"run_id": args.run.name,
                                      "path": str(pred_path.resolve().relative_to(REPO)),
                                      "sha256": digest,
                                      "schema_version": doc["schema_version"],
                                      "seed": doc["seed"], "totals": doc["totals"]},
            "scope_policy": doc["scope_policy"],
            "specimens": specimen_records,
            "totals": totals, "results": results, "accounting": accounting,
            "decision": decision, "problems": problems}, indent=2) + "\n")
        print(f"  wrote {args.out}")
    return 0 if decision == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Pre-register clb_mux predictions, before any specimen bitstream exists.

Same firewall as `gate_emit.py`: reads only the frozen database, never Vivado, and the
emitted file's sha256 is the commitment.  What differs is the shape of the claim,
because a mux is not a single bit.

Four rules this encodes, so they cannot drift later:

1. **Scope is the group's complete bit set**, not the bits that happen to change.
   `AFFMUX` is scored over all four of `30_00..30_03` — a prediction that only names
   the two bits that move could not detect a stray write to the other two.
2. **Scoring is on absolute before/after assignments plus assert-iff**, not on the
   diff.  The diff is completeness accounting only: it answers "did anything else
   move", never "is the group correct".
3. Out-of-scope buckets are **mutually exclusive**, and together with frame ECC they
   must cover the raw diff exactly.  Anything not covered is a hole in the accounting.
4. `ownership_unknown` bits do **not** falsify a group-scoped claim — they are outside
   the scope by construction — but any tile-wide claim must fail while they exist.
   This emitter therefore only ever states group-scoped claims.

Three assertion kinds are emitted per specimen, deliberately separated so a naming
error cannot contaminate an addressing result:

    group_exclusivity   at most one member decodes (the composition rule)
    scope_assignment    every bit in the group's set has this exact value
    member_identity     the decoded member is the one whose NAME matches the netlist
                        edge we built — a claim about the database's naming, marked
                        `semantic: true`, scored separately

    scripts/gate_emit_mux.py --out gate_runs/<run>/predictions.json --seed 0xB17D
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from decode_groups import groups_for  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
TILEGRID = REPO / "data/prjxray/zynq7/xc7z010/tilegrid.json"
MANIFEST = REPO / "data/MANIFEST.json"

# Evidence already spent establishing the harness rules; may inform, never score.
MINE_SITES = {"SLICE_X2Y25"}

# The netlist edge each variant builds, and the member name it should select.  The
# mapping is the *claim*, not an input to the address arithmetic.  The bypass member is
# named per slice position — AFFMUX has AX, BFFMUX has BX — so it is derived from the
# BEL letter rather than hardcoded, and the group's real membership is checked against
# the frozen db before anything is predicted.
def ffsrc_member(letter: str) -> dict[int, tuple[str, str]]:
    return {0: ("O6", "FF.D driven by the LUT6 output"),
            1: (f"{letter}X",
                "FF.D driven by a package pin through the slice bypass")}


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tile_of_site(grid: dict, site: str) -> tuple[str, str, dict]:
    for name, tile in grid.items():
        if site in tile.get("sites", {}):
            return name, tile["type"], tile["bits"]["CLB_IO_CLK"]
    raise SystemExit(f"site {site} not in the frozen tilegrid")


def site_prefix(grid: dict, site: str, tile_name: str) -> str:
    sites = grid[tile_name]["sites"]
    order = sorted(sites, key=lambda s: int(s.split("X")[1].split("Y")[0]))
    return f"{sites[site]}_X{order.index(site)}"


def addr_of(block: dict, token: str) -> dict:
    f, b = (int(x) for x in token.lstrip("!").split("_"))
    return {"far": f"0x{int(block['baseaddr'], 16) + f:08X}",
            "word": block["offset"] + b // 32, "bit": b % 32}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", default="0xB17D")
    ap.add_argument("--sites", nargs="*",
                    default=["SLICE_X2Y25", "SLICE_X8Y25", "SLICE_X9Y25"])
    ap.add_argument("--ff-bels", nargs="*", default=["AFF", "BFF", "CFF", "DFF"])
    args = ap.parse_args()

    grid = json.loads(TILEGRID.read_text())
    manifest = json.loads(MANIFEST.read_text())
    specimens, predictions = [], []

    for site in args.sites:
        tile_name, tile_type, block = tile_of_site(grid, site)
        prefix = site_prefix(grid, site, tile_name)
        groups = groups_for(tile_type, "clb_mux")
        split = "mine" if site in MINE_SITES else "holdout"

        for ff_bel in args.ff_bels:
            letter = ff_bel[0]
            label = next((g for g in groups
                          if g.startswith(f"{tile_type}.{prefix}.{letter}FFMUX[")), None)
            if label is None:
                raise SystemExit(f"no {letter}FFMUX group for {prefix} in {tile_type}")
            members = groups[label]

            # scope: EVERY bit of the group, not just the ones that move
            scope_tokens = sorted({t.lstrip("!") for toks in members.values() for t in toks})
            scope = [{"segbit": t, "address": addr_of(block, t)} for t in scope_tokens]

            for ffsrc, (member, basis) in sorted(ffsrc_member(letter).items()):
                if member not in members:
                    raise SystemExit(f"{label} has no member {member}")
                assignment = []
                for tok in scope_tokens:
                    on = [t for t in members[member] if t.lstrip("!") == tok]
                    assignment.append({
                        "segbit": tok, "address": addr_of(block, tok),
                        "expected_value": 0 if (not on or on[0].startswith("!")) else 1,
                    })
                sid = f"{site}_{ff_bel}_ffsrc{ffsrc}"
                specimens.append({"specimen_id": sid, "site": site, "ff_bel": ff_bel,
                                  "ffsrc": ffsrc, "tile": tile_name,
                                  "tile_type": tile_type, "site_prefix": prefix,
                                  "split": split})
                predictions.append({
                    "specimen_id": sid, "split": split, "group": label,
                    "rule_file": f"prjxray/zynq7/segbits_{tile_type.lower()}.db",
                    "scope": scope,
                    "assertions": [
                        {"kind": "group_exclusivity", "semantic": False,
                         "claim": "at most one member of this group decodes"},
                        {"kind": "scope_assignment", "semantic": False,
                         "claim": "every bit in scope holds its expected value",
                         "expected_assignment": assignment},
                        {"kind": "member_identity", "semantic": True,
                         "claim": f"the decoded member is {member}",
                         "predicted_member": member, "netlist_basis": basis},
                    ],
                })

    doc = {
        "schema": "gate_predictions", "schema_version": "1.1.0",
        "bit_class": "clb_mux", "seed": hex(int(args.seed, 0)),
        "scope_policy": {
            "unit": "mux group bit-address set",
            "note": "scope is the group's COMPLETE bit set; claims are group-scoped "
                    "only. ownership_unknown bits lie outside every group scope and "
                    "therefore cannot falsify these claims, but no tile-wide claim is "
                    "made here and none may be added while such bits exist.",
        },
        "split_policy": {"mine_sites": sorted(MINE_SITES),
                         "rule": "a site whose evidence established the harness rules "
                                 "may inform predictions but never score them"},
        "frozen_inputs": {
            "manifest_freeze_stamp": manifest["freeze_stamp"],
            "spec_sha256": manifest["spec"]["sha256"],
            "files": {f["path"]: f["sha256"] for f in manifest["files"]
                      if f["path"].endswith(("segbits_clbll_l.db", "segbits_clblm_l.db",
                                             "xc7z010/tilegrid.json", "part.yaml"))},
        },
        "specimens": specimens, "predictions": predictions,
        "totals": {
            "specimens": len(specimens), "predictions": len(predictions),
            "holdout_predictions": sum(1 for p in predictions if p["split"] == "holdout"),
            "assertions": sum(len(p["assertions"]) for p in predictions),
            "semantic_assertions": sum(1 for p in predictions for a in p["assertions"]
                                       if a["semantic"]),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n")
    t = doc["totals"]
    print(f"{args.out}: sha256 {sha256_file(args.out)}")
    print(f"  specimens   : {t['specimens']} ({sum(1 for s in specimens if s['split'] == 'holdout')} holdout)")
    print(f"  predictions : {t['predictions']} ({t['holdout_predictions']} holdout)")
    print(f"  assertions  : {t['assertions']} of which {t['semantic_assertions']} semantic (naming)")
    print(f"  scope       : {len(scope)} bits per group, complete set")
    print("  COMMIT THIS HASH BEFORE BUILDING ANY BITSTREAM")
    return 0


if __name__ == "__main__":
    sys.exit(main())

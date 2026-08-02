#!/usr/bin/env python3
"""Emit the gate's predictions BEFORE any specimen bitstream exists.

The prediction gate's whole value is the ordering: predictions are written down and
hashed first, the specimens are built second, and the comparison is third.  If the
predictions were derived after looking at the diffs, a passing certificate would only
prove that we can describe what we saw.

So this step is deliberately blind to Vivado.  It reads the frozen database, applies
the normative arithmetic of `docs/freeze_format.md` §5, and writes:

  * the **specimen plan** — which sites, which BELs, which INIT patterns, chosen from a
    recorded seed so the plan is reproducible and not cherry-picked;
  * the **mine/holdout split** — mine features are the ones whose behaviour informed
    the harness rules (addressing, ECC, pin locking); holdout features were never
    inspected while building the harness;
  * for every specimen and feature, the **predicted bit assignment**: `(FAR, word, bit,
    expected_value)` plus the expected base->variant transition.

The emitted file's sha256 is the commitment.  `scripts/gate_measure.py` refuses to
score a run whose predictions file does not hash to the value recorded in the run.

    scripts/gate_emit.py --out build/gate/predictions.json --seed 0xB17D
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data/prjxray/zynq7"
TILEGRID = DB / "xc7z010/tilegrid.json"
MANIFEST = REPO / "data/MANIFEST.json"

# Sites the harness rules were established on: their evidence is already spent, so
# they can inform predictions but can never score them.
MINE_SITES = {"SLICE_X2Y25"}

LUT_LETTERS = ("A", "B", "C", "D")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tile_of_site(site: str) -> tuple[str, str, dict]:
    """site -> (tile name, tile type, block record), from the frozen tilegrid."""
    grid = json.loads(TILEGRID.read_text())
    for name, tile in grid.items():
        if site in tile.get("sites", {}):
            return name, tile["type"], tile["bits"]["CLB_IO_CLK"]
    raise SystemExit(f"site {site} not found in the frozen tilegrid")


def site_prefix(site: str, tile_name: str) -> str:
    """`SLICE_X8Y25` -> `SLICEM_X0`, per freeze_format §5.5 (lower X is index 0)."""
    grid = json.loads(TILEGRID.read_text())
    sites = grid[tile_name]["sites"]
    order = sorted(sites, key=lambda s: int(s.split("X")[1].split("Y")[0]))
    return f"{sites[site]}_X{order.index(site)}"


def segbits_for(tile_type: str) -> dict[str, list[str]]:
    table: dict[str, list[str]] = {}
    for line in (DB / f"segbits_{tile_type.lower()}.db").read_text().splitlines():
        toks = line.split()
        table[toks[0]] = toks[1:]
    return table


def predict(block: dict, tokens: list[str]) -> list[dict]:
    """freeze_format §5.3: segbit tokens -> absolute bit assignment."""
    base, off = int(block["baseaddr"], 16), block["offset"]
    out = []
    for tok in tokens:
        neg = tok.startswith("!")
        f, b = (int(x) for x in tok.lstrip("!").split("_"))
        out.append({
            "token": tok,
            "segbit": {"frame_offset": f, "bit_offset": b, "negated": neg},
            "address": {"far": f"0x{base + f:08X}", "word": off + b // 32, "bit": b % 32},
            "expected_value": 0 if neg else 1,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", default="0xB17D")
    ap.add_argument("--sites", nargs="*", default=["SLICE_X2Y25", "SLICE_X8Y25", "SLICE_X9Y25"])
    ap.add_argument("--bels", nargs="*", default=["A6LUT", "D6LUT"])
    ap.add_argument("--patterns", type=int, default=2,
                    help="random INIT patterns per (site, bel), besides the all-zero base")
    args = ap.parse_args()

    seed = int(args.seed, 0)
    rng = random.Random(seed)
    manifest = json.loads(MANIFEST.read_text())

    specimens, predictions = [], []
    for site in args.sites:
        tile_name, tile_type, block = tile_of_site(site)
        prefix = site_prefix(site, tile_name)
        rules = segbits_for(tile_type)
        for bel in args.bels:
            letter = bel[0]
            if letter not in LUT_LETTERS:
                raise SystemExit(f"unexpected BEL {bel}")
            feats = {n: f"{tile_type}.{prefix}.{letter}LUT.INIT[{n:02d}]" for n in range(64)}
            missing = [f for f in feats.values() if f not in rules]
            if missing:
                raise SystemExit(f"frozen db has no rule for {missing[0]} — cannot predict")
            for k in range(args.patterns):
                pattern = rng.getrandbits(64)
                sid = f"{site}_{bel}_{pattern:016x}"
                specimens.append({
                    "specimen_id": sid, "site": site, "bel": bel, "tile": tile_name,
                    "tile_type": tile_type, "site_prefix": prefix,
                    "base_init": "0000000000000000", "variant_init": f"{pattern:016x}",
                    "split": "mine" if site in MINE_SITES else "holdout",
                })
                for n in range(64):
                    if not (pattern >> n) & 1:
                        continue          # unchanged bits predict no transition
                    feature = feats[n]
                    assign = predict(block, rules[feature])
                    if len(assign) != 1:
                        raise SystemExit(f"{feature}: expected a single-bit rule, got {rules[feature]}")
                    predictions.append({
                        "specimen_id": sid, "feature": feature,
                        "split": "mine" if site in MINE_SITES else "holdout",
                        "rule_file": "prjxray/zynq7/segbits_%s.db" % tile_type.lower(),
                        "predicted_assignments": assign,
                        "expected_transition": {"before": 0, "after": 1},
                    })

    doc = {
        "schema": "gate_predictions",
        "schema_version": "1.0.0",
        "bit_class": "clb_lut_init",
        "seed": hex(seed),
        "split_policy": {
            "mine_sites": sorted(MINE_SITES),
            "rule": "a site whose evidence established the harness rules (addressing, "
                    "frame ECC, LOCK_PINS) can inform predictions but never score them",
        },
        "frozen_inputs": {
            "manifest_freeze_stamp": manifest["freeze_stamp"],
            "spec_sha256": manifest["spec"]["sha256"],
            "files": {f["path"]: f["sha256"] for f in manifest["files"]
                      if f["path"].endswith(("segbits_clbll_l.db", "segbits_clblm_l.db",
                                             "tilegrid.json", "part.yaml"))},
        },
        "specimens": specimens,
        "predictions": predictions,
        "totals": {
            "specimens": len(specimens),
            "predictions": len(predictions),
            "holdout_predictions": sum(1 for p in predictions if p["split"] == "holdout"),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"{args.out}: sha256 {sha256_file(args.out)}")
    print(f"  specimens   : {len(specimens)} "
          f"({sum(1 for s in specimens if s['split'] == 'holdout')} holdout)")
    print(f"  predictions : {len(predictions)} "
          f"({doc['totals']['holdout_predictions']} holdout)")
    print("  COMMIT THIS HASH BEFORE BUILDING ANY BITSTREAM")
    return 0


if __name__ == "__main__":
    sys.exit(main())

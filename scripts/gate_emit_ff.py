#!/usr/bin/env python3
"""Emit the `clb_ff_config` prediction plan BEFORE any specimen bitstream exists.

Same ordering as `gate_emit.py`, and for the same reason: predictions are written down
and hashed first, specimens are built second, comparison is third. Predictions derived
after looking at a diff would only prove we can describe what we saw.

What is specific to this class, all of it recomputed from the freeze rather than assumed:

* **176 entries, every one single bit**, 22 per site instance across 8 site instances
  (4 tile types x 2 slice positions). The emitter refuses unless every one of them is
  covered by exactly one `(specimen, feature)` key — a plan that quietly skipped an
  entry would move the coverage denominator after the fact.
* **The asserted endpoint is a prediction, not bookkeeping.** Four features are claimed
  to be asserted in the *baseline* design because of the `Z` polarity convention
  (`ZINI = 1` when `INIT = 0`, measured; `ZRST`, `CEUSEDMUX`, `SRUSEDMUX`, `FFSYNC`
  read the same way). If a reading is backwards the gate records FN and the certificate
  fails. That is the intended behaviour.
* Every prediction carries one `member_identity` semantic assertion resolved by JSON
  pointer into the feature endpoint's attestation. It says what the producer claims the
  frozen name means; it is not a silicon-behaviour claim.

`docs/ff_preregistration_plan.md` is the reviewable statement of all of this, and the
commitment is **held** until the author rules on it — see `PREREGISTRATION_HOLD`.

    scripts/gate_emit_ff.py --out build/ff_draft/predictions.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data/prjxray/zynq7"
TILEGRID = DB / "xc7z010/tilegrid.json"
MANIFEST = REPO / "data/MANIFEST.json"
SPEC = REPO / "data/subset_spec.json"

# The author holds pre-registration: emitting a commitment permanently fixes the key
# space, the completeness rule and the coverage denominator. While this is True the
# emitter will only write a draft under `build/` (gitignored), so the plan can be read
# and argued with while nothing is frozen. Lifting the hold is a one-line commit, which
# is the point — it leaves a reviewable record of who lifted it and when.
PREREGISTRATION_HOLD = True

# Sites whose evidence established the harness rules: they may inform predictions and
# can never score them.
MINE_SITES = {"SLICE_X2Y25"}

# One site instance per (tile type, slice index), all in clock row Y25 so the clock
# region never varies across the run. See docs/ff_preregistration_plan.md §1.
SITE_INSTANCES = (
    "SLICE_X2Y25", "SLICE_X3Y25",      # CLBLL_L_X2Y25
    "SLICE_X14Y25", "SLICE_X15Y25",    # CLBLL_R_X11Y25
    "SLICE_X8Y25", "SLICE_X9Y25",      # CLBLM_L_X6Y25
    "SLICE_X24Y25", "SLICE_X25Y25",    # CLBLM_R_X17Y25
)

FF_BELS = ("AFF", "A5FF", "BFF", "B5FF", "CFF", "C5FF", "DFF", "D5FF")

# feature tail -> (variant that carries the asserted value, semantic pointer, expected
# semantic value). `base` means the claim is that the BASELINE design asserts it.
SLICE_WIDE = {
    "CEUSEDMUX": ("base", "/resolved/ce_mode", "DRIVEN"),
    "SRUSEDMUX": ("base", "/resolved/sr_mode", "DRIVEN"),
    "FFSYNC": ("base", "/resolved/sr_kind", "SYNC"),
    "LATCH": ("latch", "/resolved/storage_kind", "LATCH"),
    "CLKINV": ("clkinv", "/resolved/clock_mode", "CLKINV"),
    "NOCLKINV": ("base", "/resolved/clock_mode", "NOCLKINV"),
}

CLAIMS = {
    "ZINI": "the flip-flop's INIT value is the one this feature names",
    "ZRST": "the flip-flop's reset/set value is the one this feature names",
    "CEUSEDMUX": "the slice's clock-enable input is really driven, not tied",
    "SRUSEDMUX": "the slice's set/reset input is really driven, not tied",
    "FFSYNC": "the slice's set/reset is synchronous",
    "LATCH": "the slice's storage elements are latches",
    "CLKINV": "the slice clock is inverted at the sequential cell",
    "NOCLKINV": "the slice clock is not inverted at the sequential cell",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tile_of_site(grid: dict, site: str) -> tuple[str, str, dict]:
    for name, tile in grid.items():
        if site in tile.get("sites", {}):
            return name, tile["type"], tile["bits"]["CLB_IO_CLK"]
    raise SystemExit(f"site {site} is not in the frozen tilegrid")


def site_prefix(grid: dict, site: str, tile_name: str) -> str:
    """`SLICE_X8Y25` -> `SLICEM_X0`, per freeze_format §5.5 (lower X is index 0)."""
    sites = grid[tile_name]["sites"]
    order = sorted(sites, key=lambda s: int(s.split("X")[1].split("Y")[0]))
    return f"{sites[site]}_X{order.index(site)}"


def segbits_for(tile_type: str, pattern: re.Pattern[str]) -> dict[str, list[str]]:
    """Every frozen rule of this class for one tile type, keyed by feature name."""
    table: dict[str, list[str]] = {}
    for line in (DB / f"segbits_{tile_type.lower()}.db").read_text().splitlines():
        fields = line.split()
        if fields and pattern.fullmatch(fields[0]):
            table[fields[0]] = fields[1:]
    return table


def assignment(block: dict, token: str) -> dict:
    """freeze_format §5.3: one segbit token -> one absolute bit assignment."""
    negated = token.startswith("!")
    frame, bit = (int(x) for x in token.lstrip("!").split("_"))
    return {
        "token": token,
        "segbit": {"frame_offset": frame, "bit_offset": bit, "negated": negated},
        "address": {"far": f"0x{int(block['baseaddr'], 16) + frame:08X}",
                    "word": block["offset"] + bit // 32, "bit": bit % 32},
        "expected_value": 0 if negated else 1,
    }


def plan_for_site(grid: dict, site: str, pattern: re.Pattern[str]) -> tuple[list, list]:
    """The specimen family and the 22 predictions of one site instance."""
    tile_name, tile_type, block = tile_of_site(grid, site)
    prefix = site_prefix(grid, site, tile_name)
    rules = segbits_for(tile_type, pattern)
    split = "mine" if site in MINE_SITES else "holdout"
    rule_file = f"prjxray/zynq7/segbits_{tile_type.lower()}.db"

    def feature(tail: str) -> str:
        return f"{tile_type}.{prefix}.{tail}"

    # `pair_features` names the features whose endpoint pair this specimen owns, and
    # `pair_with` names the other end of that pair. Most pairs are (base, variant), but
    # not all — the LATCH pair is (latch_base, latch), because a latch endpoint has to
    # match the baseline's reset kind and clock polarity or the pair moves FFSYNC and
    # CLKINV too (measured: `docs/ff_latch_probe.md`). The prediction's own
    # `specimen_id` says which end asserts, and `comparison_specimen_id` — required from
    # schema 1.5 — commits the other end so it cannot be chosen after the build.
    def specimen(variant: str, pair_features: list[str], pair_with: str | None = None,
                 **extra) -> dict:
        specimen_id = f"{site}_{variant}"
        return {"specimen_id": specimen_id, "site": site, "variant": variant,
                "tile": tile_name, "tile_type": tile_type, "site_prefix": prefix,
                "split": split, "pair_features": pair_features,
                "pair_with": f"{site}_{pair_with}" if pair_with else None,
                # The certificate schema requires a build seed per specimen. Deriving it
                # from the specimen id keeps the plan reproducible and keeps the build
                # tool from choosing one after the fact.
                "build_seed": int(hashlib.sha256(specimen_id.encode()).hexdigest()[:8], 16),
                **extra}

    specimens = [specimen("base", [],
                          description="8x FDRE, INIT=1, CE and R driven, sync, "
                                      "non-inverted clock, anchored; one endpoint of "
                                      "every pair in this site instance except LATCH")]
    specimens += [specimen(f"zini_{bel}", [feature(f"{bel}.ZINI")], "base", ff_bel=bel,
                           description=f"{bel} INIT=0; same P&R as base")
                  for bel in FF_BELS]
    specimens += [specimen(f"zrst_{bel}", [feature(f"{bel}.ZRST")], "base", ff_bel=bel,
                           description=f"{bel} is FDSE (SRVAL=1)")
                  for bel in FF_BELS]
    specimens += [
        specimen("ce_tied", [feature("CEUSEDMUX")], "base", description="CE tied to 1'b1"),
        specimen("sr_tied", [feature("SRUSEDMUX")], "base", description="R tied to 1'b0"),
        specimen("async", [feature("FFSYNC")], "base",
                 description="FDCE, asynchronous clear"),
        # Four elements, not eight: A5FF and its siblings are BEL type FF_INIT and
        # Vivado refuses an LDCE on one. The baseline matches the latch's reset kind and
        # clock polarity so the pair moves the LATCH bit alone.
        specimen("latch_base", [],
                 description="4x FDCE with IS_C_INVERTED on AFF..DFF; the LATCH pair's "
                             "control-matched baseline"),
        specimen("latch", [feature("LATCH")], "latch_base",
                 description="4x LDCE on AFF..DFF"),
        specimen("clkinv", [feature("CLKINV"), feature("NOCLKINV")], "base",
                 description="IS_C_INVERTED on the clock pin; complementary pair, so "
                             "both endpoints assert"),
    ]

    predictions = []

    def predict(variant: str, feature_tail: str, pointer: str, expected: str, claim: str):
        feature = f"{tile_type}.{prefix}.{feature_tail}"
        tokens = rules.get(feature)
        if tokens is None:
            raise SystemExit(f"{feature}: no frozen rule — cannot predict")
        if len(tokens) != 1:
            raise SystemExit(f"{feature}: expected a single-bit rule, got {tokens}")
        owner = next((s for s in specimens if feature in s["pair_features"]), None)
        if owner is None:
            raise SystemExit(f"{feature}: no specimen names it as a pair — refusing")
        # The other end of this pair, committed rather than derived at measurement time.
        asserting = f"{site}_{variant}"
        comparison = owner["pair_with"] if asserting == owner["specimen_id"] else owner["specimen_id"]
        if comparison is None or comparison == asserting:
            raise SystemExit(f"{feature}: comparison endpoint is missing or self — refusing")
        if not any(s["specimen_id"] == comparison for s in specimens):
            raise SystemExit(f"{feature}: comparison endpoint {comparison} is not a specimen")
        item = assignment(block, tokens[0])
        value = item["expected_value"]
        predictions.append({
            "specimen_id": asserting,
            "comparison_specimen_id": comparison,
            "feature": feature,
            "split": split,
            "rule_file": rule_file,
            "predicted_assignments": [item],
            # The feature endpoint always carries the asserted value; the other endpoint
            # carries its complement. A negated token therefore runs 1 -> 0.
            "expected_transition": {"before": 1 - value, "after": value},
            "semantic_assertion": {
                "kind": "member_identity",
                "semantic": True,
                "claim": claim,
                "predicted_member": feature,
                "attestation_field": pointer,
                "expected_value": expected,
            },
        })

    for bel in FF_BELS:
        predict(f"zini_{bel}", f"{bel}.ZINI", f"/resolved/ff_init/{bel}", "0",
                CLAIMS["ZINI"])
        # ZRST=1 is claimed to mean SRVAL=0, so the FDRE baseline is the asserting
        # endpoint and the FDSE variant is the other end of the pair.
        predict("base", f"{bel}.ZRST", f"/resolved/ff_srval/{bel}", "0", CLAIMS["ZRST"])
    for tail, (variant, pointer, expected) in SLICE_WIDE.items():
        predict(variant, tail, pointer, expected, CLAIMS[tail])

    return specimens, predictions


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", default="0xFF07")
    args = ap.parse_args()

    out = args.out.resolve()
    if PREREGISTRATION_HOLD and not out.is_relative_to(REPO / "build"):
        raise SystemExit(
            "pre-registration is HELD: this emitter writes drafts under build/ only.\n"
            "  The commitment fixes the key space, the completeness rule and the\n"
            "  coverage denominator permanently. See docs/ff_preregistration_plan.md;\n"
            "  the author lifts PREREGISTRATION_HOLD, not the tool.")

    grid = json.loads(TILEGRID.read_text())
    manifest = json.loads(MANIFEST.read_text())
    spec = json.loads(SPEC.read_text())
    class_spec = next(c for c in spec["bit_classes"] if c["id"] == "clb_ff_config")
    pattern = re.compile(class_spec["feature_regex"])

    specimens: list[dict] = []
    predictions: list[dict] = []
    for site in SITE_INSTANCES:
        site_specimens, site_predictions = plan_for_site(grid, site, pattern)
        specimens += site_specimens
        predictions += site_predictions

    # Completeness against the freeze, not against the plan's own arithmetic: every
    # entry of the class in every tile type this run touches must have exactly one key.
    covered = [p["feature"] for p in predictions]
    if len(covered) != len(set(covered)):
        raise SystemExit("duplicate feature keys in the plan — refusing")
    frozen_entries = {
        feature
        for tile_type in {s["tile_type"] for s in specimens}
        for feature in segbits_for(tile_type, pattern)
    }
    missing = sorted(frozen_entries - set(covered))
    if missing:
        raise SystemExit(f"{len(missing)} frozen entries have no key, first {missing[0]} — refusing")
    entries = next(c["entries"] for c in manifest["bit_classes"] if c["id"] == "clb_ff_config")
    if len(frozen_entries) != entries:
        raise SystemExit(f"covered {len(frozen_entries)} entries but the manifest says {entries}")

    rule_files = sorted({p["rule_file"] for p in predictions})
    doc = {
        "schema": "gate_predictions",
        "schema_version": "1.5.0",
        "bit_class": "clb_ff_config",
        "seed": args.seed,
        "split_policy": {
            "mine_sites": sorted(MINE_SITES),
            "rule": "a site whose evidence established the harness rules (addressing, "
                    "frame ECC, anchoring) can inform predictions but never score them",
            "coverage": "every entry of the class is asserted exactly once; a plan that "
                        "skipped one would move the coverage denominator after the fact",
        },
        "frozen_inputs": {
            "manifest_freeze_stamp": manifest["freeze_stamp"],
            "spec_sha256": manifest["spec"]["sha256"],
            "files": {f["path"]: f["sha256"] for f in manifest["files"]
                      if f["path"] in rule_files
                      or f["path"].endswith(("xc7z010/tilegrid.json", "part.yaml"))},
        },
        "specimens": specimens,
        "predictions": predictions,
        "totals": {
            "specimens": len(specimens),
            "predictions": len(predictions),
            "holdout_predictions": sum(1 for p in predictions if p["split"] == "holdout"),
        },
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n")
    holdout_specimens = sum(1 for s in specimens if s["split"] == "holdout")
    print(f"{args.out}: sha256 {sha256_file(out)}")
    print(f"  specimens   : {len(specimens)} ({holdout_specimens} holdout) "
          f"over {len(SITE_INSTANCES)} site instances")
    print(f"  predictions : {len(predictions)} "
          f"({doc['totals']['holdout_predictions']} holdout) / {entries} class entries")
    if PREREGISTRATION_HOLD:
        print("  DRAFT — pre-registration is held; this hash commits nothing.")
    else:
        print("  COMMIT THIS HASH BEFORE BUILDING ANY BITSTREAM")
    return 0


if __name__ == "__main__":
    sys.exit(main())

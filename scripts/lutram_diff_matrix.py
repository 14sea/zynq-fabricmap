#!/usr/bin/env python3
"""Diff the clb_lutram specimen modes pairwise and collect the evidence.

Step 3 of inventory -> specimen isolation -> real diff. This is measurement only: it
emits no prediction, no commitment and no certificate, and it does not decide whether
anything passed. It reuses `specimen_diff.diff()` unchanged so the attribution rules
are the ones already reviewed.

Every bucket the differ produces is written out whole -- routing changes attributed to
`segbits_int_*.db`, the ECC exclusions, ownership_unknown and unattributed. Under the
round 9 ruling those routing bits are another class's and are not this class's false
positives, but they are evidence and are never dropped here.

Bitstreams live under build/, which is gitignored, so each specimen's sha256 and its
Vivado readback are copied into the evidence directory alongside the diffs.

    scripts/lutram_diff_matrix.py --out evidence/lutram_isolation_2026_08_03
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specimen_diff import diff  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data/prjxray/zynq7"

# (base_mode, variant_mode, what the pair is meant to isolate). "Meant to" is the
# hypothesis under test; what actually moved is the output.
PAIRS = [
    (0, 1, "LUT6 -> RAM64X1S : xLUT.RAM"),
    (1, 2, "RAM64X1S -> RAM32X1S : xLUT.SMALL"),
    (0, 3, "LUT6 -> SRLC32E : xLUT.SRL"),
    (1, 4, "RAM64X1S -> RAM128X1S : WA7USED"),
    (4, 5, "RAM128X1S -> RAM256X1S : WA8USED"),
    (3, 6, "SRLC32E -> cascaded SRLC32E : DI1MUX cascade member"),
    (0, 5, "LUT6 -> RAM256X1S : whole-slice reference"),
]

CLASS_RE = re.compile(
    r"^CLB(LL|LM)_[LR]\.SLICE[LM]_X[01]\."
    r"(([A-D]LUT\.(RAM|SMALL|SRL))|([A-D]LUT\.DI1MUX\.[A-Z0-9_]+)|(WA[78]USED)|(WEMUX\.[A-Z0-9_]+))$")


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


_rules: dict[str, dict[str, list[str]]] = {}


def rule_tokens(tile_type: str, feature: str) -> list[str]:
    key = tile_type.lower()
    if key not in _rules:
        table: dict[str, list[str]] = {}
        path = DB / f"segbits_{key}.db"
        if path.is_file():
            for line in path.read_text().splitlines():
                toks = line.split()
                table[toks[0]] = toks[1:]
        _rules[key] = table
    return _rules[key].get(feature, [])


def class_features(rec: dict) -> list[dict]:
    """Class features claiming a changed address, WITH the polarity of the claim.

    `features_using()` returns every feature whose rule mentions the coordinate in
    either polarity, so a complementary pair lists BOTH members at the one address.
    Printed bare that reads as "both members turned on", which is the opposite of what
    a one-bit complementary pair can mean. So each claim carries its token polarity and
    whether it decodes before and after -- `BI` is `00_20`, `DI_CMC31` is `!00_20`, and
    a 0->1 there means BI starts decoding and DI_CMC31 stops.
    """
    out = []
    for t in rec.get("tiles", []):
        for f in t.get("features", []):
            if not CLASS_RE.match(f):
                continue
            toks = rule_tokens(t["tile_type"], f)
            negated = any(tok.startswith("!") and tok.lstrip("!") == t["segbit"] for tok in toks)
            want = 0 if negated else 1
            out.append({
                "feature": f, "segbit": t["segbit"], "tile": t["tile"],
                "polarity": "negated" if negated else "positive",
                "decodes_before": rec["before"] == want,
                "decodes_after": rec["after"] == want,
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", type=Path, default=REPO / "build/lutram")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    out = args.out
    (out / "diffs").mkdir(parents=True, exist_ok=True)

    modes = {}
    for d in sorted(args.build.glob("mode*")):
        bits = list(d.glob("*.bit"))
        if not bits:
            print(f"SKIP {d} — no bitstream", file=sys.stderr)
            continue
        m = int(d.name.removeprefix("mode"))
        place = json.loads((d / "placement.json").read_text()) if (d / "placement.json").is_file() else {}
        modes[m] = {"dir": d, "bit": bits[0], "sha256": sha256(bits[0]), "placement": place}

    manifest = {"schema": "lutram_isolation_evidence", "schema_version": "1.0.0",
                "bit_class": "clb_lutram",
                "note": "measurement only; no prediction, commitment or certificate",
                "specimens": [], "pairs": []}
    for m in sorted(modes):
        p = modes[m]["placement"]
        manifest["specimens"].append({
            "mode": m, "bitstream": modes[m]["bit"].name,
            "bitstream_sha256": modes[m]["sha256"],
            "part": p.get("part"), "vivado_version": p.get("vivado_version"),
            "requested_site": p.get("requested_site"), "site_type": p.get("site_type"),
            "tile": p.get("tile"), "tile_type": p.get("tile_type"),
            "requested_bel": p.get("requested_bel"),
            "bel_after_constraint": p.get("bel_after_constraint"),
            # The anchor is part of the recipe: ANCHOR, its site, and the resolved
            # LOC/BEL of each of its cells. An anchor that moved between modes would
            # put back the structural variation it exists to remove.
            "anchor": p.get("anchor"),
            "anchor_site": p.get("anchor_site"),
            "anchor_site2": p.get("anchor_site2"),
            "anchor_cells": p.get("anchor_cells", []),
            "cells": [{k: c.get(k) for k in ("ref", "loc", "bel", "init", "lock_pins")}
                      for c in p.get("cells", [])],
            "nets": p.get("nets", []),
            "occupied_bels": p.get("occupied_bels", []),
        })

    for a, b, why in PAIRS:
        if a not in modes or b not in modes:
            print(f"SKIP pair {a}->{b} — missing specimen", file=sys.stderr)
            continue
        d = diff(modes[a]["bit"], modes[b]["bit"])
        name = f"mode{a}_to_mode{b}"
        # specimen_diff records the paths it was handed, which are absolute and point
        # into build/ -- gitignored, so the record would name evidence a fresh clone
        # cannot resolve and would leak this host's directory layout. Replaced by the
        # logical specimen id plus the sha256 that actually pins the artifact.
        # The build directory is a parameter, so it is read from it -- an earlier
        # version hardcoded "build/lutram", which made every anchored record name a
        # directory its bitstreams were not in.
        rel = args.build.relative_to(REPO) if args.build.is_absolute() else args.build
        d["base"] = {"specimen": f"mode{a}", "bitstream": modes[a]["bit"].name,
                     "sha256": modes[a]["sha256"],
                     "path_in_build_tree": f"{rel}/mode{a}/{modes[a]['bit'].name}"}
        d["variant"] = {"specimen": f"mode{b}", "bitstream": modes[b]["bit"].name,
                        "sha256": modes[b]["sha256"],
                        "path_in_build_tree": f"{rel}/mode{b}/{modes[b]['bit'].name}"}
        d["bitstreams_in_version_control"] = False
        d["note"] = ("bitstreams are NOT committed (build/ is gitignored); they are "
                     "identified by sha256 and rebuildable from the specimen harness "
                     "AT THE REPOSITORY COMMIT THAT PRODUCED THIS RECORD -- not "
                     "necessarily from HEAD, since the harness changes between runs")
        (out / "diffs" / f"{name}.json").write_text(json.dumps(d, indent=2) + "\n")

        in_class = defaultdict(list)
        for rec in d["attributed"]:
            for claim in class_features(rec):
                in_class[claim["feature"]].append({
                    "far": rec["far"], "word": rec["word"], "bit": rec["bit"],
                    "segbit": claim["segbit"], "tile": claim["tile"],
                    "polarity": claim["polarity"],
                    "before": rec["before"], "after": rec["after"],
                    "decodes_before": claim["decodes_before"],
                    "decodes_after": claim["decodes_after"],
                })
        manifest["pairs"].append({
            "pair": name, "hypothesis": why,
            "base_sha256": modes[a]["sha256"], "variant_sha256": modes[b]["sha256"],
            "counts": {"attributed": len(d["attributed"]),
                       "frame_ecc_excluded": len(d["excluded_diff"]),
                       "ownership_unknown": len(d["ownership_unknown"]),
                       "unattributed": len(d["unattributed"]),
                       "in_class_features_moved": len(in_class)},
            "class_features_moved": {k: in_class[k] for k in sorted(in_class)},
            "findings": d["findings"],
            "diff_file": f"diffs/{name}.json",
        })
        print(f"{name:<18} {why}")
        print(f"    attributed={len(d['attributed']):<5} ecc={len(d['excluded_diff']):<4} "
              f"unknown={len(d['ownership_unknown']):<3} unattributed={len(d['unattributed']):<3} "
              f"class-features={len(in_class)}")
        for f in sorted(in_class):
            for h in in_class[f]:
                dec = f"{'Y' if h['decodes_before'] else 'n'}->{'Y' if h['decodes_after'] else 'n'}"
                print(f"      {f.split('.',1)[1]:<30} segbit {h['segbit']:<6} "
                      f"bit {h['before']}->{h['after']}  decodes {dec}  ({h['polarity']})")
        for msg in d["findings"]:
            print(f"    FINDING {msg}")

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\nwrote {out}/manifest.json and {len(manifest['pairs'])} diffs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Turn build_lutram.tcl's flat readback into placement.json.

The Tcl writes TAB-separated `key<TAB>value` lines instead of JSON: composing JSON in
Tcl requires literal braces inside quoted strings, which the parser miscounts, and the
first attempt produced a truncated readback *after* the bitstream had already been
written -- a file that looks like evidence and is not.

This converter is deliberately dumb. It reshapes; it does not interpret, default, or
fill in anything. A key that Vivado did not emit stays absent.

    scripts/lutram_readback.py build/lutram/mode0
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse(tsv: Path) -> dict:
    flat: dict[str, str] = {}
    for line in tsv.read_text().splitlines():
        if not line.strip():
            continue
        k, _, v = line.partition("\t")
        flat[k] = v
    out: dict = {"cells": [], "anchor_cells": [], "nets": [], "occupied_bels": []}
    cells: dict[int, dict] = {}
    occ: dict[int, dict] = {}
    anchor: dict[int, dict] = {}
    nets: dict[int, dict] = {}
    for k, v in flat.items():
        parts = k.split(".")
        if parts[0] == "cell":
            c = cells.setdefault(int(parts[1]), {"bel_pins": {}})
            if parts[2] == "belpin":
                c["bel_pins"][parts[3]] = v
            else:
                c[parts[2]] = v
        elif parts[0] == "anchor" and len(parts) == 3:
            anchor.setdefault(int(parts[1]), {})[parts[2]] = v
        elif parts[0] == "net":
            nets.setdefault(int(parts[1]), {})[parts[2]] = v
        elif parts[0] == "occupied":
            occ.setdefault(int(parts[1]), {})[parts[2]] = v
        else:
            out[k] = v
    out["cells"] = [cells[i] for i in sorted(cells)]
    out["anchor_cells"] = [anchor[i] for i in sorted(anchor)]
    out["nets"] = [nets[i] for i in sorted(nets)]
    out["occupied_bels"] = [occ[i] for i in sorted(occ)]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", type=Path)
    args = ap.parse_args()
    for d in args.dirs:
        tsv = d / "readback.tsv"
        if not tsv.exists():
            print(f"MISSING {tsv}", file=sys.stderr)
            return 1
        rec = parse(tsv)
        (d / "placement.json").write_text(json.dumps(rec, indent=2) + "\n")
        bels = ",".join(c.get("bel", "?") for c in rec["cells"])
        print(f"{d.name:<8} mode={rec.get('mode')} site={rec.get('requested_site')} "
              f"site_type={rec.get('site_type')} tile={rec.get('tile')} "
              f"cells={len(rec['cells'])} bels={bels}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

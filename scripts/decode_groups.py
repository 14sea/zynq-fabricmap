#!/usr/bin/env python3
"""Decode a tile's multi-bit feature groups out of a single bitstream.

`clb_lut_init`, the one class certified so far, is a degenerate case: 1.00 bits per
feature and not a single negated token.  Everything the contract says about multi-bit
rules — the assert-iff rule, negated polarity, and the one-selected-input-per-mux-group
composition rule — has therefore only ever been exercised by fixtures.

`clb_mux` is where that stops being true: 3.36 bits per feature and 504 negated tokens.
This tool reads the **absolute** bit values of a tile (not a diff) and decodes each mux
group, so those paths can be tested against real bitstreams.

A *group* is a maximal set of features sharing one bit set — see `groups_for`, which
documents why deriving it from the feature name instead is wrong and how real data
falsifies that. A group decodes to a member when every non-negated bit of that member
is 1 and every negated bit is 0. The composition rule says **at most one** member may
decode at a time; more than one is a contradiction in the database, in our address
arithmetic, or in the grouping itself, and zero means the group is unset.

    scripts/decode_groups.py <file.bit> --tile CLBLL_L_X2Y25 [--class clb_mux]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bitstream_frames import column_map, device_layout, parse_frames  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data/prjxray/zynq7"
TILEGRID = DB / "xc7z010/tilegrid.json"
SPEC = REPO / "data/subset_spec.json"


def groups_for(tile_type: str, class_id: str | None) -> dict[str, dict[str, list[str]]]:
    """{group: {member: [tokens]}} for one tile type, optionally one bit class.

    **A group is defined by its bit set, never by its name.**  Feature names suggest
    grouping and are wrong about it: `AFFMUX.{AX,CY,XOR,F7,O5,O6}` all encode into the
    same four bits `30_00..30_03` and really are mutually exclusive, while
    `CARRY4.{A,B,C,D}CY0` are four independent booleans on four different bits
    (`30_15`, `01_15`, `30_48`, `30_49`) that merely share a prefix.  Grouping by the
    name prefix reports the latter as four simultaneously-selected members of one mux
    — 160 false violations in a real design, measured.

    So a group is a maximal set of features over an identical address set (polarity
    ignored), and its label is the common name prefix only for readability.
    """
    rx = None
    if class_id:
        spec = json.loads(SPEC.read_text())
        rx = re.compile(next(c["feature_regex"] for c in spec["bit_classes"]
                             if c["id"] == class_id))
    by_bits: dict[frozenset, dict[str, list[str]]] = defaultdict(dict)
    for line in (DB / f"segbits_{tile_type.lower()}.db").read_text().splitlines():
        toks = line.split()
        if rx and not rx.match(toks[0]):
            continue
        addrs = frozenset(t.lstrip("!") for t in toks[1:])
        by_bits[addrs][toks[0]] = toks[1:]

    out: dict[str, dict[str, list[str]]] = {}
    for addrs, members in by_bits.items():
        prefix = os.path.commonprefix(list(members)).rstrip(".")
        label = f"{prefix}[{'|'.join(sorted(m.rsplit('.', 1)[-1] for m in members))}]" \
            if len(members) > 1 else next(iter(members))
        out[label] = {m.rsplit(".", 1)[-1]: t for m, t in members.items()}
    return out


def read_tile_bits(frames: dict, block: dict) -> dict[str, int]:
    """{segbit token: value} for every bit the tile owns, per freeze_format §5."""
    base, off, nwords, nframes = (int(block["baseaddr"], 16), block["offset"],
                                 block["words"], block["frames"])
    bits = {}
    for f in range(nframes):
        frame = frames.get(base + f)
        if frame is None:
            continue
        for w in range(nwords):
            word = frame[off + w]
            for b in range(32):
                bits[f"{f:02d}_{w * 32 + b:02d}"] = (word >> b) & 1
    return bits


def decode(groups: dict, bits: dict[str, int]) -> dict:
    out = {}
    for group, members in groups.items():
        hits = []
        for member, tokens in members.items():
            ok = True
            for tok in tokens:
                neg = tok.startswith("!")
                v = bits.get(tok.lstrip("!"))
                if v is None or v != (0 if neg else 1):
                    ok = False
                    break
            if ok:
                hits.append(member)
        out[group] = hits
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bitfile", type=Path)
    ap.add_argument("--tile", required=True)
    ap.add_argument("--class", dest="class_id", default="clb_mux")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    grid = json.loads(TILEGRID.read_text())
    tile = grid[args.tile]
    block = tile["bits"]["CLB_IO_CLK"]
    frames = parse_frames(args.bitfile, column_map(), device_layout())["frames"]
    bits = read_tile_bits(frames, block)
    groups = groups_for(tile["type"], args.class_id)
    dec = decode(groups, bits)

    multi = {g: m for g, m in dec.items() if len(m) > 1}
    single = {g: m[0] for g, m in dec.items() if len(m) == 1}
    empty = [g for g, m in dec.items() if not m]

    print(f"{args.bitfile.name}  tile {args.tile} ({tile['type']})  class {args.class_id}")
    print(f"  groups            : {len(groups)}")
    print(f"  decoded to one    : {len(single)}")
    print(f"  unset (no member) : {len(empty)}")
    print(f"  MULTIPLE members  : {len(multi)}   <-- composition-rule violations")
    for g, m in sorted(single.items()):
        print(f"    {g.split('.', 1)[-1]:<44} = {m}")
    for g, m in sorted(multi.items()):
        print(f"    !! {g.split('.', 1)[-1]:<41} = {m}")
    if args.json:
        args.json.write_text(json.dumps(
            {"bitfile": str(args.bitfile), "tile": args.tile, "class": args.class_id,
             "single": single, "multiple": multi, "unset": sorted(empty)}, indent=2) + "\n")
    return 1 if multi else 0


if __name__ == "__main__":
    sys.exit(main())

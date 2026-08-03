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
arithmetic, or in the grouping itself.

Zero matches is reported in the legacy field `unset`, and that name overpromises: it
means only that **no listed codeword matched**. It is not evidence that the group is
unset, inactive or safe — the frozen DB records which patterns name a member and says
nothing about what an unnamed pattern does. Read the field as `unmatched`; the name is
kept for artifact compatibility with `gate_runs/mux_group_scan_2026_08_02/scan.json`.

**Do not report the violation count as evidence** (erratum 2026-08-03,
`docs/mux_groups.md`). Every member of a bit-set group is a full codeword over the same
scope, and all 170 `clb_mux` / 168 `clb_ff_config` groups have pairwise-distinct
codewords, so `len(matched) > 1` is structurally impossible and the counter can only
ever print 0. It is still worth running as a **DB/group/address consistency invariant** —
a nonzero result means the database, the address arithmetic or the grouping is broken —
but a zero says nothing about the fabric, and it cannot gate a write: it rejects no
bitstream pattern at all. The runtime-enforceable rule is decode-validity (the observed
pattern must be a listed codeword), which leaves 844 patterns unlisted across the 170
`clb_mux` groups, 160 across `clb_ff_config` and 30 across `clb_lutram`. Exempting the
all-zero "unset" pattern drops those to 682 / 0 / 0 — but that exemption is a **policy
assumption, not something the frozen DB establishes**, so do not quote the reduced
figures without it (`docs/mux_groups.md`). The informative outputs of
a sweep are `decoded_to_one` and `unset`. The violation test *is* meaningful for
name-derived grouping, where "members" do not share a scope; that is the comparison in
`groups_for`.

    scripts/decode_groups.py <file.bit> --tile CLBLL_L_X2Y25 [--class clb_mux]
    scripts/decode_groups.py --sweep a.bit b.bit --json scan.json   # every CLB tile
"""

from __future__ import annotations

import argparse
import hashlib
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


def sweep(bitfiles: list[Path], class_id: str) -> dict:
    """Decode every CLB tile of the die in each bitstream. Reproducible + hashed."""
    grid = json.loads(TILEGRID.read_text())
    cols, layout = column_map(), device_layout()
    gsets = {t: groups_for(t, class_id)
             for t in ("CLBLL_L", "CLBLL_R", "CLBLM_L", "CLBLM_R")}
    tiles = [(n, t) for n, t in grid.items() if t["type"] in gsets and t.get("bits")]

    out = {"schema": "mux_group_scan", "schema_version": "1.0.0",
           "class": class_id, "clb_tiles_per_bitstream": len(tiles),
           "groups_per_tile_type": {k: len(v) for k, v in gsets.items()},
           "group_definition": "maximal set of features sharing an identical bit-address "
                               "set (polarity ignored); the name prefix is a label only",
           "bitstreams": [], "totals": {"evaluations": 0, "decoded_to_one": 0,
                                        "unset": 0, "violations": 0}}
    for bf in bitfiles:
        frames = parse_frames(bf, cols, layout)["frames"]
        one = unset = multi = 0
        examples = {}
        for name, tile in tiles:
            bits = read_tile_bits(frames, tile["bits"]["CLB_IO_CLK"])
            for g, m in decode(gsets[tile["type"]], bits).items():
                if len(m) > 1:
                    multi += 1
                    examples.setdefault(f"{name} {g}", m)
                elif m:
                    one += 1
                else:
                    unset += 1
        out["bitstreams"].append({
            "path": str(bf), "name": bf.name,
            "sha256": hashlib.sha256(bf.read_bytes()).hexdigest(),
            "size_bytes": bf.stat().st_size,
            "evaluations": one + unset + multi, "decoded_to_one": one,
            "unset": unset, "violations": multi,
            "violation_examples": dict(list(examples.items())[:5]),
        })
        t = out["totals"]
        t["evaluations"] += one + unset + multi
        t["decoded_to_one"] += one
        t["unset"] += unset
        t["violations"] += multi
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bitfile", type=Path, nargs="?")
    ap.add_argument("--sweep", type=Path, nargs="*", help="scan every CLB tile of the die")
    ap.add_argument("--tile")
    ap.add_argument("--class", dest="class_id", default="clb_mux")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    if args.sweep:
        res = sweep(args.sweep, args.class_id)
        t = res["totals"]
        print(f"mux-group sweep, class {res['class']}, "
              f"{res['clb_tiles_per_bitstream']} CLB tiles per bitstream")
        for b in res["bitstreams"]:
            print(f"  {b['name']:<46} decoded={b['decoded_to_one']:>6} "
                  f"unmatched={b['unset']:>6} violations={b['violations']}")
            print(f"    sha256 {b['sha256']}")
        print(f"  TOTAL evaluations={t['evaluations']:,} "
              f"decoded_to_one={t['decoded_to_one']:,} violations={t['violations']}")
        if args.json:
            args.json.write_text(json.dumps(res, indent=2) + "\n")
            print(f"  wrote {args.json}")
        return 1 if t["violations"] else 0

    if not (args.bitfile and args.tile):
        ap.error("give a bitfile and --tile, or use --sweep")
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
    print(f"  unmatched         : {len(empty)}   (no listed codeword; NOT 'unset')")
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

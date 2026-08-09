#!/usr/bin/env python3
"""Parse a 7-series .bit into a {FAR: frame words} map, using only frozen data.

This is the producer-side half of the specimen-diff harness: the differ needs to say
*which* configuration bit changed between two bitstreams, in the same `(FAR, word,
bit)` coordinates that `docs/freeze_format.md` §5 predicts from the frozen database.

How it works
------------
A 7-series bitstream is a stream of big-endian config words after the `AA995566`
sync word.  Frames are written by setting FAR (type-1 write to register 1) and then
streaming frame data through FDRI (register 2), which **auto-increments** the frame
address: minor 0..frames-1 within a column, then the next column (major + 1).  So
recovering "which frame is at which offset" needs the frame count of every column.

That comes from the frozen `part.yaml`, which is authoritative for the die's
configuration layout; `tilegrid.json` cannot supply it, because its per-tile `frames`
is the tile type's *span* inside the column, not the column's width (CLB and INT tiles
share a column and report 36 and 28).  The two files are cross-checked for containment
instead, and both come from the freeze — nothing here is hardcoded.

The parse then **self-checks against the silicon's own bitstream**: the frame sequence
reconstructed from part.yaml, at `FRAME_WORDS` words per frame plus the per-group pad
frames, must consume the FDRI payload exactly.  A mismatch aborts rather than producing
a plausible-looking wrong map.

**This is what discharges the assumption `docs/freeze_format.md` §5.6 flagged as not
derivable from the frozen data.**  On a real xc7z010 bitstream: 5,144 frames described
by part.yaml + 8 pad = 5,152, times 101 words = 520,352 words, which is the FDRI
payload to the word.  Had the frame been any other size, or the pad rule different, no
such coincidence would exist.

Prior art: the packet-walking approach follows `zynq_xpart/scripts/icap-build-frame.py`
(read-only reference, not imported or modified).

    scripts/bitstream_frames.py <file.bit> [--far 0x0040149B] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TILEGRID = REPO / "data/prjxray/zynq7/xc7z010/tilegrid.json"
PART_YAML = REPO / "data/prjxray/zynq7/xc7z010clg400-1/part.yaml"

SYNC = b"\xaa\x99\x55\x66"
FRAME_WORDS = 101          # 7-series; discharged by the self-check, see module docstring
REG_CRC, REG_FAR, REG_FDRI, REG_CMD, REG_IDCODE = 0, 1, 2, 4, 12
IDCODE_XC7Z010 = 0x03722093
BUS_BLOCK_TYPE = {"CLB_IO_CLK": 0, "BLOCK_RAM": 1}
PAD_FRAMES_PER_ROW = 2   # emitted after each (bus, half, row) group; address nothing


# ------------------------------------------------------------------ FAR fields

def far_fields(far: int) -> dict:
    """7-series frame address layout."""
    return {
        "block_type": (far >> 23) & 0x7,
        "top": (far >> 22) & 0x1,        # 0 = top half, 1 = bottom half
        "row": (far >> 17) & 0x1F,
        "major": (far >> 7) & 0x3FF,     # configuration column
        "minor": far & 0x7F,             # frame within the column
    }


def far_of(block_type: int, top: int, row: int, major: int, minor: int) -> int:
    return ((block_type & 0x7) << 23 | (top & 1) << 22 | (row & 0x1F) << 17
            | (major & 0x3FF) << 7 | (minor & 0x7F))


# ------------------------------------------------------- column map from freeze

def _yaml_loader():
    """prjxray's part.yaml uses custom `!<xilinx/xc7series/...>` tags; ignore them."""
    import yaml

    class L(yaml.SafeLoader):
        pass

    L.add_multi_constructor("", lambda loader, suffix, node:
                            loader.construct_mapping(node, deep=True)
                            if isinstance(node, yaml.MappingNode)
                            else (loader.construct_sequence(node, deep=True)
                                  if isinstance(node, yaml.SequenceNode)
                                  else loader.construct_scalar(node)))
    return L


def device_layout(part_path: Path = PART_YAML) -> list[dict]:
    """The device's configuration columns, in FAR order, from the frozen part.yaml.

    part.yaml is the authoritative layout: `global_clock_regions -> {top,bottom} ->
    rows -> configuration_buses -> {CLB_IO_CLK, BLOCK_RAM} -> configuration_columns ->
    frame_count`.  tilegrid alone cannot give this — it only describes columns that
    hold tiles it knows, and its per-tile `frames` is a span, not a column total.

    Returns one record per (bus, half, row) group, which is also the unit the
    bitstream pads: each group is followed by `PAD_FRAMES_PER_ROW` frames.
    """
    import yaml
    doc = yaml.load(part_path.read_text(), Loader=_yaml_loader())
    groups = []
    for half, gcr in doc["global_clock_regions"].items():
        for row, rowd in gcr["rows"].items():
            for bus, busd in rowd["configuration_buses"].items():
                cols = {int(k): v["frame_count"]
                        for k, v in busd["configuration_columns"].items()}
                groups.append({
                    "block_type": BUS_BLOCK_TYPE[bus], "bus": bus,
                    "top": 0 if half == "top" else 1, "half": half,
                    "row": int(row), "columns": cols,
                    "frames": sum(cols.values()),
                })
    # stream order is numeric FAR order: block type, then half, then row
    groups.sort(key=lambda g: (g["block_type"], g["top"], g["row"]))
    return groups


def device_frame_sequence(groups: list[dict]) -> list[int | None]:
    """Every frame the bitstream carries, in stream order.  `None` marks a pad frame.

    Frames auto-increment minor within a column, then major within the row; after each
    (bus, half, row) group the tools emit two pad frames that address nothing.
    """
    seq: list[int | None] = []
    for g in groups:
        for major in sorted(g["columns"]):
            for minor in range(g["columns"][major]):
                seq.append(far_of(g["block_type"], g["top"], g["row"], major, minor))
        seq.extend([None] * PAD_FRAMES_PER_ROW)
    return seq


def cross_check_layout(groups: list[dict], cols: dict) -> list[str]:
    """part.yaml vs tilegrid — the containment the two frozen files must satisfy.

    Every tile's bits must *fit inside* its column: `span <= frame_count`.  Equality is
    not required and is not the norm — column 18 of this die is 36 frames wide while
    the widest tile tilegrid places there is an `INT_L` at 28, because the CLB side of
    that column belongs to the PS region and holds no tile the database describes.  A
    column where a tile reaches *past* the column's frame count would be a genuine
    contradiction, and that is what this flags.
    """
    from_part = {(g["block_type"], g["top"], g["row"], major): n
                 for g in groups for major, n in g["columns"].items()}
    problems = []
    for key, span in sorted(cols.items()):
        have = from_part.get(key)
        if have is None:
            problems.append(f"tilegrid column {key} absent from part.yaml")
        elif span > have:
            problems.append(f"column {key}: tilegrid tile spans {span} frames but "
                            f"part.yaml gives the column only {have}")
    return problems


def column_map(tilegrid_path: Path = TILEGRID) -> dict:
    """(block_type, top, row, major) -> frame count, derived from the frozen tilegrid.

    **`frames` is the tile type's span, not the column total.**  Several tile types
    share one configuration column and each reports only how far its own bits reach:
    in column `(0,1,0,20)` the `CLBLL_L` tiles say 36, the `INT_L` tiles in that same
    column say 28, and `HCLK_L` says 26.  The column really is 36 frames wide; INT and
    HCLK bits simply live in its first frames.  So the column count is the **maximum**
    over the tiles that address it — taking any single tile's word, or treating the
    disagreement as a freeze error, both give a wrong frame map.

    Observed maxima on this die: 28, 30, 36, 42.  The arbiter is not this reasoning
    but `parse_frames`, which has to consume a real Vivado bitstream exactly.
    """
    grid = json.loads(tilegrid_path.read_text())
    cols: dict[tuple, int] = {}
    for tile in grid.values():
        for blk in (tile.get("bits") or {}).values():
            if "baseaddr" not in blk or "frames" not in blk:
                continue
            f = far_fields(int(blk["baseaddr"], 16))
            key = (f["block_type"], f["top"], f["row"], f["major"])
            cols[key] = max(cols.get(key, 0), blk["frames"])
    return cols


# ------------------------------------------------------------- bitstream parse

def config_words(path: Path, data: bytes | None = None) -> tuple[list[int], int]:
    """`data` lets a caller parse bytes it has already hashed.

    Without it there are two reads — one to hash, one to parse — and a file swapped
    between them yields a record whose pinned hash describes bytes nobody scored. Callers
    that pin what they parse pass the bytes; `path` stays for error messages.
    """
    raw = path.read_bytes() if data is None else data
    s = raw.find(SYNC)
    if s < 0:
        raise SystemExit(f"{path}: no sync word — not a 7-series .bit?")
    n = (len(raw) - s) // 4
    return list(struct.unpack(">%dI" % n, raw[s:s + n * 4])), s


def parse_frames(path: Path, cols: dict | None = None,
                 groups: list[dict] | None = None, data: bytes | None = None) -> dict:
    """Return {'frames': {far: [words]}, 'idcode':…, 'blocks':[…], 'pad_frames':n}.

    `data`, when given, is parsed instead of re-reading `path` — see `config_words`.
    """
    cols = cols if cols is not None else column_map()
    groups = groups if groups is not None else device_layout()
    words, sync_off = config_words(path, data)

    frames: dict[int, list[int]] = {}
    blocks: list[dict] = []
    idcode = None
    cur_far = None
    pad_frames = 0

    i = 0
    while i < len(words):
        w = words[i]
        htype = w >> 29
        if htype == 1:                                  # type 1
            op, reg, cnt = (w >> 27) & 3, (w >> 13) & 0x3FFF, w & 0x7FF
            payload = words[i + 1:i + 1 + cnt] if op == 2 else []
            if op == 2 and reg == REG_FAR and cnt >= 1:
                cur_far = payload[0]
            elif op == 2 and reg == REG_IDCODE and cnt >= 1:
                idcode = payload[0]
            elif op == 2 and reg == REG_FDRI and cnt:
                blocks.append({"far": cur_far, "start": i + 1, "words": cnt})
            i += 1 + (cnt if op == 2 else 0)
        elif htype == 2:                                # type 2: continues last reg
            cnt = w & 0x7FFFFFF
            if blocks and blocks[-1]["words"] == 0:
                blocks[-1].update(start=i + 1, words=cnt)
            else:
                blocks.append({"far": cur_far, "start": i + 1, "words": cnt})
            i += 1 + cnt
        else:
            i += 1

    payload = [b for b in blocks if b["words"] >= FRAME_WORDS]
    if len(payload) != 1:
        raise SystemExit(f"{path}: expected one bulk FDRI block, found {len(payload)}")
    blk = payload[0]
    if blk["far"] != 0:
        raise SystemExit(f"{path}: bulk FDRI starts at FAR {blk['far']:#x}, expected 0 — "
                         "this parser assumes a full (not partial) bitstream")

    nframes, rem = divmod(blk["words"], FRAME_WORDS)
    if rem:
        raise SystemExit(
            f"{path}: FDRI block holds {blk['words']} words, not a multiple of "
            f"{FRAME_WORDS} — the frame-size assumption is broken")

    seq = device_frame_sequence(groups)
    if len(seq) != nframes:
        raise SystemExit(
            f"{path}: bitstream carries {nframes} frames, but the frozen part.yaml "
            f"layout describes {len(seq)} ({sum(g['frames'] for g in groups)} real + "
            f"{PAD_FRAMES_PER_ROW * len(groups)} pad) — frame map rejected")

    for k, far in enumerate(seq):
        if far is None:
            pad_frames += 1
            continue
        off = blk["start"] + k * FRAME_WORDS
        frames[far] = words[off:off + FRAME_WORDS]

    return {"path": str(path), "sync_offset": sync_off, "idcode": idcode,
            "frames": frames, "blocks": blocks, "pad_frames": pad_frames,
            "groups": groups, "layout_problems": cross_check_layout(groups, cols),
            "total_words": len(words)}


def bit_value(frame: list[int], word: int, bit: int) -> int:
    return (frame[word] >> bit) & 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bitfile", type=Path)
    ap.add_argument("--far", help="dump one frame, e.g. 0x0040149B")
    ap.add_argument("--json", type=Path, help="write the frame map as JSON")
    args = ap.parse_args()

    cols = column_map()
    groups = device_layout()
    p = parse_frames(args.bitfile, cols, groups)
    idc = p["idcode"]
    print(f"{args.bitfile.name}: sync at byte {p['sync_offset']}, {p['total_words']:,} config words")
    print(f"  IDCODE   : {idc:#010x}" + (" (xc7z010)" if idc == IDCODE_XC7Z010 else " (UNEXPECTED)"))
    real = sum(g["frames"] for g in groups)
    print(f"  layout   : {len(groups)} (bus,half,row) groups, "
          f"{sum(len(g['columns']) for g in groups)} columns, {real:,} frames "
          f"+ {PAD_FRAMES_PER_ROW * len(groups)} pad  [part.yaml]")
    lp = p["layout_problems"]
    print(f"  x-check  : part.yaml vs tilegrid over {len(cols)} tiled columns — "
          + ("OK" if not lp else f"{len(lp)} DISAGREEMENT(S)"))
    for x in lp[:5]:
        print(f"             {x}")
    print(f"  FDRI     : {len(p['blocks'])} block(s), {sum(b['words'] for b in p['blocks']):,} words")
    print(f"  frames   : {len(p['frames']):,} addressed, {p['pad_frames']} pad/undescribed")
    print(f"  self-check: {p['total_words']:,} words -> one FDRI block of "
          f"{sum(b['words'] for b in p['blocks'] if b['words'] >= FRAME_WORDS):,} words "
          f"= {len(p['frames']) + p['pad_frames']:,} x {FRAME_WORDS} words, matching the "
          f"frozen layout exactly — OK")

    if args.far:
        far = int(args.far, 0)
        f = p["frames"].get(far)
        if f is None:
            print(f"  FAR {far:#010x} not present", file=sys.stderr)
            return 1
        print(f"  FAR {far:#010x} {far_fields(far)}")
        for w in range(0, FRAME_WORDS, 8):
            print("   ", " ".join(f"{x:08x}" for x in f[w:w + 8]))
    if args.json:
        args.json.write_text(json.dumps(
            {f"{k:#010x}": v for k, v in p["frames"].items()}))
        print(f"  wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

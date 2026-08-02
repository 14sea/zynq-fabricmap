#!/usr/bin/env python3
"""Diff two specimen bitstreams and attribute every changed bit to a frozen feature.

This is the measurement half of the prediction gate.  Given a base and a variant
bitstream that differ by one intended configuration change, it reports each changed
configuration bit as one of:

  frame_ecc      word 50, bits 0..12 — the frame's ECC field, which the tools
                 recompute whenever anything else in that frame changes.  Not a
                 feature bit and never evidence for or against a prediction.
  attributed     inside a tile the frozen tilegrid describes, at a segbit coordinate
                 that at least one frozen feature rule uses.  The candidate features
                 are named.
  ownership_unknown  inside the geometric range of one or more tiles, but claimed by
                 no frozen rule in any of them, so the owning tile is NOT determined.
                 Reported with every geometric candidate. These may not be described as
                 belonging to any particular tile — in a measured CLB/INT column each
                 such bit has both a CLB and an INT candidate.
  unattributed   outside every described tile.  Always suspicious.

Addresses use `docs/freeze_format.md` §5 in reverse: from `(FAR, word, bit)` back to
`(tile, F_B)`.

    scripts/specimen_diff.py --base a.bit --variant b.bit [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bitstream_frames import (  # noqa: E402
    FRAME_WORDS, column_map, device_layout, far_fields, parse_frames,
)

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data/prjxray/zynq7"
TILEGRID = DB / "xc7z010/tilegrid.json"

ECC_WORD = 50            # the frame's middle word
ECC_BITS = range(0, 13)  # 13-bit ECC field; measured to change on any frame edit
ECC_RULE = f"word == {ECC_WORD} and 0 <= bit <= {max(ECC_BITS)}"


def tile_index() -> dict:
    """(block_type, top, row, major) -> [tile records], from the frozen tilegrid."""
    grid = json.loads(TILEGRID.read_text())
    idx: dict[tuple, list] = {}
    for name, tile in grid.items():
        for blk in (tile.get("bits") or {}).values():
            if "baseaddr" not in blk:
                continue
            base = int(blk["baseaddr"], 16)
            f = far_fields(base)
            idx.setdefault((f["block_type"], f["top"], f["row"], f["major"]), []).append({
                "tile": name, "type": tile["type"], "baseaddr": base,
                "frames": blk["frames"], "offset": blk["offset"], "words": blk["words"],
                "sites": tile.get("sites", {}),
            })
    return idx


def locate(idx: dict, far: int, word: int, bit: int) -> list[dict]:
    """All tiles that could own (far, word, bit), with the segbit coordinate in each.

    Geometry alone does not decide ownership.  A CLB tile and the INT tile beside it
    share the **same baseaddr and the same word offset** — `CLBLL_L_X2Y25` and
    `INT_L_X2Y25` are both `0x00400A00`, offset 51, words 2 — and their declared frame
    spans (36 and 28) overlap.  Their feature sets do not overlap at all, though: over
    all four CLB/INT pairings, not one coordinate is claimed by both databases
    (648 vs 1598 claimed coordinates, intersection empty).  So the databases resolve
    what the grid cannot, and `attribute` below uses that rather than guessing.
    """
    f = far_fields(far)
    hits = []
    for t in idx.get((f["block_type"], f["top"], f["row"], f["major"]), []):
        frame_off = far - t["baseaddr"]
        word_off = word - t["offset"]
        if 0 <= frame_off < t["frames"] and 0 <= word_off < t["words"]:
            hits.append({**t, "segbit": f"{frame_off}_{word_off * 32 + bit:02d}"})
    return hits


_db_cache: dict[str, dict] = {}


def features_using(tile_type: str, segbit: str) -> list[str]:
    """Frozen features whose rule mentions this coordinate (either polarity)."""
    key = tile_type.lower()
    if key not in _db_cache:
        table: dict[str, list[str]] = {}
        path = DB / f"segbits_{key}.db"
        if path.is_file():
            for line in path.read_text().splitlines():
                toks = line.split()
                for tok in toks[1:]:
                    table.setdefault(tok.lstrip("!"), []).append(toks[0])
        _db_cache[key] = table
    return _db_cache[key].get(segbit, [])


def masked(tile_type: str, segbit: str) -> bool:
    path = DB / f"mask_{tile_type.lower()}.db"
    key = f"mask::{tile_type.lower()}"
    if key not in _db_cache:
        bits = set()
        if path.is_file():
            bits = {l.split()[1] for l in path.read_text().splitlines() if l.startswith("bit ")}
        _db_cache[key] = bits
    return segbit in _db_cache[key]


def diff(base: Path, variant: Path) -> dict:
    cols, groups = column_map(), device_layout()
    a = parse_frames(base, cols, groups)["frames"]
    b = parse_frames(variant, cols, groups)["frames"]
    if a.keys() != b.keys():
        raise SystemExit("bitstreams describe different frame sets — not comparable")

    idx = tile_index()
    # Excluded bits are LISTED, never silently dropped: a consumer must be able to
    # recompute the exclusion rule over them and confirm nothing else was hidden.
    out = {"base": str(base), "variant": str(variant),
           "exclusion_rules": [{"reason": "frame_ecc", "rule": ECC_RULE,
                                "why": "the frame ECC field is recomputed whenever any "
                                       "other bit in the same frame changes"}],
           "excluded_diff": [], "attributed": [], "ownership_unknown": [],
           "unattributed": [], "findings": []}

    for far in sorted(a):
        wa, wb = a[far], b[far]
        if wa == wb:
            continue
        for word in range(FRAME_WORDS):
            x = wa[word] ^ wb[word]
            while x:
                bit = (x & -x).bit_length() - 1
                x &= x - 1
                rec = {"far": f"{far:#010x}", "word": word, "bit": bit,
                       "before": (wa[word] >> bit) & 1, "after": (wb[word] >> bit) & 1}
                if word == ECC_WORD and bit in ECC_BITS:
                    out["excluded_diff"].append({**rec, "reason": "frame_ecc",
                                                 "rule": ECC_RULE})
                    continue
                hits = locate(idx, far, word, bit)
                if not hits:
                    out["unattributed"].append(rec)
                    continue
                named = []
                for h in hits:
                    feats = features_using(h["type"], h["segbit"])
                    named.append({"tile": h["tile"], "tile_type": h["type"],
                                  "segbit": h["segbit"], "features": feats,
                                  "masked": masked(h["type"], h["segbit"])})
                claiming = [n for n in named if n["features"]]
                if len(claiming) > 1:
                    # never observed; an assumption that must stay a check
                    out["findings"].append(
                        f"{rec['far']} word {rec['word']} bit {rec['bit']}: claimed by "
                        f"{[n['tile'] for n in claiming]} — ownership ambiguous")
                rec["tiles"] = claiming or named
                rec["candidates"] = [n["tile"] for n in named]
                (out["attributed"] if claiming else out["ownership_unknown"]).append(rec)

    # An ECC change in a frame with no data change cannot be explained by the
    # exclusion rule's own rationale, so it is a finding rather than an exclusion.
    data_frames = {r["far"] for r in out["attributed"] + out["ownership_unknown"]
                   + out["unattributed"]}
    ecc_frames = {r["far"] for r in out["excluded_diff"]}
    for far in sorted(ecc_frames - data_frames):
        out["findings"].append(
            f"{far}: ECC bits changed with no other change in that frame — "
            "not explainable as recomputation, do not exclude silently")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--variant", type=Path, required=True)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    d = diff(args.base, args.variant)
    print(f"{args.base.name} -> {args.variant.name}")
    print(f"  excluded (ECC)   : {len(d['excluded_diff'])} bits, rule: {ECC_RULE}")
    print(f"  attributed bits  : {len(d['attributed'])}")
    for r in d["attributed"]:
        for t in r["tiles"]:
            if t["features"]:
                print(f"    {r['far']} word {r['word']:>3} bit {r['bit']:>2} "
                      f"{r['before']}->{r['after']}  {t['tile']} segbit {t['segbit']}"
                      f"  {', '.join(t['features'])}")
    print(f"  ownership unknown: {len(d['ownership_unknown'])}")
    for r in d["ownership_unknown"][:8]:
        print(f"    {r['far']} word {r['word']:>3} bit {r['bit']:>2}  "
              f"candidates={r['candidates']}")
    print(f"  unattributed     : {len(d['unattributed'])}")
    for r in d["unattributed"][:8]:
        print(f"    {r['far']} word {r['word']:>3} bit {r['bit']:>2}")
    for f in d["findings"]:
        print(f"  FINDING: {f}")
    if args.json:
        args.json.write_text(json.dumps(d, indent=2))
        print(f"  wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

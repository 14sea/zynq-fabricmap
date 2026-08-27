#!/usr/bin/env python3
"""Hamming-1 decidability census for xc7z010 — host-side only, no board.

**This is a diagnostic, not a gate**, and it is **not** the preregistered Claim B safety
comparison: see `docs/zynq7_decidability_census.md` §0, which retracts that framing.  The
question here is narrower and is about the frozen database, not about an operator: for
every configuration bit, can the frozen prjxray rules say what flipping it does?

What it measures, exhaustively over every configuration bit of one xc7z010 bitstream:

1. **The bit partition.**  Every one of the 5,144 x 101 x 32 bits is assigned to
   exactly one class: covered by a frozen rule file; inside a rule-file tile type but
   never referenced by any rule; inside a tile type with no frozen rules; BRAM content;
   **the frame ECC field** (word 50, bits 12:0 — not unmodelled, but warranted by
   `scripts/frame_ecc.py` rather than by prjxray, and required collateral on every real
   frame write); or claimed by no tile at all.  Anything not decidable is *fail-closed*
   as UNDETERMINED — never counted as safe.
2. **Decode-group state, before and after every single raw bit flip.**  Decode groups
   are computed by union-find over *shared bits*, per `docs/mux_groups.md` — names
   are not a grouping.  A group's state is one of ALLZERO / DECODED (exactly one
   feature's pattern matches) / MULTI (more than one matches - for a routing mux this
   is a multi-source, i.e. contention, candidate) / UNDECODABLE (bits are set but no
   pattern matches; the database cannot say what the fabric does).
3. **The map's SEMANTIC bits.**  Whether each of the certified addresses in
   `maps/*.local_map.json` is a width-1, unshared feature bit whose flip the rules can
   decide.  That is all the flag `semantic_bits_decidable` says.  It does **not** say a
   serialized candidate is decidable: a candidate also carries the recomputed ECC of
   every frame it rewrites (see `candidate_footprint`), so a Hamming-1 flip is not a
   candidate in this pipeline at all.

Coordinate arithmetic is `docs/freeze_format.md` 5.3 and nothing else.

    scripts/diag_safety_decidability.py [--bit <file.bit>] [--json out.json]
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import bitstream_frames as bf  # noqa: E402

DB = REPO / "data/prjxray/zynq7"
TILEGRID = DB / "xc7z010/tilegrid.json"
DEFAULT_BIT = REPO / "gate_runs/claimb_round1_carrier_2026_08_13_erratum006/carrier.bit"
DEFAULT_MAP = REPO / "maps/clb_lut_init_v1.local_map.json"


def _rel(path: Path) -> str:
    """Repo-relative when it can be, absolute when it cannot — never raises."""
    path = path.resolve()
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)

SCHEMA = "zynq7_hamming1_decidability_census"

ECC_WORD = 0x32            # 50 - frame_ecc.ECC_WORD
ECC_BITS_PER_FRAME = 13    # frame_ecc.ECC_MASK = 0x1FFF, bits 12:0

ROUTING_TYPES = ("INT_L", "INT_R")
CONTENT_TYPES = ("CLBLL_L", "CLBLL_R", "CLBLM_L", "CLBLM_R")
RULE_TYPES = ROUTING_TYPES + CONTENT_TYPES


# --------------------------------------------------------------- frozen rule files

def load_segbits(tile_type: str) -> dict[str, list[tuple[int, int, int]]]:
    """feature -> [(frame_offset, bit_offset, expected), ...], per freeze_format 5.3."""
    feats: dict[str, list[tuple[int, int, int]]] = {}
    path = DB / f"segbits_{tile_type.lower()}.db"
    for line in path.read_text().splitlines():
        parts = line.split()
        if not parts:
            continue
        pattern, ok = [], True
        for tok in parts[1:]:
            negated = tok.startswith("!")
            body = tok[1:] if negated else tok
            if "_" not in body:          # 'always', 'default', <const0> ... not a bit
                ok = False
                break
            frame, bit = body.split("_")
            pattern.append((int(frame), int(bit), 0 if negated else 1))
        if ok and pattern:
            feats[parts[0]] = pattern
    return feats


def decode_groups(feats):
    """Union-find over shared bits. docs/mux_groups.md: groups are bits, not names."""
    parent = {name: name for name in feats}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    bit_users = collections.defaultdict(list)
    for name, pattern in feats.items():
        for (frame, bit, _) in pattern:
            bit_users[(frame, bit)].append(name)
    for users in bit_users.values():
        root = find(users[0])
        for other in users[1:]:
            parent[find(other)] = root

    groups = collections.defaultdict(list)
    for name in feats:
        groups[find(name)].append(name)
    out = []
    for members in groups.values():
        bits = sorted({(f, b) for m in members for (f, b, _) in feats[m]})
        out.append((sorted(members), bits))
    return out, bit_users


def classify(values, members, feats) -> str:
    if not any(values.values()):
        return "ALLZERO"
    matched = sum(1 for m in members
                  if all(values[(f, b)] == e for (f, b, e) in feats[m]))
    if matched == 1:
        return "DECODED"
    if matched > 1:
        return "MULTI"
    return "UNDECODABLE"


# --------------------------------------------------------------------------- sweep

def sweep(frames, grid, feats_by_type, groups_by_type):
    base = collections.Counter()
    trans = collections.Counter()
    absent = 0
    for tile, entry in grid.items():
        tile_type = entry["type"]
        if tile_type not in feats_by_type:
            continue
        blk = (entry.get("bits") or {}).get("CLB_IO_CLK")
        if not blk:
            continue
        base_far, offset = int(blk["baseaddr"], 16), blk["offset"]
        feats = feats_by_type[tile_type]
        klass = "routing" if tile_type in ROUTING_TYPES else "content"
        for members, bits in groups_by_type[tile_type]:
            values, missing = {}, False
            for (frame, bit) in bits:
                words = frames.get(base_far + frame)
                if words is None:
                    missing = True
                    break
                values[(frame, bit)] = (words[offset + bit // 32] >> (bit % 32)) & 1
            if missing:
                absent += 1
                continue
            before = classify(values, members, feats)
            base[(klass, len(members), before)] += 1
            for coord in bits:
                values[coord] ^= 1
                after = classify(values, members, feats)
                values[coord] ^= 1
                trans[(klass, before, after)] += 1
    return base, trans, absent


# ----------------------------------------------------------------------- partition

def partition(frames, grid, feats_by_type):
    referenced = {t: len({(f, b) for p in feats_by_type[t].values() for (f, b, _) in p})
                  for t in feats_by_type}
    slots = collections.Counter()
    bram = 0
    for entry in grid.values():
        for block, d in (entry.get("bits") or {}).items():
            n = d["frames"] * d["words"] * 32
            if block == "CLB_IO_CLK":
                slots[entry["type"]] += n
            else:
                bram += n
    total = len(frames) * bf.FRAME_WORDS * 32
    routing_slots = sum(slots[t] for t in ROUTING_TYPES)
    content_slots = sum(slots[t] for t in CONTENT_TYPES)
    routing_ref = sum(referenced[t] * sum(1 for e in grid.values()
                                          if e["type"] == t and (e.get("bits") or {}).get("CLB_IO_CLK"))
                      for t in ROUTING_TYPES)
    content_ref = sum(referenced[t] * sum(1 for e in grid.values()
                                          if e["type"] == t and (e.get("bits") or {}).get("CLB_IO_CLK"))
                      for t in CONTENT_TYPES)
    other = sum(slots.values()) - routing_slots - content_slots
    unclaimed = total - sum(slots.values()) - bram
    # The frame ECC field is not "undetermined": it is excluded from every tile's bit
    # space by rule, and its semantics are fixed by scripts/frame_ecc.py (word 50,
    # bits 12:0), cross-validated against Vivado known-answer frames.  Counting it with
    # the genuinely unmodelled bits would understate what a real candidate can account
    # for.  See docs/claimb_preregistration.md 2 "Collateral bits".
    ecc_field = len(frames) * ECC_BITS_PER_FRAME
    return {
        "total_config_bits": total,
        "frames": len(frames),
        "routing_rule_covered": routing_ref,
        "routing_rule_silent": routing_slots - routing_ref,
        "content_rule_covered": content_ref,
        "content_rule_silent": content_slots - content_ref,
        "tile_types_without_frozen_rules": other,
        "bram_content": bram,
        "frame_ecc_field": ecc_field,
        "claimed_by_no_tile_other": unclaimed - ecc_field,
    }


# --------------------------------------------------------------------- map check

def check_map(map_path, feats_by_type, bit_users_by_type):
    doc = json.loads(map_path.read_text())
    rows = doc["universe"]["addresses"]
    widths = collections.Counter()
    shared = 0
    unknown = 0
    for row in rows:
        tile_type = row["feature"].split(".")[0]
        feats = feats_by_type.get(tile_type)
        pattern = feats.get(row["feature"]) if feats else None
        if pattern is None:
            unknown += 1
            continue
        widths[len(pattern)] += 1
        frame, bit, _ = pattern[0]
        if len(pattern) == 1 and len(bit_users_by_type[tile_type][(frame, bit)]) > 1:
            shared += 1
    return {
        "map": _rel(map_path),
        "addresses": len(rows),
        "feature_widths": {str(k): v for k, v in sorted(widths.items())},
        "single_bit_and_unshared": widths.get(1, 0) - shared,
        "shared_with_another_feature": shared,
        "not_in_frozen_rules": unknown,
        "semantic_bits_decidable": unknown == 0 and shared == 0
                                   and set(widths) == {1},
    }


def candidate_footprint(map_path: Path) -> dict:
    """What a *serialized* candidate touches, which is not what a bit flip touches.

    Every candidate rewrites all target frames and each rewritten frame's ECC field is
    recomputed (`scripts/gate_claimb_known_answer.py:156`; `scripts/gate_candidate.py`
    rejects a frame whose ECC is not a correct recomputation).  So the flip census below
    measures a property of the database, NOT the two operators' candidate distributions.
    """
    doc = json.loads(map_path.read_text())
    fars = sorted({row["far"] for row in doc["universe"]["addresses"]})
    return {
        "semantic_bits": doc["universe"]["address_count"],
        "target_frames": len(fars),
        "ecc_collateral_bit_positions": len(fars) * ECC_BITS_PER_FRAME,
        "note": "a frame write is >= 1 content bit plus the recomputed ECC word",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bit", type=Path, default=DEFAULT_BIT)
    ap.add_argument("--map", type=Path, default=DEFAULT_MAP)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    started = time.time()
    frames = bf.parse_frames(args.bit)["frames"]
    grid = json.loads(TILEGRID.read_text())

    feats_by_type, groups_by_type, bit_users_by_type = {}, {}, {}
    for tile_type in RULE_TYPES:
        feats = load_segbits(tile_type)
        groups, bit_users = decode_groups(feats)
        feats_by_type[tile_type] = feats
        groups_by_type[tile_type] = groups
        bit_users_by_type[tile_type] = bit_users

    base, trans, absent = sweep(frames, grid, feats_by_type, groups_by_type)
    report = {
        "schema": SCHEMA,
        "schema_version": "1.0.0",
        "bitstream": _rel(args.bit),
        "partition": partition(frames, grid, feats_by_type),
        "groups_with_absent_frames": absent,
        "base_states": [{"class": k[0], "group_size": k[1], "state": k[2], "count": v}
                        for k, v in sorted(base.items())],
        "flip_transitions": [{"class": k[0], "before": k[1], "after": k[2], "count": v}
                             for k, v in sorted(trans.items())],
        "map_universe": check_map(args.map, feats_by_type, bit_users_by_type),
        "candidate_footprint": candidate_footprint(args.map),
        "elapsed_s": round(time.time() - started, 1),
    }

    for klass in ("routing", "content"):
        rows = [r for r in report["flip_transitions"] if r["class"] == klass]
        total = sum(r["count"] for r in rows)
        print(f"\n{klass.upper()}  single raw bit flip, {total:,} bits")
        for r in sorted(rows, key=lambda r: -r["count"]):
            print(f"   {r['before']:11s} -> {r['after']:12s} "
                  f"{r['count']:>10,}  {100 * r['count'] / total:6.3f}%")
    p = report["partition"]
    print(f"\nBIT PARTITION of {p['total_config_bits']:,} bits "
          f"({p['frames']} frames)")
    for k, v in p.items():
        if k in ("total_config_bits", "frames"):
            continue
        print(f"   {k:34s} {v:>12,}  {100 * v / p['total_config_bits']:6.2f}%")
    m = report["map_universe"]
    print(f"\nMAP UNIVERSE {m['map']}: {m['addresses']} addresses, widths "
          f"{m['feature_widths']}, shared {m['shared_with_another_feature']}, "
          f"unknown {m['not_in_frozen_rules']} -> semantic_bits_decidable="
          f"{m['semantic_bits_decidable']}")
    c = report["candidate_footprint"]
    print(f"CANDIDATE FOOTPRINT: {c['semantic_bits']} semantic bits + up to "
          f"{c['ecc_collateral_bit_positions']} ECC collateral bit positions "
          f"({c['target_frames']} target frames x {ECC_BITS_PER_FRAME}). "
          f"A Hamming-1 flip is NOT a candidate here: {c['note']}.")
    print(f"\nelapsed {report['elapsed_s']}s")

    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

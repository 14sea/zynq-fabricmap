#!/usr/bin/env python3
"""Re-derive the pinned positive control of `docs/pcap_readback_probe_spec.md` §4.

Host-side, no board.  The probe's whole discriminating power rests on the target frame
being non-blank AND far from its neighbours, so the choice must be reproducible rather
than asserted: this selects it by maximising the minimum Hamming distance to the four
nearest addressable neighbours, over every frame with at least `--min-nonzero` non-zero
words, and prints the table the spec pins.

    scripts/diag_pcap_target_select.py [--bit <file.bit>] [--json out.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import bitstream_frames as bf  # noqa: E402

DEFAULT_BIT = REPO / "gate_runs/claimb_round1_carrier_2026_08_13_erratum006/carrier.bit"
NEIGHBOUR_OFFSETS = (-2, -1, 1, 2)
MIN_NONZERO = 20


def frame_bytes(words: list[int]) -> bytes:
    return b"".join(struct.pack(">I", w) for w in words)


def frame_sha256(words: list[int]) -> str:
    return hashlib.sha256(frame_bytes(words)).hexdigest()


def nonzero_words(words: list[int]) -> int:
    return sum(1 for w in words if w)


def hamming(a: list[int], b: list[int]) -> int:
    return sum(bin(x ^ y).count("1") for x, y in zip(a, b))


def select_target(frames: dict[int, list[int]], min_nonzero: int = MIN_NONZERO):
    """Return (far, min_distance, distances) for the most distinguishable frame.

    Selection: maximise the minimum Hamming distance to the four nearest addressable
    neighbours, over frames with >= `min_nonzero` non-zero words; ties broken by
    non-zero count, then by the highest FAR.
    """
    best = None
    for far, words in frames.items():
        if nonzero_words(words) < min_nonzero:
            continue
        neighbours = [frames[far + off] for off in NEIGHBOUR_OFFSETS
                      if far + off in frames]
        if len(neighbours) != len(NEIGHBOUR_OFFSETS):
            continue
        distances = [hamming(words, n) for n in neighbours]
        # Ties are real and expected: two adjacent frames that differ from each other
        # by a large margin each score that margin.  The tie-break is arbitrary by
        # construction, so it is STATED rather than left to dict order — highest FAR
        # wins.  Either member of a tie serves the probe equally well.
        key = (min(distances), nonzero_words(words), far)
        if best is None or key > best[0]:
            best = (key, far, distances)
    if best is None:
        raise SystemExit("no frame met the selection criteria")
    return best[1], best[0][0], best[2]


def reverse_index(frames) -> dict[str, list[int]]:
    """hash -> EVERY FAR carrying it.  The multiplicity is the point.

    A reverse lookup that returns one FAR would be wrong on this device: **4,716 of the
    5,144 frames are all zero** (`claimb_findings.md` §2.3 F1) and therefore share one
    hash, and four further non-blank pairs collide.  425 hashes cover 5,144 frames.  So
    "the returned bytes name the FAR they came from" is false in general, and a lookup
    that takes the first match would manufacture a confident wrong answer.
    """
    index: dict[str, list[int]] = {}
    for far in sorted(frames):
        index.setdefault(frame_sha256(frames[far]), []).append(far)
    return index


def reverse_index_stats(frames) -> dict:
    """What a reverse lookup can and cannot do on this base — pinned, not assumed."""
    index = reverse_index(frames)
    blank = frame_sha256([0] * bf.FRAME_WORDS)
    duplicate_groups = {h: f for h, f in index.items() if len(f) > 1}
    return {
        "frames": len(frames),
        "unique_hashes": len(index),
        "duplicate_groups": len(duplicate_groups),
        "frames_in_duplicate_groups": sum(len(f) for f in duplicate_groups.values()),
        "blank_group_size": len(index.get(blank, [])),
        "nonblank_duplicate_groups": [
            [f"{far:#010x}" for far in fars]
            for h, fars in sorted(duplicate_groups.items()) if h != blank
        ],
    }


def frame_table_digest(frames) -> tuple[str, int]:
    """A digest over EVERY frame's hash.

    The table lets the runner ask *which* FARs could have produced the bytes it got.  It
    answers with a SET (see `reverse_index`), never with a single FAR.
    """
    lines = "".join(f"{far:#010x} {frame_sha256(frames[far])}\n"
                    for far in sorted(frames))
    return hashlib.sha256(lines.encode()).hexdigest(), len(frames)


def table(frames, target: int) -> list[dict]:
    rows = []
    for off in (-2, -1, 0, 1, 2):
        far = target + off
        words = frames[far]
        rows.append({"far": f"{far:#010x}", "target": off == 0,
                     "nonzero_words": nonzero_words(words),
                     "sha256": frame_sha256(words)})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bit", type=Path, default=DEFAULT_BIT)
    ap.add_argument("--min-nonzero", type=int, default=MIN_NONZERO)
    ap.add_argument("--frame-table", type=Path,
                    help="write the full '<FAR> <sha256>' table (one line per frame)")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    frames = bf.parse_frames(args.bit)["frames"]
    target, min_distance, distances = select_target(frames, args.min_nonzero)
    rows = table(frames, target)
    digest, frame_count = frame_table_digest(frames)
    report = {
        "schema": "pcap_probe_target_selection",
        "schema_version": "1.0.0",
        "bitstream_sha256": hashlib.sha256(args.bit.read_bytes()).hexdigest(),
        "selection": {"min_nonzero_words": args.min_nonzero,
                      "neighbour_offsets": list(NEIGHBOUR_OFFSETS)},
        "target_far": f"{target:#010x}",
        "target_far_fields": bf.far_fields(target),
        "min_hamming_to_neighbours": min_distance,
        "hamming_to_neighbours": distances,
        "frames": rows,
        "frame_table": {"frame_count": frame_count, "sha256": digest,
                        **reverse_index_stats(frames)},
    }
    print(f"target FAR {target:#010x}  {bf.far_fields(target)}")
    print(f"min Hamming to the four nearest neighbours: {min_distance} bits  {distances}")
    for row in rows:
        mark = " <- target" if row["target"] else ""
        print(f"   {row['far']}  nonzero {row['nonzero_words']:3d}  "
              f"{row['sha256']}{mark}")
    print(f"frame-table digest over all {frame_count} frames: {digest}")
    stats = reverse_index_stats(frames)
    print(f"reverse lookup: {stats['unique_hashes']} unique hashes over "
          f"{stats['frames']} frames; {stats['duplicate_groups']} duplicate groups "
          f"covering {stats['frames_in_duplicate_groups']} frames; the all-zero hash "
          f"alone covers {stats['blank_group_size']} FARs")
    print("   non-blank collisions: "
          + "; ".join(" == ".join(g) for g in stats["nonblank_duplicate_groups"]))
    unique_target = len(reverse_index(frames)[frame_sha256(frames[target])]) == 1
    print(f"   target hash globally unique: {unique_target}")
    if args.frame_table:
        args.frame_table.write_text(
            "".join(f"{far:#010x} {frame_sha256(frames[far])}\n"
                    for far in sorted(frames)))
        print(f"wrote {args.frame_table}")
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

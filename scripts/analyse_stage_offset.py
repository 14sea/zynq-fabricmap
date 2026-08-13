#!/usr/bin/env python3
"""Offline: WHERE in the device configuration stream does a staging dump come from?

No board access. Pure measurement, and deliberately no attribution: this tool reports
where the captured window sits and how far that is from the frame that was requested. It
does not say why, and nothing in its output names a cause.

Why this is a separate tool from `analyse_stage_dump.py`
--------------------------------------------------------
`analyse_stage_dump.py` is pinned to the erratum-004 run and to that erratum's 606-word
model (one flush frame, four targets, one flush frame). Erratum 005 reads one frame per
FDRO transaction, so that model does not describe it. Rewriting the older tool in place
would leave `evidence/calibration_noop_2026_08_13_erratum004/dump_analysis.json`
unreproducible from HEAD, so it is left exactly as it is.

This tool assumes no readback model at all. It builds the device's full configuration
stream from the bitstream's own frame sequence and searches it, which is the weakest
assumption that can still answer "where did these words come from".

THE ALL-ZERO FLOOR
------------------
Word-match counts against a sparse bitstream are not scores. All 15 of the guard's frames
are all-zero in `carrier.bit` -- correctly, they are the evolvable region the ECO writes
into -- so a dump with N zeros scores N/101 against any all-zero frame in the device, and
against a great many windows. That floor is reported alongside every count here so a
count at or below it is never read as a partial match.
"""
import argparse
import collections
import hashlib
import json
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import bitstream_frames as bf   # noqa: E402
import board_uboot_axi as axi   # noqa: E402


def build_stream(parsed: dict) -> tuple[list[int], list[int | None]]:
    """The device's frames end to end, in configuration order. Pad frames read as zero."""
    seq = bf.device_frame_sequence(parsed["groups"])
    frames = parsed["frames"]
    words: list[int] = []
    for far in seq:
        words.extend(frames[far] if far is not None else [0] * bf.FRAME_WORDS)
    return words, seq


def exact_offsets(stream: list[int], got: list[int]) -> list[int]:
    """Every word offset at which `got` occurs exactly.

    Done on the packed big-endian bytes so the search is a C-level substring scan rather
    than 52 million Python comparisons. Byte offsets that are not word-aligned cannot be
    real windows and are dropped.
    """
    hay = struct.pack(f">{len(stream)}I", *stream)
    needle = struct.pack(f">{len(got)}I", *got)
    hits, at = [], hay.find(needle)
    while at != -1:
        if at % 4 == 0:
            hits.append(at // 4)
        at = hay.find(needle, at + 1)
    return hits


def scored_offsets(stream: list[int], got: list[int], top: int) -> list[dict]:
    """Best per-offset word-match counts. Only needed when nothing matches exactly."""
    try:
        import numpy as np
    except ImportError:
        return [{"note": "numpy unavailable; scored fallback skipped"}]
    arr = np.array(stream, dtype=np.uint32)
    ref = np.array(got, dtype=np.uint32)
    win = np.lib.stride_tricks.sliding_window_view(arr, len(got))
    score = (win == ref).sum(axis=1)
    order = np.argsort(score)[::-1][:top]
    return [{"offset": int(o), "words_equal": int(score[o])} for o in order]


def locate(offset: int, seq: list[int | None]) -> dict:
    frame_index, word = divmod(offset, bf.FRAME_WORDS)
    far = seq[frame_index]
    return {"offset": offset, "frame_index": frame_index, "word_in_frame": word,
            "far": None if far is None else f"{far:#010x}"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True,
                    help="the gate_runs/ root whose carrier.bit is the reference")
    ap.add_argument("--dump", type=Path, required=True,
                    help="a probe_stage_dump.py record")
    ap.add_argument("--env", type=int, default=0)
    ap.add_argument("--frame", type=int, default=0,
                    help="which frame of --env the engine was asked for")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    # recorded paths are repo-relative, so a run from anywhere reads the same
    def rel(path: Path) -> str:
        resolved = path.resolve()
        return str(resolved.relative_to(REPO) if resolved.is_relative_to(REPO)
                   else resolved)

    dump = json.loads(args.dump.read_text())
    got = [int(w, 16) for w in dump["dump"]["words"]]
    if len(got) != bf.FRAME_WORDS:
        raise SystemExit(f"dump holds {len(got)} words, not {bf.FRAME_WORDS}")

    carrier = args.run_dir / "carrier.bit"
    parsed = bf.parse_frames(carrier)
    stream, seq = build_stream(parsed)
    frames = parsed["frames"]

    zeros = got.count(0)
    requested_far = axi.far_of(args.env, args.frame)
    requested_index = seq.index(requested_far)
    requested_offset = requested_index * bf.FRAME_WORDS
    requested_words = frames[requested_far]

    hits = exact_offsets(stream, got)

    out: dict = {
        "tool": "analyse_stage_offset.py/1.0.0",
        "what": "where the staged 101 words sit in the device configuration stream",
        "attributes_a_cause": False,
        "inputs": {
            "dump": rel(args.dump),
            "dump_sha256_be": dump["dump"]["sha256_be"],
            "carrier_bit": rel(carrier),
            "carrier_sha256": hashlib.sha256(carrier.read_bytes()).hexdigest(),
            "idcode": f"{parsed['idcode']:#010x}",
        },
        "dump_content": {
            "words": len(got),
            "distinct_values": len(set(got)),
            "zero_words": zeros,
            "nonzero_words": len(got) - zeros,
            "most_common": [[f"{v:#010x}", n]
                            for v, n in collections.Counter(got).most_common(4)],
            "base64_be": dump["dump"]["base64_be"],
        },
        "all_zero_floor": {
            "words_equal": zeros,
            "meaning": "any all-zero reference window scores this; counts at or below it "
                       "carry no information",
        },
        "stream": {
            "addressed_frames": len(frames),
            "pad_frames": parsed["pad_frames"],
            "total_words": len(stream),
        },
        "requested": {
            "env": args.env, "frame": args.frame,
            "far": f"{requested_far:#010x}",
            "frame_index": requested_index,
            "offset": requested_offset,
            "nonzero_words_in_reference": sum(1 for w in requested_words if w),
            "words_equal_to_dump": sum(1 for a, b in zip(got, requested_words) if a == b),
            "exact": got == requested_words,
        },
        "frame_aligned_exact_matches": [
            f"{far:#010x}" for far, w in frames.items() if w == got],
        "exact_windows": [locate(o, seq) for o in hits],
    }

    if len(hits) == 1:
        offset = hits[0]
        delta = offset - requested_offset
        whole, part = divmod(delta, bf.FRAME_WORDS)
        end = offset + len(got) - 1
        out["unique_window"] = {
            "start": locate(offset, seq),
            "end": locate(end, seq),
            "delta_words_from_requested": delta,
            # reported both ways because neither is privileged: a delta is a delta
            "delta_as_frames_and_words": f"{whole:+d} frames {part:+d} words",
            "delta_as_frames_minus_words":
                f"{whole + 1:+d} frames {part - bf.FRAME_WORDS:+d} words",
            "identity": f"{delta} = {whole} * {bf.FRAME_WORDS} + {part}",
        }
    elif not hits:
        out["scored_offsets"] = scored_offsets(stream, got, 8)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    print(f"dump {out['inputs']['dump_sha256_be'][:16]}…  "
          f"{out['dump_content']['nonzero_words']} non-zero of {len(got)}")
    print(f"stream {out['stream']['total_words']} words "
          f"({out['stream']['addressed_frames']} addressed + "
          f"{out['stream']['pad_frames']} pad)")
    print(f"requested {out['requested']['far']} -> "
          f"{out['requested']['words_equal_to_dump']}/101 equal "
          f"(all-zero floor {zeros})")
    print(f"exact windows: {len(hits)}")
    for window in out["exact_windows"]:
        print(f"  offset {window['offset']} = {window['far']} word "
              f"{window['word_in_frame']}")
    if "unique_window" in out:
        uw = out["unique_window"]
        print(f"  delta {uw['delta_words_from_requested']:+d} words "
              f"({uw['delta_as_frames_and_words']} | "
              f"{uw['delta_as_frames_minus_words']})")
    print(f"  analysis: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

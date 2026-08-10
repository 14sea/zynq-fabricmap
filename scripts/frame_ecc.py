#!/usr/bin/env python3
"""7-series frame ECC — ported from Project X-Ray, and checked against real silicon output.

Preregistration §6 item 4: *"frame ECC after an INIT change may not be assumed. The ECC
generation path must be cross-validated independently against multiple Vivado
known-answer frames, and until it passes, nothing goes to a board."*

The algorithm is not invented here and not recalled from memory. It is a direct port of
`prjxray/lib/xilinx/xc7series/ecc.cc` (`icap_ecc` / `calculateECC` / `updateECC`,
ISC-licensed, Copyright 2017-2020 The Project X-Ray Authors). Keeping the port
line-shaped like the original is deliberate: a tidier rewrite would be harder to diff
against the source it claims to implement.

**A port is a claim, not evidence.** `--validate` is the evidence: it parses real
Vivado-built bitstreams, recomputes the ECC of every frame from that frame's own words,
and requires it to equal the ECC word Vivado wrote. Hundreds of frames per bitstream,
across specimens built for different sites and different INIT values, so the check covers
frames that differ *because* a LUT INIT differs — which is exactly the mutation this repo
will perform.

Two properties this file must keep, because the whole write path depends on them:

* **the ECC field is masked out of its own input** (word 50 bits 12:0). An implementation
  that folds the old ECC into the new one is stable on unmodified frames and wrong on
  every modified one — it would pass a lazy round-trip test and corrupt real writes;
* **only word 50 changes.** `update_ecc` rewrites 13 bits and nothing else; a frame it
  returns must differ from its input in word 50 alone.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bitstream_frames as bf  # noqa: E402

TOOL_VERSION = "frame_ecc.py/1.0.0"

ECC_WORD = 0x32            # 50 — the word carrying the frame's ECC
ECC_MASK = 0x1FFF          # bits 12:0
ECC_KEEP = 0xFFFFE000      # everything except the ECC field
LAST_WORD = 0x64           # 100 — the frame's final word index

SOURCE = (
    "prjxray/lib/xilinx/xc7series/ecc.cc (ISC, Copyright 2017-2020 "
    "The Project X-Ray Authors)"
)


def icap_ecc(idx: int, data: int, ecc: int) -> int:
    """One word's contribution to the frame ECC. Port of `icap_ecc`.

    The three `val` bases skip the Hamming positions that are powers of two (the parity
    positions themselves), which is why the offsets jump at idx 0x6 and 0x25.
    """
    val = idx * 32  # bit offset

    if idx > 0x25:      # avoid 0x800
        val += 0x1360
    elif idx > 0x6:     # avoid 0x400
        val += 0x1340
    else:               # avoid lower
        val += 0x1320

    if idx == ECC_WORD:  # mask ECC
        data &= ECC_KEEP

    for i in range(32):
        if data & 1:
            ecc ^= val + i
        data >>= 1

    if idx == LAST_WORD:  # last index
        v = ecc & 0xFFF
        v ^= v >> 8
        v ^= v >> 4
        v ^= v >> 2
        v ^= v >> 1
        ecc ^= (v & 1) << 12  # parity

    return ecc & 0xFFFFFFFF


def calculate_ecc(frame: list[int]) -> int:
    """The 13-bit ECC a frame should carry. Port of `calculateECC`."""
    if len(frame) != bf.FRAME_WORDS:
        raise ValueError(
            f"frame has {len(frame)} words, expected {bf.FRAME_WORDS} — the ECC "
            "arithmetic is defined over a whole frame"
        )
    ecc = 0
    for idx, word in enumerate(frame):
        ecc = icap_ecc(idx, word, ecc)
    return ecc


def update_ecc(frame: list[int]) -> list[int]:
    """Return a copy of `frame` with word 50's ECC field replaced. Port of `updateECC`."""
    out = list(frame)
    out[ECC_WORD] = (out[ECC_WORD] & ECC_KEEP) | (calculate_ecc(out) & ECC_MASK)
    return out


def stored_ecc(frame: list[int]) -> int:
    return frame[ECC_WORD] & ECC_MASK


def frame_is_consistent(frame: list[int]) -> bool:
    return stored_ecc(frame) == (calculate_ecc(frame) & ECC_MASK)


# --------------------------------------------------------------------------- validation


def validate_bitstream(path: Path) -> dict:
    """Recompute every frame's ECC and compare against what Vivado wrote."""
    parsed = bf.parse_frames(path)
    checked = mismatched = 0
    examples = []
    for far, frame in parsed["frames"].items():
        if len(frame) != bf.FRAME_WORDS:
            continue
        checked += 1
        want = stored_ecc(frame)
        got = calculate_ecc(frame) & ECC_MASK
        if want != got:
            mismatched += 1
            if len(examples) < 5:
                examples.append((far, want, got))
    return {
        "path": str(path),
        "frames_checked": checked,
        "mismatched": mismatched,
        "examples": examples,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--validate", nargs="+", type=Path, help="bitstreams to check")
    ap.add_argument("--limit", type=int, default=0, help="stop after N bitstreams")
    args = ap.parse_args()

    if not args.validate:
        ap.error("--validate is required")

    paths = args.validate[: args.limit] if args.limit else args.validate
    total_frames = total_bad = 0
    bad_files = []
    for path in paths:
        try:
            report = validate_bitstream(path)
        except SystemExit as exc:  # the parser refuses partial/foreign bitstreams
            print(f"  SKIP {path}: {exc}")
            continue
        total_frames += report["frames_checked"]
        total_bad += report["mismatched"]
        if report["mismatched"]:
            bad_files.append(report)
            print(f"  MISMATCH {path}: {report['mismatched']}/{report['frames_checked']}")
            for far, want, got in report["examples"]:
                print(f"    FAR {far:#010x}: stored {want:#06x} recomputed {got:#06x}")

    print(f"\nsource: {SOURCE}")
    print(f"bitstreams: {len(paths)}   frames checked: {total_frames}   mismatched: {total_bad}")
    if total_bad:
        print("ECC PORT REJECTED — recomputation disagrees with Vivado")
        return 1
    if total_frames == 0:
        print("ECC PORT UNPROVEN — no frames were checked")
        return 1
    print("ECC PORT VALIDATED against Vivado known-answer frames")
    return 0


if __name__ == "__main__":
    sys.exit(main())

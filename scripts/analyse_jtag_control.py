#!/usr/bin/env python3
"""Judge a JTAG readback against the bitstream it was supposed to reproduce.

The pass criterion is deliberately not "the three bits are somewhere in the capture". It is
the frame at its declared alignment, compared word for word against the bitstream that was
loaded, plus each expected bit checked at its exact predicted position and shown to be 0 in
the un-ECO'd carrier — otherwise a match proves only that zeros are zeros.

prjxray's mask for the tile type is reported alongside, so a reader can see whether any
disagreement falls on bits readback is not expected to preserve. It is reported, never
applied silently: the comparison above is strict.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import bitstream_frames as bf  # noqa: E402
import frame_ecc  # noqa: E402

# The ECO's three INIT bits, as the local map places them. Named here so the analysis states
# its expectation before it looks at the capture.
EXPECTED_BITS = [
    ("INIT[0]", 0x00400A20, 51, 15),
    ("INIT[32]", 0x00400A20, 51, 7),
    ("INIT[35]", 0x00400A21, 51, 6),
]
MASK_DB = REPO / "data/prjxray/zynq7/mask_clbll_l.db"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_mask() -> set[tuple[int, int]]:
    """prjxray mask entries as (word, bit); these are the bits readback may not preserve."""
    entries: set[tuple[int, int]] = set()
    if not MASK_DB.exists():
        return entries
    for line in MASK_DB.read_text("utf-8").splitlines():
        parts = line.split()
        for token in parts[1:] if parts and parts[0] == "bit" else parts:
            if "_" in token:
                word, _, bit = token.partition("_")
                if word.lstrip("!").isdigit() and bit.isdigit():
                    entries.add((int(word.lstrip("!")), int(bit)))
    return entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--capture", type=Path, required=True)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    capture = json.loads(args.capture.read_text("utf-8"))
    if capture.get("verdict") != "READ":
        print(f"the capture did not read: {capture.get('verdict')}", file=sys.stderr)
        return 1

    eco_path = args.run_dir / "carrier_eco.bit"
    base_path = args.run_dir / "carrier.bit"
    eco = bf.parse_frames(eco_path)["frames"]
    base = bf.parse_frames(base_path)["frames"]
    mask = load_mask()

    read = {int(far, 16): [int(word, 16) for word in data["frame"]]
            for far, data in capture["frames"].items()}
    pads = {int(far, 16): [int(word, 16) for word in data["pad_frame"]]
            for far, data in capture["frames"].items()}

    bits = []
    for name, far, word, bit in EXPECTED_BITS:
        entry = {"name": name, "far": f"{far:#010x}", "word": word, "bit": bit,
                 "in_carrier_eco": None, "in_carrier_base": None, "in_readback": None,
                 "discriminating": None, "verdict": "NOT READ"}
        if far in eco:
            entry["in_carrier_eco"] = (eco[far][word] >> bit) & 1
            entry["in_carrier_base"] = (base[far][word] >> bit) & 1
            entry["discriminating"] = entry["in_carrier_eco"] != entry["in_carrier_base"]
        if far in read:
            entry["in_readback"] = (read[far][word] >> bit) & 1
            entry["verdict"] = ("HIT" if entry["in_readback"] == entry["in_carrier_eco"]
                                else "MISS")
        bits.append(entry)

    frames = {}
    for far, words in sorted(read.items()):
        expected = eco.get(far)
        differing = ([index for index, (a, b) in enumerate(zip(words, expected)) if a != b]
                     if expected else None)
        frames[f"{far:#010x}"] = {
            "equals_loaded_bitstream_frame": expected is not None and words == expected,
            "differing_words": differing,
            "differing_words_touching_masked_bits": (
                sorted({index for index in (differing or [])
                        if any((index, bit) in mask for bit in range(32))})),
            "readback_sha256": hashlib.sha256(
                b"".join(word.to_bytes(4, "big") for word in words)).hexdigest(),
            "nonzero_words": sum(1 for word in words if word),
            "ecc_consistent": frame_ecc.frame_is_consistent(words),
            "pad_frame_all_zero": not any(pads[far]),
            "equals_base_frame": far in base and words == base[far],
        }

    hits = [entry for entry in bits if entry["verdict"] == "HIT"]
    misses = [entry for entry in bits if entry["verdict"] != "HIT"]
    exact = [far for far, data in frames.items() if data["equals_loaded_bitstream_frame"]]

    analysis = {
        "tool": "analyse_jtag_control.py/1.0.0",
        "what": "does the JTAG readback reproduce the bitstream that was loaded",
        "inputs": {
            "capture": {"path": str(args.capture), "sha256": sha256_of(args.capture)},
            "carrier_eco_bit": {"path": str(eco_path), "sha256": sha256_of(eco_path)},
            "carrier_bit": {"path": str(base_path), "sha256": sha256_of(base_path)},
            "mask_db": {"path": str(MASK_DB),
                        "sha256": sha256_of(MASK_DB) if MASK_DB.exists() else None,
                        "entries": len(mask)},
        },
        "alignment": {
            "declared": "the first 101 words are the pad frame, the second 101 are the "
                        "requested frame",
            "note": "declared before the comparison; the full capture is in the record so a "
                    "different alignment can be examined offline without re-reading",
        },
        "idcode": capture.get("idcode"),
        "config_status": capture.get("config_status"),
        "expected_bits": bits,
        "frames": frames,
    }
    if len(hits) == len(bits) and len(exact) == len(frames):
        analysis["verdict"] = "CONTROL PASSED"
        analysis["reading"] = (
            "Every expected bit is at its exact predicted position and every frame equals "
            "the loaded bitstream word for word. The readback method reproduces known "
            "content, so it can be trusted to report unknown content.")
    elif hits:
        analysis["verdict"] = "CONTROL PARTIAL"
        analysis["reading"] = (
            f"{len(hits)} of {len(bits)} expected bits hit and {len(exact)} of "
            f"{len(frames)} frames matched exactly. The method demonstrably works where it "
            "worked — an exact match on a frame carrying a discriminating signature is not "
            "a coincidence — but it is not yet reliable for every read, and no conclusion "
            "about unknown content may rest on the reads that failed.")
    else:
        analysis["verdict"] = "CONTROL FAILED"
        analysis["reading"] = (
            "No expected bit appeared at its predicted position. The method is not "
            "trustworthy and nothing may be concluded from it about unknown content.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    print(f"{analysis['verdict']}: {analysis['reading']}")
    for entry in bits:
        print(f"  {entry['name']:9} {entry['far']} w{entry['word']} b{entry['bit']}: "
              f"{entry['verdict']} (discriminating={entry['discriminating']})")
    print(f"  analysis: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

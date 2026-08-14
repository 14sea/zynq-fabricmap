#!/usr/bin/env python3
"""Offline analysis of a DRAM capture. It attributes nothing it cannot compute.

The question a capture invites is "where did this frame come from", and the honest answer
depends entirely on how distinctive the bytes are. So this tool measures that first: how
many word offsets of the device stream the captured window matches. A window that matches
one offset names an address; a window that matches thousands names none, and no amount of
bit-swap or alignment variation rescues it.

Every input is hashed into the output. The expected candidate frame is re-derived here from
the frozen map, manifest and report rather than read out of the producer's artifact, so this
is a second opinion and not a restatement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import bitstream_frames as bf  # noqa: E402
import frame_ecc  # noqa: E402

LUT_FEATURE = re.compile(r"CLBLL_L\.SLICEL_X0\.ALUT\.INIT\[(\d+)\]$")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    """Repo-relative where possible, so the record reads the same from any cwd."""
    resolved = path.resolve()
    return str(resolved.relative_to(REPO)) if resolved.is_relative_to(REPO) else str(resolved)


def derive_candidate(manifest: dict, local_map: dict, report: dict) -> tuple[dict, int, int]:
    """The candidate frames, re-derived from the frozen inputs. Returns (frames, mask, init)."""
    positions = {}
    for entry in local_map["universe"]["addresses"]:
        found = LUT_FEATURE.match(entry["feature"])
        if found:
            positions[int(found.group(1))] = (
                int(entry["far"], 16), entry["word"], entry["bit"])
    mask = 0
    for position in positions:
        mask |= 1 << position
    target = int(report["per_lut"][0]["target_truth_table"].split("'h")[1], 16)
    init = target & mask

    base = {int(record["far"], 16): [int(word, 16) for word in record["words"]]
            for record in manifest["frames"]}
    frames = {far: list(words) for far, words in base.items()}
    touched = set()
    for position in range(64):
        if (init >> position) & 1:
            far, word, bit = positions[position]
            frames[far][word] |= 1 << bit
            touched.add(far)
    for far in touched:
        frames[far] = frame_ecc.update_ecc(frames[far])
    return frames, mask, init


def offsets_matching(stream: list[int], window: list[int]) -> int:
    """How many word offsets of `stream` equal `window`.

    An all-zero window is the case that matters here, so it gets the cheap path: count the
    windows containing no non-zero word with a prefix sum, rather than 500k slice compares.
    """
    if any(window):
        return sum(1 for i in range(len(stream) - len(window) + 1)
                   if stream[i:i + len(window)] == window)
    prefix = [0]
    for word in stream:
        prefix.append(prefix[-1] + (1 if word else 0))
    size = len(window)
    return sum(1 for i in range(len(stream) - size + 1)
               if prefix[i + size] - prefix[i] == 0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--capture", type=Path, required=True)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--report", type=Path,
                    default=REPO / "gate_runs/claimb_round1_reachability_2026_08_10"
                                   "/reachability_report.json")
    ap.add_argument("--far", default="0x00400A20", help="the FAR the readback requested")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    capture = json.loads(args.capture.read_text("utf-8"))
    if capture.get("verdict") != "CAPTURED":
        print(f"the capture did not capture: {capture.get('verdict')}", file=sys.stderr)
        return 1
    window = [int(word, 16) for word in capture["words"]]

    manifest_path = args.run_dir / "phenotype_manifest.json"
    map_path = args.run_dir / "local_map.json"
    bit_path = args.run_dir / "carrier.bit"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    local_map = json.loads(map_path.read_text("utf-8"))
    report = json.loads(args.report.read_text("utf-8"))

    candidate, mask, init = derive_candidate(manifest, local_map, report)
    far = int(args.far, 16)
    base = {int(record["far"], 16): [int(word, 16) for word in record["words"]]
            for record in manifest["frames"]}

    device = bf.parse_frames(bit_path)["frames"]
    stream: list[int] = []
    for far_key in sorted(device):
        stream.extend(device[far_key])

    expected = candidate[far]
    differing_words = [i for i, (a, b) in enumerate(zip(expected, base[far])) if a != b]

    analysis = {
        "tool": "analyse_ddr_capture.py/1.0.0",
        "what": "what the captured window can and cannot say about its origin",
        "inputs": {
            "capture": {"path": rel(args.capture),
                        "sha256": sha256_of(args.capture)},
            "phenotype_manifest": {"path": rel(manifest_path),
                                   "sha256": sha256_of(manifest_path)},
            "local_map": {"path": rel(map_path),
                          "sha256": sha256_of(map_path)},
            "carrier_bit": {"path": rel(bit_path),
                            "sha256": sha256_of(bit_path)},
            "reachability_report": {"path": rel(args.report),
                                    "sha256": sha256_of(args.report)},
        },
        "requested_far": args.far,
        "derived": {
            "mutable_mask": f"0x{mask:016X}",
            "actual_init": f"0x{init:016X}",
            "expected_frame_sha256": hashlib.sha256(
                b"".join(w.to_bytes(4, "big") for w in expected)).hexdigest(),
            "expected_differs_from_base_in_words": differing_words,
        },
        "captured": {
            "sha256": capture["frame_sha256"],
            "words": len(window),
            "nonzero_words": sum(1 for word in window if word),
            "all_zero": not any(window),
        },
        "comparisons": {
            "equals_expected_candidate_frame": window == expected,
            "equals_base_frame_at_requested_far": window == base[far],
        },
        "device_stream": {
            "source": "the base carrier bitstream; a post-write image cannot be obtained "
                      "without an independent readback path",
            "frames": len(device),
            "words": len(stream),
            "all_zero_frames": sum(1 for words in device.values() if not any(words)),
            "word_offsets_matching_the_captured_window": offsets_matching(stream, window),
        },
    }

    matches = analysis["device_stream"]["word_offsets_matching_the_captured_window"]
    if analysis["captured"]["all_zero"]:
        analysis["verdict"] = "UNDISCRIMINATING"
        analysis["reading"] = (
            f"The window is all zero and matches {matches} word offsets of the device "
            "stream, so it names no address. Bit-swap and word-alignment variants cannot "
            "separate anything either: an all-zero window is invariant under both. This "
            "cannot distinguish a pass-2 write that never landed from a read that reached a "
            "different, also-zero frame.")
    elif matches == 1:
        analysis["verdict"] = "LOCATES"
        analysis["reading"] = (
            "The window matches exactly one word offset of the device stream, so its origin "
            "is named by the data itself.")
    else:
        analysis["verdict"] = "AMBIGUOUS"
        analysis["reading"] = (
            f"The window is not all zero but matches {matches} offsets; it constrains the "
            "origin without naming it.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    print(f"{analysis['verdict']}: {analysis['reading']}")
    print(f"  analysis: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

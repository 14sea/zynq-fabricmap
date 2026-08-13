#!/usr/bin/env python3
"""Offline reading of the staging dump. No board access.

Per the ruling: build envelope 0's expected 606-word readback sequence

    flush-buffer dummy + target0 + target1 + target2 + target3 + flush-memory

search every contiguous 101-word window for an exact match, search all 5,144 frames of the
carrier bitstream for an exact match, and if neither hits, report per-offset word-match
counts, the best offset and the first mismatches — without attributing a cause.
"""
import json
import struct
import sys
from pathlib import Path

REPO = Path("/home/test/zynq_fabricmap")
sys.path.insert(0, str(REPO / "scripts"))
import bitstream_frames as bf  # noqa: E402

RUN = REPO / "gate_runs/claimb_round1_carrier_2026_08_13_erratum004"
DUMP = REPO / "evidence/calibration_noop_2026_08_13_erratum004/stage_dump.json"

dump = json.loads(DUMP.read_text())
got = [int(w, 16) for w in dump["dump"]["words"]]
assert len(got) == 101

manifest = json.loads((RUN / "phenotype_manifest.json").read_text())
pinned = {int(r["far"], 16): [int(w, 16) for w in r["words"]] for r in manifest["frames"]}
env0 = manifest["write_envelope"]["envelopes"][0]
targets = [int(f, 16) for f in env0["target_fars"]]
flush = int(env0["flush_far"], 16)

# the sequence the engine should have been reading, in order
expected = (pinned[flush] + [w for far in targets for w in pinned[far]] + pinned[flush])
assert len(expected) == 606

out = {
    "dump_sha256_be": dump["dump"]["sha256_be"],
    "expected_sequence": {
        "shape": "flush-buffer dummy + target0..3 + flush-memory",
        "fars": [f"0x{flush:08x}"] + [f"0x{f:08x}" for f in targets] + [f"0x{flush:08x}"],
        "words": 606,
    },
}

# ---- 1. exact match against every contiguous 101-word window of the 606
exact = [off for off in range(606 - 101 + 1) if expected[off:off + 101] == got]
out["exact_window_matches"] = exact
out["delta_from_expected_offset_101"] = [off - 101 for off in exact]

# ---- 2. exact match against every frame of the carrier bitstream
parsed = bf.parse_frames(RUN / "carrier.bit")
frames = parsed["frames"]
hits = [far for far, words in frames.items() if words == got]
out["bitstream"] = {
    "frames_searched": len(frames),
    "exact_frame_matches": [f"0x{far:08x}" for far in hits],
}

# ---- 3. no exact match: the shape of the disagreement, and nothing more
if not exact:
    counts = []
    for off in range(606 - 101 + 1):
        window = expected[off:off + 101]
        counts.append(sum(1 for a, b in zip(window, got) if a == b))
    best = max(range(len(counts)), key=lambda i: counts[i])
    window = expected[best:best + 101]
    first = [{"index": i, "expected": f"0x{window[i]:08x}", "got": f"0x{got[i]:08x}"}
             for i in range(101) if window[i] != got[i]][:8]
    out["no_exact_match"] = {
        "best_offset": best,
        "best_offset_matching_words": counts[best],
        "matching_words_at_offset_101": counts[101],
        "match_count_histogram": {str(v): counts.count(v) for v in sorted(set(counts))},
        "first_mismatches_at_best_offset": first,
    }

# ---- what the dump IS, stated without attribution
distinct = sorted(set(got))
out["dump_shape"] = {
    "distinct_values": len(distinct),
    "values": [f"0x{v:08x}" for v in distinct[:8]],
    "all_identical": len(distinct) == 1,
}
if len(distinct) == 1:
    v = distinct[0]
    # the engine stores br8(icap_dout); so the wire carried br8 of what is stored
    raw = int(f"{int(f'{v:032b}'[::-1], 2):032b}", 2)  # placeholder, replaced below
    def br8(d: int) -> int:
        out_ = 0
        for b in range(8):
            for byte in range(4):
                if d >> (byte * 8 + (7 - b)) & 1:
                    out_ |= 1 << (byte * 8 + b)
        return out_
    out["dump_shape"]["stored_value"] = f"0x{v:08x}"
    out["dump_shape"]["value_on_the_ICAPE2_O_pins"] = f"0x{br8(v):08x}"

print(json.dumps(out, indent=2))
(DUMP.parent / "dump_analysis.json").write_text(json.dumps(out, indent=2) + "\n")

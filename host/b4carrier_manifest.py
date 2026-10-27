#!/usr/bin/env python3
"""The B4 carrier v2 manifest: what the built bitstream holds at the 21 certified addresses and in the target column,
read with the repository's frame parser (scripts/bitstream_frames.py, read-only) against the certificate mapping
(b4/host/b4_ff_mapping.py, read-only). It is the frame-content reference of the loaded carrier that the session-opening
record binds to (docs/b4_observation_contract.md 5.5), and a known-answer check of the placement: the natural build
must show CEUSEDMUX = SRUSEDMUX = 1 (CE and SR routed and used) and every other certified bit 0 (INIT 1, SRVAL 1,
asynchronous, flip-flop, clock not inverted) — anything else means the elements are not where the addresses say.

    host/b4carrier_manifest.py builds/b4/b4.bit [--json builds/b4/b4_carrier_manifest.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "scripts"))
sys.path.insert(0, str(R / "b4/host"))
import bitstream_frames as bf  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402

SCHEMA, VERSION = "b4_carrier_manifest", "1.0.0"
# the natural build: CE and SR are connected (used), everything else at the all-zero genome's value
EXPECTED_NATURAL = {"ce_mode": 1, "sr_mode": 1}


def address_parts(a: str) -> tuple[int, int, int]:
    far, word, bit = a.split("/")
    return int(far, 16), int(word), int(bit)


def manifest(bit_path: Path) -> dict:
    data = bit_path.read_bytes()
    parsed = bf.parse_frames(bit_path, data=data)
    frames = parsed["frames"]
    m = bm.site_mapping()
    rows, column = [], {}
    fars = sorted({address_parts(a)[0] for a in m.addresses})
    base_major = fars[0] & ~0x7F                      # the column's minor 0
    for minor in range(36):                           # a 7-series CLB column: 36 frames
        far = base_major + minor
        if far in frames:
            column[f"{far:#010x}"] = hashlib.sha256(b"".join(w.to_bytes(4, "big") for w in frames[far])).hexdigest()
    for a in m.addresses:
        far, word, bit = address_parts(a)
        e = m.entries[a]
        v = bf.bit_value(frames[far], word, bit)
        rows.append({"address": a, "semantic": e.semantic, "element": e.element, "bit_one_means": e.bit_one_means, "value": v,
                     "expected_natural": EXPECTED_NATURAL.get(e.semantic, 0)})
    mismatches = [r["address"] for r in rows if r["value"] != r["expected_natural"]]
    universe_words = sorted({(f"{address_parts(a)[0]:#010x}", address_parts(a)[1]) for a in m.addresses})
    return {"schema": SCHEMA, "schema_version": VERSION, "bitstream": str(bit_path), "bitstream_sha256": hashlib.sha256(data).hexdigest(),
            "idcode": f"{parsed['idcode']:#010x}" if parsed["idcode"] is not None else None, "site": m.site,
            "certificate": m.certificate_rel, "certificate_sha256": m.certificate_sha256,
            "target_column_frames_sha256": column, "universe_words": [{"far": f, "word": w} for f, w in universe_words],
            "addresses": rows, "natural_build_mismatches": mismatches,
            "base_genome": 0, "note": "the loaded carrier holds the natural build (CE / SR used); the session root writes genome 0 as a signed candidate (contract 5.5)"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bit", type=Path); ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    mf = manifest(a.bit)
    if a.json:
        a.json.write_text(json.dumps(mf, indent=1) + "\n")
    for r in mf["addresses"]:
        print(f"{r['address']:18} {r['semantic']:13} {str(r['element']):5} value {r['value']} expected {r['expected_natural']}")
    print("mismatches:", mf["natural_build_mismatches"] or "none")
    return 1 if mf["natural_build_mismatches"] else 0


if __name__ == "__main__":
    sys.exit(main())

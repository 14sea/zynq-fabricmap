#!/usr/bin/env python3
"""Carrier design §4 check 3 — judge the INIT ECO differential, bit for bit.

`vivado/carrier/init_eco_differential.tcl` opens the ROUTED checkpoint, changes one
evolvable LUT's INIT and writes a bitstream, with no re-synthesis, no re-placement and no
re-routing (it refuses if the routing census moves). This script decides whether the
resulting frame difference is what the `local_map` says it must be:

* **exactly the frames the map predicts**, and no others — over all frames in the device,
  not only the fifteen in the write envelope. A change leaking into a frame outside the
  envelope is the failure this check exists to find, and looking only inside the envelope
  could not see it;
* within each of those frames, **exactly the predicted address bits**, plus word 50, whose
  new value must equal an **independent recomputation** of the ECC over the resulting frame
  content. An ECC that merely differs is refused, and so is a stale one.

This is the same authority erratum 001 moved everything else to: bit equality against the
carrier base, with no segbits database consulted, so a routing bit nobody has ever named is
covered exactly as well as one we can name.

**The predicted set is read from the map, never from the observed diff.** A check that
derived its expectation from what it saw would accept anything.

Exit codes: 0 accepted, 2 refused, 3 usage/IO.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bitstream_frames as bf  # noqa: E402
import frame_ecc as fe  # noqa: E402

TOOL_VERSION = "gate_init_eco.py/1.0.0"

def parse_address_key(key: str) -> tuple[int, int, int]:
    """`0x00400A20/51/15` -> (far, word, bit). Refuses anything else."""
    parts = key.split("/")
    if len(parts) != 3:
        raise ValueError(f"malformed address key: {key!r}")
    return int(parts[0], 16), int(parts[1]), int(parts[2])


def predicted_bits(local_map: dict, lut_key: str, init_before: int, init_after: int
                   ) -> dict[int, set[tuple[int, int]]]:
    """Which (word, bit) in which FAR the map says this INIT change must touch.

    Only the init indices that ACTUALLY change are predicted. An address whose init index
    did not move must not move in the bitstream either, so it belongs in neither set.
    """
    by_lut = local_map["index"]["by_lut"]
    if lut_key not in by_lut:
        raise ValueError(
            f"{lut_key!r} is not in the map's by_lut index; have: {sorted(by_lut)}"
        )
    changed = init_before ^ init_after
    out: dict[int, set[tuple[int, int]]] = {}
    covered: set[int] = set()
    for entry in by_lut[lut_key]:
        idx = entry["init_index"]
        covered.add(idx)
        if not (changed >> idx) & 1:
            continue
        far, word, bit = parse_address_key(entry["address_key"])
        out.setdefault(far, set()).add((word, bit))

    # An INIT index that moved but is NOT in the certified set would be predicted nowhere
    # and would then show up as an unexplained difference. Say so as its own failure rather
    # than letting it masquerade as a stray bit.
    uncovered = [i for i in range(64) if (changed >> i) & 1 and i not in covered]
    if uncovered:
        raise ValueError(
            f"INIT indices {uncovered} changed but are not certified addresses for "
            f"{lut_key}: the differential cannot be judged against the map"
        )
    return out


def frame_words(path: Path) -> dict[int, list[int]]:
    parsed = bf.parse_frames(path)
    return {far: list(words) for far, words in parsed["frames"].items()}


def findings(base_path: Path, eco_path: Path, local_map: dict, eco_rec: dict
             ) -> tuple[list[dict], dict]:
    out: list[dict] = []

    def bad(kind: str, message: str, **detail):
        out.append({"kind": kind, "message": message, **detail})

    init_before = int(eco_rec["init_before"].split("'h")[1], 16)
    init_after = int(eco_rec["init_after"].split("'h")[1], 16)

    lut_key = eco_rec.get("map_lut_key")
    if not lut_key:
        raise ValueError("the ECO record carries no map_lut_key")

    predicted = predicted_bits(local_map, lut_key, init_before, init_after)

    base = frame_words(base_path)
    eco = frame_words(eco_path)

    if set(base) != set(eco):
        bad(
            "structure",
            "the two bitstreams do not carry the same frame set",
            only_in_base=len(set(base) - set(eco)),
            only_in_eco=len(set(eco) - set(base)),
        )
        return out, {}

    differing = {far for far in base if base[far] != eco[far]}
    expected_frames = set(predicted)

    for far in sorted(differing - expected_frames):
        bad(
            "stray_frame",
            "a frame differs that the map does not predict",
            far=f"0x{far:08X}",
            differing_words=[i for i in range(len(base[far])) if base[far][i] != eco[far][i]],
        )
    for far in sorted(expected_frames - differing):
        bad(
            "missing_frame",
            "the map predicts a frame that did not change",
            far=f"0x{far:08X}",
        )

    for far in sorted(expected_frames & differing):
        b, e = base[far], eco[far]
        seen: set[tuple[int, int]] = set()
        for w in range(len(b)):
            if b[w] == e[w]:
                continue
            for bit in range(32):
                if ((b[w] >> bit) & 1) == ((e[w] >> bit) & 1):
                    continue
                # Word 50 carries the 13-bit ECC field AND ordinary content. Only the ECC
                # field is exempt from the address prediction — it is judged below, as a
                # recomputation. Exempting the whole word would hide 19 real content bits.
                if w == fe.ECC_WORD and ((fe.ECC_MASK >> bit) & 1):
                    continue
                seen.add((w, bit))
        want = predicted[far]
        for wb in sorted(seen - want):
            bad("stray_bit", "a bit changed that the map does not predict",
                far=f"0x{far:08X}", word=wb[0], bit=wb[1])
        for wb in sorted(want - seen):
            bad("missing_bit", "the map predicts a bit that did not change",
                far=f"0x{far:08X}", word=wb[0], bit=wb[1])

        # the ECC must be a CORRECT RECOMPUTATION over the resulting content
        if not fe.frame_is_consistent(e):
            bad(
                "ecc",
                "word 50's ECC field is not a correct recomputation over the resulting frame",
                far=f"0x{far:08X}",
                found=f"0x{fe.stored_ecc(e):04X}",
                expected=f"0x{fe.calculate_ecc(e) & fe.ECC_MASK:04X}",
            )

    summary = {
        "lut_key": lut_key,
        "init_before": f"0x{init_before:016X}",
        "init_after": f"0x{init_after:016X}",
        "frames_total": len(base),
        "frames_differing": len(differing),
        "frames_predicted": len(expected_frames),
        "bits_predicted": sum(len(v) for v in predicted.values()),
    }
    return out, summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--build-dir", type=Path, required=True)
    ap.add_argument("--map", type=Path, required=True)
    ap.add_argument("--map-lut-key", required=True,
                    help="the by_lut key of the ECO'd cell, e.g. CLBLL_L.SLICEL_X0.ALUT")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    try:
        eco_rec = json.loads((args.build_dir / "carrier_eco.json").read_text(encoding="utf-8"))
        local_map = json.loads(args.map.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read inputs: {exc}", file=sys.stderr)
        return 3

    eco_rec["map_lut_key"] = args.map_lut_key
    if eco_rec.get("reimplemented") is not False:
        print("REFUSED: the ECO record does not assert reimplemented=false", file=sys.stderr)
        return 2

    try:
        problems, summary = findings(
            args.build_dir / "carrier.bit",
            args.build_dir / eco_rec["bitstream"],
            local_map,
            eco_rec,
        )
    except (ValueError, KeyError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    verdict = {
        "tool": TOOL_VERSION,
        "build_dir": str(args.build_dir),
        "cell": eco_rec.get("cell"),
        "loc": eco_rec.get("loc"),
        "bel": eco_rec.get("bel"),
        "accepted": not problems,
        "summary": summary,
        "findings": problems,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")

    if problems:
        for p in problems[:20]:
            print(f"REFUSED [{p['kind']}] {p['message']}: "
                  + ", ".join(f"{k}={v}" for k, v in p.items() if k not in ("kind", "message")),
                  file=sys.stderr)
        if len(problems) > 20:
            print(f"... and {len(problems) - 20} more", file=sys.stderr)
        return 2

    print(
        f"ACCEPTED: {summary['frames_differing']} of {summary['frames_total']} frames differ, "
        f"exactly the {summary['frames_predicted']} the map predicts; "
        f"{summary['bits_predicted']} predicted bit(s) moved, no stray bits, "
        "every ECC a correct recomputation"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

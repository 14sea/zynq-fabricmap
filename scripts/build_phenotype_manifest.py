#!/usr/bin/env python3
"""Pin the write envelope: base bitstream, target frames, flush frames, whitelist, clock.

This is the artifact the sequence builder, the candidate gate and the board scripts all
read, so the envelope is one pinned fact rather than a convention re-implemented in three
places.

Two things it derives rather than assumes
-----------------------------------------

**The flush frame is read out of the device frame sequence, never computed as FAR+1.**
That assumption is wrong on this device and would have written to a frame that does not
exist: the 12 target FARs form three groups, and two of them end at the last minor of
their column (`0x00400A23` is major 20 minor 35; `0x00400A24` does not exist). A 7-series
frame commits only when the *next* frame shifts in, and the FAR auto-increments through
the device's own frame order — which at a column boundary continues into the next column
(`0x00400A23` -> `0x00400A80`, major 21 minor 0). So two of the three flush frames belong
to a different column, and therefore to different logic. That is exactly why preregistration
§6 item 2 makes them non-writable authority: they are written back verbatim so the write is
a no-op, and any difference is a violation rather than "our own logic changing".

**Group membership comes from the map, not from a hard-coded FAR list.** The groups are
the maximal runs of consecutive frames in the map's `by_far` index, so a different
certificate produces a different envelope instead of silently reusing this one.

What it refuses: a map that is not a fresh derivation of its certificate; a base bitstream
whose IDCODE or part disagrees with the map's target; a target frame the bitstream does not
carry; a whitelist address that falls outside the target frames; and a run whose groups do
not partition the target FARs exactly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bitstream_frames as bf  # noqa: E402
import frame_ecc as fe  # noqa: E402

TOOL_VERSION = "build_phenotype_manifest.py/1.0.0"
SCHEMA_VERSION = "1.0.0"

ENVELOPE_OVERHEAD_WORDS = 31  # zynq-xpart's proven envelope: 233 words - 202 payload
REQUIRED_FCLK0_MHZ = 50.0


class EnvelopeError(Exception):
    """A refusal."""


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def frame_sha256(words: list[int]) -> str:
    blob = b"".join(w.to_bytes(4, "big") for w in words)
    return hashlib.sha256(blob).hexdigest()


def repo_relative(path: Path, what: str) -> str:
    """Repo-relative or refused — never a crash, and never a bare filename.

    A manifest pins paths so a consumer can resolve them. One that points outside the
    tree describes a filesystem the consumer does not have, and falling back to
    `path.name` would hide that behind a plausible-looking string. Both arguments get the
    same treatment; an earlier version guarded only one and raised ValueError on the
    other, which is a crash rather than a judgement.
    """
    if not path.is_relative_to(REPO_ROOT):
        raise EnvelopeError(
            f"{what} is outside the repository: {path} — a manifest may only pin "
            "repo-relative paths"
        )
    return path.relative_to(REPO_ROOT).as_posix()


def load_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise EnvelopeError(f"not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EnvelopeError(f"not valid JSON: {path}: {exc}") from exc


def consecutive_groups(fars: list[int]) -> list[list[int]]:
    """Maximal runs of consecutive FARs, in ascending order."""
    groups: list[list[int]] = []
    for far in sorted(fars):
        if groups and far == groups[-1][-1] + 1:
            groups[-1].append(far)
        else:
            groups.append([far])
    return groups


def successor_in_device_order(far: int, sequence: list) -> int:
    """The frame the FAR auto-increment reaches after `far`.

    Pad frames (None in the sequence) are skipped deliberately: they address nothing, so
    a burst that runs into one does not commit anything there — but a flush frame must be
    a real frame whose content we can pin, so the search continues past them and the fact
    that it had to is reported by the caller.
    """
    try:
        index = sequence.index(far)
    except ValueError as exc:
        raise EnvelopeError(f"{far:#010x} is not a frame this device carries") from exc
    for candidate in sequence[index + 1:]:
        if candidate is not None:
            return candidate
    raise EnvelopeError(
        f"{far:#010x} is the last frame of the device — nothing can flush it"
    )


def check_base_ecc(frame_records: list[dict]) -> None:
    """Refuse a base whose own frames do not verify.

    Named rather than inlined because every real base frame passes, so this refusal is
    never exercised by correct input — an inline version is an unexercised rule that a
    mutation removes without any test noticing.
    """
    inconsistent = [r["far"] for r in frame_records if not r["ecc_consistent"]]
    if inconsistent:
        raise EnvelopeError(
            f"base frames whose stored ECC does not match their content: {inconsistent} — "
            "the base is not a clean authority to pin"
        )


def build_manifest(
    map_path: Path,
    base_bitstream: Path,
    phenotype_id: str,
    pblock: str | None,
) -> dict:
    map_rel = repo_relative(map_path, "the local_map")
    base_rel = repo_relative(base_bitstream, "the base bitstream")
    local_map = load_json(map_path)
    if local_map.get("schema") != "local_map":
        raise EnvelopeError(f"{map_path}: not a local_map")

    parsed = bf.parse_frames(base_bitstream)
    frames = parsed["frames"]
    groups_layout = parsed["groups"]
    sequence = bf.device_frame_sequence(groups_layout)

    target_fars = sorted(int(far, 16) for far in local_map["index"]["by_far"])
    for far in target_fars:
        if far not in frames:
            raise EnvelopeError(
                f"target frame {far:#010x} is not in {base_bitstream} — the base "
                "bitstream does not cover the map's universe"
            )

    # Every whitelisted address must live inside a target frame; an address outside them
    # could never be written by this envelope, and a manifest that carried it would be
    # promising a reach it does not have.
    whitelist = {}
    for entry in local_map["universe"]["addresses"]:
        far = int(entry["far"], 16)
        if far not in target_fars:
            raise EnvelopeError(
                f"whitelist address {entry['key']} is outside the target frames"
            )
        whitelist.setdefault(far, []).append(
            {"word": entry["word"], "bit": entry["bit"], "feature": entry["feature"]}
        )

    envelopes = []
    flush_fars = []
    for index, group in enumerate(consecutive_groups(target_fars)):
        flush = successor_in_device_order(group[-1], sequence)
        if flush in target_fars:
            raise EnvelopeError(
                f"envelope {index}: flush frame {flush:#010x} is itself a target — the "
                "groups do not partition the universe"
            )
        if flush not in frames:
            raise EnvelopeError(
                f"envelope {index}: flush frame {flush:#010x} is not in the base bitstream"
            )
        flush_fars.append(flush)
        payload_words = (len(group) + 1) * bf.FRAME_WORDS
        same_column = bf.far_fields(flush)["major"] == bf.far_fields(group[-1])["major"]
        envelopes.append(
            {
                "index": index,
                "far_set": f"{group[0]:#010x}",
                "target_fars": [f"{far:#010x}" for far in group],
                "flush_far": f"{flush:#010x}",
                "flush_is_same_column": same_column,
                "payload_words": payload_words,
                "overhead_words": ENVELOPE_OVERHEAD_WORDS,
                "total_words": payload_words + ENVELOPE_OVERHEAD_WORDS,
            }
        )

    if len(set(flush_fars)) != len(flush_fars):
        raise EnvelopeError(f"two envelopes share a flush frame: {flush_fars}")

    frame_records = []
    for far in target_fars:
        words = frames[far]
        frame_records.append(
            {
                "far": f"{far:#010x}",
                "role": "target",
                "sha256": frame_sha256(words),
                "ecc_consistent": fe.frame_is_consistent(words),
                "words": [f"{w:#010x}" for w in words],
            }
        )
    for far in flush_fars:
        words = frames[far]
        frame_records.append(
            {
                "far": f"{far:#010x}",
                "role": "flush",
                "sha256": frame_sha256(words),
                "ecc_consistent": fe.frame_is_consistent(words),
                "words": [f"{w:#010x}" for w in words],
            }
        )

    check_base_ecc(frame_records)

    total_words = sum(e["total_words"] for e in envelopes)
    return {
        "schema": "phenotype_manifest",
        "schema_version": SCHEMA_VERSION,
        "phenotype_id": phenotype_id,
        "target": dict(local_map["target"]),
        "base_bitstream": {
            "path": base_rel,
            "sha256": sha256_of(base_bitstream),
            "idcode": f"{parsed['idcode']:#010x}" if parsed["idcode"] is not None else None,
            "total_frames": len(frames),
        },
        "local_map": {
            "path": map_rel,
            "sha256": sha256_of(map_path),
            "map_id": local_map["map_id"],
            "address_count": local_map["universe"]["address_count"],
        },
        "pblock": pblock,
        "clock": {
            "fclk0_mhz": REQUIRED_FCLK0_MHZ,
            "rule": (
                "set and verified by decoding the PLLs, never by writing a remembered "
                "constant: the 4205's 0x00200a00 yields 80 MHz on a 4203"
            ),
        },
        "write_envelope": {
            "frame_words": bf.FRAME_WORDS,
            "target_far_count": len(target_fars),
            "flush_far_count": len(flush_fars),
            "envelopes": envelopes,
            "total_words": total_words,
            "total_bytes": total_words * 4,
            "rule": (
                "every candidate rewrites all target frames, not only the frames it "
                "changed, so a candidate depends on the pinned base alone and both arms "
                "pay an identical transfer cost"
            ),
        },
        "ownership": {
            "writable_addresses": sum(len(v) for v in whitelist.values()),
            "rule": (
                "within the target and flush frames, every bit except the whitelisted "
                "addresses is determined by this pinned base — including bits belonging "
                "to our own scorer or control logic"
            ),
            "flush_rule": (
                "flush frames are non-writable authority and must equal their pinned base "
                "verbatim; falling inside the FDRI range does not make a frame writable"
            ),
            "whitelist_by_far": {
                f"{far:#010x}": sorted(v, key=lambda e: (e["word"], e["bit"]))
                for far, v in sorted(whitelist.items())
            },
        },
        "frames": frame_records,
        "tool_versions": {
            "builder": TOOL_VERSION,
            "frame_parser": "bitstream_frames.py",
            "ecc": fe.TOOL_VERSION,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--map", type=Path, required=True)
    ap.add_argument("--base-bitstream", type=Path, required=True)
    ap.add_argument("--phenotype-id", required=True)
    ap.add_argument("--pblock", default=None)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    try:
        doc = build_manifest(
            args.map.resolve(),
            args.base_bitstream.resolve(),
            args.phenotype_id,
            args.pblock,
        )
    except EnvelopeError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    env = doc["write_envelope"]
    print(f"{args.out}: {env['target_far_count']} target + {env['flush_far_count']} flush frames")
    for e in env["envelopes"]:
        note = "" if e["flush_is_same_column"] else "  (flush is in the NEXT COLUMN)"
        print(
            f"  envelope {e['index']}: FAR {e['far_set']} + {len(e['target_fars'])} targets, "
            f"flush {e['flush_far']}, {e['total_words']} words{note}"
        )
    print(f"  total {env['total_words']} words = {env['total_bytes']} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())

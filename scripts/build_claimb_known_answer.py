#!/usr/bin/env python3
"""Build the deterministic Claim B known-answer artifact from frozen inputs.

This is the producer.  It selects nothing: LUT 0, its target, the carrier run and the
train/holdout split are all already frozen.  The independent consumer is
``gate_claimb_known_answer.py`` and deliberately does not import this module.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import board_carrier_exec as ex  # noqa: E402
import frame_ecc as fe  # noqa: E402
import run_log  # noqa: E402

TOOL_VERSION = "build_claimb_known_answer.py/1.0.0"
RUN = REPO / "gate_runs/claimb_round1_carrier_2026_08_13_erratum006"
REPORT = REPO / "gate_runs/claimb_round1_reachability_2026_08_10/reachability_report.json"
CONSTANTS = REPO / "vivado/carrier/generated/carrier_constants.json"
SPEC = REPO / "specs/reachability_spec_v1.json"
TILEGRID = REPO / "data/prjxray/zynq7/xc7z010/tilegrid.json"
OUT = REPO / "gate_runs/claimb_round1_known_answer_2026_08_14/known_answer.json"
LUT_KEY = "CLBLL_L.SLICEL_X0.ALUT"
FEATURE_RE = re.compile(r"^CLBLL_L\.SLICEL_X0\.ALUT\.INIT\[(\d+)\]$")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned_frames(manifest: dict) -> tuple[dict[int, list[int]], dict[int, str]]:
    frames = {int(rec["far"], 16): [int(word, 16) for word in rec["words"]]
              for rec in manifest["frames"]}
    roles = {int(rec["far"], 16): rec["role"] for rec in manifest["frames"]}
    return frames, roles


def mapped_init(local_map: dict) -> dict[int, tuple[int, int, int]]:
    """INIT index -> FAR/word/bit, derived from the map rather than a typed mask."""
    out: dict[int, tuple[int, int, int]] = {}
    for rec in local_map["index"]["by_lut"][LUT_KEY]:
        idx = int(rec["init_index"])
        far_s, word_s, bit_s = rec["address_key"].split("/")
        if idx in out:
            raise ValueError(f"INIT[{idx}] is mapped twice")
        out[idx] = (int(far_s, 16), int(word_s), int(bit_s))
    if len(out) != 49:
        raise ValueError(f"the frozen map exposes {len(out)} LUT0 bits, expected 49")
    return out


def derive_lut_key(loc: str, bel: str, tilegrid: dict) -> tuple[str, str, int]:
    holders = [name for name, tile in tilegrid.items() if loc in (tile.get("sites") or {})]
    if len(holders) != 1:
        raise ValueError(f"{loc} belongs to {len(holders)} tiles")
    tile_name = holders[0]
    tile = tilegrid[tile_name]
    sites = sorted(tile["sites"], key=lambda name: int(re.match(r"SLICE_X(\d+)Y", name)[1]))
    index = sites.index(loc)
    letter = re.match(r"(?:SLICE[LM]\.)?([A-D])6LUT$", bel)
    if not letter:
        raise ValueError(f"unrecognised LUT BEL {bel}")
    return f"{tile['type']}.{tile['sites'][loc]}_X{index}.{letter[1]}LUT", tile_name, index


def score(init_values: list[int], targets: list[int], order: list[int]) -> list[int]:
    return [sum(((init >> vector) & 1) == ((target >> vector) & 1)
                for vector in order)
            for init, target in zip(init_values, targets)]


def payload_record(payload: bytes, target_frames: dict[int, list[int]],
                   readback_frames: dict[int, list[int]]) -> dict:
    return {
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "target_frames_sha256": run_log.frames_hash(target_frames),
        "readback_frames_sha256": run_log.frames_hash(readback_frames),
        "base64": base64.b64encode(payload).decode("ascii"),
    }


def build(run_dir: Path = RUN) -> dict:
    manifest_path = run_dir / "phenotype_manifest.json"
    map_path = run_dir / "local_map.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    local_map = json.loads(map_path.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    constants = json.loads(CONSTANTS.read_text(encoding="utf-8"))
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    tilegrid = json.loads(TILEGRID.read_text(encoding="utf-8"))

    if report.get("status") != "complete":
        raise ValueError("the frozen reachability report is not complete")
    if report.get("spec_sha256") != digest(SPEC):
        raise ValueError("the report does not pin the frozen spec bytes")
    if constants["spec"]["sha256"] != digest(SPEC) or constants["report"]["sha256"] != digest(REPORT):
        raise ValueError("the scorer constants do not pin the frozen spec/report bytes")

    selected = report["per_lut"][0]
    if (selected["site"], selected["bel"]) != ("SLICE_X2Y25", "A6LUT"):
        raise ValueError("the first frozen report entry is no longer the selected LUT")
    target = int(selected["target_truth_table"].split("'h")[1], 16)
    lut_key, tile_name, site_index = derive_lut_key(selected["site"], selected["bel"], tilegrid)
    if lut_key != LUT_KEY:
        raise ValueError(f"tilegrid derives {lut_key}, expected {LUT_KEY}")
    mapping = mapped_init(local_map)
    mask = sum(1 << idx for idx in mapping)
    actual_init = target & mask

    base, roles = pinned_frames(manifest)
    targets = {far: list(words) for far, words in base.items() if roles[far] == "target"}
    candidate = {far: list(words) for far, words in targets.items()}
    changed = []
    touched: set[int] = set()
    for idx, (far, word, bit) in sorted(mapping.items()):
        wanted = (target >> idx) & 1
        before = (candidate[far][word] >> bit) & 1
        candidate[far][word] = ((candidate[far][word] & ~(1 << bit)) |
                                (wanted << bit))
        if before != wanted:
            changed.append({"far": f"0x{far:08X}", "word": word, "bit": bit,
                            "init_index": idx, "value": wanted})
            touched.add(far)
    for far in touched:
        candidate[far] = fe.update_ecc(candidate[far])

    candidate_payload = ex.build_sequence_bytes(manifest, candidate)
    restore_payload = ex.build_sequence_bytes(manifest, targets)
    candidate_readback = {
        far: list(candidate[far] if roles[far] == "target" else base[far])
        for far in base
    }

    order = [int(v) for v in constants["order"]]
    train_count = int(constants["train_count"])
    truth = [int(rec["target"]) for rec in constants["luts"]]
    candidate_inits = [actual_init] + [0] * 5
    base_inits = [0] * 6
    candidate_train = score(candidate_inits, truth, order[:train_count])
    candidate_holdout = score(candidate_inits, truth, order[train_count:])
    base_train = score(base_inits, truth, order[:train_count])
    base_holdout = score(base_inits, truth, order[train_count:])

    blocked = set(int(v) for v in selected["blocked_positions"])
    train_set = set(order[:train_count])
    holdout_set = set(order[train_count:])
    if (sorted(blocked & train_set), sorted(blocked & holdout_set)) != (
            [5, 25, 33, 49, 56], [23]):
        raise ValueError("the frozen split no longer gives the registered 5/1 blockage")

    touched_records = []
    for far in sorted(touched):
        words = candidate[far]
        touched_records.append({
            "far": f"0x{far:08X}",
            "words": [f"0x{word:08X}" for word in words],
            "stored_ecc": f"0x{fe.stored_ecc(words):04X}",
            "recomputed_ecc": f"0x{fe.calculate_ecc(words) & fe.ECC_MASK:04X}",
        })

    return {
        "schema": "claimb_known_answer",
        "schema_version": "1.0.0",
        "round_id": "claimb_round1_known_answer_2026_08_14",
        "sources": {
            "carrier_run": str(run_dir.relative_to(REPO)),
            "phenotype_manifest": {"path": str(manifest_path.relative_to(REPO)),
                                     "sha256": digest(manifest_path)},
            "local_map": {"path": str(map_path.relative_to(REPO)),
                          "sha256": digest(map_path)},
            "reachability_report": {"path": str(REPORT.relative_to(REPO)),
                                    "sha256": digest(REPORT)},
            "carrier_constants": {"path": str(CONSTANTS.relative_to(REPO)),
                                  "sha256": digest(CONSTANTS)},
            "reachability_spec": {"path": str(SPEC.relative_to(REPO)),
                                  "sha256": digest(SPEC)},
            "tilegrid": {"path": str(TILEGRID.relative_to(REPO)),
                         "sha256": digest(TILEGRID)},
        },
        "selection": {
            "report_index": 0, "site": selected["site"], "bel": selected["bel"],
            "map_lut_key": LUT_KEY,
            "map_lut_key_derivation": {"tile": tile_name, "site_index_by_x": site_index,
                                       "rule": "site -> tile type -> same-type site index by X -> LUT letter"},
            "target_init": f"0x{target:016X}",
            "mutable_mask": f"0x{mask:016X}",
            "actual_init": f"0x{actual_init:016X}",
            "mutable_positions": sorted(mapping),
            "blocked_positions": sorted(blocked),
        },
        "candidate": {
            "changed_content_bits": changed,
            "changed_content_bit_count": len(changed),
            "touched_frames": touched_records,
            "touched_far_count": len(touched),
            "payload": payload_record(candidate_payload, candidate, candidate_readback),
        },
        "restore": {
            "actual_init": "0x0000000000000000",
            "payload": payload_record(restore_payload, targets, base),
        },
        "scores": {
            "train_count": train_count,
            "holdout_count": len(order) - train_count,
            "candidate": {"train": candidate_train, "holdout": candidate_holdout},
            "base_restore": {"train": base_train, "holdout": base_holdout},
            "blocked_split": {"train": sorted(blocked & train_set),
                              "holdout": sorted(blocked & holdout_set)},
            "target_popcounts": [value.bit_count() for value in truth],
        },
        "tool_versions": {"producer": TOOL_VERSION, "frame_ecc": fe.TOOL_VERSION},
    }


def canonical_bytes(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    blob = canonical_bytes(build())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(blob)
    print(f"WROTE {args.out.relative_to(REPO)} sha256={hashlib.sha256(blob).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

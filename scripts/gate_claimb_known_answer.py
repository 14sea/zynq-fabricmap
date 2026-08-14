#!/usr/bin/env python3
"""Independently recompute and gate the frozen Claim B known-answer artifact.

The producer is intentionally not imported.  This consumer starts again from the
published manifest, local map, reachability report and scorer constants, then compares
every leaf of the artifact — including both serialized payloads and all twelve scores.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import board_carrier_exec as ex  # noqa: E402
import frame_ecc as fe  # noqa: E402
import run_log  # noqa: E402

TOOL_VERSION = "gate_claimb_known_answer.py/1.0.0"
ARTIFACT = REPO / "gate_runs/claimb_round1_known_answer_2026_08_14/known_answer.json"
ARTIFACT_REL = ARTIFACT.relative_to(REPO).as_posix()
PRODUCTION_ARTIFACT_SHA256 = "b115e6be3c44b1500aaf0281bd7f480afa61654a12b1083a778fb9d9cb2f5ef1"
RUN_REL = "gate_runs/claimb_round1_carrier_2026_08_13_erratum006"
MANIFEST_REL = f"{RUN_REL}/phenotype_manifest.json"
MAP_REL = f"{RUN_REL}/local_map.json"
REPORT_REL = "gate_runs/claimb_round1_reachability_2026_08_10/reachability_report.json"
CONSTANTS_REL = "vivado/carrier/generated/carrier_constants.json"
SPEC_REL = "specs/reachability_spec_v1.json"
TILEGRID_REL = "data/prjxray/zynq7/xc7z010/tilegrid.json"
LUT_KEY = "CLBLL_L.SLICEL_X0.ALUT"


class KnownAnswerRefusal(Exception):
    """The round artifact or the arm precondition is not authoritative."""


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _frames(manifest: dict) -> tuple[dict[int, list[int]], dict[int, str]]:
    return (
        {int(rec["far"], 16): [int(word, 16) for word in rec["words"]]
         for rec in manifest["frames"]},
        {int(rec["far"], 16): rec["role"] for rec in manifest["frames"]},
    )


def _mapping(local_map: dict) -> dict[int, tuple[int, int, int]]:
    out = {}
    for rec in local_map["index"]["by_lut"].get(LUT_KEY, []):
        idx = int(rec["init_index"])
        pieces = rec["address_key"].split("/")
        if len(pieces) != 3 or idx in out:
            raise KnownAnswerRefusal("the local map has a malformed or duplicate LUT0 address")
        out[idx] = (int(pieces[0], 16), int(pieces[1]), int(pieces[2]))
    if len(out) != 49:
        raise KnownAnswerRefusal(f"the local map derives {len(out)} mutable LUT0 positions")
    return out


def _lut_key(loc: str, bel: str, tilegrid: dict) -> tuple[str, str, int]:
    holders = [name for name, tile in tilegrid.items() if loc in (tile.get("sites") or {})]
    if len(holders) != 1:
        raise KnownAnswerRefusal(f"tilegrid gives {len(holders)} holders for {loc}")
    tile_name = holders[0]
    tile = tilegrid[tile_name]
    try:
        sites = sorted(tile["sites"],
                       key=lambda name: int(re.match(r"SLICE_X(\d+)Y", name)[1]))
        index = sites.index(loc)
    except (AttributeError, TypeError, ValueError) as exc:
        raise KnownAnswerRefusal(f"cannot derive the site index: {exc}") from exc
    match = re.match(r"(?:SLICE[LM]\.)?([A-D])6LUT$", bel)
    if not match:
        raise KnownAnswerRefusal(f"cannot derive a LUT letter from {bel}")
    key = f"{tile['type']}.{tile['sites'][loc]}_X{index}.{match[1]}LUT"
    return key, tile_name, index


def _score(inits: list[int], truth: list[int], vectors: list[int]) -> list[int]:
    answer = []
    for init, target in zip(inits, truth):
        count = 0
        for vector in vectors:
            count += int(((init >> vector) & 1) == ((target >> vector) & 1))
        answer.append(count)
    return answer


def _payload(blob: bytes, target_frames: dict[int, list[int]],
             readback_frames: dict[int, list[int]]) -> dict:
    return {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(),
            "target_frames_sha256": run_log.frames_hash(target_frames),
            "readback_frames_sha256": run_log.frames_hash(readback_frames),
            "base64": base64.b64encode(blob).decode("ascii")}


def recompute() -> dict:
    """The expected artifact, reconstructed without producer code or its output."""
    manifest = _load(MANIFEST_REL)
    local_map = _load(MAP_REL)
    report = _load(REPORT_REL)
    constants = _load(CONSTANTS_REL)
    spec = _load(SPEC_REL)
    tilegrid = _load(TILEGRID_REL)
    if report.get("status") != "complete":
        raise KnownAnswerRefusal("reachability report is not complete")
    if report.get("spec_sha256") != _digest(REPO / SPEC_REL):
        raise KnownAnswerRefusal("reachability report does not pin the frozen spec")
    if (constants["spec"]["sha256"] != _digest(REPO / SPEC_REL) or
            constants["report"]["sha256"] != _digest(REPO / REPORT_REL)):
        raise KnownAnswerRefusal("scorer constants do not pin the frozen inputs")
    selected = report["per_lut"][0]
    if selected.get("site") != "SLICE_X2Y25" or selected.get("bel") != "A6LUT":
        raise KnownAnswerRefusal("frozen report entry zero is not SLICE_X2Y25/A6LUT")

    target = int(selected["target_truth_table"].split("'h")[1], 16)
    lut_key, tile_name, site_index = _lut_key(selected["site"], selected["bel"], tilegrid)
    if lut_key != LUT_KEY:
        raise KnownAnswerRefusal(f"tilegrid derives {lut_key}, not {LUT_KEY}")
    mapping = _mapping(local_map)
    mask = 0
    for idx in mapping:
        mask |= 1 << idx
    actual = target & mask

    base, roles = _frames(manifest)
    restore = {far: list(words) for far, words in base.items() if roles[far] == "target"}
    candidate = {far: list(words) for far, words in restore.items()}
    changes = []
    touched = set()
    for idx in sorted(mapping):
        far, word, bit = mapping[idx]
        value = (target >> idx) & 1
        old = (candidate[far][word] >> bit) & 1
        candidate[far][word] &= ~(1 << bit)
        candidate[far][word] |= value << bit
        if old != value:
            changes.append({"far": f"0x{far:08X}", "word": word, "bit": bit,
                            "init_index": idx, "value": value})
            touched.add(far)
    for far in touched:
        candidate[far] = fe.update_ecc(candidate[far])

    candidate_blob = ex.build_sequence_bytes(manifest, candidate)
    restore_blob = ex.build_sequence_bytes(manifest, restore)
    candidate_readback = {
        far: list(candidate[far] if roles[far] == "target" else base[far])
        for far in base
    }
    order = list(map(int, constants["order"]))
    if sorted(order) != list(range(64)):
        raise KnownAnswerRefusal("carrier vector order is not a permutation of 0..63")
    cut = int(constants["train_count"])
    truth = [int(rec["target"]) for rec in constants["luts"]]
    blocked = set(map(int, selected["blocked_positions"]))
    train, holdout = order[:cut], order[cut:]

    frame_records = []
    for far in sorted(touched):
        words = candidate[far]
        frame_records.append({
            "far": f"0x{far:08X}",
            "words": [f"0x{word:08X}" for word in words],
            "stored_ecc": f"0x{fe.stored_ecc(words):04X}",
            "recomputed_ecc": f"0x{fe.calculate_ecc(words) & fe.ECC_MASK:04X}",
        })

    return {
        "schema": "claimb_known_answer", "schema_version": "1.0.0",
        "round_id": "claimb_round1_known_answer_2026_08_14",
        "sources": {
            "carrier_run": RUN_REL,
            "phenotype_manifest": {"path": MANIFEST_REL,
                                     "sha256": _digest(REPO / MANIFEST_REL)},
            "local_map": {"path": MAP_REL, "sha256": _digest(REPO / MAP_REL)},
            "reachability_report": {"path": REPORT_REL,
                                    "sha256": _digest(REPO / REPORT_REL)},
            "carrier_constants": {"path": CONSTANTS_REL,
                                  "sha256": _digest(REPO / CONSTANTS_REL)},
            "reachability_spec": {"path": SPEC_REL,
                                  "sha256": _digest(REPO / SPEC_REL)},
            "tilegrid": {"path": TILEGRID_REL,
                         "sha256": _digest(REPO / TILEGRID_REL)},
        },
        "selection": {
            "report_index": 0, "site": selected["site"], "bel": selected["bel"],
            "map_lut_key": LUT_KEY, "target_init": f"0x{target:016X}",
            "map_lut_key_derivation": {"tile": tile_name, "site_index_by_x": site_index,
                                       "rule": "site -> tile type -> same-type site index by X -> LUT letter"},
            "mutable_mask": f"0x{mask:016X}", "actual_init": f"0x{actual:016X}",
            "mutable_positions": sorted(mapping),
            "blocked_positions": sorted(blocked),
        },
        "candidate": {
            "changed_content_bits": changes, "changed_content_bit_count": len(changes),
            "touched_frames": frame_records, "touched_far_count": len(touched),
            "payload": _payload(candidate_blob, candidate, candidate_readback),
        },
        "restore": {"actual_init": "0x0000000000000000",
                    "payload": _payload(restore_blob, restore, base)},
        "scores": {
            "train_count": cut, "holdout_count": len(holdout),
            "candidate": {"train": _score([actual] + [0] * 5, truth, train),
                          "holdout": _score([actual] + [0] * 5, truth, holdout)},
            "base_restore": {"train": _score([0] * 6, truth, train),
                             "holdout": _score([0] * 6, truth, holdout)},
            "blocked_split": {"train": sorted(blocked & set(train)),
                              "holdout": sorted(blocked & set(holdout))},
            "target_popcounts": [value.bit_count() for value in truth],
        },
        "tool_versions": {"producer": "build_claimb_known_answer.py/1.0.0",
                          "frame_ecc": fe.TOOL_VERSION},
    }


def _diff(want, got, path="$", out=None) -> list[str]:
    out = [] if out is None else out
    if type(want) is not type(got):
        out.append(f"{path}: type {type(got).__name__}, expected {type(want).__name__}")
    elif isinstance(want, dict):
        for key in sorted(set(want) | set(got)):
            if key not in got:
                out.append(f"{path}.{key}: missing")
            elif key not in want:
                out.append(f"{path}.{key}: unexpected")
            else:
                _diff(want[key], got[key], f"{path}.{key}", out)
    elif isinstance(want, list):
        if len(want) != len(got):
            out.append(f"{path}: length {len(got)}, expected {len(want)}")
        for index, (a, b) in enumerate(zip(want, got)):
            _diff(a, b, f"{path}[{index}]", out)
    elif want != got:
        out.append(f"{path}: {got!r}, expected {want!r}")
    return out


def verify_document(doc: dict) -> list[str]:
    try:
        expected = recompute()
    except (KeyError, ValueError, TypeError, KnownAnswerRefusal) as exc:
        return [f"frozen inputs cannot be recomputed: {exc}"]
    return _diff(expected, doc)


class KnownAnswerAuthority:
    """Published, consumer-verified bytes.  Callers never supply its manifest or hashes."""

    __slots__ = ("_raw", "_doc")
    _CAPABILITY = object()

    def __init__(self, capability, raw: bytes) -> None:
        if capability is not self._CAPABILITY:
            raise KnownAnswerRefusal("KnownAnswerAuthority is constructed only by load()")
        if hashlib.sha256(raw).hexdigest() != PRODUCTION_ARTIFACT_SHA256:
            raise KnownAnswerRefusal("the known-answer artifact is not the reviewed production artifact")
        doc = json.loads(raw)
        problems = verify_document(doc)
        if problems:
            raise KnownAnswerRefusal("consumer refused the artifact: " + "; ".join(problems[:4]))
        self._raw, self._doc = bytes(raw), doc

    @classmethod
    def load(cls) -> "KnownAnswerAuthority":
        raw = ARTIFACT.read_bytes()
        # The arm authority must be history, not an edited working copy.
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", ARTIFACT_REL],
                                 cwd=REPO, capture_output=True).returncode == 0
        head = subprocess.run(["git", "show", f"HEAD:{ARTIFACT_REL}"], cwd=REPO,
                              capture_output=True)
        if not tracked or head.returncode or head.stdout != raw:
            raise KnownAnswerRefusal("the known-answer artifact is not the exact HEAD blob")
        dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], cwd=REPO)
        if dirty.returncode:
            raise KnownAnswerRefusal("tracked files differ from HEAD; the judge is not published")
        return cls(cls._CAPABILITY, raw)

    def payload(self, which: str) -> bytes:
        if which not in ("candidate", "restore"):
            raise KnownAnswerRefusal(f"unknown payload {which!r}")
        rec = self._doc[which]["payload"]
        blob = base64.b64decode(rec["base64"], validate=True)
        if hashlib.sha256(blob).hexdigest() != rec["sha256"]:
            raise KnownAnswerRefusal(f"{which} payload no longer matches its seal")
        return blob

    def frames_sha256(self, which: str) -> str:
        return self._doc[which]["payload"]["readback_frames_sha256"]

    def scores(self, which: str, mode: str) -> list[int]:
        key = "candidate" if which == "candidate" else "base_restore"
        return list(self._doc["scores"][key][mode])

    @property
    def document(self) -> dict:
        return json.loads(self._raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artifact", type=Path, default=ARTIFACT)
    args = parser.parse_args()
    try:
        doc = json.loads(args.artifact.read_text(encoding="utf-8"))
        problems = verify_document(doc)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    if problems:
        for problem in problems[:20]:
            print(f"  - {problem}")
        print(f"KNOWN-ANSWER REFUSED ({len(problems)} problem(s))")
        return 1
    print("KNOWN-ANSWER ACCEPTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

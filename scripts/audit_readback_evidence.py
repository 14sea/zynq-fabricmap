#!/usr/bin/env python3
"""W2: has the carrier's own read path ever returned a NON-BLANK frame, whole and exact,
at the FAR it asked for?

A non-zero word is not the question. Two committed captures are already non-zero and neither
is a success: the erratum-004 carrier's staging held the abort status word 101 times, and the
erratum-005 carrier's staging held bit-exact configuration data from the WRONG address. So the
criterion is deliberately narrow, and all three parts must hold at once:

    the expected frame is non-blank  AND  the returned words equal it exactly
    AND  the frame is the one whose FAR was requested.

Scope. This audits the **engine's** frame-data path only: the frames `carrier_stream` staged
and handed to the host, and the DRAM copies of that staging RAM. JTAG captures
(`probe_jtag_config_read.py`, the `far_*.json` of every sweep) are excluded by definition —
they are the independent path this question is about, not evidence from it.

Offline, read-only, and it attributes nothing it cannot compute.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import analyse_ddr_capture as add  # noqa: E402

TOOL_VERSION = "audit_readback_evidence.py/1.0.0"

FRAME_WORDS = 101
ERRATUM006 = "claimb_round1_carrier_2026_08_13_erratum006"
RUN_DIR = REPO / "gate_runs" / ERRATUM006
REPORT = REPO / "gate_runs/claimb_round1_reachability_2026_08_10/reachability_report.json"
EVIDENCE = REPO / "evidence"

# Staging copies have no carrier field of their own; each is bound to the record that built
# the state it was taken from, named here rather than guessed from the directory name.
# Every staging copy below was taken AFTER the candidate round faulted, so a correct
# readback of the requested FAR at that moment would have returned the CANDIDATE, not the
# base. `landing_verified` says whether that starting content was independently observed in
# that same instance: only the two 2026-08-20 runs carry a location acquisition, so for the
# 2026-08-14 capture the expectation is a reproduced prior rather than a measurement.
STAGING = {
    "evidence/calibration_noop_2026_08_13_erratum004/stage_dump.json":
        ("erratum-004 carrier", "dump/words", "calibration_noop_2026_08_13_erratum004", False),
    "evidence/calibration_noop_2026_08_13_erratum005/stage_dump.json":
        ("erratum-005 carrier", "dump/words", "calibration_noop_2026_08_13_erratum005", False),
    "evidence/known_answer_2026_08_14_erratum006/ddr_slot0.json":
        ("erratum-006 carrier", "words", "known_answer_2026_08_14_erratum006", False),
    "evidence/location_sweep_2026_08_20/fault/ddr_slot0_shutdown_read.json":
        ("erratum-006 carrier", "words", "location_sweep_2026_08_20", True),
    "evidence/location_reproduction_2026_08_20/fault/ddr_slot0_shutdown_read.json":
        ("erratum-006 carrier", "words", "location_reproduction_2026_08_20", True),
}
REQUESTED_FAR = 0x00400A20     # the frame every one of those staging copies was reading


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame_sha(words: list[int]) -> str:
    return hashlib.sha256(b"".join(w.to_bytes(4, "big") for w in words)).hexdigest()


def as_words(raw: list) -> list[int]:
    return [int(w, 16) if isinstance(w, str) else int(w) for w in raw]


def engine_records() -> list[Path]:
    """Every committed record holding frames the engine handed to the host."""
    out = []
    for path in sorted(EVIDENCE.rglob("*.json")):
        try:
            document = json.loads(path.read_text("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        steps = document.get("round", {}).get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            transaction = (step.get("result") or {}).get("transaction") or {}
            if isinstance(transaction.get("readback_frames"), dict):
                out.append(path)
                break
    return out


def classify(words: list[int], expected: list[int] | None) -> str:
    """The verdict names what was expected as well as what came back.

    "blank came back and blank was expected" is the degenerate case F2 is about, and it must
    not be able to read as a success; "non-blank was expected and blank came back" is the
    failing readback itself.
    """
    if expected is None:
        return "NONBLANK_NO_AUTHORITY" if any(words) else "BLANK_NO_AUTHORITY"
    if not any(expected):
        return ("BLANK_EXPECTED_BLANK_DEGENERATE" if words == expected
                else "BLANK_EXPECTED_MISMATCH")
    if words == expected:
        return "NONBLANK_EXACT_SAME_FAR"
    return "NONBLANK_EXPECTED_GOT_" + ("BLANK" if not any(words) else "SOMETHING_ELSE")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    manifest = json.loads((RUN_DIR / "phenotype_manifest.json").read_text("utf-8"))
    local_map = json.loads((RUN_DIR / "local_map.json").read_text("utf-8"))
    report = json.loads(REPORT.read_text("utf-8"))
    base = {int(r["far"], 16): [int(w, 16) for w in r["words"]] for r in manifest["frames"]}
    candidate, _, _ = add.derive_candidate(manifest, local_map, report)

    audited = []
    for path in engine_records():
        document = json.loads(path.read_text("utf-8"))
        for step in document["round"]["steps"]:
            result = step.get("result") or {}
            transaction = result.get("transaction") or {}
            frames = transaction.get("readback_frames")
            if not isinstance(frames, dict):
                continue
            authority = Path(result.get("authority_run_dir", "?")).name
            entries = []
            for far_key, raw in frames.items():
                words = as_words(raw)
                far = int(far_key)
                # The no-op writes the blank restore payload, so its expectation is the base.
                expected = base.get(far) if authority == ERRATUM006 else None
                entries.append({
                    "far": f"0x{far:08X}", "words": len(words),
                    "nonzero_words": sum(1 for w in words if w),
                    "sha256": frame_sha(words),
                    "verdict": classify(words, expected),
                })
            audited.append({
                "source": add.rel(path), "sha256": sha256_of(path),
                "step": step["step"], "state": step["state"],
                "authority_run_dir": authority,
                "payload": "restore (blank)" if step["step"] == "no_op" else step["step"],
                "frames": len(entries), "frame_detail": entries,
                "nonblank_frames": sum(1 for e in entries if e["nonzero_words"]),
            })

    staging = []
    for relative, (era, pointer, built_by, landing_verified) in STAGING.items():
        path = REPO / relative
        document = json.loads(path.read_text("utf-8"))
        node = document
        for part in pointer.split("/"):
            node = node[part]
        words = as_words(node)
        expected = candidate.get(REQUESTED_FAR) if era == "erratum-006 carrier" else None
        staging.append({
            "source": relative, "sha256": sha256_of(path), "era": era,
            "state_built_by": built_by, "words": len(words),
            "nonzero_words": sum(1 for w in words if w), "sha256_of_frame": frame_sha(words),
            "requested_far": f"0x{REQUESTED_FAR:08X}",
            "expected_at_requested_far": "candidate (a post-fault capture)" if expected
                                         else "no authority for this carrier",
            "landing_verified_in_this_instance": landing_verified,
            "equals_base_at_requested_far": words == base.get(REQUESTED_FAR),
            "equals_candidate_at_requested_far": words == candidate.get(REQUESTED_FAR),
            "verdict": classify(words, expected),
        })

    hits = ([e for record in audited for e in record["frame_detail"]
             if e["verdict"] == "NONBLANK_EXACT_SAME_FAR"]
            + [s for s in staging if s["verdict"] == "NONBLANK_EXACT_SAME_FAR"])
    total_frames = sum(record["frames"] for record in audited)
    nonblank_engine = sum(record["nonblank_frames"] for record in audited)

    record = {
        "tool": TOOL_VERSION,
        "what": "W2 of docs/claimb_read_side_divergence_design.md",
        "criterion": ("the expected frame is non-blank AND the returned words equal it "
                      "exactly AND it is the frame whose FAR was requested"),
        "excluded_by_scope": ("JTAG captures (probe_jtag_config_read.py, every sweep's "
                              "far_*.json): the independent path, not the engine's"),
        "engine_transactions": audited,
        "staging_copies": staging,
        "totals": {
            "engine_transactions": len(audited),
            "engine_frames": total_frames,
            "engine_nonblank_frames": nonblank_engine,
            "staging_copies": len(staging),
            "staging_nonblank_erratum006": sum(
                1 for s in staging
                if s["era"] == "erratum-006 carrier" and s["nonzero_words"]),
            "engine_frames_expected_blank": sum(
                1 for record in audited for e in record["frame_detail"]
                if e["verdict"] == "BLANK_EXPECTED_BLANK_DEGENERATE"),
        },
        "hits": hits,
        "verdict": ("NONBLANK_READBACK_FOUND" if hits
                    else "NO_NONBLANK_READBACK_HAS_EVER_BEEN_RETURNED"),
        "reading": (
            "Every frame the carrier's read path has ever handed back on the erratum-006 "
            "carrier is blank, and every blank one was expected to be blank. The only "
            "non-blank engine-side content in the repository is from two superseded "
            "carriers: the erratum-004 abort word, and the erratum-005 dump that was "
            "bit-exact against the device stream at an address other than the one "
            "requested. So F2 is general across the committed erratum-006 evidence: this "
            "frame-data path has never been demonstrated to deliver non-blank "
            "configuration data correctly."
            if not hits else
            "At least one non-blank frame came back whole and exact at the FAR requested. "
            "F2 is NOT general and the design has to be rewritten around this record."),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")

    print(f"{TOOL_VERSION}")
    for entry in audited:
        print(f"  engine  {entry['source']}")
        print(f"          authority={entry['authority_run_dir']} step={entry['step']} "
              f"frames={entry['frames']} non-blank={entry['nonblank_frames']}")
    for entry in staging:
        print(f"  staging {entry['source']}")
        print(f"          {entry['era']:20s} nonzero={entry['nonzero_words']:3d}/101 "
              f"{entry['verdict']}")
    print(f"  totals: {record['totals']}")
    print(f"  VERDICT {record['verdict']}")
    print(f"wrote {add.rel(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

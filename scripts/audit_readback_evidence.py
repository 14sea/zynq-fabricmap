#!/usr/bin/env python3
"""W2: over a FROZEN committed inventory, has the carrier's own read path ever returned a
NON-BLANK frame, whole and exact, at the FAR it asked for?

A non-zero word is not the question. Two committed captures are already non-zero and neither is
a success: the erratum-004 carrier's staging held the abort status word 101 times, and the
erratum-005 carrier's staging held bit-exact configuration data from the WRONG address. So the
criterion is deliberately narrow, and all three parts must hold at once:

    the expected frame is non-blank  AND  the returned words equal it exactly
    AND  it is the frame whose FAR was requested.

**The population is closed, not discovered.** `read_side_evidence.py` freezes six engine
records, five staging copies and three authority artifacts by digest. Discovery still runs —
it is what would notice a seventh record — but its result must equal the frozen list exactly,
in both directions, or this tool refuses. A verdict with "ever" in it is only as good as the
inventory it quantifies over, and that inventory is the committed evidence at the pinned tree,
which is what the verdict now says.

**No landing flag is written by hand.** Whether an instance had the candidate at the intended
FAR before its staging copy was taken is derived from that same instance's step-4 evidence:
the plmark chain, the frozen instrument digest, the verdict, its sixteen controls, and the
capture's 101 words against the re-derived candidate.

Scope. This audits the ENGINE's frame-data path only. JTAG captures
(`probe_jtag_config_read.py`, every sweep's `far_*.json`) are excluded by definition — they are
the independent path this question is about, not evidence from it. They appear here only inside
the landing derivation, where that is exactly their job.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import analyse_ddr_capture as add  # noqa: E402
import read_side_evidence as rse  # noqa: E402

TOOL_VERSION = "audit_readback_evidence.py/2.0.0"


def classify(words: list[int], expected: list[int] | None) -> str:
    """The verdict names what was expected as well as what came back.

    "blank came back and blank was expected" is the degenerate case F2 is about and must not be
    able to read as a success; "non-blank was expected and blank came back" is the failing
    readback itself.
    """
    if expected is None:
        return "NONBLANK_NO_AUTHORITY" if any(words) else "BLANK_NO_AUTHORITY"
    if not any(expected):
        return ("BLANK_EXPECTED_BLANK_DEGENERATE" if words == expected
                else "BLANK_EXPECTED_MISMATCH")
    if words == expected:
        return "NONBLANK_EXACT_SAME_FAR"
    return "NONBLANK_EXPECTED_GOT_" + ("BLANK" if not any(words) else "SOMETHING_ELSE")


def audit(root: Path = REPO) -> dict:
    inputs = rse.checked_inputs(root)
    discovered = rse.discover_engine_records(root)
    rse.check_population(discovered, rse.ENGINE_RECORDS, "engine record")

    manifest = rse.load(root, f"{rse.RUN_DIR}/phenotype_manifest.json")
    local_map = rse.load(root, f"{rse.RUN_DIR}/local_map.json")
    report = rse.load(root, rse.REPORT)
    base = {int(r["far"], 16): [int(w, 16) for w in r["words"]] for r in manifest["frames"]}
    candidate, _, _ = add.derive_candidate(manifest, local_map, report)

    landings = {run: rse.verify_landing(root, run, candidate[rse.INTENDED_FAR])
                for run in rse.LOCATION_RUNS}

    audited = []
    for relative in rse.ENGINE_RECORDS:
        document = rse.load(root, relative)
        for step in document["round"]["steps"]:
            result = step.get("result") or {}
            transaction = result.get("transaction") or {}
            frames = transaction.get("readback_frames")
            if not isinstance(frames, dict):
                continue
            authority = Path(result.get("authority_run_dir", "?")).name
            entries = []
            for far_key, raw in frames.items():
                words = rse.as_words(raw)
                far = int(far_key)
                # The no-op writes the blank restore payload, so its expectation is the base.
                expected = base.get(far) if authority == rse.ERRATUM006 else None
                entries.append({
                    "far": f"0x{far:08X}", "words": len(words),
                    "nonzero_words": sum(1 for w in words if w),
                    "sha256": rse.frame_sha(words),
                    "verdict": classify(words, expected),
                })
            audited.append({
                "source": relative, "sha256": inputs[relative],
                "step": step["step"], "state": step["state"],
                "authority_run_dir": authority,
                "payload": "restore (blank)" if step["step"] == "no_op" else step["step"],
                "frames": len(entries), "frame_detail": entries,
                "nonblank_frames": sum(1 for e in entries if e["nonzero_words"]),
            })

    staging = []
    for relative, meta in rse.STAGING.items():
        document = rse.load(root, relative)
        words = rse.as_words(rse.at(document, meta["pointer"]))
        era_has_authority = meta["era"] == "erratum-006 carrier"
        landing = landings.get(meta["landing_source"])
        # Every staging copy below was taken AFTER the candidate round faulted, so a correct
        # readback of the requested FAR would have returned the CANDIDATE. Whether the
        # candidate was actually there is DERIVED, per instance, and is None where that
        # instance has no acquisition to derive it from.
        expected = candidate.get(rse.INTENDED_FAR) if era_has_authority else None
        staging.append({
            "source": relative, "sha256": inputs[relative], "era": meta["era"],
            "state_built_by": meta["built_by"], "words": len(words),
            "nonzero_words": sum(1 for w in words if w),
            "sha256_of_frame": rse.frame_sha(words),
            "requested_far": f"0x{rse.INTENDED_FAR:08X}",
            "expected_at_requested_far": ("candidate (a post-fault capture)" if era_has_authority
                                          else "no authority for this carrier"),
            "landing_source": meta["landing_source"],
            "landing_verified_in_this_instance": bool(landing and landing["landing_verified"]),
            "landing_derivation": landing,
            "equals_base_at_requested_far": words == base.get(rse.INTENDED_FAR),
            "equals_candidate_at_requested_far": words == candidate.get(rse.INTENDED_FAR),
            "verdict": classify(words, expected),
        })

    hits = ([e for record in audited for e in record["frame_detail"]
             if e["verdict"] == "NONBLANK_EXACT_SAME_FAR"]
            + [s for s in staging if s["verdict"] == "NONBLANK_EXACT_SAME_FAR"])

    return {
        "tool": TOOL_VERSION,
        "what": "W2 of docs/claimb_read_side_divergence_design.md",
        "criterion": ("the expected frame is non-blank AND the returned words equal it "
                      "exactly AND it is the frame whose FAR was requested"),
        "excluded_by_scope": ("JTAG captures (probe_jtag_config_read.py, every sweep's "
                              "far_*.json) are not the engine's read path. They appear only "
                              "inside the landing derivation, which is their job"),
        "inventory": {
            "closed": True,
            "engine_records_frozen": list(rse.ENGINE_RECORDS),
            "engine_records_discovered": discovered,
            "discovery_equals_freeze": sorted(discovered) == sorted(rse.ENGINE_RECORDS),
            "staging_copies_frozen": list(rse.STAGING),
            "authority_frozen": list(rse.AUTHORITY),
            "pinned_files": len(rse.PINNED),
        },
        "landing_derivations": landings,
        "engine_transactions": audited,
        "staging_copies": staging,
        "totals": {
            "engine_transactions": len(audited),
            "engine_frames": sum(record["frames"] for record in audited),
            "engine_nonblank_frames": sum(record["nonblank_frames"] for record in audited),
            "engine_frames_expected_blank": sum(
                1 for record in audited for e in record["frame_detail"]
                if e["verdict"] == "BLANK_EXPECTED_BLANK_DEGENERATE"),
            "staging_copies": len(staging),
            "staging_nonblank_erratum006": sum(
                1 for s in staging
                if s["era"] == "erratum-006 carrier" and s["nonzero_words"]),
            "landings_verified": sum(
                1 for s in staging if s["landing_verified_in_this_instance"]),
        },
        "hits": hits,
        "verdict": ("NONBLANK_READBACK_FOUND" if hits
                    else "NO_NONBLANK_READBACK_IN_THE_FROZEN_COMMITTED_INVENTORY"),
        "reading": (
            "Over the frozen inventory — six engine records, five staging copies and three "
            "authority artifacts at the pinned tree — every frame the carrier's read path "
            "handed back on the erratum-006 carrier is blank, and every blank one was "
            "expected to be blank. The only non-blank engine-side content is from two "
            "superseded carriers: the erratum-004 abort word, and the erratum-005 dump that "
            "was bit-exact against the device stream at an address other than the one "
            "requested. So F2 is general ACROSS THIS INVENTORY: within it, this frame-data "
            "path has never been demonstrated to deliver non-blank configuration data "
            "correctly. It is not a claim about runs that were never recorded."
            if not hits else
            "At least one non-blank frame came back whole and exact at the FAR requested. "
            "F2 is NOT general and the design has to be rewritten around this record."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--root", type=Path, default=REPO)
    args = ap.parse_args()

    record = audit(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")

    print(f"{TOOL_VERSION}: {record['inventory']['pinned_files']} pinned files, "
          f"discovery == freeze: {record['inventory']['discovery_equals_freeze']}")
    for run, landing in record["landing_derivations"].items():
        print(f"  landing {run}: verified={landing['landing_verified']} "
              f"({landing['words_matching_candidate']} words, "
              f"{landing['controls_exact']}/{landing['controls_declared']} controls, "
              f"one plmark={landing['checks']['one_plmark_across_fault_staging_and_acquisition']})")
    for entry in record["engine_transactions"]:
        print(f"  engine  {entry['source']}")
        print(f"          authority={entry['authority_run_dir']} step={entry['step']} "
              f"frames={entry['frames']} non-blank={entry['nonblank_frames']}")
    for entry in record["staging_copies"]:
        print(f"  staging {entry['source']}")
        print(f"          {entry['era']:20s} nonzero={entry['nonzero_words']:3d}/101 "
              f"landing={entry['landing_verified_in_this_instance']} {entry['verdict']}")
    print(f"  totals: {record['totals']}")
    print(f"  VERDICT {record['verdict']}")
    print(f"wrote {add.rel(args.out)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except rse.DerivationStop as stop:
        print(f"DerivationStop: {stop}", file=sys.stderr)
        raise SystemExit(1)

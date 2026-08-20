#!/usr/bin/env python3
"""The frozen inventory the read-side analyses run against, and the checks that enforce it.

`analyse_read_side_facts.py` (W1) and `audit_readback_evidence.py` (W2) both answer questions
whose whole value is that the population is closed. A dynamically discovered population can be
right today and quietly different tomorrow, and a hand-written boolean is not evidence at all.
So everything either tool depends on lives here, pinned by digest, and the tools refuse rather
than report when the tree does not match.

Three enforcement rules, all fail-closed:

1. **Every pinned artifact must be present and hash to its pinned value.** A mismatch is a
   refusal, not a warning: a fact re-derived from a drifted input is a new measurement wearing
   the old name.
2. **The pinned population must be closed in both directions.** Discovery is still performed —
   it is what would catch a seventh record appearing — but its result must equal the frozen
   list exactly. An extra record and a missing record are both refusals.
3. **Every repository module the tools actually loaded must be pinned.** The three files of
   this deliverable cannot pin themselves, so they are the declared exemption, and the check
   names any other unpinned module rather than passing over it.

Nothing here reads a board, a network, or anything outside the repository.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

FRAME_WORDS = 101
INTENDED_FAR = 0x00400A20
INSTRUMENT_DIGEST = "a20e56aae879812d9ed2960ec55ac8b1b3f57710411cf40da0cc32b1855aa95d"
LANDED = "WRITE_LANDED_AT_THE_INTENDED_FAR"
POSITIVE_CONTROLS = 16

ERRATUM006 = "claimb_round1_carrier_2026_08_13_erratum006"
RUN_DIR = f"gate_runs/{ERRATUM006}"
REPORT = "gate_runs/claimb_round1_reachability_2026_08_10/reachability_report.json"
KNOWN_ANSWER = "gate_runs/claimb_round1_known_answer_2026_08_14/known_answer.json"
DRIVER = "scripts/board_claimb_known_answer.py"

# The two 2026-08-20 instances, each of which carries its own step-4 location acquisition.
LOCATION_RUNS = {
    "run1": "evidence/location_sweep_2026_08_20",
    "run2": "evidence/location_reproduction_2026_08_20",
}

# THE CLOSED POPULATION. Discovery must reproduce exactly this list.
ENGINE_RECORDS = (
    "evidence/known_answer_2026_08_14_erratum006/record.json",
    "evidence/location_reproduction_2026_08_20/fault/record.json",
    "evidence/location_sweep_2026_08_20/fault/record.json",
    "evidence/phase2_2026_08_15/known_answer_record.json",
    "evidence/postfault_r4_replication_2026_08_16/fault_capture/record.json",
    "evidence/postfault_r4_step2_capture_2026_08_16/record.json",
)

# Every staging copy, with the era whose authority applies and the state it was taken from.
# `landing_source` is the run whose step-4 acquisition can DERIVE whether the candidate was in
# place — None where no such acquisition exists in that instance, which is a fact about the
# instance and not a reason to assume the answer.
STAGING = {
    "evidence/calibration_noop_2026_08_13_erratum004/stage_dump.json":
        {"era": "erratum-004 carrier", "pointer": "dump/words",
         "built_by": "calibration_noop_2026_08_13_erratum004", "landing_source": None},
    "evidence/calibration_noop_2026_08_13_erratum005/stage_dump.json":
        {"era": "erratum-005 carrier", "pointer": "dump/words",
         "built_by": "calibration_noop_2026_08_13_erratum005", "landing_source": None},
    "evidence/known_answer_2026_08_14_erratum006/ddr_slot0.json":
        {"era": "erratum-006 carrier", "pointer": "words",
         "built_by": "known_answer_2026_08_14_erratum006", "landing_source": None},
    "evidence/location_sweep_2026_08_20/fault/ddr_slot0_shutdown_read.json":
        {"era": "erratum-006 carrier", "pointer": "words",
         "built_by": "location_sweep_2026_08_20", "landing_source": "run1"},
    "evidence/location_reproduction_2026_08_20/fault/ddr_slot0_shutdown_read.json":
        {"era": "erratum-006 carrier", "pointer": "words",
         "built_by": "location_reproduction_2026_08_20", "landing_source": "run2"},
}

AUTHORITY = (
    f"{RUN_DIR}/phenotype_manifest.json",
    f"{RUN_DIR}/local_map.json",
    f"{RUN_DIR}/carrier.bit",
)

# The three files of this deliverable. They cannot pin themselves; the commit anchors them.
SELF = (
    "scripts/read_side_evidence.py",
    "scripts/analyse_read_side_facts.py",
    "scripts/audit_readback_evidence.py",
)

PINNED = {
    f"{RUN_DIR}/phenotype_manifest.json":
        "e45f466d082ccd6f227e6f9be4ce75a4e98c4caa708808c09a77ed32331c10ef",
    f"{RUN_DIR}/local_map.json":
        "56f2b9e81e180eee2540286e4fde797e0d4820a49d10624c10844c38e99d87cb",
    f"{RUN_DIR}/carrier.bit":
        "8c3369e8e4755da5aceeb7844690d5e132b2e65647004c0a46c0e868e34f0b8a",
    REPORT:
        "f06bf9074bd0a017663ce9895760f817484590ab8a11afe27e438a75983b4930",
    KNOWN_ANSWER:
        "b115e6be3c44b1500aaf0281bd7f480afa61654a12b1083a778fb9d9cb2f5ef1",
    "data/prjxray/zynq7/xc7z010/tilegrid.json":
        "db16874f2827fc05248ad4a7ef5769deaa8e70158a60c8dd40194c48713479ee",
    "data/prjxray/zynq7/xc7z010clg400-1/part.yaml":
        "43a136f26603c51bd97e9489d223bbc80f278fcc234225ed9fde404402f22683",
    "scripts/analyse_ddr_capture.py":
        "473888add4cef7b9a05fe87124be5bb9910cb02e2bf429e5cf42279c222ffd85",
    "scripts/bitstream_frames.py":
        "a55246e68e082cbb7d15833e6da134388059ffdb0497c29634a9b740eb9091b3",
    "scripts/frame_ecc.py":
        "e595c8e0467fd46de90d6f526792cedf09a4eafa1599b2c2c04a3bbcbb78a646",
    "scripts/board_uboot_axi.py":
        "574f5d01c14ccfeb41d3298f8dbcd435e004285ec9d228db840e41d58f4e7da2",
    "scripts/board_carrier_guard.py":
        "52d64feef30df8843593e84a9756f4e47cf49457606243e580189171d5440654",
    "scripts/board_serial.py":
        "ce38c9bc69c67d90cc92b16d5f782fc1eafcc8ed6a16d2d2333214624bbbb111",
    DRIVER:
        "ff3b88aabd6c7ec2f9b22da7cdb3855b72cf5a5a07a0534d3e032a023df9c357",
    "evidence/known_answer_2026_08_14_erratum006/record.json":
        "e944b85d572cb3a3cec7efe2326a4bd0f1d1b5c5df5c5ecf18ea4b9b73fe63c9",
    "evidence/known_answer_2026_08_14_erratum006/ddr_slot0.json":
        "53a261ab43f65f357efeeb98019601804372a528e592c02083255eb998bdefb5",
    "evidence/calibration_noop_2026_08_13_erratum004/stage_dump.json":
        "8cfb37e8a4346fcbb25bbcb6f037998471d5abb09895c6c76d9de487aae836e0",
    "evidence/calibration_noop_2026_08_13_erratum005/stage_dump.json":
        "1f0fc925621fbea5c8089b8189282e4f1a90e21eed34af8c80a77d57dab6ce70",
    "evidence/phase2_2026_08_15/known_answer_record.json":
        "2b7f72e4110ed8a07586e5f308dc4982e07aefba11518f52b710d258f7cab23c",
    "evidence/postfault_r4_step2_capture_2026_08_16/record.json":
        "82036ac02c0278303539e97c115350ad030145fa39ce1be115da5619c02b74d1",
    "evidence/postfault_r4_replication_2026_08_16/fault_capture/record.json":
        "50385fb850545b1e03d135654914518e81ced0cafc4406e26bd0724dd7155efa",
    "evidence/location_sweep_2026_08_20/fault/record.json":
        "db87cd770d3174d128174edb005ab4c9f8462a1671501774d2824101efe2190a",
    "evidence/location_sweep_2026_08_20/fault/ddr_slot0_shutdown_read.json":
        "413725bc551b1a2215405ac4b55a76a1fea73e0e8133df043ca0fac36caabc34",
    "evidence/location_sweep_2026_08_20/step4_sweep/index.json":
        "4747cc11f22893d383c9095c2709f505b7fa8378fa06f8ccff394a5a5ba3a6f2",
    "evidence/location_sweep_2026_08_20/step4_sweep/verdict.json":
        "f921356305cc575399e0de5ee16abe39344c2d9c8684ad51e1a4f674c239eab9",
    "evidence/location_sweep_2026_08_20/step4_sweep/far_00400a20.json":
        "404fa8c7a0ebbe5b7d15e1ad2f44ed0176bff8f20a22545c896911d7cf9dd580",
    "evidence/location_reproduction_2026_08_20/fault/record.json":
        "86bdf7f0f45997c8ff94cb56e25e2182e3564e18f5e8504bc4fe00419a2b8e1b",
    "evidence/location_reproduction_2026_08_20/fault/ddr_slot0_shutdown_read.json":
        "3221fa684a452fd7e71f70873c0085a6ea2ea8c2138525c91a7458df9e58e4e0",
    "evidence/location_reproduction_2026_08_20/step4_sweep/index.json":
        "5605cf1a89b1780e456380af260362f0eb40665e4adc10ee5d84453bfa3c45cf",
    "evidence/location_reproduction_2026_08_20/step4_sweep/verdict.json":
        "f921356305cc575399e0de5ee16abe39344c2d9c8684ad51e1a4f674c239eab9",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_00400a20.json":
        "342a704e365e943b5e8bd4e75d2cc1373e4bf22451fa1407b5baa90ac00e3cf4",
}


class DerivationStop(Exception):
    """An input, a population or a derived flag is not what the freeze says it is."""


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame_sha(words: list[int]) -> str:
    return hashlib.sha256(b"".join(w.to_bytes(4, "big") for w in words)).hexdigest()


def as_words(raw: list) -> list[int]:
    return [int(w, 16) if isinstance(w, str) else int(w) for w in raw]


def load(root: Path, relative: str) -> dict:
    return json.loads((root / relative).read_text("utf-8"))


def at(document: dict, pointer: str):
    node = document
    for part in pointer.split("/"):
        node = node[part]
    return node


def loaded_repo_modules(root: Path) -> set[str]:
    """Every module under `scripts/` that is actually loaded in this interpreter."""
    found = set()
    for module in list(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if not filename:
            continue
        path = Path(filename).resolve()
        if path.is_relative_to(root / "scripts"):
            found.add(str(path.relative_to(root)))
    return found


def checked_inputs(root: Path = REPO) -> dict:
    """Rule 1 and rule 3. Returns the verified digest map."""
    seen = {}
    for relative, expected in sorted(PINNED.items()):
        path = root / relative
        if not path.exists():
            raise DerivationStop(f"{relative} is missing from the pinned inventory")
        actual = sha256_of(path)
        if actual != expected:
            raise DerivationStop(
                f"{relative}: sha256 {actual} != pinned {expected}. The freeze does not "
                f"describe this tree, so nothing derived from it is a re-derivation.")
        seen[relative] = actual
    unpinned = sorted(loaded_repo_modules(root) - set(PINNED) - set(SELF))
    if unpinned:
        raise DerivationStop(
            f"these loaded modules are neither pinned nor part of this deliverable: "
            f"{unpinned}. Add them to PINNED with their digests, or stop importing them.")
    return seen


def check_population(discovered: list[str], frozen: tuple[str, ...], what: str) -> None:
    """Rule 2, in both directions."""
    extra = sorted(set(discovered) - set(frozen))
    missing = sorted(set(frozen) - set(discovered))
    if extra or missing:
        raise DerivationStop(
            f"the {what} population is not the frozen one: {len(discovered)} discovered vs "
            f"{len(frozen)} frozen; unexpected {extra}; absent {missing}. A closed-population "
            f"verdict cannot be issued over a population that moved.")


def discover_engine_records(root: Path) -> list[str]:
    """Every committed record holding frames the engine handed to the host."""
    out = []
    for path in sorted((root / "evidence").rglob("*.json")):
        try:
            document = json.loads(path.read_text("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(document, dict):
            continue
        steps = document.get("round", {}).get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            transaction = (step.get("result") or {}).get("transaction") or {}
            if isinstance(transaction.get("readback_frames"), dict):
                out.append(str(path.relative_to(root)))
                break
    return out


def candidate_frame_from_capture(root: Path, run_dir: str) -> tuple[list[int], dict]:
    """The 101 words the step-4 JTAG capture read at the intended FAR, with its provenance.

    A capture is 202 words: `pad_frame` then `frame`. The frame is the SECOND block, and
    reading the first one is a mistake this project has already made once, so the length and
    the recomputed digest are both checked here rather than trusted.
    """
    far_key = f"0x{INTENDED_FAR:08x}"
    name = f"far_{INTENDED_FAR:08x}.json"
    relative = f"{run_dir}/step4_sweep/{name}"
    capture = load(root, relative)
    index = load(root, f"{run_dir}/step4_sweep/index.json")

    entry = index["entries"].get(far_key)
    if entry is None:
        raise DerivationStop(f"{relative}: the index has no entry for {far_key}")
    actual = sha256_of(root / relative)
    if entry["capture_sha256"] != actual:
        raise DerivationStop(
            f"{relative}: the index records capture_sha256 {entry['capture_sha256']}, the "
            f"file hashes to {actual}")

    node = capture["frames"][far_key]
    if len(node["all_words"]) != 2 * FRAME_WORDS or len(node["frame"]) != FRAME_WORDS:
        raise DerivationStop(f"{relative}: not a 202-word capture with a 101-word frame")
    if node["pad_frame"] != node["all_words"][:FRAME_WORDS]:
        raise DerivationStop(f"{relative}: pad_frame is not the first block")
    if node["frame"] != node["all_words"][FRAME_WORDS:]:
        raise DerivationStop(f"{relative}: frame is not the second block")

    words = as_words(node["frame"])
    digest = frame_sha(words)
    if digest != node["frame_sha256"] or digest != entry["frame_sha256"]:
        raise DerivationStop(
            f"{relative}: the frame hashes to {digest}, the capture says "
            f"{node['frame_sha256']} and the index says {entry['frame_sha256']}")
    return words, {"capture": relative, "capture_sha256": actual, "frame_sha256": digest}


def verify_landing(root: Path, run: str, candidate: list[int]) -> dict:
    """Derive — never declare — whether this instance had the candidate at the intended FAR.

    Every part is read out of that instance's own evidence: the plmark chain that binds the
    fault, the staging copy and the acquisition to one boot; the frozen instrument digest; the
    verdict and its sixteen controls; and the capture's 101 words against the candidate.
    """
    run_dir = LOCATION_RUNS[run]
    fault = load(root, f"{run_dir}/fault/record.json")
    staging = load(root, f"{run_dir}/fault/ddr_slot0_shutdown_read.json")
    index = load(root, f"{run_dir}/step4_sweep/index.json")
    verdict = load(root, f"{run_dir}/step4_sweep/verdict.json")

    marks = {
        "fault_record": fault["same_boot"]["expected_plmark"],
        "staging_capture": staging.get("plmark"),
        "index_at_start": index["plmark_at_start"],
        "index_at_end": index["plmark_at_end"],
    }
    controls = verdict.get("positive_controls", [])
    exact = [c for c in controls if c.get("exact_same_far_base_match")
             and c.get("expected_sha256") == c.get("observed_sha256")]
    words, provenance = candidate_frame_from_capture(root, run_dir)
    matching = sum(1 for a, b in zip(words, candidate) if a == b)

    checks = {
        "one_plmark_across_fault_staging_and_acquisition": len(set(marks.values())) == 1,
        "instrument_digest_is_the_frozen_one":
            index["instrument_digest"] == INSTRUMENT_DIGEST,
        "verdict_is_the_landed_one": verdict.get("verdict") == LANDED,
        "verdict_names_the_intended_far":
            str(verdict.get("intended_far", "")).lower() == f"0x{INTENDED_FAR:08x}",
        "sixteen_controls_declared": len(index["positive_control_fars"]) == POSITIVE_CONTROLS,
        "sixteen_controls_exact": len(exact) == POSITIVE_CONTROLS == len(controls),
        "capture_equals_candidate_word_for_word": words == candidate,
    }
    return {
        "run": run, "run_dir": run_dir, "plmarks": marks,
        "controls_exact": len(exact), "controls_declared": len(controls),
        "words_matching_candidate": f"{matching}/{FRAME_WORDS}",
        "provenance": provenance, "checks": checks,
        "landing_verified": all(checks.values()),
    }

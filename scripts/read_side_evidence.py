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
import re
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
    "evidence/read_side_divergence_2026_08_20/fault/record.json",
)

# Every staging copy, with what a CORRECT readback owed at the requested FAR **in that
# instance**. 1.0.1 asserted that all of them were post-candidate-fault; that generalisation
# became false with the 2026-08-20 read-side run, whose copy was taken after a no-op verified
# fifteen blank frames, so a correct read owed BLANK there. The expectation is per entry:
#
#   "candidate"  the copy was taken after the candidate round faulted
#   "base"       the copy was taken after a blank (restore) payload was written and verified
#   "none"       a superseded carrier, for which this repository holds no comparable authority
#
# `landing_source` names the run whose step-4 acquisition can DERIVE whether the candidate was
# in place. It is None where no such acquisition exists in that instance — a fact about the
# instance, not permission to assume the answer.
STAGING = {
    "evidence/calibration_noop_2026_08_13_erratum004/stage_dump.json":
        {"era": "erratum-004 carrier", "pointer": "dump/words",
         "built_by": "calibration_noop_2026_08_13_erratum004",
         "expected": "none", "landing_source": None},
    # The same window read a second time with the reply kept whole; byte-identical to the
    # first. It is a staging copy, and it was MISSING from the 1.0.1 inventory — which is
    # exactly what the two-way closure guard now makes impossible to repeat.
    "evidence/calibration_noop_2026_08_13_erratum004/stage_dump_2.json":
        {"era": "erratum-004 carrier", "pointer": "dump/words",
         "built_by": "calibration_noop_2026_08_13_erratum004",
         "expected": "none", "landing_source": None},
    "evidence/calibration_noop_2026_08_13_erratum005/stage_dump.json":
        {"era": "erratum-005 carrier", "pointer": "dump/words",
         "built_by": "calibration_noop_2026_08_13_erratum005",
         "expected": "none", "landing_source": None},
    "evidence/known_answer_2026_08_14_erratum006/ddr_slot0.json":
        {"era": "erratum-006 carrier", "pointer": "words",
         "built_by": "known_answer_2026_08_14_erratum006",
         "expected": "candidate", "landing_source": None},
    "evidence/location_sweep_2026_08_20/fault/ddr_slot0_shutdown_read.json":
        {"era": "erratum-006 carrier", "pointer": "words",
         "built_by": "location_sweep_2026_08_20",
         "expected": "candidate", "landing_source": "run1"},
    "evidence/location_reproduction_2026_08_20/fault/ddr_slot0_shutdown_read.json":
        {"era": "erratum-006 carrier", "pointer": "words",
         "built_by": "location_reproduction_2026_08_20",
         "expected": "candidate", "landing_source": "run2"},
    # NOT a candidate-fault staging copy. Taken after the diagnostic no-op verified fifteen
    # blank frames, so a correct read owed the BASE at the requested FAR. Classifying it with
    # the other three would read as a fourth failing readback, which it is not.
    "evidence/read_side_divergence_2026_08_20/ddr_slot0.json":
        {"era": "erratum-006 carrier", "pointer": "words",
         "built_by": "read_side_divergence_2026_08_20 (after the no-op verified 15/15)",
         "expected": "base", "landing_source": None},
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


def frame_from_capture(root: Path, run_dir: str, far: int) -> tuple[list[int], dict]:
    """The 101 words one step-4 JTAG capture read at one FAR, with its provenance.

    A capture is 202 words: `pad_frame` then `frame`. The frame is the SECOND block, and
    reading the first one is a mistake this project has already made once, so the split, the
    length and the recomputed digest are all checked here rather than trusted.
    """
    far_key = f"0x{far:08x}"
    name = f"far_{far:08x}.json"
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


def discover_staging_copies(root: Path) -> list[str]:
    """Every committed document holding a 101-word staging window.

    Deliberately shape-based rather than name-based: `stage_dump.json`, `stage_dump_2.json`
    and `ddr_slot0*.json` are three naming conventions for the same artifact, and a fourth
    would otherwise slip past — as `stage_dump_2.json` did. JTAG captures do not match; they
    carry their words under `frames[far]`, not at the top level or under `dump`.
    """
    out = []
    for path in sorted((root / "evidence").rglob("*.json")):
        try:
            document = json.loads(path.read_text("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(document, dict):
            continue
        for pointer in ("words", "dump/words"):
            try:
                node = at(document, pointer)
            except (KeyError, TypeError):
                continue
            if isinstance(node, list) and len(node) == FRAME_WORDS:
                out.append(str(path.relative_to(root)))
                break
    return out


def candidate_frame_from_capture(root: Path, run_dir: str) -> tuple[list[int], dict]:
    """The intended FAR's frame — the one the whole location question is about."""
    return frame_from_capture(root, run_dir, INTENDED_FAR)


def device_frames(root: Path) -> dict:
    """The carrier bitstream's frames, keyed by FAR. Cheap: ~0.06 s for all 5,144."""
    import bitstream_frames as bf
    return bf.parse_frames(root / RUN_DIR / "carrier.bit")["frames"]


def check_controls(root: Path, run_dir: str, controls: list[dict],
                   declared: list[str], device: dict) -> dict:
    """Re-derive every positive control from the carrier bitstream, not from the sweep's word.

    `expected_sha256 == observed_sha256` in a verdict is the acquisition tool agreeing with
    itself. What makes a control a control is that the frame it read is the frame the frozen
    bitstream holds at that FAR — so each capture is reopened, its digest chain rechecked, and
    its 101 words compared against `carrier.bit`.
    """
    detail, exact_against_bitstream, unreadable = [], 0, []
    stated = {str(c.get("far", "")).lower(): c for c in controls}
    for far_key in declared:
        far = int(far_key, 16)
        try:
            words, provenance = frame_from_capture(root, run_dir, far)
        except (DerivationStop, FileNotFoundError, KeyError) as why:
            unreadable.append({"far": far_key, "why": str(why)})
            continue
        base = device.get(far)
        base_sha = frame_sha(base) if base is not None else None
        control = stated.get(far_key, {})
        agrees = (base is not None and words == base
                  and control.get("expected_sha256") == base_sha
                  and control.get("observed_sha256") == base_sha)
        exact_against_bitstream += 1 if agrees else 0
        detail.append({"far": far_key, "capture": provenance["capture"],
                       "frame_sha256": provenance["frame_sha256"],
                       "bitstream_sha256": base_sha,
                       "equals_the_bitstream": agrees})
    return {
        "declared": len(declared),
        "exact_against_the_bitstream": exact_against_bitstream,
        "unreadable": unreadable,
        "all_sixteen_re_derived":
            not unreadable and exact_against_bitstream == POSITIVE_CONTROLS == len(declared),
        "detail": detail,
    }


def verify_landing(root: Path, run: str, candidate: list[int],
                   device: dict | None = None) -> dict:
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
    declared_control_fars = [str(far).lower() for far in index["positive_control_fars"]]
    observed_control_fars = [str(control.get("far", "")).lower() for control in controls]
    exact = [c for c in controls if c.get("exact_same_far_base_match")
             and c.get("expected_sha256") == c.get("observed_sha256")]
    words, provenance = candidate_frame_from_capture(root, run_dir)
    matching = sum(1 for a, b in zip(words, candidate) if a == b)
    controls_vs_bitstream = check_controls(
        root, run_dir, controls, declared_control_fars,
        device if device is not None else device_frames(root))
    plmarks_are_well_formed = all(
        isinstance(mark, str) and re.fullmatch(r"[0-9a-f]{16}", mark)
        for mark in marks.values())

    checks = {
        "four_plmarks_present_and_well_formed": plmarks_are_well_formed,
        "one_plmark_across_fault_staging_and_acquisition":
            plmarks_are_well_formed and len(set(marks.values())) == 1,
        "instrument_digest_is_the_frozen_one":
            index["instrument_digest"] == INSTRUMENT_DIGEST,
        "verdict_is_the_landed_one": verdict.get("verdict") == LANDED,
        "verdict_names_the_intended_far":
            str(verdict.get("intended_far", "")).lower() == f"0x{INTENDED_FAR:08x}",
        "sixteen_controls_declared": len(declared_control_fars) == POSITIVE_CONTROLS,
        "declared_control_fars_are_unique":
            len(set(declared_control_fars)) == POSITIVE_CONTROLS,
        "verdict_control_fars_match_declared_sequence":
            observed_control_fars == declared_control_fars,
        "sixteen_controls_exact": len(exact) == POSITIVE_CONTROLS == len(controls),
        "controls_re_derived_from_the_carrier_bitstream":
            controls_vs_bitstream["all_sixteen_re_derived"],
        "capture_equals_candidate_word_for_word": words == candidate,
    }
    return {
        "run": run, "run_dir": run_dir, "plmarks": marks,
        "controls_exact": len(exact), "controls_declared": len(declared_control_fars),
        "control_fars": {"declared": declared_control_fars, "observed": observed_control_fars},
        "controls_vs_bitstream": controls_vs_bitstream,
        "words_matching_candidate": f"{matching}/{FRAME_WORDS}",
        "provenance": provenance, "checks": checks,
        "landing_verified": all(checks.values()),
    }

# The sixteen positive-control captures of each acquisition. They are pinned because the
# landing derivation re-reads them: 'sixteen controls exact' is otherwise the sweep tool's
# own self-report, and the oracle may not be derived from the thing it judges.
PINNED.update({
    "evidence/location_sweep_2026_08_20/step4_sweep/far_00000900.json":
        "23a11be167132bc336043a57f4134126c5329e6605287532d73ffa84c08a33d1",
    "evidence/location_sweep_2026_08_20/step4_sweep/far_00000986.json":
        "b3c30b3e2ded42e1c7835089a893947fc773fde66dbe9d4996db77e1df5df796",
    "evidence/location_sweep_2026_08_20/step4_sweep/far_000009a2.json":
        "b49be7d368e4de947836cdbf7f5147f12b37f73c3dfd715bd1a9fad3d6df5d62",
    "evidence/location_sweep_2026_08_20/step4_sweep/far_00000a8e.json":
        "b206f9bf177c35c2773705e3e0fd7981146e6b98dfae3f876118214c97ef3634",
    "evidence/location_sweep_2026_08_20/step4_sweep/far_00000b8a.json":
        "60429201033052784867021424c899ceb81f1284308b5939d63d4b01cc3db84b",
    "evidence/location_sweep_2026_08_20/step4_sweep/far_00000c04.json":
        "b12b3dde0c3dd0acbd8337c8aba8551f182594b0bc72293c7825d8a978f91655",
    "evidence/location_sweep_2026_08_20/step4_sweep/far_00000d04.json":
        "9ebade8e19b73a3185add31c1966fddee766cb7482e48104ab33a1d3890d55e5",
    "evidence/location_sweep_2026_08_20/step4_sweep/far_00400915.json":
        "c33b05e9bcdf18fe11f35efc0bae356b64962d5d4b642eb828577f2f05570523",
    "evidence/location_sweep_2026_08_20/step4_sweep/far_00400996.json":
        "e7e633e1a91f2726895a7e54257e5a04af33d61df2af98614c31629a15721664",
    "evidence/location_sweep_2026_08_20/step4_sweep/far_00400a10.json":
        "4a7617cc628032004b3c8d4f85f038d22409179997ea0b6ec43705da7634b8a8",
    "evidence/location_sweep_2026_08_20/step4_sweep/far_00400b05.json":
        "1b704516a85ff5f2414be048601f08193ecb917f00b904967780da53b5c230c5",
    "evidence/location_sweep_2026_08_20/step4_sweep/far_00400b91.json":
        "18429f144c864d03eb87b1b712882c569d9f69e09910a4ece154356b429150d3",
    "evidence/location_sweep_2026_08_20/step4_sweep/far_00400c0a.json":
        "ddd0a3694d4f9001801c36d07846a7047b335d96258ed18a8f464aa4befd1296",
    "evidence/location_sweep_2026_08_20/step4_sweep/far_00400c8e.json":
        "62cca5e83d533b8a4fac8613de9544bbfd19e75444f5f8233c676e2ff17ddf26",
    "evidence/location_sweep_2026_08_20/step4_sweep/far_00401101.json":
        "d415ac1c0d0b0541c82be0499cca0ad235260b5592d34edb425f155af6ac5ce5",
    "evidence/location_sweep_2026_08_20/step4_sweep/far_0040139b.json":
        "8773f452ed40e8522f7381c5cf564808c59f767b13f2e14400a92e6574b958fd",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_00000900.json":
        "bb4b3ab51933c963b89f03ed81d735f70b2221450ec862012e1ae2c46a515f5e",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_00000986.json":
        "e62bc0821cca857a47e8d37c227358fc48bf1b09cdbab0c6d57cfc4b38309913",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_000009a2.json":
        "c9165b81f63502ce230ca50f69aabb5047abb55b8c443ba55f9ccef80736afa6",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_00000a8e.json":
        "65022b85d3e6bf17f7ed9d388bce857db8ecfe1549a03ba8192054ec06464b3c",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_00000b8a.json":
        "41fa8255eb3a348810df77c9704011d6610d34f81d8acd38f46912d3cb135f53",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_00000c04.json":
        "b63405eb9f52065c6172baf6f5df44663b5bc26a76849a0ad09e814b203f1b85",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_00000d04.json":
        "12accca75ab5520e2249ca353f7d8c669728b8ec5cb139b8beb30265a65fe743",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_00400915.json":
        "1827df54a9e67f479cf216e02bed7f1b511f1bc92c22044e3901ac31a4a795ec",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_00400996.json":
        "6b02921be291706718dee4e595f8b289c3d0468470b66fccf78bc3491f08d883",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_00400a10.json":
        "ce007c199e0b32cccc2b63a3534d3063d1420ddcb9b3e17c5b616c7ea3a4e826",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_00400b05.json":
        "0769458a68c275e3bfe4d06d47d126505559d0790b8103af553b01fca8c3802e",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_00400b91.json":
        "ba0811b733cdbf59ccff4845136956b7a3cc132b29a788e4082def525d5c1709",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_00400c0a.json":
        "f6485d66b6ec9203c10fb63fc80d7debaf936471bf526d5ead53e8717c07c64a",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_00400c8e.json":
        "f1bf40c67b64d7a45a12c645703ddc9b3703bc7b2fce0f899e5cb3127fab2767",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_00401101.json":
        "eb02697ba247626cd6bd8b964e6cb6cb4e71f24d9156d631da976f76dc33b50a",
    "evidence/location_reproduction_2026_08_20/step4_sweep/far_0040139b.json":
        "2dc08f5275f2c66bcce391cc93f14925a1c7052ec23fd7ab237648dcf44ff7d5",
})

# Added when the 2026-08-20 read-side run extended both populations: the seventh engine
# record, its staging copy, and the erratum-004 second dump the 1.0.1 inventory had
# omitted. Every one of them is now inside the two-way closure guard.
PINNED.update({
    "evidence/calibration_noop_2026_08_13_erratum004/stage_dump_2.json":
        "a76d549bd57edf6f1f8aa4e14d83d82f9b600ac827765279db5625f7b8788443",
    "evidence/read_side_divergence_2026_08_20/fault/record.json":
        "ff1eed0d2cca43b43c07b2f05488328b8293b6dba73fed5e27c0ba8cfc4cccc7",
    "evidence/read_side_divergence_2026_08_20/ddr_slot0.json":
        "8f64f8adf4a66752f227003e89b694627aba7091c26428837cddc8dc821555d6",
})

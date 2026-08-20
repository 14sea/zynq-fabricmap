#!/usr/bin/env python3
"""Offline re-derivation of the six facts in docs/claimb_read_side_divergence_design.md §4.

W1 of that document. It touches no board and no network: it reads the pinned artifacts, the
committed evidence and the tracked source, recomputes every fact from them, and writes one
record. Nothing is asserted that is not computed here, and every input is hashed into the
output so the record can be checked against the tree it was taken from.

Two deliberate properties:

* **It refuses rather than reports** when a pinned digest does not match. A fact re-derived
  from an input that has drifted is not a re-derivation, it is a new measurement wearing the
  old name.
* **F6 is computed under BOTH stream orderings** — device-configuration order from
  `bitstream_frames.device_frame_sequence`, and the ascending-FAR order that
  `analyse_ddr_capture.py` uses — because the displacement bands are a property of the
  ordering, and a band that holds under only one of them would be an artifact of the tool.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import analyse_ddr_capture as add  # noqa: E402
import bitstream_frames as bf  # noqa: E402
import board_uboot_axi as axi  # noqa: E402

TOOL_VERSION = "analyse_read_side_facts.py/1.0.0"

FRAME_WORDS = 101
INTENDED_FAR = 0x00400A20
SEARCH_RADIUS = 2000

RUN_DIR = REPO / "gate_runs/claimb_round1_carrier_2026_08_13_erratum006"
REPORT = REPO / "gate_runs/claimb_round1_reachability_2026_08_10/reachability_report.json"
KNOWN_ANSWER = REPO / "gate_runs/claimb_round1_known_answer_2026_08_14/known_answer.json"
DRIVER = REPO / "scripts/board_claimb_known_answer.py"

O5 = REPO / "evidence/known_answer_2026_08_14_erratum006/record.json"
FAULTS = {
    "run1": REPO / "evidence/location_sweep_2026_08_20/fault/record.json",
    "run2": REPO / "evidence/location_reproduction_2026_08_20/fault/record.json",
}
CAPTURES = {
    "run1": REPO / "evidence/location_sweep_2026_08_20/fault/ddr_slot0_shutdown_read.json",
    "run2": (REPO / "evidence/location_reproduction_2026_08_20/fault"
                    "/ddr_slot0_shutdown_read.json"),
}

# The design's §2 freeze. A mismatch here is a refusal, not a warning.
PINNED = {
    "gate_runs/claimb_round1_carrier_2026_08_13_erratum006/phenotype_manifest.json":
        "e45f466d082ccd6f227e6f9be4ce75a4e98c4caa708808c09a77ed32331c10ef",
    "gate_runs/claimb_round1_carrier_2026_08_13_erratum006/local_map.json":
        "56f2b9e81e180eee2540286e4fde797e0d4820a49d10624c10844c38e99d87cb",
    "gate_runs/claimb_round1_carrier_2026_08_13_erratum006/carrier.bit":
        "8c3369e8e4755da5aceeb7844690d5e132b2e65647004c0a46c0e868e34f0b8a",
    "gate_runs/claimb_round1_reachability_2026_08_10/reachability_report.json":
        "f06bf9074bd0a017663ce9895760f817484590ab8a11afe27e438a75983b4930",
    "gate_runs/claimb_round1_known_answer_2026_08_14/known_answer.json":
        "b115e6be3c44b1500aaf0281bd7f480afa61654a12b1083a778fb9d9cb2f5ef1",
    "evidence/known_answer_2026_08_14_erratum006/record.json":
        "e944b85d572cb3a3cec7efe2326a4bd0f1d1b5c5df5c5ecf18ea4b9b73fe63c9",
    "evidence/location_sweep_2026_08_20/fault/record.json":
        "db87cd770d3174d128174edb005ab4c9f8462a1671501774d2824101efe2190a",
    "evidence/location_reproduction_2026_08_20/fault/record.json":
        "86bdf7f0f45997c8ff94cb56e25e2182e3564e18f5e8504bc4fe00419a2b8e1b",
    "evidence/location_sweep_2026_08_20/fault/ddr_slot0_shutdown_read.json":
        "413725bc551b1a2215405ac4b55a76a1fea73e0e8133df043ca0fac36caabc34",
    "evidence/location_reproduction_2026_08_20/fault/ddr_slot0_shutdown_read.json":
        "3221fa684a452fd7e71f70873c0085a6ea2ea8c2138525c91a7458df9e58e4e0",
}


class DerivationStop(Exception):
    """An input is not the input the design pinned."""


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame_sha(words: list[int]) -> str:
    return hashlib.sha256(b"".join(w.to_bytes(4, "big") for w in words)).hexdigest()


def checked_inputs() -> dict:
    """Hash every pinned input and refuse on the first disagreement."""
    seen = {}
    for relative, expected in PINNED.items():
        path = REPO / relative
        if not path.exists():
            raise DerivationStop(f"{relative} is missing")
        actual = sha256_of(path)
        if actual != expected:
            raise DerivationStop(
                f"{relative}: sha256 {actual} != pinned {expected}. The design's §2 freeze "
                f"does not describe this tree, so nothing below would be a re-derivation.")
        seen[relative] = actual
    return seen


# --------------------------------------------------------------------------------- F1

def fact_f1(manifest: dict) -> dict:
    """Every frame of the write envelope, its content digest and its non-zero count."""
    frames = []
    digests = {}
    for record in manifest["frames"]:
        words = [int(w, 16) for w in record["words"]]
        digest = frame_sha(words)
        if digest != record["sha256"]:
            raise DerivationStop(
                f"{record['far']}: manifest sha256 does not match its own words")
        frames.append({"far": record["far"], "role": record["role"],
                       "nonzero_words": sum(1 for w in words if w), "sha256": digest})
        digests.setdefault(digest, []).append(record["far"])
    return {
        "what": "the fifteen frames of the write envelope, as the frozen manifest holds them",
        "frames": frames,
        "distinct_contents": len(digests),
        "all_identical": len(digests) == 1,
        "all_zero": all(f["nonzero_words"] == 0 for f in frames),
        "content_sha256": next(iter(digests)) if len(digests) == 1 else None,
    }


# --------------------------------------------------------------------------------- F2

def fact_f2(known: dict, o5: dict) -> dict:
    """What the no-op step writes, read out of the driver's AST, and what O5 read back."""
    tree = ast.parse(DRIVER.read_text("utf-8"))
    payloads = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "step" and node.args):
            continue
        label = node.args[0]
        if not (isinstance(label, ast.Constant) and label.value == "no_op"):
            continue
        for inner in ast.walk(node):
            if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
                    and inner.func.id == "_write" and inner.args
                    and isinstance(inner.args[0], ast.Constant)):
                payloads.append({"line": node.lineno, "writes": inner.args[0].value})
    if len(payloads) != 1:
        raise DerivationStop(
            f"expected exactly one no_op step calling _write, found {len(payloads)}")

    transaction = o5["round"]["steps"][0]["result"]["transaction"]
    read = {far: words for far, words in transaction["readback_frames"].items()}
    nonblank = {hex(int(far)): sum(1 for w in words if w)
                for far, words in read.items() if any(words)}
    return {
        "what": "the no-op writes the restore payload, and O5 read fifteen blank frames back",
        "no_op_step": payloads[0],
        "restore_actual_init": known["restore"]["actual_init"],
        "o5_step": o5["round"]["steps"][0]["step"],
        "o5_state": o5["round"]["steps"][0]["state"],
        "o5_frames_read": len(read),
        "o5_nonblank_frames": nonblank,
        "o5_rb_frames_ok": transaction["status_after"]["rb_frames_ok"],
        "o5_configuration_valid": transaction["status_after"]["configuration_valid"],
        "o5_readback_latency": transaction["readback_latency"],
        "degenerate_as_content_control":
            payloads[0]["writes"] == "restore"
            and known["restore"]["actual_init"] == "0x0000000000000000"
            and not nonblank,
    }


# --------------------------------------------------------------------------------- F3

def fact_f3(candidate: dict, base: dict) -> dict:
    """Where the candidate differs from the blank base, frame by frame."""
    touched = []
    for far in sorted(candidate):
        differing = [i for i in range(FRAME_WORDS) if candidate[far][i] != base[far][i]]
        if not differing:
            continue
        touched.append({
            "far": f"0x{far:08X}",
            "words": differing,
            "values": [f"0x{candidate[far][i]:08x}" for i in differing],
            "sha256": frame_sha(candidate[far]),
        })
    return {
        "what": "the candidate against the blank base, per frame",
        "touched_frames": touched,
        "words_per_touched_frame": sorted({tuple(t["words"]) for t in touched}),
        "intended_far_sha256": frame_sha(candidate[INTENDED_FAR]),
    }


# --------------------------------------------------------------------------------- F4

def fact_f4(candidate: dict, base: dict) -> dict:
    """Both staging captures, against the base and the candidate at the intended FAR."""
    out = {}
    for name, path in CAPTURES.items():
        capture = json.loads(path.read_text("utf-8"))
        words = [int(w, 16) for w in capture["words"]]
        out[name] = {
            "plmark": capture.get("plmark"),
            "words": len(words),
            "nonzero_words": sum(1 for w in words if w),
            "sha256": frame_sha(words),
            "equals_base_at_intended_far": words == base[INTENDED_FAR],
            "equals_candidate_at_intended_far": words == candidate[INTENDED_FAR],
        }
    digests = {v["sha256"] for v in out.values()}
    marks = {v["plmark"] for v in out.values()}
    return {
        "what": "the two staging copies of the failing frame",
        "captures": out,
        "identical_across_runs": len(digests) == 1,
        "distinct_plmarks": len(marks) == len(out),
    }


# --------------------------------------------------------------------------------- F5

def _last_register_read(commands: list[dict], address: int) -> int | None:
    """The last word an `md.l <address> 0x1` returned, taken from the command's own reply.

    The status is DERIVED from the record here, never restated from the design: a document
    that asserts `0x04040082` and a record that shows something else must disagree loudly.
    """
    pattern = re.compile(rf"^{address:08x}: *([0-9a-f]{{8}})", re.MULTILINE | re.IGNORECASE)
    want = f"md.l 0x{address:08x} 0x1"
    for command in reversed(commands):
        if command.get("command", "").lower() != want:
            continue
        found = pattern.search(command.get("raw", ""))
        if found:
            return int(found.group(1), 16)
    return None


def fact_f5(o5: dict) -> dict:
    """The fault status of both runs, decoded, beside the passing no-op's latency."""
    runs = {}
    words = set()
    for name, path in FAULTS.items():
        record = json.loads(path.read_text("utf-8"))
        commands = record["instrumentation"]["commands"]
        status = _last_register_read(commands, axi.STATUS)
        fault = _last_register_read(commands, axi.FAULT)
        if status is None:
            raise DerivationStop(f"{name}: no STATUS read found in {len(commands)} commands")
        words.add(status)
        runs[name] = {
            "step": record["round"]["steps"][1]["step"],
            "state": record["round"]["steps"][1]["state"],
            "stop_reason": record["round"]["steps"][1]["stop_reason"],
            "commands": len(commands),
            "last_status_word": f"0x{status:08x}",
            "last_status_decoded": axi.decode_status(status),
            "last_fault_word": None if fault is None else f"0x{fault:08x}",
            "no_op_transaction_elapsed_s":
                record["round"]["steps"][0]["result"]["transaction"]["elapsed_s"],
            "wall_s": round(record["finished_at"] - record["started_at"], 1),
            "setup_steps": [{"step": step["step"], "elapsed_s": step["elapsed_s"],
                             "returncode": step["returncode"]}
                            for step in record["setup"]["steps"]],
        }
    o5_transaction = o5["round"]["steps"][0]["result"]["transaction"]
    o5_latency = o5_transaction["readback_latency"][0]["words"]
    decoded = axi.decode_status(next(iter(words)))
    return {
        "what": "the specified fault as the records show it, beside the passing run's latency",
        "same_status_word_in_both_runs": len(words) == 1,
        "fault_status_decoded": decoded,
        "fault_code_name": axi.FAULT_NAMES[8],
        "codes_that_did_not_fire": {"12": axi.FAULT_NAMES[12], "10": axi.FAULT_NAMES[10]},
        "o5_readback_latency": o5_transaction["readback_latency"],
        "latency_matches_passing_run": decoded["rb_latency_words"] == o5_latency,
        "runs": runs,
    }


# --------------------------------------------------------------------------------- F6

def _stream(device: dict, order: list[int]) -> tuple[list[int], dict[int, int]]:
    words: list[int] = []
    position: dict[int, int] = {}
    for far in order:
        position[far] = len(words)
        words.extend(device[far])
    return words, position


def _bands(stream: list[int], origin: int, radius: int) -> list[list[int]]:
    """Every displacement whose 101-word window is all zero, as contiguous runs."""
    hits = []
    for delta in range(-radius, radius + 1):
        start = origin + delta
        if start < 0 or start + FRAME_WORDS > len(stream):
            continue
        if not any(stream[start:start + FRAME_WORDS]):
            hits.append(delta)
    bands: list[list[int]] = []
    for delta in hits:
        if bands and delta == bands[-1][1] + 1:
            bands[-1][1] = delta
        else:
            bands.append([delta, delta])
    return bands


def fact_f6(device: dict, candidate: dict, base: dict) -> dict:
    """The displacement bands, under both orderings, before and after the write."""
    orders = {
        "device_configuration_order":
            [far for far in bf.device_frame_sequence(bf.device_layout()) if far is not None],
        "ascending_far_order": sorted(device),
    }
    out = {}
    for name, order in orders.items():
        if sorted(order) != sorted(device):
            raise DerivationStop(f"{name} does not cover the device's frames exactly once")
        pre, position = _stream(device, order)
        post = list(pre)
        for far, words in candidate.items():
            if words != base[far]:
                post[position[far]:position[far] + FRAME_WORDS] = words
        origin = position[INTENDED_FAR]
        out[name] = {
            "intended_far_word_offset": origin,
            "pre_write_bands": _bands(pre, origin, SEARCH_RADIUS),
            "post_write_bands": _bands(post, origin, SEARCH_RADIUS),
            "all_zero_windows_in_full_pre_write_stream":
                add.offsets_matching(pre, [0] * FRAME_WORDS),
            "all_zero_windows_in_full_post_write_stream":
                add.offsets_matching(post, [0] * FRAME_WORDS),
        }
    first = next(iter(out.values()))
    return {
        "what": "displacements whose 101-word window is all zero, within the search radius",
        "search_radius_words": SEARCH_RADIUS,
        "orderings_agree": all(
            v["pre_write_bands"] == first["pre_write_bands"]
            and v["post_write_bands"] == first["post_write_bands"] for v in out.values()),
        "by_ordering": out,
        "small_displacements_excluded_post_write": not any(
            band[0] <= delta <= band[1]
            for band in first["post_write_bands"] for delta in range(-50, 51)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    inputs = checked_inputs()

    manifest = json.loads((RUN_DIR / "phenotype_manifest.json").read_text("utf-8"))
    local_map = json.loads((RUN_DIR / "local_map.json").read_text("utf-8"))
    report = json.loads(REPORT.read_text("utf-8"))
    known = json.loads(KNOWN_ANSWER.read_text("utf-8"))
    o5 = json.loads(O5.read_text("utf-8"))

    base = {int(r["far"], 16): [int(w, 16) for w in r["words"]] for r in manifest["frames"]}
    candidate, mask, init = add.derive_candidate(manifest, local_map, report)
    device = bf.parse_frames(RUN_DIR / "carrier.bit")["frames"]

    record = {
        "tool": TOOL_VERSION,
        "what": "W1 of docs/claimb_read_side_divergence_design.md: F1-F6, re-derived",
        "inputs": inputs,
        "derived": {"mutable_mask": f"0x{mask:016X}", "candidate_init": f"0x{init:016X}"},
        "F1": fact_f1(manifest),
        "F2": fact_f2(known, o5),
        "F3": fact_f3(candidate, base),
        "F4": fact_f4(candidate, base),
        "F5": fact_f5(o5),
        "F6": fact_f6(device, candidate, base),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")

    f1, f2, f4, f6 = record["F1"], record["F2"], record["F4"], record["F6"]
    print(f"{TOOL_VERSION}: {len(inputs)} pinned inputs verified")
    print(f"F1  {len(f1['frames'])} envelope frames, {f1['distinct_contents']} distinct "
          f"content, all_zero={f1['all_zero']}, sha={f1['content_sha256']}")
    print(f"F2  no_op writes '{f2['no_op_step']['writes']}' (line {f2['no_op_step']['line']}), "
          f"restore init {f2['restore_actual_init']}, O5 non-blank frames "
          f"{f2['o5_nonblank_frames']}, degenerate={f2['degenerate_as_content_control']}")
    print(f"F3  touched {[t['far'] for t in record['F3']['touched_frames']]}, "
          f"words {record['F3']['words_per_touched_frame']}")
    print(f"F4  identical_across_runs={f4['identical_across_runs']}, "
          f"distinct_plmarks={f4['distinct_plmarks']}, "
          f"nonzero={[v['nonzero_words'] for v in f4['captures'].values()]}")
    f5 = record["F5"]
    print(f"F5  status read from the records: "
          f"{[r['last_status_word'] for r in f5['runs'].values()]} -> "
          f"{f5['fault_code_name']}, latency "
          f"{f5['fault_status_decoded']['rb_latency_words']}, "
          f"matches_passing_run={f5['latency_matches_passing_run']}, "
          f"fault reg {[r['last_fault_word'] for r in f5['runs'].values()]}")
    print(f"    wall {[r['wall_s'] for r in f5['runs'].values()]} s, of which loadb "
          f"{[r['setup_steps'][-1]['elapsed_s'] for r in f5['runs'].values()]} s; "
          f"no-op transaction {[r['no_op_transaction_elapsed_s'] for r in f5['runs'].values()]} s")
    print(f"F6  orderings_agree={f6['orderings_agree']}, "
          f"small_displacements_excluded={f6['small_displacements_excluded_post_write']}")
    for name, value in f6["by_ordering"].items():
        print(f"    {name}: pre {value['pre_write_bands']} post {value['post_write_bands']}")
    print(f"    all-zero windows in the full pre-write stream: "
          f"{next(iter(f6['by_ordering'].values()))['all_zero_windows_in_full_pre_write_stream']}")
    print(f"wrote {add.rel(args.out)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DerivationStop as stop:
        print(f"DerivationStop: {stop}", file=sys.stderr)
        raise SystemExit(1)

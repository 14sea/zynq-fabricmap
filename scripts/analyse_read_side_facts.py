#!/usr/bin/env python3
"""W1: offline re-derivation of the six facts in docs/claimb_read_side_divergence_design.md §4.

It touches no board and no network: it reads the pinned artifacts, the committed evidence and
the tracked source, recomputes every fact from them, and writes one record. Nothing is asserted
that is not computed here.

`read_side_evidence.py` holds the frozen inventory and enforces it. Three properties follow:

* **it refuses rather than reports** when a pinned digest, the loaded-module set, or a derived
  flag disagrees with the freeze;
* **F3 is not derivation alone.** The candidate is re-derived from the frozen authority AND
  read back out of both 2026-08-20 JTAG captures, so "the intended FAR held the candidate" is
  checked against the instances that observed it, not inferred from the payload;
* **F6 is computed under BOTH stream orderings** — device-configuration order and ascending
  FAR — because the displacement bands are a property of the ordering, and a band that held
  under only one of them would be an artifact of the traversal.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import analyse_ddr_capture as add  # noqa: E402
import bitstream_frames as bf  # noqa: E402
import board_uboot_axi as axi  # noqa: E402
import read_side_evidence as rse  # noqa: E402

TOOL_VERSION = "analyse_read_side_facts.py/2.0.0"
SEARCH_RADIUS = 2000
EXPECTED_FAULT_CODE = 8


# --------------------------------------------------------------------------------- F1

def fact_f1(manifest: dict) -> dict:
    """Every frame of the write envelope, its content digest and its non-zero count."""
    frames, digests = [], {}
    for record in manifest["frames"]:
        words = [int(w, 16) for w in record["words"]]
        digest = rse.frame_sha(words)
        if digest != record["sha256"]:
            raise rse.DerivationStop(
                f"{record['far']}: the manifest's sha256 does not match its own words")
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

def no_op_payload(root: Path) -> dict:
    """Which payload the no-op step writes, read out of the driver's AST, not its prose."""
    tree = ast.parse((root / rse.DRIVER).read_text("utf-8"))
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
        raise rse.DerivationStop(
            f"{rse.DRIVER}: expected exactly one no_op step calling _write, "
            f"found {len(payloads)}")
    return payloads[0]


def fact_f2(root: Path, known: dict, o5: dict) -> dict:
    """What the no-op writes, and what O5's fifteen frames came back as."""
    payload = no_op_payload(root)
    transaction = o5["round"]["steps"][0]["result"]["transaction"]
    read = transaction["readback_frames"]
    nonblank = {hex(int(far)): sum(1 for w in words if w)
                for far, words in read.items() if any(words)}
    return {
        "what": "the no-op writes the restore payload, and O5 read fifteen blank frames back",
        "no_op_step": payload,
        "restore_actual_init": known["restore"]["actual_init"],
        "o5_step": o5["round"]["steps"][0]["step"],
        "o5_state": o5["round"]["steps"][0]["state"],
        "o5_frames_read": len(read),
        "o5_nonblank_frames": nonblank,
        "o5_rb_frames_ok": transaction["status_after"]["rb_frames_ok"],
        "o5_configuration_valid": transaction["status_after"]["configuration_valid"],
        "o5_readback_latency": transaction["readback_latency"],
        "degenerate_as_content_control":
            payload["writes"] == "restore"
            and known["restore"]["actual_init"] == "0x0000000000000000"
            and not nonblank,
    }


# --------------------------------------------------------------------------------- F3

def fact_f3(root: Path, candidate: dict, base: dict) -> dict:
    """The candidate against the base — and against what both JTAG captures actually read."""
    touched = []
    for far in sorted(candidate):
        differing = [i for i in range(rse.FRAME_WORDS) if candidate[far][i] != base[far][i]]
        if not differing:
            continue
        touched.append({
            "far": f"0x{far:08X}",
            "words": differing,
            "values": [f"0x{candidate[far][i]:08x}" for i in differing],
            "sha256": rse.frame_sha(candidate[far]),
        })

    wanted = candidate[rse.INTENDED_FAR]
    observed = {}
    for run in rse.LOCATION_RUNS:
        words, provenance = rse.candidate_frame_from_capture(root, rse.LOCATION_RUNS[run])
        observed[run] = {
            **provenance,
            "words_matching_candidate":
                f"{sum(1 for a, b in zip(words, wanted) if a == b)}/{rse.FRAME_WORDS}",
            "equals_candidate": words == wanted,
            "nonzero_words": [i for i, w in enumerate(words) if w],
        }
    if not all(v["equals_candidate"] for v in observed.values()):
        raise rse.DerivationStop(
            "a 2026-08-20 JTAG capture at the intended FAR does not equal the re-derived "
            "candidate; F3 cannot be reported as reproduced")
    digests = {v["frame_sha256"] for v in observed.values()}

    return {
        "what": "the candidate against the blank base, and against both JTAG observations",
        "touched_frames": touched,
        "words_per_touched_frame": sorted({tuple(t["words"]) for t in touched}),
        "intended_far_sha256": rse.frame_sha(wanted),
        "observed_at_the_intended_far": observed,
        "both_captures_agree": len(digests) == 1,
        "capture_digest_equals_derived":
            next(iter(digests)) == rse.frame_sha(wanted) if len(digests) == 1 else False,
    }


# --------------------------------------------------------------------------------- F4

def fact_f4(root: Path, candidate: dict, base: dict) -> dict:
    """Both staging captures, against the base and the candidate at the intended FAR."""
    out = {}
    for run, run_dir in rse.LOCATION_RUNS.items():
        relative = f"{run_dir}/fault/ddr_slot0_shutdown_read.json"
        capture = rse.load(root, relative)
        words = rse.as_words(capture["words"])
        out[run] = {
            "source": relative,
            "plmark": capture.get("plmark"),
            "words": len(words),
            "nonzero_words": sum(1 for w in words if w),
            "sha256": rse.frame_sha(words),
            "equals_base_at_intended_far": words == base[rse.INTENDED_FAR],
            "equals_candidate_at_intended_far": words == candidate[rse.INTENDED_FAR],
        }
    return {
        "what": "the two staging copies of the failing frame",
        "captures": out,
        "identical_across_runs": len({v["sha256"] for v in out.values()}) == 1,
        "distinct_plmarks": len({v["plmark"] for v in out.values()}) == len(out),
    }


# --------------------------------------------------------------------------------- F5

def last_register_read(commands: list[dict], address: int) -> int | None:
    """The last word an `md.l <address> 0x1` returned, taken from the command's own reply."""
    pattern = re.compile(rf"^{address:08x}: *([0-9a-f]{{8}})", re.MULTILINE | re.IGNORECASE)
    want = f"md.l 0x{address:08x} 0x1"
    for command in reversed(commands):
        if command.get("command", "").lower() != want:
            continue
        found = pattern.search(command.get("raw", ""))
        if found:
            return int(found.group(1), 16)
    return None


def fact_f5(root: Path, o5: dict) -> dict:
    """The fault, decoded out of each record, beside the passing no-op's latency.

    Nothing here is named in advance: the status word, the FAULT word and therefore the fault's
    NAME are all read from the records, the two runs are required to agree, and the code is
    masked exactly the way `board_uboot_axi.read_fault` masks it on the wire.
    """
    runs, status_words, fault_codes = {}, set(), set()
    for run, run_dir in rse.LOCATION_RUNS.items():
        record = rse.load(root, f"{run_dir}/fault/record.json")
        commands = record["instrumentation"]["commands"]
        status = last_register_read(commands, axi.STATUS)
        fault = last_register_read(commands, axi.FAULT)
        if status is None or fault is None:
            raise rse.DerivationStop(
                f"{run}: no STATUS/FAULT read found in {len(commands)} commands")
        code = fault & 0xF
        status_words.add(status)
        fault_codes.add(code)
        runs[run] = {
            "step": record["round"]["steps"][1]["step"],
            "state": record["round"]["steps"][1]["state"],
            "stop_reason": record["round"]["steps"][1]["stop_reason"],
            "commands": len(commands),
            "last_status_word": f"0x{status:08x}",
            "last_status_decoded": axi.decode_status(status),
            "last_fault_word": f"0x{fault:08x}",
            "fault_code": code,
            "fault_code_name": axi.FAULT_NAMES.get(code, f"unknown({code})"),
            "no_op_transaction_elapsed_s":
                record["round"]["steps"][0]["result"]["transaction"]["elapsed_s"],
            "wall_s": round(record["finished_at"] - record["started_at"], 1),
            "setup_steps": [{"step": s["step"], "elapsed_s": s["elapsed_s"],
                             "returncode": s["returncode"]} for s in record["setup"]["steps"]],
        }
    if len(status_words) != 1 or len(fault_codes) != 1:
        raise rse.DerivationStop(
            f"the two runs disagree: status {sorted(status_words)}, "
            f"fault codes {sorted(fault_codes)}")
    code = next(iter(fault_codes))
    if code != EXPECTED_FAULT_CODE:
        raise rse.DerivationStop(
            f"the FAULT register reports code {code} "
            f"({axi.FAULT_NAMES.get(code, 'unknown')}), not "
            f"{EXPECTED_FAULT_CODE} ({axi.FAULT_NAMES[EXPECTED_FAULT_CODE]}); the design "
            f"describes a different fault from the one in these records")

    decoded = axi.decode_status(next(iter(status_words)))
    o5_transaction = o5["round"]["steps"][0]["result"]["transaction"]
    o5_latency = o5_transaction["readback_latency"][0]["words"]
    return {
        "what": "the specified fault as the records show it, beside the passing run's latency",
        "same_status_word_in_both_runs": True,
        "same_fault_code_in_both_runs": True,
        "fault_code": code,
        "fault_code_name": axi.FAULT_NAMES[code],
        "fault_status_decoded": decoded,
        "codes_that_did_not_fire": {
            str(other): name for other, name in axi.FAULT_NAMES.items()
            if other in (10, 12)},
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
        if start < 0 or start + rse.FRAME_WORDS > len(stream):
            continue
        if not any(stream[start:start + rse.FRAME_WORDS]):
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
            raise rse.DerivationStop(
                f"{name} does not cover the device's frames exactly once")
        pre, position = _stream(device, order)
        post = list(pre)
        for far, words in candidate.items():
            if words != base[far]:
                post[position[far]:position[far] + rse.FRAME_WORDS] = words
        origin = position[rse.INTENDED_FAR]
        out[name] = {
            "intended_far_word_offset": origin,
            "pre_write_bands": _bands(pre, origin, SEARCH_RADIUS),
            "post_write_bands": _bands(post, origin, SEARCH_RADIUS),
            "all_zero_windows_in_full_pre_write_stream":
                add.offsets_matching(pre, [0] * rse.FRAME_WORDS),
            "all_zero_windows_in_full_post_write_stream":
                add.offsets_matching(post, [0] * rse.FRAME_WORDS),
        }
    first = next(iter(out.values()))
    return {
        "what": "displacements whose 101-word window is all zero, within the search radius",
        "search_radius_words": SEARCH_RADIUS,
        "the_search_is_local": (
            "outside ±%d words nothing was searched, so a distant misaddress is "
            "unconstrained by this fact" % SEARCH_RADIUS),
        "orderings_agree": all(
            v["pre_write_bands"] == first["pre_write_bands"]
            and v["post_write_bands"] == first["post_write_bands"] for v in out.values()),
        "by_ordering": out,
        "small_displacements_excluded_post_write": not any(
            band[0] <= delta <= band[1]
            for band in first["post_write_bands"] for delta in range(-50, 51)),
    }


def derive(root: Path = REPO) -> dict:
    """Everything, in one record. Refuses before it computes anything."""
    inputs = rse.checked_inputs(root)

    manifest = rse.load(root, f"{rse.RUN_DIR}/phenotype_manifest.json")
    local_map = rse.load(root, f"{rse.RUN_DIR}/local_map.json")
    report = rse.load(root, rse.REPORT)
    known = rse.load(root, rse.KNOWN_ANSWER)
    o5 = rse.load(root, "evidence/known_answer_2026_08_14_erratum006/record.json")

    base = {int(r["far"], 16): [int(w, 16) for w in r["words"]] for r in manifest["frames"]}
    candidate, mask, init = add.derive_candidate(manifest, local_map, report)
    device = bf.parse_frames(root / rse.RUN_DIR / "carrier.bit")["frames"]

    return {
        "tool": TOOL_VERSION,
        "what": "W1 of docs/claimb_read_side_divergence_design.md: F1-F6, re-derived",
        "inputs": inputs,
        "pinning": {
            "pinned_files": len(rse.PINNED),
            "self_exempt": list(rse.SELF),
            "why": ("the three files of this deliverable cannot pin themselves; the commit "
                    "anchors them, and every OTHER loaded repository module must be pinned"),
        },
        "derived": {"mutable_mask": f"0x{mask:016X}", "candidate_init": f"0x{init:016X}"},
        "F1": fact_f1(manifest),
        "F2": fact_f2(root, known, o5),
        "F3": fact_f3(root, candidate, base),
        "F4": fact_f4(root, candidate, base),
        "F5": fact_f5(root, o5),
        "F6": fact_f6(device, candidate, base),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--root", type=Path, default=REPO)
    args = ap.parse_args()

    record = derive(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")

    f1, f2, f3, f4, f5, f6 = (record[k] for k in ("F1", "F2", "F3", "F4", "F5", "F6"))
    print(f"{TOOL_VERSION}: {len(record['inputs'])} pinned inputs verified, "
          f"every loaded repo module pinned except {len(rse.SELF)} of this deliverable")
    print(f"F1  {len(f1['frames'])} envelope frames, {f1['distinct_contents']} distinct "
          f"content, all_zero={f1['all_zero']}, sha={f1['content_sha256']}")
    print(f"F2  no_op writes '{f2['no_op_step']['writes']}' (line {f2['no_op_step']['line']}), "
          f"restore init {f2['restore_actual_init']}, O5 non-blank frames "
          f"{f2['o5_nonblank_frames']}, degenerate={f2['degenerate_as_content_control']}")
    print(f"F3  touched {[t['far'] for t in f3['touched_frames']]}, "
          f"words {f3['words_per_touched_frame']}")
    for run, value in f3["observed_at_the_intended_far"].items():
        print(f"    {run} JTAG {value['capture']} -> {value['words_matching_candidate']} "
              f"words equal the candidate, nonzero at {value['nonzero_words']}")
    print(f"    both_captures_agree={f3['both_captures_agree']}, "
          f"capture_digest_equals_derived={f3['capture_digest_equals_derived']}")
    print(f"F4  identical_across_runs={f4['identical_across_runs']}, "
          f"distinct_plmarks={f4['distinct_plmarks']}, "
          f"nonzero={[v['nonzero_words'] for v in f4['captures'].values()]}")
    print(f"F5  status {[r['last_status_word'] for r in f5['runs'].values()]}, "
          f"FAULT {[r['last_fault_word'] for r in f5['runs'].values()]} -> code "
          f"{f5['fault_code']} ({f5['fault_code_name']}), latency "
          f"{f5['fault_status_decoded']['rb_latency_words']}, "
          f"matches_passing_run={f5['latency_matches_passing_run']}")
    print(f"    wall {[r['wall_s'] for r in f5['runs'].values()]} s, of which loadb "
          f"{[r['setup_steps'][-1]['elapsed_s'] for r in f5['runs'].values()]} s; "
          f"no-op transaction "
          f"{[r['no_op_transaction_elapsed_s'] for r in f5['runs'].values()]} s")
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
    except rse.DerivationStop as stop:
        print(f"DerivationStop: {stop}", file=sys.stderr)
        raise SystemExit(1)

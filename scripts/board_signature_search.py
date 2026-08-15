#!/usr/bin/env python3
"""Search the device's frames for the known-answer signature, one process per frame.

WHY IT IS SHAPED LIKE THIS
--------------------------
A JTAG readback is trustworthy exactly once per OpenOCD process: measured on 2026-08-15,
where the same frame came back bit-exact as a process's first read and all-zero as its
second, in both orders, and became exact again in a fresh process against the same load.
So the unit of work here is a child process that reads **one** FAR, and the only thing this
module adds is bookkeeping around it. It never builds a JTAG packet: `probe_jtag_config_read`
owns that path, including the refusals, and this module would rather spawn it than
reimplement it.

WHAT IT MAY LOOK AT
-------------------
Only FARs that appear in the frozen device frame sequence of the run's own `carrier.bit`.
There is no argument that widens that set, and none that names a FAR the sequence does not
contain. Nothing here reloads the PL, touches the carrier's AXI window, or can reach WCFG,
FDRI, JPROGRAM or JSTART — those live behind the child's `check_sequence()` and its IR
allowlist, and are asserted by that tool's tests.

WHAT COUNTS AS FINDING SOMETHING
--------------------------------
A whole 101-word frame equal to a whole expected frame. Not a few INIT bits, which the
device's 4,716 all-zero frames would hand out for free, and never an all-zero signature:
`candidate_signatures()` refuses to search for one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import bitstream_frames as bf  # noqa: E402
import board_serial as bs  # noqa: E402
import frame_ecc  # noqa: E402
import probe_jtag_config_read as probe  # noqa: E402

CHILD = REPO / "scripts/probe_jtag_config_read.py"
INTENDED_FAR = 0x00400A20
LUT_FEATURE = re.compile(r"CLBLL_L\.SLICEL_X0\.ALUT\.INIT\[(\d+)\]$")


class SearchStop(Exception):
    """Anything that makes the next read meaningless, or the record incomplete."""


# --------------------------------------------------------------------- what may be read
def frozen_far_sequence(run_dir: Path) -> list[int]:
    """Every FAR of the run's own bitstream, in address order. The only admissible set."""
    frames = bf.parse_frames(run_dir / "carrier.bit")["frames"]
    return sorted(frames)


def base_frames(run_dir: Path) -> dict[int, list[int]]:
    return {far: list(words)
            for far, words in bf.parse_frames(run_dir / "carrier.bit")["frames"].items()}


def candidate_signatures(run_dir: Path, report: Path) -> dict[int, list[int]]:
    """The frames the known-answer candidate writes, re-derived from the frozen inputs.

    Refuses an all-zero signature: searching for one would report every zero frame on the
    device as a hit, which is the floor this whole line keeps falling through.
    """
    manifest = json.loads((run_dir / "phenotype_manifest.json").read_text("utf-8"))
    local_map = json.loads((run_dir / "local_map.json").read_text("utf-8"))
    truth = json.loads(report.read_text("utf-8"))["per_lut"][0]["target_truth_table"]

    positions = {}
    for entry in local_map["universe"]["addresses"]:
        found = LUT_FEATURE.match(entry["feature"])
        if found:
            positions[int(found.group(1))] = (int(entry["far"], 16), entry["word"], entry["bit"])
    mask = 0
    for position in positions:
        mask |= 1 << position
    init = int(truth.split("'h")[1], 16) & mask

    pinned = {int(record["far"], 16): [int(word, 16) for word in record["words"]]
              for record in manifest["frames"]}
    frames = {far: list(words) for far, words in pinned.items()}
    touched = set()
    for position in range(64):
        if (init >> position) & 1:
            far, word, bit = positions[position]
            frames[far][word] |= 1 << bit
            touched.add(far)
    signatures = {}
    for far in sorted(touched):
        words = frame_ecc.update_ecc(frames[far])
        if not any(words):
            raise SearchStop(f"the signature for {far:#010x} is all zero and cannot be searched for")
        signatures[far] = words
    return signatures


def inputs_digest(run_dir: Path, report: Path, fars: list[int]) -> str:
    """What a resumed run must still be looking at. A drift here invalidates the captures."""
    parts = [hashlib.sha256((run_dir / name).read_bytes()).hexdigest()
             for name in ("carrier.bit", "phenotype_manifest.json", "local_map.json")]
    parts.append(hashlib.sha256(report.read_bytes()).hexdigest())
    parts.append(hashlib.sha256(",".join(f"{far:08x}" for far in fars).encode()).hexdigest())
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


# ------------------------------------------------------------------------------ the board
def read_plmark(port: str) -> str:
    """The loader's marker, over the PS UART only. No AXI, no `md`, no writes."""
    with __import__("serial").Serial(port, bs.BAUD, timeout=0.1) as ser:
        sync = bs.ub_cmd(ser, bs.SYNC_COMMAND, 3.0)
        reply = bs.ub_cmd(ser, "printenv plmark", 3.0)
    if bs.BOOT_BANNER_RE.search(sync + reply):
        raise SearchStop("a boot banner came back: the board restarted, the PL is not the one loaded")
    found = re.search(rb"plmark=([0-9a-f]+)", reply)
    if not found:
        raise SearchStop(f"plmark is not set: {reply[-120:]!r}")
    return found.group(1).decode("ascii")


def check_child_argv(argv: list[str]) -> None:
    """Exactly one FAR per child. The measurement says a process is good for one read."""
    if argv.count("--far") != 1:
        raise SearchStop(
            f"a child must be given exactly one --far, got {argv.count('--far')}: {argv}")


def child_argv(far: int, out_path: Path, cfg: str | None, speed: int | None) -> list[str]:
    argv = [sys.executable, str(CHILD), "--far", f"{far:#010x}", "--out", str(out_path)]
    if cfg:
        argv += ["--cfg", cfg]
    if speed:
        argv += ["--speed", str(speed)]
    check_child_argv(argv)
    return argv


def subprocess_runner(far: int, out_path: Path, cfg: str | None = None,
                      speed: int | None = None, timeout: float = 600) -> int:
    argv = child_argv(far, out_path, cfg, speed)
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout).returncode


# ------------------------------------------------------------------------ the bookkeeping
def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8")
    try:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    os.replace(handle.name, path)


def validate_capture(far: int, capture: dict) -> list[int]:
    """A capture is usable only if it is this FAR, read once, whole."""
    if capture.get("verdict") != "READ":
        raise SearchStop(f"{far:#010x}: the child did not read ({capture.get('stop_reason')})")
    if capture.get("idcode") != "0x13722093":
        raise SearchStop(f"{far:#010x}: IDCODE {capture.get('idcode')}")
    frames = capture.get("frames", {})
    if list(frames) != [f"{far:#010x}"]:
        raise SearchStop(f"{far:#010x}: the capture holds {list(frames)}")
    words = [int(word, 16) for word in frames[f"{far:#010x}"]["frame"]]
    if len(words) != probe.FRAME_WORDS:
        raise SearchStop(f"{far:#010x}: {len(words)} words")
    return words


def run_search(fars: list[int], out_dir: Path, plmark: str, digest: str,
               runner=subprocess_runner, port: str = "/dev/ebaz-uart",
               max_reads: int | None = None, plmark_reader=read_plmark) -> dict:
    """One child per FAR, atomic per capture, resumable, and never a silent skip."""
    index_path = out_dir / "index.json"
    index: dict = {"tool": "board_signature_search.py/1.0.0", "inputs_digest": digest,
                   "plmark_at_start": plmark, "entries": {}}
    if index_path.exists():
        previous = json.loads(index_path.read_text("utf-8"))
        if previous.get("inputs_digest") != digest:
            raise SearchStop("the resumed run's inputs differ from the captures on disk")
        if previous.get("plmark_at_start") != plmark:
            raise SearchStop("the resumed run is a different boot from the captures on disk")
        index = previous
        index.setdefault("entries", {})

    reads = 0
    for far in fars:
        key = f"{far:#010x}"
        entry = index["entries"].get(key)
        if entry and entry.get("status") == "ok":
            continue
        if max_reads is not None and reads >= max_reads:
            break
        capture_path = out_dir / f"far_{far:08x}.json"
        staging = out_dir / f"far_{far:08x}.json.part"
        child_started = time.time()
        code = runner(far, staging)
        child_elapsed = round(time.time() - child_started, 3)
        reads += 1
        try:
            if code != 0 or not staging.exists():
                raise SearchStop(f"{key}: the child exited {code}")
            capture = json.loads(staging.read_text("utf-8"))
            words = validate_capture(far, capture)
        except SearchStop as stop:
            index["entries"][key] = {"status": "failed", "child_returncode": code,
                                     "elapsed_s": child_elapsed, "reason": str(stop)}
            _atomic_write(index_path, json.dumps(index, indent=2) + "\n")
            # A failed FAR is recorded and then stops the run. It is never skipped: a hole in
            # the coverage would let a later "not found" mean "not looked at".
            raise
        os.replace(staging, capture_path)
        index["entries"][key] = {
            "status": "ok",
            "child_returncode": code,
            # Measured per child, because the cost of a full sweep is 5,144 of these and the
            # only honest estimate is one taken from the board.
            "elapsed_s": child_elapsed,
            "capture": capture_path.name,
            "frame_sha256": capture["frames"][key]["frame_sha256"],
            "idcode": capture.get("idcode"),
            "config_status": capture.get("config_status"),
            "nonzero_words": sum(1 for word in words if word),
        }
        _atomic_write(index_path, json.dumps(index, indent=2) + "\n")

    index["plmark_at_end"] = plmark_reader(port) if plmark_reader else plmark
    if index["plmark_at_end"] != plmark:
        raise SearchStop(
            f"plmark changed from {plmark} to {index['plmark_at_end']}: the board restarted "
            "during the search and every capture after that is from a different PL")
    index["attempted"] = len(index["entries"])
    index["not_attempted"] = [f"{far:#010x}" for far in fars
                              if f"{far:#010x}" not in index["entries"]]
    _atomic_write(index_path, json.dumps(index, indent=2) + "\n")
    # Second line of defence, and the one a "just skip it and carry on" change trips over: a
    # recorded failure is not coverage, whatever the loop above decided to do about it.
    failed = sorted(key for key, entry in index["entries"].items()
                    if entry.get("status") != "ok")
    if failed:
        raise SearchStop(
            f"the search holds failed captures and cannot be read as coverage: {failed}")
    return index


# ----------------------------------------------------------------------------- the verdict
def judge(index: dict, captures: dict[int, list[int]], base: dict[int, list[int]],
          signatures: dict[int, list[int]]) -> dict:
    """The ruled order: is A20 the candidate, is it the base, and only then, search.

    Takes the base frames rather than a run directory, so the decision can be exercised
    against synthetic captures without a bitstream — every branch below has a test.
    """
    verdict: dict = {"intended_far": f"{INTENDED_FAR:#010x}",
                     "signature_fars": [f"{far:#010x}" for far in signatures]}

    intended = captures.get(INTENDED_FAR)
    if intended is None:
        verdict["verdict"] = "INCOMPLETE"
        verdict["reading"] = "the intended FAR was never captured; nothing can be decided"
        return verdict

    verdict["intended_equals_candidate"] = intended == signatures.get(INTENDED_FAR)
    verdict["intended_equals_base"] = intended == base.get(INTENDED_FAR)

    if verdict["intended_equals_candidate"]:
        verdict["verdict"] = "WRITE_LANDED_AT_THE_INTENDED_FAR"
        verdict["reading"] = (
            "The intended frame holds the candidate exactly, so the carrier's write reached "
            "the frame it asked for and the disagreement is on the read side.")
        return verdict
    if not verdict["intended_equals_base"]:
        verdict["verdict"] = "INTENDED_FAR_IS_NEITHER"
        verdict["reading"] = (
            "The intended frame is neither the candidate nor the base. That is a third thing "
            "and it is not covered by the ruled decision order; stop and look at it.")
        return verdict

    found: dict[str, list[str]] = {}
    for signature_far, words in signatures.items():
        hits = [f"{far:#010x}" for far, captured in sorted(captures.items())
                if captured == words]
        found[f"{signature_far:#010x}"] = hits
    verdict["signature_hits"] = found
    searched = len(captures)
    verdict["frames_searched"] = searched
    verdict["frames_not_searched"] = index.get("not_attempted", [])

    any_hit = any(found.values())
    duplicated = {far: hits for far, hits in found.items() if len(hits) > 1}
    if duplicated:
        verdict["verdict"] = "SIGNATURE_AMBIGUOUS"
        verdict["reading"] = (
            f"A signature matched more than one frame ({duplicated}); it does not name a "
            "location and cannot be used as evidence of where the write went.")
    elif any_hit:
        verdict["verdict"] = "WRITE_LANDED_ELSEWHERE"
        verdict["reading"] = (
            "The intended frame holds the base, and a candidate frame was found whole at "
            f"another address: {found}. The write reached the fabric at the wrong FAR.")
    elif verdict["frames_not_searched"]:
        verdict["verdict"] = "NOT_FOUND_INCOMPLETE"
        verdict["reading"] = (
            f"The intended frame holds the base and no signature was found in the "
            f"{searched} frames read, but "
            f"{len(verdict['frames_not_searched'])} frames were never read. "
            "'Not found' here does not mean 'not there'.")
    else:
        verdict["verdict"] = "NOT_FOUND_COMPLETE"
        verdict["reading"] = (
            f"The intended frame holds the base and no candidate frame appears anywhere in "
            f"the {searched} frames of the device sequence. The write did not reach the "
            "fabric as a whole frame anywhere.")
    return verdict


def load_captures(out_dir: Path, index: dict) -> dict[int, list[int]]:
    captures: dict[int, list[int]] = {}
    for key, entry in index.get("entries", {}).items():
        if entry.get("status") != "ok":
            continue
        far = int(key, 16)
        capture = json.loads((out_dir / entry["capture"]).read_text("utf-8"))
        captures[far] = [int(word, 16) for word in capture["frames"][key]["frame"]]
    return captures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", type=Path,
                    default=REPO / "gate_runs/claimb_round1_carrier_2026_08_13_erratum006")
    ap.add_argument("--report", type=Path,
                    default=REPO / "gate_runs/claimb_round1_reachability_2026_08_10"
                                   "/reachability_report.json")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--plmark", required=True,
                    help="the marker the load set; checked before and after the search")
    ap.add_argument("--port", default="/dev/ebaz-uart")
    ap.add_argument("--max-reads", type=int, default=None,
                    help="stop after this many child reads; the rest are recorded as not "
                         "attempted, never as searched")
    ap.add_argument("--judge-only", action="store_true",
                    help="decide from the captures already on disk, touching no hardware")
    args = ap.parse_args()

    started = time.time()
    try:
        fars = frozen_far_sequence(args.run_dir)
        signatures = candidate_signatures(args.run_dir, args.report)
        digest = inputs_digest(args.run_dir, args.report, fars)

        if args.judge_only:
            index = json.loads((args.out_dir / "index.json").read_text("utf-8"))
            if index.get("inputs_digest") != digest:
                raise SearchStop("the captures on disk were taken against different inputs")
        else:
            actual = read_plmark(args.port)
            if actual != args.plmark:
                raise SearchStop(f"plmark is {actual}, expected {args.plmark}")
            index = run_search(fars, args.out_dir, args.plmark, digest, port=args.port,
                               max_reads=args.max_reads)

        verdict = judge(index, load_captures(args.out_dir, index),
                        base_frames(args.run_dir), signatures)
        verdict["inputs_digest"] = digest
        verdict["elapsed_s"] = round(time.time() - started, 1)
        _atomic_write(args.out_dir / "verdict.json", json.dumps(verdict, indent=2) + "\n")
        print(f"{verdict['verdict']}: {verdict['reading']}")
        print(f"  verdict: {args.out_dir / 'verdict.json'}")
        return 0
    except SearchStop as stop:
        print(f"STOP: {stop}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Read reviewed configuration frames, one OpenOCD process per frame.

WHY IT IS SHAPED LIKE THIS
--------------------------
A JTAG readback is trustworthy exactly once per OpenOCD process: measured on 2026-08-15,
where the same frame came back bit-exact as a process's first read and all-zero as its
second, in both orders, and became exact again in a fresh process against the same load. So
the unit of work is a child process that reads **one** FAR. This module never builds a JTAG
packet: `probe_jtag_config_read` owns that path, with its refusals and its IR allowlist.

THE INTENDED FRAME IS READ FIRST; THE INSTRUMENT IS PROVED BEFORE ANY LOCATION
------------------------------------------------------------------------------
`0x00400A20` is always the first child, and what it holds decides how much else is read. But
**no location verdict is emitted before all sixteen positive controls have been read and all
sixteen have come back bit-exact at their own FARs** — including a candidate found at the
intended FAR, which until 2.7.2 skipped the control block entirely and so was the most
consequential verdict here with the least evidence behind it. Non-zero data or a valid-looking
ECC word is not a control. If a read budget leaves controls unmeasured the verdict is
`INSTRUMENT_UNVALIDATED`; if every control was read and any one of them did not reproduce its
known frame it is `INSTRUMENT_INVALID`. Neither may fall through to a location verdict, and
neither starts the sweep.

Requiring 16/16 fails closed in one case worth naming: if the write landed *on* a control
frame, that control cannot reproduce its base and the acquisition answers nothing rather than
locating the write. The per-control observations record expected and observed digests either
way, so such a state is visible in the record — but it is not adjudicated here.

CONTROL-ONLY MEANS EXACTLY THE SIXTEEN CONTROLS
-----------------------------------------------
`--control-only` is the short hardware-gradient diagnostic: it reads every pinned positive
control and no intended or sweep FAR.  Its evidence is mode-bound, so it cannot be resumed
or judged as a location search, and its verdict vocabulary is limited to the three
`INSTRUMENT_*` states.  It records each child's CONFIG_STATUS as an observation, never as a
classifier.

THE AUTHORITY IS NOT AN ARGUMENT
--------------------------------
There is no `--run-dir` and no `--report`. The carrier run must be the one HEAD published
(`carrier_run.head_authority_problems`), and the expected frames come from the reviewed
known-answer artifact, which `KnownAnswerAuthority.load()` binds to its pinned digest, to the
HEAD blob, and to a clean tree. A self-consistent set of files in a directory is not an
authority; an operator who can point the authority elsewhere has none.

WHAT COUNTS AS FINDING SOMETHING
--------------------------------
A whole 101-word frame equal to a whole expected frame. Not a few INIT bits, which the
device's 4,716 all-zero frames would hand out for free, and never an all-zero signature.
"""

from __future__ import annotations

import argparse
import base64
import collections
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
import carrier_run  # noqa: E402
import frame_ecc  # noqa: E402
import gate_claimb_known_answer as kagate  # noqa: E402
import probe_jtag_config_read as probe  # noqa: E402

TOOL_VERSION = "board_signature_search.py/2.8.0"
CHILD = REPO / "scripts/probe_jtag_config_read.py"
CHILD_CFG = REPO / "scripts/jtag_config_only.cfg"
CHILD_SPEED = 2000
CHILD_TOOL_VERSION = "probe_jtag_config_read.py/2.4.0"

CANONICAL_RUN = REPO / kagate.RUN_REL
CANONICAL_REPORT = REPO / kagate.REPORT_REL
INTENDED_FAR = 0x00400A20
EXPECTED_SITE, EXPECTED_BEL = "SLICE_X2Y25", "A6LUT"
IDCODE = "0x13722093"
LUT_FEATURE = re.compile(r"CLBLL_L\.SLICEL_X0\.ALUT\.INIT\[(\d+)\]$")
MODE_SIGNATURE_SEARCH = "signature-search"
MODE_CONTROL_ONLY = "control-only"

# Sixteen controls are deliberate, and since 2.8.0 all sixteen must pass.  They are the
# sixteen frames the four R4 acquisitions read 16/16, so the requirement is the demonstrated
# behaviour of the recovery, not a hope about it: R4 is proven on exactly this set, twice,
# and a location verdict is a far stronger claim than an instrument check.  Anything less
# than 16/16 fails the acquisition closed.  The list is independently derived below, but
# pinned here so a carrier change cannot silently choose easier controls.
POSITIVE_CONTROL_COUNT = 16
EXPECTED_POSITIVE_CONTROL_FARS = (
    0x00000900, 0x00000986, 0x000009A2, 0x00000A8E,
    0x00000B8A, 0x00000C04, 0x00000D04, 0x00400915,
    0x00400996, 0x00400A10, 0x00400B05, 0x00400B91,
    0x00400C0A, 0x00400C8E, 0x00401101, 0x0040139B,
)


class SearchStop(Exception):
    """Anything that makes the next read meaningless, or the record less than complete."""


# ------------------------------------------------------------------------- the authority
def _derive_signatures() -> dict[int, list[int]]:
    """The candidate frames, re-derived from the frozen inputs as a second opinion."""
    manifest = json.loads((CANONICAL_RUN / "phenotype_manifest.json").read_text("utf-8"))
    local_map = json.loads((CANONICAL_RUN / "local_map.json").read_text("utf-8"))
    report = json.loads(CANONICAL_REPORT.read_text("utf-8"))

    entry = report["per_lut"][0]
    if entry["site"] != EXPECTED_SITE or entry["bel"] != EXPECTED_BEL:
        raise SearchStop(
            f"the report's first entry is {entry['site']}/{entry['bel']}, not "
            f"{EXPECTED_SITE}/{EXPECTED_BEL}: the selection is not the reviewed one")

    positions = {}
    for address in local_map["universe"]["addresses"]:
        found = LUT_FEATURE.match(address["feature"])
        if found:
            positions[int(found.group(1))] = (int(address["far"], 16),
                                              address["word"], address["bit"])
    mask = 0
    for position in positions:
        mask |= 1 << position
    init = int(entry["target_truth_table"].split("'h")[1], 16) & mask

    pinned = {int(record["far"], 16): [int(word, 16) for word in record["words"]]
              for record in manifest["frames"]}
    frames = {far: list(words) for far, words in pinned.items()}
    touched = set()
    for position in range(64):
        if (init >> position) & 1:
            far, word, bit = positions[position]
            frames[far][word] |= 1 << bit
            touched.add(far)
    return {far: frame_ecc.update_ecc(frames[far]) for far in sorted(touched)}


def canonical_authority() -> tuple[dict[int, list[int]], dict]:
    """The published run, the reviewed artifact, and the frames they agree on.

    Three independent things have to line up before a single frame is read: the run is the
    one HEAD published, the artifact is the reviewed one bound to its pin and to a clean
    tree, and the frames it names are the frames a fresh derivation from the frozen inputs
    produces. Any of them alone can be forged by arranging a directory; together they cannot.
    """
    problems = carrier_run.head_authority_problems(CANONICAL_RUN)
    if problems:
        raise SearchStop(f"the carrier run is not the one HEAD published: {problems[:2]}")

    known = kagate.KnownAnswerAuthority.load()
    document = known.document

    selection = document["selection"]
    if selection["site"] != EXPECTED_SITE or selection["bel"] != EXPECTED_BEL:
        raise SearchStop(
            f"the artifact selects {selection['site']}/{selection['bel']}, not "
            f"{EXPECTED_SITE}/{EXPECTED_BEL}")
    report = json.loads(CANONICAL_REPORT.read_text("utf-8"))
    chosen = report["per_lut"][selection["report_index"]]
    if chosen["site"] != EXPECTED_SITE or chosen["bel"] != EXPECTED_BEL:
        raise SearchStop(
            f"report entry {selection['report_index']} is {chosen['site']}/{chosen['bel']}: "
            "the artifact's index does not name the reviewed LUT")

    published = {int(frame["far"], 16): [int(word, 16) for word in frame["words"]]
                 for frame in document["candidate"]["touched_frames"]}
    derived = _derive_signatures()
    if published != derived:
        raise SearchStop(
            "the published signature frames and a fresh derivation disagree; one of them is "
            "wrong and neither may be searched for")
    for far, words in published.items():
        if not any(words):
            raise SearchStop(f"the signature for {far:#010x} is all zero and names nothing")
    if INTENDED_FAR not in published:
        raise SearchStop(f"the candidate does not touch {INTENDED_FAR:#010x}")
    return published, document


def frozen_far_sequence() -> list[int]:
    """Every FAR of the published bitstream, in address order. The only admissible set."""
    return sorted(bf.parse_frames(CANONICAL_RUN / "carrier.bit")["frames"])


def base_frames() -> dict[int, list[int]]:
    return {far: list(words)
            for far, words in bf.parse_frames(CANONICAL_RUN / "carrier.bit")["frames"].items()}


def canonical_positive_controls(base: dict[int, list[int]]) -> dict[int, list[int]]:
    """Sixteen distributed, unique, non-zero base frames outside the transaction.

    A merely non-zero or ECC-consistent read is not a positive control: the invalid Phase 2
    capture contained 4,292 non-zero frames and 82 of those were ECC-consistent.  A control
    passes only when all 101 words equal the known non-zero base frame at the same FAR.

    Candidate and guard frames are excluded using the frozen manifest.  Among the remaining
    base frames, only content unique in the device is eligible, so a misaddressed read cannot
    pass by landing on a duplicate.  Sixteen evenly spaced ranks cover the eligible sequence;
    their resulting FARs are pinned above and must be reviewed when authority changes.
    """
    manifest = json.loads((CANONICAL_RUN / "phenotype_manifest.json").read_text("utf-8"))
    excluded = {int(record["far"], 16) for record in manifest["frames"]}
    counts = collections.Counter(tuple(words) for words in base.values())
    eligible = [far for far in sorted(base)
                if any(base[far]) and counts[tuple(base[far])] == 1 and far not in excluded]
    if len(eligible) < POSITIVE_CONTROL_COUNT:
        raise SearchStop(
            f"only {len(eligible)} unique non-zero base frames remain outside the transaction; "
            f"{POSITIVE_CONTROL_COUNT} positive controls are required")
    ranks = [round(i * (len(eligible) - 1) / (POSITIVE_CONTROL_COUNT - 1))
             for i in range(POSITIVE_CONTROL_COUNT)]
    selected = tuple(eligible[rank] for rank in ranks)
    if selected != EXPECTED_POSITIVE_CONTROL_FARS:
        raise SearchStop(
            "the authority-derived positive-control FARs changed; review and re-pin them "
            f"instead of silently accepting {tuple(f'{far:#010x}' for far in selected)}")
    return {far: list(base[far]) for far in selected}


def instrument_digest(fars: list[int], mode: str = MODE_SIGNATURE_SEARCH) -> str:
    """Everything a later capture must still have been taken with.

    The inputs alone are not enough: two different readback tools, or a different JTAG
    config, or a different adapter speed produce captures that must never be mixed into one
    search. A resume that cannot see the instrument change would splice them silently.
    """
    if mode not in (MODE_SIGNATURE_SEARCH, MODE_CONTROL_ONLY):
        raise SearchStop(f"unknown acquisition mode {mode!r}")
    parts = [TOOL_VERSION, CHILD_TOOL_VERSION, str(CHILD_SPEED), f"mode:{mode}"]
    for path in (Path(__file__), CHILD, CHILD_CFG,
                 CANONICAL_RUN / "carrier.bit",
                 CANONICAL_RUN / "phenotype_manifest.json",
                 CANONICAL_RUN / "local_map.json",
                 CANONICAL_REPORT, kagate.ARTIFACT):
        parts.append(f"{path.name}:{hashlib.sha256(path.read_bytes()).hexdigest()}")
    parts.append("fars:" + hashlib.sha256(
        ",".join(f"{far:08x}" for far in fars).encode()).hexdigest())
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


# ------------------------------------------------------------------------------ the board
def read_plmark(port: str) -> str:
    """The loader's marker, over the PS UART only. No AXI, no `md`, no writes."""
    with __import__("serial").Serial(port, bs.BAUD, timeout=0.1) as ser:
        sync = bs.ub_cmd(ser, bs.SYNC_COMMAND, 3.0)
        reply = bs.ub_cmd(ser, "printenv plmark", 3.0)
    if bs.BOOT_BANNER_RE.search(sync + reply):
        raise SearchStop("a boot banner came back: the PL is not the one that was loaded")
    found = re.search(rb"plmark=([0-9a-f]+)", reply)
    if not found:
        raise SearchStop(f"plmark is not set: {reply[-120:]!r}")
    return found.group(1).decode("ascii")


def check_child_argv(argv: list[str]) -> None:
    """Exactly one FAR per child. The measurement says a process is good for one read."""
    if argv.count("--far") != 1:
        raise SearchStop(
            f"a child must be given exactly one --far, got {argv.count('--far')}: {argv}")


def child_argv(far: int, out_path: Path) -> list[str]:
    argv = [sys.executable, str(CHILD), "--far", f"{far:#010x}", "--out", str(out_path),
            "--cfg", str(CHILD_CFG), "--speed", str(CHILD_SPEED)]
    check_child_argv(argv)
    return argv


def subprocess_runner(far: int, out_path: Path, timeout: float = 600) -> dict:
    argv = child_argv(far, out_path)
    done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    # The whole argv, not a summary: it is later compared against the argv this module would
    # build for that FAR, which is how a capture proves it came from the reviewed child.
    return {"returncode": done.returncode, "argv": argv,
            "stdout": done.stdout, "stderr": done.stderr}


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


def _digest_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stream_evidence(value) -> dict:
    """A subprocess exception's partial stream, preserved byte-for-byte.

    `TimeoutExpired.output` and `.stderr` may be bytes even when the original run requested
    text mode.  A replacement-decoded string is useful to a reader, but it is not evidence;
    the base64 and digest are the lossless record.
    """
    if value is None:
        raw = b""
    elif isinstance(value, bytes):
        raw = value
    else:
        raw = str(value).encode("utf-8")
    return {
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "base64": base64.b64encode(raw).decode("ascii"),
        "text": raw.decode("utf-8", errors="replace"),
    }


def frame_of(far: int, capture: dict) -> list[int]:
    """The 101 words a capture holds for this FAR, or a refusal saying why it does not."""
    if capture.get("verdict") != "READ":
        raise SearchStop(f"{far:#010x}: the child did not read ({capture.get('stop_reason')})")
    if capture.get("tool") != CHILD_TOOL_VERSION:
        raise SearchStop(f"{far:#010x}: taken with {capture.get('tool')}, not {CHILD_TOOL_VERSION}")
    if capture.get("idcode") != IDCODE:
        raise SearchStop(f"{far:#010x}: IDCODE {capture.get('idcode')}")
    frames = capture.get("frames", {})
    if list(frames) != [f"{far:#010x}"]:
        raise SearchStop(f"{far:#010x}: the capture holds {list(frames)}")
    words = [int(word, 16) for word in frames[f"{far:#010x}"]["frame"]]
    if len(words) != probe.FRAME_WORDS:
        raise SearchStop(f"{far:#010x}: {len(words)} words, expected {probe.FRAME_WORDS}")
    body = b"".join(word.to_bytes(4, "big") for word in words)
    if hashlib.sha256(body).hexdigest() != frames[f"{far:#010x}"]["frame_sha256"]:
        raise SearchStop(f"{far:#010x}: the capture's own frame digest does not match its words")
    return words


def config_status_of(far: int, capture: dict) -> str:
    """The configuration status the child observed, normalised for the index summary."""
    value = capture.get("config_status")
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-fA-F]{8}", value):
        raise SearchStop(f"{far:#010x}: missing or malformed CONFIG_STATUS {value!r}")
    return value.lower()


def _inside(out_dir: Path, name: str, key: str) -> Path:
    """A recorded file name may only ever be a file in the output directory."""
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise SearchStop(f"{key}: {name!r} is not a plain file name in the run directory")
    path = (out_dir / name).resolve()
    if path.parent != out_dir.resolve():
        raise SearchStop(f"{key}: {name!r} resolves outside the run directory")
    return path


def _check_child_log(out_dir: Path, far: int, entry: dict, key: str) -> None:
    """The child's own record has to be there, unaltered, and be the reviewed invocation."""
    path = _inside(out_dir, entry.get("child_log", ""), key)
    if not path.exists():
        raise SearchStop(f"{key}: the child log is gone")
    if _digest_of(path) != entry.get("child_log_sha256"):
        raise SearchStop(f"{key}: the child log has changed since it was written")
    log = json.loads(path.read_text("utf-8"))
    if log.get("returncode") != 0:
        raise SearchStop(f"{key}: the child exited {log.get('returncode')}")
    expected = child_argv(far, out_dir / f"far_{far:08x}.json.part")
    if log.get("argv") != expected:
        raise SearchStop(f"{key}: the capture was taken by a different invocation: {log.get('argv')}")


def validate_index(out_dir: Path, index: dict, digest: str, plmark: str,
                   fars: list[int], controls: dict[int, list[int]],
                   mode: str = MODE_SIGNATURE_SEARCH) -> tuple[dict[int, list[int]], list[str]]:
    """The one gate every path goes through: live, resumed and judge-only alike.

    Re-reads and re-hashes every capture rather than believing the index about it. An index
    is a claim; the captures are the evidence, and an evidence file that has been edited,
    truncated or swapped since it was written must not reach a verdict through a status
    field that still says "ok".

    It also **recomputes what is missing** from the frozen FAR set against the captures that
    survived validation, and returns that. The index's own `not_attempted` is never read: a
    run interrupted after a capture landed but before the closing write leaves an index that
    is entirely self-consistent and silent about the 5,143 frames nobody looked at, and
    trusting it turns one read into a complete search.
    """
    if index.get("tool") != TOOL_VERSION:
        raise SearchStop(f"the index was written by {index.get('tool')}, not {TOOL_VERSION}")
    if index.get("mode") != mode:
        raise SearchStop(
            f"the index mode is {index.get('mode')!r}, not {mode!r}; control-only and "
            "location-search evidence are not interchangeable")
    if index.get("instrument_digest") != digest:
        raise SearchStop("the captures were taken with a different instrument or inputs")
    if index.get("plmark_at_start") != plmark:
        raise SearchStop("the captures are from a different boot")
    expected_controls = [f"{far:#010x}" for far in controls]
    if index.get("positive_control_fars") != expected_controls:
        raise SearchStop(
            "the index was opened with a different positive-control set; it cannot prove "
            "this instrument")
    failed = sorted(key for key, entry in index.get("entries", {}).items()
                    if entry.get("status") != "ok")
    if failed:
        raise SearchStop(f"the search holds failed captures and is not coverage: {failed}")

    admissible = set(fars)
    captures: dict[int, list[int]] = {}
    for key, entry in index.get("entries", {}).items():
        # Only entries that claim success are validated here; the refusal above is what
        # stands between a failure and a verdict, and it is not optional on any path.
        if entry.get("status") != "ok":
            continue
        far = int(key, 16)
        if far not in admissible:
            raise SearchStop(f"{key} is not in the frozen device frame sequence")
        path = _inside(out_dir, entry.get("capture", ""), key)
        if not path.exists():
            raise SearchStop(f"{key}: the capture file is gone")
        if _digest_of(path) != entry.get("capture_sha256"):
            raise SearchStop(f"{key}: the capture file has changed since it was written")
        _check_child_log(out_dir, far, entry, key)
        capture = json.loads(path.read_text("utf-8"))
        words = frame_of(far, capture)
        config_status = config_status_of(far, capture)
        if entry.get("config_status") != config_status:
            raise SearchStop(
                f"{key}: CONFIG_STATUS in the index does not match the capture")
        body = b"".join(word.to_bytes(4, "big") for word in words)
        if hashlib.sha256(body).hexdigest() != entry.get("frame_sha256"):
            raise SearchStop(f"{key}: the frame does not match the digest the index recorded")
        captures[far] = words

    missing = [f"{far:#010x}" for far in fars if far not in captures]
    return captures, missing


def capture_one(far: int, out_dir: Path, index: dict, runner) -> list[int]:
    """One child, one FAR, and every byte of it kept — including when it fails."""
    key = f"{far:#010x}"
    capture_path = out_dir / f"far_{far:08x}.json"
    staging = out_dir / f"far_{far:08x}.json.part"
    index_path = out_dir / "index.json"

    child_path = out_dir / f"far_{far:08x}.child.json"
    frozen_argv = child_argv(far, staging)
    started = time.time()

    def fail(reason: str, result: dict) -> None:
        """Whatever went wrong, the evidence lands before the exception leaves."""
        _atomic_write(child_path, json.dumps(result, indent=2) + "\n")
        entry = {"status": "failed", "child_returncode": result.get("returncode"),
                 "elapsed_s": round(time.time() - started, 3), "child_log": child_path.name,
                 "child_log_sha256": _digest_of(child_path), "reason": reason}
        if staging.exists():
            partial = out_dir / f"far_{far:08x}.partial.json"
            os.replace(staging, partial)
            entry["partial"] = partial.name
            entry["partial_sha256"] = _digest_of(partial)
        index["entries"][key] = entry
        _atomic_write(index_path, json.dumps(index, indent=2) + "\n")
        # Recorded, then stopped. A hole in the coverage would let a later "not found" mean
        # "not looked at", so the search never continues past one.
        raise SearchStop(reason)

    try:
        result = runner(far, staging)
    except Exception as raised:
        # A timeout, a killed child, an OSError. Before this, such a run left no stdout, no
        # index entry and no partial capture at all — the failure mode with the least
        # evidence was the one that produced none.
        partial_stdout = getattr(raised, "stdout", None)
        if partial_stdout is None:
            partial_stdout = getattr(raised, "output", None)
        partial_stderr = getattr(raised, "stderr", None)
        streams = {"stdout": _stream_evidence(partial_stdout),
                   "stderr": _stream_evidence(partial_stderr)}
        fail(f"{key}: the child raised {type(raised).__name__}: {raised}",
             {"returncode": None, "argv": frozen_argv,
              "stdout": streams["stdout"]["text"], "stderr": streams["stderr"]["text"],
              "exception_streams": streams,
              "exception": f"{type(raised).__name__}: {raised}"})
    elapsed = round(time.time() - started, 3)
    result.setdefault("argv", frozen_argv)

    try:
        if result.get("returncode") != 0:
            raise SearchStop(f"{key}: the child exited {result.get('returncode')}")
        if not staging.exists():
            raise SearchStop(f"{key}: the child wrote no capture")
        capture = json.loads(staging.read_text("utf-8"))
        words = frame_of(far, capture)
        config_status = config_status_of(far, capture)
    except SearchStop as stop:
        fail(str(stop), result)
    except Exception as raised:
        # Malformed JSON, a missing key, a bad integer: the capture is unusable and the
        # reason is worth keeping in the same shape as every other failure.
        fail(f"{key}: the capture could not be read: {type(raised).__name__}: {raised}",
             result)
    else:
        _atomic_write(child_path, json.dumps(result, indent=2) + "\n")

    os.replace(staging, capture_path)
    body = b"".join(word.to_bytes(4, "big") for word in words)
    index["entries"][key] = {
        "status": "ok",
        "child_returncode": result.get("returncode"),
        "elapsed_s": elapsed,
        "capture": capture_path.name,
        "capture_sha256": _digest_of(capture_path),
        "frame_sha256": hashlib.sha256(body).hexdigest(),
        "child_log": child_path.name,
        "child_log_sha256": _digest_of(child_path),
        "nonzero_words": sum(1 for word in words if word),
        "config_status": config_status,
    }
    _atomic_write(index_path, json.dumps(index, indent=2) + "\n")
    return words


def require_closed(index: dict) -> None:
    """An index its own run never closed may be resumed, but it may not be judged.

    The closing write is where a run says the board was still the same board at the end. An
    index without it is the shape an interrupted run leaves — self-consistent, and silent
    about everything that never happened.
    """
    if index.get("plmark_at_end") != index.get("plmark_at_start"):
        raise SearchStop(
            "this index was never closed by its own run (no matching plmark_at_end); "
            "resume it, do not judge it")


def open_index(out_dir: Path, digest: str, plmark: str, fars: list[int],
               controls: dict[int, list[int]],
               mode: str = MODE_SIGNATURE_SEARCH) -> tuple[dict, dict[int, list[int]]]:
    """A fresh index, or a resumed one that has re-earned every capture it claims."""
    index_path = out_dir / "index.json"
    if not index_path.exists():
        return ({"tool": TOOL_VERSION, "mode": mode, "instrument_digest": digest,
                 "plmark_at_start": plmark,
                 "positive_control_fars": [f"{far:#010x}" for far in controls],
                 "entries": {}}, {})
    index = json.loads(index_path.read_text("utf-8"))
    captures, _ = validate_index(out_dir, index, digest, plmark, fars, controls, mode)
    index.setdefault("entries", {})
    return index, captures


def begin_invocation(out_dir: Path, index: dict) -> None:
    """Invalidate any older closure before this invocation can land a new capture."""
    index.pop("plmark_at_end", None)
    _atomic_write(out_dir / "index.json", json.dumps(index, indent=2) + "\n")


def close_invocation(out_dir: Path, index: dict, plmark: str, port: str,
                     plmark_reader, digest: str, fars: list[int],
                     controls: dict[int, list[int]], mode: str) -> None:
    """Land this invocation's end marker, reject a restart, and revalidate everything."""
    index["plmark_at_end"] = plmark_reader(port) if plmark_reader else plmark
    # The observation reaches disk before the comparison.  A reboot is evidence, and an old
    # matching closure must never reappear when the new invocation refuses.
    _atomic_write(out_dir / "index.json", json.dumps(index, indent=2) + "\n")
    if index["plmark_at_end"] != plmark:
        raise SearchStop(
            f"plmark changed from {plmark} to {index['plmark_at_end']}: the board restarted "
            "during the acquisition and every later capture is from a different PL")
    validate_index(out_dir, index, digest, plmark, fars, controls, mode)


def validate_control_inputs(base: dict[int, list[int]], fars: list[int],
                            controls: dict[int, list[int]],
                            signatures: dict[int, list[int]] | None = None) -> None:
    """The reviewed controls are same-FAR base frames inside the admitted sequence."""
    if set(controls) - set(fars):
        raise SearchStop("a positive-control FAR is outside the admitted frame sequence")
    if signatures is not None and set(controls) & set(signatures):
        raise SearchStop("candidate signature FARs cannot double as independent controls")
    if any(base.get(far) != words for far, words in controls.items()):
        raise SearchStop("positive controls must be the base frames at those same FARs")
    # This also enforces count, non-zero content, uniqueness and exclusion of intended FAR.
    judge_positive_controls({}, controls)


# ----------------------------------------------------------------------------- the verdict
def decide_intended(words: list[int], signatures: dict[int, list[int]],
                    base: dict[int, list[int]]) -> dict:
    """What the first frame says on its own, before anything else is read."""
    if words == signatures.get(INTENDED_FAR):
        return {"verdict": "WRITE_LANDED_AT_THE_INTENDED_FAR", "sweep_needed": False,
                "reading": "The intended frame holds the candidate exactly, so the write "
                           "reached the frame it asked for and the disagreement is on the "
                           "read side."}
    if words != base.get(INTENDED_FAR):
        return {"verdict": "INTENDED_FAR_IS_NEITHER", "sweep_needed": False,
                "reading": "The intended frame is neither the candidate nor the base. That "
                           "is a third thing, outside the ruled decision order; stop and "
                           "look at it."}
    return {"verdict": "INTENDED_FAR_HOLDS_THE_BASE", "sweep_needed": True,
            "reading": "The intended frame holds the base, so where the write went is now "
                       "an open question and the sweep is the way to ask it."}


def judge_positive_controls(captures: dict[int, list[int]],
                            controls: dict[int, list[int]]) -> dict:
    """Prove the post-fault instrument before allowing a location verdict.

    **All sixteen must be read and all sixteen must match** (2.8.0).  Until 2.7.2 one exact
    frame was declared sufficient and the accepting branch never looked at `missing`, so one
    hit plus fifteen mismatches passed, and so did one hit plus fifteen frames nobody read.
    That threshold was set for a hardware-gradient diagnostic, where the question is whether
    the readback path returns anything at all; it is far too weak to license a statement about
    *where* a write landed.  R4 is demonstrated at 16/16 on exactly this set, twice, so 16/16
    is what the instrument is known to do when it is working.

    Non-zero, ECC-consistent, masked, partial and relocated matches do not count.  They are
    observations, not this positive control.
    """
    if len(controls) != POSITIVE_CONTROL_COUNT:
        raise SearchStop(
            f"the positive-control set has {len(controls)} frames, expected "
            f"{POSITIVE_CONTROL_COUNT}")
    if INTENDED_FAR in controls:
        raise SearchStop("the intended FAR cannot double as an independent positive control")
    if any(not any(words) for words in controls.values()):
        raise SearchStop("an all-zero frame cannot be a positive control")
    if len({tuple(words) for words in controls.values()}) != len(controls):
        raise SearchStop("positive controls must have unique whole-frame contents")

    observations = []
    matched = []
    missing = []
    for far, expected in controls.items():
        words = captures.get(far)
        if words is None:
            missing.append(f"{far:#010x}")
            continue
        exact = words == expected
        if exact:
            matched.append(f"{far:#010x}")
        observations.append({
            "far": f"{far:#010x}",
            "exact_same_far_base_match": exact,
            "expected_nonzero_words": sum(1 for word in expected if word),
            "observed_nonzero_words": sum(1 for word in words if word),
            "expected_sha256": hashlib.sha256(
                b"".join(word.to_bytes(4, "big") for word in expected)).hexdigest(),
            "observed_sha256": hashlib.sha256(
                b"".join(word.to_bytes(4, "big") for word in words)).hexdigest(),
        })

    common = {"positive_controls": observations,
              "positive_control_matches": matched,
              "positive_controls_not_read": missing}
    # An unread control is judged before a mismatching one on purpose: it is the weaker claim
    # about the acquisition and the honest one.  "Some controls failed" would be asserted
    # partly about frames nobody looked at.
    if missing:
        return {**common, "verdict": "INSTRUMENT_UNVALIDATED",
                "reading": f"{len(matched)} of {len(controls)} preselected controls came back "
                           f"bit-exact and {len(missing)} were not read at all. All "
                           f"{len(controls)} must be read and match. No location verdict is "
                           "allowed."}
    if len(matched) == len(controls):
        return {**common, "verdict": "INSTRUMENT_VALID",
                "reading": f"All {len(controls)} preselected unique non-zero base frames came "
                           "back bit-exact at their own FARs in this acquisition."}
    return {**common, "verdict": "INSTRUMENT_INVALID",
            "reading": f"All {len(controls)} preselected controls were read and "
                       f"{len(controls) - len(matched)} did not reproduce the known non-zero "
                       "base frame at the same FAR. The captures cannot support a location "
                       "verdict."}


def require_control_only_verdict(verdict: dict) -> None:
    """A control acquisition has no vocabulary for location, even through a future edit."""
    allowed = {"INSTRUMENT_VALID", "INSTRUMENT_INVALID", "INSTRUMENT_UNVALIDATED"}
    if verdict.get("verdict") not in allowed:
        raise SearchStop(
            f"control-only produced forbidden verdict {verdict.get('verdict')!r}")
    forbidden_keys = {"signature_hits", "intended_far", "signature_fars",
                      "frames_searched", "frames_not_searched"}
    present = sorted(forbidden_keys & set(verdict))
    if present:
        raise SearchStop(f"control-only produced location fields: {present}")


def judge_sweep(index: dict, captures: dict[int, list[int]], not_attempted: list[str],
                signatures: dict[int, list[int]], controls: dict[int, list[int]]) -> dict:
    """Where, if anywhere, a whole candidate frame appears in what was read."""
    control = judge_positive_controls(captures, controls)
    if control["verdict"] != "INSTRUMENT_VALID":
        return control
    found = {f"{signature_far:#010x}": [f"{far:#010x}" for far, words in sorted(captures.items())
                                        if words == signature]
             for signature_far, signature in signatures.items()}
    verdict = {"signature_hits": found, "frames_searched": len(captures),
               "frames_not_searched": not_attempted,
               "positive_controls": control["positive_controls"],
               "positive_control_matches": control["positive_control_matches"]}
    duplicated = {far: hits for far, hits in found.items() if len(hits) > 1}
    if duplicated:
        verdict["verdict"] = "SIGNATURE_AMBIGUOUS"
        verdict["reading"] = (
            f"A signature matched more than one frame ({duplicated}); it names no location "
            "and cannot be evidence of where the write went.")
    elif any(found.values()):
        verdict["verdict"] = "WRITE_LANDED_ELSEWHERE"
        verdict["reading"] = (
            f"A candidate frame was found whole at another address: {found}. The write "
            "reached the fabric at the wrong FAR.")
    elif not_attempted:
        verdict["verdict"] = "NOT_FOUND_INCOMPLETE"
        verdict["reading"] = (
            f"No signature in the {len(captures)} frames read, but {len(not_attempted)} were "
            "never read. 'Not found' here does not mean 'not there'.")
    else:
        verdict["verdict"] = "NOT_FOUND_COMPLETE"
        verdict["reading"] = (
            f"No candidate frame appears anywhere in the {len(captures)} frames of the "
            "device sequence. The write did not reach the fabric as a whole frame anywhere.")
    return verdict


# -------------------------------------------------------------------------------- the run
def run(out_dir: Path, plmark: str, signatures: dict[int, list[int]],
        base: dict[int, list[int]], fars: list[int], digest: str,
        controls: dict[int, list[int]], runner=subprocess_runner,
        port: str = "/dev/ebaz-uart", max_reads: int | None = None,
        plmark_reader=read_plmark) -> dict:
    """Intended frame, fail-closed controls, then (only if justified) the sweep."""
    validate_control_inputs(base, fars, controls, signatures)
    index, captures = open_index(
        out_dir, digest, plmark, fars, controls, MODE_SIGNATURE_SEARCH)

    # A closure belongs to one invocation, not to the directory forever.  Invalidate an old
    # one on disk before this invocation can add a capture; otherwise a reboot during a
    # resume leaves the new captures wearing the previous invocation's matching end marker.
    begin_invocation(out_dir, index)

    if INTENDED_FAR not in captures:
        captures[INTENDED_FAR] = capture_one(INTENDED_FAR, out_dir, index, runner)
    decision = decide_intended(captures[INTENDED_FAR], signatures, base)
    verdict = dict(decision)

    # 2.8.0: the controls are read in every case, and they are read in full.  Until 2.7.2 a
    # candidate at A20 skipped this block outright — its bit-exactness was treated as its own
    # proof — and the other two cases stopped at the first matching control.  A hit at the
    # intended FAR is a location claim like any other and now pays the same sixteen reads;
    # what it costs is sixteen frames of exposure, what it buys is a verdict with an
    # instrument behind it.
    reads = 0
    for far in controls:
        if far in captures:
            continue
        if max_reads is not None and reads >= max_reads:
            break
        captures[far] = capture_one(far, out_dir, index, runner)
        reads += 1

    control = judge_positive_controls(captures, controls)
    if control["verdict"] != "INSTRUMENT_VALID":
        # No location verdict, and the sweep does not start.  This is the whole point of the
        # ordering: an acquisition that cannot prove its instrument answers nothing, and it
        # must not spend 5,144 more reads finding that out.
        verdict = control
    else:
        verdict.update({"positive_controls": control["positive_controls"],
                        "positive_control_matches": control["positive_control_matches"]})
        if decision["sweep_needed"]:
            for far in fars:
                if far in captures:
                    continue
                if max_reads is not None and reads >= max_reads:
                    break
                captures[far] = capture_one(far, out_dir, index, runner)
                reads += 1
            # Recomputed from the frozen set against what actually validated, never taken from
            # the index: an interrupted run leaves a self-consistent index that is silent about
            # every frame nobody looked at.
            _, missing = validate_index(
                out_dir, index, digest, plmark, fars, controls, MODE_SIGNATURE_SEARCH)
            verdict = judge_sweep(index, captures, missing, signatures, controls)

    index["not_attempted"] = verdict.get("frames_not_searched", [
        f"{far:#010x}" for far in fars if far not in captures])
    close_invocation(out_dir, index, plmark, port, plmark_reader, digest, fars, controls,
                     MODE_SIGNATURE_SEARCH)
    verdict["intended_far"] = f"{INTENDED_FAR:#010x}"
    verdict["signature_fars"] = [f"{far:#010x}" for far in signatures]
    return verdict


def run_control_only(out_dir: Path, plmark: str, base: dict[int, list[int]], digest: str,
                     controls: dict[int, list[int]], runner=subprocess_runner,
                     port: str = "/dev/ebaz-uart", plmark_reader=read_plmark) -> dict:
    """Read exactly the pinned controls; never inspect or state a candidate location."""
    control_fars = list(controls)
    validate_control_inputs(base, control_fars, controls)
    index, captures = open_index(
        out_dir, digest, plmark, control_fars, controls, MODE_CONTROL_ONLY)
    begin_invocation(out_dir, index)

    for far in controls:
        if far in captures:
            continue
        captures[far] = capture_one(far, out_dir, index, runner)

    verdict = judge_positive_controls(captures, controls)
    require_control_only_verdict(verdict)
    index["not_attempted"] = [f"{far:#010x}" for far in controls if far not in captures]
    close_invocation(out_dir, index, plmark, port, plmark_reader, digest, control_fars,
                     controls, MODE_CONTROL_ONLY)
    return verdict


def judge_control_only_index(out_dir: Path, plmark: str, digest: str,
                             controls: dict[int, list[int]]) -> dict:
    """Offline verdict for a closed control-only acquisition, with no location path."""
    index = json.loads((out_dir / "index.json").read_text("utf-8"))
    control_fars = list(controls)
    captures, _ = validate_index(
        out_dir, index, digest, plmark, control_fars, controls, MODE_CONTROL_ONLY)
    require_closed(index)
    verdict = judge_positive_controls(captures, controls)
    require_control_only_verdict(verdict)
    return verdict


def judge_signature_search_index(out_dir: Path, plmark: str, digest: str,
                                 signatures: dict[int, list[int]],
                                 base: dict[int, list[int]], fars: list[int],
                                 controls: dict[int, list[int]]) -> dict:
    """Offline verdict for a closed location-search acquisition."""
    index = json.loads((out_dir / "index.json").read_text("utf-8"))
    captures, missing = validate_index(
        out_dir, index, digest, plmark, fars, controls, MODE_SIGNATURE_SEARCH)
    require_closed(index)
    if INTENDED_FAR not in captures:
        raise SearchStop("the intended FAR was never captured; nothing is decided")
    decision = decide_intended(captures[INTENDED_FAR], signatures, base)
    verdict = dict(decision)
    # The same rule as the live run, deliberately duplicated rather than shared: judging is
    # the path that re-reads published evidence, and an intended hit that skipped the controls
    # here would re-license offline exactly the verdict 2.8.0 stopped licensing on the board.
    control = judge_positive_controls(captures, controls)
    if control["verdict"] != "INSTRUMENT_VALID":
        verdict = control
    else:
        verdict.update({"positive_controls": control["positive_controls"],
                        "positive_control_matches": control["positive_control_matches"]})
        if decision["sweep_needed"]:
            verdict = judge_sweep(index, captures, missing, signatures, controls)
    verdict["intended_far"] = f"{INTENDED_FAR:#010x}"
    verdict["signature_fars"] = [f"{far:#010x}" for far in signatures]
    return verdict


def validate_mode_options(control_only: bool, max_reads: int | None) -> None:
    """The diagnostic's production surface cannot request a partial control set."""
    if control_only and max_reads is not None:
        raise SearchStop(
            "--max-reads is not available with --control-only: that mode must read exactly "
            "the sixteen pinned controls")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # Logistics only. There is no --run-dir and no --report: see canonical_authority().
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--plmark", required=True,
                    help="the marker the load set; checked before and after the search")
    ap.add_argument("--port", default="/dev/ebaz-uart")
    ap.add_argument("--control-only", action="store_true",
                    help="read exactly the sixteen pinned controls and emit no location "
                         "verdict")
    ap.add_argument("--max-reads", type=int, default=None,
                    help="cap child reads for an intentionally incomplete acquisition; "
                         "unread controls remain unvalidated, never successful")
    ap.add_argument("--judge-only", action="store_true",
                    help="decide from the captures already on disk, touching no hardware")
    args = ap.parse_args()

    started = time.time()
    try:
        validate_mode_options(args.control_only, args.max_reads)
        signatures, document = canonical_authority()
        fars = frozen_far_sequence()
        base = base_frames()
        controls = canonical_positive_controls(base)
        mode = MODE_CONTROL_ONLY if args.control_only else MODE_SIGNATURE_SEARCH
        admitted_fars = list(controls) if args.control_only else fars
        digest = instrument_digest(admitted_fars, mode)

        if args.judge_only:
            if args.control_only:
                verdict = judge_control_only_index(
                    args.out_dir, args.plmark, digest, controls)
            else:
                verdict = judge_signature_search_index(
                    args.out_dir, args.plmark, digest, signatures, base, fars, controls)
        else:
            actual = read_plmark(args.port)
            if actual != args.plmark:
                raise SearchStop(f"plmark is {actual}, expected {args.plmark}")
            if args.control_only:
                verdict = run_control_only(
                    args.out_dir, args.plmark, base, digest, controls, port=args.port)
            else:
                verdict = run(
                    args.out_dir, args.plmark, signatures, base, fars, digest, controls,
                    port=args.port, max_reads=args.max_reads)

        verdict["instrument_digest"] = digest
        verdict["known_answer_artifact_sha256"] = kagate.PRODUCTION_ARTIFACT_SHA256
        verdict["elapsed_s"] = round(time.time() - started, 1)
        if args.judge_only:
            # 2.7.2. Judging used to write verdict.json like an acquisition does, which meant
            # re-judging a PUBLISHED acquisition silently replaced its `elapsed_s` — the
            # acquisition's own timing — with however long the judging took. That happened to
            # the step ③ evidence (1.9 -> 0.4) and was caught only because the authority gate
            # then refused the next acquisition for a dirty tree. A judgement is a reading of
            # evidence, so it goes to stdout and the evidence is not touched.
            print(json.dumps(verdict, indent=2))
            print(f"{verdict['verdict']}: {verdict['reading']}")
            print("  judged read-only; no file in the acquisition directory was written")
            return 0
        _atomic_write(args.out_dir / "verdict.json", json.dumps(verdict, indent=2) + "\n")
        print(f"{verdict['verdict']}: {verdict['reading']}")
        print(f"  verdict: {args.out_dir / 'verdict.json'}")
        return 0
    except SearchStop as stop:
        print(f"STOP: {stop}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

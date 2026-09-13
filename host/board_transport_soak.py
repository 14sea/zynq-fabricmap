#!/usr/bin/env python3
"""A U-Boot repeated-read consistency control on 17A6 (B1Q transport line, host-only).

WHAT THIS MEASURES, and nothing more: whether repeating one identical `md.l` command at the
board's U-Boot prompt returns a **byte-identical response** each time, under stated conditions,
over a stated exposure. The unit is one RESPONSE; a response that is not byte-identical to the
reference response is one MISMATCH.

WHAT A MISMATCH MEANS: **the cause is unknown.** It may be corruption on the console transport,
a change in the source memory being read, or a command that did not execute as issued. This
tool cannot separate them, and it does not try. The first response is a REFERENCE OBSERVATION,
not independently known transmitted bytes and not proof that the window is stable; a corruption
identical in every response — the reference included — is invisible to this design by
construction. These are declared limitations, not caveats to be read past.

WHAT IT DOES NOT ESTABLISH (the owner's review of 2026-09-13, P2-1): it is **not** a bound on
B2Q's frame loss and **not** a prediction that a B2Q session would fail. A mismatched response
here is not a lost rel-v4 frame there: one response holds many lines, any number of changed
bytes in it still counts as one mismatch, and this loop sends the next command only after the
previous prompt, so it does not reproduce the sustained host-TX-during-frame-RX pattern under
investigation. The earlier claim that a clean B1Q run's two CRC drops imply ~3.6 drops in a
543-frame B2Q session is **WITHDRAWN**: those two drops are the forced SIGNREQ and REC controls
that `b2_runner` enables in every qualification plan (`rec_control=True, sign_control=True`),
fixed session events, not a random rate that scales with frame count. Controls, real CRC drops,
fragments and retransmissions are different things and stay separate. The frozen CRC budget is
not touched by anything here.

It qualifies nothing, attributes nothing, lifts no stop-loss and authorises no session (plan
§5, §6). Its exit code is the tool's state, not a verdict. Running it needs the board powered,
the wiring returned to J7, and the owner's ruling; this file is host-only and proved offline
against a fake U-Boot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
# Only the transport primitives are reused; the acquisition and finalisation control flow is
# this tool's own and must satisfy the same contract the rig's entry point does — importing the
# helpers did NOT import that contract (the owner's P2-3).
from transport_rig import (  # noqa: E402
    Port, serial_port, read_icounters, counter_delta, claim_destination, _write_evidence,
    device_identity, identity_matches,
)
import transport_rig as _rig  # noqa: E402  — hashed as a declared dependency, never as this tool

# ---------------------------------------------------------------- the response grammar
# U-Boot's `print_buffer`/`hexdump_line`: "%08lx:" then " %08lx" per word, then padding to the
# full line width, then two spaces and the ASCII column, then '\n' (the console adds '\r').
# EVERY byte of a data line must be accounted for by this pattern — a prefix match that leaves
# bytes unexamined is how a deleted ASCII byte and a ninth hex digit both read as clean
# (the owner's P2-2).
MD_LINE_FULL = re.compile(rb"^([0-9a-fA-F]{8}):((?: [0-9a-fA-F]{8}){1,4}) +(.*)$")
PROMPT_RE = re.compile(rb"(?:zynq-uboot|Zynq)> ?$")
PROMPT_ANY = re.compile(rb"(?:zynq-uboot|Zynq)> ")
BOOT_BANNER_RE = re.compile(rb"U-Boot SPL|\r?\nU-Boot \d|Trying to boot from|Model: Ebang")

EXPECT_USB = "1a86:7523"

# ---------------------------------------------------------------- the reviewed probe window
# DDR as the B2 BSP records it (firmware/b2/bsp/include/xparameters.h): base 0x00100000,
# high 0x1FFFFFFF. The probe is confined to a reviewed 1 MiB window at that base and refuses
# anything outside it BEFORE the port opens, so "no PL AXI, no other side-effecting MMIO" is a
# property of the input check and not of the operator's typing (the owner's P2-5).
WINDOW_BASE = 0x00100000
WINDOW_LAST = 0x001FFFFF
DDR_SOURCE = "firmware/b2/bsp/include/xparameters.h: XPAR_PS7_DDR_0_S_AXI_BASEADDR/HIGHADDR"
MAX_WORDS = 0x400

DEFAULT_ADDR = WINDOW_BASE
DEFAULT_WORDS = 0x100
DEFAULT_REPS = 200
DEFAULT_SECONDS = 3600.0
DEFAULT_COMMAND_S = 3.0
STOP_AFTER_MISMATCHES = 3      # over the WHOLE run; NOT the rig's "3 lost frames in one repetition"

MISMATCH_UNIT = ("one md.l response whose framed body was not byte-identical to the reference "
                 "response, counted once however many bytes differ; the cause is unknown")

EXIT_MEANING = {
    0: "the control returned",
    2: "a tool error, or the run stopped on a board/console condition; the evidence is exported",
    3: "refused before the control — the declared identity, the window/exposure bounds, "
       "no prompt at sync, or no valid reference response",
    4: "the device would not open",
    5: "the evidence destination could not be claimed or written — nothing was spent",
}


def self_sha256() -> str:
    """THIS tool's digest. `transport_rig.self_sha256` hashes transport_rig.py: importing it
    made the acquisition declare the helper's hash, so edits here were invisible in the record
    (the owner's P2-6)."""
    return hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest()


def provenance() -> dict:
    """What produced the acquisition: this tool, and separately the dependencies it imported."""
    return {"tool": str(Path(__file__).resolve().relative_to(REPO_ROOT)),
            "tool_sha256": self_sha256(),
            "dependencies": {"host/transport_rig.py":
                             hashlib.sha256(Path(_rig.__file__).resolve().read_bytes()).hexdigest()},
            "measurement_unit": MISMATCH_UNIT,
            "python": sys.version.split()[0]}


# ---------------------------------------------------------------- input validation (before any port)


def validate_window(addr: int, words: int) -> str | None:
    """The reviewed window, checked before the device is opened. Returns a refusal reason."""
    if not isinstance(addr, int) or not isinstance(words, int):
        return "addr and words must be integers"
    if words < 1 or words > MAX_WORDS:
        return f"words must be 1..{MAX_WORDS} (0x{MAX_WORDS:x}), not {words}"
    if addr % 4:
        return f"addr {addr:#010x} is not 4-byte aligned"
    if addr < WINDOW_BASE:
        return (f"addr {addr:#010x} is below the reviewed probe window "
                f"[{WINDOW_BASE:#010x}, {WINDOW_LAST:#010x}] ({DDR_SOURCE})")
    end = addr + 4 * words - 1
    if end > WINDOW_LAST or end < addr:
        return (f"the read {addr:#010x}..{end:#010x} leaves the reviewed probe window "
                f"[{WINDOW_BASE:#010x}, {WINDOW_LAST:#010x}] ({DDR_SOURCE})")
    return None


def validate_exposure(repetitions: int, seconds: float, command_s: float) -> str | None:
    import math
    if repetitions < 1:
        return f"repetitions must be >= 1, not {repetitions}"
    for name, v in (("seconds", seconds), ("command-timeout", command_s)):
        if not math.isfinite(v) or v <= 0:
            return f"{name} must be a finite positive number, not {v!r}"
    return None


# ---------------------------------------------------------------- framing and comparison


def split_framing(reply: bytes, command: str) -> tuple[bytes, dict]:
    """Separate the DECLARED framing from the body that is compared.

    Excluded by declaration, and only these: the echo of the command line, and the trailing
    prompt. Everything that remains is the body and every byte of it is compared."""
    framing: dict = {"echo_removed": False, "prompt_removed": False}
    body = reply
    echo = command.encode()
    at = body.find(echo)
    if at != -1:                                   # the echo and the EOL that ends it
        end = at + len(echo)
        while end < len(body) and body[end:end + 1] in (b"\r", b"\n"):
            end += 1
        body = body[:at] + body[end:]
        framing["echo_removed"] = True
    m = PROMPT_RE.search(body)
    if m:
        body = body[:m.start()]
        framing["prompt_removed"] = True
    stripped = body.lstrip(b"\r\n")
    framing["leading_eol_stripped"] = len(body) - len(stripped)
    body = stripped.rstrip(b"\r\n")
    framing["body_bytes"] = len(body)
    return body, framing


def parse_response(body: bytes, addr: int, words: int) -> tuple[list[int] | None, str | None]:
    """The body must be EXACTLY the expected data lines: every line fully matched by the
    grammar, at consecutive addresses, totalling `words` values. Anything left over, any line
    that does not match end to end, is malformed — never a prefix silently accepted."""
    if not body:
        return None, "empty body"
    values: list[int] = []
    expect = addr
    lines = body.split(b"\r\n")
    for n, line in enumerate(lines):
        m = MD_LINE_FULL.match(line)
        if not m:
            return None, f"line {n} does not match the md.l grammar end to end: {line[:64]!r}"
        line_addr = int(m.group(1), 16)
        if line_addr != expect:
            return None, f"line {n} at {line_addr:#010x}, expected {expect:#010x}"
        vals = [int(w, 16) for w in m.group(2).split()]
        values.extend(vals)
        expect += 4 * len(vals)
    if len(values) != words:
        return None, f"{len(values)} words, not {words}"
    return values, None


def first_difference(a: bytes, b: bytes) -> int | None:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


# ---------------------------------------------------------------- the console


class Timeout(Exception):
    """A phase deadline expired. Carries whether the exposure or the command budget ended it."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class UBoot:
    """Send a line, read to the prompt — every operation bounded by ONE absolute deadline for
    the phase, and the partial bytes accumulated into a caller-owned buffer so they survive an
    exception (the owner's P2-3, P2-4)."""

    def __init__(self, port: Port, read_timeout: float = 0.05, clock=None):
        # resolved at construction, not bound as a default at import: a caller that supplies a
        # clock gets it, and one that does not gets whatever `time.monotonic` is at that moment
        self.port, self.read_timeout = port, read_timeout
        self.clock = clock if clock is not None else time.monotonic

    def exchange(self, line: str, buf: bytearray, deadline: float) -> dict:
        """Write `line`, then read until the prompt or the deadline. Both the write and every
        read are capped by the remaining budget. Returns what was observed; raises nothing for a
        missing prompt — that is a classification, not an exception."""
        def remaining() -> float:
            return deadline - self.clock()
        if remaining() <= 0:
            return {"wrote": False, "saw_prompt": False, "expired": True}
        self.port.write((line + "\r").encode(), max(0.0, remaining()))
        while remaining() > 0:
            chunk = self.port.read(min(self.read_timeout, remaining()))
            if chunk:
                buf += chunk
                if PROMPT_RE.search(bytes(buf[-64:])):
                    return {"wrote": True, "saw_prompt": True, "expired": False}
        return {"wrote": True, "saw_prompt": False, "expired": True}


def _counters(fd) -> dict:
    """One counter attempt, on its own; unavailable is recorded with its reason, never as zero."""
    try:
        return read_icounters(fd)
    except Exception as exc:                              # noqa: BLE001
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}",
                "note": "no counter is reported; absence of a count is not a count of zero"}


# ---------------------------------------------------------------- the acquisition


def run_control(a) -> int:
    out = Path(a.out)
    export_errors: list[str] = []
    ports: list[tuple[str, Port]] = []

    def attempt(what: str, fn):
        try:
            return fn()
        except Exception as exc:                          # noqa: BLE001
            export_errors.append(f"{what}: {type(exc).__name__}: {exc}")
            return None

    closed: list[str] = []
    close_errors: list[str] = []
    try:
        code, stage, more = _steps(a, out, ports, attempt)
    finally:
        for name, p in reversed(ports):
            try:
                p.close()
                closed.append(name)
            except Exception as exc:                      # noqa: BLE001
                close_errors.append(f"{name}: {type(exc).__name__}: {exc}")
    brief = {"label": a.label, "exit": code, "exit_meaning": EXIT_MEANING[code], "stage": stage,
             "device": a.device, "exported_to": str(out),
             "ports_opened": [n for n, _ in ports], "ports_closed": closed,
             "close_errors": close_errors, "entry_export_errors": list(export_errors),
             "measurement_unit": MISMATCH_UNIT,
             "cause_of_a_mismatch": "unknown: transport, source memory, or command execution",
             **more}
    if stage == "destination":
        brief["entry_record"] = None
    else:
        brief["export_complete"] = not export_errors and bool(more.get("records_exported", True))
        brief["entry_record"] = "entry.json"
        if attempt("entry.json", lambda: _write_evidence(
                out / "entry.json", json.dumps(brief, indent=1, sort_keys=True) + "\n")) is None:
            brief["entry_record"] = None
        # recomputed AFTER every export attempt, the entry record included: a failed archive
        # must not leave stdout claiming a complete export (the owner's P2-3)
        brief["entry_export_errors"] = list(export_errors)
        brief["export_complete"] = not export_errors and bool(more.get("records_exported", True))
    print(json.dumps(brief, sort_keys=True))
    return code


def _steps(a, out: Path, ports: list, attempt) -> tuple[int, str, dict]:
    fd, refused = claim_destination(out)
    if fd is None:
        return 5, "destination", {"refusal": "destination", "refused": refused}

    # --- mandatory construction: anything here RAISING is a tool error known before the port
    #     exists, and stops before it (plan §5, any tool error; the owner's P2-3)
    construction: list[str] = []

    def build(what, fn):
        try:
            return fn()
        except Exception as exc:                          # noqa: BLE001
            construction.append(f"{what}: {type(exc).__name__}: {exc}")
            return None

    identity = build("identity", lambda: device_identity(a.device))
    prov = build("provenance", provenance)
    window_refusal = validate_window(a.addr, a.words)
    exposure_refusal = validate_exposure(a.repetitions, a.seconds, a.command_timeout)
    command = f"md.l {a.addr:#010x} {a.words:#x}"
    invocation = {
        "argv": list(a.argv), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "label": a.label, "device": a.device, "baud": a.baud, "expect_usb": a.expect_usb,
        "command": command, "addr": a.addr, "words": a.words,
        "repetitions": a.repetitions, "seconds": a.seconds, "command_timeout_s": a.command_timeout,
        "stop_after_mismatches": a.stop_after_mismatches,
        "probe_window": {"base": WINDOW_BASE, "last": WINDOW_LAST, "source": DDR_SOURCE,
                         "note": ("enforced before the port opens; that this window is unused by "
                                  "the running U-Boot is a MANDATORY OPERATOR CHECK this program "
                                  "cannot make")},
        "identity": identity,
        "identity_note": ("the kernel's record of what was opened. `expect_usb` checks the ADAPTER's "
                          "USB VID:PID only — it does not establish that the board is 17A6, which is "
                          "a mandatory operator check"),
        "measurement_unit": MISMATCH_UNIT,
        "claims_not_made": ("no bound on B2Q frame loss, no prediction of session failure, no "
                            "attribution of a mismatch to the transport"),
        "provenance": prov, "construction_errors": construction}
    if a.expect_usb:
        ok, why = identity_matches(identity or {}, a.expect_usb)
        invocation["identity_check"] = {"expected_usb": a.expect_usb, "matched": ok, "reason": why}
    if construction:
        invocation["terminal"] = {"reason": "tool_error", "stage": "invocation",
                                  "detail": "the invocation could not be constructed; no port was opened"}
    if attempt("invocation.json", lambda: _fd_write(fd, invocation)) is None:
        return 5, "invocation", {"records_exported": False}
    if construction:
        return 2, "invocation", {"error": "; ".join(construction), "construction_errors": construction}
    if window_refusal:
        return 3, "window", {"refusal": "window", "refused": window_refusal}
    if exposure_refusal:
        return 3, "exposure", {"refusal": "exposure", "refused": exposure_refusal}
    if a.expect_usb and not invocation["identity_check"]["matched"]:
        return 3, "identity", {"refusal": "identity", "refused": invocation["identity_check"]["reason"]}

    try:
        port = serial_port(a.device, a.baud)
        ports.append((a.device, port))
    except Exception as exc:                              # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        attempt("open_error.json", lambda: _write_evidence(
            out / "open_error.json", json.dumps({"error": error, "device": a.device}, indent=1) + "\n"))
        return 4, "open", {"error": error, "records_exported": False}

    fdno = None
    try:
        fdno = port.fileno()
    except Exception:                                     # noqa: BLE001 — the counters will say so
        fdno = None
    ub = UBoot(port)
    counters_before = _counters(fdno)
    started = time.monotonic()
    exposure_end = started + a.seconds

    def phase_deadline() -> float:
        """One deadline per command: the command budget, never past the exposure (P2-4)."""
        return min(time.monotonic() + a.command_timeout, exposure_end)

    # --- sync: an unconfirmed prompt refuses before any md is issued
    sync_buf = bytearray()
    primary: str | None = None
    try:
        sync = ub.exchange("", sync_buf, phase_deadline())
    except Exception as exc:                              # noqa: BLE001 — partial bytes survive in sync_buf
        primary = f"{type(exc).__name__}: {exc}"
        sync = {"wrote": False, "saw_prompt": False, "expired": False, "error": primary}
    attempt("sync.bin", lambda: _write_evidence(out / "sync.bin", bytes(sync_buf)))
    if primary:
        _finalise(out, attempt, a, command, None, [], counters_before, _counters(fdno),
                  {"reason": "tool_error", "detail": primary, "phase": "sync"}, prov)
        return 2, "sync", {"error": primary}
    if not sync.get("saw_prompt"):
        _finalise(out, attempt, a, command, None, [], counters_before, _counters(fdno),
                  {"reason": "no_prompt_at_sync",
                   "detail": "no U-Boot prompt answered the sync CR; no md.l was issued"}, prov)
        return 3, "sync", {"refusal": "no_prompt_at_sync",
                           "refused": "no U-Boot prompt answered the sync CR; no md.l was issued"}

    # --- the reference response
    ref_buf = bytearray()
    try:
        ref = ub.exchange(command, ref_buf, phase_deadline())
    except Exception as exc:                              # noqa: BLE001
        primary = f"{type(exc).__name__}: {exc}"
        ref = {"saw_prompt": False, "expired": False, "error": primary}
    attempt("reference.bin", lambda: _write_evidence(out / "reference.bin", bytes(ref_buf)))
    ref_body, ref_framing = split_framing(bytes(ref_buf), command)
    ref_values, ref_error = (None, "no prompt") if not ref.get("saw_prompt") else \
        parse_response(ref_body, a.addr, a.words)
    reference = {"command": command, "raw_bytes": len(ref_buf), "framing": ref_framing,
                 "body_bytes": len(ref_body), "body_sha256": hashlib.sha256(ref_body).hexdigest(),
                 "parsed": ref_values is not None, "error": primary or ref_error,
                 "note": ("a REFERENCE OBSERVATION, not independently known transmitted bytes: it "
                          "does not establish that the window is stable, and a corruption present "
                          "in every response including this one is invisible by construction")}
    attempt("reference.json", lambda: _write_evidence(
        out / "reference.json", json.dumps(reference, indent=1, sort_keys=True) + "\n"))
    if primary:
        _finalise(out, attempt, a, command, reference, [], counters_before, _counters(fdno),
                  {"reason": "tool_error", "detail": primary, "phase": "reference"}, prov)
        return 2, "reference", {"error": primary}
    if ref_values is None:
        _finalise(out, attempt, a, command, reference, [], counters_before, _counters(fdno),
                  {"reason": "no_reference", "detail": f"no valid reference response: {ref_error}"}, prov)
        return 3, "reference", {"refusal": "reference",
                                "refused": f"no valid reference response: {ref_error}"}

    # --- the repeated reads
    records: list[dict] = []
    mismatches = 0
    terminal: dict | None = None
    for i in range(a.repetitions):
        if time.monotonic() >= exposure_end:
            terminal = {"reason": "exposure_seconds",
                        "detail": f"the {a.seconds} s exposure ended after {i} repeated reads"}
            break
        buf = bytearray()
        rec: dict = {"i": i}
        try:
            obs = ub.exchange(command, buf, phase_deadline())
        except Exception as exc:                          # noqa: BLE001 — the PARTIAL bytes are evidence
            primary = f"{type(exc).__name__}: {exc}"
            obs = {"saw_prompt": False, "expired": False, "error": primary}
        attempt(f"read_{i:04d}.bin", lambda b=buf, n=i: _write_evidence(out / f"read_{n:04d}.bin", bytes(b)))
        rec["raw_bytes"] = len(buf)
        if primary:
            rec["error"] = primary
            records.append(rec)
            terminal = {"reason": "tool_error", "detail": primary, "phase": f"read {i}",
                        "partial_bytes": len(buf)}
            break
        if not obs.get("saw_prompt"):
            # a missing prompt is NOT evidence of a board reset unless a banner was seen; a
            # cutoff by the exposure is not an error at all (the owner's P2-4)
            rec["raw_bytes"] = len(buf)
            records.append(rec)
            if BOOT_BANNER_RE.search(bytes(buf)):
                terminal = {"reason": "board_reset", "at_read": i,
                            "detail": "a U-Boot boot banner was observed in the reply"}
            elif time.monotonic() >= exposure_end:
                terminal = {"reason": "exposure_seconds", "at_read": i,
                            "detail": f"the {a.seconds} s exposure cut read {i} before its prompt",
                            "cut_short": True, "partial_bytes": len(buf)}
            else:
                terminal = {"reason": "no_prompt", "at_read": i,
                            "detail": (f"no prompt within the {a.command_timeout} s command budget; "
                                       "cause unknown — transport loss, command failure or cutoff "
                                       "are all consistent with this observation"),
                            "partial_bytes": len(buf)}
            break
        body, framing = split_framing(bytes(buf), command)
        rec.update(body_bytes=len(body), framing_ok=framing["echo_removed"] or framing["prompt_removed"])
        if body == ref_body:
            rec["outcome"] = "identical"
        else:
            mismatches += 1
            values, perr = parse_response(body, a.addr, a.words)
            rec.update(outcome="mismatch",
                       first_diff_offset=first_difference(body, ref_body),
                       body_delta_bytes=len(body) - len(ref_body),
                       grammar_valid=values is not None, grammar_error=perr,
                       changed_word_indices=([j for j, (x, y) in enumerate(zip(values, ref_values))
                                              if x != y][:16] if values is not None else None),
                       body_sha256=hashlib.sha256(body).hexdigest())
        records.append(rec)
        if rec.get("outcome") == "mismatch" and mismatches >= a.stop_after_mismatches:
            terminal = {"reason": "stop_rule_mismatches", "at_read": i,
                        "detail": (f"{mismatches} mismatched responses over the run "
                                   f"(>= {a.stop_after_mismatches}); this is a run-total rule and is "
                                   "NOT the rig's three lost expected frames within one repetition")}
            break
    else:
        terminal = {"reason": "exposure_repetitions",
                    "detail": f"{a.repetitions} repeated reads completed"}

    counters_after = _counters(fdno)
    # a transient mismatch (neighbours identical) and a persistent one (every later read differs)
    # look different; both are DESCRIPTIVE — neither attributes a cause
    outcomes = [r.get("outcome") for r in records]
    persistent = bool(outcomes) and all(o == "mismatch" for o in outcomes if o is not None)
    exported = _finalise(out, attempt, a, command, reference, records, counters_before,
                         counters_after, terminal, prov, mismatches=mismatches,
                         persistent=persistent, ref_body_bytes=len(ref_body))
    exit_code = 2 if (terminal or {}).get("reason") in ("tool_error", "board_reset", "no_prompt") else 0
    received = sum(r.get("raw_bytes", 0) for r in records)
    return exit_code, "control", {
        "terminal": (terminal or {}).get("reason"), "detail": (terminal or {}).get("detail"),
        "reads_done": len(records), "mismatched_responses": mismatches,
        "identical_responses": sum(1 for o in outcomes if o == "identical"),
        "received_bytes_excluding_reference": received,
        "mismatches_per_100_responses": (None if not records else 100.0 * mismatches / len(records)),
        "all_observed_responses_differ": persistent,
        "counters_delta": counter_delta(counters_before, counters_after),
        "records_exported": exported}


def _finalise(out: Path, attempt, a, command, reference, records, before, after, terminal, prov,
              mismatches: int = 0, persistent: bool = False, ref_body_bytes: int = 0) -> bool:
    """Always attempted, on every path past the port opening, each component independently."""
    received = sum(r.get("raw_bytes", 0) for r in records)
    result = {"label": a.label, "command": command, "provenance": prov,
              "measurement_unit": MISMATCH_UNIT,
              "cause_of_a_mismatch": "unknown: transport, source memory, or command execution",
              "claims_not_made": ("no bound on B2Q frame loss, no prediction of session failure, "
                                  "no attribution of a mismatch to the transport; a mismatched "
                                  "response is not a lost rel-v4 frame"),
              "reference": reference, "reference_body_bytes": ref_body_bytes,
              "parameters": {"addr": a.addr, "words": a.words, "repetitions": a.repetitions,
                             "seconds": a.seconds, "command_timeout_s": a.command_timeout,
                             "stop_after_mismatches": a.stop_after_mismatches,
                             "probe_window": [WINDOW_BASE, WINDOW_LAST]},
              "reads_done": len(records), "mismatched_responses": mismatches,
              "identical_responses": sum(1 for r in records if r.get("outcome") == "identical"),
              "received_bytes_excluding_reference": received,
              "mismatches_per_100_responses": (None if not records else 100.0 * mismatches / len(records)),
              "all_observed_responses_differ": persistent,
              "terminal": terminal, "counters_before": before, "counters_after": after,
              "counters_delta": counter_delta(before, after),
              "scope": ("a repeated-read consistency control at one U-Boot prompt; it attributes "
                        "nothing, qualifies nothing and authorises no session"),
              "reads": records}
    return attempt("control.json", lambda: _write_evidence(
        out / "control.json", json.dumps(result, indent=1, sort_keys=True) + "\n")) is not None


def _fd_write(fd: int, obj: dict) -> bool:
    import os
    try:
        f = os.fdopen(fd, "w")
    except Exception:
        os.close(fd)
        raise
    with f:
        f.write(json.dumps(obj, indent=1, sort_keys=True) + "\n")
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--device", required=True, help="the console port; on 17A6 the CH340 /dev/ebaz-uart")
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True, help="evidence directory, claimed fresh")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--expect-usb", default=EXPECT_USB, metavar="VID:PID",
                    help=f"refuse unless the ADAPTER's USB identity is this (default {EXPECT_USB}); "
                         "it does not establish the board is 17A6; '' disables the check")
    ap.add_argument("--addr", type=lambda s: int(s, 0), default=DEFAULT_ADDR,
                    help=f"read base, inside the reviewed window {WINDOW_BASE:#x}..{WINDOW_LAST:#x}")
    ap.add_argument("--words", type=lambda s: int(s, 0), default=DEFAULT_WORDS)
    ap.add_argument("--repetitions", type=int, default=DEFAULT_REPS)
    ap.add_argument("--seconds", type=float, default=DEFAULT_SECONDS)
    ap.add_argument("--command-timeout", type=float, default=DEFAULT_COMMAND_S,
                    help="per-command budget; every command is also capped by the remaining exposure")
    ap.add_argument("--stop-after-mismatches", type=int, default=STOP_AFTER_MISMATCHES,
                    help="stop after this many mismatched responses OVER THE RUN")
    a = ap.parse_args(argv)
    a.argv = list(argv if argv is not None else sys.argv[1:])
    if not a.expect_usb:
        a.expect_usb = None
    return run_control(a)


if __name__ == "__main__":
    sys.exit(main())

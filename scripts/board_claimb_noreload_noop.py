#!/usr/bin/env python3
"""One diagnostic no-op transaction into an ALREADY-LOADED carrier. No reload, no second step.

This is step ② of `docs/claimb_read_side_divergence_design.md` §7.4. Every other Claim B
entrypoint begins by configuring the carrier: it pins FCLK0 and then invokes the FPGA loader,
which insists on an empty PL. That reconfigures the device, and reconfiguring it would destroy
the post-fault configuration memory this probe exists to interrogate. So this module performs
no setup phase and invokes no loader at all — the structural gate beside it refuses the source
outright if either is so much as named here. It attaches to a board that is already in the
specified post-fault state, proves it is still that boot, writes the published **restore**
payload once, and stops.

What it is for. Under strict H-STALE the read observes configuration memory as it stood before
this burst — which is the candidate the faulted round left behind — so this no-op, the step that
has never failed, must FAULT. Under the currently observed blank-returning forms of H-PAD,
H-ADDR and H-IDLE it verifies fifteen frames and the host stops on the latched
`recovery_required`. Two different stops, both fail-closed, distinguishable from the record.

What it is NOT. A pass here is a **conditional** negative for strict H-STALE and is never
reported as a refutation: this run deliberately performs no R4/JTAG read between the fault and
this transaction — that read perturbs the configuration engine — so it never observes that this
instance held the candidate beforehand. Whether step ① actually produced the specified fault is
step ①'s verdict, judged there, not here; what this tool guarantees is that every STATUS word it
saw survives in the telemetry, so a reviewer can reconstruct the pre-state and the final state.

Structure, so that review is about a shape rather than a promise:

* the only operator choices are the tty, the boot marker to insist on, and where the evidence
  goes. There is no force, retry, continue, skip, allow or scoring option;
* two gates run BEFORE the tty is opened at all — the evidence destination is reserved, and
  the marker's format is judged — so those refusals cost zero board contact. Identity and
  same-boot need an open transport by construction, but both still precede any payload, so
  every refusal on this path costs zero transactions;
* `known_driver._write("restore", …)` is called exactly once, with a literal payload name. The
  candidate payload, the scorer, ARM and HOLDOUT are unreachable from this module;
* there is no loop and no recovery arm, and **no interrupt**: this entrypoint issues no
  console action of its own after a refusal. Every command it sends is in the telemetry;
* a real pass cannot return normally while `fault_since_reset` is latched — the transport
  refuses on the sticky `recovery_required` — so that shape is recognised and its status is
  reconstructed from the telemetry rather than lost. See `classify_stop`.

Hardware execution requires a separate user ruling. This module does not carry one.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import board_calibrate_noop as cal  # noqa: E402
import board_carrier_exec as ex  # noqa: E402
import board_claimb_known_answer as known_driver  # noqa: E402
import board_uboot_axi as axi  # noqa: E402
import gate_board_identity as ident  # noqa: E402
import gate_claimb_known_answer as kagate  # noqa: E402

TOOL_VERSION = "board_claimb_noreload_noop.py/1.0.1"

# What a clean second transaction ACTUALLY does on this board. The transport completes all
# three envelopes, reads the final status, and then refuses anyway, because `fault_since_reset`
# is latched from the fault this probe was attached to — so `status_after`, `readback_frames`
# and the session's saved transaction are never assigned, and the structured evidence would be
# lost. It is reconstructed from the command telemetry instead, which costs no extra board
# action because those reads already happened.
STICKY_RECOVERY = "recovery_required is still set"
STATUS_REPLY = re.compile(rf"^{axi.STATUS:08x}: *([0-9a-f]{{8}})", re.MULTILINE | re.IGNORECASE)
EXPECTED_ON_A_CLEAN_SECOND_TRANSACTION = {
    "rb_frames_ok": 15, "configuration_valid": True, "fault": False,
    "recovery_required": True,
}

# The loader writes `plmark` with `setenv` and never `saveenv`, so it is sixteen lowercase hex
# digits living in RAM. Anything else is a typo or a paraphrase, and a marker that cannot be
# the loader's own output must not be allowed to reach a same-boot comparison.
PLMARK = re.compile(r"[0-9a-f]{16}")

# The B1 reading, and the ONLY place it is spelled out. `classify_stop` is the only function
# permitted to reference it, and the structural gate enforces that: a branch that could mint
# this for itself would be able to call something B1 without checking the sticky recovery flag
# or the four status fields that define it.
PASS_VERDICT = (
    "THE DIAGNOSTIC NO-OP PASSED; CONDITIONAL NEGATIVE FOR STRICT H-STALE — this run did not "
    "observe its own starting content, so this is not a refutation")


class EvidenceReservationStop(Exception):
    """The evidence destination was not free, or not writable, before anything was touched."""


class ProbeStop(Exception):
    """The single-transaction probe stopped, with its partial round attached."""

    def __init__(self, message: str, *, record: dict, cause: BaseException) -> None:
        super().__init__(message)
        self.record = record
        self.cause = cause


def reserve_evidence(out: Path) -> Path:
    """Claim the destination BEFORE the tty is opened, and never overwrite an existing record.

    Two failures this closes, both found by an adversarial review of 1.0.0: an existing
    `<out>` was silently replaced by `os.replace`, and the destination's writability was not
    established until after the board had been touched — so a run could do its board work and
    then discover it had nowhere to put the evidence.

    Creating the `.part` exclusively does both jobs at once: it proves the directory is
    writable and it claims the name, so a second invocation pointed at the same output stops
    instead of racing. A stale `.part` from a killed run is deliberately fatal: something did
    not finish, and that is for a person to look at.
    """
    partial = out.with_name(out.name + ".part")
    if out.exists():
        raise EvidenceReservationStop(
            f"{out} already exists; this entrypoint never overwrites evidence. Choose a new "
            f"path or move the old record aside.")
    if partial.exists():
        raise EvidenceReservationStop(
            f"{partial} already exists, so an earlier run did not finish writing. Look at it "
            f"before starting another.")
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(partial, "x", encoding="utf-8"):
            pass
    except OSError as why:
        raise EvidenceReservationStop(
            f"cannot reserve {partial}: {why}. The destination has to be writable before the "
            f"board is touched, not after.") from why
    return partial


def reconstruct_status(record: dict) -> dict | None:
    """The last STATUS word the run actually read, taken from its own command telemetry.

    Nothing is re-read from the board to obtain this: the reads already happened inside the
    transaction, the instrumented transport kept every reply verbatim, and this is a host-side
    parse of that record.
    """
    commands = record.get("instrumentation", {}).get("commands", [])
    want = f"md.l 0x{axi.STATUS:08x} 0x1"
    for command in reversed(commands):
        if command.get("command", "").lower() != want:
            continue
        found = STATUS_REPLY.search(command.get("raw", "") or "")
        if found:
            return axi.decode_status(int(found.group(1), 16))
    return None


def classify_stop(record: dict, cause: BaseException) -> dict:
    """Name the shape this run stopped in, from the refusal and the reconstructed status.

    The one shape that has to be recognised rather than inferred is the clean second
    transaction: fifteen frames verified, `configuration_valid` set, no fault, and the sticky
    `recovery_required` that makes the transport refuse anyway. That is B1 of the design's
    reading table, and it is a CONDITIONAL negative — this run never observed its own starting
    content, so it refutes nothing.
    """
    status = reconstruct_status(record)
    reading = {
        "reconstructed_from": "the run's own command telemetry; nothing was re-read",
        "final_status": status,
        "sticky_recovery_refusal": isinstance(cause, axi.AxiRefusal)
        and STICKY_RECOVERY in str(cause),
    }
    if status is not None:
        reading["matches_a_clean_second_transaction"] = {
            field: status.get(field) == expected
            for field, expected in EXPECTED_ON_A_CLEAN_SECOND_TRANSACTION.items()}
    clean = (reading["sticky_recovery_refusal"] and status is not None
             and all(reading["matches_a_clean_second_transaction"].values()))
    reading["shape"] = "CLEAN_SECOND_TRANSACTION" if clean else "NOT_A_CLEAN_SECOND_TRANSACTION"
    reading["verdict"] = PASS_VERDICT if clean else None
    return reading


def require_plmark(marker: str) -> str:
    """The boot marker, or a refusal — before the transport exists, let alone a payload."""
    if not isinstance(marker, str) or not PLMARK.fullmatch(marker):
        raise ValueError(
            f"--plmark {marker!r} is not sixteen lowercase hex digits, so it cannot be a "
            "marker this board's loader produced. Transcribe it from the fault run's "
            "carrier_load.log; never retype it.")
    return marker


def run_noreload_noop(authority: ex.PublishedCarrierAuthority,
                      known: kagate.KnownAnswerAuthority,
                      session) -> dict:
    """Write the published restore payload once. Return on a pass; raise on anything else."""
    if not isinstance(authority, ex.PublishedCarrierAuthority):
        raise ProbeStop(
            "the carrier authority is not published",
            record={"tool": TOOL_VERSION, "steps": []},
            cause=TypeError("unpublished carrier authority"))
    if not isinstance(known, kagate.KnownAnswerAuthority):
        raise ProbeStop(
            "the known-answer authority is not consumer-verified",
            record={"tool": TOOL_VERSION, "steps": []},
            cause=TypeError("unverified known-answer authority"))

    record = {"tool": TOOL_VERSION, "steps": []}
    entry = {"step": "diagnostic_no_op", "state": "started"}
    record["steps"].append(entry)
    try:
        entry["result"] = known_driver._write("restore", authority, known, session)
    except Exception as raised:
        entry["state"] = "stopped"
        entry["stop_reason"] = f"{type(raised).__name__}: {raised}"
        child = getattr(raised, "record", None)
        if child is not None:
            entry["failure_evidence"] = child
        cause = getattr(raised, "cause", None) or raised
        # No retry, no recovery, no acknowledgement: the state this stopped in IS the finding.
        raise ProbeStop(
            f"diagnostic_no_op stopped: {raised}", record=record, cause=cause) from raised
    entry["state"] = "passed"
    # Deliberately NOT a reading. This function knows only that the write returned; whether
    # that is the pre-registered B1 depends on the sticky recovery flag and the final status,
    # which only `classify_stop` looks at. A round that named the verdict here would be the
    # same defect the classifier exists to prevent, one level down.
    record["verdict"] = "THE SINGLE WRITE RETURNED; THE READING IS NOT THIS FUNCTION'S TO MAKE"
    return record


def _atomic_write_evidence(path: Path, partial: Path, record: dict) -> None:
    """Write into the reservation this run already claimed, then move it into place."""
    partial.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(partial, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", default="/dev/ebaz-uart")
    parser.add_argument("--plmark", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    # Before anything else, and before any evidence file could be written: claim the
    # destination. A refusal here leaves an existing record byte-for-byte untouched and has
    # not opened the tty, so it costs no board contact at all.
    try:
        partial = reserve_evidence(args.out)
    except EvidenceReservationStop as stop:
        print(f"STOP: {stop}", file=sys.stderr)
        return 1

    record: dict = {
        "tool": TOOL_VERSION,
        "what": "one diagnostic no-op into an already-loaded, already-faulted carrier",
        "carrier_run": str(cal.DEFAULT_RUN.relative_to(REPO)),
        "no_reload": ("this module performs no setup phase and invokes no loader; the "
                      "carrier under test is whatever the named boot already configured"),
        "no_interrupt": ("this module sends no console action of its own after a refusal; "
                         "every command it issued is in the telemetry below"),
        "started_at": time.time(),
    }
    transport = None
    failed = False
    try:
        authority = ex.PublishedCarrierAuthority.load(cal.DEFAULT_RUN)
        known = kagate.KnownAnswerAuthority.load()
        bundle = json.loads((cal.DEFAULT_RUN / "carrier_run.json").read_text("utf-8"))
        record["authority"] = {
            "carrier_manifest_sha256": authority.manifest_sha256,
            "known_answer_artifact_sha256": kagate.PRODUCTION_ARTIFACT_SHA256,
            "run_id": bundle.get("run_id"),
        }
        # Still before the tty is opened: a marker that cannot be a loader's output is
        # refused here, so a mistyped argument costs no board contact either.
        expected_plmark = require_plmark(args.plmark)

        transport = cal.InstrumentedTransport(ident.SerialTransport(args.port), record)
        session = ident.BoardSession(transport)
        identity = session.verify_identity("content")
        record["identity"] = identity["parsed"]
        record["same_boot"] = {"expected_plmark": expected_plmark, "passed": False}
        # `printenv plmark` only. Asked before anything reads the carrier, because if the PL
        # is gone the read stalls the CPU and costs a power cycle.
        axi.same_boot(transport, expected_plmark)
        record["same_boot"]["passed"] = True
        transport.mark("before run_noreload_noop")
        record["round"] = run_noreload_noop(authority, known, session)

        # A NORMAL RETURN IS NOT B1. The transport only returns when the final status has
        # `recovery_required` clear — which means `fault_since_reset` was clear, which means
        # this did not run against a faulted carrier at all. The pre-registered B1 requires
        # the sticky flag SET. So this branch is its own finding: the premise of the
        # experiment was not met, and no conditional-negative verdict is issued for it.
        record["reading"] = {
            "shape": "UNEXPECTED_NORMAL_RETURN",
            "final_status": reconstruct_status(record),
            "sticky_recovery_refusal": False,
            "verdict": None,
            "reconstructed_from": "the round returned normally; the status is telemetry",
            "why_not_b1": ("B1 is a clean transaction refused on a STICKY recovery flag. A "
                           "normal return means recovery_required was clear at the final "
                           "read, so this carrier had not faulted and the state this probe "
                           "is only meaningful in was not the state it ran against."),
        }
        record["verdict"] = "STOP"
        record["stop_reason"] = (
            "the transaction returned normally, so recovery_required was clear and this did "
            "not run against a faulted carrier; that is not the pre-registered B1 and no "
            "reading is issued for it")
        print(f"STOP: {record['stop_reason']}", file=sys.stderr)
        failed = True
    except Exception as stop:
        if isinstance(stop, ProbeStop):
            record["round"] = stop.record
            cause = stop.cause
        else:
            cause = stop
        # No interrupt, no acknowledgement, no recovery: by the time a transaction refuses,
        # every command it sent has already returned a prompt, so a Ctrl-C here would be an
        # extra board action that no telemetry records. The console is left as it was found.
        record["reading"] = classify_stop(record, cause)
        record["verdict"] = "STOP"
        record["stop_reason"] = (record["reading"]["verdict"]
                                 if record["reading"]["verdict"] is not None
                                 else f"{type(stop).__name__}: {stop}")
        record["raised"] = f"{type(stop).__name__}: {stop}"
        print(f"STOP: {record['stop_reason']}", file=sys.stderr)
        failed = True
    finally:
        if transport is not None:
            try:
                transport.close()
            except Exception as close_error:
                record["transport_close_error"] = (
                    f"{type(close_error).__name__}: {close_error}")
                if not failed:
                    record["verdict"] = "STOP"
                    record["stop_reason"] = (
                        "transport close failed after the probe: "
                        f"{type(close_error).__name__}: {close_error}")
                    failed = True

    record["finished_at"] = time.time()
    _atomic_write_evidence(args.out, partial, record)
    print(f"  evidence: {args.out}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

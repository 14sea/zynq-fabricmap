#!/usr/bin/env python3
"""Create the two-transaction Claim B post-fault state, without a continuation path.

This fixed production entrypoint runs the published restore payload and then the published
known-answer payload. It stops after the second transaction whether that transaction faults
or unexpectedly passes. There is no third step and no device-evaluation capability in this
module. The only operator choices are the physical UART and the evidence destination.

Hardware execution requires a separate user ruling.
"""

from __future__ import annotations

import argparse
import json
import os
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

TOOL_VERSION = "board_claimb_postfault_capture.py/1.0.0"


class CaptureStop(Exception):
    """The fixed two-step capture stopped, with its partial round attached."""

    def __init__(self, message: str, *, record: dict, cause: BaseException) -> None:
        super().__init__(message)
        self.record = record
        self.cause = cause


def run_postfault_capture(authority: ex.PublishedCarrierAuthority,
                          known: kagate.KnownAnswerAuthority,
                          session) -> dict:
    """Run exactly restore then candidate; return rather than continuing after a pass."""
    if not isinstance(authority, ex.PublishedCarrierAuthority):
        raise CaptureStop(
            "the carrier authority is not published",
            record={"tool": TOOL_VERSION, "steps": []},
            cause=TypeError("unpublished carrier authority"))
    if not isinstance(known, kagate.KnownAnswerAuthority):
        raise CaptureStop(
            "the known-answer authority is not consumer-verified",
            record={"tool": TOOL_VERSION, "steps": []},
            cause=TypeError("unverified known-answer authority"))

    record = {"tool": TOOL_VERSION, "steps": []}

    def step(name: str, which: str) -> None:
        entry = {"step": name, "state": "started"}
        record["steps"].append(entry)
        try:
            entry["result"] = known_driver._write(which, authority, known, session)
        except Exception as raised:
            entry["state"] = "stopped"
            entry["stop_reason"] = f"{type(raised).__name__}: {raised}"
            child = getattr(raised, "record", None)
            if child is not None:
                entry["failure_evidence"] = child
            cause = getattr(raised, "cause", None) or raised
            raise CaptureStop(
                f"{name} stopped: {raised}", record=record, cause=cause) from raised
        entry["state"] = "passed"

    step("no_op", "restore")
    step("known_answer", "candidate")
    record["verdict"] = "KNOWN-ANSWER PASSED; REQUESTED FAULT STATE WAS NOT CREATED"
    return record


def _atomic_write_evidence(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    partial.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(partial, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", default="/dev/ebaz-uart")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    record: dict = {
        "tool": TOOL_VERSION,
        "what": "Claim B fixed two-transaction post-fault capture",
        "carrier_run": str(cal.DEFAULT_RUN.relative_to(REPO)),
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

        record["setup"] = cal.phase_setup(
            args.port, cal.DEFAULT_RUN / "carrier.bit",
            bundle["artifacts"]["carrier.bit"]["sha256"])

        transport = cal.InstrumentedTransport(ident.SerialTransport(args.port), record)
        session = ident.BoardSession(transport)
        identity = session.verify_identity("content")
        record["identity"] = identity["parsed"]
        record["same_boot"] = {
            "expected_plmark": record["setup"]["plmark"], "passed": False}
        axi.same_boot(transport, record["setup"]["plmark"])
        record["same_boot"]["passed"] = True
        transport.mark("before run_postfault_capture")
        record["round"] = run_postfault_capture(authority, known, session)

        # An unexpected pass is evidence, but it is not the requested fault state. This is
        # intentionally a stopped CLI result; nothing follows the second transaction.
        record["verdict"] = "STOP"
        record["stop_reason"] = (
            "known_answer passed; the requested post-fault state was not created")
        print(f"STOP: {record['stop_reason']}", file=sys.stderr)
        failed = True
    except Exception as stop:
        if isinstance(stop, CaptureStop):
            record["round"] = stop.record
            cause = stop.cause
        else:
            cause = stop
        if transport is not None and isinstance(cause, axi.AxiRefusal):
            try:
                record["interrupt_reply"] = transport.interrupt().decode(
                    "ascii", "replace")
            except Exception as interrupt_error:
                record["interrupt_error"] = (
                    f"{type(interrupt_error).__name__}: {interrupt_error}")
        record["verdict"] = "STOP"
        record["stop_reason"] = f"{type(stop).__name__}: {stop}"
        print(f"STOP: {stop}", file=sys.stderr)
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
                        "transport close failed after capture: "
                        f"{type(close_error).__name__}: {close_error}")
                    failed = True

    record["finished_at"] = time.time()
    _atomic_write_evidence(args.out, record)
    print(f"  evidence: {args.out}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

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
instance held the candidate beforehand. `status_before` in the transaction record is what a
reviewer reads to see the pre-state; whether step ① actually produced the specified fault is
step ①'s verdict, judged there, not here.

Structure, so that review is about a shape rather than a promise:

* the only operator choices are the tty, the boot marker to insist on, and where the evidence
  goes. There is no force, retry, continue, skip, allow or scoring option;
* identity, the marker's format and same-boot are all decided BEFORE the transport is opened or
  a payload is written, so a refusal costs zero transactions;
* `known_driver._write("restore", …)` is called exactly once, with a literal payload name. The
  candidate payload, the scorer, ARM and HOLDOUT are unreachable from this module;
* there is no loop and no recovery arm. A fault stops, a pass stops, and both keep everything.

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

TOOL_VERSION = "board_claimb_noreload_noop.py/1.0.0"

# The loader writes `plmark` with `setenv` and never `saveenv`, so it is sixteen lowercase hex
# digits living in RAM. Anything else is a typo or a paraphrase, and a marker that cannot be
# the loader's own output must not be allowed to reach a same-boot comparison.
PLMARK = re.compile(r"[0-9a-f]{16}")

PASS_VERDICT = (
    "THE DIAGNOSTIC NO-OP PASSED; CONDITIONAL NEGATIVE FOR STRICT H-STALE — this run did not "
    "observe its own starting content, so this is not a refutation")


class ProbeStop(Exception):
    """The single-transaction probe stopped, with its partial round attached."""

    def __init__(self, message: str, *, record: dict, cause: BaseException) -> None:
        super().__init__(message)
        self.record = record
        self.cause = cause


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
    record["verdict"] = PASS_VERDICT
    return record


def _atomic_write_evidence(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    partial.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(partial, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", default="/dev/ebaz-uart")
    parser.add_argument("--plmark", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    record: dict = {
        "tool": TOOL_VERSION,
        "what": "one diagnostic no-op into an already-loaded, already-faulted carrier",
        "carrier_run": str(cal.DEFAULT_RUN.relative_to(REPO)),
        "no_reload": ("this module performs no setup phase and invokes no loader; the "
                      "carrier under test is whatever the named boot already configured"),
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
        # Before the tty is opened: a marker that cannot be a loader's output is refused here,
        # so a mistyped argument costs no board contact at all.
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

        # A pass is a fail-closed stop, never a green light: nothing follows this transaction,
        # and the host will in any case refuse on the latched recovery_required.
        record["verdict"] = "STOP"
        record["stop_reason"] = PASS_VERDICT
        print(f"STOP: {record['stop_reason']}", file=sys.stderr)
        failed = True
    except Exception as stop:
        if isinstance(stop, ProbeStop):
            record["round"] = stop.record
            cause = stop.cause
        else:
            cause = stop
        if transport is not None and isinstance(cause, axi.AxiRefusal):
            try:
                record["interrupt_reply"] = transport.interrupt().decode("ascii", "replace")
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
                        "transport close failed after the probe: "
                        f"{type(close_error).__name__}: {close_error}")
                    failed = True

    record["finished_at"] = time.time()
    _atomic_write_evidence(args.out, record)
    print(f"  evidence: {args.out}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

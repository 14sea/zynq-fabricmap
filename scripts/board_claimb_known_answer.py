#!/usr/bin/env python3
"""The reviewed Claim B known-answer chain and its only device entrypoint.

The chain is intentionally boring: base no-op, candidate, two scorer modes, restore, two
scorer modes. Payload construction and expected results come only from the published
known-answer authority. The command-line entrypoint adds the already-reviewed no-op board
scaffolding around that chain: fixed carrier authority, FCLK0, an empty-PL load, one session,
identity, same-boot proof, complete command telemetry, and an evidence file.

There is deliberately no argument for a carrier run, known-answer artifact, force, skip,
allow, or transport. The only choices a caller has are which physical tty to use and where
to write the evidence. Hardware execution still requires a separate user ruling.
"""

from __future__ import annotations

import argparse
import json
import time
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import board_carrier_exec as ex  # noqa: E402
import board_calibrate_noop as cal  # noqa: E402
import board_uboot_axi as axi  # noqa: E402
import gate_board_identity as ident  # noqa: E402
import gate_claimb_known_answer as kagate  # noqa: E402

TOOL_VERSION = "board_claimb_known_answer.py/2.0.0"


class KnownAnswerStop(Exception):
    """A dry-run or hardware round failed closed."""

    def __init__(self, message: str, *, record: dict | None = None,
                 cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.record = record
        self.cause = cause


def _write(which: str, authority: ex.PublishedCarrierAuthority,
           known: kagate.KnownAnswerAuthority, session) -> dict:
    payload = ex.SealedPayload(known.payload(which))
    result = ex.run_candidate_on_board(payload, authority, session)
    expected = known.frames_sha256(which)
    # This host comparison is repeated inside the only arm function.  Keeping it here
    # makes the transaction boundary explicit in the round record; keeping it there makes
    # bypassing this orchestrator insufficient to arm.
    actual = axi._frames_hash(result["transaction"]["readback_frames"])
    if actual != expected:
        raise KnownAnswerStop(
            f"{which} readback SHA {actual} != pinned expected {expected}",
            record={"which": which, "expected_readback_sha256": expected,
                    "actual_readback_sha256": actual, "result": result})
    result["readback_sha256"] = actual
    return result


def _score(which: str, mode: str, known: kagate.KnownAnswerAuthority, session) -> dict:
    got = session.score_last_transaction(
        known.frames_sha256(which), holdout=(mode == "holdout"))
    expected = known.scores(which, mode)
    if got["scores"] != expected:
        raise KnownAnswerStop(
            f"{which} {mode} scores {got['scores']} != pinned {expected}",
            record={"which": which, "mode": mode, "expected_scores": expected,
                    "actual": got})
    return got


def run_known_answer_round(authority: ex.PublishedCarrierAuthority,
                           known: kagate.KnownAnswerAuthority,
                           session) -> dict:
    """One session: no-op → candidate → score → restore → post-baseline."""
    if not isinstance(authority, ex.PublishedCarrierAuthority):
        raise KnownAnswerStop("the carrier authority is not published")
    if not isinstance(known, kagate.KnownAnswerAuthority):
        raise KnownAnswerStop("the known-answer authority is not consumer-verified")

    record = {"tool": TOOL_VERSION, "steps": []}

    def step(name: str, action) -> None:
        # Append before calling the hardware. If the call fails, the evidence still says
        # exactly which of the seven fixed steps had started and which earlier ones passed.
        entry = {"step": name, "state": "started"}
        record["steps"].append(entry)
        try:
            entry["result"] = action()
        except Exception as raised:
            entry["state"] = "stopped"
            entry["stop_reason"] = f"{type(raised).__name__}: {raised}"
            if isinstance(raised, KnownAnswerStop) and raised.record is not None:
                entry["failure_evidence"] = raised.record
            raise KnownAnswerStop(
                f"{name} stopped: {raised}", record=record,
                cause=(raised.cause or raised)
                if isinstance(raised, KnownAnswerStop) else raised) from raised
        entry["state"] = "passed"

    step("no_op", lambda: _write("restore", authority, known, session))
    step("known_answer", lambda: _write("candidate", authority, known, session))
    for mode in ("train", "holdout"):
        step(f"candidate_{mode}",
             lambda mode=mode: _score("candidate", mode, known, session))
    step("restore", lambda: _write("restore", authority, known, session))
    for mode in ("train", "holdout"):
        step(f"post_baseline_{mode}",
             lambda mode=mode: _score("restore", mode, known, session))
    record["verdict"] = "KNOWN-ANSWER ROUND PASSED"
    return record


def _write_evidence(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # These are logistics, not authority. In particular there is no --run-dir or
    # --artifact: both authorities below are fixed in reviewed source and exact HEAD.
    parser.add_argument("--port", default="/dev/ebaz-uart")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    record: dict = {
        "tool": TOOL_VERSION,
        "what": "Claim B round 1 known-answer mutation, scoring, restore, and baseline",
        "carrier_run": str(cal.DEFAULT_RUN.relative_to(REPO)),
        "started_at": time.time(),
    }
    transport = None
    failed = False
    try:
        # Both judges are loaded and bound to HEAD before anything touches the board.
        authority = ex.PublishedCarrierAuthority.load(cal.DEFAULT_RUN)
        known = kagate.KnownAnswerAuthority.load()
        bundle = json.loads((cal.DEFAULT_RUN / "carrier_run.json").read_text("utf-8"))
        record["authority"] = {
            "carrier_manifest_sha256": authority.manifest_sha256,
            "known_answer_artifact_sha256": kagate.PRODUCTION_ARTIFACT_SHA256,
            "run_id": bundle.get("run_id"),
        }

        # Reuse the production no-op setup verbatim. It pins FCLK0 and invokes the loader
        # with --require-unconfigured; reproducing either sequence here would create drift.
        record["setup"] = cal.phase_setup(
            args.port, cal.DEFAULT_RUN / "carrier.bit",
            bundle["artifacts"]["carrier.bit"]["sha256"])

        # The session that proves identity is the session that writes and arms. The
        # instrumentation wraps it before construction, so every command is evidence.
        transport = cal.InstrumentedTransport(ident.SerialTransport(args.port), record)
        session = ident.BoardSession(transport)
        identity = session.verify_identity("content")
        record["identity"] = identity["parsed"]
        record["same_boot"] = {
            "expected_plmark": record["setup"]["plmark"], "passed": False}
        axi.same_boot(transport, record["setup"]["plmark"])
        record["same_boot"]["passed"] = True
        transport.mark("before run_known_answer_round")
        record["round"] = run_known_answer_round(authority, known, session)
        record["verdict"] = "KNOWN-ANSWER BOARD ROUND PASSED"
    except Exception as stop:  # every refusal must leave evidence, not just a traceback
        if isinstance(stop, KnownAnswerStop) and stop.record is not None:
            record["round"] = stop.record
        cause = stop.cause if isinstance(stop, KnownAnswerStop) else stop
        if transport is not None and isinstance(cause, axi.AxiRefusal):
            try:
                record["interrupt_reply"] = transport.interrupt().decode(
                    "ascii", "replace")
            except Exception as interrupt_error:  # preserve the first failure
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
                # A disconnect while closing is still part of this run. Never let it mask
                # the first stop, and never print PASS after losing the transport.
                record["transport_close_error"] = (
                    f"{type(close_error).__name__}: {close_error}")
                if not failed:
                    record["verdict"] = "STOP"
                    record["stop_reason"] = (
                        "transport close failed after the round: "
                        f"{type(close_error).__name__}: {close_error}")
                    failed = True

    record["finished_at"] = time.time()
    _write_evidence(args.out, record)
    if failed:
        print(f"  evidence: {args.out}", file=sys.stderr)
        return 1
    print("KNOWN-ANSWER BOARD ROUND PASSED")
    print("  no-op, candidate train/holdout, restore, baseline train/holdout")
    print(f"  evidence: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

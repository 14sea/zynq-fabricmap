#!/usr/bin/env python3
"""The reviewed Claim B known-answer chain; no command-line device entrypoint.

The callable is intentionally boring: base no-op, candidate, two scorer modes, restore,
two scorer modes.  Payload construction and expected results come only from the published
known-answer authority.  Hardware execution remains a separate user ruling.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import board_carrier_exec as ex  # noqa: E402
import board_uboot_axi as axi  # noqa: E402
import gate_claimb_known_answer as kagate  # noqa: E402

TOOL_VERSION = "board_claimb_known_answer.py/1.0.0"


class KnownAnswerStop(Exception):
    """A dry-run or hardware round failed closed."""


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
            f"{which} readback SHA {actual} != pinned expected {expected}")
    result["readback_sha256"] = actual
    return result


def _score(which: str, mode: str, known: kagate.KnownAnswerAuthority, session) -> dict:
    got = session.score_last_transaction(
        known.frames_sha256(which), holdout=(mode == "holdout"))
    expected = known.scores(which, mode)
    if got["scores"] != expected:
        raise KnownAnswerStop(
            f"{which} {mode} scores {got['scores']} != pinned {expected}")
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
    record["steps"].append({"step": "no_op", "result": _write(
        "restore", authority, known, session)})
    record["steps"].append({"step": "known_answer", "result": _write(
        "candidate", authority, known, session)})
    for mode in ("train", "holdout"):
        record["steps"].append({"step": f"candidate_{mode}", "result": _score(
            "candidate", mode, known, session)})
    record["steps"].append({"step": "restore", "result": _write(
        "restore", authority, known, session)})
    for mode in ("train", "holdout"):
        record["steps"].append({"step": f"post_baseline_{mode}", "result": _score(
            "restore", mode, known, session)})
    record["verdict"] = "KNOWN-ANSWER ROUND PASSED"
    return record

#!/usr/bin/env python3
"""Structural gate for the fixed, non-scoring post-fault capture CLI."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import gate_claimb_board_driver as board_gate  # noqa: E402

DRIVER = REPO / "scripts/board_claimb_postfault_capture.py"
SETUP = REPO / "scripts/board_calibrate_noop.py"
ROUND_NAME = "run_postfault_capture"
FORBIDDEN_REFERENCES = (
    "_score", "score_last_transaction", "arm_scorer", "CTRL_ARM", "CTRL_MODE_HOLDOUT",
    "run_known_answer_round",
)


def verify_sources(driver_source: str, setup_source: str) -> list[str]:
    problems = board_gate.verify_sources(
        driver_source, setup_source, round_name=ROUND_NAME)
    present = [name for name in FORBIDDEN_REFERENCES if name in driver_source]
    if present:
        problems.append(
            "the post-fault capture driver contains scoring references: " + repr(present))
    return problems


def main() -> int:
    problems = verify_sources(
        DRIVER.read_text(encoding="utf-8"), SETUP.read_text(encoding="utf-8"))
    if problems:
        print("CLAIM-B POST-FAULT CAPTURE REFUSED")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("CLAIM-B POST-FAULT CAPTURE ACCEPTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

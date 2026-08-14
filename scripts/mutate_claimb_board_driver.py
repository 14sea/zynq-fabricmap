#!/usr/bin/env python3
"""Mutation gate for the known-answer board driver's two pre-write boot interlocks.

The mutations are applied only to strings in memory. Each anchor must occur exactly once,
and the structural production gate must name a problem after the interlock is removed.
That separates "the mutant was killed" from "the mutation never happened".
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import gate_claimb_board_driver as gate  # noqa: E402

DRIVER = REPO / "scripts/board_claimb_known_answer.py"
SETUP = REPO / "scripts/board_calibrate_noop.py"

MUTANTS = {
    "skip_same_boot": (
        "driver",
        '        axi.same_boot(transport, record["setup"]["plmark"])\n',
        ""),
    "skip_require_unconfigured": (
        "setup",
        '          "--require-unconfigured"],\n',
        "          ],\n"),
}


def main() -> int:
    original = {
        "driver": DRIVER.read_text(encoding="utf-8"),
        "setup": SETUP.read_text(encoding="utf-8"),
    }
    killed = 0
    for name, (which, anchor, replacement) in MUTANTS.items():
        if original[which].count(anchor) != 1:
            print(f"{name}: HARNESS ERROR anchor occurs {original[which].count(anchor)} times")
            continue
        sources = dict(original)
        sources[which] = sources[which].replace(anchor, replacement)
        problems = gate.verify_sources(sources["driver"], sources["setup"])
        if problems:
            print(f"{name}: KILLED — {problems[0]}")
            killed += 1
        else:
            print(f"{name}: SURVIVED")
    print(f"{killed}/{len(MUTANTS)} board-driver mutants killed")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

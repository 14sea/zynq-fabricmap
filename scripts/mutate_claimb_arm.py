#!/usr/bin/env python3
"""Mutation gate for the only Claim B scorer-arm path.

Each mutant removes one reviewed interlock.  A mutant is killed only when a behavioural
probe observes the unsafe result; string presence is used solely to ensure the requested
mutation actually took.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
SOURCE = REPO / "scripts/board_uboot_axi.py"

MUTANTS = {
    "no_capability": (
        "if capability is not SCORE_CAPABILITY:\n        raise AxiRefusal(\"arm_scorer is reachable only through BoardSession\")",
        "if False and capability is not SCORE_CAPABILITY:\n        raise AxiRefusal(\"arm_scorer is reachable only through BoardSession\")"),
    "no_readback_hash": (
        "if actual != expected_readback_sha256:\n        raise AxiRefusal(",
        "if False and actual != expected_readback_sha256:\n        raise AxiRefusal("),
    "no_configuration_valid": (
        "if not status[\"configuration_valid\"]:\n        raise AxiRefusal(\"configuration_valid is clear; the scorer remains unarmed\")",
        "if False and not status[\"configuration_valid\"]:\n        raise AxiRefusal(\"configuration_valid is clear; the scorer remains unarmed\")"),
    "ignore_recovery": (
        "if status[\"recovery_required\"]:\n        raise AxiRefusal(\"recovery_required is set; the scorer remains unarmed\")",
        "if False and status[\"recovery_required\"]:\n        raise AxiRefusal(\"recovery_required is set; the scorer remains unarmed\")"),
    "drop_holdout_mode": (
        "CTRL_ARM | (CTRL_MODE_HOLDOUT if holdout else 0)",
        "CTRL_ARM | (0 if holdout else 0)"),
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def fake_board_class():
    return load_module(REPO / "tests/test_board_uboot_axi.py", "claimb_mutant_fixture").FakeBoard


def killed(module, mutant: str) -> bool:
    board = fake_board_class()()
    board.recovery = False
    board.config_valid = True
    board.rb_frames_ok = 15
    board.score_queue = [[23, 10, 12, 12, 12, 14]]
    frames = {far: [0] * 101 for far in range(15)}
    transaction = {"readback_frames": frames}
    expected = module._frames_hash(frames)
    capability = getattr(module, "SCORE_" + "CAPABILITY")

    if mutant == "no_capability":
        capability = object()
    elif mutant == "no_readback_hash":
        expected = "0" * 64
    elif mutant == "no_configuration_valid":
        board.config_valid = False
    elif mutant == "ignore_recovery":
        board.recovery = True

    try:
        getattr(module, "arm_" + "scorer")(
            capability, board, transaction, expected,
            holdout=(mutant == "drop_holdout_mode"))
    except Exception:
        pass
    arm_lines = [line for line in board.lines if "mw.l" in line and " 0x40 1" in line or
                 "mw.l" in line and " 0xc0 1" in line]
    if mutant == "drop_holdout_mode":
        return bool(arm_lines) and not any(" 0xc0 1" in line for line in arm_lines)
    # Each of the other mutants is killed when the forbidden arm write is observable.
    return bool(arm_lines)


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    killed_count = 0
    with tempfile.TemporaryDirectory(prefix="claimb-arm-mutants-") as temp:
        root = Path(temp)
        for index, (name, (anchor, replacement)) in enumerate(MUTANTS.items()):
            if source.count(anchor) != 1:
                print(f"{name}: HARNESS ERROR anchor occurs {source.count(anchor)} times")
                continue
            path = root / f"board_uboot_axi_{index}.py"
            path.write_text(source.replace(anchor, replacement), encoding="utf-8")
            module = load_module(path, f"claimb_arm_mutant_{index}")
            if killed(module, name):
                print(f"{name}: KILLED")
                killed_count += 1
            else:
                print(f"{name}: SURVIVED")
    print(f"{killed_count}/{len(MUTANTS)} arm mutants killed")
    return 0 if killed_count == len(MUTANTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Mutation gate for the fixed post-fault capture's stop and boot interlocks."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import gate_claimb_postfault_capture as gate  # noqa: E402

DRIVER = REPO / "scripts/board_claimb_postfault_capture.py"
SETUP = REPO / "scripts/board_calibrate_noop.py"


def load_source(source: str, name: str):
    path = Path(tempfile.mkdtemp(prefix="claimb-postfault-mutant-")) / f"{name}.py"
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluation_attempts(module) -> tuple[int, list[str]]:
    authority = object.__new__(module.ex.PublishedCarrierAuthority)
    known = object.__new__(module.kagate.KnownAnswerAuthority)
    with (mock.patch.object(module.known_driver, "_write",
                            side_effect=[{"which": "restore"}, {"which": "candidate"}]),
          mock.patch.object(module.known_driver, "_score",
                            return_value={"scores": []}) as evaluate):
        record = module.run_postfault_capture(authority, known, object())
    return evaluate.call_count, [step["step"] for step in record["steps"]]


def main() -> int:
    driver = DRIVER.read_text(encoding="utf-8")
    setup = SETUP.read_text(encoding="utf-8")
    killed = 0
    total = 3

    anchor = (
        '    step("known_answer", "candidate")\n'
        '    record["verdict"] = "KNOWN-ANSWER PASSED; REQUESTED FAULT STATE WAS NOT CREATED"')
    replacement = (
        '    step("known_answer", "candidate")\n'
        '    known_driver._score("candidate", "train", known, session)\n'
        '    record["verdict"] = "KNOWN-ANSWER PASSED; REQUESTED FAULT STATE WAS NOT CREATED"')
    if driver.count(anchor) != 1:
        print(f"continue_to_evaluation: HARNESS ERROR anchor occurs {driver.count(anchor)} times")
    else:
        baseline_attempts, baseline_steps = evaluation_attempts(load_source(driver, "baseline"))
        mutant_attempts, mutant_steps = evaluation_attempts(
            load_source(driver.replace(anchor, replacement), "continue_to_evaluation"))
        if (baseline_attempts == 0 and baseline_steps == ["no_op", "known_answer"]
                and mutant_attempts > 0 and mutant_steps == baseline_steps):
            print("continue_to_evaluation: KILLED — the success-path probe observed "
                  f"{mutant_attempts} forbidden evaluation attempt(s)")
            killed += 1
        else:
            print("continue_to_evaluation: SURVIVED — "
                  f"baseline={baseline_attempts}/{baseline_steps}, "
                  f"mutant={mutant_attempts}/{mutant_steps}")

    structural = {
        "skip_same_boot": (
            "driver",
            '        axi.same_boot(transport, record["setup"]["plmark"])\n',
            ""),
        "skip_require_unconfigured": (
            "setup",
            '          "--require-unconfigured"],\n',
            "          ],\n"),
    }
    originals = {"driver": driver, "setup": setup}
    for name, (which, before, after) in structural.items():
        if originals[which].count(before) != 1:
            print(f"{name}: HARNESS ERROR anchor occurs {originals[which].count(before)} times")
            continue
        sources = dict(originals)
        sources[which] = sources[which].replace(before, after)
        problems = gate.verify_sources(sources["driver"], sources["setup"])
        if problems:
            print(f"{name}: KILLED — {problems[0]}")
            killed += 1
        else:
            print(f"{name}: SURVIVED")

    print(f"{killed}/{total} post-fault capture mutants killed")
    return 0 if killed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

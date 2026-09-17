#!/usr/bin/env python3
"""Discrimination probe for the lifecycle-2 plan-stage guard.

This is read-only.  It stubs the live pin check for the same reason as the
branch's pre-repin diagnostic: the edited test is deliberately outside the
old frozen pin table.  The result is diagnostic evidence, never a proof.
"""
from __future__ import annotations

import copy
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "host"), str(ROOT / "tests")]

import b2_pins

pin_stub = mock.patch.object(b2_pins, "verify", return_value={"files_verified": 0})
pin_stub.start()
import test_b2_plan as subject


plan_bytes = subject.PLAN.read_bytes()
plan = json.loads(plan_bytes)
manifest = json.loads(subject.MANIFEST.read_text())

sessions_wrong = copy.deepcopy(manifest)
sessions_wrong["plan"]["sessions"] += 1
records_wrong = copy.deepcopy(manifest)
records_wrong["plan"]["total_records"] += 1

current = {
    "baseline": subject.split_findings(plan, plan_bytes, manifest),
    "sessions_wrong": subject.split_findings(plan, plan_bytes, sessions_wrong),
    "total_records_wrong": subject.split_findings(plan, plan_bytes, records_wrong),
}

original = subject.split_findings


def without_summary_guards(plan_doc, raw, manifest_doc):
    """Mutation: remove both new pin-summary findings, leaving status and digest intact."""
    return [
        finding
        for finding in original(plan_doc, raw, manifest_doc)
        if "sessions, the pin records" not in finding
        and "records, the pin records" not in finding
    ]


subject.split_findings = without_summary_guards
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
    unittest.defaultTestLoader.loadTestsFromTestCase(subject.StageCoverage)
)

print(json.dumps({
    "current_implementation": current,
    "mutation": "remove the sessions and total_records comparisons from split_findings",
    "stage_coverage": {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "mutant_survived": result.wasSuccessful(),
    },
    "diagnostic_only": True,
}, indent=2, sort_keys=True))

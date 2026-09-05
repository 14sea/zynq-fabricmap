#!/usr/bin/env python3
"""B1 — the clean-tree test report, FAIL-CLOSED (the round 1′ tool with the B1 artifact set).

    b1_test_report.py [--out-dir evidence/b1/tests]

Runs the whole suite from a CLEAN tree and writes `test_report_<UTC>.json` with the counts,
the result line, `head_at_run`, the dirty flag, the instrument checkout's commit and dirty
flag, and the sha256 of every B1 artifact the suite pinned — the manifest, the pin table,
the plan, the prediction, the preregistration, the build evidence, the carrier build
record, the carrier manifest and the schema. A report with `worktree_dirty: true` or
`skipped > 0` is not the package's clean-tree proof, and the package says so.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import claimb_r1p_test_report as base  # noqa: E402

B1_ARTIFACTS = ("manifests/b1_manifest.json", "manifests/b1_instrument_pins.json", "manifests/claimb_round1prime_instrument_pins.json",
                "evidence/b1/plan.json", "evidence/b1/prediction.json", "evidence/b1/build_evidence.json",
                "builds/b1/b1_build.json", "builds/b1/carrier_manifest.json", "builds/b1/isolation.txt",
                "docs/b1_preregistration.md", "docs/b1_carrier_contract.md", "docs/b1_carrier_qualification.md",
                "schemas/self_map_v2.schema.json", "firmware/b1/p3_data.h", "firmware/b1/IMPORT.json")


def main(argv=None) -> int:
    base.ARTIFACTS = B1_ARTIFACTS
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "evidence/b1/tests")
    a = ap.parse_args(argv)
    return base.main(["--out-dir", str(a.out_dir)])


if __name__ == "__main__":
    sys.exit(main())

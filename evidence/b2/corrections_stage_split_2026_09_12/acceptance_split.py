"""The owner's stage/split reproduction, re-expressed as ACCEPTANCE after the correction.

`evidence/b2/review_stage_split_2026_09_12/review_stage_split.py` builds an S3 at four finite
feasible rates and asserts the DEFECT: the 2807/h control passes and the other three fail with
"the slice (0, 4) is not one the plan's split gives", because `committed_args` supplied a
constant. Its README says that after the correction those negative assertions should become
acceptance assertions. This is that script with its structure unchanged — the same rates, the
same documented fixture seam, the same `StageCoverage.drive` over a real temporary manifest file —
and every case now required to PASS.

It also records the split each rate produced and the slice the corrected helper read from that
manifest's own pinned plan, so the four cases are visibly different experiments rather than four
copies of one.

The rates are synthetic fixture values with the qualification evidence and the re-adjudicator
explicitly stubbed: test readiness, never a measured rate and never a qualification. 4490.86/h is
the modelled virtual-clock artefact and is here only because the split rule accepts it.

Run from the repository root with `python3 -B`.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "host"), str(ROOT / "tests")]
import b2_manifest as bm                      # noqa: E402
import test_b2_runner as tests                # noqa: E402

out = {"qualification_is_stubbed_not_silicon": True, "cases": []}
for rate in (2807.0, 602.0, 4490.86, 6000.0):
    with patch.object(tests, "STUB_RATE", rate):
        f = tests.Fixture("S3")
    try:
        verified = bm.verify(f.manifest, readjudicate=f.stub)
        assert verified["stage"] == "S3" and verified["qualified"]
        path = f.path()
        result = tests.StageCoverage().drive(path)
        split = f.plan_doc["session_split"]
        first, count = tests.committed_slice(json.loads(path.read_text()))
        out["cases"].append({"rate": rate, "stage": verified["stage"],
                             "sessions": [s["pairs"] for s in split["sessions"]],
                             "first_slice_pairs": split["sessions"][0]["pairs"],
                             "slice_the_test_asked_for": [first, count],
                             "is_the_first_session": [first, count] == [split["sessions"][0]["pairs"][0],
                                                                       len(split["sessions"][0]["pairs"])],
                             "ran": result.testsRun, "failures": len(result.failures),
                             "errors": len(result.errors), "skipped": len(result.skipped),
                             "details": [s for _, s in result.failures + result.errors]})
    finally:
        f.close()
# THE INVERSION: the owner's script asserted failures == 1 for every case after the first.
assert all(c["failures"] == c["errors"] == 0 for c in out["cases"]), \
    json.dumps([c["details"] for c in out["cases"]], indent=1)
# and the four cases are four different splits, not four copies of one
assert len({len(c["sessions"]) for c in out["cases"]}) == 4
# with a non-first session exercised wherever the split has one
assert any(not c["is_the_first_session"] for c in out["cases"] if len(c["sessions"]) > 1)
print(json.dumps(out, indent=2))

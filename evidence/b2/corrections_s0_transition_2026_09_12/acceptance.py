"""The owner's S0 transition reproduction, re-expressed as ACCEPTANCE after the correction.

`evidence/b2/review_s0_transition_2026_09_12/review_s0_transition.py` asserts the DEFECT at
`fa0271e`: with `rn.MANIFEST` redirected at a temporary S1 manifest, the committed-manifest test
fails on the null-prereg assertion. Its own README says that after the correction "that assertion
must change to acceptance" — and the test it names no longer exists, so the script cannot simply
be re-run. This is the same flow, unchanged in structure, with the new test name and the
assertions inverted: the test must now PASS at S0 and at the S1 preview, and the old name must be
gone rather than merely green.

Same constraints as theirs: production `verify` and `freeze` only, a deep copy and a temporary
file, nothing written to the production manifest, and no board, ruling or freeze anywhere.
Run from the repository root with `python3 -B`.
"""
import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "host"), str(ROOT / "tests")]
import b2_manifest as bm                      # noqa: E402
import b2_runner as rn                        # noqa: E402
import test_b2_runner as tests                # noqa: E402

TEST = "test_the_committed_manifest_is_a_legal_stage_and_is_not_permission"
GONE = "test_the_committed_manifest_is_not_permission"

path = ROOT / "manifests/b2_manifest.json"
raw = path.read_bytes()
m = json.loads(raw)
digest = hashlib.sha256((ROOT / m["prereg"]["path"]).read_bytes()).hexdigest()
out = {"manifest_sha256": hashlib.sha256(raw).hexdigest(), "prereg_sha256": digest,
       "the_hard_coded_test_is_gone": not hasattr(tests.RefusalOrder, GONE),
       "s0_verify": bm.verify(m), "production_manifest_unchanged": None}


def run_test():
    stream = io.StringIO()
    suite = unittest.TestSuite([tests.RefusalOrder(TEST)])
    result = unittest.TextTestRunner(stream=stream).run(suite)
    return {"ran": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
            "skipped": len(result.skipped), "output": stream.getvalue()}


assert out["the_hard_coded_test_is_gone"], "the S0-only test is still present"
out["s0_test"] = run_test()
assert out["s0_test"]["failures"] == out["s0_test"]["errors"] == 0
# Production freeze logic on a deep copy only; the actual S0 file is never written.
preview = bm.freeze(copy.deepcopy(m), digest)
out["s1_preview_verify"] = bm.verify(preview)
assert out["s1_preview_verify"]["stage"] == "S1"
with tempfile.TemporaryDirectory(prefix="b2_s0_acceptance_") as td:
    p = Path(td) / "manifest.json"
    p.write_text(bm.render(preview))
    with patch.object(rn, "MANIFEST", p):          # only the path the test reads
        out["s1_preview_test"] = run_test()
# THE INVERSION: the owner's script asserted failures == 1 here.
assert out["s1_preview_test"]["failures"] == 0, out["s1_preview_test"]["output"]
assert out["s1_preview_test"]["errors"] == 0, out["s1_preview_test"]["output"]
out["production_manifest_unchanged"] = path.read_bytes() == raw
assert out["production_manifest_unchanged"]
print(json.dumps(out, indent=2, sort_keys=True))

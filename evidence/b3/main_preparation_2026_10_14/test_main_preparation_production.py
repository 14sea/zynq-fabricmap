#!/usr/bin/env python3
"""The production path of restore_rejudge.py over REAL evidence: the committed B3Q -02 session
(evidence/b3/b3q_17A6_2026-10-14-02, PASS, the S2 calibration's source) is archived in form (c) into a temporary
directory (no external backup), freshly restored and re-judged with the PRODUCTION seams — the production
authority (`b3_manifest.verify` with the production B3Q re-adjudicator, `b3_pins.verify`), the production instrument
(`b1_session` / the pinned psoracle checkout), the production `judge_session` — and must ACCEPT with the verdict
equal to the archived adjudication.json key for key. Run in its OWN process, never in the same process as
test_main_preparation.py (whose fixtures patch the runner's B1-manifest path process-wide — the first defect of
docs/b3_s2_proof_exception_2026_10_14.md):

    python3 -B evidence/b3/main_preparation_2026_10_14/test_main_preparation_production.py

Slow (the lifecycle verify re-adjudicates B3Q; the judge replays 125 records): minutes. No skip: an absent instrument
checkout, evidence directory or boundary record is a failure. Read-only on the repository.
"""
from __future__ import annotations
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parents[2]
for p in (R / "host", R / "b3/host", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import restore_rejudge as rr  # noqa: E402
import archive_session as ar  # noqa: E402

B3Q = R / "evidence/b3/b3q_17A6_2026-10-14-02"
BOUNDARY = R / "evidence/b3/principal_boundary_2026-10-14-02.json"


class TheProductionPathOverRealB3QEvidence(unittest.TestCase):
    def test_archive_restore_rejudge_equals_the_archived_verdict(self):
        self.assertTrue(B3Q.is_dir() and BOUNDARY.is_file(), "the B3Q -02 evidence and its boundary record must be in the tree")
        tmp = Path(tempfile.mkdtemp(prefix="b3prep_prod_"))
        try:
            out = tmp / "b3q_02"
            doc = ar.archive(B3Q, out, BOUNDARY, None, HERE / "restore_rejudge.py", root=R)
            self.assertEqual(doc["session"], "B3Q")
            self.assertEqual(sorted(p.name for p in B3Q.iterdir()), list(rr.SESSION_FILES), "the committed evidence is untouched")
            res = rr.rejudge(out, root=R)                      # ports=None, authority=None: PRODUCTION
            self.assertEqual(res["verdict"], "ACCEPT", res)
            self.assertEqual(res["steps"]["session_plan"]["rebuilt_by"], "b3_runner.qualification_session_plan")
            self.assertEqual(res["steps"]["judge"]["keys_differing_from_archived"], [])
            stored = json.loads((B3Q / "adjudication.json").read_text())
            self.assertEqual(res["steps"]["judge"]["outcome"], stored["outcome"])
            self.assertEqual(res["steps"]["judge"]["outcome"], "PASS")
            self.assertEqual(res["steps"]["judge"]["measured_rate_per_hour"], 3180.049965139327)
            self.assertEqual(res["steps"]["manifest"]["verify"]["stage"], "S1")
            self.assertEqual(res["steps"]["manifest"]["file_sha256"], "bb917ec7bde1a47da975162ff76bb27d4c6080e06a715d49f7f458e8115a23c6")
            self.assertEqual(res["steps"]["session_plan"]["expected_frames_total"], 3378)
            self.assertEqual(res["steps"]["session_plan"]["resend_budget"], 14)
            self.assertTrue(res["restored_dir_removed"])
            (HERE / "production_path_b3q_02_result.json").write_text(json.dumps(res, indent=1, sort_keys=True, default=str) + "\n")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)

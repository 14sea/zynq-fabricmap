# B2 test reports

Written by `host/b2_test_report.py`. A report is a **clean-tree proof** only when
`clean_tree_proof` is true and `proof_refusals` is empty; every other report is a record of a run.

- `test_report_2026-09-12T083954Z.json` — schema **1.0.0**, HEAD `50021e2`, 1 869 tests, zero
  skips, OK. **SUPERSEDED.** The owner's review of 2026-09-12 found the 1.0.0 verdict logic
  insufficient: it accepted logs with no result line, a bare `FAILED`, zero tests or an unparsed
  counter, and its provenance was read after the suite rather than before it. The artifact
  digests in this file were independently confirmed against `50021e2`; that review did not
  independently establish the run count or runtime clean state. The
  `clean_tree_proof` field in it was computed by that old logic and must not be cited.
- reports written under schema **2.0.0** carry `run.start` and `run.end` snapshots and a
  `proof_refusals` list, and are the ones this package cites.
- `test_report_2026-09-12T092150Z.json` — schema **2.0.0**, HEAD `12857ae`, **1 884 tests, zero
  skips, OK**, `clean_tree_proof: true` with `proof_refusals: []`. The start and end snapshots
  agree: the same HEAD, both worktrees clean, the instrument at its pinned commit and clean in
  both, the pinned surface verifying in both, and every pinned artifact digest unchanged across
  the run. Superseded by the report below, which was produced under the corrected parser.
- `test_report_2026-09-12T095607Z.json` — schema **2.0.0**, 1 893 tests, **`FAILED (failures=1)`**,
  `clean_tree_proof: false` with five refusals. Kept deliberately: it is the reporter refusing a
  REAL failing run of the real suite, end to end, which no fixture demonstrates. The failure was
  `test_evidence_manifests::test_nothing_under_evidence_is_excluded_by_gitignore`, and it was
  right — running a review probe under `evidence/` had left a `__pycache__/*.pyc` there, which
  `.gitignore` excludes, so part of the evidence tree would not have been committed. The stray
  directory was removed; nothing in the tool or the package was at fault.
- `test_report_2026-09-12T102301Z.json` — schema **2.0.0** under the corrected parser and shape
  guards, HEAD `2ed95f4`, **1 893 tests, zero skips, OK**, `clean_tree_proof: true` with
  `proof_refusals: []`, the complete `Ran 1893 tests in …s` summary and a single `OK` as the log's
  last word, the start and end snapshots agreeing on HEAD, cleanliness, the instrument, the pinned
  surface and every artifact digest. **Superseded for the current submission** by the report
  below, which was taken at the submitted HEAD.
- `test_report_2026-09-12T134616Z.json` — schema **2.0.0**, HEAD `619b22b`, **1 895 tests, zero
  skips, OK**, `clean_tree_proof: true` with `proof_refusals: []`, taken on the pushed tree that
  the §7 package is submitted from. **This is the report the package cites.**

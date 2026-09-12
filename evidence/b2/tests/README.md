# B2 test reports

Written by `host/b2_test_report.py`. A report is a **clean-tree proof** only when
`clean_tree_proof` is true and `proof_refusals` is empty; every other report is a record of a run.

- `test_report_2026-09-12T083954Z.json` — schema **1.0.0**, HEAD `50021e2`, 1 869 tests, zero
  skips, OK. **SUPERSEDED.** The owner's review of 2026-09-12 found the 1.0.0 verdict logic
  insufficient: it accepted logs with no result line, a bare `FAILED`, zero tests or an unparsed
  counter, and its provenance was read after the suite rather than before it. The run and the
  artifact digests in this file were independently confirmed against `50021e2`; the
  `clean_tree_proof` field in it was computed by that old logic and must not be cited.
- reports written under schema **2.0.0** carry `run.start` and `run.end` snapshots and a
  `proof_refusals` list, and are the ones this package cites.

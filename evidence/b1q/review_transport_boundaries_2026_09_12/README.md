# Transport boundary review evidence

Reviewed `38c91b0` on 2026-09-12. These are offline software observations only.

- `probe_boundaries.py`: independent probes for a side-effecting writer failure,
  cutoff damage versus in-flight censoring, early-stop completion status, late
  drain cutoff and analyser failure. Includes intact-stream and complete-run
  positive controls. Only temporary export directories are created and removed.
- `observed.json`: original output. Repetition details and persisted summaries
  are retained, including defective values, for comparison after a fix.
- `submitted_acceptance.json`: current submitter acceptance rerun unchanged,
  exit 0; these controls do not cover the new boundary probes.
- `tests.log`: independently captured 73-test run, zero skips, OK, 63.181 s.
- `bindings.json`: production B2 verify and live manifest/table/prereg digests.

From the repository root, run
`python3 -B evidence/b1q/review_transport_boundaries_2026_09_12/probe_boundaries.py`
and save new output separately. No serial device is opened. The suite's PTY
checks use software terminals only. No production state or pinned input changes.

See [the review](../../../docs/b1q_transport_boundaries_review_2026_09_12.md).

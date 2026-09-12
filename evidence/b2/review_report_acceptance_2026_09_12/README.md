# B2 reporter acceptance evidence

Reviewed HEAD: `b5571f0`; reporter correction `8756149`.

- `probe_after.json`: the unchanged previous review probe against the corrected code.
  Positive proof retained; all five former log gaps and all malformed input cases
  refused. Prior provenance, CLI and predicate-mutation controls remain effective.
- `tests.log`: independent reporter suite, 35 tests, OK.
- `bindings_and_shapes.json`: current live snapshot, historical Git artifact comparisons
  and verdict recomputation for both new reports, plus 36 nested-block shape cases at
  both endpoints. All artifact comparisons match; every shape case refuses.

Reproduce the primary acceptance and unit suite with:

```sh
python3 -B evidence/b2/review_test_report_v2_2026_09_12/probe_report_v2.py /home/test/zynq_fabricmap
python3 -B -m unittest discover -s tests -p test_b2_test_report.py
```

The primary probe uses controlled archived snapshots and synthetic log strings as
API inputs, not new test-run proofs or silicon evidence. Its mutation modules exist
only in memory. `-B` avoids introducing bytecode files beneath the evidence tree.
Bindings were checked before this review made the working tree dirty. The full
1,893-test suite was not rerun; the submitted report's count is not independently
re-established by these focused checks. No ports, firmware builds or rulings were used.

# B2 reporter review artifacts — 2026-09-12

Reviewed HEAD: `942a5b8555eab55632dc9c0dc64c502fb137a062`.

- `probe_report.py`: real CLI parser/import cases; expected I/O failure cases;
  controlled normal-run state-observation ordering; in-memory production-predicate
  mutation; historical artifact hashes checked directly against Git.
- `results.json`: complete findings, controls, traces, mutation-test output and paths.
- `generated_reports/`: exact reviewer-generated JSON outputs. **These include false
  positive proof flags produced from synthetic logs. They are counterexamples, not
  test-run proofs.**
- `targeted_tests.log`: eleven reporter tests, independently green.
- `preserved_inputs.json`: actual 71/105 pin verification, build check and hashes.

To reproduce on a clean checkout of the reviewed revision with the existing instrument
available:

```sh
python3 evidence/b2/review_test_report_2026_09_12/probe_report.py
```

The script requires an initially clean worktree so the missing proof conditions are
not hidden by unrelated dirt. It writes only to temporary directories. It does not
run the whole repository suite, edit the actual reporter/pins, open a port, or consume
an authorization. The ordinary CLI parser probes use real Git/pins; the normal-run
ordering probe explicitly doubles the suite boundary and Git history. The predicate
mutation changes only an in-memory module for the eleven-test check.

The script's first draft of the auxiliary empty-discovery control assumed exit 0.
This environment returns exit 5 and `NO TESTS RAN`; the saved probe records that actual
behavior separately. The zero-tests/OK import case remains an explicitly synthetic
fixture. No production file was changed to obtain the results.

See [the review](../../../docs/b2_test_report_review_2026_09_12.md).

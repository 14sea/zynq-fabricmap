# B2 reporter schema 2.0.0 review — 2026-09-12

Reviewed HEAD: `a52c22907d203c8a775d76428e4114d45a530ec5`, twenty-nine
commits ahead of origin/main. The checkout was clean before review artifacts were
written. This is an offline review, not a firmware, freeze or hardware approval.

**HOLD: one P2 remains in log validation.** Execution provenance, imported-report
handling, the previously reported I/O cases, and the test-method correction are
accepted. A P3 remains in the claimed handling of malformed internal run records.

## P2: incomplete or contradictory summaries still become proofs

At `host/b2_test_report.py:129`, the expression matches only the prefix
`Ran N tests in `, without validating the duration or the complete line. At lines
130–131, the last result line silently replaces earlier results. No check requires
one result line after the unique complete run summary.

The reproduction passes controlled execution records through the production
`build` and `proof_refusals`, with valid archived schema-2 start/end snapshots,
`executed=True`, and exit status zero. Only the log changes from the positive
control. These are synthetic API inputs, not new suite executions or silicon evidence.

| Log | Actual proof | Expected |
|---|---|---|
| `Ran 4 tests in 1.000s` followed by `OK` | true | Positive control |
| `Ran 4 tests in ` followed by `OK` | **true** | Refuse missing duration |
| `Ran 4 tests in nonsense` followed by `OK` | **true** | Refuse malformed duration |
| Valid Ran line, `FAILED (failures=1)`, then `OK` | **true** | Refuse contradictory results |
| Valid Ran line, then two `OK` lines | **true** | Refuse ambiguous result count |
| `OK` before the valid Ran line | **true** | Refuse reversed summary order |

All five negative cases have an empty `proof_refusals` list. The earlier missing
result, bare FAILED, zero count, short truncated Ran, unknown skip counter and two
complete Ran lines are now refused. Closing those examples did not fully close the
parser contract. This finding does not claim that ordinary unittest execution
normally returns zero for a failed run, or that `--no-run` still produces proofs.

Validate the whole supported Ran-line grammar, including elapsed time, and require
one coherent, correctly ordered result. Reject contradictory or duplicate summaries
before assigning zero counters. Add these cases through the actual proof builder
with otherwise qualifying execution provenance: testing only `--no-run` would hide
the parser defect behind its independently correct no-proof restriction.

## P3: malformed nested run fields still escape as AttributeError

At `host/b2_test_report.py:225`, a non-string log is replaced by an empty string for
parsing, but line 231 hashes the original value using `.encode()`. Consequently
`build({"log": None})`, array/integer/object logs, and the supported legacy tuple
`(0, None)` raise rather than producing a named, never-proof report.

Likewise, a nonempty list in `run.start.instrument` or `run.start.pins` reaches
unguarded `.get()` calls in `proof_refusals`. The top-level run guard is not a
complete shape guard for the fields the builder consumes.

Validate and retain one log value for both parsing and hashing, and establish the
shape of nested snapshot blocks before using them. Invalid input must remain named
and unable to establish proof. Do not hide unrelated implementation defects behind
a broad exception handler. This is P3 because the normal `run_suite` producer emits
text and structured snapshots; the demonstrated failures concern malformed internal
API inputs, not a demonstrated failure of the normal subprocess path.

## Corrections accepted

- An independent controlled ordering probe observes `snapshot → execute → snapshot`.
  Dirty-start/clean-end, changed HEAD, and unobserved execution all refuse proof.
- The real `--no-run` CLI returns a report with proof false. Missing parameters,
  a missing log, and an output path occupied by a file return exit 3 without a
  traceback. The previous provenance and I/O findings are closed for those scopes.
- The unchanged reporter suite runs **26 tests, OK**. Its tests now drive production
  predicates. Disabling each condition in an in-memory module produces failures:
  worktree cleanliness 3, result line 1, executed flag 6, HEAD stability 1, with no
  errors. Counts differ from the submitted mutation method, but all four conditions
  are detected. No production source or pin table was changed for these probes.

## Submitted report: confirmed facts and limits

`evidence/b2/tests/test_report_2026-09-12T092150Z.json` declares 1,884 tests, zero
skips/failures/errors, OK, and execution at
`12857ae2fe4b601954fbeacfd409815bb48c1b63`. Its start and end snapshots agree except
for timestamp. All thirteen non-null artifact digests match Git blobs at that HEAD;
the fourteenth entry correctly records the absent B2 manifest. Recomputing the
current predicate over the archived report yields no refusals.

This supports the archived artifact binding and endpoint consistency. This review
did not rerun the full 1,884-test suite or independently reproduce its raw log
digest. Endpoint equality does not observe every intermediate filesystem state.
The parser counterexamples do not establish that the submitted run failed or that
its reported count is false. Preserve the JSON unchanged; repair the predicate and
generate a new report before relying on it for package readiness.

Documentation should preserve the same distinction. The tests README currently says
the old report's “run and the artifact digests” were independently confirmed. The
previous review confirmed artifact hashes, and explicitly did not independently
establish the old run count or runtime clean state. Narrow that sentence accordingly.
The current package banner also says 25 reporter tests; the actual count is 26.

## Next step

Close the parser finding and the small internal-input guard gap, regenerate pins
after the final pinned edit, and capture the replacement report from a clean tree.
Then proceed with the already specified run-independent B2Q contract at S0/S1 and
the complete package review. Prior offline integration acceptances remain in scope.
This review neither changes those requirements nor authorizes a board session.

Reproduction and results: [review evidence](../evidence/b2/review_test_report_v2_2026_09_12/README.md).

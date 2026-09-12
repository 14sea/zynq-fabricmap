# The reporter's parser contract and nested shape guards — corrected, 2026-09-12

The owner's second reporter review (`docs/b2_test_report_v2_review_2026_09_12.md`, against
`a52c229`) accepted the snapshots, the `--no-run` restriction, the I/O contract and the corrected
test method, and left one P2 and one P3. Both are corrected; `review_probe_after.json` is that
review's own `probe_report_v2.py`, **unchanged and run to completion** on the corrected tool.

## P2 — incomplete or contradictory summaries still became proofs

The parser matched only the prefix `Ran N tests in `, and the LAST result line silently replaced
earlier ones. `parse_log` now requires the **whole** of both lines, exactly one of each, in that
ORDER, with the result line last:

| the review's log | before | now |
|---|---|---|
| `Ran 4 tests in ` then `OK` | true | `no complete 'Ran N tests in X.XXXs' line` |
| `Ran 4 tests in nonsense` then `OK` | true | the same |
| valid `Ran`, `FAILED (failures=1)`, then `OK` | true | `the log carries 2 result lines …: which result is this?` **and** `the log carries a FAILED result line` |
| valid `Ran`, then two `OK` lines | true | `the log carries 2 result lines …` |
| `OK` before the valid `Ran` line | true | `the result line comes before the run summary` |
| a result line that is not the log's last word | (unspecified) | `the result line is not the last thing the log says` |

Its positive control still proves, and the previous round's six refusals are unchanged.

## P3 — malformed nested fields escaped as AttributeError

A non-string log was replaced by `""` for parsing while the **original** was hashed, and a
non-empty list in `run.start.instrument` or `.pins` reached unguarded `.get()` calls. There is now
ONE log value used for both parsing and hashing, and the nested snapshot blocks — `instrument`,
`pins` and `artifacts_sha256` — have their shapes established before any field is read out of
them. `None`, arrays, integers, objects, bytes and the legacy `(0, None)` tuple all produce a
named, never-a-proof report.

## Discrimination

Deleting a production condition and re-running the tests: the `Ran`-line full match fails **16
tests and errors 28 more**, the one-result-line rule **3**, the ordering rule **2**, the
any-FAILED rule **2**, the log-is-text guard **8**, and the pins shape guard **5**. The review's
own predicate mutations report 6, 3, 1 and 1 failures for executed / worktree-clean / result-line
/ head-stability.

**35 reporter tests, B2/B3 437, zero skips.** The archived 2.0.0 report re-verifies: the probe
recomputes its proof with no refusals and finds its start and end snapshots equal except for their
timestamps.

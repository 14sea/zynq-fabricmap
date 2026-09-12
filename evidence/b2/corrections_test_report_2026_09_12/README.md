# The reporter's proof mechanism — corrected, 2026-09-12

The owner's test-report review (`docs/b2_test_report_review_2026_09_12.md`, against `942a5b8`)
found two P2s and a P3 in `host/b2_test_report.py`, and — separately — that its eleven tests
passed against a build with the clean-tree conditions removed. All four are corrected; the schema
migrates **`b2_test_report` 1.0.0 → 2.0.0**.

## P2-1 — incomplete or contradictory logs reached `clean_tree_proof: true`

`parse_log` now demands a COMPLETE successful summary, and `proof_refusals` names what is missing:

| the review's log | before | now |
|---|---|---|
| `Ran 1869 tests …` with no result line | true | `the log carries no OK or FAILED result line` |
| `Ran 1869 tests …` then a bare `FAILED` | true | `the log's own result line says FAILED` |
| `Ran 0 tests …` then `OK` | true | `the log records zero tests` |
| truncated `Ran 1869` alone | true | `no complete 'Ran N tests in ...' line` |
| `OK (skipped=unknown)` after a count | true | `the result line carries an unparsed counter 'skipped=unknown'` |
| two `Ran` lines in one log | (unspecified) | `the log carries 2 'Ran' lines: which run is this?` |

An unparsed counter is an **unknown**, and an unknown is never a zero: the counters are only read
from a result line this tool fully understands, and `result_line` must be exactly `OK`.

## P2-2 — the provenance described report time, not the run

`run_suite` now takes a snapshot **before** the suite starts and another when it ends, and the
report carries both under `run.start` / `run.end`. `head_at_run` is the start snapshot's HEAD.
The verdict requires the two to agree: the same HEAD and root, both worktrees clean, the
instrument at its pinned commit and clean in **both**, the pinned surface verifying in **both**,
and every pinned artifact digest unchanged across the run. The review's ordering probe — a dirty
start with a clean finish — is now refused by name.

A `--no-run` report reconstructs a verdict from a log whose run this tool did not observe, so it
is **never a proof**, however clean the tree is now. It still writes a report, and the first
refusal says why.

## P3 — I/O failures outside the guarded write

The `--no-run` log read and the output-directory creation are inside the boundary now: a missing
log, missing arguments and an output path that is already a regular file all print `EXIT 3:` and
exit 3, with no traceback. Unrelated implementation exceptions are still not converted into input
errors.

## The test method, which is the finding behind the findings

The previous file copied the condition list into the test, so removing a production condition left
all eleven passing. Every case now drives `b2_test_report.build` / `proof_refusals` themselves,
from a qualifying positive control with exactly one condition removed. Measured: deleting the
worktree-clean check fails **4** tests, the result-line check **2**, the executed-by-this-tool
check **3**, and the HEAD-stability check **2**. **25 tests**, and the B2/B3 suite is 427.

## The superseded report

`evidence/b2/tests/test_report_2026-09-12T083954Z.json` was written under schema 1.0.0, whose
verdict logic this review found insufficient. Its artifact digests were independently confirmed
against `50021e2` and its 1 869-test run is not in question, but **its `clean_tree_proof: true`
was computed by the old logic** and is superseded by the report written under 2.0.0. Evidence is
not rewritten; it is superseded, and `evidence/b2/tests/README.md` says so.

## The review's own probe, re-run

`review_probe_after.json` is `probe_report.py`'s own output on the corrected tool. **All eight of
its log fixtures now give `clean_tree_proof: false`** — including its valid four-test summary,
because that is a `--no-run` report and a reconstructed report is never a proof — and both of its
I/O cases exit **3**. Its ordering probe reports `proof: false` as well.

Two limits of that re-run, stated rather than glossed:

* its ordering probe doubles `run_suite` entirely, which is where the start snapshot now lives, so
  it observes `git_reads_before_suite: 0` by construction. What it establishes is that a run this
  tool did not observe is not a proof. The dirty-start/clean-finish semantics it was written to
  expose are covered by `TheRunState.test_a_dirty_start_and_a_clean_finish`, which drives the
  production verdict directly.
* it stops at its final step, which patches the OLD module's source text to demonstrate the
  test-coverage gap; that anchor does not exist in the rewritten module. The gap itself is
  measured above by deleting production conditions.

The probe also handed `build` a `(exit_status, log)` tuple through its `run_suite` double, which
raised `AttributeError` — the same type-before-use rule again, in this tool's own inputs. `build`
is now total over a wrong-shaped run record: a tuple, a string, `None` or anything else yields a
named, never-a-proof report carrying the shape it was given.

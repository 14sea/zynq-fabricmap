# B2 test reporter and package readiness review — 2026-09-12

Reviewed HEAD: `942a5b8555eab55632dc9c0dc64c502fb137a062`; implementation
`50021e2d2a928e91f05c4709b4359de8507821fa`; twenty-four commits ahead of
`origin/main` (`0d294ea`).

**HOLD on the reporter's clean-tree proof claim: two P2 findings remain.** The five
host tools now exist, but file presence and a green unit suite do not complete the
proof contract. A smaller P3 affects the promised report-failure exit status.

## P2-1: incomplete or contradictory logs can receive clean_tree_proof=true

`host/b2_test_report.py::build` finds the first `Ran <digits>` anywhere in the log,
defaults absent failure/error/skip counters to zero, and does not require a valid
successful result line or a positive test count when computing proof.

The unchanged CLI was exercised on the actual clean reviewed checkout, with real
pin and instrument checks, temporary logs and temporary output directories. Supplied
exit status is zero except for the explicit real-failure control:

| Log input | Parsed result | clean_tree_proof |
|---|---|---|
| Complete four-test `OK` summary | `OK`, ran 4 | true (positive parser control) |
| `Ran 1869 tests ...` with no result line | null result, ran 1869 | **true** |
| `Ran 1869 tests ...` followed by bare `FAILED` | FAILED | **true** |
| `Ran 0 tests ...` followed by `OK` | OK, ran 0 | **true** |
| Truncated `Ran 1869` alone | null result, ran 1869 | **true** |
| `OK (skipped=unknown)` after a count | skipped defaults to 0 | **true** |
| Completely unparseable log | null count/result | false |
| Failed summary with failure count 1 and exit 1 | FAILED, failures 1 | false |

These are explicit imported-log fixtures, not claims that the current unittest runner
normally returns zero for failure or empty discovery. A separate actual empty discovery
on this environment returns exit 5 and `NO TESTS RAN`; its output is recorded for that
distinction. The defect is that the report accepts an inconsistent/incomplete supplied
summary as proof instead of validating it against the supplied status.

Require a coherent, fully parsed unittest result, positive test count, recognized
counter syntax, successful outcome and agreement with process status. Missing or
malformed counters must not silently establish zero failures/skips. Retain raw log
bytes or their digest alongside the parsed result.

The tests' ten-condition matrix does not exercise the production predicate for each
case: it edits a returned dictionary and evaluates a separately copied `_proof`
expression. In an independent mutation check, removing **only the worktree-clean
condition from the in-memory production builder** still leaves **all eleven tests
green**. Original checkout/pin bytes remain untouched. Replace the duplicated rule
tests with cases driving production report construction using controlled observations;
the faulty production condition must be caught.

## P2-2: reported provenance describes report time, not established test-run state

`main` calls `run_suite` first and `build` afterward. All Git observations, artifact
hashes and pin verification occur in `build`, after execution. No run-start snapshot
is captured and no before/after consistency check is performed. `head_at_run` therefore
means the HEAD when the report is constructed, despite its stronger description.

The `--no-run` path is more direct: an arbitrary captured log and integer exit status
are combined with the **current** clean checkout, current HEAD, current instrument,
and caller-selected focused/whole-suite label. The valid four-test fixture above is
stamped `scope: whole suite`, HEAD `942a5b8`, and proof true, with no evidence linking
that log to this revision, invocation, or clean state.

A separate normal-path ordering probe doubles only the suite boundary and observed Git
history. It represents a dirty start and a clean finish. The real CLI/report builder
makes **zero Git reads before the suite**, reports the clean finish as the run state,
and sets proof true. This is a controlled environment-history test, not a claim that
the submitted 1,869-test run actually changed trees.

Capture the actual invocation and start snapshot before executing tests, and the end
snapshot before writing the report. Bind repository root, HEAD, cleanliness, instrument
identity/state, pins and relevant artifact bytes; require the intended clean, stable
relationship before asserting proof. Use the same root for Git and artifact observations
(`build(root=...)` currently uses that root for files but default-root Git calls).
Imported logs should remain reports without proof unless accompanied by a validated
run capture that establishes those facts. Fresh report-time checks cannot reconstruct
missing run-time provenance. Record whether a report was executed or imported.

## P3: some report I/O failures escape the documented exit-3 contract

The `--no-run` log read and output-directory creation are outside the guarded write.
A missing input log, or an output path that is already a regular file, produces a
traceback and exit 1 instead of the promised exit 3. Both cases were exercised through
the real CLI. Handle these expected I/O failures at their boundary without converting
unrelated implementation exceptions into input errors.

## What was verified about the submitted report

The existing `test_report_2026-09-12T083954Z.json` declares 1,869 tests, zero skips,
failures and errors, `OK`, and run HEAD `50021e2`. Every non-null artifact digest in
that report matches the actual Git bytes at the declared HEAD. The null B2 manifest
entry also matches its absence at that commit. This supports the artifact binding;
it does not independently establish the recorded count or run-time clean state.

The eleven new reporter tests independently pass. The mutation described above also
passes all eleven, showing the specific coverage gap. The entire 1,869-test suite was
not rerun during this review; rerunning it would not repair the proof logic.

Current B2 pins verify **71** files and B1 pins verify **105**. Live build verification
returns zero findings. Image `d164cd1d…`, ELF `7de96ed2…`, and B1 manifest
`38238271…fd4ba8` retain their hashes. Prior pin-table and offline integration
acceptances remain valid within their stated scopes. Preserve the historical report
unchanged; after repairing the reporter, produce a fresh report with captured provenance.

## Work order before final package review

1. Repair the reporter, including tests over the actual proof-producing path, and
   regenerate pins after the final pinned-file edit.
2. Freeze the **run-independent B2Q contract as explicit S0 inputs**: canonical plan,
   prediction, master/pair seeds and derivation rule, audit/record/frame budgets, and
   planning-bound/deadline rules. Bind their bytes in S1. Keep invocation-specific
   manifest hashes outside documents whose digests are embedded in that manifest,
   avoiding a self-referential hash cycle.
3. Have producer, offline readjudicator and lifecycle verification consume/recheck the
   same pinned contract. Demonstrate the real S1 → modelled B2Q → S2 → S3 → fresh-process
   verification path and independent field/file mutations; keep B2's budget, seeds,
   prediction and established statistical design unchanged.
4. Produce the corrected report and present the complete current image package for
   review, followed by compatibility review and any separately authorized freeze/rulings.

The previous B2 **representative non-first-slice demonstration is already accepted**:
pairs 7/8, 2,406 scored/audited records, session PASS and no pooled primary. It need not
be repeated merely to close the same item. A complete nine-pair instrument-stack run
would be a different scope, not an unfulfilled version of that accepted demonstration.
The package banner and runner still incorrectly list the representative demonstration
as absent. Refresh the current package body as well as the banner: older statements
such as "No image" and "report comes with the image" are no longer current.

Artifacts: [independent probe, generated reports and results](../evidence/b2/review_test_report_2026_09_12/).
Generated probe reports are counterexamples, not real test-run proofs. Only English
review artifacts and the package status banner were written. No production code,
firmware, image, original evidence, manifest, real ruling or instrument file was
changed. No commit, push, ARM rebuild, port access or board action was performed.

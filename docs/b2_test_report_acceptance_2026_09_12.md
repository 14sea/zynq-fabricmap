# B2 reporter correction acceptance — 2026-09-12

Reviewed HEAD: `b5571f0`, thirty-four commits ahead of origin/main. Correction:
`8756149`. The checkout was clean at the start of this offline review.

**The remaining reporter P2 and P3 are CLOSED.** This accepts the reporter correction
and removes its blocker to the next host-only package step. It is not final package,
compatibility, freeze, push or board approval.

## Independent checks

The previous `probe_report_v2.py` was rerun unchanged with Python bytecode writing
disabled. Its valid execution-record control still produces proof. All five parser
counterexamples now produce named refusals: missing/nonnumeric elapsed time,
FAILED followed by OK, duplicate OK, and reversed summary order. Earlier log,
provenance and CLI negative controls retain their expected results.

The malformed log values, legacy `(0, None)`, and malformed nested instrument/pins
blocks now produce named non-proof reports instead of AttributeError. A further
36 independent cases vary instrument, pins and artifacts blocks at both endpoints
over null, empty/nonempty lists, integer, string and boolean values. All refuse
without throwing. Parsing and hashing now consume the same validated log value.

The unchanged reporter suite independently runs **35 tests, OK**. The prior
in-memory predicate mutations still detect removal of all four checked conditions:
worktree cleanliness 3 failures, result-line condition 1, executed flag 6, and HEAD
stability 1; no errors. The snapshot ordering remains
`snapshot → execute → snapshot`. Production source and pins were not changed.

## Current and historical reports

| Report UTC suffix | Run HEAD | Declared result | Independent check |
|---|---|---|---|
| `T095607Z` | `8756149` | 1,893 tests, FAILED (failures=1), proof false | All artifact entries match Git; endpoints agree; five refusals reproduced |
| `T102301Z` | `2ed95f4` | 1,893 tests, zero skips/errors/failures, OK, proof true | All artifact entries match Git; endpoints agree; no refusals reproduced |

The successful report records duration 774.859 seconds. For each report, thirteen
non-null artifact digests match the actual blobs at its run HEAD and the absent B2
manifest is correctly recorded as null. Start/end equality excludes observation time.
Current live pins independently verify **71 B2 / 105 B1 files**; the instrument is
clean at its pinned `689dde1` commit.

Use `test_report_2026-09-12T102301Z.json` for the corrected reporter's current package
evidence. Preserve the preceding reports, including the failed run, unchanged. The
failed report is consistent with a real exit-1, one-failure run and correctly refuses
proof. Its specific bytecode-file cause is documented by the submitter; these JSON
reports do not contain the full failure traceback for independent cause verification.

This review does not independently rerun the full 1,893-test suite or reproduce its
raw log digest. It verifies the recorded bindings and verdict consistency, and tests
the corrected report-producing logic. Endpoint observations are not continuous
filesystem monitoring. No claim is made that the older successful runs were failures.

The tests README still attributed independent confirmation of the old run itself to
the earlier review. That wording is narrowed to the artifact hashes actually checked.
This documentation correction changes no historical report bytes.

## Next work

Proceed with the already requested host-only B2Q fixed contract at S0/S1: canonical
plan/prediction, seed derivation and values, policy/budgets, and planning-bound rule.
Keep run-independent inputs separate from the eventual run-manifest binding to avoid
a self-hash cycle. Producer, preflight, offline re-adjudication and lifecycle should
consume the same pinned contract. Retain the full modelled S1 → B2Q → S2 → S3 →
fresh-process verification positive control and independent input-change refusals.

That step precedes complete §7 package review, compatibility review and freeze.
Previously accepted B2 modelled-slice evidence remains accepted within its scope.

Evidence: [acceptance outputs](../evidence/b2/review_report_acceptance_2026_09_12/README.md).

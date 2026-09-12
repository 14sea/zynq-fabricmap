# B2 stage and split correction acceptance — 2026-09-12

Reviewed HEAD: `01acb5f`, initially clean, five local commits beyond origin/main.

**The S3 slice P2 is CLOSED. The original S0-only assertion P2 remains CLOSED.**
The reviewed five commits through `01acb5f` are suitable for Claude to push. The
identified transition-test blockers to S1 are resolved. This review does not
perform the production freeze, set board_ready, issue a ruling or authorize a
board session. Existing image compatibility acceptance is unchanged.

## Independent verification

Both submitted acceptance scripts were rerun, and StageCoverage independently
ran **10 tests, zero skips, OK**. Results from the unchanged committed-manifest
test, reading each real temporary S3 manifest:

| Synthetic rate (/h) | Selected last slice | Test result |
|---|---|---|
| 2807 | `(8, 1)` | PASS |
| 602 | `(8, 1)` | PASS |
| 4490.86 | `(7, 2)` | PASS |
| 6000 | `(0, 9)` | PASS |

The first three exercise non-first sessions. `committed_slice` reads the selected
session from the manifest's pinned plan, after the committed test has verified
that manifest. No-plan stages provide no slice. The missing-ruling assertion is
retained rather than weakened to accept a refusal at any gate. Restoring `(0, 4)`
through the regression-control test still produces the expected slice failure.

Production S0 verify/test and the temporary S1 verify/test both pass; the actual
manifest is unchanged. The S2/S3 stage coverage retains its explicit fixture
qualification/re-adjudicator stub. Those synthetic rates establish test readiness,
not board throughput or genuine qualification. The full reported 451-test suite
was not redundantly rerun in this correction review.

## Current bindings

- S0 manifest: `86393ed781cb25c971aeb7a4ea3bf485b5aba5a353ef94968b3128050d5b2da1`
- B2 table: `8d6f64a5fed1fa222b2c29a0dddac6c6fd3346b23481ade1f00a3f104a907ebf`
- Prereg: `68cde86d3f3decaf9775beac94c59731ada486ebe246006e7243156c084db8e0`
- Image: `d164cd1d5b30aa5eb91f230b1373be8dda60d219249924e280957b26348d85f5`
- ELF: `7de96ed25e01199ad4405dcc59b2ec92140c27679710e6acfbbad158e4986cdc`

Hashes match the submitted values. Production verify returns S0, qualified false,
refusal null, with image bytes hashed, B1 lineage reverified, canonical B2Q inputs
checked and **71 B2 / 105 B1 pins** verified. Prereg is still unpinned/unfrozen,
board_ready false, and qualification/calibration/plan null with empty history.

## Next boundary

The S1 operation, when explicitly authorized, must use the current prereg bytes
and current S0, record the resulting actual manifest hash, and be followed by the
required clean-tree report. Temporary preview hashes are not ruling bindings.
After qualification, preserve the strict transition's frozen inputs; do not edit
pinned tests to accommodate a state that could have been tested beforehand.

No new implementation change is requested by this review. Production manifest,
pins, firmware, image, prereg, instrument and rulings were not modified. No push,
production freeze or board contact was performed. Transport stop-loss remains a
separate unresolved prerequisite to scheduling B2Q.

Evidence: [acceptance outputs](../evidence/b2/stage_transition_acceptance_2026_09_12/README.md).

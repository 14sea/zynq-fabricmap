# B2 runtime freshness correction review — 2026-09-11

Correction reviewed: `fe69f956afdc9e8598f90de2c706058f270137ce`.
Final verification checkout: `aced53225ccc0f8b18683404bdae58cc8b3f7636`, twenty-two commits
ahead of local `origin/main = b951b80`. The added commit introduces `b2_records`; the
runtime verifier and firmware are unchanged by it. The checkout was clean at test start.

**PASS for the runtime freshness correction. The cache P2 is closed and the build-guard
review HOLD is lifted.** This does not clear the complete §7 package. The newly added
record validator has a separate initial review, linked below.

## Correction and independent verification

`resolved_runtime_objects()` now resolves all seven roles using the trusted compiler
and Cortex-A9 hard-float flags on every call, checks file existence, and hashes current
bytes. It retains no process-global answer. The required source inventory and role/path
binding corrections remain intact.

The prior cache reproducer was run unchanged. Both valid baselines pass. Same-size
overwrite after a successful verification now produces a runtime hash finding in
`warm_after`; deletion produces an unresolved-runtime finding. All six `Committed`
checks are also run in each altered fixture, and correctly fail after either mutation.
The old diagnostic cache-reset assignment is now irrelevant to the implementation;
the failures occur before that step.

The submitted sequential regression test additionally restores the original bytes and
verifies acceptance before deletion, without clearing any private state. The new alias
test accepts symlinks to the resolved objects. Successive resolver calls return fresh
result dictionaries.

The unchanged older guard reproducer still accepts its two legitimate baselines and
refuses the ten earlier negative fixtures and four input-authority fixtures. The internally
consistent empty dependency graph is correctly refused by the independent compiler
dependency test, as documented in the previous review.

## Current image and input evidence

The independent `verify_current_build.py` passes. It verifies the complete source
inventory, compiler identity, source bytes at the evidence's recorded commit, fresh
dependency/runtime records, and actual output hashes:

| Item | Verified value |
|---|---|
| Binary | `d164cd1d5b30aa5eb91f230b1373be8dda60d219249924e280957b26348d85f5`, 114,708 bytes |
| ELF | `7de96ed25e01199ad4405dcc59b2ec92140c27679710e6acfbbad158e4986cdc` |
| Inputs | 47 translation units, 86 headers, seven runtime objects/libraries |
| Evidence source HEAD | `6cfa8564a2f6b80111f34ae2456be90e1eaf0394` |

Firmware and build-evidence bytes are unchanged. B1's 105 pins verify and its manifest
remains `38238271510536bda565ad1b8321dd04d75e78e1fe77ef94d2795bf9edfd4ba8`.
The instrument remains unchanged and clean at `689dde1`.

## Tests, scope and next checkpoint

The independent focused suite is **232 tests, OK, zero skips, 304.517 seconds**,
run at `aced532` (196 existing B2/B3 tests plus 36 new record-validator tests).

The checkout remained clean through completion; review files were written afterward.
This total includes 31 build-evidence tests and 36 new record-validator tests. The
previous temporary test log/process could not be recovered after an environment update,
so the review reran discovery on `aced532`; no result is claimed for the interrupted run.
The separately reported 1,649-test full suite at `fb37ee0` was not rerun by this review.

The added record validator was spot-checked separately using the twin's real wire REC.
See [its initial review](b2_records_initial_review_2026_09_11.md) for a B2 extension-type
P2. That finding does not reopen the corrected runtime-cache issue.

The four remaining host implementations are `b2_adjudicate`, `b2_runner`, `b2_pins` and
`b2_test_report`; the new `b2_records` still needs correction and full review. Completing
them precedes the full §7 compatibility review, freeze and B2Q.

Artifacts: `evidence/b2/review_runtime_live_2026_09_11/`. All reproducers run offline using
temporary runtime copies or native host tooling. Review documents/artifacts and package
status are the only repository changes made here. No firmware, image build, production
input, instrument file, ruling, board, commit or push was changed by this review.

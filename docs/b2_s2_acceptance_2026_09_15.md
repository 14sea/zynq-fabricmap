# S2 acceptance and push disposition

Reviewed local commits: `ac06141` (S2 qualification), `b348fd0` (test report),
and `8927f8d` (README replacement). At review start the tree was clean and ahead
of origin/main (`24700f1`) by exactly these three commits.

**Decision: accept S2 and its archived clean-tree test report. Claude may push
these three commits together with one additional commit containing the README
corrections made during this review and this acceptance document: four commits
in total.** No history rewrite is needed. The reviewer has not committed or pushed.

## Verified state

A fresh Python process called production `b2_manifest.verify` with
`b2_runner.readjudicator` on the actual committed manifest. It returned S2,
qualified=true, refusal=null, and verified the image bytes, B1 lineage, frozen
inputs and 71 B2 / 105 B1 pinned files.

The actual manifest SHA-256 is:
`e6b8db65afad8494c215fab442cd6b0a7fbbb66ce2478d74a751f84638a1685b`.

The S1-to-S2 diff changes only qualification, qualified, calibration, status and
history. The plan remains null. Calibration is 2976.9824011102987 evaluations/h,
all-self-reporting, three sessions and at most four pairs per session. No pin
table was regenerated. S2 binds the previously reviewed real B2Q evidence, not
the modelled-session rate or a preview manifest.

## Test-report review

Report: `evidence/b2/tests/test_report_2026-09-14T210104Z.json`, schema 2.0.0.
It records whole-suite execution at
`ac06141fdd7af6d2a635faef722c26f7d640931f`: 2085 tests, zero skips, zero failures,
zero errors, result OK, clean_tree_proof=true.

The report's production `proof_refusals` function returned an empty list.
The start/end snapshots agree on HEAD, clean worktrees, pinned instrument commit,
pin verification and artifact digests. All 14 recorded artifact hashes were
independently compared with both the current files and the Git blobs at
head_at_run, including the actual S2 manifest hash. The instrument is pinned at
`689dde1dad374536c625bbe2b05986ee89eb4c94`.

This review validates the archived report and its bindings; it does not claim to
have rerun the 2085-test suite or re-parsed a raw test log. The report belongs to
ac06141, not to a later documentation commit.

## README corrections made during review

The old 475-line README is an exact byte-for-byte suffix of
`docs/README_archive_2026_09_14.md`; the new archive preface accounts for its
additional lines. That archive was not edited during this review.

Three factual corrections were applied to the new, unpinned README:

1. The final B1Q qualification PASS was attempt **4**, not attempt 3. The B1 row
   now also distinguishes carrier qualification from the later B1 mapping PASS.
2. Attempt 3's session disposition was LOST; HOLD was its adjudicator outcome.
3. A pointer-only clone is sufficient for source review, but production verification
   needs restored LFS payloads, untracked B1/B2 build outputs and the pinned
   instrument. Build reproduction and checking also need the recorded toolchain
   and embeddedsw inputs. These prerequisites are now stated before the commands.

The README's exact Python verification command was executed in the existing
prepared environment and returned `S2 True None`. This does not establish that a
fresh clone alone can run it. After the documentation corrections, `git diff
--check` and the production pin verifier passed; the S2 manifest hash is unchanged.
No new full-suite run is needed for these documentation-only corrections.

## Remaining boundary

No S3 plan has been pinned and no new board session is authorized. The transport
stop-loss remains in force; the B2Q single-attempt exception was spent. Future
mapping requires its separate S3 review, boundary, ruling pair and transport
disposition. This review made no image, firmware, frozen-input or ruling changes
and opened no device.

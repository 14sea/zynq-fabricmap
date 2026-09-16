# S3 frozen-test contradiction: owner decision

Reviewed local state: `f007f92` (S3 plan) followed by `8319683` (test correction),
both unpushed. The latter changes a file frozen in the B2 instrument pin table.

## Decision

**Choose A now as containment: revert `8319683`, preserving the revert in history.**
Do not reset away the correction attempt. Preserve the failed report and this review.
The revert restores the exact frozen pinned surface and makes production manifest
verification/preflight meaningful again.

This is **not** approval to accept one permanent test failure, issue a B2 ruling,
or run the board. `f007f92` may be retained as the correctly derived S3 transition,
but the line is held before execution because it cannot produce its required
zero-failure clean-tree proof under the frozen test contract.

Do not regenerate the pin table, update `manifest.instrument_pins`, or edit the
frozen preregistration in the current lifecycle. Do not describe such an edit as
an S3 repair or a licensed transition.

## Finding

The S3 plan itself is consistent:

- plan SHA-256 `fec30a11dde658fec043acbc055b3b3a3198f5fa3d227f6edfa36194e87ab0f7`
  equals the S3 manifest pin;
- the split is DETERMINED, 4+4+1, 10,824 records;
- prediction SHA-256 remains the pinned
  `a611b8e03c88fa797e2b9d9c5d10bb97e42c590bc8754f1defccc6c11c9e3731`.

The frozen test bytes are also unambiguous. The pin table records
`tests/test_b2_plan.py` as
`4dc42f84ff6b3399e8c2c8b0e5452de0c58d1a785a0bb2534603fd851f1bd84e`;
that is exactly the blob at `f007f92`, and it asserts that the committed plan is
UNDETERMINED. The corrected blob at `8319683` hashes to
`b758b2ebbcfc26f6c42275445321b9d2d00a5d770737247d7e00ece9439eafc2`.

Thus a legal S3 plan and that frozen assertion cannot both pass. This defect was
present at S1; S3 exposed it. It is not evidence that calibration, plan generation,
or the S3 manifest transition is wrong.

The second report ran 2,067 tests and records 20 failures plus 32 errors. Its
start and end pin checks both name only the changed test hash as the pinned-surface
refusal. The fan-out is therefore attributable to the one pin drift, while the
underlying pre-drift one-test failure remains a separate, genuine contradiction.

## Why option B as written is rejected

The frozen preregistration states that any later pin or prereg change is refused.
The qualification verifier allows differences from B2Q's `manifest_at_run` only
in qualification, qualified, calibration, plan, status and history. Neither
`instrument_pins` nor `prereg` is licensed.

Updating the pin-table reference therefore makes the current B2Q record a record
for another manifest. Editing the preregistration has the same consequence. Adding
a one-time refresh mechanism to pinned lifecycle code would itself change the
frozen surface and would relax a rule after observing the B2Q result. This review
does not authorize it.

## Correct repair after containment

If the project requires S3 plus clean_tree_proof, prepare a new lifecycle rather
than patching the current qualification in place:

1. Revert `8319683` and archive both failure reports/review evidence without
   changing pinned files.
2. On a separate new-prereg line, restore the stage-aware test correction and add
   transition coverage proving the committed test passes at S0, S1, S2 and S3.
3. Review every pinned test for other stage-constant assumptions before freeze.
4. Regenerate the pin table before the new S0, generate a new manifest, freeze a
   new preregistration, and obtain a new B2Q ruling pair bound to that manifest.
5. Repeat B2Q, qualify S2, pin S3, and require a new clean-tree whole-suite proof.

The existing silicon B2Q PASS remains valid historical evidence for its original
S1 manifest, but it cannot qualify the new frozen identity. Reusing its measured
rate in a new qualification would violate the strict manifest-at-run binding.

No commit, revert, reset, pin generation, manifest edit, ruling, push, or board
operation was performed by this review. Evidence is in
`evidence/b2/review_s3_frozen_test_2026_09_16/`.

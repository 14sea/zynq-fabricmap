# Review — lifecycle-2 pinned-test audit and transition coverage

Reviewed branch `b2-lifecycle-2` at `f942db7`, based on `main` at `4800c15`.
Read-only review: no pin table, manifest, preregistration, ruling, port or board action.

## Result: HOLD before repinning — one P2 test-discrimination gap

The audit's central conclusions are correct:

- the pin table contains exactly the 19 test files listed in the audit;
- the old committed-plan `UNDETERMINED` assertion is the only committed-state stage constant
  found in those files;
- the S2/S3 fixture error fan-out before repinning is the live pin guard working as designed;
- the corrected rule passes S0, S1, S2, S3, no-manifest, and four distinct legal S3 split
  shapes in the diagnostic harness;
- no pin table, manifest, preregistration or board state changed on this branch.

### P2 — the two pin-summary guards have no discriminating negative tests

`split_findings` now checks four independent facts after S3: status, plan-byte digest, session
count, and total record count.  The three negative `StageCoverage` cases exercise status in
both directions and the byte digest.  None changes `manifest.plan.sessions` or
`manifest.plan.total_records` while leaving the plan bytes valid.

The executable probe in
`evidence/b2/review_lifecycle2_prep_2026_09_16/` confirms both sides:

1. the current implementation correctly names either summary mismatch; and
2. after removing both summary findings in memory, all seven `StageCoverage` tests still pass.

This is a blocker before regenerating the pin table because `tests/test_b2_plan.py` will itself
be frozen.  Adding the missing discrimination after S1 would reopen the lifecycle for the same
reason as the defect being repaired.

Required correction:

1. Start from a valid S3 fixture and change only `manifest.plan.sessions`; keep the committed
   plan bytes unchanged and require a single named refusal for the session-count mismatch.
2. Independently change only `manifest.plan.total_records`; keep the plan bytes unchanged and
   require a single named refusal for the record-total mismatch.
3. Demonstrate discrimination: deleting either corresponding comparison from
   `split_findings` must fail its test.
4. Rerun the pre-repin diagnostic suite.  It remains diagnostic only; the eventual clean-tree
   proof must occur after the new pin table and new S0/S1 lifecycle.

## Lifecycle ordering after the correction

The branch should remain before repinning until the two negative cases pass.  Then complete all
pinned-file edits, update the preregistration's stage rule, regenerate the pre-S3 plan without a
rate, regenerate the pin table once, and create a new S0.  The old B2Q PASS and its measured rate
remain historical evidence and must not qualify or plan the new identity.

No authorization for pin regeneration, S0, S1, a ruling, a push, or board access is given by
this review.

# Acceptance — lifecycle-2 pinned-test correction

Reviewed `b2-lifecycle-2` at `83f5ab8`, based on `main` at `4800c15`.

## Result: PASS for the pre-repin correction

The P2 from `docs/b2_lifecycle2_prep_review_2026_09_16.md` is closed.

- The session-count negative starts from a valid S3 fixture, changes only
  `manifest.plan.sessions`, preserves the pinned plan bytes and digest, and requires the named
  session-count refusal.
- The record-total negative independently changes only `manifest.plan.total_records` and
  requires the named record-total refusal.
- The load-bearing control removes each finding in isolation and proves that the corresponding
  negative no longer succeeds for its stated reason.
- The unchanged round-1 probe now reports two failures and `mutant_survived: false` across ten
  `StageCoverage` tests.
- The pre-repin diagnostic module run is 18/18 OK.  Its pin stub remains diagnostic only.

The branch's real run still refusing `tests/test_b2_plan.py` under the old table is the expected
F2 boundary, not a regression and not a proof.

## Next authorized unit

The pinned-test audit and correction are accepted.  The next unit may update the new
preregistration version so it explicitly states the committed-plan stage rule:

- before S3, the committed plan is generated without a rate and its split is UNDETERMINED;
- at S3, the plan is regenerated from that lifecycle's own qualification calibration, is
  DETERMINED, and its bytes and summary are the ones pinned by the manifest;
- the old B2Q PASS and its `2976.98/h` rate are historical and are not inputs to lifecycle 2.

This acceptance does not authorize regenerating `plan.json`, regenerating the pin table,
creating S0/S1, issuing a ruling, pushing, or accessing the board.  Those remain separate
reviewed transitions.

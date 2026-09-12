# B2 S0 and transition readiness review — 2026-09-12

Reviewed HEAD: `fa0271e7165efa56312324476b6596c31b8c9756`, one local commit
beyond origin/main, initially clean.

**The S0 manifest verifies; HOLD on proceeding to S1 until one pinned test is
corrected.** The accepted image compatibility review remains valid. This finding
concerns lifecycle test readiness, not firmware or the validity of the current S0.

## S0 checks accepted

The committed manifest's byte digest is
`af2717476a518f3fcb31d5c76599a17585367fdc421f9607b06aaca424924540`.
The current preregistration digest is
`68cde86d3f3decaf9775beac94c59731ada486ebe246006e7243156c084db8e0`.
Both match the submission. Production `verify` independently returns stage S0,
qualified false, refusal null, board 17A6, image bytes hashed and sized, B1 chain
reverified and canonical B2Q inputs checked. The current table verifies 71 B2 and
105 B1 files; its digest is
`e848325308ee31cf479b733bd6bd93cde466991b86bb424a70c9ed81e2d8a232`.

The committed manifest retains null prereg digest, unfrozen state, board_ready false,
qualified false, null qualification/calibration/plan and empty history. These are
correct for S0. The problem is requiring those exact values of every future
committed manifest.

## P2: the new committed-manifest test cannot survive a valid S1 transition

`tests/test_b2_runner.py:155–170`,
`RefusalOrder.test_the_committed_manifest_is_not_permission`, reads `rn.MANIFEST`
and unconditionally requires S0 fields: null prereg digest, frozen false,
board_ready false, qualified false, null qualification and plan. It then expects
preflight to refuse specifically because preregistration is not frozen.

A valid S1 transition changes the first three values and moves preflight beyond
that gate. The test therefore makes the promised post-freeze green suite impossible.
Its qualified/plan assertions would also conflict with later S2/S3 transitions.
The test's name expresses a valid principle, but the hard-coded stage does not
establish it across the lifecycle.

Independent reproduction used the unchanged test and production code:

1. Read and verify the actual committed S0; run the test successfully.
2. Apply `b2_manifest.freeze` to a deep copy in memory with the actual prereg digest.
3. Verify that copy through production `verify`: **S1 accepted**, no refusal.
4. Write only a temporary file and redirect `rn.MANIFEST` to it while running the
   unchanged test. No verification or preflight function is replaced.
5. Result: **one failure, zero errors**, at line 163: the valid frozen prereg digest
   “is not None.” The production manifest's original bytes are unchanged.

This is an offline transition preview, not a production freeze or board approval.
The captured S1 preview hash is diagnostic only and must not be used for a ruling.

## Required correction before S1

- Keep exact S0 field assertions and the unfrozen-preflight refusal on an explicit
  S0 fixture. Test the intended initialization contract there.
- Make the real committed-manifest test validate legal state consistency rather
  than demand a permanent S0. In particular, do not replace this with a permanent
  S1 assertion, or simply skip the test after freeze.
- Preserve explicit missing-ruling/preflight refusal tests for otherwise eligible
  states, using fixtures. A committed or frozen manifest is not by itself a ruling.
- Exercise the corrected tests with S0 and a valid temporary S1 manifest, and with
  modelled qualified S2/S3 states. Tests that claim to cover the committed state
  must actually read the corresponding manifest; an unrelated fixture alone cannot
  detect this regression.
- Regenerate pins and the still-unfrozen S0 manifest after the pinned test changes,
  then report the new table/manifest hashes. Image and prereg bytes need no change
  for this correction. Perform this before qualification so later pinned-file edits
  do not invalidate the accepted qualification transition.

The full 440-test suite was not repeated: the actual S0 positive control and valid
S1 negative reproduction directly establish this finding. No production manifest,
pin, source, image, instrument or ruling was modified. No push or board access.

Evidence: [transition reproduction](../evidence/b2/review_s0_transition_2026_09_12/README.md).

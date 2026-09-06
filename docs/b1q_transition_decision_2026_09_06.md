B1Q qualification transition decision — 2026-09-06

**Decision: choose option B. Retain the strict manifest transition rule, repair the
state-dependent tests before another qualification, and require a new B1Q ruling pair
for the resulting committed manifest.** Neither a tests-only pin exception nor acceptance
of a red suite is approved.

Reviewed HEAD: 263928f. The current manifest remains
`e38f86a8a7679853eb943f0e968efd880a09faef849606c015ad0ec7616b9709`, with no qualification
record pinned. Attempt-2 evidence is now committed unchanged.

The reported conflict is confirmed:

- The production refresh with attempt 2's record succeeds in memory, and verify returns
  PASS. Only carrier.qualification and carrier.qualified change.
- The runner and adjudicator tests named "the_committed_manifest...refuses_at_the_qualification"
  assume that the committed manifest has no qualification. Running those two tests with
  the qualified manifest supplied in memory reproduces one error and one failure. The
  runner reaches the stale boundary check. The adjudicator's missing-qualification
  expectation no longer holds. This reproduction changed no on-disk manifest.
- Changing only the in-memory pins.sha256 is rejected by verify's final manifest comparison.
  TRANSITION_KEYS allows exactly the two qualification fields, as intended.

The attempt-2 audit correctly established the evidence and qualification transition,
but did not check whether the complete suite remained valid after that transition. That
was an omission in the review's lifecycle validation, not a failed hardware qualification.

Approved host correction scope:

1. Separate the committed-manifest freeze assertions from the missing-qualification
   negatives. The former should verify the frozen document binding and board_ready
   without asserting that qualification remains absent forever. The latter should
   explicitly construct an unqualified fixture. Existing fixture negatives already
   cover no record and a bare flag in both modules; retain that coverage without adding
   redundant copies. Correct stale DRAFT/no-session comments in the touched tests.
2. Add or strengthen lifecycle regression coverage so a standing qualified state also
   remains testable. Before another board run, test the complete suite with the normal
   unqualified manifest and with a modelled, qualified manifest in an isolated snapshot.
   The second check must exercise actual manifest reads in a fresh process; a helper-only
   refresh assertion is insufficient. Keep modelled qualification evidence explicitly
   separate from real board qualification. Validate the real refresh, strict verifier,
   and mapping preflight's progress past qualification using fake dependencies only.
3. Complete every pinned edit, regenerate pins and refresh, run the relevant regressions
   and clean-tree suite, then commit and submit the final manifest hash for review.
   No firmware, image, RTL, carrier, plan, prediction or frozen preregistration change
   is indicated. Keep the strict verifier unchanged. Do not pin attempt 2 into the new
   manifest or revise attempt 2's manifest_at_run/evidence to make it fit.

Attempt 2 remains a valid historical PASS for its original manifest. Once pinned test
inputs change, that record cannot qualify the new manifest. This is supersession of an
input binding, not LOST, HOLD, a new transport failure or an additional stop-loss strike.
A single successful run establishes this qualification result; it does not by itself
establish long-term transport stability.

After review of the complete correction batch, issue a fresh attempt-3 B1Q pair bound to
the new committed manifest, keeping session B1Q and qualification seed 176359248. Board
execution still needs a fresh power cycle, a boundary record within six hours, complete
preflight and a separate explicit instruction. A subsequent standing PASS record can be
pinned without further pinned-source edits. Only after that committed transition is
reviewed may the B1 mapping pair bind its new manifest and seed 1123460948.

This decision authorizes the host correction batch and local commits for review. It does
not authorize push, another board run or reuse of either consumed attempt-2 ruling.
This review changed no runtime/test source, pins, manifest or ruling. Its reproduction
log is in evidence/b1q/transition_review_2026_09_06/reproduction.log.

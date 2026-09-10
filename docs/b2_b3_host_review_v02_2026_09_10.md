# B2/B3 correction-batch review — 2026-09-10

Reviewed commit: `df28407` (16 commits ahead of local `origin/main = 6ac2cf2`).
Disposition: **HOLD remains for the requested push and image construction.** Five of
the previous six P2 findings are resolved at the host-design stage. The new lifecycle
does not yet enforce its claimed evidence and transition contracts. Four P2 findings
below have executable offline counterexamples.

This review creates no image, qualification, ruling or board authorization. All lifecycle
fixtures live in a temporary directory. B2Q has no production adjudicator yet; the probes
use a fixed test double returning the original evidence-derived PASS, 2,500 records/hour
and all-self-reporting policy. Its response does not change when a manifest is mutated.
These are defects in the lifecycle contract exercised by its existing tests, not a claim
that an actual B2Q session has been accepted incorrectly. The CLI's refusal without an
adjudicator is correct and should remain.

## Previous findings and the package §3 decisions

| Item | Review result |
|---|---|
| Train-membership confounding | Resolved for the stated model experiment. T and W were declared in `fcfff98`, an ancestor of the control run's `cf58540`; the report's architecture hash matches that committed text. All 600 control rows pair with the original rows by index and both seeds. Statistics reproduce; two complete grid trajectories per fitness were freshly rerun for both controls. F1 at 600: B−T = 3.23, 169/17/14; B−W = 3.63, 172/17/11. Both exact sign tests pass. This supports correct grouping beyond membership under these landscapes and operators. It is a development extension on the existing seeds, not a new independent confirmatory experiment. |
| Minimum-N search | Resolved. The implementation now scans every N in ascending order; the F3/300/N=89 counterexample and non-monotone profile are covered by passing tests. Fresh scans at the selected budgets reproduce F1/600/N=9/power=0.934, F2/1500/N=8/0.901 and F3/800/N=13/0.910. This review did not rerun the entire full-grid bootstrap selection sweep. |
| B3 refusal atomicity | Resolved for the reviewed contradiction and closure cases. Validation precedes committing candidates, decoded positions and version. The previous counterexamples and closure/malformed cases pass. All 400 archived raw rows are byte-identical to the new run, their statistics reproduce, and two complete trajectories per fitness were freshly rerun. This is ideal-model evidence; it does not qualify a B3 image. |
| Readout/replay policy | The host-design contract is resolved: all-self-reporting, all six measured readout words, per-record fitness recomputation and replay. Production exporter/adjudicator implementation remains a future deliverable; it has not been validated by these simulations. |
| B2 lifecycle | Still open; P2 findings 1–4 below. The intended S0→S1→S2→S3 structure is reasonable, but the claimed restrictions are not enforced. B1's strict transition rule is unchanged. |
| Impossible negative primary | Resolved in the preregistration: prospective reproduction of a fixed prediction; mismatch is HOLD/KILL. Keep this narrower interpretation in all summaries. |

D1–D4 are acceptable at the host-design stage with the new T/W evidence. The documented
v0.1→v0.2→v0.3 changes remain development revisions. G5 may be a total-evaluation cap;
it is not a session-duration guarantee. Retain all-self-reporting and N=9. Rebuilding the
prediction gives identical bytes and deltas `[2,5,6,3,4,6,1,-2,5]`; explicit exclusion
covers 1,223 seed values without changing those session seeds. Neither push nor image
construction is cleared by this review.

## Remaining P2 findings

1. **Frozen live inputs are not enforced.**
   `host/b2_manifest.py:262` filters out missing pinned files before checking drift.
   The lineage checks at lines 265–268 are returned as diagnostics but never gate
   qualification. `b1_chain_verified_now` is a stored flag, not a fresh verification.
   The preregistration and map files are not hashed again at all; image/build evidence
   likewise lacks a live-byte check in this verifier.

   In an isolated mirror, deleting the pinned `host/b2_search.py`, appending whitespace
   to the preregistration or map, or changing the historical B1 manifest file leaves
   `qualified: true`. In the last case the same result explicitly contains
   `lineage_b1_manifest_hash: false`. No manifest digest field or B2Q evidence is changed.
   A missing implementation file or changed frozen document must not leave this result
   valid. Enforce required pin coverage and existence, both map encodings, prereg bytes,
   image/build inputs and the required historical lineage checks. Preserve the distinction
   between verifying B1 history and qualifying the B2 image. Add file-only mutation tests,
   including deletion, with an unchanged manifest and evidence.

2. **Calibration and the qualification record are not reconstructed from evidence.**
   At `host/b2_manifest.py:305`, calibration is compared only with a mutable field of the
   embedded qualification record. At lines 309–311, re-adjudication is checked only for
   `outcome`. The record, calibration and plan are excluded from the transition comparison.

   Changing both the record's rate and calibration from 2,500 to 100,000 records/hour is
   accepted although the hashed adjudication file and the fixed re-adjudicator still
   return 2,500. Changing both policies to `sampled` is also accepted while the frozen
   manifest and evidence say all-self-reporting. Replacing `qualification.files` with
   `{}` passes because line 288 iterates only the entries supplied by the record. This
   repeats the completeness problem previously fixed in B1's export contract.

   Validate the declared record schema and exact required file set, reconstruct the
   evidence-derived record facts, and require agreement with re-adjudication and the
   frozen policy. Derive calibration from that result. Mutating record and calibration
   together must fail with unchanged original evidence; testing either field alone is
   insufficient. Do not weaken B1 or invent an exception to its transition rule.

3. **S3 does not validate the claimed plan derivation.**
   `host/b2_manifest.py:225` checks rate, split, fitness, budget, pair count and master
   seed, but omits the plan's map, engine, audit policy and prediction binding. Independently
   changing each of those fields in an otherwise generated plan succeeds through both
   `pin_plan()` and `verify()`. The wrong prediction digest is accepted without checking
   the actual prediction file.

   S3 re-verification at lines 325–328 is weaker still: it checks only `session_split.sessions`.
   Changing the plan's master seed to 42 and updating its recorded file hash also retains
   qualification. This second probe changes the final manifest hash, so an already-issued
   ruling for the old hash should reject it. The defect is that B2Q's licensed S2→S3
   transition accepts an unrelated plan before such a ruling is issued.

   Use one shared production validator for pinning and later verification. Derive every
   operational plan field and prediction binding from the frozen experiment, exact seed
   sequence, map, engine, policy and verified calibration. Normalize only explicitly
   non-operational metadata such as generation time. Validate the qualification afresh
   before returning a planned manifest; `pin_plan()` currently trusts its input's flag.
   Add separate wrong-field tests at first pinning and during re-verification, including
   a changed plan with its file hash updated.

4. **An infeasible calibration silently produces an overlong session.**
   `host/b2_plan.py:76` forces at least one pair even when no complete pair fits the
   registered 7,200-second expected-span limit. For `session_split(9,600,100)`, it returns
   `DETERMINED` with 1,204 records per session and an expected span of **43,344 seconds**
   (12.04 hours). Negative, infinite and NaN rates also produce `DETERMINED`; zero raises
   an unclassified `ZeroDivisionError`.

   Require a finite, positive measured rate. If one whole pair plus baselines cannot fit,
   return a named refusal/infeasible state and prevent S3. Resolve the draft's contradictory
   “within 7,200 s (at least one)” wording explicitly; an empty feasible set is not permission
   to exceed the limit. Test the exact one-pair boundary, just below it, zero, negative,
   NaN and infinity. Apply this validation when calibration is accepted as well as when
   the split is calculated.

## Documentation and validation record

One P3 documentation cleanup remains: package §0 still says three revised rules, uses
the sampled 1.6-hour headline and says “holdout is neutral” without the F1/F2 restriction.
The package notes that it preserves the previous submission, so this is not an undisclosed
policy change, but its current opening summary should agree with §0a. The plan module's
opening docstring still says seed sets are disjoint by construction from labels; its code
correctly enforces explicit exclusion. Update that explanation too.

The reviewer ran all 100 B2/B3 host tests: **OK, zero skips, 127.107 seconds**. This is
not a full-repository clean-tree proof. No new full-suite report for `df28407` was present
in the inspected evidence; the implementer's background run remains separately reported.
The counterexamples explain why a green host suite does not close the lifecycle finding.

Artifacts are in `evidence/b2/review_v02_2026_09_10/`:

- `reproduce_lifecycle.py` and `lifecycle.json`: isolated lifecycle counterexamples.
- `verify_results.py`, `results.json`, `results.log`: data, provenance, prediction and seed checks.
- `tests.log`: the 100-test run.
- `review_checks.json`: reviewed source hashes and B1 pin/manifest checks.

The original run 1, run 3 and B3 evidence remains byte-identical to the first submission.
Search behavior and fitness code are unchanged; the seed helper acquired the explicit
exclusion parameter. B1's manifest remains
`38238271510536bda565ad1b8321dd04d75e78e1fe77ef94d2795bf9edfd4ba8`, also recorded
in `review_checks.json`.
The review only adds English review artifacts and a package status link; no production
source, pinned B1 file, original evidence, image or board state is changed.

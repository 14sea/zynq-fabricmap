B2 / B3 host package review — 2026-09-10

**Decision: HOLD the package as a basis for firmware construction and withhold push
approval for the current batch pending the corrections below.** The nominal simulation
results reproduce. They are useful development evidence, but do not establish the missing
control, anomaly handling or evidence/qualification contracts. Approve a host-only
correction batch and local commits for review. Do not build an image or contact a board.

Reviewed HEAD `fabbef16a22225a9b2cdd0f53f097696e2ed0e22`; local origin/main `6ac2cf2`.
The actual range contains **nine**, not ten, commits. The tree was clean on entry. All
33 changed files are additions; B1 source, firmware, RTL, manifest and original evidence
are unchanged. B1 qualification still re-adjudicates PASS and all 105 pins verify.

## 1. Verified results and limits of verification

- All 74 B2/B3 tests pass, zero skips. This is the relevant host test run, not a new
  full-project clean-tree proof; the operator's pending full-suite run was not used as
  evidence of a result not yet supplied.
- Recomputed every reported B2 statistic and gate row from all 200 raw rows for each of
  F1/F2/F3. The current implementation reproduces the stored reports exactly. Fresh
  full-budget runs of every arm at rows 0, 99 and 199 reproduce each stored row for each
  fitness. This is a stratified spot check of simulation execution, not a second run of
  every seed.
- Recomputed both accountings and map-growth statistics for all 200 B3 rows per fitness.
  Fresh runs of all three arms at rows 0 and 199 reproduce their complete grid results.
  F1 and F2 each report 200/200 completed maps, zero wrong decodes and zero anomalies in
  the ideal model; exact median completion is 1415.5 evaluations, rounded to 1416.
- Regenerated the complete nine-pair B2 plan in /tmp. Prediction file bytes reproduce
  exactly; the plan matches apart from generation time. Deltas remain
  `[2,5,6,3,4,6,1,-2,5]`, with exact one-sided p = 10/512.
- Checked seed derivations and actual session-seed disjointness from archived gate run 1,
  gate run 3 and B3 simulation. Checked that the relevant current model/search/gate code
  matches the commits cited by run 3 and B3. Original reports were not overwritten.

## 2. Findings requiring correction

### P2 — existing controls do not isolate column grouping from train membership

`host/b2_maps.py::shuffled_map/lut_shuffled_map` permute INIT indices across train and
holdout; `MapView` then filters on the permuted train labels. Consequently B, D and E
have equal *nominal* train-column sizes but unequal access to actual fitness-relevant
addresses. For control seed 0, each names 183 addresses: B contains 183 actual train and
zero holdout positions; D contains 112 train / 71 holdout; E contains 111 / 72.

The observed B-versus-A benefit is real in the model, but D/E losing cannot attribute it
specifically to correct column grouping. Those controls also remove correct train
membership. Retain them, then add a control which preserves each address's train/holdout
membership and the column-size/move-size distributions while scrambling within-train
column assignments. A train-membership-only mutation arm is another useful comparison.
Predeclare the incremental comparison before running it. A control retaining genuine
train information need not be required to lose to random-safe; the question is whether
correct grouping adds benefit beyond that information. Otherwise narrow the scientific
claim explicitly. Do not claim that present G8 already separates those effects.

### P2 — required_pairs() does not implement the declared smallest-N rule

`host/b2_gate.py:110` geometrically skips candidate N values, and its early check at
n_max assumes power monotonicity. Exact sign-test rejection regions are discrete;
independently simulated rejection rates also fluctuate. A failing later N does not rule
out a passing earlier N.

Reproduction from the committed F3 rows at budget 300: the production function returns
N=91, but N=89 gives bootstrap power **0.906** with the function's own 1000 experiments,
alpha 0.05 and seed rule. Cost is 53400, not the reported minimum 54600. This particular
counterexample does not change the selected F1/600/N=9 result, but the declared search
rule is not implemented correctly.

Scan every N in ascending order, with no n_max shortcut that excludes earlier candidates.
Alternatively adopt an explicitly documented exact empirical power calculation over
positive/negative/tie probabilities. That alternative is a rule revision, not a silent
replacement. Preserve raw rows and old reports; recompute summaries on the same rows
before considering new simulations. Add the actual skipped-N counterexample as a test.

### P2 — B3 ignores contradictory decoded observations and mutates refused specimens

`host/b3_online.py:61–94` excludes decoded addresses before checking their observations.
After `observe([0], [(0,0)])`, `observe([0], [(0,1)])` returns no decode and leaves
anomalies at **zero**. Mixing that decoded address with a new one also accepts a delta
which omits the already-known position and stores invalid constraints.

The refusal path is also non-atomic. First establish candidates for `[0,2]` as
`{(0,0),(0,1)}` and for `[1,3]` as `{(0,2),(0,3)}`. Observing `[0,1]` with
`[(0,0),(0,4)]` increments anomalies, but leaves address 0 narrowed to `{(0,0)}` even
though the specimen is documented as unused. Closure may likewise mutate decodes before
discovering a conflict.

Validate known moved relations against the delta, reject positions belonging to unmoved
decoded addresses, and validate uniqueness/ranges. Compute narrowing and closure on a
candidate state and commit it only if the complete specimen is consistent. A rejected
specimen must preserve candidates, decoded relations, taken positions and version, apart
from the anomaly count/ledger. Test fully decoded contradictions, mixed contradictions,
mid-update refusal and closure conflicts. Nominal zero-anomaly simulations do not test
these guarantees. Preserve the existing B3 simulation as ideal-model evidence.

### P2 — sampled-audit replay is underspecified and overclaims recomputation

The B2 package/architecture promise recomputation of every fitness from served readouts,
while preregistration §2/§4 offers only a readout hash on unaudited records and calls that
the replay input. F1 cannot be computed from a hash. Checking a model-predicted readout
against a board-reported hash is a model-consistency check, not recovery of the measured
readout. The distinction must be explicit even if it is an acceptable sampled policy.

For the first B2 image choose **all-self-reporting**, with every record's evidence
available for recomputation, and define the resulting session split before freeze. If
sampled audit is proposed later, specify exactly which readout fields every REC carries,
which staged/readback words are sampled, mandatory baseline/champion audits, deterministic
sample selection, and what is verified on an unsampled record. Demonstrate it through
the real exporter/adjudicator with negative cases. B1's validator can support a sampled
policy; that does not supply this missing B2 replay contract automatically.

### P2 — B2Q, calibration and final-manifest binding need a complete lifecycle

Architecture D1 proposes reusing the B1 qualification chain, while preregistration §6
correctly observes that a new image needs B2Q. These must be separate bindings: immutable
B1 evidence may certify the old B1 manifest/carrier history; it cannot qualify an arbitrary
B2 manifest merely because the bitstream is unchanged. The B1 verifier permits only its
two qualification fields to change, not a new image or plan.

The draft also freezes before B2Q and then recalculates the B2 deadline from B2Q's rate.
Under the inherited strict transition rule, that plan/manifest edit invalidates the B2Q
binding. Specify the actual lifecycle before building: where carrier lineage is verified,
what the new image qualification certifies, when calibration becomes frozen input, and
which exact final-manifest transitions are allowed. Exercise that lifecycle on disk in
fresh-process host tests, including rejection of a later image/plan/pin change. Do not
silently relax the B1 verifier or repeat its earlier pinning deadlock.

### P2 — the draft's negative primary outcome is impossible under its EXACT prediction gate

Preregistration §4/§5 describes a run where every predicted fitness reproduces but the
primary is unsupported. With these fixed seeds and exact fitness predictions, the nine
deltas are fixed and p is necessarily 10/512. That proposed falsifier cannot occur.

Retain the model-led design, but describe silicon execution as a prospective reproduction
of a known predicted outcome. A mismatch can be HOLD/KILL as defined; do not also call an
unchanged prediction an independent chance of a negative primary. Alternatively design
a separately preregistered experiment whose primary is not constrained to those exact
values. This review does not request another seed draw or a favourable N adjustment.

## 3. Additional documentation and provenance corrections

- The architecture table contains **four changed rows**: budget rule, G2, G5 and G7.
  Calling these “three rules” obscures the separate budget-rule change. Run 1 executed
  code at `9f347e9`; `342450b` is the prior architecture commit. Distinguish them.
- Map digest `c6a4b23e…` is SHA256 of the canonicalized JSON object, not of the named
  file bytes. File-byte SHA256 is `b6607a9a4de4ec16b4441395703d353ba438463e3ff0be3b5984ec6f1f1bfa38`.
  Name both encodings explicitly before implementing manifest and IDENT checks. Current
  Python consumers agree on the canonical digest; this is not a changed B1 map.
- F3's train trajectories can enter holdout rows. At landscape seed 123, starting from
  the target tables, flipping certified genome bit 13 at LUT 0 / INIT 0 (a holdout row)
  changes train fitness from 320 to 256. Restrict the “holdout rows never affect train”
  claim to F1/F2; F3 needs different language/design. F1/F2 also have many train-fitness
  optima due to unconstrained holdout bits, even though the complete target readout names
  one unique genome.
- At their selected budgets, reported Cohen's d is F2 **1.4437**, F1 **1.5364**, F3
  **0.8506**. The package's F2 ≈0.8 / F3 ≈0.7 values are stale. Gate JSON and its generated
  Markdown agree; fix the prose, preserving historical run-1 numbers as historical.
- Different hashed labels do not guarantee disjoint finite 32-bit streams “by construction.”
  Actual checked sets are disjoint. Enforce explicit exclusion of all relevant frozen
  sets for future qualification/session generation and document that check.
- “Eight of nine” is the no-tie threshold, not a replacement for the exact sign test
  when ties occur. For example seven positives, no negatives and two ties also passes.
- B3's accounting is an evaluation-count model with **333 probes** charged to F. It
  excludes the two B1 baseline records, setup, qualification, audits and compute time.
  Keep that convention but name it; it is not complete wall-time end-to-end accounting.
  The reported positive O−F means at all grid budgets are reproduced exploratory results,
  not a preregistered family of confirmed tests. Bounded fitness improvements do not
  “grow without bound.”

## 4. Decisions on the five requested items

| item | decision |
|---|---|
| D1–D4 design | Accept PS-side fitness from the static functional truth tables on unchanged B1 RTL, the public landscape rule, and the shared selection engine in principle. Limit “whole phenotype” to this digital functional observation, not timing/power behaviour. D1's evidence lifecycle and D4's grouping attribution require the corrections above before implementation approval. |
| gate v0.1 → v0.2 | Accept the documented revisions as transparent **development** revisions: the old budget/negative-sign/endpoint assumptions were not mandatory scientific truths. Preserve run 1. Fix the minimum-N implementation and add the missing control or narrow the claim. G5's sampled-rate cost assumption is not approved as a final execution gate. |
| audit policy | Choose all-self-reporting for initial B2. Reject the unsupported assurance that two sessions necessarily suffice. Freeze an explicit split, per-session baselines/closing, pairing, aggregate decision and measured policy-matched deadlines. |
| N=9 margin | Retain N=9 provisionally; do not increase it because the now-visible prediction is 8/9. Exact power under the empirical F1 sign/tie frequencies is about 0.92652 at N=9 versus 0.87770 at N=8, consistent with the bootstrap choice. This is an estimated planning distribution, not guaranteed future power. Revisit only if a corrected, predeclared gate actually changes the design, and record why. |
| firmware/b2 image | Not approved yet. Complete the host corrections and lifecycle/audit specification first; submit the corrected package and tests for review. No B3 firmware or board work is authorized. |

The 1.62 h sampled / 3.21 h all-audited figures reproduce the draft's arithmetic, but
use earlier P3/C1/C2 rates, not a B2 calibration. The last B1 mapping's observed search
rate was approximately 2807/h, illustrating why 3368/h is not a demonstrated B2 rate.
No older rate is adopted here as the B2 calibration. If nine pairs were split 4+5 with
independent opening/closing baselines, the total would be 10822 records rather than the
single-session plan's 10820; whether that fits two sessions is still to be established.
The short all-audited B2Q proposal does not establish sampled-policy throughput.

## 5. Authorized correction scope and review artifacts

Repair only the new B2/B3 host implementation, tests and draft documentation. Preserve
run-1/run-3/B3 raw files and reports; write corrected summaries/new controls as separately
labelled evidence. Reuse existing raw rows and seeds for the statistics correction; do
not derive a fresh gate seed merely because a review commit changes HEAD. Freeze the new
control comparison before running it. Keep the engine, mixture, fitness family and current
session seeds fixed while resolving the findings. No B1 pinned edit is indicated.

Run regression cases reproducing these defects and relevant host tests; supply the
complete suite result with its actual tested commit. Commit the correction and this
review locally, then submit for push/image review. The current original reports remain
valid historical outputs of the reviewed implementation; HOLD is not a claim that their
nominal numbers were fabricated or that F1 ceased to discriminate.

Artifacts are in `evidence/b2/review_2026_09_10/`: recomputed.json, findings.json, the
two reproduction scripts, logs and reviewed-file hashes. For recompute.py, first run
`python3 host/b2_plan.py --out /tmp/b23_review/rebuilt_plan`; scripts write only to /tmp.
No original report, source, test, pinned input or manifest was modified by this review.
No image build, board contact, commit, push or ruling issuance was performed.

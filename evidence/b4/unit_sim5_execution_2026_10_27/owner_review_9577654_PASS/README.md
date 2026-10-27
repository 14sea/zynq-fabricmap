# Owner review — 9577654 PASS; b4-sim-5 execution accepted, no-go of record

2026-10-27. Reviewed the complete `b4-sim-5-execution` unit through `9577654`, including archive `d1e0e2c`, decision `61733c5`, unit record `0c57bc1` and the subsequent documents-only update. **PASS: the execution unit is accepted and may close with the routine documentary corrections below.** The fixed section 9.4 decision is **no-go**. This is an execution/evidence acceptance, not a gate PASS or a scientific negative conclusion.

## 1. Independent checks actually performed

| check | result |
|---|---|
| fresh-process `b4_sim_verify.py` deep on the committed archive | **exit 0, clean true, findings {}** (`sim_verify.txt`) |
| fresh-process `b4_gonogo.py verify` deep on the committed decision | **exit 0, clean true, findings {}** (`gonogo_verify.txt`) |
| commit and identity bindings | archive commit's parent is the authorised execution HEAD **ae7fc3547e1f9271a430b38ffee7fd469b89a7ee**; decision commit's parent/recorded HEAD is **d1e0e2c**; batch HEAD remains ae7fc35; protocol SHA **5bba53c78d08f3ad32e41a90ef37d2639ea584e97fbf74996d941cec4fe14e7f** |
| archive / decision commit scope and Git-blob equality | archive-only **771/771** and decision-only **2/2** equal their committed blobs; no missing, extra, differing file or symlink |
| inputs and code | **45 repository inputs and 28 tool digests** match blobs at the recorded execution HEAD; **6 external UNISIM inputs** match today; B4 and protected code/RTL/build paths unchanged from e20e12b |
| copied owner authorisation package | **9/9** checksummed payload files and SHA256SUMS equal the original owner package byte for byte |
| independent readout scoring / curves | **57,568 base/search ledger fitness values** across all seven arms and 32 pairs recalculated directly from retained q grids, masks, targets and weights; each per-budget best curve agrees |
| independent Omega−R statistics | all ten budgets' signs, means, medians, exact one-sided binomial-tail p and sample-SD Cohen d agree with the report; B64 **9/7/16**, mean **0.03125**, d **0.011027027284780772**, p **0.4018096923828125** |
| K9 retained-grid checks / summaries | **37,888 comparison rows** checked: scoped differences and coverage recomputed from the q grids; both applicability tallies and seven seed medians agree; all-seven positive controls **25/32** |
| K10 retained-grid checks | **13,440 units**: all four scores and second differences recomputed from retained grids; max-absolute indexes agree; **32/32 interacting**, tau2 |
| K7 / document pins | counts from the retained prefix relations agree; medians **2,4,5,6,8,10,14,16.5,19.5,21** in grid order; **4 pin tests OK**, no skip |
| registry / pool | four archived sets; sim5 contains **65 distinct values**, zero overlap with the prior pool; union **2690 -> 2755**; seed-derivation guards called **0** times |

`independent_checks.py` and its JSON/output preserve the arithmetic, source and blob checks. Manual K9 counting uses the recorded scopes/applicability flags; the fresh deep verifiers additionally validate the fixed comparison set and recompute model applicability. The manual K7 check counts stored relations; deep verification supplies replay/reconstruction. These are not represented as newly obtained observations.

No production master/pair derivation, batch execution, new fabric observation, tracked edit, commit, push, merge or board operation was performed by the reviewer. No unrelated 332-test/mutant/e2e battery was repeated. Current documentation differs from the execution tree as declared; historical root inputs were checked against **the recorded HEAD's blobs**, not wrongly against the later status-document bytes.

## 2. Finding and interpretation

The operator record, run header, manifest and commit chain agree with the separate execution ruling. The 3600s soft deadline was not exceeded (recorded elapsed349.419s), the batch is complete32/32, the report and decision self-validation fields are empty, and the archive carries no stop/quarantine/init-failure records. The previous three documentary precisions were faithfully incorporated without changing runtime, method or archived bytes. The documentation commit's gate-2 row is aligned to v0.3.0 and does not purport to authorise it.

At the **pre-fixed B64**, positives exceed negatives but p=.4018096923828125 exceeds the engineering cost threshold .20. The seven conditional medians are:

| semantic | conditional (b-prime) | all panel (b) |
|---|---:|---:|
| ce_mode | .875 | .875 |
| clock_mode | 1 | 1 |
| ff_init | 1 | 1 |
| ff_srval | .8333333333333334 | .4166666666666667 |
| sr_kind | .5 | .25 |
| sr_mode | .875 | .875 |
| storage_kind | 1 | 1 |

Thus the coverage component of **this cost policy** is satisfied and its sign-test component is not: **no-go is the correct recorded decision**. Equality at sr_kind=.5 is allowed. These medians do not constitute a formal K9 gate PASS: the separately reported all-seven positive-control fraction is25/32=.78125, below the unchanged formal K9(a) reference .90. No gate was run or adjudicated here.

The first positive B64 descriptive sign/mean under a new task does not establish a gain, reverse earlier decisions or license pooling records across methods. B96's p is a retained descriptive statistic; it does not replace the named decision budget. The verifier establishes internal consistency/source binding, not truthfulness of the observation source or physical-model agreement.

## 3. Two P3 wordings for ordinary closure — no new verification round

1. Unit README section5 ends with “No production / exploration estimate of coverage is claimed by this unit either”. That carries the pre-run qualification too far: **this is now the first task-v0.3 production exploration archive, and its K9 values are the empirical coverage summaries/estimates on the fixed panel over its 32 planned seeds.** They are not silicon coverage estimates or a general coverage guarantee. Replace the categorical denial with this limited positive description; retain both estimands, positive-control counts and uncertainty/claim limits. This does not change any value or criterion.
2. Replace B96's p being “not a result” with **a descriptive reported result, not a pre-specified decision criterion or a basis for choosing another budget**. Keeping and honestly describing exploratory values is appropriate; using them to override this no-go is not authorised.

Fold these two wording fixes and the review archive into the routine documents-only closure; update the section13 unit status if desired. No program, threshold, policy, raw archive, decision or old commit message is to be rewritten. **No tests, mutants, verifiers or observations need repeating solely for these faithful documentary changes, and no separate review round is needed.**

## 4. Disposition and authority

The **b4-sim-5 execution unit is accepted**, with the valid **no-go of record**. The label is consumed by its durable records, and the pool is now2755. The implementer may archive this owner package with checksum verification and make the ordinary documents-only closure described above.

The cost-policy route to gate-2 stops here. **No rerun, alternate label, next protocol, changed task/operator/grouping/threshold, gate-2 execution, push/merge, RTL/firmware, 2d, routing or board work is authorised by this PASS.** A later undertaking needs its own concrete engineering or scientific purpose and scope; no negative scientific proposition follows merely from this cost-policy stop. Preregistration remains unfrozen.

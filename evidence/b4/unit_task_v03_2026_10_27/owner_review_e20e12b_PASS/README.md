# Owner review of e20e12b — PASS, task-v0.3 engineering revision accepted

2026-10-27. Reviewed `b4-task-v03@e20e12b246571c929721519fe00f86a81e0069b5`, base `e084f07`, implementation/tests through `bf02746` plus the evidence commit. **PASS for this complete host-only revision unit. No blocking finding remains.** The narrow observation-contract update to v0.6 and the carried-forward go/no-go row are accepted within this scope. Preregistration remains unfrozen.

## 1. Independent verification

| check | result |
|---|---|
| full B4 unit test suite in a detached local clone of the committed tip | **332 tests OK, no skip**, 560.683s (`tests.txt`) |
| new-contract mutants M58–M72, including re-aimed M67 | **15/15 KILLED**, green baselines, Ran N>0/FAILED, no edit miss; old equivalents not rerun (`mutants_new_contracts.txt`) |
| unmodified e2e driver in a fresh hermetic root | **exit0, as_expected=true, production_derivation_calls=[0,0]**; fresh-process batch/gate/gonogo verifiers behave as expected for all cases; no unresolved raw link (`e2e_owner/summary.json`) |
| independent regenerated versus submitted e2e evidence | **966/966 normalised digests equal; zero different/missing/extra cases** (`regeneration_comparison.json`) |
| semantic and explanation tampers | differences localised to the prescribed four chained files / gate_report.json only;47 other files equal in the semantic case |
| scripted generator and actual planted-model probes | CE/SR/D draws2,4,256 in order; broadcast/carrier round-trip; four explicit mechanics fixtures self-score64/80 with zero None; setup reconstruction clean; refreshed-digest old-shape task refused (`contract_probes.json`) |
| frozen numbers / protected paths / inventory | K1–K10, grid/budget, operator/statistics and original target/policy rules unchanged;59 IMPORT digests match; model/hypothesis, K9/K10, carrier and historical archives unchanged (`scope_check.json`) |
| historical re-verification inputs, sim-4 |45 repository inputs and28 tools match blobs at recorded HEAD495cc36;6 external UNISIM hashes match today (`historical_bindings.json`) |

The owner regenerated one complete fresh e2e run and compared it to the committed run; the author's two-run966/966 comparison is additional submitted evidence, not represented as two owner runs. The expensive tail was the unmodified driver's repeated whole-graph normalisation (23 fixed-point passes over1022 raw-content entries), not a new simulation or production draw. It was allowed to finish, including the final tamper/localisation checks. No large raw mechanics archive was duplicated into the review package.

The full historical72-mutant battery was inspected, not repeated: its first log remains68/72 with the three accepted disk-authority equivalents and the first equivalent M67; re-aimed M67's single kill is separately retained. The independent15/15 above uses the current, non-equivalent M67. No equivalent mutant, edit miss or zero-test run is counted as a kill.

## 2. Accepted scope and interpretation

The concrete implementation and decisions described in `review_notes.md` are accepted. The task broadcasts one CE control and one SR control value per set step, with the prescribed probabilities and draw order. The common8-bit grammar, D/INIT/SRVAL per element, K6/8, masks, weights, T-i planted rule and PublicTask boundary remain intact. Shape validation is load-bearing both on the record and on offline reconstruction. The unchanged model's scalar/vector equivalence is a model property, not a silicon observation.

Protocol SHA256 **5bba53c78d08f3ad32e41a90ef37d2639ea584e97fbf74996d941cec4fe14e7f** binds the new stimulus rule and tool inventory. New tools refuse old archives instead of rejudging them; the archives remain byte-identical and their namespaces unchanged in the independent e2e check. The manifest-only historical input check confirms the documented route to sim-4's own tool is available; no historical deep replay or aggregation of its K9/search-effect values was done by this owner review.

The policy retains S32/all complete, B64, positives>negatives, one-sided p<=0.20 and all seven conditional medians>=0.50; otherwise the existing no-decision/no-go rules apply. `p_max_go` is an engineering cost threshold, not the scientific test's alpha. `b4-sim-4` remains consumed/no-go of record; `b4-sim-5` is reserved only. Keeping the never-derived `b4-gate-2` reservation is accepted; it is not reusing an exposed set.

This engineering PASS establishes neither a new K9 coverage estimate nor a map/search benefit, N/B*, predictions, sessions, physical model agreement or a gate result. Physical INIT/SRVAL/A8, timing/sampling, the latch/x5FF scoring-domain boundary, actual producer/schema/adapter integration and B4Q still require their relevant later work. It does not turn the carrier engineering PASS into a board qualification or freeze the preregistration.

## 3. P3 wording to fold into ordinary closure — no new test round

1. In `docs/b4_archive_reverification.md` section6, qualify the broad promise of an identity-component refusal/pointer: **the old gonogo decision-record verifier can reject first at policy shape (`policy: not the table's`), before identity comparison**. Batch verification/judgement/policy on the batch do give the identity refusal. Historical decision verification still follows the same recorded-HEAD procedure. The current early refusal is safe, was disclosed, and does not require a runtime change or a changed protocol digest.
2. In the unit README, qualify “No v0.3.0 coverage value exists yet” as **no production/exploration estimate of record**: mechanics fixtures necessarily contain coverage values. Their existence does not make them scientific results or justify tuning the fixed rule.

These are document corrections, to accompany the acceptance/archive bookkeeping. No rerun of tests, mutants or e2e, and no separate review round, is requested merely for this faithful closure.

## 4. Next bounded work

The routine documents-only closure may archive this review with checksum verification and mark the unit accepted/closed. The **next complete documents-only unit may prepare the b4-sim-5 execution plan**, using the accepted method and already fixed S32/policy; include a concrete candidate execution HEAD/baseline, deadline/resource estimate, input/registry checks, one-attempt stop and retention rules, fresh verification and archive/decision publication sequence. It chooses no new probability, threshold or scientific rule. Complete that plan and submit it once; no preliminary scope draft or per-edit approval is needed.

**No production seed derivation, smoke/exploration/gate, board/2d/routing, push or merge is authorised by this PASS or by the plan-writing authorisation.** The execution plan is reviewable preparation, not permission to run. No new date gate, fixed branch name or commit count is imposed.

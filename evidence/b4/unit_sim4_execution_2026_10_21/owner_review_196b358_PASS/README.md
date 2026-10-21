# Owner review — b4-sim-4 execution unit 196b358: PASS; policy no-go accepted

Reviewed on 2026-10-21. Primary reviewed tip: `196b3585a6c4e046227e8d9da46823c854917ecf`. During review, the author also committed the permitted documentation follow-up `5b8aabc`; its four-file diff was read and is included in this acceptance. No tracked file was changed by the reviewer.

## 1. Decision

**PASS: the b4-sim-4 execution/delivery unit is accepted and closed.** The batch is complete and valid; the fixed engineering cost policy's decision is **no-go**, correctly recorded as a formal decision of record. Engineering acceptance of this delivery does not convert the policy decision to go, or constitute a scientific gate PASS.

At B_go=64, Omega-minus-R has 7 positives, 13 negatives, 12 ties, mean -1.71875, Cohen's d -0.3531074633217678 and one-sided sign-test p 0.9423408508300781. Positives>negatives and p<=0.20 are both false. All seven conditional coverage medians meet 0.50. Thus the fixed conjunction gives no-go without a budget, threshold or sample-size change.

This is the policy's stop for this proposed route to gate-2. It is not evidence of scientific impossibility, an unobservable FF class, or silicon behavior. The record supplies no automatic next exploration, protocol revision or gate execution.

## 2. Independent verification performed

| check | result |
| --- | --- |
| Fresh-process b4_sim_verify.py deep | exit 0, findings {}, clean true; 75.596 s |
| Fresh-process b4_gonogo.py verify deep | exit 0, findings {}, clean true; 123.389 s |
| Independent Omega-minus-R computation | Ledger q_grids scored against each task's public mask/target/weights; base/search prefix maxima rebuilt; all ten budgets agree with curves, summary and decision |
| Independent statistics | Positive/negative/tie counts, integer-sum mean, population variance, sample-standard-deviation d, median and exact binomial upper tail recomputed with Python's standard library; arithmetic agreement checked at relative 1e-13 / absolute 1e-14 for floating values |
| K9 | Differences independently read from retained observation grids under recorded scopes, both recorded applicability flags tallied, per-seed fractions then medians computed; deep verifier separately checks those applicability flags against the formal model |
| K10 | All 32 x 420 units independently re-scored from retained corner grids; I=f11-f10-f01+f00 and per-seed maxima checked; all 32 maxima strictly greater than tau=2 and classified interacting |
| K7 | Recorded per-seed prefix counts summarized independently; deep verifier rebuilds and re-audits the prefixes |
| Batch blob equality | 771 committed Git blobs versus 771 disk files, 200674002 bytes: all equal, no missing/extra files |
| Decision blob equality | 2 committed blobs versus 2 disk files, 11359 bytes: all equal |
| IMPORT | 59 entries, file/base/copied-function digests equal; no unlisted b4 file |
| Input provenance | 45 recorded repository inputs match their execution-HEAD blobs; 28 tool files match execution blobs and current bytes; all 6 recorded external files still match |
| Review archive | Original owner review of 495cc36 copied byte-for-byte; all 6 checksum-listed artifacts verify (plus checksum file and destination SOURCE.txt) |
| Exclusions | Existing pool 2625; new recorded master/pair values 65; collisions 0; current pool 2690 |

The two verifiers were fresh processes, default deep mode. Their commands, stdout, stderr, exit status and elapsed time are retained here. They re-use recorded observations; no production exploration, new production seed draw or new fabric observation was run by this review. The independent checks script uses no B4 production scoring/statistical functions; only the exclusion reader is imported later, with master_seed and pair_seeds replaced by failing guards. Both call counts stayed zero. No full test suite or mutants were rerun for unchanged tool code.

The scripts and detailed JSON outputs are in this directory. Fixture archives are not copied into this review. SHA256SUMS covers the review artifacts.

## 3. Recomputed values

Conditional medians: ce_mode=1, clock_mode=1, ff_init=1, ff_srval=0.8125, sr_kind=0.875, sr_mode=1, storage_kind=1.

All-panel descriptive medians: ce_mode=1, clock_mode=1, ff_init=1, ff_srval=0.40625, sr_kind=0.4375, sr_mode=1, storage_kind=1. All seven semantics have positive controls in all 32 seeds. ff_init remains conditional on the unresolved A8 assumption, as before. K10 interacting=32/32.

Every budget's statistics are preserved in independent_checks.json; the policy uses only the preselected B=64. The positive descriptive means at B=192 and B=256 do not replace that policy budget. This review neither pools the three historical experiments into a new test nor treats their common B=64 direction as a causal explanation.

## 4. History, authorization and the documentation follow-up

The archive-only commit 580c0e5 has execution HEAD 495cc36 as its parent, and changes only the named batch directory. The decision-only commit adce027 changes only the named gonogo directory. The submitted unit-record commit 196b358 changes only its evidence directory. The batch manifest/report correctly record execution HEAD 495cc36; the decision correctly records its own creation HEAD 580c0e5 while binding batch.head back to 495cc36 and binding the exact seeds/manifest/report digests.

The batch reports complete 32/32, no missing records, no stop/init-failed/quarantine/.part, empty self-validation, elapsed 199.256 of 3600 seconds and expired=false. The command, plan and initial registry/receipt/exclusion inventory agree. All b4 bytes remain those accepted at 21db2de; main remains a243ee8 and b4-protocol-v2 remains 495cc36. The archived execution records and scripts cannot prove an absolute absence of unrecorded historical activity; acceptance is based on the preserved chain and independent checks, not such a claim.

The calendar deadline, branch name and exact commit count are **not** validity conditions: the owner's latest clarification supersedes the earlier organizational restrictions. This delivery happens to meet the original arrangement too, but PASS is not based on doing so. The fourth, pure-document commit 5b8aabc needs no new permission or verification round. It archives that clarification, updates execution status and applies the previously accepted wording corrections. No method, statistics or production archive bytes change.

One reviewer-side provenance check initially compared every recorded input against today's live file as well as the execution blob. It encountered the legitimate post-execution architecture update in 5b8aabc. That is not archive drift: the recorded architecture digest exactly matches 495cc36's blob; the later digest belongs to the later documentation tree. The corrected check holds historical inputs to the recorded execution tree and holds current tool/external bytes separately. git_input_checks.json records the difference explicitly. No production artifact was repaired or rerun to resolve it.

## 5. Two remaining P3 wording corrections, not blockers

Fold these into the next routine closure/documentation commit. No separate review round, test run or mutant run is required.

1. Unit README section 5 says both all-panel ff_srval and sr_kind remain below 0.5 “as they were” in sim-3 and gate-1. This is inaccurate for historical sr_kind: both old samples had sr_kind exactly 0.5. Correct wording: the present all-panel ff_srval=0.40625 and sr_kind=0.4375 are below 0.5; historical ff_srval was below 0.5, while historical sr_kind was exactly 0.5. The numerical tables and policy calculation are correct.
2. Unit README section 2 says the time estimates “held.” The actual batch 3.3 min is below the estimated 4–10 min range, and each submitted fresh verification took 74 s, below the estimated 1.5–3 min range. Say they were faster than those estimated ranges; file count and size were close to estimates. This has no effect on the soft deadline or evidence validity.

Routine closure may archive this review, mark the execution unit accepted and include these wording corrections. No new approval loop is needed merely for that bookkeeping.

## 6. What follows

b4-sim-4 is consumed by its records; the pooled exclusion is now 2690. Keep the complete archive and no-go decision unchanged. No replacement label, re-run, gate-2, operator/threshold/task adjustment or next protocol version is authorized by this acceptance. What follows needs its own scientific or engineering purpose and explicit scope; no-go does not establish a negative claim that future work must assume.

Push, merge, RTL, provisioning, purchasing and board/routing work remain outside this execution unit's authorization. No arbitrary calendar expiry, prescribed branch name or prescribed commit count is added by this review.

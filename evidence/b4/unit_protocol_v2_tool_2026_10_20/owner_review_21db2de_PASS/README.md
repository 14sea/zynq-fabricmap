# Owner review: 21db2de — PASS

Reviewed on 2026-10-21. Reviewed branch: b4-protocol-v2. Exact HEAD and parent are in review_metadata.json. This is an independent engineering review, not an execution authorization.

## 1. Decision

**21db2de PASS. The v0.2.0 host-tool unit is accepted and closed.** C1, C2, C3 and the normalization P3 are resolved. No blocking finding remains. The current changes preserve the behavior hypothesis, domain, mapping, statistical formulas, thresholds and existing production archives relative to b29b0fb.

The earlier decision to count only tool/schema IMPORT entries in the method identity remains accepted: tests and document revisions are provenance, while executable method bytes remain bound. This does not relax the artifact inventory or source checks.

## 2. Independent verification

| Check | Independent result |
| --- | --- |
| Complete B4 test suite | 326 tests, OK, 574.339 s; tests.txt |
| Fresh mechanics e2e, with the normalization-only cache disclosed below | Every case as_expected; production derivation guards [0, 0] |
| Fresh run versus submitted final-tree run | 966/966 normalized file digests equal; zero different or missing |
| Submitted final-tree run versus submitted repeat | Independently compared: 966/966 equal |
| C1 original counterexample | Float cell refused; original returned marker and steps retained in quarantine; fresh verifier exit 0 for the correctly recorded invalid batch |
| C2 original counterexamples, both phases | Interrupt after quarantine publication: incomplete batch, invalid task with correct phase/prefix; fresh verifier exit 0 |
| Additional earlier publication window, both phases | Interrupt after the durable file write but before Batch.write updates its index: same coherent recovery, fresh verifier exit 0 |
| C3 refreshed-hash negatives | Wrong stimulus, wrong expected source and null expected source rejected in both phases; all six fresh verifier exits 1 |
| Coordinated source tamper | Forged retained first source plus matching second quarantine expectation still rejected against formal source |
| Explanation normalization | Changed reasons remain visible: exactly gate_report.json differs; rendering deliberately excluded by the comparison rule |
| Target semantic normalization | Exactly target_search.json, task.json, pair index and sim_report.json differ; other 47 comparable files equal |
| Selected mutants rerun | M51–M57 killed, each with tests actually run and FAILED; M39 survives as equivalent |
| IMPORT | 59 entries and base/copied-function digests match; no unlisted b4 file |
| Prior review copied into evidence | Original owner b29 review files compared byte-for-byte: no missing or different files |

The author's full battery record is 54 killed / 57 defined, with M31, M45 and M39 surviving. I inspected that record and independently reran the selected eight above, not the whole 57. M31/M45 remain accepted equivalent memory-state mutations. M39 is now equivalent for the same reason: removing the immediate memory assignment does not remove the disk-derived state at termination. M51/M52/M55 attack the actual reconstruction and are killed. No survivor is counted as a kill.

## 3. Contract assessment

**C1:** Cell types are exact integers; float and bool are rejected. Both the early observation check and the later record-validator fallback quarantine the original port return, rather than a transformed record. The marker/steps counterexample is fixed without weakening the validator.

**C2:** Disk is the authority for a published quarantine. Recovery reconstructs task_quarantine and invalid task state only for the matching phase and ordered prefix. Keeping an interrupt as the batch stop reason while retaining the failed-return fact in task state is coherent. Both post-write windows were tested; no run is upgraded to completed.

**C3:** Quarantine context is bound to the planned seed and phase for stimulus, to formal source identity on the first call, and to the retained first observation on the second. The retained first observation is itself bound back to formal source. Mutual consistency cannot substitute for this authority; the coordinated-tamper probe is rejected.

**P3:** Semantic reasons/details are no longer globally discarded. The deadline-specific volatile explanation remains excluded only under its stated path rule. The reason-only counterexample and the fresh explanation-tamper case now retain the difference.

## 4. Fresh e2e method and reproducibility limits

The fresh run uses the submitted e2e_v2_fixtures.py at its original repository location. The owner wrapper changes only its pure global normalization calculation by memoizing it. Every fixture batch, failure injection, fresh-process verifier, old-archive refusal, identity check and tamper case still executes.

The cache key includes root path, the complete HEAD set, and the SHA256 of every evidence file's bytes. A cache miss runs the original normalization over the entire evidence graph. Each requested directory then receives the corresponding projection. Changing any evidence bytes invalidates the cache. A tiny dependency-graph test compares cached and original results, including a different projection and a leaf modification. Its output is CACHE_EQUIVALENCE_AND_INVALIDATION_OK. The real e2e used one global computation and nineteen cached projections. The copied wrapper and raw log preserve this distinction; this is not described as an unmodified-driver invocation.

fresh_e2e/ retains the independent digest records and verifier logs, not full generated fixture archives. e2e_cached.py, the submitted source driver and the recorded command allow regeneration. owner_probes.py and float_return_probe.py are the prior counterexamples rerun against current code; extra_probes.py adds the earlier publication window and coordinated attacks. Their JSON results retain fresh verifier outputs.

The author's earlier 37-file cross-tree comparison failure remains disclosed history. Acceptance rests on the submitted final-tree pair and this independent fresh run; this review does not independently establish the historical cause of that earlier attempt.

The only diff-check whitespace report is in a preserved raw historical test log. It is not a product finding; do not edit raw evidence to remove it.

## 5. Boundaries and closure

This PASS covers host tool contracts, internal consistency and source binding. It does not prove that an observation source told the truth, establish silicon behavior, pass a scientific gate, resolve A8, or freeze 2c. No production seeds were derived by this review; existing production archives were not changed. New code refuses older archives by name; historical reverification remains the documented version-specific procedure.

Closure may archive this review and update its README in one routine local documentation commit, with no new review round solely for that bookkeeping. Do not rerun tests or mutants for that pure closure documentation.

Push, merge, b4-sim-4/b4-gate-2 seed derivation or execution, full proof, RTL, provisioning, purchasing and board/routing work remain unauthorized.

## 6. Next complete unit authorized: b4-sim-4 execution-plan documents

Proceed directly with a complete **pure-document execution-plan unit**, without another preliminary scope-draft approval. Proposed deliverable: docs/b4_sim4_execution_plan.md, plus closure documentation if convenient. Submit the completed unit once for review.

Use the accepted v0.2.0 method, S=32 and reserved b4-sim-4 label. Preserve the fixed go/no-go rule: B_go=64, one-sided sign-test p <= 0.20 with positives greater than negatives, all seven conditional coverage medians >= 0.50, and every planned seed complete; incomplete inputs give no decision. Preserve the parallel reporting of old and conditional coverage, the target setup boundary/costs, data-influence disclosures and the absence of a scientific negative conclusion from no-go.

The plan must propose execution HEAD, date and deadline for a later named execution authorization; state checks for clean tree, protocol/tool identity, receipt, registry and pooled exclusions; distinguish operator duties from enforced checks; define all failure/interrupt/label-consumption paths; retain raw target returns, quarantine, partial and stopped records; specify fresh verification and commit/blob checks. No tuning, automatic retry, replacement seed/label or next protocol version is authorized.

Read existing files and metadata only. This document unit does not authorize production preflight, seed derivation or printing, smoke/mechanics/model runs, or actual exploration. Execution requires a subsequent ruling naming HEAD, date and deadline. No additional approval is needed for routine document corrections within this plan unit before whole-unit review.

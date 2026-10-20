# Owner review: fourth-round B4 harness repair

Reviewed on 2026-10-19: implementation `15bc214`, evidence tip `43ca57d`. Main stays `d5bf815`.

## Disposition

**Functional repair PASS; one P3 comment/documentation correction remains before unit closure.** No new P1/P2 was found in this review. This is acceptance of the host-only harness repair, not exploration, gate readiness, silicon behavior, or an exposure disposition.

The preceding two P2 findings are repaired. The extra K9/K10 interruption fix is also accepted: an interrupt before any diagnostic returned is `in_progress`, with no diagnostic document, rather than an unsupported `partial` claim. Returned partial records keep their existing treatment.

## Independent validation

The source snapshot was extracted from `43ca57d` into `/tmp/b4_owner_43ca57d_f0ok808x`; all 50 tracked B4 files equal the delivered tree. `15bc214..43ca57d` has no B4/docs source delta. The real tracked tree and refs were not changed.

- All 20 B4 test modules: **Ran 246 tests in 262.659s, OK**, exit 0. The outer production-master guard recorded no attempted production derivation; the delivered integration tests also use fixture schedules and guards.
- Focused mutants: **15 / 15 killed**, exit 0, 323 s; each Ran N > 0 and FAILED. The independently rerun set was M15, M18, M23, M41, M43, M50, M56, M57, M58, and M62–M67. Raw results are in `mutants.txt`. These are a selected independent rerun, not a claim to have independently rerun the complete 67-mutant battery. The author's raw round-4 log separately contains 67 unique killed mutants, each Ran N > 0 / FAILED, without survival, edit-miss or baseline-failure markers.
- IMPORT: all 49 entries, base and copied-function digests match; no unregistered tracked B4 file. The 14 repository-input and six external-source digests also match.
- All nine round-1/2/3 raw verification files are byte-identical to `8d1eefd`. No real `evidence/b4/sim/` namespace was created. Source/docs diff whitespace check passes. The broad evidence diff has one trailing space in the archived raw test-command header; preserve that raw record unchanged.

Independent probe script/output: `probes.py`, `probes_results.json`, `probes_stdout.txt`. Only the previously exposed literal mechanics pair (7,11) is run; both production seed functions are guarded in these probes.

1. Previously preserved whole archives with malformed K7/K9/K10 outer values and nested K9 `pairs:5` now return named findings, without exceptions. Actual verifier CLI: findings JSON, exit 1, empty stderr, no traceback.
2. Real Deadline producer with start 1000.000 and samples 1059.990 / 1060.010 / 1060.030 produces coherent records: 59.99 not expired; 60.01 expired with first expiry 60.01; 60.03 retains first expiry 60.01. Every record passes the existing validator.
3. Full mechanics batches interrupted before K9 or K10 returns use the public clock parameter, with `record()` untouched. K9 tested both before and after the deadline boundary; K10 before it. All retain STOPPED, preserve interrupt as first cause, report incomplete/exit 3 with no summary, record `in_progress` and no diagnostic file, and deep offline verification returns `{}`. A stop at 59.99 and a report at 60.01 are accepted as distinct coherent snapshots.

## P3: invalid-without-file wording contradicts the actual contract

Locations: `b4/host/b4_sim_verify.py:106`, `:115`, and repair evidence `README.md:143` (section 2d, row 3). These claim that an invalid diagnostic may have no document when refusal precedes any returned record. The delivery summary and `15bc214` message make the same claim.

The actual file-set check at `b4_sim_verify.py:262-266` still requires **exactly one** normal partial or quarantine for an invalid K9/K10. It exists; the former comment “checked below” was accurate about that check.

Independent reproduction: fixed mechanics batch, K9 entry raises ValueError before returning a diagnostic. The batch is invalid/exit 1, with STOPPED and report preserved, no summary and no K9 document. Both self-validation and deep offline verification report:

```text
an invalid diagnostic keeps exactly one record: the partial or its quarantine
```

See `probes_results.json:early_invalid_without_record`. This is a conservative rejection, not false completion or loss of a returned readout. The implementation may remain as delivered for this case; do not describe that archive as cleanly verified. The new no-output **interrupt** behavior is different and independently passes, as documented above.

Required follow-up: correct the two source comments/docstrings and evidence row to match the actual stricter file-set policy. An early invalid diagnostic with no record remains an invalid archive with a named verification finding. Preserve previous commits and raw logs; clarify the inaccurate historical delivery claim in the follow-up. Refresh the affected IMPORT digest and rerun the import check. This correction authorizes no change to executable behavior or relaxation of the exactly-one rule; another 246-test/mutant run is unnecessary for comments/documentation plus IMPORT only.

## Remaining boundaries

Prior production-seed exposure remains unresolved for separate owner decision. No production seed set was derived for this review, no seed scan or arm-performance study was performed. Exploration S=32, formal gate, 2c/2d, full proof, push/merge, procurement and board work remain unauthorised. Current branch commits and evidence are retained.

# Owner review of b29b0fb — HOLD (2026-10-20)

Reviewed branch `b4-protocol-v2`, commit `b29b0fb838ae62af6bff436505d200402520230d`, parent `04385ae`.
This is an independent host-tool engineering review. The reviewer did not change tracked files, derive production seeds, run a production preflight/smoke/batch, or perform a push, merge, proof, RTL or board operation.

## Accepted decisions and corrections

- Moving current document revision provenance to `b4/architecture_revision.json`, outside the inventoried method bytes, is accepted. The real-file / IMPORT / fresh-interpreter pin test exercises the right workflow. Keep actual tool and threshold changes bound.
- Disk reconciliation of the durable **valid setup prefix** is accepted. M31 and M45 modify memory values that are overwritten before publication; their survival is acceptable here and must remain reported as survival, not a kill. The reviewer independently reran M31, M45, M51 and M52: respectively SURVIVED, SURVIVED, KILLED, KILLED. No baseline failure or EDIT-MISS.
- The ordinary first/second malformed or drifting target cases now retain quarantine records. Whole-grid None rejection and the earlier ordered-prefix counterexamples are covered. The new exact count/fixture/path and directory-entry checks address the earlier go/no-go probes.
- The archived copy of the previous owner review matches the original ignored review directory byte for byte, with its SHA256SUMS valid.
- IMPORT: 59 entries match, including base and copied-function digests; no tracked B4 file absent. Protected historical B3 paths, old production B4 sim/gate archives, formal model/mapping/hypothesis, copied statistics and PRNG are unchanged from 04385ae.

These corrections do not yet close the unit: three residual P2 findings remain. They concern the existing R2/R3 contracts, not a new research method.

## Independent verification completed

- On clean b29b0fb: **323 tests OK**, 599.263 seconds, exit 0.
- The submitted e2e driver independently regenerated all cases and completed with `as_expected: true`, exit 0, production derivation calls `[0, 0]`. Fresh-process verifiers, refreshed-hash negatives, identity-revision checks and old-archive refusals behaved as expected.
- The regenerated record compared with the submitted `e2e_v2/`: **940 / 940 normalised JSON digests equal**, zero different or missing, comparison exit 0. This independently confirms the dependency-chain correction, subject to the P3 comparison-coverage limitation below.
- The target-cell semantic tamper differed in exactly `pair_000/target_search.json`, `pair_000/task.json`, `pair_000/index.json`, `sim_report.json`; the other 47 files were equal.
- The reviewer did not rerun all 52 mutants; only the four named above. The author's 50/52 count is not presented as an independent full-battery rerun.

## C1 — P2 — the defence-in-depth path quarantines a transformed record, losing the original return

Locations: `b4/host/b4_target.py:121`, `b4/host/b4_sim.py:547`.

`observation_findings` accepts 0.0 / 1.0 because Python compares them equal to 0 / 1. The later type-exact target record validator correctly rejects the float, but the fallback passes `doc` to quarantine instead of the object returned by `port.observe`.

Independent counterexample: on TARGET's first return only, convert the init cell's existing integer to its equal float and add `owner_raw_marker = preserve_entire_original_target_return`. The run stops invalid and verifies clean, but the quarantine's `raw` is the constructed `b4_sim_target_observation` document (`q_grid`, computed digests, etc.), not the original trace (`steps`, original header/context and marker). The marker is absent from both raw and repr. This is a finite JSON input and does not require a custom Python object or nonserialisable value.

Required: type-exact validation of the returned q cells before conversion, and retain access to the original return through the later validation/fallback path. A malformed return must not lose its evidence merely because a later layer is the one that discovers the defect. Test both setup phases, and test that defence-in-depth still keeps the original object when the early validator is bypassed. Do not loosen the record validator to accept floats.

Reproduction: `float_return_probe.py`; output `float_return.json`, `float_return_stdout.txt`. The fresh verifier returned exit 0 / clean true on the current invalid archive; production derivation guards reported `[0, 0]`.

## C2 — P2 — disk reconciliation does not reconcile the quarantined return

Locations: `b4/host/b4_sim.py:538`, `b4/host/b4_sim.py:741`.

`reconcile_setup` indexes a durably written quarantine but does not reconstruct `task_quarantine` or the corresponding invalid task state from it. Those are assigned only after `self.quarantine(...)` returns.

Independent counterexamples at both phases: return a malformed trace, let `Batch.write` durably write `target_search.QUARANTINE.json` / `target_holdout.QUARANTINE.json`, then raise KeyboardInterrupt immediately after that write returns. The stopped archive is incomplete, with prefix 1 / 2 and `task_quarantine: null`; its quarantine is indexed but rejected by both API and fresh-process verifier as `not a file any pair's recorded state accounts for`.

Required: cover the durability window for quarantine as well as the four successful setup files. The recorded state must account for the persisted refused return and its phase. Preserve the observed invalid-return fact and the external interrupt; do not erase, silently ignore, or accept arbitrary unrecorded quarantine files to obtain clean verification. Add interruption after each quarantine's durable publication, including the window before the in-memory file index/state update. Genuine stopped prefixes should reverify, while forged phase/order/quarantine combinations remain refused.

Reproduction: `owner_probes.py`, cases `interrupt_first_quarantine` and `interrupt_second_quarantine`; both fresh verifiers exit 1 with the named file-set finding. The normal first/second quarantine cases verify clean.

## C3 — P2 — quarantine stimulus and expected source are not bound to trusted setup inputs

Location: `b4/host/b4_sim_verify.py:363`.

The verifier holds quarantine phase, pair, role, stage, genome and config digest, but never checks `context.stimulus_sha256` or `context.expected_provenance_sha256` against the setup and its formal source / preceding target observation. Shape-valid strings and null remain their own authority.

Independent refreshed-hash counterexamples on a genuine second-call quarantine, one change per copy:

1. `context.stimulus_sha256 = "a" * 64`;
2. `context.expected_provenance_sha256 = "b" * 64`;
3. `context.expected_provenance_sha256 = null`.

The quarantine schema returns no finding and each deep API verification and fresh-process CLI verification returns clean / exit 0. All report hashes are refreshed. These are known requested stimuli and expected identities, so this is not the accepted limit about a source telling a self-consistent lie.

Required: derive and hold the expected stimulus from the phase and fixed setup/public-parts rule; derive and hold the expected source from the formal batch inputs (first phase), and the retained first observation plus formal batch inputs (second phase). No null expected source on this production setup path. Check all context fields that claim to be derived from trusted inputs, with exact types, while preserving genuine malformed/drifting raw returns as invalid evidence. Test first and second phases with refreshed hashes.

Reproduction: `owner_probes.py`, cases `wrong_stimulus`, `wrong_expected_source`, `missing_expected_source`, in `owner_probe_results.json`.

## P3 to fold into the correction — semantic reasons are still removed globally by fixture normalisation

Location: `evidence/b4/unit_protocol_v2_tool_2026_10_20/e2e_v2_fixtures.py:79` (`VOLATILE` and recursive normalisation).

The dependency-graph normalisation is the right direction. However the recursive drop set still contains **every** `reason` and `detail` key, including deterministic gate row and verdict explanations. The previous R6 explicitly asked not to discard every semantic reason. A small pure-comparison probe changes only a verdict reason and a row reason; the raw hashes differ, but the normalised digests are identical.

Fresh-process verifiers separately hold actual gate explanations to their recomputation, so this is not a demonstrated forged gate verdict. It is a comparison-coverage limitation, not a reason to alter the scientific method or require another standalone review round. Fold its correction into C1–C3: preserve deterministic semantic explanations; normalise embedded root paths / HEADs where necessary, or use narrowly specified field paths for genuinely volatile free text. Include an explanation-only semantic-tamper check and retain the old evidence with a correction note.

## Scope and evidence for the correction

Continue directly inside this already-authorised tool correction unit; no new scope proposal or intermediate permission is needed. Repair C1–C3 and fold the P3 above into the same delivery. Keep the accepted disk-authority design and honest mutant accounting; no requirement to eliminate equivalent mutants.

Run focused affected negative tests/mutants while repairing, then the appropriate final B4 suite and end-to-end checks once the unit is complete, under the agreed evidence proportionality rules. Because host logic changes, run one final full applicable host mutant battery, carrying accepted equivalent survivors honestly; there is no requirement to rerun the whole battery after every intermediate edit. Retain old raw logs, write the correction record once, and deliver the entire corrected unit together. Do not replace the historical production archives or revise the model, hypothesis, domain, certificate, statistics or numerical policy.

No production `b4-sim-4` / `b4-gate-2` preflight, derivation, smoke or execution, full proof, push, merge, RTL, routing or board operation is authorised by this review.

## Reviewer evidence

The scripts and raw outputs are under this ignored review directory. `owner_probes.py [new-output-directory]` creates its hermetic input root with explicit already-exposed mechanics schedule and production derivation guards. `float_return_probe.py [same-output-directory]` continues that temporary root. The delivered run used `/tmp/owner_b29b0fb_final_probes`; an earlier run used the default `/tmp/owner_b29b0fb_probes` and reproduced the same findings. The pure semantic-reason comparison uses a tiny JSON fixture, not a production archive. `review_metadata.json` records the independent full-suite and e2e outcomes; `SHA256SUMS` covers the delivered review artifacts. Generated fixture archives are not copied into Git; `e2e_regenerated/` holds only regeneration digest records and fresh-process logs.

The only `git diff --check` finding is trailing whitespace in the retained first-delivery raw test command, now named `tests_04385ae.txt:2`; it is not a blocker and should not be removed by rewriting that raw log.

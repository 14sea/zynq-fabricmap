# Owner review of e03dca1 / f2c4bca — HOLD

Reviewed 2026-10-18. The branch remains `b4-prework` at `f2c4bcafb9c095927bb3944cfdb0a3f63091846b`;
`main` and `origin/main` remain `d5bf81569140482bded46138a7bdf896eff63bd7`. No implementation, tracked
document, ref, ruling, production exploration directory or board was changed by this review. These review files are ignored.

The repair is substantial and its existing regression tests pass, but the archive verifier can still accept a complete
archive that does not obey the declared execution contract. The finalisation boundary also still allows success after
deadline expiry or input drift. **Do not close the repair or authorise exploration on this evidence.**

## Independent checks

- Snapshot: `git archive f2c4bca` extracted to `/tmp/b4_owner_f2c4bca_7__gab_9`. The suite ran there, not against a modified
  production tree. Command: `python3 -B` bootstrap, `unittest.TestLoader().discover('b4/tests', pattern='test_b4_*.py')`,
  `TextTestRunner(verbosity=2)`. An outer mock of `b4_seeds.master_seed` refused labels beginning `b4-sim-` / `b4-gate-`;
  the integration tests also supplied their own guards on both production master and pair derivation.
  **234 tests, OK, 146.105 s; outer production derivations reached: []** (`tests.txt`).
- The delivered 50-mutant script independently reran in the snapshot: **50 / 50 killed, 497 s**, every mutant
  `Ran N > 0 / FAILED`, no `SURVIVED`, baseline failure or `EDIT-MISS` (`mutants.txt`). Exact command from the snapshot:
  `python3 -B evidence/b4/unit_2b4a_repair_2026_10_18/b4_2b4a_mutants.py /tmp/b4_owner_f2c4bca_mutants.txt`.
- `python3 -B evidence/b4/unit_2b4a_repair_2026_10_18/import_check.py`: **49 entries match**, including recorded base and
  copied-function digests; no unregistered tracked B4 files (`import_check.txt`). Separately rehashed all **6 external
  sources + 14 repository inputs**, all match (`scope_check.json`).
- Ten previously accepted core modules, both hypothesis JSON files and their bytes are unchanged from `cdf2c53`.
  `b4_thresholds.py` changes only the architecture revision reference, not a threshold, grid, tau or anchor rule.
- F1 exposure: compared **85 preserved working-tree / historical records**, including history blobs by `git show`, to
  their surviving source trees and inventory: **zero differences** (`exposure_check.json`). The archive contains 22
  seed-record copies, including historical repetitions. This verifies the saved records, not a complete exclusion set
  for deleted test / mutant trees. No production seed was re-derived to fill missing records.
- F4's report-write / self-validation rejection, F5's immediate K10 stop, F6's quarantine / partial persistence, F7's
  three namespace symlink refusals, and the original F3 malformed-cell / fixed-comparison-set cases are exercised by
  the now-passing suite and inspected in code. The residual findings below cover additional paths.

## R1 — P1: a complete pair can downgrade an arm and bypass its audit

Locations: `b4_sim_schema.py:625`, `b4_sim_verify.py:89`, `b4_sim_verify.py:276`.

The planned-state validator accepts `status: complete` with an arm at `written`. Required files are then derived from
that weaker state, and the deep verifier skips all replay / recompute / completion checks for that arm.

Reproduction from a clean complete mechanics archive:

1. Change only R's state to `written` in report and pair index, leave pair / batch `complete`.
2. Delete `arm_R.audit.json` and refresh indexes.
3. Deep verification returns `{}`.
4. Additionally flip one bit of R's `rng_state_final`, refresh its hash and indexes. Direct `b4_replay.replay` reports
   the wrong final RNG; **archive-wide deep verification still returns `{}`**.

Evidence: `probes_results.json:complete_pair_without_R_audit`,
`probes_more_results.json:unaudited_bad_rng`. Raw modified archives remain at the recorded `/tmp` paths.

Fix criterion: complete pair / batch must require all seven arms audited, all required diagnostics complete, their full
required file set, and clean recomputed audits. A weaker recorded state cannot turn off an invariant of completeness.
Add the downgraded-state + bad-RNG negative case; simple deletion with unchanged `audited` is insufficient.

## R2 — P1: cross-file identity and declared execution inputs are not fully bound

Locations: `b4_sim_verify.py:157`, `b4_sim_verify.py:273`, `b4_sim.py:690`, `b4_sim_schema.py:238`.

The linkage checks stop short of binding every arm to its planned pair / role / operator seed and binding the manifest's
full source descriptor to the actual formal source. Independent probes, with all changed file hashes/indexes refreshed:

- Keep `seeds.json`, the planned operator seed **11**, and all other arms unchanged. Generate R using the already-exposed
  mechanics operator seed **12**, update its wrapper to 12 and recompute its audit, curves and pooled summary. The result
  replays cleanly under 12, but it contradicts the declared pair. **Deep verification returns `{}`**.
- In `pair_000/arm_R.result.json`, change wrapper `pair` to **99**, `role` to **O**, leave actual R result unchanged:
  **deep verification returns `{}`**.
- Change manifest `fabric` to `{"kind":"dropout"}` and mapping `addresses` to **21 nulls**, leave the actual raw source
  as formal truth. Both the manifest validator and deep verifier return no finding.

Evidence: `probes_results.json:wrong_R_operator_seed`, `wrong_pair_role`,
`probes_more_results.json:manifest_source_mismatch`.

These are internal contradictions between recorded authoritative inputs and execution, not the stated limitation that
ledger-only replay cannot detect an observation source's self-consistent lie.

Fix criterion: explicitly bind wrapper and inner result identity to the planned pair / file role, exact engine role,
both seeds, budget and X control seed; bind the complete typed manifest model / mapping / fabric descriptors and relevant
constants to formal inputs and raw provenance. Test self-consistent results from a *different* exposed seed; replay
alone is expected to accept that result and therefore cannot enforce the plan binding.

## R3 — P2: nested scalar types are still not exact

Locations: `b4_sim_schema.py:132`, `b4_sim_schema.py:520`.

- Replace the first K9 observation's `id: 0` with `id: false`.
- Independently replace a K10 unit's integer `index` with the equal floating-point value.

For each, the typed validator returns `[]`, and archive-wide deep verification returns `{}` after reindexing.
Python equality (`False == 0`, `0.0 == 0`) is being used without a preceding type check. The cell values are now protected,
but the claimed exactness of all nested scalar values is not yet met. These cases preserve the numeric conclusion;
the finding is admission of malformed records, not a claim of a changed scientific result.

Evidence: `probes_more_results.json:bool_observation_id`, `float_interaction_index`.
Fix criterion: exact integer checks for ids, references, indices and other arithmetic fields before equality / membership;
keep the validator total. Add direct scalar-type negatives that cannot fail merely through a hash mismatch.

## R4 — P2: expiry during the last archive verification still publishes success

Location: `b4_sim.py:654`–`671`.

`finish` snapshots the deadline before deep verification, then writes the report without checking the clock again.
The verification is a substantial work unit (multiple replays, diagnostics, statistics), followed by a separate report
publication unit. A soft deadline permits the started unit to finish; it does not permit a new success publication after
expiry with a stale on-time record.

Isolated finalisation probe: deadline 60 s, clock advanced by 10,000 s after the real deep verifier returns `{}`.
Result: **complete / exit 0**, summary and report published, reported elapsed **0 / expired false**, actual elapsed 10,000.
The independent *full `run_batch`* probe confirms the same result (1,654 prior checks), not just re-entry into `finish`.

Evidence: `probes_results.json:deadline_after_deep_verification`,
`probes_more_results.json:full_run_finalisation`.
Fix criterion: check at the final verification / publication boundary, record the current deadline after the check, and
persist `incomplete` with no pooled summary on expiry. Test expiration in the final verifier, not only before it.

## R5 — P2: the final input/tree checkpoint precedes the deep verification

Locations: `b4_sim.py:866`–`879`, `b4_sim.py:661`–`671`.

The newly expanded checkpoint covers the intended input classes, but no checkpoint follows deep verification. In the
isolated probe, modify the hermetic tree's architecture document after the real verifier returns and before publication:
**complete / exit 0**, report published, self-validation `{}`, input no longer matches its recorded digest.
The full-run finalisation probe also reproduces it. Only a temporary copied input was changed and restored; no vendor
source or tracked production file was modified.

Evidence: `probes_results.json:input_drift_after_deep_verification`,
`probes_more_results.json:full_run_finalisation`.
Fix criterion: repeat input / registry / tool / tree checks after the long deep verification and before success
publication, with deadline checks around those units. Do not rely on an earlier checkpoint as the end snapshot.

## Probe provenance and limits

Commands: `python3 -B build/wip/owner_review_f2c4bca_2026_10_18/probes.py` and `.../probes_more.py`;
scripts, JSON results and stdout are beside this report. They import the reviewed snapshot, construct a hermetic input
tree using the delivered test helper, and forbid both production seed functions throughout. Complete mechanics schedules
use only **(7,11)** and **(3,13)**; the wrong-operator probe uses exposed value **12**. No S=32 batch, new seed scan,
threshold selection or formal model exploration was performed. Their numeric K values are not used as research results.

The first version of the owner's finalisation probe accidentally retained the baseline report's own file entry when
re-entering `finish`, causing an unrelated self-validation failure. That probe error was corrected by restoring the
actual pre-publication file list for each case. The first script/results remain as `probes_attempt1*` and are not used
as findings. The separate full-run probe needs no re-entry or file-list adjustment and confirms R4 / R5.

Whole-diff `git diff --check cdf2c53..f2c4bca` reports trailing spaces in **two preserved original owner raw logs** only.
This is not a code defect and those raw records should not be silently edited for whitespace cleanup.

## Disposition

**HOLD on the repair batch.** F1's test isolation and the preserved portion of the exposure correction are accepted as
checked above. Exposure disposition remains separate and unresolved: do not treat missing historical sets as excluded
or silently rename/re-anchor/re-draw. Keep current commits and raw records. The five residual findings need fixes and
focused negative tests before repair closure; existing tests/mutants passing does not establish the missing invariants.
Exploration, gate, push, merge, full proof and board work remain unauthorised.

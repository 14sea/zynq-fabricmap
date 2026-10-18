# Unit 2b-4a — the repair after the owner's HOLD on `cdf2c53` (2026-10-18)

**Standing.** The owner's complete review of the 2b-4a batch (A `8939fb9`, B `feda985`, C `edfc93c`, evidence `cdf2c53`)
returned **HOLD** on nine reproduced gaps F1–F9 (`owner_review_cdf2c53/README.md`, with the owner's probe scripts, their
outputs and the owner's independent 207-test / 21-mutant results, copied here unchanged from `build/wip/`). The owner
authorised a focused B4 follow-up: fix the unsafe tests first and record their past exposure, keep the existing commits,
failure records and thresholds, change no old production module, derive no production set, run no exploration, then
re-run the B4 suite and the necessary mutants with explicit safe fixture schedules and deliver the batch for review.
The anchor and the label are not changed here; no set is redrawn; the exclusion set is not declared complete. **The
treatment of the prior exposure (below) is the owner's pending decision before any exploration.** The raw readouts are
retained in full (about 190 MB for S = 32 is acceptable to the owner; no compression or thinning was implemented).

## 1. The prior exposure (F1): what happened, what is preserved, what is uncertain

**What happened.** At `edfc93c` the harness's integration tests (`b4/tests/test_b4_sim.py`) ran `run_batch` with the
production labels `b4-sim-1` / `b4-sim-2`, the real anchor (the pinned hypothesis digest) and the real exclusion sources,
on hermetic repository copies under the system temporary directory. Each such batch derived the label's master and drew
S = 2 pairs against the pooled exclusion set — the formal act of §9.2, whatever directory it wrote to. Because each test
class commits every batch directory into its hermetic tree, the registry of the next batch in the same tree held the
previous set, so **consecutive batches in one tree drew successive, different `b4-sim-1` sets** (set 1 against the
38 sources; set 2 against the sources plus set 1; …). The derivation is deterministic in (label, anchor, S, exclusion
snapshot), so the same sequence recurred in every fresh tree. The runs that did this:

- the author's smoke test before commit A (one complete `b4-sim-1` S = 2 batch; the earlier README claimed "no pair was
  drawn" — false, corrected in `evidence/b4/unit_2b4a_2026_10_18/README.md`);
- every run of `test_b4_sim.py` by the author: three full-suite runs (pre-commit 217 and 218, clean-tree 218) and the test
  development runs; per run, the classes `CompleteBatch` (one `b4-sim-1` set, then one `b4-sim-2` set against a registry
  holding it), `InvalidStops` (up to seven consecutive `b4-sim-1` sets) and `IncompleteStops` (up to three);
- every mutant whose named tests included a `test_b4_sim` integration test (M1, M15, M16, M18–M23, M31, M32), twice per
  mutant (the baseline and the mutated copy — under M1 the mutated copy ignored the registry, so its second batch drew
  against a different exclusion state than production would);
- the owner's interrupted full-suite re-run (`owner_review_cdf2c53/original_suite_interrupted.txt`): six consecutive
  `b4-sim-1` batches in one tree before the interrupt.

**What is preserved.** Two hermetic test trees still existed under `/tmp` when the repair began; every seed record they
held — in the working tree and in every commit of the tree's own git history — is copied as found under `exposure/`
(`seeds.json`, `manifest.json`, `STOPPED.json`, `sim_report.json` per run directory; a listing with the digest and size of
every file of each run; `inventory.json` with the trees' commits). The values are in those files and are not repeated here.

| record | label | S | archived sets in its registry | batch status | generated (UTC) |
|---|---|---|---|---|---|
| `b4sim_jv9da6xe/worktree/b4-sim-1_20261018T165413Z` | b4-sim-1 | 2 | 0 | complete | 2026-10-18T16:54:13Z |
| `b4sim_rvf1ws_h/history/375253915f14/b4-sim-1_t001` | b4-sim-1 | 2 | 0 | invalid | 2026-10-18T18:28:56Z |
| `b4sim_rvf1ws_h/history/375253915f14/b4-sim-1_t002` | b4-sim-1 | 2 | 1 | invalid | 2026-10-18T18:28:57Z |
| `b4sim_rvf1ws_h/history/375253915f14/b4-sim-1_t003` | b4-sim-1 | 2 | 2 | invalid | 2026-10-18T18:28:58Z |
| `b4sim_rvf1ws_h/history/375253915f14/b4-sim-1_t004` | b4-sim-1 | 2 | 3 | invalid | 2026-10-18T18:29:02Z |
| `b4sim_rvf1ws_h/history/375253915f14/b4-sim-1_t005` | b4-sim-1 | 2 | 4 | invalid | 2026-10-18T18:29:02Z |
| `b4sim_rvf1ws_h/history/5a47e5e9b202/b4-sim-1_t001` | b4-sim-1 | 2 | 0 | invalid | 2026-10-18T18:28:56Z |
| `b4sim_rvf1ws_h/history/5a47e5e9b202/b4-sim-1_t002` | b4-sim-1 | 2 | 1 | invalid | 2026-10-18T18:28:57Z |
| `b4sim_rvf1ws_h/history/baf165d0db29/b4-sim-1_t001` | b4-sim-1 | 2 | 0 | invalid | 2026-10-18T18:28:56Z |
| `b4sim_rvf1ws_h/history/baf165d0db29/b4-sim-1_t002` | b4-sim-1 | 2 | 1 | invalid | 2026-10-18T18:28:57Z |
| `b4sim_rvf1ws_h/history/baf165d0db29/b4-sim-1_t003` | b4-sim-1 | 2 | 2 | invalid | 2026-10-18T18:28:58Z |
| `b4sim_rvf1ws_h/history/d3d560725477/b4-sim-1_t001` | b4-sim-1 | 2 | 0 | invalid | 2026-10-18T18:28:56Z |
| `b4sim_rvf1ws_h/history/ea987288f097/b4-sim-1_t001` | b4-sim-1 | 2 | 0 | invalid | 2026-10-18T18:28:56Z |
| `b4sim_rvf1ws_h/history/ea987288f097/b4-sim-1_t002` | b4-sim-1 | 2 | 1 | invalid | 2026-10-18T18:28:57Z |
| `b4sim_rvf1ws_h/history/ea987288f097/b4-sim-1_t003` | b4-sim-1 | 2 | 2 | invalid | 2026-10-18T18:28:58Z |
| `b4sim_rvf1ws_h/history/ea987288f097/b4-sim-1_t004` | b4-sim-1 | 2 | 3 | invalid | 2026-10-18T18:29:02Z |
| `b4sim_rvf1ws_h/worktree/b4-sim-1_t001` | b4-sim-1 | 2 | 0 | invalid | 2026-10-18T18:28:56Z |
| `b4sim_rvf1ws_h/worktree/b4-sim-1_t002` | b4-sim-1 | 2 | 1 | invalid | 2026-10-18T18:28:57Z |
| `b4sim_rvf1ws_h/worktree/b4-sim-1_t003` | b4-sim-1 | 2 | 2 | invalid | 2026-10-18T18:28:58Z |
| `b4sim_rvf1ws_h/worktree/b4-sim-1_t004` | b4-sim-1 | 2 | 3 | invalid | 2026-10-18T18:29:02Z |
| `b4sim_rvf1ws_h/worktree/b4-sim-1_t005` | b4-sim-1 | 2 | 4 | invalid | 2026-10-18T18:29:02Z |
| `b4sim_rvf1ws_h/worktree/b4-sim-1_t006` | b4-sim-1 | 2 | 5 | no report (interrupted) | 2026-10-18T18:29:03Z |

`b4sim_jv9da6xe` is the author's smoke test (2026-10-18 16:54 UTC; a default-named run directory). `b4sim_rvf1ws_h` is
the owner's interrupted re-run (18:28–18:29 UTC): `t001`–`t005` are the five `InvalidStops` batches that returned, each
against a registry one larger than the last; `t006` is the batch the interrupt caught (seeds derived, no report). The
history copies are the same records at the tree's earlier archive commits (identical bytes where the same run appears).

**What is uncertain.** Every other test tree was deleted by its test's cleanup, and every mutant copy by the battery; no
record of those runs exists. Their values are recoverable only by re-deriving (the derivation is deterministic), which
this repair deliberately did NOT do: re-deriving would be another draw of the production sets. What can be said without
re-deriving: the sets drawn were, in every tree, the deterministic sequence `b4-sim-1` set 1, 2, … (up to seven in a tree)
and `b4-sim-2` set 1 against a registry holding `b4-sim-1` set 1 — the same values on every repetition except under the
M1 mutant's second batch. No value from any of these runs was read as a result or compared with a threshold by the
author; no exploration verdict was formed. Whether the `b4-sim-1` label can still carry the first exploration, what joins
the exclusion set, and whether any derivation is to be re-done for the record are the owner's decisions.

## 2. The repair, gap by gap

| gap | what was wrong (reproduced by the owner) | what changed | where it is tested |
|---|---|---|---|
| F1 P1 | integration tests derived production sets; the README said otherwise | `b4_sim.FixtureSchedule`: a `b4-mech-<n>` MECHANICS batch takes an explicit schedule of values already exposed under §9.2 (`b4_seeds.FIXTURE_VALUES`), derives nothing (`seeds.json` 1.1.0 `fixture: true`, `master_seed: null`, no anchor digest); a production label with a schedule or a fixture label without one is refused before any write; the CLI has no fixture path. `test_b4_sim.py` uses fixture schedules only (7 / 11, 8 / 12, 3 / 13, 5 / 12); every class replaces `b4_seeds.master_seed` / `pair_seeds` with guards that raise and asserts at teardown they were never called. The registry reads a fixture set as `seeds_fixture` (its values already pooled). | `test_b4_sim` Preflight (refusals), CompleteBatch (fixture seeds, guard counts), `test_b4_seeds` (the fixture form, the registry) |
| F2 P1 | `validate_run_dir` checked surviving file shapes only | `b4/host/b4_sim_verify.py`: the archive-wide verifier — the required file set of the recorded status and of every pair's recorded state, no unlisted or duplicate file, every listed digest / size, seeds ↔ manifest ↔ report linkage, STOPPED exactly when not complete and equal to the report's copy, pair indexes, every file against its validator with the pair's task bound, and (deep) every conclusion recomputed from the raw readouts on the formal model: arm re-audits held to the audit files, controls, K7 prefixes, K9 / K10 recompute, curves, the pooled summary. The batch runs it on itself before writing the report (`self_validation`); offline CLI `b4_sim_verify.py <run_dir>`. The authenticity limit is stated. | `test_b4_sim` TheArchiveVerifier (tampered curves, a deleted arm, a tampered pooled mean, a stray file, a stray STOPPED, a malformed manifest; the clean archive), CompleteBatch (`verify_run_dir == {}`) |
| F3 P1 | comparison-set completeness and nested types not enforced; a q cell of 2 accepted; `manifest_findings(arm_order=None)` raised | validators total and type-exact on nested values (q cells 0 / 1 / null with exact dimensions; ids 0..n-1; genomes 21-bit; scores ints; corner genomes by formula; index = f11 − f10 − f01 + f00; observation references exist; one provenance, the formal one); the FIXED sets enforced (`k9.canonical_findings`, `k10.canonical_findings`: complete = exactly the 1 184 pairs / 420 units in order, partial = a prefix); the declared task bound (seed, digest, stimulus digest); every validator wrapped so an exception is a finding, never raised; a K9 / K10 record that does not validate is quarantined and the batch invalid | `test_b4_sim` TheArchiveVerifier, InvalidStops (a bad q cell from the source → invalid / quarantine), `test_b4_k9`, `test_b4_k10` (duplicated / missing / empty records named) |
| F4 P1 | a report-write failure or a non-empty self-validation still returned complete / exit 0 | `finish`: the archive verification and the report are conditions of success — a finding on a would-be complete batch makes it `invalid` (kind `self_validation`, STOPPED written, no summary, exit 1); a report that cannot be validated or written leaves `sim_report.ERROR.txt`, status `invalid`, exit 1, `original_status` recorded; the report validator refuses a complete report with an expired deadline or a non-empty self-validation | `test_b4_sim` InvalidStops (`test_self_validation_findings_and_an_unwritable_report_are_never_complete`), TheSummaryAndTheValidators |
| F5 P2 | K10 observed three more corners after a refused first corner | the driver's scoring function converts a `DomainRefusal` into `CornerRefused`, which the unchanged `b4_stats.four_corner` does not catch: no further corner is observed; the unit is recorded with its refused corner named and the corners obtained before it; `K10Invalid` carries the partial | `test_b4_k10` (`test_no_corner_is_observed_after_the_first_refused_one`: port calls 1 / 2 / 4 at the first / second / fourth corner), `test_b4_sim` InvalidStops (100 calls, 99 observations) |
| F6 P1 | a K9 refusal lost the memo; a malformed returned RunResult was dropped with the plan saying `in_flight` | `coverage` / `seed_k10` attach the partial record to ANY exception (`k9_partial` / `k10_partial`: a refusal or error → `invalid` named; an interrupt → `stopped`); the harness writes it (or its quarantine) before stopping; a returned RunResult that does not validate is written raw to `arm_<role>.result.QUARANTINE.json` with the findings and the arm's state is `result_malformed`; interrupted calls stay `result_unavailable` | `test_b4_sim` InvalidStops (`test_a_refusal_inside_k9_keeps_the_partial`, `test_a_malformed_returned_result_is_quarantined_not_lost`), IncompleteStops (an interrupt inside K9), `test_b4_k9`, `test_b4_k10` |
| F7 P1 | a tracked symlink `evidence/b4/sim` → outside was accepted | the root is resolved once; `evidence`, `evidence/b4`, `evidence/b4/sim` must each be a real directory (none a symlink); the output path must be literally `<root>/evidence/b4/sim/<label>_…` (no `..`, no normalisation); after creation the directory must resolve to itself and the chain is checked again | `test_b4_sim` Preflight (`test_a_symlinked_namespace_is_refused_at_every_level`: three levels, explicit and default output, nothing written outside) |
| F8 P2 | a batch whose deadline expired during final validation reported complete / exit 0 | `dl.check()` after the last statistics unit, after the final checkpoints and before every finalisation unit; a batch whose deadline expired is `incomplete` with every pair's work kept and no summary | `test_b4_sim` IncompleteStops (`test_the_deadline_expiring_before_finalisation_is_incomplete`) |
| F9 P2 | the checkpoints covered neither the six vendor sources nor the 38 exclusion sources nor the registry | the manifest binds and every checkpoint holds: the root inputs, the hypothesis's repository sources, the 38 exclusion sources (`inputs`), the six vendor sources by absolute path (`external_inputs`), the tool files, and the archived-set registry snapshot (`exclusion.registry_snapshot`, own directory excluded); the code root's HEAD / cleanliness are recorded apart from the input root (`code_root`) | `test_b4_sim` CompleteBatch (the manifest), InvalidStops (`test_an_unexpected_exception_and_the_three_drifts`: an input, an exclusion source, a vendor digest through the digest function with the vendor file untouched, a foreign run directory) |

Not changed: `b4_stats`, `b4_engine`, `b4_carto`, `b4_replay`, `b4_execution`, `b4_landscape`, `b4_rng`, the model and
the loaders, every threshold, the grid, τ, the anchor rule, the hypothesis. The seeds schema is 1.1.0 (the `fixture`
flag), the manifest schema 1.1.0 (`fixture`, `external_inputs`, `code_root`, `exclusion.registry_snapshot`), the K9 record
1.1.0 (`invalid`); no 1.0.0 record exists under the real `evidence/b4/sim/` (the directory does not exist).

## 2b. The second round — the owner's HOLD on `f2c4bca` (R1–R5)

The owner's second review (`owner_review_f2c4bca/README.md`, with the probe scripts and raw results, copied here unchanged
from `build/wip/`) independently confirmed 234 tests OK, 50 / 50 mutants killed, 49 IMPORT entries equal, the F1 isolation
and the 85 preserved exposure records (zero differences), and reproduced five residual gaps with new probes. Each is
fixed below with a negative test written after the owner's probe (the archive tampered one way at a time, every digest
re-indexed so that the finding is the contract's, not a stale hash).

| gap | what the owner reproduced | what changed | where it is tested |
|---|---|---|---|
| R1 P1 | a complete pair with R recorded `written`, its audit deleted and its final RNG state flipped: deep verification `{}` | the planned-record validator and the pair-index validator refuse a complete pair with any arm not `audited` or K7 / K9 / K10 not `complete`; independently, the deep verifier re-audits every arm of a complete pair whatever its recorded state and names an arm without an audit; the completion finding's text is deterministic so the recorded audit equals the recomputed one | `TheArchiveVerifier.test_a_downgraded_arm_state_cannot_switch_the_audit_off`, `…test_the_deep_verifier_re_audits_even_if_the_record_validators_were_bypassed` (the record validators mocked away: the deep stage alone refuses), `TheSummaryAndTheValidators` |
| R2 P1 | a self-consistent R generated under exposed operator seed 12 beneath a plan saying 11: `{}`; a wrapper naming pair 99 / role O: `{}`; a manifest with `fabric: dropout` and 21 null addresses: no finding | `arm_result_findings(doc, task, expect)`: the wrapper's pair / role / seeds equal the planned ones (from the file's position), `engine_arm` is the role's, the budget is B_max, the result's seeds / budget / task digest / provenance are the pair's and the formal source's, `x_control_seed` is the planned X seed or null — applied at write time by the harness and offline by the verifier; every pair file names its pair and (audits, quarantines) its role; curves and index name the planned seeds; the index's arm states are the plan's; the manifest's hypothesis / mapping / fabric descriptors are the formal inputs' (`formal_provenance()`), its constants the harness's, its thresholds the table's; every memo provenance equals the formal one | `TheArchiveVerifier.test_every_record_is_bound_to_the_planned_pair_and_the_formal_source` (the foreign-seed R replays clean and is refused by the binding) |
| R3 P2 | `id: false` and a float interaction index accepted | `_int` before every equality on ids, references, indices, counts and τ; every recomputed value (audits, prefixes, curves, summaries, max / counts) compared as canonical JSON text, so `2`, `2.0` and `true` differ | `TheArchiveVerifier.test_nested_scalars_are_exact_in_type` (id false, float index, float counts, float τ, a float in the pooled summary) |
| R4 P2 | the clock crossing the deadline during the deep verification: complete / exit 0 with an on-time record | after the deep verification `finish` checks the deadline, holds the inputs, checks again, and only then takes the deadline record and publishes; expiry → `incomplete`, stage `publication`, no summary | `IncompleteStops.test_the_deadline_expiring_during_the_final_verification_is_incomplete` (a full `run_batch`) |
| R5 P2 | an input changed during the deep verification: complete / exit 0 | the same post-verification checkpoint: `hold_inputs("publication")` and `hold_tree()` → `invalid`, `input_drift`, stage `publication` | `InvalidStops.test_an_input_drift_during_the_final_verification_is_invalid` (a full `run_batch`) |

Not changed in this round: the model, the engine, the cartographer, the replay, the statistics primitives, every
threshold, the seeds module, the anchor. The exposure disposition (section 1) remains the owner's.

## 2c. The third round — the owner's HOLD on `6c00156` (three residual findings)

The owner's third review (`owner_review_6c00156/`, copied unchanged) independently confirmed 240 tests OK, 57 / 57 mutants,
49 IMPORT entries, that every round-2 probe is now refused and that the runtime publication paths (R4 / R5) are fixed in a
full `run_batch`; it reproduced three residual gaps, each fixed below with a negative test after the owner's probe (every
digest re-indexed, the pooled summary recomputed where it changes, so that the finding is the contract's).

| gap | what the owner reproduced | what changed | where it is tested |
|---|---|---|---|
| 1 P1 | a GENUINE partial K10 (the production driver stopped after 1 / 420 units: `complete: false`, a stop record, no outcome) replacing the complete one under a plan still saying complete, summary and digests recomputed: `{}` | `b4_sim_verify.diagnostic_state_findings`: a plan's K7 / K9 / K10 state is confirmed by its document — `complete` needs a complete document with neither stop nor invalid record and the full fixed set (1 184 pairs / 420 units); `partial` a stopped, not-complete document; `invalid` an invalid partial (or its quarantine); `not_started` no document; a complete pair needs all three complete; the pooled row is built only from complete K9 / K10 documents | `TheArchiveVerifier.test_a_genuine_partial_diagnostic_cannot_belong_to_a_complete_batch` (a production partial K10 and a production partial K9) |
| 2 P2 | `pairs_total` 1184.0, `units_total` 420.0, a corner genome `false` accepted | `_int` on `pairs_total`, `units_total`, K7 budgets / counts, K9 pair backgrounds; `_genome` on corner genomes; the curves' T and the canonical-set sequences compared as JSON text; `k9/k10.canonical_findings` exact on the totals | `TheArchiveVerifier.test_the_remaining_counts_and_genomes_are_exact_in_type` |
| 3 P2 | manifest `deadline_s` 1 vs report 3600 accepted; report `elapsed_s` 10 000 with `expired: false` accepted | `b4_sim_schema.deadline_findings`: the record's exact types and ranges and its self-consistency at the record's millisecond precision (`expired` ⇔ `elapsed_s ≥ seconds` up to 1 ms; `first_expired_at_s` exactly when expired, within [seconds, elapsed_s]); applied to the report's and STOPPED's records, bound to the manifest's `deadline_s` (written before the first observation); the stop record's elapsed time ≤ the report's; a complete report's elapsed time ≤ its seconds; a late stopped record remains a consistent record | `TheArchiveVerifier.test_the_deadline_records_are_consistent_and_bound_to_the_manifest` (boundary and late-stop positives, six malformed negatives, the manifest binding) |

Not changed in this round: the model, the engine, the cartographer, the replay, the statistics primitives, every
threshold, the seeds module, the anchor, the deadline module (its record is validated, not altered).

## 3. Verification on the clean committed tree — round 1 (HEAD `e03dca1`; files `round1_*`)

Everything here ran on `b4-prework` at **HEAD `e03dca1`** (the repair commit) with `git status --porcelain` empty apart from
this directory's own new files (each header records it). The files are raw tool output with a three-line header (HEAD, the
exact command, the UTC time); nothing in them was edited. No production set was derived by any of these runs: every batch
inside them runs on a `b4-mech-<n>` fixture schedule under the derivation guard.

| file | command (from `/home/test/zynq_fabricmap`) | result |
|---|---|---|
| `round1_tests.txt` | `python3 -m unittest -v` over the 20 `b4.tests.test_b4_*` modules (the list is in the header) | **Ran 234 tests … OK**, exit 0 |
| `round1_mutants.txt` | `python3 evidence/b4/unit_2b4a_repair_2026_10_18/b4_2b4a_mutants.py evidence/b4/unit_2b4a_repair_2026_10_18/mutants.txt` (the 50-mutant script of that commit; the archived script is now the 57-mutant one) | **50 / 50 killed** in 497 s; every line `KILLED … [Ran N > 0, FAILED]` with the failing tests named; no `SURVIVED`, `BASELINE-NOT-GREEN` or `EDIT-MISS` line |
| `round1_import_check.txt` | `python3 evidence/b4/unit_2b4a_repair_2026_10_18/import_check.py` | 49 entries; file digests, base digests and copied-function digests all equal; no tracked file under `b4/` without an entry |

**The battery** (`b4_2b4a_mutants.py`, archived here as run): the 32 mutants of the previous unit — M1 (the registry) now
held by the seeds tests alone, M16 (K10 absorbing a refusal) re-targeted to the `CornerRefused` conversion, M20 (the result
written only after the audit) and M22 (the drift test's new name) re-targeted to the moved code — and 18 new ones, one per
repaired contract: M33–M36 F1 (a non-exposed fixture value accepted; a production label on a schedule; a master derived
for a fixture batch, which the tests' guard turns into a failure; a fixture document under a production label), M37 F7,
M38–M40 F6, M41–M42 F4, M43 F8, M44–M45 F9, M46–M47 F2, M48–M50 F3. On the pre-commit dry run two survived — M36 (the
test's mutation was caught by the anchor-label rule, not the label rule) and M37 (the symlink was caught by the re-check at
creation, not by the pre-flight) — and were killed by sharpening the tests to the exact contract (both tests now fail for
the named reason), before the commit. The two defects are recorded because a kill for another reason is not a kill.

**Independence.** These are the author's runs. The owner's independent results at `cdf2c53` (207 tests, 21 mutants) are in
`owner_review_cdf2c53/`; nothing here re-labels them.

**Status.** `b4-prework` holds A `8939fb9`, B `feda985`, C `edfc93c`, the evidence `cdf2c53`, this repair `e03dca1` and its
verification commit, local only — not pushed, not merged; `main` is `d5bf815`. Delivered for the owner's batch review.
Pending the owner: the treatment of the prior exposure (section 1). Still not authorised: the S = 32 `b4-sim-1`
exploration, the formal gate tool and run, units 2c / 2d, the full proof, push / merge, procurement and board work.

## 4. Verification on the clean committed tree — round 2 (HEAD `33c1739`; files `round2_*`)

Same method as section 3 (raw tool output with a three-line header; porcelain empty apart from this directory's own files;
every batch on a `b4-mech-<n>` fixture schedule under the derivation guard; nothing edited).

| file | command (from `/home/test/zynq_fabricmap`) | result |
|---|---|---|
| `round2_tests.txt` | `python3 -m unittest -v` over the 20 `b4.tests.test_b4_*` modules | **Ran 240 tests … OK**, exit 0 |
| `round2_mutants.txt` | `python3 evidence/b4/unit_2b4a_repair_2026_10_18/b4_2b4a_mutants.py evidence/b4/unit_2b4a_repair_2026_10_18/round2_mutants.txt` | **57 / 57 killed** in 642 s; no `SURVIVED`, `BASELINE-NOT-GREEN` or `EDIT-MISS` line |
| `round2_import_check.txt` | `python3 evidence/b4/unit_2b4a_repair_2026_10_18/import_check.py` | 49 entries, every digest equal; no tracked file under `b4/` without an entry |

**The battery** is the archived 57-mutant script (the 50 of round 1 plus M51–M57, one per residual finding). On the pre-commit
dry run M52 (the deep re-audit of an unaudited arm removed) survived: the planned-record validator and the pair-index
validator refuse such an archive before the deep stage is reached, so the deep check is defence in depth. It is kept, and
held by a test that mocks the two record validators away and shows the deep stage alone refusing — recorded here because a
check nothing can reach is not a check. The commit message of `33c1739` says 239 tests on the pre-commit tree; the
defence-in-depth test added afterwards makes 240 on the committed tree.

**Status.** `b4-prework`: A `8939fb9`, B `feda985`, C `edfc93c`, evidence `cdf2c53`, repair `e03dca1` + `f2c4bca`, second round
`33c1739` + this verification commit; local only — not pushed, not merged; `main` is `d5bf815`. Delivered for the owner's
review. Pending the owner: the treatment of the prior exposure (section 1). Still not authorised: the S = 32 `b4-sim-1`
exploration, the formal gate tool and run, units 2c / 2d, the full proof, push / merge, procurement and board work.

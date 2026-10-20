# B4 pre-work, unit X-A — control X as address relabelling (2026-10-18; the owner's ruling of 2026-10-18 §4, opened after D1′'s PASS on `e0b5f04`)

**Scope delivered (the ruling §4, the design note `evidence/b4/unit_2b2_followup2_2026_10_18/x_control_design.md`
option X-A with the owner's corrections):** B4 implementation, tests, `b4/IMPORT.json`, `docs/b4_architecture.md`
§8 / §9 / §13 (contract text only: the transformation, the isomorphism, the residual structure, the non-guarantee;
no threshold, no τ). The formal hypothesis, mapping and model behaviour, and every old pinned input, unchanged. Mechanism
only: no arm advantage measured, no seed scan, no landscape exploration, no gate number.

## The four conditions of the ruling, and where each lives

| condition | implementation | tests |
|---|---|---|
| 1. π from an **independent control RNG**, fixed **before the base observation**, never the operator's generator; Fisher–Yates-with-rejection attempts are a generation procedure, every attempt and the final π auditable; replay re-derives π from the control seed and checks the record | `b4_engine.run(arm="X", …, control_seed=c)`: `bc.derangement_attempts(control_seed, n)` before any observation; `x_control_seed`, `x_perm`, `x_perm_attempts` in the result; the operator's `Rng(operator_seed)` untouched by it; `b4_replay.structural_findings` re-derives the attempts and π and names a mismatch | `ControlXA.test_pi_is_drawn_before_the_base…` (DOMAIN at the base: π and attempts already recorded; DOMAIN at attempt 2: the operator's generator state equal under control seeds 5 / 6 / 7 and equal to O's, the same first candidate), `ControlX.test_the_attempts_are_recorded…` (a seed needing ≥ 2 attempts, the rejected ones with a fixed point, the sequence equal to the rule by hand), `ControlXARecords.test_pi_not_derived_from_the_control_seed_is_named` |
| 2. the ledger keeps the **true genome**; the cartographer's π(genome) reconstructible; the per-specimen shadow check covers every state of the design note; residual structure post hoc only, with `groups_moved` defined | `bc.relabel_genome` (bit a → bit π(a); the q grid untouched); `learn()` ingests the relabelled genome into X's cartographer and the true one into the shadow; the ledger entry carries `genome` = the observed candidate; `bc.isomorphic_addresses` compares, for every a, X's relation at π(a) with the shadow's at a — cells, presence, pair counts, contexts, evidence references — plus version, multi-bit and specimen counts; `bc.residual_structure` at the end only: `partition_preserved` = the two partitions equal as sets of address sets, `groups_moved` = the true groups that are not, as address sets, groups of X's partition (`groups_true`, `groups_x`, both group lists reported) | `CompleteRuns.test_o_learns_online_and_x_stays_isomorphic` (each search child = parent ⊕ bits over TRUE addresses; X's final map equals the cartographer rebuilt over the relabelled ledger genomes; the residual equals the one recomputed from the ledger), `ControlX.test_x_a_relabels_the_addresses_and_stays_isomorphic_in_full` (one evidence reference off is named), `ControlXA.test_the_operator_s_group_moves_use_x_s_relabelled_groups` (every group move ⊆ a group of X's map at that moment; at this seed at least one not ⊆ any true group) |
| 3. isomorphism failure = **control failure**, not DOMAIN / KILL / pre-observation refusal; a stated commit point; the successful observations kept; after it no draw, no evaluation, no selection; engine and replay consistent | `b4_engine.ControlFailure`, raised in `entry()` right after the exposing observation is in the ledger, scored and counted (for a search child: among the pending children, `evals` / `cost` / `best_trace` updated) and after the ingest — the commit point; `result.control_failure` = {phase, attempt, seq, findings, successful_observations, rng_state, population_commitment, map_version, map_commitment, shadow_commitment}; `completed` / `search_completed` False, no champion; the generator not rolled back; `b4_replay`: the record typed and consistent (attempt = seq = ledger length, the map state the exposing entry's, no terminal / refusal beside it), a control failure that does not reproduce on re-execution is a named finding | `ControlXA.test_a_control_failure_is_its_own_event_at_its_commit_point` (an injected contract break at the 5th ingest under `mock.patch.object` with its stop: ledger 5, evals 4, pending 4, no generation close, the population before the generation, `port.calls` 5, the generator state the event's; replays clean under the same break, named without it; a record claiming a refusal beside it refused), `ControlXARecords.test_a_malformed_residual_or_control_failure_is_a_named_finding` |
| 4. the hand **partition-changing** fixture and the **partition-preserving** derangement counterexample; no test requires every π to change the partition; base / mid-run termination, control failure, full replay, meaningful mutants | `ControlX.test_the_two_hand_fixtures_of_the_ruling`: groups {0,1}, {2,3}, {4..8}; `changing` = [1,2,3,0,5,6,7,8,4] → isomorphism holds, `partition_preserved` False, `groups_moved` 2; `preserving` = [1,0,3,2,5,6,7,8,4] (swap within the pairs, rotate the five: no fixed point) → isomorphism holds, `partition_preserved` True, `groups_moved` 0, reported as such | plus `ControlXA.test_domain_mid_generation_under_x_keeps_pi_and_reports_the_residual_post_hoc`, the replay's clean runs (X complete, base-terminated, mid-generation-terminated), `mutants.txt` |

The lane permutation of 2b-2 (`permute_grid` / `isomorphic`) stays as the cartographer's symmetry test
(`ControlX.test_permute_and_isomorphism`); no fifth arm; `ARMS` unchanged.

## Tests (`tests.txt`)

The eleven B4 modules: **Ran 128, OK**, zero skip (107 before). Per module: test_b4_carto 12, test_b4_engine 15, test_b4_execution 6, test_b4_ff_hypothesis 11, test_b4_ff_mapping 14, test_b4_ff_model 21, test_b4_landscape 5, test_b4_probe_latch_ginv 15, test_b4_replay 23, test_b4_rng 2, test_b4_stats 4.

## Mutants (`mutants.txt`; `b4_xa_mutants.py`, a copy of the ignored `build/wip/scratch_2026_10_18/` script; hermetic whole-tree copies; a kill only with Ran N > 0 and FAILED)

**19 / 19 killed**: the relabelling removed; the contract not checked after each ingest; π from the operator seed; π's
draw consuming the operator's generator; π redrawn after the base; the operator handed the true partition; the ledger
storing the relabelled genome; a control failure recorded as DOMAIN; the exposing observation dropped; selection after
a control failure; the generator advanced after it; the replay accepting the recorded π without re-deriving it; a
non-reproduced control failure not named; `groups_moved` always zero; the address isomorphism ignoring π; the evidence
references skipped; the rejected attempts not recorded (the test was vacuous at a first-attempt seed and now finds a
seed needing ≥ 2 attempts); a control seed accepted on any arm; the residual computed against X's own view.

## Not done here

No exploration run, no gate number, no threshold or τ (2b-3), no v0.3 model revision, no board work; push / merge
unauthorised. The design is still not gate-ready (F's probe pass under the formal hypothesis, §5.3).

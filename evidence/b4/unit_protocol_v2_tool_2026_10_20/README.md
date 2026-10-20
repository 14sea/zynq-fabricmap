# B4 — the protocol revision v0.2.0, tool unit (2026-10-20): implementation and mechanics-fixture acceptance

**What this unit is.** The implementation unit the owner authorised on 2026-10-20 after the PASS of the documents unit `8361068`
("v0.2.0 tool implementation and mechanics-fixture acceptance, the whole unit delivered for review at once"): the branch
`b4-protocol-v2` continued from `8361068`, one local commit, holding the v0.2.0 tool stack, its schemas, replay, validators, tests and
mutants, the refreshed import table, the three wording precisions of the owner's review of `8361068` folded into
`docs/b4_architecture.md`, and this directory. **The model behaviour, the domain, the hypothesis, the certificate, the statistics and
the ruled numbers are unchanged.** Nothing production was run: no preflight, seed derivation, smoke, exploration or gate of any
production label; no old archive, receipt, seed record or verdict touched (the e2e below checks the two named archives byte for byte
before and after); no push, no merge, no full proof, no RTL, no board. Everything executed here is a **mechanics fixture** under the
explicit `b4-mech-*` schedules; none of it is a result.

## 1. What was implemented, by file

| file | what it now is |
|---|---|
| `b4/host/b4_landscape.py` | `TASK_VERSION = "task-v0.2"`; `SALT_TARGET = 0x54415247`; `PLANTED_RULE`; `public_parts(seed, k)`; `planted_genome(seed, storage_kind_bit)` (choice 3: storage_kind fixed to flip-flop, the other 20 bits drawn once, the base included, no redraw); `targets_from_grid`; `make_task(addresses, parts, target, holdout_target, target_source_sha256)`; `score_holdout_grid`. `TargetRefusal`. |
| `b4/host/b4_target.py` (new) | the target setup: `SETUP_FILES` (`task_setup.json` → `target_search.json` → `target_holdout.json` → `task.json`), `SETUP_STATES` (not_started / in_progress / partial / complete / invalid), the `TARGET` port role with exactly two calls, `plan`, `observe_target`, the source fields and `target_source_sha256`, `rebuild_task`, `finish` (the task document with the planted scores), `setup_findings` for the offline reconstruction. |
| `b4/host/b4_execution.py`, `b4_engine.py`, `b4_replay.py` | `PublicTask` without the seed and without `g*` (choice 2): the executing side gets the addresses, the parts, the two targets and `target_source_sha256`; `TerminalEvent` carries the task digest, not a seed; the replay binds the terminal event to the task digest. |
| `b4/host/b4_controls.py`, `b4_k10.py` | the D view and K10 take the landscape seed from the harness, never from the task. |
| `b4/host/b4_k9.py` | the two applicabilities (`applicable` all-panel, `applicable_sr_driven` conditional, reason `sr_tied_low`), the two summary records (`per_semantic` judged (b′), `per_semantic_all_panel` descriptive, `excluded_by_conditional_rule`), `JUDGED_ESTIMAND = "conditional_sr_driven"`, the recompute comparing both (choice 4; the owner's precision (a) and (b)). |
| `b4/host/b4_seeds.py` | `CONSUMED_LABELS = {b4-sim-3, b4-gate-1}` beside the retired ones; `ConsumedLabelRefusal`; `EXPLORATION_LABEL = b4-sim-4`, `GATE_LABEL = b4-gate-2`. |
| `b4/host/b4_thresholds.py` | the table of record "section 9" with `ARCHITECTURE_REVISION = "v0.2.0"` beside it (informational); K9's judged / descriptive applicabilities; the `task` and `gonogo` blocks (S = 32, B_go = 64, α_go = 0.20, conditional medians ≥ 0.50, every pair complete); the anchor labels; the PINS rows incl. §7.1. |
| `b4/host/b4_protocol.py` (new) | the protocol identity (choice 6): the payload built from the trusted inventory (every `b4/host/*.py` and `b4/schemas/*` held to `b4/IMPORT.json`), the thresholds digest without `source`, task / K9 / K10 / statistics / engine / cartographer / stack / schemas / labels / inventory / `import_table_sha256`; `architecture_revision` carried but excluded from the digest and the equality; `compare` names the differing components; `refusal_for_missing`; the CLI. |
| `b4/host/b4_gonogo.py` (new) | the go / no-go policy (choice 5): `decide`, `write_decision` (`evidence/b4/gonogo/`), `verify_gonogo_dir`, the CLI; no automatic successor. |
| `b4/host/b4_sim.py` | the per-pair setup with step-wise persistence (the plan before the first call, the first observation saved before the second, a source-drift check before the second write, the call count held to two); the `task` state in the pair index; K9 with both records in the summary; manifest 1.2.0 with the identity; report 1.1.0 with `protocol_sha256`; the `target_invalid` stop. |
| `b4/host/b4_sim_schema.py` | the setup records' validators, manifest 1.2.0, K9 1.2.0, curves / pair index / stopped / report 1.1.0, the task binding of every arm result. |
| `b4/host/b4_sim_verify.py`, `b4_gate.py`, `b4_gate_verify.py` | the identity gate at step 0 (another identity, or none, is refused **by name** and pointed to `docs/b4_archive_reverification.md`); the setup reconstruction from the persisted files; the gate judging (b′) with the all-panel record carried; `run_gate` refusing consumed and retired labels by name; the gate report 1.1.0 with the identity. |
| `b4/tests/` | every existing test module updated to the v0.2 task and the harness-held seed; new `test_b4_target.py`, `test_b4_protocol.py`, `test_b4_gonogo.py`; `b4_test_fixtures.v02_setup / v02_task`; the pin test re-implemented against the new identity contract (the document's first line held to `ARCHITECTURE_REVISION`), **not** by skipping the old version assertion. |
| `b4/IMPORT.json` | refreshed (58 entries) by `refresh_import.py` (kept here); `evidence/b4/unit_2b4a_repair_2026_10_18/import_check.py`: file digests, base digests and copied-function digests all equal, no tracked file under `b4/` without an entry. |
| `docs/b4_architecture.md` | the owner's three precisions on `8361068` folded: (a) the K9 row — `applicable_conditional = applicable_all_panel AND sr_mode_driven_at_both_endpoints`, the latch / x5FF exclusions kept, the other five semantics' conditional applicability = the old; (b) clause 6 — every pair has a record, the observation set is the old applicability's; (c) the precedence sentence — v0.2.0 items supersede older text, retained text and PINS are not two current methods. The "will fail at this commit" paragraph replaced by the implementation-status paragraph; `SALT_TARGET` in §7.1; the §9.2 formula block with the v0.2.0 labels. |
| `docs/b4_archive_reverification.md` | §5: the identity implemented; the v0.2.0 verifiers, judge and policy refuse the v0.1.16 archives by name. |
| `evidence/b4/unit_protocol_v2_design_2026_10_20/owner_review_8361068_PASS/` | the owner's review of `8361068` copied byte for byte, SHA256SUMS verified, `SOURCE.txt`. |

**One implementation decision inside choice 6, disclosed for the owner.** `import_table_sha256` in the identity payload is the digest of
the import table's entries **for the inventoried tool files only** (`b4/host`, `b4/schemas`), not of the whole table file. The table also
lists the tests; with the whole-file digest, a test-only edit would have moved the method's identity and made every earlier mechanics
archive "another version". The test `test_b4_protocol.py` holds this: a changed test entry leaves `protocol_sha256` unchanged, a changed
tool file is refused as "not its inventory". If the owner wants a test edit to count as a method change, this is a one-line revert.

## 2. The verification record (all on the final tree of this commit)

| record | file | result |
|---|---|---|
| the complete local test battery | `tests.txt` | every `b4/tests/test_*.py` module by name (the command is the file's second line): **Ran 313 tests, OK** (652 s, run concurrently with the battery and the e2e) |
| the mutant battery | `v02_mutants.txt`, driver `b4_v02_mutants.py` | **36 / 36 killed**, each line `[Ran N > 0, FAILED]` with the killing tests named; the tree copied to a temporary root per mutant, never the working tree |
| the end-to-end mechanics cases | `e2e/`, driver `e2e_fixtures_v02.py`, `e2e/summary.json` | `as_expected: true`; `production_derivation_calls: [0, 0]` |
| the import table | (command in §1) | 58 entries, all equal |

**The mutant battery's history, by the proportionality rule.** The first full run on the pre-final tree killed 34 of 36; the two survivors
were **M29** (a setup that observes a third time is not named) and **M31** (the state does not advance to `partial`). Both were real gaps in
the tests, not in the tool: a test was added for each (`test_a_setup_that_observes_more_than_twice_is_named` mocks the target observation
to call the port a third time; M31 was re-stated as the state transition and its test tightened). The targeted rerun killed both; the full
rerun recorded here, on the final tree, is 36 / 36. No mutant was counted as killed on an EDIT-MISS, a non-green baseline or `Ran 0`.

**The e2e cases** (each in a hermetic copy of the tree; each archive re-verified by a **fresh-process** verifier CLI; the comparison strips
the VOLATILE keys named at the top of the driver — times, wall-clock durations, the hermetic root's HEAD and path, the deadline record's
elapsed / checks, the quarantine repr, a stop record's `reason` that may quote the root's path — and nothing else):

| case | schedule | what happened | fresh verifier |
|---|---|---|---|
| `complete` | `b4-mech-1`, S = 2 | batch complete; gate verdict FAIL (K6 FAIL, K8 / K9 / K10 PASS, the rest not assessable at S = 2); the K9 row carries `judged_estimand`, the conditional judged record and the all-panel descriptive record; go / no-go: **no decision** (precondition S = 32 not met, exit 3) | batch 0, gate 0, gonogo 0 |
| `complete_32` | `b4-mech-5`, 32 explicit pairs | batch complete; go / no-go **no-go** at B = 64: positives 7, negatives 12, ties 13, one-sided sign p 0.916 > 0.20; conditional K9 medians all ≥ 0.50 (ff_srval 0.708, the other six 1.0) beside the all-panel descriptive ones (ff_srval 0.354, sr_kind 0.500); `formal: false`; no successor named | batch 0, gonogo 0 |
| `invalid` | S = 2, a DOMAIN at the audit of pair 1 | batch invalid, stop `domain` at stage `audit`; pair 0 complete, pair 1 partial with its task complete | 0 |
| `incomplete` | S = 2, the deadline during K9 of pair 0 | batch incomplete, stop `deadline` at `k9`; pair 1 not started | 0 |
| `target_partial` | the interrupt between the two setup observations | stop `interrupted`, role `TARGET`, stage `target_setup`; pair 0 task **partial** with `task_setup.json` + `target_search.json` kept, no `target_holdout.json`, no `task.json` | 0 |
| `target_invalid` | a DOMAIN at the first setup observation | stop `target_invalid`; pair 0 task invalid with the plan kept | 0 |
| `source_drift` | the source fields change between the two observations | stop `target_invalid` at the second write; the first observation kept, nothing after it written | 0 |

**The six tampers** of the `complete` archive, each refused (exit 1) by the fresh verifier **with the component named**: the planted genome
changed ("not what the seed, the rule and the mapping give"); a target-grid cell flipped ("rebuilt"); the task's target flipped; the protocol
identity removed ("no protocol identity"); one identity component changed (`k9: judged`); the gate's identity digest changed ("not this
tool's"). **The two named old archives** (`b4-sim-3`, `b4-gate-1`, and the gate-1 gate directory): the v0.2.0 verifiers, the judge and the
policy refuse each by name ("the archive carries no protocol identity: written by a tool before the identity existed … re-verify it with its
own tool at its recorded HEAD") and write nothing; `untouched: true` (every byte compared before and after).

**What the fixtures establish, and what they do not.** They establish that the tool stack executes the v0.2.0 contract end to end on this
tree — the setup persists step by step, the executing side never sees the seed, the records validate, the fresh-process verifiers reproduce
the derived results and refuse the named tampers and the foreign versions, the policy applies the ruled numbers. They do not establish any
property of the fabric: the mechanics labels are not production labels, their numbers are not results, and the `complete_32` no-go is the
policy exercised on a fixture, not a finding about Ω − R.

## 3. The gotcha worth keeping

The identity binds the tree to `b4/IMPORT.json`: after **any** edit under `b4/`, run `refresh_import.py` (here) and the import check, or
every v0.2.0 entry point refuses with "the tree is not its inventory". That refusal is the contract working, not a fault.

## 4. What this unit does not authorise

No production label was derived, smoked, explored or gated; `b4-sim-4` and `b4-gate-2` are reserved names in the table, nothing more. The
next unit, whatever it is, needs its own ruling.

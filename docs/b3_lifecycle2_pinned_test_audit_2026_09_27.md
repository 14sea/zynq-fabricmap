# B3 lifecycle 2 — the pre-freeze audit of every B3 test against preregistration §9

Branch `b3-lifecycle-2`, audited HEAD **`f11daf2`** (the test-report unit's follow-up 3, the owner's PASS of
2026-09-27; `git diff --quiet HEAD -- b3/tests` holds, so the bytes audited are the committed bytes). The
"tests with the §9 audit" unit of preregistration v0.3.1 §8, authorised by the owner on 2026-09-27 as a
document-only unit: this file is the only change. Host-only: no test or production code is modified, no pin
table, no manifest, no canonical proof, no ruling, no push, no board.

## Question

Preregistration §9 fixes six rules for the B3 tests before anything is frozen. B2's lifecycle 1 froze
`tests/test_b2_plan.py` at S1 with an assertion true at S0–S2 and false at S3 by construction
(`docs/b2_lifecycle2_pinned_test_audit_2026_09_16.md`, F1). Before the B3 pin table is generated and S0
exists: **does any of the fifteen files under `b3/tests/` read committed lifecycle state and assert something
a later legal transition changes, take a stage from anywhere but the production `verify`, skip on a committed
artefact, name a value §8 does not call invariant, assert B2's stage other than through the B3 manifest's
pin, or treat the frozen `tests/test_b3_online.py` as a B3 test?**

## Scope and method

**The six rules (preregistration §9, verbatim in meaning).**

| # | rule |
|---|---|
| R1 | every B3 test that reads committed lifecycle state takes the stage from the production `verify` and asserts what that stage licenses — never a literal stage, split status, calibration, session count or history length |
| R2 | every such test is driven at S0, S1, S2 and S3 and against the illegal pairings before freeze |
| R3 | `skipUnless` on a committed artefact is not a pass (zero skips in every proof) |
| R4 | the values a legal transition changes are listed in §8 first (`b3_manifest.TRANSITIONS`: S0→S1 `history, image.board_ready, prereg.frozen, prereg.sha256, status`; S1→S2 `qualification, qualified, calibration, status, history`; S2→S3 `plan, status, history`) and a test may name only what §8 calls invariant |
| R5 | B2's stage is asserted only through the B3 manifest's pin of the B2 manifest |
| R6 | the frozen `tests/test_b3_online.py` is not a B3 test |

**The six categories** every stage-related read or assertion was placed in (the owner's scope):
(a) committed-state read; (b) stage-invariant; (c) stage-aware; (d) fixture-local; (e) protocol / profile
constant; (f) refusal text, comment or documentation literal — not an assertion.

**Method.** (1) Every file grepped for reads of committed state — `manifests/`, `evidence/b3`, `evidence/b2`,
the `*_REL` path constants of `b3_manifest` / `b3_pins`, `FROZEN_INPUTS`, `skipUnless` / `skipIf` /
`SkipTest`, `git_head()` / `FIXTURE_HEAD`, and reads under the repository root `R` — and for assertions
naming a stage (`"S0"`…`"S3"`), `UNDETERMINED` / `DETERMINED`, `qualified`, `status`, `history`,
`calibration`. (2) Every hit read in context and classified. (3) The stage-driving machinery read in full:
`test_b3_plan.committed_stage` / `split_findings` / `Committed` / `StageCoverage`; `test_b3_lifecycle.World`
(the tree, `at()`, the transitions, the seams), `Base`, `LegalPath`, `StagesAndTransitions`,
`B2AndB1Authority`, `PlanStage`, `Qualification`, `CommandLine`; `test_b3_runner.Fixture` and
`FakeAuthority`; `b3_test_fixtures` in full. (4) The production side of every seam read where a test's
meaning depends on it: `b3_manifest.check_b2_authority` / `_production_b2` / `B2_REQUIRED` /
`b2_authority_block` / `stage_of` / `TRANSITIONS`; `b3_runner.SEARCH` / `QUALIFICATION` and the preflight's
profile check; `b3_plan.build_plan` (which fields depend on the rate). (5) The collected test count per module
taken from `unittest.defaultTestLoader.discover("b3/tests")` (467, the number the full suite ran at
`f11daf2`), not from a grep of `def test_` (which over-counts by three string occurrences in
`test_b3_test_report.py`).

## Inventory — the 15 files at `f11daf2`

| file | SHA-256 | tests | categories present (dominant first) |
|---|---|---|---|
| `b3/tests/b3_test_fixtures.py` | `f2c562ef52b59d8c5d7f5bf68e58b0211f230e7d6c79b68fdd9f72655cdaafd2` | 0 (fixtures) | (a) `FIXTURE_HEAD = g.git_head()` — a committed-tree read (the real HEAD) used to build the gate fixture; stage-invariant (F7, a workflow constraint); (d) synthetic rows and a fixture report |
| `b3/tests/test_b3_adjudicate.py` | `79db6d01564708ebf7187215c20cf86c84da4bf2cf41eee2aec139e8541409fd` | 62 | (d) only: modelled run logs; `R` is used solely to locate the tool for subprocess runs (864, 906); no stage word |
| `b3/tests/test_b3_carto.py` | `3702c3c72f92ef0a57ed2bbc5f6a419b3015b7dcfc9805702b069a1bba25b9e5` | 8 | (d) only; no committed read, no stage word |
| `b3/tests/test_b3_control_x.py` | `78b478d35835ff32c5522ef706e116420dacab596d2e0f76b69af9bd14cf0f76` | 6 | (d) only |
| `b3/tests/test_b3_gate.py` | `a09464c023131627faf6c1d66b2c18ac274827590368cd5ddfcadfa9dc7e57aa` | 28 | (a)+(b): the committed B2 manifest's `seeds` (786) and lifecycle 1's pilot evidence `evidence/b3/gate/*`, `evidence/b3/plan_trial_2026_09_17/*` (548–849) — frozen exclusion sources, no stage; (d) fixture reports under `FIXTURE_HEAD`; (f) path constants asserted as strings (54, 56). It never reads the committed lifecycle-2 gate report (`evidence/b3/gate_2/`) |
| `b3/tests/test_b3_lifecycle.py` | `f674891fc735fb27e29e76bdf41a3fbf0e1d9a33438e51a7cd468df7468a9084` | 75 | (d)+(c): every stage value asserted on the `World` temp tree, the stage always `w.verify()["stage"]` (production verify over the fixture) — 492, 772, 1121, 1358, 1436; (a) `FROZEN_INPUTS` bytes copied from `R` into the fixture (139); (e) `bman.STAGES` / `STATUS` / `HISTORY` / `TRANSITIONS` used as the protocol; (f) refusal texts (`"S3: the pinned plan file…"`, `"S0: a plan on an unfrozen manifest"`, …) |
| `b3/tests/test_b3_online_arm.py` | `a0e135182fcf86d3d973014f4ce360eb8f3635cb8200540680a1d0a71612dcc3` | 14 | (a)+(b): one row of the frozen `evidence/b3/sim/raw_F1.json` (63, a `FROZEN_INPUTS` file) and the two ledger schemas (75, 80); no stage |
| `b3/tests/test_b3_online_map.py` | `d37b7b26a53d926ee210861442765477b7e780a56c1143ff19efdeccaf45dcfb` | 5 | (d); the tool's own source text read once (151); no stage |
| `b3/tests/test_b3_pins.py` | `8abaad9f355864b86128dbab43c447fe7cb17fe34f53ad63b90ed4e4e6fad137` | 47 | (d) temp trees; (a) the real tree's pin surface (`generate(R)`, 189–215) and, **conditionally on the committed table's absence**, its refusal (483–485 — F3); (f) path constants |
| `b3/tests/test_b3_plan.py` | `f357eccdc6f23fc0d8590cefef9d93b82cacfe2c4acb61310846c6107f0a60af` | 32 | (a)+(c): `Committed` reads `evidence/b3/plan.json`, `prediction.json`, `manifests/b3_manifest.json` (44–47) and takes the stage from `committed_stage()` = the production `verify` (71–81); `StageCoverage` (527–664) drives it at pre/S0/S1/S2/S3 and the illegal pairings; (a)+(b) the committed B2 manifest's `seeds` (188) and lifecycle 1's pilot evidence (182–184); (f) `assertTrue(status.startswith("UNDETERMINED"))` on the tool's OWN rate-less document (381), not the committed one |
| `b3/tests/test_b3_records.py` | `431a2a0a437f57bdc35d2c37aec1dfdbd82936284326f9474b9961ec3c98ccec` | 50 | (d) only (the word "R" at 12 is the R arm) |
| `b3/tests/test_b3_runner.py` | `76b388c92943bd32e79dc4e0d3381e82dae83237102cca1df94a05ea1be165a8` | 57 | (d)+(e): `Fixture(stage)` builds a temp manifest at S1 or S3 and picks `rn.QUALIFICATION` / `rn.SEARCH` (180–216); `FakeAuthority.verify` returns `{"stage": "fixture"}` (121–127) — the runner tests never take a stage from a committed manifest; (a)+(b) the instrument's `manifests/l6_manifest.json` (609, 721 — the pinned watchdog contract, not lifecycle state) and one archived B2Q session's `summary.json` (1270, tracked evidence, read-only); (f) `profile_stage` refusal texts (1359) |
| `b3/tests/test_b3_sentinel.py` | `96a3121f40958597ad3c6643b1b7be05c01e383774d549c9dc8a454e40e36dc6` | 1 | the discovery sentinel; no read, no stage |
| `b3/tests/test_b3_session.py` | `d8b62687c1da78085163f7350743ea9a3324610dd2ea021446d1dd0903b5479b` | 26 | (a)+(b): `CommittedPrediction` reads the committed `evidence/b3/plan.json` and `prediction.json` (392–393) and asserts fields the S3 regeneration does not touch (F2); `range(8)` = the preregistered N (e); everything else (d) |
| `b3/tests/test_b3_test_report.py` | `01ce023e764e29663385d2d4f172b745017c33c1e8388c046ccfd43833f051d0` | 56 | (d) temp trees and fake runs; (a) `tr.snapshot(R)` on the real tree (585–623): the pinned surface equal to `b3_pins.generate(R)`, the seven frozen inputs at their frozen digests, the B1 carrier — stage-invariant; **conditionally on the committed table's absence**, the diagnostic verdict (602–610 — F3) |

## The six rules, one conclusion each

| # | conclusion | evidence |
|---|---|---|
| R1 | **Holds.** Exactly one place reads committed lifecycle state and needs a stage: `test_b3_plan.Committed.test_the_committed_split_is_what_the_stage_licenses`. Its stage is `committed_stage()` — `bman.verify(manifest, root=TREE["root"], seams=TREE["seams"])["stage"]`, `(None, None)` before S0 when no manifest exists — never a field read off the manifest, never a literal. `split_findings` names what the stage licenses (UNDETERMINED until S3; DETERMINED, bytes-equal, session count and record total equal to the pin at S3). No committed split status, calibration, session count or history length is a literal anywhere in the fifteen files (the only `history`/`STATUS` literals are `bman.HISTORY` / `bman.STATUS`, the protocol's own tables, applied to the fixture). | `test_b3_plan.py:71–105, 503–525` |
| R2 | **Holds for the committed-state test.** `StageCoverage` drives that test, unchanged, at pre, S0, S1, S2 (UNDETERMINED accepted; the production verify observed to have run when a manifest exists — `"b2" in w.calls`), S3 (DETERMINED, the pin's numbers), S3 under a second calibration rate (another split, held to its own pin), and against the illegal pairings: a DETERMINED plan with nothing pinned at pre/S0/S1/S2; the rate-less plan under an S3 manifest; a pinned plan whose bytes drifted; the committed path holding another document; a manifest that does not verify at S3, S2, S1, S0 (four field mutations) and a frozen input absent at S1; an absent committed plan — each a failure or error, `(testsRun, skipped) == (1, 0)` asserted every time. The second committed test is driven at pre, S0, S3. The matrix below quantifies the rest of the coverage. | `test_b3_plan.py:527–664` |
| R3 | **Does not hold until F3 is corrected (HOLD).** No `skipUnless` / `skipIf` / `SkipTest` exists in `b3/tests/` (grep: 0), and `StageCoverage.drive` asserts `len(result.skipped) == 0` for every committed-state run. But two real-tree tests guard part of their assertions with `if not (R / PIN_TABLE_REL).exists():` — a conditional on a committed artefact that does what R3 forbids `skipUnless` to do, without the runner counting a skip: the moment the pin table is generated (the next legal lifecycle state) the guarded assertions stop executing and nothing in `b3/tests/` asserts the real tree's binding any more, while the suite stays green. A coverage gap that the next legal state is certain to open is a violation now, not a future one; the owner's ruling of 2026-09-27 on `918d309` fixes this reading. Correction: F3, a pinned-edit unit before the table. | `test_b3_pins.py:483`, `test_b3_test_report.py:602` |
| R4 | **Holds.** The lifecycle test holds each transition to `bman.TRANSITIONS` (`LegalPath.test_each_transition_changed_only_what_it_licenses`, 498–506) and names a field a step does not license (855–875, eleven cases plus an unexpected key). The committed-state tests name only invariants: the plan's `fitness`, `budget_per_arm`, `pairs`, `records.*`, `prediction_sha256`, `audit_policy`, `arm_order`, `map.sha256`, `seed_derivation` — none is in any `TRANSITIONS` path, and `b3_plan.build_plan` lets only `session_split` depend on the rate (so the S3 regeneration of the committed plan changes `session_split` alone); the prediction's bytes (the S3 sidecar is the S0 prediction, `PlanStage.test_the_s3_pin…`, 540–548). | `b3_manifest.py:131–135`, `b3_plan.build_plan` |
| R5 | **Holds.** No test reads `manifests/b2_manifest.json` and asserts its stage, `qualified`, `refusal` or digest. The two reads of it (`test_b3_gate.py:786`, `test_b3_plan.py:188`) take `seeds.pairs` / `seeds.master_seed` for the exclusion — frozen values, no stage. B2's stage is asserted only as the B3 manifest's `b2_authority.required` block, the frozen requirement `{S3, true, null, aec84514…}` (`test_b3_lifecycle.py:513`), and through the production B2 verify's result compared to `B2_REQUIRED` (632–640). See the B2 authority section. | — |
| R6 | **Holds.** `tests/test_b3_online.py` is not under `b3/tests/`, is not discovered by `discover -s b3/tests` (measured: the B3 suite lists 467 tests, none from it), and `test_b3_pins` asserts `host/b3_online.py` is not in the B3 pin rule (199). It is a B2-pinned frozen file (`manifests/b2_instrument_pins.json`, glob `tests/test_b3_*.py`) and is audited as such in B2's audit, not here (Not done here). | `test_b3_pins.py:198–199` |

## Findings

### F1 — `test_b3_plan.Committed` is the one committed-state stage test, and it is stage-aware (PASS)

Category (a)+(c). `PLAN`, `PRED`, `MANIFEST` are the committed paths (44–46); `TREE` is the real root with
`seams: None` — the production verify with no seam — and the production thresholds (47). `committed_stage()`
(71–81) returns `(None, None)` when no manifest exists (the pre-S0 tree, today's) and otherwise the stage the
production `bman.verify` RETURNS; a manifest that does not verify raises — "an error of the test that
asked, not a skip". `split_findings` (83–105) is B2 v0.3's committed-plan stage rule verbatim, held to
that stage. `StageCoverage` re-points the four module globals at the lifecycle `World` and runs the real
`Committed` case object (not a copy) through `unittest.TestResult`, asserting `(testsRun, skipped) ==
(1, 0)`. Today, with no manifest, the committed `evidence/b3/plan.json` is the rate-less document
(`session_split.status` starts with `UNDETERMINED`) and the test passes for that reason and no other; after
S0 it will take the stage from the full production verify (the seven frozen inputs, the B2 S3 verify with
the re-adjudicator, the B1 chain, the pins, the image, …) on every run — the cost §9 accepts.

Minimal counter-example the rule would catch: the B2 lifecycle-1 defect — a DETERMINED committed plan under
an S0–S2 manifest, or the rate-less plan under S3 — both driven and refused (601–614).

### F2 — `test_b3_session.CommittedPrediction` reads the committed plan and prediction — stage-invariant (PASS, one note)

Category (a)+(b). `setUpClass` reads `evidence/b3/plan.json` and `evidence/b3/prediction.json` (392–393)
and asserts: the prediction regenerates byte for byte from the plan's `fitness`, `budget_per_arm`, the
seeds and `map.sha256`; the session reproduces it record for record; `fitness_sequence_length` and
`fitness_sequence_sha256`; the pair index `range(8)` (the last line of 397–421).

Why it is stage-invariant: the S3 transition regenerates the committed plan through `pl.build_plan(rate,
gate)`, in which only `session_split` depends on the rate (R4); the fields this test reads are not in it. The
prediction's bytes are the S0 prediction throughout (`m["plan"]["prediction_sha256"] ==
m["prediction"]["sha256"]`, `test_b3_lifecycle.py:548`). `8` is N of preregistration v0.3.1 §2/§3 — a
preregistered constant (e), not a stage.

Note (P3, no change required): this test is not itself driven at S3 by a `StageCoverage`; its invariance is
inherited from `build_plan` and is exercised for the plan's arithmetic fields by
`StageCoverage.test_the_other_committed_test_passes_at_every_stage_too` (pre, S0, S3). B2's audit treated
the equivalent reads (its F3) the same way. Should a later plan-tool change make any of these fields
rate-dependent, `test_b3_plan.StageCoverage` would fail first.

### F3 — two real-tree tests narrow their assertions on a committed artefact's absence (P2, R3 — the audit's HOLD; correct before the pin table)

Category (a), R3 in spirit.

- `test_b3_pins.py:483–485` (`TheTreeAgainstTheTable.test_the_default_root_is_the_repository`):
  `if not (R / bp.PIN_TABLE_REL).exists():` → two refusals asserted ("…is absent"). The unconditional part
  (`REPO_ROOT == R`, discovery / generate equal with the explicit root, the fixture verifies) always runs.
- `test_b3_test_report.py:602–610` (`TheRealTree.test_a_snapshot_of_this_tree_has_the_shape_the_verdict_reads_and_is_not_yet_a_proof`):
  `if not (R / bp.PIN_TABLE_REL).exists():` → `mode == "unbound_snapshot"`, `pins_verified` False, the
  verdict over the real snapshot not a proof and naming the table. The unconditional part (the snapshot's
  shape, the pinned surface equal to `generate(R)`, the seven frozen inputs at their frozen digests, the
  B1 carrier named and digested) always runs.

Minimal counter-example: generate the pin table (the next step of §8). Both guards become false, the
guarded assertions never execute again, and nothing in `b3/tests/` then asserts what the real tree's binding
IS (`table_self_bound` before S0, `manifest_bound` and `pins_verified` after) — the tests keep passing while
saying less. That is the shape R3 forbids ("a skip on a committed artefact is not a pass"), achieved with
an `if` instead of `skipUnless`. Today nothing is skipped and no false verdict is produced, and the tool's
own binding modes are exercised unconditionally on temporary trees (`test_b3_test_report.TheBinding`,
446–584) — but the gap is not hypothetical: generating the pin table is the very next step of §8, and the
audit's question is what holds BEFORE anything is frozen, for the states the lifecycle will legally enter.
A pattern that silently removes the only real-tree binding assertions at the first legal transition is a
load-bearing R3 violation (P2), and the audit's verdict is HOLD until it is corrected (the owner's ruling on
`918d309`, 2026-09-27).

Correction (a later pinned-edit unit, **before** the table is generated — after it the edit would return
the line to the pinned edits and the table would be regenerated): replace each guard with a two-branch
assertion, each branch asserting what the committed state licenses — table absent: `unbound_snapshot`,
never a proof, the table named among the absent artifacts; table present and manifest absent:
`table_self_bound`, the diagnostic verified against the table's own bytes, never `pins_verified`; table and
manifest present: `manifest_bound` with `pins_verified` equal to what the production `b3_pins.verify(manifest,
root=R)` gives (the stage of the manifest itself is not the point of these tests and is not asserted). Its
test: each branch reached on a temporary tree (already the case for the modes in `TheBinding`), and a
mutant that drops one branch failing. Two files, no production change.

### F4 — committed reads that are frozen inputs or pilot evidence — stage-invariant (PASS)

| test | what it reads | why it is safe |
|---|---|---|
| `test_b3_gate.py:786–789`, `test_b3_plan.py:188` | `manifests/b2_manifest.json` → `seeds.pairs`, `seeds.master_seed` | B2 closed at S3; its manifest is a `FROZEN_INPUTS` entry pinned by digest `aec84514…`; the seeds are exclusion sources, no B2 stage is read (R5) |
| `test_b3_gate.py:548–633, 791–849`, `test_b3_plan.py:49, 182–184, 477–482` | lifecycle 1's `evidence/b3/gate/*`, `evidence/b3/plan_trial_2026_09_17/*` | pilot / design evidence, never overwritten (architecture §6), an exclusion source by name |
| `test_b3_online_arm.py:63, 75, 80` | `evidence/b3/sim/raw_F1.json`, the two ledger schemas | `FROZEN_INPUTS` (`sim/raw_F1.json`, `schemas/specimen_ledger.schema.json`) and the B3 schema under the pin rule |
| `test_b3_lifecycle.py:139` | the seven `FROZEN_INPUTS` bytes copied from `R` into the fixture | the fixture's authority is built from the frozen bytes; digests asserted equal to `bman.FROZEN_INPUTS` (620–630) |
| `test_b3_test_report.py:585–610` | `tr.snapshot(R)`: the pinned surface, the frozen inputs' digests, `builds/b1/b1.bit` | asserted against `b3_pins.generate(R)` and `bman.FROZEN_INPUTS` — invariant by construction within one lifecycle (the table and manifest are regenerated together before S0) |
| `test_b3_runner.py:609, 721` | the instrument's `manifests/l6_manifest.json` | the B1 instrument's pinned watchdog contract (B1 lineage), not B3 lifecycle state |
| `test_b3_runner.py:1270` | `evidence/b2/b2q_17A6_2026-09-16-01/summary.json` | archived B2Q evidence, tracked, read-only, a production-shape oracle for the transport ledger |

### F5 — fixture-local stage assertions — not committed state (PASS)

`test_b3_lifecycle.py`: 130 stage-word hits, all on the `World` temp tree. The `World` carries one tree
through pre → S0 → S1 → S2 → S3 with the production command line (`init`, `freeze`, `qualify`, `plan`,
159–172), snapshots each stage, and `at(stage)` restores the tree at the same root (129–135). Every
stage read is `w.verify()["stage"]` — the production verify over the fixture — compared with the stage the
fixture was just driven to (492, 772, 1121, 1358, 1436); `mutated(stage, …)` and `both(…)` (306–309,
694–702) select a snapshot to tamper with, they do not assert a stage; the remaining hits are `bman.STAGES`
/ `STATUS` / `HISTORY` / `TRANSITIONS` (the protocol tables) and refusal texts. `test_b3_runner.py`: 33
hits, all `Fixture("S1")` / `Fixture("S3")` (a temp manifest built for one profile, 180–216) or the
profile constants (F6); `FakeAuthority.verify` returns `{"stage": "fixture"}`, so no runner test derives a
stage from any manifest. `test_b3_plan.py`: 26 hits, all inside `StageCoverage` selecting `w.at(stage)` or
naming the expected refusal.

### F6 — the runner's `SEARCH` / `QUALIFICATION` profile constants are the runner's contract, not committed-stage constants (PASS, one production observation)

`b3_runner.py:128–129`: `SEARCH = {…, "stage": "S3", …}`, `QUALIFICATION = {…, "stage": "S1", …}`. They
name the manifest stage each ruling profile is FOR (B3Q runs against the S1 manifest, a B3 session against
the S3 one); they appear in the session plan (609, `"stage": profile["stage"]`), in the finalisation record
(`profile_stage`, 1363, 1430), and in the log's `l6.inputs.stage`. The tests hold them as the runner's
contract: `test_the_identity_and_inputs_are_held` names a log whose `inputs.stage` is `S1` under the SEARCH
plan (1138–1139); the finalisation record's `profile_stage` is held to the session's (1359); the plan's
`inputs.stage` is asserted equal to the profile's (673, 707). None of these is a committed stage, none is
read off a committed manifest, and none would change at a legal transition — they are (e), and reading them
as R1 literals would be a misclassification.

Observation for the owner (production code, outside this unit's scope, no §9 test finding): the preflight
decides the profile's fit by reading the manifest's `qualified` / `qualification` / `plan` fields
(1134–1143) before `authority.verify(manifest, …)` (1145), and does not compare the verify's returned
`stage` to `profile["stage"]`. The illegal pairings are still refused — `stage_of` inside the production
verify names every inconsistent field set — so a manifest cannot pass the field checks with a stage the
verify would not report. Comparing the returned stage explicitly would make the profile's stage
load-bearing in one place; a candidate for a later runner unit, not a defect the tests hide.

### F7 — the gate fixture is bound to the real HEAD's architecture bytes — a workflow constraint, not a stage constant (PASS)

`b3_test_fixtures.FIXTURE_HEAD = g.git_head()` (22): the gate fixture's seeds are drawn under `b3-gate-2`
from the REAL HEAD, and `b3_gate.validate_report` requires that commit to exist and to carry the architecture
bytes. Consequence (the module docstring says it): **these tests need `docs/b3_architecture.md` unchanged from
HEAD** — an uncommitted edit of the architecture makes the fixture invalid and the lifecycle-world tests
error. This is B2's F2 in a different coat: the design refusing to validate a report against bytes the tree
has moved away from. It constrains the order of work (commit the architecture before running the suite), not
the tests' stage logic.

### F8 — literals that are not assertions (category f)

Refusal texts asserted with `assertIn` (`"S3: the pinned plan file is absent or changed"`, `"S0: a plan on an
unfrozen manifest"`, `"S1: qualified / calibration without a qualification record"`, …) name the production
verify's own words for an illegal pairing the test constructed; the path constants asserted as strings
(`test_b3_gate.py:54, 56`, `test_b3_test_report.py:1143`); docstrings and comments. None reads or asserts
committed state.

## StageCoverage — the matrix

"stage from verify" = the stage the test relies on is the production `b3_manifest.verify`'s return (or
`check_transition` / `stage_of`, its constituents); "pre" = the tree before `init` (no manifest).

### A. The committed-plan stage rule — `test_b3_plan.StageCoverage` over `Committed`

| class / method | state read | stage from verify | pre | S0 | S1 | S2 | S3 | illegal pairings driven | expected |
|---|---|---|---|---|---|---|---|---|---|
| `Committed.test_the_committed_split_is_what_the_stage_licenses` (driven by `StageCoverage.test_it_passes_before_s0_and_at_s0_s1_s2…`, `…at_s3_with_the_pinned_plan`, `…at_s3_for_another_split…`) | `evidence/b3/plan.json`, `prediction.json`, `manifests/b3_manifest.json` — re-pointed to the `World` | yes (`committed_stage`; `"b2" in w.calls` asserted when a manifest exists) | ✓ | ✓ | ✓ | ✓ | ✓ (+ a second calibration rate → another split) | — | pass; UNDETERMINED before S3, DETERMINED = the pin at S3 |
| the same, `…a_determined_plan_with_nothing_pinned_is_refused` | the tool's rate-full plan written to the canonical path | yes | ✓ | ✓ | ✓ | ✓ | — | DETERMINED under pre/S0/S1/S2 | named failure ("must be UNDETERMINED, not 'DETERMINED'") |
| the same, `…the_rate_less_plan_against_an_s3_manifest_is_refused` | the S2 snapshot's plan copied over the S3 one | yes (the verify itself refuses first) | — | — | — | — | ✓ | UNDETERMINED under S3 | named ("S3: the pinned plan file is absent or changed") |
| the same, `…a_pinned_plan_whose_bytes_drifted_is_refused` | the pinned plan edited; the committed path holding another document | yes | — | — | — | — | ✓✓ | drifted bytes; another document | named (verify; "the committed plan hashes to") |
| the same, `…a_manifest_that_does_not_verify_is_an_error_never_a_skip_or_a_pass` | the manifest mutated on disk | yes | — | ✓ | ✓✓ | ✓ | ✓ | S3 with S2's status; S2 carrying a plan; S1 carrying a calibration; S0 carrying a plan; S1 with a frozen input absent | error, never a skip (5 cases) |
| the same, `…an_absent_committed_plan_fails_it_is_not_skipped` | the plan path absent | yes | — | ✓ | — | — | — | absent artefact | failure/error, `skipped == 0` |
| `Committed.test_record_arithmetic_and_the_prediction_pin` (driven by `…the_other_committed_test_passes_at_every_stage_too`) | the same three files | not needed (invariant fields) | ✓ | ✓ | — | — | ✓ | — | pass |
| `StageCoverage.test_each_s3_guard_of_the_rule_is_load_bearing` | `split_findings` unit | n/a (stage passed explicitly) | None | ✓ | ✓ | ✓ | ✓ | the five S3 guards one at a time; the rate-full plan at None/S0/S1/S2 | each named |

Every drive asserts `(result.testsRun, len(result.skipped)) == (1, 0)`.

### B. The lifecycle itself — `test_b3_lifecycle.World` on the temp tree

| class / method(s) | state read | stage from verify | pre | S0 | S1 | S2 | S3 | illegal pairings driven | expected |
|---|---|---|---|---|---|---|---|---|---|
| `LegalPath.test_every_stage_verifies_and_reports_itself` | the World at each snapshot | yes (`res["stage"]`, `qualified == (stage >= "S2")`, `refusal None`, `manifest_sha256`, `status == bman.STATUS[stage]`, `calls[:3] == [b2, b1, pins]`) | — | ✓ | ✓ | ✓ | ✓ | — | pass |
| `LegalPath.test_each_transition_changed_only_what_it_licenses` | the four snapshots pairwise | `check_transition` | — | ✓→ | ✓→ | ✓→ | ✓ | — | pass; changed paths ⊆ `TRANSITIONS`; `qualification_plan` constant |
| `LegalPath.test_s0_pins…`, `…the_s2_calibration…`, `…the_s3_pin…` | the S0 / S2 / S3 manifest | the snapshot's own stage (fixture-local content checks) | — | ✓ | — | ✓ | ✓ | — | pass |
| `StagesAndTransitions.test_every_pairing_but_the_three_steps_is_refused` | all 4×4 snapshot pairs | `check_transition` | — | ✓ | ✓ | ✓ | ✓ | 13 (every pair but S0→S1, S1→S2, S2→S3) | named refusal |
| `…test_a_field_the_step_does_not_license_is_named` | a licensed step with one extra change | `check_transition` | — | ✓ | ✓ | ✓ | ✓ | 11 unlicensed fields + 1 unexpected key | named |
| `…test_every_illegal_pairing_of_stage_fields_is_refused_by_verify` | a snapshot with one field of another stage | yes | — | ✓ | ✓ | ✓ | ✓ | 17 | named ("S0: …", "S1: …", "S2: …") |
| `…test_a_status_or_a_history_of_another_stage_is_refused` | status / history swapped | yes | — | ✓ | ✓ | ✓ | ✓ | 4×3 statuses + 4×3 histories + 4 foreign statuses + 3 history-entry drifts | named |
| `…test_a_command_from_the_wrong_stage_is_refused_and_keeps_the_bytes` (912) and the CAS / journal / lock tests (927–1247) | the command line at each stage | yes | ✓ (`init`) | ✓ | ✓ | ✓ | ✓ | wrong-stage commands; racing publishers | refusal, bytes kept |
| `FrozenInputs`, `PinsImageAndDocuments.both()` | S1 verify and pre `init` | yes | ✓ | — | ✓ | — | — | each frozen input / artifact absent or drifted | named; `init` writes nothing |
| `B2AndB1Authority` (4) | the S1 World | yes | — | — | ✓ | — | — | B2 result fields wrong (5) / absent / None; the `b2_authority` block drifted; declared refusals vs defects; `b2=None` and `b1=None` production | named refusal / INTERNAL ERROR / production run observed |
| `Qualification` (13) | S1 → S2 through `qualify` | yes (`w.verify()["stage"] == "S2"` after; `"S1"` after a refused qualify) | — | — | ✓ | ✓ | — | twelve evidence files absent / drifted; forged PASS; rate not the evidence's; wrong S1 binding | named; the manifest's bytes kept on refusal |
| `PlanStage` (5) | S2 → S3 through `plan` | yes | — | — | — | ✓ | ✓ | drifted pin, absent plan, drifted sidecar, wrong summary, a plan from another rate, INFEASIBLE split | named |
| `InitNoClobber`, `Publishing`, `CommandLine` | pre / S0; the CLI's options | yes | ✓ | ✓ | — | — | — | overwrite attempts; skip flags | refusal; no flag exists |

### C. The runner's profiles — `test_b3_runner.Fixture`

| class / method(s) | state read | stage from verify | S1 (B3Q) | S3 (B3) | pairings driven | expected |
|---|---|---|---|---|---|---|
| every `ZeroContact` / preflight / session test over `Fixture(stage)` | a temp manifest at S1 or S3 with its pinned documents; `FakeAuthority` | no — the fixture's authority returns `{"stage": "fixture"}`; the stage is the profile's contract (F6) | ✓ (9 fixtures) | ✓ (12 fixtures) | the SEARCH profile against an unqualified manifest and the QUALIFICATION profile against a qualified one are refused by the production preflight's field checks (1134–1143); a log whose `inputs.stage` disagrees with the plan (1138); `profile_stage` of another session in the finalisation record (1359) | named refusal / finding |

### D. Committed reads without a stage

| test | driven at | note |
|---|---|---|
| `test_b3_session.CommittedPrediction` (2) | the current tree only (pre-S0) | stage-invariant fields (F2) |
| `test_b3_pins.TheTreeAgainstTheTable.test_the_default_root_is_the_repository`, `test_b3_test_report.TheRealTree.test_a_snapshot…` | the current tree only; guarded assertions on the table's absence | F3 — to be made two-branch before the table |
| `test_b3_gate.SeedsAndPins`, `test_b3_plan.GateAndSeeds` | the current tree | frozen exclusion sources (F4) |

## The B2 authority boundary

| question | determination | evidence |
|---|---|---|
| Does the production `b2=None` path really execute the B2 verify? | **Yes.** `check_b2_authority` runs `seams.b2 or _production_b2`; `_production_b2` loads `manifests/b2_manifest.json` from the given root and calls `b2_manifest.verify(m, readjudicate=b2_runner.readjudicator(m, inst.DEFAULT_ROOT), root=root, b1_root=root)`. `test_none_is_the_production_b2_and_b1_never_a_skip_and_nothing_is_unpacked` (682–691) calls `w.verify(b2=None)` on the temp World — where B2's own pinned files are not present — and requires the refusal to come back under the B3 name, `"b2" not in w.calls` (the injected seam did not run), and the tree unchanged (nothing unpacked). On the real tree, `test_b3_plan.committed_stage()` uses `seams=None` — the production path — once a manifest exists. | `b3_manifest.py:251–256, 269–290`; `test_b3_lifecycle.py:682–691`; `test_b3_plan.py:47, 71–81` |
| Is the B2 result constrained by the B3 manifest's `b2_authority` block and content pins? | **Yes, twice.** (1) The manifest's `b2_authority` block must equal `b2_authority_block()` — the frozen requirement `{S3, true, null, aec84514…}` — before the verify is consulted (`"b2_authority block is not the frozen requirement"`, 640). (2) The B2 verify's result must equal `B2_REQUIRED` field by field and type by type (`"the B2 verify gives stage = 'S2', B3 requires…"`, 632–638, five wrong fields, an absent field, a non-dict result). (3) Independently, `manifests/b2_manifest.json` and `manifests/b2_instrument_pins.json` are `FROZEN_INPUTS`, checked by existence and digest before the B2 verify runs (`FrozenInputs`, 590–630; the `FixedPrefixOrder` tests hold that the frozen-input refusal comes first, 554–583). | `b3_manifest.py:90, 269–293`; `test_b3_lifecycle.py:508–513, 554–640` |
| Is the injected seam used only for temporary fixtures and fault injection? | **Yes.** `World.seams()` returns a `b2` that records the call and returns `dict(bman.B2_REQUIRED)` — a stand-in for the production result on a temp tree that cannot verify B2 (183–201, `b2` at 192); `b2=lambda …` variants inject wrong fields, a declared refusal, a defect (632–660). `test_b3_plan.TREE["seams"]` is `None` on the real tree and is re-pointed to `w.seams()` only by `StageCoverage`, which runs over the World. `CommandLine.test_the_seams_are_python_only_and_default_to_production` (1564–1568): `Seams()` is all-`None` and has exactly four members; the CLI has no seam flag (`--help` options exactly `--evidence-dir --help --manifest --plan --prereg-sha256`, and `--skip-b2` / `--allow-missing` / `--no-verify` / `--force` are rejected). No test replaces the seam to make a COMMITTED read pass. | `test_b3_lifecycle.py:183–201, 631–691, 1551–1568`; `test_b3_plan.py:47, 543–545` |
| Does any test read the committed B2 manifest and assert its stage itself? | **No.** The two reads (`test_b3_gate.py:786`, `test_b3_plan.py:188`) take the seed values for the exclusion set; neither touches `stage`, `qualified`, `refusal` or the digest. The only stage assertions involving B2 are the B3 manifest's `b2_authority.required` block (513) and the result-vs-`B2_REQUIRED` comparison inside the production check (632–638). | — |

The seams' existence is therefore not a finding: they stand in for authorities that cannot be verified
inside a temporary tree and they inject faults; they never substitute for the committed-state authority
and never let a test bypass a B3 pin assertion.

## Verdict — HOLD, pending F3's correction

R1, R2, R4, R5 and R6 hold in the fifteen files at `f11daf2`: the one committed-state stage test (F1) takes
its stage from the production verify and is driven at every stage and against the illegal pairings; every
other committed read is stage-invariant (F2, F4) or fixture-local (F5); the profile constants are the
runner's contract (F6); B2's stage is reached only through the B3 manifest's pin and the production B2
verify (R5). R3 does not: F3's two `if not table.exists()` guards on real-tree tests are a skip on a
committed artefact in everything but name, and the next legal lifecycle state — the pin table generated —
is certain to make the only real-tree binding assertions disappear while the suite stays green. That is a
load-bearing R3 violation (P2) and holds the verdict. The audit closes as PASS by a follow-up once F3's
correction (a separately authorised pinned-edit unit, two test files, no production code) is committed and
both branches are verified — the absent-table branch on this tree, the present-table branches on a
temporary tree with the table and with the table and manifest — and re-audited here.

## What else must hold before S0 (for the owner's review)

1. **F3's correction as a pinned-edit unit before the table.** `test_b3_pins.py:483–485` and
   `test_b3_test_report.py:602–610`: two-branch assertions (absent → `unbound_snapshot` and the refusal;
   present → the binding the production `b3_pins` / `b3_test_report.pin_state` give for THIS tree), each
   branch mutant-tested. Separately authorised; two test files, no production code.
2. **The ordering constraint of F7 / B2's F2.** Every pinned edit — F3's correction and anything the owner's
   review adds — before the table; the table generated once; `b3_manifest.py init`; only then a clean-tree
   proof. `docs/b3_architecture.md` must be committed (equal to HEAD) whenever the suite runs, or the gate
   fixture is invalid and the lifecycle world errors.
3. **After S0 the committed-state test costs the full production verify per run.**
   `test_b3_plan.committed_stage()` will run the B2 S3 verify with the re-adjudicator and the B1 chain on the
   real tree (about two minutes today) for each of the two `Committed` tests. This is §9's design; the suite's
   wall time and the test-report tool's three runs should be budgeted for it.
4. **The runner's profile stage (F6 observation).** Whether the preflight should compare the production
   verify's returned stage to `profile["stage"]` is a runner question for the owner, not a §9 test finding.
5. **The committed plan stays rate-less until S3.** `evidence/b3/plan.json` at `f11daf2` is the rate-less
   document (F1 passes today for that reason). The S3 `plan` command regenerates it from the calibration;
   nothing may pin a rate-full plan earlier (`test_init_requires_the_committed_plan_to_be_the_rate_less_one`,
   801–808, holds `init` to this).

## Not done here

- No test or production code is modified; F3's correction is the NEXT unit — a separately authorised
  pinned-edit unit over `b3/tests/test_b3_pins.py` and `b3/tests/test_b3_test_report.py` only, before the pin
  table — after which a follow-up to this document re-audits the two tests and closes the verdict as PASS.
- `tests/test_b3_online.py` is not audited here: it is a B2-pinned frozen file (glob `tests/test_b3_*.py` in
  `manifests/b2_instrument_pins.json`), a historical host reference, not discovered by `-s b3/tests`, and
  §9 R6 says it is not a B3 test; B2's audit of 2026-09-16 covers it as one of B2's nineteen.
- No pin table, no manifest, no canonical clean-tree proof (`evidence/b3/tests` does not exist), no image, no
  ruling, no push, no board. The next unit is the owner's review of this audit; after it, F3's correction
  and this audit's closing follow-up; only then, in the §8 order, the image sources and build evidence, the
  B3Q documents, then the pin table once, then S0.

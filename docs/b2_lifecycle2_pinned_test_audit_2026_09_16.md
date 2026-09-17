# Lifecycle 2 — the pre-freeze audit of every pinned test for stage-constant assumptions

Branch `b2-lifecycle-2`, forked from `main` at `4800c15` (the owner's containment A).
Step 2 and step 3 of the repair in `docs/b2_s3_frozen_test_decision_2026_09_16.md`.
Host-only: no manifest, pin table, preregistration, ruling, push or board action.

## Question

The current lifecycle froze `tests/test_b2_plan.py` at S1 with an assertion that is true at
S0–S2 and false at S3 by construction. Before the new lifecycle freezes anything: **which other
pinned tests read the committed tree and assert something that a later legal stage transition
changes?**

## Scope and method

The 19 test files in `manifests/b2_instrument_pins.json` (of 71 pinned files):

`test_b2_adjudicate, test_b2_build_evidence, test_b2_e2e, test_b2_gate, test_b2_hostapp,
test_b2_landscape, test_b2_leakage, test_b2_lifecycle, test_b2_maps, test_b2_pins, test_b2_plan,
test_b2_records, test_b2_runner, test_b2_search, test_b2_session, test_b2_test_report,
test_b2_twin, test_b2_wire, test_b3_online`.

1. A scan of every file for reads of committed state (`manifests/b2_manifest.json`,
   `evidence/b2/plan.json`, `evidence/b2/prediction.json`, the pin table, `skipUnless` on
   committed artefacts) and for assertions naming a stage, `UNDETERMINED`/`DETERMINED`,
   `qualified`, `plan`, `calibration`, `status` or `history`.
2. Each hit read in context to decide whether the asserted value is **stage-constant**
   (changes at a legal transition) or **stage-invariant** (the same from S0 to S3 within one
   lifecycle) or **fixture-local** (asserted on a manifest the test builds itself).

## Findings

### F1 — `tests/test_b2_plan.py:55` (the known one) — stage-constant, corrected on this branch

`Committed.test_record_count_and_split_arithmetic` asserted the committed plan's
`session_split.status` starts with `UNDETERMINED`. Preregistration §2 says the split is
UNDETERMINED until S2 and the S3 plan is regenerated with the calibration rate and pinned, so
the assertion contradicts S3 by construction.

Correction (this branch): one rule, `split_findings(plan, plan_bytes, manifest)`, used by the
committed test and by a new stage guard —

- manifest absent or `manifest.plan is None` → the committed split must be UNDETERMINED;
- a plan pinned → DETERMINED, the plan file's bytes hash to `manifest.plan.sha256`, and its
  session count and `total_records` equal the pin.

New `StageCoverage` class (7 tests) drives the real committed test, unchanged, against
`test_b2_runner.Fixture` manifests at S0, S1, S2 (with the tool's own UNDETERMINED plan,
`b2_plan.build_plan(None)`), at S3 (the fixture's pinned plan), at S3 for four synthetic rates
giving four different splits, and with no manifest at all — all must pass; and against three
illegal pairings that must each fail for its own named reason: the old constant's pairing
(UNDETERMINED plan under an S3 manifest), a DETERMINED plan with nothing pinned, and a pinned
plan whose bytes drifted.

Result with the live pin check stubbed (diagnostic, see F2): **15 tests, OK**
(`evidence/b2/lifecycle2_prep_2026_09_16/run_plan_tests_pins_stubbed.log`). The same module
run for real on this branch: `FAILED (failures=1, errors=9)`, every one a
`PinRefusal: tests/test_b2_plan.py: hash differs` (`real_run_before_repin.txt`) — F2.

### F2 — every lifecycle fixture inherits the LIVE pin table — a workflow constraint, not a defect

`test_b2_runner.Fixture`, `test_b2_lifecycle`, `test_b2_e2e` and the new `StageCoverage` reach
S2/S3 by calling the production `b2_manifest.qualify` / `pin_plan`, whose `verify` re-checks
the committed `manifests/b2_instrument_pins.json` against the tree. Consequence: **on a line
in preparation — any pinned file edited, the table not yet regenerated — every S2/S3 fixture
errors**, which is the 32-error fan-out of `test_report_2026-09-16T095911Z.json`.

This is the design working (a changed decision surface must not verify). The constraint it
imposes on lifecycle 2 is ordering:

1. make **every** pinned-file edit first (this audit's corrections, and anything the owner's
   review of it adds);
2. regenerate the pin table **once**, immediately before the new S0 (`b2_pins.py --generate`);
3. `b2_manifest.py init` → the new S0 manifest pins the new table;
4. only then can the whole suite be green, and only then is a clean-tree proof meaningful.

Until step 2 the branch's suite is red by design; the diagnostic harness in
`evidence/b2/lifecycle2_prep_2026_09_16/` (pin check stubbed) is how a single edited test is
checked in the meantime. It must never be used for a proof.

### F3 — committed reads that are stage-invariant — no change needed

| test | what it reads | why it is safe |
|---|---|---|
| `test_b2_session.py:211`, `test_b2_twin.py:206` | `evidence/b2/prediction.json` deltas | the prediction's bytes are the same S0→S3: `plan_findings` at S3 requires `prediction_sha256` to equal both the sidecar and the manifest's reference, so S3 cannot change them (and did not: `a611b8e0…` before and after) |
| `test_b2_pins.py:170-172` | the committed table and `manifest.instrument_pins.sha256` | equal by construction within one lifecycle; regenerated together before S0 |
| `test_b2_test_report.py:242-248` | the table's file list | a snapshot-coverage check, not a value assertion |
| `test_b2_plan.py` (the other seven `Committed` tests) | plan seeds, gate provenance, prediction digest, map digest | all derived from frozen inputs that no transition changes; all pass against the S3 plan |
| `test_b2_maps.py:29`, `test_b2_leakage.py:62` | the committed B1 self-map | B1 lineage, frozen before B2 |

### F4 — the committed-manifest test in `test_b2_runner.py` is already stage-aware

`test_the_committed_manifest_is_a_legal_stage_and_is_not_permission` (line 315) takes the
stage from production `verify`, checks the manifest's own fields against that stage
(`stage_findings`), and is driven at S0–S3 by its own `StageCoverage` (line 558). It replaced a
hard-coded-S0 test after the owner's review of 2026-09-12 — the same class of defect as F1,
caught then for the manifest but not for the plan. `test_b2_plan.StageCoverage` is modelled on it.

### F5 — fixture-local stage assertions — not committed state

`test_b2_lifecycle.py` (11 hits), `test_b2_e2e.py` (4), `test_b2_runner.py:290-313` (the S0
fixture contract): every stage value is asserted on a manifest the test itself builds in a temp
directory. They cannot go stale with the tree.

## What else must hold before the new S0 (for the owner's review)

- `evidence/b2/plan.json` must be regenerated **without** `--rate-per-hour` at the start of
  lifecycle 2, so the committed pre-S3 plan is UNDETERMINED again (the corrected test requires it
  while no plan is pinned). Prediction bytes will be unchanged.
- The new preregistration version should state the stage rule for the committed plan
  explicitly (UNDETERMINED until the S3 pin; DETERMINED and bytes-equal to the pin after), so
  the test and the document say the same thing.
- The existing B2Q PASS (`evidence/b2/b2q_17A6_2026-09-14-01`) and its rate `2976.98/h` are
  historical evidence for the old S1 manifest and must not be used to qualify the new identity
  (the owner's decision, §"Correct repair after containment").

## Not done here

No pin table regeneration, no manifest, no preregistration edit, no push. The next unit is the
owner's review of this audit and of the corrected test; after that, the ordered steps of F2.

# B3 lifecycle 2 — the §9 delta re-audit: the nine test files added since the audit closed

Branch `b3-lifecycle-2`, audited HEAD **`64bca1e`** (the stage-6 follow-up, the owner's PASS of 2026-10-13; `git diff
--quiet HEAD -- b3/tests` holds, so the bytes audited are the committed bytes). A document-only unit authorised by
the owner on 2026-10-13 (the §8 order: "the tests with the §9 audit" is re-closed over the files the image stages
added before the pin table is generated). This file is the only change. Host-only: no test or production code is
modified, no evidence, no pin table, no manifest, no canonical proof, no ruling, no push, no board.

**What this document is.** `docs/b3_lifecycle2_pinned_test_audit_2026_09_27.md` audited the fifteen files under
`b3/tests/` at `f11daf2` / `ef25681` against preregistration §9 and closed PASS. Since `ef25681` the image stages
1–6 added **nine** test files (324 tests) and changed none of the fifteen. This document audits the nine by the same
question, rules, categories and method, and leaves the 2026-09-27 verdict as it stands: its PASS covers the fifteen at
`ef25681`, this document's covers the nine at `64bca1e`.

## Question

Preregistration §9 fixes six rules for the B3 tests before anything is frozen. **Does any of the nine files added to
`b3/tests/` since `ef25681` read committed lifecycle state and assert something a later legal transition changes, take
a stage from anywhere but the production `verify`, skip on a committed artefact, name a value §8 does not call
invariant, assert B2's stage other than through the B3 manifest's pin, or treat the frozen `tests/test_b3_online.py`
as a B3 test?**

## Scope and method

The six rules R1–R6 and the six categories (a)–(f) are the 2026-09-27 audit's, unchanged: (a) committed-state read;
(b) stage-invariant; (c) stage-aware; (d) fixture-local; (e) protocol / profile constant; (f) refusal text, comment or
documentation literal — not an assertion. **One correction the owner made for this delta:** an actual assertion on a
committed artefact is placed in (a) with its (b)/(c) verdict — never in (f), whatever its value looks like.

**The owner's two criteria for this delta (2026-10-13).** (i) A read of the committed plan / prediction is followed to
the fields actually used and to the production derivation; if a legal transition cannot change them the F2 treatment
of the 2026-09-27 audit applies and no new stage matrix is required; only a read of a field a transition changes
requires stage-aware verification. (ii) An assertion such as `image_ready is False` is not a defect for being a
literal: it is judged with the whole block it sits in (`FINDINGS`, version, bounds, blocking) — is it verifying the
diagnostic result of this fixed image, or locking a lifecycle state?

**Method.** (1) Every one of the nine files grepped for reads of committed state (`manifests/`, `evidence/b3`,
`evidence/b2`, the `*_REL` constants, `FROZEN_INPUTS`, `skipUnless` / `skipIf` / `SkipTest` / `skipTest`,
`git_head()` / `FIXTURE_HEAD`, `verify(`, and every read under the repository root `R`) and for stage words
(`"S0"`…`"S3"`, `UNDETERMINED` / `DETERMINED`, `qualified`, `status`, `history`, `calibration`, `aec84514`).
(2) Every one of the nine files read in full (7 141 lines), every hit classified in context. (3) The production side
of every seam a test's meaning depends on, read: `b3_manifest.TRANSITIONS` (S0→S1 `history, image.board_ready,
prereg.frozen, prereg.sha256, status`; S1→S2 `qualification, qualified, calibration, status, history`; S2→S3 `plan,
status, history`), `b3_manifest.image_block` / `experiment` / `prediction` (what the manifest pins at `init`),
`b3_plan.build_plan` (the one use of `rate_measured` is `session_split`; `PLAN_NON_OPERATIONAL = ("generated_utc",
"prediction_sha256")`), `b3_records.context_from` / `expected_order` (which plan and prediction fields a session
context is derived from), `b3_pins.PINNED_GLOBS`. (4) The collected test count per module from
`unittest.defaultTestLoader.discover("b3/tests")` — **793** at `64bca1e` (469 at `ef25681` + 324) — stated as the
loader's count, not as a run: the last full executions recorded are Ran 771 (the stage-5 engineering acceptance,
`docs/b3_stage5_engineering_acceptance_2026_10_12.md`, 4 145 s) and Ran 792 (the stage-6 unit's working report of 2026-10-12, untracked, before
the follow-up's one added test); the 793 of this HEAD has not been run as a whole (the owner: this round runs no suite).
(5) The fifteen audited files compared byte for byte with `ef25681`.

## Inventory delta — the 15 unchanged, the 9 new

**The fifteen files of the 2026-09-27 inventory are byte-identical at `64bca1e` to `ef25681`** (`git diff --quiet
ef25681 HEAD -- <file>` holds for each of the fifteen; `git diff --stat ef25681..HEAD -- b3/tests` is nine files,
7 141 insertions, 0 deletions). Their rows, digests, counts and categories are the 2026-09-27 audit's and are not
restated here. `b3/tests/__pycache__` is discovery noise, not a file of the surface.

| file | SHA-256 at `64bca1e` | tests | added (stage) | categories present (dominant first) |
|---|---|---|---|---|
| `b3/tests/test_b3_carto_twin.py` | `102b12e19b3108289a91880e73a915f7b1bc65aba71a0e08d694d4dd6469cf9b` | 18 | `4817662`, 2026-09-28 (image stage 1) | (d) the twin over the boundary corpus and seeded streams; (a)+(b) `TheCommittedPrediction` reads `evidence/b3/prediction.json` (505) — `pairs[].runs.O.{ledger, ledger_entries, map_version_final, decoded_final}` and the ledger entries' fields (509–533; D1); (a)+(b) `firmware/b2/bsp/lscript.ld` and the pinned ARM toolchain `b2_build_evidence.TC` (241–247, B2's frozen bytes); (e) `8000` = N × B* (532), `bman.IMAGE_REL` (231), the cartographer constants (283–286); no stage word |
| `b3/tests/test_b3_record_twin.py` | `324986df3ac979e8232dc872c8a5034ab08dcae9688da342c2ed28fbe2d1a2ac` | 23 | `08030dd`, 2026-09-30 (stage 2) | (a)+(b) `PRED` at module level (74): `fitness`, `budget_per_arm`, `pairs[r].{landscape_seed, operator_seed, base_train_fitness, runs.O.ledger, runs.O.final_state_sha256}` (186–234, 502–521, 768–776, 870–875, 986; D1); (a)+(b) `b3/firmware/IMPORT.json` (312, the image import table, D5) and `firmware/b2/*` (the verbatim bases); (d) temp copies of the firmware with one defect, ASan builds under `build/`; (e) `8000`, `8 * 1002` (511, 879, 895); no stage word |
| `b3/tests/test_b3_wire_contract.py` | `7d002be42ded8d280f274c9ee9dd03991d6e4044223816e381293418a0542c26` | 13 | `e791758`, 2026-10-01 (stage 3) | (a)+(b) `PLAN`, `PRED` at module level (58–59) through the production `brec.context_from(PLAN, PRED, 0, 1)` (60) and directly `pairs[0].{landscape_seed, operator_seed}`, `budget_per_arm`, `fitness` (122–125; D1); (a)+(b) the instrument bound read-only (172); (e) `(0, 1, 8)` (208), `3000` = 3 × B* (229), the schema versions 1.6.0 / 1.4.0 and `B3_IDENTITY` (65, 201–234); (d) one-change documents on the twin's own output; no stage word |
| `b3/tests/test_b3_leakage.py` | `de8ba8be899ebe4e310df3e6c35dde456d7b0f6bec46421a7f9b2533773328e2` | 13 | `e791758`, 2026-10-01 (stage 3; re-aimed at stage 5) | (a)+(b) `IMPORT.json` (44), the committed image `b3_app.bin` / `.elf` (45–46, 348–355), `evidence/b3/build_evidence.json` `image.{sha256, elf_sha256, bytes}` (354–355), the B1 self-map digest (350) — all pinned inputs, none lifecycle state (D5); (e) `bman.IMAGE_REL`, `bman.BUILD_EVIDENCE_REL`, `IMPORT["stage"].startswith("image stage ")` (255: the import table's IMAGE stage, not S0–S3); (d) a perturbed copy of the table in memory, temp trees; no lifecycle stage word |
| `b3/tests/test_b3_orch_twin.py` | `65f01c0f6df1142fa7363586a151a4723c8883fc4d7cca346e5c6c262fb53626` | 22 | `0fe24b0`, 2026-10-01 (stage 4) | (a)+(b) `PLAN`, `PRED` at module level (69–70) through `context_from(PLAN, PRED, 0, PLAN["pairs"])` (71) and directly `pairs`, `fitness`, `map.sha256`, `seed_derivation.{excluded_values_total, master_seed}` (138, 258–261, 336) and `PRED.pairs[].{seeds, runs.O.*, target}` (270–275, 365, 457; D1); (a)+(b) the committed lifecycle-2 gate report `evidence/b3/gate_2/gate_report.json` through the production `b3_plan.session_exclusion()` / `gate_inputs()` (100–116, which validate it) and once directly for its `seeds.master_seed` (379; D3); (a)+(b) `firmware/b2/p3_data.h` (381), `b3/firmware/b3_seed_data.h` (an image source); (d) B3Q plan / prediction built IN MEMORY by the production builders (135–142, D4), a COPY of the plan perturbed in a temp directory (280–336), UBSan builds; (e) `24026` / `24024` (429–434), `125` / `123` / `40` (497–502), the B3Q profile; no stage word |
| `b3/tests/test_b3_image_stack.py` | `515877bf1f3a3e7193ff5b70a61b1ffc4341e7aabe6745e9c47dd68edc2187f8` | 177 | `94073b3`, 2026-10-04 (stage 5) | (d) dominant: synthetic routines built in memory (`synth`), the newlib rule's alterations of an in-memory copy; (a)+(b) the committed ELF `b3/firmware/bsp/out/b3_app.elf` (39) and `TheFinalImage` / `TheRealContracts` / `TheFlagSetters` / `TheGateOnTheInventory` / `TheNewlibRuleRefuses` asserting the analyser's diagnostic result on THAT image (127–362, 1065–1094, 963–969, 2397–2419, 2587–2730; D2); (a)+(b) the contract units' source digests `CONTRACT_SOURCES` (1083) and the newlib binding digests (268–271, the pinned toolchain's facts); (e) `"b3-image-stack 1.8.0"`, `0x2000`, the DMA sites of this ELF (337–343); no stage word |
| `b3/tests/test_b3_build_evidence.py` | `2c17b6b84c3564fb6fa214b21e340d2ae3bd856d711db93741bcab77043aaadd` | 24 | `171b638`, 2026-10-04 (stage 5) | (a)+(b) `evidence/b3/build_evidence.json` read once (61) and asserted as the diagnostic record of the committed image: provenance (69, 108–156), the stack block `FINDINGS` / `complete False` / every bound `None` / the tool / the rules / the note, and `readiness.image_ready is False` with `blocking == [stack findings]` (71–106; D2); (d) deep copies with one thing wrong, the production `build.sh` run twice into fresh directories under the ignored `build/` with the committed image asserted untouched (192–308), the analyser stubbed to a synthetic COMPLETE block (416–477); (e) `be.EVIDENCE_REL == bman.BUILD_EVIDENCE_REL` (64–66), `0x2000`, the mandatory inventory; no stage word |
| `b3/tests/test_b3_app_audit.py` | `6b6f54410af9ad89b461d499f9c2f4bc7cb5a2268a068bd1dbeefc9c768a9040` | 12 | `171b638`, 2026-10-04 (stage 5) | (a)+(b) `b3/firmware/b3_app.c` and the instrument's units (50, 213–218: image sources), `rtl/b1/b1_axil.v` (51: the B1 carrier's RTL, a B1-pinned input), the instrument bound read-only (351); (d) a generated host driver under `build/b3_bounds`, synthetic serial pieces, a fixture token; no committed lifecycle read, no stage word |
| `b3/tests/test_b3_hostapp.py` | `7d8a5d1b43402fa8bd0a99de151587006d4b68d9a00a93abbfacfd26e28fe78c` | 22 | `e0c0bec`, 2026-10-12 (stage 6; 21 → 22 at `64bca1e`) | (a)+(b) `PLAN`, `PRED` at module level (54–55) through `context_from(PLAN, PRED, 2, 1)` / `expected_order` only (135–136, 200, 210; D1); (a)+(b) `b3/firmware/b3_app.c` for `INT_STS_ERROR_MASK` (61); (d) the real `b3_app.c` executed under the fake PL / DevC, refusals and F-WIN fault injection — a simulation (the owner's ruling: never evidence that the hardware stopped a DMA); (e) `[8, PAIR, 1]` (190), `3005` = 2 + 3 × B* + 3 (189–197), `ERROR_BITS == [6, 11, 14, 15, 18, 20, 21, 22, 23]` (350: the image's own mask, read from the source and held to the enumerated list); no stage word |

Nine files, 324 tests; with the fifteen, 24 files and 793 tests by the loader.

## The six rules, one conclusion each — over the nine files

| # | conclusion |
|---|---|
| R1 | **Holds, vacuously.** None of the nine reads `manifests/b3_manifest.json`, `evidence/b3/plan.json`'s stage-bearing fields, the pin table, a session archive, a qualification record or a calibration; none takes a stage from anywhere (the grep for `"S0"`…`"S3"`, `qualified`, `UNDETERMINED` / `DETERMINED`, `calibration`, `history`, `manifests/`, `git_head`, `FIXTURE_HEAD`, `verify(` has **zero** hits in the nine files). The committed reads are the plan / prediction (D1), the gate report (D3), the build evidence and the image (D2, D5): none is lifecycle state. |
| R2 | **Holds — no new matrix is required.** No new test is stage-aware, so none needs driving at S0–S3 and the illegal pairings. The plan / prediction readers inherit their invariance from `build_plan` (D1), exactly as the 2026-09-27 audit's F2 did for `test_b3_session.CommittedPrediction`; the guards that stand between them and a drift are the existing `test_b3_plan.StageCoverage` (the committed plan at pre / S0 / S1 / S2 / S3 and the illegal pairings) and `test_b3_lifecycle.LegalPath.test_each_transition_changed_only_what_it_licenses` (`TRANSITIONS`). Both are among the fifteen unchanged files. |
| R3 | **Holds.** `skipUnless` / `skipIf` / `SkipTest` / `unittest.skip` / `skipTest(` occur in none of the nine files. Every docstring says "No skip", and the code does what it says: an absent host compiler, ARM toolchain, instrument, ELF, evidence or `nm` raises `AssertionError` ("a failure, never a skip" — `test_b3_carto_twin.py:84, 247`, `test_b3_record_twin.py:96, 351, 408, 547`, `test_b3_wire_contract.py:81`, `test_b3_orch_twin.py:152, 567, 666`, `test_b3_hostapp.py:71`, `test_b3_app_audit.py:243`, `test_b3_build_evidence.py:149`); a module-level read of `plan.json` / `prediction.json` / `IMPORT.json` / `b3_app.c` makes the module's import fail on an absent file — a red proof, not a quiet green. |
| R4 | **Holds.** The values the nine name on committed state are not in any `TRANSITIONS` path: the plan fields read (D1) are `schema`, `schema_version`, `lifecycle`, `budget_per_arm`, `fitness`, `pairs`, `seed_derivation.*`, `map.sha256`, `carto_version`, `b1_map_cost`, `gate.*`, `records.*` — and `b3_plan.build_plan` lets only `session_split` depend on the rate (its one use of `rate_measured`, `b3_plan.py:331`), while `generated_utc` and `prediction_sha256` (`PLAN_NON_OPERATIONAL`) are read by none of the nine (grep: zero hits for `generated_utc`, `prediction_sha256`, `session_split`, `planning_rates`). The prediction's bytes are the S0 prediction throughout (`test_b3_lifecycle.py:548`, unchanged). The build evidence and the image are not in any transition (D2). |
| R5 | **Holds, vacuously.** No file among the nine names `aec84514…`, the B2 manifest, B2's stage or `qualified`. The B2 bytes they read are frozen SOURCES (`firmware/b2/*`, `b2_build_evidence.TC` / `ARCH_FLAGS`, `b2_search.EXCLUDED_SEEDS`, the B1 self-map) — content pinned by the B2 pin table, read as data, never as authority. |
| R6 | **Holds.** `tests/test_b3_online.py` is byte-identical to `ef25681`, still B2-pinned (`manifests/b2_instrument_pins.json`: `tests/test_b3_*.py`, digest `7ea1ef61…`), and is not discovered by `-s b3/tests` (the loader's module set at `64bca1e` is the 23 `b3/tests/test_b3_*` modules and nothing under `tests/`). No new file imports it or reads its two committed inputs. |

## Findings

### D1 — five modules read the committed plan and prediction at module level — stage-invariant (PASS, the F2 treatment)

Category (a)+(b). `test_b3_wire_contract` (58–59), `test_b3_orch_twin` (69–70), `test_b3_hostapp` (54–55) read
`evidence/b3/plan.json` and `evidence/b3/prediction.json`; `test_b3_carto_twin` (505) and `test_b3_record_twin` (74)
read the prediction alone. Followed to the fields used (the owner's criterion (i)):

* **Through the production derivation** `b3_records.context_from(plan, prediction, first, count)` (wire, orch,
  hostapp): the plan's `schema`, `schema_version`, `lifecycle`, `budget_per_arm`, `fitness`, `pairs`,
  `seed_derivation.master_seed`, `map.sha256`, `carto_version`, `b1_map_cost`; the prediction's `schema`,
  `schema_version`, `lifecycle`, `fitness`, `budget_per_arm`, `carto_version`, `b1_map_cost`, `pairs[].{pair,
  landscape_seed, operator_seed, arm_order, runs.{R,F,O}, runs.O.{budget, ledger_schema_version, ledger,
  final_state_sha256}}` (`b3_records.py:187–274`); and `expected_order` from the context's budget, slice and
  `b3_plan.ARM_SEQUENCE`.
* **Directly**: the prediction's `fitness`, `budget_per_arm`, `pairs[r].{landscape_seed, operator_seed,
  base_train_fitness, target, runs.O.{ledger, ledger_entries, ledger_sha256, map_version_final, decoded_final,
  anomalies, final_state_sha256, champion_genome_sha256, online_map_sha256}}` and the ledger entries' fields; the
  plan's `pairs`, `fitness`, `map.sha256`, `seed_derivation.{excluded_values_total, master_seed}`
  (`test_b3_orch_twin.py:138, 258–261, 336, 365`).

Why it is stage-invariant: the S2→S3 transition regenerates the committed plan through `pl.build_plan(rate, gate)`, in
which **only `session_split` depends on the rate** (`b3_plan.py:302–331`: `rate_measured` is used once, at
`"session_split": session_split(n_pairs, budget, rate_measured)`); the only other fields that differ between two
renders are `generated_utc` and `prediction_sha256` (`PLAN_NON_OPERATIONAL`, `b3_plan.py:83`); none of the fields
above is any of the three. The prediction is pinned at S0 and its bytes never change (`m["plan"]["prediction_sha256"]
== m["prediction"]["sha256"]`, `test_b3_lifecycle.py:548`; the S3 regeneration keeps `prediction_sha256` by
construction — `test_b3_plan.StageCoverage` holds the committed plan at every stage and refuses a drifted pin). The
S0→S1 and S1→S2 transitions touch no plan field. So no legal transition changes a value these five modules read: the
F2 treatment applies, and **no new stage matrix is required** (the owner's criterion (i)).

Note (P3, no change required — the same note as F2's): none of the five is itself driven at S3 by a `StageCoverage`;
their invariance is `build_plan`'s. Should a later plan-tool change make any of the fields above rate-dependent,
`test_b3_plan.StageCoverage` fails first (it drives the committed-plan test at pre / S0 / S1 / S2 / S3 and holds the
S3 regeneration to `session_split` alone).

### D2 — the committed build evidence and the committed image are asserted as a DIAGNOSTIC record of one fixed ELF — stage-invariant, not a lifecycle lock (PASS; a category correction; one ordering note)

Category (a)+(b) — and **not (f)**: these are assertions, and the owner's correction places them in (a).

`test_b3_build_evidence.Committed.test_the_stack_assessment_has_findings_and_the_image_is_blocked` (71–106) reads
`evidence/b3/build_evidence.json` and asserts `stack.status == "FINDINGS"`, `complete is False`, every entry's `bound
is None`, no computed `unpublished` for main, the table-refusal findings present and the emitter findings absent, more
than 100 "write(s) not placed", the six withheld exception entries "synchronous paths only", the tool
`b3-image-stack 1.8.0`, `read_only_tables.targets == []`, the note "NOT complete", and then `readiness.image_ready is
False` with `readiness.blocking == ["stack: " + each finding]` and `be.readiness_findings` naming the incomplete
assessment. `test_b3_image_stack.TheFinalImage` (127–362) asserts the same result straight off the ELF (`r["ok"]`
false, no main bound, the three tables `TX_IO`, `PULL_IO`, `REC_IO` refused, the DMA commands and their sites, the
masks), and `test_b3_leakage.TheBinary` (344–355) binds the image's digests and size to the evidence's record.

Judged with the whole block (the owner's criterion (ii)):

* **It verifies the diagnostic result of THIS image, not a lifecycle state.** The block is bound to the ELF by its
  own digest (`st["elf_sha256"] == ev["image"]["elf_sha256"]`, 76; `sha(ELF) == ev["image"]["elf_sha256"]`, 111)
  and the verifier re-runs the analyser on that ELF and requires the recorded block to equal the fresh one
  (`verify_findings`, asserted empty at 69 and refused for every one-field drift at 393–414). `image_ready` is not a
  free literal there: it is held to `blocking`, and `blocking` to the stack findings, and the findings to a fresh
  analysis — the test asserts the readiness the evidence's own rule derives for this ELF, and asserts in the same
  class that the rule flips with a COMPLETE block (`test_readiness_is_empty_only_when_complete_and_within_budget`,
  456–477, the analyser stubbed). That is the shape of a verification of a fixed artefact, not of a stage.
* **No legal transition changes it.** `readiness.image_ready` is a field of the build evidence, not of the manifest;
  `TRANSITIONS` names `image.board_ready` (S0→S1) — the owner's mark in the manifest's image record — and nothing in
  the evidence. The manifest pins the evidence at `init` (`image_block`: the image's path, digests, size and the
  evidence's own digest, `b3_manifest.py:394–421`), every `verify` re-compares the manifest's image record to the
  evidence and the binary (`_same("image", …)`, 430), and the S1 freeze adds `board_ready` beside it (1041). After S0
  a changed evidence is therefore a **refusal** of the production verify, not a drift these tests could silently
  follow; before S0 the evidence changes only by a pinned edit (a rebuilt image or a new analyser), which is exactly
  the kind of edit §8 orders before the table.
* **The B2 lifecycle-1 shape is absent.** B2's defect was a value true at S0–S2 and false at S3 *by the
  preregistration's own rule*. `image_ready` has no stage-dependent rule: it is true only when the assessment is
  COMPLETE within budget and the provenance verifies, at every stage alike. An image that becomes ready changes the
  evidence file, not the stage.

**Ordering note (carried to "What else must hold before S0").** These assertions deliberately pin the diagnostic
shape of the current image (`FINDINGS`, `1.8.0`, the three tables, the DMA sites `0x2001ad0` / `0x2002800` /
`0x200332c` / `0x2003340` / `0x2003394`, `> 100` unplaced sites, `== 6` withheld). Any pinned edit that regenerates
the evidence — a rebuilt image, a new analyser version, or the readiness unit that would make `image_ready` true — goes
red here by design (the discipline of `test_b3_orch_twin.B2_FRAME_EXCEPTIONS`: a stale guard is itself a failure)
and must update `test_b3_build_evidence.Committed`, `test_b3_image_stack.TheFinalImage` and `test_b3_leakage.TheBinary`
in the same unit, before the pin table; after S0 the same edit is a lifecycle event (a new image under a new manifest),
not a test change.

### D3 — `test_b3_orch_twin` reads the committed lifecycle-2 gate report, through the production validation — stage-invariant (PASS, one observation)

Category (a)+(b). The 2026-09-27 audit recorded that `test_b3_gate` "never reads the committed lifecycle-2 gate
report (`evidence/b3/gate_2/`)". The orchestrator unit does: `b3_plan.session_exclusion()` and `gate_inputs()` are
called once per process (100–116, cached because the production validation of the report takes minutes), and the
report is read once directly for its `seeds.master_seed` (379). The gate report is pinned by the committed plan
(`plan.gate.{path, sha256, head_at_run, rules_version}`, which the generator test holds the header to, 326–328) and
by the manifest at `init` (`experiment`: `GATE_REL` with its digest and `rules_version`, `b3_manifest.py:451–477`);
no transition regenerates it. The tests assert B* and N only as "the gate's" (`gi["budget_per_arm"]`, `gi["pairs"]`,
305–314) — production's validated numbers, never a free literal.

Observation (no change required): this is the first B3 test to read `evidence/b3/gate_2/gate_report.json` as data. It
reads it the right way — through the module that validates it — and the written constants of that report are in the
preregistration (§2: B* = 1 000, N = 8), so the reads are (e) as much as (a).

### D4 — the B3Q plan and prediction are built in memory from the production builders — fixture-local (PASS, one forward note)

Category (d)+(e). `test_b3_orch_twin.b3q()` (135–142) builds the qualification plan and prediction with
`pl.build_qualification_plan` / `build_qualification_prediction` and judges the twin's B3Q session (125 records, 123
fitness values, 40 ledger entries, the `Unscored` positions) against `b3_session.run_context` over that in-memory
context. No file under `evidence/b3/b3q_*` exists at `64bca1e` (`QUAL_PLAN_REL` / `QUAL_PREDICTION_REL` are the
qualification unit's), so nothing here is a committed read.

Forward note for the "B3Q documents" unit (the next in the §8 order): when the canonical B3Q plan and prediction are
committed, `qualification`, `qualified` and `calibration` become S1→S2 values (`TRANSITIONS`), and the manifest holds
the committed documents to the canonical render (`b3_manifest.py:527–545`). A test that then reads the committed
`b3q_plan.json` / `b3q_prediction.json` reads committed lifecycle inputs and is R1 / R2 / R4 business — it must be
driven as `test_b3_plan.Committed` is, or confine itself to fields the S1→S2 transition does not change. The present
in-memory construction needs nothing.

### D5 — the image's own pinned inputs: `IMPORT.json`, the committed binary and ELF, the firmware sources, the B2 bases, the B1 RTL and map, the instrument — stage-invariant (PASS)

Category (a)+(b). `test_b3_leakage` (44–46, 96–97, 247–255, 344–355), `test_b3_record_twin` (312–321),
`test_b3_app_audit` (50–51, 351), `test_b3_hostapp` (61), `test_b3_image_stack` (39, 1083), `test_b3_carto_twin` /
`test_b3_record_twin` / `test_b3_orch_twin` (`firmware/b2/bsp/lscript.ld`, `p3_data.h`, the pinned ARM toolchain)
read files the B3 image is built from or verified against. Every one is a pinned input of the image (the import
table is held to the tree and to the build evidence; the sources are in `APP_SOURCES`; the B2 bases are B2-pinned;
`rtl/b1/b1_axil.v` and the self-map are B1's lineage as B2 carries it; the instrument is bound read-only at
`PSORACLE_ROOT`). None is lifecycle state; none changes by a transition. `IMPORT["stage"].startswith("image stage ")`
(`test_b3_leakage.py:255`) asserts the import table's own image-stage marker, a string of the artefact, not S0–S3.

### D6 — literals that are preregistered or protocol constants (category e)

`8` (N), `1000` (B*), `8000` = N × B*, `3000` = 3 × B*, `3005` = 2 + 3 × B* + 3, `24026` / `24024` (the eight-pair
session's records and blocks), `8 * 1002` (one init, 1 000 evaluations and one holdout per pair), `(0, 1, 8)` /
`[8, 2, 1]` (a slice of the N pairs), `125` / `123` / `40` (the B3Q profile: one pair, budget 40, order RFO),
`ARM_SEQUENCE`, the schema versions `1.6.0` / `1.4.0` / `2.0.0`, `B3_IDENTITY`, `specimen-carto-v1.1`, `292` / `6` /
`64`, `0x2000`, `b3-image-stack 1.8.0`, the newlib 4.4.0 digests, `INT_STS_ERROR_MASK`'s nine bits — each a
preregistered constant (v0.3.1 §2 / §3), a protocol version, or a constant of a pinned input read back and held to
the enumerated value. None is a stage, a split status, a calibration, a session count or a history length.

**Nothing in (f) carries an assertion.** The refusal texts asserted with `assertIn` in the nine files
(`"REFUSED_BY_GATE: …"`, `"DEVCFG D_P_DONE never asserted"`, `"STOP_LINK3: …"`, the generator's and the validator's
named findings, the analyser's finding sentences) are the production code's own words for a condition the test
constructed on a fixture or on the fixed image; docstrings and comments read or assert nothing.

## StageCoverage — what the nine need

| test | driven at | note |
|---|---|---|
| `test_b3_carto_twin.TheCommittedPrediction`, `test_b3_record_twin` (`TheRealOArm`, `TheCommittedLedger`, `TheImageBranch`, `_Probe`), `test_b3_wire_contract` (`session()`, `TheValidatorRejectsByName`), `test_b3_orch_twin` (`TheCommittedSession`, `ALaterSlice`, `TheSeedRule`, `Refusals`, `TheSliceAtTheCApi`), `test_b3_hostapp` (every scenario) | the current tree only (pre-S0) | stage-invariant fields of the plan and the prediction (D1), the F2 treatment: no matrix; guarded by `test_b3_plan.StageCoverage` and `LegalPath.test_each_transition_changed_only_what_it_licenses` |
| `test_b3_build_evidence.Committed`, `test_b3_image_stack.TheFinalImage` and the classes that read the ELF, `test_b3_leakage.TheBinary` / `Imports` | the current tree only | the fixed image's diagnostic record and its pinned inputs (D2, D5): invariant across S0–S3, pinned by the manifest from S0 |
| `test_b3_orch_twin.TheBuildAndTheSeedHeader`, `TheGeneratorChecksThePlanAgainstTheGate`, `TheSeedRule` | the current tree only | the gate report through production validation (D3); the plan perturbed only as a temp copy |
| every other class of the nine files | fixtures, synthetic routines, temp trees, in-memory copies | (d): no committed read |

No test of the nine reads a value a legal transition changes; none needs driving at S0–S3 or against the illegal
pairings. The 2026-09-27 matrices A–D (over the fifteen unchanged files) stand as written.

## The B2 authority boundary

Unchanged by the nine files: none reads `manifests/b2_manifest.json`, none asserts B2's stage, none injects a seam
into the production verify (`verify(` has no occurrence in the nine). The B2 material they touch is frozen content
— sources, flags, the exclusion seeds, the self-map — imported by content and hashed by the B3 import table and build
evidence, as §10 of the 2026-09-27 audit says it may be.

## Verdict — PASS (the nine files at `64bca1e`; the fifteen stand at `ef25681`)

No file among the nine reads committed lifecycle state and asserts what a transition changes (R1, R4), none takes a
stage from anywhere (R1), none skips on a committed artefact (R3), none asserts B2's stage (R5), and the frozen online
test is untouched and undiscovered (R6). The two points the scope draft left open are closed: the plan / prediction
reads are stage-invariant by `build_plan`'s own rule (D1, no new matrix), and the `image_ready is False` assertion
verifies the fixed image's diagnostic record with its whole block, which no transition changes (D2, with its ordering
note). Nothing here reopens the stage-5 engineering acceptance or the stack-proof requirement: the diagnostic result
the tests pin is the one that acceptance recorded, and this audit says only that the tests pin it lawfully.

## What else must hold before S0 (for the owner's review; the 2026-09-27 list, updated)

1. **The ordering constraint, extended by D2.** Every pinned edit that regenerates the build evidence or rebuilds the
   image — including the unit that would make the image ready — updates `test_b3_build_evidence.Committed`,
   `test_b3_image_stack.TheFinalImage` and `test_b3_leakage.TheBinary` in the same unit, before the table is generated
   once. The 2026-09-27 items 1, 2 and 5 stand (F3 done; `docs/b3_architecture.md` equal to HEAD whenever the suite
   runs; the committed plan rate-less until S3).
2. **The pin surface now covers the stage-6 harness.** `b3_pins.PINNED_GLOBS = ("b3/**/*", "docs/b3_architecture.md")`
   takes in `b3/tb/hostapp/` (the harness, its stub BSP headers, `build.sh`) and every file of `b3/tests/` and
   `b3/firmware/` alike; `build/` and the temp directories the tests use are outside it. No file the nine tests
   WRITE is under the surface: the twins, the ASan / UBSan builds, the bounds driver, the hostapp binary and
   `timings.json`, the rebuilds of `TheRealBuild` and the stack-usage objects all go to `build/` or to
   `tempfile` directories, and `TheRealBuild` / `TheBuildDirectories` assert the committed image untouched. The
   pre-freeze clean-tree proof will check this by running, not by this reading.
3. **The suite's wall time.** 793 tests by the loader; the last whole runs recorded took 4 145 s (771) and 4 277 s
   (792, the stage-6 unit's working report) on this host, with the twins' 8 000-entry replays, the orchestrator's 24 026-candidate session, the real
   build twice and the hostapp's whole pair uncached. The 2026-09-27 item 3 (the committed-state verify after S0,
   about two minutes per `Committed` test) adds to that. The test-report tool's three runs and the pre-freeze proof
   should be budgeted at that order.
4. **The B3Q documents unit (D4).** A test that reads the committed `b3q_plan.json` / `b3q_prediction.json` once they
   exist reads S1→S2 inputs and must be audited under R1 / R2 / R4 before freeze; the present in-memory construction
   in `test_b3_orch_twin` is not such a read.
5. **The runner's profile stage (the 2026-09-27 item 4)** is unchanged and still the owner's runner question, not a
   §9 finding.

## Not done here

- This document is the only file this unit touches. No test, production module, evidence file, `IMPORT.json`, pin
  table, manifest, canonical proof or ruling is created or changed; the 2026-09-27 audit document is not edited (its
  verdict covers the fifteen at `ef25681`, this one the nine at `64bca1e`).
- No suite was run for this document (the owner's ruling of 2026-10-13, item 2): the 793 is the loader's count; the
  executed numbers cited are the earlier records named above.
- `tests/test_b3_online.py` is not audited here (R6; B2's audit of 2026-09-16 covers it).
- No pin table, no S0, no board. With the §9 delta closed, the next unit in the §8 order is the B3Q documents, then
  the pin table once, then S0 — each a separately authorised unit.

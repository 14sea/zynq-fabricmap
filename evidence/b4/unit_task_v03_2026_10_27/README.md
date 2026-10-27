# B4 — the task-v0.3 revision unit (host-only, 2026-10-27): the slice-wide CE / SR stimulus, delivered for review

**What this unit is.** The engineering unit the owner authorised on 2026-10-27 (the ruling as relayed: `owner_ruling_2026_10_27.txt`),
after the PASS on the carrier v2 unit (`bf17574`, closed at `e084f07`): "a complete host-only revision engineering unit, delivered for
review once, no separate scope draft". Its reason is the carrier v2 finding — a 7-series slice has **one CE pin, one SR pin and one CLK
pin shared by its eight storage elements** (`docs/b4_carrier_v2.md` §0; AMD UG474) — under which task-v0.2's per-element `ce` / `sr`
stimulus is not realisable on the site. The revision fits the stimulus to the physical slice. It is **not** a repair of the three
negative Ω − R records (`b4-sim-3`, `b4-gate-1`, `b4-sim-4`), which stand unchanged and are not re-interpreted, and it **predicts no
map benefit**: K9's coverage and the search's behaviour under the new stimulus are to be measured by the next exploration.

**Scope (the ruling's three items, and the two scope questions it answered):** (1) task-v0.3's stimulus rule, the model input contract
and the explicit mapping onto the carrier's format; (2) the necessary K9 revision — none to the comparison set or the applicabilities;
the difference of estimand named and the data influence disclosed; (3) the protocol identity, the re-verification path of the old
archives, and the documents, tools, fixtures, regression and end-to-end verification. The observation contract revised narrowly to
v0.6 (2.2, the version pointers, the cross-references; task-v0.2's shape kept as history; the common grammar and the carrier format
unchanged, the broadcast stated as one control value per step). The go / no-go row of the next exploration placed in this unit,
document and machine table together, every number carried unchanged, the p threshold named `p_max_go` — a cost threshold, not an α.

**Branch.** `b4-task-v03` from `e084f07` (the carrier v2 closure; `main` = `origin/main` = `a243ee8`). Commits: `12ea4da` (the
implementation and the documents), `814d35c` (the test the shape mutants name, the mutant battery, the e2e driver), `bf02746` (one
test re-pinned after the first full battery), then this unit's evidence commit. Nothing pushed, nothing merged.

**Not authorised and not done:** no production label derived, smoked, explored or gated (`b4-sim-5` is a reserved name; no value of
it exists); no change to the operator, the benefit thresholds, the statistics, the hypothesis file (hence the anchor), the certificate,
the model's state machine, K9's panel or applicabilities, K10, the engine, the cartographer, any archive, receipt, seed or verdict,
the carrier RTL / register map / records; no board, no RTL, no 2d, no routing, no push, no merge. Every batch run here is a
**mechanics fixture** under explicit `b4-mech-*` schedules of already-exposed values; none of it is a result.

## 1. What changed, by file

| file | what it now is |
|---|---|
| `b4/host/b4_landscape.py` | `TASK_VERSION = "task-v0.3"` (`PREVIOUS_TASK_VERSION = "task-v0.2"` kept as history); the stimulus rule (`STIMULUS_RULE`, `CE_HIGH_ONE_IN = 2`, `SR_HIGH_ONE_IN = 4`, `BROADCAST = {0: 0x00, 1: 0xFF}`): per `set` step **one** CE value high with probability 1/2 (`uniform(2) == 0`), **one** SR value high with probability 1/4 (`uniform(4) == 0`), the two draws independent, each **broadcast** over the eight elements; `d` a per-element uniform 8-bit draw; the draw order `ce`, `sr`, `d`; `broadcast` / `is_broadcast` / `slice_wide_controls`; **`stimulus_findings`** — the task-v0.3 shape held, not assumed (an init step at index 0 only, every other step a set step whose `ce` / `sr` are the int broadcast values, `clock` 0 / 1, `d` in 0..255; total, never raises); `MODEL_INPUT_CONTRACT`. K / level steps / mask / weights / ceilings / holdout salt / the planted rule (T-i) / the PublicTask boundary (H): unchanged. |
| `b4/host/b4_sim_schema.py` (`task_findings`), `b4/host/b4_target.py` (`setup_findings`) | both stimuli of every `task.json` held to the shape by the record validator; the public parts re-derived from the plan's seed held to the shape by the offline reconstruction. |
| `b4/host/b4_thresholds.py` | `task.version = "task-v0.3"`, `task.stimulus` (the rule, `previous` as history); `anchor.exploration_label = "b4-sim-5"`, `consumed_labels` + `b4-sim-4`; `gonogo.p_max_go` (the same 0.20; `alpha_go` retired), `gonogo.applies_to`, `gonogo.p_max_go_standing`; the pins for §7.2, §9.2, §9.3 (K1–K10, every number: unchanged). |
| `b4/host/b4_seeds.py` | `CONSUMED_LABELS = {b4-sim-3, b4-gate-1, b4-sim-4}`; `EXPLORATION_LABEL = "b4-sim-5"`; `GATE_LABEL = "b4-gate-2"` kept (never derived). |
| `b4/host/b4_protocol.py` | the `task` component carries the stimulus rule, its two constants and the broadcast (a new method version: `protocol_sha256` `5bba53c7…`). |
| `b4/host/b4_sim.py` | the standing text (v0.3.0), the manifest's `constants.stimulus` block, the CLI help. |
| `b4/host/b4_gonogo.py`, `b4/host/b4_gate.py` | `p_max_go` in the policy, the decision record's `statistic_1` (`p_le_p_max_go`, `p_max_go`, `p_max_go_standing`) and the reasons; version texts. The decision rule and its numbers: unchanged. |
| `b4/architecture_revision.json`, `b4/IMPORT.json` | v0.3.0; the table refreshed (`refresh_import.py` here; 59 entries, no new file under `b4/`). |
| `docs/b4_architecture.md` v0.3.0 | the revision note; **§7.2 task-v0.3** (the rule, the common grammar / model input contract / carrier mapping, held-not-assumed, ceiling ≠ reachability, the influence disclosed); the K9 row's v0.3.0 note and **§9.3 clause 7**; §9.2 the labels; **§9.4 the row for `b4-sim-5`** with `p_max_go`; §12, §13 (this unit's row), §14. |
| `docs/b4_observation_contract.md` v0.6 | 2.2 for task-v0.3 (task-v0.2's shape as history), the heading / revision note, the status index row, four cross-references. |
| `docs/b4_preregistration.md` v0.0.4 · `docs/b4_archive_reverification.md` §6 · `docs/b4_carrier_v2.md` §8 item 1 | the pointer; the `b4-sim-4` archive under its own tool (`495cc36`, archive commits `580c0e5` / `adce027`); the pointer from the carrier's open item. |
| `b4/tests/` | `test_b4_landscape.TheSliceWideStimulus` (the shape; the two probabilities and the draw order **by hand from the generator's own draws**; the validator on every defect incl. the previous shape; the carrier `STEP_IN` mapping and `realisable`); `test_b4_ff_model.SliceWideControls` (the formal model against a **slice-wide twin** on 60 sampled configurations × 6 task stimuli, 360 traces equal; and where the two part — a per-element vector, which the validator names); `test_b4_sim…previous_shape_is_refused…` (a task record of the previous shape, digest refreshed, refused by the validator and by the reconstruction); the labels, the pins, the identity's task component, the manifest constants, `p_max_go`. Three existing assertions corrected (§4). |

**Unchanged, named:** `b4/host/b4_ff_model.py`, `b4/host/b4_ff_hypothesis.py`, `b4/hypothesis/*` (`HYPOTHESIS_SHA256` `59948f9b…`, hence
the anchor), `b4_ff_mapping.py`, `b4_engine.py`, `b4_carto.py`, `b4_controls.py`, `b4_k9.py`, `b4_k10.py`, `b4_replay.py`, `b4_snapshot.py`,
`b4_observe.py`, `b4_stats.py`, `b4_gate_stats.py`, `b4_deadline.py`, `b4_execution.py`, `b4_rng.py`, `b4_sim_verify.py`, `b4_gate_verify.py`,
`b4/schemas/`, `b4/probes/`; every number of §9 and of the go / no-go policy; `host/b4carrier_*`, `rtl/b4`, `tb/b4`, `vivado/b4`;
`git diff --name-only e084f07 HEAD -- b3 firmware manifests scripts gate_runs evidence/b1 evidence/b2 evidence/b3 evidence/b4/sim
evidence/b4/gate evidence/b4/gonogo host rtl vivado tb b4/hypothesis b4/schemas b4/probes` is **empty**.

## 2. The design, in six lines

1. **One control value per step, broadcast.** The physical slice has one CE / SR / CLK; the task now draws one CE and one SR value per
   step and writes each as `0xFF` / `0x00` over the eight elements. INIT / SRVAL stay sixteen per-element bits (the shared pins are
   control inputs, not configuration).
2. **The grammar does not move.** 8-bit `ce` / `sr` remain the common grammar of the model, the contract and the carrier; task-v0.3
   produces only the two broadcast values. The model's per-element evaluation under a broadcast gives every element the same control
   value — the slice-wide semantics — so the state machine is not rewritten (proved against a twin); the carrier's `realisable` refusal
   becomes an invariant the task never hits.
3. **Held, not assumed.** `stimulus_findings` is called by the task record validator and the reconstruction; the previous shape is a
   named finding.
4. **The identity moves.** The stimulus rule is a component of the protocol identity; the v0.2.0 archive is refused by name
   (`docs/b4_archive_reverification.md` §6), never re-judged.
5. **Labels and policy.** `b4-sim-4` consumed; `b4-sim-5` reserved; the go / no-go row carried unchanged, `p_max_go` named as the cost
   threshold it is.
6. **Nothing predicted.** The ceiling (64 / 80) is the count of scoring cells; the planted configuration's reachability on its own
   trace is checked per pair; a search's reaching it and K9's coverage under the new stimulus are to be measured.

## 3. The verification record (the final tree `bf02746`, fresh processes)

| record | file | result |
|---|---|---|
| the complete local test battery | `tests.txt` | every `b4/tests/test_b4_*.py` module by name: **Ran 332 tests, OK** (679.988 s) |
| the mutant battery | `mutants.txt` (driver `b4_v03_mutants.py`, 72 mutants: M1–M57 of the v0.2.0 unit re-run with M14 / M36 / M37 re-aimed at their moved lines, M58–M72 for this unit's contracts) | **68 / 72 killed**, each kill `[Ran N > 0, FAILED]` with the killing tests named; the survivors: **M31 / M39 / M45** — the three equivalent mutants of the accepted disk-authority design (the v0.2.0 unit §5 R3 / §5.2 C2; accepted by the owner's reviews of `b29b0fb` / `21db2de`), surviving as they did there — and **M67** in its first form (§4) |
| M67 re-aimed | `mutants_M67_reaimed.txt` | **1 / 1 killed** (`Ran 1, FAILED`, `test_it_is_deterministic_complete_and_excludes_the_document_revision_from_the_digest`) |
| the mechanics e2e, round 1 | `e2e_v3/` (driver `e2e_v3_fixtures.py` — the v0.2.0 unit's accepted second driver, unchanged in its cases, normalisation and comparison, plus the other-identity cases of §4; `e2e_v3_run.log`) | `as_expected: true`, `production_derivation_calls: [0, 0]`, exit 0 (round 1 2026-10-27T11:29:45Z, HEAD `bf02746`, identity `5bba53c7…`): the 18 batch cases, the six tampers (each refused and named), `impossible_order` and the four `gonogo_contract` probes refused by name, the explanation tamper differing in exactly `gate_report.json`, the semantic tamper in exactly its four chained files (47 equal), `identity_revision` (a documentation-only revision leaves `protocol_sha256` unchanged; a threshold number changed is refused unrefreshed and gives another digest refreshed), and `old_archives`: `b4-sim-3` / `b4-gate-1` refused by name (no identity) by the batch verifier, the judge and the policy; **`b4-sim-4` refused by name (another identity, the `task` component named) by all three; its go / no-go record refused at the policy-shape check**; every committed archive byte-identical before and after and the three namespaces' listings unchanged (`untouched: true`); `complete_32` on the fixture: no-go, `formal: false` |
| the mechanics e2e, round 2 (a fresh root, a later time) and the comparison | `e2e_v3_repeat/`, `e2e_v3_compare.txt` (`e2e_v3_compare.py`) | round 2 `as_expected: true`, `[0, 0]`, exit 0 (2026-10-27T14:22:04Z, a fresh hermetic root and HEAD); **`pass: true` — 966 of 966 comparable normalised digests equal across the two rounds, 0 different, 0 missing; 0 markdown renderings skipped by rule (held to their JSON by the verifiers)** — the same bit-for-bit reproduction the v0.2.0 unit established, now of the v0.3.0 stack |
| the first e2e attempt on this tree | `e2e_v3_first_attempt/` (log and summary only) | every case as expected except the driver's own stale `untouched` check (§4); the product untouched; superseded by `e2e_v3`, not rewritten |
| the import table | `import_check.txt` | 59 entries, every digest equal, no tracked file under `b4/` without an entry |
| the identity | `protocol_identity.txt` | `protocol_sha256` `5bba53c7…`, revision v0.3.0, labels / task / K9 as the table's |
| the protected paths | `protected_paths.txt` | the diff of §1's protected list against `e084f07`: empty |

**The mutant battery's history, by the proportionality rule.** One full run of the 72 on the final tree: 68 / 72, the three known
equivalents surviving as recorded by the v0.2.0 unit, and M67 surviving in its first form. M67's first form replaced the identity's
`broadcast` component (`{str(k): v for k, v in bl.BROADCAST.items()}`) with the literal `{"0": 0, "1": 255}` — **equal to the
generator's constant on the unmutated tree: an equivalent mutant by construction, a mutant-design error, not a test gap**. It was
re-aimed to the wrong literal `{"0": 0, "1": 128}` and re-run alone: killed by the identity test that pins the component to the
generator's constant. `mutants.txt` is kept as the full run wrote it; the re-aim is its own log. No mutant was counted as killed on an
EDIT-MISS, a non-green baseline or `Ran 0` (`--check`: 72 defined, 0 edit-miss before the run).

## 4. What the owner should know

- **Three existing test assertions corrected** (test files are not method; the contracts they test are unchanged): (a)
  `test_b4_k9…end_to_end…` read the uncovered-pair listing of the **judged (b′)** record for a pair that is uncovered under the all-panel
  rule but SR-tied-low (excluded from (b′) by design); under the new stimulus the first such pair happened to be an `sr_kind` pair and
  the assertion failed for the right reason — it now reads each uncovered pair in the all-panel list and in the (b′) list exactly when
  conditionally applicable. (b) `test_b4_gonogo…refusals_write_nothing` asserted that the repository's `evidence/b4/gonogo/` namespace
  does not exist; it exists since the committed `b4-sim-4` decision (2026-10-21) — the test now compares the namespace's listing before
  and after, and adds the `b4-sim-4` archive as the refused-by-name other-identity case. (c) `test_b4_gate…standing_for…` pinned the
  harness's standing text to "protocol v0.2.0"; re-pinned to v0.3.0 / task-v0.3 (the one failure of the first full battery, `bf02746`).
- **The e2e driver's `untouched` check** had the same stale assumption (b); corrected in `e2e_v3_fixtures.py` (the five committed
  directories byte-compared and the three namespaces' listings compared before and after; the v0.2.0 `b4-sim-4` batch and its go / no-go
  record added as the other-identity refusal cases). The first attempt is kept as its log and summary (§3); a second attempt was stopped
  on a driver needle (next bullet) and nothing of it is kept.
- **An observation on the go / no-go verifier, for the owner (no change made).** `b4_gonogo.py verify` validates the record's shape —
  its `policy` block against the current table — **before** it compares the protocol identity, so the committed v0.2.0 decision record
  (`evidence/b4/gonogo/b4-sim-4_20261021T065857Z`, whose policy block carries `alpha_go`) is refused by name at that step
  ("policy: not the table's") rather than with the identity refusal and its pointer to `docs/b4_archive_reverification.md` that the
  batch and gate verifiers give. The refusal is by name and nothing is written, which is the contract; naming the identity first would
  be a one-line reorder in `verify_gonogo_dir` — not necessary for this unit and not made, left to the owner.
- **K9 under the new stimulus is a different estimand** (`docs/b4_architecture.md` §9.3 clause 7): the comparison set and the two
  applicabilities are unchanged, but the per-address coverage of `ff_srval` / `sr_kind` under a slice-wide SR is not the quantity
  `b4-sim-4` measured under per-element SR patterns. No v0.3.0 coverage value exists yet; none is predicted here; the `b4-sim-4`
  record is not re-decided.
- **Data influence (§7.2).** The two probabilities (CE 1/2, SR 1/4), the broadcast and the draw order were fixed by the owner's ruling
  before anything was drawn; SR 1/4 equals the per-element SR rate of task-v0.1 / v0.2 at the slice level; CE 1/2 is the uniform
  choice for one control bit. No K9 value, Ω − R value, curve or per-address record of any archive was read in choosing them, and the
  unit's tests use the already-exposed seeds of §9.2 only.
- **A design note on the twin test.** `test_b4_ff_model.SliceWideControls` is a reference implementation of the slice-wide semantics
  written in the test (one control bit per step, applied to every element through the model's own decode and flags), compared with
  the formal model on sampled configurations and the task's own stimuli (360 traces equal) and shown to part exactly on a per-element
  vector. It proves the model needs no change for task-v0.3; it is a statement about the model, not about silicon.
- **Nothing of the carrier moved.** The carrier's `STEP_IN` packing and `realisable` rule are exercised read-only by
  `test_b4_landscape…carrier_mapping` (every task-v0.3 step realisable; the word round-trips); `host/b4carrier_*`, `rtl/b4`, `tb/b4`
  are byte-identical to `bf17574`.

## 5. What this unit does not do

No board was powered; no production run, seed derivation, smoke, exploration or gate of any production label; no change to a
hypothesis, a threshold number, a statistic, an operator, an archive, a receipt, a verdict or a pinned surface; no RTL, no 2d, no
routing; no push, no merge. `b4-sim-5`'s derivation and execution need their own execution plan and ruling; `b4-gate-2` stays a
reserved name; a go of `b4-sim-5` would authorise nothing by itself.

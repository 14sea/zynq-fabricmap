# B4 — the execution plan of the exploration `b4-sim-5` (DRAFT v0.1, documents only, 2026-10-27)

> **Authorisation.** The owner's review of `e20e12b` (2026-10-27, PASS: the task-v0.3 revision unit accepted and closed), section 4: the
> next bounded work is "the `b4-sim-5` execution plan as a complete documents-only unit — the accepted method, the fixed S = 32 policy, a
> concrete candidate execution HEAD / baseline, the deadline and resource estimate, the input and registry checks, the one-attempt stop and
> retention rules, the fresh verification and the archive / decision publication sequence; choosing no new probability, threshold or
> scientific rule; submitted once." This unit writes the plan and takes a read-only inventory (`evidence/b4/unit_sim5_plan_2026_10_27/inventory.py`,
> output `inventory.txt`: reads of committed files, `git` state and the tool's own constants; `b4_seeds.master_seed` / `pair_seeds` never
> called). **It does not execute the exploration, derive or print any seed, run any pre-flight, smoke, mechanics or model batch, change any
> program, table, threshold, hypothesis or archive, build RTL, touch a board, push or merge.** The execution itself remains a separate, last,
> independent authorisation (section 5) naming the **execution HEAD** and the **deadline** (and the date, if the ruling chooses to name one).
> Every number below that describes the run is an estimate from the archived `b4-sim-4` run (S = 32, protocol v0.2.0, 2026-10-21) on this
> host, the only production-shaped S = 32 run of the identity-bearing tool; **nothing here predicts the exploration's outcome or the policy's
> decision.** The precedent this plan follows is `docs/b4_sim4_execution_plan.md` (v0.1.1, executed once); where v0.3.0 differs from v0.2.0
> (the slice-wide stimulus rule and its place in the identity, the consumed `b4-sim-4`, the pooled exclusion, `p_max_go` in place of `α_go`,
> the existing go / no-go namespace, the policy-shape refusal of the old decision record), the difference is stated here and nowhere assumed.

## 0. Status index

| section | fixed | estimated | unresolved / for the owner |
|---|---|---|---|
| 1 the run's fixed conditions | S = 32, the label, the method of v0.3.0 at the accepted tool baseline `e20e12b`, task-v0.3 (the slice-wide CE ½ / SR ¼ stimulus), K9 (b′) judged with (b) carried, the §9.4 row for `b4-sim-5` (B_go = 64, p ≤ `p_max_go` = 0.20 with positives > negatives, all seven conditional medians ≥ 0.50, every planned pair complete), the soft-deadline policy, the two commands | the wall time, the disk, the archive and verification costs | the execution HEAD and the deadline value (3 600 s recommended), named by the execution ruling; the branch the run happens on (proposed in 1.2); the date, if the ruling names one |
| 2 the start, the operator's obligations and the evidence contract | what the tool enforces; what the operator must check and when to stop; what the run writes and keeps | — | the execution HEAD (named by the ruling) |
| 3 the result paths | refused / init_failed / abrupt termination / invalid / incomplete / complete for the batch; refused / no_decision / go / no-go for the policy; the consumption of the label in every row; one attempt, no retry, no replacement label | — | what follows a no-go or a no decision (the owner's, never automatic); the adjudication of an uncertain exposure |
| 4 the known records | the archived `b4-sim-3`, `b4-gate-1` (v0.1.16, task-v0.1) and `b4-sim-4` (v0.2.0, task-v0.2) values at B = 64 and for K9, stated as records; the v0.3.0 mechanics fixture stated as a fixture | — | nothing: no outcome is predicted |
| 5 acceptance | the tool's outputs, the fresh-process verifications, the commits and the Git-blob checks, in the order the clean-tree rule of the policy tool forces | — | the execution authorisation |
| 6 the identity and the old archives | the v0.3.0 verifiers refuse the three older archives by name (the old decision record first at its policy shape); `b4-sim-5`'s archive carries the v0.3.0 identity | — | nothing |
| 7 what follows | a go → `b4-gate-2` needs its own plan and ruling; a no-go → stop; no automatic successor | — | the owner's rulings |

## 1. The fixed execution conditions

| item | value | source |
|---|---|---|
| label | **`b4-sim-5`** — the exploration label of v0.3.0, a reserved name of which no value exists (`b4_seeds.EXPLORATION_LABEL`, `b4_thresholds.THRESHOLDS["anchor"]["exploration_label"]`); the harness refuses `b4-sim-1` / `b4-sim-2` (retired) and `b4-sim-3` / `b4-gate-1` / `b4-sim-4` (consumed) before any tree is read (`check_label_not_retired`, `RetiredLabelRefusal` / `ConsumedLabelRefusal`); a gate label is refused by the exploration CLI (mode `exploration` only) | `docs/b4_architecture.md` §9.2; `b4_seeds.py`; `b4_sim.preflight` |
| S | **32**, planned — never the number completed (§9.1); the policy's precondition is `count == 32` exactly (`THRESHOLDS["gonogo"]["S"]`) | §9.4; `b4_gonogo.decide` |
| method | protocol **v0.3.0** as accepted at **`e20e12b`** (the owner's PASS of 2026-10-27): `b4/IMPORT.json` 59 entries (sha256 `9de52e257e2b5c733118b097ffdb5ba69b941726b815bace302a6d1d8eecf02b`), **`protocol_sha256 = 5bba53c78d08f3ad32e41a90ef37d2639ea584e97fbf74996d941cec4fe14e7f`** (`python3 -B b4/host/b4_protocol.py`; `architecture_revision` v0.3.0 informational, excluded from the digest); **unchanged by this unit and by the closure commit `0a4cba3`** — no byte under `b4/` moves (`git diff --stat e20e12b HEAD -- b4/` empty at this inventory) | `b4_protocol.py`; `inventory.txt` |
| model, task, engine, controls | hypothesis v0.3 (`59948f9b…`), the certificate (`c69e419f…`), **task-v0.3** (§7.2: the planted flip-flop target T-i exactly as task-v0.2 — `storage_kind` fixed to flip-flop, the other 20 bits drawn once by `Rng((landscape_seed ^ 0x54415247) & 0xffffffff).uniform(1 << 20)`, the base included, nothing redrawn; **the stimulus rule revised**: per set step ONE slice-wide CE value, high with probability ½ (`uniform(2) == 0`), ONE slice-wide SR value, high with probability ¼ (`uniform(4) == 0`), the two draws independent, each broadcast over the eight elements as `0xFF` / `0x00`; `d` a per-element uniform 8-bit draw; the draw order ce, sr, d; K = 6 / 8, two level steps, the mask, the weights and the ceilings 64 / 80 as task-v0.2; the shape held on every task record by `stimulus_findings` and in the offline reconstruction; two setup observations per pair; None scores nothing; the `PublicTask` without the seed, `g*` or the private record), the (μ, λ) = (4, 8) engine, the controls of §8 — as accepted at `e20e12b` | §7.1, §7.2; `THRESHOLDS["task"]`; `b4_landscape.py` |
| thresholds and the judged K9 | `b4_thresholds.THRESHOLDS` ("section 9") — **unchanged by this unit**; K9's judged estimand **(b′)** `conditional_sr_driven` (`ff_srval` / `sr_kind` under SR-driven backgrounds, `sr_tied_low` pairs named and removed from the denominator; `sr_mode = tied_low` at both endpoints of the pair, as `b4_k9.REASON_SR_TIED_LOW` says — the model's endpoint semantics, not the stimulus draw) with the all-panel **(b)** carried beside it as a description, recomputed from the same retained grids — both recorded, both recomputable offline, never averaged across semantics | §9 K9; §9.3 clauses 6 and 7; `b4_k9.py` |
| the policy | **§9.4, the v0.3.0 row for `b4-sim-5`**, as the table holds it (`THRESHOLDS["gonogo"]`, `applies_to = "b4-sim-5 (protocol v0.3.0); b4-sim-4 was decided no-go under v0.2.0 and is not re-decided"`): precondition every planned pair complete, the batch `complete`, S = 32, the archive verifying clean under this method; statistic 1 the one-sided exact sign test on **Ω − R at B_go = 64** (ties excluded from n, counted and reported), **positives > negatives and p ≤ `p_max_go` = 0.20** (**an engineering cost threshold on the sign test's p, not the α of a formal scientific test** — the table's `p_max_go_standing`); statistic 2 **all seven (b′) medians ≥ 0.50**; **go** iff both; **no-go** otherwise; **no decision** when the precondition fails; every budget's Ω − R record carried in full, no other budget picked afterwards; **a cost policy — not a significance result, not a gate verdict, not an authorisation, never a scientific impossibility; no automatic successor.** Every number is the v0.2.0 number; the key `p_max_go` replaced `alpha_go` by name only | §9.4; `THRESHOLDS["gonogo"]`; `b4_gonogo.py` |
| the derivation | the master `sha256("b4-sim-5|" + HYPOTHESIS_SHA256)[:4]` and the 32 pairs by B2's `pair_seeds` copy against the **pooled exclusion as read at the pre-flight** — at this inventory **2 690 values**: the 38 historical sources, B4's exposed values, the exposure receipt (`68764bbc1a51ec25…`, 66 values) and the registry's three archived sets (`b4-sim-3` 65 values, `b4-gate-1` 401 values, **`b4-sim-4` 65 values**) — **performed in memory by the harness at `Batch.init`, after the pre-flight and the exclusive creation of the output directory, and nowhere else; not here** | §9.2; `b4_seeds.master_seed` / `pair_seeds`; `b4_sim.Batch.init` |
| the commands | (1) `python3 -B b4/host/b4_sim.py --label b4-sim-5 --seeds 32 --deadline-s 3600` from the repository root on the clean committed tree at the execution HEAD; the batch under `evidence/b4/sim/b4-sim-5_<UTC>/`. (2) **After the archive is committed** (section 5, step 3 — the policy CLI refuses a tree that is not clean, and an uncommitted archive is an untracked entry): `python3 -B b4/host/b4_gonogo.py decide evidence/b4/sim/b4-sim-5_<UTC>`; the decision under `evidence/b4/gonogo/b4-sim-5_<UTC>/` (`gonogo.json`, `gonogo.md`); **the namespace `evidence/b4/gonogo/` exists at this inventory and holds exactly `b4-sim-4_20261021T065857Z`** — the tool adds a sibling directory and refuses one that already exists; the actual `out` / `gonogo_out` paths the tools return are the ones used | `b4_sim.main`; `b4_gonogo.main` / `write_decision` |
| deadline | **3 600 s recommended; the execution ruling names the value.** The SOFT monotonic policy unchanged: counted from the pre-flight, checked before and after every target observation, arm, replay, snapshot, K9 pair, K10 unit, statistics unit and before every finalisation unit (after the batch's own deep verification included); a started unit never interrupted; an expiry makes the batch `incomplete` with everything on disk. The deadline is part of the authorisation, not an operator-selectable parameter; the policy's `decide` has no deadline (it runs nothing) | `b4_deadline`; `b4_sim` docstring |
| one attempt | **one batch under this label, run once**: no smoke, pre-flight, mechanics or dry run before it; no retry, redraw, resume with a redraw, or replacement label after it, whatever row of section 3 applies; the owner's substantive bounds of 2026-10-21 (archived `evidence/b4/unit_sim4_execution_2026_10_21/owner_clarification_2026_10_21.txt`) carried unchanged: the fixed method and thresholds, S = 32, the deadline, one batch, no prior seed draw or smoke, stop on any anomaly without a redraw, every raw record kept, the verifications and the source binding | the owner's ruling of 2026-10-21 and the review of 2026-10-27 §4 |
| one worker; nothing else in the repository during the run | the harness holds HEAD, every input digest (the root inputs, the hypothesis's repository and external sources, the 38 exclusion sources, the receipt), every tool digest and the registry snapshot at every pair's end and at the end (`input_drift` → `invalid`); at the end the working tree must carry nothing but the batch's output | `b4_sim.Batch.hold_inputs` / `hold_tree` |

### 1.1 Costs — every number an estimate from the `b4-sim-4` run (v0.2.0) on this host; no v0.3.0 production-shaped batch has been timed

| cost | measured | `b4-sim-5` estimated | note |
|---|---|---|---|
| the batch, including its own deep self-verification | `b4-sim-4` (S = 32, v0.2.0, 2026-10-21): `elapsed_s` **199.256** of 3 600 (52 779 deadline checks), 771 files, 200 674 002 bytes; `b4-sim-3` (v0.1.16): 209.702 s, 643 files; `b4-gate-1` (S = 200): 1 372.077 s, ≈ 6.9 s per pair | **≈ 3–10 min** | v0.3.0 changes the stimulus *draw* (three draws per set step instead of ten) and the shape check on the task records, not the number of observations per pair (two target observations and ≈ 1 827 arm observations: six arms at B + 2 = 258 and F at B + 23 = 279) nor the self-verification's work; the S = 32 mechanics fixture `complete_32` of the task-v0.3 unit (`evidence/b4/unit_task_v03_2026_10_27/e2e_v3/complete_32/`, label `b4-mech-5`, 32 explicit pairs, deadline 7 200 s) exercised exactly this path under the v0.3.0 identity but its wall time is not a record of this plan; the range is an uncertainty, not a bound |
| the deadline margin | `b4-sim-4`: 199 s against 3 600 s (≈ 18×) | **not proved**: 3 600 s against ≈ 3–10 min is ≈ 6–18× by extrapolation | an expiry is `incomplete` with everything on disk, never a loss |
| one fresh-process batch verification (`b4_sim_verify.py`, deep: the setup reconstructed from the kept records — under v0.3.0 the stimulus shape of every task record checked by `stimulus_findings` — the two target records checked (the retained grids, provenance and digests) and the task rebuilt from them (the target observations are **not** re-executed through a replay port), every arm re-executed against the ledger's recorded observations and re-audited — never re-observed on the fabric — K7's prefixes, K9 / K10 and the summary recomputed from the retained grids) | **74 s** for `b4-sim-4` (06:57:15Z → 06:58:29Z); 79 s for `b4-sim-3`; the owner's independent run 75.596 s | ≈ 1–3 min | before commit 1 (section 5) |
| the decision (`b4_gonogo.py decide`), including its in-process self-validation (the batch re-verified deep, the decision recomputed) | **74 s** for `b4-sim-4` (06:58:57Z → 07:00:11Z) | ≈ 1–3 min | after commit 1; runs nothing on the model but the replay |
| one fresh-process decision verification (`b4_gonogo.py verify`, deep: the record's shape against the v0.3.0 table — the `policy` block, `p_max_go` — then the identity, the batch re-verified, the decision recomputed, the markdown re-rendered) | **74 s** for `b4-sim-4` (07:00:17Z → 07:01:31Z); the owner's independent run 123.389 s | ≈ 1–3 min | before commit 2; the batch's third deep pass is inherent to the verifier, not a second round of record |
| disk, the working tree | 771 files / 200 674 002 bytes at S = 32 (v0.2.0) | **≈ 770 files / ≈ 200 MB**, plus 2 files for the decision | `/home/test` had 483.4 GB free at this inventory (the whole repository's `.git` grew by the order of 200 MB with `b4-sim-4`) |
| wall time, the whole executed unit | `b4-sim-4`: **≈ 8.1 min** from the batch start to the second blob check (06:53:39Z → 07:01:47Z), plus the unit record | **≈ 10–25 min** of compute, plus three commits | the computer must not sleep during the batch (a monotonic-clock jump across a suspend has been seen to count against a soft deadline on this host); keeping it awake *outside* a running deadline-bound batch is a suggestion, not a bound (the owner's clarification of 2026-10-21) |

### 1.2 The branch and the two refs, kept apart

The v0.3.0 tool exists only on **`b4-task-v03`** (`e20e12b` and its successors: the closure `0a4cba3`, this plan's commit); `main` is `a243ee8`
and carries the v0.1.16 tool; `b4-protocol-v2` / `b4-sim-4-execution` carry the v0.2.0 tool. **Every one of those older trees accepts the
syntax `b4-sim-5`** (`^b4-sim-[1-9][0-9]*$`; none of their retired or consumed lists holds it) — a run there would not be refused by the label:
`main` has no identity, no task-v0.2 / v0.3 and no policy; the v0.2.0 trees would derive the label's seeds under the per-element stimulus and
record the identity `2f096d4a…`, consuming the name under the wrong method. What prevents it is the operator's exact-HEAD, `b4/`-bytes and
protocol-digest checks of 2.3, not a label refusal; the run cannot happen on `main` as the v0.3.0 method without a merge, and **a merge is not
proposed here** (its timing is the owner's, as it was for `b4-prework`). The proposal: the execution HEAD is a commit on `b4-task-v03`'s line
**after the owner's PASS of this plan** (this plan's closure commit, or the commit the ruling names), the run performed on a branch
**`b4-sim-5-execution`** created from that HEAD, so that the archive commits sit on their own branch exactly as `b4-gate-1-execution` and
`b4-sim-4-execution` did. **Two refs:** `e20e12b` is the **accepted tool baseline** (the engineering PASS; the tool bytes the operator's stop
holds the execution tree to); the **execution HEAD** is whatever commit the ruling names — it will differ (the closure and this plan come after
`e20e12b`), and the manifest records it because that is what it reads. Both are stated in the unit README of the executed unit; neither is
substituted for the other. The registry on that line holds the three archived sets (`b4-sim-3`, `b4-gate-1`, `b4-sim-4`: `580c0e5` is an
ancestor of `e20e12b` through `a243ee8`'s successors on this line — the inventory reads three entries), which is why the pooled exclusion is
2 690 and not `main`'s 2 224 or `b4-protocol-v2`'s 2 625.

**Proposed for the execution ruling to name:** the execution HEAD as above (concretely, this plan's own commit or the closure commit after
the owner's PASS of it, on `b4-task-v03`); the deadline **3 600 s**; the date only if the owner wishes — per the clarification of 2026-10-21
the calendar date, the branch name and the number of commits are organisational suggestions, not gates; the owner's review of 2026-10-27
imposes "no date gate, branch name or commit count". The branch name `b4-sim-5-execution` is likewise a proposal.

## 2. The start — what the tool enforces, what the operator must do, and the evidence contract

### 2.1 The order of events inside the tool (`b4_sim.run_batch` → `preflight` → `create_out_dir` → `Batch.init` → the pairs → `finish`)

1. **The pre-flight writes nothing** (`refused`, exit 2, no output directory): the label grammar `b4-sim-<n>`; the retired and consumed labels
   refused before any tree is read; S and the deadline positive ints; **the protocol identity buildable from the code tree's trusted inventory**
   (`bp.identity(REPO_ROOT)`: every `b4/host` module and `b4/schemas` file at its `b4/IMPORT.json` digest — an `IdentityRefusal` is a refusal;
   the tool checks *buildable*, not *equal to the authorised digest*, which is the operator's check of 2.3); the clean tree (`git status
   --porcelain --untracked-files=all` empty, no override); the formal hypothesis (not a fixture, at its pinned digest), the mapping, the truth
   fabric; every exclusion source readable, the receipt at its pinned digest; the output directory `evidence/b4/sim/b4-sim-5_<UTC>` not existing
   and the namespace chain free of symlinks.
2. The output directory is created exclusively and the chain re-checked.
3. **`Batch.init` derives the master and the 32 pairs in memory**, **then writes `seeds.json` as the first file** (the anchor with the label beside
   it, the master, the pairs, the exclusion as pooled — the 38 sources, B4's exposed values, the registry snapshot of **three** sets, the receipt,
   the pooled total), **then `manifest.json`** (HEAD, **the protocol identity and `protocol_sha256`**, the code root, every input digest, the
   external sources by absolute path and digest, the tool digests, the registry snapshot as read, the constants — **under v0.3.0 including the
   `stimulus` block: the rule, `ce_high_one_in` 2, `sr_high_one_in` 4, the broadcast, the model input contract** — and the thresholds table),
   **and only then the first observation**. The guarantee is persistence before the first observation, not before the derivation; a failure
   between the derivation and the write is section 3's `init_failed`.
4. **Per pair, before any arm, the target setup** (§7.1): `task_setup.json` (the pair identity, `g*` by the fixed rule, the two stimulus
   digests — **the two stimuli drawn by the task-v0.3 rule of §7.2**; status `in_progress`) → the search-stimulus observation of `g*` through the
   dedicated TARGET port, phase `target`, **its return saved at once** — as `target_search.json` when it is a valid target observation, as
   `target_search.QUARANTINE.json` (the object the port returned, raw, with the findings, the phase, `g*`, the stimulus digest, the expected
   source identity and the digest of the kept projection) when it is not → the holdout-stimulus observation, phase `target_holdout`, saved the
   same way → `task.json` (the `PublicTask`, its digest, the setup files' digests; **its stimuli validated against the v0.3.0 shape by
   `stimulus_findings` — a stimulus of another shape is a schema finding, never scored**); the planned record carries the setup state
   (`in_progress` / `partial` / `complete` / `invalid`), the **durable ordered prefix** `task_prefix` (0–4) and `task_quarantine` (the phase whose
   return was quarantined, or null). Then the seven arms in the fixed order R → F → O → X → D → Ω → A0 on one worker, each `RunResult` written
   exclusively before its audit (a malformed one quarantined raw), then the controls, K7, K9 (both applicabilities), K10, the curves and the
   pair index; the inputs, the tool digests and the registry held at every pair's end.
5. The statistics (every budget's deltas, the K5 scan, the K9 summaries under both applicabilities, K10), the final holds; **`reconcile_setup`**
   (the disk is the authority for every pair's setup state, prefix and quarantined phase); the archive-wide self-verification; the report.

### 2.2 What the tool enforces and what it does not

| the tool enforces | the operator must do (not checked by the tool) |
|---|---|
| a clean tree at the pre-flight; the label grammar and the retired / consumed refusals; S and the deadline as given; the identity buildable from the inventory and recorded in the manifest; the formal inputs at their pinned digests; the receipt at its pinned digest; the snapshot of the registry *it reads* and its hold during the batch; the freezing order; the exclusive writes; the setup persistence call by call and the quarantine of a refused return; the v0.3.0 stimulus shape on every task record; the stop rules; the self-verification | **no smoke test, no mechanics batch, no dry run, no `b4-mech-*` fixture under this tree's `evidence/b4/sim/` before the production call** (a fixture batch archived there would enter the registry before the draw; the task-v0.3 unit's fixtures live in hermetic roots outside the tree and in `evidence/b4/unit_task_v03_2026_10_27/e2e_v3*/` as records, not under `evidence/b4/sim/`); **no derivation or print of any seed by any other means, before or during** — the operator's checks below are reads of committed files, `git` state and the tool's constants only (the inventory script of this unit is such a read); the computer kept awake during the batch; nothing else run in the repository; the stdout / stderr / exit status of each command captured to files **outside the tree** during the run and copied into the unit directory afterwards |
| that HEAD does not move during the batch (`input_drift`) | **that the HEAD is the one the execution ruling named** — the tool records whatever HEAD it finds |
| that the identity can be built from the tree | **that `protocol_sha256` is `5bba53c7…`**, the accepted baseline's — the tool does not know the authorised digest; a tree whose inventory is self-consistent but different (a v0.2.0 tree, for one) would run and record a different identity under this label |
| that the registry it read does not change during the batch | **that the registry it will read is exactly the three archived sets** the authorisation expects — the tool snapshots and holds what it reads and would silently pool a newly archived set (a fixture, an aborted earlier attempt) |
| the policy CLI: a clean tree, an exploration label, an archive of this identity, a validating report, the namespace, the decision directory not existing | **that the archive was committed before `decide`** (section 5, step 3), that the batch directory named is the one the run wrote, and that the decision is read from the documents on disk, never from the exit code |

### 2.3 The operator's stop (an explicit rule of this plan)

Before the batch command the operator compares — by reading committed files, `git` and the tool's constants, never by deriving or printing a
seed; `evidence/b4/unit_sim5_plan_2026_10_27/inventory.py` re-run and its output kept is sufficient for every row but the first and the last
two — the actual state with the execution authorisation, and **stops without running if any of these differs**:

| check | the expected value (this inventory, 2026-10-27) | how |
|---|---|---|
| HEAD | the execution HEAD the ruling names (on `b4-task-v03`'s line; the branch `b4-sim-5-execution` created from it) | `git rev-parse HEAD` |
| clean tree | `git status --porcelain --untracked-files=all` empty | `git status` |
| tool bytes | every file under `b4/` byte-identical to the accepted baseline **`e20e12b`** (`git diff --stat e20e12b HEAD -- b4/` empty); `b4/IMPORT.json` 59 entries, sha256 `9de52e257e2b5c733118b097ffdb5ba69b941726b815bace302a6d1d8eecf02b`, file / base / copied-function digests all equal, no untabled file (`evidence/b4/unit_2b4a_repair_2026_10_18/import_check.py`) | git; `import_check.py` |
| protocol identity | `protocol_sha256` **`5bba53c78d08f3ad32e41a90ef37d2639ea584e97fbf74996d941cec4fe14e7f`**; the identity's `task` component `version task-v0.3`, `ce_high_one_in 2`, `sr_high_one_in 4`, `broadcast {0: 0, 1: 255}` | `python3 -B b4/host/b4_protocol.py` |
| the task constants | `b4_landscape.TASK_VERSION = "task-v0.3"`, `CE_HIGH_ONE_IN = 2`, `SR_HIGH_ONE_IN = 4`, `BROADCAST = {0: 0x00, 1: 0xFF}`; the table's `task.version task-v0.3`, `task.stimulus.draw_order "ce, sr, d"`, salt 1413567047, two setup observations per pair, ceilings 64 / 80 | the inventory |
| the labels | exploration `b4-sim-5`, gate `b4-gate-2`; retired `b4-sim-1`, `b4-sim-2`; consumed exactly `b4-gate-1`, `b4-sim-3`, `b4-sim-4` (`b4_seeds` and the table agree) | the inventory |
| the policy | S 32, B_go 64, **`p_max_go` 0.2** (no `alpha_go` key), K9 min 0.5, `applies_to` naming `b4-sim-5` | the inventory |
| exposure receipt | sha256 `68764bbc1a51ec2506bf9d9bcbb3f55f88f3d7642b5eb46c6fd3dd39f8dae146`, **66** values, `pinned_receipt_count()` 66 | `b4_seeds.read_exposure_receipt` |
| registry | **exactly three** run directories: `b4-sim-3_20261019T121833Z` (`seeds`, `1a0d1e7b91132ed6…`, 65 values), `b4-gate-1_20261020T102526Z` (`seeds`, `785e76988d4e6ec4…`, 401 values) and `b4-sim-4_20261021T065339Z` (`seeds`, `ae179c376282ae61…`, 65 values); nothing else under `evidence/b4/sim/`; no `b4-sim-5_*` directory | `b4_seeds.sim_registry` |
| pooled exclusion | **2 690** values, 38 historical sources | `len(bs.load_exclusion_set().values)` |
| the policy namespace | `evidence/b4/gonogo/` holding exactly `b4-sim-4_20261021T065857Z` (the v0.2.0 no-go of record), or additionally only what a ruling put there; no `b4-sim-5_*` directory | `ls` |
| disk | ≥ 2 GB free | `df` |
| no competing process | no other `b4_sim` / `b4_gonogo` / `b4_gate` process on the host | `pgrep -af b4_` read by a human (the pattern matches its own shell; a self-match is not a competing process) |
| date | within the ruling, if the ruling names one | `date -u` |

A difference is reported to the owner; the run does not start; nothing is "fixed" to make it match.

### 2.4 What the run writes, and keeps whatever happens

`seeds.json` → `manifest.json` → per pair `task_setup.json` → `target_search.json` *or* `target_search.QUARANTINE.json` → `target_holdout.json`
*or* `target_holdout.QUARANTINE.json` → `task.json` → the seven arm results (or their `arm_<role>.result.QUARANTINE.json`) each before its
audit, the audits, the controls, `k7.json`, `k9.json`, `k10.json`, `curves.json`, `index.json` → the statistics → `sim_report.json` (status;
the identity; the archive index; the pooled summary only when complete and clean; the self-validation) and, when the batch did not
complete, `STOPPED.json` naming the kind, the pair, the stage and the whole planned list with every pair's setup state, prefix and
quarantined phase. Then, after commit 1, the decision directory `gonogo.json` + `gonogo.md`. **Every target record — a valid one as the
projection the port trace is kept as (the complete `q_grid`, the provenance and the commitments; not every field of the port object), a refused
one as the quarantined original returned object; neither proves the source's truth — every seed, every partial, every quarantine and every
stop record is kept**; nothing is redrawn, replaced, filled in, narrowed or deleted; the two commands' stdout / stderr / exit status are kept
beside them. **Retention is unconditional**: a refused, failed, truncated, invalid, incomplete or no-go run is committed and kept exactly as a
complete one is (section 5, step 1).

## 3. The result paths — separate dispositions, none automatic; one attempt

### 3.1 The batch (`b4_sim.py`; exit codes 0 complete, 1 invalid, 2 refused / init failed, 3 incomplete — captured, never deciding)

| what happened | the record on disk | disposition | what is NOT done |
|---|---|---|---|
| **pre-flight refusal** (`refused`, exit 2) | no output directory; the stdout / stderr / exit captured | report the named reason to the owner; the label is **not** consumed (no derivation ran) — the owner decides the next step | no silent fix of the tree, the inventory or the inputs and re-run |
| **initialisation failure** (`init_failed`, exit 2: an exception after the directory exists) | `INIT_FAILED.json` (`label`, `seeds_derived`, `reason`), possibly `seeds.json`, no or a partial `manifest.json`, no report, no `STOPPED.json` | keep everything; inventory which expected files are absent; **stop and report** | **no retry under the same label, no release of the label**: `seeds_derived` is set from whether a `seeds.json` write was recorded and **`false` does not prove that no in-memory derivation occurred**; the label is **consumed or exposure-uncertain pending the owner's adjudication** (values excluded by value; a label never reused on an assumption) |
| **abrupt termination** (the process or the machine dies; no return value) | the durable prefix only: whatever was written exclusively before the event — `seeds.json`, `manifest.json`, the pairs' files up to and including a setup file or a quarantine, possibly a `.part`; no `STOPPED.json`, no report; `reconcile_setup` did not run | keep everything; inventory the files present against the plan (`manifest.json` and the pair indexes name what should exist; a pair's setup files are read as the ordered prefix they are); **stop and report**; the archive verifier is run for the record but its findings on a truncated archive are expected and are not a verdict | no manufactured report, no re-run; the label consumed |
| **`invalid`** (exit 1) — the kinds: `target_invalid` (a DOMAIN or `SourceRefusal` at a target observation; **a returned object that is not a valid target observation — a None anywhere in the grid, a cell that is not the int 0 / 1, a malformed shape or provenance, a source identity that is not the expected one — kept raw in the phase's QUARANTINE file, the pair `invalid` with `task_quarantine` naming the phase**; a drift between the two observations; a third port call); `result_malformed`; a control failure; a replay or recompute finding; a K10 `comparable = False`; a schema finding (**under v0.3.0 including a task record whose stimulus is not of the slice-wide shape**); `input_drift`; `unexpected_exception`; `self_validation` | `STOPPED.json` with the kind, the pair, the stage; the report with status invalid; the quarantine files; every pair's durable prefix | a tool / source / replay / control contract break, never a landscape failure: archived (section 5's commit 1 and the fresh verification still apply, for the record); **the policy's precondition is not met → `no_decision`**; the finding named; the unit halts and reports | not re-run under the same label; the next step is the owner's (a repair unit, then a ruling on a new label — `b4-sim-5` is consumed by its records) |
| **`incomplete`** (exit 3: the deadline, an external interrupt) — including an interrupt landing **after a quarantine's durable write and before the in-memory state caught up**: `reconcile_setup` rebuilds the pair's `invalid` state and quarantined phase from the file on disk while the batch's stop carries the interrupt | `STOPPED.json`, every pair's work and prefix, the report with status incomplete | unfinished work, never a result: archived; the unexecuted and the partial pairs named; **`no_decision`** | whether the unexecuted runs are resumed is decided separately (§9.1) and never under this label with a redraw; no partial summary read as a result; no automatic re-run |
| **`complete`** (exit 0; the self-verification clean) | `sim_report.json` complete with the pooled summary: every budget's deltas (Ω − R among them), the K5 scan, K9 under both applicabilities with `judged_estimand = conditional_sr_driven`, K10, the K7 medians | the fresh-process verification, commit 1, then the decision (3.2) | no decision is read from the summary by hand; no budget other than B = 64 is picked for the policy; no threshold or policy number touched |

### 3.2 The decision (`b4_gonogo.py decide`; exit codes 0 go / no-go, 2 refused, 3 no decision; `self_validation` non-empty → no decision)

| what happened | the record on disk | disposition | what is NOT done |
|---|---|---|---|
| **refused** (exit 2: the tree not clean — an uncommitted archive is an untracked entry — a label that is not an exploration label, an archive of another or no identity, a report that does not validate, a batch directory not directly under `evidence/b4/sim/`, the decision directory existing) | nothing written | report the named reason; if the cause is an uncommitted archive, commit 1 of section 5 first and run `decide` again — that is the ordering this plan fixes, not a fix of evidence; any other cause is reported to the owner | no edit of the archive; no decision by hand |
| **`no_decision`** (exit 3: the precondition unmet — the batch not `complete`, S ≠ 32, a pair not complete, no summary — a summary contract finding, or the record's own self-validation finding its evidence inconsistent) | `gonogo.json` with `decision = no_decision`, `statistic_1` / `statistic_2` null, the reason; `gonogo.md` | stop and report; the batch's own row of 3.1 governs what follows | no re-decision after an edit; no second exploration on this plan's authority |
| **`go`** (exit 0, `formal = true`) | `gonogo.json` with both statistics (`p_le_p_max_go`, `p_max_go` 0.2, `p_max_go_standing`), every budget's Ω − R record, the policy, the identity, the evidence binding (the archive's report / seeds / manifest digests); `gonogo.md` | a **cost-policy go**: the fixed certificate grouping with the fixed operator showed a positive signal at one budget and the conditional coverage was not below threshold — a proxy, good enough to spend the gate's cost; archived and committed as section 5 says; **`b4-gate-2` needs its own execution plan and its own execution ruling** (section 7) | not a prediction of the gate, not a gate result, not an authorisation of anything; no S change, no budget re-pick, no second statistic added |
| **`no-go`** (exit 0, `formal = true`) | the same record with the reasons (which of positives > negatives, p ≤ the cost threshold `p_max_go` 0.2, the seven medians failed) | **the exploration is archived as a result; stop.** What follows — a different grouping shape, a different operator, a different stimulus, or stopping — needs its own argument and its own ruling; **a no-go is a cost-policy stop, not a scientific negative conclusion, not evidence about the fabric and not a statement that the class is indistinguishable** | **no tuning, no automatic retry, no replacement seed or label, no second exploration, no next protocol version** on this plan's authority; nothing of the carrier, the board or the routing line moves on the strength of a no-go |

**The CLI exit codes never decide anything.** Both are captured; the documents on disk and their statuses decide which row applies — a `0`
from the policy tool is a decision written (go *or* no-go), and an absent document is a row of its own.

**The label, in every row.** `b4-sim-5`'s master and pairs are in the registry and in the pooled exclusion of every later derivation as soon
as `seeds.json` exists, and treated as exposed even when it does not (the `init_failed` row): a refused pre-flight is the only row that leaves
the label unconsumed. A stopped, invalid, incomplete, no-decision or no-go batch does not free its label, and no replacement label is reserved
by this plan — `b4-sim-6` is a name nobody has proposed. **Two no-gos in a row (`b4-sim-4`, then possibly `b4-sim-5`) would not be a stronger
stop or a weaker one**: each is the cost policy's reading of its own archive under its own method, and the §9.4 row says what each licenses —
nothing automatic.

## 4. The known records, as records — not as a prediction

Three archives exist. `b4-sim-3` and `b4-gate-1` are of **protocol v0.1.16 under task-v0.1 and the old all-panel K9 applicability**;
`b4-sim-4` is of **protocol v0.2.0 under task-v0.2** (the per-element CE / SR stimulus, which the carrier v2 finding showed unrealisable on one
CE / SR pin per slice). The v0.3.0 verifiers refuse all three by name (section 6). They are stated so that a go, a no-go or a no decision is not
a surprise and not an excuse; nothing here says what `b4-sim-5` will show under task-v0.3, and no number from them sets anything in this plan.

- **Ω − R at B = 64.** `b4-sim-3` (S = 32): positives 10, negatives 12, ties 10, mean −0.219, one-sided sign-test p 0.738. `b4-gate-1`
  (S = 200): positives 56, negatives 95, ties 49, mean −0.49, p 0.9995; negative at every budget. **`b4-sim-4` (S = 32): positives 7, negatives 13,
  ties 12, mean −1.71875, d −0.353, p 0.9423 — the §9.4 policy's no-go of record** (`evidence/b4/gonogo/b4-sim-4_20261021T065857Z`, positive at
  no budget below 192; at B = 192 / 256 the mean is positive with 6 / 6 and 7 / 5 — descriptive, not a second test). Three records with the same
  sign at B = 64 under two tasks; the task is different again now (§7.2), and `b4-sim-4`'s record was the **occasion** of the carrier finding's
  protocol consequence, not a validation of the new rule (`evidence/b4/unit_task_v03_2026_10_27/README.md` §4).
- **K9.** Under the old (b): `ff_srval` median 0.4270833333333333 (`b4-sim-3`) and 0.40625 (`b4-gate-1`) against the configuration-only upper
  bound of 0.5 (the owner's audit of 2026-10-19); `sr_kind` exactly 0.5 in both; `b4-sim-3`'s other five 1.0, `b4-gate-1`'s `sr_mode` 0.96875 and
  its other four 1.0. **`b4-sim-4` under (b′)**: `ff_srval` 0.8125, `sr_kind` 0.875, the other five 1.0 (the policy's precondition met); under (b),
  carried: `ff_srval` 0.40625, `sr_kind` 0.4375, the other five 1.0. Under task-v0.3 nothing has been measured on a production archive: **no
  production / exploration estimate of record of the v0.3.0 coverage exists**. The task-v0.3 unit's mechanics fixture `complete_32`
  (`b4-mech-5`, 32 explicit fixture pairs) decided **no-go, `formal = false`** (positives 0, negatives 0, ties 32, p 1.0; its conditional
  medians `ff_srval` 0.667, `sr_kind` 1.0, `clock_mode` 0.75, `sr_mode` 0.625, the other three 1.0) — fixture values on an explicit schedule:
  the policy's paths exercised, not an estimate, not a finding about Ω − R or coverage, and no ground for tuning (the owner's P3 of 2026-10-27).
- **The latch region** (§7.1's prior): `g*` is never a latch configuration; the search still visits latch candidates whose x5FF elements read
  None and score nothing on 32 of the 64 cells — a low-score region that follows from the prior, not an observation about latches; the new
  comparison gives no evidence about a latch-target task.
- **B\* / N.** No archive had a B\*; the policy does not use B\*, N or the K5 scan — it reads B = 64 alone, named before the run.

**Data influence, disclosed.** The task contract, the conditional estimand, the policy's budget and p threshold were chosen on 2026-10-20 after
the v0.1.16 records (the owner's choices 1–6; the influence table in `evidence/b4/unit_protocol_v2_design_2026_10_20/README.md` §4); the
slice-wide stimulus rule and its two probabilities were fixed by the owner's ruling of 2026-10-27 after `b4-sim-4`'s no-go, on the carrier's
finding (§7.2's disclosure: the ruling's numbers, chosen for realisability, not fitted to any archive). This plan adds no choice informed by
data: its only numbers are the table's.

## 5. Acceptance of the executed unit (when, and only when, the execution is authorised)

The order below is forced by the policy tool's clean-tree rule (the archive must be committed before `decide`) and by the verification rule
the owner chose for `b4-gate-1` and kept for `b4-sim-4` (one fresh-process verification of record before each commit, Git-blob digests after
it, no second full round unless something changed).

1. **The batch's outputs as written**: the archive (`sim_report.json` and everything it indexes, every quarantine and stop record) and the
   captured stdout / stderr / exit status. No file is edited. If 3.1's refusal / initialisation-failure / abrupt-termination row applies, the
   acceptance stops at "keep, inventory, report" and the verification below is run for the record only; an `invalid` or `incomplete` batch is
   still verified, committed and decided (→ `no_decision`) so that the record is complete.
2. **One fresh-process batch verification, before commit 1**: `python3 -B b4/host/b4_sim_verify.py evidence/b4/sim/b4-sim-5_<UTC>` (deep;
   step 0 the identity against the verifier's own inventory; a clean result establishes internal execution / derived-result consistency and
   source binding, **not** the truth of the observation source). Exit code and output kept with a three-line header (HEAD, command, UTC).
3. **Commit 1 — the archive exactly as the tool wrote it, nothing else** (the branch `b4-sim-5-execution`). **After the commit, the committed
   bytes are compared to the verified files by Git-blob digest** (`git ls-tree -r <commit>` against `git hash-object` of every file on disk;
   the `b4-sim-4` unit's `blob_digest_check.py` reused on the one directory); equality recorded; no second deep verification.
4. **The decision**: `python3 -B b4/host/b4_gonogo.py decide evidence/b4/sim/b4-sim-5_<UTC>` on the clean tree at commit 1 (the record's
   `head` is therefore commit 1's hash, not the execution HEAD — both are stated in the unit README; the batch's manifest holds the execution
   HEAD; the decision timestamp need not equal the batch timestamp). Its stdout / stderr / exit captured.
5. **One fresh-process decision verification, before commit 2**: `python3 -B b4/host/b4_gonogo.py verify evidence/b4/gonogo/b4-sim-5_<UTC>`
   (deep). Exit code and output kept with the header.
6. **Commit 2 — the decision directory exactly as written, nothing else**; the Git-blob comparison repeated for it.
7. **Commit 3 — the unit record** `evidence/b4/unit_sim5_execution_<date>/`: the run headers, the captured outputs of both commands, the
   operator's stop (the inventory output and the row-by-row check), the two verification outputs, the two blob comparisons, and the README —
   the identity the manifest recorded (the execution HEAD, `protocol_sha256`, the `stimulus` constants, the tool digests, the receipt, the
   registry snapshot of three sets, the pooled total 2 690), the batch status and deadline record, **the decision and both statistics copied,
   not summarised** (positives / negatives / ties / p / mean / d at B = 64; the seven (b′) medians and the seven (b) medians beside them; every
   budget's Ω − R record), the disposition of section 3, and what was not done. If anything changed between a verification and its commit, the
   reason is recorded and that verification is repeated. The exact count of commits is the tool's requirement only in that the archive is
   committed and the tree clean before `decide`; the rest is the precedent, not a gate.
8. **The execution authorisation is the last, separate, independent gate**: this plan's acceptance runs nothing; a later ruling names the
   execution HEAD and the deadline; the run happens once, on that tree, with no smoke test before it, after the operator's stop of 2.3 found
   no difference.

## 6. The identity and the old archives

`b4-sim-5`'s manifest carries the protocol identity and `protocol_sha256` (§9.5) — under v0.3.0 the `task` component includes the stimulus
rule, `ce_high_one_in`, `sr_high_one_in` and the broadcast; every v0.3.0 verifier, the judge and the policy rebuild the payload from their own
trusted inventory and compare it component by component before reading anything else. An archive of another identity, or of none, is refused
by name and pointed to `docs/b4_archive_reverification.md`: the two v0.1.16 archives (no identity) and the v0.2.0 archive `b4-sim-4` (the
identity `2f096d4a…`, the `task` component named as differing) are therefore re-verified only by that page with their own tool at their
recorded HEADs, never by the v0.3.0 tool. **One qualification carried from that page's §6** (the owner's P3 of 2026-10-27): the go / no-go
*decision-record* verifier validates the record's `policy` block against the current table before it compares the identity, so the v0.2.0
decision record `evidence/b4/gonogo/b4-sim-4_20261021T065857Z` (its block carries `alpha_go`) is refused first as `policy: not the table's`,
without the identity line — safe (nothing is written), disclosed, no runtime change. `b4-sim-5` is verified by the v0.3.0 tool at the execution
HEAD, whose bytes the operator's stop holds equal to `e20e12b`'s. A later method change (a new protocol version, a changed table, a changed
validator) will refuse `b4-sim-5`'s archive by name in its turn; nothing here designs a version selector. The architecture document's own
digest is recorded in the manifest as a root input and **not pinned**: the closure commit `0a4cba3`, this plan's commit and the executed
unit's documentation commits each change that digest and nothing of the method.

## 7. What follows, and what does not

```
[b4-sim-5]  the S = 32 exploration under v0.3.0 (this plan; its execution a separate ruling)
     │ gives: the archive, the §9.4 (v0.3.0 row) decision
     ├── go ──────► [b4-gate-2]  the S = 200 gate under v0.3.0: ITS OWN execution plan and ITS OWN execution
     │                            ruling; its derivation against the pool that then includes b4-sim-5's 65 values (2 755)
     ├── no-go ───► stop; what follows needs its own argument and ruling (no automatic successor)
     └── no decision / invalid / incomplete ──► stop and report; the owner's next step
```

- A go moves nothing but the authority to *propose* the gate's plan; the gate's execution, its HEAD and deadline are its own ruling.
- A no-go, a no decision, an invalid or an incomplete batch licenses no second exploration, no tuning, no replacement label and no next
  protocol version; three stops in a row (the valid FAIL of `b4-gate-1`, the no-go of `b4-sim-4`, a no-go here) would not show that a fourth
  version is overfitting — they only remove the automatic next step (§9.4).
- Nothing of 2c, the carrier, 2d, the board or the routing line moves on the strength of any row; the dependency graph of the gate plan §7
  stands with `[G]` read as the gate of whichever protocol version the owner takes to it.

## 8. What this plan does not do

It runs nothing, derives nothing, prints no seed, changes no program, no table, no threshold, no hypothesis, no archive and no verdict; it
chooses no new probability, threshold or scientific rule (every number is §9.4's and §7.2's, carried); it predicts no outcome and no decision;
it authorises nothing — the execution (with its HEAD and deadline), the gate's plan, a revision, the carrier, 2d, the routing study, the board,
push and merge each remain the owner's. Its numbers are costs estimated from the `b4-sim-4` run on one host, with the uncertainty stated, and
the inventory values read on 2026-10-27.

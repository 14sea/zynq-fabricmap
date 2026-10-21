# B4 — the execution plan of the exploration `b4-sim-4` (DRAFT v0.1 — documents and a read-only inventory only, 2026-10-21)

> **Authorisation.** The owner's review of `21db2de` (2026-10-21, PASS: the protocol v0.2.0 host-tool unit accepted and closed), section 6:
> "Proceed directly with a complete pure-document execution-plan unit … Read existing files and metadata only. This document unit does not
> authorize production preflight, seed derivation or printing, smoke/mechanics/model runs, or actual exploration. Execution requires a
> subsequent ruling naming HEAD, date and deadline." This unit writes the plan and takes a read-only inventory
> (`evidence/b4/unit_sim4_plan_2026_10_21/inventory.py`, output `inventory.txt`: reads of committed files, `git` state and the tool's own
> constants; `b4_seeds.master_seed` / `pair_seeds` never called). **It does not execute the exploration, derive or print any seed, run any
> pre-flight, smoke, mechanics or model batch, change any program, table, threshold, hypothesis or archive, build RTL, touch a board, push or
> merge.** The execution itself remains a separate, last, independent authorisation (section 5) naming the **execution HEAD**, the **date**
> and the **deadline**. Every number below that describes the run is an estimate from the archived `b4-sim-3` (S = 32, 2026-10-19) and
> `b4-gate-1` (S = 200, 2026-10-20) runs of protocol v0.1.16 on this host; **nothing here predicts the exploration's outcome or the policy's
> decision.** The precedent this plan follows is `docs/b4_gate_execution_plan.md` (v0.2.1, ACCEPTED); where v0.2.0 differs from v0.1.16
> (the target setup, the quarantine, the ordered prefix, the protocol identity, the go / no-go policy, the consumed labels), the difference is
> stated here and nowhere assumed.

## 0. Status index

| section | fixed | estimated | unresolved / for the owner |
|---|---|---|---|
| 1 the run's fixed conditions | S = 32, the label, the method of v0.2.0 at the accepted tool baseline `21db2de`, task-v0.2, K9 (b′) judged with (b) carried, the §9.4 policy (B_go = 64, p ≤ 0.20 with positives > negatives, all seven conditional medians ≥ 0.50, every planned pair complete), the soft-deadline policy, the two commands | the wall time, the disk, the archive and verification costs | the execution HEAD, the date and the deadline value (3 600 s recommended), named by the execution ruling; the branch the run happens on (proposed in 1.2) |
| 2 the start, the operator's obligations and the evidence contract | what the tool enforces; what the operator must check and when to stop; what the run writes and keeps | — | the execution HEAD (named by the ruling) |
| 3 the result paths | refused / init_failed / abrupt termination / invalid / incomplete / complete for the batch; refused / no_decision / go / no-go for the policy; the consumption of the label in every row | — | what follows a no-go or a no decision (the owner's, never automatic); the adjudication of an uncertain exposure |
| 4 the known records | the archived `b4-sim-3` and `b4-gate-1` values at B = 64 and for K9, under task-v0.1 and the old applicability, stated as records | — | nothing: no outcome is predicted |
| 5 acceptance | the tool's outputs, the fresh-process verifications, the commits and the Git-blob checks, in the order the clean-tree rule of the policy tool forces | — | the execution authorisation |
| 6 the identity and the old archives | the v0.2.0 verifiers refuse the two v0.1.16 archives by name; `b4-sim-4`'s archive carries the identity | — | nothing |
| 7 what follows | a go → `b4-gate-2` needs its own plan and ruling; a no-go → stop; no automatic successor | — | the owner's rulings |

## 1. The fixed execution conditions

| item | value | source |
|---|---|---|
| label | **`b4-sim-4`** — the exploration label of v0.2.0, a reserved name of which no value exists (`b4_seeds.EXPLORATION_LABEL`, `b4_thresholds.THRESHOLDS["anchor"]["exploration_label"]`); the harness refuses `b4-sim-1` / `b4-sim-2` (retired) and `b4-sim-3` / `b4-gate-1` (consumed) before any tree is read (`check_label_not_retired`, `RetiredLabelRefusal` / `ConsumedLabelRefusal`); a gate label is refused by the exploration CLI (mode `exploration` only) | `docs/b4_architecture.md` §9.2; `b4_seeds.py`; `b4_sim.preflight` |
| S | **32**, planned — never the number completed (§9.1); the policy's precondition is `count == 32` exactly (`THRESHOLDS["gonogo"]["S"]`) | §9.4; `b4_gonogo.decide` |
| method | protocol **v0.2.0** as accepted at **`21db2de`** (the owner's PASS of 2026-10-21): `b4/IMPORT.json` 59 entries (sha256 `a6af67efd18d47829a91f6041a53b98a240d2d16802cda8f45f233f7fbe91b4e`), **`protocol_sha256 = 2f096d4adbd83e0ec6350e6da2942cc862e99df4e81539719fa7261dad5a258c`** (`python3 -B b4/host/b4_protocol.py`; `architecture_revision` v0.2.0 informational, excluded from the digest); **unchanged by this unit** — no byte under `b4/` moves (`git diff --stat 21db2de HEAD -- b4/` empty at this inventory) | `b4_protocol.py`; `inventory.txt` |
| model, task, engine, controls | hypothesis v0.3 (`59948f9b…`), the certificate (`c69e419f…`), **task-v0.2** (the planted flip-flop target T-i: `storage_kind` fixed to flip-flop, the other 20 bits drawn once by `Rng((landscape_seed ^ 0x54415247) & 0xffffffff).uniform(1 << 20)`, the base included, nothing redrawn; two setup observations per pair; ceilings 64 / 80; None scores nothing; the `PublicTask` without the seed, `g*` or the private record — a fixed-program access contract, not information hiding), the (μ, λ) = (4, 8) engine, the controls of §8 — as accepted at `21db2de` | §7.1; `THRESHOLDS["task"]` |
| thresholds and the judged K9 | `b4_thresholds.THRESHOLDS` ("section 9", no revision text) — **unchanged**; K9's judged estimand **(b′)** `conditional_sr_driven` (`ff_srval` / `sr_kind` under SR-driven backgrounds, `sr_tied_low` pairs named and removed from the denominator) with the all-panel **(b)** carried beside it as a description, recomputed from the same retained grids — both recorded, both recomputable offline, never averaged across semantics | §9 K9; §9.3 clause 6; `b4_k9.py` |
| the policy | §9.4 as the table holds it: precondition every planned pair complete, the batch `complete`, S = 32, the archive verifying clean under this method; statistic 1 the one-sided exact sign test on **Ω − R at B_go = 64** (ties excluded from n, counted and reported), **positives > negatives and p ≤ α_go = 0.20**; statistic 2 **all seven (b′) medians ≥ 0.50**; **go** iff both; **no-go** otherwise; **no decision** when the precondition fails; every budget's Ω − R record carried in full, no other budget picked afterwards; **a cost policy — not a significance result, not a gate verdict, not an authorisation, never a scientific impossibility; no automatic successor** | §9.4; `THRESHOLDS["gonogo"]`; `b4_gonogo.py` |
| the derivation | the master `sha256("b4-sim-4|" + HYPOTHESIS_SHA256)[:4]` and the 32 pairs by B2's `pair_seeds` copy against the **pooled exclusion as read at the pre-flight** — at this inventory **2 625 values**: the 38 historical sources, B4's exposed values, the exposure receipt (`68764bbc1a51ec25…`, 66 values) and the registry's two archived sets (`b4-sim-3` 65 values, `b4-gate-1` 401 values) — **performed in memory by the harness at `Batch.init`, after the pre-flight and the exclusive creation of the output directory, and nowhere else; not here** | §9.2; `b4_seeds.master_seed` / `pair_seeds`; `b4_sim.Batch.init` |
| the commands | (1) `python3 -B b4/host/b4_sim.py --label b4-sim-4 --seeds 32 --deadline-s 3600` from the repository root on the clean committed tree at the execution HEAD; the batch under `evidence/b4/sim/b4-sim-4_<UTC>/`. (2) **After the archive is committed** (section 5, step 3 — the policy CLI refuses a tree that is not clean, and an uncommitted archive is an untracked entry): `python3 -B b4/host/b4_gonogo.py decide evidence/b4/sim/b4-sim-4_<UTC>`; the decision under `evidence/b4/gonogo/b4-sim-4_<UTC>/` (`gonogo.json`, `gonogo.md`; the namespace `evidence/b4/gonogo/` does not exist at this inventory and is created by the tool without symlinks) | `b4_sim.main`; `b4_gonogo.main` / `write_decision` |
| deadline | **3 600 s recommended; the execution ruling names the value.** The SOFT monotonic policy unchanged: counted from the pre-flight, checked before and after every target observation, arm, replay, snapshot, K9 pair, K10 unit, statistics unit and before every finalisation unit (after the batch's own deep verification included); a started unit never interrupted; an expiry makes the batch `incomplete` with everything on disk. The deadline is part of the authorisation, not an operator-selectable parameter; the policy's `decide` has no deadline (it runs nothing) | `b4_deadline`; `b4_sim` docstring (F8, R4) |
| one worker; nothing else in the repository during the run | the harness holds HEAD, every input digest (the root inputs, the hypothesis's repository and external sources, the 38 exclusion sources, the receipt), every tool digest and the registry snapshot at every pair's end and at the end (`input_drift` → `invalid`); at the end the working tree must carry nothing but the batch's output | `b4_sim.Batch.hold_inputs` / `hold_tree` |

### 1.1 Costs — every number an estimate from the v0.1.16 runs on this host; the v0.2.0 batch cost has not been measured on a production-shaped run

| cost | measured | `b4-sim-4` estimated | note |
|---|---|---|---|
| the batch, including its own deep self-verification | `b4-sim-3` (S = 32, v0.1.16): `elapsed_s` **209.702** of 3 600, 643 files, 193 MB; `b4-gate-1` (S = 200): 1 372.077 s, ≈ 6.9 s per pair | **≈ 4–10 min** | v0.2.0 adds per pair two target observations (64 in all, beside ≈ 1 827 arm observations per pair: six arms at B + 2 = 258 and F at B + 23 = 279), the four setup files and their reconstruction in the self-verification; the S = 32 mechanics fixture of the tool unit (`e2e_v2/complete_32`, 771 batch files) exercised exactly this path but its wall time is not a record of this plan; the range is an uncertainty, not a bound |
| the deadline margin | — | **not proved**: 3 600 s against ≈ 4–10 min is ≈ 6–15× by extrapolation | an expiry is `incomplete` with everything on disk, never a loss |
| one fresh-process batch verification (`b4_sim_verify.py`, deep: the setup reconstructed from the kept records, the two target observations re-executed through the replay port against the recorded traces, every arm re-executed against the ledger's recorded observations and re-audited — never re-observed on the fabric — K7's prefixes, K9 / K10 and the summary recomputed from the retained grids) | 79 s for `b4-sim-3` | ≈ 1.5–3 min | before commit 1 (section 5) |
| the decision (`b4_gonogo.py decide`), including its in-process self-validation (the batch re-verified deep, the decision recomputed) | — | ≈ 1.5–3 min | after commit 1; runs nothing on the model but the replay |
| one fresh-process decision verification (`b4_gonogo.py verify`, deep: the batch re-verified, the decision recomputed, the markdown re-rendered) | — | ≈ 1.5–3 min | before commit 2; the batch's third deep pass is inherent to the verifier, not a second round of record |
| disk, the working tree | 643 files / 193 MB at S = 32 (v0.1.16) | **≈ 770 files / ≈ 200 MB** (the fixture's 771 files), plus 2 files for the decision | `/home/test` had 516 GB free at this inventory |
| disk, the repository | — | order of 200 MB in `.git`, a guess | the evidence discipline (every seed, partial, quarantine and stop record kept) is the owner's rule; the size is disclosed, not optimised away |
| wall time, the whole executed unit | — | **≈ 20–40 min** of compute, plus three commits | the computer must not sleep during the batch (a monotonic-clock jump across a suspend has been seen to count against a soft deadline on this host) |

### 1.2 The branch and the two refs, kept apart

The v0.2.0 tool exists only on **`b4-protocol-v2`** (`21db2de` and its successors); `main` is `a243ee8` and carries the v0.1.16 tool, which
refuses the label `b4-sim-4` by nothing but its grammar and has no identity, no task-v0.2 and no policy — the run cannot happen on `main`
without a merge, and **a merge is not proposed here** (its timing is the owner's, as it was for `b4-prework`). The proposal: the execution
HEAD is a commit on `b4-protocol-v2`'s line **after the owner's PASS of this plan** (this plan's closure commit, or the commit the ruling
names), the run performed on a branch `b4-sim-4-execution` created from that HEAD, so that the archive commits sit on their own branch
exactly as `b4-gate-1-execution` did. **Two refs:** `21db2de` is the **accepted tool baseline** (the engineering PASS; the tool bytes the
operator's stop holds the execution tree to); the **execution HEAD** is whatever commit the ruling names — it will differ (this plan and
its closure come after `21db2de`), and the manifest records it because that is what it reads. Both are stated in the unit README of the
executed unit; neither is substituted for the other. The registry on that line holds both archived sets (`b4-sim-3`, `b4-gate-1`:
`5070967` is an ancestor of `21db2de`), which is why the pooled exclusion is 2 625 and not `main`'s 2 224.

**Proposed for the execution ruling to name:** the execution HEAD as above; the date **2026-10-22 (UTC)** or the day the ruling names;
the deadline **3 600 s**.

## 2. The start — what the tool enforces, what the operator must do, and the evidence contract

### 2.1 The order of events inside the tool (`b4_sim.run_batch` → `preflight` → `create_out_dir` → `Batch.init` → the pairs → `finish`)

1. **The pre-flight writes nothing** (`refused`, exit 2, no output directory): the label grammar `b4-sim-<n>`; the retired and consumed
   labels refused before any tree is read; S and the deadline positive ints; **the protocol identity buildable from the code tree's trusted
   inventory** (`bp.identity(REPO_ROOT)`: every `b4/host` module and `b4/schemas` file at its `b4/IMPORT.json` digest — an `IdentityRefusal`
   is a refusal; note that the tool checks *buildable*, not *equal to the authorised digest*, which is the operator's check of 2.3); the
   clean tree (`git status --porcelain --untracked-files=all` empty, no override); the formal hypothesis (not a fixture, at its pinned digest),
   the mapping, the truth fabric; every exclusion source readable, the receipt at its pinned digest; the output directory
   `evidence/b4/sim/b4-sim-4_<UTC>` not existing and the namespace chain free of symlinks.
2. The output directory is created exclusively and the chain re-checked.
3. **`Batch.init` derives the master and the 32 pairs in memory**, **then writes `seeds.json` as the first file** (schema 1.2.0: the anchor
   with the label beside it, the master, the pairs, the exclusion as pooled — the 38 sources, B4's exposed values, the registry snapshot,
   the receipt, the pooled total), **then `manifest.json`** (1.2.0: HEAD, **the protocol identity and `protocol_sha256`**, the code root,
   every input digest, the external sources by absolute path and digest, the tool digests, the registry snapshot as read, the constants, the
   thresholds table), **and only then the first observation**. The guarantee is persistence before the first observation, not before the
   derivation; a failure between the derivation and the write is section 3's `init_failed`.
4. **Per pair, before any arm, the target setup** (§7.1): `task_setup.json` (the pair identity, `g*` by the fixed rule, the two stimulus
   digests; status `in_progress`) → the search-stimulus observation of `g*` through the dedicated TARGET port, phase `target`, **its return
   saved at once** — as `target_search.json` when it is a valid target observation, as `target_search.QUARANTINE.json` (the object the port
   returned, raw, with the findings, the phase, `g*`, the stimulus digest, the expected source identity and the digest of the kept
   projection) when it is not → the holdout-stimulus observation, phase `target_holdout`, saved the same way → `task.json` (the `PublicTask`,
   its digest, the setup files' digests); the planned record carries the setup state (`in_progress` / `partial` / `complete` / `invalid`),
   the **durable ordered prefix** `task_prefix` (0–4) and `task_quarantine` (the phase whose return was quarantined, or null). Then the seven
   arms in the fixed order R → F → O → X → D → Ω → A0 on one worker, each `RunResult` written exclusively before its audit (a malformed one
   quarantined raw), then the controls, K7, K9 (both applicabilities), K10, the curves and the pair index; the inputs, the tool digests and
   the registry held at every pair's end.
5. The statistics (every budget's deltas, the K5 scan, the K9 summaries under both applicabilities, K10), the final holds; **`reconcile_setup`**
   (the disk is the authority for every pair's setup state, prefix and quarantined phase); the archive-wide self-verification; the report.

### 2.2 What the tool enforces and what it does not

| the tool enforces | the operator must do (not checked by the tool) |
|---|---|
| a clean tree at the pre-flight; the label grammar and the retired / consumed refusals; S and the deadline as given; the identity buildable from the inventory and recorded in the manifest; the formal inputs at their pinned digests; the receipt at its pinned digest; the snapshot of the registry *it reads* and its hold during the batch; the freezing order; the exclusive writes; the setup persistence call by call and the quarantine of a refused return; the stop rules; the self-verification | **no smoke test, no mechanics batch, no dry run, no `b4-mech-*` fixture under this tree's `evidence/b4/sim/` before the production call** (a fixture batch archived there would enter the registry before the draw); **no derivation or print of any seed by any other means, before or during** — the operator's checks below are reads of committed files, `git` state and the tool's constants only (the inventory script of this unit is such a read); the computer kept awake; nothing else run in the repository; the stdout / stderr / exit status of each command captured to files **outside the tree** during the run and copied into the unit directory afterwards |
| that HEAD does not move during the batch (`input_drift`) | **that the HEAD is the one the execution ruling named** — the tool records whatever HEAD it finds |
| that the identity can be built from the tree | **that `protocol_sha256` is `2f096d4a…`**, the accepted baseline's — the tool does not know the authorised digest; a tree whose inventory is self-consistent but different would run and record a different identity |
| that the registry it read does not change during the batch | **that the registry it will read is exactly the two archived sets** the authorisation expects — the tool snapshots and holds what it reads and would silently pool a newly archived set (a fixture, an aborted earlier attempt) |
| the policy CLI: a clean tree, an exploration label, an archive of this identity, a validating report, the namespace | **that the archive was committed before `decide`** (section 5, step 3), that the batch directory named is the one the run wrote, and that the decision is read from the documents on disk, never from the exit code |

### 2.3 The operator's stop (an explicit rule of this plan)

Before the batch command the operator compares — by reading committed files, `git` and the tool's constants, never by deriving or printing
a seed; `evidence/b4/unit_sim4_plan_2026_10_21/inventory.py` re-run and its output kept is sufficient for every row but the first — the
actual state with the execution authorisation, and **stops without running if any of these differs**:

| check | the expected value (this inventory, 2026-10-21) | how |
|---|---|---|
| HEAD | the execution HEAD the ruling names (on `b4-protocol-v2`'s line; the branch `b4-sim-4-execution` created from it) | `git rev-parse HEAD` |
| clean tree | `git status --porcelain --untracked-files=all` empty | `git status` |
| tool bytes | every file under `b4/` byte-identical to the accepted baseline **`21db2de`** (`git diff --stat 21db2de HEAD -- b4/` empty); `b4/IMPORT.json` 59 entries, file / base / copied-function digests all equal, no untabled file (`evidence/b4/unit_2b4a_repair_2026_10_18/import_check.py`) | git; `import_check.py` |
| protocol identity | `protocol_sha256` **`2f096d4adbd83e0ec6350e6da2942cc862e99df4e81539719fa7261dad5a258c`** | `python3 -B b4/host/b4_protocol.py` |
| exposure receipt | sha256 `68764bbc1a51ec2506bf9d9bcbb3f55f88f3d7642b5eb46c6fd3dd39f8dae146`, **66** values, `pinned_receipt_count()` 66 | `b4_seeds.read_exposure_receipt` |
| registry | **exactly two** run directories: `b4-sim-3_20261019T121833Z` (`seeds`, `1a0d1e7b91132ed6…`, 65 values) and `b4-gate-1_20261020T102526Z` (`seeds`, `785e76988d4e6ec4…`, 401 values); nothing else under `evidence/b4/sim/` | `b4_seeds.sim_registry` |
| pooled exclusion | **2 625** values, 38 historical sources | `len(bs.load_exclusion_set().values)` |
| the policy namespace | `evidence/b4/gonogo/` absent (the tool creates it), or holding only what a ruling put there | `ls` |
| disk | ≥ 2 GB free | `df` |

A difference is reported to the owner; the run does not start; nothing is "fixed" to make it match.

### 2.4 What the run writes, and keeps whatever happens

`seeds.json` → `manifest.json` → per pair `task_setup.json` → `target_search.json` *or* `target_search.QUARANTINE.json` → `target_holdout.json`
*or* `target_holdout.QUARANTINE.json` → `task.json` → the seven arm results (or their `arm_<role>.result.QUARANTINE.json`) each before its
audit, the audits, the controls, `k7.json`, `k9.json`, `k10.json`, `curves.json`, `index.json` → the statistics → `sim_report.json` (status;
the identity; the archive index; the pooled summary only when complete and clean; the self-validation) and, when the batch did not
complete, `STOPPED.json` naming the kind, the pair, the stage and the whole planned list with every pair's setup state, prefix and
quarantined phase. Then, after commit 1, the decision directory `gonogo.json` + `gonogo.md`. **Every raw target return — valid or
quarantined — every seed, every partial, every quarantine and every stop record is kept**; nothing is redrawn, replaced, filled in,
narrowed or deleted; the two commands' stdout / stderr / exit status are kept beside them.

## 3. The result paths — separate dispositions, none automatic

### 3.1 The batch (`b4_sim.py`; exit codes 0 complete, 1 invalid, 2 refused / init failed, 3 incomplete — captured, never deciding)

| what happened | the record on disk | disposition | what is NOT done |
|---|---|---|---|
| **pre-flight refusal** (`refused`, exit 2) | no output directory; the stdout / stderr / exit captured | report the named reason to the owner; the label is **not** consumed (no derivation ran) — the owner decides the next step | no silent fix of the tree, the inventory or the inputs and re-run |
| **initialisation failure** (`init_failed`, exit 2: an exception after the directory exists) | `INIT_FAILED.json` (`label`, `seeds_derived`, `reason`), possibly `seeds.json`, no or a partial `manifest.json`, no report, no `STOPPED.json` | keep everything; inventory which expected files are absent; **stop and report** | **no retry under the same label, no release of the label**: `seeds_derived` is set from whether a `seeds.json` write was recorded and **`false` does not prove that no in-memory derivation occurred**; the label is **consumed or exposure-uncertain pending the owner's adjudication** (values excluded by value; a label never reused on an assumption) |
| **abrupt termination** (the process or the machine dies; no return value) | the durable prefix only: whatever was written exclusively before the event — `seeds.json`, `manifest.json`, the pairs' files up to and including a setup file or a quarantine, possibly a `.part`; no `STOPPED.json`, no report; `reconcile_setup` did not run | keep everything; inventory the files present against the plan (`manifest.json` and the pair indexes name what should exist; a pair's setup files are read as the ordered prefix they are); **stop and report**; the archive verifier is run for the record but its findings on a truncated archive are expected and are not a verdict | no manufactured report, no re-run; the label consumed |
| **`invalid`** (exit 1) — the v0.2.0 kinds: `target_invalid` (a DOMAIN or `SourceRefusal` at a target observation; **a returned object that is not a valid target observation — a None anywhere in the grid, a cell that is not the int 0 / 1, a malformed shape or provenance, a source identity that is not the expected one — kept raw in the phase's QUARANTINE file, the pair `invalid` with `task_quarantine` naming the phase**; a drift between the two observations; a third port call); `result_malformed`; a control failure; a replay or recompute finding; a K10 `comparable = False`; a schema finding; `input_drift`; `unexpected_exception`; `self_validation` | `STOPPED.json` with the kind, the pair, the stage; the report with status invalid; the quarantine files; every pair's durable prefix | a tool / source / replay / control contract break, never a landscape failure: archived (section 5's commit 1 and the fresh verification still apply, for the record); **the policy's precondition is not met → `no_decision`**; the finding named; the unit halts and reports | not re-run under the same label; the next step is the owner's (a repair unit, then a ruling on a new label — `b4-sim-4` is consumed by its records) |
| **`incomplete`** (exit 3: the deadline, an external interrupt) — including an interrupt landing **after a quarantine's durable write and before the in-memory state caught up**: `reconcile_setup` rebuilds the pair's `invalid` state and quarantined phase from the file on disk while the batch's stop carries the interrupt (C2) | `STOPPED.json`, every pair's work and prefix, the report with status incomplete | unfinished work, never a result: archived; the unexecuted and the partial pairs named; **`no_decision`** | whether the unexecuted runs are resumed is decided separately (§9.1) and never under this label with a redraw; no partial summary read as a result; no automatic re-run |
| **`complete`** (exit 0; the self-verification clean) | `sim_report.json` complete with the pooled summary: every budget's deltas (Ω − R among them), the K5 scan, K9 under both applicabilities with `judged_estimand = conditional_sr_driven`, K10, the K7 medians | the fresh-process verification, commit 1, then the decision (3.2) | no decision is read from the summary by hand; no budget other than B = 64 is picked for the policy; no threshold or policy number touched |

### 3.2 The decision (`b4_gonogo.py decide`; exit codes 0 go / no-go, 2 refused, 3 no decision; `self_validation` non-empty → no decision)

| what happened | the record on disk | disposition | what is NOT done |
|---|---|---|---|
| **refused** (exit 2: the tree not clean — an uncommitted archive is an untracked entry — a label that is not an exploration label, an archive of another or no identity, a report that does not validate, a batch directory not directly under `evidence/b4/sim/`, the decision directory existing) | nothing written | report the named reason; if the cause is an uncommitted archive, commit 1 of section 5 first and run `decide` again — that is the ordering this plan fixes, not a fix of evidence; any other cause is reported to the owner | no edit of the archive; no decision by hand |
| **`no_decision`** (exit 3: the precondition unmet — the batch not `complete`, S ≠ 32, a pair not complete, no summary — a summary contract finding, or the record's own self-validation finding its evidence inconsistent) | `gonogo.json` with `decision = no_decision`, `statistic_1` / `statistic_2` null, the reason; `gonogo.md` | stop and report; the batch's own row of 3.1 governs what follows | no re-decision after an edit; no second exploration on this plan's authority |
| **`go`** (exit 0, `formal = true`) | `gonogo.json` with both statistics, every budget's Ω − R record, the policy, the identity, the evidence binding (the archive's report / seeds / manifest digests); `gonogo.md` | a **cost-policy go**: the fixed certificate grouping with the fixed operator showed a positive signal at one budget and the conditional coverage was not below threshold — a proxy, good enough to spend the gate's cost; archived and committed as section 5 says; **`b4-gate-2` needs its own execution plan and its own execution ruling** (section 7) | not a prediction of the gate, not a gate result, not an authorisation of anything; no S change, no budget re-pick, no second statistic added |
| **`no-go`** (exit 0, `formal = true`) | the same record with the reasons (which of positives > negatives, p ≤ 0.20, the seven medians failed) | **the exploration is archived as a result; stop.** What follows — a different grouping shape, a different operator, a different stimulus, or stopping — needs its own argument and its own ruling; **a no-go is a cost-policy stop, not a scientific negative conclusion, not evidence about the fabric and not a statement that the class is indistinguishable** | **no tuning, no automatic retry, no replacement seed or label, no second exploration, no next protocol version** on this plan's authority; nothing of the carrier, the board or the routing line moves on the strength of a no-go |

**The CLI exit codes never decide anything.** Both are captured; the documents on disk and their statuses decide which row applies — a `0`
from the policy tool is a decision written (go *or* no-go), and an absent document is a row of its own.

**The label, in every row.** `b4-sim-4`'s master and pairs are in the registry and in the pooled exclusion of every later derivation as
soon as `seeds.json` exists, and treated as exposed even when it does not (the `init_failed` row): a refused pre-flight is the only row
that leaves the label unconsumed. A stopped, invalid, incomplete, no-decision or no-go batch does not free its label, and no replacement
label is reserved by this plan — `b4-sim-5` is a name nobody has proposed.

## 4. The known records, as records — not as a prediction

Both archives are of **protocol v0.1.16 under task-v0.1 and the old all-panel K9 applicability**; the v0.2.0 verifiers refuse them by name
(section 6). They are stated so that a go, a no-go or a no decision is not a surprise and not an excuse; nothing here says what `b4-sim-4`
will show under task-v0.2 and (b′), and no number from them sets anything in this plan.

- **Ω − R at B = 64.** `b4-sim-3` (S = 32): positives 10, negatives 12, ties 10, mean −0.219, one-sided sign-test p 0.738. `b4-gate-1`
  (S = 200): positives 56, negatives 95, ties 49, mean −0.49, p 0.9995; negative at every budget. Under the old task the policy's statistic 1
  would not have been met on either sample; the task is different now (§7.1), and that record was the *motivation* of the new contract, not a
  validation of it (`evidence/b4/unit_protocol_v2_design_2026_10_20/README.md` §4).
- **K9.** Under the old (b): `ff_srval` median 0.427 (`b4-sim-3`) and 0.40625 (`b4-gate-1`) against the configuration-only upper bound of 0.5
  (the owner's audit of 2026-10-19); `sr_kind` exactly 0.5; the other five 1.0. Under (b′) nothing has been measured on a production
  archive; the design unit's descriptive re-reading of `b4-gate-1`'s record (driven-only per-seed median 0.8125) is a description of the old
  sample under the new definition, recorded as post hoc and **not** a basis or a validation. The mechanics fixture `e2e_v2/complete_32` of the
  tool unit decided **no-go** at B = 64 (positives 7, negatives 12, p 0.916; conditional medians all ≥ 0.50) — the policy exercised on a
  fixture of already-exposed seeds, `formal = false`, not a finding about Ω − R.
- **The latch region** (§7.1's prior): `g*` is never a latch configuration; the search still visits latch candidates whose x5FF elements read
  None and score nothing on 32 of the 64 cells — a low-score region that follows from the prior, not an observation about latches; the new
  comparison gives no evidence about a latch-target task.
- **B\* / N.** Neither archive had a B\*; the policy does not use B\*, N or the K5 scan — it reads B = 64 alone, named before the run.

**Data influence, disclosed.** The task contract, the conditional estimand, the policy's budget and α were chosen on 2026-10-20 after the
records above (the owner's choices 1–6; the influence table in the design unit's README §4). This plan adds no choice informed by data:
its only numbers are the table's.

## 5. Acceptance of the executed unit (when, and only when, the execution is authorised)

The order below is forced by the policy tool's clean-tree rule (the archive must be committed before `decide`) and by the verification
rule the owner chose for `b4-gate-1` (one fresh-process verification of record before each commit, Git-blob digests after it, no second
full round unless something changed).

1. **The batch's outputs as written**: the archive (`sim_report.json` and everything it indexes, every quarantine and stop record) and the
   captured stdout / stderr / exit status. No file is edited. If 3.1's refusal / initialisation-failure / abrupt-termination row applies, the
   acceptance stops at "keep, inventory, report" and the verification below is run for the record only; an `invalid` or `incomplete`
   batch is still verified, committed and decided (→ `no_decision`) so that the record is complete.
2. **One fresh-process batch verification, before commit 1**: `python3 -B b4/host/b4_sim_verify.py evidence/b4/sim/b4-sim-4_<UTC>` (deep;
   step 0 the identity against the verifier's own inventory; a clean result establishes internal execution / derived-result consistency and
   source binding, **not** the truth of the observation source). Exit code and output kept with a three-line header (HEAD, command, UTC).
3. **Commit 1 — the archive exactly as the tool wrote it, nothing else** (the branch `b4-sim-4-execution`). **After the commit, the committed
   bytes are compared to the verified files by Git-blob digest** (`git ls-tree -r <commit>` against `git hash-object` of every file on
   disk; the `b4-gate-1` unit's `blob_digest_check.py` adapted to the one directory); equality recorded; no second deep verification.
4. **The decision**: `python3 -B b4/host/b4_gonogo.py decide evidence/b4/sim/b4-sim-4_<UTC>` on the clean tree at commit 1 (the record's
   `head` is therefore commit 1's hash, not the execution HEAD — both are stated in the unit README; the batch's manifest holds the
   execution HEAD). Its stdout / stderr / exit captured.
5. **One fresh-process decision verification, before commit 2**: `python3 -B b4/host/b4_gonogo.py verify evidence/b4/gonogo/b4-sim-4_<UTC>`
   (deep). Exit code and output kept with the header.
6. **Commit 2 — the decision directory exactly as written, nothing else**; the Git-blob comparison repeated for it.
7. **Commit 3 — the unit record** `evidence/b4/unit_sim4_execution_<date>/`: the run headers, the captured outputs of both commands, the
   operator's stop (the inventory output), the two verification outputs, the two blob comparisons, and the README — the identity the
   manifest recorded (the execution HEAD, `protocol_sha256`, the tool digests, the receipt, the registry snapshot, the pooled total), the
   batch status and deadline record, **the decision and both statistics copied, not summarised** (positives / negatives / ties / p / mean /
   d at B = 64; the seven (b′) medians and the seven (b) medians beside them; every budget's Ω − R record), the disposition of section 3,
   and what was not done. If anything changed between a verification and its commit, the reason is recorded and that verification is
   repeated.
8. **The execution authorisation is the last, separate, independent gate**: this plan's acceptance runs nothing; a later ruling names the
   execution HEAD, the date and the deadline; the run happens once, on that tree, with no smoke test before it, after the operator's stop of
   2.3 found no difference.

## 6. The identity and the old archives

`b4-sim-4`'s manifest carries the protocol identity and `protocol_sha256` (§9.5); every v0.2.0 verifier, the judge and the policy rebuild the
payload from their own trusted inventory and compare it component by component before reading anything else — an archive of another
identity, or of none, is refused by name and pointed to `docs/b4_archive_reverification.md`. The two v0.1.16 archives are therefore
re-verified only by that page with their own tool at their archive commits, never by the v0.2.0 tool; `b4-sim-4` is verified by the v0.2.0
tool at the execution HEAD, whose bytes the operator's stop holds equal to `21db2de`'s. A later method change (a new protocol version, a
changed table, a changed validator) will refuse `b4-sim-4`'s archive by name in its turn; nothing here designs a version selector. The
architecture document's own digest is recorded in the manifest as a root input and **not pinned**: this plan's commit changes that digest
and nothing of the method.

## 7. What follows, and what does not

```
[b4-sim-4]  the S = 32 exploration under v0.2.0 (this plan; its execution a separate ruling)
     │ gives: the archive, the §9.4 decision
     ├── go ──────► [b4-gate-2]  the S = 200 gate under v0.2.0: ITS OWN execution plan and ITS OWN execution
     │                            ruling; its derivation against the pool that then includes b4-sim-4's 65 values
     ├── no-go ───► stop; what follows needs its own argument and ruling (no automatic successor)
     └── no decision / invalid / incomplete ──► stop and report; the owner's next step
```

- A go moves nothing but the authority to *propose* the gate's plan; the gate's execution, its HEAD, date and deadline are its own ruling.
- A no-go, a no decision, an invalid or an incomplete batch licenses no second exploration, no tuning, no replacement label and no next
  protocol version; two stops in a row (the valid FAIL of `b4-gate-1`, a no-go here) would not show that a third version is overfitting —
  they only remove the automatic next step (§9.4).
- Nothing of 2c, the carrier, 2d, the board or the routing line moves on the strength of any row; the dependency graph of the gate plan §7
  stands with `[G]` read as the gate of whichever protocol version the owner takes to it.

## 8. What this plan does not do

It runs nothing, derives nothing, prints no seed, changes no program, no table, no threshold, no hypothesis, no archive and no verdict; it
predicts no outcome and no decision; it authorises nothing — the execution (with its HEAD, date and deadline), the gate's plan, a revision,
the carrier, 2d, the routing study, push and merge each remain the owner's. Its numbers are costs estimated from the v0.1.16 runs on one
host, with the uncertainty stated, and the inventory values read on 2026-10-21.

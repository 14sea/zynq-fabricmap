# B4 — the execution plan of the production gate `b4-gate-1` (DRAFT v0.2, documents and read-only inventory only, 2026-10-20)

> **v0.1 → v0.2 (2026-10-20, the owner's HOLD on `6d4b339`; documents only).** The start order corrected (the derivation happens in memory, then
> `seeds.json` is the first file written, then `manifest.json`, then the first observation — the guarantee is persistence before the first
> observation, not before the derivation); the operator's obligations separated from what the tool enforces, with an explicit operator stop
> when the actual identity differs from the execution authorisation, and the accepted tool baseline separated from the authorised execution
> HEAD; the result paths completed with the pre-flight refusal, the initialisation failure and an abrupt termination, and the limit of
> `INIT_FAILED.seeds_derived` disclosed (false does not prove that no derivation occurred); the costs re-aligned (the 209.7 s already include
> the harness's self-verification; the K5 scan does not scale linearly; one fresh-process batch verifier and one fresh-process gate verifier
> before the commit, then Git-blob digests after it; every number an estimate); K7's status on the sample stated as not assessable; option B
> of the versioning schemes re-costed as version selection across the whole verification / judgement stack; the dependency diagram's arrow
> corrected (only the rest of 2c depends on the gate), the qualification node left without a stage, B4-R's prerequisites stated with the
> shared ones. `6d4b339` is retained as v0.1's record.

> **Authorisation.** The owner's ruling of 2026-10-20 after the gate tool's engineering acceptance (`19597e7` PASS; the tool, its verifier
> and its evidence at `00336d0`): this unit writes the plan and takes a read-only inventory. **It does not execute the gate, derive or print
> any seed, change any program, run any simulation, build RTL, touch a board, push or merge.** The execution itself remains a separate,
> last, independent authorisation (section 5), which will name the **execution HEAD** to run at. Every number below that describes the run
> is an estimate from the S = 32 exploration of 2026-10-19; nothing here is a prediction of the gate's outcome.

## 0. Status index

| section | fixed | estimated | unresolved / for the owner |
|---|---|---|---|
| 1 the run's fixed conditions | S = 200, the model / method / thresholds as accepted at `00336d0`, the label, the soft-deadline policy | the wall time, the disk, the archive and verification costs | the deadline value (3 600 s recommended, named by the execution ruling) |
| 2 the start, the operator's obligations and the evidence contract | what the tool enforces; what the operator must check and when to stop | — | the execution HEAD (named by the execution ruling) |
| 3 the result paths | refused / init_failed / abrupt termination / complete-PASS / complete-FAIL / invalid / incomplete, each with its disposition | — | what follows a valid FAIL (a separately proposed revision); the adjudication of an uncertain exposure |
| 4 the known risks | the exploration's K9, K5 and K7 records, stated as records | — | nothing: no outcome is predicted |
| 5 acceptance | the tool's outputs, the two fresh-process verifications before the commit, the blob digests after it | — | the execution authorisation |
| 6 the version coupling | the owner's ruling; `00336d0` as the re-verification baseline | — | a future versioning scheme (options listed, none implemented) |
| 7 the dependency graph | the edges the architecture fixes | — | the B4 lifecycle and its stages; B4-R's own preregistration |

## 1. The fixed execution conditions

| item | value | source |
|---|---|---|
| label | `b4-gate-1` — the pinned gate label of section 9.2 (`b4_thresholds.THRESHOLDS["anchor"]["gate_label"]`); the tool refuses any other | `docs/b4_architecture.md` §9.2; `b4_gate.PINNED_GATE_LABEL` |
| S | **200**, planned — never the number completed (K6); the tool refuses any other `--seeds` | §9 K6; `b4_gate.S_GATE` |
| model, task, engine, controls | hypothesis v0.3 (`59948f9b…`), the certificate (`c69e419f…`), the task generator, the (μ, λ) = (4, 8) engine, the controls of §8 — as accepted at `00336d0`; **unchanged by this unit** | `b4/IMPORT.json` (52 entries) |
| thresholds | `b4_thresholds.THRESHOLDS`, "section 9 (v0.1.16), fixed before any exploration or gate run" — **unchanged**; the current protocol version is judged as it stands and a valid FAIL is a result of it (the owner's ruling of 2026-10-19 on the gate tool, section 1) | `b4/host/b4_thresholds.py` |
| the derivation | the gate's master and pairs by §9.2's anchor with the label beside it, against the exclusion set as pooled at the pre-flight (the 38 historical sources, the exposure receipt, every archived set under `evidence/b4/sim/`) — **performed in memory by the harness at the batch's `init`, after the pre-flight and the exclusive creation of the output directory, and nowhere else; not here** | `b4_seeds.master_seed` / `pair_seeds`; `b4_sim.Batch.init` |
| the command | `python3 -B b4/host/b4_gate.py run --label b4-gate-1 --seeds 200 --deadline-s 3600` from the repository root on the clean committed tree at the execution HEAD (section 2); the batch under `evidence/b4/sim/b4-gate-1_<UTC>/` (mode `gate`), the judgement under `evidence/b4/gate/b4-gate-1_<UTC>/` | `b4_gate.main` |
| deadline | **3 600 s recommended; the execution ruling names the value.** The existing SOFT monotonic policy unchanged: counted from the pre-flight, checked before and after every arm, replay, snapshot, K9 pair, K10 unit, statistics unit and before every finalisation unit — including after the batch's own deep verification (R4) — a started unit never interrupted; an expiry makes the batch `incomplete` with everything on disk (section 3). The deadline is part of the authorisation, not an operator-selectable parameter: the operator does not enlarge or shrink it | `b4_deadline`; `b4_sim` docstring (F8, R4) |
| one worker; nothing else in the repository during the run | the harness holds HEAD, every input digest, every tool digest and the registry snapshot at every pair's end and at the end (`input_drift` → `invalid`); the working tree must carry nothing but the batch's output at the end | `b4_sim.Batch.hold_inputs` / `hold_tree` |

### 1.1 Costs — every number an estimate from one S = 32 run on one host

The measurement: `b4-sim-3` (2026-10-19) recorded `elapsed_s` **209.702** in its report. That value is taken **after `Batch.finish`**, i.e. it already
**includes the harness's own archive-wide deep verification** (every arm re-executed on the model, the diagnostics and the summary recomputed)
that runs before the report is published; a separate fresh-process deep verification of the same archive took 79 s on this host. The archive:
643 files, 186 MB.

| cost | S = 32 measured | S = 200 estimated | note |
|---|---|---|---|
| the batch, including its own deep verification | 209.7 s | **≈ 22 min if linear (× 6.25); plausibly 25–40 min** | the per-pair work (seven arms, replay, K7, K9, K10) scales linearly; the statistics stage does not — the K5 scan is 8 … S per budget with 1 000 bootstrap experiments each, i.e. 193 scan points instead of 25, and the self-verification's summary recomputation repeats it; the range is an uncertainty, not a bound |
| the deadline margin | — | **not proved**: 3 600 s against an estimated 25–40 min is a margin of ≈ 1.5–2.4×, from an extrapolation | the recommendation of 3 600 s stands for the execution ruling to name; an expiry is `incomplete` with everything on disk, never a loss |
| the judgement (`b4_gate.write_judgement`), including its in-process self-validation (the verifier, deep) | — | ≈ 8 min (79 s × 6.25, the same caveat on the summary recomputation) | after the batch; not under the batch's deadline |
| **one** fresh-process batch verification (`b4_sim_verify.py`, deep) | 79 s | ≈ 8 min | before the commit (section 5) |
| **one** fresh-process gate verification (`b4_gate_verify.py`, deep: it re-verifies the batch and recomputes the judgement) | — | ≈ 8 min | before the commit (section 5); the two together are the verification of record — no second full round after the commit (the owner's choice; section 5) |
| disk, the working tree | 186 MB, 643 files | **≈ 1.2 GB, ≈ 4 000 files** (linear) | `/home/test` had 495 GB free at this inventory |
| disk, the repository | — | **unknown; order of 1 GB in `.git` is a guess** | the pack's growth across the earlier units is not a measurement of this archive's compressibility; whatever it is, the evidence discipline (every seed, partial and stop record kept) is the owner's rule of 2026-10-19 §6 and the size is disclosed, not optimised away |
| wall time, the whole executed unit | — | **≈ 50–70 min** of compute, plus the commits | the computer must not sleep during the batch (a monotonic-clock jump across a suspend has been seen to count against a soft deadline on this host) |

## 2. The start — what the tool enforces, what the operator must do, and the evidence contract

### 2.1 The order of events inside the tool (the production code, `b4_sim.run_batch` → `preflight` → `create_out_dir` → `Batch.init`)

1. **The pre-flight writes nothing**: the label grammar (mode `gate`: `b4-gate-<n>`; the gate tool itself refuses anything but the pinned label and any S but 200), the clean tree (`git status --porcelain` empty, no override), the formal inputs at their pinned digests (the hypothesis, the certificate, the exposure receipt), every exclusion source readable, the output directory `evidence/b4/sim/<label>_<UTC>` not existing and the namespace chain free of symlinks; a failure is `refused`, exit 2, with no output directory.
2. The output directory is created exclusively.
3. **`Batch.init` derives the master and the pairs in memory** (`bs.master_seed(label, HYPOTHESIS_SHA256)`, `bs.pair_seeds(master, 200, exclusion.values)`), **then writes `seeds.json` as the first file**, **then `manifest.json`** (HEAD, every input digest, the external sources by absolute path and digest, the tool digests, the registry snapshot as read, the constants, the thresholds table), **and only then the first observation** (the freezing order F9). The guarantee the harness gives is *persistence before the first observation*; a failure between the derivation and the write is section 3's `init_failed`.
4. Per pair the seven arms in the fixed order on one worker, each result written exclusively before its audit, then the controls, K7, K9, K10, the curves and the pair index; the inputs, the tool digests and the registry held at every pair's end.
5. The statistics, the final holds, the archive-wide self-verification, the report; then the gate directory with its own in-process self-validation.

### 2.2 What the tool enforces and what it does not

| the tool enforces | the operator must do (not checked by the tool) |
|---|---|
| a clean tree at the pre-flight; the pinned label and S = 200; the formal inputs at their pinned digests; the snapshot of the registry *it reads* and its hold during the batch; the freezing order; the exclusive writes; the stop rules; the self-verification | **no smoke test, no mechanics batch, no dry run on this tree before the production call** (a fixture batch would enter the registry before the gate's draw); **no derivation or print of any seed by any other means, before or during** — the operator's checks below are reads of committed files and `git` state only; the computer kept awake; nothing else run in the repository; the stdout / stderr / exit status of the command captured to a file |
| that HEAD does not move during the batch (`input_drift`) | **that the HEAD is the one the execution ruling named** — the tool records whatever HEAD it finds; it does not know the authorised one |
| that the registry it read does not change during the batch | **that the registry it will read is the one the authorisation expects** — the tool snapshots and holds what it reads; it does not know a separately approved snapshot and would silently pool a newly archived set |

### 2.3 The operator's stop (an explicit rule of this plan)

Before the command, the operator compares — by reading committed files and `git`, never by deriving or printing a seed — the actual state with
the execution authorisation, and **stops without running if any of these differs**: the HEAD (`git rev-parse HEAD`) against the execution HEAD
the ruling names; the tool bytes (`b4/IMPORT.json`'s digests, checked by `evidence/b4/unit_2b4a_repair_2026_10_18/import_check.py`) against the
accepted tool baseline `00336d0` (the 24 host modules' digests must be those of the baseline unless the ruling names a successor); the exposure
receipt (`68764bbc1a51ec25…`, 66 values; `bs.pinned_receipt_count()`); the registry (the run directories under `evidence/b4/sim/` — at this
inventory exactly one, `b4-sim-3_20261019T121833Z`, status `seeds`, `seeds.json` sha `1a0d1e7b91132ed6…`, 65 values) and the pooled exclusion
(2 224 values at this inventory, `len(bs.load_exclusion_set().values)`). A difference is reported to the owner; the run does not start; nothing
is "fixed" to make it match.

**Two refs, kept apart:** `00336d0` is the **accepted tool baseline** (the engineering PASS and the re-verification baseline of section 6). The
**execution HEAD** is whatever commit the execution ruling names — it will differ (this document and any merge come after `00336d0`). The
manifest records the execution HEAD because that is what it reads; the plan and the unit README state both and never substitute one for the
other.

### 2.4 What the run writes, and keeps whatever happens

`seeds.json` (the 200 pairs, the anchor, the exclusion as pooled) → `manifest.json` → per pair the seven arm results written exclusively before
their audits, the audits, the controls, K7, K9, K10, the curves, the pair index → the statistics → `sim_report.json` (status; the pooled summary
only when complete; the self-validation) and, when the batch did not complete, `STOPPED.json` naming the kind, the pair, the stage and the
whole planned list. Then the gate directory: `gate_report.json` and `gate_report.md`. **Every seed, every partial, every quarantine and every
stop record is kept** — nothing is redrawn, replaced, filled in or deleted; the command's stdout / stderr / exit status are kept beside them.

## 3. The result paths — separate dispositions, none automatic

| what happened | the record on disk | disposition | what is NOT done |
|---|---|---|---|
| **pre-flight refusal** (`refused`, exit 2) | no output directory (the pre-flight writes nothing); the stdout / stderr / exit captured | report the named reason to the owner; the label is **not** consumed (no derivation ran) — the owner decides the next step | no silent fix of the tree or the inputs and re-run |
| **initialisation failure** (`init_failed`, exit 2: an exception after the directory exists) | the output directory with `INIT_FAILED.json` (`label`, `seeds_derived`, `reason`), possibly `seeds.json`, no `manifest.json` or a partial one, no `sim_report.json`, no `STOPPED.json`, **no gate directory** | keep everything; inventory which expected files are absent; **stop and report** | **no retry under the same label, no release of the label**: `seeds_derived` is set from whether a successful `seeds.json` write was recorded (`batch.seeds_sha is not None`) and **`false` does not prove that no in-memory derivation occurred** — the derivation precedes the write; the label is treated as **consumed or exposure-uncertain pending the owner's adjudication** (the same discipline as the 2026-10-19 settlement: values are excluded by value, a label is never reused on an assumption) |
| **abrupt termination** (the process or the machine dies; no return value) | only the durable prefix: whatever was written exclusively before the event (`seeds.json`, `manifest.json`, the pairs' files), possibly a `.part`; no `STOPPED.json`, no report; the external stdout / stderr / exit, if any | keep everything; inventory the files present against the plan (`manifest.json` and the pair indexes name what should exist); **stop and report**; the archive verifier is run for the record but its findings on a truncated archive are expected and are not a verdict | no manufactured report, no demand that the normal verifiers exit 0 where the required documents do not exist; no re-run; the label consumed |
| `complete`, archive clean, every row PASS, the budget rule PASS | `sim_report.json` complete; `gate_report.json` verdict PASS, `formal = true` | **valid PASS**: archived and committed as section 5 says; the rows and B* / N become inputs of the rest of 2c (section 7); a PASS is never read as evidence about the fabric | no session, no board, no prediction, no freeze follow without their own rulings |
| `complete`, archive clean, a row or the budget rule FAILS | verdict FAIL, `formal = true` | **valid FAIL** — a result of this protocol version (the owner's ruling of 2026-10-19, section 1), confined to this model, public task / panel, operator / control design, budget grid and declared decision procedure; archived and committed exactly as a PASS is; the failing and the not-assessable rows stated as the tool states them; B* / N kept null when the budget rule failed | **no threshold adjusted, no budget or sample repaired, no re-run, no relabel, no redraw, no S change** (§9.1); no claim that FF bits or the content class are indistinguishable in general; a revision, if any, is **a separately proposed unit** that discloses the influence of `b4-sim-3` and of this gate's data and is never presented as validated by the data that motivated it |
| `invalid` (exit 1: a DOMAIN or other refusal, a control failure, a replay or recompute finding, a quarantined result, an input drift, a schema finding, a self-validation finding) | `STOPPED.json` with the kind, the pair, the stage; the report with status invalid; the gate verdict invalid | a tool / source / replay / control contract break, never a landscape failure: archived; the finding named; the unit halts and reports | not re-run under the same label; the next step is the owner's (a repair unit, then a ruling on a new label — `b4-gate-1` is consumed by its own records) |
| `incomplete` (exit 3: the deadline, an external interrupt) | `STOPPED.json`, every pair's work, the report with status incomplete; the gate verdict incomplete | unfinished work, never a result: archived; the unexecuted pairs named | whether the unexecuted runs are resumed is decided separately (§9.1); no partial summary read as a result; no automatic re-run |

**The CLI exit code never decides anything.** It is captured; the documents on disk and their statuses decide which row applies — a `0` from
the gate tool is a judgement written (PASS or FAIL), not a PASS, and an absent document is a row of its own, not a verifier failure to be
explained away.

In every case where a derivation may have run — every row but the pre-flight refusal — `b4-gate-1`'s master and pairs are in the registry
and the pooled exclusion of every later derivation as soon as `seeds.json` exists, and treated as exposed even if it does not (the
`init_failed` row): a stopped, invalid or failed batch does not free its label.

## 4. The known risks, as records — not as a prediction

Stated so that a FAIL, if it comes, is not a surprise and not an excuse; nothing here says that S = 200 will FAIL or PASS.

- **K9 (b), `ff_srval`.** Under the fixed comparison set of §9.3, exactly half of each `ff_srval` address's applicable pairs have SR tied low, where SRVAL cannot affect the trace: a configuration-only upper bound of **0.5** on that semantic's coverage fraction (the owner's audit of 2026-10-19). The exploration's 32 seeds have median **0.427083** and maximum 0.479 — none reaches 0.5. The criterion is **≥ 0.50** (equality allowed): at S = 200 a PASS of this row needs at least 101 seed fractions exactly 0.5. The owner's ruling: the bound and the observed deficit are recorded separately; the bound does not prove a universal FAIL; this version keeps the comparison set and the threshold, and a valid FAIL is an acceptable result of it. `sr_kind`'s median was exactly 0.5 (meets the threshold as written).
- **K5, Δ1 = O − R.** On the S = 32 sample the primary's Cohen's d lay in −0.32 … +0.03 across the ten budgets, and the complete N scan 8 … 32 reached bootstrap power 0.000 … 0.064 (0.000 … 0.046 at N = 32), so no N existed and the budget rule's candidate did not exist. The owner's ruling: the K5 "impossibility" is not established — the scan is a bootstrap of the one-sided exact sign test on O − R, whose power depends on the sign / tie distribution and N (at B = 32 the sample had 10 positives, 9 negatives, 13 ties beside a slightly negative mean), finite bootstrap rates need not be monotone, and S = 200 changes the empirical distribution and the scan's limit; none of this guarantees a PASS, raises d or licenses extending the sample.
- **K7.** On the sample B* did not exist, so K7's at-B* criterion (b) was **not assessable** — not passed. Descriptively, the medians of O's not-unknown addresses over the 32 seeds were 2, 3, 4, 5, 7, 9, 13.5, 16, 19, 21 at the budgets 8 … 256: below the reference 11 at the five smallest budgets, above it from B = 96 on. (a) held by the completion contract (every arm audited with no recompute finding).
- **K1, K8, K10** showed no deficit on the sample (K1 eligible at every budget; K8 by the completion contract; K10 interacting 32 / 32); these are descriptive records too, and K1 at B* is likewise not assessable without a B*.
- **The budget rule.** If no budget has both K1 eligibility and an N, B* and N are null, K1–K5 and K7 are not assessable, K6 is not assessable (S = 200 as planned), and the gate cannot PASS — reported as such, not invented.

**What follows a valid FAIL, in order and each under its own ruling:** (1) the record stands as the result of protocol v0.1.16; (2) a revision, if the owner wants one, is proposed separately with its estimand / design argument and the disclosure of the exploration's and the gate's influence, under a new label (the thresholds table and the architecture revised together, which is where section 6 applies); (3) nothing of the carrier, the board or the routing line moves on the strength of a FAIL or of a revision proposal.

## 5. Acceptance of the executed unit (when, and only when, the execution is authorised)

1. The tool's outputs as written: the batch archive (`sim_report.json` and everything it indexes), the gate directory (`gate_report.json`, `gate_report.md`), and the captured stdout / stderr / exit status. No file is edited. If section 3's refusal / initialisation-failure / abrupt-termination row applies, the acceptance stops at "keep, inventory, report" and the verifications below are run for the record only.
2. **Two fresh-process verifications, before the commit**: `python3 -B b4/host/b4_sim_verify.py evidence/b4/sim/b4-gate-1_<UTC>` (deep: the archive re-executed on the formal model, the summary recomputed) and `python3 -B b4/host/b4_gate_verify.py evidence/b4/gate/b4-gate-1_<UTC>` (deep: the batch re-verified, the judgement recomputed row by row, the markdown re-rendered). Both exit codes and outputs kept with a three-line header (HEAD, command, UTC). These two are the verification of record (the owner's choice, 2026-10-20).
3. **The raw results committed locally**: the archive and the gate directory exactly as the tool wrote them (one commit), then the verification outputs, the captured command output and the unit README (the run record, the identity the manifest recorded — the execution HEAD, the tool digests, the receipt, the registry snapshot — the verdict and every row copied, not summarised, and the disposition of section 3) in a second commit. **After the commit, the committed bytes are compared to the verified files by Git-blob digest** (`git ls-tree -r <commit>` / `git hash-object` against the files the verifiers read); equality is recorded and **no second full deep-verification round is run because bytes were committed unchanged**. If anything changed between the verification and the commit, the reason is recorded and the verification is repeated. The evidence directory of the executed unit: `evidence/b4/unit_gate1_execution_<date>/`; the archive and the gate directory stay in their own namespaces.
4. **The execution authorisation is the last, separate, independent gate**: this plan's acceptance runs nothing; a later ruling names the execution HEAD, the deadline and the date; the run happens once, on that tree, with no smoke test before it, after the operator's stop of section 2.3 found no difference.

## 6. The version coupling — the owner's ruling, the baseline, and a future scheme (none of it implemented here)

**The fact.** `b4_thresholds.THRESHOLDS["source"]` carries the architecture's revision text ("section 9 (v0.1.16)"); every archived batch's manifest and report embed the whole table, and the archive-wide verifier compares them to the module's current table (`b4/host/b4_sim_verify.py:230`: `if _j(manifest["thresholds"]) != _j(th.THRESHOLDS) … "the thresholds table is not the module's"`). So **a changed table cannot re-verify an older archive with the newest verifier.**

**The owner's ruling (2026-10-20):** this coupling does not block the current version's gate — the gate runs under the table as it stands and is verified by the verifier as it stands. What the coupling must block is an **unruled revision**: changing the table silently would make every archived summary stop verifying and would re-judge old archives under new numbers.

**The baseline of this unit:** `00336d0` — the accepted tool, its verifier and its evidence. The existing table, the architecture document, the S = 32 archive and every old manifest stay **exactly as they are**; nothing is deleted from the version text, no old manifest is edited, no compatibility migration is written. Re-verification of any archive produced under this version is done with the tool at this baseline (or at the execution HEAD, whose tool bytes the operator's stop of section 2.3 holds equal to the baseline's).

**A future versioning scheme (options for a separate design and ruling; none chosen here):**

| option | what it keeps | what it costs |
|---|---|---|
| A — re-verify at the recorded HEAD | every manifest already records the HEAD and the tool digests; an old archive is re-verified by checking out that HEAD (`git worktree add <dir> <head>`) and running its own verifier; the current verifier refuses it by name, as today | nothing in the code; a documented procedure and a test that the recorded HEAD's tree reproduces the recorded tool digests |
| B — a table registry by digest with version selection | `b4/thresholds_versions.json`: each protocol version's table digest with its architecture revision; an archive whose embedded table hashes to a registered version is verified **and judged under that version's whole stack** — the schema validators, the summary recomputation (`summarise_batch` and the thresholds it reads), the K-row judgement and the gate report validator all read the current module's table and method today, so version selection must cover every stage that reads it, not the two comparisons at line 230 | a separate design unit: the version-selection mechanism across the verification / judgement stack, a test per registered version, the registry pinned like the table; old archives and their bindings stay intact |
| C — the version out of the table | the revision text moved from the table into the manifest beside it, so that a documentation-only revision does not change the table's digest; a numeric change still does | a schema bump (manifest 1.2.0), the pin test adjusted, and **every existing archive stays on the old schema** — read by version, never rewritten |

Whichever is chosen, the invariant is the one the owner states: an old archive is judged under the table it was produced with, and a table change is a ruled revision with its reason, under a new commit, re-run and re-reported, never silent (§9's rule, B3's verbatim).

## 7. The dependency graph (the owner's ordering of 2026-10-20; nothing assumed frozen that is not)

```
[2c-obs] the observation contract of 2c (host-only; needs nothing from G):
         A2's positive-control addresses per semantic, A3's raw-observation schema,
         A8's initialisation observation design, the universe / holdout choice
      │
      ▼
[CV2] carrier v2 design: RTL, bench, XDC, isolation — against A1–A8
      │
      ▼
[2d-F8B3] provisioning F8B3 (control plane, boardid, role) → carrier bring-up on F8B3
      │
      ├──────────────► [A8] the two restore demonstrations on the board; A2 on the board for the named addresses
      │                      │
      └──────────────► [QC] the carrier's qualification and calibration (rate, split) — a node without a stage:
                             │ which lifecycle stage it is, and with what tool, is the unresolved B4 lifecycle's
                             │
[G] production gate b4-gate-1 (this plan; its execution a separate ruling)
      │ gives: every row's status, B* / N (or null), the verdict
      ▼
[2c-rest] the rest of 2c: prediction, main seeds, N / B* (from G), sessions, calibrated rates (from QC)
          — FROZEN only when the B4 lifecycle (unresolved; B3's S0 init / S1 freeze / S2 qualify / S3 plan
          is the historical reference, not a decision for B4) says at which stage, with what tool
      │
      ▼  (with A8 and QC)
[sessions] the B4-FF sessions on 17A6 (each its own ruling pair)

[B4-R] the routing study — its OWN preregistration and ruling pair, after R1–R7, PLUS the shared prerequisites:
       the provisioning and the current-limited 5 V supply's bench measurements of 2d (08EB labelled, provisioned
       with role=sacrificial, the regression re-run), the contention checker's routing coverage assessed, the
       isolation / bounded-exposure / blacklist / power-cycle mechanisms built, and the roadmap's standing interlocks
       (docs/board_roles.md; roadmap §4 hard lines 1–2; architecture §3's prohibitions) — then the escalation ladder:
       readback-only → certified compositions → unconstrained, on 08EB only
```

Edges, and what each one does **not** imply:

- **`G → 2c-rest` only.** The gate's B* / N feed the prediction and the sessions; **`2c-obs` does not depend on G** and can be written now, host-only. (v0.1's diagram drew an arrow from G into the observation contract; that was wrong and is corrected here.)
- **`2c-obs → CV2`**: the carrier is designed against an observation contract written first (A1–A8, §5.5); **the full 2c freeze is not assumed to precede the RTL** — `2c-rest` and the freeze attach where the B4 lifecycle (unresolved) puts them.
- **`CV2 → 2d-F8B3 → bring-up → A8 / QC`**: board work, each step its own ruling; A8 (the INIT / SRVAL restore demonstrations) is the open design question of `2c-obs` and an acceptance condition of the carrier; `ff_init`'s K9 row is conditional on it.
- **`QC`** is the qualification / calibration node and nothing more here: its stage, its tool and its binding to the manifest are the unresolved B4 lifecycle's to rule; **no rate is borrowed from B3** and no "S2-equivalent" is asserted.
- **`B4-R`** has its own preregistration and its own R1–R7, and it **also** depends on the shared provisioning and power-measurement work of 2d and on the roadmap's standing interlocks; the FF class completing satisfies none of those conditions; the routing study never becomes the baseline of the map-guided vs random-safe comparison; no routing-class write anywhere before its preregistration is frozen and ruled; nothing here authorises any routing work.

## 8. What this plan does not do

It runs nothing, derives nothing, prints no seed, changes no program, no table, no architecture text and no archive; it predicts no outcome; it authorises nothing — the execution (with its HEAD, deadline and date), a revision, the carrier, 2d, the routing study, push and merge each remain the owner's. Its numbers are costs estimated from one S = 32 run on one host, with the uncertainty stated.

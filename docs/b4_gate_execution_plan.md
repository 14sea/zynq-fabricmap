# B4 — the execution plan of the production gate `b4-gate-1` (DRAFT v0.1, documents and read-only inventory only, 2026-10-20)

> **Authorisation.** The owner's ruling of 2026-10-20 after the gate tool's engineering acceptance (`19597e7` PASS; the tool, its verifier
> and its evidence at `00336d0`): this unit writes the plan and takes a read-only inventory. **It does not execute the gate, derive or print
> any seed, change any program, run any simulation, build RTL, touch a board, push or merge.** The execution itself remains a separate,
> last, independent authorisation (section 5). Every number below that describes the run is an estimate from the S = 32 exploration of
> 2026-10-19; nothing here is a prediction of the gate's outcome.

## 0. Status index

| section | fixed | estimated | unresolved / for the owner |
|---|---|---|---|
| 1 the run's fixed conditions | S = 200, the model / method / thresholds of `00336d0`, the label, the soft-deadline policy | the wall time, the disk, the archive and verification costs | the deadline value (3 600 s recommended) |
| 2 the start and the evidence contract | what the pre-flight demands and what the manifest records | — | — |
| 3 the result paths | PASS / FAIL / invalid / incomplete, each with its disposition | — | what follows a valid FAIL (a separately proposed revision) |
| 4 the known risks | the exploration's K9 and K5 records, stated as records | — | nothing: no outcome is predicted |
| 5 acceptance | the tool's outputs, the fresh-process deep verification, the archive commit | — | the execution authorisation |
| 6 the version coupling | the owner's ruling; `00336d0` as the re-verification baseline | — | a future versioning scheme (options listed, none implemented) |
| 7 the dependency graph | the edges the architecture fixes | — | the B4 lifecycle; B4-R's own preregistration |

## 1. The fixed execution conditions

| item | value | source |
|---|---|---|
| label | `b4-gate-1` — the pinned gate label of section 9.2 (`b4_thresholds.THRESHOLDS["anchor"]["gate_label"]`); the tool refuses any other | `docs/b4_architecture.md` §9.2; `b4_gate.PINNED_GATE_LABEL` |
| S | **200**, planned — never the number completed (K6); the tool refuses any other `--seeds` | §9 K6; `b4_gate.S_GATE` |
| model, task, engine, controls | hypothesis v0.3 (`59948f9b…`), the certificate (`c69e419f…`), the task generator, the (μ, λ) = (4, 8) engine, the controls of §8 — exactly as committed at `00336d0`; **unchanged by this unit** | `b4/IMPORT.json` (52 entries) |
| thresholds | `b4_thresholds.THRESHOLDS`, "section 9 (v0.1.16), fixed before any exploration or gate run" — **unchanged**; the current protocol version is judged as it stands and a valid FAIL is a result of it (the owner's ruling of 2026-10-19 on the gate tool, section 1) | `b4/host/b4_thresholds.py` |
| the derivation | the gate's master and pairs by §9.2's anchor with the label beside it, against the exclusion set as pooled at the pre-flight (the 38 historical sources, the exposure receipt, every archived set under `evidence/b4/sim/`) — **performed by the harness at the batch's `init` and nowhere else; not here** | `b4_seeds.master_seed` / `pair_seeds`; `b4_sim.Batch.init` |
| the command | `python3 -B b4/host/b4_gate.py run --label b4-gate-1 --seeds 200 --deadline-s 3600` from the repository root on the clean committed tree (section 2); the batch under `evidence/b4/sim/b4-gate-1_<UTC>/` (mode `gate`), the judgement under `evidence/b4/gate/b4-gate-1_<UTC>/` | `b4_gate.main` |
| deadline | **3 600 s recommended**, the existing SOFT monotonic policy unchanged: counted from the pre-flight, checked before and after every arm, replay, snapshot, K9 pair, K10 unit, statistics unit and before every finalisation unit — including after the batch's own deep verification (R4) — a started unit never interrupted; an expiry makes the batch `incomplete` with everything on disk (section 3), never a loss | `b4_deadline`; `b4_sim` docstring (F8, R4) |
| one worker; nothing else in the repository during the run | the harness holds HEAD, every input digest, every tool digest and the registry snapshot at every pair's end and at the end (`input_drift` → `invalid`); the working tree must carry nothing but the batch's output at the end | `b4_sim.Batch.hold_inputs` / `hold_tree` |

### 1.1 Costs, estimated from the S = 32 exploration (`b4-sim-3`, 2026-10-19: 209.7 s, 643 files, 186 MB; its deep verification 79 s on this host)

| cost | S = 32 measured | S = 200 estimated (× 6.25) | note |
|---|---|---|---|
| the batch: seven arms, replay, K7, K9, K10 per pair, then the statistics | 209.7 s | **≈ 22 min** | the K5 scan is 8 … 200 per budget (1 000 bootstrap experiments each): the statistics stage grows more than linearly; count 25–30 min |
| the harness's own deep verification before publishing (`finish`, F4 / R4) | ≈ 79 s | **≈ 8 min** | inside the deadline: 30 + 8 ≈ 38 min against 3 600 s — the margin is ≈ 1.5×, which is why a smaller deadline is not recommended and a larger one is harmless (soft) |
| the judgement's self-validation (`b4_gate.write_judgement`: the verifier in process, deep) | — | ≈ 8 min | after the batch; not under the batch's deadline |
| the fresh-process verifications (section 5): `b4_sim_verify.py` on the batch, `b4_gate_verify.py` on the gate directory (deep) | 79 s | ≈ 8 min each | run twice as evidence (in place, and once more after the archive commit) |
| disk, the working tree | 186 MB, 643 files | **≈ 1.2 GB, ≈ 4 000 files** | `/home/test` had 495 GB free at this inventory |
| disk, the repository | the pack grew from 46 MB to ≈ 550 MB across the exploration and the fixture copies | **≈ +1 GB** in `.git` (JSON compresses poorly at this granularity) | a clone of `b4-prework` then carries ≈ 1.6 GB of B4 archives; acceptable for this line's evidence discipline (every seed, partial and stop record kept, the owner's ruling of 2026-10-19 §6), stated so that it is a decision and not a surprise |
| wall time, the whole unit | — | **≈ 60–70 min** of compute, plus the commits | the computer must not sleep during the batch (a monotonic-clock jump across a suspend has been seen to count against a soft deadline) |

## 2. The start and the evidence contract

**Before the command** (the operator's checklist; every item is also enforced by the tool):

1. `git status --porcelain` empty on `b4-prework` at the authorised HEAD — the harness refuses a dirty tree with no override; the gate's `judge` also refuses one.
2. No smoke test, no dry run, no mechanics batch beforehand on this tree: the first production call is the run. (A fixture batch would enter the registry and the exclusion set before the gate's draw; the owner's rule of 2026-10-19 §6: no pre-run, no S change.)
3. **No seed is derived or printed before the run**, by anyone, by any means: the derivation is the formal act of §9.2 and happens once, inside the batch's `init`, after `seeds.json` is the first file written and before any observation (the freezing order F9).
4. The identity the manifest will record is known in advance and is the baseline of section 6: HEAD `00336d0eadfcdfbd250003fc3ce0be530f68abf7` (or the authorised successor, if the owner names one); the tool files' digests as `b4/IMPORT.json` lists them (24 host modules); the exposure receipt `68764bbc1a51ec25…` (66 values); the registry snapshot `[evidence/b4/sim/b4-sim-3_20261019T121833Z, seeds, 1a0d1e7b91132ed6…]` (65 values); the pooled exclusion 2 224 values; the hypothesis and certificate digests above. **None of these is re-typed into the archive by hand: the manifest records what it reads.**
5. The deadline and the label on the command line; the output directories left to the tool's `<label>_<UTC>` default.

**What the run writes, and keeps whatever happens:** `seeds.json` (the 200 pairs, the anchor, the exclusion as pooled) → `manifest.json` (HEAD, every input digest, the external sources by absolute path and digest, the tool digests, the registry snapshot, the constants, the thresholds table) → per pair the seven arm results written exclusively before their audits, the audits, the controls, K7, K9, K10, the curves, the pair index → the statistics → `sim_report.json` (status; the pooled summary only when complete; the self-validation) and, when the batch did not complete, `STOPPED.json` naming the kind, the pair, the stage and the whole planned list. Then the gate directory: `gate_report.json` and `gate_report.md`. **Every seed, every partial, every quarantine and every stop record is kept** — nothing is redrawn, replaced, filled in or deleted.

## 3. The result paths — separate dispositions, none automatic

| batch status | verdict | what is done | what is NOT done |
|---|---|---|---|
| `complete`, archive clean, every row PASS, the budget rule PASS | **valid PASS** (`formal = true` on the pinned label, S = 200, a production archive) | archived and committed as section 5 says; the gate report's rows and B* / N become the inputs of unit 2c (section 7); a PASS is never read as evidence about the fabric | no session, no board, no prediction, no freeze follow from it without their own rulings |
| `complete`, archive clean, a row or the budget rule FAILS | **valid FAIL** — a result of this protocol version (the owner's ruling of 2026-10-19, section 1), confined to this model, public task / panel, operator / control design, budget grid and declared decision procedure (section 2 of that ruling) | archived and committed exactly as a PASS is; the rows that failed and the ones not assessable stated as the tool states them; B* / N kept null when the budget rule failed | **no threshold adjusted, no budget or sample repaired, no re-run, no relabel, no redraw, no S change** (§9.1); no claim that FF bits or the content class are indistinguishable in general; a protocol revision, if any, is **a separately proposed unit** that discloses the influence of `b4-sim-3` and of this gate's data and is never presented as validated by the data that motivated it |
| `invalid` (a DOMAIN or other refusal, a control failure, a replay or recompute finding, a quarantined result, an input drift, a schema finding, a self-validation finding) | `invalid` — a tool / source / replay / control contract break, never a landscape failure | archived with its `STOPPED.json`; the finding named; the unit halts and reports | not re-run under the same label; the next step is the owner's (a repair unit, then a ruling on a new label — `b4-gate-1` is consumed by its own records) |
| `incomplete` (the deadline, an external interrupt) | `incomplete` — unfinished work, never a result | archived with its `STOPPED.json` and every pair's work; the unexecuted pairs named | whether the unexecuted runs are resumed is decided separately (§9.1); no partial summary is read as a result; no automatic re-run |

In every case: `b4-gate-1`'s master and pairs, once drawn, are in the registry and the pooled exclusion of every later derivation — a stopped or invalid batch does not free its label (the owner's ruling of 2026-10-19 §6 for explorations; the same rule here).

## 4. The known risks, as records — not as a prediction

Stated so that a FAIL, if it comes, is not a surprise and not an excuse; nothing here says that S = 200 will FAIL or PASS.

- **K9 (b), `ff_srval`.** Under the fixed comparison set of §9.3, exactly half of each `ff_srval` address's applicable pairs have SR tied low, where SRVAL cannot affect the trace: a configuration-only upper bound of **0.5** on that semantic's coverage fraction (the owner's audit of 2026-10-19). The exploration's 32 seeds have median **0.427083** and maximum 0.479 — none reaches 0.5. The criterion is **≥ 0.50** (equality allowed): at S = 200 a PASS of this row needs at least 101 seed fractions exactly 0.5. The owner's ruling: the bound and the observed deficit are recorded separately; the bound does not prove a universal FAIL; this version keeps the comparison set and the threshold, and a valid FAIL is an acceptable result of it. `sr_kind`'s median was exactly 0.5 (meets the threshold as written).
- **K5, Δ1 = O − R.** On the S = 32 sample the primary's Cohen's d lay in −0.32 … +0.03 across the ten budgets, and the complete N scan 8 … 32 reached bootstrap power 0.000 … 0.064 (0.000 … 0.046 at N = 32), so no N existed and the budget rule's candidate did not exist. The owner's ruling: the K5 "impossibility" is not established — the scan is a bootstrap of the one-sided exact sign test on O − R, whose power depends on the sign / tie distribution and N (at B = 32 the sample had 10 positives, 9 negatives, 13 ties beside a slightly negative mean), finite bootstrap rates need not be monotone, and S = 200 changes the empirical distribution and the scan's limit; none of this guarantees a PASS, raises d or licenses extending the sample.
- **K1, K7, K8, K10** showed no deficit on the sample (K1 eligible at every budget; K7's prefix medians 2 … 21 across budgets, 16 at B = 128; K10 interacting 32 / 32); these are descriptive records too.
- **The budget rule.** If no budget has both K1 eligibility and an N, B* and N are null, K1–K5 and K7 are not assessable, K6 is not assessable (S = 200 as planned), and the gate cannot PASS — reported as such, not invented.

**What follows a valid FAIL, in order and each under its own ruling:** (1) the record stands as the result of protocol v0.1.16; (2) a revision, if the owner wants one, is proposed separately with its estimand / design argument and the disclosure of the exploration's and the gate's influence, under a new label (the thresholds table and the architecture revised together, which is where section 6 applies); (3) nothing of the carrier, the board or the routing line moves on the strength of a FAIL or of a revision proposal.

## 5. Acceptance of the executed unit (when, and only when, the execution is authorised)

1. The tool's outputs as written: the batch archive (`sim_report.json` and everything it indexes) and the gate directory (`gate_report.json`, `gate_report.md`). No file is edited.
2. **Fresh-process deep verification**, twice: `python3 -B b4/host/b4_sim_verify.py evidence/b4/sim/b4-gate-1_<UTC>` (the archive re-executed on the formal model, the summary recomputed) and `python3 -B b4/host/b4_gate_verify.py evidence/b4/gate/b4-gate-1_<UTC>` (the batch re-verified, the judgement recomputed row by row, the markdown re-rendered); both exit codes and outputs kept with a three-line header (HEAD, command, UTC).
3. **The raw results archived and committed locally** in two commits: the archive and the gate directory exactly as the tool wrote them; then the verification outputs and the unit README (the run record, the identity the manifest recorded, the verdict and every row copied — not summarised — and the disposition of section 3). The evidence directory for the executed unit: `evidence/b4/unit_gate1_execution_<date>/` (the archive and the gate directory stay in their own namespaces).
4. **The execution authorisation is the last, separate, independent gate**: this plan's acceptance does not run anything; a later ruling names the HEAD to run at, the deadline, and the date; the run happens once, on that tree, with no smoke test before it.

## 6. The version coupling — the owner's ruling, the baseline, and a future scheme (none of it implemented here)

**The fact.** `b4_thresholds.THRESHOLDS["source"]` carries the architecture's revision text ("section 9 (v0.1.16)"); every archived batch's manifest and report embed the whole table, and the archive-wide verifier compares them to the module's current table (`b4/host/b4_sim_verify.py:230`: `if _j(manifest["thresholds"]) != _j(th.THRESHOLDS) … "the thresholds table is not the module's"`). So **a changed table cannot re-verify an older archive with the newest verifier.**

**The owner's ruling (2026-10-20):** this coupling does not block the current version's gate — the gate runs under the table as it stands and is verified by the verifier as it stands. What the coupling must block is an **unruled revision**: changing the table silently would make every archived summary stop verifying and would re-judge old archives under new numbers.

**The baseline of this unit:** `00336d0` — the accepted tool, its verifier and its evidence. The existing table, the architecture document, the S = 32 archive and every old manifest stay **exactly as they are**; nothing is deleted from the version text, no old manifest is edited, no compatibility migration is written. Re-verification of any archive produced under this version is done with the tool at this baseline.

**A future versioning scheme (options for a separate ruling; none chosen here):**

| option | what it keeps | what it costs |
|---|---|---|
| A — re-verify at the recorded HEAD | every manifest already records the HEAD and the tool digests; an old archive is re-verified by checking out that HEAD (`git worktree add <dir> <head>`) and running its own verifier; the current verifier refuses it by name, as today | nothing in the code; a documented procedure and a test that the recorded HEAD's tree reproduces the recorded tool digests |
| B — a table registry by digest | `b4/thresholds_versions.json`: each protocol version's table digest with its architecture revision; the verifier accepts an archive whose embedded table hashes to a registered version and judges it under *that* table (never the current one) | a verifier change (the one place at line 230 and its twin for the report), a test per registered version, the registry pinned like the table |
| C — the version out of the table | the revision text moved from the table into the manifest beside it, so that a documentation-only revision does not change the table's digest; a numeric change still does | a schema bump (manifest 1.2.0), the pin test adjusted, and **every existing archive stays on the old schema** — read by version, never rewritten |

Whichever is chosen, the invariant is the one the owner states: an old archive is judged under the table it was produced with, and a table change is a ruled revision with its reason, under a new commit, re-run and re-reported, never silent (§9's rule, B3's verbatim).

## 7. The dependency graph (the owner's ordering of 2026-10-20; nothing assumed frozen that is not)

```
[G] production gate b4-gate-1 (this plan; its execution a separate ruling)
      │ gives: every row's status, B* / N (or null), the verdict
      ▼
[2c-obs] the observation contract of 2c (host-only): A2's positive-control addresses per semantic,
         A3's raw-observation schema, A8's initialisation observation design, the universe / holdout choice
      │                                   ╲
      ▼                                    ╲
[CV2] carrier v2 design: RTL, bench, XDC,   ╲  [2c-rest] the rest of 2c: prediction, seeds, N / B* (from G),
      isolation — against A1–A8               ╲   sessions, calibrated rates — FROZEN only when the B4 lifecycle
      │                                        ╲  (unresolved: B3's S0 init / S1 freeze / S2 qualify / S3 plan
      ▼                                         ╲ or its B4 form) says at which stage, with what tool
[2d-F8B3] provisioning F8B3 (control plane,      ╲        │
      boardid, role) → carrier bring-up on F8B3   ╲       │
      │                                            ╲      │
      ▼                                             ▼     ▼
[A8] the two restore demonstrations on the board; [B4Q] the carrier's qualification and calibration
     A2 on the board for the named addresses      (rate, split) — under the lifecycle's stage
      │                                                   │
      └──────────────────────┬────────────────────────────┘
                             ▼
                     [sessions] the B4-FF sessions on 17A6 (each its own ruling pair)

[B4-R] the routing study — INDEPENDENT: its own preregistration and ruling pair, after R1–R7
       (08EB labelled, provisioned with role=sacrificial, the current-limited 5 V supply MEASURED,
        the acceptance regression re-run, the contention checker's routing coverage assessed,
        the isolation / bounded-exposure / blacklist / power-cycle mechanisms built) ← [2d-08EB] ← the supply measurements
       then the escalation ladder: readback-only → certified compositions → unconstrained, on 08EB only
```

Edges, and what each one does **not** imply:

- `G → 2c-rest` only: the gate's B* / N feed the prediction and the sessions; **2c-obs does not wait for G** and can be written now (host-only).
- `2c-obs → CV2`: the carrier is designed against an observation contract written first (A1–A8, §5.5); **the full 2c freeze is not assumed to precede the RTL** — 2c-rest and the freeze attach where the B4 lifecycle (unresolved) puts them.
- `CV2 → 2d-F8B3 → bring-up → A8 / B4Q`: board work, each step its own ruling; A8 (the INIT / SRVAL restore demonstrations) is the open design question of 2c-obs and the acceptance condition of the carrier; `ff_init`'s K9 row is conditional on it.
- `B4Q` and the calibrated rates are the lifecycle's S2-equivalent; **no rate is borrowed from B3**.
- `B4-R` shares nothing with the FF line's progress: the FF class completing does not satisfy R1–R7; the routing study never becomes the baseline of the map-guided vs random-safe comparison; no routing-class write anywhere before its preregistration is frozen and ruled.

## 8. What this plan does not do

It runs nothing, derives nothing, prints no seed, changes no program, no table, no architecture text and no archive; it predicts no outcome; it authorises nothing — the execution, a revision, the carrier, 2d, the routing study, push and merge each remain the owner's. Its numbers are costs estimated from one S = 32 run on one host.

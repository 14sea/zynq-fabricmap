# B3 — the closed loop on the known 292 bits: preregistration (DRAFT v0.1.2, host-only, 2026-09-17)

> **v0.1.1 → v0.1.2 (the owner's review of `b729c39`).** B3Q's PASS count no longer counts
> the holdout twice (123 fitness values = 120 search + 3 champion holdout; 40 ledger entries;
> 2 baseline records; 125 records); arm-position equality holds when N is a multiple of 3;
> control X and H2 are as architecture v0.2.2 states them.

> **v0.1 → v0.1.1 (the owner's review of `4fbb305`, HOLD on six P2s).** (1) The gate's
> bootstrap algorithm and seeds are B2's by import (architecture §9); H9 is a sign test at
> every budget ≥ `B*`. (2) Control X is one fixed global derangement with a recorded digest.
> (3) The arm order is the fixed prefix-balanced sequence RFO, FOR, ORF, ROF, OFR, FRO —
> position counts differ by at most 1, equal only when N is a multiple of 6. (4) The ledger
> sub-block is on O **search** records only, under `specimen_ledger` 1.1.0 (a new schema
> file; the frozen 1.0.0 forbids the field); B3Q runs at budget **40** (the owner's choice):
> 123 scored records, 40 ledger entries, 125 records with the baselines. (5) The online map
> has its own schema and verifier, scored against the B1 truth mapping; passing B1's
> map-lifecycle verifier is not claimed. (6) The two-primary design is **conditional with a
> resolution rule** (§1): after the gate and before S1, v0.2 of this document states exactly
> one claim; and falsifier 2 attributes a wrong decode to the image only when the replay
> diverges. The 30 000 bound is a search-evaluation cap. Accepted as ruled: d ≥ 0.5, the
> 0.85 margin.

**Status: DRAFT v0.1.2 — not frozen, not owner-approved, NO BOARD RULING, NO IMAGE BUILT, NO GATE
RUN, NO PIN TABLE, NO MANIFEST.** This is step 1 of the B3 lifecycle as the pinned-surface
audit fixed it (`docs/b3_lifecycle1_pinned_surface_audit_2026_09_17.md` §8, PASS at `3a2063d`):
architecture v0.2 (`docs/b3_architecture.md`) and this draft, both unpinned by B2, for the
owner's review rounds. Numbers that the B3 gate (architecture §9) decides — the budget `B*`
and the pair count `N` — are **placeholders** marked `<gate>` and are filled in from the pinned
gate report before the S1 freeze; a draft that guessed them would be a number chosen before
the rule that chooses it. Frozen means the owner writes this document's sha256 into
`manifests/b3_manifest.json` (S1 of §8) and marks the image `board_ready`; until then nothing
may run. The structure and the wording follow `docs/b2_preregistration.md` v0.3 deliberately:
where a row is B2's unchanged, it says so.

## 1. The claim, in one sentence, and its scope

> On EBAZ4203 `17A6`, on the **B1 carrier** (its history certified by the B1 qualification
> chain; the B3 *image* qualified by its own B3Q session), the B3 image running B2's
> (μ + λ) engine, landscape (F1), population and seeds in **three arms per pair** — **R**
> random-safe (no map), **F** the frozen, board-built B1 self-map (`c6a4b23e…`, B2's arm B),
> **O** an online map that **starts empty and is built on the board from the search's own
> specimens** (every evaluation's child-readout ⊕ parent-readout, decoded by the specimen
> cartographer, `specimen-carto-v1.1`; no dedicated probe) — **reproduces on silicon, record
> for record and decode for decode, the host-predicted outcome** of `<gate>` preregistered
> landscape pairs at `<gate>` evaluations per arm: every run's best-so-far train fitness,
> every champion's holdout known answer, every O-arm decode, map version and anomaly count
> (predicted 0), and therefore the predicted primary or primaries fixed by the resolution
> rule below — **primary 1**, the one-sided exact sign test over the pairs' `Δ1 = best_O −
> best_R`; **primary 2**, the same test over `Δ2 = best_O − end_to_end_F`, the frozen arm
> charged B1's 333 mapping evaluations — and
> the host, recomputing every fitness and every behaviour delta from the served readouts,
> replaying the three searches and the ledger, and auditing every decode against the
> certificate, reproduces every choice and every map version the board reported.

**Resolution rule (fixed now; the branch is removed before freeze).** This draft carries a
conditional design and v0.2, written after the gate and before S1, carries exactly one claim:
if the gate's H9 holds, the claim requires **both** primaries and both are PASS rows of §4;
if H9 fails, the claim is **primary 1 alone**, Δ2 is reported in §4 as a non-required row, and
the sentence above loses its primary-2 clause. Either way the predicted primary or primaries
on the fixed board seeds must meet p ≤ 0.05 in the prediction (§3); if they do not, **the line
stops** — the seeds are not redrawn and N is not raised to reach a threshold.

What the claim rests on, and where each part is established:

- **that a correct map beats random-safe on this fitness and operator** — B2, on silicon
  (`docs/b2_result_2026_09_17.md`, p = 0.01953125): the historical premise, cited, not
  inherited as authority (§8a);
- **that a map built online from specimens beats random-safe from `B*` on, and beats the
  frozen map once its construction cost is charged** — established by the B3 gate over 200
  landscapes (architecture §9, H1–H9) — a *model* result whose arithmetic the board
  reproduces;
- **that the board builds its map autonomously from its own specimens under the interlocks
  and the model's arithmetic holds on silicon** — the board sessions (§4).

Scope: one die, one carrier, the content-bit class, the 292 attested addresses, F1, one
operator shape (B2 §5), one cartographer rule (architecture §3), the evaluation-count
accounting for primary 2 (architecture §10). Not claimed: generalisation (holdout is a
neutrality / known-answer control); a non-additive fabric (the anomaly path is tested, not
exercised by silicon); physical noise, timing, power, unattested bits, routing, FF, another
die, Linux, ICAPE2; the best online cartographer or operator; an independent silicon chance
of a negative primary (the deltas are fixed by the seeds and the exact prediction; a mismatch
is a HOLD / KILL of the instrument, §4); anything B4 asks.

## 2. Pins

| what | value |
|---|---|
| instrument | `zynq-psoracle` `689dde1dad374536c625bbe2b05986ee89eb4c94` (archived, read-only) — B2's |
| carrier, and its lineage | the B1 carrier `builds/b1/b1.bit` `d85daef4…`, `VARIANT` `0x42310001`; lineage exactly as B2 carries it (the B1 manifest by hash, its chain re-verified at every B3 manifest init / verify); **it qualifies nothing about the B3 manifest** |
| **the B2 authority, by content** | `manifests/b2_manifest.json` `aec84514ff29dda7957d46d650a370e155f6dc60a281b992e148f8a0fae6c4c0` (S3, closed) and `manifests/b2_instrument_pins.json` `82a5f2fb1d246c9cab506df65d53a0f329ca219ec3c5cdf50a272ff79ee319d1`; the B3 verify re-runs the B2 S3 verify and requires S3 / true / null / `aec84514…` (audit §7a). The B2 modules B3 imports (`host/b2_search.py`, `b2_landscape.py`, `b2_maps.py`, `b2_gate.py`, `host/b1_carto.py`, `b1_model.py`) are pinned through that table |
| **the B2 completion inputs** | `evidence/b2/b2_completion_inputs_2026-09-17/inputs.tar.zst` `20300d5f2476beafaa9411c11f2a412eb91f01149bf4318e79ccee2706337767` and `archive.json` `ca5fedd7bb7a119883a5b74a9f19b0d02d147e6183404ddde8766b03abd46c5d` — the 15 non-tracked files without which the B2 lineage does not verify; pinned by content, pre-checked by the B3 verify |
| **the B3 files the B2 verify reads** | `evidence/b3/sim/sim_report.json` `d9c432f8…`, `evidence/b3/sim/raw_F1.json` `ccf4d246…`, `schemas/specimen_ledger.schema.json` `7cc74295…` — pinned by content, never moved or rewritten |
| frozen host reference | `host/b3_online.py` `fd2f2759…`, `host/b3_sim.py` `bdfcc5fe…`, `tests/test_b3_online.py` `7ea1ef61…` — B2's pins; the B3 cartographer `b3/host/b3_carto.py` is a copy whose equivalence to the frozen module over the simulation seeds is a test |
| signer / validator | the B1 signer (`host/b1_sign_arm.py`, zero tables) and validator (`host/b1_records.py`) unchanged — B2's |
| B3 image | **not built.** When built: `b3/firmware/bsp/out/b3_app.bin`, sha256, size, ELF sha256, build evidence `evidence/b3/build_evidence.json` (toolchain, sources, BSP inputs, two clean builds) — pinned at S0 by `init` with a note that names the evidence (B2's image-record note contract), opened and hashed by every verify |
| map (arm F) | B1's `evidence/b1/b1_17A6_2026-09-08-02/self_map_v2.json`: canonical-JSON `c6a4b23e…`, file `b6607a9a…`; compiled as B2 compiled it (`B2_MAP_INIT` for the column view, `B2_MAP_LUT` for the universe mask only). **Arm O has no map pin: it starts empty** and a leakage test proves its view is empty at evaluation 0 and never reads `B2_MAP_INIT` |
| cartographer (arm O) | `specimen-carto-v1.1` (architecture §3): |M| = 1 decodes directly; |M| > 1 narrows by intersection with global closure; validate on a copy, commit only if consistent, else anomaly and nothing changes; version bumps on a decode |
| universe | 292 addresses, digest `895baf85…` (B1's, unchanged) |
| landscape rule, fitness | `host/b2_landscape.py` (B2's target rule; train = first 40 of the carrier order, holdout = last 24); **F1**, ceiling 40 — fixed by B2, not re-selected |
| engine | `b2-es-v1`: μ = 4, λ = 8, k ≤ 4, truncation, ties by age; base-initialised — B2's, unchanged; **the operator is the only difference between arms**, and for O the only difference from F is where the map comes from |
| budget | **`<gate>`** evaluations per arm per pair = `B*` by the frozen budget rule (architecture §9: smallest `N(B) × 3 × B` under H1); exploratory, not the gate: ≈ 1 000 |
| pairs | **`<gate>`** = `N(B*)` by the full ascending scan of the bootstrap power for Δ1 (α = 0.05, power ≥ 0.9, N ≥ 8); exploratory: ≈ 8 |
| bootstrap / power algorithm | B2's by import and pinned by content: `b2_gate.sign_test_p` (one-sided exact, ties excluded and counted); `b2_gate.required_pairs` — every N from 8 to S ascending, 1 000 experiments of a with-replacement resample of size N from the S paired Δ1, `random.Random(1 + N)`; the control-X null non-rejection with `bootstrap_reject_rate` seed 7; the gate report records the seeds |
| search-evaluation cap | `N × 3 × B*` ≤ 30 000 (H5); holdout evaluations, baselines and session record totals are outside it and are accounted by the plan |
| mapping cost charged to F | **333** evaluations (B1's budget: 9 code probes + 292 confirmations + 32 pairs) — an evaluation-count constant, carried in the IDENT |
| master seed | the first 4 bytes of sha256(`b3-session|` ‖ the instrument commit); pairs `(landscape, operator)` from one Rng stream; the fixed excluded seeds **and every archived set** explicitly excluded — B2's gate runs 1 and 3, the B3 simulation, **B2's 9 session pairs and its B2Q pair**, the B3 gate, the B3Q pair — `evidence/b3/plan.json` `seed_derivation` records every set; disjointness enforced, not assumed |
| arm order | pair r runs the fixed prefix-balanced sequence's (r mod 6)-th element: **RFO, FOR, ORF, ROF, OFR, FRO** — across any N the number of times an arm occupies a position differs by at most 1 between arms, and is equal exactly when N is a multiple of 3 (RFO, FOR, ORF already place every arm once in every position); the order is part of the plan and the prediction |
| records | **per pair 3 × B* + 3** (three searches + three champion holdout evaluations, no holdout-mode bit); **per session** 2 baselines + the session's pairs; the `ledger` sub-block is on the O arm's **B* search records only** (an O holdout record evaluates a finished genome and does not update the map), under `specimen_ledger` **1.1.0** at `b3/schemas/specimen_ledger.schema.json` (architecture §7); the frozen `schemas/specimen_ledger.schema.json` 1.0.0 stays as it is |
| online map document | `online_map` 1.0.0 (`b3/schemas/online_map.schema.json`) and its verifier `b3/host/b3_online_map.py`: schema, internal consistency, accuracy against the B1 truth mapping (host-only, post hoc). **Not** B1's map-lifecycle semantics (nine code probes, 32 interaction edges): neither required nor claimed |
| audit policy | **all-self-reporting** (B2's, the owner's decision of 2026-09-10): every record's six readout words served and host-verified; every fitness and every behaviour delta recomputed from measured readouts |
| session split (frozen rule, with a margin) | `b3/host/b3_plan.session_split`: a session holds the largest whole number of pairs whose **expected span** `records × 3600 / R_cal` ≤ 7 200 s; **`R_cal = 0.85 × R_measured`**, where `R_measured` is the B3Q-measured all-self-reporting rate written into the manifest's `calibration` (S2) by this lifecycle's own B3Q. *Why the margin (new in B3):* B2's two sessions ran at 2 630 / h and 2 724 / h against a B2Q calibration of 3 016 / h (0.87 and 0.90 of it); the 20-record B2Q was optimistic for long sessions, and session 1 exceeded 7 200 s (8 228 s) without violating its deadline. 0.85 is fixed here, before B3Q, and is not a calibration — the measured rate is. Not even one pair with its baselines fitting → **INFEASIBLE**, no plan, no S3. Until S2 the split is UNDETERMINED and the committed plan is the rate-less one (the committed-plan stage rule, B2 v0.3, verbatim; `b3/tests/test_b3_plan.py` holds the tree to it at every stage with `StageCoverage`) |
| deadline | per session, `1.25 × records × 3600 / R_cal + 600` |
| plan / prediction | `evidence/b3/plan.json`, `evidence/b3/prediction.json` (§3); the committed-plan stage rule as B2's |
| gate | `evidence/b3/gate/gate_report.json` under architecture §9, run after the criteria are committed — **not yet run** |
| manifest, pin table | `manifests/b3_manifest.json` (`b3/host/b3_manifest.py`: S0 init / S1 freeze / S2 qualify / S3 plan / verify with the §7a pre-check), `manifests/b3_instrument_pins.json` (`b3/host/b3_pins.py`, rule `b3/**/*` regular files + `docs/b3_architecture.md`) — do not exist until every pinned edit is done |
| transport | the CH340 single-byte-deletion stop-loss is **in force** (B2's exceptions were session-scoped and are spent); every B3 session's ruling pair carries its own transport disposition and its rel-v4 resend budget `N = ceil(4 × expected_frames / 1000)` from the production computation; no session runs without one |

## 3. The preregistered prediction (`evidence/b3/prediction.json`)

The reference (`b3/host/b3_plan.py` over `host/b1_model.py`'s fabric model — the certificate's
mapping, the model that predicted B1, P3 and B2) for the `<gate>` pairs, three arms, at
F1 / `B*`: every fitness in the sequence (`fitness_sequence_sha256`), every champion, every
champion's holdout value, and for the O arm every ledger entry — every `behaviour_delta`,
every decode, every map version, the final decoded count and the anomaly count (**0**).
From these: the per-pair `Δ1_r` and `Δ2_r`, the two predicted primaries with their exact
p-values, and the predicted final online map of every O run rendered as `self_map` 2.0.0
with its canonical digest — an `online_map` 1.0.0 document, not a `self_map`.

The table of predicted deltas is written here when the plan is generated, before S1, and
the resolution rule of §1 is applied to it in the same revision. **Because
the fitness and the decode predictions are exact, a board run that reproduces every predicted
record necessarily reproduces both primaries**; the session's information is the reproduction
itself (§4). The seeds are drawn once by the rule and not redrawn; N is the gate's number.

## 4. Metrics and the decision rule

All computed by `b3/host/b3_adjudicate.py` (B2's adjudicator is the template) over the host's
recomputation from the records. EXACT = equality with the pinned prediction.

| metric | definition | PASS |
|---|---|---|
| instrument | every session COMPLETED at its record count; the B1 validator's every rule; every record's readout served and verified; CRC / bad-frame budgets; the deadline | as the instrument's |
| binding | session B3, the seeds, the image, the frozen prereg, the S3 manifest's sha256, the instrument commit, the carrier hash and VARIANT, the lineage, the B2 authority digests, the B3Q record, the calibration and its margin, the map digest and the cartographer version in the IDENT | EXACT |
| fitness recomputation | for **every** record, F1 of the served readout = the record's fitness; the PL's additive `score_flat` = the additive count from the same readout | EXACT, per record |
| behaviour-delta recomputation | for every O-arm record, the served child readout ⊕ the served parent readout = the record's `behaviour_delta` | EXACT, per record |
| autonomy replay (search) | the reference, fed the served readouts, reproduces every parent draw, move, fitness, selection and champion in all three arms; the fitness sequence hash | EXACT, per record |
| **autonomy replay (ledger)** | the reference cartographer, fed the records' interventions and deltas, reproduces every `decoded`, every `map_version` / `map_version_after`, the anomaly count and the `state_sha256` projection at every step | EXACT, per record |
| **decode audit** | every decoded relation of every O run equals the certificate's (`local_map.json`, via `b1_model.truth_mapping`); wrong decodes = 0; the final online map, rendered as `online_map` 1.0.0, validates under the B3 online-map verifier and equals the predicted rendering (B1's map-lifecycle verifier is not applied) | EXACT (0 wrong) |
| anomalies | the anomaly count of every O run = the prediction (0) | EXACT |
| holdout known answers | each champion's holdout F1 on the hardware = the prediction | EXACT (3 × N values) |
| baselines | opening and closing baselines of every session equal, zero readout, the scorer's base counters | as B1 / B2 |
| **primary 1** | the exact sign test over the N pairs' `Δ1` (best-so-far train F1 at `B*`, O − R), one-sided, α = 0.05, ties excluded from *n* and counted — **pooled across sessions** | p ≤ 0.05, and equal to the predicted p |
| **primary 2** | the same test over `Δ2` (O at `B*` − F's own trace at `B* − 333`) | p ≤ 0.05, and equal to the predicted p — **a required row only if v0.2 claims it** (the resolution rule of §1: H9 held); otherwise reported, not required |

Verdict: **PASS** = every required row; the primaries are then the predicted ones, reproduced on
silicon. Any row failing is a **HOLD** (a rejection the validator names) or a **KILL** (a
falsification: a served readout contradicting a self-report — a fitness, a delta or a decode).
There is no third outcome (B2 §4, unchanged). A silicon experiment whose primary is *not*
fixed by the prediction is a separately preregistered design, not this one.

## 5. Falsifiers (of the instrument and of the model; the claim's arithmetic is fixed)

1. **A fitness or a behaviour delta differs from the recomputation** on any record — the fabric
   is not the additive model, or the image mis-computes. KILL if the served readout contradicts
   the self-report; HOLD otherwise; a finding per record.
2. **A wrong decode, or an anomaly, on silicon** — KILL, attributed by the replay: if the
   ledger replay **diverges** from the board's decode, the image is at fault (the cartographer
   twin is not the reference); if the readouts verify **and** the replay reproduces the same
   wrong decode, the reference itself decoded it from measured specimens, and the finding is a
   **certificate / fabric / model contradiction** (the additive model or the certificate is
   wrong for that address), not an image defect. An anomaly with readouts that verify and a
   replay that reproduces it is a HOLD and a finding about the fabric under this carrier (B1
   said additive; B3 does not claim otherwise, architecture §10).
3. **The ledger replay or the search replay fails** — the board did not follow the algorithm on
   its own observations (a parent, a move, a selection, a decode or a version the reference
   would not have made).
4. **Compatibility drift** — any pin of §2, the seven indirect frozen inputs, or the manifest
   lifecycle (§8) not verifying (a refusal by `b3_manifest.verify`, named).
5. **Leakage / attestation** — the image contains a LUT key, the certificate, the oracle
   rendering, or the online arm reads the compiled B1 map; a sign_reply with a non-zero table.
6. **The gate itself** — a re-run of the gate under rules the owner substitutes for
   architecture §9 in which H1–H8 fail; then B3 does not go to the board under this document.

## 6. The sessions and the rulings

**(a) Image qualification and calibration `B3Q`** — the B3 image on the qualified B1 carrier,
against the **S1 manifest** (`manifest_at_run.json` in the evidence dir): load and identity
(VARIANT, the map digest, the cartographer version, the arms, F1, `B*`, N, the slice), key
provisioning, the baselines, **one pair at budget 40 in all three arms** (the owner's choice:
3 × 40 + 3 = **123 scored records**, **40 ledger entries**, **125 records** with the two
baselines — enough O-arm records with ledger bytes for the rate to mean something), the
refused unsigned control; every record audited; PASS = the **123 fitness values (120 search
plus 3 champion holdout)**, the **40 ledger entries** (decodes, versions, 0 anomalies) and the
**2 baseline records** (zero readout, base counters) equal the prediction for the qualification
seeds (`b3-qualification|`, the same exclusions plus B3's own
set). The session's **measured all-self-reporting rate** goes into its adjudication and, on
pinning (S2), into the manifest's `calibration`; the split uses `0.85 × R_measured` (§2).

**(b) The closed loop `B3`** — as many sessions as the split rule gives, each under its own
ruling pair bound to the **S3 manifest** and carrying its own transport disposition; `17A6`,
`verify`; a fresh power cycle and boundary record per session; B2's fixed order; the host signs
zero tables, audits every record, collects; the adjudicator runs over the files as written. The
primaries are pooled over all sessions' pairs. A session lost is re-run for **the same pairs and
seeds** under a new ruling pair; never replaced by other seeds. **Stop immediately** on a
preflight refusal, KEY_NOT_LOADED, PAGE_MISMATCH, a U-Boot banner, the deadline.

**Stop-loss:** the instrument's (two sessions lost to the same cause → stop, fix host-side,
prove, review; three without COMPLETED → design review) and the transport's (in force). One
ruling = one session; a HOLD is never argued into a PASS.

## 7. Compatibility — what the new image owes

The B3 image is a successor of the B2 image (the third arm and the cartographer added; the
record's `search` block extended by the `ledger` sub-block on O-arm records; the IDENT
carrying the cartographer version, the arms and the mapping-cost constant). The owner's
**compatibility review** (the L6 / B1 / B2 list: the wire contract, the settle poll, the audit
service, the MMIO allowlist against the B1 RTL — unchanged RTL —, the DMA order, no ICAPE2,
no SLCR write, the watchdog gating) precedes `board_ready`. The B2 guards (verbatim imports,
header without tables, source include scan, binary scan extended to the cartographer's tables,
the certificate and the oracle rendering, C = Python twin — for the engine **and** the
cartographer —, the real application off-board, wire contract, fail-closed adjudication, pins)
are re-established for the B3 image before the image package is submitted.

## 8. The lifecycle and the freeze (`b3/host/b3_manifest.py`; to be exercised in `b3/tests/test_b3_lifecycle.py`)

B2's §8 table applies stage for stage — S0 init, S1 freeze, the B3Q ruling pair, S2 qualify,
S3 plan, the B3 ruling pairs, any later change refused — with these additions:

| where | addition |
|---|---|
| **S0 init** | pins, in its own block and by content, the seven indirect frozen inputs (§2: the B2 manifest and table, the completion-input archive and its manifest, the three B3 files the B2 verify reads); the B3 code pins by table (`b3/**/*`); the image from its build evidence with the note contract |
| **every verify** | the §7a pre-check first (existence and digest of the seven, named refusal), then the B2 S3 verify (required S3 / true / null / `aec84514…`, its refusal re-raised under the B3 name), then the B1 lineage; **any other exception is an INTERNAL ERROR**, never a refusal |
| **S2 qualify** | the calibration carries `rate_per_hour` (measured), `margin` (0.85, frozen here) and `rate_for_split`; the split rule and `plan_findings` use `rate_for_split` |
| **S3 plan** | `plan_findings` rebuilds the canonical plan **and the prediction including every ledger entry** and compares field for field; the arm order per pair is part of the plan |
| **the committed-plan stage rule** | B2 v0.3's, verbatim, held by `b3/tests/test_b3_plan.py` with `StageCoverage` at S0–S3 and against the forbidden pairings, before the pin table is generated (§9) |

Ordering (the audit's §8, each unit separately authorised, none authorising the next): the
owner's review of architecture v0.2 and this draft → every pinned edit (the `b3/` implementation,
the tests with the §9 audit, the image sources and build evidence, the gate run and its report,
`B*` and `N` written into this document) → the pin table generated **once** → S0 → the pre-freeze
proof (both start directories, discovery sentinel and removal control, zero skip / fail / error,
clean tree) → the owner's S1 freeze → the post-freeze proof bound to the S1 sha → the B3Q ruling
pair → B3Q → S2 → the S2 proof → S3 → the final proof → the B3 ruling pairs, one per session →
the result document.

## 8a. What B2 does not hand over — stated so it cannot be argued in later

**Not an input, not an authority (history only):** the four B2 rulings; the B2 calibration
(3 016.40 / h) and its split; the B2 session evidence and the pooled primary (p = 0.01953125),
bound to `aec84514…`; the B2 clean-tree proofs; the B2 transport exceptions (spent; the
stop-loss stands); every lifecycle-1 identity of B2. None of it qualifies, calibrates or
authorises anything about a B3 manifest.

**Carried as explicitly pinned inputs or historical premises:** the B1 lineage exactly as B2
carries it; the B2 engine, landscape, maps and gate code **by content** through the B2 table's
digest in the B3 table; the closed B2 manifest `aec84514…` at S3 and `docs/b2_result_2026_09_17.md`
as the historical premise that the frozen-map arm reproduces on silicon; the archived seed
sets as exclusion sets; the B2 image, its build evidence and BSP sources as the base the B3
image is diffed against; the instrument and the board as B2 pins them; the 15 completion
inputs through their archive.

## 9. Stage-aware tests — the rule applied before anything is frozen (audit §9)

Every B3 test that reads committed lifecycle state takes the stage from the production
`verify` and asserts what that stage licenses — never a literal stage, split status,
calibration, session count or history length; every such test is driven at S0, S1, S2 and S3
and against the illegal pairings before freeze; `skipUnless` on a committed artefact is not a
pass (zero skips in every proof); the values a legal transition changes are listed in §8 first
and a test may name only what §8 calls invariant; B2's stage is asserted only through the B3
manifest's pin of the B2 manifest; the frozen `tests/test_b3_online.py` is not a B3 test. The
pre-freeze audit of every B3 test against these rules is a written unit (the lifecycle-2
pattern, `docs/b2_lifecycle2_pinned_test_audit_2026_09_16.md`) and precedes step 3.

## 10. What is asked now

Decided by the owner on v0.1 (2026-09-17): d ≥ 0.5; the 30 000 search-evaluation cap; the
0.85 margin; B3Q at budget 40; the conditional two-primary design with the resolution rule;
control X as a fixed derangement; the prefix-balanced arm order. Asked now: the owner's review
of architecture v0.2.2 and this v0.1.2 — that the six P2s and the four points on `b729c39` are closed as written (§9's pinned
bootstrap and H9; control X; the arm order; the ledger scope and schema version; the online-map
verifier; the resolution rule and falsifier 2). Nothing else: no pinned edit, no gate run, no
pin table, no manifest, no image, no ruling, no board.

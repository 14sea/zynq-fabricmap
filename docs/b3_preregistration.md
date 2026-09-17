# B3 — the closed loop on the known 292 bits: preregistration (DRAFT v0.3.1 — lifecycle 2, host-only, 2026-09-17)

> **v0.3 → v0.3.1 — the lifecycle-2 gate and the prediction preflight, filled in (2026-09-17; the
> owner's release of the code unit at `825ecf2` and PASS on both runs).** Gate run 1 of lifecycle 2
> (`evidence/b3/gate_2/`, committed `a2beb8c`, on the clean tree `825ecf2`, label `b3-gate-2`,
> architecture v0.3 §9): **F1 PASS** on every row and the budget rule — **`B*` = 1 000** evaluations
> per arm (24 000 at 1 000 against 31 200 at 800, 36 000 at 1 500, 70 200 at 600), **N = 8**
> (bootstrap power 0.904 for Δ1 at α = 0.05; Δ1 over S = 200: 185 / 7 / 8, p 2.83e-46, Cohen's d
> 1.690), search cost **24 000 ≤ 30 000**; H4 O / F medians 19 / 21 = 0.905 with Δ2 124 / 55 / 21,
> p 1.34e-07 over S = 200; H7 288 decoded at `B*`, 0 wrong, 0 anomalies. **H9, the diagnostic, decided
> nothing and is reported:** Δ2 at 1 000 p 1.34e-07 but N₂ = 65 and a power of 0.150 at the gate's
> N = 8; at 1 500 / 2 000 / 3 000 p 0.0024 / 0.0147 / 0.224 with no N₂ within S = 200 — the
> secondary outcome is expected to be underpowered at N = 8, exactly as v0.3 accepted. F2 is
> information only (its `B*` = 2 000 costs 48 000 > cap). **The prediction preflight ran immediately
> after the gate** (`b3_plan.py`, committed `7cb0879`): the eight `b3-session-2` pairs, the
> prediction with every O-arm ledger entry embedded (8 × 1 000), Δ1 = [11, 9, 7, 7, 4, 6, 9, 2] —
> **the predicted primary 8 / 0 / 0, exact p = 1/256 = 0.0039 ≤ 0.05, SUPPORTED**; Δ2 = [−1, 7, 3,
> 6, −7, 0, 4, −1] — the secondary outcome, reported: 4 / 3 / 1, p 0.5, mean 1.375, median 1.5,
> d 0.301, no threshold. The stop rule (the primary alone, §3) did not fire; the canonical
> `evidence/b3/plan.json` / `prediction.json` exist. This revision fills the six `<gate-2>`
> placeholders (8 pairs, 1 000 evaluations per arm), pins the gate's, the raw files', the plan's
> and the prediction's digests and commits in §2, adds the committed eight-pair table to §3, and
> records the lifecycle's progress in §8 / §10. **Unchanged:** the claim, every threshold, the
> labels, the stop rule, the 30 000 cap, the 0.85 margin, the 7 200 s expected span, the transport
> conditions. The canonical plan is not re-run.

> **v0.2 → v0.3 — lifecycle 2 (the owner's ruling of 2026-09-17, after lifecycle 1 stopped at the
> prediction preflight: `docs/b3_lifecycle1_stop_decision_2026_09_17.md`, tag
> `b3-lifecycle-1-stopped-2026-09-17`).** Option 2 of the analysis the stop produced: **one
> confirmatory primary** — Δ1 = O − R, the one-sided exact sign test at α = 0.05 — and **Δ2 = O −
> end-to-end F becomes a preregistered secondary outcome**: its definition stays fixed, it is
> predicted per pair, and it is *reported* (positives / negatives / ties, the exact p, the effect
> size) with **no significance PASS threshold**; every value underneath it — records, replay,
> ledger, map, binding, and the prediction's per-pair Δ2 — must still verify EXACTLY. H9 stays as an
> S = 200 gate **diagnostic** and no longer decides the claim. The new gate derives `B*` and `N`
> **from Δ1 alone within the 30 000 cap** — lifecycle 1's B = 1 000 / N = 9 is the pilot's
> expectation and is not carried in. New labels: gate `b3-gate-2`, sessions `b3-session-2`,
> qualification `b3-qualification-2` (control X's `b3-gate-x` is tied to the instrument commit and
> is unchanged). The nine lifecycle-1 pairs and gate run 1 are **pilot / design evidence**: they
> informed this ruling, they enter every exclusion set, and they are never a sizing input (§8b).
> The two P2s the owner found on `b1b82d0` become requirements of §3 and §8 (every ledger entry in
> the prediction; the stop rule before any canonical write). Unchanged: the 30 000 search-evaluation
> cap, the 7 200 s expected span, the 0.85 margin, B3Q at budget 40, the stop rule and no redraw.
> Options 1 (more board time to reproduce model arithmetic) and 3 (a different estimand for Δ2)
> were rejected by the owner. **Nothing had run under v0.3 when it was written; the gate and the
> prediction preflight then ran under it on 2026-09-17 (the v0.3.1 note above).**

> **v0.1.2 → v0.2 (after gate run 1, `docs/b3_gate_report.md`, on the clean tree `f159dee`).** The
> gate decided what the draft left open: **`B*` = 1 000** evaluations per arm (the budget rule:
> min N(B) × 3 × B under H1 — 27 000 at 1 000 against 28 800 at 800 and 36 000 at 1 500),
> **N = 9** (bootstrap power 0.942 at α = 0.05), search cost 27 000 ≤ 30 000; every pass row H1–H8
> holds for F1 (F2 is reported: at its `B*` = 2 000 the cost 48 000 exceeds the cap). **H9 held**
> (Δ2 = O − end-to-end F: p 3.8e-9 at 1 000, 1.4e-4 at 1 500, 2.4e-3 at 2 000, 4.8e-3 at 3 000),
> so the resolution rule of §1 resolves to **both primaries, both required** — the conditional
> wording of v0.1.x is gone; there is one claim. The `<gate>` placeholders are filled; the
> gate's provenance is pinned in §2; nothing else changed.

> **v0.1.1 → v0.1.2 (the owner's review of `b729c39`).** B3Q's PASS count no longer counts
> the holdout twice (123 fitness values = 120 search + 3 champion holdout; 40 ledger entries;
> 2 baseline records; 125 records); arm-position equality holds when N is a multiple of 3;
> control X and H2 are as architecture v0.2.3 states them (the derangement's rejection sampling made unique there).

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

**Status: DRAFT v0.3.1 — lifecycle 2: the code unit accepted (`825ecf2`), the gate run
(`a2beb8c`) and the prediction preflight passed (`7cb0879`); not frozen, not owner-approved, NO
BOARD RULING, NO IMAGE BUILT, NO PIN TABLE, NO MANIFEST.** Lifecycle 1 (`docs/b3_lifecycle1_pinned_surface_audit_2026_09_17.md` §8 for the
lifecycle's shape; architecture v0.2.3 and draft v0.1.2 accepted at `1aa06f1`; gate run 1
`b7db6c7`; the plan tool `b1b82d0`) stopped at the prediction preflight and is closed at the tag
`b3-lifecycle-1-stopped-2026-09-17` (§8b). Lifecycle 2 restarted from step 1 on the
branch `b3-lifecycle-2`. **`B*` = 1 000 and N = 8** are the lifecycle-2 gate's numbers (§2), written
here after the run under architecture v0.3 and this document's rules — never guessed. Frozen means the owner writes this document's sha256 into
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
> for record and decode for decode, the host-predicted outcome** of **8** preregistered
> landscape pairs at **1 000** evaluations per arm: every run's best-so-far train fitness,
> every champion's holdout known answer, every O-arm decode, map version and anomaly count
> (predicted 0), and therefore the **one** predicted **primary** — the one-sided exact sign test
> over the N pairs' `Δ1 = best_O − best_R` — together with the predicted per-pair values of the
> **secondary outcome** `Δ2 = best_O − end_to_end_F` (the frozen arm charged B1's 333 mapping
> evaluations; reported, not a threshold) — and
> the host, recomputing every fitness and every behaviour delta from the served readouts,
> replaying the three searches and the ledger, and auditing every decode against the
> certificate, reproduces every choice and every map version the board reported.

**The claim's structure (v0.3, the owner's ruling).** One confirmatory primary, Δ1. Δ2 is a
preregistered **secondary outcome**: its definition (O's best-so-far at `B*` minus F's own trace at
`B* − 333`), its per-pair prediction and its reporting (positives / negatives / ties, the exact
one-sided sign-test p, the mean, median and Cohen's d of the paired differences) are fixed here;
**no board-session or pooled-result PASS threshold** is attached to it and no §4 PASS row depends
on its sign. (The pre-board model gate still has its own S = 200 row on Δ2 — architecture v0.3
H4's end-to-end half — which is a condition for going to the board at all, not a condition on the
board result.) The stop rule
applies to the primary: the predicted primary on the fixed board seeds must meet p ≤ 0.05 in the
prediction (§3); if it does not, **the line stops** — the seeds are not redrawn and N is not
raised. Lifecycle 1's two-primary design and the reason it could not be sized are in §8b.

What the claim rests on, and where each part is established:

- **that a correct map beats random-safe on this fitness and operator** — B2, on silicon
  (`docs/b2_result_2026_09_17.md`, p = 0.01953125): the historical premise, cited, not
  inherited as authority (§8a);
- **that a map built online from specimens beats random-safe from `B*` on** — to be established
  by the lifecycle-2 gate over 200 landscapes (architecture v0.3 §9, H1–H8; H9 is the
  end-to-end diagnostic) — a *model* result whose arithmetic the board reproduces; gate run 1
  of lifecycle 1 showed it under the same criteria and is pilot evidence (§8b), not this
  lifecycle's gate;
- **that the board builds its map autonomously from its own specimens under the interlocks
  and the model's arithmetic holds on silicon** — the board sessions (§4).

Scope: one die, one carrier, the content-bit class, the 292 attested addresses, F1, one
operator shape (B2 §5), one cartographer rule (architecture §3), the evaluation-count
accounting for the secondary outcome (architecture §10). Not claimed: generalisation (holdout is a
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
| labels (v0.3) | gate **`b3-gate-2`** (master = first 4 bytes of sha256(`b3-gate-2|` ‖ HEAD at the run) — run 1: 4260131137 from `825ecf2`); sessions **`b3-session-2`** (master 981420253); qualification **`b3-qualification-2`** (masters from the instrument commit); control X **`b3-gate-x`** unchanged (its seed is the instrument commit's, seed_x 2041341936; π `9cc0b64e…` recurred in run 1, re-derived in 2 attempts and recorded) |
| budget | **1 000** evaluations per arm per pair = `B*` by the frozen budget rule (architecture v0.3 §9: smallest `N(B) × 3 × B` under H1, N(B) sized on **Δ1 alone**) — the lifecycle-2 gate run 1 (`a2beb8c`): 24 000 at 1 000 against 31 200 at 800, 36 000 at 1 500, 70 200 at 600 (no finite N(B) below 600); lifecycle 1's pilot had given 1 000 too, as an expectation, not an input |
| pairs | **8** = `N(B*)` by the full ascending scan of the bootstrap power for Δ1 (α = 0.05, power ≥ 0.9, N ≥ 8) — the lifecycle-2 gate run 1: power 0.904 at N = 8 (Δ1 over S = 200: 185 / 7 / 8, Cohen's d 1.690); the pilot's N = 9 (power 0.942) was an expectation, not an input |
| bootstrap / power algorithm | B2's by import and pinned by content: `b2_gate.sign_test_p` (one-sided exact, ties excluded and counted); `b2_gate.required_pairs` — every N from 8 to S ascending, 1 000 experiments of a with-replacement resample of size N from the S paired Δ1, `random.Random(1 + N)`; the control-X null non-rejection with `bootstrap_reject_rate` seed 7; the gate report records the seeds |
| search-evaluation cap | `N × 3 × B*` ≤ **30 000** (H5, unchanged); holdout evaluations, baselines and session record totals are outside it and are accounted by the plan; the secondary outcome adds no evaluation (it reads the same runs' traces) |
| mapping cost charged to F | **333** evaluations (B1's budget: 9 code probes + 292 confirmations + 32 pairs) — an evaluation-count constant, carried in the IDENT |
| master seed | the first 4 bytes of sha256(`b3-session-2|` ‖ the instrument commit); pairs `(landscape, operator)` from one Rng stream; the fixed excluded seeds **and every archived set** explicitly excluded — B2's gate runs 1 and 3, the B3 simulation, B2's 9 session pairs and its B2Q pair, **the lifecycle-1 B3 gate run 1 (`b3-gate`, 200 pairs and master) and the lifecycle-1 nine session pairs and master (`b3-session`, the observed pilot)**, the lifecycle-2 gate (`b3-gate-2`), and the B3Q pair — `evidence/b3/plan.json` `seed_derivation` records every set; disjointness enforced, not assumed |
| arm order | pair r runs the fixed prefix-balanced sequence's (r mod 6)-th element: **RFO, FOR, ORF, ROF, OFR, FRO** — across any N the number of times an arm occupies a position differs by at most 1 between arms, and is equal exactly when N is a multiple of 3 (RFO, FOR, ORF already place every arm once in every position); the order is part of the plan and the prediction |
| records | **per pair 3 × B* + 3** (three searches + three champion holdout evaluations, no holdout-mode bit); **per session** 2 baselines + the session's pairs; total = 2 × sessions + N × (3 × B* + 3); the `ledger` sub-block is on the O arm's **B* search records only** (an O holdout record evaluates a finished genome and does not update the map), under `specimen_ledger` **1.1.0** at `b3/schemas/specimen_ledger.schema.json` (architecture §7); the frozen `schemas/specimen_ledger.schema.json` 1.0.0 stays as it is |
| online map document | `online_map` 1.0.0 (`b3/schemas/online_map.schema.json`) and its verifier `b3/host/b3_online_map.py`: schema, internal consistency, accuracy against the B1 truth mapping (host-only, post hoc). **Not** B1's map-lifecycle semantics (nine code probes, 32 interaction edges): neither required nor claimed |
| audit policy | **all-self-reporting** (B2's, the owner's decision of 2026-09-10): every record's six readout words served and host-verified; every fitness and every behaviour delta recomputed from measured readouts |
| session split (frozen rule, with a margin) | `b3/host/b3_plan.session_split`: a session holds the largest whole number of pairs whose **expected span** `records × 3600 / R_cal` ≤ 7 200 s; **`R_cal = 0.85 × R_measured`**, where `R_measured` is the B3Q-measured all-self-reporting rate written into the manifest's `calibration` (S2) by this lifecycle's own B3Q. *Why the margin (new in B3):* B2's two sessions ran at 2 630 / h and 2 724 / h against a B2Q calibration of 3 016 / h (0.87 and 0.90 of it); the 20-record B2Q was optimistic for long sessions, and session 1 exceeded 7 200 s (8 228 s) without violating its deadline. 0.85 is fixed here, before B3Q, and is not a calibration — the measured rate is. Not even one pair with its baselines fitting → **INFEASIBLE**, no plan, no S3. Until S2 the split is UNDETERMINED and the committed plan is the rate-less one (the committed-plan stage rule, B2 v0.3, verbatim; `b3/tests/test_b3_plan.py` holds the tree to it at every stage with `StageCoverage`) |
| deadline | per session, `1.25 × records × 3600 / R_cal + 600` |
| plan / prediction | **the preflight of §3, passed, committed `7cb0879`:** `evidence/b3/plan.json` `fbd922baff7f1463e76c209e1fcbf83d8b44976f1080aa228f4919b5b5805fb9` and `evidence/b3/prediction.json` `92b774ea62d290d380e72a4c990b384060db9006cf9160940fb4848ae4a14cf5` (the plan pins the prediction's sha256; the plan binds the gate report `8f717b12…`, `825ecf2`, architecture `f0f6b292…`, π `9cc0b64e…`); 8 pairs, 3 003 records per pair, 24 026 in a single session; the committed-plan stage rule as B2's — the split is UNDETERMINED until S2 (the rate-less plan is the committed one) |
| gate | **lifecycle 2, run 1 — committed `a2beb8c`, on the clean tree `825ecf2`:** `evidence/b3/gate_2/gate_report.json` `8f717b12bdc7258d49145bd47bbcfb8291d2b2a79cad42cb75491a19398fda90` (schema 2.0.0; `raw_F1.json` `631aac7119dc054b9db835a756e2fbc1f56b4071f027506b13d5a3630c08b0fc`, `raw_F2.json` `cba55465bde4a35c39cc33ce0a853db4a3db5f9ac85e0ded6d671a87732cbfe5`, each bound in the report by digest and row count; rendered `docs/b3_gate_2_report.md` `ce7433dd…`) under architecture v0.3 §9 (`docs/b3_architecture.md` `f0f6b2920f7f4c33b477cf6157fb5b0c675084f68ffc1b3a23f8f338a2ad72b5`, last commit `2663e15`) and the label `b3-gate-2` (master 4260131137, 200 pairs, 1 665 excluded values — every archived set incl. lifecycle 1's gate run 1 and its nine trial pairs): **F1 PASS** on every row and the budget rule, `B*` = 1 000, N = 8, cost 24 000; H9 as a diagnostic (the v0.3.1 note); F2 for information (`B*` = 2 000, cost 48 000 > cap: H5 FAIL, every other row PASS); wall 569.8 s. The plan and the renderer read it only through `b3_gate.validate_report` (provenance re-derived from `825ecf2`, the raw digests, `evaluate` re-run from the raw rows). **Run 1 of lifecycle 1** (`evidence/b3/gate/gate_report.json` `477225f5…`, on `f159dee`, architecture v0.2.3 `0713dee9…`: F1 PASS, B* = 1 000, N = 9, H9 held, control X π `9cc0b64e…`) is **pilot / design evidence** — it informed the v0.3 ruling and its 200 pairs are excluded; it is not this lifecycle's gate and not a sizing input |
| manifest, pin table | `manifests/b3_manifest.json` (`b3/host/b3_manifest.py`: S0 init / S1 freeze / S2 qualify / S3 plan / verify with the §7a pre-check), `manifests/b3_instrument_pins.json` (`b3/host/b3_pins.py`, rule `b3/**/*` regular files + `docs/b3_architecture.md`) — do not exist until every pinned edit is done |
| transport | the CH340 single-byte-deletion stop-loss is **in force** (B2's exceptions were session-scoped and are spent); every B3 session's ruling pair carries its own transport disposition and its rel-v4 resend budget `N = ceil(4 × expected_frames / 1000)` from the production computation; no session runs without one |

## 3. The preregistered prediction (`evidence/b3/prediction.json`)

The reference (`b3/host/b3_plan.py` over `host/b1_model.py`'s fabric model — the certificate's
mapping, the model that predicted B1, P3 and B2) for the 8 pairs, three arms, at
F1 / `B*` = 1 000: every fitness in the sequence (`fitness_sequence_sha256`), every champion, every
champion's holdout value, and for the O arm **every ledger entry, embedded in the prediction
document itself** — every `behaviour_delta`, every decode, every map version and the running
anomaly count, entry by entry (a digest and a count are not enough: `b3_plan.py` at `b1b82d0`
stored only those, the owner's P2, and v0.3 requires the entries) — the final decoded count and
the anomaly count (**0**), and the predicted final online map of every O run as an
`online_map` 1.0.0 document with its canonical digest (not a `self_map`). From these: the
per-pair `Δ1_r` and the **predicted primary** with its exact p; the per-pair `Δ2_r` and the
**secondary outcome's** predicted report (positives / negatives / ties, exact p, mean, median,
Cohen's d).

The table of predicted deltas is written here when the plan is generated, before S1. **The
stop rule is evaluated on the prediction before any canonical file is written**: `b3_plan.py`
computes the prediction, checks the primary against α, and writes `evidence/b3/plan.json` /
`prediction.json` only if it passes; on a stop it writes nothing to a canonical path and exits 3
naming the primary (the owner's second P2 on `b1b82d0`: the tool wrote first and checked
after). **Because the fitness and the decode predictions are exact, a board run that reproduces
every predicted record necessarily reproduces the primary and every secondary value**; the
session's information is the reproduction itself (§4). The seeds are drawn once by the rule and
not redrawn; N is the gate's number.

**The committed prediction (v0.3.1; the preflight of 2026-09-17, immediately after gate run 1,
committed `7cb0879`; `evidence/b3/prediction.json` `92b774ea…`, `evidence/b3/plan.json`
`fbd922ba…`).** Label `b3-session-2`, master 981420253, 8 pairs drawn with 2 066 excluded values
(every archived set, lifecycle 1's two sets, the lifecycle-2 gate's 200 pairs); F1 at `B*` = 1 000;
`fitness_sequence_sha256` `8df40ac9a75ca0f9bb965aa65239cb1ac9cd14681f47e219627a7e7543cfde13`
over 24 024 values (8 × (3 × 1 000 + 3)); every O run's 1 000 ledger entries embedded
(`specimen_ledger` 1.1.0), 0 wrong decodes, 0 anomalies, every online map verified. Best-so-far
train F1 at 1 000 per arm; `F end-to-end` = F's own trace at 667; the holdout known answers R / F / O:

| pair | (landscape, operator) | order | base | R | F | F end-to-end | O | **Δ1 = O − R** | Δ2 = O − F end-to-end | O decoded / map version | holdout R / F / O |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | (2961656459, 1343397103) | RFO | 1 | 6 | 22 | 18 | 17 | **+11** | −1 | 288 / 178 | 2 / 2 / 2 |
| 1 | (3785070923, 2731497693) | FOR | 2 | 10 | 16 | 12 | 19 | **+9** | +7 | 286 / 179 | 0 / 1 / 2 |
| 2 | (3587510309, 2084003005) | ORF | 2 | 12 | 19 | 16 | 19 | **+7** | +3 | 289 / 172 | 2 / 3 / 2 |
| 3 | (3491865220, 1136202755) | ROF | 2 | 13 | 20 | 14 | 20 | **+7** | +6 | 287 / 174 | 1 / 0 / 0 |
| 4 | (1595133113, 3832447288) | OFR | 2 | 8 | 21 | 19 | 12 | **+4** | −7 | 285 / 169 | 2 / 1 / 2 |
| 5 | (556892415, 1747787438) | FRO | 5 | 14 | 25 | 20 | 20 | **+6** | 0 | 290 / 175 | 0 / 0 / 1 |
| 6 | (2376967347, 1528092051) | RFO | 3 | 12 | 19 | 17 | 21 | **+9** | +4 | 290 / 187 | 0 / 0 / 1 |
| 7 | (205178539, 2230924639) | FOR | 2 | 17 | 21 | 20 | 19 | **+2** | −1 | 291 / 180 | 0 / 1 / 3 |

**The predicted primary** (Δ1, one-sided exact sign test, α = 0.05): **8 positives / 0 negatives /
0 ties, p = 1/256 = 0.00390625 ≤ 0.05 — SUPPORTED**; the stop rule did not fire. **The predicted
secondary outcome** (Δ2, reported, no threshold): 4 / 3 / 1, exact one-sided p = 0.5, mean 1.375,
median 1.5, Cohen's d 0.301 — consistent with the gate's H9 diagnostic (a power of 0.150 for Δ2 at
N = 8). On the board the primary's PASS is p ≤ 0.05 **and equal to this predicted p**; every
value of the secondary is EXACT to this table (§4).

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
| **primary** | the exact sign test over the N pairs' `Δ1` (best-so-far train F1 at `B*`, O − R), one-sided, α = 0.05, ties excluded from *n* and counted — **pooled across sessions** | p ≤ 0.05, and equal to the predicted p |
| **secondary outcome** (reported) | the N pairs' `Δ2` (O at `B*` − F's own trace at `B* − 333`): positives / negatives / ties, the exact one-sided p, mean, median, Cohen's d — **pooled across sessions** | every value EXACT to the prediction; **no significance threshold** (v0.3, the owner's ruling) |

Verdict: **PASS** = every required row; the primary is then the predicted one, reproduced on
silicon, and the secondary outcome equals its prediction. Any row failing is a **HOLD** (a rejection the validator names) or a **KILL** (a
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
seeds (`b3-qualification-2|`, the same exclusions plus B3's own
set). The session's **measured all-self-reporting rate** goes into its adjudication and, on
pinning (S2), into the manifest's `calibration`; the split uses `0.85 × R_measured` (§2).

**(b) The closed loop `B3`** — as many sessions as the split rule gives, each under its own
ruling pair bound to the **S3 manifest** and carrying its own transport disposition; `17A6`,
`verify`; a fresh power cycle and boundary record per session; B2's fixed order; the host signs
zero tables, audits every record, collects; the adjudicator runs over the files as written. The
primary and the secondary report are both pooled over all sessions' pairs. A session lost is re-run for **the same pairs and
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
| **the plan tool (v0.3, the two P2s of `b1b82d0`)** | (a) the prediction document embeds **every ledger entry** of every O run (`pairs[r].runs.O.ledger`, `specimen_ledger` 1.1.0 entries, B* per run) and `plan_findings` / the adjudicator compare them entry by entry, not by digest alone; (b) `b3_plan.py` evaluates the **stop rule before any canonical write** — no `evidence/b3/plan.json` or `prediction.json` exists on a stop, the CLI exits 3 naming the primary, and a trial run can only write to an explicit non-canonical `--out`; tests for both (an entry-level tamper named; a stopping prediction leaves the canonical paths absent) precede the pin table |

Ordering (the audit's §8, each unit separately authorised, none authorising the next): the
owner's review of architecture v0.3 and this v0.3 → the plan-tool repairs (the two P2s) → the
lifecycle-2 gate run under `b3-gate-2` and its report → **the prediction preflight immediately
after the gate** (the stop rule, before anything else is built) → `B*` and `N` written into this
document → every other pinned edit (records, session, adjudicator, runner, manifest, pins, test
report, the tests with the §9 audit, the image sources and build evidence) → the pin table
generated **once** → S0 → the pre-freeze
proof (both start directories, discovery sentinel and removal control, zero skip / fail / error,
clean tree) → the owner's S1 freeze → the post-freeze proof bound to the S1 sha → the B3Q ruling
pair → B3Q → S2 → the S2 proof → S3 → the final proof → the B3 ruling pairs, one per session →
the result document.

**Progress (v0.3.1, 2026-09-17):** the owner's review of architecture v0.3 and v0.3 — accepted at
`559294f`; the plan-tool repairs and the rest of §10's code unit — `c0a8bf9`, closed after four
owner HOLDs at `825ecf2` (the gate authority: a validator that re-derives the provenance from the
run's commit, binds every raw file by digest and re-runs `evaluate` from the raw rows, read by the
plan and the renderer alike; the H9 diagnostic's null power when no N₂ exists; lifecycle 1's
directories and every path under them refused; named `REFUSED:` exits; a no-clobber, atomic
publish by `RENAME_NOREPLACE`); the lifecycle-2 gate run under `b3-gate-2` and its report —
`a2beb8c`; the prediction preflight immediately after the gate — `7cb0879`, passed; `B*` = 1 000
and N = 8 written into this document — this revision. **Next:** every other pinned edit, then the
pin table once, then S0 — each unit separately authorised.

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

## 8b. Lifecycle 1 — provenance, and what it does not hand over (v0.3)

Lifecycle 1 (branch `b3-lifecycle-1`, closed at tag `b3-lifecycle-1-stopped-2026-09-17` →
`2504467`, not merged) ran: the pinned-surface audit (`3a2063d`), architecture v0.2.3 and this
document's v0.1.2 (`1aa06f1`), the `b3/` cartographer / online arm / control X / online map
(`25c7ede`), the gate code (`f159dee`) and gate run 1 (`b7db6c7`; F1 PASS, B* = 1 000, N = 9, H9
held), this document's v0.2 (`8b43205`), the plan tool and the prediction preflight (`b1b82d0`).
The preflight triggered v0.2's stop rule: primary 1 (Δ1) 9 / 0 / 0, p = 1/512; primary 2 (Δ2)
5 / 3 / 1, p = 93/256. The cause was structural — N was sized on Δ1 alone while Δ2 was required;
under the same bootstrap rule Δ2 needed N = 53 at B* = 1 000 (power 0.213 at N = 9), and Δ2
weakens with the budget as O's map completes, so no budget within the cap could carry both
(`docs/b3_lifecycle1_stop_decision_2026_09_17.md` §2 and the owner's ruling of option 2).

**Not an input, not an authority (history only):** gate run 1 and its `B*` / N (the lifecycle-2
gate derives its own under v0.3 and the label `b3-gate-2`); the trial prediction
(`evidence/b3/plan_trial_2026_09_17/`) and its nine pairs — an **observed pilot**, in every
exclusion set of this lifecycle and never a draw; every lifecycle-1 label (`b3-gate`,
`b3-session`); the v0.2 two-primary claim. **What the pilot did hand over, and how:** its
numbers informed the v0.3 ruling (the choice of one confirmatory primary) — a design decision
made before any lifecycle-2 gate or prediction, recorded here so it cannot be argued in later
as a result. **Carried unchanged:** units 1 and 2 (the namespace, the pin discipline, the
verifier contract, the authority boundary of §8a), the `b3/` code as reviewed — the gate and plan
tools then change under the next unit exactly as §10 lists (labels, rules version, H9 as a pure
diagnostic with N₂(B) and the gate-N power per budget, the renderer, the single-primary plan
contract, the new output paths), each change with a load-bearing test — architecture v0.3's
criteria other than H9's role, the frozen wrappers, B2's authority as §2 pins it.

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

Decided by the owner (2026-09-17): option 2 — one confirmatory primary Δ1; Δ2 a reported secondary
outcome with a fixed definition and no threshold; H9 a gate diagnostic; the new gate sizes Δ1
within the unchanged 30 000 cap; new labels; the lifecycle-1 pairs and gate run 1 as pilot /
design evidence in the exclusion set; 7 200 s, 0.85, B3Q at 40, the stop rule and no redraw
unchanged. Asked now: the owner's review of this v0.3 and of architecture v0.3 (H9's role, the
labels, §11) — **documents only; no gate, no prediction, no code change under this unit**. After
the review, in order: **the code unit** — (i) the plan-tool repairs of §8 (every ledger entry in
the prediction with entry-level comparison; the stop rule before any canonical write); (ii) the
gate tool: label `b3-gate-2`, rules version `architecture v0.3 §9`, lifecycle 1's gate run 1 and
nine pairs in the exclusion, `H9_claim_condition` replaced by a pure diagnostic, N₂(B) and the
gate-N power for Δ2 computed and reported per budget, output to **`evidence/b3/gate_2/`** and a
separate rendered report **`docs/b3_gate_2_report.md`** (lifecycle 1's `evidence/b3/gate/` and
`docs/b3_gate_report.md` are never overwritten); (iii) the renderer no longer prints "H9 holds /
fails"; (iv) the plan tool: labels `b3-session-2` / `b3-qualification-2`, `primary_2` and
`both_required` and the "either primary stops" contract removed, one primary plus the secondary
report, the stop rule on the primary alone; (v) a load-bearing test for each of (i)–(iv) —
then the lifecycle-2 gate run, then the prediction preflight.

**Done (v0.3.1, 2026-09-17):** the review (`559294f`); the code unit, (i)–(v) and the owner's four
HOLDs closed (`c0a8bf9` → `825ecf2`, released); gate run 1 (`a2beb8c`: F1 PASS, `B*` = 1 000,
N = 8, cost 24 000; H9 reported); the prediction preflight (`7cb0879`: the primary 8 / 0 / 0,
p = 1/256, SUPPORTED; the secondary 4 / 3 / 1, p 0.5, reported; the canonical plan and prediction
written); and this revision (the placeholders filled, the digests pinned in §2, the eight-pair
table in §3). **Asked now:** the owner's review of this v0.3.1 — documents only; the canonical plan
is not re-run. **After it, in the §8 order:** the remaining pinned edits (records, session,
adjudicator, runner, manifest, pins, test report, the tests with the §9 audit, the image sources and
build evidence), then the pin table generated once, then S0 — each a separately authorised unit.

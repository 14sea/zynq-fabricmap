# B2 — map utility on the known 292 bits: preregistration (DRAFT v0.2, host-only, 2026-09-10)

**Status: DRAFT — not frozen, not owner-approved, NO BOARD RULING, NO IMAGE BUILT; the
package is under the owner's HOLD (`docs/b2_b3_host_review_2026_09_10.md`).** v0.2 is the
correction batch after that review: the audit policy is **all-self-reporting** (the owner's
decision), the replay contract is stated in terms of measured readouts, the silicon run is
described as a **prospective reproduction of a predicted outcome** (not as a fresh chance
of a negative), the session split is a frozen rule applied to a **B2Q-measured** rate, and
the qualification / calibration / plan lifecycle is specified and exercised on disk
(`host/b2_manifest.py`, `tests/test_b2_lifecycle.py`). Frozen means the owner writes this
document's sha256 into `manifests/b2_manifest.json` (S1 of §8) and marks the image
`board_ready`; until then nothing may run. The gate is `docs/b2_gate_report_v0.3.md`
(run 3's rows under rules v0.3, plus the predeclared control comparison G9); the
architecture is `docs/b2_architecture.md` v0.3.

## 1. The claim, in one sentence, and its scope

> On EBAZ4203 `17A6`, on the **B1 carrier** (its history certified by the B1 qualification
> chain; the B2 *image* qualified by its own B2Q session), the B2 image running the same
> (μ + λ) search engine with the same landscape, budget, population and seeds in both arms
> — the only difference being that arm B's mutation operator consults the **frozen,
> board-built B1 self-map** (canonical-JSON digest `c6a4b23e…`, file digest `b6607a9a…`,
> 292 confirmed relations) and arm A's does not — **reproduces on silicon, record for
> record, the host-predicted outcome** of 9 preregistered landscape pairs at fitness **F1**
> and 600 evaluations per arm: the predicted best-so-far train fitness of every run, every
> champion's holdout known answer, and therefore the predicted paired differences and the
> predicted primary (the one-sided exact sign test over the 9 pairs, α = 0.05, ties
> excluded from *n* and counted); and the host, recomputing every fitness from the served
> readouts and replaying the search from the records, reproduces every choice the board
> made.

What the claim rests on, and where each part is established:

- **that a correct map beats random-safe on this fitness, and that the benefit is correct
  column grouping** — established by the gate over 200 landscapes (G1–G8 at
  `docs/b2_gate_report_v0.3.md`; G9 §4 there: the self-map beats train-membership-only and
  the within-train scramble); this is a *model* result, and its arithmetic is what the
  board reproduces;
- **that the board executes the search autonomously under the interlocks and the model's
  arithmetic holds on silicon** — the board session (§4).

Scope: one die, one carrier, the content-bit class, the 292 attested addresses, one fitness
(F1), one map (B1's), one operator shape (`docs/b2_architecture.md` §5). Not claimed:
generalisation (holdout is a neutrality / known-answer control for F1; architecture §8);
anything about F2 / F3 (they discriminate in simulation; not selected: total cost); the
best structured operator; timing or power behaviour ("phenotype" = the digital functional
observation); unattested bits, routing, FF, another die, Linux, ICAPE2, physical noise; the
closed loop (B3). Not claimed either: an independent silicon chance of a negative primary —
with fixed seeds and an exact fitness prediction the nine deltas are fixed (§3); a
mismatch is a HOLD / KILL of the instrument, not a result about the map (§4).

## 2. Pins

| what | value |
|---|---|
| instrument | `zynq-psoracle` `689dde1dad374536c625bbe2b05986ee89eb4c94` (archived, read-only) |
| carrier, and its lineage | the B1 carrier `builds/b1/b1.bit` `d85daef4…`, `VARIANT` `0x42310001`. **Lineage**: the B1 manifest (`manifests/b1_manifest.json`, by hash) and its standing qualification chain (`evidence/b1q/b1q_17A6_2026-09-08-01`), re-verified by `host/b1_qualification.verify` at every B2 manifest init / verify — it certifies the carrier's history under the B1 manifest; **it qualifies nothing about the B2 manifest** (the B1 verifier permits only its own two transition fields to change; a new image or plan is outside it). The B2 image is qualified by **B2Q** (§6) |
| signer / validator | the B1 signer (`host/b1_sign_arm.py`, zero tables) and validator (`host/b1_records.py`, rule iii-B1) unchanged |
| B2 image | **not built** — built only after the owner lifts the HOLD; its hash, ELF, build evidence and two-clean-builds proof go into the manifest at S0. Once pinned, every `verify()` opens the binary itself and compares its digest and size with both the manifest and the build evidence; the declaration alone never satisfies the check |
| map | `evidence/b1/b1_17A6_2026-09-08-02/self_map_v2.json`: canonical-JSON sha256 `c6a4b23e1871e1889621191d671886f804c88edaa9748119d9a5006fd0b64296` (sorted keys, no spaces — what the IDENT carries and the Python consumers compare), file-byte sha256 `b6607a9a4de4ec16b4441395703d353ba438463e3ff0be3b5984ec6f1f1bfa38` (what a file pin checks); both in the manifest. Compiled into the image as two tables, `B2_MAP_INIT` and `B2_MAP_LUT`, used for **different things and by different code**: the map-guided operator's column view is built from `B2_MAP_INIT` alone (the INIT index — the column), while `B2_MAP_LUT` is read only by `b2_universe_mask` to derive the set of writable (LUT, INIT) positions the public landscape rule masks its target to, so both arms face the same landscape (`tests/test_b2_leakage.py::test_the_operator_reads_only_the_column`). Neither is a LUT SITE KEY: those, the certificate and any polarity or group table remain forbidden and are scanned for |
| oracle rendering (host-only) | `57aaa412…`; agrees with the map in 292/292 relations — no oracle arm runs on the board |
| universe | 292 addresses, digest `895baf85…` (B1's, unchanged) |
| landscape rule | `host/b2_landscape.py`: target = the instrument's xorshift stream per (k, v), masked to the universe; train = the carrier's frozen order first 40, holdout last 24 |
| fitness | **F1** = Σ over train columns [W(v) = T(v)], ceiling 40 — gate-selected by the frozen order F2 → F1 → F3 under rules v0.3 |
| engine | `b2-es-v1`: μ = 4, λ = 8, k ≤ 4, truncation, ties by age; base-initialised (`host/b2_search.py`) |
| budget | **600** evaluations per arm per pair (B*, the cheapest discriminating budget under G1; `evidence/b2/gate/recomputed_2026_09_10/`) |
| pairs | **N = 9** (N(B*) by the full ascending scan: bootstrap power 0.934 at α = 0.05; the review's exact empirical power ≈ 0.927 at N = 9 vs 0.878 at N = 8 — a planning distribution, not guaranteed future power) |
| master seed | **716 169 644** = the first 4 bytes of sha256(`b2-session|` ‖ the instrument commit); pairs `(landscape, operator)` from one Rng stream; the fixed excluded seeds **and every archived run's seed set** (gate run 1, gate run 3, the B3 simulation: 1 223 values) explicitly excluded — `evidence/b2/plan.json` `seed_derivation` records the sets; disjointness is enforced, not assumed |
| arm order | pair r runs A then B when r is even, B then A when r is odd |
| records | **per pair 1 202** (2 × 600 search + 2 champion holdout evaluations, `mode_holdout` = 1); **per session** 2 baselines (opening, closing) + the session's pairs; total = 2 × sessions + 9 × 1 202 (one session 10 820; two 10 822; three 10 824) |
| audit policy | **all-self-reporting** (the owner, 2026-09-10): every record's six 64-bit readout words are served and host-verified (B1's `evidence.score.functional_readout`), so every fitness is recomputed from a *measured* readout. No sampled policy is specified for B2; one would need the fields, the sample rule, the mandatory audits and negative cases the review lists, demonstrated through the real exporter / adjudicator |
| session split (frozen rule) | `host/b2_plan.session_split`: a session holds the largest whole number of pairs whose **expected span** `records × 3600 / R` ≤ 7 200 s, pairs assigned in order, each session with its own baselines; if not even one pair with its baselines fits (R < 602 / h at 600 per arm) the rate is **INFEASIBLE** — a named state, no plan, no S3 (an empty feasible set is not permission to exceed the limit); a rate that is not a finite positive number is invalid; **R = the B2Q-measured all-self-reporting rate** written into the manifest's `calibration` (S2). Until then the split is **UNDETERMINED** (the plan says so). Planning rates only, not calibration: S #3 sampled ≈ 6 690 / h, B1's plan 3 368 / h, the last B1 mapping ≈ 2 807 / h observed — at 2 807 / h the rule gives 4 pairs per session, three sessions (4 + 4 + 1), 10 824 records; whether two sessions suffice is **not assumed** |
| deadline | per session, `1.25 × records × 3600 / R + 600` with the measured R |
| plan / prediction | `evidence/b2/plan.json` (split UNDETERMINED until S2; the S3 plan is regenerated with `--rate-per-hour` from the calibration and pinned), `evidence/b2/prediction.json` |
| gate | `evidence/b2/gate/recomputed_2026_09_10/gate_report.json` (rules v0.3 over run 3's rows; `controls_report.json` G9); run 3 as run (`evidence/b2/gate/gate_report.json`, rules v0.2) and run 1 (`v0.1_2026-09-10/`, rules v0.1) kept |
| manifest | `manifests/b2_manifest.json`, `host/b2_manifest.py` (S0 init / S1 freeze / S2 qualify / S3 plan / verify); does not exist until the image does |

## 3. The preregistered prediction (`evidence/b2/prediction.json`)

The reference engine over the fabric model (the certificate's mapping — the model that
predicted B1's 335 records and P3's 12 570) for the 9 pairs, both arms, at F1 / 600:
every fitness in the sequence (`fitness_sequence_sha256` over 10 818 values), every
champion, every champion's holdout value:

| pair | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| Δ = best_B − best_A | +2 | +5 | +6 | +3 | +4 | +6 | +1 | −2 | +5 |

Predicted primary: 8 positives, 1 negative, 0 ties, *n* = 9 → **p = 10/512 = 0.0195 ≤ 0.05:
SUPPORTED.** This is the exact sign test, not a "8 of 9" rule: with ties the threshold
moves (7 positives, 0 negatives, 2 ties would also pass with p = 1/128). On these seeds
one more negative would give p = 0.09. The seeds were drawn once by the rule and are not
redrawn; N = 9 is the gate's number, retained provisionally by the owner and not raised
because the prediction is visible. **Because the fitness prediction is exact, a board
run that reproduces every predicted fitness necessarily reproduces this primary**; the
session's information is the reproduction itself (§4).

## 4. Metrics and the decision rule

All computed by `host/b2_adjudicate.py` (to be written with the image; B1's adjudicator is
the template) over the host's recomputation from the records. EXACT = equality with the
pinned prediction.

| metric | definition | PASS |
|---|---|---|
| instrument | every session COMPLETED at its record count; the B1 validator's every rule; every record's readout served and verified; CRC / bad-frame budgets; the deadline | as the instrument's |
| binding | session B2, the seeds, the image, the frozen prereg, the S3 manifest's sha256, the instrument commit, the carrier hash and VARIANT, the carrier lineage, the B2Q record, the calibration, the map digests in the IDENT | EXACT |
| fitness recomputation | for **every** record, F1 of the served six-word readout = the record's fitness; the PL's additive `score_flat` = the additive count from the same readout | EXACT, per record |
| autonomy replay | the reference, fed the records' served readouts, reproduces every parent draw, move, fitness, selection and champion the board reported; the fitness sequence hash | EXACT, per record |
| holdout known answers | each champion's holdout F1 on the hardware = the prediction | EXACT (18 values) |
| baselines | opening and closing baselines of every session equal, zero readout, the scorer's base counters | as B1 |
| **primary** | the exact sign test over the 9 pairs' Δ (best-so-far train F1 at 600, B − A), one-sided, α = 0.05, ties excluded from *n* and counted — **pooled across sessions** | p ≤ 0.05, and equal to the predicted p |

Verdict: **PASS** = every row above; the primary is then the predicted one, reproduced on
silicon. Any row failing is a **HOLD** (a rejection the validator names) or a **KILL** (a
falsification: a served readout contradicting a self-report). There is no third outcome:
a run in which the bytes reproduce but the primary differs cannot occur (the primary is a
function of the bytes), and a run in which the bytes do not reproduce says nothing about
the map. If the owner wants a silicon experiment whose primary is *not* fixed by the
prediction, that is a separately preregistered design (e.g. seeds drawn on the board from
a hardware source under its own controls), not this one.

## 5. Falsifiers (of the instrument and of the model, since the claim's arithmetic is fixed)

1. **A fitness differs from the recomputation** on any record — the fabric is not the
   additive model (B1 said it is, 292/292 and 32/32), or the image mis-computes F1. KILL if
   the served readout contradicts the self-report; HOLD otherwise; a finding per record.
2. **The autonomy replay fails** — the board did not follow the algorithm on its own
   observations (a parent, a move or a selection the reference would not have made).
3. **Compatibility drift** — any pin of §2, or the manifest lifecycle (§8), not verifying
   (a refusal by `b2_manifest.verify`).
4. **Leakage / attestation** — the image contains a LUT key, the certificate or the oracle
   rendering (the target is derived on the board from the landscape seed by the public rule;
   the *certificate* must not be there); a sign_reply with a non-zero table word.
5. **The gate itself** — a re-run of the gate under rules the owner substitutes for v0.3
   (the review allows rejecting any revision) in which F1 fails; then B2 does not go to the
   board under this document.

## 6. The sessions and the rulings

Board sessions, each with its own ruling pair, in this order:

**(a) Image qualification and calibration `B2Q`** — the B2 image on the qualified B1
carrier, against the **S1 manifest** (a copy `manifest_at_run.json` in the evidence dir):
load and identity (VARIANT, the map's canonical digest, the fitness id, budget and pair
count in the IDENT), key provisioning, the baselines, **one pair at budget 8** (16 search
records + 2 holdout), the refused unsigned control; every record audited; PASS = the 18
fitness values and the champions equal the prediction for the qualification seeds (derived
under `b2-qualification|` with the same explicit exclusions plus B2's own set). The session's
**measured all-self-reporting rate** goes into its adjudication and, on pinning (S2), into
the manifest's `calibration`. A short all-audited B2Q measures the all-self-reporting
throughput; it says nothing about a sampled policy.

**(b) Map utility `B2`** — as many sessions as the split rule gives from the calibration,
each under its own ruling pair bound to the **S3 manifest**; `17A6`, `verify`; a fresh
power cycle and boundary record per session; the fixed order (precheck → identity → dcache
off → clock preflight → carrier load → key provisioning → identity page (the session's
pairs, seeds, budget, flags) → image load → `go`); the host signs zero tables, audits every
record, collects; the adjudicator runs over the files as written. The primary is pooled
over all sessions' pairs. A session lost to the instrument or the transport is re-run for
**the same pairs and seeds** under a new ruling pair (the prediction is unchanged); it is
never replaced by other seeds. **Stop immediately** on a preflight refusal, KEY_NOT_LOADED,
PAGE_MISMATCH, a U-Boot banner, the deadline.

**Stop-loss (the instrument's, in force; the transport stop-loss of B1Q unresolved):** two
sessions lost to the same cause → stop, fix host-side, prove, review; three without
COMPLETED → design review. One ruling = one session; a HOLD is never argued into a PASS.

## 7. Compatibility — what the new image owes

The B2 image is a successor of the B1 image (the cartographer replaced by the search; the
record's `carto` block replaced by a `search` block carrying the fitness, the move and the
population state; the IDENT carrying the map digest, the fitness id, the budget and the
pair count). The owner's **compatibility review** (the L6 / B1 list: the wire contract, the
settle poll, the audit service, the MMIO allowlist against the B1 RTL — unchanged RTL, so
the B1 check stands —, the DMA order, no ICAPE2, no SLCR write, the watchdog gating)
precedes `board_ready`. The B1 guards that apply (verbatim imports, header without tables,
source include scan, binary scan — extended to the certificate and the oracle rendering —,
C = Python twin, the real application off-board, wire contract, fail-closed adjudication,
pins) are re-established for the B2 image before the image package is submitted.

## 8. The lifecycle and the freeze (`host/b2_manifest.py`; exercised in `tests/test_b2_lifecycle.py`)

| stage | who | what changes | what is checked from then on |
|---|---|---|---|
| **S0 init** | the tool, after the image is built | the manifest from the tree: the carrier lineage (B1 manifest by hash, its chain re-verified), the map's two digests, the universe, the experiment constants (F1 / 600 / 9), the engine, the seeds with their exclusions, the B2 code pins, the image from its build evidence | pins drift → refusal once frozen; lineage re-verified |
| **S1 freeze** | the owner, after the compatibility review | `prereg.sha256` = this document; `image.board_ready` = true | the first transition; a freeze on a manifest with a qualification or a plan is refused |
| **B2Q ruling pair** | the owner | bound to the S1 manifest's sha256 (session B2Q, image, prereg) | — |
| **S2 qualify** | the tool, after B2Q PASS | the B2Q record **reconstructed from the evidence files** (the exact file set by hash, the adjudication's outcome / measured rate / policy, the binding from `manifest_at_run`) **and** `calibration` derived from that reconstruction under the split rule, in one licensed transition | the current manifest must equal `manifest_at_run` outside {qualification, qualified, calibration, plan, status, history}; the embedded record must equal the reconstruction field by field; the binding must be this manifest's image / prereg / carrier / map; the policy must be the frozen one; the rate must be finite, positive and feasible; re-adjudication must PASS and agree on rate and policy (pluggable until the B2 adjudicator exists; without it, not qualified) |
| **S3 plan** | the tool | the plan regenerated with `--rate-per-hour` = the calibration and pinned (path, sha256, the prediction file's path and sha256, sessions, total records) | `plan_findings` — the same validator at pinning and at every verify — **rebuilds the canonical plan and prediction** from the frozen inputs and compares the whole structures field for field (schema and version, session, fitness, budget, pairs, engine, carrier, map, seed derivation, gate provenance, audit policy, record accounting, arm order, session split, span limit, deadline formula, planning-rate notes, the primary statistic with its α and tie policy, the architecture pin; and in the prediction every pair's runs, arm order, target, base fitness, delta, the aggregate deltas, the predicted primary and the sequence hash and length). Only `generated_utc` may differ; `prediction_sha256` must equal the sidecar's digest **and** the manifest's reference, so a relocated prediction is allowed only when it is the same bytes. A plan on an unqualified manifest, a second plan, or any other operational difference: refused |
| **B2 ruling pairs** | the owner | bound to the **S3** manifest's sha256 (session B2, master seed, image, prereg) | — |
| any later change | — | image, prereg, map, seeds, lineage, experiment, calibration, plan file, pin, a lying `qualified` flag; **and file-only changes with the manifest untouched**: a pinned implementation file deleted or changed, the frozen preregistration or the map file edited, the B1 manifest file edited, **the image binary deleted, truncated or replaced with the same number of different bytes** | **refused** by `verify`, which re-hashes every frozen input — the image binary included, opened and sized — and re-verifies the B1 chain fresh on every call (each case a fresh-process test) |

What this closes: the draft's earlier order ("freeze, then B2Q, then recompute the deadline")
edited the plan after the qualification; under B1's strict rule that would have
invalidated the binding. Now the plan is *produced* by the qualification's calibration and
that production is the licensed transition, checked field by field. The B1 verifier is not
relaxed (the lifecycle test asserts the B1 files are unchanged since `6ac2cf2`). Any
later change to this text is a new preregistration.

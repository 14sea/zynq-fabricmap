# B2 — map utility on the known 292 bits: preregistration (DRAFT v0.1, host-only, 2026-09-10)

**Status: DRAFT — not frozen, not owner-approved, NO BOARD RULING, NO IMAGE BUILT.** Frozen
means the owner writes this document's sha256 into `manifests/b2_manifest.json`
`prereg.sha256` (a manifest that does not exist yet — it is written when the image is) and
marks the image `board_ready`; until then nothing may run, and any number produced against
this draft is a pilot, not a result. Written after the discriminability gate passed for F1
(`docs/b2_gate_report.md`, run 3 at `7b49f4c`) under the architecture
`docs/b2_architecture.md` v0.2. B1's preregistration is the template; what differs is said.

## 1. The claim, in one sentence, and its scope

> On EBAZ4203 `17A6`, on the **qualified B1 carrier**, the B2 image running the same
> (μ + λ) search engine with the same landscape, budget, population and seeds in both arms
> — the only difference being that arm B's mutation operator consults the **frozen,
> board-built B1 self-map** (`c6a4b23e…`, 292 confirmed relations) and arm A's does not —
> reaches a higher best-so-far train fitness **F1** (exact column words over the 40 train
> vectors) at 600 evaluations per arm in more of the 9 preregistered landscape pairs than
> the sign test allows by chance (one-sided, α = 0.05: **≥ 8 of 9 non-tied pairs
> positive**); and the host, recomputing every fitness from the served readouts and
> replaying the search from the records, reproduces every choice the board made.

Scope: one die, one carrier (already qualified: `evidence/b1q/b1q_17A6_2026-09-08-01`, the
chain re-verified by the B2 runner), the content-bit class, the 292 attested addresses, one
fitness (F1), one map (B1's), one operator shape (§5 of the architecture). Not claimed:
generalisation (holdout is a neutrality / known-answer control — architecture §8); anything
about F2 / F3 (they discriminate in simulation but were not selected: session cost); the
best structured operator; unattested bits, routing, FF, another die, Linux, ICAPE2, physical
noise; the closed loop (B3).

## 2. Pins

| what | value |
|---|---|
| instrument | `zynq-psoracle` `689dde1dad374536c625bbe2b05986ee89eb4c94` (archived, read-only; the B1 pin table `manifests/b1_instrument_pins.json` re-used and extended for B2) |
| carrier | the B1 carrier `builds/b1/b1.bit` `d85daef4…`, `VARIANT` `0x42310001`; **qualified** through the evidence chain of `docs/b1_carrier_qualification.md` §4 (record `evidence/b1q/b1q_17A6_2026-09-08-01`, PASS, pinned in `manifests/b1_manifest.json` `38238271…`); the B2 runner and adjudicator re-verify the chain, never the flag |
| signer / validator | the B1 signer (`host/b1_sign_arm.py`, zero tables) and the B1 validator (`host/b1_records.py`, rule iii-B1) unchanged; a reply with attested tables is refused |
| B2 image | **not built** — built only after the owner's package review (`docs/b2_package.md`); its hash, ELF, build evidence and two-clean-builds proof go here at freeze |
| map | `evidence/b1/b1_17A6_2026-09-08-02/self_map_v2.json` sha256 `c6a4b23e1871e1889621191d671886f804c88edaa9748119d9a5006fd0b64296` (the board-authored B1 map; 292 confirmed, 0 anomalies, 32 edges none); compiled into the image as the column table of `docs/b2_architecture.md` §5 (`init_index` per genome bit — no LUT key); the image's IDENT carries the map hash |
| oracle rendering (host-only, the bound) | `57aaa412…`; agrees with the map in 292/292 relations (`docs/b2_gate_report.md`) — arms B and C are the same operator on the same relations, so no oracle arm runs on the board |
| universe | 292 addresses, digest `895baf85…` (B1's, unchanged) |
| landscape rule | `host/b2_landscape.py`: target = the instrument's xorshift stream per (k, v), masked to the universe; train = the carrier's frozen order first 40, holdout last 24 |
| fitness | **F1** = Σ over train columns [W(v) = T(v)], ceiling 40 (gate-selected by the frozen order F2 → F1 → F3) |
| engine | `b2-es-v1`: μ = 4, λ = 8, k ≤ 4, truncation, ties by age; base-initialised (`host/b2_search.py`) |
| budget | **600** evaluations per arm per pair (the gate's B*, the cheapest discriminating budget under G1) |
| pairs | **N = 9** (the gate's N(B*): bootstrap power 0.934 at α = 0.05) |
| master seed | **716 169 644** = the first 4 bytes of sha256(`b2-session|` ‖ the instrument commit); pairs `(landscape, operator)` from one Rng stream, excluded seeds skipped (`evidence/b2/plan.json` `seed_derivation`; gate seeds are under `b2-gate|HEAD` and disjoint) |
| arm order | pair r runs A then B when r is even, B then A when r is odd (drift is not confounded with the arm) |
| records | 1 opening baseline + 9 × 2 × 600 search + 18 champion holdout evaluations (`mode_holdout` = 1) + 1 closing baseline = **10 820** |
| audit policy | **the owner's choice, before freeze** (architecture §7 G5): *sampled audit* at the instrument's evidenced S #3 policy (≈ 6 690 records / h → expected span ≈ 1.62 h, deadline 7 878 s) or *all-self-reporting* (≈ 3 368 / h → 3.21 h, which does not fit one two-hour session and needs the session split under two rulings). Under sampled audit every record still carries the board's fitness and the readout **hash**; the served raw readouts of the audited sample are host-verified and any mismatch is a KILL (the instrument's falsification rule) |
| plan / prediction | `evidence/b2/plan.json`, `evidence/b2/prediction.json` (their hashes into the manifest at freeze) |
| gate | `evidence/b2/gate/gate_report.json` (run 3, rules v0.2, HEAD `7b49f4c`, clean tree, master 1 324 512 209), `docs/b2_gate_report.md`; run 1 kept at `evidence/b2/gate/v0.1_2026-09-10/` |

## 3. The preregistered prediction (`evidence/b2/prediction.json`)

The reference engine over the fabric model (the certificate's mapping — the same model that
predicted B1's 335 records and P3's 12 570) for the 9 pairs, both arms, at F1 / 600. On a
correct instrument the board reproduces every fitness in the sequence (`fitness_sequence_sha256`
over 10 818 values: 10 800 search + 18 holdout), every champion, and therefore every Δ:

| pair | Δ = best_B − best_A |
|---|---|
| 0..8 | **+2, +5, +6, +3, +4, +6, +1, −2, +5** |

Predicted primary: **8 positives, 1 negative, 0 ties → p = 10/512 = 0.0195 ≤ 0.05 →
SUPPORTED.** Stated plainly: this is the minimum that passes at N = 9. One more negative
pair would give p = 0.09 and NOT SUPPORTED. The seeds were drawn once by the rule and are
not redrawn; N = 9 is the gate's number, not a number chosen after seeing this table. If
the owner prefers a margin, the place to say so is the package review, before freeze, with
the reason recorded — and the cost is 2 × 600 evaluations per additional pair.

## 4. Metrics and the decision rule

All computed by `host/b2_adjudicate.py` (to be written with the image; B1's adjudicator is
the template) over the host's recomputation from the records. Rows marked EXACT are
equalities with the pinned prediction; the primary is a statistic.

| metric | definition | PASS |
|---|---|---|
| instrument | the run COMPLETED at 10 820 records; the B1 validator's every rule; audit sample verified; CRC / bad-frame budgets; deadline | as the instrument's |
| binding | session B2, the seeds, the image, the frozen prereg, the manifest's own hash, the instrument commit, the carrier hash and VARIANT, the carrier's qualification chain, the map hash in the IDENT | EXACT |
| autonomy replay | the reference, fed the records' readouts (audited ones served, the others by the board's readout hash), reproduces every parent draw, move, fitness, selection and champion the board reported; the fitness sequence hash | EXACT, per record |
| fitness recomputation | for every audited record, F1 of the served readout = the record's fitness; the PL's additive `score_flat` = the additive count from the same readout (the free known answer) | EXACT |
| **primary** | the sign test over the 9 pairs' Δ (best-so-far train F1 at 600, B − A), one-sided, α = 0.05, ties excluded | **p ≤ 0.05** (≥ 8 of 9 non-tied positive) |
| holdout known answers | each champion's holdout F1 on the hardware = the prediction | EXACT (18 values) |
| baselines | opening and closing baselines equal, zero readout, the scorer's base counters | as B1 |

Verdict: PASS = instrument + binding + replay + recomputation + holdout all EXACT **and** the
primary p ≤ 0.05. A run in which the bytes reproduce but the primary is not supported is a
**negative result for the claim on these seeds** (reported as such, not re-run on other
seeds). A run in which the bytes do not reproduce is a **HOLD / KILL of the instrument**, not
a result about the map.

## 5. Falsifiers

1. **The primary is not supported although every byte reproduces** — the map's benefit at
   this budget is smaller than the gate's simulation predicted, or these seeds are the
   ~7 % the gate's power leaves. Reported; a second experiment needs its own seeds by the
   rule and its own ruling.
2. **A fitness differs from the recomputation** — the fabric is not the additive model
   (B1 said it is, 292/292 and 32/32), or the image mis-computes F1. A finding per record.
3. **The autonomy replay fails** — the board did not follow the algorithm on its own
   observations (a parent, a move or a selection the reference would not have made).
4. **Compatibility drift** — any pin of §2 not hashing (a refusal).
5. **Leakage / attestation** — the image contains a LUT key, the certificate or the target
   tables (the target is derived on the board from the landscape seed — it is a public rule,
   not a leak; the *certificate* must not be there); a sign_reply with a non-zero table word.
6. **The gate was wrong** — if the board's A arm or B arm at 600 lands outside the gate's
   simulated distribution for these seeds, the prediction fails first (2), so this reduces
   to (2); the gate itself cannot be falsified by a run that reproduces its arithmetic.

## 6. The sessions and the rulings

Two board sessions, each with its own ruling pair, in this order:

**(a) Image qualification `B2Q`** — the B1 rule applies: a qualification binds the image
hash, so the new image needs its own short session on the qualified carrier: load and
identity (VARIANT, the map hash in the IDENT), key provisioning, the baselines, **one pair
at budget 8** (both arms: 16 search records + 2 holdout), the refused unsigned control;
every record audited; PASS = the 18 fitness values and the champions equal the prediction
for the qualification seeds (derived under `b2-qualification|`, excluded from B2's set).
This session also yields the B2 image's own rate measurement (roadmap §6: a new image may
not reuse the C1/C2 rates); the B2 plan's deadline is recomputed from it before (b).

**(b) Map utility `B2`** — `17A6`, `verify`; a fresh power cycle; the D4 boundary record as
the runner < 6 h before `go`; the rulings written by the owner and consumed once. Order
(fixed, B1's): precheck → identity → dcache off → clock preflight → B1 carrier load
(sha-gated) → key provisioning → identity page (seeds, budget, pairs, flags) written and
read back → image load (sha-gated) → `go` → the console belongs to the application; the host
signs (zero tables), audits per the policy, collects; the adjudicator runs over the files as
written. **Stop immediately** on a preflight refusal, KEY_NOT_LOADED, PAGE_MISMATCH, a U-Boot
banner, the deadline.

**Stop-loss (the instrument's, in force; the transport stop-loss of B1Q unresolved):** two
sessions lost to the same instrument / transport cause → stop, fix host-side, prove, review;
three without COMPLETED → design review. One ruling = one session; a HOLD is never argued
into a PASS.

## 7. Compatibility — what the new image owes

The B2 image is a successor of the B1 image (the cartographer replaced by the search; the
record's `carto` block replaced by a `search` block; the IDENT carrying the map hash, the
fitness id, the budget and the pair count). The owner's **compatibility review** (the L6 /
B1 list: the wire contract, the settle poll, the audit service, the MMIO allowlist against
the B1 RTL — unchanged RTL, so the B1 check stands —, the DMA order, no ICAPE2, no SLCR
write, the watchdog gating) precedes `board_ready`. The guards of `docs/b1_architecture.md`
§5 that apply (verbatim imports, header without tables, source include scan, binary scan —
now also for the certificate and the oracle rendering —, C = Python twin, the real
application off-board, wire contract, fail-closed adjudication, pins) are re-established
for the B2 image before the package that asks for the image review.

## 8. Freeze

(1) the owner reviews `docs/b2_package.md` (this draft, the architecture v0.2 and its
revision, the gate report) and rules on: the design, the audit policy, N; (2) the image is
built, its guards and twin tests added, the manifest written; (3) the owner's compatibility
review; the owner writes this document's sha256 into the manifest, sets `board_ready`;
(4) session (a) under its ruling pair, its record pinned; (5) session (b)'s ruling pair
bound to that committed manifest; (6) a fresh power cycle and boundary record;
(7) `host/b2_runner.py`. Any later change to this text is a new preregistration.

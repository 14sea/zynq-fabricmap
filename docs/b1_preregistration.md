# B1 — autonomous cartography on the known 292 bits: preregistration (DRAFT v0.3, host-only, 2026-09-05)

**Status: DRAFT — not frozen, not owner-approved, NO BOARD RULING.** Frozen means the owner
writes this document's sha256 into `manifests/b1_manifest.json` `prereg.sha256` and marks
the image `board_ready`; until then `host/b1_runner.py` refuses to run (first check after
the rulings), and any number produced against this draft is a pilot, not a result. Written
under the owner's ruling of 2026-09-05 (`docs/autonomous_cartography_roadmap.md`; B1
authorised to the pre-board package); v0.2 after the owner's FAIL of the first package, v0.3
after the owner's review of the second (`docs/b1_package.md` §0): the gates below are
exact, the qualification is an evidence chain, the rulings are two pairs. The architecture
is `docs/b1_architecture.md`; the noninterference contract `docs/b1_carrier_contract.md`;
the carrier's own qualification `docs/b1_carrier_qualification.md`.

## 1. The claim, in one sentence, and its scope

> On EBAZ4203 `17A6`, the B1 image on the **B1 carrier** — given only the 292 certified
> `clb_lut_init` addresses and their safety class, its seed and its budget, with **no
> semantic attestation from the host before any measurement** — recovers, from its own
> probes, a replayable map that names each address's LUT and INIT position with a stated
> confidence, an observed transition and an evidence trail, in **9 probes** to a complete
> provisional map and **301** to a fully confirmed one (333 in all); and the host,
> recomputing from the records, reproduces every choice the board made.

Scope: one die (`17A6`), one carrier (`d85daef4…`, qualified under its own ruling first),
the content-bit class, the 292 attested addresses only. Not claimed: polarity (the map
records the observed transition, not a derived word); anything about unattested bits,
routing, FF, another die, Linux, the ICAPE2 path, map utility (B2), the closed loop (B3);
a human-blind test (the certificate exists and was read — the claim is runtime-blind
reconstruction by the executable, guarded as `docs/b1_architecture.md` §5 says).

## 2. Pins

| what | value |
|---|---|
| instrument | `zynq-psoracle` `689dde1dad374536c625bbe2b05986ee89eb4c94` (archived, read-only; 128 files by hash); its carrier and signer are **not** used |
| B1 carrier | `builds/b1/b1.bit` `d85daef4e3aa1ff925c327e1c1f98465a83d96e79955aca432d664d98aa4f38f`; build record, carrier manifest and isolation report by hash; `VARIANT` `0x42310001`; nonce seed `0x9e3779b97f4a7c15`; **qualified only through the evidence chain** of `docs/b1_carrier_qualification.md` §4 (never a flag) |
| B1 signer | `host/b1_sign_arm.py` (contract `b1-nonsemantic-v1`, pinned by hash in the manifest) |
| B1 image | `firmware/b1/bsp/out/b1_app.bin` `300b12b1104b70d1612f4c6236a9280a0556443757b2ddf9dbadd9ef993d5abb`, 114 708 bytes, ELF and inputs in `evidence/b1/build_evidence.json`, two clean builds byte-identical |
| universe | 292 addresses, digest `895baf85…` (in the image and the IDENT) |
| ground truth (held back from the executable) | `local_map.json` `56f2b9e8…`; phenotype manifest `e45f466d…`; carrier constants `48f79b87…` — this repository's and the instrument's imported copies must hash equal (falsifier 3) |
| cartographer | `carto-v1`: 9 code bits, 292 confirmations, 32 pairs; per-entry evidence = code mask, confirm seq, observed; wire sample cap 8 |
| master seed | **1 123 460 948** = the first 4 bytes of sha256(`b1-cartography|` ‖ the archive commit); excluded: every L5, L6, round-1′, twin-corpus and host-model seed (`plan.json` `seed_exclusion`) |
| qualification seed | **176 359 248** = the same rule under `b1-qualification|`, excluding the above **and** B1's seed; recorded in the manifest; its records are never B1 data |
| budget | **333** probes → **335** records (opening baseline, 333 probes, closing baseline); an unscored candidate ends the epoch |
| audit policy | **all-self-reporting**: every record's raw words served and host-verified — in B1 every readout is the data |
| expected frames / CRC and bad-frame budget | 9 048 / 37 (the instrument's D-s4 formula over rel-v4) |
| deadline | 1 048 s after `go` (the instrument's timeout formula over the C1 #6 / C2 #2 planning rates; expected span ≈ 358 s) |
| flags | `0x32` (watchdog ON; both seq-1 controls; schedule-mode bits 0, ignored by B1) |
| plan / prediction | `evidence/b1/plan.json` `470e18f8…`; `evidence/b1/prediction.json` `7d197a49…`; qualification `evidence/b1q/plan.json` `dead8853…`, `evidence/b1q/prediction.json` `d2c9293a…` |
| adjudication pins | `manifests/b1_instrument_pins.json` — every adjudication-critical fabricmap file by hash (`host/b1_pins.py`), the normative documents included (contract, qualification, architecture), pinned in the manifest and **re-verified inside the adjudicator** |
| reporting strata | stratum B = LUT indices 4, 5 = `CLBLM_L.SLICEM_X0.ALUT` (50) + `.DLUT` (44) = 94 addresses (not consulted while the cartographer was developed); stratum A = the other four = 198. Both are reported; neither is a "holdout" in the blind sense |

## 3. The preregistered prediction (`evidence/b1/prediction.json`)

The reference cartographer over the truth fabric with the pinned seed and budget — the
exact probe sequence (333 genomes; sha256 `plan.json` `predicted_probe_sequence_sha256`
`f351475c…`), every record's `carto` block at content level, and the final map's
**content** sha256 **`7e1e7702…`** (the whole-map hash binds the session token and is not
predicted). On a correct instrument the board reproduces these bytes. Expected score, all
exact: precision 1.0, recall 1.0 (292 claimed, 292 correct), unobserved claims 0, anomalies
0; **the probe-9 snapshot**: precision 1.0, recall 1.0, **confidence-1 accuracy 292/292**, no
confidence-2 cohort; **the final snapshot**: **confidence-2 accuracy 292/292**, **no
confidence-1 cohort remains** (every decoded entry was confirmed); stratum A 198/198,
stratum B 94/94; 32 pairs tested, 0 deviations, 0 pending; **9 probes to full recall at
confidence ≥ 1**, **301 to full confirmation** of all 292, 333 in all. The prediction file
must itself carry these constants (the adjudicator checks it: a regenerated prediction
with other numbers is a finding, not a moved goalpost).

## 4. Metrics and the decision rule

All computed by `host/b1_verify.py` over the host's **reconstruction** (which, by the
autonomy replay, equals the board's map — or the run is not a PASS). Every row is an
EXACT equality, checked by `host/b1_adjudicate.b1_findings` and tested from the
adjudicator's entry point (`tests/test_b1_adjudicate.py`):

| metric | definition | PASS value |
|---|---|---|
| precision | correct (LUT, INIT) among entries that claim one (decoded / confirmed) | 1.0 |
| recall | correct claims over the 292 truth-mapped addresses | 1.0 |
| claimed | entries that claim a relation | 292 |
| unobserved claims | claims without an observed transition (score as wrong) | 0 |
| anomalies | the cartographer's own count | 0 |
| probe-9 snapshot | the belief after the 9th code probe: precision, recall; confidence-1 cohort claimed / correct / accuracy; confidence-2 cohort | 1.0, 1.0; 292 / 292 / 1.0; 0 claimed |
| final snapshot | the map at the end: confidence-2 cohort claimed / correct / accuracy; confidence-1 cohort | 292 / 292 / 1.0; 0 claimed |
| strata A / B | precision and recall on the four development LUTs and on ALUT/DLUT separately | all 1.0 |
| interaction | pairs tested / deviations / pending | 32 / 0 / 0 |
| sample efficiency | probes at which full recall at confidence ≥ 1 is first reached; probes at which every address is confirmed | 9; 301 |
| autonomy replay | every board probe = the reference's proposal (**the probe sequence is a finding, per record**); every record's `content_sha256` and `map_sha256` = the reconstruction's, bound as the board was | all |
| prediction | every record's content-level block and the final content = the prediction's; the prediction carries the constants above | equal |
| commitment | the closing record's hashes = the final map = the reconstruction | equal |
| map | the expanded `self_map` 2.0.0 validates under the JSON schema (no validator = a finding) and under the semantic rules: exactly the 292 pinned addresses once each, legal state / confidence / observation / evidence combinations, 9 distinct code-probe seqs, 32 legal edges, none pending | no finding |

**PASS** = every row holds AND the instrument's own conditions hold through the B1
validator (run-log validation with the audit gate, rule iii-B1, every record audited,
structural / baseline / REC / rel-v4 closure and controls, heartbeat and CRC / bad-frame
budgets, span within the deadline, COMPLETED at seq 335). **HOLD** = any finding; the map is
still reported, scored, and expanded. **KILL** = a validator falsification (served words
that do not recompute, a broken nonce chain, a staged hash ≠ the signed commit, a closing
control not refused). **REFUSED** = a pin or binding that does not hold — the plan, the
prediction and the pin table re-verified inside the adjudicator; the carrier's
qualification evidence re-adjudicated — nothing is adjudicated. Nothing is adjusted after
the fact: a map that differs from the prediction is an instrument / fabric question or a
cartographer defect and is reported as such.

## 5. Falsifiers

1. **The board's map differs from the prediction** while the instrument's conditions hold
   — the fabric is not the additive single-position model the certificate implies, or the
   image mis-reads it. Reported; the anomaly counters and phase C say where.
2. **The autonomy replay fails** — the board probed something the algorithm would not have
   proposed from its own observations, or committed to a hash the observations do not
   give. A defect of the image or of the twin discipline.
3. **Compatibility drift** — any pin of §2 not hashing (machine-checked, a refusal).
4. **Leakage or attestation** — any guard of `docs/b1_architecture.md` §5 failing, or a
   sign_reply with a non-zero table word (rule iii-B1: the host attested semantics; the
   record is refused and the session is a HOLD).
5. **The metric is decidable without measuring** — if the address-only baseline or a
   hard-coded map ever scores near the reference on the permuted fixture, B1 is
   withdrawn before freeze, exactly as round 1′ was (owner 2026-09-05).

## 6. The sessions and the four rulings

Two board sessions, each with its own ruling **pair** (a provisioning ruling is consumed
once and is bound to its session name), in this order:

**(a) Carrier qualification `B1Q`** — `whole-of-run B1 carrier qualification` +
`provisioning P3-K` (session `B1Q`): `docs/b1_carrier_qualification.md` §3 — the B1 image
with budget 9 on the B1 carrier, seed 176 359 248, 11 records every one audited; `VARIANT`
over the PS path, key provisioning, the baselines on a zero-table payload with zero readout
and the scorer's base counters, the nine code probes SCORED with a non-zero readout and
`tables_match` = 0 while `configuration_valid_hw` = 1, the closing baseline, the refused
unsigned control. PASS → the record pinned into the manifest (`carrier.qualification`),
from which `carrier.qualified` is derived and re-verified by every later runner and
adjudicator (§4 there). No host-attested reply control is sent to the board.

**(b) Mapping `B1`** — `whole-of-run B1 cartography` + `provisioning P3-K` (session `B1`),
bound to the manifest **after** the qualification record is pinned. `17A6`, `verify`; a
fresh power cycle; the D4 boundary record as the runner < 6 h before `go`; the rulings
written by the owner and consumed once. Order (fixed): precheck → identity → dcache off →
clock preflight → **B1 carrier** load (sha-gated) → key provisioning (P3-K) → identity page
(seed, budget, flags) written and read back → image load (sha-gated) → `go` → the console
belongs to the application; the host signs (zero tables), audits every record, collects; at
the end the adjudicator runs over the files as written and the map is expanded to
`self_map` 2.0.0 beside the verifier report. **Stop immediately** on a preflight refusal,
KEY_NOT_LOADED, PAGE_MISMATCH, a U-Boot banner, the deadline.

**Stop-loss (the instrument's, in force):** two sessions lost to the same instrument /
transport cause → stop, fix host-side, prove, review; three without COMPLETED → design
review. B1's own: one ruling = one session; a HOLD is never argued into a PASS; a second
attempt needs its own ruling pair after the owner's review of the first.

## 7. Compatibility and recalibration — what a new image and a new carrier owe

The B1 image is a successor, not the pinned P3 image: the owner's **compatibility review**
(the same list the L6 preregistration §2 applied to the two-operator image — the wire
contract, the settle poll, the audit service, the MMIO allowlists against the B1 RTL, the
DMA order, no ICAPE2, no SLCR write, the watchdog gating) precedes `board_ready`. The B1
carrier inherits none of the P3 carrier's board-level guarantees and is qualified by
session (a) before session (b); the qualification binds the image hash, so a new image
needs a new qualification. B1 derives **no budget from a rate** — its budget is the
cartographer's own bound — so no C1/C2-style calibration is required for this stage; the
deadline is a bound, not a prediction. Should a later stage size anything from B1's pace,
it calibrates first.

## 8. Freeze

(1) the owner reviews `docs/b1_package.md` and rules; (2) the owner writes this document's
sha256 into the manifest's `prereg.sha256`, sets `image.board_ready` true after the
compatibility review, commits; (3) session (a) under its ruling pair; its PASS record
pinned with `host/b1_manifest.py --qualification <dir>`, committed; (4) session (b)'s
ruling pair bound to that committed manifest's sha256; (5) a fresh power cycle and boundary
record; (6) `host/b1_runner.py`. Any later change to this text is a new preregistration.

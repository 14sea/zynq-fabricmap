# B1 — autonomous cartography on the known 292 bits: preregistration (DRAFT v0.2, host-only, 2026-09-05)

**Status: DRAFT — not frozen, not owner-approved, NO BOARD RULING.** Frozen means the owner
writes this document's sha256 into `manifests/b1_manifest.json` `prereg.sha256` and marks
the image `board_ready`; until then `host/b1_runner.py` refuses to run (first check after
the rulings), and any number produced against this draft is a pilot, not a result. Written
under the owner's ruling of 2026-09-05 (`docs/autonomous_cartography_roadmap.md`; B1
authorised to the pre-board package); v0.2 after the owner's FAIL of the first package the
same day (`docs/b1_package.md` §0). The architecture is `docs/b1_architecture.md`; the
noninterference contract `docs/b1_carrier_contract.md`; the carrier's own qualification
`docs/b1_carrier_qualification.md`.

## 1. The claim, in one sentence, and its scope

> On EBAZ4203 `17A6`, the B1 image on the **B1 carrier** — given only the 292 certified
> `clb_lut_init` addresses and their safety class, its seed and its budget, with **no
> semantic attestation from the host before any measurement** — recovers, from its own
> probes, a replayable map that names each address's LUT and INIT position with a stated
> confidence, an observed transition and an evidence trail, in **9 probes** to a complete
> provisional map and **333** to a fully confirmed one; and the host, recomputing from the
> records, reproduces every choice the board made.

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
| B1 carrier | `builds/b1/b1.bit` `d85daef4e3aa1ff925c327e1c1f98465a83d96e79955aca432d664d98aa4f38f`; build record `5da31443…`; carrier manifest `2e9de7c7…`; `VARIANT` `0x42310001`; nonce seed `0x9e3779b97f4a7c15`; `qualified` **false** until the qualification ruling |
| B1 signer | `host/b1_sign_arm.py` (contract `b1-nonsemantic-v1`, pinned by hash in the manifest) |
| B1 image | `firmware/b1/bsp/out/b1_app.bin` `54b006636fe07d1b52784e636452cfbd1191407a100699a7666c57b96ba4d6c8`, 114 708 bytes, ELF and inputs in `evidence/b1/build_evidence.json`, two clean builds byte-identical |
| universe | 292 addresses, digest `895baf85…` (in the image and the IDENT) |
| ground truth (held back from the executable) | `local_map.json` `56f2b9e8…`; phenotype manifest `e45f466d…`; carrier constants `48f79b87…` — this repository's and the instrument's imported copies must hash equal (falsifier 3) |
| cartographer | `carto-v1`: 9 code bits, 292 confirmations, 32 pairs, evidence cap 4, wire sample cap 8 |
| master seed | **1 123 460 948** = the first 4 bytes of sha256(`b1-cartography|` ‖ the archive commit); excluded: every L5, L6, round-1′, twin-corpus and host-model seed (`plan.json` `seed_exclusion`) |
| budget | **333** probes → **335** records (opening baseline, 333 probes, closing baseline); an unscored candidate ends the epoch |
| audit policy | **all-self-reporting**: every record's raw words served and host-verified — in B1 every readout is the data |
| expected frames / CRC and bad-frame budget | 9 048 / 37 (the instrument's D-s4 formula over rel-v4) |
| deadline | 1 048 s after `go` (the instrument's timeout formula over the C1 #6 / C2 #2 planning rates; expected span ≈ 358 s) |
| flags | `0x32` (watchdog ON; both seq-1 controls; schedule-mode bits 0, ignored by B1) |
| plan / prediction | `evidence/b1/plan.json` `4bc2e9b9…`; `evidence/b1/prediction.json` `fc1d41ce…` |
| adjudication pins | `manifests/b1_instrument_pins.json` — every adjudication-critical fabricmap file by hash (`host/b1_pins.py`), pinned in the manifest |
| reporting strata | stratum B = LUT indices 4, 5 = `CLBLM_L.SLICEM_X0.ALUT` (50) + `.DLUT` (44) = 94 addresses (not consulted while the cartographer was developed); stratum A = the other four = 198. Both are reported; neither is a "holdout" in the blind sense |

## 3. The preregistered prediction (`evidence/b1/prediction.json`)

The reference cartographer over the truth fabric with the pinned seed and budget — the
exact probe sequence (333 genomes; sha256 `plan.json` `predicted_probe_sequence_sha256`
`f351475c…`), every record's `carto` block at content level, and the final map's
**content** sha256 **`7e1e7702…`** (the whole-map hash binds the session token and is not
predicted). On a correct instrument the board reproduces these bytes. Expected score:
precision 1.0, recall 1.0 (292 confirmed), unobserved claims 0, anomalies 0, calibration:
confidence-2 accuracy 1.0 (292/292); provisional snapshot after phase A: precision 1.0,
recall 1.0; stratum A 198/198, stratum B 94/94; 32 pairs tested / 0 deviations; **9 probes
to full recall at confidence ≥ 1**, 301 to full confirmation of all 292, 333 in all.

## 4. Metrics and the decision rule

All computed by `host/b1_verify.py` over the host's **reconstruction** (which, by the
autonomy replay, equals the board's map — or the run is not a PASS):

| metric | definition | PASS threshold |
|---|---|---|
| precision | correct (LUT, INIT) among entries that claim one (decoded / confirmed) | = 1.0 |
| recall | correct claims over the 292 truth-mapped addresses | = 1.0 |
| unobserved claims | claims without an observed transition (score as wrong) | 0 |
| calibration | accuracy at confidence 2 ≥ at confidence 1; both = 1.0 on this fabric | as stated |
| confidence snapshots | the provisional map (after the 9 code probes) and the confirmed map (at the end) scored separately; probes to full recall at confidence ≥ 1; probes to full confirmation | 1.0 / 1.0; 9; 301 |
| strata A / B | precision and recall on the four development LUTs and on ALUT/DLUT separately | all = 1.0 |
| interaction | pairs tested / deviations | 32 / 0 |
| anomalies | the cartographer's own count | 0 |
| autonomy replay | every board probe = the reference's proposal (**the probe sequence is a finding, per record**); every record's `content_sha256` and `map_sha256` = the reconstruction's, bound as the board was | all |
| prediction | every record's content-level block and the final content = the prediction's | equal |
| commitment | the closing record's hashes = the final map = the reconstruction | equal |
| map schema | the expanded `self_map` 2.0.0 validates | no finding |

**PASS** = every row holds AND the instrument's own conditions hold through the B1
validator (run-log validation with the audit gate, rule iii-B1, every record audited,
structural / baseline / REC / rel-v4 closure and controls, heartbeat and CRC / bad-frame
budgets, span within the deadline, COMPLETED at seq 335). **HOLD** = any finding; the map is
still reported, scored, and expanded. **KILL** = a validator falsification (served words
that do not recompute, a broken nonce chain, a staged hash ≠ the signed commit, a closing
control not refused). **REFUSED** = a binding or pin that does not hold (nothing is
adjudicated). Nothing is adjusted after the fact: a map that differs from the prediction is
an instrument / fabric question or a cartographer defect and is reported as such.

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

## 6. The sessions

Two board sessions, each with its own ruling pair, in this order:

**(a) Carrier qualification** — `whole-of-run B1 carrier qualification` + `provisioning
P3-K` (`docs/b1_carrier_qualification.md` §3): the B1 image with budget 9 on the B1
carrier; `VARIANT` over the PS path, key provisioning, the opening baseline on a zero-table
payload, the nine code probes SCORED and host-audited, the closing baseline and the refused
unsigned control. PASS → the owner marks the carrier `qualified`. Its seeds and records are
not B1 data.

**(b) Mapping** — `whole-of-run B1 cartography` + `provisioning P3-K`. `17A6`, `verify`; a
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
session (a) before session (b). B1 derives **no budget from a rate** — its budget is the
cartographer's own bound — so no C1/C2-style calibration is required for this stage; the
deadline is a bound, not a prediction. Should a later stage size anything from B1's pace,
it calibrates first.

## 8. Freeze

(1) the owner reviews `docs/b1_package.md` and rules; (2) the owner writes this document's
sha256 into the manifest's `prereg.sha256`, sets `image.board_ready` true after the
compatibility review, commits; (3) session (a) under its ruling pair, then
`carrier.qualified` true, committed; (4) session (b)'s ruling pair bound to the committed
manifest's sha256; (5) a fresh power cycle and boundary record; (6) `host/b1_runner.py`.
Any later change to this text is a new preregistration.

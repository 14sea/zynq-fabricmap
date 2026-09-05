# Claim B, round 1′ — preregistration (DRAFT v0.1, host-only, 2026-09-05)

**Status: DRAFT — not frozen, not owner-approved, no board ruling.** Written under the
owner's ruling of 2026-09-05 (`docs/claimb_l6_package.md` §0: *RESUMED — PREREGISTRATION
PENDING (HOST-ONLY)*). Nothing here may be relied on until it is frozen: frozen means
the owner writes this document's sha256 into `manifests/claimb_round1prime_manifest.json`
`prereg.sha256`, and every later artifact and ruling pins that hash. Until then the runner
refuses to run (`host/claimb_r1p_runner.py`, first check after the rulings), and any number
produced against this draft is a pilot, not a preregistered result.

This document **supersedes `docs/claimb_preregistration.md` (round 1, DRAFT) by reference,
not by edit**: the claim, the universe, the map and the falsifiers are carried over where
they still apply and are re-pinned; the evaluation loop, the budget, the metrics'
implementation, the gates, the board procedure and the freeze are rewritten for the P3
instrument. Where this document changes a round-1 decision it says so and why.

## 0. What the pinned instrument can test — read this first

Round 1′ runs on the archived P3 instrument exactly as it was soaked
(`zynq-psoracle` `689dde1`, image `5deee74c…`, carrier `956379fa…`, `mutation_bits = 4`;
the owner's ruling forbids changing any of it without a new ruling). On that instrument
the two arms are **operators that sample candidates independently from the pinned base**:
candidate *i* is `operator(arm(i), pair_seed(i))` applied to the all-zero base, four INIT
bits set. There is no selection, no parent, no population on the board (`p3_search.c`),
and the host cannot inject one. Round 1′ therefore tests Claim B in its **operator form**:

> Given the same base, the same 292-address universe, the same paired seeds, the same
> budget, the same fitness, the same board and the same session — do the candidates the
> **map-guided** operator proposes reach a better preregistered primary metric than the
> candidates the **random-safe** operator proposes?

and NOT the evolutionary form of round 1 (a search with selection). A search with selection
on this instrument is a firmware change and is outside this preregistration.

**The fitness is additive, and the outcome is therefore predicted before the run.** The
carrier's scorer counts, per LUT, the train vectors (40 of 64, frozen order) whose LUT
output equals the frozen target bit; a LUT's output for vector *v* is INIT[*v*]; the base
INIT is all-zero. So a candidate's fitness is the base's (118) plus, for each of its four
set bits, +1 (train position, target 1), −1 (train position, target 0) or 0 (holdout
position) — `host/claimb_r1p_model.py`, per-bit table in
`evidence/claimb_round1prime/model_prediction.json`: 102 gains, 81 losses, 109 zeros among
the 292 addresses. Consequences, all computed and pinned:

- every candidate's gain lies in [−4, +4] for either arm; the best of any block of a few
  hundred candidates is +4 for **both** arms — round 1's primary ("best fitness at a fixed
  budget") **ties by construction**;
- same-LUT locality — the one thing the map knows — cannot change an additive score; the
  arms' distributions differ only in how they weight LUTs (random-safe by mapped-bit
  count, map-guided uniformly): E[gain] = 0.287671 (random-safe) vs 0.289427 (map-guided)
  per candidate, exactly, an artefact of the base's agreement pattern, not navigation;
- the host predictor (`zynq-psoracle/host/p3_oracle.py:predict_scores` over the operator
  twins' genomes) matched **all 12 570 SCORED records of S #3 exactly** (0 mismatches;
  `docs/claimb_round1prime_package.md` §2) — that comparison used S #3 only to validate the
  predictor, never as an arm or metric; every score of round 1′ is therefore predicted in
  advance, candidate by candidate, and pinned by hash.

What a board run of round 1′ can then establish: **(a)** the preregistered Claim B
(operator form) outcome, *measured* on silicon rather than argued — the model predicts the
negative (falsifier 1) with 16 of 16 primary blocks tied; **(b)** 11 754 host-predicted,
non-blank known answers through the PS oracle and the signed interlock in one unattended
session, which is the strongest oracle-scale test this line has (S #3's were predicted only
after the fact); **(c)** whether the instrument holds this round's budget inside the
evidenced window. What it cannot establish: anything about the map's *navigational* value —
on an additive fitness no operator has any, so a null here is not evidence against the map
on a non-additive one. **That is a finding about the carrier, not about the map, and it is
stated here so the owner decides with it in view** (package §0).

## 1. The claim, and what is not claimed

**Claim B** (from `zynq-autoehw/docs/tech_report.md`): *a device-local map guides evolution
better or more safely than raw mutation.* Round 1′ tests its operator form (§0) on one
instrument. The only difference between the arms is the operator; everything else is shared
by construction — one runner, one image, one schedule, the arm a per-candidate parameter of
the A,B,B,A pairing rule (`l6_schedule.arm_abba`).

Not claimed, carried verbatim from round 1 and from the L6 package (§5 there): on-board
self-cartography; evolution-as-fuzzing; `int_pip`, `clb_lutram`, `clb_mux`, `clb_ff_config`;
any comparison against flipping bits outside the certified universe. Not claimed, new here:
the evolutionary form of Claim B (selection); anything about the ICAPE2 readback path
(H-PAD/H-ADDR/H-IDLE stay where `claimb_findings.md` §3.3 left them); any other die (`17A6`
only), Linux, the blank-FAR diagnostic route, autonomous discovery (seeds are host-supplied
by rule); anything beyond the evidenced window (6763.9 s); a hardware holdout (§4).

## 2. The writable universe — pinned, re-verified by hash

Round 1's §2 stands: `clb_lut_init` only, the **292 certified addresses** over 12 FARs
(`0x00400A20‥23`, `0x00400C1A‥1D`, `0x00400C20‥23`), words 51/52, six partially writable
LUTs (49/49/49/51/50/44 of 64), every certified bit `expected_value = 1`. The pins:

| artifact | sha256 | verified where |
|---|---|---|
| `local_map.json` (erratum-006 run) | `56f2b9e8…` | plan builder, tests, and the instrument's `operator_data` derivation (`0c9c82a8…`) |
| `phenotype_manifest.json` | `e45f466d…` | plan builder, tests |
| `carrier_constants.json` (vector order, targets, train 40 / holdout 24) | `48f79b87…` | plan builder, tests, the model |
| `specs/reachability_spec_v1.json` | `11f82662…` | plan builder |
| genome addresses (292, ascending far/word/bit) | `895baf85…` | the instrument's `p3_genome` |

**Falsifier 3 (compatibility drift)** is a machine check: this repository's copies and the
instrument's imported copies (fabricmap `71666b02`) must hash to the pins above
(`host/claimb_r1p_plan.py:check_fabricmap_artifacts`); a drift refuses the plan.

## 3. The map

Round 1's §3 stands: `local_map` 1.0.0, derived mechanically from the certificate, never
edited by hand. The map data the image compiles in (`l6_operator_data`, 292 addresses in
genome-bit order + each LUT's mapped INIT positions) hashes to `0c9c82a8…`; the IDENT names
it and the runner regenerates it from `local_map.json` before every session.

## 4. Metrics — fixed before any run, with the model's prediction beside each

**Fitness** of a candidate = Σ over the six LUTs of the scorer's train-slice match counter
(`loop_record.evidence.score.scores`, six counters, read by the PS after a signed ARM); the
base scores `[18, 22, 20, 20, 20, 18]` = 118. The statistic used everywhere below is the
**gain** `d_train = fitness − 118`.

**Pairing and blocks.** Candidates 2k and 2k+1 form pair *k* and share `pair_seed(k)`; pair 0
runs A,B, pair 1 runs B,A, alternating (round 1 §4, `l6_schedule`). N = 11 752 candidates =
5 876 pairs. The first 5 872 pairs form **16 blocks of 367 consecutive pairs**; the 4 pairs
beyond the blocks enter the secondary only.

**Primary (one, chosen in advance).** Per block *b*: `best_A(b)` = max gain over the block's
367 random-safe candidates, `best_B(b)` likewise for map-guided; `D(b) = best_B − best_A`.
**Decision rule:** *map-guided better* iff `D(b) > 0` in at least **12 of 16** blocks —
a one-sided sign test at α = 0.05 (P(X ≥ 12 | p = ½) = 0.0384); ties and negatives count
against. This is round 1's "best fitness at a fixed budget", made decidable by blocks
instead of a single number. **Model prediction:** `best_A(b) = best_B(b) = +4` in every
block; 0 of 16 positive; *map-guided better* = **false**.

**Secondary (reported, not primary).** The per-pair paired difference
`d_train(B) − d_train(A)` over all 5 876 pairs: its mean and the sign counts. **Model
prediction for the pinned seed:** mean −0.010211, 2 418 positive / 2 410 negative /
1 048 ties (the sign of the mean under other seeds is the LUT-weighting artefact of §0,
not navigation, and a positive value would not support the claim).

**Known answer (the run's validity, not a Claim B metric).** For every SCORED record,
`scores` must equal the preregistered prediction for that seq; the two baselines must equal
`[18, 22, 20, 20, 20, 18]`. A mismatch is a HOLD naming the seq (an oracle/instrument
question), never a Claim B number. Time-to-threshold (round 1's secondary) is dropped: on an
additive fitness it is +4's first occurrence and carries no information the primary lacks.

**Safety metrics (reported, every run):** `refused_by_gate`; every non-`SCORED` outcome by
kind; recoveries (CRC drops, bad frames, fragments, re-requests); every gate finding. Both
arms draw inside the certified universe by construction, so gate refusals are expected to
be zero for both; a non-zero count is an instrument finding.

**No hardware holdout.** Round 1 §4 required train/holdout vector sets and holdout scoring
of each arm's champion. The scorer has that split (train 40 / holdout 24, `MODE_HOLDOUT`),
but the pinned image never sets it, and the ruling fixes the image; and the fitness is
deterministic (the baselines are bit-identical across every session of the line), so a
holdout would separate nothing that the additive table does not already decide. The
holdout arithmetic is computed and pinned in the prediction (`metrics_holdout_arithmetic`)
for completeness; it is measured nowhere and claimed nowhere. **This is a deviation from
round 1, recorded as such.**

## 5. Falsifiers — what makes round 1′ report a negative, or stop

1. **Map-guided does not beat random-safe** on the primary rule (§4). *Predicted to fire.*
   It is reported as the round's result, not adjusted.
2. **The schedule does not replay from cold:** a fresh process, from the pinned artifacts,
   does not regenerate the plan's `schedule_sha256`, the operator twins' genomes and the
   prediction's per-candidate rows bit for bit (tests `test_claimb_r1p_plan` /
   `test_claimb_r1p_model`; the runner regenerates the schedule and refuses a hash mismatch).
3. **Compatibility drift is not caught** — §2's hashes (machine-checked; a drift refuses).
4. **A wrong record is not refused host-side:** the instrument's validators must refuse a
   swapped arm, a foreign genome, an unaudited requested seq, a broken chain (their own
   tests, pinned by hash), and this round's adjudicator must refuse a log bound to another
   session or seed and HOLD on one altered score (`test_claimb_r1p_adjudicate`).
5. **The known answer fails** — any SCORED record's counters differ from the prediction:
   HOLD, an instrument question, the run is not a Claim B result either way.

## 6. The evaluation loop and the budget — the P3 stack, the evidenced window

One session, "B", on EBAZ4203 `17A6` (role `verify`, IDCODE `0x13722093`), U-Boot control
plane → the pinned standalone image, exactly the S #3 configuration with this round's seed
and N: `abba` schedule; the sampled audit policy (every 16th seq + first/last candidate +
both baselines = 738 audited records, host-paced sparse pulls); watchdog ON (D-s1: prescaler
7, 30 s); both seq-1 forced retry controls armed (flags `0x32`); rel-v4 transactions; the
v0.7 host rules (bad-frame ledger policy, record-budget heartbeat rule). Per candidate the
image: derives the genome from (pair seed, arm); asks the host notary to sign (link 1: the
gate over the whitelist, on the host); stages three PCAP envelopes and re-reads them
(link 2); DMAs; reads the twelve frames back (link 3); ARMs with the signature; settles;
reads the six counters; sends the record (REC transaction); serves the audit when asked.

**The budget** (`host/claimb_r1p_plan.py`, `evidence/claimb_round1prime/plan.json`):

| quantity | value | derivation |
|---|---|---|
| window W | **6763.9 s** | S #3's measured span, first SIGNREQ → last REC (owner 2026-09-05: the budget must fall entirely inside it) |
| rates | C1 #6 → 6982.1933 /h; C2 #2 → 6950.3715 /h | the instrument's `policy_matched_wall` rule (D-n1) over the two pinned calibration run logs, at this round's audit fraction, solved by fixed point |
| N | **11 752** (5 876 pairs) | ⌊0.9 × **min**(rate_A, rate_B) × W / 3600⌋ = ⌊11752.90⌋, rounded down to whole pairs — the SLOWER arm sizes N because the window is a ceiling (D-n1 used the faster arm for its floor) |
| runner deadline | **W after `go`** | a session still open at the deadline is STOPPED by the runner: a HOLD, never a PASS |
| post-hoc validation | predicted wall **6323.6 s** ≤ 0.95 × W = 6425.7 s (margin 102.1 s) | N × S #3's observed inter-record interval normalised to this round's audit fraction — validation only, never an input to N |
| audits | 738 | `sampled_audit_seqs(11752, 16)` |
| expected inbound frames | 218 217 | D-s4's brackets over rel-v4 |
| CRC budget = bad-frame budget | 873 | ⌈4 × 218 217 / 1000⌉ |
| settle bound | 10 × 16 polls | the calibrations' median (16), the soak's rule |
| master seed | **1 281 816 666** | §7 |

The round-1 §6 contract items that survive unchanged on the P3 path: every candidate
rewrites all twelve target frames from complete raw base frames (the image's staging);
the three flush frames are the pinned base verbatim (the gate); ECC is recomputed and
cross-checked (the gate, imported at `71666b02`); the gate parses the serialised streams
(link 1 on the host, `p3_gate.py` = `gate_candidate.py` verbatim); the board-side guard is
fixed (the image's MMIO allowlists against the RTL, tested in the instrument); readback of
all twelve frames after every write, fitness scored only on a match (link 3 + the signed
ARM; the audit re-verifies a sample on the host). Items that are superseded: partial-frame
ICAP (the PS/PCAP path replaces it), the U-Boot-only control-plane boundary (the identity
page and the standalone epoch replace it, with the D4 principal boundary verified < 6 h
before `go`).

## 7. Seeds — the rule, and every L6 seed excluded

`master_seed` = the first 4 bytes, big-endian, of
`sha256(b"claimb-round1prime|" ‖ b"689dde1dad374536c625bbe2b05986ee89eb4c94")`, advanced by
4 bytes while the value is in the excluded set = **1 281 816 666** (offset 0; derivation
recorded in the plan). Excluded: the L5 sessions' seed (1), the L6 C1/C2 seed
(1 278 624 577), the L6 S seed (1 278 628 687), the twin corpus's four master seeds, and
the three seeds the host model used on 2026-09-05. In addition no pair seed of this round's
5 876 pairs equals any pair seed of any L6 session's schedule (6 348 L6 pairs checked; 0
collisions) — `plan.json` `seed_exclusion`. **S #3's 12 568 candidates are not Claim B
data**: the adjudicator refuses a log bound to session S or to an L6 seed before computing
anything (§8, `test_s3s_evidence_is_refused_as_claim_b_data`).

## 8. Machine gates — all host-side, all before any device write

| gate | refuses |
|---|---|
| instrument pin table (`manifests/claimb_round1prime_instrument_pins.json`, 128 files) | an instrument checkout that is not `689dde1`, not clean, or with any pinned file not hashing — before any import (`claimb_r1p_instrument.bind`) |
| manifest pins | the plan or the prediction not hashing to `manifests/claimb_round1prime_manifest.json`; a DRAFT manifest (`prereg.sha256` null) |
| runner preflight (`claimb_r1p_runner.preflight`, in order) | wrong ruling text / board; no or consumed P3-K; prereg not frozen or not hashing; plan/prediction pins; instrument; the instrument's L6 manifest, image (board-ready, watchdog pinned), protocol, carrier pins; the image file's bytes; operator data; rulings not bound to session B, this prereg, this image, THIS manifest file's sha256 and the plan's seed; `sb`; the D4 boundary (< 6 h, this OS user, this signer, this key path); an existing evidence directory; the regenerated schedule and flags |
| the instrument's validators (unchanged) | chain, readout ≠ tables, readback ≠ commit, unsigned scores, a swapped arm, a foreign genome, a requested audit not served/verified, REC/rel-v4 closure and control shapes, heartbeat budget, CRC/bad-frame budgets, settle bound |
| the round's adjudicator (`claimb_r1p_adjudicate`) | binding to another session/seed/image/prereg; not COMPLETED at N + 2; span > W; any SCORED record ≠ prediction; then the metrics |
| clean-tree test report (`claimb_r1p_test_report.py`) | the board package cites only a report with a clean tree, 0 skipped, the instrument at the pinned commit |

## 9. Board, first contact and stop-loss

**Board:** `17A6`, `verify`; the P3 carrier `956379fa…`; `CPU_CLK_CTRL` preflight read;
FCLK0 decoded = 50 MHz. **Before the session:** a fresh power cycle (one epoch per power
cycle); the principal boundary record produced as the runner < 6 h before `go`
(`verify_principal_boundary.py`, R1–R5); the rulings written by the owner into `rulings/`
(gitignored, consumed once); the image binary hash-checked from the archive backup.

**Order (fixed; deviation ends the session):** precheck → identity → dcache off → clock
preflight → carrier load (sha-gated ymodem) → key provisioning (P3-K) → identity page
written and read back → image load (sha-gated) → `go` → the console belongs to the
application. **Stop immediately** on: any preflight refusal (no board contact happened);
a KEY_NOT_LOADED or PAGE_MISMATCH stop; a U-Boot banner (the epoch ended); the deadline.

**Stop-loss (inherited from L6 §7, in force):** the instrument's — two sessions lost to the
same instrument/transport cause → stop, fix host-side, prove, review, before a third
ruling; three sessions without `COMPLETED` → design review; psmap's "a new instrument is
not a new mechanism". This round's own: **one whole-of-run ruling = one session.** A
session that ends `STOPPED`/`CRASHED`/`PROTOCOL`, or `COMPLETED` short of N + 2, or past
the window, is a HOLD and is never argued into a PASS; a second attempt needs its own
ruling pair after the owner's review of the first. Console byte loss is *survived* by the
v0.7 rules, not removed; a session lost to it is still a HOLD.

## 10. Rulings and freeze

**Ruling pair, drafted (package §5):** `whole-of-run Claim B round 1′` — fields `ruling`,
`boardid` `17A6`, `granted_by`, `date`, `session` `"B"`, `master_seed` 1281816666,
`prereg_sha256` (this document, frozen), `image_sha256` `5deee74c…`,
`claimb_manifest_sha256` (the manifest file as committed at the freeze); and
`provisioning P3-K` with the same bindings minus the seed. The runner refuses any
mismatch; both are consumed by any outcome.

**Freeze procedure:** (1) the owner reviews the whole package and rules; (2) the owner
writes this document's sha256 into the manifest's `prereg.sha256` with a `frozen` note
(`status` → FROZEN), commits; (3) the owner issues the ruling pair bound to the committed
manifest's sha256; (4) a fresh power cycle and boundary record; (5) `claimb_r1p_runner.py`.
Any later change to this text is a new preregistration and a new round — not an edit.

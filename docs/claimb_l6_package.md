# Claim B — the L6 package, and the request for the resumption ruling (2026-09-05)

> **REQUEST — 2026-09-05. This document asks the owner for one ruling: whether Claim B's
> readback leg leaves PAUSED. It is not that ruling, not a preregistration, not a budget,
> and not a change to any governing document. It authorises no board contact.** The
> 2026-09-01 ruling (`docs/claimb_resumption_memo.md` §0) made the leg RESUMPTION-ELIGIBLE and
> kept it PAUSED "until a calibration/soak preregistration has passed and the two-operator
> image has completed P3 compatibility review". Both conditions were met in `zynq-psoracle`
> on 2026-09-04 and that repository is now archived. This document lays the evidence for
> each condition against the ruling's own words, with hashes, so that the decision is taken
> on the record and not on a summary. Until the owner rules: the readback leg stays PAUSED,
> Claim B has zero data points, the ICAPE2 path is neither resumed nor explained, and
> nothing here may be read as active.

## 0. Owner ruling — 2026-09-05 (additive; the text below is unchanged)

> **Claim B: RESUMED — PREREGISTRATION PENDING (HOST-ONLY).**
>
> - Both preconditions of the L6 package are satisfied; Claim B may leave PAUSED.
> - Authorised, inside `zynq-fabricmap` and without stopping for batch-by-batch review in
>   between: the round 1′ preregistration, the runner / validators / guards, the host-only
>   model and replay tests, the evidence index, and the candidate execution package.
> - Host-only draft commits may be pushed, but until the final review nothing may be
>   marked owner-approved FROZEN and no board ruling may be issued.
> - The work MUST stop before the next board contact and deliver the whole package for
>   review; until the next explicit ruling: no board contact, no power cycle, no image
>   load, no Claim B execution.
> - `zynq-psoracle` stays archived and read-only. Modifying it, extending the soak, changing
>   the image, or changing `mutation_bits = 4` requires stopping in advance and a new ruling.
> - Claim B's candidate budget must fall entirely inside the evidenced 6763.9 s window;
>   otherwise the soak must be extended first.
> - S #3's 12 568 candidates are still not Claim B data: not for arm comparison, not for
>   the primary metric, not for a holdout.
> - Round 1′ keeps every existing non-claim: `17A6` only, the PS/PCAP standalone path only;
>   ICAPE2 is not explained; no extrapolation to a second die, Linux, the blank-FAR
>   diagnostic route, or autonomous discovery.
> - Every L6 seed must be excluded from the Claim B schedule.
> - The board package must contain: the frozen candidate and its hashes, the complete budget
>   derivation, the whole-of-run ruling pair draft, the stop-loss, the fresh-power-cycle /
>   boundary requirements, the test reports, and the clean-tree proof.

Recorded by the author from the owner's ruling of 2026-09-05 (given in Chinese; this is a
faithful rendering, and the owner's message is the authority). The short re-review that
preceded it found the corrected package PASS with no new blocker, and approved the push of
`zynq-psoracle` `689dde1` and this repository's `1bba03d`. The work now proceeds host-only
under `docs/claimb_round1prime_*` and stops at "ready for the board" for the whole-package
review.

---

Author: Claude. Evidence repository pinned: `zynq-psoracle` archive head `689dde1` — the
adjudication commit is `32d1460` (`origin/main` until the 2026-09-05 archive-narrative
correction is pushed); independent read-only backup at
`/home/test/psoracle_backups/2026-09-04_S3_v0.7/` (taken at the adjudication commit). Earlier pins unchanged: `zynq-psmap`
`191ab05`; this repository's artifacts at `71666b02` as imported by P3. This repository is
at `d7708a1` when this is written.

---

## 1. The ruling's two conditions, verbatim, and where each is met

**Condition 1 — "a calibration/soak preregistration has passed".**

| | |
|---|---|
| the preregistration | `zynq-psoracle/docs/l6_soak_prereg.md`, **v0.7, FROZEN 2026-09-03**, sha256 `95d177a148e901b0f1ef10716d3468574b01b6864159128dda09bf57713781eb` |
| what it asked | **Q1** (calibration): the measured end-to-end rate per candidate on the P3 path, with the image Claim B will use, reported as three rates (inclusive / nominal / planning). **Q2** (soak): does the loop hold every L5 invariant for hours, unattended, under the sampled audit policy with the watchdog decided |
| Q1 answered by | **C1 #6** (random-safe arm, ruling `2026-09-03-01`): rate report `08222f85799fa3d18012cdd26a5cc047527995b682bfd5679a668014ea03251c` — 3495.7 evaluations/hour inclusive, nominal CoV 0.0151 over 63/63 clean periods, planning 3381.4. **C2 #2** (map-guided arm, ruling `2026-09-03-02`): rate report `959790d0e17401936ddd9636f79b9f79e9d45f4fc106de1482f2c8aa969db191` — 3479.6 inclusive, nominal CoV 0.0175 over 61/63 clean, planning 3367.8. Both owner-adjudicated PASS after an independent re-check and **pinned** (`manifests/l6_manifest.json` `calibration.C1` / `calibration.C2`); measured under v0.6 (`bfd69d10…`) and imported into the frozen v0.7 by the explicit declaration D-i1, which relaxes the preregistration hash and nothing else |
| Q2 answered by | **S #3** (ruling pair `2026-09-04-01`, the ONE soak authorised under v0.7): `COMPLETED / budget`; **12 570 `SCORED` records in 6763.9 s** (1 opening baseline + 12 568 scheduled candidates + 1 closing baseline), above §6.4's floor of 0.9 T = 6480 s and inside the 8739 s timeout; 6284 random-safe + 6284 map-guided on the A,B,B,A schedule, `arm_check` 12 568/12 568; both baselines exactly `[18, 22, 20, 20, 20, 18]`; closing unsigned control refused (fault 13) with CLOSE and TERM agreeing; **789/789 sampled audit pulls completed and verified** by the host recomputing all three hashes — five AUDIT chunks (seq 352, 5584, 9312, 9744, 10160) arrived CRC-broken and were re-requested exactly once each (attempt 0 crc, attempt 1 ok); zero timeouts, zero AUDITWAIT, zero DONE replays, zero failed pulls; nonce chain 12 571; every sign, REC, pull, IDENT and TERM transaction closed; 42 CRC drops and 4 bad frames of a 934 budget; 14 heartbeats lost over 7 records inside D-h1's budget of 12; `findings: []`. **Owner adjudication 2026-09-04: PASS (scoped)**, after an independent re-check of the raw evidence — validator 12 570 / 789 / 12 571, all 12 568 arms and genomes matching the schedule, every gate empty, the rate report regenerated field-identical (`8af02b917ca457ccccdbd016976e9c88bfe468f1c5256b469f7f1e5f58542d5b`), the counterfactual replayed independently |
| the status record | `zynq-psoracle/docs/status.md` L6 row and `manifests/l6_manifest.json` `status` — three manifest hashes to keep apart: the S #3 ruling pair was bound to `3fea5c4b…` as issued; the adjudication commit `32d1460` pinned `1c31b81dc9d767a5efaba4eda224e401932224318da0d76a7e730bb078d0f8da`; the archive head `689dde1` carries `b3991d82d889597e2754d5c3e20cc35f61966ad78055bccfffac93716db22a1a` after the 2026-09-05 narrative correction (prereg and image pins unchanged). The `status` text: "L6's Q1 (calibration) and Q2 (soak) are both ANSWERED … The complete L6 package may go to `zynq-fabricmap`'s owner, who decides independently whether Claim B leaves PAUSED; in this repository Claim B stays closed." |

The S #3 scope, in the psoracle findings' own words (`docs/l6_s_session3_findings.md` §5):
established is "Q2's answer for 2 hours" — meaning the registered criterion, T = 7200 s with the
measured wall span ≥ 0.9 T = 6480 s; the observed window is 6763.9 s (≈ 1 h 52 min 44 s), not a
full 7200 s; not established is "anything about Claim B (still
zero data points); any other die, carrier or control plane; the ICAPE2 readback path; that
2 h predicts longer … anything about the physical console path beyond this session's own
event counts."

**Condition 2 — "the two-operator image has completed P3 compatibility review".**

| | |
|---|---|
| the image | rel-v4 two-operator application image **`5deee74c44785ebe88168ccffaa5f399f26a7c5a567fccb3d430cf4eb14cdc7c`** (`firmware/bsp/out/p3_app_l6.bin`, 98 324 bytes, ELF `ebe97ce6…`), built twice from scratch byte-identical; `manifests/l6_manifest.json` `pinned_at_build`, `board_ready: true`, protocol rel-v4 |
| the review | the rel-v4 firmware package went to the owner's **full P3 compatibility review on 2026-09-03: HOLD**, the first candidate `734d6c04…` **withdrawn DEFECTIVE** (early `AUDITDONE` accepted, whole-line bound 32 s, `AUDITWAIT.served` counted transmissions); the corrected `5deee74c…` passed the short re-review (`docs/l6_rel_firmware_package.md` §7) and the evidence-closure review (§8), and was **promoted to the sole rel-v4 `pinned_at_build` at the v0.6 freeze, 2026-09-03** (`docs/decisions.md`, "owner's promotion/freeze batch") |
| what it carries | both Claim B arms on the standalone plane — random-safe (4 addresses uniform without replacement over the 292) and map-guided (one LUT uniform over the map's six, then 4 of its mapped INIT positions), `mutation_bits = 4` **frozen as an image/calibration contract** (owner 2026-09-01), `operator_data_sha256` `0c9c82a8…` over this repository's phenotype manifest + `local_map.json` (`56f2b9e8…`); the A,B,B,A pair-seed schedule from Claim B's prereg §4 with a twin in the image (`fixtures/l6_operator_corpus_v1.json`, 256 pairs, both arms bit-exact); the watchdog (D-s1: prescaler 7, 30 s, gated by the identity page); the sampled-audit pull transport; the rel-v4 transactions with bounded resends (D-p1) |
| it ran | on `17A6` in exactly four sessions — the rel-v4 sessions C1 #6 (PASS), C2 #2 (PASS), S #2 (HOLD, transport) and S #3 (PASS) — the same bytes every time, hash-checked before `go`. The seven earlier L6 sessions (C1 #1–#5, C2 #1, S #1) ran the historical images `bd1454cd…`, `e19e1b12…` and `403f4ab5…` |

Both conditions are therefore met **as the ruling worded them**, on the record of a
repository whose owner adjudicated every step and which is now archived (adjudication
`32d1460`, archive head `689dde1` after a doc-only narrative correction).

## 2. Evidence index (the package)

Everything below is in `zynq-psoracle` at the archive head `689dde1` unless marked; the backup directory
holds a verified `git bundle --all`, the S #3 evidence tarball (byte-compared), and the two
things the repository cannot keep — the gitignored S #3 **ruling pair** and the image
binary `p3_app_l6.bin` — with `SHA256SUMS`.

| item | path | note |
|---|---|---|
| the frozen preregistration | `docs/l6_soak_prereg.md` | v0.7, `95d177a1…`; §0 the two questions and their non-claims; §1 pins; §2 the two-operator image and its review requirements; §3 the decisions D-s1..D-i1, all RULED; §6 PASS/HOLD/KILL; §7 stop-loss; §8 what L6 does not establish; §9 the hand-back |
| the manifest | `manifests/l6_manifest.json` | `b3991d82…` at the archive head (`1c31b81d…` at the adjudication commit; `3fea5c4b…` bound by the S #3 ruling pair); the pins, the calibration records with their bindings, the S plan (N 12568, 789 audits, 233 364 expected frames, budget 934, timeout 8739 s), the S #3 hardware history and standing |
| S #3 findings | `docs/l6_s_session3_findings.md` | the soak record; §2 wall time; §3 transport and what each v0.7 rule did; §4 rates; §5 scope |
| S #3 evidence | `evidence/l6_17A6_2026-09-04-01-S/` | `run_log.json`, `audits.json`, `timeline.json`, `console.log`, `console.ts.log`, `rate_report.json`, `summary.json`, identity page, preflight, ymodem logs — ≈ 227 MB (two files drew GitHub's > 50 MB warning; under the 100 MB limit) |
| S #3 boundary | `evidence/boundary/principal_boundary_2026-09-04-01.json` | D4 R1–R5 PASS as the runner, 05:35 |
| the counterfactual | `evidence/l6_v07_counterfactual/s_2026-09-04-01_policy_replay.json` | S #3's own console bytes replayed through the real reader / session / collector / relay with one flag changed: v0.6 policy → `CRASHED: unparseable frame` at record 1011 (go + 546 s); v0.7 → `COMPLETED` 12 570 |
| the calibrations | `docs/l6_c1_session6_findings.md`, `docs/l6_c2_session2_findings.md`; `evidence/l6_17A6_2026-09-03-01-C1/`, `…-02-C2/` | C1 #6 and C2 #2, each with its `rate_report.json` pinned by hash |
| the host batch after S #2 | `docs/l6_s2_host_batch_package.md` | the four v0.7 decisions and their proofs: the S #2 replay, the modelled resend and negatives, the modelled session soak (12 seeds COMPLETE under the ledger policy, all CRASH under v0.6), N against T |
| the image's review | `docs/l6_rel_firmware_package.md` (§7 re-review, §8 evidence closure), `docs/l6_compat_review_package.md` (the review's requirements, §2 of the prereg) | `734d6c04…` withdrawn DEFECTIVE; `5deee74c…` PASS and promoted |
| status and decisions | `docs/status.md` L6 row; `docs/decisions.md` 2026-09-01 … 2026-09-04 | the canonical state; the full chain of HOLDs and PASSes, session by session |
| the archive | `README.md`, `docs/status.md` (archive banner); backup `/home/test/psoracle_backups/2026-09-04_S3_v0.7/` | no more board contact, no new ruling, no new calibration |

Note on the prereg's own hand-back list (`docs/l6_soak_prereg.md` §9.5, "`docs/l6_findings.md`:
the measured rates, the soak record, PASS/HOLD/KILL per §6"): no file of that name exists.
Its content is the status row, the per-session findings documents and the manifest's
`calibration` and `status` fields, all named above; the frozen text cannot be edited to say
so, hence this note.

## 3. What L6 delivered against the memo's §6 (what a resumed programme needs)

| memo §6 item | state after L6 |
|---|---|
| 1. a new Claim B preregistration (round 1′) | **not done — deliberately.** It is host-only work in this repository and is what a resumption ruling would authorise; writing it before the ruling would pre-empt the ruling |
| 2. instrument pins | available: `zynq-psoracle` `32d1460` (frozen, archived), image `5deee74c…`, carrier `956379fa…` (unchanged since L1), `zynq-psmap` `191ab05`, this repository's `71666b02` artifacts (`local_map.json` `56f2b9e8…`, genome addresses `895baf85…`) |
| 3. identity and epoch | in place and exercised in every L6 session: the identity page (session token, epochs, carrier and image sha, `fclk0_hz_decoded`), `17A6 verify` IDCODE `0x13722093`, the `CPU_CLK_CTRL` preflight, one epoch per power cycle, the D4 boundary verified as the runner < 6 h before `go` |
| 4. rulings | P3's per-session pair (whole-of-probe P3-L6 + provisioning P3-K, bound to prereg + image + manifest sha, refused on any mismatch, consumed by any outcome) is proven across eleven L6 sessions. **Still missing:** a Claim B whole-of-run ruling text of its own, checked by a Claim B runner the same way — part of round 1′ |
| 5. budget and the long run | **measured.** The calibration rates are pinned; the soak sized from them by D-n1 ran 6763.9 s against a post-hoc prediction of 6784.9 s (0.31 %). The rule that travels: the Claim B budget must sit **inside the observed 6763.9 s window** — what S #3 met is the registered 2-hour criterion (T = 7200 s, span ≥ 0.9 T = 6480 s), a full 7200 s or longer was not observed — or the soak is extended by its own ruling (prereg §8). The watchdog is ON (D-s1), no longer "off" as the memo recorded |
| 6. stop-loss in advance | L6's §7 is the model: two sessions lost the same way → fix and prove host-side before a third; three without `COMPLETED` → design review. It fired twice (S #1 + C1 #5; S #1 + S #2) and was honoured both times. The fault class it was written for — contiguous byte loss on the console — is **survived, not removed** (D-b1, D-h1 on S #3's own bytes); a round 1′ stop-loss inherits that distinction |

## 4. The memo's §4 gaps, re-stated after L6

| gap | after L6 |
|---|---|
| 1. blank FARs | **unchanged.** Every non-baseline candidate is non-blank content read back by the PS and recomputed on the host (12 568 of them in S #3); the two baselines are by construction the all-zero content the old interlock succeeded on, attributed by the positive control and the per-session identity. The diagnostic-carrier route remains unexecuted and this route still does not deliver it |
| 2. long runs | **closed for the observed 6763.9 s window** — the registered 2-hour criterion (T = 7200 s, span ≥ 0.9 T) met; a full 7200 s or longer not observed (§3 item 5). The board selected and scored every candidate itself with the watchdog armed; the host took no part in candidate selection or scoring, but stayed on the line throughout as notary, auditor, rel-v4 transaction endpoint and collector |
| 3. cross-chip | **unchanged.** Everything is `17A6`. The 4205 — the die the ICAPE2 line ran on — has never run the P3 stack |
| 4. the original Claim B path | **unchanged, and must stay written into round 1′'s non-claims.** The ICAPE2 carrier-internal readback, H-PAD/H-ADDR/H-IDLE and the diagnostic carrier are where the findings left them; a Claim B result on the PS route says nothing about them |
| 5. universe and map identity | **verified by hash at every session start**, not inherited by name: the fabricmap import at `71666b02`, the genome addresses, the local map, and the operator data (which covers `mutation_bits`). Round 1′ re-states the pin as its falsifier 3 |
| 6. the evaluation loop is different | **now measured rather than argued** — the three rates per arm and the wall-time behaviour under the sampled policy exist; round 1′'s §6 is written from them, not from the ICAP transfer arithmetic |
| 7. two arms on the board | **closed.** Both operators ran on the standalone plane, interleaved A,B,B,A, 6284 each in one epoch, `arm_check` exact. The contract that came with it: `mutation_bits = 4` is frozen; **if round 1′ changes it, C1/C2 must be re-run under the new contract** and the pinned rates may not be reused (manifest `operator.mutation_bits_note`) |
| 8. audit under a long run | **closed.** The sampled policy (every sixteenth record, 789 of 12 570) with host-paced pulls; 789/789 pulls completed and verified, five chunks re-requested once each, zero timeouts / AUDITWAIT / replays |

## 5. Non-claims that travel with this package

- **Nothing in L6 is a Claim B data point.** S #3 scored 12 568 candidates across both arms,
  but the prereg's §0 rules that "no primary metric, no holdout, no comparison between arms
  is made or reported as a finding"; the arms ran so that the instrument was calibrated
  and soaked in the configuration Claim B will use. Those scores are **not** to be mined,
  compared, or cited as an arm result — that would be an unpreregistered Claim B run.
- Seeds were host-supplied; nothing about autonomous discovery.
- One die (`17A6`), one carrier, one control plane (U-Boot → standalone). Nothing about
  Linux, another die, or the 4205.
- The ICAPE2 readback question is untouched (§4 item 4).
- The observed window is 6763.9 s: the registered 2-hour criterion (span ≥ 0.9 T) was met, a
  full 7200 s was not observed, and longer is not predicted (prereg §8).
- The console's byte-loss fault class was survived by the v0.7 rules, not removed; nothing
  was measured about CH340/usbipd.
- "PASS (scoped)" on S #3 is the owner's adjudication of a soak; a soak pins nothing.

## 6. What the ruling would and would not do

**If the owner rules that Claim B leaves PAUSED** (the memo's Option A, made concrete):

- the readback leg's status becomes something like RESUMED — PREREGISTRATION PENDING; the
  README banner and `docs/claimb_findings.md`'s pause remain as written, with the ruling
  recorded additively;
- the authorised next work is **host-only**: Claim B preregistration round 1′ in this
  repository (memo §6 item 1), superseding the DRAFT by reference — the claim, universe,
  map, metrics and falsifiers carried over where they still apply; §6 rewritten from the
  L6 rates with the budget inside the observed 6763.9 s window; §7 gates extended by P3's validators and audit gate;
  §8–§9 for the standalone plane; a Claim B whole-of-run ruling text; a stop-loss that
  inherits L6 §7; the non-claims of §5 above; §10 frozen with hashes;
- **no board contact** follows from the ruling itself. A board session needs round 1′
  frozen, its own ruling, and — because `zynq-psoracle` is archived — a separate decision
  to reopen that repository as the instrument (a new soak, a longer soak, a changed
  `mutation_bits`, or any image change each reopen it under its own ruling).

**If the owner rules HOLD or keeps PAUSED**, the reasons the memo already named still apply
in modified form: (i) the diagnostic-carrier route is judged worth the next board time
instead; (ii) reproduction on a second die is wanted first (gap 3 is the only §4 gap that
L6 could not touch and that round 1 as preregistered does not need); (iii) a longer soak is
wanted before any budget is frozen.

**In either case** this document changes nothing by itself; the ruling is written into §0.

## 7. The author's view, marked as such

The two conditions the owner set are met in the owner's own adjudications, and the gaps
that were engineering (long run, two arms, audit under load, the measured loop) are closed
on hardware. What remains open is science (the blank baselines, the second die, the
ICAPE2 question), and none of it is a reason to withhold the *preregistration*, which is
the only thing a PASS here authorises. The recommendation is to rule Claim B out of PAUSED
into a preregistration-pending state, so that the first Claim B ruling is spent on Claim B.

## 8. What this document is not

It is not evidence; every observation lives in `zynq-psoracle` (adjudication `32d1460`,
archive head `689dde1`) and in its backup. It does not change `docs/claimb_findings.md`, `docs/claimb_jtag_gate_review.md`,
`docs/claimb_preregistration.md`, `docs/claimb_resumption_memo.md` or the README beyond an
additive pointer. It requests a ruling; it does not give one, and it authorises no build,
no board time and no run.

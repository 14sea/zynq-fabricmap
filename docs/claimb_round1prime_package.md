# Claim B round 1′ — the board package, delivered for the whole-package review (2026-09-05)

> **HOST-ONLY. Delivered at "ready for the board" under the owner's ruling of 2026-09-05
> (`docs/claimb_l6_package.md` §0) and STOPPED there, as the ruling requires. Nothing in
> this package is FROZEN or owner-approved; no board ruling exists; no board contact,
> power cycle, image load or Claim B execution has happened or may happen before the
> owner's next explicit ruling.** The preregistration is a DRAFT
> (`docs/claimb_round1prime_preregistration.md`); the manifest's `prereg.sha256` is null and
> the runner refuses to run on it (§7).

## 0. The finding the owner should decide with — before anything else in this package

Building the host model (`host/claimb_r1p_model.py`) showed that, on the pinned instrument,
**Claim B's outcome is decided by arithmetic before the board runs.** The carrier's scorer
is a per-LUT count of train vectors whose LUT output equals a frozen target bit; a LUT's
output for vector *v* is INIT[*v*]; the base is all-zero. The fitness is therefore
**additive over the 292 genome bits** (+1 / −1 / 0 per set bit), and:

- both operators set four bits, so every candidate's gain is in [−4, +4] and the best of
  any few hundred candidates is +4 for both arms — round 1's primary metric ("best fitness
  at a fixed budget") **ties by construction** (the prediction: 16 of 16 blocks tied);
- same-LUT locality, the one thing the map-guided operator knows, **cannot change an
  additive score**; the arms differ only by how they weight LUTs (E[gain] 0.287671 vs
  0.289427 per candidate, exactly), an artefact of the base's agreement pattern;
- the host predictor reproduces the silicon exactly: it matched **all 12 570 SCORED
  records of S #3** with 0 mismatches (§2), so every score of round 1′ is predicted in
  advance and pinned by hash.

The consequence is about this scorer, and it is narrower than "no operator can matter":
**under this additive scorer the same-LUT structure has no interaction advantage, and the
fixed round 1′ seed, budget and primary are predicted to saturate into a tie.** Operators
and selection schemes still differ (LUT weighting, sampling law, selection dynamics); what
is shown is that the *interaction* the map could exploit does not exist here — *(wording
narrowed 2026-09-05 on the owner's review; the original sentence over-generalised)*. The map could matter only
on a **non-additive** fitness (e.g. LUT outputs chained, or a target defined over
combinations), which is a carrier change, outside this ruling and outside this line's
present authority.

The package below is complete for the pinned instrument as ruled. What it buys on the
board, honestly: (a) the Claim B (operator form) negative **measured** instead of argued;
(b) **11 754 host-predicted non-blank known answers** through the PS oracle and the signed
interlock in one unattended session — the strongest oracle-scale test available; (c) the
budget-inside-the-window discipline exercised end to end. What it does not buy: any
evidence about the map's navigational value. The author's view, marked as such: the owner
should weigh (a)–(c) against the board time before ruling, and consider whether the next
carrier — not this round — is where Claim B is actually decidable.

## 1. What was built (host-only; every file additive; nothing in the instrument changed)

| file | what |
|---|---|
| `docs/claimb_round1prime_preregistration.md` | the DRAFT preregistration: §0 what the instrument can test; §4 the metrics and the model's prediction beside each; §5 falsifiers; §6 the loop and the budget; §7 seeds; §8 gates; §9 board and stop-loss; §10 rulings and freeze |
| `manifests/claimb_round1prime_manifest.json` | the round's pins: instrument commit, L6 manifest / prereg / image / carrier / operator-data / calibration / soak hashes, this repository's artifact hashes, window, seed rule + exclusions, audit policy, plan and prediction hashes, rulings required and their bindings; `prereg.sha256` null (DRAFT) |
| `manifests/claimb_round1prime_instrument_pins.json` | 128 files of `zynq-psoracle` at `689dde1` (host/, validators/, scripts/, imported/, firmware/, rtl/, fixtures/, manifests/, builds/p3/, the L6 prereg and findings, the C1 #6 / C2 #2 / S #3 evidence files), each by sha256 |
| `host/claimb_r1p_instrument.py` | the read-only binding: verifies commit, clean tree and every pin before putting the instrument on `sys.path` in the L6 runner's order |
| `host/claimb_r1p_model.py` | the fitness model (per-bit table, exact expectations), the operator twins' schedule, the preregistered metrics (`metrics()`, shared with the adjudicator), the prediction artifact |
| `host/claimb_r1p_plan.py` | the plan: master seed by rule + exclusions (incl. pair seeds vs every L6 schedule), N from the pinned calibrations through the instrument's policy-matched rule with the window as ceiling, the audit schedule, frame count and budgets, the S #3 post-hoc validation, blocks |
| `host/claimb_r1p_adjudicate.py` | the adjudication over an evidence directory: binding → the instrument's validators (unchanged) → completion → window → known answer → metrics vs prediction |
| `host/claimb_r1p_runner.py` | the board runner: the fail-closed preflight (§7), the session function copied from the instrument's `run_l6`, adjudication from the files as written |
| `host/claimb_r1p_test_report.py` | the clean-tree test report (fail-closed), §8 |
| `evidence/claimb_round1prime/plan.json` | the plan (sha256 pinned in the manifest) |
| `evidence/claimb_round1prime/model_prediction.json` | the prediction: base scores, per-bit table, exact expectations, every candidate's seq/pair/arm/genome/bits/gain/six predicted counters, the metrics and the predicted outcome (sha256 pinned) |
| `tests/test_claimb_r1p_{instrument,model,plan,adjudicate,runner}.py` | 57 tests, §8 |

## 2. The predictor's validation on S #3 — instrument use only

`zynq-psoracle/host/p3_oracle.py:predict_scores` over the expected truth tables of each
record (which the instrument's validator already requires to equal the readout) was run
over S #3's `run_log.json` (sha in the instrument's rate report `inputs`): **12 570 SCORED
records, 12 570 matches, 0 mismatches**, baselines included. This used S #3 to validate the
predictor's fidelity and for nothing else — no arm, no metric, no holdout was computed from
it; the adjudicator refuses S #3's directory as Claim B data by its binding
(`test_s3s_evidence_is_refused_as_claim_b_data`).

## 3. The budget derivation (`plan.json`; the preregistration §6)

| | |
|---|---|
| window W | 6763.9 s (S #3's span, the owner's ceiling) |
| rates (policy_matched_wall, this round's audit fraction 0.06279) | C1 #6: 6982.1933 /h; C2 #2: 6950.3715 /h |
| product | 0.9 × 6950.3715 × 6763.9 / 3600 = 11752.9044 |
| **N** | **11 752** (5 876 pairs; whole pairs) |
| audited records (sampled 1/16 + brackets) | 738 |
| expected inbound frames / CRC and bad-frame budget | 218 217 / 873 |
| runner deadline | 6763.9 s after `go` (open at the deadline → STOPPED → HOLD) |
| post-hoc validation at S #3's pace (normalised interval 0.5381 s) | predicted 6323.6 s ≤ 6425.7 s (0.95 W) — PASS, margin 102.1 s |
| settle bound | 10 × 16 polls |
| master seed | 1 281 816 666 (rule in §7 of the preregistration; 0 pair-seed collisions over 6 348 L6 pairs) |

## 4. The preregistered prediction (`model_prediction.json`, sha `33c259a5…`)

| | |
|---|---|
| base scores | train `[18, 22, 20, 20, 20, 18]` = 118; holdout (arithmetic only) 74 |
| per-bit table | 102 gains, 81 losses, 59 holdout-gains, 50 holdout-losses (train-slice zeros) |
| exact E[gain] per candidate | random-safe 0.287671; map-guided 0.289427 |
| primary (16 blocks × 367 pairs, best-of-block) | every block `+4` vs `+4`; 0 positive, 16 ties → **map-guided better = false** (falsifier 1) |
| secondary (5 876 paired differences) | mean −0.010211; 2 418 + / 2 410 − / 1 048 ties |
| per candidate | seq, pair, seed, arm, genome, the four bits, gain, the six predicted counters — 11 752 rows |

## 5. The ruling pair — DRAFT texts, for the owner to issue after the freeze

The manifest's sha256 below is the one **after** the owner writes the frozen prereg hash into
it and commits; it is therefore unknown today and left as `<manifest sha256 at freeze>`.

```json
{"ruling": "whole-of-run Claim B round 1′", "boardid": "17A6", "granted_by": "14sea",
 "date": "<YYYY-MM-DD-NN>", "session": "B", "master_seed": 1281816666,
 "prereg_sha256": "<sha256 of docs/claimb_round1prime_preregistration.md as frozen>",
 "image_sha256": "5deee74c44785ebe88168ccffaa5f399f26a7c5a567fccb3d430cf4eb14cdc7c",
 "claimb_manifest_sha256": "<manifest sha256 at freeze>"}
```
```json
{"ruling": "provisioning P3-K", "boardid": "17A6", "granted_by": "14sea",
 "date": "<YYYY-MM-DD-NN>", "session": "B",
 "prereg_sha256": "<sha256 of docs/claimb_round1prime_preregistration.md as frozen>",
 "image_sha256": "5deee74c44785ebe88168ccffaa5f399f26a7c5a567fccb3d430cf4eb14cdc7c",
 "claimb_manifest_sha256": "<manifest sha256 at freeze>"}
```

Both go into `rulings/` (gitignored), are consumed once by any outcome, and are refused on
any binding mismatch. The P3-K text is the instrument's own; its signer
(`zynq-psoracle/host/sign_arm.py`) checks only the text, and this round's runner checks the
bindings.

## 6. What a board session needs (the requirements the ruling listed)

- **A fresh power cycle** before the session (one epoch per power cycle; the S2 button is
  unreliable — physical Type-C unplug), UART re-enumeration checked (`/dev/ebaz-uart`).
- **The D4 principal boundary** produced as the runner < 6 h before `go`:
  `zynq-psoracle/host/verify_principal_boundary.py --out …` — R1–R5 PASS; the runner binds
  the record to its own OS user, signer user and key path.
- **The image binary** `p3_app_l6.bin` (`5deee74c…`; gitignored in the instrument) from the
  read-only backup `/home/test/psoracle_backups/2026-09-04_S3_v0.7/artifacts/`, hash-checked
  by the runner. **The carrier** from the instrument's `builds/p3/` (pinned).
- **The instrument** at `689dde1`, clean — verified before any import.
- **The rulings** (§5), then:

```bash
cd /home/test/zynq_fabricmap && python3 host/claimb_r1p_runner.py \
  --ruling rulings/claimb_b_<date>.json --provision-ruling rulings/p3_k_<date>.json \
  --boundary <boundary json> --out evidence/claimb_round1prime/b_17A6_<date> \
  --image /home/test/psoracle_backups/2026-09-04_S3_v0.7/artifacts/firmware_bsp_out_p3_app_l6.bin
```

- **Stop-loss** (preregistration §9): one ruling = one session; any non-`COMPLETED` end, a
  short run, a span past the window, a known-answer mismatch = HOLD; the instrument's
  two-strikes / three-without-COMPLETED rules; nothing argued into a PASS.
- **Evidence** (~230 MB per session, as S #3): plan the push (Git LFS or a summary) before
  the session, not after.

## 7. Fail-closed today — what the runner does with this package as committed

`python3 host/claimb_r1p_runner.py --ruling … --provision-ruling … --boundary … --out … --image …`
on the committed manifest: **REFUSED: the round 1′ preregistration is not frozen (manifest
prereg.sha256 is null): host-only until the owner freezes it** — after the two ruling files
have been checked for their text, board and consumption marker, and before any instrument
import, port open or ruling consumption. With a fixture "frozen" manifest the later checks
are reached one by one (`tests/test_claimb_r1p_runner.py`): the document not hashing, a wrong
plan pin, an image that is not the pinned bytes, a ruling bound to another seed or another
manifest, a boundary record that is stale.

## 8. Tests and the clean-tree proof

57 new tests (`tests/test_claimb_r1p_*.py`): the instrument pin table regenerates equal and
refuses one altered hash / another commit / a missing checkout; the bit table's shape, the
base scores, the additive table against P3's exact predictor on real candidates, the
decision rule in both directions on synthetic blocks, the committed prediction regenerating
identically; the seed rule advancing past an excluded value, the pair-seed check detecting
a collision (L6's S seed collides on every pair) and finding none for the pinned seed, the
committed plan regenerating identically and fitting the window, compatibility drift refused;
the adjudicator's PASS on a synthetic run equal to the prediction (reading the NEGATIVE),
HOLD on one altered score naming the seq, HOLD on a short run and on a span past the window,
REFUSED on another session/seed and on **S #3's real evidence**, the positive reading on
synthetic lifted blocks; the runner's refusal order.

Whole suite: **see the report cited below** — a dirty tree skips 27 carrier-authority tests
and hides 5, so only a report with `worktree_dirty: false`, `skipped: 0`, the instrument at
`689dde1` and clean is the proof (`host/claimb_r1p_test_report.py`, `clean_tree_proof: true`).

Report: `evidence/claimb_round1prime/tests/test_report_2026-09-05T090046Z.json` — ran **1295**, skipped **0**, failures 0,
errors 0, `OK`; `head_at_run` `23f0f3e64ace` (the package commit),
`worktree_dirty` False; instrument `689dde1dad37` = pinned, dirty False;
**`clean_tree_proof: True`**. The report also carries the sha256 of the manifest, the pin table,
the plan, the prediction and the preregistration as they were when the suite ran.

## 9. Status line

| | |
|---|---|
| preregistration | DRAFT v0.1, never frozen — **round 1′ WITHDRAWN BEFORE FREEZE / NO-RUN (owner 2026-09-05, on two audits of §0)**; not a Claim B negative; kept as the instrument's known-answer fixture and the template for stage B2 of `docs/autonomous_cartography_roadmap.md` |
| plan / prediction | generated and pinned (`plan.json` `454abf1f…`, `model_prediction.json` `33c259a5…`) |
| instrument | `zynq-psoracle` `689dde1`, archived, read-only, 128 files pinned |
| board contact | **none**; this round will not run (withdrawn); the next board work is stage B1 of the roadmap, under its own package and ruling |
| disposition (ruled 2026-09-05) | **WITHDRAWN BEFORE FREEZE / NO-RUN.** Not a Claim B negative. Kept as the instrument's known-answer fixture and as the template for stage B2 of `docs/autonomous_cartography_roadmap.md`; nothing here is asked of the owner any more |
| test report | `test_report_2026-09-05T090046Z.json`: 1295 ran / 0 skipped / OK on a clean tree at `23f0f3e64ace`, clean_tree_proof true |

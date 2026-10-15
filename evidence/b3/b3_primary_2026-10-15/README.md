# B3 lifecycle 2 — the pooled primary — 2026-10-15

The owner authorised the pooled unit on 2026-10-15 after all eight pairs had a PASS session (sessions 0–7, session 0 = attempt
-02; `3246c15`). Run at HEAD `3246c15` on the committed S3 manifest `258bb14c…`, the pinned plan `b202a280…` and
prediction `92b774ea…` (`inputs.json`: their digests, read from the tree).

## The inputs: eight fresh restores, each in its own process, all ACCEPT

Each session's own `restore_rejudge.py --keep` was run in its own process (`rejudge/<session>.json`, `.stdout.txt`), four at a
time; every restore ACCEPTed (the sixteen files by size and sha256, the seal, the archived manifest verified at S3 with the 88
pins, the plan and prediction through the pin, the SEARCH session plan rebuilt from the authoritative inputs, the production
judge equal to the archived verdict, the boundary record), and every restored `run_log.json` hashes to the digest the session's
`archive.json` records:

| session | archive.json | restore / judge | restored run_log.json |
|---|---|---|---|
| evidence/b3/b3_17A6_2026-10-14-02 | `7b44c3dae43a2a50…` | ACCEPT / PASS | `ef9917539261e4c2…` (equal) |
| evidence/b3/b3_17A6_2026-10-15-01 | `88885e06719e1887…` | ACCEPT / PASS | `60f2f87bb040052e…` (equal) |
| evidence/b3/b3_17A6_2026-10-15-02 | `a21506736e359d3c…` | ACCEPT / PASS | `e6640e9d69c41ea2…` (equal) |
| evidence/b3/b3_17A6_2026-10-15-03 | `7c854ec734333a64…` | ACCEPT / PASS | `f69dafe0122f76f3…` (equal) |
| evidence/b3/b3_17A6_2026-10-15-04 | `dd37332ed0e93dc1…` | ACCEPT / PASS | `de278b67330e7d53…` (equal) |
| evidence/b3/b3_17A6_2026-10-15-05 | `3482cbe86163278d…` | ACCEPT / PASS | `9b0ed305fa45a8f1…` (equal) |
| evidence/b3/b3_17A6_2026-10-15-06 | `0c9f7a23ba6b70c8…` | ACCEPT / PASS | `351353965ef94dc7…` (equal) |
| evidence/b3/b3_17A6_2026-10-15-07 | `f64ac146101b68a7…` | ACCEPT / PASS | `2e8d25d87fd9433e…` (equal) |

The restored temporary directories were removed after the adjudication; `run_record.json` records every restored file's digest.

## The adjudication

The exact command is in `command.txt`; `adjudicate.stdout.txt` is the tool's output (`adjudicate.stderr.txt` is empty), exit 0
(`exit_codes.txt`); `adjudication.json` is the verdict as written (sha256 `1b8f092d1c7a32507862b40a10cfb33efdc2cf686366bf80290dc38b503b7403`). `--scope run` over the
eight restored directories in session order, the pinned plan and prediction, the instrument's common validator on (no `--no-common`).

| field | adjudicated | predicted (`evidence/b3/prediction.json`) |
|---|---|---|
| outcome | **PASS** | — |
| coverage | pairs 0–7, 24 024 records replayed, 24 040 readouts served, 24 024 checked | 8 pairs |
| findings / kills | [] / [] | — |
| Δ1 per pair | [11, 9, 7, 7, 4, 6, 9, 2] | [11, 9, 7, 7, 4, 6, 9, 2] (equal) |
| **primary** (one-sided exact sign test over Δ1, α 0.05) | **8 positives / 0 negatives / 0 ties, p = 0.00390625** — `online > random-safe SUPPORTED` | 8 / 0 / 0, p = 0.00390625 (equal) |
| Δ2 per pair (secondary, reported) | [-1, 7, 3, 6, -7, 0, 4, -1] | equal |
| secondary outcome | 4 / 3 / 1, p 0.5, mean 1.375, median 1.5, d 0.301204 — no threshold, no verdict | equal |
| fitness sequence | length 24024, sha256 `8df40ac9a75ca0f9bb965aa65239cb1ac9cd14681f47e219627a7e7543cfde13` | equal |
| online maps | pairs 0–7: decoded 288 / 286 / 289 / 287 / 285 / 290 / 290 / 291, map versions 178 / 179 / 172 / 174 / 169 / 175 / 187 / 180, anomalies 0 everywhere | anomalies 0 |

Every adjudicated quantity equals the preregistered prediction (`run_record.json` → `comparison_with_prediction`, all `equal: true`).

## What this is, and what it is not

This is the preregistered primary of B3 lifecycle 2 (preregistration v0.3.1 §4), computed by the pinned adjudicator from the
eight sessions' served readouts: the board's closed loop reproduced, record for record, the host-predicted outcome, and the
sign test over Δ1 is 8 / 0 / 0 at p = 1/256. It is **not** a result document and authorises nothing: the adjudicator does not
check the manifest pins, the carrier qualification, the instrument's rate / deadline / CRC budgets, the evidence exports or the
ruling bindings (`not_checked_here`) — those are established per session by the production verdicts, the fresh re-judges above,
the archived rulings and boundary records. Standing facts the result document must carry: the formal S2 and S3 clean-tree
proofs did not pass and the two named exceptions apply (`docs/b3_s2_proof_exception_2026_10_14.md`; the S3 node serves as §8's
final proof for engineering purposes by the owner's ruling of 2026-10-15); session 0's first attempt was LOST at the carrier
configuration; sessions 3 and 7 carried heartbeat-burst damage absorbed by rule v07; the transport stop-loss stands; the claim's
scope is one die, one carrier, the content-bit class, F1, one operator and one cartographer rule.

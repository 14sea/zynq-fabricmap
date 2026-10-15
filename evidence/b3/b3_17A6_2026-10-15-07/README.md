# B3 session 7 — lifecycle 2 — 17A6 — 2026-10-15-07 (pair 7, the last of the plan) — **PASS / COMPLETED** (one heartbeat burst damaged, within the rule)

Outcome **PASS / COMPLETED** (`adjudication.json`, `summary.json`, `runner_session.json`): 3 005 records scored and audited
(all-self-reporting), 3 003 candidates replayed for pair 7 (seeds 205178539 / 2230924639, arm order FOR), findings and kills
empty, measured rate **2932.4900045105846 evals/h** (session span 3 688.94 s within the 5 602.70 s deadline; the split's
rate_for_split 2 703.04), epoch end `budget` at seq 3005, online map for pair 7: 291 decoded, map version 180, 0 anomalies.
Bound to the lifecycle-2 S3 manifest `258bb14c…` (`manifest_at_run.json`), under `rulings/b3_2026-10-15-07.json` +
`rulings/p3_k_b3_2026-10-15-07.json` (archived here as `ruling_*.json`, both spent with this outcome), boundary `evidence/b3/principal_boundary_2026-10-15-07.json`
(R1–R5 passed 14:18:23Z; 4 347 s old at finalisation), after a power cycle and usbipd re-attach. The carrier configured
normally (`setup_load`: INT_STS `0xa802000b` → `0x50021004`). First attempt of this session; sessions 0–6 closed PASS
(`c766266`, `03de515`, `50b5420`, `626f228`, `0ff8bd1`, `da973b7`, `fe2f2d1`).

Runner started 14:19:51Z, claim 14:22:22Z, identity page 14:25:51Z, image loaded 14:26:12Z, finalised 15:30:50Z.

## Transport, from the timeline (the one inbound ledger) — read this section

| item | value |
|---|---|
| expected frames / seen | 81 138 / 114 216 |
| HB | **48 078 of 48 080: record 2872 has 14 of its 16 heartbeats** (every other record 16 / 16). Rule v07 holds at most floor(R / 1000) = 3 SCORED records missing any heartbeat for R = 3 005; one record is within it, so the instrument layer raised no finding and the verdict is PASS |
| bad frames | **1** of budget 325, at t = 3 521.0 s — the damaged line of that same burst (below) |
| CRC drops | **11** of budget 325: SIGNREQ at t=0.0 s and REC at 1.1 s are the two **forced controls**; the other nine — REC at 280.8 / 765.8 / 1 573.2 / 2 786.5 s, AUDIT at 1 168.6 / 1 331.3 / 2 867.4 / 2 948.9 / 3 682.2 s — were recovered by rel-v4 (RECGET 5, AUDITGET 24 045 = 24 040 + 5). A CRC failure says a line arrived corrupted, not how |
| fragments | **0** |
| disruptions / rereads | 0 / 0 |

**The damaged heartbeat burst, reconstructed from `console.log` (the raw bytes).** Record 2872's burst arrived as 15 lines instead
of 16: fourteen intact 67-byte `HB 2872` lines (i = 0…6 and 9…15) and one 43-byte line that is **the first 4 bytes of HB i = 7
(`P3L5`) followed immediately by the last 39 bytes of HB i = 8** (`ae400f680b5b4d394 eyJpIjo4fQ== d50e5607`), rejected as a bad
frame. The two heartbeats i = 7…8 would have occupied 136 bytes including separators; 44 were kept; **92 contiguous bytes are
absent with zero replacement bytes** — if one event, a single contiguous inbound deletion. This is the same loss class as
session 3's record 1075 (189 bytes, `626f228`) and B3Q attempt -01 (80 bytes), and, as in session 3, it was absorbed by the
frozen rule inside one record. The owner ruled session 3's occurrence *the same heartbeat-damage class recurring, absorbed by
rule v07's budget* and did not add it to the two-sessions-same-cause count; **this occurrence is reported for the owner's ruling
in the same terms** — the facts are here, the counting decision is not this record's. The mechanism (where on the host-side
path the bytes vanish) remains undetermined.

Not a lost session; the stop-loss stands; nothing here establishes transport stability.

## Layout (form (c))

Eleven ordinary files are what a reviewer reads. The five large exports (≈ 102 MB together) are in **`exports.tar.zst`**
(7,123,861 bytes, sha256 `39c9adcb30c892e032c614f6e88b5e994a2e81d1cb7b5358a3916d85011ba8c2`), a deterministic archive whose member sizes and
digests are in `archive.json`; `exports.json` (sealed by the runner) names the same five files. `restore_rejudge.py` is the
preparation's script byte for byte (sha256 `e42a83ca5fa89d4a1f01a9ef925fbe62ffd52aaf98b409116cd28255a82df556`). The complete original directory (exactly the
16 runner files) is kept read-only at `/home/test/fabricmap_backups/b3_17A6_2026-10-15-07` with `b3_17A6_2026-10-15-07.SHA256SUMS`
(`sha256sum -c` passed at archival).

## The fresh restore and production re-judge, at archival

`python3 -B evidence/b3/b3_17A6_2026-10-15-07/restore_rejudge.py` — **ACCEPT** (`rejudge_result_at_archival.json`, not part of
the session record): the sixteen files by size and sha256; the seal; the archived manifest `258bb14c…` verified at S3 with the
88-file pinned surface; the plan and the prediction verified byte-for-byte through the pin; the SEARCH session plan rebuilt from
the authoritative inputs (pair 7 / count 1, 3 005 records, 81 138 frames, budgets 325, deadline 5 602.696090881941 s) equal to
`summary.json`'s `l6` and `run_log.json`'s `l6`; the production `judge_session` **PASS at 2932.4900045105846 evals/h with zero
keys differing from `adjudication.json`**; `runner_session.json` consistent; the boundary record through the production validator.

This is the last session of the plan. Nothing here authorises the pooled primary, the result document or any transition:
each is a separately authorised unit.

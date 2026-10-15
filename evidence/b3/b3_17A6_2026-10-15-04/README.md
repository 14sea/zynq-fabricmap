# B3 session 4 — lifecycle 2 — 17A6 — 2026-10-15-04 (pair 4) — **PASS / COMPLETED**

Outcome **PASS / COMPLETED** (`adjudication.json`, `summary.json`, `runner_session.json`): 3 005 records scored and audited
(all-self-reporting), 3 003 candidates replayed for pair 4 (seeds 1595133113 / 3832447288, arm order OFR), findings and kills
empty, measured rate **3008.081183656435 evals/h** (session span 3 596.21 s within the 5 602.70 s deadline; the split's
rate_for_split 2 703.04), epoch end `budget` at seq 3005, online map for pair 4: 285 decoded, map version 169, 0 anomalies.
Bound to the lifecycle-2 S3 manifest `258bb14c…` (`manifest_at_run.json`), under `rulings/b3_2026-10-15-04.json` +
`rulings/p3_k_b3_2026-10-15-04.json` (archived here as `ruling_*.json`, both spent with this outcome), boundary `evidence/b3/principal_boundary_2026-10-15-04.json`
(R1–R5 passed 10:05:36Z; 4 416 s old at finalisation), after a power cycle and usbipd re-attach. The carrier configured
normally (`setup_load`: INT_STS `0xa802000b` → `0x50021004`). First attempt of this session; sessions 0–3 closed PASS
(`c766266`, `03de515`, `50b5420`, `626f228`).

Runner started 10:09:16Z, claim 10:11:46Z, identity page 10:15:15Z, image loaded 10:15:36Z, finalised 11:19:12Z.

## Transport, from the timeline (the one inbound ledger)

| item | value |
|---|---|
| expected frames / seen | 81 138 / 114 203 |
| HB | **48 080 = 16 × 3 005 — every heartbeat arrived** |
| CRC drops | **4** of budget 325: SIGNREQ at t=0.0 s and REC at 1.0 s are the two **forced controls**; the other two — AUDIT at 1 715.4 s and REC at 2 118.0 s — were recovered by rel-v4 (RECGET 2, AUDITGET 24 041 = 24 040 + 1). A CRC failure says a line arrived corrupted, not how |
| bad frames | 0 of budget 325 |
| fragments | **0** |
| disruptions / rereads | 0 / 0 |

The quietest of the five main sessions so far (two unforced events). Not a lost session; the stop-loss stands; nothing here
establishes transport stability.

## Layout (form (c))

Eleven ordinary files are what a reviewer reads. The five large exports (≈ 102 MB together) are in **`exports.tar.zst`**
(7,068,652 bytes, sha256 `c64d00f9afe262f50fe24e272404089af5c222367e2353a689e19c442a101c23`), a deterministic archive whose member sizes and
digests are in `archive.json`; `exports.json` (sealed by the runner) names the same five files. `restore_rejudge.py` is the
preparation's script byte for byte (sha256 `e42a83ca5fa89d4a1f01a9ef925fbe62ffd52aaf98b409116cd28255a82df556`). The complete original directory (exactly the
16 runner files) is kept read-only at `/home/test/fabricmap_backups/b3_17A6_2026-10-15-04` with `b3_17A6_2026-10-15-04.SHA256SUMS`
(`sha256sum -c` passed at archival).

## The fresh restore and production re-judge, at archival

`python3 -B evidence/b3/b3_17A6_2026-10-15-04/restore_rejudge.py` — **ACCEPT** (`rejudge_result_at_archival.json`, not part of
the session record): the sixteen files by size and sha256; the seal; the archived manifest `258bb14c…` verified at S3 with the
88-file pinned surface; the plan and the prediction verified byte-for-byte through the pin; the SEARCH session plan rebuilt from
the authoritative inputs (pair 4 / count 1, 3 005 records, 81 138 frames, budgets 325, deadline 5 602.696090881941 s) equal to
`summary.json`'s `l6` and `run_log.json`'s `l6`; the production `judge_session` **PASS at 3008.081183656435 evals/h with zero
keys differing from `adjudication.json`**; `runner_session.json` consistent; the boundary record through the production validator.

Nothing here authorises the next session's ruling pair, the pooled primary or any transition.

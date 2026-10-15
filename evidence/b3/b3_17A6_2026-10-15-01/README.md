# B3 session 1 — lifecycle 2 — 17A6 — 2026-10-15-01 (pair 1) — **PASS / COMPLETED**

Outcome **PASS / COMPLETED** (`adjudication.json`, `summary.json`, `runner_session.json`): 3 005 records scored and audited
(all-self-reporting), 3 003 candidates replayed for pair 1 (seeds 3785070923 / 2731497693, arm order FOR), findings and kills
empty, measured rate **2928.0826286989204 evals/h** (session span 3 694.41 s within the 5 602.70 s deadline; the split's
rate_for_split 2 703.04), epoch end `budget` at seq 3005, online map for pair 1: 286 decoded, map version 179, 0 anomalies.
Bound to the lifecycle-2 S3 manifest `258bb14c…` (`manifest_at_run.json`), under `rulings/b3_2026-10-15-01.json` +
`rulings/p3_k_b3_2026-10-15-01.json` (archived here as `ruling_*.json`, both spent with this outcome), boundary `evidence/b3/principal_boundary_2026-10-15-01.json`
(R1–R5 passed 05:38:08Z; 4 376 s old at finalisation), after a power cycle and usbipd re-attach. The carrier configured
normally (`setup_load`: INT_STS `0xa802000b` → `0x50021004`). First attempt of this session; session 0 (pair 0) closed PASS at
`c766266`.

Runner started 05:40:12Z, claim 05:42:43Z, identity page 05:46:11Z, image loaded 05:46:32Z, finalised 06:51:04Z.

## Transport, from the timeline (the one inbound ledger)

| item | value |
|---|---|
| expected frames / seen | 81 138 / 114 217 |
| HB | **48 080 = 16 × 3 005 — every heartbeat arrived** |
| CRC drops | **11** of budget 325: SIGNREQ at t=0.1 s and REC at 1.2 s are the two **forced controls** (identity flags 0x32); the other nine — REC at 215.5 / 888.4 / 974.3 / 1 132.8 / 1 295.5 / 2 189.0 / 2 593.9 / 3 645.1 s and AUDIT at 764.1 s — were recovered by rel-v4 (RECGET 9, AUDITGET 24 041 = 24 040 + 1). A CRC failure says a line arrived corrupted, not how; the cause of these nine is not determined here |
| bad frames | 0 of budget 325 |
| fragments | **0** |
| disruptions / rereads | 0 / 0 |

Nine unforced CRC drops against session 0's four (and two fragments there, none here): more inbound events, all absorbed inside
the frozen budgets and rules; the mechanism is not established by these records. Not a lost session; it does not count toward
the two-sessions-same-cause stop-loss, which stands. Nothing here establishes transport stability.

## Layout (form (c))

Eleven ordinary files are what a reviewer reads. The five large exports (≈ 102 MB together) are in **`exports.tar.zst`**
(7,123,620 bytes, sha256 `35dd55ddf22bef981fe1bbb843463853bea65f6bbfd4d2b47084ae34b5579c34`), a deterministic archive whose member sizes and
digests are in `archive.json`; `exports.json` (sealed by the runner) names the same five files. `restore_rejudge.py` is the
preparation's script byte for byte (sha256 `e42a83ca5fa89d4a1f01a9ef925fbe62ffd52aaf98b409116cd28255a82df556`). The complete original directory (exactly the
16 runner files) is kept read-only at `/home/test/fabricmap_backups/b3_17A6_2026-10-15-01` with `b3_17A6_2026-10-15-01.SHA256SUMS`
(`sha256sum -c` passed at archival).

## The fresh restore and production re-judge, at archival

`python3 -B evidence/b3/b3_17A6_2026-10-15-01/restore_rejudge.py` — **ACCEPT** (`rejudge_result_at_archival.json`, not part of
the session record): the sixteen files by size and sha256; the seal; the archived manifest `258bb14c…` verified at S3 with the
88-file pinned surface; the plan and the prediction verified byte-for-byte through the pin; the SEARCH session plan rebuilt from
the authoritative inputs (pair 1 / count 1, 3 005 records, 81 138 frames, budgets 325, deadline 5 602.696090881941 s) equal to
`summary.json`'s `l6` and `run_log.json`'s `l6`; the production `judge_session` **PASS at 2928.0826286989204 evals/h with zero
keys differing from `adjudication.json`**; `runner_session.json` consistent; the boundary record through the production validator.

Nothing here authorises the next session's ruling pair, the pooled primary or any transition.

# B3 session 2 — lifecycle 2 — 17A6 — 2026-10-15-02 (pair 2) — **PASS / COMPLETED**

Outcome **PASS / COMPLETED** (`adjudication.json`, `summary.json`, `runner_session.json`): 3 005 records scored and audited
(all-self-reporting), 3 003 candidates replayed for pair 2 (seeds 3587510309 / 2084003005, arm order ORF), findings and kills
empty, measured rate **2960.5452960695798 evals/h** (session span 3 654.04 s within the 5 602.70 s deadline; the split's
rate_for_split 2 703.04), epoch end `budget` at seq 3005, online map for pair 2: 289 decoded, map version 172, 0 anomalies.
Bound to the lifecycle-2 S3 manifest `258bb14c…` (`manifest_at_run.json`), under `rulings/b3_2026-10-15-02.json` +
`rulings/p3_k_b3_2026-10-15-02.json` (archived here as `ruling_*.json`, both spent with this outcome), boundary `evidence/b3/principal_boundary_2026-10-15-02.json`
(R1–R5 passed 07:11:44Z; 4 493 s old at finalisation), after a power cycle and usbipd re-attach. The carrier configured
normally (`setup_load`: INT_STS `0xa802000b` → `0x50021004`). First attempt of this session; sessions 0 and 1 closed PASS at
`c766266` and `03de515`.

Runner started 07:15:52Z, claim 07:18:24Z, identity page 07:21:53Z, image loaded 07:22:13Z, finalised 08:26:37Z.

## Transport, from the timeline (the one inbound ledger)

| item | value |
|---|---|
| expected frames / seen | 81 138 / 114 211 |
| HB | **48 080 = 16 × 3 005 — every heartbeat arrived** |
| CRC drops | **7** of budget 325: SIGNREQ at t=0.1 s and REC at 1.2 s are the two **forced controls** (identity flags 0x32); the other five — AUDIT at 413.3 / 1 546.3 / 2 269.7 / 2 672.2 s and REC at 1 948.5 s — were recovered by rel-v4 (RECGET 2, AUDITGET 24 045 = 24 040 + 5). A CRC failure says a line arrived corrupted, not how; the cause of these five is not determined here |
| bad frames | 0 of budget 325 |
| fragments | **1** resync ("a frame head arrived with no line end before it"): an AUDIT line of seq 540 at 658.2 s — the next frame head arrived before the line's end; the audit was re-served (the fifth extra AUDITGET) and nothing was lost. The 672 bytes are the length of the fragment the host kept, not a measured number of lost bytes |
| disruptions / rereads | 0 / 0 |

Six inbound events besides the two forced controls (five unforced CRC drops and one fragment), all absorbed inside the
frozen budgets and rules; their mechanism is not established by these records. Not a lost session; it does not count toward
the two-sessions-same-cause stop-loss, which stands. Nothing here establishes transport stability.

## Layout (form (c))

Eleven ordinary files are what a reviewer reads. The five large exports (≈ 102 MB together) are in **`exports.tar.zst`**
(7,112,527 bytes, sha256 `5b145a2cec83c2ea1ff244cb857f963f95b2a8e9bfd9e257dc55fca95cfad51e`), a deterministic archive whose member sizes and
digests are in `archive.json`; `exports.json` (sealed by the runner) names the same five files. `restore_rejudge.py` is the
preparation's script byte for byte (sha256 `e42a83ca5fa89d4a1f01a9ef925fbe62ffd52aaf98b409116cd28255a82df556`). The complete original directory (exactly the
16 runner files) is kept read-only at `/home/test/fabricmap_backups/b3_17A6_2026-10-15-02` with `b3_17A6_2026-10-15-02.SHA256SUMS`
(`sha256sum -c` passed at archival).

## The fresh restore and production re-judge, at archival

`python3 -B evidence/b3/b3_17A6_2026-10-15-02/restore_rejudge.py` — **ACCEPT** (`rejudge_result_at_archival.json`, not part of
the session record): the sixteen files by size and sha256; the seal; the archived manifest `258bb14c…` verified at S3 with the
88-file pinned surface; the plan and the prediction verified byte-for-byte through the pin; the SEARCH session plan rebuilt from
the authoritative inputs (pair 2 / count 1, 3 005 records, 81 138 frames, budgets 325, deadline 5 602.696090881941 s) equal to
`summary.json`'s `l6` and `run_log.json`'s `l6`; the production `judge_session` **PASS at 2960.5452960695798 evals/h with zero
keys differing from `adjudication.json`**; `runner_session.json` consistent; the boundary record through the production validator.

Nothing here authorises the next session's ruling pair, the pooled primary or any transition.

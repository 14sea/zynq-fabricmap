# B3 session 5 — lifecycle 2 — 17A6 — 2026-10-15-05 (pair 5) — **PASS / COMPLETED**

Outcome **PASS / COMPLETED** (`adjudication.json`, `summary.json`, `runner_session.json`): 3 005 records scored and audited
(all-self-reporting), 3 003 candidates replayed for pair 5 (seeds 556892415 / 1747787438, arm order FRO), findings and kills
empty, measured rate **2895.5920859950797 evals/h** (session span 3 735.83 s within the 5 602.70 s deadline; the split's
rate_for_split 2 703.04), epoch end `budget` at seq 3005, online map for pair 5: 290 decoded, map version 175, 0 anomalies.
Bound to the lifecycle-2 S3 manifest `258bb14c…` (`manifest_at_run.json`), under `rulings/b3_2026-10-15-05.json` +
`rulings/p3_k_b3_2026-10-15-05.json` (archived here as `ruling_*.json`, both spent with this outcome), boundary `evidence/b3/principal_boundary_2026-10-15-05.json`
(R1–R5 passed 11:29:48Z; 4 391 s old at finalisation), after a power cycle and usbipd re-attach. The carrier configured
normally (`setup_load`: INT_STS `0xa802000b` → `0x50021004`). First attempt of this session; sessions 0–4 closed PASS
(`c766266`, `03de515`, `50b5420`, `626f228`, `0ff8bd1`).

Runner started 11:31:45Z, claim 11:34:16Z, identity page 11:37:44Z, image loaded 11:38:05Z, finalised 12:42:59Z.

## Transport, from the timeline (the one inbound ledger)

| item | value |
|---|---|
| expected frames / seen | 81 138 / 114 222 |
| HB | **48 080 = 16 × 3 005 — every heartbeat arrived** |
| CRC drops | **14** of budget 325: SIGNREQ at t=0.1 s and REC at 1.1 s are the two **forced controls**; the other twelve — REC at 182.6 / 1 000.0 / 1 081.7 / 2 470.3 / 2 552.0 / 2 961.2 / 3 696.4 s, AUDIT at 3 042.8 / 3 124.6 / 3 212.6 s, SIGNREQ at 3 171.9 s, and one line at 510.0 s whose type the ledger could not classify — were all recovered by rel-v4 (RECGET 8, AUDITGET 24 043 = 24 040 + 3; the SIGNREQ and the unclassified line were retransmitted by the board). The unclassified line, read from `console.ts.log`, is the `AUDIT_READY 425` line arriving 162 bytes long where its retransmission is the full length — a damaged line, re-sent; record 425's sixteen heartbeats are all present. A CRC failure says a line arrived corrupted, not how |
| bad frames | 0 of budget 325 |
| fragments | **0** |
| disruptions / rereads | 0 / 0 |

Twelve unforced events, the most of the six main sessions so far, all absorbed inside the frozen budgets (the CRC budget is
325) and rules; their mechanism is not established by these records. Not a lost session; the stop-loss stands; nothing here
establishes transport stability.

## Layout (form (c))

Eleven ordinary files are what a reviewer reads. The five large exports (≈ 102 MB together) are in **`exports.tar.zst`**
(7,133,097 bytes, sha256 `6853f448c3b487a027bef5c832b6f7cbe2ec94bef41c95016b2e15848af04c49`), a deterministic archive whose member sizes and
digests are in `archive.json`; `exports.json` (sealed by the runner) names the same five files. `restore_rejudge.py` is the
preparation's script byte for byte (sha256 `e42a83ca5fa89d4a1f01a9ef925fbe62ffd52aaf98b409116cd28255a82df556`). The complete original directory (exactly the
16 runner files) is kept read-only at `/home/test/fabricmap_backups/b3_17A6_2026-10-15-05` with `b3_17A6_2026-10-15-05.SHA256SUMS`
(`sha256sum -c` passed at archival).

## The fresh restore and production re-judge, at archival

`python3 -B evidence/b3/b3_17A6_2026-10-15-05/restore_rejudge.py` — **ACCEPT** (`rejudge_result_at_archival.json`, not part of
the session record): the sixteen files by size and sha256; the seal; the archived manifest `258bb14c…` verified at S3 with the
88-file pinned surface; the plan and the prediction verified byte-for-byte through the pin; the SEARCH session plan rebuilt from
the authoritative inputs (pair 5 / count 1, 3 005 records, 81 138 frames, budgets 325, deadline 5 602.696090881941 s) equal to
`summary.json`'s `l6` and `run_log.json`'s `l6`; the production `judge_session` **PASS at 2895.5920859950797 evals/h with zero
keys differing from `adjudication.json`**; `runner_session.json` consistent; the boundary record through the production validator.

Nothing here authorises the next session's ruling pair, the pooled primary or any transition.

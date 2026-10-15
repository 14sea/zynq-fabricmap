# B3 session 0, attempt 2 — lifecycle 2 — 17A6 — 2026-10-14-02 (pair 0) — **PASS / COMPLETED**

Outcome **PASS / COMPLETED** (`adjudication.json`, `summary.json`, `runner_session.json`): 3 005 records scored and audited
(all-self-reporting; chain length 3 006), 3 003 candidates replayed for pair 0, findings and kills empty, measured rate
**2946.7341436762595 evals/h** (session span 3 671.09 s within the 5 602.70 s deadline; the split's rate_for_split 2 703.04),
epoch end `budget` at seq 3005, online map for pair 0: 288 decoded, map version 178, 0 anomalies. Bound to the lifecycle-2
S3 manifest `258bb14c…` (`manifest_at_run.json`), under `rulings/b3_2026-10-14-02.json` + `rulings/p3_k_b3_2026-10-14-02.json`
(archived here as `ruling_*.json`, both spent with this outcome), boundary `evidence/b3/principal_boundary_2026-10-14-04.json`
(R1–R5 passed 20:17:01Z; 4 473 s old at finalisation). Attempt 1 of this session (`evidence/b3/b3_17A6_2026-10-14-01/`, `7677d23`)
was LOST at the carrier configuration before any session; this attempt, authorised separately after a second power cycle,
configured the carrier normally (`setup_load`: INT_STS `0xa802000b` → `0x50021004`, plmark set).

Runner started 20:20:38Z, claim 20:23:10Z, identity page 20:26:38Z, image loaded 20:26:59Z, finalised 21:31:33Z.

## Transport, from the timeline (the one inbound ledger)

| item | value |
|---|---|
| expected frames / seen | 81 138 / 114 209 (the extra are the reply and request kinds the schedule does not count) |
| HB | **48 080 = 16 × 3 005 — every heartbeat arrived** (rule v07's record budget of 3 unused) |
| CRC drops | **6** of budget 325: SIGNREQ at t=0.0 s and REC at 1.1 s are the two **forced controls** (identity flags 0x32); the other four — REC at 875.8 s, AUDIT at 215.6 / 1 519.0 / 2 162.5 s — were recovered by rel-v4 (RECGET 2, AUDITGET 24 043 = 24 040 + 3). A CRC failure says a line arrived corrupted; it does not by itself say how (a deletion, a substitution, an insertion) — the cause of these four is not determined here |
| bad frames | 0 of budget 325 |
| fragments | **2** resyncs ("a frame head arrived with no line end before it"): a SIGNREQ line of seq 93 at 113.3 s and an AUDIT_READY line of seq 2018 at 2 410.6 s — in each case the next frame head arrived before the line's end; the board retransmitted and no record, audit or heartbeat was lost. The 320 and 160 bytes are the lengths of the fragments the host kept, not a measured number of lost bytes |
| disruptions / rereads | 0 / 0 |

So this session saw six inbound transport events besides the two forced controls (four unforced CRC drops and two fragments
in 3 671 s, ≈ 26 MB of console); their mechanism is not established by these records (the fragments are consistent with a lost
line end, the CRC drops with any corruption). All were absorbed inside the frozen budgets and rules; it is not a lost session
and does not count toward the two-sessions-same-cause stop-loss, which stands. Nothing here establishes transport stability.

## Layout (form (c), the owner's archival ruling of 2026-10-14)

Eleven ordinary files are what a reviewer reads. The five large exports — `audits.json`, `console.log`, `console.ts.log`,
`run_log.json`, `timeline.json` (≈ 102 MB together) — are in **`exports.tar.zst`** (7,057,839 bytes, sha256
`cf31b6080c0d5ba6e4ad3053f87acff31ac9c4ca901f19353abe3c1ef2178362`), a deterministic archive whose member sizes and digests are in `archive.json`;
`exports.json` (sealed by the runner) names the same five files. `restore_rejudge.py` is the preparation's script byte for byte
(sha256 `e42a83ca5fa89d4a1f01a9ef925fbe62ffd52aaf98b409116cd28255a82df556`, equal to the preparation copy). The complete original directory (exactly the 16
runner files) is kept read-only outside the repository at `/home/test/fabricmap_backups/b3_17A6_2026-10-14-02` with `b3_17A6_2026-10-14-02.SHA256SUMS`
(`sha256sum -c` passed at archival).

## The fresh restore and production re-judge, at archival

`python3 -B evidence/b3/b3_17A6_2026-10-14-02/restore_rejudge.py` (from the repository root) — **ACCEPT**
(`rejudge_result_at_archival.json`, not part of the session record): exactly the sixteen files restored by size and sha256; the
seal; the archived manifest `258bb14c…` verified at S3 (qualified, no refusal) with the 88-file pinned surface; the plan and the
prediction verified byte-for-byte through the manifest's pin; the SEARCH session plan **rebuilt from the authoritative inputs**
(`search_session_plan`: pair 0 / count 1, 3 005 records, 81 138 frames, budgets 325, deadline 5 602.696090881941 s) equal to
`summary.json`'s `l6` and to `run_log.json`'s `l6`; the production `judge_session` **PASS at 2946.7341436762595 evals/h with zero keys
differing from `adjudication.json`**; `runner_session.json` consistent with the rebuilt plan and that verdict; the boundary record through
the production validator. This is the first production SEARCH run of the script (the preparation could prove it only on B3Q evidence).

Nothing here authorises the next session's ruling pair, the pooled primary or any transition.

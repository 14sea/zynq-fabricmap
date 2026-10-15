# B3 session 3 — lifecycle 2 — 17A6 — 2026-10-15-03 (pair 3) — **PASS / COMPLETED** (one heartbeat burst damaged, within the rule)

Outcome **PASS / COMPLETED** (`adjudication.json`, `summary.json`, `runner_session.json`): 3 005 records scored and audited
(all-self-reporting), 3 003 candidates replayed for pair 3 (seeds 3491865220 / 1136202755, arm order ROF), findings and kills
empty, measured rate **3006.3651197597505 evals/h** (session span 3 598.39 s within the 5 602.70 s deadline; the split's
rate_for_split 2 703.04), epoch end `budget` at seq 3005, online map for pair 3: 287 decoded, map version 174, 0 anomalies.
Bound to the lifecycle-2 S3 manifest `258bb14c…` (`manifest_at_run.json`), under `rulings/b3_2026-10-15-03.json` +
`rulings/p3_k_b3_2026-10-15-03.json` (archived here as `ruling_*.json`, both spent with this outcome), boundary `evidence/b3/principal_boundary_2026-10-15-03.json`
(R1–R5 passed 08:39:56Z; 4 323 s old at finalisation), after a power cycle and usbipd re-attach. The carrier configured
normally (`setup_load`: INT_STS `0xa802000b` → `0x50021004`). First attempt of this session; sessions 0, 1 and 2 closed PASS
(`c766266`, `03de515`, `50b5420`).

Runner started 08:41:22Z, claim 08:43:54Z, identity page 08:47:22Z, image loaded 08:47:42Z, finalised 09:51:59Z.

## Transport, from the timeline (the one inbound ledger) — read this section

| item | value |
|---|---|
| expected frames / seen | 81 138 / 114 214 |
| HB | **48 076 of 48 080: record 1075 has 12 of its 16 heartbeats** (every other record 16 / 16). Rule v07 holds at most floor(R / 1000) = 3 SCORED records missing any heartbeat for R = 3 005; one record is within it, so the instrument layer raised no finding and the verdict is PASS |
| bad frames | **1** of budget 325, at t = 1 258.6 s — the damaged line of that same burst (below) |
| CRC drops | **10** of budget 325: SIGNREQ at t=0.0 s and REC at 1.1 s are the two **forced controls**; the other eight — REC at 211.7 / 690.8 / 2 360.1 / 2 597.9 / 2 756.7 s, AUDIT at 1 406.5 / 1 646.1 / 2 042.6 s — were recovered by rel-v4 (RECGET 6, AUDITGET 24 044 = 24 040 + 4) |
| fragments | **1**: an AUDIT line of seq 2122 at 2 520.4 s, reason `pull timeout: seq 2122 chunk 0` (608 bytes kept) — the audit chunk was pulled again; nothing lost |
| disruptions / rereads | 0 / 0 |

**The damaged heartbeat burst, reconstructed from `console.log` (the raw bytes, not the timestamped copy).** Record 1075's
burst arrived as 13 lines instead of 16: twelve intact 67-byte `HB 1075` lines (i = 0…10 and 15) and one 82-byte line that is
**the first 52 bytes of HB i = 11 followed immediately by the last 30 bytes of HB i = 14** (`P3L5 HB 1075 <tag> eyJpIj` + `159ea85d eyJpIjoxNH0= 9175f4f2`),
rejected as a bad frame. The four heartbeats i = 11…14 would have occupied 272 bytes including separators; 83 were kept; **189
contiguous bytes are absent with zero replacement bytes** — if one event, a single contiguous inbound deletion. This is the same
loss class as B3Q attempt -01 (`evidence/b3/b3q_17A6_2026-10-14-01/`: a 51-byte prefix and an 80-byte deletion inside a heartbeat
burst), which ended HOLD only because R = 125 gives a record budget of 0. **Here the same class of event, inside one record,
was absorbed by the frozen rule and the session is PASS.** Whether it counts toward the owner's cross-session counting ("a
contiguous inbound deletion causing a session HOLD" counted once for B3Q -01) is the owner's ruling, not this record's; the
facts are stated here so that it can be made. The mechanism (where on the host-side path the bytes vanish) remains undetermined,
as in every earlier observation.

**The owner's ruling (2026-10-15, on review of this session):** recorded as *the same heartbeat-damage class recurring, absorbed by
rule v07's budget* — one record short of heartbeats against a budget of three, no HOLD and no LOST — and therefore **not added to the
two-sessions-same-cause count**; the earlier HOLD and LOST counts stand; the stop-loss is not lifted. Not a lost session; nothing here
establishes transport stability.

## Layout (form (c))

Eleven ordinary files are what a reviewer reads. The five large exports (≈ 102 MB together) are in **`exports.tar.zst`**
(7,108,298 bytes, sha256 `edf92e71178ebd7b38f8060870d3f543e196bc044b2af6ae1cb2c4972d1fe9bc`), a deterministic archive whose member sizes and
digests are in `archive.json`; `exports.json` (sealed by the runner) names the same five files. `restore_rejudge.py` is the
preparation's script byte for byte (sha256 `e42a83ca5fa89d4a1f01a9ef925fbe62ffd52aaf98b409116cd28255a82df556`). The complete original directory (exactly the
16 runner files) is kept read-only at `/home/test/fabricmap_backups/b3_17A6_2026-10-15-03` with `b3_17A6_2026-10-15-03.SHA256SUMS`
(`sha256sum -c` passed at archival).

## The fresh restore and production re-judge, at archival

`python3 -B evidence/b3/b3_17A6_2026-10-15-03/restore_rejudge.py` — **ACCEPT** (`rejudge_result_at_archival.json`, not part of
the session record): the sixteen files by size and sha256; the seal; the archived manifest `258bb14c…` verified at S3 with the
88-file pinned surface; the plan and the prediction verified byte-for-byte through the pin; the SEARCH session plan rebuilt from
the authoritative inputs (pair 3 / count 1, 3 005 records, 81 138 frames, budgets 325, deadline 5 602.696090881941 s) equal to
`summary.json`'s `l6` and `run_log.json`'s `l6`; the production `judge_session` **PASS at 3006.3651197597505 evals/h with zero
keys differing from `adjudication.json`**; `runner_session.json` consistent; the boundary record through the production validator.

Nothing here authorises the next session's ruling pair, the pooled primary or any transition.

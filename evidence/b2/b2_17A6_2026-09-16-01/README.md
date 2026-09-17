# B2 session 1 — lifecycle 2 — 17A6 — 2026-09-16-01 (pairs 0–4)

Outcome **PASS / COMPLETED** (`adjudication.json`, `summary.json`): 6012 records scored and audited
(all-self-reporting), 6010 candidates replayed for pairs 0–4, findings and kills empty, measured rate
2630.433828050359 evals/h, epoch end `budget` at seq 6012, CRC drops 11 (SIGNREQ 1 / REC 5 / AUDIT 5),
bad frames 1, budget 650. Bound to the lifecycle-2 S3 manifest `aec84514…` (`manifest_at_run.json`),
under `rulings/b2_2026-09-16-01.json` + `rulings/p3_k_b2_2026-09-16-01.json` (archived here as
`ruling_*.json`), boundary `evidence/b2/principal_boundary_2026-09-16-02.json`.

## Layout

Ten ordinary files are what a reviewer reads. The five large exports — `audits.json`, `console.log`,
`console.ts.log`, `run_log.json`, `timeline.json` (~200 MiB together) — are in **`exports.tar.zst`**
(14,342,304 bytes, sha256 `607b362be8bd4c96d7a712a681eaea5c31e9d6586691f6f00ceb1db647f610ab`), a deterministic archive whose member sizes
and digests are listed in `archive.json`. `exports.json` (sealed by the runner) names the same five
files by size and sha256, so the seal is checkable after restore. `restore_rejudge.py` is the executable fresh-restore and re-judge (empty temp dir → the five members → the
ten ordinary files → exactly fifteen files, each checked by size and sha256 → production `judge_session`
with both instrument import paths); its result must equal `adjudication.json` key for key, and did at
archival and at the owner's review. The complete original directory (exactly the 15 original files) is kept read-only outside
the repository at `/home/test/fabricmap_backups/b2_17A6_2026-09-16-01` with a per-file hash list.

Nothing here authorises session 2, the primary adjudication, or any transition.

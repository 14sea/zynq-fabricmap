# B2 session 2 — lifecycle 2 — 17A6 — 2026-09-17-01 (pairs 5–8)

Outcome **PASS / COMPLETED** (`adjudication.json`, `summary.json`): 4810 records scored and audited
(all-self-reporting), 4808 candidates replayed for pairs 5–8, findings and kills empty, measured rate
2723.7861917937157 evals/h (span 6357 s within the 7776 s deadline), epoch end `budget` at seq 4810,
CRC drops 11 (SIGNREQ 1 / REC 5 / AUDIT 4 / unclassified 1), bad frames 2, budget 520. Bound to the
lifecycle-2 S3 manifest `aec84514…` (`manifest_at_run.json`), under `rulings/b2_2026-09-17-01.json` +
`rulings/p3_k_b2_2026-09-17-01.json` (archived here as `ruling_*.json`), boundary
`evidence/b2/principal_boundary_2026-09-17-01.json`. Session 1 (pairs 0–4) is
`evidence/b2/b2_17A6_2026-09-16-01/`; together the two sessions cover the nine preregistered pairs.

## Layout

Ten ordinary files are what a reviewer reads. The five large exports — `audits.json`, `console.log`,
`console.ts.log`, `run_log.json`, `timeline.json` (~160 MiB together) — are in **`exports.tar.zst`**
(11,479,719 bytes, sha256 `78f5bffda31a09b27e0527a04c83c43c07b2e5927a4b9df254d9e47f6f667b66`), a deterministic archive whose member sizes
and digests are listed in `archive.json`. `exports.json` (sealed by the runner) names the same five
files by size and sha256, so the seal is checkable after restore. `restore_rejudge.py` is the
executable fresh-restore and re-judge (empty temp dir → the five members → the ten ordinary files →
exactly fifteen files, each checked by size and sha256 → the pinned plan **and** prediction located
through the run manifest's plan pin and verified byte-for-byte before being read → production
`judge_session` with both instrument import paths); its result must equal `adjudication.json` key for
key, and did at archival. The complete original directory (exactly the 15 original files) is kept
read-only outside the repository at `/home/test/fabricmap_backups/b2_17A6_2026-09-17-01` with a per-file hash list.

Nothing here authorises the primary adjudication or any transition.

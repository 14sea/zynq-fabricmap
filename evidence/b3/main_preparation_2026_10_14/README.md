# B3 lifecycle 2 — main-experiment preparation: offline re-judge and form (c) archiving (2026-10-14)

The owner's ruling of 2026-10-14 on the main-batch scope draft: *first complete the offline re-judge and the
archiving preparation, then sign the first session's ruling; the eight sessions are not authorised as a batch.*
This directory is that preparation, done host-only on HEAD `a8275e8` (S3, manifest
`258bb14c4b3ba1a3d33741f23b1663f563de64da800843d30c8a615e2f128628`): no ruling was written, no port was opened,
no board was touched, nothing under `b3/` or in the manifests, pins or existing evidence changed. The ten rulings
are recorded in §4 as applied.

## 1. What is here

| file | sha256 | what |
|---|---|---|
| `restore_rejudge.py` | `e42a83ca5fa89d4a1f01a9ef925fbe62ffd52aaf98b409116cd28255a82df556` | the shared fresh-restore and production re-judge of ONE archived session (§2); the copy every session directory will carry must hash to this (archive.json records both digests) |
| `archive_session.py` | `03168a9fa7dae9f91f4d087769bf873b29eb57490f6c4b6a402843474bb7478d` | builds a form (c) archive from the runner's raw `--out` directory (§3); never modifies the raw directory |
| `test_main_preparation.py`, `test_main_preparation.txt` | — | the hermetic tests over SYNTHETIC sessions behind the fake seams of `b3/tests/test_b3_runner.py`: **23 / 23 OK** (own process) |
| `test_main_preparation_production.py`, `test_main_preparation_production.txt` | — | the PRODUCTION path over the real B3Q -02 archive: **1 / 1 OK, 147 s** (own process) |
| `production_path_b3q_02_result.json` | — | that run's result document: ACCEPT, re-judge PASS at 3180.049965139327 evals/h, zero keys differing from the committed `adjudication.json`, 88 pins verified, manifest `bb917ec7…` verified at S1, the boundary record through the production validator (age at finalisation 618 s) |
| `owner_review_0850e6b_reproduction_after_fix.txt` | — | the owner's three probes (`build/wip/b3_main_preparation_0850e6b_owner_review.py`, read-only) re-run on the follow-up: all three refused by name (§7) |

Neither script is an instrument. They live in evidence, read the tree, write only where told, and mutate copies only
in temporary directories. `restore_rejudge.py` exposes the same seams the runner does (`ports`, `authority`; `None`
is production) so the tests can inject fakes exactly as the pinned runner tests do.

## 2. The re-judge (`restore_rejudge.py`), step by step — every step fail-closed by name

1. **Restore.** `archive.json` (schema `b3_session_evidence_archive` 1.0.0) must list exactly the 5 members and the 11
   ordinary files; `exports.tar.zst` must size and hash to it; an EMPTY temporary directory; **the archive's table of
   contents is read BEFORE anything is written and must be exactly the five members by name, each a regular file — no
   duplicate, no directory, no hard or symbolic link, no path** (`list_tar`); then the five extracted (no owner, no
   permissions carried over) and checked to be regular files; the eleven copied, each refused if a link or if its
   name already exists in the restore directory; the restored set must be exactly the sixteen the runner writes;
   every file's size and sha256 equal to archive.json.
2. **Seal.** The production `b1_adjudicate.check_exports` over the restored files.
3. **Manifest, pins, pinned documents.** `manifest_at_run.json` must be a `b3_manifest`; its FILE digest is the
   binding every later check holds to; the archived whole-of-run ruling must bind that digest; the authority's
   `verify` (production: `b3_manifest.verify` with the production B3Q re-adjudicator — the lifecycle verify) and
   `verify_pins` (the tree's 88-file pinned surface equals the archived manifest's table, so the judge below is the
   pinned code) must pass; a SEARCH session's manifest must be qualified; the plan and prediction are located
   through the manifest's pin and verified byte-for-byte BEFORE being read (`b3_runner.pinned_documents`).
4. **Rulings.** Both archived rulings are decoded through the instrument's strict envelope reader (read, never
   claimed). The whole-of-run ruling is the AUTHORITY for the slice and the transport disposition.
5. **The session plan rebuilt from the authoritative inputs.** `search_session_plan` mirrors the production
   preflight's SEARCH construction (`b3/host/b3_runner.py`, `preflight`) field for field: the slice must be one the
   committed split gives; the record count from the frozen arithmetic; the deadline from the split's
   `rate_for_split` through the frozen formula (checked against the split entry, rel_tol 1e-9); frames, CRC /
   bad-frame and resend budgets from the bound instrument's `l6_schedule`; the identity-page flags; the binding
   (image, prereg, manifest file digest, instrument commit — which must equal the manifest's — map, fitness, carrier,
   universe, board, resend budget). A B3Q archive is rebuilt by the production `qualification_session_plan`.
   `summary.json["l6"]` and `run_log.json["l6"]` are then COMPARED to the rebuilt plan key for key; they are never the
   authority. (`test_main_preparation.ThePlanRebuild` holds `search_session_plan` equal to the real preflight's plan,
   key for key, on both slices of the fixture split.)
6. **The judge.** The production `b3_runner.judge_session` over the restored directory against the rebuilt plan;
   its verdict must equal the archived `adjudication.json` key for key; `runner_session.json` must satisfy the
   production `session_record_findings` against the rebuilt plan and THIS verdict, and its transport disposition
   must be the archived ruling's.
7. **The boundary record** named in archive.json: present, hashing as recorded, then through the PRODUCTION validator
   `b1_records.boundary_established` (the schema with its version, exactly the five named checks, runner ≠ signer,
   `all_passed` consistent with the checks, all passed) with the record's own timestamp as `now`; the recorded runner
   user; and the record must PRECEDE the session's finalisation (`runner_session.json`'s `at`), its age at
   finalisation reported. The six-hour freshness rule is the preflight's, enforced at run time; it is not re-judged
   offline against today's clock.

Exit 0 only on ACCEPT; 2 on a named refusal; 3 on an internal error. The result document records every step. The
temporary directory is removed (kept with `--keep`). Run from the repository root, or pass `--repo-root`.

## 3. The archive (`archive_session.py`) — form (c), as ruled

```
python3 -B evidence/b3/main_preparation_2026_10_14/archive_session.py \
    --raw <the runner's --out directory> --out evidence/b3/b3_17A6_<date>-NN \
    --boundary evidence/b3/principal_boundary_<date>-NN.json      # default --backup-root /home/test/fabricmap_backups
python3 -B evidence/b3/b3_17A6_<date>-NN/restore_rejudge.py        # the archive is evidence of a verdict only after this ACCEPTs
```

Refuses unless the raw directory holds EXACTLY the runner's sixteen files, its export seal holds, its finalisation
record names a B3 / B3Q session, the boundary record is a passed `principal_boundary`, and `--out` does not exist.
The external backup is refused if a backup of that name exists; its hash list is written beside the backup and
checked with `sha256sum -c` from inside it (the backup root is resolved to an absolute path at entry, so a relative
`--backup-root` works); the backup must hold exactly the sixteen files.
Then: the five large exports (`audits.json`, `console.log`, `console.ts.log`, `run_log.json`, `timeline.json`) into
one deterministic `exports.tar.zst` (GNU tar, posix format, sorted names, owner 0, one fixed mtime = the finalisation
record's `at`, pax headers without atime / ctime; zstd -19 — a second archive of the same directory is byte-identical,
tested); the eleven small files copied; `restore_rejudge.py` copied in (its digest and the preparation copy's both
recorded, with `equals_preparation_copy`); `archive.json` with every file's size and sha256, the boundary record's
path / digest / runner user, the archive's digest; the complete original directory copied read-only to the backup
root with a `SHA256SUMS` list, `sha256sum -c` passed. The raw directory is never modified. The B3Q -02 archive built
this way is 223 599 bytes for 4.3 MB of raw evidence; a 3 005-record main session (~100 MiB of exports) is expected
to compress to a few MB.

## 4. The owner's ten rulings of 2026-10-14, as applied here

1. **Final proof.** The accepted S3 proof node (`a8275e8`: the formal report archived as failed, the two supplements)
   serves as the engineering acceptance of preregistration §8's "final proof before any ruling pair". The formal
   clean-tree proof is NOT passed; no identical full run is repeated. Recorded in
   `docs/b3_s2_proof_exception_2026_10_14.md` (the added closing section).
2. **Re-runs.** Archived HOLD / LOST verdicts stand. Only a CONFIRMED transport or instrument loss may be re-run,
   separately authorised, for the same pair and seeds under a new ruling pair. A KILL stops the line; other HOLDs are
   not re-run automatically. (The runner never retries; `restore_rejudge.py` never edits a verdict.)
3. **Cross-session counting.** B3Q -01 counts once as "a contiguous inbound deletion causing a session HOLD"; -02's
   PASS does not reset it; the same loss again triggers the two-sessions-same-cause stop-loss. A different frame type
   or different finding text is not a new cause. COMPLETED is the epoch's end state; three claimed attempts without
   COMPLETED trigger the design review.
4. **Order.** Pairs 0 → 7. Sessions per day by the available window. The next ruling pair is signed only after the
   previous session is archived, re-judged (ACCEPT) and reviewed; the scope is not re-submitted each time.
5. **Archiving and re-judge.** Form (c): 5 large exports + 11 small files, the boundary record kept separately
   (`evidence/b3/principal_boundary_<date>-NN.json`, referenced and hashed in archive.json). The shared script and its
   verification are this directory; after review each session keeps the same script and its digest. The re-judge
   checks the complete file set, sizes / hashes, the seal, the manifest, the pins, both rulings, rebuilds the SEARCH
   session plan from the authoritative inputs (summary.l6 compared, never the authority) and ends with the pinned
   `judge_session` equal to the archived verdict field for field. Synthetic SEARCH positive case and the negative
   cases (tampered archive, binding, slice, deadline / budget) are in `test_main_preparation.py`.
6. **Transport disposition.** One bounded exception per session; the stop-loss stands. The resend budget (325 for a
   3 005-record session) is labelled honestly as the preflight's binding (it is checked against the ruling at
   preflight and recorded; nothing consumes it during the session); in-session, CRC and bad-frame counts are over
   budget only when they EXCEED 325. The heartbeat record budget is floor(SCORED records / 1000) over the records
   actually scored — 3 only for a complete 3 005-record session.
7. **Ruling text.** `whole-of-run B3 closed loop`, the pinned runner's text, unchanged.
8. **Result document.** The draft's requirements, plus every attempt listed, every re-run's reason, and the choice of
   pooled inputs. No HOLD pair is dropped to shrink N; the pooled primary takes each of the eight pairs' FIRST
   qualifying PASS; every failure stays archived and disclosed.
9. **Layered transport comparison.** Deferred. After a stop-loss trigger, the transport is dealt with before any re-run.
10. **Stale docstring** (`b3_runner.py:44-49`, "the authority modules do not exist yet"): recorded; fixed next lifecycle.

## 5. What this preparation does NOT establish

- **No SEARCH evidence that passes the production instrument layer exists on the host.** The repository has no
  B3 counterpart of `host/b2_modelled_session.py`; the host-app twin's notary is a stub (no audits); the pinned runner
  tests pass SEARCH evidence only behind a fake instrument layer with common validation off. The synthetic positive
  case here is exactly that: it proves the restore, the hashes, the seal, the plan rebuild, the comparison discipline
  and the refusals — not the instrument layer on SEARCH frames. The production path is proved on the real B3Q -02
  archive (same files, same judge, B3Q plan builder). **The first board session's re-judge will be the first
  production SEARCH run of this script**, as B2's first session was for its script. Writing a `b3_modelled_session`
  is a separate unit, if the owner wants one before session 0.
- The re-judge is one session's; the pooled primary is `b3_adjudicate --scope run` over the eight restored logs,
  not this script.
- Nothing here authorises a ruling, a session or a push.

## 6. Numbers for session 0..7 (from the committed plan `b202a280…`, reproduced through the pinned instrument)

3 005 records (2 baselines + 3 × 1 000 + 3); expected frames 81 138 (IDENT 1, CLOSE 1, TERM 1, SIGNREQ 3 005,
REC 3 005, AUDIT_READY 3 005, AUDIT 24 040, HB 48 080); CRC = bad-frame = resend budget 325; deadline
5 602.696090881941 s from `go`; expected span 4 002.156872705553 s at `rate_for_split` 2 703.042470368428.

## 7. Follow-up to the owner's review of `0850e6b` (2026-10-14; three P1s, all reproduced by the owner)

| P1 | defect in `0850e6b` | fix (this follow-up) | test |
|---|---|---|---|
| the default backup failed | `archive_session.backup` ran `sha256sum -c` on the list's bare name from inside the backup directory, but the list lives beside it → "No such file or directory" on every backed-up archive | the list's absolute path; the backup must hold exactly 16 files; the same backup name is refused | `TheArchiver.test_the_backup_round_trip`: backup enabled, 16 read-only files equal to the raw ones, 16-line hash list, `sha256sum -c` passes, re-judge ACCEPT, the same name refused |
| the restore could write outside its directory | the archive was extracted before its contents were checked; a planted symlink member named `summary.json` was followed by the later copy and overwrote a file outside the restore directory, and the restore still accepted | `list_tar` BEFORE extraction: exactly the five members, regular files only, no links / directories / duplicates / paths; after extraction every entry must be a regular file; ordinary files are refused if a link or if the name already exists | `TheRoundTrip.test_a_planted_link_member_is_refused_before_anything_is_written`: symlink, hard link, directory, extra regular member, duplicate, `../` path — each refused by name with the restore directory still empty and the external marker unchanged |
| an invalid boundary record was accepted | only the schema name and `all_passed` were looked at; a record without `schema_version`, with empty checks and runner = signer, which the production validator rejects, was accepted | the production `b1_records.boundary_established` (structure, the five checks, runner ≠ signer, consistency, all passed) with the record's own timestamp as `now`; order against the finalisation; age reported; the 6 h rule stays the preflight's | `TheRoundTrip.test_an_invalid_boundary_record_is_refused_by_the_production_validator`: the owner's record, an inconsistent `all_passed`, a failed check, runner = signer, four checks, no `schema_version`, a record later than the finalisation — each refused; a month-old but valid record ACCEPTs offline |

The owner's reproduction script, re-run on the follow-up: all three probes refused
(`owner_review_0850e6b_reproduction_after_fix.txt`). Both test modules re-run in their own processes (22 / 22;
1 / 1 production over the real B3Q -02 archive, 146 s); the scripts' digests in §1 are the follow-up's. `0850e6b`
is kept as committed; this is a separate commit.

## 8. Follow-up to the owner's review of `0a86d00` (2026-10-14; one P2)

| P2 | defect in `0a86d00` | fix | test |
|---|---|---|---|
| a relative backup root still failed | `backup()` passed `str(sums)` to `sha256sum -c` run from inside the backup; with a legal relative `--backup-root` (`backups`) the list's path was relative to the working directory, not to the backup → "No such file or directory" even on a complete 16-file backup | `backup_root` is resolved to an absolute path at the function's entry, so the backup, the hash list and the check all use absolute paths | `TheArchiver.test_the_backup_round_trip_with_a_relative_backup_root`: a relative root under a changed working directory — 16 files equal to the raw ones, absolute recorded paths, `sha256sum -c` passes from inside the backup, re-judge ACCEPT |

The hermetic module re-run in its own process: 23 / 23. The production path and the full proof were not re-run
(the owner's ruling: not needed for this narrow fix; `restore_rejudge.py` is unchanged — its digest in §1 stands).
`0850e6b` and `0a86d00` are kept as committed; this is a separate commit.

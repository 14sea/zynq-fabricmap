# The complete offline B2Q lifecycle — the positive control, 2026-09-11

`host/b2_modelled_session.py` drives a whole B2Q session through the instrument's real host stack
and the **production exporter**, the runner's own verdict judges it, and the lifecycle carries it
S1 → B2Q → S2 → S3 and verifies it again **in a fresh process**. This is the acceptance the owner
has required through five review rounds: the checks this batch added can be SATISFIED, not only
failed, and **no replay double and no stored-verdict double appears anywhere on the positive
path** — `b2_manifest.qualify` and `verify` are handed the REAL `b2_runner.readjudicator`, which
re-runs the whole composed verdict over the evidence files.

`lifecycle.json` is the run.

| stage | result |
|---|---|
| the modelled session | `COMPLETED`, **20 records** (the preregistration's 1 pair at budget 8), every export `ok`, **two forced-control CRC drops** (the seq-1 SIGNREQ and REC controls, which the session arms deliberately), **zero non-control CRC drops, zero bad frames** |
| the runner's verdict | **PASS**, zero findings, zero kills, `binding_checked: true`, session `B2Q` |
| the measured rate | **4490.86 /h**, from the session's own timing — recomputed, never echoed |
| the audit policy | `all-self-reporting`, verified by the instrument's own check |
| S2 `qualify` | **qualified**, calibration derived from that rate under the split rule: 2 sessions, 7 pairs/session max; the record pins all **11** evidence files at schema **1.2.0** |
| S3 `pin_plan` | the plan regenerated from the calibration and pinned |
| fresh-process `verify` | **rc 0**, stage `S3`, qualified, board `17A6`, the B1 chain re-verified, the image binary opened, sized and hashed |

## What the session actually exercises

The board twin is the instrument's own rel-v4 soak board with B2's substitutions: the candidates
come from the reference orchestrator `b2_session.run` (driven with B2Q's OWN pair seeds, which the
orchestrator now accepts explicitly — B2Q's seed rule is not B2's), the records are loop_record
1.3.0 with the `search` block and the arm, the IDENT is app_identity 1.5.0 built from
`expected_identity` — so the online identity check the console runs and the offline binding check
the verdict runs are the same contract — and the audit pull serves each candidate's REAL staging
streams and readback frames, so the instrument's audit gate recomputes every hash. The host side
is the instrument's ConsoleSession / NotaryRelay / Collector / reader / timeline, and the evidence
is written by `b1_session.export_evidence`, the production exporter.

## Eleven negatives ON TOP of that PASS

`tests/test_b2_e2e.py` mutates the passing evidence one thing at a time and requires each to be
refused: a relabelled epoch, a short epoch, a record no longer audited, a broken export seal, a
changed `l6.binding`, a wrong IDENT carrier digest, a deadline the session exceeds, a tampered
readout (a **KILL**), an archived ruling naming another board, a tampered calibration and a
changed evidence file through the lifecycle — **eleven**, alongside **three** positive tests.
Each starts from the real PASS, so none of them can be passing for a reason unrelated to what it
claims to test.

## What this is NOT

**The model stands in for a board.** This is not silicon evidence, not a session, and not a
qualification. The rulings are inert modelled documents that authorise nothing and are never
consumed. No board was contacted and none is authorised. The B2 (map-utility) profile is not
driven from this entry point: at budget 600 even a two-pair slice is 2 406 records and a four-pair
slice 4 810, which belongs in a one-off demonstration rather than the suite. Those figures are
slice arithmetic, not this demonstration's split — the calibration measured here gives 2 sessions
at up to 7 pairs each.

14 end-to-end tests; the B2/B3 suite is **395, zero skips**.

# B2 modelled session integration review — 2026-09-12

Reviewed HEAD: `9035b188959ca5b14325cc7563fc67520e18f21c`, implementation
`c006de8`, sixteen commits ahead of `origin/main` (`0d294ea`).

**The missing offline positive integration blocker is CLOSED for the demonstrated
B2Q lifecycle and a representative B2 session.** No new P2 was reproduced in this
review. The documentation/entry-point P3 items below remain to be corrected; the
complete runner package still awaits its missing tools and final review.

## Verified B2Q integration

The previously missing positive B2Q lifecycle is demonstrated. An independent invocation
uses a temporary S1 fixture produced by the real manifest initializer and freeze function,
the modelled board, the instrument's real host stack and production exporter, and the
runner's real `adjudication_for` callback. It produces PASS with 20 scored/audited records,
zero findings and zero kills. There is no replay or stored-verdict double in this path.

Real `qualify`, `pin_plan`, and fresh-process `verify` accept S2, S3, and qualified S3
respectively. The modelled measured rate is 4490.856163729762 records/hour under the
instrument's rate definition. The calibration generates a 7+2 split: 8,416 and 2,406
records, 10,822 including four session brackets. These are model timings, not board
performance measurements or a real qualification.

The focused suite independently passed: **395 tests, zero skips, OK in 383.052 seconds**.
This is a focused suite result, not a full-repository clean-tree report.

## Independent B2 session demonstration

The same genuinely re-adjudicated S3 fixture was passed to the production B2 preflight.
Only three boundaries were doubled: the not-yet-implemented `b2_pins` hook, principal
boundary establishment, and `sb` discovery. Manifest verification, image/build input
verification, instrument binding, B1 qualification-chain verification, plan/prediction,
slice selection, and test-ruling bindings were real. No preflight double supplied a
replay, session verdict, calibration, or qualification result.

The final planned slice, **pairs 7 and 8 at budget 600**, was then driven through
`run_modelled` and judged by the actual **`adjudication_for(cfg)`** callback:

| Check | Result |
|---|---|
| Epoch | COMPLETED / budget, last seq 2,406 |
| Scored / audited | 2,406 / 2,406; nonce chain length 2,407 |
| Replay | 2,404 search/holdout records, absolute pairs `[7, 8]` |
| Verdict | PASS; zero findings, zero kills; binding checked |
| Exports | All seven statuses `ok` |
| Transport | Two forced-control CRC drops; zero other CRC drops; zero bad frames |
| Modelled span / authorized deadline | 2,059.849 s / 3,010.899 s |
| Pooled primary | Absent, as required for session scope |

This exercises a nonzero slice offset and both odd/even pair arm orders. It closes
the missing representative B2 profile demonstration; it is not a complete nine-pair
instrument-stack experiment or a new pooled-primary result. The model's B2 CLI remains
unsupported; this demonstration uses the API and the runner-generated invocation.

## Production finalization ordering

A separate independent probe supplies the actual model Collector, ConsoleSession,
NotaryRelay, Timeline and reader to **`b1_session.finalize`**, with the real runner callback.
The export seal exists when the callback executes; `summary.json` does not yet exist.
The verdict is PASS. After the production `persist_summary` writes the final summary,
real `b2_manifest.qualify` accepts the evidence with the real readjudicator.

This verifies the ordering that the package's model-specific `finalize` helper alone
could not establish. It does not execute the live `b1_session.run` preamble or
`b2_runner.execute`, provision a key, open a serial port, or consume an authorization.

## P3 documentation and entry-point corrections

1. `evidence/b2/b2q_modelled_lifecycle_2026_09_11/README.md:15` says zero CRC drops.
   Its own `lifecycle.json` records **two**, as do both independent model runs. These
   are the seq-1 SIGNREQ and REC forced controls. Use "two forced-control CRC drops,
   zero non-control CRC drops, zero bad frames." Do not rewrite the recorded result.
2. That README's "Ten negatives" and the package banner should say **eleven**.
   There are three positive tests and eleven negative tests, fourteen in total.
   The 4,810-record example is a four-pair slice; it is not the split produced by
   this demonstration's calibration.
3. `host/b2_modelled_session.py:330` says `run_modelled` judges and finalizes, but it
   returns after export and artifact creation. Its CLI likewise exits zero with a
   COMPLETED model epoch while leaving **no `adjudication.json`, no `summary.json`,
   and no verdict in stdout**. The acceptance tests explicitly call the real judge
   and the separate finalization helper, which is why their lifecycle succeeds.
   Document that caller obligation and the actual B2Q-only CLI, or implement the
   advertised orchestration. The module's example advertises unsupported pair-slice
   CLI options. `host/b2_session.py` also still says pair seeds are not an input,
   although this batch introduces an explicit seed override for B2Q.

These discrepancies do not invalidate the demonstrated API-level positive lifecycle.
They should be corrected before describing the CLI itself as a complete judged run.

## Preserved inputs and limits

Live build evidence verification returns zero findings. All **105 B1 pins** verify.
The following bytes remain unchanged:

| Artifact | SHA-256 |
|---|---|
| B2 image, 114,708 bytes | `d164cd1d5b30aa5eb91f230b1373be8dda60d219249924e280957b26348d85f5` |
| B2 ELF | `7de96ed25e01199ad4405dcc59b2ec92140c27679710e6acfbbad158e4986cdc` |
| B1 manifest | `38238271510536bda565ad1b8321dd04d75e78e1fe77ef94d2795bf9edfd4ba8` |

The instrument remains clean at `689dde1dad374536c625bbe2b05986ee89eb4c94`.
Modelled board output is derived from Python reference code; this batch does not
execute `b2_app.c` or establish silicon behavior, serial-path reliability, or measured
board throughput. Existing C twin/harness evidence remains a separate layer.

Missing `b2_pins` still makes production preflight refuse. `b2_test_report`, the
complete package review, and the qualification-document/planning-rule freeze remain
outstanding. No push, production freeze, ruling, or board clearance follows from this
offline review. Continue with the remaining host tools.

Artifacts: [review scripts, outputs and compressed modelled transcripts](../evidence/b2/review_modelled_integration_2026_09_12/).
The compressed transcripts retain the generated bytes; manifests refer to temporary
fixture paths. The scripts rebuild the lifecycle when repeatable verification is needed.
No original session evidence, production code, firmware, image, manifest, real ruling,
or instrument file was changed. Only English review artifacts and the package status
banner were written. No commit, push, ARM rebuild or board action was performed.

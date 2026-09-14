# Native-Linux transport acquisition archive review — 2026-09-14

**PASS for local archive consistency and preservation.** Claude may push the
five local commits through `7815c8a`, under the scope below. The board consistency
control remains on HOLD with the four P2s in
`docs/b1q_board_consistency_review_2026_09_13.md`; this archive decision does not
accept that implementation, authorize its use or release the transport stop-loss.

## What was independently checked

The review regenerated every native acquisition's source frames from its run_id
and repetition, using the recorded tool version's unchanged generator. It did
not use the stored loss count as the expected byte stream. The check verified:

- All **125 captures**: byte length and SHA-256 against run.json, plus received
  byte totals against the per-read event counts.
- Accepted source-write indices, frame kinds and lengths against regenerated
  frames; host write counts, sizes and causes against the generated schedule.
- Every accounted host echo against an exact generated line, with multiplicity.
  After echo removal, every source line was compared in order to its generated
  frame, including the shortened final no-TX repetition.
- All five damaged source lines are single contiguous deletions. All other
  source lines match exactly, and each damaged line's successor matches exactly.
- Per-repetition and aggregate accepted/delivered/loss counts, denominators,
  preflight nonce/raw digest, entry/run agreement and export/close state.
- The native tool and framing-module digests match the locally available files.

| native acquisition | captures | accepted / delivered source frames | received bytes | confirmed losses | exact host echoes |
|---|---:|---:|---:|---:|---:|
| notx | 101 | 30,372 / 30,368 | 9,907,831 | 4 | 0 |
| rehearsal_notx | 2 | 604 / 604 | 197,198 | 0 | 0 |
| rehearsal_tx | 2 | 604 / 604 | 225,776 | 0 | 250 |
| tx | 20 | 6,040 / 6,039 | 2,257,759 | 1 | 2,500 |

The reproduced deletion locations match the submitted table: notx repetitions
36, 41, 72 and 86, frame indices 253, 299, 199 and 64, respectively; tx
repetition 0, frame index 145. All are REC frames. The first deletes `G4`
(two bytes); the other four delete one byte each. Full observations and exact
hashes are in `evidence/b1q/review_native_archive_2026_09_14/results.json`.

## Comparison limits

WSL used tool digest `aaff46e9…`; native Linux used `e2af873d…`. They are not
identical tool binaries. AST comparison confirms unchanged definitions for
Frame, token_for, plan_frames, host_frame, host_schedule, Driver, analyse and Run;
the reviewed changes concern the device entry point and finalization. This
supports comparing the archived byte-delivery observations while retaining
both tool versions explicitly in provenance.

Host topology, same physical adapter/wiring, root-port connection, package
preparation and absence of board power are operator-reported conditions. This
review did not remotely inspect Orange Pi, independently verify its source
copies, or open any device. The archived invocation confirms the USB VID:PID and
local node metadata; it does not independently prove the complete USB topology
or uniquely identify a serial-less physical adapter.

Under the reported native setup, byte deletions are observed without WSL or
USB/IP. That rules out their being necessary for this observed deletion class;
it does not identify the cause of these or the original B1Q losses. The TX
conditions have **equal observed event counts**, not established equal fault
rates. Small counts and differing exposures do not establish stability or a
component-level causal result. The two driver-counter failures remain
unavailable measurements, not zero overruns.

The reported native 161/162 test result is retained as reported, including the
missing-artifact gate failure. It is not a clean-tree proof. Locally, production
B2 verify still accepts S1, qualified false, refusal null, with 71 B2 / 105 B1
pins and manifest
`8699767744b8f7c1f68a49252acddd91af0e9d1732a0a772476fc0f257949b35`.
No software test suite was rerun for this evidence-only review.

## Exact push and retention disposition

Claude may push these five commits as historical work and evidence, with the
unresolved software HOLD preserved:

- `1986bd4`: initial board-control preparation;
- `2c2cd0f`: first board-control review;
- `fd89516`: narrowed consistency implementation, still subject to four P2s;
- `918de3f`: four-P2 review retained verbatim;
- `7815c8a`: native-Linux acquisitions and observations.

This is explicit archival push permission despite the unresolved implementation
findings; it does not supersede their acceptance criteria. Keep the records in
place and do not rewrite history. This review document and
`evidence/b1q/review_native_archive_2026_09_14/` may be included as one additional
review/evidence commit in the push; report six rather than five if included.

Retain the Orange Pi evidence copies and both clones for subsequent comparison
and provenance checks. No deletion or remote operation was performed here.
The next software task remains the four P2 fixes; any further physical
comparison or B2Q remains a separate decision and is not authorized here.

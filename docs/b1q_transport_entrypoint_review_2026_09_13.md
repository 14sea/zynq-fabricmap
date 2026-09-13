# Transport device entry-point review — 2026-09-13

Disposition: **HOLD for the device entry point: three P2 findings.**
This review does not release push of the submitted change as accepted software.
The previously accepted analyser/driver scope is unchanged. S1 remains frozen;
this review neither lifts the transport stop-loss nor authorizes B2Q.

The submitted change is `819117c`. During review, HEAD advanced to `d406f1c`
through procedure and physical-evidence commits. The reviewed Python implementation
and its tests are identical to `819117c`; their diff from that commit is empty.
No physical port was opened by this review. Existing physical captures were not
modified or adjudicated. The new physical runs require their own evidence review.

Reproducer: `evidence/b1q/review_transport_entrypoint_2026_09_13/probe_entrypoint.py`.
Its `results.json` records the actual reviewed HEAD and tool SHA-256. All ports,
identities and counter observations in these probes are doubles. Temporary output
directories are used; no previously archived evidence is passed to the CLI.

## P2-1 — preflight has no absolute drain deadline

`host/transport_rig.py:1279–1284`: every nonempty read resets `quiet_since`.
The one-second deadline constrains the initial nonce read only. A stream that
continues to produce bytes keeps the subsequent loop alive indefinitely, before
`Run.execute` starts its registered exposure clock. Memory also grows with every
read. The tool-error and exposure stops in `Run` cannot govern this loop.

The continuous-input probe advances a virtual clock by each requested read timeout.
At 3.05 seconds the **probe's** watchdog raises; production has not terminated.
Only `invocation.json` exists. This is a bounded demonstration of the missing
production bound, not a claim about measured wall time on a UART.

Required correction: bound the entire preflight, including write, nonce reception
and quiet drain, by an absolute deadline. Cap every operation by the remaining
budget. Failure to achieve quiet must produce a named refusal/error and preserve
the observed bytes; it must not begin exposure with an unbounded backlog. Test
continuous data, delayed nonce, and expiry during drain against a clean control.

## P2-2 — preflight exceptions bypass the evidence and exit contract

`host/transport_rig.py:1273–1288,1323–1337`: preflight is outside the guarded
`Run.execute` path. A write/read/counter exception escapes before `preflight.json`
is written. The after-counter is not independently attempted. The command exits
through a traceback rather than its declared tool-state result.

The detach probe first receives the complete nonce, then raises `OSError` on the
next read. Production leaves only `invocation.json`, takes one counter sample,
and loses the received nonce and terminal preflight diagnosis. No later frame is
written, but the acquisition evidence is missing. Successful preflight also only
stores a 64-byte receive prefix rather than the complete observation.

Required correction: give preflight its own guarded acquisition/finalization
boundary. Preserve the actual sent nonce, partial raw receive bytes, timing,
primary error, and independent before/after counter attempts on success and
failure. Export components independently; a secondary write failure must not
replace the primary transport exception. Include invocation/open/preflight export
failures in the entry-point error contract, and close all successfully opened
ports on every return path. Test faults after some bytes have already arrived,
plus write, read and finalization faults, from the real CLI entry point.

## P2-3 — reusing --out overwrites an earlier acquisition

`host/transport_rig.py:1302–1313` accepts an existing directory and overwrites its
invocation before the port opens. The production exporter then replaces captures,
events and summary with the same names. Files beyond the new run's repetition
count remain. A mistyped rerun therefore creates a mixture of two acquisitions
and destroys the earlier bytes.

A temporary directory containing old invocation, summary and two captures was
passed to the real CLI with a clean one-repetition fake port. It returned exit 0,
`completed_exposure=true`, `export_complete=true`; the invocation, summary and
capture 000 were replaced, while old capture 001 remained.

Required correction: claim a fresh output directory before any port opens or
byte is written. Refuse a nonempty existing destination without changing any of
its bytes; avoid a race between checking and claiming a destination. A retry
needs a new destination. Do not repair this by deleting old files. Test that the
old tree is byte-identical and that the device opener was not called on refusal.

## P3 — distinguish recorded identity and attempted counters from guarantees

The source USB identity is best-effort metadata, not a preflight gate. The probe
supplying `0403:6001` runs 302 frames and returns exit 0. This is consistent with a
generic diagnostic tool, but does not establish the procedure's stated CH340
condition. State explicitly where `1a86:7523` is enforced for that condition:
either add an explicit expected-identity check before opening, or make the
operator's identity check a mandatory documented prerequisite. Do not describe
metadata collection as device acceptance. Missing identity must stay unavailable.

Likewise, change the procedure's assertion that counters "are available" on a
real tty to "are attempted on the real fd; availability and failure reason are
recorded." `read_icounters` itself correctly supports an unavailable result.
A real fd alone does not establish a successful ioctl or usable counters.

## Validation and limits

- Existing transport suite: **111 tests, zero skips, OK**, 66.978 seconds.
- B1 pins, B2 pins and B2 gate suites: **3 + 6 + 28 = 37 tests, OK**,
  zero skips. These are focused checks, not a new whole-suite clean-tree proof.
- Independent clean-loopback control: exit 0, 302 accepted frames, zero losses,
  complete exposure and export. Silent preflight: exit 3, one nonce write,
  both counter attempts, no exposure run.
- Three P2 probes reproduce as described. Wrong-USB probe establishes the
  metadata-only behavior. A zero-repetition observation is also retained: exit 0
  but `completed_exposure=false`; it is **not** counted as a false acceptance.
- Production B2 verify accepts **S1**, `qualified=false`, `refusal=null`;
  **71 B2 / 105 B1 pins**. Manifest remains
  `8699767744b8f7c1f68a49252acddd91af0e9d1732a0a772476fc0f257949b35`.
  Pin table and frozen preregistration digests remain unchanged.

Do not rewrite existing physical captures in response to these findings. Fix and
retest the entry point, then identify the exact software version used by any new
acquisition. This review adds only English review documents and offline probes;
it changes no production code, frozen input, image, instrument or ruling.

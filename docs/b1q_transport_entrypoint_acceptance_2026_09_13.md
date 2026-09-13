# Transport entry-point acceptance — 2026-09-13

**PASS within the reviewed offline software scope.** The second review's P2 and
P3 are closed. No additional blocking finding was reproduced in this review.
This is not a transport-stability verdict, a stop-loss release or a B2Q ruling.

Reviewed fix: `c2f38ab`; observed fabricmap HEAD: `3539baf`.
Tool SHA-256:
`e2af873d521b340d2f42d1c9248e2a28f9669687b2d24c762638dd05a5543478`.

## Independent validation

The production transport suite passed **130 tests, zero skips, OK**, 71.391 s.
The independent acceptance script drives production CLI behavior with fake ports
and fresh temporary directories. No real port is opened. Its nine cases verify:

- A clean 302-frame acquisition remains complete with zero losses.
- Silence refuses; continuous input reaches the absolute 3.0-second preflight
  bound; detach preserves the received nonce and both counter attempts.
- A provenance construction error returns exit 2, with no opened ports, zero
  writes, no run.json, and a durable invocation diagnostic.
- A failed close appears only in close_attempted, not ports_closed; the error is
  archived without altering the 302 accepted frames and zero observed losses.
- Nonempty destinations retain their bytes and get no new entry file or port
  writes. A wrong explicit expected USB identity refuses before opening.
- On writable destinations, entry.json equals the emitted stdout object.
  If entry.json itself cannot be written, stdout explicitly reports the missing
  record and export_complete false; acquisition data survives. That path is
  not a complete archived entry and must not be treated as one merely because
  the run's exit code remains 0.

The last point is a limit of the documented tool-state interface, not a hidden
acceptance: consumers must inspect entry/export/close status, not exit 0 alone.

Production B2 verify rechecked image bytes, B1 chain and 71 B2 / 105 B1 pins and
accepted S1, qualified false, refusal null. Its manifest remains
`8699767744b8f7c1f68a49252acddd91af0e9d1732a0a772476fc0f257949b35`.
The instrument remains clean at `689dde1`. The previous 37-test pin/gate result
was not rerun in this review; live production pin verification was rerun. This
is not a new whole-suite clean-tree proof.

## Push disposition

Claude may push the **12 fabricmap commits** currently above origin/main,
`eba9260` through **`3539baf`**, including the original acquisitions as historical
records and the reviewed software corrections. Push does not upgrade those
acquisitions to a stability proof or re-label their software version.

Claude may independently push the **two xilinx documentation commits**,
**`20760a6` and `fb20e7f`**. The final wording correctly distinguishes observed
reset-time dropout from the unsupported board-3.3-V attribution.

This acceptance document and
`evidence/b1q/transport_entrypoint_acceptance_2026_09_13/` may be archived in one
additional documentation/evidence commit and pushed with the fabricmap batch.
Report that extra commit separately; do not call the resulting batch twelve.
No unrelated edits, force-push, board operation or ruling are included.

## Existing physical acquisitions and the next transport step

For archival consistency, all **127 captures** across the four physical
acquisitions were checked against their recorded sizes and SHA-256 digests.
Each invocation's tool digest matches the committed `819117c` implementation,
`aaff46e9…`; they were not produced by the newly accepted implementation.
This check is not a fresh full replay or physical acceptance adjudication.

Keep the TX observation of one confirmed source-frame loss over 2,257,741
received bytes, with damaged host echo recorded separately. It is an empirical
ratio from a declared 20-repetition exposure, not an established failure rate.
Existing protocol recovery can restore a logical record without erasing that
transport observation; no new retry implementation is required merely to use
rel-v4's existing mechanisms.

Preferred next direction: **the native-Linux comparison in the existing option-B
plan**, holding adapter, wiring, baud, traffic and exposure definitions fixed.
Prepare that comparison and its provenance on the host first. Do not infer a
root cause or justify B2Q by a later clean run. This acceptance authorizes no
new physical acquisition or board session; stop-loss remains in force.

A factual correction to the latest handoff: LOST and PROTOCOL_CRC_BUDGET are not
mutually exclusive. The archived summaries of B1Q attempts 1 and 3 both contain
PROTOCOL epoch ends, respectively `3 > 2` and `5 > 4`; LOST describes their
experimental disposition. Attempt 1 additionally suffered the host finalizer
exception. Preserve both the classification and the observed termination cause.

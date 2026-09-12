# Transport driver correction review — 2026-09-12

Reviewed HEAD: `146e60a`, initially clean, three commits ahead of origin/main.

**HOLD: do not push this as an accepted software delivery yet.** The submitted
acceptance passes, as do all **49 tests, zero skips** (75.243 s). Those controls
establish several corrections, but do not cover the remaining cases below.
No serial device, board, ruling, production freeze, image build or pinned input
was changed or used for an experiment in this review.

Evidence and executable probes:
[review directory](../evidence/b1q/review_transport_driver_2026_09_12/README.md).

## What is accepted from this batch

- On a fully transmitted repetition, the original CRC/missing double-count is
  removed. The submitted one/two/three affected-frame controls pass, including
  the inserted-newline and valid-CRC payload mutation examples.
- The known-index payload alteration is no longer credited, and a capture from
  repetition 0 is rejected against repetition 1's token. Short and unreported
  writes are rejected in the existing controls.
- The ordinary detach path attempts counters on both sides and exports raw bytes
  when all finalization operations succeed. It is a substantial improvement over
  returning no evidence, but the summary and secondary-error paths remain wrong.
- The exposure-unit argument is withdrawn correctly: 20 records and 543 planned
  B2Q frames cannot be compared as "20 versus 302 frames."
- The next-newline field is now named accurately, with a separate verified-frame
  resynchronisation field. The original inserted-newline P3 control passes.
- Scope now correctly distinguishes software PTY acceptance from the pending
  physical stage-1 acceptance. The transport stop-loss remains in force.

## P2-1 — Byte-exact delivery and echo accounting still accept unsent bytes

`host/transport_rig.py:345–405, 416–420, 457–467`.

The parser splits on newline, then reconstructs `ln + b'\n'` even for the final
unterminated segment. Remove just the final TERM newline: **302 delivered,
zero losses**, although only 98,598 of 98,599 bytes arrived. The overall
`clean` flag remains false through the divergence check; the delivery/loss
accounting nevertheless violates the new byte-exact unit.

Echo handling adds a stronger false-clean case. Supply exactly one expected
IDENTACK echo, then append that echo **100 times**: `host_echo_lines: 100`,
zero defects, `clean: true`. Alternatively append 100 unsent blank lines and
one valid echo: also `clean: true`. Echo membership is a set with no count
bound; blank lines are ignored; `_without_echo` discards any nonmatching whole
line rather than just the authorized echo occurrences. Merely having an echo
activates a normalization that can hide additional bytes.

Only complete actually received lines may receive delivery credit. Retain an
unterminated suffix as a fragment, including a missing newline on an otherwise
valid frame. Consume echoes against an explicit successful-write ledger with
multiplicity and a declared topology; do not permit unlimited occurrences or
drop arbitrary lines. Run.execute currently supplies the host echo list even
for a topology not declared to echo, and appends entries before write success.
Normalize only the exact accounted echo occurrences, preserving raw offsets and
all other bytes as diagnostics. Keep the measured total-byte denominator and
direction/echo byte counts separately available for comparison.

Required controls: complete stream, one legitimate echo, missing final newline,
extra echo copies, inserted blank lines with/without an echo, unexpected echo
on a non-echo topology, and a failed host write followed by apparent echo bytes.

## P2-2 — Partial repetitions report planned traffic as sent, or omit it entirely

`host/transport_rig.py:625–639, 657–677`.

Deadline path: the probe successfully writes and reads one IDENT (1,048 bytes).
It stops before the second source frame. Analysis still receives all 302 planned
frames and reports **302 frames sent, 98,599 bytes sent, 301 losses**. These are
untransmitted frames, not observed transport losses.

Exception path: after the same one successful IDENT, the next read raises.
`capture_000.bin` correctly contains **1,048 bytes**, but the persisted summary
reports **frames_sent: 0, bytes_sent: 0, denominator_bytes: 0, losses: 0**. The
partial repetition is appended to `captures` but skipped by `analyse` and
`results`; `_summarise` only aggregates the latter.

Track planned, attempted, completely accepted and partially/uncertainly written
traffic separately. Analyze every partial capture against the applicable write
ledger in a guarded finalization step. Never count unattempted frames as losses;
do not invent a definitive loss for bytes still in flight at a cutoff. Preserve
incomplete/censored status where needed, and include all received capture bytes
in the declared aggregate denominator. The original stop reason must remain
distinct from transport loss. A zero-loss incomplete run is not a completed
exposure. Test deadline, partial write and detach before/after specific complete
frames, asserting both raw files and exact summary accounting.

## P2-3 — Deadline checks still permit writes after expiry and unbounded writes

`host/transport_rig.py:549–578, 706–713`.

Use a 0.01 s deadline and a cooperative reader that consumes exactly its requested
timeout. The driver asks it to wait **0.05 s**, then starts a host write at
**t = 0.05**, already after expiry, sleeps another 0.065 s, and returns at
**0.115 s**. This is not merely a gap that began before the deadline: a new write
is initiated after the capture operation has exhausted the budget.

`_drain` does not cap its timeout by the remaining duration, and there is no
expiry check between `_drain` and the host write. Source writes and sleeps also
have no remaining-budget parameter. The actual `serial_port` constructor passes
no `write_timeout`; the locally installed pyserial signature defaults it to
`None`. Post-operation checks cannot bound a blocked write. The probe inspects
construction with a serial double; no real serial connection is opened.

Make remaining time part of the transport contract, cap read/write waits and
scheduled sleeps, check expiry before every new source or host write, and record
any unavoidable bounded overrun explicitly. Test expiry in source write, read,
pace and host-send scheduling separately. The existing test only advances time
in the inter-frame sleep and cannot establish these guarantees.

## P2-4 — The TX condition does not yet establish the required overlap or traffic shape

`host/transport_rig.py:314–325, 565–578`.

Writes are now interleaved with reads, but that does not establish host TX while
source traffic is being received. The driver writes a source frame, optionally
sleeps for its entire wire time, drains it, then sends the host command and waits
before scheduling the next source frame. In a deterministic paced transport
model, all **125 host writes occur after the source transmission has finished**:
zero overlapping writes. This is a model observation, not a measurement of a
physical UART. It demonstrates that the allowed implementation can satisfy every
current test without exercising the independent variable in A1/B1.

The host traffic is also plain `COMMAND seq\n` (**9–14 bytes**), not rel-v4
framing with a session-shaped length/payload distribution. Matching 125 command
labels cannot establish TX wire occupancy. The archived schedule itself shows
the changed composition: it has 11 SIGNOK, 11 RECACK, SIGNGET and RECGET; the rig
has 12 SIGNOK and 12 RECACK. Removing forced CRC controls is an accepted declared
difference, but the corresponding traffic substitution and timing must be
quantified, not represented as reproduction solely because the totals match.

Use an independently scheduled source, capture and host sender with declared
timing semantics. Add a timing-aware offline positive control that verifies
nonzero intended TX/RX overlap and the appropriate source occupancy/gaps, plus
the no-TX negative control. Generate a justified host byte-length/burst profile;
record actual scheduling timestamps and achieved gaps/overlap separately from
targets. Record pace/read-timeout/baud and schedule inputs in run parameters.
The current PTY tests disable sleeping and cannot validate the pacing contract.
No physical experiment is requested to resolve this software acceptance gap.

## P2-5 — Finalization can still lose the summary and replace the primary error

`host/transport_rig.py:649–696`.

With an otherwise writable output directory, fail only `events_000.json`.
`capture_000.bin` survives, but **run.json is never attempted**: one outer try
wraps all component writes. On a clean transport run the function returns
normally with a completed-exposure message and `exported_to` naming the
incomplete directory, despite `export_error`. With a simultaneous detach the
primary error remains in memory, but no final summary is persisted.

There is an earlier failure boundary too. After a transport detach, inject a
read error only when provenance hashes the framing module. `_summarise` raises
the new **OSError: injected provenance read failure**, with no attached result
and no output directory. The primary detach and its captured bytes are no
longer delivered to the caller. This is a real filesystem-error branch exposed
by a narrowly scoped mock; it does not replace the entire finalizer with a stub.

Guard counter completion, provenance, partial analysis, individual raw/event
exports and summary persistence independently. Attempt the summary even when
another file cannot be written. Preserve the primary failure, record secondary
failures, and explicitly mark the export incomplete rather than claiming a
successful export path. Provide a minimal-summary fallback when enrichment
cannot be constructed. Tests must start from a successful production run, fail
one component at a time, and assert which other artifacts remain readable and
which primary/secondary errors are present.

## Disposition

The previous B2Q exposure P2 and original resynchronisation P3 are closed within
their reviewed scope. Several original clean/full-repetition counterexamples
are fixed; do not revert them. The remaining driver, measurement and finalization
findings above block acceptance of this software batch. Save this review, correct
the implementation and add focused tests against the production entry points,
then return for review before Claude pushes the batch as accepted.

Production B2 verify still returns **S0, qualified false, refusal null**, with
71 B2 / 105 B1 pins verified. The manifest remains
`86393ed781cb25c971aeb7a4ea3bf485b5aba5a353ef94968b3128050d5b2da1`;
the B2 table remains
`8d6f64a5fed1fa222b2c29a0dddac6c6fd3346b23481ade1f00a3f104a907ebf`.
The image compatibility conclusion is unaffected. No push, production freeze,
ruling, physical port access or stop-loss exception was performed or granted.

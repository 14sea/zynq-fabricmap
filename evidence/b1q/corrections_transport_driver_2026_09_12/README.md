# The driver's five P2s — corrected, 2026-09-12

The owner's review: `docs/b1q_transport_driver_review_2026_09_12.md`, against `146e60a`, with
its probes in `evidence/b1q/review_transport_driver_2026_09_12/`. All five were reproduced from
the production entry points and all five are real. `acceptance.py` runs the same probes against
the corrected code and prints each observation **beside theirs**; `acceptance.json` is its output.

| | at `146e60a` | now |
|---|---|---|
| **P2-1** missing final newline | **302 delivered, 0 losses** over 98 598 of 98 599 bytes | **301 delivered, 1 loss**, the tail kept as a `fragment` |
| one authorised echo | clean | clean (unchanged) |
| the same echo **100 times** | `host_echo_lines: 100`, **clean true** | 1 echo consumed, **99 `unexpected_echo`**, not clean |
| 100 blank lines plus an echo | **clean true** | **100 `empty_line` defects**, not clean |
| an echo on a topology that does not echo | not distinguished | **`unexpected_echo`**, not clean |
| **P2-2** deadline after one IDENT | **302 sent, 98 599 bytes, 301 losses** | **302 planned, 1 accepted, 1 sent, 0 losses**, `incomplete`, `completed_exposure: false` |
| detach after one IDENT | capture 1 048 bytes but summary **0 sent, 0 denominator, 0 repetitions** | **1 048 bytes sent, denominator 1 048, 1 repetition**, the partial capture analysed and aggregated |
| **P2-3** a 0.01 s deadline | ran **0.115 s**, a host write started at 0.05 after expiry | ends at exactly **0.01 s**; every wait is capped by the remaining budget |
| the serial constructor | `timeout=0.05, exclusive=True`, **no write_timeout** | **`write_timeout=5.0`**, and each write is given the remaining budget (0.25 s in the probe) |
| **P2-4** paced overlap | **0 of 125** host writes during source transmission | **124 of 125**; the no-TX control is **0** |
| host traffic shape | plain `COMMAND seq` lines, **9–14 bytes** | **real rel-v4 frames, 14 289 bytes** — SIGNOK 469 bytes from the archived `sign_reply` shape, acknowledgements 69–76 |
| **P2-5** failing only `events_000.json` | **`run.json` never attempted** | `run.json` written, `export_complete: false`, `export_errors` naming the component |
| a provenance read failure after a detach | a **new** `OSError`, no result, no directory | the **primary detach** preserved as the cause, result attached, directory and capture on disk, provenance recorded as unavailable |

## What changed in the tool

* **Only complete lines are credited.** The stream is split into newline-terminated lines and an
  unterminated **tail**, which is a `fragment` — not a reconstructed final frame. An empty line
  is an `empty_line` defect, not something to skip.
* **An echo ledger with multiplicity.** The driver counts each host frame it **successfully**
  wrote; the analyser consumes echoes against those counts, only on a topology declared to echo.
  Extra copies and echoes on a non-echoing topology are defects. The normalisation used to
  compare against the expected stream now removes **exactly the accounted occurrences at their
  own offsets** — nothing else — so a blank line or an extra copy still shows as a divergence.
* **Planned, attempted, accepted, uncertain and censored are five different numbers.** An
  analysis holds the capture to the frames the transport **accepted**, never to what was planned;
  a write that started and did not complete is `uncertain`; and at a cut-off, frames whose bytes
  had nothing after them were still in flight and are **`censored`**, not losses. A partial
  capture is analysed and aggregated into the denominator. `completed_exposure` is a field: a
  zero-loss incomplete run is not one.
* **Remaining time is part of the transport contract.** Every read wait, every scheduled gap and
  every write is capped by what is left, expiry is checked before each write, and `serial_port`
  sets a `write_timeout` — an unbounded write cannot be stopped by a later check.
* **Real overlap.** The source transmits **continuously**: frame *i+1* starts when frame *i*'s
  bytes have left the wire, and a reply is due the measured gap after the frame that caused it,
  which lands while a **later** frame is on the wire. Paced, 124 of 125 host writes overlap
  source transmission; the no-TX control is 0. Each is recorded, so a run states its achieved
  overlap rather than implying it. Run parameters now record pace, read timeout, baud, byte time,
  gap and write timeout.
* **Host traffic is rel-v4.** Built with the instrument's own builder and the payloads the
  instrument sends — `{"seq": n}` for acknowledgements, the signer's `sign_reply` for SIGNOK.
  A SIGNOK is **469 bytes**, the same length as the archived answer built the same way, which a
  test asserts against `run_log.json`.
* **Every finalisation component is guarded on its own** — counters before and after, provenance,
  each repetition's analysis, each raw and event file, and the summary, which is **always
  attempted** (and falls back to `run.min.json`). Secondary failures go to `export_errors` with
  `export_complete: false`; the primary error is never replaced.

`tests/test_transport_rig.py` is **73 tests**, including every control the review names: the
complete stream, one legitimate echo, the missing final newline, extra copies, blank lines with
and without an echo, an echo on a non-echo topology, echo bytes after a failed host write;
deadline expiry in the read, the source write, the host write and the paced source separately;
detach before and after specific complete frames with both the raw files and the exact summary
asserted; the paced overlap positive control and the no-TX negative; and the finalisation with
one component failed at a time.

## Still NOT done

The plan's stage 1 requires a **physical** acceptance — a separate serial device or a physical
self-loopback. That has not happened; a pty has no UART framing, parity or overrun and loses
nothing. This remains a **partial software delivery**. Nothing here attributes anything, lifts
the stop-loss or authorises a board session; no pinned file moved.

# The three boundary P2s — corrected, 2026-09-12

The owner's review: `docs/b1q_transport_boundaries_review_2026_09_12.md`, against `38c91b0`,
with its probes in `evidence/b1q/review_transport_boundaries_2026_09_12/`. All three were
reproduced through the public API or a production `Run` and all three are real. `acceptance.py`
keeps the owner's probe structure, runs each through the corrected code, prints every
observation **beside theirs**, and asserts the answer the review asks for — the old answer now
fails loudly; `acceptance.json` is its output. The ten earlier corrections are kept and still pass.

| | at `38c91b0` | now |
|---|---|---|
| **P2-1** a writer that accepted `abc`, then raised `TypeError` internally | called **twice**, timeouts `[0.25, None]`, **`abcabc`** accepted, returned 3, no error | called **once** with `0.25`, `abc` accepted, the **TypeError propagates**; inside a run the frame is `uncertain`, the run stops with that exception as the cause and **no source or host write follows** |
| the callback contract | discovered by catching `TypeError` from an active write | **declared** by the adapter (`takes_timeout`) and checked against the signature **at construction**; a declaration that contradicts the signature is refused before any byte moves; an uninspectable builtin is taken as declared and still never probed |
| **P2-2** one accepted IDENT, the whole 1 048-byte line with one byte changed, under a cutoff | **0 losses, frame 0 censored** (normal completion said 1) | **1 loss, nothing censored**, under a cutoff and under normal completion alike; `observed: [0]`, `observed_damaged: {"0": "crc_failed"}` |
| complete silence under the same cutoff | 0 losses, frame 0 censored | unchanged — and now distinguishable from the damaged case by `observed` |
| frames 0–2 delivered, 3 absent, 4 arrives damaged, 5.. nothing | frontier `max(delivered)` = 2 → 3 and 4 censored, **0 losses** | frontier = last **observation** = 4 → **3 and 4 are losses**, 5.. censored |
| a genuinely partial line of frame 2 after 0–1 | censored | censored as `partial_frame: 2`, identified by byte-exact prefix; without a cutoff, 3 losses |
| damaged bytes that identify no frame, after the frontier | censored | **`unresolved`** — neither a loss nor in flight; `cutoff.ambiguous: true` with the count of unidentified observations |
| **P2-3** 200 requested, three frames damaged in the first, stop rule fires | `completed_exposure: true, incomplete: false` | `terminal.reason: stop_rule_losses`, `exposure_reached: false`, **`completed_exposure: false`**, `incomplete: true`; the repetition itself is `resolved` |
| every source write accepted, the deadline expires while draining, nothing back | `cut_short: true`, 302 censored, **`completed_exposure: true`** | `terminal.reason: exposure_seconds_censored`, `exposure_reached: true`, `traffic_resolved: false`, **`completed_exposure: false`**; the repetition is `incomplete` although all 302 were accepted |
| the analyser raises after repetition 1 | `losses: 0` substituted, the run **continued into repetition 2** (604 source frames), returned normally, `error: null`, "2 repetitions completed", loss rate **0.0** | **302 source frames — no second repetition**; `RigError` raised with the `ValueError` as cause; `error` set; `terminal.reason: analysis_unavailable`; **`losses: null`, rate `null`**, `repetitions_unanalysed: [0]`; the capture is exported; `export_complete: true` describes files, not measurement |

## What changed in the tool

* **`Port`**: the writer's contract is declared and checked once, against the callable's
  signature, before any write. `Port.write` no longer catches anything: an exception from an
  active write is that write's failure. A run that hits one marks the frame `uncertain`, stops,
  exports, and raises with the original exception as the cause — the path a detach already took.
* **`analyse`** tracks **observation** separately from **delivery**. A frame is observed when it
  was delivered, arrived altered, is identified by a damaged complete line, or is identified by
  the unterminated tail. `_identify` uses three correspondences with the known transmitted bytes,
  each requiring a unique match among the frames not yet observed: byte-exact **prefix**, same
  length within `NEAR_MATCH_BYTES` (**near**), and an intact **header** (magic, kind, seq, token,
  the payload's index when it decodes, one header per line, length within tolerance). At a cutoff:
  a missing frame at or below the observation frontier is a loss; the tail's frame is censored as
  partial; frames above the frontier are censored only when nothing unidentifiable arrived after
  the last identified observation, otherwise they are **`unresolved`** and reported as ambiguous.
  New fields: `observed`, `observed_damaged`, `unresolved`, `cutoff`, and `identified_by` on the
  defect. `losses` counts definitively affected frames once; `clean` also requires nothing unresolved.
* **`Run`** states its **terminal reason** — one of `TERMINAL_REASONS`: `exposure_repetitions`,
  `exposure_seconds`, `exposure_seconds_censored`, `stop_rule_losses`, `tool_error`,
  `analysis_unavailable` — set once, first wins. `completed_exposure` is **derived**:
  `exposure_reached` (the registered bound was reached) **and** `traffic_resolved` (every
  repetition resolved: all planned frames accepted, nothing uncertain, not cut short, nothing
  censored or unresolved, analysis available) **and** no error. `incomplete` is its negation, per
  repetition and per run. An analyser failure is a tool error under plan §5: the run stops there,
  the repetition's losses are `null`, the aggregate `losses` and rate are `null` while
  `losses_in_analysed_repetitions` and `repetitions_unanalysed` say what is known, and a second
  failure in the same repetition is recorded in `secondary_errors` under the primary.

`tests/test_transport_rig.py` is **94 tests** (73 → 94): `TheWriterContract` (the side-effecting
writer at the port and through a run, both signatures as positive controls, a contradicting
declaration refused, an uninspectable builtin), `ObservationIsNotDelivery` (the complete CRC
failure at the tail, silence, a valid-CRC alteration, a later damaged arrival, a genuinely
partial line, a partial line of a later frame, unidentifiable damage, two frames merged by a lost
newline, and the cutoff report through a run), `TheTerminalReason` (the zero-loss control, the
early-loss stop, the drain cutoff, a time bound reached between resolved repetitions, the
analyser failure with the assertion that no second repetition starts, an analyser failure that is
secondary to a driver failure) — each Run case asserted on the returned result **and** on the
persisted `run.json`.

## Still NOT done

The plan's stage 1 requires a **physical** acceptance — a separate serial device or a physical
self-loopback. That has not happened; a pty has no UART framing, parity or overrun and loses
nothing. This remains a **partial software delivery**. Nothing here attributes anything, lifts
the stop-loss or authorises a board session; no pinned file moved — B2 verify still reports S0,
qualified false, refusal null at `86393ed7…`, table `8d6f64a5…`, 71 B2 / 105 B1, prereg
`68cde86d…` unfrozen.

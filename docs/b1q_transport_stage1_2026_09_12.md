# B1Q transport stop-loss — a partial software delivery, and what the owner must decide (2026-09-12)

> **Host-only. No board, no port, no ruling, no attribution.** The stop-loss remains in force;
> nothing here lifts it. `docs/b1q_transport_plan_2026_09_07.md` is the reviewed plan.
>
> **Scope corrected after the owner's review of the same day**
> (`docs/b1q_transport_stage1_review_2026_09_12.md`): the first version of this document claimed
> "stage 1 in full". It is **withdrawn**. The plan's stage 1 also requires a physical acceptance
> — a separate serial device or a physical self-loopback — which has **not** happened and which
> a software pseudo-terminal cannot replace. What exists is the **generator, driver and
> analyser, with an offline acceptance**; the physical acceptance is outstanding. Four reviews that day
> found fourteen P2 defects between them, all now corrected; the four §"What the … review
> corrected" sections record each one. The B2Q exposure argument this document originally made is
> **withdrawn as wrong**, not merely softened.

## Where the stop-loss stood before today

| | |
|---|---|
| what happened | two of the first three B1Q sessions were lost to byte-level console damage; attempt 4 (2026-09-08) was clean and PASSed |
| what was decided | the owner's review of 2026-09-07 selected **option B**, controlled console-path isolation, *as an engineering investigation, not a confirmed cure*. Option A (raising the CRC budget) was refused; option C (a quiet capture) was not selected |
| what was corrected | the first diagnosis overstated its evidence. Four non-control CRC events, not five; the timing comparison had no discrimination (233 349 / 233 354 of all valid frames also arrived within 0.5 s of a host TX); the attempt-1 TERM comparison used an inferred frame |
| what was still open | everything causal. CH340/driver, USB-IP/WSL, wiring, board UART, host handling |
| stage status | **stage 0 done** (plan + inventory). Stage 1 not started: no generator, no capture tool |

Attempt 4 changed **two** variables at once (module A→B, hub port 2→3) against two lost
sessions on module A. It separates nothing, and one PASS is not stability.

## What exists — the software half

`host/transport_rig.py`, `tests/test_transport_rig.py` (**111 tests**), evidence in
`evidence/b1q/transport_stage1_2026_09_12/` and the four `evidence/b1q/corrections_transport_*_2026_09_12/`.
The generator, the driver and the analyser, with an **offline** acceptance over a pty pair
through the production entry point. **Not** the plan's stage 1 in full: the physical acceptance
on a separate serial device or a self-loopback has not happened.

It supplies the four things the three lost sessions could not:

1. **Known transmitted bytes.** 302 frames per repetition in the measured shape, real rel-v4
   built by the instrument's own `l5_notary`, deterministic and seed-derived. A divergence is
   measured against what was sent — not against a retransmission whose provenance the
   post-hoc analysis could not establish.
2. **Per-byte localisation.** First divergence offset, the frame and the byte inside it, and
   the bytes to resynchronisation.
3. **`TIOCGICOUNT` framing / parity / overrun / break counters**, before and after — the
   measurement no session recorded and none could, because it needs an open fd. When
   unavailable it is recorded as unavailable *with its reason*, never as zero.
4. **The pre-registered exposure and stop rules** of plan §5, including the early stop at
   three losses in one repetition, and the decision rule reported as losses per received byte
   **with its denominator stated** — and reported as *unavailable* when nothing was received,
   because a stream that arrived empty has no denominator.
5. **An execution contract**: the stream written frame by frame with every write's completion
   checked, the host's replies on their own port at the points a recorded session emits them,
   incremental timestamped reads, a deadline checked around every operation, and a
   finalisation that exports the raw capture, the per-read events and the partial results even
   when the run dies — with the original error preserved.

Proved the way this project proves instruments: every fault the real sessions showed is
injected into a known stream and must be detected *and* localised — a byte dropped inside a
2.6 kB REC, a bit flipped in a 66-byte HB, an excised frame, a 200-byte run, a duplicate, a
swap, a truncation, silence, line noise, a well-formed frame the rig never sent, a valid CRC
over bytes it did not send, and an earlier repetition's capture replayed into a later one.

### Two things the record gains

* The plan's §2 traffic table is now **derived from the committed bytes**, not transcribed.
* The owner's corrected count **reproduces independently**: four non-control CRC events across
  the three reviewed sessions plus one fragment — TERM in session 1; HB, REC and AUDIT in
  session 3; the malformed SIGNREQ retransmission as the fragment. The two forced controls sit
  at the same offsets in every complete session, so they are a session feature and not
  transport, and the rig therefore transmits none: every CRC failure a rig run sees is a
  transport event with nothing to subtract.

## What the fourth review corrected (the loss metric's uncertainty, 2026-09-12)

`docs/b1q_transport_uncertainty_review_2026_09_12.md` accepted the three boundary corrections
and the `exposure_reached` / `completed_exposure` distinction, and named one more P2 in what the
third round had added. Corrected, with the owner's probe re-run beside its original answers in
`evidence/b1q/corrections_transport_uncertainty_2026_09_12/`:

| finding | at `328e9c1` | now |
|---|---|---|
| **unresolved damage still became a numeric total rate** | `unresolved` frames were subtracted from `losses`, so one accepted IDENT answered by `garbled\n` at a cutoff reported `losses: 0` and **`losses_per_100k_bytes: 0.0`** — the same unqualified zero as an intact frame | **`confirmed_losses`** is the definite count and is always a number; **`losses` is the total** and is null whenever anything is unresolved or unanalysed; `losses_upper_bound` = confirmed + unresolved; the rate exists only for an exact total, with `confirmed_losses_per_100k_bytes` (a lower bound) and `losses_per_100k_bytes_upper_bound` beside it; **`loss_metric.status`** ∈ {`exact`, `bounded`, `unknown`, `no_denominator`} is the machine-readable contract. The registered three-loss stop counts **confirmed** losses and outranks the deadline reason |

## What the third review corrected (the boundaries, 2026-09-12)

`docs/b1q_transport_boundaries_review_2026_09_12.md` held the batch again and named three more
P2s at the edges of the previous fixes, all real. Corrected, with the owner's own probes re-run
beside their original answers in `evidence/b1q/corrections_transport_boundaries_2026_09_12/`:

| finding | at `38c91b0` | now |
|---|---|---|
| **a `TypeError` fallback retried a write that had taken effect** | a writer that accepted `abc` and then raised internally was called again: `abcabc` delivered, 3 returned, no error | the writer's contract is **declared** by the adapter and checked against its signature before any byte moves; an exception from an active write propagates, the frame is `uncertain`, the run stops with the original exception as the cause and nothing is written after it |
| **cutoff censoring hid a fully observed CRC failure** | the same damaged 1 048-byte line was 1 loss on normal completion and **0 losses, censored** under a cutoff; the frontier was `max(delivered)` | **observation is tracked separately from delivery**: a damaged line or the tail is matched to the frame it belongs to (unique prefix, same-length near match, or intact header), a missing frame at or below the observation frontier is a loss, the tail's frame is censored as partial, and frames above the frontier are censored only when nothing unidentifiable arrived after the last identified observation — otherwise they are **`unresolved`** and reported as ambiguous |
| **the terminal status misled** | an early-loss stop at 1 of 200 and a drain cutoff with 302 censored frames both said `completed_exposure: true`; an analyser failure was replaced by `losses: 0`, the run went on into repetition 2 and reported a 0.0 rate with `error: null` | the run states a **terminal reason** (`exposure_repetitions`, `exposure_seconds`, `exposure_seconds_censored`, `stop_rule_losses`, `tool_error`, `analysis_unavailable`); `completed_exposure` is derived from `exposure_reached` **and** `traffic_resolved`; a repetition is `incomplete` unless everything planned was accepted and resolved; an analyser failure stops the run there, its losses and the aggregate are **`null`**, not zero |

## What the second review corrected (the driver, 2026-09-12)

`docs/b1q_transport_driver_review_2026_09_12.md` held this batch and named five more P2s, all
real. Corrected, with the owner's own probes re-run beside their original answers in
`evidence/b1q/corrections_transport_driver_2026_09_12/`:

| finding | at `146e60a` | now |
|---|---|---|
| **delivery and echo accepted unsent bytes** | removing the last newline still gave 302 delivered and 0 losses; one authorised echo appended 100 times, or 100 blank lines plus an echo, were **clean** | only complete lines are credited and the tail is a `fragment`; echoes are consumed against a ledger of **successful** host writes with multiplicity, on a topology declared to echo, and only those exact occurrences are normalised away |
| **partial repetitions mis-accounted** | a deadline after one IDENT reported 302 sent and **301 losses**; a detach left a 1 048-byte capture with a summary of 0 sent, 0 denominator, 0 repetitions | planned / attempted / accepted / uncertain / **censored** are five numbers; frames never attempted are not losses, bytes in flight at a cut-off are censored, and every partial capture is analysed and aggregated. `completed_exposure` is explicit |
| **the deadline did not bound operations** | a 0.01 s limit ran **0.115 s**, starting a host write after expiry; `serial_port` set no `write_timeout` | every wait and every write is capped by the remaining budget, expiry is checked before each write, and the serial port is opened with a `write_timeout` |
| **no TX/RX overlap, and the wrong traffic shape** | **0 of 125** host writes overlapped source transmission; host traffic was `COMMAND seq` at 9–14 bytes | the source transmits continuously and a reply lands while a later frame is on the wire: **124 of 125** overlap, 0 in the no-TX control. Host frames are real rel-v4 — 14 289 bytes per repetition, SIGNOK 469 bytes matching the archived `sign_reply` |
| **finalisation lost the summary** | failing only `events_000.json` left `run.json` unwritten; a provenance read failure raised a new error over the primary detach | every component is guarded on its own, the summary is always attempted (with a `run.min.json` fallback), secondary failures are recorded and the primary error is preserved |

## What the first review corrected

Five P2s, all reproduced from the public API with a pristine generated stream as the control.
`evidence/b1q/corrections_transport_stage1_2026_09_12/acceptance.json` runs the owner's own
probes against the corrected code and prints each observation beside theirs.

| finding | at `4528ef8` | now |
|---|---|---|
| **P2-1** the loss unit double-counted, and the denominator was the bytes SENT | one corrupted frame = 2 losses, two = 4 and tripped the three-loss stop, an inserted newline = 3, a deleted frame = 1; silence gave a finite 306.204 per 100k over 98 627 bytes that never arrived | one loss = **one expected frame not delivered byte-exact, counted once**, whatever its damage; 1, 2 and 3 affected frames give exactly 1, 2 and 3; the denominator is **received** bytes, and silence reports no rate at all while still reporting 302 losses and still stopping. The registered threshold is unchanged — only the unit it counts is now correct |
| **P2-2** a known index was credited without its known bytes | keep the REC index, alter a pad byte, rebuild a valid CRC → **302 delivered, zero losses**; and every repetition regenerated identical bytes, so repetition 0's capture replayed as repetition 1 was **clean twice** | delivery requires a **byte-exact** match with the frame generated for **this** repetition; the altered frame is `damaged`, one loss. Each repetition carries its own epoch token, so a replayed capture is 302 losses, not a clean run. A write that reports fewer bytes than it was given — or reports nothing — is a refusal |
| **P2-3** the driver did not implement the planned traffic or capture | one write of the whole stream, then every host command to the same writer, then **one** read; `after_frame` never used; the host schedule was `i % 8` (8 AUDITGET against the plan's 30); a 0.1 s limit spent **2.232 s** and still reported a completed repetition | 302 frame-by-frame writes with completion checked, **125 host replies on the host port** by the rule the clean session's own `timeline.json` exhibits (88 AUDITGET, 12 SIGNOK, 11 AUDITDONE, 12 RECACK, IDENTACK, TERMACK — the same 125 that session sent), interleaved with incremental timestamped reads; the 0.1 s limit now stops **inside** the repetition after 2 frames. A self-loopback's returning host traffic is classified as `host_echo` and the topology is recorded, instead of being filtered away by a test helper |
| **P2-4** the error path lost the result | `RigError` raised, nothing returned, counters sampled once, no raw capture anywhere | counters attempted on **both** sides, raw capture and per-read events per repetition and the partial results **exported to disk**, the result attached to the exception, and the **original** error preserved — an export failure is recorded inside the result, never allowed to replace it |
| **P2-5** the B2Q exposure argument compared different units | "20 B2Q records vs 302 B1Q frames — a much shorter exposure" | **withdrawn.** Production `qualification_session_plan` derives **543 expected frames** for B2Q (160 AUDIT, 320 HB, 20 REC …) against B1Q's 302 — *more*, not fewer — and even that is planning arithmetic, not an observed run |
| **P3** `bytes_to_resync` only found a newline | an inserted newline reported `1` | two fields: `bytes_to_next_newline`, and `resynchronised_at`, which names the next line that is **byte-exactly an expected frame of this repetition** (or null) |

## The physical half — entry point ready, awaiting the owner's ruling (2026-09-13)

The owner accepted the software delivery on 2026-09-12 and on 2026-09-13 answered plan §7: the
WSL + usbipd path is to be tested first (the earlier usbipd failure was a host configuration
error; the native Linux host exists but is deferred) and board power is permitted if needed —
and corrected the wiring: the CH340 is host-USB-powered and reaches the board by GND, TX, RX only,
so the self-loopback involves no board power and needs no ruling (plan §4). `host/transport_rig.py
run --device …` is the entry point for that
run — device identity from sysfs, a loopback preflight that refuses silence before spending the
exposure, the real fd for `TIOCGICOUNT`, the registered exposure as defaults — proved offline in
`TheDeviceEntryPoint` (10 tests) against a fake serial module. The procedure, the wiring and
what a result can and cannot say are in
`docs/b1q_transport_physical_stage1_procedure_2026_09_13.md`. **Not yet run on any port.**

## What is still blocked, and on whom

Stage 2 runs the four conditions of plan §3 (WSL+USB/IP vs native Linux, each with and without
host TX during RX). It cannot start until the owner answers plan §7:

1. **Is a native Linux host available** that can take the CH340 by direct USB? The preferred
   first experiment changes the host path only; without it the order changes and an
   adapter-only design comes first.
2. **Can the CH340 module be detached from the board header and looped back**, powered from
   host USB? If yes, stage 1's rig runs with **no board involvement at all**; if it is powered
   from the board's Type-C, powering it powers the stack and that needs its own ruling.
3. **Is a second known-good USB-serial adapter available** as traffic source and cross-check?

## The decision that actually gates B2Q

The B2 preregistration §6 records the transport stop-loss as unresolved, and B2Q runs over the
same console path with the same instrument. Two dispositions are available and they are the
owner's, not mine:

* **Attribute first** — run stages 2 and 3, then decide. Highest confidence, needs the
  hardware in §7 and takes its own time.
* **Proceed with a declared exposure** — schedule B2Q under a named stop rule and the standing
  instrument stop-loss, with the transport question left open and recorded.

**The "shorter exposure" rationale this document originally offered for the second option is
withdrawn.** It compared 20 B2Q *records* against 302 B1Q *frames*, which are different units.
Production `qualification_session_plan` derives **543 expected frames** for B2Q — 160 AUDIT,
320 HB, 20 REC, 20 SIGNREQ, 20 AUDIT_READY, IDENT, CLOSE, TERM — against B1Q's 302 transmitted
frames. On the only unit that was actually compared, B2Q is the **larger** exposure. And that
number is planning arithmetic, not an observed run: any disposition must compare declared
frames, bytes and duration, with the applicable controls and retries, in like units.

What must **not** happen either way: if a session is to carry transport instrumentation
(an exclusive open, or the counters above), that is a **pinned change to the runner**, and the
plan already fixes its order — it lands, is reviewed and is re-qualified *before* the session
that counts. After S1 and B2Q it would be exactly the "changing pinned inputs after
qualification" the owner ruled out on this same day.

## Standing

No board contact, no port opened, no ruling, no freeze, no attribution, no change to any pinned
file. The rig sits deliberately outside **both** pinned globs, so neither the B2 manifest and
its 71 / 105 pins nor B1's frozen table moved. That placement was not free: written first as
`host/b1q_transport_rig.py`, it was refused by B1's own pin guard — *files matching the pinned
globs are not in the table* — which is the guard working. An investigation tool in a verdict
namespace would either churn a frozen manifest or claim an authority it does not have, so it is
named outside both and carries its own sha256 beside every result instead.

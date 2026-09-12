# B1Q transport stop-loss — stage 1 delivered, and what the owner must decide (2026-09-12)

> **Host-only. No board, no port, no ruling, no attribution.** The stop-loss remains in force;
> nothing here lifts it. `docs/b1q_transport_plan_2026_09_07.md` is the reviewed plan and this
> executes the part of it that needs nothing but a host.

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

## What was built today — stage 1

`host/transport_rig.py`, `tests/test_transport_rig.py` (30 tests), evidence in
`evidence/b1q/transport_stage1_2026_09_12/`. The plan's stage 1 in full: *the generator and
capture tool, proved against a separate traffic source, not the Zynq.*

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
   **with its denominator stated**.

Proved the way this project proves instruments: every fault the real sessions showed is
injected into a known stream and must be detected *and* localised — a byte dropped inside a
2.6 kB REC, a bit flipped in a 66-byte HB, an excised frame, a 200-byte run, a duplicate, a
swap, a truncation, silence, line noise, and a well-formed frame the rig never sent. **That
last case found a real defect** (a foreign frame was being counted as delivered); it is fixed.

### Two things the record gains

* The plan's §2 traffic table is now **derived from the committed bytes**, not transcribed.
* The owner's corrected count **reproduces independently**: four non-control CRC events across
  the three reviewed sessions plus one fragment — TERM in session 1; HB, REC and AUDIT in
  session 3; the malformed SIGNREQ retransmission as the fragment. The two forced controls sit
  at the same offsets in every complete session, so they are a session feature and not
  transport, and the rig therefore transmits none: every CRC failure a rig run sees is a
  transport event with nothing to subtract.

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
* **Proceed with a declared exposure** — accept that B2Q is 20 records against B1Q's 302
  frames, i.e. a much shorter exposure, and schedule it under a named stop rule and the
  standing instrument stop-loss, with the transport question left open and recorded.

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

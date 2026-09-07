# B1Q console-path isolation — the option-B plan (preparation only, 2026-09-07)

> **Standing: PREPARATION ONLY.** The owner selected option B as a *controlled
> path-isolation experiment, not a proven cure*
> (`docs/b1q_transport_review_2026_09_07.md`), and authorised the preparation of the plan
> and nothing else. Stop-loss remains in force. Nothing here has been executed: no port
> opened, no cable moved, no device detached or re-attached, no board run, no new ruling.
> Every number below is read-only host state or arithmetic over already-committed session
> evidence (`evidence/b1q/transport_plan_2026_09_07/inventory.json`). A successful
> diagnostic is **not** a B1Q PASS and waives nothing in the qualification chain.

## 0. What the inventory adds (facts, not attributions)

Three host-side facts that bear on the design, none of which names a cause:

1. **Both USB devices are attached over the same USB/IP socket.** `vhci_hcd` shows the
   FT4232H (`1-1`) and the CH340 (`1-2`) sharing `sockfd 000003`. This is direct evidence
   for the owner's point: exchanging the console adapter while keeping this arrangement
   does not remove USB/IP from the path, so adapter-swap-first would confound the result.
2. **The sessions carry no serial error counters, and none can be read without opening the
   port.** `/proc/tty/driver/usbserial` is absent and the `ttyUSB4` sysfs nodes expose no
   framing/parity/overrun/break counts; `TIOCGICOUNT` on an open fd is the only source, and
   neither pyserial nor the instrument calls it. The three sessions therefore contain no
   measurement of framing, parity or overrun at all — which is why the mechanism could not
   be settled from them.
3. **The console port is not opened exclusively.** The archived instrument opens
   `serial.Serial(port, baud, timeout=0.1)` — 115200 8N1, raw, no flow control, and no
   `exclusive=True`. Nothing holds `ttyUSB4` now and no known serial-grabbing daemon is
   running, but no session recorded whether anything held it at the time. Port contention
   is therefore an **unexcluded hypothesis**, not a finding — and it is cheap to exclude.

**Constraint on any instrumentation.** The transport is the archived instrument's code
(read-only, pinned by hash). Counter capture, an exclusive open, or any other transport
change must be a B1-side wrapper in this repository, which is a **pinned-file change** — so
it must land, be reviewed and be re-qualified *before* the B1Q session that is meant to
count (`docs/b1q_transition_decision_2026_09_06.md`).

## 1. The one variable

The preferred first experiment changes **the host USB path only**: the same CH340, the same
wiring, the same 115200 8N1 raw settings, the same traffic — moved from WSL + USB/IP to a
native Linux host with the adapter attached directly. Nothing else moves. If a native host
is unavailable, an adapter-only design is submitted separately, with verified pinout and
voltage, before any rewiring; the two changes are never made together.

## 2. The traffic the rig must reproduce

A quiet capture does not represent the traffic that failed, so the generator reproduces the
measured shape of a B1Q session (from the committed `console.log` of the three sessions):

| board→host frame | count per session | bytes |
|---|---:|---|
| HB | 176 | 65–66 |
| AUDIT chunk | 88 | 304–708 |
| SIGNREQ | 12 | 370–375 |
| REC | 12 | **2610–2915** |
| AUDIT_READY | 11 | 230–235 |
| IDENT | 1 | 1048 |
| TERM | 1 | 711–724 |
| CLOSE | 1 | 217 |

Total ≈ 302 frames / ≈ 94 kB per session; a 2.6 kB REC occupies 227 ms of wire time at
115200. The corrupted frames in the real sessions were REC, AUDIT, HB and TERM — both the
longest and the shortest classes. The host side must also reproduce its **send bursts**
(attempt 3: 30 AUDITGET, plus SIGNOK / AUDITDONE / RECACK / RECGET / IDENTACK / SIGNGET /
AUDITABORT), with the measured tx→next-rx gap (median 62 ms, min 41 ms), because the
host-transmitting-while-receiving condition is one of the things under test.

**Known transmitted bytes.** The generator emits a deterministic, seed-derived stream framed
to the length distribution above, with a per-frame sequence number and a per-byte position
check, so any loss is localisable by offset and length rather than inferred from a
retransmission. This removes the comparison-provenance weakness of the post-hoc analysis:
the transmitted bytes are known in advance, not reconstructed.

## 3. Conditions

Pre-registered, each run under one condition only:

| condition | host path | host TX during RX | purpose |
|---|---|---|---|
| A1 | WSL + USB/IP | yes (session-shaped bursts) | reproduce the failing configuration |
| A2 | WSL + USB/IP | no (receive only) | the TX-overlap question, with a proper denominator this time |
| B1 | native Linux, direct USB | yes | the isolation comparison against A1 |
| B2 | native Linux, direct USB | no | the same control on the other path |

A2/B2 exist only as controls for A1/B1 and are not a stand-alone quiet capture. Every
condition records: the raw received bytes, per-frame CRC results, fragments, retries,
per-read timestamps, and **`TIOCGICOUNT` framing/parity/overrun/break counters sampled
before and after each run** — the counters the sessions lack.

## 4. Order of work, and what each stage needs

| stage | what | needs |
|---|---|---|
| 0 | this plan + inventory (**done**) | nothing; already host-only |
| 1 | build the generator/capture tool and **prove it against a separate traffic source**, not the Zynq | a second serial device or a CH340 self-loopback; a physical jumper and, if the module is board-powered, a ruling |
| 2 | run A1/A2, then B1/B2, one variable apart | a native Linux host; the adapter moved between hosts |
| 3 | read the result: loss on A but not B ⇒ the WSL/USB-IP path; loss on both ⇒ the adapter, driver, wiring or host handling; loss on neither ⇒ the rig does not yet reproduce the failure and the design returns to stage 1 | — |
| 4 | only then: the transport instrumentation lands as a reviewed pinned change, and a board session is requested under a **new** ruling pair | the owner's ruling |

Stage 1 deliberately proves capture and replay **without the Zynq**. If the CH340 module is
host-USB-powered and can be unplugged from the board header, the entire first stage runs
with no board involvement at all; if it is powered from the board's Type-C, powering it
powers the stack and that needs its own ruling.

## 5. Exposure and stopping criteria, fixed in advance

- **Exposure per condition:** 200 × the session traffic profile ≈ 19 MB and ≈ 60 000
  frames, or 60 minutes, whichever comes first.
- **Stop early** on: 3 losses within one profile repetition (record and stop — the
  condition is reproducing the failure), any tool error, any device detach, or any change
  of a variable other than the one under test.
- **Decision rule, pre-registered:** the comparison is losses per received byte with its
  exact denominator stated, A1 vs B1, on the pre-declared exposure. A difference is
  reported as a difference under that exposure; it is not extrapolated to a stationary
  link-noise rate, and no per-frame timing window is used to argue causation — the base
  rate of that window is already known to be ~100 % of normal traffic.
- **Nothing in the result is a qualification outcome.** A clean B1 does not qualify the
  carrier, does not lift the stop-loss by itself, and does not authorise a board session.

## 6. What this plan does not do

It does not raise the CRC budget (excluded), does not change the budget's meaning (option A
is not approved), does not run a stand-alone quiet board capture (option C is not
selected), does not touch the archived instrument, and does not attribute the loss to any
component: CH340/driver, USB/IP/WSL, wiring, board UART and host handling all remain open
until an experiment separates them.

## 7. Open questions the owner must answer before stage 1

1. Is a **native Linux host** available that can take the CH340 by direct USB? The preferred
   first experiment depends on it; without it the order changes and the adapter-only design
   comes first.
2. Can the **CH340 module be detached from the board header and looped back** on its own,
   powered from host USB? If yes, stage 1 needs no board involvement; if no, it needs a
   ruling.
3. Is a **second known-good USB-serial adapter** available as the traffic source and
   cross-check?

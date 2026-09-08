# B1Q console-path isolation — the option-B plan (preparation only, 2026-09-07)

> **Standing as of 2026-09-08: the isolation experiment remains unexecuted; attempt 4
> completed separately and passed.** The original authorization covered preparation of
> option B (`docs/b1q_transport_review_2026_09_07.md`). The dated updates below record
> subsequent owner-directed moves and the reported one-session stop-loss exception for
> attempt 4. They supersede the original statement that no board run or cable move had
> occurred. Attempt 4 is not an execution of the controlled isolation experiment and
> does not establish transport stability or authorize another session. See
> `docs/b1q_session4_audit_2026_09_08.md` for its independent evidence audit.

## 0. What the inventory adds (facts, not attributions)

Three host-side facts that bear on the design, none of which names a cause:

1. **Both USB devices are attached through the same USB/IP mechanism** (`vhci_hcd`, one
   TCP connection to usbipd *per device*). Exchanging the console adapter while keeping this
   arrangement does not test removal of USB/IP. An adapter-only swap can compare adapters
   on that path, provided the other variables are held fixed. *Corrected 2026-09-08:*
   the first version of this item claimed both devices
   share **one** socket because both `vhci_hcd` rows show `sockfd 000003`; that number is the
   file-descriptor index inside each attach process, not a socket identity, and `ss` shows
   two separate established connections. The design point stands; that evidence is withdrawn
   (`evidence/b1q/transport_plan_2026_09_07/host_topology_2026_09_08.json`).
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

**Host topology, read 2026-09-08 (after the owner re-plugged the CH340).** Full record in
`evidence/b1q/transport_plan_2026_09_07/host_topology_2026_09_08.json`. In brief:

- The CH340 is **not** on an independent USB path. It moved from port 2 to port 3 of the
  same external Genesys `05e3:0610` USB 2.0 hub on which the FT4232H sits at port 1
  (`usbipd` BusIds `4-3` / `4-1` are hub-relative). Both still share that hub, its upstream
  link to PCH-xHCI root port 4, and the controller. An independent path means a device
  whose Windows LocationPaths has a single `#USB(n)` after `USBROOT(0)`, ideally on the
  other controller (`PCI(0D00)`).
- Two Windows-side components were not in the plan's path list: **`hrdevmon.sys`** (Huorong
  Internet Security device monitor, a Boot-start USB-class upper filter bound to every USB
  device, the hub and both adapters included), and the fact that `VBoxUSB`/`VBoxUSBMon`
  are usbipd-win's own stub driver (VirtualBox is not installed). The `VBoxUSBMon` event-4
  bursts in the System log occur at bind time, ~5 min before each session, never inside one.
- **No device-level drop inside any session window.** Kernel-PnP logs show no
  re-enumeration, surprise removal or port reset of the CH340 or FT4232H during the three
  sessions; the post-hoc WSL dmesg for session 1 shows nothing but vhci's informational
  `seqnum max`. The loss is byte-level on an attached device. Hub ports 1–3 do carry older
  enumeration-failure ghosts (Jul/Aug), outside every session.
- Nothing holds `/dev/ttyUSB4` now; the CH340 reports `bcdDevice 0x0264`, full-speed, no
  serial number.

None of this attributes the loss. No device-level drop was found in the inspected logs;
that is not proof that every transient would have been recorded. The "one shared socket"
claim is withdrawn, and the host path list now includes hub sharing and `hrdevmon`.

**Update 21:50 the same evening.** The owner moved the CH340 again; it now sits directly on
PCH-xHCI root port 9 (`PCI(1400)#USBROOT(0)#USB(9)`, parent = the root hub, `usbipd` BusId
`2-9`), so the shared-hub variable is removed. The FT4232H is unchanged behind the
`05e3:0610` hub. What the console path still shares with the recorded sessions: the same
xHCI controller (the second controller only exposes the dock's SuperSpeed hub on this
laptop), `hrdevmon`, the `VBoxUSB` stub, usbipd/USB-IP, `vhci_hcd`, `ch341`, pyserial, the
same CH340 module, the same wiring, the same board UART. WSL re-bound it cleanly to
`ttyUSB4` (`/dev/ebaz-uart` follows). Recorded in the same evidence file under
`re_plug_2026_09_08_2150`.

**Update 21:55.** The owner swapped in a **second CH340 module** and returned it to the hub
(port 3), stating the order "test from the hub first". The new module is
descriptor-identical to the first (`bcdDevice 0x0264`, same endpoints, no serial number), so
nothing on the host distinguishes the two; module identity in any comparison is
owner-attested at run time. WSL bound it as `1-1` → `ttyUSB0` this time (`/dev/ebaz-uart`
followed). Versus the three sessions the changed variables are now *module* and *hub port*;
hub sharing, the Windows stack, USB/IP, WSL and the board side are unchanged. Recorded under
`module_swap_2026_09_08_2155`.

**Attempt 4 (2026-09-08-01, executed 22:02–22:07 BST) under a new ruling pair — PASS.**
The owner chose a board session over the loopback rig ("test from the hub first"), with
a fresh power cycle, boundary `principal_boundary_2026-09-08-01.json`, module B on hub
port 3, wiring untouched. Result: 300/300 frames received, 11/11 records audited, the
only two CRC drops are the two forced controls (SIGNREQ seq 1, REC), zero non-control
drops, zero fragments, `COMPLETED / budget` — the same profile as attempt 2.
`qualification.json` re-verifies PASS in memory against the current manifest; the record
is **not yet pinned** (owner's call). What this is and is not: one clean session with two
variables changed at once (module A→B, hub port 2→3) against two lost sessions on module
A; it does not separate module from port, does not implicate or clear USB/IP, `hrdevmon`,
the hub, the wiring or the board UART, and — as the transition decision already says — a
single PASS does not establish transport stability. The isolation plan above remains the
instrument for attribution if the owner still wants one.

**Audit clarification.** The 21:55 topology snapshot names `ttyUSB0`, whereas attempt 4's
`summary.json` records `/dev/ebaz-uart` resolving to `ttyUSB4` (`188:4`). These are distinct
observations at different times; the intervening enumeration history is not supplied by
the session evidence. Module B and hub port 3 remain operator-attested run conditions.
The transcript validates board 17A6 and the session binding, not the physical adapter's
identity. No original topology snapshot or session file has been rewritten to reconcile
the device names.

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
| 3 | compare the observed loss and exposure under each complete host path; an A/B difference does not isolate USB/IP from the other host-stack changes, loss on both does not identify a common cause, and loss on neither leaves reproduction unresolved | — |
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

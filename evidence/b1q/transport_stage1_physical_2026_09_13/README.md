# B1Q transport — stage 1's physical half: CH340 self-loopback on WSL (2026-09-13)

The plan's stage 1 physical acceptance (`docs/b1q_transport_plan_2026_09_07.md` §4), run through
`host/transport_rig.py run --device` (`docs/b1q_transport_physical_stage1_procedure_2026_09_13.md`).

**Wiring (the owner, 2026-09-13):** the USB-CH340 module's TX and RX wires were taken off the
main board's J7 and joined to each other; its VCC5, 3.3 V and GND pins are all unconnected;
the module is powered by the host USB. **The board is not powered and not on the line.** Attached
to WSL with usbipd; node `/dev/ebaz-uart → /dev/ttyUSB0`, `188:0`, USB `1a86:7523` "USB Serial",
kernel driver `ch341` — recorded by the tool in each `invocation.json`.

## Rehearsals (`--repetitions 2`, NOT the acceptance)

| dir | condition | reps | frames accepted / delivered | received bytes | confirmed losses | metric | terminal |
|---|---|---|---|---|---|---|---|
| `rehearsal_notx/` | no host TX during RX | 2 | 604 / 604 | 197 198 | 0 | exact | `exposure_repetitions` |
| `rehearsal_tx/` | host TX during RX | 2 | 604 / 604, 250 host frames echoed and accounted | 225 776 | 0 | exact | `exposure_repetitions` |

Preflight nonce matched in both (43 of 43 bytes, ~0.35 s). One repetition takes ~35 s on this
path without pacing (the port's own wire time plus the 50 ms read waits), so the registered
exposure of 200 repetitions will be bounded by the 3 600 s limit at roughly repetition 100, with
the last repetition's in-flight tail censored — that is the `exposure_seconds_censored` case the
owner accepted, and it is reported as such, not as a completed exposure.

**The `TIOCGICOUNT` counters are unavailable on this adapter**: the `ch341` driver answers the
ioctl with `ENOTTY` ("Inappropriate ioctl for device"), before and after every run. The tool
records that as unavailable with the reason, never as zero. The framing / parity / overrun /
break measurement the plan hoped for cannot be had from this adapter's driver; a second adapter
whose driver implements it (FTDI, CP210x, PL2303 do) would be needed for that particular
evidence. Byte-exact delivery against known transmitted bytes — the loss measurement itself —
does not depend on it.

## The runs

| dir | condition | exposure | reps | frames accepted / delivered | received bytes | confirmed losses | rate / 100k | metric | terminal |
|---|---|---|---|---|---|---|---|---|---|
| `notx/` | no host TX during RX | **registered** (200 reps / 3 600 s) | 103, the last cut at 177/302 by the time bound | 30 981 / 30 981 | 10 109 648 | **0** | 0.0 | exact | `exposure_seconds_censored` (reached; not complete — see note) |
| `tx/` | host TX during RX | **declared shorter: 20 repetitions** (the owner's choice, 2026-09-13, to save time; not the registered exposure) | 20 | 6 040 / 6 039 | 2 257 741 | **1** | 0.044 | exact | `exposure_repetitions`, completed |

Both preflights matched. Counters unavailable throughout (`ch341`, `ENOTTY`).

### The one loss, byte by byte (`tx/`, repetition 0, `capture_000.bin` offset 40 304)

Frame **121**, an AUDIT of 458 bytes, followed on the wire by the rig's own AUDITGET reply (77
bytes, seq 120) — both written by the host, both looping back. What came back in one read of
516 bytes (13.928 s into the repetition) instead of 535:

| where | expected | received | what happened |
|---|---|---|---|
| frame 121, byte 352 of 458 | `…rDK1g2rS1EoO…` | `…rDK12rS1EoO…` | **one byte (`g`) deleted**; the rest of the frame, CRC included, follows shifted by one — `crc_failed`, identified by its intact header |
| the AUDITGET echo, inside its 32-hex token | `f1a058d8e549403ae4acfb1e6484a99d` | `f1a05e6484a99d` | **18 contiguous bytes deleted**; the line no longer matches the written echo, so it is a second `crc_failed` line and one echo is unaccounted (124 of 125) |

19 bytes missing in total, in two deletions about 120 wire-bytes apart, both inside the same
read. Nothing was duplicated or reordered; frames 0–120 and 122–301 of that repetition and all
of repetitions 1–19 are byte-exact. One expected frame affected → **one confirmed loss** (the
echo is host traffic, not traffic under test; its damage is a diagnostic).

### What this says, and what it does not

- **The failure class reproduces without the Zynq and without the board powered.** The three
  lost B1Q sessions showed CRC-failed frames on the console path; here a CRC-failed frame with
  bytes *deleted* appears on a path that is only usbipd, the CH340 and the WSL host — under the
  condition the sessions also had, host TX while RX is in progress.
- **0 losses in 10.1 MB without host TX; 1 loss in 2.26 MB with it.** That is a difference under
  these two exposures (plan §5), reported as such. It is **not** significant on its own — one
  event against zero, with unequal exposures — and it is not extrapolated to a rate. It points
  where the next exposure should go: more TX-during-RX traffic on this same path, and the same
  two conditions on the native Linux host (plan §3 B1/B2) when that host is configured.
- 18 contiguous bytes vanishing is the shape of a dropped or truncated USB bulk transfer or a
  FIFO overrun, not of line noise; without `TIOCGICOUNT` on this driver it cannot be told which.
- Nothing here is attribution to a component, lifts the stop-loss, or authorises B2Q. The
  disposition is the owner's.

### Two tool observations for the next review (not changed here)

1. `divergence.first_offset` in an echo topology points at the first *accounted* echo (here
   offset 1 423, inside HB 2) rather than at the damage, because `_divergence` compares the raw
   capture with the expected stream when they are not equal after echo removal. It should
   compare the echo-stripped stream so the first offset is the first real divergence.
2. `notx/` ended `exposure_seconds_censored` with **0** censored and 0 unresolved: the time
   bound cut repetition 102 after 177 frames and all 177 arrived. The reason name says
   "censored" for what is only "cut short with nothing in flight"; the fields are right, the
   name over-states. A separate `exposure_seconds_cut` (or the same name with the counts) would
   read truthfully.

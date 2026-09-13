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

## The acceptance runs

Added below as they complete; each is a full registered exposure under one condition.

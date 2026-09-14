# B1Q transport — plan §3 B1/B2: the same CH340 self-loopback on a native Linux host (2026-09-14)

The plan's native-Linux comparison (`docs/b1q_transport_plan_2026_09_07.md` §1 and §3, conditions
B1/B2), run through the same tool as the WSL runs of 2026-09-13
(`evidence/b1q/transport_stage1_physical_2026_09_13/`), on the same adapter, the same wiring,
the same 115200 8N1 settings and the same traffic. **The one variable that moved is the host USB
path: WSL + usbipd → a native Linux host with the CH340 on a root port.** Nothing here is
attribution, lifts the stop-loss, or authorises B2Q; the disposition is the owner's.

## The host, as found and as prepared (2026-09-14)

- Orange Pi 3B, Ubuntu 22.04.5 aarch64, kernel `5.10.160-rockchip-rk356x`, Python 3.10.12,
  pyserial 3.5 (`pip --user`), `lrzsz` installed (not used by these runs).
- CH340 `1a86:7523` "USB Serial", bcdDevice `0264`, on USB bus 5 root port 1 (xhci, no hub,
  full-speed), kernel driver `ch341`; node `/dev/ebaz-uart → /dev/ttyUSB0`, `188:0`, udev rule
  identical to the WSL one. Recorded by the tool in each `invocation.json`, and gated with
  `--expect-usb 1a86:7523` (matched in all four runs).
- As found, `brltty` 6.4 claimed the CH340 within a second of every attach (its rule 293
  matches `1a86/7523` as a braille display) and the tty node disappeared. `brltty` was purged
  before any run. An FT4232H "Xilinx" JTAG cable (`0403:6011`) had been on the host earlier and
  was detached before the runs; only the CH340 was attached during them.
- The repository checkouts on the host are git clones from bundles of the WSL trees:
  `~/zynq_fabricmap` at `918de3f` (the WSL HEAD, four commits ahead of `origin/main`) and
  `~/zynq_psoracle` at `689dde1`, both clean; `PSORACLE_ROOT=$HOME/zynq_psoracle`. The tool is
  the current one (`transport_rig.py` sha `e2af873d…`, framing `0ceab57c…`), not the
  `aaff46e9…` version the WSL acquisitions used.
- The three transport test suites ran on this host under Python 3.10 before any port was
  opened: 161 of 162 pass; the one failure is `test_b1_transport`'s B1 session pin gate, which
  pins five git-ignored Vivado artefacts (`vivado/carrier/generated/vivado.jou`, `vivado.log`,
  two `*.backup.jou`, `clockInfo.txt`) that a clone does not contain. Neither `transport_rig`
  nor `board_transport_soak` reads those pins. Noted for the owner; not changed here.

**Wiring (the owner, 2026-09-14):** the CH340 module's TX and RX wires are off the main board's
J7 and joined to each other; the module is powered by the host USB; **the board is not powered
and not on the line** — the same loopback as the WSL runs. The owner confirmed this before the
first port open.

`TIOCGICOUNT` is unavailable on this driver too — `ch341` answers `EINVAL` here (WSL's answered
`ENOTTY`); recorded as unavailable with the reason, never as zero. No overrun / framing count is
available on either host.

## Rehearsals (`--repetitions 2`, NOT the comparison)

| dir | condition | reps | frames accepted / delivered | received bytes | confirmed losses | terminal |
|---|---|---|---|---|---|---|
| `rehearsal_notx/` | no host TX during RX | 2 | 604 / 604 | 197 198 | 0 | `exposure_repetitions` |
| `rehearsal_tx/` | host TX during RX | 2 | 604 / 604, 250 host frames echoed and accounted | 225 776 | 0 | `exposure_repetitions` |

Two repetitions took 71 s here against 70 s on WSL: the rate is set by the port and the rig's
read waits, not by the host.

## The runs, side by side with WSL

| condition | host | reps | frames accepted / delivered | received bytes | confirmed losses | per 100 k bytes | terminal |
|---|---|---|---|---|---|---|---|
| no host TX (B2 vs A2) | WSL 09-13 `notx/` | 103, cut at 177/302 by the 3 600 s bound | 30 981 / 30 981 | 10 109 648 | **0** | 0.0 | `exposure_seconds_censored` |
| no host TX (B2 vs A2) | **orangepi `notx/`** | 101, cut at 172/302 by the 3 600 s bound | 30 372 / 30 368 | 9 907 831 | **4** | 0.040 | `exposure_seconds_censored` |
| host TX during RX (B1 vs A1) | WSL 09-13 `tx/` | 20 | 6 040 / 6 039 | 2 257 741 | **1** | 0.044 | `exposure_repetitions` |
| host TX during RX (B1 vs A1) | **orangepi `tx/`** | 20 | 6 040 / 6 039, 2 500 host frames echoed, all accounted | 2 257 759 | **1** | 0.044 | `exposure_repetitions` |

All preflights matched. No frame censored in flight, none unresolved, no secondary errors, all
exports complete. The `notx/` `exposure_seconds_censored` case is the same "cut short with nothing
in flight" the WSL README already flagged as over-named.

### The five losses, byte by byte

Each lost frame was regenerated from the run's `run_id` with the tool's own `plan_frames` and
compared byte by byte with the captured line (`capture_NNN.bin` at the defect offset). Every one
is a **single contiguous deletion inside a REC frame**; the rest of the frame, CRC included,
follows shifted, so the line fails CRC and is identified by its intact header. The next expected
frame is byte-exact in every case (`resynchronised_at` = the next index).

| run | repetition | frame | expected → received bytes | deleted | at byte of frame | context expected → received |
|---|---|---|---|---|---|---|
| `notx/` | 36 | REC 253 | 2 860 → 2 858 | 2 (`G4`) | 1 120 | `…uQwG4uy…` → `…uQwuy…` |
| `notx/` | 41 | REC 299 | 2 916 → 2 915 | 1 (`i`) | 2 432 | `…b6biSPs…` → `…b6bSPs…` |
| `notx/` | 72 | REC 199 | 2 804 → 2 803 | 1 (`q`) | 192 | `…OK2qHfr…` → `…OK2Hfr…` |
| `notx/` | 86 | REC 64 | 2 667 → 2 666 | 1 (`6`) | 1 120 | `…CR6mCJ…` → `…CRmCJ…` |
| `tx/` | 0 | REC 145 | 2 752 → 2 751 | 1 (`F`) | 2 176 | `…Vj5Fd_Q…` → `…Vj5d_Q…` |

Nothing duplicated or reordered anywhere; every other frame of every repetition is byte-exact. In
`tx/` all 125 host echoes per repetition are accounted, including in repetition 0 — unlike the
WSL loss, where the neighbouring AUDITGET echo lost 18 bytes as well.

### What this says, and what it does not

- **Byte deletions of the same shape occur on the native Linux host, on a root port, with no
  USB/IP and no WSL in the path.** With host TX during RX the two hosts are equal under this
  exposure: 1 loss in ~2.26 MB each. Without host TX, WSL showed 0 in 10.1 MB and this host 4 in
  9.9 MB.
- That is a difference under these exposures (plan §5), reported as such and not extrapolated to
  a rate; four events against zero at ~10 MB each is a small count. What the pair of runs does
  establish is that the WSL `notx/` zero was not a property of the CH340 + loopback + rig alone.
- What stays common to both hosts is the CH340 (`bcdDevice 0264`), the `ch341` driver family,
  the three-wire loopback, and the rig's traffic and read cadence; what differs is everything
  else in the host stack (usbipd + Windows + WSL vs a Rockchip xhci root port + kernel 5.10).
  **The cause is unresolved.** A dropped or truncated USB bulk transfer, a receiver FIFO overrun
  in the CH340, and host read scheduling are all candidates; the deletion shape alone does not
  isolate one, and neither driver gives an overrun count. Two of the five deletions fall at byte
  1 120 of their frame and none of the five in the first 190 bytes; that is an observation, not a
  mechanism.
- Nothing here attributes the B1Q session losses to a component, lifts the stop-loss, or
  authorises B2Q. The plan's next step remains the owner's call; the adapter-only comparison
  (plan §1's second design, a driver with `TIOCGICOUNT`) is the one that would add the overrun
  evidence both hosts lack.

## Files

Per run: `invocation.json` (argv, node identity, `identity_check`, provenance), `preflight.json`
+ `preflight_rx.bin`, `capture_NNN.bin` + `events_NNN.json` per repetition, `run.json`,
`entry.json`. Copied from the host with `rsync -a`; `run.json` sha256 verified equal on both
sides after the copy (`notx` `034b5109…`, `tx` `af9bb0dd…`, `rehearsal_notx` `d5a116ce…`,
`rehearsal_tx` `096933e7…`).

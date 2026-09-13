# B1Q transport — stage 1's physical half: the self-loopback procedure (2026-09-13)

> **Host-only until the owner's ruling.** This document is the procedure and the tool entry
> point for plan §4 stage 1's physical acceptance — a CH340 self-loopback — which the software
> acceptance (`docs/b1q_transport_software_acceptance_2026_09_12.md`) explicitly left open. It
> authorises nothing: the owner's answers of 2026-09-13 are that the WSL + usbipd path is the one
> to test first (the earlier usbipd failure was a host configuration error) and that board power
> is permitted if needed. **Corrected the same day by the owner:** the CH340 module is powered
> from the host's USB and reaches the board by three wires only — GND, TX, RX — so the loopback
> involves no board power and, under plan §4, needs no ruling. (The first version of this
> document claimed the module was fed from the board's 3.3 V, taken from a bring-up note about a
> reset-time dropout; that inference was wrong. The dropout happened, its cause is not
> established here.) Nothing here attributes anything, lifts the stop-loss or authorises B2Q.

## What the loopback is, physically

The USB-CH340 module is powered by the host's USB and reaches the Zynq's UART1 (main board
**J7**) by three wires — GND, TX, RX; its 3.3 V and 5 V pins are not connected. A self-loopback
is simply **the module's TX shorted to its own RX**:

1. unplug the TX and RX wires from **J7** — the Zynq is then not on the line at all; the board
   can stay unpowered;
2. join the two freed wire ends (TX to RX), or put a jumper across the module's TX and RX pins;
3. attach the CH340 (`1a86:7523`) to WSL with `usbipd` from Windows, and confirm the node.

No board power, no board contact: plan §4's "host-USB-powered and unplugged from the board
header" case, which needs no ruling.

Everything the tool writes on that port comes straight back on the same port. There is no
board-side software, no console, no session: a byte that does not come back byte-exact was lost
or damaged **between the host's write and the host's read** — the USB/IP path, the CH340 and
the host stack — which is exactly the isolation plan §3 wants for its A1/A2 conditions.

## The entry point

```
python3 -B host/transport_rig.py run \
    --device /dev/ebaz-uart --label loopback-notx --no-tx-during-rx \
    --out evidence/b1q/transport_stage1_physical_2026_09_13/notx
python3 -B host/transport_rig.py run \
    --device /dev/ebaz-uart --label loopback-tx --tx-during-rx \
    --out evidence/b1q/transport_stage1_physical_2026_09_13/tx
```

Defaults are the registered exposure of plan §5 — **200 repetitions or 3 600 s, whichever
first**, stop at **3 confirmed losses** in one repetition or any tool error. `--repetitions` /
`--seconds` shorten a rehearsal; a rehearsal is not the acceptance. `--pace` models the
source's wire time between frames (the driver's overlap model); on a real port the wire itself
paces, so the default is off.

What one run writes into `--out`:

| file | what |
|---|---|
| `invocation.json` | argv, parameters, the tool's provenance, and the device's **kernel identity** — resolved node, major:minor, and from sysfs the USB `idVendor:idProduct`, product string, serial. The record must show `1a86:7523`, not merely a name |
| `preflight.json` | one nonce line written and read back before any exposure; the `TIOCGICOUNT` counters around it. **Silence is a refusal (exit 3)** — the jumper is not in place or this is not the port — rather than an hour of censored frames. A garbled nonce is recorded and the run proceeds |
| `run.json` | the run record: terminal reason, `confirmed_losses` / `losses` / bounds / `loss_metric`, the received-byte denominator, per-repetition results, counters before and after and their delta, export status |
| `capture_NNN.bin`, `events_NNN.json` | the raw bytes and the timestamped reads and writes of each repetition |

Exit codes are the tool's state, not a verdict: `0` the run returned, `2` a tool error (the
evidence is still exported), `3` the preflight refused, `4` the device would not open.

## What a result can and cannot say

- The **counters** (framing, parity, overrun, break) are the measurement the three lost B1Q
  sessions never had. On a real tty they are available; on a pty they are not, and the record
  says which.
- A clean hour under both TX conditions says the WSL + usbipd + CH340 path, *by itself*, did
  not lose bytes at that exposure. It does **not** say the board's UART or the session's
  interleaving is clean, and it does not lift the stop-loss.
- Losses here reproduce the failure **without the Zynq and without the board powered**: that
  is attribution to the host path and the adapter, and stage 2's host comparison becomes the
  next question (the native Linux host exists; the owner has deferred configuring it).
- Whatever the result, if a board session is later to carry transport instrumentation, that is
  a pinned change to the runner and lands, is reviewed and is re-qualified **before** the
  session that counts.

## Offline proof of the entry point

`tests/test_transport_rig.py::TheDeviceEntryPoint` drives `main(["run", …])` against a fake
`serial` module that loops back in memory: a clean condition under each TX setting with every
file exported and the counters attempted on the fd (unavailable, with the reason); the preflight
nonce matched and drained so it never reaches the capture; silence at the preflight refusing
(exit 3) before anything is spent; `--no-preflight` turning silence into the analyser's
measured 302 confirmed losses with no denominator; a device that will not open (exit 4); a
detach mid-run (exit 2) with the evidence on disk; a two-device topology opening both and
naming them; and the registered exposure as the defaults. **No real port is opened by any
test.**

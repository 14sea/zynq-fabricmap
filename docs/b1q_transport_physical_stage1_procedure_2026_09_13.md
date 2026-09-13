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
    --device /dev/ebaz-uart --expect-usb 1a86:7523 \
    --label loopback-notx --no-tx-during-rx \
    --out evidence/b1q/transport_stage1_physical_2026_09_13/notx
python3 -B host/transport_rig.py run \
    --device /dev/ebaz-uart --expect-usb 1a86:7523 \
    --label loopback-tx --tx-during-rx \
    --out evidence/b1q/transport_stage1_physical_2026_09_13/tx
```

`--expect-usb 1a86:7523` is **where the CH340 condition is enforced**: before the port is
opened, the node's sysfs identity must read exactly that vendor:product, or the run is refused
(exit 3, `refusal: identity`) — an unavailable identity is a refusal too, never a pass. Without
the flag the tool is a generic diagnostic: the identity is recorded as metadata and nothing is
enforced (the owner's P3 of the entry-point review). `--out` must be a **fresh** directory
(new, or existing and empty); a nonempty one is refused with nothing in it touched (exit 5) —
a retry needs a new `--out`, and nothing is ever deleted to make room.

Defaults are the registered exposure of plan §5 — **200 repetitions or 3 600 s, whichever
first**, stop at **3 confirmed losses** in one repetition or any tool error. `--repetitions` /
`--seconds` shorten a rehearsal; a rehearsal is not the acceptance. `--pace` models the
source's wire time between frames (the driver's overlap model); on a real port the wire itself
paces, so the default is off.

What one run writes into `--out`:

| file | what |
|---|---|
| `invocation.json` | argv, parameters, the tool's provenance (`provenance.tool_sha256` names the exact software version), and the device's **kernel identity** — resolved node, major:minor, and from sysfs the USB `idVendor:idProduct`, product string, serial. This is the kernel's record of what was opened, **metadata, not acceptance**; with `--expect-usb` the record also carries `identity_check` (expected, matched, reason), and that check is the gate. It is created with `O_EXCL` — it is the claim on the directory |
| `preflight.json` | one nonce line written and read back before any exposure, inside one absolute deadline (`PREFLIGHT_DEADLINE_S`, 3 s) that bounds the write, the nonce wait and the quiet drain together; the `TIOCGICOUNT` counters **attempted** before and after, independently. Three named outcomes: **silence is a refusal (exit 3, `refusal: silence`)** — the jumper is not in place or this is not the port — rather than an hour of censored frames; **bytes still arriving at the deadline are a refusal (exit 3, `refusal: not_quiet`)** — the exposure must not start with a backlog; a transport exception is the preflight's **primary error (exit 2)**, recorded with the phase it struck in (`write` / `nonce` / `drain`). A garbled nonce that goes quiet is recorded and the run proceeds |
| `preflight_rx.bin` | every byte the preflight received, as received — on success, on refusal and on error; `preflight.json` carries its length and SHA-256 |
| `run.json` | the run record: terminal reason, `confirmed_losses` / `losses` / bounds / `loss_metric`, the received-byte denominator, per-repetition results, counters before and after and their delta, export status |
| `capture_NNN.bin`, `events_NNN.json` | the raw bytes and the timestamped reads and writes of each repetition |

Exit codes are the tool's state, not a verdict: `0` the run returned, `2` a tool error — in
the preflight or in the run — with the evidence that exists exported, `3` refused before any
exposure (the declared identity, or the preflight: silence / not quiet), `4` the device would
not open, `5` the evidence destination could not be claimed or written (a nonempty `--out`, or
an invocation / preflight record that could not be written) — nothing is spent on the device.
The brief on stdout names the `stage` the exit came from, lists `ports_closed` — every opened
port is closed on every return path, before the brief is printed — and any `entry_export_errors`
/ `close_errors`, which never replace the primary result.

## What a result can and cannot say

- The **counters** (framing, parity, overrun, break) are the measurement the three lost B1Q
  sessions never had. They are **attempted** on the real fd, before and after the preflight and
  the run; the record says whether the ioctl answered and, if not, why (`ch341` answers
  `ENOTTY`, so on this adapter they are unavailable). A real fd alone does not establish a
  usable counter; on a pty they are never available.
- A clean hour under both TX conditions says the WSL + usbipd + CH340 path, *by itself*, did
  not lose bytes at that exposure. It does **not** say the board's UART or the session's
  interleaving is clean, and it does not lift the stop-loss.
- Losses here reproduce the failure **without the Zynq and without the board powered**: that
  is attribution to the host path and the adapter, and stage 2's host comparison becomes the
  next question (the native Linux host exists; the owner has deferred configuring it).
- Whatever the result, if a board session is later to carry transport instrumentation, that is
  a pinned change to the runner and lands, is reviewed and is re-qualified **before** the
  session that counts.

## What happened when it ran (2026-09-13)

See `evidence/b1q/transport_stage1_physical_2026_09_13/README.md`: rehearsals clean; the
registered no-TX exposure clean over 10.1 MB; the TX-during-RX condition, at a declared 20
repetitions, produced one confirmed loss — two byte deletions inside one read. The counters are
unavailable on this adapter (`ch341` answers `ENOTTY`).

Those acquisitions were made with the tool as reviewed — `819117c`, `tool_sha256`
`aaff46e90422bf242b632fa68000eb649f5077afde98d9cd624aae58d1d630ee` in each `invocation.json` —
**before** the entry-point corrections below; they are not rewritten and their own evidence
review is still open. Any new acquisition names the tool it used the same way.

## The entry-point review and its corrections (2026-09-13)

`docs/b1q_transport_entrypoint_review_2026_09_13.md` (as received) held the entry point on
three P2s; each is corrected in `host/transport_rig.py` and reproduced-then-proved from the
real CLI in `tests/test_transport_rig.py::TheDeviceEntryPoint`:

- **P2-1** the preflight's drain had no absolute bound — a line that kept producing bytes kept it
  alive indefinitely, before `Run` had started its clock. Now one deadline bounds write, nonce
  and drain; every read is capped by the remaining budget; expiry with bytes still arriving is
  the named refusal `not_quiet`, with the bytes kept and no exposure started.
- **P2-2** the preflight ran outside any guard: a read that raised after the nonce escaped as a
  traceback, leaving only `invocation.json`. Now the preflight has its own guarded boundary —
  the nonce as sent, everything received, timing, the primary error and its phase, and both
  counter attempts survive success and failure; `preflight.json` and `preflight_rx.bin` are
  exported independently; a secondary export failure is listed, never substituted for the
  primary error; every opened port is closed on every return path.
- **P2-3** an existing `--out` was overwritten in place, leaving a mixture of two acquisitions
  reported complete. Now the destination is claimed fresh and atomically (`O_EXCL` on
  `invocation.json`) before any port opens; a nonempty directory is refused byte-untouched.
- **P3** the identity is metadata; `--expect-usb` is the gate, and the counters are "attempted",
  as written above.

## Offline proof of the entry point

`tests/test_transport_rig.py::TheDeviceEntryPoint` drives `main(["run", …])` against a fake
`serial` module that loops back in memory: a clean condition under each TX setting with every
file exported and the counters attempted on the fd (unavailable, with the reason); the preflight
nonce matched and drained so it never reaches the capture; silence at the preflight refusing
(exit 3) before anything is spent; `--no-preflight` turning silence into the analyser's
measured 302 confirmed losses with no denominator; a device that will not open (exit 4); a
detach mid-run (exit 2) with the evidence on disk; a two-device topology opening both and
naming them; and the registered exposure as the defaults. After the entry-point review: a line
that never goes quiet refused at the deadline with its bytes kept, and a late nonce still
passing; a detach after the nonce, a write fault and a faulted `preflight.json` export, each
with the primary error kept and the other files on disk; a passed preflight that could not be
recorded spending nothing (exit 5); a nonempty destination refused byte-identical with the
opener never called, a fresh one created, a stale-empty race losing at `O_EXCL`; `--expect-usb`
refusing an unavailable or different identity before opening and passing the declared one;
and every opened port closed on every path, the first closed when the second will not open.
**No real port is opened by any test.**

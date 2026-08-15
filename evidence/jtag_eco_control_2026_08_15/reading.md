# Phase 1: does a JTAG readback reproduce a bitstream we already know?

The carrier's own readback is the thing under suspicion, so it cannot be its own witness.
Before spending an irreplaceable post-fault state on an independent readback, the readback
itself is calibrated against a bitstream whose content is known exactly.

`carrier_eco.bit` (`78eff0cb…`, published and gate-accepted) is `carrier.bit` with three
INIT bits of one LUT set. The local map places them at `0x00400A20` word 51 bits 15 and 7,
and `0x00400A21` word 51 bit 6. All three are **0** in `carrier.bit`, so finding them is
discriminating rather than a restatement of the all-zero floor that has defeated every
earlier measurement on this line.

## What was run

Fresh power-on precheck, then `fpga loadb` of `carrier_eco.bit` onto an empty PL
(`INT_STS 0x50021004`, `PCFG_DONE=1`, plmark `18cbfeacd7296aa9`). Then
`scripts/probe_jtag_config_read.py` over the FT4232H, driving the PL TAP directly:

```
IDCODE → CFG_IN(read STAT) → CFG_OUT → CFG_IN(RCRC) → JSHUTDOWN → RTI 12 TCK
→ per FAR: CFG_IN(RCFG, FAR, FDRO type-1, type-2 count 202, 32 NOOP) → CFG_OUT(202 words)
→ CFG_IN(DESYNC)
```

The allowed set is enforced in code: `check_sequence()` refuses an FDRI write, a WCFG/MFW/
IPROG command and any type-2 write before a bit is shifted, and the generated script only
ever issues IR `0x09/0x05/0x04/0x0d`. `JPROGRAM (0x0b)` and `JSTART (0x0c)` are named only
as things that must not appear, and a test asserts they do not.

## Result: the method works, and it is not yet reliable twice in a row

| | |
|---|---|
| IDCODE | `0x13722093` |
| CONFIG_STATUS | `0x46107ffc` |
| `0x00400A20` | **101 of 101 words identical to `carrier_eco.bit`**, ECC consistent, both expected bits present at their exact positions |
| `0x00400A21` | all zero — differs from the expected frame in words 50 and 51, i.e. the ECO bit and its ECC are absent |

The A20 result is not a coincidence available to a zero window: the frame carries two bits
that are set in the loaded bitstream and clear in the base, and the whole 101-word frame
matches. **A JTAG readback of a configured device can reproduce known content on this
board.** The declared alignment — first 101 words are the pad frame, second 101 are the
requested frame — is confirmed by that match, and it is the same convention the carrier's
own RTL uses (`rb_skip = rb_lat + SKIP_FRAME`).

The A21 result is a miss, and the most economical explanation is the one this repository has
already paid for once: **each FAR-set needs its own `sync … DESYNC` envelope.** The script
issued one sync at the start of each read but only one DESYNC at the very end, so the second
read continued inside the first envelope. `zynq-xpart` recorded the same rule for ICAP.
That is a hypothesis about the script, not a measurement — it has not been tested.

## What this does and does not license

* It licenses the *method*, for one read per envelope, against a device configured and then
  shut down with `JSHUTDOWN`.
* It does not license the two-reads-per-session shape that produced the A21 miss.
* It says nothing yet about the open question — whether the carrier's pass-2 write lands at
  the requested FAR — because that needs a post-fault state, and the previous one was lost
  to a power cycle.

Stopped here per the authorisation: the read is done, nothing further was run, and the board
is to be power-cycled before anything else. No `known-answer` round was started.

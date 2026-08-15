# Phase 1, reversed order: the failure is positional, not addressed

Same board, same `carrier_eco.bit` (`78eff0cb…`), same per-FAR `SYNC → RCFG → FAR → FDRO →
CFG_OUT → DESYNC` shape, one `JSHUTDOWN` per session, fresh boot (plmark
`18cc00f0fa537908`). The only change is the order: **A21 first, then A20.**

## The result

| position | FAR | outcome |
|---|---|---|
| first | `0x00400A21` | **101 of 101 words identical to `carrier_eco.bit`**, ECC consistent, `INIT[35]` present at w51 b6 |
| second | `0x00400A20` | all 202 words zero — both of its bits absent |

Against the previous run, which read them the other way round:

```
run B (A20 → A21)   #1 0x00400A20  frame 02fc3959…  2 non-zero words
                    #2 0x00400A21  frame 0441772f…  0 non-zero words
run C (A21 → A20)   #1 0x00400A21  frame f39553be…  2 non-zero words
                    #2 0x00400A20  frame 0441772f…  0 non-zero words
```

**Whichever frame is read first comes back exactly. Whichever is read second comes back
all zero**, pad frame included. This is positional, and it settles the question the previous
round could not: A21 is not a special address, and the second read of a session is not
trustworthy.

> **Correction, 2026-08-15 (a boundary this file first overstated).** An earlier wording here
> said the second read "returns nothing". All 202 words being zero establishes only that
> **the expected frame was not obtained**. It does not distinguish that from a command that
> did not take effect followed by a read of some all-zero frame — 4,716 of the device's 5,144
> frames are all-zero, so an all-zero window names no address and licenses no claim about
> what the interface did. The positional conclusion is unaffected: it rests on the *first*
> read being exact in both orders, which is a discriminating observation, not on any reading
> of the zeros.

## Two things this establishes beyond the defect

**The local map is now confirmed on silicon for all three ECO bits.** `INIT[0]` and
`INIT[32]` at `0x00400A20` w51 b15/b7 (runs A and B, A20 read first) and `INIT[35]` at
`0x00400A21` w51 b6 (this run, A21 read first) — each at its exact predicted position, each
clear in the base bitstream, each present in the ECO'd one. The offline localisation of
`INIT[35]` was already strong from the raw configuration stream and prjxray's `33_06` rule;
it is now a hardware observation as well. Nothing in the map or the parser needs changing.

**A single JTAG readback per session is a trustworthy instrument.** Three sessions, three
first reads, three exact 101-word matches.

## What it does not license, and the experiment that would

A multi-FAR readback — the thing a signature search across frames would need — is **not**
available. Phase 1's success condition asked for both frames in one session, and this run
does not meet it either, in the other direction.

The next question is what "session" means to the device: the OpenOCD connection, or the
`JSHUTDOWN`, or the first `CFG_OUT` after it. The cheap experiment is to read A20 and A21 in
**two separate OpenOCD invocations** against one loaded bitstream, without reloading between
them. If both come back exact, multi-FAR reading is available at the cost of one process per
frame, which is seconds, and the signature search is affordable after all. It was not run:
this round's authorisation ends at the read.

Phase 2 stays unauthorised.

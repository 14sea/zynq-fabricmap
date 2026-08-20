# The failing frame's DDR copy is all zero — and that now means something it could not mean before

A single authorised read, taken in the same boot as the fault and step ④, before any power
cycle. `probe_ddr_capture.py` touches no carrier register: `echo`, `printenv plmark`, one
`md.l 0x10100000 0x65`. No acknowledgement, no retry, no second slot, no JTAG.

```
capture     101 words, 0 non-zero, all_zero = true
            sha256 0441772f66559a1c71f4559dc4405438fc9b8383ce1229139257a7fe6d7b8de9
analysis    UNDISCRIMINATING — an all-zero window matches 474,494 word offsets of the device
            stream and is invariant under bit-swap and word-alignment variants
comparisons equals_base_frame_at_requested_far = true
            equals_expected_candidate_frame    = false
expected    the candidate differs from the base at words 50 and 51 only
```

## What the analyser could not decide, and what decides it

`analyse_ddr_capture.py` states its own limit exactly: an all-zero window "cannot distinguish
a pass-2 write that never landed from a read that reached a different, also-zero frame", and
it says why — it has no post-write image of the device, only the base bitstream.

**Step ④ is that missing image.** In this same boot, after this same fault, an independent
path (JTAG, R4 recovery, sixteen positive controls exact in the same acquisition) read
`0x00400A20` and found **the candidate frame, bit-for-bit, words 50 and 51 included**.

So for **this transaction** the first horn is eliminated: the write landed. What remains is
the second — **the engine's pass-2 readback delivered a zero frame into staging slot 0 while
the frame it was supposed to be reading held the candidate.** The staging copy is not a
picture of the fabric; it is a picture of what the readback path handed over.

## What this still does not say

* **It names no address.** An all-zero window matches 474,494 offsets, so it cannot say
  *which* frame was read — only that what arrived was not what `0x00400A20` contains.
* **It is one observation**, in one boot, of one transaction. The location itself still needs
  independent reproduction under the same frozen identity.
* **It does not identify a mechanism.** `RB_SKIP`, readback latency and FDRO framing are the
  natural suspects for "a zero frame arrived instead of the addressed one", and none of them
  is examined here.

## One thing that must not be used as support

Phase 2's real-frame non-zero distribution — 0 words × 3, 10 × 4, 101 × 9 — was taken with
the **invalidated JTAG instrument** (`board_signature_search.py/2.1.0`, child `2.0.0`,
pre-R4). It explains why Phase 2's own verdict is void and nothing else. It is **not**
evidence about this ICAP read-side question, and this reading does not lean on it.

## State

Read-only. The board is still in the post-fault state and may now be powered down; the DDR
copy has been taken and committed, and R4's JTAG reads never disturbed it.

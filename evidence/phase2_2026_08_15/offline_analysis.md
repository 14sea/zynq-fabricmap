# Phase 2 offline analysis: the mask, the alignment, and what the readback actually is

Two questions, deliberately answered apart. A mask hides bits it names; if the readback were
misaddressed, masking would only make the numbers smaller without making them mean anything.
So neither report is allowed to stand in for the other.

Nothing here touched the board or changed a production verdict. The board is still in the
post-fault state it was left in.

## Report 1 — the mask does not account for it

`mask_analysis.json`. Masks exist upstream only for CLB tiles, so 3,560 of the 5,144 frames
have no mask at all; that limit is part of the answer rather than a footnote.

| | |
|---|---|
| differing bits, unmasked | 10,367,215 |
| differing bits, masked | 7,143,064 (−31%) |
| frames equal, unmasked | 771 |
| frames equal, masked | 882 |
| **frames equal AND non-zero in the base** | **0, before and after** |

Masking removes bits and creates no positive control. Not one frame whose base content is
non-zero becomes equal to its readback once the bits prjxray names as dynamic are excluded.

## Report 2 — it is not the same data displaced either

`alignment_analysis.json`. 420 base frames are non-zero and unique in the device stream, so
finding one anywhere in the readback would be an address rather than a coincidence. 24 were
probed against the whole 519,544-word readback stream under five transforms — identity,
32-bit bit-reversal, byte swap, per-byte bit reversal, and byte swap then bit reversal:

```
identity                   0/24        byte_bit_reverse            0/24
word_bit_reverse           0/24        byte_swap_then_bit_reverse  0/24
byte_swap                  0/24
```

None appears, at any offset, under any transform. And of the 519,544 words, 119,388 are equal
in place — **2 of them non-zero**.

## What the readback is, as far as this can say

A configuration frame carries a computed ECC, and the check is cheap:

| | frames | ECC-consistent |
|---|---|---|
| base bitstream | 5,144 | **5,144 (100%)** |
| readback, all-zero frames | 852 | 852 — trivially, zero satisfies it |
| readback, non-zero frames | 4,292 | **82 (1.9%)** |

So the readback is not returning configuration frames from somewhere else on the device: 98%
of its non-zero frames do not satisfy the invariant every real frame satisfies. It is not the
bitstream masked, not the bitstream moved, and mostly not frame-shaped.

## What follows, and what does not

* The acquisition stands: 5,144 of 5,144 frames, 0 missing, bookkeeping and closure valid,
  archived and re-verified.
* `NOT_FOUND_COMPLETE` remains void, and now for a sharper reason than "no positive control":
  in this state the instrument does not return configuration data at all, so the search had
  nothing to find the signature *in*.
* This says nothing about whether the candidate was written. All three possibilities the
  ruling named — never written, written elsewhere, readback mapping broken — remain open, and
  this analysis narrows the third rather than eliminating the others.
* Phase 1 stands unchanged and so does its scope: on a freshly loaded, JSHUTDOWN'd device
  whose design had never run a transaction, the same tool reproduced frames bit-exactly. The
  difference between that state and this one is that here the carrier ran, drove ICAP, and
  faulted.

The obvious next question is whether a post-fault device can be read at all by this path —
which is a positive control in a post-fault state, and a production change, and therefore not
this round's to make.

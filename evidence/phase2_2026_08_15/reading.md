# Phase 2: the sweep completed, and its verdict does not mean what it says

## What ran

Fresh power-on precheck (read-only, all four registers at their reference values,
`PCFG_DONE=0`). Then one known-answer round on the canonical erratum-006 carrier
(`8c3369e8…`), which reproduced the now-familiar result exactly: `no_op` passed, and
`known_answer` stopped at `F_READBACK` in pass 2 of envelope 0. 353 console commands, no
reboots, a prompt every time, `same_boot` verified. Restore, arm and scoring never ran —
the chain stops at step 2, and the arm is structurally unreachable without a digest match.

That left a fresh post-fault state, marker `18cc061a7180f194`. In the same boot, the audited
signature search read `0x00400A20` first, decided, and then swept.

| | |
|---|---|
| intended frame `0x00400A20` | **all zero — equal to the base, not to the candidate** (`INTENDED_FAR_HOLDS_THE_BASE`) |
| sweep | **5,144 of 5,144 frames read, 0 missing**, every entry `ok`, plmark identical at start and end |
| signature hits | none, for any of the four candidate frames |
| cost | **median 0.061 s per child**, 5.2 minutes of child time for the whole device |
| tool verdict | `NOT_FOUND_COMPLETE` |

## Why that verdict is void

The verdict string says the write did not reach the fabric as a whole frame anywhere. It is
not entitled to say that, and the reason is in the captures themselves.

Comparing every capture against the frame the loaded bitstream holds at the same FAR
(`readback_vs_bitstream.json`):

```
matches, both all zero (the zero floor)      771
matches, non-zero (discriminating)             0     <-- not one
base non-zero -> readback all zero            81
base all zero -> readback non-zero          3945
both non-zero, differing                     347
```

**Not one known non-zero frame was reproduced.** The differences are not a handful of
dynamic bits either: all 101 word positions differ, in between 3,878 and 4,299 of the 4,373
mismatching frames each — spread evenly across the frame rather than concentrated where
capture data would sit.

So in this state the instrument does not reproduce the configuration it was given. A search
that looks for four specific non-zero frames by whole-frame equality, in a state where
whole-frame equality fails for **every** frame whose content is known, returns "not found"
whether or not the signature is there. The sweep's coverage is complete and its bookkeeping
is sound; the comparison underneath it is not answering the question.

## What this does not overturn

Phase 1's control stands, and it is worth being precise about what it covered: a freshly
loaded `carrier_eco.bit`, `JSHUTDOWN`, and a first read per process reproduced
`0x00400A20` and `0x00400A21` **bit-exactly**, including bits set in the ECO and clear in the
base. That licensed the method **for that state** — a device configured and shut down, whose
design had never run a transaction. This is a different state: the carrier ran, drove ICAP,
and faulted. Nothing here says the Phase 1 result was wrong; it says it was not a licence for
this.

## What would make the sweep mean something

A positive control **in this state**, of the same shape as Phase 1's: a frame whose content
is known and non-zero must read back exactly, here, after a fault. Until one does, no
whole-frame comparison in a post-fault state carries information.

If the cause is readback capture returning dynamic cell state rather than configuration,
prjxray's mask files (`data/prjxray/zynq7/mask_*.db`, already frozen in this repo) name the
bits that are not expected to survive, and the comparison would have to exclude them —
reported, as ever, rather than applied silently. If the cause is an addressing or alignment
difference in this state, masking will not rescue it and the offset has to be measured first.

Either way that is a change to production code, so this round stops here, as ruled.

## State

The board is still in the post-fault state, powered, and has not been touched since the
sweep — which was read-only JTAG throughout. No restore, no reload, no new transaction, no
arm, no scoring. The 5,140 sweep captures that are not committed here are 124 MB on disk;
committing them into a public repository is a permanent weight decision and is left to the
user rather than taken by default.

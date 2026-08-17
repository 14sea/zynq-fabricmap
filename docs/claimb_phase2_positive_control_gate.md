# Claim B Phase 2: fail-closed post-fault positive-control gate

Status: implemented offline on 2026-08-15; not run on a board in this change.

## Why the Phase 2 location verdict is void

The historical Phase 2 acquisition is complete as an acquisition: 5,144 children exited
successfully, every capture and child log validates, no FAR is missing, and the boot marker
matches at both ends. Its `NOT_FOUND_COMPLETE` location verdict is nevertheless void.

In that post-fault state, not one known non-zero base frame came back bit-exact at its own
FAR. Of 4,292 non-zero captured frames only 82 were ECC-consistent, while the loaded base is
ECC-consistent in all 5,144 frames. Masking the prjxray-named dynamic bits produced no
non-zero same-FAR match, and searching 24 unique non-zero base frames under five word/byte
transformations found none anywhere in the captured stream. The instrument therefore did
not establish that its captures were configuration frames. A complete search over invalid
measurements cannot locate or exclude a signature.

The immutable evidence and the sharper offline analysis remain in
`evidence/phase2_2026_08_15/`. This document changes no historical evidence and does not
reclassify the three still-open mechanisms: the write may not have landed, it may have
landed elsewhere, or the post-fault readback mapping may have failed.

## What now counts as a positive control

A control passes only when all 101 captured words equal the known, non-zero base frame at
the same FAR. The following do **not** pass:

* merely non-zero data;
* a frame with a self-consistent ECC word;
* a partial, masked, transformed, or relocated match;
* an all-zero frame, even when zero is the expected content at many FARs.

The production search derives eligible controls from the authority bitstream, then requires
all of these properties:

1. the base frame is non-zero;
2. its complete 101-word content occurs at exactly one FAR in that bitstream;
3. it is outside all 15 frames named by the phenotype manifest;
4. sixteen evenly distributed eligible ranks reproduce a source-pinned FAR list.

Sixteen is intentional. The transaction presents fifteen frame writes. If a fault can spoil
at most one distinct control per write, at least one of sixteen remains available. If the
fault is broader, all controls may fail and the instrument refuses; that false refusal is the
safe outcome. The assumption is used only to improve the chance of obtaining a control, not
to turn a failed control into evidence.

The pinned FARs are:

```
00000900 00000986 000009a2 00000a8e
00000b8a 00000c04 00000d04 00400915
00400996 00400a10 00400b05 00400b91
00400c0a 00400c8e 00401101 0040139b
```

The derivation is rerun before use. A different result is a refusal requiring review and a
new pin, not an automatic substitution.

## Verdict ordering

The intended FAR remains the first child. If its complete frame equals the non-zero
candidate, the search returns `WRITE_LANDED_AT_THE_INTENDED_FAR` immediately: that
observation is itself the exact object being located, and further JTAG reads only risk the
state.

Every other path reads controls in pinned order until one exact match is obtained or all
sixteen fail:

* one exact control permits the already-observed third state or the location sweep to be
  interpreted;
* all sixteen attempted with no exact match yields `INSTRUMENT_INVALID` and no sweep;
* a read budget or interrupted run that leaves controls unattempted yields
  `INSTRUMENT_UNVALIDATED`, never `INSTRUMENT_INVALID` and never a location verdict.

`judge_sweep()` independently repeats the control gate, so a caller cannot bypass the live
ordering and manufacture `NOT_FOUND_COMPLETE` from captures alone. Live, resumed, and
judge-only paths also pin the control FAR list in the index and include the changed tool
source/version in the instrument digest.

## Verification boundary

Offline tests exercise exact success, non-zero wrong controls, incomplete controls, the
third-state bypass, resume/index validation, and a direct `judge_sweep()` bypass. Three new
behavioral mutants remove those protections and must all be killed.

This change does not touch the board, restore the lost Phase 2 state, or prove that any selected
control remains static after a real post-fault transaction. A future hardware run may
therefore fail closed. That result would validate the gate's refusal, not the underlying
JTAG readback method.

## Addendum 2026-08-17 — the threshold this document set is superseded by 16/16

Kept as written above, because it is the design the four R4 acquisitions were taken under and
because the reasoning is what got reviewed. Two of its rules no longer describe the tool:

* **"one exact control permits ... the location sweep to be interpreted"** and the immediate
  `WRITE_LANDED_AT_THE_INTENDED_FAR` return are both gone. From
  `board_signature_search.py/2.8.0`, **all sixteen controls are read in every case and all
  sixteen must match before any location verdict is emitted, the intended hit included.**
  See `claimb_location_sweep_spec.md` for the ruling and the four mutants that hold it.
* The "sixteen is intentional" paragraph justified sixteen as *redundancy* — fifteen writes can
  spoil at most fifteen controls, so one survivor suffices. Under 16/16 the same sixteen frames
  are justified differently: they are the set R4 is demonstrated on, twice, at 16/16, so the
  threshold is the recovery's measured behaviour rather than an argument about how a fault might
  distribute. Anything less now fails the acquisition closed.

What did not change: the eligibility derivation, the pinned FAR list, the re-derivation before
use, `judge_sweep()`'s independent repetition of the gate, and the treatment of unread controls
as `INSTRUMENT_UNVALIDATED` rather than as failures.

One consequence is worth stating where the threshold is documented: if the write landed *on* a
control frame, that control cannot reproduce its base, so the acquisition fails closed and
locates nothing. The per-control observations still record expected and observed digests, so
the state is visible in the record; it is not adjudicated by the tool.

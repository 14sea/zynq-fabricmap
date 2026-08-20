# This directory's `verdict.json` is superseded — read `NOT_FOUND_COMPLETE` as void

`verdict.json` is kept **exactly as the tool wrote it on 2026-08-15**, including the string
`NOT_FOUND_COMPLETE` and its `reading` field. It is historical evidence: what
`board_signature_search.py/2.1.0` at `instrument_digest 0caf4a36…` actually emitted in that state.
It is not to be edited, and this file does not edit it. Ruled 2026-08-20; the correction is
additive, here and in `../reading.md`.

## Why the verdict is void

The sixteen positive controls of this acquisition — the same sixteen FARs pinned in
`board_signature_search.py` as `EXPECTED_POSITIVE_CONTROL_FARS`, all of them known-non-zero,
device-unique base frames outside the transaction — are **committed in this directory**, and
they read **0 of 16**.

Recomputed offline on 2026-08-20 from the committed captures alone (no board), by comparing
each capture against the frame the canonical `carrier.bit` holds at the same FAR:

```
exact whole-frame matches, controls:   0 / 16
  on capture words[0:101]              0 / 16
  on capture words[101:202]            0 / 16     (the read is 202 words, pad_frames = 1;
                                                   neither alignment matches)
expected non-zero words per control:   48, 66, 71, 46, 84, 14, 2, 82, 57, 3, 13, 55, 30, 14, 2, 3
observed non-zero words, words[0:101]: 0 in every one of the sixteen
```

That is consistent with, and sharper than, the aggregate already recorded in
`../readback_vs_bitstream.json`: **`matches_non_zero_discriminating = 0`** across all 5,144
frames. In a state where whole-frame equality fails for every frame whose content is known, a
search that looks for four specific non-zero frames *by whole-frame equality* returns "not
found" whether or not the signature is present. The coverage was complete; the comparison
underneath it carried no information.

## What is *not* being retracted

* 5,144 of 5,144 frames read, **0 missing**, every entry `ok`.
* `plmark 18cc061a7180f194` identical at start and end; no reboot, read-only JTAG throughout.
* `elapsed_s = 408.2` — the sweep's real wall clock, and evidence that a full-device sweep is
  cheap.

The bookkeeping stands. Only the location verdict is void.

## What has changed since, and what it means for this record

* The child was **`probe_jtag_config_read.py/2.0.0`**, which predates R4. The post-fault
  readback defect this acquisition ran into was diagnosed afterwards and R4
  (`…/2.4.0`) recovers it — demonstrated 16/16 on a post-fault state, twice, across two
  independently built faults. See `docs/claimb_readback_recovery_study.md` and
  `docs/claimb_postfault_r4_spec.md`.
* The parent is now **`board_signature_search.py/2.8.0`**, which requires **16/16 controls
  before any location verdict, the intended hit included**. Stated precisely, because the
  loose version of it is wrong: **2.8.0 cannot re-judge this acquisition at all** — it
  refuses it on tool version and `instrument_digest` before any control is examined. What is
  true is the counterfactual: **had this same 0/16 control observation been taken under the
  2.8.0 identity, the acquisition would be `INSTRUMENT_INVALID` and would emit no location
  verdict at all.** See `docs/claimb_location_sweep_spec.md` and the 2026-08-17 addendum in
  `docs/claimb_phase2_positive_control_gate.md`.
* This acquisition's identity is **dead** and cannot serve as a control for anything current:
  parent **`board_signature_search.py/2.1.0`** (the value in this directory's `index.json`,
  not a later one), child `probe_jtag_config_read.py/2.0.0`, digest `0caf4a36…`.

## Where the real answer is expected to come from

`docs/claimb_location_sweep_spec.md`, steps ①–⑤: a fresh-load full acquisition as the negative
control, a power cycle, the specified fault, one acquisition in that same boot, and an
instrument comparison before the verdict is looked at. That procedure is what makes a
"not found" mean something — because its controls have to pass **in the same acquisition that
reports it**, which is exactly what this one could not do.

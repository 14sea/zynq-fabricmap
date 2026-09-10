# Corrections after the owner's third review (2026-09-10)

`remaining_after.json` is the output of the owner's own reproducer,
`evidence/b2/review_v021_2026_09_10/reproduce_remaining.py`, run UNCHANGED against the
corrected code. Only the three legitimate baselines are accepted
(`baseline_S2_real_fixture_bytes`, `baseline_S3`, `baseline_copied_plan_and_prediction`);
all seventeen other cases are refused with a named field:

* the image binary replaced with the same number of different bytes, or deleted, is
  refused because `verify()` now opens, hashes and sizes the binary itself;
* every plan and prediction mutation of the review's table is refused by the canonical
  rebuild, which names the differing path (for example `plan primary.alpha: 1.0 != 0.05`
  or `prediction pairs[0].delta_B_minus_A: -999 != 2`);
* the manifest pointing at an unrelated prediction document is refused because the
  manifest's reference and the plan's sidecar must name the same bytes.

The second review's twenty cases still behave as recorded, with one fixture change: the
old reproducer declared an image path without ever creating the binary, so its baseline
could not exercise the new check. `../corrections_v02_2026_09_10/reproduce_lifecycle_patched.py`
now writes a real fixture binary; `lifecycle_after.json` there is its current output
(three baselines accepted, twelve mutations refused, 100 records/hour INFEASIBLE, four
invalid rates raising `RateInvalid`).

Neither reproducer builds an image, issues a ruling or touches a board. The fixture bytes
are arbitrary data, not firmware.

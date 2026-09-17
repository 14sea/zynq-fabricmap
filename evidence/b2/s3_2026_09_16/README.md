# B2 lifecycle 2 — S3 plan — 2026-09-16

The owner accepted step 11 (the S2 clean-tree proof, `test_report_2026-09-16T204304Z.json`) and
explicitly authorised §8a step 12. In order, once each: the plan regenerated from the S2
calibration (`b2_plan.py --out evidence/b2 --rate-per-hour 3016.3995578641097`), the prediction
bytes confirmed unchanged, then `bm.pin_plan` in Python with `readjudicate=rn.readjudicator(m)`
at 2026-09-16T20:47:34Z on the S2 manifest `3415e290…`.

- S3 manifest SHA-256: `aec84514ff29dda7957d46d650a370e155f6dc60a281b992e148f8a0fae6c4c0`
  — **the B2 ruling pairs bind to this value**
- Plan SHA-256: `62dc85934eec02e2fe31a90b336d0fd320d03a4f54bf90537e944ece72458b9c`
- Prediction SHA-256: `a611b8e03c88fa797e2b9d9c5d10bb97e42c590bc8754f1defccc6c11c9e3731` (unchanged)
- Split: DETERMINED at 3016.3995578641097 evals/h — session 1 pairs 0–4, 6012 records; session 2
  pairs 5–8, 4810 records; total 10822
- Preregistration `fa401221…`, pin table `82a5f2fb…`, image `d164cd1d…` unchanged

Production `verify` with the production re-adjudicator passes before (S2) and after (S3) in fresh
processes. The transition changed exactly `plan`, `status` and `history` (`transition.json`,
from the bytes). The stage-aware committed-plan test (`tests/test_b2_plan.py`, the lifecycle-2
correction) passes on this tree: DETERMINED, bytes equal to the pin, sessions and total equal.

`transition.json` records the actual resulting binding; no preview hash is a binding. Not done
here: the final clean-tree proof (§8a step 13), B2 ruling pairs (step 14), push, board.

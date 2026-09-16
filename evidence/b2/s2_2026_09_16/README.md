# B2 lifecycle 2 — S2 qualify — 2026-09-16

The owner reviewed the B2Q evidence (`evidence/b2/b2q_17A6_2026-09-16-01`, PASS, re-adjudicated
from the raw files by the production re-adjudicator) and explicitly authorised §8a step 10. The
production `bm.qualify` ran once, in Python with `readjudicate=rn.readjudicator(m)` (the CLI
deliberately carries no re-adjudicator), at 2026-09-16T20:27:42Z on the S1 manifest `90115453…`.

- S2 manifest SHA-256: `3415e290444959f3b9409569de52140ac923aaa2779d537e56098210e30c9bb2`
- Calibration: **3016.3995578641097 evals/h**, all-self-reporting, reconstructed from the B2Q
  adjudication; the split rule gives **2 sessions, at most 5 pairs per session**
- Preregistration `fa401221…`, pin table `82a5f2fb…`, image `d164cd1d…` unchanged; plan null

Production `verify` with the production re-adjudicator passes before (S1) and after (S2) in fresh
processes (`verify_before.json`, `verify_after.json`). The transition changed exactly the five
licensed top-level fields — `qualification`, `qualified`, `calibration`, `status`, `history`
(`transition.json`, computed from the bytes). The lifecycle-1 rate 2976.98/h was not an input.

`transition.json` records the actual resulting binding; the owner's in-memory preview hash is
not a binding. Not done here: the S2 clean-tree proof (§8a step 11), S3 (step 12), push, board.

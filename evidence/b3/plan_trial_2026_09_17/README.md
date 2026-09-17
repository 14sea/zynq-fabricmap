# B3 plan trial — 2026-09-17 — the stop rule triggered

`b3/host/b3_plan.py` run once, without a rate, against the committed gate run 1
(`evidence/b3/gate/gate_report.json` `477225f5…`): the nine session pairs drawn by the frozen rule
(`b3-session` ‖ instrument commit, master 1 273 858 430, 1 646 excluded values including the gate's
own 200 pairs) and the reference prediction at F1 / 1 000 in the prefix-balanced arm order.

| | Δ per pair (0..8) | positives / negatives / ties | p (one-sided exact sign test) | verdict |
|---|---|---|---|---|
| primary 1, Δ1 = O − R | 9, 5, 4, 5, 8, 4, 2, 6, 4 | 9 / 0 / 0 | 0.001953125 | SUPPORTED |
| primary 2, Δ2 = O − end-to-end F | 4, 0, −1, 3, 3, 2, −1, 3, −2 | 5 / 3 / 1 | 0.36328125 | **NOT SUPPORTED** |

Preregistration DRAFT v0.2 §1: "the two predicted primaries on the fixed board seeds must meet
p ≤ 0.05 in the prediction; if either does not, the line stops — the seeds are not redrawn and N
is not raised". Primary 2 does not. This directory is that finding, kept as it came out; nothing
here is the committed plan (`evidence/b3/plan.json` is not written) and nothing downstream was
started. The decision is the owner's.

What the numbers say, for that decision (not a proposal): the gate sized N on Δ1 alone (H5:
N(B*) = 9 by bootstrap power for Δ1); at B* = 1 000 over the 200 gate seeds Δ2 was positive in
125 / 49 / 26, i.e. P(Δ2 > 0 | not tied) ≈ 0.72, for which the exact sign test at N = 9 has power
well below 0.9 — H9 (significant over S = 200) says the population effect is real, N = 9 says nine
pairs are too few to show it. The prediction is exact and the seeds are fixed; every O-arm map in
the trial decoded ≥ 286 / 292 with 0 wrong decodes and 0 anomalies.

Files: `plan.json` (rate-less, UNDETERMINED split), `prediction.json` (the trial prediction; the
27 027-value fitness sequence hashed), both as `b3_plan.py --out` wrote them.

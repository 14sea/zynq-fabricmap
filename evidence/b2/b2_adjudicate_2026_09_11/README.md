# b2_adjudicate — the host tool and its end-to-end demonstration, 2026-09-11

`host/b2_adjudicate.py` is host tool 2 of the five §7 asks: it consumes a run's session logs
in session order and, for every record, recomputes the fitness **from the readout the record
served** and replays the search the board reported.

## What is here

- `modelled_run.py` — builds a modelled B2 run at the REAL pinned plan
  (`evidence/b2/plan.json`: F1, budget 600, 9 pairs) in the plan's three-session shape
  (4 + 4 + 1 pairs, 10 824 records) and gives every record the readout the fabric model
  would have measured for its genome.
- `full_run_result.json` — that run adjudicated against the pinned
  `evidence/b2/prediction.json`: **PASS**, 10 824 readouts served, 10 818 records replayed,
  per-pair deltas `[2, 5, 6, 3, 4, 6, 1, −2, 5]`, fitness sequence
  `0b81b34369b73ebc…` over 10 818 values, primary p = 0.01953125 — each of them EQUAL to the
  preregistered value. 18 s.
- `tampered_readout_result.json` — the same run with **one 64-bit readout word of one record**
  (session 1, seq 2004) flipped, nothing else touched: **KILL**, naming both the PL's additive
  known answer and the F1 recomputation for that one record, plus the replay divergence, and
  claiming no primary.

## What this is NOT

**The model is standing in for a board.** These files demonstrate the tool against the
preregistered prediction; they are not a board result, not a session, and not evidence about
the silicon. No board was contacted and no image was built. The adjudicator itself never
produces a readout — `tests/test_b2_adjudicate.py` makes the fabric model raise on use and the
same run still adjudicates, while the tampered-readout cases show the recomputation is real.

The layers this tool deliberately does not check — the manifest pins, the carrier's
qualification chain, the instrument's rate/deadline/CRC budgets, the evidence exports and the
ruling binding — are listed in its own result under `not_checked_here`, and are the runner's
and `b2_pins`' work.

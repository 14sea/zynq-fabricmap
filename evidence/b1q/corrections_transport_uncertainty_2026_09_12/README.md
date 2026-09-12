# The loss metric's uncertainty — corrected, 2026-09-12

The owner's review: `docs/b1q_transport_uncertainty_review_2026_09_12.md`, against `328e9c1`,
with its probe in `evidence/b1q/review_transport_uncertainty_2026_09_12/`. It accepted the three
boundary corrections and the `exposure_reached` / `completed_exposure` distinction, and named one
P2 in what that round had added: `unresolved` frames were subtracted from `losses`, so an
uninterpretable capture reported the same unqualified `losses_per_100k_bytes: 0.0` as an intact
frame. `acceptance.py` runs the owner's four fixture shapes unchanged through a production `Run`,
adds the mixed confirmed-then-unresolved regression the review requests, and asserts every case on
the returned result **and** the persisted `run.json`; `acceptance.json` is its output.

| shape (one IDENT accepted, 0.01 s budget) | at `328e9c1` | now |
|---|---|---|
| intact observed bytes | `losses 0`, rate `0.0` | `confirmed_losses 0`, `losses 0`, bound 0, rate `0.0`, **`loss_metric.status: exact`** |
| a fully identified corrupted frame | `losses 1`, rate 95.42 | `confirmed_losses 1`, `losses 1`, rate 95.42, `exact` |
| `garbled\n` back — unidentifiable damage at the cutoff | `losses 0`, **rate `0.0`**, `unresolved 1` | `confirmed_losses 0`, **`losses null`**, `losses_upper_bound 1`, **rate `null`**, `confirmed_losses_per_100k_bytes 0.0` (a lower bound), upper-bound rate 12 500, **`bounded`** |
| silence, nothing received | `losses 0`, rate `null`, censored 1 | unchanged, and now **`no_denominator`** says why |
| two identified corrupted frames, then unidentifiable damage, then the cutoff (new) | — | `confirmed_losses 2`, **`losses null`**, `losses_upper_bound 3`, rate `null`, confirmed rate numeric, `bounded` |

## What changed in the tool

* **`analyse`** reports `confirmed_losses` (the definite count, always a number), `losses` (the
  **total**, `null` whenever anything is unresolved), `losses_known` and `losses_upper_bound`
  (confirmed + unresolved). `clean` is on the confirmed count and on nothing being unresolved.
* **`_summarise`** keeps confirmed and unresolved counts separately and derives the total: a
  number only when every repetition was analysed and nothing is unresolved. `loss_metric`
  is the machine-readable contract — `status` ∈ {`exact`, `bounded`, `unknown`, `no_denominator`},
  `exact` bool, `reason` text — and the `denominator` text repeats it when not exact. The rate
  exists only for an exact total; `confirmed_losses_per_100k_bytes` (a lower bound) and
  `losses_per_100k_bytes_upper_bound` are reported beside it. `losses_in_analysed_repetitions`
  is replaced by `confirmed_losses`. `run.min.json` carries `confirmed_losses` and `loss_metric`.
* **The registered three-loss stop counts confirmed losses**, is unchanged in value, and now
  outranks the deadline reason when both hold — three definite losses reproduced the failure
  however the repetition ended.

`tests/test_transport_rig.py` is **101 tests** (94 → 101): `TheLossMetric` covers the review's
five shapes through a production Run, each asserted on the returned result and the persisted
`run.json`, plus the mixed regression, three confirmed losses stopping the run with the total
still unknown, and an unanalysed repetition leaving no bound either. The previous round's
analyser-failure / null-rate tests stay green; the round-3 acceptance is updated on the one
assertion that named the old contract, and says so inline.

## Still NOT done

The plan's stage 1 requires a **physical** acceptance — a separate serial device or a physical
self-loopback. That has not happened. This remains a **partial software delivery**. Nothing here
attributes anything, lifts the stop-loss or authorises a board session; no pinned file moved —
B2 verify still reports S0, qualified false, refusal null at `86393ed7…`, table `8d6f64a5…`,
71 B2 / 105 B1, prereg `68cde86d…` unfrozen.

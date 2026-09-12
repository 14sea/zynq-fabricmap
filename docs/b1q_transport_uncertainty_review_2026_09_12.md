# Transport uncertainty review — 2026-09-12

Reviewed HEAD: `328e9c1`, initially clean, seven commits ahead of origin/main.

**The three original boundary P2 examples are corrected. One remaining P2 in
the newly added unresolved-loss reporting blocks acceptance of the batch.**
Do not push the batch as accepted until that reporting contract is corrected.

## Independent validation

- The transport suite passes **94 tests, zero skips, 63.299 s**.
- The prior owner `probe_boundaries.py` runs unchanged, exit 0; its observations
  show one writer invocation, correct complete-CRC loss at cutoff, an early-stop
  terminal reason, and analyser failure stopping after one repetition with null
  aggregate loss/rate.
- The submitter's current corrections acceptance runs unchanged, exit 0.
- Production B2 verify returns S0, qualified false, refusal null, with unchanged
  71 B2 / 105 B1 pins. No full repository suite was rerun.

Results and executable probes are in the
[review evidence directory](../evidence/b1q/review_transport_uncertainty_2026_09_12/README.md).

## Accepted design choice: time reached does not imply resolved traffic

Retain the separation between `exposure_reached` and `completed_exposure`.
Reaching the registered time limit while traffic is censored can correctly mean
`exposure_reached: true`, `traffic_resolved: false`, and
`completed_exposure: false`. The explicit terminal reason distinguishes this
from not reaching the time bound. Do not change one line to make every timed
cutoff a completed exposure merely because timed physical runs may often end
with a tail in flight. Keep the actual exposure, counts and unresolved tail
available for the subsequent comparison, with their uncertainty stated.

This is acceptance of the reporting distinction, not a physical experiment,
stop-loss exception, freeze or board authorization.

## P2 — Unresolved damage still becomes a numeric total loss rate

`host/transport_rig.py:523–545, 1061–1082`.

`analyse` now explicitly distinguishes unresolved damage from both confirmed
loss and censored in-flight traffic. That is useful. However, it subtracts the
unresolved frames from `losses`, and `_summarise` reports a numeric aggregate
rate whenever the analyser itself did not raise. The unknown-total handling
only covers `repetitions_unanalysed`; it does not cover an available analysis
whose conclusion is explicitly ambiguous.

Production Run reproduction, with a 0.01 s budget and a cooperative reader:
one IDENT write is fully accepted, the capture returns `garbled\n`, and the
deadline expires. Returned and persisted results both state:

| Field | Value |
|---|---|
| accepted frames | 1 |
| received denominator | 8 bytes |
| `cutoff.ambiguous` | true |
| `unresolved_at_cutoff` | 1 |
| `losses` | 0 |
| `losses_per_100k_bytes` | **0.0** |
| `traffic_resolved` / `completed_exposure` | false / false |

This is **not** a claim that the run reports clean or completed; those flags
correctly reject that interpretation. The remaining problem is the numeric
metric used by plan section 5 for comparisons. Zero confirmed losses is a
valid lower bound here. It is not an exact total loss count or loss rate.
An uninterpretable damaged capture and an intact observed frame should not
have indistinguishable unqualified zero-rate values.

The repository test
`test_unidentifiable_damage_after_the_frontier_is_unresolved_not_censored`
already establishes the ambiguous state and asserts zero confirmed losses,
but does not check how that uncertainty propagates into the aggregate rate.
The corrections README defines `losses` as definitively affected frames; keep
that count if useful, but propagate that restricted meaning into the rate and
its machine-readable contract rather than relying on readers to infer it from
another field.

### Required correction and acceptance

Keep confirmed counts separately, for example `confirmed_losses` or an explicitly
named loss lower bound. When unresolved attribution remains, either make the
total `losses` / `losses_per_100k_bytes` null with a named reason, or provide
clearly named bounds and metric-validity fields so the result cannot be consumed
as an exact zero rate. Do not invent which frame was lost, and do not change the
registered three-loss threshold. A confirmed count can still support stopping
once three definite losses exist.

Add a production Run test asserting both returned and persisted fields for:

1. intact observed bytes: numeric confirmed zero where the metric is resolved;
2. a fully identified corrupted frame: one confirmed loss;
3. unidentifiable damage at cutoff: unknown total rate, with its confirmed lower
   bound retained separately;
4. confirmed losses followed by unresolved damage: preserve the confirmed count,
   but do not report it as the exact aggregate total;
5. silence with zero received bytes: no rate, preserving the censored state.

The four basic fixture shapes are exercised by `probe_uncertainty.py`; the mixed
confirmed/unresolved case is requested as an additional regression. The previous
analyser-exception/null-rate tests must remain green.

## Unchanged boundaries

The current bindings remain:

- Manifest: `86393ed781cb25c971aeb7a4ea3bf485b5aba5a353ef94968b3128050d5b2da1`
- B2 table: `8d6f64a5fed1fa222b2c29a0dddac6c6fd3346b23481ade1f00a3f104a907ebf`
- Unfrozen prereg: `68cde86d3f3decaf9775beac94c59731ada486ebe246006e7243156c084db8e0`

Only new review documentation and offline evidence were written. No pinned
implementation, instrument, image, manifest or ruling was changed. No push,
freeze, physical port access or board action was performed. Image compatibility
is unaffected; physical stage-1 acceptance and transport stop-loss remain pending.

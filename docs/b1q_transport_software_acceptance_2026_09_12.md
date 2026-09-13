# Transport rig software acceptance — 2026-09-12

Reviewed HEAD: `61e8a61`, initially clean, nine commits ahead of origin/main.

**PASS within the offline software scope. The outstanding uncertainty P2 is
closed; no remaining blocker was found in this correction review.** Claude may
push the nine reviewed commits through `61e8a61`. This acceptance document and
its evidence may also be collected in a separate documentation commit and pushed
with them; the additional documentation commit is explicitly included in that
disposition.

## Independent verification

- Full transport suite: **101 tests, zero skips, OK**. This is the transport
  suite, not a rerun of the full repository suite.
- Prior owner boundary and uncertainty probes: both rerun unchanged, exit 0.
- Current boundary and uncertainty correction acceptance scripts: both rerun,
  exit 0. The one updated old assertion is documented as a superseded contract;
  the historical observations remain available.
- The supplied mixed case preserves two confirmed losses, an unknown total,
  upper bound three, and a null total rate. Three confirmed losses still trigger
  the registered stop rule when the total is unknown. The unanalysed case has
  neither an exact total/rate nor a finite upper bound.
- The two committed PTY captures were independently reanalysed from raw bytes
  with the current generator, run identity and echo ledger. Both are clean and
  contain 302 delivered source frames. TX capture: 125 accounted echoes and
  112,888 received bytes; no-TX capture: no echoes and 98,599 received bytes.
  Capture hashes and recorded tool hashes match. Both exports report complete.
- Production B2 verify: **S0, qualified false, refusal null**, with **71 B2 /
  105 B1 pins** verified. No pinned input changed.

[Saved validation outputs](../evidence/b1q/transport_software_acceptance_2026_09_12/README.md).

## Accepted metric and termination contracts

An available analysis now preserves confirmed losses separately from the exact
total. When attribution is unresolved, the total and its rate are null, the
confirmed count is a named lower bound, and a separate upper bound is provided.
The aggregate `loss_metric` states exact, bounded, unknown or no_denominator
explicitly, with a reason. An analyser failure remains unknown and stops further
transmission. The registered stop threshold remains three confirmed losses.

The time-limit distinction remains accepted: `exposure_reached: true` can
coexist with `completed_exposure: false` when the cutoff leaves censored or
unresolved traffic. Do not collapse those fields into one success flag. Exact
metric values do not by themselves establish a complete exposure, physical link
stability or qualification; consumers must also read the terminal reason,
traffic/censoring state, provenance and export status. The numerator and received
byte denominator, including explicitly recorded host echoes where applicable,
must stay visible when comparing conditions.

## Scope and next boundary

This accepts the generator/driver/analyser software delivery and its offline
regressions. It does **not** complete the plan's physical stage-1 acceptance:
the separate serial device or physical self-loopback has not been tested. PTY
captures and paced software models establish no UART/USB-path stability or
physical overlap, identify no transport root cause, and lift no stop-loss.

No new implementation change is requested by this review. Physical rig
inventory, any authorized physical acceptance, A1/A2/B1/B2 experiments, and the
stop-loss disposition remain subsequent work. Production B2 S1 freeze and any
ruling or board session remain separate explicitly authorized actions.

Verified bindings:

- B2 S0 manifest: `86393ed781cb25c971aeb7a4ea3bf485b5aba5a353ef94968b3128050d5b2da1`
- B2 pin table: `8d6f64a5fed1fa222b2c29a0dddac6c6fd3346b23481ade1f00a3f104a907ebf`
- Unfrozen prereg: `68cde86d3f3decaf9775beac94c59731ada486ebe246006e7243156c084db8e0`

No push, production freeze, ruling, physical port access, board action or image
build was performed in this review. Existing image compatibility acceptance is
unaffected.

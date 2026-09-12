# Transport rig boundary review — 2026-09-12

Reviewed HEAD: `38c91b0`, initially clean, five commits ahead of origin/main.

**HOLD: three remaining P2 findings. Do not push this batch as accepted yet.**
The submitted acceptance passes unchanged and the full transport rig suite
independently passes **73 tests, zero skips, 63.181 s**. The remaining findings
were reproduced separately, through the current public API or production Run.

[Evidence and executable probes](../evidence/b1q/review_transport_boundaries_2026_09_12/README.md).

## Corrections accepted within the tested scope

The previous missing-newline, excess-echo, blank-line and non-echo-topology
examples are rejected. The ordinary deadline and detach examples now distinguish
planned and accepted frames and retain the received-byte denominator. Cooperative
read/write adapters receive the remaining timeout; the supplied serial adapter
sets a write timeout. Per-file export failure no longer prevents independent
summary attempts, and the original provenance/transport failure combination
preserves the primary cause and raw evidence. These corrections should remain.

The framed host traffic and nominal paced overlap controls also pass. They are
software scheduling evidence, not a measurement of UART overlap or a physical
stage-1 acceptance. The scope correction and withdrawal of the B2Q shorter-
exposure argument remain accepted. No hardware or stop-loss exception is granted.

## P2-1 — TypeError fallback retries a write that may already have taken effect

`host/transport_rig.py:583–593`.

`Port.write` catches any TypeError from the writer, interprets it as a signature
mismatch, disables timeout forwarding and calls the writer again. It cannot
distinguish a wrong signature from an internal exception after bytes were
accepted. This can both manufacture duplicate traffic and suppress a tool error.

Independent probe: a writer accepts `abc`, then raises an internal TypeError
once. The wrapper calls it twice, with timeouts **[0.25, None]**, accepts **abcabc**
in total, and returns **3** with no exception. The same catch also surrounds the
one-argument branch, so it is not limited to adapting a timeout-aware callback.

Determine the callback contract before executing it, using the explicit adapter
configuration already present. Do not retry or downgrade the timeout contract in
response to an exception from an active write. Retain the operation as uncertain,
stop the run and preserve its original exception. Test a side-effecting writer
that fails internally, and both supported callback signatures as independent
positive controls. Verify one invocation, no hidden duplicate bytes and no
subsequent source/host write after the error.

## P2-2 — Cutoff censoring hides a fully observed CRC failure

`host/transport_rig.py:454–467` (the censor_tail branch).

The censoring frontier is only `max(delivered)`. Any missing frame beyond it is
classified as still in flight, even if a complete corrupted line for that frame
has already arrived. The CRC diagnostic survives, but the loss metric changes.

With one expected, fully written IDENT, deliver the entire 1,048-byte line with
one byte changed and the original CRC:

| Same received bytes | losses | censored | CRC failures |
|---|---:|---|---:|
| Normal completion | 1 | none | 1 |
| Cutoff analysis | 0 | frame 0 | 1 |

The separate control with no received bytes legitimately reports the accepted
frame as censored. These cases must remain distinguishable. A cutoff does not
make bytes already observed as damaged become unobserved in-flight traffic.
The same issue affects the last observed frontier when later damaged frames
arrive but are not credited as delivered.

Track observation and delivery separately. Use defensible correspondence with
the known transmitted stream to distinguish complete damage, a partial tail and
absence of observations. Count definitively affected frames once; reserve
censoring for unresolved delivery at cutoff. Where correspondence is ambiguous,
report that ambiguity rather than silently asserting zero damage. Test complete
CRC failures at the tail, valid-CRC alterations, later damaged arrivals, a
genuinely partial line and complete silence under otherwise identical cutoffs.

## P2-3 — Termination and unknown analysis still produce misleading run status

`host/transport_rig.py:779–807, 838–885`.

Three independent production Run observations expose this boundary:

1. Request **200 repetitions**, damage three frames in the first, and trigger the
   registered early-stop rule. The persisted report correctly says one repetition
   and three losses, but also says **completed_exposure: true, incomplete: false**.
   A complete first repetition is being confused with completion of the requested
   condition exposure.
2. Complete all source writes and expire during draining, with accepted bytes
   still in flight. The report says `cut_short: true`, **302 censored frames**,
   and a deadline stop, yet **completed_exposure: true**. Per-repetition incomplete
   only tests the accepted-frame count and ignores cutoff and unresolved delivery.
3. Inject an analyser error after the first repetition. `_guarded` preserves an
   unavailable annotation, but `_analyse` substitutes `losses: 0`; Run continues
   into repetition 2. It sends **604 source frames**, returns normally with
   **error: null**, a completed-repetitions stop message and **loss rate 0.0**.
   It does mark `incomplete: true` and `completed_exposure: false`; this is not a
   claim that every field reports success. Nevertheless, analysis was unknown,
   the aggregate rate is not measured zero, and the registered "any tool error"
   stop rule was not followed. `export_complete: true` in this probe correctly
   describes files written; it must not be interpreted as valid measurement.

Represent the terminal reason explicitly and distinguish completed repetition,
completed registered exposure, early loss stop, censored cutoff and tool failure.
Make `completed_exposure` consistent with that reason and the actual traffic and
capture state. If a time-bounded condition ends with censored traffic, report that
condition explicitly rather than equating accepted write count with completion.

A live analyser failure must stop further transmission while preserving partial
evidence and secondary errors. Unknown losses/rates must remain unknown; do not
replace them with numeric zero for aggregation. Keep export completeness separate.
The normal two-repetition zero-loss positive control passes and should continue
to do so. Add the three negative controls above against persisted run.json as
well as the returned result, including an assertion that no second repetition
starts after the analyser failure.

## Validation and disposition

The original controls and submitted acceptance were rerun, not inferred from the
commit message. New observations are saved separately from previous evidence;
no old transcript or output was rewritten. No full repository suite was rerun.

Production B2 verification still reports **S0, qualified false, refusal null**,
with **71 B2 / 105 B1 pins** verified. Bindings are unchanged:

- Manifest: `86393ed781cb25c971aeb7a4ea3bf485b5aba5a353ef94968b3128050d5b2da1`
- B2 table: `8d6f64a5fed1fa222b2c29a0dddac6c6fd3346b23481ade1f00a3f104a907ebf`
- Unfrozen prereg: `68cde86d3f3decaf9775beac94c59731ada486ebe246006e7243156c084db8e0`

Correct these boundaries before the next acceptance review; preserve the already
passing fixes and the current pinned inputs. Push remains for Claude after review.
No production freeze, ruling, image build, physical port access or board action
was performed. Image compatibility is unaffected; physical transport acceptance
and the stop-loss disposition remain separate pending work.

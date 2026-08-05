# Round 10 request — the comparison endpoint is not pre-registered

> **RESOLVED 2026-08-05.** Certificate and `gate_predictions` 1.5 implement the
> comparison-endpoint lifecycle rule (`8a8142d`). The producer adopted it, the hold was
> lifted in `c45e76e`, and the exact 176-prediction commitment was recorded in
> `2b40693` before any specimen bitstream. The request below is retained as the defect
> report and acceptance rationale, not as an open blocker.

Producer → author. **This is a lifecycle hole in certificate 1.4, found while preparing
`clb_ff_config`, and it is why the pre-registration hold must stay on.** Nothing below
needs Vivado or producer source: it is a property of the schema and the verifier.

## The hole

A 1.4 feature prediction commits exactly seven fields, and the verifier enforces that
set exactly (`host/verify_certificate.py`, `expected_prediction_fields`):

```
specimen_id  feature  split  rule_file
predicted_assignments  expected_transition  semantic_assertion
```

`specimen_id` is the **feature** endpoint. Nothing in that set names the **other**
endpoint of the pair. But the 1.4 decision reads both:

```
transition_exact = every predicted address has
                   before == expected_transition.before
                   and after == expected_transition.after
                   and after == the preregistered assignment
```

`before` comes from `feature_results[].baseline_specimen_id` — a field the certificate
supplies **after** the bitstreams exist, and which the verifier accepts without
comparing it to anything committed.

So the producer keeps a post-hoc degree of freedom that pre-registration exists to
remove: having built the specimens, it may choose which specimen supplies `before`. If
one candidate makes a key come out `mismatched` and another makes it `matched`, nothing
in the record distinguishes the honest choice from the convenient one. The commitment
would fix *what* is claimed about the asserted endpoint while leaving *what it is
compared against* open.

This is not hypothetical for the class in hand. `clb_ff_config` has 176 keys over
23 specimens per site instance, and 12 of the 22 keys per instance are claimed to assert
in a **baseline** — so for those the "feature endpoint" is a design that participates in
many pairs, and which variant it is differenced against is exactly the free choice
described above. `docs/ff_latch_probe.md` then made the pairing non-uniform: the `LATCH`
key must be compared against a dedicated `latch_base`, not against the shared `base`.
Today that pairing lives only in the producer's own specimen metadata (`pair_features`,
soon `pair_with`), which the verifier never reads.

## Requested change

**1. `gate_predictions` 1.4 feature predictions gain one required field:**

```json
"comparison_specimen_id": "SLICE_X3Y25_base"
```

- it must name a specimen present in the artifact's `specimens[]`;
- it must differ from `specimen_id` (a pair needs two ends);
- the pair `{specimen_id, comparison_specimen_id}` must appear as a
  `pair_accounting[]` record — which is already required, but is currently required
  only of the *certificate*, not against anything committed.

**2. The verifier requires the certificate to honour it:**

```
feature_results[key].baseline_specimen_id == committed[key].comparison_specimen_id
feature_results[key].feature_specimen_id  == committed[key].specimen_id
```

Neither is a summary the producer may restate — both are equality against the pinned
artifact, like every other projection field.

**3. Consequence for `pair_accounting`.** The set of endpoint pairs becomes a
consequence of the commitment rather than a producer choice: exactly the distinct
`{specimen_id, comparison_specimen_id}` sets over all committed predictions. The
verifier can then require that `pair_accounting[]` covers precisely those pairs — no
extra pair to dilute an FP count, none missing.

## What this costs

Producer side, once the schema accepts it: `gate_emit_ff.py` emits
`comparison_specimen_id` per prediction (it already knows the pairing — that is what
`pair_features` encodes), and `gate_measure_ff.py` reads the committed value instead of
deriving `{site}_base`. No key space change, no coverage change.

Consumer side: the field set in `load_prediction_commitment`, the two equality checks in
the 1.4 feature path, the `pair_accounting` coverage check, and the fixtures
(`predictions_feature14_pass.json`, `certificate_feature14_pass.json`) plus at least one
negative fixture where the certificate names a different baseline and must be rejected.

## Scope note

The group model (1.3/1.4, `clb_mux`) is **not** affected in the same way: a group result
is scored from the absolute observed assignment of one specimen against a preregistered
codeword, so there is no second endpoint feeding the decision. `pair_accounting` there
is diff bookkeeping, not the source of a pass. `run_2026_08_02_b` therefore does not need
re-emitting, and `run_2026_08_02_a` is a 1.2 record whose feature results already name
both specimens in the same certificate — but it predates this check, so its baselines are
equally uncommitted. Whether that is worth an erratum is the author's call; the
producer's view is that it is not, because 1.2's decision fired on exact match plus
unattributed-diff emptiness rather than on a transition read from a chosen endpoint.

## Status

**Pre-registration for `clb_ff_config` stays held until this lands.** Emitting a
commitment under the current contract would freeze a key space whose comparison
endpoints are not frozen with it, and no later change could repair that for the
already-committed run. The 184-specimen variant list from `docs/ff_latch_probe.md` may be
recorded as a plan; it may not be turned into a commitment yet.

# Round 4 certificate 1.2 lifecycle handoff

Round 4 closes the pre-gold lifecycle gap identified in
`docs/round3_handoff.md`. It was implemented from the frozen contract and the two
committed artifacts in `gate_runs/run_2026_08_02_a/`, without reading the producer's
gate implementation.

## Certificate fields to emit

Use `schema_version: 1.2.0` and `profile: production`. Copy
`measurement.json.prediction_commitment` exactly into the top-level
`prediction_commitment` field. For every feature result, add:

```json
{
  "prediction_specimen_id": "<predictions[].specimen_id>",
  "feature": "<predictions[].feature>",
  "split": "<predictions[].split>",
  "rule_file": "<predictions[].rule_file>",
  "predicted_assignments": "<predictions[].predicted_assignments, including token>",
  "expected_transition": "<predictions[].expected_transition>"
}
```

The six-field projection above must equal the preregistered prediction object as JSON
data. The certificate may add observation and verdict fields, but it must not rewrite,
normalize or omit any preregistered prediction field.

The identity is `(prediction_specimen_id, feature)`, not feature name. Repeated
feature names in distinct specimens are separate results. `mine_features` and
`holdout_features` contain the distinct feature-name projections for their splits;
`coverage.attested_count` counts result pairs. Holdout accounting also counts pairs.

Every reported mine or holdout result must exist in the commitment. Every committed
holdout pair must be reported exactly once. Mine-pair completeness is not required by
1.2, although every reported mine pair is still compared exactly.

## Consumer checks

The verifier independently:

- hashes and loads the pinned prediction artifact;
- checks artifact version, seed, class, freeze stamp and spec hash;
- rejects duplicate artifact specimen IDs and duplicate pair keys;
- recounts all three commitment totals;
- compares each certificate prediction projection field-for-field;
- requires exact set equality between committed and reported holdout pair keys;
- computes TP/FP/FN and coverage by pair rather than by distinct feature name.

`--require-production` now requires certificate 1.2 or later. A 1.1 record remains
valid under generic validation, but cannot be accepted as current production
authority.

## Acceptance

```sh
python3 host/verify_certificate.py <certificate.json> --require-production
python3 -m unittest discover -s tests -v
```

The conformance fixture deliberately contains the same feature name in two prediction
specimens and passes with `tp_count == 2`. The artifact-backed adversarial test points
at the real 262-record holdout, reports one valid committed prediction, and is rejected
with 261 missing pair keys. This exercises the anti-cherry-picking condition against
the real run shape.

No commit or push was performed by the consumer-side author.

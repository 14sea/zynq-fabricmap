# Certificate schema — `fabric_bit_class_certificate` 1.2.0

Version 1.1.0 adds optional specimen-attestation and explicit diff-exclusion evidence
to 1.0.0. Version 1.2.0 adds an optional preregistered prediction commitment and a
specimen-qualified prediction key. All additions are optional in the generic 1.x
schema, so older records remain valid under generic validation. The current
production acceptance profile makes all three evidence classes mandatory.

Machine-readable schema: `schemas/certificate.schema.json`. This document defines
the semantic checks that JSON Schema cannot express. The certificate is emitted by
the producer-owned gate and judged by the consumer-owned
`host/verify_certificate.py`.

Versioning follows the repository contract: MAJOR changes are incompatible; MINOR
changes only add optional fields. A consumer rejects an unsupported MAJOR and ignores
unknown fields in a supported MAJOR. The JSON Schema therefore deliberately permits
unknown properties.

## Evidence model

- `frozen_inputs` pins the spec hash, every declared consumed frozen-file hash, the
  manifest schema version and `freeze_stamp`. The verifier compares all of them with
  the current `data/` freeze; a mismatch is stale evidence and is rejected.
- `specimens[]` records one built bitstream per design, including source hash, Vivado
  version, part, LOC site, tile, tile frame base, seed and bitstream hash. A feature
  result names its baseline and feature specimens, making the compared pair explicit.
- Certificate 1.1 may attach `attestation: {path, sha256, schema_version}` to a
  specimen. The path is relative to the repository root. The verifier validates the
  external `specimen_attestation` against
  `schemas/specimen_attestation.schema.json`, checks its pinned file hash and version,
  and requires its routed `resolved_loc`, tile, part and output bitstream hash to agree
  with the specimen record. For `clb_lut_init`, the current production profile accepts
  identity pin mapping only; permutation application is deliberately not implemented.
- `predicted_assignments[]` retains both the raw segbit coordinate and the absolute
  address. `expected_value` is 0 for a negated `!F_B` token and 1 otherwise.
- Certificate 1.2 may pin the pre-gold `gate_predictions` file with
  `prediction_commitment: {run_id, path, sha256, schema_version, seed, totals}`.
  The verifier checks the file hash, artifact version, seed and class; compares its
  freeze stamp and spec hash with the certificate; rejects duplicate specimen IDs or
  duplicate `(specimen_id, feature)` keys; and independently recounts specimen,
  prediction and holdout totals.
- A 1.2 production feature result carries `prediction_specimen_id`, the raw segbit
  `token`, and `expected_transition`. Its prediction projection — specimen ID,
  feature, split, rule file, complete assignment list and expected transition — must
  be exactly equal to the preregistered record. A recipe hash or a copied total is not
  a substitute for this comparison.
- `rule_file` identifies the frozen `.db` record behind a feature. It must be among
  `frozen_inputs.files`; the verifier rereads that exact feature line and rejects a
  prediction whose complete token sequence differs from the frozen rule.
- `observed_assignments[]` records the value read from the feature specimen at every
  predicted address. `observed_diff[]` records every non-excluded changed address and
  its direction. In 1.1, `excluded_diff[]` lists excluded changes explicitly and
  `exclusion_rules[]` states the independently checked reason; their union is the raw
  changed-bit record.
  `unattributed_diff[]` is exactly the subset of changed addresses absent from the
  prediction, including whether each address is listed by the frozen mask.
- In 1.0/1.1, `split` stores exact feature-name membership and feature name is the
  result key. In 1.2 production, the authoritative unit is
  `(prediction_specimen_id, feature)`: repeated feature names across specimens are
  valid and separately scored. `mine_features` and `holdout_features` remain the
  distinct-name projections of the result records. Every preregistered holdout pair
  must appear exactly once; reporting only the successful pairs is invalid.

## Accounting and falsifier

On holdout evidence:

```
tp_count = feature results whose complete prediction matched with no unattributed diff
fn_count = feature results that did not match exactly
fp_count = unattributed changed-bit observations
```

For 1.2 production, `tp_count + fn_count` equals the number of preregistered holdout
pairs, not the number of distinct feature names. A passing certificate must satisfy:

```
tp_count == prediction_commitment.totals.holdout_predictions
fn_count == 0
fp_count == 0
```

Anything else is a failed certification. A failed record is first-class rather than
malformed: it has `status: failed`, at least one structured `failure_reasons[]` item,
the same evidence fields as a pass, and the non-passing counts and feature verdicts.
A record that says `passed` while its evidence or counts falsify the decision is
invalid and the verifier exits nonzero.

The verifier also exits nonzero for a valid `status: failed` record so it cannot be
mistaken for a usable certificate. `--allow-failed` is available only for validating
that a failure record conforms to this schema; it does not turn the decision into a
pass.

`coverage` stores integer numerator and denominator, not a rounded rate. In 1.2
production its numerator equals the number of specimen-feature result records; its
denominator equals the current manifest class entry count.

## Current production profile 1.2

The profile is selected by `profile: production`. Production consumers invoke the
verifier with `--require-production`; this currently requires certificate 1.2 or
later, so emitting a 1.1 record cannot bypass lifecycle verification. A historical
1.1 production fixture remains accepted by generic validation for compatibility,
but it is not current production authority.

The current profile requires:

- certificate `schema_version >= 1.2.0`;
- an attestation reference on every specimen;
- `exclusion_rules[]` and `excluded_diff[]` on every feature result, including an
  empty excluded list when no ECC bit changed;
- a valid `prediction_commitment` reference;
- `prediction_specimen_id`, `expected_transition`, and each assignment's raw `token`;
- exact field equality for every reported prediction and complete inclusion of all
  preregistered holdout pairs.

Only one exclusion rule is supported: `frame_ecc`, exactly
`word == 50 and 0 <= bit <= 12`. The verifier rejects an excluded bit outside that
shape, observed/excluded overlap, predicted/excluded overlap, unchanged "diff" bits,
undeclared rules, ECC-shaped bits left in `observed_diff`, and any excluded FAR with
no non-ECC `observed_diff` in the same frame. Thus an ECC-only frame cannot be hidden.

Generic validation still accepts legacy and conformance records. Acceptance for a
production certificate is always:

```sh
python3 host/verify_certificate.py <certificate.json> --require-production
```

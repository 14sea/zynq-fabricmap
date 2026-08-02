# Certificate schema — `fabric_bit_class_certificate` 1.0.0

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
- `predicted_assignments[]` retains both the raw segbit coordinate and the absolute
  address. `expected_value` is 0 for a negated `!F_B` token and 1 otherwise.
- `observed_assignments[]` records the value read from the feature specimen at every
  predicted address. `observed_diff[]` records every changed address and its direction.
  `unattributed_diff[]` is exactly the subset of changed addresses absent from the
  prediction, including whether each address is listed by the frozen mask.
- `split` stores exact feature membership. Mine and holdout are disjoint, and every
  member has exactly one `feature_results[]` record with the same split label.

## Accounting and falsifier

On holdout evidence:

```
tp_count = feature results whose complete prediction matched with no unattributed diff
fn_count = feature results that did not match exactly
fp_count = unattributed changed-bit observations
```

Consequently `tp_count + fn_count == len(holdout_features)`. A passing certificate
must satisfy all of:

```
tp_count == len(holdout_features)
fn_count == 0
fp_count == 0
```

Anything else is a failed certification. A failed record is first-class rather than
malformed: it has `status: failed`, at least one structured `failure_reasons[]` item,
the same evidence fields as a pass, and the non-passing counts and feature verdicts.
A record that says `passed` while its evidence or counts falsify the decision is
invalid and the verifier exits nonzero.

`coverage` stores integer numerator and denominator, not a rounded rate. The verifier
requires its numerator to equal the number of explicitly attested features and its
denominator to equal the current manifest class entry count.

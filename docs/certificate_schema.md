# Certificate schema — `fabric_bit_class_certificate` 1.1.0

Version 1.1.0 adds optional specimen-attestation and explicit diff-exclusion evidence
to 1.0.0. Both additions are optional in the generic 1.x schema, so every 1.0.0
record remains valid. They become mandatory when `profile: production` is selected.

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

The verifier also exits nonzero for a valid `status: failed` record so it cannot be
mistaken for a usable certificate. `--allow-failed` is available only for validating
that a failure record conforms to this schema; it does not turn the decision into a
pass.

`coverage` stores integer numerator and denominator, not a rounded rate. The verifier
requires its numerator to equal the number of explicitly attested features and its
denominator to equal the current manifest class entry count.

## Production profile 1.1

The first production profile is selected by `profile: production`; production
consumers invoke the verifier with `--require-production` so omitting the profile is
not a downgrade path. It requires:

- certificate `schema_version >= 1.1.0`;
- an attestation reference on every specimen;
- `exclusion_rules[]` and `excluded_diff[]` on every feature result, including an
  empty excluded list when no ECC bit changed.

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

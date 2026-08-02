# Round 3 certificate 1.1 production-evidence handoff

This consumer-side drop implements the two evidence additions specified by
`docs/evidence_contract.md`. It was written from that contract, the normative freeze
format, machine schemas, and frozen producer samples. Producer implementation source
was not read or imported.

## Version and profile

`fabric_bit_class_certificate` 1.1.0 adds optional fields to the generic 1.x schema:

- `specimens[].attestation: {path, sha256, schema_version}`;
- `feature_results[].exclusion_rules[]` and `excluded_diff[]`;
- top-level `profile`.

Legacy 1.0.0 records remain valid. `profile: production` makes both evidence classes
mandatory, and production consumers must invoke `host/verify_certificate.py` with
`--require-production`. Thus omitting the profile or evidence is not a downgrade path
for a formal certificate.

Machine schemas:

- `schemas/certificate.schema.json` — generic 1.x plus the 1.1 production profile;
- `schemas/specimen_attestation.schema.json` — consumer validation shape for external
  `specimen_attestation` 1.x artifacts.

## Independent semantic checks

For every supplied attestation, the verifier:

1. resolves its repository-relative path and rejects path escape;
2. checks file SHA-256 and validates the external record schema;
3. checks the reference schema version against the file;
4. compares attested routed `resolved_loc`, tile and input part with the specimen;
5. requires the specimen's bitstream hash among attestation outputs;
6. requires identity pin mapping for every `clb_lut_init` result.

Permutation application is not implemented in this profile. A non-identity mapping
is rejected rather than interpreted optimistically.

For frame-ECC exclusion, the verifier independently requires:

1. exactly the declared `frame_ecc` rule,
   `word == 50 and 0 <= bit <= 12`;
2. every excluded address to satisfy that shape and record a real transition;
3. observed and excluded sets to be disjoint;
4. no predicted address to be excluded;
5. every excluded FAR to contain a non-ECC observed change;
6. every ECC-shaped change to be in the excluded set rather than ordinary observed
   evidence.

`observed_diff[] union excluded_diff[]` is therefore the declared raw change record;
only `observed_diff[]` participates in attribution and TP/FP/FN accounting.

## Conformance fixture and falsifiers

`tests/fixtures/certificate_production_pass.json` is a sample-backed 1.1 production
conformance record for interior LUT bit INIT[01]. It pins the real routed attestation
sample (`sha256 76a951db...`), both real sample bitstream hashes, the observed
`33_15` change, and all nine frame-ECC changes in the frozen producer diff sample.
It demonstrates record conformance, not a complete mine/holdout campaign certificate.

`tests/test_round3.py` supplies 13 checks, including decisive rejection of:

- legacy/profile omission in production mode;
- missing attestation, hash mismatch, LOC/tile mismatch, unlisted bitstream output,
  and non-identity LUT pin mapping;
- missing exclusion evidence, invalid ECC shape, observed/excluded and
  predicted/excluded overlap, ECC-only frames, and ECC-shaped bits left observed.

Combined with rounds 1 and 2, the consumer suite has 26 passing tests.

## Production invocation

```sh
python3 host/verify_certificate.py certificate.json --require-production
```

Exit behavior is unchanged: verified pass = 0, malformed or contradictory artifact =
1, well-formed certification failure = 2. `--allow-failed` only validates the shape
and evidence of a failed record.

## Commands run

```sh
scripts/extract_prjxray_subset.py --verify
python3 host/verify_data.py
python3 host/verify_address_fixtures.py
python3 host/verify_certificate.py \
  tests/fixtures/certificate_production_pass.json --require-production
python3 -m unittest -v \
  tests/test_round1.py tests/test_round2.py tests/test_round3.py
python3 -m py_compile host/verify_certificate.py tests/test_round3.py
git diff --check
```

## One remaining lifecycle boundary

Concurrent producer commit `5250cd0` adds a valuable pre-gold
`gate_predictions` artifact. Certificate 1.1 as requested above does not yet pin or
compare that commitment, so this verifier proves consistency with frozen rules and
reported observations but does not independently prove that holdout predictions
preceded fresh-gold observation. Before the certificate becomes authority, the
consumer needs a producer contract for referencing the registered artifact and
mapping certificate results to committed `(specimen_id, feature)` predictions; the
artifact legitimately contains repeated feature names across distinct specimens, so
feature name alone is not a sufficient join key.

Repository coordination: during this work, concurrent commit `5bd42c3` intentionally
captured the schema additions and froze real producer samples. The remaining verifier,
documentation, production fixture, tests, and this handoff are working-tree changes.
Untracked `scripts/gate_build.py` is producer-side concurrent work and is not part of
this author drop. No commit or push was performed by the author.

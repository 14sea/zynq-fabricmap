# Claim B round 1 — consumer response

This is the author-side response to `docs/claimb_handoff.md`. It covers only the
consumer-owned schema, verifier and known-answer fixtures. It does not authorise a carrier
build, a board-side guard, calibration, a device write, or freezing §6's budget.

## Accepted authority shape

`local_map` 1.0.0 is accepted with `provenance.kind` fixed to
`certificate_inherited`. A stronger provenance claim is not a minor extension of this
round and is refused by the schema. The proposal markings have been removed from
`schemas/local_map.schema.json`; it is now the consumer-owned authority schema.

Two count meanings are deliberately distinct:

- the certificate has 388 feature-result records;
- after agreeing re-attestations collapse, the writable universe has 292 distinct,
  uniquely-addressed features.

`bit_class.attested_count` means the latter. It may never be copied from the former.

## Independent verifier

`host/verify_local_map.py` does not import or invoke `scripts/build_local_map.py`. It:

1. validates the map against the authority schema;
2. resolves and hashes the pinned certificate and the canonical `data/MANIFEST.json`;
3. requires the existing certificate verifier to accept the certificate under
   `--require-production`, and independently verifies the frozen manifest;
4. re-derives the unique universe from matched predicted/observed assignments;
5. derives polarity from `segbit.negated` and cross-checks the token, predicted value and
   observed value;
6. rejects disagreeing re-attestations and two features claiming one address;
7. reconstructs `by_far` and `by_lut` from feature semantics, not from map keys;
8. derives the one frame-ECC exception from every result's exclusion rule; and
9. compares the complete derived universe, counts, indexes and collateral record to the
   map.

The current artifact passes as exactly 292 addresses over 12 frames and 6 partial LUTs.

## Independent known answers

`tests/fixtures/local_map_negated_bundle.json` is intentionally synthetic. The real 292
entries contain no negated token, so a real-data-only suite cannot distinguish correct
polarity handling from a constant-one implementation. The fixture includes one negated
and one positive INIT assignment and is consumed directly by
`tests/test_verify_local_map.py`, not by the producer builder.

The same suite refuses an unattested but internally indexed address, a map that combines
two LUTs under one `by_lut` key, wrong certificate and manifest hashes, failed and
conformance certificates, conflicting re-attestation, a stronger provenance kind, and
map-selected ECC collateral.

`tests/test_claimb_consumer_fixtures.py` serialises a candidate from literal packet words,
without either producer sequence builder. It proves both frame semantics and supplies the
requested plausible known-bad candidate: its frame ECC is correct, but one content bit is
outside the whitelist, so it is refused for `target_frame`, not for `ecc` or malformed
structure.

## Gate review: frame partition accepted, control envelope blocked

The target-frame rule is complete at bit level. All 3,232 bits of a 101-word frame fall
into exactly one of these domains:

- words other than 50: only whitelist members may differ;
- word 50 bits 0..12: must equal the ECC recomputed over the candidate frame;
- word 50 bits 13..31: must equal the pinned base.

Flush frames correctly admit no differences at all.

The surrounding ICAP envelope is not yet gated to the preregistered fixed sequence.
Removing RCRC, removing WCFG, or changing the sole CRC write from zero to a non-zero word
all currently produce `writable=true` and no finding. The decisive reproduction and
acceptance boundary are in the intentionally untracked `review.v1.txt` required by
`docs/workflow.md`.

Therefore the consumer drop is ready, but Claim B is **not ready for a first device
write** until the producer closes that review and the consumer fixtures remain green.

# Round 6 certificate 1.3 handoff

> **ACCOUNTING ERRATUM 2026-08-04.** The `address_pass=32` acceptance headline below
> counted 16 vacuous `group_exclusivity` outcomes as address evidence. Run B was
> re-emitted under certificate 1.4 without changing predictions, measurements or
> specimens. Its current result is 16/16 falsifiable strict-codeword passes, 16 vacuous
> exclusivity diagnostics, decode-validity 16/16 diagnostic, and semantic 16/16. See
> `docs/round9_ruling.md` and `tests/test_run_b_erratum.py`.

Certificate 1.3 adds the consumer-owned `group` evidence model needed to certify
`clb_mux`. It is additive: certificate 1.2 feature records and the already certified
Run A remain valid production authority.

## Emitter contract

Emit these top-level selectors:

```json
{
  "schema": "fabric_bit_class_certificate",
  "schema_version": "1.3.0",
  "evidence_model": "group",
  "profile": "production",
  "claim_scope": "group_bit_set",
  "status": "passed",
  "semantic_status": "passed"
}
```

Copy `prediction_commitment` from the measurement. For every committed prediction,
emit exactly one `group_results[]` item keyed by
`(prediction_specimen_id, group)`. Copy its preregistered `group`, `split`,
`rule_file`, `scope`, and `assertions` without recomputing or normalizing them. Add
the measurement's `decoded_members`, complete `observed_assignment`, and all three
`assertion_outcomes`.

Copy each measurement specimen without its ignored `bitstream` path. The required
fields are `specimen_id`, `split`, `site`, `ff_bel`, `ffsrc`, `tile`, `tile_type`,
`bitstream_sha256`, and the complete attestation reference including checkpoint.
Copy `measurement.accounting[]` to certificate `pair_accounting[]`; preserve every
bucket's bit list, not only its count.

For `bit_class`, report unique group-label projections in `split`, all-result coverage,
and holdout-only assertion counts:

```json
{
  "id": "clb_mux",
  "tier": "content",
  "manifest_entries": 500,
  "split": {"mine_groups": [], "holdout_groups": []},
  "coverage": {"attested_count": 24, "class_entry_count": 500},
  "address_accounting": {
    "group_exclusivity": {"pass_count": 16, "fail_count": 0},
    "scope_assignment": {"pass_count": 16, "fail_count": 0}
  },
  "semantic_accounting": {
    "member_identity": {"pass_count": 16, "fail_count": 0}
  },
  "decision_rule": "holdout_address_assertions: group_exclusivity.fail_count == 0 and scope_assignment.fail_count == 0",
  "semantic_rule": "member_identity is reported independently and never contributes to status"
}
```

`status` is the address decision only. `semantic_status` reports member identity only.
Do not turn a semantic failure into address failure. A failed address certificate
needs structured `failure_reasons`; a semantic-only failure keeps
`status: passed`, has no address failure reason, and sets `semantic_status: failed`.

## Independent verifier

`host/verify_certificate.py` now independently:

- validates the prediction artifact, preregistered specimen identity projection, and
  exact `(specimen_id, group)` lifecycle join;
- derives maximal groups by identical frozen-DB bit set, never by name;
- requires complete scope and recomputes all absolute addresses;
- decodes assert-iff and both address outcomes from absolute observed values;
- rebuilds expected routed edges from preregistered `netlist_basis`, compares raw edge
  evidence with each pinned attestation, and recomputes semantic identity separately;
- checks five-bucket duplicate freedom, pairwise disjointness, counts, and union size;
- rejects tile-wide authority in the presence of geometric `ownership_unknown` or any
  frozen-DB coordinate absent from the asserted-scope union for that physical tile.

The verifier can check only the recorded partition and pinned hashes without the
bitstreams. It cannot recreate the raw diff. A DCP hash is an integrity anchor, not
proof that the pinned bitstream came from that DCP; reproducing that relation requires
Vivado. These limits are normative in `docs/certificate_schema.md`.

## Acceptance

The Round 6 conformance suite is driven by the committed real Run B predictions,
measurement, and 24 attestations. It covers the requested positive case and all five
adversarial classes, including semantic-only failure isolation.

```sh
python3 -m unittest tests.test_round6 -v
python3 -m unittest discover -s tests -v
python3 host/verify_certificate.py <certificate.json> --require-production
```

The final command should report `address_pass=32 address_fail=0` and
`semantic_status=passed semantic_pass=16 semantic_fail=0` for Run B.

## Round 7 correction — tile authority also requires coverage

The first formal group certificate exposed an overclaim path: changing only
`claim_scope` from `group_bit_set` to `tile` passed when `ownership_unknown` happened
to be empty. That condition proves attribution of observed movers, not coverage.

The verifier now independently derives every coordinate in each specimen tile's full
frozen segbits DB and compares it with the union of scopes asserted for that physical
tile. Both the coverage requirement and the original unknown-ownership requirement
must pass. Run B remains valid at group scope; promoting the same evidence to tile
scope fails with 632 and 634 uncovered addresses in its two tiles.

# Certificate schema — `fabric_bit_class_certificate` 1.3.0

Version 1.1.0 adds optional specimen-attestation and explicit diff-exclusion evidence
to 1.0.0. Version 1.2.0 adds an optional preregistered prediction commitment and a
specimen-qualified prediction key. All additions are optional in the generic 1.x
schema. Version 1.3.0 adds a selectable group evidence model for mux claims. Selecting
that model makes its group fields mandatory, while records that omit
`evidence_model` continue to validate as feature-model records. Older records remain
valid and the feature production profile is unchanged.

Machine-readable schema: `schemas/certificate.schema.json`. This document defines
the semantic checks that JSON Schema cannot express. The certificate is emitted by
the producer-owned gate and judged by the consumer-owned
`host/verify_certificate.py`.

Versioning follows the repository contract: MAJOR changes are incompatible; MINOR
changes only add optional fields. A consumer rejects an unsupported MAJOR and ignores
unknown fields in a supported MAJOR. The JSON Schema therefore deliberately permits
unknown properties.

## Evidence-model selector

`evidence_model` is `feature` or `group`. Omission means `feature` for compatibility.
The two result shapes are deliberately not mixed:

- `feature` uses `feature_results[]` and the 1.2 TP/FP/FN decision described below;
- `group` requires schema 1.3 or later and uses `group_results[]`,
  `pair_accounting[]`, `claim_scope`, and an independent `semantic_status`.

A group certificate cannot gain authority by also carrying feature results. The host
verifier dispatches solely on `evidence_model` and recomputes the selected model.

## Feature evidence model (1.0–1.2)

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
- `predicted_assignments[]` retains the verbatim frozen-db token, the parsed segbit
  coordinate and the absolute address. Token text uses the normative `%02d_%02d`
  spelling from `docs/freeze_format.md` §5.3. `expected_value` is 0 for a negated
  `!F_B` token and 1 otherwise.
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
  prediction whose complete token sequence differs string-for-string from the frozen
  rule. It does not reconstruct token text from integer coordinates. The independently
  parsed coordinate sequence must also agree.
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

## Feature accounting and falsifier

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

## Group evidence model (1.3)

`group_results[]` is keyed by `(prediction_specimen_id, group)`. Every result copies
the preregistered `group`, `split`, `rule_file`, complete `scope`, and `assertions`
verbatim. The verifier compares that projection with the pinned `gate_predictions`
artifact and requires every committed mine and holdout pair exactly once.
The preregistered specimen's site, FF BEL/source variant, tile, tile type, split, and
ID must also equal the certificate specimen projection; the ID alone is not identity.

Group membership is recomputed from the frozen DB by bit identity, never by name: it
is the maximal set of class features with the same coordinate set after polarity is
removed. The declared scope must equal one such complete set, including bits that did
not move. Its absolute addresses are independently recomputed from the specimen tile
and the normative arithmetic in `docs/freeze_format.md`. A bracketed group label is
only reconciled with the members after bit-set grouping; it never selects the group.
Thus a name-derived `CARRY4` union and a mover-only truncated scope are invalid.
Every polarity-free `segbit` coordinate retains the frozen DB's canonical
`%02d_%02d` spelling; integer-equivalent unpadded text is invalid.
The rule filename must match the specimen tile type, and the bit-set-derived feature
prefix must match the specimen's independently derived site type/index. This prevents
a valid group from a neighbouring site instance being substituted into the record.

Each group has exactly three assertions:

| assertion | decision class | verifier recomputation |
|---|---|---|
| `group_exclusivity` | address | at most one frozen member satisfies assert-iff |
| `scope_assignment` | address | every complete-scope observed value equals its preregistered value, and that value pattern encodes a frozen member |
| `member_identity` | semantic | decoded DB member name and routed netlist edge agree with the preregistered claim |

Assert-iff means every positive token is 1 and every negated token is 0. The verifier
rereads all member rules and decodes the absolute observed assignment; copied decoded
member lists and outcome booleans are summaries, not inputs to the decision.

Only holdout address outcomes enter `status`. A pass requires both address
`fail_count` values to be zero and every pair partition to be exact. The independently
recomputed `member_identity` outcomes enter `semantic_status` and
`semantic_accounting` only. A semantic failure with correct addressing therefore has
`status: passed`, `semantic_status: failed`, and verifier exit 0 with the semantic
failure counts printed prominently. Setting address `status: failed` merely because
semantic identity failed is malformed, not a stricter certificate.

### Semantic edge evidence

The verifier derives the expected edge from the preregistered `netlist_basis`; it does
not trust the producer's `expected_edge` copy or `netlist_basis_consistent` boolean.
It compares `attested_edge` with the pinned attestation and requires:

- edge checkpoint equality with the attestation's top-level checkpoint;
- route status `ROUTED`;
- LUT-output basis: `driver_ref == LUT6` and `driver_cell == target`;
- package-pin basis: `driver_ref == IBUF`, a nonempty top-level source port, and a
  nonempty named package pin.

These checks make a semantic PASS auditable without putting it into the address
decision.

### Diff partition and its limit

Every `pair_accounting[]` record lists bit identities for five buckets:
`in_scope`, `frame_ecc`, `db_attributed`, `ownership_unknown`, and `unattributed`.
The verifier checks duplicates, pairwise disjointness, each recorded count against the
list length, and union size against `raw_diff_bits`; `partition_exact` is only a
summary. A tile-wide `claim_scope: tile` cannot pass while any pair contains
`ownership_unknown` in a claimed tile's geometric range. Run B uses
`claim_scope: group_bit_set` and currently records no unknown bits; its narrower claim
would not silently acquire tile-wide authority if that bucket became nonempty later.

Absence of unknown ownership is not coverage. For a tile-wide claim the verifier also
reads every token coordinate in the frozen `segbits_<tile_type>.db`, instantiates that
set at each physical specimen tile, and requires it to be a subset of the union of all
asserted scopes for that tile. No producer-supplied coverage count or `uncovered_bits`
summary is trusted. An uncovered coordinate makes the address decision fail even when
every observed changed bit was attributable. The Run B certificate leaves 632 DB
addresses uncovered in `CLBLL_L_X2Y25` and 634 in `CLBLM_L_X6Y25`, so changing only
its `claim_scope` to `tile` is rejected.

The verifier does not possess the bitstreams and therefore cannot independently
recompute `raw_diff_bits`. It validates the partition's internal completeness and the
attestations' pinned bitstream hashes. Likewise, hashing a checkpoint and bitstream in
one attestation anchors both against substitution but does not prove that the latter
was produced from the former. Re-establishing either relation requires a Vivado
rebuild; the checkpoint hash is an integrity anchor, not independent provenance proof.

## Current production profiles 1.2 and 1.3

The profile is selected by `profile: production`. Production consumers invoke the
verifier with `--require-production`. A feature record requires certificate 1.2 or
later; a group record requires 1.3 or later. Emitting a 1.1 record cannot bypass
lifecycle verification. A historical 1.1 production fixture remains accepted by
generic validation for compatibility, but it is not current production authority.

The feature profile requires:

- certificate `schema_version >= 1.2.0`;
- an attestation reference on every specimen;
- `exclusion_rules[]` and `excluded_diff[]` on every feature result, including an
  empty excluded list when no ECC bit changed;
- a valid `prediction_commitment` reference;
- `prediction_specimen_id`, `expected_transition`, and each assignment's raw `token`;
- exact field equality for every reported prediction and complete inclusion of all
  preregistered holdout pairs.

The group profile requires:

- `schema_version >= 1.3.0` and `evidence_model: group`;
- a valid prediction commitment and complete `(specimen_id, group)` reporting;
- attestation and checkpoint references on every specimen;
- complete frozen-DB-derived group scopes and independently decoded assert-iff;
- separate address and semantic accounting/status;
- identity-bearing, exact five-bucket partition records for every variant pair.

For the feature profile, only one exclusion rule is supported: `frame_ecc`, exactly
`word == 50 and 0 <= bit <= 12`. The verifier rejects an excluded bit outside that
shape, observed/excluded overlap, predicted/excluded overlap, unchanged "diff" bits,
undeclared rules, ECC-shaped bits left in `observed_diff`, and any excluded FAR with
no non-ECC `observed_diff` in the same frame. Thus an ECC-only frame cannot be hidden.

Generic validation still accepts legacy and conformance records. Acceptance for a
production certificate is always:

```sh
python3 host/verify_certificate.py <certificate.json> --require-production
```

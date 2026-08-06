# Certificate schema — `fabric_bit_class_certificate` 1.6.0

Version 1.1.0 adds optional specimen-attestation and explicit diff-exclusion evidence
to 1.0.0. Version 1.2.0 adds an optional preregistered prediction commitment and a
specimen-qualified prediction key. All additions are optional in the generic 1.x
schema. Version 1.3.0 adds a selectable group evidence model for mux claims. Version
1.4.0 adds shared five-bucket accounting to feature records, verifier-derived group
consistency, observation consistency, a fixed pair-level FP definition, and corrects
the group model's vacuous address accounting. Version 1.5.0 preregisters the feature
comparison endpoint and derives the exact endpoint-pair accounting set from that
commitment. Version 1.6.0 pins an exact post-build staging set and selects the routed
multi-cell `specimen_attestation` 2.0 profile. Selecting a newer record version makes
that version's evidence mandatory.
Older records retain their original semantics.

Machine-readable schema: `schemas/certificate.schema.json`. This document defines
the semantic checks that JSON Schema cannot express. The certificate is emitted by
the producer-owned gate and judged by the consumer-owned
`host/verify_certificate.py`.

Versioning follows the repository contract: MAJOR changes are incompatible; MINOR
changes add fields without invalidating records emitted under an older 1.x version.
Those fields may become mandatory when a producer explicitly selects the newer MINOR
version. A consumer rejects an unsupported MAJOR and ignores unknown fields in a
supported MAJOR. The JSON Schema therefore deliberately permits unknown properties.

## Evidence-model selector

`evidence_model` is `feature` or `group`. Omission means `feature` for compatibility.
The two result shapes are deliberately not mixed:

- `feature` uses `feature_results[]`; 1.2 uses per-result diffs, while 1.4 uses shared
  pair accounting and the revised TP/FP/FN decision described below;
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

## Feature evidence model 1.4

Certificate 1.4 keeps a single feature namespace. A result remains keyed by
`(prediction_specimen_id, feature)` and its preregistered projection is unchanged.
There is no `mixed` evidence model and no producer-declared group namespace.

The raw diff is recorded once per endpoint pair in `pair_accounting[]`, using the five
identity-bearing buckets described below. The legacy per-result `observed_diff`,
`excluded_diff`, and `unattributed_diff` arrays are not inputs to a 1.4 decision.
Every 1.4 feature result instead records endpoint evidence at each predicted address:

```json
{
  "address": {"far": "0x00400A01", "word": 52, "bit": 19},
  "before_value": 0,
  "after_value": 1,
  "observed_value": 1
}
```

`observed_value` is a compatibility summary and must equal `after_value`. The complete
address set must equal the preregistered assignment set. A matched result requires,
at every address, the recorded before/after values to equal `expected_transition` and
the after value to equal the preregistered assignment. TP and FN are computed only
from these holdout endpoint assignments and transitions, never from whether a bit
appears in the diff.

For every `(specimen_id, absolute address)`, all result records must report the same
value. A contradiction is malformed evidence. Opposite values in different specimens
are valid and are how complementary states are certified.

### Feature semantic evidence

Every 1.4 feature prediction preregisters one `semantic_assertion` of kind
`member_identity`. It names the predicted frozen member and identifies a scalar
readback value by RFC 6901 JSON pointer into the selected endpoint's pinned
attestation, together with the expected value. The certificate copies that assertion
verbatim and records a `semantic_outcome` summary. For example:

```json
{
  "kind": "member_identity",
  "semantic": true,
  "predicted_member": "CLBLL_L.SLICEL_X0.CLKINV",
  "attestation_field": "/resolved/clock_mode",
  "expected_value": "CLKINV"
}
```

The verifier resolves the pointer itself, compares the attested value with the
preregistered expectation, and rebuilds the outcome. A missing field, an unpinned
attestation, or a copied `passed` boolean inconsistent with the readback is invalid.
The assertion says what the producer claims the frozen name means; the pinned readback
makes whether the implemented specimen has that basis independently auditable. It
does not turn the naming claim into a silicon-behaviour claim.

For certificate 1.6, the scalar pointer targets in `resolved` are summaries, not an
additional producer authority. The verifier rebuilds `ff_init`, `ff_srval`, `ce_mode`,
`sr_mode`, `sr_kind`, `storage_kind`, and `clock_mode` from the complete routed cell
list, including primitive type, properties, pins and constant/non-constant nets. A
summary which agrees with the prediction but disagrees with the routed cell facts is
invalid. The full contract is in `docs/ff_attestation_contract.md`.

Holdout semantic outcomes are reported in `semantic_status` and
`semantic_accounting.member_identity`. They never contribute to address `status`.
A semantic-only failure therefore retains `status: passed`, exits zero, and prints its
semantic failure count prominently.

### Verifier-derived group consistency

The verifier rereads every consumed class rule and groups features by their complete
polarity-free coordinate set. Each member is converted to a full 0/1 codeword over
that scope. Two distinct frozen feature names carrying the same codeword are a
`frozen-group ambiguity` and make the record invalid. Group membership, polarity and
complementary relations are therefore freeze-derived facts, not producer assertions.

This derivation does not create additional address passes. Strict equality to the
preregistered feature's codeword is already the feature assignment check. In
particular, the verifier does not count codeword exclusivity or decode validity beside
that same observation.

### 1.4 FP definition and decision

FP is fixed by the profile; a producer cannot select a weaker policy:

```text
FP = ownership_unknown
   union unattributed
   union {db_attributed bits in an asserted tile that are claimed by this bit class
          and lie in no preregistered scope}
```

Each FP is counted once per `(endpoint pair, address)`. A `db_attributed` change owned
by another class, such as legal INT routing outside a CLB content assertion, does not
become this class's FP. Every `in_scope` bit must be covered at least once by the
union of preregistered scopes belonging to that endpoint pair; both endpoints covering
the same address is valid.

The 1.4 feature decision is:

```text
status = passed iff
    every committed result is present exactly once
    and every pair partition is exact
    and tp_count == committed holdout prediction count
    and fn_count == 0
    and fp_count == 0
```

`coverage.attested_count` is the number of distinct asserted class entries, not the
number of result records. `coverage.class_entry_count` remains the current manifest
denominator.

## Feature comparison lifecycle (1.5)

In 1.4, `baseline_specimen_id` made the compared endpoint explicit only in the final
certificate. It was not part of the preregistered prediction, so a producer could
choose that endpoint after the bitstreams existed. Version 1.5 closes that lifecycle
gap. The pinned `gate_predictions` artifact selects schema 1.5 or later, and every
feature prediction in it additionally requires:

```json
{"comparison_specimen_id": "SLICE_X2Y25_latch_base"}
```

The comparison specimen must be a distinct, named member of the artifact's
`specimens[]`. The prediction's `specimen_id` remains the selected feature endpoint.
For each certificate result, the verifier requires:

```text
feature_specimen_id  == committed specimen_id
baseline_specimen_id == committed comparison_specimen_id
```

The verifier derives the authoritative set of distinct unordered endpoint pairs
directly from all committed `(specimen_id, comparison_specimen_id)` values.
`pair_accounting[]` must contain that set exactly once each: no post-build pair may be
added, omitted, or substituted. Each pair's in-scope address union is likewise
derived from the committed predictions rather than from result-selected endpoints.

This rule applies to feature records selecting schema 1.5 or later. Published 1.4
feature records keep their prior lifecycle semantics. Group records compare a single
specimen's absolute assignment with a committed codeword and therefore have no second
endpoint to preregister. Historical feature 1.2 records also retain their original
decision semantics and require no erratum.

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

In 1.3 each group has exactly three assertions:

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

### Group accounting correction in 1.4

Because bit-set group members are complete codewords, pairwise-distinct codewords make
`group_exclusivity` true for every possible observation. It is therefore a vacuous
DB-consistency diagnostic, not an address pass. A codeword collision is instead the
same `frozen-group ambiguity` format failure defined above. `decode_validity` is also
a diagnostic: strict equality to the preregistered codeword entails it, so scoring both
would count one observation twice.

A 1.4 group result keeps the three preregistered assertions but carries four outcomes:

- `group_exclusivity` has `classification: vacuous`, no `passed` field, and the
  independently decoded members;
- `decode_validity` has `diagnostic: true`, a recomputed boolean, and decoded members;
- `scope_assignment` is strict preregistered codeword equality and is the sole address
  pass;
- `member_identity` remains semantic and isolated.

Accordingly, 1.4 `address_accounting` contains only
`strict_codeword_equality`. `diagnostic_accounting` records exclusivity
`vacuous_count`/`ambiguity_count` and decode-validity pass/fail counts. Neither
diagnostic contributes to `status`. Recounting Run B under this rule yields
`falsifiable 16/16`, `vacuous 16`, and semantic `16/16`; the evidence and certification
decision are unchanged.

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
summary. It also independently recomputes every label. A changed address in either
specimen's asserted group scope is `in_scope`; word 50 bits 0 through 12 are
`frame_ecc`; all other addresses are classified from every geometrically candidate
tile in `tilegrid.json` and the corresponding classified frozen segbits DBs:

- at least one candidate DB feature claims the local coordinate: `db_attributed`;
- candidates exist but none claims it: `ownership_unknown`;
- no geometric candidate exists: `unattributed`.

CLB/INT geometry may overlap, so checking only the named specimen tile is invalid.
A `db_attributed` record requires at least one claiming DB to be pinned in
`frozen_inputs.files`. Proving `ownership_unknown` requires every available candidate
segbits DB to be pinned. Prediction inputs and accounting inputs need not be the same:
Run B's out-of-scope routing changes are claimed by `segbits_int_l.db` and
`segbits_int_r.db`, so both are accounting inputs even though neither supplied a mux
prediction. `frame_ecc` is independently limited to word 50 bits 0 through 12; unlike
the feature model's exclusion record, group accounting does not require every
ECC-labelled FAR to contain another changed bit in that same pair.

A tile-wide `claim_scope: tile` cannot pass while any pair contains
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

## Current production profiles 1.2 through 1.6

The profile is selected by `profile: production`. Production consumers invoke the
verifier with `--require-production`. A legacy feature record requires certificate
1.2 or later; a group record requires 1.3 or later. Classes using shared endpoint-pair
accounting require 1.4. New feature commitments whose decision consumes a comparison
endpoint require 1.5. Emitting a lower version cannot bypass the semantic checks
selected by its record version. A historical 1.1 production fixture remains accepted
by generic validation for compatibility, but it is not current production authority.

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

The 1.4 feature profile additionally requires:

- a single complete feature commitment and no producer group namespace;
- before/after endpoint observations at every predicted address;
- a preregistered semantic assertion backed by a scalar field in the selected
  endpoint's pinned attestation, with independently rebuilt semantic accounting;
- global specimen/address observation consistency;
- one exact five-bucket accounting record per endpoint pair;
- independently recomputed bucket labels and the fixed pair-level FP rule;
- freeze-derived group/codeword consistency with collisions treated as format errors.

The 1.5 feature profile additionally requires:

- `comparison_specimen_id` on every committed prediction, naming a distinct specimen
  already present in the prediction artifact;
- `gate_predictions` and its pinned reference selecting schema 1.5 or later;
- exact result endpoint equality with both committed endpoint identities;
- an exact `pair_accounting[]` pair set and pair scope derived solely from the
  commitment.

The 1.6 formal-FF feature profile is selected only for `clb_ff_config` and additionally
requires:

- `staging_manifest: {path, sha256, schema_version}` selecting
  `specimen_staging` 1.0;
- exact set equality among the commitment's specimen plan, the staging manifest,
  the staging-root directories and the certificate's `specimens[]`;
- exactly `<staging-root>/<specimen_id>/{spec.bit,attestation.json}` for every
  committed specimen, with no extra directory, file, ID or duplicate path;
- `specimen_attestation` 2.0 on every specimen. Its embedded completed source stamp,
  source hashes, bitstream hash, routed multi-cell facts, checkpoint and semantic
  summaries are independently cross-checked;
- for a derived specimen, equality among its embedded `derived_from`, checkpoint
  source, and the independently pinned source specimen's `base.dcp` hash;
- repository-relative paths for the commitment, staging manifest, staged bitstreams,
  and attestations. Absolute strings may remain inside raw `tclargs` solely as
  invocation history; they are not artifact references.

Within attestation 2.0, `requested` is pinned producer intent. Equality with
`resolved` detects an internally contradictory record; it is not an independent
readback proving that Vivado received the request. Likewise, `resolved.nets` preserves
routed facts but the host does not reconstruct the producer's dedicated-net set or
pairwise tier-2 equality from them. Those remain producer-gate claims, while the host's
independent checks derive the required cell topology and semantic summaries from the
routed `resolved.cells` facts.

Exact staging is indivisible for the selected commitment. In particular, the public
184-specimen FF commitment cannot have a valid 23-specimen mine-only staging manifest.
Mine attestations may be checked individually and staging conformance may use the
consumer-owned synthetic commitment, but creating a reduced `predictions.json` is not
an accepted substitute for the public commitment.

The host can verify those preserved facts. It cannot observe that the producer called
a function named `verified_state()`, nor prove a DCP produced a bitstream. No boolean
field is accepted as a substitute for either fact: the former is represented by the
completed stamp and hashes the function is meant to check, and the latter remains an
explicit integrity-anchor limitation.

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

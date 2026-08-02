# Round 6 request — certificate 1.3, group-scoped assertions

Producer → author. `clb_mux` is measured and passing, but it cannot be certified:
certificate 1.2 models a per-feature list of bit assignments, and a mux claim is not
that shape. This is the ask for the extension.

Everything below can be written against two committed artifacts, no Vivado and no
producer source:

```
gate_runs/run_2026_08_02_b/predictions.json    schema gate_predictions 1.1.0
gate_runs/run_2026_08_02_b/measurement.json    schema gate_measurement 1.1.0
```

Both are real output of the run described in `7d73915`, not mock-ups.

## Why 1.2 does not fit

A `clb_lut_init` claim is "this feature owns this bit, and it went 0→1". A `clb_mux`
claim is about a **group** — a set of features sharing one bit field — and has three
parts that are deliberately separate:

| assertion | `semantic` | what it claims |
|---|---|---|
| `group_exclusivity` | false | at most one member of the group decodes |
| `scope_assignment` | false | every bit of the group's **complete** bit set holds its predicted value |
| `member_identity` | **true** | the decoded member is the one whose *name* matches the netlist edge that was built |

The third is a claim about the **database's naming**, not about hardware. It must be
scored and reported, and it must **not** contribute to the production decision. Mixing
it in would let a naming discrepancy sink an addressing result, or worse, let a passing
naming result paper over one.

## What the record needs

1. **`group_results[]`** keyed by `(prediction_specimen_id, group)` — the join key here
   is the group label, not a feature name, and the same group appears in many
   specimens. Each carries the preregistered projection verbatim (`group`, `split`,
   `rule_file`, `scope`, `assertions`) plus the observed outcome per assertion.
2. **`scope`** as the complete bit-address set: `segbit` plus `{far, word, bit}` for
   every bit of the group, including the ones that do not change. A certificate whose
   scope lists only the movers must be rejected — see the adversarial fixture below.
3. **Per-pair accounting**, shape already in `measurement.json.accounting[]`:
   `raw_diff_bits`, `in_scope`, `frame_ecc`, `db_attributed`, `ownership_unknown`,
   `unattributed`, `partition_exact`.
4. **`prediction_commitment`** exactly as in 1.2 — unchanged, still pinned and
   compared.

## Verification rules requested

- **Recompute the scope from the frozen db.** The group's complete bit set is derivable
  from `rule_file`: the maximal set of features sharing an identical bit-address set
  (`docs/mux_groups.md` — group membership is defined by bits, never by name). A
  certificate's declared scope must equal it. This is the check that makes rule 2 real.
- **Recompute assert-iff** from the rule file: a member decodes iff every non-negated
  bit is 1 and every negated bit is 0. The certificate's expected assignment must match
  what the frozen rule implies for the claimed member.
- **Semantic isolation.** `member_identity` results are reported but excluded from the
  pass/fail decision. A certificate that folds them in should be rejected as malformed
  rather than accepted as stricter.
- **Partition integrity.** Buckets must be pairwise disjoint and their sizes must sum to
  `raw_diff_bits`, with `partition_exact` consistent with that arithmetic. Note the
  honest limit: without the bitstreams a verifier cannot confirm the raw diff itself —
  it can only confirm internal consistency plus the attestation's pinned bitstream
  hashes. Please state that limit in the schema doc rather than let it be assumed away.
- **Tile-wide claims are forbidden while ownership is unknown.** If a certificate ever
  declares a tile-wide scope, any `ownership_unknown` bit inside that tile's geometric
  range must force FAIL. Run B declares only group scopes, so this rule has nothing to
  bite on yet — which is exactly when it should be written.
- **Holdout completeness** by `(specimen_id, group)` pairs, same discipline as 1.2:
  every committed holdout pair reported exactly once.

## Fixtures requested

Positive: one conforming group-scoped pass.

Negative, in rough order of how much they matter:

1. **Truncated scope** — scope lists only the two bits that move, omitting the two that
   do not. Everything else self-consistent. Must FAIL.
2. **Two members decode** — a `group_exclusivity` violation, i.e. the composition rule
   broken. Must FAIL.
3. **Semantic-only failure** — `member_identity` wrong, both address assertions
   correct. Must **PASS** the address decision while reporting the semantic failure
   loudly. This one is the point of the separation.
4. **Bucket overlap / uncovered bit** — a bit in two buckets, and a `raw_diff_bits`
   larger than the buckets sum. Both must FAIL.
5. **Name-derived grouping** — a scope assembled from the `AFFMUX.` name prefix instead
   of the bit set. It happens to coincide for `AFFMUX`; build it for `CARRY4`, where
   the four members sit on four different bits, and it must FAIL.

## Measured numbers for reference

Run B: 24 specimens (16 holdout) over `CLBLL_L` and `CLBLM_L`, SLICEL and SLICEM, all
four slice positions. Holdout `group_exclusivity` 16/16, `scope_assignment` 16/16,
`member_identity` 16/16, and all 12 variant pairs partition-exact with zero
unattributed bits. `in_scope` is 2 in every pair — `O6` and the bypass member differ in
two of the group's four bits, and the other two are scored anyway. That is the whole
reason scope is the complete set.

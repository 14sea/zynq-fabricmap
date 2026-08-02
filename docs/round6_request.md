# Round 6 request — certificate 1.3, group-scoped assertions

Producer → author. `clb_mux` is measured and passing, but it cannot be certified:
certificate 1.2 models a per-feature list of bit assignments, and a mux claim is not
that shape. This is the ask for the extension.

Everything below can be written against committed artifacts alone — no Vivado, no
producer source:

```
gate_runs/run_2026_08_02_b/predictions.json        gate_predictions 1.1.0
gate_runs/run_2026_08_02_b/measurement.json        gate_measurement 1.1.0
gate_runs/run_2026_08_02_b/attestations/*.json     specimen_attestation 1.0.0 (24)
```

All real output, not mock-ups. **An earlier draft of this request claimed the same and
was wrong**; the author's review caught three gaps and they are now closed:

- `results[]` carries one record per `(specimen_id, group)` — decoded members, the
  absolute observed assignment for **every** scope bit (expected and observed side by
  side), and an outcome per assertion — recorded whether it passed or failed. Recording
  only failures makes a passing run unauditable, which is exactly when someone wants to
  audit it.
- `accounting[].buckets` carries **bit identity**, not just counts: every bucket lists
  its `{far, word, bit}` entries, so disjointness and coverage can be checked directly
  instead of inferred from arithmetic.
- `specimens[]` carries `bitstream_sha256` and an `attestation` reference (path,
  sha256, resolved LOC/BEL, `pin_mapping_is_identity`), and the measure step fails the
  run if a bitstream does not match its attestation.

The attestations are **copied into the run directory** and referenced there. They are
produced under `build/`, which is gitignored, so a record pointing at them would name
evidence a fresh clone cannot resolve. The same fix was applied to
`run_2026_08_02_a`'s certificate, which had the identical defect.

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
   `raw_diff_bits`, `counts{}` per bucket, `buckets{}` with the `{far, word, bit}`
   entries of each, and `partition_exact`.
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
- **Partition integrity, from the bit lists.** `buckets{}` carries every bit's
  identity, so check disjointness directly — pairwise empty intersections — and check
  that the union's size equals `raw_diff_bits` and each `counts{}` entry equals its
  list length. Do not settle for the arithmetic alone; that was the gap that made the
  first version of this request unimplementable.
  The honest limit remains: without the bitstreams a verifier cannot confirm the raw
  diff *itself* — it confirms internal consistency plus the attestation's pinned
  bitstream hashes. Please state that limit in the schema doc rather than let it be
  assumed away.
- **Tile-wide claims are forbidden while ownership is unknown.** If a certificate ever
  declares a tile-wide scope, any `ownership_unknown` bit inside that tile's geometric
  range must force FAIL. Run B declares only group scopes, and after the padding fix
  below its `ownership_unknown` count is **zero**, so the rule has nothing to bite on —
  which is exactly when it should be written.

  **Correction, 2026-08-02:** an earlier version of run B's measurement reported 136
  `ownership_unknown` bits. They were an artifact: `specimen_diff.locate()` built the
  segbit coordinate with an unpadded frame offset, so everything in frames `00`–`09`
  missed the database. Same `%02d_%02d` ambiguity that broke the verifier in round 4.
  The re-measured artifact in this repo has `db_attributed` 328 and
  `ownership_unknown` 0; the decision, the partition exactness and every assertion
  count are unchanged. If you already coded against the old numbers, re-pull.
- **Holdout completeness** by `(specimen_id, group)` pairs, same discipline as 1.2:
  every committed holdout pair reported exactly once.

### Semantic evidence — auditable, still outside the decision

`member_identity` names a netlist edge, so reporting it as passing is only meaningful
if the edge is in the record. Each result carries `netlist_basis` (the pre-registered
sentence, verbatim), `expected_edge` (derived from it), and `attested_edge` (read back
from the routed checkpoint: `ff_bel`, `ff_d_net`, `ff_d_driver_pin`,
`ff_d_driver_cell`, `ff_d_driver_ref`, `ff_d_source_port`,
`ff_d_source_package_pin`, `ff_d_net_route_status`, `checkpoint`).

Both variants are proved **positively**. `ffsrc=0` requires `driver_ref == LUT6` *and*
`driver_cell` to be the LUT under test; `ffsrc=1` requires `driver_ref == IBUF` *and* a
top-level source port on a named package pin. "Not a LUT6" would be satisfied by
anything and is not used.

Requested verifier behaviour:

- `attested_edge.checkpoint` must equal the attestation's top-level `checkpoint` hash;
- `ff_d_net_route_status` must be `ROUTED`;
- rebuild `expected_edge` independently from `netlist_basis` rather than reading the
  producer's copy;
- recompute consistency from `expected_edge` + `attested_edge`.
  `netlist_basis_consistent` in the record is a **summary only** and must never be
  trusted as the check.
- The result stays **out of the address production decision** either way.

**Limit to state in the schema doc, not to assume away:** hashing the DCP and the
bitstream together pins both against later substitution. It does *not* independently
prove the bitstream was produced from that checkpoint — that link is asserted by the
attestation and can only be re-established by rebuilding with Vivado. Treat the
checkpoint hash as an integrity anchor, not as provenance proof.

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

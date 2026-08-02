# Evidence contract — producer answers to the round 2 schema questions

`docs/round2_handoff.md` asks two questions that must be settled before a production
certificate is emitted. Both are producer-side facts, so this document answers them
with what the harness now actually produces; the schema change itself is the
consumer's to make, under the MAJOR/MINOR policy.

Both answers follow the same principle: **a hash of the recipe proves what was asked
for, and an omission proves nothing at all.** Evidence must be read back from the tool
and listed, so a consumer can recompute it.

## 1. Implementation freedom — `specimen_attestation` 1.0.0

`build/<dir>/attestation.json`, produced by `scripts/specimen_attest.py` from the
`placement.json` the Tcl writes out of the **routed design**:

```json
{
  "schema": "specimen_attestation", "schema_version": "1.0.0",
  "inputs": {
    "files": {"vivado/specimen/specimen_lut.v": "<sha256>",
              "vivado/specimen/build_specimen.tcl": "<sha256>"},
    "tclargs": ["SLICE_X2Y25", "A6LUT", "0000000000000000", "0000000000000002"],
    "part": "xc7z010clg400-1", "vivado_version": "2025.2"
  },
  "resolved": {
    "requested_site": "SLICE_X2Y25", "resolved_loc": "SLICE_X2Y25",
    "requested_bel": "A6LUT",        "resolved_bel": "SLICEL.A6LUT",
    "tile": "CLBLL_L_X2Y25",
    "lock_pins": "I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6",
    "pin_mapping": {"I0": "SLICE_X2Y25/A6LUT/A1", "...": "..."},
    "pin_mapping_is_identity": true
  },
  "outputs": {"spec_<init>.bit": "<sha256>", "...": "..."}
}
```

Three things matter about this shape:

- **`resolved` is read back, not restated.** The Tcl queries `get_property LOC/BEL/
  LOCK_PINS` and `get_bel_pins -of_objects [get_pins target/I*]` on the routed design.
  A `LOCK_PINS` constraint in a hashed script proves only that it was requested;
  `pin_mapping` proves the tool honoured it. That distinction is the whole point —
  the pin-swapping trap in `docs/specimen_harness.md` would pass a recipe-hash check.
- **`pin_mapping_is_identity` is computed, and its absence is fatal, not cosmetic.**
  `specimen_attest.py` exits non-zero when the mapping is not `I{k} -> A{k+1}`, and
  records a warning inside the attestation saying that interior INIT-bit predictions
  are invalid unless the permutation is applied.
- **Inputs and outputs are in the same record**, so a certificate that pins
  `attestation_sha256` transitively pins the HDL, the Tcl, the arguments, the part,
  the tool version, the resolved placement and every bitstream measured.

**Ask of the consumer:** add to `specimens[]` a required
`attestation: {path, sha256, schema_version}` and verify (a) the file hashes to the
pinned value, (b) `resolved_loc`/`tile` agree with the `loc_site`/`tile` the specimen
record already declares, (c) `bitstream_sha256` appears in `outputs`, and (d) for any
`clb_lut_init` result, `pin_mapping_is_identity` is true — or a permutation is stated
and applied. A certificate whose attestation is absent should be rejected outright
rather than treated as a weaker pass.

## 2. ECC exclusion — listed, ruled, and cross-checked

`scripts/specimen_diff.py` no longer drops ECC bits. Every diff now carries:

```json
"exclusion_rules": [{"reason": "frame_ecc",
                     "rule": "word == 50 and 0 <= bit <= 12",
                     "why": "the frame ECC field is recomputed whenever any other bit
                             in the same frame changes"}],
"excluded_diff": [{"far": "0x00400a21", "word": 50, "bit": 3,
                   "before": 0, "after": 1, "reason": "frame_ecc", "rule": "..."}],
"findings": []
```

So the record is complete: `observed_diff ∪ excluded_diff` is every bit that moved,
and the rule that separates them is data rather than an implementation detail.

The differ also enforces the rule's own rationale. ECC bits are excluded *because*
they are recomputed when something else in the frame changes — therefore an ECC change
in a frame with **no** other change is not covered by that justification. Such a frame
becomes a `findings[]` entry instead of a silent exclusion.

**Ask of the consumer:** `verify_certificate.py` should check that (a) every excluded
bit satisfies the stated rule, (b) `observed_diff` and `excluded_diff` are disjoint,
(c) no excluded bit is also a predicted bit, and (d) every frame appearing in
`excluded_diff` also appears in `observed_diff` — i.e. reject an ECC-only frame. That
is a full independent re-derivation of the exclusion from the record alone.

Optional, stronger: recompute the 13-bit frame ECC from the frame contents and check
the observed value. That turns "these bits are ECC-shaped" into "these bits are the
correct ECC". It is not proposed as mandatory for 1.1.0 because the payoff is small
next to (a)-(d), but the producer can supply frame contents in the record if the
consumer wants it.

## 2b. What hashing the checkpoint does and does not prove

`specimen_attestation` now also carries `checkpoint: {file: base.dcp, sha256}`, so a
semantic claim's readback is bound to the routed design it was taken from.

State the limit precisely, because the strong reading is tempting and wrong. Hashing
the DCP and the bitstream together **pins both against later substitution** — neither
can be swapped without breaking the record. It does **not** independently prove that
the bitstream was produced from that checkpoint. Nothing in the artifacts establishes
that link; it is *asserted* by the attestation, and re-establishing it means rebuilding
with Vivado, which is exactly what a consumer-side verifier cannot do.

So a verifier should treat the checkpoint hash as an integrity anchor, not as
provenance proof, and say so where the claim is recorded.

## 3. Version note

Both items add required evidence, so under the compatibility policy they cannot be
retrofitted into `fabric_bit_class_certificate` 1.0.0 as semantics. The producer's
recommendation is a **`1.1.0` with the fields optional-but-verified-if-present**,
immediately followed by making them required in the first production profile — so the
existing conformance fixtures stay valid while no real certificate can omit them.

## 4. Producer-side documentation state

`docs/freeze_format.md` §5.6 has been corrected: the 101-word frame geometry is no
longer "an assumption pending the first specimen run". It was discharged by
`scripts/bitstream_frames.py` against real bitstreams — 5,144 frames from `part.yaml`
plus 8 pad frames, at 101 words each, consume the FDRI payload exactly. The finding
was correctly reported by the consumer side; the inconsistency was ours.

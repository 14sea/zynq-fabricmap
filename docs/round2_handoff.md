# Round 2 nonempty-prediction fixture handoff

This consumer-side follow-up was written against `docs/freeze_format.md`,
`docs/certificate_schema.md`, the machine-readable certificate schema, and frozen
data only. The producer-owned frame parser, differ, specimen RTL/Tcl and run script
were not read or imported.

## Delivered

- `tests/fixtures/certificate_segbits_pass.json` — a conforming nonempty prediction
  for frozen feature `CLBLL_L.SLICEL_X0.ALUT.INIT[01] 33_15` instantiated at
  `CLBLL_L_X2Y25`: `FAR 0x00400A21`, word 51, bit 15, expected value 1. Its observed
  assignment matches, so holdout accounting is TP=1, FP=0, FN=0.
- `tests/fixtures/certificate_segbits_fail.json` — the same correct frozen prediction
  with observed value 0 and no observed transition. This is a well-formed failed
  certification with TP=0, FP=0, FN=1.
- `tests/test_round2.py` — four tests that exercise the verifier paths skipped by the
  original empty ppip fixtures:
  1. the nonempty pass conforms;
  2. the nonempty failed record conforms under `--allow-failed`;
  3. a prediction changed coherently to `32_15` keeps its evidence and absolute
     arithmetic internally consistent but is rejected by complete frozen-rule
     comparison;
  4. a prediction retaining the correct `33_15` coordinate but changed coherently to
     the wrong FAR is rejected by normative address arithmetic.

The obvious synthetic hashes identify these as schema conformance records, not
Vivado evidence or production certificates. Choosing INIT[01], rather than
permutation-invariant INIT[00]/INIT[63], deliberately exercises an interior LUT INIT
bit implicated by the measured input-pin-swapping trap.

## Commands run

```sh
python3 host/verify_certificate.py tests/fixtures/certificate_segbits_pass.json
python3 host/verify_certificate.py \
  tests/fixtures/certificate_segbits_fail.json --allow-failed
python3 -m unittest -v tests/test_round1.py tests/test_round2.py
python3 -m py_compile tests/test_round2.py
git diff --check
```

Round 2 result: 4 tests passed. Combined consumer result: 13 tests passed.

## Schema decisions required before the first production certificate

The real harness findings expose two evidence classes not represented explicitly by
certificate 1.0.0. They should be resolved before a production certificate is
accepted, but this fixture-only drop does not silently revise a frozen schema:

1. **Implementation freedom.** `specimens[].design_source_sha256` does not state
   whether the Tcl/XDC constraints containing mandatory `LOCK_PINS` are inside the
   hash domain. Either define a canonical design-input bundle hash that covers RTL,
   Tcl/XDC and generated constraints, or record and verify a separate implementation-
   constraints hash plus the resolved pin mapping. Otherwise the certificate cannot
   demonstrate that the measured feature index was protected from permutation.
2. **ECC exclusion.** Certificate 1.0.0 says `observed_diff[]` records every changed
   address, while the harness correctly removes frame-ECC changes from attribution.
   A certificate needs an explicit excluded-diff list/classification, and the host
   verifier should independently permit `frame_ecc` only at word 50 bits 0..12.
   Silently omitting ECC bits makes the record incomplete; including them as ordinary
   observed diff turns them into false positives.

Because validators and conformance fixtures already exist, making either item
mandatory requires an explicit schema-version decision under the MAJOR/MINOR policy;
it should not be smuggled into 1.0.0 as an undocumented semantic change.

There is also a documentation-state mismatch owned by the producer side:
`docs/specimen_harness.md` says frame geometry is discharged, while
`docs/freeze_format.md` section 5.6 still says it is awaiting the first specimen run.
The normative freeze document should be updated before the next consumer round.

No commit or push was performed by the author.

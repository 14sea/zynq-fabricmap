# B2 pin-table correction acceptance artifacts — 2026-09-12

Reviewed HEAD: `23b1dfd`. These are offline review results, not board evidence or a
real qualification. Only temporary copies are mutated; model/test ruling documents
are inert and never consumed.

- `coverage_after.json`: unchanged previous `probe_coverage.py` on the correction.
- `inputs_after.json`: unchanged previous `probe_inputs.py`, including the valid
  real-pins preflight and model CLI/qualification chain.
- `probe_all_twelve.py` and `all_twelve.json`: independent exhaustive mutation/deletion
  matrix for the twelve paths listed in the original coverage finding. Both APIs
  refuse all 24 cases, and both positive controls pass.
- `preserved_inputs.json`: live build check, B1 pin count and artifact hashes.
- `focused_suite.log`: 402 tests, zero skips, OK in 493.115 seconds.

To repeat the probes from this checkout:

```sh
python3 evidence/b2/review_pins_2026_09_12/probe_coverage.py
python3 evidence/b2/review_pins_2026_09_12/probe_inputs.py
python3 evidence/b2/review_pins_acceptance_2026_09_12/probe_all_twelve.py <coverage-temporary-artifacts-directory>
```

Use the first script's printed `temporary_artifacts` path for the matrix argument.
The scripts require the existing image and instrument. The coverage probe builds only
a temporary native harness. The preflight doubles only boundary establishment and
`sb` discovery; it opens no serial port and executes no runner session.

See [the acceptance review](../../../docs/b2_pins_acceptance_2026_09_12.md).

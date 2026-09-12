# B2 pin review artifacts — 2026-09-12

Reviewed HEAD: `06ef938d37eabd4a717c5fe947257eaed40635f6`.
All probes are offline. They mutate temporary copies, never the checked-out sources,
instrument, production manifest, image, original evidence or real rulings.

- `probe_coverage.py` and `coverage.json`: valid mirrored S1 manifest/table, native
  hostapp build/startup positive control, omitted-dependency mutations, and
  already-pinned/new-glob-member controls. Manifest verification uses fresh Python
  processes. Manifest/table bytes remain unchanged across cases.
- `probe_inputs.py` and `inputs_and_positive_flow.json`: manifest-block type tests
  via pin API, lifecycle API and CLI; valid preflight with the real pins hook; the
  model CLI verdict/files and real qualification re-adjudication. Only boundary
  establishment and `sb` discovery are doubled in preflight.
- `preserved_inputs.json`: build-verifier result, B1 pin count and preserved hashes.
- `focused_suite.log`: 401 tests, zero skips, OK in 490.341 seconds.

To repeat from this checkout with its existing instrument and built image available:

```sh
python3 evidence/b2/review_pins_2026_09_12/probe_coverage.py
python3 evidence/b2/review_pins_2026_09_12/probe_inputs.py
```

The scripts print results and temporary artifact locations. The coverage probe invokes
the native host compiler for its temporary harness; it does not rebuild the ARM image.
The second probe uses inert model/test ruling documents, opens no serial port,
consumes no authorization, and creates no real qualification.

Mutation results are descriptive rather than asserted to equal defective behavior,
so corrected named refusals can be inspected after a repair without historical final
assertions stopping the reproducer. Positive controls must continue to pass.

See [the review](../../../docs/b2_pins_review_2026_09_12.md) for findings and limits.

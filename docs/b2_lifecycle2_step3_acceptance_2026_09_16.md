# Acceptance — B2 lifecycle 2 step 3

Reviewed `b2-lifecycle-2` at `8de4dfc`.

## Result: PASS

`manifests/b2_instrument_pins.json` hashes to `82a5f2fb…`, is exactly the object produced by
`b2_pins.generate()`, and contains 71 entries for 71 matching files.  Every digest matches the
current tree.  The only changes from lifecycle 1 are the three reviewed files:

- `host/b2_manifest.py`
- `tests/test_b2_lifecycle.py`
- `tests/test_b2_plan.py`

The old S3 manifest remains byte-identical at `5d2312c3…`; its refusal against the new table is
the expected between-transition state.

An in-memory production-init preview verifies at S0 with the new table, accurate image note,
unfrozen preregistration, `board_ready=false`, and null qualification/calibration/plan with an
empty history.  The preview hash is diagnostic and is not a lifecycle binding.

## Authorization: step 4 only

Run:

```sh
python3 -B host/b2_manifest.py init --image-evidence evidence/b2/build_evidence.json
```

Commit the generated S0 manifest and the step-4 record.  Then report the actual committed
manifest digest and a fresh-process verification showing S0, `qualified=false`, `refusal=null`,
the `82a5f2fb…` table pin, the accepted image identity/note, an unfrozen null prereg digest,
`board_ready=false`, null qualification/calibration/plan, and empty history.

This does not authorize the step-5 suite/proof, S1, a ruling, push, port or board access.

# B2 pin-table review — 2026-09-12

Reviewed HEAD: `06ef938d37eabd4a717c5fe947257eaed40635f6`, nineteen commits
ahead of `origin/main` (`0d294ea`). Prior P3 corrections are in `3d67e3f`.

**The three previous P3 findings are CLOSED. The new pin-table implementation remains
HOLD for the two P2 findings below.** Normal integration works. Independent focused
suite: **401 tests, zero skips, OK in 490.341 seconds**. This is not a full-repository
clean-tree report; review artifacts were written while the focused suite ran.

## P2-1: the table omits application-harness and local BSP inputs

`host/b2_pins.py:31` selects the Python hostapp test but omits the files that test
actually compiles and executes. Twelve tracked inputs are outside the table:

- `tb/b2/hostapp/hostapp.c`, `tb/b2/hostapp/build.sh`, and its six `hostbsp/*.h` files.
- `firmware/b2/bsp/src/console.c` and its three `bsp/include/*.h` files.

Hashing `tests/test_b2_hostapp.py` does not hash the C harness, build script or fake
BSP that determine what the test executes. This contradicts the stated coverage of
the whole decision surface, including the tests guarding the image. B1's table already
includes its equivalent harness and local BSP inputs.

An independent probe copies the actual table, its files, the S1 fixture's referenced
inputs and these omitted files into a temporary mirror. The baseline passes both
`b2_pins.verify` and **fresh-process `b2_manifest.verify`**. The native harness builds
and executes `startup_valid` successfully. With the **same manifest bytes and same
table bytes**, independent mutations then produce:

| Mutation | Pin verification | Fresh-process manifest verification | Native harness build |
|---|---|---|---|
| Insert `#error REVIEW_PIN_COVERAGE_MUTATION` in `hostapp.c` | ACCEPTED | ACCEPTED, S1 | Fails, rc 1 |
| Insert `exit 73` at the start of hostapp `build.sh` | ACCEPTED | ACCEPTED, S1 | Fails, rc 73 |
| Insert the same `#error` in hostapp `xil_io.h` | ACCEPTED | ACCEPTED, S1 | Fails, rc 1 |
| Change local BSP `console.c` | ACCEPTED | ACCEPTED, S1 | Not exercised here |
| Change local BSP `xparameters.h` | ACCEPTED | ACCEPTED, S1 | Not exercised here |
| Change pinned `host/b2_records.py` | REFUSED | REFUSED | Not needed |
| Change pinned `tests/test_b2_hostapp.py` | REFUSED | REFUSED | Not needed |
| Add unlisted `host/b2_review_new.py` | REFUSED | REFUSED | Not needed |

The unchanged table digest is
`c2d78cf2231b48a7ee62aa16efac47ccf32aaaa7bb52c2cec08b9b94338c5610`.
No manifest/table rehashing or verifier double enables the accepted mutations.
Only temporary copies are changed and each is restored before the next case.

The runner also has a separate build-evidence guard. These BSP probes establish
pin-table and lifecycle acceptance, **not** passage through every live preflight
check or a change to the built image. Hostapp inputs are not ARM build inputs, so
the ARM build-evidence guard does not substitute for their inclusion in the table.

Required correction: include the local BSP and hostapp dependency paths, regenerate
the table, and add explicit coverage expectations plus mutation/deletion tests over
those actual paths. Preserve a valid mirror and native-build positive control.

## P2-2: malformed instrument_pins raises instead of refusing

`host/b2_pins.py:78` calls `.get("sha256")` before establishing that the new
`instrument_pins` value is an object:

```python
pinned = (manifest.get("instrument_pins") or {}).get("sha256")
```

On an otherwise valid S1 manifest, replace only that field with `"broken"`, `[{}]`,
`true`, or `7`. All four produce **AttributeError** through both `b2_pins.verify`
and `b2_manifest.verify`. The pin CLI prints a traceback and exits 1 instead of its
documented `REFUSED` exit 2. The lifecycle wrapper catches only `PinRefusal`
(`host/b2_manifest.py:569`), so the unexpected exception propagates. Empty-object
and missing-field controls produce named refusals and exit 2.

This remains a stop, not a false acceptance or board authorization. Ordinary malformed
input escapes the input-refusal contract and is reported as a program failure,
repeating the type-before-use issue fixed in earlier tools.

Required correction: establish the manifest and new block's object shapes, then the
digest's type/domain, before lookup or use. Raise `PinRefusal` for invalid input and
preserve the existing adapters. Do not classify arbitrary implementation exceptions
as input refusals. Cover public API, lifecycle and CLI, retaining a valid manifest.

## Positive integration and prior corrections

- The committed table verifies **57 files**; B1's table verifies **105**.
- Read-only B2Q preflight accepts a valid S1 fixture using the **real pins hook** and
  real manifest/image/build/lineage checks. Only principal-boundary validation and
  `sb` discovery are doubled. No pins, replay or verdict check is doubled, and no
  evidence directory is created by preflight.
- The model CLI exits 0, reports `verdict.outcome: PASS`, and writes both
  `adjudication.json` and `summary.json` with PASS. Real `qualify` with the real
  `readjudicator` accepts its evidence. Model calibration remains 4490.856163729762/h,
  two sessions with at most seven pairs each. This is not a real qualification.
- CRC wording, the eleven-negative count, the four-pair example and the CLI/seed
  documentation corrections are present. The three previous P3 findings are closed.

## Remaining documentation drift and scope

The current package banner says **56 files**; the actual table verifies **57**. It
also lists the B2 map-utility demonstration as absent, although the previous reviewed
2,406-record non-first-slice demonstration remains accepted for that scope. Do not
repeat it merely to close the same item. It did not demonstrate a complete nine-pair
instrument-stack experiment or pooled primary.

`host/b2_runner.py` still says pins do not exist, explicit B2Q seeds are unsupported,
and no positive lifecycle or runner PASS has been demonstrated. These are obsolete
module-level statements. Correct them with the implementation fixes before regenerating
the table, so its source hashes include the documentation correction.

Live build verification returns zero findings. Image `d164cd1d…`, ELF `7de96ed2…`,
and B1 manifest `38238271…fd4ba8` retain their hashes; all 105 B1 pins verify.
Only English review artifacts and the package banner were written. No production
code, firmware, image, original evidence, manifest, real ruling or instrument file
was changed. No commit, push, ARM rebuild, port access or board action was performed.
`b2_test_report` and final package review remain pending.

Artifacts: [independent probes and outputs](../evidence/b2/review_pins_2026_09_12/).

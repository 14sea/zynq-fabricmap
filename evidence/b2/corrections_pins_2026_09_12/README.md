# The pin table's two P2s — corrected, 2026-09-12

The owner's pin-table review (`docs/b2_pins_review_2026_09_12.md`, against `06ef938`).
`review_probes_after.txt` is that review's own `probe_coverage.py` and `probe_inputs.py`,
**unchanged**, re-run on the corrected table and code.

## P2-1 — the table omitted what its own pinned harness compiles and runs

Twelve tracked inputs were outside the table: `tb/b2/hostapp/hostapp.c`, its `build.sh` and six
`hostbsp/*.h`, and this repository's `firmware/b2/bsp/src/console.c` with three
`bsp/include/*.h`. Hashing `tests/test_b2_hostapp.py` does not hash the C harness, the build
script or the fake BSP that decide what that test executes, and the BSP sources decide what the
image *is*. Five globs added; the table goes from **57 to 69 files**.

The review's own probe now reports `omitted: []`, and every mutation it demonstrated is refused —
at the pin layer and through fresh-process manifest verification alike:

| the review's mutation | before | now |
|---|---|---|
| `#error` in `tb/b2/hostapp/hostapp.c` | ACCEPTED / ACCEPTED | **REFUSED / REFUSED** |
| `exit 73` in hostapp `build.sh` | ACCEPTED / ACCEPTED | **REFUSED / REFUSED** |
| `#error` in hostapp `xil_io.h` | ACCEPTED / ACCEPTED | **REFUSED / REFUSED** |
| `firmware/b2/bsp/src/console.c` changed | ACCEPTED / ACCEPTED | **REFUSED / REFUSED** |
| `firmware/b2/bsp/include/xparameters.h` changed | ACCEPTED / ACCEPTED | **REFUSED / REFUSED** |
| `host/b2_records.py`, `tests/test_b2_hostapp.py`, an unlisted new file | REFUSED | unchanged |

## P2-2 — type before use, a rule this tool skipped

`(manifest.get("instrument_pins") or {}).get("sha256")` looked up before establishing the value
was an object, so `"broken"`, `[{}]`, `true` and `7` raised **AttributeError** through
`b2_pins.verify` and `b2_manifest.verify`, and the CLI printed a traceback and exited 1 instead
of its documented `REFUSED` exit 2. This is the same type-before-use rule the earlier tools were
corrected to; it should not have needed a second review to reach this one.

Corrected: the manifest must be an object, `instrument_pins` must be an object, and its `sha256`
must be 64 lower-case hex — each a named `PinRefusal`, checked in that order before any lookup.
The distinction the review asked for is preserved: a malformed input is a refusal, and an
implementation exception is never dressed up as one.

## Tests

6 pin tests, **B2/B3 402, zero skips**: the generated table is asserted to contain the harness,
its build script, its stub headers and the local BSP inputs by name; fourteen malformed
`instrument_pins` values and three malformed manifests are each a named refusal; and four of them
are driven through both `b2_manifest.verify` and the CLI as a subprocess, requiring exit 2, a
`REFUSED:` line and **no traceback**.

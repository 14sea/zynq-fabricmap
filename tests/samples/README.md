# Sample producer artifacts — frozen reference shapes

Real output of the committed harness, not hand-written mock-ups. They exist because
the consumer side has to pin verification rules to these shapes, and the artifacts
themselves live under `build/`, which is gitignored — so without this directory the
only way to see them would be to run Vivado.

| file | produced by | pins |
|---|---|---|
| `placement.sample.json` | `vivado/specimen/build_specimen.tcl` (read back from the routed design) | what the tool did |
| `specimen_attestation.sample.json` | `scripts/specimen_attest.py` | inputs + resolved placement + output bitstream hashes |
| `specimen_diff.sample.json` | `scripts/specimen_diff.py` | classified changed bits, incl. `exclusion_rules[]` / `excluded_diff[]` / `findings[]` |

Provenance: Vivado 2025.2, part `xc7z010clg400-1`, one LUT6 at `SLICE_X2Y25`
(`CLBLL_L_X2Y25`, BEL `A6LUT`), `LOCK_PINS` identity, variants
`INIT=0x0…0` vs `INIT=0x0…2`. The diff shows the real result: 1 attributed bit
(`0x00400a21` word 51 bit 15 = segbit `33_15` = `CLBLL_L.SLICEL_X0.ALUT.INIT[01]`),
9 excluded frame-ECC bits, 0 unattributed.

**Shape freeze.** These record shapes are frozen as of commit `19e9db7` while the
consumer side builds `certificate` 1.1.0 against them. A producer change to any of
these shapes goes through a review round first — verification rules pinned to a shape
that moves underneath them are worse than no rules at all.

To regenerate:

```sh
mkdir -p build/spec && cd build/spec
../../scripts/run_vivado.sh -mode batch -nojournal -source \
  ../../vivado/specimen/build_specimen.tcl \
  -tclargs "$PWD" SLICE_X2Y25 A6LUT 0000000000000000 0000000000000002
cd ../..
scripts/specimen_attest.py --dir build/spec \
  --tclargs SLICE_X2Y25 A6LUT 0000000000000000 0000000000000002
scripts/specimen_diff.py --base build/spec/spec_0000000000000000.bit \
                         --variant build/spec/spec_0000000000000002.bit \
                         --json build/spec/diff.json
```

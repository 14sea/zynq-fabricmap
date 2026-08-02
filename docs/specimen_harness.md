# Specimen-diff harness — how a bit gets measured

The producer half of the prediction gate: build two bitstreams that differ by one
intended configuration change, and report which configuration bits actually moved, in
the `(FAR, word, bit)` coordinates `docs/freeze_format.md` §5 predicts.

```
vivado/specimen/specimen_lut.v          one explicitly instantiated LUT6
vivado/specimen/build_specimen.tcl      place/route once, re-write per INIT variant
scripts/run_vivado.sh                   Vivado is not on PATH on this host
scripts/bitstream_frames.py             .bit -> {FAR: 101 words}
scripts/specimen_diff.py                two .bit -> classified changed bits
```

```sh
mkdir -p build/spec && cd build/spec
../../scripts/run_vivado.sh -mode batch -nojournal -source \
  ../../vivado/specimen/build_specimen.tcl \
  -tclargs "$PWD" SLICE_X2Y25 A6LUT 0000000000000000 0000000000000002
cd ../.. && scripts/specimen_diff.py --base build/spec/spec_0000000000000000.bit \
                                     --variant build/spec/spec_0000000000000002.bit
```

## Design rule: one place-and-route, many bitstreams

Variants are written from a **single** placed-and-routed design; each variant only
sets the cell's `INIT` and re-runs `write_bitstream`. Re-running placement per variant
would let unrelated bits move, and the "isolated single-feature diff" would be a
fiction that still looks clean.

## Two confounders, both measured here rather than assumed

### 1. Frame ECC — every frame edit moves ~9 extra bits

Word 50 of each frame carries a 13-bit ECC field which the tools recompute whenever
anything else in that frame changes. A one-bit LUT INIT change therefore shows up as
**10 changed bits**: the real one, plus up to 13 in word 50 bits 0..12.

`specimen_diff.py` classifies those as `frame_ecc` and excludes them from attribution.
Without this, every certificate would carry ~9 unattributed bits per feature and the
"unattributed bit" alarm — the thing that makes a certificate worth having — would be
useless noise.

Note word 50 is shared: it also holds `HCLK_*` tile bits (`tilegrid` offset 50). Only
bits 0..12 are ECC.

### 2. LUT input pin swapping — the one that would have produced a wrong certificate

Vivado permutes a LUT's `I0..I5` onto the physical `A1..A6` inputs and rewrites `INIT`
to compensate. The function is preserved; the **bit index is not**. A prediction that
assumes logical INIT bit *n* is physical truth-table entry *n* is then wrong for every
entry except all-zeros and all-ones, which are invariant under any input permutation.

Measured on this exact design, `SLICE_X2Y25` / `A6LUT`:

| logical INIT bit set | without `LOCK_PINS` | with `LOCK_PINS` | frozen db |
|---|---|---|---|
| 0 | `32_15` | `32_15` | `ALUT.INIT[00] 32_15` |
| 1 | **`32_13`** = `INIT[04]` | `33_15` | `ALUT.INIT[01] 33_15` |
| 4 | — | `32_13` | `ALUT.INIT[04] 32_13` |
| 63 | `34_00` | `34_00` | `ALUT.INIT[63] 34_00` |

Bits 0 and 63 agreeing in **both** builds is exactly what makes this trap dangerous:
a gate that certified only the obvious endpoints would have passed, and every
interior bit in the resulting map would have been silently wrong.

The harness therefore sets

```tcl
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} $cell
```

and this is a **standing requirement for any LUT-INIT specimen**, not an option.

Generalisation to record before the gate mines other classes: a specimen must pin
every degree of freedom the tools are allowed to permute — pin order here, and for
other classes potentially site-within-tile, control-set mapping, or route choice. The
mining key may have to grow, exactly as the EP4CE6 campaign's key eventually had to.

## What is confirmed so far

- The frame map consumes real bitstreams exactly (5,144 + 8 pad frames × 101 words),
  which **discharges the frame-geometry assumption** flagged in `freeze_format.md`
  §5.6. See `scripts/bitstream_frames.py`.
- Four `clb_lut_init` predictions reproduced from real Vivado bitstreams:
  `INIT[00] 32_15`, `INIT[01] 33_15`, `INIT[04] 32_13`, `INIT[63] 34_00`, all in
  `CLBLL_L_X2Y25` at `SLICE_X2Y25`, with **zero** unattributed bits after ECC
  exclusion. `INIT[00]` is the same known answer as the author's fixture
  `clbll_l_lut_init_crosses_clock_row`, so fixture, producer cross-check and a real
  Vivado bitstream all agree on it.

  Wording: **real-bitstream** evidence, not silicon evidence. Every bitstream in this
  repo came out of Vivado and none has been loaded onto a board. See
  `docs/mux_groups.md` for the same correction applied there.

This is evidence, not a certificate. A certificate requires the full mine → holdout →
emit → fresh-gold run with `fp_count == 0 and fn_count == 0` over a holdout the
predictions were not derived from, emitted against `schemas/certificate.schema.json`
and accepted by `host/verify_certificate.py`.

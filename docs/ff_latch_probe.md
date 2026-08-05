# LATCH probe — measured on the mine site, 2026-08-04

> **APPLIED 2026-08-05.** This is the mine-site exploration record. Its four-latch
> topology and control-matched `latch_base` were incorporated into the 1.5 commitment
> at `2b40693` (sha256 `5440ef27…`). References below to an unchanged emitter, the old
> `4b06f78b…` draft or a held commitment describe the probe moment, not current state.

**Exploration, not evidence for any certificate.** Everything below was built on
`SLICE_X2Y25`, the mine site, whose evidence is already spent and can never score. No
holdout site was built, no holdout bitstream was read, no commitment was emitted and
`PREREGISTRATION_HOLD` was not touched.

Answers §5 risk 3 of `docs/ff_preregistration_plan.md`: `LDCE` is a different primitive
from the plan's baseline `FDRE`, so the `LATCH` pair was expected to move more of the
slice-wide control set than the single `LATCH` bit — and every extra mover would be
`db_attributed`, claimed by this class, outside the pair's one preregistered scope, i.e.
a false positive under the fixed 1.4 rule with FP=0 required.

Portable copy of everything below, with full bucket addresses, raw readbacks and the
recipe hashes: `evidence/ff_latch_probe_2026_08_04/`.

## Two results, and the second one changes the specimen plan

**1. The `LATCH` bit isolates, but it takes two control matches.** One is not enough.

**2. A slice cannot hold eight latches.** `A5FF` and its siblings are BEL type
`FF_INIT`, and Vivado refuses outright:

```
ERROR: [Vivado 12-2285] Illegal to place instance ... g_latch.s on site SLICE_X2Y25.
The location site type (SLICEL) and bel type (FF_INIT) do not match the cell type (LDCE).
```

This is not a constraint that can be worked around — it is what the site is. The plan's
formal topology (all eight storage elements per slice) is therefore **impossible for the
latch endpoint**, and the `LATCH` pair has to be a four-element pair on the main storage
elements. The eight-element **baseline** builds fine (mode `full_base`, all of
`AFF, A5FF, BFF, B5FF, CFF, C5FF, DFF, D5FF` occupied by `FDCE`), so the restriction is
specific to latch mode, exactly as UG474 says.

## Measurements

| pair | topology | raw | in_scope | ecc | db_attr | unknown | unattr | same-class movers | FP (1.4) |
|---|---|---|---|---|---|---|---|---|---|
| `fdre → ldce` (plan as written) | 1 FF | 24 | 1 | 21 | 2 | 0 | 0 | `FFSYNC` 1→0, `CLKINV` 0→1, `LATCH` 0→1 | **2** |
| `fdce → ldce` (reset kind matched) | 1 FF | 16 | 1 | 14 | 1 | 0 | 0 | `CLKINV` 0→1, `LATCH` 0→1 | **1** |
| `fdce_inv → ldce` (reset **and** clock matched) | 1 FF | 6 | 1 | 5 | 0 | 0 | 0 | `LATCH` 0→1 only | **0** |
| **`main_base → main_latch`** (**the formal pair**) | **4 FF** | **6** | **1** | 5 | **0** | 0 | 0 | **`LATCH` 0→1 only** | **0** |
| `full_base → full_latch` | 8 FF | — | — | — | — | — | — | **NOT MEASURABLE** — the latch endpoint cannot be built | — |
| `fdre → fdce` (control) | 1 FF | 8 | — | 7 | 1 | 0 | 0 | `FFSYNC` 1→0 | — |
| `fdce → fdce_inv` (control) | 1 FF | 10 | — | 9 | 1 | 0 | 0 | `CLKINV` 0→1 | — |

The two control pairs are what make this a measurement rather than a story: each removed
mover is separately attributable. Matching the reset kind removes exactly `FFSYNC`;
matching the clock polarity removes exactly `CLKINV`. And the four-element pair
reproduces the one-element result rather than merely agreeing with it in spirit — same
raw count, same single mover, same FP.

`LATCH` = `CLBLL_L.SLICEL_X0.LATCH` = segbit `30_32` = `0x00400A1E` word 52 bit 0,
moving **0→1** into the latch, the direction the plan preregisters.

## The pair that works

Both endpoints are four-element designs on the **main** storage elements, fed by four
`LUT5`s on `A6LUT..D6LUT` (with four more on `A5LUT..D5LUT` present in both endpoints so
the LUT occupancy cannot vary):

```
main_base    4x FDCE, IS_C_INVERTED=1, CE and CLR driven   -> AFF BFF CFF DFF
main_latch   4x LDCE, IS_G_INVERTED=0, GE and CLR driven   -> AFF BFF CFF DFF
```

Both endpoints occupy exactly the same twelve BELs
(`A6LUT..D6LUT`, `A5LUT..D5LUT`, `AFF..DFF`); the readbacks differ only in the storage
`REF_NAME` and its inversion properties. The Q outputs are reduced to the single `q`
port by two `LUT6`s pinned into the anchor tile, so the reduction is bit-identical
between endpoints and contributes nothing to the diff.

## The finding worth keeping

**`LDCE` reports `IS_G_INVERTED = 1'b0` and still sets the `CLKINV` bit.** The netlist
asked for no inversion anywhere; the bitstream has `01_51` set. So `CLKINV` is not a
faithful readout of "the netlist inverted this clock" — in latch mode the slice asserts
it regardless. What is *measured* is that matching the baseline's clock polarity removes
the mover; that latch mode implies the inverted-clock encoding is the obvious mechanism
but is an inference this probe does not establish.

Two consequences, both narrow:

1. The plan's semantic assertion for `CLKINV`/`NOCLKINV` reads `/resolved/clock_mode`,
   derived from the netlist inversion property. That stays right for the `clkinv` pair
   (mode `fdce_inv` confirms `IS_C_INVERTED = 1` ⇒ bit 0→1) and would be **wrong if ever
   applied to a latch specimen**. It is not, and must not be.
2. `CLKINV = 1` holds for the `LATCH` pair's baseline as well as for the `clkinv`
   variant. Not a conflict: observation consistency is per specimen, and these are
   different specimens.

Two of the plan's twelve directional predictions were incidentally confirmed on the mine
site, which is what a mine site is for — they inform, they do not score:
`FFSYNC = 1 ⟺ synchronous` and `CLKINV = 1 ⟺ inverted clock`.

## Artifacts and reproduction

`build/ff_latch_probe/` (gitignored) holds the bitstreams and checkpoints;
`evidence/ff_latch_probe_2026_08_04/` holds the portable record — the full report with
every bucket address, the seven raw `readback.tsv` files, **the `full_latch` failure log
and its stamp under `failures/`**, and a manifest pinning the recipe
(`specimen_ff_probe.v`, `build_ff_probe.tcl`, `gate_build_ff.py`) plus every
bitstream/checkpoint/readback hash and the hash of every file it carries. A mode that
cannot be built is a result, so its log travels with the record: "see run.out" pointing
into gitignored `build/` was the same defect as leaving the report there, one level
down. Bitstreams themselves are not copied — large and rebuildable from the pinned
recipe, with their hashes in the manifest.

Vivado 2025.2, `xc7z010clg400-1`. Reproduce with
`scripts/gate_build_ff.py --out build/ff_latch_probe`.

Build reuse is verified rather than assumed. Each mode's directory carries a
`stamp.json` naming the mode, the site, the hash of every source that produced it and
the hash of every artifact. **A stamp is written on every attempt, successful or not** —
a failure that left no stamp would be indistinguishable from a directory nobody ever
built in — and only `completed: true` is reusable; a stamp that matches the recipe but
records a failure is reported as an unbuildable mode, which for `full_latch` is the
answer rather than an accident. A non-empty directory whose stamp does not match is
**refused**, not overwritten and not reused; two runs of this probe did exactly that to
their own predecessor's output.

The same verification gates `--report-only`. That flag exists to rebuild nothing, which
made it the one path that would have stamped the current recipe's hashes onto an older
run's bitstreams; export and build now go through the identical check, and a single
tampered byte in a `spec.bit` makes the export refuse.
As `docs/mux_groups.md` records for the other classes: hashing a checkpoint and a
bitstream together anchors both against substitution but does not prove the bitstream
came from that checkpoint.

## Proposed adjustment to the 176-key plan — NOT applied

`scripts/gate_emit_ff.py` is unchanged and the draft still reproduces to
`4b06f78b9ea3edeb8f151dc0c19f81ac824d49d3ec533c7ebd43056ccba7eb8a`. The variant list is
the author's to fix once this result is confirmed. What it would become:

- the `latch` variant is redefined: **four** `LDCE` on `AFF..DFF`, not eight — eight is
  not buildable;
- a new `latch_base` specimen per site instance: four `FDCE` with `IS_C_INVERTED` on the
  same four BELs;
- the `LATCH` pair becomes `(latch_base, latch)` instead of `(base, latch)`;
- specimens per site instance 22 → 23 (**184 total**), P&R runs 14 → 15 (**120 total**),
  bitstreams **184**;
- **endpoint pairs stay 168 and predictions stay 176.** Coverage stays 176/176, split
  stays 22 / 154. The `LATCH` key keeps its one-bit scope.

Mechanically it needs one change beyond the extra specimen: `pair_features` currently
assumes every pair is `(base, variant)`, so each variant needs an explicit `pair_with`
naming its other endpoint, and `gate_measure_ff.py` must read that instead of deriving
`{site}_base`.

**And that is exactly what cannot be done producer-side alone.** The pairing would live
in producer metadata the verifier never reads, leaving the comparison endpoint free
after the commitment — see `docs/round10_request.md`. The formal predictions must
pre-register a `comparison_specimen_id` and the verifier must require it to equal the
result's `baseline_specimen_id`. **The variant list may be recorded as a plan; it may
not become a commitment until that contract lands.**

**No wider scope was guessed and no entry was dropped.** The plan's other 175 keys are
untouched by this: only the `LATCH` pair's two endpoints change.

# LATCH probe — measured on the mine site, 2026-08-04

**Exploration, not evidence for any certificate.** Everything below was built on
`SLICE_X2Y25`, the mine site, whose evidence is already spent and can never score. No
holdout site was built, no holdout bitstream was read, no commitment was emitted and
`PREREGISTRATION_HOLD` was not touched.

Answers §5 risk 3 of `docs/ff_preregistration_plan.md`: `LDCE` is a different primitive
from the plan's baseline `FDRE`, so the `LATCH` pair was expected to move more of the
slice-wide control set than the single `LATCH` bit — and every extra mover would be
`db_attributed`, claimed by this class, outside the pair's one preregistered scope, i.e.
a false positive under the fixed 1.4 rule with FP=0 required.

The author's ruling was: keep `LATCH`, try a control-matched baseline first, and if
movers remain, report all of them with their directions rather than guess a wider scope.

## Result

**A doubly control-matched baseline isolates `LATCH` to its single bit, FP = 0.** One
control match was not enough; two are.

| pair | raw | in_scope | ecc | db_attr | unknown | unattr | same-class movers | FP (1.4) |
|---|---|---|---|---|---|---|---|---|
| `fdre → ldce` (plan as written) | 24 | 1 | 21 | 2 | 0 | 0 | `FFSYNC` 1→0, `CLKINV` 0→1, `LATCH` 0→1 | **2** |
| `fdce → ldce` (reset kind matched) | 16 | 1 | 14 | 1 | 0 | 0 | `CLKINV` 0→1, `LATCH` 0→1 | **1** |
| **`fdce_inv → ldce`** (reset kind **and** clock polarity matched) | **6** | **1** | 5 | **0** | 0 | 0 | **`LATCH` 0→1 only** | **0** |
| `fdre → fdce` (control) | 8 | — | 7 | 1 | 0 | 0 | `FFSYNC` 1→0 | — |
| `fdce → fdce_inv` (control) | 10 | — | 9 | 1 | 0 | 0 | `CLKINV` 0→1 | — |

The two control pairs are what make this a measurement rather than a story: each removed
mover is separately attributable. Matching the reset kind removes exactly `FFSYNC`;
matching the clock polarity removes exactly `CLKINV`.

`LATCH` = `CLBLL_L.SLICEL_X0.LATCH` = segbit `30_32` = `0x00400A1E` word 52 bit 0, and it
moves **0→1** into the latch — the direction the plan preregisters.

## The baseline that works

`FDCE` with `IS_C_INVERTED`, i.e. asynchronous clear like `LDCE`'s `CLR`, **and** an
inverted clock. Both endpoints then carry `CLKINV = 1` and `FFSYNC = 0`, so neither bit
appears in the diff at all.

```
mode 0  fdce      FDCE                       CE, CLR driven   IS_C_INVERTED=0
mode 1  ldce      LDCE   <- under test       GE, CLR driven   IS_G_INVERTED=0
mode 2  fdre      FDRE   <- plan default      CE, R driven     IS_C_INVERTED=0
mode 3  fdce_inv  FDCE   <- the fix          CE, CLR driven   IS_C_INVERTED=1
```

All four resolved to `SLICEL.AFF` in `CLBLL_L_X2Y25` with the target LUT6 on `A6LUT`
under `LOCK_PINS`, occupying exactly `{A6LUT, AFF}`; anchor placement and LUT placement
are byte-identical across all four readbacks, so nothing structural varied except the
storage element itself.

## The finding worth keeping

**`LDCE` reports `IS_G_INVERTED = 1'b0` and still sets the `CLKINV` bit.** The netlist
asked for no inversion anywhere; the bitstream has `01_51` set. So `CLKINV` is not a
faithful readout of "the netlist inverted this clock" — in latch mode the slice asserts
it regardless. What is *measured* is that matching the baseline's clock polarity removes
the mover; that latch mode implies the inverted-clock encoding is the obvious mechanism
but is an inference, not something this probe establishes.

Two consequences, both narrow:

1. The plan's semantic assertion for the `CLKINV`/`NOCLKINV` keys reads
   `/resolved/clock_mode`, which is derived from the netlist inversion property. That
   remains right for the `clkinv` pair (mode 3 confirms `IS_C_INVERTED = 1` ⇒ bit 0→1)
   and would be **wrong if it were ever applied to a latch specimen**. It is not, and
   must not be.
2. `CLKINV = 1` will be true of the `LATCH` pair's baseline as well as of the `clkinv`
   variant. That is not a conflict: observation consistency is per specimen, and these
   are different specimens.

Two of the plan's twelve directional predictions were incidentally confirmed on the mine
site, which is what a mine site is for — they inform, they do not score:
`FFSYNC = 1 ⟺ synchronous` and `CLKINV = 1 ⟺ inverted clock`.

## Artifacts

`build/ff_latch_probe/` (gitignored), Vivado 2025.2, `xc7z010clg400-1`. Full five-bucket
records, per-bit directions, resolved LOC/BEL, control-pin nets, pin-inversion
properties and occupied BELs are in `probe_report.json`.

| mode | bitstream sha256 | checkpoint sha256 | readback sha256 |
|---|---|---|---|
| fdce | `65df5a6e5c723857…` | `ce1d2741f09d1351…` | `26d485c7bfff616f…` |
| ldce | `f5acd7e03868f8e5…` | `7157b089671b5761…` | `c61d2f4f9c13f81d…` |
| fdre | `464089a15547a303…` | `a75bd0ff2a1f31d6…` | `a7736b3809d1ec1d…` |
| fdce_inv | `c30341a8d184ffdb…` | `86f5e9ba272cb542…` | `04bfc13fee61fae0…` |

Reproduce with `scripts/gate_build_ff.py --out build/ff_latch_probe`. As
`docs/mux_groups.md` records for the other classes: hashing a checkpoint and a bitstream
together anchors both against substitution but does not prove the bitstream came from
that checkpoint.

## Proposed adjustment to the 176-key plan — NOT applied

`scripts/gate_emit_ff.py` is unchanged and the draft still reproduces to
`4b06f78b9ea3edeb8f151dc0c19f81ac824d49d3ec533c7ebd43056ccba7eb8a`. The variant list is
the author's to fix once this result is confirmed. What it would become:

- add one specimen per site instance, `latch_base` = `FDCE` with `IS_C_INVERTED`;
- the `LATCH` pair becomes `(latch_base, latch)` instead of `(base, latch)`;
- specimens per site instance 22 → 23 (**184 total**), P&R runs 14 → 15 (**120 total**),
  bitstreams **184**;
- **endpoint pairs stay 168 and predictions stay 176** — the `LATCH` pair changes which
  specimen it is paired against, not how many keys exist. Coverage stays 176/176 and the
  split stays 22 / 154.

This needs one mechanical change to the emitter beyond the extra specimen: `pair_features`
currently assumes every pair is `(base, variant)`, so each variant needs an explicit
`pair_with` naming its other endpoint, and `gate_measure_ff.py` must read it instead of
deriving `{site}_base`. Nothing about the key space moves.

**Not done, and deliberately: no wider scope was guessed and no entry was dropped.** The
`LATCH` key keeps a one-bit scope, which is what the freeze says it is.

# `clb_lutram` — inventory

Step 1 of the three that precede pre-registration (inventory → specimen isolation →
real diff), done under the model selected by the round 9 ruling: one feature namespace
and `(specimen, feature)` keys. That model was introduced in certificate 1.4; after
Round 10, any new comparison-based commitment for this class must select 1.5 and pin
both endpoints. **No gate emitter, no commitment hash, no manifest certification slot
is touched by this work.**

Everything here is recomputed from `data/` at the freeze pinned in
`data/MANIFEST.json`. Nothing below claims anything about RAM behaviour on silicon;
the claim under test, later, is only that the frozen rules predict which bits a Vivado
bitstream moves.

## The class is SLICEM-only

42 entries, and the regex resolves them entirely inside **`CLBLM_L` and `CLBLM_R`**, on
**`SLICEM_X0`**. `CLBLL_L` and `CLBLL_R` carry **zero** — the same query that returns 21
features per CLBLM tile type returns nothing for either CLBLL type.

That is the first structural difference from `clb_ff_config`, which spans all four tile
types, and it halves the specimen surface: there is one SLICEM per CLBLM tile and no
`SLICEM_X1`.

| | `clb_ff_config` | `clb_lutram` |
|---|---|---|
| tile types | 4 (CLBLL_L/R, CLBLM_L/R) | **2** (CLBLM_L/R) |
| sites per tile | 2 | **1** (`SLICEM_X0`) |
| entries | 176 | 42 |
| entries per tile type | 44 | 21 |

## The 21 features of one tile type

Coordinates below are `CLBLM_L`; `CLBLM_R` carries the identical 21 features at the
identical coordinates (the two tile types' rule text differs nowhere in this class).

| scope | feature | segbit |
|---|---|---|
| per-LUT | `ALUT.RAM` / `BLUT.RAM` / `CLUT.RAM` / `DLUT.RAM` | `31_16` / `31_17` / `31_46` / `31_47` |
| per-LUT | `ALUT.SMALL` / `BLUT.SMALL` / `CLUT.SMALL` / `DLUT.SMALL` | `00_04` / `00_24` / `00_28` / `01_59` |
| per-LUT | `ALUT.SRL` / `BLUT.SRL` / `CLUT.SRL` / `DLUT.SRL` | `30_16` / `30_17` / `30_46` / `30_47` |
| per-LUT, complementary | `ALUT.DI1MUX.AI` / `.BDI1_BMC31` | `00_00` / `!00_00` |
| per-LUT, complementary | `BLUT.DI1MUX.BI` / `.DI_CMC31` | `00_20` / `!00_20` |
| per-LUT, complementary | `CLUT.DI1MUX.CI` / `.DI_DMC31` | `01_43` / `!01_43` |
| per-SLICE | `WA7USED` | `00_40` |
| per-SLICE | `WA8USED` | `01_27` |
| per-SLICE | `WEMUX.CE` | `01_23` |

Notes that matter for specimen design:

- **`DLUT` has no `DI1MUX`.** A, B and C do; D does not. 12 + 6 + 3 = 21.
- **Every feature is one bit wide**, all 42 of them, and only the `DI1MUX` cascade
  members carry a negated token: **6 negated entries class-wide**, three in `CLBLM_L`
  and three in `CLBLM_R`. (The table above lists one tile type, so it shows three; an
  earlier version of this line read as though three were the class-wide total.) This is
  the same shape as `clb_ff_config` and is why the round 9 ruling covers both classes at
  once.
- The class touches **18 distinct coordinates** across frame offsets **0, 1, 30, 31** —
  the same two frame pairs `clb_ff_config` uses, so the frame-address arithmetic is
  already exercised.

## Grouping (bits, never names)

36 polarity-free bit-set groups over the 42 entries:

```
36 groups = 30 singletons (30 entries) + 6 two-member groups (12 entries)
```

All six multi-member groups are `DI1MUX` complementary pairs — three per tile type.
Like `CLKINV|NOCLKINV`, each is a **complete cover** of a one-bit scope: exactly one
member decodes for every possible observation. Under the round 9 ruling that makes
`group_exclusivity` a vacuous diagnostic here too, and the address evidence rests
entirely on strict equality with the preregistered codeword.

Codeword-collision check (the ruling's format-FAIL condition): **0** across this class,
as across every other bit-bearing class in the freeze.

## What is not settled by the inventory

The database names a feature; it does not say which tool-visible knob sets it. Those
correspondences are what the specimen work measures, and they are **not** assumed here:

- which primitive/mode sets `RAM`, `SMALL`, `SRL` — and whether they are independent;
- whether `WEMUX.CE` is a real degree of freedom or always follows RAM use;
- whether a `DI1MUX` cascade member can be selected at all by a reachable design;
- which LUT BELs Vivado picks for a multi-LUT primitive, and therefore which per-LUT
  features a `RAM128X1S` / `RAM256X1S` moves.

Every one of these is a tool freedom, so the specimen harness reads back what Vivado
actually did (site type, resolved LOC/BEL per leaf cell, bel-pin mapping, occupied
BELs) rather than restating what was requested. See `docs/lutram_specimens.md`.

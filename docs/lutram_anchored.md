# `clb_lutram` — holding the clock/IO structure fixed, and measuring the result

Follow-up to `docs/lutram_diff.md`, which found 90 `ownership_unknown` records across
the seven pairs and noted that certificate 1.4 counts those as FP, so a gate on those
pairs would fail on bits outside every preregistered scope whose ownership is
undetermined. **Measurement only — still no gate emitter, no commitment hash, no
manifest certification slot.**

Evidence: `evidence/lutram_isolation_anchored_2026_08_03/`. The earlier
`evidence/lutram_isolation_2026_08_03/` is untouched.

**Which commit reproduces the earlier evidence.** `commit 044b204`, not HEAD. An earlier
version of this section said `ANCHOR=0` reproduces the original structure from this file;
that is **false**. The module now declares `anchor_o` and `anchor_o2` unconditionally and
the Tcl assigns `F19`/`F20` unconditionally, so even at `ANCHOR=0` the design carries two
extra output ports and their `OBUF`s — a different design, and no claim is made about its
bitstreams matching. `ANCHOR=0` remains the default, and it still means "no anchor
cells", but it is not a compatibility mode. Making it one would mean a wrapper that omits
the ports and then **measuring** that all seven bitstream hashes match; that has not been
done, so the earlier evidence is pinned to the commit that produced it.

## Result

| pair | attributed | frame ECC | `ownership_unknown` | `unattributed` | class features |
|---|---|---|---|---|---|
| 0→1 | 214 | 688 | **0** | 0 | 2 |
| 1→2 | 121 | 569 | **0** | 0 | 1 |
| 0→3 | 350 | 970 | **0** | 0 | 2 |
| 1→4 | 250 | 858 | **0** | 0 | 2 |
| 4→5 | 485 | 1067 | **0** | 0 | 3 |
| 3→6 | 302 | 848 | **0** | 0 | 5 |
| 0→5 | 565 | 1227 | **0** | 0 | 7 |

**All seven, not one.** The class result is unchanged from the unanchored run: 12
distinct coordinates carrying 13 frozen feature names, same segbits, same directions,
including the `BLUT.DI1MUX` pair reading `BI` n→Y and `DI_CMC31` Y→n on the one
coordinate `00_20`.

What this does and does not say: the count is a measurement. `ownership_unknown` holds
exactly the bits no frozen database can attribute, so zero cannot be read back as a
claim that any particular clock or IO resource stayed put. It says the bucket is empty
under a design in which the structure was deliberately held fixed — which is what the
1.4 FP rule needs, and it is consistent with the isolation hypothesis rather than proof
of it.

## What the anchor is

`ANCHOR=1` adds four cells, all `DONT_TOUCH`, all with `LOC` and `BEL` forced:

| cell | site | BEL | job |
|---|---|---|---|
| `anchor_lut1` | `SLICE_X2Y25` | `A6LUT` | consumes `a[5:0]` |
| `anchor_lut2` | `SLICE_X2Y25` | `B6LUT` | consumes `a[7:6]`, `d`, `we` |
| `anchor_ff` | `SLICE_X2Y25` | `AFF` | consumes the buffered clock |
| `anchor_ff2` | `SLICE_X9Y25` | `AFF` | clocked keeper beside the site under test |

Verified from the emitted manifest: `anchor: 1`, both sites recorded, and the four
cells' resolved `REF`/`LOC`/`BEL`/`INIT` **identical across all seven modes**.

Every net's `ROUTE_STATUS` is in the record, and only `ROUTED` and `INTRASITE` appear.
**That shows routing completed; it does not show the paths are the same.** An earlier
version of this section said the field lets a reader check that downstream routing
matched — it does not. `ROUTE_STATUS` is a completion state per net, and two builds can
both report `ROUTED` over entirely different paths. Establishing path identity would
require recording the actual route — the `ROUTE` property or the PIP list per net — and
comparing it across modes. That is not recorded here, so no claim of identical routing
is made; what the seven pairs show is the measured bucket counts, which is the thing the
1.4 FP rule is defined over.

## Three keeper sites, three different failures

The site for `anchor_ff2` took three attempts, and only the last is legal for all seven
modes. Kept because two of the three would have looked fine from a single pair.

| keeper site | probe pair 0→1 | mode 5 | verdict |
|---|---|---|---|
| none (`ANCHOR=0`) | 22 unknown | builds | the original problem |
| `SLICE_X2Y25` only | 3 unknown | builds | IO/BUFG variation gone, HCLK remains |
| `SLICE_X8Y20` (same column, other row) | 2 unknown | builds | insufficient |
| `SLICE_X8Y25` (**inside** the target slice) | 0 unknown | **ERROR** | illegal in one mode |
| `SLICE_X9Y25` (SLICEL of the same tile) | 0 unknown | builds | adopted |

**Step 1 — ports and clock.** Each mode used a different subset of the top-level ports;
`MODE 0` touches `a[5:0]` and never `clk`. Vivado therefore trimmed a different `IBUF`
set per mode and could drop the `BUFG`, so the IO ring and clock tree differed between
the endpoints of a pair. Those tile types are not in the freeze, so the changes landed
in `ownership_unknown`. Consuming every port and the clock in every mode removed the
`RIOB33` / `RIOI3` / `CLK_BUFG_*` records: 90 → 9.

**Step 2 — the HCLK residue.** What survived was **three coordinates in
`HCLK_L_X46Y26`**, and only in the three pairs based on mode 0 — the one mode whose
target clocks nothing. All three sit at **word 50**, which this repo already knows
carries HCLK tile bits alongside the ECC field, and at bits 14, 23 and 25, so they are
above the 0–12 ECC range and are correctly *not* excluded as ECC. A keeper elsewhere in
the column cleared one of the three; only a clocked element beside the site under test
cleared the other two.

**Step 3 — the site that was legal.** Putting the keeper *inside* the target slice gave
zero on the probe pair and then failed mode 5 outright:

```
Cannot set LOC property of instance 'g_ram256.target/F7.A'...
Element SLICE_X8Y25.A5LUT cannot be used as a route-through for net g_anchor.w2
because a RAM or shift register is placed there
```

`RAM256X1S` occupies `A5LUT`, and the keeper's `D` arrives from a LUT in another slice,
so the route to `AFF.D` wanted `A5LUT` as a route-through. That failure was loud, which
is the good case — but it only appeared because all seven modes were built. **A keeper
site validated on one pair can be illegal in another mode**, and stopping at the probe
would have produced a specimen plan that fails on `RAM256X1S`. Moving the keeper to the
SLICEL of the same tile keeps it out of the SLICEM's BELs and route-throughs.

The keeper is in the tile under test (`CLBLM_L_X6Y25`, `SLICEL_X1`), so it writes
`clb_ff_config` bits into that tile. Being identical in every mode they cancel in every
diff, and the class result above confirms it rather than assuming it: same 12
coordinates, same 13 names, `unattributed` still 0.

## Still held

Pre-registration and the commitment hash remain held, and the 1.4 FP rule is untouched —
the fix was to the specimen plan, which is where the problem was. What is now shown is
that a `clb_lutram` specimen family can reach `ownership_unknown = 0` and
`unattributed = 0` on every intended pair, which is the precondition an FP-clean
measurement run needs.

Any future commitment for this class must use certificate/`gate_predictions` 1.5 and
preregister both endpoints. The FP rule above remains the fixed rule introduced by 1.4;
the 1.5 lifecycle addition does not weaken or replace it.

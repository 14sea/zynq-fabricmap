# `clb_lutram` — real diff

Step 3 of inventory → specimen isolation → real diff, under the round 9 ruling.
**Measurement only: no prediction, no commitment hash, no certificate, no manifest
certification slot.** Nothing here is a pass or a fail; a gate decides that later.

Evidence: `evidence/lutram_isolation_2026_08_03/` — `manifest.json` (every specimen's
bitstream sha256 plus its Vivado readback, and per-pair counts) and `diffs/*.json`
(every changed bit of every pair, in all five buckets). Produced by
`scripts/lutram_diff_matrix.py`, which reuses `scripts/specimen_diff.py` unchanged.

## Where Vivado actually put things

Read back from the routed design, not requested:

| mode | primitive(s) | resolved BELs in `SLICE_X8Y25` (`SLICEM`, `CLBLM_L_X6Y25`) |
|---|---|---|
| 0 | `LUT6` | `D6LUT` |
| 1 | `RAM64X1S` → `RAMS64E` | `D6LUT` |
| 2 | `RAM32X1S` → `RAMS32` | `D6LUT` |
| 3 | `SRLC32E` | `D6LUT` |
| 4 | `RAM128X1S` → 2× `RAMS64E` + `MUXF7` | `C6LUT`, `D6LUT`, `F7BMUX` |
| 5 | `RAM256X1S` → 4× `RAMS64E` + 2× `MUXF7` + `MUXF8` | `A6LUT`…`D6LUT`, `F7AMUX`, `F7BMUX`, `F8MUX` |
| 6 | 2× `SRLC32E`, `Q31 → D` | `A6LUT`, `B6LUT` |

The **D** LUT is not a choice: a single-LUT RAM macro's child is already pinned to
`D6LUT` before any BEL constraint, and `set_property BEL` on it is a silent no-op
(`docs/lutram_specimens.md`). The baseline was moved to `D6LUT` to match, so the
single-LUT pairs compare like with like.

## What moved

`decodes` is the assert-iff reading of the frozen rule at that coordinate, so a negated
member reads inversely to the raw bit.

| pair | class features that moved | segbit | bit | decodes |
|---|---|---|---|---|
| 0→1 `LUT6`→`RAM64X1S` | `DLUT.RAM` | `31_47` | 0→1 | n→Y |
| | `WEMUX.CE` | `01_23` | 0→1 | n→Y |
| 1→2 `RAM64X1S`→`RAM32X1S` | `DLUT.SMALL` | `01_59` | 0→1 | n→Y |
| 0→3 `LUT6`→`SRLC32E` | `DLUT.SRL` | `30_47` | 0→1 | n→Y |
| | `WEMUX.CE` | `01_23` | 0→1 | n→Y |
| 1→4 `RAM64X1S`→`RAM128X1S` | `CLUT.RAM` | `31_46` | 0→1 | n→Y |
| | `WA7USED` | `00_40` | 0→1 | n→Y |
| 4→5 `RAM128X1S`→`RAM256X1S` | `ALUT.RAM` | `31_16` | 0→1 | n→Y |
| | `BLUT.RAM` | `31_17` | 0→1 | n→Y |
| | `WA8USED` | `01_27` | 0→1 | n→Y |
| 3→6 `SRLC32E`→cascaded | `DLUT.SRL` | `30_47` | 1→0 | Y→n |
| | `ALUT.SRL` | `30_16` | 0→1 | n→Y |
| | `BLUT.SRL` | `30_17` | 0→1 | n→Y |
| | `BLUT.DI1MUX.BI` | `00_20` | 0→1 | n→Y |
| | `BLUT.DI1MUX.DI_CMC31` | `00_20` | 0→1 | **Y→n** |
| 0→5 `LUT6`→`RAM256X1S` | all four `xLUT.RAM`, `WA7USED`, `WA8USED`, `WEMUX.CE` | | 0→1 | n→Y |

**Every `clb_lutram` coordinate that moved is exactly the one the frozen rule names.**
The scope of that sentence matters: most changed bits in every pair are INT routing and
frame ECC, which no rule of *this* class names and which the claim says nothing about.
Within the class, the specimens moved **12 distinct coordinates** carrying **13 frozen
feature names** — the `BLUT.DI1MUX` complementary pair contributes two names on the one
coordinate `00_20`, so "12 features" (as an earlier version of this line said)
undercounts the names and "13 coordinates" would overcount the bits.

That agreement is the whole point of the step and the only thing it shows: the frozen
rules' addresses agree with where Vivado 2025.2 moved bits. Nothing here says what a RAM
does on silicon.

### Reading the complementary pair correctly

`BLUT.DI1MUX.BI` and `BLUT.DI1MUX.DI_CMC31` appear at **one** address, `00_20`, both
listed against a 0→1 change. That is not both members turning on — `BI` is `00_20` and
`DI_CMC31` is `!00_20`, so the change means `BI` starts decoding and `DI_CMC31` stops.
The first version of the diff summary printed the bare feature names and read exactly
like a contradiction; it now carries the polarity and the before/after decode.

### The cascade member was not demonstrated

The `DI1MUX` cascade member decodes in mode 3, where the **B LUT is unused**, and stops
decoding in mode 6, where B holds an SRL fed from the direct input. So a complete-cover
one-bit pair always decodes *something*, including for a LUT no design touches — the
vacuity the round 9 ruling describes, visible in measurement. **No specimen here has
shown a design that meaningfully selects the cascade member**; the `DI1MUX` pairs
therefore remain in the "not settled" list from `docs/lutram_inventory.md`.

### `WEMUX.CE` is not an independent knob in any specimen built

It turns on with `RAM64X1S` (0→1) and equally with `SRLC32E` (0→1), and stays set
through the RAM modes. Nothing here separates it from "some write-enabled LUT is in
use". Stated as an observation about seven specimens, not a rule.

## Buckets kept whole

Per the ruling, routing/ECC/unknown/unattributed evidence is preserved, not filtered.

| pair | attributed | frame ECC | ownership_unknown | unattributed | findings |
|---|---|---|---|---|---|
| 0→1 | 130 | 442 | 22 | 0 | 0 |
| 1→2 | 35 | 157 | 4 | 0 | 0 |
| 0→3 | 200 | 592 | 26 | 0 | 0 |
| 1→4 | 162 | 486 | 4 | 0 | 0 |
| 4→5 | 375 | 853 | 4 | 0 | 0 |
| 3→6 | 204 | 488 | **0** | 0 | 0 |
| 0→5 | 389 | 827 | 30 | 0 | 0 |

`unattributed` is **zero in every pair** — nothing changed outside a described tile.
Most `attributed` bits are INT routing claimed by `segbits_int_l.db` / `segbits_int_r.db`
(e.g. 0→5: `INT_L` 182, `INT_R` 166, `CLBLM_L` 41). Under the 1.4 FP rule those belong to
another class and are not this class's false positives.

### The `ownership_unknown` bits are a pre-registration problem, and they are avoidable

90 records across the seven pairs. **Every one has at least one candidate tile of a
clock or IO type the freeze does not contain** — `CLK_BUFG_REBUF`, `CLK_HROW_BOT_R`,
`CLK_BUFG_BOT_R`, `HCLK_L`, `RIOB33`, `RIOI3`, `RIOI3_TBYTETERM`, `RIOI3_TBYTESRC` — and
no frozen rule in any candidate claims the coordinate. That is exactly
`ownership_unknown` rather than `unattributed`.

**They are not "clock/IO bits", and an earlier version of this section called them
that.** Ownership is undetermined, so naming the owner is the one thing the bucket does
not license. **30 of the 90 also carry an `INT_R` candidate** — `CLK_BUFG_REBUF`+`INT_R`
15, `CLK_HROW_BOT_R`+`INT_R` 12, `CLK_BUFG_BOT_R`+`INT_R` 3 — and `segbits_int_r.db`
*is* frozen and claims none of those coordinates. The honest statement is: candidate set
includes an unfrozen clock/IO tile, and no database claims it.

Candidate sets, all 90:

| candidate tile types | records |
|---|---|
| `RIOB33` + `RIOI3` | 28 |
| `CLK_BUFG_REBUF` + `INT_R` | 15 |
| `RIOB33` + `RIOI3_TBYTETERM` | 12 |
| `CLK_HROW_BOT_R` + `INT_R` | 12 |
| `HCLK_L` | 9 |
| `RIOB33` + `RIOI3_TBYTESRC` | 8 |
| `CLK_BUFG_BOT_R` + `INT_R` | 3 |
| `CLK_HROW_BOT_R` | 3 |

Under the 1.4 FP definition `ownership_unknown` **counts as FP**, and `fp_count == 0` is
required to pass. So a gate built on these pairs as they stand would fail on 4–30 bits
per pair that **lie outside every preregistered scope and whose ownership is
undetermined**. That is the accurate statement, and it is weaker than the one an earlier
version of this line made: "nothing to do with the claim" asserts that these bits are
irrelevant, which is a claim about their owner — and their owner is exactly what the
bucket says is unknown.

Pair 3→6 records **zero** of them. Its two endpoints were built with the same clock and
IO structure, so the result is **consistent with the isolation hypothesis** that holding
that structure fixed across a pair avoids the bucket. It does not establish that the
clock tree did not move: unknown bits are the ones no database can attribute, so their
absence cannot be read back as a statement about what any particular resource did.

The hypothesis is worth acting on anyway, because the cost of being wrong is only a
rebuild: hold the clock/IO structure identical across every endpoint pair and **measure**
whether `ownership_unknown` reaches 0 for all of them, rather than assuming it will. The
alternative — extending the freeze to the clock tile databases — is a much larger change.
Better to have found this here than in a measurement run against a committed prediction.

## Not claimed

- No silicon behaviour. Every bitstream came out of Vivado; this line has never been on
  a board.
- No semantics for `RAM`, `SMALL`, `SRL`, `WEMUX.CE` or the `DI1MUX` members beyond
  "this knob moved this bit in these builds".
- No statement that the seven modes exhaust the class: 12 of 21 features per tile type
  were moved; `DLUT` has no `DI1MUX`, and the A/C `DI1MUX` pairs, the remaining `SMALL`
  and `SRL` positions, and `CLBLM_R` were not exercised.

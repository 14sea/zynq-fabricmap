# `clb_lutram` — specimen isolation

Step 2 of inventory → specimen isolation → real diff, under the round 9 ruling.
**No gate emitter, no commitment hash, no manifest certification slot is touched.**

Harness: `vivado/specimen/specimen_lutram.v` + `build_lutram.tcl`, readback reshaped by
`scripts/lutram_readback.py`. Site under test `SLICE_X8Y25`, confirmed by readback to be
**`SLICEM`** in tile `CLBLM_L_X6Y25` — the same tile family run B used, and the only site
type this class exists in (`docs/lutram_inventory.md`).

## Why every variant is its own place-and-route

`clb_ff_config` could reuse one implementation because FF `INIT` is a cell property.
Nothing in `clb_lutram` is: RAM, SRL, small/large and the wide-address modes are all
*different primitives*. So each mode is its own synth + place + route + bitstream, and
every pairwise diff carries genuine routing change. Under the round 9 FP rule those
routing bits are `db_attributed` to `segbits_int_*.db` and are **not** false positives;
they are kept in the evidence, never filtered.

## Modes

| mode | primitive | what it is meant to move |
|---|---|---|
| 0 | `LUT6` (baseline) | nothing in this class |
| 1 | `RAM64X1S` | `xLUT.RAM` |
| 2 | `RAM32X1S` | `xLUT.RAM` + `xLUT.SMALL` |
| 3 | `SRLC32E` | `xLUT.SRL` |
| 4 | `RAM128X1S` | `WA7USED` + a second LUT's bits |
| 5 | `RAM256X1S` | `WA8USED` + all four LUTs' bits |
| 6 | two `SRLC32E`, `Q31 → D` | a `DI1MUX` cascade member |

"Meant to move" is the hypothesis being tested, not a claim. What actually moved is in
`docs/lutram_diff.md`.

## Tool freedoms, read back rather than assumed

The ruling requires the SLICEM choice, the BEL a multi-LUT primitive lands on, the pin
mapping and the RAM mode to come from the routed design. `build_lutram.tcl` emits a flat
`readback.tsv` per specimen carrying: part, tool version, requested vs resolved site,
`SITE_TYPE`, tile and tile type, and per leaf cell the `REF_NAME`, `LOC`, `BEL`,
`LOCK_PINS`, `INIT` and the resolved bel-pin of every cell pin — plus every occupied BEL
of the site, enumerated from the site rather than derived from the request.

Flat TSV, not JSON, on purpose: composing JSON in Tcl needs literal braces inside quoted
strings, the parser miscounts them, and the first attempt died **after** `write_bitstream`
had already run. That left a directory holding a valid bitstream next to a truncated
readback — a specimen that looks measurable and whose provenance record is a fragment.

## Three ways this harness silently built the wrong thing

Kept because each produced a plausible-looking artifact rather than an error, which is
the failure mode this project keeps meeting.

1. **`IS_PRIMITIVE` returns the macro *and* its child.** `RAM64X1S` is a `MACRO`
   containing one `RAMS64E`. The "exactly one cell ⇒ force the BEL" test therefore saw
   two cells, forced nothing, and Vivado placed the RAM on **`D6LUT`** while the
   baseline `LUT6` sat on `A6LUT`. The diff would have been between two different LUTs,
   and every per-LUT feature name in it would have been wrong. Caught only by reading
   the resolved BEL back — the build exited 0.
2. **`PRIMITIVE_LEVEL == LEAF` matches neither.** A macro's child reports
   **`INTERNAL`**, not `LEAF` (`LUT6` = `LEAF`, `RAM64X1S` = `MACRO`,
   `RAM64X1S/SP` = `INTERNAL`). The filter matched zero cells, so **no `LOC` was applied
   at all** and the specimen floated to wherever the placer chose. The build still
   exited 0 and still wrote a bitstream. The script now selects
   `IS_PRIMITIVE && PRIMITIVE_LEVEL != "MACRO"`, minus IO/clock buffers, and **errors
   out if that set is empty** rather than building an unconstrained specimen.
3. **A partial readback outlives its build.** Fixed by writing the readback as flat
   key/value lines and converting outside Tcl.

The general rule this class keeps re-teaching: a Vivado script that fails to constrain
anything is indistinguishable, at the exit code, from one that constrained everything.
Only the readback separates them.

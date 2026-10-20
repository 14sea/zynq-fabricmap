# B4 pre-work, D1′ `latch_ginv` probe — host build / readback / bitstream correspondence on the mine site (2026-10-18)

**Authorisation:** the owner's ruling of 2026-10-18 (`owner_ruling_2026_10_18.md`, copied here from the ignored
`build/wip/`), section 2: a host-only pair of control-matched latch endpoints on `SLICE_X2Y25`, one recipe, one tool,
no board, no certificate, no hypothesis change. **Stop rule:** any miss is archived as it came and the unit stops for
review — no fallback to D1 / D2, no added condition, no other site, no re-run chasing the expected answer.

**Recipe (recorded first, commit `0210156`):** `b4/probes/latch_ginv/` — the derived Verilog and Tcl (the pinned
originals unchanged; `manifest.json` → `originals_unchanged` equals the old probe's recipe digests), the driver with
the expectation fixed in it. Vivado 2025.2, `xc7z010clg400-1`. Raw output `build/b4_ff_latch_ginv_probe/` (ignored);
the stamps, readbacks, run logs and Vivado logs are copied here (`stamps/`, `readbacks/`, `logs/*.txt`).

## Result — the driver's verdict is `expectation_met: false` (exit 2); every bitstream clause and the structure hold; the misses are the verifier's own route-status rule

| clause (fixed before the build) | value |
|---|---|
| LATCH (`CLBLL_L.SLICEL_X0.LATCH`, 30_32, `0x00400A1E` w52 b0) = 1 in both endpoints | **true** (1, 1) |
| CLKINV (`CLBLL_L.SLICEL_X0.CLKINV` / `NOCLKINV`, 01_51, `0x00400A01` w52 b19) moves 1 → 0 | **true** (1 → 0) |
| CLKINV is the only same-class mover | **true** |
| CLKINV in scope exactly once; no `db_attributed` / `ownership_unknown` / `unattributed` bit; no class claim out of scope | **true** (raw diff 10 = 1 in-scope + 9 frame-ECC bits, all at `0x00400A01` w50) |
| the two endpoints' structure (cells minus `IS_G_INVERTED`, LUT cells, occupied BELs, anchors, tool, part) identical | **true** (no finding) |
| each endpoint: four LDCE on AFF / BFF / CFF / DFF of `SLICE_X2Y25`, `IS_G_INVERTED` resolved to the requested value on **every** cell, `IS_CLR_INVERTED` 1'b0, G = `clk_g`, GE = `ce_IBUF`, CLR = `rst_IBUF` shared, D and Q with nets | **true** for all of these |
| every G / GE / CLR / D / Q net `ROUTE_STATUS == ROUTED` | **false** on 3 cells × 2 endpoints: the D nets `g_full.o6[1..3]` (LUT O6 → latch D inside the slice) report **`INTRASITE`**; cell 0's D is `o_OBUF`, which leaves the site, and reports `ROUTED` |

So: `probe_report.json` → `pair.expectation.met` **true** (all six bitstream clauses), `pair.structure_findings` `[]`,
`endpoints.*.cell_findings` six entries, all of the form `pin D net 'g_full.o6[k]' route status 'INTRASITE'`, and
`verdict.expectation_met` **false** because the driver's cell rule accepts `ROUTED` only.

**What the misses are.** `INTRASITE` is Vivado's `ROUTE_STATUS` for a net routed entirely inside one site (here the
slice's own O6 → D path), a completed route, not an unrouted one; the same statuses appear in the old probe's
`main_latch` readback (16 `INTRASITE` lines), which never judged pin routes. The rule `== ROUTED` in
`probe_latch_ginv.cell_findings` was written too narrowly in the recipe commit. **Under the stop rule nothing was
changed or re-run**: the finding is archived as it came, and whether `INTRASITE` counts as a complete route for this
check is for the owner (it would be a one-line recipe change, a new recipe digest, and a second attempt with its own
stamps — the first attempt's artifacts stay).

**Cross-check against the historical record (a fact, never a condition).** The rebuilt `main_latch` bitstream has
**zero configuration-frame differences** against the old probe's `main_latch` (`build/ff_latch_probe/main_latch/
spec.bit`, digest `e260d4fc…` = `evidence/ff_latch_probe_2026_08_04/manifest.json`); the file digests differ
(`ee675f96…` vs `e260d4fc…`) because the `.bit` header carries the build time. The attested endpoint reproduces
under the derived recipe.

**Logs.** Each build: synthesis 0 warnings; one placer warning `[Place 30-574]` (IO pin → BUFG with
`CLOCK_DEDICATED_ROUTE FALSE`, the old recipe's known condition); 0 critical warnings, 0 errors; `SPECIMEN_DONE`;
exit 0; 57.1 s and 54.4 s.

## What this does and does not establish

If the owner accepts the route-status reading, the pair shows, **for this recipe on this site**, that
`IS_G_INVERTED = 1` on four main LDCE clears the site's CLKINV bit and moves nothing else of the class: the reading
"latch, CLKINV = 0 ⇒ gate inverted" would gain a host exploration source of the same kind as the attested
`CLKINV = 1` endpoint of `docs/ff_latch_probe.md`. It is not a certificate, not a silicon observation, not a
verification of the 21-address domain or of any other latch combination (the ruling, §2 last paragraph). The formal
hypothesis v0.2.1, `HYPOTHESIS_SHA256`, the domain and the F fact test are **unchanged**; v0.3 is a separate unit,
not authorised (the ruling, §3).

## Files

`probe_report.json` (every changed bit with its address, every bucket, the movers with direction, every cell's
properties and pins, the expectation clause by clause, the verdict), `manifest.json` (recipe / borrowed / originals
digests, the historical cross-check, the bitstream and checkpoint digests — bitstreams not copied, rebuildable from the
recipe), `readbacks/`, `stamps/`, `logs/`, `owner_ruling_2026_10_18.md`, `tests.txt`.

# B4 pre-work, D1′ `latch_ginv` probe, attempt 2 — the owner's follow-up ruling of 2026-10-18 (`owner_followup_ruling_2026_10_18.md`)

**What changed, and only that:** the driver's cell rule accepts `ROUTE_STATUS` **ROUTED and INTRASITE** (UG912:
INTRASITE = a net routed entirely within one site, complete, not an error). Every other expectation clause is the one
of attempt 1. Recipe recorded first (commit `5d73ede`, suite Ran 107 OK: the positive case, the two real attempt-1
readbacks under the rule, nine rejected statuses plus a missing value), then built.

**Attempt 1 is untouched:** `evidence/b4/unit_d1prime_latch_ginv_2026_10_18/` and `build/b4_ff_latch_ginv_probe/`
keep their `expectation_met: false`, exit 2, stamps and artifacts under the attempt-1 recipe digest. Attempt 2 wrote to
`build/b4_ff_latch_ginv_probe_attempt2/` (ignored) and this directory, with its own stamps under the new recipe digest.

## Result — `expectation_met: true`, exit 0, no finding

Vivado 2025.2, `xc7z010clg400-1`, mine site `SLICE_X2Y25`, `main_latch` 54.4 s and `main_latch_ginv` 54.6 s, exit 0,
`SPECIMEN_DONE`, 0 errors, 0 critical warnings, the one placer warning `[Place 30-574]` of the old recipe.

| clause (fixed before attempt 1; unchanged) | value |
|---|---|
| LATCH (`CLBLL_L.SLICEL_X0.LATCH`, 30_32, `0x00400A1E` w52 b0) = 1 in both endpoints | **true** (1, 1) |
| CLKINV (`CLBLL_L.SLICEL_X0.CLKINV` / `NOCLKINV`, 01_51, `0x00400A01` w52 b19) moves 1 → 0 | **true** |
| CLKINV is the only same-class mover; in scope exactly once; no `db_attributed` / `ownership_unknown` / `unattributed` bit; no class claim out of scope | **true** (raw diff 10 = 1 in-scope + 9 frame-ECC bits at `0x00400A01` w50) |
| the two endpoints' structure identical (cells minus `IS_G_INVERTED`, LUT cells, occupied BELs, anchors, tool, part) | **true** |
| each endpoint: four LDCE on AFF / BFF / CFF / DFF of `SLICE_X2Y25`, `IS_G_INVERTED` resolved on **every** cell to 1'b0 (`main_latch`) / 1'b1 (`main_latch_ginv`), `IS_CLR_INVERTED` 1'b0, G = `clk_g`, GE = `ce_IBUF`, CLR = `rst_IBUF` shared, D and Q nets complete (`ROUTED` for cell 0's `o_OBUF`, `INTRASITE` for the intra-slice `g_full.o6[1..3]`) | **true** |

**Reproducibility across the two attempts (facts, not conditions).** Both endpoints' readbacks are byte-identical to
attempt 1's (`readback_sha256` equal: `c5c6b978…`, `214dc46b…`); both endpoints' configuration frames have **zero**
differences against attempt 1's bitstreams; the rebuilt `main_latch` keeps zero configuration-frame differences against
the historical `main_latch` of `evidence/ff_latch_probe_2026_08_04/` (`e260d4fc…`). Bitstream file digests differ
between attempts by the `.bit` header's build time only.

## What this establishes, and what it does not

For this recipe on this site, `IS_G_INVERTED = 1` on four main LDCE clears the site's CLKINV bit and moves nothing
else of the class; `IS_G_INVERTED = 0` leaves it set (the attested endpoint of `docs/ff_latch_probe.md`, reproduced).
The reading "latch, CLKINV = 0 ⇒ gate inverted" now has a host exploration source of the same kind as the attested
`CLKINV = 1` endpoint. **It is not** a certificate, a silicon observation, a proof that routing paths are the same, a
verification of the 21-address domain or of any other latch combination (the ruling §2; the follow-up ruling). The
formal hypothesis v0.2.1, `HYPOTHESIS_SHA256`, the domain and the F fact test are **unchanged**; the v0.3 model
revision is a separate unit, not authorised; D1′ is closed only by the owner's review of this attempt.

## Files

`probe_report.json` (schema 1.1.0, `attempt: 2`, `complete_route_status`, every changed bit with its address, every
bucket, the movers with direction, every cell's properties and pins, the expectation clause by clause, the verdict),
`manifest.json` (recipe / borrowed / originals digests, the historical cross-check, the bitstream and checkpoint digests
— bitstreams not copied, rebuildable), `readbacks/`, `stamps/`, `logs/` (raw tool output verbatim),
`owner_followup_ruling_2026_10_18.md`, `tests.txt`.

# Holdout build 2026-08-06 — complete, and refused by the pair gate

Attempt `54431dd9ced7-20260806T091428Z`, all eight instances, ~2h40m wall (under
external CPU load from an unrelated job). This directory preserves a run that **built
everything and still must not be measured**.

## What the run produced

| fact | value |
|---|---|
| specimens built | **184 / 184**, every stamp `completed: true` |
| composition | **120 implementations + 64 derived**, 8 instances × 23 |
| distinct `recipe.sources` sets across all 184 | **1** (`recipe_sources.json`) |
| preregistration plan / commitment hashes | 1 each — `ac9dbab8…97a64` / `5440ef27…d1b2e51` |
| converter `gate_stage_ff_formal.py --check` | 184/184 records accepted, 0 problems |
| **committed pairs compared** | **168** |
| **T1 failures** | **0** |
| **T2 failures** | **1 pair**, two field differences (`w1.route`, `w1.pips`) |
| T3 (shared nets, diagnostic only, never a FAIL) | 188 field differences over the whole run; **10 of them in the failing pair** |
| derived checks | 64, 0 failures |

The mine instance built on 2026-08-05 is part of this set and shares the single recipe,
so this is one coherent batch, not two.

## The failure

```
pair   : SLICE_X25Y25_base  ↔  SLICE_X25Y25_ce_tied      (split: holdout)
tier   : T2 — dedicated net `w1`
same   : driver, every sink, both endpoints, all cell facts (T1 clean)
differs: one PIP, and therefore the route string
           a: … INT_R_X19Y20/INT_R.LOGIC_OUTS8->>NL1BEG_N3  NL1BEG_N3->>IMUX13
           b: … INT_R_X19Y20/INT_R.BYP_BOUNCE1->>IMUX13
```

It carries exactly one committed prediction, `CLBLM_R.SLICEL_X1.CEUSEDMUX`
(1 of 176). The other 20 predictions on this instance ride other pairs and passed.

**What it means.** The anchor/keeper design pins cells, LOC and BEL, but it does not pin
the *routing* of its own dedicated nets. The two specimens of this pair differ by
design in one control connection, the router answered the surrounding congestion
differently, and `w1` took another path. The mine instance's 21/21 could not have
revealed this; it took 168 pairs to hit once.

**What it is not.** It is not a build failure (both specimens are `completed: true`,
hashes intact), not non-determinism (same recipe and seed reproduce the same routing —
so rebuilding this node changes nothing, and rebuilding until it agrees would be
tampering with the build), and not a T3 matter (shared nets are diagnostic by design).

## The ruling this run is preserved under

T2 is a **hard gate** and stays one. It was written into the design before any holdout
artifact existed, so downgrading it to a diagnostic *after* it fired on holdout would be
moving the goalposts — and the five-bucket accounting cannot be used to justify the
weakening, because that accounting has not been looked at and must not be, for these
artifacts. Therefore: **no staging, no measurement, and the affected prediction is not
dropped.**

The remedy is to pin dedicated-net routing in the specimen design, which changes a
recipe-domain file and so **invalidates all 184 artifacts**; the next run rebuilds
120 implementations + 64 derived and must be 168/168 green before anything is staged.

## Portability — read before citing this directory

Versioned here: `run_report.json` (all 168 pair records and 64 derived records,
including the full route/PIP strings of the failing pair), the failing pair's two
`readback.tsv` and `stamp.json`, `artifact_hashes.tsv` (184 rows: `spec.bit`,
`readback.tsv` and checkpoint hashes), and `recipe_sources.json`.

**Not versioned, and deliberately not recoverable from this directory:** the 184
bitstreams, the 8 `base.dcp` and 64 `derived.dcp` checkpoints, and the 182 readbacks
outside the failing pair. They lived in gitignored `build/` and are invalidated by the
recipe change. `artifact_hashes.tsv` therefore pins artifacts that **cannot be produced
again from this tree** — after the recipe-domain fix, a rebuild produces different
hashes by definition. Treat those hashes as a record of what this batch was, never as a
target for a later run to match.

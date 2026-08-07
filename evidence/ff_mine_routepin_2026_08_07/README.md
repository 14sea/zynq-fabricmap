# Mine instance rebuilt under the pinned recipe — gate green, scope unchanged

The build after `065b5a1`, which pins the dedicated nets and closes four fail-open gaps
in the checks over the record. Mine instance only:
`SLICE_X2Y25`, 23 specimens. Nothing was staged, no holdout instance was built, and
`gate_runs/` and `data/` were not touched.

Two superseded trees are preserved intact, moved and never deleted: the 184 of
2026-08-06 under `build/gate_ff_formal.invalidated_t2fail_2026_08_06/`, and the first
route-pinned mine build under `build/gate_ff_formal.superseded_prefailopen_2026_08_07/`
(23 stamps), which a later tightening of the same gate invalidated in turn.
The recipe was committed **before** this build, and all five recipe sources were verified
to match `HEAD` first — the 2026-08-05 incident was a run that stamped a builder hash no
longer in the tree.

## The gate

| criterion | result |
|---|---|
| implementations | **15 / 15** |
| specimens | **23 / 23** |
| committed pairs compared | **21**, T1 failures **0**, T2 failures **0** |
| derived checks | **8**, failures **0** |
| pair gate / derived gate | **pass / pass** |
| diagnostic: pairs scored | 21, predictions scored 22 |
| diagnostic: TP / FN | **22 / 0** |
| diagnostic: FP | **0** |
| diagnostic: ownership_unknown / unattributed | **0 / 0**, partition exact |
| route-pin problems over all 23 specimens | **0** |
| dedicated set, recomputed per specimen | **exactly the nine**, everywhere |
| routable / intrasite split | **6 / 3**, everywhere |
| distinct dedicated route sets across the 23 | **1** |
| `recipe.sources` sets across the 23 | **1**, and its builder hash is `HEAD`'s blob |
| artifact-dependent tests that had been skipping | **6 now run and pass** — the built tree matches the current recipe again |

T3 (shared nets, diagnostic by design, never a FAIL): 21 field differences over the 21
pairs.

## `ready_for_measurement` is false, and that is correct

The builder exits 1. `build_complete` is false because this run is 15 of 120
implementations and 23 of 184 specimens — a mine-only run *is* incomplete, by choice.
The pair gate and the derived gate both pass; readiness is their conjunction with build
completeness, and a scope this narrow cannot satisfy it. A green mine gate is a licence to
consider the next step, not a measurable run.

## What this does and does not say

It says the pinned recipe builds every mine variant, that all 21 committed pairs at this
instance are structurally comparable, that the derived specimens changed nothing but the
one cell property, and that the route-pin record is internally consistent and identical
across all 23 specimens.

It says **nothing** about `SLICE_X25Y25`. That instance is holdout and was not built. The
mine site never exhibited the failure — before the fix, its nine dedicated nets already
shared one route under every variant and every router directive
(`evidence/ff_route_pin_probe_2026_08_06/`). Only a full 168/168 run can answer whether
the observed failure is repaired.

## Files

`run_report.json` (the whole `ff_formal_run/2` record, 21 pair records and 8 derived
records), `mine_diagnostic.json`, `artifact_hashes.tsv` (23 rows), `recipe_sources.json`,
and `routepin_base.section.tsv` — the `routepin.` namespace of one readback, so the record
format is readable without a build tree. Hashes here are integrity anchors; they detect
substitution and prove nothing about provenance, and the bitstreams and checkpoints they
name live in gitignored `build/`.

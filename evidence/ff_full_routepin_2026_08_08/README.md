# Full 184-specimen rebuild under the pinned recipe — every gate green

The first complete run after `19bb911` (`origin/main`). 120 implementations + 64 derived,
8 instances, ~2 hours. **Nothing has been staged and nothing has been measured**; this
directory records a build and its structural gate, and stops there.

## Acceptance

| criterion | result |
|---|---|
| implementations | **120 / 120** |
| specimens | **184 / 184**, every stamp `completed: true` |
| committed pairs compared | **168 / 168** |
| T1 differences, run-wide | **0** |
| T2 differences, run-wide | **0** |
| pairs with status FAIL | **0** |
| derived checks | **64 / 64**, failures **0** |
| `build_complete` / pair gate / derived gate | **true / pass / pass** |
| `ready_for_measurement` | **true**, builder exit **0** |
| structural problems | **0** |
| route-pin records inspected | **184**, problems **0** |
| `(nets, routable, intrasite)` per specimen | **(9, 6, 3)** — one value across all 184 |
| distinct `recipe.sources` sets | **1**, and each of its five hashes equals the blob in `origin/main` `19bb911` |

T3 (shared nets, diagnostic by design, never a FAIL): 184 field differences over 168
pairs.

## The pair that stopped the previous run

On 2026-08-06 `SLICE_X25Y25_base` ↔ `SLICE_X25Y25_ce_tied` failed T2: same driver, same
sinks, one PIP different on the dedicated net `w1`. Under the pinned recipe:

```
dedicated nets compared      : 9
fields differing (final)     : 0
w1.route identical           : True
w1.pips  identical           : True
gate status                  : pass   T1=0 T2=0 T3=6
```

Both route-pin sections are here verbatim (`SLICE_X25Y25_base.routepin.tsv`,
`SLICE_X25Y25_ce_tied.routepin.tsv`) so the comparison can be redone from the files.

**What this licenses saying, and what it does not.** This pair is now structurally
comparable, and all 168 are. It does not follow that the pin *caused* it: this is one
run of a new recipe, not a controlled comparison against the old one at this instance —
the old artifacts are invalidated and the old recipe is gone from the tree. The
mechanism was shown to remove the freedom on a non-committed site of the same geometry
(`evidence/ff_route_pin_sacrificial_2026_08_06/`), and this run is consistent with that.
"Consistent with" is the strength available.

## The structural result worth keeping

`route_stability.json`: **within every one of the eight instances, all 23 specimens share
exactly one dedicated route set** — 1, eight times over. Across instances there are eight
distinct sets, which is expected, because each instance sits in a different column and
the geometry differs.

That is the property the pin exists to produce: the dedicated routing is a function of
the fixed placement, not of what the target slice happens to contain. Before the pin,
`qr1` alone was observed taking two different paths depending on when it was routed.

## Files

`run_report.json` (the whole `ff_formal_run/2` record: 168 pair records, 64 derived
records, node states), `artifact_hashes.tsv` (184 rows), `recipe_sources.json`,
`route_stability.json`, and the two route-pin sections of the previously failing pair.

Hashes here are integrity anchors: they detect substitution of these files and prove
nothing about provenance. The bitstreams and checkpoints they name live in gitignored
`build/`, and superseded trees from earlier attempts are preserved under
`build/gate_ff_formal.invalidated_t2fail_2026_08_06/` and
`build/gate_ff_formal.superseded_prefailopen_2026_08_07/` — moved, never deleted.

## Next step is a decision, not a continuation

`ready_for_measurement: true` means this run *may* be staged and measured. It has not
been, and doing so is the step where the holdout predictions stop being unread. That
needs its own authorisation.

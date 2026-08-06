# Sacrificial site: the routing freedom reproduced, then removed

Probe only. No recipe-domain file was modified — the specimen Verilog and the readback
Tcl were **read**, and the congestion cells are added to the *synthesized netlist*, so
nothing about the specimen's own cells or its nine dedicated nets changes. No bitstream
was written, no frame parsed, and no committed site touched.

## Why a different site

The mine instance cannot show this fix working: its nine dedicated nets take one route
under every variant and every router directive, before any change
(`evidence/ff_route_pin_probe_2026_08_06/`). The failure is instance-local congestion,
and the instance that showed it is holdout. So the probe moves to a **non-committed site
of the same geometry** and creates the congestion itself.

```
target SLICE_X31Y25   CLBLM_R_X21Y25   CLBLM_R / SLICEL / row 25
keeper SLICE_X31Y20   CLBLM_R_X21Y20   CLBLM_R / SLICEL
anchor SLICE_X33Y20   CLBLM_R_X23Y20   CLBLM_R / SLICEL
   (failure point, for comparison: SLICE_X25Y25, CLBLM_R_X17Y25, CLBLM_R / SLICEL)
```

The three roles are exactly what `sites_for()` yields for that target — the probe refuses
roles that do not follow the committed site rule — and **every role and every congestion
site is recomputed against the published commitment and refused if it is one of the 24
committed target/keeper/anchor sites.** The refusals are unit-tested
(`tests/test_probe_guards.py`), including a committed role site, a committed congestion
site, roles that violate the site rule, and a site absent from the freeze.

## Method

Congestion is 32 `DONT_TOUCH` LUT6 cells created in the synthesized netlist, each pulling
all six input nets into a slice around the anchor and along the anchor→keeper span, with
outputs left dangling. 10 builds: two flows × two variants × two congestion levels, plus
`Explore` and `latch` under congestion.

## Results — all six preregistered criteria pass

The verdict first asserts that the ten runs of the matrix are all present. A verdict over
whatever happens to be on disk is how a run that lost a build reports one route set and
passes, so the matrix is the unit, not the file listing; `collect_evidence()` likewise
refuses to pin an incomplete set rather than skipping what is missing.

| # | criterion | result |
|---|---|---|
| 1 | the current flow routes at least one dedicated net differently under the two congestion conditions — **the freedom is reproduced** | **yes: `qr1`** |
| 2 | the pinned flow yields one route set over the same conditions, variants and directives | **1 route set over 6 runs** |
| 3 | no dedicated net moves after the freeze | **0 runs with movement** |
| 4 | drivers and sinks identical across every run | **0 nets differ** |
| 5 | the six routable nets read `IS_ROUTE_FIXED=1` **in the six pinned runs** — the only runs that freeze anything | **ok** |
| 6 | the three pad nets stay `INTRASITE` with empty route and pips **in all ten runs**, both flows — a fact about the design, not about the flow | **ok** |

Criterion 1 is a **precondition**, not a bonus: without reproducing the freedom the
probe would show nothing about removing it, and `verdict.json` records
`freedom_reproduced` so the distinction survives.

## What this supports, and the sentence not to exceed

The routing freedom of the class that failed T2 was **reproduced and removed on a
non-committed site of the same geometry**. That is the whole claim.

It is **not** evidence that the observed `SLICE_X25Y25` failure is repaired: that site is
holdout and was not built. `verdict.json` carries the same limit in `claim_limit`, and
the driver prints it at the end of every run.

## Two probe bugs, reported as bugs rather than results

* `route_design -directive X -preserve` is refused by Vivado; the crashed run's empty
  snapshot looked exactly like "the pinned flow let 9 nets move".
* Vivado prints an empty route as the empty Tcl list `{}`, and `bool("{}")` is `True`, so
  criterion 5 reported 18 problems in a run where all five criteria had in fact passed.
  `empty_route()` now decides that, and `tests/test_probe_guards.py` pins it.

Both were in the *measuring* code, not the thing measured. That is the more dangerous
place for a bug, because its output reads like a finding.

## Reproduce

```bash
scripts/probe_sacrificial_site.py --scope-only                     # refusals only
scripts/probe_sacrificial_site.py --out build/probe_sacrificial    # 10 builds, ~5 min
scripts/probe_sacrificial_site.py --compare-only                   # re-derive the verdict
```

`.gitattributes` in this directory turns off git's whitespace checks. The raw readback
TSVs carry trailing tabs because `emit_readback` writes a tab and then whatever the
property returned, and an empty property leaves the tab behind. That is what Vivado
produced; tidying it would make the evidence a transcription rather than a record. The
exception is scoped to this directory, where nothing is source and every file is pinned.

`manifest.json` pins every file here plus the probe's script and Tcl, the inputs it read
(specimen Verilog, readback Tcl, the commitment, the tilegrid), the Vivado version, the
part, the full scope check and the matrix. **Those hashes are integrity anchors** — they
detect substitution and prove nothing about provenance.

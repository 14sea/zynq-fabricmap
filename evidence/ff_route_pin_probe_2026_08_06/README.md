# Route-pin probe, mine site only — the mechanism works; the mine site cannot prove it

Probe only. No recipe-domain file was touched, nothing here produced a committed
specimen, only `SLICE_X2Y25` was built, and no bitstream, frame or holdout artifact was
read. Tools: `vivado/probe/route_pin/probe_route_pin.tcl`, `scripts/probe_route_pin.py`.

## What was tested

The 2026-08-06 holdout run failed T2 because `SLICE_X25Y25_base` and `…_ce_tied` — two
specimens of one committed pair, differing in one control connection — routed the
dedicated net `w1` along different paths. The proposed fix routes the dedicated nets
**first**, into a fabric where nothing else is routed, then freezes them:

```tcl
place_design
route_design -nets $dedicated      ;# nothing else is routed yet, so the target slice's
snap first_pass                    ;#   contents cannot present as congestion
set_property IS_ROUTE_FIXED 1 $dedicated
route_design -directive $directive ;# the rest
snap final
```

14 builds: two flows (`current`, `pinned`) × variants (`base`, `ce_tied`, `latch`,
`async`, `clkinv`) × router directives (`Default`, `Explore`, `AlternateCLBRouting`,
`NoTimingRelaxation`).

## Results

| question | answer |
|---|---|
| pinned flow: did the second pass move anything the first pass routed? | **no — 0 of 9, in all 8 pinned runs**, read back from the design rather than assumed from the property |
| pinned flow: do all runs agree on the dedicated routes? | **yes — 8 runs, 1 distinct route set**, across 5 variants and 3 directives |
| current flow: do all runs agree? | yes — 6 runs, 1 distinct route set |
| **was the failure reproduced on the mine site?** | **NO** |

**Six of the nine nets have a route to pin; three do not.** `q`, `anchor_o` and
`anchor_o2` are pad nets — Vivado reports `ROUTE_STATUS = INTRASITE` and says so itself
(`[Route 35-50] Skipped 3 intrasite nets`, `[Route 35-47] Routing for 6 nets will be
attempted`). They have no interconnect route in any of the 14 runs; their placement is
fully determined by `PACKAGE_PIN`. So `IS_ROUTE_FIXED` reads 0 on them. That is not a net
that resisted pinning and it is **not** a tier being quietly downgraded — it is a net with
no routing degree of freedom to fix. The T2 comparison domain is unchanged: all nine are
still compared, exactly as before.

`qr1` is the one net with two distinct routes in the matrix — one under each flow, each
internally consistent across all its runs. That is evidence *for* the mechanism rather
than against it: `qr1` (`q_reduce1` → `q_reduce2`, both in the anchor slice) genuinely has
routing freedom, and which path it takes depends on when it is routed relative to
everything else. The pinned flow removes that dependency by always routing it first.

## What this does and does not establish

Establishes: after `place_design`, whose result is fully constrained and identical across
variants, the first pass routes six nets into an empty fabric and produces the same
result for `base`, `ce_tied`, `latch` (four storage elements, LDCE), `async` and
`clkinv`; and the freeze then survives three different router directives, including
`Explore`, without a single net moving.

Does **not** establish that the `SLICE_X25Y25` failure is gone. The mine instance cannot
show that, and this is not a limitation of the probe: **the mine site does not exhibit the
failure at all.** Its 15 implementations already shared one route for all nine nets before
any change, and six current-flow runs across four router directives and two variants still
agree. The trigger is instance-local congestion at a site this probe may not touch.

So the honest status is: *mechanism argued and empirically consistent on one instance;
efficacy against the observed failure unproven.* Whoever reads this should not upgrade
that sentence.

## Reproduce

```bash
scripts/probe_route_pin.py --out build/probe_route_pin      # 14 builds, ~12 min
scripts/probe_route_pin.py --compare-only                   # re-derive the verdict
```

`verdict.json` records `trigger_reproduced: false` and `problems: []`. The probe prints
the "no trigger" caveat itself, so the limitation cannot be lost in the retelling.

## What is pinned here

`manifest.json` lists every file in this directory with its sha256, plus the probe's own
script and Tcl, the two recipe-domain files it *read* (`specimen_ff_formal.v`,
`ff_formal_readback.tcl` — read, never modified), the Vivado version, the part, the site
mapping and the full run matrix. **Those hashes are integrity anchors**: they detect
substitution of these files. They do not prove Vivado produced these snapshots, and they
are not a target for any later run to reproduce.

The driver transcript is `probe_run.txt`, not `.log`: the first version of this directory
saved it as `probe_run.log`, which `.gitignore`'s `*.log` rule silently excluded, so this
README referenced a file the commit did not contain. `scripts/probe_route_pin.py
--evidence <dir>` now copies and pins everything it lists, and asserts each listed file
exists.

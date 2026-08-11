# Claim B round 1 — carrier build, 2026-08-11

Acceptance ladder step 4 (`docs/claimb_carrier_design.md` §7): the `phenotype_manifest`
emitted from the built carrier, with the records that make it checkable.

Built under [architecture erratum 001](../../docs/claimb_erratum_001_static_routes.md).

| file | what it is |
| --- | --- |
| `phenotype_manifest.json` | the write envelope, derived from the **final routed carrier bitstream**: 12 target + 3 flush frames, 1608 words = 6432 bytes |
| `carrier_build.json` | provenance written by `build_carrier.tcl` at `write_bitstream` — the only point in the flow that knows the file is the routed design whose cell isolation passed |
| `carrier_base_gate.json` | `gate_carrier_base.py`'s verdict binding the manifest's base to that bitstream |
| `isolation.txt` | cell-ownership **verdict** (target 6, flush 0) plus the route **evidence** record — inventories and hashes, exempting nothing by name |
| `carrier_eco.json` | the post-route INIT ECO: `evolvable_0` at `SLICE_X2Y25/A6LUT`, `0x0…0` → `0x0000000900000001`, `reimplemented=false` |
| `init_eco_verdict.json` | §4 check 3: 2 of 5144 frames differ, exactly the 2 the map predicts; 3 predicted bits moved; no stray bits; every ECC a correct recomputation |

## The bitstream itself is NOT in this directory

`carrier.bit` is 2,083,863 bytes and stays in `build/carrier_left/`, which is gitignored.
Committing bitstreams is the open Git LFS question ruled for `staging/**/*.bit` on
2026-08-09 and it is not settled for `gate_runs/`, so nothing here decides it. What is
committed is the **sha256 that pins it**:

```
carrier.bit      e677d09753d6f248775815d61b272071b3cad9c749336e7a8d864893d881eb23
post_route.dcp   4d3dba7c6a003ed42c4a78b82d95763ea576442610b817e073a394aecf17ac1e
```

**A rebuild does not reproduce that hash.** `write_bitstream` stamps a timestamp into the
header, so two builds of identical RTL give identical frames and different files —
measured here as `dd8bf0b8…` then `e677d097…`. Re-running the build therefore invalidates
this manifest by design, and `gate_carrier_base.py` will say so rather than let a stale
base through.

## Measurements

```
LUTs      680 logic + 112 LUTRAM = 792   of 800 sites in pb_logic
FFs       531                            of 1600
control sets 52
WNS       +7.048 ns at 50 MHz
cells     target columns 6, flush columns 0            (VERDICT: pass)
routes    flush segments 153 nets, target segments 401,
          of which 395 are not evolvable data nets     (EVIDENCE: erratum 001)
```

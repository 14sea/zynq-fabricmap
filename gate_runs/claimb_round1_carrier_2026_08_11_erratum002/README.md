# Claim B round 1 — carrier build, 2026-08-11 (erratum 002)

Acceptance ladder step 4 (`docs/claimb_carrier_design.md` §7), built under
[architecture erratum 001](../../docs/claimb_erratum_001_static_routes.md) and
[architecture erratum 002](../../docs/claimb_erratum_002_ps7_axi3.md).

**This directory is the authority for the carrier, and it SUPERSEDES
`gate_runs/claimb_round1_carrier_2026_08_11`.** That run's carrier cannot be reached from
the PS at all: `carrier_top.v` wired PS7's AXI3 `M_AXI_GP0` with the AXI4-Lite signal set,
leaving `MAXIGP0RLAST` tied low, so the first PS read stalled the A9 on board `17A6` and the
board needed a power cycle. Nothing was ever scored against it. It stays in history as the
record of that, and no device write may use it.

## What changed, and what did not

**Changed** — carrier feasibility only:
* `carrier_axi3_lite.v`, a real AXI3→AXI4-Lite bridge: beat-by-beat burst conversion,
  BID/RID/RLAST, and every unsupported or malformed transaction COMPLETED with SLVERR
  rather than left hanging. Benched by an independent AXI3 master, 17/17 mutations caught.
* `pb_logic` gains `SLICE_X6Y0:SLICE_X7Y99` — CLBLM_R_X5, baseaddr `0x00400B80`, **not one
  of the 15 written FARs**. Ruled 2026-08-11: necessary because the shim puts the design at
  837 LUTs post-opt against 800 sites; admissible because erratum 001 made cell ownership
  the verdict and crossing nets an evidence record. This is the final floorplan.

**Not changed**: the map, the 292 certified addresses, the target sites, the seed, the
fitness, the train/holdout split, the A/B rules, the write envelope, the ECC port, the host
gate, the guard and the board interlock.

## Reproducing the verdicts from a fresh clone

```
git clone <remote> && cd zynq-fabricmap
git lfs pull
python3 scripts/gate_carrier_base.py --run-dir gate_runs/claimb_round1_carrier_2026_08_11_erratum002
python3 scripts/gate_init_eco.py     --run-dir gate_runs/claimb_round1_carrier_2026_08_11_erratum002
```

Both take a run directory and **nothing else**: every path, every expected digest and the
ECO's `by_lut` key come from `carrier_run.json`. An operator who chooses the inputs chooses
the verdict. Without `git lfs pull` the artifacts are ~130-byte pointers and both gates say
so by name.

| file | what it is | in Git as |
| --- | --- | --- |
| `carrier_run.json` | the bundle: every artifact pinned by sha256, ECO LUT key derived from the tilegrid | ordinary |
| `carrier.bit` | the final routed carrier — the base every candidate is judged against | **LFS** |
| `carrier_eco.bit` | the post-route INIT ECO variant | **LFS** |
| `post_route.dcp` | the routed checkpoint the ECO was taken from | **LFS** |
| `local_map.json` | the canonical map, 292 addresses over 12 frames, 6 LUTs | ordinary |
| `phenotype_manifest.json` | the write envelope: 12 target + 3 flush frames, 1608 words = 6432 bytes | ordinary |
| `carrier_build.json` | provenance written by `build_carrier.tcl` at `write_bitstream` | ordinary |
| `carrier_eco.json` | the ECO: `evolvable_0` at `SLICE_X2Y25/A6LUT`, `0x0…0` → `0x0000000900000001` | ordinary |
| `isolation.txt` | cell-ownership **verdict** (target 6, flush 0) and the route **evidence** | ordinary |

Verdict files are not here. A bundle that pinned its own verdicts would be pinning the
answer.

## Publishing another run

```
git add gate_runs/<run_id>
python3 scripts/gate_publish_carrier_run.py --run-root gate_runs/<run_id>   # must pass
git commit -m "gate_runs: …"
```

The gate reads the **index**, not the working tree.

## What this carrier was built from

```
source_commit  9bd902ebc3bf164741e24639fbd340ae6d4f33dd
source_tree    clean
sources        13 files pinned by sha256 — 6 RTL (the shim is new), the XDC,
               build_carrier.tcl, isolation_checks.tcl, and the 4 generated inputs
```

`gate_carrier_base.py` requires every one of those to equal its HEAD blob.

```
carrier.bit      7c6bba90c63833552859d7d5374375ef5da4da1bae4ca68d31872e64e6a96bc6
carrier_eco.bit  e8ffa654dd7e6a3eaf79276361c0c072b410a1899c7907c572bc393a4d4ebb8e
post_route.dcp   b7a5f5b77d317d70b6b8effeb0507272f47d59437247010df8bc476c23573f99
```

## Measurements

```
LUTs      688 logic + 110 LUTRAM = 798   of 1600 sites in pb_logic (two ranges)
FFs       see post_route_util in build/
WNS       +6.716 ns at 50 MHz
cells     target columns 6, flush columns 0            (VERDICT: pass)
routes    see isolation.txt)  (EVIDENCE: erratum 001)
INIT ECO  the differential is the verdict of scripts/gate_init_eco.py, not of this file
```

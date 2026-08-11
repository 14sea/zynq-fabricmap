# Claim B round 1 — carrier build, 2026-08-11

Acceptance ladder step 4 (`docs/claimb_carrier_design.md` §7), built under
[architecture erratum 001](../../docs/claimb_erratum_001_static_routes.md).

**This directory is the authority for the carrier.** Under erratum 001 the safety rule is
bit invariance against **one exact bitstream**, and `write_bitstream` stamps a timestamp
into the header — so a rebuild produces identical frames in a *different file*, measured
here as `dd8bf0b8…` then `e677d097…`. Keeping the sha256 and discarding the bytes it names
would leave an authority nobody outside one workstation could exercise, so the exact
artifacts are published with the records, via Git LFS.

## Reproducing the verdicts from a fresh clone

```
git clone <remote> && cd zynq-fabricmap
git lfs pull
python3 scripts/gate_carrier_base.py --run-dir gate_runs/claimb_round1_carrier_2026_08_11
python3 scripts/gate_init_eco.py     --run-dir gate_runs/claimb_round1_carrier_2026_08_11
```

Both take a run directory and **nothing else**: every path, every expected digest and the
ECO's `by_lut` key come from `carrier_run.json`. Neither accepts a map, a LUT key or a
bitstream on the command line, because an operator who chooses the inputs chooses the
verdict. Without `git lfs pull` the artifacts are ~130-byte pointers and both gates say so
by name rather than failing with a confusing digest mismatch.

| file | what it is | in Git as |
| --- | --- | --- |
| `carrier_run.json` | the bundle: every artifact pinned by sha256, plus the ECO's LUT key **derived** from the tilegrid rather than typed in | ordinary |
| `carrier.bit` | the final routed carrier — the base every candidate is judged against | **LFS** |
| `carrier_eco.bit` | the post-route INIT ECO variant | **LFS** |
| `post_route.dcp` | the routed checkpoint the ECO was taken from | **LFS** |
| `local_map.json` | the canonical map, 292 addresses over 12 frames, 6 LUTs | ordinary |
| `phenotype_manifest.json` | the write envelope: 12 target + 3 flush frames, 1608 words = 6432 bytes | ordinary |
| `carrier_build.json` | provenance written by `build_carrier.tcl` at `write_bitstream` | ordinary |
| `carrier_eco.json` | the ECO: `evolvable_0` at `SLICE_X2Y25/A6LUT`, `0x0…0` → `0x0000000900000001`, `reimplemented=false` | ordinary |
| `isolation.txt` | cell-ownership **verdict** (target 6, flush 0) and the route **evidence** — inventories and hashes, exempting nothing by name | ordinary |

Verdict files are **not** in this directory. They are outputs of the gates that read this
bundle, and a bundle that pinned its own verdicts would be pinning the answer.

## Publishing another run

```
git add gate_runs/<run_id>
python3 scripts/gate_publish_carrier_run.py --run-root gate_runs/<run_id>   # must pass
git commit -m "gate_runs: …"
```

The gate reads the **index**, not the working tree: the LFS filter can be defeated at
`git add` (`-c filter.lfs.process=`) or by editing `.gitattributes` first, and committing
binary into ordinary history is the one mistake here a later commit does not undo. It
requires `.gitattributes` unchanged in the index — a publication commit does not stage its
own policy — every LFS pointer's oid to equal the bundle's pin, and every ordinary blob's
bytes to hash to it.

## What this carrier was built from

```
source_commit  a9b0703fda66b785596941cc00481f325587c472
source_tree    clean
sources        12 files pinned by sha256 — 5 RTL, the XDC, build_carrier.tcl,
               isolation_checks.tcl, and the 4 generated inputs
```

`gate_carrier_base.py` requires every one of those to equal its HEAD blob. An earlier
publication was built before the scorer's recovery interlock landed: the RTL was edited
afterwards, the benches verified the new sources, and the exact bitstream a board would
have loaded was the pre-fix one. Output hashes alone could not have said so, which is why
the sources are pinned and checked.

```
carrier.bit      25681f363916587ecfdd96ef6dd76c86bb73267ef44f38d1270f85f9ec3f7b37
carrier_eco.bit  bf57d25360b2fc2d08606ccb90efcda8d8de175a2b5b37d72e9a21d52e2cf2ef
post_route.dcp   513ae01321b7dba41954dc812f4b888f00de49747af90d98ec70bc9a01d1f871
```

## Measurements

```
LUTs      668 logic + 112 LUTRAM = 780   of 800 sites in pb_logic
FFs       532                            of 1600
control sets 52
WNS       +5.598 ns at 50 MHz
cells     target columns 6, flush columns 0            (VERDICT: pass)
routes    flush segments 159 nets, target segments 374,
          of which 368 are not evolvable data nets     (EVIDENCE: erratum 001)
INIT ECO  2 of 5144 frames differ, exactly the 2 the map predicts;
          3 predicted bits moved; no stray bits; ECC a correct recomputation
```

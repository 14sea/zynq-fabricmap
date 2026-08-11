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

## Measurements

```
LUTs      680 logic + 112 LUTRAM = 792   of 800 sites in pb_logic
FFs       531                            of 1600
control sets 52
WNS       +7.048 ns at 50 MHz
cells     target columns 6, flush columns 0            (VERDICT: pass)
routes    flush segments 153 nets, target segments 401,
          of which 395 are not evolvable data nets     (EVIDENCE: erratum 001)
INIT ECO  2 of 5144 frames differ, exactly the 2 the map predicts;
          3 predicted bits moved; no stray bits; ECC a correct recomputation
```

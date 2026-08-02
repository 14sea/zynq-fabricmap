# `data/` — the frozen prjxray subset

This directory is a **freeze**, not a working copy. Nothing here is edited by hand.

| file | what it is |
|---|---|
| `subset_spec.json` | the only place the subset is defined: which upstream files are frozen, and the bit-class taxonomy they are cut into. Hand-maintained. |
| `MANIFEST.json` | the freeze record produced by `scripts/extract_prjxray_subset.py`: per-file sha256/size/counts, upstream commit, cross-family audit result, per-bit-class entry counts and certification slots. Generated. |
| `prjxray/` | verbatim byte-identical copies of the upstream files, at their upstream paths. Generated. |

## Provenance

Upstream: **[f4pga/prjxray-db](https://github.com/f4pga/prjxray-db)** @ `0a0adde`
(2021-12-14), licence **CC0-1.0** (`prjxray/LICENSE`, frozen alongside the data).
The upstream project is archived; its fuzzers are pinned to Vivado 2017.2 and are
**not** a dependency of this repo — see `docs/kickoff_fuzz_and_map.md` §4.

The dependency risk of an archived database is *tool* rot, not *data* rot: the `.db`
files are static text, so a frozen copy plus this provenance note resolves it
completely. Re-mining upstream's work is unnecessary; **independence comes from
validation, not re-derivation** — every bit class enters the whitelist only through
our own Vivado specimen-diff prediction gate, and after that the authority is our
certificates. What is frozen here is an *index*.

## Reproducing / checking the freeze

```bash
scripts/extract_prjxray_subset.py --src /path/to/prjxray-db   # re-freeze
scripts/extract_prjxray_subset.py --verify                    # integrity check
```

`--verify` needs neither prjxray-db nor Vivado: it recomputes every hash and every
count from this directory alone and fails on tampering, on files that drifted from
the manifest, and on untracked files under `prjxray/`. Run it before trusting any
certificate that cites this data. Format details: `docs/freeze_format.md`.

## What the extraction established (2026-08-02)

- **46 files, 16.6 MB, 10,896 features, all classified.** No feature in the frozen
  set falls outside the six declared bit classes (`unclassified_policy: fail`).
- **The "7-series shares one fabric" audit is now machine-checked, not remembered.**
  Of 34 rule files compared against artix7: **28 byte-identical**, 2 rule-equivalent
  (`segbits_int_l/r.origin_info.db` — same feature→bits rules, different
  `origin:<fuzzer>` provenance labels), and **4 with a real delta**.
- **The real delta is in the CLB mask files.** `mask_clb{ll,lm}_{l,r}.db` each list
  4 bits in artix7 that zynq7 does not (`34_15`, `34_31`, `34_47`, `34_63` — one per
  16-row group). Masks mark bits known to move without belonging to a documented
  feature. zynq7's masks being the *smaller* set is the safe direction: an
  unmasked, unattributed bit in a specimen diff raises an alarm instead of being
  silently swallowed. **Do not paper over this by unioning in the artix7 masks** —
  if the gate trips on one of those four bits, that is a finding to certify, and it
  is recorded here so the trip is recognised rather than re-derived.
- **Device sanity check** (`device_summary` in the manifest): 13,440 tiles, of which
  2,200 CLB (400 `CLBLL_L` + 300 `CLBLL_R` + 600 `CLBLM_L` + 900 `CLBLM_R`) and
  3,200 INT. 2,200 CLB × 2 slices × 8 LUTs = the 17,600 LUTs of an XC7Z010. The
  geometry is for the right die.

## Deliberately *not* frozen

IOB/IOI, BRAM, DSP, CLK/HCLK tile classes. Nothing in this line touches them, and a
subset in which every single line is classified is what makes the
`unclassified_policy: fail` invariant load-bearing. Adding a group is a MINOR bump of
`subset_spec.json` plus a re-extraction — cheap, and deliberately explicit.

`mask_int_*.db` does not exist upstream (INT tiles have no mask file). That is
expected, not a missing file.

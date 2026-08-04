# Mux groups are defined by bits, not by names

A finding from the first `clb_mux` work, recorded separately because it changes a
safety rule rather than a tool.

## The rule this is about

`zynq-autoehw/docs/schema.md` §5 gives the `safety_whitelist` a composition rule:

```yaml
composition_rules:
  one_selected_input_per_mux_group: true
```

The rule is right. What it does not say is **how a mux group is determined**, and the
obvious answer is wrong.

## Names suggest a grouping and are wrong about it

Feature names look like `<tile>.<site>.<GROUP>.<MEMBER>`, which invites grouping by the
prefix up to the last dot. Two examples from the frozen `segbits_clbll_l.db`:

```
CLBLL_L.SLICEL_X0.AFFMUX.AX    !30_00  30_01 !30_02 !30_03
CLBLL_L.SLICEL_X0.AFFMUX.CY     30_00 !30_01  30_02 !30_03
CLBLL_L.SLICEL_X0.AFFMUX.XOR   !30_00 !30_01  30_02 !30_03
CLBLL_L.SLICEL_X0.AFFMUX.F7     30_00  30_01 !30_02 !30_03
CLBLL_L.SLICEL_X0.AFFMUX.O5     30_00 !30_01 !30_02  30_03
CLBLL_L.SLICEL_X0.AFFMUX.O6    !30_00 !30_01 !30_02  30_03

CLBLL_L.SLICEL_X0.CARRY4.ACY0   30_15
CLBLL_L.SLICEL_X0.CARRY4.BCY0   01_15
CLBLL_L.SLICEL_X0.CARRY4.CCY0   30_48
CLBLL_L.SLICEL_X0.CARRY4.DCY0   30_49
```

`AFFMUX` is a real mux: six members, one shared 4-bit field, mutually exclusive
encodings. `CARRY4` is not: four **independent booleans**, each on its own bit, that
happen to share a name prefix. Applying "at most one member may be selected" to the
second set is simply false — a design using all four carry stages sets all four bits,
legally.

## Measured, not argued

Decoding every CLB tile of the die (2,200 tiles × 42-43 groups) out of real bitstreams:

| grouping | evaluations | decoded to one | violations |
|---|---|---|---|
| by name prefix | 61,600 per bitstream | — | **160** in `dfx_top.bit`, all `CARRY4` |
| by bit set | 281,700 over 3 bitstreams | 23,910 | **0** |

### The evidence, pinned

Two of the three bitstreams are not ours, which is what makes the sample worth
something:

| bitstream | origin | sha256 |
|---|---|---|
| `spec_0000000000000000.bit` | our LUT specimen, `run_2026_08_02_a` | `8711ee7a0deb6d85d2f4741d7a91336c9b8460e766f425033967f49ae8900339` |
| `dfx_top.bit` | `zynq-autoehw` DFX design (2026-07-11) | `08552db39fcc567c4cc48d394f9fd6de45fe64c8a8278c7555c12596913dbb3c` |
| `design_1_wrapper.bit` | EBAZ4203 **vendor** `boardtest` design | `7c6d1d14f408925da8c86412e6665e7c805c9016abddca3ecfb05f650d184859` |

Full per-bitstream counts: `gate_runs/mux_group_scan_2026_08_02/scan.json`
(schema `mux_group_scan` 1.0.0). Reproduce:

```sh
scripts/decode_groups.py --sweep <the three .bit files> \
    --json gate_runs/mux_group_scan_2026_08_02/scan.json
```

It exits non-zero if any group decodes to more than one member, so the claim is a
check rather than a report. The counts are recomputable from the frozen data plus
those three files alone.

## The rule, corrected

> A mux group is a **maximal set of features sharing an identical bit-address set**
> (polarity ignored). The common name prefix is a label for humans, never the
> definition. Features that share a prefix but not a bit set are independent and the
> one-selected-input rule does not apply to them.

Consequences worth carrying forward:

- A whitelist implementation that groups by name will **falsely reject legal
  configurations** — every carry-using design, on this evidence.
- `at most one`, not `exactly one`: 89,331 of 93,900 group evaluations in the vendor
  design match **no listed member**, so a checker that demands a selection everywhere
  would reject a real vendor bitstream. **Wording corrected 2026-08-03:** this said "an
  unset group is the normal state", which reads the scan as evidence that those groups
  are *unset* and benign. It is not. The scan establishes only that no listed codeword
  matched; what such a pattern does to the silicon is not recorded by the frozen DB. See
  the erratum below.
- ~~The composition rule itself survives contact with real data: zero violations in
  281,700 evaluations, once groups are derived correctly. That is the first
  **real-bitstream** evidence for the rule the safety whitelist depends on — previously
  it was only ever exercised by fixtures.~~ **Retracted 2026-08-03 — see the erratum
  below. That zero is a tautology, not evidence.**

**Erratum 2026-08-03: "zero violations in 281,700 evaluations" is unfalsifiable.**
Raised in review of `docs/round9_request.md` and confirmed by recomputation from the
freeze. A group is the maximal set of features sharing one polarity-free coordinate set,
so every member is a full 0/1 codeword over the same complete scope, and assert-iff means
"the observed assignment equals this member's codeword". If the members' codewords are
pairwise distinct, at most one can match **any** observation — so
`scripts/decode_groups.py`'s violation test (`len(matched) > 1`) can never fire. All
**170/170** `clb_mux` groups have pairwise-distinct codewords, six-member `AFFMUX`
included; so do all 168 `clb_ff_config` groups. The scan could not have reported
anything but zero.

What the scan does establish stands: 23,910 of 281,700 evaluations decoded to exactly one
listed member and 257,790 matched no listed codeword. That is a statement about the
database's coverage of observed patterns and nothing more — "unmatched" is not "unset",
and neither is evidence of safety. And the name-derived comparison above is **unaffected** — name-grouped "members"
do not share a scope, which is exactly why that variant could and did produce 160 real
violations.

**What the composition rule is, restated.** It is a
**DB/group/address consistency invariant**: a violation means the database, our address
arithmetic, or our grouping is broken. It is worth asserting and worth running for that
reason. It is **not** a safety gatekeeper, and the earlier wording here claimed too much:
under unique codewords it cannot reject any bitstream pattern whatsoever, so it can never
stop a bad write. The rule that *can* gate at runtime is decode-validity — the observed
pattern must be a listed codeword — and that one has teeth: across the 170 `clb_mux`
groups, **844 patterns are listed by no member**. Any safety whitelist should be built on
decode-validity, not on exclusivity.

**Caveat, and it is load-bearing.** 162 of those 844 are the all-zero pattern of a group
that does not list it (8 mux groups do list all-zero as a real member). Exempting
all-zero as "unset, therefore safe" drops the figure to 682 and makes `clb_ff_config`'s
168 groups and `clb_lutram`'s 36 look like they forbid **nothing** — their raw unlisted
counts are 160 and 30, every one the all-zero pattern of a one-bit group. **The frozen DB
does not establish that.** segbits files record which patterns name a member; they say
nothing about what an unnamed pattern does to the silicon, and nothing about all-zero
being benign. So the safe formulation is to require a listed codeword only for groups a
write actually touches, and to treat "all-zero = unset = safe" as an explicit policy
assumption if it is ever relied on. Either way, for the one-bit classes the write-safety
argument has to come from somewhere other than these rules.

Consequence for certification, **now applied**: run B's certificate used to report 32/32
holdout address assertions, of which the 16 `group_exclusivity` ones were tautologies.
It was re-emitted under certificate 1.4 (`docs/round9_ruling.md`) with the same
predictions, the same measurement and the same specimens — a recount, not a re-run — and
now reports **16/16 falsifiable address passes** (`strict_codeword_equality`), 16
**vacuous** exclusivity diagnostics, `decode_validity` 16/16 as a diagnostic, and
semantic `member_identity` 16/16. `clb_mux` was certified before and after; only the
count was wrong, and the old headline overstated the evidence by 2×. The 1.3 record is
archived byte-for-byte at `tests/fixtures/certificate_group13_run_b.json`, and
`tests/test_run_b_erratum.py` holds the boundary: it fails if any observation, hash or
pair-accounting record differs between the two, and if the vacuous outcome is ever put
back into `address_accounting`.

**Wording, deliberately.** This is real-bitstream evidence, not silicon evidence.
Every bitstream here came out of Vivado; nothing was loaded onto a board, and this
line has never touched one. An earlier version of this document and the messages of
commits `da1fbcb` and `0a3de1c` said "silicon-grade", which overstates it —
`da1fbcb` is already pushed and its message cannot be corrected in place, so the
correction is recorded here instead.

## Driving a mux structurally, and what the diff really contains

`vivado/specimen/specimen_mux.v` + `build_mux.tcl` build a LUT6 and an `FDRE` pinned
to one slice, with a parameter that changes **one netlist edge**: the FF's data source
is either the LUT output or a package pin. A mux selection is not a property that can
be set on a routed design, so each variant is its own implementation run — which is
exactly why isolation has to be re-established rather than assumed.

Measured on `SLICE_X2Y25` / `CLBLL_L_X2Y25`:

| variant | FF `D` source | decoded `AFFMUX` |
|---|---|---|
| `FFSRC=0` | LUT6 output | **`O6`** |
| `FFSRC=1` | package pin | **`AX`** |

That is a 4-bit, negation-bearing group switching with the netlist, and the member
*names* line up with the structure — `O6` when the data comes from the LUT's O6 output,
`AX` when it comes from the slice's bypass input. **This is netlist-level
corroboration, not silicon**: it says the database's naming agrees with what Vivado
built, not that the hardware behaves that way.

The diff between the two variants, classified by **who claims each bit**:

| class | bits | |
|---|---|---|
| uniquely db-attributed | **34** | 2 in `CLBLL_L_X2Y25` — `30_01` and `30_03`, exactly the `AFFMUX` members' differing bits — and 32 in INT tiles, routing that legitimately had to move |
| claimed by two databases | **0** | checked, not assumed |
| ownership unknown | **0** | |
| frame ECC | 140 | excluded by the stated rule |
| outside every tile | 0 | |

> **Corrected 2026-08-02.** An earlier version of this table reported 11
> `ownership_unknown` bits, four of them listing the tile under test, and argued at
> length that they must not be called INT bits. **That measurement was wrong and the
> argument rested on it.** `specimen_diff.locate()` formatted the segbit's frame offset
> without zero-padding (`f"{frame_off}_..."`), so every coordinate in frames `00`–`09`
> failed to match the database and fell into `ownership_unknown`. This is the **same
> `%02d_%02d` ambiguity** that broke the consumer's verifier in round 4 — and which
> `docs/freeze_format.md` §5.3 was written to pin down. Writing the normative fix and
> not auditing our own code for it is the whole of the mistake.
>
> After the fix, `ownership_unknown` across the entire run B is **zero**: 136 bits that
> had been reported as unowned are claimed by the frozen database. The rule below still
> stands as a rule; what changed is that it currently has nothing to bite on.

### What this means for the scoring contract

A structural class cannot use the whole-bitstream `fp_count == 0` rule that
`clb_lut_init` used, because the routing legitimately moves. But the replacement is
**not** "tile-wide exactness" either — that phrasing would quietly assert ownership of
those four bits. The contract is:

- **Prediction scope is an explicit bit-address set** — the mux group's own bits,
  enumerated — never "the tile".
- Every changed bit outside that scope is listed and labelled `db_attributed` (with the
  claiming tile and features) or `ownership_unknown` (with all candidates). Nothing is
  dropped and nothing is assigned by assumption.
- If a certificate ever wants to claim tile-wide exactness, then any
  `ownership_unknown` bit inside that tile's geometric range **must block a production
  PASS**. Unknown is not clean. As measured today the category is empty, so the rule is
  written before it is needed rather than after.

Were such bits to appear, nothing would check them: prjxray ships **no mask file for
INT tiles at all**, and the CLB mask does not list them.

### Ownership is decided by the database, not by the grid

Attributing those bits turned up a structural fact worth stating: **a CLB tile and its
neighbouring INT tile share the same `baseaddr` and the same word offset.**
`CLBLL_L_X2Y25` and `INT_L_X2Y25` are both `0x00400A00`, offset 51, words 2, and their
declared frame spans (36 and 28) overlap; the CLB database really does use frames
`00`, `01`, `26`–`35` while the INT database uses `00`–`25`.

Geometry therefore cannot say which tile owns a changed bit. The databases can, and do:
across all four CLB/INT pairings, **not one coordinate is claimed by both**
(648 vs 1598 claimed coordinates, empty intersection). `scripts/specimen_diff.py` now
resolves ownership by which database claims the coordinate, and records a finding if
two ever claim the same one — an assumption that stays a check rather than becoming a
belief.

## Not yet propagated to the consumer side

`zynq-autoehw/docs/schema.md` §5 still states `one_selected_input_per_mux_group`
without defining group membership. **This document is evidence, not a fix**: the
sibling repo is a read-only source from here (`docs/workflow.md`, isolation rule) and
has not been modified. Anything that implements the whitelist — here or there — needs
the bit-set definition carried across explicitly before it can be relied on; until
then, treat any name-derived grouping as unvalidated.

Tool: `scripts/decode_groups.py`, which reads absolute bit values (not a diff) and
decodes each group.

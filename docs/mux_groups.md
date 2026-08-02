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
  design decode to no member at all. An unset group is the normal state, so a checker
  that demands a selection everywhere is equally wrong.
- The composition rule itself survives contact with real data: zero violations in
  281,700 evaluations, once groups are derived correctly. That is the first
  **real-bitstream** evidence for the rule the safety whitelist depends on — previously
  it was only ever exercised by fixtures.

**Wording, deliberately.** This is real-bitstream evidence, not silicon evidence.
Every bitstream here came out of Vivado; nothing was loaded onto a board, and this
line has never touched one. An earlier version of this document and the messages of
commits `da1fbcb` and `0a3de1c` said "silicon-grade", which overstates it —
`da1fbcb` is already pushed and its message cannot be corrected in place, so the
correction is recorded here instead.

## Not yet propagated to the consumer side

`zynq-autoehw/docs/schema.md` §5 still states `one_selected_input_per_mux_group`
without defining group membership. **This document is evidence, not a fix**: the
sibling repo is a read-only source from here (`docs/workflow.md`, isolation rule) and
has not been modified. Anything that implements the whitelist — here or there — needs
the bit-set definition carried across explicitly before it can be relied on; until
then, treat any name-derived grouping as unvalidated.

Tool: `scripts/decode_groups.py`, which reads absolute bit values (not a diff) and
decodes each group.

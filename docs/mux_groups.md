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

The three bitstreams are independent and not ours in two cases: a full `zynq-autoehw`
DFX design, the EBAZ4203 vendor `boardtest` design, and one of our LUT specimens.

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
  silicon-grade evidence for the rule the safety whitelist depends on — previously it
  was only ever exercised by fixtures.

Tool: `scripts/decode_groups.py`, which reads absolute bit values (not a diff) and
decodes each group.

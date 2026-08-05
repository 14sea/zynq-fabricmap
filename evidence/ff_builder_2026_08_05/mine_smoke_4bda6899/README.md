# Mine-instance smoke — `SLICE_X2Y25`, builder `4bda6899`, 2026-08-05

**Scope: the mine site only. No holdout instance has been built, in this run or any
other.** `SLICE_X2Y25`'s evidence was already spent before this line began and can never
score, which is why the smoke costs nothing scientifically.

**The run is deliberately INCOMPLETE and reports itself so: 15/120 implementations,
23/184 specimens.** `--instance` can satisfy at most that, arithmetically, so a smoke can
never be mistaken for a certification build.

Contents: `run_report.json` (the builder's own accounting) and, per specimen,
`stamp.json` + `readback.tsv`. Checkpoints and bitstreams stay in gitignored `build/` —
their sha256 values are pinned in the stamps and in the run report.

## 1. One recipe, across all 23 specimens

Checked by hash, not by completion count — the aborted attempt recorded in
`../aborted_619f3288/` read a perfectly ordinary 8-of-15 while pinning a builder that no
longer existed.

**23 of 23 specimens share exactly one recipe fingerprint:**

| recipe input | sha256 (16) |
|---|---|
| `scripts/gate_build_ff_formal.py` | `4bda6899a1965b34` |
| `vivado/specimen/specimen_ff_formal.v` | `47b2e3fade7a1943` |
| `vivado/specimen/build_ff_formal.tcl` | `a54a546a8e1ada44` |
| `vivado/specimen/derive_ff_formal.tcl` | `9f3ebcfb704838b3` |
| `vivado/specimen/ff_formal_readback.tcl` | `ad69919d6cf2caa0` |
| commitment (authority A) | `5440ef27acbd5b4f` |
| pre-registration plan (authority B) | `ac9dbab8ba299360` |
| part / Vivado | `xc7z010clg400-1` / `2025.2` |

Every stamp reads `completed: true` and every recorded artifact hash still matches the
file on disk.

## 2. The dedicated-net set, independently reproduced

`docs/ff_builder_design.md` §5.3's erratum (`7c8d619`) was measured against an artifact
that was subsequently destroyed, so it owed a reproduction from artifacts that exist. It
has one: recomputing from all 23 readbacks of this run gives **one distinct dedicated set,
of size nine, equal to `EXPECTED_DEDICATED`**, on every specimen:

```
anchor_o  anchor_o2  anchor_o2_OBUF  anchor_o_OBUF  q  q_OBUF  qr1  w1  w2
```

The erratum is confirmed, not merely carried forward. Shared-net counts are 30 (the
four-element latch family) or 38 (the eight-element family) — the difference is the four
`d_k` nets that do not exist when only four storage elements are instantiated.

## 3. Per-pair accounting — 21 pairs, T1 = 0, T2 = 0

168 ÷ 8 = 21 committed pairs for this instance: twenty against `base`, plus
`latch` ↔ `latch_base`. Enumerated from the commitment, not from the build tree.

| pair | T1 | T2 | T3 | status |
|---|---|---|---|---|
| `async` ^ `base` | 0 | 0 | 1 | pass |
| `base` ^ `ce_tied` | 0 | 0 | 6 | pass |
| `base` ^ `clkinv` | 0 | 0 | 0 | pass |
| `base` ^ `sr_tied` | 0 | 0 | 4 | pass |
| `base` ^ `zini_{AFF,A5FF,BFF,B5FF,CFF,C5FF,DFF,D5FF}` | 0 | 0 | 0 | pass ×8 |
| `base` ^ `zrst_{AFF,A5FF,BFF,B5FF,CFF,C5FF,DFF,D5FF}` | 0 | 0 | 1 | pass ×8 |
| `latch` ^ `latch_base` | 0 | 0 | 2 | pass |

**Totals: T1 = 0, T2 = 0, T3 = 21.**

## 4. Every T3 diagnostic, and why each one is topology rather than fault

Tier 3 is shared nets: recorded and reported, never a FAIL. Each entry below is a
consequence of the variant's own definition.

| pair | net | field | cause |
|---|---|---|---|
| `async` ^ `base` | `rst_IBUF` | sinks | `FDRE.R` → `FDCE.CLR`: a different control pin |
| `base` ^ `ce_tied` | `ce_IBUF` | sinks, route, pips | the variant ties target CE to `1'b1`, so the net loses eight sinks and the router takes a shorter path |
| | `<const1>` | sinks | those eight CE pins move onto the constant net |
| | `rst_IBUF` | route, pips | rerouted around the freed resources; its sink set is unchanged |
| `base` ^ `sr_tied` | `rst_IBUF` | sinks, route, pips | the variant ties target R to `1'b0` |
| | `<const0>` | sinks | the eight R pins move onto the constant net |
| `base` ^ `zrst_*` (×8) | `rst_IBUF` | sinks | that one flip-flop is `FDSE`, so its control pin is `S`, not `R` |
| `latch` ^ `latch_base` | `ce_IBUF` | sinks | `FDCE.CE` → `LDCE.GE` |
| | `clk_g` | sinks | `FDCE.C` → `LDCE.G` |

**Twelve of the twenty-one pairs carry at least one T3 difference.** Under revision 2's
untiered comparison — full sink-set and `ROUTE` equality on every net touching an anchor
pin — all twelve would have failed, every one of them a false failure on a correct build.
That is the concrete measurement behind the tiering ruling.

## 5. The derived chain

One place-and-route serving nine bitstreams. All eight derived specimens pin **the same**
`base.dcp` (`5dfe79b7…`) and each writes its own `derived.dcp`, so the `INIT=0` state the
attestation describes exists on disk rather than only in principle.

| specimen | changed readback key | resolved BEL | `derived.dcp` | `spec.bit` |
|---|---|---|---|---|
| `zini_AFF` | `store.0.init` | `SLICEL.AFF` | `b817a953` | `b88f8ca6` |
| `zini_A5FF` | `store.1.init` | `SLICEL.A5FF` | `93722432` | `f7b71dc5` |
| `zini_BFF` | `store.2.init` | `SLICEL.BFF` | `f31fcf19` | `642dc729` |
| `zini_B5FF` | `store.3.init` | `SLICEL.B5FF` | `2a7729cd` | `262d006a` |
| `zini_CFF` | `store.4.init` | `SLICEL.CFF` | `661fb313` | `25edf89c` |
| `zini_C5FF` | `store.5.init` | `SLICEL.C5FF` | `1597fe43` | `52b8db6a` |
| `zini_DFF` | `store.6.init` | `SLICEL.DFF` | `f6ab5835` | `8e4172ab` |
| `zini_D5FF` | `store.7.init` | `SLICEL.D5FF` | `9d979fe7` | `c653a5e9` |

Eight distinct checkpoints, eight distinct bitstreams, one source checkpoint.
**`unexpected` differences: 0** — across the full three-tier domain, shared nets included,
the only readback key that moved in each derived specimen is that one `INIT`, `1'b1` →
`1'b0`.

The index-to-flip-flop mapping is confirmed rather than assumed: `base`'s readback resolves
`store.0…store.7` to `AFF, A5FF, BFF, B5FF, CFF, C5FF, DFF, D5FF`, exactly the builder's
`FF_ORDER`. A disagreement there would have silently changed the wrong flip-flop in all
eight, and each one would still have built and still looked correct.

## 6. What this run does NOT establish

* **No false-positive result exists, and none can at this stage.** FP,
  `ownership_unknown` and `unattributed` are outputs of `gate_measure_ff.py`, which
  §7.6 forbids on an incomplete run — and this run is incomplete by construction. So the
  "stop if the smoke produces an FP" condition has **not been satisfied; it has been left
  unevaluated.** Nothing here should be read as "the bit accounting is clean".
* **Nothing has been on a board.** This is address prediction from frozen rules, not
  silicon semantics.
* `ROUTE_STATUS` is a completion flag throughout; path identity comes from the per-net
  `ROUTE`/PIP readback, and only inside tier 2.
* Checkpoint and bitstream hashes anchor integrity. They do not prove the bitstream came
  from that checkpoint.

# Claim B round 1 — carrier build, 2026-08-13 (erratum 006)

Acceptance ladder step 4 (`docs/claimb_carrier_design.md` §7), built under errata
[001](../../docs/claimb_erratum_001_static_routes.md),
[002](../../docs/claimb_erratum_002_ps7_axi3.md),
[003](../../docs/claimb_erratum_003_config_idcode_and_refusal.md),
[004](../../docs/claimb_erratum_004_icap_readback.md),
[005](../../docs/claimb_erratum_005_fdro_contiguity.md) and
[006](../../docs/claimb_erratum_006_command_order.md), to the sequence derived in
[the ICAPE2 readback derivation](../../docs/claimb_icape2_readback_sequence.md).

**This directory is the authority for the carrier, and it SUPERSEDES
`gate_runs/claimb_round1_carrier_2026_08_13_erratum005`.** That build was the first to read
**real configuration data** off silicon — a bit-exact 101-word slice of the device's own
stream, which is strictly further than anything before it. But it read the **wrong frame**:
the staged window sat at `0x00400A81`/`0x00400A82`, **+604 words** from the `0x00400A20` it
asked for. Its readback loaded FAR before the RCFG that gives FAR its meaning, and UG470
executes the command CMD is holding at the moment FAR is loaded. A readback that is
confidently wrong is worse than one that obviously fails, so no device write may use it.

## What changed, and what did not

**Changed** — the order of seven words, and nothing else:

* `RB_SETUP` now emits **`CMD1, RCFG, NOOP, FAR1, frame_far, FDRO0, RDLEN`**. It used to
  emit `FAR1, frame_far, CMD1, RCFG, NOOP, FDRO0, RDLEN`. Same seven words, same length,
  same timing, same everything else.
* `icape2_model.v` gained `pend_wcfg`/`pend_rcfg`: a command written to CMD is **held**, and
  a write to `REG_FAR` **executes** it. This is what makes command order observable at all.
  Before it, the model set `rcfg` on the CMD payload and checked `E_NO_RCFG` only at FDRO,
  so a stream that wrote FAR then RCFG established a read anyway — and every bench passed
  against RTL that did not follow the documented sequence.
* `tb_icape2_model.v`'s `seq_readback` helper had the defective order baked in, because it
  was written to match the RTL. Corrected, with the old order kept as a fixture
  (`seq_readback_far_before_rcfg`) so the rule that rejects it stays tested.

**`RB_WORDS` is unchanged at 202, deliberately.** An earlier reading called it a length
defect against `rb_skip = rb_lat + SKIP_FRAME`; that is **retracted**. UG470 defines the
FDRO Type-2 count as `101 * (frames + 1 pad) = 202`, and pipeline latency clocks are not
part of a word count.

**Unchanged:** the target, the seed, the ceiling, the cap, the masks, the fitness, the
train/holdout split, the A/B rules, the floorplan (`pb_logic` still
`SLICE_X0Y0:SLICE_X1Y99` + `SLICE_X6Y0:SLICE_X7Y99`), the map, the AXI register map, the
STATUS telemetry, the host protocol (one frame, one `cp.l`, one ack) and every host test
bound to it. The write path is untouched — it already used the documented order.

## Build

| | |
|---|---|
| source commit | `e4ffb00`, tree **clean**, 13 sources pinned |
| part | `xc7z010clg400-1` |
| **WNS** | **+6.641 ns** (TNS 0, 0 failing of 2189 endpoints; WHS +0.105, WPWS +8.750) |
| utilisation | 989 Slice LUTs (879 as logic, 110 as memory), 624 FFs, 63 control sets |
| pblock occupancy | 305 of 400 slices; `PRIMITIVE_COUNT` 1837, all 1969 cells carry `PBLOCK` |
| **cell isolation** | **target cells 6 (exactly 6), flush cells 0** |
| route inventory | flush 539 / target 682 / foreign 676 |

Against erratum 005 (994 LUTs, 624 FFs, 63 control sets, 303 slices, WNS +5.864) the change
is **−5 LUTs, 0 FFs, +2 slices and +0.777 ns**. Reordering the setup words is not a resource
trade; it relaxed timing.

Route counts are an **evidence record**, not a verdict — erratum 001 moved the authority to
bit invariance and cell ownership. Against erratum 005's 509 / 676 / 670 the inventories grew
by 30 / 6 / 6; the net inventory digests are `b2640610…` (flush) and `2d77f76c…` (target).

The `routed nodes` and `routed pips` digests in `isolation.txt` are identical to erratum
005's, and that is **not** a statement that the routing is the same.
`vivado/carrier/isolation_checks.tcl` hashes the entire node/PIP *namespace* of the touched
tiles, not the resources the design actually uses — so an unchanged digest says only that
the same region of the device was touched.

## Artifacts

| file | sha256 |
|---|---|
| `carrier.bit` | `8c3369e8e4755da5aceeb7844690d5e132b2e65647004c0a46c0e868e34f0b8a` |
| `carrier_eco.bit` | `78eff0cbc6c4d8034f18a5a7f928bcc33e3f57e07e67f117debf27728543d9ae` |
| `post_route.dcp` | `8d9cfffcfcd0a1dba3f4e42f51be407688f80d6ca676c5d7b21f73d0ca5aa624` |
| `local_map.json` | `56f2b9e81e180eee2540286e4fde797e0d4820a49d10624c10844c38e99d87cb` |
| `phenotype_manifest.json` | `e45f466d082ccd6f227e6f9be4ce75a4e98c4caa708808c09a77ed32331c10ef` |
| `carrier_build.json` | `0cee21b874ad5b05251f0d9aaf385533d343199e42dc3ed4e515b4c070a709b1` |
| `carrier_eco.json` | `cacbb5b9462a24e2a52be9cefd71bbd3c59fb38afbfc8bc50abfc1f6eb7f9d07` |
| `isolation.txt` | `2dc47cd2e648bda4490caae60ddb3bbb942b84653db2feb8d0845db1c7931345` |

`PRODUCTION_MANIFEST_SHA256` in `scripts/board_carrier_exec.py` is repointed to `e45f466d…`.
`local_map.json` is byte-identical to erratum 003's, 004's and 005's: the map is a property
of the device, not of the carrier. The ECO is the same cell, LOC and BEL as erratum 005
(`evolvable_0`, `SLICE_X2Y25`, `SLICEL.A6LUT`, `reimplemented: false`).

## How the defect was found

On the board, then in the dump, then in the model — in that order, and the third step is the
one that matters.

The erratum-005 no-op stopped with `F_READBACK` and a STATUS word **bit-identical** to
erratum 004's, which on its own said only "the same shape of failure". The authorised
read-only dump of the staging window said much more: the `0xFFFFFFDA` constant pattern was
**gone**, and the 101 words were a **bit-exact** window of the device's configuration
stream — matched at exactly one word offset out of 520,352, at `0x00400A81` word 99. That
is +604 words from the requested frame. Pass 2 writes `A20, A21, A22, A23, A80`, which
leaves FAR at `A81`.

Evidence: `evidence/calibration_noop_2026_08_13_erratum005/`, analysed offline by
`scripts/analyse_stage_offset.py`, which attributes nothing.

**The model is what turned a correlation into a defect.** Once `icape2_model.v` executed
CMD commands at FAR load, the *unchanged* RTL failed `tb_carrier_readback` 1527 times with
device error 2, `E_NO_RCFG` —
`evidence/erratum006_model_first_2026_08_13/rtl_unchanged_readback.txt`. That failure was
produced **before** a line of RTL changed, which is the only order in which a fix like this
proves anything.

Mutation `far_before_rcfg` reorders the seven words back and changes nothing else: killed,
device error 2. Before this erratum it was undetectable. **12 as expected, 0 unexpected.**
Benches: **all 14 runs OK**, including the eight-configuration readback sweep.

## What this run does NOT establish

That the board will now read the frame it asks for. The command-order defect was real and
is fixed, and the dump is consistent with it — but one misaligned window at one offset does
not by itself exclude a further latency or addressing error underneath. The board has not
been touched since the read-only dump. That is a question for the next calibration.

# Claim B round 1 — carrier build, 2026-08-13 (erratum 005)

Acceptance ladder step 4 (`docs/claimb_carrier_design.md` §7), built under errata
[001](../../docs/claimb_erratum_001_static_routes.md),
[002](../../docs/claimb_erratum_002_ps7_axi3.md),
[003](../../docs/claimb_erratum_003_config_idcode_and_refusal.md),
[004](../../docs/claimb_erratum_004_icap_readback.md) and
[005](../../docs/claimb_erratum_005_fdro_contiguity.md), to the sequence derived in
[the ICAPE2 readback derivation](../../docs/claimb_icape2_readback_sequence.md).

**This directory is the authority for the carrier, and it SUPERSEDES
`gate_runs/claimb_round1_carrier_2026_08_13_erratum004`.** That build got further than any
before it — its probe established a real ICAP read on silicon, which is what made this
diagnosable — but its readback used `CSIB` as back-pressure for a byte-serial CRC, and what
came back was not frame data: the staging window held 101 identical words, `0xFFFFFFDA`,
which is `br8` of `0xFFFFFF5B` — a value **consistent with** an abort status word. It reads
nothing back either. No device write may use it.

> **Correction, 2026-08-13** (`docs/claimb_erratum_005_correction_2026_08_13.md`): the gapped
> read is **highly correlated** with that failure and is **not uniquely proven** to have
> caused it. UG470 documents non-contiguous configuration by de-asserting `CSI_B` *or* by
> stopping `CCLK`, and AMD's defined abort condition is `RDWRB` changing while `CSIB` is
> asserted — a plain FDRO gap is not shown to abort. Erratum 005 is a **conservative fix**
> that removes the uncertainty for +1 LUT; it is a hypothesis under test, not a repair whose
> success is known. The per-frame architecture is **accepted at the 2026-08-13 review**.

## What changed, and what did not

**Changed** — the readback's pacing, and nothing else:

* **Five independent, contiguous FDRO transactions per envelope, one per frame.** Each is its
  own `sync..DESYNC` with exactly one FAR set — the shape `scripts/icap_sequence.py` records
  as safe — reading a dummy frame plus its own frame, 202 words.
* **`CSIB` Low and `RDWRB` High on every clock of the burst.** The words land in the existing
  101-word staging RAM at one word per clock, because a RAM write port keeps up with ICAP
  where a byte-serial CRC cannot.
* **The CRC runs afterwards, out of that RAM**, with the ICAP idle and desynced. Nothing
  back-pressures the configuration engine.
* **`frame_far(env, frame)`**: a 15-entry ROM, because a per-frame FDRO addresses the frame it
  is reading rather than the envelope's head.
* **The latency probe is contiguous too**, and runs per frame in the same sync session as the
  burst that uses it. Erratum 004's measurement of 1 word is void — it was taken through a
  gapped read.

**Unchanged:** the target, the seed, the ceiling, the cap, the masks, the fitness, the
train/holdout split, the A/B rules, the floorplan (`pb_logic` still
`SLICE_X0Y0:SLICE_X1Y99` + `SLICE_X6Y0:SLICE_X7Y99`), the map, the AXI register map, the
STATUS telemetry, the host protocol (one frame, one `cp.l`, one ack) and every host test
bound to it. The write path is untouched.

## Build

| | |
|---|---|
| source commit | `9da33c8`, tree **clean**, 13 sources pinned |
| part | `xc7z010clg400-1` |
| **WNS** | **+5.864 ns** (TNS 0, 0 failing of 2189 endpoints; WHS +0.036, WPWS +8.750) |
| utilisation | 994 Slice LUTs (884 as logic, 110 as memory), 624 FFs, 63 control sets |
| pblock occupancy | 303 of 400 slices; `PRIMITIVE_COUNT` 1836, all 1968 cells carry `PBLOCK` |
| **cell isolation** | **target cells 6 (exactly 6), flush cells 0** |
| route inventory | flush 509 / target 676 / foreign 670 |

Against erratum 004 (993 LUTs, 625 FFs, 63 control sets, 305 slices, WNS +5.753) the change
is **+1 LUT, −1 FF, −2 slices and +0.111 ns**: the 15-entry FAR ROM costs almost exactly what
the deleted per-word request handshake freed.

Route counts are an **evidence record**, not a verdict — erratum 001 moved the authority to
bit invariance and cell ownership.

## Artifacts

| file | sha256 |
|---|---|
| `carrier.bit` | `d93c59ad3b00ffba2ec46befdec6c7009de842ed523c2486d04101b06078792d` |
| `carrier_eco.bit` | `233fa60286aa7ebf5efe6616feb8d784c9a79b0c50de8026279321a6717ad015` |
| `post_route.dcp` | `77e04fca53a099523fcdccf490c6340fddf9cef8b5caa585c096ba3bb3ac3002` |
| `local_map.json` | `56f2b9e81e180eee2540286e4fde797e0d4820a49d10624c10844c38e99d87cb` |
| `phenotype_manifest.json` | `400a1e9c4cacb51b499fac0ccaadd09a7193f374dd8e574c3ef54d72a3cda69d` |
| `carrier_build.json` | `f7fa27cd78db4fb40b19f0e5c44f6eb1d8f1df88b12541ed90654696de7f207a` |
| `carrier_eco.json` | `2361b0239456dfe2eea3262aca81988d913da2c39ad055c2ab280d645929070e` |
| `isolation.txt` | `c7ca519eab103e4eccbf2c283f54f310d9ac8cf185259307ccbce322fe1eea1b` |

`PRODUCTION_MANIFEST_SHA256` in `scripts/board_carrier_exec.py` is repointed to `400a1e9c…`.
`local_map.json` is byte-identical to erratum 003's and 004's: the map is a property of the
device, not of the carrier.

## How the defect was found

On the board, and then in the dump. The erratum-004 no-op stopped with `F_READBACK` **and
`rb_latency_valid = 1`** — the telemetry erratum 004 added is what said "the probe worked, so
look after it". One authorised read-only dump of the staging window, repeated with the reply
kept whole, showed 101 identical words matching **no** offset of the expected stream (zero
matching words at every one of 506 offsets) and **no** frame of the bitstream. Their value is
the abort status word, un-swapped by an engine that assumes everything on those pins is
configuration data.

`icape2_model` now refuses what it used to permit: a `CSIB` gap during an **active** FDRO read
aborts, and the device drives `0xFFFFFF5B` raw until a fresh sync. That rule is an
**adversarial contract** — the design must not depend on a device tolerating a gap — and not
a reproduction of silicon behaviour. Under it the published erratum-004 RTL scores **1,527
failures**, which demonstrates that the design violated the contract. The bench also counts, off the pins and
without asking the model, any read burst resumed after a pause — required to be zero — and
`scripts/mutate_carrier_readback.sh` carries the erratum-005 defect itself as an eleventh
mutant.

## Status

Host gates and simulation only. **No board time has been taken on this build**, and none is
authorised until this publication chain has been reported and the next no-op ruled. The board
still holds the erratum-004 carrier with `recovery_required` latched, so a reload or a power
cycle is the first act of any session.

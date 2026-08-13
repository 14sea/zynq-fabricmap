# Claim B round 1 — carrier build, 2026-08-13 (erratum 004)

Acceptance ladder step 4 (`docs/claimb_carrier_design.md` §7), built under
[architecture erratum 001](../../docs/claimb_erratum_001_static_routes.md),
[erratum 002](../../docs/claimb_erratum_002_ps7_axi3.md),
[erratum 003](../../docs/claimb_erratum_003_config_idcode_and_refusal.md) and
[erratum 004](../../docs/claimb_erratum_004_icap_readback.md), to the sequence derived in
[the ICAPE2 readback derivation](../../docs/claimb_icape2_readback_sequence.md).

**This directory is the authority for the carrier, and it SUPERSEDES
`gate_runs/claimb_round1_carrier_2026_08_13_erratum003`.** That build's pass 1 worked on
silicon — three envelopes streamed, validated and committed, which is still the first time
this board ever accepted a real envelope — but its pass 2 could not have worked and did not:
it implemented **no ICAP readback protocol at all**, and it handed SelectMAP-order words to a
port that reads them **bit-reversed within each byte**, so the configuration engine never
synced on the write either. It stays in history as the record of that. No device write may
use it.

## What changed, and what did not

**Changed** — carrier feasibility only:

* `carrier_stream`, `P_RDBACK`: a real FDRO readback transaction replaces a bare `RDWRB`
  flip. sync → **Type-1 read of IDCODE** → 32 NOOP flush → turnaround → read until the
  device names itself → turnaround → **FAR, RCFG, FDRO(0), Type-2 606** → 32 NOOP flush →
  turnaround → discard the measured latency and **one whole dummy frame** → five frames →
  DESYNC. The FAR is each envelope's first target FAR; 606 = (5+1) × 101.
* **The read pipeline is MEASURED, not pinned.** The IDCODE read is a known answer, so the
  number no simulation can establish is taken from the device at run time. `tb_carrier_readback`
  sweeps read latencies 0…12 and device flush demands 32…64 and the design may not know either.
* **ICAPE2 wire order.** `br8()` — per-byte bit reversal — at the ICAP pins, in both
  directions. Everything above the pins keeps SelectMAP order, because the committed CRCs,
  the staging window, the host's SHA-256 and the manifest are all in that order.
* **CSIB is gated on the consumer.** `carrier_crc32` takes one word every four cycles; the
  old code held CSIB Low continuously, which against a real device discards three words in
  four. One word is in flight at a time, requested only when it can be taken.
* **A direction change happens only with CSIB High**, which is what UG470 requires and what
  the old entry into readback violated.
* New fault code **`F_RBSYNC = 4'd12`**: the probe never got the device to name itself. It is
  deliberately not `F_READBACK` — "the read path never came up" and "it came up and the
  content disagreed" are different findings, and erratum 004 cost a board round because one
  code covered both.
* **STATUS telemetry**: bits **25:18 `rb_latency_words`**, bit **26 `rb_latency_valid`**;
  bits 31:27 stay reserved and read zero. Cleared before every envelope's probe, set only on
  a real match, cleared by `F_RBSYNC` at its own site, and **kept across `F_READBACK`** —
  which is the case a host most needs it in. It is a separate latch from the one the
  sequencer skips on: telemetry takes no part in acceptance, in a fault, or in
  `configuration_valid`.
* `carrier_axil`: the two telemetry fields in the STATUS multiplexer. Nothing else.
* An end-of-envelope `F_READBACK` refusal was followed by an unconditional `phase <= P_IDLE`
  that overwrote it, leaving `fault_code` set and `fault` clear. Written as one if/else.

**Unchanged:** the target, the seed, the ceiling, the cap, the masks, the fitness, the
train/holdout split, the A/B rules, the floorplan (`pb_logic` still
`SLICE_X0Y0:SLICE_X1Y99` + `SLICE_X6Y0:SLICE_X7Y99`, ruled 2026-08-11), and the map. The
write path's *content* is unchanged: every word the PL sends is still a word the host sent,
now in the order the primitive reads.

## Build

| | |
|---|---|
| source commit | `8ef9fd9`, tree **clean**, 13 sources pinned |
| part | `xc7z010clg400-1` |
| **WNS** | **+5.753 ns** (TNS 0, 0 failing of 2190 endpoints; WHS +0.094, WPWS +8.750) |
| utilisation | 993 Slice LUTs (883 as logic, 110 as memory), 625 FFs, 63 control sets |
| pblock occupancy | 305 of 400 slices; `PRIMITIVE_COUNT` 1849, all 1981 cells carry `PBLOCK` |
| **cell isolation** | **target cells 6 (exactly 6), flush cells 0** |
| route inventory | flush 506 / target 633 / foreign 627 |

Against erratum 003 (816 LUTs, 582 FFs, 57 control sets, WNS +7.371, flush 428 / target 559)
the readback sequencer costs **+177 LUTs, +43 FFs, +6 control sets and 1.618 ns of slack**.
The floorplan is two segments of about 1,600 LUTs, so the margin is comfortable; the earlier
"the region has 800 LUTs" figure was the left segment alone and has been corrected wherever
it was quoted as a live budget.

Route counts are an **evidence record**, not a verdict — erratum 001 moved the authority to
bit invariance and cell ownership. They rise with the design's size and every candidate
rewrites those routes identically.

## Artifacts

| file | sha256 |
|---|---|
| `carrier.bit` | `9f95ebd787c3625e99675d95100cc6cd0615544ec51a2646d94bbabed43937ab` |
| `carrier_eco.bit` | `34348ac40b711b4429e3e894f7dc3673918379ec2b2ae4b6b0a0016a8e930151` |
| `post_route.dcp` | `98808cc638913007e9540fd1ccd7315bc7cc211b36e60d52d62bfb2481ddd959` |
| `local_map.json` | `56f2b9e81e180eee2540286e4fde797e0d4820a49d10624c10844c38e99d87cb` |
| `phenotype_manifest.json` | `38009ca9a54b28464afbd1422c5560a98982140827deb06913a1cb2c67ef4668` |
| `carrier_build.json` | `d881efe90750a1875204fac5f5675296fb222e0d6c4ad5e8fbdcf91f0dd8ca0b` |
| `carrier_eco.json` | `4f92c0d14c59c3650d2a84aa721de4fcbedffe8fc48494e2a8f1f4703dd8d889` |
| `isolation.txt` | `aa5c513b2f96446fc3fc7eb3c49d5b3eccaf2a68ea7e8f9adf996bc2a95ab3d2` |

`PRODUCTION_MANIFEST_SHA256` in `scripts/board_carrier_exec.py` is repointed to
`38009ca9…`, the manifest above.

`local_map.json` is byte-identical to erratum 003's: the map is a property of the device,
not of the carrier, and nothing in this build touches it.

## How the defect was found, and what it says about the tests

Not from the board this time. `vivado/carrier/icape2_model.v` is an ICAPE2 model that never
reads a signal, an array or a parameter of the DUT: it parses the wire, keeps its own
configuration memory, computes FAR successors from the address format — which reproduces
this manifest's two non-consecutive flush FARs unaided — and models the one-frame write
buffer, so five frames in commit four.

Pointed at the published erratum-003 RTL it returned **1,525 failures: 802 words read and
every one of them idle, `E_ABORT` on the direction flip, and zero frames committed to the
fabric.** The write had never synced either.

Nothing caught it earlier because the benches modelled the readback the way the RTL
implemented it: `tb_carrier_stream`'s device handed back the words the DUT had just staged,
indexed by the DUT's own `frame_word`, so it agreed with any read protocol including none,
and it hid a consumer that dropped three words in four. That device is gone from
`tb_carrier_stream` and `tb_carrier_integration`; both now instantiate the model, and a
**provenance test** changes one word of the fabric between the write and the readback —
which a DUT reading its own staging buffer cannot fail.

`scripts/mutate_carrier_readback.sh` breaks the sequence ten ways and requires the bench to
notice each: a missing RCFG, a wrong FAR, a short FDRO length, a discarded-or-not dummy
frame, a one-frame offset, a direction change under CSIB, the word order, a pinned latency,
and a shortened flush both inside and beyond the probe's 64-word cap.

## Status

Host gates and simulation only. **No board time has been taken on this build**, and none is
authorised until the publication chain above has been reported and the next no-op ruled.
The board's `fault_since_reset` and `recovery_required` are still latched from the
erratum-003 calibration, so the first act of any board session is a reload or a power cycle.

# Claim B round 1 — carrier build, 2026-08-13 (erratum 003)

Acceptance ladder step 4 (`docs/claimb_carrier_design.md` §7), built under
[architecture erratum 001](../../docs/claimb_erratum_001_static_routes.md),
[erratum 002](../../docs/claimb_erratum_002_ps7_axi3.md) and
[erratum 003](../../docs/claimb_erratum_003_config_idcode_and_refusal.md).

**This directory is the authority for the carrier, and it SUPERSEDES
`gate_runs/claimb_round1_carrier_2026_08_11_erratum002`.** That build was reachable from the
PS and its shim worked — every STATUS and FAULT read on the board returned correctly — but it
rejected **every real envelope at word 15** and answered the rest of the host's `cp.l` with
SLVERR, which on this board is a data abort, a `panic()` and a CPU reset. Nothing was ever
scored against it. It stays in history as the record of that, and no device write may use it.

## What changed, and what did not

**Changed** — carrier feasibility only:

* `carrier_stream`: `parameter IDCODE = 32'h13722093` becomes
  **`CONFIG_IDCODE = 32'h03722093`**, compared exactly. The old value is the PSS/JTAG
  identity; UG470 makes `IDCODE[31:28]` a revision field, so a bitstream's IDCODE register
  write carries it masked off. The host — bitstream, manifest, candidate gate and sealed
  payload — had always emitted `0x03722093`. Renamed so the two identities cannot be
  confused again. No masking, and the JTAG value is **not** also accepted.
* `carrier_axil`: a stream write arriving with **no pass open** now completes on the bus with
  **OKAY** and pulses a new `stream_refused` output. It delivers no word to the engine and
  advances no position, CRC, commit or ICAP.
* `carrier_stream`: new input `protocol_fault`, new fault code **`F_PROTOCOL = 4'd11`**,
  latched **only when no fault is latched yet**, so the first verdict survives a full drain.
* **Shim-level errors keep SLVERR** — unsupported AXI3 transactions and malformed bursts are
  master-side protocol violations, not guard refusals, and leave no verdict to read.

**The contract this creates for the host:** *AXI OKAY on a stream write means the bus
transfer completed. It does not mean the candidate was accepted.* FAULT must be read after
`cp.l` returns.

**Unchanged:** the target, the seed, the ceiling, the cap, the masks, the fitness, the
train/holdout split, the A/B rules, the floorplan (`pb_logic` still
`SLICE_X0Y0:SLICE_X1Y99` + `SLICE_X6Y0:SLICE_X7Y99`, ruled 2026-08-11), and the map.

## Build

| | |
|---|---|
| source commit | `a0cffbf`, tree **clean**, 13 sources pinned |
| part | `xc7z010clg400-1` |
| **WNS** | **+7.371 ns** (TNS 0, 0 failing of 2108 endpoints; WHS +0.044) |
| utilisation | 816 Slice LUTs (706 as logic), 582 FFs, 57 control sets |
| **cell isolation** | **target cells 6 (exactly 6), flush cells 0** |
| route inventory | flush 428 / target 559 |

Route counts are an **evidence record**, not a verdict — erratum 001 moved the authority to
bit invariance and cell ownership.

## Artifacts

| file | sha256 |
|---|---|
| `carrier.bit` | `15e4a8cf999c58b353808bc17e575358efcfaec46394c7fcdb08e1b8c2604679` |
| `carrier_eco.bit` | `5ff80911dc705eba40d9a865e34d6dfc2d4f9a9d3f543cadc2ef7e5911dd0757` |
| `post_route.dcp` | `1f010dbbf324d1ee2f86ffc6d331dc941804f9d73676a03df94278e6431bddea` |
| `local_map.json` | `56f2b9e81e180eee2540286e4fde797e0d4820a49d10624c10844c38e99d87cb` |
| `phenotype_manifest.json` | `44312a51355c630c8afb1db18e34aead09220f657d13f55390e72bbb85f7ac23` |
| `carrier_build.json` | `294f4e6df4932796ddcae23fc911ac398ec7983abd47b5aa353e3f478f3e6a0a` |
| `carrier_eco.json` | `aa4505b31ba98842d673072202fe55d66af19111f59762cc9bf786fd49842b61` |
| `isolation.txt` | `c7d4333bc69754d06913ed5eac2b5b4ea82f440cce345e3813683808e06784b0` |

`PRODUCTION_MANIFEST_SHA256` in `scripts/board_carrier_exec.py` is repointed to
`44312a51…`, the manifest above.

## How the defect was found, and what it says about the tests

The chain bench `vivado/carrier/tb_carrier_chain.v` replays `begin_txn` → STATUS →
`start_pass1` → the **real 536-word envelope** through the real
`carrier_axi3_lite → carrier_axil → carrier_stream` chain, with an AXI3 master written from
the spec rather than from the shim. On the published erratum-002 RTL it reproduced the board
exactly, in all four AXI shapes: 16 beats accepted, then every beat SLVERR, `phase=P_IDLE`,
`fault=1`, `code=2 (F_CONTROL)`, `pos=15`.

Nothing caught it earlier because each side was tested against a copy of its own assumption:
`tb_carrier_stream.v` typed `env_words[15] = 32'h13722093`, and the host gate judges frame
*content*, not the control skeleton. The benches now take their skeleton from
`vivado/carrier/tb_envelope0.hex` — the host's real bytes — and
`tests/test_config_idcode_agreement.py` compares the parsed bitstream, the manifest, every
envelope the host builds, and the RTL parameter against **each other**.

## Status

Host gates and simulation only. **No board time has been taken on this build**, and none is
authorised until the publication chain above has been reported and the next no-op ruled.

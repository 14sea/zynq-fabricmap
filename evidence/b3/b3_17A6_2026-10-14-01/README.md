# B3 session 0, attempt 1 — lifecycle 2 — 17A6 — 2026-10-14-01 (pair 0) — **LOST at carrier configuration; no session**

Outcome **`REFUSED: configuration did not happen: INT_STS=0xa802000b, PCFG_DONE clear`**, cause class **LOST**
(`runner_session.json`, `summary.json`; the ruling pair `rulings/b3_2026-10-14-01.json` + `rulings/p3_k_b3_2026-10-14-01.json`
is spent — both `.consumed` markers carry this outcome). The runner was started at 2026-10-14T20:00:47Z under the
owner's authorisation of one SEARCH attempt for session 0 (pair_first 0, pair_count 1), bound to the S3 manifest
`258bb14c…` (`manifest_at_run.json`), boundary `evidence/b3/principal_boundary_2026-10-14-03.json` (sha256 `13ebc1527d2b8aac…`,
R1–R5 passed at 19:54:31Z). The full production preflight passed (claim at 20:03:19Z); the session was refused by the
instrument's board driver at the carrier load, before any image load, identity page, record or heartbeat.

## What happened, from the bytes

- Precheck (`summary.json` `precheck`): devcfg CTRL `0x4e00e07f`, INT_STS `0xa802000b`, STATUS `0x40000a30`,
  FPGA0_CLK_CTRL `0x00400800` (FCLK0 50 MHz from the 1600 MHz IO PLL), `plmark` undefined — all as expected on a fresh
  power-up and identical to B3Q -02's precheck earlier the same day.
- The carrier bitstream (`builds/b1/b1.bit`, 2 083 858 bytes, sha `d85daef4…`) was sent by ymodem to 0x04000000 and
  the transfer completed (`ymodem.log`: `Bytes Sent:2083968`, `Transfer complete`; byte-identical to B3Q -02's log
  except the BPS figure); U-Boot reported `## Total Size = 0x001fcc12 = 2083858 Bytes`.
- `mw.l 0xf800700c 0x00000004 1` cleared the sticky PCFG_DONE edge (INT_STS still `0xa802000b`).
- **`fpga loadb 0 0x04000000 0x001fcc12`** printed the bitstream header (`b1_top`, `7z010clg400`, 2 083 740 bytes) and
  then **`zynq_dma_xfer_init: Timeout wait for INIT to clear` / `Command 'loadb' failed: Error 1`**; INT_STS read back
  unchanged, `0xa802000b`, PCFG_DONE clear → the driver's named refusal (`zynq_psoracle/scripts/board_session.py:490`).
  In B3Q -02 the same command left INT_STS `0x50021004` with PCFG_DONE set.
- Transport: 0 CRC drops, 0 bad frames, no disruptions; no rel-v4 frame was ever exchanged. **This is not a transport
  event** and not the inbound-deletion cause B3Q -01 counted; it is a PL configuration-interface failure (the DevC's
  PROG_B → INIT_B handshake did not complete) at the instrument's load step on a cold board.

## What is archived here (7 files, as the runner left them; no exports, no seal, no adjudication)

| file | sha256 |
|---|---|
| `B1_0_preflight.json` | `b75e8c9e2c9833febae2682adc468382fe9a7e3d5ef7ff219a8bfffc1c6fb82f` |
| `manifest_at_run.json` | `258bb14c4b3ba1a3d33741f23b1663f563de64da800843d30c8a615e2f128628` |
| `offline_binding_check.json` | `2d46dc0ffa2d98d646c58d8e37deb7463ac313a7f5b4d96900fd600a74995465` |
| `ruling_provisioning.json` | `4ba9c35d3b5ae62290b1000615041e5bc22888829af4bc13551a8dfd9a168532` |
| `ruling_whole_of_run.json` | `41ef457597617e8c141ca57f894fa1db7a069d20573eab92eb20a5da13e432f4` |
| `runner_session.json` | `7b4cf4ca900cdb02d43825c88c19db5c273e1b044811a0c2d9242ceb2693fbf6` |
| `summary.json` | `34ab3dedb8013450011870c4254977d159d1a096a8d0e092f13734162e2f69f0` |
| `ymodem.log` | `811d8fe94e70524c4961252fa2f56d4e17192d65128c5b4f2cf42fed94afc3cb` |

`manifest_at_run.json` hashes to the ruling pair's binding; both ruling envelopes decode and rebind (`offline_binding_check.json`:
`archived_manifest_findings` and `archived_ruling_findings` empty against the SEARCH session plan rebuilt from the authoritative
inputs by `evidence/b3/main_preparation_2026_10_14/restore_rejudge.search_session_plan`; the 88-file pinned surface verified).
Form (c) archiving and the fresh-restore re-judge do not apply: there is no run log, no exports and no verdict to re-derive
(`archive_session.py` refuses a directory that is not the runner's sixteen files, by design). The original directory is kept
unchanged at `build/wip/scratch_2026_10_14/s0_raw/b3_17A6_2026-10-14-01/` (ignored); the seven files here are byte-identical copies.

## Standing

- The ruling pair is spent; nothing here authorises a second attempt. Under the owner's rulings of 2026-10-14: a LOST verdict
  stands as archived; a re-run of pair 0 (same seeds, new ruling pair) is possible only for a CONFIRMED transport or instrument
  loss, separately authorised. This attempt counts as one claimed attempt without COMPLETED (three trigger the design review);
  as a cause it is new — not the same cause as B3Q -01.
- No diagnosis was performed on the board after the refusal: the port was not reopened. The instrument carries a carrier-load
  isolation script (`zynq_psoracle/scripts/board_isolate_carrier.py`); running it is board use and needs its own authorisation.
- The board was power-cycled and both USB devices re-attached before this attempt (CH340 on ttyUSB4, FT4232H at 001/068).

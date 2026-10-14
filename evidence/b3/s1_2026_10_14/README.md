# B3 lifecycle 2 — S1 freeze — 2026-10-14

The owner authorised the S1 freeze in conversation on 2026-10-14, naming the preregistration
digest, and ruled on the three preconditions below. The production CLI executed the freeze
once, at 2026-10-14T06:34:59Z, on the committed S0 manifest (`00b330c5…`, commit `b3db72a`,
pre-freeze proof `evidence/b3/tests/test_report_2026-10-13T140003Z.json`, commit `02ebd87`)
and on the preregistration bytes as committed.

- Frozen (S1) manifest SHA-256: `bb917ec7bde1a47da975162ff76bb27d4c6080e06a715d49f7f458e8115a23c6`
- Preregistration SHA-256 (v0.3.1, frozen as is): `e89c5677ac7f2be28e178b64d48b7a6f8bfdd35158d5ca5639ac8323c1451353`
- Pin table SHA-256: `73cec93a72aa962f10b331c3720f50439201a73bee2ba34971dd2b8b677ac280` (88 files)
- Image SHA-256: `28c80eca419efe88ac6e1969c9fc5d87d416d8a6137e4612288298b9e5da8299` (131 092 bytes, ELF `0d0f99a6…`, build evidence `288077c0…`)
- B3Q documents: plan `490347f4…`, prediction `7eae2650…` (master 3776596183, 125 records), pinned at S0, unchanged

Production `verify` passes before (S0) and after (S1) in fresh processes — the seven frozen
inputs, the B2 S3 verify (`aec84514…`), the B1 lineage re-verified, the 88 B3 pins by bytes and
content, the image bytes, B3Q's documents re-derived, the prediction rebuilt in full
(`verify_before.json`, `verify_after.json`). The transition changed exactly `history`,
`image.board_ready`, `prereg.frozen`, `prereg.sha256` and `status` (`transition.json`, computed
from the manifest bytes before and after); the pin table, the image record and the B3Q block
are unchanged; `qualified` stays false; `qualification`, `calibration` and `plan` stay null.

## The owner's three rulings that precede this freeze (2026-10-14)

### 1. Preregistration §7 — the compatibility review: PASSED by the owner

§7 says the owner's compatibility review (the L6 / B1 / B2 list) precedes `board_ready`, and
that the B2 guards are re-established for the B3 image. The owner checked the B3 and B2
implementations side by side — the MMIO allowlist, the settle poll, the DMA submission and
wait, the readback, the watchdog kick and the closing control keep B2's logic; the rectx / pull
units are byte-identical — and independently ran the MMIO, leakage / IMPORT and wire-parity
checks (19 in all, every one passing), accepting the stage 1–6 units and the pre-freeze proof as
the standing evidence. The item-by-item index below is the basis of that ruling, recorded here
as the owner asked; no separate index review is opened.

| §7 item | where it is held (host-only evidence at `b3db72a` / `02ebd87`) |
|---|---|
| the wire contract | `b3_wire.c` derived from `b2_wire.c` (IMPORT.json `derived`); `b3/tests/test_b3_wire_contract.py` (stage 3, `e791758`): the whole pair-0 session through `b3_records.validate_run_log` with the instrument's common contract, identity 1.6.0 with the three B3 fields, every embedded block byte for byte, B2 parity of every public builder but IDENT and the record version; `test_b3_app_audit.TheBounds` / `TheHostReadsTheLongestLine` (stage 5, `171b638`): the longest line through the instrument's own reader, parser and collector |
| the settle poll | `settle_condition` in `b3_app.c` byte-identical to `b2_app.c`'s (`P3_SETTLE_POLLS_MAX` 1 000 000 unchanged); exercised off-board by every candidate of `test_b3_hostapp.TheWholePair` (stage 6, `e0c0bec` / `64bca1e`) |
| the audit service | `p3_pull.c` / `p3_pull.h` / `p3_rectx.c` / `p3_rectx.h` verbatim copies of `firmware/b2/` (IMPORT.json `verbatim`, digests held by `test_b3_leakage.Imports` and `test_b3_record_twin.TheCopiesAndTheBuild`); the audit-ready / sparse / audit builders byte-identical to B2's in the wire parity (`B2Parity.test_every_public_builder_unaffected_by_b3_is_byte_identical`); the link-3 stop audited whether asked or not (`test_b3_hostapp.test_d_p_done_before_the_data_lands_is_a_link3_stop_not_a_score`) |
| the MMIO allowlist against the B1 RTL (unchanged RTL) | `axi_readable` / `axi_writable` in `b3_app.c` byte-identical to `b2_app.c`'s; `test_b3_app_audit.TheAxiAllowlist` (stage 5): the application's read decode equals `rtl/b1/b1_axil.v`'s read decode exactly, its write decode lies inside the RTL's and leaves out only the MAC key window, CTRL (`0x2000`) is never read, the key window is never named; `rtl/b1/b1_axil.v` is the B1-pinned carrier RTL and the carrier `builds/b1/b1.bit` (`d85daef4…`) is the one the B1 and B2 manifests name |
| the DMA order | `devcfg_dma`, `devcfg_wait_done`, `write_envelopes`, `readback_frame` in `b3_app.c` byte-identical to `b2_app.c`'s; the order WRITE_ENVELOPE → READ_COMMAND → READ_FRAME → READ_CLEANUP per candidate held by `test_b3_hostapp.TheWholePair.test_the_session_completes` (`dma_candidate` env 3 / cmd 12 / frame 12 / clean 12 per candidate) and by `test_b3_image_stack.TheFinalImage.test_the_dma_commands_of_the_final_image` on the built ELF (the four direct call sites, each with a constant descriptor); the F-WIN fault injection of stage 6 (timeout, each error bit, late completion, sticky device) is a simulation and is recorded as such, never as evidence that the hardware stopped a DMA |
| no ICAPE2 | no ICAP primitive or driver symbol under `b3/firmware/` (the only match of "icap" is `icap_ecc` in the verbatim `p3_derive.c`, prjxray's frame-ECC arithmetic, as in B2); the PL is reached only through the DevC PCAP DMA registers (`DEVCFG_*`) and the carrier's AXI window (`P3_AXI_BASE` `0x43C00000`); `test_b3_leakage.TheBinary` scans the committed binary and ELF for the forbidden tokens and the required declarations |
| no SLCR write | `b3_app.c:181` — `SLCR_PSS_IDCODE` is "READ ONLY — this application writes no SLCR word"; the only `Xil_Out32` targets in `b3_app.c` are the DevC DMA / INT_STS registers, the carrier AXI window and the three DDR buffers (`P3_CMD_BUF`, `P3_WR_BUF`, `P3_DST_BUF`); `test_b3_image_stack` lists every placed MMIO store of the final ELF and names the one DMA command |
| the watchdog gating | `XScuWdt` used in `b3_app.c` exactly as in `b2_app.c` (seven uses each; `XScuWdt_RestartWdt` after a framed line, §6a, only once initialised); the stub `b3/tb/hostapp/hostbsp/xscuwdt.h` of stage 6 keeps the call sites live off-board |
| B2 guard: verbatim imports | `b3/firmware/IMPORT.json` is the final import inventory (14 verbatim, 6 derived, 13 new, 2 built); `test_b3_leakage.Imports` holds the table to the tree and every entry to its digests; `test_b3_record_twin` holds the five engine / hash copies |
| B2 guard: header without tables | `b3_seed_data.h` is a fresh render of `gen_b3_seed_data.py` carrying nothing of the prediction (`test_b3_orch_twin.TheBuildAndTheSeedHeader`); `p3_data.h` verbatim |
| B2 guard: source include scan | `test_b3_leakage.Sources.test_every_source_has_an_include_allowlist_and_keeps_to_it` (every source under `b3/firmware`), no forbidden token in any source through B2's comment stripper |
| B2 guard: binary scan extended to the cartographer's tables | `test_b3_leakage.TheBinary`: no forbidden token in `b3_app.bin` / `.elf`, the engine version, the cartographer version `specimen-carto-v1.1` and the map digest declared; the scanner held load-bearing on synthetic bytes |
| B2 guard: the certificate and the oracle rendering | `certificate` and the LUT-site names are in the forbidden list (`gen_b2_data.FORBIDDEN`) scanned above; B2's oracle rendering is unchanged input (the self-map `c6a4b23e…` pinned by the plan and the manifest's `map` block) |
| B2 guard: C = Python twin, for the engine AND the cartographer | `test_b3_carto_twin` (stage 1: the C cartographer against `b3_carto.py`, the 8 000 committed ledger entries replayed), `test_b3_record_twin` (stage 2: the O arm's record / ledger / commitment, every committed pair; the image's compile branch executed, B-2), `test_b3_orch_twin` (stage 4: all 24 026 candidates against `b3_session.run_context`, the B3Q session, the seed rule) |
| B2 guard: the real application off-board | `b3/tb/hostapp/` (stage 6): the real `b3_app.c` with `-DB3_EMIT_SHA` against stub BSP, fake PL / DevC and a scripted host — the whole pair-2 session COMPLETED and validated, refusals at seven points, the startup identity, F-WIN fault injection |
| B2 guard: fail-closed adjudication | `b3/host/b3_adjudicate.py` and `test_b3_adjudicate` (62 tests); `b3_records.validate_run_log` with the instrument's common contract on every host-side session above |
| B2 guard: pins | `manifests/b3_instrument_pins.json` (88 files, `73cec93a…`), verified by bytes and content in every `verify`; the pre-freeze proof bound to it (`manifest_bound`, `pins_verified true`) |

### 2. `board_ready = true` with `image_ready = false` — the owner's decision

The freeze marks the image `board_ready`. The owner makes this mark knowing that the formal
stack assessment of the committed image stands at `FINDINGS` and `readiness.image_ready` is
`false` (`evidence/b3/build_evidence.json`; the stage-5 engineering acceptance,
`docs/b3_stage5_engineering_acceptance_2026_10_12.md`, 2026-10-12): the analysis cannot place
every write of the image, no I/O table is proved read-only, no stack bound is published for
any entry, and F-WIN (a DMA that times out is not shown to be stopped), F-DEC, F-SUB and F-PL
stand as findings. The decision rests on the accepted engineering evidence of stages 1–6 and
the pre-freeze proof, not on a completed proof. Nothing about the board is confirmed by it:
the on-board premises are unverified until B3Q, and a board session still needs the B3Q ruling
pair with its transport disposition (preregistration §6a, §8).

### 3. The preregistration is frozen as committed (v0.3.1, `e89c5677…`)

Its "Progress (v0.3.1, 2026-09-17)" paragraph carries its own historical date and is not
updated; the progress since then is recorded in `README.md` and in the evidence directories.

## Not done by this transition

The post-freeze clean-tree proof (preregistration §8: it must bind the S1 manifest
`bb917ec7…`) — **pending at this commit; it is the next commit's**. The B3Q ruling pair, any
board or port access, any push. Each is its own authorised unit.

B1 compatibility review — package §7, 2026-09-05

**Result: HOLD.** Static review and off-board verification of image `54b00663…` found one blocker: the `SIGNREF` branch retains P3's behavior of continuing after refusal, violating B1's contract that any non-SCORED candidate ends the epoch. Results for the other §7 items follow. This review does not perform a freeze, grant a board ruling or mark the carrier qualified.

Review baseline: fabricmap `a548bfb2afe145c37a66df0d4f1cec3fc4629819`; instrument `689dde1dad374536c625bbe2b05986ee89eb4c94`. Both worktrees were clean at the start, and fabricmap matched local origin/main. Existing firmware, image, RTL, manifest and evidence were unchanged by this review; only this report and the off-board review artifacts were added.

| Binding | SHA256 |
|---|---|
| manifest | `b85746114fa3dab1b09f8046cb034545a6de0b0fab928200c6c4a66e4612a895` |
| image, 114708 bytes | `54b006636fe07d1b52784e636452cfbd1191407a100699a7666c57b96ba4d6c8` |
| ELF | `9d23ddf9190d4cde0e11a02a2adf469acd6d65d8b4963e26afee50c0371233f7` |
| carrier | `d85daef4e3aa1ff925c327e1c1f98465a83d96e79955aca432d664d98aa4f38f` |

Rechecked these bytes, 93 fabricmap pins, 128 instrument pins, and every source/verbatim copy in IMPORT.json. Function-level comparison shows 49 shared functions in b1_app.c are textually unchanged. Only axi_readable, establish_identity, run_candidate and main differ among shared functions; carto_block is added and schedule_mode removed. Complete diffs and lists are in the [review evidence](../evidence/b1/compatibility_review_2026_09_05/).

| Package §7 item | Decision | Verification and evidence |
|---|---|---|
| Wire contract | Item passed | rel-v4 framing, CRC, base64 and the REC/IDENT/SIGNREQ/TERM transaction units are unchanged. b1_wire.c/h adds carrier_variant, carto_version, probe_budget and universe_sha256 to IDENT 1.4.0, and carto to REC 1.2.0; B1 emits no arm. The actual C serializer's identity/record payloads are accepted by the instrument validator. Serializer tally code is unchanged. All 3 test_b1_wire tests pass. |
| Settle poll | Item passed | settle_condition and arm_attempt are textually unchanged. 20 payload writes + 4 tag writes + 1 CTRL strobe; at most 1000000 STATUS reads; the poll does not repeat ARM. It finishes only when neither gate nor scorer is busy and fault or scorer_done is latched. status_first, status_last, fault and nonce evidence is retained for success and failure. B1 does not require tables_match=1 to recognize cfg_valid. |
| Audit service | Item passed | p3_pull.c/h and p3_rectx.c/h imports are byte-identical; audit_pull, all pull callbacks, audit_word and emit_record are textually unchanged. 1602 staging words + 1212 readback words = 2814, a 384-word window, 8 chunks. AUDITDONE completion and actual service are required to mark audited. The normal SCORED path still completes the requested audit before ARM; pull failure takes STOP_AUDIT without ARM. B1 end-to-end model tests verify auditing of all 335 records. |
| MMIO allowlists against B1 RTL | Item passed | The app read set equals the RTL decode; added read-only VARIANT at 0x2034, value 0x42310001. CTRL at 0x2000 remains unreadable. Writes are limited to CTRL, the 20-word payload and the 4-word tag. The RTL's only write offsets beyond the app's set are the 0x2160–0x216C key window, which the app cannot write. Write-once key behavior and key-read SLVERR are unchanged. Both MmioAllowlist tests and the RTL bench pass. |
| DMA order | Item passed | devcfg_dma, devcfg_wait_done, stage_streams, write_envelopes, readback_frame, link2_witness and link3_witness are textually unchanged. PCAP mode is checked and interrupt status cleared/checked before writing the four registers in SRC_ADDR→DEST_ADDR→SRC_LEN→DEST_LEN order. Completion requires D_P_DONE, not DMA_DONE. Readback follows command→frame DMA→cleanup; prefill sentinel verification is unchanged. Link-2 comparison precedes DMA; link-3 comparison and audit precede ARM. |
| Cache / data-region boundaries | Item passed | Before the first staging operation, main uses the same Xil_SetTlbAttributes calls to mark command, destination, staging, identity page and evidence ring as strongly ordered/non-cacheable. No new path depends on per-operation flushes. The image/heap/stack link region is separate from these buffers. |
| No ICAPE2 | Existing artifact verification passed | B1 synthesis sources contain no ICAPE2; post_route_util.rpt and b1_build.json both report 0 cells. B1 still uses PS PCAP. The carrier bitstream hash matches. This review did not rerun Vivado place-and-route or verify through board reads. |
| No SLCR write | Source/diff verification passed | b1_app.c uses SLCR only to read PSS_IDCODE at 0xF8000530; no Xil_Out32 to SLCR was added. Other writes remain the existing DDR, DEVCFG and allowlisted AXI writes. main's XTime_SetTime(0) and watchdog initialization retain the original code and are not new SLCR writes. |
| Watchdog gating | Item passed | Only flags.bit1 enables CfgInitialize→SetControlReg (prescaler 7, WD_MODE)→LoadWdt (1250000035)→Start, followed by setting wdt_started. kick_watchdog calls Restart only after wdt_started; emitting IDENT does not kick an uninitialized instance. With the flag off, the watchdog is not started. These code sections and progress kick points are unchanged. The 30 s interpretation still depends on the specified clock and was not remeasured here. |
| Existing transaction bounds | Value/code comparison passed | Each bounded receive still has both an 8 s tick bound and a poll cap. REC/pull idle cap: 50000000; IDENT/SIGNREQ/TERM: 100000000. At most 3 transmissions per transaction. Existing limits of 64 stale lines, 8 previous ACKs and 3 AUDITWAITs are unchanged. The pure C transaction units and wrappers are identical. |
| B1 memory | Static capacity check passed; no hardware high-water measurement | ELF symbols: O=4664 B, g_carto_json=2048 B, g_map_render=20480 B, g_content=20480 B. Including tables, variant and changed globals, B1 cartography static allocation is approximately 48320 B. The package's “~34 KB state +20 KB render” is an estimate and should be expressed using these actual symbol sizes. The full map is not placed on the stack. |
| C stack / linker bounds | No new B1 capacity blocker found; measurement limitations apply | With the same ARM flags plus -fstack-usage: run_candidate=9968 B, equal to archived P3; main=400 B (P3: 368 B); b1_orch_record_block=640 B; draw_pairs=640 B; b1_carto_render=200 B. Main stack allocation: 16384 B; heap: 1048576 B. The ELF's final stack endpoint is 0x021414F0, within the agreed 4 MiB region starting at 0x02000000. These are function-frame and link-capacity checks, not a hardware stack high-water measurement or a formal bound over the full call graph including libc. |
| Carto / REC payload | Off-board stress scenario passed | Existing tests use only 2 changed entries. This review additionally uses the same C renderer/serializer with 8 changed entries, 292 contradiction entries, 32 pairs, long numeric fields and 32-bit counter extrema: map=12446 B (buffer 20480), carto=576 B (buffer 2048), REC=2306 B (buffer 4096), conservative base64 frame length=3136 B (buffer 7168). Serialization into the actual 4096-byte output buffer succeeds. This is a capacity test, not a valid scientific map or on-board observation. Serializer overflow→0 and the caller's PROTOCOL stop are retained. |
| B1 initialization / successful session order | Item passed | main runs b1_orch_init, including init+bind, before the opening baseline. Probes update the map from readout before emitting its commitment. Normal B1/B1Q C↔Python sessions and the 335-record host model pass. |
| B1 stop on any non-SCORED candidate | **HOLD, blocks compatibility approval** | run_candidate's SIGNREF branch emits REFUSED_BY_GATE and, after RECACK, returns 0 without setting STOPPED. main treats 0 as success and continues, skipping b1_orch_unobserved and break. A code probe can propose the same genome again. Reproduction below. |
| RTL diff | Item passed | b1_arm_gate still computes tables_match after the sweep, but with SEMANTIC_GATE=0 it no longer gates valid_latch/scorer_arm. SipHash, nonce, write-once key, unsigned/replay/wrong-key refusal and sticky recovery are retained. b1_axil adds read-only VARIANT; b1_core/b1_top pass the parameters and change module names; p3_siphash is identical. The Vivado script explicitly sets SEMANTIC_GATE=0. |

Reran the RTL bench: a zero-table signature with nonzero readout can ARM; tables_match=0 still permits cfg_valid; readout follows fabric changes. No-key, wrong-key, wrong-commit, unsigned and replay attempts are refused. Key write-once/read refusal, VARIANT read/write refusal and reset clearing the key all pass. Also checked the existing implementation reports: WNS +7.993 ns, WHS +0.026 ns and passed isolation. These are not new silicon qualification results; B1Q still requires its own ruling pair.

**Reproducible blocking behavior.** The [SIGNREF branch in b1_app.c](../firmware/b1/b1_app.c#L1235) retains P3's “gate refusal is data; session continues” behavior. The [main loop](../firmware/b1/b1_app.c#L1571) stops only on a nonzero return. This conflicts with B1's stop contract in b1_architecture §3, b1_preregistration §2 and b1_orch.h.

The reproduction harness extracts the SIGNREF branch from the actual b1_app.c, replacing only emit_record with a stub that successfully receives ACK. It links the actual b1_orch.c, b1_carto.c and p3_derive.c. After completing the opening baseline, the first code probe receives SIGNREF. Output:

```text
SIGNREF rc=0 running=1 next_candidate=1 same_genome=1 probes_issued=2
```

This is an off-board reproduction of the source branch and orchestrator; it does not execute the entire ARM application or a board. The existing test_b1_session UNSCORED simulation breaks directly inside the twin, so it cannot detect the application's return value. All 47 existing relevant tests can pass while this defect remains. A later adjudicator refusing the session cannot replace the requirement for the board application to stop before the next probe when refusal occurs.

Changes required to close HOLD:

1. After successfully recording SIGNREF, the application must end the epoch and issue no next probe, closing scored baseline or closing ARM. Retain the permitted restore-only cleanup and terminal evidence. Implement an explicit success/non-SCORED result or a consistent stop+return contract, rather than adding a break only in the twin.
2. Add regressions covering the actual application branch: SIGNREF at the opening baseline, a normal probe and the closing baseline, including record-ACK failure. Verify no subsequent candidate/ARM and no COMPLETED epoch outcome.
3. A firmware change requires a new image hash. Rebuild, update build evidence/image pins, rerun wire, session, non-SCORED paths and the complete suite, then repeat the compatibility review for the new image. This review found no required change to the existing carrier RTL.

Verification for this review: 9 test modules, 47 tests, 0 skips, OK; see [tests.log](../evidence/b1/compatibility_review_2026_09_05/tests.log). Modules: test_b1_wire, carrier, build_evidence, leakage, twin, session, e2e, signer and records. The complete 1417-test project suite was not rerun. The existing clean-tree report is an earlier record and does not cover this new counterexample.

Review artifacts include the function-difference list, application/wire/four RTL diffs, SIGNREF harness, payload harness, ARM stack-usage results and binding metadata. Reproduce SIGNREF from the repository root with the following commands, which do not access a board or key store:

```sh
cc -std=c99 -O2 -Ifirmware/b1 evidence/b1/compatibility_review_2026_09_05/signref_repro.c firmware/b1/b1_orch.c firmware/b1/b1_carto.c firmware/b1/p3_derive.c -o /tmp/b1_signref_repro
/tmp/b1_signref_repro
```

At the time of this review, the manifest retained prereg.sha256=null, board_ready=false, qualification=null and qualified=false. No freeze, commit, push, serial access, power cycle, provisioning or image load was performed.

# B4Q — the bring-up execution plan (DRAFT v0.1, documents only, 2026-10-28; deliverable E of the owner's disposition on `c84b8bd5`): the measurements a device must yield before the PS image is trusted, the phases that yield them, the authority each phase needs — none granted here

This plan is executed by nothing in this unit. Every step below names the authority it would need; the runner
(`host/b4q_runner.py`) is validated only against the device surrogate on a PTY (`host/b4q_device_surrogate.py`,
`host/b4q_runner_e2e.py`). The verifier refuses to verify a `uart-board` archive as a host-only one: extending its claims to a
board archive is itself a unit the owner would authorise.

## 0. What is fixed before any phase

| item | value | where pinned |
|---|---|---|
| the image | `build/b4q_image/b4q_app_v2.bin` (protocol `b4q-v2`; the evidence log at `0x10800000`, 16 MiB; the export epilogue after the END) | `evidence/b4/unit_b4q_runner_2026_10_28/build_evidence.json` (sha256 pinned there; the image test holds the layout) |
| the load | the raw `.bin` at `0x02000000` by `loady` (YMODEM-1K, `host/b4q_ymodem.py`), `go 0x02000000`; the identity page at `0x10440000` by `mw.l`, read back by `md.l` | `docs/b4q_image.md` §4, `host/b4q_runner.py` |
| the console | UART1 (`0xE0001000`) as U-Boot leaves it, 115200 8N1, through the CH340 at `/dev/ebaz-uart` (the symlink, never the raw `ttyUSBn`) | `firmware/b4q/target/b4q_board_console.c`, B1's `bsp/src/console.c` |
| the DDR map the image assumes | `CMD_BUF 0x10200000`, `DST_BUF 0x10300000`, `WR_BUF 0x10400000`, `PAGE 0x10440000`, the evidence log `0x10800000`–`0x11800000`: **all above 256 MiB** | `firmware/b4q/target/b4q_psmap.h`, `b4q_board_main.c` |
| the key | the fixture notary's key only, provisioned into the carrier's write-once key by the signer principal (`provisioning P3-K`), never a production key | `docs/b4q_plan.md` §8 |
| the carrier | the pinned bitstream (`instrument.carrier_sha256`), loaded by the control plane of its own ruling (`fpga loadb` under U-Boot: the psoracle / agentctl recipe; never Linux `fpgautil`) | `docs/b4q_plan.md` §7 |

**The target board is an EBAZ4203 (F8B3 or 17A6: 512 MiB DDR, mainline U-Boot with `bootdelay=-1` → the `Zynq> ` prompt), not
the EBAZ4205 of this workspace (256 MiB DDR: the page, the buffers and the log lie outside its memory; the miner U-Boot's autoboot
must be broken with `d`).** The runner handles both prompts (`PROMPT_RE`) and both break styles; the DDR size is the first measurement
and a STOP on the 4205 until the map is re-placed (a design change: a new image identity, a re-pin).

## 1. The phases, each under its own authority

| phase | what runs on the device | what it yields | the authority it needs |
|---|---|---|---|
| **P4 — the control plane** | the prompt, `loady` + `crc32`, the page `mw.l` + `md.l`, `bdinfo`, `md.l` of the SLCR clock registers and of the carrier's variant word; **no `go`** | M1–M3 below; the load witness and the page witness on a device; the transcript (`raw/console.bin`, `uboot.json`) | board contact, power, the carrier already loaded (its own ruling) |
| **P5 — the opening** | `go`; the IDENT; the startup readback (the opening's read group); `QUIT`; the export epilogue (the log of the opening pulled) | M4 (the DMA / PCAP chain on silicon: the startup readback against the loaded-image reference), M6a (the tick rate), the first wall-clock bounds | P4's plus **execution** (`go`) and the fixture key provisioned |
| **P6 — one transaction** | the root (genome 0) and one candidate (a fixture genome with its task); the pull after each; `QUIT` | the links on silicon (the staging witness, the three read groups), the A7 accesses of a transaction, M5 (the watchdog period) in a separate idle run | P5's plus the signer in the loop (the fixture notary) |

P4, P5 and P6 are not one session: P4 ends without `go`; P5 ends at the END of an opened-and-quit session; P6 is the first session
that signs anything. A stop in a phase ends the phase; the next phase is not entered on the same ruling.

## 2. The measurements, with their acceptance and their stop

| # | what | how (the observable) | accept | stop / fallback |
|---|---|---|---|---|
| **M1** | DDR size and the map | `bdinfo` → `DRAM bank` size; the page / buffers / log addresses inside it; `md.l 10440000 18` after `mw.l` returns the written words (the page witness) | 512 MiB and the witness equal | a 256 MiB device: STOP — the map must be re-placed (a new image identity) |
| **M2** | the UART and the load | `loady` of 98 324 bytes at 115200 (expected ≈ 10 s), U-Boot's `## Total Size` = the file's length, `crc32 02000000 18014` = the host's crc32 of the file (the load witness); three loads byte-identical in their crc | witness equal, three times | a mismatch: STOP before `go` (the runner refuses to `go` on an unequal witness) |
| **M3** | FCLK0 and the PL window | `md.l F8000170 1` (SLCR `FPGA0_CLK_CTRL`) and `md.l F8000180 1`; then `md.l 43C00000 1` = the carrier's variant word `0x42340001` (`b4carrier_regmap.VARIANT_WORD`) | the variant word read | a gated FCLK0 freezes the AXI interconnect and the read hangs the A9 (this workspace's lesson: JTAG halt then fails too; a power-cycle recovers) — probe the window through the DAP mem-AP first (`openocd … mem_ap mdw 0x43C00000`) where a pod exists; never from Linux |
| **M4** | the DMA / PCAP chain | P5's startup readback: the IDENT's `open.startup_readback` and the pulled log's first read group (eight target FARs) against `loaded_frames_reference_sha256`; the DEVC poll counts of the log (`count` on INT_STS / STATUS records) | equal; the counts finite | unequal: the opening fails by name (the session-opening record's finding), nothing is signed; the diff of the eight frames is retained from the log (`frame_sha256` per read) — a frame-readback semantics question (dynamic bits, the GLUTMASK) is a design finding, not a retry |
| **M5** | the watchdog period (F8B3's PERIPHCLK is unconfirmed) | an opened session left idle: the END STOPPED (the idle bound), then no kick, then the banner — the host's clock from the END to the banner | 30 s ± 10 % (`B4Q_WDT_LOAD 1 250 000 035`, prescaler 7 at PERIPHCLK / 8 = 41 666 668 Hz) | another period: the pin is wrong for this device — a bring-up finding, the image's constant re-pinned under a ruling |
| **M5b** | the idle bound and the heartbeat in seconds | the host's clock from its last line to the first HB (`B4Q_APP_HB_EVERY` polls) and to the END STOPPED (`B4Q_APP_IDLE_POLLS`); the host's own between-command work (the pull + the derivation + the records ≈ 0.3–0.5 s on the pipe) must sit well inside the idle bound | the idle bound ≥ 10 × the host's longest between-command work | shorter: the poll constants are re-pinned (a new image identity) |
| **M6** | the tick | `t` of the log's marks against the host's clock between a TX and its RESULT (`tick` = the A9 global timer's low word, nominally CPU / 2) | a constant ratio | the tick stays "unmeasured" in every record until this holds |
| **M7** | the export rate | the pull of one transaction's log (≈ 30 KB → 40 KB base64 in 768-byte chunks) at 115200: expected ≈ 4 s; `bad_chunks` = 0 | the digest equal (`RING` vs the pulled bytes), every chunk whole | a dropped byte: the host re-asks (bounded at 8 bad chunks); the CH340 dropout at a board reset reopens the port by its symlink |
| **M8** | the exception path | **not exercised** (a deliberate bad access is not planned) — the END ABORT with DFAR / DFSR exists in the image and has never fired | — | — |

## 3. Stop rules and retention

- Every phase retains, unconditionally and before anything is judged: `raw/console.bin` (every byte received), `raw/console_tx.bin`,
  `uboot.json` (each control-plane step with its witness), the partial evidence log (`raw/evidence_log.bin`) and `raw/pulls.json`, the
  console log — the runner writes them on a stop as on a success.
- A stop is named where it happens (the load witness, the page witness, a banner mid-session, silence beyond the host's bound, an
  END before the IDENT, a NACK where a RESULT was due) and ends the phase. No retry loop; a second attempt is a second ruling.
- The host may use a clock (`silence_s`, M5's stopwatch); the application never does — its bounds are poll counts, and M5b is what
  turns them into seconds.
- A transport cut mid-transaction leaves that transaction with no PS evidence (the log cannot be pulled from a dead transport): the
  record is the interrupted last one with an empty range, named by the verifier's completeness rule, never filled in from a model.
- The terminal END (the sequence exhausted) leaves the log's tail unobtainable (no epilogue after it): a declared limitation.
- The EBAZ4205's S2 reset is unreliable; its only known recovery from a wedged A9 is the Type-C power-cycle. The 4203's reset path is
  a bring-up fact to record. SRST is not wired on the 4205's JTAG header.

## 4. The authorities named, none granted by this unit

| authority | needed by | status |
|---|---|---|
| board contact (the console port) | P4 | not granted |
| power / power-cycle | P4 (and every recovery) | not granted |
| the carrier loaded (`fpga loadb`) | P4's M3, P5, P6 | not granted (its own ruling: the carrier v2 session plan §7) |
| execution (`go`) | P5, P6 | not granted |
| provisioning of the fixture key (`provisioning P3-K`) | P5 (the signer's key must be in the carrier for a candidate to be admitted) | not granted |
| physical PCAP (the readback DMAs on silicon) | P5, P6 | not granted |
| the signer in the loop | P6 | not granted |
| the verifier's board claims (`uart-board` archives verified) | after P6 | not granted — a unit of its own |
| a production key | never | never |

## 5. The runner's invocation per phase (what would be typed, under the ruling)

```
# P4 — control plane only (no go): the prompt, the load + witness, the page + witness, the clock registers
python3 host/b4q_runner_e2e.py --phase P4 --port /dev/ebaz-uart --out evidence/.../P4      # (a --phase switch is not written: P4 is the runner's start() without go — to be added under the ruling)
# P5 — the opening: go, IDENT, QUIT, the epilogue's pull
python3 -c 'import b4q_runner as rn; rn.run("/dev/ebaz-uart", out, lambda s: s.open())'
# P6 — one transaction
python3 -c 'import b4q_runner as rn, b4q_console_e2e as ce; rn.run("/dev/ebaz-uart", out, lambda s: (s.open(), s.transaction("root", 0, ce.stim([])), ce._tx(s, "normal", ce.G_CESR, ce.FIX1)))'
```

The archives these produce carry `transport.kind = "uart-board"`; `host/b4q_verify.py` refuses them by name until its board claims
are extended. The surrogate run of the same bodies (`host/b4q_runner_e2e.py`) is what this unit validates.

## 6. What this plan does not do

It does not touch a board, a port, a power supply, a key or a bitstream. It does not change the hypothesis, the model, the task, the
thresholds, the qualification claim or the session sizes (`docs/b4q_plan.md`). It does not grant itself any of §4. It names the
4205's DDR map as incompatible with the image rather than re-placing the map (a re-placement is a new image identity under a ruling).

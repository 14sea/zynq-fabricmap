# B4Q — the bring-up execution plan (DRAFT v0.2, documents only, 2026-10-28; deliverable E of the owner's disposition on `c84b8bd5`; v0.1 corrected after the owner's HOLD on `dad9e4de`, its R5): the F8B3 bring-up as the accepted prerequisite graph has it, the measurements a device must yield before the PS image is trusted, the executable host-tested stages the runner provides for them, the authorities each needs — none granted here

This plan is executed by nothing in this unit. The runner (`host/b4q_runner.py`) and its archive contract are validated against the
device surrogate on a PTY (`host/b4q_device_surrogate.py`, `host/b4q_runner_e2e.py`) and against synthetic device-format fixtures
(`host/b4q_device_fixture.py`); the verifier holds a device-format archive's internal consistency and says, apart, that nothing in it
is established as observed on a device. The prerequisite graph of `docs/b4q_plan.md` §8 is kept as accepted:

| accepted phase | meaning (unchanged) | this plan's part |
|---|---|---|
| **P4** | `F8B3` 2d provisioning; the supply measured; FCLK0 at 50 MHz; the acceptance regression touched on the board | the preconditions this plan assumes and re-checks at admission (§2 M1–M3); nothing here provisions |
| **P5** | the `F8B3` bring-up (engineering rehearsal) under its own label and ruling pair | **this plan**: the stages S1–S3 below are its internal, ordered steps with stop rules — one whole-of-run ruling covers them; no further owner round is required between S1, S2 and S3 |
| **P6** | the `17A6` qualification session | not this plan; nothing of 17A6 is a measurement of F8B3 |

Target **F8B3 first** (an EBAZ4203 spare awaiting its P4 provisioning: 512 MiB DDR, mainline U-Boot). 17A6's saved `bootdelay`
and its verified FCLK facts are 17A6's: they are not measurements of an unprovisioned F8B3. The EBAZ4205 of this workspace (256 MiB,
the miner U-Boot) is not a target: the image's page, buffers and log lie above 256 MiB — the runner's admission refuses it (§2 M1).

## 0. What is fixed before any stage

| item | value | where pinned |
|---|---|---|
| the image | `build/b4q_image/b4q_app_v2.bin` (protocol `b4q-v2`; the evidence log at `0x10800000`, 16 MiB; the export epilogue after the END) | `evidence/b4/unit_b4q_runner_2026_10_28/build_evidence.json` — **the pin of record**: the runner's `ExecutionContext.pinned()` takes the sha256 from it, never from the selected file (R3) |
| the load | the raw `.bin` at `0x02000000` by `loady` (YMODEM-1K, `host/b4q_ymodem.py`, one cumulative deadline), `go 0x02000000`; the identity page at `0x10440000` by `mw.l`, read back by `md.l` | `docs/b4q_image.md` §4, `host/b4q_runner.py` |
| the console | UART1 (`0xE0001000`) as U-Boot leaves it, 115200 8N1, through the CH340 at `/dev/ebaz-uart` (the symlink, never the raw `ttyUSBn`; a bare `\r` first — the 4203 answers power-on garbage with `Unknown command`) | `firmware/b4q/target/b4q_board_console.c`, B1's `bsp/src/console.c` |
| the DDR map the image assumes | `CMD_BUF 0x10200000`, `DST_BUF 0x10300000`, `WR_BUF 0x10400000`, `PAGE 0x10440000`, the evidence log `0x10800000`–`0x11800000`: all above 256 MiB | `firmware/b4q/target/b4q_psmap.h`, `b4q_board_main.c` |
| the carrier | the pinned bitstream (`instrument.carrier_sha256`), loaded by the control plane of its own ruling (`fpga loadb` under U-Boot: the psoracle / agentctl recipe; never Linux `fpgautil`); its VARIANT word `0x42340001` at **`0x43C02034`** (`AXI_BASE 0x43C00000` + `VARIANT 0x2034`, `host/b4carrier_regmap.py`) | `docs/b4q_plan.md` §7; the runner's admission reads it before any other PL access |
| the key | the fixture notary's key only, provisioned into the carrier's write-once key by the signer principal (`provisioning P3-K`), never a production key | `docs/b4q_plan.md` §8 |
| the execution context | `ExecutionContext(image_sha256=<pin>, board_models=("Ebang EBAZ4203",), dram_min_mib=512, variant_word=0x42340001, fclk0_ctrl_expected=<M3's value once pinned>, role="bringup-rehearsal")` | `host/b4q_runner.py`; the archive's `uboot.json.context` |

## 1. The stages of the F8B3 bring-up (P5), in order, each an executable host-tested entry point

| stage | the runner's entry point | what runs on the device | what it yields | the stop that ends the run |
|---|---|---|---|---|
| **S1 — the control plane** | `python3 host/b4q_runner.py --port /dev/ebaz-uart --out <dir> --stage control-plane` | the prompt; the admission (the pin, the banner's model / DRAM, VARIANT at 0x43C02034, FPGA0_CLK_CTRL); `loady` + `crc32` (the load witness); the page `mw.l` × 24 + `md.l` (the page witness); **no `go`** — the phase ends at `pre-go` | M1–M3; an archive without a session whose streams the verifier recomputes (`agree`, phase `pre-go`) | an admission refusal or a witness mismatch, named and demonstrated by the raw streams |
| **S2 — the opening** | `--stage open` | S1, then `go` (the phase persisted before the command), the IDENT, the startup readback, `QUIT`, the export epilogue (the opening's log pulled) | M4 (the DMA / PCAP chain against the loaded-image reference), M6 (the tick), M7 (the export) | an END before the IDENT, silence, a banner (a reset), a digest mismatch |
| **S3 — one transaction** | `--stage transaction` | S2's opening, the root (genome 0), one candidate (a fixture genome with its task), the pull after each, `QUIT` | the links on silicon (the staging witness, the three read groups), A7 on the logged accesses | the session's own stops (a NACK, a STOP_*, an unsealed O) |
| **S4 — the watchdog** | `--stage open` with `--no-export` (to be added under the ruling: an opening that does NOT pull after the END) left idle | the opened session idle: the END STOPPED (the idle bound), then no line from either side, then the banner | M5 | — |

A stage's archive is verified by `host/b4q_verify.py` in a fresh process; its `provenance` says `uart-board` and `observed_on_device:
false` — the verifier holds internal consistency (the transferred bytes re-assembled from the sent stream are the pinned image, the
device's crc over exactly the loaded range equals theirs, the page read back equals the page written, the admission's words are in
the received stream, the console lines are in the streams in order); what the ruling may then claim about the device is the ruling's.

## 2. The measurements, with their acceptance and their stop

| # | what | how (the observable) | accept | stop / fallback |
|---|---|---|---|---|
| **M1** | DDR size and the map | the banner's `DRAM:` line (or `bdinfo` → `-> size`) ≥ 512 MiB; `md.l 10440000 18` after the 24 `mw.l` returns the written words (the page witness) | 512 MiB and the witness equal | 256 MiB: the admission refuses before any load (a re-placement of the map is a new image identity under a ruling) |
| **M2** | the UART and the load | `loady` of 98 324 bytes at 115200 (expected ≈ 10 s), U-Boot's `## Total Size` = the file's length, `crc32 02000000 18014` over exactly that range = the host's crc32 of the file (the load witness); three loads byte-identical in their crc | witness equal, three times | a mismatch: the runner refuses to `go` (demonstrated in the raw streams) |
| **M3** | the clock and the PL window | `md.l F8000170 1` (SLCR `FPGA0_CLK_CTRL`: SRCSEL bits 5:4, DIVISOR0 bits 13:8, DIVISOR1 bits 25:20) and `md.l F8000108 1` / `F8000100 1` (IO_PLL / ARM_PLL `CTRL`, FDIV bits 18:12) against PS_CLK = 33.333 MHz: FCLK0 = PS_CLK × FDIV / (DIVISOR0 × DIVISOR1) — the derivation recorded, then held to 50 MHz; **then** `md.l 43C02034 1` = `0x42340001` (VARIANT, the admission's first PL access) | 50 MHz derived; the variant word read | a gated FCLK0 freezes the AXI interconnect and a PL read hangs the A9 (this workspace's lesson; a power-cycle recovers): no PL access before the derivation says the clock runs; where a pod exists, probe the window through the DAP mem-AP first (`openocd … mem_ap mdw 0x43C02034`), never from Linux. The VARIANT read alone establishes no frequency |
| **M4** | the DMA / PCAP chain | S2's startup readback: the IDENT's `open.startup_readback` and the pulled log's first read group (eight target FARs) against `loaded_frames_reference_sha256`; the DEVC poll counts of the log | equal; the counts finite | unequal: the opening fails by name, nothing is signed; the eight frames' digests are retained from the log — a readback-semantics question (dynamic bits) is a design finding, not a retry |
| **M5** | the watchdog period (F8B3's PERIPHCLK is unconfirmed) | S4: the host's clock from the LAST line either side put on the console (the END STOPPED, with no export after it — the export epilogue's RING / CHUNK lines go through the kicking emitter, so an opening that pulls after the END measures the epilogue's close, not the END) to the banner; the host's line timestamps retained in `console.jsonl` and `uboot.json` | 30 s ± 10 % after the last kick (`B4Q_WDT_LOAD 1 250 000 035`, prescaler 7 at PERIPHCLK / 8 = 41 666 668 Hz — a hypothesis from 17A6 until measured on F8B3) | another period: the pin is wrong for this device — a bring-up finding, the image's constant re-pinned under a ruling |
| **M5b** | the idle bound and the heartbeat in seconds | the host's clock from its last line to the first HB (`B4Q_APP_HB_EVERY` polls) and to the END STOPPED (`B4Q_APP_IDLE_POLLS`); the host's between-command work (the pull + the derivation + the records ≈ 0.3–0.5 s on the pipe) must sit well inside the idle bound | the idle bound ≥ 10 × the host's longest between-command work | shorter: the poll constants are re-pinned (a new image identity) |
| **M6** | the tick | `t` of the log's marks against the host's clock between a TX and its RESULT (`tick` = the A9 global timer's low word, nominally CPU / 2) | a constant ratio | the tick stays "unmeasured" in every record until this holds |
| **M7** | the export rate | the pull of one transaction's log (≈ 30 KB → 40 KB base64 in 768-byte chunks) at 115200: expected ≈ 4 s; `bad_chunks` = 0 | the digest equal (`RING` vs the pulled bytes), every chunk whole | a dropped byte: the host re-asks (bounded at 8 bad chunks); the CH340 dropout at a board reset reopens the port by its symlink |
| **M8** | the exception path | **not exercised** (a deliberate bad access is not planned) — the END ABORT with DFAR / DFSR exists in the image and has never fired | — | — |

## 3. Stop rules and retention

- Every stage persists, after every control-plane step and before `go`, `uboot.json` (the steps, the admission, the witnesses, the
  phase) and the raw streams (`raw/console.bin`, `raw/console_tx.bin`); a stop, a transport cut or a programming error leaves them on
  disk (the programming error re-raised afterwards, named as such — never reported as a device finding).
- A stop is named where it happens and must be demonstrated by the raw streams (the verifier refuses a named stop the streams do not
  show); no retry loop; a second attempt is a second run under the same whole-of-run ruling's stop rules.
- The host may use a clock (`silence_s`, M5's stopwatch); the application never does — its bounds are poll counts, and M5b is what
  turns them into seconds.
- A transport cut mid-transaction leaves that transaction with no PS evidence (the log cannot be pulled from a dead transport): the
  record is the interrupted last one with an empty range, named by the verifier's completeness rule, never filled in from a model.
- The terminal END (the sequence exhausted) leaves the log's tail unobtainable (no epilogue after it): a declared limitation.
- The EBAZ4203's reset path is a bring-up fact to record; the 4205's S2 is unreliable and its JTAG SRST is not wired (not a target).

## 4. The authorities named, none granted by this unit

| authority | needed by | status |
|---|---|---|
| P4: F8B3 provisioned, the supply measured, FCLK0 at 50 MHz, the acceptance regression touched | S1 | not granted (the 2d rulings) |
| board contact (the console port) and power / power-cycle | S1 (and every recovery) | not granted |
| the carrier loaded (`fpga loadb`) | S1's M3, S2, S3 | not granted (its own ruling: `docs/b4q_plan.md` §7) |
| execution (`go`) | S2, S3, S4 | not granted |
| provisioning of the fixture key (`provisioning P3-K`) | S2 (the signer's key must be in the carrier for a candidate to be admitted) | not granted |
| physical PCAP (the readback DMAs on silicon) | S2, S3 | not granted |
| the signer in the loop | S3 | not granted |
| the claim that a device-format archive was observed on a device | after P5 | not this verifier's: it holds consistency and reports provenance apart |
| a production key | never | never |

## 5. What this plan does not do

It does not touch a board, a port, a power supply, a key or a bitstream. It does not change the hypothesis, the model, the task, the
thresholds, the qualification claim or the session sizes (`docs/b4q_plan.md`). It does not grant itself any of §4 and adds no gate the
owner did not issue. It names the 4205's DDR map as incompatible with the image rather than re-placing the map. S4's `--no-export`
option and the three-load repetition of M2 are named engineering of the runner, not yet written.

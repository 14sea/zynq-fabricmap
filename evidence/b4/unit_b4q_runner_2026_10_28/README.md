# B4 — the B4Q physical-runner and evidence-acquisition preparation unit (host-only, 2026-10-28): the PS evidence source, the runner, the device surrogate, the bring-up execution plan — delivered once, whole, for review

**What this unit is.** The one complete host-only unit the owner's disposition on `c84b8bd5` (2026-10-28, archived in
`owner_ruling_2026_10_28/`, its section 3) authorised: "B4Q physical-runner and evidence-acquisition preparation" with the bring-up
plan draft — under the owner's substantive correction that it is **not** "pipe → UART": the v1 image's board HAL exported no MMIO /
PCAP trace and the verifier required `emulated`, so the unit had to add a truthful real-source acquisition / export contract with a
versioned schema, adapter and verification, keep the logical O / F / X semantics, and never fabricate board facts from the model or by
reading the surrogate's private backend logs; PS instrumentation allowed, any image / wire change a distinct identity, rebuilt and re-pinned.
**Nothing physical happened and nothing is claimed about a device**: no board contact, power, provisioning, supply measurement,
image / bitstream loading, physical PCAP, production key, B4Q physical session, routing, exploration / gate or threshold change;
local files and emulated / PTY endpoints only; fixture key only. Delivered on the branch `b4-b4q-runner` on top of `main` =
`e34432ea`; no push, no merge (not bundled with the ruling's section 3).

## 1. The deliverables (the ruling's A–E), where they are, how each is held

| deliverable | what was built | held by |
|---|---|---|
| **A** the evidence-source audit | `docs/b4q_source_audit.md`: every raw item the records / links / A7 / console contract consume mapped to its PS producer; what no board can produce (a frame-store digest, a bus response beyond the PS's own abort, an `x` cell, a DMA's effect at its time, the cycle time, the executable's identity from the IDENT, the log's tail after the terminal END or a cut, the device's DMA handling, the surrogate's private logs) and what is claimed instead | the document; the verifier's `verify_source` implements §3.4 |
| **B** the PS instrumentation — a new image identity | `firmware/b4q/target/b4q_ring.{h,c}` (pure): the append-only evidence log, 16-byte records of every window / DevC / buffer access (refused flagged), the marks, polls and sentinel runs compressed in place; `b4q_app.c`: `answer_export` (RINGINFO → RING, PULL → CHUNK), the `log` position on IDENT / SIGNREQ / RESULT / END, the **export epilogue** after a non-terminal END, the overflow NACK; the board HAL / host HAL log every access; `b4q_board_main.c`: 16 MiB at `0x10800000`, 16 more strongly-ordered sections; `b4q_app_host.c`: a 16 MiB buffer. Protocol `b4q-v2`; the image **`b4q_app_v2.bin`**, sha256 `4d989ee84757f60965d2a43da9c61981366893423e3b96bd559b575edf07da5b` (98 324 bytes; two clean builds byte-identical — `build_evidence.json`); the v1 image `010f6a05…` is history | `tests/test_b4q_app.py` (the image's layout, the console twins, the source audit), the battery's R1–R3 / A1–A6, `xcheck.txt`, `IMPORT.json` refreshed (b4q_ring.{c,h} added) |
| **C** the acquisition / export contract, the versioned source, the adapter, the verification | `host/b4q_evidence_log.py` (`ps-evidence-log-v1`: the grammar refused by name, the incremental `Deriver` whose prefix derivation is the whole's prefix, `read_frame.target_frames_hash` = the digest of the eight frames the PS read back, `submit.mode = "unwitnessed"`, `nonce_read`, `trace_index_at`); `host/b4q_console_session.py` (`source="ps-evidence-log-v1"`, `PsEvidence`: the records from the pulled log after every result, the console positions from the board's `log` offsets, `manifest.source`, `tail_unobtainable`, the halt on a digest mismatch / an overflow, the epilogue pull and its closing QUIT, the zero-token END before any IDENT); `host/b4q_session.py` (the evidence-source hooks: `_acquire`, `_nonce_before_tx`, `_transport_alive`, the two verifier rules recorded on the session side); `host/b4q_verify.py` (`verify_source`: the derivation recomputed and held equal entry for entry, the raw log held to the board's last RING and the END, the console positions, `uart-board` refused by name, an unknown source kind refused, a retained log beside an emulated source held to the emulation; the v2 replay: the epilogue, the zero-token export, a corrupted CHUNK's failed answer, the banner as the cut marker held to its bytes, a cut export / the terminal END / a declared overflow as **limitations** apart from findings; `ControlPlaneStop`: a runner archive without a session) | `tests/test_b4q_runner.py` (Adapter / PsSource / SourceRules), the battery's E1–E4 / V1–V8 / S2 / A3+S1, the 19 console scenarios under the PS source (`e2e_ps/`, every archive agreeing) and under the emulated source with the retained log held to the emulation (`e2e_emulated/`) |
| **D** the runner, the surrogate, the scenarios | `host/b4q_runner.py` (`Port`: a PTY → `console-pty-surrogate`, a tty → `uart-board`; `UBoot`: the prompt from any state with the 4205's `d` break key and both prompts, `loady` + the host's own YMODEM-1K sender `host/b4q_ymodem.py`, `crc32` = the **load witness** held to the host's crc32 of the file, `mw.l` × 24 + `md.l` = the **page witness**, the nonce by `md.l` of the carrier window, `go`; `RunnerSession`: **no backend in its process**, the PS source forced, a boot banner mid-session = the cut by name, the host's silence bound, unconditional retention of `raw/console.bin` / `raw/console_tx.bin` / `uboot.json` also on a stop; the IDENT's image echo kept apart from the load witness); `host/b4q_device_surrogate.py` (emulated U-Boot on a PTY master — the banner, the countdown broken by `d`, `loady` as a YMODEM receiver, `mw.l` / `md.l` / `crc32` / `go` / `reset` — then the real v2 host harness with its console bridged byte for byte and its MMIO answered from a private backend; the loaded bytes "executed" only if their sha256 is in the image table; 14 declared faults); `host/b4q_runner_e2e.py` (31 scenarios, each with its declared `expect`) | `e2e_runner/` (31 archives: 29 verified agreeing, 2 stopped before any session object — `missed_autoboot`, `no_prompt` — with their transcripts), `tests/test_b4q_runner.py` (Runner / YModem / Guards), the battery's N1–N4 |
| **E** the bring-up execution plan | `docs/b4q_bringup_plan.md`: the fixed inputs, the EBAZ4203 (512 MiB) as the target and the 4205's DDR map incompatibility, the phases P4 (control plane, no `go`) / P5 (the opening) / P6 (one transaction) each under its own authority, the measurements M1–M8 (DDR size, UART / load witness, FCLK0 and the window, the DMA / PCAP chain, the watchdog period and the bounds in seconds, the tick, the export rate, the exception path not exercised) with acceptance and stop, the stop rules and retention, the authorities named and not granted | the document; `docs/b4q_plan.md` v0.4 and `docs/b4q_image.md` v0.5 (§11) point at it |

## 2. The runs of record (`assemble.sh`, fresh runs; `run_header.txt`)

| run | what | result |
|---|---|---|
| `build_evidence.json` | two clean builds of `b4q_app_v2` with the pinned toolchain | byte-identical; sha256 `4d989ee8…`; the 5 + 16 MMU sections, the evidence log region, b4q_ring in the sources |
| `host_build.txt`, `xcheck.txt` | the host harness, the twins, the cortex-a9 compile check | OK |
| `e2e_emulated/` (19) | the console scenarios under the emulated source, the PS log retained beside the fake's logs | 19 / 19 verified, agreeing; `source.agrees_with_emulation` true on every archive that retained a log |
| `e2e_ps/` (19) | the same scenarios with the records built from the PS log pulled through the console (the backend answers MMIO only) | 19 / 19 verified, agreeing; `valid` clean; `sequence_cut` with the terminal-END limitation (17 648 bytes unobtainable, the record cut has no O); `interrupt` with an empty range for the cut transaction |
| `e2e_runner/` (31) | the runner over the surrogate: the 18 console scenarios adapted + 13 of the runner's own (interrupted load, wrong crc, md garbage, a page corrupted after its witness, a page write that does not take, missed autoboot, no prompt, unknown image, silence, a reset mid-session, a corrupted CHUNK re-asked, the log overflow, a DevC fault) | every declared expectation met (`e2e_summary.json`); 29 archives verified agreeing (`valid`, `corrupt_chunk` clean with both witnesses equal; the cut sessions with their partial export as a limitation; the pre-`go` stops as `control_plane_stop`), 2 stops before any session (transcripts only) |
| `a7_valid_ps.txt` | A7 on the PS-source valid session's logged accesses | no finding |
| `mutants.txt` / `mutants.json` | the focused battery (`b4q_runner_mutants.py`): 27 single mutants + 1 combined | **28 killed, 0 survived, 0 edit-miss, 0 probe-error**; a scenario that did not run is never a kill (PROBE-ERROR by construction); the one hang-kill (A3+S1) is where the bound IS the guard |
| `tests_b4q.txt` | the B4Q test modules (`test_b4q_app`, `_wire`, `_session`, `_runner`, `_derive`, `_emu`, `_firmware`, `_schema`, `_view`) | **Ran 93, OK** (the image built with the pinned toolchain inside them) |
| `import_check.txt`, `protected_paths.txt` | the frozen b4/ and the protected paths against `main` `e34432ea`; `b4q_tx.c` unchanged | all equal; empty diff |

## 3. What the unit found on the way (for the owner)

- **The host harness's poll budget is a wall-clock-ish bound of ≈ 0.5 s** (`B4Q_APP_IDLE_POLLS` = 400 000 polls of a syscall): the
  host's between-command work (the pull, the derivation, the records) must stay inside it — hence the incremental `Deriver`. On the
  board the same counts are a different number of seconds: the plan's M5b.
- **The emulated source's `pcap_log` orders a frame's `read_frame` at the device's delivery; the PS logs its own read of the frame
  later** — the two witnesses agree entry for entry by (n, kind), not by position; the verifier compares them so.
- **The END is terminal for effects, not for export**: without the epilogue a stopped session's log could not have been pulled;
  the terminal END (the exhausted sequence) still leaves its tail unobtainable — a declared limitation, never filled in.
- **The 4205's DDR map does not fit the image** (the page, the buffers and the log are above 256 MiB): the bring-up target is an
  EBAZ4203 (512 MiB); a re-placement is a new image identity under a ruling.
- **A transport cut mid-transaction leaves that transaction with no PS evidence**; the verifier's completeness rule names the gap
  (an empty range for the interrupted last record) instead of filling it from the fake's trace.

## 4. What this unit does not claim

No on-target evidence; no claim about a UART, a DMA, a PCAP, a watchdog, an abort, a tick or a supply on silicon. The verifier
refuses `uart-board` archives by name: extending its claims to a board archive is a unit of its own. The runner's control plane is
validated against the surrogate's emulation of U-Boot's wire behaviour, not against U-Boot. The fixture key only. No change to the
carrier, the register map, the hypothesis / model / task, the no-go results, the qualification claim or sizes. `b4q_tx.c` unchanged.
B1–B3's files read-only. No push, no merge.

# B4 — the B4Q PS-image preparation unit (host-only, 2026-10-28): the board application, its BSP, its console notary, its bounds, its build evidence — **resubmitted after the owner's HOLD on `ba18e3c` (section 7: R1–R5 and P3 repaired in this unit)**

**What this unit is.** The one complete unit the owner's PASS on `a41f573` authorised (its section 4, archived in
`evidence/b4/unit_b4q_integration_2026_10_27/owner_review_a41f573_PASS/README.md`): "the actual PS board-image preparation,
host-only" — a loadable PS application ELF with its offline build artifacts and identities; the target HAL, the notary / console
framing, the bounded waits / watchdog, the DDR cache / MMU discipline and the exception-to-stop path, preserving the admission
invariant and the key-window separation; host-side tests of the actual glue / protocol / record paths with injected backends and
faults, target compilation / linkage checks and A7 against the actual program; the readiness / plan documentation naming the
image and the remaining physical prerequisites. The design record is `docs/b4q_image.md`; the plan is `docs/b4q_plan.md` v0.3.
**Nothing physical happened and nothing is claimed about a device**: the image was compiled, never loaded; the console is a
pipe; the UART, the DMA / PCAP, the fabric, the watchdog's clock and the aborts are emulated, counted or never fired; no board,
power, provisioning, 2d, routing, production, push, merge. Delivered once, whole, on the branch `b4-b4q-integration` on top of
the closed integration unit (`e267405`).

## 1. The four deliverables, where they are, how each is held

| deliverable (the PASS's section 4) | what was built | held by |
|---|---|---|
| 1 the loadable PS application and its build artifacts | `firmware/b4q/bsp/build.sh` → `build/b4q_image/b4q_app.{elf,bin,map}` (ignored; pinned by hash): the accepted executing side (`b4q_tx.c`, unchanged) and `b4q_derive.c` with the shared command unit `b4q_cmd.c` under the board application `firmware/b4q/target/` and B1's BSP (`firmware/b4q/bsp/`: `lscript.ld`, `include/*`, `src/console.c` byte for byte; B1 untouched), cross-compiled with the instrument's pinned xPack arm-none-eabi-gcc 14.2.1 against embeddedsw 2025.2 standalone_v9_4 + scuwdt_v2_6 (referenced in place); load address 0x02000000, `go 0x2000000`; the carrier bitstream and the register map unchanged | `build_evidence.json` (`host/b4q_build_evidence.py --build`): two clean builds byte-identical; the compiler's path, version and sha256; every source the image links and every header gcc names (49 translation units, 90 headers) by sha256; the runtime objects and libraries; the ELF's entry, program headers, sections, the symbols that matter, the DDR layout; `tests/test_b4q_app.py::Image` (the build, the entry inside the first page, the vector table at 0x02000000, the segments inside lscript's region and never over the buffers / the page, `make xcheck`) |
| 2 the target HAL, framing, watchdog, MMU, exception path | `target/b4q_board_hal.c` (Xil_In32 / Out32 behind the pure allowlist `b4q_psmap.c`; a refused address reported SLVERR and never issued; OKAY = "completed without an abort", nothing invented), `target/b4q_board_main.c` (the three buffers and the page strongly-ordered non-cacheable before any access; the global timer; data / prefetch abort and undefined handlers → END ABORT with DFAR / DFSR, then a halt; the SCU watchdog in reset mode with B1's pinned load / prescaler, armed only when the page asks, kicked only after a framed line went out), `target/b4q_board_console.c` over B1's `console.c`; the wire `target/b4q_wire.c` (b4q-v1: the instrument's CRC / base64url byte for byte; the identity page); the session `target/b4q_app.c` (the IDENT, the commands, the console notary with the request id, the refusal final, the stale reply ignored, three attempts within a poll bound, heartbeats, NACKs, the END by name); the admission invariant preserved (the application performs no MMIO; `b4q_sign` fails closed); the key window absent by construction; the fixture key only | `tests/test_b4q_wire.py` (8: the C unit against the Python twin on fixed and random payloads, every refusal code, the page, the verbatim digests), `tests/test_b4q_app.py` (16: the 18 console scenarios fresh-verified and agreeing, the framing of every console line by the twin, the kick invariant held by the harness's own count, the bounded notary, the silent host, the bad page / unarmed watchdog signing nothing, the executing side's stop through the console, the allowlist offset by offset against the table and the A7 regions, A7 on the program, the source audits), the focused mutants (section 3) |
| 3 host-side tests of the actual glue with injected backends and faults; target compilation; A7 | `host/b4q_console_session.py` (the board host over the emulated backend: the page written before the program starts, IDENT held — protocol, token, image digest echo, nonce echo, watchdog state —, TX / QUIT framed, SIGNREQ answered by the bench notary, EV / HB / NACK / END logged in `console.jsonl`, the records built by the accepted session class from the same register trace; the fault knobs declared in the manifest), `host/b4q_console_e2e.py` (18 scenarios), `host/b4q_wire.py` (the twin); `make xcheck` (every pure unit for cortex-a9) and the image link; `host/b4q_a7.py` with the page as a read-only region | `e2e/` (every scenario's records, trace, PCAP and console logs, `verify.json` / `verify.txt`), `a7_valid_console.txt`, `xcheck.txt`, `host_build.txt` |
| 4 the readiness / plan documentation | `docs/b4q_image.md` (what was built, the wire, the invariant kept, **what only a device can show**, the scenarios, what is not claimed); `docs/b4q_plan.md` v0.3 (P2 built host-only and NOT met as a board prerequisite; the F8B3 bring-up and 17A6 qualification handoffs explicit: the image pinned by the build evidence and echoed by the IDENT, the page and token the runner's, the key a P3-K ruling, 2d's provisioning and supply measurement, FCLK0, the write-set / composition authority, F8B3's PERIPHCLK, the UART / DMA / exception path on the device; no prerequisite marked met, no N / B\* / prediction / session size, 2c not frozen, the no-go results intact); `docs/b4_architecture.md` §13 row | this README; the owner's review |

## 2. The runs of record

`run_header.txt` names the commit the evidence was assembled on. `build_evidence.txt` / `build_evidence.json`: the two clean builds
(`reproduced_byte_identical: true`), the image's sha256, the inputs. `e2e_run.log`, `e2e/e2e_summary.json`: the 18 console scenarios;
per scenario `verify.txt`: the fresh-process verification, the console contract included — **every archive agrees with its session**; the valid paths (`valid`, `a5`,
`reply_corrupt`, `reply_dropped_once`, `wrong_token`, `stale_reply`, `garbage_command`, `silent_host`, `host_seq_gap`, `duplicate_tx`, `malformed_tx`) clean (the refused commands
of the last two are named non-successes that ran nothing); the negatives named
(`notary_refuses`, `replies_dropped`, `pre_event_corrupt`: STOP at P1 / P2, no O, the session halted, the next candidate refused;
`bad_page`, `watchdog_fail`: no IDENT, nothing signed, END STOPPED; `interrupt`: the transport cut). A7 on the valid console session:
empty (`a7_valid_console.txt`; the page's 24 reads are the program's, counted). `import_check.txt`: the frozen `b4/` untouched (59
entries equal). `protected_paths.txt`: nothing under the protected paths changed since the closed integration unit `e267405`; from
`main` only the previously authorised manifest correction. `tests_b4q.txt`: the eleven unittest modules (the accepted nine rerun as the
regression of the shared command unit and the session / verifier edits, plus the two new ones) — **95 tests OK, no skip**, the carrier
benches first.

## 3. The focused mutant battery (`b4q_image_mutants.py`, `mutants.txt`)

Eleven single mutants of the first delivery in the image's own pure units — the kick removed (the application still claiming it), the page checksum and
the reserved words unchecked, an unarmed watchdog ignored, the CRC unchecked, the token unchecked, another request's reply accepted,
the reply bound and the idle bound removed, the key window and the page made writable — each probed by the console scenario or the
twin check that observes the guard (the harness's own kick count, the bad page / unarmed watchdog, the framing faults, the bounds
under a wall-clock limit a missing bound cannot meet, the allowlist). **11 killed, 0 survived, 0 edit-miss of 11**; five green
baselines first. One mutant was first written so that the compiler refused it (the token check deleted left its parameter unused
under -Werror) and was rewritten to keep the comparison and drop the refusal, so that its kill is the probe's (`wrong_token`: no
NACK, the foreign line accepted), not the build's; the battery was then rerun whole into `mutants.txt`. **After the HOLD, sixteen more** (section 7): R1a–c the budget
(never spent / replenished by another frame / the oversize discard uncharged), R2a–b the two freshness checks, R3a–b the two latches,
R4a–e the console contract (a dropped log, the RESULT binding, the IDENT's token, the END's counters, the cached IDENT), R5a–d the
grammar (an unknown kind defaulted, a wide number, trailing text, a no-op control) — each probed by the budget twin, the duplicate /
after-stop scenarios and the host's unit cases, the console tamper copies, the parser twin. The whole battery rerun whole into `mutants.txt`: **27 killed, 0 survived, 0 edit-miss of 27**, ten green baselines. Two of
the first runs of this round had survivors that were probe blind spots, not equivalences — R1b (a foreign-frame flood during a sign
wait: the twin's stale flood never reached that branch; a seventh mode added), R4c / R4d (the IDENT's token and the END's counters:
masked by the cached-summary comparison; coordinated tampers of the line AND the cached summary added), R5a / R5b / R5d (an
unknown kind not consumed, a width overflow also out of range, a partial TASK with an out-of-range first cell: the mutants / cases
sharpened so that each guard is reached) — each fixed in the probe or the mutant, the battery rerun whole; no survivor is claimed
equivalent.
The log's header names the working-tree commit at the time of the run; the sources it restored to are the ones the code commit of
this round carries (their digests in `build_evidence.json`).

## 4. The session / verifier edits of the accepted unit, and why

Two edits outside `firmware/b4q/target`, both needed by the console path and both covered by the accepted suites rerun: (i)
`b4q_host_main.c`'s TX parser and RESULT writers moved into `b4q_cmd.c` (the host driver's output byte-identical: the accepted e2e's
`firmware_result.json` unchanged); (ii) `b4q_session._opened` split out of `open()` for the console session, and the opening's
findings worded exactly as the verifier recomputes them (the record's validators and schema, the host's view of the readback, the
executing side's own refusal) — a branch the host-only path never exercised (its executing side always reached the readback) and the
console path does (a bad page, an unarmed watchdog: refused before any readback); the verifier now also states the executing side's
refusal and validates `session_open.executing_side`'s shape (R2c's discipline). `host/b4q_a7.py` learnt the identity page as a
read-only region (a write into it is a finding). No change to the records, the schemas, the qualification readings, the RTL, the
register map, the bitstream.

## 5. What the unit does not do

No board connection, power, provisioning, physical PCAP or image loading; no 2d, routing, production seed / search / gate; no push,
no merge; no change to the carrier bitstream, the register map, the hypothesis / model / task, the protocol / statistics /
thresholds, the labels / receipt, the historical results; B1–B3's files read-only (the BSP copied, nothing of theirs edited). No
measured timing anywhere: every bound is a count; the watchdog's period is B1's 17A6 pin until F8B3's PERIPHCLK is measured. The
production key is a later, separately authorised act. The image's existence meets no board prerequisite (`docs/b4q_plan.md` §8).

## 6. Files

`README.md` (this) · `build_evidence.json`, `build_evidence.txt` · `host_build.txt`, `xcheck.txt` · `e2e_run.log`, `e2e/` (fourteen
scenario directories: the records, `manifest.json`, `summary.json`, `verify.json`, `verify.txt`, `session_open.json`, `notary_log.json`,
`trace.jsonl`, `pcap_log.jsonl`, `events.jsonl`, `console.jsonl`, `accesses.jsonl.gz`; `e2e_summary.json`) · `a7_valid_console.txt` ·
`b4q_image_mutants.py`, `mutants.txt` · `tests_b4q.txt` · `import_check.txt` · `protected_paths.txt` · `run_header.txt` · `assemble.sh`.

## 7. The repair after the owner's HOLD on `ba18e3c` (2026-10-28; archived in `owner_review_ba18e3c_HOLD/`, 97 checksums OK)

The owner reproduced the build (the same raw `.bin`), the 90 tests, the 11 / 11 mutants and 28 agreeing fresh verifications, and held
five residuals, each reproduced with injected fixtures against the unmodified sources (`wait_probe.c`, `parser_probe.c`,
`console_probes.py`, `archive_probes.py`); all five accepted and repaired in this same unit (`docs/b4q_image.md` §7 has the design):

| item | the residual | the repair | the evidence |
|---|---|---|---|
| R1 (P1) the receive budget was replenished | `b4q_sign` handed the full poll budget back after a stale or foreign frame; `recv_frame` after a malformed line; the oversize discard had no bound | **one cumulative budget per declared wait** (`b4q_budget`: per SIGNREQ attempt, per command wait), spent by every readiness poll and every byte read whatever the line is (well-formed, malformed, stale, another type, an oversize line's discard); nothing replenishes it (not a heartbeat, a NACK or a kick); the per-wait NACK cap stays; the flush before a SIGNREQ is the primitive's own 4096-byte cap, counted apart (`END.flushed`); the command wait's budget renews only after a transaction ran (a flood of valid non-command frames ends the wait PROTOCOL, never restarts it) | the budget twin `target/b4q_wait_twin.c` (the owner's fixture approach: the unmodified `b4q_app.c`, injected console, every poll counted, a 50x fixture cap): a silent peer, a stale-reply flood and an endless overlong line each end at **exactly 3 × the attempt's budget**, the malformed and non-command floods within it, the silent host at exactly the idle budget — `test_r1_*`; mutants R1a–c, B1 |
| R2 (P1) a duplicate TX ran again | the application assigned the host sequence without a check; the host accepted duplicate / decreasing board sequences | **freshness at both receiving boundaries**, before any effect: the application refuses a host frame whose sequence is not greater than the last accepted (NACK `stale sequence`; a gap is accepted — a dropped frame; the first frame sets the floor); the host refuses a duplicate / decreasing board frame (counted, noted in the console log, a console finding, the session halted); request-id binding kept beside sequence freshness; each side's sequence starts at 0 / 1 and the session ends PROTOCOL / the host refuses to frame before a wrap (`B4Q_APP_SEQ_LIMIT`) | `duplicate_tx` (the previous TX line replayed byte for byte: NACK, no signature, no trace, no record, the session halted on the named non-success), `host_seq_gap` (a gap of 5: closed, clean), the host's unit case (7, 7, 6, 9 → one accepted, two refused, the session halted, the fresh 9 still counted) — `test_r2_*`; mutants R2a / R2b |
| R3 (P1) the framing boundary signed after a stop | the application's loop continued after a failed transaction; the host's notary answered without the halt latch | **the session latch at the application** (`S.sum.halted`: set by any transaction that did not close — status ≠ 0 —, a later TX is NACKed `halted: <the first failure>` and `b4q_sign` refuses without a request; QUIT still closes the session; the A5 `injection_open` close is status 0 and no stop) and **at the host's notary** (`_answer_sign` answers `REFUSED <req> the session is halted` and logs the refusal once `self.halted` is set); the accepted per-call rule of `b4q_tx.c` untouched | `after_stop_tx` (a valid TX injected at the console boundary after a notary refusal: NACK halted, 0 signatures, 0 trace events, `END.refused_tx` 1), the host's unit case (an unsolicited SIGNREQ while halted: REFUSED, a notary-log refusal) — `test_r3_*`; mutants R3a / R3b |
| R4 (P1) the console evidence was never verified | `console.jsonl` and the transport summary were written, not read | **the console archive contract** in `b4q_verify.verify_console`: the retained log required (a dropped log is `REFUSED`) and shaped; every board line re-parsed under the page's token with its CRC, its type the protocol's, its sequence strictly increasing (a line the session noted as refused must indeed be stale); every host line likewise, the session's noted bench faults counted against the declared knobs; the IDENT derived and held to the page (token, carrier digest, flags, epoch), to the executing-side image (digest echo), to the retained opening result, and the cached transport IDENT to it; every RESULT held to the retained `firmware_result.json` of its position (an interrupted transaction's missing one allowed); every SIGNREQ's request id its first line's sequence, re-requests ≤ 3 on the same candidate, every OK SIGNREPLY's 24 words the notary log's for that candidate (the notary now logs its words), every REFUSED one a logged refusal; the latch on the lines (no RESULT and no OK reply after a RESULT that did not close); the END derived (counters recomputed from the lines, kicks = lines, COMPLETED only after the host's QUIT, nothing from the host after a non-COMPLETED END, `opened` the retained opening's), the cached END and stats held to it; the session's own console findings compared (agreement) | `test_r4_*`: a dropped log REFUSED; the IDENT's CRC, token and the cached IDENT, a RESULT's fitness, a dropped RESULT, an OK reply's words, a duplicated board sequence, the END's counters and the cached END, the page's magic, the stats and the line count — each **not clean, not agree, named**; the untouched archives agree with empty console findings; mutants R4a–e |
| R5 (P2) the parser normalised, truncated and defaulted | the host driver's `sscanf` parser copied to the wire boundary | **a checked grammar** (`b4q_cmd.h`): kind one of four words; genome 1–8 lower-case hex, only the 21 configuration bits; n decimal 0..28 with exactly n steps of 1–8 hex ≤ 0x1FFFFFF; the root with n = 0; TASK: a 64-hex digest, m 0..256 with exactly 4m fields in range (s 1..n, e 0..7, t 0..1, w 0..65535), every number width- and range-checked before narrowing; fields one-or-more spaces apart; trailing spaces only; anything else refuses the whole command (NACK `malformed TX`, nothing run). The SIGNREPLY parsed the same way (`req` exact, exactly 24 hex words, nothing after; a reply to another request ignored on the same budget; a malformed one NACKed) | the parser twin (`TX …` through `b4q_wire_twin`): the owner's six cases and seventeen boundary cases refused, the legitimate forms and every TX the host-only path ever framed parse — `test_r5_*`; `malformed_tx` (six commands through the console: NACK, 0 signatures, 0 trace events, 0 DMA submissions; a legitimate one then closes); mutants R5a–d |
| P3 | `reproduced_byte_identical` compared the raw `.bin` digests only, without saying so | the evidence's `reproducibility.covers` states it: the raw `.bin` only; the ELF / map hashes are provenance artifacts that carry debug sections and checkout paths; the ELF's layout facts are what the image test holds | `build_evidence.json` |

Two things the repair changed outside the target: the notary's log now carries the 24 words it handed out (the console contract binds every
OK reply to them); a command the application refused by name (status 7 at the host: a NACK where a RESULT was expected) ran nothing and is
not a transaction record — it stays in the console log and the transport summary (`refused_commands`) and halts the session as any unsealed
outcome does (`docs/b4q_plan.md` §4.2). The image was rebuilt and re-pinned (`build_evidence.json`); the accepted executing side
`b4q_tx.c` is byte-identical to `e267405`'s.

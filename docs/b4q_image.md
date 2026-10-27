# B4Q — the PS image (host-only preparation, v0.1, 2026-10-28): the standalone application that runs the accepted executing side on the board, its BSP, its console notary, its bounds, its build evidence — COMPILED, NEVER BOARD-RUN

> **Authorisation.** The owner's PASS on `a41f573` (archived in `evidence/b4/unit_b4q_integration_2026_10_27/owner_review_a41f573_PASS/`,
> its section 4): one complete B4Q PS-image preparation unit, host-only — "the actual PS board-image preparation", to satisfy the
> board-image / BSP / transport prerequisite (`docs/b4q_plan.md` §8 P2), not to execute qualification or revive the search / gate
> route. **Not authorised, not done:** board connection, power, provisioning, physical PCAP or image loading, 2d execution, routing,
> production draw / search / gate, push / merge. Everything below was compiled and exercised on the host; the first board contact is
> the F8B3 bring-up under its own execution plan and execution ruling (§7).

## 0. The one sentence

The image is the accepted executing side (`firmware/b4q/b4q_tx.c`, unchanged) linked under a thin board application whose every
provable part — the console framing, the identity page, the address allowlist, the session state machine with its bounds and its
notary exchange — is a pure unit the host compiles from the same source and drives through the same emulated backend and a Python
console host, so that what the tests hold is the bytes and the sequence the board will produce, not a model of them; what only a
device can show (the UART, the real DMA and PCAP, the watchdog's clock, the aborts) is named as such and left to the bring-up.

## 1. What was built (and where)

| piece | files | what it is | held by |
|---|---|---|---|
| the board application (pure) | `firmware/b4q/target/b4q_app.{h,c}` | the session: the identity page read through the HAL and parsed; the watchdog armed when the page asks (fail-closed: cannot arm → END STOPPED); `b4q_session_open` → the IDENT line; then the host's commands (TX / QUIT) through the console, each TX run by `b4q_transaction` and answered with the RESULT line (the host-only driver's exact JSON, `b4q_cmd.c`); the notary behind `b4q_sign` as SIGNREQ / SIGNREPLY with the request id, the refusal final, a reply to another request ignored, a bad line NACKed and the request re-sent, at most three attempts within a poll bound; the events behind `b4q_emit` as EV lines; heartbeats during every bounded wait; the END line by name (COMPLETED / STOPPED / PROTOCOL / ABORT) | `tests/test_b4q_app.py` over the 14 console scenarios of `host/b4q_console_e2e.py`; the focused mutants |
| the framing (pure) | `firmware/b4q/target/b4q_wire.{h,c}` | `B4Q1 <TYPE> <seq> <token32> <payload-base64url> <crc32>`; the CRC over everything before the final field; the instrument's `p3_crc32` / `p3_base64url` / `p3_base64url_decode` byte for byte (held by digest to `firmware/b1/p3_derive.c`); the parse with refusal codes (bad CRC / not a frame / wrong token / bad payload); the identity page (24 words, magic `B4QI`, layout 1, the token, the U-Boot epoch, the image digest's low word, the carrier digest, the nonce and STATUS the host saw, the flags, three reserved zeros, the xor checksum) parsed as `p3_parse_identity_page` parses B1's | `tests/test_b4q_wire.py` against the Python twin `host/b4q_wire.py` (fixed and random payloads, every refusal, the page) |
| the allowlist (pure) | `firmware/b4q/target/b4q_psmap.{h,c}` | every PS address the program may read / write: the carrier window's registers of the table of record (the key window absent), the DevC's six registers, the three DDR buffers, the identity page (read only), the SLCR IDCODE (read only); checked by the board HAL BEFORE every access | `tests/test_b4q_app.py::Allowlist` against `host/b4carrier_regmap.py` and the A7 regions, offset by offset |
| the board platform | `firmware/b4q/target/b4q_board_main.c`, `b4q_board_hal.c`, `b4q_board_console.c` | the MMU attributes (the three buffers and the page strongly-ordered non-cacheable, B1's rule: no per-operation cache maintenance to miss), the global timer zeroed, the exception handlers (data abort / prefetch abort / undefined → END ABORT with the fault address and status, then a halt), the SCU watchdog in reset mode with B1's pinned load / prescaler, the halt; the HAL's MMIO half as `Xil_In32` / `Xil_Out32` behind the allowlist (a refused address is reported SLVERR and never issued; OKAY means "completed without an abort" and nothing more); the console primitives over B1's `console.c` | the source audit (`tests/test_b4q_app.py::SourceAudit`); cross-compiled (`make xcheck`, the image build); **not** host-runnable, not board-run |
| the BSP | `firmware/b4q/bsp/` | B1's `lscript.ld`, `include/*`, `src/console.c` byte for byte (B1 untouched); `build.sh` re-pointed at the B4Q sources and the top-level `build/` | the build evidence's `b1_verbatim`; the audit |
| the host harness | `firmware/b4q/target/b4q_app_host.c` | the same application linked with the MMIO half of the HAL on stdin / stdout (the emulated backend's line protocol) and the console on two inherited descriptors; the platform as counters (the kicks counted by the harness, reported on exit); small poll bounds so that a silent host is a fast test | `host/b4q_console_session.py` |
| the console host | `host/b4q_console_session.py`, `host/b4q_wire.py`, `host/b4q_console_e2e.py` | the board host's acts: the page written into DDR before the program starts (a board's `mw.l` before `go`), the IDENT read and held (protocol, token, image digest echo, nonce echo, watchdog state), TX / QUIT framed, SIGNREQ answered by the bench notary, EV / HB / NACK / END logged (`console.jsonl`), the records built by the accepted session class from the same register trace; the fault knobs (a corrupted / dropped / stale reply, a wrong-token or malformed line, a silent host, a bad page, an unarmed watchdog) declared in the manifest | `tests/test_b4q_app.py`; `host/b4q_verify.py` on every archive |
| the shared command unit | `firmware/b4q/b4q_cmd.{h,c}` | the TX parser and the RESULT writers, moved out of the host driver unchanged in meaning so the board parses and reports exactly what the host-only path did (the host driver's output byte-identical: the accepted e2e unchanged) | the accepted unit's suites rerun; `tests/test_b4q_session.py` |
| the build and its evidence | `firmware/b4q/bsp/build.sh`, `host/b4q_build_evidence.py` | the image `build/b4q_image/b4q_app.{elf,bin,map}` with the pinned xPack toolchain and the embeddedsw standalone + scuwdt sources B1 uses; two clean builds byte-identical; every input by hash (49 translation units, every header gcc names, the runtime objects), the compiler's identity, the ELF's entry / segments / sections / symbols, the DDR layout | `evidence/b4/unit_b4q_image_2026_10_28/build_evidence.json`; `tests/test_b4q_app.py::Image` |
| A7 on the program | `host/b4q_a7.py` (the identity page as a read-only region) | the program's actual accesses against the RTL decode, the table and the regions — the console program's accesses (the page's 24 reads included) carry no finding; a write into the page is one | `tests/test_b4q_app.py` |

## 2. The wire (b4q-v1)

One line per message, both directions: `B4Q1 <TYPE> <seq> <token> <payload> <crc32>\n`. The CRC (IEEE 802.3) covers everything
before the final space. The payload is base64url (padded, the instrument's alphabet) of the plain text, or `-`. The token is the
session token of the identity page; before the page is read (and on a refused page) the application frames with 32 zeros. Board →
host: `IDENT` (JSON: protocol, the page's fields as decoded, the nonce echo equality, the watchdog state, the opening's RESULT
object), `HB`, `SIGNREQ` (JSON: genome, nonce, req), `EV` (the executing side's event text), `RESULT` (the transaction's JSON),
`NACK` (why), `END` (JSON: kind, reason, the counters). Host → board: `TX <the textual command of b4q_cmd>`, `QUIT`, `SIGNREPLY`
(`OK <req> <24 words>` / `REFUSED <req> <why>`). Sequence numbers are each side's own, strictly increasing. A line that does not fit
is never truncated: a NACK names it. A reply to another request is ignored and the wait continues on the same bound.

**The bounds are counts of console polls, never a clock the application measures:** `B4Q_APP_IDLE_POLLS` (50 000 000 on the board)
for the next host command, `B4Q_APP_REPLY_POLLS` (50 000 000) per SIGNREQ attempt, three attempts, a heartbeat every
`B4Q_APP_HB_EVERY` (5 000 000) polls; the harness compiles with small counts (400 000 / 200 000 / 50 000). What a poll takes on the
board (one strongly-ordered UART status read, B1 measured ~100–200 ns) is a bring-up measurement; the watchdog (30.0 s under B1's
PERIPHCLK pin) is the last resort for a stall inside a line, as in B1.

## 3. The admission invariant, kept

The executing side's rule (the owner's R1): after the first stop of a call no write of any kind is issued and no signature is
requested. The image adds nothing that could bypass it — `b4q_app.c` performs no MMIO; its only outputs are console lines and the
platform kick; `b4q_sign` returns −1 on a refusal, an invalid reply or the exhausted bound and the executing side stops at P1 with
`STOP_SIGN` (the specific cause on an EV line). The key window is absent from the allowlist by construction; a write into the page
or the IDCODE is refused by the HAL. The watchdog is kicked after a framed line went out and nowhere else (one call site; the
harness counts the platform's restarts and the tests hold them to the lines emitted, the END's own line included).

## 4. The platform's facts the host cannot show — the bring-up's

| fact | the image's assumption | what shows it |
|---|---|---|
| UART1 at 0xE0001000 configured by U-Boot | B1's console.c (no re-initialisation) | the F8B3 bring-up's first IDENT line |
| the DMA / PCAP path, the strongly-ordered buffers | B1's MMU rule; the four tuples of the executing side | the bring-up's startup readback and the root's links on the device |
| the watchdog's period | B1's pin: 1 250 000 035 / prescaler 7 = 30.0 s at the 17A6-confirmed PERIPHCLK; **F8B3's PERIPHCLK is unconfirmed** | a bring-up measurement (an armed session left idle until the banner) |
| the exception path | END ABORT with DFAR / DFSR, then a halt until the watchdog resets | only a deliberate bad access on a device (not done; not planned) |
| the load | the raw `.bin` at 0x02000000 (lscript.ld), `go 0x2000000` (the instrument's L5 recipe); the page at 0x10440000 written by `mw.l` before `go`; the image's digest echoed by the IDENT (`app_image_sha_lo32`) against the build evidence's pin | the bring-up's control plane under its ruling |
| the OKAY of an access | "completed without an abort" (the AXI response is not observable from the A9; an SLVERR is the abort) | — (a design fact, stated, not a measurement) |

## 5. The scenarios of record (`host/b4q_console_e2e.py`, 14; every archive fresh-verified, every one agreeing)

`valid` (open / root / three candidates with tasks / QUIT → END COMPLETED, clean), `a5` (J1 / J2 / J3 through the console: pass),
`notary_refuses` (REFUSED → STOP_SIGN at P1, no O, the next candidate refused), `reply_corrupt` (NACK bad crc, re-request, closed),
`reply_dropped_once` (re-request, closed), `replies_dropped` (three attempts, the bound, STOP_SIGN, halted), `wrong_token` (NACK wrong
token, then the command), `stale_reply` (another request's garbage words ignored, the right reply used, closed), `silent_host` (the
idle bound → END STOPPED, heartbeats on the way), `garbage_command` (NACK bad crc, then the command), `bad_page` (no IDENT, nothing
signed, END STOPPED), `watchdog_fail` (no IDENT, nothing signed, END STOPPED), `pre_event_corrupt` (the executing side's own stop
reported through the console; halted), `interrupt` (the transport cut mid-transaction).

## 6. What this unit does not claim

No on-target evidence of any kind: the image was never loaded; the console is a pipe, the UART is B1's untested-on-this-image glue,
the DMA / PCAP / fabric are the host emulation, the watchdog and the aborts are counters and handlers that have never fired. No
measured timing (§2, §4). No production key: the fixture key only; provisioning on a device is a `provisioning P3-K` ruling. No
change to the carrier bitstream, the register map, the hypothesis / model / task, the protocol, the no-go results. B1–B3's files
are read-only inputs (the BSP copied, B1's build script re-pointed; nothing of theirs edited). The qualification claim, N / B\* /
prediction / session sizes and the freeze of 2c are not touched (`docs/b4q_plan.md`).

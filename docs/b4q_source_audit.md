# B4Q — the evidence-source audit (deliverable A of the owner's disposition on `c84b8bd5`, 2026-10-28): every raw item the records need, its real producer on a board, where it persists, how it is exported, what commits to it — and what no board can produce

> **Standing.** A host-only audit written before the runner: the emulated backend of the integration unit supplied, as an
> omniscient fake, material a board does not hand out (a register trace, a PCAP log with the frame store's digests, every access
> with its response). This page maps each raw item the accepted record / link / A7 / qualification contracts consume to its
> ACTUAL producer on the PS, decides the acquisition design the unit implements (§3), and names what is honestly unobtainable
> (§4). Nothing here is on-target evidence: the design is exercised on a PTY surrogate only (deliverable D).

## 1. What the contracts consume, and from where today

| consumer | raw item (emulated unit) | emulated producer | on a board: who actually produces it |
|---|---|---|---|
| `b4carrier_records.observation` / `transaction_close` / `acquisition_boundary` (O / X) | the carrier-window register trace: every `rd` / `wr` with offset, data, response, in order; the transaction marks | `CarrierEmu._log` (the fake's own bus) | **the PS program**: each `Xil_In32` / `Xil_Out32` it issues through the HAL — the only party that sees the data of a read and the acceptance of a write (a refused write on a board is a data abort, never a response) |
| the same | `x` (unmodelled cells) | the hypothesis model | never: a board samples a physical value |
| `session_open` | the executing side's startup-readback digest; the host's own view of it | the executing side (`b4q_tx`) / the fake's frame store | the executing side's digest (a RESULT / IDENT field) **and** the readback words the PS DMA'd into DST_BUF and then read — the PS's reads of DST_BUF are the only host-checkable copy of what the device returned |
| the links (`links.*`, `staging_witness`, `stream_words_sha256`) | `stream_submitted` (the staged stream bytes), `read_frame` (`target_frames_hash` of the fake's store) | `Devc.data` (omniscient) | the stream bytes are the PS's own writes into WR_BUF (observable as its writes); a "frame store hash" does **not** exist on a board — the honest analogue is the hash of the frames the PS read back from DST_BUF after each readback DMA |
| A7 | every access `(op, addr, resp)`: window, DevC registers, the three buffers, the page, the IDCODE; the DMA tuples (`submit`) | `Backend.accesses`, `Devc.submit` | the PS program's own accesses (the DMA tuple = its four DEVCFG register writes); a response is "completed without an abort" |
| the console contract (R4 / C2) | the console lines; the trace index `i` and PCAP position `pcap_n` at each line | the host, from its backend | the console lines (the UART bytes); the positions must come from the board's own log position at emission (its claim, cross-checked against the log's order) |
| the qualification readings | O / X only | — | unchanged |
| `b4q_verify` source gate | `manifest.emulated == True` | the session | a declared physical-source kind with its own contract (§3.4) |

## 2. The producer of record on the PS: the evidence log

Every raw item above that a board can produce is produced by **the PS program's own accesses** — nothing else on the PS side sees
the bus. The acquisition design therefore instruments the HAL: every access the executing side makes through `b4q_rd32` /
`b4q_wr32` is appended, as it completes, to an **evidence log** in DDR (`b4q_ring`, §3.1), together with the transaction marks and
the executing side's events; the host pulls the log over the console in CRC-framed, re-askable chunks (§3.2) and rebuilds the
records from those bytes exactly as it rebuilt them from the fake's trace — with the adapter of §3.3 translating the log into the
logical inputs the accepted builders take. The host never reads anything but UART bytes.

What this is: the program's record of what it did and what it read. What it is not: a bus monitor. A read's data is what the A9
received; a write's "response" is that the write completed without an abort; a DMA's effect is visible only through what the
program later reads back (the DST_BUF words) — the log preserves that distinction by recording accesses, never effects.

## 3. The acquisition design implemented by this unit

### 3.1 `b4q_ring` — the evidence log (PS side, pure unit; the board image `b4q_app_v2`)

An append-only byte log in a strongly-ordered DDR region (`0x10800000`, **16 MiB** on the board — above 256 MiB: the EBAZ4203's
512 MiB, not the 4205's, `docs/b4q_bringup_plan.md` M1; a 16 MiB buffer in the host harness, `B4Q_APP_HOST_RING_BYTES`), fixed
16-byte records `{tick u32, kind u8, op u8, count u16, addr u32, data u32}` (`count`: bit 15 = refused, bit 14 = a RUN, 14 bits of count):

| kind | what | notes |
|---|---|---|
| `WIN` | a carrier-window access (`op` rd / wr, `addr` = the offset, `data`; refused = bit 15 of `count`) | every window access; identical consecutive reads (same offset, same data) are compressed into one POLL record with `count` (the STATUS polls) — the record builders consume the order and the data, not the repetition |
| `DEVC` | a DevC register access | the DMA tuples and the INT_STS polls (compressed the same way) |
| `BUF` | a DDR buffer access (CMD / DST / WR / PAGE) | every word: the staged streams are the WR_BUF writes, the readback frames are the DST_BUF reads, the sentinel prefill the DST_BUF writes; a sweep of the same data over consecutive words (the sentinel prefill / verification) is one RUN record (`count` words from `addr`) |
| `MARK` | a transaction mark / an event id | `open`, `transaction_begin`, `P6_sealed`, `transaction_end`, `transaction_interrupted` |
| `END` | reserved (no END record is written: the END line carries the log's position, record count and digest) | — |

The log is never overwritten: a full log sets `overflow`, the application refuses to admit another transaction (a named NACK
`halted: the evidence log is full`) and the END reports it. The sha256 over `bytes[0:used]` is computed by the PS on demand
(`b4q_ring_digest`, the compressed records amended in place are hashed in their final form) and reported in the `RING` answer and
the END: the host's pulled bytes must hash to it. The tick is the A9 global timer's low word (a counter in the host harness) —
labelled unmeasured. A valid four-transaction session logs ≈ 123 KB (7 709 records; 70 098 polls compressed).

### 3.2 The pull (console, protocol `b4q-v2`)

Host → board `RINGINFO` → board `RING <used> <capacity> <overflow> <sha256(bytes[0:used])>`; host → board `PULL <offset> <n>` →
board `CHUNK <offset> <base64url of n bytes>` (n ≤ 768; a chunk may be asked for as often as needed — a CHUNK corrupted in transit
is the one re-askable exchange, bounded at 8 bad chunks; an offset beyond `used` is NACKed). Every line framed, CRC'd and fresh as
before; an export command renews the wait's budget. The board's SIGNREQ / RESULT / END / IDENT payloads carry `log` = the log
offset at emission, so that the host pulls up to the position each result claims and the verifier binds each line to it (the nonce
read before a request, the staging after a reply). **After the END** (one that is not the terminal, sequence-exhausted one) the
application serves an **export epilogue**: RINGINFO / PULL answered, QUIT ends it, anything else NACKed `ended: export only`; so the
log of a session that stopped is still the host's to pull. After the terminal END nothing is framed: the tail of the log beyond the
last pull is **unobtainable** — the host names it (`manifest.source.tail_unobtainable`), the verifier reports it as a limitation.
A transport cut mid-session likewise leaves the unpulled tail unobtainable: the session is `interrupted` by its transport.

### 3.3 The adapter (host, `b4q_evidence_log.py`)

Parses the pulled bytes (refusing anything outside the record grammar), expands the compressed polls, and yields the logical inputs
the accepted builders take: the window events with marks (`trace`), the DevC and buffer accesses (A7), the staged streams (the WR_BUF
writes of each staging, parsed by the pinned grammar → the staging witness), the readback frames (the DST_BUF reads after each frame
DMA, FAR-ordered → the readback digests), the DMA tuples (the four DEVCFG writes). Every digest the host computes is labelled by its
domain: "the hash of the frames the PS read back", never "the frame store's hash".

### 3.4 The versioned source (host, schema + verifier)

`manifest.source = {"kind": "ps-evidence-log-v1", raw, bytes, sha256, records, digest_equal, end_log, end_log_sha256,
tail_unobtainable, adapter, adapter_sha256, derived, pull_stats, …}` beside the existing `emulated` manifests (which keep their
contract and their re-verification path untouched: `source: null`). The raw pulled bytes are retained verbatim
(`raw/evidence_log.bin`; every RING answer and chunk line stays in `console.jsonl`, the pull statistics in `raw/pulls.json`);
`trace.jsonl` / `pcap_log.jsonl` / `accesses.jsonl` are then the adapter's DERIVATION (`host/b4q_evidence_log.Deriver`, incremental
after every result), which the verifier recomputes from the raw bytes and holds equal entry for entry — never trusts. The verifier
(`verify_source`): a declared PS source without its raw log, or a raw log that is not the declared bytes, is refused; the raw log is
held to the board's last RING and to the END's `log` / `log_sha256`; the console entries' positions must be the board's `log`
offsets mapped onto the derivation; a transport kind `uart-board` is refused by name (no board claim is granted); an archive with a
retained log beside an EMULATED source has that log held to the emulation's own trace / accesses / PCAP activity (the two witnesses
of one session must agree). The records are rebuilt from the derived trace as before, the links recomputed from the derived PCAP
log (its `read_frame.target_frames_hash` = the digest of the eight frames the PS read back in a complete consecutive group — the
only meaning it has here), A7 run on the logged accesses, the console contract replayed with the board's positions.

The sessions: `host/b4q_console_session.ConsoleSession(source="ps-evidence-log-v1")` over the pipe (the backend answers MMIO only;
its trace is not read for a record — the e2e's 19 scenarios run this way too), and `host/b4q_runner.RunnerSession` over a serial
endpoint that constructs no backend at all (`make_backend=False`; the device surrogate on a PTY, `host/b4q_device_surrogate.py`; a
board's UART under a ruling not given).

**The runner archive contract and its verification (the owner's R1 / R4 on `dad9e4de`; `host/b4q_verify_runner.py`).** A runner
archive (`transport.kind` = `console-pty-surrogate`, a declared host fixture, or `uart-board`, the device format) retains both raw
streams (`raw/console.bin`, every byte received; `raw/console_tx.bin`, every byte sent) and `uboot.json` (schema `b4q_runner_uboot`
v2: the execution context, the control-plane steps with their stream offsets, the admission, the load and page witnesses, the
execution phase — persisted after every step and BEFORE `go`). Nothing in `uboot.json` is an authority: the verifier re-assembles the
YMODEM blocks from the sent stream (their sha256 IS the transferred image, held to the archive's executing-side identity and the
context's pin), holds the device's `crc32 for <start> ... <end>` line to the crc32 of those bytes over exactly the loaded range and
U-Boot's `## Total Size` to their length, holds the page's 24 `mw.l` words (sent) to the `md.l` dump (received) and to the
transport's page words and the page's nonce to the `md.l` of NONCE_LO / NONCE_HI, holds the admission's model / DRAM / VARIANT /
FPGA0_CLK_CTRL to the received stream, holds the phase to the streams (`go` sent ⇔ a post-go phase; `## Starting application` ⇒
`go` sent), links every retained console line to the streams in order after `go`, and accepts a control-plane-only archive (no
session) only when the streams show no `go`, no board frame, no transaction directory and the named stop is DEMONSTRATED by them.
Provenance is reported apart (`verify.json: provenance`): a PTY archive is a fixture; a `uart-board` archive's consistency is held
with `observed_on_device: false` (a later ruling's claim, never this verifier's); a synthetic device-format fixture
(`host/b4q_device_fixture.py`, `manifest.synthetic`) is reported as such; a device-format archive carrying an emulator-only witness
(the surrogate's banner, a backend record, a private directory, `emulated: true`, a declared fixture) is found.

The state machine (the owner's C1 on `30c5ccba`): a `go` in the sent stream requires every prerequisite RECOMPUTED true from the
streams — the admission present with `ok`, the admitted image the context's pin, the board class, the board's own `boardid` / `role`
(`printenv`, `docs/board_roles.md`), the clock derived from the SLCR words (`fclk0_from_words`, the same function in the runner and
the verifier) with no PL read before the clock words and the role answer, the carrier's variant word, a complete and equal transfer
of the pinned image, an equal page — else `state: go was issued although …`; the load / crc / go / start addresses are one address
bound to the context; the application's exchange is ACCOUNTED line by line: the received stream after `go` must BE the retained
board console (a noted unparsable line, a noted banner included; the reset's boot output after a noted banner accounted as after
the cut), the sent frames the retained host lines, nothing else sent; a named stop of a class the verifier cannot demonstrate is
`unverified` (a finding). The source (C4): a runner archive is the PS-log source by construction — `manifest.source` absent on one
is refused, never defaulted to the pipe session's emulated contract. The runner's own barriers (C2 / C3): the evidence is persisted
before every guarded step and `go` (a failed persistence is a `PersistStop`: nothing guarded follows); the sent-byte log commits
only what the OS accepted, an incomplete write kept apart as intent; the admitted image's bytes are held from the hash to the wire
(the file is never re-read); the identity, the clock and the carrier are refused by name before anything content-sensitive.

The role policy and the clock eligibility exactly (the owner's R1 / R2 on `6eeacfc2`): the content-class policy of
`docs/board_roles.md` is a FIXED floor — `role ∈ {verify, sacrificial}`, read from the board's own saved environment, no role =
reference = refused; a context may only narrow it (`ExecutionContext.__post_init__` refuses any other list; `--role` likewise;
the verifier recomputes the verdict with the floor first, independently of the context, and finds a context list that widens it).
The clock: the admission reads SIX PS words before any PL access — `FPGA0_CLK_CTRL`, the ARM / DDR / IO PLL `CTRL`s, `PLL_STATUS`,
`BOOT_MODE` — and the selected PLL (SRCSEL) is an ELIGIBLE source iff `PLL_RESET` = 0, `PLL_PWRDWN` = 0, not bypassed (`PLL_BYPASS_FORCE`
= 0, and if `PLL_BYPASS_QUAL` = 1 the `BOOT_MODE` sampled `PLL_BYPASS` pin = 0) and its `PLL_STATUS` lock bit = 1
(`host/b4q_zynq_clk.py`, one module written against AMD UG585, used by the runner and the verifier alike); only then the nominal
rate PS_CLK × FDIV / (DIVISOR0 × DIVISOR1) is held to the pinned 50 MHz. The verifier takes every identity / clock input from the
received prefix before the first PL ACCESS — the earlier of the first PL command's echo and its data reply (`first_pl_reply_offset`;
the owner's approved follow-up on `315f6935`, applied unchanged as `bd7cef03`: as first delivered in `bcfc6fbf` the cut was at the data
reply alone, so a reply arriving while the PL command was already being handled still counted as a prior input) — and requires every
such command before the first PL read command; a later good state is
no earlier admission. All of this is software register consistency — the configured nominal rate of a source the registers call
running — never a measured clock (the bring-up's M3). Modes outside this predicate (a stable-but-unlocked PLL, another SRCSEL
source's unread status, a word not read) are refused as unresolved, not assumed. The nonce of a transaction's links is the one the PS read (`NONCE_LO` / `NONCE_HI` in the log); the timing
word is the one the IDENT reports; a transaction cut by the transport has an empty range and no record of its own (the verifier's
completeness rule names the gap).

## 4. What no board can produce — claims the unit limits

| item | why | what is claimed instead |
|---|---|---|
| a frame-store digest (`target_frames_hash`) | no observer of the PL configuration memory exists on the PS | the digest of the frames the PS read back through the readback DMA (the device's answer to a readback command) |
| the bus response of a completed access | an SLVERR is an abort; a completed access has no readable response | "completed without an abort"; a refused address is the HAL's refusal, never issued |
| an `x` cell | the board samples a physical value | none — every sampled cell is a value |
| a DMA's effect at the time of the DMA | invisible | the later readback |
| the emulator's cycle time | — | the global-timer tick, unmeasured (no timing claim) |
| the identity of the executable the board runs | the IDENT echoes the page's low word (host-written) | the load / transfer witness of the control plane (U-Boot's `crc32` of the loaded range vs the local image) — a different fact, kept apart |
| the UART / DMA / PCAP / watchdog / abort facts of a device | device-only | the bring-up plan's measurements (`docs/b4q_bringup_plan.md`) |
| the log's tail after the terminal END, or after a transport cut | nothing is framed after the exhausted sequence; a dead transport answers no PULL | a named limitation (`tail_unobtainable`; `interrupted.transport`); the cut transaction has no record of its own |
| the device's handling of a DMA (`mode`) | the PS sees its own tuple and the later status, not the device's queue | `submit.mode = "unwitnessed"` |
| what the surrogate's backend did | its logs are private to its process | nothing — a test may cross-check them; the runner never reads them |
| that a device-format archive was observed on a device | a byte stream and a program's log prove internal consistency, not physical behaviour | `provenance.observed_on_device: false` on every archive this verifier accepts; the claim is a ruling's, after the bring-up |

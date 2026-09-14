# A U-Boot repeated-read consistency control on 17A6 (preparation, 2026-09-13)

**Status: host-only preparation, revised after the owner's review of 2026-09-13
(`docs/b1q_board_transport_soak_review_2026_09_13.md`, HOLD, six P2s).** Running it needs the
board powered, the wiring returned to J7, and the owner's ruling. This document and
`host/board_transport_soak.py` open no port and touch no board. The transport stop-loss remains
in force. (The file keeps its original name; the experiment it implements is narrower than that
name suggests, and this document is the definition.)

## What was withdrawn

The earlier version of this document claimed the probe would bound B2Q's frame loss, and argued
from "a clean B1Q run dropped 2 frames in ~300" to "≈3.6 drops in B2Q's 543 frames, so B2Q most
likely busts its budget of 3". **That argument is withdrawn and the claim with it.** Those two
drops are the forced `SIGNREQ` and `REC` controls that `host/b2_runner.py` enables in every
qualification plan (`rec_control=True, sign_control=True`) — fixed session events present by
design, not a random background rate that scales with frame count. The archived summaries show
exactly that shape: `crc_dropped_by_type {"SIGNREQ": 1, "REC": 1}` in both clean attempts.
Controls, real CRC drops, fragments and retransmissions are different things and stay separate.
Nothing here touches the frozen CRC budget.

Consequently this document makes **no prediction about whether a B2Q session would pass**, and
the decision between a native-Linux comparison and a direct B2Q is not settled by it.

## What the experiment is

One narrow question: **does repeating one identical `md.l` command at the U-Boot prompt return a
byte-identical response each time**, under stated conditions, over a stated exposure?

- **Unit:** one *response*. A response whose framed body is not byte-identical to the reference
  response is one **mismatch**, counted once however many bytes differ.
- **Framing, declared as a grammar and recognised by position only** (the fifth review's P2-2):
  `reply := [echo] body [prompt]`. The echo is `command` + CR LF and is recognised **only as the
  very first bytes** of the reply; the prompt is `Zynq> ` / `zynq-uboot> ` **with its trailing
  space** and is recognised **only as the very last bytes**. The declared line ending is CR LF.
  Nothing is normalised: every other byte — a command-like string inside the data, a prompt-like
  string before the end, an extra or missing separator, a stray byte before the echo — is body
  and is compared. A body that does not consist of complete CR LF-terminated `md.l` lines fails
  the grammar and is a mismatch with `grammar_valid: false`.
- **Reference:** the first valid response is a **reference observation** — not independently
  known transmitted bytes, and not proof that the window is stable.
- **Stop rule:** `--stop-after-mismatches` (default 3), counted **over the whole run**. This is
  explicitly *not* the rig's "three lost expected frames within one repetition"; the two are not
  interchangeable.

## What a mismatch means, and what it does not

**The cause of a mismatch is unknown.** It is consistent with corruption on the console
transport, with a change in the source memory being read, and with a command that did not
execute as issued. This tool cannot separate them and does not try. Specifically:

- A mismatched response **is not** a lost rel-v4 frame. One response holds many lines; any
  number of changed bytes in it counts as one mismatch.
- The loop sends the next command only after the previous prompt, so it **does not** reproduce
  the sustained host-TX-during-frame-RX pattern that is under investigation.
- **Declared blind spot:** a corruption present identically in the reference and in every later
  response is invisible here by construction. More aggregate bytes do not fix this.
- A missing prompt is classified `no_prompt` with the cause stated as unknown; only an observed
  boot banner is classified `board_reset`. A read cut by the exposure is `exposure_seconds` with
  `cut_short` and the partial bytes kept — not an error.
- **A boot banner line is a `board_reset` whether or not a prompt follows it** (P2-3): it is
  classified before any comparison and before any further command, in the sync, the reference and
  every repeated read alike, the bytes preserved. A banner is a *line beginning* with a banner
  marker; the ASCII column of an `md.l` line never begins a line, so memory holding banner-like
  text is a mismatch, not a reset.
- **A required acquisition export that fails stops the run before the next command** (P2-1):
  `sync.bin`, `reference.bin`, `reference.json`, `read_NNNN.bin`. The primary export error is
  named in the terminal (phase `export <file>`, stage `export`, exit 2) together with any
  transport error before it; the remaining finalisation and both counters are still attempted;
  a response that completed before its file failed is still classified and its record names the
  missing file. `control.json` / `entry.json` are written after acquisition and cannot stop past
  commands; they recompute `export_complete` truthfully. **The terminal status is decided
  explicitly after the loop** (the sixth review, 2026-09-14): if the last read's raw export
  failed, the terminal is `tool_error` / `export read_NNNN.bin` and the exit is 2 **whatever that
  read observed** — a cutoff, a missing prompt, a banner or a completed response — and the
  observation is kept whole under `terminal.observed` (the read stays unclassified or classified
  exactly as it was, partial bytes and denominators untouched). A transport error on the same
  read stays the primary error with the export error beside it.
- **Statistics name their denominators** (P2-4): `reads_attempted` (a command was issued),
  `reads_completed` (a prompt, no banner, no error), `reads_compared` (classified identical or
  mismatch; every completed read is compared), `reads_unclassified` (with `unclassified_by_reason`:
  `tool_error`, `board_reset`, `no_prompt`, `exposure_cut_short`). `mismatches_per_100_compared_responses`
  divides by `reads_compared` and is **null** when that is zero; `all_compared_responses_differ` is
  **null** when nothing was compared. A cut-short or partial response is neither a match nor a
  mismatch, and is reported, not dropped.

## Scope enforced in the program, versus checks the operator must make

Enforced **before the port opens**, refusing with exit 3:

| check | rule |
|---|---|
| probe window | the read must lie inside `0x00100000..0x001FFFFF`, the reviewed 1 MiB window at the DDR base the B2 BSP records (`firmware/b2/bsp/include/xparameters.h`) |
| alignment / length / end | `--addr` 4-byte aligned, `1 ≤ --words ≤ 0x400`, end address inside the window, no overflow |
| exposure | `--seconds` and `--command-timeout` finite and positive, `--repetitions ≥ 1` |
| adapter | `--expect-usb` must match the node's USB VID:PID |

Because arbitrary addresses are refused, "no PL AXI and no other side-effecting MMIO" is a
property of the input check, not of the operator's typing. There is no `mw`, no write, no DMA,
no JTAG, no image load, no `fpga loadb`.

**Mandatory operator checks this program cannot make**, and which the record says it cannot:

1. **That the board is `17A6`.** `--expect-usb 1a86:7523` identifies the *adapter*, not the board.
2. **That the probe window is unused by the running U-Boot.** A successful first read is not
   proof of that; it must be established independently.

## The command

```
python3 -B host/board_transport_soak.py \
    --device /dev/ebaz-uart --expect-usb 1a86:7523 \
    --label consistency-17A6 --out evidence/b1q/transport_board_17A6_2026-09-13/control \
    --addr 0x00100000 --words 0x100 --repetitions 200 --seconds 3600 \
    --command-timeout 3.0 --stop-after-mismatches 3
```

Every command is bounded by one deadline: the per-command budget, never past the remaining
exposure. Exit codes are the tool's state, not a verdict: `0` returned, `2` a tool error (a
required export failure included, stage `export`) or a board/console condition, `3` refused before the control (identity, window, exposure, no prompt at
sync, or no valid reference), `4` the device would not open, `5` the destination could not be
claimed or written. Evidence: `invocation.json`, `sync.bin`, `reference.bin/json`,
`read_NNNN.bin`, `control.json`, `entry.json`.

`invocation.json` and `control.json` carry `provenance.tool_sha256` for **this** tool, with the
imported `host/transport_rig.py` recorded separately under `dependencies`, plus the measurement
unit and an explicit `claims_not_made`.

## Offline proof

`tests/test_board_transport_soak.py`, **48 tests**, drives `main([...])` against a fake U-Boot;
no real port is opened. Each of the six findings of the fourth review, and each of the four of the
fifth, has a test that fails on the reviewed implementation. The fifth review's: each required
export (`sync.bin`, `reference.bin`, `reference.json`, `read_0000.bin`, `read_0001.bin`) faulted
separately with the issued-command count asserted, and a transport error plus an export failure
both retained; command text inside the data, an extra leading separator, a missing / extra / bare-LF
/ trailing-extra separator, an echo not at the start and a prompt not at the end all as mismatches
with the genuine echo/prompt positive control kept; a banner with a prompt, without a prompt, at
the reference, at the sync, banner-like text in the data column, and the four declared shapes;
zero compared, an exposure cut-off, mixed completed-plus-unclassified with the compared
denominator, and the positive and all-differ controls — stdout and archive compared in each.
The sixth review's: a 67-byte cutoff alone (exit 0), the same cutoff with its raw export failed
(exit 2, stage `export`, the cutoff and its 67 partial bytes retained under `observed`, statistics
still null), and a silent cutoff, a missing prompt and a banner-with-prompt each with a failed
export. The fourth review's: an ASCII-column deletion and a ninth hex digit as mismatches (plus damage in the
address, hex, inter-word space and ASCII regions, and on a later line of a multi-line response);
a provenance failure stopping before the port opens; a detach mid-response keeping the partial
bytes, attempting both counters and still finalising; a failed `control.json` and a failed
`entry.json` both recomputing `export_complete` to false; the exposure bounding an active read; a
missing prompt not called a board reset; an observed banner that is; a sync without a prompt
refusing before any `md.l`; addresses outside the window, misaligned, over-long or overrunning the
end refused with the port never opened; non-finite exposure refused; and the provenance naming
this tool with the rig as a dependency. The declared blind spot is tested **as a blind spot**.

## The ruling to sign (the owner's step)

`rulings/` is gitignored by policy — a ruling is written by the owner per session and never
committed — so this is the text, not a tracked file. It is **illustrative**: the program does not
read it, and none of its fields are enforced by the CLI.

```json
{
  "ruling": "whole-of-probe U-Boot repeated-read consistency control",
  "boardid": "17A6",
  "granted_by": "14sea",
  "date": "2026-09-13",
  "scope": "read-only md.l repeated reads inside 0x00100000..0x001FFFFF; no mw, no write, no DMA, no PL AXI read, no JTAG, no image load, no fpga loadb",
  "authorises": "one run of host/board_transport_soak.py on 17A6 at the Zynq> prompt",
  "measures": "whether repeated identical md.l responses are byte-identical; the cause of any mismatch is unknown",
  "does_not": "bound or predict B2Q frame loss, qualify the carrier, lift the B1Q transport stop-loss, or authorise a B2Q or B2 session",
  "tool_sha256": "37dfad21f75d9377dd03d2c69ce781135934082677bd349a46c034b9e332342e",
  "b1_manifest_sha256": "38238271510536bda565ad1b8321dd04d75e78e1fe77ef94d2795bf9edfd4ba8",
  "operator_checks": [
    "the board on this console is 17A6 (the USB VID:PID identifies the adapter only)",
    "the probe window is unused by the running U-Boot"
  ]
}
```

`tool_sha256` is `host/board_transport_soak.py` as committed here; re-hash it at run time if the
file changed. The run records its own `provenance.tool_sha256` regardless. `b1_manifest_sha256`
is the current committed B1 manifest (the earlier draft named an obsolete `38363973…`).

## Running it

1. Return the CH340's TX/RX from the loopback jumper to main-board **J7**.
2. Power the board; confirm `/dev/ebaz-uart` and a `Zynq>` prompt; make both operator checks above.
3. Place the ruling and authorise the run.
4. Run the command; archive the evidence directory; report `reads_attempted` / `reads_compared` /
   `reads_unclassified`, `mismatched_responses`, `mismatches_per_100_compared_responses` (null when
   nothing was compared) and the terminal reason — as a consistency observation with an
   unknown cause, not as a transport rate and not as a B2Q prediction.

What this result feeds into is a separate decision, which the owner makes.

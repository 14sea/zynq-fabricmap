# The board-side transport control — a U-Boot `md.l` soak on 17A6 (preparation, 2026-09-13)

**Status: host-only preparation. Running it needs the board powered, the wiring returned to J7,
and the owner's ruling `whole-of-probe transport soak` on `17A6`.** This document and
`host/board_transport_soak.py` open no port and touch no board. This is not a B2Q session, does
not lift the transport stop-loss, and adjudicates nothing (plan §5, §6).

## Why this, and why now

The owner asked to measure the real board path before deciding between a native-Linux comparison
and a direct B2Q. The entry point proved the tool offline; the self-loopback measured the host
path with no board on the line (**1 confirmed loss in 2.26 MB** under host TX, 0 in 10.1 MB
without). Neither measures the path a B2Q console session's frames actually cross: the CH340 on
`17A6`, through usbipd into WSL, **with the board powered and transmitting**.

A B2Q console session is **~543 rel-v4 frames** under a CRC drop budget of
**`ceil(4 × 543 / 1000) = 3`**. The two clean B1Q attempts each dropped 2 frames in ~300; the
two lost attempts dropped 3 (budget 2) and 5 (budget 4) and ended `PROTOCOL_CRC_BUDGET`. So the
budget headroom for B2Q is thin, and whether a real board run stays under it is exactly the open
question. This soak measures **damaged reads per received byte** on that path over an exposure
several times a B2Q session's byte volume, so the budget arithmetic can be checked against a
measured rate rather than the loopback's optimistic one.

## What it does (read-only)

At the board's `Zynq>` prompt (U-Boot, `bootdelay = -1` drops straight to it), the tool:

1. gates on the CH340 identity (`--expect-usb 1a86:7523`) **before opening** the port;
2. syncs with one bare CR (clears the power-on RX garbage the 17A6 answers `Unknown command`);
3. takes one clean **baseline** read of a fixed DDR window with `md.l <addr> <words>` — that
   first clean read is the KNOWN answer; **no clean baseline, no soak** (exit 3);
4. repeats the same `md.l` read under the exposure and stop rules, comparing each reply to the
   baseline **byte-exact per line**;
5. classifies each read: `structural` (a line short, misaddressed, or with the wrong word
   count — `parse_md`), `word_mismatch` (parses cleanly but a value differs from the baseline),
   or clean; a boot banner mid-soak is a **board disruption**, not a transport drop;
6. samples `TIOCGICOUNT` before and after; closes the port on every path; archives
   `invocation.json`, `baseline.json/bin`, `read_NNNN.bin`, `soak.json`, `entry.json`.

There is **no `mw`, no write, no DMA, no PL AXI read, no JTAG, no image load, no `fpga loadb`**.
Because no PL AXI register is read, the FCLK0-gated hard-hang (bring-up CLAUDE.md) does not
apply; the window is plain DDR that U-Boot is not touching at an idle prompt, so its contents
are stable and any per-line difference is a transport event, not a memory change.

## The command

```
python3 -B host/board_transport_soak.py \
    --device /dev/ebaz-uart --expect-usb 1a86:7523 \
    --label soak-17A6 --out evidence/b1q/transport_board_17A6_2026-09-13/soak \
    --addr 0x00100000 --words 0x100 --repetitions 200 --seconds 3600
```

Defaults: `--addr 0x00100000` (a low-DDR window), `--words 0x100` (256 words = 64 `md.l` lines
≈ 4.3 KB per read), `--repetitions 200` (≈ 863 KB, about **5× one B2Q session**), `--seconds
3600`, stop at **3 damaged reads**. `--expect-usb ''` disables the identity gate (records it as
metadata only). Pick `--addr` to a window the loaded U-Boot is not using; the baseline read
proves it is stable before the soak spends anything.

Exit codes are the tool's state, not a verdict: `0` returned, `2` a tool error or a board
disruption mid-soak (evidence still exported), `3` refused before the soak (identity, or no
prompt / no clean baseline), `4` the device would not open, `5` the destination could not be
claimed or written. The stdout brief carries `stage`, `terminal`, `damaged_reads`,
`received_bytes`, `damaged_per_100k_bytes`, `counters_delta`, `ports_closed`, `export_complete`.

## What a result can and cannot say

- **It measures the transport, not the protocol.** `md.l` lines are not rel-v4 frames; they
  cross the same UART controller, baud, CH340 and usbipd path at a comparable byte volume. A
  damaged-read rate here is the path's, and it bounds what a B2Q console session would face on
  the same path — it is not the B2Q frame-loss rate itself.
- **A clean soak does not qualify anything.** It does not lift the stop-loss, authorise B2Q, or
  attribute the earlier losses to any component. It says the path, at this exposure, on this
  board, did not damage `md.l` output.
- **A dirty soak reproduces the failure class on the board path with a denominator** — the
  measurement the three lost sessions never had — and gives a rate to weigh against the budget.
- **The counters** (framing, parity, overrun, break) are attempted on the real fd; on the
  `ch341` driver they answer `ENOTTY` and are recorded unavailable with that reason.
- The comparison to B2Q's budget (3 in ~543) is stated in `soak.json` for the reader; the tool
  enforces none of it.

## Offline proof

`tests/test_board_transport_soak.py` drives `main([...])` against a fake U-Boot that emits
`md.l` lines, never a real port: a clean path soaking to completion with every file exported and
the port closed; a deleted byte in the hex as one `structural` damage; a flipped word as one
`word_mismatch`; three damaged reads firing the stop rule; a boot banner as a board disruption
(exit 2) with evidence on disk; silence at the baseline refusing (exit 3) before anything is
spent; the wrong adapter refused before opening; a device that will not open (exit 4); a nonempty
destination refused byte-untouched (exit 5); and `parse_md` flagging short and misaddressed
replies. **No real port is opened by any test.** The whole transport suite is 140 tests, OK.

## Running it (the owner's step)

1. Return the CH340's TX/RX from the loopback jumper to main-board **J7** (Zynq back on the line).
2. Power the board; confirm `/dev/ebaz-uart` and a `Zynq>` prompt (a bare CR first).
3. Place the ruling `rulings/transport_soak_17A6_2026-09-13.json` and authorise the run. The
   `rulings/` directory is gitignored by policy — a ruling is written by the owner per session
   and never committed — so the text is given here as a draft to sign, not as a tracked file:

```json
{
  "ruling": "whole-of-probe transport soak",
  "boardid": "17A6",
  "granted_by": "14sea",
  "date": "2026-09-13",
  "scope": "read-only U-Boot md.l soak on the console path; no mw, no write, no DMA, no PL AXI read, no JTAG, no image load, no fpga loadb; measures transport line-damage only",
  "authorises": "one run of host/board_transport_soak.py on 17A6 at the Zynq> prompt against a fixed DDR window",
  "does_not": "qualify the carrier, lift the B1Q transport stop-loss, or authorise a B2Q or B2 session",
  "tool_sha256": "331c8c446c61d8ec96c952703423129956dbc77af4f3baadb97d7c3970f47f60",
  "b1_manifest_sha256": "38363973c10c48244dc04f08044647b1159d1446b00dec5776d9478b9aad0a0e"
}
```

The `tool_sha256` above is `host/board_transport_soak.py` as committed here; re-hash it at run
time if the file changed, and the run records its own `provenance.tool_sha256` regardless.
4. Run the command above; archive the evidence dir; report `damaged_per_100k_bytes` and the
   terminal reason. Then the choice between native-Linux comparison and B2Q is made against a
   measured board-path rate, not an inference.

The stop-loss stays in force until the owner rules on the result.

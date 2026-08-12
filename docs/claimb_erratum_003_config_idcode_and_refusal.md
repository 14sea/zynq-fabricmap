# Erratum 003 — the configuration IDCODE, and a guard refusal that rebooted the host

**Status:** RTL corrected, rebuild in progress. Ruled by the user 2026-08-13.
**Scope:** `carrier_stream`'s word-15 expectation, and `carrier_axil`'s stream-refusal
semantics. Nothing about the target, the seed, the ceiling, the cap, the masks, the fitness,
the train/holdout split or the A/B rules moves.

This erratum is **additive**. Errata 001 and 002 stand as written, and every failure record
in `evidence/` stays exactly as it was recorded, including the ones whose interpretation this
document overturns. Nothing is rewritten to look prescient.

---

## 1. What was wrong

Two defects, found together, in one command.

### 1a. The RTL expected the wrong IDCODE

`carrier_stream` validated envelope word 15 against a parameter named `IDCODE`, set to
**`0x13722093`** — the PSS/JTAG identity of the XC7Z010, the number read over JTAG all
session and checked by `gate_board_identity`.

That is not what a configuration stream carries. UG470 makes `IDCODE[31:28]` a **revision
field**, and a bitstream's IDCODE register write masks it off, so this device streams
**`0x03722093`**. The host had it right everywhere: the carrier bitstream itself, the parsed
`base_bitstream.idcode` in the phenotype manifest, the candidate gate and the sealed payload
all carried `0x03722093`.

So the engine rejected **every real envelope** at word 15 with `F_CONTROL`.

### 1b. A guard refusal was an AXI error response

`carrier_axil` answered a stream write that arrived with no pass open with **SLVERR**. That
is a reasonable way for a slave to say no, and on this board it is catastrophic:

* SLVERR reaches the A9 as a **data abort**;
* U-Boot's `do_data_abort` calls `bad_mode()`, which calls `panic()`;
* this build has `# CONFIG_PANIC_HANG is not set`, so `panic_finish()` calls `do_reset()`.

The board reboots. The PL is cleared. The console comes back with a **fresh prompt that is
byte-identical to the one the command should have produced**, and the evidence of the
refusal is gone with the boot.

Together: 1a raised a fault at word 15, the phase returned to idle, and the remaining ~520
words of the host's `cp.l` met a closed stream and were answered with SLVERR — so the guard's
own refusal destroyed the host before the host could read the guard's verdict.

## 2. How it presented, and why it took so long

The no-op calibration stopped with `no prompt … the fabric did not answer at all` naming
`md.l <STATUS>`. That address occurs several times in a run, and it was read as the step-0
liveness read without checking. A whole day of isolation cells — fclk50-before-load, a
session ladder, transport-first-touch, identity × first-touch — therefore probed a prefix
that had never been broken, and each of them passed.

What settled it was making the calibration timestamp its own commands. The timeline showed
the first STATUS read succeeding at 0.816 s, the full staging, the staged readback, the
PCAP_PR handover, `begin_txn`, a second STATUS read of `0x00000080` at 22.2 s — and then the
first pass-1 envelope, whose reply was a U-Boot banner.

**Three defects in this project have now hidden in the same place: a test that models the
assumption it is meant to test.** `tb_carrier_stream.v` typed `env_words[15] = 32'h13722093`
— a copy of the parameter under test — and the host gate judges frame *content*, not the
control skeleton. Both sides passed while disagreeing with each other.

## 3. What changed

### RTL

* `carrier_stream`: `parameter [31:0] IDCODE = 32'h13722093` becomes
  **`parameter [31:0] CONFIG_IDCODE = 32'h03722093`**, compared **exactly** — no masking, and
  the JTAG value is not also accepted. The rename is the point: the two identities must not
  be mistakable for each other again.
* `carrier_axil`: a stream write with no pass open now **completes with OKAY** and pulses a
  new output `stream_refused`. The word is not delivered to the engine and advances no
  position, CRC, commit or ICAP.
* `carrier_stream`: new input `protocol_fault`, new fault code **`F_PROTOCOL = 4'd11`**,
  latched **only when no fault is latched yet** — so a first verdict such as `F_CONTROL`
  survives a full drain.
* **Shim-level errors keep SLVERR**: unsupported AXI3 transactions and illegal bursts are
  protocol violations by the master, not guard refusals, and there is no verdict to read.

### The contract this creates for the host

> **AXI OKAY on a stream write means the bus transfer completed. It does not mean the
> candidate was accepted.** The host must read STATUS/FAULT after `cp.l` returns.

### Benches and tests

* `vivado/carrier/tb_carrier_chain.v` — new: the real chain, `carrier_axi3_lite` →
  `carrier_axil` → `carrier_stream` (+CRC), replaying `begin_txn` → STATUS → `start_pass1` →
  the **real 536-word envelope 0** from `tb_envelope0.hex`. Its AXI3 master is written from
  the spec and borrows no handshake assumption from the shim.
* `tb_carrier_stream.v` and `tb_carrier_integration.v` take their control skeleton from
  `tb_envelope0.hex` instead of re-typing the RTL's constants.
* `tests/test_board_uboot_axi.py` separates `JTAG_IDCODE` from `CONFIG_IDCODE`.
* `tests/test_config_idcode_agreement.py` — new: the parsed bitstream, the manifest, the
  envelope word the host builds in **every** envelope, and the RTL parameter, all compared
  against each other.

## 4. Evidence

| what | where |
|---|---|
| the run whose timeline exposed it | `evidence/calibration_noop_2026_08_12f/` |
| the chain bench reproducing it on the published RTL | `evidence/bench_chain_2026_08_13/` |
| the isolation cells that cleared the prefix | `evidence/cell_*_2026_08_12/` |

Reproduction, before the fix, identical in all four AXI shapes (single beat, stalled write,
late B, 16-beat INCR burst): **16 beats accepted, then every beat SLVERR**, `phase=P_IDLE`,
`stream_open=0`, `fault=1`, `code=2 (F_CONTROL)`, `pos=15`.

After the fix, all four accept the envelope and commit it, and three added controls hold: the
JTAG idcode at word 15 still raises `F_CONTROL`; a write with no pass open completes OKAY and
latches `F_PROTOCOL`; and `F_CONTROL` survives 520 drained writes.

## 5. What this invalidates

A rebuild re-stamps `write_bitstream`'s timestamp, so as with erratum 002 the whole
publication chain must be regenerated and re-accepted: `carrier.bit`, `carrier_eco.bit`,
`post_route.dcp`, the LFS pins, the isolation record, the ECO differential, the phenotype
manifest, `carrier_run.json`, `PRODUCTION_MANIFEST_SHA256` in `board_carrier_exec.py`, and
both production gates.

**No board time is authorised on this build until that chain is regenerated and reported.**

## 6. What is NOT claimed

* That every earlier calibration STOP was this defect. It fits all of them and is the only
  mechanism identified, but the older records lack the timeline that would prove it, and one
  of the seven used the pre-shim carrier — a different, already-corrected defect.
* That the board's copper, its supply, its PL state or its serial-port lifecycle were ever
  implicated. They were investigated at length and cleared; those investigations are recorded
  where they happened and are not rewritten here.

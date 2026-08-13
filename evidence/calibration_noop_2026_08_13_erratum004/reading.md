# Reading of the erratum-004 no-op, 2026-08-13

Ruled procedure: one attempt, no mutation, no arm, no scoring, stop on anything. It stopped.
This file interprets `record.json`; it does not add to it.

## Verdict

**STOP — `F_READBACK` (fault code 8) in pass 2 of envelope 0, with `rb_latency_valid = 1`.**

Under the ruling's own decoding table that is the second case: *the probe succeeded, so the
problem lies in the FDRO latency-equivalence assumption, the dummy-frame alignment, or the
content.* It is not the first case (`F_RBSYNC` + `valid=0`), and no reclassification is
offered for it.

## What the board did, read out of the transcript

| # | STATUS | reading |
|---|---|---|
| 8 | `0x00000080` | before the transaction: `recovery_required` only, PL freshly loaded |
| 159 | `0x00000080` | `begin_txn` |
| 161 | `0x00000980` | pass 1 envelope 0 committed (`env_committed=001`, `expect_env=1`) |
| 163 | `0x00001a80` | pass 1 envelope 1 committed (`011`, `expect_env=2`) |
| 165 | `0x000038c0` | pass 1 envelope 2 committed (`111`), **`pass1_complete=1`** |
| 167 | `0x04040082` | pass 2 envelope 0: **`fault=1`, `rb_frames_ok=0`, `rb_latency_words=1`, `rb_latency_valid=1`** |
| 168 | FAULT `8` | `readback` |

* **171 commands, zero reboots, every one got its prompt back.** `Ctrl-C` answered
  `<INTERRUPT> Zynq>`.
* **PCAP_PR handed over and restored, and the restore was READ BACK**: `0x4e00e07f` →
  `0x4600e07f` → `0x4e00e07f`, confirmed by `md.l` as the last command of the run.
* Identity verified on the writing session: `boardid 17A6`, `role verify`, PSS IDCODE
  `0x13722093`, FCLK0 50.0 MHz off a 1600 MHz PLL.
* Payload `07fbca9e…`, 6432 bytes, against manifest `38009ca9…` of the erratum-004 run.

## What is newly PROVEN, and it is not small

**The ICAP read path came up.** The engine issued a Type-1 read of the IDCODE register,
the device answered, the engine recognised its own device in the reply and measured the
pipeline at **1 word**. `rb_latency_valid=1` means the match happened; it cannot be reached
any other way.

That single fact validates, on silicon, four things this round could only argue for:

1. **The ICAPE2 word ordering, in both directions.** The command words had to be understood
   by the configuration engine for it to answer at all, and the reply had to survive the
   engine's un-swap to match `0x_3722093`. A wrong `br8` fails both ways. Erratum 004's §2
   finding is confirmed rather than merely reasoned.
2. **The `CSIB`-High turnaround.** A direction change under `CSIB` Low aborts the
   configuration; the probe read after two turnarounds and got data.
3. **The 32-clock pipeline flush is sufficient** on this device — the measured residual is
   1 word, not tens.
4. **The probe design itself**: a number no simulation could establish was taken from the
   device, and the bench had already been swept across 0…12 with 1 inside that range.

This is the first time this board has demonstrated a working ICAP **read** of any kind.

## What failed, and what cannot yet be said

`rb_frames_ok = 0` places the failure at the **first readback frame's CRC**, exactly as in
the erratum-003 run — but for a strictly narrower reason, because that run had never
established a read at all. The low half of STATUS is identical (`…0082`); the whole
difference is the telemetry saying the probe worked.

Three candidates remain, and **the evidence in hand does not separate them**:

* **the latency-equivalence assumption** (`docs/claimb_icape2_readback_sequence.md` §9
  item 1) — the FDRO frame read's pipeline may not equal the register read's, in which case
  the capture starts a few words early or late;
* **the dummy-frame alignment** — one frame of discard may be the wrong count on this
  device, or the pad may not be where UG470's wording implies;
* **the content** — the frames may be read correctly and genuinely differ, which for a no-op
  would mean the write did not land as intended.

Nothing here is a retry, a reload or a loosened rule.

## The one cheap thing that would separate them, NOT DONE

The engine's staging window (`0x43C01000`…`0x43C0118F`) still holds the 101 words it
captured for frame 0, and the board is alive at its prompt with the carrier still loaded.
Reading those 101 words is a **read-only** act that needs no reload and no second
transaction, and it answers the question directly:

* if the captured words are the expected frame **shifted by n words**, it is the latency
  equivalence, and `n` is the correction;
* if they are the expected frame **shifted by exactly 101 words**, it is the dummy-frame
  count;
* if they are neither — unrelated content, or all-ones — it is not an alignment problem at
  all and the FDRO transaction is returning something else entirely.

It is not done here because the ruling said stop, and stopping means stopping. It is offered
as the next act, for a ruling.

## Board state left behind

Alive at `Zynq>`, carrier `9f95ebd7…` still configured, PCAP_PR restored to `0x4e00e07f`.
`fault_since_reset` and `recovery_required` are latched again, so any further transaction
needs a reload or a power cycle first. Nothing was written to the fabric that a power cycle
does not clear: the load is volatile (`fpga loadb`), no `saveenv`, no flash write.

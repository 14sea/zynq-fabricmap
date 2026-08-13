# The ICAPE2 readback sequence, derived before anything is built

**Status:** derivation only, ruled offline 2026-08-13. No Vivado run, no board run. This
document is step 1 of the erratum-004 round and it is deliberately written *before* the
device model, the bench or the RTL, so that what follows can be checked against it rather
than the other way round.

The rule this round exists to obey: **the oracle may not be derived from the thing it
judges.** Errata 002, 003 and 004 were all the same defect — a bench that modelled the
RTL's assumption — so the sequence below is derived from UG470 and from prior art measured
on silicon, and every step is marked as one of:

* **[UG470]** — required by the documented configuration-interface contract;
* **[MEASURED]** — observed on this silicon by an earlier project, with the reference;
* **[DERIVED]** — follows from the two above plus this carrier's own structure;
* **[ASSUMED]** — *not* established by either, carried explicitly, and listed again in §9.

---

## 1. Why UG470's readback table is not the contract here

UG470's readback command sequences are written for **SelectMAP on a device that is being
verified**, and two of their steps are actively wrong for this carrier:

* **The bus-width detect pattern (`000000BB`, `11220044`) does not apply.** It exists so an
  8/16/32-bit SelectMAP bus can be discovered. ICAPE2 is instantiated `ICAP_WIDTH("X32")`
  and has no width to detect; the pattern would be parsed as two ordinary words. **[UG470]**
* **The SHUTDOWN / GTS / GRESTORE flow does not apply and must not be copied.** UG470's
  readback-*capture* flow shuts the device down so that flip-flop state can be captured.
  This carrier **contains the engine doing the reading**: `carrier_stream`, its CRC, its AXI
  window and the U-Boot transport all live in the fabric being read. A SHUTDOWN would stop
  the machine mid-transaction, and `GTS`/`GRESTORE` reach every flip-flop on the die. The
  repo already treats these as forbidden in a candidate write
  (`scripts/icap_sequence.py:FORBIDDEN_CMDS`), and the same prohibition applies to the read
  path for the same reason. **[DERIVED]**

  This is the point the round's instructions single out, and it is worth stating as a rule:
  *what is being performed here is configuration-memory readback of a running design, not a
  verification readback of an idle one.* Only the FDRO transaction is shared between them.

What *is* shared with UG470's table is the part that matters: a readback is a **transaction
that has to be established** — sync, RCFG, FAR, FDRO — and not a direction flip.

## 2. Word ordering on the ICAPE2 pins — the finding that changes the write path too

**The words this carrier sends are in SelectMAP order (the order they appear in a `.bit`
file). ICAPE2's `I`/`O` pins are in the bit-reversed-per-byte order.** Each byte's bits
must be reversed before the word reaches `I`, and again on the way back out of `O`:

```
SelectMAP word   AA 99 55 66   (the sync word as it appears in every bitstream)
ICAPE2 I/O       55 99 AA 66   = 0x5599AA66
```

Two independent lines of evidence, neither of them this repo's own RTL:

* **[MEASURED], and exhaustively.** `zynq-xpart` settled this on silicon rather than by
  reading: `rtl/xbus_icap.v` exposes a swap-mode register (0 none / 1 per-byte bit reverse /
  2 byte swap / 3 both) driving a directly instantiated `ICAPE2 #(.ICAP_WIDTH("X32"))` — the
  same primitive this carrier instantiates — and `sw/icap_firmware/main.c` **tries all four
  in turn and reports which one actually rewrote the fabric**, watching the edited LUT's
  output for the flip:

  ```c
  const uint32_t modes[4] = {1u, 0u, 2u, 3u};   // ICAPE2 wants per-byte bit-reverse
  for (int k = 0; k < 4; k++) {
      icap_write(n, modes[k]);
      if ((LUT_RB & 1u) == 1u) { good_mode = modes[k]; break; }
  }
  ```

  Its header records the result: *"Verified on EBAZ4205: lut_o flips 0->1, mbox reports
  winning swap mode 1."* One ordering configured the device and the other three did not.
  `docs/icap_investigation.md` adds that with the proven sequence *"swap mode 1 hits the LUT
  cleanly on the first try"*.
* **[UG470]** the 7-series MultiBoot/IPROG sequences written for ICAPE2 carry the sync word
  as `0x5599AA66` and the Type-1 CMD header as `0x0C000180`, which are exactly `br8` of the
  SelectMAP `0xAA995566` and `0x30008001`. A published constant that is the bit-reversal of
  the documented one is not a coincidence; it is the interface convention.

**Consequence for this carrier — this is new, and it is not confined to the readback.**
`carrier_top.v` wires `carrier_stream`'s `icap_din`/`icap_dout` straight to `ICAPE2.I`/`.O`,
and `carrier_stream` forwards the host's envelope words verbatim. So the **write** path has
been sending SelectMAP-order words to a port that expects the reversed order. On silicon
that means the sync word was never recognised and **the pass-2 writes were almost certainly
never accepted by the configuration engine at all**.

This is consistent with every observation in the erratum-003 calibration and changes none of
its conclusions: pass 1 never touches ICAP (only `P_PASS2`/`P_EMIT` drive it), so pass 1's
success says nothing about ordering, and a write the engine ignored would produce exactly the
readback failure that was seen. It also means the erratum-003 run is **not** evidence that
anything was written to the fabric — which, given that a partial write is the dangerous
outcome, is the benign reading of an already-benign result.

The swap is pure wiring (a permutation of 32 bits), so it costs no logic. It belongs at the
ICAP boundary inside `carrier_stream`: the CRC, the staging RAM and the host must continue to
see **SelectMAP-order** words, because the committed CRCs, the SHA-256 and the manifest are
all in that order. Swap on `I`, unswap on `O`, nowhere else. **[DERIVED]**

## 3. The pause rule, and a second defect it exposes

**[UG470]** The configuration interface is *pausable*: holding `CSIB` High stalls it with no
loss of state. What aborts a configuration is **toggling `RDWRB` while `CSIB` is Low**. So:

* a direction change must be made as **`CSIB` High → change `RDWRB` → `CSIB` Low**;
* every clock with `CSIB` Low in read mode delivers **one word and only one word**, and the
  consumer must be ready for it in that cycle.

`carrier_crc32` accepts one word every **four** cycles (`ready` is withdrawn for three while
the byte-serial engine drains). The present `P_RDBACK` holds `CSIB` Low continuously and
merely refrains from advancing `frame_word` when `crc_ready` is Low — against a real device
that **discards three of every four words**. The bench never saw it because its device model
is indexed by `dut.frame_word`, so a paused consumer was served the same word again.

This is a distinct defect from erratum 004's "there is no readback protocol", it is on the
same path, and it would have survived a correct command sequence. **[DERIVED]**
So: in the data phase, `CSIB` is Low exactly when the consumer can take a word.

## 4. The transaction, word by word

All words below are written in **SelectMAP order**; `br8` is applied on the wire (§2).
`FAR₀` is the envelope's **first target FAR** — `permitted_far(env)`, i.e. `0x00400A20`,
`0x00400C1A`, `0x00400C20` — which is the same FAR the envelope's own preamble wrote.

The envelope's trailer ends in `DESYNC`, so the engine is desynchronised when the readback
begins and the readback must establish its own sync. **[DERIVED]**

### 4a. Phase R0 — sync and the latency probe (write direction)

```
FFFFFFFF                    dummy
AA995566                    sync
20000000                    NOOP
20000000                    NOOP
28018001                    Type-1 READ  IDCODE (reg 12), 1 word
20000000  × 32              pipeline flush
```

`28018001` = `001 01 00000000001100 00 00000000001`. **[MEASURED]** — this is the register
read `zynq-xpart` used as its readback health check (`hwicap-uart.py readreg 12`), and it
returned a correct, repeatable IDCODE on this silicon.

### 4b. Turnaround, then read until the IDCODE appears

`CSIB` High ≥1 clock → `RDWRB`=1 → `CSIB` Low. Then read words and compare each against the
device IDCODE **with the revision nibble masked off** (`[27:0] == 0x3722093`): the register
read was recorded as `0x13722093` in the measurement above while the configuration stream's
IDCODE word is `0x03722093` (erratum 003). Masking accepts either and keeps the two
identities from being confused a second time.

**Why a probe at all.** The number of clocks between the last written word and the first
valid word on `O` is a pipeline latency that *no simulation can establish* — any model that
supplies it is supplying the RTL's own assumption back to it, which is the exact failure this
round exists to end. Measuring it against a **known answer the device itself produces**
removes the constant from the design: the sequencer counts clocks until the IDCODE arrives
and uses that count for the frame read. If it never arrives within 64 words, the sequencer
raises a **distinct fault code** (`F_RBSYNC`) rather than a CRC mismatch, so a board run can
tell "the read path never came up" from "the read path came up and the content disagreed".
**[DERIVED]**

### 4c. Phase R1 — the frame read transaction (write direction again)

Turn back to write (`CSIB` High → `RDWRB`=0 → `CSIB` Low), then:

```
30002001  FAR₀              Type-1 WRITE FAR, 1 word
30008001  00000004          Type-1 WRITE CMD = RCFG
20000000                    NOOP
28006000                    Type-1 READ  FDRO (reg 3), 0 words
4800025E                    Type-2 READ, 606 words
20000000  × 32              pipeline flush
```

**[MEASURED]** the FAR → RCFG → NOOP → Type-1 FDRO(0) → Type-2 shape is precisely the
sequence `hwicap-uart.py readback()` used, and its comment records that it was written to
match the register read that works.

`606 = (FRAMES_PER_ENV + 1) × FRAME_WORDS = 6 × 101` — one dummy frame plus the envelope's
five. **[UG470]/[MEASURED]** UG470 requires that the first frame returned be discarded, and
the same prior art measured it: *"the addressed frame comes out behind a ~101-word readback
pad"*.

What that pad physically is, is worth naming because it makes the discard testable: it is the
**frame buffer's** content, i.e. the last frame the FDRI burst pushed in — the envelope's
flush frame. A sequencer that failed to discard it would therefore compare the *flush* frame
against frame 0's CRC, which is a mismatch, not an accident that might pass. **[DERIVED]**

### 4d. Turnaround, then the data phase

`CSIB` High → `RDWRB`=1 → `CSIB` Low, then, with `CSIB` gated on the consumer's readiness
(§3):

1. discard `latency` words (the count measured in 4b);
2. discard `FRAME_WORDS` = 101 words (the dummy frame);
3. capture 5 × 101 words: CRC each frame, compare against the committed CRC for
   `(env, frame)`, stage it, and hand it to the host, which is what actually computes the
   SHA-256 over the fifteen frames' received bytes.

### 4e. Phase R2 — leave the engine clean

```
30008001  0000000D          Type-1 WRITE CMD = DESYNC
20000000  × 4
```

Without this the next envelope's `AA995566` would arrive at an already-synced engine, where
it is an ordinary word rather than a sync. **[DERIVED]**

## 5. Why one transaction per envelope, and why FAR₀

The FDRI burst that wrote the envelope set FAR once and let the hardware auto-increment; the
FDRO read does the same in the same direction, so five consecutive frames read from FAR₀ are
the five frames the envelope wrote, in the same order. Re-issuing FAR per frame would need
five transactions inside one watchdog phase and would test a different addressing path from
the one the write used. **[DERIVED]**

The auto-increment rule is independently checkable, and the device model implements it rather
than being told the answer: FAR is `[22]` top/bottom, `[21:17]` row, `[16:7]` column,
`[6:0]` minor; the successor of the last minor of a column is minor 0 of the next column, and
a 7-series CLB column has **36** frames. That rule, applied to the pinned target FARs,
reproduces the pinned flush FARs exactly:

| envelope | targets | successor of the last target | pinned flush FAR |
|---|---|---|---|
| 0 | `00400A20`–`00400A23` (col 24, minors 32–35) | col 25, minor 0 = `00400A80` | `00400A80` ✓ |
| 1 | `00400C1A`–`00400C1D` (col 28, minors 26–29) | minor 30 = `00400C1E` | `00400C1E` ✓ |
| 2 | `00400C20`–`00400C23` (col 28, minors 32–35) | col 29, minor 0 = `00400C80` | `00400C80` ✓ |

That the manifest's flush FARs fall out of a rule derived from the address format — including
the two that are *not* `FAR+1` — is a cross-check on the manifest as well as on the model.
**[DERIVED]**

## 6. The frame-buffer pipeline, and why five frames read back correctly

**[UG470]** FDRI writes pass through a one-frame buffer: the last frame written stays in the
buffer and never reaches the configuration memory, which is why bitstreams append a pad
frame. This carrier's envelope is *4 target frames + 1 flush frame*, and the flush frame is
taken from the **manifest's pinned content for the successor FAR**, never from the candidate
(`icap_sequence.py:build_sequence`).

So after the write: configuration memory holds the four candidate frames at the four target
FARs, and the flush FAR still holds its pinned content — which is byte-identical to the
flush frame that was written and left in the buffer. Reading five frames back therefore
returns the same five frames that were streamed, and comparing all five against the committed
CRCs is sound. The design's flush trick and the readback agree; neither had to be bent for
the other. **[DERIVED]**

## 7. What the device model must do, stated as a contract

Written here so the model can be judged against a specification instead of against the RTL:

1. speak the **wire** interface only (`CLK`, `CSIB`, `RDWRB`, `I`, `O`), and apply `br8` on
   both directions, so a stream in SelectMAP order **never syncs**;
2. parse Type-1/Type-2 packets itself and hold its own `CMD`/`FAR`/`IDCODE`/`STAT`;
3. keep a **configuration memory** keyed by FAR, and compute FAR successors with the rule in
   §5 — never a list of expected addresses;
4. model the one-frame write buffer of §6, so the last frame of a burst does not land;
5. serve an FDRO read as: `latency` idle words, then the frame-buffer pad frame, then frames
   read **out of configuration memory**;
6. refuse what the hardware refuses — no sync, no RCFG before FDRO, `RDWRB` toggled while
   `CSIB` Low (abort), an IDCODE write that disagrees;
7. **never read any signal, array or parameter belonging to the DUT.**

## 8. The negative cases this makes catchable

| defect | what the model does | how it shows up |
|---|---|---|
| RCFG missing | no read transaction is established | no data served → watchdog timeout |
| FAR wrong | serves the frames living at that FAR | CRC mismatch, `F_READBACK` |
| FDRO length wrong | serves exactly what was asked for | short → timeout; long → trailing junk |
| dummy frame not discarded | pad = the flush frame, then the five | frame *n* compared against CRC *n−1* |
| dummy discard off by one frame | as above, one frame late | last frame runs off the end → timeout |
| flush clocks/words too few | data is not ready yet; idle words are served | misaligned capture → CRC mismatch |
| direction switched with `CSIB` Low | abort: desync, transaction dropped | no data → timeout |
| word ordering not `br8` | the sync word is never recognised | never syncs → `F_RBSYNC` |

## 9. Carried assumptions — the honest list

1. **[ASSUMED]** The read pipeline latency measured on the IDCODE probe equals the latency of
   the FDRO frame read. If it does not, the capture is misaligned by the difference and every
   frame CRC fails — the same symptom as today, but now with the measured latency held in the
   engine and the staged 101 words readable, so the offset is diagnosable rather than mute.
2. **[ASSUMED]** 32 NOOPs is enough pipeline flush after a read command. UG470 shows 32 in
   its readback sequences; the true minimum is not published. 32 clocks costs 0.64 µs of a
   20.97 ms watchdog phase, so there is no reason to trim it.
3. **[ASSUMED]** Pausing an in-flight FDRO burst with `CSIB` for milliseconds at a time (the
   host's per-frame copy) preserves the transaction. UG470 documents the pause; it does not
   quantify a limit.
4. **[ASSUMED]** The device IDCODE register returns `0x13722093` on this die. The masked
   compare accepts `0x03722093` as well, so only a third value would break the probe.
5. **[UNCHANGED, NOT RE-DERIVED]** everything the write path does before `P_RDBACK`, other
   than the `br8` correction of §2.

## 10. What was built against this, and what it found

Written after the fact; §§1–9 above were not edited to match the result.

`vivado/carrier/icape2_model.v` implements §7 and `tb_icape2_model.v` pins it with a literal
known-answer trace and the eight negative cases of §8, driven word by word by the bench with
`carrier_stream` **not instantiated**. `tb_carrier_readback.v` then points the DUT at it.

**The published RTL scored 1,525 failures**: 802 words read, all of them idle; `E_ABORT` from
the direction flip; and **zero frames committed to the fabric** — the write had never synced
either, exactly as §2 predicted. Erratum 004's diagnosis was right and narrower than the
truth.

The sequencer is now §4 as written. `scripts/run_carrier_benches.sh` runs it at read
latencies 0, 1, 3, 5, 7 and 12 against devices demanding 32, 40, 48 and 64 flush clocks —
thirteen bench runs, no failures — and `scripts/mutate_carrier_readback.sh` breaks it ten
ways and requires the bench to notice each one:

| mutation | how it dies |
|---|---|
| RCFG removed | `F_READBACK`, device reports `E_NO_RCFG` |
| FAR + 1 | `F_READBACK` — those are not this envelope's frames |
| FDRO length 505 instead of 606 | `F_READBACK` — the stream runs out |
| dummy frame not discarded | `F_READBACK` — the flush frame meets frame 0's CRC |
| dummy discard one frame long | `F_READBACK` — runs off the end |
| `RDWRB` moved with `CSIB` Low | `F_RBSYNC`, device reports `E_ABORT` |
| `br8` removed | `F_RBSYNC` — never syncs |
| measured latency pinned to 0 | `F_READBACK` — capture starts three words early |
| flush 32 → 2 clocks | **survives, and should** — see below |
| flush 32 → 2 against a 64-clock device | `F_RBSYNC` — past the probe's cap |

The expected survivor is the round's one pleasant surprise. Shortening the flush is absorbed,
because the probe then measures a correspondingly longer latency: **the flush length is not
load-bearing precisely because the latency is measured.** What *is* load-bearing is the
probe's 64-word cap, and the last row shows it refusing cleanly rather than reading rubbish.

Two defects beyond §2 and §3 turned up while building it, both recorded in
`evidence/bench_readback_2026_08_13/record.json`: an unconditional `phase <= P_IDLE` that
overwrote the end-of-envelope `F_READBACK` refusal (leaving `fault_code` set and `fault`
clear), and a host `FAULT_NAMES` table missing `F_PROTOCOL`.

## 11. Open decision for the rebuild, not taken here

The measured latency is currently visible only inside the engine. Surfacing it — STATUS bits
`25:18`, which are reserved and read zero today — would let a board run report *how far* the
read pipeline actually is, and would turn assumption 1 from a guess into a measurement in the
very first calibration. It touches the AXI register map, the host decoder and the tests that
pin the reserved bits, so it is **not** done in this round; it is put here to be ruled on
before the erratum-004 carrier is built.

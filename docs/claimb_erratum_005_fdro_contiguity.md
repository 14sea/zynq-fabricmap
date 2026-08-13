# Erratum 005 — an FDRO read cannot be back-pressured with CSIB

**Status:** diagnosed on silicon 2026-08-13 from the erratum-004 no-op and its staging dump,
ruled the same day, and rebuilt offline. The erratum-004 carrier stays published; what it
fixed it fixed, and what it did not is stated here.

> **SUPERSEDED IN PART, 2026-08-13** — see
> [`claimb_erratum_005_correction_2026_08_13.md`](claimb_erratum_005_correction_2026_08_13.md).
> Two statements below are overclaims: that UG470's way to run the interface non-contiguously
> is to stop CCLK *rather than* toggle CSIB (UG470 documents both), and that a CSIB gap in an
> FDRO read therefore aborts (AMD defines the abort as RDWRB changing while CSIB is asserted;
> a plain gap is not shown to abort). The correct reading is that `0xFFFFFF5B` is *consistent
> with* an abort status, that the gapped read is *highly correlated* with the failure but not
> uniquely proven as its cause, that erratum 005 is a *conservative* fix removing that
> uncertainty, and that the model's `E_FDRO_GAP` is an adversarial contract rather than a
> reproduction of silicon behaviour. §4's attribution of the per-frame architecture is also
> corrected there. The engineering, the artifacts and their digests are unaffected.

**Scope:** the readback's *pacing* only. Nothing about the target, the seed, the ceiling, the
cap, the masks, the fitness, the train/holdout split, the A/B rules, the floorplan or the map
moves. The write path is untouched.

Additive, like 001–004: no earlier record is rewritten.

---

## 1. What the board returned

The erratum-004 no-op stopped in pass 2 of envelope 0 with `F_READBACK`, and — this is the
part erratum 004 was built to make possible — with **`rb_latency_valid = 1`**. The probe had
worked: the engine read the IDCODE register, recognised the device and measured the pipeline.
The failure was after that.

One authorised read-only dump of the staging window, repeated once with the reply kept whole
(`evidence/calibration_noop_2026_08_13_erratum004/`):

> **All 101 words are `0xFFFFFFDA`.**

The engine stores `br8(icap_dout)`, and `br8(0x5B) == 0xDA` exactly, so the ICAPE2 `O` pins
carried **`0xFFFFFF5B`**, 101 times.

That is not frame data and it is not misaligned frame data. Both searches the ruling asked
for came back empty:

* no exact match in any of the **506** contiguous 101-word windows of the expected 606-word
  sequence, and **zero** matching words at every one of them — histogram `{0: 506}`;
* no exact match against any of the **5,144** frames of `carrier.bit`.

## 2. What it is

`0xFFFFFF5B` has the shape of UG470's **abort status word**: the upper 24 bits all 1, and in
the low byte `CFGERR_B=0`, `DALIGN=1`, `RIP=0`, `IN_ABORT_B=1`. An abort status word is not
part of the configuration data stream and is **not bit-swapped** — which is why the engine's
unconditional un-swap turned it into `0xFFFFFFDA` on the way into the staging RAM.

**The configuration had been aborted, and the engine spent the whole burst reading the
device's complaint about it.**

## 3. Why — and why simulation agreed with the defect

`carrier_stream`'s erratum-004 readback pulled `CSIB` Low for one clock per word and High for
three, because its consumer was `carrier_crc32`, which is byte-serial and accepts one word
every four cycles. The engine was using `CSIB` as back-pressure.

* **[UG470]** the documented way to run the configuration interface non-contiguously is to
  **stop CCLK**, not to toggle `CSIB`.
* **[PG134]** AMD's own AXI HWICAP does **not** stop the ICAP stream when its read FIFO
  fills — which is precisely why that core can overflow, and `zynq-xpart` measured exactly
  that overflow on this silicon.

So a gap in an active FDRO read is not a pause. The device aborted, and from then on drove
the abort status word.

**Why no test caught it, for the fifth time in the same shape:** `icape2_model` modelled
pausing as free in *both* directions. It was written that way because the WRITE path depends
on pausing between frames — the frame-staged design's whole premise — and the read path was
never considered separately. A model that permits the defect will agree with an engine that
commits it.

The model now refuses it: a `CSIB` gap during an **active** FDRO read aborts, and the device
drives `0xFFFFFF5B` raw until a fresh sync. "Active" begins when the first data word is
*served*, not at the FDRO header — a window that opened at the header would make the legal
write-to-read turnaround an abort, and the model's own bench caught that first attempt.
The rule is deliberately asymmetric: a gap during an FDRI **write** is still a legal pause.
The ruling scopes this to FDRO and nothing measured says otherwise about the write path.

Under the corrected model the published erratum-004 RTL scores **1,527 failures** with device
error `E_FDRO_GAP`, 609 words read of which 603 idle, and 4 frames ever committed. The
simulation now fails for the same reason the silicon did.

## 4. What replaces it

**Five independent, contiguous FDRO transactions per envelope — one per frame.**

```
for each frame f:
    sync, NOOP, NOOP, Type-1 read IDCODE, 32 NOOPs      (the latency probe)
    turnaround -> read CONTIGUOUSLY until the IDCODE arrives; the count is the latency
    turnaround -> FAR(f), CMD=RCFG, NOOP, FDRO(0), Type-2(202), 32 NOOPs
    turnaround -> read 202 words with CSIB Low and RDWRB High on EVERY clock:
                  discard latency + 101 (the dummy frame), then
                  101 words straight into the staging RAM, one word per clock
    turnaround -> CMD=DESYNC
    then, with the ICAP idle and desynced: CRC the frame OUT OF THE RAM and compare
    then: the host reads the same RAM and acknowledges
```

The decisions inside that, and why:

* **A RAM write port keeps up with ICAP; a byte-serial CRC cannot.** The burst is absorbed
  first and checked afterwards. Nothing back-pressures the configuration engine, which is the
  whole point of this erratum.
* **Per frame, not per envelope.** A single 606-word burst would need a 505-word buffer,
  which means either a BRAM — and `build_carrier.tcl` adds every primitive to `pb_logic`, so
  the pblock would need a RAMB range and the floorplan was RULED FINAL on 2026-08-11 — or
  about 256 LUTs of LUTRAM, taking slice occupancy from 305/400 to roughly 370/400. It would
  also change the host protocol (one window, one `cp.l 0x1f9`, one ack) and every test bound
  to it. Per-frame reuses the existing 101-word staging RAM, the existing host protocol and
  the existing floorplan, and costs a 15-entry FAR ROM.
* **One FAR set per `sync..DESYNC`.** This is the shape the project already knows is safe:
  `scripts/icap_sequence.py` records that several FAR sets inside one envelope mis-commit the
  buffered frame and corrupt the array. Five transactions with one FAR each is not that
  shape.
* **The latency is measured per frame, immediately before the burst that uses it.** The
  erratum-004 measurement of 1 word is **void**: it was taken through a gapped read. Measuring
  it contiguously, in the same sync session as the burst it applies to, is as close as the
  assumption can be brought to its use.

## 5. What is still assumed

1. **[ASSUMED]** a Type-1 register read's pipeline latency equals an FDRO frame read's. This
   is erratum 004 §9 item 1, unchanged in kind and narrowed in distance: same transaction,
   same sync session, both contiguous.
2. **[ASSUMED]** one dummy frame is the right discard for a 2-frame FDRO read. UG470 requires
   a dummy frame; `zynq-xpart` measured "the addressed frame comes out behind a ~101-word
   readback pad" through the AXI HWICAP.
3. **[ASSUMED]** a gap in an FDRI *write* remains a legal pause. Untested either way; the
   frame-staged write depends on it.

## 6. What is NOT claimed

* That the readback content is right. It has still never been read.
* That "the dump matched nothing" means the frames differ. It means the 101 captured words
  are not any shift of the expected stream — **narrow**. It does not exclude an interface
  that was being restarted repeatedly and returned the same abort word each time, which is
  in fact what the abort status says happened.
* That erratum 004 is invalidated. Its word ordering, its turnaround rule, its flush, its
  probe and its telemetry are what made this diagnosable: without `rb_latency_valid = 1` the
  failure would again have been mute.

# Erratum 004 — the readback abstraction is falsified

**Status:** diagnosed on silicon 2026-08-13, ruled by the user the same day. **No fix
implemented yet.** The erratum-003 carrier stays published; it is not superseded, because
what it fixed it fixed and what it did not is stated here.

**Scope:** `carrier_stream`'s `P_RDBACK` phase only. Nothing about the target, the seed, the
ceiling, the cap, the masks, the fitness, the train/holdout split or the A/B rules moves.

Additive, like 001–003: no earlier record is rewritten.

---

## 1. What the calibration established

`evidence/calibration_noop_2026_08_13_erratum003/` — one no-op on the erratum-003 carrier,
from a fresh power-on, 171 commands with a full timeline.

**Two things are now proven on hardware, and both are new:**

* **Pass 1 works end to end.** All three envelopes streamed and were accepted; after the
  third, STATUS read `0x000038c0` — `pass1_complete = 1`, `env_committed = 0b111`. This is
  the first time the board has ever accepted a real envelope. Erratum 003's `CONFIG_IDCODE`
  correction is validated on silicon.
* **A guard refusal is now survivable.** Zero reboots, no command without a prompt, `Ctrl-C`
  answered `<INTERRUPT> Zynq>`, and the PCAP_PR handover was restored and **verified by a
  read** (`0x4600e07f` → `0x4e00e07f`). Under the old SLVERR semantics this fault would have
  been a data abort, a `panic()` and a boot banner, and the run would have been lost with its
  evidence. Erratum 003's other half did exactly what it was built for.

**And one thing is refuted:** pass 2 of envelope 0 stopped with STATUS `0x00000082` and
FAULT `0x8`, `F_READBACK`.

## 2. The root cause, read out of the source

`rb_frames_ok = 0` in that STATUS places the failure precisely: it is the **per-frame CRC
comparison at `carrier_stream.v:555`**, on the **first** readback frame — not the fifteen-frame
accounting at `:528`. Nothing was ever read back correctly, so this is not a mismatch in one
frame's content.

The reason is that **the module does not implement an ICAP readback at all**:

* On entering the readback it sets `icap_rdwrb <= 1'b1` (`:564`) and immediately treats
  `icap_dout` as frame data (`crc_source = (phase == P_RDBACK) ? icap_dout : word_data`,
  `:241`).
* `grep -niE "RCFG|FDRO"` over `carrier_stream.v` returns **nothing**. There is no sync word,
  no RCFG command, no FAR write and no FDRO read header on the read path. `W_SYNC` and
  `W_DUMMY` exist only in the write-side control ROM.
* There is no dummy-frame discard.

UG470's readback procedure requires an **FDRO read transaction to be established first**, and
**a whole dummy frame is returned before valid data**. Flipping RDWRB and sampling `O` returns
whatever the configuration engine happens to present, which is not the frame.

This is precisely the assumption the RTL's own comments flagged as unprovable in simulation
and deferred to calibration. **The calibration has now ruled on it.**

## 3. Why no test caught it

The same shape as errata 002 and 003, a fourth time: **the benches model the readback the way
the RTL implements it.** A device model that hands back the words the DUT just staged will
agree with any read protocol at all, including none. Nothing on the host side judges the ICAP
command sequence, because the host never sees it.

## 4. What the next round must build (ruled 2026-08-13, not yet started)

An actual ICAP readback sequencer:

* establish and pin the RCFG / FAR / FDRO sequence that applies to **ICAPE2** specifically;
* handle the packet-flush latency, the **first dummy frame**, and then the five valid frames;
* the FAR read back must be **each envelope's first target FAR**;
* verify the command ORDER against an **independent device model** — one that does not simply
  echo the DUT's own stage buffer;
* tests must catch: a missing RCFG, a wrong FAR, a wrong FDRO length, and a dummy-frame
  offset of exactly one frame;
* the host still computes the SHA-256 itself, from the fifteen frames' actual received bytes.

Then a new erratum-004 carrier: Vivado rebuild, the full publication chain, and a fresh no-op
ruling.

## 5. Board state

The board is alive at U-Boot with the erratum-003 carrier still configured, but
`fault_since_reset` and `recovery_required` are **latched**. Any future carrier test needs a
reload or a power cycle first. No action is needed now.

## 6. What is NOT claimed

* That the readback content is wrong. It was never read.
* That anything in errata 001–003 is invalidated. Pass 1, the transport, the validator, the
  CRC, the commit path and the refusal semantics are all now hardware-proven.
* That the fix is known. The sequence above is UG470's requirement, not a tested design.

---

## 7. UPDATE, same day: the offline round happened

Appended, not rewritten — §§1–6 stand as the diagnosis they were.

`docs/claimb_icape2_readback_sequence.md` derives the sequence and
`evidence/bench_readback_2026_08_13/` records the round. Three things changed:

1. **§4's list was built**, and the sequencer now measures the read pipeline against a known
   answer (a Type-1 IDCODE read) rather than pinning a constant no simulation can establish.
   A new fault code `F_RBSYNC` separates "the read path never came up" from "it came up and
   disagreed" — the ambiguity that cost this erratum a board round.
2. **§2's diagnosis was right and too narrow.** Against a device model that does not echo the
   DUT, the published RTL read 802 words of which 802 were idle, aborted the configuration on
   the direction flip, and **committed zero frames to the fabric**: `ICAPE2`'s `I`/`O` bus is
   bit-reversed within each byte and the carrier was feeding it SelectMAP-order words, so the
   *write* had never synced either. The erratum-003 calibration is therefore not evidence
   that anything was written to the fabric — which, for a project whose worst outcome is a
   partial write, is the benign reading of an already-benign result.
3. **§3's "why no test caught it" is closed.** `tb_carrier_stream` and
   `tb_carrier_integration` no longer contain a device that hands back the DUT's staging
   buffer; both now instantiate `icape2_model`, and a provenance test changes one word of the
   fabric between the write and the readback — which a DUT reading its own buffer cannot
   fail.

Still true: no Vivado, no bitstream, no board time. §4's closing sentence — a new carrier,
the full publication chain and a fresh no-op ruling — has not been done.

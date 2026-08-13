# Correction to erratum 005 — two overclaims, and what the evidence actually supports

**Status:** additive correction, ruled by the user on review, 2026-08-13. It supersedes the
named statements in
[`claimb_erratum_005_fdro_contiguity.md`](claimb_erratum_005_fdro_contiguity.md), in
`gate_runs/claimb_round1_carrier_2026_08_13_erratum005/README.md`, in `icape2_model.v`'s
comments, in `carrier_stream.v`'s `P_RDBACK` comment, and in the bodies of commits
`e1e663d` and `9da33c8`.

**No Vivado run, no rebuild, no change to any of the 13 pinned build sources, and no change
to any artifact or its digest.** The engineering of erratum 005 is accepted; what is
corrected is what the record claims to have PROVEN.

---

## 1. The two overclaims

### 1a. "UG470's way to run the interface non-contiguously is to stop CCLK, not to toggle CSIB"

**Wrong.** UG470 documents non-contiguous configuration as available **either** by
de-asserting `CSI_B` **or** by stopping `CCLK`. Raising `CSI_B` between words is a documented
way to pause the interface, not a documented way to break it.

This sentence appears, in one wording or another, in erratum 005 §3, in the run README, in
`icape2_model.v` and in `carrier_stream.v`'s `P_RDBACK` comment. It should not have been
written as a citation, because it is not what the document says.

### 1b. "so a gap in an active FDRO read is not a pause; the device aborted"

**Not established.** The abort condition AMD defines is a change of `icap_we`/`RDWRB` **while
`icap_ce`/`CSIB` is asserted** (PG134, Abort Status Register). Nothing in UG470 or PG134
says that a plain `CSIB` gap inside an FDRO read must abort a configuration. The observed
abort is consistent with the gapped read; it is not proven to be caused by it.

What the second citation *does* support is narrower and still useful: **AMD's own AXI HWICAP
does not stop the ICAP stream when its read FIFO fills**, which is why that core can
overflow. That says a reader must be able to absorb the stream. It does not say what the
device does to a reader that cannot.

## 2. What the evidence actually supports

Stated as a chain, with each link at its real strength:

1. **`0xFFFFFF5B` is CONSISTENT with an abort status word.** Upper 24 bits all 1; low byte
   decodes as `CFGERR_B=0`, `DALIGN=1`, `RIP=0`, `IN_ABORT_B=1`. `br8(0x5B) == 0xDA` exactly
   accounts for the `0xFFFFFFDA` the engine stored. **Consistent with**, not "is".
2. **The 101 captured words are not any shift of the expected stream** — zero matching words
   at every one of 506 offsets, and no match among the 5,144 frames. This is a **narrow**
   fact: it excludes misalignment of correctly-read data. It does not exclude an interface
   that was restarted repeatedly and returned the same word each time.
3. **The gapped FDRO read is HIGHLY CORRELATED with the failure**, and it is the one thing in
   that read path that is both unusual and under our control. It is **not uniquely proven**
   to be the root cause. Other candidates the evidence does not exclude include the
   register-read/FDRO latency-equivalence assumption and the dummy-frame count.
4. **Erratum 005 is therefore a CONSERVATIVE FIX**: it removes an uncertainty from the design
   rather than repairing a proven defect. Absorbing the burst contiguously is what a reader
   must do if the stream cannot be stopped, it costs +1 LUT and it makes the next board
   result interpretable. That is the whole claim.
5. **`icape2_model`'s `E_FDRO_GAP` is an ADVERSARIAL CONTRACT, not a reproduction of silicon
   truth.** The model refuses a gap because the design must not depend on a device tolerating
   one — the same reason the model refuses a missing RCFG. It is a rule the design is held
   to, and the reader should not take a bench that enforces it as evidence that the silicon
   enforces it.

Consequently `E_FDRO_GAP` firing on the old RTL (1,527 failures) demonstrates that **the
design violated the contract**. It is not, and was written as though it were, a demonstration
that the contract is what the device implements.

## 3. Provenance of the per-frame architecture

Erratum 005 §4 and commit `9da33c8` say the per-frame shape was "ruled by the user after the
trade was put to them". **That does not match the history.** The correct record:

> The per-frame, contiguous-FDRO architecture is **accepted at this review, 2026-08-13**, as
> the engineering approach for erratum 005.

The trade-off analysis behind it stands as written — a single 606-word burst needs a 505-word
buffer, hence a BRAM and a RAMB range in a floorplan that was ruled final, or ~256 LUTs of
LUTRAM and a host-protocol rewrite — but the analysis was the author's, and the acceptance is
dated here, not earlier.

## 4. What is NOT corrected, and why

* **The artifacts.** `carrier.bit` `d93c59ad…`, the ECO, the checkpoint, the manifest
  `400a1e9c…` and every other digest are unchanged. Nothing about them depended on the
  claims above.
* **`carrier_stream.v`'s comment.** It is one of the 13 build sources pinned by
  `carrier_build.json`, and `gate_carrier_base` requires each to equal its HEAD blob.
  Editing it would invalidate the published run over a comment. It is superseded here
  instead, and the next carrier that is built for another reason should carry the corrected
  wording.
* **The two commit bodies.** History is not rewritten; they are named at the top of this
  file so a reader arriving from `git log` finds the correction.
* **The design.** Contiguous absorption is still the right thing to build, for the reason in
  §2 item 4.

## 5. The consequence for the next board run

Erratum 005 must be read as a **hypothesis under test**, not as a fix whose success is
already known:

* if the no-op passes, the gapped read was the fault or was masking it, and the record should
  say which of those it can distinguish (it cannot distinguish them by itself);
* if it fails again with `rb_latency_valid = 1` and a fresh dump of abort status words, then
  contiguity was not the cause and the remaining candidates in §2 item 3 move to the front;
* if it fails with `F_RBSYNC`, the read path did not come up at all this time, which would be
  a new finding against a design whose probe demonstrably worked on 2026-08-13.

# Claim B — findings, and why the programme is paused

**Status: Claim B's board programme is PAUSED under a stop-loss that was committed to in the
2026-08-20 session ruling before the review that triggered it.** That ruling and the completed
review first entered this repository together in commit `dd7721d`; Git history alone therefore
does not independently establish their order. Claim B has **zero data points** and its
preregistration is still **DRAFT** (§6 budget unfrozen, §10 freeze never performed).

This document is the standalone statement of what was established, what was not, and why the
programme stopped where it did. It is written so that the three kinds of statement stay
separate and stay labelled:

* **§2 OBSERVED** — measured on silicon or derived mechanically from a pinned artifact. Each
  entry names where it comes from.
* **§3 INFERRED** — what follows from §2, with the strength of the inference stated.
* **§4 NOT TESTED** — things that were never measured. Listed so that they are not later
  mistaken for either of the above.

Nothing in §3 may be cited as if it were §2, and nothing in §4 may be cited at all except as an
open question.

---

## 1. What Claim B was, and what was being built

Claim B, as preregistered in `zynq-autoehw` and restated in `docs/claimb_contracts.md`:

> A device-local map (learned or inherited inside a constrained island) can guide later hardware
> evolution more safely than raw bit mutation.

Testing it needs a loop: write a candidate into a constrained island of configuration memory,
confirm the write is what the host gate authorised, measure the resulting phenotype, and score
it against a random-safe control arm. The instrument built for this is the **carrier** — an
in-fabric design that receives an envelope of configuration frames over AXI from U-Boot, writes
them through ICAPE2, reads them back through the same engine, and compares.

The loop never closed. It stopped at the third step: **the carrier's own readback**.

## 2. OBSERVED

### 2.1 The write lands, and it was confirmed twice by an instrument outside the fabric

Two separately established fault-state runs on 2026-08-20 —
`evidence/location_sweep_2026_08_20/` and `evidence/location_reproduction_2026_08_20/`, with
different `plmark`s — both returned the verdict `WRITE_LANDED_AT_THE_INTENDED_FAR`. They used
the same JTAG method; this is replication across fault instances, not an independent method.

In each run, by JTAG readback with sixteen pinned positive controls:

| | run 1 | run 2 |
|---|---|---|
| controls exact at the same FAR | **16 / 16** | **16 / 16** |
| controls re-derived against the carrier bitstream | 16 / 16 | 16 / 16 |
| words of `0x00400A20` matching the candidate | **101 / 101** | **101 / 101** |
| frame sha256 at `0x00400A20` | `15cb05e6…69a5bbe7` | `15cb05e6…69a5bbe7` |

That sha256 is also what `analyse_ddr_capture.py` derives independently from the frozen
authority (F3). `readback_audit.json` records `landings_verified: 2`.

**Within this frozen JTAG method, the candidate was observed at the frame it was addressed to in
two separately established fault states.** That replicated location result is an input to
everything below; an independent readback method was not tested (§4).

### 2.2 The carrier's internal readback faults on the candidate

In the same transaction that wrote the candidate, the engine's readback of `0x00400A20` staged
101 words that did not CRC-match the committed CRC for that frame, and the staged words were
**all zero** (F4: O3 and O4 in
`evidence/location_sweep_2026_08_20/fault/ddr_slot0_shutdown_read.json` and
`evidence/location_reproduction_2026_08_20/fault/ddr_slot0_shutdown_read.json`; 101 words, 0
non-zero, sha256 `0441772f6655…6d7b8de9` — equal to the *base* frame at that FAR, unequal to the
candidate, byte-identical across both fault states).

The fault is `F_READBACK` (code 8), **not** `F_RBSYNC` (12) and **not** `F_BYTECOUNT` (10). The
fault STATUS `0x04040082` decodes to `rb_latency_words = 1`, `rb_latency_valid = 1` — the same
latency the passing run measured (F5). So the read path came up, the device named itself, and
the CRC consumed exactly `BYTES_PER_FRAME`. **101 words were staged and CRC'd, and they were the
wrong 101 words.** This is not a timeout, a sync failure or a short read.

### 2.3 The interlock's record of success covers only degenerate all-zero content

This is the finding that limits everything the carrier has ever demonstrated.

* **F1** — all fifteen frames of the write envelope are byte-identical and **all zero**
  (`gate_runs/claimb_round1_carrier_2026_08_13_erratum006/phenotype_manifest.json`; one distinct
  content, `0441772f6655…6d7b8de9`, zero non-zero words). 4,716 of the device's 5,144 frames are
  also all zero.
* **F2** — the no-op writes that same blank content (`scripts/board_claimb_known_answer.py:104`;
  `gate_runs/claimb_round1_known_answer_2026_08_14/known_answer.json` records
  `restore.actual_init = 0x0000000000000000`).
* **O5** — the erratum-006 no-op **passed**: `rb_frames_ok = 15`, `configuration_valid = 1`,
  fifteen frames verified
  (`evidence/known_answer_2026_08_14_erratum006/record.json`).

Across the seven committed no-op transactions in §2.4, every time the interlock was satisfied
on silicon, **the content it verified was all zero**. O5 names that degenerate positive-control
shape; it is a content class, not a claim that only one transaction passed.

* **F3** — the candidate differs from blank in exactly **two words per frame** (word 50 is the
  recomputed ECC, word 51 carries the INIT bits;
  `evidence/read_side_facts_2026_08_20/facts.json`).

**The interlock has never verified non-blank content. In both landing-verified fault instances,
it faults when asked to verify the candidate.**

### 2.4 The W2 audit — scoped exactly as the audit itself scopes it

`scripts/audit_readback_evidence.py` 2.1.0, over a **frozen and closed** inventory (66 pinned
files; discovery reproduces the freeze in both directions), with the criterion: *the expected
frame is non-blank AND the returned words equal it exactly AND it is the frame whose FAR was
requested*. Evidence: `evidence/read_side_facts_2026_08_20/readback_audit.json`.

```
engine_transactions          7
engine_frames              105
engine_nonblank_frames       0
engine_frames_expected_blank 105
staging_copies               7
staging_nonblank_erratum006  0
hits                         0
verdict  NO_NONBLANK_READBACK_IN_THE_FROZEN_COMMITTED_INVENTORY
```

Two precisions that must travel with those numbers:

1. **All 105 engine frames were *expected* to be blank**, because every one of them is a no-op
   step writing the blank restore payload. In those seven completed transactions the
   erratum-006 engine read path was **never asked** for non-blank content. The candidate
   transactions did ask for non-blank content, but stopped at `F_READBACK`; their **staging
   copies** owed the candidate. Three were taken after the candidate round faulted and returned
   blank.
2. **The inventory does contain non-blank content, from superseded carriers**, which is why the
   criterion has to be *same-FAR whole-frame exact*: the erratum-004 abort word `0xFFFFFFDA`
   ×101, and the erratum-005 dump that was **bit-exact against the device stream at an address
   other than the one requested**.

The audit's own reading, and the scope is part of the finding:

> So F2 is general **ACROSS THIS INVENTORY**: within it, this frame-data path has never been
> demonstrated to deliver non-blank configuration data correctly. **It is not a claim about runs
> that were never recorded.**

**This verdict stands unchanged.** Nothing later in this document revises it.

### 2.5 The 2026-08-20 read-side experiment returned B1

A diagnostic no-op run into an already-loaded, already-faulted carrier, with no reload,
completed **15/15** with `configuration_valid = 1`, `fault = 0`, and the host stopping on the
still-latched `recovery_required`. That is the **pre-registered conditional negative** for strict
H-STALE, not a refutation of it: the experiment deliberately performs no R4/JTAG read between the
fault and the second transaction, so its pre-second-write candidate content is a reproduced
prior, not a same-instance observation. Evidence:
`evidence/read_side_divergence_2026_08_20/noreload_noop/record.json` and the mechanically
reconstructed `evidence/read_side_divergence_2026_08_20/reading.md`.

**H-PAD, H-ADDR and H-IDLE remain inseparable** under the frozen carrier's telemetry (§3.3).

### 2.6 The JTAG path reads only after a device-wide startup transition

R3-control measured, **for this fixed probe sequence on this device**: without `JSHUTDOWN` a
fresh load with no transaction returns **0/16**; the same controls with it read **16/16**
(`docs/claimb_r4_protocol.md` §1, which is explicit that this is a fact about this instrument and
this part, not a general law).

The emitted sequence (`scripts/probe_jtag_config_read.py`) is
`JSHUTDOWN → runtest 12 → JSTART → runtest 2000 → RCRC envelope → JSHUTDOWN → runtest 12` and
then, per FAR, `RCFG → FAR → FDRO → CFG_OUT → DESYNC`. `claimb_r4_protocol.md` §2 requires **one
FAR per child process**, so a seventeen-read acquisition performs **seventeen** such transitions.
Each child's script ends at the readback prefix's `JSHUTDOWN` with **no trailing `JSTART`**.

### 2.7 The arming interlock is enforced in fabric

`vivado/carrier/carrier_scorer.v:26` records that `configuration_valid` **"is NOT a software
bit"**; `:103` freezes and disarms when it is absent. The arm conjunct
(`docs/claimb_carrier_design.md:217`) is

> arm ⟺ `gate_verdict.writable` ∧ `configuration_valid` ∧ `¬recovery_required` ∧
> `candidate_sha256 == readback_sha256`

and the same section records that **`carrier_scorer` enforces it in hardware**. A host write to
CTRL (AXI offset `0x2000`) with bit 6 set (`CTRL_ARM = 0x40`) is a request the PL refuses unless
its own readback compare has raised `configuration_valid`.

### 2.8 Cost of a JTAG acquisition

Both executed 17-read hit acquisitions record **1.8 s**
(`evidence/location_sweep_2026_08_20/reading_steps_2_to_5.md`,
`evidence/location_reproduction_2026_08_20/reading.md`). The budget figure is ≈2 s; the two
independently measured per-read rates (0.1007 and 0.125 s/frame) bracket seventeen reads at
1.7–2.1 s.

## 3. INFERRED

### 3.1 The blocker is the readback interlock, not the write — strong

§2.1 and §2.2 concern the same two fault instances and the same candidate writes, observed by
two paths: the later JTAG acquisition finds the candidate in the frame, while the carrier's
readback during the faulting transaction stages blank. Combined with §2.3 (the interlock's only
successful content class is degenerate), the inference is direct for these tested candidate
transactions: **what fails is the carrier's internal read-and-compare path, not delivery of
these candidates to configuration memory.**

### 3.2 A silicon-wide impossibility is less credible than it was — weak, and a change of credence only

An audited read of prior art in a sibling tree (`zynq_xpart/scripts/hwicap-uart.py`, and its
`docs/icap_investigation.md`) supports only this weak proposition:

> On the **same device type**, on **another board instance**, and with a **different carrier and
> a different (AXI HWICAP) implementation**, an FDRO stream has been reported to contain
> recognisable non-blank LUT-INIT content.

Its limits are as load-bearing as the claim:

* it is a **single sentence of prior-art prose with no pinned evidence record**;
* there is **no stable same-FAR whole-frame exact capture** — a full frame is pad (~101) + frame
  (101) = 202 words against a read FIFO of ~128, the controller does not back-pressure ICAP, and
  words past the FIFO are lost;
* chunked draining reaches further but the FDRO chunk boundary **drifts run-to-run** (~18 words
  between two back-to-back reads), so that prior art's own conclusion is that a clean automated
  before/after whole-frame compare **is not reliable**.

Therefore, and these bounds are not optional:

* it **does not** answer W2, and **W2's frozen-inventory verdict (§2.4) is unchanged**;
* it **does not** establish that the fault lies outside the silicon or the configuration engine,
  and no such statement may be made on its authority;
* it **does** make a *silicon-wide impossibility* — the reading in which this part's
  configuration engine simply cannot return non-blank frame content — **less credible, on the
  strength of this prior-art self-report**. That is a change in credence, not a fact;
* it is **consistent with**, and lends weak prior-art support to,
  `claimb_r4_protocol.md` §1's refusal to generalise "readback requires a shutdown": that path
  is reported to have returned frame content with **no `JSHUTDOWN` at all**, requiring
  `PCAP_PR=0` instead. It supports only the narrower reading that R3-control's measured shutdown
  requirement belongs to this fixed JTAG probe on this part, not a silicon-wide rule.

It is a **precedent, not an artifact**, and it is not an oracle.

### 3.3 Three mechanism hypotheses remain inseparable — strong

Under the frozen carrier and its current telemetry, nothing distinguishes **H-PAD** (a discarded
pad frame reaching the compare), **H-ADDR** (a wrong, also-blank address) and **H-IDLE** (idle
pins). F1 says every frame the engine is authorised to rewrite is blank in the base; F3 says the
candidate's only non-blank content is two words per frame; F6 says the blank run around each
envelope is 7 frames (`A1F`–`A81`, 707 words) and 12 frames (`C1A`–`C81`, 1212 words). **Every
frame the current production authority permits the carrier to rewrite is blank, so no
observation available under that authority is distinctive.**

Separating them requires a new design, not a further run of this one.

### 3.4 The JTAG gate was rejected for three structural reasons — decisive

A host-side design review (`docs/claimb_jtag_gate_review.md`) asked whether a Claim B
write-verification gate could ride the already-validated JTAG path. It required five proofs
together; one passed. The three failures are structural, not engineering difficulties:

1. **No hardware channel exists for a host-side verdict.** By §2.7 the scorer cannot arm without
   `configuration_valid`, which only the carrier's internal readback can raise. Connecting a JTAG
   verdict is an RTL change, outside this review; directly injecting it into or bypassing the
   existing interlock would be exactly the "dressed-up bypass" the fifth proof forbids. A new
   architecture that re-establishes the interlock is a different case (§3.5). A verify-last,
   quarantine-and-promote variant on the present carrier dies the same way:
   to have a score at all, the scorer must first arm, which needs the internal readback to verify
   **non-blank** content — the broken thing. By §2.3 the interlock has only been observed to
   succeed in the degenerate all-zero case, and it failed on both tested candidates for which a
   gate was needed.
2. **The JTAG path's validity comes from the action this project forbids on the read path.** By
   §2.6 the shutdown is not decoration; it is the mechanism. But
   `docs/claimb_icape2_readback_sequence.md` §1 rules that SHUTDOWN/GTS/GRESTORE must not be
   copied to the read path, because they reach every flip-flop on the die and the carrier —
   `carrier_stream`, its CRC, its AXI window, the U-Boot transport — **lives in the fabric being
   read**. Seventeen reads is seventeen such transitions applied to the design under test.
3. **Continuation after verification is not established** (this is a gap, **not** a general
   impossibility). Every child ends at `JSHUTDOWN` with no trailing `JSTART`;
   `scripts/board_signature_search.py` has no board-side restart; and in both O1 and O2 the
   acquisition is the last board step, so **nothing has ever been run on the board after an R4
   acquisition**. A trailing `JSTART` would add another whole-die startup transition, but its
   actual post-R4 effect was never measured (§4). Without evidence that the phenotype and
   transport survive unchanged, it cannot satisfy this gate's required state-preservation proof.

**Cost was never the obstacle.** By §2.8 an acquisition is 1.8 s. JTAG was not rejected for being
slow; it was rejected because there is no interlock channel for its verdict and because the read
sequence that makes it work perturbs the state under test.

### 3.5 What `configuration_valid` is, and why the distinction matters later — strong

It is **not** a candidate authorization or whitelist gate. Authorization is **link 1, the
host's**, in `scripts/gate_candidate.py` — the 292-bit whitelist, flush frames equal to the
pinned base verbatim, each ECC a correct recomputation — and it runs before anything is written.
`docs/claimb_carrier_design.md` §3b: *"A readback compare proves exactly one thing: the fabric
now holds what the guard actually received and wrote. It does not prove that candidate was
permitted."*

`configuration_valid` is the scorer's **hardware write-integrity, readback-attribution and
validity interlock**, establishing links 2 and 3 of

> bytes the host candidate gate ACCEPTED == bytes actually HANDED TO the guard
> == bytes READ BACK from the fabric

Consequently, replacing links 2–3 with a stronger oracle is **legitimate in principle** — §3b
itself demands the third conjunct be computed by the host from bytes it actually received, never
from a match bit the PL reports. But that legitimacy requires a **new, reviewed hardware
architecture** in which the interlock is re-established rather than removed. **Direct bypass
remains invalid**, and no host-side verdict can reach this line as the carrier is built.

## 4. NOT TESTED

Listed so they are not mistaken for findings in either direction.

* **Whether the carrier's engine can successfully return non-blank content at all.** All 105
  frames in the seven completed engine transactions in the frozen inventory were expected to be
  blank (§2.4). The candidate transactions did request non-blank content, but stopped at
  `F_READBACK` and staged blank. No discriminating non-blank positive-control transaction has
  completed, so the general capability question remains open rather than answered negatively.
* **Whether restore and baseline can run after an R4 acquisition.** Never attempted (§3.4.3).
* **Whether a trailing `JSTART` would leave the carrier and its AXI transport usable.** Never
  attempted; expected to disturb whole-die state, but that expectation is an inference.
* **Which of H-PAD / H-ADDR / H-IDLE is the mechanism.** Inseparable under this carrier (§3.3).
  A distant misaddress beyond F6's ±2000-word local search is also unbounded.
* **The PCAP/devcfg independent readback path.** Deliberately never folded in: an independent
  method changes what an observation means and must be argued on its own terms. It addresses
  systematic instrument error, **not** the internal fork.
* **Cross-die generalisation.** Deferred. `zynq-autoehw`'s M1 already reproduced bit-identically
  on a second die, but that is a different claim and is not extended here.
* **Claim B itself.** Zero data points. No map-guided arm, no random-safe control arm, no score.

## 5. Why the programme is paused

The stop-loss was written into the 2026-08-20 session ruling **before** the review that triggered
it, with the explicit purpose of stopping a later session from drifting past it by finding one
more thing to fix. As the opening status records, that temporal ordering lives in the session
record; commit `dd7721d` is the first repository artifact and contains both the ruling and the
completed review:

> If the review cannot find a credible Claim B verification chain, Claim B is PAUSED and the work
> to date is published as a complete negative result.

The review found no credible chain (§3.4). The stop-loss is triggered on its own terms.

**The negative result, stated once, in full:**

> The candidate write was observed **twice, in separately established fault states, by the same
> JTAG method** to have landed at the intended FAR. The canonical carrier's **internal readback
> interlock faults on the candidate**, and its record of success covers only **degenerate
> all-zero content**. Neither the existing JTAG path nor the sibling HWICAP path can serve as a
> substitute gate without changing the measurement architecture.

This is a legitimate outcome and was chosen in advance, not as a consolation. The instrument was
characterised; the question it was built to answer was not reached.

## 6. What is paused, and what is not

**Paused:** Claim B's board programme. No board contact is authorised.

**Not withdrawn:** the **diagnostic, per-frame-unique carrier** fallback design. Its six
constraints came from the 2026-08-20 session ruling but had no earlier committed artifact; this
is their first repository record, not evidence that the design has been implemented or audited:

1. it has a separate diagnostic identity and does not replace the canonical carrier;
2. all fifteen target frames, the pad and plausible neighbours are non-blank, device-unique and
   mutually different;
3. the mapping from an observed signature to H-PAD/H-ADDR/H-IDLE is preregistered;
4. a fresh-load no-op must first return 15/15 same-FAR bit-exact **non-blank** frames or the round
   stops;
5. the readback engine, transaction sequence, scorer and every existing production authority
   remain unchanged; and
6. raw ICAP instrumentation is considered only if a distinctive carrier still cannot separate
   the survivors.

That fallback's fourth constraint is the positive control this line has never had, and §3.5 is
the finding it would most need if it is ever revived.

**Also not withdrawn:** everything in this repository that is not Claim B — the certified
universe, the specimen attestations, the frozen map data and their gates.

## 7. What would reopen this

Not a fix to the present instrument. Either:

* a **new, reviewed measurement architecture** in which the write-integrity interlock is
  re-established around an oracle that can actually observe non-blank content (§3.5); or
* the **diagnostic carrier** returning 15/15 same-FAR bit-exact non-blank frames on a fresh-load
  no-op, which would for the first time establish that this engine can deliver non-blank
  configuration data correctly, and would make H-PAD/H-ADDR/H-IDLE separable (§3.3).

Absent one of those, further runs of the present carrier under the same all-blank authority do
not provide distinctive content with which to separate the hypotheses. That is the condition
this pause exists to stop paying for.

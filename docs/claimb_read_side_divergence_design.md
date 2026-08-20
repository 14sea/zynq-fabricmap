# The read-side divergence — an investigation design

**Design only. No board action is authorised by this document, and none is performed by it.**
Everything below is host-side reading of already-committed artifacts plus offline review of the
RTL and the recorded traces. No RTL is changed, no production code is added, and the board
stays powered down.

On 2026-08-20 the location question was answered twice, independently within one instrument:
`WRITE_LANDED_AT_THE_INTENDED_FAR`, sixteen of sixteen positive controls exact in both runs,
`A20` equal to the candidate word for word, the same frame sha256 in both. The write reaches
the frame it asks for. What the engine's own readback hands to the interlock is something else.
This document is about that something else.

It fixes, before any further experiment, what the hypotheses are, which of them the evidence
already kills, what the minimum experiment that separates the survivors would be, and what each
of its outcomes would mean. It does not propose a mechanism as if one were established, and it
does not ask for board time yet.

---

## 1. The one question

> Pass 2 of envelope 0 writes the candidate to `0x00400A20`. The frame at `0x00400A20`
> afterwards holds the candidate. The engine's readback of `0x00400A20`, in the same
> transaction, stages 101 words that do not CRC-match the committed CRC for that frame, and the
> staged words are all zero. **Why?**

What is *not* in scope, and must not be smuggled in:

* not whether the write lands — that is answered, twice, and is an input here;
* not Claim B, which still has **zero data points** and a **DRAFT** preregistration (§6 budget
  unfrozen, §10 freeze never performed);
* not §9 step 6, which cannot pass while the interlock faults;
* not the PCAP/devcfg independent readback path — a **separate design**, deliberately not folded
  in, because an independent method changes what an observation means and would be argued on its
  own terms;
* not a fix. Nothing here proposes an RTL change. A change proposed before the mechanism is
  separated would be the seventh erratum written from a guess.

## 2. The evidence base, frozen

Pinned now, the way `claimb_location_reproduction_spec.md` §3 pins its inputs, so drift between
review and use is detectable rather than assumed.

```
baseline commit          eea513b1c37ac246da73a1089e24fd2324c391ad
scripts tree             c0bb137139b937fc94302d6940cada3a9bc58b2c
vivado/carrier tree      942f1db23a8315d93b68f60f19cda8cdbfa9ad2d
carrier-run tree         98d7721ec8095ea08944f2c50c515d3a003ee879
known-answer tree        892432c99ebbe056005d2c64ea0282f0e0e45e5b
```

The six records this design reasons from, and nothing else — full digests, so the
freeze is checkable rather than recognisable:

| # | what | sha256 |
|---|---|---|
| **O1** | run 1 location verdict<br>`evidence/location_sweep_2026_08_20/step4_sweep/verdict.json` | `f921356305cc575399e0de5ee16abe39344c2d9c8684ad51e1a4f674c239eab9` |
| **O2** | run 2 location verdict<br>`evidence/location_reproduction_2026_08_20/step4_sweep/verdict.json` | `f921356305cc575399e0de5ee16abe39344c2d9c8684ad51e1a4f674c239eab9` |
| **O3** | run 1 staging copy, then its offline analysis<br>`evidence/location_sweep_2026_08_20/fault/ddr_slot0_shutdown_read.json` | `413725bc551b1a2215405ac4b55a76a1fea73e0e8133df043ca0fac36caabc34` |
| | `evidence/location_sweep_2026_08_20/fault/ddr_slot0_shutdown_read_analysis.json` | `69d4081ea7310e67b0b7a87cb1640bbae7176cd677e17a3197dbaf9cd32a5c80` |
| **O4** | run 2 staging copy, then its offline analysis<br>`evidence/location_reproduction_2026_08_20/fault/ddr_slot0_shutdown_read.json` | `3221fa684a452fd7e71f70873c0085a6ea2ea8c2138525c91a7458df9e58e4e0` |
| | `evidence/location_reproduction_2026_08_20/fault/ddr_slot0_shutdown_read_analysis.json` | `37f3000c6fff4c5abd4e138e0034a25760cf4f5414ec40bfb9e83f5e83fcdb63` |
| **O5** | the erratum-006 no-op that PASSED, with its fifteen readback frames<br>`evidence/known_answer_2026_08_14_erratum006/record.json` | `e944b85d572cb3a3cec7efe2326a4bd0f1d1b5c5df5c5ecf18ea4b9b73fe63c9` |
| **O6** | the two fault records that produced O3 and O4<br>`evidence/location_sweep_2026_08_20/fault/record.json` | `db87cd770d3174d128174edb005ab4c9f8462a1671501774d2824101efe2190a` |
| | `evidence/location_reproduction_2026_08_20/fault/record.json` | `86bdf7f0f45997c8ff94cb56e25e2182e3564e18f5e8504bc4fe00419a2b8e1b` |

O1 and O2 are byte-identical; that is a fact about the two runs, not a citation of one twice.

**Not part of the evidence base, and not cited in support of any mechanism below:**

* **Phase 2** (`evidence/phase2_2026_08_15/`). Its instrument is the pre-R4 `2.1.0`/`2.0.0`
  build, its verdict is VOID, and it appears in this document only where the subject is *why*
  it is void.
* **The erratum-005-era staging dump** (`evidence/calibration_noop_2026_08_13_erratum005/`,
  the bit-exact window at `0x00400A81`/`0x00400A82`, +604 words). It was taken on a
  **superseded carrier with a different command order**. It is used exactly once below, as
  hypothesis *generation*, and is marked there. It supports nothing.

## 3. The read path as it is actually built

Hypotheses have to be about this machine, not about a sketch of it. All references are to
`vivado/carrier/carrier_stream.v` at the pinned tree.

One `sync … DESYNC` transaction **per frame** (erratum 005 §4), five per envelope:

```
RB_PCMD    dummy, sync, NOOP, NOOP, Type-1 READ IDCODE            :695
RB_PFLUSH  32 NOOPs                                               :711
RB_TRN     CSIB High, then RDWRB moves, then CSIB Low             :726
RB_PROBE   read contiguously until a word matches IDCODE[27:0];
           the count of preceding words is rb_lat                 :739
RB_SETUP   CMD1, RCFG, NOOP, FAR1, frame_far, FDRO0, RDLEN(202)   :775   (erratum 006 order)
RB_SFLUSH  32 NOOPs, then rb_skip <- rb_lat + 101                 :794
RB_SKIP    discard rb_skip words                                  :810
RB_DATA    stage 101 words, one per clock                         :821
RB_DESYNC  CMD1, DESYNC, NOOPs                                    :835
RB_CRC     CRC the RAM, compare against the committed CRC         :855  <- F_READBACK is raised here
RB_WAIT    host copies the frame out of the same RAM, then acks   :878
```

Four properties of that machine matter for everything below:

1. **`F_READBACK` is a content compare, and it is the engine's own.** `:867` raises it when
   `crc_value != cc_rdata` — the CRC of the 101 staged words against the CRC pass 1 committed
   for `(env, frame)`. It is *not* the host's `KnownAnswerStop`, which has never fired.
2. **The capture window is timed, not qualified.** `icap_rd_valid <= !icap_csib && icap_rdwrb`
   (`:479`) is a delayed copy of the engine's own bus control. The engine counts clocks; it has
   no signal that says a word was *served*. "The device answered" and "the device drove
   something while I clocked" are indistinguishable to it.
3. **The discard is `rb_lat + 101`** (`:802`), where `rb_lat` is measured on a **Type-1 register
   read** and applied to an **FDRO frame read**. That substitution is `claimb_icape2_readback_sequence.md`
   §9 assumption 1, still carried, never tested on silicon.
4. **A fault does not require a reload.** `P_FAULT` (`:921`) latches `fault_since_reset` and
   leaves `recovery_required` set, but `begin_txn` from `P_IDLE` clears `fault` and `fault_code`
   (`:484`). The configuration memory is untouched by any of it. This is what makes §7 possible.

## 4. Six facts every hypothesis has to fit

Each is re-derivable from the pinned artifacts by the derivation given. They are stated here so
that a hypothesis can be killed on paper instead of on the board.

### F1 — all fifteen frames of the write envelope are byte-identical and all zero

```sh
python3 - <<'PY'
import json, hashlib
m = json.load(open('gate_runs/claimb_round1_carrier_2026_08_13_erratum006/phenotype_manifest.json'))
for r in m['frames']:
    w = [int(x, 16) for x in r['words']]
    print(r['far'], r['role'], sum(1 for v in w if v),
          hashlib.sha256(b''.join(v.to_bytes(4, 'big') for v in w)).hexdigest()[:12])
PY
```

Twelve targets and three flush frames, one distinct content:
`0441772f66559a1c71f4559dc4405438fc9b8383ce1229139257a7fe6d7b8de9`, **zero non-zero words**.
4,716 of the device's 5,144 frames are also all zero.

### F2 — the no-op writes that same blank content, so O5 is a degenerate control

`board_claimb_known_answer.py:104` is `step("no_op", lambda: _write("restore", …))`, and
`known_answer.json`'s `restore.actual_init` is `0x0000000000000000`. So the only content the
readback has ever been asked to verify on silicon is the all-zero content of F1, and it verified
it fifteen times (O5: `rb_frames_ok = 15`, `configuration_valid = 1`, every one of the fifteen
`readback_frames` all zero).

**The engine has never once read back a non-blank frame correctly, because it has never been
asked to.** A read path that returned 101 zero words unconditionally would have produced O5
exactly. This is the single most important constraint in this document and it is why the no-op's
"pass" cannot be used as evidence that the read path works.

### F3 — the candidate differs from blank in exactly two words per frame

`0x00400A20` → words 50/51 = `0x0000100E`, `0x00005213`; `A21` → `0x000009C1`, `0x00001276`;
`A22` → `0x00001008`, `0x00004040`; `A23` → `0x000009C4`, `0x0000F573`. Word 50 is the ECC word
`frame_ecc.update_ecc` recomputes; word 51 carries the INIT bits. `A20`'s frame sha256 is
`15cb05e68adbff6c962053bb5220c33d278c09a793ce12bc4017f37269a5bbe7` — the value JTAG read back
in both runs (O1, O2) and the value `analyse_ddr_capture.py` derives independently from the
frozen authority.

### F4 — the staged frame is all zero, twice, and it is the failing frame

O3 and O4: 101 words, **0 non-zero**, sha256 `0441772f6655…6d7b8de9` — equal to the base frame
at the requested FAR, unequal to the candidate, byte-identical across two separately built fault
states with different `plmark`s. The copy is the staging RAM: `pass2_line()`
(`board_uboot_axi.py:270`) issues `cp.l RDBACK → slot` for every frame of the envelope
unconditionally, so slot 0 holds the window the engine had staged when it faulted.

### F5 — the probe came up, measured the same latency as on the passing run, and 101 words were staged

Fault STATUS `0x04040082` decodes to `fault = 1`, `rb_frames_ok = 0`, **`rb_latency_words = 1`,
`rb_latency_valid = 1`**. O5's passing run measured `1` in all three envelopes. The fault code is
**8 = `F_READBACK`**, not `12 = F_RBSYNC` and not `10 = F_BYTECOUNT`: the read path came up, the
device named itself, the CRC consumed exactly `BYTES_PER_FRAME`. So 101 words were staged and
CRC'd, and they were the wrong 101 words. Nothing here is a timeout, a sync failure or a
short read.

### F6 — the blank neighbourhood, and what it does and does not hide

Treating the served stream as contiguous configuration memory in device order, let δ be the
displacement in words between the window the engine staged and the intended first word of
`0x00400A20`. Searching ±2000 words for a 101-word all-zero window:

```
pre-write image    δ ∈ [-1159,-1061] ∪ [-654,-253] ∪ [-150,+555]
post-write image   δ ∈ [-1159,-1061] ∪ [-654,-253] ∪ [-150,-51] ∪ [+355,+555]
```

(derivation: `bitstream_frames.parse_frames` + `device_frame_sequence` on the pinned
`carrier.bit`, with the F3 candidate words overlaid at `A20`–`A23` for the post-write image.)

Two consequences, and they point in opposite directions:

* **Every δ with |δ| ≤ 50 is excluded post-write.** An alignment error of a few words cannot
  produce F4: the candidate's non-zero words at 50/51 would still be inside the window. A
  latency-class error surviving F4 has to be **≥ 51 words**, in the direction of discarding too
  few — i.e. the FDRO pipeline would have to be at least 51 words deeper than the register read
  the probe measures. `δ = −101` — exactly one frame, the pad — is in the surviving band.
* **δ = 0 is blank in the pre-write image.** So "the read is one transaction late" fits F4
  perfectly, and F6 cannot distinguish it from a displaced read that landed on a blank frame.
  This is the fork §7 exists to open.

## 5. The hypotheses, kept apart

Stated so that each is separable from the others, with what would have to be true for it and
what it predicts. **H-REF** and **H-LAT** are listed because they were live before F4 and F6;
they are dead now and saying so is part of the record.

| tag | hypothesis | what it says |
|---|---|---|
| **H-STALE** | *as-of-before read* | The FDRO read is correctly addressed but observes configuration memory as it stood **before this transaction's FDRI burst** — the write is buffered, deferred, or not visible on the read port until the transaction ends. JTAG, reading later and through a different port, sees the committed result. |
| **H-PAD** | *pad-frame alignment* | The engine stages the **dummy/pad frame** rather than the addressed one. `RB_WORDS = 202` is pad + frame; a one-frame error in the discard (δ = −101) stages the pad. The pad is blank here, whatever it physically is. |
| **H-ADDR** | *wrong, also-blank address* | The read is served real configuration memory from an address that is not `frame_far(env, frame)` — a FAR that did not take, an auto-increment residue, a mis-executed RCFG — and that address happens to be blank. F6 bounds it to the surviving δ bands. |
| **H-IDLE** | *no configuration data at all* | The FDRO transaction never serves the frame; the engine clocks its timed window against an idle interface and stages whatever the pins hold, here zeros. Property 2 of §3 is what makes this invisible to the engine. |
| **H-REF** | *the reference, not the data* | The readback is correct and the committed CRC it is compared against is wrong. |
| **H-LAT** | *probe-to-FDRO latency* | `rb_lat` measured on a Type-1 read mis-states the FDRO latency by a few words, shifting the capture. |

Three framings are deliberately **not** on the list, with reasons:

* *"the write did not land"* — refuted by O1 and O2, which is what those runs were for.
* *"the bytes came back different"* as a host-side finding — the host's `KnownAnswerStop` has
  never fired; every stop is the engine's FAULT register. The distinction matters because the
  host has never independently compared a candidate readback byte for byte.
* *"the fault is content-dependent, so the content is what breaks it"* — F1 and F2 dissolve
  this. The asymmetry between the passing no-op and the failing candidate is not evidence about
  content handling; it is what a blank-returning read looks like when the expectation is blank
  in one case and not in the other.

## 6. What the evidence already decides

| hypothesis | O5 (no-op passed 15/15) | F4 (staging all zero) | F5 (latency 1, valid, `F_READBACK`) | F6 (δ bands) | status |
|---|---|---|---|---|---|
| **H-STALE** | consistent — blank written over blank, so a pre-write view is the same view | consistent — pre-write `A20` is blank | consistent | consistent (δ = 0 blank pre-write) | **ALIVE** |
| **H-PAD** | consistent — the pad is blank too | consistent | consistent | consistent (δ = −101 in a surviving band) | **ALIVE** |
| **H-ADDR** | consistent **only** for wrong addresses that are blank in every one of O5's fifteen reads; a residue read starting at `A81` would have served `A82` (19 non-zero words) and O5 would have failed | consistent | consistent | consistent within the surviving bands only | **ALIVE, narrowed** |
| **H-IDLE** | consistent | consistent | consistent | not applicable — no stream is being displaced | **ALIVE, weakened**: the one time this silicon has been observed with a read transaction that was not delivering frame data, it drove the abort status word `0xFFFFFF5B` 101 times — not zeros. *[hypothesis generation only: superseded carrier, and on it the write had not synced either; erratum 005 §1]* |
| **H-REF** | consistent | **refuted** — a correct read of the candidate would have staged words 50/51 non-zero; the staged window has zero non-zero words | — | — | **DEAD** |
| **H-LAT** | consistent | — | — | **refuted for \|δ\| ≤ 50**; survives only as an error of ≥ 51 words, of which exactly 101 is H-PAD | **DEAD as stated** |

So: **four survive, and the first fork is H-STALE against {H-PAD, H-ADDR, H-IDLE}** — "the read
looks at the right place at the wrong time" against "the read does not deliver the addressed
frame at all". Every experiment below is judged on whether it moves that fork.

## 7. The minimum experiment that separates them

### 7.1 The idea

`begin_txn` clears `fault` and `fault_code` from `P_IDLE` (§3 property 4) and **nothing in the
fault path touches configuration memory**. So after the candidate round faults, the fabric holds
the candidate at `A20`–`A23` — O1 and O2 prove it does — and a *second* transaction can be run
into the same loaded carrier, in the same boot, with no reload and no power cycle.

Run the **no-op step again**, into that state. It writes blank over the candidate and reads
`A20` back, expecting blank.

* Under **H-STALE**, the read observes the memory as it stood before *this* burst — which is now
  the **candidate**, non-blank. Expected blank. The step **faults**, `F_READBACK`, pass 2 of
  envelope 0 — on a step that has passed every time it has ever run.
* Under **H-PAD / H-ADDR / H-IDLE**, the read returns blank as it always has, all fifteen frames
  verify, `configuration_valid` goes high — and the host then stops anyway, because
  `recovery_required` is still latched from the first fault (`board_uboot_axi.py:638`). A
  fail-closed stop with `rb_frames_ok = 15` and `fault = 0`.

Both outcomes are stops. They are **not the same stop**, they are distinguishable from
`record.json` without interpretation, and they answer the fork. That is the whole experiment.

The reversal is worth stating because it is what makes this sharp: the *no-op* — the step that
has never failed — is predicted to **fail** under H-STALE, and the candidate step is not reached
in either branch.

### 7.2 What it cannot do

It does not separate H-PAD from H-ADDR from H-IDLE. Nothing available under the frozen carrier
does: F1 says every frame the engine can address is blank before the write and F3 says the
only non-blank content it can ever create is two words per frame, F6 says the blank run around each
envelope is 7 frames (`A1F`–`A81`, 707 words) and 12 frames (`C1A`–`C81`, 1212 words), and the
payload authority is frozen, so no legal write can put distinctive content where a displaced or
idle read would reveal itself. **Separating those three requires either a carrier whose target
frames sit in non-blank, mutually distinct content — an RTL and build change — or an independent
readback path. Both are out of scope here, and the second is the separate PCAP/devcfg design.**
That is a limit of the instrument, and it should be stated in the next handoff rather than
discovered by a reviewer.

### 7.3 What it needs that does not exist yet

**There is no entrypoint that can run one transaction into an already-loaded carrier.**
`board_claimb_known_answer.py` and `board_claimb_postfault_capture.py` both call
`cal.phase_setup`, which does SHA + `board_set_fclk50.py` + `loadb --require-unconfigured` — and
a reload **reconfigures the device and destroys the state the experiment is about**.
`board_carrier_exec.py` is a library with no CLI.

So the experiment needs exactly one new non-scoring entrypoint: *given an already-loaded,
already-faulted carrier and a `plmark`, stage one sealed payload from the frozen authority, run
one transaction, record everything, never arm the scorer, never reload.* Building it is **not
part of this pass** — it is new production code, and it needs its own tests, mutants, audit and
authorisation. It is named here so the next ruling is about a known quantity. This is the same
missing piece §9 step 6 has needed all along.

### 7.4 Shape of the run, if it is ever authorised

Not a request. Recorded so the reading table below has something concrete to attach to.

```
① the specified fault, exactly as in claimb_location_reproduction_spec.md §5 steps ①–③
② SAME BOOT, NO RELOAD: one no-op transaction through the new entrypoint
③ SAME BOOT: probe_ddr_capture.py --slot 0, read-only, whatever ② did
④ host-side only: the reading below
```

Step ③ is what makes a fault in ② interpretable rather than merely surprising: under H-STALE
the staged frame should be the **candidate** — sha256 `15cb05e68adbff6c…69a5bbe7`, non-zero at
words 50/51 — which would be the **first time this project has ever seen the read path deliver
non-blank configuration data**. That is a bigger result than the fork it settles.

## 8. Pre-registered reading table

Fixed here, before the experiment can be run, and before any of it can be seen.

| # | observation in ② | verdict, decided in advance |
|---|---|---|
| **A1** | `F_READBACK`, pass 2 of envelope 0, `rb_frames_ok = 0`, and ③ stages the **candidate** frame (sha `15cb05e6…`) | **H-STALE supported, H-PAD/H-ADDR/H-IDLE refuted.** The read is correctly addressed and observes memory before the burst. The read path can deliver real frame content. Stop; the mechanism question becomes "why is the write not visible to the read port", which is a new design |
| **A2** | `F_READBACK`, pass 2 of envelope 0, and ③ stages an **all-zero** frame | **Uninterpretable as it stands, and a result.** A fault whose staged content is blank is what the *candidate* round already produces; the no-op reproducing it means the fault is not about the written content at all. Record, stop, make no causal claim |
| **A3** | `F_READBACK`, and ③ stages something that is **neither** blank nor the candidate | valid third state and the most informative one: run the offset search over the post-write image. Record the frame and its matching offsets; do not interpret further in this experiment |
| **B1** | fifteen frames verify, `configuration_valid = 1`, `fault = 0`, host stops on `recovery_required` | **H-STALE refuted; H-PAD/H-ADDR/H-IDLE all survive.** The fork is answered in the other direction, and the next step needs a non-blank target or an independent read path — neither of which this instrument has. Stop |
| **B2** | any other fault code — `F_RBSYNC`, `F_BYTECOUNT`, `F_TIMEOUT`, `F_ORDER`, `F_PHASE` | not this experiment's question. The engine did something it has not done before; record it, stop, and do not read it as evidence about the fork |
| **C1** | step ① does not produce the specified fault (`STATUS 0x04040082`, `FAULT 0x8`, pass 2 envelope 0) — **including an unexpected pass** | stop **before** ②. The state the experiment is about was not created |
| **C2** | any reboot, `plmark` mismatch, refused transaction, missing capture, or bookkeeping anomaly | not interpretable; stop where it happened, keep everything |

**Fixed with the table**: the run happens once. A failed separation is a result, not a reason to
rebuild the state. `recovery_required` will be set for the whole of ② by construction, so any
reading that depends on it being clear is invalid by definition. And a pass in ② is a
**fail-closed host stop**, never a green light — nothing downstream of it is authorised by it.

## 9. Offline work, which needs no board and no authorisation

Ordered. Each has its reading fixed here.

**W1 — re-derive F1–F6 from the pinned artifacts and commit the derivations.** The four
`python3 -` derivations in §4, their output, and the commands. *Reading*: if any of the six does
not reproduce at the pinned tree, this document is wrong and the hypothesis table has to be
rebuilt before anything else happens.

**W2 — audit every committed record for a readback of non-blank content.** Every
`evidence/*/record.json` with a `readback_frames` or a staging capture, checked for a single
frame with a non-zero word. *Reading*: if none exists, then §4 F2 is general and not a property
of one run — **the read path has never been demonstrated to deliver configuration data at all**,
and that sentence belongs in the README's status block, not only here. If one does exist, it is
the most important artifact in the repository and this design is rewritten around it.

**W3 — state, per hypothesis, which clause of the device-model contract it violates.**
`claimb_icape2_readback_sequence.md` §7 is a seven-clause contract and `icape2_model.v` implements
it; the benches pass at read latencies 0/1/3/5/7/12 against devices demanding 32/40/48/64 flush
clocks, and `mutate_carrier_readback.sh` carries twelve mutants of the read sequence, each with the outcome it must produce. So **every surviving hypothesis is a
divergence between the model and the silicon, not a defect the benches could have caught.**
Which clause: H-STALE contradicts clause 5 (serve from configuration memory) plus clause 4's
write-buffer model; H-PAD contradicts the pad's identity and length; H-ADDR contradicts clause 3
(FAR successor arithmetic) or the erratum-006 execute-on-FAR-load rule; H-IDLE contradicts
clause 6 (refuse what the hardware refuses). *Reading*: a hypothesis that no clause covers is a
hole in the contract and gets written up as one.

**W4 — review the timed capture window against UG470 and write down what the engine cannot
know.** §3 property 2 in full: `icap_rd_valid` is a delayed copy of the engine's own bus
control; the discarded words are never recorded; the pre-IDCODE idle word's *value* — the one
word that would separate "idle drives zeros" from "idle drives the abort pattern" and therefore
H-IDLE from the rest — is measured as a count and thrown away. *Reading*: this is an
instrumentation gap, it is cheap to close in RTL, and it is recorded here as the leading
candidate for whatever the next carrier does. **It is not implemented in this pass.**

**W5 — write the handoff.** This document, W1–W4's outputs, and one paragraph that states
plainly: the location question is closed at two observations under one instrument, the read-side
question has four live hypotheses, one fork is separable with the existing carrier and the rest
are not, and Claim B still has zero data points.

## 10. Budget

| item | figure |
|---|---|
| W1–W5 | host-side only, no board, no new production code |
| the §7 experiment, if ever authorised | one new entrypoint (+ tests, mutants, audit) — a separate ruling |
| board time for ①–④ | one power cycle, one carrier load ≈ 3 min, two transactions ≈ 2 s of engine time, one read-only `md.l` |
| what it consumes | one fault state, which is rebuildable |
| what it risks | two ICAP writes of payloads already reviewed under the frozen authority, into a carrier already in a fault state, with the scorer unarmed on the wire |

## 11. Decisions requested

1. **Accept or amend the hypothesis set (§5) and the two refutations (§6).** H-REF and H-LAT are
   killed on the committed evidence, not on the board; if either refutation is wrong, the fork
   in §6 is wrong too.
2. **Rule on §4 F2** — that the no-op's fifteen-frame pass is a degenerate control and cannot
   support "the readback works". This is a correction to how earlier results have been read, and
   under the standing ruling it goes in an additive file beside them, never as a rewrite.
3. **Authorise W1–W5** (host-side, no board contact).
4. **Rule on §7.3** — whether the non-scoring, no-reload entrypoint is built next, as its own
   reviewed deliverable, or whether the read-side question waits for the PCAP/devcfg design or
   for a carrier with non-blank targets. §7.2 is the argument that the last two are the only
   ways past the fork.

Nothing in this document authorises board contact. When something does, it will carry its own
stop conditions and its own host-only freeze preflight.

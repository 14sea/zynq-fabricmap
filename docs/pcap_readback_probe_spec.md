# PCAP readback probe — specification

> **HOST-SIDE SPECIFICATION ONLY. No implementation, no allowlist entry, and NO BOARD RUN
> is authorised by this document.** Nothing here is evidence. It fixes what would be
> measured, what would count as a pass, and — before anything runs — what would stop it.
> Style and standing follow `docs/claimb_r4_protocol.md`, which is an offline derivation
> under the same rule.

## 0. The one question

> On **EBAZ4203 `17A6`**, can the PS read one **known non-blank** configuration frame back
> through **PCAP** into DDR, such that the returned 101 words are **bit-exact** against an
> expectation pinned in this document **before the run**?

That is the whole probe. It is a capability question about a path, not a Claim B
experiment, and §9 bounds what a pass would license.

## 1. Why this is not "more instrumentation on the paused leg"

`docs/claimb_findings.md` §7 names exactly two things that would reopen Claim B, and the
first is *"a **new, reviewed measurement architecture** in which the write-integrity
interlock is re-established around an oracle that can actually observe non-blank content."*
Every such architecture has the same precondition: **something must be able to observe
non-blank configuration content on this part.** §4 of that document lists this as an open
question, not a closed one:

> *Whether the carrier's engine can successfully return non-blank content at all … the
> general capability question remains open rather than answered negatively.*

This probe asks the precondition, on a path that is **not** the carrier's engine. It
therefore does not touch, revise, or depend on the W2 verdict, which stands unchanged
(`claimb_findings.md` §2.4). If the probe fails, §7.7 applies: publish, do not instrument.

## 2. Warrant classes — every load-bearing fact is tagged

Nothing in the sequence may be executed on a fact whose class is not stated.

### 2a. VERIFIED IN-REPO (hardware record exists, on a **different board**)

| fact | source |
|---|---|
| devcfg is at `0xF8007000`; `CTRL[PCAP_PR]` is **bit 27** (`0x08000000`) | `zynq_xpart/docs/icap_investigation.md`, RESOLUTION 2026-06-07 |
| Clearing bit 27 hands the configuration engine to **ICAP**; restoring it returns ownership to **PCAP** — so a PCAP readback requires **bit 27 = 1**, the default post-boot state | ibid. |
| The observed CTRL word on **that** board was `0x4c00e07f` (PCAP) / `0x4400e07f` (ICAP) | ibid. |
| **On `17A6` itself, `CTRL` reads `0x4e00e07f`** in several committed records (`evidence/isolate_2026_08_12b/record.json`, `evidence/cell_fclk50_before_load_2026_08_12/record.json`, `evidence/calibration_noop_2026_08_14_erratum006/record.json`, `evidence/postfault_r4_step1_control_2026_08_16/reading.md`) | this repo's own evidence tree |
| A 7-series frame is 101 words; xc7z010 carries 5,144 frames, self-checked against the FDRI payload to the word | `scripts/bitstream_frames.py` |
| On the **AXI HWICAP** path the addressed frame comes out **behind a ~101-word readback pad** | `zynq_xpart/docs/icap_investigation.md` §"HWICAP readback" |
| Board identity: `REQUIRED_BOARDID = "17A6"`, `REQUIRED_ROLE = "verify"`, `CONTROL_PLANE = "uboot"` | `scripts/gate_board_identity.py:66,67,85` |

**⚠ The hardware record above is from EBAZ4205, which `docs/board_roles.md`:17 places
*out of the pool* for this line ("reference … Never a sacrifice candidate"). It is the same
silicon (XC7Z010) on a different board with a different boot environment. Constants that
are board-specific must be READ on `17A6`, never carried across** — the standing precedent
is the FCLK0 magic `0x00200A00`, which is 4205-specific because the 4203's IO PLL differs.
**`CTRL` is read and recorded before anything is written** — and §5e fixes what may then be
done with it.

**One difference is already visible and it is not cosmetic.** `0x4e00e07f` (17A6) and
`0x4c00e07f` (the 4205) differ in exactly **bit 25** (`0x02000000`); both carry bit 27, so
both have PCAP owning the configuration engine. UG585 identifies bit 25 as
`QUARTER_PCAP_RATE_EN` — **that identification is class 2b and S0 must discharge it** — but
if it holds, the board this probe runs on is configured for a *quarter-rate* PCAP, which
bears directly on the bandwidth-overflow stop condition (§7.1). This is precisely the kind
of board-specific difference §2a exists to catch.

### 2b. VENDOR-DOCUMENTED, NOT VERIFIED HERE

Supplied by review, citing AMD UG585 (Zynq-7000 TRM), *PL Bitstream Readback* / *Example PL
Bitstream Readback* / *PCAP Throughput*. **These pages were not fetched or read by the
author of this specification**, so each is a claim to be discharged in S0, not a fact:

- PCAP performs bitstream readback with **two DMA transfers**; the minimum unit is **one
  101-word frame**.
- PCAP has an **RxFIFO** and the PL side has **no flow control**: insufficient DMA bandwidth
  **overflows**, and **one readback may not be split across multiple DMA accesses**.
- ≈145 MB/s theoretical throughput. A 2.08 MB transfer landing in the tens of milliseconds
  is a **derivation from that figure, not an end-to-end measurement on this board**, and
  must be written that way everywhere.

### 2c. TO BE DERIVED AND PINNED IN S0, BEFORE ANY BOARD TIME

The exact readback command word sequence; the exact offsets and bit fields for the DMA
source/destination/length registers, the completion indication, and **the overflow /
underrun indication** (a stop condition cannot be pre-committed against a bit whose
identity is guessed); the DDR buffer addresses; and U-Boot's cache handling for a buffer a
DMA engine writes.

## 3. Control plane: U-Boot only — and that is the point

`docs/claimb_preregistration.md` §"The control-plane boundary" is explicit:

> **Booting Linux after verifying identity invalidates the authorisation.** … *If round 1
> keeps a U-Boot-only control plane, there is no gap.* … *If calibration uses a Linux-side
> executor (`/dev/mem`, HWICAP through a running kernel), then a **Linux-side identity
> mechanism must exist and be built first**.*

`scripts/gate_board_identity.py:357` enforces it: `authorise_write()` refuses a `linux`
executor against a `uboot` identity even if the epoch matched.

**A PCAP readback needs nothing Linux provides.** It needs register writes into devcfg, a
DDR buffer, and a read of that buffer — `mw` and `md`, which is what every existing board
script on this line already uses. **This probe is therefore specified U-Boot-only, and a
Linux executor is refused.** That is not a stylistic preference: choosing Linux would
require building and reviewing a Linux-side identity gate first, which is a larger project
than the probe and would gate it behind unrelated work.

**Consequence worth stating:** because no PL AXI register is read, the FCLK0-gated hard hang
(`docs/board_roles.md` §"Wedge is not damage") **does not apply to this probe as specified**.
If any step is later added that reads PL AXI, it applies again and FCLK0 must be enabled.

## 4. The pinned positive control

Base bitstream: `gate_runs/claimb_round1_carrier_2026_08_13_erratum006/carrier.bit`,
sha256 `8c3369e8e4755da5aceeb7844690d5e132b2e65647004c0a46c0e868e34f0b8a`.

Target frame **FAR `0x00000B99`** (`block_type 0, top 0, row 0, major 23, minor 25`) —
**all 101 words non-zero**. Expectations, big-endian, 404 bytes per frame:

| FAR | nonzero words | sha256 |
|---|---:|---|
| `0x00000b97` | 100 | `e4d5335eb8a4b1332e4449384627088a25d57d2b4c87f2b41be271d0656b166c` |
| `0x00000b98` | 101 | `09e6542e15d2236ef806ab934ff70db967cde6d248bda996b753d6542839351c` |
| **`0x00000b99`  ← target** | **101** | **`9029c9d032e0287453cb5c02cd18be42bc03acef38b17ef7295ee0d16beb6b1f`** |
| `0x00000b9a` | 84 | `80f782b962888a97d6a663d116d3b6158ff4d7408626ce6b83f43ba855356477` |
| `0x00000b9b` | 83 | `83e824b6b26107265390cb0a51b7f22d447bdbe45cf3842853a146eecfa7e760` |

Target word 0 = `0x4756bea7`, word 100 = `0x00800001`, ECC word 50 = `0x000009bb`.

### 4a. The discriminating-power check, done before any board time

This is the gate the first iCE40 probe failed and that B1 failed — an observation that
cannot separate the hypotheses is an uninterpretable null, however clean the run looks.
What is separable, stated exactly — **not** "all three failure modes are separable", which
an earlier draft claimed and which is more than this instrument delivers:

| what came back | what the probe can say |
|---|---|
| **blank** | **Partly.** The sentinel (§6c) separates "the destination is unchanged from the prefill" from "zeros overwrote it"; but zeros delivered cannot be told apart from a misaddress to any of the **4,716 blank FARs** (§4c), so `BLANK` is a class, not a diagnosis |
| **misaddressed by ±1 or ±2** | **Identified by name** — and here that is warranted, because all five hashes are unique **across the whole 5,144-frame table**, not merely against each other (asserted by test). Minimum Hamming distance to the four nearest neighbours is **822 bits** |
| **misaddressed to some other frame of the same base** | **Narrowed to a candidate FAR set** via the frame table (§4c) — one FAR when its hash is unique, otherwise the whole set. Not "identified by name" in general |
| **not frame-aligned, truncated, or corrupted** | **NOT separated from each other.** All land in `NO_MATCH`. The raw 202 words are kept so the question stays open rather than being answered by the verdict |

`claimb_findings.md` §4 already records that a distant misaddress is unbounded; §4c narrows
that for frame-aligned cases and does not pretend to close it for the rest.

**The target was chosen by maximising that minimum distance over every frame in the
bitstream with ≥20 non-zero words**, ties broken by non-zero count and then by the highest
FAR. `scripts/diag_pcap_target_select.py` re-derives the whole table above, and
`tests/test_pcap_probe_target.py` asserts the pinned hashes against it, so §4 is
machine-checked rather than asserted.

### 4b. The expectation is a constant, not a computation

The runner compares against the **hashes written above**, not against a value it derives
during the run. Re-deriving at run time is how "recompute until it matches" gets in.
`erratum-005` is the precedent: a dump that was **bit-exact against the device stream at an
address other than the one requested**. A run that searches for an offset that matches has
proved nothing.

### 4c. The whole-bitstream frame table — and what it cannot do

`scripts/diag_pcap_target_select.py --frame-table` emits one `<FAR> <sha256>` line for each
of the **5,144** frames of the pinned base. Its digest is

    5039aab0c39411251fb3d405788fe5119236d2159528c85bd3bd280e65d6ad21

**A reverse lookup on this table returns a SET of FARs, never one.** An earlier draft said
it would identify a misaddress "by name"; that is false on this device, and the numbers were
already in this repository when the claim was written:

| | |
|---|---:|
| frames | 5,144 |
| **distinct hashes** | **425** |
| duplicate-hash groups | 5 |
| frames inside a duplicate group | 4,724 |
| **FARs sharing the all-zero hash** | **4,716** (`claimb_findings.md` §2.3 F1) |

The four non-blank collisions are `0x0000_0d0b == 0x0000_0d0f`,
`0x0000_139d == 0x0040_139d`, `0x0040_118a == 0x0040_118d`, `0x0040_118b == 0x0040_118c`.

A lookup that took the first match would manufacture a confident wrong answer. The verdict
contract is therefore:

| reverse match | verdict |
|---|---|
| exactly one FAR | `MISADDRESS`, that FAR named |
| more than one FAR | `MISADDRESS_AMBIGUOUS`, **the full candidate set reported**, never a pick |
| the all-zero hash | `BLANK` — and **which** of the 4,716 blank FARs it came from is *not* recoverable (§7.3a) |
| no match | `NO_MATCH` |

**S1 and S2 are unaffected:** the target and all four neighbours have **globally unique**
hashes, verified over the whole table, not merely against each other.
`tests/test_pcap_probe_target.py` pins the multiplicity table above so a lookup that
collapses a set to one FAR fails a test rather than a run.

### 4d. Which 101 words the comparison and the lookup use

Fixed, so that no run may choose:

- **`words[101:202]`** — and only these — are compared to the pinned target hash, and are
  the sole input to the §4c reverse lookup.
- **`words[0:101]`** is the pad (§6a). It is hashed and recorded as a **diagnostic only**.
- **A hit anywhere in `words[0:101]` never produces a verdict about the requested FAR.** If
  the target's hash appears there, the verdict is a pad finding, reported as such, and the
  comparison offset is *not* moved to make it a pass.

**There is a genuine tie, and it is stated rather than hidden:** `0x00000B98` and
`0x00000B99` both have 101 non-zero words and both score a minimum distance of 822 — which
is precisely their distance from *each other*. The tie-break is arbitrary by construction;
either frame would serve the probe equally well, and the rule is written down so the
selection is reproducible, not so that it is uniquely determined by the data.

The runner reads the pinned constants; it does **not** call the selector at run time.

## 5. Every device operation, exhaustively — and what is NOT done

### 5a. The session begins with a canonical setup write — stated, not hidden

An earlier draft said the probe loads no bitstream and runs "against whatever the board
already holds". **That was wrong and it would have made a negative uninterpretable.** The
board is powered down; on power-up the PL is empty. If S1 then missed, nothing would
separate *"PCAP readback does not work"* from *"the die was not holding the base"* — the
same shape of uninterpretable null as B1, arrived at by a different route.

The session is therefore fixed, in this order, in **one boot**:

1. **Physical power cycle** (unplug; the S2 button is unreliable).
2. **`scripts/precheck_fresh_power.py`** — read-only, all five preconditions, every reply
   guarded against a mid-check reboot. It does not repair; it refuses.
3. **Verify board identity — `boardid` and `role` — BEFORE the setup load**, on the session
   that will perform it, and hold that identity and epoch through step 6.
4. **SHA gate on the bitstream file** against
   `8c3369e8e4755da5aceeb7844690d5e132b2e65647004c0a46c0e868e34f0b8a` before it is sent.
5. **Load the canonical carrier with the existing audited loader**,
   `scripts/board_uboot_fpga_load.py`, which requires the PL to be empty first, clears the
   sticky `PCFG_DONE` (`0xF800700C` bit 2) so the post-load check is an **edge** and not a
   level, and sets `plmark`.
6. **S1–S3 run in that same boot and that same epoch**, each stage re-checking the same
   `plmark` (`board_claimb_known_answer.py:163` does this already). **A reboot ends the
   probe** — it does not restart it.

So the *session* contains exactly one configuration write, the canonical setup load, and it
is named here rather than left implicit. **The probe stages themselves still write zero
configuration frames** (§5c), which is a claim about S1–S3 and not about the session.

**⚠ Step 3 is a CHANGE, not a description of what the tools do today, and S0 must deliver
it.** An earlier draft put identity verification at S1, *after* the load — which left the
session's only configuration write happening before anyone had established that this is
`17A6` in role `verify`. That is exactly what prereg §7's board-identity gate exists to
refuse ("writes … with the wrong `boardid`, or on the wrong board — **no flag override**").
Two facts make the hole concrete, and both were checked rather than assumed:

- `scripts/precheck_fresh_power.py` interrogates `echo`, `md.l` and **`printenv plmark`
  only**. It never reads `boardid` or `role`.
- `scripts/board_uboot_fpga_load.py` performs **no identity check of any kind**.

**The unresolved engineering, named rather than papered over:** the loader and the probe
runner currently open **separate serial sessions**, while §5d requires one `BoardSession`,
one identity and one epoch across the whole probe. S0 must either drive the loader through
that session or pin an explicit, reviewed boundary — and if it pins a boundary, it must say
what re-establishes authority across it. This specification does **not** authorise a setup
load performed outside a verified identity.

### 5b. Performed by the probe stages

1. U-Boot identity verification (`printenv boardid`, `printenv role`, `md`) on the open
   session that will perform the probe, in one epoch.
2. Read and record `CTRL` at `0xF8007000`, and check it per §5e.
3. **Pre-fill the destination buffer with a non-zero sentinel and read it back to confirm
   the fill landed.**
4. Write the readback **command** word sequence into a DDR buffer (`mw`).
5. Program the devcfg DMA to send that command stream to the configuration engine.
6. Program the devcfg DMA to receive **202 words** (pad frame + target frame — see §6a) into
   the sentinel-filled buffer.
7. `md` that buffer out over UART and hash it on the host.

**Only one thing in that list is normative**, and it is the correction: an earlier draft put
the sentinel fill *after* the receive DMA was programmed, which either races the DMA or
overwrites its result.

> **NORMATIVE: the destination sentinel is written and verified before ANY step that could
> let the DMA write that buffer.**

**Everything else about the DMA ordering above is illustrative and S0 owns it.** §2c already
places the exact sequence in the to-be-derived class, so declaring "send DMA, then receive
DMA" normative here would pin from the specification what the specification says it cannot
yet know. S0 derives the order, it is reviewed, and only then is it pinned — into an amended
§5b, not into this sentence.

### 5c. NOT performed by any probe stage — the probe's main safety property

- **No `FDRI`. No configuration frame is written. Not one CRAM bit is modified.**
- No `GRESTORE`, `GTS`, `GCAPTURE`, `JSHUTDOWN`, `JSTART`, or any startup transition.
- No PL AXI access (§3).
- No bitstream load **inside a stage**; the one load is §5a's setup, before S1.
- No use of the candidate gate, the whitelist, or the phenotype manifest — they gate frame
  writes, and the stages perform none.

### 5d. The authority entry point — pinned here, not deferred

An earlier draft left "is a command-only transaction *a write* in `write_sequence()`'s
sense?" open for a later ruling. **That cannot be deferred: S0 has to implement the runner,
and a runner without a named entry point either invents one or borrows a wrong one.**
`BoardSession.write_sequence()` is the *carrier AXI* transaction and reusing it would be a
mis-fit; but "it does not write CRAM" is not a licence to bypass session identity either.
S0 pins this contract:

1. The runner **reuses the same `BoardSession`, identity and epoch** — no second session,
   no re-resolved port.
2. It is a **new, named configuration-read capability**, distinct from `write_sequence()`
   and separately reviewed.
3. A **fixed allowlist of DDR and devcfg addresses**; anything else is refused before
   transmission.
4. **Refused unconditionally:** `FDRI`, any configuration command not on the allowlist,
   any DDR address off the allowlist, and any `linux` executor (§3).
5. Before each read: **clear and then verify** stale DMA completion/error status. After
   each read: record `CTRL` and status, and perform the config-engine cleanup the derived
   sequence requires.
6. The same `plmark` is checked at every stage (§5a.5).

### 5e. `CTRL` is checked, not adjusted

Fail-closed, because a probe that reconfigures the engine to make itself work is measuring
its own setup:

1. After §5a's setup, **read** `CTRL` and record it verbatim in every stage record.
2. **This is a MASKED-BIT gate, not an exact-word gate.** S0 derives a mask of the bits that
   must hold for a PCAP readback (bit 27 among them); only those bits are required to be
   **already correct**. The full word is recorded verbatim either way.
3. If a masked bit is wrong → **STOP**. Do not modify `CTRL`, do not proceed, report the
   value read. If the masked bits are right but the **full word differs from `0x4e00e07f`**,
   that is **recorded as an observation and is not a stop** — the historical value is an
   expectation about this board, not a gate.
4. **If S0 concludes a modification is genuinely required**, the spec is amended *before the
   run* to pin the exact mask, and the runner saves the original value and restores it
   exactly in a `finally`. No ad-hoc write is permitted at run time.

`0x4e00e07f` is a **historical** value from this board (§2a). It sets the expectation and it
does not substitute for the live read. To say it once, unambiguously:

> **A mismatch in a required masked bit is a STOP. A full-word mismatch with the mask
> satisfied is RECORDED ONLY.**

## 6. Sequence shape

### 6a. The pad frame

On the HWICAP path the addressed frame arrives **behind a ~101-word pad** (§2a). Whether
PCAP presents the same pad is **not established**. The destination buffer is therefore
**202 words**, and the record keeps **both halves**:

- words `[101:202]` are compared against the target's pinned sha256 — the expected case;
- words `[0:101]` are hashed and recorded too. If the target's hash appears at offset 0
  instead, that is a **finding about the PCAP pad**, and it is reported as such — it is
  **not** a pass, and the comparison offset is not adjusted to make it one.

### 6b. Timeouts and completion

A single pinned timeout per DMA, derived in S0 from §2b's throughput figure with an explicit
margin, and recorded as *derived, not measured* until a measurement exists.

### 6c. Every read is pre-filled with a sentinel

The destination buffer is filled with a non-zero sentinel and the fill is verified **before**
each readback. Without it, *"the destination is unchanged from the prefill"* and *"the DMA
replaced the destination with zeros"* produce the same bytes — and one of those is a stop condition about the instrument
while the other is a finding about the die. A run that cannot tell them apart has re-created
the failure this probe exists to avoid.

## 7. Stop conditions — pre-committed, and binding

The point of writing these before the run is that they cannot be relaxed after they fire —
the ruling this line already made once, on 2026-08-06, when T2 failed.

1. **Any overflow / underrun / error indication** in the devcfg status → **STOP**.
2. **DMA completion not signalled within the pinned timeout** → **STOP**. Do not re-issue.
3. **Adjudication runs in two steps, and the first one is NOT on the frame half.**

   **Step 1 — the sentinel check, on the whole 202-word buffer.** S0 pins the complete
   sentinel pattern; the runner compares the **entire buffer** against it.

   | condition on all 202 words | verdict | continue? |
   |---|---|---|
   | every word still equals the pinned sentinel | `BUFFER_UNCHANGED_FROM_PREFILL` — instrument unvalidated | **STOP** |
   | **some** sentinel words survive and some do not | `SENTINEL_REMAINS` — possible partial transfer or value collision; instrument unvalidated | **STOP** |
   | no sentinel word survives | — | go to step 2 |

   **These two verdicts name an OBSERVATION, not a mechanism, and the names were narrowed
   for that reason.** A buffer identical to the prefill establishes only that the
   destination is unchanged from the prefill — **it does not prove the DMA never wrote**,
   because the DMA could have written values that happen to equal the sentinel. Likewise a
   partial survival does not prove a partial transfer: the real returned words could collide
   with the sentinel at exactly those positions. Both remain **STOP**, and both are recorded
   as *instrument unvalidated* rather than as a diagnosis.

   The stronger reading would need S0 to prove the sentinel **positionally disjoint from
   every value the path can return**, and the unknown pad (§6a) makes that hard: you cannot
   exclude a collision with content you have never seen. Until such a proof exists, the
   narrow reading is the only one this specification supports.

   An earlier draft also evaluated "sentinel intact" on `words[101:202]` alone and read it
   as "the DMA never wrote" — false whenever the DMA writes the pad half and leaves the
   frame half untouched, which is why step 1 runs on the whole buffer.

   **Step 2 — the frame verdict table, the ONLY way a stage's content is adjudicated.** It
   is evaluated on `words[101:202]` and on nothing else (§4d), against the pinned constants
   (§4) and the frozen frame table (§4c), first row that matches wins:

   | condition on `words[101:202]` | verdict | continue? |
   |---|---|---|
   | equals the **pinned target hash** | `PASS` | yes |
   | all zero | `BLANK` (see 3a) | **STOP** |
   | reverse lookup hits **exactly one** FAR | `MISADDRESS`, that FAR named | **STOP** |
   | reverse lookup hits **more than one** FAR | `MISADDRESS_AMBIGUOUS`, **the full candidate set** recorded — never a pick | **STOP** |
   | no hit anywhere in the table | `NO_MATCH`, raw 202 words recorded | **STOP** |

   An earlier draft handled only the neighbour case, which left a remote-but-unique hit and
   an ambiguous hit with no assigned verdict — and an unadjudicated outcome is where a run
   starts improvising. **No alignment search, ever** (§4b): the table is consulted at the
   fixed offset or not at all.

   **3a. What `BLANK` does and does not mean.** It establishes that **the DMA replaced the
   destination with zeros** — and nothing beyond that about where those zeros came from. It
   does **not** distinguish *"the read path delivered zeros"* from *"the read was misaddressed to one of the 4,716 blank FARs"* —
   those are indistinguishable in the returned bytes, and the record says so rather than
   choosing. It is also why `BLANK` is listed **before** the reverse-lookup rows: the
   all-zero hash would otherwise return a 4,716-element "candidate set" that says nothing.

4. **No retries and no parameter changes inside a run.** One shot per stage. A second
   attempt is a new run, with a new record, declared before it happens.
5. **Sentinel not confirmed present before a read** → **STOP**; the read is not attempted.
6. **If S1, S2 *or* S3 fails, the PS/PCAP line PAUSES and that stage's scoped negative is
   published.** No additional instrumentation, no retries, no "one more thing to fix". An
   earlier draft applied the stop-loss to S1 only — but **S2 (misaddress) and S3 (drift) are
   probe failures of the same standing**, and S3 is precisely where the HWICAP precedent
   died (§8). A stop-loss that exempts the stage most likely to fail is not a stop-loss.

## 8. Stages, and the gate on each

| stage | board? | what it does | gate to proceed |
|---|---|---|---|
| **S0** | **no** | Discharge §2b against UG585; derive and **pin** §2c; write the runner and its tests; reproduce the §4 target selection | Reviewed by the party that did not write it (`docs/workflow.md`: a gate written by the author of the thing under test is not a gate). **Board ruling is separate and comes after.** |
| **S1** | yes | Identity → one readback of `0x00000B99` → compare to the pinned hash | Pass = bit-exact. Anything else → §7 |
| **S2** | yes | Read `0x00000B98` and `0x00000B9A`; each must equal **its own** pinned hash | Tests that the requested FAR selects three *distinct* pinned frames — a stronger address-select test than S1 alone, and not a proof that the address is honoured in general |
| **S3** | yes | **10 independent** transactions (FAR and readback command re-issued each time, DMA status cleared, sentinel re-filled, all 10 raw buffers kept) | Pass requires **both**: every one of the ten equals the **pinned target hash**, *and* the ten are identical to each other. Ten stable reads of the *wrong* frame must not pass. The HWICAP path failed exactly here — the chunked-FDRO boundary **drifted ~18 words between two back-to-back reads** |
| **S4** | — | Only now is an architecture review discussable | Still requires `claimb_findings.md` §3.5's *new, reviewed hardware architecture*; a readback capability is not an interlock |

S2 and S3 run **only** if every prior stage passed. One whole-of-probe board ruling covers
S1–S3; there is no ruling per stage.

## 9. What a pass would, and would not, establish

**Would:** on this die, on board `17A6`, over a U-Boot control plane, **with the canonical
carrier loaded (§5a) but no Claim B transaction or scorer measurement in progress**, PCAP
returned **this specific non-blank frame** bit-exactly, repeatably, at the address
requested. (An earlier draft said "no design under test running", which contradicts §5a's
setup load.)

**Would not:**

- that it does so **while a design is running**, or without perturbing it. **S3 proves read
  repeatability, not non-perturbation** — there is no observable in this probe that a
  running design's state survived, and adding one is a separate design. Naming this gap is
  the point; verifying both ends of a chain and leaving the middle empty is a known failure
  mode on this line.
- that it works at Claim B's target FARs (`0x00400A20‥23`, `0x00400C1A‥1D`,
  `0x00400C20‥23`), which are in a different region and are **blank in the base** — the very
  property that makes them useless as positive controls (F1).
- **anything about the carrier's internal engine.** W2's verdict is untouched.
- that PCAP can serve as a Claim B **interlock**. `claimb_findings.md` §3.5: replacing links
  2–3 is legitimate *in principle*, but only via a new reviewed architecture in which the
  interlock is **re-established**; direct bypass stays invalid. A readback that works is a
  precondition, not an architecture.
- anything about a Linux control plane (§3).
- anything about any other board. `17A6` is one board.

## 10. Evidence to be produced

Per stage, a `record.json` carrying: the board identity block and epoch as returned by the
identity gate; `CTRL` **as read** before any probe-stage devcfg or DMA write (the setup load
of §5a is itself a write and precedes this); the pinned expectations copied verbatim
from §4; the raw 202 words; the two half-frame sha256s; the elapsed time with its
`measured` / `derived` tag; and the verdict from §7's fixed vocabulary
(`BUFFER_UNCHANGED_FROM_PREFILL`; `SENTINEL_REMAINS`; `PASS`; `BLANK`, with §7.3a's limit attached;
`MISADDRESS` with the one FAR it matched; `MISADDRESS_AMBIGUOUS` with the **full** candidate
FAR set; `NO_MATCH`; `OVERFLOW`; `TIMEOUT`) — and, for every stage, both half-frame hashes
with which half each verdict came from (§4d). Plus the raw UART log,
unedited. `docs/evidence_contract.md` governs the format.

## 11. Board, wedge, recovery

**EBAZ4203 `17A6`**, role `verify` (`docs/board_roles.md`:18). **Not the 4205**, which is out
of the pool. A wedge is **not** damage: recovery is a power cycle (physically unplug; the S2
button is unreliable), and **the known-answer regression runs before anyone suspects
damage** — that lesson already cost a board swap and a torn-down harness.

## 12. What this specification cannot close

- The UG585 sequence itself (§2b, §2c) — S0's job, and S0 may conclude the path is not
  reachable as specified, which is a legitimate S0 outcome.
- The **content** of the S0 contract in §5d — the shape is fixed there, the concrete
  allowlists and the named capability are S0 deliverables.
- Whether PCAP presents a pad frame (§6a).
- A non-perturbation observable (§9).
- Whether bit 25 of `CTRL` is `QUARTER_PCAP_RATE_EN` and what a quarter-rate PCAP does to
  the overflow margin (§2a, §7.1) — S0's job. The 4203 `CTRL` value itself is **not** open:
  `0x4e00e07f` is in this repo's evidence tree, and §5e makes it an expectation to be
  re-read live rather than a constant to be trusted.
- Which blank FAR a `BLANK` verdict came from (§7.3a) — not recoverable from the bytes.
- Whether a sentinel that survives means the DMA did not write, or merely collided (§7.3).
  Closing it needs a positional disjointness proof against every value the path can return,
  which the unknown pad (§6a) obstructs. **Until then the two sentinel verdicts stay
  observational and both stop the run.**

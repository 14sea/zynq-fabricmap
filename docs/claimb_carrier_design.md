# Claim B round 1 — carrier design

**Status: DESIGN, for review before any code.** This repo's rule since the `clb_ff_config`
builder: the design document comes first and is reviewed, so the implementation can only be
its executor and cannot quietly become a second plan. **No Vivado build is authorised**, and
no device write is authorised.

The carrier is the bitstream the evolution run mutates: it holds the evolvable LUTs at the
certified sites, a scorer that turns a candidate into a number the PS can read, and the
control path that applies candidates. Its hard requirement is not that it works — it is
that **frame ownership is separated and provable**.

## 1. Where the evolvable logic must go — derived, not chosen

The 292 certified addresses sit in **three slices**, and each slice is **exactly one ICAP
envelope**:

| envelope | FARs | bits | site | tile | tile type |
|---|---|---|---|---|---|
| 0 | `0x00400A20‥A23` | 98 | **`SLICE_X2Y25`** | `CLBLL_L_X2Y25` | `CLBLL_L` |
| 1 | `0x00400C1A‥C1D` | 100 | **`SLICE_X9Y25`** | `CLBLM_L_X6Y25` | `CLBLM_L` (SLICEL_X1) |
| 2 | `0x00400C20‥C23` | 94 | **`SLICE_X8Y25`** | `CLBLM_L_X6Y25` | `CLBLM_L` (SLICEM_X0) |

Six "LUTs" is three slices × {`A6LUT`, `D6LUT`}. `SLICE_X8Y25` and `SLICE_X9Y25` are the two
slices of **one tile**, yet they occupy different frame groups — SLICEM carries more
configuration — so **the envelope boundary is per slice, not per tile**.

**LOCK_PINS is part of the contract, not an optimisation detail.** The certification
specimens pinned `I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6`. The certified addresses are the
INIT bits *under that pin mapping*; if Vivado permutes the carrier's LUT inputs, the same
truth table lands on different INIT bits and every address in the map becomes wrong while
everything still looks correct. The carrier's six LUT6s must carry the same `LOCK_PINS`,
plus `DONT_TOUCH` so they survive optimisation.

## 2. The frames, and what is actually in them

Each frame spans a whole column within one clock region, so the exclusion zones are
**column segments, not tiles**:

| major | base | column | rows | frames used |
|---|---|---|---|---|
| 20 | `0x00400A00` | `CLBLL_L_X2` + `INT_L_X2` | Y0‥Y49 | minors 32‥35 — **targets** |
| **21** | `0x00400A80` | **`CLBLM_R_X3` + `INT_R_X3`** | Y0‥Y49 | minor 0 — **flush** |
| 24 | `0x00400C00` | `CLBLM_L_X6` + `INT_L_X6` | Y0‥Y49 | 26‥29 **targets**, 30 **flush**, 32‥35 **targets** |
| **25** | `0x00400C80` | **`DSP_R_X7` + `INT_R_X7`** | DSP Y0‥Y45, INT Y0‥Y49 | minor 0 — **flush** |

### Frame ownership — corrected after review v3

**Two measurements, and only one of them supports a strong conclusion.**

From the frozen segbits:

| rule file | frame offsets **named** | minor 0 |
|---|---|---|
| `segbits_int_l.db` / `segbits_int_r.db` | **0‥25** | yes — **324 tokens** |
| `segbits_clbll_l.db` | 0‥35 | yes — 13 tokens |
| `segbits_clblm_l.db` / `segbits_clblm_r.db` | 0‥35 | yes — 21 tokens |

From the frozen `tilegrid.json`, which is the **structural** authority:

| tile | frames | minors spanned |
|---|---|---|
| `INT_L_X2Y25`, `INT_L_X6Y25`, `INT_R_X3Y25`, `INT_R_X7Y25` | **28** | **0‥27** |
| `CLBLL_L_X2Y25`, `CLBLM_L_X6Y25`, `CLBLM_R_X3Y25` | 36 | 0‥35 |
| `DSP_R_X7Y25` | 28 | 0‥27 |

**The correction.** An earlier revision concluded from "no INT token above 25" that every
target frame at minor ≥ 26 holds no routing bits. That promotes *the database does not name
a token there* into *nothing owns configuration there*, and this repo's own position is
that the frozen DB is an **index, not ground truth**. `tilegrid` contradicts the strong
form: the INT tile structurally spans minors 0‥27.

What the segbits measurement actually supports is only the narrow statement: **`INT_L` and
`INT_R` contain no `F_B` token whose frame offset exceeds 25.**

So the honest partition of the 12 target frames is:

| target frames | minors | INT structural span | writable bits |
|---|---|---|---|
| `0x00400A20‥A23`, `0x00400C1C‥C1D`, `0x00400C20‥C23` | 28‥29, 32‥35 | **outside** (10 of 12) | 244 |
| **`0x00400C1A`, `0x00400C1B`** | **26, 27** | **INSIDE `INT_L_X6Y25`'s span** | **48** |

Those two frames must be treated as **shared with, or potentially owned by, `INT_L_X6`**.
The in-column flush `0x00400C1E` (minor 30) is outside the span, as are all four of
envelope 0's frames.

**Preserving every non-whitelist bit from the pinned base remains required — but it is not
a transient-safety proof.** It guarantees the *content* is unchanged; it says nothing about
what a reconfiguration write does to a column while it is being reloaded.

### The one sentence to use, because the shorter version is wrong

> **A candidate changes content bits only; every other bit of every frame it writes is the
> pinned base's, verbatim.**

That is a statement about what we *write*. It is **not** the same as "the target frames
contain only CLB content", which is false and was already retracted once: `0x00400C1A` and
`0x00400C1B` sit inside `INT_L_X6Y25`'s 28-frame structural span, and the two cross-column
flush frames are minor 0, which carries INT routing configuration.

The distinction is the whole justification for three things that therefore do **not** get
simplified away, however low the hardware risk otherwise looks:

* the **board-side FAR/FDRI guard** — the intended write set is provably content-only, so
  the path that could reach a routing frame is a MIS-ADDRESSED write, i.e. a software
  defect. The guard is what stands between that defect and the fabric;
* the **quiesce interlock** — because a write reloads a column that the evolvable data path
  shares;
* the **readback compare** — because "what we meant to write" and "what the device now
  holds" are different questions.

The two cross-column minor-0 flush frames remain the strongest hazard, and their route
ownership must be **empty**: a net through `INT_R_X3` or `INT_R_X7` has its PIP
configuration inside a frame this run rewrites on every candidate.

## 3. Placement and routing rules

The previous revision said "`PROHIBIT` on the four column segments", which applied
literally forbids the six BELs the design requires. The scopes below are exact and
separately testable.

### Flush columns — `CLBLM_R_X3`/`INT_R_X3` and `DSP_R_X7`/`INT_R_X7`, Y0‥Y49

- **placement: prohibited entirely.** No cell of any kind.
- **routing: must be empty.** Routed-net ownership over these tiles is checked and must
  return nothing (§4 check 2).

### Target columns — `CLBLL_L_X2`/`INT_L_X2` and `CLBLM_L_X6`/`INT_L_X6`, Y0‥Y49

- **placement: prohibited everywhere except the six named LUT BELs** —
  `SLICE_X2Y25/{A6LUT,D6LUT}`, `SLICE_X9Y25/{A6LUT,D6LUT}`,
  `SLICE_X8Y25/{A6LUT,D6LUT}`, each `DONT_TOUCH` with the pinned `LOCK_PINS`.
- **routing: not globally prohibited** — those LUTs need data nets, which must traverse
  `INT_L_X2` and `INT_L_X6`. It is governed instead by an **explicit net allowlist**:

  > Only the enumerated **evolvable data nets** (the six LUTs' inputs and outputs) may use
  > target-column INT resources. **No** HWICAP write-control path, **no** board
  > identity/control-plane path, **no** clock or reset that a write depends on to
  > complete, and **no** unrelated scorer path may traverse them.

  The reason is `0x00400C1A`/`0x00400C1B`: 48 writable bits live in frames inside
  `INT_L_X6Y25`'s structural span, so a write to them touches a frame the INT tile also
  spans. A transient on the **evolvable data path** is tolerable — that path is what is
  being mutated. A transient on the path performing the write is not.

### Scorer, HWICAP and control logic

Outside all four column segments. The case that must never exist is **HWICAP writing a
frame that carries its own control path** — the write would be able to interrupt the
mechanism performing it.

Their pblock must state explicitly whether `CONTAIN_ROUTING` (or the equivalent) is
required. **A placement-only pblock may not be described as a routing constraint**;
routing is free to cross a region no cell occupies.

### Quiescing — a HARDWARE interlock, ruled 2026-08-10

Because target-frame writes may perturb the evolvable data path, the scorer must not be
sampling across a write. **Firmware calling things in the right order is not sufficient**:
that is trusted code, and the whole point of an interlock is to hold when the trusted code
does not run. The scorer is gated in hardware and is **fail-closed**:

1. the interlock **freezes the scorer** — evaluation disabled and accumulator held —
   whenever reconfiguration is in progress **or** the readback has not been confirmed;
2. all three envelopes are written;
3. the 12 target frames are **read back and compared** to the candidate (preregistration
   §6 item 8);
4. only an explicit *readback-confirmed* signal releases the interlock, and the result is
   sampled only after the scorer reports completion.

**Default state is frozen.** A reset, a lost control connection, or any condition in which
the release signal is absent or indeterminate leaves the scorer held — never running. An
interlock whose failure mode is "sampling" would produce a fitness number for a device
state nobody verified, and that number is indistinguishable from a real one.

A fitness sampled without that sequence is not scored — the run log's `scored` flag already
requires a matching readback, and this ordering is what makes the flag meaningful rather
than a claim the runner makes about itself.

**A pblock is an instruction to the tools and is not evidence** (§4).

## 3b. What `configuration_valid` authorises — a three-part conjunction

Ruled 2026-08-10, after the phrase "set only on the complete candidate" was noticed to be
doing more work than it can carry.

**A readback compare proves exactly one thing: the fabric now holds what the guard actually
received and wrote.** It does not prove that candidate was *permitted*. Whether the payload
changes only the 292 whitelisted bits, whether the flush frames equal the pinned base
verbatim, and whether each ECC is a correct recomputation are judgements of the **host**
gate, `scripts/gate_candidate.py`. The PL does **not** re-implement a 292-bit content gate;
it must simply not be described as one.

What has to hold before a score means anything:

> **bytes the host candidate gate ACCEPTED
> == bytes actually HANDED TO the guard
> == bytes READ BACK from the fabric**

`configuration_valid` establishes links 2 and 3. Link 1 is the host's, and scoring needs it
too. Two consequences for the data path, so nothing can slip between the links:

* **the transport sends the same in-memory bytes the gate parsed.** Gating and then
  re-reading the file is a different artifact with the same name, and every property the
  gate established is about the bytes it held;
* **the run log's candidate hash and readback hash must be equal before an arm is issued.**
  `run_log.record_candidate` already refuses to mark an entry `scored` without that
  equality; this makes it a precondition of arming as well, not only of scoring.

### The arm condition, in full

Confirmed 2026-08-10 against `run_log`'s hash domains, which do not collide:
`sequence_sha256` is the complete ordered three-envelope byte stream, while
`candidate_sha256` and `readback_sha256` are both the FAR-ordered canonical frame set — so
comparing the latter two is meaningful, and the former pins what was actually transmitted.

> **arm ⟺ `gate_verdict.writable` ∧ `configuration_valid` ∧
> `candidate_sha256 == readback_sha256`**

One conjunct per link of §3b: the host gate's verdict, the fabric's own confirmation, and
the host's independent check that what came back is what went out.

## 3c. The flush-column exception — RULED 2026-08-10, before the routed names were known

The only nets that may cross a flush column are the **twelve** derived mechanically from
the six evolvable LUTs' pins: `vector[0..5]` and `lut_q[0..5]`. The allowlist is generated
from the LUT and scorer endpoints **before** a build, never chosen from a list of
post-route violators — the exception is fixed by the six LUTs' data interface, which
existed before any of this floorplanning.

Conditions, all of which must hold together:

* flush **cells** remain 0;
* none of the twelve may fan out to the guard, ICAPE2 control, AXI, clock/reset, the
  watchdog, `configuration_valid`, `arm` or `done`;
* the scorer is already disabled before a write, and cannot re-arm until the readback
  matches in full;
* flush frame bytes still equal the pinned base verbatim.

The physical reason, and it is a real distinction rather than a convenience: these data
paths may be transiently unstable during quiesce, because they are what is being mutated.
The paths that PERFORM the write, CONFIRM it, or AUTHORISE scoring may not be.

**Any control-class net crossing a flush column stops the work at the architecture, and the
allowlist is not widened to admit it.**

## 3d. ■ ARCHITECTURE STOP — the buffer cannot sit on the left, and PS7 cannot move

The stop condition of §3c is met, and the cause is device geometry rather than constraint
tuning. Measured tile columns:

| resource | tile column | side of the first flush column (tile X3) |
|---|---|---|
| PS7 | far left | left |
| `CLBLL_L_X2` — targets, `evolvable_0/1` | X2 | left |
| **`CLBLM_R_X3` — FLUSH** | **X3** | — |
| `RAMB36_X0` (`BRAM_L_X4`) | X4 | right |
| `DSP_R_X7` — FLUSH | X7 | right |
| `CLBLM_L_X6` — targets, `evolvable_2..5` | X6 | right |

**There is no BRAM column to the left of the first flush column.** So:

* **logic on the right** (`SLICE_X10..X43`): the AXI bus from PS7 must cross tile columns
  X3 and X7. 124 crossing nets, including the AXI bus and `guard/configuration_valid` —
  control class.
* **logic on the left** (`SLICE_X0..X1`): AXI stays left, but the buffer's BRAM is at tile
  X4, so `axi_buf_rdata` crosses instead. 190 crossing nets — also control class.

And the left region cannot hold the buffer as LUTRAM instead:

    SLICE_X0Y0:X1Y99      200 slices = 800 LUTs
    buffer 1608 x 32      832 LUTs   (32 bits x ceil(1608/64) per SLICEM LUT)
    logic (measured)      432 LUTs
    required             1264 LUTs   -> short by 464

### The option that does fit, and what it costs

A **one-envelope buffer** (536 words) is 288 LUTs, so 288 + 432 = 720 of 800 fits on the
left with no BRAM at all. But it gives up the property that closed a real window and was
explicitly approved: *validate all 1608 words before streaming any of them.* With one
envelope resident, envelope 0 would be written before envelope 2 had been looked at.

That is recoverable — the host can send the stream **twice**, once for a validation pass
over all three envelopes and once to write, with the mismatch flag accumulated across
passes so `configuration_valid` still requires all 15 frames to match. The cost is a second
6,432-byte transfer, which is nothing beside the 2 MB a full reload would need.

It is a change to an approved property, so it is not made unilaterally.

## 4. Proving the isolation — from the routed design, not from constraints

Three checks, each producing a machine-readable record. All are host-side and none needs a
board.

1. **Cell ownership.** For every tile in the four column segments,
   `get_cells -of_objects [get_tiles ...]` must return exactly the six evolvable LUTs (in
   the two target columns) and **nothing at all** in the two flush columns.
2. **Route ownership, two different questions.**
   - over the two **flush** column segments: `get_nets -of_objects [get_tiles ...]` must be
     **empty**;
   - over the two **target** column segments: every net returned must be on the enumerated
     evolvable-data-net allowlist, and the check fails on the first net that is not — in
     particular any HWICAP, control-plane, clock or reset net.

   This is the check a pblock cannot substitute for: pblocks constrain placement, and
   routing is free to cross a region no cell occupies.
3. **INIT differential — a post-route ECO on the SAME routed DCP, never a re-route.**
   Open the routed checkpoint, `set_property INIT` on one evolvable LUT, write the
   bitstream, and require the frame diff against the base bitstream to be confined to that
   LUT's expected target frames plus their own ECC words.

   Re-running placement and routing for the variant would make the comparison worthless:
   the router is free to produce a different result, so a clean diff would prove nothing and
   a dirty one would not distinguish an INIT effect from a routing change. This is exactly
   how the `clb_ff_config` line's `zini_*` specimens were derived — open the routed DCP,
   change a property, write the bitstream, no re-place and no re-route — and the frame-ECC
   known answers in `scripts/frame_ecc.py` were validated against those very pairs.

Check 3 subsumes a lot, but 1 and 2 must exist too: a diff can be clean because a route
exists and simply did not change, while still being present in a frame we rewrite.

## 5. The scorer, and what the fitness may assume

**No LUT is fully writable**: 49, 49, 49, 51, 50 and 44 of 64 INIT bits are certified, 92
are not. The uncertified positions keep whatever the base bitstream put there. So:

- the phenotype is **six partially constrained truth tables**, not six free ones;
- a fitness defined as "distance to an arbitrary target function" is misspecified, because
  most target functions are unreachable;
- the honest formulation is a fitness over the **reachable** space: the target is defined,
  and the score is a match rate over a fixed input-vector set, with the unreachable
  positions fixed by the base for both arms equally.

Both arms face the identical constraint, so the comparison stays fair; the constraint
affects the achievable ceiling, not the contrast.

Shape: a fixed vector source drives the six LUT inputs, the six outputs are compared
against a target word, and a counter accumulates matches into a register the PS reads —
the mailbox pattern this hardware line has used throughout. Train and holdout are different
vector sets, and holdout is evaluated **only** on each arm's final champion.

## 6. The board-side guard (separate deliverable, same review)

Independent of the host gate, per the preregistration: a **fixed** FAR/FDRI range check
that no environment variable or command line can widen. The sibling `icaphw.c`'s
`ICAPHW_FAR_LO` / `ICAPHW_FAR_HI` / `ICAPHW_MAX_FDRI` overrides must **not** be carried
across — an overridable guard is not a guard. The permitted set is the 12 target FARs plus
the 3 flush FARs and nothing else, compiled in.

`PCAP_PR` is restored with try/finally semantics: on failure too, the code attempts to
restore it and reports ICAP health rather than leaving the device half-configured.

## 7. Acceptance ladder — nothing skips a step

1. this design document, reviewed;
2. RTL + constraints written; **no build yet**;
3. Vivado build (**needs authorisation**), then checks 1–3 of §4 as a gate that must pass
   before anything else looks at the result;
4. `phenotype_manifest` emitted from the built carrier and committed — the first instance
   this repo will hold;
5. host-only dry run: candidates generated, sequences built, gated, logged, **no device**;
6. board-side guard firmware, with its own host-side tests;
7. only then the engineering calibration — which is a device write and needs the single
   whole-of-run ruling.

## 8. Reachability — ruled: it may precede the carrier build, under a frozen spec

The reachable space may be measured **before** the carrier is built (it is pure arithmetic
over the 292 writable positions and needs no Vivado). But it may not be measured and *then*
used to pick a convenient target: that is choosing the hypothesis after seeing the data.

**`reachability_spec` is frozen first, committed, and hash-pinned.** It fixes, before any
measurement runs:

| field | why it must be frozen first |
|---|---|
| **base INIT** of all six LUTs | the 92 uncertified positions keep these values; they define the reachable set |
| **`LOCK_PINS`** | the INIT↔truth-table mapping; a different mapping is a different reachable set |
| **the 64 input vectors, in order** | fitness is a match count over them; reordering or reselecting after the fact changes the score |
| **train/holdout seed and split** | the behavioural holdout must be unread — see preregistration §4 |
| **the target family** | *which* functions are candidate targets, stated as a family (e.g. "parity over a fixed input subset"), not as one function chosen later |
| **the deterministic selection and replacement rule** | how a target is drawn from that family, and what happens when a draw is unreachable — an algorithm, not a judgement call |

Only then is the measurement run, and the target follows from the frozen rule applied to
the measured set. If every draw turns out unreachable, that is a **result about the space**
to report, not a licence to widen the family.

## 9. Scorer placement — the region choice is frozen before the first build

Ruled 2026-08-10: **where** the scorer ends up may be decided by engineering results, but
the candidate regions and the rule that picks among them are frozen **before the first
build**, so a region is never chosen after seeing behavioural results.

**ERRATUM (2026-08-10).** This section said the region choice was frozen in
`specs/carrier_placement_spec.json` before the first build. **That file did not exist**, and
several builds have now run without it. It is frozen below instead, and legitimately so:
no board data and no fitness number exists yet, so nothing can have influenced the choice.

**Frozen selection rule:** take the FIRST region, in the order listed, that passes the §4
isolation checks and meets timing. Fitness plays no part — there is none yet, and there
will never be a licence to build in several regions and keep the one that scored best.

Region order: (1) one contiguous block clear of all four column segments,
`SLICE_X10Y0:SLICE_X43Y99`; (2) the same widened leftwards to `SLICE_X6`; (3) a
multi-region layout, only if a contiguous one cannot route.

Frozen alongside the RTL, before any further build:

- a **named preferred region** and a **named ordered fallback list**;
- a **deterministic selection rule**: take the first region in the order that satisfies
  every §4 check and meets timing; record which one was taken and why each earlier one was
  rejected;
- all regions must, by construction, lie outside the four column segments and satisfy the
  target-column net allowlist.

What may not happen: building in several regions, comparing fitness, and keeping the one
that scored best. That would make placement a tuned parameter of the result.

*(Settled by review v3: all six LUTs are used — a one-slice carrier would erase most of the
cross-LUT and cross-frame structure whose navigational value is the thing under test.
Settled 2026-08-10: the quiescing interlock is hardware, see §3.)*

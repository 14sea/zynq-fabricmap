# A Hamming-1 database decidability census for xc7z010

**Status: a standalone host-side measurement, 2026-08-26. No board was touched.**

> **⚠ This is NOT the preregistered Claim B safety leg, and it does not settle Claim B's
> safety conjunct.** A draft of this document, written before review and never published,
> claimed it did. That claim was wrong on two counts, is retracted in §0, and the retraction
> is kept here rather than in a commit message because this document is where it has to
> travel. The measurements themselves are unchanged and stand.

## 0. What this is, and what it is not — read before citing anything below

**What it is.** An exhaustive census of one question about the *frozen database*: for
every configuration bit of an xc7z010, can the frozen prjxray rules say what flipping it
does? The answer is a property of `data/prjxray/zynq7/` plus one pinned bitstream. It is
reproducible in 45 seconds and needs no hardware.

**What it is not, and why — both of these were got wrong first time:**

1. **It is not the preregistered Claim B safety comparison.**
   `docs/claimb_preregistration.md` §1 fixes that comparison: *both* arms draw from **the
   same certified 292-address universe**, the baseline is **random-safe within it**, and
   comparing map-guided content mutation against "flipping bits anywhere in the bitstream"
   is **explicitly refused** — not only because that baseline touches routing and is unsafe
   on a working board, but because *"any difference would confound the map's navigational
   value with a difference in the risk envelope."* The refusal is epistemic as well as
   operational, so moving the same comparison to the host does not license it. The round-1
   safety metrics are also different quantities entirely (§4 of the prereg: gate rejections
   by reason, invalid compositions proposed vs reaching the device, reloads and recoveries,
   wedges) and none of them is measured here.
2. **A Hamming-1 flip is not a candidate in this pipeline.** Every candidate rewrites whole
   frames, and each rewritten frame's ECC word is recomputed —
   `scripts/gate_claimb_known_answer.py:156` calls `fe.update_ecc()`, and
   `scripts/gate_candidate.py:185` **rejects** a frame whose ECC field is not a correct
   recomputation (violation class `"ecc"`). The repo had already recorded this in its
   sparse-diagnosis ruling: *"A 'single-bit candidate' does not exist in this pipeline …
   frame-level it is always ≥1 content bit **plus** the ECC word."* So the census measures a
   **database property**, never an operator's candidate distribution, and a raw single-bit
   flip with a stale ECC is not a legal candidate that could be compared to the map arm at
   all.

**Therefore the honest scope is:** *how much of this device's configuration space can the
frozen database adjudicate, and what does it say about the neighbourhood of the current
state?* Everything below is that, and only that.

## 1. Method

    scripts/diag_safety_decidability.py [--bit <file.bit>] [--map <map.json>] [--json out]

Frozen data only, one real bitstream, coordinate arithmetic per `docs/freeze_format.md`
§5.3, decode groups by union-find over **shared bits** per `docs/mux_groups.md` (names are
not a grouping). Every configuration bit is assigned to exactly one class; every
database-referenced bit is flipped and its decode group re-classified as ALLZERO /
DECODED (exactly one feature matches) / MULTI (more than one matches — for a routing mux,
a two-source state) / UNDECODABLE (bits set, no pattern matches).

`scripts/diag_safety_decidability.py` is a **diagnostic, not a gate**;
`tests/test_safety_decidability.py` pins its two load-bearing pieces and shows each of
them able to fail.

## 2. The bit partition — 16,625,408 bits, 5,144 frames

| class | bits | share |
|---|---:|---:|
| routing (INT_L/R), covered by a frozen rule | 5,113,600 | 30.76% |
| routing, inside the tile type but referenced by no rule | 620,800 | 3.73% |
| content (CLBLL/CLBLM), covered by a frozen rule | 1,452,600 | 8.74% |
| content, inside the tile type but referenced by no rule | 3,616,200 | 21.75% |
| tile types with a config block but **no frozen rules** (BRAM/DSP/IOB/IOI/CLK/CMT/HCLK…) | 1,913,856 | 11.51% |
| BRAM content array | 2,457,600 | 14.78% |
| **frame ECC field** (word 50, bits 12:0, all 5,144 frames) | **66,872** | **0.40%** |
| claimed by no tile, other | 1,383,880 | 8.32% |

The ECC field is broken out because it is **not** unmodelled: it is excluded from every
tile's bit space by rule, and its semantics are fixed by `scripts/frame_ecc.py`
(`ECC_WORD = 0x32`, `ECC_MASK = 0x1FFF`) and cross-validated against Vivado known-answer
frames (prereg §6 item 4). Counting it as "undetermined" would understate what a real
candidate can account for. **The two categories a candidate needs must be kept apart:
semantic mutation bits, and required transport collateral.**

Only the two "covered by a frozen rule" rows — **39.5% of the die** — can be adjudicated
by the rules at all.

## 3. Single database-referenced bit flip, decode-group transition

Base = `gate_runs/claimb_round1_carrier_2026_08_13_erratum006/carrier.bit`:

| class | before → after | flips | share of class |
|---|---|---:|---:|
| routing | ALLZERO → **UNDECODABLE** | 4,955,945 | 96.917% |
| routing | DECODED → **MULTI** (two sources into one destination) | 97,456 | 1.906% |
| routing | DECODED → **UNDECODABLE** | 60,199 | 1.177% |
| routing | ALLZERO → DECODED | **0** | **0%** |
| content | ALLZERO → DECODED | 1,388,066 | 95.557% |
| content | ALLZERO → UNDECODABLE | 34,294 | 2.361% |
| content | DECODED → ALLZERO | 27,201 | 1.873% |
| content | DECODED → UNDECODABLE | 2,110 | 0.145% |
| content | DECODED → DECODED | 882 | 0.061% |
| content | DECODED → MULTI | 47 | 0.003% |

**The structural finding, stated exactly:** in the routing class, **no flip leaves a mux
decoding exactly one source that it was not already decoding** — `ALLZERO → DECODED` is 0 of
5,113,600 here and 0 again on the second base below, so 0 of 10,227,200, and there is no
`DECODED → DECODED` transition either. A new source *is* enabled in 97,456 cases, but only
ever **alongside** the existing one (`DECODED → MULTI`), never alone. An earlier draft
compressed this to "no flip produces a decodable route", which the `DECODED → MULTI` row
contradicts. A 7-series INT mux is 7–10 bits wide with 2- and 5-bit codes, and the
Hamming-1 neighbours of a valid code are essentially never valid codes. (On iCE40, whose
routes are enabled by single bits, flips *do* produce routes, and counting the contending
ones is a meaningful exercise. That does not transfer.)

A named positive, so MULTI is not an abstraction: in `INT_L_X0Y0`, flipping bit `16_01`
makes `IMUX_L0` decode **both** `GFAN0` and `NN2END0` — the two patterns share their four
second-stage bits and differ only in the first-stage select.

### 3.1 A second, sparser base — and a warning

Base = `build/lutram_anchored/mode3/spec_mode3.bit`: routing ALLZERO → UNDECODABLE
5,111,159 (99.952%), DECODED → MULTI **1,796** (0.035%), DECODED → UNDECODABLE 645,
ALLZERO → DECODED **0**; content ALLZERO → DECODED 1,417,319 (97.571%), ALLZERO →
UNDECODABLE 35,197.

The MULTI count moved **54×** (97,456 → 1,796) between two bitstreams of the same device,
because it scales with how much of the fabric the base design routes. **Do not turn that
into a rate law.** The iCE40 line published exactly such a law and had to retract it; the
corrected figures pointed the other way. Report MULTI **per pinned base**, with that
base's driven-mux census beside it, or not at all.

**Observed in both bases tested** (which is not the same as invariant, and two bases cannot
establish invariance): routing `ALLZERO → DECODED` = 0, and content decidability ≈97.5%.
The mechanism — Hamming-1 neighbours of a multi-bit mux code are not codes — is a property
of the encoding rather than of a design, but that is the *explanation* offered for the
observation, not a third measurement.

## 4. The map's 292 addresses — a precise, narrower statement

All **292/292** certified addresses in `maps/clb_lut_init_v1.local_map.json` are
**width-1 features on bits shared with no other feature** (`feature_widths {1: 292}`,
`shared 0`, `not_in_frozen_rules 0`). The report field is named `semantic_bits_decidable`,
and that name is the claim:

> **The map's 292 *semantic mutation bits* are decidable. That a *serialized candidate* is
> decidable does not follow and is not shown here.** A candidate also carries up to
> **12 frames × 13 = 156 ECC collateral bit positions** in word 50 — bits this census's
> partition puts outside every tile's rule space. Their semantics are fixed by
> `frame_ecc.py` rather than by prjxray, which is a different kind of warrant and has to be
> argued as such.

That the check can **fail** is machine-enforced, because a check with no discriminating
power proves nothing: `tests/test_safety_decidability.py` asserts that a `clb_mux`-shaped
4-bit `AFFMUX` member, a bit shared by two features, and a feature absent from the frozen
rules each drive `semantic_bits_decidable = False`.

## 5. Boundaries

- **A statement about prjxray's zynq7 database, not about silicon.** UNDECODABLE means
  *the database cannot say*, not *the fabric does something bad*; MULTI means *two patterns
  match*, not *a measured short*. No contention has ever been measured on silicon on this
  line, nor on the iCE40 line, whose routing candidate was built and never programmed.
- **The candidate set and the judge share an assumption.** The map's addresses are proposed
  by prjxray rule files (every entry carries `rule_file`) and only then attested by this
  repo's Vivado specimen-diff. An oracle can be made independent of the *arithmetic and the
  grouping*; it cannot be made independent of the *rules*.
- **Hamming-1 only, and Hamming-1 is not the operator's unit** (§0.2).
- **Nothing here bears on Claim B's primary metric**, which needs the board, the evaluation
  loop, and the readback interlock that is paused.

## 6. What would have to be settled before any of this could inform Claim B's safety leg

1. **Define the two arms on the pipeline's own unit.** Frame-writes with correct ECC, both
   arms under the *same* ECC rule, both drawing from the *same* certified universe as
   prereg §1 requires. A comparison against raw whole-bitstream flipping is refused there
   and stays refused.
2. **Decide how ECC collateral is accounted.** It is required, it is not a semantic
   mutation, and it is warranted by a different artifact than the map. It needs its own
   class in any safety accounting, not silent inclusion in either bucket.
3. **An independent oracle**, reimplemented from the text of `docs/freeze_format.md` §5.3
   and `docs/mux_groups.md`, never importing `scripts/` (§5.3 already mandates exactly
   this). Precedent: the iCE40 `work/oracle.py` caught a real defect its model missed.
4. **The pre-committed discriminating-power gate** (§4) runs before anything is believed.

## 7. Correction log

- **2026-08-26** — the pre-review draft was titled *"Claim B, the safety leg — feasibility
  assessment"* and stated that the leg *"settles the safety conjunct"*. Both are retracted
  (§0); it was never published under that title. The measurements are unchanged; the framing
  was wrong. Added in the same correction: the ECC collateral class (§2), the
  semantic-vs-serialized distinction (§4), the exact form of the routing finding (§3), and
  "observed in both bases tested" in place of "invariant" (§3.1).

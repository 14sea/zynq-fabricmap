# Claim B, round 1 — preregistration

**Status: DRAFT — not frozen.** One decision is open (§6, the evaluation loop). Nothing
in this document may be relied on until it is frozen: frozen means committed, its content
sha256 recorded here and in the run's artifacts, and every later artifact pinning that
hash. Until then this is a proposal, and any result produced against a draft is a pilot,
not a preregistered result.

Authorised 2026-08-10 (user): host-side preregistration, `local_map` and the safety gates
may start; **device writes are not authorised.** One whole-of-run board ruling comes after
the three gaps below are closed, not a ruling per step.

## 1. What is being tested, and what is not

**Claim B** (from `zynq-autoehw/docs/tech_report.md`, restated here so this repo does not
depend on a sibling tree at runtime): *a device-local map guides evolution better or more
safely than raw mutation.*

Round 1 tests exactly one proposition:

> Given the same base bitstream, the same writable-bit universe, the same initial
> population, the same evaluation budget, the same paired seeds, the same fitness, the
> same clock and the same board — an evolutionary search whose **mutation operator
> consults a certified device-local map** reaches a better preregistered primary metric,
> and/or a better safety record, than one whose operator does not.

**The only difference between the two arms is the mutation operator.** Everything else is
shared by construction, not by care: both arms are driven by one runner from one config,
and the arm is a parameter.

### Not in round 1

| Excluded | Why |
|---|---|
| **On-board self-cartography** | Round 1's map is *inherited from a certificate* (§3). A board that maps its own fabric is a strictly stronger claim; mixing it in means a failure cannot be attributed to the map or to the mapping process. |
| **Evolution-as-fuzzing** (map as a search byproduct) | Same reason, further out. It is the unclaimed territory (`docs/kickoff_fuzz_and_map.md` §5) and it deserves its own round. |
| **`int_pip`** (routing class) | Routing-class writes are forbidden on a working board (`docs/board_roles.md`). Only the sacrificial board may host them, and only at ladder step 4. |
| **`clb_lutram`** | Not registered, not certified. It must select schema 1.5 and go through the ladder first. |
| **`clb_mux`** | Certified, but composition is the risk here. It joins only once the known-bad composition fixture (§7) demonstrably rejects. |
| **`clb_ff_config`** | Its **addresses** were certified 2026-08-10 (`90527e6`), but nothing about its **silicon semantics** has ever been observed — this whole line has never been on a board. It gets a single-point known-answer smoke first, and only then is joining the evolvable space even discussable. |

### The comparison that is explicitly refused

Map-guided *content* mutation must **not** be compared against flipping bits anywhere in
the bitstream. That baseline touches routing, so it is both unsafe on this board and
uninterpretable: any difference would confound the map's navigational value with a
difference in the risk envelope. The baseline arm is **random-safe** — uniformly random
over *the same* certified writable universe, subject to *the same* safety gates.

## 2. Scope of the writable universe (pinned, and smaller than it looks)

Round 1 uses **`clb_lut_init` only**, and within it only what is *certified*, which is far
less than the class:

| quantity | value | source |
|---|---|---|
| class entries in the frozen manifest | 2048 | certificate `bit_class.coverage.class_entry_count` |
| **features actually attested** | **292** | 388 feature results over 292 distinct features |
| **distinct writable addresses** | **292** | one `(FAR, word, bit)` per feature; zero features carry more than one assignment |
| distinct FARs | 12 | `0x00400A20‥23`, `0x00400C1A‥1D`, `0x00400C20‥23` |
| words used | 51, 52 | — |
| mine / holdout features (address certification) | 98 / 194 | `bit_class.split` |

**The writable universe for round 1 is those 292 addresses and nothing else.** The other
1756 class entries are *named* by the frozen DB but were never attested by a specimen
pair; treating them as known would be exactly the error this repo exists to avoid.

### Three properties of that universe, measured from the built map (not assumed)

These came out of building `local_map` and they constrain the benchmark, so they are
recorded here rather than discovered later:

1. **No LUT is fully writable.** The 292 bits belong to **6 LUTs**, and every one of them
   is partial: 49, 49, 49, 51, 50 and 44 of 64 INIT bits, **92 uncertified in total**. So
   an arbitrary 6-input truth table is *not* reachable in any LUT — the uncertified
   positions keep whatever the base bitstream put there. The fitness function must
   therefore be defined over a **partially constrained** truth table, and any benchmark
   that silently assumes a free 64-bit INIT is misspecified.
2. **Consecutive INIT bits alternate frames.** For `CLBLL_L.SLICEL_X0.ALUT`, INIT[0] is in
   frame `…A20`, INIT[1] in `…A21`, INIT[2] in `…A20`, INIT[3] in `…A21`, then INIT[8] in
   `…A23` and INIT[9] in `…A22`. This is the non-obvious structure the map encodes and a
   blind operator cannot know: which bits form one truth table, and which frames a
   candidate will touch. It is a reason to expect the arms to differ at all.
3. **Every certified bit has `expected_value = 1`** — there is not one `!`-negated token in
   the set. Polarity handling is therefore **completely unexercised** by this universe, so
   a polarity bug in the operator or in a gate cannot be caught by round-1 data. This is
   named in `docs/claimb_handoff.md` as an adversarial-fixture request, because the only
   way to test that path here is against a synthetic map.

Source certificate: `gate_runs/run_2026_08_02_a/certificate.json`,
`fabric_bit_class_certificate` 1.2.0, profile `production`, `status: passed`,
`tp=262 fp=0 fn=0`, part `xc7z010clg400-1`. Its sha256 is pinned by the `local_map`
instance (§3) and re-checked by every gate.

### Collateral bits that are expected, not violations

Any write into a frame changes that frame's ECC field. The certificate records the rule
as an exclusion: `word == 50 and 0 <= bit <= 12`, *"the frame ECC field is recomputed
whenever any other bit in the same frame changes"*. The diff gate (§7) therefore admits
**exactly** two things and refuses everything else:

1. bits in the 292-address whitelist, and
2. ECC-field bits of frames the candidate actually touches.

An ECC change in a frame the candidate did not touch is a **violation**, not collateral.

## 3. The map (round 1 = inherited from a certificate)

`local_map` 1.0.0 is derived mechanically from the `clb_lut_init` certificate, and pins:
the certificate's sha256 and its `status`/`profile`, the frozen `data/MANIFEST.json`
stamp, part and device, and the 292-address universe with each address's feature name and
`expected_value` polarity.

The map adds no knowledge the certificate does not already carry. It is a *navigational
re-indexing*: certificates are organised per feature for auditing, a mutation operator
needs the inverse (which bits are addressable at all, which belong to the same LUT, which
belong to the same frame). Whether that re-indexing measurably helps navigation is
precisely the claim under test.

**The map may not be edited by hand, ever.** It is regenerated from the certificate or it
does not change.

## 4. Metrics, fixed before any run

### Primary (one, chosen in advance)

**Best holdout fitness at a fixed evaluation budget**, per arm. Secondary and reported but
not primary: evaluations to reach a preregistered fitness threshold.

Both arms get the **same** budget, and the budget is **derived from a measured evaluation
rate on this board**, not chosen as a wall-clock number — the discipline that made
zynq-autoehw's long runs interpretable (a "2 h" run derived from a v1 rate would have been
37 h on the v2 path; the calibration probe is what caught it).

### Safety metrics (all reported, every run)

- gate rejections, by gate and by reason;
- invalid compositions proposed (and, separately, invalid compositions that reached the
  device — which must be **zero**);
- reloads and recoveries, with cause;
- wedges (DEVCFG stuck / PL-AXI hang), each with the recovery that worked.

A wedge is **not** damage (`docs/board_roles.md` §"Wedge is not damage"). Recovery is
power-cycle, then the known-answer regression, and only a regression failure raises the
question of damage.

### Paired seeds and interleaving

Seeds are drawn as **pairs**: seed *s* runs in arm A and in arm B, and the two are run
**adjacent and alternating** (A,B,B,A ordering across successive pairs) so that thermal
drift and time-of-day effects fall on both arms roughly equally rather than on whichever
arm ran second. The seed schedule is generated from one preregistered master seed and
written into this document at freeze time.

### Train/holdout firewall (new — the 154 are spent)

**The 154 `clb_ff_config` holdout predictions read on 2026-08-10 are not a Claim B
holdout.** They certified *addresses*; Claim B is about *behaviour*. They are spent for
their own purpose and irrelevant to this one.

Claim B round 1 needs its own unread confirmation set:

- the evaluation conditions are split into **train** and **holdout** before any run;
- search sees train only — the operator, the fitness that drives selection, and every
  intermediate decision;
- holdout is evaluated **only** on each arm's final champion, at **high resolution**
  (enough evaluations that the resolution is finer than the arm gap being claimed);
- the holdout split, its size and its seed are frozen here.

The resolution requirement is not a nicety: zynq-autoehw's first A/B verdict was
undecidable because a 16-evaluation holdout could not resolve a difference between arms,
and the fix (1024-sample final holdout) is what made the question answerable.

## 5. Falsifiers — what would make round 1 report a negative

Preregistered, so that a negative is a result and not a reason to keep adjusting:

1. **Map-guided does not beat random-safe** on the primary metric, with the gap inside the
   reported noise band.
2. **The map does not replay from cold** — a fresh process, from the pinned artifacts
   alone, does not reproduce the same map bytes and the same candidate stream for a given
   seed.
3. **Compatibility drift is not caught** — the artifacts drift (certificate, frozen data,
   base bitstream) and no gate refuses.
4. **A known-bad composition is not rejected** host-side (§7).

Any of these is reported as-is. Relaxing a stop condition *after* it fires, using the
accounting it was placed in front of, is moving the goalposts — the ruling this line
already made once, on 2026-08-06, when T2 failed.

## 6. The evaluation loop — RULED 2026-08-10: partial-frame ICAP

Whole-bitstream reload is **not** an evaluation path. The 7z010 bitstream is ~2.08 MB;
over the 115200-baud console that is ~180 s per candidate, so the budget would be too
small to distinguish the arms — the exact failure that made the first zynq-autoehw A/B
undecidable.

### The transfer arithmetic (corrected by the user; my first estimate was wrong)

The 12 target FARs are **three groups of four consecutive frames** — `0x00400A20‥A23`,
`0x00400C1A‥C1D`, `0x00400C20‥C23` (confirmed against the built map). The proven 7-series
write shape needs **one real adjacent frame per group as a flush**, so the ideal shape is:

| | words | bytes |
|---|---|---|
| per envelope: 4 target + 1 flush frames | 5 × 101 = 505 | |
| per envelope: command overhead | ≈ 31 | |
| per envelope total | ≈ 536 | 2,144 |
| **3 envelopes** | **≈ 1,608** | **≈ 6,432** |

If it degrades to one envelope per FAR: ≈ **11.2 KB**. Both are far below 2.08 MB, but
**the budget may not be frozen against "12 × 101 words"** — that figure ignores the flush
frames and the per-envelope overhead, and it is the number a naive estimate produces.

### Implementation contract (all of it is a gate, not a style note)

1. **Every candidate rewrites all 12 target frames**, not only the frames it changed. A
   candidate then depends on the pinned base alone and never on residue from the previous
   candidate, and the two arms pay an identical transfer cost — otherwise transfer volume
   becomes a second difference between them.
2. **The three flush frames are non-writable authority.** Each must equal its pinned base
   frame **verbatim**. Falling inside the FDRI range does not make a frame writable.
3. **Frame content is produced from complete raw base frames**, never reconstructed from
   the 292-bit sparse map. Bits the map does not know keep their base values exactly.
4. **Frame ECC after an INIT change may not be assumed.** The ECC generation path must be
   cross-validated independently against **multiple Vivado known-answer frames**, and
   until it passes, nothing goes to a board.
5. **The candidate gate parses the final serialized ICAP sequence**, not the operator's
   intent: every command word, the IDCODE, each FAR, each FDRI length, the payload, the
   flush frames, and the absence of `GRESTORE`/`GTS` or any extra write.
6. **The board-side guard is a fixed range that no environment variable or CLI flag can
   widen.** The sibling `icaphw.c`'s `ICAPHW_FAR_LO`/`HI`/`MAX_FDRI` overrides must **not**
   be carried across as they are — an overridable guard is not a guard.
7. **`PCAP_PR` is restored with try/finally semantics**: on failure too, the code attempts
   to restore it to 1 and reports ICAP health/status rather than leaving the device in a
   half-configured state.
8. **Read back the 12 target frames after every candidate write** and recompute the actual
   frame-diff hash. Fitness is scored **only** if the readback equals the candidate.
9. **The phenotype manifest pins** the base bitstream, the 12 base frames, the 3 flush
   frames, and all of their hashes.
10. **Frame ownership is explicit, and the gate never relaxes for our own logic.** The
    evolvable LUTs, the scorer, and the HWICAP/control logic must be placed so their
    ownership of frames is separated and stated. Within the 12 target and 3 flush frames,
    **every bit except the 292 whitelisted addresses is determined by the pinned base
    authority** — including bits that belong to our own scorer. "That is my own logic, so
    it is safe to differ" is exactly the reasoning that turns a gate into a formality.

### The two gate semantics — they are different rules, not one rule twice

Ruled 2026-08-10. A single "must match the base except the whitelist" rule applied to all
15 frames would be wrong, because the flush frames admit no exception at all:

| frames | what may differ |
|---|---|
| **12 target frames** | **only** the 292 whitelisted bits, plus the frame ECC *correctly recomputed* for the resulting content. Nothing else, in any word. |
| **3 flush frames** | **nothing.** All 101 words must equal the pinned base **verbatim, including word 50's ECC.** Zero difference. |

The three successor relations — `0x00400A23`→`0x00400A80`, `0x00400C1D`→`0x00400C1E`,
`0x00400C23`→`0x00400C80` — are **derived from the device frame sequence and pinned into
the manifest**, never recomputed as integer FAR+1 at use time.

### Carrier placement constraints on the flush frames (stronger than "no dynamic content")

The two cross-column flush frames (`major 21 minor 0`, `major 25 minor 0`) must carry:

- **no live carrier cell**, and
- **no scorer, HWICAP or control logic**, and
- **no routing that crosses the resources those frames own**.

Writing identical bytes back is not sufficient grounds to relax this: a reconfiguration
write can disturb the frame's resources **transiently** even when the content is
unchanged. The case that must never exist is **HWICAP writing a frame that carries its own
control path** — the write would be able to interrupt the mechanism performing it.

**And placement constraints are not proof.** The routed carrier must *demonstrate* target
and flush frame ownership isolation from the DCP or from readback. A pblock is an
instruction to the tools; what the tools actually did is a separate question, and only the
second one is evidence.

### The budget still cannot be frozen here

The transfer size is not the evaluation rate. Before the arms run, an **engineering
calibration** measures the real thing, and it deliberately touches **no** part of the new
behavioural holdout:

1. load golden;
2. apply one pre-fixed LUT known-answer candidate;
3. read back and verify;
4. restore base;
5. repeat enough times to measure end-to-end write + readback + score latency **and the
   failure rate**.

The measured rate derives the evaluation budget, the seed schedule is then written into
§4, and only then is this document frozen. Calibration is itself a device write and waits
for the single whole-of-run board ruling.

## 7. Machine gates that must exist before any device write

Per the ruling, all of these are host-side and all must be in place first:

| gate | refuses |
|---|---|
| `local_map` 1.0.0 + **independent verifier** | a map that does not descend from a passing production certificate, or whose universe disagrees with it |
| `phenotype_manifest` | a run whose base bitstream, part, pblock, allowed FARs, whitelist or 50 MHz clock requirement does not match the pinned envelope |
| **candidate diff gate** | any bit outside the whitelist, any unknown combination, any invalid codeword — evaluated on the *actual* frame diff, not on the operator's intent |
| **known-bad composition fixture** | must be **rejected host-side**; a gate that has never refused anything has not been shown to work |
| **run log** | records map hash, base hash, candidate and frame-diff hashes, seed, budget, arm, fitness, and every recovery |
| **board identity gate** | writes without a role, with the wrong `boardid`, or on the wrong board — **no flag override** |

The independent verifier and the adversarial fixtures are **not written by me**:
`docs/workflow.md` puts the `local_map` schema, the verifiers that judge its output and the
known-answer fixtures on the author's side, for the reason that makes this line work — a
gate written by the party that wrote the thing under test is not a gate. Requested in
`docs/claimb_handoff.md`.

## 8. Board, and the two facts that are board-specific

Round 1 runs on **EBAZ4203 `17A6`**, role `verify` (`docs/board_roles.md`). The **EBAZ4205
reference board is not used** — it holds the M1 golden environment and its recovery is
JTAG-only.

Two things do not transfer between the boards, and both have bitten this line before:

1. **FCLK0.** The 4205's magic `0x00200a00` written to a 4203 gives **80 MHz, not 50** —
   its IO PLL is 1600 MHz, not 1000. The clock is set and verified by decoding the PLLs
   (`scripts/board_set_fclk50.py --verify-only`), never by writing a remembered constant.
2. **The JTAG adapter is shared, its settings are not.** The HS3 that reaches the 4203 is
   the 4205's cable; `ebaz4205.cfg`'s `adapter speed 5000` was tuned for 4205 flying leads
   and is a parameter to verify on the 4203, not a given. (The 4203 boots from TF card and
   its control plane is UART; JTAG is a convenience here, not the recovery path.)

## 9. First contact order (fixed; deviation ends the session)

1. UART and 5 V only. **No PL write.**
2. Read back and check `boardid=17A6` and `role=verify`.
3. `board_set_fclk50.py --verify-only` — confirm the measured clock really is 50 MHz.
4. Run the existing known-answer regression to establish a pre-write baseline.
5. Load golden, restore golden; confirm mailbox, reload and cold-boot replay.
6. Apply **one** precomputed LUT-INIT known-answer mutation; restore; re-run the baseline.
7. Only after that fixed smoke sequence passes, start the preregistered paired arms.

**Stop immediately** on: a gate crash, an identity or clock mismatch, a diff outside the
envelope, UART disappearing, abnormal current, or a DEVCFG wedge. A gate that crashes has
not judged anything — that is a stop, not a retry. On a wedge: power-cycle, run the
known-answer regression, and do **not** conclude hardware damage from the wedge itself.

## 10. Freeze

At freeze this document is committed, its content sha256 recorded in the commit message
and in `local_map`/`phenotype_manifest`/run log, and the seed schedule written into §4.
Any later change means a new preregistration and a new round — not an edit.

# `clb_ff_config` 184-specimen builder — design, for review before any code

**Status: DESIGN, revision 3 after two review rounds. No builder code, no formal
bitstream.** The
commitment is already frozen (`2b40693`, sha256
`5440ef27acbd5b4f624cae54f4ffad89b3f656c1e6e5fa35b29226ff0d1b2e51`). That ordering is
the whole evidentiary value of this class, and it constrains what the builder is allowed
to be: **a deterministic executor of a plan that already exists**. If the builder decides
anything about the key space, the split, the coverage denominator or the pair set, then a
second plan exists, it was written after the freeze, and the commitment no longer covers
what was built.

Every number, site, tile, frame address and word offset below was recomputed from
`gate_runs/run_2026_08_05_ff/predictions.json` and `data/prjxray/zynq7/` while writing
this document. None of it is quoted from memory or from a previous round's prose.

**Revision 2** answered a review that independently reproduced the site mapping and then
found four defects in the surrounding claims. **Revision 3** answers the next round, which
found two more — one of them a defect revision 2 introduced. The site mapping (§3.2, §3.3)
and the 120/184 topology are unchanged and have now survived two independent
recomputations; the four rulings in §11 stand. What has moved, twice, is the *epistemic*
status of the claims around the mapping and the strictness of the checks. §11.1 lists all
six corrections.

The revision-3 changes: §5.3's comparison domain is **tiered**, because revision 2's
version would have rejected correct specimens; §1.3 resolves a contradiction between
authority B and cold-archive testing; §7.2 defines how a `failed` node is retried; and
§3.3 stops calling a site "legal" when the freeze only says it exists and is not
prohibited.

Reviewer's job for this revision: **falsify §5.3's tier boundaries and §7's recipe
domain.** Tier 2's membership in particular is computed from the netlist rather than
declared, and if that computation is wrong the gate silently narrows.

---

## 1. Two authorities, and 120 belongs to the second one

An earlier draft of this section said the commitment was the only authority and listed
**120** as something recomputed from it. That was wrong, and the distinction matters
enough to state before anything else.

**Authority A — the commitment (`predictions.json`), sole and sufficient.** The scientific
content: the key space, the pair set, the split, and the coverage denominator. Every one
of these is a structural field or a direct consequence of one.

| assertion | required value | where it comes from |
|---|---|---|
| sha256 of the committed file | `5440ef27…2e51` | recomputed over the bytes on disk |
| specimens | **184** | `len(specimens)`, and `totals.specimens` |
| site instances | **8** | distinct `site` |
| specimens per instance | **23** | grouped count, all 8 equal |
| predictions | **176** | `len(predictions)`, and `totals.predictions` |
| canonical accounting pairs | **168** | `gate_measure_ff.committed_pairs()`, unordered key |
| directed observations | **176** | same call, `(comparison, asserting)` key |
| mine / holdout predictions | **22 / 154** | `split`, and `totals.holdout_predictions` |
| coverage denominator | **176 / 176** | `data/MANIFEST.json` class entries |

**Authority B — the pre-freeze builder plan, for the execution mapping only.** The
commitment's `totals` carry **184 / 176 / 154 and nothing else**. There is no `node_type`
field, no `derived_from`, and no count of implementations. **120 is not readable from the
JSON.** It is what you get by applying the execution topology — which variants need their
own place-and-route and which are cell-property derivations — to the committed variant
names and their `description` strings. That topology was fixed before the freeze, in
`docs/ff_preregistration_plan.md`, and it is the thing that says 8 × 15 = 120.

So the builder pins **both**:

| pinned artifact | sha256 | why |
|---|---|---|
| `gate_runs/run_2026_08_05_ff/predictions.json` | `5440ef27…2e51` | authority A |
| `docs/ff_preregistration_plan.md` **as of `2b40693`** | `ac9dbab8ba299360b924dec20507ed3c4f014b276cd1e20d82c25d3e92997a64` | authority B |

**The plan document has already been rewritten since the freeze.** `a643992` updated it
from DRAFT to COMMITTED, so the working-tree copy hashes to `c16d10c5…`, not `ac9dbab8…`.
That is precisely the failure this pin exists to prevent: without it, a later edit to the
plan's prose would silently redefine what "120" means while every hash still verified. It
also means the frozen bytes exist only in git history — see §1.3, which is why a
certification run requires a clone rather than an archive.

Both authorities are checked at startup, before any Vivado process is launched. These are
not logged and continued past; each is a hard exit. Confirmed by recomputation at design
time: 184 = 8 × 23; 176 predictions collapse to 168 canonical pairs because the 8
complementary `CLKINV`/`NOCLKINV` pairs assert in both directions over one bit; and
120 = 8 × 15 **under authority B**, cross-checked against the 184 by requiring
15 + 8 = 23 per instance.

**The builder may not derive a key space of its own, and may not build a subset.** There
is no `--only`, no `--features`, no `--continue-from`. The one permitted scope flag is
`--instance <site>`, and it is doubly constrained:

- it **accepts only a site whose `split` is `mine` in the commitment** — today that is
  exactly `SLICE_X2Y25`. A holdout site passed to `--instance` is a hard exit. The flag
  exists for the §10 smoke test, and a flag that can single out a holdout instance is a
  flag that can be used to look at holdout evidence one convenient piece at a time;
- it **cannot produce a certifiable run** (§7.6 forbids it arithmetically, not by
  convention).

### 1.1 The builder is forbidden to read the predicted bits

The builder consumes only the *structural* fields of a specimen record: `specimen_id`,
`site`, `variant`, `tile`, `tile_type`, `site_prefix`, `split`, `pair_with`,
`build_seed`. It must never read `predicted_assignments`, `expected_value`,
`expected_transition`, or the `feature` of any prediction.

This is not tidiness. A builder that can see the expected bits is a builder that can be
tuned — by me, unconsciously, one "fix" at a time — until the specimen produces them.
Measurement belongs to `gate_measure_ff.py`, which reads the same commitment
independently. Enforced by a unit test that parses the builder's source and fails on any
reference to those keys.

### 1.2 Variant coverage is closed at both ends

The builder holds a `VARIANTS` table keyed by variant name. At startup it asserts
**set equality** between the variants named in the commitment and the variants it knows
how to build — not containment in either direction. An unknown variant in the commitment
is a hard exit (the builder is out of date); a variant in the table that the commitment
never uses is also a hard exit (dead recipe, or someone edited one and not the other).

### 1.3 Authority B needs git history, so the formal precondition is a clone

This forces a decision, because the working-tree copy is *deliberately* not the frozen
text: the only place the frozen bytes exist is the git object at `2b40693`. Revision 2 said
the builder runs `git show 2b40693:docs/ff_preregistration_plan.md` **and** that the suite
must pass from `git archive` — and an archive has no `.git`, so authority B could not have
been verified there at all. The two requirements contradicted each other.

**Ruled: the formal precondition is a fresh `git clone`, not an archive.** Stated
explicitly so nobody has to infer it:

- a certification run requires a working tree **whose git history contains commit
  `2b40693`**. The builder resolves the frozen text with
  `git show 2b40693:docs/ff_preregistration_plan.md`, hashes it, and requires
  `ac9dbab8…97a64`;
- if git history is unavailable, or the object is missing, the builder **exits** — it does
  not fall back to the working-tree copy, which would silently substitute `c16d10c5…` for
  the frozen plan and defeat the entire pin;
- `git archive` remains the cold-start test for everything that does **not** depend on
  history (§10 step 1). What it tests about authority B is the refusal itself: with no
  `.git` present, the builder must decline to start. That is history-independent, and it
  is a real assertion rather than a skipped test.

The rejected alternative is worth recording: copying the frozen bytes into a tracked
artifact in the current tree would let an archive verify authority B, but it puts the same
bytes in two places, and the copy is then something a later editor can "tidy". If that
option is ever taken it must be a **byte-for-byte** copy of the `2b40693` blob — writing a
fresh machine-readable plan instead would be exactly the post-freeze second plan this whole
document exists to prevent.

---

## 2. 23 specimens, 15 implementations, per instance

Variant names and their meanings come from the commitment; the "own P&R?" column is
**authority B** (§1), not something the JSON states. Identical for all 8 instances.

| # | variant | own P&R? | derived from | what changes |
|---|---|---|---|---|
| 1 | `base` | **yes** | — | 8× FDRE, INIT=1, CE and R driven, sync, non-inverted clock |
| 2–9 | `zrst_{A,A5,B,B5,C,C5,D,D5}FF` | **yes** ×8 | — | that one FF becomes **FDSE** (SRVAL=1) |
| 10 | `ce_tied` | **yes** | — | CE tied to `1'b1` |
| 11 | `sr_tied` | **yes** | — | R tied to `1'b0` |
| 12 | `async` | **yes** | — | FDCE, asynchronous clear |
| 13 | `latch_base` | **yes** | — | **4×** FDCE with `IS_C_INVERTED`, `AFF..DFF` |
| 14 | `latch` | **yes** | — | **4×** LDCE, `AFF..DFF` |
| 15 | `clkinv` | **yes** | — | `IS_C_INVERTED` on the clock pin |
| 16–23 | `zini_{A,A5,B,B5,C,C5,D,D5}FF` | **no** ×8 | `base` | that one FF's `INIT` 1 → 0 |

**15 own P&R + 8 derived = 23. × 8 instances = 120 implementations, 184 bitstreams.**

### 2.1 What "derived from `base`" means mechanically

`INIT` on a flip-flop is a **cell property**, not a netlist or placement change. The 8
`zini_*` specimens therefore reuse `base`'s post-route checkpoint:

```
open_checkpoint   <base>/base.dcp         # the routed checkpoint, not a re-implementation
set_property INIT 1'b0 [get_cells <the one FF>]
write_checkpoint  <zini_XFF>/derived.dcp  # the state the bitstream is actually written from
write_bitstream   <zini_XFF>/spec.bit
```

`place_design` / `route_design` are **not** re-run, and `base.dcp` is **not** modified.

**The derived checkpoint is saved, and this is a correction to the earlier draft.** That
draft hashed only `base.dcp` — but `base.dcp` holds `INIT=1`, while the derived specimen's
readback and bitstream are `INIT=0`. The design state the attestation described was
therefore never the design state that produced the bitstream, and no artifact on disk held
it. Each derived specimen records:

| field | what it pins |
|---|---|
| `source_base_dcp_sha256` | which routed checkpoint was opened |
| `derived_dcp_sha256` | the modified state the bitstream was written from |
| `readback_sha256` | the resolved placement/property readback of that state |
| `bitstream_sha256` | `spec.bit` |

Still one P&R serving many bitstreams — 120 is untouched — but the state that the
attestation talks about now has a preservable integrity anchor instead of being
reconstructible only in principle. §9's limit still applies to all four: they anchor
integrity, they do not prove provenance.

Three invariants are asserted after the property change and before `write_bitstream`; any
failure is a hard exit for that specimen:

1. exactly one cell matched the `get_cells` (§5 match discipline applies here too);
2. `ROUTE_STATUS` is unchanged from the value recorded in `base`'s readback — as a
   completion flag only, per §9; path identity comes from item 3;
3. the readback is identical to `base`'s **except** for the single `INIT` attribute that
   was deliberately changed — and here that means **all three of §5.3's tiers, shared nets
   included**, not just tiers 1 and 2.

The asymmetry in item 3 is deliberate and is the one place full identity is legitimate:
§5.3 has to tier its comparison because a pair's two ends are two *different
implementations*, whose shared nets differ on purpose. A derived specimen is not a
different implementation — it is the same routed checkpoint with one cell property
changed, so nothing in the netlist or the routing has any business differing. Demanding
less here would waste the strongest check available in the whole design.

What is deliberately *not* checked is whether the resulting bitstream differs from
`base`'s in the predicted bit. That is the measurement, it is pre-registered, and a
builder that checked it would be scoring its own work.

### 2.2 The risk this carries, and how it was ruled

Reusing a checkpoint means a defect in `base` propagates silently into 8 specimens and
into 8 of the instance's predictions. The mitigation is that `base` is also an endpoint of
20 of the instance's 21 pairs — every one except `latch`↔`latch_base` — so a broken `base`
fails loudly across the whole instance rather than quietly in one corner. The alternative,
re-implementing all 23, costs 64 more P&R runs and **changes 120, which is fixed by
authority B** — so it is not available as a builder change.

**Ruled 2026-08-05: reuse accepted, derived checkpoint preserved** (§11 item 1). The
reviewer's point was that the risk was never the shared P&R; it was that the design state
being attested had no artifact. §2.1's `derived.dcp` closes that without touching 120.

---

## 3. Target → anchor / keeper mapping (the conflict, resolved)

### 3.1 The conflict is real and the LUTRAM rule cannot be reused

`docs/lutram_anchored.md` fixed the keeper at **`SLICE_X9Y25`**, the SLICEL of the target
tile. That rule is unusable here, for two independent reasons:

1. **`SLICE_X9Y25` is itself target instance 6.** A keeper there would occupy the site
   under test.
2. **The 8 targets fill 4 tiles completely** — both slices of each of `CLBLL_L_X2Y25`,
   `CLBLL_R_X11Y25`, `CLBLM_L_X6Y25`, `CLBLM_R_X17Y25`. So "the other slice of the target
   tile" is a target for *every* instance, not just instance 6. The LUTRAM rule does not
   fail at one site; it fails at all eight.

The FF LATCH probe had already moved off that rule: `vivado/specimen/build_ff_probe.tcl`
uses `asite = SLICE_X4Y20` and `asite2 = SLICE_X2Y20` for target `SLICE_X2Y25` — keeper in
the **same column, row 20**, anchor **two columns over, row 20**. That is the geometry that
measured FP=0, and it generalises without collision.

### 3.2 The rule

For a target `SLICE_X{n}Y25`:

- **keeper** (`anchor_ff2`, the clocked column keeper) = `SLICE_X{n}Y20` — same CLB
  column, row 20.
- **anchor** (`anchor_lut1`, `anchor_lut2`, `anchor_ff`, `q_reduce1`, `q_reduce2`) =
  `SLICE_X{n+2}Y20` — two columns over, row 20.

A rule, not a table of hand-picked sites: the table below is generated from it and checked,
so a ninth instance could not be added by quietly inventing a site for it.

### 3.3 The mapping, and the collision proof

| # | target site | target tile | split | keeper (same column, Y20) | anchor (column +2, Y20) |
|---|---|---|---|---|---|
| 1 | `SLICE_X2Y25` | `CLBLL_L_X2Y25` | mine | `SLICE_X2Y20` (SLICEL, `CLBLL_L_X2Y20`) | `SLICE_X4Y20` (SLICEM, `CLBLM_R_X3Y20`) |
| 2 | `SLICE_X3Y25` | `CLBLL_L_X2Y25` | holdout | `SLICE_X3Y20` (SLICEL, `CLBLL_L_X2Y20`) | `SLICE_X5Y20` (SLICEL, `CLBLM_R_X3Y20`) |
| 3 | `SLICE_X14Y25` | `CLBLL_R_X11Y25` | holdout | `SLICE_X14Y20` (SLICEL, `CLBLL_R_X11Y20`) | `SLICE_X16Y20` (SLICEM, `CLBLM_L_X12Y20`) |
| 4 | `SLICE_X15Y25` | `CLBLL_R_X11Y25` | holdout | `SLICE_X15Y20` (SLICEL, `CLBLL_R_X11Y20`) | `SLICE_X17Y20` (SLICEL, `CLBLM_L_X12Y20`) |
| 5 | `SLICE_X8Y25` | `CLBLM_L_X6Y25` | holdout | `SLICE_X8Y20` (SLICEM, `CLBLM_L_X6Y20`) | `SLICE_X10Y20` (SLICEM, `CLBLM_L_X8Y20`) |
| 6 | `SLICE_X9Y25` | `CLBLM_L_X6Y25` | holdout | `SLICE_X9Y20` (SLICEL, `CLBLM_L_X6Y20`) | `SLICE_X11Y20` (SLICEL, `CLBLM_L_X8Y20`) |
| 7 | `SLICE_X24Y25` | `CLBLM_R_X17Y25` | holdout | `SLICE_X24Y20` (SLICEM, `CLBLM_R_X17Y20`) | `SLICE_X26Y20` (SLICEL, `CLBLL_R_X19Y20`) |
| 8 | `SLICE_X25Y25` | `CLBLM_R_X17Y25` | holdout | `SLICE_X25Y20` (SLICEL, `CLBLM_R_X17Y20`) | `SLICE_X27Y20` (SLICEL, `CLBLL_R_X19Y20`) |

Checked at design time, and to be re-checked by unit test at build time:

- **8 targets + 8 keepers + 8 anchors = 24 distinct sites.** No site is used twice in any
  role, anywhere in the matrix.
- **Within an instance, `{target, keeper, anchor}` are three distinct sites** — trivially,
  since the columns are `n`, `n`, `n+2` and the rows are 25, 20, 20.
- **No anchor or keeper can ever be a target**, by construction: every target is at row
  **Y25**, every anchor and keeper at row **Y20**. This covers the reviewer's request to
  check the pre-existing fixed resources — `SLICE_X2Y25` (the mine site) included — because
  the row separation is what makes the check total rather than case-by-case.
- **All 16 anchor/keeper sites exist and are not marked prohibited in the freeze**: present
  in `tilegrid.json`, and `prohibited_sites` is `[]` on all 8 distinct anchor/keeper tiles.
  That is the whole of what the freeze can say. It is **not** a claim that each site can
  host the cells this design asks of it — the freeze describes the fabric, not the
  placer's rules. Whether `A6LUT`/`B6LUT`/`C6LUT`/`D6LUT`/`AFF` actually take those cells
  at that site is settled by Vivado and by the resolved readback of §5.2, which hard-fails
  on any requested-versus-resolved disagreement. This repo has already been bitten by
  assuming a site could host something it could not: `A5FF` and its siblings are BEL type
  `FF_INIT` and refuse `LDCE` outright, and the keeper site validated on one lutram pair
  turned out to be illegal in another mode.
- Anchor site type varies (SLICEM for instances 1, 3, 5; SLICEL otherwise). The BELs the
  anchor needs are named in both types, but per the point above that is an expectation to
  be confirmed by readback, not a guarantee. Recorded so the reviewer can object.

### 3.4 Why row 20 — an isolation hypothesis, with its geometric precondition proven

**What follows is a hypothesis supported by one measurement on the mine site, not a
proof.** The distinction was blurred in the earlier draft, which said row 20 was "proven
from the freeze". The freeze proves a *geometric* fact. It cannot prove a *functional*
one: nothing in `tilegrid.json` establishes that a flip-flop at `SLICE_X{n}Y20` causes the
clock branch serving `SLICE_X{n}Y25` to stay enabled. That claim rests on the LATCH
probe's FP=0 result at one site, and it is exactly the kind of "absence of unattributable
bits" evidence this repo has already had to retract once for overreaching.

The hypothesis: the keeper holds the column's clock branch enabled regardless of what the
target does with the clock, provided it is in the same clock region and same CLB column.

The **precondition** — same clock region, same CLB column — is what the freeze does
establish: the target tile and its keeper tile have the **same `CLB_IO_CLK` base address**
(same half, same frame row, same frame column) and differ only in word offset.

| target tile | keeper tile | shared baseaddr | target word | keeper word |
|---|---|---|---|---|
| `CLBLL_L_X2Y25` | `CLBLL_L_X2Y20` | `0x00400A00` | 51 | 40 |
| `CLBLL_R_X11Y25` | `CLBLL_R_X11Y20` | `0x00401180` | 51 | 40 |
| `CLBLM_L_X6Y25` | `CLBLM_L_X6Y20` | `0x00400C00` | 51 | 40 |
| `CLBLM_R_X17Y25` | `CLBLM_R_X17Y20` | `0x00401480` | 51 | 40 |

The column X2 word ladder, read out of the freeze, shows why 51 and 40 are safe neighbours
and not an accident:

```
Y18=36  Y19=38  Y20=40  Y21=42  Y22=44  Y23=46  Y24=48  [word 50]  Y25=51  Y26=53
```

Two words per CLB row, with **word 50 skipped** — that is the ECC/HCLK word (word 50 bits
0–12 are the frame ECC, and HCLK tile bits live above that range in the same word). So,
geometrically:

- keeper occupies words **40–41**, target occupies words **51–52**: they share frames but
  **never share a word**;
- the HCLK word sits **between** them — the resource the keeper is *hypothesised* to hold
  up. That the keeper's bits neighbour that word is a geometric fact; that the keeper's
  presence keeps the branch enabled is the hypothesis, and the two must not be conflated.

**The cost of this choice, stated plainly:** the keeper's bits live in the *same frames* as
the target's. If a keeper bit ever moved between the two ends of a pair, it would land in
the target's frames. Keeper invariance is therefore not assumed — §5.3 requires it to be
demonstrated per pair, every run — and if the hypothesis above is false, the symptom is
movers appearing in the five-bucket accounting, which is where it belongs and where the
formal measurement will refuse to certify.

### 3.5 The anchor *cells* sit in a different frame column — which is not a claim about routing

The anchor's CLB coordinates are two columns over, in a **different** frame column
(e.g. target `CLBLL_L_X2Y25` is frame column 20; anchor tile `CLBLM_R_X3Y20` is column 21;
verified for all 8 instances). So **the anchor's own CLB configuration bits** cannot share
a frame with the target's.

**That is all it establishes.** The earlier draft went further and said anchor bits
"cannot perturb the target frames' ECC" — an overreach. A cell's coordinates do not bound
the routing that reaches it: nets between the IO ring, the BUFG, the anchor and the target
may be routed through interconnect tiles in the target's column, whose bits live in the
target's frames. Placement is constrained; routing is not, beyond what
`DONT_TOUCH` + fixed `LOC`/`BEL` imply.

What actually keeps routing out of the diff is that it is *identical at both ends of a
pair*, and that is measured, not decreed — §5.3 compares the routing readback pairwise,
and anything that still moves is adjudicated by the five-bucket accounting in the formal
measurement. The keeper's in-frame position is a deliberate exception taken for the clock
hypothesis in §3.4; the anchor's out-of-column position is a useful reduction of exposure,
not an immunity.

---

## 4. Anchor structure, and what must match within a pair

Carried over from `specimen_ff_probe.v` / `build_ff_probe.tcl`, which measured
`ownership_unknown = 0` and `unattributed = 0`:

| cell | site | BEL | purpose |
|---|---|---|---|
| `anchor_lut1` | anchor | `A6LUT` | consumes `i[5:0]` |
| `anchor_lut2` | anchor | `B6LUT` | consumes `ce`, `rst` |
| `anchor_ff` | anchor | `AFF` | consumes the buffered clock |
| `q_reduce1` | anchor | `C6LUT` | reduces `Q[7:0]` so `q` stays one port |
| `q_reduce2` | anchor | `D6LUT` | second reduction stage |
| `anchor_ff2` | **keeper** | `AFF` | clocked column keeper |

All six are `DONT_TOUCH`, all have explicit `BEL` then `LOC`, and every LUT carries
`LOCK_PINS`. The port set (`i[5:0]`, `clk`, `ce`, `rst`, `o`, `q`, `anchor_o`, `anchor_o2`)
is **identical in every variant including the 4-element latch pair**. That **eliminates
one cause** of IO-ring and BUFG movement — differing port sets, which is how different
modes came to trim different IBUFs and drop the BUFG in the lutram round. It does not
establish that the IO ring and BUFG were implemented identically: an identical port set is
an identical *input* to the tool, not an identical *result*. What their bits actually did
is settled by §5.3 and, in the end, by the five-bucket accounting.

**But the anchor's connectivity is not identical across all 23 specimens, and requiring
that would be a design error.** The reduction cells exist in every topology, yet what they
are wired to differs by family: in the 8-element variants `q_reduce1`/`q_reduce2` consume
eight real `Q` outputs, while in the 4-element `latch`/`latch_base` pair four of their
inputs are tied constants. A checker demanding all-23 identity would fire on a correct
build, every run, and the only way to keep it quiet would be to weaken it into something
that no longer catches anything.

**The invariant the reviewer should hold me to is per pair, not per instance:** for each of
the **168 committed endpoint pairs**, the anchor and keeper structure must match *between
that pair's two ends*. Within a family it is then identical by consequence; across the
4/8-element boundary nothing is compared, because no committed pair crosses it — `latch`
pairs only with `latch_base`. That is checked in §5.3.

---

## 5. Per-mode cell contract and match discipline

### 5.1 Constraint order and pin locking

- **`BEL` before `LOC`, always.** With `LOC` first the placer picks a BEL itself and the
  next cell collides ("bel is occupied"). Measured, 2026-08-04.
- **`LOCK_PINS` on every LUT.** Vivado permutes `I0..I5` onto `A1..A6` and rewrites `INIT`;
  without locking, logical index ≠ physical and only the permutation-invariant endpoints
  agree.
- **Never `set_property BEL` on a macro's child** — silent no-op. Every storage element and
  LUT is instantiated as a leaf primitive with its own name.
- **Never rely on `get_cells <bare name>` for a cell inside a generate block** — it matches
  nothing, constrains nothing, and exits 0. Hierarchical names are used throughout.

### 5.2 Match discipline: zero, many, and disagreement are all hard failures

Every `get_cells` in the flow goes through one helper. It takes the pattern **and the
expected count**, and exits non-zero unless exactly that many cells matched. There is no
`catch` that continues, and no warn-and-proceed path — the probe's
`catch {set_property BEL …}` + `SPECIMEN_WARN` pattern is removed for the formal builder.

After placement, the flow reads back `LOC` and `BEL` for **every** constrained cell and
writes them to `readback.tsv`. The builder then asserts, per specimen:

- every target storage element and LUT resolved to the **site and BEL that were requested**;
- the number of resolved target cells equals the mode's expected count (8 or 4 storage,
  8 or 4 LUT5, plus reductions);
- no cell resolved into a site outside `{target, anchor, keeper}`.

A requested-vs-resolved disagreement is a hard failure **even when Vivado exits 0 and
produces a valid bitstream** — that combination has already happened three times in this
repo, which is why it is checked rather than trusted.

### 5.3 Pairwise structural identity (the check that carries §3.4 and §3.5)

**Granularity: the 168 committed endpoint pairs, not all 23 specimens.** The comparison is
driven by `gate_measure_ff.committed_pairs()` reading the commitment — the same pair set
the measurement will use — so the builder cannot invent a comparison the plan does not
contain, and the 4-element family is never compared against the 8-element one because no
committed pair crosses that boundary.

`LOC`/`BEL` alone is far too narrow: two builds can agree on every placement and still
differ in inversion attributes, pin mapping or routing. But revision 2 over-corrected in
the other direction, and that error would have been worse than the one it fixed.

**Why "every net touching an anchor or keeper pin" was wrong.** Those nets also serve the
target, and several variants exist precisely to change the target end of them. A gate
demanding full sink-set and `ROUTE` equality on shared nets would reject *correct*
specimens, by design, every run:

| shared net | why its two ends legitimately differ |
|---|---|
| `ce` | reaches `anchor_lut2` **and** the target FFs — and `ce_tied` exists to tie the target's CE to `1'b1`, removing those sinks |
| `rst` | same shape; `sr_tied` ties the target's R to `1'b0` |
| `rst` (again) | `zrst_*` turns one FF from FDRE into FDSE, moving that pin from `R` to `S` |
| `qb[*]` → `q_reduce1/2` | the 4-element family drives four of those inputs with constants, the 8-element family with real `Q` |
| `clk_g`, `i[5:0]` | their routing trees contain target branches by construction |

A check that fires on a correct build is not a strict check; it is a check that will be
weakened until it catches nothing. So the domain is **tiered by what the net actually is**.

**Tier 1 — hard equality, always.** Local, placement- and attribute-level facts about the
six anchor/keeper cells themselves:

| domain | why it is in |
|---|---|
| `REF_NAME` / `PRIMITIVE` of every anchor and keeper cell | an `FDRE` silently becoming something else changes slice control bits |
| `LOC` and `BEL` | placement |
| `INIT`, `IS_C_INVERTED`, `IS_G_INVERTED`, `IS_D_INVERTED`, `IS_R_INVERTED`, `IS_CE_INVERTED` | inversion attributes are configuration bits; the LATCH probe showed a slice asserting `CLKINV` with `IS_G_INVERTED = 0` |
| `LOCK_PINS` and the resolved logical→physical pin mapping | an unlocked permutation rewrites `INIT` without moving a cell |
| **the local driver/sink identity seen at each anchor/keeper pin** — which net, driven by which cell pin | catches a rewired anchor without asserting anything about the rest of that net |

**Tier 2 — hard equality on dedicated nets only.** A net is *dedicated* when its driver
and **every** sink lie inside the anchor/keeper subgraph. For those, full endpoint sets and
the sorted `ROUTE`/PIP list must match. The builder **computes** the dedicated set from the
netlist and asserts it equals the expected set — so a net silently gaining a target sink is
itself a failure, rather than quietly dropping out of tier 2. Expected, from the specimen
source: `w1` (`anchor_lut1` → `anchor_lut2`), `w2` (`anchor_lut2` → `anchor_ff.D` and
`anchor_ff2.D`), and the `anchor_o` / `anchor_o2` output nets. `w2` is the one that
physically spans the anchor column and the keeper column, so it is the most valuable member
of this tier, not an incidental one.

**Tier 3 — diagnostic only, never a FAIL.** Nets shared with the target: full readback
(endpoints, `ROUTE`, PIP list) is captured and preserved in the run record, and is
reported, but **the whole routing tree may not fail a pair**. Extracting only the branch
that reaches the anchor/keeper sink would make this enforceable, and if that extraction is
ever implemented and shown reliable, the branch — and only the branch — may be promoted to
tier 2. Until then, an unreliable extraction used as a gate is worse than no gate: it
fails correct builds unpredictably, which teaches everyone to ignore it.

Explicit non-claims, so this check is not read as more than it is:

- **`ROUTE_STATUS` remains a completion flag only.** Two builds can both report `ROUTED`
  over entirely different paths; that is why per-net `ROUTE`/PIP readback exists at all,
  and why `ROUTE_STATUS` is never treated as evidence of path identity.
- **This does not claim the two ends contribute identical bits**, and after the tiering it
  claims less than before. It is a design-state comparison, not a bitstream comparison.
  Any bit difference that survives is adjudicated by the formal measurement's five-bucket
  accounting under the fixed 1.4 FP rule — the builder does not pre-empt that verdict, and
  must not, since it is forbidden to look at the predicted bits at all (§1.1).
- A pair whose ends disagree **in tier 1 or tier 2** fails that pair, and therefore the run
  (§7.6), reported with the differing keys rather than summarised as "structure changed".
  A tier 3 difference is recorded and reported and does **not** fail anything.

---

## 6. `LATCH`: four elements, its own baseline, no fallback

- `latch` = **4× LDCE on `AFF`, `BFF`, `CFF`, `DFF`**.
- `latch_base` = **4× FDCE with `IS_C_INVERTED` on the same four BELs**.
- The pair is `latch ↔ latch_base`. It is the **only** pair in the class not taken against
  `base`, and the only 4-element pair.

Not negotiable at build time, and specifically:

- **No 8-element fallback.** `A5FF` and its siblings are BEL type `FF_INIT`; Vivado refuses
  `LDCE` on them outright. An 8-element latch mode is not a slow path, it is a
  non-existent one.
- **No sharing `base`.** Against `base` the transition also moves `FFSYNC` and `CLKINV`
  (FP=2); against `fdce`-with-inverted-clock only `LATCH` moves (FP=0). Two control pairs
  attributed each removed mover separately — this is measured, `docs/ff_latch_probe.md`.
- If `latch` fails to build at a holdout instance, that is a **run failure** (§7), not a
  result. The "a mode that cannot be built is itself an answer" rule belongs to the
  exploration phase and does not enter the formal matrix.
- **`LDCE` reports `IS_G_INVERTED = 0` and still sets the `CLKINV` bit.** The builder must
  not derive any clock-polarity expectation for latch specimens, and `/resolved/clock_mode`
  must never be applied to one.

---

## 7. Stamp state machine and run-level completion

### 7.1 Node types

Two kinds of node, stamped separately:

- **implementation node** (120): its own P&R, produces `base.dcp`, `spec.bit`,
  `readback.tsv`;
- **derived specimen node** (64): produces `derived.dcp`, `spec.bit`, `readback.tsv`, and
  records the sha256 of the `base.dcp` it opened (§2.1).

### 7.2 States

`build` / `reuse` / `failed` / `refuse`, extended from `gate_build_ff.cache_state()`:

| state | meaning | when |
|---|---|---|
| `build` | nothing there | directory absent or empty |
| `reuse` | stamp matches on every field, `completed: true`, every artifact hash matches | only path that skips work |
| `failed` | this exact recipe ran at this instance and variant and did not complete | `completed: false` with a matching recipe |
| `refuse` | anything else | no stamp, mismatched instance/variant/recipe/artifact hash, missing artifact |

**A stamp is written on every attempt, successful or not.** A failure that left no stamp is
indistinguishable from a directory nobody ever built in.

**Retrying a `failed` node — previously undefined, now specified.** A transient failure (a
killed tool, a full disk, a licence hiccup) must not wedge a 120-run matrix permanently;
equally, a deterministic failure must not be masked by silently rebuilding until it passes.
So:

- a `failed` node is **reported and not rebuilt by default**. The run stays incomplete
  (§7.6), which is the honest state;
- retrying is an **explicit act** — `--retry <specimen>` or `--retry-failed` — and it may
  not write into the existing directory. The old node directory is first moved, with a
  single atomic `os.replace`, into the attempt evidence path of §8, which is
  non-overwritable; the node is then rebuilt **from an empty directory**;
- each retry carries its own `attempt_id`, so evidence **accumulates**: attempt 1's log is
  still there after attempt 2. Nothing is ever deleted to make room;
- if the archival move fails, the retry aborts. Building over evidence that could not be
  preserved is how a run loses the record of why it first failed.

### 7.3 Stamp fields

```
schema, tool_version
node_type        implementation | derived
instance         SLICE_XnY25
variant          base | zini_AFF | …
attempt_id       <run_uuid>-<utc timestamp>-<seq>   ← §8, unique per attempt, never reused
sites            {target, anchor, keeper}           ← §3, so a re-mapped site refuses reuse
recipe           see below → sha256 or literal each
derived_from     {specimen_id, base_dcp_sha256}     ← derived nodes only
artifacts        {spec.bit, readback.tsv, base.dcp | derived.dcp} → sha256 each
completed        true | false
```

**Recipe domain** — everything that can change what a build *means*. A difference in any
of these refuses reuse:

| field | form | why |
|---|---|---|
| `specimen_ff.v`, the build Tcl, the builder source | sha256 | the code that decides the design |
| `commitment` | sha256 `5440ef27…` | authority A; a build for another plan is not reusable here |
| `preregistration_plan` | sha256 `ac9dbab8…97a64` at `2b40693` | authority B (§1); pins what "120" means against later prose edits |
| `part` | literal, e.g. `xc7z010clg400-1` | the same RTL on another part is a different bitstream |
| `vivado_version` | literal, e.g. `2025.2` | tool version changes placement and encoding |
| `tclargs` | full argument vector, verbatim | the arguments *are* half the recipe; hashing the script without them hashes half of it |
| `build_seed` | the specimen's committed `build_seed` | it is a committed per-specimen field; a build under a different seed is a different build |

Three additions beyond the probe's stamp, all load-bearing: **`sites`**, so changing the
§3 mapping invalidates cached artifacts rather than silently mixing geometries;
**`commitment` + `preregistration_plan`**, so neither authority can drift under a cached
build; and **`part`/`vivado_version`/`tclargs`/`build_seed`**, without which two materially
different builds hash identically.

### 7.4 Atomicity, and one run at a time

The stamp is the one file whose corruption would turn `refuse` into a false `reuse`, so:

- written to a **uniquely named** temporary in the same directory —
  `.stamp.<attempt_id>.tmp`, not a fixed `stamp.json.tmp`. A fixed name is itself a
  collision: two attempts sharing it can interleave writes into one file and produce a
  well-formed stamp describing neither build;
- `flush` + `os.fsync` on the file, `os.replace` onto `stamp.json`, then **`os.fsync` on
  the containing directory**, so the rename itself is durable and a crash cannot leave the
  directory entry pointing at nothing;
- the temporary is removed on every exit path, including failure.

**Whole-run exclusive lock.** The builder takes an `O_EXCL` lock file at the root of the
build tree for the duration of the run, recording the run's `attempt_id`, pid and start
time. A second builder finding the lock **exits immediately** rather than waiting. Two
concurrent builders over one tree would overwrite each other's stamps and artifacts, and
the damage would look exactly like a successful run — the failure mode this whole section
exists to make impossible. A stale lock is removed deliberately by a human, never
automatically on a timeout: "the other process is probably dead" is a guess, and guessing
here silently corrupts a 120-run matrix.

### 7.5 One verification entry point

Every path that *reads* an artifact — build, resume, export, report, `--report-only`, the
smoke test, and anything added later — goes through the same `verified_state()`. The
`--report-only` bypass has already caused exactly this defect once (it would have stamped
the current recipe onto older bitstreams). Enforced by a unit test that asserts no artifact
is opened except through the helper.

### 7.6 Run-level completion

A run is complete **only if both** hold:

- **120 / 120 implementation nodes** `completed: true`;
- **184 / 184 specimens** have a verified `spec.bit`.

Both are checked; neither implies the other, because the 64 derived specimens can fail
independently of the 120 P&R runs that back them. `--instance` runs can satisfy at most
15/120 and 23/184 and are therefore arithmetically incapable of completing a run — the
smoke test cannot be mistaken for a certification build.

**There is no `MAY_FAIL` set in the formal matrix.** Any failure of any of the 184 leaves
the run incomplete. `gate_measure_ff.py` is never invoked on an incomplete run.

---

## 8. Failure evidence

`build/` is gitignored, so "see `run.out`" is not a citable record. On any failure the
builder copies into a versioned path keyed by **attempt**, not by day:

```
evidence/ff_builder_<YYYY_MM_DD>/<attempt_id>/<instance>/<variant>/
    stamp.json  vivado.log  run.out  readback.tsv (if it exists)
```

`attempt_id` is `<run_uuid>-<utc timestamp>-<seq>`, generated once per run and unique per
attempt within it. A date alone is not enough: **a second run on the same day would
overwrite the first run's evidence**, and the evidence most likely to be destroyed that way
is the failure someone is actively iterating on — the one with the most diagnostic value.
So the builder **creates the attempt directory with `exist_ok=False` and fails if it is
already there**; it never writes into an existing evidence directory, and never deletes
one.

Preserving diagnostics is the point; **it must not turn a partial success into a
measurable run.** The evidence directory is written by the builder and read by humans. It
is not an input to `gate_measure_ff.py`, and no code path lets its presence satisfy §7.6.

---

## 9. What the hashes do and do not prove

`base.dcp`, `derived.dcp`, `readback.tsv` and `spec.bit` hashes are all recorded, and each
derived specimen pins the `base.dcp` it opened alongside the `derived.dcp` it wrote. This
is an **integrity anchor**: it detects substitution and drift, and after §2.1 the state the
attestation describes is a state that actually exists on disk. It does **not** prove the
bitstream was produced from that checkpoint — nothing in this flow does, adding
`derived.dcp` does not change that, and the attestation must not be worded as though it
did.

Likewise `ROUTE_STATUS` records **completion only**. Two builds can both report `ROUTED`
over entirely different paths. Where this design says "routing unchanged" (§2.1) it means
"the checkpoint was not re-routed", evidenced by the flow not calling `route_design` and by
the placement and per-net `ROUTE`/PIP readback being identical — not by `ROUTE_STATUS`,
which is never treated as evidence of path identity anywhere in this document.

---

## 10. Acceptance before any holdout bitstream exists

In order. **Nothing at a holdout instance is built until this document is approved.**

1. **History-independent unit tests, from `git archive HEAD` into an empty directory**, per
   `2ca9320`. Covers: authority A's assertions, including deliberately corrupted copies of
   the commitment; the §3 mapping regenerated from the rule and checked against the
   24-distinct-sites property; §1.1 source scan; §1.2 set equality in both directions;
   **`--instance` rejecting every holdout site** while accepting `SLICE_X2Y25`; and — the
   only authority-B assertion possible without history — that the builder **refuses to
   start when `.git` is absent** instead of falling back to the working-tree plan.
2. **Authority-B tests, from a fresh `git clone`** (§1.3). The clone's history contains
   `2b40693`, so these run for real: the frozen plan text resolves and hashes to
   `ac9dbab8…97a64`; a tampered working-tree copy does **not** change that result; and a
   stamp carrying a different plan hash refuses reuse. Splitting the suite this way is
   deliberate — a test that quietly skips when history is missing would report green for
   the check that matters most here.
3. **Cache-tampering negatives**, one test each, each asserting the *reason*: no stamp;
   stamp for another variant; stamp for another instance; **stamp whose `sites` differ**;
   builder/Tcl/Verilog hash mismatch; **commitment hash mismatch**; **plan hash mismatch**;
   **`part` mismatch**; **`vivado_version` mismatch**; **`tclargs` mismatch**;
   **`build_seed` mismatch**; artifact hash mismatch; `completed: false`; artifact deleted
   while the stamp claims success; and for derived nodes, a `derived.dcp` whose hash does
   not match its stamp. Every one must land in `refuse` or `failed` — **never `reuse`**.
4. **Concurrency and evidence negatives**: a second builder finding the run lock exits
   without touching anything; a stale lock is *not* auto-cleared; an existing evidence
   attempt directory causes a hard failure rather than an overwrite; a killed builder
   leaves either a valid stamp or none, never a partial one.
5. **Mine-instance smoke: all 15 implementations + 8 derived on `SLICE_X2Y25` only.**
   `SLICE_X2Y25`'s evidence is already spent and can never score, so this costs nothing
   scientifically. It must demonstrate: every mode builds; every requested BEL/LOC resolved
   as requested; **§5.3 pairwise structural identity holds over the 21 committed pairs of
   this instance** — 168 ÷ 8 = 21: twenty taken against `base`, plus `latch`↔`latch_base`,
   enumerated from the commitment and checked to be exactly that set;
   derived specimens produce a `derived.dcp` whose readback differs from `base.dcp`'s in
   the `INIT` attribute and in nothing else; and the run correctly reports itself
   **incomplete** (15/120, 23/184).
6. **Stop condition, per the reviewer's ruling on `zrst_*`:** if the mine smoke produces
   any FP — from `zrst_*` or anything else — the run stops there. No holdout instance is
   built until the cause is understood and written down. "It is only the mine site" is not
   a reason to continue past a false positive; it is the reason the mine site exists.
7. Only then, the 105 remaining implementations across the 7 holdout instances.

Step 5 is where the formal topology is first exercised end to end, `latch` included; if the
four-element pair misbehaves, it is far cheaper to discover it on the mine site than 100
P&R runs later.

---

## 11. The four questions, and how they were ruled

Ruled by the reviewer on 2026-08-05. Recorded here with the reasoning, because a ruling
whose "why" is lost gets re-litigated by whoever reads this next.

1. **Checkpoint reuse for `zini_*` — ACCEPTED, with the derived checkpoint preserved.**
   One P&R serving nine bitstreams stands; 120 is untouched. What was missing was not the
   P&R but the *artifact*: only `base.dcp` was hashed, and it holds `INIT=1` while the
   derived specimen's readback and bitstream are `INIT=0`, so the attestation described a
   design state that existed nowhere on disk. Fixed in §2.1 — each derived specimen writes
   and hashes `derived.dcp` and pins the `base.dcp` it came from.
2. **Anchor at column +2 — KEPT.** The constant relative offset is the invariant, not
   physical distance. It is the geometry the probe actually measured, and "nearest
   non-target tile" would make the anchor's position a function of the target's
   neighbourhood — a rule that varies per instance is a rule that has to be re-argued per
   instance.
3. **Keeper sharing frames with the target — the original check was NOT sufficient, and
   was replaced.** All-23 identity was both too strong (the 4- and 8-element families
   legitimately differ in anchor connectivity, so it would fire on a correct build) and too
   narrow (`LOC`/`BEL` only, blind to inversion attributes, pin mapping and routing).
   §5.3 is now pairwise over the 168 committed pairs — and, after revision 3, **tiered**,
   because the replacement over-corrected: demanding full sink-set and `ROUTE` equality on
   nets shared with the target would have rejected `ce_tied`, `sr_tied`, `zrst_*` and the
   latch family, all of which change the target end of a shared net on purpose. Tier 1 is
   local cell facts, tier 2 is dedicated anchor/keeper nets, tier 3 is shared nets kept as
   diagnostics only. It explicitly does not claim the two ends contribute identical bits.
4. **`zrst_*` — KEPT as a falsifiable risk, with a stop condition.** FDSE is a different
   primitive from FDRE, changing the reset pin (R → S) and not only a property, which makes
   it the least "single-bit-shaped" of the 15 topologies. It is not redesigned to be safer;
   if it moves more than that FF's `ZRST`, that surfaces as FP under the fixed 1.4 rule.
   The ruling is procedural: **if the mine smoke produces any FP, stop before holdout**
   (§10 step 5).

### 11.1 Corrections these reviews forced, kept visible

Six claims across revisions 1 and 2 were wrong or overreaching. They are listed rather than
quietly edited away, because the patterns in them are the useful part.

**Revision 1 → 2. Four instances of one pattern: a geometric or structural fact doing duty
as a functional guarantee.**

- "row 20 **proven** from the freeze" → the freeze proves the geometric precondition; that
  the keeper keeps the clock branch enabled is a **hypothesis** resting on one mine-site
  measurement (§3.4).
- anchor bits "**cannot** perturb the target frames' ECC" → only the anchor's *cells* are
  out of column; **routing to them may still cross the target's column** (§3.5).
- "**120** recomputed from the commitment" → the JSON's totals are 184/176/154 only; 120
  comes from the pre-freeze execution topology, which is now pinned by its own hash as a
  second authority (§1).
- "anchor and keeper identical across all **23**" → wrong granularity; the comparison is
  **pairwise over the 168 committed pairs** (§4, §5.3).

**Revision 2 → 3. A different pattern, and the more instructive one: a tightened check that
tightened past what it was checking.**

- **The corrected §5.3 would have rejected correct specimens.** Requiring full sink-set and
  `ROUTE` equality on "every net touching an anchor or keeper pin" ignored that those nets
  also serve the target, and that four variants exist *precisely* to change the target end
  of them. This was self-inflicted while fixing the all-23 error — over-correction is its
  own failure mode, and a gate that fires on correct builds gets weakened until it catches
  nothing. Fixed by tiering (§5.3).
- **Authority B and cold-archive testing contradicted each other.** Revision 2 required
  reading the frozen plan through `git show 2b40693:…` *and* required the suite to pass
  from `git archive`, which has no history. Neither statement was wrong alone; together
  they were unsatisfiable, and nobody would have noticed until the first certification run.
  Fixed by §1.3: clone for the formal run, archive for history-independent tests, and the
  refusal-without-history is itself asserted.
- Also this round, two smaller precisifications rather than errors: a `failed` node's retry
  path is now defined (§7.2, archive-then-rebuild-empty, never overwrite, never wedge), and
  "the site is **legal**" is narrowed to "exists and is not marked prohibited in the
  freeze" — whether it can host the requested cells is Vivado's answer, read back and
  hard-checked (§3.3, §5.2).

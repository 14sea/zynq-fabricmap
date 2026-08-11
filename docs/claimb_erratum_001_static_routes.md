# Architecture erratum 001 — static routes inside the written frames

**Ruled 2026-08-11. This is an ADDITIVE record. It does not rewrite
`claimb_carrier_design.md` §4 or the preregistration; those stand as written and this
erratum states what supersedes what.**

Scope: **carrier feasibility only.** It does not change the reachability target, the seed
(`0xB1B0`), the ceiling, the cap, the masks, the fitness, the train/holdout split or the
A/B rules. Nothing measured or preregistered about Claim B round 1 moves.

## What was measured

The frame-staged carrier fits the left-of-flush region and routes: 680 logic + 112 LUTRAM
= 792 LUTs against 800 sites, 531 FFs against 1,600, 52 control sets, WNS +7.048 ns at
50 MHz. `place_design` and `route_design` both complete.

The isolation check of §4.2 then fails, and restricting it to the rows the design actually
writes (`Y0‥Y49`) does not rescue it:

| routed resources in | whole column | `Y0‥Y49` only |
| --- | --- | --- |
| nets over the two flush column segments | 153 | 113 |
| nets over the two target column segments | 403 | 241, of which **235** are not evolvable data nets |

The residual set is dominated by `icap_dout[0..31]`, `icap_din[*]`, `axil/*` and
`stream/*` — control class, not data class.

This is geometry, not a placement mistake. The carrier logic is at `SLICE_X0..X1`, the
`ICAPE2` site is on the right of the die, and the target column (`X2/X3`) and the first
flush column (`X4/X5`) stand full-height between them. Every ICAP net must cross both. The
right-hand alternative was measured earlier at 124 crossers including the AXI bus, i.e. the
same failure with a different set of nets. No legal floorplan on this device avoids it.

**One thing in that check is a false positive and must not be chased**: `pb_logic
PRIMITIVE_COUNT 1460 but 1592 expected`. Asked per cell, **0 primitives are outside
`pb_logic`**. `PRIMITIVE_COUNT` does not count the same set; the per-cell `PBLOCK` property
is the oracle, exactly as `isolation_checks.tcl` already argues for the `CELL_COUNT` case.

## The ruling

**Accept that the carrier's own static routing passes through the target and flush frames.
Do NOT accept it by adding the 235 control nets to an allowlist.** The authority moves from
*which nets are named* to *which configuration bits change*:

> **Every non-evolutionary bit of every written frame must equal the final carrier base,
> bit for bit.**

A net's name is not a safety argument. Its configuration bits being unchanged is.

### Why "zero static routes" was never the necessary condition

7-series partial reconfiguration explicitly contemplates static routes crossing a
reconfigurable region: their programming information is included in the partial bitstream,
and the requirement is that the partial write reproduces it. See UG909, *Vivado Design Suite
User Guide: Dynamic Function eXchange* —
<https://docs.amd.com/api/khub/documents/aFtTMbStto75TDahM0xQEg/content>.

So "no foreign route in a written frame" was a **stronger condition we adopted for a
smaller blast radius**, not a property silicon requires. This device's geometry proves it
unachievable here. Dropping it costs the containment argument — a defective write can now
damage the carrier itself, not only the evolvable LUTs — which is why the compensating
gate below is *bit* equality and why the board sequence now opens with a no-op.

## The gate, as it is now fixed

**Unrelaxed, and still refusals:**

1. **Cell isolation.** The target column segments hold **exactly** the six evolvable LUTs;
   the flush column segments hold **zero** cells. Unchanged.
2. **Positive control** before any verdict: the checker must see the six LUTs and their
   data nets, or it fails rather than passing.

**The new authority:**

3. **The 15 frames of the base come from the FINAL ROUTED CARRIER BITSTREAM** — not an
   earlier probe, not a DCP, not a previous build. Machine-checked by identity, not by
   convention.
4. **Flush frames**: all 101 words of each must equal the pinned base **verbatim**, word 50
   included.
5. **Target frames**: the only differences permitted are
   - actual changes among the 292 certified `local_map` bits, and
   - the explicit frame-ECC bit mask, whose value must equal an **independent
     recomputation** over the resulting content — an ECC that merely differs is refused, and
     so is a stale one;
   - **every other bit must equal the base.**
6. This is **byte/bit equality and does not consult a segbits database**, so a routing bit
   nobody has ever named is protected exactly as well as a bit we can name. That is the
   whole reason the authority moved here.
7. **Readback must equal the candidate word for word**, and `arm` remains forbidden until
   the host SHA-256 comparison passes.
8. **The INIT ECO differential on the same routed DCP still has to pass**, proving the
   evolutionary edit lands only on whitelisted bits and their ECC words.

**Demoted, and only demoted:**

9. The route check of §4.2 becomes an **evidence recorder**, not a verdict. It enumerates
   and hashes the routed nodes, PIPs and net inventory of the touched regions so the record
   exists and any later change to it is visible. **It does not exempt nets by name**, and it
   does not pass or fail on them. The safety judgement is (4)–(6): the configuration bits
   did not change.

## How the authority is actually held — added 2026-08-11 after review

A rule nobody can re-check is a comment, and "the final routed carrier base" only means
something if a reviewer elsewhere can obtain those exact bytes:

* the run **bundle** `carrier_run.json` pins every artifact by sha256 and carries the ECO's
  `by_lut` key **derived from the tilegrid**, not typed in;
* `gate_carrier_base.py` and `gate_init_eco.py` take a run directory and **nothing else** —
  no map, no LUT key, no bitstream, no build directory. An operator who picks the inputs
  picks the verdict. Both record every input digest in their verdicts;
* the three exact artifacts — `carrier.bit`, `carrier_eco.bit`, `post_route.dcp`, under
  5 MiB together — are **published via Git LFS in the run root**. Keeping the sha256 and
  discarding the bytes it names leaves an authority nobody outside one workstation can
  exercise, and a rebuild does not reproduce the file: `write_bitstream` stamps a
  timestamp, measured as `dd8bf0b8…` then `e677d097…` for identical RTL;
* `gate_publish_carrier_run.py` decides what enters history **from the git index**, because
  the LFS filter can be defeated at `git add` and binary in ordinary history is the one
  mistake a later commit does not undo;
* all three gates have tracked negative tests (`tests/test_carrier_run_gates.py`), and a
  fresh clone plus `git lfs pull` re-runs both verdicts to the same answer.

## Board calibration order — tightened by the same ruling

The one assumption that cannot be settled off the board is whether the self-hosted ICAP
path is stable while rewriting the *same* static-route bits it is itself running on. So the
first device write tests exactly that and nothing else:

1. **A complete NO-OP transaction first**: all 15 frames equal the base.
2. Require **guard alive, zero faults, readback hash equal to the base, and the scorer NOT
   armed**.
3. Only then the **pre-selected known-answer mutation**.
4. Readback, score, restore base, post-baseline.

**If the no-op wedges the device, faults the guard, or produces any readback difference at
all: stop.** Not a retry, and not a rule loosened to explain it. A no-op that does not read
back identically has falsified the assumption the whole carrier rests on.

## What was explicitly refused

* re-choosing the target sites — it would invalidate the frozen `local_map` addresses;
* accepting arbitrary control-bit drift;
* returning to the right-hand floorplan, which fails the same way with different nets;
* widening the checker's allowlist to cover what the router happened to do.

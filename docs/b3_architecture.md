# B3 — the closed loop: architecture and host simulation (v0.1.1, host-only, 2026-09-10)

> **v0.1 → v0.1.1 (the owner's review of 2026-09-10).** The specimen cartographer now
> validates every specimen against what is decoded and commits atomically (§3; the review's
> counterexamples are tests); the simulation re-run on the same seeds with the corrected
> cartographer is bit-identical (`evidence/b3/sim_v0.1.1/`, 400 rows), so §5's numbers stand
> as **ideal-model** evidence — the anomaly guarantees are established by the tests, not by
> zero anomalies in an additive model. Corrections of language: the accounting is an
> **evaluation-count model** (333 probes charged to F; baselines, setup, qualification,
> audits and compute time not counted); bounded fitnesses do not "grow without bound"; the
> positive O − F means at every grid budget are **reproduced exploratory results**, not a
> preregistered family of confirmed tests.

> **Standing: design and host simulation only. No preregistration, no image, no ruling, no
> board.** Stage B3 of `docs/autonomous_cartography_roadmap.md` §2 ("the closed loop,
> last"), opened with B2 on the owner's instruction of 2026-09-09. B3 depends on B2's
> package being reviewed and on B2's board result; what is fixed here is the interface
> the roadmap asks for (three arms, the specimen ledger, two costs) and what a host
> simulation on B2's own engine says about it — so that the owner can decide the order
> of B2 and B3 board time with the arithmetic in view.

## 1. The question

*Can evolution specimens — the evaluations a search makes anyway — update the map online,
and does the update improve later search? And once the cost of building the map is
charged, which pays: a map built up front (B1, 333 probes), a map built from the search's
own specimens (no dedicated probe), or no map at all?*

## 2. The three arms (roadmap §2 B3) — B2's engine, landscape and operator, nothing tuned

| arm | map | mapping cost charged | notes |
|---|---|---|---|
| **R** random-safe | none, ever | 0 | B2's arm A |
| **F** frozen self-map | B1's board-authored map (`c6a4b23e…`) | **333** evaluations (B1's budget: 9 code probes + 292 confirmations + 32 pairs) | B2's arm B |
| **O** online-updating self-map | starts **empty**; grows from specimens | 0 dedicated probes | B2's map-guided operator over the *current* map version |

The engine (μ + λ, `host/b2_search.py`), the landscape rule and fitness (`host/b2_landscape.py`),
the operator and its ½ mixture (`docs/b2_architecture.md` §5) are B2's, unchanged — B3
changes only where the map comes from. This is deliberate: a B3 that tuned the operator
would be testing a different operator, not the loop.

## 3. Every evaluation is a specimen — the online cartographer

On this carrier the readout is six truth tables and the fabric is additive (B1: 292/292,
32/32 pairs without deviation). A child differs from its parent by the moved bits M
(1..4 addresses), and **the child's readout XOR the parent's is exactly the set D of
positions those addresses toggled** — a behaviour delta the board already has, at no
cost. The specimen cartographer (`host/b3_online.py` `SpecimenCarto`) is B1's group
testing turned inside out:

- a specimen with |M| = 1 decodes its address directly (confidence 2, like B1's phase B);
- a specimen with |M| > 1 **narrows**: each address in M keeps the intersection of its
  candidate set with D (confidence 1); a singleton is a decode; a decoded position is
  removed from every other candidate set, and the closure runs over all candidates;
- a specimen is **refused** (anomaly counted, **nothing else changes**) when it is malformed
  (duplicate / out-of-range addresses or positions, |D| ≠ |M|), when a decoded moved
  address's known position is not in D, when a position in D belongs to a decoded address
  that was *not* moved, when a pending address's intersection is empty, or when the closure
  conflicts; narrowing and closure are computed on a copy and committed only if the whole
  specimen is consistent (`tests/test_b3_online.py`: the review's three counterexamples,
  a closure conflict, malformed cases — each with a state snapshot equal before and after);
- every decode bumps the **map version**; the operator consults the current version.

The **specimen ledger** (`schemas/specimen_ledger.schema.json`, `specimen_ledger` 1.0.0)
is the evidence chain: one entry per evaluation — `(seq, map_version, parent_born,
intervention, move_kind, behaviour_delta, fitness, confidence, decoded, map_version_after)`
— bound to the session and the landscape seed. Replaying the ledger from the first entry
reproduces every map version (`tests/test_b3_online.py`); the host audits the decodes
against the certificate afterwards, never during (the B1 boundary).

## 4. What the board would do, and the autonomy boundary

Unchanged from B2 (roadmap §1): the board draws parents, moves, computes the fitness,
selects, **and updates the map** — the map update is an executing decision and stays on
the board. The host recomputes fitness from served readouts, replays the search *and the
ledger*, and audits the decoded relations against the certificate after the session; none
of it reaches the board. The record's `search` block gains the ledger fields; the IDENT
names the online cartographer and its version.

## 5. Host simulation — `host/b3_sim.py`, 200 landscape seeds, F1 and F2

`evidence/b3/sim/sim_report.json` (HEAD `c6e3705`, clean tree, master seed 3 829 368 064,
label `b3-sim`; per-seed values in `raw_F1.json`, `raw_F2.json`). Two accountings:

- **search**: best-so-far at B evaluations of each arm's own search;
- **end-to-end**: best-so-far at total budget T, the frozen arm charged its 333 mapping
  probes first (its search value at T is its own trace at T − 333; the base fitness while
  T ≤ 333); R and O charged nothing. **This is an evaluation-count model**, not wall-time
  accounting: B1's two baseline records, setup, qualification, audits and compute time are
  not counted.

### 5.1 F1 (B2's selected fitness; ceiling 40) — medians over 200 seeds

| budget | 100 | 200 | 300 | 400 | 600 | 800 | 1000 | 1500 | 2000 | 3000 |
|---|---|---|---|---|---|---|---|---|---|---|
| R | 6 | 8 | 10 | 11 | 12 | 13 | 13.5 | 14 | 15 | 15 |
| F (search) | 6 | 9 | 11 | 13 | 16 | 18.5 | 21 | 24 | 27 | 30 |
| O | 5 | 6.5 | 8 | 10 | 14 | 16 | 18.5 | 23 | 26 | 29 |
| F (end-to-end) | 2 | 2 | 2 | 5 | 10 | 14 | 17 | 22 | 25 | 29 |
| O map decoded (of 292) | 40 | 106.5 | 167 | 212.5 | 262 | 280 | 288 | 292 | 292 | 292 |

Paired (mean Δ; positives / negatives / ties; one-sided sign test p):

| pair | 300 | 600 | 1000 | 2000 | 3000 |
|---|---|---|---|---|---|
| O − R (both accountings) | −1.28 (41/130/29, ns) | **+1.33** (123/54/23, 1e-7) | **+4.96** (185/4/11, 7e-50) | **+11.04** (200/0/0) | **+14.25** (200/0/0) |
| O − F, search | −2.34 (27/159/14, ns) | −2.42 (26/157/17, ns) | −1.98 (34/140/26, ns) | −0.76 (60/107/33, ns) | −0.32 (79/97/24, ns) |
| O − F, end-to-end | **+6.22** (200/0/0) | **+3.52** (175/11/14, 2e-39) | **+1.63** (132/46/22, 4e-11) | **+0.77** (106/69/25, 3e-3) | **+0.67** (106/68/26, 2e-3) |
| F − R, end-to-end | −7.51 (0/200/0) | −2.19 (33/140/27, ns) | **+3.33** (164/22/14, 2e-28) | **+10.27** (200/0/0) | **+13.58** (200/0/0) |

Online map: full 292/292 within budget in **200 / 200** runs, median **1 416** evaluations to
the full map; **0 wrong decodes, 0 anomalies** over 200 × 3 000 specimens; median 177 map
versions. Champion holdout medians R / F / O = 1 / 1 / 1 (neutral, as in B2).

### 5.2 F2 (graded word; ceiling 160) — the same shape, larger numbers

Search medians at 600 / 1000 / 2000 / 3000: R 81 / 100 / 121 / 128; F 87 / 111 / 141 / 153;
O 77 / 104 / 139 / 152. O − R crosses zero at ≈ 800 (+0.27, ns) and is +3.94 (p 9e-6) at
1 000, +17.82 at 2 000. End-to-end O − F: +21.8 at 600, +11.8 at 1 000, +5.0 at 2 000,
+1.5 (p 3e-3) at 3 000; F − R end-to-end turns positive at 1 500 (+5.17). Same online map
growth (the cartographer does not depend on the fitness), 0 wrong, 0 anomalies.

### 5.3 Reading — the three outcomes the roadmap wanted distinguishable (exploratory)

1. **"Correct but useless" — no.** The map is correct (B1) and useful (B2's gate; F − R
   increases across the whole grid, within the bounded fitness).
2. **"Useful but too expensive to build" — at small total budgets, yes.** Charged its
   333 probes, the frozen map does not repay itself before ≈ 800 evaluations on F1
   (≈ 1 500 on F2); below that, no map at all is better than a map paid for up front.
3. **"Online updating pays" — yes, and twice.** (a) *Against random-safe:* the online
   arm pays the poor-map cost first (B2 §8: a sparse map diverts half the moves), is
   behind R until ≈ 400–500 evaluations, then wins from 600 on with a growing margin
   (F1: +1.3 at 600, +11 at 2 000). (b) *Against the frozen map, end-to-end:* the online
   arm is ahead at **every** budget on the grid (F1: +6.2 at 300, +0.7 at 3 000, all p < 0.01
   in this exploratory sweep — one preregistered budget would be the confirmed test),
   converging to the frozen arm as its own map completes (search accounting: −0.3 at
   3 000, ns). The online map costs no probe and is complete by a median 1 416
   evaluations with zero wrong decodes in the ideal model — on this fabric the search *is*
   a cartographer.

What this does not say: anything about a non-additive fabric (anomalies were 0 because
the model is additive; the board's anomaly counter is where B4's routing bits will show),
about physical noise, or about a different operator. And the B2 caveat stands: the
crossing points depend on the ½ mixture's poor-map cost, which was fixed before any
simulation and not tuned.

## 6. What a B3 board stage would need (not asked now)

- B2 reviewed and, if ruled, run: B3's F arm *is* B2's arm B, and B2's board result is
  the calibration for whether the simulation's arithmetic holds on silicon.
- A B3 preregistration with its own gate (the B2 pattern): the primary a paired statistic
  on O − R at a budget chosen by the cost rule, the end-to-end O − F as the second
  primary, the ledger's replay and the post-hoc decode audit as EXACT rows, the online
  map's `self_map` 2.0.0 rendering scored by the B1 verifier at the end of each run.
- The image: B2's with the specimen cartographer (a C twin of `SpecimenCarto`) and the
  ledger fields in the record block; the map version in every record's commitment.
- Board time: the online arm needs ≥ 600 evaluations per run to show its benefit against
  R on F1 (≥ 1 000 for a large one); with the three arms that is 3 × N × B — at N = 9,
  B = 1 000, ≈ 27 000 evaluations, several sessions under the sampled-audit rate. The
  owner decides whether B3 is worth that after B2.

## 7. Files (host-only, additive)

| file | role | tests |
|---|---|---|
| `host/b3_online.py` | the specimen cartographer, the online arm, the ledger entries | `tests/test_b3_online.py` (9): direct and narrowed decodes, anomalies, no wrong decode over a full run, ledger replay reproduces every map version, determinism, schema validation with a negative |
| `host/b3_sim.py` | the three-arm simulation, both accountings, the report | — |
| `schemas/specimen_ledger.schema.json` | `specimen_ledger` 1.0.0 | in the test above |
| `evidence/b3/sim/` | `sim_report.json`, `raw_F1.json`, `raw_F2.json` | — |

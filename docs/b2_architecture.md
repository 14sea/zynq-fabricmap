# B2 — map utility: a carrier that can discriminate — architecture (v0.3, host-only, 2026-09-10)

> **Revision v0.2 → v0.3 (2026-09-10, after the owner's review `docs/b2_b3_host_review_2026_09_10.md`, HOLD).**
> Nothing in the engine, the mixture, the fitness family or the session seeds changes. What
> changes: **§7a** predeclares two further controls (T train-membership-only, W within-train
> column scramble) and the comparison G9 that attributes the benefit to correct column
> grouping — run on the SAME 200 seeds and rows as gate run 3, after this text is committed;
> **G5** is a bound on the experiment's *total* evaluations (13 000) and no longer a
> "fits one session" claim — the session count is decided by the B2Q-measured
> all-self-reporting rate (the owner chose all-self-reporting for the first B2); the
> **minimum-N search** is a full ascending scan (the geometric sweep skipped N = 89 at
> F3 / 300); run 3's rows are re-evaluated under these rules into
> `evidence/b2/gate/recomputed_2026_09_10/` (run 3's report untouched). Corrections of
> record: the v0.1 → v0.2 table has **four** changed rows (the budget rule, G2, G5, G7), not
> "three rules"; gate run 1 executed the code of `9f347e9` under the architecture text of
> `342450b`; the map digest `c6a4b23e…` is the sha256 of the **canonical JSON object**
> (sorted keys, no spaces), the file bytes hash to `b6607a9a…` — both are named wherever a
> digest is pinned; "the whole phenotype" means the **digital functional observation** (the
> six truth tables under the sweep), not timing or power; F3's trajectories can enter
> holdout rows, so the "holdout never touches train" statement holds for F1 / F2 only
> (§8); seed-set disjointness is **enforced by explicit exclusion**, not assumed from
> distinct labels.

> **Revision v0.1 → v0.2 (2026-09-10, after gate run 1).** Run 1 (`evidence/b2/gate/v0.1_2026-09-10/`,
> executing the code of `9f347e9` under the architecture text of `342450b`) failed every
> fitness — not on discrimination (all three beat random-safe; the shuffled and within-LUT-
> shuffled maps do not profit, they *lose*) but on **four** rows of §7 that the run showed to
> be mis-specified. §7 v0.2 changes exactly these, each with its reason, and the gate is
> re-run under the commit holding this text (`evidence/b2/gate/gate_report.json`). Nothing
> in §1–§6 changed. The v0.1 report is kept unchanged so the owner can see what the first
> rules produced. (The owner's review accepted these as documented *development* revisions.)
>
> | rule | v0.1 | v0.2 | why |
> |---|---|---|---|
> | budget rule | `B*` = smallest grid budget at which the oracle arm's median ≥ 60 % of the ceiling | `B*` = the grid budget with the **smallest session cost** `N(B) × 2 × B` among budgets where G1 holds and `N(B)` exists | the 60 % rule chose budgets 2.5–4× costlier than the cheapest discriminating one (F1: 1 500 → 24 000 evaluations vs 600 → 10 800); non-saturation is G1's job, not the budget rule's |
> | G2 | P(Δ_B < 0) > 0 at `B*` | the definitional-lock test: var(Δ_B) > 0, **and** Δ_B takes both signs at some grid budget, **and** the same procedure does not reject on the shuffled arm | F1 at 1 500 gave 200/200 positives — a strong effect, not a lock; round 1′'s lock was budget- and seed-independent, and that is what the test must exclude |
> | G5 cost cap | 6 000 evaluations (one session, all-self-reporting audit, B1's rate) | **13 000** evaluations = one two-hour session at the instrument's evidenced **sampled-audit** rate (S #3: 12 570 records / 6 763.9 s), the all-self-reporting fit (6 000) reported alongside; the audit policy is put to the owner (`docs/b2_package.md`) | v0.1 silently assumed B1's all-self-reporting policy; B2's records carry the board's fitness and the readout, and the instrument's sampled-audit policy with falsification-on-mismatch is equally evidenced — the choice is the owner's, and the arithmetic for both is reported |
> | G7 | mean Δ monotone non-increasing over q ∈ {0, ¼, ½, ¾, 1}, with Δ(1) = 0 (random-safe) | monotone non-increasing over q ∈ {0, ¼, ½, ¾}; Q(¾) ≤ ½ · arm B; the q = 1 endpoint reported, not required | the run shows Δ(¾) < 0 on every fitness: under the ½ mixture a poor map **diverts half the budget to a small subset**, so a poor map is worse than no map. The continuity assumption was wrong, and wrong in a way that is itself a finding (§8) |

> **Standing: host-only design. Nothing here is frozen, ruled, built as firmware or loaded on
> any board; no board contact is authorised.** Stage B2 of
> `docs/autonomous_cartography_roadmap.md` §2, opened on the owner's instruction of
> 2026-09-09 after B1 closed (`docs/b1_mapping_session_audit_2026_09_08.md`, PASS). This
> document fixes the design and, in §7, **the discriminability-gate criteria and the fitness
> selection rule before the gate simulation is run** — the gate report cites the commit
> that holds this text. The B2 preregistration (`docs/b2_preregistration.md`) says what a
> board session will be judged by; `docs/b2_package.md` is what the owner reviews.

## 1. The question, and what round 1′ taught

*Does a frozen, board-built map (the B1 self-map) make the **same** selection engine, on a
fitness with **real interaction** between bits, beat the random-safe operator — and does that
benefit come from the map's structure being correct, rather than from the shape of the
map-guided move?*

Round 1′ (`docs/claimb_round1prime_preregistration.md` §0) was withdrawn before freeze
because the P3 carrier's scorer is additive over the 292 INIT bits: every candidate's gain
is the sum of per-bit constants, the best of any block is +4 for either arm, and the
preregistered primary tied 16/16 by arithmetic. The roadmap's corrections are adopted here
verbatim: additive fitness does not make the operators identical, and a digital, replayable
landscape is enough. What B2 must therefore give, and the gate must show *before* any board
time, is a fitness where structured moves can pay, and a set of controls that separate
"the map is right" from "the map-guided move has a convenient shape".

## 2. The carrier: the qualified B1 carrier, unchanged — the fitness lives on the PS

**Decision D1.** B2 runs on the **B1 carrier** (`builds/b1/b1.bit` `d85daef4…`, `VARIANT`
`0x42310001`, qualified by the evidence chain `evidence/b1q/b1q_17A6_2026-09-08-01`), with
no RTL change. The reason is what B1 already established: under `configuration_valid_hw`
the arm gate sweeps all 64 input vectors of the six evolvable LUT6s and latches the **raw
functional readout** — six 64-bit truth tables, table *k* bit *v* = LUT *k*'s output for
vector *v* (`docs/b1_carrier_contract.md` §2). Because the six LUTs are combinational in a
shared 6-bit input, **that readout *is* the whole phenotype** — in the sense that matters here,
the **digital functional observation** under the sweep (not timing, not power): every
function the fabric can exhibit under this carrier is a function of those 384 bits. So any fitness over the
phenotype is a pure function `F(readout)` and can be computed by the board application on
the PS from the READOUT registers, interlocked exactly as B1's cartographer was (the
readout is latched only after a signed, staged, read-back candidate — links 1–3 unchanged).

What this buys: no Vivado build, no isolation re-check, no new MMIO allowlist, no new
carrier qualification session. What it costs, stated: the PL scorer's additive
`score_flat` is no longer the fitness. It is still latched and still recorded on every
record, and the host validator checks it against the additive count derived from the same
record's readout — a free per-record known answer, kept as an instrument self-check.

The **image** is new (`firmware/b2/`, after the package review): the instrument's
`p3_derive` / `p3_rectx` / `p3_pull` / BSP / linker byte for byte (as B1's `IMPORT.json`),
B1's `b1_app.c` lineage with the cartographer replaced by the **search** (§4), the B1
signer and validator unchanged (zero tables signed; a reply with attested tables refused).
A new image owes the compatibility review, its own calibration and its own seeds (roadmap
§6); the B2 runner re-verifies the carrier's qualification chain, never the flag.

## 3. The landscape: a public rule, a seed, and nothing from the map

**Decision D2.** The target is a genome-space point drawn by a **public rule from a landscape
seed**, and the fitness is a function of the readout and that target. Notation:
`W_k[v]` = readout table *k* bit *v* (k = 0..5, v = 0..63); the **column word**
`W(v) = (W_5[v] … W_0[v])`; `M_k[v]` = 1 iff (k, v) is one of the 292 certified writable
positions (the **universe** — public, the same object both arms and the whitelist use; it
is not the map).

*Target rule.* `T_k[v]` = the next bit of an xorshift64 stream seeded by the landscape seed
(the instrument's `Rng`, `l6_operators.Rng` / `validators.nonce.step`, warm-up 4), taken in
(k, v) order, **masked to the universe**: `T_k[v] := 0` (the base value) wherever
`M_k[v] = 0`. The optimum is therefore reachable and unique (the genome that sets exactly
the writable positions where T is 1) — the "fitness over the reachable space" that
`docs/claimb_carrier_design.md` §5 asks for. The mask depends on the universe only; the
map never enters the landscape.

*Train / holdout.* The carrier's frozen vector order (`vivado/carrier/generated/
carrier_constants.json` `order`) is kept: the first 40 vectors are **train**, the last 24
**holdout**. Fitness is computed over train columns only. Holdout is evaluated **once per
arm, on the champion, on the hardware, last** — and what it means is stated honestly in §8:
for a lookup-table phenotype, holdout rows are independent parameters, so holdout is a
**neutrality / known-answer control**, not a generalisation measure.

*The fitness family, in the order fixed now (§7 selection rule).* Let
`d_v = popcount(W(v) ⊕ T(v))` over the six bits of column *v*.

| id | name | definition (train columns) | range | interaction |
|---|---|---|---|---|
| **F2** | graded word | `Σ_v g(d_v)`, `g(0) = 4`, `g(1) = 1`, `g(≥2) = 0` | 0..160 | across the six LUTs at one INIT index (a column is a block); gradient only from d ≤ 2 |
| **F1** | exact word | `Σ_v [d_v = 0]` | 0..40 | the same block, no partial credit (a royal-road landscape) |
| **F3** | trajectory | the automaton `s ← W(s)`; for each train vector as start state, the length of the longest prefix (≤ 8 steps) on which the trajectory equals the target automaton's `s ← T(s)`; summed | 0..320 | across columns along trajectories and across LUTs within a word |

None is additive over bits: in F1/F2 a bit's contribution depends on the other five bits of
its column; in F3 on the whole path. The order F2 → F1 → F3 is a design preference
recorded before any simulation (F2 has both interaction and a gradient; F1 is the pure block
landscape; F3 the most epistatic and the most likely to be a needle). The gate runs all three
and reports all three; the first in this order that passes every criterion of §7 is the B2
fitness. If none passes, B2 does not go to the board.

## 4. The search engine, shared by both arms

**Decision D3.** A deterministic **(μ + λ) evolution strategy** with truncation selection,
integer-only, seeded by the instrument's RNG so that a C image and its Python reference
can be twins byte for byte (B1's discipline):

- μ = 4 parents, λ = 8 children per generation; the initial population is μ copies of the
  base (all-zero, the opening baseline's genome); every child is one board evaluation; the
  budget *B* counts children (evaluations), not generations;
- each child = one parent (drawn uniformly) + one **move** from the arm's operator; a child
  equal to its parent (an empty move) is not possible by construction (§5);
- selection: the μ best of parents ∪ children by train fitness; ties by age (the older
  survives), then by index — deterministic;
- the **champion** is the best-by-train individual at the budget; ties as above; it alone is
  evaluated in holdout mode;
- the two arms share the universe, the landscape seed, the population size, the budget,
  the fitness and the seed derivation; **the operator is the only difference**.

The arm's evaluations are paired by landscape: run *r* uses landscape seed `L_r` for both
arms and operator seed `O_r` for both arms (the RNG streams diverge after the first
operator draw; pairing is on the landscape).

## 5. The operators — one shape, three maps, and the random-safe endpoint

**Decision D4.** A move is a set of 1..4 universe positions to flip in the parent.

- **random-safe** (arm A): `k ~ U{1, 2, 3, 4}`; *k* distinct universe positions drawn
  uniformly without replacement (the instrument's `random_safe`, made parent-relative).
- **map-guided** (arm B): with probability ½ a random-safe move; otherwise a **column
  move**: choose uniformly a column *v* among train columns for which the map names ≥ 1
  address; from the addresses the map places in column *v* (any LUT), flip a uniformly
  drawn non-empty subset of size ≤ 4. The operator reads the map through one interface —
  `relation.init_index` per entry, entries in state `decoded` / `confirmed` only — and never
  a LUT key, the certificate, or the target. The ½ mixture keeps every universe position
  reachable under any map, and makes random-safe the *q = 1* endpoint of the degraded-map
  family below, so a single code path covers all arms and controls.

The **map** is a `self_map` 2.0.0 document (`schemas/self_map_v2.schema.json`) and nothing
else. The arms and controls differ only in which document they are handed:

| arm / control | map document | what it tests |
|---|---|---|
| A random-safe | none (`q = 1`) | the baseline |
| B self-map | B1's board-authored map `evidence/b1/b1_17A6_2026-09-08-02/self_map_v2.json` (292 confirmed, 0 anomalies) | **the claim** |
| C oracle-map | the certificate `local_map.json` rendered into the same schema by the host | the upper bound; **fact: B1's map equals it in every relation (292/292), so B ≡ C arithmetically** — reported, not hidden |
| D shuffled-map | B's relations permuted across the 292 entries by a seeded permutation | a wrong map with the same move shape and the same size distribution: must not profit |
| E within-LUT shuffled | B's `init_index` permuted within each LUT (LUT membership kept, column identity destroyed) | round 1′'s question again: is it LUT membership or column identity that pays? |
| Q(q) degraded | B with a fraction *q* ∈ {¼, ½, ¾} of entries reset to `unknown` | dose–response: benefit should fall with map quality, continuously to A at q = 1 |

## 6. What the board does, and what the host may do (the autonomy boundary)

The board is the sole executing authority for the parent draw, the move, the fitness, the
selection and the champion (roadmap §1). Every record carries a `search` block (loop_record
1.3.0, additive): generation, parent index, the move (positions), the child's train fitness
as the board computed it, the population's fitness vector after selection, and a running
commitment `search_sha256` over the population state. The host recomputes the fitness of
every record from the served readout and replays the whole search from the records
(`b2_adjudicate.py`, B1's autonomy-replay pattern): a board that did not follow the
algorithm on its own observations is a finding per record. The host's recomputation never
reaches the board.

Because F is a pure function of the readout and the readout is a pure function of the
genome on this carrier (B1: 292/292 additive, 32/32 pairs without deviation; P3: 12 570 /
12 570 predicted), **every fitness of a B2 session is predictable before the run**, as in
round 1′. That is not the defect of round 1′ — the defect was a primary that tied by
arithmetic. What the board adds is stated plainly: the search executed autonomously on
silicon under the interlocks, the prediction reproduced candidate by candidate, and the
champions' holdout known answers; the *scientific* outcome is established by the gate over
many seeds and confirmed on the board over the preregistered N.

## 7. The discriminability gate — criteria fixed before the simulation runs

`host/b2_gate.py` runs the engine of §4 over the fabric model of `host/b1_model.py` (the
certificate's mapping; the same model that predicted B1's session) for every fitness of §3,
every arm of §5, over **S = 200 landscape seeds** derived from the gate label; the board's
seeds are later derived from a different label and are disjoint from the gate's by
construction (G6). Budget grid `{100, 200, 300, 400, 600, 800, 1000, 1500, 2000}`.

*Primary statistic.* Per landscape, the paired difference `Δ_r = best_B(r) − best_A(r)` of
best-so-far train fitness at `B*`; the decision statistic is the **sign test** on
`{Δ_r}` (one-sided, H1: map-guided > random-safe, α = 0.05; ties excluded and counted).
`N(B)` = the smallest pair count for which the sign test has power ≥ 0.9 at α = 0.05 under
the simulated Δ distribution at budget B (1 000 bootstrap experiments).

*Budget rule (frozen, v0.2).* `B*` = the grid budget with the **smallest session cost**
`N(B) × 2 × B` among the budgets at which G1 holds and `N(B)` exists; ties to the smaller
budget. All other criteria are evaluated at `B*`. *(v0.1: "the smallest grid budget at
which the oracle arm's median ≥ 60 % of the ceiling" — replaced, see the revision note.)*

| id | criterion | threshold |
|---|---|---|
| G1 non-saturation | the 95th percentile of arm C's best-so-far at `B*` is below the ceiling; arm A's median at `B*` exceeds the base fitness | both hold |
| G2 not a definitional lock | var(Δ_r) > 0 for arm B at `B*`; Δ_r for arm B takes **both signs at some grid budget** (the sign is a property of the effect and the budget, not of the definition); **and** the same decision procedure applied to arm D's pairs must *not* reject H0 in ≥ 90 % of 1 000 bootstrap experiments of size N | holds |
| G3 shuffled map does not profit | mean Δ for arm D ≤ 10 % of mean Δ for arm B, and the sign test on arm D is not significant over the full S | holds |
| G4 oracle headroom | arm C's median at `B*` ≤ 90 % of the ceiling (the problem is not solved), and arm B's mean Δ ≥ 90 % of arm C's mean Δ (the self-map delivers the bound) | holds |
| G5 effect, power, N | Cohen's d of `{Δ_r}` for arm B ≥ 0.8; `N = N(B*)` by a **full ascending scan** of the bootstrap power (no bracketing); `N × 2 × B*` ≤ **13 000** evaluations as a bound on the experiment's *total* evaluations (v0.3) — how many sessions they take is decided by the B2Q-measured all-self-reporting rate under the preregistration's split rule, never by the planning rates (S #3 ≈ 6 690 / h sampled-audit, B1's plan ≈ 3 368 / h, the last B1 mapping ≈ 2 807 / h observed), which are reported for planning only | holds |
| G6 no fixed-seed lock | S ≥ 200; the primary is a statistic over N ≥ 8 pairs; board seeds derived under their own label **with every archived seed set explicitly excluded**; **var(Δ_r) > 0** (round 1′'s 16/16 tie is named as the failure this excludes) | holds |
| G7 dose–response | mean Δ is monotone non-increasing in q over {0, ¼, ½, ¾} (arm B, Q(¼), Q(½), Q(¾)), with Q(¾) ≤ ½ · arm B; the q = 1 endpoint (arm A, Δ = 0) is reported next to Q(¾) and not required to be below it | holds |
| G8 not LUT membership | arm E's mean Δ ≤ 25 % of arm B's — the benefit is column identity, not same-LUT locality | holds |

### 7a. The control comparison G9 — predeclared (v0.3), run after this text is committed

The controls D and E of §5 permute INIT indices across the train / holdout boundary: for
control seed 0 the self-map names 183 train / 0 holdout addresses, D 112 / 71, E 111 / 72
(the review's count). D and E losing therefore shows that a wrong map costs budget, but it
cannot attribute the self-map's benefit to *correct column grouping* rather than to *knowing
which addresses matter*. Two further controls, on the **same seeds and rows as run 3**:

| control | map document / view | keeps | destroys |
|---|---|---|---|
| **T** train-membership only | one group holding the 183 train addresses (`b2_maps.train_membership_view`); a "column move" is a 1..4-subset of them | which addresses matter | column identity, column sizes |
| **W** within-train column scramble | the self-map with the train labels permuted **among the train addresses** (`b2_maps.within_train_scrambled_map`); holdout entries untouched | membership; the multiset of train column labels, hence the column-size and move-size distributions | which addresses share a column |

**G9 (predeclared).** At the recomputed `B*` (F1 / 600 unless the recomputation moves it),
paired over the 200 landscapes: `best_B − best_T > 0` **and** `best_B − best_W > 0`, each by
the one-sided exact sign test at α = 0.05. Neither T nor W is required to lose to
random-safe; their Δ versus A and the fraction of B's benefit each retains are reported.
If G9 fails, the claim is narrowed explicitly to "a correct map beats random-safe and a
wrong map does not; whether the benefit is grouping or membership is undetermined" — it is
not argued into a pass. F2 and F3 are run and reported for information; they do not enter
the selection rule.

*Selection rule (frozen).* The B2 fitness is the first of F2, F1, F3 for which every row
G1–G8 holds at its own `B*`; G9 is a condition on the **claim**, not on the selection. The gate report (`evidence/b2/gate/gate_report.json`,
`docs/b2_gate_report.md`) states every row for every fitness, PASS or FAIL, with the
numbers; a fitness that fails is reported, not tuned. **If the thresholds above are changed
after the first gate run, the change is recorded as a revision of this document with the
reason, and the gate is re-run and re-reported under the new commit** — never silently.

## 8. What B2 does not claim

- **Holdout is not generalisation.** The phenotype is six lookup tables; for **F1 and F2**
  the 24 holdout rows are parameters the train fitness never touches, so a champion's
  holdout score is what the base and neutral drift left there. **F3 is different**: its
  trajectories can pass through holdout rows (at landscape seed 123, flipping genome bit 13
  — LUT 0 / INIT 0, a holdout row — drops the train fitness from 320 to 256), so for F3
  holdout rows *do* affect train fitness and the neutrality reading does not apply. Also,
  F1 / F2 have many train-fitness optima (the holdout bits are unconstrained), although the
  complete target readout names one unique genome. It is evaluated on the hardware last as a
  known answer (predicted by the host from the champion's genome) and as a neutrality check
  (the search did not move holdout positions it had no signal for, beyond drift). If a later
  stage wants generalisation it needs a phenotype with shared parameters (routing, B4).
- **Nothing about physical noise.** The landscape is digital and replayable (roadmap §0).
- **Nothing about unattested bits, routing, FF, another die, Linux or ICAPE2.**
- **The self-map equals the oracle map.** B1 recovered 292/292; arm B and arm C are the
  same operator on the same relations. The oracle row (G4) is kept as the definition of the
  bound and because a future, imperfect self-map (unattested bits, B4) will need it.
- **Not a claim that the map-guided move is the best structured operator** — only that a
  correct map, through one fixed move shape, beats the same engine without it, and that a
  wrong map through the same shape does not.
- **A poor map is worse than no map under this operator** (gate run 1, every fitness):
  the ½ mixture spends half the budget on column moves, and when the map names few or wrong
  columns those moves re-flip a small or irrelevant subset. The dose–response is therefore
  monotone in map quality but crosses zero — the map-guided operator has a *cost* that a
  correct map must repay. B2 states this as a property of the operator; it does not tune
  the mixture to hide it (a mixture weight chosen after seeing the run would be a tuned
  parameter of the result).

## 9. Files (host-only; every one additive)

| file | role |
|---|---|
| `docs/b2_architecture.md` | this document |
| `host/b2_landscape.py` | the target rule (D2), the fitness family F1/F2/F3, train/holdout split from the carrier constants |
| `host/b2_maps.py` | the map interface the operator sees; the oracle, shuffled, within-LUT-shuffled and degraded renderings; schema validation |
| `host/b2_search.py` | the (μ + λ) engine, the two operators, the paired run — the Python reference of the future image |
| `host/b2_gate.py` | the discriminability gate: runs, statistics, criteria G1–G8, the report |
| `tests/test_b2_*.py` | determinism, fitness known answers, operator invariants (every move non-empty, inside the universe, column moves inside one column under a correct map), controls, criteria negatives |
| `evidence/b2/gate/` | run 3 (rules v0.2, as run) and run 1 (`v0.1_2026-09-10/`); `recomputed_2026_09_10/` = run 3's rows under rules v0.3; `controls_2026_09_10/` = T / W on run 3's seeds and G9 |

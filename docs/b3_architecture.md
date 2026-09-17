# B3 — the closed loop: architecture and host simulation (v0.3 — lifecycle 2, host-only, 2026-09-17)

> **v0.2.3 → v0.3 (lifecycle 2; the owner's ruling of 2026-09-17 after lifecycle 1 stopped at the
> prediction preflight, `docs/b3_lifecycle1_stop_decision_2026_09_17.md`).** One change of role in
> §9: **H9 is a gate diagnostic**, reported at every budget ≥ `B*`, and no longer a condition on
> the claim — the preregistration (v0.3) has one confirmatory primary, Δ1 = O − R, and Δ2 is a
> reported secondary outcome. The budget rule and N(B) were already sized on Δ1 alone and are
> unchanged; the criteria H1–H8, control X, the arm order and the ledger contract are unchanged.
> The gate is **re-run** under this version and a new label (`b3-gate-2`; sessions `b3-session-2`,
> qualification `b3-qualification-2`; control X's `b3-gate-x` unchanged), with lifecycle 1's gate
> run 1 and its nine session pairs in the exclusion set. Gate run 1 (`evidence/b3/gate/`, under the
> v0.2.3 text `0713dee9…`) stays as pilot / design evidence. §11 updated. This revision is
> recorded before any lifecycle-2 gate run, as §9's own rule requires.

> **v0.2.2 → v0.2.3 (the owner's review of `faa7421`, HOLD on one P2).** The derangement's
> rejection sampling is made unique: every attempt starts from the identity array and the
> RNG continues from the preceding attempt (the owner showed that "repeat the shuffle on the
> same stream" admitted a second reading — continuing from the previous attempt's array —
> that yields a different π under the pinned instrument commit). No digest is written here:
> the gate report records the one it computes.

> **v0.2.1 → v0.2.2 (the owner's review of `b729c39`, HOLD on three P2s and one P3).** Control
> X's move contract is made consistent (X's operator consumes X's own scrambled map; moves,
> readouts and fitness diverge naturally; π touches only what enters X's cartographer; the
> scramble's self-consistency is proved by a shadow cartographer isomorphic under π) and its
> PRNG, seed byte order and permutation serialisation are named; H2's sign condition is one
> condition (both signs within one budget); the arm-position equality holds when N is a
> multiple of **3**, not 6.

> **v0.2 → v0.2.1 (the owner's review of `4fbb305`, HOLD on six P2s; the decisions on d ≥ 0.5,
> the 30 000 cap, the 0.85 margin, B3Q at budget 40 and the conditional two-primary design
> accepted).** §9 now pins the gate's bootstrap algorithm and seeds (B2's, by import) and
> states H9 as a sign test at every budget ≥ `B*`; control X is a single fixed global
> derangement with a recorded digest; the arm order is a fixed prefix-balanced sequence; the
> ledger sub-block is on O **search** records only under a new schema version (the frozen
> 1.0.0 entry forbids the field); the online map gets its own schema and verifier, scored
> against the B1 truth mapping and **not** claimed to pass B1's map-lifecycle semantics; the
> 30 000 bound is a *search-evaluation* cap. Nothing in §1–§5 changed.

> **v0.1.1 → v0.2 (2026-09-17, after B2 closed and after the B3 lifecycle-1 pinned-surface
> audit `docs/b3_lifecycle1_pinned_surface_audit_2026_09_17.md` passed the owner's review at
> `3a2063d`).** §1–§5 are v0.1.1's text, unchanged: the three arms, the specimen cartographer,
> the ledger and the simulation numbers stand as **ideal-model, exploratory** evidence. What
> is new is everything a board stage needs and did not have: **§6** the namespace and the
> pin discipline the audit ruled (the frozen `host/b3_*.py` / `tests/test_b3_online.py` stay
> as B2 pinned them; the B3 implementation lives under `b3/`, with its own pin table and
> manifest that pin the B2 authority by content); **§7** the B3 image and the record / ledger
> contract; **§8** the autonomy boundary and the replay obligations; **§9** the B3
> discriminability gate — criteria and the budget / N rule **fixed before the gate simulation
> is run** (B2's discipline, §7 there); **§10** what B3 does not claim; **§11** files. The
> preregistration draft is `docs/b3_preregistration.md`. **Standing: host-only design. No
> pinned edit, no pin table, no manifest, no image, no ruling, no board.** B2 closed at S3
> `aec84514…` (PASS / SUPPORTED, `docs/b2_result_2026_09_17.md`); it is the historical
> premise of this stage and hands B3 no authority (preregistration §8a).


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

## 6. Where B3 lives — the namespace and the pin discipline (audit ruling 2b + 3)

The completed B2 pins `host/b3_online.py`, `host/b3_sim.py` and `tests/test_b3_online.py` by
name and captures `host/b3_*.py` / `tests/test_b3_*.py` by glob; the B2 S3 verify refuses by
name if any of them is modified, deleted or joined by a new file (the audit's probes 4–11).
B3 therefore does not develop in place:

- **Frozen wrappers.** The three files stay byte-for-byte as B2 pinned them, for as long as
  the tree is expected to verify B2 — which is always. They are the v1.1 host reference of
  §3 and the record of the simulation of §5; they are imported, never edited, and never
  joined by a `host/b3_*.py` or `tests/test_b3_*.py` file (audit I-1, I-2).
- **The `b3/` namespace.** Every B3 implementation file lives under a top-level `b3/`:
  `b3/host/` (the cartographer copied from the frozen reference and then developed; the
  online arm; the runner, records, session, adjudicator, plan, manifest, pins, test report),
  `b3/tests/`, `b3/schemas/`, `b3/firmware/` (the image sources and BSP inputs),
  `b3/tb/hostapp/` (the C harness the pinned test compiles). The B2 globs cannot see any of
  it (probe 16). The test command is `python3 -B -m unittest discover -s b3/tests` (no `-t`,
  no package files — the `-t .` form is not importable without them; measured).
- **The B3 pin table** `manifests/b3_instrument_pins.json` (`b3/host/b3_pins.py`): rule
  **`b3/**/*` filtered to regular files** (`b3/**` alone lists directories only — measured),
  plus `docs/b3_architecture.md`; its tests prove a new file at depth 1, 2 and deeper each
  refuses as *not in the table*. The B2 modules B3 imports by content (`host/b2_search.py`,
  `b2_landscape.py`, `b2_maps.py`, `b2_gate.py`, `host/b1_carto.py`, `b1_model.py`) are pinned
  through `manifests/b2_instrument_pins.json`, which the B3 manifest pins by content — as B2
  pins B1's table.
- **The B3 manifest** `manifests/b3_manifest.json` (`b3/host/b3_manifest.py`) pins, in its
  own block and by content, the seven **indirect frozen inputs** the audit named (§7a there):
  the B2 manifest `aec84514…` and the B2 table `82a5f2fb…`; the completion-input archive
  `evidence/b2/b2_completion_inputs_2026-09-17/inputs.tar.zst` `20300d5f…` and its manifest
  `archive.json` `ca5fedd7…` (the 15 non-tracked files the B2 verify needs, so the B2 lineage
  stays reproducible); and the three B3 files the B2 verify or its frozen test reads
  (`evidence/b3/sim/sim_report.json`, `evidence/b3/sim/raw_F1.json`,
  `schemas/specimen_ledger.schema.json`). **`verify` checks these seven by existence and
  digest first**, naming the one that is absent or drifted; only then does it call the B2 S3
  verify and require S3 / true / null / `aec84514…`, re-raising a B2 refusal under the B3
  name; any other exception is an INTERNAL ERROR and is never converted into a refusal.
- **Evidence.** `evidence/b3/sim/` and `evidence/b3/sim_v0.1.1/` are never moved or
  rewritten (the first is a B2 verify input through the seed exclusion); new B3 evidence
  goes under `evidence/b3/<unit>/`. A revised ledger schema is a new file under
  `b3/schemas/`; `schemas/specimen_ledger.schema.json` stays.
- **Order.** Every pinned edit first — the cartographer copy, the arms, the lifecycle tools,
  the image sources, the tests (each reviewed; the stage-aware test audit of the
  preregistration §9 before anything is frozen) — then the pin table generated **once**,
  then S0. The table is never patched; a later pinned edit returns the line to the edits and
  the table is regenerated.

## 7. The B3 image and the record / ledger contract

**Decision E1 — the image is B2's plus the cartographer.** `b3/firmware/` is derived from
`firmware/b2/` the way B2's was derived from B1's (`IMPORT.json` names every verbatim file
and every changed one): the instrument's `p3_derive` / `p3_rectx` / `p3_pull` / BSP / linker
byte for byte; `b2_search.c` (the engine, the two operators) unchanged; new `b3_carto.c`, the
C twin of the specimen cartographer (`SpecimenCarto` v1.1 semantics: candidate-set
intersection, global closure, validate-then-commit, anomalies counted, the version bump);
`b3_orch.c` running the **three arms per pair** (R, F, O) in the preregistered arm order;
`b3_wire.c` = `b2_wire.c` with `app_identity` 1.6.0 and `loop_record` 1.4.0 (below). The F
arm's map is the B1 self-map compiled as B2 compiled it (`B2_MAP_INIT` for the column view,
`B2_MAP_LUT` only for the universe mask); the **O arm starts empty** and reads nothing but
its own decoded state — a leakage test proves the online view is empty at evaluation 0 and
that the O operator never reads `B2_MAP_INIT`. No LUT site key, no certificate, no oracle
rendering in the image (B2's scans, extended to `b3_carto.c`'s tables).

**app_identity 1.6.0** adds to B2's 1.5.0: `carto_version` (`specimen-carto-v1.1`), `arms`
(`"RFO"`), `b1_map_cost` (333, the constant the end-to-end accounting charges — carried so
the identity says what the accounting is), and the same per-session pair slice.

**loop_record 1.4.0** keeps B2's `search` block (`arm`, `best`, `column_moves`, `eval`,
`fitness`, `generation`, `holdout`, `landscape_seed`, `move`, `operator_seed`, `pair`,
`parent_born`, `population`, `selected`, `state_sha256`, `version`) and, **on O-arm search
records only** — never on an O champion's holdout record, which evaluates a genome the search
already produced and **does not update the map** —, adds a `ledger` sub-block = one entry of
**`specimen_ledger` 1.1.0** (`b3/schemas/specimen_ledger.schema.json`, a new file: the frozen
1.0.0 entry has `additionalProperties: false` and cannot carry the running count): `seq`,
`map_version` (before), `intervention` (the moved addresses), `move_kind` (`random` |
`column`), `behaviour_delta` (the (LUT, vector) positions that toggled, from the board's own
two readouts), `fitness`, `confidence` (2 for a single-bit specimen, 1 otherwise), `decoded`
(the addresses this specimen decoded, with their positions), `map_version_after`, and
`anomalies` (the running count — the one field 1.1.0 adds to the entry; the document-level
fields of 1.0.0 are kept). A session's O-arm ledger therefore has exactly B entries per pair. The **`state_sha256` commitment on O-arm records covers the
cartographer state as well**: the map version, the sorted decoded relations, the sorted
candidate sets and the anomaly count (`b3_carto_state_hex`), so the replay checks that the
board's map at every step is the one its own specimens imply. The board never sees the
certificate; `decoded` is what the board believes, audited afterwards (§8).

**Records per pair** = 3 × B + 3 (three arms' searches, three champions' holdout
evaluations, no holdout-mode bit — as B2), of which B carry a ledger entry. Per session:
2 baselines + the session's pairs. **Arm order** within pair r: the (r mod 6)-th of the fixed
prefix-balanced sequence **RFO, FOR, ORF, ROF, OFR, FRO** — over any N the number of times an
arm occupies a position differs by at most 1 between arms, and is equal exactly when N is a
multiple of **3** (the first three permutations already place every arm once in every
position); the order is part of the plan and the prediction. The ledger adds bytes to
every O-arm search record, so the all-self-reporting rate is B3's own (B3Q at budget 40:
3 × 40 + 3 = 123 scored records, 40 ledger entries, plus 2 baselines = 125 records), never
B2's 3 016 / h.

## 8. What the board does, and what the host may do (the autonomy boundary, extended)

Unchanged from B2 (roadmap §1) for the parent draw, the move, the fitness, the selection
and the champion. **The map update is an executing decision and stays on the board**: the
cartographer runs on the PS from the two readouts it already has (parent and child), and the
O operator consults the current version. The host, after the session and never during:

1. recomputes every fitness from the served readout (B2's rule, EXACT per record);
2. replays the three searches from the records (EXACT per record);
3. **replays the ledger**: feeding the O-arm records' `intervention` and `behaviour_delta` to
   the reference cartographer must reproduce every `decoded`, every `map_version`, the
   anomaly count and the `state_sha256` projection at every step (EXACT);
4. recomputes every `behaviour_delta` from the served parent and child readouts (EXACT —
   the board's delta is a self-report; the readouts are measured);
5. **audits the decodes against the certificate** (`local_map.json`): every decoded
   relation must be the certificate's (0 wrong decodes) — the B1 boundary: the certificate
   is the host's, after the fact, never the board's;
6. renders the final online map of every O run as an **`online_map` 1.0.0** document
   (`b3/schemas/online_map.schema.json`: the decoded relations, the map version, the anomaly
   count, the ledger digest it was built from) and scores it with the **B3 online-map
   verifier** (`b3/host/b3_online_map.py`): schema validity, internal consistency (one
   position per address, no position twice), and **accuracy against the B1 truth mapping**
   (`b1_model.truth_mapping`, i.e. the certificate — host-only, after the fact): decoded
   count, wrong decodes (must be 0), coverage of the 292. **This is not B1's map-lifecycle
   verifier**: B1's semantics require the nine code probes and the 32 interaction edges,
   which an online map built from specimens does not have and does not claim; passing
   `host/verify_local_map.py` is neither required nor asserted.

Because the fabric is additive (B1: 292/292, 32/32 pairs; P3: 12 570 / 12 570 predicted) and
the cartographer is deterministic, **every fitness, every decode and every map version of a
B3 session is predictable before the run** from the seeds — the O arm included. B3 is, like
B2, a prospective reproduction of a fixed prediction (preregistration §3); its silicon
information is that the board built its map from its own specimens under the interlocks and
that the prediction reproduced record for record, decode for decode. The predicted anomaly
count is 0; an anomaly on silicon is a finding about the fabric or the image, not about the
loop (preregistration §5).

## 9. The B3 discriminability gate — criteria fixed before the gate simulation runs

`b3/host/b3_gate.py` runs the engine of §2 over
the fabric model of `host/b1_model.py` for the three arms and the controls below, **S = 200
landscape seeds** under the label **`b3-gate-2`** (lifecycle 2; disjoint from every archived set by
explicit exclusion, as B2's — including lifecycle 1's gate run 1 under `b3-gate` and its nine
session pairs under `b3-session`), budget grid `{100, 200, 300, 400, 600, 800, 1000, 1500, 2000, 3000}`,
fitness **F1** (B2's selected fitness — B3 does not re-select; F2 is reported for
information). The v0.1.1 simulation (§5) is *not* the gate: it ran under a different label,
before these criteria were written, and its numbers are exploratory.

*The primary and the secondary statistic, paired by landscape.* The **primary** `Δ1_r = best_O(r) − best_R(r)` at `B*` (search
accounting; R and O are charged nothing); the **secondary outcome** `Δ2_r = best_O(r) − end_to_end_F(r)` at total budget
`T = B*`, where `end_to_end_F(r)` is F's own best-so-far trace at `T − 333` (the base fitness
while `T ≤ 333`) — the frozen arm charged B1's mapping cost, from **the same F run**, no extra
evaluation. Decision statistic for each: the one-sided exact sign test (α = 0.05, ties
excluded from *n* and counted) — **`b2_gate.sign_test_p`, by import**. `N(B)` = the smallest
pair count with bootstrap power ≥ 0.9 for Δ1 at budget B — **`b2_gate.required_pairs`, by
import, unchanged**: for each candidate N from 8 to S in ascending order (no bracketing),
1 000 experiments, each a resample **with replacement** of size N from the S paired Δ1
values, `random.Random(1 + N)` (B2's seed 1 plus the candidate N, exactly as B2 computed
N(B*) = 9); the control null non-rejection of H2 uses `b2_gate.bootstrap_reject_rate` with
**seed 7** (B2's). These functions are pinned by content through the B2 table; the gate
report records the seeds it used. *Exploratory only (not the gate):* the owner's application
of B2's algorithm to the v0.1.1 rows gives roughly `B*` = 1 000, N = 8, search cost 24 000;
the gate run decides.

*Budget rule (frozen).* `B*` = the grid budget with the smallest session cost `N(B) × 3 × B`
among budgets at which H1 holds and `N(B)` exists; ties to the smaller budget. Every other
row is evaluated at `B*`.

| id | criterion | threshold |
|---|---|---|
| H1 non-saturation | the 95th percentile of arm O's best-so-far at `B*` is below the ceiling (40); arm R's median at `B*` exceeds the base fitness | both hold |
| H2 not a definitional lock | var(Δ1_r) > 0 at `B*`; **there exists a grid budget B at which both `positives(Δ1(B)) > 0` and `negatives(Δ1(B)) > 0`** (one condition, evaluated within one budget; v0.1.1 already shows it at 300: 41 positives, 130 negatives — the mean's change of sign across budgets is *reported* next to it and is not a criterion); and the same decision procedure applied to control **X** (below) does not reject H0 in ≥ 90 % of 1 000 bootstrap experiments of size N (`bootstrap_reject_rate`, seed 7) | holds |
| H3 a wrong online map does not profit | control **X — scrambled specimens** (the contract below): mean Δ_X (X − R) ≤ 10 % of mean Δ1 and X's sign test against R is not significant over S; X's map growth (decoded count per grid budget) is reported, not assumed equal to O's | holds |
| H4 the frozen map is the bound the online map approaches | search accounting: arm O's median at `B*` ≥ 80 % of arm F's; end-to-end: the sign test on Δ2 over the S seeds rejects (O − F > 0 at `B*`) — an S = 200 **model-gate** statistic meeting its threshold before any board time, not a board-session or pooled-result threshold (v0.3: Δ2 is the preregistration's reported secondary outcome; this row says the S = 200 gate statistic met the threshold, not that N pairs will show it) | both hold |
| H5 effect, power, N | Cohen's d of {Δ1_r} ≥ 0.5 (the online arm pays the poor-map cost first, §5.3; 0.8 is B2's threshold for a map that is correct from evaluation 0); `N = N(B*)`; `N × 3 × B*` ≤ **30 000** as a **search-evaluation cap** — holdout evaluations, baselines and the session record totals are counted separately by the plan and are not inside this number (B2's cap was 13 000 for two arms); how many sessions the records take is decided by the B3Q-measured rate under the split rule with its margin, never by planning rates | holds |
| H6 no fixed-seed lock | S ≥ 200; N ≥ 8; board seeds under `b3-session-2|` with every archived set excluded (B2's gate runs, the B3 simulation, B2's plan and B2Q seeds, lifecycle 1's gate run 1 and its nine `b3-session` pairs, this gate); var(Δ1_r) > 0 | holds |
| H7 the online map is a map | over S: 0 wrong decodes and 0 anomalies in the ideal model (a nonzero count is a defect of the cartographer or the model, not a result); the median decoded count at `B*` ≥ 146 (half of 292); the fraction of seeds whose map is complete by the largest grid budget reported | holds |
| H8 ledger replay | for every seed, replaying the ledger reproduces every map version and every decode (EXACT); the ledger validates against the schema | holds |
| H9 (v0.3: a **diagnostic**, neither a pass criterion nor a claim condition) | the one-sided exact sign test on Δ2 (O − end-to-end F) at every grid budget B ≥ `B*`, with mean and median Δ2, and — reported next to it — the pair count N₂(B) the same bootstrap rule would need for Δ2 and its power at the gate's N | reported; it decides nothing (Δ2 is the preregistration's secondary outcome, v0.3) |

**Control X, precisely.** X is the online arm run by the **same algorithm and the same RNG
rule as O** (`b1_carto.Rng(operator_seed)`, the same landscape and operator seeds per pair,
the same engine and operator code path); its operator **consumes X's own scrambled map**, so
after the first differing decode X's moves, readouts and fitness values diverge from O's
naturally — nothing is forced equal. One global permutation **π of the 384 positions**
(index = 64 · LUT + vector, in (k, v) order) is drawn **once per gate run**: `seed_X =
b2_search.master_seed("b3-gate-x", instrument_commit)` (= `int.from_bytes(sha256("b3-gate-x|" ‖
commit)[:4], "big")`, the rule every B-line seed uses); PRNG = the instrument's `b1_carto.Rng`
seeded with `seed_X`; Fisher–Yates from i = 383 down to 1 with `j = rng.uniform(i + 1)`,
rejection-sampled until the result has no fixed point: **each attempt starts from the
identity array `[0, …, 383]`; the RNG is not reset and continues from the preceding attempt**
(a derangement; deterministic and unique — an implementation that shuffled the previous
attempt's array again would produce a different π). π acts on **only one thing**: the
`behaviour_delta` of each of X's specimens is mapped position-wise through π **before it
enters X's cartographer**; the readouts, the fitness, the search state and the move it
produced are untouched. **Self-consistency is proved, not assumed:** a **shadow
cartographer** that takes no part in the search is fed X's actual specimens with their
*unpermuted* deltas; after every specimen the gate requires the shadow's state and X's
cartographer state to be **isomorphic under π** — same version, same anomaly count, and for
every address the X candidate set / decoded position equals π applied to the shadow's (EXACT
per specimen; a single mismatch fails the gate run as a defect, not a result). The gate
report records `seed_X` and `permutation_sha256` = sha256 of the canonical JSON array
`[π(0), …, π(383)]` (compact, no spaces, UTF-8).

*Controls, all on the same seeds and rows:* **X** scrambled specimens (H2, H3); **F** is
itself the positive control for the operator (B2 established that the correct map beats R);
**R** the baseline. A degraded-map family is not needed: the online arm *is* the dose–response
in time (its map grows from 0 to 292), and its curve against R is reported per grid budget.

*Selection.* Nothing is selected: F1 is fixed by B2. The lifecycle-2 gate report
(**`evidence/b3/gate_2/gate_report.json`**, rendered as **`docs/b3_gate_2_report.md`** — lifecycle 1's
`evidence/b3/gate/` and `docs/b3_gate_report.md` are historical evidence and are never overwritten)
states every row PASS or FAIL with the numbers and H9 as a diagnostic; a row that fails
is reported, not tuned. **If any threshold above is changed after the first gate run, the
change is recorded as a revision of this document with the reason, and the gate is re-run
and re-reported under the new commit** — never silently. `B*` and `N` are the gate's
numbers and are written into the preregistration before S1; the preregistration draft
carries them as placeholders until then.

## 10. What B3 does not claim

- **Nothing about a non-additive fabric.** The cartographer's anomaly path is exercised by
  tests, not by silicon; on this carrier the predicted anomaly count is 0 and any other
  value is a falsifier of the instrument (preregistration §5), not a finding about
  non-additive fabrics (B4's).
- **Nothing about physical noise, timing, power, unattested bits, routing, FF, another die,
  Linux or ICAPE2** (B2 §8, unchanged).
- **The end-to-end accounting is an evaluation-count model.** B1's two baseline records,
  setup, qualification, audits, retransmissions and compute time are not counted; the 333
  charged to F is B1's probe budget, not its wall time. The secondary outcome is a statement
  inside that model.
- **Not the best online cartographer** — one fixed rule (intersection with global closure)
  on one fixed operator shape; nothing was tuned after the v0.1.1 simulation and nothing
  is tuned after the gate.
- **Not an independent silicon chance of a negative primary.** With fixed seeds and an
  exact prediction the deltas are fixed; the board reproduces them or the instrument is
  held (B2 §1, unchanged).
- **The frozen host reference stays frozen.** `host/b3_online.py` v1.1 is B2's pinned
  file; the `b3/host/` cartographer is a copy that may evolve *before* the B3 pin table is
  generated and not after; a one-time equivalence test between the copy and the frozen
  module over the simulation seeds is allowed (import, never edit).

## 11. Files

| file | status | role |
|---|---|---|
| `docs/b3_architecture.md` | this document, v0.3 (lifecycle 2) | design; the gate criteria of §9 |
| `docs/b3_preregistration.md` | DRAFT v0.3 (lifecycle 2) | what a board session is judged by |
| `docs/b3_lifecycle1_pinned_surface_audit_2026_09_17.md` | PASS (`3a2063d`) | the namespace / pin ruling (§6), the verifier contract, the lifecycle order, the stage-aware test rules, the authority boundary |
| `host/b3_online.py`, `host/b3_sim.py`, `tests/test_b3_online.py` | **frozen by B2** | the v1.1 host reference and the v0.1.1 simulation; never edited |
| `evidence/b3/sim/`, `evidence/b3/sim_v0.1.1/` | frozen (the first a B2 verify input) | the v0.1 / v1.1 simulations |
| `evidence/b2/b2_completion_inputs_2026-09-17/` | committed (unit 1) | the 15 non-tracked B2 inputs, restorable and verified |
| `b3/host/b3_carto.py`, `b3_online_arm.py`, `b3_control_x.py`, `b3_online_map.py`, `b3_gate.py`, `b3_gate_report_md.py`, `b3_plan.py`; `b3/schemas/`; `b3/tests/` | written in lifecycle 1 (reviewed to `25c7ede`, `8b43205`, `b1b82d0`); the lifecycle-2 gate / plan changes listed in preregistration §10 remain | the implementation so far, under the pin rule `b3/**/*` |
| `b3/host/` records, session, adjudicator, runner, manifest, pins, test report; `b3/firmware/`; `b3/tb/hostapp/` | **not yet written** | the rest of the pinned edits |
| `manifests/b3_instrument_pins.json`, `manifests/b3_manifest.json` | not yet generated (steps 3–4) | the B3 authority |
| `evidence/b3/gate/` | lifecycle-1 run 1 (pilot / design evidence, under v0.2.3) | the gate of §9 as it was |
| `evidence/b3/gate_2/` | not yet run | the lifecycle-2 gate of §9 under this version and the label `b3-gate-2` |

# B4 — expansion from LUT content bits to the FF class, then routing: architecture (DRAFT v0.1, host-only, 2026-10-16)

> **Standing: a draft architecture, not a preregistration and not a ruling.** Written under the
> owner's authorisation of 2026-10-16 (unit 2a of the B4 pre-work: this one document, on the
> branch `b4-prework` from `main` `d5bf815`; no code, no schema change, no board, no purchase).
> It applies `docs/autonomous_cartography_roadmap.md` §7 — "a host-only architecture /
> preregistration package … reviewed before carrier v2 is designed" — to stage B4, and the
> owner's four rulings of 2026-10-16: B4-FF first; B4-R only its question, prerequisites and
> prohibitions, under its own later preregistration; the 1 756 unattested `clb_lut_init`
> entries not in scope; the FF scorer specified as functional requirements, an observation
> contract and acceptance conditions, never as RTL; the current-limited supply recorded as a
> prerequisite with no measurement evidence yet. Every number in this document is either
> quoted from a named source or marked `<gate>` (to be fixed by unit 2b before it is measured).
> Nothing here authorises any board contact.

## 0. The question, and why it is two studies

The roadmap names B4 as "from LUT content bits to FF, then routing — content classes on any
verify board; routing only on the sacrificial board" (§2, §3). B1–B3 established, on one
board and one carrier, that a board can map 292 certified LUT-INIT bits from its own probes
(B1), that a frozen self-built map makes the same search engine beat random-safe (B2), and that
an online-updating map closes the loop record for record (B3, `docs/b3_result_2026_10_15.md`).
All three say the same thing about what they do not cover: "nothing about unattested bits,
routing, FF, another die" (`docs/b2_architecture.md` §8, `docs/b3_architecture.md` §10).

B4 asks whether that chain survives a bit class whose meaning is **not a truth table**. It is
two studies because the risk and the question differ:

| | **B4-FF** (this document's subject) | **B4-R** (§3 only) |
|---|---|---|
| class | `clb_ff_config`, a content class (`docs/board_roles.md`: content-class writes need `role ∈ {verify, sacrificial}`) | `int_pip`, the routing class (routing-class writes need `role = sacrificial`, no override) |
| question | can the board map, and then use, bits whose effect is sequential behaviour rather than a combinational function? | can a routing bit be probed and composed without contention, and what does a map of it buy? |
| ground truth held back | the FF class certificate (§4) | none that is silicon-attested; the frozen DB names 7 272 entries |
| board | the verify board `17A6` under the P3 discipline (roadmap §3) | the sacrificial board, after the four conditions of roadmap §4 |
| risk | the content-bit boundary — the same as B1–B3 | the only work in the line that can damage hardware (roadmap §5) |
| package | this architecture → a gate simulation (unit 2b) → a preregistration (unit 2c) | its own preregistration and ruling; never the baseline of a map-guided A/B (roadmap §4, hard line 2) |

The 1 756 `clb_lut_init` entries that the frozen DB names and no specimen ever attested stay
outside B4 (roadmap, the B1 section: "a separate ruling"; the owner, 2026-10-16).

## 1. Where B4 begins — the boundaries with B1, B2 and B3

What B4 inherits is evidence and discipline, not code it may change:

- **From B0 / the instrument** (`zynq-psoracle` `689dde1`, archived, read-only): the three
  links, the signed ARM, the nonce chain, the watchdog, rel-v4, the stop-loss, the identity
  page. Reopened only under a new ruling after a new carrier package passes review (roadmap §6).
- **From B1**: the noninterference contract (`docs/b1_carrier_contract.md`: the host signs
  writability only, never expected semantics; the readout reaches the cartographer raw), the
  guard set (`docs/b1_architecture.md` §5: header without tables, source-include scan, binary
  scan, verbatim imports, the permuted fixture, the address-only baseline, the autonomy
  replay), and the rule that the certificate is scored against the map only after the map is
  frozen and hashed.
- **From B2**: the two-arm discipline (shared universe, selection, population, budget,
  fitness and seeds; the operator the only difference), the discriminability gate's form
  (`docs/b2_architecture.md` §7: G1–G8, the controls, the selection rule, the revision rule),
  the map schema v2 (`schemas/self_map_v2.schema.json`) and the oracle row kept "because a
  future, imperfect self-map (unattested bits, B4) will need it" (§8).
- **From B3**: the specimen ledger and the online cartographer (`docs/b3_architecture.md`
  §3), the control X contract (§9), the lifecycle S0 → S3 with its pin table, manifest,
  clean-tree proof and stage-aware test rule (`docs/b3_preregistration.md` §8, §9), and the
  statement that "the board's anomaly counter is where B4's routing bits will show" (§5) —
  i.e. the cartographer's anomaly path has been exercised by tests, never by silicon.

What B4 may not do with that inheritance: edit any pinned file of `b3/**`, `host/`, `tests/`,
`firmware/` or `schemas/` (every B1–B3 verdict binds to their digests through the three pin
tables, `manifests/b1_instrument_pins.json`, `manifests/b2_instrument_pins.json`, `manifests/b3_instrument_pins.json`). A module B4 needs is **copied** into the
B4 namespace and declared in an import table with `verbatim` / `derived` / `new` kinds and
digests — the discipline `b3/firmware/IMPORT.json` already applies to B2's firmware — never
imported across the namespace boundary and changed in place.

## 2. The autonomy boundary, restated for a sequential class

Roadmap §1, which this document does not relax: *the board is the sole executing authority
for probe choice, candidate choice, fitness, selection and map update; the host is notary,
auditor, rel-v4 transaction endpoint and collector; it may independently recompute any of
those after the data is submitted, as an audit, and the result of that recomputation may
never feed back into the board's decisions in that session or into a map update.*

Applied to B4-FF, two things are added, both consequences rather than new rules:

1. **The certificate and every oracle derived from it are host-side reference answers,
   invisible to the executing side.** They are used (a) by the host simulation of unit 2b,
   where an oracle map is a control; (b) by the adjudicator after a session, to score a
   frozen, hashed map. They are never compiled into the image, never consulted by the board,
   never used to choose, score or stop a candidate during a session, and never used to
   update a map version. The B1 guards (header, source, binary scans; the permuted fixture)
   are the mechanism, extended to the FF class's names and fields.
2. **The observation is raw before it is a fitness.** For a sequential class the board must
   first *observe* (§5) and only then *score*; the two records are separate in the ledger, so
   that an audit can recompute the fitness from the raw observation and a semantic that the
   observation cannot resolve stays `unknown` (§5.4) instead of being decoded by assumption.

## 3. B4-R — the routing study: question, prerequisites, prohibitions (nothing else here)

**Question** (to be sharpened by its own preregistration, not here): on the sacrificial board,
can a routing-class bit be probed under the escalation ladder — readback-only, then
specimen-derived certified compositions, then unconstrained composition — without a wedge that
the acceptance regression later shows to be damage; and does a map of such bits buy anything
for a search that is not already decided by the content-bit map?

**Prerequisites, every one unmet today, each machine-checked where a tool exists:**

| # | prerequisite | source | status 2026-10-16 |
|---|---|---|---|
| R1 | `08EB` physically labelled as the sacrificial board | roadmap §4 hard line 1; `docs/board_roles.md` | not done |
| R2 | `08EB` carries the TF / U-Boot control plane with `boardid` and `role=sacrificial` saved | same | not done — `08EB` has no boot medium and no environment (`/home/test/test_devices/result.txt`, the 2026-08-25 retest: "目前仍無開機媒體") |
| R3 | `08EB` runs on a current-limited 5 V supply | same; roadmap §5 item 4 | **no measurement evidence exists**: the trip threshold, sampling rate, reaction time from event to de-configuration, the external cut-off and the fallback when `PCFG_PROG_B` does not take effect "must all be measured on the bench before the first routing write" — none has been; this is a to-be-measured prerequisite, not a protection in place |
| R4 | `08EB` passes the acceptance regression again, after R1–R3 | roadmap §4; `docs/board_roles.md` "Wedge is not damage" | the 2026-08-25 xsdb retest passed 6 / 6 as a known-answer round; it predates R1–R3 and does not count for them |
| R5 | a host-side contention checker over the frozen DB model (one driver per node, listed codeword per mux group), with the limits of `docs/mux_groups.md` stated | roadmap §5 item 1 | exists for content classes' composition rules; its routing-class coverage is not assessed here |
| R6 | region isolation proven from the routed design, bounded-exposure transactions, blacklist-never-retry, power-cycle between sessions, the acceptance regression plus a fabric self-test of the probed region after every session | roadmap §5 items 3, 5–8 | design intentions |
| R7 | its own preregistration and ruling pair | roadmap §4 hard line 2 | not written |

**Prohibitions, standing until that preregistration is frozen and ruled:** no tool treats
`08EB` as sacrificial (a board that does not answer with `role=sacrificial` is refused); no
routing-class write anywhere; no routing bit in any B4-FF universe, control or landscape; the
routing study is never the baseline of the map-guided vs random-safe comparison; no purchase
and no bench work is implied by this document.

## 4. The FF universe — what is counted, what the certificate proves, and what it does not

### 4.1 Counting discipline: 176 feature entries, 168 distinct addresses

The frozen DB names **176** `clb_ff_config` feature entries (`data/MANIFEST.json`), every
one single-bit; the class preregistration plan (`docs/ff_preregistration_plan.md` §1) groups
them by polarity-free coordinate set into **168 groups = 160 singletons + 8 two-member
groups**, the eight being exactly the `CLKINV` / `NOCLKINV` pairs, which **share one
coordinate** and differ only by the sign of the bit. So:

- a **universe** for the board (the whitelist, the genome, the map's `entries`) is counted in
  **addresses**: 168 per the eight site instances of the plan's family, or the per-slice count
  the preregistration fixes; **never 176** — the complementary names are two readings of one
  bit, not two independently writable bits;
- the **Z polarity convention** is a property of the names, not of the fabric: `ZINI = 1 ⟺
  INIT = 0`, `ZRST = 1 ⟺ SRVAL = 0`, `CEUSEDMUX = 1 ⟺ CE driven`, `SRUSEDMUX = 1 ⟺ R driven`,
  `FFSYNC = 1 ⟺ synchronous` (plan §2, "a falsifiable prediction, not bookkeeping"); the
  board sees bits and behaviour, never these names;
- per site instance the plan's family is 16 per-FF bits (8 FFs × {ZINI, ZRST}), 4 per-slice
  singletons (`CEUSEDMUX`, `FFSYNC`, `LATCH`, `SRUSEDMUX`) and 1 per-slice complementary pair
  (`CLKINV` / `NOCLKINV`) = **21 addresses** carrying 22 feature names; 8 instances give the
  168 / 176 above.

### 4.2 What the certificate establishes — and its limits

`gate_runs/run_2026_08_05_ff/certificate.json` (schema 1.6.0, `status: passed`,
`semantic_status: passed`, committed as `90527e6` "certify the clb_ff_config holdout") was
produced under the committed plan (`2b40693`): 184 specimen bitstreams, 168 endpoint pairs,
176 predictions, the twelve directional predictions of plan §2 taken as written, `tp = 154`
on the holdout, `fn = fp = 0`, coverage 176 / 176 (plan §4), and one `member_identity`
assertion per feature resolved into the pinned readback attestation (plan §3). It proves:

- the **correspondence between host specimens and attestations**: for every one of the 176
  keys, the bit the frozen DB names moves when, and only when, the preregistered design
  variant is built — a statement about Vivado's output and the DB's naming, on the host;
- the **polarity readings** of plan §2, as predictions that a wrong reading would have failed.

It does **not** prove:

- **silicon behaviour**: "nothing in this line has been on a board, and a semantic failure
  never touches the address decision" (plan §3) — that an FF whose `ZINI` bit is set powers
  up at 0 on this die, that `CLKINV` inverts the sampled edge, that `LATCH` is transparent,
  are all unobserved;
- **safety of arbitrary combinations**: the certificate is about single-bit movements between
  preregistered endpoints; the plan's own §5 names modes that are illegal in combination
  (`LATCH` is unreachable on `A5FF` and its siblings; a keeper valid in one mode was illegal
  in another). A B4-FF universe is therefore **not** "any subset of the 168 addresses" until
  a composition rule for the class is stated and checked, host-side, before the first write;
- **novelty to a human**: the certificate exists and its author has read it, as B1 said of the
  292 (roadmap, the B1 section). What B4-FF can claim is closed-book, runtime-blind
  reconstruction by the executable, protected by the B1 guards — never "a human-unseen
  discovery".

### 4.3 The certificate's role in B4-FF

A **reference answer invisible to the executing side** (§2), used by the unit-2b simulation
(the fabric model and the oracle-map control) and by the post-session adjudicator (scoring the
frozen, hashed map; the B1 primary metrics — precision, recall, polarity errors, sample
efficiency, confidence calibration, cold-boot replay, map-hash consistency — apply per address,
with "polarity" now meaning the Z reading of §4.1). The certificate's **22 / 154 mine /
holdout split** (plan §7, ruling 1: `mine = {SLICE_X2Y25}`) is the certificate's own
engineering holdout against *its* tuning; it is **not** B4's holdout. B4-FF's holdout — by
whole site instance, not consulted while the FF cartographer is developed — is fixed by the
preregistration (unit 2c), and the preregistration says in one sentence why it is an
engineering holdout and not a claim that the truth was unseen.

## 5. The observation contract for FF semantics — functional requirements, not RTL

What the line can observe today is combinational: the B1 carrier's arm gate "sweeps all 64
vectors and exposes the readout raw" (`docs/b1_carrier_contract.md` §2) — a truth table per
LUT. An FF configuration bit has no truth table; its effect appears only across clock edges,
resets and time. A **carrier v2 scorer** is therefore required, and this section states what
it must do and how it will be accepted — the design (RTL, timing, placement) belongs to a
later, separately authorised unit and is not sketched here.

### 5.1 One observation, as a sequence the board can replay

For every candidate the board must be able to perform, and the ledger to record, the
following in order, with nothing of it computed on the host before the measurement:

1. **Initial state** — the slice under test brought to a defined state before any clock:
   the configuration written (link 1 as today: the host signs writability only), the fabric
   readback hashing to the commit (link 3), then **a global or regional reset of the storage
   elements under a stated discipline** (which reset, asserted how long, released when) so
   that what is observed next is the configuration's power-up / reset behaviour and not the
   previous candidate's leftover state.
2. **Stimulus sequence** — a preregistered, seed-derivable sequence of `(clock-enable,
   synchronous-set / reset, data)` vectors applied over `K` clock edges to every storage
   element of the site, with the clock itself under the scorer's control (so that an inverted
   clock, an enable that is or is not driven, a synchronous versus asynchronous reset and a
   latch's transparency each produce a **distinguishable** observation at least once in the
   sequence — the sequence's discriminating power is a 2b simulation result, not an assumption).
3. **Readout** — the storage elements' outputs sampled at stated points of the sequence
   (after each edge, and between edges for transparency), exposed **raw**: no comparison with
   an expected value anywhere in the PL or the application before the record is written.
4. **Restore** — the candidate undone and the base configuration re-established and read back
   (link 3 again), **and the storage elements reset once more**, before the next candidate.
5. **Isolation between candidates** — the record of candidate *n+1* must not depend on the
   state candidate *n* left behind: the reset of step 1 is part of every candidate, the
   stimulus sequence restarts from its seed, and the scorer's own state machine is returned
   to idle; an audit recomputes the fitness from the raw observation alone (§5.3).

Everything the instrument's links already give — the signed ARM, the staging re-read, the
twelve-frame readback, the nonce chain, the identity page, the watchdog — is kept unchanged;
the new scorer sits where the 64-vector sweep sits now and emits an observation where the
sweep emits tables.

### 5.2 What the observation must be able to tell apart

For each configuration semantic of the class, at least one preregistered stimulus / readout
pair in the sequence under which the two values of the bit give different observations; the
semantics are the certificate's seven attestation fields (plan §3) read as behaviours:

| semantic (plan §3 field) | behaviour to be distinguishable | observed where |
|---|---|---|
| `ff_init` (`ZINI`) | the value after reset, before any edge | step 1 readout |
| `ff_srval` (`ZRST`) | the value after a synchronous set / reset edge | after an edge with SR asserted |
| `ce_mode` (`CEUSEDMUX`) | whether the enable input gates the capture | an edge with CE de-asserted |
| `sr_mode` (`SRUSEDMUX`) | whether the SR input has any effect | an edge with SR asserted vs not |
| `sr_kind` (`FFSYNC`) | whether SR acts without an edge | SR asserted between edges |
| `storage_kind` (`LATCH`) | transparency while the gate is open | readout between edges |
| `clock_mode` (`CLKINV` / `NOCLKINV`) | which edge captures | data changed between the two edges |

A semantic for which **no** pair in the sequence separates the two values on a given address
is not decoded: the map keeps `state = unknown` for that relation (§6) and the ledger records
that the sequence did not discriminate. Decoding by assumption ("a bit that did nothing must
be the enable mux") is forbidden; the B1 rule "a relation is a claim only when state is
decoded or confirmed; every claim must carry an observed transition"
(`schemas/self_map_v2.schema.json`, description) carries over unchanged.

### 5.3 Raw observation and fitness are two records

The ledger entry of every evaluation carries the raw observation (the sampled outputs per
step, or a digest of them with the full vector retrievable through the audit pull) **and**,
separately, the fitness the board computed from it under the landscape rule (§7). The
adjudicator recomputes the fitness from the raw observation; a mismatch is a finding against
the board, never corrected. This is B3's specimen-ledger discipline
(`docs/b3_architecture.md` §3) with the readout replaced by an observation sequence.

### 5.4 Nobody in the loop

The certificate, the oracle map, the attestation fields and the Z readings are not available
to the scorer, the application, the cartographer or the search at any point of a session
(§2). The B1 guard set is re-aimed at the FF names: no `ZINI` / `ZRST` / `CEUSEDMUX` /
`SRUSEDMUX` / `FFSYNC` / `LATCH` / `CLKINV` / `NOCLKINV` string, no attestation field name, no
per-address expected behaviour reachable from the image; a permuted fixture whose behaviour
mapping is a seeded permutation of the certificate's must make the cartographer output the
permutation, not the truth.

### 5.5 Acceptance conditions for a carrier v2 scorer (to be met before the package freezes)

Stated now so that a later design unit is judged against something written first:

- **A1** the observation of §5.1 is a single transaction per candidate under the instrument's
  existing links, watchdog and stop-loss, with no new host-side computation before the record;
- **A2** every semantic of §5.2 is distinguishable on at least one address of the fabric
  *model* (unit 2b) and, under the ruling that first loads the carrier, on the board for the
  positive-control addresses the preregistration names — before any mapping session;
- **A3** the raw observation validates against a schema that forbids an expected value;
- **A4** the readback contract (links 2–3), the identity page and the `VARIANT` word are
  extended, not replaced, and the application refuses any other carrier;
- **A5** isolation between candidates is demonstrated by a negative test: a candidate whose
  leftover state would change the next observation does not (§5.1 step 5);
- **A6** the bench (iverilog) reproduces every scenario of the B1 carrier's bench that still
  applies and adds one per row of §5.2;
- **A7** the MMIO allowlist of the application matches the RTL's AXI-Lite decode, reported as
  mismatches only (the standing check of this line).

## 6. The map — `self_map` v2 and the contracts the FF class needs

`schemas/self_map_v2.schema.json` (2.0.0) is a LUT map. The constraints that make it so, read
from the schema itself:

| field | v2 constraint | why it does not fit the FF class |
|---|---|---|
| `entries[].relation` | `null` or `{kind: "lut_init", lut_index 0..5, init_index 0..63}` — exactly one `kind` | an FF address's relation is a semantic of §5.2 and a storage element, not a LUT and an INIT index |
| `interaction_edges[].kind` | `same_lut` \| `cross_lut` | the FF interactions of interest are within a slice (an enable or a reset mode shared by eight elements) and between a storage element and the LUT feeding it |
| `code_probe_seqs` | exactly 9 integers | nine code probes are B1's design for 6 LUTs × 64 entries; the FF probe design is 2b's to fix and its count is not nine by construction |
| `universe.safety_class` | `content` \| `routing` | sufficient — the FF class is `content` |
| `confidence`, `state`, `observed_transition`, `evidence`, `anomalies`, `binding` | class-agnostic | kept as they are |

What B4-FF needs, as **new contracts** (names provisional; fixed by unit 2b with the probe
design, so that the schema is written against a probe plan and not before it):

- a relation kind for the class — e.g. `{kind: "ff_config", element: <one of the eight storage
  elements or "slice">, semantic: <one of the seven of §5.2>, value: <the decoded behaviour>}` —
  with `state: unknown` allowed per semantic, not only per address;
- edge kinds for the class — within-slice (shared mode bits), element-to-LUT (the LUT that
  feeds a storage element), and the cross-slice edge kept for anomalies;
- a probe-sequence record whose length is the plan's, with the stimulus sequence's seed and
  the number of edges recorded, not a fixed count;
- the observation record of §5.3 referenced from `evidence` by digest.

**Version strategy.** v2 is frozen by three pin tables and is not modified. The FF contracts
go into a **new schema file** (working name `schemas/self_map_v3.schema.json` or
`self_map_ff_v1`; the name is 2b's), with `schema_version` its own, read by the B4 verifier
and adjudicator only; B1–B3 maps remain valid v2 documents and B1–B3 tools never see v3. A
v3 document is never a superset promise over v2: an FF map does not carry LUT relations, and a
tool that is handed the wrong class refuses by name.

## 7. The landscape and the fitness — the generation rule

The B2 lessons are the rule (`docs/b2_architecture.md` §4, roadmap §2 "B2 — a carrier that
can discriminate"): a fitness with **real interaction** across elements — never a sum of
per-bit contributions; a landscape generated by a **public rule or an isolated seed,
independent of the map operator** — no problem engineered to reward same-slice mutation; an
image with real selection and population; the two arms sharing everything but the operator;
search sees train only, each champion sees the holdout last.

For the FF class the fitness must be a function of the **observation sequence** of §5.1, not
of the configuration bits: a target behaviour (what the eight storage elements should output
over the `K`-edge stimulus) drawn from the landscape seed, and a score comparing the observed
sequence with the target under a rule fixed in the preregistration. Requirements, no numbers:

- the target must be reachable by some configuration of the universe and not by the base
  configuration (non-saturation and non-triviality, the gate's H1 analogue);
- the score must depend on the joint configuration of at least two storage elements or
  modes for a fraction of the landscape seeds the gate reports (real interaction);
- the score must be computable by the board from the raw observation and recomputable by the
  host from the ledger (§5.3);
- the landscape generation rule must not consult the certificate, the map or the operator
  (independence), and the seed derivation follows the line's rule
  (`master = first 4 bytes of sha256(label | instrument commit)`, every archived seed set
  excluded — `docs/b3_architecture.md` §9 H6);
- the holdout (a site instance, §4.3) is never part of the search's fitness.

Whether such a fitness exists with the properties above is **the first thing unit 2b must
show in simulation**; if it does not, B4-FF stops at the gate like round 1′ did
(`docs/claimb_round1prime_package.md` §9), and that is a result.

## 8. Controls

All on the same seeds and rows, the form of B2 §7 / §7a and B3 §9:

| control | what it is | what it shows |
|---|---|---|
| **R** random-safe | the engine with the uniform operator over the universe | the baseline |
| **F** frozen self-map | the engine consulting a map the FF cartographer built and froze | the search benefit of a correct map (B2's claim, re-asked) |
| **O** online self-map | the map updated from every specimen (B3's arm) | whether updating pays on this class |
| **X** scrambled specimens | O with each specimen's behaviour delta permuted before the cartographer (B3 §9's contract, the shadow-cartographer isomorphism check included) | a wrong online map does not profit |
| **D** shuffled map | F with the map's relations permuted across addresses (B2 §5's control) | a wrong frozen map does not profit |
| **Ω** oracle map | F with the certificate-derived map — host simulation only, never on the board (§2) | the upper bound and the headroom (B2 G4) |
| **A0** address-only baseline | what address structure alone predicts (B1's guard) | the map carries more than addresses |
| T / W (optional) | train-membership-only and within-train scramble (B2 §7a) | grouping versus membership, if the preregistration asks |

## 9. The discriminability gate — criteria with their methods; thresholds `<gate>`

The gate is unit 2b's simulation; this section fixes **what is computed and how**, and leaves
each threshold as `<gate>` to be written into this document **before** the gate simulation is
run — the B3 rule applies verbatim: "if any threshold is changed after the first gate run, the
change is recorded as a revision of this document with the reason, and the gate is re-run and
re-reported under the new commit — never silently" (`docs/b3_architecture.md` §9). **A
threshold is never derived from the run it judges.**

| id | criterion | method (fixed) | threshold |
|---|---|---|---|
| K1 non-saturation | arm Ω's 95th percentile of best-so-far at `B*` below the ceiling; arm R's median at `B*` above the base | B2 G1's computation | `<gate>` |
| K2 not a definitional lock | var(Δ_r) > 0 at `B*`; positives and negatives of Δ both present at one grid budget | B3 H2's computation, one budget | `<gate>` |
| K3 wrong maps do not profit | D's and X's mean Δ against R as a fraction of F's / O's; their sign tests not significant over S | B2 G3 / B3 H3 | `<gate>` |
| K4 oracle headroom | Ω's median at `B*` below the ceiling by a margin; F's mean Δ as a fraction of Ω's | B2 G4 | `<gate>` |
| K5 effect, power, N | Cohen's d of {Δ_r}; `N(B)` by `b2_gate.required_pairs`'s ascending scan (1 000 bootstrap experiments, seed `1 + N`), the sign test by `b2_gate.sign_test_p` — both **by copy into the B4 namespace with their digests recorded**, never by import across the pinned boundary; the session cost `N × arms × B*` under a stated cap | B2 G5 / B3 H5 | `<gate>` |
| K6 no fixed-seed lock | S ≥ `<gate>`; N ≥ `<gate>`; board seeds under a B4 label with every archived set excluded | B2 G6 / B3 H6 | `<gate>` |
| K7 the map is a map | over S: wrong decodes and anomalies in the ideal model; the median decoded count at `B*`; `unknown` count reported, never forced to zero | B3 H7, extended by the `unknown` rule of §5.2 | `<gate>` |
| K8 ledger replay | every map version and decode reproduced from the ledger; the raw observation reproduces the fitness | B3 H8 + §5.3 | holds |
| K9 observability | every semantic of §5.2 distinguishable on every address of the model under the preregistered stimulus sequence; the fraction of addresses per semantic reported | new; §5.2 | `<gate>` |
| K10 real interaction | the fraction of landscape seeds on which the score depends jointly on ≥ 2 elements or modes | new; §7 | `<gate>` |

The primary statistic and the budget rule are B3's in form (Δ paired by landscape at `B*`,
the one-sided exact sign test, `B*` = the grid budget with the smallest session cost among
budgets at which K1 holds and `N(B)` exists); the secondary outcome and the diagnostic rows
are the preregistration's to add. A row that fails is reported, not tuned.

## 10. Provenance, paths and proofs — rules B4 adopts from the repair of 2026-10-15/16

Three lessons of the pinned-test repair — recorded on the branch `b3-pinned-test-repair` (tip
`4db22e5`, engineering PASS 2026-10-16, **not merged into `main`**, so its files
`docs/b3_lifecycle2_pinned_test_audit_delta_2026_10_15.md`, `evidence/b3/repair_2026_10_15/README.md`
and `evidence/b3/repair_2026_10_16_canonical/README.md` are not on this branch) — become B4
rules before any B4 tool is written:

1. **Repository-internal provenance is recorded by repository-relative path.** A B4 build
   evidence, import table, pin table or ledger names a file as `b4/…`, `evidence/b4/…`, never
   as `/home/test/…`. **External tools and trees** (the instrument's toolchain and checkout,
   embeddedsw, Vivado) are named by an explicit root **plus** the digest of what is used, so
   that a verifier re-resolves the root and holds the digest.
   *Compatibility limitation, stated as such:* the frozen B1 and B2 build evidence
   (`evidence/b1/build_evidence.json`, 19 absolute paths; `evidence/b2/build_evidence.json`,
   160, pinned by the B2 manifest's image block) record absolute paths under the canonical
   checkout `/home/test/zynq_fabricmap`; the whole-tree clean-tree proof therefore runs **at
   the canonical path** as long as those frozen inputs are part of it. This is a property of
   existing, frozen proofs that B4 inherits, not a rule B4's own tools may rely on.
2. **A pinned, generated artefact binds only content that no legal lifecycle transition
   changes** (the S3 defect: a header carrying the plan file's digest). B4's generators state
   what they bind and a test renders the artefact under every stage's inputs.
3. **R7**: every `mock.patch(...).start()` in a B4 test is stopped within the same test,
   fixture close or module; `atexit` is not a stop; the §9 audit of B4's tests inventories
   every start and reads each for its cleanup and exception paths.

And the inherited disciplines: a pin table generated once per lifecycle over `b4/**`; a
manifest S0 → S3 with the clean-tree proof at each node (`docs/b3_preregistration.md` §8);
stage-aware tests (§9); an import table for every copied module; the B2 / B3 gate functions
copied with digests, not imported.

## 11. Boards and the provisioning plan (roadmap §4; nothing here is authorised)

| board | role (`docs/board_roles.md`) | B4 use | state 2026-10-16 |
|---|---|---|---|
| `17A6` | verification | B4-FF: the carrier v2 qualification, the FF mapping session, the A/B — under the P3 discipline and the content-class interlock | the only board with the full acceptance and the TF / U-Boot control plane; not to be powered for B4 before a ruling |
| `F8B3` | spare → carrier / cartographer bring-up | carrier v2 bring-up before it touches `17A6` | not provisioned (no `boardid` / `role` environment) |
| `08EB` | sacrificial candidate | B4-R only, after R1–R4 of §3 | accepted 2026-08-01, retested 2026-08-25 (6 / 6, known-answer); no boot medium, no environment, not labelled |
| `3671` | cold spare | none | untouched |
| K7 pair | on hold | none | off the desk with the 12 V supply (`docs/board_roles.md`) |

The provisioning unit (2d) would, each step under its own authorisation: write the control
plane and `role` on `F8B3` and `08EB`; label `08EB`; **measure** the current-limited supply's
behaviour (roadmap §5 item 4's list) and record it in the B4-R package; re-run the acceptance
regression on each board touched. None of it is implied by this document; the current-limited
supply in particular is, as of this draft, **a design intention with no measurement
evidence** and is listed as a prerequisite, not described as a protection.

## 12. What this document does not claim, and what it does not authorise

- Nothing about silicon: no FF behaviour, no timing, no power, no die has been observed for
  this class (§4.2).
- Nothing about routing beyond §3's prerequisites and prohibitions; no routing design, no
  contention model assessment, no board-loss estimate (roadmap §5: "none of those is
  evidenced for this hardware").
- Nothing numerical about the gate (§9, every threshold `<gate>`), the universe size per
  session, the stimulus length `K`, the budget, N or the effect size.
- No schema change (§6 proposes; v2 is untouched), no code, no RTL, no image.
- No authorisation: units 2b (gate simulation), 2c (preregistration) and 2d (provisioning)
  are each separately authorised; no board contact, no port, no purchase.
- The B1–B3 verdicts, the lifecycle-2 S2 / S3 proof exceptions and the repair unit's
  acceptance are unchanged by this document.

## 13. The units ahead (each separately authorised; none begun)

| unit | deliverable | gate |
|---|---|---|
| 2b | `b4/host/b4_sim.py`, `b4/tests/`, the FF fabric model from the certificate, the stimulus-sequence design, the K1–K10 thresholds written into §9 **before** the run, `docs/b4_gate_report.md`, the v3 map schema draft | the thresholds committed before measurement; the report states every row PASS / FAIL |
| 2c | `docs/b4_preregistration.md` DRAFT (B4-FF: claim, pins, prediction, metrics, falsifiers, sessions and rulings, compatibility, lifecycle, §9 rule; B4-R: prerequisites and prohibitions only) | the owner's review; the holdout and the universe fixed by whole site instance |
| carrier v2 design | RTL, bench, XDC, isolation — against §5.5 A1–A7 | a separate unit after 2c |
| 2d | provisioning and the supply measurements (§11) | board work; the owner's rulings per step |

## 14. Files and references

`docs/autonomous_cartography_roadmap.md` (§1–§7) · `docs/board_roles.md` ·
`docs/ff_preregistration_plan.md` (§1–§5, §7) · `gate_runs/run_2026_08_05_ff/certificate.json` ·
`data/MANIFEST.json` · `schemas/self_map_v2.schema.json` · `docs/b1_carrier_contract.md` ·
`docs/b1_architecture.md` §5 · `docs/b2_architecture.md` §4, §5, §7, §7a, §8 ·
`docs/b3_architecture.md` §3, §5, §9, §10 · `docs/b3_preregistration.md` §8, §9 ·
`docs/b3_result_2026_10_15.md` · `docs/claimb_round1prime_package.md` §9 · `docs/mux_groups.md` ·
on the branch `b3-pinned-test-repair` at `4db22e5` (not merged): `docs/b3_lifecycle2_pinned_test_audit_delta_2026_10_15.md`,
`evidence/b3/repair_2026_10_15/README.md`, `evidence/b3/repair_2026_10_16_canonical/README.md` · `b3/firmware/IMPORT.json` ·
`/home/test/test_devices/result.txt` (the 2026-08-25 `08EB` retest).

# B4 — expansion from LUT content bits to the FF class, then routing: architecture (DRAFT v0.1.12, host-only, 2026-10-16; revised 2026-10-18)

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
>
> **Revision v0.1.1 (2026-10-16, the owner's HOLD on `cec6aac`, documents only):** P1 — INIT and
> the set / reset value separated into two restore mechanisms with their own observation points,
> which mechanism restores which state a condition the carrier must prove (§5.1, §5.2, A8); P1 — the
> observability quantifier corrected: a positive control per semantic, discriminability judged per
> address and per applicable context, uncovered and `unknown` reported (K9, A2); P1 — the primary
> Δ named (O − R, search accounting), the H2 control bootstrap non-rejection restored, and an
> operable interaction criterion (the four-corner index) written (§9); P2 — `observed_transition`
> (and `evidence`) are not class-agnostic in v2 (§6); P2 — the certificate's mapping separated from
> the hypothesised behaviour model (§4.4, §13).
>
> **Revision v0.1.2 (2026-10-17, the owner's engineering PASS on `24b2e21` with four corrections, documents
> only):** §2 cites §5.2 for `unknown`; §13 cites A1–A8; K5 names `{Δ1_r}`; K10 — a seed with no
> comparable pair is *not assessable*, kept in the denominator of all S and counted, never judged
> additive; a seed whose comparable pairs all give `I = 0` is "no interaction seen among the tested
> comparisons", not "every context additive". The PASS covers the architecture document, not any gate
> result or hardware observation.
>
> **Revision v0.1.3 (2026-10-17, unit 2b-1, the owner's three contract corrections):** the sources of the
> behaviour hypothesis are the vendor's UNISIM models, recorded by root, path and digest, kept apart from the
> certificate mapping and from the project's own decode assumptions (§4.4); `valid_configuration`,
> `applicable_semantics` and `observation_context` are three different things (§5.0); the context is
> complete enough to replay a readout (§5.1); K10's four-corner comparisons fix everything but (a, b) (§9);
> a seed anchor fixed once with every exploration seed and failure retained — determinism from HEAD is not
> a protection against selection (§9). Unit 2b-1 delivered `b4/host/b4_ff_mapping.py`,
> `b4/host/b4_ff_hypothesis.py`, `b4/hypothesis/ff_behaviour_v0.1.json`, `b4/host/b4_ff_model.py` and
> their tests (§13).
>
> **Revision v0.1.4 (2026-10-17, the owner's HOLD on `2bad829`, six probes):** the clock-mode reading is
> decoded by storage context — under a latch the CLKINV bit is asserted with `IS_G_INVERTED = 0`
> (`docs/ff_latch_probe.md`), so there bit 1 means not inverted and bit 0 has no attested reading (outside
> the model's domain, §5.0); an observation is the executing side's view only, the decode and everything
> derived from it a host-only diagnostic (§5.3); the loaders verify by default and fixtures enter only through
> a marked boundary (§10); readings are validated enums, an unrecognised one refused (§4.4); the mapping
> loader cross-checks ranges, endpoints and polarity; `observe` validates what it is handed and the init
> step's context (§5.1). Hypothesis file `ff_behaviour_v0.2.json`.
>
> **Revision v0.1.5 (2026-10-17, the owner's HOLD on `b91162c`, three probes):** a domain refusal reaches the
> executing side as a fixed code with no reason, and is never a specimen, a redraw condition or a map-update
> signal (§5.3); the formal hypothesis is the committed file only, read without a path against a pinned digest —
> every other document, a valid copy included, is a marked fixture (§10); a token's reading direction is the
> class's, not the row's, and the two readings of a shared bit must be complementary (§4.4); `unknown` is a
> reading in the latch context of the clock mode only, held by the shape check.
>
> **Revision v0.1.6 (2026-10-18, unit 2b-2 — the owner's five rulings on the revised scope):** the 21 addresses
> and the formal hypothesis kept, no reading added, no universe narrowed, no candidate filtered by diagnostics; a
> DOMAIN refusal terminates the run — the measured prefix and the terminal state are kept, nothing is added to a
> curve, no seed is dropped, an incomplete pair never yields a primary PASS (§5.3, §9); the task is PUBLIC —
> stimulus, mask M, target t and weights w from the landscape seed alone, the base all-zero by declared choice,
> None scoring nothing and moving no ceiling (§7); reachability, a non-optimal base and interaction are separate
> host audits, never satisfied by choosing seeds. Unit 2b-2 delivered the execution boundary, the task generator,
> the engine, the observation cartographer, the replay and the four-corner computation with their tests (§13).
>
> **Revision v0.1.7 (2026-10-18, the owner's HOLD on `2eae943`):** the replay is a RE-EXECUTION from the declared
> inputs and the recorded observations, with its authenticity limit stated (§5.3); the observation source's identity
> (the hypothesis's digest and fixture marker, the certificate's digest) and a given view's provenance chain are bound
> into every result and ledger entry and checked — a shuffled oracle stays oracle-derived (§10); a DOMAIN at the
> holdout keeps the search's champion without a holdout score and the run incomplete (§5.3); the implemented control X
> is a SYMMETRY control, not yet the negative control K2 / K3 name — a design note is before the owner (§8); the design
> is not gate-ready: the frozen arm cannot complete its probe pass under the formal hypothesis, and 2b-3 does not
> follow until that is ruled on.
>
> **Revision v0.1.8 (2026-10-18, the owner's HOLD on `8d2757a`):** the observation source's identity includes the
> FABRIC (kind, effect digest, dropout digest and count, seed — digests only), is validated field by field on every
> observation and in the replay, and a malformed or drifting identity is a `SourceRefusal` by its own name (§10);
> non-DOMAIN refusals are recorded under a finite set of kinds and replayed by kind (§5.3); the replay's validation is
> total and type-exact and a malformed record is a named finding, never an exception or a pass (§5.3); the X-A design
> note is corrected — a derangement of addresses does not guarantee a changed partition, π is fixed blind and never
> redrawn, residual structure is reported post hoc, the lane permutation is a symmetry check of the relation /
> partition structure, no trajectory-equality claim (§8). Still not gate-ready; nothing implemented for X-A.
>
> **Revision v0.1.9 (2026-10-18, the owner's ruling on the F / domain / X-A scope draft):** D1′ chosen — a host-only
> probe of the latch gate inversion on the mine site (`b4/probes/latch_ginv/`, §13), executed and archived under
> `evidence/b4/unit_d1prime_latch_ginv_2026_10_18/`: every bitstream clause held (LATCH kept, CLKINV 1 → 0 the only
> same-class mover), the driver's own route-status rule produced the only findings (`INTRASITE`), the unit stopped
> for review under the stop rule. The domain, the hypothesis, `HYPOTHESIS_SHA256` and the F fact are UNCHANGED here;
> a model revision (v0.3) is a separate unit, not authorised. X-A authorised as a later independent unit (§8 revised
> there, not here). The arithmetic of the scope draft corrected by the owner: 3/28 is one random-safe draw's
> combinatorial fraction from the all-zero parent and (25/28)^8 needs eight independent such draws — a model
> quantity for R's first generation, not a frequency of any arm's runs and not transferable to O / X.
>
> **Revision v0.1.10 (2026-10-18, the owner's follow-up ruling on attempt 1):** the probe's cell rule accepts
> `ROUTED` and `INTRASITE` as complete route statuses (UG912); attempt 2 under the new recipe digest, in its own
> directories (`evidence/b4/unit_d1prime_latch_ginv_attempt2_2026_10_18/`), met every clause with no finding;
> attempt 1 kept as it was. Awaiting the owner's review; nothing of the model changed; X-A opens after that review.
>
> **Revision v0.1.11 (2026-10-18, the X-A unit, authorised by the ruling of 2026-10-18 §4 after D1′'s PASS on
> `e0b5f04`):** control X is now X-A — the addresses relabelled through a derangement π drawn once from its own
> control generator before the base observation, the full shadow contract after every ingest, a control failure as
> its own event with a stated commit point, the residual structure reported post hoc with the non-guarantee written
> in (§8); K2 / K3 carry the residual-structure counts beside X's numbers, no threshold or τ filled (§9); the lane
> permutation kept as the cartographer's symmetry test, no fifth arm. The model, the hypothesis, the domain and the F
> fact unchanged; still not gate-ready.
>
> **Revision v0.1.12 (2026-10-18, the v0.3 model revision, authorised by the owner's ruling on the v0.3 scope draft after
> D1′'s PASS on `e0b5f04` and X-A's PASS on `c0689f8`):** the hypothesis file is `b4/hypothesis/ff_behaviour_v0.3.json`
> (0.3.0): the latch's clock-mode bit 0 reads *inverted* on the D1′ host correspondence pair, with three layers kept apart in
> the file — L1 the host endpoint correspondence (the probe report pinned by digest as a source), L2 the vendor's primitive
> behaviour (the UNISIM lines already adopted), L3 the project's generalisation assumptions G1–G6, each its own item; status
> unverified. Every assignment of the 21 bits is in the domain **by an added assumption, not by any observation** (§4.4, §5.0);
> the DOMAIN refusal, the `unknown` enum and the executing-side contract unchanged; the initialisation event's atomic,
> unsettled assignment named as a model abstraction (A8 unresolved). The v0.2 file is kept byte for byte and its result —
> F's probe pass terminating at the LATCH flip — is kept as a test on the marked `v021_hole` fixture built from it; under
> 0.3.0 the pass completes (§5.3). The behaviour state machine, the engine, the cartographer and the replay are not changed.
> `b4/IMPORT.json` refreshed (its stale `v0.1.json` references corrected) and this document's title version synchronised.
> v0.3 fills a hole the model itself defined; **it does not make the design gate-ready** (2b-3, §13).

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
   observation cannot resolve stays `unknown` (§5.2) instead of being decoded by assumption.

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
(the model of §4.4 — the certificate mapping plus the behaviour hypothesis — and the oracle-map control) and by the post-session adjudicator (scoring the
frozen, hashed map; the B1 primary metrics — precision, recall, polarity errors, sample
efficiency, confidence calibration, cold-boot replay, map-hash consistency — apply per address,
with "polarity" now meaning the Z reading of §4.1). The certificate's **22 / 154 mine /
holdout split** (plan §7, ruling 1: `mine = {SLICE_X2Y25}`) is the certificate's own
engineering holdout against *its* tuning; it is **not** B4's holdout. B4-FF's holdout — by
whole site instance, not consulted while the FF cartographer is developed — is fixed by the
preregistration (unit 2c), and the preregistration says in one sentence why it is an
engineering holdout and not a claim that the truth was unseen.

### 4.4 The model: what the certificate supplies, and what is a hypothesis

Every "model" in this document and in unit 2b is two things that must stay apart in every
file, report and sentence:

| | the **certificate mapping** | the **behaviour hypothesis** |
|---|---|---|
| what it is | per address: the feature name, the Z polarity reading, the site, the element (§4.1); per specimen: which design variant moved which bit — **each token's reading direction is the class's** (every token direct — the bit set in its feature endpoint — but `NOCLKINV`, the negated, complementary reading of `CLKINV`'s bit), so a row that re-labels a direction, however self-consistent, is refused. **The clock-mode reading is per storage context**: the clkinv pair attests bit 1 = inverted for a flip-flop; the latch probe attests the LDCE endpoint with the CLKINV bit set and `IS_G_INVERTED = 0`, so under a latch bit 1 = *not* inverted (`docs/ff_latch_probe.md`, "The finding worth keeping"); **since v0.3** bit 0 under a latch = *inverted* — the gate is the slice clock inverted — on the D1′ pair of `evidence/b4/unit_d1prime_latch_ginv_attempt2_2026_10_18/` (`IS_G_INVERTED` 0 → 1 clears CLKINV, LATCH kept, no other same-class mover): a **host correspondence** source of the same kind as the bit-1 endpoint, not a certificate and not silicon | per storage element and per configuration value: the state machine the element is *assumed* to follow — the value after an initialisation event, the value after a user SR operation, whether CE gates capture, whether SR acts without an edge, transparency, the capturing edge |
| source | `gate_runs/run_2026_08_05_ff/certificate.json`, the plan's attestation fields (plan §3) | **three kinds, listed per entry in `b4/hypothesis/ff_behaviour_v0.2.json` `sources`**: (1) the vendor's UNISIM simulation models — `FDRE.v`, `FDSE.v`, `FDCE.v`, `FDPE.v`, `LDCE.v`, `LDPE.v` under the root `/home/test/Xilinx/2025.2/data/verilog/src/unisims` — each by path, sha256 and the lines adopted (the GSR initialisation, the edge and level rules, the latch UDP table); (2) the certificate mapping, by path and sha256; (3) the project's own decode assumptions (the Z readings, the primitive-selection table, the pin correspondence, the initialisation event modelled as GSR). Nothing of (1)–(3) is a measurement of this line |
| status | host-attested (§4.2) | **unverified on silicon**; a modelling assumption until the carrier-v2 unit demonstrates each row on the board under its own ruling |
| what 2b's simulation can say | that the cartographer recovers the mapping *given* the hypothesis | nothing — a simulation under the hypothesis cannot confirm the hypothesis |

A gate report that says "the model" without saying which of the two is meant, or that reads a
PASS under the hypothesis as evidence that the fabric behaves so, is wrong by construction.

The hypothesis file's readings are **machine enums**, validated by its loader against a closed list per
semantic; an unrecognised reading is refused by name at load and at decode and is never read as a default.
An `unknown` reading puts a configuration **outside the model's domain** (§5.0), and the model refuses to observe it
rather than simulate it with a default; v0.2 had one (clock mode, bit 0, under a latch), v0.3 has none.

**The v0.3 latch reading, in three layers that the hypothesis file keeps in separate source entries** (the owner's ruling
of 2026-10-18): **L1** the host endpoint correspondence — the D1′ probe report, pinned by digest, says only that on one
recipe, one site and one tool version a resolved `IS_G_INVERTED` property corresponds to one bitstream bit; **L2** the
vendor's primitive behaviour — `LDCE.v`'s `G_in = G xor IS_G_INVERTED` and its UDP table, a simulation model, not a
measurement; **L3** the project's generalisation assumptions, each named — G1 the other 19 bits do not change the reading,
G2 the property is realised as the slice-level clock inversion on silicon, G3 the vendor's model describes the silicon gate,
G4 the correspondence is tool- and recipe-invariant, G5 four main elements speak for the per-slice bit, G6 the init readout
under an open gate rests on the model's atomic, unsettled init step (A8 unresolved). The reading is L1 ∧ L2 ∧ L3; its status
is unverified, like every row of the hypothesis, and the model's domain is complete **because of L3**, not because anything
was observed.

## 5. The observation contract for FF semantics — functional requirements, not RTL

What the line can observe today is combinational: the B1 carrier's arm gate "sweeps all 64
vectors and exposes the readout raw" (`docs/b1_carrier_contract.md` §2) — a truth table per
LUT. An FF configuration bit has no truth table; its effect appears only across clock edges,
resets and time. A **carrier v2 scorer** is therefore required, and this section states what
it must do and how it will be accepted — the design (RTL, timing, placement) belongs to a
later, separately authorised unit and is not sketched here.

### 5.0 Three contracts that are not one: `valid_configuration`, `applicable_semantics`, `observation_context`

The hypothesis file carries them as three separate blocks, and the model and every later tool keep them
apart:

| contract | what it answers | status of what it says |
|---|---|---|
| `valid_configuration` | which assignments of the 21 bits the **model accepts as its domain**: those whose every decoded reading is known — v0.2 excluded a latch with the CLKINV bit clear (19 free bits, 2^19 assignments), which nothing attested; v0.3 reads that bit on the D1′ pair under the assumptions G1–G6 (§4.4), so every assignment is in its domain | a domain definition — never a statement that a configuration is legal to build, safe to write, or has been observed; v0.3's completeness rests on an added assumption |
| `applicable_semantics` | which relations **exist** for an address under a configuration (under a latch the x5FF elements are not storage elements, so their `ff_init` / `ff_srval` are *not applicable* — distinct from `unknown`; a latch has no `sr_kind`) | a model assumption drawn from `docs/ff_latch_probe.md`; a changed context is not an illegal configuration |
| `observation_context` | what every readout must carry so that it can be replayed from the trace alone (§5.1) | a recording requirement |

The legal-composition question of §4.2 (which configurations may be written to silicon) is none of these
three; it is a later, separately stated rule of the preregistration (unit 2c), and no "accepted by the model"
is ever read as "legal".

### 5.1 One observation, as a sequence the board can replay

For every candidate the board must be able to perform, and the ledger to record, the
following in order, with nothing of it computed on the host before the measurement:

1. **Configuration** — the candidate written (link 1 as today: the host signs writability
   only) and the fabric readback hashing to the commit (link 3).
2. **Initialisation event, and the init observation** — an event under a stated discipline
   (which event, asserted how long, released when) after which the storage elements are read
   **before any clock edge and with the user SR input de-asserted**: the *init readout* (the model refuses an init step in any other context). Two
   restore mechanisms exist on the primitives and **this document does not say which restores
   what**: (i) an *initialisation event* — the configuration load itself, or an explicit global
   set / reset event the carrier can raise — hypothesised to bring each element to its `INIT`
   value; (ii) a *user SR operation* — the element's own set / reset input, applied at or
   between edges — hypothesised to bring it to its `SRVAL`. Which mechanism restores which
   state, on this die, is **a condition the carrier-v2 unit must demonstrate** (A8), with
   positive controls per mechanism, before either observation is read as a semantic. Until
   it is demonstrated, and on any carrier where an initialisation observation cannot be
   established at all, every `ff_init` relation stays `unknown` (§5.2).
3. **Stimulus sequence, with the SR observations inside it** — a preregistered, seed-derivable
   sequence of `(clock-enable, user set / reset, data)` vectors applied over `K` clock edges
   to every storage element of the site, with the clock under the scorer's control; the user
   SR operations of (ii) are steps of this sequence, each followed by its own readout point
   (the *SR readout*), so that the value an SR operation restores is observed separately from
   the value the initialisation event left. The sequence must give an inverted clock, an
   enable that is or is not driven, a synchronous versus asynchronous SR and a latch's
   transparency each a **distinguishable** observation at least once — the sequence's
   discriminating power is a 2b result under the behaviour hypothesis (§4.4), not an assumption.
4. **Readout** — the storage elements' outputs sampled at stated points (the init readout,
   after each edge, after each SR operation, and between edges for transparency), exposed
   **raw**: no comparison with an expected value anywhere in the PL or the application before
   the record is written; every readout carries which event or step preceded it.
5. **Restore** — the candidate undone and the base configuration re-established and read back
   (link 3 again), **and an initialisation event raised once more** (the same mechanism as
   step 2, recorded as such), before the next candidate.
6. **Isolation between candidates** — the record of candidate *n+1* must not depend on the
   state candidate *n* left behind: the initialisation event of step 2 is part of every
   candidate, the stimulus sequence restarts from its seed, and the scorer's own state machine
   is returned to idle; an audit recomputes the fitness from the raw observation alone (§5.3).

Everything the instrument's links already give — the signed ARM, the staging re-read, the
twelve-frame readback, the nonce chain, the identity page, the watchdog — is kept unchanged;
the new scorer sits where the 64-vector sweep sits now and emits an observation where the
sweep emits tables.

**The context, completely.** A readout that cannot be replayed is not an observation. Every readout record
carries: the step index and kind (initialisation event or input / clock step); the previous event
(`none` / `init` / `edge` / `level`); the slice clock before and after and the edge it made; **per element,
the edge in its physical clock** (the slice clock through the decoded inversion); the `ce`, `sr` and `d`
vectors applied; **Q before and Q after** per element; and the applicability of each element. The trace
header carries the configuration (and its digest), the initial state (clock low, inputs low, Q never
initialised), the stimulus sequence, the mapping's certificate digest and the hypothesis's digest and
version. The model's trace of unit 2b-1 is this record (`b4/host/b4_ff_model.py`).

### 5.2 What the observation must be able to tell apart

The semantics are the certificate's seven attestation fields (plan §3) read as behaviours. The
requirement has two levels, and the quantifiers matter: **for each semantic, at least one
positive control** — an address which, under the certificate mapping and the behaviour
hypothesis (§4.4), carries that semantic, and a preregistered stimulus / readout pair in the
sequence under which the two values of that bit give different observations; and **for each
address, for each semantic applicable to it** (an address is one bit and carries one semantic;
a `ZINI` address is never asked to show a clock-mode effect), whether the sequence separates
the two values — judged per address and per applicable context, with the addresses it does
not cover reported as uncovered and their relations left `unknown`. K9 and A2 use exactly
this wording.

| semantic (plan §3 field) | behaviour to be distinguishable | observed where |
|---|---|---|
| `ff_init` (`ZINI`) | the value after the initialisation event, before any edge, SR de-asserted — **only once A8 has shown which event restores INIT** | the init readout (§5.1 step 2) |
| `ff_srval` (`ZRST`) | the value after a user SR operation | the SR readout (§5.1 step 3) |
| `ce_mode` (`CEUSEDMUX`) | whether the enable input gates the capture | an edge with CE de-asserted |
| `sr_mode` (`SRUSEDMUX`) | whether the SR input has any effect | an edge with SR asserted vs not |
| `sr_kind` (`FFSYNC`) | whether SR acts without an edge | SR asserted between edges |
| `storage_kind` (`LATCH`) | transparency while the gate is open | readout between edges |
| `clock_mode` (`CLKINV` / `NOCLKINV`) | which edge captures | data changed between the two edges |

A semantic for which **no** pair in the sequence separates the two values on a given address
is not decoded: the map keeps `state = unknown` for that relation (§6) and the ledger records
that the sequence did not discriminate. `ff_init` in particular stays `unknown` on every
address while the restore mechanisms are undemonstrated (A8), however clean the init readout
looks: an init readout that merely *agrees* with the hypothesis is not a demonstration. Decoding by assumption ("a bit that did nothing must
be the enable mux") is forbidden; the B1 rule "a relation is a claim only when state is
decoded or confirmed; every claim must carry an observed transition"
(`schemas/self_map_v2.schema.json`, description) carries over unchanged.

### 5.3 Raw observation and fitness are two records; the decode is a third thing, host-only

The ledger entry of every evaluation carries the raw observation (the sampled outputs per
step, or a digest of them with the full vector retrievable through the audit pull) **and**,
separately, the fitness the board computed from it under the landscape rule (§7). The
adjudicator recomputes the fitness from the raw observation; a mismatch is a finding against
the board, never corrected. This is B3's specimen-ledger discipline
(`docs/b3_architecture.md` §3) with the readout replaced by an observation sequence.

**What the executing side sees, and what it never sees.** An observation (the model's `observe`,
the carrier's record) carries only what the executing side applied and read: the configuration
it wrote, the stimulus, and per step the context of §5.1 and the Q values. Everything derived
from the decode — the primitive, INIT, SRVAL, the CE / SR modes, the kind, the inversion, the
applicability of an element, the edge in an element's *physical* clock — is a **host-only
diagnostic** (the model's `diagnose` / `step_diagnostics`), classified item by item in the
hypothesis file's `observation_context`, produced for audits and simulation reports, and never
an input to a decision in a session (§2). A Q of `null` in an observation says only that no
readout exists for that element in that configuration or that it was never initialised — it is
not labelled with the reason. A cartographer that could obtain the decode without measuring
would not be mapping; the split is what makes 2b-2's cartographer honest by construction.

**A refusal is not an observation either.** A configuration outside the model's domain is refused
with a **fixed code** (`DOMAIN`) that carries no reading, no semantic and no reason; the reason is
host-only (`diagnose`). Such a refusal is never a specimen, never a redraw condition of the search
and never a map-update signal — 2b-2's cartographer and engine inherit this rule (the hypothesis
file's `domain_refusal` block).

**What a DOMAIN does to a run (the owner's ruling 2 of 2026-10-18; `b4/host/b4_engine.py`).** Every
observation of a run — the base, each mapping probe, each search candidate, the holdout — passes the
one boundary. The first DOMAIN terminates the run: the event is recorded as it came (the phase, the
attempt ordinal, the candidate's and the stimulus's digests, the seeds, the budget, the successful
observations, the generator's state, the population's and the map's commitments as they stood before
the call), kept apart from the specimen ledger; the candidate has no fitness, no specimen and no place
in the population; the generation's successful children stay pending — no selection pretends the
generation closed; nothing is generated, observed, scored, selected or learned afterwards; the
generator is not rolled back. The best-so-far trace is the **measured prefix**: the unexecuted budget
points are missing, never filled with zero or with the last value; an incomplete run never enters a
pair as if complete, and a seed is never dropped and replaced. Any other refusal is recorded by its own
name, never as DOMAIN. **The F fact, under each hypothesis revision.** Under 0.2.1, from the all-zero base
(CLKINV clear, in the domain) the single flip of the LATCH address was outside the domain, so a mapping
probe pass that covers every address terminated there, in whatever order — the frozen arm's own probe
pass could not complete; that result is kept as a test on the marked `v021_hole` fixture built from the
kept v0.2 file. Under 0.3.0 every assignment is in the domain, so the pass completes — base + 21 probes,
a complete F run B + 23 observations with its B search evaluations and one holdout (`test_b4_engine`) —
**because a reading was added (§4.4, L1 ∧ L2 ∧ L3), not because anything was observed**. v0.3 fills a
hole the model itself defined; **it does not make the design gate-ready**: the thresholds, τ and the seed
anchor are 2b-3's, to be written and reviewed before any landscape exploration, and no number is set here.

**The holdout.** The champion is fixed when the search loop completes; the holdout observation passes
the same boundary; a DOMAIN there terminates the run with phase `holdout` — the champion is kept as the
search's result, the holdout score stays absent, the run is not complete.

**Replay is re-execution, and what it proves.** A run's record is replayed by running the engine again
from the declared inputs (arm, task, operator seed, budget, a given view, X's permutation) against a port
that hands back the recorded observations in order and raises the recorded refusal at its attempt,
holding every call to the record; the whole result must reconstruct field by field. This proves the
INTERNAL EXECUTION SEQUENCE — nothing decided, drawn, selected or learned beyond the declared inputs and
the recorded observations. It does not prove that an observation or a DOMAIN came from the model or
from hardware: the observation source's identity is bound and checked for consistency, not re-derived
(`b4/host/b4_replay.py`). Its validation is total and type-exact — every field, every entry, every q grid
against the phase's public stimulus, the terminal event, the refusal (one of the finite kinds `ValueError`,
`ModelRefusal`, `SourceRefusal`, re-raised by kind at its attempt), the given view, the source identity —
before anything is hashed, indexed or reconstructed; a malformed record is a named finding and an internal
error is reported as such, distinct from a refusal. A source that told a consistent lie passes: the limit stands.

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
- **A2** the §5.2 quantifiers hold: for each semantic a positive-control address under the
  model of §4.4 (unit 2b) and, under the ruling that first loads the carrier, on the board for
  the positive-control addresses the preregistration names — before any mapping session;
  per address and per applicable context the discriminability is reported, the uncovered
  addresses named and left `unknown`;
- **A3** the raw observation validates against a schema that forbids an expected value;
- **A4** the readback contract (links 2–3), the identity page and the `VARIANT` word are
  extended, not replaced, and the application refuses any other carrier;
- **A5** isolation between candidates is demonstrated by a negative test: a candidate whose
  leftover state would change the next observation does not (§5.1 step 5);
- **A6** the bench (iverilog) reproduces every scenario of the B1 carrier's bench that still
  applies and adds one per row of §5.2;
- **A7** the MMIO allowlist of the application matches the RTL's AXI-Lite decode, reported as
  mismatches only (the standing check of this line);
- **A8** the two restore mechanisms of §5.1 step 2 are demonstrated on the board, each with a
  positive control: which event restores an element to its `INIT` value and which operation
  restores it to its `SRVAL`, under which conditions (SR de-asserted, no edge pending); an
  element for which neither is demonstrated keeps `ff_init` / `ff_srval` `unknown`, and a
  carrier on which no initialisation observation can be established is accepted only with
  `ff_init` excluded from the semantics it claims to observe.

## 6. The map — `self_map` v2 and the contracts the FF class needs

`schemas/self_map_v2.schema.json` (2.0.0) is a LUT map. The constraints that make it so, read
from the schema itself:

| field | v2 constraint | why it does not fit the FF class |
|---|---|---|
| `entries[].relation` | `null` or `{kind: "lut_init", lut_index 0..5, init_index 0..63}` — exactly one `kind` | an FF address's relation is a semantic of §5.2 and a storage element, not a LUT and an INIT index |
| `interaction_edges[].kind` | `same_lut` \| `cross_lut` | the FF interactions of interest are within a slice (an enable or a reset mode shared by eight elements) and between a storage element and the LUT feeding it |
| `code_probe_seqs` | exactly 9 integers | nine code probes are B1's design for 6 LUTs × 64 entries; the FF probe design is 2b's to fix and its count is not nine by construction |
| `universe.safety_class` | `content` \| `routing` | sufficient — the FF class is `content` |
| `entries[].observed_transition` | `null` or exactly `{base: 0, set: 1}` (both `const`): "what the board actually saw at the claimed position: 0 in the base, 1 with the address set" | a single lit position under a single-address probe is B1's observation; an FF observation is a *trace* — the stimulus applied, the initialisation / SR context it was taken in, the outputs before and after — and must be expressible as such, with evidence references, not as two constants |
| `entries[].evidence` | exactly `{code_probe_seqs: [...], confirm_seq}` | B1's probe design (code probes + one confirming single-address probe); the FF evidence is the record seqs of the observation steps that separated the two values, per context |
| `confidence`, `state`, `anomalies`, `binding` | class-agnostic | kept as they are |

What B4-FF needs, as **new contracts** (names provisional; fixed by unit 2b with the probe
design, so that the schema is written against a probe plan and not before it):

- a relation kind for the class — e.g. `{kind: "ff_config", element: <one of the eight storage
  elements or "slice">, semantic: <one of the seven of §5.2>, value: <the decoded behaviour>}` —
  with `state: unknown` allowed per semantic, not only per address;
- edge kinds for the class — within-slice (shared mode bits), element-to-LUT (the LUT that
  feeds a storage element), and the cross-slice edge kept for anomalies;
- a probe-sequence record whose length is the plan's, with the stimulus sequence's seed and
  the number of edges recorded, not a fixed count;
- an `observed_transition` for the class: the stimulus step (or initialisation event) under
  which the value separated, the context (initialisation / SR state, CE, the edge), the output
  trace before and after (or their digests), and the record seqs that carry the raw trace;
  `null` while the state is `unknown`;
- an `evidence` block naming the observation steps per context (the FF analogue of
  `code_probe_seqs` / `confirm_seq`), and the observation record of §5.3 referenced by digest.

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

**The public task as implemented (`b4/host/b4_landscape.py`, task-v0.1; the owner's ruling 3 of
2026-10-18).** The stimulus (an initialisation step, K alternating clock steps, two input-only steps),
the scoring mask M (every readout cell after the init step), the target t (a bit per cell) and the
weights w (one) are generated from the landscape seed alone by a versioned generator that imports
neither the mapping nor the hypothesis; every arm of a pair receives the same task. The base is the
all-zero configuration — a declared design choice (all-one is permutation-invariant and in the domain
too). The fitness is `f = Σ_{j∈M} w_j · [q_j ∈ {0,1} and q_j = t_j]`; a None cell scores nothing and is
counted; the ceiling `Σ w` never moves with a candidate's applicability; None = None is not a hit. The
holdout stimulus is its own derivation, scored once for a completed run's champion. Whether a task's
ceiling is reachable, whether its base is not already optimal, and whether it carries interaction
(K10) are NOT given by the generator: they are claims for a separate host audit, and a task that lacks
them is an unresolved problem of that task, never a reason to draw another seed.

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
| **X** relabelled addresses (X-A) | O with the cartographer's input transformed: before the base observation a derangement π of the addresses is drawn ONCE from its own control generator (B3's Fisher–Yates-with-rejection rule; every attempt recorded; never the operator's generator, never redrawn or rejected after anything is learned); X's cartographer ingests each specimen with the genome's bits relabelled through π and the q grid untouched, so every seen effect is credited to the wrong address; the shadow ingests the true genome and the contract is checked in full after EVERY ingest (`b4_carto.isomorphic_addresses`: X's relation at π(a) equals the shadow's at a — cells, presence, pair counts, contexts, evidence references — with the version, multi-bit and specimen counts); the ledger keeps the TRUE genome, the transformed input is reconstructible from π. A difference is a **control failure** — its own event, not DOMAIN, not a refusal, not a result: the exposing observation stays in the ledger, scored and counted (a search child among the pending children); after it nothing is drawn, observed, selected or learned; the replay must reproduce it or names it. **What the transformation does not guarantee:** a derangement does not guarantee a changed partition (swapping within every pair and rotating the slice-wide group has no fixed point and maps every group onto itself), so the **residual structure** (`b4_carto.residual_structure`: `partition_preserved`, `groups_moved` = the true groups that are not, as address sets, groups of X's partition) is computed once at the end and REPORTED beside X's rows — never read during the run, never a reason to redraw or to select. The lane permutation of 2b-2 is not an arm: it stays as the cartographer's symmetry test (`permute_grid` / `isomorphic`) | a wrong online map does not profit — evidence under the stated null, its strength per run read with the residual structure, not a logical proof |
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

**The primary and the secondary statistic, and the accounting (B3's, named here so that 2b
cannot pick):** paired by landscape seed *r*, the **primary** `Δ1_r = best_O(r) − best_R(r)` at
`B*` under **search accounting** (R and O charged nothing; the online arm pays its map cost in
time, not in evaluations); the **secondary outcome** `Δ2_r = best_O(r) − end_to_end_F(r)` at
total budget `T = B*`, F's own best-so-far trace charged the mapping cost of the frozen map's
build, from the same F run — reported, no threshold (`docs/b3_architecture.md` §9). The
decision statistic for each is the one-sided exact sign test at α = 0.05, ties excluded from
*n* and counted (`b2_gate.sign_test_p`, by copy). The frozen arm's own benefit over R
(`best_F − best_R`, B2's primary) is reported next to Δ1 as the dose the online arm approaches.

| id | criterion | method (fixed) | threshold |
|---|---|---|---|
| K1 non-saturation | arm Ω's 95th percentile of best-so-far at `B*` below the ceiling; arm R's median at `B*` above the base | B2 G1's computation | `<gate>` |
| K2 not a definitional lock | var(Δ1_r) > 0 at `B*`; there exists a grid budget B at which both `positives(Δ1(B)) > 0` and `negatives(Δ1(B)) > 0` (one condition, within one budget); **and** the same decision procedure applied to control X's pairs does **not** reject H0 in ≥ `<gate>` of 1 000 bootstrap experiments of size N (`b2_gate.bootstrap_reject_rate`, seed 7, by copy — B3's: ≥ 90 %); X's rows carry, per run, the residual structure of its π (`partition_preserved`, `groups_moved` / `groups_true`) and the count of runs whose π preserved the partition — reported, never used to drop or re-pick a run | B3 H2, in full | `<gate>` |
| K3 wrong maps do not profit | D's and X's mean Δ against R as a fraction of F's / O's; their sign tests not significant over S; X's residual-structure counts reported beside its numbers (§8) | B2 G3 / B3 H3 | `<gate>` |
| K4 oracle headroom | Ω's median at `B*` below the ceiling by a margin; F's mean Δ as a fraction of Ω's | B2 G4 | `<gate>` |
| K5 effect, power, N | Cohen's d of {Δ1_r}; `N(B)` by `b2_gate.required_pairs`'s ascending scan (1 000 bootstrap experiments, seed `1 + N`), the sign test by `b2_gate.sign_test_p` — both **by copy into the B4 namespace with their digests recorded**, never by import across the pinned boundary; the session cost `N × arms × B*` under a stated cap | B2 G5 / B3 H5 | `<gate>` |
| K6 no fixed-seed lock | S ≥ `<gate>`; N ≥ `<gate>`; board seeds under a B4 label with every archived set excluded | B2 G6 / B3 H6 | `<gate>` |
| K7 the map is a map | over S: wrong decodes and anomalies in the model of §4.4 (under the behaviour hypothesis — since v0.3 including the latch bit-0 reading of L1 ∧ L2 ∧ L3, so a decode that rests on it is reported as such); the median decoded count at `B*`; `unknown` count reported, never forced to zero | B3 H7, extended by the `unknown` rule of §5.2 | `<gate>` |
| K8 ledger replay | every map version and decode reproduced from the ledger; the raw observation reproduces the fitness | B3 H8 + §5.3 | holds |
| K9 observability | (a) for each of the seven semantics, at least one positive-control address on which the preregistered stimulus sequence separates the two values under the model of §4.4; (b) per address and per applicable context (§5.2), the separation judged and the fraction of addresses covered per semantic reported, the uncovered addresses named and their relations `unknown`; `ff_init` reported separately as "conditional on A8" | new; §5.2 — the same wording as A2 | `<gate>` (per-semantic coverage fractions) |
| K10 real interaction | for each landscape seed and each pair (a, b) of elements or modes whose **four corner configurations** `00, 01, 10, 11` are all **legal** under the class's composition rule (§4.2), the **four-corner index** `I_ab = f11 − f10 − f01 + f00` computed from the landscape's fitness on the model of §4.4 — the four corners differing in (a, b) **only**: every other configuration bit, the initial state (the same initialisation event) and the stimulus sequence are held fixed across the four, and the fixed values are recorded with the index; a pair with an illegal corner is recorded as *not comparable* with the corner named, excluded from the pair denominator and counted. Per seed, three outcomes: **interacting** when some comparable pair has `|I_ab| > <gate>` (a stated fraction of the fitness range); **no interaction seen among the tested comparisons** when every comparable pair has `I_ab = 0` — a statement about the comparisons made, not that every context is additive (an additive score `f = a + b` gives `I = 0` on every pair and lands here); **not assessable** when the seed has no comparable pair at all — never counted as additive. The criterion is the fraction of interacting seeds over **all S seeds** (the not-assessable seeds stay in the denominator), with the counts of the three outcomes reported | new; §7 | `<gate>` |

The budget rule is B3's: `B*` = the grid budget with the smallest session cost `N(B) × 3 × B`
(three arms R, F, O charged at `B`) among budgets at which K1 holds and `N(B)` exists, ties to
the smaller budget; every other row is evaluated at `B*`. The diagnostic rows (B3's H9 form)
are the preregistration's to add. A row that fails is reported, not tuned.

**Seeds, and what determinism does not buy.** The gate's seeds are derived by the line's rule from a label
and a **seed anchor fixed once**, in the same commit that fixes the thresholds, and recorded in the gate
report; every exploration seed set (`b4-sim`) and every failed, aborted or superseded run is retained under
`evidence/b4/sim/` with its seeds, so that the gate's exclusion set and the record of what was tried are
both complete. That a derivation from a commit is deterministic is **not** a protection against selecting
a favourable seed set — a commit can be re-made — and is not claimed as one; the protection is the fixed
anchor, the retained record and the owner's review of the thresholds commit before the gate runs.

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
4. **A loader's default entry verifies; a fixture enters through a marked boundary.** The
   hypothesis loader re-hashes every named source on every load and has no switch to skip it;
   the mapping loader reads the committed certificate only against its pinned digest, and any
   other file only with its digest given explicitly; a hypothesis that is not the committed
   file is built through `fixture(doc, label)` and marked `fixture: true` in every trace it
   produces. A tool that silently accepts a changed source would make "same digest" mean nothing.
   **Provenance is bound through results**: every run records the observation source's identity (the
   hypothesis's path, digest, version and fixture marker; the mapping's site and certificate digest; the
   FABRIC's kind — truth, permuted, dropout, custom — with its effect and dropout digests, count and seed:
   digests only, never the effect table) from its first observation, validates it field by field (exact
   fields and types, 64-hex digests; a malformed or drifting identity is a `SourceRefusal` by its own name),
   requires it equal on every later one, surfaces the hypothesis-fixture and the fabric-fixture markers
   separately, and binds it into every ledger entry; a
   given frozen map is recorded with its whole provenance chain, and a transformation never drops its
   parent — a shuffled oracle is oracle-derived and privileged, never a learned source. A descriptor
   identifies an input; it is no licence to inspect the decode.
   **The formal hypothesis is the committed file and nothing else**: its loader takes no path and holds
   the file to a digest pinned in the module (a change to the file is a change to the pin, reviewed);
   a valid copy at another path is a fixture like any other document (`formal_input` in the file).

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
| 2b-1 (**delivered**; corrected on the owner's HOLD, v0.1.4) | `b4/host/b4_ff_mapping.py` (the certificate mapping of `SLICE_X2Y25`, 21 addresses / 22 names, held to the specimen pairs), `b4/hypothesis/ff_behaviour_v0.2.json` + `b4/host/b4_ff_hypothesis.py` (the behaviour hypothesis: sources by kind with digests, the eleven behaviour flags, the enum readings with the clock mode by storage context, the three contracts of §5.0; the loader verifies by default, fixtures marked), `b4/host/b4_ff_model.py` (the fabric: configuration + stimulus → the executing side's trace under mapping and hypothesis passed in separately, the decode a host-only diagnostic, validation at the entry, out-of-domain configurations refused; the fixtures truth / permuted / dropout / seven hypothesis swaps), `b4/tests/test_b4_ff_*.py`, `b4/IMPORT.json` | hand-derived expected traces; INIT and SR separated; CE, edge, kind, transparency; isolation; permutation; hypothesis swap; the mutants (a model that ignores its hypothesis is killed) |
| 2b-2 (delivered v0.1.6; **HOLD and follow-up v0.1.7**: replay as re-execution, provenance bound, the holdout contract; X a symmetry control pending the design review) | `b4/host/b4_execution.py` (the port that exposes `observe` and the addresses only; the terminal event), `b4/host/b4_landscape.py` (the public task and the scoring), `b4/host/b4_engine.py` (the derived (μ, λ) engine over the FF universe; R / F / O / X; DOMAIN termination as ruled), `b4/host/b4_carto.py` (the observation cartographer: seen cells, presence, no-effect-seen, context-dependent, unknown; groups; the v3 draft; control X with its shadow isomorphism; A0, D, the privileged Ω), `b4/host/b4_replay.py` (EXACT replay), `b4/host/b4_stats.py` (the four-corner computation), `b4/host/b4_rng.py` (the PRNG copy), `b4/schemas/self_map_v3.schema.json`, the tests. **No exploration run, no gate number, no threshold.** The exploration under `b4-sim` (S = 32 first) follows 2b-3 and its own authorisation | the revised scope's acceptance list (section 6); the thresholds commit before any exploration |
| D1′ latch_ginv probe (**delivered; PASS on `e0b5f04`**; the owner's ruling of 2026-10-18 §2 and the follow-up ruling) | `b4/probes/latch_ginv/` (the derived specimen and build script with `GINV`, the driver with the expectation fixed before the build, the test), `evidence/b4/unit_d1prime_latch_ginv_2026_10_18/` (attempt 1: the six bitstream clauses and the structure held, the cell rule's `ROUTED`-only reading of `INTRASITE` the finding, kept as it was) and `…_attempt2_2026_10_18/` (the rule accepting `ROUTED` / `INTRASITE`: every clause met, no finding; readbacks and configuration frames identical to attempt 1's; the historical `main_latch` reproduced frame-for-frame) | host correspondence only; nothing of the model changed; v0.3 a separate unit |
| v0.3 model revision (**delivered**; the owner's ruling of 2026-10-18 on the scope draft, after the PASSes on `e0b5f04` and `c0689f8`) | `b4/hypothesis/ff_behaviour_v0.3.json` (the latch bit-0 reading on the D1′ pair, labelled host correspondence; the three layers L1 / L2 / L3 in their own source entries; the domain complete by assumption; the init step's atomic assignment named a model abstraction), `b4/host/b4_ff_hypothesis.py` (the formal pointer and digest only), the v0.2 file kept byte for byte, the tests (the hand-derived inverted-gate trace in the model's settle order; the `v021_hole` fixture carrying the 0.2.1 result; F completing under 0.3.0), `b4/IMPORT.json`, this document, `evidence/b4/unit_v03_2026_10_18/` | the local regression and the mutants; the owner's review; silicon status unverified; not gate-ready |
| X-A (**delivered; PASS on `c0689f8`**; the ruling of 2026-10-18 §4) | `b4/host/b4_carto.py` (`derangement_attempts`, `relabel_genome`, `isomorphic_addresses`, `residual_structure`; the lane permutation kept as the symmetry test), `b4/host/b4_engine.py` (arm X over relabelled addresses with its own control seed, π before the base, the shadow contract after every ingest, the control failure event, the residual post hoc), `b4/host/b4_replay.py` (π re-derived from the control seed; the control fields typed; a control failure must reproduce), the tests, `evidence/b4/unit_xa_2026_10_18/` | the partition-changing fixture and the partition-preserving counterexample; π from the control generator (the operator's untouched); base / mid-generation termination; the control failure's commit point; full replay; 19 mutants. Mechanism only: no arm advantage measured, no seed scan, no landscape exploration |
| 2b-3 | the K1–K10 thresholds and τ written into §9, the seed anchor, in one commit | the owner's review before any gate run |
| 2b-4 | `b4/host/b4_gate.py`, the formal gate under `b4-gate-1` (S = 200), `docs/b4_gate_report.md` stating every result as "under the behaviour hypothesis"; the v3 map schema draft (§6) | every row PASS / FAIL; a PASS never read as evidence about the fabric |
| 2c | `docs/b4_preregistration.md` DRAFT (B4-FF: claim, pins, prediction, metrics, falsifiers, sessions and rulings, compatibility, lifecycle, §9 rule; B4-R: prerequisites and prohibitions only) | the owner's review; the holdout and the universe fixed by whole site instance |
| carrier v2 design | RTL, bench, XDC, isolation — against §5.5 A1–A8 | a separate unit after 2c |
| 2d | provisioning and the supply measurements (§11) | board work; the owner's rulings per step |

## 14. Files and references

`b4/host/b4_ff_mapping.py` · `b4/host/b4_ff_hypothesis.py` · `b4/hypothesis/ff_behaviour_v0.3.json` (the formal hypothesis; `ff_behaviour_v0.2.json` kept as the 0.2.1 record) · `b4/host/b4_ff_model.py` · `b4/IMPORT.json` ·
`evidence/b4/unit_d1prime_latch_ginv_attempt2_2026_10_18/probe_report.json` (the v0.3 L1 source) ·
`docs/autonomous_cartography_roadmap.md` (§1–§7) · `docs/board_roles.md` ·
`docs/ff_preregistration_plan.md` (§1–§5, §7) · `gate_runs/run_2026_08_05_ff/certificate.json` ·
`data/MANIFEST.json` · `schemas/self_map_v2.schema.json` · `docs/b1_carrier_contract.md` ·
`docs/b1_architecture.md` §5 · `docs/b2_architecture.md` §4, §5, §7, §7a, §8 ·
`docs/b3_architecture.md` §3, §5, §9, §10 · `docs/b3_preregistration.md` §8, §9 ·
`docs/b3_result_2026_10_15.md` · `docs/claimb_round1prime_package.md` §9 · `docs/mux_groups.md` ·
on the branch `b3-pinned-test-repair` at `4db22e5` (not merged): `docs/b3_lifecycle2_pinned_test_audit_delta_2026_10_15.md`,
`evidence/b3/repair_2026_10_15/README.md`, `evidence/b3/repair_2026_10_16_canonical/README.md` · `b3/firmware/IMPORT.json` ·
`/home/test/test_devices/result.txt` (the 2026-08-25 `08EB` retest).

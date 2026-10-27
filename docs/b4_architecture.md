# B4 — expansion from LUT content bits to the FF class, then routing: architecture (DRAFT v0.3.0, host-only, 2026-10-16; revised 2026-10-20, 2026-10-27)

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
> quoted from a named source or, for the gate's thresholds, fixed in advance by unit 2b-3 under the
> owner's ruling of 2026-10-18 (§9): an advance engineering criterion, never an empirical result.
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
>
> **Revision v0.1.12a (2026-10-18, the owner's PASS on `12eaa72` with two P3 documentation corrections; documents only):**
> §4.4's source row now names the formal v0.3 file and its four machine source kinds, with the v0.2 identity kept apart as
> historical; the unit's evidence labels the pasted v0.3 ruling an excerpt and archives the owner's full ruling beside it.
>
> **Revision v0.1.13 (2026-10-18, unit 2b-3, the owner's ruling on the thresholds scope draft after the PASS on
> `b2a958c`):** every `<gate>` of §9 replaced by a threshold fixed in advance — K1 two medians with B2's interpolated
> percentile, K2 population variance with X's bootstrap non-rejection ≥ 90 %, K3 the 10 % ratios with `mean(F − R) > 0`
> and `mean(O − R) > 0` required and a non-positive denominator failing the row, K4 57.6 and 50 % against a grouping
> reference that is no proved bound, K5 d ≥ 0.5 with power ≥ 0.90 on a complete ascending scan and the 4 000-evaluation
> cap, K6 S = 200 and N ≥ 8, K7 rewritten (zero ledger-recomputation mismatches; O's `B*` prefix median ≥ 11 of 21; the
> certificate-versus-observed partition difference a diagnostic, not a defect), K8 over every executed run, K9 the ≥ 90 %
> of seeds and ≥ 0.50 median coverage on §9.3's fixed comparison set, K10 τ = 2 score units with `max|I| > 2`, two fixed
> backgrounds, all 210 address pairs and ≥ 0.50 of S. The grid `{8 … 256}` and the `B*` rule; no eligible budget means
> the budget rule FAILS and the gate cannot PASS. §9.1: a verdict needs every planned run complete, a contract break is
> `invalid`, no PASS from survivors, and no `N` on valid complete data is an ordinary result. §9.2: the anchor is the
> formal hypothesis's digest with the label passed beside it, the X and D control seeds have their own formulas, and the
> exclusion set is listed file by file with digests, with `evidence/b4/sim/` named as not yet created and B4's exposed
> seeds listed. §8: D is the same seed's F-learned frozen map passed once through `shuffled_view`, never a shuffled
> oracle. Documents only — no code, no run, no seed value, no K result. **Not gate-ready**; the thresholds commit is
> itself no gate-readiness verdict, and a later revision keeps the old version, its reason and its results, needs its own
> authorisation and a complete re-run, and never re-labels an earlier run.
>
> **Revision v0.1.13a (2026-10-18, after `3564236`; no threshold, grid, formula or seed changed; wording, except that the
> K9 (b) rule "one not-assessable seed makes the semantic's median not assessable" is a DECISION-POLICY ADDITION fixed in
> advance — accepted as such by the owner's ruling of 2026-10-18 on unit 2b-4a §1, not a wording change):** K2 and K3
> name the sign test's direction (H1: the control beats R) and the population it runs on; K7 (b) defines O's `B*` prefix
> as ledger records (base through the `B*`-th search evaluation); K9 names the seven semantics, states that `ff_init`
> counts as the others do with its A8 flag in addition, and fixes the median's population (all S seeds; one
> not-assessable seed makes the semantic's median not assessable); K10 says why a not-comparable corner can only be a
> DOMAIN refusal under v0.3; the `B*` paragraph says K1 is evaluated at every grid budget for eligibility and that a bare
> `N` is `N(B*)`; §9.2 says the exclusion set is one pooled set of integers applied to both positions of a pair.
>
> **Revision v0.1.14 (2026-10-18, unit 2b-4a commit A, the owner's ruling of 2026-10-18 on the exploration-harness scope
> draft; no threshold, grid, τ or anchor changed):** the owner's P3 — the sign test's H1 is written in its conditional form
> P(Δ > 0 | Δ ≠ 0) > ½ (ties excluded from *n*; all ties → p = 1, never a 0 filled in); §9.2 names the typed reading of the
> exclusion table and the rule that every archived set under `evidence/b4/sim/` joins the pooled set; the two manifests'
> `seeds.pairs` fields are listed as seed-bearing (they were read by the typed loader and the table now says so); §13 carries
> unit 2b-4a with commit A delivered. The v0.1.13a note now states that its K9 (b) rule is a decision-policy addition the
> owner accepted, not a wording change. **Commit B** (same date): §13's row carries the deadline, the statistics copies, the
> observation memo, K9's and K10's drivers; the hand-counted applicable denominators of §9.3's set (384 / 384 / 32 / 32 /
> 16 / 32 / 32) are stated there and held by a test. No threshold or method of §9 / §9.3 changed. **Commit C** (same date): the
> harness, its validators and the thresholds table (§13, §14); the exploration harness EXISTS but no exploration has run —
> running it is a separate authorisation (the ruling's §5).

> **Revision v0.1.15 (2026-10-18, the repair unit after the owner's HOLD on `cdf2c53` — nine reproduced gaps F1–F9; no
> threshold, grid, τ, anchor, formula or hypothesis changed; no old engine / cartographer / replay / statistics primitive
> changed):** §9.2 names the two label namespaces — `b4-sim-<n>` for a PRODUCTION set (the anchor and the master derived
> here and only here) and `b4-mech-<n>` for a MECHANICS fixture set (an explicit schedule of values already exposed under
> this section, no anchor, no master, no draw; the harness's tests use these only, and a guard in the tests fails if a
> production derivation is ever reached) — and records that before this repair the harness's integration tests DID derive
> production `b4-sim-1` / `b4-sim-2` sets on hermetic copies (S = 2, several times); the records that still existed are
> preserved under `evidence/b4/unit_2b4a_repair_2026_10_18/exposure/` and their treatment is the owner's pending decision
> before any exploration. §9.1's stop rules gain the batch's own archive-wide verification (`b4/host/b4_sim_verify.py`: the
> required file set, hashes, linkage and the conclusions recomputed from the raw readouts — a finding makes a would-be
> complete batch `invalid`, as does a report that cannot be validated or written), the FIXED comparison sets enforced by
> the validators (a complete K9 record holds exactly the 1 184 forced pairs, a complete K10 record exactly the 420 units,
> a partial one a prefix; a q cell is 0, 1 or null), the quarantine of a returned object that does not validate (kept raw
> with its findings, never dropped, never written as valid), the partial K9 / K10 record kept on every failure, K10
> observing NO corner after the first refused one, the deadline checked before every finalisation unit (a batch whose
> deadline expired is never `complete`), the namespace confined through no symlink at any level, and the checkpoints
> holding every input — the root inputs, the hypothesis's repository and external (vendor) sources, the 38 exclusion
> sources, the tool files and the archived-set registry snapshot. §13's 2b-4a row records the HOLD and the repair.
> **Second round (same date, the owner's HOLD on `f2c4bca`, five residual findings R1–R5):** a complete pair has every arm
> audited and K7 / K9 / K10 complete — a weaker recorded state is refused by the planned-record and pair-index validators and,
> independently, the deep verifier re-audits every arm of a complete pair whatever its recorded state (R1); every record is
> bound to its planned pair, role and seeds (the arm wrapper and the result's seeds, budget, task digest, control seed and
> provenance; the curves' and index's seeds; every file's pair) and every manifest descriptor (hypothesis, mapping, fabric,
> constants, thresholds) to the formal inputs — replay alone cannot see the plan, so a self-consistent result from another
> exposed seed is refused by the binding, not by the replay (R2); every id, reference, index, count and τ is an exact int
> and every recomputed value is compared as canonical JSON text, so `false`, `0.0` and `0` are three different records (R3);
> after the batch's own deep verification — a long unit — the deadline is checked again, every input, the registry and the
> tree are held again, and the deadline record is taken after those checks: a success is never published on a stale
> on-time record or over a drifted input (R4, R5). **Third round (same date, the owner's HOLD on `6c00156`, three
> residual findings):** a plan's K7 / K9 / K10 state is confirmed by its document and never its own authority — `complete`
> needs a complete document with neither stop nor invalid record and the full fixed set, so a genuine partial diagnostic
> cannot sit in a complete batch; the remaining totals (`pairs_total`, `units_total`), the corner genomes, the prefix
> budgets and counts are exact ints; the deadline record is validated for its types and its self-consistency at the
> record's millisecond precision (`expired` ⇔ `elapsed_s ≥ seconds`; `first_expired_at_s` exactly when expired) and
> bound to the manifest's `deadline_s` written before the first observation — a late stopped record remains a
> consistent record; a complete report's elapsed time lies within its declared seconds. **Fourth round (2026-10-19, the
> owner's HOLD on `8d1eefd`, two P2 findings and one gap found while fixing the second):** the diagnostic state ↔ file
> contract is asked only about documents their typed validator accepted and is itself total (a document that is not an
> object, a set that is not a list, is a finding, never an exception; the verifier's CLI reports an exception as a finding);
> the deadline record is ONE monotonic sample — elapsed, expired and the first expiry describe the same instant, in
> `record()`, `expired()` and `check()` alike, so the producer can never write a record its own validator refuses (the
> owner reproduced `elapsed_s 59.99, expired true, first_expired_at_s 60.01` from three samples, and a stopped batch that
> could not write STOPPED.json because of it); the soft policy, the record's keys and its precision are unchanged. An
> interrupt inside K9 / K10 before any record was returned leaves the stage `in_progress` (entered, no document), not
> `partial` (which promises a stopped document) — found when the repaired stopped batch was verified end to end.
>
> **Revision v0.1.16 (2026-10-19, the exposure settlement after the owner's ruling of 2026-10-19 on the prior
> production-seed exposure; a bounded administrative correction made BEFORE any result exists — no threshold, τ, grid,
> anchor formula, control formula or hypothesis changed; no exploration run):** the labels `b4-sim-1` and `b4-sim-2`
> are RETIRED — their sets were derived before the repair by tests, a smoke test and the mutant battery, so no new
> production derivation under them is allowed (the harness refuses the label before any tree is read; the registry
> still reads their archived records) — and the next exploration label is `b4-sim-3`, reserved before any value of it
> exists and not derived in the settlement. §9.2 gains a fourth pooled component, the EXPOSURE RECEIPT
> (`evidence/b4/unit_2b4a_exposure_settlement_2026_10_19/exposure_receipt.json`, pinned by digest in `b4_seeds`): a
> seed-only reconstruction from the historical derivation code (`edfc93c`) and the historical exclusion contents of
> every set the committed recipes could have drawn (`b4-sim-1` sets 1–7 in sequence, `b4-sim-2` set 1, the M1 mutant's
> variant), compared record by record with the 22 preserved seed records (all agree), with the control seeds of every
> drawn pair; each value marked observed / reconstructed_recipe / conservative_superset. The receipt is a root input:
> pooled into both pair positions at derivation, named in `seeds.json` and the manifest, held at every checkpoint and
> bound by the verifier. It makes the known and reconstructable exposure EXCLUDED; it does not make the historical
> exposure record complete — the raw evidence of the deleted runs is lost and is not recreated, and uncommitted
> development versions of the tests that ran before `edfc93c` are outside the reconstructed envelope.

> **Revision v0.3.0 (2026-10-27, the task-v0.3 revision unit after the carrier v2 finding; a protocol revision of the task's stimulus
> rule and of the records that hold it, written on the branch `b4-task-v03` from the carrier v2 closure `e084f07` under the owner's
> ruling of 2026-10-27 — "a complete host-only revision engineering unit, delivered for review once"; mechanics fixtures only; no
> production label derived, no exploration, no gate; the model's state machine, the hypothesis file, the certificate, the operator, the
> engine, the cartographer, every K1–K10 number, the go / no-go policy's numbers, the statistics copies, the K9 panel and both
> applicabilities, K10, the anchor formula and every archive, receipt, seed and verdict UNCHANGED):**
>
> - **The reason, and what it is not.** The carrier v2 unit (`docs/b4_carrier_v2.md` §0, accepted on `bf17574`) found that a 7-series
>   slice has **one CE pin, one SR pin and one CLK pin shared by its eight storage elements** (AMD UG474: the site's `CEUSEDVCC` /
>   `SRUSEDGND`, one each). task-v0.2's stimulus drew `ce` uniformly over 256 values and `sr` per element with probability 1/4, so
>   almost every step is **not realisable** on the site (the carrier refuses it by name, `F_NOT_REALISABLE`). task-v0.3 makes the
>   stimulus fit the physical slice — **that is its reason** — and not an attempt to improve the three negative Ω − R records
>   (`b4-sim-3`, `b4-gate-1`, `b4-sim-4`), which stand as they are and are not re-interpreted; §9.4 of v0.2.0 permits new research
>   with its own reason and ruling, and this is one. Nothing in v0.3.0 predicts a map benefit: the new stimulus may change K9's
>   coverage and the search's behaviour, and both are to be **measured again** under a new label, never carried over.
> - **§7.2 — task-v0.3, the slice-wide control stimulus.** Per `set` step the generator draws **one** CE value (high with probability
>   **1/2**) and **one** SR value (high with probability **1/4**), the two draws independent, and **broadcasts** each over the eight
>   elements in the common 8-bit grammar (`0xFF` / `0x00`); `d` stays a per-element uniform 8-bit draw; the draw order is `ce`, `sr`,
>   `d`; K = 6 / 8, the two level steps, the mask, the weights, the ceilings 64 / 80 and the planted target (T-i) and the executing
>   side's input (H) of §7.1 are unchanged. The shared control inputs do **not** merge the eight elements' INIT / SRVAL into one value:
>   those sixteen bits stay per element. The 8-bit grammar is kept because it is the common grammar of the model, the observation
>   contract (2.1) and the carrier's `STEP_IN` word; the model's per-element evaluation under a broadcast vector gives every element the
>   same control value — the slice-wide semantics — so the model's state machine is **not** rewritten (held by a test against a
>   slice-wide twin); the carrier's realisability refusal becomes an invariant the task never hits. The shape is **held, not assumed**:
>   `b4_landscape.stimulus_findings` names any set step whose `ce` / `sr` is not a broadcast, and every task record is checked by its
>   validator and by the offline reconstruction. The ceiling (64 / 80) is verified as the **count of scoring cells**; the planted
>   configuration's reachability of that ceiling on its own trace is verified per pair (`b4_target.setup_findings`); the two are not
>   the same statement, and a search's reaching it is not guaranteed.
> - **K9 (§9, §9.3 clause 7).** The comparison set, the 64 backgrounds, the 1 184 forced pairs and **both** applicabilities (the
>   all-panel (b) and the judged conditional (b′)) are unchanged; what changes is the stimulus under which the pairs are observed —
>   K9 measures observability under the task's own stimulus, which is now slice-wide. Under a slice-wide SR every element sees the
>   same SR level at the same step, so a per-address `ff_srval` / `sr_kind` coverage is **a different quantity** from the one measured
>   under per-element SR patterns; the `b4-sim-4` K9 record (per-element SR) is not reinterpreted, not compared and not re-decided;
>   the v0.3.0 coverage is to be measured by the next exploration. The data influence is disclosed in §7.2.
> - **§9.2 — labels.** `b4-sim-4` is **consumed** by its archived records (S = 32, 2026-10-21; its 65 values in the registry and the
>   pooled exclusion, 2 690 at this revision; `b4_seeds.CONSUMED_LABELS`). The next exploration label is **`b4-sim-5`** — a reserved
>   name only, no value derived. `b4-gate-2` stays the reserved gate name: no value of it was ever derived under v0.2.0 (the
>   exploration ended no-go), so the same label under this version reproduces nothing. The anchor formula is unchanged.
> - **§9.4 — the go / no-go row of `b4-sim-5`.** The complete policy is carried unchanged: S = 32 all complete, B = 64, the one-sided
>   exact sign test on Ω − R with positives > negatives and **p ≤ 0.20**, the seven judged conditional K9 medians ≥ 0.50, incomplete
>   data → no decision. The p threshold is named for what it is — **`p_max_go`, an engineering cost threshold on the sign test's p,
>   not the α of a formal scientific test** (the machine table's key is renamed from `alpha_go` to `p_max_go`; the number is the
>   same); the execution plan cites the fixed rule and chooses nothing. `b4-sim-4`'s no-go of record is not re-decided.
> - **§9.5 — the identity.** The task's stimulus rule (its constants and its text) is a component of the protocol identity; the
>   v0.2.0 archive `b4-sim-4` (and its go / no-go record) is therefore of another method version and is refused by name by every
>   v0.3.0 verifier, judge and policy, pointed to `docs/b4_archive_reverification.md` §6 (re-verify it with its own tool at its
>   recorded HEAD `495cc36`). No verifier is a general version selector.
> - **The observation contract** `docs/b4_observation_contract.md` is revised narrowly to **v0.6** (§2.2 the task-v0.3 shape with the
>   broadcast stated as one control value per step; task-v0.2's shape kept as history; the common grammar and the carrier format
>   unchanged; A1–A8, the transaction order, INIT / SRVAL, restore and sampling requirements unchanged). `docs/b4_preregistration.md`
>   v0.0.4 points at it.
> - **Unchanged, named.** `b4/hypothesis/ff_behaviour_v0.3.json` and its digest (hence the anchor); `b4_ff_model.py`; the certificate
>   mapping; the engine, the cartographer, the controls, K10, the replay; every number of §9; the statistics copies; the exposure
>   receipt; `b4-sim-3` / `b4-gate-1` / `b4-sim-4` and their verdicts; the carrier v2 RTL, register map and record layer (accepted on
>   `bf17574`, this unit maps onto them and changes nothing there).

> **Revision v0.2.0 (2026-10-20, the protocol revision after the production gate `b4-gate-1`; a DESIGN revision of the
> documents, written on the branch `b4-protocol-v2` from `d19cc2f` under the owner's ruling of 2026-10-20 on the scope
> proposal v0.2 — seven binding choices and the supplementary contracts of
> `evidence/b4/unit_protocol_v2_design_2026_10_20/`; no program, hypothesis, import table, thresholds table, archive, seed or
> verdict changed; nothing run):** the formal gate `b4-gate-1` (S = 200, 2026-10-20, `evidence/b4/gate/b4-gate-1_20261020T102526Z`,
> the owner's PASS on the executed unit `d19cc2f`) is a **valid FAIL of protocol v0.1.16** — the budget rule FAILS (K1 eligible at
> every grid budget, N null at every budget, so B\* and N do not exist and K1–K7 are not assessable), K9 FAILS ((b): `ff_srval`
> median coverage 0.40625 < 0.50; (a) 200 / 200 seeds with all seven positive controls), K8 and K10 PASS. The correct statement of
> that result is **"this sample and this design did not meet the pre-set benefit and coverage criteria"** — not "the map is useless",
> not "`ff_srval` is unobservable", not "the task is the cause": Ω is a fixed certificate-derived grouping with a fixed operator, not an
> upper bound over maps and operators, and its deficit against R does not separate grouping, operator, task and budget. That result
> and its archives stand unchanged; nothing in v0.2.0 re-judges them, and nothing in v0.2.0's future performance is evidence about
> v0.1.16's cause. v0.2.0 defines a **new host benchmark contract** for the next exploration and gate, each of which needs its own
> tool unit, its own exploration and its own execution ruling before any of this takes effect:
>
> - **§7.1 — task-v0.2, the planted flip-flop target (the owner's choices 1, 2, 3)**: the target is the observed trace of a planted
>   configuration `g*` under the task's own stimuli — *fabric-dependent* by construction (the hypothesis in simulation, the die on a
>   board), which is a substantive change of the mapping-independent public-task contract of §7 and is **not** equivalent to B2's
>   D2 (B2's phenotype-to-genome correspondence was not handed to the arms); **T-i**: `storage_kind` fixed to flip-flop, the other
>   20 bits drawn once, the all-zero base not excluded, nothing redrawn; the search universe stays 21 bits, the ceilings 64 / 80,
>   None scores nothing; **H**: the executing side's inputs carry no landscape seed, no `g*` and no private target record — a
>   fixed-program access contract, never a claim of information hiding. The setup, persistence, isolation, cost and replay
>   contracts of §7.1 are the owner's supplementary rulings, written here before any tool implements them.
> - **§9 K9 (b′) and §9.3 clause 6 (choice 4)**: the judged coverage of `ff_srval` and `sr_kind` becomes the *conditional coverage
>   under SR-driven backgrounds*, median ≥ 0.50 per semantic; (a) stays at ≥ 90 %; the old all-panel (b) is kept beside it as a
>   description, recomputed from the same retained raw grids under the old applicability — never filled in with model-derived
>   zeros; the two applicabilities are recorded separately.
> - **§9.4 (choice 5)**: an engineering go / no-go policy for the exploration `b4-sim-4` (S = 32, B = 64, one-sided sign test
>   p ≤ 0.20 with positives > negatives, all seven conditional medians ≥ 0.50, every planned pair complete and valid or no
>   decision) — a cost policy, not a significance result, not a gate, not an authorisation; and the no-automatic-successor policy.
> - **§9.5 (choice 6)**: a multi-component protocol identity (thresholds, task, panel / applicability, K10, the statistics copies,
>   engine / cartographer / execution / snapshot / replay, summary, judgement, validators / verifiers, schemas by content, the
>   hypothesis and the certificate; the document's revision text excluded from the digest and from the equality) that a verifier
>   compares against a payload rebuilt from its own trusted inventory, refusing by name what it does not support; the anchor
>   formula unchanged; designed here, not implemented.
> - **§9.2**: the proposal labels `b4-sim-4` and `b4-gate-2` are reserved names only; `b4-sim-3` and `b4-gate-1` are consumed by
>   their records. **§5.5 / A2 (choice 7)**: the data-informed selection rule for the positive-control pairs is fixed in words
>   (the most-covered unique forced pair per semantic in the gate-1 K9 record, tie-break by `bit`, `g0`, `g1` numeric order,
>   `ff_srval` / `sr_kind` from SR-driven and old-applicable pairs only), disclosed as tuning on gate-1; not executed here.
>   **Revised by the owner's acceptance of 2026-10-21 (the review of `4fc3dc7`, the 2c-obs unit):** the B4Q qualification-selection
>   rule is now the one of `docs/b4_observation_contract.md` §7.2 — the source the `b4-sim-4` archive under task-v0.2 and K9 (b′)
>   (the protocol the carrier will be qualified against), address-first by the pooled (b′) fraction over the 32 pairs (ties in the
>   mapping's address order), then the background covered in the most pairs (ties the lowest `g0`), one main-element and one
>   x5FF-element address each for `ff_init` / `ff_srval`; the nine pairs of §7.3 are the **data-informed DRAFT A2 selection** for
>   later B4Q planning, selected on host-model data as disclosed there. The gate-1 wording above is kept as the history of the
>   first choice and is not rewritten; the K9 panel, both applicabilities, the model, the method, the thresholds and the archives are
>   unchanged. The selection is not a certificate, a legal-composition rule, a whitelist, a fixed qualification-stimulus guarantee
>   or a board-demonstrated control.
> - **`docs/b4_archive_reverification.md`**: the historical re-verification procedure for the two named archives (code HEAD,
>   archive commit, repository inputs and external dependencies kept apart; the registry-at-start versus registry-at-archive
>   relation stated correctly).
>
> **Precedence (the owner's review of `8361068`, item 3).** On the items they change, v0.2.0's §7.1, K9 (b′), §9.3 clause 6, §9.4 and
> §9.5 **supersede** the older descriptions; the older requirements of §7 that are retained (the public rule from the seed, the
> generator reading no certificate, map or operator, the base all-zero, None scoring nothing) **do not** forbid the approved T-i
> target or the inclusion of the base as a planted outcome; retained historical text and the pinned strings of the thresholds table
> do not make two current methods — there is one, v0.2.0 — and task-v0.1 is referenced only for the stimulus rule the ruling kept
> unchanged (the sparse-SR sequence, K = 6 / 8, the two level steps). The v0.1.16 archives are read under their own version
> (`docs/b4_archive_reverification.md`).
>
> **Implementation status (the v0.2.0 tool unit, delivered on the branch `b4-protocol-v2` after the owner's authorisation of
> 2026-10-20; mechanics fixtures only, no production derivation):** `b4_landscape` task-v0.2 (`public_parts`, `planted_genome`,
> `targets_from_grid`, `make_task`); `b4_target` (the setup, its persistence and its offline reconstruction); `b4_execution.PublicTask`
> without the seed, `TerminalEvent` with the task digest; `b4_engine` / `b4_replay` / `b4_controls` / `b4_k10` taking the seed from the
> harness; `b4_k9` with both applicabilities and both records; `b4_sim` with the per-pair setup, the task state, the durable ordered
> prefix (`task_prefix` / `task_quarantine`), the quarantine of a refused target return and the identity in the manifest; `b4_sim_schema`
> (the setup records, manifest 1.2.0, quarantine 1.1.0 with the target context, K9 1.2.0, curves / index 1.1.0, stopped / report 1.2.0,
> the state ↔ prefix contract); `b4_sim_verify` with the identity gate at step 0, the setup reconstruction, the exact prefix file set and
> real files in pair directories only; `b4_gate` / `b4_gate_verify` judging (b′), carrying the protocol digest and refusing other versions
> by name; `b4_gonogo` (§9.4; exact types, a plain in-root evidence path, the directory's entries held); `b4_protocol` (§9.5); `b4_seeds`
> with the consumed labels; `b4_thresholds` = "section 9" with no revision text, `ARCHITECTURE_REVISION` read from
> `b4/architecture_revision.json` (outside the inventory), the labels `b4-gate-2` / `b4-sim-4`, the K9 applicability fields, the task and
> go / no-go blocks; the static pin re-implemented (`test_b4_thresholds`: the first line of this document against that file's value, no
> revision literal in any tool file or test, the method digests unmoved by the revision). The harness records this document's digest in
> every manifest (`b4_sim.ROOT_INPUTS`) without pinning it, and the verifiers compare recorded values only. The corrections after the
> owner's HOLD on `04385ae` (R1–R6) are recorded in `evidence/b4/unit_protocol_v2_tool_2026_10_20/README.md` §5. **Nothing here is
> authorised beyond the tool**: no derivation of any label, no exploration, no gate, no board, no push, no merge. The data influence of
> `b4-sim-3`, `b4-gate-1` and the two scope drafts on every choice is tabulated in `evidence/b4/unit_protocol_v2_design_2026_10_20/README.md` §4.

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
| source | `gate_runs/run_2026_08_05_ff/certificate.json`, the plan's attestation fields (plan §3) | **four machine kinds, listed per entry in `b4/hypothesis/ff_behaviour_v0.3.json` `sources`** (the formal file since the v0.3 unit): (1) `vendor_primitive` — the vendor's UNISIM simulation models `FDRE.v`, `FDSE.v`, `FDCE.v`, `FDPE.v`, `LDCE.v`, `LDPE.v` under the root `/home/test/Xilinx/2025.2/data/verilog/src/unisims`, each by path, sha256 and the lines adopted (the GSR initialisation, the edge and level rules, the latch UDP table; the L2 layer below); (2) `certificate_mapping` — the certificate, by path and sha256 (addresses, elements, the Z readings' directions; no behaviour); (3) `repository_document` — `docs/ff_latch_probe.md` and the D1′ probe report `evidence/b4/unit_d1prime_latch_ginv_attempt2_2026_10_18/probe_report.json`, each by path and sha256: **host exploration / readback / bitstream correspondence** records (the L1 layer), not certificate mappings and not silicon attestations; (4) `project_decode_assumption` — the project's own decode assumptions (the Z readings, the primitive-selection table, the pin correspondence, the initialisation event modelled as GSR, and since v0.3 the generalisation assumptions G1–G6; the L3 layer). Nothing of (1)–(4) is a measurement of this line. *Historical identity, kept apart:* `ff_behaviour_v0.2.json` (0.2.1, sha256 `1118bedf…`) carried kinds (1), (2), (4) and one document of kind (3); it is kept byte for byte as the record of 0.2.1, never loaded as formal, and enters the tests only as the marked `v021_hole` fixture |
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

### 7.1 task-v0.2 — the planted flip-flop target (DRAFT v0.2.0; a new host benchmark contract, not implemented)

**Standing (the owner's ruling of 2026-10-20, choice 1).** task-v0.2 is a **new host benchmark contract** for the next exploration
and gate under this protocol. It is not a repair of a proven cause of `b4-gate-1`'s FAIL (none was proven), it is not equivalent to
B2's D2 (there the target lived in readout space and the phenotype-to-genome correspondence was not given to the arms), and no
result under it is evidence about v0.1.16's cause. Everything in this subsection is a contract to be implemented, tested on
mechanics fixtures and accepted by a separate tool unit before any derivation; the harness, engine and task generator in `b4/host/`
at this revision still implement task-v0.1.

**The target (choice 3, T-i).** For each pair the host plants one configuration `g*`:

- the `storage_kind` address, as the certificate mapping identifies it (`b4_ff_mapping`), is **fixed to flip-flop**; the other
  **20 bits are drawn once** by a rule fixed before any draw — its own salt, its own generator, independent of the task stimulus,
  the operator, the control and the K10 generators: `Rng((landscape_seed ^ SALT_TARGET) & 0xffffffff).uniform(1 << 20)`, the first
  call, mapped onto the 20 non-`storage_kind` bits in address order, with `SALT_TARGET` = 0x54415247 (an arbitrary constant, fixed
  before any draw by the tool unit and named in the protocol identity, §9.5; `b4_landscape.planted_genome`);
- the all-zero base is **not excluded**, and **nothing is redrawn** — not for a genotype equal to the base, not for a trace equal to
  the base's, not for a low score, not for a None;
- the candidate search universe stays the **21 bits**; the search and holdout masks, weights and ceilings (**64 / 80**) and the rule
  that a None cell scores nothing are unchanged (§7);
- a formal target observation that contains a None or a malformed value is **`invalid`** (kept, stopped, named) — there is no switch
  to a per-task mask or a tri-valued target in this version, and no mask is narrowed.

*Disclosure of the prior.* The target space is the flip-flop half of the model's domain: `g*` is never a latch configuration. The
search still visits latch candidates, whose four x5FF elements read None on every step and therefore score nothing on 32 of the 64
cells — a low-score region of the landscape that follows from this prior, not an observation about latches. The new primary
comparison gives no evidence about a latch-target task.

**The executing side's inputs (choice 2, H).** `PublicTask` — what every arm receives, identical for the seven arms of a pair —
carries the label, the task version, the addresses, the base genome, the search stimulus, mask, target and weights, and the holdout
stimulus, mask, target and weights, and its digest. It carries **no landscape seed, no `g*` and no private target record**.
`PrivateTask` — held by the harness only — carries the landscape seed, `g*`, the salt, the two setup observations with their
provenance, and the private record's digest. The engine and the cartographer never read `PrivateTask`, the host archive, the mapping,
the hypothesis or `diagnose`, and implement no inference of the seed or of `g*` from anything; the operator seed and the control
flows are used for their declared purposes only. The context the engine hands the port (`b4_execution.observe_candidate`) carries the
task digest in place of the landscape seed; the `TerminalEvent`'s seed field is filled by the harness when the event is recorded;
the replay takes the seed from the pair record, never from an arm. **This is a fixed-program access contract, not information
hiding**: the host process holds everything; the stimulus is derived from a 32-bit seed and could in principle be inverted to it;
the replay proves that the declared program sequence is consistent with the record, not that nothing could have leaked. On a board
the physical separation of host and executing side adds no automatic hiding either — the same stimulus-to-seed limitation stands,
and who executes the target configuration, which programs can see it and how it is isolated are open design questions of 2c.

**The task digest.** `sha256` over the canonical JSON of the public fields (label, version, addresses, base genome, the two stimuli,
masks, targets, weights) **plus** `target_source_sha256` — the digest of the canonical pair of setup observation records (per record:
the configuration digest of `g*`, the stimulus digest, the trace digest, the provenance digest). The private record's own digest is
written in the pair index beside the task digest; the arms' results bind the task digest only.

**Setup and persistence.** Per pair, before any arm starts: (1) the public stimuli, masks and weights from the landscape seed by the
public rule; (2) `g*` by the rule above; (3) **before the first target call** the pair identity (seed, pair index), `g*` and the
planned setup (the two stimulus digests) are persisted as `task_setup.json` with status `in_progress`; (4) the search-stimulus target
observation through the **same execution port** as every observation, phase `target`, and **immediately on return** its raw trace
and provenance saved (`target_search.json`); (5) only then the holdout-stimulus target observation, phase `target_holdout`, saved on
return (`target_holdout.json`); (6) the `PublicTask` formed, its digest and the private digest written, the setup status `complete`;
(7) the seven arms, each on that one `PublicTask`, base observation first, in the existing order. The two setup observations must
come from one source identity, and every arm's observation source must equal it (a difference is `invalid`, as an input drift is).

**Failure records (no redraw, nothing fabricated).** A pair whose setup began is never recorded as "not started": the pair's planned
record carries the setup state (`in_progress` / `partial` / `complete` / `invalid`) **and the durable ordered prefix** — `task_prefix`,
how many of `task_setup.json` → `target_search.json` → `target_holdout.json` → `task.json` exist, in this order and no other — and
`task_quarantine`, the phase whose *return* was kept in quarantine (or null). The verifier holds a pair's files to exactly that prefix:
a later file never exists without its prerequisites, and a genuine prefix (an interrupt right after any of the four writes, during
either observation, or at either deadline check — including both observations written and `task.json` not yet) re-verifies clean
(the owner's review of 04385ae, R3). A DOMAIN (nothing returned), a `SourceRefusal` raised by the port, or a third port call is
**`invalid`** (§9.1: a contract break). **A returned object that is not a valid target observation is never dropped and never written
as an observation**: a malformed return, a `q` cell that is not 0 / 1 — **a None anywhere in the grid, the init readout included; the
mask does not narrow this check** — or a source identity that is not the expected one (the batch's formal source for the first call,
the first observation's for the second: a drift) is kept **raw** in `target_search.QUARANTINE.json` / `target_holdout.QUARANTINE.json`
with the findings that refused it, the phase, the planted configuration, the stimulus digest, the expected source identity and the
digest of the kept projection (`raw` null and the `repr` kept when it cannot be serialised), and *then* the pair is **`invalid`** with
`task_quarantine` naming the phase (R2 / R4); the same check is made by the record validator and by the offline reconstruction. **What
is kept is the object the port returned**, never a record derived from it — the cell check is type-exact (0.0, 1.0 and true are not the
ints 0 / 1), and a return that only a later layer refuses (the record validator, the defence in depth) is still quarantined as it came
(the owner's review of b29b0fb, C1). The quarantine's context is **derived from trusted inputs and held to them by the verifier**: the
stimulus digest from the plan's seed and the phase, the expected source identity from the formal source (the first call) or from the
retained first observation (the second call) — never null on this path, never its own authority (C3). An interrupt landing after a
quarantine's durable write and before the in-memory state is reconciled from disk like the four setup files: the pair's record carries
the invalid return and its phase, the batch's stop carries the interrupt (C2). The deadline or an external interrupt is **`incomplete`**;
whatever was durably written is kept; no task digest and no arm record is manufactured for a task that was not completed.

**Isolation.** The target observations pass through no arm's ledger and no `learn`: they are pair-level records with their own
offline reconstruction, never a specimen, never in the map, the population, a parent, the champion, the best-so-far trace or the
operator's generator. The holdout target and its trace are not an input to the search, the selection, the map or any tuning, and
measuring them at setup does not make them training data.

**Cost — a design expectation, not a measurement.** Two setup observations per pair, shared by the seven arms; the arms' own counts
unchanged — R / O / X / D / Ω / A0 at `B + 2` observations, F at `B + 23`. These numbers are to be established by the tool unit's
call-count fixtures (fixed small budget, fixture seeds, `port.calls` and `cost` compared) before they are written as facts. K9's and
K10's logical observations, physical port calls and memo hits are recorded as separate quantities; a cache hit is never counted as a
physical call.

**Replay.** The verifier rebuilds the task from the retained setup records and re-executes the two target observations through the
replay port against the recorded traces — the fabric is never asked again — then replays every arm as today; every arm's task digest
must equal the pair's. The observation-authenticity limit of §5.3 stands: a clean replay shows consistency with the record, not the
physical truth of the target.

**Non-triviality — read, not measured again.** Per pair the harness records whether the target's search-stimulus trace equals the
R arm's existing base observation under the same stimulus (`target_equals_R_base_search_trace`), from records that already exist;
**no base observation is added**, and no holdout-base comparison is required in this version (the search-base trace is never
substituted for it). A pair whose planted configuration is the base or equivalent to it stays in the planned S and is counted with
every other pair; no non-triviality threshold is set from the gate-1 values; K1's two-median condition (§9) is the aggregate guard
and is unchanged.

**The holdout's two axes.** (a) *Held-out-stimulus behavioural consistency*: the champion's holdout trace against `g*`'s holdout
trace — a research quantity, reported with no threshold (§9), which does not by itself show that a unique configuration was
identified or that anything generalises; (b) the *whole-site engineering holdout* of 2c (the site instance held back) — a different
axis, not exclusive with (a). The holdout target is fixed at setup, before any search; reachability of the search ceiling by `g*`
says nothing about the holdout ceiling being reached by a champion.

**Influence, disclosed.** This contract was motivated by the descriptive record of `b4-gate-1` (Ω − R negative at every budget;
every arm's median 41 at B = 256; the best observed score 51; the holdout at chance), by `b4-sim-3`, by the two scope drafts and by
the owner's rulings of 2026-10-20; the table of what drove which choice is
`evidence/b4/unit_protocol_v2_design_2026_10_20/README.md` §4. None of that record validates this contract, and no number from it
sets a threshold here.

### 7.2 task-v0.3 — the slice-wide control stimulus (DRAFT v0.3.0; the owner's ruling of 2026-10-27; implemented by the task-v0.3 revision unit)

**Standing.** task-v0.3 is task-v0.2 with **one change**: the stimulus rule, so that every step the task produces is realisable on the
certified site, where the eight storage elements share **one CE pin, one SR pin and one CLK pin** (`docs/b4_carrier_v2.md` §0; AMD
UG474). The planted target (T-i), the executing side's input (H), the setup and persistence, the failure records, the isolation, the
cost, the replay, the non-triviality record and the two holdout axes of §7.1 apply **unchanged**. It is a revision made for a physical
reason, not for a result: no record of `b4-sim-3`, `b4-gate-1` or `b4-sim-4` is corrected, compared or re-judged by it, and no map
benefit is expected from it — K9's coverage and the search's behaviour under the new stimulus are to be measured, not assumed.

**The stimulus rule (fixed before any draw; `b4_landscape.STIMULUS_RULE`).** Per `set` step, from the task's generator in this order:

1. `ce` — **one slice-wide value**, CE high with probability **1/2** (`uniform(2) == 0`);
2. `sr` — **one slice-wide value**, SR high with probability **1/4** (`uniform(4) == 0`), the draw independent of `ce`'s;
3. `d` — `d` stays a per-element uniform 8-bit draw (every element has its own D input through its LUT).

The draw order is `ce`, `sr`, `d`. Each control value is **broadcast** over the eight elements in the common 8-bit grammar —
`0xFF` when high, `0x00` when low (`b4_landscape.broadcast`): the step's `ce` and `sr` fields carry the broadcast vector, which is the
only form of those fields task-v0.3 ever produces. K = 6 search steps / 8 holdout steps, the two level steps, the mask (every readout
cell after the init step), the weights (all 1), the holdout salt and the two level steps are task-v0.2's. The shared control pins do
**not** merge the eight elements' INIT / SRVAL into one value: those sixteen per-element bits are drawn, planted and decoded exactly as
before. The previous rule (task-v0.2: `ce` a per-element uniform 8-bit draw, `sr` each element with probability 1/4) is kept as
history in the machine table (`task.stimulus.previous`) and in the observation contract 2.2; it is consumed by `b4-sim-4`.

**The common grammar, the model's input contract and the carrier mapping.** The 8-bit `ce` / `sr` vectors are the common grammar of
the model (`b4_ff_model.validate_step`: ints in 0..255), of the observation contract (2.1: "one bit per element") and of the
carrier's `STEP_IN` word (`host/b4carrier_regmap.step_word`: `d` bits 7:0, `ce` 15:8, `sr` 23:16, `clock` 24). task-v0.3 changes none
of them; it **produces only the two broadcast values**. Under a broadcast vector the model's per-element evaluation (`_ce_ok` /
`_sr_active` reading bit *i*) gives every element the same control value — the slice-wide semantics — so the model's state machine
is **not rewritten**; the unit holds this by a test that runs the formal model against a slice-wide twin (one control bit per step,
through the model's own decode and flags) on sampled configurations of the whole domain and the task's own stimuli, and shows where
the two part: a per-element vector, which the task no longer produces. The carrier applies a step only when `ce` and `sr` are each
uniform (`realisable`): under task-v0.3 that refusal is an **invariant the task never hits**, kept in the carrier as accepted (the
RTL, the register map and the record layer of `bf17574` are unchanged by this unit).

**Held, not assumed.** `b4_landscape.stimulus_findings(stimulus)` names any set step whose `ce` / `sr` is not a broadcast (and every
other shape defect: an init step anywhere but index 0, a clock outside 0 / 1, a `d` outside 0..255, a bool); the record validator of
`task.json` (`b4_sim_schema.task_findings`) and the offline reconstruction (`b4_target.setup_findings`, on the public parts re-derived
from the plan's seed) call it on both stimuli of every pair, so a task record of the previous shape, or any tampering toward it, is a
finding — never a silent acceptance.

**Ceiling and reachability, kept apart.** The ceiling is the **count of scoring cells** — 64 for the search stimulus, 80 for the
holdout — verified from the mask the generator writes (every readout cell after the init step, weight 1). That the **planted
configuration** reaches the ceiling on its own trace is verified **per pair** by the setup reconstruction (the target is that trace; a
None cell refuses it under T-i); that a **search** reaches it, that the base is not already the target, and interaction are not
guaranteed and are recorded (K1, the non-triviality record of §7.1), never arranged by choosing seeds. A contradiction between the
rule above and any of these — found while implementing or measuring — is to be named and reported, never resolved toward a better
number.

**Influence, disclosed.** The two probabilities, the broadcast and the draw order were fixed by the owner's ruling of 2026-10-27
before this unit drew anything. The SR probability 1/4 equals the per-element SR rate of task-v0.1 / v0.2 (one user SR operation
inside the sequence, now at the slice level); the CE probability 1/2 is the uniform choice for a single control bit. **No K9 coverage
value, Ω − R value, curve or per-address record of `b4-sim-3`, `b4-gate-1` or `b4-sim-4` was read in choosing them**, and none sets a
threshold here. The unit's tests use the already-exposed seeds of §9.2 only; no production value is derived.

## 8. Controls

All on the same seeds and rows, the form of B2 §7 / §7a and B3 §9:

| control | what it is | what it shows |
|---|---|---|
| **R** random-safe | the engine with the uniform operator over the universe | the baseline |
| **F** frozen self-map | the engine consulting a map the FF cartographer built and froze | the search benefit of a correct map (B2's claim, re-asked) |
| **O** online self-map | the map updated from every specimen (B3's arm) | whether updating pays on this class |
| **X** relabelled addresses (X-A) | O with the cartographer's input transformed: before the base observation a derangement π of the addresses is drawn ONCE from its own control generator (B3's Fisher–Yates-with-rejection rule; every attempt recorded; never the operator's generator, never redrawn or rejected after anything is learned); X's cartographer ingests each specimen with the genome's bits relabelled through π and the q grid untouched, so every seen effect is credited to the wrong address; the shadow ingests the true genome and the contract is checked in full after EVERY ingest (`b4_carto.isomorphic_addresses`: X's relation at π(a) equals the shadow's at a — cells, presence, pair counts, contexts, evidence references — with the version, multi-bit and specimen counts); the ledger keeps the TRUE genome, the transformed input is reconstructible from π. A difference is a **control failure** — its own event, not DOMAIN, not a refusal, not a result: the exposing observation stays in the ledger, scored and counted (a search child among the pending children); after it nothing is drawn, observed, selected or learned; the replay must reproduce it or names it. **What the transformation does not guarantee:** a derangement does not guarantee a changed partition (swapping within every pair and rotating the slice-wide group has no fixed point and maps every group onto itself), so the **residual structure** (`b4_carto.residual_structure`: `partition_preserved`, `groups_moved` = the true groups that are not, as address sets, groups of X's partition) is computed once at the end and REPORTED beside X's rows — never read during the run, never a reason to redraw or to select. The lane permutation of 2b-2 is not an arm: it stays as the cartographer's symmetry test (`permute_grid` / `isomorphic`) | a wrong online map does not profit — evidence under the stated null, its strength per run read with the residual structure, not a logical proof |
| **D** shuffled map | **the frozen `MapView` that the SAME seed's F arm learned from its 21 single-flip probes over the slice's configuration-bit addresses**, passed ONCE through `b4_carto.shuffled_view` with its parent provenance kept — *not* a shuffled oracle view. That one view is handed to the frozen arm (`run("F", …, view=…)`): nothing is relearned, and no later result may be consulted to pick the map. D is a host control and may reuse F's probe artefacts, but its logical cost is listed separately as the 21 probes obtained once; its search comparison is aligned with the others at the same `B` | a wrong frozen map does not profit |
| **Ω** oracle map | F with the certificate-derived map (`b4_carto.oracle_view`) — host simulation only, never on the board (§2); the view is marked `privileged` and Ω is a **grouping reference**, not a proved global bound or optimum of the search | the headroom against a certificate-derived grouping (B2 G4) |
| **A0** address-only baseline | what address structure alone predicts (`b4_carto.address_only_view`; B1's guard) | the map carries more than addresses |
| T / W (optional) | train-membership-only and within-train scramble (B2 §7a) | grouping versus membership, if the preregistration asks |

Ω, A0 and D are given views on the frozen arm; **none of them is ever handed to the main R / F / O / X runs**.

**The two control generators are fixed before any observation** (the owner's ruling of 2026-10-18 §2), each from the
pair's own seeds, as UTF-8 decimal text with no spaces, and each driving its own generator so that neither the task's
nor the operator's stream is consumed:

```
X control seed = int.from_bytes(sha256('b4-x-control-1|<landscape_seed>|<operator_seed>').digest()[:4], 'big')
D shuffle seed = int.from_bytes(sha256('b4-d-control-1|<landscape_seed>|<operator_seed>').digest()[:4], 'big')
```

A coincidental collision between the two values is recorded, never redrawn. X keeps every attempt of the derangement
rule itself (§8's X row); D uses an ordinary shuffle, which **may** leave the partition unchanged — the permutation it
applied and the residual structure are recorded, and a residual is never a reason to redraw.

## 9. The discriminability gate — criteria with their methods and their fixed thresholds

The gate is unit 2b's simulation; this section fixes **what is computed and how** and, since unit
2b-3 (the owner's ruling of 2026-10-18), **every threshold**. The thresholds were written here
before any exploration or gate run of this class. They are fixed engineering research criteria,
chosen in advance: no number below is claimed to be empirically guaranteed, statistically
calibrated, or valid for silicon, and a criterion that fails under valid complete data is
reported as a failure, never retuned. The B3 rule applies verbatim: "if any threshold is changed after the first gate run, the
change is recorded as a revision of this document with the reason, and the gate is re-run and
re-reported under the new commit — never silently" (`docs/b3_architecture.md` §9). **A
threshold is never derived from the run it judges.**

**The primary and the secondary statistic, and the accounting (B3's, named here so that 2b
cannot pick):** paired by landscape seed *r*, the **primary** `Δ1_r = best_O(r) − best_R(r)` at
`B*` under **search accounting** (R and O charged nothing; the online arm pays its map cost in
time, not in evaluations); the **secondary outcome** `Δ2_r = best_O(r) − end_to_end_F(r)` at
total budget `T = B*`, F's own best-so-far trace charged the mapping cost of the frozen map's
build — **21 probes, one per address of the slice's configuration-bit universe** — from the same
F run: at `T ≤ 21` the value is F's observed base score, marked *mapping-in-progress* because the
search has not begun; at `T > 21` it is F's best-so-far after its `T − 21`-th search evaluation. A
probe candidate is never read as a search champion and a prefix cut short by a terminated run is
never filled in. The holdout score never enters a training curve. Δ2 is reported with no threshold
(`docs/b3_architecture.md` §9). The
decision statistic for each is the one-sided exact sign test at α = 0.05, ties excluded from
*n* and counted (`b2_gate.sign_test_p`, by copy): its H1 is **P(Δ > 0 | Δ ≠ 0) > ½** — the
conditional form is what the copied function computes; an unconditional P(Δ > 0) > ½ is not equivalent once ties
are excluded from *n*. With every pair tied there is no evidence either way and the function returns p = 1
(B2's rule); the conditional probability is never filled in as 0. The bootstrap of K2 resamples all S pairs,
ties included. The frozen arm's own benefit over R
(`best_F − best_R`, B2's primary) is reported next to Δ1 as the dose the online arm approaches, and
it carries **no significance threshold of its own**; K3 and K4 below do use it as a comparison
reference, including the condition that its mean is positive, and those conditions are stated there
rather than hidden behind the word *reported*.

| id | criterion | method (fixed) | threshold |
|---|---|---|---|
| K1 non-saturation | `percentile(best_Ω(B*), 95) < 64` (the task's ceiling, §7) **and** `median_r(best_R(B*)) > median_r(base_r)` — two medians compared, *not* `median(best_R − base) > 0`; the percentile is B2's linear interpolation (`b2_gate.percentile`, by copy) | B2 G1's computation | holds / fails (no fraction) |
| K2 not a definitional lock | the **population** variance of {Δ1_r} at `B*` is > 0; there exists one grid budget B at which both `positives(Δ1(B)) > 0` and `negatives(Δ1(B)) > 0` (one condition, within one budget); **and** at `B*`, with size `N(B*)`, the same one-sided sign test — H1: P(X − R > 0 | X − R ≠ 0) > ½, the direction in which X would profit — applied to the S values of X − R does **not** reject H0 in **≥ 90 %** of 1 000 bootstrap experiments (`b2_gate.bootstrap_reject_rate` by copy, α = 0.05, rejection at `p ≤ 0.05`, `random.Random(7)`; ties do not enter the sign test's effective *n*, yet the tied pairs stay in the resampled population). Every X run's residual structure (`partition_preserved`, `groups_moved` / `groups_true`) is reported in full, never used to drop or re-pick a run | B3 H2, in full | ≥ 90 % non-rejection |
| K3 wrong maps do not profit | `mean(F − R) > 0` **and** `mean(D − R) ≤ 0.10 · mean(F − R)`; `mean(O − R) > 0` **and** `mean(X − R) ≤ 0.10 · mean(O − R)`; D's and X's one-sided sign tests over the S pairs at `B*`, each with H1: P(control − R > 0 | control − R ≠ 0) > ½ (the direction in which a wrong map would profit), not significant (`p > 0.05`). A negative numerator passes the inequality and is **not** made absolute; a zero or negative denominator means the ratio condition cannot be read as satisfied — the row fails and says so. X's residual-structure counts are reported beside its numbers (§8) | B2 G3 / B3 H3 | 10 %; `p > 0.05` |
| K4 headroom against the certificate-derived grouping | `median_r(best_Ω(B*)) ≤ 0.90 · 64 = 57.6`; `mean(Ω − R) > 0` **and** `mean(F − R) ≥ 0.50 · mean(Ω − R)`. The 50 % is this unit's advance criterion, **not** a known attainable effect: Ω is a privileged grouping reference (§8), not a proved global bound | B2 G4 | 57.6; 50 % |
| K5 effect, power, N | paired Cohen's d of {Δ1_r} at `B*` **≥ 0.5**; `N(B)` by `b2_gate.required_pairs`'s **complete ascending scan over every integer from 8 to S** (no bisection, no skipping; α = 0.05, bootstrap power **≥ 0.90**, 1 000 experiments, `random.Random(1 + N)`); the sign test by `b2_gate.sign_test_p` — all three **by copy into the B4 namespace with their digests recorded**, never by import across the pinned boundary; `N × 3 × B* ≤ 4 000` **search evaluations** | B2 G5 / B3 H5 | d ≥ 0.5; power ≥ 0.90; cap 4 000 |
| K6 no fixed-seed lock | **S = 200** and **N ≥ 8**; the gate's seeds derived once by §9.2's formula with the complete exclusion set. S is the number of seeds planned, never the number that completed | B2 G6 / B3 H6 | S = 200; N ≥ 8 |
| K7 the map is a map | (a) **zero recomputation mismatches**: from the arm's own ledger, the single-flip pairs are recomputed — affected cells, presence, pair counts, contexts, evidence references, the map version and the map at that budget — and must equal what the run recorded. This is an internal-consistency check, not a claim about semantic truth. (b) coverage on **arm O's `B*` search prefix** — the ledger records from the base observation through O's `B*`-th search evaluation inclusive (arm O has no probe phase, so these are O's first `B* + 1` records), and the map state is the one the cartographer reached after ingesting exactly those records; nothing from after `B*` and nothing from the holdout; the snapshot is rebuilt from the true ledger prefix without re-running any candidate: `median_r(#addresses whose state is not unknown) ≥ 11` of 21. Per seed the 21 addresses are reported in the four states `unknown` / `effect_seen` / `no_effect_seen` / `context_dependent`, summing to 21; *not unknown* means the latter three and implies **neither** a usable grouping **nor** a decoded semantic. F's frozen post-probe map and the other controls are reported separately and never substitute for O's ≥ 11. The difference between the certificate-derived partition (Ω) and an observed partition is reported as a **diagnostic with no threshold**: the cartographer groups by the elements an address was *seen* to affect and puts every multi-element address in one group, so a slice-wide configuration bit that moved one element under one stimulus lands beside that element's address — that is not a defect, and the model never promised the two partitions agree. X's own relations are judged against its shadow under the X-A contract (§8), never against the certificate partition | B3 H7, extended by the `unknown` rule of §5.2 | 0 mismatches; median ≥ 11 |
| K8 ledger replay | for **every** run actually executed (R / F / O / X / D / Ω / A0): the replay reports no finding, the recorded q grid recomputes the recorded fitness, X's shadow isomorphism holds and the source-identity / fixture boundary holds. A broken tool contract is `invalid` under §9.1 and is never packaged as an ordinary landscape failure | B3 H8 + §5.3 | holds |
| K9 observability | computed on the fixed host-only comparison set of **§9.3** (the stimulus of `task-v0.1` as generated, the whole public `q_after` trace including the init readout, no champion and no holdout): (a) **≥ 90 % of all S seeds** have, for each of the seven semantics, at least one applicable address-and-background pair whose two readouts differ; (b) per semantic, the **median over all S seeds of the coverage fraction** (distinguishable applicable pairs / all applicable pairs) **≥ 0.50** — per semantic, never averaged across the seven. A semantic with an empty denominator for a seed is *not assessable* for that seed and is never recorded as 100 %; if a semantic is not assessable for even one seed, its median is *not assessable*, condition (b) is not met for that semantic, and the number of such seeds is reported. The seven semantics are those of §5.2: `ff_init`, `ff_srval`, `ce_mode`, `sr_mode`, `sr_kind`, `storage_kind`, `clock_mode`. `ff_init` is one of the seven and counts in (a) and (b) exactly as the others do; in addition its row carries the flag *conditional on A8* (§5.2), because a difference at the init readout rests on the model's atomic-initialisation abstraction **(b′) — v0.2.0 (DRAFT; the judged quantity once the tool unit of v0.2.0 is accepted — until then the table of record is v0.1.16 and judges (b)):** for `ff_srval` and `sr_kind` the **conditional coverage under SR-driven backgrounds** — `applicable_conditional = applicable_all_panel AND sr_mode_driven_at_both_endpoints` (§9.3 clause 6; the latch / x5FF exclusions of the all-panel rule stay in force, and a new flag never overwrites an old exclusion), the SR-tied-low pairs named and removed from (b′)'s denominator with the reason `sr_tied_low` — per semantic the median over all S seeds **≥ 0.50**; for the five other semantics the conditional applicability IS the all-panel applicability; (a) unchanged at ≥ 90 %, from the all-panel record. (b) over all panel backgrounds is kept beside (b′) as a description, recomputed from the same retained raw grids under the old applicability — never filled in with model-derived zeros for unobserved pairs; the two applicabilities, denominators, exclusion reasons, counts and fractions are recorded separately and are each recomputable offline. The old (b) judged v0.1.16 correctly by its own definition; (b′) is a different estimand, not a correction of it. The host decode and either applicability never enter the engine or the cartographer. **Implemented** (the v0.2.0 tool unit): `b4_k9.applicability` records both (`applicable` / `applicable_sr_driven`), `b4_k9.summarise` writes both records, the summary and the judgement read (b′) as `judged_estimand = conditional_sr_driven`. **v0.3.0:** the comparison set, the panel, both applicabilities and both thresholds are unchanged; the stimulus of clause 1 is now task-v0.3's (slice-wide `ce` / `sr`, §7.2, §9.3 clause 7), under which the per-address coverage of `ff_srval` / `sr_kind` is a **different quantity** from the one measured under per-element SR patterns — the `b4-sim-4` record is not reinterpreted, and the v0.3.0 values are to be measured by the next exploration, never carried over | new; §5.2 — the same wording as A2 | ≥ 90 % of seeds; median coverage ≥ 0.50 per semantic |
| K10 real interaction | τ = **2 fitness score units** (the task's weights are all 1, so two scoring cells of 64). For each landscape seed, two fixed background configurations — `genome0 = 0` and `genome1 = Rng((landscape_seed ^ 0x4C0A4E55) & 0xffffffff).uniform(1 << 21)`, the first `uniform` call of that new generator, independent of the task, operator and control generators, drawn once and kept even if the two backgrounds coincide — and in each background **all 210 unordered pairs** of the 21 configuration-bit addresses: the four-corner index `I_ab = f11 − f10 − f01 + f00` with every other bit, the initial state and the stimulus held fixed across the four corners (`b4_stats.four_corner`), recording the background, the four corner configurations, their scores and `I`. `max|I|` per seed is taken over all comparable values of both backgrounds. Outcomes: **interacting** when `max|I| > 2` (exactly 2 falls in *nonzero below threshold*), *nonzero below threshold*, *no interaction seen among the tested comparisons*, *not assessable*; all four counts and the comparable / not-comparable counts are reported, and the criterion is **interacting seeds / all S ≥ 0.50** (not-assessable seeds stay in the denominator). Comparability here is **comparability inside the model's domain under hypothesis v0.3** — it is *not* a statement that a corner is buildable, writable or safe as a bitstream on a device; if 2c needs composition legality, that is a separate frozen condition and this result never stands in for it. Under hypothesis v0.3 every assignment of the 21 bits is in the domain (`ff_behaviour_v0.3.json`, the domain rule), so a corner can be *not comparable* only through a DOMAIN refusal: the expected not-comparable count is 0, and a DOMAIN refusal — the only way a nonzero count can arise — is `invalid` under §9.1, never absorbed as *not assessable* or as *not comparable* | new; §7 | τ = 2; ≥ 0.50 of S |

**The budget grid and `B*`.** The grid is `G = {8, 16, 24, 32, 48, 64, 96, 128, 192, 256}` with
`B_max = 256` — multiples of λ = 8 over a universe of 21 configuration-bit addresses, where one
generation of the (μ, λ) = (4, 8) engine costs 8 evaluations. `B*` = the grid budget with the
smallest cost `N(B) × 3 × B` (three arms R, F, O charged at `B`) **among the budgets at which K1
holds and `N(B)` exists**, ties to the smaller budget; every other row is evaluated at `B*`, and
`B*` is never re-chosen to let another row pass. K1 is evaluated at every grid budget to decide
eligibility, and its row above restates it at `B*`. Where a row writes `N` with no budget argument,
`N` means `N(B*)`. A budget at which `required_pairs` has no
solution is not eligible; if no budget is eligible, `B*` does not exist, the budget rule FAILS,
every row that depends on `B*` or `N` is marked *not assessable*, the gate cannot PASS, and
neither `B*` nor `N` is invented. The diagnostic rows (B3's H9 form) are the preregistration's to
add. A row that fails is reported, not tuned.

**What the cap of 4 000 is and is not.** `N × 3 × B* ≤ 4 000` bounds the **search evaluations of
the planned three-arm main experiment** and nothing else. It is not a bound on a single board
session, on time, on total observations or on total records. F pays 21 probes per pair on top; a
complete R or O run calls the observation boundary `B + 2` times and a complete F run `B + 23`, so
the main arms' base observations come to `3B + 27` per pair, before any board-side baseline,
audit, transport or retry that is not designed yet. B4 has no measured rate of its own: the
session split stays with unit 2c and its qualification, and B3's measured rate is never borrowed
as a guarantee for this class. An eligible combination under the cap is, for example,
`N = 16, B* = 64` → `16 × 3 × 64 = 3 072`.

### 9.1 Incomplete runs, invalid runs, and no solution

**A gate verdict needs every planned run complete.** For every planned arm and seed the run goes
to `B_max` and the existing holdout: `completed` is the boolean `True`, `search_completed` is
`True`, the search evaluations and `len(best_trace)` are both exactly `B_max`, and the refusal and
`control_failure` fields are `None`. The curve at each grid budget is the measured prefix of that
one complete run. All planned runs complete is a **precondition** for any PASS verdict.

**Contract breaks are `invalid`, not results.** A DOMAIN refusal under the formal v0.3 hypothesis,
any other refusal, a control failure, or a violation of the source-identity or replay contract makes
the batch `invalid`: under the stop rule the run and the prefix it completed are kept as they are,
and the unit halts and reports. Such a break is never dressed up as an ordinary landscape failure.

**No judging by survivors.** A PASS is never computed from the subset of pairs that happened to
finish. Every planned seed stays on the list; a seed that was never started or was aborted is named
as such. No seed is swapped, no value is filled in, nothing is redrawn. A resource limit, a time
limit or an external abort is an incomplete evaluation like any other. Diagnostics may report how
many pairs completed and what they measured, **marked explicitly as not a formal gate verdict**;
the denominator stays all S seeds. Whether the unexecuted runs are resumed is decided separately.

**A complete, valid run with no `N` is an ordinary result.** If `required_pairs` has no solution on
valid complete data, that is a discriminability result about this class — not a tool defect and not
an artefact of incomplete runs; §9's `B*` and `N` rules then apply as written. A threshold that
fails on valid complete data is a FAIL, and no threshold is adjusted in response.

### 9.2 The seed anchor, the control generators and the exclusion set

**The anchor is the formal hypothesis's digest; the label is passed beside it**, never pre-joined
into the anchor (which would put two labels in one string):

```
gate master = int.from_bytes(sha256(utf8('b4-gate-2|' + HYPOTHESIS_SHA256)).digest()[:4], 'big')   # protocol v0.2.0 (b4-gate-1 consumed by its records, 2026-10-20)
exploration = the same formula with the label 'b4-sim-5'   # protocol v0.3.0 (b4-sim-4 consumed by its records, 2026-10-21; b4-sim-1 / b4-sim-2 retired, 2026-10-19; b4-sim-3 consumed, 2026-10-20)
v0.2.0 (the history): the label 'b4-sim-4' with the same formula and the same anchor (consumed)
v0.1.16 (the history): the labels 'b4-gate-1|' and 'b4-sim-3' with the same formula and the same anchor
HYPOTHESIS_SHA256 = 59948f9be3b4516547fbf039556d4aa6a4afd0b2dda2324619e4d40ef0651ed8
```

Binding the anchor to the hypothesis's digest makes it auditable, keeps it stable when a commit is
re-made, and ties the seed set to the model being judged: a different hypothesis is a different
anchor and therefore a different gate. This unit fixes the formula only; **no seed value is
generated here and no candidate result is read.** Pairs are drawn by a copy of B2's `pair_seeds`
algorithm: every seed is a 32-bit value from one generator stream off the master; the exclusion set is
**one pooled set of integers** — every value in every seed-bearing field listed below, whatever its role
there (landscape, operator, master or control seed), together with B4's exposed values — and it is
applied to **both** positions of every drawn pair; a draw whose two values coincide, or whose value
is in the pooled set or was drawn earlier, is skipped and never kept. The two control generators of
§8 are separate from this derivation.

**The exclusion set, file by file** (path, the field that carries the seeds, and the digest of the
file as of this commit):

| source | seed-bearing field | sha256 |
|---|---|---|
| `host/b2_search.py` | `EXCLUDED_SEEDS`, the line's frozen list of 20 values | `3acb04714a6c677708892d171f6a418e6de7627210e2ec6ad65158db51eab1cf` |
| `manifests/b2_manifest.json` | `seeds.master_seed`, `seeds.pairs`, `seeds.excluded_frozen_sets` (each set's `master_seed`), `qualification_plan.master_seed` | `aec84514ff29dda7957d46d650a370e155f6dc60a281b992e148f8a0fae6c4c0` |
| `manifests/b3_manifest.json` | `seeds.master_seed`, `seeds.pairs`, `qualification_plan.master_seed` | `258bb14c4b3ba1a3d33741f23b1663f563de64da800843d30c8a615e2f128628` |
| `evidence/b2/gate/gate_report.json` | `seeds` (schema `b2_gate_report` 1.0.0) | `571196bd509e5eb09897d206a634b508655bb42f293be7eeaf7fba8d4c514c43` |
| `evidence/b2/gate/raw_F1.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `b821c24998dece562026d41c094509da98cfd5430b099ea52ec35dc44050e0bf` |
| `evidence/b2/gate/raw_F2.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `6194ed690afd5107a76cd081f158a174d2147c3f364e331e0c58ebba74dcab5f` |
| `evidence/b2/gate/raw_F3.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `8a751a23c7e3088f85f39f2da32a175648623861d525099dcfb05c93eb8111a9` |
| `evidence/b2/gate/v0.1_2026-09-10/gate_report.json` | `seeds` (the superseded v0.1 gate run) | `d547144fce433078531b125937b946c2df94ad69d5c44f7ba37c45976984e4ce` |
| `evidence/b2/gate/v0.1_2026-09-10/raw_F1.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `ffb0bf396f975585cc9bd88f7500ea188612ab2e8a5e9f59076dbd675dcab532` |
| `evidence/b2/gate/v0.1_2026-09-10/raw_F2.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `859b96a03cdccd23b116a0b64e41f5f3c091ba85da4c13c404027c8b77ca7522` |
| `evidence/b2/gate/v0.1_2026-09-10/raw_F3.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `f37ae4e4b38b4b9508c424bf0cedc85f1b5f88b1c3b01f75cdc2c90047fce21d` |
| `evidence/b2/gate/recomputed_2026_09_10/gate_report.json` | `source.seeds` (schema `b2_gate_recomputation` 1.0.0) | `997317fb8763925ffcaa1ae63700471165e2f804c527648205a31622d02f625c` |
| `evidence/b2/gate/recomputed_2026_09_10/controls_report.json` | `source.seeds` (schema `b2_gate_controls` 1.0.0) | `4a5042e283069f7112cf45c2dbbbb913ef81ea7d5fede97450c2d6b4084c2f89` |
| `evidence/b2/gate/recomputed_2026_09_10/raw_controls_F1.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `bddc7ad93003e787cebe5fb569131d161b05d76f931212fe4e52f658bc2e4aa6` |
| `evidence/b2/gate/recomputed_2026_09_10/raw_controls_F2.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `7948e974be96fd983e5155bdbb72f0d97bc646dc5a0bfdb1cda22c3188f33ed8` |
| `evidence/b2/gate/recomputed_2026_09_10/raw_controls_F3.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `a5ed062f6591acc4fe782a35e8cca1910269145ce8682465f8022c181890d394` |
| `evidence/b2/plan.json` | `seed_derivation` incl. `excluded_frozen_sets` (schema `b2_plan` 1.0.0) | `62dc85934eec02e2fe31a90b336d0fd320d03a4f54bf90537e944ece72458b9c` |
| `evidence/b2/b2q_plan.json` | `seed_derivation` (B2Q pairs) | `3d194d76e083fd4ba3ce3cf0458af65637120fcda6761be36598833dbc659216` |
| `evidence/b2/prediction.json` | `pairs[].landscape_seed` / `pairs[].operator_seed` | `a611b8e03c88fa797e2b9d9c5d10bb97e42c590bc8754f1defccc6c11c9e3731` |
| `evidence/b2/b2q_prediction.json` | `pairs[].landscape_seed` / `pairs[].operator_seed` | `2ada4d5dab7ed08f081aa55bb4b6f138688a326bb859ab5d63f58c16e67b58aa` |
| `evidence/b3/sim/sim_report.json` | `seeds` (schema `b3_sim_report` 1.0.0) | `d9c432f8b797933e26e24a77d33e5884f29c03c2be88e6c59c61bc0af250adf9` |
| `evidence/b3/sim/raw_F1.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `ccf4d24622c7cfb3ee698623047ea461303c603449d47ffb0452f83656b74c53` |
| `evidence/b3/sim/raw_F2.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `953511d7540bbf0a0af7932f5c8c486a03f64d3d68cda576b2ed07f6e4ed4e1c` |
| `evidence/b3/sim_v0.1.1/sim_report.json` | `seeds` (the v0.1.1 simulation) | `dcbaa2a3cf2fe817c77ce24ab4a4250ec4c8a2c171117f55da9d80740e29401c` |
| `evidence/b3/sim_v0.1.1/raw_F1.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `ccf4d24622c7cfb3ee698623047ea461303c603449d47ffb0452f83656b74c53` |
| `evidence/b3/sim_v0.1.1/raw_F2.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `953511d7540bbf0a0af7932f5c8c486a03f64d3d68cda576b2ed07f6e4ed4e1c` |
| `evidence/b3/gate/gate_report.json` | `seeds`, `control_x.seed_x` (lifecycle 1 gate run 1) | `477225f54bb40866abb08df69e6e34341c7516cd7e398e8bb6d0c06c8ae2aa68` |
| `evidence/b3/gate/raw_F1.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `54f9c4fbc0bac8c0bfe1c6ce203f8848367d201b85b610e40c031f96c1746ed6` |
| `evidence/b3/gate/raw_F2.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `279b08ede52cf73d948f69e1390e2c02c09e417ca8406bb52da78439ff1b3e2d` |
| `evidence/b3/gate_2/gate_report.json` | `seeds`, `control_x.seed_x` (schema `b3_gate_report` 2.0.0) | `8f717b12bdc7258d49145bd47bbcfb8291d2b2a79cad42cb75491a19398fda90` |
| `evidence/b3/gate_2/raw_F1.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `631aac7119dc054b9db835a756e2fbc1f56b4071f027506b13d5a3630c08b0fc` |
| `evidence/b3/gate_2/raw_F2.json` | `rows[].landscape_seed` / `rows[].operator_seed` | `cba55465bde4a35c39cc33ce0a853db4a3db5f9ac85e0ded6d671a87732cbfe5` |
| `evidence/b3/plan.json` | `seed_derivation.excluded_sources` (schema `b3_plan` 2.0.0) | `b202a2800d5934978394ffca7ee8f24d9b2897c953d4f41b1050fed840c81dd1` |
| `evidence/b3/b3q_plan.json` | `seed_derivation.excluded_sources` (B3Q pairs) | `490347f4b3542147581940035a12eb9bb7db7cbd0ad550dd8bfd3e2b68261026` |
| `evidence/b3/prediction.json` | `pairs[].landscape_seed` / `pairs[].operator_seed` | `92b774ea62d290d380e72a4c990b384060db9006cf9160940fb4848ae4a14cf5` |
| `evidence/b3/b3q_prediction.json` | `pairs[].landscape_seed` / `pairs[].operator_seed` | `7eae26509b9488a111257c112c5cf90e9cc8f6e34311af837c79ccc40245ec27` |
| `evidence/b3/plan_trial_2026_09_17/plan.json` | `seed_derivation` (the lifecycle 1 trial, pilot) | `8b6142b06b883baee2e9e8b298635429384279d2be78efab18cd73bdcc3761d2` |
| `evidence/b3/plan_trial_2026_09_17/prediction.json` | `pairs[].landscape_seed` / `pairs[].operator_seed` | `6e45a752bd3db536db0cbea7dcb0e531bb40889fff91f7dc6c28250f44f729b2` |

**The typed reading of the table, and the sets that join it later** (unit 2b-4a, `b4/host/b4_seeds.py`): each file above is
read against its digest through a typed field path — a path that does not resolve, or a leaf that is not an integer in
0 .. 2³² − 1, or a bool, is a refusal by name; counts, versions and timestamps are never read as seeds because no path
points at them. The pooled set is those values, B4's exposed values below, and **every archived exploration set under
`evidence/b4/sim/`** — each run directory's `seeds.json` (its master and every planned pair, whether the batch
completed, was invalid, incomplete, failed, aborted or void), read in path order; a run directory with no readable,
valid seed record (and no record stating that no seeds were derived) is a refusal, never skipped.

**Two label namespaces, one derivation point** (the repair of 2026-10-18, F1). A **production** exploration set carries a
label `b4-sim-<n>`: its master is `sha256("<label>|<anchor>")[:4]` and its pairs are drawn against the pooled set — that
derivation happens in `b4/host/b4_sim.py` for a production label and nowhere else, and it is a formal act of this section
whatever directory it writes to (a hermetic copy under `/tmp` does not make the values fake). A **mechanics fixture** set
carries a label `b4-mech-<n>` (schema `b4_sim_seeds 1.1.0`, `fixture = true`): its pairs are an explicit schedule of values
already exposed under this section (B2's copy and B4's exposed values), it has no anchor and no master, nothing is drawn,
and it can never reach a production set; the harness's own tests use these only, a production label with a schedule or a
fixture label without one is refused before anything is written, and the CLI has no fixture path. A fixture set under
`evidence/b4/sim/` joins the pooled set like any archived set (its values are already in it). **Prior exposure, and its
settlement (the owner's ruling of 2026-10-19):** before the repair the harness's integration tests derived production
`b4-sim-1` sets (S = 2; in one test tree several in sequence, each against the registry holding the previous ones) and one
`b4-sim-2` set, on hermetic copies whose directories were mostly deleted; the author's smoke test before commit A did the
same once; the owner's interrupted re-run of the suite did so again. The records that still existed are preserved in
`evidence/b4/unit_2b4a_repair_2026_10_18/exposure/` (22 seed records, six distinct `b4-sim-1` sets). The settlement:
`b4-sim-1` and `b4-sim-2` are retired — the harness refuses a production derivation under either label before any tree is
read, the registry still reads their archived records, and the old batches are development exposure that counts toward no
sample, population, result or power estimate; the next exploration label is `b4-sim-3`, reserved before any value of it
exists. The **exposure receipt** (`evidence/b4/unit_2b4a_exposure_settlement_2026_10_19/exposure_receipt.json`, schema
`b4_exposure_receipt 1.0.0`, pinned by digest in `b4/host/b4_seeds.py`) is the fourth pooled component: a seed-only
reconstruction from the historical derivation code and exclusion contents of every set the committed recipes could have
drawn, compared with every preserved record, with the control seeds of every drawn pair — each value marked `observed`,
`reconstructed_recipe` or `conservative_superset`; the harness pools it into both pair positions, names it in `seeds.json`
(schema 1.2.0) and the manifest, holds it at every checkpoint, and the verifier binds it. A missing, re-hashed or malformed
receipt is a refusal. The receipt excludes the known and reconstructable exposure; it does not make the historical exposure
record complete — the raw evidence of the deleted runs is lost, and the uncommitted development runs before `edfc93c` are
outside the reconstructed envelope. The anchor formula is unchanged and no set is redrawn.

**B4's own exposed values.** `evidence/b4/sim/` **does not exist yet** — it is named here as the
directory the exploration sets will be archived in, and its absence is not a missing source. That
is deliberately kept apart from a historical seed source that ought to exist: a missing one of
those is refused, never silently skipped. Already exposed on this line, and excluded
conservatively: the landscape seeds **3, 5, 7, 8** and the operator seeds **11, 12, 13** used as
literal arguments in the B4 tests and in the v0.3 mechanism fixing; the X control values **5, 6, 7,
8**; the fabric-fixture seeds **1, 2, 3, 5**; the derangement seeds **5, 6, 9** and the value **1**
that a test finds by scanning for the first seed whose rule needs at least two attempts; and the
single formal base observation made while drafting this unit's scope under landscape seed **7**
(recorded as executed — this line does not claim the model was never run). Excluding exposed values
is a conservative measure; it is not a basis for estimating any distribution.

**Freezing order.** The exploration set is produced once, before any exploration, and archived; it
is never redrawn after a result is seen. The gate set is derived **once**, after every exploration,
failed and void set is archived, from the fixed master and the complete exclusion set; the input
list, the digests and the final seeds are frozen, and once the run has started the exclusion set
may not be changed in order to redraw. Both the anchor and the exclusion set determine the set, so
a fixed anchor is **not** by itself a guarantee against selection bias; the protection is the frozen
input list, the retained record of everything tried, and the owner's review of this commit before
any run. That a derivation is deterministic buys nothing here — a commit can be re-made. Changing
the hypothesis or the anchor does not license a redraw and retry: that needs its own ruling, and the
earlier set and its results are kept.

**v0.2.0: labels, consumption and what the anchor does not carry.** `b4-sim-3` and `b4-gate-1` are consumed by their archived
records under `evidence/b4/sim/` (S = 32, 2026-10-19; S = 200, 2026-10-20) — their 65 and 401 values are in the registry and in the
pooled exclusion of every later derivation (2 625 pooled values at this revision, read from the registry; nothing derived) — and the
tool unit refuses a production derivation under either label before any tree is read (`b4_seeds.CONSUMED_LABELS`,
`ConsumedLabelRefusal`), as it does for the retired `b4-sim-1` and `b4-sim-2`. The names **`b4-sim-4`** (the next exploration) and
**`b4-gate-2`** (the next gate) are the table's labels (`b4_thresholds`, `anchor.exploration_label` / `anchor.gate_label`) and
*reserved names only*: no value of either exists and none is derived by the tool unit; their derivation and execution need their own
rulings. **The anchor formula is unchanged.** The protocol identity of §9.5 is
*not* part of the anchor: the same label under a new protocol would reproduce the same seed set, which is exactly why a new protocol
version must use a new label and why the identity lives in the manifest, not in the anchor. Changing the hypothesis or the anchor
still licenses no redraw.

**v0.3.0: labels (the owner's ruling of 2026-10-27).** `b4-sim-4` is consumed by its archived records (`evidence/b4/sim/b4-sim-4_20261021T065339Z`, S = 32, 2026-10-21; its 65 values
in the registry and in the pooled exclusion of every later derivation — 2 690 pooled values at this revision, read from the registry; nothing derived) and the tool unit
refuses a production derivation under it before any tree is read: `b4-sim-3`, `b4-gate-1` and `b4-sim-4` are consumed (`b4_seeds.CONSUMED_LABELS`). The next exploration label is
**`b4-sim-5`** — the table's `anchor.exploration_label`, a reserved name only: no value of it exists and none is derived by this unit; its derivation and execution need
their own rulings. **`b4-gate-2`** stays the reserved gate name: no value of it was ever derived under v0.2.0, so the same label under this version reproduces
no existing set. The anchor formula is unchanged; the protocol identity (§9.5) is not part of it.

### 9.3 K9's fixed comparison set, written before it is measured

Writing only "90 %" and "0.50" would leave the choice of comparison contexts free after the fact,
so the method is fixed here (and executed by no code in this unit):

1. **The stimulus is the task's own.** Each seed uses the `task-v0.1` search stimulus exactly as
   generated — nothing modified, nothing selected — and the whole public `q_after` trace is read,
   **including the init readout**. K9 measures observational distinguishability, not coverage of the
   fitness mask. A difference visible only at the init readout rests on the model's atomic
   initialisation abstraction and stays conditional on A8.
2. **64 fixed background configurations.** All 32 combinations of the five slice-wide mode bits
   (`ce_mode`, `sr_mode`, `sr_kind`, `storage_kind`, `clock_mode`), crossed with the 16 per-element
   INIT / SRVAL bits taken at all-zero and at all-one. The set is built from the host mapping for
   audit only and is **never handed to the cartographer or the engine as a prior**.
3. **One forced address at a time.** For each real address and each background, that bit is forced
   to 0 and to 1 with every other bit held at the background; identical endpoint pairs are
   de-duplicated, ordered by genome value, and both complete configurations are kept with references
   to their traces. This covers that finite set only — it is no claim about the remaining 19 free
   bits in every combination.
4. **Which readouts may be compared.** A per-element semantic compares only its own element's
   `q_after`; a slice-wide semantic may compare any applicable element. Under a latch the x5FF
   elements' INIT / SRVAL are not applicable and `sr_kind` is not applicable: those are named and
   removed from their denominators. `storage_kind`'s own endpoints may differ by an element being
   present or absent; every other relation needs readouts applicable at **both** endpoints. Value
   differences (0 versus 1) and `storage_kind`'s None-versus-present differences are reported with
   the positions where they occur; separation is never asserted from the decode instead of the trace.
5. **Coverage.** `covered(address, background)` means the pair's two traces differ in at least one
   readout within that scope. Per seed and semantic, coverage = distinguishable applicable pairs /
   all applicable pairs, each pair weighted equally; the per-address applicable and covered counts
   and their ratio are also reported, as are the addresses and backgrounds with no coverage at all.
   An empty denominator is *not assessable* and is never recorded as 100 %. A semantic's positive
   control is one applicable address-and-background pair that is distinguishable, and only a seed
   with all seven counts toward the 90 %. K9 (b)'s median is over all S seeds; a seed for which the
   semantic is not assessable makes that semantic's median not assessable (K9).

6. **Conditional applicability for the SR semantics (v0.2.0, DRAFT; the owner's choice 4 of 2026-10-20).** For `ff_srval` and
   `sr_kind` a pair is *applicable under (b′)* only when both endpoints decode `sr_mode = driven` (the `sr_mode` address is
   slice-wide, so the two endpoints of any other address's pair agree on it); under `sr_mode = tied_low` the model's
   `sr_tied_low_when_not_driven` leaves SRVAL and the SR kind no path to the trace, and such a pair is named and removed from
   (b′)'s denominator with the reason `sr_tied_low` — exactly as the latch rule of clause 4 removes the x5FF elements' INIT / SRVAL
   and `sr_kind`: `applicable_conditional = applicable_all_panel AND sr_mode_driven_at_both_endpoints`. The **old applicability of
   clauses 4–5 is kept and recorded separately** (its own `applicable` flag and reason, the latch / x5FF exclusions included); **every
   pair of the fixed set has a record, and the set of pairs OBSERVED is the one the old applicability requires** — the conditional rule
   adds no observation and removes none; (b) and (b′) are both computed from the same retained raw grids of the pairs actually observed,
   and an unobserved pair is never filled in as `covered = false` from the model; the comparison set, the denominators' definitions and
   the query contract are unchanged. For the five other semantics the conditional applicability equals the all-panel one, and a new flag
   never overwrites an old exclusion.

7. **The stimulus of clause 1 under v0.3.0 (the owner's ruling of 2026-10-27).** "The task's own stimulus" is task-v0.3's (§7.2): per
   set step one slice-wide CE and one slice-wide SR value, broadcast over the eight elements. Clauses 2–6 are unchanged — the same 64
   backgrounds, the same 1 184 forced pairs, the same two applicabilities read from the decode of the endpoints, the same scopes and
   denominators. What differs is the quantity: under a slice-wide SR the eight elements see one SR level per step, so a per-address
   `ff_srval` / `sr_kind` coverage under v0.3.0 is **not the same estimand** as under per-element SR patterns (v0.2.0's `b4-sim-4`
   record, 1/4 per element); the two are reported under their own versions and never compared, pooled or corrected against each
   other. Which semantics are distinguishable under the new stimulus is to be **measured** by the next exploration, not predicted here.

This set is an advance host-side engineering diagnostic. It is **not** the same contract as unit
2c's board stimulus, and it says nothing about what is legal or safe to write to a device. An
uncovered semantic is never repaired by adding one favourable background afterwards; changing the
set requires a new version of this section, the reason, and a complete re-report.

**The two records.** Per pair of the fixed set: `applicable_all_panel` with its reason, `applicable_sr_driven` with its reason,
`covered` from the traces; per semantic and per address: both denominators, both covered counts, both fractions, and the list of
excluded pairs with their reasons; per seed: the seven medians' inputs under both definitions. The owner's choice 4: the judged row
in v0.2.0 is (b′); (b) is the description beside it; neither is a correction of the other.

### 9.4 The engineering go / no-go policy for an exploration (v0.2.0, DRAFT, the owner's choice 5 — `b4-sim-4`, decided; v0.3.0 — the row for `b4-sim-5`, below)

A **cost policy** for spending the production gate's budget — not a significance result, not a scientific impossibility, not a
gate verdict, and not an authorisation of anything (the gate's execution is its own ruling, as it was for `b4-gate-1`). Fixed here,
before the exploration, and not changed after it:

| item | rule |
|---|---|
| precondition | all **32** planned pairs complete, the batch neither `invalid` nor `incomplete`, every source / tool contract held; otherwise **no decision** — stop and report (§9.1 comes first) |
| the budget | **B = 64** of the grid, named here; the ten budgets' descriptive values (mean, Cohen's d, positives / negatives / ties, the sign test's p) are all reported in full; no other budget is picked afterwards |
| statistic 1 | the one-sided exact sign test (`b4_gate_stats.sign_test_p`, by copy) on **Ω − R** at B = 64 — H1: P(Ω − R > 0 \| Ω − R ≠ 0) > ½; ties excluded from n, counted and reported |
| statistic 2 | the seven per-semantic medians of K9 **(b′)** over the 32 seeds |
| **go** | positives > negatives at B = 64 **and** p ≤ **0.20** **and** all seven (b′) medians ≥ 0.50 |
| **no-go** | anything else with the precondition met: the exploration is archived as a result; the next step — a different grouping shape, a different operator, a different stimulus, or stopping — needs its own argument and its own ruling |
| what a go means | that the fixed certificate grouping with the fixed operator showed a positive signal on this task at one budget, and that the conditional coverage was not below threshold — a proxy (Ω is not the upper bound over maps and operators), good enough to spend the gate's cost; **not** a prediction of the gate |
| unchanged | the stimulus length and the SR-sparsity rule of the task, the operator, the statistics copies, every other number of this section |

**No automatic successor.** A no-go stops; a valid FAIL of `b4-gate-2` closes this protocol version; any later research needs its
own reasons and its own authorisation. Neither outcome is written as a scientific impossibility, and two FAILs do not prove that a
third version would be overfitting — they only remove the automatic next step.

**v0.3.0 — the row for `b4-sim-5` (the owner's ruling of 2026-10-27; fixed here, before the exploration, in the document and in the
machine table `b4_thresholds.THRESHOLDS["gonogo"]` together).** The policy above is carried **unchanged in every number and rule** to the
next exploration `b4-sim-5` under task-v0.3: the precondition (all **32** planned pairs complete, the batch neither `invalid` nor
`incomplete`, every contract held — otherwise **no decision**); the budget **B = 64** with every budget's descriptive values reported;
statistic 1, the one-sided exact sign test on Ω − R at B = 64 with **positives > negatives** and **p ≤ 0.20**; statistic 2, the seven
judged conditional K9 medians each **≥ 0.50**; go iff all hold, no-go otherwise; no automatic successor. One naming is corrected: the
threshold on the sign test's p is **`p_max_go` = 0.20, an engineering cost threshold on p, not the α of a formal scientific test** —
the record's field and the table's key say so, the value is the one of v0.2.0. The row applies to `b4-sim-5`; `b4-sim-4`'s no-go of
record (`evidence/b4/gonogo/b4-sim-4_20261021T065857Z`, v0.2.0) is not re-decided under it. An execution plan for `b4-sim-5` cites this
row and chooses nothing; a go authorises nothing by itself.

### 9.5 The protocol identity (v0.2.0, DRAFT; the owner's choice 6; implemented by the v0.2.0 tool unit, `b4_protocol.py`)

**The problem it answers.** The thresholds table's digest covers the numbers of this section and nothing else; the task version, the
comparison set and its applicability, K10, the statistics copies, the engine, the cartographer, the execution boundary, the snapshot,
the replay, the summary, the judgement, the validators and verifiers and the record schemas are the *method* just as much. A
document-only revision of this file must not change the method's identity, and a changed method must not re-judge an old archive.

**The payload.** A canonical JSON document `protocol_identity` built from the **trusted source inventory** of the tree the tool runs
in (`b4/IMPORT.json` and the file digests it is held to), containing: `thresholds_sha256` (the canonical table with no revision text
in it); `task` (version string and the generator's digest); `k9` (panel version, applicability rule version, the module's digest);
`k10` (τ, salt, the module's digest); `statistics` (the seven copied functions' per-function digests); the digests of
`b4_engine`, `b4_carto`, `b4_execution`, `b4_snapshot`, `b4_replay`, the summary (`b4_sim`'s statistics stage), the judgement
(`b4_gate`), the validators and verifiers (`b4_sim_schema`, `b4_sim_verify`, `b4_gate_verify`); every record schema by **content
digest of its validator, not by its version string alone**; the hypothesis's and the certificate's digests; and, as a provenance
field **excluded from the digest and from the equality**, `architecture_revision` (this document's revision text). The complete
tool-file inventory is cited (every `b4/host` module and every `b4/schemas` file by digest, and the import table's entries for exactly
those files) so that no stage of the summary / judgement stack is left out — and nothing else: an edit of a test file is not a change
of the method. **The revision text lives outside the inventoried method bytes** — `b4/architecture_revision.json`, a provenance file
that is not a tool file, read by `b4_thresholds.ARCHITECTURE_REVISION` and held to this document's first line by the static pin test —
so that a documentation-only revision changes that file and this document, no byte under `b4/host`, and the method's identity does not
move (the owner's review of 04385ae, R1; proven in fresh interpreters on the real file / import-table workflow by `test_b4_protocol`).
`protocol_sha256` is the digest of the payload without `architecture_revision`; the payload never contains its own digest.

**Where it is written and how it is compared.** The harness writes the payload and `protocol_sha256` into the manifest beside the
inputs. A verifier **rebuilds the payload from its own trusted inventory** and compares it with the archive's — never merely re-checks
the digest the archive recorded of itself. Equal: the archive is of this version and the verifier proceeds with this version's
schemas and methods. Not equal, or malformed: a **named refusal** that lists the differing components and points to
`docs/b4_archive_reverification.md`; no re-judgement of an old archive under a new method, no partial verification. An archive
written before the identity existed (`b4-sim-3`, `b4-gate-1`) is recognised by its lack of the field and refused by name the same
way, with its recorded HEAD and tool digests as the pointer. **No general version selector** is designed or authorised here.

**What is unchanged.** The anchor formula (§9.2); every number of this section; the rule that an old archive is judged under the
table and the method it was produced with (the gate execution plan §6).

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
- No gate **result**: §9's thresholds are fixed in advance (unit 2b-3) and no row of them has been
  measured; N, `B*`, the effect size and the per-session universe size are not known here.
- No schema change (§6 proposes; v2 is untouched), no code, no RTL, no image.
- No authorisation: units 2b (gate simulation), 2c (preregistration) and 2d (provisioning)
  are each separately authorised; no board contact, no port, no purchase.
- The B1–B3 verdicts, the lifecycle-2 S2 / S3 proof exceptions and the repair unit's
  acceptance are unchanged by this document.
- **v0.2.0 (DRAFT) claims nothing new about the fabric and authorises nothing**: task-v0.2, K9 (b′), the go / no-go policy and the
  protocol identity are designs for a tool unit that does not exist; `b4-sim-4` and `b4-gate-2` are names, not derivations; the
  gate `b4-gate-1`'s valid FAIL and the archives of `b4-sim-3` and `b4-gate-1` are unchanged and are not re-judged; the owner's
  review of these documents is not a tool acceptance, an exploration or a gate.
- **v0.3.0 (DRAFT) claims nothing new about the fabric and authorises nothing**: task-v0.3 is a stimulus rule fitted to the physical
  slice, implemented and verified on mechanics fixtures; `b4-sim-5` is a name, not a derivation; the no-go of `b4-sim-4` and the
  archives of `b4-sim-3`, `b4-gate-1` and `b4-sim-4` are unchanged and not re-judged; no K9 coverage or search benefit under the new
  stimulus is predicted; the owner's review of this unit is a host-tool engineering acceptance, not an exploration, a gate, a
  preregistration freeze, a board authorisation or a push / merge.

## 13. The units ahead (each separately authorised; none begun)

| unit | deliverable | gate |
|---|---|---|
| 2b-1 (**delivered**; corrected on the owner's HOLD, v0.1.4) | `b4/host/b4_ff_mapping.py` (the certificate mapping of `SLICE_X2Y25`, 21 addresses / 22 names, held to the specimen pairs), `b4/hypothesis/ff_behaviour_v0.2.json` + `b4/host/b4_ff_hypothesis.py` (the behaviour hypothesis: sources by kind with digests, the eleven behaviour flags, the enum readings with the clock mode by storage context, the three contracts of §5.0; the loader verifies by default, fixtures marked), `b4/host/b4_ff_model.py` (the fabric: configuration + stimulus → the executing side's trace under mapping and hypothesis passed in separately, the decode a host-only diagnostic, validation at the entry, out-of-domain configurations refused; the fixtures truth / permuted / dropout / seven hypothesis swaps), `b4/tests/test_b4_ff_*.py`, `b4/IMPORT.json` | hand-derived expected traces; INIT and SR separated; CE, edge, kind, transparency; isolation; permutation; hypothesis swap; the mutants (a model that ignores its hypothesis is killed) |
| 2b-2 (delivered v0.1.6; **HOLD and follow-up v0.1.7**: replay as re-execution, provenance bound, the holdout contract; X a symmetry control pending the design review) | `b4/host/b4_execution.py` (the port that exposes `observe` and the addresses only; the terminal event), `b4/host/b4_landscape.py` (the public task and the scoring), `b4/host/b4_engine.py` (the derived (μ, λ) engine over the FF universe; R / F / O / X; DOMAIN termination as ruled), `b4/host/b4_carto.py` (the observation cartographer: seen cells, presence, no-effect-seen, context-dependent, unknown; groups; the v3 draft; control X with its shadow isomorphism; A0, D, the privileged Ω), `b4/host/b4_replay.py` (EXACT replay), `b4/host/b4_stats.py` (the four-corner computation), `b4/host/b4_rng.py` (the PRNG copy), `b4/schemas/self_map_v3.schema.json`, the tests. **No exploration run, no gate number, no threshold.** The exploration under `b4-sim` (S = 32 first) follows 2b-3 and its own authorisation | the revised scope's acceptance list (section 6); the thresholds commit before any exploration |
| D1′ latch_ginv probe (**delivered; PASS on `e0b5f04`**; the owner's ruling of 2026-10-18 §2 and the follow-up ruling) | `b4/probes/latch_ginv/` (the derived specimen and build script with `GINV`, the driver with the expectation fixed before the build, the test), `evidence/b4/unit_d1prime_latch_ginv_2026_10_18/` (attempt 1: the six bitstream clauses and the structure held, the cell rule's `ROUTED`-only reading of `INTRASITE` the finding, kept as it was) and `…_attempt2_2026_10_18/` (the rule accepting `ROUTED` / `INTRASITE`: every clause met, no finding; readbacks and configuration frames identical to attempt 1's; the historical `main_latch` reproduced frame-for-frame) | host correspondence only; nothing of the model changed; v0.3 a separate unit |
| v0.3 model revision (**delivered**; the owner's ruling of 2026-10-18 on the scope draft, after the PASSes on `e0b5f04` and `c0689f8`) | `b4/hypothesis/ff_behaviour_v0.3.json` (the latch bit-0 reading on the D1′ pair, labelled host correspondence; the three layers L1 / L2 / L3 in their own source entries; the domain complete by assumption; the init step's atomic assignment named a model abstraction), `b4/host/b4_ff_hypothesis.py` (the formal pointer and digest only), the v0.2 file kept byte for byte, the tests (the hand-derived inverted-gate trace in the model's settle order; the `v021_hole` fixture carrying the 0.2.1 result; F completing under 0.3.0), `b4/IMPORT.json`, this document, `evidence/b4/unit_v03_2026_10_18/` | the local regression and the mutants; the owner's review; silicon status unverified; not gate-ready |
| X-A (**delivered; PASS on `c0689f8`**; the ruling of 2026-10-18 §4) | `b4/host/b4_carto.py` (`derangement_attempts`, `relabel_genome`, `isomorphic_addresses`, `residual_structure`; the lane permutation kept as the symmetry test), `b4/host/b4_engine.py` (arm X over relabelled addresses with its own control seed, π before the base, the shadow contract after every ingest, the control failure event, the residual post hoc), `b4/host/b4_replay.py` (π re-derived from the control seed; the control fields typed; a control failure must reproduce), the tests, `evidence/b4/unit_xa_2026_10_18/` | the partition-changing fixture and the partition-preserving counterexample; π from the control generator (the operator's untouched); base / mid-generation termination; the control failure's commit point; full replay; 19 mutants. Mechanism only: no arm advantage measured, no seed scan, no landscape exploration |
| 2b-3 (**delivered**; the owner's ruling of 2026-10-18 on the thresholds scope draft; wording follow-up v0.1.13a, no number changed) | one documents-only commit: §9's K1–K10 thresholds, τ = 2, the grid and `B*` rule, what the 4 000 cap is and is not, §9.1 the incomplete-run / invalid policy, §9.2 the anchor on the hypothesis digest with the control-generator formulas and the file-by-file exclusion set, §9.3 K9's fixed comparison set, §8's D row as the shuffled F-learned view; `evidence/b4/unit_2b3_2026_10_18/` | the owner's review; the exploration harness comes next, then the formal gate — neither authorised here |
| 2b-4a (**A / B / C delivered `8939fb9` / `feda985` / `edfc93c`, evidence `cdf2c53`; the owner's review of 2026-10-18: HOLD on nine reproduced gaps F1–F9; the repair unit delivered below, awaiting the owner's batch review**; the owner's ruling of 2026-10-18 on the exploration-harness scope draft) | **A (delivered):** `b4/host/b4_seeds.py` (the anchor formula with the label beside it; the 38 historical sources read against their digests through typed field paths; B4's exposed values; the `evidence/b4/sim/` registry of every archived set; one pooled set; B2's `pair_seeds` by copy), `b4/host/b4_controls.py` (the X and D control seeds; F's frozen view REBUILT from the base and the 21 probes and held to the record, replayed first; D as that view through `shuffled_view` once with the permutation and residual recorded and verified), `b4/host/b4_snapshot.py` (K7: the map rebuilt from the ledger under each arm's rule — O online, X relabelled with its shadow, F base + probes then frozen, given views and R not applicable; O's `B*` prefix of exactly `B* + 1` records; the final fields held to the rebuild), their tests. **B (delivered):** `b4/host/b4_deadline.py` (the soft monotonic deadline: `check()` between work units, a started unit never interrupted), `b4/host/b4_gate_stats.py` (`median` / `percentile` / `mean` / `cohen_d` / `sign_test_p` / `bootstrap_reject_rate` / `required_pairs` copied verbatim from `host/b2_gate.py`, per-function digests in IMPORT; `required_pairs_scan` the same scan with a check before each N; `encode_stat` for a non-finite statistic), `b4/host/b4_observe.py` (the per-seed memo: every unique observation kept whole, true calls vs hits, one source identity), `b4/host/b4_k9.py` (§9.3 as code: 64 backgrounds, 1 184 forced pairs, applicability from the decode of the endpoints only — by hand 384 / 384 / 32 / 32 / 16 / 32 / 32 applicable pairs — the differences by position, the per-semantic and per-address counts, the offline recompute), `b4/host/b4_k10.py` (two fixed backgrounds, 2 × 210 four-corner units with every corner kept, τ = 2, a `comparable = False` return escalated to invalid at once, the offline recompute), their tests. **C (delivered):** `b4/host/b4_sim.py` (the harness: a pre-flight that writes nothing on refusal — the `b4-sim-<n>` label, a clean tree with no override, the formal source, the root's inputs at their pinned digests, every exclusion source, an output directory directly under `evidence/b4/sim/` created exclusively; `seeds.json` then `manifest.json` then the first observation; per pair R → F → O → X → D → Ω → A0 on one worker, each `RunResult` written at once before its audit, the typed completion checks of the ruling §4.3, the replay, the ledger recompute, the given-view checks, D from F's rebuilt map, K7's prefixes, K9, K10, the curves, the pair index, the HEAD / input checkpoint; the fail-closed stop rules — invalid or incomplete, `STOPPED.json` with the whole planned list, a typed `sim_report.json` always and a pooled summary only when complete; values beside the §9 thresholds, no verdict field), `b4/host/b4_sim_schema.py` (typed validators of every file, applied before each write and offline), `b4/host/b4_thresholds.py` (the machine table of §9's numbers, pinned field by field to this document's text by a static test), their tests (the harness on a hermetic repository copy: refusals, a complete batch, the registry of a second batch, the invalid and incomplete stops, the validators), `evidence/b4/unit_2b4a_2026_10_18/` (README, tests, mutants, the IMPORT check). **Repair (delivered; the owner's HOLD of 2026-10-18 on `cdf2c53`):** F1 the tests' production derivation replaced by `b4-mech-<n>` fixture schedules with a guard, the prior exposure recorded (`evidence/b4/unit_2b4a_repair_2026_10_18/exposure/`); F2 `b4/host/b4_sim_verify.py`, the archive-wide verifier (required files, hashes, linkage, every conclusion recomputed from the raw readouts), run by the batch on itself; F3 the validators total and type-exact on nested values, the fixed comparison sets enforced, the task and source bound; F4 a verification finding or an unwritable report is `invalid`, never `complete`; F5 K10 observes no corner after the first refused one; F6 the quarantine of a malformed returned object and the partial K9 / K10 record kept on every failure; F7 no symlink at any level of the namespace; F8 the deadline checked before every finalisation unit; F9 the checkpoints hold the external sources, the 38 exclusion sources and the registry snapshot, the code root recorded apart from the input root. **Second round (the owner's HOLD on `f2c4bca`, R1–R5, delivered):** R1 completeness invariants in the record validators and the deep re-audit of every arm of a complete pair; R2 every record bound to the planned pair / role / seeds and every descriptor to the formal source; R3 exact scalar types, canonical-text comparisons; R4 / R5 the deadline and every input re-checked after the final verification, before publication. **Third round (the owner's HOLD on `6c00156`, delivered):** the diagnostic state ↔ file contract, the remaining counts and genomes exact, the deadline records validated and bound to the manifest. **Fourth round (the owner's HOLD on `8d1eefd`, 2026-10-19, delivered):** the contract total and asked only of validated documents, the deadline record one monotonic sample, an interrupt before any K9 / K10 record leaves `in_progress`. **Closed:** the owner's engineering acceptance of `82e863e` (2026-10-19) | the owner's review of the repair (PASS, 2026-10-19); the treatment of the prior exposure (the settlement unit below); no exploration run, no gate, no threshold changed |
| exposure settlement (**delivered for review**; the owner's ruling of 2026-10-19 on the prior exposure) | `evidence/b4/unit_2b4a_exposure_settlement_2026_10_19/` (the ruling; `reconstruct_exposure.py`, the seed-only reconstruction from `edfc93c`'s derivation code; `exposure_receipt.json`, the pinned receipt; `reconstruction_comparison.json`, the 22 preserved records against their recipes; README); `b4/host/b4_seeds.py` (`RETIRED_LABELS`, `EXPLORATION_LABEL`, the receipt loader and validator, seeds schema 1.2.0), the harness's refusal of a retired label before any tree is read, the receipt as a root input held at every checkpoint, the manifest / seeds / verifier binding, the thresholds table's exploration label `b4-sim-3`; tests and mutants | the owner's review of the settlement; the S = 32 `b4-sim-3` exploration remains a separate authorisation |
| 2b-4 (**delivered and executed**: the gate tool, PASS on `19597e7`, archived `00336d0`; the execution plan v0.2.1, PASS on `b15a572`; the production `b4-gate-1` executed 2026-10-20 at `a243ee8`, archive `5070967`, unit record `d19cc2f`, the owner's PASS on the executed unit) | `b4/host/b4_gate.py`, the formal gate under `b4-gate-1` (S = 200): **verdict FAIL, formal** — the budget rule FAILS (no N at any budget), K9 FAILS (`ff_srval` 0.40625), K1–K7 not assessable, K8 / K10 PASS; `evidence/b4/gate/b4-gate-1_20261020T102526Z/gate_report.md`; the v3 map schema draft (§6) unchanged | every row PASS / FAIL as the tool wrote it; a valid FAIL of protocol v0.1.16, confined to this model, task / panel, design, grid and procedure; never evidence about the fabric |
| 2c | `docs/b4_preregistration.md` DRAFT (B4-FF: claim, pins, prediction, metrics, falsifiers, sessions and rulings, compatibility, lifecycle, §9 rule; B4-R: prerequisites and prohibitions only) | the owner's review; the holdout and the universe fixed by whole site instance |
| carrier v2 design (**accepted and closed — the owner's PASS on `bf17574`, 2026-10-21: the host-only engineering unit, R1–R4 resolved; archived `evidence/b4/unit_carrier_v2_2026_10_21/owner_review_bf17574_PASS/`, closure 2026-10-27**; delivered at `823f5b0`, 2026-10-21; the owner's HOLD the same day, R1–R5; repaired in the same unit — v0.2 of `docs/b4_carrier_v2.md`: P9 the current transaction's event on the restored base, the AXI gates making the event safe for the bus, the latched STEP and the one CTRL rule, the record layer rewritten with closed schemas / binding / chain, the LUTRAM thermometer pulse and the GSR-aware netlist bench; the owner's second HOLD on `aaf15ba` (five items), repaired in the same unit — v0.3: W never masked by the gates (an accepted burst drains), the observation sealed at the P6 boundary and the close judged by the engine's completion witnesses, the session-opening record bound to the trusted context with seq reconciliation and the fitness recomputed from the trusted task, the phase table governing the acquisitions, the recorded pre-init cleanup inside step 0 for the A5 exception; the owner's third HOLD on `ce3ca6d` (four items), repaired in the same unit — v0.4: the loaded-image and restored-base references bound separately, the P6 seal from the acquisition state with premature operations kept as invalid observations, a write admitted per half (a W-first AXI-Lite transfer held during the event), the chain validating every record's shape before traversal; resubmitted for review**; the branch `b4-carrier-v2` from `36e012c`) | `docs/b4_carrier_v2.md` (the design: the init mechanism **(b) GSR through STARTUPE2** selected with the reasons, the GSR-immune LUTRAM store, the transaction ↔ CTRL mapping, the MMIO map, the timing, the sampling path, A1–A8 host-verified vs board); `rtl/b4/` (the target slice at `SLICE_X2Y25`, the AXI gate, the gate without the sweep, the engine, the register file, the top); `tb/b4/` + `sim/b4/run.sh` (the hypothesis v0.3 as the bench's fabric, six fixtures from the formal model, 27 scenarios, the vendor-model bench over the RTL and over the GSR-aware netlist of the core, the PS path through the pinned shim incl. multi-beat bursts); `vivado/b4/` + `builds/b4/` (routed, WNS +7.263 ns, target 12 / flush 0, RAM32X1S 279, STARTUPE2 1, ICAPE2 0; the 21 addresses read back from the bitstream at their expected values); `host/b4carrier_*.py` + `tests/test_b4carrier_*.py` (the register table vs the RTL decode; the O / F / X / session_open records from the bench traces in three layers); `evidence/b4/unit_carrier_v2_2026_10_21/` (README, the mutant battery, the build and bench records, the owner's HOLD review archived). **Finding:** a 7-series slice has one CE / SR / CLK pin for its eight elements; task-v0.2's and the model's per-element `ce` / `sr` vectors are realisable only when uniform — the carrier refuses the rest by name (`docs/b4_carrier_v2.md` §0); the protocol consequence is the owner's (taken up by the task-v0.3 revision unit, the ruling of 2026-10-27) | the owner's review: **PASS on `bf17574`** (host-only engineering scope; not A8, silicon, timing, legal compositions, a gate result or a freeze); A2 / A8 and the pulse width on the board; the firmware, the PCAP integration and the B4Q plan separate units; push / merge not authorised |
| 2c-obs — the observation contract (**delivered as a DRAFT v0.1 at `e91650b`, 2026-10-21; the owner's HOLD (R1–R3, D1–D4) → v0.2 at `d8ef6cf`; the owner's second HOLD (C1–C4, one P3) → v0.3; the owner's third HOLD (R1–R4) → v0.4; the owner's fourth HOLD (two P2) → v0.5; **accepted and closed by the owner's review of `4fc3dc7`, 2026-10-21 (PASS: the document contract; D4 accepted as the data-informed DRAFT A2 selection); all in the same documents-only unit on the branch `b4-2c-obs`**) | `docs/b4_observation_contract.md` DRAFT v0.5, accepted as a document contract: the step grammar and task-v0.2's stimulus shape (ending at clock 0) as the carrier's application rule; the raw readout as a **logical view** built from each **retained representation through a declared adapter** — the archive's observations are projections bound by four separate commitments (`trace_sha256` the Q-grid digest only), the raw return retained only in quarantine with its dictionary config and default-separator digest, nothing re-encoded or retagged, derived view fields labelled derived, the `fabric` descriptor copied exactly, the source bound to trusted identity outside the record; D1 as ruled with the model / board **scoring-domain limit** named on a retained `b4-sim-4` k10 observation; **three objects per transaction** — the observation `O` immutable before scoring, the fitness `F`, the transaction close `X` holding the cleanup, the current base readback, the current base-state sample and the idle status — with exact closed field sets (an invalid `O` phase-dependent), a field-aware A3 rule (enum identity values such as the model's `fabric.kind = "truth"` validated by enum, the deny-list on key names only, the B1 zero-table check in the signed-reply layer), D3 as ruled; the transaction P1–P10 with one initialisation = the stimulus's step 0, a recorded cleanup, a **session-opening record** binding the fabric as loaded to the pinned carrier's base-frame reference and the **session root** as the terminating predecessor, the frame binding conditional on mechanism and predecessor context and apart from Q-state restoration, **A5 as a decision table** (the pre-init state excluded in both places it appears; the injection witness checked apart; a qualification-only injection protocol with its own record statuses), faulted / interrupted transactions retained as non-success records; INIT / SRVAL as two observation points, D2 as ruled, the per-mechanism order, the **same-element 2 × 2 A8 cross** with **one fixed stimulus carrying a validated reference, planted priors and two SR episodes (`d = 0`, `d = 1`) judged jointly** (restore / capture / hold / `unknown`), the G6 limit, the per-corner readings deriving the quantities of a **precedence-ordered outcome table** with a not-demonstrated row, a constant restore an absent SRVAL effect, no overlapping rows and attribution left to independent evidence; the positive-control rule as the **qualification-selection revision of choice 7, accepted** (the revision note above; the gate-1 wording kept as history), the nine pairs the data-informed DRAFT A2 selection; the two holdouts; the bench and board lists against A1–A8; `docs/b4_preregistration.md` v0.0.3 pointing to it; `evidence/b4/unit_2c_obs_2026_10_21/` (README, the two read-only scripts and outputs, the static contract checks against the owner's counterexamples of every HOLD, the authorisation with its source note, the five owner reviews archived) | **closed**: the owner's PASS on `4fc3dc7` — a document contract, not A8, not a silicon qualification, not a frozen preregistration; A8, the mechanism, the timings, the schema names and adapter, the holdout instance, the board-study metric across the scoring-domain limit, N / `B*` / prediction / sessions all **unresolved**; 2c not frozen; the carrier-v2 unit, 2d and any board contact separately authorised |
| 2d | provisioning and the supply measurements (§11) | board work; the owner's rulings per step |
| protocol v0.2.0 documents (**this revision**; the branch `b4-protocol-v2` from `d19cc2f`, the owner's ruling of 2026-10-20 on the scope proposal v0.2) | this document v0.2.0 (§7.1, §9 K9 (b′), §9.2, §9.3 clause 6, §9.4, §9.5, §12–§14), `docs/b4_archive_reverification.md`, `evidence/b4/unit_protocol_v2_design_2026_10_20/` (the two scope drafts, the owner's rulings, the read-only aggregation record, the influence table); the gate-1 unit's two pending document items | the owner's review of the documents; no program, table, hypothesis, import table, archive or seed changed; nothing run |
| tool unit v0.2.0 (**delivered and accepted**: `04385ae` HOLD R1–R6, `b29b0fb` HOLD C1–C3 / P3, **`21db2de` PASS, 2026-10-21** — the v0.2.0 host-tool engineering acceptance; `evidence/b4/unit_protocol_v2_tool_2026_10_20/`, the three owner reviews archived there) | task-v0.2 and the `PublicTask` / `PrivateTask` boundary, the target setup and its records (the quarantine of a refused return, the durable ordered prefix, the disk-authority reconciliation), K9 (b′) and the two applicabilities, the protocol identity and the verifier's named refusal, the go / no-go policy tool, the consumed labels, the call-count fixtures, tests and mutants, the thresholds table revised to section 9 with the revision text in `b4/architecture_revision.json` | the owner's reviews (PASS on `21db2de`); mechanics fixtures only; no production derivation |
| `b4-sim-4` (**executed once, 2026-10-21**: the plan `docs/b4_sim4_execution_plan.md` accepted at `495cc36`; the batch `complete` 32 / 32 in 199.256 s, archive `evidence/b4/sim/b4-sim-4_20261021T065339Z` (commit `580c0e5`); the §9.4 policy decided **no-go** at B = 64 — positives 7, negatives 13, ties 12, one-sided sign-test p 0.9423; the seven conditional K9 medians all ≥ 0.50 (`ff_srval` 0.8125, `sr_kind` 0.875) — `evidence/b4/gonogo/b4-sim-4_20261021T065857Z` (commit `adce027`); the unit record `evidence/b4/unit_sim4_execution_2026_10_21/` (commit `196b358`); **accepted and closed by the owner's review of `196b358`, 2026-10-21 (PASS; the no-go of record; the pooled exclusion now 2 690)**; the label consumed by its records) | the S = 32 exploration under v0.2.0 after the tool unit's acceptance; the §9.4 policy applied once | **a no-go is the cost policy's stop, not a scientific negative conclusion and not evidence about the fabric; no automatic successor** — what follows (a different grouping shape, operator or stimulus, or stopping) needs its own argument and ruling; `b4-gate-2` remains a reserved name |
| task-v0.3 revision unit (**accepted and closed — the owner's PASS on `e20e12b`, 2026-10-27**: the complete host-only revision unit, no blocking finding; the contract v0.6 and the carried go / no-go row accepted within scope; two P3 wordings folded into the closure; archived `evidence/b4/unit_task_v03_2026_10_27/owner_review_e20e12b_PASS/`; delivered 2026-10-27 under the owner's ruling of 2026-10-27 after the carrier v2 PASS; the branch `b4-task-v03` from the closure `e084f07`) | §7.2 (the slice-wide stimulus rule: CE 1/2, SR 1/4, independent, broadcast; `d` per element; the common grammar, the model input contract, the carrier mapping; ceiling ≠ reachability; the data influence disclosed), §9 K9 note and §9.3 clause 7, §9.2 labels (`b4-sim-4` consumed, `b4-sim-5` reserved), §9.4 the `b4-sim-5` row with `p_max_go`, §9.5 the stimulus rule in the identity, §12, §14; `b4/host/b4_landscape.py` (`TASK_VERSION = task-v0.3`, `STIMULUS_RULE`, `broadcast` / `is_broadcast` / `slice_wide_controls`, `stimulus_findings`), `b4_thresholds.py` (`task.stimulus`, `gonogo.p_max_go` / `applies_to` / standing, the labels, the pins), `b4_seeds.py` (the consumed `b4-sim-4`, `EXPLORATION_LABEL = b4-sim-5`), `b4_protocol.py` (the stimulus rule in the `task` component), `b4_sim.py` (the standing, the manifest constants), `b4_sim_schema.py` / `b4_target.py` (the shape held on every task record and in the reconstruction), `b4_gonogo.py` (`p_max_go`), `b4/architecture_revision.json` v0.3.0, `b4/IMPORT.json` refreshed; `docs/b4_observation_contract.md` v0.6, `docs/b4_preregistration.md` v0.0.4, `docs/b4_archive_reverification.md` §6; the tests (the shape, the two probabilities by hand, the validator, the carrier mapping, the slice-wide twin of the model, the labels, the pins, the identity), the mutants and the mechanics e2e; `evidence/b4/unit_task_v03_2026_10_27/` | the owner's review: **PASS on `e20e12b`** (an engineering acceptance: not a K9 estimate, a map benefit, N / B*, a gate result, silicon or a freeze); mechanics fixtures only — no production derivation, exploration, gate, board, push or merge; the next bounded work the review names: the `b4-sim-5` execution plan as a documents-only unit; `b4-sim-5`'s derivation and execution need that plan and their own ruling |
| `b4-sim-5` execution plan (**delivered for review**, 2026-10-27; the documents-only unit the owner's review of `e20e12b` names, section 4; the branch `b4-task-v03` after the task-v0.3 closure `0a4cba3`) | `docs/b4_sim5_execution_plan.md` DRAFT v0.1 (the accepted v0.3.0 method at the baseline `e20e12b`, `protocol_sha256 5bba53c7…`; the fixed S = 32 policy row with `p_max_go`; the candidate execution HEAD on `b4-task-v03`'s line after the plan's PASS and the branch `b4-sim-5-execution`; the deadline 3 600 s recommended and the costs estimated from `b4-sim-4`; the operator's fourteen-row stop (the tool bytes, the identity and its `task` component, the task constants, the labels, the policy key, the receipt, the three-entry registry, the pool of 2 690, the existing go / no-go namespace); one attempt, no retry, no replacement label, retention unconditional; the result paths; the known records of the three archives and the v0.3.0 fixture as records; the acceptance order; the identity and the old archives; what follows); `evidence/b4/unit_sim5_plan_2026_10_27/` (README, the read-only inventory script and its output; no seed derived or printed) | the owner's review; the execution needs its own ruling naming the execution HEAD and the deadline; no production derivation, exploration, gate, board, push or merge |
| `b4-gate-2` (**not authorised**; a reserved name) | the S = 200 gate under v0.2.0, after a go and its own execution plan and execution ruling | its own rulings |

## 14. Files and references

Unit 2b-4a (host-only, no run): `b4/host/b4_seeds.py` · `b4/host/b4_controls.py` · `b4/host/b4_snapshot.py` · `b4/host/b4_deadline.py` ·
`b4/host/b4_gate_stats.py` · `b4/host/b4_observe.py` · `b4/host/b4_k9.py` · `b4/host/b4_k10.py` · `b4/host/b4_thresholds.py` ·
`b4/host/b4_sim_schema.py` · `b4/host/b4_sim.py` · `b4/host/b4_sim_verify.py` · `evidence/b4/unit_2b4a_2026_10_18/` · `evidence/b4/unit_2b4a_repair_2026_10_18/` ·
`evidence/b4/unit_2b4a_exposure_settlement_2026_10_19/` (the exposure settlement: the ruling, the seed-only reconstruction, the pinned exposure receipt).

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

v0.2.0 (documents only): `docs/b4_archive_reverification.md` · `docs/b4_gate_execution_plan.md` (v0.2.1, the historical plan of `b4-gate-1`, unchanged) ·
`docs/b4_sim4_execution_plan.md` (v0.1.1, the plan of the `b4-sim-4` exploration, executed 2026-10-21; the read-only inventory `evidence/b4/unit_sim4_plan_2026_10_21/`; the executed unit `evidence/b4/unit_sim4_execution_2026_10_21/`) ·
`docs/b4_sim5_execution_plan.md` (DRAFT v0.1, the plan of the `b4-sim-5` exploration under v0.3.0, delivered for review 2026-10-27; the read-only inventory `evidence/b4/unit_sim5_plan_2026_10_27/`) ·
`evidence/b4/unit_protocol_v2_tool_2026_10_20/` (the v0.2.0 tool unit: the implementation record, the two correction rounds, the three owner reviews archived) ·
`evidence/b4/unit_gate1_execution_2026_10_20/` (the executed gate's records; the owner's review archived) ·
`evidence/b4/gate/b4-gate-1_20261020T102526Z/` and `evidence/b4/sim/b4-gate-1_20261020T102526Z/` (the gate's judgement and archive, unchanged) ·
`evidence/b4/unit_protocol_v2_design_2026_10_20/` (this revision's design record: the scope drafts v0.1 and v0.2, the owner's reviews and ruling, the read-only aggregation scripts and outputs, the influence table) ·
`b4/tests/test_b4_thresholds.py` (the static pin; its document-version assertion is expected to fail at this revision, see the v0.2.0 note).

2c-obs (documents only, 2026-10-21): `docs/b4_observation_contract.md` (DRAFT v0.5, the observation contract, accepted as a document contract on `4fc3dc7`; v0.1 held on `e91650b`, v0.2 on `d8ef6cf`, v0.3 on `df3b65e`, v0.4 on `6927c24`) · `docs/b4_preregistration.md` (v0.0.3, the skeleton pointing to it) · `evidence/b4/unit_2c_obs_2026_10_21/` (README, `k9_address_record.py` / `.txt`, `positive_control_choice.py` / `.txt` — read-only over the committed `b4-sim-4` archive).

carrier v2 (host-only, 2026-10-21): `docs/b4_carrier_v2.md` · `rtl/b4/` · `tb/b4/` · `sim/b4/run.sh` · `vivado/b4/` · `builds/b4/` · `host/b4carrier_regmap.py` · `host/b4carrier_records.py` · `host/b4carrier_manifest.py` · `tests/test_b4carrier_*.py` · `evidence/b4/unit_carrier_v2_2026_10_21/`. · `evidence/b4/unit_carrier_v2_2026_10_21/owner_review_bf17574_PASS/` (the owner's PASS review, archived; the unit closed, README §11).

task-v0.3 revision (host-only, 2026-10-27): `b4/host/b4_landscape.py` · `b4/host/b4_thresholds.py` · `b4/host/b4_seeds.py` · `b4/host/b4_protocol.py` · `b4/host/b4_sim.py` ·
`b4/host/b4_sim_schema.py` · `b4/host/b4_target.py` · `b4/host/b4_gonogo.py` · `b4/architecture_revision.json` (v0.3.0) · `b4/IMPORT.json` ·
`docs/b4_observation_contract.md` (v0.6) · `docs/b4_preregistration.md` (v0.0.4) · `docs/b4_archive_reverification.md` (§6: the `b4-sim-4` archive under its own tool) ·
`evidence/b4/unit_task_v03_2026_10_27/` (README, the owner's ruling as relayed, the tests, the mutant battery, the mechanics e2e, the import check; `owner_review_e20e12b_PASS/` — the owner's PASS review archived, the unit closed).

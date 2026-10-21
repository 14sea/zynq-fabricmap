# B4-FF — the flip-flop configuration-bit class on the board: preregistration (DRAFT v0.0.3 — a SKELETON, host-only, 2026-10-19; pointer revision 2026-10-21)

> **v0.0.2 → v0.0.3 (2026-10-21, the 2c-obs unit; a pointer, nothing resolved):** the observation contract that sections 5, 6 and 8 of this skeleton leave to 2c now exists as a DRAFT — `docs/b4_observation_contract.md` v0.5 (v0.1 held by the owner on `e91650b`, R1–R3; v0.2 held on `d8ef6cf`, C1–C4; v0.3 held on `df3b65e`, R1–R4; v0.4 held on `6927c24`, two P2; v0.5 **accepted as a document contract** by the owner's PASS on `4fc3dc7`, 2026-10-21; all corrected in the same unit: the stimulus, the raw readout as a logical view built from each source's raw wire format through a declared adapter, the three records per transaction with their immutability points, the one-initialisation transaction with its cleanup, session-opening record, session root and witnesses, A5 as a decision table with a qualification-only injection protocol, INIT / SRVAL observed separately with the same-element A8 cross, the two-episode SR-restore evidence and a precedence-ordered outcome table, A8 unresolved, the positive-control rule as a revision proposal of choice 7 with its nine pairs and the data influence disclosed, the two holdouts, the bench / board acceptance lists). **Every `<unresolved>` of this skeleton stays unresolved**: the contract fixes no N, `B*`, prediction, session, seed, holdout instance or initialisation mechanism, and this skeleton is not frozen by it. Sections 5, 6 and 8 carry a one-line pointer each; nothing else changed.

> **v0.0.1 → v0.0.2 (2026-10-19, the owner's P3 on `7cf6c7f`): the reference to B3's lifecycle corrected.** v0.0.1 wrote S0 as
> "freeze: the pins, the seeds, the plan", S1 as "the prediction" and S2 / S3 as "the sessions and the adjudication". The production
> reference `b3/host/b3_manifest.py` defines: **S0 init** — the manifest derived from the tree, the prediction already pinned, not frozen,
> no qualification, no main-plan binding; **S1 freeze** — the preregistration pinned and the owner's board-ready mark; **S2 qualify** — the
> qualification record reconstructed from its evidence and the calibration written from it; **S3 plan** — the calibrated plan bound;
> the board sessions and the pooled adjudication introduce no later transition. Sections 0, 2, 7 and 11 now say so, and the B4
> lifecycle, tool and stage contract stay **unresolved** — this correction authorises no lifecycle design. Nothing else changed.

> **What this document is.** The skeleton of unit 2c, written under the owner's ruling of 2026-10-19 ("B4 gate tool versus
> production execution", section 4) alongside the gate-tool unit and kept separable from it. It lays out the sections a B4-FF
> preregistration must fill and states, for each, what is already fixed elsewhere (by reference) and what is **unresolved**.
> **Nothing here is frozen or pinned**: no N, no B*, no main seeds, no prediction, no session partition, no calibrated rate, no
> board execution. Every `<unresolved>` is a field this document cannot fill before its named dependency is ruled. The formal
> gate (`b4-gate-1`, S = 200) has **not** run; this skeleton does not speculate about its outcome and carries no derived
> production seed. B4-R (the routing study) appears only as its prerequisites and prohibitions (architecture section 3).

> Sources, all by reference: `docs/b4_architecture.md` v0.1.16 (sections 2, 4, 5, 7, 8, 9, 10, 11, 12), `docs/b3_preregistration.md`
> v0.3.1 (the section pattern B3 used), `docs/autonomous_cartography_roadmap.md` sections 1, 4, 5, `docs/board_roles.md`,
> `b4/host/b4_thresholds.py` (the machine table of section 9, pinned field by field), the owner's rulings of 2026-10-18 (unit 2b-3, the
> thresholds) and 2026-10-19 (the exposure settlement; the gate tool versus the production execution).

## 0. Status of every field (the index the review reads first)

| section | fixed elsewhere (by reference) | unresolved here |
|---|---|---|
| 1 claim and scope | the question (architecture section 0), the class (`clb_ff_config`, content; section 3's routing prohibitions) | the one-sentence claim's N, B*, the pairs count |
| 2 pins | the hypothesis v0.3 digest, the certificate digest, the thresholds table's source (`b4_thresholds`) | every pin taken by the B4 lifecycle tool at the stage it defines for it (unresolved; B3 pinned at S0 init and froze at S1): tool digests, image, carrier, the gate report's digests |
| 3 universe and holdout | the 21 addresses of the certified site (section 4.1–4.3), `safety_class` content | the choice address-only universe versus whole-site-instance holdout; which site instance is the holdout |
| 4 authority | section 2 verbatim | nothing — restated, not changed |
| 5 raw observation versus scoring | sections 5.1–5.4 | the schema file that forbids an expected value (A3) |
| 6 carrier obligations A1–A8 | section 5.5 verbatim | which positive-control addresses the carrier must show before any mapping session (A2); A8's two restore demonstrations |
| 7 prediction and decision rule | the statistics of section 9 (Δ1 sign test, Δ2 reported) | N, B*, the main seeds, the prediction itself |
| 8 falsifiers | the kinds (section 9.1's invalid / incomplete; B3's falsifier form) | the exact list against the carrier v2 |
| 9 sessions and rulings | the per-session discipline (B3's) | the session partition, the calibrated rates, the board execution plan |
| 10 compatibility | A4, A7 | the carrier v2 and image identity |
| 11 provenance and lifecycle | section 10's three rules; section 9's revision rule | the lifecycle tool (B3's manifest pattern or its B4 form) |
| 12 dependencies | named below | all of them |

## 1. The claim, in one sentence, and its scope

> `<unresolved>` — of the form: *on EBAZ4203 `17A6`, on the carrier v2 (its qualification chain to be written), the B4 image running the
> derived (μ, λ) = (4, 8) engine over the 21-address flip-flop configuration-bit universe of the certified site, in the arms of
> section 8 at the gate's `B*` evaluations per arm, reproduces on silicon, record for record, the host-predicted outcome of N
> preregistered landscape pairs — the one predicted primary Δ1 = best_O − best_R by the one-sided exact sign test at α = 0.05 —
> and the host, recomputing every fitness from the served raw observations and replaying every arm, reproduces every choice.*
> N and `B*` are the formal gate's (section 7); the sentence is not written until they exist.

Scope: the content class `clb_ff_config` on one certified site, under the behaviour hypothesis v0.3; the sequential semantics
of section 5.2 (`ff_init`, `ff_srval`, `ce_mode`, `sr_mode`, `sr_kind`, `storage_kind`, `clock_mode`); the host-side map a
diagnostic, never a claim about silicon by itself (architecture section 4.2). Out of scope, and prohibited by section 3 until its
own preregistration: every routing-class (`int_pip`) write, anywhere; no routing bit in any universe, control or landscape;
`08EB` is not a sacrificial board under this document.

## 2. Pins (taken by the B4 lifecycle tool at the stage it defines — unresolved; B3 pinned at S0 init and froze at S1; none taken by this skeleton)

| what | fixed by reference now | pinned by the lifecycle tool (stage unresolved) |
|---|---|---|
| the behaviour hypothesis | `b4/hypothesis/ff_behaviour_v0.3.json`, sha256 `59948f9be3b4516547fbf039556d4aa6a4afd0b2dda2324619e4d40ef0651ed8` (`b4_ff_hypothesis.HYPOTHESIS_SHA256`) | its digest, re-verified |
| the certificate mapping | `gate_runs/run_2026_08_05_ff/certificate.json`, sha256 `c69e419f836684872c9edb3754cdb7c76591aaabf69859dab448454c6d78ceef` | its digest, re-verified |
| the thresholds | `b4/host/b4_thresholds.py` — section 9 (v0.1.16), pinned field by field by `test_b4_thresholds` | the table's digest; the gate report that was judged under it |
| the formal gate result | `<unresolved>` — `evidence/b4/gate/b4-gate-1_<UTC>/gate_report.json` and the batch archive it binds, when the production execution is ruled and run | both digests; the verdict and every row copied, not summarised |
| the host modules | `b4/host/*.py` by `b4/IMPORT.json` | every digest |
| the carrier v2, the image | `<unresolved>` (a separate design unit after 2c; the image build evidence as B3 recorded it) | bitstream, `VARIANT`, ELF / BIN, build evidence |
| the instrument | `zynq-psoracle` as B2 / B3 pinned it (archived, read-only) | re-verified |
| the universe, the holdout | section 3 below | the universe digest; the holdout site instance |
| the seeds | the anchor of section 9.2 with the exclusion set as pooled at the derivation (the exposure receipt, every archived set under `evidence/b4/sim/`) | the main seeds — derived once, at the lifecycle step B4 defines for it (unresolved), never here |

## 3. The universe and the holdout — choices to be decided

- **Universe.** The 21 configuration-bit addresses of `SLICE_X2Y25` as the certificate maps them (architecture section 4.1: 176
  feature entries, 168 distinct addresses on the site family; 21 on the one site; 22 names). `<unresolved>`: whether the board
  universe is **address-only** (the 21 addresses, the genome of 21 bits, as the host model's) or whether a whole-site-instance
  carrier exposes more; the counting discipline of section 4.1 applies to whichever is chosen.
- **Holdout.** The certificate's 22 / 154 mine / holdout split is the certificate's own engineering holdout against *its* tuning and
  is **not** B4's holdout (section 4.3). B4-FF's holdout is **by whole site instance**, not consulted while the FF cartographer is
  developed. `<unresolved>`: which site instance; whether it is a second site of the same family on `17A6` or a second die
  (`3671`, untouched). The sentence this section owes: *it is an engineering holdout — a site the cartographer's development did
  not read — and not a claim that the truth was unseen, because the certificate that names the truth was produced on the same
  board family by the same toolchain.*
- **Safety class.** `content`; routing-class risk is nil for this class (roadmap section 5, last paragraph).

## 4. Executing-side versus host authority (architecture section 2, restated, not changed)

The board is the sole executing authority for probe choice, candidate choice, fitness, selection and map update; the host is
notary, auditor, transaction endpoint and collector; it may recompute any of those after the data is submitted, as an audit, and
the result may never feed back into the board's decisions in that session or into a map update. The certificate and every
oracle derived from it are host-side reference answers invisible to the executing side: used by the host simulation (the gate's
Ω control) and by the adjudicator after a session, never compiled into the image, never consulted by the board. The B1 guard set
is re-aimed at the FF names (section 5.4); the permuted fixture must make the cartographer output the permutation, not the truth.

## 5. Raw observation versus scoring (architecture sections 5.1–5.4)

> *v0.0.3 pointer:* the logical observation view, the retained representations (the archive's projections and their four separate commitments, the raw return in quarantine, the carrier record) with their adapters, the physical-Q rule (D1 as ruled) and the model / board scoring-domain limit are drafted in `docs/b4_observation_contract.md` section 3; the three records per transaction (`O`, `F`, `X`), their exact field sets and immutability points and the field-aware A3 validator in its section 4; the schema file names are provisional there (D3), nothing implemented.

Every ledger entry carries the raw observation (the sampled outputs per step, or a digest with the full vector retrievable) **and**,
separately, the fitness the board computed under the landscape rule (section 7); the adjudicator recomputes the fitness from the
raw observation and a mismatch is a finding against the board, never corrected. The decode is a third thing, host-only. A semantic
the observation cannot resolve stays `unknown` (section 5.2), never decoded by assumption. `<unresolved>`: the schema file of the raw
observation (A3: it forbids an expected value), its name under `b4/schemas/`, and the digest form of the per-step vector.

## 6. The carrier's obligations — A1 to A8 (architecture section 5.5; the design unit is judged against them)

> *v0.0.3 pointer:* the A2 positive-control addresses are the **accepted data-informed DRAFT A2 selection** (nine pairs; the rule the accepted revision of choice 7; the data influence disclosed; the owner's PASS on `4fc3dc7`) in `docs/b4_observation_contract.md` section 7 — a selection for later B4Q planning, not a certificate, a legal-composition rule, a whitelist or a board-demonstrated control; A1's transaction, the cleanup and the opening baseline in its section 5; A5's projection, roles and injected state in its section 5.6; A8's same-element 2 × 2 cross, the SR restore evidence, the G6 limit, the three candidate initialisation mechanisms (D2 as ruled) and the conditional outcome table with attribution left to independent evidence in its sections 6.2–6.7 — A8 itself stays unresolved.

| id | obligation (verbatim by reference) | what 2c must name |
|---|---|---|
| A1 | one transaction per candidate under the instrument's links, watchdog and stop-loss; no new host-side computation before the record | nothing further |
| A2 | for each of the seven semantics a positive-control address under the model (unit 2b) and, under the ruling that first loads the carrier, on the board — before any mapping session; per address and context the discriminability reported, the uncovered addresses named and left `unknown` | `<unresolved>` the positive-control addresses per semantic, chosen from the model's K9 record (the fixed comparison set of section 9.3) — named here, measured on the board only under that ruling |
| A3 | the raw observation validates against a schema that forbids an expected value | the schema (section 5) |
| A4 | readback contract, identity page, `VARIANT` extended, not replaced; the application refuses any other carrier | the identity (section 10) |
| A5 | isolation between candidates by a negative test (a candidate's leftover state does not change the next observation) | the test's form |
| A6 | the bench reproduces every B1 scenario that still applies, plus one per row of section 5.2 | the list |
| A7 | the MMIO allowlist matches the RTL's AXI-Lite decode, mismatches only | the standing check |
| **A8** | the two restore mechanisms demonstrated on the board, each with a positive control: which event restores an element to its `INIT` value and which operation restores it to its `SRVAL`, under which conditions; an element with neither demonstrated keeps `ff_init` / `ff_srval` `unknown`; a carrier with no initialisation observation is accepted only with `ff_init` excluded | **the initialisation observation is the open design question**: the model's init readout rests on the atomic-initialisation abstraction (section 5.2; K9's `ff_init` row is *conditional on A8*); 2c must say what the carrier does to observe an `INIT` restore and an `SRVAL` restore separately, and what the claim loses if only one is demonstrable |

## 7. The prediction and the decision rule — unresolved until the formal gate result

- **The statistic** (fixed, section 9): the primary `Δ1_r = best_O(r) − best_R(r)` at `B*`, the one-sided exact sign test at α = 0.05 with
  H1 P(Δ1 > 0 | Δ1 ≠ 0) > ½, ties excluded from n and counted; the secondary `Δ2_r = best_O(r) − end_to_end_F(r)` at T = `B*` with F
  charged its 21 probes, reported with no threshold; the frozen arm's own benefit `best_F − best_R` reported next to Δ1.
- **N and `B*`**: `<unresolved>` — the formal gate's, under the budget rule of section 9 (the cheapest eligible budget; N by the complete
  ascending scan). This skeleton records neither a candidate nor an estimate: the S = 32 exploration of 2026-10-19 (`b4-sim-3`) found
  no N on its sample and is a descriptive reference only (its settlement README and the gate tool's read-only test say what it
  does and does not show); it fixes nothing here.
- **The main seeds and the prediction**: `<unresolved>` — derived once, at the lifecycle step B4 defines for it, by section 9.2's anchor
  under a session label, against the exclusion set as pooled then (the receipt, every archived set); the prediction embeds every O-arm
  ledger entry, as B3's did (B3 pinned its prediction at S0 init, before the S1 freeze). No value appears in this document before that step.
- **The stop rule**: `<unresolved>` — B3's form (the primary alone; no redraw; a stopped lifecycle is a stop decision document) is the
  template; whether B4 adds a stop on A8's demonstration is for the review.

## 8. Falsifiers — the kinds, to be sharpened against the carrier v2

> *v0.0.3 pointer:* kinds 4–6 take their observable form from `docs/b4_observation_contract.md` sections 5.6, 6.4–6.7 and 7.3; the exact list is still this skeleton's to write.

1. A fitness differs from its recomputation from the raw observation on any record — the image mis-computes or the model is wrong:
   a finding per record; KILL if the served observation contradicts the self-report.
2. A decode (host-only) contradicts the certificate on an address where the observation resolves the semantic — a certificate /
   model contradiction, not an image defect, when the replay reproduces it from verified observations (B3's attribution rule).
3. A DOMAIN refusal under the formal hypothesis on the board — `invalid` under section 9.1, never a landscape failure.
4. A8 not demonstrated for an element — `ff_init` / `ff_srval` stay `unknown` for it; the claim's semantics shrink accordingly and say so.
5. A positive-control address (A2) that the board cannot distinguish — the semantic is not observable on this carrier; reported, not repaired.
6. The isolation test (A5) fails — the carrier is refused before any session.
7. `<unresolved>`: the transport stop-loss and the per-session budget forms (B3's measured rate is never borrowed as a guarantee).

## 9. The sessions and the rulings — unresolved

The per-session discipline is B3's: power cycle → boundary → draft → owner signs → runner → archive → re-judge → commit; one
ruling per session; the archive verified before the next. `<unresolved>`: the session partition (how many pairs per session under
the per-session universe and observation count — a complete R or O run calls the observation boundary `B* + 2` times and a
complete F run `B* + 23`; the main arms' base observations come to `3 B* + 27` per pair before any baseline, audit or retry),
the calibrated rates (none exists for this class; B3's is not borrowed), the board (`17A6` under the content-class interlock of
`docs/board_roles.md`; `F8B3` for the carrier bring-up first; nothing powered before a ruling), the qualification session of the
carrier v2 (its own B4Q), and the execution plan of the sessions — each a separate ruling.

## 10. Compatibility — what the carrier v2 and the image owe

The readback contract (links 2–3), the identity page and the `VARIANT` word extended, not replaced (A4); the application refuses any
other carrier; the MMIO allowlist against the RTL decode, mismatches only (A7); the B1 guards (header, source, binary scans) over
the FF names and fields; the instrument unchanged. `<unresolved>`: the carrier v2 identity, the image identity, the build evidence.

## 11. Provenance and the lifecycle

Section 10's rules apply to every B4 file: repository-internal provenance by repository-relative path; external tools and trees by
an explicit root plus the digest of what is used; the clean-tree proof at the canonical path. The historical reference is B3's
lifecycle (`b3/host/b3_manifest.py`): **S0 init** (the manifest derived from the tree, the prediction already pinned, not frozen, no
qualification, no plan) → **S1 freeze** (the preregistration pinned, the owner's board-ready mark) → **S2 qualify** (the qualification record
reconstructed from its evidence, the calibration) → **S3 plan** (the calibrated plan bound); the board sessions and the pooled adjudication
introduce no later transition. `<unresolved>` for B4: the stages, the tool (whether `b3_manifest.py`'s form is copied into the B4 namespace
— by copy, with digests, never by import across the pinned boundary — or rewritten), which stage pins which of section 2's pins and
derives the seeds; nothing of this is decided by naming B3's. Section 9's revision rule stands: a threshold changed after the first gate run is a
revision of the architecture with its reason, and the gate is re-run and re-reported under the new commit — never silently.

## 12. Unresolved dependencies (each a separate ruling; none implied here)

1. **The formal gate result** — the production execution of `b4-gate-1` (S = 200) is withheld pending the gate tool's acceptance and
   an execution plan; N, `B*` and the eligibility of every budget come from it or from nothing.
2. **A protocol revision, if any** — the exploration's K9 record (the `ff_srval` median 0.427083 under the fixed comparison set; the
   configuration-only bound 0.5 the owner's audit found) is a question for a separately proposed revision that would disclose the
   exploration's influence; this version keeps the comparison set and the thresholds, and a valid formal FAIL is an acceptable result
   of it. Not decided here.
3. **The carrier v2 design unit** — RTL, bench, XDC, isolation, against A1–A8; after 2c defines the observation contract.
4. **2d** — provisioning (`F8B3`, `08EB`), the supply measurements of roadmap section 5 item 4, the acceptance regressions; board work.
5. **The thresholds-table / architecture-version coupling** — `b4_thresholds.ARCHITECTURE_SECTION` carries the architecture's revision
   number inside the table every archived batch binds; a documentation-only revision of the architecture would make every archived
   summary stop verifying. Found by the gate-tool unit; a design question for the owner before the architecture is next revised.
6. **The B3 open items** on `main` (the S2 / S3 formal proof exceptions, `image_ready = false`, the transport stop-loss) — unchanged by B4.

## 13. What this skeleton does not do

It fixes no number, derives no seed, names no prediction, partitions no session, calibrates no rate, powers no board, builds no RTL
or image, changes no threshold, and does not say that the gate has passed or will pass. It is separable from the gate-tool unit:
nothing in `b4/` reads it, and the gate tool's acceptance does not depend on it.

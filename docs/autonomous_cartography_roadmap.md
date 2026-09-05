# Autonomous cartography roadmap — the line after round 1′ (v0.1, host-only, 2026-09-05)

> **Standing: a roadmap, not a preregistration and not a ruling.** It records what the
> owner decided on 2026-09-05 after two audits of the round 1′ package
> (`docs/claimb_round1prime_package.md` §0) and after re-reading the device inventory,
> and it supersedes, additively, two earlier statements named in §6. It authorises no
> board contact. Every stage below gets its own host-only architecture / preregistration
> package and its own ruling before any board time.

## 0. What changed, in one paragraph

Round 1′ showed that on the pinned carrier the fitness is additive over the 292 INIT
bits, so a map-guided A/B there is decided by arithmetic (every primary block tied,
`docs/claimb_round1prime_preregistration.md` §0). Two corrections to the reading of that
finding are adopted: **additive fitness does not make the operators identical** — they
still differ by LUT weighting and sampling law, and what is proved is only that same-LUT
structure has no interaction advantage and that the fixed round 1′ primary saturates; and
**"device-local" need not mean physical noise** — the uart_stream benchmark's noise is a
seeded, replayable PL LFSR, and a digital, replayable, on-board self-learned map is
sufficient for a first autonomous-cartography stage. The programme is therefore
re-shaped from "run one map-guided A/B" into **four stages that can each fail on their
own**: build the map autonomously, prove it correct, prove it useful, close the loop.
Claim B becomes the *map-utility* sub-question (B2) and no longer carries the whole goal.

## 1. The architecture, and the autonomy boundary

```
minimal safe prior (addresses + coarse safety class only)
        ↓
board chooses its own probes
        ↓
readback + behavioural measurement (the P3 oracle: links 1–3, signed ARM, scorer)
        ↓
self_map + evidence + confidence   →  freeze / hash
        ↓
map-guided evolution (selection on the board)
        ↓
every evaluation is a specimen  ──────────→  the next map version
```

**The autonomy boundary.** The board is the sole executing authority for probe choice,
candidate choice, fitness, selection and map update. The host is notary, auditor, rel-v4
transaction endpoint and collector: it may **independently recompute** any of those after
the data is submitted, as an audit — and the result of that recomputation may **never**
feed back into the board's decisions in that session or into a map update. That line is
what "autonomous" means in every stage below; a stage that moves an executing decision
to the host is a different, weaker claim and must say so. *(Corrected 2026-09-05 on the
owner's review: the first wording forbade the host to compute fitness at all, which
contradicted its auditor role.)*

## 2. Stages

| stage | question | on the board | status |
|---|---|---|---|
| **B0 instrument** | can the board write, read back, sign, score and run for hours safely? | P3 / L6 (`zynq-psoracle`, archived at `689dde1`) | **done** |
| **B1 autonomous mapping** | can the board recover a replayable bit → function / structure map from its own probes? | mapping only; no Claim B A/B | **first package FAILED review 2026-09-05 (circular measurement on the P3 carrier — `docs/b1_package.md` §0); v2 package delivered the same day** on a B1 carrier under a noninterference contract (`docs/b1_carrier_contract.md`: the host signs writability only, never expected semantics; the readout reaches the cartographer raw) with an end-to-end modelled session through the real validators; awaiting the whole-package review, compatibility review, freeze, the carrier qualification ruling, then the mapping ruling |
| **B2 map utility** | does a frozen self-built map make the *same* selection engine beat random-safe? | the formal map-guided A/B | after B1 and the carrier-v2 gate |
| **B3 closed loop** | can evolution specimens update the map online, and does the update improve later search? | evolution-as-fuzzing | after B1 and B2 |
| **B4 expansion** | from LUT content bits to FF, then routing | content classes on any verify board; routing only on the sacrificial board (§5) | last |

### B1 — closed-book cartography on the known 292 bits first

Do not touch unattested bits yet. The existing `clb_lut_init` certificate (292 addresses,
6 LUTs, polarity, INIT index) is the **ground truth held back from the executable**. This
is not a human-blind test and may not be called one: the certificate exists and its
developer has read it. What B1 can claim is **closed-book, runtime-blind reconstruction by
the executable / the algorithm**, and that claim is protected by guards, not by trust — a
dependency scan and a binary/source guard (no LUT table, INIT index, polarity or group
may be compiled into or reachable from the cartographer), synthetic fixtures with a
permuted mapping (a cartographer that still outputs the real structure is hard-coded; one
that follows the fixture's behaviour is measuring), an address-only baseline (what
address structure alone predicts), and scoring only after the map is frozen and hashed.
Genuinely unknown discovery is reserved for the later, unattested content bits:

- the cartographer receives only addresses and a coarse safety class — never LUT names,
  INIT indices, polarity or groups;
- the board chooses probes (single-bit and combined interventions), measures readback
  and behaviour, and emits `self_map` with evidence and confidence per entry;
- the verifier scores the answer against the certificate only at the end;
- **primary metrics:** precision, recall, polarity errors, sample efficiency, confidence
  calibration, cold-boot replay of the same map bytes, map-hash consistency;
- a holdout: by whole LUT, not consulted while the cartographer is developed — an
  engineering holdout against tuning, not a claim that the ground truth was unseen.

Only after B1 passes is a separate ruling sought for probing the remaining unattested
content-bit entries (1 756 named by the frozen DB, never specimen-attested).

### B2 — a carrier that can discriminate

"Change the scorer" is necessary, not sufficient. The B2 package must also give:

- a fitness with **real interaction** across LUTs / bits — never Σ of per-bit
  contributions (the round 1′ lesson);
- a landscape / target generated by a public rule or an isolated seed **independent of
  the map operator** — no problem engineered to reward same-LUT mutation;
- a map schema v2 that can express functional relations, interaction edges, context,
  confidence and evidence provenance — not just bit groups;
- an image with **real selection / population**; candidates are no longer independent
  draws from the all-zero base;
- the two arms sharing universe, selection, population, budget, fitness and seeds, the
  mutation operator the only difference; search sees train only, each arm's champion
  sees the hardware holdout last.

**The discriminability gate — host simulation, before any board time.** The package
must show, in simulation over many seeds: the primary does not saturate; positive and
negative outcomes are both reachable; a **shuffled-map negative control** does not
profit; an **oracle-map upper bound** shows enough headroom; a pre-stated effect size,
power and required N; and no fixed-seed outcome locked by the primary's definition (the
16/16 tie of round 1′). A carrier or image that fails this gate does not go to the board.

### B3 — the closed loop, last

Three arms from a minimal bootstrap map: random-safe; frozen self-map; online-updating
self-map. Every evaluation writes `(map_version, probe/candidate, intervention,
behaviour_delta, confidence)` into a specimen ledger that produces the next map version.
Two costs are reported: search benefit once a map exists, and end-to-end benefit with
the mapping cost included — so that "correct but useless", "useful but too expensive to
build" and "online updating pays" are distinguishable.

## 3. Sequencing on the boards (owner, 2026-09-05)

**Everything without routing-class risk is done on `17A6` first; the sacrificial board is
entered only for routing, and only after the LUT (content-bit) stages are complete and
their gates hold.** No image, configuration or power operation is zero-risk; what is
guaranteed on `17A6` is that the work stays inside the certified content-bit boundary. Concretely: B1 (blind cartography on the 292), the B2 discriminability
gate and B2/B3 on content bits run on the verify board under the P3 discipline; B4's
routing part is the only work that touches the sacrificial board.

## 4. Device policy — Zynq first, and why K7 is not the sacrificial board

The inventory (`/home/test/test_devices/result.txt`, `EBAZ4203_UBOOT_BRINGUP.md`,
`EBAZ4203_PS_PL_DEMO.md`): **4 × EBAZ4203** (`17A6`, `F8B3`, `3671`, `08EB`; all accepted;
only `17A6` has the TF/U-Boot control plane), **2 × XC7K70T** (no hard PS; JTAG /
soft-core paths only; 12 V supply on the same barrel as the 4203's 5 V), 1 × Stratix V
(not accepted; not this line). The whole instrument line — psmap's PCAP reads and
writes, P3's three links and signed ARM, the standalone image and identity page — is a
**PS-looks-at-PL** architecture. It does not exist on a K7. So:

| board | role | notes |
|---|---|---|
| `17A6` | **verification** (unchanged) | P3 / L6 evidence; B1–B3 content-bit work |
| `F8B3` | non-destructive carrier / cartographer bring-up | to be provisioned (TF/U-Boot, `boardid`, `role`) before use |
| `08EB` | **sacrificial candidate** — not yet provisioned | see the hard lines below |
| `3671` | cold spare / future second-die confirmation | untouched |
| K7 pair | **ON HOLD** | not "impossible": a soft-core + ICAP oracle could be rebuilt, but the existing P3 is PS/PCAP and the port has no present necessity; the fabric-size advantage is the only surviving reason. prjxray coverage differences are index quality only — the evidence authority is our own specimen certificates either way |

Two hard lines, machine-checked where a tool exists (`docs/board_roles.md` interlock):

1. **`08EB` is not a sacrificial board until** it is physically labelled, carries the
   TF/U-Boot control plane with `boardid` and `role=sacrificial` in the saved
   environment, runs on the current-limited 5 V supply, and has passed the acceptance
   regression again. Until then no tool may treat it as one.
2. **Writing unconstrained routing bits is a separate destructive study**, under its own
   preregistration and ruling. It is never the baseline of the map-guided vs random-safe
   A/B: the main Claim B stays inside one certified-safe universe for both arms; the
   routing-hazard comparison is a different experiment with a different question.

## 5. The sacrificial board — what is known about damage, and how to spend as few boards as possible

*(Rewritten 2026-09-05 on the owner's review: the first version stated currents, times and
"expected zero boards" as facts. None of those is evidenced for this hardware; the
vendor's documents — AMD UG480 for the XADC, UG585 for the PS, DEVCFG and `PCFG_PROG_B` —
describe the mechanisms and do not endorse any damage current or safe exposure time for
this project. What follows is stated as conservatively as the evidence allows.)*

**Q1 — does a routing write destroy the board, and is it one board per mistake?** What is
established: an illegal routing composition can put more than one driver on one wire
(`docs/mux_groups.md`); the observable consequence is a **wedge-class** event (a dark or
hung fabric, a brownout, a regulator trip), and `docs/board_roles.md` §"Wedge is not damage"
rules that **a wedge by itself does not prove damage — damage is decided afterwards by the
acceptance regression, and only a failed regression retires a board.** So a sacrificial
board is reusable across incidents *as long as it keeps passing its regression*; it is not
one board per mistake. What is **not** established, and must not be written as if it were:
how much current a contended net draws on this die, how long an exposure is harmless,
whether degradation is gradual or abrupt, or whether the PS's rails are isolated enough
from a PL fault. The failure mode to plan for is a **silent partial degradation** that only
a regression covering the probed region would catch.

**Q2 — how to reduce consumption.** Each measure below *reduces* risk; none proves the
absence of damage:

1. **A host-side contention checker over the frozen DB model** — one driver per node,
   listed codeword per mux group (the escalation ladder's step 3). It proves *no known
   conflict under the frozen model*; it cannot prove the silicon is contention-free,
   because the model may be wrong or incomplete — which is exactly what the certificate
   ladder exists to find, one bit-class at a time.
2. **Specimen-derived compositions only** (patterns Vivado itself produced) before any
   blind composition.
3. **Bounded exposure**: write → readback → score → restore in one transaction, with the
   PS de-configuring the PL (`PCFG_PROG_B`) on a watchdog or a current threshold. This
   shortens exposure; it does not prove a short exposure is harmless.
4. **A current-limited 5 V supply with a trip, current telemetry on the supply, XADC
   temperature and rail readings by the PS.** The trip threshold, the sampling rate, the
   total reaction time from event to de-configuration, the external supply cut-off, and
   the fallback when `PCFG_PROG_B` itself does not take effect **must all be measured on
   the bench before the first routing write**, and the measurements go into the B4
   package. Until then these are design intentions, not protections.
5. **Region isolation** proven from the routed design — probes confined to a pblock whose
   frames carry no PS/AXI, scorer, HWICAP or control nets.
6. **The ladder as ruled** (readback-only → certified writes → unconstrained), each rung
   exhausted before the next, with the **acceptance regression plus a fabric self-test of
   the probed region after every session**, so a degradation is caught one incident old.
7. **Blacklist, never retry** a composition that wedged (`blacklist` schema, its
   fingerprint).
8. **Power-cycle between sessions**; never leave an illegal configuration loaded.

With 1–5 in place the routing stage's board consumption is *expected* to be low; that
expectation is a hypothesis the B4 package must state and the sessions must test. The
content-bit stages (B1–B3) involve no routing-class risk at all.

## 6. Disposition of existing assets, and what this supersedes

- The additive carrier is **kept**, demoted to a P3 regression / known-answer / cartographer
  ground-truth fixture.
- **Round 1′ is WITHDRAWN BEFORE FREEZE / NO-RUN.** It is not a Claim B negative; its
  package, plan, prediction and 57 tests stay as the instrument's known-answer fixture
  and as the template for B2's package (`docs/claimb_round1prime_package.md` §9).
- P3's three interlocks, readback, audit, rel-v4 and the L6 stop-loss are all kept.
- A new carrier or image may not reuse the C1/C2 rates: compatibility review,
  calibration and soak are redone. `zynq-fabricmap` owns the map / cartographer /
  scientific contract; `zynq-psoracle` is reopened only after the new carrier package
  passes review, under a new ruling.
- **Superseded, additively:** `docs/kickoff_fuzz_and_map.md` §5's "routing-class
  autonomous fuzzing → K7 sacrificial boards" (a banner on that file points here; its
  text is historical); the sentence in the assistant's 2026-09-05 assessment that placed
  B2 on the K7 line. `docs/board_roles.md` (2026-08-02) already ruled Zynq-first and is
  unchanged.

## 7. The nearest next step

Not RTL. A **host-only architecture / preregistration package** that fixes: the B1–B3
boundaries; the autonomy definition of §1; the map v2 schema; the landscape generation
rule; the controls (shuffled map, oracle map); the discriminability gate; the board and
provisioning plan of §4. That package is reviewed before carrier v2 is designed — so that
no more engineering is spent sending an experiment that arithmetic has already decided to
the board.

# B4 — the 2c-obs unit: the observation contract (documents and two read-only scripts only, 2026-10-21)

**What this unit is.** The documents-only unit the owner authorised on 2026-10-21 after the PASS on the `b4-sim-4` execution unit
(`196b358`, closed at `fceedd6`; the review's section 6: *what follows needs its own scientific or engineering purpose and explicit
scope*). The scope as the owner gave it, relayed by the user in session and recorded here (the owner's verbatim text was not handed
over as a file; if it is, it goes into `owner_authorisation_2026_10_21.txt` beside this README, unchanged): **a draft observation
contract for unit 2c — a pure document** covering the stimulus, the raw readout, the evidence fields and the isolation between
candidates; INIT and SRVAL each observed and recovered separately, A8 left unresolved; the positive controls, the address choice and
the disclosure of the data that informed it; the stimulus holdout against the whole-site holdout; the bench and board acceptance
conditions of a carrier v2. N, `B*`, the prediction and the sessions stay unresolved; 2c is not frozen; the whole unit is submitted
for review once; push and merge are not authorised; read-only inventory and proposals may continue.

**Branch.** `b4-2c-obs`, created from `fceedd6` (= `b4-sim-4-execution`'s closure; `main` = `origin/main` = `a243ee8`). One commit
for the whole unit. Nothing pushed, nothing merged.

**Interruption, disclosed.** The first attempt to write the contract document in the preceding session was stopped by the
assistant's safety classifier before the file existed; that text was not retained and, by instruction, not reproduced. The present
`docs/b4_observation_contract.md` was drafted afresh in this session from the sources its standing paragraph names, with a new
structure. The two read-only scripts predate the interruption (`k9_address_record.py`, 08:54 UTC) or were written after it
(`positive_control_choice.py`); neither was affected.

## 1. The files

| file | what it is |
|---|---|
| `docs/b4_observation_contract.md` | DRAFT v0.1: §0 status index; §1 position (a contract between architecture §5 and the carrier-v2 design; not a preregistration, not a composition rule, not RTL); §2 the stimulus (the step grammar `init` / `set`, task-v0.2's shape K = 6 + 2 / K = 8 + 2, the application rule with four declared-and-recorded timing intervals, the stimulus digest); §3 the raw readout (the visible fields in the model's order; **D1** the carrier records a physical 0 / 1 for every element and never `null`, the model's `null` a host diagnostic; the sample points; what a readout is not); §4 the evidence fields (the three records per candidate, the header incl. the two link-3 readbacks around the init mechanism, the A3 prohibitions as a closed key list and type-exact cells, **D3** the proposed schema name); §5 isolation (the cycle, idle as an observable status bit, the init mechanism raised twice, the A5 negative test's form with its limit stated); §6 INIT / SRVAL (two observation points, **D2** three candidate initialisation mechanisms declared not chosen with the bench-witnessable condition of each, the recovery by two readbacks, the three A8 demonstrations, the five-case table of what the claim loses); §7 positive controls (the quantifiers, **D4** the choice rule, the nine proposed pairs, the data influence disclosed); §8 the two holdouts as two axes with the carrier indifferent and a bench scenario for it; §9 the bench list and the board list against A1–A8; §10 twelve unresolved items each with its resolving dependency; §11 what the document does not do |
| `docs/b4_preregistration.md` | v0.0.2 → v0.0.3: a revision note and three one-line pointers (sections 5, 6, 8) to the contract; every `<unresolved>` unchanged; not frozen |
| `docs/b4_architecture.md` | §13 one row (2c-obs delivered as a DRAFT, its contents and its unresolved list); §14 one reference line. No numbered section, threshold, pin string or the first line touched |
| `k9_address_record.py` / `.txt` | read-only: per address the K9 covered / applicable counts under (b′) and (b) summed over the 32 `pair_*/k9.json` of the committed `b4-sim-4` archive; the choice rule's first half |
| `positive_control_choice.py` / `.txt` | read-only: the rule of contract §7.2 applied — per semantic the highest-(b′) address (ties in the mapping's address order; `ff_init` / `ff_srval` one main and one x5FF element each) and, for it, the background covered in the most pairs (ties the lowest `g0`); the nine pairs of contract §7.3 |

## 2. What was read, and what was not touched

| item | value |
|---|---|
| archive read | `evidence/b4/sim/b4-sim-4_20261021T065339Z` — `pair_*/k9.json` (32) and `sim_report.json` (sha256 `01744b39598b10bbf7d4371be1e5b9355c08fc39a8877ef6957866ac8178f1fa`) only |
| what the scripts do not do | derive, print or exclude a seed; call `master_seed` / `pair_seeds`; write outside this directory; modify the archive, a receipt, the registry, a threshold, a label or a decision |
| the pooled exclusion | 2 690, unchanged |
| `b4/` | unchanged (no program, schema, hypothesis, table or test edited) |
| the no-go of `b4-sim-4` | the record it is; not reinterpreted; the Ω − R sign played no part in the address choice (contract §7.4) |

## 3. Decisions proposed for the owner (none taken)

D1 physical Q never `null` on a carrier trace (contract §3.2); D2 the initialisation mechanism declared by the carrier among three
named candidates (§6.2); D3 the schema file's name and the one-validator-two-sources rule (§4.4); D4 the positive-control rule and
the nine pairs (§7.2–7.3). Each is marked in the document; the status index (§0) lists what is fixed as a draft and what is not.

## 4. Verification (documents only; proportionate per the owner's ruling of 2026-10-20)

No program changed, so no mutant battery and no full regression. Run as a guard against a pin accidentally touched by the
architecture edit: `b4/tests/test_b4_seeds.py` (scans `docs/b4_architecture.md` for seed literals) and `b4/tests/test_b4_thresholds.py`
(the §9 pin strings and the document version) — their results are in `verification.txt` beside this README, as they came.

## 5. What this unit does not claim, and what it does not authorise

The contract is a draft for review, not a frozen preregistration; its fractions are the host model's under hypothesis v0.3 and say
nothing about silicon; A8 is open; no board was powered, no RTL, bench, XDC or schema file was written; no seed was derived; no
archive, threshold, label, receipt or decision changed; the carrier-v2 unit, 2d, routing, `b4-gate-2`, any new batch, push and merge
remain the owner's.

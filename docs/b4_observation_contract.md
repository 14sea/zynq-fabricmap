# B4-FF — the observation contract between the executing side and the host (DRAFT v0.1, host-only, documents only, 2026-10-21)

> **Standing: a draft contract, not a preregistration, not a ruling, not RTL.** Written under the owner's authorisation of
> 2026-10-21, given after the PASS on the `b4-sim-4` execution unit (`196b358` / `fceedd6`; the review's section 6: *what follows
> needs its own scientific or engineering purpose and explicit scope*). The purpose: unit 2c's skeleton (`docs/b4_preregistration.md`
> v0.0.2) leaves the observation contract of architecture section 5 as functional requirements and names, in its sections 5, 6 and
> 8, what 2c must fill before a carrier v2 can be designed. This document fills those items **as a contract**: what the executing
> side applies, what it records, what the record may never contain, how one candidate is kept apart from the next, how the two
> restore mechanisms of A8 are observed and recovered from, which addresses are proposed as positive controls and from what data,
> how the two holdouts differ, and against what a carrier v2 is accepted on the bench and on a board. The scope the owner gave:
> the stimulus, the raw readout, the evidence fields, the isolation between candidates; INIT and SRVAL each observed and recovered
> separately with A8 left unresolved; positive controls, the address choice and the disclosure of the data that informed it;
> the stimulus holdout against the whole-site holdout; the bench and board acceptance conditions of a carrier v2. **Outside the
> scope, and unresolved here as in the skeleton:** N, `B*`, the prediction, the session partition; 2c is **not frozen** by this
> document. Nothing here authorises a board, an RTL unit, a push or a merge.
>
> **What it is built from, all by reference.** `docs/b4_architecture.md` v0.2.0 (sections 2, 4.1–4.4, 5.0–5.5, 7, 7.1, 8, 9.1, 9.3),
> `docs/b4_preregistration.md` v0.0.2 (sections 3, 5, 6, 8, 12), `docs/b1_carrier_contract.md` v0.1 (the links, the zero-table
> rule, `VARIANT`), `docs/b1_carrier_qualification.md` v0.3 (the qualification session's form and its evidence chain),
> `b4/hypothesis/ff_behaviour_v0.3.json` (`observation_context`, `initialisation_event`, `applicable_semantics`),
> `b4/host/b4_ff_model.py` (the step grammar and the visible step keys), `b4/host/b4_landscape.py` (task-v0.2's stimulus shape),
> `docs/board_roles.md` (the content-class interlock), `docs/autonomous_cartography_roadmap.md` sections 4–5. The one data
> source read for section 7 is the committed `b4-sim-4` archive, through the two read-only scripts of
> `evidence/b4/unit_2c_obs_2026_10_21/` (section 7.4 discloses that influence).

## 0. Status of every section (the index the review reads first)

| section | what it fixes as a draft contract | what stays unresolved (named, not decided) |
|---|---|---|
| 1 position | what a contract is here and what it is not | — |
| 2 the stimulus | the step grammar, the task-v0.2 shape, the carrier's application rule, the stimulus identity | the electrical timing numbers (hold, settle, sample offsets) — the carrier-v2 unit's, with the bench as witness |
| 3 the raw readout | the record's visible fields, the Q encoding on silicon, the sample points | nothing of the fields; the sampling implementation is the carrier's |
| 4 the evidence fields | the three records per candidate, the header, the prohibitions, the validator's rule | the schema file's name and version under `b4/schemas/` (proposed, section 4.4) |
| 5 isolation | the candidate cycle, what "idle" means, the A5 negative test's form | the leftover-state injection the bench and the board use for A5 |
| 6 INIT and SRVAL | the two observations as separate records, the three candidate initialisation mechanisms, the recovery and the readback after each, what the claim loses under each A8 outcome | **A8 itself** — which mechanism restores which value on this die |
| 7 positive controls | the quantifiers, the choice rule, the proposed nine address / background pairs, the data influence | the board's own result; whether the owner accepts the rule and the proposal |
| 8 the two holdouts | the stimulus holdout and the whole-site holdout as two axes; the carrier's indifference | the whole-site holdout's site instance |
| 9 acceptance | the bench list and the board list against A1–A8, each with its witness | the ruling that first loads a carrier; the board; the qualification session's plan |
| 10 unresolved | the list, each with its dependency | all of them |
| 11 what this document does not do | — | — |

## 1. Position — what a contract is here, and what it is not

Architecture section 5 says what a carrier v2 must *do* (the six-step observation of 5.1, the seven distinguishable behaviours
of 5.2, the three records of 5.3, nobody in the loop in 5.4) and how it will be *accepted* (A1–A8 in 5.5). It does not say what the
executing side and the host owe each other **at the record**: which fields, in which encoding, under which prohibitions, so that a
record written on a board is the same object as a record the host model writes today, and the host's verifier, replay and
adjudicator read both without a branch. This document is that contract. It sits between the architecture and the carrier-v2
design unit: the design is judged against it, the preregistration cites it, and neither may silently change it (architecture
section 9's revision rule applies: a change is a new version with its reason).

It is **not**: a preregistration (nothing is frozen or pinned); a legal-composition rule for the 21 bits (architecture section
4.2 — a separate rule of 2c, not written here; "accepted by the model" is never read as "legal to write"); an RTL sketch, a
timing budget or a placement (the carrier-v2 unit's); a statement about silicon (every behaviour named here is the hypothesis's,
unverified); an authorisation of any board contact.

## 2. The stimulus — what the executing side applies

### 2.1 The step grammar (fixed; `b4_ff_model.STEP_KEYS`)

A stimulus is an ordered list of steps of exactly two kinds:

| kind | fields | meaning |
|---|---|---|
| `init` | none | the initialisation event (section 6), raised once at the head of every stimulus; the model refuses it in any other context than the slice clock low and the user SR input de-asserted |
| `set` | `clock` (0 / 1), `ce`, `sr`, `d` (one bit per element, 8 bits each) | the inputs applied, then the clock set to the given level; a level change is an edge, no change is a level step |

The carrier applies the steps **in order, exactly, and nothing else**: no step inserted (no "warm-up" edge, no extra reset), no
step dropped, no reordering, no input held across a step it is not listed in. The clock is under the scorer's control only
(architecture 5.1 step 3); the user SR operations are steps of the sequence, never a side channel.

### 2.2 The shape of task-v0.2's stimuli (fixed by the public rule; `b4_landscape._stimulus`)

| stimulus | steps | readout cells after init |
|---|---|---|
| search | `init`, then K = 6 `set` steps with the clock alternating (an edge each), then 2 `set` steps at the final clock level (level steps) | 8 × 8 = 64 |
| holdout | the same shape with K = 8 and its own derivation (`HOLDOUT_SALT`) | 10 × 8 = 80 |

Per `set` step `ce` and `d` are uniform 8-bit draws and `sr` is sparse (each element asserted with probability 1/4). The carrier
does not know and need not know this rule: it receives a stimulus as a list and applies it. **A stimulus is never derived on the
executing side** — the `PublicTask` carries it (architecture 7.1); the executing side derives neither the landscape seed nor the
target from it, and the contract forbids any program on that side from computing a stimulus from a seed.

### 2.3 The application rule, per step (contract; the numbers are the carrier unit's)

For a `set` step the carrier (i) drives `ce`, `sr`, `d` to the listed values, (ii) waits a declared settle interval, (iii) sets the
slice clock to `clock`, (iv) waits a declared hold interval, (v) samples every element's Q (section 3.2). For an `init` step it
raises the declared initialisation mechanism (section 6.2) under the allowed context, waits its declared release interval, and
samples. The four intervals (settle, hold, release, sample offset) are **parameters of the carrier, declared in its identity page
and recorded in every trace header** (section 4.2); this document fixes that they exist and are recorded, not their values. They
are the same for every candidate of a session; a carrier that varied them per candidate would make the records incomparable.

### 2.4 The stimulus identity

The record carries `stimulus_sha256` over the canonical JSON of the step list (the model's digest today). The host checks it
against the task's; a mismatch is a finding against the carrier, never corrected. The carrier does not compute this digest to
decide anything — it is an audit field.

## 3. The raw readout — what the record contains

### 3.1 The visible fields (fixed; `ff_behaviour_v0.3.json` `observation_context.executing_side_visible`, `b4_ff_model.VISIBLE_STEP_KEYS`)

Per step, in this order and with no other key: `step` (the index, the init step 0), `kind`, `prev_event` (`none` / `init` /
`edge` / `level`), `clock_before`, `clock_after`, `edge` (`rising` / `falling` / `null` — of the **slice** clock as driven, never
per element), `ce`, `sr`, `d` (as applied), `q_before`, `q_after` (per element, in the fixed element order `AFF, A5FF, BFF, B5FF,
CFF, C5FF, DFF, D5FF`). This is exactly the host model's step record, so a board trace and a model trace validate under one
validator and replay through one port.

### 3.2 Q on silicon — a proposed decision (D1, for the owner)

The host model writes `null` for an element that has no readout under the hypothesis in that configuration (the x5FF elements
under a latch) or that was never initialised. **A physical carrier always has a Q to sample**: every element's output pin exists
whatever the configuration. The contract therefore says: **the carrier samples and records a physical 0 / 1 for every element at
every sample point and never writes `null`**; whether that value is *meaningful* (whether the element is a storage element in that
configuration) is the host's `applicable_semantics` diagnostic, applied after the fact and never on the executing side. The
consequence is accepted and named: a board trace and a model trace of the same configuration may differ exactly in the cells the
model leaves `null`; the verifier's comparison of a board trace with a model prediction (an adjudication step, not this contract)
must compare over the model's non-null cells only and report the rest as *unmodelled*, never as a mismatch and never as agreement.
The fitness rule (architecture section 7: a `None` cell scores nothing) then applies to the board's fitness **as the board computes
it from physical values** — on a board no cell is `None`, so the board's ceiling is the full mask; the host, scoring the same trace,
uses the same rule on the same values. Nothing in the fitness consults the decode.

### 3.3 The sample points (fixed by architecture 5.1 step 4)

`q_after` is sampled once per step after the hold interval; `q_before` is the previous step's `q_after` copied (step 0's
`q_before` is the carrier's sample before the initialisation mechanism is raised — a physical value that the model has no
counterpart for; the model's `q_before` at step 0 is all `null`, and D1's rule covers it). The init readout is step 0's `q_after`;
the SR readouts are the `q_after` of the steps whose `sr` is non-zero; the transparency readouts are the two level steps'.
No other sample is in the record; an extra sample the carrier takes for its own state machine is not an observation and is not
recorded.

### 3.4 What the readout is not

It is not compared with anything before it is written (architecture 5.1 step 4, 5.4; B1's `SEMANTIC_GATE = 0` carried over);
it is not filtered, majority-voted, debounced or retried by the carrier — one sample per point, as read; a sample the carrier
could not take (a transport fault, a watchdog) makes the whole observation a **refusal by its own name** (architecture 5.3: never
`DOMAIN`, which is the model's word; the carrier's refusals are its own fixed codes, listed by the carrier unit and validated as a
closed set) and never a partial trace.

## 4. The evidence fields — the three records and their prohibitions

### 4.1 Three records per candidate (architecture 5.3, restated as fields)

| record | written by | contains | never contains |
|---|---|---|---|
| the **observation** | the executing side, before any scoring | the header (4.2) and the steps (3.1) | a fitness, a target, an expected value, a semantic name, a decode |
| the **fitness** | the executing side, after the observation is durable | the fitness as the board computed it, the task digest, the observation's digest it was computed from | the target itself (the board holds the task; the record cites its digest), any per-cell expected value |
| the **decode** | the host only, after the session | the host's diagnostics (architecture 5.3's list) keyed to the observation's digest | — (it is never on the executing side at all) |

The adjudicator recomputes the fitness from the observation under the task and holds it to the fitness record; a mismatch is a
finding against the board, never corrected (B3's ledger discipline).

### 4.2 The observation's header (contract)

`schema`, `schema_version` (4.4); `source` — the carrier's identity as the instrument's identity page gives it (`VARIANT`
extended, not replaced: the B1 word `0x42310001` is refused by a v2 application, and a v2 word is refused by B1's — A4), the
bitstream digest, the image digest; `configuration` — the 21-bit genome in address order and its digest, the commit the host
signed (link 1), the staging re-read digest (link 2), the twelve-frame readback digest **before the initialisation mechanism and
after it** (link 3 twice; section 6.3); `init_event` — the mechanism's declared name and its recorded parameters (6.2);
`timing` — the four intervals of 2.3; `stimulus_sha256` (2.4); `nonce`, the sequence number and the session label as the
instrument's records carry them; `mapping_sha256` and `hypothesis_sha256` / `hypothesis_version` — **present for the host's
binding only and never read by the executing side**: the carrier copies them from the task as opaque strings and no program on
that side opens the files they name (the B1 guard set of architecture 5.4, re-aimed, is the witness).

### 4.3 The prohibitions (the A3 rule, as a validator)

The record validator (host side; also applied to every model trace) refuses an observation that carries, at any depth: a key
from the closed list `{target, expected, tables, table, truth, oracle, semantic, decode, primitive, init_value, srval, polarity}`
or any of the seven semantic names or the eight attestation tokens of architecture 5.4; a non-zero "table" word (B1's rule
iii-B1, kept: the signed payload's twelve table words are zero, and a reply carrying non-zero ones is refused by the host); a
`q` cell that is not the int 0 or the int 1 (type-exact: `0.0`, `1.0`, `true`, `false`, `null` are refused on a board trace;
`null` is accepted on a **model** trace only, and the record says which source wrote it — 3.2); a step whose key set is not
exactly 3.1's; a header missing any field of 4.2. A refused record is kept raw in quarantine with the findings (task-v0.2's
quarantine form, architecture 7.1) and the observation is `invalid`; nothing is dropped and nothing is repaired.

### 4.4 The schema file — a proposal (D3)

`b4/schemas/ff_observation_v1.schema.json`, versioned apart from `self_map_v3`; one schema for board and model traces with a
`source.kind` discriminator (`model` / `carrier`) that switches only the `null` rule of 4.3; the fitness record's schema beside
it. The names are a proposal for the owner; the rule that one validator reads both sources is the contract.

## 5. Isolation between candidates

### 5.1 The candidate cycle (contract; architecture 5.1 steps 1, 5, 6)

```
idle → sign + stage (link 1, 2) → write → readback (link 3, pre-init) → init mechanism → readback (link 3, post-init)
     → stimulus (2.3) → observation durable → fitness durable → restore base → readback of the base (link 3)
     → init mechanism once more (the same one, recorded) → scorer state machine to idle → next candidate
```

"Idle" is a defined state: every input low, the slice clock low, the scorer's step counter zero, the sample registers cleared,
no pending edge — and it is **observable**: the identity page exposes it as a status bit that the host reads between
candidates and records (the instrument's STATUS discipline). The stimulus restarts from its list at every candidate; nothing of a
previous candidate's inputs or samples is reused.

### 5.2 Why the init mechanism is raised twice

Once at the head of every stimulus (so that every candidate's observation begins from the mechanism's state, whatever the
previous candidate left) and once after the base is restored (so that the fabric between candidates is in a declared state, not in
the last candidate's). The second raise is **recorded** in the next candidate's header as `prev_candidate_restored = true` with
the base readback digest; a candidate whose predecessor's restore was not recorded is refused before it is signed.

### 5.3 The A5 negative test — its form (the injection is the carrier unit's)

A5 demands a demonstration, not an argument. The form: observe candidate *c* from idle (trace T₀); then observe a candidate *c′*
chosen to leave a known, maximal leftover (every element at the value opposite to *c*'s init readout, inputs asserted, the
clock at the opposite level); then observe *c* again (trace T₁). The test passes when T₁ = T₀ cell for cell; it fails when they
differ anywhere, and the difference's positions are the finding. On the bench *c′* is the bench's; on a board it is the same
*c′* under the qualification session's ruling. **What A5 does not show:** that no leftover state exists — only that the maximal
one the test injects does not reach the next record. A leftover the test did not inject is a finding of a later session, not a
refutation of A5.

## 6. INIT and SRVAL — two observations, two recoveries, A8 unresolved

### 6.1 The two values and where each is read (architecture 5.1 step 2, 5.2)

| value | the hypothesis's restore mechanism | observed at | the record's field |
|---|---|---|---|
| `INIT` (the `ff_init` relation, the `ZINI` bit) | an *initialisation event* — hypothesised to set Q := INIT on every applicable element and nothing else (`initialisation_event.assumption`, a model abstraction) | the init readout: step 0's `q_after`, before any edge, SR de-asserted | `steps[0].q_after` |
| `SRVAL` (the `ff_srval` relation, the `ZRST` bit) | a *user SR operation* — the element's own set / reset input, applied as a step of the stimulus | the SR readout: the `q_after` of a `set` step whose `sr` bit for that element is 1 | `steps[n].q_after[e]` where `steps[n].sr` has bit *e* |

The contract keeps them as **two observation points in one trace**, never as one value read twice, and never derives one from
the other: an init readout that equals the SR readout is a coincidence of values, not a demonstration that the two mechanisms are
one.

### 6.2 The initialisation mechanism — three candidates, one declared (D2, for the carrier unit under the owner)

The carrier **declares one mechanism** in its identity page and records it in every header (4.2, `init_event`). The candidates
this line knows of, each with its condition, none chosen here:

| candidate | what it is | the condition the carrier must state and the bench must witness |
|---|---|---|
| (a) a configuration-port restore command | the configuration logic's own command that loads every storage element from its configured initial value, issued through the port the instrument already uses for links 1–3 | that the command changes **no configuration frame** (link 3's readback equal before and after); that it reaches the site's elements and not only the carrier's own; what else it resets on the device, listed |
| (b) a global set / reset net raised by the carrier | the device's global initialisation net, driven from the carrier's own logic for a declared number of cycles | the same frame-invariance; the release timing relative to the slice clock (the allowed context: clock low, SR de-asserted); that the net reaches the pblock's elements |
| (c) a full or partial reconfiguration of the candidate | the candidate written again from the staged frames | that the written frames equal the staged ones (link 2 / 3); the cost (every candidate pays a write) and the fact that this mechanism cannot be raised *between* the write and the stimulus as a separate event |

The hypothesis models the event on the vendor's GSR abstraction (`initialisation_event`); whether (a), (b) or (c) realises that
abstraction on this die is **A8's question** and is not answered by the choice. The bench can witness the conditions in the
table; only the board, under its own ruling, can show which mechanism restores INIT (section 9).

### 6.3 Recovery after each mechanism — the two readbacks

Whatever the mechanism, the header carries link 3's readback digest **before** and **after** it (4.2). A mechanism that changed a
frame is a finding against the carrier (the candidate's configuration is no longer what was signed) and the observation is
`invalid`; the record is kept. This is the recovery contract for INIT: the fabric after the event is proved to be the signed
candidate, so the init readout is attributable to it. For SRVAL there is no separate recovery: the SR operation is a stimulus
step, and the next step's inputs are the recovery, recorded as any step.

### 6.4 The A8 demonstrations — their form (the result is the board's)

| demonstration | configurations | the witness |
|---|---|---|
| INIT restore | two candidates differing in one `ff_init` address only (the positive-control pair of section 7), the same stimulus | the init readouts of that element differ, and in the direction the mapping's Z reading predicts; the SR readouts of that element do **not** differ (the mechanism did not set SRVAL) |
| SRVAL restore | two candidates differing in one `ff_srval` address only, the same stimulus with an SR step on that element, `sr_mode` driven at both endpoints (architecture 9.3 clause 6) | the SR readouts of that element differ; the init readouts do **not** differ (the SR operation did not set INIT) |
| the cross | the four candidates above | no init readout tracks the `ff_srval` bit and no SR readout tracks the `ff_init` bit |

Each is a positive control in the sense of 5.2: a difference between two values of one bit, visible at a named readout.

### 6.5 What the claim loses under each A8 outcome (architecture A8, restated as cases)

| outcome on the board | the semantics the carrier may claim to observe | what 2c's claim says |
|---|---|---|
| both demonstrated | all seven | the full table of 5.2 |
| SRVAL only | six — `ff_init` **excluded**: every `ff_init` relation stays `unknown` on every address | the claim's universe keeps its 21 addresses (the eight `ff_init` addresses are still in the genome and still written) but the map carries no `ff_init` claim and the adjudicator scores none; the preregistration says so in one sentence |
| INIT only | six — `ff_srval` `unknown` | likewise, with the eight `ff_srval` addresses |
| neither | five | both excluded; whether a five-semantic B4-FF is worth running is the owner's, not decided here |
| the cross fails (a readout tracks the other bit) | the mechanism is not the one the hypothesis models | a finding against the hypothesis's `initialisation_event`, not against the carrier; the model's `ff_init` row is revised before any session (a hypothesis revision, its own unit) |

No outcome is a repair: the carrier is not re-tuned until a demonstration passes; a failed demonstration is reported and the
case above applies.

## 7. Positive controls — the quantifiers, the rule, the proposal, the data influence

### 7.1 The two quantifiers (architecture 5.2, A2 — unchanged)

For **each semantic** at least one positive control: an address that carries that semantic under the mapping and the hypothesis,
and a stimulus / background pair under which the bit's two values give different observations. For **each address and each
applicable context**, whether the sequence separates the two values, judged per address and per context, uncovered addresses
reported and their relations left `unknown`. The first is what the board must show before any mapping session (A2, under the
ruling that first loads the carrier); the second is K9's report.

### 7.2 The choice rule (proposed, D4)

Per semantic: the address with the highest (b′) covered / applicable fraction summed over the 32 pairs of the one archive read
(7.4), ties broken in the mapping's address order (`b4_ff_mapping.site_mapping().addresses`); for `ff_init` and `ff_srval` one
main-element and one x5FF-element address each, because under a latch the x5FF elements are not storage elements (the
`applicable_semantics` contract) and the main / x5FF split is the one place the per-element semantics behave differently; for the
chosen address, the background (the endpoint pair of architecture 9.3's fixed set) whose pair is applicable under (b′) and
covered in the most of the 32 pairs, ties the lowest `g0`. The rule is **data-informed** (7.4) and chooses among the model's
records; it chooses nothing the board will be judged by except *which* addresses the A2 demonstration uses.

### 7.3 The proposal (from `evidence/b4/unit_2c_obs_2026_10_21/positive_control_choice.txt`; a host-model record under v0.3)

| semantic | address | element | (b′) fraction over 32 pairs | endpoints g0 / g1 (hex, 21-bit genome) | covered at that background |
|---|---|---|---|---|---|
| `ce_mode` | `0x00400a01/52/7` | slice | 0.997 | `000000` / `000010` | 32 / 32 |
| `clock_mode` | `0x00400a01/52/19` | slice | 0.965 | `000000` / `000040` | 32 / 32 |
| `sr_kind` | `0x00400a00/52/16` | slice | 0.895 | `000008` / `000009` | 32 / 32 |
| `sr_mode` | `0x00400a01/52/3` | slice | 0.967 | `000000` / `000008` | 32 / 32 |
| `storage_kind` | `0x00400a1e/52/0` | slice | 1.000 | `000000` / `000400` | 32 / 32 |
| `ff_init` (main) | `0x00400a1f/51/3` | `AFF` | 1.000 | `000000` / `002000` | 32 / 32 |
| `ff_init` (x5FF) | `0x00400a1f/51/6` | `A5FF` | 1.000 | `000000` / `004000` | 32 / 32 |
| `ff_srval` (main) | `0x00400a1e/51/30` | `BFF` | 0.875 | `000008` / `000208` | 31 / 32 |
| `ff_srval` (x5FF) | `0x00400a01/52/15` | `C5FF` | 0.766 | `000008` / `000028` | 30 / 32 |

Read: the `sr_kind` and both `ff_srval` controls sit on the background `000008` (the `sr_mode` bit set — SR driven), as clause 6
of architecture 9.3 requires; the five slice-wide controls other than `sr_kind` and the two `ff_init` controls sit on the all-zero
base. The fractions are the model's distinguishability under the task stimuli of 32 seeds, **not** a probability that the board
distinguishes anything; a board result of 0 / 1 on any row is the A2 finding for that semantic, reported, never repaired by
choosing another address afterwards (the rule above is fixed before the board is touched; a change is a new version of this
section with its reason, as architecture 9.3 says of its set).

The stimulus of the A2 demonstration is **not** a task stimulus (those are drawn per pair from seeds the board never sees): it is
a fixed demonstration stimulus of the qualification plan — the same step grammar, K = 6, two level steps, an SR step on the
controlled element — written in the plan before the session and pinned by it; this document fixes the grammar and the
requirement, not the vectors.

### 7.4 The data influence, disclosed

The choice of 7.3 was made by reading the **committed** archive `evidence/b4/sim/b4-sim-4_20261021T065339Z` (`sim_report.json`
sha256 `01744b39598b10bbf7d4371be1e5b9355c08fc39a8877ef6957866ac8178f1fa`), the 32 `pair_*/k9.json` files only, through
`k9_address_record.py` (the per-address sums) and `positive_control_choice.py` (the rule applied), both read-only, both in the
unit directory with their outputs. What that reading did and did not touch: no seed was derived or printed; no archive, receipt,
registry, threshold, label or decision was changed; the pooled exclusion stays 2 690; `b4-sim-4`'s no-go stays the record it is.
What the influence means: the positive-control addresses were chosen where the **model** says the task stimuli discriminate best;
if the board agrees, that is a board result on model-favoured addresses, which is what A2 asks (a positive control is the easiest
case, by design); if the board disagrees, the model-favoured choice makes the disagreement harder to attribute to a poor address.
It does **not** mean the K9 fractions predict the board, and the sim-4 Ω − R record (negative) played no part in the choice.

## 8. The two holdouts — two axes, one contract

| | the stimulus holdout (task-v0.2, architecture 7.1 "the holdout's two axes" (a)) | the whole-site holdout (2c, architecture 4.3) |
|---|---|---|
| what is held out | a second stimulus (K = 8, its own derivation) that the search never scores against; the champion is scored on it once | a site instance whose addresses the FF cartographer's development never read |
| what it tests | behavioural consistency of the champion on vectors it was not tuned on — a research quantity, no threshold | that the map was built from observations, not from the developer's knowledge of this site — an engineering holdout, not a claim the truth was unseen (the certificate was produced on the same board family by the same toolchain) |
| who knows which is which | the engine (phase `holdout`); the carrier **does not**: it receives a configuration and a stimulus, as for any observation | the preregistration names the instance; the carrier is built for a site, so a second instance is a second build or a parameterised one — the carrier unit's, not decided here |
| the record | the same observation record (sections 3–4); the phase is the engine's field, not the carrier's | the same record on the holdout site, in its own session under its own ruling |
| status | fixed by task-v0.2 | **unresolved**: which instance (a second site of the family on `17A6`, or a second die `3671`, untouched) — the skeleton's section 3 |

The contract's point: **neither holdout changes what the executing side does or records.** A carrier that could tell a holdout
observation from a search one would have a side channel; the bench's negative scenario for this is "a holdout-phase observation
and a search-phase observation of the same configuration and stimulus produce byte-identical records apart from the nonce and
sequence fields".

## 9. Acceptance of a carrier v2 — the bench list and the board list (against A1–A8)

### 9.1 On the bench (iverilog, the carrier unit's deliverable; host-verifiable, no ruling)

| condition | scenario | witness |
|---|---|---|
| A1 | one candidate observed end to end inside one transaction: sign → stage → write → readback → init → readback → stimulus → record → fitness → restore → readback → init → idle, under the instrument's watchdog | the bench's transaction count 1; the watchdog not tripped; every link's digest equal |
| A3 | the bench emits a record for a known fabric and the host validator accepts it; the bench is made to emit a record with a `target` key, a non-zero table word, a `null` cell, a float cell, a missing header field — each refused by name (4.3) | the validator's findings, one per injected break |
| A4 | `VARIANT` reads the v2 word; the B1 application refuses it; the v2 application refuses the B1 word and the instrument's word | the identity scenarios |
| A5 | 5.3's form with the bench's maximal leftover | T₁ = T₀ |
| A6 | every B1 scenario that still applies (alive, SLVERR, write-once key, no-key, replay, unsigned, wrong commit, wrong key, reset) and one scenario per row of architecture 5.2 (seven), plus this contract's own: the stimulus applied exactly (a step inserted, dropped or reordered by the bench's fabric model is seen in the record), the two readbacks around the init mechanism, the holdout-indifference scenario of section 8, the init mechanism's frame-invariance (6.2's condition) | each scenario PASS, by name |
| A7 | the application's MMIO allowlist against the RTL's AXI-Lite decode — mismatches only (the standing check of this line — architecture A7 and `docs/b1_carrier_qualification.md` section 2's form: app reads ⊆ RTL reads, app writes ⊆ RTL writes) | the mismatch list empty |
| A2, A8 | **not bench-verifiable**: the bench's fabric is the hypothesis, so it can only reproduce the model | — |

### 9.2 On a board (under its own ruling; the qualification session of the carrier v2, B4Q, before any mapping session)

| condition | what the session shows | witness in the evidence |
|---|---|---|
| identity | `VARIANT` v2 over the PS path, the carrier and image digests, the timing parameters of 2.3 in the identity page | the IDENT record |
| links | the two baselines (the base before and after the session) equal, every record audited (the served words recompute the hashes), the closing unsigned / replay / wrong-key controls refused | B1Q's form (`docs/b1_carrier_qualification.md` 3.1), re-aimed |
| A2 | the nine pairs of 7.3, each observed at both endpoints under the demonstration stimulus: the readout differs at the named point for each semantic, or does not — reported per row | the nine pair records and the per-row verdict; an uncovered row is a finding, the semantic not claimed |
| A5 | 5.3's form on silicon with the same *c′* | T₁ = T₀ on the board |
| A8 | 6.4's three demonstrations | the per-case outcome of 6.5, written into the preregistration's claim |
| frame invariance | the readbacks before and after every init mechanism equal, on every record | the header digests |
| the board | `17A6` under the content-class interlock (`role ∈ {verify, sacrificial}`; a board with no role is refused); `F8B3` for the carrier's bring-up first (roadmap section 4), provisioned before use; nothing powered before the ruling | the interlock's record in the run log |

The session's result is a qualification record in B1Q's evidence-chain form (verified before it is pinned; a changed pin after it
re-qualifies): `qualified` is derived, never set. A HOLD session leaves a record of a failed qualification. **This document does
not plan that session**: the plan, the stimulus vectors, the ruling pair and the date are 2c's and the owner's.

## 10. Unresolved — each with the dependency that resolves it

1. **A8** — which mechanism of 6.2 restores INIT on this die, and whether the cross of 6.4 holds: the board, under the B4Q ruling.
2. **The mechanism the carrier declares** (6.2 (a) / (b) / (c)): the carrier-v2 design unit, with the bench witnessing its conditions.
3. **The four timing intervals** of 2.3: the carrier unit; recorded, never fixed here.
4. **The schema file's name and version** (4.4): the owner; the rule (one validator for both sources) is the contract.
5. **The A5 injection** (5.3's *c′*): the carrier unit for the bench, the B4Q plan for the board.
6. **The demonstration stimulus** of 7.3: the B4Q plan; its grammar is fixed here.
7. **Whether the owner accepts the choice rule and the nine pairs** of 7.2–7.3, and the disclosure of 7.4.
8. **The whole-site holdout's instance** (section 8): the preregistration.
9. **The legal-composition rule** for the 21 bits (architecture 4.2): 2c, a separate section; not this contract.
10. **Who executes the planted target configuration on a board** (architecture 7.1: *who executes the target configuration, which
    programs can see it and how it is isolated are open design questions of 2c*): under this contract the target observation is an
    observation like any other — the carrier sees a configuration and a stimulus — and the isolation is the harness's (task-v0.2's
    setup records); whether the harness runs on the host and drives the board, or the board program is handed `g*`, is undecided.
11. **N, `B*`, the prediction, the session partition, the calibrated rates, the lifecycle tool**: the skeleton's sections 7, 9, 11, 12 — untouched here.
12. **2c's freeze**: not by this document.

## 11. What this document does not do

It fixes no number that the board will be judged by (the fractions of 7.3 are the model's and are disclosed as such); it derives no
seed; it names no prediction; it partitions no session; it chooses no initialisation mechanism; it writes no RTL, bench, XDC or
schema file; it powers no board; it changes no archive, threshold, label, receipt or decision; it does not say that the hypothesis
holds on silicon or that A8 will pass; it does not freeze 2c; it does not authorise the carrier-v2 unit, 2d, routing, a push or a
merge. It gives the next units something written first to be judged against.

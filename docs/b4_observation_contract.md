# B4-FF — the observation contract between the executing side and the host (DRAFT v0.2, host-only, documents only, 2026-10-21)

> **Revision v0.1 → v0.2 (2026-10-21, the owner's HOLD on `e91650b`, R1–R3 with the D1–D4 rulings; documents only).** R1 — the
> "one object, one schema, one null rule" promise withdrawn: section 3 now separates a **common observation payload** from two
> **source provenance branches** (model, carrier), lists which fields exist for each, says how the existing model trace
> (`b4_ff_observation_trace` 0.2.0) is represented without fabricating board witnesses, and binds the source discriminator to trusted
> identity outside the record; D1 as ruled, with the model / board **scoring-domain limit** named on a retained counterexample
> (3.4); the A3 rule rewritten as **closed field sets with types** (4.3), the deny-list kept as defence in depth, the B1 zero-table
> check placed in the signed-reply layer; D3 as ruled (4.4). R2 — one coherent transaction per candidate (section 5): the single
> initialisation event **is the stimulus's step 0**; a recorded **cleanup phase** before the base restore; the first candidate's
> predecessor is the **opening baseline**; the order of pre-init sample, assertion / release, init sample and the two readbacks
> stated per mechanism (6.3); frame equality separated from Q-state restoration (5.4); the G6 limit kept visible (6.6); A5 given a
> compared projection, roles for the samples, a specified injected state with its witness, and the retention of faulted prefixes
> (5.6); D2 as ruled (6.2). R3 — A8's cross defined on the **same element and background** as a 2 × 2 factorial (6.4), the SR
> restore evidence distinguished from the SR = 1 input condition (6.5), the outcome table made conditional and the attribution of a
> failed cross left to independent evidence (6.7); the A2 pairs no longer asked to serve as the cross. D4 — the selection rule
> recorded as a **qualification-selection proposal that revises the architecture's recorded choice-7 rule**, with reason and
> precedence (7.2); the P3 "five slice-wide" → four (7.3). Section numbering kept so the skeleton's v0.0.3 pointers still land.
>
> **Standing: a draft contract, not a preregistration, not a ruling, not RTL.** Written under the owner's authorisation of
> 2026-10-21 (archived in `evidence/b4/unit_2c_obs_2026_10_21/owner_authorisation_2026_10_21.txt` with its source note), given
> after the PASS on the `b4-sim-4` execution unit (`196b358` / `fceedd6`). The purpose: unit 2c's skeleton
> (`docs/b4_preregistration.md`) leaves the observation contract of architecture section 5 as functional requirements and names, in
> its sections 5, 6 and 8, what 2c must fill before a carrier v2 can be designed. This document fills those items **as a contract**:
> what the executing side applies, what it records, what the record may never contain, how one candidate is kept apart from the
> next, how the two restore mechanisms of A8 are observed and recovered from, which addresses are proposed as positive controls and
> from what data, how the two holdouts differ, and against what a carrier v2 is accepted on the bench and on a board. **Outside the
> scope, and unresolved here as in the skeleton:** N, `B*`, the prediction, the session partition, A8 itself; 2c is **not frozen** by
> this document. Nothing here authorises a board, an RTL unit, a schema implementation, a change to `b4/`, a push or a merge.
>
> **What it is built from, all by reference.** `docs/b4_architecture.md` v0.2.0 (sections 2, 4.1–4.4, 5.0–5.5, 7, 7.1, 8, 9.1, 9.3;
> the v0.2.0 revision note's choice 7), `docs/b4_preregistration.md` v0.0.3 (sections 3, 5, 6, 8, 12), `docs/b1_carrier_contract.md`
> v0.1 (the links, the zero-table rule, `VARIANT`), `docs/b1_carrier_qualification.md` v0.3 (the qualification session's form and
> its evidence chain), `host/b1_records.py` (the signed-reply layer: `sign_reply.expected_tables`), `b4/hypothesis/ff_behaviour_v0.3.json`
> (`observation_context`, `initialisation_event`, `applicable_semantics`; G6), `b4/host/b4_ff_model.py` (`observe()`'s return — the
> model trace as it exists; the step grammar; the visible step keys), `b4/host/b4_landscape.py` (task-v0.2's stimulus shape and
> scoring rule), `docs/board_roles.md` (the content-class interlock), `docs/autonomous_cartography_roadmap.md` sections 4–5. The data
> read for section 7 is the committed `b4-sim-4` archive, through the two read-only scripts of `evidence/b4/unit_2c_obs_2026_10_21/`
> (7.4 discloses that influence); the counterexample of 3.4 is one retained observation of the same archive, read, not re-run.

## 0. Status of every section (the index the review reads first)

| section | what it fixes as a draft contract | what stays unresolved (named, not decided) |
|---|---|---|
| 1 position | what a contract is here and what it is not | — |
| 2 the stimulus | the step grammar, the task-v0.2 shape, the carrier's application rule, the stimulus identity | the electrical timing numbers (hold, settle, release, sample offsets) — the carrier-v2 unit's, with the bench as witness |
| 3 the raw readout | the common payload; the two provenance branches and their field lists; the legacy model trace's representation; D1; the scoring-domain limit | the board-study metric that would compare a board fitness with a model fitness (a 2c question, not this contract's) |
| 4 the evidence fields | the three records per candidate; the exact header sets per source with types; the source binding; the A3 closed-set rule; D3 | the schema file names (provisional, 4.4); the implementation (a later tool unit) |
| 5 the transaction | one initialisation per candidate = step 0; the phases in order; the cleanup phase and its witness; the opening baseline; frame equality versus Q restoration; A5's projection, roles, injected state and witness; faulted prefixes | the cleanup's and the injection's electrical realisation (the carrier unit); the bench's and the board's *c′* |
| 6 INIT and SRVAL | two observation points; D2; the per-mechanism order of samples and readbacks; the same-element 2 × 2 cross; the SR restore evidence; the G6 limit; the conditional outcome table and the attribution rule | **A8 itself**; the mechanism; which contexts a mechanism can observe |
| 7 positive controls | the quantifiers; the selection rule as a revision of choice 7 with reason and precedence (D4); the nine proposed pairs; the data influence | the board's own result; the fixed qualification stimulus and its predeclared conditions (the B4Q plan) |
| 8 the two holdouts | two axes; the carrier's indifference | the whole-site holdout's site instance |
| 9 acceptance | the bench list and the board list against A1–A8, each with its witness | the ruling that first loads a carrier; the board; the qualification session's plan |
| 10 unresolved | the list, each with its dependency | all of them |
| 11 what this document does not do | — | — |

## 1. Position — what a contract is here, and what it is not

Architecture section 5 says what a carrier v2 must *do* (the six-step observation of 5.1, the seven distinguishable behaviours of
5.2, the three records of 5.3, nobody in the loop in 5.4) and how it will be *accepted* (A1–A8 in 5.5). It does not say what the
executing side and the host owe each other **at the record**: which fields, in which encoding, under which prohibitions, so that a
record written on a board and a record the host model writes today share one **observation payload** that the host's verifier,
replay and adjudicator read through one entry point, while each keeps its own **provenance** and neither pretends to be the other.
This document is that contract. It sits between the architecture and the carrier-v2 design unit: the design is judged against it,
the preregistration cites it, and neither may silently change it (architecture section 9's revision rule applies: a change is a new
version with its reason).

It is **not**: a preregistration (nothing is frozen or pinned); a legal-composition rule for the 21 bits (architecture 4.2 — a
separate rule of 2c, not written here; "accepted by the model" is never read as "legal to write"); an RTL sketch, a timing budget or
a placement (the carrier-v2 unit's); a schema implementation (a later tool unit's; `b4/` is unchanged by this document); a statement
about silicon (every behaviour named here is the hypothesis's, unverified); a retagging of any existing trace or archive; an
authorisation of any board contact.

## 2. The stimulus — what the executing side applies

### 2.1 The step grammar (fixed; `b4_ff_model.STEP_KEYS`)

A stimulus is an ordered list of steps of exactly two kinds:

| kind | fields | meaning |
|---|---|---|
| `init` | none | the initialisation event (section 6), **at index 0 of every stimulus and nowhere else** (2.2; the model refuses it in any context other than the slice clock low and the user SR input de-asserted, and the transaction of section 5 guarantees that context at index 0) |
| `set` | `clock` (0 / 1), `ce`, `sr`, `d` (one bit per element, 8 bits each, ints) | the inputs applied, then the clock set to the given level; a level change is an edge, no change is a level step |

The carrier applies the steps **in order, exactly, and nothing else**: no step inserted (no "warm-up" edge, no extra reset, **no
second initialisation**), no step dropped, no reordering, no input held across a step it is not listed in. The clock is under the
scorer's control only (architecture 5.1 step 3); the user SR operations are steps of the sequence, never a side channel.

### 2.2 The shape of task-v0.2's stimuli (fixed by the public rule; `b4_landscape._stimulus`)

| stimulus | steps | readout cells after init |
|---|---|---|
| search | `init` (index 0), then K = 6 `set` steps with the clock alternating (an edge each), then 2 `set` steps at the final clock level (level steps) | 8 × 8 = 64 |
| holdout | the same shape with K = 8 and its own derivation (`HOLDOUT_SALT`) | 10 × 8 = 80 |

Per `set` step `ce` and `d` are uniform 8-bit draws and `sr` is sparse (each element asserted with probability 1/4) — so **the
last step may leave `sr`, `ce` or `d` non-zero and the clock at 1**; section 5.3's cleanup phase exists for that reason. The
carrier does not know and need not know the generation rule: it receives a stimulus as a list and applies it. **A stimulus is never
derived on the executing side** — the `PublicTask` carries it (architecture 7.1); the executing side derives neither the landscape
seed nor the target from it, and the contract forbids any program on that side from computing a stimulus from a seed.

### 2.3 The application rule, per step (contract; the numbers are the carrier unit's)

For a `set` step the carrier (i) drives `ce`, `sr`, `d` to the listed values, (ii) waits a declared **settle** interval, (iii) sets
the slice clock to `clock`, (iv) waits a declared **hold** interval, (v) samples every element's Q (3.3). For the `init` step
(index 0) the order is section 6.3's, per mechanism, with a declared **release** interval and a declared **sample offset**. The
four intervals are **parameters of the carrier, declared in its identity page and recorded in every carrier record** (4.2); this
document fixes that they exist and are recorded, not their values. They are the same for every candidate of a session; a carrier
that varied them per candidate would make the records incomparable.

### 2.4 The stimulus identity

The record carries `stimulus_sha256` over the canonical JSON of the step list (the model's digest today). The host checks it
against the task's; a mismatch is a finding against the carrier, never corrected. The carrier does not compute this digest to
decide anything — it is an audit field.

## 3. The raw readout — the common payload, the two provenance branches, D1 and the scoring-domain limit

### 3.1 The common observation payload (the part both sources write; `ff_behaviour_v0.3.json` `observation_context.executing_side_visible`, `b4_ff_model.VISIBLE_STEP_KEYS`)

| field | type | content |
|---|---|---|
| `config` | list of 21 ints in {0, 1} | the genome in the mapping's address order |
| `config_sha256` | hex string | over the canonical JSON of `config` |
| `stimulus` | list of steps per 2.1 | as applied |
| `stimulus_sha256` | hex string | 2.4 |
| `elements` | the fixed list `AFF, A5FF, BFF, B5FF, CFF, C5FF, DFF, D5FF` | the element order of every per-element vector |
| `initial` | `{clock: 0, ce: 0, sr: 0, d: 0, q: [...]}` | the state before step 0 — the model writes `q` as eight `null`; a carrier writes its pre-init sample (6.3) |
| `steps[]` | per step exactly the keys `step, kind, prev_event, clock_before, clock_after, edge, ce, sr, d, q_before, q_after` | `step` the index (0 the init step); `kind` per 2.1; `prev_event` ∈ {`none`, `init`, `edge`, `level`}; `edge` ∈ {`rising`, `falling`, `null`} of the **slice** clock as driven; `ce`, `sr`, `d` ints as applied; `q_before`, `q_after` lists of eight cells |

**The cell rule by source** (D1, 3.2): a cell is the int 0 or the int 1 on both sources; the model may additionally write `null`
(its `q_null_means`); a carrier never writes `null` (3.2). This is the *only* payload-level rule that differs by source; the
provenance branches (3.2) differ in far more, and that is where the v0.1 claim was wrong.

### 3.2 The two provenance branches (what exists for each source; nothing fabricated for the other)

| branch field | model (`b4_ff_observation_trace` 0.2.0, as `observe()` writes it today) | carrier (the v2 record; proposed) |
|---|---|---|
| discriminator | `visibility: "executing_side"` and the `fabric` block are what exist today; the branch is **recognised by the trusted context, not by a self-declared tag** (3.5) | `source.kind = "carrier"`, bound as 3.5 says |
| the hypothesis | `hypothesis: {path, sha256, version, fixture}` — the model's own input | **absent** (never on the executing side; the host binds the hypothesis to the *session*, in the manifest, not in the record) |
| the mapping | `mapping: {site, certificate, certificate_sha256}` — the model's own input | **absent** (the carrier is built for a site; the site identity is in its identity page and the manifest, not in a record it writes) |
| the fabric / the instrument | `fabric: {kind, effect_sha256, ...}` — the model's source identity (`truth` / `permuted` / `dropout` / a swap) | `instrument: {variant, carrier_sha256, image_sha256}` as the identity page gives them (A4) |
| the signed candidate | **absent** (the model signs nothing) | `commit`, `staging_readback_sha256` (link 2), `fabric_readback_sha256_pre_init`, `fabric_readback_sha256_post_init` (link 3 twice, 6.3), `nonce`, `seq`, `session` |
| the initialisation | the model's init step is an atomic assignment (`initialisation_event.assumption`); no mechanism field | `init_event: {mechanism, parameters}` (6.2) |
| the timing | none (the model has no time) | `timing: {settle, hold, release, sample_offset}` (2.3) |
| the transaction witnesses | none | `predecessor` (5.5), `cleanup` (5.3), `idle_status` (5.2) |
| `q_null_means` | the model's sentence | **absent** |

**The legacy model trace is represented as it is.** Every retained trace in `evidence/b4/sim/` and `evidence/b4/gate/` stays byte
for byte what the archive holds; the common payload of 3.1 is *already* a subset of its fields (`config`, `config_sha256`,
`stimulus`, `initial`, `elements`, `steps`), so a reader of the common payload reads it without any field added, renamed or
retagged; the model-branch fields are its existing `hypothesis`, `mapping`, `fabric`, `visibility`, `q_null_means`. **No board
witness is ever manufactured for a model trace** (no `commit`, no readback digest, no nonce, no timing: absent, not `null`), and
no carrier record ever carries a `hypothesis` or `mapping` block. A future envelope that wraps both (4.4) adds a layer around
the legacy trace; it does not rewrite it.

### 3.3 The sample points (fixed by architecture 5.1 step 4)

`q_after` is sampled once per step after the hold interval; `q_before` is the previous step's `q_after` copied; step 0's
`q_before` is `initial.q` — the carrier's **pre-init sample** (6.3), the model's eight `null`. The init readout is step 0's
`q_after`; the SR readouts are the `q_after` of the steps whose `sr` is non-zero (whether such a readout is *evidence of a
restore* is 6.5's question, not the sample's); the transparency readouts are the two level steps'. No other sample is in
`steps[]`; the cleanup phase's samples are in `cleanup` (5.3), and an extra sample the carrier takes for its own state machine is
not an observation and is not recorded.

### 3.4 D1 as ruled — the physical sample, the named fault, and the scoring-domain limit

**The rule.** A successfully obtained physical sample is recorded as the actual, type-exact int 0 or 1 — never converted to
`null` by a host decode, never discarded because the model would have no value there. An unmodelled value is neither fabricated
nor dropped: it is recorded and later *reported as unmodelled* (below). The inability to obtain a valid sample for an element at
a sample point is a **named fault** of the carrier (its own fixed code, a closed set listed by the carrier unit; never the model's
`DOMAIN`), and the observation is then `invalid` with every raw and partial sample already taken **retained** (5.6) — not a trace
with a hole, not a trace with a guessed cell. **The carrier must establish the sampling path**: that an element's Q is routed to
the sampler in every configuration of the universe is a condition the bench witnesses (9.1) and the board confirms (9.2); this
contract does not assert that every BEL and configuration automatically supplies a meaningful or usable Q.

**The scoring-domain limit, named on a retained counterexample.** The model's fitness rule (architecture 7: `f = Σ_{j∈M} w_j ·
[q_j ∈ {0,1} ∧ q_j = t_j]`) scores nothing for a `null` cell. In the committed archive, `evidence/b4/sim/b4-sim-4_20261021T065339Z/pair_000/k10.json`,
retained observation `id 20` (genome 1024 = `000400`, the `storage_kind` bit alone set, i.e. a latch configuration) has a q grid
whose four x5FF columns are `null` at every step: **32 of the 64 masked cells carry no value and the model's fitness is 24**. Any
physical 0 / 1 completion of those 32 cells under the same public target and weights scores between **24 and 56**. This is
arithmetic on one retained grid — not a board measurement, not a prediction of what a board would read, and not a claim that a
board produces either extreme. What it shows is that **counting raw physical values is a different scoring domain from the
model's**: a board fitness computed from physical 0 / 1 over the full mask and a model fitness computed with `null` excluded are
not the same quantity even for the same configuration, stimulus and target. The contract therefore says: (i) the board computes
its fitness from the physical values over the full mask, with no decode-based filtering in the board loop (architecture 5.3, 5.4);
(ii) the host, auditing a board record, recomputes that same board fitness from the record's values — the A1 / B3 recomputation —
and holds the board to it; (iii) the host separately **reports the unmodelled cells** of that configuration (the cells the model
would leave `null`, a host diagnostic from `applicable_semantics`) and the board's score restricted to the modelled cells, **labelled
as a diagnostic restriction and never called the board fitness**; (iv) no sentence of a report says that a board fitness and a model
fitness agree or disagree without naming the unmodelled-cell count. Whether a board study compares scores across that limit, with
what metric, is **a 2c decision, unresolved**, as N, `B*` and the prediction are; the old model results and the model's method are
untouched by this rule.

### 3.5 Binding the source to trusted identity (an untrusted record cannot grant itself `null`)

The validator does not take the branch from the record. For a **model** trace the expected source is the batch's formal source as
the harness pinned it (`b4_sim`'s source identity, the hypothesis and certificate digests from the root inputs); a trace is read
under the model branch only when that context names it. For a **carrier** record the expected source is the manifest's pinned
carrier (`carrier_sha256`, `VARIANT`, the image digest) and the instrument's identity page as the run log recorded it over the PS
path; the record's `instrument` block must equal that, and the signed-reply chain (`commit`, `nonce`, `seq`) must reconcile with
the notary log. A record that declares a branch its context does not grant it is refused by name; so a record cannot obtain the
model's `null` allowance by calling itself a model, and a model trace cannot pass as a board witness by carrying a `commit`.

### 3.6 What the readout is not

It is not compared with anything before it is written (architecture 5.1 step 4, 5.4; B1's `SEMANTIC_GATE = 0` carried over); it is
not filtered, majority-voted, debounced or retried by the carrier — one sample per point, as read; a fault during the stimulus
makes the whole observation `invalid` by the fault's name with the prefix retained (5.6), never a partial trace scored as if complete.

## 4. The evidence fields — the three records and the closed-set rule

### 4.1 Three records per candidate (architecture 5.3, restated as fields)

| record | written by | contains | never contains |
|---|---|---|---|
| the **observation** | the executing side, before any scoring | the common payload (3.1) and the source's provenance branch (3.2); for a carrier, the transaction witnesses (5) | a fitness, a target, an expected value, a semantic name, a decode |
| the **fitness** | the executing side, after the observation is durable | the fitness as the board computed it over the full mask (3.4 (i)), the task digest, the observation's digest it was computed from | the target itself (the board holds the task; the record cites its digest), any per-cell expected value, any restricted or filtered score |
| the **decode** | the host only, after the session | the host's diagnostics (architecture 5.3's list), the unmodelled-cell report of 3.4 (iii), keyed to the observation's digest | — (it is never on the executing side at all) |

The adjudicator recomputes the fitness from the observation under the task and holds it to the fitness record; a mismatch is a
finding against the board, never corrected (B3's ledger discipline).

### 4.2 The carrier observation's exact field set (contract; types; closed at every level)

Top level, **exactly** these keys and no other:

| key | type | binding |
|---|---|---|
| `schema`, `schema_version` | strings | 4.4 |
| `source` | `{kind: "carrier"}` | 3.5 |
| `instrument` | `{variant: hex string, carrier_sha256: hex, image_sha256: hex}` | the manifest's pins and the identity page (3.5) |
| `session`, `seq`, `nonce` | string, int, hex string | the instrument's records; the notary log |
| `commit` | hex string | link 1 — what the host signed |
| `staging_readback_sha256` | hex | link 2 |
| `fabric_readback_sha256_pre_init`, `fabric_readback_sha256_post_init` | hex, hex | link 3, taken as 6.3 orders them |
| `init_event` | `{mechanism: one of 6.2's names, parameters: a closed per-mechanism set}` | the identity page's declared mechanism (equal on every record of a session) |
| `timing` | `{settle: int, hold: int, release: int, sample_offset: int}` in the carrier's declared unit | the identity page (equal on every record of a session) |
| `predecessor` | 5.5's object | the previous transaction's witness |
| `config`, `config_sha256`, `stimulus`, `stimulus_sha256`, `elements`, `initial`, `steps` | 3.1 | the common payload |
| `cleanup` | 5.3's object | the transaction's cleanup witness |
| `idle_status` | int (the status word as read) | 5.2 |

`mapping_sha256` and `hypothesis_sha256` of v0.1 are **removed from the record**: the host binds them to the session in the
manifest (as B1 bound the frozen preregistration), so no program on the executing side has a reason to carry, copy or open them.

The model trace's field set is `observe()`'s as it exists (3.2) and is not changed by this document.

### 4.3 The A3 rule as a validator — closed sets, not a deny-list

A3 says the raw observation validates against a schema that forbids an expected value. v0.1 offered a list of forbidden keys; the
owner's review is right that a list forbids only what it names (`answer_bits` was not on it). The rule is therefore **closed
sets**: at every level of a carrier record the key set must equal the set of 4.2 (and of 3.1 for the payload, 5.3 for `cleanup`,
5.5 for `predecessor`) **exactly** — an extra key anywhere, whatever its name, is a refusal by name; every value must have the
listed type (type-exact: a cell is the int 0 or 1, not `0.0`, `1.0`, `true`, `false` or `null` on a carrier record; `null` only on
a model trace under the model branch, 3.5); every binding of 4.2 must hold. The v0.1 deny-list (`target`, `expected`, `tables`,
`truth`, `oracle`, `semantic`, `decode`, the seven semantic names, the eight attestation tokens) is **kept as defence in depth**
inside string values and nested keys of both branches — it catches a leak the closed set cannot see inside a value. Neither rule
is proof against an arbitrary semantic encoding inside a legitimate field (a stimulus chosen to spell an answer, a config digest
chosen as a signal): **that is what the source / binary / noninterference guards are for** (architecture 5.4; the B1 guard set
re-aimed at the FF names; the bench's noninterference scenarios of 9.1), and the validator is not claimed to replace them.

**The B1 zero-table check belongs to the signed-reply layer, not here.** `sign_reply.expected_tables` (`host/b1_records.py`) are
the twelve words of the signed payload; B1's rule iii-B1 refuses a reply whose words are not zero. A v2 carrier keeps that layer
unchanged (links 1–3, the nonce chain, the SipHash authorisation) and the check stays there; the raw observation record of 4.2 has
no table field at all, and the closed set refuses one.

A refused record is kept raw in quarantine with the findings (task-v0.2's quarantine form, architecture 7.1) and the observation is
`invalid`; nothing is dropped and nothing is repaired.

### 4.4 The schema files — provisional names (D3 as ruled)

`b4/schemas/ff_observation_payload_v1.schema.json` (the common payload of 3.1), `b4/schemas/ff_observation_carrier_v1.schema.json`
(4.2, referencing the payload), `b4/schemas/ff_observation_model_v1.schema.json` (the existing model trace's field set, referencing
the payload — a description of what `observe()` already writes, so that no legacy trace is rewritten), and the fitness record's
schema beside them. **One validator entry point dispatches to the typed branch the trusted context names** (3.5) and validates the
common payload under one rule; the source-dependent rules are **not only `null`**: they are the cell rule, the whole provenance
branch, the transaction witnesses, and the bindings of 3.5. The names are provisional and the owner's; nothing under `b4/` is
written or changed by this unit — the implementation is a later tool unit's.

## 5. The transaction — one candidate, one initialisation, one cleanup, one witness chain

### 5.1 The phases, in order (contract; A1's single transaction)

```
[predecessor witness in hand (5.5)]
P1  sign (link 1) → stage → staging re-read (link 2)
P2  write the candidate → fabric readback (link 3, PRE-INIT)            — for mechanism (c) see 6.3: P2 is the init event
P3  stimulus step 0 = THE initialisation event (6.3): pre-init sample → assert → release → init sample (= steps[0].q_after)
P4  fabric readback (link 3, POST-INIT)
P5  stimulus steps 1 … n, exactly (2.3)                                — the scored observation ends here
P6  observation durable → fitness durable
P7  CLEANUP (5.3): inputs to 0 in the stated order, clock to 0, sampled, recorded — not scored
P8  restore the base: write → fabric readback of the base (link 3)
P9  the base-state witness (5.4): the declared mechanism raised once in the permitted context → sample → recorded
P10 idle (5.2): the status word read and recorded
```

**There is exactly one initialisation event inside the scored observation, and it is step 0 of the stimulus.** v0.1's diagram
raised the mechanism before the stimulus *and* let the stimulus's step 0 raise it again; that double event is withdrawn. P9's
event is outside the scored observation, after the base is restored, and is recorded in P9's own witness, never in `steps[]`.

### 5.2 Idle, as a state and as a witness

"Idle" is a defined state: every input low, the slice clock low, the scorer's step counter zero, the sample registers cleared, no
pending edge, the fabric holding the base — and it is **observable**: the identity page exposes a status word whose idle bit the
host reads between candidates; the record carries the word as read (`idle_status`). A candidate is not signed while the previous
transaction's `idle_status` is not idle.

### 5.3 The cleanup phase (P7) — defined, recorded, not scored

The last stimulus step may leave `sr`, `ce`, `d` non-zero and the clock at 1 (2.2). The initialisation of P9 requires the clock low
and SR de-asserted. Cleanup is the recorded bridge, in this order: (1) `sr` → 0, `ce` → 0, `d` → 0 (one settle interval); (2) if the
clock is 1, clock → 0 (a falling edge — it is one, it is recorded as one, and it may capture on a falling-edge element: that is a
consequence of the stimulus's final state, not an observation, and it is why cleanup is kept apart from the scored steps);
(3) one hold interval; (4) sample. The `cleanup` object: `{steps: [ {clock_before, clock_after, edge, ce, sr, d, q_after} ... ],
final_q: [8 cells]}` — the same cell rule as 3.1, the same key closure as 4.3. Cleanup is **never** part of the fitness, never part
of K9 / K10's grids, never an input to the cartographer; its purpose is that P9's precondition is met *and witnessed*, not assumed.
SRVAL's "recovery" of v0.1 (the next step's inputs) is withdrawn: an SR operation inside the stimulus is recovered by nothing
inside the stimulus — the next step may assert SR again — and the transaction's recovery is P7–P9.

### 5.4 Frame equality is not Q restoration — two witnesses, kept apart

| witness | what it proves | what it does not prove |
|---|---|---|
| **frame equality** — link 3's readback of the base after P8 equal to the session's base readback digest; and the pre-init / post-init readbacks of a candidate equal to each other (6.3) | the configuration binding: the fabric holds the signed bits | anything about the storage elements' Q, which no frame readback reads |
| **Q-state restoration** — P9's sample after the mechanism on the base equal to the session's **base-state reference** (the opening baseline's P9 sample, 5.5) | that the transaction returned the elements to the declared base state, under the declared mechanism | that a *different* leftover would also have been cleared (5.6's limit); that the mechanism is the one the hypothesis models (A8, section 6) |

Both are required for the next candidate to be signed; a failure of either is a transaction fault with its name, the candidate's
records kept, the next candidate not signed until the session's stop rule says what follows (the B4Q plan's, not this
document's).

### 5.5 The predecessor — the opening baseline for the first candidate

Every carrier record carries `predecessor: {kind: "opening_baseline" | "candidate", seq: int | null, base_readback_sha256: hex,
base_state_sample: [8 cells], idle_status: int}` — the witnesses of P8–P10 of the previous transaction. The **opening baseline**
is the session's first transaction, on the base configuration itself: P1–P2 (the base signed and written — the base is a
candidate like any other for links 1–3), P3 (the mechanism raised, the pre-init and init samples taken), P4, **no stimulus steps**,
P7 (trivially — nothing to clean), P8 (the base is already there; the readback taken), P9 (the mechanism raised once more, the
sample taken — this sample is the session's **base-state reference**), P10. Its record is a carrier record with an empty
`steps[1:]`, flagged `opening_baseline: true` in `predecessor.kind` of the *first* candidate; the first candidate's predecessor is
therefore a real witness, not a nonexistent previous candidate. The closing baseline of B1Q's form is kept and compared with the
opening one (frame equality and Q-state restoration both).

### 5.6 The A5 negative test — projection, roles, the injected state, its witness, and the limit

**The compared projection.** Two observations of the same candidate under the same stimulus are *equal for A5* when their
`steps[]` are equal in every field of 3.1 **and** their `cleanup.final_q` are equal. **Excluded from the comparison**, because they
change by construction: `seq`, `nonce`, `predecessor`, `idle_status`, the readback digests (compared separately for equality to
the candidate's own — 5.4), and `initial.q` (below).

**The roles of the samples.** `initial.q` — the **pre-init sample** of step 0 — is the *leftover witness*: in the second observation
it is expected to show the injected state (it is where the leftover would be seen if the mechanism had not cleared it, and it
*must* differ from the first observation's for the injection to have been proved to reach the elements). `steps[0].q_after` — the
init sample — and everything after it are the *compared* samples: equality there is what A5 claims.

**The injected state, specified.** A5's second transaction observes a candidate *c′* and **deliberately omits P7–P9** (cleanup,
restore, base-state witness), so that *c*'s next observation starts from *c′*'s final state. *c′* is specified, not assumed
maximal: its final stimulus step leaves every element at the value opposite to *c*'s init sample on that element (`d` chosen
accordingly, `ce` asserted on every element, `sr` de-asserted, the clock at the level that captures on the configured edge), the
inputs held non-zero and the clock at 1 at the end. **Its witness** is *c′*'s own `cleanup`-less final sample recorded in
`steps[-1].q_after` **and** *c*'s second `initial.q`: the two must agree, or the injection did not take and the test is *not run*
(a finding of its own, not a pass). The test is then: *c*'s second observation equals the first under the projection above. A
pass establishes that **this** adversarial state does not reach the next record; it does not establish that no leftover state
can — a leftover the test did not inject is a finding of a later session, never a refutation of A5, and the contract says so in
the qualification record's wording.

**Faulted and incomplete prefixes.** An observation that faults mid-stimulus (3.4) or an A5 transaction that is stopped keeps
**every sample already taken, raw, in the record it was writing**, marked `invalid` with the fault's name and the step reached; it is
retained for audit, counted in the session's accounting, and **never** scored, never compared under A5, never a specimen.

## 6. INIT and SRVAL — two observations, the per-mechanism order, the same-element cross, A8 unresolved

### 6.1 The two values and where each is read (architecture 5.1 step 2, 5.2)

| value | the hypothesis's restore mechanism | the raw sample point | the record's field |
|---|---|---|---|
| `INIT` (the `ff_init` relation, the `ZINI` bit) | an *initialisation event* — hypothesised to set Q := INIT on every applicable element and nothing else (`initialisation_event.assumption`, a model abstraction) | the init sample: step 0's `q_after`, before any edge, SR de-asserted | `steps[0].q_after` |
| `SRVAL` (the `ff_srval` relation, the `ZRST` bit) | a *user SR operation* — the element's own set / reset input, applied as a step of the stimulus | the `q_after` of a `set` step whose `sr` bit for that element is 1 — **a sample point, not by itself evidence that a restore completed** (6.5) | `steps[n].q_after[e]` where `steps[n].sr` has bit *e* |

The contract keeps them as **two observation points in one trace**, never as one value read twice, and never derives one from the
other: an init sample that equals an SR sample is a coincidence of values, not a demonstration that the two mechanisms are one.

### 6.2 The initialisation mechanism — three candidates retained, one declared, none selected (D2 as ruled)

The carrier **declares one mechanism** in its identity page and records it in every header (`init_event`). The candidates this
line knows of, each with a condition the bench can witness, none chosen here:

| candidate | what it is | the bench-witnessable condition | what remains a feasibility question for the carrier design / qualification unit |
|---|---|---|---|
| (a) a configuration-port restore command | the configuration logic's own command that loads every storage element from its configured initial value, issued through the port the instrument already uses for links 1–3 | that the command changes **no configuration frame** (6.3's two readbacks equal); that it is issued and completes inside the transaction | availability through the instrument's port; its scope (the whole device, not only the pblock); what else it resets; whether it has any Q effect on this die at all |
| (b) a global set / reset net raised by the carrier | the device's global initialisation net, driven from the carrier's own logic for a declared number of cycles | frame invariance; the release timing relative to the slice clock (the permitted context: clock low, SR de-asserted) | whether the net reaches the pblock's elements; its interaction with the carrier's own state machine and the PS path |
| (c) configuration as the event | the candidate's write itself (P2) is the event; there is no separate assertion | that the written frames equal the staged ones (links 2–3) | that a write has any defined Q effect; the cost (every candidate pays a write — it does already); that the event **cannot be raised between P2 and the stimulus as a separate act**, so P9's base-state witness is the base *write* followed by a sample |

**Neither a command's name nor two equal frame readbacks establishes an event-to-Q effect** — that is A8's question (6.4), to be
shown on a board under its own ruling; the hypothesis models the event on the vendor's GSR abstraction, and whether (a), (b) or
(c) realises it on this die is not answered by the declaration. No mechanism is selected or authorised to run here.

### 6.3 The order of samples and readbacks at step 0, per mechanism (coherent with 5.1)

| | (a) command | (b) net | (c) configuration |
|---|---|---|---|
| P2 | write; **PRE-INIT readback** | write; **PRE-INIT readback** | the base readback before the write stands as the pre-write witness; the write **is** the event |
| P3.1 pre-init sample (`initial.q`) | after the pre-init readback, inputs at 0, clock 0 | the same | **before the write** (the base's last state — the predecessor's `base_state_sample` is the same sample; recorded again here as read) |
| P3.2 assert | the command issued | the net driven for the declared cycles | — (the write) |
| P3.3 release | the command's completion + the **release** interval | the net released + the **release** interval | the write's completion + the **release** interval |
| P3.4 init sample (`steps[0].q_after`) | after the **sample offset** | the same | the same |
| P4 | **POST-INIT readback**; must equal PRE-INIT | the same | **POST-INIT readback** = link 3 of the write; must equal the staging re-read (link 2) |

The four intervals are 2.3's; the two readbacks are 4.2's fields; for (c) `fabric_readback_sha256_pre_init` holds the base's
readback digest and the record says so (`init_event.parameters.pre_init_is_base_readback: true`). Frame equality here proves the
configuration binding only (5.4).

### 6.4 The A8 cross — a 2 × 2 factorial on the same element and background

**The design.** Choose one element *e* and one background *b* in which *e* is a flip-flop storage element with SR driven
(`storage_kind` = FF, `sr_mode` = driven; the other mode bits and the other elements' bits fixed at *b*'s values). Vary **only**
*e*'s `ff_init` bit and *e*'s `ff_srval` bit: four candidates `(INIT, SRVAL) ∈ {(0,0), (0,1), (1,0), (1,1)}`, everything else
identical — the same stimulus (the demonstration stimulus of the B4Q plan, with an SR operation on *e* that satisfies 6.5), the
same timing, the same mechanism, the same source.

**What the readouts should discriminate.**

| readout of *e* | tracks | must not track |
|---|---|---|
| the init sample (`steps[0].q_after[e]`) | the `ff_init` bit (the two candidates differing only in it differ here, in the direction the Z reading predicts) | the `ff_srval` bit (the two candidates differing only in it are equal here) |
| the SR-restore evidence sample (6.5) | the `ff_srval` bit | the `ff_init` bit |

Four candidates give both main effects and the interaction from one element in one context; v0.1's "the four candidates above"
(two pairs on different elements and backgrounds) could not, and is withdrawn. The A2 pairs of 7.3 **need not** serve as this
cross; they demonstrate distinguishability per semantic, which is a different question.

**Scope.** The cross is run at least once on a main element and once on an x5FF element (the two kinds the hypothesis treats
differently under a latch); in the FF storage context only (under a latch the x5FF elements are not storage elements, and the main
elements' init readout under an open inverted gate rests on G6 — 6.6); at the clock-mode value of *b*, with the other value a
second cross if the plan runs it, otherwise **reported as not demonstrated for that context**. What a passing cross establishes is
the demonstrated context (element kind, background, mechanism, stimulus, timing); it does not establish the seven semantics on
all addresses (6.7).

### 6.5 The SR restore evidence — SR = 1 is an input condition, not a completed restore

For a synchronous element the SR input acts at a capture event (the hypothesis: `sync_sr_acts_on_edge_only`, with SR priority
over capture); for an asynchronous one it acts at level. **Before mapping, `sr_kind` is unknown for the element**, so the
demonstration stimulus must make the restore complete under **either** kind: the SR bit of *e* asserted **across a capture edge**
of *e*'s clock (asserted on the step before the edge, held through the edge step), with the edge's `d` for *e* set to the value
**opposite** to the SRVAL the Z reading predicts (so that a capture of `d` and a restore to SRVAL are distinguishable). The
**SR-restore evidence sample** is the `q_after` of the edge step. A sample at a level step with SR asserted is an SR sample (6.1)
but not the evidence of a completed restore on a synchronous element. The latch context and `sr_mode = tied_low` are excluded as
architecture 9.3's clauses 4 and 6 exclude them: no SR restore evidence exists there and none is claimed. The qualification
vectors stay with the B4Q plan; these conditions do not.

### 6.6 The G6 limit, kept visible

Under v0.3 the model's init readout exists in every configuration **because the init step assigns atomically and settles no level
effect** (`initialisation_event.assumption`; G6): a latch whose gate is open at the init step still reads INIT in the model. A
device has no atomic step — a declared release interval, a sample offset or a readback **cannot be presumed to preserve that
transient**, and the carrier may be unable to observe an init value in that context at all. The contract's rule: the carrier
**reports the contexts in which its mechanism cannot observe an init value** (per element kind and per mode combination, from the
bench and the board), those contexts are **not demonstrated** and their `ff_init` relations stay `unknown`; **no unrecorded clock,
reset or input operation is added to force agreement with the model's atomic readout**. A8 stays unresolved by this section.

### 6.7 Outcomes — conditional, bounded, with attribution left to independent evidence

**Preconditions of every row.** A1–A7 met on the bench and, where they apply, on the board (9.2); the cross run in the contexts
of 6.4's scope; frame equality and Q-state restoration holding on every record (5.4). A row below is read *for the demonstrated
contexts only*; a context not run or not observable (6.6) is `unknown` whatever the row says.

| outcome of the cross (per demonstrated context) | the semantics the carrier may claim to observe there | what follows for 2c's claim |
|---|---|---|
| both main effects as 6.4 requires, no cross-tracking | `ff_init` and `ff_srval` observable in that context, with the other five | the claim may name all seven, **for the demonstrated contexts**; the undemonstrated contexts are listed with their relations `unknown` |
| SRVAL effect only | `ff_srval`; `ff_init` **not** observable: every `ff_init` relation `unknown` (A8's text) | the **semantic claim** and the **certificate-map scoring** of the adjudicator exclude `ff_init` (no precision / recall / polarity row for it); the **raw task fitness is untouched** — the eight `ff_init` bits stay in the genome, are written, and score through the behaviour they cause like any bit, with no masking; **whether that reduced claim is a preregistration 2c wants is 2c's decision**, not settled by keeping 21 writable bits |
| INIT effect only | likewise with `ff_srval` `unknown` | likewise |
| neither | five | both excluded from the semantic claim and the map scoring; fitness untouched; whether to run is the owner's |
| a readout tracks the other bit, or a main effect is absent where the other is present | **the context is marked `failed` and the affected qualification claim `unresolved`** | the evidence is preserved as it came; **no attribution is made by this table**: the cause may be the mechanism, the stimulus or timing, the instrumentation or implementation, or a model mismatch, and only independent evidence (a second mechanism, a bench reproduction, a different stimulus, a second die) can separate them; **no hypothesis revision and no carrier re-tuning follows automatically** from the outcome — each would be its own unit under its own ruling |

No outcome is a repair: the carrier is not re-tuned until a demonstration passes; a failed demonstration is reported and the row
above applies.

## 7. Positive controls — the quantifiers, the rule as a revision, the proposal, the data influence

### 7.1 The two quantifiers (architecture 5.2, A2 — unchanged)

For **each semantic** at least one positive control: an address that carries that semantic under the mapping and the hypothesis,
and a stimulus / background pair under which the bit's two values give different observations. For **each address and each
applicable context**, whether the sequence separates the two values, judged per address and per context, uncovered addresses
reported and their relations left `unknown`. The first is what the board must show before any mapping session (A2, under the
ruling that first loads the carrier); the second is K9's report.

### 7.2 The selection rule — a qualification-selection proposal that revises the recorded choice 7 (D4 as ruled)

**What the architecture already records** (the v0.2.0 revision note, choice 7): the positive-control pairs selected as *the
most-covered unique forced pair per semantic in the gate-1 K9 record, tie-break by `bit`, `g0`, `g1` numeric order, `ff_srval` /
`sr_kind` from SR-driven and old-applicable pairs only*, disclosed as tuning on gate-1 and not executed. **What this document
proposes instead**, and why: (i) the **source** is the `b4-sim-4` archive (task-v0.2, K9 (b′) the judged estimand), not gate-1
(task-v0.1, (b) only) — the rule should read the record produced under the protocol the carrier will be qualified against; (ii)
the selection is **address-first, by the pooled (b′) fraction over the 32 pairs** (ties in the mapping's address order), then the
background covered in the most pairs (ties the lowest `g0`) — because A2 asks for an *address* per semantic, and pooling over
seeds prefers an address that discriminates across stimuli over one that happens to be best for one seed; (iii) for `ff_init`
and `ff_srval` **one main-element and one x5FF-element address each**, because the hypothesis treats the two kinds differently
under a latch and the A2 demonstration should not rest on one kind. **Precedence:** if the owner accepts this proposal it
*replaces* choice 7's rule for the B4Q selection and the architecture's revision note is amended to say so with this reason; until
then choice 7's wording stands as the recorded rule and this is a proposal beside it. The historical choice is not rewritten; the
frozen K9 panel, both applicabilities, the host method and the old verdicts are unchanged.

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
of architecture 9.3 requires; the **four** other slice-wide controls and the two `ff_init` controls sit on the all-zero base. **What
the nine pairs are**: a data-informed DRAFT A2 proposal. **What they are not**: certified combinations (the legal-composition rule
of architecture 4.2 is not written here, and a pair is not made legal by being listed), board-observed effects, a whitelist, the
A8 cross (6.4), or a guarantee about the fixed qualification stimulus — the fractions are the model's distinguishability under the
*changing task stimuli* of 32 seeds, and the B4Q demonstration stimulus, a fixed sequence predeclared in that plan (the step
grammar of 2.1, K = 6 and two level steps, an SR operation on the controlled element satisfying 6.5), must show distinguishability
**under its own predeclared conditions**; the archive does not prove that future sequence. A board result of 0 / 1 on any row is the
A2 finding for that semantic, reported, never repaired by choosing another address afterwards (the rule is fixed before the board is
touched; a change is a new version of this section with its reason).

### 7.4 The data influence, disclosed

The choice of 7.3 was made by reading the **committed** archive `evidence/b4/sim/b4-sim-4_20261021T065339Z` (`sim_report.json`
sha256 `01744b39598b10bbf7d4371be1e5b9355c08fc39a8877ef6957866ac8178f1fa`), the 32 `pair_*/k9.json` files only, through
`k9_address_record.py` (the per-address sums) and `positive_control_choice.py` (the rule applied), both read-only, both in the unit
directory with their outputs; the owner's review of `e91650b` reran both (byte-identical outputs) and reselected the nine rows
independently with exact fractions. What that reading did and did not touch: no seed was derived or printed; no archive, receipt,
registry, threshold, label or decision was changed; the pooled exclusion stays 2 690; `b4-sim-4`'s no-go stays the record it is.
What the influence means: the positive-control addresses were chosen where the **model** says the task stimuli discriminate best;
if the board agrees, that is a board result on model-favoured addresses, which is what A2 asks (a positive control is the easiest
case, by design); if the board disagrees, the model-favoured choice makes the disagreement harder to attribute to a poor address.
It does **not** mean the K9 fractions predict the board, and the sim-4 Ω − R record (negative) played no part in the choice. The
counterexample of 3.4 is a second read of the same archive (one `k10.json` observation), disclosed likewise.

## 8. The two holdouts — two axes, one contract

| | the stimulus holdout (task-v0.2, architecture 7.1 "the holdout's two axes" (a)) | the whole-site holdout (2c, architecture 4.3) |
|---|---|---|
| what is held out | a second stimulus (K = 8, its own derivation) that the search never scores against; the champion is scored on it once | a site instance whose addresses the FF cartographer's development never read |
| what it tests | behavioural consistency of the champion on vectors it was not tuned on — a research quantity, no threshold | that the map was built from observations, not from the developer's knowledge of this site — an engineering holdout, not a claim the truth was unseen (the certificate was produced on the same board family by the same toolchain) |
| who knows which is which | the engine (phase `holdout`); the carrier **does not**: it receives a configuration and a stimulus, as for any observation | the preregistration names the instance; the carrier is built for a site, so a second instance is a second build or a parameterised one — the carrier unit's, not decided here |
| the record | the same carrier record (sections 3–5); the phase is the engine's field, not the carrier's | the same record on the holdout site, in its own session under its own ruling |
| status | fixed by task-v0.2 | **unresolved**: which instance (a second site of the family on `17A6`, or a second die `3671`, untouched) — the skeleton's section 3 |

The contract's point: **neither holdout changes what the executing side does or records.** A carrier that could tell a holdout
observation from a search one would have a side channel; the bench's negative scenario for this is "a holdout-phase observation
and a search-phase observation of the same configuration and stimulus produce records equal under 5.6's projection".

## 9. Acceptance of a carrier v2 — the bench list and the board list (against A1–A8)

### 9.1 On the bench (iverilog, the carrier unit's deliverable; host-verifiable, no ruling)

| condition | scenario | witness |
|---|---|---|
| A1 | one candidate observed end to end inside one transaction, P1–P10 of 5.1 in order, under the instrument's watchdog; the opening baseline of 5.5 first | the bench's transaction count 1; the watchdog not tripped; every link's digest equal; the phases' order in the bench log |
| A3 | the bench emits a record for a known fabric and the host validator (4.3) accepts it; the bench is made to emit a record with an extra key at each level (`answer_bits` among them), a `null` cell, a float cell, a missing header field, a `hypothesis` block, a non-idle `idle_status` — each refused by name | the validator's findings, one per injected break |
| A4 | `VARIANT` reads the v2 word; the B1 application refuses it; the v2 application refuses the B1 word and the instrument's word | the identity scenarios |
| A5 | 5.6's form: the injection's witness (*c′*'s final sample = *c*'s second `initial.q`), then the projection equal | the two agreements, by name |
| A6 | every B1 scenario that still applies (alive, SLVERR, write-once key, no-key, replay, unsigned, wrong commit, wrong key, reset) and one scenario per row of architecture 5.2 (seven), plus this contract's own: the stimulus applied exactly (a step inserted, dropped, reordered or **initialised twice** by the bench's fabric model is seen in the record); the cleanup phase recorded and the P9 precondition witnessed; the two readbacks around step 0 per the declared mechanism (6.3); the holdout-indifference scenario (8); the mechanism's frame invariance; **the sampling path** — every element's Q reaches the sampler in every mode combination the bench can set (3.4) | each scenario PASS, by name |
| A7 | the application's MMIO allowlist against the RTL's AXI-Lite decode — mismatches only (the standing check of this line, architecture A7; `docs/b1_carrier_qualification.md` section 2's form: app reads ⊆ RTL reads, app writes ⊆ RTL writes) | the mismatch list empty |
| A2, A8 | **not bench-verifiable**: the bench's fabric is the hypothesis, so it can only reproduce the model; the bench witnesses the mechanism's *conditions* (6.2), never its Q effect | — |

### 9.2 On a board (under its own ruling; the qualification session of the carrier v2, B4Q, before any mapping session)

| condition | what the session shows | witness in the evidence |
|---|---|---|
| identity | `VARIANT` v2 over the PS path, the carrier and image digests, the declared mechanism and the timing parameters in the identity page | the IDENT record |
| links and baselines | the opening and closing baselines (5.5) equal under both witnesses of 5.4, every record audited (the served words recompute the hashes), the closing unsigned / replay / wrong-key controls refused | B1Q's form (`docs/b1_carrier_qualification.md` 3.1), re-aimed |
| the sampling path | every element's Q sampled as a type-exact value on every record; no sampling fault | 3.4 |
| A2 | the nine pairs of 7.3, each observed at both endpoints under the demonstration stimulus: the readout differs at the named point for each semantic, or does not — reported per row | the nine pair records and the per-row verdict; an uncovered row is a finding, the semantic not claimed |
| A5 | 5.6's form on silicon with the plan's *c′* | the injection's witness, then the projection equal |
| A8 | 6.4's cross on a main element and an x5FF element, with 6.5's restore evidence, 6.6's unobservable contexts reported | the four-corner records per cross and the row of 6.7 that applies, written into the preregistration's claim as a *demonstrated-context* statement |
| frame equality and Q-state restoration | both witnesses of 5.4 on every record | the readback digests; the P9 samples against the base-state reference |
| the board | `17A6` under the content-class interlock (`role ∈ {verify, sacrificial}`; a board with no role is refused); `F8B3` for the carrier's bring-up first (roadmap section 4), provisioned before use; nothing powered before the ruling | the interlock's record in the run log |

The session's result is a qualification record in B1Q's evidence-chain form (verified before it is pinned; a changed pin after it
re-qualifies): `qualified` is derived, never set. A HOLD session leaves a record of a failed qualification. **This document does not
plan that session**: the plan, the demonstration stimulus and its predeclared conditions, the injected state, the ruling pair and
the date are 2c's and the owner's.

## 10. Unresolved — each with the dependency that resolves it

1. **A8** — which mechanism of 6.2 has an event-to-Q effect on this die, whether the same-element cross of 6.4 holds, and in which contexts (6.6): the board, under the B4Q ruling.
2. **The mechanism the carrier declares** (6.2 (a) / (b) / (c)), its availability, scope and reset effects: the carrier-v2 design unit, with the bench witnessing its conditions.
3. **The four timing intervals** of 2.3 and the cleanup's electrical realisation (5.3): the carrier unit; recorded, never fixed here.
4. **The schema files' names and the validator's entry point** (4.4): the owner for the names; a later tool unit for the implementation; nothing under `b4/` now.
5. **The A5 injected state** *c′* for the bench and for the board (5.6): the carrier unit and the B4Q plan.
6. **The demonstration stimulus** of 7.3 and 6.5 and its predeclared conditions: the B4Q plan; the grammar and the conditions are fixed here.
7. **Whether the owner accepts the selection rule as the revision of choice 7** (7.2) and the nine pairs (7.3): the owner; the architecture's note amended only on acceptance.
8. **The whole-site holdout's instance** (8): the preregistration.
9. **The legal-composition rule** for the 21 bits (architecture 4.2): 2c, a separate section; not this contract; the nine pairs are not made legal by 7.3.
10. **The board-study metric across the scoring-domain limit** (3.4): 2c, with N, `B*` and the prediction.
11. **Who executes the planted target configuration on a board** (architecture 7.1): under this contract the target observation is an observation like any other — the carrier sees a configuration and a stimulus — and the isolation is the harness's (task-v0.2's setup records); whether the harness runs on the host and drives the board, or the board program is handed `g*`, is undecided.
12. **N, `B*`, the prediction, the session partition, the calibrated rates, the lifecycle tool**: the skeleton's sections 7, 9, 11, 12 — untouched here.
13. **2c's freeze**: not by this document.

## 11. What this document does not do

It fixes no number that the board will be judged by (the fractions of 7.3 and the counterexample of 3.4 are the model's and are
disclosed as such); it derives no seed; it names no prediction; it partitions no session; it chooses no initialisation mechanism;
it writes no RTL, bench, XDC or schema file and changes nothing under `b4/`; it rewrites or retags no existing trace or archive; it
powers no board; it changes no archive, threshold, label, receipt, legal-write rule or decision; it does not say that the hypothesis
holds on silicon, that A8 will pass, or that a board fitness and a model fitness are comparable; it does not freeze 2c; it does not
authorise the carrier-v2 unit, 2d, routing, a push or a merge. It gives the next units something written first to be judged against.

# B4-FF — the observation contract between the executing side and the host (DRAFT v0.5, host-only, documents only, 2026-10-21)

> **Revision v0.4 → v0.5 (2026-10-21, the owner's fourth HOLD, on `6927c24`, two P2; documents only; targeted edits).** R1 — the
> mechanism-(c) **session root** no longer dereferences a predecessor it does not have: a **session-opening record** (`session_open`,
> 5.5, 4.1) taken before anything is signed binds the fabric as loaded to the pinned carrier's base-frame reference (a trusted
> manifest input), the root's pre-event readback binds to it (5.4's table, the `session_root` row split from `closed`), and a
> mismatch refuses the session (a retained non-success record). R2 — a **constant restore** (all four corners `restore` to one
> value) is an absent SRVAL effect (`srval_absent`, 6.7), landing in row 4 or 5, never row 1; the cross-tracking guard still fails a
> value that changes with INIT.
>
> **Revision v0.3 → v0.4 (2026-10-21, the owner's third HOLD, on `df3b65e`, R1–R4; documents only; targeted edits, not a
> rewrite).** R1 — 3.1 / 3.2 corrected to the code: the ledger's `trace_sha256` hashes the Q grid only; archived observations are
> projections with four separate commitments; a full raw return is retained only in quarantine; the view's grid digest is
> `q_grid_sha256`, a whole-record digest exists only for the new carrier record; the retained representations named with what each
> holds, what each digest covers and which adapter reads it; the `fabric` descriptor copied exactly. R2 — an invalid `O` has
> phase-dependent exact field sets with a bound stop location (4.2, 5.7). R3 — the readbacks renamed pre / post-**event**; the frame
> binding conditional on mechanism and predecessor context (5.4), with (c)'s pre-write sample and prior-configuration readback in
> 5.1 and 6.3 and *c′* as the prior configuration under J3; the view's `pre_init_state` carries a declared `context`. R4 — 6.5
> requires a valid reference and planted prior values, reads restore / capture / hold / inconsistent, and yields `unknown` for an
> invalid reference; 6.7 derives its quantities from the per-corner readings with a not-demonstrated row. The truncated sentence
> of 6.5 folded in.
>
> **Revision v0.2 → v0.3 (2026-10-21, the owner's second HOLD, on `d8ef6cf`, C1–C4 and one P3; documents only).** C1 — the
> "common payload" is now a **logical observation view** that every reader builds from a source's **raw wire format through a
> declared adapter** (3.1–3.2): the legacy model trace's `config` is an address → bit dictionary and its `config_sha256` is the
> digest of that dictionary under the model's own encoding — both kept as they are; the vector view and the stimulus digest are
> **derived** fields, labelled so, computed by the reader the way the ledger already computes them, and bound to the raw trace by
> `trace_sha256`; no legacy digest is reinterpreted under another encoding; the deny-list is **field-aware** (4.3): a closed-enum
> identity field such as the model's `fabric.kind = "truth"` is validated against its enum, never string-matched. C2 — one
> persistence scheme (5.1, 4.2): three objects per transaction — the **observation** `O` immutable at P6a, the **fitness** `F` at
> P6b binding `O`'s digest, the **transaction close** `X` at P10 binding `O`'s digest and holding the cleanup, the current base
> readback, the current base-state sample and the idle status; `predecessor` is a *reference* to the previous `X`, the opening
> baseline's predecessor is the **session root** (the terminating case), and an interrupted or faulted transaction keeps whichever
> objects exist with a non-success status (5.5–5.7). C3 — A5's projection excludes the pre-init state in **both** places it appears
> (`initial.q` and its copy `steps[0].q_before`), the injection witness is checked apart from the projection, the three outcomes
> (not demonstrated / pass / fail) are a decision table, and the injection is a **qualification-only protocol** with its own
> record types and statuses inside otherwise normal signed transactions (5.6). C4 — the A8 demonstration stimulus is **one fixed
> sequence for every corner containing two SR-restore episodes with `d = 0` and `d = 1`**, judged jointly (restore ⇔ the two
> episode readouts agree; capture ⇔ they differ) so no candidate-dependent `d` is needed (6.5); the outcome classification is a
> **precedence-ordered decision table** with no overlapping rows (6.7). P3 — task-v0.2's fixed stimuli end at clock 0 (2.2); the
> general grammar may end high and the cleanup handles the general case. Section numbering kept so the skeleton's pointers land.
>
> **Revision v0.1 → v0.2 (2026-10-21, the owner's HOLD on `e91650b`, R1–R3 with the D1–D4 rulings).** R1 — model / carrier
> format split; D1 as ruled with the scoring-domain limit named (3.4); A3 as closed sets; D3 as ruled. R2 — one initialisation per
> candidate = the stimulus's step 0; a cleanup phase; the opening baseline; frame equality apart from Q restoration; G6 visible; A5
> given a projection, roles and a specified injection; D2 as ruled. R3 — the A8 cross on the same element and background; SR
> restore evidence distinguished from SR = 1; the outcome table conditional, attribution left to independent evidence. D4 — the
> selection rule as a revision proposal of choice 7 (7.2). Earlier text is superseded where a later revision restates it.
>
> **Standing: a draft contract, not a preregistration, not a ruling, not RTL.** Written under the owner's authorisation of
> 2026-10-21 (archived in `evidence/b4/unit_2c_obs_2026_10_21/owner_authorisation_2026_10_21.txt` with its source note), given
> after the PASS on the `b4-sim-4` execution unit (`196b358` / `fceedd6`). The purpose: unit 2c's skeleton
> (`docs/b4_preregistration.md`) leaves the observation contract of architecture section 5 as functional requirements and names, in
> its sections 5, 6 and 8, what 2c must fill before a carrier v2 can be designed. This document fills those items **as a contract**.
> **Outside the scope, and unresolved here as in the skeleton:** N, `B*`, the prediction, the session partition, A8 itself; 2c is
> **not frozen** by this document. Nothing here authorises a board, an RTL unit, a schema implementation, a change to `b4/`, a push
> or a merge.
>
> **What it is built from, all by reference.** `docs/b4_architecture.md` v0.2.0 (sections 2, 4.1–4.4, 5.0–5.5, 7, 7.1, 8, 9.1, 9.3;
> the v0.2.0 revision note's choice 7), `docs/b4_preregistration.md` v0.0.3, `docs/b1_carrier_contract.md` v0.1,
> `docs/b1_carrier_qualification.md` v0.3, `host/b1_records.py` (`sign_reply.expected_tables`), `b4/hypothesis/ff_behaviour_v0.3.json`
> (`observation_context`, `initialisation_event`, `applicable_semantics`; G6), `b4/host/b4_ff_model.py` (`validate_config`,
> `observe()`'s return — the legacy wire format), `b4/host/b4_execution.py` (`sha256_json`, `genome_to_config`, `provenance_findings`), `b4/host/b4_engine.py` (the ledger
> entry: `trace_sha256 = sha256_json(grid)`), `b4/host/b4_target.py` (the target record), `b4/host/b4_replay.py` (`ENTRY_KEYS`), `b4/host/b4_landscape.py`
> (task-v0.2's stimulus shape), `docs/board_roles.md`, `docs/autonomous_cartography_roadmap.md` sections 4–5. The data read for
> section 7 is the committed `b4-sim-4` archive through the two read-only scripts of `evidence/b4/unit_2c_obs_2026_10_21/`; the
> counterexample of 3.4 is one retained observation of the same archive; the representation facts of 3.2 are those the owner's
> static probes of `d8ef6cf` and `df3b65e` read from a retained quarantine record (`float_return.json`) and from `pair_000`'s
> ledger and target records, re-read by this unit's static checks.

## 0. Status of every section (the index the review reads first)

| section | what it fixes as a draft contract | what stays unresolved (named, not decided) |
|---|---|---|
| 1 position | what a contract is here and what it is not | — |
| 2 the stimulus | the step grammar, the task-v0.2 shape (ending at clock 0), the application rule, the stimulus identity | the electrical timing numbers — the carrier-v2 unit's |
| 3 the raw readout | the logical view with its `context`; the retained representations, what each holds and what each digest covers; the adapters and their scope; the sample points; D1 and the scoring-domain limit; the source binding | the board-study metric across the limit (2c) |
| 4 the records | the three objects per transaction; the exact field set of each, with the phase-dependent sets of an invalid `O`; the field-aware A3 rule; D3 | the schema file names (provisional); the implementation (a later tool unit) |
| 5 the transaction | P1–P10 with one initialisation = step 0; the readiness table with (c)'s pre-write sample; the cleanup; the frame binding conditional on mechanism and predecessor context; the session-opening record and the session root; A5 as a decision table with a qualification-only injection protocol; faulted / interrupted retention with the stop location | the cleanup's and the injection's electrical realisation; the bench's and the board's *c′* |
| 6 INIT and SRVAL | two observation points; D2; the per-mechanism order and binding; the same-element 2 × 2 cross; the two-episode SR evidence with a validated reference and planted priors; G6; the per-corner readings → the quantities → the precedence-ordered table with a not-demonstrated row | **A8 itself**; the mechanism; the contexts a mechanism can observe |
| 7 positive controls | the quantifiers; the rule as a revision proposal of choice 7 (D4); the nine pairs; the data influence | the board's result; the B4Q stimulus's own conditions |
| 8 the two holdouts | two axes; the carrier's indifference | the whole-site instance |
| 9 acceptance | the bench and board lists against A1–A8 | the ruling, the board, the B4Q plan |
| 10 unresolved | the list | all of them |
| 11 what this document does not do | — | — |

## 1. Position — what a contract is here, and what it is not

Architecture section 5 says what a carrier v2 must *do* and how it is *accepted* (A1–A8). It does not say what the executing side
and the host owe each other **at the record**. This document is that contract: each source writes its **own raw wire format**,
immutable and digested as written; every reader (verifier, replay, adjudicator) builds one **logical observation view** from it
through a declared adapter, and reads both sources through that view. It sits between the architecture and the carrier-v2 design
unit; neither may silently change it (architecture section 9's revision rule applies).

It is **not**: a preregistration (nothing frozen or pinned); a legal-composition rule for the 21 bits (architecture 4.2 — 2c's,
not here); an RTL sketch or timing budget; a schema implementation (`b4/` is unchanged by this document); a statement about silicon
(every behaviour named is the hypothesis's, unverified); a retagging, re-encoding or re-digesting of any existing trace or archive;
an authorisation of any board contact.

## 2. The stimulus — what the executing side applies

### 2.1 The step grammar (fixed; `b4_ff_model.STEP_KEYS`)

| kind | fields | meaning |
|---|---|---|
| `init` | none | the initialisation event (section 6), **at index 0 of every stimulus and nowhere else**; the model refuses it in any context other than the slice clock low and the user SR input de-asserted, and the transaction of section 5 guarantees that context at index 0 |
| `set` | `clock` (0 / 1), `ce`, `sr`, `d` (ints, one bit per element) | the inputs applied, then the clock set to the given level; a level change is an edge, no change is a level step |

The carrier applies the steps **in order, exactly, and nothing else**: no step inserted (no warm-up edge, no extra reset, no second
initialisation), none dropped, none reordered, no input held across a step it is not listed in. The clock is under the scorer's
control only; the user SR operations are steps of the sequence, never a side channel.

### 2.2 The shape of task-v0.2's stimuli (fixed by the public rule; `b4_landscape._stimulus`)

| stimulus | steps | final clock | readout cells after init |
|---|---|---|---|
| search | `init` (index 0); K = 6 `set` steps, the clock toggling from 0 (an edge each); 2 `set` steps at the final level | **0** (K even) | 64 |
| holdout | the same with K = 8 (`HOLDOUT_SALT`) | **0** | 80 |

Per `set` step `ce` and `d` are uniform 8-bit draws and `sr` is sparse (each element asserted with probability 1/4): **the last step
may leave `sr`, `ce` or `d` non-zero**, which is what the cleanup (5.3) clears. The task-v0.2 stimuli end with the clock at 0; the
**general grammar** of 2.1 allows a stimulus to end at clock 1, and the cleanup handles that general case too — a clock at 1 is not
an outcome of the current fixed task shape. The carrier does not know the generation rule; **a stimulus is never derived on the
executing side** — the `PublicTask` carries it (architecture 7.1).

### 2.3 The application rule, per step (contract; the numbers are the carrier unit's)

For a `set` step: (i) drive `ce`, `sr`, `d`; (ii) wait the declared **settle** interval; (iii) set the slice clock; (iv) wait the
declared **hold** interval; (v) sample every element's Q (3.3). For the `init` step (index 0): 6.3's order per mechanism, with a
declared **release** interval and a declared **sample offset**. The four intervals are parameters of the carrier, declared in its
identity page and recorded in every observation (4.2); equal on every record of a session.

### 2.4 The stimulus identity

The **logical view** carries `stimulus_sha256` = `b4_execution.sha256_json(list(stimulus))` — sha256 over the canonical JSON
(`sort_keys`, separators `,` `:`) of the step list. The model's projections (ledger, target, memo) carry it as a written
commitment; the model's raw return has no `stimulus_sha256` field (it has `stimulus`), so there the reader **derives** it; a carrier
**writes** it over the same canonical encoding of the same list. The host checks the
view's value against the task's; a mismatch is a finding, never corrected.

## 3. The raw readout — the logical view, the retained representations and the adapters, D1 and the scoring-domain limit

### 3.1 The logical observation view (what every reader reads; built by an adapter of 3.2; never written as such by the model)

Per field: **R** = retained as the source wrote it, **D** = derived by the reader and labelled derived, **A** = absent.

| view field | type | M-raw | M-proj (ledger / target / memo) | C-O (carrier) |
|---|---|---|---|---|
| `source` | `{kind: "model" \| "carrier", representation: 3.2's name}` | from the trusted context (3.5) | from the trusted context | from the trusted context |
| `provenance` | the descriptor as written (model: `hypothesis`, `mapping`, `fabric`; carrier: `instrument`) | R | target: R (`provenance`); ledger / memo: A — only `provenance_sha256` R | R |
| `config_vector` | 21 ints, the mapping's address order | D (from the dictionary) | D (from `genome`, `genome_to_config`) | R (`config`, a list) |
| `genome` | int, bit *i* = address *i* | D | R | D |
| `config_sha256_raw` | `{value, encoding}` | R, encoding `raw-dict-default` | R, encoding `proj-dict-canonical` | R, encoding `list-canonical` |
| `stimulus` | the step list (2.1) | R | A — the pair's task stimulus is the reference, bound by `stimulus_sha256` | R |
| `stimulus_sha256` | hex, `sha256_json(list(stimulus))` | D | R | R |
| `elements` | the fixed list | R | D | R |
| `pre_init_state` | `{context: "idle" \| "a5_injection", clock, ce, sr, d, q}` | R (`initial`), `context` D = `idle` | D (`q` eight `null` by the model's rule) | R (`initial`; under `idle` the inputs are 0 by 5.2's checked precondition; under `a5_injection` the **held** values, 5.6 J3) |
| `steps[]` | 3.3's keys | R | `q_after` R (= `q_grid[step]`); every other key D from the task's step list and the previous `q_after` | R |
| `q_grid_sha256` | hex, `sha256_json([q_after per step])` | D | R — **this is the ledger's `trace_sha256`**, which hashes the Q grid and nothing else | D |
| `record_sha256` | hex, a whole-record digest | D (over the retained file bytes, if wanted) | **A — no whole-record digest of an archived observation exists, and none is claimed** | R (`observation_sha256`, **new**, 4.1) |

The cell rule by source: an int 0 or 1 on both; the model may additionally write `null`; a carrier never does (3.4). A view is
rebuilt on every read, never stored in place of the record, and a **D** field is never presented as something the source wrote.

### 3.2 The retained representations — what each holds, what each digest covers, and which adapter reads it (copied from the code)

| name | where | fields | digests and **exactly what each covers** |
|---|---|---|---|
| **M-raw** — `observe()`'s return, `b4_ff_observation_trace` 0.2.0 | **quarantine only** (a refused return kept whole, e.g. `float_return.json`); the engine archives no raw return | `schema, schema_version, visibility, q_null_means, hypothesis, mapping, fabric, config` (**a dictionary** address → bit, the 21 addresses), `config_sha256, stimulus, initial, elements, steps`; **no `stimulus_sha256` field** | `config_sha256` = `sha256(json.dumps(config_dict, sort_keys=True))`, Python's **default separators** |
| **M-ledger** — the engine ledger entry (`b4_engine`; `b4_replay.ENTRY_KEYS`) | every `arm_*.result.json` | `seq, phase, genome, genome_hex, config_sha256, provenance_sha256, fixture, stimulus_sha256, trace_sha256, q_grid, fitness, none_cells, map_*` — **a projection**: no dictionary, no `initial`, no `stimulus`, no full `steps`, no descriptor blocks | `config_sha256` = `sha256_json(genome_to_config(genome, addresses))` (canonical JSON over the **reconstructed** dictionary — a different value from M-raw's for the same configuration); `provenance_sha256` = `sha256_json({hypothesis, mapping, fabric})`; `stimulus_sha256` = `sha256_json(list(stimulus))`; **`trace_sha256` = `sha256_json(q_grid)`** |
| **M-target** — `b4_target`'s record | `target_search.json`, `target_holdout.json` | as M-ledger plus `provenance` (the descriptor retained), `fabric_kind` | as M-ledger |
| **M-memo** — the K9 / K10 observation | `k9.json`, `k10.json` `observations[]` | `id, genome, genome_hex, config_sha256, provenance_sha256, fixture, fabric_kind, stimulus_sha256, trace_sha256, q_grid` | as M-ledger |
| **C-O** — the carrier observation (proposed) | the B4Q / session evidence | 4.2 | `config_sha256` canonical JSON over the list; `stimulus_sha256` as 2.4; `observation_sha256` over the whole sealed `O` — the only whole-record digest in this contract, and new |

**Four separate commitments, not one.** An archived entry binds its configuration by `config_sha256`, its stimulus by
`stimulus_sha256`, its source by `provenance_sha256` (checked against the batch's formal source, 3.5) and its Q grid by
`trace_sha256`; changing one leaves the others unchanged (the owner's probe on `pair_000`: `trace_sha256` =
`5cd4aa74…` = the Q-grid digest, unchanged under a changed stimulus commitment). The archive verifier and the replay check each
commitment against its reference and the files against the archive's own digests. **Nothing in the archive is a full raw record or
a hash of one.**

**Adapters and scope.** The **M-raw adapter** reads a full return (quarantine, or a future batch that chooses to retain returns).
The **M-proj adapter** reads a ledger / target / memo entry **with the pair's task** (its stimulus and addresses) and derives every
step key but `q_after`, the pre-init state and the configuration, each labelled derived; it never claims a raw record was retained.
Historical projections keep **their recorded version's reader** (`b4_replay`, `b4_sim_verify`) as the verification authority; the
view is a reading aid beside it. The **carrier adapter** reads `C-O`. No adapter rewrites, re-encodes, re-digests or retags
anything under `evidence/`; every digest is verified under the encoding its representation declares and never recomputed under
another.

**The `fabric` descriptor, copied exactly** (`b4_execution.provenance_findings`, `b4_ff_model.Fabric.source`): keys exactly
`kind, effect_sha256, dropout_sha256, dropout_count, seed`; `kind ∈ {truth, permuted, dropout, custom}` (`SOURCE_KINDS`); the two
digests 64-hex; `dropout_count` an int; `seed` an int or `null`. The hypothesis's fixture / swap identity is **separate** —
`hypothesis = {path, sha256, version, fixture: bool}`; a swap fixture is another hypothesis file named there, never a fabric kind.
`mapping` = exactly `site, certificate, certificate_sha256`.

### 3.3 The sample points (fixed by architecture 5.1 step 4)

`q_after` is sampled once per step after the hold interval; `q_before` is the previous step's `q_after` copied; **`steps[0].q_before`
is a copy of `initial.q`** — the pre-init state appears in those two places and nowhere else (this matters for A5, 5.6). The init
readout is `steps[0].q_after`; the SR readouts are the `q_after` of steps whose `sr` is non-zero (whether such a readout is *evidence
of a restore* is 6.5's question); the transparency readouts are the level steps'. The cleanup's samples are in `X` (4.2), not in
`steps[]`; an extra sample the carrier takes for its own state machine is not an observation and is not recorded.

### 3.4 D1 as ruled — the physical sample, the named fault, and the scoring-domain limit

**The rule.** A successfully obtained physical sample is recorded as the actual, type-exact int 0 or 1 — never converted to `null`
by a host decode, never discarded because the model would have no value there. An unmodelled value is neither fabricated nor
dropped: it is recorded and later reported as *unmodelled* (below). The inability to obtain a valid sample for an element at a
sample point is a **named fault** of the carrier (a closed set of codes listed by the carrier unit; never the model's `DOMAIN`), the
observation is `invalid` with every sample already taken **retained** (5.7). **The carrier must establish the sampling path**: that
an element's Q reaches the sampler in every configuration of the universe is a bench condition (9.1) confirmed on the board (9.2);
this contract does not assert that every BEL and configuration automatically supplies a meaningful or usable Q.

**The scoring-domain limit, on a retained counterexample.** The model's fitness rule (architecture 7) scores nothing for a `null`
cell. In `evidence/b4/sim/b4-sim-4_20261021T065339Z/pair_000/k10.json`, retained observation `id 20` (genome 1024 = `000400`, the
`storage_kind` bit alone — a latch configuration) has `null` in the four x5FF columns at every step: **32 of the 64 masked cells carry
no value and the model's fitness is 24**; any physical 0 / 1 completion of those 32 cells under the same target and weights scores
between **24 and 56**. Arithmetic on one retained grid — not a board measurement, not a prediction, not a claim that a board produces
either extreme. The contract therefore says: (i) the board computes its fitness from the physical values over the full mask, with no
decode-based filtering in the board loop; (ii) the host recomputes **that same board fitness** from the record's values and holds the
board to it; (iii) the host separately reports the **unmodelled cells** of that configuration (a host diagnostic from
`applicable_semantics`) and the board's score restricted to the modelled cells, **labelled a diagnostic restriction and never called
the board fitness**; (iv) no report sentence says a board fitness and a model fitness agree or disagree without the unmodelled-cell
count. Whether a board study compares scores across that limit, with what metric, is **a 2c decision, unresolved**; the old model
results and method are untouched.

### 3.5 Binding the source to trusted identity (an untrusted record cannot grant itself `null`)

The reader does not take `source.kind` from the record. For a **model** trace the expected source is the batch's formal source as
the harness pinned it (`b4_sim`'s source identity; the hypothesis and certificate digests from the root inputs), and the
descriptor (M-raw's blocks; a projection's `provenance_sha256`) must equal it; a record is read under the model branch, in the
representation the context names, only when that context names it. For a **carrier** record the
expected source is the manifest's pinned carrier (`carrier_sha256`, `VARIANT`, the image digest) and the identity page as the run
log recorded it; the raw `instrument` block must equal that, and `commit`, `nonce`, `seq` must reconcile with the notary log. A
record that declares or implies a branch its context does not grant is refused by name.

### 3.6 What the readout is not

Not compared with anything before it is written (architecture 5.1 step 4, 5.4; B1's `SEMANTIC_GATE = 0` carried over); not
filtered, voted, debounced or retried — one sample per point, as read; a fault during the stimulus makes the observation `invalid`
by the fault's name with the prefix retained (5.7), never a partial trace scored as complete.

## 4. The records — three objects per transaction, their exact fields, immutability and the field-aware A3 rule

### 4.1 The objects (architecture 5.3's three records, plus the transaction close that C2 required)

| object | written by | exists from | immutable at | its digest covers | binds |
|---|---|---|---|---|---|
| **`O` the observation** | the executing side | P3 (header) … P5 (last step) | **P6a** — before any scoring | the whole raw `O` (4.2) → `observation_sha256` | `predecessor` → the previous `X` (a reference, 5.5) |
| **`F` the fitness** | the executing side | P6b | P6b | `{observation_sha256, task_digest, fitness}` | `observation_sha256` |
| **`X` the transaction close** | the executing side | P7 (first cleanup sample) … P10 | **P10** (or at the fault, 5.7) | the whole raw `X` (4.2) → `close_sha256` | `observation_sha256`; the next `O.predecessor` → `close_sha256` |
| **`session_open`** the session-opening record (5.5) | the runner, with the carrier | before the root is signed | at its write | `{instrument, startup_readback_sha256, base_frames_reference_sha256, status}` | the root's mechanism-(c) pre-event readback (5.4) |
| the **decode** | the host only, after the session | — | — | keyed to `observation_sha256` | — |

`O` is never extended after P6a; the values that only exist later (the cleanup, the current base readback, the current base-state
sample, the idle status) live in `X` and **nowhere in `O`**. The adjudicator recomputes `F.fitness` from `O` under the task; a
mismatch is a finding against the board, never corrected.

### 4.2 The exact field sets (carrier; closed at every level; types)

**`O` — the observation** (top level, exactly these keys):

| key | type | binding |
|---|---|---|
| `schema`, `schema_version` | strings | 4.4 |
| `instrument` | `{variant: hex, carrier_sha256: hex, image_sha256: hex}` | the manifest and the identity page (3.5) |
| `session`, `seq`, `nonce` | string, int, hex | the instrument's records; the notary log |
| `commit` | hex | link 1 |
| `staging_readback_sha256` | hex | link 2 |
| `fabric_readback_sha256_pre_event`, `fabric_readback_sha256_post_event` | hex, hex | link 3 twice; **what each must equal depends on the mechanism and the predecessor context** (5.4, 6.3) |
| `init_event` | `{mechanism: enum of 6.2, parameters: closed per mechanism}` | the identity page's declared mechanism |
| `timing` | `{settle, hold, release, sample_offset}` ints in the declared unit | the identity page |
| `predecessor` | `{kind: "session_root" \| "closed" \| "a5_injection", seq: int \| null, close_sha256: hex \| null}` | 5.5, 5.6 |
| `config` (list of 21 ints), `config_sha256`, `stimulus`, `stimulus_sha256`, `elements`, `initial`, `steps` | 3.2's carrier column | the payload |
| `status` | `"complete"` | — |

**`O` — the observation, invalid (a stop in P1–P5): phase-dependent exact sets.** `status = "invalid"` and
`fault = {code: enum, phase_reached: "P1" | "P2" | "P3" | "P4" | "P5", step_reached: int | null}`; the key set is **exactly** the
always-present keys **plus the keys of every phase completed before the stop**, and nothing of a later phase — absent, never
`null`, never a placeholder digest, never copied from another transaction:

| stop in | always present | present (acquired before the stop) | absent |
|---|---|---|---|
| P1 | `schema`, `schema_version`, `instrument`, `session`, `seq`, `nonce`, `predecessor`, `config`, `config_sha256`, `stimulus`, `stimulus_sha256`, `elements`, `init_event`, `timing`, `status`, `fault` | `commit`, `staging_readback_sha256` **if** link 1 / 2 completed | both fabric readbacks, `initial`, `steps` |
| P2 | the same | `commit`, `staging_readback_sha256`; `fabric_readback_sha256_pre_event` **if** the readback completed; for mechanism (c) also `initial` (the pre-write sample, 6.3) if taken | `fabric_readback_sha256_post_event`, `steps` (and `initial` where not yet taken) |
| P3 | the same | the P2 fields; `initial` if the pre-init sample was taken; `steps` = `[]` or `[steps[0]]` as acquired (`step_reached` 0) | `fabric_readback_sha256_post_event` |
| P4 | the same | the P3 fields with `steps = [steps[0]]` | `fabric_readback_sha256_post_event` if the readback did not complete |
| P5 | the same | everything of a complete `O` except that `steps` is the prefix `steps[0 .. step_reached]` as acquired | — |

`observation_sha256` is computed over the invalid `O` as sealed (5.7); the owner's static example — a sampling fault during P3,
before P4 — is a P3 row: the pre-event readback present, the post-event readback absent, `steps` the acquired prefix.

**`F` — the fitness**: exactly `{schema, schema_version, observation_sha256, task_digest, fitness: int}`; exists only when
`O.status = "complete"`.

**`X` — the transaction close**: exactly `{schema, schema_version, observation_sha256, seq, cleanup, base_readback_sha256,
base_state_sample, idle_status, status}` with `cleanup = {steps: [{clock_before, clock_after, edge, ce, sr, d, q_after}...],
final_q: [8 ints]}` (5.3), `base_readback_sha256` the P8 readback (link 3 of the restored base), `base_state_sample` the P9 sample
(8 ints), `idle_status` the P10 word, `status ∈ {"closed", "injection_open", "faulted"}` and with `faulted`: `fault: {code,
phase_reached}` (5.6, 5.7). Fields that a faulted `X` could not take are **absent** (the closed set is "exactly the keys that the
status allows"), never `null`, never filled from another transaction.

The model trace's raw field set is `observe()`'s (3.2) and is not changed by this document.

### 4.3 The A3 rule as a validator — closed sets, typed fields, and a field-aware deny-list

**Closed sets.** At every level of a carrier `O`, `F` or `X` the key set must equal 4.2's **exactly** — an extra key anywhere,
whatever its name (`answer_bits` among them), is a refusal by name; every value has the listed type (type-exact: a cell is the int 0
or 1, not `0.0`, `1.0`, `true`, `false` or `null`); every binding of 3.5 and 4.2 holds. A legacy model trace is validated against
*its own* raw field set (3.2) under the model branch, where `null` cells are allowed.

**Field-aware values.** Every string-valued field of both branches is one of three kinds, and the validator treats each by its kind:

| kind | fields | the rule |
|---|---|---|
| **enum** | model `fabric.kind` (`truth`, `permuted`, `dropout`, `custom` — `SOURCE_KINDS`; a hypothesis swap is not a fabric kind), `visibility`; carrier `init_event.mechanism`, `O.status`, `X.status`, `predecessor.kind`, `fault.code` | the value must be a member of the closed enum; **an enum member is never string-matched against the deny-list** — the model's formal source identity `fabric.kind = "truth"` is legitimate metadata, not a leaked answer |
| **fixed text** | model `q_null_means`, `schema`; carrier `schema` | equality to the fixed text |
| **identity** | digests (hex of fixed length), paths (`hypothesis.path`, `mapping.certificate`, `fabric.effect_sha256`), `session`, `nonce` | the type and length rule, and the binding of 3.5 |

There is **no free-text field** in either branch; so the v0.1 deny-list (`target`, `expected`, `tables`, `oracle`, `semantic`,
`decode`, the seven semantic names, the eight attestation tokens) applies to **key names at every level** (defence in depth behind
the closed set) and to nothing else. What no key list or value rule can see — a stimulus or a digest chosen to spell an answer —
is the job of the source / binary / noninterference guards (architecture 5.4; the bench's scenarios, 9.1).

**The B1 zero-table check belongs to the signed-reply layer.** `sign_reply.expected_tables` (`host/b1_records.py`) are the twelve
words of the signed payload; B1's rule iii-B1 refuses a reply whose words are not zero. A v2 carrier keeps that layer unchanged and
the check stays there; `O` has no table field and the closed set refuses one.

A refused record is kept raw in quarantine with the findings (task-v0.2's quarantine form); nothing is dropped or repaired.

### 4.4 The schema files — provisional names (D3 as ruled)

`b4/schemas/ff_observation_view_v1.schema.json` (the logical view of 3.1 — what readers consume, never what a source writes),
`b4/schemas/ff_observation_model_raw_v1.schema.json` (the legacy raw format of 3.2's model column, as `observe()` writes it; its
adapter named beside it), `b4/schemas/ff_observation_carrier_v1.schema.json` (`O`), `ff_fitness_v1`, `ff_transaction_close_v1`
(`F`, `X`). **One validator entry point**: the trusted context names the branch (3.5) → the raw record is validated against that
branch's raw schema → the adapter builds the view → the view is validated against the view schema. The source-dependent rules are
the raw format, the cell rule, the digest encodings, the provenance fields and the bindings — not only `null`. **The unadapted
legacy trace is not an instance of the view schema and is not claimed to be.** The names are provisional and the owner's; nothing
under `b4/` is written or changed by this unit.

## 5. The transaction — one candidate, one initialisation, three objects, one witness chain

### 5.1 The phases and the record-readiness table (contract; A1's single transaction)

| phase | what happens | object and field written | immutable after |
|---|---|---|---|
| — | the previous `X` closed (or the session root, 5.5; or an `a5_injection` `X` under 5.6) and its `idle_status` idle | — | — |
| P1 | sign (link 1), stage, staging re-read (link 2) | `O.commit`, `O.staging_readback_sha256`, `O.predecessor` (a reference to the previous `X`) | — |
| P2 | (a) / (b): write the candidate; fabric readback (link 3) = **pre-event**. (c): the **pre-write sample** (`O.initial`, 6.3) and the readback of the **prior configuration** = **pre-event**; then the write, which **is** the event | `O.fabric_readback_sha256_pre_event`; (c) also `O.initial` | — |
| P3 | stimulus step 0 = **the** initialisation event: (a) / (b) pre-init sample → assert → release → init sample; (c) release after the write → init sample (6.3) | `O.initial` ((a) / (b)), `O.steps[0]` | — |
| P4 | fabric readback (link 3) = **post-event** | `O.fabric_readback_sha256_post_event` | — |
| P5 | stimulus steps 1 … n, exactly (2.3) — the scored observation ends here | `O.steps[1:]` | — |
| **P6a** | `O.status = "complete"`; `O` sealed, `observation_sha256` computed | `O` | **`O`** |
| **P6b** | the fitness computed from `O` | `F` | **`F`** |
| P7 | **cleanup** (5.3): inputs to 0, clock to 0, sampled — not scored | `X.cleanup` | — |
| P8 | restore the base: write → fabric readback of the base (link 3) | `X.base_readback_sha256` | — |
| P9 | the base-state witness (5.4): the declared mechanism raised once in the permitted context → sample | `X.base_state_sample` | — |
| **P10** | idle (5.2): the status word read; `X.status = "closed"`, `close_sha256` computed | `X.idle_status`, `X` | **`X`** |

**Exactly one initialisation event lies inside the scored observation, and it is step 0.** P9's event is outside it and is
recorded only in `X`. `O` contains nothing from P7–P10; `X` references `O` by digest; the next `O` references `X` by digest. No
object is mutated after its immutability point; a value that does not yet exist is never written.

### 5.2 Idle, as a state and as a witness

"Idle": every input low, the slice clock low, the scorer's step counter zero, the sample registers cleared, no pending edge, the
fabric holding the base — **observable** as the identity page's status word, read at P10 and recorded in `X.idle_status`. A
candidate is not signed while the last `X` is not `closed` with an idle `idle_status` (the A5 exception: 5.6).

### 5.3 The cleanup phase (P7) — defined, recorded in `X`, not scored

In this order: (1) `sr` → 0, `ce` → 0, `d` → 0 (one settle interval); (2) if the clock is 1 (possible under the general grammar;
not under task-v0.2's fixed shapes, 2.2), clock → 0 — a falling edge, recorded as one, possibly capturing on a falling-edge
element: a consequence of the stimulus's final state, not an observation; (3) one hold interval; (4) sample. `X.cleanup` =
`{steps: [...], final_q}`. Cleanup is never part of the fitness, never in K9 / K10's grids, never an input to the cartographer; its
purpose is that P9's precondition (clock low, SR de-asserted) is met *and witnessed*. An SR operation inside the stimulus is
recovered by nothing inside the stimulus — the next step may assert SR again — and the transaction's recovery is P7–P9.

### 5.4 Frame equality is not Q restoration — two witnesses, both in the current `X`

| witness | where | what it proves | what it does not prove |
|---|---|---|---|
| **frame binding** (conditional, the table below) | `O`'s two readbacks each equal to **their own reference**; `X.base_readback_sha256` = the session's base readback digest | the configuration binding: the fabric held the prior configuration before the event and the signed candidate after it | anything about Q, which no frame readback reads |
| **Q-state restoration** | `X.base_state_sample` = the session's **base-state reference** (the session root's `X.base_state_sample`, 5.5) | that the transaction returned the elements to the declared base state under the declared mechanism | that a *different* leftover would also have been cleared (5.6's limit); that the mechanism is the one the hypothesis models (section 6) |

**The frame binding, by mechanism and predecessor context** (R3: for (c) the two readbacks are of two *different* configurations
and are never required to equal each other):

| mechanism | `predecessor.kind` | `fabric_readback_sha256_pre_event` must equal | `fabric_readback_sha256_post_event` must equal |
|---|---|---|---|
| (a) / (b) — a separate event after the write | `closed` or `session_root` | `staging_readback_sha256` (the candidate, written) | `fabric_readback_sha256_pre_event` (the event changed no frame) |
| (a) / (b) | `a5_injection` (J3) | the same | the same |
| (c) — the write is the event | `closed` | the predecessor `X.base_readback_sha256` (the **base**, the prior configuration) | `staging_readback_sha256` (the candidate) |
| (c) | `session_root` | **`session_open.startup_readback_sha256`** — the session-opening record's readback of the fabric as loaded (5.5), itself equal to the manifest's pinned base-frame reference; **never** the root's own `X` (not yet written) and never a predecessor (there is none) | `staging_readback_sha256` (the base, written) |
| (c) | `a5_injection` (J3) | **`O_c′.fabric_readback_sha256_post_event`** (the prior configuration is *c′*; no base restoration was performed and none is pretended) | `staging_readback_sha256` |

Both witnesses of the table above are required for the next candidate to be signed (5.2); a failure of either closes `X` as
`faulted` with its code (5.7).

### 5.5 The session root and the predecessor chain

`O.predecessor` is a **reference** `{kind, seq, close_sha256}` to the previous transaction's `X`, whose fields hold that
transaction's own restore witnesses (5.4); the current transaction's witnesses are in its own `X`, so **the last transaction of a
session and every interruption window keep their own evidence** (5.7).

**The session-opening record (the bootstrap).** Before anything is signed — after the sha-gated carrier load and the identity page
(B1Q's preamble) — the runner writes `session_open = {instrument, startup_readback_sha256, base_frames_reference_sha256, status}`:
`startup_readback_sha256` is link 3's readback of the fabric **as loaded**, taken then; `base_frames_reference_sha256` is the
**trusted input**: the base-frame content of the pinned carrier (the target frames the carrier manifest records as blank in the
base — `frame_table_sha256`, `target_frames_nonzero_words`, the bitstream digest), pinned in the instrument manifest before the
session, derived from no record of the session. `status = "open"` only when the two are equal; otherwise `"refused"` — **the
session does not open, no root is signed, nothing follows**, and the refused record is retained as a non-success record. The
root's mechanism-(c) pre-event readback binds to `session_open.startup_readback_sha256` (5.4's table), and the root's `O` names
the record it binds to in `init_event.parameters.session_open_sha256`; the root never references its own later `X`, and a
predecessor it does not have.

The chain terminates at the **session root**: the session's first transaction, on the base configuration itself — P1–P4 (the base
signed, written, read back; the mechanism raised; the pre-init and init samples taken; for (c) the pre-event readback is
`session_open`'s, above), **no P5**, P6a (`O` with `steps = [steps[0]]`, `status = "complete"`), **no `F`** (nothing to score; `F`
exists only for a task observation), P7 (trivial), P8 (the base is in place; the readback taken), P9 (the mechanism raised once more;
**this sample is the session's base-state reference**), P10. Its `O.predecessor = {kind: "session_root", seq: null, close_sha256:
null}` — the only `O` allowed that value; the first candidate's `predecessor = {kind: "closed", seq: <root seq>, close_sha256: <the
root's X>}`. The closing baseline of B1Q's form is kept and compared with the root under both witnesses of 5.4.

### 5.6 A5 — the compared projection, the injection witness, the qualification-only injection protocol, and the decision table

**The pre-init state appears in two places and is excluded from the projection in both.** `initial.q` and its copy
`steps[0].q_before` (3.3) are the *pre-init state representation*; the **post-init projection** of an observation is:
`steps[0].q_after`; every field of `steps[1:]` (all of 3.1's step keys, `q_before` included — from step 1 on, `q_before` is a copy
of a post-init sample); and `X.cleanup.final_q`. Excluded besides the pre-init state: `seq`, `nonce`, `predecessor`, the readback
digests (compared separately for equality to the candidate's own, 5.4), `X.idle_status`, `X.base_*`. Two observations of the same
candidate under the same stimulus are *equal for A5* when their post-init projections are equal. (The owner's static counterexample
— pre-init `[0]*8` versus `[1]*8`, both init samples `[0]*8`, equal cleanup — is **equal** under this projection; it was unequal
under v0.2's.)

**The injection witness, checked apart from the projection.** The injection "arrived" when the second observation's
`initial.q` (= `steps[0].q_before`) **differs** from the first's **and equals** the injecting transaction's recorded final state
(below). It is a separate check with its own name; it is not part of the projection.

**The qualification-only injection protocol** (a record type of the B4Q plan; never in a mapping session):

| step | transaction | what is normal | what is special, and how it is recorded |
|---|---|---|---|
| J1 | observe *c* from a `closed` predecessor | P1–P10 entirely normal | `O_c1` (`status = "complete"`), `F` absent (a qualification observation is not a task observation — the record type is `a5_qualification`, 9.2), `X_c1` `closed` |
| J2 | observe *c′* — the injecting transaction | P1–P6a **entirely normal**: signed, nonce, writability, link 2 / 3, the predecessor `X_c1` `closed` | *c′*'s stimulus is predeclared in the plan: its last step leaves every element at the value opposite to `O_c1.steps[0].q_after` on that element (`d` so chosen, `ce` asserted on every element, `sr` de-asserted, the clock at the level that captures on the configured edge), inputs held non-zero at the end. **P7–P9 deliberately omitted**: `X_c′` is written at once with `status = "injection_open"`, `cleanup` **absent**, `base_readback_sha256` **absent**, `base_state_sample` **absent**, `idle_status` the word as read (not idle). **`O_c′.steps[-1].q_after` is the injected state's record** |
| J3 | observe *c* again | P1 normal (signed, nonce, writability) **with `predecessor = {kind: "a5_injection", seq: <c′>, close_sha256: <X_c′>}` — the one value under which a non-`closed` predecessor is accepted, and only inside a B4Q session under the plan's A5 ruling**; P2 the write of *c* — **the carrier changes no input and no clock between J2's last step and this write** (the inputs and clock stay as *c′* left them; recorded in `O_c2.initial.{clock, ce, sr, d}` as read, which for this record are therefore **not** 0); P3.1 the pre-init sample (= `initial.q`): for mechanisms (a) and (b) taken **after** the write of *c* and the pre-init readback, inputs then set to 0 and clock to 0 by a recorded cleanup-like step *inside* step 0's context (`init_event.parameters.pre_init_cleanup: true` — the only configuration where step 0 starts from non-zero inputs, and it is recorded); for mechanism (c) taken **before** the write (6.3) — **an actual sample, never the cached base-state reference** — and (c)'s pre-event readback is *c′*'s configuration (5.4's table), no base restoration inserted; then the event, the init sample, P4–P10 normal | `O_c2` (`status = "complete"`), `X_c2` `closed`; the next normal candidate requires `X_c2` `closed` and idle as usual |

**The decision table** (per element and per cross-element; the whole record set retained whatever the row):

| injection witness (`O_c2.initial.q` vs `O_c1.initial.q` and vs `O_c′.steps[-1].q_after`) | post-init projection (`O_c2` vs `O_c1`) | verdict |
|---|---|---|
| equal to `O_c1`'s, or not equal to the injected state | — (not evaluated) | **not demonstrated**: the injection did not reach the pre-init boundary (a finding of its own; the test is not run) |
| differs from `O_c1`'s and equals the injected state | equal | **pass**: this adversarial state arrived and was cleared by the initialisation |
| differs from `O_c1`'s and equals the injected state | differs | **fail**: persistence after initialisation; the differing positions are the finding |

A pass establishes that **this** specified state does not reach the next record; it does not establish that no leftover state can,
and the qualification record says so. Proving that the normal gate refuses an unrestored predecessor is a different scenario (9.1,
A1) and is **not** A5.

### 5.7 Faulted and interrupted transactions — retention as non-success records

| where it stops | what exists | status written | what is never done |
|---|---|---|---|
| in P1–P5 (a sampling fault, a link failure, a watchdog) | `O` with exactly the fields of the phases completed before the stop (4.2's phase table) | `O.status = "invalid"`, `fault = {code, phase_reached, step_reached}`; `O` sealed as such (`observation_sha256` over the invalid record); no `F`; `X` written at once as `faulted` with `phase_reached` | no `F`; no cell guessed; no field of a later phase; the prefix never scored, never a specimen, never compared under A5 |
| in P7–P10 (after `O` sealed) | `O` complete, `F` (if a task observation), a partial `X` | `X.status = "faulted"`, `fault = {code, phase_reached}`, the fields it could not take absent | `O` and `F` untouched; the next candidate not signed (5.2) until the session's stop rule says what follows (the B4Q plan's) |
| an external interruption (power, transport) | whatever objects were sealed | the objects that exist stay as they are; the missing ones are **missing**, recorded as such by the host from the notary log | no object reconstructed or completed by the host |

Every row is counted in the session's accounting and retained for audit.

## 6. INIT and SRVAL — two observations, the per-mechanism order, the same-element cross, A8 unresolved

### 6.1 The two values and where each is read

| value | the hypothesis's restore mechanism | the raw sample point | the record's field |
|---|---|---|---|
| `INIT` (`ff_init`, the `ZINI` bit) | an *initialisation event* (`initialisation_event.assumption`, a model abstraction) | the init sample: `steps[0].q_after`, before any edge, SR de-asserted | `O.steps[0].q_after` |
| `SRVAL` (`ff_srval`, the `ZRST` bit) | a *user SR operation* — the element's own set / reset input, applied as a step | the `q_after` of a `set` step whose `sr` bit for that element is 1 — a sample point, **not by itself evidence of a completed restore** (6.5) | `O.steps[n].q_after[e]` |

Two observation points in one trace, never one value read twice, never derived from each other.

### 6.2 The initialisation mechanism — three candidates retained, one declared, none selected (D2 as ruled)

| candidate | what it is | the bench-witnessable condition | feasibility questions left to the carrier design / qualification unit |
|---|---|---|---|
| (a) a configuration-port restore command | the configuration logic's own command that loads every storage element from its configured initial value, through the instrument's port | no configuration frame changed (6.3's two readbacks equal); issued and completed inside the transaction | availability through the port; scope (the device, not only the pblock); what else it resets; whether it has any Q effect on this die |
| (b) a global set / reset net raised by the carrier | the device's global initialisation net driven from the carrier's logic for a declared number of cycles | frame invariance; the release timing relative to the slice clock (clock low, SR de-asserted) | reach into the pblock; interaction with the carrier's own state machine and the PS path |
| (c) configuration as the event | the candidate's write (P2) is the event | the written frames equal the staged ones (links 2–3) | whether a write has any defined Q effect; that the event cannot be raised as a separate act, so P9's base-state witness is the base *write* followed by a sample |

**Neither a command's name nor two equal frame readbacks establishes an event-to-Q effect** — that is A8's question (6.4); no
mechanism is selected or authorised to run here.

### 6.3 The order of samples and readbacks at step 0, per mechanism

| | (a) command | (b) net | (c) configuration |
|---|---|---|---|
| pre-event readback | after the write of the candidate (P2); = staging | the same | the readback of the **prior configuration before the write** (P2): the base in a normal transaction, *c′* under J3 (5.4's table) |
| pre-init sample (`initial.q`) | after the pre-event readback; inputs 0, clock 0 under `context = idle`; the held values under `a5_injection` (5.6 J3, recorded) | the same | **before the write** (P2), an actual sample under the same context rule — in a normal transaction it equals the predecessor's base-state sample by 5.4 and is still taken, never copied |
| assert | the command issued (P3) | the net driven (P3) | the write itself (P2) |
| release | completion + the **release** interval | release + the **release** interval | the write's completion + the **release** interval (P3) |
| init sample (`steps[0].q_after`) | after the **sample offset** | the same | the same |
| post-event readback (P4) | of the candidate; = pre-event | the same | of the candidate; = staging |

For (c) `init_event.parameters.pre_event_is_prior_configuration = true`. Frame binding proves the configuration binding only
(5.4); it never proves an event-to-Q effect (6.2).

### 6.4 The A8 cross — a 2 × 2 factorial on the same element and background

Choose one element *e* and one background *b* in which *e* is a flip-flop storage element with SR driven (`storage_kind` = FF,
`sr_mode` = driven; every other bit fixed at *b*'s values). Vary **only** *e*'s `ff_init` bit and `ff_srval` bit: four candidates
`(INIT, SRVAL) ∈ {00, 01, 10, 11}`, **one predeclared demonstration stimulus for all four** (6.5), the same timing, mechanism and
source. What the readouts of *e* should discriminate:

| readout of *e* | tracks | must not track |
|---|---|---|
| the init sample (`steps[0].q_after[e]`) | the `ff_init` bit, in the direction the Z reading predicts | the `ff_srval` bit |
| the SR-restore evidence (6.5's joint value) | the `ff_srval` bit | the `ff_init` bit |

Scope: once on a main element and once on an x5FF element; FF storage context only (under a latch the x5FF elements are not storage
elements, and the main elements' init readout under an open inverted gate rests on G6, 6.6); at *b*'s clock-mode value, the other
value a second cross if the plan runs it, else **reported as not demonstrated for that context**. The A2 pairs of 7.3 need not serve
as the cross.

### 6.5 The SR evidence — one fixed stimulus, a validated reference, known prior values, two episodes judged jointly

SR = 1 is an input condition. For a synchronous element SR acts at a capture event (`sync_sr_acts_on_edge_only`, SR priority over
capture); for an asynchronous one at level; **before mapping, `sr_kind` is unknown**. A single fixed `d` cannot be "opposite to
SRVAL" for corners whose SRVAL differ, so the demonstration stimulus — **the same for every corner** — contains, for the element *e*
(the other elements held at *b*'s inputs):

| part | steps | sample |
|---|---|---|
| C0, C1 — the **reference captures** | an edge with `ce(e) = 1`, `sr(e) = 0`, `d(e) = 0`; then one with `d(e) = 1` | `K0`, `K1` |
| E0 — episode 0 | a plain capture of **`d(e) = 1`** (so the prior value is 1), then `sr(e) = 1` asserted on a level step and held through the next capture edge of *e*'s clock with `ce(e) = 1` and **`d(e) = 0`** at the edge | `P0` (the prior value, the `q_after` before the SR level step), `R0` (the edge step's `q_after`) |
| E1 — episode 1 | a plain capture of **`d(e) = 0`** (prior value 0), then SR asserted likewise with **`d(e) = 1`** at the edge | `P1`, `R1` |

**The reference must be valid before any restore is read.** `K0 = 0` and `K1 = 1` show that *e* captures both values through a
plain edge; `K0 = K1` means the reference does not discriminate (a held or non-capturing element, a sampling path that does not
reach *e*, or an element that is not a storage element in *b*) and **no SR reading is made for that corner**: it is `unknown`,
its raw samples retained. Likewise the prior values must be as planted (`P0 = 1`, `P1 = 0`), else `unknown`.

**The joint reading, per corner, with a valid reference and the planted priors** (no candidate-dependent adaptation):

| `(R0, R1)` | reading | why it is identifiable |
|---|---|---|
| `R0 = R1 = v` | **restore** to `v` — the SR evidence of the corner | with `K0 ≠ K1` the element captures `d`, and with `P0 ≠ P1` a hold would give `(1, 0)`; equal readouts across `d = 0 / 1` and priors `1 / 0` can only be the SR operation setting one value |
| `(R0, R1) = (K0, K1) = (0, 1)` | **capture** — SR had no effect at this edge; no restore value | the element followed `d` as in the reference |
| `(R0, R1) = (P0, P1) = (1, 0)` | **hold** — SR blocked the capture without setting a value; no restore value | the element kept its prior value |
| any other pattern, or a sample fault | **inconsistent** | recorded; no restore value |

The stuck case the owner's probe named (`R0 = R1 = K0 = K1`) is caught by the reference rule before the joint reading: it is
`unknown`, never a restore. Because SR is asserted across a capture edge, an episode completes under either `sr_kind` (an
asynchronous element restores at the level step already and reads the same at the edge). The latch context and `sr_mode =
tied_low` are excluded as architecture 9.3's clauses 4 and 6 exclude them. The vectors and timing stay with the B4Q plan; the
parts, the reference rule and the joint reading are fixed here and are satisfiable for every corner.

### 6.6 The G6 limit, kept visible

Under v0.3 the model's init readout exists in every configuration **because the init step assigns atomically and settles no level
effect** (G6). A device has no atomic step — a release interval, a sample offset or a readback **cannot be presumed to preserve that
transient**. The carrier **reports the contexts in which its mechanism cannot observe an init value**; those contexts are *not
demonstrated* and their `ff_init` relations stay `unknown`; **no unrecorded clock, reset or input operation is added to force
agreement with the model's atomic readout**. A8 stays unresolved by this section.

### 6.7 Outcomes — a precedence-ordered classification, conditional, with attribution left to independent evidence

**Preconditions of every row.** A1–A7 met (9); the cross run in 6.4's scope; frame equality and Q-state restoration on every record
(5.4). A row is read *for the demonstrated contexts only*; a context not run or not observable (6.6) is `unknown` whatever the row.

**Per-corner readings.** Each corner `c ∈ {00, 01, 10, 11}` = `(INIT, SRVAL)` yields `i_c` — the init sample of *e*
(`steps[0].q_after[e]`, or `fault`) — and `s_c` — 6.5's reading: `restore(v)`, `capture`, `hold`, `inconsistent` or `unknown`.

**The quantities, derived from the readings:**

| quantity | definition |
|---|---|
| `not_assessable` | any `i_c = fault`, or any `s_c = unknown` (an invalid reference or a prior not as planted) |
| `init_effect` | `i_00 ≠ i_10` and `i_01 ≠ i_11`, both in the predicted direction |
| `init_absent` | `i_00 = i_10` and `i_01 = i_11` |
| `srval_effect` | all four `s_c` are `restore` and `v_00 ≠ v_01` and `v_10 ≠ v_11`, both in the predicted direction |
| `srval_absent` | all four `s_c` are `capture`, or all four are `hold` (a consistent non-restore in every corner: no restore value to compare); **or all four are `restore` with `v_00 = v_01` and `v_10 = v_11`** (a **constant restore**: SR restores in every corner but the SRVAL bit has no effect on the value — an absent main effect, not an inconsistency; whether that constant value tracks INIT is `cross_tracking`'s question) |
| `cross_tracking` | `i_00 ≠ i_01` or `i_10 ≠ i_11` (the init sample tracks SRVAL); or, when all four are `restore`, `v_00 ≠ v_10` or `v_01 ≠ v_11` (the restore value tracks INIT) |
| `inconsistent` | neither `init_effect` nor `init_absent`; or neither `srval_effect` nor `srval_absent` (restore in some corners and not in others; a restore in all four with the values differing in one INIT-constant pair and not the other; any `s_c = inconsistent`) |

**The classification, applied in this order — the first matching row is the verdict and no later row applies:**

| # | condition | verdict for the demonstrated context | what follows for 2c's claim |
|---|---|---|---|
| 0 | `not_assessable` | **not demonstrated** | the cross did not produce evidence in this context: the samples are retained raw; the context stays `unknown`; whether it is re-run is the B4Q plan's rule, not an automatic retry; **not** a failure and **not** a reduced claim |
| 1 | `cross_tracking` **or** `inconsistent` | **failed / unresolved** | the evidence preserved as it came; **no attribution**: mechanism, stimulus / timing, instrumentation / implementation or model mismatch are separated only by independent evidence; **no hypothesis revision and no carrier re-tuning follows automatically** |
| 2 | `init_effect` and `srval_effect` | **both demonstrated** | `ff_init` and `ff_srval` observable in that context with the other five; undemonstrated contexts listed, their relations `unknown` |
| 3 | `init_absent` and `srval_effect` | **SRVAL demonstrated; INIT not** | every `ff_init` relation `unknown`; the semantic claim and the certificate-map scoring exclude `ff_init`; the **raw task fitness is untouched**; whether that reduced claim is a preregistration 2c wants is **2c's decision** |
| 4 | `init_effect` and `srval_absent` | **INIT demonstrated; SRVAL not** | likewise with `ff_srval` |
| 5 | `init_absent` and `srval_absent` | **neither demonstrated** | both excluded from the semantic claim and the map scoring; fitness untouched; whether to run is the owner's |

Rows 2–5 are the four combinations of `{init_effect, init_absent} × {srval_effect, srval_absent}` and partition every case that
rows 0 and 1 do not take, because row 1's `inconsistent` takes exactly the cases where a kind has neither its effect nor its
absence; so each raw corner data set lands in one row. An absent main effect alone (rows 3–5) is a reduced claim, not a failure;
a readout that tracks the wrong bit, an effect present in one pair and absent in the other, or a mixed restore / non-restore
across corners is a failure and is never read as a reduced claim; a **constant restore** (all four `restore` to one value) is an
absent SRVAL effect — row 4 with INIT present, row 5 with INIT absent — unless its value changes with INIT, which is row 1; an
invalid reference is neither. No row is a repair.

## 7. Positive controls — the quantifiers, the rule as a revision, the proposal, the data influence

### 7.1 The two quantifiers (architecture 5.2, A2 — unchanged)

For **each semantic** at least one positive control: an address carrying that semantic under the mapping and the hypothesis, and a
stimulus / background pair under which the bit's two values give different observations. For **each address and each applicable
context**, whether the sequence separates the two values, judged per address and context, uncovered addresses reported and their
relations left `unknown`. The first is what the board must show before any mapping session (A2); the second is K9's report.

### 7.2 The selection rule — a qualification-selection proposal that revises the recorded choice 7 (D4 as ruled)

**What the architecture records** (the v0.2.0 revision note, choice 7): *the most-covered unique forced pair per semantic in the
gate-1 K9 record, tie-break by `bit`, `g0`, `g1` numeric order, `ff_srval` / `sr_kind` from SR-driven and old-applicable pairs
only*, disclosed as tuning on gate-1, not executed. **What this document proposes instead, and why**: (i) the **source** is the
`b4-sim-4` archive (task-v0.2, K9 (b′) the judged estimand), not gate-1 (task-v0.1, (b) only) — the record produced under the
protocol the carrier will be qualified against; (ii) **address-first, by the pooled (b′) fraction over the 32 pairs** (ties in the
mapping's address order), then the background covered in the most pairs (ties the lowest `g0`) — A2 asks for an *address* per
semantic, and pooling over seeds prefers an address that discriminates across stimuli; (iii) for `ff_init` and `ff_srval` **one
main-element and one x5FF-element address each**. **Precedence:** if the owner accepts this proposal it replaces choice 7's rule for
the B4Q selection and the architecture's note is amended to say so with this reason; until then choice 7's wording stands as the
recorded rule and this is a proposal beside it. The historical choice is not rewritten; the frozen K9 panel, both applicabilities,
the host method and the old verdicts are unchanged.

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

The `sr_kind` and both `ff_srval` controls sit on the background `000008` (SR driven), as architecture 9.3 clause 6 requires; the
**four** other slice-wide controls and the two `ff_init` controls sit on the all-zero base. **What the nine pairs are**: a
data-informed DRAFT A2 proposal. **What they are not**: certified combinations (the legal-composition rule of architecture 4.2 is not
written here), board-observed effects, a whitelist, the A8 cross (6.4), or a guarantee about the fixed qualification stimulus — the
fractions are the model's distinguishability under the *changing task stimuli* of 32 seeds, and the B4Q demonstration stimulus (the
grammar of 2.1; for the two `ff_srval` rows and `sr_kind`, 6.5's episodes) must show distinguishability **under its own predeclared
conditions**. A board result of 0 / 1 on any row is the A2 finding for that semantic, reported, never repaired by choosing another
address afterwards.

### 7.4 The data influence, disclosed

The choice of 7.3 was made by reading the **committed** archive `evidence/b4/sim/b4-sim-4_20261021T065339Z` (`sim_report.json`
sha256 `01744b39598b10bbf7d4371be1e5b9355c08fc39a8877ef6957866ac8178f1fa`), the 32 `pair_*/k9.json` files only, through
`k9_address_record.py` and `positive_control_choice.py`, both read-only, both in the unit directory with their outputs; the owner's
reviews of `e91650b` and `d8ef6cf` reran / re-checked them (byte-identical; the nine rows reselected independently with exact
fractions). No seed was derived or printed; no archive, receipt, registry, threshold, label or decision was changed; the pooled
exclusion stays 2 690; `b4-sim-4`'s no-go stays the record it is. The positive-control addresses were chosen where the **model** says
the task stimuli discriminate best; if the board agrees, that is a board result on model-favoured addresses (a positive control is
the easiest case, by design); if it disagrees, the choice makes the disagreement harder to attribute to a poor address. The K9
fractions do not predict the board, and the sim-4 Ω − R record played no part. The counterexample of 3.4 and the legacy-format facts
of 3.2 are further reads of retained records, disclosed likewise.

## 8. The two holdouts — two axes, one contract

| | the stimulus holdout (task-v0.2, architecture 7.1 axis (a)) | the whole-site holdout (2c, architecture 4.3) |
|---|---|---|
| what is held out | a second stimulus (K = 8, its own derivation) the search never scores against; the champion scored on it once | a site instance whose addresses the FF cartographer's development never read |
| what it tests | behavioural consistency on vectors the champion was not tuned on — a research quantity, no threshold | that the map was built from observations, not from knowledge of this site — an engineering holdout, not a claim the truth was unseen |
| who knows which is which | the engine (phase `holdout`); the carrier **does not** | the preregistration names the instance; a second instance is a second build or a parameterised one — the carrier unit's |
| the record | the same `O` / `F` / `X`; the phase is the engine's field | the same records on the holdout site, in its own session |
| status | fixed by task-v0.2 | **unresolved**: which instance (`17A6` second site, or `3671`) |

**Neither holdout changes what the executing side does or records**; the bench's negative scenario: a holdout-phase and a
search-phase observation of the same configuration and stimulus are equal under 5.6's post-init projection and in every `O`
field but `seq`, `nonce`, `predecessor`.

## 9. Acceptance of a carrier v2 — the bench list and the board list (against A1–A8)

### 9.1 On the bench (iverilog, the carrier unit's deliverable; host-verifiable, no ruling)

| condition | scenario | witness |
|---|---|---|
| A1 | the session root, then one candidate P1–P10 in order under the instrument's watchdog; `O` sealed at P6a, `F` at P6b, `X` at P10, each digest covering what 4.1 says; a candidate offered against a non-`closed` predecessor **refused** (the normal gate; not A5) | the bench's transaction count; the three digests; the refusal by name |
| A3 | a record for a known fabric accepted by 4.3; injected breaks each refused by name: an extra key at each level of `O`, `F`, `X` (`answer_bits` among them); a `null` cell; a float cell; a missing header field; a `hypothesis` block; a value written into `O` that only exists at P7+; `fabric.kind = "truth"` on a **model** trace **accepted** (the field-aware rule) | the findings, one per break; the acceptance |
| A4 | `VARIANT` reads the v2 word; the B1 application refuses it; the v2 application refuses the B1 word and the instrument's | the identity scenarios |
| A5 | 5.6's protocol J1–J3 with the bench's *c′*; the three rows of the decision table each produced once (a bench fabric that clears, one that persists, one where the injection does not arrive) | the three verdicts, by name |
| A6 | every B1 scenario that still applies; one per row of architecture 5.2; this contract's own: the stimulus applied exactly (a step inserted, dropped, reordered or initialised twice is seen); the cleanup recorded in `X` and P9's precondition witnessed; the two readbacks per mechanism (6.3); the holdout-indifference scenario (8); frame invariance; the sampling path (3.4); 6.5's reference and two episodes reading restore on a restoring fabric, capture on a non-restoring one, hold on a blocking one and `unknown` on a non-capturing reference; a faulted transaction retained per 5.7 | each scenario PASS, by name |
| A7 | the MMIO allowlist against the RTL's AXI-Lite decode — mismatches only (architecture A7; `docs/b1_carrier_qualification.md` section 2's form) | the mismatch list empty |
| A2, A8 | **not bench-verifiable**: the bench's fabric is the hypothesis; the bench witnesses the mechanism's *conditions* (6.2), never its Q effect | — |

### 9.2 On a board (under its own ruling; the qualification session B4Q, before any mapping session)

| condition | what the session shows | witness in the evidence |
|---|---|---|
| identity | `VARIANT` v2 over the PS path, the carrier and image digests, the declared mechanism and the timing parameters | the IDENT record |
| links and baselines | the session root and the closing baseline equal under both witnesses of 5.4; every record audited; the closing unsigned / replay / wrong-key controls refused | B1Q's form, re-aimed |
| the sampling path | every element's Q sampled type-exact on every record; no sampling fault | 3.4 |
| A2 | the nine pairs of 7.3 at both endpoints under the demonstration stimulus — per row, the readout differs at the named point or does not | the nine pair records (type `a2_qualification`) and the per-row verdict |
| A5 | 5.6's protocol with the plan's *c′*; the decision table's row | the `a5_qualification` records: `O_c1`, `O_c′` with `X_c′` `injection_open`, `O_c2`; the row |
| A8 | 6.4's cross on a main and an x5FF element with 6.5's episodes; 6.7's row by precedence; 6.6's unobservable contexts reported | the four-corner records per cross (type `a8_qualification`); the row, written into the preregistration as a demonstrated-context statement |
| frame equality and Q-state restoration | both witnesses on every `X` | the digests; the P9 samples against the root's |
| the board | `17A6` under the content-class interlock; `F8B3` for bring-up first; nothing powered before the ruling | the interlock's record in the run log |

The result is a qualification record in B1Q's evidence-chain form (verified before pinned; a changed pin re-qualifies);
`qualified` is derived, never set. A HOLD session leaves a record of a failed qualification. **This document does not plan that
session**: the plan, the demonstration stimulus vectors, *c′*, the ruling pair and the date are 2c's and the owner's.

## 10. Unresolved — each with the dependency that resolves it

1. **A8** — which mechanism has an event-to-Q effect on this die, whether the same-element cross holds, in which contexts: the board under the B4Q ruling.
2. **The declared mechanism** (6.2), its availability, scope and reset effects: the carrier-v2 design unit.
3. **The four timing intervals**, the cleanup's and the J3 `pre_init_cleanup`'s electrical realisation: the carrier unit; recorded, never fixed here.
4. **The schema files and the adapter** (4.4): the owner for the names; a later tool unit for the implementation; nothing under `b4/` now.
5. **The A5 injected state** *c′* for the bench and the board, and the plan's A5 ruling: the carrier unit and the B4Q plan.
6. **The demonstration stimulus vectors** of 6.5 and 7.3: the B4Q plan; the grammar, the episodes and the joint rule are fixed here.
7. **Whether the owner accepts the selection rule as the revision of choice 7** (7.2) and the nine pairs (7.3).
8. **The whole-site holdout's instance** (8): the preregistration.
9. **The legal-composition rule** (architecture 4.2): 2c; the nine pairs are not made legal by 7.3.
10. **The board-study metric across the scoring-domain limit** (3.4): 2c, with N, `B*` and the prediction.
11. **Who executes the planted target configuration on a board** (architecture 7.1): undecided; under this contract the target observation is an `O` like any other and the isolation is the harness's.
12. **N, `B*`, the prediction, the session partition, the calibrated rates, the lifecycle tool**: the skeleton's sections 7, 9, 11, 12.
13. **2c's freeze**: not by this document.

## 11. What this document does not do

It fixes no number the board will be judged by; derives no seed; names no prediction; partitions no session; chooses no
initialisation mechanism; writes no RTL, bench, XDC, schema or adapter and changes nothing under `b4/`; rewrites, re-encodes,
re-digests or retags no existing trace or archive; powers no board; changes no archive, threshold, label, receipt, legal-write rule
or decision; does not say that the hypothesis holds on silicon, that A8 will pass, or that a board fitness and a model fitness are
comparable; does not freeze 2c; does not authorise the carrier-v2 unit, 2d, routing, a push or a merge.

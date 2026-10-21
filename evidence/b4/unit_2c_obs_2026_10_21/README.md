# B4 — the 2c-obs unit: the observation contract (documents and read-only scripts only, 2026-10-21) — **CLOSED: the owner's PASS on `4fc3dc7`**

**What this unit is.** The documents-only unit the owner authorised on 2026-10-21 after the PASS on the `b4-sim-4` execution unit
(`196b358`, closed at `fceedd6`; the review's section 6: *what follows needs its own scientific or engineering purpose and explicit
scope*). The scope as the owner gave it — the authorisation text is archived beside this README as `owner_authorisation_2026_10_21.txt`
with `AUTHORISATION_SOURCE.txt` (supplied by the owner with the review of `e91650b`: a transcription of the in-conversation message by
its author, **not** a byte-identical copy of an exported original, and the two files here are byte-identical to the copies in that
review directory): **a draft observation
contract for unit 2c — a pure document** covering the stimulus, the raw readout, the evidence fields and the isolation between
candidates; INIT and SRVAL each observed and recovered separately, A8 left unresolved; the positive controls, the address choice and
the disclosure of the data that informed it; the stimulus holdout against the whole-site holdout; the bench and board acceptance
conditions of a carrier v2. N, `B*`, the prediction and the sessions stay unresolved; 2c is not frozen; the whole unit is submitted
for review once; push and merge are not authorised; read-only inventory and proposals may continue.

**Branch.** `b4-2c-obs`, created from `fceedd6` (= `b4-sim-4-execution`'s closure; `main` = `origin/main` = `a243ee8`). The first
submission `e91650b` (v0.1) was held by the owner (section 6), the second `d8ef6cf` (v0.2) was held again (section 7), the third `df3b65e` (v0.3) was held again
(section 8), the fourth `6927c24` (v0.4) was held on two P2 (section 9); the fifth `4fc3dc7` (v0.5) **passed** (section 10); the four correction
rounds are the second to fifth commits of the same unit and the closure the sixth. Nothing pushed, nothing merged.

**Interruption, disclosed.** The first attempt to write the contract document in the preceding session was stopped by the
assistant's safety classifier before the file existed; that text was not retained and, by instruction, not reproduced. The present
`docs/b4_observation_contract.md` was drafted afresh in this session from the sources its standing paragraph names, with a new
structure. The two read-only scripts predate the interruption (`k9_address_record.py`, 08:54 UTC) or were written after it
(`positive_control_choice.py`); neither was affected.

## 1. The files

| file | what it is |
|---|---|
| `docs/b4_observation_contract.md` | DRAFT v0.5 (v0.1 `e91650b`, v0.2 `d8ef6cf`, v0.3 `df3b65e`, v0.4 `6927c24`, each held; the revision notes list what changed; v0.4 and v0.5 are targeted edits on v0.3, not a rewrite): §0 status index; §1 position; §2 the stimulus; §3 the raw readout — the **logical view** with per-representation retained / derived / absent status and a declared `context` (3.1), the **four retained representations** (raw return in quarantine; ledger, target and memo projections) and the carrier record with what each digest covers — `trace_sha256` the Q-grid digest only, four separate commitments, no whole-record digest in the archive — the adapters and their scope, the `fabric` descriptor copied exactly (3.2), the sample points (3.3), D1 and the scoring-domain limit (3.4), the source binding (3.5); §4 the three objects `O` / `F` / `X` (4.1), the exact field sets **with the phase-dependent sets of an invalid `O`** (4.2), the field-aware A3 rule (4.3), D3 (4.4); §5 the transaction — the readiness table with (c)'s pre-write sample (5.1), idle (5.2), cleanup (5.3), **the frame binding conditional on mechanism × predecessor context** apart from Q restoration (5.4), the session-opening record and the session root (5.5), A5 as a decision table with the qualification-only protocol (5.6), faulted / interrupted retention with the stop location (5.7); §6 INIT / SRVAL — the two points (6.1), D2 (6.2), the per-mechanism order with (c)'s prior configuration (6.3), the same-element cross (6.4), **6.5 the validated reference, planted priors and two episodes read as restore / capture / hold / inconsistent / unknown**, G6 (6.6), **6.7 per-corner readings → quantities → the precedence-ordered table with a not-demonstrated row, a constant restore an absent SRVAL effect**; §7 positive controls; §8 the two holdouts; §9 the bench and board lists; §10 unresolved; §11 what the document does not do |
| `docs/b4_preregistration.md` | v0.0.2 → v0.0.3: a revision note and three one-line pointers (sections 5, 6, 8) to the contract, re-aimed at v0.2's sections in the correction round; every `<unresolved>` unchanged; not frozen |
| `docs/b4_architecture.md` | §13 one row (2c-obs: v0.1 delivered, held, corrected to v0.2 in the same unit; its contents and its unresolved list); §14 one reference line. No numbered section, threshold, pin string or the first line touched; **the v0.2.0 revision note's choice 7 is NOT amended** — contract 7.2 records the selection rule as a proposal beside it, and the note is amended only if the owner accepts the revision |
| `k9_address_record.py` / `.txt` | read-only: per address the K9 covered / applicable counts under (b′) and (b) summed over the 32 `pair_*/k9.json` of the committed `b4-sim-4` archive; the choice rule's first half |
| `owner_authorisation_2026_10_21.txt` / `AUTHORISATION_SOURCE.txt` | the owner's authorisation of this unit and its source note, as supplied with the review of `e91650b` (byte-identical to the review directory's copies) |
| `static_contract_checks.py` / `.txt` | read-only static checks against the owner's counterexamples — on `d8ef6cf` (C1–C4, v0.3), on `df3b65e` (R1–R4, v0.4) and on `6927c24` (two P2, v0.5: the (c) root binding to the session-opening record with its own later `X` and a missing record rejected; four constant-restore classifications; the R-section reads `pair_000`'s ledger and target records and the quarantine record's `fabric` block, and evaluates the written rules of 3.2, 4.2, 5.4 and 6.5–6.7 on symbolic / synthetic values); C1–C4: C1 the legacy quarantine record's dictionary config through the adapter (digest verified under its declared encoding only; the view's vector, genome and derived stimulus digest), the field-aware rule accepting `fabric.kind = "truth"` and the closed set refusing an extra `answer_bits`; C2 every field's earliest phase against its object's immutability phase and `O` holding nothing from P7 on; C3 the owner's A5 counterexample under the post-init projection (pass), a persisting state (fail), a non-arriving injection (not demonstrated); C4 the two-episode rule interpretable at both SRVAL values and the 6.7 classification total with one row per state. R1 the Q-grid digest, the projection's missing raw fields, the two config-digest encodings, the fabric keys / enum, a projection view marking derived and absent fields; R2 the P3 stop's present / absent sets; R3 the frame binding for (a) / (b), for (c) normal and under J3, a fake base under J3 rejected; R4 the stuck reference → `unknown`, healthy / capture / hold readings, ten classification cases incl. mixed restore / capture, both cross-tracking directions, an unknown corner and a faulted corner. No model, fabric, seed, carrier or verifier called; `all_pass: true` |
| `owner_review_4fc3dc7_PASS/` | the owner's PASS review (v0.5), archived byte for byte (9 files incl. `SHA256SUMS`, verified after the copy): README, review_metadata.json, the pin-test output, the independent checks (script output and json), the author's static checks rerun and the copy of the script it ran, the diff check |
| `owner_review_6927c24_HOLD/` | the owner's fourth HOLD review (v0.4), archived byte for byte (9 files incl. `SHA256SUMS`, verified after the copy): README, review_metadata.json, the pin-test output, the static contract probes (script, json, txt), the author's static checks rerun, the diff check |
| `owner_review_df3b65e_HOLD/` | the owner's third HOLD review (v0.3), archived byte for byte (8 files incl. `SHA256SUMS`, verified after the copy): README, review_metadata.json, the pin-test output, the static contract probes (script, json, txt), the author's static checks rerun |
| `owner_review_d8ef6cf_HOLD/` | the owner's second HOLD review (v0.2), archived byte for byte (7 files incl. `SHA256SUMS`, verified after the copy): README, review_metadata.json, the pin-test output, the static contract probes (script, json, txt) |
| `owner_review_e91650b_HOLD/` | the owner's HOLD review of v0.1, archived byte for byte (11 files; `SHA256SUMS` verified after the copy): README, review_metadata.json, the independent reruns of both scripts, the pin-test output, the read-only checks and the selection-consistency record |
| `verification.txt` | the two pin-test modules, run at v0.1 and after each of the four correction rounds, as they came |
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

No program changed, so no mutant battery and no full regression (the owner's review §6: proportionate). Run as a guard against a pin
accidentally touched by the architecture edit, once at v0.1 and once after the correction round: `b4/tests/test_b4_seeds.py` (scans
`docs/b4_architecture.md` for seed literals) and `b4/tests/test_b4_thresholds.py` (the §9 pin strings and the document version) —
all five runs in `verification.txt`, as they came. The second correction round added `static_contract_checks.py` (static / manual examples
corresponding to C1–C4, as the owner's review §7 asked); the third round extends it with R1–R4, the fourth with the root-binding and constant-restore cases; its output beside it. As the
owner's fourth review notes, `all_pass` covers the listed static cases, not a general validator or a state-space proof. The two read-only scripts were not rerun in the correction round: their logic and data
references are unchanged since `e91650b`, and the owner's independent rerun was byte-identical. The contract's internal section
references were scanned against its headings after the rewrite (every `x.y` cited is a heading of the document, a version number or
an architecture section named as such).

## 5. What this unit does not claim, and what it does not authorise

The contract is a draft for review, not a frozen preregistration; its fractions are the host model's under hypothesis v0.3 and say
nothing about silicon; A8 is open; no board was powered, no RTL, bench, XDC or schema file was written; no seed was derived; no
archive, threshold, label, receipt or decision changed; the carrier-v2 unit, 2d, routing, `b4-gate-2`, any new batch, push and merge
remain the owner's.

## 6. The correction round — the owner's HOLD on `e91650b` (R1–R3, D1–D4, one P3), answered in v0.2

The review is archived in `owner_review_e91650b_HOLD/`. Independent checks there: clean tree at `e91650b`, nine files, protected
surfaces unchanged; both scripts rerun byte-identical and the nine rows reselected with exact fractions; the pin tests 29 OK.

| finding | what was wrong in v0.1 | where v0.2 answers it |
|---|---|---|
| **R1** (P1) — a common model / carrier format was not established: the model trace (`b4_ff_observation_trace` 0.2.0: `hypothesis`, `mapping`, `fabric`, `config`, `stimulus`, `initial`, `elements`, `steps`) has none of the proposed carrier header, so "one schema, only the null rule differs" was false; the A3 deny-list forbade only what it named; the B1 zero-table check was misplaced; the physical-values-all-score rule had an unnamed comparison boundary against the model's None-scores-nothing rule | §3.1 the common payload (a subset the legacy trace already has); §3.2 the two provenance branches, field by field, the legacy trace represented as it is with no board witness fabricated; §3.5 the branch taken from the trusted context (the batch's formal source / the manifest's pinned carrier), never from a self-declared tag; §4.2 the carrier record's exact closed field set with types, `mapping_sha256` / `hypothesis_sha256` removed from the record; §4.3 closed sets at every level (an unlisted `answer_bits` refused by closure), the deny-list kept as defence in depth, the guards named as what a key list cannot replace, the zero-table check placed in `sign_reply.expected_tables`; **D1 as ruled** in §3.4 — type-exact physical 0 / 1, an unobtainable sample a named fault with raw evidence retained, the sampling path the carrier's to establish; the **scoring-domain limit** named on `pair_000/k10.json` observation 20 (genome 1024, model fitness 24, 32 masked null cells, physical completions 24–56 — arithmetic, not a measurement), with the four-part rule (board fitness over the full mask with no decode filtering; the host recomputes that; the unmodelled cells reported and the restricted score labelled a diagnostic, never the board fitness; no agreement sentence without the count) and the board-study metric left to 2c; **D3 as ruled** in §4.4 — provisional names, one entry point dispatching to typed branches, the source-dependent rules listed (not only null), nothing implemented |
| **R2** (P1) — the cycle raised the mechanism before the stimulus and the stimulus's step 0 raised it again; the final step could leave SR asserted and the clock high yet the next initialisation followed directly; the first candidate's predecessor did not exist; the order of pre-init sample / assert / release / init sample / readbacks was unstated and incoherent for configuration-as-init; frame equality was read as restoration; "the next step is SRVAL's recovery" was wrong; G6 was not visible; A5 lacked a projection, roles and a specified injection | §5.1 P1–P10 with **one** initialisation = the stimulus's step 0, P9's event outside the scored observation; §5.3 the cleanup phase (inputs to 0, clock to 0 as a recorded falling edge, a sample; never scored) and v0.1's SRVAL "recovery" withdrawn; §5.4 frame equality and Q-state restoration as two witnesses; §5.5 the opening baseline as the first predecessor and the session's base-state reference; §6.3 the per-mechanism order table, (c) coherent with the write as the event; §6.6 the G6 limit — no unrecorded operation to force the atomic readout, unobservable contexts reported and `unknown`; §5.6 A5's compared projection (steps and `cleanup.final_q`; `seq`, `nonce`, `predecessor`, `idle_status`, readbacks, `initial.q` excluded), the pre-init sample as the leftover witness and the post-init samples as the compared ones, *c′* specified with its witness (its final sample = *c*'s second `initial.q`, else the test is not run), "not globally maximal" stated, faulted prefixes retained raw and never scored; **D2 as ruled** in §6.2 — three candidates retained with their feasibility questions, one declared, none selected, no event-to-Q effect from a name or from equal frames |
| **R3** (P1) — "the four candidates above" were two pairs on different elements and backgrounds (AFF @ 000000 vs BFF @ 000008; A5FF vs C5FF), not a factorial cross; a failed cross was attributed to the hypothesis and exonerated the carrier; SR = 1 was treated as a completed restore; the outcome table was unconditional and implied a settled reduced claim | §6.4 the 2 × 2 cross on the **same element and background** (INIT bit × SRVAL bit, all else fixed), what each readout must and must not track, the scope (main and x5FF; FF context only; the clock-mode context reported if not run), the A2 pairs not asked to serve as the cross; §6.5 the SR restore evidence — asserted across a capture edge with `d` opposite to the predicted SRVAL, so the restore completes under either `sr_kind`; latch and tied-low excluded; §6.7 the outcome table conditional on A1–A7 and context coverage, a pass establishing the demonstrated context only, `unknown` relations withheld from the semantic claim and the certificate-map scoring while the raw task fitness is untouched and the reduced claim is 2c's decision; a failed cross marked `failed` / `unresolved` with the evidence preserved and **no attribution** — mechanism, stimulus / timing, instrumentation or model mismatch separated only by independent evidence; no automatic hypothesis revision or carrier re-tuning |
| **D4** — the nine pairs accepted as a data-informed DRAFT A2 proposal, not certified combinations, board effects, a whitelist or a guarantee about the fixed qualification stimulus; the new rule differs from the architecture's recorded choice 7 and must be recorded as a revision with reason and precedence | §7.2 the rule written as a qualification-selection proposal revising choice 7 (the source sim-4 under task-v0.2 and (b′) instead of gate-1; address-first pooled fraction; main / x5FF each), with precedence (choice 7's wording stands until the owner accepts; the architecture's note is **not** amended in this unit); §7.3 what the pairs are and are not, the B4Q stimulus's own predeclared conditions |
| **P3** — "five slice-wide controls other than `sr_kind`" | §7.3: four |
| the missing authorisation file | archived beside this README with its source note, as supplied; no byte-identity-to-an-export claim |

Nothing in the correction round changed `b4/`, a hypothesis, a pinned surface, a statistic, an archive, a schema implementation, a
legal-write rule or a threshold; N / `B*` / prediction / sessions and A8 remain unresolved; 2c is not frozen.

## 7. The second correction round — the owner's HOLD on `d8ef6cf` (C1–C4, one P3), answered in v0.3

The review is archived in `owner_review_d8ef6cf_HOLD/`. Independent checks there: 29 pin tests OK; protected surfaces unchanged;
the first review's archive and the authorisation byte-identical; the selection scripts unchanged; four static probes (C1–C4) on a
retained quarantine record's config / header fields and small synthetic records — reproduced and answered by `static_contract_checks.py`.

| finding | what was wrong in v0.2 | where v0.3 answers it | static check |
|---|---|---|---|
| **C1** (P1, residual R1) — the "common payload" said `config` is a list of 21 ints, but the legacy trace's `config` is an address → bit **dictionary**; the legacy trace has **no** `stimulus_sha256`; its `config_sha256` is `sha256(json.dumps(dict, sort_keys=True))` with default separators, not a canonical-list digest; a value-level deny-list would reject the formal source's legitimate `fabric.kind = "truth"` | §3.1 a **logical view** that readers build, never a format a source writes; §3.2 the two **raw wire formats** field by field with the **adapter** (dictionary → vector in the mapping's order; the raw digest kept and verified **under its declared encoding only**; `stimulus_sha256` **derived** for the model by the ledger's existing `sha256_json(list(stimulus))` rule, bound by `trace_sha256`, written by the carrier); the legacy trace neither an instance of the view type nor claimed to be, nothing added / renamed / re-encoded / retagged; §4.3 **field-aware** values — enum identity fields validated by enum (`fabric.kind`, `init_event.mechanism`, the statuses), fixed-text fields by equality, identities by type and binding, the deny-list on **key names only**; §4.4 view / model-raw / carrier schemas with the adapter, one entry point | C1: the retained record's digest verifies under its declared encoding; the adapter yields the 21-vector and genome; the derived stimulus digest; a legitimate model record passes; `answer_bits` is refused by closure |
| **C2** (P1, residual R2) — the observation was required durable at P6 yet its closed field set required `cleanup` (P7) and `idle_status` (P10); the current transaction's P8 / P9 witnesses had no field; `predecessor` held the previous transaction's values; the opening baseline needed a predecessor without a root case | §4.1 three objects — `O` immutable at P6a (nothing from P7 on), `F` at P6b binding `observation_sha256`, **`X` the transaction close** at P10 binding `observation_sha256` and holding `cleanup`, `base_readback_sha256`, `base_state_sample`, `idle_status`, `status`; §4.2 the exact sets; §5.1 the phase / record-readiness table; §5.5 `predecessor` a **reference** `{kind, seq, close_sha256}` to the previous `X`, the **session root** `{session_root, null, null}` as the terminating case, the root's P9 sample the base-state reference; §5.7 faulted / interrupted transactions keep whichever objects exist with non-success statuses, nothing reconstructed | C2: no field's earliest phase exceeds its object's immutability phase; `O` has no P7+ field |
| **C3** (P1, residual R2) — A5 required `initial.q` to differ yet compared `steps[0].q_before` (its copy) for equality; the injection path (P7–P9 omitted, inputs held) conflicted with the normal signing precondition; no distinct record type / status | §5.6 the **post-init projection** (`steps[0].q_after`, `steps[1:]`, `X.cleanup.final_q`; the pre-init state excluded in **both** places); the injection witness checked apart (differs from the first `initial.q` **and** equals the injecting transaction's recorded final state); the **qualification-only protocol J1–J3**: J2 a fully normal signed transaction whose `X` is written `injection_open` with the omitted fields absent; J3 signed normally with `predecessor.kind = "a5_injection"` (the one value accepting a non-`closed` predecessor, only inside B4Q under the plan's A5 ruling), no input or clock changed between J2's last step and J3's write, the pre-init sample an actual sample (for mechanism (c) taken before the write, never the cached reference), the recorded `pre_init_cleanup`; record type `a5_qualification`, never a mapping observation; the **three-row decision table** (not demonstrated / pass / fail); the normal-gate refusal explicitly *not* A5 | C3: the owner's counterexample → pass; persistence → fail; non-arrival → not demonstrated |
| **C4** (P1, residual R3) — one fixed `d` cannot be opposite to both SRVAL = 0 and SRVAL = 1, so the same-stimulus cross had no satisfiable SR condition; "SRVAL only" / "INIT only" also matched the failure row | §6.5 **one fixed stimulus for every corner with two SR-restore episodes** (`d = 0`, `d = 1`) and two reference captures, judged jointly: `R0 = R1` ⇒ restore (its value the evidence), `(R0, R1) = (K0, K1)` ⇒ capture, else inconsistent — no candidate-dependent adaptation, a capture opportunity for either `sr_kind`; §6.7 four defined quantities and a **precedence-ordered classification** (row 1 cross-tracking or inconsistency = failed / unresolved, no attribution; rows 2–5 the four `(init_effect, srval_effect)` values partitioning the rest), so an absent main effect alone is a reduced claim and never also a failure | C4: the two-episode rule interpretable at both SRVAL values; the classification total over 16 states, one row each; srval-only → 3, init-only → 4, any cross-tracking → 1 |
| **P3** — the final clock described as possibly 1 under the task's fixed shape | §2.2: task-v0.2's stimuli end at clock 0 (K even, from 0); the general grammar may end high; cleanup handles the general case | — |

Accepted directions of the first round preserved (the owner's §6): the scoring-domain counterexample and its four rules, the trusted
source selection, no hypothesis / mapping reference in carrier output, frames apart from Q state, cleanup unscored, G6, the
same-element factorial, bounded context claims, D4 as a data-informed draft revision. Nothing in this round changed `b4/`, a
hypothesis, a pinned surface, a statistic, an archive, a schema implementation, a legal-write rule or a threshold; the
authorisation / source archive was not reopened.

## 8. The third correction round — the owner's HOLD on `df3b65e` (R1–R4), answered in v0.4

The review is archived in `owner_review_df3b65e_HOLD/`. Independent checks there: 29 pin tests OK; protected surfaces unchanged
since `fceedd6`; the second review's archive byte-identical; the selection scripts unchanged; the author's static checks rerun
byte-identical; four static probes on `pair_000`'s ledger and target records, the quarantine record and symbolic witnesses.

**Interruption, disclosed.** The first attempt at this round (a whole-document rewrite) was stopped by the assistant's safety
classifier before any file was written; by instruction that text was not reproduced. The round was then done as targeted,
finding-by-finding edits on v0.3 (sections 3.1–3.2, 2.4, 3.5, 4.2, 4.3's enum row, 5.1, 5.4, 5.6's J3 cell, 5.7, 6.3, 6.5, 6.7,
the header, the status index and one bench row), each applied and checked separately; the owner's authorisation for the
same-unit repair was unchanged.

| finding | what was wrong in v0.3 | where v0.4 answers it | static check |
|---|---|---|---|
| **R1** (P1) — the view's `trace_sha256` was described as a whole-raw-record digest and "the ledger's existing digest"; in the code `trace_sha256 = sha256_json(q_grid)` (`b4_engine`, `b4_target`), archived observations are projections without raw fields, a full `observe()` return exists only in quarantine; the `fabric` keys / enum were paraphrased wrongly (`dropout` for `dropout_sha256` + `dropout_count`, `custom` omitted, swap names added); "no stimulus field" | §3.1 the view with per-representation **R / D / A** status, `q_grid_sha256` (= the ledger's `trace_sha256`, the grid only), `record_sha256` absent for projections and **new** for the carrier; §3.2 the four retained representations with fields, digest encodings (`raw-dict-default`, `proj-dict-canonical`, `list-canonical`) and what each digest covers, "four separate commitments, not one", the adapters' scope (projection adapter reads the entry **with the task**, derives and labels; historical readers stay the authority; nothing under `evidence/` touched), the `fabric` descriptor copied from `provenance_findings`; §2.4 and §3.5 reworded; §4.3's enum row corrected | R1 |
| **R2** (P1) — an invalid `O` still required both readback digests; a P3 stop has no P4 readback | §4.2 the phase-dependent exact sets of an invalid `O` (always-present keys + the keys of the completed phases; absent otherwise; `fault = {code, phase_reached, step_reached}`); §5.7 refers to it | R2 |
| **R3** (P2) — §5.4 required `O`'s two readbacks equal, but for mechanism (c) they are the prior configuration and the candidate; under J3 the prior configuration is *c′*; (c)'s pre-write sample was not in the readiness table; the view's `pre_init_state` fixed the inputs at zero against J3 | fields renamed `_pre_event` / `_post_event`; §5.4 the binding **by mechanism × predecessor context** (for (c): the base, or *c′*'s post-event readback under J3; no base restoration inserted); §5.1 P2 / P3 / P4 rows per mechanism; §6.3 the prior-configuration readback and the pre-write sample; §5.6 J3's cell; §3.1 `pre_init_state.context ∈ {idle, a5_injection}` with the held inputs recorded under `a5_injection` | R3 |
| **R4** (P2) — `R0 = R1` was read as a restore even when `K0 = K1` (a held or non-capturing element); no derivation of 6.7's quantities when a corner has no restore value | §6.5 the reference must be valid (`K0 = 0`, `K1 = 1`) and the priors as planted (`P0 = 1`, `P1 = 0`) before any reading — else `unknown`, raw samples retained; the joint reading restore / capture / hold / inconsistent with the identifiability argument; §6.7 the per-corner readings `(i_c, s_c)`, the quantities `not_assessable`, `init_effect`, `init_absent`, `srval_effect`, `srval_absent`, `cross_tracking`, `inconsistent` defined from them (all-capture or all-hold = SRVAL absent; mixed = inconsistent), the classification with row 0 **not demonstrated**; the truncated sentence folded in | R4 |

Accepted directions of the earlier rounds preserved (the owner's §1). Nothing in this round changed `b4/`, a hypothesis, a pinned
surface, a statistic, an archive, a schema implementation, a legal-write rule or a threshold; the architecture's choice 7 note is
not amended; the authorisation / source archive was not reopened.

## 9. The fourth correction round — the owner's HOLD on `6927c24` (two P2), answered in v0.5

The review is archived in `owner_review_6927c24_HOLD/`. Independent checks there: 29 pin tests OK; the author's static output
reproduced byte for byte; the third review's archive byte-identical; protected paths unchanged; `pair_000`'s ledger, target and
memo digests re-checked against the corrected representation rules. The two P1 of the previous round are accepted as addressed.
The owner's evidence note on `owner_review_df3b65e_HOLD/author_static_rerun.txt` (a trailing blank line, originating in the
owner's own artefact) is followed: the raw copy is preserved untrimmed.

| finding | what was wrong in v0.4 | where v0.5 answers it | static check |
|---|---|---|---|
| **R1** (P2) — 5.4's (c) row grouped `session_root` with `closed` and bound the root's pre-event readback to a predecessor `X` that does not exist (the root's predecessor is `{session_root, null, null}`; its own `X` is written later) | §5.5 the **session-opening record** `session_open = {instrument, startup_readback_sha256, base_frames_reference_sha256, status}`, written after the sha-gated carrier load and the identity page and before anything is signed: the fabric as loaded against the **trusted input** — the pinned carrier's base-frame content (the carrier manifest's blank target frames, `frame_table_sha256`, the bitstream digest), pinned in the instrument manifest; `open` only on equality, else `refused` (no root, nothing signed, the record retained); §5.4 the `session_root` row split from `closed`, the root's (c) pre-event readback bound to `session_open.startup_readback_sha256`, never to its own `X` or to a predecessor; §4.1 the record listed; the root's `O` names it in `init_event.parameters.session_open_sha256` | R3: the root binds to a record available before its event; without it refused; its own later `X` rejected; a differing startup readback refuses the session |
| **R2** (P2) — four corners all `restore` to one value with INIT tracking correctly gave `srval_effect = false` and `srval_absent = false`, hence `inconsistent` and row 1, against the accepted rule that an absent main effect alone is a reduced claim | §6.7 `srval_absent` includes the **constant restore** (all four `restore`, `v_00 = v_01` and `v_10 = v_11`); the cross-tracking guard unchanged (a value changing with INIT is row 1); the closing paragraph says where a constant restore lands (row 4 with INIT present, row 5 with INIT absent) | R4: the four constant-restore cases (value 0 / 1 × INIT present / absent) → rows 4 / 4 / 5 / 5; `restore_value_tracks_init` still → row 1 |

Nothing in this round changed `b4/`, a hypothesis, a pinned surface, a statistic, an archive, a schema implementation, a legal-write
rule or a threshold; choice 7 stays unchanged pending acceptance; the authorisation / source archive was not reopened.

## 10. Closure — the owner's PASS on `4fc3dc7` (2026-10-21)

The review is archived in `owner_review_4fc3dc7_PASS/`. Independent checks there: 29 pin tests OK; the author's static output
reproduced byte for byte; eight root-bootstrap static cases (an opening bound to a preexisting trusted reference; its absence; a
future / own-close reference; a startup mismatch; a self-declared wrong reference; a wrong root-to-opening hash; a drift of the
root's pre-event value) and the four constant-restore cases independently derived (rows 4 / 4 / 5 / 5; restore values tracking
INIT still row 1); the fourth review's nine files archived byte-identical; protected paths unchanged from `fceedd6`.

**Accepted.** The document contract (every correction of sections 6–9 of this README) and **D4**: `docs/b4_observation_contract.md`
§7.2's rule and §7.3's nine pairs as the data-informed DRAFT A2 qualification-selection choice for later B4Q planning, selected on
host-model data as disclosed in §7.4.

**Closure edits (documents only, as the review's section 3 allows; no test, static script, mutant or experiment rerun):**
this review archived; the unit marked closed here and in `docs/b4_architecture.md` §13 / §14; the architecture's v0.2.0
revision note's **choice 7** synchronised — the accepted rule, its reason and precedence appended, the gate-1 wording kept as the
history of the first choice, nothing of the K9 panel, the applicabilities, the model, the method, the thresholds or the archives
changed; the contract's heading and standing note carry the acceptance and its limits, §7.2's precedence paragraph marked
resolved, unresolved item 7 struck as resolved; the skeleton's note and A2 pointer updated.

**What the PASS does not establish** (the review's section 4, copied in substance): A8, a working initialisation mechanism,
electrical timing, a schema / adapter implementation, carrier RTL, legal compositions, sampling feasibility on every
configuration, silicon agreement, a gate result; the session-opening record and its base-frame reference are requirements on the
future carrier / tool implementation, not something built or measured; the physical full-mask fitness / model-null comparison
boundary stays explicit and unresolved for the board-study metric; N, `B*`, the prediction, the session partition, the whole-site
holdout choice and 2c's freeze are not supplied. The sim-4 no-go and all existing evidence are unchanged. No production draw or
run, `b4-gate-2`, protocol revision, RTL, board work, push or merge is authorised by it. The trailing blank lines in the two
archived owner stdout files remain untrimmed, as the review asks.

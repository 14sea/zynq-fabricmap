# B4 — the 2c-obs unit: the observation contract (documents and two read-only scripts only, 2026-10-21)

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
submission `e91650b` (v0.1) was held by the owner (section 6); the correction round is the second commit of the same unit. Nothing
pushed, nothing merged.

**Interruption, disclosed.** The first attempt to write the contract document in the preceding session was stopped by the
assistant's safety classifier before the file existed; that text was not retained and, by instruction, not reproduced. The present
`docs/b4_observation_contract.md` was drafted afresh in this session from the sources its standing paragraph names, with a new
structure. The two read-only scripts predate the interruption (`k9_address_record.py`, 08:54 UTC) or were written after it
(`positive_control_choice.py`); neither was affected.

## 1. The files

| file | what it is |
|---|---|
| `docs/b4_observation_contract.md` | DRAFT v0.2 (v0.1 at `e91650b`, held; the revision note lists what changed): §0 status index; §1 position; §2 the stimulus (the step grammar with `init` at index 0 only, task-v0.2's shape, the application rule with four declared-and-recorded timing intervals, the stimulus digest); §3 the raw readout — the **common payload** (3.1), the **two provenance branches** with their field lists and the legacy model trace represented as it is (3.2), the sample points (3.3), **D1 as ruled** and the model / board **scoring-domain limit** on the retained k10 counterexample (3.4), the source bound to trusted identity (3.5); §4 the three records, the carrier record's exact field set with types (4.2), the A3 rule as **closed sets** with the deny-list as defence in depth and the B1 zero-table check in the signed-reply layer (4.3), **D3 as ruled** (4.4); §5 the **transaction** — P1–P10 with one initialisation = step 0 (5.1), idle as a witnessed state (5.2), the **cleanup phase** (5.3), frame equality versus Q-state restoration (5.4), the **opening baseline** as the first predecessor (5.5), A5's projection / sample roles / specified injected state and witness / faulted prefixes (5.6); §6 INIT / SRVAL — two observation points (6.1), **D2 as ruled** (6.2), the per-mechanism order of samples and readbacks (6.3), the **same-element 2 × 2 cross** (6.4), the SR restore evidence versus SR = 1 (6.5), the G6 limit (6.6), the conditional outcome table with attribution left to independent evidence (6.7); §7 positive controls — the quantifiers, the rule as a **qualification-selection proposal revising choice 7** with reason and precedence (**D4**, 7.2), the nine pairs as a data-informed draft (7.3, the P3 four slice-wide rows fixed), the data influence (7.4); §8 the two holdouts; §9 the bench and board lists; §10 thirteen unresolved items; §11 what the document does not do |
| `docs/b4_preregistration.md` | v0.0.2 → v0.0.3: a revision note and three one-line pointers (sections 5, 6, 8) to the contract, re-aimed at v0.2's sections in the correction round; every `<unresolved>` unchanged; not frozen |
| `docs/b4_architecture.md` | §13 one row (2c-obs: v0.1 delivered, held, corrected to v0.2 in the same unit; its contents and its unresolved list); §14 one reference line. No numbered section, threshold, pin string or the first line touched; **the v0.2.0 revision note's choice 7 is NOT amended** — contract 7.2 records the selection rule as a proposal beside it, and the note is amended only if the owner accepts the revision |
| `k9_address_record.py` / `.txt` | read-only: per address the K9 covered / applicable counts under (b′) and (b) summed over the 32 `pair_*/k9.json` of the committed `b4-sim-4` archive; the choice rule's first half |
| `owner_authorisation_2026_10_21.txt` / `AUTHORISATION_SOURCE.txt` | the owner's authorisation of this unit and its source note, as supplied with the review of `e91650b` (byte-identical to the review directory's copies) |
| `owner_review_e91650b_HOLD/` | the owner's HOLD review of v0.1, archived byte for byte (11 files; `SHA256SUMS` verified after the copy): README, review_metadata.json, the independent reruns of both scripts, the pin-test output, the read-only checks and the selection-consistency record |
| `verification.txt` | the two pin-test modules, first run at v0.1 and second run after the correction round, as they came |
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
both runs in `verification.txt`, as they came. The two read-only scripts were not rerun in the correction round: their logic and data
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

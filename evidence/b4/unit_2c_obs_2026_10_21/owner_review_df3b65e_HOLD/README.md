# Owner review of df3b65e — HOLD, four remaining document contracts

2026-10-21. Reviewed exact tip `df3b65e8072eaab96d7c19d9d10e177b14e1ff9b` on `b4-2c-obs`, parent `d8ef6cf`. Tree clean. This is an independent, read-only review of the same 2c-obs document unit, not a new implementation or experiment.

## 1. Independently checked and accepted

- The two document-pin modules independently pass: **29 tests OK**, no skip. No production seed derivation or new observation was performed.
- The author's static checks rerun from a temporary copy produce byte-identical output with `all_pass: true`; the tracked script/output were not overwritten. Those checks establish the cases they enumerate, not the additional cases below.
- `b4/`, hypothesis/domain, statistics, historical pinned surfaces, production archives and decisions are unchanged from `fceedd6`. Selection scripts and their outputs are unchanged from `e91650b`; they were not rerun. Prior review's seven files are byte-identical, including validated checksum entries.
- The logical-view/raw-format separation, legacy configuration encoding, field-aware handling of `truth`, O/F/X separation on the normal path and session-root chain address the earlier review's direction.
- The A5 comparison now correctly excludes both copies of the pre-init state; its pass/fail/not-demonstrated examples work. The qualification-only injection exception is explicit. The A8 same-stimulus design is feasible in its healthy-reference case, and its final precedence table no longer overlaps.
- Data-informed A2 selection remains accepted as a draft proposal with the disclosed influence and precedence. No need to rerun selection or reopen the authorization-source archive.

## 2. R1 — P1: the new source binding conflates a Q-grid digest with a whole raw-record digest

References: contract **3.1 line 134**, **3.2 lines 147, 151, 156–158**, 4.3; `b4_engine.py:252`, `b4_target.py:141`.

The view defines `trace_sha256` as SHA256 of the whole raw record and calls this the model ledger's existing digest. That is false: both the engine ledger and retained target records hash **only `q_grid`**. Independently checked on committed sim-4 pair 000: the ledger's trace digest is `5cd4aa74851515af0e30e8acb66c71905650f2ef1a3da67905308c687adfb6c5`, exactly the Q-grid hash. Changing a stimulus commitment while keeping the grid leaves that digest unchanged. This is not an attack that the entire archive verifier accepts: the surrounding bindings check it separately. It shows that this one digest does not bind the raw configuration, stimulus, provenance or context as the new document claims.

Normal archived ledger entries are **projections**, not preserved full `observe()` returns: they have genome, grid and separate commitments, but not raw dictionary config, `initial`, full `steps`, `stimulus` and source blocks. The statement that all retained archive traces have the raw dictionary/config encoding is therefore also inaccurate. A retained quarantine may contain a full raw return; that is a different representation.

Correct the binding map without changing archived bytes or production code: distinguish the existing Q-grid digest from a full raw-record/file/envelope digest, name what each covers, and say which actual retained representation each adapter consumes. If reconstructing a logical view from projections, mark reconstructed fields as derived and name the surrounding bindings; do not claim an original full raw record or its hash was retained. It is also acceptable to limit the new raw adapter's scope explicitly and leave historical projections with their recorded version's reader. A new whole-record hash, if useful for future records, must be labelled new/derived rather than reinterpreting the old field.

**The same raw-format table has a P2 shape error:** actual `fabric` keys are exactly `kind, effect_sha256, dropout_sha256, dropout_count, seed`; its enum is `truth | permuted | dropout | custom` (`b4_execution.provenance_findings`). The document substitutes `dropout`, omits `custom`, and adds hypothesis swap names. With the document's closed-set rule, valid raw metadata would still fail. Copy the actual descriptor contract; hypothesis fixture/swap identity is separate. The sentence “no stimulus field” should say “no stimulus_sha256 field”; the raw trace does have `stimulus`.

## 3. R2 — P1: invalid O still requires future witnesses

References: **4.2 lines 225–239**, **5.1 P3/P4**, **5.7 lines 382–390**.

The normal-path split solves the earlier P6-versus-P10 problem. The fault path still contradicts the exact O schema: 4.2 requires both PRE-INIT and POST-INIT readback hex digests for O; `invalid` only adds `fault`. But 5.7 seals O invalid on a P1–P5 failure. For example, a sample fault during P3 occurs **before P4 obtains the POST-INIT readback**. There is no real value for that required field. Earlier faults also lack `initial` or step data. The explicit absent-field exception is currently only for faulted **X**.

Define phase/status-dependent required and allowed fields for a partial invalid O, or a distinct bound partial-record form. Retain exactly the acquired prefix, its source bindings and a stop location; no invented hex, fabricated samples or copy from another transaction. Keep the full requirements for complete O. A small phase/field table and static early-stop example suffice; no persistence implementation is requested.

## 4. R3 — P2: configuration-as-init contradicts the universal frame/context rules

References: **5.4 line 330**, **6.2–6.3 lines 409–425**, **6.7 preconditions**; A5 J3 and 3.1's pre-init context.

For mechanism (c), 6.3 assigns the PRE-INIT witness to the base before the candidate write and the POST-INIT witness to the candidate, equal to staging. Section 5.4 nevertheless requires **O's two readbacks equal to each other**; 6.7 requires that witness on every cross record. For any candidate differing from base, the correctly obtained witnesses necessarily violate 5.4. Frame invariance across a separate init event is appropriate for (a)/(b), not across (c)'s configuration-changing write. This inconsistency predates this round and I missed it in the earlier reviews; it is not a new author regression.

Make the frame-binding rule explicitly conditional on mechanism and predecessor context: before/after a configuration write bind the actual prior configuration and staged candidate separately. Under J3 the prior configuration is **c-prime**, not restored base; no fake base readback or inserted base restoration may be used. Align the phase/readiness table with the actual pre-write sample for (c).

Also make the already declared J3 input exception explicit in the logical view: 3.1 currently types `pre_init_state` with clock/CE/SR/D all fixed zero, while J3 requires copying the actually held nonzero inputs into `initial` and 3.2 adapts that field directly. A declared qualified context is allowed; fabricated zeros are not. This is a conditional-contract correction, not selection/authorization of an init mechanism or a new operation.

## 5. R4 — P2: SR restore is declared before its capture reference is validated

References: **6.5 lines 454–474**, **6.7 quantities lines 486–493** and author's C4 static check.

The new two-episode design works for healthy reference captures. Its written first row unconditionally calls `R0 = R1` “a restore occurred.” A retained-value/static counterexample is **R0=R1=K0=K1=0** (similarly all ones): the SR-on and SR-off evidence are identical, and the reference has not shown either D can be captured. A held/non-capturing element is classified as a successful restore at that corner. This is an evidence-identifiability issue, not a claim about how actual silicon will behave.

Require/define the reference-control validity before making the causal restore claim, or weaken that local reading to consistency and specify what additional joint evidence establishes it. Failed or non-discriminating references need an explicit unresolved/not-demonstrated path with their raw values retained; do not assume they passed from the stimulus labels or from A2 in another background. The author's helper always uses healthy `K0=0,K1=1` and therefore does not cover this case.

Finally, connect 6.5 to 6.7 for **absent** restore evidence: a `capture` corner has no SR-restore value, yet `cross_tracking` compares such values. State how all-capture and mixed restore/capture corners produce the four quantities/status. The 16 precomputed-Boolean cases prove the final row priority only, not that raw corner data can always be classified. A few manual raw-corner examples are sufficient; do not build a new simulator.

## 6. Complete the existing unit once

Continue under the existing document-repair authorization; resolve R1–R4 together and submit once. No scope proposal, per-fix approval, prescribed date or commit count. Keep the accepted corrections above. Fold the truncated “and do not.” sentence at the end of 6.5 into the same edit.

Only changed document pins and targeted static/manual counterexamples are needed. No full suite, mutant battery, duplicate fixture archive, new model/board observation, production seed derivation, schema implementation or production-code change is requested. No method/threshold/archive/receipt/label/no-go change, RTL, push or merge is authorized by this review. A8, the board-study metric, N/B*/prediction/sessions and 2c freeze remain unresolved as already stated; the HOLD is for the concrete contract contradictions above, not for leaving those legitimate future decisions open.

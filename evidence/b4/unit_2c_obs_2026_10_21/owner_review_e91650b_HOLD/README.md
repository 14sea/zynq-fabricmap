# Owner review of e91650b — HOLD, 2c-obs document unit

Reviewed on 2026-10-21, exact tip `e91650b828bfbb06f24881f8c3e8cc0dac357e6d`, branch b4-2c-obs. The unit is within the authorized documents-only scope. The missing authorization file is not a scope/approval defect: the authorization was given in this conversation and is supplied here for routine archival, with its source description. This review assesses the submitted new draft; it does not reconstruct or adjudicate the earlier unretained, classifier-stopped attempt.

**HOLD for three substantive contract issues below.** The data inventory and protected surfaces pass; no experiment, production draw, hypothesis change, gate or hardware work is needed to correct these documents. Complete all corrections within this unit, then submit the whole unit once. No new scope proposal or intermediate approval is required.

## 1. Independent checks

- Clean tree at e91650b; parent fceedd6. Exactly nine changed/new files, documents and the two read-only aggregators with outputs. b4/, B1/B2/B3 pinned surfaces, certificates, historical production archives and decisions are unchanged.
- Both submitted read-only scripts were independently rerun; stdout matches each retained .txt byte-for-byte. A separate standard-library, exact-Fraction calculation reselects all nine address/background proposals and agrees with the author's output, including tie-breaks. No model observation or production seed derivation is involved.
- The two document-sensitive test modules were independently rerun: 29 tests OK, 0.659 s, no skips. Their anchor tests use fake anchors/literal masters; no production set is derived. These tests guard document pins; they do not validate the new draft's semantic adequacy.
- No full regression, mutant battery, production preflight, new exploration, verifier re-judgement or board activity was run. Existing no-go and exclusion records remain unchanged.

## 2. R1 — P1: a common payload is possible, but the proposed shared schema/source/score contract is not yet consistent

References: contract sections 1, 3.1–3.2 and 4.2–4.4 (notably lines 109–121 and 155–180); b4_ff_model.py observe()'s existing return dictionary.

The draft promises that model and board records are the same object and one schema changes ONLY the null rule under source.kind. Current model traces have schema b4_ff_observation_trace/0.2.0 and fields hypothesis/mapping/fabric/config/stimulus/initial/elements/steps. They have no source.kind, carrier VARIANT, signed commit/readbacks, nonce, timing or init_event header. A validator requiring every section-4.2 carrier field on every model trace would reject the existing model format even with no null cells. The mismatch is larger than a null discriminator.

Specify a common observation payload plus explicit source-specific provenance branches, or a versioned adapter/envelope contract. List which source fields exist for model versus carrier, how a legacy model trace is represented without fabricating board witnesses, and what binds the source discriminator to trusted instrument/manifest identity. An untrusted record cannot grant itself permission for null by calling itself a model. Existing pinned traces/archives are not rewritten or silently retagged. This is a design of a future schema/adapter, not authorization to implement one now.

The A3 rule also needs exact allowed header/nested field sets, types and source bindings, rather than describing the reserved-key deny-list as sufficient. An extra unlisted header such as answer_bits is not prohibited by the stated list. Keep the source/binary/noninterference guards; a key list is not proof against arbitrary semantic encoding. Clarify that the B1 zero-table check belongs to the signed payload/reply layer, distinct from the new raw observation payload.

**D1 ruling:** accept the principle that a successfully obtained physical sample is recorded as the actual type-exact 0/1, without converting it to null from a host decode. An unmodelled value is not fabricated or discarded, and inability to obtain a valid sample is a named fault with all available raw/partial evidence retained. Do not assert that every BEL/configuration automatically supplies a meaningful or usable Q; the carrier must establish the sampling path.

There is a material comparison consequence to name explicitly. In retained sim-4 pair_000/k10.json observation 20 (genome 1024), the model scores 24 with 32 masked null cells. Hypothetical physical 0/1 completions can score anywhere from 24 to 56 under the same public target/weights. This is only a mathematical counterexample, not a board measurement or prediction. Counting raw physical values may be the proposed board scoring rule, but its scoring domain differs from the model's. Report the unmodelled cells and state the limit of model/board score comparability; do not imply score equality follows from a common syntax or compare only model-known cells while calling that the board fitness. Do not put decode-based filtering into the board loop. N/B*/prediction, any corresponding board-study metric decision and 2c freeze remain unresolved; old model results and method stay untouched.

**D3 ruling:** provisional schema filenames are acceptable. One validator entry point may dispatch to typed source branches/common payload. Reject the assertion that null is its only source-dependent rule. Do not implement schema or change b4/ in this correction unit.

## 3. R2 — P1: initialization count, sampling window and final cleanup must form one coherent transaction

References: contract sections 2.1–2.3, 3.3, 5.1–5.3, 6.2–6.3 and A1/A6 acceptance rows.

The task stimulus starts with init. The candidate-cycle diagram already performs init mechanism -> post-init readback -> stimulus; a literal implementation then executes the stimulus's init again. Section 5.2 instead says one initialization at the stimulus head and one after restoring base. Explicitly identify the first event with the stimulus's step 0, or define a deliberate extra event and its consequences. Do not leave carrier designers to guess which reading is intended.

A valid final set step may leave SR asserted (and CE/D nonzero). The diagram restores base and initializes again BEFORE entering idle, but does not explicitly deassert SR/establish the permitted clock context first. That conflicts with the stated init precondition. Define a cleanup phase and its recorded witness, separate from the scored stimulus. Also define the first candidate's predecessor/baseline witness; it cannot depend on a nonexistent previous candidate.

State the precise order of pre-init sample, init assertion/release, init sample and the two configuration readbacks. Their timing references must be coherent for all proposed mechanisms, including configuration-as-init. Configuration-frame equality proves the configuration binding, NOT restoration of sequential Q state or candidate isolation. SRVAL recovery is not guaranteed merely because some next input step exists; it may assert SR again. The final return-to-base/state/idle witness must remain explicit after either kind of operation.

Keep the v0.3 G6 limit visible: with an inverted latch gate open at clock low, the model's init readout exists because init assigns atomically without settling. A declared post-release delay or readback cannot be presumed to preserve that transient on a device. Leave A8 unresolved and report contexts the mechanism cannot observe; do not add an unrecorded clock/reset operation to force agreement.

For A5, define the compared observation projection and exclusions for changing record identity fields. A pre-init state sample and the post-init semantic samples need stated roles. Describe the injected leftover as a specified, achievable adversarial state with a witness; one candidate is not proved globally maximal. Preserve incomplete/faulted raw prefixes for audit without treating them as valid scored observations.

**D2 ruling:** retaining unselected mechanism candidates and requiring a declared mechanism is appropriate. Their availability, scope, reset effects and interaction with the transaction remain feasibility questions for the later carrier design/qualification. Neither a proposed command name nor unchanged frames establishes the event-to-Q effect. No mechanism is selected or authorized to run here.

## 4. R3 — P1: A8 needs a same-element cross and bounded attribution/outcomes

References: contract sections 6.1 and 6.4–6.5, plus the nine proposed A2 pairs in 7.3.

“The four candidates above” does not define a factorial cross. The main INIT control uses AFF at background 000000; the main SRVAL control uses BFF at SR-driven background 000008. The x5FF controls likewise use A5FF versus C5FF. Two independent pairs on different elements/backgrounds cannot establish that one element's init and user-SR mechanisms are independent.

Define the A8 cross on the SAME element and background: vary only its INIT bit and SRVAL bit to form the four corners; hold the remaining configuration, stimulus, timing and source fixed. Explain the scope in main/x5FF and storage/clock contexts, what the readouts should discriminate, and what remains unknown. A2's nine demonstration proposals need not themselves serve as this cross.

SR=1 is an input condition, not in every context a completed SRVAL restore. A synchronous FF needs an appropriate capture event; SR tied-low and latch exclusions/context differences remain relevant. Distinguish the raw sample point from the evidence that a restore actually happened. The qualification vectors may stay to the later plan, but their required conditions cannot be omitted from the contract.

A passing pair/cross establishes the demonstrated context; it does not by itself establish all seven semantics on all addresses. Make the outcome table conditional on the other A1–A7 requirements and context coverage. When a relation remains unknown, distinguish withheld semantic claims/certificate-map scoring from raw task fitness; do not silently mask fitness or declare that retaining the same 21 writable bits is already a settled reduced-claim preregistration.

A failed cross cannot automatically be attributed to the hypothesis while exonerating the carrier. It can reflect mechanism, stimulus/timing, instrumentation/implementation or model mismatch. Preserve the evidence, mark the affected qualification/claim unresolved or failed, and leave attribution to independent evidence. No automatic hypothesis revision or carrier re-tuning is approved by the outcome table.

## 5. D4 and ancillary wording

The selection arithmetic and its sim-4 provenance pass. The nine pairs are accepted as a DATA-INFORMED DRAFT A2 proposal, not as certified combinations, board-observed effects, a legal-composition whitelist or a guarantee about the later fixed qualification stimulus. The latter must demonstrate distinguishability under its own predeclared conditions; the archive's changing task stimuli do not prove that future sequence.

The new address-first pooled-fraction/background-count rule over sim-4 differs from the architecture's already recorded v0.2.0 choice 7/A2 rule (gate-1, most-covered unique forced pair, numeric bit/g0/g1 tie-break). Record that explicitly as a qualification-selection proposal/revision with reason and precedence, rather than implying unchanged inheritance. Do not rewrite the historical choice or change the frozen K9 panel/applicability, host method or old verdicts. The extra main/x5FF demonstrations are useful scoped proposals; their empirical support remains the disclosed model data.

Small P3: section 7.3 says “five slice-wide controls other than sr_kind”; there are FOUR such slice-wide rows. Fix alongside the substantive corrections, with no extra review round. The missing owner-authorization file is supplied beside this review; archive it with AUTHORISATION_SOURCE.txt rather than claiming an original exported file was copied byte-identically.

## 6. Complete this same unit; no new scope gate

Continue the authorized documents-only unit and resolve all three issues together, including the D1–D4 decisions above. Update the contract, pointers/status and evidence explanation as needed. No separate scope draft or per-fix approval is needed. Do not change production code, hypothesis, pinned surfaces, statistics, archives, schema implementations, legal-write rules or scientific thresholds; N/B*/prediction/sessions and A8 remain unresolved and 2c is not frozen.

Verification is proportionate: recheck changed cross-references/contract consistency, and the two document pin modules if their referenced documents change. Rerun the two read-only scripts only if their logic/data references change. No mutant battery, full regression, model experiment, new seed derivation or board run is required. Submit the completed document correction unit once for review. Push/merge and new execution units remain outside this authorization.

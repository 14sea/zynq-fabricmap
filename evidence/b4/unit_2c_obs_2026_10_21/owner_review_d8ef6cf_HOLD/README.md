# Owner review of d8ef6cf — HOLD, remaining 2c-obs contract inconsistencies

2026-10-21. Exact reviewed tip `d8ef6cf5b91f24a928e642a45a13a2743138c48b`, parent e91650b, branch b4-2c-obs, clean tree. The author has addressed the intended direction of R1–R3, including source-context binding, the physical/model scoring boundary, cleanup as an explicit phase, a same-element A8 cross and bounded attribution. **Four remaining inconsistencies prevent acceptance of the document as an implementable/decidable contract.** They require document corrections, not another experiment or a larger evidence battery.

## 1. Checks that pass

- Independently reran the two document-pin modules: **29 tests OK**, no skip. These tests use fake anchors/literal masters where they test derivation; no production set was derived.
- b4/, hypothesis/domain, statistics, B1/B2/B3 pinned surfaces, certificates, production archives and no-go decisions remain unchanged.
- Prior e91650b owner review copied byte-for-byte, checksum entries verified; authorization text/source note copied correctly. No further authorization-original work is needed.
- The two read-only selection scripts and their outputs are unchanged since the prior independent rerun; no repeat was needed. The nine-pair arithmetic and data-informed draft status remain accepted.
- Static probes below use a retained trace's unchanged configuration/header fields and small synthetic Boolean records. They do not call a model, fabric, seed generator, carrier, simulator or production verifier. Full tests, mutants and new observations were not run.

## 2. C1 — P1, residual R1: common payload still does not describe the legacy format

References: contract 3.1–3.2 (lines 123–155), 4.3–4.4 (lines 249–278); b4_ff_model.py observe()'s return and config hash construction.

Three concrete mismatches remain:

1. The proposed payload says config is a **list of 21 ints**. The legacy trace actually has an **address-to-bit dictionary**. A raw legacy record cannot already be a direct instance/subset of that typed payload as claimed.
2. The legacy trace has **no stimulus_sha256 field**. Its config_sha256 is SHA256(json.dumps(config, sort_keys=True)) with the existing dictionary and default separators, not the proposed canonical-list digest. The retained header inspected by static_contract_probes.py matches the former exactly; the canonical dictionary and canonical vector hashes differ. This is provenance/hash behavior, not a wording-only rename.
3. Section 4.3 now searches both branches' string values for the deny-list, including **truth**. The formal model's legitimate fabric.kind is exactly **truth**. The new generic value rule would reject that legitimate source while claiming to preserve it. Existing allowed metadata must not be confused with leaked reference answers.

Resolve these without changing b4/ or archived bytes. Define a **logical/canonical view** separately from each source's raw wire format, or adopt a common format that actually matches legacy data. Give the field/type/encoding/digest mapping explicitly. A reader may compute a derived stimulus digest or vector view from retained fields, but label it derived, bind it to the raw source digest, and do not claim it was a field the model wrote. Do not overwrite/reinterpret a legacy digest under a new encoding.

Make the defence-in-depth rule field-aware: approved source identity enum values such as model fabric.kind=truth are legitimate. Keep exact field sets, source-context binding and noninterference guards; do not blanket-reject every occurrence of an allowed identity string. A provisional schema can reference the common logical view through a defined adapter; it cannot both require absent fields and promise that the unadapted legacy trace is already that payload.

D1's actual 0/1 sampling rule, source binding and the named scoring-domain limitation are accepted in direction. They are not the reason for this HOLD; the issue is the remaining incompatible type/hash/validation specification.

## 3. C2 — P1, residual R2: sealing and transaction witnesses are not causally ordered

References: exact carrier field set 4.2; P6–P10 in 5.1; predecessor and opening baseline in 5.5; faulted-prefix statement in 5.6.

Section 4.1 makes the observation include the carrier's transaction witnesses, and the closed observation field set requires cleanup and idle_status. P6 nevertheless says the observation is durable before fitness; cleanup only exists at P7 and idle_status at P10. A complete immutable record at P6 cannot contain future values. The document does not define an earlier immutable payload plus a later envelope/close record, nor which digest the fitness binds if the same record is later extended.

The current transaction's P8 base readback and P9 base-state sample are said to be recorded, but have no declared location in the exact current observation fields. predecessor holds the PREVIOUS transaction's values, not the current transaction's restore witness. Moving values into the next predecessor would also leave the last transaction and interruption windows without their own evidence. The opening baseline is itself called a carrier record requiring a predecessor, without defining a terminating session-root case.

Choose and document one coherent persistence/binding scheme. For example, an immutable observation payload at P6, its fitness record, and a later transaction-close witness can bind the cleanup, current base readback, current P9 sample and idle status. A final envelope referring to separately immutable payloads is another possibility. These are examples, not mandatory names/counts. State when each object exists and becomes immutable, what its digest covers, how the current restore witness is retained before another candidate is permitted, the baseline/root case, and how interrupted/faulted prefixes are retained as non-success records. Do not mutate an already hashed observation silently or manufacture future witness values.

Keep the raw-observation-before-fitness discipline and the trusted source boundary. This is a document-level phase/record dependency repair; no carrier/schema implementation is authorized now.

## 4. C3 — P1, residual R2: A5's comparison cannot pass the required successful injection

References: initial.q alias in 3.3 (lines 159–160), normal sign/restore/idle requirements in 5.2/5.4, A5 5.6 (lines 347–366), mechanism (c) pre-init sample description in 6.3.

A5 requires the second initial.q to DIFFER, to show the injection arrived. Section 3.3 makes steps[0].q_before exactly that initial.q. Section 5.6 compares steps[] in EVERY field, so it also requires those two q_before copies to be EQUAL. Excluding only the top-level initial.q does not exclude its nested copy.

The static counterexample has before=[0]*8 versus [1]*8, a perfect reset giving q_after=[0]*8 in both, and equal cleanup.final_q. The intended post-init property holds but the written projection rejects it. Specify the post-init comparison projection precisely (including the init-step q_before exception or a separate representation of pre-init state); preserve the injection sample as an independently checked witness.

A second integration problem remains: c-prime deliberately omits P7–P9 and holds nonzero inputs/clock high, whereas the normal path refuses signing c without prior restoration/idle and starts step 0 with clock/SR low. Define an explicit **qualification-only injection protocol** and how it reaches and witnesses c's pre-init boundary, or place a specified injection within an otherwise authorized transaction. Do not silently disable normal signing, nonce, writability or source checks. State the control/clock changes and any configuration write between injection and sampling; for configuration-as-init, do not substitute a cached base-state reference for an actual injection witness. The special test's expected incomplete cleanup must have a record type/status distinct from a normal completed mapping observation.

A5 is not demonstrated merely by proving the normal gate refuses an unrestored predecessor. It must distinguish a witness that injection failed to arrive (not demonstrated) from a witness that it arrived and was cleared (pass) and from persistence after initialization (fail). No new board/test run is requested by this document review.

## 5. C4 — P1, residual R3: common A8 stimulus and the SRVAL-opposite requirement conflict

References: same-stimulus factorial requirement 6.4, SR condition 6.5 (lines 444–447), outcome rows 6.7 (lines 470–474).

For a single fixed evidence-edge D, being opposite to predicted SRVAL=0 requires D=1; being opposite to predicted SRVAL=1 requires D=0. The four corners deliberately contain BOTH SRVAL values. There is no common D satisfying section 6.5 for all corners. Varying D with the candidate's predicted SRVAL would violate the controlled same-stimulus requirement and confound the cross.

Retain one predeclared stimulus for every corner and give a feasible, jointly interpretable anti-capture witness. A single fixed D may be sufficient when the paired SRVAL responses are judged together, or a fixed sequence can contain both D values/restore episodes for EVERY corner. Either is a design option; this review does not impose extra episodes. Define why the chosen joint evidence separates an SR restore from ordinary data capture without candidate-dependent stimulus adaptation. Continue to require a compatible physical capture opportunity for either sr_kind. Qualification vector/timing implementation stays with its later unit; the present contract must have satisfiable conditions.

The outcome table also needs non-overlapping classification or explicit precedence. “SRVAL effect only” and “INIT effect only” each satisfy the last row's “a main effect is absent where the other is present,” producing both an unknown/reduced-claim row and a failed/unresolved row. Decide the classification once. Missing main effects alone and actual cross-tracking need not be conflated; retain the no-automatic-attribution/no-automatic-revision rule and demonstrated-context limits. A small manual four-state decision table is sufficient verification; no new model observation is required.

## 6. Accepted direction and minor wording

The scoring-domain counterexample and four rules, trusted source selection, removal of hypothesis/mapping references from carrier output, separation of frames from Q state, cleanup as an explicit unscored phase, G6 limitations, same-element factorial design, bounded context claims and qualification-only/data-informed selection revision all address the previous review's intent. Preserve them while removing the contradictions above.

D4 remains accepted as a data-informed DRAFT A2 proposal/revision, not a certified/whitelisted/board-demonstrated choice and not an alteration of the existing K9 panel or no-go. Its numerical scripts need no further rerun if unchanged. No hypothesis or threshold change is requested.

P3 to fold in: the specific task-v0.2 search/holdout stimuli start at clock 0, have an even 6/8 alternating-edge count, and finish with same-level steps, so their final clock is 0. A general allowed stimulus may end high; cleanup may support that general case. Do not describe final clock=1 as an outcome of the current fixed task shape. This wording does not affect the need to clear possibly nonzero SR/CE/D.

## 7. Finish the same document correction unit

Continue within the existing authorization. Resolve C1–C4 together and submit once; no scope proposal or per-fix approval. You may simplify this long draft into field/encoding, phase/record readiness, A5 and A8 decision tables rather than add more narrative. The objective is an internally consistent contract with its legitimate unresolved implementation questions named.

No production code, model, domain, hypothesis, new schema implementation, statistical method, legal-write rule, pinned surface or archive changes. No new seeds, model/board observations, benchmark, full proof, RTL, push or merge. Validate changed document pins and a few static/manual examples corresponding to the issues; do not add a full regression, mutant battery or fixture-archive duplication for this document repair. The existing authorization/source archive already passes; do not reopen it.

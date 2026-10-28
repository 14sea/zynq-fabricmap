# Owner review — PS-image repair round 3 — d4ff43e — HOLD

Reviewed tip **d4ff43e6** (full identities in review_metadata.json), repair e32e0d1. All independent execution used the detached disposable clone /tmp/owner_b4q_r3_gskm2dvv. No canonical tracked edit, board connection/power, image loading, physical PCAP, production seed derivation/run, push or merge.

## 1. Disposition and accepted repairs

**HOLD for the two remaining integrated paths R1–R2 below.** Accept the demonstrated C1 source anchoring, C3 message shape/type checks, C2 bindings against the previous six counterexamples, and C4 suppression of sequence reuse. R1 is the remaining C2 successful-handshake requirement; R2 is C4 terminal quiescence across an active transaction. Earlier accepted repairs remain accepted.

Independent checks:

- Eleven unittest modules: **99 tests OK, no skip**, carrier benches first. Retained unclosed-pipe ResourceWarnings are not failures.
- Two clean builds produce raw .bin SHA256 **ee7076a03d602ad1025fb698d213f98a111449d623012a29c3147e0d7e867770**, identical to the submitted image. Compiler/runtime inputs, sources, 49 translation-unit and 90 header hashes match after checkout-path normalisation. P3's raw-bin-only reproducibility wording is correct. ELF entry 0x020000cc and the vector-table load address 0x02000000 remain distinct, checked facts.
- **18 submitted and 18 independently regenerated** console cases fresh-verify in agreement; recorded failure cases retain their findings. A7 has no findings; final cortex-a9 xcheck passes.
- All **14 previous archive negatives** now exit 1 by named refusal/finding, no verifier_error; the untouched control remains clean. This includes the coordinated source removal, altered/missing TX, wrong/out-of-order reply, reply-plus-notary-word tamper, identity nonce/echo and malformed JSON/type cases.
- The prior actual-app duplicate and after-stop fixtures reject with zero new signature/trace events; halted notary returns REFUSED. The old near-limit C fixture now emits just SIGNREQ then END, two frames, zero wrap. This validates the no-wrap repair, not the remaining post-END effect condition.
- b4/IMPORT.json 59/59 pinned digests match. Firmware IMPORT hashed entries all match; b4q_tx.c and protected paths remain unchanged from e267405. From main dd8a7b9, only the previously authorised carrier manifest correction remains in the protected paths.
- The previous owner review's 131 payload checksums match. e32e0d1..d4ff43e has no firmware/host/tests/b4 source change.

The submitted mutant result is **36 killed / 1 named masked survivor / 0 edit-miss of 37**. R4a's masking by C1a and the killed combination are a reasonable account; do not relabel the single survivor as independently killed or equivalent. This review inspected that record but did not rerun the full mutant battery: the independent regression, old counterexamples and new integrated probes determine this HOLD. No 332-test battery or broad fuzz campaign ran. The existing ignored netlist fixture was copied/hash-checked, not resynthesised.

## 2. R1 — P1 — a successful transaction does not require any accepted SIGNREPLY

**Code:** host/b4q_verify.py:649 onward, especially its RESULT handling: staging is checked only for q['answered'] with ok=true, and a successful RESULT merely requires cur['reqs'] to be nonempty. Unanswered requests never have to become an accepted reply before successful completion.

**Independent fresh-process reproductions** in exchange_probes.py/json:

| case | change to submitted valid console archive | result |
|---|---|---|
| untouched | none | clean=true, agree=true, exit 0 |
| all_replies_removed | remove every host SIGNREPLY, refresh console_lines | clean=true, agree=true, exit 0 |
| all_replies_removed_counters | same removal; also set cached stats.signreply and both raw/cached END.sign_replies to 0 | clean=true, agree=true, exit 0 |
| first_reply_removed / last_reply_removed | remove one successful reply, refresh console_lines | both clean=true, agree=true, exit 0 |
| reply_noted_stale | annotate the actual matching first reply as stale; refresh the stale stat | clean=true, agree=true, exit 0 |
| signreq_only_unanswered | annotate all actual replies as stale; refresh the stale stat | clean=true, agree=true, exit 0 |

All retained successful RESULTs, actual staging writes and notary logs remain unchanged. This is missing/inconsistent console evidence of the same successful calls; no assertion is made that the actual historical signature did not occur. The complete/clean console contract cannot be established without retaining the accepted exchange.

The notes example also confirms that an annotation is still authority to skip decoding. A reply carrying the current request id is not made stale merely by labelling it so.

**Repair contract:** before a successful RESULT can close an admitted transaction, require every signing call actually needed by that transaction to have exactly the accepted response required by the executing code. Track unanswered/OK/refused/ignored states explicitly; only a matching, causally valid OK response can establish a successful signing call and trigger the notary/staging-word comparisons. Derive relevant reply counts from accepted exchanges. Keep genuinely dropped, corrupt, stale and refused paths valid as named failures/prefixes; do not require an OK response for a STOP_SIGN failure. Validate noted-line classifications from the bytes and active protocol state rather than trusting their note or cached stats. The listed coordinated negatives must be not clean, not merely a cached-summary mismatch caught before this guard.

### Source clarification (P3, not another HOLD item)

My earlier candidate/restore signing wording was imprecise. The accepted b4q_tx.c has **one b4q_sign call site**, in candidate_in (line 287), called once per transaction apart from that function's own retry exchange. P8 restores the base through the existing stream path and does not make a second signing call. Bind against those actual call sites and the retained phase evidence; **do not add a new restore signature to satisfy the verifier**. This corrects the review wording, not the accepted transaction core or protocol.

## 3. R2 — P2 — terminal END suppresses output but the active transaction keeps executing effects

**Code:** firmware/b4q/target/b4q_app.c:44–65 sets S.terminal and returns from emit_raw. b4q_emit is a void event callback. b4q_transaction continues after that callback and is checked for S.terminal only after the entire call returns in the app loop. The host and board MMIO HALs do not enforce this terminal latch.

**Independent integrated reproduction:** terminal_app_fixture.c includes the original app unchanged and uses a linker wrapper around b4q_emit solely to inject the sequence limit immediately before its original `EV P4` event. The actual unchanged b4q_tx.c, native app HAL and emulated backend then execute normally. No transaction/signing/peripheral implementation is replaced. The baseline completes status 0. In the injected root transaction:

- The app emits **END PROTOCOL**, reason `this side's line sequence is exhausted`; host receives status 6.
- Without sending another TX or signature, the fixture continues answering **only the emulated MMIO HAL**, so operations that a real HAL performs synchronously can be observed.
- After END: **16 backend trace events, including 4 register writes**, plus **26 emulated DMA submissions**, including **2 envelope writes**. The writes include CLEANUP, RESTORE_INIT and CLOSE; no later RESULT is emitted.

The 54 subsequent PCAP-log entries include those submissions and their completion/read/frame records; they are not 54 DMA transfers. Exact raw trace/console/PCAP material is retained as sequence_cut_*.jsonl. The observer drain ends with the expected closed-console exception when the app exits. This is host-only mechanism evidence, not a claim about a powered device or physical DMA timing.

The absence of later UART output does not establish quiescence of the transaction that was already running. The earlier direct b4q_sign boundary test did not exercise that path.

**Repair contract:** the terminal condition must stop further peripheral writes/new DMA issuance in the active transaction, as well as command, wait, signing and output loops. Enforce it at an actual effect boundary or terminate/unwind the call safely; a caller check after the transaction completes is insufficient. Keep the accepted per-call core contract intact and preserve the acquired prefix. Do not silently perform recovery/cleanup after the terminal END; any required recorded shutdown belongs before that terminal statement. This is about newly issued effects, not cancelling previously issued physical transfers.

Add a full console-path regression of terminal exhaustion inside an active transaction, not just a line-counter twin. Retain an honest named terminal/non-success prefix, no fabricated RESULT/O/F/X, and fresh verification in agreement with that outcome. Test both the terminal emitted during a wait and at an event callback. No board run or billions of output lines are required.

## 4. Same-unit repair authority

Authorise R1–R2 together in the existing PS-image preparation unit: necessary app/HAL/console verifier/producer/tests, narrow docs, IMPORT and rebuilt-image evidence. Retain accepted C1/C3, the proven no-wrap behaviour and all previous repairs. Keep the accepted b4q_tx.c and per-call semantics unchanged where possible. Carrier RTL/regmap/bitstream, model/hypothesis/task, scientific methods/thresholds, production labels/receipt and historical archives remain unchanged.

Use host mechanics/injected fixtures. Add targeted regressions and affected mutants; require the tests to observe the intended guard. Re-run the final 99-test regression, existing console scenarios and the new handshake/active-terminal cases with fresh verification; rebuild/pin the image when its sources change. No unchanged 332-test or unrelated full mutant battery is required. Preserve prior evidence in history. Complete the unit and submit once; no date gate, fixed commit count or per-edit approval.

No board connection/power/provisioning, image loading, physical PCAP, production seed/run, new exploration/gate, push or merge is authorised. This remains host engineering review, not B4Q qualification or silicon evidence.

## 5. Evidence

- snapshot.json, identity_checks.py/json, build_evidence.json/txt, tests.txt, xcheck.txt, a7.txt: independent scope/build/regression checks.
- prior_archive_probes.py, archive_probes.json, verify_*.json/txt: all previous negative cases now rejected.
- exchange_probes.py/json/txt, exchange_*.json/txt: missing/relabelled reply cases with clean control.
- terminal_app_fixture.c, terminal_app_probe.py/json/stderr, baseline_*.jsonl and sequence_cut_*.jsonl: actual-app/actual-core terminal test, its control and retained raw observations.
- prior_wrap_probe.c/txt, prior_console_probes.py/json/stderr, host_callback_probe.py/json: accepted mechanism repairs independently rechecked.
- e2e.txt, verify_cases.py/json/txt and verify_submitted_*/verify_regenerated_*: 36 fresh checks.
- previous_review_integrity.json, REPRODUCE.md, review_metadata.json, SHA256SUMS: provenance, commands, integrity and scope.

Findings are limited to these concrete contracts and fixtures; no universal proof or new scientific conclusion is supplied.

# Owner review — PS-image repair — 0606758 — HOLD

Reviewed tip **0606758275f5828cd3594c3b689866e6a1060ce6**, code/import baseline c96edce (repair 1a215e3). Independent source inspection, image builds, original-C fixtures and fresh-process archive verification ran in a detached disposable clone at /tmp/owner_b4q_repair_i_m6wlns. The actual review time is recorded in review_metadata.json.

## 1. Disposition and accepted progress

**HOLD for C1–C4 below, repaired together in the same PS-image unit.** C1–C3 are remaining portions of the prior R4 console-evidence contract; C4 is the prior R2 sequence-exhaustion requirement. Accept the demonstrated R1 cumulative budget, R2 duplicate/decreasing-frame rejection, R3 session admission/notary latch, R5 checked command grammar and P3 reproducibility clarification. No reversal of the accepted transaction core or earlier scientific/engineering units.

Independent results:

- Eleven unittest modules: **95 tests OK**, no skip. The accepted carrier benches ran first. The retained ResourceWarning concerns unclosed Python pipe objects, not a test failure.
- Two clean image builds: raw .bin byte-identical and equal to the submitted image, SHA256 **f50930a19981c13e16351582a2fc353cab7fdcc2bd3bba2f205e565452ea8c63**. Source, compiler, runtime-object and 49 translation-unit / 90 header hashes match after checkout-path normalisation. The ELF entry remains 0x020000cc. The raw vector-table load address is 0x02000000; these are distinct facts. The P3 wording now correctly limits the reproducibility boolean to raw .bin bytes.
- All **18 submitted + 18 independently regenerated** console cases fresh-verify with exit 0 and agree=true. Negative cases retain their recorded findings; agreement is not qualification.
- The prior independent C wait fixture now ends at **30,000 polls, three attempts** for silent, stale-flood and overlong-line cases (10,000 per attempt). The prior six malformed commands all return -1.
- The prior duplicate-TX and after-stop fixtures now return status 7, with **zero new SIGNREQ and zero new backend trace events**. The actual host receiver accepts one HB from sequences 7,7,6 and refuses the other two. A direct halted-notary callback returns REFUSED and logs a refusal, with zero new backend events.
- Final cortex-a9 xcheck passes. A7 on the independently regenerated valid console case has no findings.
- b4/IMPORT.json 59/59 digests match. firmware/b4q/IMPORT.json has 35 entries, 34 hashed entries all matching. b4q_tx.c is unchanged from e267405; protected paths are unchanged from that closure. From main dd8a7b9, the sole protected-path difference remains the previously authorised carrier manifest correction.
- The previous owner review was archived with all **97 checksums matching**. c96edce..0606758 has no firmware/host/tests/b4 code change.

The submitted 27-mutant log states ten green baselines and 27/27 killed. It is an author record, not a mutant battery independently rerun in this review. Independent tests, fixtures and the concrete negatives below suffice for this HOLD; no unchanged full battery or broad fuzz campaign was added. The existing ignored netlist fixture was copied unchanged and hashed (snapshot.json), not resynthesised.

## 2. C1 — P1 — console source selection can still be downgraded

**Code:** host/b4q_verify.py:213–216. The console contract is selected only when manifest.transport or console.jsonl exists.

**Reproduction:** from the submitted valid console archive, delete **both** manifest.transport and console.jsonl; change nothing else. In particular the apphost executing-side identity and the retained opening/transactions remain. Fresh verifier returns **exit 0, clean=true, agree=true**. Deleting only the log is now correctly REFUSED: that is the positive control proving the new guard exists but its source selection is optional.

See archive_probes.json cases source_downgrade and missing_console_control; exact edits are in archive_probes.py.

**Required repair:** determine the expected source from an anchored identity or explicit trusted caller context, rather than solely from optional material being tested. A declared/expected console archive must not fall through to legacy verification when its console markers are removed. Preserve actual legacy host-only archives under their own source contract. This is internal source binding, not a demand for cryptographic authenticity or a universal version selector. Add the coordinated removal negative, not merely another single-file-missing check.

## 3. C2 — P1 — messages are counted/classified without binding the transaction exchange

**Code:** host/b4q_verify.py:517–735, especially host-line classification, the notary exchange at 632–685, and IDENT at 589–620. No binding is made between TX payload and the retained transaction; replies are looked up by request frame sequence without requiring a corresponding active request or causal position.

Each of these independent copies still returns **exit 0, clean=true, agree=true**:

| case | changed material | untouched evidence that now contradicts it |
|---|---|---|
| tx_genome_changed | change the first normal TX genome from 0 to 1; regenerate CRC | retained ctx/O/config, actual trace and transaction result remain genome 0 |
| tx_all_removed | remove all four TX frames, refresh transport.console_lines | four performed transactions, their results and raw traces remain |
| reply_req_changed | change the first successful SIGNREPLY req id to 999999; regenerate CRC | its actual request id and the successfully executed transaction remain |
| reply_before_request | move that SIGNREPLY before its SIGNREQ, preserving each direction's sequence order and every frame's bytes | the purported reply precedes the request it answers |
| reply_notary_words_changed | change the first signed word in both the console reply and cached notary.words | raw MMIO staging writes and the notary's other payload/tag facts remain unchanged |
| ident_nonce_echo_changed | change raw IDENT.nonce_echo_equal to 0 and page_nonce_seen to ffffffffffffffff; refresh CRC and cached transport IDENT | the page, retained opening nonce and successful session remain unchanged |

The row for notary words is not a demand to authenticate the archive. It is an inconsistency between two retained representations of the very same staged signature. Copying the bad value to its new notary-log field makes the present comparison pass.

**Required repair:** validate an ordered protocol exchange, with explicit state linking each admitted TX to the retained kind/configuration/declared steps/task, each SIGNREQ to that transaction's candidate or restore phase and nonce, and each accepted reply to its request id, phase and causal order. Account for retries, drops, refused/ignored commands and A5; do not assume contiguous frame sequences. A performed RESULT cannot exist without the corresponding admitted TX. Bind the issued words to the actual retained staging writes as well as their notary record. Derive IDENT's page/nonce/echo/watchdog claims against the page and opening rather than accepting unchecked cached fields. Keep the existing legitimate negative and interrupted prefixes.

Explanatory notes such as corrupted/replayed are annotations, not authority to skip a frame's actual protocol condition. Validate what the raw evidence permits; do not require unobservable UART or hardware facts. No new board observation or scientific estimator is authorised by this repair.

## 4. C3 — P2 — payload shape is not checked before accepting or indexing it

**Code:** host/b4q_verify.py:603–620 and 703–727 only validate IDENT/END if the parsed payload happens to be a dict; SIGNREQ at 650–666 and repeated RESULT parsing at 687 index data without an accepted shape.

Focused examples with valid outer framing/CRC:

| case | result |
|---|---|
| raw IDENT payload replaced by [] | exit 0, clean=true; all identity checks skipped |
| raw END payload replaced by [] | exit 0, clean=true; all END checks skipped |
| END.transactions changed to 4.0 in both line and cached END | exit 0, clean=true; integer type not held |
| SIGNREQ payload [] | exit 2, VERIFIER ERROR: AttributeError |
| SIGNREQ.req changed to an object | exit 2, VERIFIER ERROR: unhashable dict |
| RESULT payload changed to {broken | exit 2, VERIFIER ERROR: JSONDecodeError from a second parse, after an earlier parse already found the malformed JSON |

**Required repair:** decode once and check the minimal per-message shapes/types before field access, grouping, formatting or arithmetic. Non-object IDENT/END must produce a named refusal/finding, never bypass their contracts. Reject the malformed SIGNREQ/RESULT as bad evidence (exit 1 / named finding), reserving exit 2 for a verifier defect. Fields representing integer counters/ids must retain their exact type. Respect legitimate phase-dependent absence. Only the actual protocol message contracts and listed boundary cases are required; no arbitrary-JSON fuzz campaign or general parser framework.

## 5. C4 — P2 — sequence exhaustion is checked only between waits

**Code:** firmware/b4q/target/b4q_app.c:41–50 emits and increments without a limit; the limit test is only at line 268 before wait_command. A transaction/sign wait can emit more than the reserved 16 lines.

**Independent original-C fixture:** wrap_probe.c includes the application unchanged. It injects a boundary state with sequence/line/kick counts at **SEQ_LIMIT−1 = 0xffffffef**, still allowed by the current gate, and runs a silent SIGNREQ wait. It scales REPLY_POLLS/HB_EVERY to 10,000/1,000, preserving the production ratio of ten heartbeats per attempt. The result is:

```
ret=-1 initial_allowed_seq=0xffffffef first=0xffffffef last=0x00000010 frames=34 wraps=1 polls=30000 requests=3 final_end=0
```

This is a state-injected boundary fixture, not a claim that a real session has emitted billions of lines. It proves the advertised no-wrap invariant is not enforced during a wait. The peer freshness check is useful but does not make this producer invariant true.

**Required repair:** enforce exhaustion wherever outgoing messages can be emitted, with a finite named terminal outcome before sequence reuse. Preserve the raw prefix and avoid recursive END emission or further transaction effects after that terminal condition. A check only at the next command boundary, or a fixed small reserve without a bound covering the whole intervening operation, is insufficient. Keep normal gaps/freshness, budgets and the session latch unchanged. A focused near-limit C fixture is sufficient; do not run billions of lines or a physical test.

## 6. Same-unit repair scope and acceptance

Authorise C1–C4 together in the existing PS-image unit, with the necessary app/console verifier/producer/tests, narrow documentation and IMPORT/build-evidence updates. Retain the already accepted repairs. Keep the accepted b4q_tx.c and per-call invariant unchanged where possible; carrier RTL/regmap/bitstream, model/hypothesis/task, scientific protocol/statistics/thresholds, labels/receipt and all production archives remain unchanged.

Use mechanics/host fixtures. Add direct regressions for these cases and affected mutants; tests must reach the intended guard. Re-run the relevant 95-test regression on the final code, the 18 console scenarios with fresh verification, the new coordinated negatives, and pin the rebuilt image if its code changes. No unchanged 332-test battery or full unrelated mutant battery is required. Preserve prior raw evidence in history. Complete the whole repair and resubmit once, with no per-edit approval, date gate or mandated commit count.

This is **not** authority for board connection/power/provisioning, image loading, physical PCAP, production seeds/runs, new exploration/gate, push or merge. P2 and the remaining physical B4Q prerequisites remain unmet; this review supplies no silicon witness.

## 7. Evidence inventory

- snapshot.json: detached clone and pre-existing netlist dependency hash.
- identity_checks.py/json, build_evidence.json/txt, tests.txt, xcheck.txt, a7.txt: independently rerun source/build/regression checks.
- e2e.txt, verify_cases.py/json/txt and verify_submitted_*/verify_regenerated_*: 36 fresh-process archive checks.
- prior_wait_probe.c, prior_parser_probe.c, prior_c_probes.json, prior_console_probes.py/json/stderr, host_callback_probe.py/json: accepted repairs independently retested with the original owner fixtures and halted-notary check.
- archive_probes.py/json/txt and verify_* payload reports: baseline, correctly refused missing-log control, ten wrongly clean contradictory archives and three wrongly classified malformed archives.
- wrap_probe.c/txt: sequence-exhaustion counterexample.
- REPRODUCE.md, review_metadata.json and SHA256SUMS: commands, run scope, outcome and integrity.

All findings are scoped to the concrete host-only contracts above. This is not a general totality proof, legal composition certificate, device timing measurement or B4Q qualification.

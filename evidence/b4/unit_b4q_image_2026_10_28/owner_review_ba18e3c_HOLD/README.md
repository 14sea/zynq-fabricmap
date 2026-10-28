# Owner review — B4Q PS-image preparation — ba18e3c — HOLD

Reviewed implementation c4f9613ee97746855d4ef6df4b262f928dec9da5 and evidence tip ba18e3ca8c7260450a40daa2d7651cbc19c1f707. This is an independent source review and host-only execution in a detached disposable clone. No board, physical PCAP, image loading, production seed derivation, canonical tracked edit, commit, push or merge occurred. The review directory name follows the unit's date; the actual review timestamp is in review_metadata.json.

## 1. Disposition

**HOLD this PS-image preparation unit for R1–R5 below.** The image builds and the submitted test numbers are reproducible. The new console boundary has independent failures in bounded receiving, freshness, stop admission, archive verification and command decoding. These are host-reproducible engineering defects; they do not require a board to resolve. This HOLD does not reverse the accepted transaction core, carrier, model or historical scientific dispositions.

## 2. Independent checks that passed

- The canonical tree was and remains clean at ba18e3c; main remains dd8a7b9. All executions used /tmp/owner_b4q_image_2skt9o2b, detached at ba18e3c.
- The accepted b4q_tx.c is byte-identical to e267405. The protected paths in identity_checks.py have zero change since e267405; relative to main, only the already authorised carrier manifest correction appears.
- Frozen b4/IMPORT.json: 59/59 digests match. firmware/b4q/IMPORT.json: all 33 hashed entries match (34 entries including the table itself).
- Eleven unittest modules: **Ran 90 tests, OK, no skip**. Carrier benches ran first. Native host/app/wire/derive builds succeeded. A ResourceWarning for unclosed Python pipe file objects is retained in tests.txt; it is not a test failure.
- Two clean image builds independently produced the same raw .bin, sha256 **048f9ab9499db86496128c1893497ef0f7127332528c0437b014e136c292fb1b**, equal to the submitted raw image. All 49 translation-unit hashes and 90 header hashes, runtime inputs and compiler digest match after normalising checkout paths. B1 linker/include/console copies are byte-identical. ELF entry is 0x020000cc; program headers and selected symbols match. Loading the raw image at the vector-table address 0x02000000 is distinct from the ELF entry; this is already exercised by the image test.
- Focused mutant battery independently rerun: **11 killed / 0 survived / 0 edit-miss**, five green baselines; the two missing-bound mutants each reached the original script's 240-second timeout. This does not cover R1's stale-frame/oversize paths. The detached clone's sources were restored and its tracked tree is clean. Final cortex-a9 pure-unit xcheck passed after restoration.
- All 14 submitted console archives and 14 independently regenerated cases: fresh-process verifier exit 0, agree=true, no verifier exception. The intended transaction/opening failure cases remain clean=false; exit 0 is agreement with their recorded findings, not a successful qualification. Silent-host termination can be a consistent archive without any successful qualification.
- The pre-existing netlist fixture required by the benches was copied from canonical builds/b4/b4_core_funcsim.v to the clone and hashed in snapshot.json. This review did not rerun Vivado synthesis and does not claim a new netlist or physical witness.

Raw logs and independently written probes are included. Passing checks above do not cover the failures below.

## 3. R1 — P1 — the receive budget is replenished rather than consumed

**Code:** firmware/b4q/target/b4q_app.c:73, 82–100, 113–144.

b4q_sign repeatedly passes the unchanged full polls to recv_frame after a stale SIGNREPLY or another valid frame. recv_frame likewise hands the full budget back to read_line after a bad line. The oversize-line drain at line 73 has no poll bound at all. Consequently the documented per-attempt console-poll budget is not an upper bound.

**Independent reproduction:** wait_probe.c includes the original application source unchanged and links the original pure units. Only the console/platform/MMIO fixtures and compile-time poll constant are injected. With REPLY_POLLS=10,000, a silent peer returns -1 after 30,000 polls and three requests. With valid CRC/token, strictly increasing frame sequences and a wrong request id, the application is still in attempt 1 at poll 100,001 (the 1,425th stale frame has begun). A continuous overlong line also reaches poll 100,001 in attempt 1. The fixture then exits 77 to stop the probe; that is the review fixture's cap, not the application enforcing a bound. See c_probes.json.

**Repair contract:** one cumulative receive budget per declared idle wait or SIGNREQ attempt, spent by every UART readiness poll, including malformed/ignored/stale frames and oversize discard. Preserve bounded re-requests, named refusal/end and retained evidence. State exactly how flush/discard work is accounted for or separately bounded. Heartbeats, NACKs and watchdog kicks must not replenish that budget. The watchdog remains a fallback; no measured timeout or physical hang is inferred by this probe.

## 4. R2 — P1 — a duplicate TX executes again

**Code:** b4q_app.c:100 (assignment without a check); host/b4q_console_session.py:210–225 (parses without checking incoming sequence freshness). docs/b4q_image.md section 2 declares each direction strictly increasing.

**Independent reproduction:** console_probes.py uses the compiled, unmodified b4q_apphost. After a complete normal transaction it re-sends the exact previous TX frame, token, sequence and payload. The second transaction succeeds with X closed and no findings, adds one SIGNREQ and 155 backend trace events. The replayed host sequence is 3. New notary replies use fresh increasing sequences, so there is no need to replay an old valid signature. See console_probes.json, duplicate. The actual host receiver also accepts HB sequences 7, 7, 6 without refusal; all three increment its received heartbeat count.

**Repair contract:** enforce per-direction freshness at the stateful receiving boundaries, before any command/notary side effect. Define initial sequence and exhaustion handling explicitly; reject duplicate/decreasing values by name. Do not force contiguity: a dropped frame may leave a gap. Keep request-id binding in addition to sequence freshness. Test duplicate/decreasing TX and board-side frames, legitimate gaps and the existing dropped/stale-reply cases. The pure CRC parser need not own session state.

## 5. R3 — P1 — the framing boundary can sign after a session stop

**Code:** b4q_app.c:204–210 unconditionally continues after a failed transaction; host/b4q_console_session.py:120–132 answers SIGNREQ without checking the session halt latch.

The accepted per-call core invariant is intact: b4q_tx.c stops writes/signing within a failed call. The new session loop starts another call, which resets that call's stop state. The high-level Python transaction API refuses after self.halted, but that guard is absent from the console app and the callback that actually invokes the notary.

**Independent reproduction:** a notary refusal yields STOP_SIGN and the ordinary high-level next transaction is correctly refused. Injecting the next valid TX at the console boundary, while the host remains halted, causes a new signature and 155 backend trace events; the raw transaction returns status 0. The probe deliberately bypasses the high-level API to exercise the newly exposed framing boundary; it does not allege that the normal API itself bypasses its latch. See console_probes.json, after_stop.

**Required policy remains docs/b4q_plan.md section 4.2:** a host-side failure that cannot be sealed latches the stop; nothing further is signed until a ruling.

**Repair contract:** enforce session admission at the actual app and signing boundaries, preserving the first failure and RESULT/raw prefix before termination or named refusal. A halted/refused/unclosed session must not sign another request. Preserve the explicitly authorised A5 injection_open transition; do not turn a valid A5 handoff into a generic failure. Do not change the accepted per-call transaction rule to disguise a missing session rule. Test the failed call followed by an injected/queued valid TX and unsolicited SIGNREQ, including the host shutdown path, with zero further signature/transaction activity after the first failure. This is not a demand that the accepted per-call core own persistent session state; the new app/session boundary must own it.

## 6. R4 — P1 — fresh verification ignores the new console evidence

**Code:** host/b4q_console_session.py:300–306 writes console.jsonl and manifest.transport. host/b4q_verify.py does not read either as evidence to verify.

**Independent reproduction:** archive_probes.py makes copies of the submitted valid console archive. Baseline is clean. Each of the following independently remains exit 0, agree=true, clean=true:

1. Delete console.jsonl entirely.
2. Corrupt IDENT's CRC.
3. Change RESULT.fitness to 999, regenerating its CRC.
4. Change IDENT's payload token, regenerating its CRC.
5. Change END.transactions to 999, regenerating its CRC.
6. Change cached manifest transport IDENT, page magic and END counters.

The accepted raw MMIO/PCAP/record checks remain useful, but their agreement does not independently validate this unit's new framing, identity or RESULT claims. There is no console hash refresh to bypass: the material is simply ignored. See archive_probes.json and verify_tamper_*.json/txt.

**Repair contract:** give the console source an explicit archive contract and fresh verifier path. Require its retained material, validate its shapes/CRC/token/freshness and protocol state, derive rather than trust the cached identity/result/end summaries, and bind page/IDENT, requests/replies, RESULT to the retained opening/transaction results and notary material. Validate counters/termination only to the extent supported by the retained evidence, including legitimate refused/interrupted prefixes. This is internal consistency, not authenticity or physical proof. Preserve the existing non-console archive path. A console archive must not gain a clean verdict by dropping/changing its source declaration or raw log; make source selection explicit in the producer/verification interface and test that downgrade. Do not add an all-version verifier or rewrite old archives.

## 7. R5 — P2 — malformed TX text silently changes the requested transaction

**Code:** firmware/b4q/b4q_cmd.c:16–37, now shared with the actual console app.

**Independent reproduction:** the unmodified C parser returns success for all six cases in parser_probe.c / c_probes.json:

- unknown kind mystery becomes normal;
- genome hex 100000000 becomes genome 0;
- step word hex 100000000 becomes step 0;
- arbitrary trailing GARBAGE is ignored;
- TASK declares two cells but supplies one: accepted with task.n=1;
- TASK tuple (257,256,256,65537) becomes (1,0,0,1) through narrowing casts.

These are semantic changes, not whitespace normalisation. Copying a formerly internal parser unchanged does not make it a checked wire-input boundary.

**Repair contract:** a complete, explicitly defined textual grammar checked before transaction/signing. Reject unknown kind, values outside genome/step/field widths, malformed/partial TASK, invalid digest and trailing non-whitespace; validate counts and indices before narrowing. Preserve legitimate commands, full physical scoring and supported A5 grammar. Apply the same exact-count/range principle to SIGNREPLY's req and 24 words: no overflow/truncation or ignored extra words. Tests should prove malformed commands cause no SIGNREQ, staging write or DMA and no fabricated RESULT for a different transaction. No general-purpose parser framework is required.

## 8. P3 — narrow reproducibility wording

build_once returns only the .bin digest; reproduced_byte_identical compares those two strings. Say explicitly that two clean builds establish raw .bin equality. ELF/map hashes are provenance artifacts, not covered by that boolean. In this review's different checkout path, raw .bin, ELF program headers and selected symbols match; debug sections and ELF/map file hashes differ. No requirement to remove debug information or make every artifact path-independent. Fold this wording clarification into the repair documentation; no separate review round.

## 9. Same-unit repair authority and completion criteria

Authorised now: repair R1–R5 together in this PS-image preparation unit, with the necessary app/parser/console producer/verifier/tests/build evidence and narrow documentation/IMPORT changes. Keep b4q_tx.c's accepted core unchanged where possible; do not alter its per-call contract, carrier RTL/regmap/bitstream, model/hypothesis/task, protocol statistics, scientific thresholds, production labels/receipt or historical archives. Preserve first-delivery raw evidence as history.

Use injected host fixtures only. Add focused regressions for the reproduced paths and corresponding affected mutants; run the relevant 90-test regression once on the final code tree, regenerate the console e2e cases with fresh-process verification including coordinated console tamper negatives, and rebuild/pin the changed PS image. No unchanged 332-test battery, unrelated full mutant battery, or arbitrary fuzz/proof campaign is required. Valid negatives may be agree=true with recorded findings; contradictory/tampered evidence must not be clean. A test must exercise its intended guard, not pass because another early refusal masks it.

Complete the whole repair unit and submit once. No per-edit approvals, mandatory date gate or fixed commit count is imposed. This authorises no board connection/power/provisioning, image loading, physical PCAP, production derivation/run, new exploration/gate, push or merge. The remaining device-only and 2d/B4Q execution prerequisites stay unresolved.

## 10. Evidence guide

- snapshot.json, identity_checks.py/json: identities, source scope and digest checks.
- tests.txt, host_build.txt, xcheck.txt, a7.txt, mutants.txt / mutants_run.txt, build_evidence.py's output build_evidence.json/txt: independently rerun checks. xcheck_during_mutation.txt is an earlier compile-only invocation made while the mutant battery was active; xcheck.txt was rerun on restored sources and is the final check of record.
- e2e.txt, archive_probes.py/json/txt and verify_submitted_*/verify_regenerated_*: 28 fresh-process checks.
- wait_probe.c, parser_probe.c, c_probes.json: original-C bound/parser reproductions; review cap exit 77 is intentional.
- console_probes.py/json/stderr: duplicate-frame and after-stop reproductions.
- verify_tamper_*.json/txt: each bad copy's wrongly clean verdict; untouched is the control.
- REPRODUCE.md: commands and fixture boundary. review_metadata.json / SHA256SUMS: inventory and integrity.

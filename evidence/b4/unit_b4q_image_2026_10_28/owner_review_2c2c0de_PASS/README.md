# Owner review — PS-image round 4 — 2c2c0de — R1/R2 accepted, exact follow-up pre-approved for closure

Reviewed delivery **2c2c0dec** (full identity in review_metadata.json), implementation b1e5943. Canonical tracked tree was not edited. Baseline execution used /tmp/owner_b4q_r4_vv0dliwh; a separate clone /tmp/owner_b4q_approved_fix_vptfvsn0 holds the concrete follow-up patch independently tested by the owner.

## 1. Disposition

**Accept the submitted R1 and R2 repairs.** The actual missing/relabelled-reply counterexamples now reject, and the original active-terminal fixture now observes zero writes and zero new DMA issuance after END. No new candidate/restore signature was introduced; b4q_tx.c remains byte-identical to e267405.

The submitted tip still needs the two small P2 follow-ups in section 3. **The owner has already implemented and verified their exact repair in the second disposable clone.** Apply owner_followup.patch and meet section 4's byte-level conditions, then the author may archive and close this PS-image engineering unit **without another owner review round**. This is approval of a concrete, tested follow-up; it is not a claim that unmodified 2c2c0de already contains that follow-up.

No board, image loading, physical PCAP, production seed/run, push or merge is authorised. Engineering closure is not B4Q qualification, fulfilment of device prerequisite P2, 2c freeze, or silicon evidence.

## 2. Independent checks of the submitted repairs

- Two clean image builds match the submitted raw .bin: **010f6a05651e3db644a500d9e2081ecbc176bab04fcc526cc5af08d46dce1713**. Source/compiler/runtime/49 translation-unit/90 header hashes match after checkout-path normalisation. Raw-bin reproducibility is distinct from path-dependent ELF/map file hashes.
- All **14 older archive negatives** and **6 missing/relabelled-reply negatives** reject by named findings/refusal; clean controls remain clean. No verifier error in those probes.
- Original actual-app active-terminal probe: baseline status 0; injected sequence exhaustion status 6. After END: **0 writes, 0 PCAP entries/new DMA submissions**, one permitted diagnostic read in this earlier-cut fixture; no subsequent RESULT. This fixture sets the limit immediately before EV P4; the author's limit-minus-one fixture emits EV P4 then terminates and has no such read. Both demonstrate the write/effect boundary, not a physical-device observation.
- **19 submitted + 19 independently regenerated** console cases fresh-verify in agreement, including the honest sequence-cut prefix; A7 findings empty, cortex-a9 xcheck passes.
- Baseline fresh-checkout test invocation: 79 tests pass, then app setUpModule fails because seqcut was not built. After explicitly building seqcut, all 22 app tests pass. Do not describe that initial invocation as a cold-checkout 101-test success; both logs are retained. Section 3/F1 fixes the missing declaration.
- Frozen b4/IMPORT.json digests and firmware IMPORT digests all match; protected paths unchanged from e267405. From main dd8a7b9, only the already authorised carrier-manifest correction remains. The previous owner's 158-file checksum manifest matches its copied payloads and original source.

The submitted 39 killed / 1 named masked survivor / 0 edit-miss / 0 probe-error of 40 is an author battery record, inspected but not independently rerun here. R4a's masking and the killed R4a+C1a combination remain an acceptable account. No unrelated full battery or arbitrary fuzz campaign was added. The ignored netlist fixture was copied and hashed, not resynthesised.

## 3. Two concrete follow-ups, already repaired and verified by the owner

### F1 — P2 — declare the new seqcut fixture dependency

Fresh test setup builds host/apphost/wiretwin/waittwin but the new nineteenth scenario needs b4q_seqcut_twin. The evidence assemble script likewise builds apphost/wiretwin without seqcut. A warm working directory hides this missing dependency.

Exact patch: include the existing **seqcut** make target in tests/test_b4q_app.py setUpModule and evidence/b4/unit_b4q_image_2026_10_28/assemble.sh. No new build mechanism or firmware change.

### F2 — P2 — bind an exhaustion label to the publisher's sequence condition

The verifier's new terminal-prefix exception recognises kind PROTOCOL plus the reason string, but does not require the frame sequence to satisfy the existing publisher limit. On a complete valid archive, changing raw/cached END to that reason at sequence **34** still gives clean=true, agree=true, exit 0. On the genuine negative sequence-cut archive, lowering the last two frame sequences to **100/101**, preserving strict increase and cached sequence fields, still agrees as the same terminal prefix. Those sequences cannot satisfy the publisher's exhaustion guard.

Exact patch: import the existing SEQ_LIMIT from the console module and produce a named finding when an exhaustion-labelled END has seq below it. The patch adds one regression covering both complete and cut archives with refreshed CRC/cache. It does not invent a new numerical policy, require contiguous sequences, or change how legitimate interrupted/failed prefixes are classified.

The STOPPED-after-sent-QUIT probe is **not a finding**: capture order alone does not rule out an idle-timeout/queued-command race. Do not add a blanket rejection from that experiment. The narrow F2 patch checks an observable numeric predicate, not an inferred timing relation.

## 4. Exact follow-up and closure authority

The already-reviewed changes are these three files only:

1. host/b4q_verify.py — exhaustion sequence check, sharing the existing limit.
2. tests/test_b4q_app.py — seqcut setup dependency and one regression.
3. evidence/b4/unit_b4q_image_2026_10_28/assemble.sh — seqcut build dependency.

**Owner validation of this exact patch:** from a new clone without a prebuilt seqcut binary, **102 tests OK**, no skip; all **38 existing submitted/regenerated archives** still fresh-verify in agreement; both low-sequence exhaustion counterexamples reject. The real terminal prefix and the previous invalid-input classification controls retain the expected outcomes. bash -n and source diff --check pass. Tests and code hashes are retained. The target firmware/BSP/image inputs are unchanged, so the raw image remains 010f6a05…; no new image build is needed for this host/test/script-only follow-up.

The author is authorised to:

- Apply owner_followup.patch on the delivered branch, keeping the exact repaired bytes in approved_file_hashes.json. Running `python3 -B <review-dir>/verify_approved_followup.py <repo-root>` checks those hashes, the unchanged imports/protected runtime paths and source diff whitespace without deriving seeds or running a batch.
- Preserve this review/patch/test evidence; add a short own record of the successful hash/check result. Make the routine documentation/closure updates, including the scope clarification in section 5 and the architecture unit status. No date, branch-name or commit-count gate is imposed.
- **Once the exact checks match and only those repairs plus narrow documentation/evidence changed, close the unit as engineering accepted. No further owner round, repeated 102-test run, image rebuild or full mutant rerun is required.** The owner already ran the concrete repaired code. Preserve the submitted and cold-checkout failure evidence as history.

A different functional implementation or additional runtime changes are outside this exact pre-approval; they require their own review rather than being silently covered by these hashes. No push/merge or next undertaking is bundled with closure.

## 5. Claim boundaries to retain in the closing documentation

The archive verifier establishes its explicitly checked framing, identity, transaction/signature/result and terminal-sequence relations. It does **not** independently validate the END entry's `i` / `pcap_n` observer-position annotations or certify every post-END effect count from them. Their tamper probes remain agree=true on an already-negative archive; this is recorded as a limit of the current predicate, not claimed as a verified witness. The no-new-write/no-new-DMA mechanism evidence here comes from the source gate plus the independently drained actual-app/core fixtures. Do not describe verifier agreement alone as proof of quiescence or a device fact. A general timestamp/position verifier is not required by this closure.

UART, actual DMA/PCAP, watchdog clock/reset, platform abort behaviour and board timing remain device-only prerequisites. No key provisioning or physical operation happened. The model, task, hypotheses, statistical methods, thresholds, labels/receipt, historical production archives, carrier RTL/regmap/bitstream, N/B*, prediction/sessions and 2c standing remain unchanged.

## 6. Evidence guide

- tests_fresh_checkout.txt: real cold-checkout failure; seqcut_prebuild.txt and tests_app_after_prebuild.txt: explicit prerequisite and 22 app tests passing.
- build_evidence.json/txt, identity_checks.json, a7.txt, xcheck.txt, snapshot.json: independent baseline checks.
- archive_probes.json / exchange_probes.json and per-case reports: all previous negative cases now rejected.
- terminal_app_fixture.c, terminal_app_probe.py/json and baseline_*/sequence_cut_*.jsonl: old active-terminal probe, now zero effectful writes/submissions after END.
- terminal_archive_probes.py/json, end_reply_probes.py/json: the narrow new sequence-label defect and nongating observer/timing experiments, with controls.
- owner_followup.patch, approved_file_hashes.json, verify_approved_followup.py, approved_followup_check.json: concrete repair and closure check.
- patched_snapshot.json, patched_tests.txt, patched_checks/*: independent patched-code validation; patched source is separate from canonical and baseline trees.
- previous_review_integrity.json, review_metadata.json, REPRODUCE.md, SHA256SUMS: provenance/integrity/scope.

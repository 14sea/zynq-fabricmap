# Owner review — 3723b91 HOLD, B4Q host-only integration unit

Reviewed b4-b4q-integration@3723b91, parent b4e540a, WIP39b3e9c, based on main dd8a7b9. **HOLD: five blocking contracts below need repair in this same complete unit.** Normal-path reproduction succeeds; the failures concern boundaries not exercised by those paths. This is not a finding about silicon or the model's truth.

## 1. Independent work and limits

A detached local shared-object clone of the committed tip was used: `/tmp/owner_b4q_7w3a_pwh` (`snapshot.json`). No tracked source in the canonical tree was changed. No board, physical PCAP, production seed derivation, new exploration/gate, formal manifest regeneration, commit, push or merge was performed.

- Rebuilt host firmware under the submitted strict flags. The cortex-a9 compile-only check succeeds (`xcheck.txt`), not a board image.
- Reproduced the submitted RTL-trace fidelity check: 27 scenarios, **zero mismatches**, with the same explicitly limited bus-handshake coverage on the three hand-driven cases. This does not add fidelity beyond those traces (`fidelity.json/txt`).
- Regenerated all **11 host-only e2e scenarios**. Fresh-process verification on all 11 submitted and all 11 regenerated archives yields **22 exit0/agree=true**, with clean versus negative-path findings as recorded (`scenario_verifications.json`). That agreement is real but is insufficient to establish the missing contracts below.
- Initial test order on a clean snapshot gave **62 tests, 5 errors and 1 failure** (`tests.txt`). Schema/view/access tests attempted to consume or generate build/b4q_e2e/valid before the host binary existed, then reused a partial directory; the inherited netlist bench also lacked the ignored carrier netlist. After explicitly building/generating the fixture and supplying the unchanged pre-existing netlist dependency, the same nine modules give **65 tests OK** (`tests_with_prerequisites.txt`). `external_netlist.json` records the copied netlist's hash; this was not a fresh synthesis. Do not represent the initial run as green, or the dependency-supplied run as a source-only checkout without prerequisites.
- Frozen b4/host, b4/schemas, hypothesis, carrier RTL/builds/Vivado, historical firmware/manifests/certificates and production archives are unchanged in this unit's diff. The submitted332-test B4 result is not represented as an owner rerun; repeating it is unnecessary while those components remain unchanged.
- The probes in `probes.py` run the real compiled firmware against the injected host HAL, and use fresh CLI processes on copied archives. Their output is `probes.json/txt`. They modify only disposable clone/build files. Use `python3 -B probes.py <prepared-clone> <output-directory>` after building the host firmware; no board backend is involved.

## 2. Blocking findings and repair acceptance

### R1 — P1: fail-closed sequencing must precede subsequent operations/signing

Locations: firmware/b4q/b4q_tx.c:79,275,352,357,404; host/b4q_session.py:145,162,240.

Independently reproduced:

- Corrupt one startup readback word in the HAL. Session.open records **refused**, but Session.transaction still obtains a notary signature for root, the firmware reports status0 and X is **closed** (`startup` probe).
- Corrupt a returned pre-event frame word at frame ordinal9 (startup used8). The real firmware's pre_event digest differs from its commit, but it still runs init and completes closed. The host finds a link mismatch **after the transaction**. Calling another normal transaction obtains a second signature and succeeds (`pre_event`).
- Equivalent corruption in post-event and restored-base readbacks also produces firmware success/closed rather than stopping before stimulus or RESTORE_INIT/CLOSE (`post_event`, `base_readback`).
- Return **SLVERR on STEP_IN without changing the register**. The code ignores that write response, launches STEP on the old value and completes with firmware status0. Only the later record check catches “applied step is not the declared step” (`STEP_IN_SLVERR`).

Required: enforce the opening/previous-close/stop state at the layer owning the transaction and signing; a failed opening, link check, faulted/nonclosed predecessor or unresolved host failure must prevent the next signature/transaction. In firmware compare the observed pre-event digest to the staged/signed candidate **before init**, post-event to the required invariant **before steps**, and restored-base to the derived base **before the restore event/close**. Propagate unsuccessful accessor/HAL responses instead of reusing stale register data. Stop, retain acquired raw evidence and report the actual phase; post-hoc findings must not substitute for withholding the next operation. Preserve the explicitly authorised A5 injection exception and distinguish a bus acknowledgement from operation completion.

Tests must assert absence of the forbidden later event/DMA/signature, not merely the presence of a later host finding. Successful normal/A5 paths must remain valid. No RTL or model change is requested.

### R2 — P1: the archive verifier lacks completeness and correctly phased witness binding

Locations: host/b4q_verify.py:57,99–118; host/b4q_session.py:193–200.

**R2a, completeness.** Delete only `valid/tx_004/` from a copy of the submitted archive, leaving its manifest and full trace/PCAP logs intact. A fresh CLI verifier still reports **exit0, clean=true, agree=true, transactions3** instead of4 (`dropped_final_tx`). It enumerates directories but does not hold that set to manifest.records, the declared record sequence or the unconsumed raw suffix.

Required: bind the archive's declared records and indices/ranges to the exact retained transaction set; check order, duplicate/omitted records and raw evidence coverage, with explicit treatment of a declared partial tail. Reject unindexed/missing records and unconsumed successful transaction suffixes. Do not infer completeness merely from the remaining chain being self-consistent. This need not become a generic multi-version archive manager.

**R2b, staging phase.** `staging_readback_sha256` is currently taken from the second **envelope_written** event's configured frame-store hash, after PCAP submission, in both producer and verifier. That is not a retained witness of the executing side's DDR stream re-read **before the write**. Equality on a normal run does not make these the same event/commitment. Retain and bind the actual staging re-read/parsed-stream witness at its phase; recompute it from the relevant retained bytes/transcript. Keep pre-write staging and post-write frame/readback evidence separate and bind the executing-side report to each, without inventing past-phase witnesses from future effects.

**R2c, public refusal boundary (P2 within this repair).** `manifest.json = []` makes the CLI print an AttributeError traceback (`malformed_manifest.txt`). Validate the structures/file set and the fields/ranges actually indexed before consuming them; missing/malformed evidence must produce a named finding/refusal and nonzero status, not an uncaught exception. Focus negative cases on these archive boundaries; no exhaustive synthetic numeric campaign is requested.

### R3 — P1: qualification conclusions are neither reverified nor sufficiently conditioned

Locations: host/b4q_verify.py (no use of b4q_qual or retained qualification conclusion files), host/b4q_qual.py:18; docs/b4q_plan.md sections1,4.

Independent fresh CLI probes:

- Change AFF's a8_cross.json from row2/both demonstrated to row5/neither demonstrated: **exit0, clean=true**.
- Change a5_persist/a5_verdict.json from **fail to pass**: **exit0, clean=true**.
- Change a2_rows.json's ce_mode result: still **exit0/agree=true** (this fixture is already not clean because of its disclosed latch endpoint; there is no added finding for the changed conclusion).
- Directly call a5_verdict with the authentic J1/J2/J3 observations but **without either X/cleanup witness**: it returns **pass** (`A5_without_close_witnesses`). The accepted A5 projection includes cleanup and the required close/chain context; omission cannot demonstrate it.

Required: make qualification selection part of the retained declared plan/index (record IDs, elements, backgrounds, same-element corner roles and demonstration-part indices), validate it against the available complete/bound records and required witnesses, then independently recompute A2/A5/A8 and compare every retained conclusion/summary. Missing required corners, close witnesses, invalid references or malformed observations must not become a positive qualification claim.

Clarify the plan's machine-checkable distinction between **a valid collection/recording of fail or unknown data** and **the qualification claims being established**. A2 does_not_differ is not a positive control; A5 fail is not an A5 pass; A8 row0 stays unknown and row1 unresolved; rows3–5 can support only their explicitly reduced claims. “Every record audited” alone cannot give the broad section1 B4Q PASS. Do not erase negative/unknown data or tune vectors to obtain a desired verdict. The known host latch limit remains not_assessable, not a manufactured physical sample.

### R4 — P2: A7 checks a partial DMA tuple and trusts its kind label

Location: host/b4q_a7.py:95–101.

The tuple discards the memory-side source for writes/destination for reads. Supplying kind=env with source **0xdead0001**, the valid staging address **without HOLD tag**, or staging|3 (wrong low bits) all yields **findings=[]** (`A7_tuple_checks`). The fixed-endpoint/length checks are insufficient to establish the four legal submissions.

Required: derive/validate the kind from the full actual submitted addresses, lengths and tag/alignment; bind both endpoints and the exact allowed staging offsets/buffer extents, without accepting the logged kind as authority. Apply the same rule to read-command/read-frame/cleanup tuples. Include refreshable transcript/log negatives that retain the valid kind label but change the ignored endpoint/tag. The actual executing-side valid accesses must remain clean. No broader MMIO permission is granted.

### R5 — P2: raw model configuration shape is lost by coercion

Locations: b4q/schemas/ff_observation_model_raw_v1.schema.json:121; host/b4q_view.py:87–105.

The raw config schema is merely `{type: object}`. Replace one bit by **0.25**, recompute the raw dictionary digest in its correct encoding, and preserve the valid trusted provenance. The raw schema gives **no findings**, the adapter accepts it via int(...), and the resulting view also has **no findings**, with that bit silently changed to0 (`raw_float_config`). Source identity and a self-consistent hash do not make an illegal bit valid.

Required: validate raw configuration keys/domain and type-exact0/1 values before any conversion; reject float/bool/out-of-range values by name. Hold the raw schema/subset implementation and adapter to the same applicable constraints, with deliberate dynamic mapping/source bindings kept in the code validator where necessary. Preserve the legacy digest encoding; do not repair an input by coercion or re-encode a historical commitment. Check the other consumed raw/projection fields before deriving view data; legitimate model null cells remain permitted and carrier cells remain physical0/1.

## 3. P3 evidence/test descriptions

- The initial clean-snapshot run demonstrates setup dependencies/order sensitivity. State the build/netlist prerequisites, and make the B4Q fixture setup build/generate or explicitly check a complete compatible fixture rather than treating a directory's existence as completion. The existing ignored netlist is a declared carrier dependency, not a new defect in its RTL. Keep both owner test logs; do not claim the prepared run required no setup.
- “Equivalent on every available probe” is not semantic equivalence. C9's check can matter when staging is corrupted; C11's idle check needs an environment that does not supply the expected idle witness. Preserve **17/23** and the six named survivors as submitted, distinguish proven redundancy under an explicit contract from unexercised fault conditions, and add focused fault probes for the repair. The combined-mutant kills are useful evidence; do not count an untested guard as tested merely because a healthy path does not reach it.
- A raw mutant log has trailing whitespace (mutants.txt line17). It is an original output; do not trim it merely to make diff --check green. State the raw-log exception if reporting whitespace checks.

## 4. Dispositions on the author's disclosed issues

1. **Stale carrier manifest:** accepted as a real, disclosed metadata mismatch, not permission to use it on a board. The repair unit may include a **separate, narrow metadata correction** generated from the existing committed `builds/b4/b4.bit` at SHA256 **4e406f1280d3cf5cabf43d001278ef3b807a9ce4a7d036445122f5636e3d18a9**, using the existing manifest generator. Preserve the old manifest/digest and the generation command/comparison as historical evidence, show the21 values and frame references, and do not rebuild/replace RTL, bitstream or prior evidence. Update the stale-fact tests/documents to reflect the before/after state. This does not certify composition, routing isolation, live rewriting or any device.
2. **Host-side link failure without an O fault code:** keep it as a **named host non-success result with the actual phase/context and acquired raw prefix, with no fabricated O** when acquisition cannot be sealed. This narrow clarification is accepted for the integration; document it in the contract/plan rather than calling every host error an interruption. Do not add a carrier fault code or fill missing future witnesses. Such a failure latches stop as R1 requires. An already sealed O remains immutable; later failure retains the appropriate partial/faulted closing evidence.
3. **Latch endpoint unmodelled:** accepted as the host emulation's limitation. Do not fill the x5FF cells with zero or remove them to obtain a clean carrier O. Demonstrate the refusal/unknown path offline; actual physical observations require a later board ruling.

## 5. Scope of the repair — complete it once, then resubmit

R1–R5 and the corresponding focused tests, fault injections, affected mutants, explicit schema/adapter/qualification-plan updates and evidence may be repaired within this same unit. No preliminary scope draft or per-edit permission is needed. Retain previous logs, including failed setup runs and first mutant outcomes. Run the affected suites and the full inexpensive nine-module check once at closure with prerequisites stated; rebuild the host firmware and regenerate the complete offline scenarios, then fresh-verify them and the refreshed-evidence negatives. Do not rerun the unchanged332-test B4 battery or an unrelated production proof merely for this repair. Complete the metadata correction above if incorporated; it does not require a new implementation unit.

Preserve the hypothesis/model, task, protocol identity, statistics/thresholds, labels/receipt, historical archives/decisions and pinned B1–B3 history. Carrier RTL/regmap remains unchanged. Return the whole repair package for owner review. **No board/power/provisioning/physical PCAP, routing, production draw/search/gate, push or merge is authorised.**

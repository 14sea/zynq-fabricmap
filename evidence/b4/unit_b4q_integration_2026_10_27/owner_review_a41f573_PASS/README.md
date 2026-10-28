# Owner review — a41f573 PASS; B4Q host-only integration accepted

Reviewed **a41f57341a69fb6c9612bb7db4e0c434f9175525** on b4-b4q-integration, repaired implementation96ff8ee, following HOLDs on3723b91 and6f62b6a. **PASS for the complete host-only engineering unit. No blocking finding remains in the reviewed scope.** The B4Q plan is accepted as host-side qualification preparation with its physical prerequisites and claim limits intact; it is not a qualification result, a board execution ruling or a freeze of the B4 mapping preregistration.

## 1. Independent verification

All runtime work used a new detached local clone `/tmp/owner_b4q_round3_ut4zzex4` (`snapshot.json`). The existing ignored GSR-aware carrier netlist was supplied unchanged as a declared dependency and hashed, not regenerated. Canonical tracked files were not edited.

| check | result |
|---|---|
| stated-order regression, carrier benches before schema consumers | **71 tests OK, zero skip**,93.955s; nine unittest modules (`tests.txt`) |
| strict host build and cortex-a9 compile-only check | success (`build.txt`, `xcheck.txt`); pure target objects, not an executable board image |
| independent RTL-trace fidelity | **27 scenarios, zero mismatch**, retaining the same limitations on unlogged hand-driven handshake portions (`fidelity.json/txt`) |
| independent regeneration | **19 offline e2e scenarios** regenerated on the reviewed tree (`e2e.txt`); no physical backend |
| fresh-process scenario verification | **38/38 exit0/agree=true**, covering all19 submitted and19 regenerated archives; valid paths clean, negative outcomes named, no abnormal verifier exit (`scenario_verifications.json`) |
| prior coordinated archive/qualification counterexamples | missing final transaction, internal PCAP gap, A5/A8 conclusion tamper, A8 element/bits/background relabelling, changed init_samples/quantities, A2 semantic relabelling all refused/found; malformed manifest/record/ctx/nested executing_side all named REFUSED, no traceback (`probes.json`) |
| read/HAL admission counterexamples | failed NONCE read gives **zero signatures/no ARM**; failed HEARTBEAT read gives **no INIT_REQ**; failed DEVCFG_CTRL read gives **status1, no closed X**, rather than success; first failure retained (`probes.json`, `read_error_supplement.json`) |
| independent focused mutants | **8/8 KILLED**, zero survivors/edit misses, **14 green baselines**; three single mutants and five combinations kept distinct (`mutants_focused_full_log.txt`) |
| inventory/protected scope | IMPORT59 file/base/copied-function checks match; cloned frozen file hashes independently match; protected diff from6f62b6a empty; from dd8a7b9 only the previously authorised carrier manifest correction (`scope_checks.json`) |
| prior review archive | all **88** checksummed payloads, plus SHA256SUMS, match the original owner review byte for byte |

The independent mutation subset is **R2d, R3e, R3g; R1f+R1j, R1h+R1k, R2e+R2e2, R3c+R3d+R3e+R3f, R2c+R2e**. R3e uses swapped corners **with the conclusion recomputed to agree**, so the kill is held by corner identity rather than a collateral conclusion mismatch. The corrected malformed-manifest follow-up is independently killed. These8 are not represented as a rerun of the author's60 or as eight single-guard kills.

The submitted round-2 record remains **37 killed /23 named survivors /0 edit miss of60**, plus the separately retained R2c+R2e follow-up. The initial zsh zero-mutant attempt is not a kill or validation. Earlier whole-battery logs remain historical evidence, not an assertion that every survivor is semantically equivalent. The frozen332-test battery was not rerun.

The mutation script operates in place and writes its default log; it ran **only in the disposable clone**. Edited source bytes were restored by the script, its clone-only log was retained in this review and restored to the committed log bytes. Canonical and cloned tracked trees were checked clean after all runs. No original raw evidence was altered.

## 2. Accepted repairs and interpretation

**R1:** the first stop is now an admission invariant at both write accessors and before signing, with read/HAL response propagation and explicit precondition checks. It withholds further CTRL/staging/DMA writes and signatures while allowing failure diagnostics. Success/failure waits remain witness-based, and the authorised A5 injection path remains explicit. The read-failure examples now stop before the forbidden operation, not merely at a later audit.

**R2:** the opening owns a declared trace/PCAP prefix; subsequent records tile both retained logs with in-bounds ranges. Coordinated manifest/record gaps and undeclared/missing transaction suffixes are no longer accepted. Consumed nested structures are checked with named refusals; the CLI separately identifies an internal verifier failure, never a clean result. The emulated staging witness retains the bytes before the frame-store effect and is now described at its actual data-handling time, not at DMA queue admission.

**R3:** selection identity is held to actual O.config and mapping metadata: element order, selected element/varied bits, corner labels, common background/stimulus, endpoint genomes and semantic addresses, and A5 role/order/configuration. Bystanders remain diagnostic. The entire data-bearing conclusions are compared to recomputation. Missing/invalid witnesses do not create positive claims, while valid fail/unknown data remains retained data. The plan distinguishes record/collection validity from establishment of each qualification claim.

The previously accepted **R4 full DMA tuples**, **R5 type-exact raw configurations**, the **narrow manifest correction**, the **named host non-success/no fabricated O disposition** and the **honest latch emulation limitation** remain accepted. Carrier bitstream SHA4e406f12… and manifest SHA6e1cab86… remain unchanged from the accepted correction. No change to hypothesis/model/task, formal protocol/statistics/thresholds, labels/receipt, existing archives/decisions or pinned B1–B3 history is part of this PASS.

These checks establish the reviewed host-side sequence, arithmetic, record and verifier contracts on the specified fixtures/counterexamples. They do **not** establish physical PCAP links, routing/write-set safety, legal composition, real GSR/A8/timing/sampling, silicon agreement or B4Q qualification on either die. They do not reverse gate-1 FAIL or sim4/sim5 no-go and do not supply N/B-star/predictions/sessions for the stopped mapping route. This is not a universal proof over arbitrary archives or all possible HAL failures.

## 3. Routine documents-only closure — no new review or test round

The implementer may archive this review with checksum verification, mark the host integration unit accepted/closed and fold the following small description fixes into that ordinary closure:

- The current file index still describes `e2e/` as **sixteen** directories; the run of record now has **nineteen**. Preserve earlier16-scenario logs/tables as historical states, but make the current index unambiguous.
- Report **nine unittest modules /71 tests** (the repository README already enumerates nine). The delivery message's “ten suites” is not the module count; build/fidelity/cross-compile checks are additional checks. Do not rewrite raw test outputs.
- Keep the original37/23 round-2 result and the corrected follow-up separately attributable. No new total of60/60 or universal equivalence claim is warranted.

No program, schema, raw archive, mutant log or recorded result needs editing for this closure. **Do not rerun tests/mutants/e2e solely for these faithful wording/archive updates, and no separate review round is required.**

## 4. Next bounded work authorised — the actual PS board-image preparation, host-only

After routine closure, the implementing side may directly undertake **one complete B4Q PS-image preparation unit**, based on this accepted line (including its documents-only closure), finish it and submit once. No preliminary scope draft or per-edit approval is needed. Its concrete purpose is to satisfy the remaining **board-image/BSP/transport prerequisite**, not to execute qualification or revive the search/gate route.

Deliver:

1. A loadable PS application ELF and required offline build artifacts using the existing pinned/local toolchain and appropriate BSP, with self-contained build commands, compiler/source/library identities, linker/map/ELF hashes, entry point and buffer layout. Keep the carrier bitstream and accepted register map unchanged, reuse B1–B3 references read-only, and create new B4Q outputs rather than replacing historical artifacts/pins. If a required dependency is unavailable/incompatible, report the concrete limitation and continue independent preparation; do not fabricate a successful build.
2. The target HAL, notary/console framing, bounded waits/watchdog, DDR cache/MMU discipline and exception/error-to-stop path. Preserve the accepted admission invariant and key-window separation. Do not invent OKAY responses or measured timings where the platform provides no such witness. Production key provisioning remains a later, separately authorised act; offline fixtures use explicit fixture keys only.
3. Host-side tests of the actual glue/protocol/record paths with injected backends and meaningful faults, target compilation/linkage checks and A7 against the actual program/RTL map. Distinguish statically/host-verified properties from the real PS/PCAP path that only a device can demonstrate. Keep cold-start/session-open references and restored study-base references distinct, preserve raw prefixes and the unknown/refusal paths, and do not claim offline execution is on-target evidence.
4. Update B4Q readiness/plan documentation to name the produced image and remaining measured/physical prerequisites. Make the later F8B3 bring-up and17A6 qualification handoffs explicit, including pending2d provisioning/power measurement and write-set/composition authority. Do not mark those prerequisites met, select mapping N/B-star/prediction/session sizes, or freeze2c from this build. The existing no-go results remain intact.

Necessary B4Q firmware/host glue/build/test/document changes and local commits are within that complete unit; preserve the accepted observation/core semantics and frozen model/method/history. A concrete incompatibility requiring carrier RTL/protocol changes is reported, not silently absorbed. Dates, branch names and commit count are organisational, not newly imposed gates.

**This PASS and next-unit permission authorise no board connection/power/provisioning/physical PCAP or image loading,2d execution,routing,production draw/search/gate,push or merge.** Actual board work still needs a reviewed execution plan and its own explicit execution ruling. The owner review itself performed none of those actions.

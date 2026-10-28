# Owner disposition — c84b8bd5 — integration and next host-only unit

## 1. Closure confirmed

The exact approved follow-up is present at b98f3219 and the PS-image closure is c84b8bd57ca4c4f7f813116cbfd5d3408b656b46. The owner rechecked the three repaired hashes, imports, unchanged runtime scope and the 292 copied review checksums. Closure conditions are satisfied. No repeated unchanged test/image/mutant run is required for this confirmation.

## 2. Push and merge authority — granted for this milestone

Authorise the implementing side to perform the following normal integration, in order:

1. Fetch and confirm main and origin/main are dd8a7b9b0bea5acc37e55ef92513303af2b0fcec, the branch tip is c84b8bd57ca4c4f7f813116cbfd5d3408b656b46, the tree is clean and main is its ancestor. A changed main/tip is not covered by silently resetting/rebasing to force these values.
2. Push b4-b4q-integration at this exact tip, normally (no force), and verify the remote branch. Confirm main has not moved.
3. On main, merge that exact tip with --no-ff, preserving the history (no squash/rebase). The merge parents must be the named main and tip, and its tree must be byte-identical to the approved branch tree.
4. Normally push that verified merge commit to origin/main; fetch and confirm equality and a clean tree. A tree-identical merge does not need another unchanged suite run.

This is an engineering milestone integration, not a gate result or physical qualification. It covers only this branch publication and this merge/main push. It does not publish future unit commits, authorise force operations, merge/delete the isolated B3 repair or RED WIP, or authorise worktree deletion/prune. Other already-integrated branch references may remain as they are.

Archive this ruling in the next appropriate unit/evidence commit; do not add a pre-merge commit merely to archive the authority and thereby change the exact approved tip.

## 3. Next undertaking — authorised as one complete host-only unit

Authorise **B4Q physical-runner and evidence-acquisition preparation, host-only**, including its bring-up plan draft. It may start without another scope-proposal approval. Work through the unit internally, validate it, and submit the whole unit once. Starting from the newly integrated main on a separate working branch is appropriate; no particular branch name, date or commit count is a gate.

Purpose: prepare a real-source observation/collection path and its offline tests before F8B3 provisioning/bring-up authority. This is independent of the stopped mapping-benefit route. gate-1 FAIL, sim-4/sim-5 no-go, N/B*, predictions/sessions and unfrozen 2c remain unchanged.

### Deliverables

A. **Evidence/source audit and implemented acquisition design.** Before treating transport as solved, map every raw item needed by O/F/X/session_open, links 1–3, A7 and qualification to its actual producer, persistence point, export mechanism and commitment. The current board HAL completes Xil_In32/Out32 but does not export the MMIO/PCAP logs supplied by the emulated backend. Current b4q_verify also explicitly requires emulated=true. These are source-contract differences, not just a different file descriptor.

The unit must provide a truthful path for the required raw material, or explicitly limit a claim it cannot support. No reconstruction from an expected genome/model/emulator may masquerade as a physical observation. Preserve the distinction between recorded access/completion, actual sampled/readback data, derived digests and facts only a device can demonstrate.

B. **Runner and collector.** Implement the U-Boot/UART control-plane and application transport: pinned image selection, transfer/load witnesses and failure handling, page/token creation and verification, IDENT/framing/notary exchanges, banners/reset detection, timeout/silence/END handling and unconditional retention of acquired prefixes. Separate local image hash, load/transfer evidence and the IDENT low-word echo; the echo is not self-measurement of the executable. U-Boot text is control-plane evidence, not a PL observation. The tested host path must stop signing/admitting after a refusal/unknown or incomplete outcome as already contracted.

C. **Versioned raw source and verification.** Preserve the accepted logical O/F/X/session-opening semantics. Add the necessary physical-source raw schema/adapter/validator and trusted source selection where the old emulated format cannot honestly carry the observations. Reuse genuine common payload/logic where valid, but do not promise an unchanged byte format or obtain acceptance merely by removing the emulated check. Keep prior emulated evidence and its verification/reverification path intact; distinguish emulated/PTY fixtures from future device records.

Narrow PS-side HAL/console/collection changes needed to expose this evidence are authorised within this host-only unit, with dataflow, allowlist/A7, memory/layout, stop and overflow checks. Retain the accepted b4q_tx.c transaction semantics, its admission invariant, key-window separation, and carrier RTL/regmap/bitstream. If firmware/wire bytes change, issue a distinct image/protocol identity and rebuild/pin it; do not call it the unchanged 010f6a05 image. Fixture keys only in tests; no production-key provisioning/use is authorised.

D. **Offline end-to-end validation.** Test through PTY/serial and boot/application transcript boundaries. The device surrogate may emulate hardware internally, but the runner must obtain raw evidence through the proposed transport/export interface; it must not read the surrogate's private backend.trace/pcap_log to create facts unavailable on the board. Cover the applicable 19 scenarios, explicitly adapting/noting mechanism-specific fixtures, and inject interrupted loads, wrong image/page/identity, unexpected banners, silence/truncated output, partial witness export and effect/record stop cases. Fresh-process verification must reproduce the declared outcomes. Use focused tests/mutants, with no unrelated whole-project reruns.

E. **Bring-up execution-plan draft.** Map each device-only question to a proposed measurement/witness, prerequisite, stop outcome and permitted claim: UART/load/control plane, FCLK0, DMA/PCAP/readback chain, watchdog PERIPHCLK/period/reset, timing and the platform exception path. A deliberate abort is not automatically required or authorised: if proposed, justify it and its recovery separately in the draft. Separate the P4 2d provisioning/power work, F8B3 engineering bring-up P5, and 17A6 qualification P6. Name the still-unresolved write-set/composition/key/board-role authorities; do not grant them in the draft. Estimated timing and untested capabilities remain labelled as such.

The resulting unit may reveal an acquisition or hardware prerequisite that still needs work. Its host acceptance does not guarantee the board day requires no further engineering, and does not replace P4–P6.

## 4. Execution remains separately authorised

No real serial/SSH board contact, power, provisioning, supply measurement, image/bitstream loading, physical PCAP, production-key use, B4Q physical session, routing, new exploration/gate or scientific-method/threshold change is granted here. Use local files and emulated/PTY endpoints only. No push/merge of the next unit is bundled with section 3.

This is a complete next-unit authority, not a request for another preliminary proposal. Return for review when the host-only unit is concrete and validated; routine implementation choices within this scope do not need per-edit approval.

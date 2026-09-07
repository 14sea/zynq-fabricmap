B1Q attempt 3 audit and stop-loss decision — 2026-09-07

**Decision: LOST due to recurrent receive-stream corruption; qualification HOLD.
Stop-loss is in force. No further B1Q or mapping session is authorized.** Approve
committing the original attempt-3 directory and boundary record unchanged, together
with this separate audit. Do not pin the HOLD record, increase the CRC budget, issue
another ruling pair or reuse a consumed ruling to continue the experiment.

Reviewed repository HEAD: 90ddab7. Session B1Q, board 17A6, ruling identifier 2026-09-06-03;
execution and boundary record are dated 2026-09-07. Evidence directory:
`evidence/b1q/b1q_17A6_2026-09-06-03/`.
Manifest_at_run equals the committed manifest, SHA256
`38363973c10c48244dc04f08044647b1159d1446b00dec5776d9478b9aad0a0e`.
The 16 original files and boundary file have been hashed in the separate inspection.

1. **Independent result: HOLD reproduced.** The real B1Q adjudicator reproduces the
   stored result: audit seq 4 is incomplete, missing chunks 4 through 7. make_record()
   reproduces qualification.json; verify() refuses that record because its outcome is
   HOLD. All eleven record-bound file hashes verify, exports.json passes its schema,
   status, hash and size checks, and all seven summary export statuses are ok. Both
   archived ruling envelopes decode to the exact issued bytes; both original rulings
   are consumed. All 105 fabricmap pins and 128 instrument pins verify; the instrument
   remains clean at 689dde1.

2. **The collector/export failure handling worked for this session.** A read-only replay
   of console.log through the production line reader and CRC parser reproduces the
   exported IDENT, three REC objects, 28 audit chunks and quarantined fragment. There
   are four valid SIGNREQ, 63 valid HB and four AUDIT_READY frames. Records 1 through 3
   have eight chunks each and independently audit 3/3; seq 4 has chunks 0 through 3.
   Its pull ledger records an abort on the CRC budget at chunk 4. There is no valid
   CLOSE or TERM. The collector summary preserves PROTOCOL at last_seq 3, reason
   PROTOCOL_CRC_BUDGET: 5 > 4, with closing steps not_reached. No false COMPLETED or
   qualification PASS was produced. The last timeline event is 15.294 s after go.

   "Complete exports" means the collected evidence was persisted, including the partial
   pull and damaged bytes. It does not mean the board completed the intended data set,
   or that bytes lost before reaching the recorded stream were recovered. The application
   exporter worked; this does not exonerate every host-side transport component.

3. **Corruption characterization, with comparison provenance.** Two CRC failures are
   the seq-1 forced SIGNREQ/REC controls. Three additional CRC failures and one fragment
   are present. The additional CRC failures are consistent with character deletion:

   | Frame | Observed loss | Comparison |
   |---|---|---|
   | HB seq 2 | token shortened from 32 to 26 characters; payload intact | restoring the known session token yields the received CRC and the expected heartbeat i=6; received frame is a deletion-only subsequence |
   | REC seq 3 | payload shortened from 2556 to 2555 characters | same-run CRC-valid retransmission, matching retained CRC; deletion-only subsequence |
   | AUDIT seq 4, chunk 4 | payload shortened from 408 to 406 characters | attempt-2 valid chunk under the same image/plan; rebuilding its frame with this token matches the retained CRC and deletion subsequence |

   The AUDIT comparison is an inferred expected frame, not an independent transmitter
   trace. A 288-byte SIGNREQ seq-1 prefix without its terminator is also preserved by
   resynchronization. Do not count only the three non-control CRC drops when describing
   the full observed corruption. Being inside the base64 alphabet alone does not prove
   deletion rather than bit substitution; the comparisons above supply the stronger
   evidence. In particular, the HB loss is in the header, not its payload, so the failure
   is not confined to long REC payloads.

   An additional retrospective comparison builds the attempt-2 app TERM with attempt 1's
   token. Its CRC matches attempt 1's retained CRC; the received frame is a deletion-only
   subsequence with 13 characters missing (payload 655 versus expected 668). This supports
   the same observable receive-stream failure class in attempts 1 and 3. It does not
   authenticate attempt 1 as COMPLETED or restore that lost qualification.

4. **Root cause remains unlocalized.** The evidence establishes missing characters in
   the recorded receive stream, not the particular component that lost them. The existing
   post-hoc attempt-1 dmesg excerpt and the new post-hoc sysfs inventory support a CH340
   path through vhci_hcd on WSL. They do not establish usbipd as the cause, a UART FIFO
   overflow, a specific buffer limit, or exact correlation of a kernel warning to a bad
   frame. The three runs' non-control CRC counts 1/0/3 are not comparable noise-rate
   estimates: run duration, received bytes and completion differ, and fragments are a
   separate observation.

   The current sysfs inventory also puts FTDI ttyUSB2 and ttyUSB3 under the same
   vhci_hcd path. Switching adapters while retaining that arrangement would isolate
   an adapter/driver variable, not bypass USB/IP. Enumeration does not establish that
   those channels are physically available, correctly wired or suitable for this board.
   No device node was opened for this inventory; it is labeled post hoc and kept outside
   the original session evidence.

5. **Stop-loss accounting.** The frozen preregistration §6 requires stopping after two
   sessions lost to the same instrument/transport cause. Attempts 1 and 3 satisfy the
   operational stop criterion of repeated receive-stream corruption; a proven usbipd
   root cause is not required to stop. Attempt 2 remains a validated COMPLETED/PASS for
   its old manifest; its later supersession is not another LOST session. This is the
   second transport loss, not three sessions without validated COMPLETED.

6. **Next work authorized: offline investigation and a reviewable diagnostic plan.**
   Preserve raw bytes, fragments, retry timing and the per-frame deletion comparisons.
   Inspect existing host logs, USB topology/version records and the reader/serial setup;
   use memory-backed replay to test framing and export behavior. Keep any later log
   collection explicitly post hoc. Define a diagnostic matrix that changes one variable
   at a time and records known transmitted bytes, received bytes, retries, fragments and
   clock correlation before proposing an adapter, driver or USB/IP-path change. Any
   proposed fix needs repeatable evidence and review; one successful session is not a
   stability demonstration. Do not simply raise the frozen session's allowance.

   Opening a board-connected port, passive monitoring, reconnecting/reattaching a USB
   device, changing wiring or executing another session requires a separate explicit
   instruction after that plan is reviewed. No such action is authorized by this audit.
   Pinned changes require a newly reviewed manifest and qualification under fresh rulings;
   the current HOLD cannot become a qualification by post-hoc adjustment.

The boundary record `evidence/b1q/principal_boundary_2026-09-07-01.json` passes the
instrument validator at the reconstructed go time, approximately 247.831 s after its
timestamp. This is a recorded-boundary check, not a new live boundary check or independent
proof of a physical power cycle. Preserve it with the original evidence.

Audit artifacts: `evidence/b1q/session3_review_2026_09_07/`, including inspection.json,
readjudication.json, header_comparison.json, attempt1_term_comparison.json and a clearly
labeled host_inventory_post_hoc.json. The audit script writes only to a separate /tmp
directory. No original session file, pin, manifest or ruling was changed. No commit,
push, provisioning, device attach/detach, serial-port open or board execution occurred
in this audit. The unpinned package status was updated to record the stop-loss decision.

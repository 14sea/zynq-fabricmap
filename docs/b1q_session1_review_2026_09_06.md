B1Q session 1 review — 2026-09-06

**Decision: LOST due to host/transport failure; qualification remains HOLD.** Preserve
session `B1Q`, board `17A6`, identifier `2026-09-06-01`, as the first lost B1Q attempt.
No qualification PASS record may be issued from this run. The carrier remains unqualified.
Both rulings remain consumed. This review authorizes the host correction batch described
below, followed by tests and local commits for review; it does not authorize another
board session, new ruling issuance, or a push.

The frozen manifest at run hashes to
`2c031b4472d3b6a3b5393e5fdf4a367a124f1345d24460cde47277a379e36815`.
Image: `300b12b1104b70d1612f4c6236a9280a0556443757b2ddf9dbadd9ef993d5abb`.
Preregistration: `f995245cca13d5ac8cba8475c609a6e9f01d269cddc2d87e6a9b980f983652f2`.
The archived ruling envelopes decode to the issued whole-of-run and provisioning bytes,
with SHA256 `af7b464e4ab4a26beb1b9bad50ce62c5f0cb708aec7d852ed86d582a1f67bd19`
and `0975de226b167d2c012305372c947c73fc7aa23997ff9db6e34200df260a897c` respectively.

Source evidence is in `evidence/b1q/b1q_17A6_2026-09-06-01/`. The independent off-board
inspection and hashes of every file inspected are in
`evidence/b1q/session1_review_2026_09_06/inspection.json`. The original session files
were not rewritten. No board operation was performed during this review.

| Observation | Independently checked result |
|---|---|
| Valid received frames | 1 IDENT, 11 SIGNREQ, 176 HB, 11 AUDIT_READY, 88 AUDIT, 11 REC, 1 CLOSE; no valid TERM |
| Record sequence | seq 1 through 11, all SCORED; each record passes the B1 record validator |
| Audit | Recomputed from the raw-console chunks using the instrument's audit gate: 11/11 audited |
| Gate observations | All records have fault 0 and configuration_valid_hw=1; baseline tables_match=1 and zero readout; code-probe tables_match=0 and nonzero readout; signed expected tables are zero |
| Prediction | Both baseline score vectors, all nine probe genomes and all eleven content-level blocks match the pinned B1Q prediction |
| Closing observation | Valid CLOSE records unsigned refusal, fault 13, status 0x00000982, nonce 08f474ffb8e8ab15 → 2ead854756d71f03 |
| Host transactions | Timeline records 11 SIGNOK, 88 AUDITGET, 11 AUDITDONE, 11 RECACK, one SIGNGET and one RECGET; no TERMGET or TERMACK |
| Corrupt frames | Exactly three CRC failures in raw console: SIGNREQ, REC, TERM; timeline agrees; bad_frames=0 |
| Observed duration | 13.586488374 s from the first received IDENT to the final TERM CRC-drop event; this is not a complete session-span adjudication |
| Host termination | epoch_end PROTOCOL, reason `PROTOCOL_CRC_BUDGET: 3 > 2`; then `ValueError: crashed_summary is only for a CRASHED end` |

The valid records support the observed candidate and gate behavior. A decodable prefix
of the CRC-failed TERM is not authenticated by a valid frame and cannot establish
COMPLETED or rel-v4 closure. The missing run_log, audits export and adjudication do not
erase the raw observations, but they prevent treating this evidence as a complete
qualification. Count this attempt as one instrument/transport loss and one attempt
without a validated COMPLETED closure for stop-loss accounting. The existing two-loss
and three-without-COMPLETED limits remain in force.

Two host defects are confirmed from the source and saved traceback:

1. B1Q's CRC budget is `ceil(4 * 300 / 1000) = 2`. Its enabled SIGNREQ and REC retry
   controls already consume those two CRC drops. The TERM is the third drop. The console
   correctly enforces the pinned budget before reaching the TERM recovery handler;
   increasing the budget after the run cannot retroactively qualify this attempt.
2. `host/b1_session.py` calls `collector.crashed_summary()` whenever no app summary
   exists, although the imported method accepts only CRASHED. For this PROTOCOL end it
   raises before run_log/audits serialization. The finally block preserves summary/raw
   console, but not the complete collected evidence. Preserve the original PROTOCOL
   cause alongside the secondary host exception.

The raw frame corruption is established. The reported USB `seqnum max` event was not
among the persisted artifacts inspected here; it does not yet establish a particular
cable, driver, USB device or firmware cause. Preserve any available contemporaneous
kernel log separately, with its provenance, without replacing the original evidence.

Authorized correction batch:

1. **B1Q CRC budget only:** use the D-s4 noise allowance plus one drop per enabled
   forced CRC control. With the current flags, `2 + 2 = 4`. Expose the components and
   resulting formula in the B1Q plan and qualification document. Keep the B1Q bad-frame
   budget at 2: these controls are CRC failures, not malformed frames. Keep mapping B1's
   CRC and bad-frame budgets at 37, and preserve its plan and prediction bytes.
2. **Evidence preservation:** retain an existing valid app summary; otherwise produce
   a collector-written summary appropriate to the actual CRASHED, PROTOCOL or STOPPED
   state. Never relabel a protocol failure as CRASHED just to call a helper, or promote
   a corrupt TERM to COMPLETED. Preserve the valid CLOSE as an observation without
   asserting unsupported closing completion in a synthetic summary. The expected
   qualification result for missing closure remains HOLD/refusal.
3. **Finalization:** persist available records, audits, notary entries, transaction
   ledgers, timeline and raw bytes before adjudication. Summary construction and
   adjudicator exceptions must not prevent independent exports. Handle exceptions both
   before and after console initialization, and retain the primary failure reason.
   Mark incomplete exports explicitly; do not fabricate successful audit or closure
   evidence. Leave the archived instrument checkout unchanged.
4. **Regression coverage:** exercise the actual B1 session finalization path with fake
   transport/dependencies. Cover PROTOCOL without TERM, STOPPED without TERM, CRASHED,
   early setup failure and adjudicator failure. Verify persisted partial evidence and
   original causes. Exercise both forced controls plus a corrupt TERM followed by a
   valid retransmission, CRC exhaustion at the fifth drop with budget 4, and malformed
   frame exhaustion at the third bad frame with budget 2. Verify mapping budgets and
   frozen preregistration bytes are unchanged.
5. **Evidence and pins:** retain the original session and boundary evidence as the first
   LOST attempt. Any diagnostic reconstruction must be stored separately and labeled
   post hoc; do not backfill the original directory as though the runner wrote it.
   Update host/document/plan pins and the manifest as required, run the relevant tests
   and complete clean-tree suite, then make local commits and report for review.

Firmware, image, carrier RTL/bitstream, seeds, probe predictions and the frozen
preregistration remain unchanged. The host/plan/pin changes require a new manifest hash;
a subsequent attempt needs a new B1Q ruling pair bound to that committed manifest after
review. The original pair must not be edited, unconsumed or reused. Do not set
carrier.qualified or proceed to mapping on the strength of this diagnostic review.

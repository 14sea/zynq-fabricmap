B1 mapping session evidence audit — 2026-09-08

**Decision: PASS for the preregistered B1 mapping claim on board 17A6. Approve pushing
evidence commit 31d619e together with a separate commit containing this review, its audit
artifacts and the package status update.** No blocking evidence finding was identified.
No additional board session, retry or extension to B2/B3 follows from this decision.

Reviewed HEAD: `31d619eada9367dad35d4a6fe66f369e5a6c86f8`, one commit ahead of local
origin/main `5171d89`, clean on entry. That commit adds only the 16 original session files
and the boundary record. All 17 files still match their committed bytes. Manifest:
`38238271510536bda565ad1b8321dd04d75e78e1fe77ef94d2795bf9edfd4ba8`.
Session B1; seed 1123460948; token `6b6a8cf15ba2e45fdb9f1c5ee65862a8`.

1. **Binding and qualification pass.** manifest_at_run.json is byte-identical to the
   standing qualified manifest. All 105 fabricmap pins and 128 instrument pins verify;
   the instrument remains clean at 689dde1. The pinned attempt-4 qualification chain
   re-adjudicates to PASS. Both inert ruling envelopes reproduce the exact issued
   2026-09-08-02 bytes and their recorded issuance hashes. Board, session, seed, image,
   frozen preregistration and manifest bindings agree. Both local consumed markers record
   PASS; neither ruling may be reused.

2. **Exports and raw evidence agree.** Production exports schema, required status/file
   sets, hashes and byte sizes pass. Independent frame parsing finds 9048 valid frames:
   IDENT 1, SIGNREQ 335, HB 5360, AUDIT_READY 335, AUDIT 2680, REC 335, CLOSE 1, TERM 1.
   Decoded REC, AUDIT, IDENT, CLOSE and TERM payloads exactly match their exported objects.
   Receive order matches the timeline; the full timestamped console reproduces all raw
   lines. Every valid frame names this session's token. Original-file hashes, including
   files outside exports.json, are recorded in the audit artifact.

3. **The complete production adjudication is reproduced.** Re-running b1_adjudicate with
   require_git=True, the committed manifest and pinned plan/prediction gives PASS with
   zero findings. It reproduces the stored adjudication apart from evidence-path spelling
   and the map being exported separately. Its expanded map equals self_map_v2.json exactly,
   including schema and semantic checks. Every one of the 333 probe proposals replays;
   content SHA256 equals prediction:
   `7e1e7702ad3dc69d1ee4c809bf3cc829d7dc93696092d1e65c5ac1c4019ecbfa`.
   The token-bound internal map digest is
   `8e54ed81be7636724b1048432093d87c5323ab937b55bbc89285c15a27023f40`;
   this is distinct from the file-byte hash of the expanded JSON.

4. **The preregistered metrics hold.** All 292 entries are confirmed at confidence 2;
   precision and recall are 1.0, with zero unobserved claims or anomalies. Confidence-2
   calibration is 292/292; no confidence-1 cohort remains. Stratum A is 198/198 and B is
   94/94. All 32 interaction pairs have zero deviations and zero pending results. The
   provisional snapshot is 292/292 at confidence 1 after nine code probes. Full
   confirmation is reached at probe 301; the complete sequence contains nine code probes,
   292 confirmations and 32 pair probes. This supports the scoped claim for the 292
   certified addresses on this carrier/die, not arbitrary routing, another die or map
   utility in a later experiment.

5. **Audits and closure hold.** The audit gate independently recomputes 335/335 record
   audits from all 2680 chunks. All records are SCORED and every signed expected-table
   slot is zero. All 336 nonce transitions, including the unsigned control, recompute
   from the fixed manifest seed. The app-written CRC-valid TERM declares COMPLETED at
   seq 335, reason budget, 335/335 audited and all three closing steps done. CLOSE agrees
   with TERM: unsigned ARM refused with fault 13, nonce `f5a2fa6852249193` to
   `f4231ce12176dc70`. Timeline records TERMACK at wire seq 336 after TERM.

6. **Transport recovered within the frozen budgets.** Six additional received lines fail
   CRC: the two forced seq-1 controls and four non-control failures listed below. Each
   has exactly one subsequent matching valid retransmission in the raw console. For
   controls the body is identical and the CRC differs; for real failures the received
   CRC matches the valid retransmission and the damaged line is a shorter subsequence
   of it. No fragment or malformed frame is recorded. Host CRC use is 6/37 and bad-frame
   use 0/37. The TERM's 0/16 CRC figures describe the opposite, board-receive direction.

| non-control failure | valid retransmission | bytes missing relative to that retransmission |
|---|---|---:|
| REC seq 85 | next raw line | 441 |
| AUDIT seq 147, chunk 4 | next raw line | 42 |
| SIGNREQ seq 221 | next raw line | 222 |
| SIGNREQ seq 244 | next raw line | 33 |

These are materially larger losses than the small deletions observed in earlier B1Q
sessions. They remain recovered corruption, not missing final records. The evidence does
not identify where bytes disappeared or prove that the transport is repaired.

The operator's denominator needs correction: 9048 is the valid-frame count; six failed
frames are additional, giving 9054 framed receive attempts. Excluding only the two forced
control failures leaves 9052 attempts, including retries: 4/9052 = 0.04419%. Alternatively
report four failures per 9048 valid frames with that denominator named. 4/9046 subtracts
controls from a count that already excludes them and is incorrect. Attempt 3 had three
non-control CRC failures and one separate fragment, not four CRC failures. Its comparable
framed-attempt fraction is 3/(103+3); fragments are reported separately. The descriptive
ratio between these two sessions is about 64, not two orders of magnitude, and is not
an estimate of a stable link-noise rate. No TX-window causation is inferred.

7. **Timing and boundary are checked with limits.** First valid SIGNREQ to last REC spans
   429.863912 monotonic seconds; go to valid TERM spans 430.235281 seconds, below the
   pinned 1048-second deadline. The recorded boundary passes the production validator at
   the reconstructed go wall time and is 251.213 seconds old, with all five checks passed.
   This validates the recorded boundary, not a new live check or independent proof of
   physical power removal. Power-cycle execution remains operator-attested.

   The difference between recorded wall time and monotonic time changes by approximately
   -26.369458 seconds between the first and last valid receive events. The timeline does
   not explain that clock discrepancy. Elapsed-time/deadline figures above use the
   instrument's monotonic clock; wall timestamps must not be substituted for those
   durations. This run is not a host-clock calibration or a transport-stability proof.

No runtime or pinned-source change was needed, so the complete unit suite was not rerun
for this evidence review. Validation consisted of complete production re-adjudication,
qualification verification, independent raw parsing, audit recomputation, nonce checks,
map comparison and source/evidence hashes. The earlier 1456-test clean-tree report still
binds the unchanged qualified manifest and pinned inputs.

Audit artifacts: `evidence/b1/mapping_review_2026_09_08/inspection.json` records original
hashes and computed findings; readjudication.json is the independent production result;
inspect_evidence.py reproduces the offline audit and writes only to
/tmp/b1_mapping_review_2026_09_08. The original session directory and boundary remain
unchanged. Only unpinned package/review documentation and separate review artifacts were
added or edited. No commit, push, ruling issuance or board contact was performed here.

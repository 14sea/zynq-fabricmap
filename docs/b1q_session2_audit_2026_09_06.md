B1Q attempt 2 evidence audit — 2026-09-06

**Decision: PASS. The evidence supports the B1 carrier qualification specified in
docs/b1_carrier_qualification.md §3.1. No blocking finding was identified.** Approve
preserving the original attempt-2 evidence directory and its boundary record in a commit,
then pinning the existing qualification.json through the production manifest command.
This audit does not authorize running the B1 mapping session.

Reviewed repository HEAD: `98d95d84bd217855367b36536e912f33ee4addc8`.
Evidence: `evidence/b1q/b1q_17A6_2026-09-06-02/`, 16 files, initially untracked.
The committed manifest and manifest_at_run.json are byte-identical, SHA256
`e38f86a8a7679853eb943f0e968efd880a09faef849606c015ad0ec7616b9709`.
Session: B1Q; board: 17A6; master_seed: 176359248;
token: `9b4f0eba6fc8241283905eb88e5be991`.

1. **Evidence completeness and identity passed.** All 11 files named by the qualification
   record hash correctly. exports.json passes the production schema, status, hash and size
   checks. The audit additionally records hashes of all 16 original files, including the
   preflight/page records, transfer logs and qualification.json, plus the separate boundary
   record. Both ruling envelopes decode to the exact bytes issued for 2026-09-06-02;
   the original ruling files have consumed markers. No new usable ruling copy was made.

2. **Independent adjudication and qualification verification passed.** The real B1Q
   adjudicator, including the instrument validators, returns PASS with no findings and
   reproduces the stored adjudication (apart from relative versus absolute evidence path).
   make_record() reproduces qualification.json exactly. verify() returns PASS with
   readjudicated true when given an in-memory manifest containing this record. The real
   refresh(..., qualification_dir=...) produces that same in-memory manifest with
   qualified true. These checks used require_git=True where supported: all 104 fabricmap
   pins and 128 instrument pins verify, and the instrument is clean at 689dde1.

3. **Raw evidence agrees with the exported objects.** Independently parsed console.log
   using the instrument frame CRC/parser. Valid frames comprise 1 IDENT, 11 SIGNREQ,
   176 HB, 11 AUDIT_READY, 88 AUDIT, 11 REC, 1 CLOSE and 1 TERM. Decoded IDENT, every REC,
   every audit chunk, CLOSE and TERM equal their exported objects. The complete timestamped
   console reproduces the raw lines, including the go echo and application-start line.
   Valid received frame order agrees with the timeline after separating CRC_DROP events.
   All valid frames name this session's token. The host audit gate recomputes 11/11 audits.

4. **The required silicon observations are present.** Every record is SCORED, has zero
   signed table slots, fault_after 0, STATUS fault clear and configuration_valid_hw set.
   Baselines 1 and 11 have zero readout, tables_match 1 and counters [18,22,20,20,20,18].
   Probes 2 through 10 have nonzero readout and tables_match 0 while remaining valid and
   SCORED. All nine proposals replay and the content digest matches prediction:
   `ce2c89f96f063d90373b0be7bc67039fef714f796966ce43c3ca55594614240b`.
   The provisional result is 292/292 at precision and recall 1.0. This is the qualification
   result, not the later mapping session's confirmed-map claim.

5. **Closure and transport passed.** The CRC-valid TERM is app-written, declares COMPLETED
   at seq 11 for reason budget, reports 11/11 audited and all three closing steps done.
   Its closing control agrees with the separate CRC-valid CLOSE: unsigned ARM refused
   with fault 13, nonce 08f474ffb8e8ab15 to 2ead854756d71f03. Timeline records TERMACK at
   wire seq 12 after receipt of TERM. Exactly two raw lines fail CRC: seq-1 SIGNREQ and
   REC, matching the forced controls and their retries. There are no other CRC failures,
   bad frames or fragments. Host receive CRC count/budget is 2/4; the app TERM's 0/16
   describes the separate board receive direction and is not a contradiction.

6. **Nonce and timing interpretation checked.** Independently recomputed the RTL's
   64-bit xorshift for all eleven candidate ARMs and the unsigned control. All twelve
   transitions match, starting from the manifest's fixed seed. The same closing values
   as attempt 1 therefore follow from the same seed and attempt count; they do not
   establish fresh random nonces across sessions. The rate report's session_span_s is
   13.766874 s, defined as first SIGNREQ to last REC. The recorded go-to-valid-TERM span
   is 14.108917 s. Both are below the qualification plan's 615 s deadline.

7. **Boundary evidence passed with a stated limit.** The supplied boundary record passes
   the instrument validator at the reconstructed go wall time. It is approximately
   333.100 s old then, well within six hours, and records all five principal checks as
   passed. This is a review of the recorded checks, not a new live boundary test. The
   session directory does not independently prove that physical power was removed before
   this run; that operational prerequisite remains based on the operator's execution
   record/attestation, not inferred from repeated nonce values.

The original files remain unchanged. Audit artifacts are separate:
`evidence/b1q/session2_review_2026_09_06/inspection.json` contains the source hash table
and checks; `readjudication.json` contains the independent result; `inspect_evidence.py`
reproduces the read-only audit and writes to /tmp/b1q_session2_audit. No source change was
needed, so the full unit suite was not rerun for this evidence audit.

Approved next steps: commit the 16 original files unchanged together with
`evidence/b1q/principal_boundary_2026-09-06-02.json` and these audit artifacts; use
`host/b1_manifest.py --qualification evidence/b1q/b1q_17A6_2026-09-06-02` to verify and pin
the existing record; verify the resulting manifest and commit that transition separately.
Only carrier.qualification and carrier.qualified may differ from manifest_at_run in the
standing qualification chain. Pin regeneration should be byte-identical with unchanged
inputs; do not combine unrelated pinned-code or normative-document edits with this
transition. Historical wording can be clarified in an unpinned review/package document.

After the transition is committed and its exact manifest hash reviewed, the mapping pair
must bind session B1, master_seed 1123460948 and that new manifest. A fresh boundary and
separate explicit execution instruction are still required. Attempt 1 remains LOST;
attempt 2 has a validated COMPLETED closure, and both attempt-2 rulings remain consumed.

No evidence commit, manifest write, ruling issuance, push, provisioning, runner execution
or board contact was performed by this audit. The on-disk manifest remains unqualified
until the approved pinning step is carried out.

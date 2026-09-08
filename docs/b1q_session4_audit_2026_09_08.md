B1Q attempt 4 evidence audit — 2026-09-08

**Review decision: PASS for the recorded B1 carrier qualification. The existing record
is suitable for pinning through the production manifest command. The six reviewed local
commits are suitable for push with the separate documentation corrections from this
review.** No blocking evidence or strict-transition defect was found. This is not a
transport-stability finding or permission to execute B1 mapping.

Reviewed HEAD: `62927da8e906d0474d243d50aca2f86053873b52`.
The six commits after local origin/main `10a7bde` change only documentation and evidence.
No remote fetch or push was performed. Original attempt-4 evidence and its boundary are
already committed in `bc85b6c`; all 16 session files and the boundary still match that
commit byte for byte.

1. **Bindings and recorded authorization.** The archived ruling envelopes decode to the
   exact local ruling bytes for `2026-09-08-01`, granted_by `14sea`, board `17A6`, session
   `B1Q`. Both consumed markers record PASS. Their manifest, image and frozen prereg pins
   agree; the whole-of-run seed is 176359248. The package records an owner exception to
   stop-loss for this single run. That operational authorization is taken from the
   repository/operator record; parsing the ruling files does not independently authenticate
   the issuer or prove compliance with the prior stop-loss procedure. This audit neither
   retroactively issues that exception nor extends it to another run.

2. **Completeness and raw data.** Production exports validation passes, including exact
   schema, required statuses, file membership, byte sizes and hashes. All eleven files
   bound into qualification.json verify. Independent console parsing finds exactly 300
   valid frames: IDENT 1, SIGNREQ 11, HB 176, AUDIT_READY 11, AUDIT 88, REC 11, CLOSE 1,
   TERM 1. The only CRC failures are the seq-1 SIGNREQ and REC controls, with no other
   CRC failures, malformed frames or fragments. Decoded records, audit chunks, identity,
   CLOSE and TERM exactly equal their exported objects. Timeline receive order and the
   complete timestamped console agree with the raw stream.

3. **Independent adjudication.** The real B1Q adjudicator reproduces the stored PASS with
   no findings. make_record() reproduces qualification.json exactly; verify() re-adjudicates
   it successfully. The audit recomputes all 11 record audits from 88 chunks. All nine
   probes replay with predicted content SHA256
   `ce2c89f96f063d90373b0be7bc67039fef714f796966ce43c3ca55594614240b`;
   provisional claims are 292/292 correct. This is qualification, not the later B1 mapping
   result. All 105 fabricmap pins and 128 instrument pins verify. The instrument remains
   clean at `689dde1dad374536c625bbe2b05986ee89eb4c94`.

4. **Silicon observations and closure.** All eleven records are SCORED with zero signed
   table slots, cfg_valid set and fault clear. Baselines 1 and 11 have tables_match 1 and
   zero readout; probes 2–10 have tables_match 0 and nonzero readout. The CRC-valid,
   app-written TERM declares COMPLETED at seq 11, reason budget, with all closing steps
   done. CLOSE reports unsigned-control fault 13. All twelve nonce transitions recompute
   from the fixed manifest seed, ending at `2ead854756d71f03`; repeated closing nonces
   across sessions are deterministic and do not prove a fresh power cycle. TERMACK follows
   TERM in the timeline.

5. **Boundary and timing.** The recorded boundary passes the production validator and all
   five checks at the reconstructed go time, at an age of 366.491 seconds. Physical power
   removal remains operator-attested. First SIGNREQ to last REC is 14.269399 seconds;
   go to valid TERM is 14.611146 seconds, below the 615-second deadline. Session token is
   `d3d7c12332a53f94248a603392c04b9c` throughout the valid frames and qualification chain.

6. **The proposed state transition is valid.** Current manifest and manifest_at_run are
   identical, SHA256
   `38363973c10c48244dc04f08044647b1159d1446b00dec5776d9478b9aad0a0e`.
   Production refresh in memory changes exactly `carrier.qualification` and
   `carrier.qualified`, deriving true. The existing qualification.json hashes to
   `d0a7bbdae5781175795d650776168b7466ca047034919fecf96df9f29a8565d2`.
   With the production CLI's current serialization, the prospective manifest SHA256 is
   `38238271510536bda565ad1b8321dd04d75e78e1fe77ef94d2795bf9edfd4ba8`.
   This is a dry calculation, not a committed binding or an issued mapping ruling.

7. **Lifecycle validation.** The 18 tests in test_b1_qualification.py pass with no skips,
   including the freeze → qualification → pin → mapping-preflight fixture. Pinned code
   is unchanged from the v2.4.3 review, which already exercised the complete suite in both
   qualification states. This audit did not rerun that complete suite and does not claim
   a clean-tree proof for a transition that has not happened. After the real pin, commit
   the transition, then run the complete clean-tree suite and commit its report separately.
   Any failure must be reviewed before further pinned edits or mapping authorization.

8. **Documentation and interpretation corrections.** The isolation plan's opening claim
   that no board run or cable move had occurred was stale; it now distinguishes the
   unexecuted isolation experiment from the recorded attempt-4 exception. Statements
   treating absence of PnP log entries as conclusive exclusion, or a host-path comparison
   as isolation of USB/IP itself, have been narrowed to the available evidence. The 21:55
   topology snapshot names ttyUSB0, but the actual session summary names ttyUSB4 (188:4).
   An intervening enumeration is not documented by these session files. Module B and hub
   port 3 are operator-attested conditions; a USB device number cannot authenticate a
   descriptor-identical module. Preserve both original observations.

The operator's comparison table also repeats old attempt-3 counts. The reviewed values
are 103 valid received frames, three non-control CRC drops plus one separate fragment,
and 3/3 completed records audited. Its fourth audit pull was incomplete. There were five
total CRC drops including the two controls, not four non-control drops. Attempt 3 remains
LOST; these corrected counts do not change its outcome. See the attempt-3 audit and
corrected transport diagnosis. Attempt 2 remains a historical PASS for its old manifest.

Approved sequence for the proposed host transition:

- Commit this unpinned review and documentation correction separately; the reviewed six
  commits and these additions may be pushed. Preserve all original session files.
- Pin the existing record with `python3 host/b1_manifest.py --qualification
  evidence/b1q/b1q_17A6_2026-09-08-01`. Verify that only the two permitted manifest fields
  change and verify the chain again. Do not regenerate different pin bytes or change a
  source file, plan, prediction, frozen preregistration, image or carrier.
- Commit the transition and obtain the complete clean-tree test report, with no skips,
  before submitting its exact committed manifest hash for mapping-pair review. This review
  does not authorize a future, unreviewed transition commit for push.
- Mapping needs its own B1 pair bound to the final committed manifest and seed 1123460948,
  plus the required boundary and a separate explicit execution instruction. One B1Q PASS
  does not establish transport stability or resolve the earlier stop-loss cause.

Reproducible audit artifacts are in `evidence/b1q/session4_review_2026_09_08/`:
inspection.json records the source hashes and computed checks; readjudication.json is the
independent result; qualification_tests.log records the 18-test run; review_checks.json
records the commit scope. inspect_evidence.py audits the pre-transition state and writes
only to /tmp/b1q_session4_audit. No manifest write, original-evidence change, commit, push,
ruling issuance or board contact was performed by this review.

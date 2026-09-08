B1 qualified-manifest and mapping-pair review — 2026-09-08

**Review: PASS. The real qualification transition and its clean-tree test report stand.**
Following the user's request to review and issue the mapping pair, identifier
`2026-09-08-02` was selected after checking that neither file nor consumed marker existed.
The pair is issued under `granted_by: 14sea`, for board 17A6 and session B1. It is held
pending a separate explicit execution instruction; this review does not waive the
transport stop-loss or authorize board contact.

Reviewed HEAD and local origin/main both equal
`fb9de4de26bfb9022fff13f16cc3befc655c55b0`. The tree was clean on entry. No remote fetch
was performed. Transition commit `776b2db43686bc6029c71f3a734aa713f2b5df60` changes only
the two permitted qualification fields relative to the attempt-4 manifest. The current
manifest SHA256 is
`38238271510536bda565ad1b8321dd04d75e78e1fe77ef94d2795bf9edfd4ba8`.
Production qualification verify re-adjudicates the existing record to PASS and all 105
fabricmap pins verify. The instrument remains pinned to 689dde1.

The report `evidence/b1/tests/test_report_2026-09-08T212212Z.json` records 1456 tests,
zero skips, failures or errors, exit status zero, a clean working tree and clean_tree_proof
true at the transition commit. All 18 artifact hashes were independently checked against
both that commit's bytes and current disk bytes, including the qualified manifest. This
review verified the recorded full-suite result; it did not rerun the full suite.

The issued pair binds the current manifest above, frozen preregistration
`f995245cca13d5ac8cba8475c609a6e9f01d269cddc2d87e6a9b980f983652f2`, and image
`300b12b1104b70d1612f4c6236a9280a0556443757b2ddf9dbadd9ef993d5abb`:

| file | purpose | SHA256 |
|---|---|---|
| rulings/b1_2026-09-08-02.json | whole-of-run B1 cartography; master_seed 1123460948 | 88c1baaa8d2b4d60847a3bbcc2643914d6693468e10072450f2356ff6c89190c |
| rulings/p3_k_b1_2026-09-08-02.json | provisioning P3-K; session B1 | a3186d588fc46245186138e1e0be38c653cc1a454066a6772b17b8e781d5d4aa |

Both files were created exclusively in gitignored rulings/, read back and checked with
the production bind_ruling() rules. Neither has a consumed marker. No executable copy is
included in the tracked review artifacts. Full execution preflight was not performed;
the previous session's boundary was not presented as fresh evidence for a new session.

Before execution, the owner must explicitly instruct the run, addressing the continuing
transport stop-loss. A fresh power cycle, new principal-boundary record within six hours
of go, full preflight and unchanged manifest/pinned inputs remain required. The previous
one-session exception covered attempt 4 only. No additional B1Q run or automatic mapping
retry is authorized by this pair. The mapping plan remains 333 probes, 335 records,
9048 expected frames, CRC/bad-frame budgets 37/37 and deadline 1048 seconds.

Package header, ruling status and fail-closed description were corrected in unpinned
documentation to reflect the real qualified state. These edits do not change the
manifest or its qualification chain. Inspection metadata is in
`evidence/b1/mapping_pair_review_2026_09_08/inspection.json`.

No pinned file, source, original evidence, manifest or archived instrument was changed.
No commit, push, serial access, power operation, provisioning or runner execution was
performed by this review. The review documentation and metadata may be committed and
pushed separately; the live ruling files remain gitignored.

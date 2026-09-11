# B2 session binding completion review — 2026-09-11

Reviewed HEAD: `4d135be`, eight commits ahead of `origin/main` (`0d294ea`).

**HOLD remains on accepting/pushing the runner batch.** Export-seal validation, the
11-file qualification record and the deadline comparison are implemented. Offline
binding is still incomplete in two P2 areas below. The acknowledged absence of a complete
modelled B2/B2Q session and S1-to-S3 positive lifecycle also remains an acceptance blocker.
No new image or board action is requested by these findings.

## What is corrected

- `judge_session` now checks the archived manifest digest, export seal, expected log
  binding and selected slice. Independent negative controls for the binding image and
  actual slice now produce the appropriate findings.
- The shared B1 export validator verifies its declared schema, exact statuses/files,
  hashes and lengths. The qualification schema is explicitly migrated to 1.2.0 and
  includes all eleven B1 evidence filenames. The implementation's membership acceptance
  script was rerun unchanged: each formerly omitted file now affects the record, and
  an incomplete evidence set is refused. This closes the byte-coverage defect; it does
  not establish the semantic validity of every newly covered file.
- The measured span is compared with the supplied deadline, and a missing deadline
  produces a finding. B2Q's producer and re-adjudicator share a declared 2807/h planning
  rate; the CLI can agree with that rate or omit it, but cannot widen the deadline.
  Keep the planned S0/S1 pinning of the qualification documents and planning rule as
  a required part of the complete package, before freezing/running B2Q.
- The deadline/count tests now call the production instrument layer on a valid archived
  B1 transport fixture. The STOPPED mutation is honestly labelled as possibly rejected
  earlier by instrument validation; it does not establish coverage of the final
  epoch-outcome branch in isolation.
- Live build-input verification has zero findings, and all 105 B1 pins verify. The
  image remains `d164cd1d…`, ELF `7de96ed2…`, and B1 manifest `38238271…fd4ba8`.
  No ARM image was rebuilt. Independent focused suite: **361 tests, zero skips, OK in
  385.015 seconds**. Review artifacts were written during the run; this is not a
  full-repository clean-tree proof. Production code remained at the reviewed HEAD.

## P2-1. Offline identity checking still omits carrier/universe and B2Q inputs

`binding_findings` checks several B2 identity fields, but does not compare the IDENT's
`carrier_sha256` or `universe_sha256` with the manifest. The online
`identity_check_for` checks both, but it is not used during re-adjudication. The common
instrument validator checks field shape/internal consistency, and the B2 record replay
does not establish these two identities either.

Also, `qualification_session_plan` constructs no `inputs` member. The producer's
preflight does construct one using `expected_inputs`. `binding_findings` only checks
inputs when the expected member is non-null, so the B2Q offline path silently skips
this check. The producer/reconstructor consistency list does not compare `inputs`,
so that discrepancy is not detected by preflight's new self-check.

Independent isolated transport probes start from a zero-finding positive control and
change one field at a time. Wrong IDENT carrier digest, wrong universe digest, removed
`l6.inputs`, and a wrong manifest digest in `l6.inputs` all retain PASS with
`binding_checked: true`. Real B2 record replay, common validation enabled and without
any replay double, also accepts its own numerical fixture after changing either of
those IDENT digests. By contrast, the wrong-binding-image and wrong-slice controls
correctly HOLD. This separates the missing checks from the working ones.

Reuse a complete expected identity definition across online and offline checks, including
carrier/universe and the other existing online requirements. Reconstruct B2Q's exact
expected inputs from the validated run manifest and include them in the producer/offline
plan consistency check. Require the inputs object even when some fields are deliberately
null before S3. A missing expected contract must not disable a required check.

Add a zero-finding positive control followed by each mutation independently through both
producer adjudication and lifecycle re-adjudication. The current acceptance script does
not rerun the earlier wrong-IDENT-carrier case, and its other binding probes retain
unrelated seal/deadline/binding findings; they cannot establish this complete boundary.

## P2-2. Archived authorization files are hashed but not interpreted or rebound

`b2_manifest.reconstruct_qualification_record` now hashes the two ruling archives and
`summary.json`, but never parses them. `judge_session` does not read those files either.
Unlike B1 qualification verification, no B2 consumer decodes the inert envelopes, checks
their exact schema and internal byte digest, rebinds the ruling contents to the session,
or cross-checks the final summary against the archived ruling bytes and session token.

The independent isolated transport probes retain PASS after:

- replacing either ruling archive with `not JSON`;
- supplying a well-formed whole-of-run archive naming a different master seed, image,
  board or session;
- replacing the final summary with `not JSON`.

The real record builder also creates an eleven-file qualification record containing
the invalid ruling archive. The existing B1 archive parser correctly refuses that
same file. This is a parsing/binding omission, not a hash failure: once such a file is
accepted at initial qualification, recording its hash simply preserves the invalid
declaration. Later detection of changes to already-pinned bytes does not validate the
first accepted contents. The probe does not claim an end-to-end B2 qualification.

Decode the archived envelopes using the existing strict reader, and rebind the B2/B2Q
ruling text, board, session, image, preregistration, manifest and whole-of-run master.
Validate the final summary's token, outcome, whole-of-run ruling and provisioning
ruling byte digest against the session and archives. Preserve the distinction between
an inert archive and a live authorization: do not consume or reactivate archived rulings.

Place final-summary checks at the post-finalization lifecycle boundary: the shared
`b1_session.run` persists the final `summary.json` **after** the adjudication callback.
Requiring that final file inside the callback would create a new impossible positive
path. The ruling archives already exist before the callback; the final summary can be
verified when reconstructing/qualifying the completed evidence. Test both boundaries
through the real producer and fresh-process lifecycle verifier.

## Evidence scope and remaining acceptance

`probe_binding_completion.py` uses a temporary copy of committed B1Q attempt-4 transport
evidence. It supplies consistent synthetic invocation metadata and inert test-ruling
archives, reseals the copied log using the production seal writer, and runs the real
instrument/audit/ledger/timing checks. Only B2 record replay is doubled in this part.
The expected record count is explicitly adjusted to the inherited eleven B1Q records,
instead of B2Q's twenty. This creates a useful isolated contract control, **not a B2Q
session**, and neither the relabelled metadata nor the copied raw console is silicon
evidence for B2. Separate B2 numerical fixtures run real record replay with common
validation enabled. No source evidence or real authorization is modified.

The complete positive deliverable remains: modelled B2 and B2Q through the real host
stack and production exporter, actual session adjudication, S1 → B2Q → S2 → S3 and
fresh-process verification, with no replay or stored-result double establishing PASS.
Follow that control with independent identity/input/ruling/seal/deadline/closing/audit
mutations. Keep the missing `b2_pins` and `b2_test_report` tracked separately.

Artifacts: [`evidence/b2/review_binding_completion_2026_09_11/`](../evidence/b2/review_binding_completion_2026_09_11/).
This review writes only English review artifacts and a package status banner. No
production code, firmware, manifest, original evidence, real ruling or instrument file
is changed. No commit, push, board contact or port access is performed.

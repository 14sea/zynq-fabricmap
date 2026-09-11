# B2 ruling board authority review — 2026-09-11

Reviewed HEAD: `39125fb`, ten commits ahead of `origin/main` (`0d294ea`).

**HOLD remains on the runner batch.** The identity/input corrections and archive/summary
validation are substantially implemented, but the ruling's expected board is still not
established. This is one remaining P2 in the authorization contract, in addition to the
acknowledged missing complete offline positive lifecycle. No firmware rebuild or board
operation is needed to fix or verify it.

## Corrections verified

The implementation's `corrections_binding_completion_2026_09_11/acceptance.py` was rerun
unchanged. Its assertions pass, including zero-finding controls for binding, ruling
archives and final summary. Carrier/universe and variant mutations, missing/wrong inputs,
malformed archives, wrong ruling text/session/image/seed, and invalid final summary are
now detected by their respective components.

Source inspection confirms that online and offline identity checks share
`expected_identity`, the qualification plan includes inputs, and preflight compares
those inputs with the reconstructed plan. Archive parsing is strict and read-only.
The record builder refuses undecodable ruling envelopes before accepting their hashes.
`b2_manifest.verify` actually calls `summary_findings` at the post-finalization boundary;
the final summary is not made a prerequisite of the earlier adjudication callback.

Live build verification has no findings; all 105 B1 pins verify. Image `d164cd1d…`,
ELF `7de96ed2…` and B1 manifest `38238271…fd4ba8` retain their expected hashes.
Independent focused suite: **377 tests, zero skips, OK in 387.186 seconds**. Review
artifacts were written during the run; this is not a full-repository clean-tree proof.
Production files remained at the reviewed commit. No ARM build occurred.

## P2. Both rulings can agree on the wrong board

The issue is missing expected authority, not failure to compare two provided values:

1. `b2_manifest.init` produces no `board` member. The real test fixture, initialized and
   frozen through production S0/S1 functions, has no board field. The pinned B1 lineage
   manifest names `17A6`, consistent with the B2 preregistration's scope.
2. `parse_ruling` reads `(manifest.get('board') or {}).get('boardid')` and only compares
   the ruling when that value is non-null. Thus current preflight skips this check.
3. Neither the producer session plan nor `qualification_session_plan` supplies
   `boardid` at the top level or inside `binding`.
4. `archived_ruling_findings` reads those optional plan locations for `want_board`.
   With both absent, it only requires that the two archived rulings name the same
   board. Its expected-board comparison is never reached with the actual plans.

The independent probe uses a real S1 fixture and the actual B2Q preflight and offline
plan constructor. It does not add an expected board to either production plan.

| Case | Producer-plan archive check | Offline-plan archive check |
|---|---|---|
| Both archives name `17A6` | zero findings | zero findings |
| Only whole-of-run names `FFFF` | different-boards finding | different-boards finding |
| **Both archives name `FFFF`** | **zero findings** | **zero findings** |
| Both name `FFFF`, explicit expected `17A6` supplied only as a diagnostic control | two board findings | two board findings |

The actual read-only preflight also accepts a pair of temporary test rulings that both
name `FFFF`. The absent pin hook and unrelated principal-boundary/`sb` checks are
explicitly doubled; manifest/image/build/instrument/B1-chain checks are real. No
`execute()` call, port access or ruling consumption occurs. Missing `b2_pins` still
blocks production execution today; this result does not claim otherwise.

Both archives using the same nonempty array for `boardid` also receive zero findings.
Requiring a valid expected board and equality to it will prevent that alias from
passing; record the type/domain expectation explicitly as part of the contract.

The implementation's board mutation changes only the whole-of-run archive, leaving
provisioning at `17A6`. It therefore proves pair disagreement is rejected, not that
either archive is bound to the intended board. The same-board wrong pair is the
missing negative case.

## Required correction and acceptance

Establish the intended board from the reviewed B2 scope and validated lineage when
constructing S0, and pin it in the manifest before freeze. Require that authority to
be present and valid at verification and preflight; absence must be a refusal, not
permission to skip comparison. Do not derive the expected board from either ruling.

Carry that same expected value into producer and reconstructed session contracts, or
pass the validated manifest directly to the archive validator. Include it in the
producer/offline consistency check. Compare both live and archived rulings with it,
as well as with each other. Add tests for both profiles: correct pair; one wrong board;
both the same wrong board; missing expected board; and malformed board values.

The complete modelled B2/B2Q session remains the next integration deliverable: real
collector/console/notary/timing/exporter, real session adjudication, S1 → B2Q → S2 → S3
and fresh-process verification. No stored-verdict or replay double may establish that
positive lifecycle. The probe here exercises preflight and the archive component only,
so it needs no B1 transcript relabelled as B2 and makes no end-to-end PASS claim.

Artifacts: [`evidence/b2/review_ruling_board_2026_09_11/`](../evidence/b2/review_ruling_board_2026_09_11/).
Only English review artifacts and the package banner were written. No production code,
manifest, firmware, original evidence, real ruling or instrument file was modified.
No commit, push, ARM build or board contact was performed.

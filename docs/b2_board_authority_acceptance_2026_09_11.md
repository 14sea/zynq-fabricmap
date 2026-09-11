# B2 board authority correction acceptance — 2026-09-11

Reviewed HEAD: `7c4f0ca` (implementation `ecb56a6`, followed by a package-status commit),
thirteen commits ahead of `origin/main` (`0d294ea`).

**The board-authority P2 is CLOSED.** No further blocking defect was found within this
correction's scope. The overall runner package remains HOLD pending the previously
required complete offline positive integration. This is acceptance of a correction,
not a B2/B2Q session verdict, push authorization, freeze or board clearance.

## Independent evidence

The original `review_ruling_board_2026_09_11/probe_ruling_board.py` was run unchanged.
It produces the corrected results before failing its historical assertion that the
same wrong board should receive no finding. The failure is at that old expectation,
not at preflight construction or an unexpected runtime exception.

| Check | Current result |
|---|---|
| S0/S1 board declaration | `17A6`, with lineage role/part/idcode metadata |
| Producer and reconstructed plan | Both carry `binding.boardid = "17A6"` |
| Correct archived pair | Zero findings in both paths |
| One archive names `FFFF` | Pair disagreement and expected-board finding |
| Both archives name `FFFF` | Each receives an expected-board finding |
| Both carry the same nonempty array | Each receives a board type/domain finding |
| Read-only preflight with both live test rulings naming `FFFF` | Refused against `17A6` |

The original probe's missing-pins and unrelated principal-boundary/`sb` doubles remain
explicit. Real manifest, image/build, instrument and B1-chain checks run. It does not
call `execute`, open a port or consume a ruling. Its temporary test documents are not
owner authorizations. Missing `b2_pins` still blocks production execution.

An additional independent probe runs `b2_manifest.verify` in a fresh Python process
for each case, with no verifier or qualification callback double:

- Valid S1 fixture: accepted, board `17A6`.
- Missing board, wrong board `FFFF`, array value and whitespace-only value: named refusals.
- Change both the B2 board and a temporary copy of the B1 lineage manifest to `FFFF`,
  then update the declared lineage path/hash: refused by the real B1 qualification
  chain because the lineage manifest differs from its qualified manifest beyond the
  permitted transition. Original B1 files are untouched.

This establishes that mutual consistency of rewritten declarations does not replace
the existing qualification authority. S0 records the board from lineage; subsequent
verification checks the lineage file's hash, board agreement and the actual B1 chain.

## Code and scope assessment

`check_board` now makes a board declaration mandatory. Preflight calls it before ruling
processing, `parse_ruling` requires equality to it, and both session-plan construction
paths propagate it. `archived_ruling_findings` requires the expected value instead of
silently disabling the comparison, and checks each archive independently. The existing
producer/reconstructor comparison covers the complete binding object, including boardid.

The focused suite includes both B2 and B2Q controls, malformed/missing authorities and
live/archived ruling cases. Live build-input verification has zero findings, all 105 B1
pins verify, and image `d164cd1d…`, ELF `7de96ed2…`, B1 manifest `38238271…fd4ba8` retain
their hashes. Independent focused suite: **381 tests, zero skips, OK in 388.129 seconds**.
No ARM build was performed. Review artifacts were written during testing, so this result
does not constitute a full-repository clean-tree proof. Production code stayed at the
reviewed commit.

## Next required deliverable

Proceed with `b2_modelled_session`: complete B2 and B2Q sessions through the real host
collector/console/notary/timing/exporter, real adjudication, S1 → B2Q → S2 → S3 and
fresh-process verification. Establish the successful controls without replay or stored-
adjudication doubles, then mutate the session, binding, archive, audit, seal, deadline
and final-summary inputs independently. Include the producer/final-summary ordering
that previous reviews identified. Do not treat an S1 board-validation control as the
missing successful B2Q transition.

The remaining `b2_pins`, `b2_test_report`, frozen qualification documents/planning rule
and complete package review remain tracked. The current correction does not complete
those deliverables or demonstrate a runner PASS. Keep the overall runner batch under
review before push.

Artifacts: [`evidence/b2/review_board_acceptance_2026_09_11/`](../evidence/b2/review_board_acceptance_2026_09_11/).
Only English review artifacts and the package status banner were written. No production
code, firmware, original evidence, manifest, real ruling or instrument file was changed.
No commit, push, ARM rebuild, port access or board action was performed.

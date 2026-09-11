# Board authority correction acceptance evidence

Reviewed HEAD `7c4f0ca`, implementation `ecb56a6`. Offline only. No production code,
original evidence, real ruling, manifest or instrument file was modified. No port,
board, execute call, ruling consumption, ARM build, commit or push occurred.

- `original_probe_after.json` and `.stderr`: unchanged
  `evidence/b2/review_ruling_board_2026_09_11/probe_ruling_board.py`. It writes all results
  before failing its historical assertion that the both-wrong-board case is accepted.
  Corrected expectations were independently checked: board `17A6` in both plans;
  correct pairs have zero findings; both wrong archives each receive board findings;
  malformed arrays each receive type findings; wrong live test rulings are refused.
  Missing pins and unrelated principal-boundary/`sb` checks remain explicit doubles.
- `check_board_lineage.py`: run with
  `python3 evidence/b2/review_board_acceptance_2026_09_11/check_board_lineage.py`.
  An optional first argument specifies the repository root. Real `b2_manifest.verify`
  runs in a fresh process per case, with no verifier/qualification callback doubles.
  The S1 fixture is accepted. Missing/wrong/malformed boards are refused. A mutually
  rewritten B2 board and temporary B1 lineage file with an updated hash is refused by
  the existing B1 qualification chain. All mutations are temporary.
- `fresh_process_lineage.json`: output of that probe. This tests S1 board authority,
  not the still-missing positive B2Q qualification transition.
- `live_build_checks.json`: no build findings, 105 verified B1 pins and unchanged
  image/ELF/B1-manifest byte hashes. No ARM rebuild.
- `tests.log`: independent focused B2/B3 suite output. The run started on the reviewed
  clean commit; review artifacts were written while it ran. This is not a complete
  repository clean-tree proof. Command: `python3 -m unittest discover -s tests -p
  'test_b[23]*.py'`. Result: **381 tests, zero skips, OK in 388.129 seconds**.

See [the acceptance review](../../../docs/b2_board_authority_acceptance_2026_09_11.md).
The board P2 is closed. Overall runner HOLD remains until the required complete offline
positive producer-to-lifecycle path and remaining package deliverables are reviewed.

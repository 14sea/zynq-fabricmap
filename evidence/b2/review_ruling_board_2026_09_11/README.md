# Ruling board authority review evidence

Reviewed commit: `39125fb`. All probes are offline. No execute call, port, board,
provisioning, ruling consumption, ARM build, commit or push is involved.

- `acceptance_after.json`: rerun of the unchanged implementation acceptance script
  in `evidence/b2/corrections_binding_completion_2026_09_11/acceptance.py`. Its assertions
  pass. Its wrong-board case changes one archive, testing disagreement between the pair.
- `probe_ruling_board.py`: independent real S0/S1 fixture, read-only B2Q preflight and
  archive-component probes. Run with
  `python3 evidence/b2/review_ruling_board_2026_09_11/probe_ruling_board.py`.
  An optional first argument specifies the repository root. Temporary test rulings
  and inert archives are not owner authorizations. The missing pin hook and unrelated
  principal-boundary/`sb` checks are doubled. Manifest, image/build, instrument and
  B1-chain checks are real. No B2 replay double or relabelled transport is needed.
- `board_probes.json`: zero-finding correct-pair control, rejected single-wrong-board
  pair, accepted same-wrong-board pair against both producer and offline plans, and
  explicit-expected-board diagnostic controls that refuse it. Also records missing
  expected board in the real manifest/plans, the lineage board `17A6`, accepted live
  preflight with both test rulings naming `FFFF`, and accepted same non-string board
  values at the archive component. No end-to-end B2 session PASS is claimed.
- `live_build_checks.json`: zero build-input findings, 105 verified B1 pins and unchanged
  image/ELF/B1-manifest hashes. No image was rebuilt.
- `tests.log`: independent focused B2/B3 unittest output. The run started at a clean
  reviewed commit; English review artifacts were written while it ran. This is not a
  full-repository clean-tree proof. Command: `python3 -m unittest discover -s tests -p
  'test_b[23]*.py'`. Result: **377 tests, zero skips, OK in 387.186 seconds**.

The relocated probe was rerun and compared with the archived output. The source B1
evidence, production code, firmware, manifests and real rulings are untouched.
See [the review](../../../docs/b2_ruling_board_review_2026_09_11.md) for disposition
and the required complete offline positive lifecycle.

# B2 stage transition acceptance outputs

Reviewed source: `01acb5f`.

- `splits.json`: rerun of the submitted split acceptance, four valid S3 plans,
  all passing, with the actual selected slices and explicit fixture-stub scope.
- `tests.log`: independent StageCoverage run, 10 tests, zero skips, OK.
- `s0_s1.json`: rerun of S0/S1 acceptance; live manifest bytes unchanged.
- `bindings.json`: live file hashes, production S0 verification and state fields.

```sh
python3 -B evidence/b2/corrections_stage_split_2026_09_12/acceptance_split.py
python3 -B evidence/b2/corrections_s0_transition_2026_09_12/acceptance.py
PYTHONPATH=host:tests python3 -B -m unittest test_b2_runner.StageCoverage
```

Run from the repository root. `-B` avoids bytecode files in evidence. Temporary
S1 previews and stubbed S2/S3 fixtures are diagnostic test data, not live freezes,
measured calibration or qualification. No port, live ruling or production manifest
write was used. The full 451-test suite was not rerun for this targeted acceptance.

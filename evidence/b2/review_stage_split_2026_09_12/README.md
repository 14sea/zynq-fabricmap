# B2 stage/split review evidence

Reviewed source: `4f27ffa`.

- `review_stage_split.py`: build S3 fixtures at four finite feasible rates using
  the existing explicit fixture stub, verify each, and drive the unchanged
  committed-manifest test against each actual temporary manifest file.
- `results.json`: four-pair control passes; legal one-, seven- and nine-pair
  slices fail because the test supplies `(0, 4)` rather than their actual split.
- `stage_coverage.log`: submitted StageCoverage suite, 8 tests, OK.
- `s0_s1_acceptance.json`: independent rerun of the submitted acceptance script;
  both stages pass and production manifest bytes remain unchanged.

```sh
python3 -B evidence/b2/review_stage_split_2026_09_12/review_stage_split.py
python3 -B evidence/b2/corrections_s0_transition_2026_09_12/acceptance.py
PYTHONPATH=host:tests python3 -B -m unittest test_b2_runner.StageCoverage
```

Run from the repository root. The reproduction asserts the defect observed at
the reviewed commit; after correction its negative assertions should become
acceptance assertions. The rates are synthetic fixture values, not board
measurements, and its qualification re-adjudicator is explicitly stubbed as in
the submitted StageCoverage. No live manifest, pins, firmware, image, ruling or
instrument file is changed. No production freeze, push or hardware contact.

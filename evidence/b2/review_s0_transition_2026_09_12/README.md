# B2 S0 transition review evidence

- `review_s0_transition.py`: production S0 verify, unchanged committed-manifest
  test, production freeze on a deep copy, production S1 verify, and the same test
  reading a temporary S1 path instead of the live S0 path.
- `results.json`: S0 verify/test pass; S1 verify passes but the unchanged test fails
  on the null-prereg assertion. The live manifest's bytes remain unchanged.

Run from the repository root:

```sh
python3 -B evidence/b2/review_s0_transition_2026_09_12/review_s0_transition.py
```

The script asserts the defect observed at `fa0271e`; after correction that assertion
must change to acceptance. The in-memory freeze and temporary file are only a test
preview. No production freeze, board_ready change, ruling or board action occurs.
Do not use its generated S1 preview hash as an authorization binding. `-B` avoids
introducing ignored bytecode files into the evidence directory.

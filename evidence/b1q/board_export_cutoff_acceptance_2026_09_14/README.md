# Seventh-review offline acceptance

Target: 83e9e0b. These are software observations through a fake serial adapter,
not board evidence or a qualification.

`acceptance.py` runs the unchanged sixth-review 16-case probe and explicitly
asserts that its required-export contract is now satisfied. It also checks that
cutoff data, null comparison statistics, counter records, command count, and the
primary transport error survive the terminal-status correction. Completed reads
remain classified when their raw export fails.

Reproduce with:

```sh
python3 -B evidence/b1q/board_export_cutoff_acceptance_2026_09_14/acceptance.py
python3 -B -m unittest discover -s tests -p test_board_transport_soak.py
python3 -B host/b2_manifest.py verify
```

`results.json` is the acceptance output; `board_tests.txt` records the 48-test
suite; `b2_verify.json` records production S1 verification. Temporary acquisition
directories named in results are cleaned by the test fixture. No real port was
opened. No full-suite clean-tree proof is claimed.

# B2 adjudicator review evidence

Reviewed HEAD: `1b3995107088a48bbda2b380177f1a44d0864687`. Offline only.

- `reproduce_adjudicate.py`: run with `python3 evidence/b2/review_adjudicate_2026_09_11/reproduce_adjudicate.py`. It uses the committed small model fixture, wrapped in the native twin's per-record common envelopes. Common validation is enabled; these are synthetic envelopes, not signed/audited board evidence. A valid control passes, a wrong state digest gives HOLD, malformed inputs raise, and each nonblank baseline independently passes. It also invokes the real CLI with a malformed seq and records that `--out` is not written.
- `counterexamples.json`: captured public-API and CLI results from that script.
- `digest_correction.json`: unchanged 330-case probe from `review_records_types_2026_09_11`; all negative type cases rejected and the trailing-newline digest now rejected.
- `tests.log`: `python3 -m unittest discover -s tests -p 'test_b[23]*.py'`; 286 tests, zero skips, OK in 328.171 seconds. The tree was clean until completion.
- `live_build_checks.json`: independent `review_build_guard_2026_09_10/verify_current_build.py` output.
- `full_run_inputs.json`: byte sizes and hashes of the regenerated temporary model logs. They were generated with the committed `evidence/b2/b2_adjudicate_2026_09_11/modelled_run.py`; the large logs remain temporary rather than being duplicated here.
- `full_run.json`: CLI result for those three model logs, using the default committed plan and prediction and `--no-common`. PASS and all preregistered metrics match. The illustrative partition is 4+4+1; the plan's calibrated split remains UNDETERMINED.
- `train_word_changed.json`: same logs, except session index 1, seq 2004, readout word 0 is XORed with `0xffffffffffffffff`. Additive/F1 contradictions give KILL, replay diverges, and no primary is present.
- `holdout_bit_changed.json`: separate control, same record/word XORed with `1`. Vector 0 is outside train, so the search-stage numeric checks are unchanged and this case passes. It demonstrates the limit of these checks, not a claimed universal tamper detector.

For the large run, the command shape is `python3 host/b2_adjudicate.py --no-common --run-log DIR/run_log_0.json --run-log DIR/run_log_1.json --run-log DIR/run_log_2.json`; mutate only the identified word for the two controls. No model fixture is evidence about silicon.

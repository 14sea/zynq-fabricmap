# B2 adjudicator input-guard review evidence

Reviewed HEAD: `da89506cb5a70277c85646e166456de79c6bdd5e`. Host-only software review.

- `reproduce_input_guards.py`: independent mutations of the committed common-envelope model fixture. Run with `python3 evidence/b2/review_adjudicate_inputs_2026_09_11/reproduce_input_guards.py`. It invokes the public API with common validation enabled and separately runs the real CLI on `fitness=[]`. Native host twin construction is allowed; no ARM build or board contact occurs.
- `input_guards.json`: four API type exceptions, the CLI INTERNAL ERROR result, accepted malformed/ambiguous declarations, and positive/negative controls. Synthetic envelopes are not signed or audited board evidence.
- `previous_cases_after.json`: unchanged `review_adjudicate_2026_09_11/reproduce_adjudicate.py` output. Every original case is corrected, including baseline genomes and the mixed contradiction/malformed case.
- `tests.log`: `python3 -m unittest discover -s tests -p 'test_b[23]*.py'`; 302 tests, zero skips, OK in 317.090 seconds, run before any review files were written.
- `live_build_checks.json`: independent live image/build/pin check.
- `full_run.json`: corrected adjudicator over the prior independently generated 4+4+1 model fixture, using `common=False`; PASS, 18.696 seconds. Original input hashes are in `review_adjudicate_2026_09_11/full_run_inputs.json`.
- `word_tampered.json`: same fixture, session index 1 seq 2004 readout word 0 XORed with `0xffffffffffffffff`; KILL and no primary. This mutation changes both additive and F1 results.

The three-session partition is an illustrative planning scenario. The full-size fixtures are a model standing in for a board, not silicon evidence. No frozen-manifest bypass is claimed by the malformed plan/prediction probes; that external verification layer is explicitly outside this module's current scope.

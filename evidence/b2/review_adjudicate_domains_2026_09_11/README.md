# B2 adjudicator domain-correction review evidence

Reviewed HEAD: `0d294ea`. Independent checks ran on a clean tree; this directory was added afterwards. Offline only.

- `reproduce_domains.py`: run with `python3 evidence/b2/review_adjudicate_domains_2026_09_11/reproduce_domains.py`. Uses independent field paths over the committed common-envelope model fixture. Its 138 mutation cases comprise 135 REFUSED invalid inputs, one in-domain/self-consistent mismatch giving HOLD, and two accepted numeric aliases in the optional redundant delta (nonblocking P3). An unmodified run passes, generated F1/F2/F3 predictions pass the guards, and an injected programming error verifies the distinct INTERNAL ERROR / exit 3 path with a saved traceback. The script's expected outcomes explicitly retain the observed P3 behavior.
- `domains.json`: captured matrix and controls; no unexpected result or exception.
- `input_cases_after.json`: unchanged `review_adjudicate_inputs_2026_09_11/reproduce_input_guards.py`; prior malformed/ambiguous cases now refused. The old out-of-domain 999 control is correctly REFUSED too.
- `original_cases_after.json`: unchanged `review_adjudicate_2026_09_11/reproduce_adjudicate.py`; previous baseline, malformed-seq, mixed KILL and CLI corrections remain intact.
- `tests.log`: `python3 -m unittest discover -s tests -p 'test_b[23]*.py'`; 315 tests, zero skips, OK in 355.907 seconds.
- `live_build_checks.json`: independent image/ELF/build-input/B1-pin verification.
- `full_run.json`: corrected adjudicator over the prior independently generated model logs (input hashes in `review_adjudicate_2026_09_11/full_run_inputs.json`), `common=False`; PASS in 23.671 seconds, all preregistered numerical results reproduced.
- `word_tampered.json`: same fixture with session index 1, seq 2004, readout word 0 XORed with `0xffffffffffffffff`; KILL, no primary.

The fixture envelopes are synthetic, not actual signatures/audits. The large 4+4+1 partition is an illustrative planning scenario pending B2Q calibration. No result here is evidence about silicon, and no frozen-manifest or pin-chain bypass is claimed.

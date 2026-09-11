# B2 runner integration review evidence

Reviewed HEAD: `fb71b00939983c26d279e872628e85ac5fa566b8`. Offline only.

- `reproduce_runner.py`: run with `python3 evidence/b2/review_runner_2026_09_11/reproduce_runner.py`. It calls callbacks, the real lifecycle consumer and read-only preflight; it never calls `execute()`, opens a port or consumes a ruling. All mutable documents are temporary fixtures. The numeric fixtures use the committed native-twin common envelopes and model readouts, not actual signatures/audits or board evidence.
- `integration_probes.json`: B2 session-state/audit acceptance gaps, real B2Q replay and lifecycle refusal, actual instrument-schema preflight error, and subsequent isolated branches. The B2Q model is valid for these fixed seeds because the probe asserts the reference and qualification derivations coincide first; this does not claim general equivalence of the two exclusion rules.
- Later preflight branches use explicit doubles for the missing pin module and unrelated boundary/`sb` checks. The **actual** absent `protocol.wire` failure is recorded first. Only then is a read-only, in-memory instrument-manifest view given `wire="rel-v4"` to expose independent frame/ruling/rate defects. No instrument file changes.
- `tests.log`: `python3 -m unittest discover -s tests -p 'test_b[23]*.py'`; 346 tests, zero skips, OK in 371.179 seconds, before review artifacts dirtied the tree.
- `live_build_checks.json`: independent live image/build-input/B1-pin verification.
- `delta_after.json`, `delta_after.stderr`: unchanged `review_adjudicate_domains_2026_09_11/reproduce_domains.py`. Its assertion fails only on `redundant_delta_bool` and `redundant_delta_float`, whose recorded expected PASS represented the now-corrected P3. All other cases retain the expected results.

The record-only callback control is not a fully valid session; after session-level enforcement is added it needs replacement by a complete positive timing/audit/closing fixture. The synthetic calibration-rate declaration is likewise not measured throughput. No frozen-manifest or real authorization bypass is claimed.

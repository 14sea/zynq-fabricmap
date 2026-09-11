# B2 runner correction review evidence

Reviewed HEAD: `366d96f08a9e0bfef228b88091a3f838d5060be7`.
All work was offline. No board port, runner execution, provisioning, ruling consumption,
ARM build, commit or push occurred. Source session evidence was not modified.

## Files and reproduction

- `original_reproducer_after.json`: output of the unchanged earlier
  `evidence/b2/review_runner_2026_09_11/reproduce_runner.py`. Its imported test fixture
  now supplies the B2Q master, as disclosed by the implementation. The first successful
  preflight uses the actual instrument shape; later branches retain that old script's
  historical read-only wire view and missing-pins/boundary/sb doubles. The four original
  callback probes now stop at missing configuration, not at instrument acceptance.
- `probe_session_contract.py`: run from the repository root with
  `python3 evidence/b2/review_runner_correction_2026_09_11/probe_session_contract.py`.
  An optional first argument specifies another repository root. All writes are to
  temporary directories. The relocated script was rerun and produced identical output.
- `session_contract_probes.json`: the new probe's output. The instrument controls copy
  the committed B1Q attempt-4 run log, audits and timeline. The instrument validators,
  audit gate, closure/control checks and rate report are real. Only B2 record replay is
  doubled for these controls, because B1 records do not have B2 search blocks. Relabelling
  the supplied session plan as B2Q does not make the source transcript B2 evidence.
  The one-second deadline is an isolated boundary sensitivity probe, not a deadline
  obtainable from the production B2Q preflight. Real B2 record replay is separately
  exercised on numerical fixtures with common validation enabled. The qualification
  file-membership probe uses synthetic declarations and the real record builder; it
  does not claim a successful lifecycle transition.
- `tests.log`: independent `python3 -m unittest discover -s tests -p 'test_b[23]*.py'`;
  **358 tests, zero skips, OK in 360.050 seconds**. Started at the reviewed clean HEAD;
  review artifacts were written while it ran. This is not a full-suite clean-tree proof.
- `live_build_checks.json`: live build verifier findings (empty), 105 verified B1 pins,
  and image/ELF/B1-manifest byte hashes. No image was rebuilt.

## Interpretation

The earlier wire/master/seed/frame/rate corrections are reproduced. The session-level
work remains incomplete: invocation bindings, export sealing and qualification input
coverage, and maximum deadline checks are absent. The real instrument layer rejects
the independent CRC-over-budget and wrong-record-count controls. The controls that
reach PASS with a doubled replay locate missing outer checks; **none is an end-to-end
B2/B2Q PASS or evidence about B2 behavior on silicon**.

The complete offline S1-to-S3 positive flow remains outstanding. See
[`docs/b2_runner_correction_review_2026_09_11.md`](../../../docs/b2_runner_correction_review_2026_09_11.md)
for findings, scope and required verification.

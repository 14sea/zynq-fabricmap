# Transport uncertainty review evidence

Reviewed `328e9c1` on 2026-09-12. No physical device, ruling or production state
is used by these probes.

- `tests.log`: independent 94-test run, zero skips, OK, 63.299 s.
- `prior_owner_probe.json`: prior probe_boundaries.py rerun unchanged, exit 0.
- `submitted_acceptance.json`: current submitter acceptance rerun unchanged,
  exit 0. The three original boundary cases are corrected.
- `probe_uncertainty.py`: four identical production Run setups differing only in
  the returned bytes: intact, known CRC damage, unidentifiable damage, or silence.
- `observed.json`: original returned/persisted results and captured bytes for
  those probes. Temporary output directories are inspected then removed.
- `bindings.json`: production B2 verify and current binding hashes.

Run `python3 -B evidence/b1q/review_transport_uncertainty_2026_09_12/probe_uncertainty.py`
from the repository root, directing new output to a separate location.
Software PTYs are used only by the submitted test suite, never physical serial.

See [review and disposition](../../../docs/b1q_transport_uncertainty_review_2026_09_12.md).

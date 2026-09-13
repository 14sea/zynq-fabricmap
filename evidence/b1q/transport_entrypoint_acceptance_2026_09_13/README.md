# Offline transport entry-point acceptance

`acceptance.py` reuses the previous review's fake-port scaffolding, adds a close
adapter and asserts corrected behavior through the production CLI. All output
directories are temporary; no real serial port is opened. Run with
`PYTHONDONTWRITEBYTECODE=1 python3 -B`.

- `results.json`: PASS for nine independent positive/refusal/failure cases,
  including archived entry equality and explicit handling of archive failure.
- `b2_verify.json`: production verification at unchanged S1.
- `physical_archive_checks.json`: sizes and hashes of 127 already archived raw
  captures, and historical tool-digest checks. This is archival consistency
  only, not a re-adjudication of physical stability.

The reviewer also observed `Ran 130 tests in 71.391s`, `OK`, zero skips for
`python3 -B -m unittest discover -s tests -p test_transport_rig.py`.
No whole-suite clean-tree proof is claimed.

See `docs/b1q_transport_entrypoint_acceptance_2026_09_13.md` for the bounded
software acceptance, exact push scope and remaining physical transport work.

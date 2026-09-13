# Independent transport software acceptance

Reviewed `61e8a61` on 2026-09-12. These are offline validation outputs; they are
not a physical rig run, board session, qualification or stop-loss release.

- `tests.log`: independent 101-test transport suite, zero skips, OK.
- `owner_boundary.json`: prior owner probe_boundaries.py rerun unchanged.
- `owner_uncertainty.json`: prior owner probe_uncertainty.py rerun unchanged.
- `submitted_boundary_acceptance.json`: current boundary correction acceptance.
- `submitted_uncertainty_acceptance.json`: current metric correction acceptance,
  including the mixed confirmed/unresolved case.
- `bindings_and_pty_reanalysis.json`: production B2 verify, binding hashes, and
  independent raw-byte reanalysis of committed run_tx/run_notx PTY captures.

All four scripts exited 0. Source scripts remain in their original review and
correction directories; run with `python3 -B` and preserve new outputs separately.
The PTY reanalysis regenerated frames from each archived run_id, reconstructed
the successful full-run host echo ledger, reanalysed capture_000.bin, checked its
hash against run.json, and checked the recorded tool hash against current bytes.
No physical port was opened and no production state was modified.

See [acceptance and scope](../../../docs/b1q_transport_software_acceptance_2026_09_12.md).

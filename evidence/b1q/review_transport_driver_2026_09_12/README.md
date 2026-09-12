# Transport driver correction review evidence

Reviewed `146e60a` on 2026-09-12. All probes are offline. No physical port,
production manifest, pinned input, image, instrument or ruling is modified.

- `probe_driver.py`: pristine and one-echo controls, exact-delivery/echo mutations,
  production Run partial/deadline/error paths, individually injected export and
  provenance failures, mocked serial construction and a timing-aware source model.
- `observed.json`: original probe output. Temporary export directories referenced
  inside the output were inspected by the script and then removed automatically.
- `submitted_acceptance.json`: the submitter's acceptance.py rerun unchanged;
  its assertions all pass. It does not test the new cases in probe_driver.py.
- `bindings.json`: production B2 verify and current manifest/table/prereg hashes.
- `validation.txt`: test command and observed unittest completion summary.

Run from the repository root with `python3 -B` and send new output to a separate
file. The serial constructor probe installs a fake module; it opens no device.
The source-busy model only checks scheduling behavior, not real UART behavior.
The 49-test suite separately runs software PTYs, including production driver
controls with and without synthetic host TX. No full repository suite was rerun.

See [review findings](../../../docs/b1q_transport_driver_review_2026_09_12.md).
The original observations are retained for comparison after corrections.

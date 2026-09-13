# Transport entry-point second review probes

`probe_v2.py` imports the setup portion of the previous review probe, adds the
adapter's close contract, then drives production CLI paths with fake ports,
identity, counters and a virtual preflight clock. All acquisitions use temporary
directories. No physical device or archived acquisition is modified.

Run with `PYTHONDONTWRITEBYTECODE=1 python3 -B`.
`results.json` records observations at HEAD 84be778, including original-fix
acceptance controls, a mandatory provenance failure and an explicit close
failure. Assertions record the observed baseline/defect behavior; they are not
post-fix acceptance expectations for the two new probes.

Reviewed tests: 124 transport tests, zero skips, OK, 68.821 seconds. Production
B2 verify passed at the unchanged S1 binding. No whole-suite proof is claimed.
See `docs/b1q_transport_entrypoint_v2_review_2026_09_13.md` for findings and the
separate clarification of existing session retry behavior.

## After the corrections (`c2f38ab`, tool `e2af873d…`)

`results_after_fix.json` is `probe_v2.py` re-run against the corrected tool with its
before-fix assertions not evaluated; the two new cases read `run.json` only if it exists and
additionally read `entry.json` and the invocation's `terminal`. Observed: the four original
controls and the old-destination refusal unchanged (exit 0 / 3 / 3 / 2 / 5), each now with
`entry.json` beside the other files; `provenance_failure` exit 2, stage `invocation`, **zero
port writes**, no `run.json`, `invocation.json` carrying `terminal.reason: tool_error`, and
`entry.json` equal to the stdout brief; `close_failure` exit 0 with `close_attempted:
["/dev/FAKE"]`, `ports_closed: []`, the close error in both the brief and `entry.json`, and
`run.json` intact (302 accepted, 0 losses, error null). Offline; no real port opened.

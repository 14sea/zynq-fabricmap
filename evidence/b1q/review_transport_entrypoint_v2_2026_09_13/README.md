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

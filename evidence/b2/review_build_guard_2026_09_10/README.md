# B2 build-guard review artifacts

Reviewed HEAD: `9c1f3ca347ea6a58f356009796cbe364357372e0`.
The review is offline. Firmware, image, original evidence and instrument files are unchanged.

Run with `python3` from any directory:

- `reproduce_guard.py` reuses the prior review's mutation functions with the current
  verifier. It also tests four further provenance substitutions/omissions against both
  that verifier and every current `Committed` test, including real compiler dependency
  discovery. Only fixture loading is redirected to deep copies. The temporary compiler
  stand-in is ordinary text and is never executed. `counterexamples.json` is the output.
- `verify_current_build.py` independently compares the current evidence to inputs derived
  from the actual build configuration, requires the complete source inventory, checks
  the compiler identity, and verifies source/output hashes. It runs dependency discovery
  but does not build an ARM image. `live_checks.json` is its output.

`tests.log` contains the independent full B2/B3 discovery result: 186 tests, OK, no skips.
`test_counts.json` lists source-defined test methods by module.

Empty findings and successful consumer checks on the deliberately altered fixtures are
counterexamples, not review approval. The internally consistent empty dependency graph
is included as a control: the standalone verifier accepts it but the fresh dependency
test correctly rejects it.

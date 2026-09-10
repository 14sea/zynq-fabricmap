# B2 image correction review artifacts

Reviewed HEAD: `842abb96ef986a9645e632641bfb734002fc69d5`.
All activity is offline. Original evidence and compiled image files are unchanged.

- `reproduce_startup.py` uses the archived `a32b1fe` host harness and current application
  source to rerun the prior actual-main counterexample. `startup_after.json` is its output.
- `build_checks.json` comes from running the previous review's
  `../review_image_2026_09_10/verify_build.py` against the current checkout. It checks live
  hashes and reruns compiler dependency discovery without rebuilding an ARM image.
- `reproduce_guard.py` runs the actual seven submitted build-evidence tests against
  deep-copied evidence mutations. `guard_mutations.json` records the results. ACCEPTED
  means those tests passed, not that the evidence is valid or accepted by this review.
- `producer_mismatched_elf.json` records an independent producer check: `build_once` was
  mocked to return identical binary digests and different ELF digests; the actual
  `build_evidence(True)` correctly marked ELF equality and overall equality false.
- `tests.log` is the full B2/B3 discovery result; `test_counts.json` lists source-defined
  test-method counts by module. There are 172 tests including 28 gate tests.

Run the two reproducers with `python3` from any directory. They use temporary host builds
or in-memory evidence copies. Neither writes firmware, image, manifest or pin files.

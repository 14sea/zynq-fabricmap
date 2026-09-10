# B2 authority-correction review artifacts

Reviewed HEAD: `fb37ee0c32efc19aa2b2c41fe575df954c64e7ea`.

- `previous_counterexamples_after.json`: the preceding review's
  `../review_build_guard_2026_09_10/reproduce_guard.py`, run unchanged on current code.
  Previous role-substitution and source-omission counterexamples are now refused.
- `live_checks.json`: output of the preceding review's unchanged `verify_current_build.py`.
- `reproduce_runtime_cache.py`: run with `python3` from any directory. It copies the seven
  runtime files into a temporary directory and redirects only compiler `-print-file-name`
  responses to those copies. It exercises actual verification, cache and test code before
  and after a same-size overwrite or deletion. The original compiler, libraries, source,
  image and evidence are never changed. `runtime_cache.json` is its output.
- `runtime_aliases.json`: all seven recorded runtime paths replaced with temporary symlinks
  to their original targets; the verifier correctly accepts their canonical identities.
- `tests.log`: complete B2/B3 discovery, 193 tests, OK, zero skips.
- `test_counts.json`: source-defined test-method counts by module.

The cache probe runs all six current `Committed` checks with fixture loading redirected
to its copied evidence. Other subprocess calls, including dependency discovery, run
normally. Its after-cache-reset results are controls showing that the altered files are
refused when the real resolver rereads them. No board, image build, commit or push is involved.

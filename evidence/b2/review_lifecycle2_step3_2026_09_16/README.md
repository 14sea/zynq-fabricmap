# Lifecycle-2 step-3 review evidence

Read-only review of `8de4dfc` on `b2-lifecycle-2`.

The committed table equals `b2_pins.generate()` in memory, its 71 entries equal the 71 files
matched by the pinned globs, and every entry hashes to the current file.  Relative to the old
table, exactly the three reviewed pinned files changed.  The lifecycle-1 S3 manifest remained
byte-identical.

`b2_manifest.init` was also previewed in memory with the real build evidence.  The preview
verifies as S0 and has the expected empty transition state.  Its preview digest is diagnostic;
only the manifest actually written and committed in step 4 may be used as an identity.

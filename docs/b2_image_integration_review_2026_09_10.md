# B2 image integration review — 2026-09-10

Reviewed HEAD: `a32b1fe79921dfe06c7def083a8ddcff64be5c43`, ten commits ahead of the
local `origin/main = b951b80`. The checkout was clean at the start of review.

**HOLD on accepting image `e06b77a6…` for the completed §7 package. Two P2 findings
require correction and a new build.** Host implementation and corrections may continue.
This is an offline integration review, not a compatibility clearance, freeze, ruling,
push approval or board authorization. The explicitly unfinished B2 host tools remain
required; their absence is not counted as an unexpected implementation defect.

## P2: IDENT is emitted before the pair slice is initialized

`firmware/b2/b2_app.c:598` copies `g_pairs_total`, `g_pair_first`, and `g_pair_count`
into IDENT. These static variables start at zero. They are only assigned by the decode
in `b2_session_init()` at line 1550. Application `main()` calls `establish_identity()`
at line 1615 and waits for IDENTACK before reaching session initialization near its end.
Every valid first IDENT therefore reports `(0, 0, 0)`, irrespective of the page's slice.

The review reproducer compiles the unchanged application through the existing fake BSP
and actually calls its `main()` (`b2_app_main` in the harness). It supplies a checksummed
identity page with a valid `(pairs_total, pair_first, pair_count) = (9, 4, 4)`, a matching
fake nonce and passing carrier observations. Only the harness is adapted to supply that
page and script the IDENT handshake. No PL behavior is asserted.

| Scripted host / page | Observed application behavior |
|---|---|
| Valid page, ACK only if the three slice fields match | Three IDENT frames, all `(0,0,0)` with empty findings; STOP_IDENT; zero SIGNREQ |
| Valid page, ACK every IDENT | One incorrect IDENT; session starts and the first SIGNREQ is deliberately refused by the script |
| Reserved high bit, ACK every IDENT | Incorrect IDENT with empty findings; subsequently STOP_PAGE; zero SIGNREQ |
| Slice outside the experiment, ACK every IDENT | Incorrect IDENT with empty findings; subsequently STOP_PAGE; zero SIGNREQ |

A B2 host that enforces the intended identity binding cannot start the valid session.
Accepting the zero fields would bypass that binding. The invalid-page cases still stop
before proposing a candidate, but their IDENT does not yet report the slice refusal.

Decode and validate the B2 session fields after the common page parser succeeds and
before constructing IDENT. Preserve their validated values for subsequent orchestrator
initialization. Simply moving initialization before the page is parsed is not sufficient.
Add actual-main startup regression coverage for first and later valid slices, an invalid
slice, reserved bits and the identity ACK boundary. A valid page must emit its exact
slice, receive ACK and reach the deliberate first-candidate refusal. Invalid parameters
must never be presented as a clean, valid identity.

The existing application tests call `b2_session_init/run/finish` directly and never
exercise `establish_identity()`. The wire twin supplies its own fixed identity values.
Those tests pass without covering this ordering defect. UBSan reported no diagnostic
in the four review startup scenarios; this is a logic defect, not an observed memory fault.

## P2: the built image and evidence precede the tested firmware revision

`evidence/b2/build_evidence.json` records clean source revision `61bb908`. Both its
`sources.b2_app.c` and translation-unit entry have hash:

`5a9c386d92c376e0d364b07beb88d095fcb5186ee57dfe9820beb861f8da3a66`.

At reviewed HEAD, that source actually hashes to:

`cfbac577ecfb2c185aa8d61fc01f17e6f8eb1ba3bcbfb62da8726b393e9643de`.

Commit `a32b1fe` changed a runtime string after the clean build:

```diff
-REFUSED_BY_GATE: an unscored candidate ends the B1 epoch
+REFUSED_BY_GATE: an unscored candidate ends the epoch
```

This is executable string data. The actual binary contains the first string and does
not contain the second. The host harness compiles HEAD and asserts the second string.
Consequently the successful harness run does not test the source revision represented
by the submitted image. The difference is confined to this refusal wording; this finding
does not claim an additional search-algorithm difference.

The binary does hash to the declared `e06b77a6a9300a8d855ea99fb77e055890bd1e91c3cbdb6e2eb31c68f54b0ae9`
and is 114,708 bytes. Its ELF also matches the recorded final ELF digest. Those agreements
establish that the old output is present; they do not make its source provenance current.

After the startup correction and all other firmware edits, perform the clean builds and
regenerate evidence against the exact source revision being submitted. Add B2 build-input
freshness coverage that compares current source hashes, dependency sets and actual output
bytes with evidence; a binary string-presence scan alone does not detect this mismatch.
Do not reuse this image hash as the candidate for compatibility review.

## Checks that passed and their scope

- The comment scanner now preserves quoted comment markers and escaped literals. The
  previous P3 is closed for the reported cases, with the added fixtures passing. The
  generated header remains fresh at `518170db…c295`; binary leakage checks run without skips.
- All ten verbatim imports match their originals. Instrument files were compared with
  `git show` at archived commit `689dde1`; BSP scaffolds match the unchanged B1 copies.
- The orchestrator's nominal candidate order, absolute-pair arm alternation, slices,
  baseline brackets, holdout candidates and record blocks pass the C/Python tests.
  The whole nine-pair session produces 10,820 records and deltas `[2,5,6,3,4,6,1,-2,5]`.
- The application consumes PL readout words before calling `b2_orch_observe()`. The C
  orchestrator stores the measured opening baseline and supplies that stored base to
  both arms. Champion holdout is proposed as a real candidate and its observation is
  passed to `b2_search_champion_observe()`.
- The refusal harness exercises the real session loop, refusal branch, record handshake,
  restore-only cleanup and TERM. Closing-baseline completion is recorded after its
  observation. Earlier SCORED candidates are primed through observation/bookkeeping;
  staging, ARM and successful PL readout are not executed by this harness. Its generation
  case closes a budget-shortened generation at budget 2, rather than a full eighth child.
- Build dependency discovery was rerun for all 47 translation units, including with the
  optimization flags used by the build script. The recorded header set covers those
  dependencies. Compiler and seven runtime objects/libraries match their hashes. The
  only current input-hash mismatch is `b2_app.c`, listed twice as described above.
- B1's 105 pins verify; its manifest remains
  `38238271510536bda565ad1b8321dd04d75e78e1fe77ef94d2795bf9edfd4ba8`.
  The instrument checkout remains clean and unchanged.

The independent focused suite is **159 tests, OK, zero skips, 279.414 seconds**. The
reported 131 is not the current B2/B3 total. This review did not repeat the reported
1,615-test full suite and does not issue a new clean-tree full-suite proof.

The Python session reference remains a nominal model comparison: it calls the arm engine
to completion before emitting its candidate list, and its holdout block comes from the
modeled champion's stored tables. That is not replay of a fresh, possibly differing
holdout observation. The forthcoming adjudicator must consume actual returned observations
in session order, including the freshly remeasured holdouts, rather than treat this
nominal comparison as sufficient replay evidence.

## Documentation and provenance clarifications

The 86 headers are **26 embeddedsw, 10 repository firmware and 50 toolchain headers**;
they are not 86 embeddedsw headers. The 20 `sources` entries include headers, the linker
script and build script; they are not 20 linked C translation units.

The submitted reproducibility array contains two binary hashes but only one final ELF
hash is recorded. `build_once()` returns only the binary digest and the generator compares
those two values. It does not persist or compare both ELF hashes. The report's stronger
two-ELF equality claim is not independently supported by this evidence document. Record
and compare both ELF hashes on the required replacement build, or narrow that claim.

`IMPORT.json` still describes `b2_app.c` as B2-owned and derived from no instrument file,
while the application header correctly says it derives from B1 and claims the import
table names that derivation. Add the B1 application base/derived provenance when updating
the table for the replacement image. The earlier wire and scaffold entries are correct.

## Next checkpoint and artifacts

Close both P2 findings with actual-main startup tests and current build evidence. Finish
`b2_records`, `b2_adjudicate`, `b2_runner`, `b2_pins` and `b2_test_report`, then submit the
complete §7 package. B2-specific fields and cross-record bindings must be checked by
those tools; legacy instrument validators ignore unknown extension fields. Compatibility,
freeze and B2Q remain later steps, with existing ruling and transport requirements intact.

Artifacts: `evidence/b2/review_image_2026_09_10/reproduce_startup.py`, `startup.json`,
`verify_build.py`, `build_checks.json`, and `tests.log`. The startup probe runs unchanged
application code against a modified host harness. The build probe records the two stale
source-hash entries and asserts the independent dependency/output checks; successful
script execution is not an image PASS verdict. This review changes only review artifacts
and the package's review-status block. No firmware, image, pin, manifest, ruling, board,
commit or push action was performed.

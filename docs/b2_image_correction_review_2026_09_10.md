# B2 image correction review — 2026-09-10

Reviewed HEAD: `842abb96ef986a9645e632641bfb734002fc69d5`, fourteen commits ahead of
local `origin/main = b951b80`. The checkout was clean when the review and focused suite
started. This review is offline and does not authorize a push, freeze or board session.

**The original IDENT ordering defect and the actual source/image mismatch are corrected.
One P2 remains in the newly submitted build-evidence regression guard.** The current
image passes the independent input/output checks; it is not being designated defective
because of this test gap. Complete the guard before claiming the requested provenance
coverage is finished. Host implementation can continue; the full §7 package remains pending.

## 1. IDENT startup correction: verified

The application now decodes the slice after the common identity-page parser succeeds,
before constructing IDENT. The result and decoded values are retained for session init.
Invalid slices zero those values and add an identity finding. The findings array remains
sufficient for the checks present in this revision.

The previous independent startup probe was rerun against current `b2_app.c` using the
archived `a32b1fe` fake-BSP harness. Only the harness source selection was adapted; the
checksummed page and host handshake script retain the previous reproducer's behavior.
This avoids substituting the new submitted harness for the independent counterexample.

| Case | Current application result |
|---|---|
| Valid `(9,4,4)`, host ACKs only a matching slice | First IDENT accepted; exact slice and empty findings; first SIGNREQ reached |
| Same page, host ACKs every IDENT | Same correct identity and first SIGNREQ |
| Reserved bit | `(0,0,0)` with a slice finding; STOPPED / identity refused; zero SIGNREQ |
| Out-of-range slice | `(0,0,0)` with a slice finding; STOPPED / identity refused; zero SIGNREQ |

The first candidate in valid cases is deliberately refused by the host script. These
are startup/refusal checks, not successful PL-path tests. No UBSan diagnostic was observed.
The submitted six startup scenarios additionally cover the first slice `(9,0,4)` and no
IDENTACK (three transmissions, no candidate). The complete focused suite includes them.

## 2. Current source and built outputs: verified

The independent build probe rehashes all recorded inputs, reruns dependency discovery
for all 47 translation units, checks the unit list against the build script, and hashes
the actual binary and ELF. There are no current source-hash differences. In particular,
the application's current refusal string is present in the binary and the obsolete
`B1 epoch` version is absent.

| Output | SHA-256 |
|---|---|
| Binary, 114,708 bytes | `d164cd1d5b30aa5eb91f230b1373be8dda60d219249924e280957b26348d85f5` |
| ELF | `7de96ed25e01199ad4405dcc59b2ec92140c27679710e6acfbbad158e4986cdc` |

Both entries in the submitted two-build array equal these actual output hashes. Evidence
records clean source revision `2b20df9`; subsequent commits change evidence/docs rather
than the compiled application. The generator now collects both hashes per build and
compares both. A mocked build-output probe with identical binaries and differing ELFs
correctly produces `bin_identical=true`, `elf_identical=false`, and overall false.
The review did not run another ARM build; it verified the recorded two-build evidence
and current input/output files independently.

The ten verbatim imports and three B1-derived files have matching base/derived hashes.
The application derivation is now represented. Counts are correctly documented as 20
source entries (including headers/scripts), 47 translation units, 86 headers split as
26 embeddedsw / 10 repository / 50 toolchain, and seven runtime objects/libraries.

## 3. P2: the new build guard accepts incomplete or contradictory provenance

`tests/test_b2_build_evidence.py` does catch the original changed application hash,
changed image hash and dirty-tree declaration. Its claimed dependency/freshness coverage
is incomplete, however:

- Lines 51–58 iterate the evidence's declared translation units, substitute a repository
  basename if the recorded path is absent, then silently continue if it is still absent.
  A missing external compilation unit therefore passes. Lines 64–71 extract only the
  seven application-loop files, omitting the separately compiled `bsp/src/console.c`
  and the BSP/watchdog lists from the expected complete input set.
- The tests never recompute header dependencies or header hashes. The only header test
  checks rough category counts. Compiler and runtime-object hashes are not checked either.
- Lines 77–87 trust the three equality booleans and compare only build zero to `image`.
  Build one's actual hashes can disagree while the test still passes. The producer is
  correct; this consumer-side regression check does not enforce its recorded contract.

The isolated reproducer runs the actual seven `BuildEvidence` tests with a deep-copied
evidence object. It replaces only class fixture loading; test bodies and real input files
remain unchanged. No repository or toolchain files are mutated.

| Evidence fixture | Result of all seven submitted guard tests |
|---|---|
| Unmodified baseline | PASS |
| Application hash changed (control) | FAIL |
| Image hash changed (control) | FAIL |
| Dirty-tree declaration (control) | FAIL |
| Second build's binary and ELF hashes disagree | **PASS** |
| Recorded `stdint.h` hash is wrong | **PASS** |
| Required `stdint.h` entry removed | **PASS** |
| `libc.a` hash is wrong | **PASS** |
| Compiler hash is wrong | **PASS** |
| External translation unit points to a nonexistent path | **PASS** |
| Console removed from both source and translation-unit inventories | **PASS** |

These are counterexamples to the regression guard, not claims that the actual submitted
evidence contains these defects. The current independent build check finds none of them.

Complete the expected inventory from all build-script compile paths, including console,
BSP, watchdog and application units. Require the named inputs to exist; do not substitute
an unrelated basename or silently discard a missing entry. Recompute dependencies and
hash every header, compiler and resolved runtime object. Compare both build-output pairs
with each other and the named current outputs. Cover omissions and wrong hashes with
negative fixtures. The earlier review's `verify_build.py` already demonstrates much of
the required read-only checking.

The image test also skips when the binary is absent and conditionally ignores an absent
ELF. That may be useful in an explicitly incomplete development checkout, but a completed
image-package proof must require those artifacts. Its result must not be described as
an unconditional refusal of missing build outputs. This is part of the same guard scope.

## 4. Verification result and next step

The independent focused suite is **172 tests, OK, zero skips, 302.121 seconds**.
The working tree remained clean through its completion; review files were written afterward.

The reported 144 excludes exactly the 28 tests in `test_b2_gate.py`; the complete B2/B3
discovery includes those tests. The review does not repeat or certify the separately
reported/background full suite.

B1's 105 pins verify and its manifest stays at
`38238271510536bda565ad1b8321dd04d75e78e1fe77ef94d2795bf9edfd4ba8`.
The instrument remains clean at `689dde1`. The wire claim is now appropriately limited
to common-envelope compatibility. B2-specific validation and replay of actual observations,
including remeasured holdout, remain work for the unfinished host tools.

Resolve the guard gap, then finish the full §7 host-tool package and submit it for review.
No additional firmware defect was found in this correction diff. The remaining correction
can be addressed in host verification/tests; no new image is requested by this finding
alone. No firmware, image, manifest, pin, ruling, board, commit or push was changed here.

Review artifacts are in `evidence/b2/review_image_correction_2026_09_10/`: the startup
reproducer and output, independent build checks, isolated guard mutation script/output,
the producer's mismatched-ELF probe output, focused test log and test counts. Earlier
review artifacts remain unchanged. `ACCEPTED` in the mutation output means the submitted
guard tests passed, not an approval of that evidence by this review.

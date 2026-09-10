# B2 build-evidence guard review — 2026-09-10

Reviewed HEAD: `9c1f3ca347ea6a58f356009796cbe364357372e0`, seventeen commits ahead
of local `origin/main = b951b80`. The checkout was clean at review start.

**The previous seven counterexamples now fail as required. One P2 remains: the guard
does not fully bind its input inventory and toolchain roles to the actual build.** The
current submitted image and evidence pass independent live-input verification. This
finding concerns the guard's acceptance rules, not a newly observed firmware defect.
Host work can continue; complete this guard before declaring its review HOLD resolved.
The five unfinished host tools and complete §7 review remain separate requirements.

## 1. Previous counterexamples: corrected

The previous review's mutation functions were reused against the new `verify_findings()`
API. Its original unmodified baseline passes. All seven previously accepted corruptions
are now refused with findings: differing second-build hashes, wrong header/compiler/libc
hashes, a missing header entry, a nonexistent external unit, and omitted console input.
The application-hash, image-hash and dirty-tree negative controls also remain refused.

The submitted dependency test genuinely reruns `gcc -M` for the build's units. As an
additional control, the reviewer replaced every recorded dependency list with an empty
list and emptied the header table. The standalone verifier accepts that internally
consistent object, but the complete `Committed` checks reject it at the fresh dependency
comparison. That is the intended contribution of the additional test, and is not counted
as a new failure of the combined guard.

The new checks require the binary and ELF, compare both build-output pairs, recompute
the equality verdicts, and compare those pairs with the named outputs. The old basename
fallback and silent missing-unit continuation are gone.

## 2. P2: build roles and required non-translation-unit inputs are not bound

At `host/b2_build_evidence.py:221`, the compiler file is selected by the evidence's own
`toolchain.path`. At line 228, each runtime file is likewise selected by the evidence's
own object path. The code verifies those bytes against the same object's declared hash,
without checking that the path names the compiler or runtime object the build actually
uses. The source inventory at lines 186–192 requires application and console C files,
but does not require the linker script or build script to remain in `sources`.

The reviewer supplied four additional deep-copied evidence fixtures:

| Evidence change | `verify_findings()` | All four `Committed` tests, including real `-M` |
|---|---|---|
| Point the compiler path at a temporary ordinary text file named `bin/arm-none-eabi-gcc`, with that file's correct hash | Empty findings | PASS |
| Put the real `libm.a` path and hash into the `libc.a` entry | Empty findings | PASS |
| Remove `bsp/lscript.ld` from `sources` | Empty findings | PASS |
| Remove `bsp/build.sh` from `sources` | Empty findings | PASS |

The fake compiler file is not executable and was never run. Dependency discovery still
uses the real compiler selected by the module's `TC`, which is why its successful result
does not establish that the different compiler named in the evidence was used. Similarly,
the fresh dependency test compares dependency maps and header names, not the resolved
runtime-object identities. The linker/build scripts are outside those header graphs.

These fixtures preserve the current real binary, ELF and compilation inputs. They prove
that an incorrect compiler/library identity or a missing critical script pin can receive
a successful provenance verdict. Merely updating a path and its hash together must not
allow a different file to assume the role of the actual build input.

### Required correction

Derive the trusted build description from the selected repository/build configuration,
then compare the evidence to that description:

1. Require the complete build-input inventory, including the build script and linker
   script. The existing `APP_SOURCES` inventory already includes both. Do not let the
   evidence's lists decide which critical source entries are mandatory.
2. Resolve the compiler from the same configuration used by `build.sh`. Compare the
   evidence's compiler identity with that resolved file, rather than simply opening a
   path supplied by the evidence. Use the trusted compiler for any discovery commands.
3. Resolve each of the seven runtime objects with that compiler's `-print-file-name`
   under the build's Cortex-A9/hard-float flags. Require each recorded role to match its
   actual resolved input and hash. Canonical path aliases may be handled explicitly;
   substituting another library with a self-consistent hash must fail.
4. Add negative coverage for the four fixtures above through the real consumer checks.
   Keep the already passing omission, changed-hash and dependency-graph tests.

The expected translation-unit set in `verify_findings()` is also computed from the
evidence's lists/roots. The full fresh-dependency test currently provides an independent
check on those units. When this verifier is wired into the future production package
validator, retain that independent comparison; `verify_findings() == []` alone is not
currently equivalent to all the `Committed` checks passing.

## 3. Current image and evidence: independently consistent

The reviewer reran dependency discovery and compared the complete freshly generated
`bsp_inputs` object with the submitted one, including the new dependency map and runtime
entries. They are equal. All source hashes match both current files and files committed
at the evidence's source HEAD, `6cfa8564a2f6b80111f34ae2456be90e1eaf0394`.

| Item | Verified value |
|---|---|
| Binary | `d164cd1d5b30aa5eb91f230b1373be8dda60d219249924e280957b26348d85f5`, 114,708 bytes |
| ELF | `7de96ed25e01199ad4405dcc59b2ec92140c27679710e6acfbbad158e4986cdc` |
| Recorded two-build digests | Both binary and ELF entries agree with each other and the actual outputs |
| Build inputs | 47 translation units, 86 headers, seven runtime objects/libraries |
| B1 | 105 pins verify; manifest `38238271510536bda565ad1b8321dd04d75e78e1fe77ef94d2795bf9edfd4ba8` |

No firmware changed in this batch. The review did not rebuild the ARM image or repeat
the unchanged application startup review. No new image is required by this host-verifier
finding alone.

## 4. Test result and artifacts

The independent focused suite is **186 tests, OK, zero skips, 302.832 seconds**.
The checkout remained clean through completion; review files were written afterward.

The total comprises the reported 186 source-defined B2/B3 tests, including 21 build-evidence
tests. This review does not certify the separately running/reported full repository suite.

Artifacts in `evidence/b2/review_build_guard_2026_09_10/` include the reproducible probe,
its old/new counterexample results, live build checks, focused test log and per-module
test counts. The probe changes only in-memory evidence fixtures and temporary stand-in
bytes. It runs the actual consumer test bodies with class fixture loading redirected to
those objects; the real compiler dependency check remains enabled.

Review documents and artifacts are the only repository changes made here. No firmware,
image, manifest, pin, instrument file, ruling, board, commit or push was changed.

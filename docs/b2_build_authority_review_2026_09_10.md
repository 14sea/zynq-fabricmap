# B2 build-input authority correction review — 2026-09-10

Reviewed HEAD: `fb37ee0c32efc19aa2b2c41fe575df954c64e7ea`, nineteen commits ahead
of local `origin/main = b951b80`. The checkout was clean at review start.

**The previous input-role and mandatory-inventory findings are corrected. One new P2
in the runtime hash cache prevents closure of the build-guard review.** The submitted
image and current real build inputs remain consistent. The new finding requires a host
verification correction, not a firmware change or replacement image.

## 1. Previous findings: verified corrected

The previous `reproduce_guard.py` was run unchanged. Both unmodified baselines pass.
The ten earlier negative cases (seven counterexamples and three controls) are refused.
The four input-authority cases now fail both `verify_findings()` and the current six
`Committed` tests: the fake compiler, `libm.a` in `libc.a`'s role, omitted linker script
and omitted build script. The internally consistent empty dependency-graph control
still fails the fresh dependency test, as intended.

The verifier now checks the compiler selected by the build configuration, resolves each
runtime role under the Cortex-A9 hard-float flags, and requires the module's complete
source inventory. An additional positive check replaced the seven recorded runtime
paths with symlinks to those same files: `verify_findings()` accepted all seven canonical
aliases. No alias target or toolchain file was changed.

## 2. P2: cached runtime hashes hide subsequent deletion or modification

`host/b2_build_evidence.py:157` introduces `resolved_runtime_objects()` with a process-global
`_RESOLVED_RUNTIME` cache. At lines 162–169 it hashes each runtime file once and stores
both its path and hash. Later calls at lines 273–285 compare evidence with that stored
hash without checking whether the resolved file still exists or hashing its current bytes.
The path comparison still succeeds when both sides name the same now-missing path.

The result depends on whether the process has already verified evidence. A previously
valid object can be deleted or changed, yet the next verification still returns no
findings. The compiler itself is rehashed, but this does not detect changes to its
separate runtime objects/libraries.

The independent reproducer uses real copies of the seven runtime files in a temporary
directory. A narrowly scoped toolchain double redirects only `-print-file-name` results
to those copies; all hashing, caching, verification and submitted test bodies execute
unchanged. Other compiler calls, including `-M`, still run normally. It never writes
the repository's image, firmware, original evidence or instrument/toolchain files.

| Temporary `crti.o` state | Verifier | All six `Committed` tests |
|---|---|---|
| Original copied bytes, initial validation | No findings | PASS |
| One byte changed, same size, after initial validation | **No findings** | **PASS** |
| Deleted after initial validation | **No findings** | **PASS** |

After clearing `_RESOLVED_RUNTIME`, the same altered evidence/environment is correctly
refused: a hash mismatch for the overwrite and unresolved runtime object for deletion.
Each mutation case has its own valid baseline. This isolates the failure to cached state.

The new runtime-object test also calls `resolved_runtime_objects()` and compares against
its cached hashes. It therefore shares this blind spot. The fresh-dependency test does
not compare runtime hashes from its fresh `bsp_inputs()` result, so it does not rescue
these cases.

### Required correction

Check the current existence and bytes of every resolved runtime file on every verification.
The simplest correction is to remove the cross-call runtime result cache and resolve/hash
the seven objects afresh. If any resolution metadata is cached, it must not substitute
for live file checks or retain authority after its build configuration changes.

Add sequential negative tests: a valid baseline first warms the normal verifier, then
the same process verifies unchanged evidence after a same-size overwrite or deletion.
Both must refuse without the test clearing private cache state. Retain the role-substitution,
required-source and canonical-alias coverage. A fresh-process test alone does not exercise
this defect.

## 3. Current image and build evidence

The unchanged independent `verify_current_build.py` succeeds. Its comparison covers the
actual build configuration, complete source inventory, compiler identity, freshly derived
dependency/runtime records, source bytes at the evidence's recorded commit, and outputs.

- Binary: `d164cd1d5b30aa5eb91f230b1373be8dda60d219249924e280957b26348d85f5`, 114,708 bytes.
- ELF: `7de96ed25e01199ad4405dcc59b2ec92140c27679710e6acfbbad158e4986cdc`.
- Both recorded build-output pairs match those files. No ARM rebuild was performed here.
- Evidence source HEAD remains `6cfa8564a2f6b80111f34ae2456be90e1eaf0394`; firmware and
  build evidence are unchanged by this correction batch.
- B1's 105 pins verify; manifest remains
  `38238271510536bda565ad1b8321dd04d75e78e1fe77ef94d2795bf9edfd4ba8`.

## 4. Test result and scope

The independent focused suite is **193 tests, OK, zero skips, 298.937 seconds**.
The build-evidence module contributes 28 tests. The checkout was still clean when
this run finished; review artifacts were written afterward.

The previous full-suite result of 1,642 tests at `9c1f3ca` is the submitter's report;
this review does not repeat or certify that full-suite run. The five remaining host
tools still precede submission of the complete §7 package. No completed-image clearance,
push, freeze, ruling or board action is granted by this review. Host development can
continue while the cache defect is corrected.

Artifacts are under `evidence/b2/review_build_authority_2026_09_10/`: previous-counterexample
results, independent live-build checks, the cache reproducer and output, canonical-alias
check, focused test log and test counts. Review docs/artifacts are the only repository
changes made here; no production input, instrument file, commit or push was changed.

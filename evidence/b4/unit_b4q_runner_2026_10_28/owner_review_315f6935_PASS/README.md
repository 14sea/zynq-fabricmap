# Owner review — runner repair — 315f6935 — conditional PASS with an approved follow-up

Reviewed `315f69351c528fdaaf628ad9b6e7cd3c938c3539`, implementation `bcfc6fbf`, after the R1–R2 HOLD on `6eeacfc2`.

**R1 and the PLL qualification repair are accepted.** One narrower P2 prefix defect remains on the bare tip. The owner has supplied and tested its minimal two-file fix, so this does not require another open-ended HOLD/repair/review round. The actionable disposition is **[RULING.md](RULING.md)**: apply the exact approved patch, confirm the repaired hashes, archive and close.

## Independent verification of the submitted tree

Canonical tracked files and branch tips were not changed. All tests ran in `/tmp/owner_b4q_runner_round4_l_e4zhxw`, with copied, hashed dependencies in `snapshot.json`. No device/UART/SSH contact, physical PCAP, key provisioning, production seed derivation, commit, push or merge.

- Bench prerequisite: **1 test OK**, accepted netlist copied rather than re-synthesised.
- Nine-module B4Q suite: **126 tests OK, exit 0**, 407.657 seconds.
- Its setup independently regenerated **47 runner scenarios**, zero expectation failures and **47 fresh verifier agrees**; **19 PS-source console scenarios**, **19 fresh verifier agrees**. The emulated valid control and ordinary module regressions also ran; no separate full 19-case emulated rerun is claimed.
- Independent role/clock checks: 18 eligibility cases against explicit expected outcomes, five context widening attempts rejected, verify/sacrificial positives and narrowed-role/power-down refusals. See `role_clock_checks.py/.json`. This validates the configured nominal/selected-PLL predicate, not physical clock presence or frequency.
- IMPORT: **59 + 37 hashes match**. Protected paths unchanged against `e34432ea`; no firmware changes since `dad9e4de`. Reused the exact previously independently reproduced `4d989ee84757f60965d2a43da9c61981366893423e3b96bd559b575edf07da5b` image; no redundant image rebuild.
- The author's 67-mutant record was inspected, not independently rerun. No unrelated frozen whole-project battery was requested.

## Accepted repairs

The role policy is now a fixed floor independently enforced by context construction, runtime admission and verifier; a caller can narrow it but cannot admit reference/missing roles by widening its own list. The selected-source clock checker now records the six required PS words and considers reset, power-down, active or qualified bypass, and the selected PLL lock. A missing word is ineligible. The submitted tests exercise the new negative paths without issuing a PL read.

The verifier now catches a selected PLL command/reply moved after the PL read and a sent command order inconsistent with its echoes. The runtime already obtains the prerequisites in the correct sequential order. The remaining issue is solely where the verifier cuts its receive-side prefix.

The terminal-END race repair from the preceding round, immutable admitted image bytes, pre-go persistence barrier, accepted-TX-byte accounting, required versioned runner source, raw-frame accounting and prior state/address checks are not reopened by this review. Physical-source fixtures remain explicitly synthetic and observed_on_device=false; no qualification follows from their consistency.

## Remaining P2 and exact fix

`first_pl_reply_offset()` originally cuts before the first PL **data reply**, rather than before the command starts being handled. If a PS/identity reply appears after the VARIANT command echo but before VARIANT's returned data, it still qualifies as a prior input. Command ordering remains unchanged, so the new echo-order guard does not catch it.

`prefix_probe.py` reconstructs two such copied raw streams, refreshes their commitments and runs a fresh CLI verifier. No raw bytes of canonical evidence are changed. Outcomes:

| case | submitted 315f6935 | exact approved follow-up |
|---|---|---|
| proper prefix | exit 0, clean/agree true | exit 0, clean/agree true |
| IO PLL reply moved after VARIANT command echo but before its data | **exit 0, clean/agree true** | exit 1, clock/state findings |
| role reply moved into the same window | **exit 0, clean/agree true** | exit 1, identity/state findings |

The incorrect archives are internally contradictory to the declared synchronous reader: the prerequisite arrives while the PL command is already being handled. This is a verifier P2; it is not evidence that the corrected runtime issued a bad physical operation.

`owner_followup.patch` changes only:

- `host/b4q_verify_runner.py`: choose the earliest received PL command echo **or** PL data reply as the boundary. The existing helper name is retained for compatibility; the docstring explains the semantics.
- `tests/test_b4q_runner.py`: one regression method with both delayed-reply negatives and a proper-prefix positive, appended to `StateMachineRound3`.

Active documentation referring to the first PL reply alone should be clarified in the routine closure update. Historical descriptions/results can remain with a superseding note. No unrelated rewrite is required.

## Validation of the exact follow-up

A **separate** disposable root `/tmp/owner_b4q_runner_followup_pbz_ca_j` holds the patched candidate, so the submitted-tree suite was never run against files being edited.

- `git apply --check` succeeded on the untouched reviewed root.
- Four focused `StateMachineRound3` tests passed, including the new method (`focused_followup_tests.txt`). For this focused run, the submitted module's expensive setup was replaced only in the owner driver with the retained runner fixture root; these tests consume copied archives and invoke fresh verifiers, not native application execution. The actual test source remains part of the approved patch.
- **All 47 retained runner archives fresh-verified agree** on the patched candidate (`followup_archive_checks.json/.txt`). The checker makes no changes to those archives. Reports are hashed in the summary; their temporary report paths are not an extra authority.
- Both newly delayed-reply negatives are now rejected and the proper-prefix control stays clean (`after_followup/`).
- `verify_approved_followup.py` passed: the two repaired hashes match; IMPORT 59/37 match; only the two approved code/test paths differ; code whitespace clean; image hash unchanged (`verify_approved_followup.json`).

This is **126 tests on the submitted tree, four focused tests plus 47 fresh archive checks on the approved candidate**. It is not a full 127-test run, nor a repeated 67-mutant battery. The targeted checks cover the sole new helper change; another unchanged full assembly is not required for the exact-byte follow-up.

## Applying and closing

Use the clean reviewed code or a docs-only descendant with matching before hashes. Apply `owner_followup.patch`, run `verify_approved_followup.py <repo-root>` from this directory, retain its output and archive the review/closure. `approved_file_hashes.json` records both input and repaired hashes; the ephemeral owner `root` field is provenance only and is not a required local path.

Only the exact two-file candidate has this no-further-round acceptance. Closure documentation is separately authorised by the ruling. No fixed commit count or branch name is imposed. Prior evidence remains tied to its actual code head; archive the new owner validation rather than relabelling earlier tests as run on the follow-up.

The PASS is host-only engineering acceptance, not physical readiness or an execution authorisation. The outstanding P4/P5/P6 and stopped scientific route are unchanged; publication and hardware work are not bundled.

## Package

- `RULING.md`: operative conditional acceptance and exact follow-up/closure authority.
- `owner_followup.patch`, `approved_file_hashes.json`, `verify_approved_followup.py/.json`: concrete candidate and its verification.
- `prefix_probe.py`, `prefix_probe.json`, original three CLI reports and `after_followup/`: defect/control and repaired outcomes.
- `focused_followup_tests.py/.txt`, `check_followup_archives.py`, `followup_archive_checks.json/.txt`: focused repaired-candidate validation.
- `tests.txt`, `bench_prerequisite.txt`, `independent_e2e_summary.json`, `role_clock_checks.py/.json`, `integrity_checks.json`, `snapshot.json`, `review_metadata.json`: submitted-tree independent checks and scope.

Scripts take an explicit disposable repo root. No probe opens a real device or derives a production seed. No duplicate raw fixture archives are copied into this package. SHA256SUMS covers every other file here.

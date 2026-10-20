# The owner's review of b49b2ec (2026-10-19), as relayed by the user (build/wip/owner_review_b49b2ec_2026_10_19/README.md; its raw probe artifacts stay in that ignored directory)

# Owner review of b49b2ec — gate-tool numerical corrections

Reviewed commits: `6431e9f` and `b49b2ec0678f456792ad201956f509e7877877f8`.
Review base: `a8f2da1`. No product file or branch ref was changed by this review.

**Decision: HOLD for one remaining P2 (derived arithmetic) and one P3 wording correction.**
The Cohen's d magnitude/sample-variance fix, previous exact-type cases, and the earlier R3/D1 corrections are accepted.
Finish the residual work within this unit and submit one complete batch. Production gate execution, new production seed
derivation, new exploration, RTL, 2d, routing, push and merge remain outside this authorization.

## 1. P2: finite inputs can still overflow inside validation

Location: `b4/host/b4_gate.py`, `_ratio_findings`, `implied_cohen_d` and `_stat_findings`.

The numeric pre-pass now rejects the prior huge-integer and non-finite-input probes correctly. However, finite input values
do not guarantee finite results of arithmetic. The validator's advertised totality must also cover intermediate results.

### 1a. Ratio recomputation escapes as ValueError

`1e308` and `5e-324` are finite floats accepted by `numeric_findings`. Their quotient overflows to positive infinity.
`_ratio_findings` then calls `sc.canonical(want)` with that derived infinity, raising:

`ValueError: Out of range float values are not JSON compliant: inf`.

The direct helper reproduction is in `arithmetic_probe.py`. The `finite_ratio_overflow` case in `probes.py` carries these
values through an otherwise schema-shaped, finite synthetic summary. **The summary contract, pure judge and synthetic writer
all raise the same exception**, instead of returning a named finding / invalid judgement or a named pre-write refusal.
See `probes_results.json` and `probes_stdout.txt`.

These enormous values are not plausible task scores and are not evidence of a production gate forgery. That is precisely why
the malformed evidence must be rejected by a contract finding rather than escaping the validation boundary. No requirement
to accept these numbers as model statistics is implied.

### 1b. An overflowing implied d can make the magnitude check accept any finite d

With finite `mean=1e308`, `population_variance=5e-324`, `S=200`, `implied_cohen_d` returns an infinite value with special=null.
Passing recorded finite d **-0.9** into `_stat_findings` yields **no findings**, although its sign is opposite to that mean.
The comparison reduces to `inf > inf`, which is false:

`abs(v - w) > D_REL_TOL * max(1.0, abs(w))` with `w=inf`.

`arithmetic_probe_results.json` records that the input numeric pre-pass is empty, the implied value is not finite, and the
statistic validator returns `[]`. This is a helper-level reproduction, not a demonstrated production archive or formal PASS.
It illustrates why checking only the original JSON values is insufficient even after the missing d formula was added.

Required correction:

- Guard the **derived** ratio/statistic results and any overflow/underflow/serialization boundary before using them for
  comparison. Either reject out-of-contract source ranges before arithmetic or perform numerically safe arithmetic and
  reject unrepresentable results with named findings. Preserve the frozen statistic and its legitimate zero-variance special cases.
- Never allow a non-finite intermediate to turn a malformed summary into an accepted statistic or an uncaught exception.
  `_same` catches serialization errors, but `_ratio_findings` still directly serializes its unchecked derived record.
- Add finite-extreme input cases, including both of the actual paths above, and carry the ratio case through validator,
  judge and artifact boundary. Verify that a kept PASS report with refreshed hashes/markdown is rejected. Retain the old
  input-pre-pass, exact-type and production-statistic checks.

This is a completion of the current numerical/totality repair, not a request to modify the model, task distribution, thresholds
or statistical method. Do not modify the old exploration archive to satisfy the new check.

## 2. P3: the tolerance is not smaller than every difference a criterion can notice

Locations: the `D_REL_TOL` comment in `b4/host/b4_gate.py` and the magnitude-binding row of the unit README section 9.1.

The empirical measurement is independently confirmed: **140 archived delta records, maximum absolute discrepancy
2.220446049250313e-16** (`archived_cohen_check.json`). The sample-variance formula and previous ordinary boundary are correct.
The use of a documented 1e-12 consistency tolerance (with floor 1) is accepted for this check. It does not authorize changing
the frozen K5 threshold or replacing the production statistic with a new one.

However, the claim that this tolerance is "eleven [orders] below any difference a criterion could notice" is false.
A threshold comparison is discontinuous at its boundary; there is no general minimum such difference.

Independent example (`tolerance_crosses_K5`): mean=1, population variance=3.98, S=200 implies d=0.5. The concrete integer
delta sequence `[20, -18, 7, -5, 2, 0] + [1] * 194` has exactly those statistics and production d=0.5
(`arithmetic_probe_results.json`). The original synthetic judgement PASSes. Changing both recorded d copies to
`0.5 - 5e-13` is within the accepted tolerance, produces no contract finding, and changes K5 and the overall verdict to FAIL.
The resulting synthetic report verifies clean in a fresh process.

This **does not establish a wrong formal production verdict**: the production path separately recomputes the raw archive,
which binds the recorded d to the actual delta sequence. It establishes a limit of the tolerant summary-only consistency
check. Correct the comment/README to say:

- the archived comparison measured rounding discrepancies on those records, not every possible future record;
- the tolerance applies to consistency validation, not to the K5 threshold;
- near a decision boundary, accepted summary perturbations within that tolerance can change a synthetic judgement;
  production source authenticity and exact replay/recomputation remain separate requirements.

Do not respond by tuning the threshold, silently adding epsilon to K5, or changing the frozen production method.
Keep the recorded-value decision rule and disclose the validation limit honestly.

## 3. Accepted work and evidence

- The previous six shape/consistency probes, the five exact-type aliases, the huge JSON integer and the coordinated false d
  now all produce named invalid judgements. Non-serializable synthetic input is refused before writing, as specified.
- The finite d magnitude now follows the production sample-standard-deviation convention. The previous mean=1,
  population variance=4, S=200 boundary gives 0.49874843358150006 on the FAIL side.
- R3 mixed-registry handling and D1 preregistration skeleton remain accepted; no reopening of those corrections.
- G33/G35 relocation is acceptable evidence maintenance; keep the original EDIT-MISS records. G29 remains the accepted
  equivalent survivor. Independent focused mutant rerun and full-suite results are recorded in `validation_summary.json`.
- IMPORT/scope: **52 entries**, 78 distinct file/source digest checks, no mismatch or unregistered file; old pinned surfaces,
  architecture/thresholds, hypothesis/model, engine, seed loader, production statistics/harness and S=32 archive are unchanged.
  See `scope_import_check.json`.

## 4. Independent review artifacts

- `snapshot.json`: exact reviewed HEAD and extracted /tmp source; `suite_guard.py`, `tests.txt`: **282 tests OK, zero skips**, exit 0, 493.539 seconds;
  production-master derivation guard calls `[]`. `validation_summary.json` records the completed exit/count/time.
- `focused_mutants.txt`: **5/5 killed**, G33, G35, G37–G39, exit 0, 496 seconds, on hermetic roots;
  the supplied full battery logs were inspected, not claimed
  as another independent full rerun.
- `verify_archives.py`, `archive_verification.json` and raw outputs: **32/32 expected exits** in fresh processes: five normal e2e cases,
  fourteen negatives, twelve invalid controls, and the unchanged S=32 archive. Two refusal controls intentionally have no
  gate directory and are checked as such, rather than passed to an archive verifier.
- `probes.py`, `probes_results.json`, `probes_stdout.txt`: previous cases and the two new whole-summary probes.
- `arithmetic_probe.py` / results: small direct reproductions and the exact d=0.5 integer sequence.
- `archived_cohen_check.json`: independent 140-record rounding audit.
- `probe_archives/`: preserved generated mechanics/synthetic probe artifacts.
- `review_setup_attempts/`: the first review driver incorrectly assumed all invalid controls produced gate directories;
  that setup error was corrected before the verifier run. An attempted detached suite subprocess did not survive the tool
  sandbox; the actual suite ran in a managed session. These are review setup errors, not product findings.

No production gate, new production seed set or new exploration was run. Only /tmp fixtures and this ignored review directory
were written. Finish the residual arithmetic repair and the wording correction, refresh IMPORT, validate the final clean tree
and fresh-process negatives, and submit one complete batch for review.

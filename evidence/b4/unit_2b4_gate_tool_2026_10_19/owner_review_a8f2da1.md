# The owner's review of a8f2da1 (2026-10-19), as relayed by the user (build/wip/owner_review_a8f2da1_2026_10_19/README.md; its raw probe artifacts stay in that ignored directory)

# Owner review of a8f2da1 — B4 gate-tool HOLD corrections

Reviewed commits: `77a6c8cf55ab5b6d285d1700c5f92dc3b7dfe015` and
`a8f2da191d166eea8095220f649b0db3665d870b`. Base: `4cdc0c1`.

**Decision: HOLD on two residual P2 workstreams.** The original six concrete probes now produce invalid judgements;
R3 (registry test states) and D1 (the lifecycle description) are accepted. R1/R2 are substantially improved but their
broader advertised contracts still have the failures below. These are corrections within the same tool unit, not a
new scientific method or permission to run the production gate. Fix the two workstreams together and submit one batch.

## 1. P2 — Cohen's d is bound only by sign, not by magnitude

Locations: `b4/host/b4_gate.py:168` (`_stat_findings`), `b4/tests/test_b4_gate.py:63` (`_delta`).
For a positive population variance, `_stat_findings` checks that d is finite and has the mean's sign. It does not verify
the value implied by mean, variance and S. Binding the at-B* copy to the per-budget copy cannot close a coordinated edit.

Independent reproduction (`probes.py`, case `coordinated_false_cohen_pass`):

- Start with a synthetic summary whose primary mean is 0.5, population variance is 4, and S is 200; the other rows PASS.
  Its original K5 FAILS and its overall verdict is FAIL.
- Change **only both copies** of the selected budget's d to `{value: 0.9, special: null}`.
- The contract findings remain `[]`; K5 and the overall verdict become PASS. The writer succeeds and a fresh-process
  verifier returns exit 0, findings `{}`, `clean: true`.
- The declared primitive quantities instead imply d = **0.24937421679075003** under the production method.

All these artifacts remain `formal=false`. No forgery of a production archive was demonstrated; the production raw-data
recomputation is a separate boundary. The defect is in the same accepted synthetic judge/verification contract as the
previous review: two mutually consistent copies are not an authority for the quantity they represent.

There is also a fixture formula error: `_delta` currently sets d to `mean / sqrt(population_variance)`, while the frozen
`b4_gate_stats.cohen_d` uses `statistics.stdev`, the **sample** standard deviation. For S >= 2 and positive population
variance, the implied value is:

`mean / sqrt(population_variance * S / (S - 1))`.

This matters at the boundary: S=200, mean=1, population variance=4 gives fixture d=0.5 but production d approximately
0.49874843358150006. The fixture therefore places a value below the frozen K5 threshold on its passing side.
`cohen_formula_check.json` also checks a concrete 200-value delta sequence against the unchanged production function.

Required correction:

- Recompute and bind the finite d magnitude using the production sample-variance convention and a documented numerical
  comparison that does not conceal a criterion change. Preserve the production S<2 and zero-variance special cases.
- Correct the synthetic fixture calculation and its boundary expectations. Do not change the frozen production statistic,
  threshold or exploration archive to accommodate the fixture.
- Add a coordinated two-copy edit negative that fails specifically on this binding, plus independent numerical expectations
  covering the sample/population distinction and the K5 boundary. Carry the negative through refreshed hashes/markdown and
  a fresh verifier. A test of sign or copy equality alone does not hold this contract.

## 2. P2 — totality and exact-type validation are still incomplete

Locations: `b4/host/b4_gate.py:137` (`_fin`), `:217` (`_scan_findings`), and the at-B*/K10 bindings in
`summary_contract_findings`.

### Totality

The JSON integer `10**400` is a valid decoded JSON value within Python's normal integer-string limit. Putting it at
`per_budget[64].k1.omega_best_p95` raises **OverflowError: int too large to convert to float** in `_fin`'s `math.isfinite`.
The contract validator, judge and synthetic writer all raise instead of returning a named finding / invalid judgement.
See the `huge_json_integer` probe. This extends the original arbitrary-JSON totality requirement; it is not a request
to accept the number as a valid model statistic. Reject it by the applicable numeric contract without escaping.

Likewise, decoding JSON numeric literal `1e400` produces an infinite float in the current Python decoder. Putting that value
inside `thresholds_for_reference.K10.tau` makes the contract and judge raise **ValueError** from `sc.canonical` before a
finding is returned. `nonfinite_probe.py` and its JSON result reproduce this second numeric edge. Non-finite and out-of-range
values must be rejected before canonical serialization or arithmetic, rather than relying on the serializer to throw.

### Exact types

Several copy/constant bindings use Python `==` / `!=` rather than an exact-type check. The following isolated changes
all pass the contract, receive a PASS judgement and verify clean in a fresh process:

| case | change |
|---|---|
| `float_scan_n_min` | `required_pairs.n_min`: 8 -> 8.0 |
| `float_bootstrap_seed` | `at_candidate_B_star.k2.bootstrap.seed`: 7 -> 7.0 |
| `float_k10_tau` | `k10.tau`: 2 -> 2.0 |
| `float_at_k5_N` | `at_candidate_B_star.k5.N`: 16 -> 16.0 |
| `float_at_k7_values` | at-B* K7 address counts: integer 15 -> floating 15.0 |

These are the same integer/count/seed fields whose exact representations are promised by the schema and the correction.
The existing fuzz uses 1.5 as its float, which differs numerically from these values and therefore does not exercise the
equality alias. No scientific benefit or production formal promotion is claimed from the aliases; the problem is accepting
invalid evidence as a valid judgement rather than enforcing the declared typed contract.

Required correction: finish the explicit type checks for all typed fields and redundant copies/constants, and make numeric
validation total before any conversion/arithmetic. Keep legitimate finite floating statistics allowed where specified.
Add tests using **numerically equal foreign types**, not just a numerically different float: int/float and bool/int aliases
where applicable, in both originals and redundant fields. Include large decoded integers and other numeric boundary cases
in totality testing. Require named invalid findings before judgement and fresh-verifier rejection of a kept PASS report
after all hashes and markdown are refreshed.

## 3. Accepted corrections and evidence handling

- Original six probes: D_over_F null, B* float, empty N scan, contradictory d copies, malformed +inf, K9 fraction 2.0:
  all independently reproduced as named invalid judgements; the invalid reports themselves verify clean as intended.
- R3: the independent prior mixed-root reproduction now passes both historical-source tests; the newly added mixed-registry
  regression covers `seeds`, `seeds_fixture`, `init_failed_no_seeds`, membership, hashes and pooled union. The loader is unchanged.
- D1: `docs/b4_preregistration.md` v0.0.2 correctly distinguishes B3 S0 init / S1 freeze / S2 qualify / S3 plan and leaves B4's
  lifecycle contract unresolved. This document correction is accepted; it does not freeze a preregistration.
- G21's stale battery name/target is an evidence-script error, disclosed and corrected. The focused independent rerun uses
  the corrected script. Keep the initial non-green baseline log; do not rewrite it into a successful kill.
- G29 remains the previously accepted equivalent survivor. No new demand to manufacture a kill.

## 4. Independent validation artifacts

Review snapshot and identity: `snapshot.json`; all code execution uses the reviewed committed source extracted into /tmp.
No production gate or new production seed derivation was performed. Mechanics/synthetic schedules only; derivation guards
remain active. No product file, branch ref, old pinned input, original exploration file or receipt was changed.

- Full regression: **280 tests OK, zero skips**, exit 0, 377.472 seconds; outer production derivation guard calls `[]`.
  See `tests.txt`, `suite_guard.py`, `validation_summary.json`.
- Focused mutants: **7/7 killed**, G21 and G31–G36, `focused_mutants.txt`. The author's complete 36-mutant logs were inspected, not represented
  as another independent full battery rerun.
- Fresh-process verification: **18/18 expected exits** — the five positive archived cases, six refreshed-hash negatives, six invalid controls, and
  the unchanged S=32 archive: `archive_verification.json`, `verify_archives.py` and each raw stdout/stderr file.
- IMPORT/scope: `scope_import_check.json`: 52 entries; 78 distinct file/source digest checks; no mismatch, no unregistered
  B4 file, no protected-surface change. Architecture, thresholds, hypothesis/model, engine, landscape and seed loader unchanged.
- New negative artifacts: `probe_archives/`; exact scripts/results: `probes.py`, `probes_results.json`, `probes_stdout.txt`.
- Registry acceptance recheck: `registry_probe.py`, `registry_probe_results.json`, raw output.

Finish both residual workstreams within this unit, correct the accompanying descriptions of what is actually validated,
refresh IMPORT, and validate the completed clean tree and negative artifacts before one batch review. Keep the accepted R3/D1
corrections and all prior evidence. Production gate, new exploration, RTL, 2d, routing, push and merge remain outside this scope.

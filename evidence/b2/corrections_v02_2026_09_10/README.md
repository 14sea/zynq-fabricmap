# Corrections to the B2 manifest lifecycle after the owner's second review (2026-09-10)

`reproduce_lifecycle_patched.py` is the owner's `evidence/b2/review_v02_2026_09_10/reproduce_lifecycle.py`
with three mechanical changes so it can run against the corrected code: the repo root is
absolute, `pin_plan` is given the same fixed test double as `qualify` (the corrected
`pin_plan` verifies the manifest first and refuses without a re-adjudicator, which is the
intended CLI behaviour), and the plan-pinning probes are wrapped so a refusal is recorded
instead of aborting the script. `lifecycle_after.json` is its output: the three baselines
(S2, S3, the faithful mirror) are accepted; every counterexample is refused; the slow rate
is INFEASIBLE; invalid rates raise `RateInvalid`. The full set of cases, including the
ones the owner's script does not probe (a wrong prediction file with its digest updated,
the one-pair boundary, string / bool rates, a record with an extra file entry), is in
`tests/test_b2_lifecycle.py` and `tests/test_b2_plan.py`.

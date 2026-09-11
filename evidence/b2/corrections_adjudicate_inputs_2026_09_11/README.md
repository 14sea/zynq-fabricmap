# The adjudicator's input-validation P2 — acceptance, 2026-09-11

The owner's input review (`docs/b2_adjudicate_input_review_2026_09_11.md`, against `da89506`)
closed the baseline P2 and the planning-scenario P3 and left the input-validation P2 open on
three gaps. All three are corrected in `host/b2_adjudicate.py`.

`review_input_guards_after.json` is the owner's own `reproduce_input_guards.py`, **unchanged**,
re-run with common validation enabled; `previous_review_cases_after.json` is the previous
round's `reproduce_adjudicate.py`, also unchanged, confirming nothing regressed.

| the review's case | before | now |
|---|---|---|
| `fitness` = `[]`, `{}`, `["F1"]`, `{"name":"F1"}` | `TypeError` (hashed before typed) | REFUSED — the plan's fitness … is not a string |
| `fitness = "F9"` (control) | REFUSED | unchanged |
| the CLI with `fitness=[]` and `--out` | exit **3**, INTERNAL ERROR | exit **1**, `REFUSED: the plan's fitness [] is not a string`, no `internal_error` |
| prediction `budget_per_arm` = `12.0` | PASS | REFUSED — is not the plan's (12) |
| pair 0 A `best_train` = `2.0` | PASS | REFUSED — is not an integer |
| pair 0 A `column_moves` = `false` | PASS | REFUSED — is not an integer |
| primary `positives` = `true` | PASS | REFUSED — is not a count |
| primary `ties` = `2.0` | PASS | REFUSED — is not a count |
| a contradictory duplicate pair 0 prepended | PASS, silently overwritten | REFUSED — pair identities are [0, 0, 1, 2], not 0..2 exactly once in order |
| a pair whose id equals `plan.pairs` appended | PASS, never visited | REFUSED — pair identities are [0, 1, 2, 3], not 0..2 exactly once in order |
| master seed + `2**32`, identity synced | PASS | REFUSED — outside 0..2\*\*32-1 (Rng masks to 32 bits, so it would replay another number's stream) |
| map digest `not-a-digest`, identity synced | PASS | REFUSED — is not 64 lower-case hex |
| positive control | PASS | PASS |

## How each was corrected

- **A.** `check_plan` establishes that `fitness` is a **string before** the membership lookup;
  every other consumed field follows the same ordering (type, then domain, then use).
- **B.** `check_prediction` types each consumed value — the three run counts, the two run
  digests, the three primary counts, `sign_test_p`/`alpha` as probabilities, the verdict as a
  string — so Python's numeric equality can no longer accept a boolean or a float for a count
  this module reports as EXACT. Pair identities must equal `0..pairs-1` exactly once **in
  order, established before any lookup is built from them**. Domains are checked too:
  `best_train` within the fitness ceiling, `champion_holdout` within the holdout ceiling,
  `column_moves` within the budget. The document must also account for itself: each delta is
  its own B−A, the deltas number the pairs, the primary counts sum to the pairs, and
  `predicted_primary` is the sign test over its own deltas. The sequence digest is 64 hex and
  its length is the `pairs × (2×budget + 2)` the experiment produces.
- **C.** `check_plan` checks the plan's domains: `master_seed` in `0..2**32-1` and the map
  `sha256` 64 lower-case hex; `pairs` must also fit the identity page's 1..16 slice field.

## One deliberate consequence, stated

The review's own numeric negative control — pair 0 A `best_train = 999` — is now **REFUSED**
rather than HOLD, because 999 is outside F1's ceiling of 40 and so is not a value this
prediction could hold. The distinction the review asked to preserve is kept and tested with an
**in-domain** disagreement instead: `test_a_valid_prediction_that_merely_disagrees_is_a_finding_not_a_refusal`
raises `best_train` by one and re-derives the document's own accounting, and that is a HOLD
naming `best_train`, not a refusal. If the reviewer prefers the out-of-domain value to stay a
HOLD, the domain checks are the thing to drop, and that is the owner's call.

## Tests

70 adjudicator tests (was 57); the B2/B3 suite is **315, zero skips**. The new cases are the
review's table one by one through the public API, plus the digests, the domains, a missing
pair, out-of-order pairs, the self-accounting checks, and the CLI case proving an input error
never takes the internal-error path. Reverting only `host/b2_adjudicate.py` to `da89506`
fails 42 sub-cases and 1 error across those two classes.

The full-size demonstration was regenerated with the corrected module: PASS, 10 818 records
replayed, `0b81b343…`, p = 0.01953125; the one-word tamper still a KILL with no primary. The
model stands in for a board there — not silicon evidence.

None of this is `b2_manifest.verify` or the pin chain; those remain this module's declared
exclusions under `not_checked_here`.

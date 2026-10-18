# B4 pre-work, unit 2b-3 — the gate's thresholds, τ, the incomplete-run policy and the seed anchor (2026-10-18)

**Authorised by** the owner's PASS on `b2a958c` and the full ruling archived here as
`owner_ruling_2b3_full_2026_10_18.md`. **Documents only:** `docs/b4_architecture.md` (DRAFT v0.1.13)
and this directory. Nothing under `b4/` changed; no test, no model run, no landscape exploration, no
seed value generated, no K result computed. Verification is `git diff --check` plus the citation and
digest checks in `checks.txt`.

**Standing, as the ruling states it:** these are engineering research criteria fixed in advance. No
number here is claimed to be empirically guaranteed, statistically calibrated or valid for silicon;
a criterion that fails on valid complete data is reported as a failure. **This commit is not a
gate-readiness verdict.** The formal hypothesis stays v0.3 / unverified and A8 unresolved.

## Where each number lives, and why it is that number

| criterion | fixed as | reason |
|---|---|---|
| grid, `B_max` | `{8, 16, 24, 32, 48, 64, 96, 128, 192, 256}`, 256 | multiples of λ = 8 over 21 configuration-bit addresses; one generation of the (μ, λ) = (4, 8) engine costs 8 evaluations. B3's grid is the scale of a 292-address LUT class and is not transferable |
| K1 | `p95(Ω) < 64` and `median(best_R) > median(base)` | the task's ceiling is 64 scoring cells (§7). Two medians compared, not the median of a difference — the ruling's correction. B2's interpolated percentile by copy |
| K2 | variance > 0 (population), both signs at one budget, X non-rejection ≥ 90 % | B3 H2's numbers unchanged; ties stay in the resampled population but not in the sign test's effective *n* |
| K3 | 10 % ratios, `p > 0.05`, positive denominators required | B2 G3 / B3 H3's 10 %. A negative numerator passes without being made absolute; a non-positive denominator fails the row instead of reading as satisfied |
| K4 | 57.6 and 50 % | 90 % of the ceiling is B2 G4's. The 50 % is this unit's advance criterion and has no precedent: B4's F map is a closed-book observation grouping with no semantics, while Ω is a certificate-derived grouping reference, so B2's 90 % has no basis here. Failing it is a result about the learned grouping |
| K5 | d ≥ 0.5, power ≥ 0.90, complete ascending scan, cap 4 000 | d from B3 H5 (the online arm pays the poor-map cost first). The scan is complete by the 2026-09-10 lesson that bracketing returned N = 91 where 89 already had power. The cap bounds the three-arm main experiment's search evaluations only |
| K6 | S = 200, N ≥ 8 | B2 G6 / B3 H6. S is the planned count, never the completed count |
| K7 | 0 recomputation mismatches; O's `B*`-prefix median ≥ 11 of 21 | rewritten per the ruling: the certificate partition is not the right answer for a closed-book observer, so the partition difference became a threshold-free diagnostic and the zero-anomaly check became internal recomputation from the arm's own ledger. 11 is half of 21, read on O's prefix, and *not unknown* implies neither a usable grouping nor a decoded semantic |
| K8 | holds, over every executed run | a contract break is `invalid` under §9.1, never an ordinary failure |
| K9 | ≥ 90 % of seeds, median coverage ≥ 0.50 per semantic, on §9.3's fixed set | the stimulus is per seed, so the criterion is per seed. The 64 fixed backgrounds, the forced-bit pairs, the applicability exclusions and the coverage denominator are all written in §9.3 so that no context can be chosen afterwards. No precedent for the two numbers; they are this unit's choice |
| K10 | τ = 2 score units, `max|I| > 2`, two fixed backgrounds, all 210 pairs, ≥ 0.50 of S | τ as a fraction of the range (2 / 64) keeps a single-cell difference from counting as interaction; exactly 2 falls in *nonzero below threshold*. The second background is derived once from the landscape seed with a fixed salt, independent of the task, operator and control generators, so it can never be a champion or any run's product |
| `B*` | smallest `N(B) × 3 × B` among eligible budgets, ties to the smaller | B3's rule. No eligible budget means the budget rule FAILS, dependent rows are *not assessable* and the gate cannot PASS; `B*` and `N` are never invented |
| anchor | `sha256('b4-gate-1|' + the v0.3 hypothesis digest)`, label passed beside it | auditable, stable when a commit is re-made, and tied to the model being judged. A pre-joined label would put two labels in one string |

## The ruling's corrections, each applied

- **K7** no longer treats a difference between the certificate-derived and the observed partition as
  a defect; it is a diagnostic with no threshold, and §9's K7 says why a slice-wide configuration bit
  can legitimately land beside one element's address.
- **K9** carries the fixed comparison set of §9.3 and a stated coverage denominator.
- **D** is now the same seed's F-learned frozen map passed once through `shuffled_view` (§8), not a
  shuffled oracle view; X's and D's control seeds have their own formulas, fixed before observation.
- **Incomplete data** cannot produce a PASS: §9.1. Valid complete data with no solution for `N` is
  an ordinary discriminability result; a broken tool contract is `invalid`.
- **The 4 000 cap** is the three-arm main experiment's search evaluations, explicitly not a board
  session, time, observation or record bound; the per-pair observation arithmetic is written out and
  the draft's `16 × 3 × 83` example, whose 83 is not on the grid, is replaced by `16 × 3 × 64`.
- **Seeds**: the anchor, the file-by-file exclusion set with digests, and B4's exposed values are all
  listed; `evidence/b4/sim/` is named as not yet created, kept apart from a historical source that
  ought to exist and is missing, which would be refused.
- **K10** is comparability inside the model's domain under v0.3, and §9's K10 says in those words
  that it is not a statement that a corner is buildable, writable or safe on a device.

## Not authorised by this commit

The S = 32 exploration is **not** authorised. Next comes the exploration harness and its execution
scope (the D and X controls, K7's prefix snapshot, K9's fixed set, replay, the seed and archive
rules, time limits, the dirty-tree / no-clobber / stop rules) for the owner's review. Exploration,
the formal gate, unit 2b-4, 2c, 2d, purchases, push, merge and board work all remain unauthorised.

## Follow-up v0.1.13a — wording only (2026-10-18, after `3564236`)

Made on the user's instruction that the document must not leave a sentence open to two readings. **No
threshold, grid, formula, seed, path or digest changed**; `checks_followup_v0113a.txt` lists the
number tokens the edit added (dates, section references, the literals `0`, `1`, `21`, `32`, the commit
`3564236`) and confirms none was removed. Each sentence below was ambiguous before and is fixed now:

| where | the two readings it allowed | fixed as |
|---|---|---|
| K2, K3 | the one-sided sign test's direction was only implied by the copied function | H1: P(control − R > 0) > ½, the direction in which the control would profit; K3 runs over the S pairs at `B*` |
| K7 (b) | "O's `B*` search prefix" did not say which ledger records | the records from the base observation through the `B*`-th search evaluation inclusive — O's first `B* + 1` records — and the map state after ingesting exactly those |
| K9 | "`ff_init` is reported separately" could be read as "excluded from the seven"; "median over seeds" did not say whether a not-assessable seed enters it | the seven are named from §5.2; `ff_init` counts as the others do and carries its A8 flag in addition; the median is over all S seeds and one not-assessable seed makes the semantic's median not assessable (fail-closed; condition (b) not met for that semantic) |
| K10 | "not comparable" and "DOMAIN is invalid" sat side by side without saying how they relate | under v0.3 every assignment is in the domain, so a not-comparable corner can arise only from a DOMAIN refusal, which is invalid; the expected not-comparable count is 0 |
| `B*` paragraph | K1 appeared both as a row at `B*` and as an eligibility condition at `B`; a bare `N` had no budget | K1 is evaluated at every grid budget for eligibility and its row restates it at `B*`; a bare `N` means `N(B*)` |
| §9.2 | "both values de-duplicated and screened against the exclusion set" did not say whether a value exposed as an operator seed also bars a landscape seed | one pooled set of integers from every listed field whatever its role, applied to both positions, as B2's `pair_seeds` does; a coinciding or repeated draw is skipped |
| §9.3 step 5 | — | repeats K9 (b)'s population rule so the two places cannot drift |

The K9 median rule (one not-assessable seed → the semantic's median not assessable) is this follow-up's
own fail-closed reading of the ruling's "a zero denominator is not assessable, never 100 %"; the ruling
did not say how such a seed enters the median, and the owner may rule otherwise. §13's 2b-3 row and the
document header carry the suffix `a`.

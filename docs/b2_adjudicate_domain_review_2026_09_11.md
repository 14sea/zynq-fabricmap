# B2 adjudicator input corrections — acceptance review, 2026-09-11

Reviewed HEAD: `0d294ea` (five commits ahead of `origin/main`, `a645c72`). Verification
ran on a clean tree; these review artifacts were added afterwards.

**The blocking input-validation P2 is closed.** The adjudicator batch may proceed to
push and `b2_runner` implementation. One nonblocking P3 remains on the optional redundant
per-pair delta field. This is a scoped host-tool review, not completion of package §7,
freeze permission, B2Q acceptance or board authorization. No push was performed here.

## 1. Original cases and guard structure

Both original reproducers were rerun unchanged, with common validation enabled. All
previously accepted malformed/ambiguous declarations or raised input cases now return
named refusals/findings. Positive controls still PASS. The earlier nonblank baseline
cases remain HOLD without primary, and the mixed measurement contradiction / malformed
seq case retains both diagnostics with outcome KILL.

The fitness string check now precedes dictionary membership. Master seeds have an
unsigned 32-bit domain, map digests use full-string lowercase-hex matching, and experiment
pair counts respect the identity-page limit. Prediction pair identities are checked
before lookup construction. Authoritative run counts, digests, primary counts and
probabilities are checked before numeric comparisons and accounting.

The prediction's deltas, sign test and sequence length must agree with its own validated
run values. This closes the earlier duplicate-entry overwrite and Boolean/float count
aliases without replacing the external manifest's canonical-plan verification.

## 2. Independent evidence

| Check | Result |
|---|---|
| Original `reproduce_input_guards.py` | Positive control PASS; malformed cases REFUSED; `fitness=[]` CLI exits 1, writes a result, no internal error |
| Original `reproduce_adjudicate.py` | Previous corrections preserved, including blank brackets and mixed-case KILL |
| Additional type/domain matrix | 135 invalid cases REFUSED, without uncaught exceptions |
| Valid prediction families | Generated F1, F2 and F3 prediction controls accepted by the guards |
| Valid but disagreeing prediction | In-domain, self-consistent changed best fitness produces named HOLD |
| Genuine programming error injection | INTERNAL ERROR, exit 3, traceback preserved in the result; no false input refusal |
| B2/B3 suite | 315 tests, zero skips, OK in 355.907 seconds |
| Full-size model replay | PASS in 23.671 seconds; 10,818 replayed records from 10,824 records |
| Full-word readout mutation | KILL; no primary |
| Live build verification | No findings; image, ELF, actual build inputs and B1 pins match |

The additional matrix declares independent field paths and includes missing/wrong value
types, Boolean/float counts, digest length/case/trailing-newline cases, probability
bounds and non-finite values, integer-domain endpoints and count ceilings. Its 138
mutation cases comprise the 135 refusals, one valid HOLD case and the two P3 probes below.
A separate unmodified common-enabled run is accepted.

The large replay uses the prior independently generated model logs, with hashes recorded
in `review_adjudicate_2026_09_11/full_run_inputs.json`, against the committed plan and
prediction. Deltas remain `[2,5,6,3,4,6,1,-2,5]`, primary p is `0.01953125`, and the sequence
digest is `0b81b34369b73ebc24ef604014bae245cc6e0c67c176bc5988fbdbd50ee95f37`.
Its illustrative 4+4+1 partition is not a B2Q-calibrated split. The fixture is a model
standing in for a board and is not evidence about silicon.

Image `d164cd1d…` (114,708 bytes), ELF `7de96ed2…`, B1 manifest/pins and the clean
instrument at `689dde1` remain unchanged. No ARM rebuild was performed.

## 3. REFUSED versus HOLD is correct

The original `best_train=999` numerical counterexample is now correctly REFUSED:
999 is outside F1's 0..40 range and cannot be a valid prediction value. Retain that
domain check.

The independent replacement changes pair 0 A best_train from 2 to 3, then recomputes
the prediction's own per-pair delta, aggregate deltas and primary. This document passes
input validation but disagrees with measured replay, so it receives HOLD naming
best_train. The distinction between invalid input and a valid, contradicted prediction
is preserved. A complete valid replay may report its measured primary even when the
comparison with the prediction gives HOLD; the partial/diverged-replay exclusions are
unchanged.

## 4. Nonblocking P3 — optional redundant delta still accepts numeric aliases

At `host/b2_adjudicate.py:197`, the optional `pairs[i].delta_B_minus_A` field is compared
with the computed difference without first requiring an integer. In the synthetic
positive control, pair 0 has delta 0. Replacing only that field with `false` or `0.0`
still yields PASS. Replacing it with 99 is correctly REFUSED.

When this optional field is present, require a JSON integer before equality comparison;
add Boolean and float negative cases. This is nonblocking for continued host development
because the field is redundant: the run counts and authoritative `deltas` array already
have strict integer checks and must agree, and this optional field does not determine
the replayed metrics or primary. The two probes do not alter the numerical verdict or
demonstrate an external pin-chain bypass. Close the schema inconsistency before the
complete §7 package review.

## 5. Disposition

Accept the reviewed adjudicator correction and proceed with the host batch. The remaining
tools are `b2_runner`, `b2_pins` and `b2_test_report`; their binding, evidence export and
instrument integration still require review. Existing `not_checked_here` exclusions
remain exclusions, not satisfied acceptance conditions.

Artifacts: [`evidence/b2/review_adjudicate_domains_2026_09_11/`](../evidence/b2/review_adjudicate_domains_2026_09_11/).
Only review documents/artifacts and the package status banner were written. No production
code, firmware, existing evidence, manifest, ruling or instrument was edited. No commit,
push, ARM image build or board action was performed.

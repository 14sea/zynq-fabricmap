# Owner review of 6927c24 — HOLD, two remaining P2 cases

2026-10-21. Reviewed exact tip `6927c2452ad7f8ead23d78a0061a3c201b872ac1`, parent `df3b65e8072eaab96d7c19d9d10e177b14e1ff9b`, branch `b4-2c-obs`, clean tree. This is a read-only review of the existing document unit. No tracked file was changed by the reviewer.

## 1. Verified and accepted

- Independently reran `python3 -B -m unittest b4.tests.test_b4_seeds b4.tests.test_b4_thresholds`: **29 tests OK**, no skip.
- Reran the author's static script from a temporary copy so its output did not overwrite tracked evidence: **byte-identical output, all_pass true**. The two additional boundary cases below are outside its enumerated cases.
- Independently checked existing sim-4 pair 000 ledger, target and K9 memo observations: their grid and reconstructed-configuration hashes match the corrected representation rules. No model, replay, fabric, production verifier or seed generator was called.
- The previous review's eight files are byte-identical to the archived copy, checksum entries verified. Protected paths are unchanged from `fceedd6`; the selection scripts and outputs are unchanged and were not rerun. Architecture and skeleton changes remain confined to document pointers/status; choice 7 is unchanged.
- The previous R1/P1 is addressed: Q-grid versus whole-record digests separated, archive projections identified, adapters scoped, legacy digest encodings preserved and fabric descriptor corrected.
- The previous R2/P1's future-field problem is addressed: an invalid observation now retains phase-dependent acquired fields, including the P3 case with no P4 readback, without inventing future witnesses.
- The previous R3's ordinary/J3 frame binding and held-input context are addressed. A5's projection and explicit qualification exception remain accepted. The remaining root case is R1 below.
- The previous R4's stuck-reference counterexample is addressed: reference/prior controls are required, capture/hold/unknown are distinguished, and quantities are derived from per-corner readings. The constant-restore absence case below remains.

## 2. R1 — P2: mechanism (c)'s session root still dereferences a nonexistent predecessor

References: `docs/b4_observation_contract.md` **5.4, line 385**, and **5.5, lines 395–400**; `static_contract_checks.py:133–144`.

The new table groups `closed` and `session_root` together for (c) and requires pre-event readback to equal the **predecessor X.base_readback_sha256**. But 5.5 correctly makes the first transaction's predecessor `{kind:session_root, seq:null, close_sha256:null}`. No preceding X exists at that point. Its own X is not written until later and cannot serve as a past reference without a cycle/future witness. The mechanism-(c) root therefore cannot satisfy the required binding, even though the normal and J3 rows now work.

Split the root from `closed`. Name the independent, retained session-opening/initial-configuration reference that the root's actual pre-write readback binds to and the trusted input establishing what that prior configuration is. If startup is required to have been verified as base, state that requirement and its reference explicitly; do not infer it from a nonexistent predecessor or from the root's own later X. If the reference is unavailable, give the non-success path rather than manufacturing it. Keep the terminating predecessor value and the normal/J3 rules.

This asks for a bootstrap contract, not a new board operation, a selected mechanism, a new record-count prescription or an experiment. The author's helper receives a `base_ref` argument even for `session_root`, but does not resolve its source, and its actual r3 cases never exercise the root. Add one static check that the root's reference is available before its event and does not lead back to its own close.

## 3. R2 — P2: a constant restore is incorrectly turned from absent SRVAL effect into failure

References: **6.7 lines 557–560, 570–577**; `static_contract_checks.py`'s final `classify` function.

Use valid reference captures `K0=0,K1=1` and valid planted priors `P0=1,P1=0` in every corner. Let INIT samples track INIT correctly. Let all four corners produce **restore(0)** (or all four restore(1)). The four SR readings are identified restores, but the SRVAL bit has no main effect; neither readout tracks the wrong bit, and there is no mixed restore/non-restore, unknown reference or disagreement between paired effects.

The written formula makes `srval_effect=false`, `srval_absent=false` (only all-capture/all-hold count as absent), hence `inconsistent=true` and **row 1 failure**. I independently evaluated the formula and confirmed the author's helper returns row 1. Yet the document's explicit rule at line 575, accepted in previous rounds, says **an absent main effect alone is a reduced claim, not a failure**. With INIT present this should be row 4, INIT demonstrated / SRVAL not; with INIT also absent it should be row 5. Four combinations (constant value 0/1, INIT present/absent) reproduce the error in the review's static results.

Include the all-restore/no-SRVAL-contrast case in `srval_absent`: in notation already used, all four are restore and `v00=v01` and `v10=v11`. Keep the separate cross-tracking guard, so values changing with INIT still fail. Preserve existing all-capture/all-hold absence handling, mixed-corner inconsistency, unknown-reference handling, direction checks and no automatic attribution/revision. This corrects the agreed distinction between absent effects and inconsistent/cross-tracking evidence; it is not a new threshold or a change to a historical result.

Add these constant-restore examples to the small static table. No model observation or larger test battery is necessary.

## 4. Same-unit finish and verification limits

Continue within the existing authorization: correct both P2 items together and submit once, without another scope proposal or per-fix approval. Only targeted static cases and the affected document-pin checks are needed. No full suite, mutants, new model/device observations, production seed derivation, schema implementation, b4/ changes, push or merge are requested. Keep choice 7 unchanged pending acceptance as already stated. A8, mechanisms/timing, metric, N/B*/prediction/sessions and 2c freeze remain legitimately unresolved; those open design decisions are not this HOLD's reason.

Minor evidence notes, not additional blockers:

- `git diff --check fceedd6 HEAD` reports only an extra blank line at EOF in the **byte-identical owner output** `owner_review_df3b65e_HOLD/author_static_rerun.txt`. That whitespace originates in my prior artifact. Preserve the raw review copy; do not trim it to obtain a green diff check.
- The script's older C1/C2 helpers retain historical enum/field names; the newer R1 checks carry the current corrections. Treat `all_pass` as the listed static cases, not a general schema/transaction validator or complete state-space proof.

Artifacts here contain the exact independent examples, pin output, author rerun, review metadata and checksums. No production archive or method was changed or rerun.

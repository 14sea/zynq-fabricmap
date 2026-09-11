# The optional delta field is typed — P3 closed, 2026-09-11

The owner's acceptance review (`docs/b2_adjudicate_domain_review_2026_09_11.md`, against
`0d294ea`) closed the blocking input-validation P2 and left one nonblocking P3: the optional
redundant `pairs[i].delta_B_minus_A` was compared with the computed difference without first
requiring an integer, so `false` and `0.0` both substituted for 0 (99 was correctly refused).

Corrected: when the field is present it must be a JSON integer, checked before the equality.
A field that is present is a field that is typed, redundant or not.

`review_domains_after.json` is the owner's own `reproduce_domains.py`, **unchanged**, re-run on
the corrected module (its `head` records the commit it ran against):

- baseline PASS; the F1 / F2 / F3 valid prediction families still ACCEPTED.
- the injected programming defect still reports INTERNAL ERROR with exit 3 and a saved
  traceback, `misclassified_as_refusal: false`.
- of its 138 mutation cases, the **only two** that no longer match its expectations are
  `redundant_delta_bool` and `redundant_delta_float`, which the probe recorded with
  `expected: "PASS"` **because that was the defect it was reporting**. They are now
  `REFUSED: the prediction's pair 0: delta_B_minus_A False / 0.0 is not an integer`, which is
  the correction. The script's closing `assert not out['failed']` therefore trips — it asserts
  the pre-correction behaviour. Every other case, including the 135 refusals and the single
  valid-but-disagreeing HOLD, is unchanged.

71 adjudicator tests (was 70); the B2/B3 suite is **316, zero skips**. The new test drives
`false`, `0.0`, `true`, `"0"` and `null` through a pair whose delta is genuinely 0, so the
alias cannot hide behind a non-zero value.

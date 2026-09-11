# B2 extension types — the correction's acceptance, 2026-09-11

The owner's initial review of the record validator (`docs/b2_records_initial_review_2026_09_11.md`,
against `aced532`) found that `record_findings()` used B2 extension values before checking
their types: a string `pair` raised `TypeError` at the range comparison, scalar `population`
elements raised `TypeError` in `sorted()`, and wrong-typed `born`/`fit` values and a
non-Boolean `selected` were accepted in silence.

- `record_types_after.json` is the owner's own `reproduce_record_types.py`, unchanged, run
  against the corrected `host/b2_records.py`. The twin's real wire `REC` is still accepted
  with no findings; each of the four mutations the instrument's common validator waves
  through is now a NAMED finding and none of them raises.

The same four mutations are in the suite twice: on the Python fixture
(`Types.test_refuses_the_reviews_four_extension_values`) and on the twin's real wire record
alongside the instrument's acceptance of it
(`WhyThisModuleExists.test_the_instrument_accepts_a_record_with_malformed_b2_values`).

Discrimination: with `host/b2_records.py` reverted to `aced532` and the new tests left in
place, the new cases fail — 13 failures and 9 errors across `Types` and `WhyThisModuleExists`
— so the tests are driven by the defect, not by the correction.

Host-only. The twin is a native build; no ARM image build, no firmware, evidence, instrument,
ruling or board contact.

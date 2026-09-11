# B2 adjudicator corrections — input review, 2026-09-11

Reviewed HEAD: `da89506cb5a70277c85646e166456de79c6bdd5e`, three commits ahead of
`origin/main` (`a645c72`). The tree remained clean throughout independent verification;
the review artifacts were added afterwards.

**HOLD remains on accepting/pushing this adjudicator batch.** The baseline P2 and the
planning-scenario documentation P3 are closed. The input-validation P2 is only partially
closed: the original cases now behave correctly, but the new guards still use an untyped
value as a dictionary key and accept ambiguous or mistyped prediction inputs.

## 1. Corrections independently verified

The original `reproduce_adjudicate.py` was rerun unchanged, with common validation enabled.
Every previously raised case now gives a named result. The opening and closing nonblank
genomes each produce HOLD without primary. The mixed additive contradiction / malformed
seq case produces KILL and preserves both diagnostics. The malformed-seq CLI case exits 1,
has empty stderr and writes its result file.

The position-keyed readout map, input-order replay and record-finding gate correctly remove
the previous wire-seq hazard. The independent measurement pass survives that malformed
record, while stateful replay is disabled. Both bracket genome checks sit at the point
where the replay assumes a blank starting population and closing bracket.

The README and generator now correctly call 4+4+1 an illustrative planning scenario;
the plan's final split remains UNDETERMINED pending B2Q calibration.

Verification results:

| Check | Independent result |
|---|---|
| B2/B3 suite | 302 tests, zero skips, OK in 317.090 seconds |
| Full-size model fixture | PASS; 10,818 replayed records from 10,824 records; 18.696 seconds |
| Prediction | Deltas `[2,5,6,3,4,6,1,-2,5]`, sequence `0b81b343…`, primary p `0.01953125` unchanged |
| One full readout word complemented | KILL with measurement and replay findings; no primary |
| Live build check | Zero findings; image `d164cd1d…`, ELF, source inputs and B1 pins match |
| Instrument | Clean at `689dde1` |

The large model logs are the prior independently generated fixtures, whose hashes are
recorded in `review_adjudicate_2026_09_11/full_run_inputs.json`. Only the corrected
adjudicator was rerun over them. They are not board evidence.

## 2. Remaining P2: input guards are incomplete

### A. `fitness` is hashed before its type is established

At `host/b2_adjudicate.py:102`, `plan["fitness"] not in bl.FITNESS` performs dictionary
membership before checking that the value is a string. A JSON array or object therefore
raises `TypeError` from the public `adjudicate()` API. The four cases `[]`, `{}`, `["F1"]`
and `{"name":"F1"}` all reproduce it. The existing unknown-string control `"F9"` is
correctly REFUSED.

The real CLI now writes a result, which is an improvement, but `fitness=[]` exits **3**
with `INTERNAL ERROR: TypeError: unhashable type: 'list'` rather than giving a named input
refusal. The last-resort error handler is working; it does not replace the missing guard.

Require a string before membership lookup, and exercise both array/object values through
the API and CLI. Audit the other directly consumed fields under the same ordering rule.

### B. Prediction values and pair identities are not fully validated

`check_prediction()` at lines 125–136 establishes that A/B runs and the primary are
objects, but not the types of their compared values. Python numeric equality then accepts
Boolean/float substitutes for integer counts. The pair dictionary built at line 560
silently overwrites duplicates, and entries outside the experiment are never visited.

The independent common-enabled fixture produces these results:

| Single input mutation | Result |
|---|---|
| Prediction budget integer 12 replaced by `12.0` | PASS |
| Pair 0 A `best_train=2.0` instead of integer 2 | PASS |
| Pair 0 A `column_moves=false` instead of integer 0 | PASS |
| Primary `positives=true` instead of integer 1 | PASS |
| Primary `ties=2.0` instead of integer 2 | PASS |
| Prepend a duplicate pair 0 declaring A `best_train=-999`; retain the correct pair 0 later | PASS; the contradiction is silently overwritten |
| Append a pair whose ID equals `plan.pairs`, outside the experiment | PASS; the extra entry is ignored |
| Change the sole pair 0 A `best_train` to 999 | HOLD (negative control) |

Require the prediction pair IDs to cover the experiment exactly once before constructing
the lookup. Validate the consumed run fields and primary fields individually, distinguishing
integer counts from Boolean/float values. Check sequence/delta accounting and the domains
of the values being consumed. Preserve the existing distinction between an invalid input
and a valid prediction whose values disagree with measured replay.

### C. The claimed plan domain checks are also incomplete

The same probe confirms two additional acceptance gaps:

- Add `2**32` to the plan's master seed and the identity's master seed: PASS. The guard
  accepts any integer, while `b1_carto.Rng` masks to 32 bits, silently replaying the
  original stream under an out-of-range declaration.
- Replace the plan map digest and both identity map references with `not-a-digest`: PASS.
  The guard checks only for a string, not digest syntax.

Check the master seed's wire-representable domain and complete digest syntax before use.
The submission's claim that every consumed value's type and range is checked is stronger
than the implementation currently supports.

These probes address the adjudicator's declared local input contract. They do **not**
demonstrate bypass of `b2_manifest.verify()` or the frozen pin chain, which this module
explicitly excludes. Fixing them does not require duplicating the manifest's complete
canonical-plan verifier here.

## 3. Disposition and evidence

Keep the new adjudicator batch under review until the remaining input-validation P2 is
closed. Existing acceptance of the earlier record validator is unchanged. The three
remaining host tools and the complete §7 review are still required before board clearance.

The new probe contains a passing common-enabled control and a named-HOLD numerical
counterexample, so its accepted malformed cases are not caused by a broken fixture or a
disabled comparison. All envelopes are synthetic local fixtures; none claims actual
signatures, audit completion or silicon behavior.

Artifacts: [`evidence/b2/review_adjudicate_inputs_2026_09_11/`](../evidence/b2/review_adjudicate_inputs_2026_09_11/).
No production code, firmware, manifest, ruling, instrument or existing evidence was
edited. No commit, push, ARM image build or board contact was performed.

# The owner's review of 4cdc0c1 (2026-10-19), as relayed by the user (build/wip/owner_review_4cdc0c1_2026_10_19/README.md; its raw probe artifacts stay in that ignored directory)

# Owner review: B4 gate tool and 2c skeleton, 2026-10-19

Reviewed HEAD: `4cdc0c181a1a899714c575e2b52a8aefe5e1df63`.
Unit: `4f3806d` (implementation), `7cf6c7f` (2c skeleton), `4cdc0c1` (evidence).
Base of this unit: `85c95d9`. Main remains `d5bf815`.

**Decision: HOLD for the three P2 findings and the P3 document correction below.**
Fix these as one complete unit, validate the finished unit, then submit one batch for review.
No approval is needed between the individual fixes within this scope. Preserve existing commits and evidence.
This review does not authorize production gate execution, new production seed derivation, a new exploration,
carrier RTL, provisioning, board work, push or merge.

## 1. Independent checks

- Full B4 regression on a `git archive` snapshot of reviewed HEAD: **277 tests, OK**, zero skips,
  323.545 seconds. The outer production-master derivation guard recorded no calls. See `tests.txt` and `suite_guard.py`.
  The snapshot was `/tmp/b4_owner_4cdc0c1_4iop5d6u`.
- All five committed end-to-end cases were verified again in fresh processes: PASS, FAIL, FAIL with B*,
  invalid and incomplete all returned verifier exit 0, findings `{}`. See `e2e_verification.json` and individual raw outputs.
  Clean here means consistent evidence and judgement, not a scientific PASS.
- Focused independent mutant rerun: G2, G3, G7, G9, G11, G13, G15, G16, G17, G21, G25, G26,
  G27, G29, G30: **14/15 killed**, G29 survived, 165 seconds. See `focused_mutants.txt`.
  The author's full battery logs were also inspected; they are not represented as another independent full rerun.
- IMPORT: all **52 entries** match; all 78 distinct file/source digest checks match; no unregistered or missing B4 file.
  The architecture, threshold table, hypothesis loader, behaviour model, search engine and task generator are unchanged
  from the unit base. No change to the old pinned namespaces. See `scope_import_check.json`.
- The committed b4-sim-3 archive was independently deep-verified again; see `sim3_deep_verify.txt`.

## 2. R1 — P2: malformed summaries can escape the contract as exceptions

Location: `b4/host/b4_gate.py:125` (`summary_contract_findings`), and the reads in `judge`, including line 332.
The stated contract is that a malformed summary is invalid and is not judged. Validation is shallow enough that:

| isolated change to the supplied synthetic summary | contract result | judge / synthetic writer |
|---|---|---|
| `at_candidate_B_star.k3.D_over_F = null` | `[]` | `AttributeError: 'NoneType' object has no attribute 'get'` |
| `candidate_B_star.value = 64.0` | `KeyError: '64.0'` | the same exception |

The second case passes numeric equality with the integer budget before being used as a string dictionary key.
The outer verifier CLI catches exceptions, but that does not implement the pure judge's invalid-summary contract.

Required correction: make the summary contract total on arbitrary decoded JSON, validate nested shapes and exact types
before indexing or arithmetic, and return named contract findings / an invalid judgement rather than an uncaught exception.
Include finite numeric/range checks where the schema requires finite values. Preserve the intentional null/special-statistic
representations rather than treating every absent number as a landscape FAIL.
Test the direct validator, judge and artifact path; an outer CLI catch alone is insufficient.

## 3. R2 — P2: inconsistent summary evidence receives PASS and verifies clean

Locations: `b4/host/b4_gate.py:125`, `:353` (K5), `:388` (K9), and the verifier's re-judgement path.
Each of these single changes is independently accepted by the contract, judged PASS, written successfully,
and accepted by a **fresh-process verifier** with exit 0 and `clean: true`:

| case | inconsistent or impossible evidence |
|---|---|
| `empty_N_scan` | the selected budget claims N=16 and power 0.95 but `required_pairs.scan` is empty |
| `contradictory_delta1_d` | per-budget primary Cohen's d is -1, while the at-B* copy remains +0.9 and is used to PASS K5 |
| `inconsistent_positive_infinity` | Cohen's d is `{value: -100, special: "+inf"}` and is interpreted as positive infinity |
| `K9_fraction_above_one` | `fraction_of_S = 2.0` while its count remains unchanged |

See `summary_probes.py`, `summary_probes_results.json`, and `negative_archives/` for the artifacts.
The probes use the delivered hand-made synthetic fixture. **All results remain `formal=false`; this is not a demonstrated
forgery of a production gate archive.** The production archive's raw recomputation provides another boundary.
Nevertheless, the accepted synthetic path is part of this unit's judge/verification acceptance and must enforce its advertised
summary contract. Re-running the same incomplete validator in the verifier does not detect these contradictions.

Required correction: validate the ascending N-scan structure and its consistency with the claimed N/power; bind the at-B*
statistics to their per-budget counterparts wherever they represent the same quantity; enforce the unique valid encodings
for finite/null/special statistics; validate bounded fractions, counts, and their linkage to S. Cover all fields read by K1–K10,
not just these four examples. This does not require synthetic observations to become authenticated model evidence or a new
statistical method: it requires the declared summary to be well formed and internally coherent under the frozen method.
Adjust synthetic fixtures coherently when necessary. Test that refreshed hashes and re-rendered markdown cannot make an
invalid summary a clean PASS artifact. Keep valid PASS/FAIL/incomplete/invalid examples and the formal=false boundary.

Positive control: setting the K10 interacting count to null already produces a named contract finding, an invalid judgement
and a cleanly verifiable invalid report. That demonstrates the intended distinction between invalid evidence and a valid FAIL.

## 4. R3 — P2: the repaired seed regression assumes all registry entries have seeds

Location: `b4/tests/test_b4_seeds.py:145`.
The new loop asserts every entry has status `seeds` and unconditionally opens its seeds.json.
The production registry also accepts `init_failed_no_seeds`: a valid INIT_FAILED record written before seed derivation.
This legal state must remain archiveable without breaking the regression suite.

Independent reproduction: a hermetic root with the committed S=32 seed record and one well-formed mechanics INIT_FAILED
record (`seeds_derived=false`) is accepted by the registry. Running the two changed HistoricalSources tests yields
**Ran 2, one failure**, specifically `'init_failed_no_seeds' != 'seeds'`. No derivation was performed.
See `registry_probe.py`, `registry_probe_results.json` and `registry_probe_stdout.txt`.

Required correction: make the regression status-aware for every legal registry record kind (including the existing fixture
record kind), while retaining exact membership, digest and pooled-union assertions. Add a mixed-registry case. Do not alter
the production loader or exclusion policy to make the test pass.

## 5. D1 — P3: the 2c skeleton misstates B3's lifecycle

Location: `docs/b4_preregistration.md:152`.
The skeleton states B3 S0 is freeze/pins/seeds/plan, S1 is prediction, and S2/S3 are sessions/adjudication.
The production reference `b3/host/b3_manifest.py:28` and `:124` instead defines:

- S0: initialized, not frozen, no qualification, no main-plan binding; the prediction is already pinned.
- S1: freeze preregistration and owner board-ready state.
- S2: qualification and calibration.
- S3: calibrated plan binding; board sessions and pooled adjudication do not introduce a later transition.

Correct the historical reference and keep the B4 lifecycle/tool/stage contract unresolved where it has not been decided.
Do not silently turn a skeleton sentence into authorization for a new lifecycle design. The other unresolved N/B*/seeds/
prediction/session fields appropriately remain unresolved; no preregistration freeze is accepted by this review.

## 6. Accepted explanations and follow-up boundaries

- **G29:** accepted as an equivalent survivor in the current reachable judgement states. Without B*/N the budget rule fails,
  so removing `not na` cannot make the overall verdict PASS. Keep the honest count; do not manufacture another kill.
- **Old M18 / G30:** retaining the archived old script's EDIT-MISS and recording G30's successful relocation is acceptable;
  the old evidence need not be rewritten. The independent focused run also killed G30.
- The architecture-version text inside THRESHOLDS is a real historical-verification coupling when that constant is revised.
  A mere document edit does not mechanically change the constant, but updating it to follow the document version changes the
  comparison table. Record this as a separate design issue before any such update; this correction unit must preserve the
  frozen table and the existing S=32 archive. It is not a reason to modify thresholds now.

Finish all fixes above within this unit, refresh IMPORT, run the complete B4 regression once on the finished clean tree,
add targeted negative controls for the actual failure modes, and verify the refreshed-hash negative artifacts and the positive
e2e artifacts in fresh processes. Preserve derivation guards and use mechanics/synthetic inputs only. Recheck the unchanged
S=32 archive. Submit code, document correction and evidence as one batch; production gate remains withheld.

## 7. Review provenance

This directory is ignored review material, not a committed product change. Only temporary fixtures and these review artifacts
were written. The reviewed branch and main refs were not changed. The first probe setup attempt failed because the review
script tried to commit an unchanged temporary tree; that script setup error is retained under `attempt1_probe_setup/` and is
not a product finding. The corrected script conditionally commits only changed temporary artifacts.

The scripts record their temporary roots and use snapshot paths. For a later replay, extract the same reviewed commit and
substitute that extraction path. No production master or pair-seed computation is needed by these probes.

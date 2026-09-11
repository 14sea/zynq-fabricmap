# B2 adjudicator review — 2026-09-11

Reviewed HEAD: `1b3995107088a48bbda2b380177f1a44d0864687`, one commit ahead of
`origin/main` (`a645c72`). The tree was clean throughout the independent test run.

**HOLD on accepting/pushing the new adjudicator commit.** Two P2 findings remain:
malformed inputs can escape as exceptions after validation, and nonblank baseline
genomes pass the replay. The earlier digest-format P3 is closed. These findings
require host changes; they do not identify a firmware defect or require a new image.

## 1. Verified behavior

- The unchanged 330-case record-type matrix still rejects all negative cases. Its
  trailing-newline digest probe now returns `state_sha256 is not 64 hex`; normal
  IDENT and REC controls remain accepted.
- The independent B2/B3 suite passes **286 tests, zero skips, in 328.171 seconds**.
- The full-size model fixture was regenerated from the committed generator and
  adjudicated through the CLI with `--no-common`: 10,824 readouts, 10,818 replayed
  records, deltas `[2,5,6,3,4,6,1,-2,5]`, primary p `0.01953125`, and sequence digest
  `0b81b34369b73ebc24ef604014bae245cc6e0c67c176bc5988fbdbd50ee95f37`, all matching
  the submitted prediction.
- Complementing all 64 bits of readout word 0 at session index 1, seq 2004 yields
  KILL: additive scores disagree and recomputed F1 changes from 8 to 0. Replay
  diverges at that record and no primary is emitted.
- Source inspection confirms replay obtains observations from the collected readouts,
  rather than invoking the fabric model to generate them. Public landscape construction,
  seed/order helpers and `record_block()` are reused; `b2_session.run()` is not used
  as replay evidence. Full and short generations, champion remeasurement and per-arm
  prediction checks have committed test coverage.
- The live build verifier reports no findings. Image `d164cd1d…` (114,708 bytes), ELF
  `7de96ed2…`, actual inputs and B1 pins still match. The instrument remains clean at
  `689dde1`. No ARM rebuild was performed.

These are offline software checks and model fixtures, not observations about silicon.

## 2. P2 — validation findings do not protect downstream operations

At `host/b2_adjudicate.py:540–546`, record validation findings are collected, but
measurement and replay proceed unconditionally. `measurement_pass()` then inserts
`(session, seq)` into a dictionary at line 200 without establishing that `seq` is
hashable. With `seq=[]`, the upstream record validator already returns named findings,
but the adjudicator raises `TypeError` instead of returning a result. The outer handler
catches only `Refusal`.

The independent probe exercises the public adjudicator with **common validation enabled**:

| Input mutation | Current result |
|---|---|
| Unmodified positive control | PASS |
| Session log replaced by an array | Uncaught `AttributeError` |
| REC `seq=[]` or `seq={}` | Uncaught `TypeError` |
| `loop_records=7` | Uncaught `TypeError` |
| Plan `map=null` or `pairs="3"` | Uncaught `TypeError` |
| Prediction `pairs` missing / null | Uncaught `KeyError` / `TypeError` |
| Prediction pair `runs=null` | Uncaught `AttributeError` |
| Valid-shaped REC with wrong state digest | Named HOLD, no primary (negative control) |

The CLI counterexample additionally invokes `--out result.json`: it exits with a
traceback and **does not write the result file**. A variant placing an additive-score
contradiction before the malformed seq also raises, losing the already collected
measurement contradiction from the returned result.

Validate container/value shapes before each dependent operation, including the plan
and prediction fields this module directly consumes. Malformed data must produce a
named refusal/finding; unsafe records must not enter replay or readout indexing. Preserve
diagnostics already collected from valid records when handling later failures. Do not
solve this solely by converting every programming exception into an input refusal.
Add public-API and CLI negative tests, including the mixed contradiction/malformed case.

This finding concerns the module's own input and result contract, not the intentionally
deferred manifest/pin/transport layers.

## 3. P2 — baseline genome identity is never replayed

`Replay._session()` at lines 299–314 checks the opening readout and absence of search
blocks, but neither baseline's genome. `_arm()` then initializes every parent genome
to zero regardless of what the opening record actually names. The measurement pass
checks zero baseline readout and additive scores, which do not establish that the
declared candidate is the blank genome.

Two independent mutations therefore still produce **PASS, zero findings and a primary**:

1. Replace only the opening baseline's genome by `genome_to_hex(1)`.
2. Replace only the closing baseline's genome by `genome_to_hex(1)`.

The probe keeps the baseline readout zero and updates the related local commit fields
consistently. Each mutated record passes common per-record validation. The synthetic
envelopes do not claim real signatures or audits; they demonstrate that enabling the
actual common-validation entry point does not close this replay gap.

The firmware contract is explicit: `firmware/b2/b2_orch.c:109` and `:154` call
`genome_clear()` for the two brackets. Preregistration §4 also requires the baseline
contract inherited from B1. A replay cannot assume a zero-genome starting population
while accepting a different opening candidate, or accept a different closing candidate
as restoration evidence.

Require the exact blank genome at both bracket positions in every session. Reject either
mutation with a named finding and suppress successful replay/primary claims. Add the
two negative cases with common validation enabled, plus a valid split-session control.
This check needs no fabric-model readout and no new external authority.

## 4. P3 — the demonstrated split is a planning scenario

The demonstration README and generator comment call `4+4+1` the plan's three-session
shape. The committed `evidence/b2/plan.json` actually says
`UNDETERMINED until B2Q measures the all-self-reporting rate` and lists candidate splits.
The generator hardcodes `[(0,4),(4,4),(8,1)]`.

Label that partition as an illustrative planning scenario, not a frozen/calibrated
plan. The experiment's fitness, budget, seeds and prediction are the committed inputs;
the final session partition still depends on B2Q calibration. This is a documentation
correction, not a request to freeze or change the plan now.

## 5. Limits and disposition

One additional control flips only bit 0 of readout word 0 in that search record and
still passes. Vector 0 belongs to holdout, so this change affects neither the search
fitness nor the PL train additive score. This is not classified as another defect:
the implemented checks do not promise byte-for-byte authenticity for every unused
readout bit. Evidence sealing, audits and the remaining integrity checks must be
reviewed when their integration exists.

The declared exclusions under `not_checked_here` remain exclusions, not satisfied
acceptance conditions. Finish the two P2 corrections before accepting this adjudicator;
then continue `b2_runner`, `b2_pins` and `b2_test_report` toward the full §7 review.
Earlier approval/push of `a645c72` is unaffected.

Reproducers and outputs are under
[`evidence/b2/review_adjudicate_2026_09_11/`](../evidence/b2/review_adjudicate_2026_09_11/).
Only new review artifacts and the package status banner were written. No production
code, firmware, prior evidence, manifest, instrument or ruling was edited; no commit,
push, ARM build or board action was performed.

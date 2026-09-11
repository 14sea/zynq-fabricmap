# The session contract's three P2s — corrected, 2026-09-11

The owner's runner correction review (`docs/b2_runner_correction_review_2026_09_11.md`, against
`366d96f`) accepted the wire lookup, the ruling master binding, the seed-container validation and
both P3s, and left three P2 gaps in the composed session verdict. All three are corrected.

`acceptance.json` is `acceptance.py`'s output — the review's own probe cases, re-run against the
corrected code, with the same doubling the review used (the archived B1Q transcript has no B2
search blocks, so ONLY the B2 record replay is doubled; every instrument validator, audit gate,
ledger check and rate report is real).

| the review's case | before | now |
|---|---|---|
| `no_l6_binding` | PASS | HOLD — `the run log's l6 carries no binding block` |
| `wrong_l6_image` | PASS | HOLD — `binding: the log's image_sha256 is …, this invocation's is …` |
| `wrong_l6_manifest` | PASS | HOLD — the same, on `b2_manifest_sha256` |
| `no_l6` | PASS | HOLD — `the session declared no binding at all` |
| `different_manifest_argument` | PASS (the argument was unused) | HOLD — `the archived manifest's image is not this invocation's` |
| a same-length wrong slice | not detected | `slice: the IDENT's pair_first is 4, this session's is 0` |
| no export seal | not checked | `evidence seal: the evidence carries no exports.json` |
| the session's own deadline | never compared | `the session spanned 14.3 s, past the 1.0 s deadline this session was authorised for` |
| a changed `audits.json` / `timeline.json` / `exports.json` / console / summary / ruling | left the qualification record identical | **every one of them changes it**; an incomplete evidence set is refused for membership |

## How each was corrected

- **P2-1 identity and invocation bindings.** `binding_findings` holds the log's `l6.binding` and
  `l6.inputs`, and the IDENT, to what this invocation declares — including the **slice**, which a
  record count cannot separate when two slices share a length. `archived_manifest_findings` makes
  the `manifest` argument load-bearing: the manifest archived beside the evidence must BE this
  invocation's, by bytes and by stage, before anything else is read — otherwise every later check
  is reading declarations that agree with each other and with nothing else. `readjudicator` now
  judges against the **validated run manifest** the lifecycle hands it, refuses without one, and
  refuses when its image or preregistration is not the transition's.
- **P2-2 seal and coverage.** `export_seal_findings` runs B1's declared export check (the same
  code writes both stages' exports) on every standalone re-adjudication, not only inside the
  production finalizer. `b2_manifest.QUAL_EVIDENCE_FILES` is now B1's complete qualification
  evidence set — one definition for both stages — under an explicit schema migration,
  **`b2_image_qualification` 1.1.0 → 1.2.0**: eleven files, the audits and timeline a verdict
  consumes, the export seal, the raw console, the summary and both rulings.
- **P2-3 deadline.** The measured `session_span_s` is compared with the limit the invocation
  authorised, and a plan carrying no deadline is itself a finding. B2Q's planning bound is now a
  DECLARED constant with its rule (`QUAL_PLANNING_RATE_PER_HOUR`, the slowest archived planning
  rate) so the offline verdict reconstructs the same limit the producer used; `--qual-rate-per-hour`
  may only agree with it, never widen it. Pinning it in the manifest at S0/S1 remains the owner's
  standing recommendation.

Also corrected: the epoch/record-count test no longer copies the production branch logic. It now
drives `instrument_findings` through the committed **B1 session** `evidence/b1/b1_17A6_2026-09-08-02`
— a real sealed, audited, COMPLETED session — asserting a clean positive control with a measured
rate, then the deadline, the missing-deadline, the record-count and the epoch branches on it. The
export seal is likewise checked against that session's real `exports.json`, its mutation and its
removal. The lifecycle's file-set assertion names the eleven files instead of reading the
constant, so it would fail if the set shrank back.

## Why the review's own script now exits non-zero

`probe_session_contract.py`'s closing assertions encode the PRE-correction behaviour — that the
binding mutations still PASS and that a changed evidence file leaves the record unchanged — and
its membership fixture writes five of the extra files where the record now pins eleven, so it
stops at `reconstruct_qualification_record`. `acceptance.py` re-expresses its cases rather than
asserting the old answers.

## Still not done

**There is still no modelled B2/B2Q session.** The complete offline S1 → B2Q → S2 → S3 →
fresh-process verification the review requires as the next deliverable is not in this batch, and
this runner has still never produced a PASS. Every positive control here is either the archived
B1/B1Q transport with the B2 replay doubled, or a component driven directly.

## Tests

32 runner tests (was 31 before this round's additions; 19 two rounds ago), 11 lifecycle tests,
**B2/B3 361, zero skips**. Reverting only `host/b2_runner.py` and `host/b2_manifest.py` errors
`SessionAcceptance.setUpClass` — so none of that class's nine tests can run at all — plus two
`RefusalOrder` tests, and fails the lifecycle's file-set assertion.

# The runner's five P2s and two P3s — what is corrected, and what is NOT, 2026-09-11

The owner's runner integration review (`docs/b2_runner_review_2026_09_11.md`, against `fb71b00`).
`review_runner_after.json` is that review's own `reproduce_runner.py`, **unchanged**, re-run on
the corrected code (one fixture change is named below).

| the review's finding | before | now |
|---|---|---|
| **P2-1** record replay used as the session verdict — its four probes (control, STOPPED, PROTOCOL, replayed-only/no audits) | **PASS, zero findings** | **REFUSED — no session verdict without ['profile', 'manifest', 'plan', 'instrument_root']: a record replay alone is not one** |
| **P2-2** B2Q producer/consumer cannot complete | `NOT ADJUDICATED HERE`; re-adjudication returned `session="B2"` with no rate or policy | the callback judges B2Q against B2Q's own documents and seeds; the result carries `session: "B2Q"` and RECOMPUTES the rate and policy. **Still not a positive transition** — see below |
| **P2-3** successful preflight raised `KeyError: 'wire'` | crash | **`preflight_actual_instrument_shape: ACCEPTED`** against the ACTUAL pinned instrument shape, with no wire double |
| **P2-4** B2Q ruling did not bind its master | wrong seed accepted | refused: `bound to master_seed = 505806526, this session needs 505806527` |
| **P2-5** seeds converted before validation | `TypeError` for 7, [None], [1] | named refusals: `the pair seeds are int, not an array`, `1 pair seeds were given for 3 pairs` |
| **P3-1** frames counted the brackets twice | 579 frames for 22 "records" | **543 frames, 20 records** — equal to the review's own `B2Q_correct_frame_count` |
| **P3-2** infinite planning rate accepted | accepted | refused, and the check moved before the rulings so it is reachable independently |

## How each was corrected

- **P2-1/P2-2** — `judge_session` COMPOSES the instrument and evidence contract with the record
  replay: `instrument_findings` is B1's `_p3_layer` over B2's session plan (the standalone
  run-log validation with the audit gate, the declared audit policy, structural / baseline /
  REC / rel closure and control findings, the transport budgets, the rate report, the epoch's
  own outcome and its last seq against the slice's record count). The result carries what §8's
  S2 transition reads — session identity, outcome, the MEASURED rate from the evidence's own
  timing, the VERIFIED policy — and none of it is echoed from a stored `adjudication.json`.
  `adjudication_for` refuses by name when a caller cannot supply what a session verdict needs,
  instead of raising.
- **P2-3** — the wire protocol is read from the **B1 manifest**, whose bytes the preflight has
  already re-verified through the carrier lineage; the L6 manifest has no wire selector. The
  IDENT check now binds the protocol too.
- **P2-4** — both profiles bind the master seed of the experiment they run: B2's is the
  manifest's, B2Q's is its own derived one.
- **P2-5** — `check_seeds` validates the outer container, each pair's container and arity, and
  each value's type and 32-bit domain BEFORE anything converts or indexes; `seeds=None` remains
  the documented way to ask for the derivation.
- **P3-1** — `expected_frames` is given the non-bracket count and the result is cross-checked
  against the record arithmetic.
- **P3-2** — the planning rate must be finite and positive, checked with B2Q's other parameters.

## What is NOT corrected in this batch — stated, not implied

**The positive path is still not demonstrated.** The review's own reproducer now shows
`B2Q_real_readjudicator` and `B2Q_qualify` failing *for the right reason* — its B2Q evidence
directory holds only `run_log.json`, so there is no transport or timing evidence to measure a
rate from — but that is a fail-closed refusal, not the complete offline S1 → B2Q → S2 → S3
demonstration the review asked for. That needs a **modelled B2/B2Q session** (a `b2_modelled_session`
in the shape of `b1_modelled_session.py`, driving the instrument's real host stack and writing
`run_log.json`, `audits.json` and `timeline.json`), which this batch does not contain. Until it
exists:

- the instrument layer's later branches (epoch outcome, last-seq, audit coverage, transport
  budgets, the rate) are exercised only in isolation, not through a valid session;
- `b2_manifest.qualify` has not been shown to ACCEPT a B2Q transition;
- the runner's PASS path has never been produced at all.

The tests say so where they assert it. One fixture change was needed in the review's script:
`tests/test_b2_runner.Fixture.args` now binds the B2Q master seed, because P2-4's correction
requires it — without it the script stops at that refusal.

## Tests

29 runner tests (was 19) and 86 adjudicator tests; the B2/B3 suite is **358, zero skips**.
Reverting only `host/b2_runner.py` and `host/b2_adjudicate.py` fails 16 cases and errors 14
more across the two suites.

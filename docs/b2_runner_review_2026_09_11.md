# B2 runner integration review — 2026-09-11

Reviewed HEAD: `fb71b00939983c26d279e872628e85ac5fa566b8`, four commits ahead of
`origin/main` (`0d294ea`). The tree was clean throughout verification.

**HOLD on accepting/pushing the new runner batch.** The delta-type P3 is closed. The
record-level session scope works, but the runner has not yet composed it with the
session acceptance and B2Q lifecycle contracts. Five P2 findings and two P3 boundary
issues are detailed below. These are host integration findings, not a request for a
new firmware image or permission to use the board.

## Verified scope

- Independent B2/B3 suite: **346 tests, zero skips, OK in 371.179 seconds**.
- The unchanged `reproduce_domains.py` rejects the two redundant-delta aliases now.
  Its final assertion fails only because those two cases explicitly expected the old
  PASS behavior. The 135 invalid-input refusals, valid-but-disagreeing HOLD, positive
  control, F1/F2/F3 prediction controls and INTERNAL ERROR control are unchanged.
- Live image/build verification reports no findings. Image `d164cd1d…`, ELF,
  actual build inputs and B1 pins still match. No ARM rebuild occurred.
- Missing `b2_pins` is an explicit refusal. That intentional placeholder is not counted
  as a defect below. No committed B2 manifest exists and no board execution is cleared.

The independent probes never call `execute()`, open a port, provision a key, consume a
ruling or write a real manifest. Temporary documents labelled as test rulings and model
evidence are software fixtures, not owner authorizations or observations about silicon.

## P2-1. Record replay is being used as the final session verdict

`host/b2_runner.py:503–519` supplies `adj.adjudicate(..., scope="session")` directly to
`b1_session.run()`. The shared finalizer assigns the callback's outcome to the session
outcome. This adjudicator explicitly does not check the complete instrument/evidence
contract, and the runner callback adds no such checks.

With common validation enabled, the callback returns **PASS with zero findings** for:

| Record-complete synthetic log | Callback outcome |
|---|---|
| Record-only positive control | PASS |
| `session_summary` declares STOPPED; restore/unsigned control not reached | PASS |
| `session_summary` declares PROTOCOL; restore/unsigned control not reached | PASS |
| Every record marked `replayed-only`; no audit file supplied | PASS |

The control is a computational record fixture, not a complete valid session. Its purpose
is to show that adding explicit failed session state does not affect the current callback.
Common per-record validation does not establish TERM/closing, every required audit,
transport budgets, evidence sealing or invocation binding. Export completeness alone
also cannot establish those facts.

Compose the session-level acceptance checks with record replay before producing the
runner's final PASS. Require the expected successful epoch/record count, closing steps,
all-self-reporting audit coverage and integrity, transport constraints, sealed evidence
and this invocation's bindings. Preserve failed primary causes. Add a fully valid
offline session fixture through the production finalizer, then mutate TERM, closing,
audit coverage and bindings independently. The old record-only fixture should not be
promoted into a complete-session positive control.

## P2-2. The B2Q producer and lifecycle consumer cannot complete a positive transition

For B2Q, `adjudication_for()` returns `NOT ADJUDICATED HERE` unconditionally because
`round_plan` is null. This is not the result `b2_manifest.qualify()` requires.

Separately, the real `readjudicator()` can reproduce a correct B2Q record fixture, but
returns `session="B2"` and supplies neither `measured_rate_per_hour` nor `audit_policy`.
The lifecycle at `host/b2_manifest.py:530–534` requires the recomputed rate/policy to
agree with the evidence. An actual call to `qualify()` with this callback fails with
`the re-adjudication's measured rate / audit policy disagree with the evidence's adjudication`.
Using a stored-result test double hides this incompatibility.

A positive B2Q record fixture is possible for the current fixed inputs without changing
the reference orchestrator. The probe first asserts that the two derivations coincide:

- Qualification master: `505806527`.
- Qualification pair: `(3890725659, 1378470437)`.
- The unchanged reference's default derivation gives the same pair for this master.

It then generates and wraps the one-pair, budget-8 model records and runs the **real**
B2Q re-adjudicator: numerical PASS, followed by the actual lifecycle refusal above.
The derivation rules are not equivalent in general; equality was checked for this
specific fixture. The supplied rate in the lifecycle probe is synthetic, not measured
board throughput. The failure demonstrates missing result fields, not valid calibration.

Implement a B2Q session result with the correct session identity, checked evidence,
rate derived from timing evidence, and verified audit policy. Re-adjudication must
recompute those values, not echo `adjudication.json`. Demonstrate the complete offline
S1 → B2Q result → S2 → S3 path using the real callback and a complete timing/audit fixture.

## P2-3. A successful preflight reads a field absent from the pinned instrument

At `host/b2_runner.py:413`, `l6m["protocol"]["wire"]` raises `KeyError: 'wire'`.
The actual pinned instrument manifest's protocol object contains heartbeat, silence and
timeout fields; it has no wire selector. The probe reaches this failure using a genuine
fixture S1 manifest and actual image/build/B1-chain checks. Only missing pins and the
unrelated boundary/`sb` checks are doubled; no file in the instrument is edited.

Read the wire protocol from its correct pinned authority and add successful preflight
controls for both profiles. Pure component answers and refusal-only cases do not prove
that preflight can construct the configuration consumed by `b1_session.run()`.

## P2-4. The B2Q whole-of-run ruling does not bind its master seed

The call at `host/b2_runner.py:361–362` supplies the master seed only for SEARCH;
QUALIFICATION passes `None`. A B2Q whole-of-run test ruling naming the wrong master
therefore passes preflight unchanged.

This later branch was isolated with an explicitly labelled, read-only in-memory
`protocol.wire="rel-v4"` view to get past P2-3. The unchanged control and the wrong-seed
variant both pass. The absent pins and unrelated boundary/`sb` checks remain doubled.

Bind the B2Q whole-of-run ruling to the derived/frozen B2Q master as described by the
runner's own contract. Test missing and mismatched seeds for both profiles. This finding
does not assert a manifest-pin bypass: a manifest digest may imply deterministic inputs,
but it does not make a contradictory explicit ruling field acceptable.

## P2-5. The new `seeds` parameter is normalized before validation

`Replay.__init__()` at `host/b2_adjudicate.py:445` iterates `seeds` and calls `tuple(x)`
before the checks at lines 731–734. Public API calls with `seeds=7`, `[None]` or `[1]`
raise `TypeError`, contradicting the promised named refusal for malformed seed inputs.

Validate the outer container, every pair container and arity, and each unsigned 32-bit
value before conversion or lookup. Preserve the caller's rule responsibility, explicit
reported seeds and the distinct INTERNAL ERROR path for actual programming defects.
Add API/CLI malformed-container tests, not only length/value tests on iterable pairs.

## P3 boundary corrections

1. **Frame arithmetic counts the brackets twice.** `l6_schedule.expected_frames(n, …)`
   adds two baseline records. Passing `records_expected` instead of the non-bracket
   count makes B2Q declare 22 frame records for 20 actual records. Under rel-v4 the
   recorded calculation is 579 frames; the same helper with the correct argument gives
   543. Both yield CRC budget 3 here. Correct the units and test the exact by-type totals;
   this finding requests no budget relaxation.
2. **Infinite planning rate is accepted.** `--qual-rate-per-hour=inf` passes the positive
   float check and produces a 600-second deadline. Require a finite positive rate, and
   test the boundary independently of the protocol lookup. This observation uses the
   same explicitly labelled in-memory wire-selector double as P2-4.

## Design recommendations and disposition

Record B2Q's exact plan, prediction and pair seeds, their derivation/exclusions and the
planning-bound rule in S0; bind their bytes/digests at S1. Read the frozen B2Q documents
from the validated run manifest when re-adjudicating. This makes the qualification
experiment reviewable before the session that produces its calibration. It does not
require changing B1's transition rules or freezing a measured rate before it exists.

The proposed ruling names can remain interface proposals. Align their documented fields
with the parser, including B2Q master binding, before requesting real rulings. This review
does not issue or approve a ruling. Provide a documented B2Q CLI entry point when its
positive path is complete; `main()` currently defaults to SEARCH with no profile option.

Keep this batch under review and complete the offline positive/negative integration
fixtures before accepting it. `b2_pins` and `b2_test_report` remain unfinished; their
absence does not account for the defects above. Earlier adjudicator acceptance remains
valid within its record-replay scope.

Artifacts: [`evidence/b2/review_runner_2026_09_11/`](../evidence/b2/review_runner_2026_09_11/).
Only new review artifacts and the package status banner were written. No production code,
firmware, existing evidence, manifest, ruling or instrument file was modified. No commit,
push, ARM image build or board contact was performed.

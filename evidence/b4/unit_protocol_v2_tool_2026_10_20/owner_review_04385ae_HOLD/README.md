# Owner review of 04385ae — HOLD (2026-10-20)

Reviewed commit: `04385ae42373a4db33716f8aa5d6c58a4789de09`, parent `8361068`, branch `b4-protocol-v2`.
This is an independent engineering review of the host tool unit, not an exploration, gate result, or silicon claim.
No tracked file was changed. All generated batches used explicit already-exposed mechanics schedules in `/tmp`.
No production master/pair seed derivation, production preflight, smoke, run, push, merge, or board operation was performed.

## Independent checks

- Complete local suite: **313 tests, OK**, 606.832 seconds, on clean 04385ae. Exact command is in `review_metadata.json`.
- Author's e2e driver independently regenerated all seven cases; fresh-process verifiers accepted the expected records, rejected all six tampers and the named old archives. Driver exit 0, `as_expected: true`, production derivation calls `[0, 0]`.
- IMPORT: **58 entries match**, including base files and copied function digests; no tracked B4 file absent.
- Protected paths are unchanged from 8361068: the historical B3 paths; old B4 sim/gate archives; hypothesis; formal model/mapping/loaders; copied statistics and PRNG.
- Independent additional probes reproduced R1–R5 below. The complete and init-None cases use the **formal** v0.3 hypothesis and truth fabric, under a mechanics schedule; no mechanics alteration of the domain is needed.
- No independent rerun of all 36 submitted mutants: the complete test/e2e reruns and new counterexamples suffice for this HOLD. The author's mutant record is retained as the author's evidence, not represented as a reviewer rerun.

## Decisions

The proposed `import_table_sha256` projection onto **tool/schema entries only is ACCEPTED**. Tests are still held by the ordinary IMPORT check, but editing only a test need not change the method. This does not resolve R1.

The unit is **HOLD** on the following six reproducible findings. These are corrections inside the already-authorised tool unit, not a request for another scope proposal.

### R1 — P1 — document version remains coupled to method identity through source bytes

Locations: `b4/host/b4_protocol.py:145`, `b4/tests/test_b4_thresholds.py:82`, `b4/host/b4_thresholds.py`.

`digest_view` drops the top-level `architecture_revision`, but `inventory` and `import_table_sha256` still include the full bytes of the module declaring it. The pin test requires the current architecture heading to match that constant. Thus an ordinary document-heading revision either fails the static pin, or updating the corresponding informational constant and refreshing IMPORT changes the method digest.

Fresh interpreter, clone only: change `ARCHITECTURE_REVISION` from `v0.2.0` to `v0.2.1`, refresh just that tool entry's file digest, keep every method number and rule unchanged. The protocol digest changes from `2c207d51…` to `28cf2af9…`. The current dictionary-only test cannot exercise that dependency.

Required: make an actual documentation-only revision possible with green pins and unchanged method identity. Either source current informational provenance outside inventoried method bytes, or explicitly retain a frozen method-document reference without requiring it to equal every later heading. Keep real thresholds/code changes bound; do not solve this by dropping the thresholds module or the full tool inventory from integrity checks. Test the real file/IMPORT workflow in fresh interpreters, not only changing an already-built dictionary.

### R2 — P1 — returned target observations are discarded on failure

Locations: `b4/host/b4_target.py:83`, `b4/host/b4_sim.py:523`, `b4/host/b4_sim.py:529`.

Two independent returns are lost:

1. TARGET's second call returns a trace with a different valid-shaped fabric digest. The run correctly stops invalid, but there is no `target_holdout.json` **and no quarantine/raw-return record**.
2. TARGET's first call returns a malformed step (no `q_after`, carrying a unique marker). The run stops invalid with `KeyError`, but only the setup plan remains; no record holds the returned object.

Both archives currently verify clean. A refusal that returned nothing may legitimately have no raw result; a call that returned malformed/drifting data is different. The §7.1 persistence contract and existing quarantine discipline require retaining that evidence before abandoning processing or making the next call.

Required: retain each returned object, or a lossless supported quarantine representation with its findings, phase, identity and digests. Do not publish drifting/malformed data as a normal valid observation; invalid must still stop and never redraw. Add source-malformed, source-drift, malformed-grid and nonserialisable-return cases, including second-call failures, and fresh-process verification of the resulting invalid archives.

### R3 — P2 — target state/file contract rejects a real prefix and accepts an impossible one

Locations: `b4/host/b4_sim_verify.py:100`, `b4/host/b4_target.py:191`, the setup state transitions in `b4_sim.py`.

- A real `KeyboardInterrupt` immediately after the second target record is durably written produces `incomplete`, task `partial`, and both target files. Deep verification rejects `pair_000/target_holdout.json` as unaccounted for.
- Starting with a genuine invalid setup, remove `target_search.json`, retain the matching valid `target_holdout.json`, and refresh **all** report file hashes. Both API and fresh-process verifier return clean/exit 0, despite a later observation existing without its required earlier persisted result.

Required: hold setup states to the durable **ordered prefix**, including quarantine and invalid outcomes introduced by R2. Exercise interruption at every persistence boundary, not only during the second observe call. Later stages cannot exist without their prerequisites; genuine retained prefixes must reverify. Do not obtain this merely by allowing all setup files for every noncomplete state.

### R4 — P2 — a None in the target's unscored init row is silently accepted

Locations: `b4/host/b4_landscape.py:126`, `b4/host/b4_target.py:106`; architecture §7.1 explicitly says a formal target observation containing a None is invalid.

Change only TARGET's first returned grid cell at init step 0, element 0 to `None`; leave all scored cells intact. The batch finishes **complete**, task complete, and deep verification is clean. Validation checks only mask cells for the target rule, while the full grid validator permits None.

Required: enforce the approved target validity over the whole returned target grid, including init, on both producer and offline reconstruction. Retain the failed return and stop invalid. This does **not** change mask, ceiling, scoring, the model's init semantics, or the applicability of ordinary candidate observations.

### R5 — P2 — new go/no-go verifier does not hold namespace and exact metadata types

Locations: `b4/host/b4_gonogo.py:170`, `b4/host/b4_gonogo.py:348`.

On a cleanly verifying fixture decision, refresh MD and its file index after each alteration:

- `batch.count: 1 -> 1.0` is accepted although the source count and outer S are integer 1.
- `batch.fixture: true -> 1` is accepted.
- `batch.path: ../escaped_batch` points to an identical archive **outside the recorded repo root**. It is accepted, despite the publication contract requiring a direct `evidence/b4/sim/<label>_…` archive.

All three fresh-process verifications return exit 0 / clean true. The producer rejects such paths, so a validly produced record and an accepted altered record have different contracts. An unexpected empty subdirectory is also ignored by the API; see the preliminary probe results.

Required: use type-exact checks and canonical, in-root, direct namespace checks in the record validator and offline verifier, with the existing no-symlink policy. Hold the go/no-go directory's file set too. Negative fixtures must refresh all hashes and MD so they reach these rules rather than incidental stale-hash checks. Do not alter the policy numbers or decision rule.

### R6 — P2 — the advertised canonical fixture digest comparison is not reproducible

Location: `evidence/b4/unit_protocol_v2_tool_2026_10_20/e2e_fixtures_v02.py:61`, its README §2.

The independent regeneration reproduces the expected behaviour, but only **811 of 908 JSON canonical digests match; 97 differ**, with no missing expected files. For `complete` alone, 8 of 53 differ; for `complete_32`, 68 of 772 differ. `e2e_comparison.json` names each file.

Dropping UTC / HEAD fields does not remove their dependency chain: target files' raw digests are embedded in task documents, then pair indexes, reports and decisions; a changed hermetic HEAD similarly propagates into hashes and registry snapshots. Thus stripping the declared keys does not yield the claimed bit-for-bit comparable record.

Required: provide a deterministic regeneration/comparison procedure that actually validates its expected digest list, either controlling these fixture-only inputs or normalising the dependency graph explicitly. Preserve independent validation of every raw file hash/link. Do not simply drop all sha256/identity/binding fields or every semantic reason. Include a fresh-root, different-time repeat proving the comparison passes, and a semantic tamper proving it fails. Preserve and correct the old evidence rather than rewrite it.

## Correction authorisation and limits

Finish R1–R6 together in this unit, including necessary B4 implementation, tests, schema, IMPORT, docs and reproducible evidence. No new scope draft is needed for these corrections. Retain old logs and identify changed contracts. Run the affected negative tests/mutants during correction and the complete B4 suite plus required final host-logic mutant checks before resubmission, following the agreed proportionality rule; keep fixture archives regenerable rather than copying them all into Git.

This does not authorise production `b4-sim-4` / `b4-gate-2` preflight, derivation, smoke or execution, a model/domain/hypothesis/certificate/statistics/threshold revision, full proof, RTL, board/routing work, push or merge. Bring one complete corrected unit for review.

## Reproduction / provenance

`owner_probes.py` is the final standalone counterexample driver, run on 04385ae with an output directory under `/tmp`; it clones tool files for the identity probe and builds an explicit-schedule hermetic Git repo under `/tmp` for the batch probes. The original first probe attempt used a test helper expecting a complete pair index on an invalid archive and ended in that helper's FileNotFoundError. The final driver updates the stopped archive's actual report index directly and runs through cleanly; the earlier raw attempt is retained in `preliminary_probe_stdout.txt`.

`compare_e2e.py` compares only the declared JSON canonical entries in the submitted and regenerated records; per-file raw hashes are not expected to match across times/roots. `e2e_regenerated/` contains the driver's new digest records and fresh-process logs, not full generated fixture archives. The submitted driver remains in its original evidence path because its own source-root inference depends on that location.

The review directory is ignored and is not a commit or a push. Its `SHA256SUMS` covers the review artifacts; generated fixture archives remain under `/tmp` and are not part of the delivery. No scientific result is inferred from any fixture.

# B4 pre-work, unit 2b-2 follow-up 2 — the owner's HOLD on `8d2757a` (2026-10-18)

The owner's review (`build/wip/owner_review_8d2757a_2026_10_18/README.md`, ignored; its probe script copied here as
`owner_review_8d2757a.py`, re-run against this tree into `owner_probes_rerun.json`): one P1, two P2s, and the X-A
design ruling with five corrections. Fixed in the original unit's files; `8d2757a` and the earlier commits kept; the
formal model, the hypothesis and every old pinned input unchanged; nothing implemented for X-A; no exploration,
threshold or gate.

| # | gap | fix | regression |
|---|---|---|---|
| P1 | the source identity was the hypothesis and mapping headers only: `truth`, `permuted` and `dropout` fabrics under the formal hypothesis declared the same identity; a header `{"sha256": "x", "fixture": false}` completed a run and replayed | every `Fabric` carries a **source descriptor** — kind (truth / permuted / dropout / custom), the effect table's digest, the dropout set's digest and count, the seed — as DIGESTS only, in every trace header (`fabric`); the engine validates the whole identity on every observation with one validator (`b4_execution.provenance_findings`: exact fields, exact types, 64-hex digests, `fixture` a bool and never coerced), refuses a malformed or drifting identity as a `SourceRefusal` by its own name, binds it into `result.provenance` and every ledger entry, and surfaces the hypothesis-fixture (`fixture`) and the fabric-fixture (`fabric_fixture`) markers separately; the replay validates the same way | `test_b4_replay.Replay.test_the_fabric_identity_tells_truth_permuted_and_dropout_apart` (three identities, no address / semantic string in any result), `test_a_malformed_source_identity_is_a_named_refusal_and_replays` (the owner's header, a header without `fabric`, a coerced `fixture`), `test_b4_execution.ThePort.test_the_source_identity_validator_is_exact`, `test_b4_ff_model.TheTrace.test_the_trace_header_names_the_fabric_by_digests_only` |
| P2 | the replay port re-raised every non-DOMAIN refusal as `ModelRefusal`, so a recorded `ValueError` (the provenance drift included) did not replay | refusals are recorded under a **finite set of kinds** (`ValueError`, `ModelRefusal`, `SourceRefusal`; `b4_execution.refusal_kind`) and re-raised by kind (`raise_refusal`), never by importing a name; an unknown kind in a record is a named finding | `test_legitimate_non_domain_refusals_replay_by_their_recorded_kind` (a drift as `SourceRefusal`, a `ValueError`, a `ModelRefusal` each replay with no finding; an unknown kind and a wrong attempt are named) |
| P2 | the structural validation was not total: a list as `terminal`, an empty q grid, a string genome and `{"groups": []}` raised uncaught exceptions; `completed = 1` passed as True | `shape_findings` validates every field of the record, every ledger entry, every q grid (rows against the phase's public stimulus, cells 0 / 1 / None, ints never bools), the terminal event, the refusal, the given view and the source identity BEFORE anything is hashed, indexed, scored or reconstructed; the comparison is type-exact (1 is not True); the re-execution runs inside a boundary that turns an internal error into a finding distinct from a refusal; a malformed record is always a named finding | `test_malformed_records_are_named_findings_never_exceptions` (the owner's five cases and fifteen more) |
| X-A | the note claimed a derangement of addresses destroys the grouping | **design text only** (`x_control_design.md`): a derangement does not guarantee a changed partition — the counterexample (swap within every pair, rotate the five-address group: no fixed point, the same partition) is written in; π is fixed blind from the control seed before any map and never redrawn or rejected after inspecting the partition or the null result, every generated seed / permutation retained; residual structure reported post hoc and never fed back; the full per-specimen isomorphism (address identities, cells, presence, counts, contexts, evidence references, states, version, multi-bit count); the true candidate kept in the ledger; the lane permutation described as a symmetry check of the relation / partition structure with no trajectory-equality claim; the tests to write at implementation (a partition-changing fixture AND the partition-preserving counterexample) | none — nothing implemented; the owner's counterexample probe reproduces (`owner_probes_rerun.json`: fixed points `[]`, same partition true) |

## Tests (`tests.txt`)

The ten B4 modules: **Ran 92, OK**, zero skip (86 before).

## Mutants (`mutants.txt`; `build/wip/scratch_2026_10_17/b4_2b2_mutants.py`, ignored)

**32 / 32 killed**: the twenty-seven of the previous rounds (two anchors re-aimed after the edits) and five for this
one — the fabric identity dropped from the trace header, the engine accepting any non-empty identity, the replay port
re-raising every refusal as `ModelRefusal`, `completed` accepted as an int, the shape validation skipped.

## The owner's probes, re-run (`owner_probes_rerun.json`)

`provenance_drift` is recorded as `SourceRefusal` and replays with no finding; `ValueError` replays by name; the five
malformed records are each a named finding; the malformed identity is a `SourceRefusal` at attempt 1 with no
provenance and no ledger, and replays; the old fixes (forged generator pair, F map history, pending children) still
named; the shuffled oracle keeps privilege and chain; the holdout contract holds. The probe's `effect_identity`
comparison reads only the `hypothesis` and `mapping` keys and therefore still reports the three headers equal — the
identity that now differs is the `fabric` key beside them (effect digest for `permuted`, dropout digest and count for
`dropout`), which `test_the_fabric_identity_tells_truth_permuted_and_dropout_apart` holds. IMPORT digests match.

## The authenticity limit, restated

The replay proves the internal execution sequence from the declared inputs and the recorded observations. A record
that relabels a refusal's kind within the finite set, or rewrites its message, is a consistent record and
reconstructs; so does a source that told a consistent lie about its identity. These are outside what a ledger-only
replay can decide and are stated as such (`test_legitimate_non_domain_refusals_replay_by_their_recorded_kind`).

## What this establishes, and only this

Mechanisms, on fixtures, with the record replayable by re-execution, its source identified by digests and validated,
and malformed records refused by name. The design is **not gate-ready** (the frozen arm's probe pass under the formal
hypothesis; X-A unimplemented); nothing about silicon; no threshold, no exploration.

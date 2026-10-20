# B4 pre-work, unit 2b-2 follow-up — the owner's HOLD on `2eae943` (2026-10-18)

The owner's review (`build/wip/owner_review_2eae943_2026_10_18/README.md`, ignored; its probe script copied here as
`owner_review_2eae943.py`, re-run against this tree into `owner_probes_rerun.json`): three P1s, one P2. Fixed in the
original unit's files; `2eae943` and the earlier commits kept; the formal model, the hypothesis and every old pinned
input unchanged; no exploration, no threshold, no gate.

| # | gap | fix | regression |
|---|---|---|---|
| P1-1 | the replay recomputed selected ledger facts and did not regenerate the search / termination state: the terminal candidate, its identity fields, both generator states forged together, the pending children, the population, a forged parent / move, a fabricated champion, the counts / cost / final map state and a corrupted F probe-pass map history all passed | **replay as re-execution** (`b4/host/b4_replay.py`): the engine is run again from the declared inputs against a `ReplayPort` that serves the ledger's q grids in order, raises the recorded refusal at its attempt and holds every call to the record (config and stimulus digests; no observation beyond the ledger); the whole result is compared field by field; the structural checks (digests, fitness arithmetic, the terminal event's consistency) run first; the authenticity limit is stated in the module — the internal execution sequence is proved, the observations' origin is bound and checked, not re-derived | `test_b4_replay`: the owner's nine tampers each named; the earlier sixteen still named; the replay port refuses anything not in the ledger; clean replays of R / O / F / X / D / A0, of runs terminated at the base, in the probe pass, mid-generation and at the holdout, of the formal F run and of an other-refusal run |
| P1-2 | the result and ledger carried neither the hypothesis's digest nor its fixture marker; `shuffled_view(oracle_view(...))` came back unprivileged and without its parent | the observation source's identity (hypothesis path / sha256 / version / fixture, mapping site / certificate sha256) is taken from the first observation, required equal on every later one, kept in `result.provenance`, surfaced as `result.fixture`, and bound into every ledger entry (`provenance_sha256`, `fixture`); `MapView` carries a provenance chain and a base commitment, a transformation never drops its parent, and a shuffled oracle stays privileged (`("oracle", "shuffled")`); a given view is recorded whole (`given_view`) and reconstructed by the replay | `test_b4_engine.CompleteRuns.test_the_observation_source_is_bound_into_the_result` (the fixture and the formal hypothesis told apart by the result alone; a drifting source refused by name), `test_given_views_carry_their_provenance`, `test_b4_carto.ControlX.test_a0_d_and_omega`, `test_b4_replay.Replay.test_provenance_is_bound_and_checked` |
| P1-3 | the implemented X permutes the eight visible lanes, which relabels elements but keeps the partition of addresses the operator uses — a symmetry control, not the negative control K2 / K3 name | **no change** (design review first, as ruled): `x_control_design.md` — why the lane permutation is a symmetry control; option X-A (address relabelling before the cartographer, shadow isomorphism under π over genome bits; recommended), X-B (keep the lane permutation as a separate symmetry test "S"), X-C (cell scrambling; not recommended); nothing implemented or explored | the architecture's §8 row now states the status; the hand-ledger probe stays reproducible (`owner_probes_rerun.json`: same partition, isomorphism holds) |
| P2 | a DOMAIN at the holdout left a champion the replay then rejected | the contract: the champion is fixed when the search loop completes (`search_completed`); a DOMAIN at the holdout terminates the run with phase `holdout`, keeps the champion as the search's result, leaves `champion_holdout` None and `completed` False; the structural replay allows a champion iff the terminal phase is `holdout` | `test_b4_engine.Termination.test_domain_at_the_holdout_keeps_the_search_s_champion_without_a_holdout_score`, `test_b4_replay.Replay.test_the_holdout_contract` |

## Tests (`tests.txt`)

The ten B4 modules: **Ran 86, OK**, zero skip (80 before the follow-up).

## Mutants (`mutants.txt`; `build/wip/scratch_2026_10_17/b4_2b2_mutants.py`, ignored)

**27 / 27 killed**: the twenty-two of 2b-2 (two anchors re-aimed after the edits) and five for the follow-up — the
replay without re-execution, the replay port serving whatever is asked, the source identity not recorded, a shuffled
oracle losing its privilege and chain, a holdout DOMAIN leaving the run completed (a first version of that mutant was
equivalent — the Terminated branch reset the flag — and was rewritten to disable the reset).

## The owner's probes, re-run (`owner_probes_rerun.json`)

All nine replay tampers now named (the terminal candidate: "the terminal candidate / stimulus is not what the
re-execution asked for"; both generator states: "result.rng_state_final: recorded '0', reconstructed …"; the pending
children and the population: length differences; the forged parent / move, champion, counts / cost / map state and the
F probe history: field differences). The fixture marker and the hypothesis digest are in the serialised result and in
every ledger entry. `shuffled_oracle_privileged` is true. The X probe is unchanged by design (same partition,
isomorphism holds) — the design note is the deliverable for it. IMPORT digests match.

## What this establishes, and only this

Mechanisms, on fixtures, with the record now replayable by re-execution and its source bound. The design is **not
gate-ready**: the frozen arm cannot complete its probe pass under the formal hypothesis (an accepted design
limitation), and X carries no negative-control reading yet. No threshold, no exploration, nothing about silicon.

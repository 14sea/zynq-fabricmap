# B4 pre-work, unit 2b-2 — the pure-function implementation (2026-10-18)

The owner's authorisation of 2026-10-18 on the revised scope (`build/wip/b4_2b2_scope_draft_2026_10_18.md`, ignored)
with five rulings: (1) the 21 addresses and the formal hypothesis kept — no reading added, no universe narrowed, no
candidate filtered by diagnostics; (2) a DOMAIN keeps the measured prefix and the terminal state, adds nothing to a
curve, drops no seed, and an incomplete pair never yields a primary PASS; (3) the public task and the all-zero base
(a declared choice; all-one would be permutation-invariant and in the domain too), fixed M / t / w, None scoring
nothing and moving no ceiling; (4) the revised scope's sections 5–6; (5) the order: this implementation → 2b-3
(thresholds, τ, the incomplete-run policy, the seed anchor, one commit) → exploration under its own authorisation →
2b-4 gate. **Nothing here is an exploration, a gate number or a threshold.** Branch `b4-prework`.

| file | what | derived from |
|---|---|---|
| `b4/host/b4_rng.py` | the line's PRNG | `host/b1_carto.Rng`, behaviourally equal (tested by import of the pinned original, read-only) |
| `b4/host/b4_execution.py` | `ObservationPort` (observe + addresses, nothing else; `__slots__`), `SpyPort`, `PublicTask`, `TerminalEvent`, `observe_candidate` (DOMAIN → the event with the state BEFORE the call; any other refusal by its name) | new |
| `b4/host/b4_landscape.py` | task-v0.1: stimulus (init, K = 6 alternating clock steps, 2 input-only steps), M = every readout cell after init, t random bits, w = 1, from the landscape seed alone; the holdout stimulus its own derivation (K = 8); scoring | new; imports neither the mapping nor the hypothesis (an AST scan is a test) |
| `b4/host/b4_engine.py` | (μ, λ) = (4, 8), KMAX = 4; R / F / O / X; F's map from a seeded single-flip probe pass then frozen, or a given view with its provenance (A0 / D / privileged Ω); DOMAIN termination; the ledger with map versions and commitments; generation closes; the holdout once | `host/b2_search.py` |
| `b4/host/b4_carto.py` | the observation cartographer (single-bit pairs under one stimulus → seen cells / presence / no effect seen / context-dependent / unknown; multi-bit pairs counted, never decomposed; no semantic claim), the operator's disjoint groups, the v3 draft's shape check, control X (B3's derangement rule, lane permutation, shadow isomorphism), A0, D, Ω (privileged, marked) | `b3/host/b3_control_x.py` (the control-X contract) |
| `b4/host/b4_replay.py` | EXACT replay from the task and the ledger alone | new |
| `b4/host/b4_stats.py` | the four-corner index and the four per-seed outcomes; τ a parameter without default; all S in the denominator | new |
| `b4/schemas/self_map_v3.schema.json` | the draft: observation relations, groups, `semantic_claims` empty, `host_verdict` null | new; v2 untouched |

## The DOMAIN semantics as implemented (`b4_engine.run`)

Every observation — base, probe, search candidate, holdout — goes through `observe_candidate`. On the first DOMAIN the
run terminates: the event records the phase, the attempt ordinal, the candidate's and stimulus's digests, the seeds,
the budget, the successful observations, the generator's state and the population's and map's commitments **as they
stood before the refused call**; the candidate has no fitness, no specimen, no place in the population; the
generation's successful children stay `pending_children` and no generation close is written; nothing is drawn,
observed, scored, selected or learned afterwards (`port.calls == attempt`, `rng_state_final == terminal.rng_state`,
the live cartographer holds exactly the ledger's specimens); the best-so-far is the measured prefix. Any other
refusal is `other_refusal` by its own name. A completed run scores its champion on the holdout once.

**A fact, recorded as such (`test_under_the_formal_hypothesis_f_s_probe_pass_terminates_at_the_latch_flip`):** under
the formal hypothesis, from the all-zero base, the frozen arm's probe pass terminates at the single flip of the LATCH
address in whatever order — F cannot complete its mapping phase on this design. The engine does not skip it (a
mutant that skips is killed): that would be filtering by what cannot be observed.

## Tests (`tests.txt`)

The ten B4 modules (2b-1's three and 2b-2's seven): **Ran 80, OK**, zero skip. Complete runs are exercised under a
MARKED mechanics fixture (the latch's clock bit 0 read as not inverted, so the domain has no hole; it says nothing
about the fabric — `b4/tests/b4_test_fixtures.py`); the DOMAIN semantics under injection at the base, in the probe
pass and mid-generation; the cartographer on hand ledgers (every expected relation by hand) and over the model's
fixtures (the permuted fabric's relations follow the observation, dropout gives no effect seen, a hypothesis swap
changes a relation); X's derangement by hand against B3's rule and the shadow isomorphism; the replay on complete and
terminated runs with sixteen named tampers; the four-corner computation on hand fitnesses; the capability spy (an
engine run touches `observe` and `addresses` only; a read of anything else from outside the port is recorded).

## Mutants (`mutants.txt`; `build/wip/scratch_2026_10_17/b4_2b2_mutants.py`, ignored)

**22 / 22 killed**: redraw after DOMAIN; the refusal swallowed and scored; selection continuing on the pending
children; the map updated after DOMAIN; the trace padded to the budget; the generator advanced; another refusal
folded into DOMAIN; the port exposing the fabric; the engine reading beyond observe / addresses; the task generator
importing the mapping; None = None scored; a multi-bit pair decomposed; a no-effect pair made permanent; X's
permutation not applied; the isomorphism ignoring the permutation; the frozen arm still learning; the oracle view
unmarked; the replay not checking fitness / accepting a terminated run as completed; a not-assessable seed judged
additive; the four corners varying a third bit; the probe pass skipping what it cannot observe. Three first-round
survivors (the post-DOMAIN map update hidden behind multi-bit distances; a mutant that could not run under
`__slots__`; the spy blind to its own counter) were closed by `map_specimens_final`, a meaningful fabric-exposure
mutant and a spy that records only accesses from outside the port.

## What this establishes, and only this

Mechanisms, on fixtures: the boundary, the termination semantics, the public task, the cartographer's rules, the
controls and the replay. No landscape has been explored, no seed scanned, no threshold or τ set, no S > 1 run made;
nothing about silicon; the observation that F cannot complete a probe pass under the formal hypothesis is a
consequence of rulings 1–3 and is reported, not worked around.

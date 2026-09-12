# The S3 slice P2 — corrected, 2026-09-12

The owner's review: `docs/b2_stage_split_review_2026_09_12.md`, against `4f27ffa`, with its
reproduction in `evidence/b2/review_stage_split_2026_09_12/`. The S0→S1 finding is **closed**;
this is the one that remained, and again it is the test, not the manifest.

`committed_args` supplied a constant `pair_first=0, pair_count=4` for every B2 invocation. B2's
session split is **derived from the B2Q calibration** (`b2_plan.session_split`), so how many pairs
a session holds is a measured consequence, not an invariant of the experiment — and `(0, 4)` is
only what the fixture's default 2807/h happens to give. Three other legally verified S3 manifests
therefore refused at

    the slice (0, 4) is not one the plan's split gives

*before* the missing-ruling gate the test exists to reach.

## The correction

`committed_slice(manifest)` reads the slice from the manifest's **own verified pinned plan** —
never a constant, never inferred from a rate — and returns the **last** session, so a split with
more than one session is not exercised only at its first. A manifest with no plan pinned has no
slice at all (`(None, None)`): preflight refuses at its stage long before it reads one.

## The four rates, now passing, and visibly different

`StageCoverage.test_it_passes_at_every_split_a_calibration_can_give`, and the owner's own script
re-expressed as acceptance in `acceptance_split.py` / `acceptance_split.json`:

| fixture rate | the split it gives | slice the test asked for | first session? | their run at `4f27ffa` | now |
|---|---|---|---|---|---|
| 2 807/h | `[0-3] [4-7] [8]` | `(8, 1)` | no | PASS | **PASS** |
| 602/h | nine one-pair sessions | `(8, 1)` | no | **FAIL** | **PASS** |
| 4 490.86/h | `[0-6] [7,8]` | `(7, 2)` | no | **FAIL** | **PASS** |
| 6 000/h | one nine-pair session | `(0, 9)` | yes (it has no other) | **FAIL** | **PASS** |

The test asserts the four rates give **four different splits** — otherwise it would say nothing
about splits — and that wherever a split has more than one session the slice is **not** its first.

These are synthetic FIXTURE rates, with the B2Q evidence and the re-adjudicator explicitly
stubbed: test readiness, never a measured rate and never a qualification. **4 490.86/h is the
modelled virtual-clock artefact** and appears only because the split rule accepts it; it is not a
calibration and nothing here uses it as one.

## That the fix is load-bearing

`StageCoverage.test_a_constant_slice_would_not_survive_another_calibration` puts the old constant
back behind a patch, on a legal 602/h S3, and **requires the failure** —
`the slice (0, 4) is not one the plan's split gives`. The owner's reproduction is kept as a test,
so the constant cannot come back unnoticed.

The S0/S1/S2 stage checks and all the illegal-state cases are unchanged; `StageCoverage` is now
**10 tests**.

## Regenerated, before any qualification

The pinned test changed, so the table and the still-unfrozen S0 were regenerated — the order the
review asked for, so that no pinned input has to change *after* B2Q, which would invalidate the
strict qualification transition.

| | before (`4f27ffa`) | now |
|---|---|---|
| pin table | `50cb6f5a1d141d18bd011938355f6f900e25dcb40c1e8f2a2aa2e647c8793116` | **`8d6f64a5fed1fa222b2c29a0dddac6c6fd3346b23481ade1f00a3f104a907ebf`** |
| manifest | `848f56528b129939d4d6bfd8d016e455789d958af180033ed668de811a62d140` | **`86393ed781cb25c971aeb7a4ea3bf485b5aba5a353ef94968b3128050d5b2da1`** |
| files verified | 71 B2 + 105 B1 | **71 B2 + 105 B1** |
| preregistration | `68cde86d…` | **unchanged, still not pinned** |
| image / ELF | `d164cd1d…` / `7de96ed2…` | **unchanged** |

`verify_s0.json`: stage S0, qualified false, refusal null; the state fields untouched
(`prereg.sha256` null, `frozen` false, `board_ready` false, `qualified` false,
`qualification`/`calibration`/`plan` null, `history` empty). **No firmware, image, preregistration,
instrument or ruling was touched — the accepted image compatibility conclusion is unaffected.**

Focused suite **451 tests, zero skips, OK** (449 before: +1 split coverage, +1 constant-slice
control). The S0/S1 acceptance script was re-run at the new hashes and still passes. No freeze, no
ruling, no push, no board.

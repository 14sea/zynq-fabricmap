# The S0 transition P2 — corrected, 2026-09-12

> **The hashes in "Regenerated, and the new hashes" are superseded.** The owner's stage/split
> review then found a P2 in the same test's S3 slice; correcting it changed a pinned test again,
> so the table is now `8d6f64a5fed1fa222b2c29a0dddac6c6fd3346b23481ade1f00a3f104a907ebf` and the
> manifest `86393ed781cb25c971aeb7a4ea3bf485b5aba5a353ef94968b3128050d5b2da1` — still the same
> unfrozen S0, same state fields, same image and preregistration. See
> `../corrections_stage_split_2026_09_12/`. Everything else here stands, and `acceptance.json`
> has been re-run at the new hashes.

The owner's review: `docs/b2_s0_transition_review_2026_09_12.md`, against `fa0271e`, with its own
reproduction in `evidence/b2/review_s0_transition_2026_09_12/`. **The S0 manifest itself was
accepted; the defect was in the test I added with it.**

`RefusalOrder.test_the_committed_manifest_is_not_permission` read the committed manifest and
required S0's values unconditionally. A valid S1 freeze — one production `verify` accepts —
changes three of them and moves preflight past the gate the test expected, so the test made the
promised post-freeze green suite impossible, and its `qualified` / `plan` assertions would have
collided with S2 and S3 as well. The name stated a true principle; the hard-coded stage did not
establish it across the lifecycle.

## What replaced it

| | |
|---|---|
| `stage_findings(m, stage)` | one contract, four stages: which fields each stage licenses to be set, what `status` and `history` must then say, and that a frozen preregistration is the file on disk. Not a second copy of `verify` — verify re-derives the frozen inputs from live bytes and re-adjudicates the qualification; this is the consistency between a manifest's stage and its own fields |
| `STAGE_GATE` | which gate refuses each (stage, session): the stage's own reason where the stage is the gate, and **`no readable ruling at`** at the stage each profile is otherwise eligible for — S1 for B2Q, S3 for B2 |
| `test_an_s0_fixture_is_exactly_the_initialisation_contract` | the exact S0 values, asserted exactly, **on a fixture built by the production `b2_manifest.init`**. There they are the initialisation contract and cannot go stale; on the committed manifest they expire at the freeze |
| `test_the_committed_manifest_is_a_legal_stage_and_is_not_permission` | reads `rn.MANIFEST`, whatever stage it has reached: production `verify` accepts it, its own fields agree with the stage verify reports, and **with no ruling to consume the runner refuses it** — which gate depends on the stage, that one does not |
| `StageCoverage` (8 tests) | drives that test against real manifest files at S0, S1, S2 and S3 and requires it to PASS, then against four illegal manifests and requires it to FAIL for each one's named reason |

The missing-ruling refusals stay where the review asked: on fixtures —
`test_the_rulings_must_exist_be_this_text_and_be_bound` (S3: absent, wrong text, wrong binding,
wrong seed, already consumed) and `test_the_stage_each_profile_requires` are unchanged.

### The coverage, and that it discriminates

    python3 -m unittest tests.test_b2_runner.StageCoverage     ->  Ran 8 tests ... OK

| driven against | required | why it is the case it is |
|---|---|---|
| S0, S1, S2, S3 fixtures | **passes** | the transition the owner is about to make, and the two after it, keep the suite green |
| S0 claiming `board_ready` | fails: `board_ready is True` | `verify` does not read `board_ready` at S0; the stage contract does |
| S1 with `history` emptied | fails: `history records []` | the freeze happened or it did not; `verify` does not read `history` at all |
| S2 wearing `S1 FROZEN` as its status | fails: `does not begin with S2` | |
| S3 with the plan dropped but still logged | fails: `history records` … `S3 plan` | `verify` reports S2 for it, which on its own fields would be legal — the log is what says a plan was pinned and is missing |
| S1 frozen with a null digest | fails: `b2_manifest.Refusal` … `the frozen preregistration file is absent or changed` | not every illegal state is this table's to catch; production `verify` refuses first and the test carries that refusal instead of swallowing it |

Two seams, both named: the manifest path the test reads, and the re-adjudicator — a fixture's B2Q
evidence is a stub log the REAL adjudicator must refuse, which is what
`test_the_real_readjudicator_refuses_a_qualification_it_cannot_reproduce` establishes, and that
test stays. The committed-manifest test itself uses the runner's production hook.

## The owner's reproduction, inverted

`acceptance.py` is their `review_s0_transition.py` with the structure unchanged — production
`verify` and `freeze` only, a deep copy, a temporary file, nothing written to the production
manifest — and the assertions inverted, as their README says they must be after the correction.
Their script cannot simply be re-run: the test it names no longer exists, so `acceptance.py`
asserts that too.

`acceptance.json`:

| | their run at `fa0271e` | now |
|---|---|---|
| the S0-only test is gone | — | **true** |
| the test on the real S0 | 0 failures, 0 errors | **0 failures, 0 errors** |
| `verify` on the frozen deep copy | S1 accepted | **S1 accepted** |
| the test on the temporary S1 | **1 failure** (`'68cde86d…' is not None`) | **0 failures, 0 errors** |
| the production manifest's bytes | unchanged | **unchanged** |

The S1 preview hash is diagnostic only and is **not stable between runs** — `freeze` stamps the
transition with the time it happened. It is not a binding and must never be used as one.

## Regenerated, and the new hashes

The pinned test changed, so `verify` refused until the table was regenerated and the still-unfrozen
S0 was re-derived — the review asked for this order, before any qualification, so that later
pinned-file edits cannot invalidate an accepted qualification transition.

| | before (`fa0271e`) | now |
|---|---|---|
| pin table `manifests/b2_instrument_pins.json` | `e848325308ee31cf479b733bd6bd93cde466991b86bb424a70c9ed81e2d8a232` | **`50cb6f5a1d141d18bd011938355f6f900e25dcb40c1e8f2a2aa2e647c8793116`** |
| manifest `manifests/b2_manifest.json` | `af2717476a518f3fcb31d5c76599a17585367fdc421f9607b06aaca424924540` | **`848f56528b129939d4d6bfd8d016e455789d958af180033ed668de811a62d140`** |
| files verified | 71 B2 + 105 B1 | **71 B2 + 105 B1** (unchanged count) |
| preregistration | `68cde86d3f3decaf9775beac94c59731ada486ebe246006e7243156c084db8e0` | **unchanged, still not pinned** |
| image / ELF | `d164cd1d…` / `7de96ed2…` | **unchanged** |

`verify_s0.json` is the production `verify` at the new hashes: stage S0, qualified false, refusal
null. The state fields are untouched — `prereg.sha256` null, `prereg.frozen` false,
`image.board_ready` false, `qualified` false, `qualification`/`calibration`/`plan` null, `history`
empty. **Image compatibility is unaffected: no firmware, image, instrument or ruling was touched.**

Focused suite: **449 tests, zero skips, OK** (440 before: −1 removed, +2 committed/fixture, +8
coverage). No freeze, no ruling, no push, no board.

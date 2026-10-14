# B3 lifecycle 2 — the S2 and S3 clean-tree proofs: an explicitly named exception to preregistration §8's verification procedure (2026-10-14; the second defect added at S3 the same day)

**Standing: the formal S2 clean-tree proof did NOT pass.** `evidence/b3/tests/test_report_2026-10-14T144023Z.json`
(run at `d2ac67d`, the S2 qualify commit; `clean_tree_proof = false`, ten `proof_refusals`) is archived as
written and its verdict is not changed. The S2 transition itself stands on the production verify — a fresh
process reports S2 / qualified true / refusal null / manifest `bea08769c4adb86a20654d455b79e015973192c67bf62199a91c561e97ecab8f`
before and after the proof run — and the owner, having reproduced the failure and its cause independently,
rules this an **engineering-acceptance exception**: a listed exception to the frozen preregistration's §8
verification procedure for lifecycle 2 from S2 onward. It is not a statement that the formal proof is
satisfied, and it changes no scientific criterion, no pin, no manifest binding and no B3Q evidence.

## What failed, exactly

The proof tool ran its three fixed suites on the clean tree. `b2_tree` (2 096 tests) was OK. `b3_tree`
(793) and `b3_removal` (792) each ended `FAILED (errors=1)` on **one** test, the same in both:

```
ERROR: test_the_committed_split_is_what_the_stage_licenses (test_b3_plan.Committed…)
  b3/tests/test_b3_plan.py:523  stage, manifest = committed_stage()
  b3/tests/test_b3_plan.py:80   bman.verify(manifest, root=TREE["root"], seams=TREE["seams"])
  b3/host/b3_manifest.py:970    check_qualification(...)
  b3/host/b3_manifest.py:843    Refusal: S2: the pinned B3Q evidence re-adjudicates to
        'KILL falsified: (vii) seq 1: nonce_before is not the model chain value 0000000000000000', not PASS
```

Every other criterion of the proof held: one `Ran` line per suite, no skips or failures, the discovery
sentinel listed once in `b3_tree` and absent from `b3_removal` (793 → 792, the listings otherwise identical),
the start and end snapshots equal (HEAD `d2ac67d`, both worktrees clean, the instrument at `689dde1`, the
88-file pinned surface identical, every required artefact present with the same digest), the pinned surface
`manifest_bound` to `bea08769…`.

## The cause — a fixture-path contamination inside the test process, reproduced

`b3/tests/test_b3_lifecycle.py` builds a `World` (a temporary tree carried S0 → S3 through the production
command line) and, in `World.__init__`, patches the runner's B1-manifest path onto that tree:

```python
self._patch = mock.patch.object(rn, "B1_MANIFEST", self.root / bman.B1_MANIFEST_REL)
self._patch.start()
```

`world()` returns a **process-wide singleton** (`_WORLD`), and the patch is stopped only by
`atexit.register(_WORLD.close)` — at interpreter exit, not at the end of the test or the module. In a
discovery run the order is `test_b3_lifecycle` → `test_b3_plan.Committed` → `test_b3_plan.StageCoverage`:
the lifecycle tests create the World first, so from then on `b3_runner.B1_MANIFEST` names the fixture's B1
manifest (`/tmp/b3life_*/manifests/b1_manifest.json`) for the rest of the process; the contamination comes
from the lifecycle tests that ran earlier (`StageCoverage.setUp` also calls `life.world()`, but it runs
after `Committed` and only reuses the same singleton). The committed-state test runs the
**production** verify on the real tree; at S2 (and at every later stage: `b3_manifest.verify` re-adjudicates
the pinned B3Q evidence whenever `stage >= "S2"`) that verify calls the production re-adjudicator, whose
`instrument_findings` reads the model nonce chain's seed from `B1_MANIFEST["carrier"]["nonce_seed"]`
(`b3/host/b3_runner.py:769`). The real B1 manifest's seed is `0x9e3779b97f4a7c15`; the fixture's is
`00000000`. The model chain therefore starts at zero, the first record's `nonce_before` does not match, and
the re-adjudication is a KILL under rule (vii) — a verdict about the fixture's seed, not about the session.

Reproduced three ways: (1) `python3 -B -m unittest b3.tests.test_b3_plan.Committed` alone in a fresh
process — **2 tests, OK** (145 s), the same test included; (2) in one process, importing
`test_b3_lifecycle`, calling `life.world()` and reading `rn.B1_MANIFEST` — the fixture path, seed
`00000000`; (3) the owner's independent reproduction: with the real World's patch still in force after
`tearDownModule` the same nonce KILL appears, and with the real B1 path restored the full verdict returns
to PASS.

Why the S0 and S1 proofs (`test_report_2026-10-13T140003Z.json`, `test_report_2026-10-14T090238Z.json`)
passed: before S2 `verify` does not re-adjudicate, so the leaked path was never read. Why B2's S2 proof
passed: B2's lifecycle test does not patch the runner's path, and `b2_runner` reads
`b2_manifest.B1_MANIFEST`.

The §9 pre-freeze audit (`docs/b3_lifecycle2_pinned_test_audit_2026_09_27.md`) and its delta
(`…_delta_2026_10_13.md`) did not catch this: it is a test-isolation defect, not a stage-literal one, and
it is latent until a stage at which the committed verify re-adjudicates.

**The defect, precisely, for the next lifecycle:** the patch's lifetime is the process's instead of the
test's. The isolation to adopt: scope `World`'s `rn.B1_MANIFEST` patch to the tests that use the World
(start it in `at()` / per-test `setUp` and stop it in cleanup, or make `committed_stage` run the production
verify with `rn.B1_MANIFEST` explicitly restored to the repository path), and have the §9 audit check every
`mock.patch(...).start()` for a matching stop within the test or the module. The files are
`b3/tests/test_b3_lifecycle.py` (`World.__init__`, `World.close`, `world()`) and
`b3/tests/test_b3_plan.py` (`committed_stage`). **They are pinned (`b3/**/*`) and are not changed in
lifecycle 2**: a pinned edit after S0 regenerates the table and the S0 / S1 manifests, and the two B3Q
sessions and the S2 record are bound to the S1 manifest `bb917ec7…`. Rebuilding the lifecycle would not
void that historical B3Q evidence; it would mean it could no longer be bound automatically to a new freeze.

## The owner's exception, as ruled (2026-10-14)

1. **Every scheduled proof node still runs the formal tool and archives its result as written** —
   `clean_tree_proof` false stays false. The exception applies **only** when the failure is confined to the
   reproduced fixture-path contamination above (that test, that `Refusal`, in `b3_tree` and `b3_removal`
   alike); any other error, failure or refusal is outside this authorisation and is reported.
2. **At each such node, a supplementary verification is performed afresh**: the complete plan module
   (`b3.tests.test_b3_plan`) in its own process on the original tree and in a removal shadow, then that
   stage's fresh-process verify. It is bound to that node's HEAD, manifest digest and the unchanged pins;
   the S2 supplement below is not reused for a later node.
3. **The shadow is built by the formal tool's own `b3_test_report.build_shadow`**; its path, construction
   record and removal are recorded.
4. The defect's location, the patch's lifetime and the isolation to adopt are recorded (above).
5. `README.md`, the evidence READMEs and the eventual result document keep the two statements apart:
   *engineering acceptance under this exception* versus *the formal clean-tree proof did not pass*. The
   archived JSON verdicts are never edited.

The exception extends to lifecycle 2's later proofs (S3, final) for the same failure only. The pins
(`73cec93a…`), the manifests, the B3Q bindings and the scientific criteria are unchanged.

## The second defect — the seed header's plan digest (named at S3, 2026-10-14)

**Standing: the formal S3 clean-tree proof did NOT pass.** `evidence/b3/tests/test_report_2026-10-14T180234Z.json`
(run at `2f8ff58`, the S3 plan commit, 15:39:21Z – 18:02:34Z; `clean_tree_proof = false`, twelve `proof_refusals`)
is archived as written. `b2_tree` (2 096) OK; `b3_tree` (793) and `b3_removal` (792) each ended
`FAILED (failures=2, errors=1)`: the error is the first defect above (that test, that `Refusal`), and the two
failures are new, the same in both suites:

```
FAIL: test_the_seed_header_is_a_fresh_render_byte_for_byte (test_b3_orch_twin.TheBuildAndTheSeedHeader…)
FAIL: test_the_unchanged_plan_renders_the_committed_header (test_b3_orch_twin.TheGeneratorChecksThePlanAgainstTheGate…)
  b3/tests/test_b3_orch_twin.py:248 / :306   self.assertEqual(HEADER.read_text(), gen.render(…))
```

Both hold the pinned `b3/firmware/b3_seed_data.h` byte for byte to a fresh render by the production generator
`b3/host/gen_b3_seed_data.py`. The generator's `inputs()` writes the plan file's digest into the header's
"source binding" block (`#define B3_SEED_PLAN_SHA256 "<sha256 of evidence/b3/plan.json>"`). The header was
rendered at image stage 4 (`0fe24b0`, 2026-10-01) from the rate-less plan `fbd922ba…`, which was unchanged
through S0, S1 and S2 (no commit between `0fe24b0` and `e6ba9a2` touches `evidence/b3/plan.json`); the S3
transition necessarily rewrites the plan (`session_split`, `generated_utc`) and so its file digest (`b202a280…`),
so from S3 on these two tests cannot pass with the header as pinned. The S2 proof ran both as `ok`. It is a
stage-latent defect of the same class as the first: a pinned test correct for the pre-S3 tree and not stage-aware,
not caught by the §9 audits (the delta of 2026-10-13 classed these tests as "the current tree only" and audited the
plan's perturbation on a temporary copy, not the committed plan's own digest changing at S3) nor by the S3 scope
draft, which foresaw only the first defect.

What the macro is and is not: nothing in `b3/firmware/*.c`, `*.h` or `b3/host/*.py` reads `B3_SEED_PLAN_SHA256`
(the generator alone writes it); the header's data — the excluded set, the B3 and B3Q profiles, the instrument
commit, the gate report's digest — is identical in the committed header and the fresh render. The committed header
`e3eb2b84…` is the one the pin table (`73cec93a…`) and the build evidence (`evidence/b3/build_evidence.json`,
`sources.b3_seed_data.h`) bind, and the image `28c80eca…` was built from it. The production verify at S3 passes.

**The fix, for the next lifecycle:** bind the header to its build-time source or to a field that genuinely does
not change with the stage — not to the plan file's digest. (The plan without `generated_utc`, `6267c8f7…`, is not
stage-invariant either: it contains `session_split`, which S3 determines.) The files are
`b3/host/gen_b3_seed_data.py` (`inputs()`, `render()`), `b3/firmware/b3_seed_data.h` and
`b3/tests/test_b3_orch_twin.py`; all pinned, none changed in lifecycle 2.

### The owner's extension of the exception, as ruled (2026-10-14)

Having independently confirmed the fresh verify (S3 / true / null), that the complete re-render differs in
exactly the `B3_SEED_PLAN_SHA256` line, that the old value is the pre-S3 plan's and the new value the current
manifest's plan pin, and that the macro has no consumer, the owner **narrowly extends** the engineering-acceptance
exception to this second defect, from S3 on, for these two named tests and later identical failures. The first
defect's conditions above are kept unchanged. For the second defect, at each proof node:

1. The failed report is committed as written; `clean_tree_proof` false stays false.
2. The supplementary verification keeps the complete fresh header, the diff, the inputs' digests and the checks'
   results. It ACCEPTS only when the committed header and the fresh render differ in **exactly that one line**,
   the old digest equals the historical plan's (`fbd922ba…`) and the new digest equals the manifest's plan pin,
   and the committed header still equals the pin table's and the build evidence's digest. Anything else is a
   named refusal.
3. Negative controls accompany it on temporary copies: a second changed line, and a digest that does not match,
   must each be refused.
4. The first defect's supplement is repeated under its own rules (the plan module in its own process on the tree
   and on a formal removal shadow, then a fresh verify). **No claim is made that a separate process makes the two
   header tests pass** — they fail in any process while the header is pinned as it is.
5. `README.md` and the evidence READMEs list both defects and keep *engineering acceptance under this exception*
   apart from *the formal clean-tree proof did not pass*. Any other failure is still reported, not accepted.

## The S2 supplementary verification (the S2 node)

Recorded in `evidence/b3/s2_2026_10_14/proof_exception/`: `inputs.json` (HEAD, the digests of the manifest,
the pin table, the plan and prediction documents, the B3Q documents, the build evidence, the B1 manifest,
the four modules involved, and every file of the qualification evidence), `test_b3_plan_tree.txt` and
`test_b3_plan_shadow.txt` (the raw verbose logs), `shadow.json` (the shadow's path and `build_shadow`'s
record), `exit_codes.txt`, `verify_after_supplement.json`, `started_utc.txt` / `finished_utc.txt`.

| run | where | result |
|---|---|---|
| the plan module, original tree | cwd the repository, HEAD `d2ac67d`, own process | **Ran 32 tests in 190.052 s — OK**, 32 `ok`, zero skips / failures / errors; `test_the_committed_split_is_what_the_stage_licenses` passes (the production verify inside it reports S2) |
| the plan module, removal shadow | `/tmp/b3_removal_control_ukehtkuo`, built by `b3_test_report.build_shadow` (the sentinel `test_b3_sentinel.py` not linked, every other entry linked back), removed afterwards (`shadow_removed=true`) | **Ran 32 tests in 191.203 s — OK**, 32 `ok` |
| fresh-process verify, after both | `python3 -B b3/host/b3_manifest.py verify` | **S2 / qualified true / refusal null / `bea08769c4adb86a20654d455b79e015973192c67bf62199a91c561e97ecab8f`** |

Window 15:02:26Z – 15:11:40Z on 2026-10-14; at the start no tracked file was modified, while the untracked
paths listed in `inputs.json` existed (this exception's own outputs and the archived failed report) — not a
clean worktree in the proof tool's sense. The inputs' digests are in `inputs.json`:
the manifest `bea08769…`, the pin table `73cec93a…`, `b3/tests/test_b3_plan.py`, `b3/tests/test_b3_lifecycle.py`,
`b3/host/b3_manifest.py`, `b3/host/b3_runner.py`, `b3/host/b3_test_report.py`, the plan / prediction / B3Q
documents, the build evidence, the B1 manifest and the sixteen files of `evidence/b3/b3q_17A6_2026-10-14-02/`.

**What this establishes, and only this.** The one test the formal run could not complete passes in both
contexts the formal run uses when it is not sharing a process with the lifecycle World, and the production
verify at this node is S2 with no refusal. It does not make the archived report a proof; the exception is
what accepts S2 for engineering purposes, and the next proof node (S3) repeats this supplement afresh.

## The S3 supplementary verification (the S3 node)

Recorded in `evidence/b3/s3_2026_10_14/proof_exception/`, HEAD `2f8ff58`, manifest `258bb14c…`, pins `73cec93a…`
(`inputs.json` carries the digests of the manifest, the pin table, the plan and prediction, the B3Q documents, the
build evidence, the B1 manifest, the gate report, the header, the generator and the six modules involved, and every
file of the qualification evidence; the worktree had no modified tracked file, only this node's untracked outputs
and the archived failed report).

| run | where | result |
|---|---|---|
| **defect 2** — the production generator's own check, read-only | `python3 -B b3/host/gen_b3_seed_data.py --check` | `STALE: b3/firmware/b3_seed_data.h is not a fresh render`, exit 1 (`gen_check.stdout`) — the formal failure reproduced directly |
| the complete fresh render | `header_check.py render` (the generator's `render(inputs())`, `inputs()` validating the plan against the gate) | `b3_seed_data.fresh.h`, 382 lines, sha256 `61c59b33…` (`header_render.json`) |
| the check | `header_check.py check` against the committed header, the manifest, the pin table and the build evidence | **ACCEPT**: exactly line 19 differs (`header.diff`); committed `fbd922ba…` = the historical plan, fresh `b202a280…` = the manifest's plan pin; committed header `e3eb2b84…` = pin table = build evidence (`header_check.json`) |
| the negative controls | `header_check.py controls`, four mutants in a temporary directory, removed afterwards | **all four refused by name** (`header_controls.json`): a second changed line (`B3_PROFILE_B3_BUDGET` 1000→1001: "2 lines differ, not exactly one: [19, 24]"), a fresh digest that is not the pin, a committed digest that is not the historical plan (also refused as not the pin table's / build evidence's), a wrong historical digest |
| **defect 1** — the plan module, original tree | cwd the repository, own process | **Ran 32 tests in 197.508 s — OK** (`test_b3_plan_tree.txt`); the committed-split test passes with the production verify reporting S3 |
| the plan module, removal shadow | `/tmp/b3_removal_control_jkrgp6ki`, built by `b3_test_report.build_shadow` (sentinel not linked), removed afterwards | **Ran 32 tests in 198.663 s — OK** (`test_b3_plan_shadow.txt`, `shadow.json`) |
| fresh-process verify, after both | `python3 -B b3/host/b3_manifest.py verify` | **S3 / qualified true / refusal null / `258bb14c4b3ba1a3d33741f23b1663f563de64da800843d30c8a615e2f128628`** (`verify_after_supplement.json`) |

Windows: the plan module and the verify 18:17:30Z – 18:29:04Z; the header checks 18:30:01Z – 18:34:39Z. The first
header attempt (18:17Z) failed on a bug of the checker script itself — its JSON record overwrote the fresh render —
and is kept as observed in `header_attempt_1_script_bug/`; the script was corrected and re-run, the tree untouched
throughout (`header_git_status_after.txt`). `header_check.py` is this node's evidence, not an instrument: it lives in
the evidence directory, reads the tree, mutates copies only in a temporary directory.

**What this establishes, and only this.** The header's divergence from a fresh render is confined to the plan-digest
annotation, whose two values are the two plans the lifecycle has carried; the header the image was built from is
the pinned one; the first defect's test passes outside the shared process; the production verify at this node is
S3 with no refusal. It does not make the archived report a proof. The final proof node repeats both supplements
afresh.

## The final proof's position (the owner's ruling of 2026-10-14, after S3)

Preregistration §8 orders "the final proof" before any B3 ruling pair. The owner rules that the accepted S3 proof
node — the formal report `evidence/b3/tests/test_report_2026-10-14T180234Z.json` archived as failed, and the two
supplements above — serves as that node's **engineering acceptance**; the formal clean-tree proof is **not passed**,
and no identical full run is repeated for the position alone. Both named exceptions continue to apply to any later
proof node of lifecycle 2 for the same failures only; any other failure is reported, not accepted. The main-experiment
preparation that follows is recorded in `evidence/b3/main_preparation_2026_10_14/README.md`.

# B3 lifecycle 1, unit 1 — the pinned-surface audit (host-only, 2026-09-17)

> **v1.1 (the owner's review of `c648d6e`, 2026-09-17: inventory and the 20 probes accepted,
> direction 2b + 3 accepted, unit HELD on four P2s).** Closed in this follow-up: (1) P-F1 is now
> resolved by a completion-input archive, not merely recorded (§6, P-F1); (2) P-F2 becomes a rule
> the B3 verifier must satisfy — every indirect frozen input is checked by existence and digest
> *before* the B2 verify is called, so a missing file is a named B3 refusal and never an inherited
> `FileNotFoundError` (§7a); (3) the B3 pin rule `b3/**` was wrong — `Path.glob("b3/**")` yields
> directories only — and is replaced by `b3/**/*` filtered to regular files, with the negative
> tests it requires (§7, candidate 3); (4) the planned test command `discover -s b3/tests -t .`
> does not run without packages — the measured, working form is chosen and the test report gets a
> discovery sentinel and a removal control (§7, candidate 2b). Measurements in
> `evidence/b3/lifecycle1_pinned_surface_audit_2026_09_17/glob_and_discovery.json` and
> `evidence/b2/b2_completion_inputs_2026-09-17/runs/`. `c648d6e` is kept as is; the original 15
> files, the B2 pins / manifest and the frozen B3 wrappers are untouched.

Branch `b3-lifecycle-1`, base **`73b68d7`** (`main` = `origin/main`, the B2 completion merge: parents
`4800c15` + `4cbeef2`, tree `84e8220…` = `b2-lifecycle-2`'s). Host-only: this unit adds one
document and one evidence directory and changes **nothing else** — no B3 code, no test, no B2
pin, no manifest, no preregistration, no evidence rewrite, no ruling, no push, no board. Every
mutation this audit needed was made in a **throwaway detached worktree** of `73b68d7` under the
session scratch directory and removed afterwards; the main working tree's tracked content was
asserted clean and at `73b68d7` before and after (`evidence/b3/lifecycle1_pinned_surface_audit_2026_09_17/results.json`
`main_tree_before` / `main_tree_after`).

## 0. Standing

The owner's condition for opening B3 (2026-09-17): the first unit is a host-only audit of the
structural problem left by B2, and until the audit passes review **no B3 code is changed, no pin
table is regenerated, no S0 is initialised and no board is touched**. This document is that unit.
It proposes; it authorises nothing.

## 1. The question

The B2 instrument pin table (`manifests/b2_instrument_pins.json`, sha256
`82a5f2fb1d246c9cab506df65d53a0f329ca219ec3c5cdf50a272ff79ee319d1`, 71 files, 19 globs) is
pinned by the closed B2 manifest (S3, `aec84514ff29dda7957d46d650a370e155f6dc60a281b992e148f8a0fae6c4c0`).
Two of its globs, `host/b3_*.py` and `tests/test_b3_*.py`, capture B3's host reference and its
test; three B3 files are pinned by name and hash. **Any B3 development in place therefore makes the
completed B2 refuse to verify on the current tree.** The audit has to establish exactly what is
bound, prove the refusal is real and named, inventory what B3 depends on and what depends on B3,
rule between the candidate ways of isolating B3 from B2, and fix the order of the B3 lifecycle so
that lifecycle 1's mistake (a stage-constant test frozen at S1) is not repeated.

## 2. Baseline and closing verification

The production S3 verify (README "Verify it yourself"), run on `main` at `73b68d7` with the tree
clean, before anything was written (`verify_baseline.json`) and again after everything was written
(`verify_closing.json`):

| | stage | qualified | refusal | manifest sha256 | pins verified |
|---|---|---|---|---|---|
| baseline, `73b68d7` clean | S3 | true | null | `aec84514…` | 71 B2 files, 105 B1 files, table `82a5f2fb…` |
| closing, `73b68d7` + this unit's two untracked paths | S3 | true | null | `aec84514…` | same |
| closing v1.1, `c648d6e` + the follow-up's paths (`verify_closing_v1.1.json`) | S3 | true | null | `aec84514…` | same |

## 3. The surface as it stands (read from the table, not from memory)

- `host/b2_pins.PINNED_GLOBS` has 19 entries; the two that reach B3 are **`host/b3_*.py`** and
  **`tests/test_b3_*.py`**. Both are non-recursive (`Path.glob`): they match files directly under
  `host/` or `tests/` whose names start with `b3_` / `test_b3_`. A subdirectory (`host/b3/…`,
  `tests/b3/…`), a top-level directory (`b3/…`), `docs/b3_*`, `schemas/*`, `evidence/b3/*` are not
  matched (proved in §6, probes 14–20).
- `b2_pins.verify` refuses, in this order and each by name: a table not hashing to the manifest's
  pin; a malformed table; **a pinned file whose hash differs**; **a pinned file that is missing**;
  **a file matching a glob that the table does not list**; B1's table drifting under it. It stops
  listing after five drifts, so a large refactor reports the first five names.
- The B2 manifest verify calls it inside `_check_frozen_inputs`, *before* the stage logic, so a
  pinned-surface drift is a `b2_manifest.Refusal` raised by `verify()`, not a `refusal` field in a
  returned S3 record. `b2_runner.preflight` and every S2/S3 test fixture inherit the same check
  (`docs/b2_lifecycle2_pinned_test_audit_2026_09_16.md` F2).
- `tests/test_b2_pins.py:36` (`test_the_generated_table_covers_the_decision_surface`, itself pinned)
  asserts that `host/b3_online.py` **must** be in the generated table. So even a B2-side edit of
  the globs to release B3 would fail a frozen B2 test — a second, independent reason that the B2
  surface cannot be "opened" for B3 from inside.

## 4. Inventory — B3 material at `73b68d7` (`inventory.json`)

| path | tracked | in B2 table | how bound | role |
|---|---|---|---|---|
| `host/b3_online.py` (`fd2f2759…`) | yes | **yes** | by name and by glob `host/b3_*.py`; named in `tests/test_b2_pins.py:36` | the specimen cartographer, the online arm, ledger entries (v1.1) |
| `host/b3_sim.py` (`bdfcc5fe…`) | yes | **yes** | by name and by glob | the three-arm simulation and report |
| `tests/test_b3_online.py` (`7ea1ef61…`) | yes | **yes** | by name and by glob `tests/test_b3_*.py`; run by every B2 whole-suite proof (`unittest discover -s tests`) | 17 tests (cartographer, online arm, ledger replay, schema, the review's counterexamples, the ideal-model regression); green at the base (`Ran 17 tests … OK`) |
| `docs/b3_architecture.md` | yes | no | — (pinned by nothing; referenced by README, `docs/b2_package.md`, the frozen test's docstring) | design v0.1.1 |
| `schemas/specimen_ledger.schema.json` | yes | no | **read by the frozen test** `test_ledger_validates` — an edit that breaks its validation turns a B2-frozen test red without any PinRefusal | `specimen_ledger` 1.0.0 |
| `evidence/b3/sim/sim_report.json` | yes | no | **bound through the B2 plan**: `host/b2_plan.FROZEN_SEED_SETS` (pinned code) reads its `seeds.master_seed`/`count` to build the exclusion set; the B2 manifest `seeds.excluded_frozen_sets`, `evidence/b2/plan.json` and `evidence/b2/b2q_plan.json` record the result; `qualification_plan_pin` rebuilds it on every verify | the v0.1 simulation (HEAD `c6e3705`, clean tree, master seed 3 829 368 064, 200 seeds) |
| `evidence/b3/sim/raw_F1.json`, `raw_F2.json` | yes | no | `raw_F1.json` **read by the frozen test** `test_ideal_model_run_is_unchanged_by_the_correction` (skips if absent); both re-summarised by `evidence/b2/review_2026_09_10/recompute.py` | per-seed rows |
| `evidence/b3/sim_v0.1.1/*` | yes | no | read by nothing in the B2 verify or suite (probe 19); historical evidence | the v1.1 identity re-run (HEAD `fcfff981`, **`worktree_dirty_at_start: true`**, same seeds, bit-identical rows) |

The two image binaries the verify hashes (`firmware/b1/bsp/out/b1_app.bin`,
`firmware/b2/bsp/out/b2_app.bin`) are present in the working tree and gitignored, as their
manifests state.

## 5. Dependency scan

**B3 → B2/B1 (imports, by content).** `host/b3_online.py` imports `b1_carto`, `b2_landscape`,
`b2_search`, `b2_maps`; `host/b3_sim.py` imports `b1_model`, `b2_gate`, `b2_landscape`, `b2_maps`,
`b2_search`; the test imports `b1_carto`, `b1_model`, `b2_landscape`, `b2_search`. Every one of
these modules is in the B2 table (`host/b2_*.py`) or the B1 table (`host/b1_*.py`). B3's F arm *is*
B2's arm B on the same engine (`b2-es-v1`, μ 4 / λ 8 / kmax 4) over the B1 map `c6a4b23e…`; B3
cannot be built without these modules, and a B3 whose pinned surface did not cover them would be
the lifecycle-1 defect in another form.

**B2 → B3 (what the closed B2 holds onto).** Five bindings, all found by the scan
(`inventory.json` `b2_to_b3_references`):

1. the three pinned files and the two globs (§3);
2. `tests/test_b2_pins.py:36` naming `host/b3_online.py` as mandatory;
3. `host/b2_plan.py:63` `FROZEN_SEED_SETS` → `evidence/b3/sim/sim_report.json`, mirrored in the
   manifest's `seeds.excluded_frozen_sets`, `evidence/b2/plan.json:132` and the B2Q plan;
4. the frozen test's two committed reads: `schemas/specimen_ledger.schema.json` and
   `evidence/b3/sim/raw_F1.json`;
5. the owner-review evidence scripts `evidence/b2/review_2026_09_10/{recompute,reproduce_findings}.py`
   import `b3_online` / `b3_sim` by module name and re-summarise `evidence/b3/sim/*`. They are
   evidence, not verify inputs; they reproduce only against the frozen modules and rows.

**Stage assumptions in the B3 test as frozen.** `tests/test_b3_online.py` reads no manifest, plan
or pin table; its two committed reads (4.) are stage-invariant for B2 (B2 defines no transition
that changes them) and were 0-skip in every B2 proof. They are, however, **B3-owned files frozen by
B2**: B3 must keep both byte-stable (§7, rule I-4).

## 6. Throwaway probes (`probe_pinned_surface.py` → `results.json`, `probe.log`)

Method, per probe: `git worktree add --detach <scratch>/wt/<name> 73b68d7` with
`GIT_LFS_SKIP_SMUDGE=1` (LFS payloads stay pointers — the verify hashes none); restore the inputs a
checkout lacks (the two image directories and the 13 gitignored files the B1 table pins, by digest
— except in probes 2 and 3, which restore nothing / only the images); apply one mutation; run the
production verify in a subprocess with the worktree as `REPO_ROOT` and cwd; run the
`host/b2_pins.py` CLI; record; `git worktree remove --force`. 20 probes, 43 s, **20/20
expectations met**, main tree clean before and after, `git worktree list` back to one entry.

| # | probe | mutation | verify outcome | `b2_pins.py` exit |
|---|---|---|---|---|
| 1 | `control_no_mutation` | none, all 15 non-tracked inputs restored | S3 / true / null / `aec84514…`, 71 + 105 files, table `82a5f2fb…` | 0 |
| 2 | `control_fresh_checkout_nothing_restored` | none; the bare checkout | `Refusal: image: the image binary 'firmware/b2/bsp/out/b2_app.bin' is absent — the declaration is not evidence that it exists` | 0 |
| 3 | `control_fresh_checkout_images_only_restored` | none; only `firmware/*/bsp/out/` restored | `Refusal: instrument pins: B1's instrument pin table: pinned files changed: vivado/carrier/generated/clockInfo.txt: missing; … vivado.jou: missing; … vivado.log: missing; … vivado_1012301.backup.jou: missing; … vivado_1032984.backup.jou: missing` (five named, then it stops) | 2 |
| 4 | `modify_host_b3_online` | one comment line appended | `Refusal: instrument pins: pinned files changed: host/b3_online.py: hash differs` | 2 |
| 5 | `modify_host_b3_sim` | same | `… host/b3_sim.py: hash differs` | 2 |
| 6 | `modify_tests_test_b3_online` | same | `… tests/test_b3_online.py: hash differs` | 2 |
| 7 | `delete_host_b3_online` | deleted | `… host/b3_online.py: missing` | 2 |
| 8 | `delete_host_b3_sim` | deleted | `… host/b3_sim.py: missing` | 2 |
| 9 | `delete_tests_test_b3_online` | deleted | `… tests/test_b3_online.py: missing` | 2 |
| 10 | `add_host_b3_glob_match` | new `host/b3_lifecycle1_probe.py` | `Refusal: instrument pins: files matching the pinned globs are not in the table: ['host/b3_lifecycle1_probe.py']` | 2 |
| 11 | `add_tests_test_b3_glob_match` | new `tests/test_b3_lifecycle1_probe.py` | `… not in the table: ['tests/test_b3_lifecycle1_probe.py']` | 2 |
| 12 | `modify_evidence_b3_sim_report_master_seed` | `evidence/b3/sim/sim_report.json` `seeds.master_seed` + 1 | `Refusal: evidence/b2/b2q_plan.json is not the canonical B2Q plan: ['seed_derivation.excluded_frozen_sets.evidence/b3/sim/sim_report.json.master_seed: 3829368064 != 3829368065']` (raised in `qualification_plan_pin`, i.e. at the frozen-input check, before S3) | 0 |
| 13 | `delete_evidence_b3_sim_report` | `evidence/b3/sim/sim_report.json` deleted | **`FileNotFoundError`** from `b2_plan.frozen_seed_exclusion` — an unhandled implementation exception, **not a named refusal** | 0 |
| 14 | `neg_add_host_b3_subdir_module` | new `host/b3/online.py` | S3 / true / null | 0 |
| 15 | `neg_add_tests_b3_subdir_test` | new `tests/b3/test_online.py` | S3 / true / null | 0 |
| 16 | `neg_add_toplevel_b3_dir` | new `b3/host/online.py` | S3 / true / null | 0 |
| 17 | `neg_modify_docs_b3_architecture` | one line appended | S3 / true / null | 0 |
| 18 | `neg_modify_schemas_specimen_ledger` | one line appended (the JSON stays valid) | S3 / true / null | 0 |
| 19 | `neg_modify_evidence_b3_sim_v011_report` | `sim_v0.1.1/sim_report.json` `seeds.master_seed` + 1 | S3 / true / null | 0 |
| 20 | `neg_add_evidence_b3_new_dir` | new `evidence/b3/lifecycle1_probe/x.json` | S3 / true / null | 0 |

Probes 4–11 are what the owner asked for: modifying, deleting, and adding under each glob all
produce a **named** refusal from the completed B2's S3 verify (and exit 2 from the pin CLI).
Probes 14–20 are the negative controls the isolation decision (§7) rests on. (The pin CLI checks
only the table, so probes 2, 12 and 13 exit 0 there: the refusal is the manifest verify's.)

### Findings from the probes

**P-F1 — the B2 S3 verify is not reproducible from a checkout of `73b68d7` alone** (probes 2
and 3). The bare checkout refuses at the first frozen-input check, the absent B2 image binary
(`firmware/b2/bsp/out/b2_app.bin`, gitignored by design). With the two image directories restored
it refuses at B1's pin table: the B1 glob `vivado/carrier/generated/*` pinned **13 gitignored
files** (`*.jou`, `*.log`, `clockInfo.txt` — `.gitignore` lines 16, 17, 22) that exist only in this
workstation's working tree. With all **15 non-tracked inputs** restored it verifies (probe 1). The
B2 table itself pins nothing untracked. This is a B1-era condition B2 inherited by pinning B1's
table by content; it is frozen and is not to be repaired here. It bears on candidate 1 in §7.

*Resolved (v1.1) by the completion-input archive unit* `evidence/b2/b2_completion_inputs_2026-09-17/`:
`inputs.tar.zst` (sha256 `20300d5f2476beafaa9411c11f2a412eb91f01149bf4318e79ccee2706337767`, 99 325
bytes; the 15 files, 666 808 bytes, relative paths, deterministic ustar + zstd, rebuilt
byte-identically on repeat) and `archive.json` (sha256
`ca5fedd7bb7a119883a5b74a9f19b0d02d147e6183404ddde8766b03abd46c5d`: every member's bytes, sha256,
why it is needed and the pin it equals). `restore_verify.py`, in a fresh detached checkout of
`73b68d7` under `env -i PATH=/usr/local/bin:/usr/bin:/bin`, refused to overwrite nothing, restored
exactly 15 files, verified each by size and digest before and after writing, and the production B2
verify then gave **S3 / true / null / `aec84514…` / table `82a5f2fb…` / 71 files**
(`runs/positive_env_i.json`, 3.1 s). Negative controls (`runs/summary.json`, 7/7 as expected):
a member missing and one byte changed, each refused first by the outer archive digest and — with
the outer digest patched to match — by the per-member check naming `clockInfo.txt`; a target
already holding the files (`refuses to overwrite`, nothing written); a target at `4800c15`
(`target HEAD … is not the base`). Nothing pinned changed: the archive is additive and each member
hashes to the digest the frozen tables / manifests already carry. **The B3 S0 manifest pins
`archive.json` and `inputs.tar.zst` by content** (§7a, §8 step 4); candidate 1's checkout is now
the commit plus this archive, both in the repository.

**P-F2 — deleting `evidence/b3/sim/sim_report.json` is refused by accident, not by name** (probe
13). The frozen `b2_plan.frozen_seed_exclusion` reads each `FROZEN_SEED_SETS` path without an
existence check; `plan_findings` catches only `Refusal`/`ValueError`, so the verify dies with
`FileNotFoundError` instead of naming the missing frozen input. Modification (probe 12) *is* named.
Practical consequence for B3: `evidence/b3/sim/` is a B2 verify input and must never be moved,
renamed or rewritten; new B3 simulations go elsewhere (probe 20). The gap in `b2_plan.py` is a
pinned-file matter for a future B2-line unit, not for B3. *What B3 must do about it (v1.1):* the
B3 verifier may not inherit that bare exception — it checks every indirect frozen input by
existence and digest **before** calling the B2 verify, and names the one that is missing or
drifted (§7a).

**P-F3 — the B2 surface is exactly as narrow as its globs** (probes 14–20). Subdirectories under
`host/` and `tests/`, a top-level `b3/`, `docs/b3_*`, the ledger schema, `evidence/b3/sim_v0.1.1/`
and new `evidence/b3/` directories are invisible to B2. Isolation by namespace needs no change on
the B2 side.

## 7. Candidate isolation — comparison and ruling

| candidate | what it does | verdict |
|---|---|---|
| **1. B2 reproduces only at a checkout of `73b68d7`** (tag the commit; let the working tree drift) | keeps B2's proof where it was taken | **Not sufficient alone; kept as the reproducibility record.** (a) A checkout does not verify without the 15 non-tracked inputs (P-F1): the "frozen tree" is the commit **plus** a restore list, which this audit now documents; the two read-only backups (`/home/test/fabricmap_backups/b2_17A6_2026-09-1{6,7}-01/`) hold only the session archives; as of v1.1 the 15 inputs are archived in the repository (`evidence/b2/b2_completion_inputs_2026-09-17/`, P-F1) and a checkout plus that archive verifies under `env -i`. (b) README's "Verify it yourself" and every B2 ruling bind to the manifest sha and re-check the *current* tree; letting `main` drift off the B2 surface would make the published verify instruction false on `main`. An annotated tag `b2-complete` at `73b68d7` is recommended as an owner action; it is not created by this unit. |
| **2. Keep the frozen wrappers; put the new B3 implementation in a namespace the B2 globs do not capture** | `host/b3_online.py`, `host/b3_sim.py`, `tests/test_b3_online.py` stay byte-frozen as B2 pinned them (historical host reference v1.1); B3 lifecycle 1 develops in a namespace outside `host/b3_*.py` / `tests/test_b3_*.py` | **Adopted.** Proved by probes 14–16. Two layouts qualify: **2b, a top-level `b3/`** (`b3/host/`, `b3/tests/`, `b3/schemas/`, `b3/firmware/` …) or **2a, subpackages** (`host/b3/`, `tests/b3/`). **Ruling: 2b.** It is the layout the negative control 16 proved, it makes the boundary visible in every path, and it keeps `unittest discover -s tests` (what every B2 proof runs) from silently absorbing B3 tests: Python 3.12 does not discover namespace packages, so `tests/b3/` would need an `__init__.py` to be found by the B2 discovery and would then be run inside any future B2 whole-suite proof. **The B3 test command is `python3 -B -m unittest discover -s b3/tests`** (no `-t`, no package files) — measured to run the sentinel test (`glob_and_discovery.json` `discovery` A); the form first written here, `-s b3/tests -t .`, fails with `Start directory is not importable` unless `b3/__init__.py` and `b3/tests/__init__.py` exist (B, C), and is not chosen. B3's test report runs both start directories (`-s tests`, then `-s b3/tests`) and must carry a **discovery sentinel and a removal control**: a named sentinel test must appear in the verbose listing, the parsed `Ran N tests` must count it, and the same command over a temporary copy with the sentinel file removed must run exactly one test fewer (measured: A `Ran 1 test`, E `Ran 0 tests` after removal; and B2's `-s tests` discovery never sees `b3/`, D). An empty `OK` is not a proof. |
| **3. A B3 pin table and manifest of its own** | `b3/host/b3_pins.py` → `manifests/b3_instrument_pins.json`; `b3/host/b3_manifest.py` → `manifests/b3_manifest.json` | **Adopted, together with 2.** B3 needs its own authority regardless. Its pin rule is **`b3/**/*` filtered to regular files** (`.pyc` and `__pycache__` excluded) plus its normative documents — *not* `b3/**`, which `Path.glob` expands to directories only and would pin no file at all (measured: `glob_and_discovery.json` `glob`; `b3/**/*` filtered reaches depth 1, 2 and 4). `b3_pins.py`'s tests must prove that a new file at the top level (`b3/x`), at the second level (`b3/host/x`) and deeper (`b3/tests/deep/deeper/x`) each refuses as *not in the table*, and that a directory alone pins nothing; the B2 modules B3 imports (`host/b2_search.py`, `b2_landscape.py`, `b2_maps.py`, `b2_gate.py`, `host/b1_carto.py`, `b1_model.py`) are pinned **by content** through `manifests/b2_instrument_pins.json` and `manifests/b2_manifest.json` — exactly as B2 pins B1's table — and the B3 verify re-runs the B2 S3 verify (`S3 / true / null / aec84514…`) the way B2 re-runs B1's chain. Any B2-surface drift then refuses B3, which is right: B3's F arm is B2's arm B. |
| **4. Regenerate the B2 pin table, edit its globs, or touch the B2 S3 manifest** | "release" B3 from inside B2 | **Not adopted, in any variant** — including a "one-time refresh" mechanism, a `PINNED_GLOBS` edit, or a re-pin followed by a new `instrument_pins` sha. The S2 rule licenses only {qualification, qualified, calibration, plan, status, history} to differ from `manifest_at_run`; a new table sha makes the B2Q record and both B2 session rulings records for another manifest; `tests/test_b2_pins.py:36` fails on a glob edit anyway. This is the owner's containment decision of 2026-09-16 applied to B3. |
| (considered) **a separate repository for B3** (the standing preference for cross-project work) | pin `zynq-fabricmap` at `73b68d7` the way the instrument is pinned at `689dde1` | **Not adopted for lifecycle 1**, owner may override. B3 is the roadmap's third stage of this line, imports the B2 engine by content, runs on the B1 carrier under the B1 lineage and the same instrument, and its evidence chain continues B1/B2's. A second repository would have to re-implement the lineage verification (image, carrier, B1 chain, B2 S3, the 15 non-tracked inputs) against a pinned checkout, splitting the evidence trail. Candidate 2b gives the same visible boundary inside the repository. |

**Rules the ruling imposes on every later B3 unit (I-1 … I-6):**

- I-1 `host/b3_online.py`, `host/b3_sim.py`, `tests/test_b3_online.py` are **never edited, moved
  or deleted** on this line. The new implementation starts as a copy under `b3/`.
- I-2 No new file may match `host/b3_*.py` or `tests/test_b3_*.py` (probes 10–11).
- I-3 `evidence/b3/sim/` is a B2 verify input (probes 12–13): never moved, renamed or rewritten.
  New B3 evidence goes under `evidence/b3/<unit>/` (probe 20) — this unit's directory is the first.
- I-4 `schemas/specimen_ledger.schema.json` and `evidence/b3/sim/raw_F1.json` stay byte-stable
  (read by the frozen test). A revised ledger schema is a new file under `b3/schemas/`.
- I-5 `docs/b3_architecture.md` may be revised (unpinned by B2); the B3 table will pin it.
- I-6 Before **any** edit on this line: `grep -n <path> manifests/*_instrument_pins.json`; a hit is
  a stop (`feedback-fabricmap-pinned-surface`).
- I-7 (v1.1) The B3 verifier checks the indirect frozen inputs of §7a by existence and digest
  before it calls the B2 verify; a miss is a named B3 refusal.

### 7a. The B3 verifier's frozen-input contract (P-F2, v1.1)

`b3_manifest.verify` runs, in this order, before anything else and before `b2_manifest.verify`
is called: for each path below, *present* and *hashes to the B3 manifest's pin*; the first miss
raises a named `b3_manifest.Refusal` (`frozen input <path>: absent` / `: hash differs`). Only
then is the B2 verify called, and its own `Refusal` is re-raised under the B3 name (`B2 lineage:
…`). **Any other exception is an INTERNAL ERROR**: it propagates as what it is and is never
converted into an input refusal — a bare `FileNotFoundError` from inside a frozen tool means
the contract above missed a path, which is a defect to fix, not a refusal to report.

| indirect frozen input | sha256 at `73b68d7` | why the B2 verify depends on it |
|---|---|---|
| `evidence/b3/sim/sim_report.json` | `d9c432f8b797933e26e24a77d33e5884f29c03c2be88e6c59c61bc0af250adf9` | `b2_plan.FROZEN_SEED_SETS` (probes 12–13) |
| `evidence/b3/sim/raw_F1.json` | `ccf4d24622c7cfb3ee698623047ea461303c603449d47ffb0452f83656b74c53` | read by the frozen `tests/test_b3_online.py` |
| `schemas/specimen_ledger.schema.json` | `7cc74295b5c76806bddaa995675b77dfea598fb6ad42fa4ec7bfbf426d12563d` | read by the frozen `tests/test_b3_online.py` |
| `evidence/b2/b2_completion_inputs_2026-09-17/archive.json` | `ca5fedd7bb7a119883a5b74a9f19b0d02d147e6183404ddde8766b03abd46c5d` | the completion-state restore manifest (P-F1) |
| `evidence/b2/b2_completion_inputs_2026-09-17/inputs.tar.zst` | `20300d5f2476beafaa9411c11f2a412eb91f01149bf4318e79ccee2706337767` | the 15 non-tracked inputs themselves |
| `manifests/b2_manifest.json` | `aec84514ff29dda7957d46d650a370e155f6dc60a281b992e148f8a0fae6c4c0` | the closed B2 identity (S3) |
| `manifests/b2_instrument_pins.json` | `82a5f2fb1d246c9cab506df65d53a0f329ca219ec3c5cdf50a272ff79ee319d1` | the B2 decision surface, pinned by content |

The 15 files inside the archive are checked by the B2 verify itself (image pins, B1 table); the
B3 verifier checks the archive, not its members, and refuses if the archive that could restore
them is gone. The B3 pin table pins none of these seven by glob (they are outside `b3/`); the B3
manifest pins them by content in its own block, and `test_b3_manifest` must prove each of the
seven refuses by name when absent and when one byte differs.


## 8. The B3 lifecycle — order of units (each separately authorised; none authorises the next)

Modelled on `docs/b2_preregistration.md` §8a and the lifecycle-2 audit's F2 ordering; the pin
table is generated **once**, after the last pinned edit and before S0, so that the suite is green
by construction at every stage.

1. **Architecture and preregistration review** (docs only): `docs/b3_architecture.md` v0.2 —
   the `b3/` layout, the B3 image (B2's image plus a C twin of the cartographer, the ledger
   fields and the map version in every record's commitment), the three arms and the two
   accountings unchanged; `docs/b3_preregistration.md` DRAFT — claim, the primary (a paired
   statistic on O − R at a budget fixed by the cost rule) and the second primary (end-to-end
   O − F), the falsifiers, the sessions, the lifecycle S0–S3 table, the calibration rule with
   the B2 lesson applied (a longer qualification run or an explicit margin: both B2 sessions ran
   slower than the 20-record B2Q rate), the transport disposition per session (the stop-loss is
   not lifted), and §10's authority statement verbatim. Owner review rounds until PASS.
2. **All pinned edits**, host-only: `b3/host/` (cartographer and online arm copied from the
   frozen reference, the B3 runner, records, session, adjudicator, plan, manifest, pins, test
   report), `b3/tests/`, `b3/schemas/`, `b3/firmware/` sources and their build evidence, the
   hostapp twin; each reviewed. The pre-freeze **stage-aware test audit** (§9) is part of this
   unit and precedes step 3.
   The test report's discovery sentinel and removal control (§7, candidate 2b) and the seven
   frozen-input refusal tests (§7a) are part of this unit.
3. **Pins generated once**: `b3/host/b3_pins.py --generate` → `manifests/b3_instrument_pins.json`
   (rule `b3/**/*`, regular files).
   Any later pinned edit returns the line to step 2 and step 3 is repeated; the table is not
   patched.
4. **S0 init**: `manifests/b3_manifest.json` pins the B3 table, the seven indirect frozen inputs
   of §7a by content (the B2 table and manifest, the completion-input archive and its manifest,
   the three B3 files the B2 verify reads), re-verifies the B2 S3 and the B1 lineage after the
   §7a pre-check, re-hashes the B3 image.
5. **Pre-freeze proof**: the whole suite (`tests` + `b3/tests`) green, zero skip/fail/error,
   `clean_tree_proof` on the S0 tree — a transition check only.
6. **Owner S1 freeze**: `prereg.sha256`, `board_ready`; then the **post-freeze proof** bound to
   the actual S1 manifest sha — required before any ruling.
7. **Qualification and rulings**: the B3Q ruling pair (owner) → one board session under it, with
   its own transport disposition → S2 qualify (the tool, from reconstructed evidence, re-adjudicated)
   → proof at S2 → S3 plan (the tool) → **final proof** at S3 — required before any B3 ruling pair.
8. **Sessions**: one ruling pair per session, bound to the S3 sha; fresh power cycle, boundary
   record, archived as produced, owner-reviewed before the next.
9. **Result**: adjudication, result document, closure at S3 unless the preregistration defines a
   later transition.

Steps 2–4 are where lifecycle 1 of B2 went wrong (a pinned test frozen with a stage constant);
step 2's audit is the guard.

## 9. Review of every future stage-aware test (the rule for step 2)

The lifecycle-1 defect: `tests/test_b2_plan.py` asserted a value (`UNDETERMINED`) that was true
at S0–S2 and false at S3 *by the preregistration's own rule*, and was frozen at S1. The rules that
prevent it on the B3 line, to be applied to every B3 test before the table is generated:

- T-1 A test that reads committed lifecycle state (`manifests/b3_manifest.json`,
  `evidence/b3/plan.json`, the prediction, the pin table, session archives) takes the stage from
  the production `verify` and asserts what that stage licenses — never a literal stage, split
  status, calibration, session count or history length (the `StageCoverage` pattern of
  `tests/test_b2_runner.py:558` and `test_b2_plan.py`).
- T-2 Every such test is driven by fixtures at S0, S1, S2 and S3 **and** against the illegal
  pairings (a pre-S3 value under an S3 manifest, a pinned plan whose bytes drifted, a stage
  wearing another stage's status), each refusing for its own named reason — before freeze.
- T-3 `skipUnless` on a committed artefact is not a pass: the B3 proof keeps B2's zero-skip rule,
  so a missing artefact is a red proof, not a quiet green.
- T-4 Values that a legal B3 transition changes are listed in the preregistration's lifecycle
  table first; a test may name only what that table calls invariant across S0–S3.
- T-5 B2's stage is a **pinned input** to B3 (its manifest sha `aec84514…`, S3, closed with no
  post-B2 transition): a B3 test may assert it only through the B3 manifest's pin of the B2
  manifest, not as a free literal.
- T-6 The frozen `tests/test_b3_online.py` is not a B3 test: it stays as B2 froze it, and its two
  committed reads (I-4) stay byte-stable.

## 10. What B2 does not hand to B3 — stated so it cannot be argued in later

**Not an input, not an authority (history only):**

- the four B2 rulings (B2Q pair, two B2 session pairs; `rulings/`, consumed, untracked) — each
  authorised one B2 session under the B2 manifest and nothing else;
- the B2 calibration (3 016.40 records / h, all-self-reporting, 5 pairs / session max) — the rate
  of a B2 image on a B2 session; B3 measures its own in its own qualification session;
- the B2 session evidence (`evidence/b2/b2q_17A6_2026-09-16-01`, `b2_17A6_2026-09-16-01`,
  `b2_17A6_2026-09-17-01`) and the pooled primary (`evidence/b2/b2_primary_2026-09-17`, p =
  0.01953125) — bound to `aec84514…`; they qualify nothing about a B3 manifest;
- the B2 clean-tree proofs — they proved the B2 surface;
- the B2 transport exceptions — spent by their sessions; the stop-loss stands and every B3 board
  session needs its own disposition in its own ruling;
- every lifecycle-1 identity of B2 (§8a of the B2 preregistration) — doubly so.

**Carried as explicitly pinned inputs or historical premises (never as authority):**

- the B1 lineage exactly as B2 carries it (carrier `d85daef4…` / `0x42310001`, the B1 manifest,
  the B1 qualification chain, the B1 map `c6a4b23e…`), re-verified fresh by the B3 verify;
- the B2 engine and landscape by content (`b2-es-v1`, μ 4 / λ 8 / kmax 4, `host/b2_search.py`,
  `b2_landscape.py`, `b2_maps.py`, `b2_gate.py`), through the B2 table's sha in the B3 table;
- the closed B2 manifest `aec84514…` at S3 and the B2 result document
  (`docs/b2_result_2026_09_17.md`) as the **historical premise** that the frozen-map arm reproduces
  on silicon — a premise the B3 preregistration cites, not a result it inherits;
- the archived seed sets (both gate reports, the B3 simulation, and now the B2 plan's nine pairs
  and B2Q's) as **exclusion sets** for the B3 seed draw — disjointness enforced, not assumed;
- the B2 image, its build evidence and BSP sources as the base the B3 image is diffed against;
  the B3 image is pinned by its own build evidence and hashed by the B3 manifest;
- the instrument (`zynq-psoracle` at `689dde1`, `PSORACLE_ROOT`) and board `17A6` as B2 pins them.

## 11. Closing, and what was not done

Closing verify on the main tree after this document and the evidence directory were written:
S3 / true / null / `aec84514…` (`verify_closing.json`); `git status` shows only the two paths this
unit adds; `git worktree list` is `main` alone; `git diff --check` clean.

Not done, by the owner's condition: no B3 code, test or schema edited or added outside this
document and its evidence; no pin table generated; no manifest; no preregistration; no tag; no
push; no board.

**v1.1 follow-up.** Added: `evidence/b2/b2_completion_inputs_2026-09-17/` (archive, manifest,
producer, consumer, controls, runs) and `glob_and_discovery_probe.py` → `glob_and_discovery.json`
in this unit's evidence directory; this document's §6 P-F1/P-F2, §7 candidates 2b and 3, §7a,
§8 steps 2–4. `c648d6e` untouched; the original 15 files, the B2 pins / manifest and the frozen
B3 wrappers untouched; closing verify on the tree S3 / true / null / `aec84514…`
(`verify_closing_v1.1.json`). **Next unit, if the four P2s are accepted closed: step 1 of §8**
(architecture v0.2 and the preregistration draft) — still host-only, still no pinned edit.

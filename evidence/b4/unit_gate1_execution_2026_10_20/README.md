# B4 — the production gate `b4-gate-1`: the executed unit (2026-10-20, UTC)

The run record of the one authorised execution of the formal gate under `docs/b4_gate_execution_plan.md` v0.2.1 (ACCEPTED). Nothing in this
directory is a verdict of its own: the verdict is the tool's, in `evidence/b4/gate/b4-gate-1_20261020T102526Z/gate_report.json` and
`gate_report.md`, bound by digest to the batch archive `evidence/b4/sim/b4-gate-1_20261020T102526Z/`. Both were committed exactly as the
tool wrote them, in the commit before this one (`5070967`); this directory holds the operator's records (section 5.3 of the plan).

## 1. The authorisation and the operator's stop (section 2.3)

The owner's execution ruling of 2026-10-20 (relayed by the user): a single production execution of `b4-gate-1` under the accepted plan;
execution HEAD **`a243ee8`**; date **2026-10-20 (UTC)**; S = 200; deadline **3 600 s** under the existing soft policy; a branch
`b4-gate-1-execution` from that HEAD for this unit's two local commits; no smoke test, no derivation or print of any seed; stop and
report on any difference, nothing fixed to make it match; one fresh-process batch verify and one gate verify; the raw results and the
verification records committed; Git-blob digests compared; valid FAIL is a result of this version; invalid, incomplete or an
initialisation failure stops with the state kept, no retry, no redraw, no relabel. **Not authorised:** push, merge, any change to the
model / methods / thresholds, RTL, routing, placement or board work.

The operator's stop before the command — reads of committed files and `git` only, no seed derived or printed
(`operator_stop_check.py`, output `operator_stop_check.txt`, 10:25:15Z; `import_check.txt` from
`evidence/b4/unit_2b4a_repair_2026_10_18/import_check.py`):

| check | authorisation / plan | actual | result |
|---|---|---|---|
| HEAD | `a243ee8` (the execution HEAD; the branch `b4-gate-1-execution` created from it) | `a243ee8ab904d23706bd6b8fee0d76d6ccb200a5` | no difference |
| clean tree | `git status --porcelain` empty | empty | no difference |
| tool bytes | the 24 host-module digests of the accepted baseline `00336d0` | `git diff --stat 00336d0 HEAD -- b4/` empty (every file under `b4/` byte-identical); `import_check.py`: 52 entries, file / base / copied-function digests all equal, no untabled file | no difference |
| exposure receipt | sha256 `68764bbc1a51ec25…`, 66 values | `68764bbc1a51ec2506bf9d9bcbb3f55f88f3d7642b5eb46c6fd3dd39f8dae146`, len 66, `pinned_receipt_count()` 66 | no difference |
| registry | exactly one run directory, `b4-sim-3_20261019T121833Z`, status `seeds`, `seeds.json` sha256 `1a0d1e7b91132ed6…`, 65 values | 1 entry, that directory, `seeds`, `1a0d1e7b91132ed6814a9e369e23f2c55f28886448fa5efd55d722182f50b17d`, 65 | no difference |
| pooled exclusion | 2 224 values | `len(load_exclusion_set().values)` = 2224 | no difference |

No difference was found; the run started. The two refs are kept apart as the plan says: `00336d0` is the tool baseline, `a243ee8` the
execution HEAD the ruling named (the manifest records the latter).

## 2. The run record

| item | value |
|---|---|
| command | `python3 -B b4/host/b4_gate.py run --label b4-gate-1 --seeds 200 --deadline-s 3600` from the repository root, on the clean tree at `a243ee8` (`run_header.txt`) |
| stdout / stderr / exit | `run_stdout.txt` (the tool's final JSON: status FAIL, exit_code 0, the two output directories), `run_stderr.txt` (empty), `run_exit.txt` (`EXIT 0`) — captured outside the tree during the run, copied here after the first commit |
| start (host, UTC) | 2026-10-20T10:25:26Z; the pre-flight / manifest `generated_utc` 2026-10-20T10:25:26Z |
| sim_report written | 2026-10-20T10:48:18Z |
| gate judgement written | 2026-10-20T10:48:18Z (then the gate's in-process self-validation) |
| process end (host, UTC) | 2026-10-20T10:57:09Z — **≈ 31.7 min** of wall time for the batch and the judgement (10:25:26Z → 10:57:09Z). **With the two fresh-process verifications of section 6 (10:57:35Z → 11:15:01Z) the executed unit took ≈ 49.6 min** (10:25:26Z → 11:15:01Z); the plan's 50–70 min estimate was for the whole unit including those verifications and is compared with the second figure only (the owner's P3 on `d19cc2f`, folded in here on 2026-10-20) |
| deadline record | `elapsed_s` 1372.077 of 3600, 329747 checks, expired False, clock `time.monotonic` |
| batch status | `complete`, count 200 / 200 pairs, stopped `None`, missing `[]`, fixture `False`; self-validation `{}` |
| gate | verdict `FAIL`, formal `True`, formal_reasons `[]`, contract_findings `[]`, clean_tree `True`; self-validation `{}` |
| archive on disk | 4 003 files, 1.2 GB (`evidence/b4/sim/…`); 2 files, 68 KB (`evidence/b4/gate/…`) |
| exit code | 0 — captured, not a decision: a judgement was written; the documents decide the row of section 3 |

The computer stayed awake; nothing else ran in the repository during the batch (the only other process was a read-only progress
watcher outside the tree, counting `pair_*` directories every three minutes).

## 3. The identity the manifest recorded (`manifest.json`, written before the first observation and held at every pair's end)

| field | recorded |
|---|---|
| `head` | `a243ee8ab904d23706bd6b8fee0d76d6ccb200a5` |
| `label` / `count` / `fixture` / `deadline_s` | `b4-gate-1` / 200 / False / 3600 |
| `seeds_sha256` | `785e76988d4e6ec49cfb86b7b896358b484e5899d48700ee1bcfffd6e034bced` |
| hypothesis v0.3 | `59948f9be3b4516547fbf039556d4aa6a4afd0b2dda2324619e4d40ef0651ed8` |
| certificate | `c69e419f836684872c9edb3754cdb7c76591aaabf69859dab448454c6d78ceef` |
| `b4/IMPORT.json` | `1e2a42ca7b79e03141d157b80056b74132bc64df651e17cb04a12492d1ea4669` |
| `docs/b4_architecture.md` | `8097e2d05651a6b1b8481ae874005e792782823aae6258d40b59bc7fb9df5922` |
| exposure receipt | `evidence/b4/unit_2b4a_exposure_settlement_2026_10_19/exposure_receipt.json`, sha256 `68764bbc1a51ec2506bf9d9bcbb3f55f88f3d7642b5eb46c6fd3dd39f8dae146`, count 66 |
| registry snapshot | 1 entry: `evidence/b4/sim/b4-sim-3_20261019T121833Z`, status `seeds`, seeds sha256 `1a0d1e7b91132ed6814a9e369e23f2c55f28886448fa5efd55d722182f50b17d` |
| historical sources / pooled total | 38 / 2224 |
| inputs held | 45 repository files by digest, 6 external inputs by absolute path and digest |

The tool files (the 24 host modules and the schema), as recorded — every one byte-identical to the baseline `00336d0`:

| file | sha256 |
|---|---|
| `b4/host/b4_carto.py` | `f4933fcbf9af3d70a9949af8f61762361c27f26a46fe7ff6dbc44824ceadb2cd` |
| `b4/host/b4_controls.py` | `f8727cca7ed6fec4d0d84c18bb33c009b97532ead1ee38cfb1b48cdc8625b724` |
| `b4/host/b4_deadline.py` | `77629dde20e2e338f36f7980ad92e068453b86f881816b6e8a6b650e699f4682` |
| `b4/host/b4_engine.py` | `1cc7708d681f8cc2c09126093974fd62ffc9286eaa9191b3f77efed83d70a9e4` |
| `b4/host/b4_execution.py` | `c487d1a3bd229a6921afb4234290a9f309b880bc2f0172f344d0bce833ef0a7d` |
| `b4/host/b4_ff_hypothesis.py` | `e5e7f43233b4cf7db3a411ce224b480e5ec59c0e841a99a0001da02c93eb6ff1` |
| `b4/host/b4_ff_mapping.py` | `e750d02a8e77805587cb490aff47ce0cae93c5e1cce3e3ba39745019618df08f` |
| `b4/host/b4_ff_model.py` | `d6529700c766eeb354d01ae190adad5adb5241ab26ebfc10a6a3bb3a3fd15dbf` |
| `b4/host/b4_gate.py` | `4ccccff9e8ffed6f423392e74046c7c1bc89f8c7e556378b6752bfc4c41d5dbf` |
| `b4/host/b4_gate_stats.py` | `f03f2203a9db8b75c567316ac257a3cd4163dee9a2fd297a75887d676b779a0a` |
| `b4/host/b4_gate_verify.py` | `67f0eee5bf1f4f3dda4bf4c420f004a2d9c987f581e3c56aa7460aecef295e41` |
| `b4/host/b4_k10.py` | `a92edd103ac349e91055fdc35eeb477fa931d8fcac2bf8c18130f479d1682ebd` |
| `b4/host/b4_k9.py` | `4c159ac0b80a4b9cad6d39d6bfc9ee5dd5a38177bf8e8d3ace20ddebb3ebfd3c` |
| `b4/host/b4_landscape.py` | `abf8c6b3de4c1d0ad92b1d05611aef9976307ae74b94fbac0650fef4d2da0865` |
| `b4/host/b4_observe.py` | `d39ebb6bb9a5216deb0b7f0393c217a6d524dcdf61fa874e0e663da0dc0402dd` |
| `b4/host/b4_replay.py` | `e3302363a947a6598b6eeb5d63ee4d8120b25449f05fcdf19b73e4a9af59f40d` |
| `b4/host/b4_rng.py` | `f2ef921176d46f1fec3f0d496300a42bce66a4d051c8c3e6f87e4bfff067b42a` |
| `b4/host/b4_seeds.py` | `856f99c04ba98045e781224f0ec4e1762a55c0d6f0adf89ca76a39139696677e` |
| `b4/host/b4_sim.py` | `18fc7c3a56ee3d245046eabe052c9c3c5cd1784ba6ef8581742fb1effc8bb4a2` |
| `b4/host/b4_sim_schema.py` | `9f229f0af95d7ba256b0e374291170ddc81c262844cf5a379c5b4a44be699e80` |
| `b4/host/b4_sim_verify.py` | `edfee81303822ce20d151dffb873d0dfad5b9f598d74b589405d00641e745cce` |
| `b4/host/b4_snapshot.py` | `a8960ec81383a8a39b15e7d9393460862b64e6e306f74864d75f0c6e71a2f14d` |
| `b4/host/b4_stats.py` | `9b6dd9ef6020eb1aa6673bdfa442e7fe6c02d96ed06632b9ecd83acead5e258d` |
| `b4/host/b4_thresholds.py` | `c7fcd2126313abf473ee2e42da8871158584082a5b6013b612f00b655c5e858f` |
| `b4/schemas/self_map_v3.schema.json` | `4492f83c57ff7b0f7d28dc3c1012c32906808a7221783f0f5cfacca932220513` |

The gate report's binding to the archive: archive sha256 `dab33280753ca5a8fca5f02064eb6afe441913924cae88b000f5061285ce4a07`, seeds `785e76988d4e6ec49cfb86b7b896358b484e5899d48700ee1bcfffd6e034bced`, manifest `5ee9e3e22c50f388c6da5ff15b9d400bd8e02c29354313254bf1f454e425da2e` (from `gate_report.md`, header).

## 4. The verdict and every row, copied from `gate_report.md` (not summarised)

## Verdict: **FAIL** — a complete, valid batch on which budget rule FAILS; K9 FAILS; not assessable: K1, K2, K3, K4, K5, K6, K7 — no threshold is adjusted, no budget or sample repaired

## The budget rule — **FAIL**: B* = None, N = None, N × 3 × B* = None, eligible []

no grid budget has both K1 eligibility and an N: the budget rule's candidate does not exist on this S (not invented) — B* and N are not invented; every row that depends on B* or N is not assessable; the gate cannot PASS

| budget | K1 eligibility | N |
|---|---|---|
| 8 | True | None |
| 16 | True | None |
| 24 | True | None |
| 32 | True | None |
| 48 | True | None |
| 64 | True | None |
| 96 | True | None |
| 128 | True | None |
| 192 | True | None |
| 256 | True | None |

## The rows

| id | criterion | status | reason | value | threshold |
|---|---|---|---|---|---|
| K1 | non-saturation | **not_assessable** | no B*: the budget rule failed (no grid budget has both K1 eligibility and an N); K1's eligibility per budget is in the budget rule's record | `{"k1_by_budget":{"128":{"eligibility":true,"median_base":32.0,"median_best_R":40.0,"omega_best_p95":45.05000000000001},"16":{"eligibility":true,"median_base":32.0,"median_best_R":35.0,"omega_best_p95":40.0},"192":{"eligibility":true,"median_base":32.0,"median_best_R":41.0,"omega_best_p95":46.0},"24":{"eligibility":true,"median_base":32.0,"median_best_R":36.0,"omega_best_p95":41.0},"256":{"eligibility":true,"median_base":32.0,"median_best_R":41.0,"omega_best_p95":46.0},"32":{"eligibility":true,"median_base":32.0,"median_best_R":37.0,"omega_best_p95":41.0},"48":{"eligibility":true,"median_base":32.0,"median_best_R":38.0,"omega_best_p95":42.0},"64":{"eligibility":true,"median_base":32.0,"median_best_R":39.0,"omega_best_p95":43.0},"8":{"eligibility":true,"median_base":32.0,"median_best_R":34.0,"omega_best_p95":39.0},"96":{"eligibility":true,"median_base":32.0,"median_best_R":40.0,"omega_best_p95":45.0}}}` | `{"medians":"median_r(best_R(B)) > median_r(base_r), two medians compared","omega_best_p95_lt":64}` |
| K2 | not a definitional lock | **not_assessable** | no B*: the budget rule failed (no grid budget has both K1 eligibility and an N) | `null` | `{"population_variance_gt":0,"x_minus_r_nonrejection_min":0.9}` |
| K3 | wrong maps do not profit | **not_assessable** | no B*: the budget rule failed (no grid budget has both K1 eligibility and an N) | `null` | `{"ratio_max":0.1,"sign_test_p_gt":0.05}` |
| K4 | headroom against the certificate-derived grouping | **not_assessable** | no B*: the budget rule failed (no grid budget has both K1 eligibility and an N) | `null` | `{"f_over_omega_min":0.5,"omega_median_max":57.6}` |
| K5 | effect, power, N | **not_assessable** | no B*: the budget rule failed (no grid budget has both K1 eligibility and an N) | `null` | `{"cap_search_evaluations":4000,"cohen_d_min":0.5,"power_min":0.9}` |
| K6 | no fixed-seed lock | **not_assessable** | S = 200 as planned; N does not exist (no B*) | `{"N":null,"S_planned":200}` | `{"N_min":8,"S_gate":200}` |
| K7 | the map is a map | **not_assessable** | (a) holds by the completion contract of a complete batch (every arm audited with no recompute finding); (b) needs B*: no B*: the budget rule failed (no grid budget has both K1 eligibility and an N) | `{"a_basis":"complete batch: every executed run audited clean","a_recomputation_mismatches":0,"b_median_by_budget":{"128":17.0,"16":3.0,"192":19.0,"24":4.5,"256":21.0,"32":6.0,"48":8.0,"64":10.0,"8":2.0,"96":14.0}}` | `{"o_prefix_median_not_unknown_min":11,"recomputation_mismatches":0}` |
| K8 | ledger replay | **PASS** | holds by the completion contract of a complete batch | `{"basis":"complete batch: the replay of every executed run recorded no finding (each arm's audit); re-audited by the archive-wide verifier"}` | `{"replay":"no finding on every executed run; a broken tool contract is invalid under section 9.1"}` |
| K9 | observability | **FAIL** | (b) median coverage below 0.50: ff_srval 0.40625 | `{"fraction_of_S_with_all_seven_positive_controls":1.0,"per_semantic":{"ce_mode":{"conditional_on_A8":false,"median_coverage_over_all_S":1.0,"not_assessable_seeds":0,"seeds_with_positive_control":200},"clock_mode":{"conditional_on_A8":false,"median_coverage_over_all_S":1.0,"not_assessable_seeds":0,"seeds_with_positive_control":200},"ff_init":{"conditional_on_A8":true,"median_coverage_over_all_S":1.0,"not_assessable_seeds":0,"seeds_with_positive_control":200},"ff_srval":{"conditional_on_A8":false,"median_coverage_over_all_S":0.40625,"not_assessable_seeds":0,"seeds_with_positive_control":200},"sr_kind":{"conditional_on_A8":false,"median_coverage_over_all_S":0.5,"not_assessable_seeds":0,"seeds_with_positive_control":200},"sr_mode":{"conditional_on_A8":false,"median_coverage_over_all_S":0.96875,"not_assessable_seeds":0,"seeds_with_positive_control":200},"storage_kind":{"conditional_on_A8":false,"median_coverage_over_all_S":1.0,"not_assessable_seeds":0,"seeds_with_positive_control":200}},"seeds_with_all_seven_positive_controls":200}` | `{"median_coverage_per_semantic_min":0.5,"seeds_with_all_seven_positive_controls_min":0.9}` |
| K10 | real interaction | **PASS** | interacting seeds / S >= 0.50 | `{"counts":{"interacting":200,"no_interaction_seen_among_tested_comparisons":0,"nonzero_below_threshold":0,"not_assessable":0},"fraction_interacting_over_S":1.0,"tau":2}` | `{"interacting_seeds_over_S_min":0.5,"tau":2}` |

Per-semantic K9 medians, from the diagnostics: ce_mode 1.0, clock_mode 1.0, ff_init 1.0, ff_srval 0.40625, sr_kind 0.5, sr_mode 0.96875, storage_kind 1.0. The configuration-only upper bound of 0.5 on
`ff_srval` under the fixed comparison set of §9.3 is recorded in the plan's section 4 (the owner's audit of 2026-10-19); the observed median
0.40625 is below it and below the threshold; the bound and the deficit remain separate records, as ruled. Descriptive records with no threshold
(the plan's section 4): Δ1 = O − R at every budget has a negative mean (−0.485 … −0.94), Cohen's d −0.23 … −0.39 and a one-sided sign-test
p ≥ 0.9999; the K5 scan's power at N = S is 0.0 at every budget, so N is null everywhere; K7's (b) medians over the 200 seeds are
2, 3, 4.5, 6, 8, 10, 14, 17, 19, 21 at the budgets 8 … 256 (six of ten below the reference 11, the budgets 8 … 64, as on the S = 32 sample).

## 5. The disposition (section 3 of the plan)

The row that applies is **`complete`, archive clean, a row or the budget rule FAILS → valid FAIL**: a result of protocol v0.1.16, confined to
this model, the public task / panel, the operator / control design, the budget grid and the declared decision procedure — not a statement
about silicon, the carrier, or the content class in general. Archived and committed exactly as a PASS would be. **Not done, by the plan and
the ruling:** no threshold adjusted, no budget or sample repaired, no re-run, no relabel, no redraw, no S change; the label `b4-gate-1` is
consumed by its own records and its master and pairs are in the registry and in the pooled exclusion of every later derivation. A revision,
if the owner wants one, is a separately proposed unit under a new label that discloses the influence of `b4-sim-3` and of this gate's data
(the plan's section 4, "what follows a valid FAIL"); nothing of the carrier, the board or the routing line moves on the strength of this FAIL.

## 6. The verification of record (section 5.2) and the commits (section 5.3)

| step | record | result |
|---|---|---|
| fresh-process batch verify, deep | `sim_verify.txt` — `python3 -B b4/host/b4_sim_verify.py evidence/b4/sim/b4-gate-1_20261020T102526Z`, 10:57:35Z → 11:06:16Z | findings `{}`, clean true, exit 0 |
| fresh-process gate verify, deep | `gate_verify.txt` — `python3 -B b4/host/b4_gate_verify.py evidence/b4/gate/b4-gate-1_20261020T102526Z`, 11:06:16Z → 11:15:01Z | findings `{}`, clean true, exit 0 |
| commit 1 | `5070967` — the archive and the gate directory exactly as written (4 005 files), nothing else | tree clean after |
| Git-blob digest comparison | `blob_digest_check.txt` (`blob_digest_check.py`): `git ls-tree -r 5070967` for the two directories against `git hash-object` of every file on disk, 11:16:19Z | 4 005 committed blobs, 4 005 files on disk, 4 005 equal; 0 only-in-commit, 0 only-on-disk, 0 differing → **EQUAL**; no second deep-verification round (section 5.3) |
| commit 2 | this directory: the captured command output, the operator's stop records, the two verification outputs, the blob comparison and this README | — |

Both verifications establish internal execution / derived-result consistency and source binding (every arm re-executed against the
ledger's recorded observations through the replay port and re-audited, K7's prefixes and the summary recomputed, K9 / K10 recomputed from
the retained grids; the judgement recomputed row by row and the markdown re-rendered) — not the truth of the observation source, and a
clean gate verification is not itself a PASS.

## 7. What this unit did not do

No push, no merge (`main` stays `a243ee8`; this branch `b4-gate-1-execution` is two commits ahead of it, both local); no change to any
model, method, threshold, archive or program; no RTL, routing, placement or board work; no second batch, no `b4-gate-2`, no revision
proposal. The disk cost of the archive in `.git` is disclosed as a fact for the owner, not optimised away.

## 8. The owner's review of this unit (2026-10-20) and its archive

The owner's review of `d19cc2f` is **PASS**: the executed unit is closed, the formal verdict stays a valid FAIL, no P1 / P2; one P3 (the
timing sentence of section 2, corrected above). The review record as the owner provided it — its README, `independent_checks.json`
(the owner's own re-aggregation of the 200 pair records: per-budget Δ1 means, sample Cohen's d, one-sided sign-test p and K7 medians;
the per-semantic K9 medians from the per-address counts; K10 recomputed from the 84 000 four-corner units; the 401 archived gate values
against the prior pool of 2 224 with zero collisions, the current pool 2 625; 45 inputs, 25 tool / schema entries and 6 external inputs
equal; no seed derivation called), `review_metadata.json`, the owner's own fresh-process verifier outputs and its `SHA256SUMS` — is archived
unchanged in `owner_review_d19cc2f_2026_10_20/` (see `SOURCE.txt` there for how it was obtained and verified). The review's numbers agree
value for value with `gate_report.json`.

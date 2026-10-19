# Unit 2b-4, the gate-tool half — the formal gate tool, its verifier, the harness's gate mode (2026-10-19)

The owner's ruling of 2026-10-19 (`owner_ruling_gate_tool_2026_10_19.md`, as relayed by the user) split unit 2b-4 into (a) a host-only
gate-tool unit, authorised, and (b) the production `b4-gate-1` execution, withheld. This directory is the evidence of (a). **No gate
master or pairs were derived, no production batch was run, no b4-sim set was drawn; the committed S = 32 exploration was read once,
read-only.** The 2c skeleton (`docs/b4_preregistration.md` v0.0.1) is a separate docs-only commit (`7cf6c7f`) and is not part of this unit's
acceptance.

## 1. The deliverable (commit `4f3806d`, on the clean tree after `85c95d9`)

| file | what |
|---|---|
| `b4/host/b4_gate.py` | the gate tool: `judge` (pure), the formal identity, the gate report (`gate_report.json` + `gate_report.md`), the gate directory, `run_gate`, `judge_batch`, `judge_synthetic`, the production CLI |
| `b4/host/b4_gate_verify.py` | the independent verifier of a gate directory; a fresh-process CLI |
| `b4/host/b4_sim.py` | mode `"gate"` (b4-gate-<n> labels, reached through `b4_gate.py` only; the exploration CLI unchanged), `standing_for(label)`, `STANDING_GATE`; `summarise_batch(..., standing=)`; **no constant changed; the archived explorations' `STANDING` text untouched** |
| `b4/host/b4_sim_verify.py` | the report's standing bound to its label; the summary recomputed with it |
| `b4/tests/test_b4_gate.py` | 22 tests at `4f3806d`; 24 after the first HOLD; 26 after the second (sections 4, 9, 9.1) |
| `b4/tests/test_b4_seeds.py` | two tests repaired (section 5) |
| `b4/IMPORT.json` | 52 entries, refreshed |
| `b4_gate_mutants.py` (here) | 39 mutants, one contract each (G30 after the re-run of unit 2b-4a's battery, section 6; G31–G36 after the first HOLD, section 9; G37–G39 after the second, section 9.1) |
| `e2e_fixtures.py` (here) | the five end-to-end cases, fresh-process verified, copied as evidence (section 7); after the HOLD the six refreshed-hash negatives and their invalid controls (section 9) |

### 1.1 Where things live

- **A gate batch** is a harness batch: `evidence/b4/sim/<label>_<UTC>/` (the seed-consuming namespace; its `seeds.json` enters the
  registry and the pooled exclusion like every archived set, so a later derivation excludes the gate's values). The harness writes it in
  mode `gate`; its `sim_report.json` carries the gate standing (values beside the thresholds, *not a gate verdict here*) and no verdict key.
- **A judgement** is a gate directory `evidence/b4/gate/<label>_<UTC>/`: `gate_report.json`, `gate_report.md` (and `synthetic_summary.json`
  when that is the evidence), bound to the batch archive by the digests of its `sim_report.json`, `seeds.json` and `manifest.json` and by
  identity (label, count, fixture, status, HEAD, time). Created exclusively, no symlink in the chain, nothing overwritten; the verifier runs
  in process before the report is written and any finding makes the verdict `invalid`.
- **The production CLI**: `b4_gate.py run --label b4-gate-1 --seeds 200 --deadline-s <s>` (the pinned gate label of section 9.2 and S = 200
  only, refused before the tree is read otherwise; then `b4_sim.run_batch(mode="gate")` — the derivation of section 9.2 — then the judgement)
  and `b4_gate.py judge <batch_dir>` (the production archive on a clean tree only; runs nothing). No fixture, allow-dirty or mode flag.
  **Running it is withheld by the ruling.**
- **Fixtures**: a `b4-mech-<n>` batch through `run_gate(..., schedule=FixtureSchedule)` (Python API) and a synthetic summary through
  `judge_synthetic` (Python API, `b4-mech-<n>` labels, `fixture = true`, a note that says synthetic). Both are judged with `formal = false`
  and a standing that says NOT A GATE RESULT; the validator refuses a formal flag on either.

### 1.2 The judge, and the distinctions the ruling names

`judge(doc, evidence_kind)` reads a report-like document (status, label, fixture, count, summary) and returns the budget rule, the ten
rows and the verdict:

- the summary's own contract is checked first (`summary_contract_findings`: every grid budget present; K1's eligibility the one of its own
  numbers; `cost = N × 3 × B`; the eligible list; B* the cheapest eligible budget, ties to the smaller, or null with its reason; the at-B*
  record naming the same B* / N / cost; K9 over the seven semantics with a null median exactly when a seed is not assessable; K10's counts
  summing to S) — a break is `invalid` with the findings named and **nothing judged**;
- a batch recorded `invalid` is `invalid` (a tool / source / replay / control contract break), one recorded `incomplete` is `incomplete`
  (unfinished work); every row not assessable;
- on a complete, valid batch: **the budget rule** from `candidate_B_star` — FAIL when no grid budget has both K1 eligibility and an N,
  B* and N not invented, **K1–K5 and K7 not assessable, K6 not assessable at S = 200 (FAIL otherwise), the gate cannot PASS**; the rows
  K1 (at B*), K2 (variance > 0, both signs at a budget, X − R non-rejection ≥ 0.90), K3 (both ratios readable and ≤ 0.10 — a non-positive
  denominator is not readable and the row fails and says so — and neither control significant), K4 (median Ω ≤ 57.6; F / Ω readable and
  ≥ 0.50), **K5 on Δ1 = O − R** (d ≥ 0.5 with a legitimate +inf kept as PASS; bootstrap power at N ≥ 0.90; N × 3 × B* ≤ 4 000), K6 (S = 200
  planned, N ≥ 8), K7 ((a) by the completion contract — every arm audited with no recompute finding, re-audited by the archive verifier;
  (b) median of O's not-unknown addresses at B* ≥ 11), K8 (by the completion contract), K9 ((a) ≥ 90 % of seeds; (b) every semantic's
  median ≥ 0.50, a not-assessable semantic failing (b) with its seed count named), K10 (≥ 0.50); every boundary as written with its equal sign;
- the verdict: PASS iff the budget rule and every row PASS; FAIL otherwise, the reason naming each failing and each not-assessable row
  and saying "no threshold is adjusted, no budget or sample repaired".

**The formal identity** (`formal_reasons`): the pinned gate label, S = 200, a non-fixture batch archive that completed. A PASS on anything
else is written with `formal = false`, the reason saying NOT a gate result, and the standing NOT A GATE RESULT. The standing of a
formal judgement states the scope the ruling gives a FAIL: this model, public task / panel, operator / control design, budget grid and
declared decision procedure under hypothesis v0.3 — never a proof that FF bits or the content class are indistinguishable in general;
a PASS never evidence about the fabric.

### 1.3 The verifier

`b4_gate_verify.py <gate_dir>`: the directory lies at `evidence/b4/gate/<label>_…` under a root and holds exactly the expected files; the
report validates; the evidence is bound (digests and identity; an exploration archive is never a gate's evidence); **(deep) the batch archive
is re-verified archive-wide by `b4_sim_verify`** (every arm re-executed on the formal model, the diagnostics and the pooled summary
recomputed), findings under `batch: …`; the judgement is recomputed from the evidence and held row by row (budget rule, rows, formal flag and
reasons, contract findings, verdict, standing, diagnostics); the markdown is re-rendered and compared byte for byte; **a report that recorded
self-validation findings never verifies clean.** Exit 0 iff no finding. A clean verification of a FAIL report means the FAIL follows from
the evidence; a clean verification of a fixture or synthetic report means the rows were applied as written to evidence that is not a
gate result — the verifier's `limit` line says so.

## 2. The read-only reference: the committed S = 32 exploration judged in memory

`test_b4_gate.TheJudge.test_the_committed_exploration_report_as_a_read_only_reference` reads
`evidence/b4/sim/b4-sim-3_20261019T121833Z/sim_report.json` (bytes checked unchanged after) and judges it: not formal (an exploration
label; S = 32), the budget rule FAILS (no N at any budget), K6 FAILS on S, K9 FAILS naming `ff_srval 0.427083` only (`sr_kind`'s 0.5 meets
the ≥ 0.50 written with an equal sign), K8 and K10 PASS, K1–K5 and K7 not assessable, verdict FAIL. Nothing is written; this is the tool's
path on real data, not a result, and `judge_batch` refuses an exploration archive by label.

## 3. What was not changed, and why

- **No threshold, τ, grid, anchor or control formula, hypothesis, model, comparison set, task generator or search engine** (ruling section 1).
- **`docs/b4_architecture.md` is untouched.** `b4_thresholds.ARCHITECTURE_SECTION` ("9 (v0.1.16)") is inside the thresholds table that every
  archived batch's manifest and report bind, and `test_b4_thresholds` holds it to the document's title line; a revision of the architecture
  — even documentation-only, e.g. section 13's progress row — would change the table and make every archived summary (b4-sim-3's included)
  stop deep-verifying. This coupling is reported to the owner (also listed in the 2c skeleton's dependencies); the progress record of this
  unit is this README, not the architecture's table.
- **`b4_sim.STANDING` (the exploration's text, "v0.1.15") is untouched** for the same reason: the archive-wide verifier recomputes every
  archived summary with it. The gate mode carries its own `STANDING_GATE`, chosen by `standing_for(label)`.
- **The 2b-4a battery script** (`evidence/b4/unit_2b4a_repair_2026_10_18/b4_2b4a_mutants.py`) is archived evidence and is not edited; its
  M18 now misses its edit target (section 6) and is re-targeted as G30 in this unit's battery.

## 4. The tests (`b4/tests/test_b4_gate.py`, 22; hermetic roots, mechanics fixtures and synthetic summaries only; derivation guarded)

- **TheJudge** (pure): the PASS path with every row PASS and the formal reasons; the formal identity on a pure document; every row's FAIL on
  its own number (K2 ×3, K3 ×5, K4 ×3, K5 ×4 incl. −inf and the 4 000 cap, K7, K9 ×3, K10) with the verdict naming the row; the boundaries
  written with an equal sign (K2 0.90, K3 0.10, K4 57.6 and 0.50, K5 0.90 and +inf, K7 11, K9 0.90 and 0.50, K10 0.50) all PASS; K5 is Δ1 not
  F − R; K6 on S = 199; no B* (the budget rule FAIL, the dependent rows not assessable, K6 not assessable at 200 and FAIL at 32, the verdict
  FAIL); invalid / incomplete; ten contract breaks of the summary (`invalid`, nothing judged); the committed exploration as a read-only
  reference; `standing_for`; the synthetic summary's own findings.
- **EndToEnd** (one hermetic root; four runs in `setUpClass`): a valid FAIL archive without B* (`run_gate` with the mechanics schedule 7 / 11,
  8 / 12: the harness batch complete, judged FAIL, `formal = false`, the verifier clean in process and in a fresh process, the batch's
  report carrying the exploration standing and no verdict key); a synthetic PASS (`judge_synthetic`: PASS, never formal, three files,
  verifier clean); an invalid archive (DOMAIN injected in pair 1's arm O) and an incomplete one (the 60 s deadline expired by a fake clock
  inside pair 0's K9) judged `invalid` (exit 1) and `incomplete` (exit 3), verifier clean; **the tampering negatives** of the gate report with
  every digest refreshed and the markdown re-rendered (a row's status alone; the verdict alone; the coordinated internal tamper — every
  row PASS, the budget rule PASS with invented B* / N, the verdict PASS; a formal claim; the standing; a threshold; the batch's digests,
  identity and path; the rows' order; a self-validation record; a self-invalidated report; the markdown alone with and without its index
  refreshed; an extra file; a `.part`; a missing file); **the coordinated tamper of the evidence** (the batch's pooled summary changed with
  every index refreshed and the gate report re-judged from it so that it is internally consistent: the shallow verification is clean, the
  deep one names the archive — clean evidence and a passing criterion are two different things), a tampered raw curve value, the batch
  standing bound to its label; the synthetic evidence bound and re-judged, a production label in it refused; the refusals (another label, S ≠
  200, a mechanics label without a schedule, the harness's modes, an existing / symlinked / misplaced / misnamed gate directory, a dirty
  tree, `judge_batch` outside the namespace / without a report / an exploration label / a misnamed directory, `judge_synthetic` with a gate
  or exploration label, `fixture = false`, an unmarked note) writing nothing; a second judgement of the same archive giving the same rows in
  a new directory; the CLI (no fixture / allow-dirty / mode flag; the production refusals before the tree is read; `judge` on a dirty tree
  and on a fixture archive refused); the verifier CLI on a wrong directory.

## 5. The two seed tests repaired

`test_b4_seeds.TheHistoricalSources.test_every_source_reads_hashes_and_yields_seeds` and
`…test_the_pool_holds_the_copy_the_exposed_values_and_every_source_value` asserted an **empty** exploration registry and a pool without
registry values — true when written, false since `5c08536` archived `b4-sim-3` under `evidence/b4/sim/`. Nobody ran the suite after that
commit (the settlement's 255 OK is at `d293cd5`). Found by this unit's regression; repaired to assert the registry is exactly the archived
run directories (each read from its `seeds.json`: status, master, digest, values) and that their values are pooled. No loader code changed.

## 6. Validation on the clean committed tree (`4f3806d`; the raw files beside this README, each with a three-line header)

| file | what | result |
|---|---|---|
| `tests.txt` | the 21 `b4.tests.test_b4_*` modules, verbose | **Ran 277 tests, OK**, exit 0, no skip (7 min) |
| `gate_mutants.txt` | `b4_gate_mutants.py`, G1–G29, hermetic copies | **28 / 29 killed**, each with Ran N > 0 and FAILED and the failing tests named; **G29 SURVIVED (Ran 1, OK) — an equivalent mutant, see 6.1** |
| `gate_mutants_g30.txt` | G30 (2b-4a's M18 re-targeted to the changed statistics line) | **1 / 1 killed** |
| `mutants_2b4a_rerun.txt` | unit 2b-4a's 77-mutant battery re-run under the gate-mode change | **76 / 77 killed; M18 EDIT-MISS** (its target line changed: the `standing=` parameter) — the same contract killed as G30 |
| `import_check.txt` | `b4/IMPORT.json` | 52 entries, every digest equal, no tracked file under `b4/` without an entry |
| `e2e_run.txt`, `e2e/` | the five end-to-end cases (section 7) | every verifier run exit 0 in the hermetic root and again on the evidence copy; derivation calls [0, 0] |
| `sim3_deep_verify.txt` | `b4_sim_verify.py` on the committed `b4-sim-3` archive under the changed harness | findings {}, clean true |

### 6.1 G29, the survivor, and what it shows

G29 removes `not na` from the verdict's PASS condition (`if not fails and not na and budget PASS`). It survives because the state it would
expose — a not-assessable row with nothing failed and the budget rule PASS — is unreachable by construction: a row is not assessable only
when B* or N is absent, and then the budget rule FAILS, so `fails` is non-empty whatever the guard says. The guard is defence in depth, not a
separately reachable contract; the claim "a PASS cannot be produced beside a not-assessable row" is held on the report side by the
validator (`verdict PASS with the budget rule or a row not PASS`, tampered in `test_every_tamper_…` and killed by G24) and by the verifier's
recomputation. Reported as a survivor, not removed and not re-counted; the battery's comment says the same.

## 7. The end-to-end evidence (`e2e/<case>/`)

Each case directory holds `root/evidence/b4/gate/<gate dir>` (and `root/evidence/b4/sim/<batch>` for the archive cases), the fresh-process
verifier output in the hermetic root (`verify_in_hermetic_root.txt`) and again on the copy here (`verify_on_the_evidence_copy.txt`), and
`e2e/summary.json`. The copies are re-verifiable from this directory: `python3 -B b4/host/b4_gate_verify.py evidence/b4/unit_2b4_gate_tool_2026_10_19/e2e/fail/root/evidence/b4/gate/b4-mech-1_fail`.

| case | evidence | verdict | exit | formal | rows |
|---|---|---|---|---|---|
| `fail` | a `b4-mech-1` batch of two fixture pairs, complete, no B* | FAIL | 0 | false | budget rule FAIL; K1–K5, K7 not assessable; K6 FAIL (S = 2); K8 PASS; K9 / K10 the model's values on two pairs |
| `invalid` | the same with a DOMAIN refusal in pair 1's arm O | invalid | 1 | false | all not assessable |
| `incomplete` | the same with the deadline expired inside pair 0's K9 | incomplete | 3 | false | all not assessable |
| `pass` | a synthetic summary (invented numbers, `b4-mech-7`) | PASS | 0 | false | all PASS |
| `fail_b_star` | the synthetic summary with `ff_srval`'s median 0.427083 | FAIL | 0 | false | B* exists; K9 FAIL, the rest PASS |

None of these is a gate result. The `fail` case's K9 / K10 statuses are whatever the model gives on two fixture pairs and are not read.

## 9. The owner's HOLD on `4cdc0c1` and the correction round (commit `77a6c8c`; the raw files `hold_*` beside this README)

The owner's review (`owner_review_4cdc0c1.md`, as relayed; its probe artifacts stay in the ignored review directory) held the unit on
three P2 findings and one P3, with the first round's independent checks confirmed (277 tests, the five e2e cases, IMPORT, the sim-3
deep verify, G29 and G30 accepted). Fixed as one unit; nothing of the first round's commits or evidence rewritten.

| id | finding | correction |
|---|---|---|
| R1 (P2) | the summary contract was shallow: `D_over_F = null` and `B* = 64.0` escaped as `AttributeError` / `KeyError` instead of an invalid judgement | `summary_contract_findings` rewritten as a **total** validator on arbitrary decoded JSON: every nested shape and exact type checked before it is indexed or used in arithmetic (a bool is never an int, 64.0 is never the budget 64, every number finite); `doc_identity_findings` validates status / label / fixture / count before anything is read; a non-object document is invalid |
| R2 (P2) | four incoherent synthetic summaries (an empty N scan beside N = 16, a per-budget d of −1 beside an at-B* copy of +0.9, `{value: −100, special: "+inf"}`, `fraction_of_S = 2.0`) were judged PASS and verified clean in a fresh process | every field K1–K10 reads is **bound** to the quantity it represents: the at-B* copies to their per-budget originals (k2's variance and both-signs list; k3's ratios through the harness's `_ratio` and its sign-test p values; k4's medians / means / ratio; k5's Cohen's d and N / cost; k7's record); a delta's sign-test p to its counts, its counts to S, its mean to the difference of the arm means, its Cohen's d to its mean and variance with the one valid encoding of +inf (`"-inf"` / `"nan"` never occur); the N scan complete and ascending from 8, ending at the first n whose rate reaches 0.90 when N exists, covering every n to S below it otherwise, empty with a null power below n_min; the cost to N × 3 × B; K1's eligibility to its numbers and its medians to the arm values; K7's median to its values; K9's fraction to its count and S, a null median exactly with a not-assessable seed, each semantic's positive-control count ≥ the all-seven count; K10's counts summing to S and the fraction to the interacting count; the thresholds table, the driver's note, the grid, the eligible list and the cheapest candidate. The intentional representations are kept (a null N; a null power below n_min; +inf; a null median with a not-assessable seed). The synthetic fixture is now **built coherently from primitives** (arm means from the deltas, counts scaled to S, the exact sign-test p, d from mean and variance, the scan from N and the power, the at-B* record copied from the originals), so every row's FAIL is produced coherently — and two consequences are recorded: K5's *power* condition cannot fail when N exists (the scan's definition), and a non-positive denominator shared by K3 and K4, or a zero variance shared by K2 and the +inf d, fails both rows at once |
| R3 (P2) | the repaired seed regression assumed every registry record has seeds; a legal `init_failed_no_seeds` record failed it | the assertions are status-aware for every legal record kind (`seeds`, `seeds_fixture`, `init_failed_no_seeds`), with exact membership, digests and the pooled union; a mixed-registry case beside the committed set (`test_a_mixed_registry_beside_the_committed_set_is_read_status_by_status`); no loader code changed |
| D1 (P3) | the 2c skeleton misstated B3's lifecycle | `docs/b4_preregistration.md` v0.0.2: S0 init (derived from the tree, the prediction already pinned, not frozen), S1 freeze, S2 qualify, S3 plan; the sessions and the pooled adjudication introduce no later transition; the B4 lifecycle / tool / stage contract stays unresolved |

**The new tests** (`test_b4_gate.py`, 24): `test_an_incoherent_or_malformed_summary_is_invalid_never_judged_and_never_an_exception` (the owner's six
reproductions and one case per binding — 55 incoherent summaries, each a named finding, an invalid verdict, every row not assessable);
`test_the_contract_is_total_every_node_replaced_by_every_foreign_value` (every node of a coherent summary, containers included, replaced by
null / a string / a bool / a float / an empty list / an empty object: the judge never raises; a null in place of a non-null node is always a
finding); the identity-field and non-object documents; `EndToEnd.test_an_incoherent_synthetic_summary_cannot_be_made_a_clean_pass_by_refreshed_hashes`
(the six written over the committed synthetic PASS evidence with the PASS report kept, every digest refreshed and the markdown re-rendered:
the fresh-process verifier refuses each; the same evidence judged directly: invalid reports that verify clean). The row-FAIL and boundary
tests re-expressed on the coherent builder. The set-up stops its derivation guards if it fails, so they never leak into other modules.

**Validation on the clean committed tree `77a6c8c`:**

| file | what | result |
|---|---|---|
| `hold_tests.txt` | the 21 modules, verbose | **Ran 280 tests, OK**, exit 0, no skip (7.5 min) |
| `hold_gate_mutants.txt` | G1–G36 on hermetic copies (the computer slept during the run: 9 775 s wall time; no batch was affected — every kill names its expected tests) | **34 / 36 killed**; G29 SURVIVED (the equivalent survivor of 6.1, accepted by the owner); **G21 BASELINE-NOT-GREEN** — its named test was renamed in this round (a stale name in the battery, not a product finding) |
| `hold_gate_mutants_g21.txt` | G21 with its test name and its edit target (the rewritten line) corrected | **1 / 1 killed** — so 35 / 36 with the one equivalent survivor |
| `hold_e2e_run.txt`, `e2e_hold/` | the five cases, the six negatives, the six invalid controls | the five: verifier exit 0 in the hermetic root and on the copy; the six negatives: **exit 1** both places, naming the rows / verdict as not the recomputed; the six invalid controls: the tool exit 1 (verdict invalid, the finding named), the verifier exit 0; derivation calls [0, 0] |
| `hold_import_check.txt` | `b4/IMPORT.json` | 52 entries, every digest equal, nothing untabled |
| `hold_sim3_deep_verify.txt` | the committed `b4-sim-3` archive under the corrected tree | findings {}, clean true — the real summary passes the total contract (asserted in the read-only test too) |

The first round's raw files (`tests.txt`, `gate_mutants.txt`, `gate_mutants_g30.txt`, `mutants_2b4a_rerun.txt`, `import_check.txt`, `e2e/`, `sim3_deep_verify.txt`)
are kept unchanged as the record of `4f3806d`. Two evidence scripts changed after `77a6c8c` and are committed with this evidence:
`e2e_fixtures.py` takes the output directory name (`e2e_hold`), `b4_gate_mutants.py` has G21's test name and edit target corrected.

### 9.1 The owner's second HOLD on `a8f2da1` and the correction (commit `6431e9f`; the raw files `hold2_*`)

The owner's review (`owner_review_a8f2da1.md`, as relayed) accepted R3 and D1, the six original probes and G21's correction, and held two
residual P2 workstreams of the same contract: (1) Cohen's d was bound by sign and by copy agreement only, so a coordinated edit of both
copies at B* turned a K5 FAIL into a PASS that verified clean; and the fixture used the population standard deviation where the frozen
production statistic (`b4_gate_stats.cohen_d`, by copy of `host/b2_gate.py`: mean / `statistics.stdev`) uses the sample one, so the
fixture's "0.5" sat at production's 0.4987…; (2) totality and exact types were incomplete: a decoded `10**400` raised `OverflowError` in
`math.isfinite`, `1e400` in the thresholds table raised `ValueError` in the canonical serialisation, and five numerically-equal float aliases
(8.0 for `n_min`, 7.0 for the bootstrap seed, 2.0 for `tau`, 16.0 for the at-B* N, 15.0 in the at-B* K7 values) passed `==` bindings.

| workstream | correction |
|---|---|
| Cohen's d magnitude | `implied_cohen_d(mean, pvariance, S)` reproduces the production function's value from the recorded statistics: S < 2 → 0.0; variance 0 → +inf when the mean is positive, 0.0 otherwise; else mean / sqrt(pvariance · S / (S − 1)) — the **sample** standard deviation from the recorded **population** variance. A recorded finite d must lie within `D_REL_TOL = 1e-12` (relative, floor 1) of it. **The comparison is documented in the module and is not a criterion change:** the two routes to d agree to ≈ 2.2 × 10⁻¹⁶ on every one of the 140 archived delta records (the S = 32 exploration and the fixture archives), so 1e-12 is four orders above rounding noise and eleven below any difference a criterion could notice; the judgement always reads the **recorded** value (the production function's), the bound only refuses a record whose d is not that function's. The fixture now computes d by the same convention; the K5 boundary expectations are the production's (mean 1, population variance 4, S 200 → 0.49874843358150006, the FAIL side; the PASS-side boundary case uses variance 3.9 → 0.5051…). |
| totality | `numeric_findings` walks the decoded JSON first — every float finite, every int within ±2^63 (a bool is not a number) — in the summary contract, the identity fields, the synthetic summary, the gate report and `judge_batch`, before any canonical serialisation, comparison or arithmetic; `_fin` / `_int` are safe on huge ints; the planned count is bounded (`S_MAX` = 1 000 000: the scan is enumerated to S). `10**400`, `1e400` and NaN at any path, the thresholds table included, are named findings. A synthetic summary carrying such a number is **refused** at the evidence boundary (no judgement could carry it into a report), with nothing written — the refusal is named. |
| exact types | every copy and constant binding compares through `_same` (canonical JSON: 8.0 is never 8, 7.0 never the seed 7, 2.0 never tau 2, 16.0 never N 16, 15.0 never an address count, true never 1); K7's median is bound to the production median's own type (`statistics.median`); the five aliases and the bool aliases are named findings. |

**The new tests** (`test_b4_gate.py`, 26): `test_cohen_s_d_is_bound_by_magnitude_under_the_production_sample_variance_convention` — a concrete
200-value delta sequence: the production function against the implied value (within 1e-12; equal to `mean / statistics.stdev` to 15 places);
the owner's boundary numbers; the special cases on the production function itself (`cohen_d([5]) = 0.0`, `[5, 5] = +inf`, `[-5, -5] = 0.0`)
and on a one-pair summary (+inf there is a finding); the coordinated two-copy edit over a mean of 0.5 and a variance of 4 (a named finding
"is not the production statistic of its mean … sample standard deviation", an invalid judgement); a d within 1e-14 of its implied value
accepted, one 1e-9 away refused. `test_numerically_equal_foreign_types_and_numeric_edges_are_findings_never_exceptions` — the five aliases,
bool aliases in originals and copies, `10**400`, `1e400`, NaN at several paths including the thresholds table, the count bound; then the
alias fuzz: every int leaf of a coherent summary replaced by its float alias, and every 0 / 1 leaf by its bool alias, is invalid (over 100
and over 10 cases). The totality fuzz's replacement set extended with `10**400`, inf and NaN. End to end: eight more negatives
(the coordinated d over the owner's base, the five aliases, the huge integer, the infinite literal — the last two written as the decoder
reads them) refused by the fresh-process verifier with the PASS report kept and every digest refreshed; judged directly, the first six are
invalid reports that verify clean and the last two named refusals with nothing written.

**Validation on the clean committed tree `6431e9f`:**

| file | what | result |
|---|---|---|
| `hold2_tests.txt` | the 21 modules, verbose | **Ran 282 tests, OK**, exit 0, no skip (8 min) |
| `hold2_gate_mutants.txt` | G1–G39 on hermetic copies (1 637 s) | **36 / 39 killed**; G29 SURVIVED (the accepted equivalent survivor); **G33 and G35 EDIT-MISS** — their edit targets were the `==` / `sc.canonical` lines that this round rewrote as `_same` bindings (a stale target in the battery, not a product finding; the first round's kills of both stand in `hold_gate_mutants.txt`) |
| `hold2_gate_mutants_g33_g35.txt` | G33 and G35 retargeted to the exact-type binding lines | **2 / 2 killed** — so 38 / 39 with the one equivalent survivor |
| `hold2_e2e_run.txt`, `e2e_hold2/` | the five cases, fourteen negatives, fourteen controls | the five: verifier exit 0 both places; the fourteen negatives: **exit 1** both places; twelve invalid controls: the tool exit 1 (verdict invalid), the verifier exit 0; the two refusal controls (`huge_json_integer`, `infinite_literal_in_thresholds`): refused by name, nothing written; derivation calls [0, 0] |
| `hold2_import_check.txt` | `b4/IMPORT.json` | 52 entries, every digest equal, nothing untabled |
| `hold2_sim3_deep_verify.txt` | the committed `b4-sim-3` archive under the magnitude binding and the exact-type bindings | findings {}, clean true (its 70 delta records agree with the production formula to ≈ 2 × 10⁻¹⁶) |

The first two rounds' raw files are kept unchanged.

## 10. What this unit does not claim, and what remains withheld

No gate result exists. The tool reports; it does not decide what the owner has not ruled. The production execution of `b4-gate-1`
(S = 200), carrier v2 RTL, image builds, provisioning, electrical measurements, purchase, routing operations, 2d and B4-R implementation,
push and merge remain outside this unit. A formal FAIL, when and if the production gate runs, is confined to this protocol version
(ruling section 2). The S = 32 exploration's data are unchanged.

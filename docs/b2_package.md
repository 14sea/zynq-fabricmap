# B2 — the pre-image package: what was built, what the gate showed, what is asked (v0.2, host-only, 2026-09-10)

> **v0.2.1 third review: HOLD remains.** Record/calibration reconstruction and rate
> feasibility are resolved. Two P2 findings remain: checking the actual image binary,
> and validating the complete plan/prediction contract, including their shared digest.
> See [the third review](b2_b3_host_review_v021_2026_09_10.md). All 104 B2/B3 host tests
> pass, but the additional isolated counterexamples are still accepted. Push and image
> construction are not cleared.

> **v0.2 re-review: HOLD remains.** Five previous P2 findings are resolved at the
> host-design stage. Four reproducible P2 findings remain in the new lifecycle:
> live input verification, evidence-derived calibration, complete plan derivation,
> and refusal of infeasible session durations. See
> [the correction-batch review](b2_b3_host_review_v02_2026_09_10.md).
> Push and image construction are not cleared.

> **Review HOLD (2026-09-10).** Nominal simulation results reproduce, but the control
> design, minimum-N search, B3 anomaly handling and B2 evidence/qualification contracts
> require correction before image construction or push approval. Decisions on D1–D4,
> gate revisions, audit policy and N are in `docs/b2_b3_host_review_2026_09_10.md`.
> The descriptions below preserve the submitted package; they are not a superseding
> approval of the reviewed issues.
>
> **v0.2 — the correction batch (same day), submitted for the owner's re-review. HOLD
> stands until the owner lifts it.** **v0.2.1** — the second review
> (`docs/b2_b3_host_review_v02_2026_09_10.md`) closed five of the six findings and found four
> P2 defects in the lifecycle's enforcement; §0b maps those to their corrections. §0a below maps each finding to its correction and
> evidence; §1 lists the new files; §3 is what is asked now. Nothing in the engine, the
> mixture, the fitness family or the session seeds changed; run 1 / run 3 / B3 raw files and
> reports are untouched; corrected summaries are in separately labelled directories.

> **Standing: host-only. No image, no manifest, no ruling, no board.** Stage B2 of
> `docs/autonomous_cartography_roadmap.md`, opened on the owner's instruction of 2026-09-09.
> Roadmap §7 asks for *"a host-only architecture / preregistration package … reviewed before
> carrier v2 is designed — so that no more engineering is spent sending an experiment that
> arithmetic has already decided to the board."* This is that package. The owner reviews it
> and rules; the image is built only after.

## 0. The one paragraph

B2 asks whether B1's board-built map makes the same search engine beat random-safe on a
fitness with real interaction. The package keeps the **qualified B1 carrier unchanged** and
puts the fitness on the PS, because the carrier's raw functional readout already *is* the
whole phenotype (`docs/b2_architecture.md` §2). The landscape is a public seeded rule; three
non-additive fitnesses were fixed in a frozen order; the (μ + λ) engine and the two
operators are shared code with one difference; five controls (oracle, shuffled,
within-LUT-shuffled, three degraded maps) ride the same code path. The **discriminability
gate** (host simulation, 200 landscape seeds, every arm, every fitness) was specified
before it ran. Run 1 failed every fitness on four rows that the run showed were
mis-specified (the budget rule, a wrong "a negative must appear" test, a cost cap tied to
an unstated audit policy, a wrong continuity assumption); the rules were revised **with the
reasons written down and the first report kept**, and run 3 on a clean tree with fresh
seeds **passes F1**; re-evaluated under rules v0.3 (§0a) it still does: B* = 600
evaluations per arm, N = 9 pairs, **10 800 evaluations in total** — how many
all-self-reporting sessions they take is decided by the B2Q-measured rate (three at the
last B1 mapping's rate). F2 and F3 also discriminate but cost 2× more. The shuffled and
within-LUT maps **lose** to random-safe, and the predeclared controls of v0.3 §7a show the
benefit is **correct column grouping** beyond train membership and beyond the size
distributions (G9); the dose–response is monotone and crosses zero (a poor map is worse
than none); holdout is neutral **for F1 / F2** (F3's trajectories reach holdout rows). The
frozen session seeds predict **8 of 9 pairs positive (p = 0.0195)** — the minimum that
passes; the silicon run is a prospective reproduction of that prediction.

## 0a. The review's findings and their corrections (v0.2)

| finding (review §2) | correction | where |
|---|---|---|
| controls D / E cross the train / holdout boundary: the benefit was not attributable to column grouping | two controls predeclared in architecture v0.3 §7a **before running** (`fcfff98`): **T** train-membership only, **W** within-train column scramble (membership and column-size / move-size distributions kept); **G9** = B beats both by exact sign tests at B*. Run on run 3's 200 seeds: **PASS on F1 / F2 / F3** (F1 at 600: B − T +3.23, 169/17/14, p 6e-33; B − W +3.63, 172/17/11, p 9e-34; T retains 22 %, W 13 % of B's benefit). The claim is attributed; D / E stand as "a wrong map costs budget" | `host/b2_maps.py`, `host/b2_gate.py controls`, `evidence/b2/gate/recomputed_2026_09_10/controls_report.json`, `docs/b2_gate_report_v0.3.md` §4, `tests/test_b2_maps.py`, `tests/test_b2_gate.py` |
| `required_pairs` skipped candidate N (F3 / 300: 91 returned, 89 had power 0.906) | a full ascending scan, no bracketing, no n_max shortcut; the counterexample is a test (N = 89, power 0.906, cost 53 400); a synthetic non-monotone profile is a second test. Run 3's rows re-evaluated under v0.3 into a labelled directory (run 3's report untouched): **F1 still selected, B* = 600, N = 9, 10 800**; F2 (N = 8 at 1 500, 24 000) and F3 (N = 13 at 800, 20 800) still fail on cost only | `host/b2_gate.py`, `evidence/b2/gate/recomputed_2026_09_10/gate_report.json`, `tests/test_b2_gate.py` |
| B3 ignored contradictions on decoded addresses; refusals mutated state | `SpecimenCarto.observe` validates (malformed specimens, a decoded moved address whose position is missing, a position of an unmoved decoded address, empty intersections, closure conflicts) and **commits atomically**; the review's three counterexamples plus closure-conflict and malformed cases are tests with `snapshot()` equality; the ideal-model simulation re-run on the same seeds is **bit-identical** (400 rows) | `host/b3_online.py` (carto v1.1), `evidence/b3/sim_v0.1.1/`, `tests/test_b3_online.py` |
| sampled-audit replay underspecified; "recompute every fitness" overclaimed | **all-self-reporting** for B2 (the owner's decision): every record's six readout words served and host-verified; every fitness recomputed from a *measured* readout; no readout-hash language; a sampled policy is not specified for B2 and what one would need is listed | `docs/b2_preregistration.md` §2, §4 |
| B2Q / calibration / final-manifest lifecycle not closed | `host/b2_manifest.py`: S0 init (carrier **lineage** from the B1 manifest, re-verified — certifies history, qualifies nothing) → S1 freeze → S2 qualify (record bound to `manifest_at_run`; the measured rate written into `calibration` in the same licensed transition) → S3 plan (regenerated from the calibration; split and rate checked). B1's strict rule kept; the plan edit that used to break the binding is now the licensed, checked production. Exercised on disk in fresh processes; every later change refused; B1 files asserted unchanged | `host/b2_manifest.py`, `tests/test_b2_lifecycle.py` (6 tests, 20+ refusals), `docs/b2_preregistration.md` §8 |
| a negative primary was impossible under the EXACT prediction gate | the silicon run is a **prospective reproduction of a predicted outcome**; a mismatch is HOLD / KILL; the falsifier that could not occur is removed; a design whose primary is not fixed by the prediction is named as a separate preregistration | `docs/b2_preregistration.md` §1, §3, §4, §5 |
| documentation / provenance (review §3) | four changed rows; `9f347e9` vs `342450b`; canonical-JSON vs file-byte digests (`c6a4b23e…` / `b6607a9a…`), both pinned in the manifest; F3's train trajectories enter holdout rows (seed 123 example) — the neutrality reading restricted to F1 / F2; F1 / F2 have many train optima; Cohen's d at the selected budgets **F2 1.4437, F1 1.5364, F3 0.8506** (§2 below corrected); seed exclusion explicit (1 223 values, recorded in the plan); the sign test stated exactly (ties move the threshold); B3's accounting named an evaluation-count model; "grow without bound" withdrawn; O − F at all budgets = exploratory | `docs/b2_architecture.md` v0.3 header and §8, `docs/b3_architecture.md`, `host/b2_plan.py` |
| the "ahead 10" statement | nine commits were ahead of `6ac2cf2` at review; corrected in the memory file | — |

## 0b. The second review's lifecycle findings and their corrections (v0.2.1)

| finding (review v02 §2) | correction | where |
|---|---|---|
| 1 frozen live inputs not enforced (missing pins filtered out; lineage a diagnostic; a stored chain flag; prereg / map / image not re-hashed) | `verify()` refuses on: any required pin missing from the manifest, absent from the tree or changed; the map changed in **either** encoding or no longer validating; the frozen preregistration's bytes changed; the build-evidence file changed or not naming the image; the B1 manifest file changed or its carrier not this carrier; and the B1 qualification chain **re-verified fresh** by `b1_qualification.verify` on every call (no stored flag). File-only mutation tests on a mirrored tree (deletion, whitespace on prereg / map / B1 manifest) with an unchanged manifest and evidence | `host/b2_manifest.py` `_check_frozen_inputs`, `tests/test_b2_lifecycle.py` |
| 2 calibration and record not reconstructed from evidence | the record is **reconstructed from the evidence files** (exact file set, hashes, the adjudication's outcome / rate / policy, the binding from `manifest_at_run`) and compared field by field with the embedded one; the record schema and key sets are exact; the calibration must equal the one derived from the reconstruction under the split rule; the re-adjudication must agree on outcome **and** rate **and** policy; the policy must be the frozen audit policy. Record + calibration co-mutation, policy change, empty file table: each refused with unchanged evidence | same; tests |
| 3 S3 plan derivation unvalidated | one validator `plan_findings` used at pinning and at every verify: fitness / budget / pairs / engine / map (canonical digest and path) / audit policy / seed derivation (master, label, commit) / the whole split against the calibration / the span limit / the prediction file's hash / the prediction's seed sequence / **the prediction re-derived by the reference engine** (`b2_plan.predict`) for the frozen experiment, seeds and map. `pin_plan` verifies the manifest first (never its flag) and re-verifies the result. Wrong-field tests at pinning and at re-verification with the file hash updated | same; `host/b2_plan.predict`; tests |
| 4 infeasible rate accepted | `session_split` raises on a non-finite / non-positive rate and returns **INFEASIBLE** when not even one pair with its baselines fits the registered expected span; `calibration_from` and `plan_findings` refuse on INFEASIBLE; the one-pair boundary (602 records / h) and 0 / −1 / NaN / ∞ are tests | `host/b2_plan.py`, `tests/test_b2_plan.py` |
| P3 documentation | §0 above agrees with §0a (four rows, total evaluations, F1 / F2 holdout); the plan module's docstring says exclusion is enforced, not assumed | — |

## 1. What was built (host-only; every file additive; nothing in B1 or the instrument changed)

| file | role | tests |
|---|---|---|
| `docs/b2_architecture.md` v0.2 | D1 carrier kept; D2 landscape; the fitness family F2/F1/F3 in frozen order; D3 engine; D4 operators and the controls; the autonomy boundary; §7 gate criteria and the selection rule; the v0.1 → v0.2 revision with reasons; §8 what is not claimed | `test_b2_gate.test_thresholds_are_the_architecture_documents` |
| `host/b2_landscape.py` | universe mask, public target rule, train/holdout, F1/F2/F3 | `tests/test_b2_landscape.py` (13) |
| `host/b2_maps.py` | the operator's view of a `self_map` 2.0.0; oracle / shuffled / within-LUT-shuffled / degraded renderings; schema validation (draft 2020-12, a missing validator is a refusal) | `tests/test_b2_maps.py` (11) |
| `host/b2_search.py` | the (μ + λ) engine, the two operators, the model fabric with the incremental toggle, seed derivation | `tests/test_b2_search.py` (13) |
| `host/b2_gate.py` | the gate: runs, statistics (exact sign test, bootstrap power, Cohen's d), criteria G1–G8, the budget rule, the report | `tests/test_b2_gate.py` (21; one negative per criterion through `evaluate()`) |
| `host/b2_gate_report_md.py` | renders `docs/b2_gate_report.md` from the JSON | — |
| `host/b2_plan.py` | the session seeds by the B1 rule under `b2-session|` with every archived set excluded, the all-self-reporting plan, the frozen split rule (`session_split`), the prediction | `tests/test_b2_plan.py` (8) |
| `host/b2_manifest.py` (v0.2) | the manifest lifecycle S0–S3 and `verify` | `tests/test_b2_lifecycle.py` (6, fresh-process) |
| `evidence/b2/gate/` | run 3 (rules v0.2, as run): `gate_report.json`, `raw_F1/F2/F3.json`; run 1 (rules v0.1) under `v0.1_2026-09-10/`; **`recomputed_2026_09_10/`** = run 3's rows under rules v0.3 + the §7a controls (`controls_report.json`, `raw_controls_*.json`) | — |
| `evidence/b2/plan.json`, `prediction.json` | the frozen-seed plan (split UNDETERMINED until S2) and prediction — deltas unchanged by the corrections | — |
| `docs/b2_gate_report_v0.3.md` | the recomputation and G9, rendered from the JSON | — |
| `docs/b2_preregistration.md` DRAFT v0.2 | the claim as a prospective reproduction, pins, prediction, decision rule, falsifiers, the sessions and the split rule, compatibility, the lifecycle and freeze | — |

## 2. What the gate showed (`docs/b2_gate_report.md`; the numbers are the JSON's)

- **Discrimination is not the problem.** On every fitness arm B (self-map) beats arm A
  (random-safe) with a large effect at the selected budget (at B*: F1 / 600 Cohen's d 1.5364,
  182 / 9 / 9 positives / negatives / ties over 200 seeds; F2 / 1 500 d 1.4437; F3 / 800
  d 0.8506 — the v0.1 prose's "F2 ≈ 0.8 / F3 ≈ 0.7" were stale run-1 numbers).
- **A wrong map does not merely fail to help; it hurts.** Shuffled (D) and within-LUT
  shuffled (E) have negative mean Δ on every fitness, and the sign test on D is nowhere near
  significant. D and E also move addresses across the train / holdout boundary, so this
  shows a wrong map costs budget; it does **not** by itself attribute the benefit.
- **The attribution is G9 (v0.2):** the self-map beats train-membership-only (T) and the
  within-train column scramble (W) on every fitness — correct column grouping adds benefit
  beyond knowing which addresses matter and beyond the column-size / move-size
  distributions (`docs/b2_gate_report_v0.3.md` §4).
- **Dose–response**: Δ falls monotonically with the fraction of the map removed and crosses
  zero between q = ½ and q = ¾. Under the ½ mixture a poor map diverts half the budget to a
  small subset. This is a property of the operator and is stated, not tuned (architecture
  §8); the mixture weight was not changed after seeing it.
- **Holdout is neutral**: champion holdout medians are equal across arms.
- **Cost decides between fitnesses**, not discrimination: F1's powered test is 10 800
  evaluations in total; F2 needs 24 000, F3 20 800. How many all-self-reporting sessions
  10 800 take is decided by the B2Q-measured rate under the split rule (at the last B1
  mapping's ≈ 2 807 / h: three sessions, 4 + 4 + 1; two is not assumed).
- **Consistency across seed sets**: F1 was the passing fitness in run 2 (`eff1771`, N = 10,
  12 000) and run 3 (`7b49f4c`, N = 9, 10 800); run 1 under the v0.1 rules already showed
  the same effects with the failing rows being cost, the q = 1 endpoint and the F1 sign
  test at 1 500 (200/200 positive).

## 3. What the owner is asked to rule on (v0.2)

The five items of v0.1 were decided in the review (D1–D4 accepted in principle; the gate
revisions accepted as development revisions; all-self-reporting; N = 9 retained; no image
yet). What is asked now:

1. **Re-review of the corrections** (§0a) — in particular: the §7a controls and G9 as the
   attribution; the v0.3 G5 (a total-evaluation bound; sessions from the measured rate);
   the reproduction framing of the preregistration; the lifecycle S0–S3 and its tests.
2. **Whether the HOLD is lifted** for (a) pushing the batch, (b) building the image under
   the preregistration's §7 guards. Neither is assumed. No B3 firmware or board work is
   asked.

## 4. What is not asked, and not done

No board contact. No image. No manifest. No ruling text. No change to `zynq-psoracle`, to
B1's files, evidence or manifest, or to the B1 carrier. No probe of unattested bits, no
routing, no `08EB`. No tuning of the engine or the operator after the gate. B3 is a separate
package (`docs/b3_architecture.md`, design and host simulation only).

## 5. Tests and the clean-tree proof

The whole suite (B1's 1 456 + B2/B3's) runs from a clean tree; the result line and the
tested commit are in the commit message of the batch's last commit. A `b2_test_report.py`
in `host/b1_test_report.py`'s discipline comes with the image.

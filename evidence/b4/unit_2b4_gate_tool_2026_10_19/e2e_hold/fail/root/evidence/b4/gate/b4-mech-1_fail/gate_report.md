# B4 gate judgement — b4-mech-1 — **FAIL** (NOT A GATE RESULT)

Generated 2026-10-19T15:02:41Z at HEAD `88ea2711d81545dbc3cd593f7f1c2676f5285cf1` (clean tree: True). Evidence: batch_archive `evidence/b4/sim/b4-mech-1_fail` (status complete, label b4-mech-1, S = 2, fixture True, sha256 `adf61fff071d3c1f543abe47eb59d794a1d372869e52675a68f6f52b55f01fec`; seeds `a08056c0f9c7101c34cbc1ab3fc436a355e726414f2e22241029a4277e725c8c`, manifest `bc2602da6bdd32003b1259e9d7d640510f8768f4291bfbb87255759335458296`; batch HEAD `88ea2711d81545dbc3cd593f7f1c2676f5285cf1`).

Hypothesis `59948f9be3b4516547fbf039556d4aa6a4afd0b2dda2324619e4d40ef0651ed8`, certificate `c69e419f836684872c9edb3754cdb7c76591aaabf69859dab448454c6d78ceef`; thresholds: docs/b4_architecture.md section 9 (v0.1.16), fixed before any exploration or gate run.

**Standing.** NOT A GATE RESULT: the gate's rows applied as written to batch_archive evidence under the label 'b4-mech-1' so that the tool's paths are exercised; this judgement can never be represented as a real gate result — the formal result needs the pinned gate label, S = 200 as planned and a production batch archive

**Scope.** every result is under the behaviour hypothesis v0.3 and the certificate mapping of the one site; a FAIL is confined to this model, public task / panel, operator / control design, budget grid and declared decision procedure; nothing here is a statement about silicon, about the carrier, or about the content class in general; a PASS is never read as evidence about the fabric

**Why this is not the formal result:** a fixture batch; the label 'b4-mech-1' is not the pinned gate label 'b4-gate-1'; S = 2 is not the planned 200.

## Verdict: **FAIL** — a complete, valid batch on which budget rule FAILS; K6 FAILS; K9 FAILS; not assessable: K1, K2, K3, K4, K5, K7 — no threshold is adjusted, no budget or sample repaired

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
| K1 | non-saturation | **not_assessable** | no B*: the budget rule failed (no grid budget has both K1 eligibility and an N); K1's eligibility per budget is in the budget rule's record | `{"k1_by_budget":{"128":{"eligibility":true,"median_base":34.0,"median_best_R":41.0,"omega_best_p95":45.6},"16":{"eligibility":true,"median_base":34.0,"median_best_R":38.5,"omega_best_p95":35.9},"192":{"eligibility":true,"median_base":34.0,"median_best_R":41.0,"omega_best_p95":46.55},"24":{"eligibility":true,"median_base":34.0,"median_best_R":38.5,"omega_best_p95":40.75},"256":{"eligibility":true,"median_base":34.0,"median_best_R":41.0,"omega_best_p95":46.8},"32":{"eligibility":true,"median_base":34.0,"median_best_R":38.5,"omega_best_p95":42.65},"48":{"eligibility":true,"median_base":34.0,"median_best_R":39.5,"omega_best_p95":43.6},"64":{"eligibility":true,"median_base":34.0,"median_best_R":40.0,"omega_best_p95":43.7},"8":{"eligibility":true,"median_base":34.0,"median_best_R":38.5,"omega_best_p95":35.9},"96":{"eligibility":true,"median_base":34.0,"median_best_R":41.0,"omega_best_p95":45.6}}}` | `{"medians":"median_r(best_R(B)) > median_r(base_r), two medians compared","omega_best_p95_lt":64}` |
| K2 | not a definitional lock | **not_assessable** | no B*: the budget rule failed (no grid budget has both K1 eligibility and an N) | `null` | `{"population_variance_gt":0,"x_minus_r_nonrejection_min":0.9}` |
| K3 | wrong maps do not profit | **not_assessable** | no B*: the budget rule failed (no grid budget has both K1 eligibility and an N) | `null` | `{"ratio_max":0.1,"sign_test_p_gt":0.05}` |
| K4 | headroom against the certificate-derived grouping | **not_assessable** | no B*: the budget rule failed (no grid budget has both K1 eligibility and an N) | `null` | `{"f_over_omega_min":0.5,"omega_median_max":57.6}` |
| K5 | effect, power, N | **not_assessable** | no B*: the budget rule failed (no grid budget has both K1 eligibility and an N) | `null` | `{"cap_search_evaluations":4000,"cohen_d_min":0.5,"power_min":0.9}` |
| K6 | no fixed-seed lock | **FAIL** | S = 2 is not the planned 200; N does not exist | `{"N":null,"S_planned":2}` | `{"N_min":8,"S_gate":200}` |
| K7 | the map is a map | **not_assessable** | (a) holds by the completion contract of a complete batch (every arm audited with no recompute finding); (b) needs B*: no B*: the budget rule failed (no grid budget has both K1 eligibility and an N) | `{"a_basis":"complete batch: every executed run audited clean","a_recomputation_mismatches":0,"b_median_by_budget":{"128":16.5,"16":3.0,"192":19.0,"24":4.5,"256":20.5,"32":5.0,"48":7.5,"64":10.0,"8":1.0,"96":14.5}}` | `{"o_prefix_median_not_unknown_min":11,"recomputation_mismatches":0}` |
| K8 | ledger replay | **PASS** | holds by the completion contract of a complete batch | `{"basis":"complete batch: the replay of every executed run recorded no finding (each arm's audit); re-audited by the archive-wide verifier"}` | `{"replay":"no finding on every executed run; a broken tool contract is invalid under section 9.1"}` |
| K9 | observability | **FAIL** | (b) median coverage below 0.50: ff_srval 0.458333, sr_kind 0.375 | `{"fraction_of_S_with_all_seven_positive_controls":1.0,"per_semantic":{"ce_mode":{"conditional_on_A8":false,"median_coverage_over_all_S":1.0,"not_assessable_seeds":0,"seeds_with_positive_control":2},"clock_mode":{"conditional_on_A8":false,"median_coverage_over_all_S":1.0,"not_assessable_seeds":0,"seeds_with_positive_control":2},"ff_init":{"conditional_on_A8":true,"median_coverage_over_all_S":1.0,"not_assessable_seeds":0,"seeds_with_positive_control":2},"ff_srval":{"conditional_on_A8":false,"median_coverage_over_all_S":0.45833333333333337,"not_assessable_seeds":0,"seeds_with_positive_control":2},"sr_kind":{"conditional_on_A8":false,"median_coverage_over_all_S":0.375,"not_assessable_seeds":0,"seeds_with_positive_control":2},"sr_mode":{"conditional_on_A8":false,"median_coverage_over_all_S":1.0,"not_assessable_seeds":0,"seeds_with_positive_control":2},"storage_kind":{"conditional_on_A8":false,"median_coverage_over_all_S":1.0,"not_assessable_seeds":0,"seeds_with_positive_control":2}},"seeds_with_all_seven_positive_controls":2}` | `{"median_coverage_per_semantic_min":0.5,"seeds_with_all_seven_positive_controls_min":0.9}` |
| K10 | real interaction | **PASS** | interacting seeds / S >= 0.50 | `{"counts":{"interacting":2,"no_interaction_seen_among_tested_comparisons":0,"nonzero_below_threshold":0,"not_assessable":0},"fraction_interacting_over_S":1.0,"tau":2}` | `{"interacting_seeds_over_S_min":0.5,"tau":2}` |

### Methods (fixed; section 9)

- **K1** — percentile(best_Omega(B*), 95) < 64 (B2 linear interpolation, by copy) and median_r(best_R(B*)) > median_r(base_r), two medians compared; eligibility at every grid budget decides B*
- **K2** — population variance of {delta1_r} at B* > 0; one grid budget with positives and negatives of delta1; the one-sided exact sign test on X - R at B* with size N (H1: P(X - R > 0 | X - R != 0) > 1/2) not rejecting H0 in >= 90 % of 1 000 bootstrap experiments (random.Random(7), alpha 0.05, ties out of n and kept in the population)
- **K3** — mean(F - R) > 0 and mean(D - R) <= 0.10 mean(F - R); mean(O - R) > 0 and mean(X - R) <= 0.10 mean(O - R); D's and X's one-sided sign tests (H1: P(control - R > 0 | != 0) > 1/2) not significant (p > 0.05); a non-positive denominator is not readable as satisfied
- **K4** — median_r(best_Omega(B*)) <= 0.90 * 64 = 57.6; mean(Omega - R) > 0 and mean(F - R) >= 0.50 mean(Omega - R)
- **K5** — paired Cohen's d of {delta1_r} at B* >= 0.5; N(B*) by the complete ascending scan of required_pairs (8 .. S, alpha 0.05, bootstrap power >= 0.90, 1 000 experiments, random.Random(1 + N)); N x 3 x B* <= 4 000 search evaluations
- **K6** — S = 200 planned (never the number completed) and N >= 8
- **K7** — (a) zero recomputation mismatches on every arm's own ledger (the completion contract: each audit's recompute findings empty, re-audited by the archive-wide verifier); (b) median_r over seeds of the addresses whose state is not unknown in arm O's B* prefix >= 11 of 21
- **K8** — the replay of every executed run reports no finding, the recorded q grid recomputes the recorded fitness, X's shadow isomorphism and the source-identity / fixture boundary hold (the completion contract; a break is invalid under 9.1)
- **K9** — on the fixed comparison set of 9.3: (a) >= 90 % of all S seeds have, for each of the seven semantics, an applicable pair whose readouts differ; (b) per semantic, the median over all S seeds of the coverage fraction >= 0.50 (a semantic not assessable for one seed has no median and does not meet (b))
- **K10** — tau = 2: interacting seeds (max|I| > 2 over both fixed backgrounds, all 210 pairs) / all S >= 0.50; not-assessable seeds stay in the denominator

## Diagnostics (no threshold)

```json
{
 "deadline": {
  "checks": 3295,
  "clock": "time.monotonic",
  "elapsed_s": 17.96,
  "expired": false,
  "first_expired_at_s": null,
  "seconds": 3600
 },
 "k10": {
  "S": 2,
  "counts": {
   "interacting": 2,
   "no_interaction_seen_among_tested_comparisons": 0,
   "nonzero_below_threshold": 0,
   "not_assessable": 0
  },
  "fraction_interacting_over_S": 1.0,
  "note": "a seed with no comparable pair is not assessable and stays in the denominator; all comparable pairs at zero means no interaction seen among the tested comparisons, not that every context is additive; with tau = 0 the nonzero-below-threshold class is empty by definition",
  "tau": 2
 },
 "k9_per_semantic": {
  "ce_mode": {
   "conditional_on_A8": false,
   "median_coverage_over_all_S": 1.0,
   "median_rule": "all S seeds; one not-assessable seed makes the semantic's median not assessable",
   "not_assessable_seeds": 0,
   "seeds_with_positive_control": 2
  },
  "clock_mode": {
   "conditional_on_A8": false,
   "median_coverage_over_all_S": 1.0,
   "median_rule": "all S seeds; one not-assessable seed makes the semantic's median not assessable",
   "not_assessable_seeds": 0,
   "seeds_with_positive_control": 2
  },
  "ff_init": {
   "conditional_on_A8": true,
   "median_coverage_over_all_S": 1.0,
   "median_rule": "all S seeds; one not-assessable seed makes the semantic's median not assessable",
   "not_assessable_seeds": 0,
   "seeds_with_positive_control": 2
  },
  "ff_srval": {
   "conditional_on_A8": false,
   "median_coverage_over_all_S": 0.45833333333333337,
   "median_rule": "all S seeds; one not-assessable seed makes the semantic's median not assessable",
   "not_assessable_seeds": 0,
   "seeds_with_positive_control": 2
  },
  "sr_kind": {
   "conditional_on_A8": false,
   "median_coverage_over_all_S": 0.375,
   "median_rule": "all S seeds; one not-assessable seed makes the semantic's median not assessable",
   "not_assessable_seeds": 0,
   "seeds_with_positive_control": 2
  },
  "sr_mode": {
   "conditional_on_A8": false,
   "median_coverage_over_all_S": 1.0,
   "median_rule": "all S seeds; one not-assessable seed makes the semantic's median not assessable",
   "not_assessable_seeds": 0,
   "seeds_with_positive_control": 2
  },
  "storage_kind": {
   "conditional_on_A8": false,
   "median_coverage_over_all_S": 1.0,
   "median_rule": "all S seeds; one not-assessable seed makes the semantic's median not assessable",
   "not_assessable_seeds": 0,
   "seeds_with_positive_control": 2
  }
 },
 "per_budget": {
  "128": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -1.0,
    "median": -1.0,
    "n": 2,
    "negatives": 1,
    "population_variance": 1,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -1.0,
    "median": -1.0,
    "n": 2,
    "negatives": 1,
    "population_variance": 1,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "arm_medians": {
    "A0": 40.0,
    "D": 40.0,
    "F": 40.0,
    "O": 40.0,
    "Omega": 42.0,
    "R": 41.0,
    "X": 40.0
   },
   "base_median": 34.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -1.0,
    "median": -1.0,
    "n": 2,
    "negatives": 1,
    "population_variance": 1,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.7071067811865475
    },
    "mean": 0.5,
    "median": 0.5,
    "n": 2,
    "negatives": 0,
    "population_variance": 0.25,
    "positives": 1,
    "sign_test_p": 0.5,
    "ties": 1
   },
   "k1": {
    "eligibility": true,
    "median_base": 34.0,
    "median_best_R": 41.0,
    "omega_best_p95": 45.6
   },
   "power_at_N_or_last": null
  },
  "16": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -2.0,
    "median": -2.0,
    "n": 2,
    "negatives": 1,
    "population_variance": 4,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.0
    },
    "mean": 0.0,
    "median": 0.0,
    "n": 2,
    "negatives": 0,
    "population_variance": 0,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 2
   },
   "arm_medians": {
    "A0": 37.0,
    "D": 37.0,
    "F": 36.5,
    "O": 38.5,
    "Omega": 35.0,
    "R": 38.5,
    "X": 38.5
   },
   "base_median": 34.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.0
    },
    "mean": 0.0,
    "median": 0.0,
    "n": 2,
    "negatives": 0,
    "population_variance": 0,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 2
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.7071067811865476
    },
    "mean": 4.5,
    "median": 4.5,
    "n": 2,
    "negatives": 0,
    "population_variance": 20.25,
    "positives": 1,
    "sign_test_p": 0.5,
    "ties": 1
   },
   "k1": {
    "eligibility": true,
    "median_base": 34.0,
    "median_best_R": 38.5,
    "omega_best_p95": 35.9
   },
   "power_at_N_or_last": null
  },
  "192": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.23570226039551587
    },
    "mean": -0.5,
    "median": -0.5,
    "n": 2,
    "negatives": 1,
    "population_variance": 2.25,
    "positives": 1,
    "sign_test_p": 0.75,
    "ties": 0
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -1.0,
    "median": -1.0,
    "n": 2,
    "negatives": 1,
    "population_variance": 1,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "arm_medians": {
    "A0": 42.0,
    "D": 41.0,
    "F": 40.5,
    "O": 40.0,
    "Omega": 42.5,
    "R": 41.0,
    "X": 40.0
   },
   "base_median": 34.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -1.0,
    "median": -1.0,
    "n": 2,
    "negatives": 1,
    "population_variance": 1,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -0.5,
    "median": -0.5,
    "n": 2,
    "negatives": 1,
    "population_variance": 0.25,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "k1": {
    "eligibility": true,
    "median_base": 34.0,
    "median_best_R": 41.0,
    "omega_best_p95": 46.55
   },
   "power_at_N_or_last": null
  },
  "24": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865476
    },
    "mean": -1.5,
    "median": -1.5,
    "n": 2,
    "negatives": 1,
    "population_variance": 2.25,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.0
    },
    "mean": 0.0,
    "median": 0.0,
    "n": 2,
    "negatives": 0,
    "population_variance": 0,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 2
   },
   "arm_medians": {
    "A0": 37.0,
    "D": 37.5,
    "F": 37.0,
    "O": 38.5,
    "Omega": 38.5,
    "R": 38.5,
    "X": 38.5
   },
   "base_median": 34.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.0
    },
    "mean": 0.0,
    "median": 0.0,
    "n": 2,
    "negatives": 0,
    "population_variance": 0,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 2
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.7071067811865476
    },
    "mean": 4.5,
    "median": 4.5,
    "n": 2,
    "negatives": 0,
    "population_variance": 20.25,
    "positives": 1,
    "sign_test_p": 0.5,
    "ties": 1
   },
   "k1": {
    "eligibility": true,
    "median_base": 34.0,
    "median_best_R": 38.5,
    "omega_best_p95": 40.75
   },
   "power_at_N_or_last": null
  },
  "256": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.23570226039551587
    },
    "mean": -0.5,
    "median": -0.5,
    "n": 2,
    "negatives": 1,
    "population_variance": 2.25,
    "positives": 1,
    "sign_test_p": 0.75,
    "ties": 0
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -1.0,
    "median": -1.0,
    "n": 2,
    "negatives": 1,
    "population_variance": 1,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "arm_medians": {
    "A0": 42.0,
    "D": 41.5,
    "F": 40.5,
    "O": 40.0,
    "Omega": 45.0,
    "R": 41.0,
    "X": 40.0
   },
   "base_median": 34.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -1.0,
    "median": -1.0,
    "n": 2,
    "negatives": 1,
    "population_variance": 1,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -0.5,
    "median": -0.5,
    "n": 2,
    "negatives": 1,
    "population_variance": 0.25,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "k1": {
    "eligibility": true,
    "median_base": 34.0,
    "median_best_R": 41.0,
    "omega_best_p95": 46.8
   },
   "power_at_N_or_last": null
  },
  "32": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865476
    },
    "mean": -1.5,
    "median": -1.5,
    "n": 2,
    "negatives": 1,
    "population_variance": 2.25,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.0
    },
    "mean": 0.0,
    "median": 0.0,
    "n": 2,
    "negatives": 0,
    "population_variance": 0,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 2
   },
   "arm_medians": {
    "A0": 37.0,
    "D": 38.5,
    "F": 37.0,
    "O": 38.5,
    "Omega": 39.5,
    "R": 38.5,
    "X": 38.5
   },
   "base_median": 34.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.0
    },
    "mean": 0.0,
    "median": 0.0,
    "n": 2,
    "negatives": 0,
    "population_variance": 0,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 2
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.7071067811865475
    },
    "mean": 2.5,
    "median": 2.5,
    "n": 2,
    "negatives": 0,
    "population_variance": 6.25,
    "positives": 1,
    "sign_test_p": 0.5,
    "ties": 1
   },
   "k1": {
    "eligibility": true,
    "median_base": 34.0,
    "median_best_R": 38.5,
    "omega_best_p95": 42.65
   },
   "power_at_N_or_last": null
  },
  "48": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -2.0,
    "median": -2.0,
    "n": 2,
    "negatives": 1,
    "population_variance": 4,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -0.5,
    "median": -0.5,
    "n": 2,
    "negatives": 1,
    "population_variance": 0.25,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "arm_medians": {
    "A0": 39.5,
    "D": 39.0,
    "F": 37.5,
    "O": 39.0,
    "Omega": 40.0,
    "R": 39.5,
    "X": 39.0
   },
   "base_median": 34.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -0.5,
    "median": -0.5,
    "n": 2,
    "negatives": 1,
    "population_variance": 0.25,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.7071067811865475
    },
    "mean": 2.0,
    "median": 2.0,
    "n": 2,
    "negatives": 0,
    "population_variance": 4,
    "positives": 1,
    "sign_test_p": 0.5,
    "ties": 1
   },
   "k1": {
    "eligibility": true,
    "median_base": 34.0,
    "median_best_R": 39.5,
    "omega_best_p95": 43.6
   },
   "power_at_N_or_last": null
  },
  "64": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -2.0,
    "median": -2.0,
    "n": 2,
    "negatives": 1,
    "population_variance": 4,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -1.0,
    "median": -1.0,
    "n": 2,
    "negatives": 1,
    "population_variance": 1,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "arm_medians": {
    "A0": 39.5,
    "D": 40.0,
    "F": 38.0,
    "O": 39.5,
    "Omega": 41.0,
    "R": 40.0,
    "X": 39.0
   },
   "base_median": 34.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -0.5,
    "median": -0.5,
    "n": 2,
    "negatives": 1,
    "population_variance": 0.25,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.7071067811865475
    },
    "mean": 2.0,
    "median": 2.0,
    "n": 2,
    "negatives": 0,
    "population_variance": 4,
    "positives": 1,
    "sign_test_p": 0.5,
    "ties": 1
   },
   "k1": {
    "eligibility": true,
    "median_base": 34.0,
    "median_best_R": 40.0,
    "omega_best_p95": 43.7
   },
   "power_at_N_or_last": null
  },
  "8": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -2.5,
    "median": -2.5,
    "n": 2,
    "negatives": 1,
    "population_variance": 6.25,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.0
    },
    "mean": 0.0,
    "median": 0.0,
    "n": 2,
    "negatives": 0,
    "population_variance": 0,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 2
   },
   "arm_medians": {
    "A0": 36.0,
    "D": 36.5,
    "F": 36.0,
    "O": 38.5,
    "Omega": 35.0,
    "R": 38.5,
    "X": 38.5
   },
   "base_median": 34.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.0
    },
    "mean": 0.0,
    "median": 0.0,
    "n": 2,
    "negatives": 0,
    "population_variance": 0,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 2
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.7071067811865476
    },
    "mean": 4.5,
    "median": 4.5,
    "n": 2,
    "negatives": 0,
    "population_variance": 20.25,
    "positives": 1,
    "sign_test_p": 0.5,
    "ties": 1
   },
   "k1": {
    "eligibility": true,
    "median_base": 34.0,
    "median_best_R": 38.5,
    "omega_best_p95": 35.9
   },
   "power_at_N_or_last": null
  },
  "96": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -2.1213203435596424
    },
    "mean": -1.5,
    "median": -1.5,
    "n": 2,
    "negatives": 2,
    "population_variance": 0.25,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 0
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -1.0,
    "median": -1.0,
    "n": 2,
    "negatives": 1,
    "population_variance": 1,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "arm_medians": {
    "A0": 40.0,
    "D": 40.0,
    "F": 39.5,
    "O": 40.0,
    "Omega": 42.0,
    "R": 41.0,
    "X": 40.0
   },
   "base_median": 34.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.7071067811865475
    },
    "mean": -1.0,
    "median": -1.0,
    "n": 2,
    "negatives": 1,
    "population_variance": 1,
    "positives": 0,
    "sign_test_p": 1.0,
    "ties": 1
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.7071067811865476
    },
    "mean": 1.5,
    "median": 1.5,
    "n": 2,
    "negatives": 0,
    "population_variance": 2.25,
    "positives": 1,
    "sign_test_p": 0.5,
    "ties": 1
   },
   "k1": {
    "eligibility": true,
    "median_base": 34.0,
    "median_best_R": 41.0,
    "omega_best_p95": 45.6
   },
   "power_at_N_or_last": null
  }
 },
 "standing_of_the_batch": "exploration data under the label given, S as planned; not a gate verdict; the thresholds of docs/b4_architecture.md v0.1.15 section 9 are listed for reference only; candidate B* / N are estimates on this S, never the formal S = 200's"
}
```

Self-validation and the file index are in `gate_report.json`; the verifier `b4_gate_verify.py` recomputes this judgement from the evidence and re-renders this file.

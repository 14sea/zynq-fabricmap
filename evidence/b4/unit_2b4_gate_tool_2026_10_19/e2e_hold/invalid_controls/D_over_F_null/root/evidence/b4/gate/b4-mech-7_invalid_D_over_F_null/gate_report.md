# B4 gate judgement — b4-mech-7 — **invalid** (NOT A GATE RESULT)

Generated 2026-10-19T15:03:33Z at HEAD `a698b3649aa762a495fe1639dac6c83291f2ccc9` (clean tree: True). Evidence: synthetic_summary `evidence/b4/gate/b4-mech-7_invalid_D_over_F_null/synthetic_summary.json` (status complete, label b4-mech-7, S = 200, fixture True, sha256 `fa4f2aba2bd13540ab869f4044ef9833f193fd1c17f66bfe15db43970f47af01`; seeds `None`, manifest `None`; batch HEAD `None`).

Hypothesis `59948f9be3b4516547fbf039556d4aa6a4afd0b2dda2324619e4d40ef0651ed8`, certificate `c69e419f836684872c9edb3754cdb7c76591aaabf69859dab448454c6d78ceef`; thresholds: docs/b4_architecture.md section 9 (v0.1.16), fixed before any exploration or gate run.

**Standing.** NOT A GATE RESULT: the gate's rows applied as written to synthetic_summary evidence under the label 'b4-mech-7' so that the tool's paths are exercised; this judgement can never be represented as a real gate result — the formal result needs the pinned gate label, S = 200 as planned and a production batch archive

**Scope.** every result is under the behaviour hypothesis v0.3 and the certificate mapping of the one site; a FAIL is confined to this model, public task / panel, operator / control design, budget grid and declared decision procedure; nothing here is a statement about silicon, about the carrier, or about the content class in general; a PASS is never read as evidence about the fabric

**Why this is not the formal result:** the evidence is synthetic_summary, not a batch archive; a fixture batch; the label 'b4-mech-7' is not the pinned gate label 'b4-gate-1'.

## Verdict: **invalid** — the pooled summary does not satisfy the harness's contract: k3.D_over_F: not an object

## The budget rule — **not_assessable**: B* = None, N = None, N × 3 × B* = None, eligible None

the summary breaks its contract

## The rows

| id | criterion | status | reason | value | threshold |
|---|---|---|---|---|---|
| K1 | non-saturation | **not_assessable** | the summary breaks its contract: nothing is judged | `null` | `{"medians":"median_r(best_R(B)) > median_r(base_r), two medians compared","omega_best_p95_lt":64}` |
| K2 | not a definitional lock | **not_assessable** | the summary breaks its contract: nothing is judged | `null` | `{"population_variance_gt":0,"x_minus_r_nonrejection_min":0.9}` |
| K3 | wrong maps do not profit | **not_assessable** | the summary breaks its contract: nothing is judged | `null` | `{"ratio_max":0.1,"sign_test_p_gt":0.05}` |
| K4 | headroom against the certificate-derived grouping | **not_assessable** | the summary breaks its contract: nothing is judged | `null` | `{"f_over_omega_min":0.5,"omega_median_max":57.6}` |
| K5 | effect, power, N | **not_assessable** | the summary breaks its contract: nothing is judged | `null` | `{"cap_search_evaluations":4000,"cohen_d_min":0.5,"power_min":0.9}` |
| K6 | no fixed-seed lock | **not_assessable** | the summary breaks its contract: nothing is judged | `null` | `{"N_min":8,"S_gate":200}` |
| K7 | the map is a map | **not_assessable** | the summary breaks its contract: nothing is judged | `null` | `{"o_prefix_median_not_unknown_min":11,"recomputation_mismatches":0}` |
| K8 | ledger replay | **not_assessable** | the summary breaks its contract: nothing is judged | `null` | `{"replay":"no finding on every executed run; a broken tool contract is invalid under section 9.1"}` |
| K9 | observability | **not_assessable** | the summary breaks its contract: nothing is judged | `null` | `{"median_coverage_per_semantic_min":0.5,"seeds_with_all_seven_positive_controls_min":0.9}` |
| K10 | real interaction | **not_assessable** | the summary breaks its contract: nothing is judged | `null` | `{"interacting_seeds_over_S_min":0.5,"tau":2}` |

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

## Contract findings

- k3.D_over_F: not an object

## Diagnostics (no threshold)

```json
{
 "deadline": null,
 "k10": {
  "S": 200,
  "counts": {
   "interacting": 200,
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
   "seeds_with_positive_control": 200
  },
  "clock_mode": {
   "conditional_on_A8": false,
   "median_coverage_over_all_S": 1.0,
   "median_rule": "all S seeds; one not-assessable seed makes the semantic's median not assessable",
   "not_assessable_seeds": 0,
   "seeds_with_positive_control": 200
  },
  "ff_init": {
   "conditional_on_A8": true,
   "median_coverage_over_all_S": 1.0,
   "median_rule": "all S seeds; one not-assessable seed makes the semantic's median not assessable",
   "not_assessable_seeds": 0,
   "seeds_with_positive_control": 200
  },
  "ff_srval": {
   "conditional_on_A8": false,
   "median_coverage_over_all_S": 1.0,
   "median_rule": "all S seeds; one not-assessable seed makes the semantic's median not assessable",
   "not_assessable_seeds": 0,
   "seeds_with_positive_control": 200
  },
  "sr_kind": {
   "conditional_on_A8": false,
   "median_coverage_over_all_S": 1.0,
   "median_rule": "all S seeds; one not-assessable seed makes the semantic's median not assessable",
   "not_assessable_seeds": 0,
   "seeds_with_positive_control": 200
  },
  "sr_mode": {
   "conditional_on_A8": false,
   "median_coverage_over_all_S": 1.0,
   "median_rule": "all S seeds; one not-assessable seed makes the semantic's median not assessable",
   "not_assessable_seeds": 0,
   "seeds_with_positive_control": 200
  },
  "storage_kind": {
   "conditional_on_A8": false,
   "median_coverage_over_all_S": 1.0,
   "median_rule": "all S seeds; one not-assessable seed makes the semantic's median not assessable",
   "not_assessable_seeds": 0,
   "seeds_with_positive_control": 200
  }
 },
 "per_budget": {
  "128": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.05
    },
    "mean": 0.1,
    "median": 0.1,
    "n": 200,
    "negatives": 70,
    "population_variance": 4.0,
    "positives": 60,
    "sign_test_p": 0.832656120631536,
    "ties": 70
   },
   "arm_medians": {
    "A0": 12.0,
    "D": 12.1,
    "F": 17.0,
    "O": 17.0,
    "Omega": 20.0,
    "R": 12.0,
    "X": 12.1
   },
   "base_median": 4.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 3.0
    },
    "mean": 6.0,
    "median": 6.0,
    "n": 200,
    "negatives": 80,
    "population_variance": 4.0,
    "positives": 90,
    "sign_test_p": 0.24506928355195023,
    "ties": 30
   },
   "k1": {
    "eligibility": true,
    "median_base": 4.0,
    "median_best_R": 12.0,
    "omega_best_p95": 25.0
   },
   "power_at_N_or_last": 0.3
  },
  "16": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.05
    },
    "mean": 0.1,
    "median": 0.1,
    "n": 200,
    "negatives": 70,
    "population_variance": 4.0,
    "positives": 60,
    "sign_test_p": 0.832656120631536,
    "ties": 70
   },
   "arm_medians": {
    "A0": 12.0,
    "D": 12.1,
    "F": 17.0,
    "O": 17.0,
    "Omega": 20.0,
    "R": 12.0,
    "X": 12.1
   },
   "base_median": 4.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 6.5
    },
    "mean": 13.0,
    "median": 13.0,
    "n": 200,
    "negatives": 80,
    "population_variance": 4.0,
    "positives": 90,
    "sign_test_p": 0.24506928355195023,
    "ties": 30
   },
   "k1": {
    "eligibility": true,
    "median_base": 4.0,
    "median_best_R": 12.0,
    "omega_best_p95": 25.0
   },
   "power_at_N_or_last": 0.3
  },
  "192": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.05
    },
    "mean": 0.1,
    "median": 0.1,
    "n": 200,
    "negatives": 70,
    "population_variance": 4.0,
    "positives": 60,
    "sign_test_p": 0.832656120631536,
    "ties": 70
   },
   "arm_medians": {
    "A0": 12.0,
    "D": 12.1,
    "F": 17.0,
    "O": 17.0,
    "Omega": 20.0,
    "R": 12.0,
    "X": 12.1
   },
   "base_median": 4.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 3.0
    },
    "mean": 6.0,
    "median": 6.0,
    "n": 200,
    "negatives": 80,
    "population_variance": 4.0,
    "positives": 90,
    "sign_test_p": 0.24506928355195023,
    "ties": 30
   },
   "k1": {
    "eligibility": true,
    "median_base": 4.0,
    "median_best_R": 12.0,
    "omega_best_p95": 25.0
   },
   "power_at_N_or_last": 0.3
  },
  "24": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.05
    },
    "mean": 0.1,
    "median": 0.1,
    "n": 200,
    "negatives": 70,
    "population_variance": 4.0,
    "positives": 60,
    "sign_test_p": 0.832656120631536,
    "ties": 70
   },
   "arm_medians": {
    "A0": 12.0,
    "D": 12.1,
    "F": 17.0,
    "O": 17.0,
    "Omega": 20.0,
    "R": 12.0,
    "X": 12.1
   },
   "base_median": 4.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 3.0
    },
    "mean": 6.0,
    "median": 6.0,
    "n": 200,
    "negatives": 80,
    "population_variance": 4.0,
    "positives": 90,
    "sign_test_p": 0.24506928355195023,
    "ties": 30
   },
   "k1": {
    "eligibility": true,
    "median_base": 4.0,
    "median_best_R": 12.0,
    "omega_best_p95": 25.0
   },
   "power_at_N_or_last": 0.3
  },
  "256": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.05
    },
    "mean": 0.1,
    "median": 0.1,
    "n": 200,
    "negatives": 70,
    "population_variance": 4.0,
    "positives": 60,
    "sign_test_p": 0.832656120631536,
    "ties": 70
   },
   "arm_medians": {
    "A0": 12.0,
    "D": 12.1,
    "F": 17.0,
    "O": 17.0,
    "Omega": 20.0,
    "R": 12.0,
    "X": 12.1
   },
   "base_median": 4.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 3.0
    },
    "mean": 6.0,
    "median": 6.0,
    "n": 200,
    "negatives": 80,
    "population_variance": 4.0,
    "positives": 90,
    "sign_test_p": 0.24506928355195023,
    "ties": 30
   },
   "k1": {
    "eligibility": true,
    "median_base": 4.0,
    "median_best_R": 12.0,
    "omega_best_p95": 25.0
   },
   "power_at_N_or_last": 0.3
  },
  "32": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.05
    },
    "mean": 0.1,
    "median": 0.1,
    "n": 200,
    "negatives": 70,
    "population_variance": 4.0,
    "positives": 60,
    "sign_test_p": 0.832656120631536,
    "ties": 70
   },
   "arm_medians": {
    "A0": 12.0,
    "D": 12.1,
    "F": 17.0,
    "O": 17.0,
    "Omega": 20.0,
    "R": 12.0,
    "X": 12.1
   },
   "base_median": 4.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 3.0
    },
    "mean": 6.0,
    "median": 6.0,
    "n": 200,
    "negatives": 80,
    "population_variance": 4.0,
    "positives": 90,
    "sign_test_p": 0.24506928355195023,
    "ties": 30
   },
   "k1": {
    "eligibility": true,
    "median_base": 4.0,
    "median_best_R": 12.0,
    "omega_best_p95": 25.0
   },
   "power_at_N_or_last": 0.3
  },
  "48": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.05
    },
    "mean": 0.1,
    "median": 0.1,
    "n": 200,
    "negatives": 70,
    "population_variance": 4.0,
    "positives": 60,
    "sign_test_p": 0.832656120631536,
    "ties": 70
   },
   "arm_medians": {
    "A0": 12.0,
    "D": 12.1,
    "F": 17.0,
    "O": 17.0,
    "Omega": 20.0,
    "R": 12.0,
    "X": 12.1
   },
   "base_median": 4.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 3.0
    },
    "mean": 6.0,
    "median": 6.0,
    "n": 200,
    "negatives": 80,
    "population_variance": 4.0,
    "positives": 90,
    "sign_test_p": 0.24506928355195023,
    "ties": 30
   },
   "k1": {
    "eligibility": true,
    "median_base": 4.0,
    "median_best_R": 12.0,
    "omega_best_p95": 25.0
   },
   "power_at_N_or_last": 0.3
  },
  "64": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "N": 16,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.05
    },
    "mean": 0.1,
    "median": 0.1,
    "n": 200,
    "negatives": 70,
    "population_variance": 4.0,
    "positives": 60,
    "sign_test_p": 0.832656120631536,
    "ties": 70
   },
   "arm_medians": {
    "A0": 12.0,
    "D": 12.1,
    "F": 17.0,
    "O": 17.0,
    "Omega": 20.0,
    "R": 12.0,
    "X": 12.1
   },
   "base_median": 4.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 3.0
    },
    "mean": 6.0,
    "median": 6.0,
    "n": 200,
    "negatives": 80,
    "population_variance": 4.0,
    "positives": 90,
    "sign_test_p": 0.24506928355195023,
    "ties": 30
   },
   "k1": {
    "eligibility": true,
    "median_base": 4.0,
    "median_best_R": 12.0,
    "omega_best_p95": 25.0
   },
   "power_at_N_or_last": 0.95
  },
  "8": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.05
    },
    "mean": 0.1,
    "median": 0.1,
    "n": 200,
    "negatives": 70,
    "population_variance": 4.0,
    "positives": 60,
    "sign_test_p": 0.832656120631536,
    "ties": 70
   },
   "arm_medians": {
    "A0": 12.0,
    "D": 12.1,
    "F": 17.0,
    "O": 17.0,
    "Omega": 20.0,
    "R": 12.0,
    "X": 12.1
   },
   "base_median": 4.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 6.5
    },
    "mean": 13.0,
    "median": 13.0,
    "n": 200,
    "negatives": 80,
    "population_variance": 4.0,
    "positives": 90,
    "sign_test_p": 0.24506928355195023,
    "ties": 30
   },
   "k1": {
    "eligibility": true,
    "median_base": 4.0,
    "median_best_R": 12.0,
    "omega_best_p95": 25.0
   },
   "power_at_N_or_last": 0.3
  },
  "96": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 0.05
    },
    "mean": 0.1,
    "median": 0.1,
    "n": 200,
    "negatives": 70,
    "population_variance": 4.0,
    "positives": 60,
    "sign_test_p": 0.832656120631536,
    "ties": 70
   },
   "arm_medians": {
    "A0": 12.0,
    "D": 12.1,
    "F": 17.0,
    "O": 17.0,
    "Omega": 20.0,
    "R": 12.0,
    "X": 12.1
   },
   "base_median": 4.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": 2.5
    },
    "mean": 5.0,
    "median": 5.0,
    "n": 200,
    "negatives": 20,
    "population_variance": 4.0,
    "positives": 150,
    "sign_test_p": 4.0161803977113074e-26,
    "ties": 30
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 3.0
    },
    "mean": 6.0,
    "median": 6.0,
    "n": 200,
    "negatives": 80,
    "population_variance": 4.0,
    "positives": 90,
    "sign_test_p": 0.24506928355195023,
    "ties": 30
   },
   "k1": {
    "eligibility": true,
    "median_base": 4.0,
    "median_best_R": 12.0,
    "omega_best_p95": 25.0
   },
   "power_at_N_or_last": 0.3
  }
 },
 "standing_of_the_batch": null
}
```

Self-validation and the file index are in `gate_report.json`; the verifier `b4_gate_verify.py` recomputes this judgement from the evidence and re-renders this file.

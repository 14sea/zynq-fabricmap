# B4 gate judgement — b4-mech-7 — **PASS** (NOT A GATE RESULT)

Generated 2026-10-20T08:06:58Z at HEAD `da35fb9f5dfa8a29db827eb1d6316598ee2e4c27` (clean tree: True). Evidence: synthetic_summary `evidence/b4/gate/b4-mech-7_pass/synthetic_summary.json` (status complete, label b4-mech-7, S = 200, fixture True, sha256 `7e4e8765ef95e283cbb289beed2ecf62362799f2106cbed1c160ce98c0468cd0`; seeds `None`, manifest `None`; batch HEAD `None`).

Hypothesis `59948f9be3b4516547fbf039556d4aa6a4afd0b2dda2324619e4d40ef0651ed8`, certificate `c69e419f836684872c9edb3754cdb7c76591aaabf69859dab448454c6d78ceef`; thresholds: docs/b4_architecture.md section 9 (v0.1.16), fixed before any exploration or gate run.

**Standing.** NOT A GATE RESULT: the gate's rows applied as written to synthetic_summary evidence under the label 'b4-mech-7' so that the tool's paths are exercised; this judgement can never be represented as a real gate result — the formal result needs the pinned gate label, S = 200 as planned and a production batch archive

**Scope.** every result is under the behaviour hypothesis v0.3 and the certificate mapping of the one site; a FAIL is confined to this model, public task / panel, operator / control design, budget grid and declared decision procedure; nothing here is a statement about silicon, about the carrier, or about the content class in general; a PASS is never read as evidence about the fabric

**Why this is not the formal result:** the evidence is synthetic_summary, not a batch archive; a fixture batch; the label 'b4-mech-7' is not the pinned gate label 'b4-gate-1'.

## Verdict: **PASS** — the budget rule and every row PASS on a complete, valid batch — NOT a gate result (the evidence is synthetic_summary, not a batch archive; a fixture batch; the label 'b4-mech-7' is not the pinned gate label 'b4-gate-1')

## The budget rule — **PASS**: B* = 64, N = 16, N × 3 × B* = 3072, eligible [64]

B* = 64 is the cheapest eligible budget (N x 3 x B = 3072); eligible [64]

| budget | K1 eligibility | N |
|---|---|---|
| 8 | True | None |
| 16 | True | None |
| 24 | True | None |
| 32 | True | None |
| 48 | True | None |
| 64 | True | 16 |
| 96 | True | None |
| 128 | True | None |
| 192 | True | None |
| 256 | True | None |

## The rows

| id | criterion | status | reason | value | threshold |
|---|---|---|---|---|---|
| K1 | non-saturation | **PASS** | at B* the 95th percentile of best_Omega is below 64 and median best_R exceeds median base | `{"B_star":64,"eligibility_by_budget":{"128":true,"16":true,"192":true,"24":true,"256":true,"32":true,"48":true,"64":true,"8":true,"96":true},"median_base":4.0,"median_best_R":12.0,"omega_best_p95":25.0}` | `{"medians":"median_r(best_R(B)) > median_r(base_r), two medians compared","omega_best_p95_lt":64}` |
| K2 | not a definitional lock | **PASS** | variance > 0, both signs at a budget, X - R not rejected in >= 90 % | `{"bootstrap":{"N":16,"alpha":0.05,"experiments":1000,"seed":7},"budgets_with_both_signs":[8,16,24,32,48,64,96,128,192,256],"population_variance_delta1":4.0,"x_minus_r_bootstrap_nonrejection":0.97}` | `{"population_variance_gt":0,"x_minus_r_nonrejection_min":0.9}` |
| K3 | wrong maps do not profit | **PASS** | both ratios readable and <= 0.10, neither control significant | `{"D_over_F":{"denominator":5.0,"note":null,"numerator":0.1,"ratio":0.02,"readable":true},"D_sign_test_p":0.832656120631536,"X_over_O":{"denominator":5.0,"note":null,"numerator":0.1,"ratio":0.02,"readable":true},"X_sign_test_p":0.832656120631536}` | `{"ratio_max":0.1,"sign_test_p_gt":0.05}` |
| K4 | headroom against the certificate-derived grouping | **PASS** | median Omega within the ceiling margin and F reaches half of Omega's benefit | `{"F_over_Omega":{"denominator":8.0,"note":null,"numerator":5.0,"ratio":0.625,"readable":true},"mean_F_minus_R":5.0,"mean_Omega_minus_R":8.0,"median_best_Omega":20.0}` | `{"f_over_omega_min":0.5,"omega_median_max":57.6}` |
| K5 | effect, power, N | **PASS** | d >= 0.5, power >= 0.90 at N, cost within the cap | `{"N":16,"cohen_d_delta1":{"special":null,"value":2.4937421679075005},"cost_N_x_3_x_B_star":3072,"power_at_N":0.95,"scan":[[8,0.3],[9,0.3],[10,0.3],[11,0.3],[12,0.3],[13,0.3],[14,0.3],[15,0.3],[16,0.95]]}` | `{"cap_search_evaluations":4000,"cohen_d_min":0.5,"power_min":0.9}` |
| K6 | no fixed-seed lock | **PASS** | S = 200 planned and N >= 8 | `{"N":16,"S_planned":200}` | `{"N_min":8,"S_gate":200}` |
| K7 | the map is a map | **PASS** | (a) holds by the completion contract; (b) the median of O's not-unknown addresses at B* reaches 11 | `{"a_basis":"complete batch: every executed run audited clean","a_recomputation_mismatches":0,"b_median_O_prefix_not_unknown_at_B_star":15.0,"b_values":[15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15]}` | `{"o_prefix_median_not_unknown_min":11,"recomputation_mismatches":0}` |
| K8 | ledger replay | **PASS** | holds by the completion contract of a complete batch | `{"basis":"complete batch: the replay of every executed run recorded no finding (each arm's audit); re-audited by the archive-wide verifier"}` | `{"replay":"no finding on every executed run; a broken tool contract is invalid under section 9.1"}` |
| K9 | observability | **PASS** | (a) >= 90 % of seeds and (b) every semantic's median coverage >= 0.50 | `{"fraction_of_S_with_all_seven_positive_controls":1.0,"per_semantic":{"ce_mode":{"conditional_on_A8":false,"median_coverage_over_all_S":1.0,"not_assessable_seeds":0,"seeds_with_positive_control":200},"clock_mode":{"conditional_on_A8":false,"median_coverage_over_all_S":1.0,"not_assessable_seeds":0,"seeds_with_positive_control":200},"ff_init":{"conditional_on_A8":true,"median_coverage_over_all_S":1.0,"not_assessable_seeds":0,"seeds_with_positive_control":200},"ff_srval":{"conditional_on_A8":false,"median_coverage_over_all_S":1.0,"not_assessable_seeds":0,"seeds_with_positive_control":200},"sr_kind":{"conditional_on_A8":false,"median_coverage_over_all_S":1.0,"not_assessable_seeds":0,"seeds_with_positive_control":200},"sr_mode":{"conditional_on_A8":false,"median_coverage_over_all_S":1.0,"not_assessable_seeds":0,"seeds_with_positive_control":200},"storage_kind":{"conditional_on_A8":false,"median_coverage_over_all_S":1.0,"not_assessable_seeds":0,"seeds_with_positive_control":200}},"seeds_with_all_seven_positive_controls":200}` | `{"median_coverage_per_semantic_min":0.5,"seeds_with_all_seven_positive_controls_min":0.9}` |
| K10 | real interaction | **PASS** | interacting seeds / S >= 0.50 | `{"counts":{"interacting":200,"no_interaction_seen_among_tested_comparisons":0,"nonzero_below_threshold":0,"not_assessable":0},"fraction_interacting_over_S":1.0,"tau":2}` | `{"interacting_seeds_over_S_min":0.5,"tau":2}` |

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
     "value": 2.4937421679075005
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
     "value": 0.04987484335815001
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
     "value": 2.4937421679075005
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
     "value": 2.9924906014890005
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
     "value": 2.4937421679075005
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
     "value": 0.04987484335815001
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
     "value": 2.4937421679075005
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
     "value": 6.4837296365595005
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
     "value": 2.4937421679075005
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
     "value": 0.04987484335815001
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
     "value": 2.4937421679075005
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
     "value": 2.9924906014890005
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
     "value": 2.4937421679075005
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
     "value": 0.04987484335815001
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
     "value": 2.4937421679075005
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
     "value": 2.9924906014890005
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
     "value": 2.4937421679075005
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
     "value": 0.04987484335815001
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
     "value": 2.4937421679075005
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
     "value": 2.9924906014890005
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
     "value": 2.4937421679075005
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
     "value": 0.04987484335815001
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
     "value": 2.4937421679075005
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
     "value": 2.9924906014890005
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
     "value": 2.4937421679075005
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
     "value": 0.04987484335815001
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
     "value": 2.4937421679075005
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
     "value": 2.9924906014890005
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
     "value": 2.4937421679075005
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
     "value": 0.04987484335815001
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
     "value": 2.4937421679075005
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
     "value": 2.9924906014890005
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
     "value": 2.4937421679075005
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
     "value": 0.04987484335815001
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
     "value": 2.4937421679075005
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
     "value": 6.4837296365595005
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
     "value": 2.4937421679075005
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
     "value": 0.04987484335815001
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
     "value": 2.4937421679075005
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
     "value": 2.9924906014890005
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

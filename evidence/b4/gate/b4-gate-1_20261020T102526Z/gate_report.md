# B4 gate judgement — b4-gate-1 — **FAIL** (FORMAL GATE RESULT)

Generated 2026-10-20T10:48:18Z at HEAD `a243ee8ab904d23706bd6b8fee0d76d6ccb200a5` (clean tree: True). Evidence: batch_archive `evidence/b4/sim/b4-gate-1_20261020T102526Z` (status complete, label b4-gate-1, S = 200, fixture False, sha256 `dab33280753ca5a8fca5f02064eb6afe441913924cae88b000f5061285ce4a07`; seeds `785e76988d4e6ec49cfb86b7b896358b484e5899d48700ee1bcfffd6e034bced`, manifest `5ee9e3e22c50f388c6da5ff15b9d400bd8e02c29354313254bf1f454e425da2e`; batch HEAD `a243ee8ab904d23706bd6b8fee0d76d6ccb200a5`).

Hypothesis `59948f9be3b4516547fbf039556d4aa6a4afd0b2dda2324619e4d40ef0651ed8`, certificate `c69e419f836684872c9edb3754cdb7c76591aaabf69859dab448454c6d78ceef`; thresholds: docs/b4_architecture.md section 9 (v0.1.16), fixed before any exploration or gate run.

**Standing.** the formal discriminability gate of docs/b4_architecture.md section 9 under the behaviour hypothesis v0.3: every row compares a recorded value with its threshold fixed in advance; a PASS is a statement about this model, public task and panel, operator and control design, budget grid and declared decision procedure — never evidence about the fabric or the silicon; a FAIL is a result of this protocol version, not a proof that FF bits or the content class are indistinguishable in general; no threshold is adjusted in response

**Scope.** every result is under the behaviour hypothesis v0.3 and the certificate mapping of the one site; a FAIL is confined to this model, public task / panel, operator / control design, budget grid and declared decision procedure; nothing here is a statement about silicon, about the carrier, or about the content class in general; a PASS is never read as evidence about the fabric

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
  "checks": 329747,
  "clock": "time.monotonic",
  "elapsed_s": 1372.077,
  "expired": false,
  "first_expired_at_s": null,
  "seconds": 3600
 },
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
   "median_coverage_over_all_S": 0.40625,
   "median_rule": "all S seeds; one not-assessable seed makes the semantic's median not assessable",
   "not_assessable_seeds": 0,
   "seeds_with_positive_control": 200
  },
  "sr_kind": {
   "conditional_on_A8": false,
   "median_coverage_over_all_S": 0.5,
   "median_rule": "all S seeds; one not-assessable seed makes the semantic's median not assessable",
   "not_assessable_seeds": 0,
   "seeds_with_positive_control": 200
  },
  "sr_mode": {
   "conditional_on_A8": false,
   "median_coverage_over_all_S": 0.96875,
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
     "value": -0.2672055982226393
    },
    "mean": -0.535,
    "median": 0.0,
    "n": 200,
    "negatives": 83,
    "population_variance": 3.988775,
    "positives": 39,
    "sign_test_p": 0.9999810405968355,
    "ties": 78
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.2359260876131731
    },
    "mean": -0.55,
    "median": 0.0,
    "n": 200,
    "negatives": 78,
    "population_variance": 5.4075,
    "positives": 42,
    "sign_test_p": 0.9996666380514982,
    "ties": 80
   },
   "arm_medians": {
    "A0": 40.0,
    "D": 40.0,
    "F": 40.0,
    "O": 40.0,
    "Omega": 40.0,
    "R": 40.0,
    "X": 40.0
   },
   "base_median": 32.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.3859716595765849
    },
    "mean": -0.9,
    "median": 0.0,
    "n": 200,
    "negatives": 95,
    "population_variance": 5.41,
    "positives": 38,
    "sign_test_p": 0.9999998403021217,
    "ties": 67
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.004163507748697359
    },
    "mean": 0.01,
    "median": 0.0,
    "n": 200,
    "negatives": 55,
    "population_variance": 5.7399,
    "positives": 64,
    "sign_test_p": 0.23174408831138207,
    "ties": 81
   },
   "k1": {
    "eligibility": true,
    "median_base": 32.0,
    "median_best_R": 40.0,
    "omega_best_p95": 45.05000000000001
   },
   "power_at_N_or_last": 0.0
  },
  "16": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.25948041831609625
    },
    "mean": -0.74,
    "median": 0.0,
    "n": 200,
    "negatives": 83,
    "population_variance": 8.0924,
    "positives": 41,
    "sign_test_p": 0.9999517609476105,
    "ties": 76
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.2142386004172568
    },
    "mean": -0.455,
    "median": 0.0,
    "n": 200,
    "negatives": 63,
    "population_variance": 4.487975,
    "positives": 38,
    "sign_test_p": 0.9953324759396776,
    "ties": 99
   },
   "arm_medians": {
    "A0": 35.0,
    "D": 35.0,
    "F": 34.0,
    "O": 34.5,
    "Omega": 34.0,
    "R": 35.0,
    "X": 35.0
   },
   "base_median": 32.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.2989441408246561
    },
    "mean": -0.64,
    "median": 0.0,
    "n": 200,
    "negatives": 66,
    "population_variance": 4.5604,
    "positives": 31,
    "sign_test_p": 0.9998905451184948,
    "ties": 103
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.8863963215085535
    },
    "mean": 3.1,
    "median": 2.0,
    "n": 200,
    "negatives": 0,
    "population_variance": 12.17,
    "positives": 127,
    "sign_test_p": 5.877471754111438e-39,
    "ties": 73
   },
   "k1": {
    "eligibility": true,
    "median_base": 32.0,
    "median_best_R": 35.0,
    "omega_best_p95": 40.0
   },
   "power_at_N_or_last": 0.0
  },
  "192": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.2835743552605607
    },
    "mean": -0.605,
    "median": 0.0,
    "n": 200,
    "negatives": 81,
    "population_variance": 4.528975,
    "positives": 36,
    "sign_test_p": 0.9999917479332603,
    "ties": 83
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.2690672382542508
    },
    "mean": -0.635,
    "median": 0.0,
    "n": 200,
    "negatives": 77,
    "population_variance": 5.541775,
    "positives": 35,
    "sign_test_p": 0.9999804472917491,
    "ties": 88
   },
   "arm_medians": {
    "A0": 41.0,
    "D": 41.0,
    "F": 40.0,
    "O": 40.0,
    "Omega": 41.0,
    "R": 41.0,
    "X": 41.0
   },
   "base_median": 32.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.3307674911334117
    },
    "mean": -0.815,
    "median": 0.0,
    "n": 200,
    "negatives": 82,
    "population_variance": 6.040775,
    "positives": 32,
    "sign_test_p": 0.9999994098310279,
    "ties": 86
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": -0.02655666483875443
    },
    "mean": -0.065,
    "median": 0.0,
    "n": 200,
    "negatives": 53,
    "population_variance": 5.960775,
    "positives": 57,
    "sign_test_p": 0.3875014914153122,
    "ties": 90
   },
   "k1": {
    "eligibility": true,
    "median_base": 32.0,
    "median_best_R": 41.0,
    "omega_best_p95": 46.0
   },
   "power_at_N_or_last": 0.0
  },
  "24": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.28558192232759844
    },
    "mean": -0.765,
    "median": 0.0,
    "n": 200,
    "negatives": 88,
    "population_variance": 7.139775,
    "positives": 45,
    "sign_test_p": 0.9999407102665724,
    "ties": 67
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.2881871948130147
    },
    "mean": -0.69,
    "median": 0.0,
    "n": 200,
    "negatives": 84,
    "population_variance": 5.7039,
    "positives": 38,
    "sign_test_p": 0.9999917551764251,
    "ties": 78
   },
   "arm_medians": {
    "A0": 36.0,
    "D": 36.0,
    "F": 35.0,
    "O": 35.0,
    "Omega": 35.0,
    "R": 36.0,
    "X": 35.0
   },
   "base_median": 32.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.33382068116775204
    },
    "mean": -0.83,
    "median": 0.0,
    "n": 200,
    "negatives": 89,
    "population_variance": 6.1511,
    "positives": 37,
    "sign_test_p": 0.9999991776150617,
    "ties": 74
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.7837274653525855
    },
    "mean": 2.87,
    "median": 2.0,
    "n": 200,
    "negatives": 9,
    "population_variance": 13.3431,
    "positives": 121,
    "sign_test_p": 1.7450735227525562e-26,
    "ties": 70
   },
   "k1": {
    "eligibility": true,
    "median_base": 32.0,
    "median_best_R": 36.0,
    "omega_best_p95": 41.0
   },
   "power_at_N_or_last": 0.0
  },
  "256": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.24940404208040454
    },
    "mean": -0.56,
    "median": 0.0,
    "n": 200,
    "negatives": 77,
    "population_variance": 5.0164,
    "positives": 37,
    "sign_test_p": 0.9999478816471918,
    "ties": 86
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.22118177162704888
    },
    "mean": -0.52,
    "median": 0.0,
    "n": 200,
    "negatives": 67,
    "population_variance": 5.4996,
    "positives": 35,
    "sign_test_p": 0.9995067315959077,
    "ties": 98
   },
   "arm_medians": {
    "A0": 41.0,
    "D": 41.0,
    "F": 41.0,
    "O": 41.0,
    "Omega": 41.0,
    "R": 41.0,
    "X": 41.0
   },
   "base_median": 32.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.2307997151174868
    },
    "mean": -0.58,
    "median": 0.0,
    "n": 200,
    "negatives": 71,
    "population_variance": 6.2836,
    "positives": 31,
    "sign_test_p": 0.999980574927867,
    "ties": 98
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.04793664024585
    },
    "mean": 0.1,
    "median": 0.0,
    "n": 200,
    "negatives": 50,
    "population_variance": 4.33,
    "positives": 58,
    "sign_test_p": 0.25038319670821807,
    "ties": 92
   },
   "k1": {
    "eligibility": true,
    "median_base": 32.0,
    "median_best_R": 41.0,
    "omega_best_p95": 46.0
   },
   "power_at_N_or_last": 0.0
  },
  "32": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.301618982746711
    },
    "mean": -0.79,
    "median": 0.0,
    "n": 200,
    "negatives": 91,
    "population_variance": 6.8259,
    "positives": 51,
    "sign_test_p": 0.9997331146232715,
    "ties": 58
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.30051388016905944
    },
    "mean": -0.75,
    "median": 0.0,
    "n": 200,
    "negatives": 91,
    "population_variance": 6.1975,
    "positives": 44,
    "sign_test_p": 0.999985045198205,
    "ties": 65
   },
   "arm_medians": {
    "A0": 36.0,
    "D": 36.0,
    "F": 36.0,
    "O": 36.0,
    "Omega": 36.0,
    "R": 37.0,
    "X": 36.0
   },
   "base_median": 32.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.31386537963442107
    },
    "mean": -0.85,
    "median": 0.0,
    "n": 200,
    "negatives": 93,
    "population_variance": 7.2975,
    "positives": 41,
    "sign_test_p": 0.9999982481349159,
    "ties": 66
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.6139244757800547
    },
    "mean": 1.98,
    "median": 1.0,
    "n": 200,
    "negatives": 18,
    "population_variance": 10.3496,
    "positives": 110,
    "sign_test_p": 1.327071906532612e-17,
    "ties": 72
   },
   "k1": {
    "eligibility": true,
    "median_base": 32.0,
    "median_best_R": 37.0,
    "omega_best_p95": 41.0
   },
   "power_at_N_or_last": 0.0
  },
  "48": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.35551867810540055
    },
    "mean": -0.845,
    "median": 0.0,
    "n": 200,
    "negatives": 88,
    "population_variance": 5.620975,
    "positives": 46,
    "sign_test_p": 0.9999099311982291,
    "ties": 66
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.2966120207162622
    },
    "mean": -0.76,
    "median": 0.0,
    "n": 200,
    "negatives": 99,
    "population_variance": 6.5324,
    "positives": 46,
    "sign_test_p": 0.9999971384129177,
    "ties": 55
   },
   "arm_medians": {
    "A0": 37.0,
    "D": 37.0,
    "F": 37.0,
    "O": 37.0,
    "Omega": 38.0,
    "R": 38.0,
    "X": 37.0
   },
   "base_median": 32.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.36342909113690697
    },
    "mean": -0.94,
    "median": -1.0,
    "n": 200,
    "negatives": 103,
    "population_variance": 6.6564,
    "positives": 39,
    "sign_test_p": 0.9999999860831114,
    "ties": 58
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.4402292779329278
    },
    "mean": 1.225,
    "median": 0.5,
    "n": 200,
    "negatives": 30,
    "population_variance": 7.704375,
    "positives": 100,
    "sign_test_p": 2.7105840132689216e-10,
    "ties": 70
   },
   "k1": {
    "eligibility": true,
    "median_base": 32.0,
    "median_best_R": 38.0,
    "omega_best_p95": 42.0
   },
   "power_at_N_or_last": 0.0
  },
  "64": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.3018239004800257
    },
    "mean": -0.715,
    "median": 0.0,
    "n": 200,
    "negatives": 93,
    "population_variance": 5.583775,
    "positives": 52,
    "sign_test_p": 0.9997767844114052,
    "ties": 55
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.2790514386313777
    },
    "mean": -0.695,
    "median": 0.0,
    "n": 200,
    "negatives": 99,
    "population_variance": 6.171975,
    "positives": 40,
    "sign_test_p": 0.9999998834313549,
    "ties": 61
   },
   "arm_medians": {
    "A0": 38.0,
    "D": 38.0,
    "F": 38.0,
    "O": 38.0,
    "Omega": 38.0,
    "R": 39.0,
    "X": 38.0
   },
   "base_median": 32.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.3714904265069308
    },
    "mean": -0.9,
    "median": -1.0,
    "n": 200,
    "negatives": 108,
    "population_variance": 5.84,
    "positives": 37,
    "sign_test_p": 0.9999999995046622,
    "ties": 55
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.3658051362916929
    },
    "mean": 0.92,
    "median": 0.0,
    "n": 200,
    "negatives": 46,
    "population_variance": 6.2936,
    "positives": 93,
    "sign_test_p": 4.1368554089427357e-05,
    "ties": 61
   },
   "k1": {
    "eligibility": true,
    "median_base": 32.0,
    "median_best_R": 39.0,
    "omega_best_p95": 43.0
   },
   "power_at_N_or_last": 0.0
  },
  "8": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.30956882794366325
    },
    "mean": -0.945,
    "median": 0.0,
    "n": 200,
    "negatives": 73,
    "population_variance": 9.271975,
    "positives": 36,
    "sign_test_p": 0.9998812659926862,
    "ties": 91
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.1813630667569091
    },
    "mean": -0.36,
    "median": 0.0,
    "n": 200,
    "negatives": 36,
    "population_variance": 3.9204,
    "positives": 17,
    "sign_test_p": 0.9972568275616199,
    "ties": 147
   },
   "arm_medians": {
    "A0": 34.0,
    "D": 34.0,
    "F": 33.0,
    "O": 34.0,
    "Omega": 33.0,
    "R": 34.0,
    "X": 34.0
   },
   "base_median": 32.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.24624775769768323
    },
    "mean": -0.485,
    "median": 0.0,
    "n": 200,
    "negatives": 38,
    "population_variance": 3.859775,
    "positives": 13,
    "sign_test_p": 0.9999009802743313,
    "ties": 149
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.7097230632788607
    },
    "mean": 2.285,
    "median": 0.0,
    "n": 200,
    "negatives": 0,
    "population_variance": 10.313775,
    "positives": 96,
    "sign_test_p": 1.262177448353619e-29,
    "ties": 104
   },
   "k1": {
    "eligibility": true,
    "median_base": 32.0,
    "median_best_R": 34.0,
    "omega_best_p95": 39.0
   },
   "power_at_N_or_last": 0.0
  },
  "96": {
   "F_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.3079851376889306
    },
    "mean": -0.675,
    "median": 0.0,
    "n": 200,
    "negatives": 90,
    "population_variance": 4.779375,
    "positives": 40,
    "sign_test_p": 0.9999970618050718,
    "ties": 70
   },
   "N": null,
   "X_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.2308257213269753
    },
    "mean": -0.56,
    "median": 0.0,
    "n": 200,
    "negatives": 86,
    "population_variance": 5.8564,
    "positives": 48,
    "sign_test_p": 0.9996523949603341,
    "ties": 66
   },
   "arm_medians": {
    "A0": 39.0,
    "D": 39.0,
    "F": 39.0,
    "O": 39.0,
    "Omega": 39.0,
    "R": 40.0,
    "X": 39.0
   },
   "base_median": 32.0,
   "delta1_O_minus_R": {
    "cohen_d": {
     "special": null,
     "value": -0.3835877507339144
    },
    "mean": -0.92,
    "median": 0.0,
    "n": 200,
    "negatives": 96,
    "population_variance": 5.7236,
    "positives": 35,
    "sign_test_p": 0.9999999833925,
    "ties": 69
   },
   "delta2_O_minus_endtoend_F": {
    "cohen_d": {
     "special": null,
     "value": 0.18361813705168012
    },
    "mean": 0.47,
    "median": 0.0,
    "n": 200,
    "negatives": 48,
    "population_variance": 6.5191,
    "positives": 78,
    "sign_test_p": 0.004751582516451103,
    "ties": 74
   },
   "k1": {
    "eligibility": true,
    "median_base": 32.0,
    "median_best_R": 40.0,
    "omega_best_p95": 45.0
   },
   "power_at_N_or_last": 0.0
  }
 },
 "standing_of_the_batch": "the batch of the formal gate under the label given, S as planned; values beside the thresholds of docs/b4_architecture.md section 9 and not a gate verdict here: the verdict is b4_gate.py's, written in a gate directory under evidence/b4/gate/ and bound to this archive by digest (unit 2b-4); candidate B* / N are the budget rule's on this batch"
}
```

Self-validation and the file index are in `gate_report.json`; the verifier `b4_gate_verify.py` recomputes this judgement from the evidence and re-renders this file.

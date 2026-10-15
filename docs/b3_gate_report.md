# B3 gate report — 2026-09-17T10:17:02Z (`f159dee`, dirty at start: False)

Rules: architecture v0.2.3 §9 — `docs/b3_architecture.md` sha256 `0713dee9e6954bb9db20a3a8be0b52512de762ebe2c4674f18902646bd8dbac8` (last commit `1aa06f1`). Engine `b2-es-v1` (μ 4, λ 8, k ≤ 4); cartographer `specimen-carto-v1.1`; map `c6a4b23e…`. Seeds: label `b3-gate`, master 3097524112, 200 pairs, 1245 excluded values from 5 archived sources plus the fixed list. Control X: seed_x 2041341936 (2 attempt(s)), permutation sha256 `9cc0b64ef1faa37ad89858a92f6beb03056c1308c9c3e270658c1196d1f217dd`. Wall 532.9 s.

The gate fitness is **F1**; other fitnesses are reported for information. H9 is a condition on the claim, not on passing.

## F1 — ceiling 40, 200 seeds — **PASS**, B* = 1000, H9 holds

| budget | R | F | O | X | F end-to-end | Δ1 mean (pos/neg/ties, p) | Δ2 mean (p) | ΔX mean (p) | O decoded | N(B) | cost | H1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 6 | 6 | 5 | 5 | 2 | -1.00 (31/128/41, p 1) | +2.59 (p 3.19e-58) | -1.09 (p 1) | 40 | — | — | yes |
| 200 | 8 | 9 | 7 | 7 | 2 | -1.38 (33/140/27, p 1) | +4.68 (p 2.49e-60) | -1.71 (p 1) | 105 | — | — | yes |
| 300 | 10 | 11 | 9 | 8 | 2 | -0.96 (47/119/34, p 1) | +6.58 (p 6.22e-61) | -1.86 (p 1) | 168 | — | — | yes |
| 400 | 11 | 13 | 11 | 9 | 5 | -0.23 (74/87/39, p 0.865) | +5.89 (p 1.24e-60) | -1.72 (p 1) | 214 | — | — | yes |
| 600 | 12 | 16 | 14 | 11 | 10 | +1.67 (138/35/27, p 5.74e-16) | +3.39 (p 2.36e-36) | -1.41 (p 1) | 263 | 28 | 50400 | yes |
| 800 | 13 | 19 | 16 | 12 | 14 | +3.51 (172/16/12, p 1.69e-34) | +2.21 (p 1.21e-20) | -1.28 (p 1) | 281 | 12 | 28800 | yes |
| 1000 | 13 | 21 | 19 | 13 | 17 | +5.30 (182/7/11, p 2.02e-45) | +1.58 (p 3.79e-09) | -0.98 (p 1) | 288 | 9 | 27000 | yes |
| 1500 | 14 | 24 | 23 | 13.5 | 22 | +8.94 (198/1/1, p 2.49e-58) | +1.03 (p 0.000142) | -0.86 (p 0.999) | 292 | 8 | 36000 | yes |
| 2000 | 15 | 27 | 26 | 14 | 25 | +11.26 (200/0/0, p 6.22e-61) | +0.91 (p 0.00242) | -0.91 (p 1) | 292 | 8 | 48000 | yes |
| 3000 | 15 | 30 | 30 | 14 | 29 | +14.26 (200/0/0, p 6.22e-61) | +0.60 (p 0.00477) | -1.23 (p 1) | 292 | 8 | 72000 | yes |

| criterion | result | numbers |
|---|---|---|
| H1 | **PASS** | O_p95 = 23; base_median = 2; ceiling = 40; random_median = 13 |
| H2 | **PASS** | N_used = 9; budgets_with_both_signs = [100, 200, 300, 400, 600, 800, 1000, 1500]; control_X_nonreject_rate = 0.998; mean_delta1_changes_sign_across_budgets (reported) = yes; var_delta1 = 10.36 |
| H3 | **PASS** | decoded_median_O_at_b_star = 288; decoded_median_X_at_b_star = 288; fraction = -0.185849; mean_delta1 = 5.3; mean_deltaX = -0.985; sign_test_p_X_vs_R = 1 |
| H4 | **PASS** | F_median = 21; O_median = 19; O_over_F = 0.904762; delta2 = {cohen_d: 0.520607, mean: 1.585, median: 1.5, negatives: 49, positives: 125, sign_test_p: 3.79e-09, ties: 26} |
| H5 | **PASS** | cohen_d = 1.64251; mean_delta1 = 5.3; negatives = 7; positives = 182; power_at_N = 0.942; required_pairs_N = 9; sd_delta1 = 3.22677; search_evaluations = 27000; sign_test_p_full_S = 2.02e-45; ties = 11 |
| H6 | **PASS** | N = 9; pairs_min = 8; seeds = 200; var_delta1 = 10.36 |
| H7 | **PASS** | anomalies_total = 0; decoded_median_at_b_star = 288; evals_to_full_map_median = 1421.5; full_map_within_b_max = 200; online_map_verified_all = yes; wrong_decodes_total = 0 |
| H8 | **PASS** | seeds_with_X_shadow_findings (a defect, not a result) = []; seeds_with_ledger_schema_findings = []; seeds_with_replay_findings = [] |
| H9 | **PASS** | alpha = 0.05 |
| budget_rule | **PASS** | b_star = 1000; search_evaluations = 27000 |

H9 detail — Δ2 = O − end-to-end F at every budget ≥ B* (one-sided sign test, α = 0.05):

| budget | p | mean Δ2 | median Δ2 | p ≤ α |
|---|---|---|---|---|
| 1000 | 3.79e-09 | +1.585 | 1.5 | yes |
| 1500 | 0.000142 | +1.035 | 1 | yes |
| 2000 | 0.00242 | +0.910 | 1 | yes |
| 3000 | 0.00477 | +0.605 | 1 | yes |

Budget rule candidates (N(B), search cost N × 3 × B, H1): 100: N —, cost —, H1 yes; 200: N —, cost —, H1 yes; 300: N —, cost —, H1 yes; 400: N —, cost —, H1 yes; 600: N 28, cost 50400, H1 yes; 800: N 12, cost 28800, H1 yes; 1000: N 9, cost 27000, H1 yes; 1500: N 8, cost 36000, H1 yes; 2000: N 8, cost 48000, H1 yes; 3000: N 8, cost 72000, H1 yes

Champion holdout medians at B_max: {'F': 1.0, 'O': 1.0, 'R': 1.0, 'X': 1.0}. At B* = 1000: medians {'F': 21.0, 'O': 19.0, 'R': 13.0, 'X': 13.0}, F end-to-end 17.0.

## F2 — ceiling 160, 200 seeds — **FAIL**, B* = 2000, H9 holds

| budget | R | F | O | X | F end-to-end | Δ1 mean (pos/neg/ties, p) | Δ2 mean (p) | ΔX mean (p) | O decoded | N(B) | cost | H1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 34 | 34 | 30 | 29 | 18 | -3.87 (28/163/9, p 1) | +11.95 (p 6.22e-61) | -4.28 (p 1) | 40 | — | — | yes |
| 200 | 47 | 48 | 41 | 39 | 18 | -6.32 (28/160/12, p 1) | +22.82 (p 6.22e-61) | -7.76 (p 1) | 105 | — | — | yes |
| 300 | 58 | 59 | 51 | 48 | 18 | -7.15 (25/166/9, p 1) | +32.94 (p 6.22e-61) | -9.66 (p 1) | 168 | — | — | yes |
| 400 | 67 | 70 | 60.5 | 57 | 28 | -6.78 (29/159/12, p 1) | +31.54 (p 6.22e-61) | -9.91 (p 1) | 214 | — | — | yes |
| 600 | 82 | 86 | 78 | 72 | 56 | -3.54 (59/133/8, p 1) | +22.18 (p 6.22e-61) | -9.68 (p 1) | 263 | — | — | yes |
| 800 | 94 | 100 | 93 | 84 | 75 | +0.06 (101/96/3, p 0.388) | +17.40 (p 1.58e-52) | -9.13 (p 1) | 281 | — | — | yes |
| 1000 | 102 | 111 | 106 | 93 | 91 | +4.13 (137/56/7, p 2.55e-09) | +13.80 (p 3.94e-47) | -8.73 (p 1) | 288 | 51 | 153000 | yes |
| 1500 | 114 | 130 | 127 | 107 | 118 | +12.01 (178/16/6, p 4.45e-36) | +8.11 (p 9.62e-20) | -7.01 (p 1) | 292 | 11 | 49500 | yes |
| 2000 | 121 | 142 | 140 | 116 | 135 | +18.05 (197/2/1, p 2.48e-56) | +4.88 (p 2.08e-12) | -6.14 (p 1) | 292 | 8 | 48000 | yes |
| 3000 | 128 | 153 | 153 | 124 | 150 | +24.05 (200/0/0, p 6.22e-61) | +2.47 (p 2.77e-09) | -4.64 (p 1) | 292 | 8 | 72000 | no |

| criterion | result | numbers |
|---|---|---|
| H1 | **PASS** | O_p95 = 147; base_median = 18; ceiling = 160; random_median = 121 |
| H2 | **PASS** | N_used = 8; budgets_with_both_signs = [100, 200, 300, 400, 600, 800, 1000, 1500, 2000]; control_X_nonreject_rate = 1; mean_delta1_changes_sign_across_budgets (reported) = yes; var_delta1 = 103.058 |
| H3 | **PASS** | decoded_median_O_at_b_star = 292; decoded_median_X_at_b_star = 292; fraction = -0.340166; mean_delta1 = 18.05; mean_deltaX = -6.14; sign_test_p_X_vs_R = 1 |
| H4 | **PASS** | F_median = 142; O_median = 140; O_over_F = 0.985915; delta2 = {cohen_d: 0.668039, mean: 4.88, median: 5, negatives: 47, positives: 141, sign_test_p: 2.08e-12, ties: 12} |
| H5 | **FAIL** | cohen_d = 1.77357; mean_delta1 = 18.05; negatives = 2; positives = 197; power_at_N = 0.996; required_pairs_N = 8; sd_delta1 = 10.1772; search_evaluations = 48000; sign_test_p_full_S = 2.48e-56; ties = 1 |
| H6 | **PASS** | N = 8; pairs_min = 8; seeds = 200; var_delta1 = 103.058 |
| H7 | **PASS** | anomalies_total = 0; decoded_median_at_b_star = 292; evals_to_full_map_median = 1421.5; full_map_within_b_max = 200; online_map_verified_all = yes; wrong_decodes_total = 0 |
| H8 | **PASS** | seeds_with_X_shadow_findings (a defect, not a result) = []; seeds_with_ledger_schema_findings = []; seeds_with_replay_findings = [] |
| H9 | **PASS** | alpha = 0.05 |
| budget_rule | **PASS** | b_star = 2000; search_evaluations = 48000 |

H9 detail — Δ2 = O − end-to-end F at every budget ≥ B* (one-sided sign test, α = 0.05):

| budget | p | mean Δ2 | median Δ2 | p ≤ α |
|---|---|---|---|---|
| 2000 | 2.08e-12 | +4.880 | 5 | yes |
| 3000 | 2.77e-09 | +2.470 | 3 | yes |

Budget rule candidates (N(B), search cost N × 3 × B, H1): 100: N —, cost —, H1 yes; 200: N —, cost —, H1 yes; 300: N —, cost —, H1 yes; 400: N —, cost —, H1 yes; 600: N —, cost —, H1 yes; 800: N —, cost —, H1 yes; 1000: N 51, cost 153000, H1 yes; 1500: N 11, cost 49500, H1 yes; 2000: N 8, cost 48000, H1 yes; 3000: N 8, cost 72000, H1 no

Champion holdout medians at B_max: {'F': 10.0, 'O': 10.0, 'R': 10.0, 'X': 10.0}. At B* = 2000: medians {'F': 142.0, 'O': 140.0, 'R': 121.0, 'X': 116.0}, F end-to-end 135.0.

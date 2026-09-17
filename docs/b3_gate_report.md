# B3 gate report — 2026-09-17T10:17:02Z (`f159dee`, dirty at start: False)

Rules: architecture v0.2.3 §9 — `docs/b3_architecture.md` sha256 `0713dee9e6954bb9db20a3a8be0b52512de762ebe2c4674f18902646bd8dbac8` (last commit `1aa06f1`). Engine `b2-es-v1` (μ 4, λ 8, k ≤ 4); cartographer `specimen-carto-v1.1`; map `c6a4b23e…`. Seeds: label `b3-gate`, master 3097524112, 200 pairs, 1245 excluded values from 5 archived sources plus the fixed list. Control X: seed_x 2041341936 (2 attempt(s)), permutation sha256 `9cc0b64ef1faa37ad89858a92f6beb03056c1308c9c3e270658c1196d1f217dd`. Wall 532.9 s.

The gate fitness is **F1**; other fitnesses are reported for information. H9 is a condition on the claim, not on passing.

## F1 — ceiling 40, 200 seeds — **PASS**, B* = 1000, H9 holds

| budget | R | F | O | X | F end-to-end | Δ1 mean (pos/neg/ties, p) | Δ2 mean (p) | ΔX mean (p) | O decoded | N(B) | cost | H1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 6 | 6 | 5 | 5 | 2 | -1.00 (31/128/41, 1.00) | +2.59 (3.2e-58) | -1.09 (1.00) | 40 | — | — | yes |
| 200 | 8 | 9 | 7 | 7 | 2 | -1.38 (33/140/27, 1.00) | +4.68 (2.5e-60) | -1.71 (1.00) | 105 | — | — | yes |
| 300 | 10 | 11 | 9 | 8 | 2 | -0.96 (47/119/34, 1.00) | +6.58 (6.2e-61) | -1.86 (1.00) | 167.500 | — | — | yes |
| 400 | 11 | 13 | 11 | 9 | 5 | -0.23 (74/87/39, 0.87) | +5.89 (1.2e-60) | -1.72 (1.00) | 213.500 | — | — | yes |
| 600 | 12 | 16 | 14 | 11 | 10 | +1.67 (138/35/27, 5.7e-16) | +3.39 (2.4e-36) | -1.41 (1.00) | 263 | 28 | 50400 | yes |
| 800 | 13 | 19 | 16 | 12 | 14 | +3.51 (172/16/12, 1.7e-34) | +2.21 (1.2e-20) | -1.28 (1.00) | 281 | 12 | 28800 | yes |
| 1000 | 13 | 21 | 19 | 13 | 17 | +5.30 (182/7/11, 2e-45) | +1.58 (3.8e-09) | -0.98 (1.00) | 288 | 9 | 27000 | yes |
| 1500 | 14 | 24 | 23 | 13.500 | 22 | +8.94 (198/1/1, 2.5e-58) | +1.03 (0.00014) | -0.86 (1.00) | 292 | 8 | 36000 | yes |
| 2000 | 15 | 27 | 26 | 14 | 25 | +11.26 (200/0/0, 6.2e-61) | +0.91 (0.00) | -0.91 (1.00) | 292 | 8 | 48000 | yes |
| 3000 | 15 | 30 | 30 | 14 | 29 | +14.26 (200/0/0, 6.2e-61) | +0.60 (0.00) | -1.23 (1.00) | 292 | 8 | 72000 | yes |

| criterion | result | numbers |
|---|---|---|
| H1 | **PASS** | O_p95 = 23; base_median = 2; ceiling = 40; random_median = 13 |
| H2 | **PASS** | N_used = 9; budgets_with_both_signs = [100, 200, 300, 400, 600, 800, 1000, 1500]; control_X_nonreject_rate = 0.998; mean_delta1_changes_sign_across_budgets (reported) = yes; var_delta1 = 10.360 |
| H3 | **PASS** | decoded_median_O_at_b_star = 288; decoded_median_X_at_b_star = 288; fraction = -0.186; mean_delta1 = 5.300; mean_deltaX = -0.985; sign_test_p_X_vs_R = 1.000 |
| H4 | **PASS** | F_median = 21; O_median = 19; O_over_F = 0.905; delta2 = {"cohen_d": 0.5206069961965352, "mean": 1.585, "median": 1.5, "negatives": 49, "positives": 125, "sign_test_p": 3.793677 |
| H5 | **PASS** | cohen_d = 1.643; mean_delta1 = 5.300; negatives = 7; positives = 182; power_at_N = 0.942; required_pairs_N = 9; sd_delta1 = 3.227; search_evaluations = 27000; sign_test_p_full_S = 2.02e-45; ties = 11 |
| H6 | **PASS** | N = 9; pairs_min = 8; seeds = 200; var_delta1 = 10.360 |
| H7 | **PASS** | anomalies_total = 0; decoded_median_at_b_star = 288; evals_to_full_map_median = 1421.500; full_map_within_b_max = 200; online_map_verified_all = yes; wrong_decodes_total = 0 |
| H8 | **PASS** | seeds_with_X_shadow_findings (a defect, not a result) = []; seeds_with_ledger_schema_findings = []; seeds_with_replay_findings = [] |
| H9 | **PASS** | alpha = 0.050 |
| budget_rule | **PASS** | b_star = 1000; search_evaluations = 27000 |

Champion holdout medians at B_max: {'F': 1.0, 'O': 1.0, 'R': 1.0, 'X': 1.0}. At B* = 1000: medians {'F': 21.0, 'O': 19.0, 'R': 13.0, 'X': 13.0}, F end-to-end 17.0.

## F2 — ceiling 160, 200 seeds — **FAIL**, B* = 2000, H9 holds

| budget | R | F | O | X | F end-to-end | Δ1 mean (pos/neg/ties, p) | Δ2 mean (p) | ΔX mean (p) | O decoded | N(B) | cost | H1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 34 | 34 | 30 | 29 | 18 | -3.87 (28/163/9, 1.00) | +11.95 (6.2e-61) | -4.28 (1.00) | 40 | — | — | yes |
| 200 | 47 | 48 | 41 | 39 | 18 | -6.32 (28/160/12, 1.00) | +22.82 (6.2e-61) | -7.76 (1.00) | 105 | — | — | yes |
| 300 | 58 | 59 | 51 | 48 | 18 | -7.15 (25/166/9, 1.00) | +32.94 (6.2e-61) | -9.66 (1.00) | 167.500 | — | — | yes |
| 400 | 67 | 70 | 60.500 | 57 | 28 | -6.78 (29/159/12, 1.00) | +31.54 (6.2e-61) | -9.91 (1.00) | 213.500 | — | — | yes |
| 600 | 82 | 86 | 78 | 72 | 56 | -3.54 (59/133/8, 1.00) | +22.18 (6.2e-61) | -9.68 (1.00) | 263 | — | — | yes |
| 800 | 94 | 100 | 93 | 84 | 75 | +0.06 (101/96/3, 0.39) | +17.40 (1.6e-52) | -9.13 (1.00) | 281 | — | — | yes |
| 1000 | 102 | 111 | 105.500 | 93 | 91 | +4.13 (137/56/7, 2.5e-09) | +13.80 (3.9e-47) | -8.73 (1.00) | 288 | 51 | 153000 | yes |
| 1500 | 114.500 | 130 | 127 | 107 | 118 | +12.01 (178/16/6, 4.5e-36) | +8.11 (9.6e-20) | -7.01 (1.00) | 292 | 11 | 49500 | yes |
| 2000 | 121 | 142 | 140 | 116 | 135 | +18.05 (197/2/1, 2.5e-56) | +4.88 (2.1e-12) | -6.14 (1.00) | 292 | 8 | 48000 | yes |
| 3000 | 128 | 153 | 153 | 124 | 150 | +24.05 (200/0/0, 6.2e-61) | +2.47 (2.8e-09) | -4.64 (1.00) | 292 | 8 | 72000 | no |

| criterion | result | numbers |
|---|---|---|
| H1 | **PASS** | O_p95 = 147; base_median = 18; ceiling = 160; random_median = 121 |
| H2 | **PASS** | N_used = 8; budgets_with_both_signs = [100, 200, 300, 400, 600, 800, 1000, 1500, 2000]; control_X_nonreject_rate = 1.000; mean_delta1_changes_sign_across_budgets (reported) = yes; var_delta1 = 103.058 |
| H3 | **PASS** | decoded_median_O_at_b_star = 292; decoded_median_X_at_b_star = 292; fraction = -0.340; mean_delta1 = 18.050; mean_deltaX = -6.140; sign_test_p_X_vs_R = 1.000 |
| H4 | **PASS** | F_median = 142; O_median = 140; O_over_F = 0.986; delta2 = {"cohen_d": 0.6680394286967598, "mean": 4.88, "median": 5.0, "negatives": 47, "positives": 141, "sign_test_p": 2.0785286 |
| H5 | **FAIL** | cohen_d = 1.774; mean_delta1 = 18.050; negatives = 2; positives = 197; power_at_N = 0.996; required_pairs_N = 8; sd_delta1 = 10.177; search_evaluations = 48000; sign_test_p_full_S = 2.48e-56; ties = 1 |
| H6 | **PASS** | N = 8; pairs_min = 8; seeds = 200; var_delta1 = 103.058 |
| H7 | **PASS** | anomalies_total = 0; decoded_median_at_b_star = 292; evals_to_full_map_median = 1421.500; full_map_within_b_max = 200; online_map_verified_all = yes; wrong_decodes_total = 0 |
| H8 | **PASS** | seeds_with_X_shadow_findings (a defect, not a result) = []; seeds_with_ledger_schema_findings = []; seeds_with_replay_findings = [] |
| H9 | **PASS** | alpha = 0.050 |
| budget_rule | **PASS** | b_star = 2000; search_evaluations = 48000 |

Champion holdout medians at B_max: {'F': 10.0, 'O': 10.0, 'R': 10.0, 'X': 10.0}. At B* = 2000: medians {'F': 142.0, 'O': 140.0, 'R': 121.0, 'X': 116.0}, F end-to-end 135.0.

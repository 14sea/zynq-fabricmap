# B3 gate report (lifecycle 2) — 2026-09-17T16:21:12Z (`825ecf2`, dirty at start: False)

Rules: architecture v0.3 §9 — `docs/b3_architecture.md` sha256 `f0f6b2920f7f4c33b477cf6157fb5b0c675084f68ffc1b3a23f8f338a2ad72b5` (last commit `2663e15`). Engine `b2-es-v1` (μ 4, λ 8, k ≤ 4); cartographer `specimen-carto-v1.1`; map `c6a4b23e…`. Seeds: label `b3-gate-2`, master 4260131137, 200 pairs, 1665 excluded values from 7 archived sources plus the fixed list. Control X: seed_x 2041341936 (2 attempt(s)), permutation sha256 `9cc0b64ef1faa37ad89858a92f6beb03056c1308c9c3e270658c1196d1f217dd`. Wall 569.8 s.

The gate fitness is **F1**; other fitnesses are reported for information. The gate is H1–H8 and the budget rule. H9 is a diagnostic (architecture v0.3 §9): Δ2 = O − end-to-end F at every budget ≥ B*, with N₂(B) by the same bootstrap rule and Δ2's power at the gate's N — reported, it decides nothing (Δ2 is the preregistration's secondary outcome).

## F1 — ceiling 40, 200 seeds — **PASS**, B* = 1000

| budget | R | F | O | X | F end-to-end | Δ1 mean (pos/neg/ties, p) | Δ2 mean (p) | ΔX mean (p) | O decoded | N(B) | cost | H1 | N₂(B) | Δ2 power at N(B) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 6 | 6 | 4.5 | 4 | 2 | -0.89 (28/120/52, p 1) | +2.54 (p 1.59e-58) | -0.98 (p 1) | 40 | — | — | yes | 8 | — |
| 200 | 8 | 9 | 7 | 6 | 2 | -1.28 (37/138/25, p 1) | +4.52 (p 2.49e-60) | -1.56 (p 1) | 106 | — | — | yes | 8 | — |
| 300 | 9 | 11 | 9 | 8 | 2 | -0.92 (47/121/32, p 1) | +6.42 (p 1.24e-60) | -1.72 (p 1) | 166 | — | — | yes | 8 | — |
| 400 | 10 | 13 | 10 | 9 | 5 | -0.30 (78/91/31, p 0.859) | +5.54 (p 1.25e-56) | -1.61 (p 1) | 211 | — | — | yes | 8 | — |
| 600 | 12 | 16 | 13 | 10 | 10 | +1.67 (129/42/29, p 8.7e-12) | +3.08 (p 1.53e-33) | -1.33 (p 1) | 262 | 39 | 70200 | yes | 13 | 1 |
| 800 | 13 | 19 | 17 | 12 | 14 | +3.65 (168/19/13, p 2.68e-31) | +1.96 (p 1.08e-18) | -0.92 (p 1) | 281 | 13 | 31200 | yes | 22 | 0.617 |
| 1000 | 13 | 21 | 19 | 12 | 17 | +5.38 (185/7/8, p 2.83e-46) | +1.40 (p 1.34e-07) | -0.80 (p 1) | 288 | 8 | 24000 | yes | 65 | 0.15 |
| 1500 | 14 | 24 | 23 | 13 | 22 | +8.80 (197/1/2, p 4.95e-58) | +0.90 (p 0.00242) | -0.66 (p 0.995) | 292 | 8 | 36000 | yes | — | 0.084 |
| 2000 | 14 | 27 | 26 | 13.5 | 25 | +11.30 (200/0/0, p 6.22e-61) | +0.71 (p 0.0147) | -0.77 (p 0.994) | 292 | 8 | 48000 | yes | — | 0.068 |
| 3000 | 15 | 30 | 30 | 14 | 29 | +14.26 (200/0/0, p 6.22e-61) | +0.41 (p 0.224) | -0.78 (p 0.997) | 292 | 8 | 72000 | yes | — | 0.037 |

| criterion | result | numbers |
|---|---|---|
| H1 | **PASS** | O_p95 = 23; base_median = 2; ceiling = 40; random_median = 13 |
| H2 | **PASS** | N_used = 8; budgets_with_both_signs = [100, 200, 300, 400, 600, 800, 1000, 1500]; control_X_nonreject_rate = 0.996; mean_delta1_changes_sign_across_budgets (reported) = yes; var_delta1 = 10.0856 |
| H3 | **PASS** | decoded_median_O_at_b_star = 288; decoded_median_X_at_b_star = 288; fraction = -0.148699; mean_delta1 = 5.38; mean_deltaX = -0.8; sign_test_p_X_vs_R = 1 |
| H4 | **PASS** | F_median = 21; O_median = 19; O_over_F = 0.904762; delta2 = {cohen_d: 0.494975, mean: 1.4, median: 1, negatives: 55, positives: 124, sign_test_p: 1.34e-07, ties: 21} |
| H5 | **PASS** | cohen_d = 1.68983; mean_delta1 = 5.38; negatives = 7; positives = 185; power_at_N = 0.904; required_pairs_N = 8; sd_delta1 = 3.18375; search_evaluations = 24000; sign_test_p_full_S = 2.83e-46; ties = 8 |
| H6 | **PASS** | N = 8; pairs_min = 8; seeds = 200; var_delta1 = 10.0856 |
| H7 | **PASS** | anomalies_total = 0; decoded_median_at_b_star = 288; evals_to_full_map_median = 1434.5; full_map_within_b_max = 200; online_map_verified_all = yes; wrong_decodes_total = 0 |
| H8 | **PASS** | seeds_with_X_shadow_findings (a defect, not a result) = []; seeds_with_ledger_schema_findings = []; seeds_with_replay_findings = [] |
| budget_rule | **PASS** | b_star = 1000; search_evaluations = 24000 |

H9 diagnostic (decides nothing) — Δ2 = O − end-to-end F at every budget ≥ B* (one-sided sign test, α = 0.05); N₂(B) = the pair count the gate's bootstrap rule would need for Δ2 (power ≥ 0.9); the gate's N = 8:

| budget | p | mean Δ2 | median Δ2 | pos/neg/ties | Cohen's d | N₂(B) | power at N₂ | Δ2 power at the scan's last N (no N₂) | Δ2 power at the gate's N |
|---|---|---|---|---|---|---|---|---|---|
| 1000 | 1.34e-07 | +1.400 | 1 | 124/55/21 | 0.495 | 65 | 0.905 | — | 0.15 |
| 1500 | 0.00242 | +0.900 | 1 | 111/72/17 | 0.292 | — | — | 0.896 at N = 200 | 0.084 |
| 2000 | 0.0147 | +0.710 | 1 | 104/74/22 | 0.23 | — | — | 0.732 at N = 200 | 0.068 |
| 3000 | 0.224 | +0.410 | 0 | 92/81/27 | 0.132 | — | — | 0.201 at N = 200 | 0.037 |

Budget rule candidates (N(B), search cost N × 3 × B, H1): 100: N —, cost —, H1 yes; 200: N —, cost —, H1 yes; 300: N —, cost —, H1 yes; 400: N —, cost —, H1 yes; 600: N 39, cost 70200, H1 yes; 800: N 13, cost 31200, H1 yes; 1000: N 8, cost 24000, H1 yes; 1500: N 8, cost 36000, H1 yes; 2000: N 8, cost 48000, H1 yes; 3000: N 8, cost 72000, H1 yes

Champion holdout medians at B_max: {'F': 1.0, 'O': 1.0, 'R': 1.0, 'X': 1.0}. At B* = 1000: medians {'F': 21.0, 'O': 19.0, 'R': 13.0, 'X': 12.0}, F end-to-end 17.0.

## F2 — ceiling 160, 200 seeds — **FAIL**, B* = 2000

| budget | R | F | O | X | F end-to-end | Δ1 mean (pos/neg/ties, p) | Δ2 mean (p) | ΔX mean (p) | O decoded | N(B) | cost | H1 | N₂(B) | Δ2 power at N(B) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 32 | 33 | 29 | 28 | 17 | -3.46 (41/147/12, p 1) | +12.07 (p 6.22e-61) | -3.86 (p 1) | 40 | — | — | yes | 8 | — |
| 200 | 45 | 47 | 39 | 38 | 17 | -5.64 (30/161/9, p 1) | +22.42 (p 6.22e-61) | -6.56 (p 1) | 106 | — | — | yes | 8 | — |
| 300 | 56 | 58.5 | 50 | 47 | 17 | -6.54 (25/166/9, p 1) | +32.72 (p 6.22e-61) | -8.69 (p 1) | 166 | — | — | yes | 8 | — |
| 400 | 66 | 69 | 59 | 55 | 28 | -6.50 (32/161/7, p 1) | +30.76 (p 6.22e-61) | -9.53 (p 1) | 211 | — | — | yes | 8 | — |
| 600 | 80 | 87 | 77 | 71 | 55 | -3.21 (66/127/7, p 1) | +21.61 (p 6.22e-61) | -9.37 (p 1) | 262 | — | — | yes | 8 | — |
| 800 | 92 | 101 | 92 | 82 | 76 | +0.35 (94/94/12, p 0.529) | +15.97 (p 8.05e-53) | -9.26 (p 1) | 281 | — | — | yes | 8 | — |
| 1000 | 101 | 111 | 104 | 90 | 92 | +3.88 (126/62/12, p 1.76e-06) | +11.67 (p 6.17e-42) | -9.01 (p 1) | 288 | 80 | 240000 | yes | 9 | 1 |
| 1500 | 114 | 130 | 125 | 106 | 118 | +11.61 (172/26/2, p 6.73e-28) | +6.33 (p 1.84e-17) | -8.09 (p 1) | 292 | 13 | 58500 | yes | 24 | 0.653 |
| 2000 | 122 | 142 | 139 | 114 | 135 | +17.36 (189/8/3, p 2.53e-46) | +4.24 (p 2.19e-10) | -7.48 (p 1) | 292 | 8 | 48000 | yes | 44 | 0.245 |
| 3000 | 128 | 153 | 151 | 122 | 150 | +23.27 (195/3/2, p 3.22e-54) | +1.43 (p 0.0161) | -5.58 (p 1) | 292 | 8 | 72000 | yes | — | 0.05 |

| criterion | result | numbers |
|---|---|---|
| H1 | **PASS** | O_p95 = 149; base_median = 17; ceiling = 160; random_median = 122 |
| H2 | **PASS** | N_used = 8; budgets_with_both_signs = [100, 200, 300, 400, 600, 800, 1000, 1500, 2000, 3000]; control_X_nonreject_rate = 1; mean_delta1_changes_sign_across_budgets (reported) = yes; var_delta1 = 130.119 |
| H3 | **PASS** | decoded_median_O_at_b_star = 292; decoded_median_X_at_b_star = 292; fraction = -0.431; mean_delta1 = 17.355; mean_deltaX = -7.48; sign_test_p_X_vs_R = 1 |
| H4 | **PASS** | F_median = 142; O_median = 139; O_over_F = 0.978873; delta2 = {cohen_d: 0.548024, mean: 4.235, median: 4, negatives: 53, positives: 139, sign_test_p: 2.19e-10, ties: 8} |
| H5 | **FAIL** | cohen_d = 1.51763; mean_delta1 = 17.355; negatives = 8; positives = 189; power_at_N = 0.937; required_pairs_N = 8; sd_delta1 = 11.4356; search_evaluations = 48000; sign_test_p_full_S = 2.53e-46; ties = 3 |
| H6 | **PASS** | N = 8; pairs_min = 8; seeds = 200; var_delta1 = 130.119 |
| H7 | **PASS** | anomalies_total = 0; decoded_median_at_b_star = 292; evals_to_full_map_median = 1434.5; full_map_within_b_max = 200; online_map_verified_all = yes; wrong_decodes_total = 0 |
| H8 | **PASS** | seeds_with_X_shadow_findings (a defect, not a result) = []; seeds_with_ledger_schema_findings = []; seeds_with_replay_findings = [] |
| budget_rule | **PASS** | b_star = 2000; search_evaluations = 48000 |

H9 diagnostic (decides nothing) — Δ2 = O − end-to-end F at every budget ≥ B* (one-sided sign test, α = 0.05); N₂(B) = the pair count the gate's bootstrap rule would need for Δ2 (power ≥ 0.9); the gate's N = 8:

| budget | p | mean Δ2 | median Δ2 | pos/neg/ties | Cohen's d | N₂(B) | power at N₂ | Δ2 power at the scan's last N (no N₂) | Δ2 power at the gate's N |
|---|---|---|---|---|---|---|---|---|---|
| 2000 | 2.19e-10 | +4.235 | 4 | 139/53/8 | 0.548 | 44 | 0.902 | — | 0.245 |
| 3000 | 0.0161 | +1.430 | 1 | 107/77/16 | 0.236 | — | — | 0.672 at N = 200 | 0.05 |

Budget rule candidates (N(B), search cost N × 3 × B, H1): 100: N —, cost —, H1 yes; 200: N —, cost —, H1 yes; 300: N —, cost —, H1 yes; 400: N —, cost —, H1 yes; 600: N —, cost —, H1 yes; 800: N —, cost —, H1 yes; 1000: N 80, cost 240000, H1 yes; 1500: N 13, cost 58500, H1 yes; 2000: N 8, cost 48000, H1 yes; 3000: N 8, cost 72000, H1 yes

Champion holdout medians at B_max: {'F': 10.0, 'O': 11.0, 'R': 10.0, 'X': 10.0}. At B* = 2000: medians {'F': 142.0, 'O': 139.0, 'R': 122.0, 'X': 114.0}, F end-to-end 135.0.

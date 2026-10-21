# B4 go / no-go — b4-sim-4 — **no-go** (OF RECORD)

Generated 2026-10-21T06:58:57Z at HEAD `580c0e5d06079dfe9ad885e69aaec23ff13ffcaa` (clean tree: True). Evidence `evidence/b4/sim/b4-sim-4_20261021T065339Z` (status complete, label b4-sim-4, S = 32, fixture False, sha256 `01744b39598b10bbf7d4371be1e5b9355c08fc39a8877ef6957866ac8178f1fa`; batch HEAD `495cc360c97aba58bda959a2e867e6b43dbf4f7f`). Protocol identity `2f096d4adbd83e0ec6350e6da2942cc862e99df4e81539719fa7261dad5a258c`.

**Standing.** the engineering go / no-go policy of docs/b4_architecture.md section 9.4 applied to an exploration archive: a cost policy for spending the production gate's budget — not a significance result, not a gate verdict, not an authorisation of any execution; a go is a proxy signal at one budget, not a prediction of the gate; a no-go stops and what follows needs its own ruling (no automatic successor)

**Policy.** {"B_go":64,"S":32,"alpha_go":0.2,"k9_conditional_medians_min":0.5,"precondition":"every planned pair complete and valid, else no decision","standing":"an engineering cost policy for spending the gate's budget: not a significance result, not a gate, not an authorisation; no automatic successor","statistic":"one-sided exact sign test on Omega - R at B_go, ties excluded from n and counted; positives > negatives"}

## Decision: **no-go** — no-go: at B = 64 positives 7 are not more than negatives 13; at B = 64 the one-sided sign-test p 0.9423408508300781 > 0.2 — the exploration is archived as a result; what follows needs its own ruling (no automatic successor)

## Precondition

```json
{
 "S_is_32": true,
 "every_pair_complete": true,
 "status_complete": true,
 "summary_present": true
}
```

## Statistic 1 — Ω − R at B_go

```json
{
 "alpha_go": 0.2,
 "budget": 64,
 "cohen_d": {
  "special": null,
  "value": -0.3531074633217678
 },
 "mean": -1.71875,
 "negatives": 13,
 "p_le_alpha_go": false,
 "positives": 7,
 "positives_gt_negatives": false,
 "sign_test_p": 0.9423408508300781,
 "ties": 12
}
```

## Statistic 2 — K9 judged conditional medians

```json
{
 "all_ge_min": true,
 "all_panel_medians_descriptive": {
  "ce_mode": 1.0,
  "clock_mode": 1.0,
  "ff_init": 1.0,
  "ff_srval": 0.40625,
  "sr_kind": 0.4375,
  "sr_mode": 1.0,
  "storage_kind": 1.0
 },
 "conditional_medians": {
  "ce_mode": 1.0,
  "clock_mode": 1.0,
  "ff_init": 1.0,
  "ff_srval": 0.8125,
  "sr_kind": 0.875,
  "sr_mode": 1.0,
  "storage_kind": 1.0
 },
 "judged_estimand": "conditional_sr_driven",
 "min": 0.5
}
```

## Ω − R at every budget (descriptive; no other budget is picked)

```json
{
 "128": {
  "cohen_d": {
   "special": null,
   "value": -0.30865070014336937
  },
  "mean": -1.1875,
  "median": 0.0,
  "n": 32,
  "negatives": 10,
  "population_variance": 14.33984375,
  "positives": 5,
  "sign_test_p": 0.940765380859375,
  "ties": 17
 },
 "16": {
  "cohen_d": {
   "special": null,
   "value": -0.3359847412190017
  },
  "mean": -3.875,
  "median": 0.0,
  "n": 32,
  "negatives": 14,
  "population_variance": 128.859375,
  "positives": 6,
  "sign_test_p": 0.9793052673339844,
  "ties": 12
 },
 "192": {
  "cohen_d": {
   "special": null,
   "value": 0.09754311729437715
  },
  "mean": 0.40625,
  "median": 0.0,
  "n": 32,
  "negatives": 6,
  "population_variance": 16.8037109375,
  "positives": 6,
  "sign_test_p": 0.61279296875,
  "ties": 20
 },
 "24": {
  "cohen_d": {
   "special": null,
   "value": -0.09757025178093509
  },
  "mean": -0.84375,
  "median": 0.0,
  "n": 32,
  "negatives": 12,
  "population_variance": 72.4443359375,
  "positives": 7,
  "sign_test_p": 0.9164657592773438,
  "ties": 13
 },
 "256": {
  "cohen_d": {
   "special": null,
   "value": 0.11536778241162536
  },
  "mean": 0.34375,
  "median": 0.0,
  "n": 32,
  "negatives": 5,
  "population_variance": 8.6005859375,
  "positives": 7,
  "sign_test_p": 0.38720703125,
  "ties": 20
 },
 "32": {
  "cohen_d": {
   "special": null,
   "value": -0.19230973161493153
  },
  "mean": -1.5,
  "median": 0.0,
  "n": 32,
  "negatives": 14,
  "population_variance": 58.9375,
  "positives": 5,
  "sign_test_p": 0.9903945922851562,
  "ties": 13
 },
 "48": {
  "cohen_d": {
   "special": null,
   "value": -0.1257263280188742
  },
  "mean": -0.875,
  "median": 0.0,
  "n": 32,
  "negatives": 11,
  "population_variance": 46.921875,
  "positives": 7,
  "sign_test_p": 0.8810577392578125,
  "ties": 14
 },
 "64": {
  "cohen_d": {
   "special": null,
   "value": -0.3531074633217678
  },
  "mean": -1.71875,
  "median": 0.0,
  "n": 32,
  "negatives": 13,
  "population_variance": 22.9521484375,
  "positives": 7,
  "sign_test_p": 0.9423408508300781,
  "ties": 12
 },
 "8": {
  "cohen_d": {
   "special": null,
   "value": -0.16670022639547
  },
  "mean": -1.84375,
  "median": 0.0,
  "n": 32,
  "negatives": 13,
  "population_variance": 118.5068359375,
  "positives": 7,
  "sign_test_p": 0.9423408508300781,
  "ties": 12
 },
 "96": {
  "cohen_d": {
   "special": null,
   "value": -0.28556017368430914
  },
  "mean": -1.25,
  "median": 0.0,
  "n": 32,
  "negatives": 10,
  "population_variance": 18.5625,
  "positives": 9,
  "sign_test_p": 0.6761970520019531,
  "ties": 13
 }
}
```

Self-validation and the file index are in `gonogo.json`; `b4_gonogo.py verify` re-decides this record from its evidence.

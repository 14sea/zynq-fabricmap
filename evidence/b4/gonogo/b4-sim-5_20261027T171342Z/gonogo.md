# B4 go / no-go — b4-sim-5 — **no-go** (OF RECORD)

Generated 2026-10-27T17:13:43Z at HEAD `d1e0e2cc33e9cdfbdf65270a89277599a17ccd74` (clean tree: True). Evidence `evidence/b4/sim/b4-sim-5_20261027T170605Z` (status complete, label b4-sim-5, S = 32, fixture False, sha256 `54613dabd94a4e73aff81ce179f17f8c4b78a41601f9b10b78abe69b43fc5e8c`; batch HEAD `ae7fc3547e1f9271a430b38ffee7fd469b89a7ee`). Protocol identity `5bba53c78d08f3ad32e41a90ef37d2639ea584e97fbf74996d941cec4fe14e7f`.

**Standing.** the engineering go / no-go policy of docs/b4_architecture.md section 9.4 applied to an exploration archive: a cost policy for spending the production gate's budget — not a significance result, not a gate verdict, not an authorisation of any execution; a go is a proxy signal at one budget, not a prediction of the gate; a no-go stops and what follows needs its own ruling (no automatic successor)

**Policy.** {"B_go":64,"S":32,"applies_to":"b4-sim-5 (protocol v0.3.0); b4-sim-4 was decided no-go under v0.2.0 and is not re-decided","k9_conditional_medians_min":0.5,"p_max_go":0.2,"p_max_go_standing":"an engineering cost threshold on the sign test's p, not the alpha of a formal scientific test","precondition":"every planned pair complete and valid, else no decision","standing":"an engineering cost policy for spending the gate's budget: not a significance result, not a gate, not an authorisation; no automatic successor","statistic":"one-sided exact sign test on Omega - R at B_go, ties excluded from n and counted; positives > negatives"}

## Decision: **no-go** — no-go: at B = 64 the one-sided sign-test p 0.4018096923828125 > the cost threshold p_max_go 0.2 — the exploration is archived as a result; what follows needs its own ruling (no automatic successor)

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
 "budget": 64,
 "cohen_d": {
  "special": null,
  "value": 0.011027027284780772
 },
 "mean": 0.03125,
 "negatives": 7,
 "p_le_p_max_go": false,
 "p_max_go": 0.2,
 "p_max_go_standing": "an engineering cost threshold on the sign test's p, not the alpha of a formal scientific test",
 "positives": 9,
 "positives_gt_negatives": true,
 "sign_test_p": 0.4018096923828125,
 "ties": 16
}
```

## Statistic 2 — K9 judged conditional medians

```json
{
 "all_ge_min": true,
 "all_panel_medians_descriptive": {
  "ce_mode": 0.875,
  "clock_mode": 1.0,
  "ff_init": 1.0,
  "ff_srval": 0.4166666666666667,
  "sr_kind": 0.25,
  "sr_mode": 0.875,
  "storage_kind": 1.0
 },
 "conditional_medians": {
  "ce_mode": 0.875,
  "clock_mode": 1.0,
  "ff_init": 1.0,
  "ff_srval": 0.8333333333333334,
  "sr_kind": 0.5,
  "sr_mode": 0.875,
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
   "value": 0.24029162745540172
  },
  "mean": 0.46875,
  "median": 0.0,
  "n": 32,
  "negatives": 3,
  "population_variance": 3.6865234375,
  "positives": 6,
  "sign_test_p": 0.25390625,
  "ties": 23
 },
 "16": {
  "cohen_d": {
   "special": null,
   "value": -0.39083241881612885
  },
  "mean": -4.34375,
  "median": 0.0,
  "n": 32,
  "negatives": 15,
  "population_variance": 119.6630859375,
  "positives": 4,
  "sign_test_p": 0.9977874755859375,
  "ties": 13
 },
 "192": {
  "cohen_d": {
   "special": null,
   "value": 0.28846459742239733
  },
  "mean": 0.5625,
  "median": 0.0,
  "n": 32,
  "negatives": 3,
  "population_variance": 3.68359375,
  "positives": 7,
  "sign_test_p": 0.171875,
  "ties": 22
 },
 "24": {
  "cohen_d": {
   "special": null,
   "value": -0.38102793517998595
  },
  "mean": -4.71875,
  "median": 0.0,
  "n": 32,
  "negatives": 14,
  "population_variance": 148.5771484375,
  "positives": 8,
  "sign_test_p": 0.9330997467041016,
  "ties": 10
 },
 "256": {
  "cohen_d": {
   "special": null,
   "value": 0.16459062535345328
  },
  "mean": 0.34375,
  "median": 0.0,
  "n": 32,
  "negatives": 4,
  "population_variance": 4.2255859375,
  "positives": 4,
  "sign_test_p": 0.63671875,
  "ties": 24
 },
 "32": {
  "cohen_d": {
   "special": null,
   "value": -0.37060675543468613
  },
  "mean": -3.65625,
  "median": 0.0,
  "n": 32,
  "negatives": 11,
  "population_variance": 94.2880859375,
  "positives": 9,
  "sign_test_p": 0.7482776641845703,
  "ties": 12
 },
 "48": {
  "cohen_d": {
   "special": null,
   "value": -0.3516677590652254
  },
  "mean": -1.5,
  "median": 0.0,
  "n": 32,
  "negatives": 11,
  "population_variance": 17.625,
  "positives": 8,
  "sign_test_p": 0.8203582763671875,
  "ties": 13
 },
 "64": {
  "cohen_d": {
   "special": null,
   "value": 0.011027027284780772
  },
  "mean": 0.03125,
  "median": 0.0,
  "n": 32,
  "negatives": 7,
  "population_variance": 7.7802734375,
  "positives": 9,
  "sign_test_p": 0.4018096923828125,
  "ties": 16
 },
 "8": {
  "cohen_d": {
   "special": null,
   "value": -0.2624524482470899
  },
  "mean": -3.40625,
  "median": 0.0,
  "n": 32,
  "negatives": 15,
  "population_variance": 163.1787109375,
  "positives": 4,
  "sign_test_p": 0.9977874755859375,
  "ties": 13
 },
 "96": {
  "cohen_d": {
   "special": null,
   "value": 0.14455534152860666
  },
  "mean": 0.3125,
  "median": 0.0,
  "n": 32,
  "negatives": 2,
  "population_variance": 4.52734375,
  "positives": 9,
  "sign_test_p": 0.03271484375,
  "ties": 21
 }
}
```

Self-validation and the file index are in `gonogo.json`; `b4_gonogo.py verify` re-decides this record from its evidence.

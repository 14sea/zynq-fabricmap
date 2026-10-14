# B3 lifecycle 2 — S3 plan — 2026-10-14

The owner authorised the S3 batch on 2026-10-14 (the rate fixed at the S2 calibration's
3180.049965139327 evals/h; the transition to change exactly `plan`, `status` and `history`). Both
production steps ran once, in order, on the committed S2 manifest `bea08769…` (commit `e6ba9a2`):

```
python3 -B b3/host/b3_plan.py --rate-per-hour 3180.049965139327        # canonical --out evidence/b3
python3 -B b3/host/b3_manifest.py plan --manifest manifests/b3_manifest.json --plan evidence/b3/plan.json
```

- Planned (S3) manifest SHA-256: `258bb14c4b3ba1a3d33741f23b1663f563de64da800843d30c8a615e2f128628`
- Canonical plan `evidence/b3/plan.json`: file SHA-256 `b202a2800d5934978394ffca7ee8f24d9b2897c953d4f41b1050fed840c81dd1`
  (`generated_utc` 2026-10-14T15:32:14Z); the plan without `generated_utc`, as canonical JSON:
  `6267c8f7f42c664800b2f9405d880f2059a223068661318f5e43e3228cb588ac` — equal to the owner-checked
  scratch baseline rendered before authorisation (`build/wip/scratch_2026_10_14/s3_trial/`, ignored)
- Prediction `evidence/b3/prediction.json`: **byte-identical** to the S0-pinned prediction, SHA-256
  `92b774ea62d290d380e72a4c990b384060db9006cf9160940fb4848ae4a14cf5` (rewritten by the tool with the same bytes)
- Pin table `73cec93a…` (88 files), image `28c80eca…`, preregistration `e89c5677…`, B3Q documents, the S2
  qualification record and calibration: unchanged

## The plan

The tool evaluated the preregistered stop rule before writing (`plan_regen.stdout`): the predicted
primary on the fixed seeds is 8 / 0 / 0, sign-test p = 0.00390625 ≤ α 0.05 — **no finding**, the same
prediction the preflight of `7cb0879` passed. Only `session_split` and `generated_utc` differ from the
rate-less plan the tree carried since S0 (`fbd922ba…`).

| split field | value |
|---|---|
| `status` | DETERMINED |
| `rate_measured` / `calibration_margin` / `rate_for_split` | 3180.049965139327 / 0.85 / 2703.042470368428 |
| `pairs_per_session_max` | 1 |
| `sessions` | **8**, one pair each (pairs 0..7): 3 005 records, expected span 4 002.156872705553 s, deadline 5 602.696090881941 s per session |
| `total_records` | **24 040** (16 of them baselines) |

`pin_plan` rebuilt the whole plan and the whole prediction — every O run's every ledger entry — from the
frozen inputs and the calibration's rate and compared them path by path (`plan_findings`), held the split
DETERMINED and its `rate_for_split` to the calibration's, and tied the plan's `prediction_sha256` to the
sidecar's bytes and the sidecar to the S0 pin. The manifest's `plan` block records the plan's file digest,
the prediction's digest, `sessions 8` and `total_records 24040`.

## The transition, from the bytes

Production `verify` passes before (S2) and after (S3) in fresh processes (`verify_before.json`,
`verify_after.json`: S3 / qualified true / refusal null / `258bb14c…`, `check_plan` ok). The transition
changed exactly `history`, `plan` and `status` (`transition.json`, computed from the manifest bytes before
and after); `prereg`, `image`, `instrument_pins`, `qualification_plan`, `qualification`, `qualified`,
`calibration`, `experiment`, `seeds`, `prediction` and `map` are unchanged.

## Standing

Every B3 ruling pair binds to THIS manifest's sha256 (`258bb14c…`); none exists yet, and no board session
is authorised by this transition. The transport stop-loss stands. The S3 clean-tree proof is **pending at
this commit** and is the next commit's: it runs the formal tool and archives its result as written; under
the owner's named exception (`docs/b3_s2_proof_exception_2026_10_14.md`) a failure confined to the
reproduced fixture-path contamination is followed by the supplementary verification recorded in
`proof_exception/`; any other failure is reported, not accepted.

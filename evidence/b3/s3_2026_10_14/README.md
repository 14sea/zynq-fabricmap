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
is authorised by this transition. The transport stop-loss stands.

## The S3 clean-tree proof (the next commit after the plan)

The formal tool ran on the clean tree at `2f8ff58` (`evidence/b3/tests/test_report_2026-10-14T180234Z.json`,
15:39:21Z – 18:02:34Z, archived as written) and **did not pass**: `clean_tree_proof = false`, twelve
`proof_refusals`; `b2_tree` 2 096 OK, `b3_tree` 793 and `b3_removal` 792 each `FAILED (failures=2, errors=1)`,
the start and end snapshots equal, the pins `manifest_bound` to `258bb14c…`, the sentinel 793 → 792.

- **The error** is the first defect of `docs/b3_s2_proof_exception_2026_10_14.md` (the lifecycle World's
  process-wide patch of the runner's B1-manifest path; `test_b3_plan.Committed.test_the_committed_split_is_what_the_stage_licenses`
  erroring on the fixture's nonce `0000000000000000`), the same test and the same `Refusal` as at S2.
- **The two failures are a second defect, named at this node**: the pinned `b3/firmware/b3_seed_data.h` carries
  the plan file's digest (`fbd922ba…`, the pre-S3 plan) and the two byte-for-byte tests of `test_b3_orch_twin`
  compare it to a fresh render, which now carries the S3 plan's `b202a280…`. The S3 transition necessarily changes
  that digest, so the tests cannot pass at S3 with the header as pinned. The macro has no consumer; the header's
  data is unchanged; the committed header `e3eb2b84…` is the one the pin table and the build evidence bind.

The owner's ruling of 2026-10-14 narrowly extended the engineering-acceptance exception to the second defect and
the supplementary verification was performed afresh at this node, recorded in `proof_exception/`:

| | result |
|---|---|
| the generator's own check (read-only) | `STALE`, exit 1 — the formal failure reproduced directly |
| the complete fresh render vs the committed header | **exactly line 19** differs (`header.diff`): `B3_SEED_PLAN_SHA256` `fbd922ba…` → `b202a280…`; old = the historical plan, new = the manifest's plan pin; the committed header = pin table = build evidence → `header_check.json` **ACCEPT** |
| negative controls (temporary copies) | four mutants, **all refused by name** (`header_controls.json`) |
| the plan module, tree / removal shadow (own process each) | **32 / 32 OK** and **32 / 32 OK** |
| fresh-process verify after both | **S3 / qualified true / refusal null / `258bb14c…`** |

**Engineering acceptance** of S3 rests on that supplement under the named exception. **The formal clean-tree
proof did not pass**, and the archived report says so; no process isolation makes the two header tests pass. The
first attempt of the header check failed on the checker script's own bug and is kept in
`proof_exception/header_attempt_1_script_bug/`. Not done: any B3 ruling pair, any board session, any push.

# B3 lifecycle 2 — S2 qualify — 2026-10-14

The owner authorised the S2 transition in conversation on 2026-10-14 after accepting the two
B3Q attempts as archived: -01 HOLD (`evidence/b3/b3q_17A6_2026-10-14-01/`, commit `35d81c2`,
kept as observed and NOT an input here) and -02 PASS (`evidence/b3/b3q_17A6_2026-10-14-02/`,
commit `76534b7`). The production CLI executed the transition once, at 2026-10-14T12:13:20Z,
on the committed S1 manifest (`bb917ec7…`, commit `6e0098d`; post-freeze proof
`evidence/b3/tests/test_report_2026-10-14T090238Z.json`), from the -02 evidence only.

```
python3 -B b3/host/b3_manifest.py qualify --manifest manifests/b3_manifest.json \
    --evidence-dir evidence/b3/b3q_17A6_2026-10-14-02
```

- Qualified (S2) manifest SHA-256: `bea08769c4adb86a20654d455b79e015973192c67bf62199a91c561e97ecab8f`
- Run manifest the session was bound to (`manifest_at_run.json`): the S1 manifest `bb917ec7…`
- Preregistration SHA-256 (v0.3.1, frozen at S1): `e89c5677ac7f2be28e178b64d48b7a6f8bfdd35158d5ca5639ac8323c1451353`
- Pin table SHA-256: `73cec93a72aa962f10b331c3720f50439201a73bee2ba34971dd2b8b677ac280` (88 files)
- Image SHA-256: `28c80eca419efe88ac6e1969c9fc5d87d416d8a6137e4612288298b9e5da8299` (131 092 bytes, ELF `0d0f99a6…`)
- B3Q documents: plan `490347f4…`, prediction `7eae2650…` (pinned at S0, unchanged)

## What S2 pinned

**The qualification record** is RECONSTRUCTED from the evidence directory on every verify —
B1's eleven qualification files plus `runner_session.json`, the export seal checked — never
copied from a summary, and the evidence is RE-ADJUDICATED by the production
`b3_runner.readjudicator` against the S1 manifest's pinned B3Q plan and prediction. The
re-adjudication's outcome, measured rate, verified audit policy and qualification block equal
the evidence's: outcome PASS; 123 fitness values, 40 ledger entries, 2 baselines,
fitness-sequence sha256 `cbd277e6…` — equal to the pinned prediction's; audit policy
all-self-reporting; binding to session B3Q, the image, the preregistration, the carrier
`d85daef4…` / `0x42310001`, the map `c6a4b23e…`, the S1 manifest and the B3Q documents.

**The calibration**, written from that record by `calibration_from` and recomputed on every
verify:

| field | value |
|---|---|
| `rate_per_hour` | **3180.049965139327** evals/h (the -02 session's measured all-self-reporting rate, full precision; the -01 attempt's 2970.27 is not an input and the two are not averaged) |
| `margin` | 0.85 (frozen, preregistration §2) |
| `rate_for_split` | **2703.042470368428** |
| `audit_policy` | all-self-reporting (verified by the instrument layer) |
| `sessions` / `pairs_per_session_max` | **8 / 1** |

## The consequence for S3, derived here and authorising nothing

Under the frozen split rule (`b3_plan.session_split`: a session holds the largest whole number
of pairs whose expected span `records × 3600 / rate_for_split` fits the 7 200 s cap; records per
pair 3 003 plus two baselines per session), this rate gives **eight sessions of one pair each**:
3 005 records, expected span 4 002.1569 s, deadline 5 602.6961 s per session; two pairs would need
8 001.6501 s, over the cap. 24 040 records in all, 16 of them baselines. (B2 ran its nine pairs in
two sessions of 5 + 4 pairs.) This is the rule's arithmetic over the pinned rate — the S3 plan
will carry it — and it authorises no board session: each B3 session needs its own ruling pair
with its own transport disposition.

## The transition, from the bytes

Production `verify` passes before (S1) and after (S2) in fresh processes (`verify_before.json`,
`verify_after.json`: S2 / qualified true / refusal null / `bea08769…`). The transition changed
exactly `calibration`, `history`, `qualification`, `qualified` and `status` — the five the S2 rule
licenses (`transition.json`, computed from the manifest bytes before and after); `prereg`, `image`,
`instrument_pins`, `qualification_plan`, `experiment`, `seeds`, `prediction` are unchanged and `plan`
stays null. The history entry records the run manifest `bb917ec7…` and the rate.

## Standing

The transport stop-loss stands: the -02 PASS is one attempt under a bounded exception and does
not establish transport stability; the -01 HOLD (an 80-byte deletion inside a heartbeat burst) is
archived as observed. Not done by this transition: the S2 clean-tree proof (**pending at this
commit; the next commit's**, bound to `bea08769…`), the S3 plan (`b3_plan.py --rate-per-hour
3180.049965139327`, the owner's unit), any ruling, any board session, any push.

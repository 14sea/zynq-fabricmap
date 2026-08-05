# Round 10 consumer handoff — comparison lifecycle

> **APPLIED 2026-08-05.** The producer adopted this contract and committed
> `gate_runs/run_2026_08_05_ff/predictions.json` at sha256 `5440ef27…` in `2b40693`,
> after the separately recorded hold release `c45e76e`. No specimen bitstream existed
> when the commitment was made. Statements below about what the then-held producer
> "can now" do describe the handoff moment.

Status: **shipped**. The lifecycle rule requested in `docs/round10_request.md` is
implemented as certificate and `gate_predictions` schema 1.5.0. Published 1.4 and
1.2 records retain their original semantics.

## Contract

Every feature prediction at 1.5 or later has exactly the 1.4 fields plus required
`comparison_specimen_id`. Both endpoint IDs must occur in the prediction artifact's
`specimens[]`, and they must differ. In the resulting certificate:

```text
feature_specimen_id  == committed specimen_id
baseline_specimen_id == committed comparison_specimen_id
```

The verifier derives the complete distinct unordered endpoint-pair set from those
committed fields. `pair_accounting[]` must contain exactly that set, once per pair.
The in-scope address union used to relabel every accounting bit is also commitment
derived; a result cannot change its endpoint and make the changed pair self-consistent
by changing its accounting record too.

The external prediction artifact and its pinned reference must select schema 1.5 or
later when the feature certificate selects 1.5. JSON Schema pins that version rule;
the host verifier enforces the cross-file prediction shape and lifecycle equality.

## Consumer artifacts

- normative schema text: `docs/certificate_schema.md`;
- machine-readable certificate constraints: `schemas/certificate.schema.json`;
- independent verifier: `host/verify_certificate.py`;
- passing known answer:
  `tests/fixtures/{predictions_feature15_pass,certificate_feature15_pass}.json`;
- negative post-build endpoint substitution:
  `tests/fixtures/certificate_feature15_wrong_comparison.json`;
- ten conformance/adversarial tests: `tests/test_round10.py`.

The negative fixture swaps both result baselines and rewrites `pair_accounting[]` to
match the substituted result pairs. Those two certificate sections are internally
consistent with one another, but verification still fails because neither may replace
the preregistered comparison endpoints.

## Compatibility and producer use

The committed Run A feature-1.2 certificate and Run B group-1.4 certificate both
continue to verify as production. Group records have no comparison endpoint, so Run B
does not need another reissue. No historical Run A erratum is required.

The held `clb_ff_config` commitment can now select `schema_version: 1.5.0`, include
both endpoints in `specimens[]`, and record `comparison_specimen_id` on all 176
predictions. Its certificate must select 1.5.0 and account for precisely the committed
pair set.

Validation at handoff:

```text
127 tests OK
freeze verify: 46 files, 10,896 classified features, unclassified=0
address known answers: 5/5; producer cross-check OK
Run A production: tp=262 fp=0 fn=0
Run B production: address 16/16, vacuous 16, semantic 16/16
```

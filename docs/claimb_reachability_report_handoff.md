# Claim B reachability report — consumer handoff

This is the consumer-side completion of `review.v4.txt` item 3. It defines what the
producer's host-only reachability calculation must emit; it does **not** run that
calculation and contains no production target.

Authority:

- schema: `schemas/reachability_report.schema.json`, `reachability_report` 1.0.0;
- independent verifier: `host/verify_reachability_report.py`;
- literal conformance spec/report and three schema-valid known-bad reports under
  `tests/fixtures/reachability_{spec,report}_*.json`.

## Producer record

The report is one JSON object:

```text
schema / schema_version / report_id
spec { path, schema_version, spec_id }
spec_sha256
status = complete | exhausted
per_lut[]
  site / bel / mutable_count
  target_truth_table / draw_index
  discarded_draws[] { draw_index, attainable_ceiling, blocked_positions[] }
  attainable_ceiling / blocked_positions[] / exhausted
totals
  expected_luts / reported_luts / selected_luts
  discarded_draws / attainable_ceiling / exhausted
tool_versions
```

`spec_sha256` is deliberately top-level because that is the field frozen by
`specs/reachability_spec_v1.json`. `target_truth_table` is canonical
`64'h[0-9A-F]{16}`. A selected LUT has non-null target fields and `exhausted:false`; the
first exhausted LUT has null target fields, exactly the cap's rejected draws, and
`exhausted:true`. Nothing follows an exhausted LUT.

The producer calls its executable selection functions from
`scripts/build_reachability_spec.py`. It must read and hash the committed spec bytes and
emit the derived record; it must not copy the consumer fixture or ask the verifier to
construct the output.

## What the verifier independently proves

The verifier imports no producer module. From the committed spec it separately:

1. checks the literal target-vector known answer;
2. validates every LUT mask/fixed partition, base INIT and identity `LOCK_PINS`;
3. rebuilds each balanced target from the LCG/Fisher-Yates contract;
4. advances one global draw index across accepted and rejected per-LUT draws;
5. recomputes every blocked position and attainable ceiling;
6. stops on the first exact-cap exhaustion;
7. requires the complete `per_lut` and `totals` records to equal that derivation.

The CLI additionally requires the production spec path
`specs/reachability_spec_v1.json`, its production `spec_id`, exactly six LUTs, and spec
bytes identical to the blob in `HEAD`. Thus the committed conformance fixture cannot be
presented as the Claim B result.

Production verification command, after the producer has emitted a report:

```sh
python3 host/verify_reachability_report.py path/to/reachability_report.json
```

No `--allow`, alternate-spec, or skip-authority option exists.

## Known-bad boundary

All three bad reports pass the authority schema and fail semantic verification:

- `reachability_report_bad_wrong_target.json`: balanced target, wrong for its recorded k;
- `reachability_report_bad_skipped_draw.json`: skips an acceptable k and selects a later one;
- `reachability_report_bad_early_exhaustion.json`: reports exhaustion before the cap.

The tests also refuse missing/extra/duplicate/reordered LUTs, wrong pins or spec hash,
unbalanced targets, reordered or acceptable discarded draws, wrong ceiling/blocked
positions/totals, success after 256 failures, a non-`per_lut` predicate, a drifted literal
known answer, an uncommitted spec, and absence of Git authority.

This handoff authorises neither the production reachability calculation nor Vivado or
device work.

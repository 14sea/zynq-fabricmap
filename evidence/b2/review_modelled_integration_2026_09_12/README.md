# Independent modelled integration review — 2026-09-12

Reviewed HEAD: `9035b188959ca5b14325cc7563fc67520e18f21c`.
All generated board output is **MODELLED**. No hardware was contacted, no real
qualification was created, and no authorization was issued or consumed.

- `integration.json`: independent B2Q callback PASS, actual S2/S3 transitions,
  fresh-process verification, and B2 pairs 7/8 at budget 600 through the same
  instrument host stack and runner callback. The B2 preflight doubles only the
  missing pins hook, principal-boundary validation and `sb` discovery.
- `finalization.json`: separate production `b1_session.finalize` and
  `persist_summary` acceptance, followed by genuine qualification re-adjudication;
  also records the model CLI's missing adjudication and final-summary outputs.
- `focused_suite.log`: 395 tests, zero skips, OK in 383.052 seconds.
- `verification.json`: preserved input hashes and hashes/sizes of review artifacts.
- `modelled_transcripts.tar.gz`: the original generated B2Q/B2 transcripts, S3
  manifest and plan/prediction. The test ruling archives inside are inert model
  documents and grant no authority. Paths inside fixture manifests are the original
  temporary paths; this archive does not constitute a portable or real qualification.

To repeat the offline probes in this checkout, with the existing instrument and
image available:

```sh
python3 evidence/b2/review_modelled_integration_2026_09_12/review_modelled.py
python3 evidence/b2/review_modelled_integration_2026_09_12/review_finalization.py
```

They create new temporary fixtures/evidence and print their locations. No live
runner execution or serial port is involved. The larger B2 demonstration takes
several minutes. The model helper's reported `wall_s` starts after candidate
construction, so it is not the duration of the whole script.

The initial local draft of `review_modelled.py` assumed split entries exposed
`pair_first`/`pair_count`. Actual plan entries contain a `pairs` list. That reviewer
script error was corrected before the saved successful run; production code was
unchanged.

See [the English review](../../../docs/b2_modelled_integration_review_2026_09_12.md)
for acceptance scope, P3 corrections and remaining package work.

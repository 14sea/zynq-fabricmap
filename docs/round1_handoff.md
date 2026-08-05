# Round 1 consumer-side handoff

> **GEOMETRY UPDATE 2026-08-02.** The 101-word frame-size assumption described below
> was discharged after this handoff: `(5,144 frames + 8 pad) × 101 words` exactly
> consumes the real FDRI payload, independently reproduced on two bitstreams. Current
> normative text is `docs/freeze_format.md` §5.6 and `docs/evidence_contract.md`.

This drop implements the author-owned side of `docs/workflow.md` Round 1 without
reading or importing the producer-owned extractor, specimen harness, differ, or gate.

## Delivered

- `schemas/certificate.schema.json` — `fabric_bit_class_certificate` 1.0.0, including
  first-class passed and failed records.
- `docs/certificate_schema.md` — semantic invariants and the independently recomputed
  falsifier that JSON Schema cannot express.
- `host/verify_certificate.py` — JSON Schema, frozen-input freshness, complete frozen
  rule, address/polarity, observed evidence, mask, split, coverage, accounting and
  decision verification. A valid failed certificate exits 2 by default and is never
  mistaken for a usable pass; `--allow-failed` only checks failure-record conformance.
- `host/verify_data.py` — independent spec/manifest verifier for file sets, hashes,
  sizes, machine-readable classification participation, regex partition/coverage,
  per-file/per-class counts and totals.
- `tests/fixtures/address_known_answers.json` plus
  `host/verify_address_fixtures.py` — five known answers covering a CLBLL_L LUT INIT,
  SLICEM LUTRAM, negated INT_L PIP assignments, bit-less ppip and frozen mask bit.
  The selected Y25 tiles exercise the normative 48 -> 51 clock-row offset jump; the
  LUTRAM and mask cases also exercise `B // 32` into the second tile word.
- `tests/fixtures/certificate_{pass,fail}.json` — conformance records for both outcomes.
- `tests/test_round1.py` — positive checks and decisive falsifiers for a bad data hash,
  wrong FAR, stale freeze and a certificate that falsely claims to pass.

Each `feature_results[]` item names `rule_file`. The certificate verifier requires
that file to be pinned, rereads the named feature, and compares the complete ordered
segbits rule (including negation) with the emitted prediction. This prevents a
self-consistent but frozen-data-inconsistent certificate.

## Commands run

```sh
scripts/extract_prjxray_subset.py --verify
python3 host/verify_data.py
python3 host/verify_address_fixtures.py
python3 host/verify_certificate.py tests/fixtures/certificate_pass.json
python3 host/verify_certificate.py tests/fixtures/certificate_fail.json --allow-failed
python3 -m unittest -v tests/test_round1.py
python3 -m py_compile host/verify_data.py host/verify_address_fixtures.py \
  host/verify_certificate.py tests/test_round1.py
git diff --check
```

Latest test result: 9 tests passed. The current host has Python 3.12.3 and
`jsonschema` 4.10.3; certificate validation requires the `jsonschema` package.

## Producer integration

The specimen generator and differ do not need to wait for this drop. Before treating
the gate's address arithmetic as trusted or emitting the first production certificate:

1. run the independent data and address verifiers above;
2. emit both a deliberately passing and deliberately failing trial certificate;
3. require the passing record to exit 0, the failed record to exit 2, and use
   `--allow-failed` only to establish that the latter is a complete valid record;
4. open `review.vN.txt` on any disagreement rather than changing the fixture.

The 101-word frame geometry remains an assumption pending the first specimen run, as
already disclosed by `docs/freeze_format.md` section 5.6. These fixtures prove
conformance to the frozen address contract; they do not certify physical feature
meaning or discharge that assumption.

## Repository coordination note

While this handoff was being authored, concurrent local commit `7d02816` swept the
then-present preliminary Round 1 files into a board-policy commit. The final
`rule_file` checks, failed-certificate exit behavior, ninth test, and this handoff are
later working-tree changes and must be included intentionally before the Round 1 drop
is considered committed. No push was performed by the author.

# Round 5 token-text resolution and first production certificate

The first real certificate exposed an ambiguity in the original freeze contract:
the producer copied token `32_09` verbatim while the independent verifier rendered
the parsed integers as `32_9`. The frozen data adjudicates the issue. All 14,142
tokens in the three frozen segbits files use exactly two zero-padded decimal digits
for each field, with zero exceptions; `docs/freeze_format.md` §5.3 now makes this
normative.

The consumer fix deliberately does not add zero-padding code. The verifier now:

- compares the emitted token sequence directly with the matched frozen `.db` line;
- separately parses both sides and compares frame offset, bit offset and polarity;
- retains the Round 4 field-for-field prediction commitment comparison.

This catches a self-consistent producer error: the new adversarial test changes the
same token in both preregistered predictions and certificate, so their lifecycle
comparison passes, but frozen-text comparison rejects it.

Acceptance result:

```text
CERTIFICATE VERIFY: OK — status=passed tp=262 fp=0 fn=0
```

Command:

```sh
python3 host/verify_certificate.py \
  gate_runs/run_2026_08_02_a/certificate.json --require-production
```

No certificate or prediction artifact was changed. No commit or push was performed
by the consumer-side author.

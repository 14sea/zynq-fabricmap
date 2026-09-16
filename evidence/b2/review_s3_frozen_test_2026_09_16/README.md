# S3 frozen-test contradiction

`probe.py` is read-only. It compares Git blobs at `f007f92` and `8319683`, the
frozen B2 pin table, the committed S3 plan, and the failed report currently at
`evidence/b2/tests/test_report_2026-09-16T095911Z.json`.

It establishes two separate facts:

1. The S3 plan is DETERMINED, bound to its manifest digest, and gives 4+4+1.
2. The exact test bytes frozen by the pin table require the committed plan to be
   UNDETERMINED. Correcting that test changes a frozen pinned file and causes the
   observed 52 dependent failures/errors.

The script also records that `instrument_pins` and `prereg` are outside the
licensed qualification transition fields. It does not claim that a new lifecycle
can reuse the old B2Q qualification.

Run from the repository root:

```sh
python3 -B evidence/b2/review_s3_frozen_test_2026_09_16/probe.py
```

No suite, manifest transition, pin generation, board access, or ruling occurs.

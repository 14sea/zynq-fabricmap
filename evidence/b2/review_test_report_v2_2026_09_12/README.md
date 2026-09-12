# B2 reporter schema 2.0.0 independent review evidence

Reviewed source: `a52c22907d203c8a775d76428e4114d45a530ec5`.

- `probe_report_v2.py`: controlled positive/negative API cases, actual no-run and
  I/O CLI checks, snapshot-order probe, historical Git artifact checks, and four
  in-memory production-predicate mutations running the unchanged reporter tests.
- `results.json`: captured output. Five malformed/contradictory logs receive proof;
  four malformed log values, one legacy tuple and two malformed snapshot blocks
  raise AttributeError. Prior negative controls refuse as intended.
- `reporter_tests.log`: independent unmodified suite, 26 tests, OK.

Run from any directory:

```sh
python3 /home/test/zynq_fabricmap/evidence/b2/review_test_report_v2_2026_09_12/probe_report_v2.py /home/test/zynq_fabricmap
```

The script uses archived schema-2 snapshots as controlled API inputs. Synthetic
four-test log strings are not actual executions, new qualifications, or silicon
evidence. The original schema-1 probe uses an obsolete builder signature and mutation
source text; this script exercises the corresponding contracts through schema 2.0.0.
CLI outputs use temporary directories. Mutation modules exist only in memory.
The original reporter, pins, reports, manifest, firmware, image, instrument and
rulings are not modified. No ports are opened and no ruling is consumed.

The probe records observed outcomes rather than asserting that defects must remain;
after correction, negative results should change to named refusals. Positive controls,
earlier refusals and predicate mutation detection remain assertions.

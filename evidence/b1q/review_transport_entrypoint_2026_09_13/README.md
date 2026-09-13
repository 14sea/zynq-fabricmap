# Offline transport entry-point review

See `docs/b1q_transport_entrypoint_review_2026_09_13.md` for the findings.

Run from any working directory:

```
PYTHONDONTWRITEBYTECODE=1 python3 -B /home/test/zynq_fabricmap/evidence/b1q/review_transport_entrypoint_2026_09_13/probe_entrypoint.py
```

The script replaces serial ports, kernel identity and counters with doubles and
uses temporary directories. It never opens a real port. Production `main`,
preflight, acquisition, analysis and exporter execute unchanged; only preflight's
clock and driver sleep are replaced to make the cases deterministic and fast.
The reported fake clock is not a throughput measurement or calibration.

Assertions describe the reviewed defects and positive controls. They must be
updated or interpreted as before/after expectations when validating a fix;
nonzero exit after a fix does not by itself mean a regression. `results.json`
retains the observations on the reviewed tool digest.

Existing suite run observed by the reviewer:
`Ran 111 tests in 66.978s`, `OK`, zero skips. This is a focused test result,
not a whole-suite clean-tree proof. The first probe invocation stopped at an
incorrect expectation that zero repetitions would report complete exposure;
inspection showed `completed_exposure=false`. That expectation was removed,
and the actual zero-repetition result is retained without a false finding.

The B1 pins, B2 pins and B2 gate suites separately passed 3, 6 and 28 tests
(37 total), with no skips. Production B2 verify accepted the unchanged S1.

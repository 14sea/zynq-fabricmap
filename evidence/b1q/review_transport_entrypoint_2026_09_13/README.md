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

## After the corrections (`6c7a276`, tool `15460127…`)

`results_after_fix.json` is the same probe run unchanged against the corrected tool, with its
before-fix assertions not evaluated (they are before/after expectations, as above); it records
the head and tool digest it ran on. Observed: `positive` exit 0 (302 accepted, 0 losses, every
file plus `preflight_rx.bin`); `silence_control` exit 3 `refusal: silence`, one write, both
counter attempts; `continuous_preflight` exit 3 `refusal: not_quiet` at the 3.0 s fake
deadline, the received bytes on disk, no exposure; `preflight_detach` exit 2, `failed_phase:
drain`, the nonce in `preflight_rx.bin`, both counter attempts, no traceback;
`reuse_directory` exit 5, all four old files byte-identical, the opener never called;
`wrong_usb_identity` exit 0 without `--expect-usb` (metadata only, by design — the gate is the
flag, exercised in the suite); `zero_repetitions` unchanged. Offline; no real port opened.

# Board soak offline review

`probe_soak.py` drives the production board-soak CLI using an in-memory fake
U-Boot, a virtual monotonic clock and temporary output directories. No real
serial port is opened. It reuses only the test helper that renders md output;
the parser, orchestration and finalization under review run unchanged.

Run with `PYTHONDONTWRITEBYTECODE=1 python3 -B`.
`results.json` contains one clean control and ten independent adverse/scope
probes. Assertions record the observed pre-fix behavior; they are not post-fix
acceptance criteria. `repeated_wrong` deliberately alters the same value in all
responses, demonstrating the lack of independent source truth, not a prediction
of the probability of that failure on hardware. `fake_elapsed` is virtual time,
not measured UART throughput.

The reviewer ran the new board-soak suite: 10 tests, zero skips, OK, 3.022 s.
The unchanged 130-test rig suite was not rerun; no 140-test rerun or clean-tree
proof is claimed. `b2_verify.json` records successful live verification of the
unchanged S1 and pins.

See `docs/b1q_board_transport_soak_review_2026_09_13.md` for six P2 findings and
the HOLD disposition. No physical run, push or ruling is authorized here.

## After the corrections (tool `a435bc64…`, see `results_after_fix.json` for the exact digest)

`results_after_fix.json` is `probe_soak.py` re-run unchanged against the corrected tool with its
pre-fix assertions not evaluated (per this README: they record observed pre-fix behaviour, not
post-fix acceptance). Observed, against the ten pre-fix rows:

| case | before | after |
|---|---|---|
| `ascii_delete` | 0 damaged | **2 mismatches** |
| `extra_hex` | 0 damaged | **2 mismatches** |
| `repeated_wrong` | 0 damaged | 0 mismatches — the **declared blind spot**, now stated in the record rather than implied clean |
| `partial_detach` | exception escaped, no soak.json/entry.json | **exit 2**, the 20 partial bytes in `read_0000.bin`, both counters attempted, `control.json` and `entry.json` written |
| `provenance_failure` | port opened, 4 commands, exit 0 | **exit 2, zero opens**, the diagnostic in `invocation.json` |
| `entry_export_failure` | stdout `export_complete: true` | **`export_complete: false`**, `entry_record: null` |
| `timeout` (`--seconds 0.01`) | ~3.15 s burned, mislabelled `board_disruption` | refused at the reference, elapsed bounded by the exposure |
| `non_ddr_address` | emitted `md.l 0x40000000 0x4` | **exit 3 `window`, zero opens, no command emitted** |
| `positive` / `baseline_export_failure` | exit 0 | exit 0 |

Two harness notes, so the rows are not misread: the acquisition record is now `control.json`
and the first response `reference.bin`, so the probe's `baseline.bin` fault target and its
`soak.json` field extraction no longer match any file — the equivalent faults are covered by
`tests/test_board_transport_soak.py` (`control.json` and `entry.json` export failures), and the
provenance digest is asserted there against this file rather than the rig's.

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

# Independent stage 1 transport rig review

Reviewed `4528ef8` on 2026-09-12. This directory contains offline observations,
not a board session, qualification, transport attribution or authorization.

- `probe_rig.py`: public-API probes with a pristine generated-stream control,
  mutations, deterministic callback/clock traces and production B2 verification.
- `observed.json`: the original output on the reviewed commit. It deliberately
  preserves defective answers so a corrected implementation can be compared.
- `tests.log`: the submitted 30-test suite, independently run, zero skips, OK.

Run `python3 -B evidence/b1q/review_transport_stage1_2026_09_12/probe_rig.py` from
the repository root and direct new output to a separate location. The script
opens no serial device and changes no manifest, pin, instrument or ruling. Its
fake counter fd is intercepted by a mock, never passed to ioctl. The original
suite's PTY tests use only software pseudo-terminals.

See [the review](../../../docs/b1q_transport_stage1_review_2026_09_12.md)
for expected corrected behavior and acceptance requirements. No production
implementation was modified by this review.

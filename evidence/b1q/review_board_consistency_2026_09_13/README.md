# Repeated-read consistency review probes

Run `probe_consistency.py` with `PYTHONDONTWRITEBYTECODE=1 python3 -B`.
The script drives the production CLI through the submitted fake-board fixture,
using temporary directories; no real port is opened. One valid control and eight
adverse cases are asserted against the observed pre-fix behavior. These
assertions must be interpreted as before/after expectations when reviewing a fix.

`results.json` records stdout, archived outcome fields, exact issued md command
lists, file membership and entry/stdout equality. The reference-export probe
faults the current `reference.bin` name, not the obsolete `baseline.bin` name.

The existing 26-test board suite passed, zero skips, 0.057 seconds. This is a
focused run, not a whole-suite clean-tree proof. `b2_verify.json` records live
verification of the unchanged S1 and 71/105 pins. No physical acquisition or
prior evidence was modified.

See `docs/b1q_board_consistency_review_2026_09_13.md` for the four P2 findings,
HOLD disposition and separate recommendation about the next experiment.

# B3 lifecycle 1 — stop evidence (2026-09-17)

Decision: `docs/b3_lifecycle1_stop_decision_2026_09_17.md`. Containment only: nothing pinned, nothing
rewritten; `evidence/b3/plan_trial_2026_09_17/` and commit `b1b82d0` stay as they are, defects included.

| file | what |
|---|---|
| `regeneration_and_sizing.json` | the committed code (`b3/host/b3_plan.py` at `b1b82d0`) regenerates the trial `prediction.json` byte-identically and the plan equal outside `generated_utc` / `prediction_sha256`; the CLI exits 3 naming primary 2; the two exact p-values (1/512, 93/256); primary 2 sized by the gate's own bootstrap rule at B* = 1 000: N = 53, power 0.909, search cost 159 000 > 30 000 |
| `b3_tests_at_b1b82d0.log` | `python3 -B -m unittest discover -s b3/tests` at `b1b82d0`: 47 tests OK (test_b3_plan: 9) |
| `verify_closing.json` | the B2 S3 verify on the tree after the containment was written |

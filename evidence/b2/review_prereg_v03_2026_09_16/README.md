# Preregistration v0.3 review evidence

Read-only review of `e20705c` on `b2-lifecycle-2`.

The probe compares the draft's declarations with the committed image, lifecycle-1 S1
transition, and post-freeze report.  It also confirms that `prediction.json` is byte-identical
to its parent commit.  It does not alter any lifecycle artifact.

Run from the repository root:

```sh
python3 evidence/b2/review_prereg_v03_2026_09_16/probe.py
```

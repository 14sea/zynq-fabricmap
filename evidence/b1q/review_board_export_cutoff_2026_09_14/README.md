# Offline sixth-review evidence

Target: commit 04d4b86. See
`docs/b1q_board_export_cutoff_review_2026_09_14.md` for the disposition.

- `probe.py`: independent case orchestration through the production CLI, using
  the submitted fake serial/clock adapter. No physical port is opened.
- `results.json`: 16 cases, including clean and individual-fault controls and the
  combined exposure-cutoff / required-raw-export-failure case. Temporary paths
  name isolated test directories which are cleaned after each case.
- `b2_verify.json`: production verification of the unchanged S1 manifest.

Run `python3 -B evidence/b1q/review_board_export_cutoff_2026_09_14/probe.py`
to print fresh observations. The script asserts corrected controls and reports
the remaining contract through `required_export_failure_contract.satisfied`;
script exit 0 means the probe ran, not that the tool passed this review.

The first attempt to run this new probe had an incorrect repository-parent index
and failed before importing or exercising the tool. That probe path was corrected
before the recorded run; no production change was made.

The decisive compound case receives 67 bytes but cannot write read_0000.bin.
It still exits 0 / control / exposure_seconds, while correctly recording the
export error and export_complete false. No new command follows the error.
The review requires the tool-failure exit contract to cover this combination.

## After the correction (tool `37dfad21…`, see `results_after_fix.json` for the exact digest)

`results_after_fix.json` is `probe.py` re-run unchanged against the corrected tool with its
assertions not evaluated (`python3 -O`); the `head` it records is the last commit before the fix,
the tree being modified and uncommitted when it ran, so the tool digest is the binding identifier.
Observed on the sixteen cases, against the pre-fix `results.json`:

| case | before | after |
|---|---|---|
| `partial_cutoff_and_export_failure` (67 bytes, no prompt, exposure expires, `read_0000.bin` fails) | exit 0 / `control` / `exposure_seconds` | **exit 2 / `export` / `tool_error`**, phase `export read_0000.bin`; `terminal.observed` = the `exposure_seconds` cutoff with `cut_short` true and 67 partial bytes; the read `unclassified` / `exposure_cut_short`; 2 commands; compared 0, rate null, all-differ null; `export_complete` false |
| `cutoff_and_export_failure` (silent) | exit 0 / `exposure_seconds` | **exit 2 / `export` / `tool_error`**, `observed.reason` `exposure_seconds` |
| `detach_and_export_failure` | exit 2, both errors | exit 2, the transport error primary, `terminal.export_error` beside it (unchanged) |
| `partial_cutoff`, `exposure_cutoff` alone | exit 0 / `exposure_seconds` | unchanged: exit 0, `export_complete` true, statistics null |
| the five single export faults, `reset_with_prompt`, `injected_command`, `leading_crlf`, the positive and echo controls | as the sixth review verified | unchanged |

The board-control suite is now 48 tests (45 + 3), zero skips; the three transport suites 184;
the pins/gate suites 37; B2 verify unchanged (S1, qualified false, refusal null, manifest
`8699767…`). No physical run, push or ruling is claimed here.

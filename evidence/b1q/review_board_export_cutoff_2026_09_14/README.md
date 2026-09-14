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

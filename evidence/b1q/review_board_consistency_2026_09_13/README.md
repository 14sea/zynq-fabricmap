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

## After the corrections (tool `73447f61…`, see `results_after_fix.json` for the exact digest)

`results_after_fix.json` is `probe_consistency.py` re-run unchanged against the corrected tool
with its pre-fix assertions not evaluated (`python3 -O`; per this README they record observed
pre-fix behaviour, not post-fix acceptance). The `head` it records is the last commit before the
fix — the tree was modified and uncommitted when it ran; the tool digest is the binding
identifier. Its `disk` block reads the pre-fix field names (`reads_done`,
`mismatches_per_100_responses`, `all_observed_responses_differ`), which no longer exist, so those
entries are null there; the same statistics are in `brief` under their new names. Observed,
against the nine pre-fix rows:

| case | before | after |
|---|---|---|
| `positive` | 4 identical, exit 0 | 4 identical, exit 0; `reads_attempted/compared/unclassified` 4/4/0, rate 0.0, `all_compared_responses_differ` false |
| `sync_export` | 5 commands issued, exit 0 | **0 commands, exit 2, stage `export`**, terminal `tool_error` phase `export sync.bin`; `control.json` + `entry.json` written, both counters attempted |
| `reference_export` | 5 commands, exit 0 | **1 command (the reference), exit 2, stage `export`** |
| `read_export` | 5 commands, exit 0 | **2 commands (reference + read 0), exit 2, stage `export`**; read 0's response is classified (identical) and carries `raw_export_error` |
| `injected_command_in_body` | 4 identical, 0 mismatches | **1 mismatch**, 3 identical, `body_delta_bytes` = the injected length, `echo_removed` false |
| `leading_newline` | 4 identical | **1 mismatch**, `first_diff_offset` 0, `body_delta_bytes` 2, grammar invalid |
| `reset_with_prompt` | 1 ordinary mismatch, 4 reads, exit 0 | **`board_reset`, exit 2, 2 commands**, `prompt_followed_the_banner` true, the read record `unclassified`/`board_reset`, bytes in `read_0000.bin` |
| `partial_detach` | rate 0.0 and "all differ" true with nothing compared | exit 2; attempted 1, compared 0, unclassified 1 (`tool_error`); **rate null, `all_compared_responses_differ` null** |
| `exposure_cutoff` | rate 0.0 and "all differ" true with nothing compared | exit 0 `exposure_seconds`; attempted 1, compared 0, unclassified 1 (`exposure_cut_short`); **rate null, all-differ null** |

`entry.json` equals stdout in every case. The board-control suite is now 45 tests (26 + 19 for
the four findings), zero skips; the three transport suites 181; the pins/gate suites 37; B2 verify
unchanged (S1, qualified false, refusal null, manifest `8699767…`). No physical run, push or
ruling is claimed here.

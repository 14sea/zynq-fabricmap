# Board consistency control: seventh-review acceptance

Reviewed commit: `83e9e0b` (on top of `1553036` and `04d4b86`). The tree was clean
and ahead of origin/main by exactly these three commits at review start.
Tool SHA-256:
`37dfad21f75d9377dd03d2c69ce781135934082677bd349a46c034b9e332342e`.

**PASS for the sixth-review P2 correction. Claude may push the three commits
04d4b86, 1553036, and 83e9e0b together.** Claude may additionally archive this
acceptance document and its evidence in one separate commit and include it in
the push; that would be four commits, not three. This permission covers these
review artifacts, not unrelated changes.

The explicit post-loop decision now promotes a failed required read export to
tool_error / export read_NNNN.bin / exit 2 even when the response ends at the
exposure deadline. The original observation remains under terminal.observed;
the read's classification and comparison denominator are unchanged. A primary
transport exception remains primary with the export error alongside it.

Independent validation:

- The board suite passed: 48 tests, zero skips.
- The original sixth-review probe ran unchanged, retaining its 16 positive,
  individual-fault, and combined-fault cases. Its required export contract now
  reports satisfied=true. Additional assertions check the corrected exit/status,
  two-command limit, missing raw file, counter records, disk/stdout agreement,
  port closure, primary transport exception, and preserved classified responses.
- The decisive case retains 67 received bytes in metadata and exposure_seconds
  under observed, with zero compared responses and null comparison statistics.
  Its tool result is now exit 2 / export / tool_error. Cutoff alone still exits 0.
- Production B2 verification returned S1, qualified=false, refusal=null, with
  71 B2 and 105 B1 files verified. The tool digest in the procedure's illustrative
  ruling draft matches the current source bytes.

The evidence is in `evidence/b1q/board_export_cutoff_acceptance_2026_09_14/`.
The user-reported 184 transport tests and 37 pin/gate tests were not independently
rerun as entire groups in this review; no new full-suite proof is claimed.

Unchanged bindings:

- B2 manifest: `8699767744b8f7c1f68a49252acddd91af0e9d1732a0a772476fc0f257949b35`.
- Pin table: `8d6f64a5fed1fa222b2c29a0dddac6c6fd3346b23481ade1f00a3f104a907ebf`.
- Frozen preregistration: `68cde86d3f3decaf9775beac94c59731ada486ebe246006e7243156c084db8e0`.

This acceptance closes the reviewed software defect. It is not a physical
consistency result, root-cause attribution, transport stability claim, release
of stop-loss, or authorization for a board run or B2Q. The procedure's ruling
remains an illustrative draft. No production code, frozen input, image, or ruling
was changed by this review. No commit, push, or port access was performed.

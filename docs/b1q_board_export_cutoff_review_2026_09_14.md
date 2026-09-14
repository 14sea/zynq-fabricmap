# Board consistency control: sixth review

Reviewed commit: `04d4b865ed2d95986e390ac4d916eba4eda4300d`.
Tool: `host/board_transport_soak.py`, SHA-256
`73447f6172aff650fd697d10e8d24cb600bfce7fe97ad281f2fea104991e843e`.

Disposition: **HOLD for one remaining P2; defer push of this correction as an
accepted tool revision.** The original four single-fault findings are addressed.
This review does not authorize hardware access, a ruling, B2Q, or release of the
transport stop-loss. No production files were changed during this review.

## Verified corrections

The submitted board suite independently ran: 45 tests, zero skips, OK.
The separate CLI probe in `evidence/b1q/review_board_export_cutoff_2026_09_14/`
exercises 16 cases with the submitted fake serial/clock adapter and the production
CLI. It does not replace acquisition, comparison, export, or finalization logic.

- Each required export failure by itself stops at the expected md.l command count:
  sync.bin: 0; reference.bin: 1; reference.json: 1; read_0000.bin: 2;
  read_0001.bin: 3. Each reports exit 2, stage export, and tool_error.
- Clean replies with and without the declared leading echo remain identical.
  A leading CRLF or injected command inside the data now produces a mismatch.
- A boot banner followed by a prompt produces board_reset after two commands;
  no subsequent read is sent.
- Detach and exposure-cutoff responses are unclassified, with zero compared
  responses and null comparison statistics. Detach plus export failure retains
  both errors and returns exit 2.
- Every probe case closes the fake port once and writes entry.json equal to
  stdout. These are offline observations, not physical-port evidence.

## P2: exposure cutoff still masks a mandatory export failure in the exit status

Location: `host/board_transport_soak.py`, the missing-prompt branch at lines
559–578 and exit selection at line 617 (line numbers refer to the reviewed file).

Starting from a valid sync and reference, the first repeated read receives 67
bytes without its trailing prompt. The 0.12-second exposure then expires.
Independently fail the write of `read_0000.bin`.

| Observation | Cutoff alone | Cutoff plus mandatory export failure |
| --- | --- | --- |
| md.l commands | 2 | 2 |
| received bytes in the read | 67 | 67 |
| compared responses | 0 | 0 |
| exit | 0 | **0** |
| stage | control | **control** |
| terminal | exposure_seconds | **exposure_seconds** |
| export_complete | true | false |

The second case records the write error in the read and terminal and preserves
metadata. It does stop issuing commands. The defect is narrower than the original
continued-acquisition issue: a required raw artifact is absent, but automation
receives a normal-exposure exit status. The same result occurs for a silent cutoff.

The missing-prompt branch adds `terminal.export_error` then breaks before the
successful-response branch's `read_export` handling. Exit selection consults only
`terminal.reason`, so the recorded export failure cannot change exit 0.

Required correction: keep the read unclassified and retain the observed cutoff,
partial byte count, comparison denominator, and export error; report the failed
mandatory export as a tool failure (exit 2, stage export, terminal tool_error with
the named file). Do not turn the cutoff into a mismatch or infer a board reset.
Preserve existing primary transport errors when they coexist with an export error.
Use an explicit terminal-status decision; a blanket exception conversion does not
address this branch.

Acceptance should cover cutoff alone, required export failure alone, and both
together, including a nonempty partial response. Assert command count, absent raw
file, retained metadata/counter attempts, terminal, CLI exit, and disk/stdout
agreement. The current probe reports the unmet contract without asserting that
the defective exit status must remain unchanged.

## Frozen state

Production `b2_manifest.py verify` independently returned S1, qualified false,
refusal null, and verified 71 B2 / 105 B1 pins. Manifest SHA-256 remains
`8699767744b8f7c1f68a49252acddd91af0e9d1732a0a772476fc0f257949b35`;
pin-table SHA-256 remains
`8d6f64a5fed1fa222b2c29a0dddac6c6fd3346b23481ade1f00a3f104a907ebf`.
No full-suite proof is claimed by this review. The user-reported 181 transport
tests and 37 pin/gate tests were not rerun as such.

The new review files are left for Claude to archive using the established workflow.
No commit, push, serial-port access, image change, manifest change, or ruling was
performed by this review.

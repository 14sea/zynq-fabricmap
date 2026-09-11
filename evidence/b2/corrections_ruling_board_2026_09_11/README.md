# The ruling's board authority — corrected, 2026-09-11

The owner's ruling-board review (`docs/b2_ruling_board_review_2026_09_11.md`, against `39125fb`)
accepted the identity/inputs, archive-decoding and final-summary corrections and left one P2: the
expected board was never established, so two rulings agreeing on the WRONG board passed.

`review_probe_after.json` is that review's own `probe_ruling_board.py`, **unchanged**, re-run on
the corrected code. Its closing assertions expect the pre-correction answers
(`assert not result[label + '_both_wrong']`), so the script exits non-zero — after reporting:

| the review's case | before | now |
|---|---|---|
| the S0/S1 manifest's `board` | absent | `{"boardid": "17A6", "role": "verify", "part": "xc7z010clg400-1", "idcode": "0x13722093"}` from the validated lineage |
| the producer and offline plans' expected board | absent from both | `binding.boardid = "17A6"` in both |
| both archives name `17A6` | zero findings | zero findings (the control) |
| only the whole-of-run names `FFFF` | different-boards finding | that, **plus** `names board 'FFFF', this stage is '17A6'` |
| **both archives name `FFFF`** | **zero findings** | **two findings**, one per archive |
| both archives carry the same non-empty ARRAY | zero findings | two findings: `boardid ["FFFF"] is not a non-empty string` |
| the read-only preflight with two `FFFF` rulings | accepted | `ruling names board 'FFFF', this stage is '17A6'` |

## How it was corrected

The board is a **frozen input**, established from the reviewed scope's validated lineage and
never derived from a ruling:

- `b2_manifest.board_from_lineage` takes it from the B1 manifest the lineage pins, and
  `init` records it. The manifest schema migrates **0.2.2 → 0.2.3**.
- `b2_manifest.check_board` requires a present, well-formed `boardid`; **absence is a refusal,
  not permission to skip the comparison**. `_check_frozen_inputs` calls it on every `verify` and
  additionally requires it to equal the validated lineage's, so a manifest cannot be re-scoped to
  another board without the lineage agreeing.
- The runner establishes it **before any ruling is read**; `parse_ruling` refuses when the
  manifest declares none, instead of silently skipping; both the producer session plan and
  `qualification_session_plan` carry it in their binding, so the producer/offline consistency
  check compares it like every other bound field; and `archived_ruling_findings` requires it,
  names a session that declares none, checks each archive's `boardid` type and domain, and
  compares each archive with the authority as well as with the other.

## Still not done

**There is still no modelled B2/B2Q session.** The complete offline S1 → B2Q → S2 → S3 →
fresh-process verification remains the next deliverable, and this runner has never produced a
PASS.

## Tests

50 runner tests (was 46), **B2/B3 381, zero skips**: the correct pair, one wrong board, both the
same wrong board, six malformed boardid values, a session declaring no authority, a manifest with
no board and with five malformed ones, and a live ruling naming the wrong board — for **both**
profiles. Reverting only `host/b2_runner.py` and `host/b2_manifest.py` fails or errors 10 cases.

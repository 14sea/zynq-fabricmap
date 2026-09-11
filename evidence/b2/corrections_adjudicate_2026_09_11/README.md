# The adjudicator's two P2 corrections — acceptance, 2026-09-11

The owner's adjudicator review (`docs/b2_adjudicate_review_2026_09_11.md`, against `1b39951`)
held the commit on two P2s. Both are corrected; this directory is the acceptance.

`review_counterexamples_after.json` is the owner's own `reproduce_adjudicate.py`, **unchanged**,
re-run on the corrected module with **common validation enabled** (its `common_validation: true`).
Every case that raised now returns a named result, and the two baseline mutations are refused:

| the review's case | before | now |
|---|---|---|
| positive control | PASS | PASS |
| session log replaced by an array | `AttributeError` | REFUSED — a session log is list, not a JSON object |
| `seq=[]` / `seq={}` | `TypeError` | HOLD — record 3 carries seq …, which is not an integer |
| `loop_records=7` | `TypeError` | HOLD — loop_records is int, not an array |
| plan `map=null` / `pairs="3"` | `TypeError` | REFUSED — the plan's map carries no sha256 string / pairs is not a positive integer |
| prediction `pairs` missing / null | `KeyError` / `TypeError` | REFUSED — the prediction carries no array of pairs |
| prediction pair `runs=null` | `AttributeError` | REFUSED — pair 0 carries no A and B run objects |
| wrong state digest (negative control) | HOLD, no primary | unchanged |
| **opening baseline genome ≠ blank** | **PASS with a primary** | **HOLD — the opening baseline's genome is …, not the blank genome**; no primary |
| **closing baseline genome ≠ blank** | **PASS with a primary** | **HOLD — the closing baseline's genome is …, not the blank genome**; no primary |
| a contradiction before a malformed seq | raised, losing the contradiction | **KILL** naming the additive contradiction, with the shape finding kept |
| the CLI with a malformed seq and `--out` | traceback, no file written | exit 1, empty stderr, **result file written** |

## How each was corrected

1. **Shapes are established before each dependent operation**, not by a blanket exception
   handler: `check_plan` / `check_prediction` validate every plan and prediction value this
   module consumes; `structure_findings` requires an array of record objects with integer
   seqs; the readout map is keyed by the record's **position**, so a wire value is never a
   dictionary key. The stateful replay does not run at all over a session the record layer
   refused (the result says so under `replay.not_run`) — but the measurement pass, which is
   per record and independent, still runs, so a served readout contradicting its self-report
   is never hidden by a shape finding elsewhere in the log. The CLI keeps a last-resort net
   that writes the result file and labels the outcome **INTERNAL ERROR** with a traceback —
   deliberately not "REFUSED", so a defect in this module is never presented as an input
   refusal (exit code 3, distinct from a verdict).
2. **Both brackets must carry the blank genome**, checked in `Replay._session` — where the
   zero-genome starting population is assumed and where the firmware's `genome_clear()` at
   `b2_orch.c:109` and `:154` is the contract. Either bracket failing is a divergence, so the
   replay stops and no prediction comparison or primary is claimed.

## Tests and discrimination

57 adjudicator tests (was 41), including the owner's whole counterexample table through the
public API, the mixed contradiction/malformed case, three CLI cases, and the two baseline
mutations **with common validation enabled** on records wrapped in the twin's real rel-v4
envelopes (plus wrapped whole-run and split-run controls). Reverting only
`host/b2_adjudicate.py` to `1b39951` makes 37 of those sub-cases fail across 16 test methods.

The full-size demonstration was regenerated with the corrected module: PASS, 10 818 records
replayed, sequence digest `0b81b343…`, p = 0.01953125; the one-word tamper still gives a KILL
with no primary. The model stands in for a board there; it is not silicon evidence, and the
4 + 4 + 1 partition is an illustrative planning scenario — the plan's split is UNDETERMINED
until B2Q (the review's P3, corrected in that directory's README and generator).

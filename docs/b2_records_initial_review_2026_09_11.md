# B2 record validator — initial review, 2026-09-11

Commit inspected: `aced53225ccc0f8b18683404bdae58cc8b3f7636` (`host/b2_records.py`
and its tests). This commit appeared while the runtime freshness correction was being
verified. The following is a bounded initial review, not clearance of the new validator
or a replacement for the complete §7 review.

## P2: B2 extension types are incompletely validated

`record_findings()` checks the search block's key names, then uses some values before
checking their types. At `host/b2_records.py:182`, a string pair index raises `TypeError`
during the range comparison. At line 191, scalar population elements raise `TypeError`
during `sorted(p)`. Population entries are checked only for their key names; the `born`
and `fit` value types are unchecked. Search records never require `selected` to be Boolean.

The independent probe uses the native twin's actual wire `REC`, which passes the
instrument's common validator and, unmodified, the new `record_findings()` function.
Only the named B2 extension value is altered in each fixture:

| Mutation | Common validator | B2 `record_findings()` |
|---|---|---|
| None, positive control | ACCEPTED | No findings |
| `search.pair = "0"` | ACCEPTED | Uncaught `TypeError` |
| `search.population = [0,0,0,0]` | ACCEPTED | Uncaught `TypeError` |
| Four population entries with `born = "invalid"`, `fit = {}` | ACCEPTED | **No findings** |
| `search.selected = "invalid"` | ACCEPTED | **No findings** |

The exceptions break the API's promise to return named findings for invalid records.
The accepted cases leave malformed B2 fields for downstream consumers, even though
this module is specifically responsible for extensions the common validator ignores.
These are shape/type checks; correcting them does not require search replay or fitness
recomputation, which remain the adjudicator's responsibility.

Validate the nested B2 value types before comparisons, indexing, sorting, set creation
or state updates. Require population entries to be objects with typed `born`/`fit`
values and `selected` to be a Boolean. Distinguish JSON booleans from integer fields.
Return named findings for malformed JSON values rather than raising incidental Python
exceptions. Apply the same ordering to the other B2 fields and identity inputs, and add
negative fixtures alongside the accepted real-wire baseline.

The probe and output are under `evidence/b2/review_runtime_live_2026_09_11/` as
`reproduce_record_types.py` and `record_types.json`. It builds only the native host twin;
it performs no ARM image build or board contact. No verdict is claimed here about full
session replay, transport collection or the unfinished adjudicator.

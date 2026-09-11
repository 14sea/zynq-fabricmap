# B2 record types — correction review, 2026-09-11

Reviewed HEAD: `45791a74ff9376336d61440424097f42e12a95d0`, 24 commits ahead of
`origin/main` (`b951b80`). The working tree was clean throughout the independent test
run; review documents and outputs were added afterwards.

**The extension-type P2 is closed.** The correction passes this review. One nonblocking
P3 remains in digest syntax validation. There is no review objection to pushing this
host-work batch and continuing the adjudicator implementation. This review performs no
push and does not clear the complete image package, freeze, B2Q or board execution.

## 1. Type checks precede unsafe uses

The exact search-block key check precedes `block_type_findings()`. Its early return
prevents invalid scalar, move and population values from reaching seed indexing,
set construction or counter updates. Integer fields reject JSON booleans. Nullable
fields are typed before the search-versus-holdout shape rules apply.

The identity type check covers the values used in arithmetic and context binding.
Missing fields still produce presence or binding findings. The additional experiment
bound check prevents indexing beyond the derived seed list for an inconsistent slice.
Malformed top-level documents and record containers return findings through the public
validation entry points. This conclusion concerns JSON inputs and the trusted context;
it is not a claim that arbitrary Python objects are supported.

## 2. Independent verification

| Check | Result |
|---|---|
| Original, unchanged `reproduce_record_types.py` | Actual wire REC accepted; all four mutations produce named findings |
| Independent mutation matrix | 330/330 negative cases rejected without exceptions |
| State preservation | Wrong-type and missing-key REC cases leave the supplied, populated counter state unchanged |
| B2/B3 focused suite | 243 tests, zero skips, OK; 306.856 seconds |
| Current build and image verification | No findings; source inventory, fresh compiler dependencies, compiler identity and both binary/ELF records match |
| B1 / instrument | B1 pins verify; manifest unchanged; instrument clean at `689dde1` |

The mutation matrix declares its own field inventory rather than importing the
validator's predicate tables. It covers scalar types, booleans, missing fields,
nested move/population types, and malformed documents with common validation both
enabled and disabled. Positive controls use the native twin's IDENT and REC. These
are separate codec fixtures: IDENT declares budget 600, while the REC fixture uses
budget 4. Each is checked against its corresponding context; they are not presented
as a coherent measured session or replay evidence.

The independently checked image remains
`d164cd1d5b30aa5eb91f230b1373be8dda60d219249924e280957b26348d85f5`
(114,708 bytes); ELF remains
`7de96ed25e01199ad4405dcc59b2ec92140c27679710e6acfbbad158e4986cdc`.
The recorded build source is `6cfa856`; no ARM rebuild was performed. The full-repository
1694-test result is the submitter's report, not an independently repeated run in this review.

## 3. P3: a trailing newline passes the digest format check

`host/b2_records.py` defines `HEX64` using `^[0-9a-f]{64}$` and checks the state digest
with `match()`. Python's `$` also matches immediately before a final newline.

Appending one newline to the native twin's valid `search.state_sha256` produces a
65-character value. Both common validation and `record_findings()` still accept it
with no findings. This violates the stated 64-hex format; it does not demonstrate a
replay or qualification bypass, because those B2 consumers are not implemented yet.

Use a full-string match and add a negative case for the trailing newline, alongside
the accepted 64-character digest. The upcoming adjudicator must compare the exact
commitment to the state reconstructed from measured readouts, independently of this
syntax check. This small host-only correction requires no replacement firmware image.

## 4. Scope and next step

The observed type failures are closed; the available shape/order tests pass. Fitness,
selection, population and commitment correctness still require the planned measured-readout
replay. `b2_adjudicate`, `b2_runner`, `b2_pins` and `b2_test_report` remain absent, so
this is not final compatibility clearance under package §7.

Reproducers and captured outputs are in
[`evidence/b2/review_records_types_2026_09_11/`](../evidence/b2/review_records_types_2026_09_11/).
Production code, firmware, existing session evidence, instrument and rulings were not
edited. No commit, push or board contact was performed.

# state_sha256 — the P3 correction's acceptance, 2026-09-11

The owner's record-type correction review (`docs/b2_records_types_review_2026_09_11.md`,
against `45791a7`) closed the extension-type P2 and left one nonblocking P3: `HEX64` was
`^[0-9a-f]{64}$` checked with `match()`, and Python's `$` also matches immediately before a
final newline, so a 65-character `state_sha256` ending in a newline was accepted.

Corrected in `9422ae0`: the pattern drops its anchors and is matched with `fullmatch()`.

Both reproducers below are the owner's own, unchanged, re-run at `9422ae0`:

- `type_matrix_after.json` — `review_records_types_2026_09_11/reproduce_types.py`. Its head
  field records `9422ae0`. The IDENT and REC positive controls are still accepted with no
  findings, its **330 negative cases are still all refused** with no exceptions, and its
  trailing-newline probe — the P3 itself — now reports
  `record 2: state_sha256 is not 64 hex` while the common validator still accepts the
  65-character value.
- `record_types_after.json` — `review_runtime_live_2026_09_11/reproduce_record_types.py`,
  the original extension-type probe: the twin's real record still accepted, its four
  mutations still named.

Suite: 245 B2/B3 tests, zero skips (was 243). Discrimination: reverting only
`host/b2_records.py` to `86149e7` leaves exactly the two new digest tests failing, and only
on the newline sub-case — the other six (a leading newline, a trailing space, 65 and 63
characters, upper-case hex, an embedded newline) were already refused by the old pattern,
which is what makes the trailing newline the finding.

A syntax check is not a commitment check: the adjudicator must still compare this digest
against the state rebuilt from measured readouts.

Host-only. Native twin build only; no ARM image build, no firmware, evidence, instrument,
ruling or board contact.

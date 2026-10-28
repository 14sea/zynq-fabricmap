# The approved follow-up applied here (2026-10-28)

The owner's package (this directory's parent, 34 checksums OK on arrival and after copying) ruled a conditional PASS on
`315f6935` with one P2 and supplied the exact two-file fix `owner_followup.patch` (sha256 `34958c56…`). Applied unchanged with
`git apply` on the clean tip `315f6935` (the two files' `before` hashes equal the package's); committed alone as `bd7cef03031a2b6c2d976a68bac70aaa0e934bf8`.

| check (run here, on this tree) | result | file |
|---|---|---|
| `verify_approved_followup.py .` — the two repaired hashes, IMPORT 59 + 37, no other runtime path touched, whitespace, the image unchanged | exit 0, `approved_followup_matches: true` | `verify_approved_followup.json` |
| `focused_followup_tests.py .` — the four `StateMachineRound3` tests on the retained runner fixtures (the owner's driver, the module's setup replaced by the retained archives) | Ran 4, OK | `focused_followup_tests.txt` |
| `check_followup_archives.py .` — a fresh verifier process on each of the 47 retained runner archives | 47 / 47 agree, 0 bad | `followup_archive_checks.json` / `.txt` |

Repaired hashes: `host/b4q_verify_runner.py` `f1ebd9e37a8ee76918031abd380ffe60ad2f51fed31c401db5e842870cc2e3b0`,
`tests/test_b4q_runner.py` `b5082b3d5d1f583fc35932e202eecdafb0168c2d8f328ebaada330ba032e3645`. Image `4d989ee8…` unchanged.

Not run here, per the ruling: the full suite, the battery, an image rebuild, a full evidence re-assembly. The runs of record in the
unit's README §2 stay tied to `bcfc6fbf` (126 tests on the submitted tree); this is four focused tests plus 47 fresh archive agrees on
the approved candidate — not a 127-test run.

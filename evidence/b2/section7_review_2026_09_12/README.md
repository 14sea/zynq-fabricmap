# B2 Section 7 review evidence

Reviewed checkout: `9fa8a7a`; submitted implementation: `619b22b`.

- `review_section7.py`: read-only artifact/build checks, 22 shared-function
  comparisons, actual B2 allowlists versus B1 RTL, an in-memory production S0
  init/verify, C B2Q orchestration against explicit pinned seeds, and report binding.
- `verification.json`: results, live initial snapshot and the S0 review preview.
  The embedded preview is **not an installed or frozen manifest** and is not a ruling.
- `guards.log`: independent targeted suite, 91 tests, zero skips, OK.

Reproduce after building only the native twin if it is absent:

```sh
make -s -C firmware/b2 twin
python3 -B evidence/b2/section7_review_2026_09_12/review_section7.py
PYTHONPATH=host:tests python3 -B -m unittest test_b2_build_evidence test_b2_leakage test_b2_hostapp test_b2_wire test_b2_twin test_b2_session
```

Run from the repository root. `-B` prevents bytecode files under evidence. The C
orchestrator receives modelled fabric readout; it does not contact a board. The
review's initial exploratory call used the wrong reference keyword `seeds`; the
actual API keyword is `pair_seeds`, corrected before the saved successful comparison.

No ARM binary/ELF rebuild, live manifest write, freeze, board access, ruling issuance,
consumption or push was performed. The initial snapshot was captured before these
review files made the checkout dirty. The full submitted 1,895-test run was not
repeated; verification of its metadata is distinct from independent execution.

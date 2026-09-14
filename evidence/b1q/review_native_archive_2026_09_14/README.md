# Native acquisition archive checks

`verify_archive.py` is a read-only local verifier. It regenerates source and
host traffic, checks all capture hashes and event byte accounting, consumes
exact host echoes with multiplicity, independently compares source lines and
verifies each contiguous deletion and its byte-exact successor. No serial port
or remote host is accessed. Run with `PYTHONDONTWRITEBYTECODE=1 python3 -B`.

`results.json` records PASS archive consistency at HEAD 7815c8a, all four native
acquisitions and five reproduced deletions. `b2_verify.json` records unchanged
S1 and pin verification. These checks establish local consistency, not remote
transfer authentication, physical topology, transport stability or a new
whole-suite clean-tree proof.

The full review and exact push scope are in
`docs/b1q_native_archive_review_2026_09_14.md`. Four P2s in the separate board
consistency tool remain open.

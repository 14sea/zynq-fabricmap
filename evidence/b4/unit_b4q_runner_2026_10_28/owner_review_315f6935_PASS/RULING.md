# Owner ruling — 315f6935 — approved follow-up, then closure

**Conditional engineering PASS.** R1's fixed role floor and R2's selected-PLL eligibility/command order repairs are accepted within the checked host-only scope. Bare `315f6935` retains one P2 receive-prefix boundary error. The owner has implemented and independently verified the exact two-file follow-up supplied here; acceptance attaches to its repaired hashes, not to the unpatched tip.

Authorise the implementing side to:

1. Apply `owner_followup.patch` unchanged to the reviewed source (315f6935, or a documentation-only descendant retaining the same input hashes). Only `host/b4q_verify_runner.py` and `tests/test_b4q_runner.py` change in code/tests.
2. Run `verify_approved_followup.py <repo-root>` from this package and retain its successful output. Its repaired-file hashes are in `approved_file_hashes.json`; the owner already ran the focused tests and all 47 retained runner archives against these exact bytes. No unchanged full suite, battery, image rebuild or full evidence assembly is required merely to repeat that validation.
3. Archive this review package and complete the routine documentation/closure update locally. Align active descriptions in the audit/plan with the earlier-of-command-echo-or-data-reply boundary; preserve old results as historical, with a follow-up note. State the actual validation: original tree 126 tests OK; approved follow-up four focused tests OK plus 47/47 fresh archive agrees. Do not claim a full 127-test rerun.

Once these exact conditions hold, **the runner host-only engineering unit may close without another owner review round**. No new proposal, fixed date, branch name, commit count or per-edit approval is required. A different implementation is outside this exact-byte acceptance and cannot be reported as this approved follow-up.

This is not a gate result, physical provenance, hardware qualification, satisfaction of P4–P6, or a freeze of 2c. It does not authorise board/serial/SSH contact, power/provisioning, physical load/go/PCAP, production keys/seeds, scientific-method changes, push/merge, or another undertaking. The image/firmware, carrier, protected production archives and no-go results remain unchanged.

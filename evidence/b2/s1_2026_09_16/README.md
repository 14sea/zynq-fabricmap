# B2 lifecycle 2 — S1 freeze — 2026-09-16

The owner explicitly authorised §8a step 6 in conversation, naming the preregistration
digest. The production CLI executed it once at 2026-09-16T19:42:52Z on the reviewed S0
(`a5e84423…`, step 4, proof `test_report_2026-09-16T193807Z.json`) and the accepted v0.3
preregistration bytes.

- Frozen (S1) manifest SHA-256: `90115453666218a44a4522f3404f612066bf5c79203fab6fec771d8f038933df`
- Preregistration SHA-256 (DRAFT v0.3): `fa401221d20869c2dc9f77bbf12f4c2ab92efee9bd15c287f3109d501161fccf`
- Pin table SHA-256: `82a5f2fb1d246c9cab506df65d53a0f329ca219ec3c5cdf50a272ff79ee319d1`
- Image SHA-256: `d164cd1d5b30aa5eb91f230b1373be8dda60d219249924e280957b26348d85f5` (114 708 bytes, ELF `7de96ed2…`)

Production `verify` passes before (S0) and after (S1) in fresh processes, rechecking the
image bytes, the B1 lineage, the canonical B2Q inputs and 71 B2 / 105 B1 pins
(`verify_before.json`, `verify_after.json`). The transition changed exactly
`prereg.sha256`, `prereg.frozen`, `image.board_ready`, `status` and the S1 `history` entry
(`transition.json`, computed from the manifest bytes before and after). Qualification stays
false; qualification, calibration and plan stay null.

`transition.json` records the actual resulting binding, not a preview. The lifecycle-1 S1
(`86997677…`, `evidence/b2/s1_2026_09_13/`) is a different identity and is not an input here
(preregistration §8a).

Not done by this transition: the post-freeze clean-tree proof (§8a step 7 — its report's
artifact snapshot must name `90115453…`), the B2Q ruling pair (step 8), any board or port
access, any push. Each is its own authorised unit.

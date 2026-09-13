# B2 S1 freeze — 2026-09-13

The user explicitly instructed S1 freeze. The production CLI executed it at
2026-09-13T05:16:15Z, using the reviewed S0 and current preregistration bytes.

- Frozen manifest SHA-256: `8699767744b8f7c1f68a49252acddd91af0e9d1732a0a772476fc0f257949b35`
- Preregistration SHA-256: `68cde86d3f3decaf9775beac94c59731ada486ebe246006e7243156c084db8e0`
- Pin table SHA-256: `8d6f64a5fed1fa222b2c29a0dddac6c6fd3346b23481ade1f00a3f104a907ebf`
- Image SHA-256: `d164cd1d5b30aa5eb91f230b1373be8dda60d219249924e280957b26348d85f5`

Production verify passes before (S0) and after (S1), rechecking image bytes,
B1 lineage, canonical B2Q inputs and 71 B2 / 105 B1 pins. The transition changes
only prereg.sha256, prereg.frozen, image.board_ready, status and the S1 history
entry. Qualification remains false; qualification, calibration and plan remain null.

`transition.json` records the actual resulting binding, not a preview hash.
`verify_before.json` and `verify_after.json` retain the independent verification.
The post-freeze whole-suite clean-tree report will be generated after this
transition is committed, and recorded in a subsequent evidence commit.

No firmware, image, pinned input, instrument or ruling was changed. No board
or physical serial access occurred. This state transition does not lift the
transport stop-loss, complete physical transport acceptance or authorize B2Q.

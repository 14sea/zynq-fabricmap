# B2 pin-table correction acceptance — 2026-09-12

Reviewed HEAD: `23b1dfd`, twenty-one commits ahead of `origin/main` (`0d294ea`).

**Both P2 findings from the pin-table review are CLOSED.** No additional blocking
defect was reproduced within this correction's scope. Continue with `b2_test_report`
and the complete package review. This correction acceptance grants no push, freeze,
qualification or board clearance.

Independent focused suite: **402 tests, zero skips, OK in 493.115 seconds**.
Review artifacts were written while the suite ran; this is not a full-repository
clean-tree test report.

## Independent acceptance

Both previous review scripts were rerun unchanged. Their valid controls still pass:
the mirrored S1 manifest, native application harness build/startup, real pin verification,
read-only preflight, model CLI and genuine qualification re-adjudication.

| Check | Result |
|---|---|
| Previously omitted local BSP and hostapp files | None omitted; all twelve are in the table |
| Original source/script/header mutations | Named REFUSED through pins and fresh-process manifest verification |
| Already-pinned source/test mutations and an unlisted new glob member | Still REFUSED |
| Non-object pin block: string, array, boolean and number | Named REFUSED through pins, lifecycle and CLI |
| Missing and empty pin blocks | Still named REFUSED |
| CLI error contract for those malformed blocks | Exit 2, `REFUSED:`, no traceback |
| Actual B2 pins / underlying B1 pins | 69 / 105 verified |
| Real pins hook in read-only B2Q preflight | Accepted; no evidence directory created |
| Model CLI | Exit 0; verdict, adjudication file and final summary all PASS |
| Real `qualify` over that CLI's output | Accepted, with real `readjudicator` |

Preflight doubles only principal-boundary validation and `sb` discovery. It uses real
pins, manifest, image/build, instrument and B1-chain checks. The model substitutes for
the board; no replay or stored-verdict double supplies its successful qualification.

An additional independent matrix covers **each of the twelve previously omitted files**,
once with changed bytes and once deleted: **24 cases**. Every case is refused by both
the pin verifier and a fresh-process manifest verifier, with the specific path named.
The valid mirror passes before and after the matrix. Manifest and table bytes remain
unchanged throughout; each temporary input is restored before the next case. No cache
is cleared between calls to the pin verifier.

## Code assessment

The five added glob patterns cover the actual native harness source, build script and
stub headers, plus the local BSP source and headers. The committed table contains
all twelve inputs, so the existing per-file hash/existence checks now protect them.
The table digest is
`fd3c73e6be4d6247eb921cc02c4446d6fdf67b5b7afcad0deaeba4c27d5577e5`.

The new guard establishes that the manifest is an object, the `instrument_pins` block
is an object, and its digest is exactly 64 lowercase hexadecimal characters before
using it. Invalid inputs raise `PinRefusal`; the existing lifecycle/runner adapters
translate that expected refusal. No broad exception handler disguises program defects.

The six pin tests include explicit dependency-path expectations, malformed block and
manifest inputs, and public lifecycle/CLI checks. The independent twelve-file matrix
adds exhaustive change/deletion coverage for this finding's dependency set.

## Preserved inputs and remaining work

Live build verification returns zero findings. Image `d164cd1d…` (114,708 bytes),
ELF `7de96ed2…`, and B1 manifest `38238271…fd4ba8` retain their hashes. All 105 B1 pins
verify. The modelled qualification's calibration remains 4490.856163729762/h with
two planned sessions and at most seven pairs per session; it is not a silicon rate
measurement or a real qualification.

The previous representative B2 non-first-slice demonstration remains accepted:
2,406 scored/audited records for pairs 7 and 8, with a session PASS and no pooled
primary. Do not repeat it just to close that same item. It does not establish a full
nine-pair instrument-stack run.

The nonblocking documentation drift noted in the previous review remains in the
runner module's `WHAT IS NOT DONE HERE` text: it still says pins do not exist,
explicit B2Q seeds are unsupported, and no positive lifecycle/PASS exists. Correct
that current-source description alongside the remaining host-tool work, before
regenerating pins. The current package banner supersedes the historical status banners.

Artifacts: [independent acceptance outputs and matrix](../evidence/b2/review_pins_acceptance_2026_09_12/).
Only English review artifacts and the package status banner were written. No production
code, firmware, image, original evidence, manifest, real ruling or instrument file was
changed. No commit, push, ARM rebuild, port access or board action was performed.

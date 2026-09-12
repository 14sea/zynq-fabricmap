# B2 Section 7 package and image compatibility review — 2026-09-12

**PASS within Section 7's static compatibility and offline verification scope. No
new blocking implementation finding was reproduced.** This accepts image
`d164cd1d…` against the unchanged qualified B1 carrier. The documentation corrections
below should land before freeze; this review does not perform or authorize a freeze,
set `board_ready`, issue rulings, resolve transport stop-loss, or authorize board time.

Reviewed checkout: `9fa8a7a10643bfbf0f97a03c5b756690201d2400`, initially clean,
two local report/submission commits beyond `origin/main`. Submitted implementation:
`619b22b9b4cc2a8684f38141eb7504d18f86ba63`. No production source, manifest, firmware,
image, pin table, ruling or instrument bytes were changed in this review.

## Bindings independently checked

| Artifact | SHA-256 |
|---|---|
| B2 binary, 114,708 bytes | `d164cd1d5b30aa5eb91f230b1373be8dda60d219249924e280957b26348d85f5` |
| B2 ELF | `7de96ed25e01199ad4405dcc59b2ec92140c27679710e6acfbbad158e4986cdc` |
| B2 build evidence | `ce58eaf3cc79db5687e8324e77ec7c814d181e497cbeb069587fb3b66f33af5b` |
| B1 manifest | `38238271510536bda565ad1b8321dd04d75e78e1fe77ef94d2795bf9edfd4ba8` |
| B2 pin table, 71 files | `95256af80d7513396adee7b14235558b5860111b2d288c584ab2906d23a20759` |
| B2Q plan file | `3d194d76e083fd4ba3ce3cf0458af65637120fcda6761be36598833dbc659216` |
| B2Q prediction file | `2ada4d5dab7ed08f081aa55bb4b6f138688a326bb859ab5d63f58c16e67b58aa` |

The instrument is clean at `689dde1dad374536c625bbe2b05986ee89eb4c94`. B1's
105-file pin table and carrier qualification chain reverify. The carrier remains
`d85daef4e3aa1ff925c327e1c1f98465a83d96e79955aca432d664d98aa4f38f`.
The live build verifier returns zero findings, including current named compiler,
runtime objects, dependency graph, headers, sources and output hashes, and agreement
of both recorded binary/ELF builds. No ARM image rebuild was performed here.

## Section 7 compatibility checklist

| Item | Result and evidence |
|---|---|
| Wire contract | PASS. Framing and retransmission remain rel-v4. The deliberate changes are IDENT 1.5.0's search/map/fitness/slice fields and REC 1.3.0's search block and arm. Common-envelope C wire tests pass; B2-specific validation remains the records/replay layer's responsibility. |
| Settle poll | PASS. `settle_condition` and `arm_attempt` are textually identical to B1. Twenty payload words, four tag words, then one CTRL strobe; the bounded STATUS poll waits for neither engine busy and a latched fault/done result. It records first/last status and nonce, without repeating ARM. |
| Audit service | PASS. `audit_word`, `serve_sparse_chunk`, `audit_pull`, transaction and record helpers are unchanged. Link-2 staging and link-3 readback are checked before ARM. Requested audit completes before ARM; an incomplete pull stops the epoch. Existing modelled transport evidence verifies the served staging/readback bytes through the real host audit gate. |
| MMIO versus B1 RTL | PASS. Both B1 RTL allowlist tests were rerun with the actual B2 application and B2 macro definitions. Read offsets exactly match RTL, including VARIANT; the RTL's extra write offsets are only the key window, absent from the application. Runtime read/write accessors reject offsets outside the allowlists. |
| DMA order | PASS. Stage/link-2/write-envelope/readback/link-3 and DMA/wait functions are textually identical to B1. Source address, destination address, source length, destination length are written in that order; PCAP mode and interrupt checks precede submission. Completion uses D_P_DONE; readback is command → frame → cleanup. |
| No ICAPE2 | PASS within static successor-image scope. No new PL or ICAPE2 path is introduced. B2 uses B1's PCAP transactions and unchanged carrier; new search/orchestrator units perform computation, not configuration I/O. |
| No SLCR write | PASS within static successor-image scope. The application only reads `SLCR_PSS_IDCODE`; direct writes target allowed AXI registers, DDR buffers or DEVCFG DMA registers. Console glue uses UART status/FIFO. SCU timer/watchdog and MMU operations remain the inherited BSP paths, not new SLCR writes. |
| Watchdog gating | PASS. Initialization follows successful identity; the page flag gates enablement. Failed lookup/configuration stops without candidates. Prescaler 7, load 1250000035 and watchdog reset mode match B1. `kick_watchdog` is unchanged and gated by started/running state. Host preflight verifies the pinned instrument watchdog settings. |

Twenty-two selected HAL/protocol functions are **textually identical** to B1; their
names and comparison results are recorded in the evidence. The manual review also
covered the changed startup, `run_candidate`, scored bookkeeping and session loop.
Slice decoding precedes IDENT. A non-SCORED candidate terminates the epoch; closing
baseline completion is set only after that baseline has actually been observed.
The offline application harness exercises refusals and startup; it does not execute
the real PL scoring path for the earlier candidates it primes as SCORED.

## Guard coverage and firmware/host integration

Independent targeted suite: **91 tests, zero skips, OK**, covering build evidence,
imports/leakage, actual host application, wire serialization, C/Python search twin
and session orchestration. The two additional MMIO tests above also pass.
This review extends the previous independent **439-test** B2/B3 acceptance at the
same submitted implementation; those tests were not redundantly rerun in full.

The build/dependency and binary guards bind the reviewed executable to its source.
The import, generated-header, compiled-map, seed-exclusion and operator-view guards
pass. Their scope remains explicit: the C twin answers with modelled readout, while
the firmware's actual run path loads readout from PL registers before computing F1.

An additional C orchestrator run used the **pinned B2Q master 505806527**, one pair
at budget 8, and was compared against the Python reference with the explicit pinned
pair `(3890725659, 1378470437)`. All **20 candidate records**, including both baseline
brackets and both champion remeasurements, match in sequence, phase, arm, genome and
search-block bytes. This checks the actual C seed derivation against the new B2Q
contract; it is not merely Python model output compared with another Python run.
It still establishes no silicon result or physical throughput.

The five host tools retain their reviewed division of responsibility. The record
adjudicator establishes measurement/replay consistency; `judge_session` additionally
checks binding, archived authorizations, export seal, instrument/audit closure,
transport limits, epoch and measured timing. `execute` archives before claiming the
ruling and opening the port. No execution path was invoked during this review.

## S0 preview, lifecycle and the submitted report

Production `b2_manifest.init` was called in memory with the actual image build
evidence, followed by production `verify`. Result: **S0**, board 17A6, B1 lineage
reverified, image bytes hashed, B2Q canonical inputs verified, qualified false,
prereg unfrozen and `board_ready` false. The preview is stored only as review data;
**no `manifests/b2_manifest.json` was created**. Its digest is not an S1 ruling binding.

The previously accepted modelled S1 → B2Q → S2 → S3 → fresh-process verification
remains the offline lifecycle evidence. The previous accepted **B2 pairs 7/8** run
also exists: 2,406 records, all scored/audited, session PASS, no pooled primary.
It used the real instrument host stack and runner callback, with modelled board
output. Neither its virtual-clock rate nor the B2Q model's rate is live calibration.

`test_report_2026-09-12T134616Z.json` declares 1,895 tests, zero skips/errors/failures
and OK at `619b22b`. Every artifact entry matches that commit (including the absent
B2 manifest), endpoint snapshots agree except timestamp, and recomputing proof
refusals yields none. The full 1,895-test execution and raw log digest were not
independently reproduced in this review. Historical reports remain unchanged.

## Nonblocking documentation corrections before freeze

1. Submission §2 misidentifies the imports. The three derived files are
   **`b2_app.c`, `b2_wire.c`, `b2_wire.h`**; `p3_data.h` is generated B2 data.
   The ten verbatim files comprise six instrument derivation/transaction files and
   four B1 BSP scaffold files, not ten direct instrument imports.
2. Submission §1's “6 BSP inputs” counts six metadata categories. State the actual
   provenance: **47 translation units, 86 headers and seven runtime objects**, with
   dependency graph/build lists/header roots. “20 sources” includes headers/scripts.
3. Submission §6 and the runner docstring still deny a B2 modelled demonstration.
   Cite the accepted non-first-slice run and distinguish the B2Q-only model CLI from
   that already demonstrated API path; do not require another identical demonstration.
4. The reports README labels both `T102301Z` and `T134616Z` as the current citation.
   Keep the earlier report but mark it superseded for the current submission.
5. Prereg §2 says champion holdout records use `mode_holdout = 1`. The firmware does
   **not** set a separate holdout mode bit: it rewrites/remeasures the champion, gets
   all 64 vectors from the B1 gate and computes holdout F1 from that readout. Correct
   this implementation description before freezing the preregistration bytes.

These do not reproduce an unsafe MMIO path, a prediction mismatch or a false session
PASS in the submitted implementation. The prereg correction must precede its freeze;
do not change an already frozen document later to make the prose match.

## Ruling text review and next boundary

The proposed literal texts match the implemented profile purposes:

- B2: `whole-of-run B2 map utility`
- B2Q: `whole-of-run B2 image qualification and calibration`
- Both provisioning companions: `provisioning P3-K`

They are suitable technical labels and need no rename for this package review.
This is not issuance, a signature, or advance approval of a particular session.
The actual pair still needs the owner's identity/date and the eventual S1 or S3
manifest, board, image, prereg and whole-of-run seed bindings. No live ruling was
created, validated for execution, claimed or consumed here. Transport stop-loss and
the fresh boundary/power-cycle requirements remain outside this offline clearance.

Evidence: [scripts and results](../evidence/b2/section7_review_2026_09_12/README.md).

# B4 — the host-only B4Q observation integration unit (2026-10-27 / 28): the executing side, the PCAP links, the schemas and adapters, the offline end-to-end transaction and the B4Q plan — **resubmitted after the owner's HOLD on `3723b91` (section 9: R1–R5 repaired in this unit)**

**What this unit is.** The one complete engineering unit the owner's disposition of 2026-10-27 opened (section 4; archived here in
`owner_ruling_2026_10_27/`, checksums verified): "an offline end-to-end observation transaction using the executing-side implementation
and the real record / validation path, with a reviewable B4Q qualification plan" — its five deliverables, on the branch
`b4-b4q-integration` from `main` `dd8a7b9` (the merged B4 milestone). The design record is `docs/b4q_integration.md`; the plan is
`docs/b4q_plan.md`. **Nothing physical happened and nothing is claimed about a device**: no board, power, provisioning or PCAP on
silicon; no A2 / A8 on a die; no qualification; no production seed, search or gate; nothing under `b4/host`, `b4/schemas`, `rtl/`,
`vivado/` changed, and under `builds/` only the carrier manifest of record, regenerated from the committed bitstream under the
owner's disposition after the HOLD (`protected_paths.txt` names that one file; section 9); no push, no merge. Delivered once, whole.

## 1. The five deliverables, where they are, how each is held

| deliverable (the ruling's section 4) | what was built | held by |
|---|---|---|
| 1 the executing-side register-sequence implementation and MMIO interface | `firmware/b4q/b4q_tx.{h,c}` — the session opening and the P1–P10 / A5 (J2 / J3) transaction on the accepted carrier v2 register map, through the injected transport `b4q_hal.h` (five calls, nothing else reaches the outside); VARIANT rejection, wait / completion by STATUS and FAULT witnesses (never a bus acknowledgement), the applied-input readback per slot, the P6 seal left to the host, the P9 base-state witness, the close, the A5 context rules; the allowlist checked at the accessor; the key window never touched; the four legal DMA tuples; `b4q_host_main.c` the host driver; `b4q_derive.{h,c}` DERIVED from the instrument's derive unit (verbatim functions held by the digest of each function's text; the 21-bit codec; `IMPORT.json`); the generated write-set / regmap headers; strict-flag host build (`firmware_build.json`); the pure units compile for cortex-a9 (`xcheck.txt`, objects only — **no board image**) | `tests/test_b4q_derive.py` (8: the C ↔ Python parity corpus, the verbatim functions, the generated headers, the stale-manifest fact), `tests/test_b4q_firmware.py` (4: the build, the source audit, **A7 on the program's actual accesses** against the RTL decode and the table; tampers found), the mutant battery |
| 2 the PCAP links 1–3 / session-opening integration against a host backend | `host/b4q_backend.py` — one address space: the carrier window, the DevC with a minimal PCAP fake (submissions recorded; envelopes parsed by the pinned grammar and stored by FAR; readback commands matched; the pad + target frame delivered; fault modes for the negatives), the DDR buffers, the IDCODE; the loaded-image frame reference and the restored-base reference kept apart (two commitments in one hash domain, never compared to each other); every value **symbolic / emulated and labelled so** (`manifest.json: emulated true`), never a physical link proof; `host/b4q_frames.py` the Python twin of the derive (the write set: two envelopes of the column `0x00400a00` from the committed bitstream at `b4_build.json`'s digest) | the e2e; `a7_valid.txt` (the DMA submissions all legal) |
| 3 the explicit schema / adapter and producer wiring | `b4q/schemas/` — six files under the contract's provisional names (O complete / invalid-by-phase, F, X closed / injection_open / faulted, session_open, the model raw trace, the view) with the closed subset validator `host/b4q_schema.py`; `host/b4q_view.py` — the M-raw, M-ledger / M-target / M-memo and C-O adapters into one view with every field tagged R / D / A, digests verified under their declared encodings only, the source from the trusted context; the producer = the executing side + `host/b4q_session.py` building every record **from the register trace** with the accepted `host/b4carrier_records.py` (extended in one place: an absent PCAP-side witness is never written — the carrier unit's 18 record tests unchanged) | `tests/test_b4q_schema.py` (5: every record of the e2e and of the bench under both the file and the code validator; the owner's counterexamples and tampers refused by both), `tests/test_b4q_view.py` (5: the `b4-sim-5` target / ledger records, the `b4-sim-4` null counterexample (36 cells), a model return, a session O; refusals by name) |
| 4 the B4Q plan | `docs/b4q_plan.md` — the limited claim; the identities (the carrier, both frame references, the write set, the hypothesis / certificate, the executing side, the schema versions); the records in order (the root and baselines; A5's *c′*; the two A8 crosses with 6.5's fourteen-step demonstration stimulus and its six sample points; the nine A2 pairs with vectors); the outcomes and stop rules as the contract's rules made executable (`host/b4q_qual.py`); the legal-write / composition authority stated as the owner's question with the build-of-record facts; the timing parameters declared and **none measured**; F8B3 bring-up ≠ 17A6 qualification; the prerequisites P1–P6 | the review |
| 5 the end-to-end evidence | `host/b4q_e2e.py` — sixteen scenarios (eleven at the first delivery, five fail-closed ones after the HOLD), each its own session; `host/b4q_verify.py` — the fresh-process verifier (records rebuilt from the trace and compared to the stored ones; structure / binding / chain; the schema files; the links recomputed from the PCAP log; the executing side's digests and fitness held to the host's; A7; the view; the manifest's references; agreement with the session's own findings as the exit code); the run of record in `e2e/` (section 3) | `tests/test_b4q_session.py` (6), `e2e/*/verify.json` |

## 2. The emulation held to the RTL and to the model (`fidelity.txt`, `fidelity.json`; `tests/test_b4q_emu.py`, 7 tests)

`host/b4q_emu.py` replays the carrier unit's 27 archived bench traces (`evidence/b4/unit_carrier_v2_2026_10_21/bench/`): every write at its
recorded time, every read's data (or x pattern) and response compared — **0 mismatches over 1 884 reads and 2 100 writes**; the three
bus-level scenarios the bench drives by hand (`backpressure`, `w_first`, `w_first_early`) compared up to the first unlogged handshake,
and the report says so. The cycle model: a flip-flop result one cycle after the computing cycle, a LUTRAM result two; the engine sees a
CTRL write one cycle after the bench logs it; the gate's tag 49 cycles after; the event stall held until the sample. Its fabric is the
hypothesis model applied step by step (equal to `observe()` row by row on the six bench fixtures and 60 seeded genomes); the ARM gate is
the instrument's SipHash with the fixture key (VALID / UNSIGNED / WRONG_COMMIT / wrong key / replay / no key as the bench has them). An
element the model gives no value for reads as x and becomes None in the record, which the carrier validator refuses — the D1 rule seen
from the host.

## 3. The end-to-end run of record (`e2e/`; `e2e_run.log`; `e2e/e2e_summary.json`; per scenario `verify.json` / `verify.txt`)

| scenario | outcome | verifier |
|---|---|---|
| `valid` | open; root; three candidates (BASE, CE_SR_ASYNC, SYNC_SRVAL0) with a trusted task: 4 O complete, 4 X closed, 3 F equal to the host's recomputation | **clean**, agree |
| `a5` | J1 / J2 (CLOSE_INJECTION) / J3 (the A5 flag, `pre_init_cleanup`, `predecessor.kind = a5_injection`) / a normal candidate after; the decision table: **pass** (arrived and cleared) | clean, agree |
| `a5_persist` | the same on the hypothesis swap `init_no_effect`: **fail** (arrived and persisted; the positions listed) | clean, agree |
| `a8_cross` | the AFF cross under the demonstration stimulus: row 2 **both demonstrated**; BFF (a bystander): row 5 **neither demonstrated** (a constant restore) — the mechanics of 6.7 on the model | clean, agree |
| `a2_pairs` | `ce_mode` **differs** (its own vectors); `storage_kind` **not assessable** (the latch endpoint's x5FF cells unmodelled: the record refused) | agree (the refused record named) |
| `not_realisable` | a non-uniform `ce` at step 3: O invalid at **P5** (`not_realisable`), prefix retained, no X; the next ARM refused under recovery | agree |
| `wrong_key` | the root's ARM under another key: O invalid at **P1** (`arm_auth`), no X | agree |
| `notary_refuses` / `dma_never` / `interrupt` | the executing side stops (P1 `STOP_SIGN` / P2 `STOP_DMA` / interrupted after 3 000 accesses): **no O** (nothing to seal: no carrier fault, the link incomplete — finding 2 of `docs/b4q_integration.md` §6), the raw result and trace retained | agree |
| `latch_unmodelled` | a latch candidate: the O refused for its None cells | agree |

A7 on every scenario: empty (`a7_valid.txt`: 19 carrier offsets read, the expected writes, the DevC's registers, the three buffers; the
RTL's one write region not touched is the key window). The access logs are kept compressed (`accesses.jsonl.gz`; the verifier reads them).

## 4. The mutant battery (`b4q_mutants.py`, `mutants.txt`)

36 single mutants (13 on the executing side's C, 8 on the session / verifier / record builder / A7, and after the HOLD 15 on the
repair's guards: R1a–e, R2a / R2a2 / R2c, R3a / R3b, R4a / R4b, R5a / R5b) and 8 combined, each one text edit restored byte for
byte, probed by the e2e, the verifier, the tampers and the ten fault probes (a corrupted readback, a refused write, a refused opening,
a dropped / undeclared record, a malformed manifest, an altered conclusion, missing close witnesses, a bad DMA tuple, a float bit);
green baselines first. **31 killed, 13 survived, 0 edit-miss of 44** (the first delivery's log, 17 / 6 / 0 of 23, kept as
`mutants_first_delivery.txt`). Every survivor is named with the check that masks it, and every masked repair guard is killed by the
combined mutant that removes its twin: C9 (the link-2 comparison alone — killed beside a corruption, C9+C10), P2 (the session's
fitness hold alone — killed beside C6, P2+C6), P5 (the applied-vector rule, masked by the declared-step equality), P7 (A7's
key-window line, masked by the allowlist line), C11 (the idle check after CLOSE: equivalent on every available probe), C13 (an ARM
refusal ignored by the executing side: silent by the record layer's authority over the trace, which is the design); R1b / R1b2 / R1c
(the three guards on a refused STEP_IN write: the response, the read-back, the accessor's propagation — R1b+R1b2 and R1c+R1b+R1b2
launch the STEP on the stale word and are killed), R1d (the halt latch, masked by the previous-close rule — R1d+prev killed), R1e (the
opening rule, masked by the halt latch — R1d+R1e killed), R2a2 (a declared directory missing, masked by the per-record file checks —
R2a2+files killed), R5b (the adapter's type check, masked by the schema file validated first — R5a+R5b killed). A redundant guard is
not counted as a tested guard by itself.

## 5. The tests (`tests_b4q.txt`; the B4 battery in `tests_b4_suite.txt`)

The nine suites this unit touches or depends on: `test_b4q_derive` 8, `test_b4q_emu` 7, `test_b4q_schema` 5, `test_b4q_view` 6,
`test_b4q_firmware` 5, `test_b4q_session` 9, `test_b4carrier_records` 18, `test_b4carrier_regmap` 11, `test_b4carrier_benches` 1 (the
iverilog benches) — **70 OK, no skip** (65 at the first delivery; the five added by the repair are named in section 9). The frozen B4 battery (`b4/tests`, 332 tests) unchanged and green (section 5's file; `b4/` is
byte-identical to `main`, `import_check.txt` 59 entries equal).

## 6. Findings for the owner (not repaired here; `docs/b4q_integration.md` §6)

1. **The carrier manifest of record is stale**: `builds/b4/b4_carrier_manifest.json` names the pre-v0.4 bitstream and per-frame digests
   of which 22 of the column's 36 frames differ from the committed `b4.bit`; the four frames holding the 21 addresses and all 21
   address values are equal. A session opened against it would refuse. This unit binds to `b4_build.json`'s digest and records the
   loaded-image reference it derives (`firmware/b4q/b4q_data.json`); regenerating a build of record is the owner's (plan P1).
2. **A host-side link failure has no fault code** in the contract's closed set: no O is sealed for a notary refusal, a stopped DMA or
   an interruption; the raw material is retained (5.7's interruption row). A contract decision (plan P3).
3. **The latch A2 endpoint is unmodelled on the host**; the plan carries the row to the board.
4. A bench-model / hypothesis corner no fixture reaches (a non-inverted-gate latch after the init event); noted.

## 7. What the unit does not do

No board, power, provisioning, PCAP on a device, 2d, routing; no production seed derivation, search, gate, sweep; no change to the
protocol, task, operator, thresholds, labels, receipt, hypothesis, any archive or decision; no carrier RTL change; no board image; no push,
no merge. The write set's authority on a live device is the plan's question (§5), not decided here.

## 8. Files

`README.md` (this) · `owner_ruling_2026_10_27/` · `run_header.txt` · `firmware_build.json` · `xcheck.txt` · `fidelity.txt`, `fidelity.json` ·
`e2e/` (sixteen scenario directories: `manifest.json`, `summary.json`, `verify.json`, `verify.txt`, `session_open.json`, `notary_log.json`,
`trace.jsonl`, `pcap_log.jsonl`, `events.jsonl`, `accesses.jsonl.gz`, `tx_NNN/{o,f,x,ctx,links,firmware_result,record}.json`, the
A5 / A8 / A2 readings) · `e2e_run.log` · `a7_valid.txt` · `b4q_mutants.py`, `mutants.txt` · `tests_b4q.txt`, `tests_b4_suite.txt` ·
`import_check.txt` · `protected_paths.txt` · `assemble.sh` (how the evidence is regenerated from fresh runs).

## 9. The repair after the owner's HOLD on `3723b91` (2026-10-27; archived in `owner_review_3723b91_HOLD/`, 63 checksums OK)

The HOLD named five blocking contracts, all reproduced by the owner's probes (`owner_review_3723b91_HOLD/probes.py`) and all
accepted; the repair is in this same unit (`docs/b4q_integration.md` §5a has the per-item table):

| item | the repair | the evidence |
|---|---|---|
| R1 fail-closed sequencing | the executing side stops **before** the next operation on a pre-event / post-event / restored-base readback that is not what it must be and on any refused write (a refused STEP_IN launches no STEP); the session latches a halt on a refused opening, a transaction without a sealed `O` or a closed / `injection_open` `X`, a link / F / binding finding or an interruption — nothing further is signed | five new e2e scenarios (`startup_corrupt`, `pre_event_corrupt`, `post_event_corrupt`, `base_readback_corrupt`, `step_in_slverr`) whose tests assert the **absence** of the later CTRL operation, DMA and signature (`test_r1_fail_closed_before_the_next_operation`); the verifier finds a transaction run after a record that required a halt; mutant R1a killed, R1b / R1b2 / R1c / R1d / R1e each masked by a redundant guard and killed in the combined mutants (section 4) |
| R2 the archive verifier | the manifest declares every record with its ranges; the verifier validates the archive's shape first (a malformed manifest or a missing file is a named `REFUSED`, exit 1, no traceback), refuses a declared record missing or an undeclared directory, finds an unconsumed trace / PCAP suffix; the staging witness is recomputed from the **retained submitted stream bytes** (the DDR content when each envelope DMA was queued — the executing side's link-2 input), apart from the post-write readbacks | `test_r2_archive_completeness_and_refusals`; mutants R2a / R2c killed, R2a2 masked and killed in R2a2+files |
| R3 qualification conclusions | the session declares the qualification index (which records play which role); the verifier recomputes A2 / A5 / A8 from the retained `O` / `X` and holds the conclusion files to it; A5 needs J1 / J3 closed with their cleanup and J2 `injection_open`, A8 every corner complete and closed, A2 both endpoints closed — a missing witness is `not_demonstrated` / `not_assessable`, never a positive claim; the plan's §4.1 fixes the data-versus-claim distinction | `test_r3_qualification_conclusions_recomputed_and_conditioned`; mutants R3a / R3b killed |
| R4 A7's DMA tuple | every submission classified from its full registers (both endpoints, both lengths, the HOLD tag, the alignment, the exact staging slots); the logged kind held to it | `test_dma_tuples_are_classified_from_their_registers`; mutants R4a / R4b killed |
| R5 the raw configuration | the raw schema types the 21-bit dictionary; the adapters validate every consumed field by type before deriving; no coercion | `test_raw_values_are_checked_by_type_before_any_conversion`; mutants R5a killed, R5b masked and killed in R5a+R5b |
| P3 | the shared fixture builds the executing side and generates the valid scenario unless complete (`tests/b4q_fixture.py`); the owner's two test logs are in the archived review; the first-delivery mutant log kept as `mutants_first_delivery.txt`; the raw mutant log's trailing whitespace is an original output and is not trimmed | — |
| disposition 1 | the carrier manifest of record regenerated from the committed bitstream by the existing generator; the old manifest, the digests before / after, the generation command and the comparison (22 of 36 column frames differ, the four address frames and all 21 values equal) in `manifest_regeneration/` | `test_the_manifest_correction_is_a_recorded_before_and_after` |
| disposition 2 | a host-side failure that cannot be sealed stays a named host non-success result with the raw prefix, no fabricated `O`, the stop latched (plan §4.2) | the e2e negatives |
| disposition 3 | the latch endpoint stays `not_assessable`; the x5FF cells are never filled | `a2_pairs` |

The e2e run of record now has **16 scenarios**; the first delivery's 11 keep their names. The tests: the nine suites rerun at
closure (`tests_b4q.txt`, 70 OK); the mutant battery rerun whole (section 4: 31 / 13 / 0 of 44); the 332-test B4 battery not rerun
(`b4/` unchanged, `import_check.txt` 59 entries equal; the owner's instruction). The evidence was assembled on the repair commit's
tree (`run_header.txt`) and committed on top of it, as at the first delivery.

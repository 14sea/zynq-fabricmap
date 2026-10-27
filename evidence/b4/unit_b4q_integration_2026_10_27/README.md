# B4 — the host-only B4Q observation integration unit (2026-10-27 / 28): the executing side, the PCAP links, the schemas and adapters, the offline end-to-end transaction and the B4Q plan — **resubmitted after the owner's HOLD on `3723b91` (section 9: R1–R5 repaired in this unit) and the owner's second HOLD on `6f62b6a` (section 10: the R1–R3 residuals repaired in this unit; R4 / R5 and the manifest correction accepted there)**

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
| 5 the end-to-end evidence | `host/b4q_e2e.py` — nineteen scenarios (eleven at the first delivery, five fail-closed ones after the first HOLD, three read-failure ones after the second), each its own session; `host/b4q_verify.py` — the fresh-process verifier (records rebuilt from the trace and compared to the stored ones; structure / binding / chain; the schema files; the links recomputed from the PCAP log; the executing side's digests and fitness held to the host's; A7; the view; the manifest's references; agreement with the session's own findings as the exit code); the run of record in `e2e/` (section 3) | `tests/test_b4q_session.py` (6), `e2e/*/verify.json` |

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
| `startup_corrupt` / `pre_event_corrupt` / `post_event_corrupt` / `base_readback_corrupt` / `step_in_slverr` (after the first HOLD) | the opening refused on a corrupted startup readback (no root signed); a candidate stopped **before** INIT_REQ / before any STEP / before RESTORE_INIT on a readback that is not what it must be; a refused STEP_IN launching no STEP — the session halted, the next candidate refused | agree (the halt declared) |
| `nonce_read_slverr` / `heartbeat_read_slverr` / `devc_ctrl_read_slverr` (after the second HOLD) | a read answered SLVERR, the word unchanged: no signature on the refused nonce (no ARM); no INIT_REQ after the refused pre-event read; no DMA after the refused DEVCFG read — **zero writes of any kind after the refused read**, a stop, no O, the session halted, the next candidate refused | agree (the halt declared; the bench's declared refused reads are not A7 findings) |

A7 on every scenario: empty (`a7_valid.txt`: 19 carrier offsets read, the expected writes, the DevC's registers, the three buffers; the
RTL's one write region not touched is the key window). The access logs are kept compressed (`accesses.jsonl.gz`; the verifier reads them).

## 4. The mutant battery (`b4q_mutants.py`; `mutants.txt` the whole battery at `6f62b6a`; `mutants_round2.txt` the round-2 subset)

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
not counted as a tested guard by itself; "masked" means masked on the tested fault conditions, not a proof of semantic equivalence.

**Round 2 (`mutants_round2.txt`, after the owner's HOLD on `6f62b6a`; the whole-battery log `mutants.txt` of `6f62b6a` kept as it was):**
19 new single mutants on the round-2 guards (R1f–R1k the admission invariant; R2d / R2d2 the exact tiling and the opening's range;
R2e / R2e2 / R2e3 the nested shapes; R3c–R3j the index bindings and the full conclusion comparison) and 6 new combined ones, run as a
subset together with the 35 existing mutants whose files changed (`b4q_tx.c`, `b4q_session.py`, `b4q_verify.py`; the QUAL / A7 /
SCHEMA / VIEW / RECORDS mutants untouched since `6f62b6a` not rerun), with four new probes (the read-failure scenarios, the
coordinated range mutation, the nested malformed files, the coordinated relabellings): **37 killed, 23 survived, 0 edit-miss of 60**,
plus `mutants_round2_followup.txt` for R2c+R2e rerun with its proper probe (the first run paired it with the nested-files probe, which
never writes `manifest = []`). Every round-2 guard is killed either alone (R1g, R1i, R2d, R2d2, R2e3, R3e–R3j) or in the combined
mutant that removes its masking twin (R1f+R1j, R1h+R1k, R2e+R2e2, R3d+R3e+R3f, R3c+R3d+R3e+R3f, R2c+R2e). Masked on the tested
fault conditions, each named with its twin: R1f (by the explicit pre-signing / pre-event / DMA checks), R1h, R1j, R1k, R2e / R2e2,
R3c / R3d (the corner binding uses the mapping's bits of the relabelled element, so a relabelling fails there first). Three results of
`6f62b6a` moved: R2c (the top-level manifest check) and the combined R1b+R1b2 and R2a2+files are now masked by the round-2 guards
(the field validator's object check, the write accessor's admission gate, the per-record reader) — named, not recounted; R1c+R1b+R1b2
and R2c+R2e are the kills that stand behind them. The 16 pre-existing survivors keep their names and reasons.

## 5. The tests (`tests_b4q.txt`; the B4 battery in `tests_b4_suite.txt`)

Prerequisite (the owner's P3 of the second review): `test_b4q_schema`'s schema-against-bench test reads `sim/b4/out/flow.jsonl`, which
`test_b4carrier_benches` generates; in a source-only tree run the bench suite first (as `tests_b4q.txt` does, the benches before the
schema suite) or that one test skips — the owner's first full invocation saw exactly that skip and then passed the test alone.

The nine suites this unit touches or depends on: `test_b4q_derive` 8, `test_b4q_emu` 7, `test_b4q_schema` 5, `test_b4q_view` 6,
`test_b4q_firmware` 5, `test_b4q_session` 10, `test_b4carrier_records` 18, `test_b4carrier_regmap` 11, `test_b4carrier_benches` 1 (the
iverilog benches) — **71 OK, no skip** (65 at the first delivery; five added by the first repair, section 9; one by the second, section 10),
run in the stated order (the benches first). The frozen B4 battery (`b4/tests`, 332 tests) unchanged and green (section 5's file; `b4/` is
byte-identical to `main`, `import_check.txt` 59 entries equal).

## 6. Findings for the owner at the first delivery (historical, 2026-10-27; each with its disposition — none is an open present-tense state)

1. **RESOLVED (disposition 1, section 9): the carrier manifest of record was stale** at the first delivery: `builds/b4/b4_carrier_manifest.json` names the pre-v0.4 bitstream and per-frame digests
   of which 22 of the column's 36 frames differ from the committed `b4.bit`; the four frames holding the 21 addresses and all 21
   address values are equal. A session opened against it would refuse. This unit binds to `b4_build.json`'s digest and records the
   loaded-image reference it derives (`firmware/b4q/b4q_data.json`). The owner's HOLD on `3723b91` authorised the narrow regeneration; it was
   done (`manifest_regeneration/`, before / after archived) and accepted in the review of `6f62b6a` (plan P1 closed).
2. **RESOLVED (disposition 2, section 9): a host-side link failure has no fault code** in the contract's closed set, so no O is sealed for a
   notary refusal, a stopped DMA, a refused read or an interruption; the ruling: such a failure stays a named host non-success result with its
   raw prefix, no fabricated O, the stop latched (plan §4.2; accepted in the review of `6f62b6a`).
3. **ACCEPTED LIMITATION (disposition 3): the latch A2 endpoint is unmodelled on the host**; its row stays `not_assessable` here and the plan
   carries it to the board; the x5FF cells are never filled.
4. NOTED (no action): a bench-model / hypothesis corner no fixture reaches (a non-inverted-gate latch after the init event).

## 7. What the unit does not do

No board, power, provisioning, PCAP on a device, 2d, routing; no production seed derivation, search, gate, sweep; no change to the
protocol, task, operator, thresholds, labels, receipt, hypothesis, any archive or decision; no carrier RTL change; no board image; no push,
no merge. The write set's authority on a live device is the plan's question (§5), not decided here.

## 8. Files

`README.md` (this) · `owner_ruling_2026_10_27/` · `run_header.txt` · `firmware_build.json` · `xcheck.txt` · `fidelity.txt`, `fidelity.json` ·
`e2e/` (sixteen scenario directories: `manifest.json`, `summary.json`, `verify.json`, `verify.txt`, `session_open.json`, `notary_log.json`,
`trace.jsonl`, `pcap_log.jsonl`, `events.jsonl`, `accesses.jsonl.gz`, `tx_NNN/{o,f,x,ctx,links,firmware_result,record}.json`, the
A5 / A8 / A2 readings) · `e2e_run.log` · `a7_valid.txt` · `b4q_mutants.py`, `mutants.txt` · `tests_b4q.txt`, `tests_b4_suite.txt` ·
`import_check.txt` · `protected_paths.txt` · `assemble.sh` (how the evidence is regenerated from fresh runs) · `owner_review_3723b91_HOLD/`,
`owner_review_6f62b6a_HOLD/` (the owner's two reviews as relayed, checksums verified) · `mutants_round2.txt`, `mutants_round2_followup.txt`
(section 4, round 2) · `manifest_regeneration/` (section 9, disposition 1).

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

The e2e run of record then had **16 scenarios**; the first delivery's 11 keep their names. The tests: the nine suites rerun at that
closure (70 OK); the mutant battery rerun whole (section 4: 31 / 13 / 0 of 44, `mutants.txt`); the 332-test B4 battery not rerun
(`b4/` unchanged, `import_check.txt` 59 entries equal; the owner's instruction). That evidence was assembled on the repair commit's
tree and committed on top of it (`6f62b6a`); the owner's review of it is section 10.

## 10. The repair after the owner's second HOLD, on `6f62b6a` (2026-10-27; archived in `owner_review_6f62b6a_HOLD/`, 88 checksums OK)

The owner independently regenerated the 16 scenarios (32 fresh verifications agreeing, fidelity 0 mismatches), accepted R4 / R5 and the
manifest correction, and held three residuals of the original R1–R3 contracts, each reproduced by probes (`owner_review_6f62b6a_HOLD/probes.py`,
`read_error_supplement.py`); all three accepted and repaired in this same unit (`docs/b4q_integration.md` §5b has the per-item table):

| item | the residual | the repair | the evidence |
|---|---|---|---|
| R1 (P1): read / HAL failures still admitted later events | a NONCE read answered SLVERR was still followed by a signature and ARM; a HEARTBEAT read answered SLVERR by INIT_REQ; a DEVCFG_CTRL read's response was discarded (`mem_rd`) and the transaction closed | **one admission invariant, centralised** (`b4q_tx.c`): after the first stop of a call no write of any kind is issued — the two write accessors refuse (`axi_wr`, `mem_wr`: so no CTRL operation, no staging word, no DMA register write, hence no DMA is queued) and no signature is requested (`candidate_in` checks before `b4q_sign`); every PS-map read's response is propagated (`mem_rd` stops on SLVERR, the word is not evidence); `devcfg_dma` / `devcfg_wait_done` check admission around the CTRL read and before the queueing write; a refused IDCODE read refuses the opening. Reads stay admitted (a diagnostic read after a refusal is evidence, never permission); the first reason, the phase reached and the raw prefix are kept; the session halts as before. The A5 paths and the valid paths unchanged | three e2e scenarios (`nonce_read_slverr`, `heartbeat_read_slverr`, `devc_ctrl_read_slverr`) whose test asserts the **absence** of the later signature / CTRL operation / DMA and **zero writes after the refused read** (`test_r1_read_and_transport_failures_admit_no_later_event`, with the refused-IDCODE opening); the owner's own probes rerun on the repaired tree: NONCE → 0 signatures, CTRL [PRE_SAMPLE-less: `0x100` only]; HEARTBEAT → `[0x100, 0x40, 0x200]`, no `0x400`; mutants R1f–R1k and the combined R1f+R1j / R1h+R1k (section 4) |
| R2a (P1): an internal PCAP gap was clean | the tiling condition only rejected overlaps | the opening owns exactly its declared prefix (`open_pcap_range`, written by the session, held to the first record's start and to the startup readback's kinds: no transaction event, one readback group); then **exact** tiling — every record starts where the previous ended in the PCAP log and in the trace, every range in-bounds, no unconsumed suffix (with or without records) | the coordinated +1 mutation (manifest + record.json) in `test_r2_*` and `probe_tiling`; the owner's `pcap_internal_gap` rerun: exit 1, not clean; mutants R2d / R2d2 |
| R2c (P2): nested malformed files / fields were tracebacks | only the top-level manifest shape was validated | every consumed object validated by name **before** indexing (`_fields` / `_read_json_object` / `validate_record_files` / `validate_qualification_index`): the manifest's nested `executing_side`, `instrument`, `hypothesis`, `mapping`, `qualification_plan` (typed roles and keys), `halted`, `backend`, the ranges; `session_open.record`; per record `record.json`, `ctx.json`, `links.json`, `firmware_result.json`, `o.json` / `f.json` / `x.json`; the JSON-lines entries' kinds and access fields. A malformed archive is `REFUSED` (exit 1); anything the verifier itself cannot handle is reported as a **`VERIFIER ERROR`** (exit 2, named, no traceback) — the verifier's own defect, never a finding about the evidence and never confused with a refusal | `test_r2_*` (twelve nested cases, each `REFUSED` with the field named, no traceback); the owner's `record_list` / `ctx_list` / `nested_binary_missing` rerun: named refusals; `probe_nested`; mutants R2e / R2e2 / R2e3 and R2e+R2e2 |
| R3 (P1): the index's labels and the conclusions' data fields were unbound | the recomputation trusted the index's element names / indices / bits / background and compared only row / verdict / one reading block | the index is **bound to the mapping and to the records' actual `O.config`**: every element name / index against the mapping's element order; the qualified element declared (`element`) and among the index's elements (others are declared bystanders: diagnostics, their bits not required to vary); the varied bits equal to the mapping's addresses of (element, ff_init / ff_srval); each corner's record observing its (INIT, SRVAL) label and the declared background outside the varied bits; four distinct corner records with one demonstration stimulus and in-range parts; A2's semantic bound to the one address at which the endpoints' records actually differ, the declared endpoint genomes to the records, one stimulus; A5's roles three consecutive records of the protocol's kinds (normal / inject / a5) on one configuration with J1 = J3's stimulus. Every conclusion compared **in full** (the whole data-bearing content: samples, readings, quantities, differing points, witnesses, the endpoint findings held to the records'); nothing is informational-only | the owner's four relabelling probes rerun: each exit 1 with the binding named (`A5FF`: not the mapping's element order; bits / background: not the mapping's addresses, corners not observing the background; init_samples / quantities: the conclusion not recomputed in full; `ff_init`: the endpoints do not differ at an ff_init address); `test_r3_*` (relabelling onto the bystander, swapped corners, a foreign endpoint genome, wrong role kinds, five partial-conclusion edits); `probe_binding`; mutants R3c–R3j and the combined R3c+R3d / R3d+R3e+R3f |
| P3-1 the stream witness's capture time | documented as "at submission / queued" | the comments and docstrings now say what the fake does: the bytes are read in the DevC fake's data handling, reached from the first status poll after the queueing write, immediately **before** the emulated frame-store update — not at the queueing write, not a physical DDR re-read; a DMA that never reaches data handling leaves only its `submit` entry and no witness is written | `b4q_backend.Devc.data`, `b4q_session.staging_witness`, `docs/b4q_integration.md` §5a R2b |
| P3-2 section 6's present tense | two states for resolved findings | section 6 rewritten as the historical findings with their dispositions | this file |
| P3-3 the owner's test evidence | the 70-test invocation skipped one | the prerequisite stated (section 5); the owner's logs kept in the archived review | `owner_review_6f62b6a_HOLD/tests.txt`, `skipped_test_rerun.txt` |
| P3-4 the mutant wording | "masked" without the condition | "masked on the tested fault conditions" throughout; a combined kill is never recounted as a single kill; the STEP_IN guards' evidence is not a claim about every read / transport stop — the read / transport stops have their own scenarios and mutants (R1 above) | section 4 |

The e2e run of record now has **19 scenarios**. The affected tests and suites rerun (section 5); the affected and relocated mutants rerun as a
subset with the round-2 ones (`mutants_round2.txt`; the whole-battery log `mutants.txt` of `6f62b6a` kept unchanged, per the owner: no
whole-44 repeat while unrelated code is unchanged); the 332-test B4 battery not rerun (`b4/` unchanged). Nothing physical; no push, no merge.

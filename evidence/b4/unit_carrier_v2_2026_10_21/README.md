# B4 — the carrier v2 engineering unit (host-only, 2026-10-21) — resubmitted after the owner's HOLD on `823f5b0` (section 8)

**What this unit is.** The engineering unit the owner authorised on 2026-10-21 after the 2c-obs closure (`36e012c`): design,
RTL, bench, XDC / isolation, the host build and verification; the initialisation mechanism selected, the sampling path, the MMIO
interface, the session-opening and the O / F / X flow built to the accepted observation contract; end-to-end verification on
the success and the fault paths; A1–A8 split into host-verified and board-only. One submission for one review. The branch
`b4-carrier-v2` from `36e012c`; nothing pushed or merged.

**Round 2.** The first delivery `823f5b0` was held by the owner (R1–R5); section 8 of this README records the repair, finding by
finding, and the verification of the repaired unit. Sections 1–7 describe the unit as it now is.

**The design document is `docs/b4_carrier_v2.md`** (v0.2); its section 0 is the unit's finding (one CE / SR / CLK pin per slice against
the per-element `ce` / `sr` vectors of task-v0.2 and the model), its section 2 the mechanism selection, its section 7 the A1–A8
table, its section 8 the unresolved items. This README is the unit's record: what was delivered, how it was verified, what the
numbers are, and what was not done.

## 1. Deliverables (all new files; nothing pinned or protected touched — `verification.txt`, the diff over the protected paths is empty)

| area | files |
|---|---|
| RTL | `rtl/b4/b4_top.v`, `b4_core.v`, `b4_axil.v`, `b4_gate.v`, `b4_engine.v`, `b4_axi_gate.v`, `b4_gsr_reg.v`, `b4_slot_ram.v`, `b4_gsr_ram32.v`, `b4_target_slice.v` (+ `rtl/b1/p3_siphash.v` and `vivado/carrier/carrier_axi3_lite.v` by reference, unchanged) |
| bench | `tb/b4/b4_target_slice_model.v`, `tb/b4/gen_b4_fixture.py`, `tb/b4/b4_fixture.vh` (generated), `tb/b4/tb_b4_core.v` (21 scenarios), `tb/b4/tb_b4_unisim.v` (run over the RTL core and over the netlist), `tb/b4/tb_b4_axi3.v` (the PS path through the pinned shim), `sim/b4/run.sh` |
| build | `vivado/b4/b4.xdc`, `vivado/b4/build_b4.tcl`, `vivado/b4/resume_b4.tcl`, `vivado/b4/isolation_checks_b4.tcl`, `vivado/b4/netlist_core.tcl`; `builds/b4/b4.bit`, `b4_build.json`, `b4_carrier_manifest.json`, `b4_core_funcsim.json`, `isolation.txt`, `timing.rpt`, `post_synth_util.rpt`, `post_route_util.rpt` (the checkpoints, the Vivado stdout and the 1.4 MB netlist are regenerated and ignored by `.gitignore`; the stdout and the netlist's record are archived here under `build/`) |
| host | `host/b4carrier_regmap.py` (the register table, the CTRL bits, the fault names, the STEP_IN packing and realisability), `host/b4carrier_records.py` (O / F / X / session_open from a register trace; the carrier-branch validator), `host/b4carrier_manifest.py` (the 21 addresses read from the bitstream) |
| tests | `tests/test_b4carrier_regmap.py`, `tests/test_b4carrier_records.py`, `tests/test_b4carrier_benches.py` |
| documents | `docs/b4_carrier_v2.md`; `docs/b4_architecture.md` §13 (one row) and §14 (one line) |
| this directory | `verification.txt` (every check in a fresh process; round 1 then round 2), `bench/` (the 21 + 3 scenario results and the 21 register traces the records are built from), `build/` (the Vivado stdout of the builds, the netlist synthesis, the manifest, the netlist record), `mutants/` (the battery, its script, its outputs), `owner_review_823f5b0_HOLD/` (the owner's review of round 1, 30 files, byte for byte, `SHA256SUMS` verified) |

## 2. The design in five lines

1. **Target**: eight `FDPE` + four pass-through `LUT6` pinned to `SLICE_X2Y25` and its BELs; CE and SR connected so the pins are
   routed (the loaded bitstream shows `CEUSEDMUX = SRUSEDMUX = 1`; the session root writes genome 0 as a signed candidate).
2. **Init mechanism (b)**: GSR through `STARTUPE2`, raised by the engine inside the transaction with hardware timing; (c) rejected
   (no Q effect without GRESTORE), (a) not selected (host-timed, through archived code).
3. **GSR-robust by construction**: the key, the nonce, the sticky fault, the armed latch, the samples and the witnesses live in
   `RAM32X1S` (231 cells, no flip-flop among them — an isolation verdict); the engine wakes from its reset state and finishes the
   init sample from the persisted `init_pending`.
4. **The step**: control (`ce`, `sr`) one cycle before data (`d`), then settle, the clock level, hold, sample — a `set` step with a
   non-uniform `ce` or `sr` is refused by name (`F_NOT_REALISABLE`).
5. **Records**: every sample into a GSR-immune slot; the host builds `O` (complete or phase-dependent invalid), `F` over the full
   mask, `X` (closed / injection_open) and `session_open`, and validates them against the contract's closed sets.

## 3. Verification (fresh processes; `verification.txt` has every output as it came)

| check | command | result |
|---|---|---|
| the verbatim SipHash bench, the 12 core scenarios over the hypothesis model, the vendor-model bench | `bash sim/b4/run.sh` | **14 × TB_PASS** |
| the register map vs the RTL decode (9 tests); the records from the bench traces and the closed-set validator (10 tests); the benches (1 test) | `python3 -B -m unittest tests.test_b4carrier_regmap tests.test_b4carrier_records tests.test_b4carrier_benches` | **Ran 20 … OK** |
| the 21 certified addresses read from `builds/b4/b4.bit` | `python3 -B host/b4carrier_manifest.py builds/b4/b4.bit` | **no mismatch** (`ce_mode`, `sr_mode` = 1; the other 19 = 0) |
| the Vivado build (2025.2) and the v2 isolation checks on the routed design | `vivado/b4/build_b4.tcl` → `resume_b4.tcl` (`build/*.stdout`) | routed; **WNS +8.173 ns**; target cells 12 / flush 0; RAM32X1S 231, flip-flops in the store 0; STARTUPE2 1 (GSR driven); ICAPE2 0; the sampling path as listed in `builds/b4/isolation.txt` |
| the pinned B1 surface | `python3 -B -m unittest tests.test_b1_pins` | OK |
| the protected paths since `fceedd6` | `git diff --name-only fceedd6 HEAD -- …` | none |

**The bench scenarios** (one simulation each — a fault is persistent in v2 and only a reconfiguration, i.e. a fresh simulation,
clears it, which `flow` also shows by surviving a reset): `regs` (alive, SLVERR, VARIANT, TIMING, the key write-once and
persistent across a reset); `flow` (six fixtures end to end: each init sample and every step's sample equal to the formal
model's expectation on the modelled cells; `gsr_count` one per transaction; the heartbeat restart; the inputs 0 after the event;
the nonce chain across the events; the replay refused with a sticky fault that survives a reset); `fault_not_armed`,
`fault_nokey`, `fault_unsigned`, `fault_wrong_commit`, `fault_wrong_key`, `fault_sequence`, `fault_double_arm`,
`fault_realisable` (the acquired prefix retained: step_index 2, slot_count 4, the last acquired step intact); `a5` (J1–J3: the
injection witnessed in `IN_LIVE` and slot 0, cleared by the event — the pass data); `a5_persist` (the same on the hypothesis-swap
fabric `init_no_effect`: the injected state persists while the carrier raised the event twice — the fail data); `unisim` (the
vendor FDPEs return to INIT under the carrier's GSR; the LUTRAM key and nonce survive).

**What the records tests say, verbatim in substance**: the four flip-flop fixtures' transactions validate as complete carrier
records with `F` and a closed `X`; the first transaction's pre-init sample is the model's never-initialised fabric (`x`) and the
carrier validator refuses that null — as it must, since a carrier samples a physical value; the two latch fixtures' records carry
the model's null on the x5FF cells and are refused for exactly that (the D1 rule seen from the bench, not a carrier defect); the
non-uniform-`ce` stop yields an invalid `O` at P5 with `step_reached` 2 and the prefix; J2 closes `injection_open` and J3's
record carries the held context, the injected state and its clearing.

## 4. The mutant battery (`mutants/run_mutants.py`, `mutants.txt`, `mutants.json`; hermetic: a temporary copy of the needed
subtree is mutated, never the repository; a kill is a REPORTED failure with the run having happened)

| id | what the mutant removes or breaks | killed by |
|---|---|---|
| M01 | the armed / recovery gate on engine operations | `fault_not_armed` |
| M02 | the nonce step after a verification | `flow` (the replay verifies) |
| M03 | the realisability check | `fault_realisable` |
| M04 | the GSR pulse (no init event) | `flow` (no heartbeat restart, `gsr_count`), `a5` |
| M05 | control-before-data (the v0.1 race restored) | `flow` (the latch fixture) |
| M06 | the VARIANT word (the core's live default; a first version mutated the register file's overridden default and survived — recorded, re-aimed) | `regs` |
| M07 | the ARM-while-armed refusal | `fault_double_arm` |
| M08 | the STEP-before-init refusal | `fault_sequence` |
| M09 | the `closed_without_cleanup` witness | `a5` |
| M10 | the init sample inverted | `flow` |
| M11 | the tag comparison (every payload verifies) | `fault_unsigned` |
| M12 | the cleanup's clock-to-0 | `flow` |
| H01 | the closed set of a complete `O` (missing keys only) | `test_b4carrier_records` |
| H02 | the phase table of an invalid `O` | `test_b4carrier_records` |
| H03 | the app read allowlist widened to the old sweep window | `test_b4carrier_regmap` |
| H04 | the null-cell refusal | `test_b4carrier_records` |
| H05 | the realisability rule | `test_b4carrier_regmap` |
| H06 | the deny-list | `test_b4carrier_records` |

**18 / 18 killed; 0 survived; 0 EDIT-MISS; 0 NOT-RUN.** (A first run reported every RTL mutant NOT-RUN because the temporary copy
lacked the instrument-binding manifests the fixture generator reads; the copy list was completed and the battery rerun — the
NOT-RUN rows were never counted as kills.)

## 5. The finding, stated for the review (`docs/b4_carrier_v2.md` §0)

A 7-series slice has one CE, one SR and one CLK pin shared by its eight storage elements. task-v0.2's stimuli and the hypothesis
model use per-element `ce` / `sr` vectors; on the certified site those are realisable only when uniform. The carrier applies a
step only then and refuses the rest by name. **task-v0.2 as specified is therefore not executable on this site**, and K9's
discriminability was computed under per-element SR. What follows (a task / model revision to slice-wide `ce` / `sr`, a
recomputation under it) is the owner's decision; this unit changes neither the task nor the model, and the bench fixtures use
uniform vectors on purpose.

## 6. A1–A8 (the table of `docs/b4_carrier_v2.md` §7, in one line each)

A1 the carrier's part of every phase on the bench — the PCAP links and the firmware remain; A2 board only; A3 the closed-set
validator with every injected break refused; A4 the identity word, the stable offsets, the persistent write-once key — the PS
path on the board; A5 the J1–J3 protocol with pass and persistence data on the bench — silicon with the plan's *c′*; A6 the B1
scenarios that apply plus the six fixtures and the contract's own; A7 the allowlist = the decode; A8 the mechanism selected,
declared, timed and witnessed on the vendor models — the Q effect, the same-element cross and the self-timed pulse on the board.

## 7. Unresolved (`docs/b4_carrier_v2.md` §8) and what the unit did not do

The protocol consequence of the finding; A8 and the pulse width on silicon; the firmware and the PCAP / session-opening
integration; P9's base-state witness form; the link and manifest fields of the records (symbolic on the bench); sampling
meaning in every configuration. Not done: no board, no production run, no change to `b4/`, the pinned B1–B3 surfaces, the
hypothesis, the thresholds, the archives or any decision; no push, no merge. The evidence-proportionality rule of 2026-10-20
applies: the battery is complete for this first delivery; a correction round would run the affected scenarios / modules.

## 8. Round 2 — the owner's HOLD on `823f5b0` (R1–R5), answered in the same unit

The review is archived in `owner_review_823f5b0_HOLD/`. Its independent baseline (20 tests, 14 benches, 3 pin tests, 21
addresses, the shared-pin finding against AMD UG474) is accepted as the starting point; its five reproductions are scenarios of
`tb/b4/tb_b4_core.v` now, with the repaired expectations; nothing under `b4/`, the pinned surfaces, the hypothesis, the task,
the thresholds or the archives changed (`verification.txt`, the protected-path diff since `fceedd6` is empty).

| finding | what was wrong at `823f5b0` | the repair | verified by |
|---|---|---|---|
| **R1** P9 missing; permissive close | no event on the restored base in the current transaction; `CLOSE` accepted without cleanup, `idle` shown with held inputs, the next ARM accepted | `RESTORE_INIT` (CTRL bit 14): the current transaction's event on the restored base, the sample into `BASE_STATE` (0x203C), `gsr_count + 1`; a normal `CLOSE` only after `restore_done` (else F_SEQUENCE); `CLOSE_INJECTION` (bit 15) the explicit A5 exception persisting `injection_open`; the next ARM must carry the A5 flag (bit 7) and only then (else F_SEQUENCE, both directions); `idle` = engine idle ∧ ¬armed ∧ ¬injection_open ∧ inputs and clock 0; the host's `X` takes `base_state_sample` from `BASE_STATE`, never from a caller | `p9`, `p9_ok`, `open_close_refused`, `a5`, `a5_wrong_context`, `a5_flag_without_injection`, `flow` (two events per transaction), `unisim` (RTL and netlist: the base-state sample = INIT on the vendor FDPEs), `axi3`; records: a closed `X` requires `idle_status = 1`, `transaction_close` refuses an unclosed transaction |
| **R2** GSR lost an outstanding AXI response | the pulse was scheduled eight cycles after the request regardless of the bus; BREADY = 0 lost the write response | `b4_axi_gate` in front of the pinned shim (`b4_top`) and at the core's Lite port: while an event is pending nothing new is accepted (the master holds its VALID); the engine launches only after ASSERT_DELAY consecutive cycles with nothing outstanding (AW→B, AR→last R, no response pending) on either path | `backpressure` (the response held for the master through the window, one event after it is taken, exactly one response), `read_during_window`, `read_at_launch` (a poll at every offset around the launch cycle), the same backpressure and stalled read THROUGH THE SHIM in `tb_b4_axi3`; mutant M18 (the gate's masking removed) killed by `read_at_launch` |
| **R3** STEP not atomic; busy commands vanished | the engine read `STEP_IN` live in different cycles; a CTRL write while busy was answered OKAY and dropped | the accepted STEP is latched (`cmd`) and only the latched copy is applied; one CTRL acceptance rule in the register file — exactly one operation, known bits, the A5 flag with arm only, engine and gate idle, otherwise SLVERR and nothing changes; the inputs the engine APPLIED are recorded per sample (`SLOT_IN_READ`, 0x2040) and the host builds the steps from them | `step_atomic` (the staged next word changes nothing of the running step; the applied-input record = the accepted command), `busy_refused` (CLOSE and STEP during a step SLVERR; one step applied), `regs` (combined, flag-only, unknown-bit and empty commands SLVERR); mutants M14–M16 |
| **R4** records not the claimed contract | closure only at the top level; empty complete steps, null samples, wrong kinds / types / variant, a non-idle closed `X`, a null `session_open` accepted; dictionary order compared; a list raised; a boolean fitness, a short target; `X` sealed before CLOSE; the refused step dropped from the stimulus; a fabricated init step; no source / task / link binding | `host/b4carrier_records.py` rewritten in three layers: structure (closed, typed schemas at every level; order-independent; the applied steps held to the declared stimulus, which is an input kept whole; the q chain; the phase-dependent invalid `O`; a faulted `X`; a strict `session_open`; malformed input a finding), binding to a trusted context (instrument and VARIANT, session, declared stimulus, planned configuration, nonce, the previous close, mechanism (b)'s frame invariance, the task digest), the chain (session_open open → root → each predecessor naming the previous close); the builder reads the carrier's samples, applied inputs and `BASE_STATE`, fabricates no step or sample, refuses to close an unclosed transaction; `fitness` validates the task's dimensions and refuses an invalid observation | `tests/test_b4carrier_records.py`: every owner counterexample refused by name (the VARIANT one by the binding layer), the sorted-JSON round trip, the six-fixture chain from the bench traces (the four flip-flop fixtures at all three layers; the first pre-init sample and the latch fixtures' x5FF cells refused as the model's null — D1), the refused step kept in the stimulus with the prefix acquired, `X` not sealable before CLOSE, J2 `injection_open` / J3 `a5_injection`; mutants H01–H10 |
| **R5** the vendor bench did not model the implemented pulse generator | the pulse counter was flip-flops that silicon's GSR resets (40 ns in the RTL model, 0.1 ns with vendor FDCEs) | the generator is LUTRAM: a thermometer word in `RAM32X1S` loaded by `fire` and shifting itself (`11 → 01 → 00`); no flip-flop holds the pulse; a thermometer and not a binary count because the binary `2 → 1` glitched the resolved global net for a delta cycle (found on the vendor bench; a hazard on an asynchronous reset net); the vendor bench runs over the RTL core AND over a GSR-aware post-synthesis out-of-context netlist of the core (`vivado/b4/netlist_core.tcl`; a `write_verilog -cell` of the implemented top left the cell's constants undriven, `b4_core_funcsim.json` records the chosen netlist: 1970 flip-flops, 278 RAM32X1S), measuring the pulse on `glbl.GSR` | `unisim` on both: TB_PASS with `GSR_PULSE_WIDTHS_NS 40.0 40.0 40.0` (PULSE = 2 clocks) on every event; mutant M21 (PULSE = 1) killed on the vendor bench |
| the owner's further points | the bootstrap reference was B1-shaped; A7 overstated; A3 / A6 overstated; (c) overstated; the checkout not clean | the loaded image's frame content (its own hash domain) distinct from the signed base genome 0 — `docs/b4_carrier_v2.md` §3 and the contract's 5.5 clarification; A7 = the declared table vs the RTL, not a firmware's accesses; A3 / A6 marked partial with what is missing; (c) = no guaranteed independent restore; `.gitignore` for the regenerated outputs | `docs/b4_carrier_v2.md` §§2, 3, 7; `docs/b4_observation_contract.md` 5.5 |

**Verification of the repaired unit** (`verification.txt`, round 2, fresh processes): 21 core scenarios + the vendor bench over
the RTL core + the PS path through the shim + the vendor bench over the netlist — **25 × TB_PASS**, the GSR pulse 40 ns on every
event on both vendor benches; `tests/test_b4carrier_regmap` (11) + `tests/test_b4carrier_records` (13) + `tests/test_b4carrier_benches`
(1) — **Ran 25 … OK**; the rebuilt bitstream routed, WNS +7.426 ns, target 12 / flush 0, RAM32X1S 278 (no flip-flop in the store),
STARTUPE2 1, ICAPE2 0; the 21 addresses at their expected values; the B1 pin test OK; the protected paths unchanged. **The mutant
battery**: 21 RTL + 10 host mutants, **31 / 31 killed**, 0 survived, 0 EDIT-MISS, 0 NOT-RUN (M18 first survived against
`backpressure` / `read_during_window`, which pass without the masking; `read_at_launch` was written for what the masking is for
and kills it — recorded in `mutants/run_mutants.py`). What was NOT rerun: the full B1–B4 regression (nothing of it touched),
the production verifiers, any model or board observation.

**What stays as it was.** The finding of section 5 (one CE / SR / CLK per slice) and its protocol consequence for the owner;
the unresolved items of `docs/b4_carrier_v2.md` §8 (A8 and the release skew on silicon, the firmware, the PCAP integration,
the B4Q plan); no task, model, K9, threshold, archive or decision changed; nothing pushed or merged.

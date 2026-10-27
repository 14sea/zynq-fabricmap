# B4 carrier v2 — design, mechanism selection, sampling path, interface and acceptance (v0.4, host-only, 2026-10-21) — accepted and closed (the owner's PASS on `bf17574`, 2026-10-21)

> **Standing note (the owner's review of `bf17574`, 2026-10-21 — PASS; archived in
> `evidence/b4/unit_carrier_v2_2026_10_21/owner_review_bf17574_PASS/`, unit README §11).** This document and the delivered RTL,
> bench, build, host records and tests are accepted as the **host-only carrier v2 engineering unit**, R1–R4 resolved. The PASS
> does not establish A8, silicon behaviour, electrical timing, legal compositions, a gate result, a preregistration freeze or the
> future firmware / schema / adapter; the shared CE / SR / CLK finding of §0 and its protocol consequence are **not** resolved by it
> (the task-v0.3 revision is a separate unit under the owner's ruling of 2026-10-27). The carrier's RTL, register map and record
> layer are kept as accepted; task-v0.3 maps its slice-wide control values onto this interface (`0x00` / `0xFF` broadcast), the
> interface itself unchanged.

> **v0.1 → v0.2 (the owner's HOLD on `823f5b0`, R1–R5, 2026-10-21; the same unit, repaired).** R1 — P9 is the current
> transaction's: `RESTORE_INIT` raises the declared event on the restored base and samples it into `BASE_STATE`; a normal
> `CLOSE` is accepted only after it; `CLOSE_INJECTION` is the explicit, context-bound A5 exception and the next ARM must carry
> the A5 flag; `idle` means engine idle, not armed, no injection open, inputs and clock 0 (section 3). R2 — an AXI gate in
> front of the pinned shim and one at the core's Lite port: the event launches only after ASSERT_DELAY cycles with nothing
> outstanding on either path, and nothing new is accepted from the request until the sample; an outstanding response is
> delivered whatever BREADY does (section 4). R3 — the accepted STEP is latched; one CTRL acceptance rule (exactly one
> operation, known bits, engine and gate idle, else SLVERR and no change); the record carries the inputs the engine APPLIED
> per sample (section 4). R4 — the record layer rewritten: closed schemas at every level, order-independent, the applied steps
> against the declared stimulus kept whole, phase-dependent invalid records, faulted closes, a binding layer to the trusted
> context, chain validation (section 6 and `host/b4carrier_records.py`). R5 — the pulse generator is LUTRAM (a thermometer
> shift: hardware-timed, GSR-immune, glitch-free), and the vendor bench runs over a GSR-aware post-synthesis netlist of the
> core as well as over the RTL (section 2). Scope statements corrected (section 7); the bootstrap reference named in its own
> hash domain (section 3); the rejection of (c) rephrased (section 2).

> **v0.2 → v0.3 (the owner's HOLD on `aaf15ba`, five items, 2026-10-21; the same unit, repaired).** (1) The gates mask new
> AW / AR only — **W is never masked**: a W beat belongs to a transaction the shim already accepted, and masking it left a legal
> two-beat FIXED write whose first beat was `INIT_REQ` unable to drain while the engine waited for exactly that burst's B (the
> owner's reproduction; now `tb_b4_axi3` drives such bursts with the request in either beat). Under the shim the core's Lite
> gate only tracks (`LITE_STALL = 0` in `b4_top`); the outer gate does the masking (section 4). (2) The observation is **sealed
> at the P6 boundary** — the first accepted CLEANUP / CLOSE / CLOSE_INJECTION / RESTORE_INIT — and nothing after it enters `O`
> or its digest; a CTRL write the register file answered OKAY is an acknowledgement, **not** the operation's completion: `X`
> is closed only on the engine's completion witnesses, faulted with the real stop phase otherwise (section 6). (3) The
> session-opening record is bound to the trusted context (the manifest's instrument, the pinned loaded-frame reference every
> transaction restores to); `X.seq`, `O.seq` and `predecessor.seq` are reconciled; `F` is recomputed over the full grid from
> the trusted task; one zero-finding opening → init-only root → candidate → close chain comes from the bench (`session`)
> through fresh serialization (section 6). (4) The phase table governs which acquisitions may exist, the cleanup continues the
> observation's final clock, zero-valued constants are exact integers, a malformed chain entry is a finding (section 6).
> (5) The A5 exception enters the event in the contract's context: `INIT_REQ` with held inputs performs a **recorded pre-init
> cleanup** inside step 0 (control to 0, a falling edge if the clock was high, then the launch), witnessed as `pre_init_cleanup`
> (WITNESS bit 27, `O.init_event.parameters.pre_init_cleanup`) and checked at every GSR assertion on the bench (section 3).

> **v0.3 → v0.4 (the owner's HOLD on `ce3ca6d`, four items, 2026-10-21; the same unit, repaired).** Three statements of the
> v0.3 note above are superseded here. (1) **Two references, two bindings.** The session-opening record binds the trusted
> **loaded-image** frame reference (the natural carrier image, `CEUSEDMUX = SRUSEDMUX = 1`, `ctx.loaded_frames_reference_sha256`);
> every closed `X` binds the trusted **restored study-base** reference (signed base genome 0, `ctx.base_readback_sha256`). v0.3
> compared session_open against the restored-base field and its test made both one hash — an honest session with distinct
> references was refused. The two are never compared to each other (section 3). (2) **The seal is an acquisition state, not an
> operation name.** P6 is reached when the carrier's witnesses show the init event done and as many set steps applied as the
> declared stimulus holds; the seal is the first accepted P7+ operation after that. A P7+ operation before P6 is premature: if
> the engine refuses it, `O` keeps the acquired prefix and the named fault at the phase actually reached; if the carrier accepts
> it (it does not know the declared length), `O` ends before it, invalid with the host-recorded code `premature_operation`. No
> `X` exists unless P6 was sealed (section 6). (3) **A write is admitted per half.** In the standalone AXI-Lite configuration a
> master may deliver W before AW; v0.3 let W through unconditionally, the GSR cleared the acknowledged W and its later AW never
> got a response. Now, while the stall lasts, W is admitted only when its AW is outstanding (the beats of an accepted write —
> every AXI3 burst beat — still drain), AW only when its W was already accepted, and a W accepted ahead of its AW is outstanding
> and holds the launch (section 4). (4) The chain validates every source record's shape before traversing it: a malformed
> session_open, entry, `O` or `X` is a named finding and ends the chain there.

> **Standing: the carrier v2 engineering unit (the owner's authorisation of 2026-10-21 after the 2c-obs closure), delivered for
> one review.** It builds the observation contract `docs/b4_observation_contract.md` (v0.5, accepted as a document contract)
> into RTL, a bench, constraints and isolation checks, a host build, and the host side of the record flow — and it says, per
> condition A1–A8 of the architecture (§5.5), what the host has verified and what only a board can. Everything here is host-only:
> no board was powered, no production run, no change to `b4/`, to the pinned B1–B3 surfaces, to the hypothesis, to any threshold,
> archive, receipt, label or decision. The executing-side **firmware** (the PS application of B1's form) and the integration with
> the archived PCAP write / readback path are **not** in this unit (section 9).

## 0. The finding first: one CE, one SR, one CLK per slice

A 7-series slice has **one clock-enable pin, one set / reset pin and one clock pin shared by its eight storage elements** (the
site's BEL list has `CEUSEDVCC` and `SRUSEDGND`, one each). The task stimulus of task-v0.2 (`b4_landscape._stimulus`) and the
behaviour hypothesis model (`b4_ff_model._ce_ok`, `_sr_active`) treat `ce` and `sr` as **eight-bit per-element vectors**, drawn
independently per element. On the certified site those vectors are physically realisable **only when uniform** (all 0 or all 1).
The carrier therefore applies a `set` step only when both are uniform and refuses the rest by name (`F_NOT_REALISABLE`, sticky —
rtl/b4/b4_engine.v); it hides nothing and adapts nothing. Consequences, for the owner, not decided here:

- **task-v0.2 as specified is not executable on this site**: its search and holdout stimuli draw `ce` uniformly over 256 values
  and `sr` sparsely per element, so almost every step would be refused. A protocol under which the board study can run needs
  slice-wide `ce` / `sr` (one bit each per step), which is a task / model revision (task-v0.3) with its own ruling; this unit
  changes neither the task nor the model.
- **K9's discriminability record** was computed with per-element SR patterns; under slice-wide SR the distinguishability of
  `ff_srval` / `sr_kind` per address is a different quantity, to be recomputed under the revised protocol — the sim-4 record is
  not reinterpreted here.
- The bench fixtures of this unit use uniform vectors on purpose (tb/b4/gen_b4_fixture.py), so that the hypothesis model and
  the carrier agree on what was applied; they are mechanics fixtures, not task stimuli.

## 1. What was built

| piece | files | what it is |
|---|---|---|
| the target | `rtl/b4/b4_target_slice.v`, `vivado/b4/b4.xdc` | eight `FDPE` (the all-zero genome: INIT 1, SRVAL 1, asynchronous) + four pass-through `LUT6` at `SLICE_X2Y25`, every cell pinned to its BEL; CE and SR **connected** so the pins are routed (the loaded bitstream shows `CEUSEDMUX = SRUSEDMUX = 1`; the session root writes genome 0 as a signed candidate, contract 5.5) |
| the GSR-immune store | `rtl/b4/b4_gsr_reg.v`, `rtl/b4/b4_slot_ram.v`, `rtl/b4/b4_gsr_ram32.v` | `RAM32X1S` banks: the key (128 + 1), the nonce (64), fault + recovery (4 + 1), the armed latch (1), the engine's flags (10), `gsr_count` (8), indices (10), `base_state` (8), the pulse (4), 32 × 8-bit sample slots and 32 × 32-bit applied-input slots — 279 cells, none a flip-flop (isolation check) |
| the gate | `rtl/b4/b4_gate.v` (+ the verbatim `rtl/b1/p3_siphash.v`) | the B1 gate without the 64-vector sweep: SipHash-2-4-128 over commit ‖ zero tables ‖ nonce, the nonce stepping after every attempt, sticky faults — all of it persistent across the events; an ARM while armed, an ARM with the A5 flag and no injection open, or without the flag while one is open: F_SEQUENCE; `HW_COMMIT` a flip-flop register the host reads before `INIT_REQ` |
| the engine | `rtl/b4/b4_engine.v` | `PRE_SAMPLE`, `INIT_REQ` and `RESTORE_INIT` (the GSR sequence, launched only on a quiet bus, hardware-timed), `STEP` (the accepted command latched; control one cycle before data, settle, clock, hold, sample, the applied inputs recorded), `CLEANUP`, `CLOSE` (after the restore event only), `CLOSE_INJECTION` (the A5 exception); the realisability refusal; the witnesses |
| the AXI gate | `rtl/b4/b4_axi_gate.v` | VALID / READY masking while an event is pending, outstanding tracking (AW→B, AR→last R); one in front of the pinned shim (`b4_top`), one at the core's Lite port |
| the register file | `rtl/b4/b4_axil.v`, `host/b4carrier_regmap.py` | the v2 map (section 4); the one CTRL acceptance rule; `VARIANT = 0x42340001` |
| the top | `rtl/b4/b4_top.v`, `rtl/b4/b4_core.v` | PS7 + the instrument's AXI3→Lite shim (pinned, by reference) + `STARTUPE2` with `GSR` driven by the engine; no ICAPE2, no IO |
| the bench | `tb/b4/` (`b4_target_slice_model.v`, `gen_b4_fixture.py`, `tb_b4_core.v`, `tb_b4_unisim.v`, `tb_b4_axi3.v`), `sim/b4/run.sh` | the hypothesis v0.3 in Verilog as the bench's fabric; six model fixtures from the formal `b4_ff_model`; 27 core scenarios (the owner's reproductions among them, with the repaired expectations); the vendor-model bench over the RTL core and over the GSR-aware netlist of the core, the GSR pulse width measured; the PS path through the pinned AXI3 shim |
| the build | `vivado/b4/build_b4.tcl`, `resume_b4.tcl`, `isolation_checks_b4.tcl`, `netlist_core.tcl`, `builds/b4/` | routed (v0.4 rebuild), WNS +7.263 ns, target 12 / flush 0, RAM32X1S 279, STARTUPE2 1, ICAPE2 0; `b4.bit` sha256 `4e406f12…` (the file `resume_b4.tcl` writes from the routed checkpoint, recorded in `b4_build.json`); the post-synthesis out-of-context netlist of the core for the vendor bench (`b4_core_funcsim.json` records its digest and primitive counts) |
| the manifest | `host/b4carrier_manifest.py`, `builds/b4/b4_carrier_manifest.json` | the 21 certified addresses read back from the bitstream: all at their expected natural values (section 5) |
| the records | `host/b4carrier_records.py`, `tests/test_b4carrier_records.py` | `O` / `F` / `X` / `session_open` built from the register trace (the samples and the APPLIED inputs per slot, `BASE_STATE`) with the task's declared stimulus as input, `O` up to its terminal boundary only — the P6 seal established from the acquisition state (init done, every declared step applied), or the actual stop of a premature operation or fault — `X` from the engine's completion witnesses after the seal and never without it; validated in three layers — structure (closed at every level, typed, order-independent, the phase table governing the acquisitions), binding to a trusted context (instrument, session, stimulus, config, nonce, predecessor digest and seq, frame invariance, the fitness recomputed from the trusted task, the restored study-base reference), the chain (the session-opening record bound to the loaded-image reference and the instrument; every source record's shape validated before it is traversed) |

## 2. The initialisation mechanism: (b), GSR through STARTUPE2 — selected, with the reasons

| candidate (contract 6.2) | verdict | why |
|---|---|---|
| (c) configuration as the event | **not selected** | a configuration-frame write carries no *guaranteed, independent* restore of the storage elements: the line's own earlier raw-FDRI writes (without a GRESTORE command) left flip-flop state as it was. That is the absence of a mechanism to declare and time — not a claim that no frame write could ever change a Q |
| (a) a configuration-port restore command (GRESTORE through PCAP) | **not selected** | the same global effect as (b), but issued by host software through the archived PCAP path with software timing; the carrier could not time, witness or sequence it |
| **(b) GSR through STARTUPE2, raised by the carrier** | **selected** | the event is inside the transaction, hardware-timed (`ASSERT_DELAY`, the pulse, `RELEASE`, `SAMPLE_OFFSET`), witnessed (`gsr_count`, the heartbeat restart), and witnessed on the vendor models (tb_b4_unisim: the FDPEs return to INIT, the LUTRAM does not) |

**What GSR does to the carrier itself, and the design answer.** GSR returns every flip-flop of the PL to its INIT value — the
target elements (the point) and the carrier's own registers (the problem). Everything that must survive the event lives in LUTRAM
(section 1); the engine's own state machine is *meant* to be reset by the event: it wakes in its INIT state, finds `init_pending`
set and `init_done` clear in the store, counts `RELEASE` then `SAMPLE_OFFSET` cycles and takes the init sample. The slice inputs
and the slice clock are 0 after the event by the same reset — the permitted init context. The AXI shim is reset too, which is why
the host must issue no AXI access from the `INIT_REQ` write response until the engine is done (`QUIET` cycles, section 4): a
transaction in flight at the pulse would be dropped.

**The pulse (v0.2).** The generator is LUTRAM: a 4-bit thermometer word in `RAM32X1S`, loaded with PULSE ones by the engine's
`fire` and then shifting itself right once per clock (`11 → 01 → 00`), `STARTUPE2.GSR` = the OR of its bits. No flip-flop holds
the pulse, so the GSR it raises cannot shorten it (v0.1's flip-flop counter was reset by its own GSR — the owner's R5 model
comparison showed 40 ns in the RTL bench and 0.1 ns with vendor FDCEs; both benches now measure PULSE clocks = 40 ns on every
event, the RTL core and the GSR-aware netlist alike, `GSR_PULSE_WIDTHS_NS` in `sim/b4/out/*.result`). A thermometer and not a
binary count because a binary `2 → 1` changes two bits and the resolved global net showed a delta-cycle `1 → 0 → 1` inside the
pulse on the vendor bench — a hazard on an asynchronous reset net, removed. The launch waits for the bus (section 4). What the
pulse DOES on this die — release skew, the Q effect — stays **A8's board question**, and WNS is not evidence of it.

## 3. The transaction, as the carrier runs it (contract 5.1 ↔ CTRL operations)

| contract phase | who | the carrier operation | witness |
|---|---|---|---|
| session open | host (PCAP, manifest) | — (the carrier is loaded; `VARIANT`, `TIMING`, `WITNESS` read) | `session_open` (host record) |
| P1 sign / stage / re-read | host (PCAP) | the signed payload staged (`PAYLOAD`, `TAG`); `CTRL.arm` (with the A5 flag after an injection close, and only then) → the gate verifies, `armed` persisted, `HW_COMMIT` readable | STATUS `configuration_valid_hw`, `tag_ok`; FAULT 7 / 12 / 13 on refusal |
| P2 write + pre-event readback | host (PCAP) | — | link 3 (host) |
| P3 step 0 | carrier | `CTRL.pre_sample` → slot 0 and `IN_LIVE` (the held inputs under J3); `CTRL.init_req` → the GSR sequence → slot 1 | `init_done`, `gsr_count + 1`, the heartbeat restart, `IN_LIVE = 0` |
| P4 post-event readback | host (PCAP) | — | link 3 (host) |
| P5 steps 1 … n | carrier | per step: `STEP_IN` staged, `CTRL.step` → the command latched, applied, sampled into slot 2 + k with the applied inputs; `step_done`; a CTRL write while the step runs is SLVERR | FAULT 6 (not realisable), 7 (sequence), 8 (overflow) |
| P6a / P6b | host | `O` sealed from the slots and witnesses **at the P6 boundary**, established from the acquisition state (init done and every declared step applied; the seal is the first accepted P7+ operation after that, nothing after it enters `O`); a P7+ operation before P6 is premature and leaves `O` invalid at the phase actually reached; `F` from `O` under the trusted task (`b4carrier_records`) | `observation_sha256` |
| P7 cleanup | carrier | `CTRL.cleanup` → inputs 0, clock 0 (a recorded falling edge if it was 1), sample | `cleanup_done`, `cleanup_edge`, the cleanup slot |
| P8 base restore + readback | host (PCAP) | — | `X.base_readback_sha256` (host) |
| P9 base-state witness | carrier | `CTRL.restore_init` → the declared event on the restored base (the same launch rule), the sample into `BASE_STATE`; `gsr_count + 1` — **in this transaction**, the last one included | `restore_done`; `X.base_state_sample` = `BASE_STATE` |
| P10 close | carrier | `CTRL.close` (accepted only after `restore_done`) → `armed` and the flags cleared | STATUS `idle` = engine idle ∧ not armed ∧ no injection open ∧ inputs and clock 0 |
| the A5 exception | carrier | `CTRL.close_injection` (after the init event, no cleanup) → `injection_open` persisted, the inputs left as they are, `armed` cleared; the next ARM must carry the A5 flag; that transaction's `PRE_SAMPLE` records the held inputs and `pre_context_a5`; its `INIT_REQ` performs the recorded pre-init cleanup inside step 0 (contract 5.6 J3: inputs to 0, a falling edge if the clock was high, SETTLE + HOLD, then the launch — the event always enters with inputs and clock 0) and persists `pre_init_cleanup` | STATUS bit 14; WITNESS bits 25, 27 |

The A5 injection protocol of the contract (5.6) is the one explicit exception: J2 closes with `CLOSE_INJECTION`, J3 arms with
the A5 flag and its `PRE_SAMPLE` records the held inputs and the injected state; an ordinary ARM after an injection close, or
an A5-flagged ARM with none open, is F_SEQUENCE (`a5_wrong_context`, `a5_flag_without_injection`); the bench's `a5` and
`a5_persist` scenarios produce the pass and the persistence data (the latter on the hypothesis-swap fabric `init_no_effect`).

**The bootstrap reference, in its own hash domain.** Three things are distinct and the contract's `session_open` compares the
first against the second only: (i) the **loaded carrier's frame image** of the target column — the natural build, `CEUSEDMUX =
SRUSEDMUX = 1`, whose *frame-content* digest is what the manifest records per frame (`builds/b4/b4_carrier_manifest.json`,
`target_column_frames_sha256`) and what the startup readback over the PCAP path must reproduce; (ii) the pinned reference of
that same content, derived from the manifest before the session; (iii) the **signed base genome 0** the session root then
writes as a candidate (links 1–3), which differs from (i) in exactly the two mux bits. A frame-table digest and a bitstream-file
digest are different commitments again and bind nothing about Q. This clarification is carried into the contract's 5.5 as the
owner allowed; it changes no task, model, method, threshold or evidence. **In the record layer** (v0.4) the trusted context
carries (ii) as `loaded_frames_reference_sha256`, which `session_open` binds, and the readback of the restored study base —
(iii), the P8 readback every closed `X` names — as `base_readback_sha256`; they differ in the two mux bits, live in their own
hash domains and are never compared to each other (`validate_chain`, `validate_bound`).

## 4. The MMIO interface (rtl/b4/b4_axil.v; the table of record is host/b4carrier_regmap.py)

The instrument's eight stable words keep their offsets; the staging, tag, key and `HW_COMMIT` windows are B1's; the sweep readout
window is gone. New: `Q_LIVE` 0x2010, `IN_LIVE` 0x2014, `SLOT_READ` 0x2018, `SLOT_ADDR` 0x201C, `WITNESS` 0x2020 (`gsr_count`,
mechanism 2, PULSE, `restore_pending`, `pre_context_a5`, `stall`, `pre_init_cleanup`), `TIMING` 0x2024, `STEP_IN` 0x2038, `BASE_STATE` 0x203C,
`SLOT_IN_READ` 0x2040 (the inputs applied at a sample). CTRL: bit 6 arm (bit 7 the A5 context flag, with bit 6 only), bit 8
key_commit, bits 9–15 the engine's seven operations. **One acceptance rule**: a CTRL write is accepted only when the engine and
the gate are idle, exactly one operation is named and no other bit is set — otherwise SLVERR and nothing changes, so a busy or
combined command neither half-applies nor disappears (`busy_refused`, `regs`). Undecoded addresses are SLVERR on read and on
write (the P2 allowlist rule). The allowlist check (`tests/test_b4carrier_regmap.py`) holds the **declared register table** to
the RTL decode: app reads = RTL reads, app writes = RTL writes minus the key window, the fault codes, CTRL bits and STEP_IN
packing as the RTL has them — it is a check of this table, not of a PS application's accesses (none is delivered here).

**The bus and the event.** The two AXI gates (`b4_axi_gate`) make the launch safe without any host timing assumption: from the
accepted `INIT_REQ` / `RESTORE_INIT` the gates hide new AW / AR from the slaves and their readies from the master (the PS
simply holds its VALID). **A write is admitted per half** (v0.4): W is admitted while a write address is outstanding — the
beats of an accepted write always drain (the owner's two-beat FIXED write with `INIT_REQ` in beat 1 deadlocked v0.2: the stall
hid the remaining beat while the engine waited for that burst's B; `tb_b4_axi3` drives such bursts with the request in beat 1
and in beat 2 — one event, the burst's response delivered); a W with no outstanding address — an AXI-Lite master's W-first
transfer — is held, never acknowledged into storage the GSR would clear (the owner's standalone reproduction of v0.3: the
acknowledged W was lost and its later AW never answered; `w_first`); AW is admitted when its W was already accepted, and such
an early W is outstanding, so the launch waits for that write's response (`w_first_early`: a W taken in the cycle between
INIT_REQ's response and the rising stall). Under the shim only the outer gate masks; the
core's Lite gate tracks outstanding transfers without masking (`LITE_STALL = 0`, since every Lite transfer there is a beat of a
transaction the outer gate admitted). The engine fires only after ASSERT_DELAY consecutive cycles in which nothing is outstanding on
either path — a response the master has not taken yet is delivered first, whatever BREADY does (`backpressure`, through the
shim in `tb_b4_axi3`); a read presented during the window is held and served afterwards (`read_during_window`,
`read_at_launch` at every offset around the launch cycle). The host's quiet window of v0.1 is therefore no longer a correctness
requirement; polling right away is legal and merely waits at the bus.

**Timing (the identity page's `TIMING` and `WITNESS` words; cycles of FCLK0 = 50 MHz):** `ASSERT_DELAY` 8 (quiet cycles before the
launch), `PULSE` 2, `RELEASE` 16, `SAMPLE_OFFSET` 4, `SETTLE` 4, `HOLD` 4. These are **declared values for the bench and the
build**; the contract fixes that they exist and are recorded — their adequacy for silicon is the qualification session's to show.

## 5. The sampling path and the placement — host-verified on the routed design

`builds/b4/isolation.txt`: the twelve target cells at `SLICE_X2Y25` on their BELs; the x5FF elements' D enters the site through
`AX / BX / CX / DX`, the main elements' D is their LUT6's O6; every Q leaves through `AQ … DQ` and `AMUX … DMUX`; `CLK`, `CE`
and `SR` driven by the engine's nets. `builds/b4/b4_carrier_manifest.json`: at the 21 certified addresses the bitstream holds
`ce_mode = sr_mode = 1` and every other bit 0 — the natural values of this design at exactly those addresses, which is the
known-answer that the elements are where the certificate's addresses say. What this does **not** show: that a Q sample is
*meaningful* in every configuration (a latch's x5FF, 3.4 of the contract) — the carrier samples a physical value there, and
the bench's fabric has none (the record tests show that refusal).

## 6. Verification record (the unit README has the fresh-process outputs)

| what | where | result |
|---|---|---|
| the verbatim SipHash bench | `sim/b4/run.sh` | TB_PASS |
| 27 core scenarios over the hypothesis model: regs (incl. the CTRL rule), flow (six fixtures, two events per transaction, persistence, the replay refused after a reset), seven named refusals incl. the prefix retention, the A5 pass / persistence / wrong-context cases (the GSR entry context checked at every assertion), `open_close_refused`, `p9` / `p9_ok`, `busy_refused`, `step_atomic`, `backpressure`, `read_during_window`, `read_at_launch`, `session` (the zero-finding root → candidate chain), `post_fault` (CLOSE refused after P6: O sealed, X faulted), `w_first` (a W-first transfer during the pending event held, then answered once), `w_first_early` (a W taken just before the stall rises: the launch waits for its write), `early_cleanup` (CLEANUP before INIT_REQ: refused, O invalid at P3, no X) | `sim/b4/run.sh`, `sim/b4/out/*.result` | all TB_PASS |
| the vendor-model bench over the RTL core and over the GSR-aware post-synthesis netlist of the core; the GSR width measured | `sim/b4/run.sh` | TB_PASS, 40 ns on every event, both |
| the PS path through the pinned AXI3 shim (backpressure, a stalled read, a full transaction, two-beat FIXED bursts at CTRL with the event request in beat 1 and in beat 2) | `tb/b4/tb_b4_axi3.v` | TB_PASS |
| the register table vs the RTL decode; the records from the bench traces incl. every owner counterexample (rounds 2 and 3), the serialization round trip, the zero-finding session chain from the bench, the sealed observation under a post-P6 fault; the benches | `tests/test_b4carrier_*.py` | OK |
| the mutant battery (21 RTL + 10 host, hermetic) | `evidence/b4/unit_carrier_v2_2026_10_21/mutants/` | the unit README |
| the Vivado build and the isolation checks | `builds/b4/` | routed, WNS +7.426 ns, every verdict OK |
| the bitstream known-answer at the 21 addresses | `builds/b4/b4_carrier_manifest.json` | no mismatch |

## 7. A1–A8: what the host has verified, what only a board can

| condition | host-verified in this unit | needs the board (B4Q, its own ruling) |
|---|---|---|
| A1 one transaction, the instrument's links | the carrier's part of every phase P1–P10 on the bench, the current transaction's P9 included; the refusal of an ARM while armed; the close only after the restore event; the PS path through the shim incl. multi-beat bursts; `O` sealed at P6 and `X` from the engine's completion, never from a bus acknowledgement | the PCAP links 1–3 around it (the archived host path, mocked by symbolic but consistent values on the bench; the firmware) |
| A2 positive controls | — (the bench's fabric is the hypothesis) | the nine pairs of the contract 7.3 |
| A3 the raw observation validates against a schema forbidding an expected value | the record layer's closed, typed schemas at every level over the bench's own records and the owner's counterexamples (both rounds); the binding to a trusted context incl. the session-opening record, the seq reconciliation and the fitness recomputed from the trusted task — **partially**: the schema files themselves and the firmware that would emit records are not delivered, so A3 is verified for the host validator, not for an executing-side producer | the producer's side |
| A4 readback contract, identity, `VARIANT` extended | `VARIANT = 0x42340001` read, not writable; the stable words at their offsets; the key write-once and persistent | the identity over the PS path |
| A5 isolation between candidates | the protocol J1–J3 on the bench as the explicit exception: `CLOSE_INJECTION`, the A5-flagged ARM, the held context recorded; the recorded pre-init cleanup inside step 0 so the event enters with inputs and clock 0 (checked at every GSR assertion on the bench, witnessed in the record); the injection witnessed, cleared (pass) and persisting (fail data) | the same on silicon with the plan's *c′* |
| A6 the bench reproduces B1's scenarios that still apply + one per 5.2 row + the contract's own | alive, SLVERR, write-once key, no-key, replay, unsigned, wrong commit, wrong key; the six fixtures cover init, SR level and sync, CE gating, inversion, latch transparency, the all-ones genome; the cleanup, the restore event, the realisability refusal, the prefix retention, the bus cases — **partially**: the bench's fabric is the hypothesis model, uniform vectors only; the holdout-indifference scenario of the contract is not written | — |
| A7 MMIO allowlist = RTL decode, mismatches only | `tests/test_b4carrier_regmap.py`: the **declared register table** against the RTL decode (no mismatch) — not an actual PS application's accesses; no firmware is delivered | the firmware's accesses against the same table |
| A8 the two restore mechanisms on the board | the mechanism selected, declared, hardware-timed (LUTRAM) and witnessed on the vendor models and on the GSR-aware netlist of the core (the FDPEs return to INIT under the carrier's GSR; the pulse PULSE clocks wide) | the event-to-Q effect on this die, release skew, the same-element cross |

## 8. Unresolved — named

1. **The per-element `ce` / `sr` of task-v0.2 and of the model** against one CE / SR pin per slice (section 0): an owner decision
   on the protocol; the carrier refuses what it cannot apply. *Taken up (2026-10-27): the owner's ruling opened the task-v0.3 revision
   unit — the task produces one slice-wide CE / SR value per step, broadcast in the same 8-bit grammar (`docs/b4_architecture.md` §7.2);
   this carrier, its register map and its records are unchanged, and the realisability refusal stays as an invariant the task never hits.*
2. **A8** and the GSR pulse width on silicon (section 2).
3. **The firmware** (the executing-side program of the register sequence; `host/b4carrier_regmap.py` is its table) and the
   integration of links 1–3 (the archived PCAP write / readback path) and of the session-opening readback with the carrier's
   transaction: a later unit; this unit's bench drives the register interface directly.
4. **P8's base write and readback** are the host's (PCAP) between `CLEANUP` and `RESTORE_INIT`; the carrier cannot see them and
   the host's readback is the witness (resolved in design: P9 is the carrier's own event and sample).
5. **The contract's `fabric_readback_sha256_*`, `commit`, `staging_readback_sha256`, `instrument`, `session_open`** come from the
   PCAP path and the manifest; the record builder takes them as inputs (symbolic on the bench).
6. **Sampling meaning in every configuration** (contract 3.4): the carrier samples a value everywhere; whether it is a storage
   element's state is the hypothesis's question, unverified on silicon.

## 9. What this unit does not do

No board was powered; no production run, seed, label or gate; nothing under `b4/`, `host/b1*`, `host/b2*`, `host/b3*`, `b3/`,
`firmware/`, `manifests/`, the certificates or the archives changed; the hypothesis, the thresholds, the no-go and every
historical decision stand; task-v0.2, the model and the K9 record are not revised (section 0 states the consequence; the
decision is the owner's). The firmware, the PCAP integration, the B4Q plan, push and merge are outside it. The PCAP-side values
in the bench's records are symbolic and mutually consistent, never physical links proved.

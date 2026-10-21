# B4 carrier v2 — design, mechanism selection, sampling path, interface and acceptance (v0.1, host-only, 2026-10-21)

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
| the GSR-immune store | `rtl/b4/b4_gsr_reg.v`, `rtl/b4/b4_slot_ram.v` | `RAM32X1S` banks: the key (128 + 1), the nonce (64), fault + recovery (4 + 1), the armed latch (1), the engine's flags (6), `gsr_count` (8), indices (10), 32 × 8-bit sample slots — 231 cells, none a flip-flop (isolation check) |
| the gate | `rtl/b4/b4_gate.v` (+ the verbatim `rtl/b1/p3_siphash.v`) | the B1 gate without the 64-vector sweep: SipHash-2-4-128 over commit ‖ zero tables ‖ nonce, the nonce stepping after every attempt, sticky faults — all of it persistent across the init event; `HW_COMMIT` a flip-flop register the host reads before `INIT_REQ` |
| the engine | `rtl/b4/b4_engine.v` | `PRE_SAMPLE`, `INIT_REQ` (the GSR sequence, hardware-timed), `STEP` (control one cycle before data, settle, clock, hold, sample), `CLEANUP`, `CLOSE`; the realisability refusal; the witnesses |
| the register file | `rtl/b4/b4_axil.v`, `host/b4carrier_regmap.py` | the v2 map (section 4); `VARIANT = 0x42340001` |
| the top | `rtl/b4/b4_top.v`, `rtl/b4/b4_core.v` | PS7 + the instrument's AXI3→Lite shim (pinned, by reference) + `STARTUPE2` with `GSR` driven by the engine; no ICAPE2, no IO |
| the bench | `tb/b4/` (`b4_target_slice_model.v`, `gen_b4_fixture.py`, `tb_b4_core.v`, `tb_b4_unisim.v`), `sim/b4/run.sh` | the hypothesis v0.3 in Verilog as the bench's fabric; six model fixtures from the formal `b4_ff_model`; 12 scenarios; the vendor-model GSR witness |
| the build | `vivado/b4/build_b4.tcl`, `resume_b4.tcl`, `isolation_checks_b4.tcl`, `builds/b4/` | routed, WNS +8.173 ns, target 12 / flush 0, RAM32X1S 231, STARTUPE2 1, ICAPE2 0; `b4.bit` sha256 `cbf5f95c…` |
| the manifest | `host/b4carrier_manifest.py`, `builds/b4/b4_carrier_manifest.json` | the 21 certified addresses read back from the bitstream: all at their expected natural values (section 5) |
| the records | `host/b4carrier_records.py`, `tests/test_b4carrier_records.py` | `O` / `F` / `X` / `session_open` built from the register trace and validated against the contract's closed sets |

## 2. The initialisation mechanism: (b), GSR through STARTUPE2 — selected, with the reasons

| candidate (contract 6.2) | verdict | why |
|---|---|---|
| (c) configuration as the event | **rejected** | a configuration-frame write without a GRESTORE command leaves flip-flop state as it is (the line's own earlier finding on raw FDRI writes); it has no event-to-Q effect to demonstrate |
| (a) a configuration-port restore command (GRESTORE through PCAP) | **not selected** | the same global effect as (b), but issued by host software through the archived PCAP path with software timing; the carrier could not time, witness or sequence it |
| **(b) GSR through STARTUPE2, raised by the carrier** | **selected** | the event is inside the transaction, hardware-timed (`ASSERT_DELAY`, the pulse, `RELEASE`, `SAMPLE_OFFSET`), witnessed (`gsr_count`, the heartbeat restart), and witnessed on the vendor models (tb_b4_unisim: the FDPEs return to INIT, the LUTRAM does not) |

**What GSR does to the carrier itself, and the design answer.** GSR returns every flip-flop of the PL to its INIT value — the
target elements (the point) and the carrier's own registers (the problem). Everything that must survive the event lives in LUTRAM
(section 1); the engine's own state machine is *meant* to be reset by the event: it wakes in its INIT state, finds `init_pending`
set and `init_done` clear in the store, counts `RELEASE` then `SAMPLE_OFFSET` cycles and takes the init sample. The slice inputs
and the slice clock are 0 after the event by the same reset — the permitted init context. The AXI shim is reset too, which is why
the host must issue no AXI access from the `INIT_REQ` write response until the engine is done (`QUIET` cycles, section 4): a
transaction in flight at the pulse would be dropped.

**The pulse width (unresolved, board).** In silicon the register that drives `STARTUPE2.GSR` is itself reset by the GSR it
raises: the pulse is self-timed, its width the GSR tree's delay (`WITNESS` bit 16 says so). On the bench the generator holds the
drive for `PULSE` cycles so the vendor models see a clean pulse; both end with the generator cleared and the engine in its reset
state. Whether the self-timed pulse reliably reaches every element on this die is **A8's board question**, like the mechanism's
Q effect itself.

## 3. The transaction, as the carrier runs it (contract 5.1 ↔ CTRL operations)

| contract phase | who | the carrier operation | witness |
|---|---|---|---|
| session open | host (PCAP, manifest) | — (the carrier is loaded; `VARIANT`, `TIMING`, `WITNESS` read) | `session_open` (host record) |
| P1 sign / stage / re-read | host (PCAP) | the signed payload staged (`PAYLOAD`, `TAG`); `CTRL.arm` → the gate verifies, `armed` persisted, `HW_COMMIT` readable | STATUS `configuration_valid_hw`, `tag_ok`; FAULT 12 / 13 on refusal |
| P2 write + pre-event readback | host (PCAP) | — | link 3 (host) |
| P3 step 0 | carrier | `CTRL.pre_sample` → slot 0 and `IN_LIVE` (the held inputs under J3); `CTRL.init_req` → the GSR sequence → slot 1 | `init_done`, `gsr_count + 1`, the heartbeat restart, `IN_LIVE = 0` |
| P4 post-event readback | host (PCAP) | — | link 3 (host) |
| P5 steps 1 … n | carrier | per step: `STEP_IN`, `CTRL.step` → slot 2 + k; `step_done` | FAULT 6 (not realisable), 7 (sequence), 8 (overflow) |
| P6a / P6b | host | `O` sealed from the slots and witnesses; `F` from `O` under the task (`b4carrier_records`) | `observation_sha256` |
| P7 cleanup | carrier | `CTRL.cleanup` → inputs 0, clock 0 (a recorded falling edge if it was 1), sample | `cleanup_done`, `cleanup_edge`, the cleanup slot |
| P8 base restore + readback | host (PCAP) | — | `X.base_readback_sha256` (host) |
| P9 base-state witness | carrier + host | a second signed transaction on the base is **not** needed: the host reads `Q_LIVE` after P8 and the event of the next transaction's step 0 is the mechanism on the base — see section 9, item 3 | `X.base_state_sample` |
| P10 close | carrier | `CTRL.close` → `armed` cleared, the flags cleared, `closed_without_cleanup` kept for the next record (the A5 injection path) | STATUS `idle`, bit 14 |

The A5 injection protocol of the contract (5.6) runs without any special mode: J2 is a normal transaction closed without
cleanup (the witness bit), J3 is a normal transaction whose `PRE_SAMPLE` records the held inputs and the injected state; the
bench's `a5` and `a5_persist` scenarios produce the pass and the persistence data (the latter on the hypothesis-swap fabric
`init_no_effect`).

## 4. The MMIO interface (rtl/b4/b4_axil.v; the table of record is host/b4carrier_regmap.py)

The instrument's eight stable words keep their offsets; the staging, tag, key and `HW_COMMIT` windows are B1's; the sweep readout
window is gone. New: `Q_LIVE` 0x2010, `IN_LIVE` 0x2014, `SLOT_READ` 0x2018, `SLOT_ADDR` 0x201C, `WITNESS` 0x2020 (`gsr_count`,
mechanism 2, self-timed), `TIMING` 0x2024, `STEP_IN` 0x2038. CTRL bits 9–13 are the engine's five operations. Undecoded
addresses are SLVERR on read and on write (the P2 allowlist rule). The MMIO allowlist check (`tests/test_b4carrier_regmap.py`):
app reads = RTL reads, app writes = RTL writes minus the key window, the fault codes and CTRL bits as the RTL has them.

**Timing (the identity page's `TIMING` word; cycles of FCLK0 = 50 MHz):** `ASSERT_DELAY` 8, `RELEASE` 16, `SAMPLE_OFFSET` 4,
`SETTLE` 4, `HOLD` 4; the bench's `PULSE` 2. The host's quiet window after `INIT_REQ`: at least ASSERT_DELAY + PULSE + RELEASE +
SAMPLE_OFFSET cycles plus margin (the bench uses + 16). These are **declared values for the bench and the build**; the contract
fixes that they exist and are recorded — their adequacy for silicon is the qualification session's to show.

## 5. The sampling path and the placement — host-verified on the routed design

`builds/b4/isolation.txt`: the twelve target cells at `SLICE_X2Y25` on their BELs; the x5FF elements' D enters the site through
`AX / BX / CX / DX`, the main elements' D is their LUT6's O6; every Q leaves through `AQ … DQ` and `AMUX … DMUX`; `CLK`, `CE`
and `SR` driven by the engine's nets. `builds/b4/b4_carrier_manifest.json`: at the 21 certified addresses the bitstream holds
`ce_mode = sr_mode = 1` and every other bit 0 — the natural values of this design at exactly those addresses, which is the
known-answer that the elements are where the certificate's addresses say. What this does **not** show: that a Q sample is
*meaningful* in every configuration (a latch's x5FF, 3.4 of the contract) — the carrier samples a physical value there, and
the bench's fabric has none (the record tests show that refusal).

## 6. Verification record

| what | where | result |
|---|---|---|
| the verbatim SipHash bench | `sim/b4/run.sh` | TB_PASS |
| 12 core scenarios over the hypothesis model (regs; flow over six fixtures with persistence, nonce chain, replay refused after a reset; seven named refusals incl. the prefix retention; A5 pass; A5 persistence data) | `sim/b4/run.sh`, `sim/b4/out/*.result` | 12 × TB_PASS |
| the vendor-model bench (FDPE / RAM32X1S / STARTUPE2 / glbl) | `sim/b4/run.sh` | TB_PASS |
| the register map against the RTL decode; the records from the bench traces; the benches | `tests/test_b4carrier_*.py` | OK |
| the mutant battery (12 RTL mutants, 6 host mutants, hermetic on a temporary copy) | `evidence/b4/unit_carrier_v2_2026_10_21/mutants/` | see the unit README |
| the Vivado build and the isolation checks | `builds/b4/` | routed, WNS +8.173 ns, every verdict OK |
| the bitstream known-answer at the 21 addresses | `builds/b4/b4_carrier_manifest.json` | no mismatch |

## 7. A1–A8: what the host has verified, what only a board can

| condition | host-verified in this unit | needs the board (B4Q, its own ruling) |
|---|---|---|
| A1 one transaction, the instrument's links | the carrier's part of every phase on the bench, the refusal of an ARM while armed, the close | the PCAP links 1–3 around it (archived host path; the firmware) |
| A2 positive controls | — (the bench's fabric is the hypothesis) | the nine pairs of the contract 7.3 |
| A3 the raw observation validates against a schema forbidding an expected value | the closed-set validator over the bench's own records; an extra key, a null cell, a float cell, a deny-listed key, a later-phase key each refused | — |
| A4 readback contract, identity, `VARIANT` extended | `VARIANT = 0x42340001` read, not writable; the stable words at their offsets; the key write-once and persistent | the identity over the PS path |
| A5 isolation between candidates | the protocol J1–J3 on the bench: injection witnessed, cleared (pass) and persisting (fail data) | the same on silicon with the plan's *c′* |
| A6 the bench reproduces B1's scenarios that still apply + one per 5.2 row + the contract's own | alive, SLVERR, write-once key, no-key, replay, unsigned, wrong commit, wrong key; the six fixtures cover init, SR level and sync, CE gating, inversion, latch transparency, the all-ones genome; the cleanup, the two-event witness, the realisability refusal, the prefix retention | — |
| A7 MMIO allowlist = RTL decode, mismatches only | `tests/test_b4carrier_regmap.py` (no mismatch) | — |
| A8 the two restore mechanisms on the board | the mechanism selected, declared, timed and witnessed on the vendor models (the FDPEs return to INIT under the carrier's GSR) | the event-to-Q effect on this die, the same-element cross, the self-timed pulse |

## 8. Unresolved — named

1. **The per-element `ce` / `sr` of task-v0.2 and of the model** against one CE / SR pin per slice (section 0): an owner decision
   on the protocol; the carrier refuses what it cannot apply.
2. **A8** and the GSR pulse width on silicon (section 2).
3. **The firmware** (the executing-side program of the register sequence; `host/b4carrier_regmap.py` is its table) and the
   integration of links 1–3 (the archived PCAP write / readback path) and of the session-opening readback with the carrier's
   transaction: a later unit; this unit's bench drives the register interface directly.
4. **P9's base-state witness** needs a readback and a sample on the restored base without a second signed transaction: the host
   reads `Q_LIVE` after the base write (the carrier exposes it) — whether a dedicated base-state operation (with its own event) is
   wanted instead is a design question for the B4Q plan.
5. **The contract's `fabric_readback_sha256_*`, `commit`, `staging_readback_sha256`, `instrument`, `session_open`** come from the
   PCAP path and the manifest; the record builder takes them as inputs (symbolic on the bench).
6. **Sampling meaning in every configuration** (contract 3.4): the carrier samples a value everywhere; whether it is a storage
   element's state is the hypothesis's question, unverified on silicon.

## 9. What this unit does not do

No board was powered; no production run, seed, label or gate; nothing under `b4/`, `host/b1*`, `host/b2*`, `host/b3*`, `b3/`,
`firmware/`, `manifests/`, the certificates or the archives changed; the hypothesis, the thresholds, the no-go and every
historical decision stand. The firmware, the PCAP integration, the B4Q plan, push and merge are outside it.

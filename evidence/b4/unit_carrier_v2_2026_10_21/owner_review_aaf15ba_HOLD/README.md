# Owner review of aaf15ba — HOLD

2026-10-21. Reviewed `aaf15ba` on `b4-carrier-v2`, including WIP parent `bf54a3b` and original delivery `823f5b0`. This is an independent review of the existing carrier engineering unit. **HOLD: five remaining items below, to repair together in this same unit.** No tracked source, ref, board, production draw or archive was changed by the reviewer.

## Independent checks and accepted progress

- Exported the necessary committed source with `git archive` into the root recorded in `snapshot.json`. Independently regenerated the GSR-aware **out-of-context core netlist from those sources** using `vivado/b4/netlist_core.tcl`, Vivado 2025.2: 1970 flip-flops and 278 RAM32X1S; zero errors / critical warnings. The log and generated metadata are retained. This is a fresh synthesis, not a fresh full routed carrier build or a physical timing simulation. Generated netlist bytes differ from the historical file digest; this review does not claim byte identity.
- In that root, ran the three host modules: **25 tests OK, no skip**, including the complete simulation runner. It runs **22 core scenarios + SipHash + vendor RTL + AXI3 shim + vendor netlist = 26 TB_PASS results**. Both vendor benches report three 40 ns GSR pulses. The regenerated fixed mechanics fixture is byte-identical to the committed header. No production seed/task schedule was derived.
- B1 pins: **3 tests OK**. Recomputed the manifest over the committed bitstream: **21 addresses match**; bitstream SHA256 `52f2ea56fddd6268ce6a3b5adcf9aede9d1ab953dc8d1e75b653054524178745` agrees with the build record. Inspected the routed reports (WNS 7.426 ns, target 12, flush 0, RAM278, STARTUPE2 1, ICAPE2 0), without claiming this establishes physical sampling or GSR release timing.
- Protected scientific and historical paths compared against `fceedd6`: no changes (`protected_paths.txt`). Previous owner review copy: all **31 files including SHA256SUMS**, byte-identical. Checkout was clean before and remains clean after this review.
- The current-transaction RESTORE_INIT / BASE_STATE path, latched STEP, explicit injection/ARM context, busy-command SLVERR, and LUTRAM thermometer pulse are substantial improvements. The original single-beat backpressure reproduction now passes, including through the shim. The new OOC netlist bench addresses the earlier controller/GSR model-fidelity objection. Physical A8 remains open, as disclosed.
- Shared CE/SR/CLK finding remains accepted. No task/model/K9 revision is authorized by this engineering review; existing host results and no-go stand.

## R1 — P1: accepted AXI3 burst cannot drain across INIT_REQ

Code: `rtl/b4/b4_axi_gate.v:29–45`, the two gates in top/core, engine S_LAUNCH. Reproducer: `axi_burst_probe.py`, raw output `axi_burst_probe.txt`.

Through the **actual pinned AXI3 shim and both gates**, submit a legal two-beat FIXED write at CTRL: first beat INIT_REQ, second beat the same command (the duplicate may be refused, but its bus transaction must finish). After beat 1, init_pending makes both gates mask every W. The outer gate still has the accepted burst outstanding and the shim is waiting for beat 2. The engine waits for that burst's B handshake before GSR. After 200 cycles:

```
stall=1 ps_quiet=0 shim_state=4 WVALID=1 WREADY=0 BVALID=0 gsr_count=0 lite_quiet=1
```

This is a deterministic circular wait, not BREADY backpressure imposed by the master. Current shim bench is single-beat only. Tracking AW→B and blocking all W treats the remainder of an accepted transaction as a new request.

Repair the event/bus boundary so every already accepted transaction can drain or receive a defined complete error before GSR. Account for the whole burst and both gates; merely allowing W at the outer gate while blocking the corresponding Lite transfers is insufficient. Also cover independently timed AW/W where applicable. Keep the pinned shim source unchanged. Add bounded progress checks for an event request within a burst, plus the existing held-BREADY and pending-read checks. A software preference for single-beat MMIO does not justify hanging an accepted AXI3 transaction.

## R2 — P1: bus write acceptance is still confused with CLOSE success; O is not phase-scoped

Code: `host/b4carrier_records.py` observation builder (last WITNESS, fault scan), `_accepted_ctrl`, `transaction_close:323–344`. Reproducers: `record_probes.py`, **`phase_probe.py` with actual RTL/MMIO**, `phase_probe_results.json`, `phase_probe_mmio.jsonl`.

1. From the real second `flow` transaction, O built at P6 is structurally valid with `gsr_count_after=3`. Building from the same complete transaction after P9 gives `gsr_count_after=4`, also accepted, and a different O digest. The latter counts the base restore as the observation's init witness. The existing record tests build O from whole transactions, so this is a used path, not an invented input.
2. A new real RTL scenario completes a valid observation, then issues normal CLOSE **before** cleanup/restore. RTL correctly latches F_SEQUENCE and remains unclosed. At P6 the O is complete with zero findings. Rebuilding from the retained trace after the fault changes it to **invalid, phase P5**, although the fault happened after P6. Passing the correctly sealed P6 O to `transaction_close` raises `RecordRefusal: a closed X needs ...`: `_accepted_ctrl` considers the CTRL bus OKAY an accepted CLOSE and takes the closed branch before considering the actual fault. There is no retained faulted X for this ordinary failed-close path.

Separate MMIO request acknowledgement from engine-operation completion. Establish an explicit P6 boundary/snapshot for O and its init witness; later P7–P10 events and faults must not rewrite O or its digest. Construct X from phase/completion/fault witnesses, retaining its actual stop location rather than guessing P7 versus P9 only from cleanup_done. An explicit sealed-prefix API/orchestrator is acceptable; no full firmware or physical PCAP integration is required. Verify a successful transaction and a post-P6 failed CLOSE through actual register traces, serialization and revalidation, with O unchanged and faulted X retained.

## R3 — P1: claimed trusted-reference / chain / fitness binding is incomplete

Code: `validate_session_open`, `validate_bound:522–557`, `validate_chain:561–580`. Exact cases in `record_probe_results.json`; all return **zero findings** at present.

- A proper init-only root followed by a candidate validates. Replace session_open.carrier_sha256 with another carrier and replace **both** startup/reference digests with an arbitrary equal pair: the same chain still validates. O's instrument is checked against ctx, but session_open's instrument and pinned frame reference are not. Two agreeing self-declared hashes are not a trusted reference.
- `X.seq=999` for `O.seq=1` passes. A candidate naming predecessor.seq=999 while its predecessor digest actually names X.seq=1 also passes (including the proper root→candidate case). The digest does not make contradictory identity fields true.
- A structurally valid F with the correct trusted task digest and `fitness=999` passes `validate_bound`, although the two-cell fixture's correct score is 1. The binding API receives only the task digest, not the trusted task needed to verify the score. Hash linkage alone is not fitness revalidation.

Finish the contextual validation entry point: bind session_open to the manifest's instrument and independently pinned loaded-frame reference; reconcile O/X/predecessor identities and ordering; bind the task contents/digest and recompute F over the full physical grid. Keep loaded image, signed root genome and restored-base commitments distinct. A context with symbolic but internally correct PCAP witnesses is sufficient for these host tests. Provide one **zero-finding** opening → init-only root → candidate → current close path through fresh serialization and this full validation entry point. Existing flow tests that accept expected null findings from the model do not substitute for that valid chain. Do not convert model nulls to pretend physical samples to get it.

## R4 — P2: phase/type/relationship schema checks still admit contradictory records

Code: O_COMMON/O_PHASE and `validate_observation`, CLEANUP_STEP and `validate_close`, `validate_chain` before its structural checks. Reproducer: `record_probes.py`.

- An invalid O stopped at **P2**, with `initial` and the post-event readback removed but **two future init/set steps retained**, validates. The phase table must determine which acquisition fields can exist, not merely which readback keys are present. The accepted contract's P1/P2 absent/prefix rules must hold.
- A complete O ends clock=1, but X claims cleanup.clock_before=0, clock_after=0, edge=null (no falling edge): `validate_bound` accepts it. Cleanup must continue the actual observation's final clock and obey the declared cleanup transition.
- Cleanup zeros changed to `ce=false`, `sr=0.0`, `d=false`, `clock_after=0.0` pass because `_t_enum(0)` uses Python equality. These fields are integer inputs, and the delivery claims exact types.
- A chain entry with O=[] raises AttributeError before reaching the otherwise total O validator.

Apply the existing schema discipline at these boundaries: phase-dependent acquired fields, cleanup continuity/edge consistency, exact integer constants, and named findings for malformed record objects at the public chain entry point. Target the concrete cases above; no broad numeric-fuzz campaign or full-project proof is requested.

## R5 — P2: A5 J3 omits the accepted pre-init cleanup and its witness

Code: engine PRE_SAMPLE → INIT_REQ → S_LAUNCH; INIT_PARAMS in the host record schema. Contract **5.6 J3** requires mechanisms (a)/(b), after the actual held-input pre-init sample, to set inputs/clock to zero by a **recorded cleanup-like operation inside step 0's context**, marked `init_event.parameters.pre_init_cleanup=true`.

`a5_context_probe.py` adds only a monitor to the committed A5 bench. At the J3 GSR assertion it reports:

```
OWNER_EVENT_PRE_RESET clk=1 ce=1 sr=0 d=0 gsr_count=3
```

The inputs become zero because GSR resets the engine itself, not because the required pre-event cleanup was executed and witnessed. The builder unconditionally presents the init step with clock_before=0; INIT_PARAMS cannot even represent pre_init_cleanup. The A5 benchmark's final Q match does not establish that intervening sequence.

Implement and record the contract's ordering: actual held-input/Q witness first; declared pre-init cleanup/context transition next; event only in the required low-clock / SR-deasserted context; init readout afterwards. Preserve the distinction from P7 cleanup and keep one scored init step. Include the conditional A5 metadata and validate it against predecessor/context and recorded witnesses. Extend the A5 bench with the event-entry input/context checks; retain the pass/persistence cases. Do not change the scientific model, task, scores or contract to waive this step.

## P3 and bounded completion

The delivery and several docstrings say **21 core / 25 total benches**. Current source and independent rerun have **22 core / 26 total**, including the verbatim SipHash bench. Correct this with the next appropriate document edit; no extra review round or rerun for the wording alone.

Continue the existing engineering unit and resolve R1–R5 together, with no new scope draft, per-fix approval, date gate or commit-count rule. Run affected tests/mutants, then the complete inexpensive carrier suite at closure; rebuild and re-audit the routed carrier after RTL changes. Retain faithful GSR-aware netlist validation and the physical A8 limitations. Evidence should be scripts, relevant logs and digests, not another large fixture archive. Full B1–B4 proof is not requested. Firmware/PCAP integration and real board witnesses remain later work; mock their trusted inputs honestly for this unit. No production seed/run, new task/model/protocol, board/2d/routing, push or merge is authorized here.

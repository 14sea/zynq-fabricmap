# Owner review of 823f5b0 — HOLD, carrier transaction and evidence integrity

2026-10-21. Reviewed committed tip `823f5b08bacaa09dece5747523225534992479c4` on `b4-carrier-v2`, including milestone `aafffdb`, from `36e012c`. **HOLD.** The physical-control finding and useful host implementation are accepted in direction, but five engineering items below must be resolved together. No tracked source was modified by the reviewer.

## 1. Independent baseline and scope

- Exported the necessary **committed** files with `git archive` into a temporary root. In it, independently ran the three host-test modules: **20 tests OK, zero skip**; their simulation runner reproduces the **14 original TB_PASS results** (SipHash, twelve core scenarios, vendor-model witness). The regenerated fixed mechanics fixture is byte-identical to the committed header. These use the existing explicit fixture schedule/nonce chain, never a production task or pair-seed derivation.
- Independently ran B1 pin checks: **3 tests OK**. Recomputed the manifest known-answer over the committed bitstream: all **21 addresses match**. Bitstream SHA256 matches the committed build record. These do not prove every legal composition, firmware integration or physical timing.
- Reviewed routed isolation/timing reports and their scripts; the cell/pin claims are consistent with those reports. A fresh Vivado build/post-route timing simulation was **not** run in this review. Target paths are false-pathed in the XDC; WNS is not a timing proof of target sampling or the self-timed GSR pulse.
- Five new AXI/engine reproductions run against the unchanged committed RTL in the isolated root. Their `TB_PASS owner_*` markers mean **the specified defect was reproduced**, not that the product passed the requirement. Raw outputs and reproducer are beside this README.
- Record probes use the actual committed record functions and bench traces. No board, provisioning, production run/draw, revised task/model or statistical analysis was performed.
- The checkout was **not fully clean at arrival**: four `builds/b4/` outputs plus `sim/b4/out/` were untracked (`status_before.txt`). Tracked files were clean. The review leaves those original files alone; this factual status correction is not itself the HOLD's reason.

## 2. D1 — shared pins accepted; no task revision authorized here

The finding agrees with the routed pin report and AMD **UG474 Control Signals**: CLK, CE and SR are shared by the storage elements in one slice. Independent CE/SR vectors therefore cannot be physically applied as specified by task-v0.2 on this site. Refusing non-uniform vectors explicitly, rather than silently broadcasting or selecting one element's value, is the right boundary.

Source: https://docs.amd.com/r/en-US/ug474_7Series_CLB/Control-Signals . This supports the physical finding, not a new scientific interpretation of the archives.

Keep the current task, model, K9 records and no-go unchanged. This does not authorize task-v0.3, a model revision, new discriminability/gate runs or a new label. The current study's board applicability is blocked by that independent protocol question; mechanics fixtures may remain uniform for the engineering repair. Neither a passing uniform bench nor an engineering acceptance would solve it.

## 3. R1 — P1: current transaction never obtains P9 restoration, and normal close is permissive

References: design document sections 3/8; engine lines 124–155; accepted observation contract 5.1/5.4/5.5/5.7.

The design moves the base initialisation to the **next** transaction and proposes reading Q_LIVE after a base write. That is not the accepted P9: for mechanism (b), the current transaction must raise its declared event **on the restored base**, acquire the base-state sample, and bind it in its own X before normal close/next signing. A frame write and live Q read do not substitute for that event, and the last transaction cannot borrow evidence from a nonexistent next transaction.

`owner_p9` starts the base at INIT=FF, captures zero, cleans up and retains the base configuration. Q remains **00**, with only **one** event. Requesting the needed second event is refused as F_SEQUENCE because `init_done` is already set. The interface cannot perform the accepted sequence. `base_state_sample=[1]*8` supplied by a caller in the record tests is not a measured witness.

`owner_open_close` also closes without cleanup, reports STATUS.idle=1 while IN_LIVE=0x500 (clock and CE high), and accepts the next ordinary ARM. This is only valid under the explicitly qualified A5 exception; the current implementation has no enforced distinction. The host close builder can likewise label an incomplete/non-idle flow closed.

Implement and exercise the **current** P8→P9→P10 flow, with its own immutable X and failure retention, including the final transaction. Require complete restore/idle witnesses before the normal path permits another candidate; preserve an explicit, context-bound A5 qualification exception. This can be tested with a PCAP/link stub and the real register interface; no board or full PS firmware is required to establish the host transaction contract. Do not silently change the accepted observation contract to waive P9 or use a future record.

## 4. R2 — P1: GSR destroys an outstanding AXI write response

References: core `rst_n_eff`, axil reset/write channel, engine INIT_DELAY; `owner_axi_backpressure.txt`.

The engine schedules GSR from command acceptance plus eight cycles, independent of response delivery. Holding **BREADY=0** after a valid INIT_REQ gives BVALID=1 before GSR and BVALID=0 after it, with BREADY still zero. The event happened (`gsr_count=1`), but the write response vanished without a handshake. The master can wait forever. The documented quiet period starts **after the write response**, so it cannot repair this preceding violation.

Synchronize event launch with completion/quiescence of the actual bus path, or preserve/drain outstanding responses through reset with a defined interface. Include the AXI3 shim when claiming the top-level path. A guessed delay or requiring a fast BREADY is not a protocol proof. Retain a bounded backpressure reproduction and verify that response delivery/event execution each occur exactly once; also cover a pending read if the chosen implementation can reset it.

## 5. R3 — P1: STEP is not atomic and busy commands disappear

References: engine S_IDLE/S_STEP_DATA/S_STEP_SETTLE; axil STEP_IN; `owner_step_snapshot.txt`, `owner_busy_close.txt`.

The engine reads CE/SR, D and clock from **live STEP_IN in different cycles**, without latching the accepted command. Through the normal AXI interface, issue STEP for clock=0/D=A5, then merely stage the next word (clock=1/D=5A), without issuing another STEP. Actual inputs become **clock=1/D=A5**, and Q becomes A5 instead of holding INIT=FF. The applied event is not the declared step; a truthful raw readout would be attached to the wrong stimulus.

Also, CLOSE during an in-flight step receives an ordinary bus response but is silently ignored: the transaction remains armed, no named fault. Commands in non-IDLE states are not generally handled or refused.

Snapshot a complete accepted command, or reject changes while it is in flight; define one consistent acceptance/ready/refusal rule for operations. Unsupported/busy/combined operations must not silently alter half a command or disappear. The raw record must describe **applied** operations with an acquired-sample prefix, not infer them merely from attempted MMIO writes. Verify these two cases and the relevant phase/operation combinations in the same repair.

## 6. R4 — P1: O/F/X/session_open validation and construction do not implement the claimed contract

References: `host/b4carrier_records.py`, tests/test_b4carrier_records.py; `record_findings.json`.

Actual counterexamples accepted with zero findings include:

- `instrument.answer_bits` and `init_event.parameters.answer_bits` (closure is only top-level / selected fields, not every level).
- A complete O with **no steps**, or initial.q=null plus its step-0 copy null; wrong step kind/timing, wrong predecessor types and a wrong carrier VARIANT.
- A closed X with **null cleanup/base samples, idle_status=0, and an extra nested answer_bits**.
- session_open with **both digest values null and instrument empty**, marked open by None==None.
- F.fitness=true; a two-cell mask with one target/weight is silently truncated by zip and scored.

Conversely, serialize a valid O with sorted JSON keys and read it back: its canonical digest is unchanged, but the validator rejects the step because it compares dictionary **iteration order** to STEP_KEYS. A closed key set is not a prescribed JSON member order.

Source/link bindings are not checked: test records deliberately carry unrelated staging/pre/post hashes despite mechanism (b)'s frame invariance rule. No expected manifest/task/context enters these validators. Caller-supplied placeholders can be useful fixture inputs, but cannot be claimed to establish trusted source binding. Either provide the contextual binding layer and exercise it end to end, or explicitly keep helpers below that layer and implement the missing entry point in this unit.

The producer also rewrites the declared stimulus to its successful prefix: the non-realisable trace contains **three attempted set steps**, while O.stimulus retains only **two** plus init. The rejected step disappears from the stimulus commitment. Before any sample, it fabricates a step-0 object with null samples. `transaction_close` has no faulted-X representation, and validation of malformed top-level input can raise AttributeError rather than named findings.

Implement the actual source/status/phase-dependent schemas and bindings for O, F, X (including faulted/partial), and session_open. Preserve the full declared/attempted stimulus and acquired prefix separately; retain original returns/reads rather than inventing success or samples. Validate types and dimensions before fitness, forbid fitness for invalid observations, and use a trusted immutable task/source/reference as the authority. Show one **valid** complete opening/root→candidate→current close and named fault paths through fresh serialization/revalidation. It may be a uniform mechanics fixture with symbolic but mutually consistent PCAP data; no physical PCAP measurement is being demanded. Keep the null rule strict for carrier data; do not retag the bench model's unknowns as real samples to make it pass.

## 7. R5 — P2: the vendor witness does not model the implemented pulse-generator reset

The author disclosed the self-timed silicon pulse; that uncertainty is real. But the current so-called vendor bench still uses behavioral Verilog registers for `pulse_cnt` that do **not** see global GSR, holding the pulse two clocks. The synthesis/timing report identifies pulse counter registers as FDCE, whose vendor models do see global GSR.

In a separate temporary comparison, replacing only the counter flops with the corresponding vendor FDCE model changes the functional-model pulse from **40 ns to 0.1 ns**; both benches still print TB_PASS. This is a **model-fidelity counterexample**, not a measurement or prediction of physical pulse width. The exact probe and both logs are retained. It shows that TB_PASS currently does not verify the actual controller's global-reset behavior or a hardware-timed pulse width.

Use a faithful GSR-aware primitive/netlist bench for every affected controller element, and make the pulse-control/retention design and claims match it. A GSR-immune timed controller is one option; it is not the only authorized design. Keep physical event-to-Q effect, release skew and eventual A8 demonstrations explicitly unverified. Do not treat ordinary WNS or the ideal two-cycle bench as proof of those properties. AMD describes GSR as a global asynchronous control: https://docs.amd.com/r/en-US/ug474_7Series_CLB/STARTUPE2-Primitive .

## 8. Bounded decisions and same-unit completion

Continue the **existing complete engineering unit** and resolve R1–R5 together. No scope draft or per-fix approval. Host RTL/bench/build/record work remains authorized; mock the not-yet-integrated PCAP path as necessary without claiming physical links proved. Do not add production seeds, a new task/model/protocol run, board work, push or merge.

For the bootstrap, distinguish the **loaded carrier's natural frame image** (CE/SR used) from the **signed study base genome 0**. Pin/compare actual expected loaded frame content, not a B1-derived assumption that B4's occupied target frames are blank. A narrow engineering clarification of that reference in the observation/design documents is allowed with disclosure; it does not alter task, K9, model, method, thresholds or historical evidence. Keep loaded/root/restored references distinct and in the correct hash domain.

Correct scope statements while repairing: A7 presently checks a declared register-map table against RTL, not an actual PS application's accesses (no PS firmware delivered); A3/A6 are not fully verified yet. The choice not to use raw frame writes as the init mechanism is reasonable, but phrase it as lack of a guaranteed independent restore, not proof that every possible frame write can never change Q.

Run affected scenarios/modules/mutants and the complete inexpensive carrier end-to-end set at closure; rebuild and re-audit the carrier if RTL changes. No full B1–B4 regression/proof or repeated full mutant battery is requested. Keep evidence proportional (reproduction scripts, logs and digests), and submit the repaired unit once. Public model references/fixtures are legitimate host tests; they never establish silicon behavior. No new date or commit-count restriction is imposed.

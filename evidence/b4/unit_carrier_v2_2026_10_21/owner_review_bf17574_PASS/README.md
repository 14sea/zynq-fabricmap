# Owner review of bf17574 — PASS, carrier v2 engineering unit closed

2026-10-21. Reviewed committed `b4-carrier-v2@bf17574` against the HOLD on `ce3ca6d` and its preceding same-unit repairs. **PASS for the host-only carrier v2 engineering unit within its declared scope. R1–R4 are resolved; no blocking finding remains in this review.** The reviewer changed no tracked source, refs, production data or board state.

## 1. Independent verification

Necessary committed files were exported with git archive to the isolated temporary root named in `snapshot.json`. All simulations and new probes ran there, using explicit mechanics fixtures, never a production task/master/pair-seed draw.

| check | independent result |
|---|---|
| fresh synthesis of the committed core with `vivado/b4/netlist_core.tcl`, Vivado2025.2 | completed, no errors/critical warnings; 1972 FF and 279 RAM32X1S; fresh netlist metadata/log retained |
| carrier register-map, records and bench modules | **30 tests OK, no skip** (`host_tests.txt`) |
| complete simulation runner | **31 TB_PASS**: 27 core scenarios, SipHash, vendor RTL, pinned AXI3 shim and regenerated GSR-aware OOC netlist; both vendor benches report three 40 ns pulses (`baseline_benches.json`) |
| additional owner bus-state monitor | **29 core cases pass**: all27 existing core cases plus independent legal W-first and AW-first writes; each new split write receives one response and applies its value once; at every GSR assertion no pending AW/W half or B/R response is seen in the register file (`bus_boundary_check.py/.txt`) |
| B1 pin tests | **3 tests OK** |
| committed bitstream known-answer | **21 addresses match**; SHA256 `4e406f1280d3cf5cabf43d001278ef3b807a9ce4a7d036445122f5636e3d18a9` agrees with build record |
| fixed mechanics fixture | regeneration byte-identical to the committed header |
| historical/scientific protected paths versus fceedd6 | unchanged (`protected_paths.txt`) |
| copy of the previous owner review | all34 payload files match the original review checksum list (`previous_review_copy.json`) |

A fresh **OOC core synthesis** was run; a fresh full top-level place/route or physical timing simulation was **not** run by the owner. The submitted routed build reports WNS7.263 ns, target12/flush0, RAM279, STARTUPE2=1, ICAPE2=0; those reports and the committed bitstream/manifest were inspected. WNS is not a proof of target sampling, physical GSR pulse width or release skew. The newly generated functional netlist has a different file digest from the historical export; byte identity is not claimed.

The submitted affected-subset mutant log contains34 identified KILLED rows and a34/34 summary; the owner inspected that evidence and did **not** repeat the battery. Independent positive/negative probes below and the complete inexpensive carrier suite were rerun. No full B1–B4 proof or production verifier/run was requested or performed.

## 2. Resolution of the four HOLD items

### R1 — separate loaded-image and restored study-base references: accepted

The context now has two required authorities at their relevant binding points: `loaded_frames_reference_sha256` binds session_open to the loaded natural carrier image; `base_readback_sha256` binds each closed X to the restored signed study base. No equality between those references is assumed. The trusted references are distinct in the tests; the accepted observation contract was not rewritten to redefine the loaded image.

Reran `record_boundaries.py` **unchanged** from the previous review. Its proper init-only root → candidate chain with distinct references now has **zero findings**; all O and X shapes are valid. Its older “ordinary fixture chain” produces the loaded-image-reference finding because that probe deliberately supplies the restored-base hash as session_open's reference. This is the required rejection, not a regression. The current session test independently refuses a missing/wrong authority, a foreign instrument, contradictory sequences and an incorrect fitness under the trusted task.

### R2 — acquisition-based P6 boundary and premature operations: accepted

`acquisition_boundary` uses read acquisition witnesses and the declared length before allowing a P6 seal. An operation normally belonging to P7+ does not create that seal merely because its bus write received OKAY. Engine refusal before P6 is retained in invalid O at the observation phase; an accepted premature operation has the explicit host-recorded `premature_operation` code. Neither path manufactures X before P6. The post-P6 immutability and faulted-X repairs remain intact.

The previous early-CLEANUP **stimulus** was rerun against committed RTL. The probe consumer was adapted only to catch the now-expected RecordRefusal instead of unconditionally asking for a nonexistent X. Result (`early_cleanup_records.json`):

- invalid O, `sequence`, phaseP3, step_reached0; acquired pre-init sample retained, no init step invented;
- **O validator: zero findings**;
- X refused by name because acquisition never reached the P6 seal.

Also reran the older post-P6 phase probe unchanged: O remains complete with zero findings before/after the failed CLOSE; X is faulted and structurally valid. The current tests and the independent `acquisition_check.py` cover an accepted premature cleanup, open acquisition without a terminal fault, successful seals, and the same root trace under its actual init-only declared stimulus. A fault's named carrier code remains distinct from the host's premature-operation diagnostic.

### R3 — independent write halves across pending/GSR: accepted

The gate now blocks a newly arriving unpaired W during the stall, accounts for a W accepted before stall as outstanding, and admits its matching AW. An AW already accepted admits its W, including all beats of an accepted AXI3 burst; the top retains the outer admission gate and tracking-only inner gate. The previous burst probe was rerun unchanged and no longer reproduces the deadlock; it observes one event after completion. Existing shim/backpressure tests pass.

The former standalone W-first defect probe expected WREADY=1 and withdrew WVALID after that fixed cycle. That master is no longer legal when the repaired gate correctly keeps WREADY=0; its old failure marker is not a product failure. The new owner probe holds VALID until the actual channel handshake. Independent W-first and AW-first transfers during the pending window each complete once, without losing or replaying a beat. The extra bus-state monitor passes across all27 core scenarios, including `w_first_early`, and both owner split-write cases. The delivered before-stall W case separately verifies that an already accepted W holds the event until its matching AW/write response finish.

### R4 — malformed source records become findings before traversal: accepted

Reran the previous record-boundary probe unchanged. Null/list/integer session_open and predecessor values, and the malformed faulted-X fault value, each produce named findings; **no exception is raised**. The chain now stops at the malformed record rather than continuing to dereference it. The well-formed normal/A5/faulted-chain tests pass. This acceptance covers the declared record/source boundary; it is not a claim of a universal validator for arbitrary trusted application code.

## 3. A5 fixture and prior repairs

Initialising the A5 bench's fabric to its configured INIT values is accepted as an explicit **mechanics fixture initial condition**, as with the session fixture. The samples still come from the carrier path; model nulls were not converted into alleged physical sample values inside records. The full A5 chain is now checked with zero findings. This is a model/RTL fixture check, not observed silicon behaviour or B4Q qualification.

The earlier A5 event-context probe was rerun unchanged: every GSR entry has clock, CE, SR and D at0, including J3 after its recorded pre-init cleanup. The prior current-transaction RESTORE_INIT/BASE_STATE, latched STEP/applied inputs, busy-command refusal, explicit injection/ARM context, GSR-immune authority state and LUTRAM pulse repairs remain exercised by the suite. Vendor RTL and the independently regenerated GSR-aware netlist agree on the declared functional pulse width; physical A8 stays open.

## 4. Meaning and closure

This PASS closes the **carrier v2 host-only engineering unit**, including its same-unit repairs. It does not freeze preregistration, establish a new gate result, qualify legal compositions or prove the contract's future schema/adapter/firmware producer. The document's partial A3/A6 status remains appropriate; A7 checks the declared map against RTL, not accesses of undelivered firmware.

The shared CE/SR/CLK finding and its protocol consequence remain unresolved: the current per-element task-v0.2 is not thereby made executable on the site. This PASS authorizes no task/model/K9/threshold revision, new label, production execution, or reinterpretation of sim-4 no-go. Firmware/PCAP links and session-opening integration, B4Q planning, physical sampling/timing, release skew and A8 demonstrations remain subsequent work. No board/2d/routing, push or merge is authorized here.

A routine **documents-only closure/archive** may copy this owner review with checksum verification, mark the existing unit accepted/closed, and record these boundaries. No new test/mutant run or additional review round is required solely for that faithful closure bookkeeping. There is no new date, branch-name, commit-count or per-step approval requirement. Further engineering/scientific work should follow its own concrete purpose and authorized scope.

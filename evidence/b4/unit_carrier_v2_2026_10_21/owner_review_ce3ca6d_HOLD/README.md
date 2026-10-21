# Owner review of ce3ca6d — HOLD on four remaining boundary contracts

2026-10-21. Reviewed `b4-carrier-v2@ce3ca6d` (repair body `b124052`) against the prior owner review of `aaf15ba`. **HOLD**, with the four remaining items below to finish together inside the same carrier engineering unit. No tracked file, branch/ref, production seed/archive or board was changed by this review.

## Independent checks and accepted repairs

- Exported the necessary **committed** files with git archive into the temporary root in `snapshot.json`. Regenerated the GSR-aware OOC core netlist from those sources using Vivado 2025.2: **1971 FF, 279 RAM32X1S**, no errors/critical warnings (`netlist_regeneration.log`, `fresh_netlist_metadata.json`). This review did not perform a fresh full place/route or physical timing simulation; generated netlist byte identity to the historical file is not claimed.
- Fresh-process carrier modules: **28 tests OK, no skip**. The full runner gives **24 core + SipHash + vendor RTL + AXI3 shim + vendor netlist = 28 TB_PASS**; both vendor benches report 40 ns GSR pulses. Fixed mechanics fixture regeneration is byte-identical. B1 pins: **3 tests OK**. Manifest recomputation: **21 address values match**. Committed bitstream SHA256 `2a3b75c3b5052abc9c4cc9b35227df72050bd340756ad885cfa170d212ecfebb` matches its build record.
- Read routed reports and build scripts: WNS7.985 ns, target12/flush0, RAM279, STARTUPE2=1, ICAPE2=0. Physical sampling, release skew and A8 remain unverified; WNS is not evidence of those. The obsolete write_verilog -cell overwrite was removed from the build script as reported.
- Protected scientific/historical paths against `fceedd6` are unchanged (`protected_paths.txt`). Prior owner review's **21 payload files** in the committed copy each match the original SHA256SUMS (`previous_review_copy.json`). Worktree clean before and after. No production task/master/pair-seed derivation, board access, statistical analysis, push or merge.
- Copied and reran the previous **four reproducer scripts unchanged** inside the new isolated review root (their `.rerun.log` files are retained). The accepted AXI3 two-beat burst now drains and produces one event (`OWNER_NOT_REPRODUCED` for the former deadlock). The post-P6 CLOSE fault leaves O complete and unchanged and produces a valid faulted X. The A5 J3 event enters with clock/CE/SR/D all zero on every pulse. Previous record negatives are rejected. Exact enum constants, cleanup clock continuity, X/predecessor sequence checks, and trusted-task fitness recomputation are improvements accepted in direction.
- P3 count correction is resolved: 24 core / 28 total benches. The added valid session scenario is useful, but its use of the same startup/restored-base hash hides R1 below.

## R1 — P1: startup's pinned loaded-image reference is bound to the restored study base

Code: `host/b4carrier_records.py:637–656`; `tests/test_b4carrier_records.py` STARTUP/LINKS and ctx_for. Reproducer: `record_boundaries.py`, `record_boundaries.json`.

`validate_chain` compares `session_open.base_frames_reference_sha256` to **ctx.base_readback_sha256**. That context field is also used by `validate_bound` to bind **X.base_readback_sha256**, the P8 readback of the restored signed study base. The docstring explicitly calls these the same reference. The tests were changed to make both STARTUP and every restored base one hash.

The accepted contract **5.5** and carrier design **section 3** explicitly distinguish them: the startup reference is the **loaded natural carrier image** (CEUSEDMUX=SRUSEDMUX=1); the root and P8 use **signed base genome 0**, differing in those mux bits. The previous owner review also explicitly required keeping these commitments distinct. An actual correct session cannot satisfy the new equality.

Using the real `session` bench trace, reconstruct an init-only root, candidate and both closes with one symbolic restored-base hash, and a session_open with a different symbolic loaded-image hash. Every O and X is structurally valid. Supply both independently trusted values in the context. The chain produces the pinned-reference finding on both records. These are honest, distinct PCAP stubs, not an attempted mismatch of a pinned reference.

Keep separate trusted fields for the **loaded-image frame reference** and the **restored study-base frame reference**, using the proper hash domain for each. Bind session_open against the former and each X against the latter. The complete zero-finding session test must use distinct values; retain the foreign-carrier / arbitrary-startup-reference rejection tests. Do not change the accepted contract or redefine the loaded image as genome 0 to make the equality work. This is still host binding work; no actual PCAP/firmware integration or board measurement is required.

## R2 — P2: seal_index assigns P7 by operation name before P6 has occurred

Code: `seal_index` and observation / transaction_close builders. Reproducer: `boundary_probes.py`, actual RTL/MMIO in `owner_early_cleanup.txt` and `.jsonl`; `early_cleanup_records.json`.

After a warm transaction, ARM a new candidate and perform PRE_SAMPLE, **before INIT_REQ**, then issue CLEANUP. RTL correctly records F_SEQUENCE; no init observation has completed. Nevertheless `seal_index` cuts O immediately before this CTRL write because the bus acknowledged a command whose name is normally P7. The later fault is excluded:

- O is emitted as **status complete**, with zero steps and no fault; its own structural validator rejects it for missing the init observation.
- X is emitted as **faulted P7**, even though observation step 0 has not run and P6 has never been reached; it also fails validation against the malformed O.

This is not the repaired post-P6 CLOSE case: that case now works. A bus-accepted cleanup/close/restore request is not itself proof that acquisition reached the P6 seal. Similar premature operations must retain an invalid observation's actual acquired prefix and fault, rather than fabricate a completed observation and a later-phase X.

Establish the seal from acquisition/phase state (or an explicit validated P6 marker), with a recorded terminal boundary, rather than solely the first accepted operation name. Preserve the post-P6 immutability fix. Test the actual premature-operation path: invalid O at the correct observation phase with pre-init sample/prefix and named fault retained; no P7 success or post-P6 close invented. Keep source PCAP failure phases honestly separate from carrier register phases; no new PCAP integration is being demanded.

## R3 — P2: standalone Lite gate acknowledges W then loses it at GSR

Code: `b4_axi_gate.v` W pass-through and AW-only write tracking; `b4_core` default **LITE_STALL=1**. Reproducer: `boundary_probes.py`, `owner_wfirst.txt` / `.jsonl`.

The **integrated top's AXI3 path is improved**: its serialized shim accepts AW before W and the outer gate tracks that accepted burst, so this reproduction is specifically the delivered **standalone AXI-Lite configuration**, not a claim that the top's repaired burst case still fails.

On the default core, issue INIT_REQ; while pending/stall=1, send the next write's **W first**, as independent AXI-Lite channels permit. WREADY is high, so the master completes that handshake and correctly deasserts WVALID. The gate tracks only AW and considers the bus quiet. GSR clears the register file's accepted W. After the event send the matching AW, which is accepted, then wait 80 cycles:

```
gsr_count=1 responses_for_split_write=0 aw_seen=1 w_seen=0 step_in=0000000
```

The write cannot finish without re-sending a beat the master already delivered. The new wr helper correctly handles independent handshakes, but current scenarios do not place a W-first transfer across the pending window.

Make admission/quiescence account for both halves of a write in the supported standalone configuration: avoid acknowledging a new unpaired W into resettable storage, or preserve/drain both accepted halves with progress guaranteed. Merely counting W while still blocking its missing AW would replace loss with deadlock. Keep the integrated shim/burst drain fix. Add the W-first pending-window case with bounded response and exactly-once application checks; do not assume that every AXI-Lite W has a previously accepted AW.

## R4 — P2: public chain validation still dereferences unvalidated nested records

Code: `validate_chain`, before and after `validate_bound`. Reproducer: `record_boundaries.py`, `malformed_chain_inputs` in its JSON output.

The previous O=[] counterexample is repaired, but valid surrounding context with any of these malformed source records still raises AttributeError:

- session_open = null, list or integer: the structural finding is obtained, then `so.get` is called anyway.
- O.predecessor = null, list or integer: `.get('kind')` is used before the O schema rejects it.
- X.status = faulted with fault='bad': the X validator produces a finding, then the chain-ending text dereferences `fault.get` anyway.

Validate source object shapes before traversal and use a named finding as the terminal result for that malformed record. Do not continue indexing the malformed value merely because another layer already rejected it. These are concrete record-boundary negatives, not a request for another general fuzzing campaign or to harden arbitrary trusted caller code. Preserve the normal and faulted-chain rules and all existing zero-finding cases.

## Completion within the existing unit

Resolve R1–R4 together and resubmit once. This continues the already authorized complete carrier engineering unit: no scope draft, per-fix approval, new date/commit-count restriction, or additional production run is needed. Run the affected cases/modules/mutants; run the inexpensive complete carrier suite at closure and rebuild/re-audit the carrier after RTL changes, retaining the faithful GSR-aware netlist bench. A full B1–B4 proof or repeated unrelated mutant battery is not requested. Scripts, relevant logs and digests suffice.

Shared CE/SR/CLK and its unresolved protocol consequence, A8/physical release skew, firmware/PCAP integration and B4Q remain as disclosed. Task/model/K9/thresholds, archives and no-go must remain unchanged. This review authorizes no board/2d/routing, production seed/run, new protocol/task/model, push or merge.

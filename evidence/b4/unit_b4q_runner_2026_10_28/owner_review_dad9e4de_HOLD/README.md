# Owner review — B4Q runner unit — dad9e4de — HOLD

Reviewed: `dad9e4dedffbe4fac86db33cf758ec66074f29ec` (implementation `02d90207`, base `e34432ea`). Review on 2026-10-28. Basis: the already-issued `owner_disposition_c84b8bd5_2026_10_28/RULING.md`, §3 A–E, archived in the submitted unit.

**HOLD.** The PS evidence log and its derivation are useful progress. The submitted tests pass, but the runner control-plane evidence is not yet independently checked, ordinary serial packet boundaries lose bytes, and the real-source preparation has been deferred rather than completed. These are within the existing undertaking; a new preliminary proposal is unnecessary.

## Independent checks

All execution used disposable `/tmp/owner_b4q_runner__914ex6_` or local fixture objects. No UART device, SSH, board, physical PCAP, production key, seed derivation, git commit/push/merge or canonical tracked edit occurred.

- Bench prerequisite: 1 test OK. Used the pre-existing netlist dependency, copied by hash; no synthesis/rebuild of the protected PL.
- The submitted nine-module B4Q command: **93 tests OK**, 402.8 s. Its setup independently regenerated 19 PS-source console cases (19 fresh verifier agrees), 31 runner cases (zero declared-expectation failures, 29 fresh verifier agrees and two pre-session transcript-only stops). This is not an independent rerun of all 19 emulated console cases; the emulated valid control and other module regressions ran.
- Two clean image builds: raw `.bin` byte-identical, SHA256 `4d989ee84757f60965d2a43da9c61981366893423e3b96bd559b575edf07da5b`. This establishes build reproducibility, not device execution.
- IMPORT checks: 59 `b4/` hashes and 37 firmware hashes, no mismatch. Protected paths, including `b4q_tx.c`, unchanged against `e34432ea`. Canonical working tree clean.
- Did not repeat the author's 28-mutant battery; its positive record does not answer the counterexamples below. No frozen whole-project battery is required for this review.

Logs and executable counterexamples are in this directory. `independent_e2e_summary.json` identifies the generated fixture roots and results. `snapshot.json` identifies the netlist input. `review_metadata.json` records the review scope.

## R1 — P1: runner witnesses and the control-plane-stop account bypass verification

Locations: `host/b4q_verify.py`, `load_archive`, `verify`, and the runner's `write` contract.

Fresh-process results from copies of the committed runner `valid` fixture (`archive_probes.py` / `archive_probes.json`):

| modification | verifier result |
|---|---|
| unchanged control | exit 0, clean=true, agree=true |
| delete `uboot.json`, `raw/console.bin`, `raw/console_tx.bin` | **exit 0, clean=true, agree=true** |
| change both runner copies of the load witness to host CRC `11111111`, device CRC `22222222`, `equal=true` | **exit 0, clean=true, agree=true** |
| change both copies of page `read_back[0]` to `00000000`, retain `equal=true` | **exit 0, clean=true, agree=true** |
| set `session_open.json` to null, clear manifest.records, add a claimed pre-go stop; leave all acquired bytes and four transaction directories | **exit 0, agree=true, control_plane_stop=the unverified claim** |

The final case is clean=false, not clean=true; the defect is agreeing with an invented stop and skipping the remaining evidence. The retained raw stream contains `go 02000000`; the four retained transactions contradict the asserted pre-session account. The early branch merely trusts a nonempty `runner.stops` list. Missing a session-opening object also does not prove that `go` was never issued.

Repair the runner archive contract and its fresh verifier: require and parse its retained raw material, check typed load/page/command witnesses and their linkage to the selected image, address ranges, page, application byte stream and normalised console. Summary booleans or two agreeing copies are not authorities. Check the raw prefix and directory/account completeness before accepting a control-plane-only stop. Persist execution phase before issuing `go`; distinguish demonstrated pre-go refusal from post-go/unknown execution. Do not fabricate missing observations or turn a contradictory archive into a legitimate limitation.

This is internal evidence/source consistency; it must not claim that text or a program log independently proves physical behaviour.

## R2 — P1: serial handovers lose bytes; busy input escapes the transfer deadline; write errors lose the acquired prefix

Locations: `host/b4q_runner.py` (`UBoot.read_until`, `loady`, `go`, `run`), `host/b4q_ymodem.py` (`_read_byte`, `send_block`, `send`).

`transport_probes.py` / `.json` reproduce with local byte queues:

1. A read containing `## Starting application ...\r\n` **and the first application line** is consumed wholly by `go`. Its next reader receives nothing. The first line is stranded in the U-Boot reply, not delivered to the application protocol.
2. The last YMODEM ACK coalesced with `## Total Size ... Zynq> ` leaves that tail in `port._ym_buf`; the subsequent U-Boot reader never sees it. The analogous Ready/C transition also needs one continuous stream contract.
3. With transfer timeout=5 and retries=2, a receiver sending non-ACK junk stays inside the header's inner loop. At 305 simulated seconds the owner probe stops after 101 reads with its **own cap**, not a product timeout. The declared overall bound is not enforced inside this loop.
4. `md.l 10440000 1` accepts a value labelled address `deadbeef`; `crc32 02000000 1` accepts a CRC explicitly labelled for the wrong range. Counting words or finding `==>` is insufficient to establish the requested witness.

`retention_probe.py` / `.json` inject a tty write `OSError` during the runner's console write. The runner propagates it, persists none of the already-acquired `ACQUIRED-PREFIX`, and leaves the port unclosed. `run` only catches two named exception classes; its finally block does not unconditionally write/close. Real `Port.write` can raise this error from `os.write`.

Repair with a shared receive-buffer/handover contract, preserving bytes beyond the consumed protocol boundary; cumulative bounds covering inner loops, partial reads/writes and junk input; monotonic elapsed-time measurement; exact returned address/range checks; and unconditional prefix persistence plus resource cleanup on transport errors. Preserve a true programming error as such rather than misreporting a device finding. The host-only byte-stream fixtures must cover coalesced and fragmented boundaries, not only the surrogate's current timing.

## R3 — P1: image selection and board admission are not pinned by the runner

Locations: `host/b4q_runner.py` (`RunnerSession.__init__`, `load_image`, `write_page`, `start`), `host/b4q_device_surrogate.py` (`go`, image table).

`admission_probe.py` / `.json` supplies a **56-byte non-executable local fixture**, with a matching transfer CRC and page readback. `RunnerSession.start()` issues `go 0x02000000`. No image was executed by the probe. The runner computes the arbitrary file's SHA and writes it into the page; it does not hold selection to an independently pinned expected image. The surrogate's image-table rejection is on the *receiver* side, after `go`, and masks this missing runner rule.

There is also no runner admission of expected boardid/role/DDR/preconditions before its PL nonce access or execution. The committed valid surrogate even announces EBAZ4205, 256 MiB, and the runner proceeds with the image whose page/buffers/log are all above 256 MiB. That is a host fixture, not a physical operation; it nevertheless demonstrates that the claimed board-map stop is not implemented. `docs/board_roles.md` requires the content-class role interlock and treats missing role as reference/refused. F8B3 is an EBAZ4203 spare awaiting provisioning, not this EBAZ4205.

Introduce an explicit trusted execution/fixture context: selected pinned image, permitted board identity/role, memory/layout and required carrier/clock prerequisites. Refuse an image/hash mismatch or disallowed/unknown physical target before proceeding with its execution-sensitive path. Explicit host fixture profiles may simulate the failure cases; a pathname beginning `/dev/pts/` is not proof of physical provenance or permission. Do not provision a role, change the memory map or load a real board in this repair.

## R4 — P2: the authorised physical-source offline verification has been deferred

Locations: `host/b4q_verify.py` (transport refusal; unconditional emulated requirement), `docs/b4q_source_audit.md`, `docs/b4q_bringup_plan.md` introduction/§4–5.

The ruling's deliverable C explicitly authorised the physical-source raw contract, adapter/validator and trusted source selection in this host-only unit. It did not authorise hardware execution or a physical qualification claim. These are different matters.

The submission rejects every `uart-board` archive and separately requires `manifest.emulated=true`. The bring-up draft says enabling board archives needs another unit. Thus it provides a PS-log path exercised behind a surrogate, but not the requested offline validation contract for future physical-source records. This is not repaired by relabelling a PTY fixture as a board or removing one check; `archive_probes.json` includes that trivial relabelling refusal only as evidence of the current branch restriction.

Complete the versioned source/provenance selection and offline validation for the physical-source format with **explicitly synthetic device-format fixtures**, including the absence of emulator-only witnesses, source downgrade attempts and R1's runner linkage. Separate structural/source consistency from observed-on-device provenance and qualification. No synthetic fixture becomes actual board evidence, and no validation result grants device execution or qualification. Keep old emulated evidence's supported verification/reverification path. Narrow schema/metadata changes already fit this unit's authority.

## R5 — P2: the bring-up draft conflicts with the accepted prerequisite graph and includes a wrong MMIO address

Location: `docs/b4q_bringup_plan.md` (and its cross-reference in `docs/b4q_plan.md` §8).

- Preserve the established **P4 = F8B3 2d provisioning / measured power / FCLK / acceptance regression; P5 = F8B3 bring-up; P6 = 17A6 qualification**. Do not reuse those names for load/open/one-transaction subphases. Target F8B3 first; “F8B3 or 17A6” is not the accepted sequence. Existing saved bootdelay and verified FCLK facts about 17A6 are not measurements of an unprovisioned F8B3.
- The draft's “next phase is not entered on the same ruling” adds a gate not issued by the owner. A whole-of-run ruling can cover ordered internal stages with stop rules. Keep genuine distinct P4/P5/P6 authorities; do not require another owner round for every internal load/open/transaction step.
- M3's `md.l 43C00000 1` is **not** VARIANT. From `AXI_BASE=0x43C00000`, `VARIANT=0x2034`, the address is **0x43C02034**. Its expected value is `0x42340001`. Verify the plan's command/address claims from the accepted regmap. A VARIANT read alone does not establish 50 MHz; specify the clock derivation/measurement and safe prerequisites before PL accesses.
- M5 assumes no watchdog kick after END. The new export epilogue emits RING/CHUNK through the kicking emitter. A runner that pulls after END changes that interval. Specify an idle/no-export or last-kick/epilogue-close measurement with the actual sequence and retained timing; keep 17A6's load/clock value a hypothesis until measured on F8B3. No intentional abort is required by this review.
- §5's `--phase P4` invocation is explicitly unimplemented and uses the e2e driver, while the two `python -c` commands omit necessary definitions/import setup. Provide an executable host-tested entry point for the proposed control-plane-only and session stages, or mark exact remaining engineering rather than present placeholder commands as runnable. This implementation is already within the runner undertaking; no new physical authority follows.

## P3 — factual wording

`RunnerSession` does construct and provision a local `Backend` in `super().__init__`, then sets it to None. The admission probe records one constructor call. This does **not** demonstrate that surrogate-private trace/PCAP data was used for physical observations; the PS-log derivation is separate, and opening replaces the timing word from IDENT. But “NO backend in this process” and its string-only test are factually too strong. Remove that dependency in the real-source path, or narrow the claim and test the actual source boundary. Do not turn this wording issue into an unrelated refactor mandate.

## Same-unit repair authority and proportional validation

Repair **R1–R5 together in this unit**, update the audit/plan/README and add the focused counterexamples. Runner/collector, source contract/verifier, necessary narrow PS collection changes and their host fixtures are already authorised. No new scope proposal, date restriction, branch-name gate, exact commit count or per-edit approval is required. Routine implementation choices remain yours.

Run affected tests and isolated mutants for changed contracts. Re-run the applicable console/runner scenarios with fresh-process verification after the final relevant source changes; add explicit positive and coordinated negative controls for these repairs. If the image runtime changes, rebuild/pin it and verify its raw binary reproducibility; if it does not, reuse the unchanged build evidence rather than repeat it. Keep failed attempts honestly labelled. No unrelated frozen 332-test battery, PL rebuild or arbitrary JSON fuzz expansion is requested.

Submit the complete corrected unit once. This HOLD does **not** authorise real serial/SSH/board contact, power/provisioning, physical load/go/PCAP, production keys/seeds, scientific-method changes, push or merge. Existing no-go results and P4–P6 remain unchanged.

## Reproduction and package

The four probe scripts take a disposable repo root as their first argument; `archive_probes.py` additionally takes this review directory for its result files. Use a fresh clone/work directory for a rerun, because copied probe archives are intentionally not overwritten. Supply the accepted build dependencies as recorded in `snapshot.json`; the image build and existing host test setup provide the fixture binaries. All probes use files, byte queues, fake clocks or injected HAL/transport objects only. The admission probe records a **spy's** go call, not image execution.

`archive_probes.py` invokes the verifier in a fresh interpreter for each case. The direct transport/admission/retention probes isolate producer behaviour that archive-only checks cannot reach. The generated `/tmp` fixture archives are not copied into this package; source, logs, outcomes and hashes are retained here. `SHA256SUMS` covers every other file in this review directory.

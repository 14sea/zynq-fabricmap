# Owner review — runner repair — 30c5ccba — HOLD

Reviewed tip `30c5ccbaaa3c9df2abb686de71e5d0f98f11c4fd`, code `972b63c6`, repairing the HOLD on `dad9e4de`. This is the same host-only runner/evidence undertaking under the already-issued disposition on `c84b8bd5` and the first review's R1–R5 repair authority.

**HOLD: four residual groups C1–C4.** This round fixed the literal first-review counterexamples, but coordinated raw+summary negatives still pass and two execution barriers are incomplete. Repair all four together; a preliminary proposal or per-edit permission is unnecessary.

## Independent validation

All work used `/tmp/owner_b4q_runner_repair_ogyqg5da`, local files, byte queues, test harnesses or spy objects. No device/serial/SSH contact, physical PCAP, key provisioning, production seed derivation, git commit/push/merge or canonical tracked edit.

- Bench prerequisite: **1 test OK**, using the copied accepted netlist; not re-synthesised.
- Final nine-module B4Q suite: **109 tests OK, exit 0**, 338.0 s. Its setup regenerated **19 PS-source console cases, 19 fresh verifier agrees**, and **38 runner cases, 38 fresh verifier agrees, zero declared-expectation failures**. The emulated valid control and module regressions also ran; this is not an independent full 19-case emulated rerun.
- First owner suite run lacked the ignored `build/b4q_image/b4q_app_v2.bin`: 109 tests, 2 failures/16 errors. That log is `tests_missing_image_dependency.txt`. This was an owner clone setup error, not a product regression. The exact pinned image was copied, SHA checked, and the suite rerun without source changes.
- No firmware changes since `dad9e4de`. Reused the exact image independently reproduced at the first review: SHA256 `4d989ee84757f60965d2a43da9c61981366893423e3b96bd559b575edf07da5b`. Did not repeat an unchanged image build.
- IMPORT: **59 + 37 hashes match**. Protected runtime/evidence paths unchanged against `e34432ea`; canonical working tree clean. See `integrity_checks.json`.
- The author’s 43-mutant record was inspected, not independently rerun; passing that table does not cover the residual counterexamples below. No frozen whole-project battery was run or requested.

The test command and source/dependency snapshots are in `review_metadata.json` and `snapshot.json`. Fresh fixture roots and outcomes are in `independent_e2e_summary.json`.

## Accepted progress / unchanged limits

- `Port.buf` now preserves coalesced `go`/IDENT and YMODEM/prompt tails, including the submitted fragmented cases. Transfer reads have cumulative monotonic bounds and a junk bound. Exact md.l and crc32 range checks exist in the live reader.
- The basic first-review missing-file, mismatched-copy and forged pre-go probes now fail as intended. The executable stages and the corrected VARIANT address are present.
- The runner’s constructor no longer creates a Backend. The constructor-spy test passed; the former P3 is addressed.
- A synthetic device-format positive archive verifies internally, while its provenance explicitly says observed_on_device=false and qualification=false. This is appropriate; it is not a physical observation or qualification.
- P4/P5/P6 are restored to their accepted meanings, F8B3 is first, and ordered P5 sub-stages are not separate owner gates. S4/no-export and M2 repetition are now explicitly marked remaining engineering. That marking is accepted; this review does not require an unrelated image change or pretend the board day is fully ready.

## C1 — P1: state-dependent completeness and raw-console coverage remain missing

Location: `host/b4q_verify_runner.py::verify_runner` and its integration in `host/b4q_verify.py`.

`coordinated_archives.py` copies the submitted valid runner fixture, changes raw material and all relevant witness/digest copies, and invokes a **fresh verifier process** for each case. The final script asserts that the banner mutation actually applies. Outcomes in `coordinated_archives.json`:

| fixture / change | fresh result |
|---|---|
| unchanged valid control | exit 0, clean=true, agree=true |
| change received CRC and its recorded witness together to `equal=false`, retain executed/complete transactions | **exit 0, clean=true, agree=true** |
| change raw banner to 256 MiB, board witness to dram_ok=false, admission.ok=false; context still requires 512; retain executed transactions | **exit 0, clean=true, agree=true** |
| set admission=null on the completed session | **exit 0, clean=true, agree=true** |
| change loady/CRC command and CRC response range to `0x04000000`, keep context/go at `0x02000000`, retain the same pinned image | **exit 0, clean=true, agree=true** |
| insert a valid retained END frame into raw received bytes **before IDENT**, leave normalised console/session unchanged, refresh raw commitments | **exit 0, clean=true, agree=true** |
| put an invented unknown stop on a copied pre-go fixture and declare the stop at prompt | **exit 0, agree=true, stop.demonstrated=null** |
| null context image pin (shape-rejection control) | exit 1, named REFUSED, no verifier exception |

The CRC/DRAM cases are now self-consistent accounts of a failed prerequisite followed by forbidden execution. Comparing each value to its own raw source does not enforce the production state machine. `admission=None` also skips every admission branch. A go command is tested mostly for existence, without binding its address to the load/context.

The END case is not a harmless suffix after shutdown: it is inserted before the opening's first IDENT. The verifier only checks that each cached console line occurs in raw bytes as a subsequence, so an unaccounted terminal frame can disappear from the interpreted exchange.

Required repair:

- Apply a phase-dependent record/prefix contract. Issued go requires completed successful admission and the required successful load/page witnesses. Bind context, command addresses, loaded range, go address and image identity. Missing/null/false prerequisite evidence cannot be skipped for an executed session.
- Legitimate refusals **before** go must remain retainable and verifiable as refusals. Do not reject every failed witness unconditionally; reject continued execution after it and contradictory phase accounts.
- Parse/account for the received and sent application frames in the retained raw streams, with the existing framing/freshness/token/error rules. Compare the resulting ordered exchange with the retained console, including explicitly accounted ignored/incomplete bytes. A cached transcript cannot omit an observed END and remain a clean normal session.
- Unknown/unproved stop reasons must be reported as unverified/limited or refused, not accepted as a demonstrated stop by treating None like success. Reconcile phase claims with the acquired prefix. Preserve the distinction between a named program error and an observed device refusal.

These are consistency/completeness rules; they do not claim that raw text authenticates a physical device.

## C2 — P1: failed persistence still permits go; raw TX records unsent bytes

Locations: `host/b4q_runner.py::RunnerSession.persist`, `start`, `Port.write`.

`producer_probes.py` / `.json` isolate the following without executing an image:

1. Starting from a pre-go fixture state (the prior checks assumed completed), inject ENOSPC into required uboot.json writes. `persist()` appends an in-memory stop but swallows the exception. `start()` **returns normally, calls the go spy once, advances to application**, and no uboot.json exists. A failed publication barrier cannot be merely diagnostic.
2. Let os.write accept only `go`, then raise EIO on the remainder of `go 02000000\r`. `Port.tx_log` nevertheless records the **whole command**, because it is appended before writes succeed. A future verifier cannot distinguish intent from the prefix actually accepted for transmission.

Required repair:

- Make required evidence persistence a fail-closed execution barrier. If it fails before load/go/other guarded continuation, latch failure and do not perform the operation. Preserve/retry only the safe evidence finalisation that remains possible; no promise that a full disk can retain bytes it cannot store. Do not silently turn this into a successful run or continue after an in-memory stop.
- Commit raw TX bytes according to successful write counts. Record attempted commands / incomplete writes separately as intent and uncertainty. Bytes accepted by the local OS still do not prove device receipt. Retain the good new finally/close behaviour.
- Test the publication failure at the actual pre-go boundary and partial/zero writes, with positive controls. No actual disk filling, device write or image execution is necessary.

## C3 — P1: board/clock admission is incomplete; the selected file can change after its hash check

Locations: `host/b4q_runner.py::ExecutionContext`, `admit`, `load_image`; corresponding surrogate/context tests and plan claims.

`producer_probes.py` / `.json`:

- For a mismatched expected FCLK word, the sent command order is **`md.l 43c02034 1` then `md.l f8000170 1`**, and only then an AdmissionStop. The first is a PL access. The corrected plan M3 explicitly requires PS clock checks/derivation **before** that PL access, because a gated-clock PL read can hang. The host fixture returns the VARIANT regardless of clock; it is not a demonstration that this ordering works on a device.
- A context whose role is `reference` is still admitted. More fundamentally, the code never queries/binds `boardid` or the device role at all. A Model line identifies a board class, not F8B3 vs 17A6/08EB. The context's role string is not a role interlock. `docs/board_roles.md` requires a content-class role of verify/sacrificial; missing role is reference/refused. This was expressly part of the first R3, not a new gate.
- After successful admit of the pinned local image, replace that disposable file before `start()` continues. `load_image()` re-reads it without holding those bytes to the pin. The **70-byte substituted non-executable fixture** gets matching load CRC and reaches the go spy. Its SHA is `9755d088350b257b21c83fe360643496c4ee4602c9a4aceb46510f6bbbfec239`, not the accepted image. No image was executed; the spy records the forbidden continuation.

Required repair:

- Distinguish trusted expected board identity/role from observed boardid/role and from the purpose string “bringup-rehearsal”; enforce and retain their binding. Reject missing/disallowed actual roles and wrong boardids before the content/execution-sensitive path. Explicit negative fixture profiles may simulate these cases, but a model substring or a PTY pathname is not the physical identity/interlock.
- Establish the requisite clock enable/rate/pinned configuration through PS-accessible inputs **before any PL read**, consistent with the accepted P4 inputs and M3. For the real-source execution profile, an unchecked/unknown clock cannot silently become permission to probe PL. Do not require physical measurements in this repair: model good/bad/missing prerequisites with host fixtures.
- Hash/hold the exact bytes used for transfer, or retain the admitted immutable bytes and transfer those. A successful check of an earlier file read does not pin a later read. Keep honest transfer/load witnesses and the final verifier check as additional layers, not substitutes for preventing the wrong go.

No role provisioning, board contact, clock modification, memory-map relocation or scientific protocol change is authorised by this repair.

## C4 — P2: a device-format archive can silently select the legacy emulated source

Locations: `host/b4q_verify.py::load_archive/verify_source`, the trusted runner/source selection contract.

`device_source_probes.py` / `.json` creates an explicitly synthetic device-format fixture using the submitted converter. Positive control: clean=true, selected source ps-evidence-log-v1, observed_on_device=false. Delete only manifest.source: **exit 0, clean=true, agree=true, selected source emulated**, while provenance.kind remains uart-board and backend is null.

The physical-source path must not default into the legacy emulator contract just because a declaration is absent. Select/require the expected versioned source from the verified runner/source context, reject a missing/wrong source there, and retain the established legacy default only in its legitimate emulated context. Keep the positive synthetic device-format test and add this downgrade test. Do not infer actual device provenance from passing it.

## P3 — wording/remaining engineering, fold into the repair documentation

- README's first deliverables table still describes P4=control-plane/P5=opening/P6=transaction with separate authorities, while its repair table and the plan correct that. Mark the former as historical or update it.
- “Every downgrade found” overstates the no-marker test: that test intentionally accepts a device-format archive without the synthetic marker, while reporting physical provenance as NOT established. This is a defensible limit; state the actual result rather than claim it was rejected. Do not invent an impossible proof of physical origin just to reject the unmarked case.
- M5 says line timestamps are retained in console.jsonl/uboot.json. Current console entries carry indices but no line timestamps; U-Boot step timestamps are not application-line receipt times. Mark the proposed timing acquisition as remaining engineering, or implement the host instrumentation with a declared time origin. S4/no-export already being explicitly unwritten is acceptable. No hardware test is required here.

These P3 items do not justify a separate review round or unchanged suite rerun.

## Same-unit authority / focused validation

Repair C1–C4 and fold in the wording fixes **as one batch in the current unit**, then submit once. Existing host-only runner/collector/source-verifier/schema/test/plan scope covers it. Do not ask for a new undertaking, date, branch name, exact commit count or per-edit approval. No scientific model/task/threshold, PL runtime, accepted b4q_tx semantics, key-window or production-evidence change is requested.

Validate changed contracts with isolated tests and appropriate mutants/combined guards, retaining positive and coordinated negative controls. Re-run affected console/runner scenarios and fresh-process verifiers on the final relevant tree. No arbitrary JSON fuzz campaign, frozen whole-project battery, unchanged PL synthesis or unchanged image rebuild is requested. If image runtime bytes actually change for a necessary narrow collection repair, rebuild/pin them under the existing rule; do not call changed bytes unchanged.

No real serial/SSH/board contact, power/provisioning, physical load/go/PCAP, production key/seed work, push or merge is authorised. P4–P6 and the stopped scientific routes remain unchanged.

## Reproduction / package

- `coordinated_archives.py <disposable-root> <output-dir>`: final coordinated mutations and fresh CLI reports. Use a fresh work root to avoid overwriting prior copies. The script leaves them under that clone's ignored build/.
- `producer_probes.py <disposable-root>`: imported test byte-queue fixtures, ENOSPC/short-write spies, and the post-admission image mutation. A go spy call is not execution. Supply the exact copied image dependency in snapshot.json first.
- `device_source_probes.py <disposable-root> <output-dir>`: synthetic device-format positive and absent-source downgrade, each a fresh verifier.
- `tests.txt`, `bench_prerequisite.txt`, `independent_e2e_summary.json`, `integrity_checks.json`, `snapshot.json`, `review_metadata.json`: independent validation and scope. The first missing-image attempt is separately retained and is not counted as a product failure.

The disposable fixture archives are not recopied into this package. Source, final probe outcomes, fresh verifier reports and dependency hashes suffice for reproduction. SHA256SUMS covers every other file in this directory.

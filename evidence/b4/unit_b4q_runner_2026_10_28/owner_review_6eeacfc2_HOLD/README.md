# Owner review — runner repair — 6eeacfc2 — HOLD

Reviewed tip `6eeacfc2f306bf6aabcacabca4036fec82439ec3`, repair code `b9b5496a` and terminal-race repair `e49836b0`. This is the existing host-only runner/evidence undertaking, reviewed against the previous C1–C4/P3 and the standing board-role policy.

**HOLD, limited to two remaining groups R1–R2 below (both P1).** The prior literal counterexamples are now caught and the publication/stream/source repairs are accepted within their tested limits. Do not reopen the entire earlier unit or repeat unchanged work.

## Independent validation

All execution used disposable `/tmp/owner_b4q_runner_round3_0lq94x7h`, local queues, host harnesses or spy fixtures. No real serial/SSH/device contact, physical PCAP, key provisioning, seed derivation, tracked modification, commit, push or merge.

- Bench prerequisite: **1 test OK**; copied accepted netlist, not re-synthesised.
- Nine-module B4Q suite: **121 tests OK, exit 0**, 391.690 seconds. Its setup independently regenerated **43 runner cases, 43 fresh verifier agrees, zero declared-expectation failures**, and **19 PS-source console cases, 19 fresh verifier agrees**. The emulated valid control/module regressions also ran; not a separate independent full 19-case emulated rerun.
- Previous coordinated archive probes rerun unchanged: control clean; mismatched load/go address, failed CRC followed by execution, 256 MiB followed by execution, missing admission, omitted raw END and invented unknown stop all rejected. The missing-source synthetic device case is now named REFUSED; its declared-source positive remains clean.
- Previous persistence/accepted-TX/file-replacement tests passed in the full suite. The unchanged image is SHA256 `4d989ee84757f60965d2a43da9c61981366893423e3b96bd559b575edf07da5b`; no firmware changes since `dad9e4de`. Reused that exact previously independently reproduced image, no redundant build.
- IMPORT: **59 + 37 hashes match**. Protected paths unchanged against `e34432ea`; canonical tree clean.
- The terminal-END change was inspected and separately checked with transport alive and dead: `_acquire` names the same terminal tail in both states **without consulting liveness** (`terminal_race_check.py/.json`). This verifies the specific race repair, not a universal absence of flakes.
- Author’s 59-mutant record inspected, not independently repeated. No frozen whole-project battery was run or requested.

See `review_metadata.json`, `snapshot.json`, `tests.txt`, `independent_e2e_summary.json`, `integrity_checks.json` and the fresh CLI reports. All new probes below run locally and never execute an image.

## R1 — P1: the role policy can be widened by context / CLI

Locations: `host/b4q_runner.py::ExecutionContext/admit/main`; `host/b4q_verify_runner.py::verify_runner`.

The program now reads boardid and role, and default context correctly refuses reference. However, admission uses only `role in c.allowed_roles`; the verifier likewise uses only `role in ctx["allowed_roles"]`. `--role` exposes that same list. Neither checks that the requested set remains within the mandatory content-class policy `{verify, sacrificial}`.

`remaining_probes.py` / `remaining_probes.json`:

| local fixture | result |
|---|---|
| observed verify, default allowed roles | admitted (positive control) |
| observed reference, default allowed roles | refused, no PL read (correct refusal control) |
| observed reference, context allowed_roles=(reference,) | **admitted, PL read issued** |
| missing observed role, API context allowed_roles=(None,) | **admitted, PL read issued** |
| completed fixture changed coherently to raw role=reference and context/admission allowed_roles=[reference], commitments refreshed | **fresh verifier exit 0, clean=true, agree=true** |

The CLI can express the reference override with `--role reference`; the missing-role example is an additional API boundary check, not a CLI syntax claim. These are synthetic fixture operations, not contacts with a reference board.

This is the same content-class interlock required by `docs/board_roles.md` and the prior C3. The context may **narrow** eligible roles for a particular run; it is not authority to widen the standing policy. Purpose, boardid and user-selectable lists do not replace that fixed policy. A future explicit policy revision is outside this unit; none was granted here.

Repair the runtime and verifier to enforce the policy floor independently of context, and validate/narrow requested role lists. Keep missing role mapped to reference/refused. Test the default refusal, explicit CLI/API attempted widening, and the coordinated refreshed-commitment archive, alongside a valid verify/sacrificial control. No new board provisioning or role change is authorised or needed for the test.

## R2 — P1: clock admission still equates a nominal divider result with an eligible running source; verifier checks an incomplete prefix

Locations: both `fclk0_from_words` copies, runner `admit`, verifier clock/source-order branch and their fixtures.

### R2a. Known powered-down PLL still admitted

For `FPGA0_CLK_CTRL=0x00200A00`, selected `IO_PLL_CTRL=0x0001E002`, both copies return **mhz=50.0** and the runner admits and issues its first PL read. The function checks reset bit 0 and forced-bypass bit 4 but omits power-down bit 1. In this test qualification and forced bypass are clear: this is not an ambiguous bypass case.

This contradicts AMD's [IO_PLL_CTRL definition](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/Register-IO_PLL_CTRL-Details?contentId=6BqkscdadihuNAZVxMHx8g): PLL_PWRDWN=1 powers down that PLL. A normal FDIV value does not undo power-down.

The corresponding executed archive, with raw selected-PLL read and cached clock words/derivation updated together and hashes refreshed, still returns **exit 0, clean=true, agree=true**. The verifier copies the same incomplete formula. Equal outputs from the two copies are not an independent check against the register semantics.

### R2b. Bypass/operating state is unresolved

The runner also accepts selected PLL CTRL `0x0001E008`. That fixture alone does **not** prove a board is bypassed: it exposes the missing input. With PLL_BYPASS_QUAL set, BOOT_MODE's sampled bypass bit participates; forced-bypass=0 alone cannot determine the rate. The current function neither receives nor reads that state, nor the selected PLL's lock/status. See the same AMD definition and [PLL_STATUS](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/Register-PLL_STATUS-Details), summarised in `hardware_sources.md`.

Repair the supported normal-clock eligibility check using the relevant selected-source state, or conservatively refuse unsupported/unresolved modes. At minimum handle power-down, reset, active/qualified bypass and the needed selected-source readiness consistently; keep nominal rate arithmetic distinct from that eligibility. Record/bind the inputs actually relied on. This is not a request for a general clock controller, arbitrary physical-state exploration or hardware writes. Actual frequency measurement remains P4/M3 work; software register consistency must not be called a physical clock measurement.

### R2c. Required PLL read can occur after the PL read and still verify

Another coordinated fixture moves the selected IO PLL read **after VARIANT**, retaining the FPGA divider read and role query before VARIANT. Both raw streams, step order/offsets and commitments are adjusted. The fresh verifier still returns **exit 0, clean=true, agree=true**.

The current order guard checks only the FPGA0_CLK_CTRL command and the role command before first PL access. It then takes PLL values from anywhere before go, so later data retroactively satisfy the earlier PL-access prerequisite. This does not match the implemented runtime order or the claimed contract that clock eligibility was established before any PL read.

Bind *all* required identity/clock replies used for admission to the prefix available before the first PL access, not just two command substrings or values seen later before go. Add a late-selected-PLL-read negative and its proper-prefix positive. Include any new status/bypass inputs required by the repaired clock check in this prefix contract. Do not accept a later good state as evidence of an earlier safe admission.

## Accepted boundaries and small follow-up

- Earlier C1 state/address/raw-frame rules, C2 pre-go ENOSPC and accepted-byte accounting, C3 immutable admitted image and default identity order, C4 required runner source, and terminal-END race are accepted for the cases independently checked above. The two residual groups concern the role floor and completeness of the new clock check, not a restart of those repairs.
- The synthetic device-format verifier still proves internal/source consistency only. observed_on_device=false and qualification=false remain necessary; no silicon fact follows from these fixtures.
- Prior P3 document corrections are acceptable within their declared remaining engineering. Keep S4/no-export marked unwritten. Do not add a separate P3 commit/review round merely for wording.

## Same-unit authority and proportional validation

Repair **R1–R2 together** in this unit, add the isolated controls and update the source audit/bring-up description to the exact supported clock assumptions. Existing host-only runner/source/verifier/context/fixture authority covers these changes. No preliminary proposal, date, branch name, commit count or per-edit approval is required.

Run the affected admission/state/source tests and isolated/combined mutants that genuinely reach each repair. Fresh-verify the affected runner/clock/role positives and negatives, including the coordinated archive cases. If only these host admission/verifier paths change, do not repeat unrelated console scenarios, the frozen whole-project battery, PL synthesis or the unchanged image build. Broaden only if a shared-path change or a new failure justifies it. Submit the complete repaired unit once.

No real serial/SSH/board contact, power/provisioning, physical load/go/PCAP, production key/seed work, scientific-method change, push or merge is authorised. The P4/P5/P6 prerequisites and existing no-go results remain unchanged.

## Package / reproduction

- `remaining_probes.py <fresh-disposable-root> <output-directory>` uses submitted FakePort/scripted U-Boot helpers for runtime admission and fresh-process CLI verification for coherent archive mutations. It leaves fixture copies under that clone's ignored build/. The final order mutation updates both streams and reorders the corresponding step metadata; this is not merely a stale step-cache probe.
- `previous_coordinated_archives.py` and `previous_device_source_probes.py` are exact copies of the previous owner's scripts, rerun on this tree. Their scripts report outcomes rather than asserting that old defects must remain; the expected outcomes in this review are rejection.
- `terminal_race_check.py <disposable-root>` deterministically forces both liveness states without a process/device or extra assembly runs.
- Supply the copied image/netlist dependencies identified in `snapshot.json`; build the ordinary host harnesses as the submitted test setup does. The package retains scripts, final outcomes, fresh verifier reports and dependency hashes, not duplicate generated fixture archives.

SHA256SUMS covers every other file in this review directory. The reviewer left canonical tracked files and branch tips unchanged.

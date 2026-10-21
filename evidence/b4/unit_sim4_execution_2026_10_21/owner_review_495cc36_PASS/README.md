# Owner review of 495cc36 — PASS; execution-plan unit closed

Review date: 2026-10-21. Reviewed HEAD: `495cc360c97aba58bda959a2e867e6b43dbf4f7f`, branch `b4-protocol-v2`. This review reads files and metadata only; no production preflight, seed derivation/printing, smoke/mechanics/model run, batch or verifier of a production archive was invoked.

## 1. Decision and independent checks

**495cc36 PASS. The b4-sim-4 execution-plan document unit is accepted and closed.** No blocking finding. The plan preserves S=32, task-v0.2, the fixed go/no-go policy, conditional K9 with all-panel reporting, fail-closed result paths and immutable evidence. Costs are expressly estimates rather than deadline guarantees.

The actual CLI `b4_gonogo.main` checks the entire porcelain before `write_decision`. The plan's order is therefore correct: fresh batch verification, archive-only commit, blob comparison, decide on the clean tree, fresh decision verification, decision-only commit and blob comparison, then the unit record. The decision HEAD is the archive commit; the batch manifest HEAD is the execution HEAD. Neither replaces the other.

Read-only checks independently confirm:

- Clean tree at exactly the reviewed HEAD; main remains a243ee8.
- All bytes under b4/ unchanged from accepted baseline 21db2de. IMPORT has 59 matching file/base/copied-function entries, with no unlisted file. Protocol SHA256 remains `2f096d4adbd83e0ec6350e6da2942cc862e99df4e81539719fa7261dad5a258c`.
- Receipt SHA256 `68764bbc1a51ec2506bf9d9bcbb3f55f88f3d7642b5eb46c6fd3dd39f8dae146`, 66 values; registry exactly the two named historical batches; pooled exclusion 2625, with 38 historical sources; gonogo namespace absent.
- B3 surfaces and historical B4 production archives unchanged. No full tests or mutants were rerun for this documents-only unit.
- Every original file of the 21db2de owner review was copied byte-for-byte. Precisely: 74 checksum-listed artifacts, plus SHA256SUMS itself = 75 original files; the evidence copy adds SOURCE.txt, for 76 files. No missing or differing original file, no checksum failure. The delivery's shorthand “74 files” refers to the checksum-listed artifacts, not the entire directory count.
- The inventory was rerun with master_seed, pair_seeds, preflight, run_batch and Fabric.observe replaced by failing call guards. All five counters stayed zero. The script and log are retained here. This is read-only inventory, not execution preflight.

## 2. Three P3 corrections; fold into the next appropriate document record

These do not change method, parameters, command order or acceptance. They do not require a separate review round, test run or mutant run. This ruling supplies the operational clarification now; fold the wording corrections into the eventual execution-unit record or another appropriate documentation commit.

1. **Plan §1.2, main's label handling:** a243ee8 accepts the syntax `b4-sim-4` via `^b4-sim-[1-9][0-9]*$`; its retirement list contains sim-1/sim-2, not sim-4. Do not describe main as rejecting sim-4 by grammar. It is unauthorized because it is the wrong HEAD and wrong method, and lacks task-v0.2/identity/policy. The operator's exact-HEAD, b4-bytes and full protocol-digest checks, not a presumed label refusal, prevent a run on main. Source excerpts are saved in main_label_source.txt; no old tool was executed.
2. **Plan §1.1 and §2.4, target verification/storage:** setup_findings checks retained target grids/provenance/digests and rebuilds the task; it does not re-execute those target observations through a replay port. Arm engines do re-execute against ledger observations. A valid target record keeps the complete q_grid and provenance plus commitments; it is a projection of the port trace, not every field of the original port object. Refused returns keep the original returned object via the quarantine representation. Neither path proves source truth. Use these distinctions instead of implying every valid original trace object is retained or replay-executed.
3. **Plan §4, historical K9:** sim-3 has five remaining medians equal to 1.0; gate-1 has sr_mode=0.96875, with the other four equal to 1.0. The gate-1 ff_srval=0.40625 and sr_kind=0.5 values were correctly copied. The complete per-semantic values and Omega-minus-R at B=64 are independently extracted into known_archive_values.json.

For command placeholders, use the actual `out` and `gonogo_out` returned by the respective tools. The decision timestamp need not equal the batch timestamp.

## 3. Separate named execution ruling — one b4-sim-4 unit authorized

To avoid another scope/approval exchange, this review separately authorizes the complete execution unit under the following exact bounds. **This reviewer has not run it.**

| item | authorization |
| --- | --- |
| Execution HEAD | `495cc360c97aba58bda959a2e867e6b43dbf4f7f` |
| Accepted method baseline | `21db2de`, all b4/ bytes equal, protocol SHA256 as stated above |
| Start date | **2026-10-22 UTC**; no production preflight or derivation before this UTC date; if the date is missed, obtain a new date ruling without a draw |
| Execution branch | create `b4-sim-4-execution` from that exact HEAD; do not overwrite/reuse an existing branch or output directory |
| Label / planned S | `b4-sim-4` / **32** |
| Soft deadline | **3600 seconds**, unchanged policy; no operator adjustment |
| Production command | `python3 -B b4/host/b4_sim.py --label b4-sim-4 --seeds 32 --deadline-s 3600` from repository root |
| Decision command | after verified archive commit and clean-tree check: `python3 -B b4/host/b4_gonogo.py decide <actual batch out>` |
| Attempts | **one batch initiation**, no smoke, no prior seed derivation/printing, no automatic retry or replacement label |
| Commits | local archive-only, decision-only and unit-record commits following plan §5; permitted as part of this unit, no push/merge |

Start at the named existing HEAD. Do not insert a closure/P3 commit before the run: that would change the authorized execution HEAD. Keep this ruling and command outputs outside tracked paths during the batch. Archive it and the P3 wording corrections in the final unit-record commit, after both raw output commits, without modifying archive bytes.

At start, perform the plan §2.3 operator comparison. Require exact HEAD, clean tree, baseline b4/ bytes and all IMPORT entries, full protocol digest, pinned receipt/count, exact registry directories/status/digests, pooled exclusion 2625 with 38 historical sources, absent gonogo namespace, sufficient disk (at least 2 GB), and no competing work or sleep. Any discrepancy or missing check is a stop/report, never a silent repair to make the run fit. Do not change main, merge branches or import the B3 repair S0 tree.

All outputs, target records, quarantine, partials and stop records remain intact. Use actual returned paths; capture stdout/stderr/exit outside the tracked tree. Follow the plan's refusal/init-failed/abrupt/invalid/incomplete handling and label-exposure rules. A preflight refusal does not permit an automatic retry. A failure of fresh verification or blob equality is a recorded failure and a stop in the successful-acceptance path; it is never explained away or repaired in-place. Preserve and inventory failed output even when it cannot produce a clean decision record.

For a coherent completed or stopped archive, perform the plan's fresh verification and raw archive commit; on a clean archive-commit tree produce the policy record and fresh-verify it, then commit its unchanged bytes. Commit the unit record last. No extra full round is required after unchanged committed blob equality.

The fixed decision is at B_go=64: one-sided sign-test p<=0.20 and positives>negatives, all seven conditional medians>=0.50, with all 32 planned pairs complete and archive clean; otherwise no-go or no_decision as specified. Carry the old all-panel medians and every budget's descriptive record too. Do not hand-select budgets, tune numbers or replace seeds.

Return the whole execution unit once for review. Go does not authorize gate-2; no-go is a cost-policy stop, not a scientific negative result; invalid/incomplete permits no automatic successor. Gate-2 and its seeds, revisions, push, merge, full proof, RTL, 2d, purchasing and board/routing work remain unauthorized.

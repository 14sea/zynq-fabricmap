# Owner review — ae7fc35 PASS; b4-sim-5 execution plan accepted

2026-10-27. Reviewed `b4-task-v03@ae7fc3547e1f9271a430b38ffee7fd469b89a7ee`, including the documents-only closure `0a4cba3`. **PASS for the complete execution-plan unit. No blocking finding.** This accepts the plan, not an exploration result. Section 4 below is a separate, explicit execution ruling delivered with this review; the plan-writing permission alone did not permit a draw.

## 1. Independent checks

- The archived previous review: all **74 checksummed payload files**, plus SHA256SUMS itself, equal the original owner package byte for byte. The two P3 corrections faithfully distinguish decision-record policy-shape refusal from batch identity refusal, and mechanics values from production/exploration estimates.
- The committed tip is clean; `b4/` and the protected code/RTL/build paths are unchanged from accepted baseline `e20e12b`. The IMPORT checker confirms **59 entries**, file/base/copied-function digests match, no untabled tracked B4 file. `git diff --check e20e12b HEAD` is clean.
- Independently reran the submitted read-only inventory with `master_seed`, `pair_seeds`, `preflight` and `run_batch` patched to raise. **All four call counts zero.** Protocol SHA256 is `5bba53c78d08f3ad32e41a90ef37d2639ea584e97fbf74996d941cec4fe14e7f`; registry exactly the three named archives; pooled exclusion **2690**, historical sources **38**, pinned receipt **66** values.
- The document pin suite: **4 tests OK**, no skip. No full 332-test suite, mutants, mechanics batch or historical deep verification was repeated for this documents-only unit.
- Read the three existing summary documents for the plan's B64 Omega−R and K9 references; the counts, means and medians agree. This is a check of quoted archived values, not a new experiment, replay, hypothesis test or aggregation across methods. No seeds were derived or printed.
- Read the implementation of Batch.init/run_batch, the policy CLI/record writer and deep verifier. The plan correctly distinguishes in-memory derivation from persistence before observation, execution HEAD from method baseline/decision HEAD, CLI clean-tree ordering, recorded-grid replay from new observations, and the authenticity limit.

Scripts and outputs in this package document these checks. No tracked file was changed by the reviewer; no push, merge, board operation or production observation occurred.

## 2. Accepted plan and interpretation

The fixed method is v0.3.0/task-v0.3 at `e20e12b`. S32/all complete, B64, positives>negatives, one-sided sign p<=0.20 as an engineering cost threshold, and all seven conditional K9 medians>=0.50 are unchanged. Both K9 estimands remain reported. No outcome is predicted by the old results or the mechanics fixture. The cost estimates and deadline margin are explicitly uncertain; they are not measured v0.3.0 production timings.

The operator checks the authorised HEAD and inventory before starting; any mismatch stops and is reported, without editing inputs to make them fit. The single batch is followed by the retained-record verification and policy decision, with the archive committed before the production decide CLI. All raw artifacts, partials, quarantines and stop/refusal outputs are kept. A valid no-go is a cost-policy stop, not a scientific negative or silicon evidence. A go is not a gate pass or permission to run gate-2. No automatically released label, replacement label, resumed draw or tuned method is accepted.

The soft deadline is measured by the tool and checked at its declared boundaries; it is not a hard process kill. CLI exit codes do not replace the documents on disk. An init-failure flag based on a missing successful seeds write cannot establish that derivation did not occur in memory.

## 3. Nonblocking document precisions — fold into the executed unit's ordinary documentation

These do not require a new code change, test round, preliminary commit or review cycle. They do not alter the accepted operational sequence.

1. Section 5's statement that invalid/incomplete batches are "decided -> no_decision" is conditional on the writer being able to accept their records. A malformed report can instead be **refused without a decision directory**; an internally inconsistent archive can yield a self-invalidating no_decision record whose fresh verification is **not clean**. Keep that output and stop/report; never manufacture a clean decision or continue as if it were a valid result. This follows the refusal and self-validation rows already present in section 3.2 and `b4_gonogo.py` lines 264–266/294–306.
2. Section 7's future pool **2755** assumes all 65 registry values are new and distinct. Pair generation guarantees the 64 pair values avoid the pool and each other, but `master_seed` itself is a separate deterministic hash and is not screened there (nor added to pair_seeds' seen set). Report the actual set union after this batch; **do not redraw** to make the arithmetic 2755. No new derivation was performed to check this possibility. It is not a condition on this execution.
3. The existing architecture section 13 `b4-gate-2` row still says v0.2.0. When ordinary status documentation is updated, align that reserved future row with the accepted v0.3.0 route, retaining the historical v0.2.0 no-go. This is not permission to execute gate-2.

The previous closure README says “74 payload files incl. SHA256SUMS”; precisely, 74 files are checksummed, with SHA256SUMS additional. The archive bytes and checksums are correct; this counting wording has no effect on acceptance.

## 4. Separate execution ruling — one complete b4-sim-5 unit authorised

**The implementing side may now execute and complete the one bounded b4-sim-5 exploration unit under the accepted plan**, and submit the whole unit once for independent review:

- **Execution HEAD:** `ae7fc3547e1f9271a430b38ffee7fd469b89a7ee`, clean committed tree. **Accepted tool baseline:** `e20e12b`. The protocol digest, receipt, registry three entries and pooled2690 are those verified above and in the plan. If the actual inventory differs, stop and report; do not draw.
- **Label / S / soft deadline:** `b4-sim-5`, **32**, **3600 seconds**. One production batch, no prior smoke, mechanics or other seed derivation; no retry, redraw or substitute label. The command is the plan's `python3 -B b4/host/b4_sim.py --label b4-sim-5 --seeds 32 --deadline-s 3600`.
- **No calendar-date gate.** The actual UTC times are recorded. The suggested branch name is organisational; the named execution HEAD and inventory are the substantive binding. No new fixed commit count is imposed.
- Complete the accepted archive / fresh sim_verify / commit-and-blob check / decide / fresh gonogo verify / decision commit-and-blob check / unit record sequence. The policy command uses the actual returned batch path and the actual decision path is verified. Handle refusal, invalid, incomplete or interrupted work by its on-disk disposition and keep everything; anomalous verification stops progression and is reported.
- This review's archival and the section 3 documentary precisions can go into the final unit documentation **after the execution**; no pre-run closure commit is needed that would change the named execution HEAD. Work within the complete unit without asking for per-step approval; return the full result for review.

This authorises this exploration and the local commits needed to retain and verify it. **It does not authorise push/merge, gate-2, another exploration, a protocol/operator/task/threshold revision, RTL/firmware, 2d, routing or board work.** The preregistration remains unfrozen. Nothing is executed by this owner review itself.

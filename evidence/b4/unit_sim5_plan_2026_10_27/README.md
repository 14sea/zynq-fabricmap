# B4 — the `b4-sim-5` execution-plan unit (documents and a read-only inventory only, 2026-10-27)

**What this unit is.** The complete documents-only unit the owner's review of `e20e12b` (PASS, 2026-10-27, section 4) names as the next
bounded work: the plan of the one future execution of the S = 32 exploration `b4-sim-5` under protocol v0.3.0 (task-v0.3, the slice-wide
CE ½ / SR ¼ stimulus) — `docs/b4_sim5_execution_plan.md` (DRAFT v0.1) — and this directory's read-only inventory. It follows the precedent
of `docs/b4_sim4_execution_plan.md` (v0.1.1, executed once on 2026-10-21) and states where v0.3.0 differs. **Nothing was executed**: no
pre-flight, no seed derived or printed, no smoke, mechanics or model batch, no verifier of any production label, no change to any program,
table, threshold, hypothesis, archive, receipt, seed record or verdict (`b4/` is byte-identical to the accepted baseline `e20e12b`); no RTL,
board, push or merge. **The plan chooses no new probability, threshold or scientific rule**: every number in it is §9.4's and §7.2's as the
table holds them, or a cost estimated from the archived `b4-sim-4` run. The execution needs a subsequent ruling naming the execution HEAD
and the deadline (the plan's sections 1.2 and 5); the date, the branch name and the commit count are organisational (the owner's
clarification of 2026-10-21; the review of 2026-10-27, section 4).

## 1. The files

| file | what it is |
|---|---|
| `docs/b4_sim5_execution_plan.md` | the plan: §0 status index; §1 the fixed conditions (the label, S = 32, the method at the accepted baseline `e20e12b` with `protocol_sha256 5bba53c7…`, task-v0.3, K9 (b′) judged with (b) carried, the §9.4 v0.3.0 row with `p_max_go` as the table holds it, the derivation point against the pool of 2 690, the two commands, the deadline policy, the one-attempt rule), §1.1 the costs as estimates from `b4-sim-4`, §1.2 the branch and the two refs with the proposed execution HEAD / deadline (every older tree accepts the syntax `b4-sim-5`; the operator's checks, not a label refusal, keep the run on the v0.3.0 tree); §2 the tool's order of events, what it enforces versus the operator's duties, the operator's stop table (fourteen rows, incl. the task constants, the policy key, the three-entry registry and the existing go / no-go namespace), what the run writes and keeps with retention unconditional; §3 the result paths of the batch and of the decision, the label's consumption in every row, no replacement label; §4 the known records of `b4-sim-3`, `b4-gate-1` and `b4-sim-4` at B = 64 and for K9 as records, the v0.3.0 mechanics fixture as a fixture, the data-influence disclosure; §5 the acceptance order forced by the policy tool's clean-tree rule (fresh batch verify → commit 1 → blob check → `decide` → fresh decision verify → commit 2 → blob check → commit 3 the unit record); §6 the identity and the three older archives (the old decision record refused first at its policy shape); §7 what follows (a go → `b4-gate-2`'s own plan and ruling; a no-go → stop; no automatic successor); §8 what the plan does not do |
| `inventory.py` | the read-only inventory script (the `b4-sim-4` plan's script carried to v0.3.0): HEAD, branch, `main`, the porcelain, `b4/` against the baseline `e20e12b` and against the v0.2.0 baseline `21db2de` (expected to differ), the protocol identity, its digest and its `task` component, `b4/IMPORT.json`, the labels and the table's blocks (incl. `task.stimulus` and the landscape constants), the receipt, the registry, the pooled exclusion, the three namespaces, the three archives' sizes, deadline records and recorded identities, the `b4-sim-4` decision record's decision and policy keys, the disk; `master_seed` / `pair_seeds` never called, no seed printed; nothing written outside this directory |
| `inventory.txt` | its output on 2026-10-27T16:40:16Z at `0a4cba3` (the porcelain entries listed are this unit's own then-untracked files) |

## 2. The inventory, read (the values the plan's section 2.3 expects at the execution)

| item | value at this inventory |
|---|---|
| HEAD / branch / `main` | `0a4cba39626d58b22a33746993300f58197897c3` (the task-v0.3 unit's closure) / `b4-task-v03` / `a243ee8ab904d23706bd6b8fee0d76d6ccb200a5` |
| `b4/` against the accepted baseline `e20e12b` | `git diff --stat` empty (byte-identical); against `21db2de` not empty (task-v0.3, as expected) |
| `protocol_sha256` | `5bba53c78d08f3ad32e41a90ef37d2639ea584e97fbf74996d941cec4fe14e7f` (`architecture_revision` v0.3.0 informational); the `task` component: `version task-v0.3`, `ce_high_one_in 2`, `sr_high_one_in 4`, `broadcast {0: 0, 1: 255}`, the stimulus rule, the planted rule, salt 1413567047, `holdout_salt 2779096485`, K 6 / 8, two level steps, 21 bits |
| `b4/IMPORT.json` | 59 entries, sha256 `9de52e257e2b5c733118b097ffdb5ba69b941726b815bace302a6d1d8eecf02b` |
| labels | exploration `b4-sim-5`, gate `b4-gate-2`; retired `b4-sim-1`, `b4-sim-2`; consumed `b4-gate-1`, `b4-sim-3`, `b4-sim-4` (`b4_seeds` and the table agree) |
| the policy | S 32, B_go 64, `p_max_go` 0.2 (`p_max_go_standing`: an engineering cost threshold, not an α), the seven conditional K9 medians ≥ 0.5, every planned pair complete and valid else no decision; `applies_to` `b4-sim-5` (protocol v0.3.0), `b4-sim-4` not re-decided |
| the task block | task-v0.3, salt 1413567047, 2 setup observations per pair, ceilings 64 / 80; `stimulus`: ce slice-wide ½, sr slice-wide ¼ independent, d per element, draw order ce, sr, d, K 6 / 8, two level steps; `b4_landscape` `TASK_VERSION task-v0.3`, `CE_HIGH_ONE_IN 2`, `SR_HIGH_ONE_IN 4`, `BROADCAST {0: 0x00, 1: 0xFF}` |
| the exposure receipt | `68764bbc1a51ec2506bf9d9bcbb3f55f88f3d7642b5eb46c6fd3dd39f8dae146`, 66 values (pinned, count 66) |
| the registry | three run directories: `b4-gate-1_20261020T102526Z` (`seeds`, `785e76988d4e6ec49cfb86b7b896358b484e5899d48700ee1bcfffd6e034bced`, 401 values), `b4-sim-3_20261019T121833Z` (`seeds`, `1a0d1e7b91132ed6814a9e369e23f2c55f28886448fa5efd55d722182f50b17d`, 65 values), `b4-sim-4_20261021T065339Z` (`seeds`, `ae179c376282ae61f7057765a061105badee5e0d576a161af5fa43dd6c7e0296`, 65 values) |
| the pooled exclusion | 2 690 values, 38 historical sources |
| the namespaces | `evidence/b4/sim/` (the three archives), `evidence/b4/gate/` (`b4-gate-1`), `evidence/b4/gonogo/` (`b4-sim-4_20261021T065857Z` only; the policy tool adds a sibling) |
| the archives | `b4-sim-3`: 643 files, 193 230 267 bytes, complete, 209.702 s of 3 600, no identity; `b4-gate-1`: 4 003 files, 1 202 331 492 bytes, complete, 1 372.077 s of 3 600, no identity; `b4-sim-4`: 771 files, 200 674 002 bytes, complete, 199.256 s of 3 600, identity `2f096d4a…` |
| the `b4-sim-4` decision record | no-go, formal, head `580c0e5…`, its `policy` block keyed with `alpha_go` (hence refused first at the v0.3.0 verifier's policy-shape check) |
| disk | 483.4 GB free of 1 081.1 |

## 3. What this unit does not claim, and what it does not authorise

No value of `b4-sim-5` exists; no production / exploration estimate of record of the v0.3.0 coverage exists; the plan predicts no outcome
and no decision; the costs are estimates from the `b4-sim-4` run; a go would be a cost-policy proxy and not a gate result, a no-go a
cost-policy stop and not a scientific negative conclusion. The exploration's execution (its HEAD and deadline), `b4-gate-2`, any revision,
push, merge, RTL, 2d and board / routing work remain the owner's. The unit is submitted once, whole, for the owner's review.

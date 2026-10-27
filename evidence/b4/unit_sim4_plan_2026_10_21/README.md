# B4 — the `b4-sim-4` execution-plan unit (documents and a read-only inventory only, 2026-10-21)

**What this unit is.** The pure-document unit the owner authorised in the review of `21db2de` (PASS, 2026-10-21, section 6): the plan of
the one future execution of the S = 32 exploration `b4-sim-4` under protocol v0.2.0 — `docs/b4_sim4_execution_plan.md` (DRAFT v0.1) — and
this directory's read-only inventory. It follows the precedent of `docs/b4_gate_execution_plan.md` (v0.2.1, ACCEPTED) and states where
v0.2.0 differs. **Nothing was executed**: no pre-flight, no seed derived or printed, no smoke, mechanics or model batch, no verifier of any
production label, no change to any program, table, threshold, hypothesis, archive, receipt, seed record or verdict; no RTL, board, push or
merge. The execution needs a subsequent ruling naming the execution HEAD, the date and the deadline (the plan's sections 1.2 and 5).

## 1. The files

| file | what it is |
|---|---|
| `docs/b4_sim4_execution_plan.md` | the plan: §0 status index; §1 the fixed conditions (the label, S = 32, the method at the accepted baseline `21db2de` with `protocol_sha256 2f096d4a…`, task-v0.2, K9 (b′) judged with (b) carried, the §9.4 policy as the table holds it, the derivation point, the two commands, the deadline policy), §1.1 the costs as estimates, §1.2 the branch and the two refs with the proposed execution HEAD / date / deadline; §2 the tool's order of events, what it enforces versus the operator's duties, the operator's stop table, what the run writes and keeps; §3 the result paths of the batch (refused / init_failed / abrupt termination / invalid incl. the quarantine of a refused target return / incomplete incl. the interrupt after a quarantine / complete) and of the decision (refused / no_decision / go / no-go), the label's consumption in every row; §4 the known records of `b4-sim-3` and `b4-gate-1` at B = 64 and for K9, under the old task and applicability, as records, with the data-influence disclosure; §5 the acceptance order forced by the policy tool's clean-tree rule (fresh batch verify → commit 1 → blob check → `decide` → fresh decision verify → commit 2 → blob check → commit 3 the unit record); §6 the identity and the old archives; §7 what follows (a go → `b4-gate-2`'s own plan and ruling; a no-go → stop; no automatic successor); §8 what the plan does not do |
| `inventory.py` | the read-only inventory script: HEAD, branch, `main`, the porcelain, `b4/` against the baseline, the protocol identity and its digest, `b4/IMPORT.json`, the labels and the table's blocks, the receipt, the registry, the pooled exclusion, the three namespaces, the two archives' sizes and deadline records, the disk; `master_seed` / `pair_seeds` never called, no seed printed; nothing written outside this directory |
| `inventory.txt` | its output on 2026-10-21T05:09:33Z at `21db2de` (the porcelain entries listed are this closure's own then-untracked files) |

## 2. The inventory, read (the values the plan's section 2.3 expects at the execution)

| item | value at this inventory |
|---|---|
| HEAD / branch / `main` | `21db2de362b4f1f3bac635d01803ac765b931e3e` / `b4-protocol-v2` / `a243ee8ab904d23706bd6b8fee0d76d6ccb200a5` |
| `b4/` against the accepted baseline `21db2de` | `git diff --stat` empty (byte-identical) |
| `protocol_sha256` | `2f096d4adbd83e0ec6350e6da2942cc862e99df4e81539719fa7261dad5a258c` (`architecture_revision` v0.2.0 informational) |
| `b4/IMPORT.json` | 59 entries, sha256 `a6af67efd18d47829a91f6041a53b98a240d2d16802cda8f45f233f7fbe91b4e`; `import_check.py`: all equal, no untabled file |
| labels | exploration `b4-sim-4`, gate `b4-gate-2`; retired `b4-sim-1`, `b4-sim-2`; consumed `b4-gate-1`, `b4-sim-3` |
| the policy | S 32, B_go 64, α_go 0.2, the seven conditional K9 medians ≥ 0.5, every planned pair complete and valid else no decision |
| the task block | task-v0.2, salt 1413567047 (0x54415247), 2 setup observations per pair, ceilings 64 / 80 |
| the exposure receipt | `68764bbc1a51ec2506bf9d9bcbb3f55f88f3d7642b5eb46c6fd3dd39f8dae146`, 66 values (pinned, count 66) |
| the registry | two run directories: `b4-gate-1_20261020T102526Z` (`seeds`, `785e76988d4e6ec49cfb86b7b896358b484e5899d48700ee1bcfffd6e034bced`, 401 values), `b4-sim-3_20261019T121833Z` (`seeds`, `1a0d1e7b91132ed6814a9e369e23f2c55f28886448fa5efd55d722182f50b17d`, 65 values) |
| the pooled exclusion | 2 625 values, 38 historical sources |
| the namespaces | `evidence/b4/sim/` (the two archives), `evidence/b4/gate/` (`b4-gate-1`), `evidence/b4/gonogo/` **does not exist** (created by the policy tool) |
| the archives | `b4-sim-3`: 643 files, 193 230 267 bytes, complete, 209.702 s of 3 600; `b4-gate-1`: 4 003 files, 1 202 331 492 bytes, complete, 1 372.077 s of 3 600 |
| disk | 515.9 GB free of 1 081.1 |

## 3. What this unit does not claim, and what it does not authorise

No value of `b4-sim-4` exists; the plan predicts no outcome and no decision; the costs are estimates from v0.1.16 runs; a go would be a
cost-policy proxy and not a gate result, a no-go a cost-policy stop and not a scientific negative conclusion. The exploration's execution,
`b4-gate-2`, any revision, push, merge, RTL, 2d and board / routing work remain the owner's.

# B4 — the executed unit of the exploration `b4-sim-5` (one batch, one decision: **complete, no-go**; 2026-10-27)

**What this unit is.** The one execution of the S = 32 exploration `b4-sim-5` under protocol v0.3.0 (task-v0.3, the slice-wide CE ½ / SR ¼
stimulus) that the owner's review of `ae7fc35` (PASS, 2026-10-27, section 4 — archived in `owner_review_ae7fc35_PASS/`) authorised, run as
`docs/b4_sim5_execution_plan.md` (DRAFT v0.1) says. **The batch completed (32 / 32 pairs, 349.419 s of 3 600, no quarantine, no stop
record, self-validation empty); the fixed §9.4 policy (the v0.3.0 row) decided no-go at B = 64: positives 9 > negatives 7 (ties 16), but
the one-sided sign-test p 0.4018096923828125 > the cost threshold `p_max_go` 0.2; the seven conditional K9 medians were all ≥ 0.50
(`sr_kind` exactly 0.5).** Both records were fresh-process verified clean before their commits and their committed bytes equal the verified
files. **A no-go is the cost policy's stop — not a scientific negative conclusion, not evidence about the fabric, not a statement that the
class is indistinguishable — and nothing follows from it automatically** (plan §3.2, §7). Not done: no push, no merge, no second batch, no
replacement label, no tuning, no gate, no RTL or board work.

## 1. The commits of this unit (branch `b4-sim-5-execution`, created from the execution HEAD; nothing pushed, nothing merged)

| commit | content | before it | after it |
|---|---|---|---|
| execution HEAD **`ae7fc3547e1f9271a430b38ffee7fd469b89a7ee`** | the tree the batch read (the plan unit's commit on `b4-task-v03`; `b4/` byte-identical to the accepted tool baseline `e20e12b`) | the operator's stop (section 3) | — |
| commit 1 **`d1e0e2cc33e9cdfbdf65270a89277599a17ccd74`** | the archive `evidence/b4/sim/b4-sim-5_20261027T170605Z/` exactly as the tool wrote it: 771 files, 200 300 381 bytes, nothing else | `b4_sim_verify.py` deep, fresh process: clean (`sim_verify.txt`) | Git-blob check 771 / 771 equal (`blob_digest_check_commit1.txt`) |
| commit 2 **`61733c55e49ed39737f537eae4f01aaf700f8ca4`** | the decision `evidence/b4/gonogo/b4-sim-5_20261027T171342Z/` (`gonogo.json`, `gonogo.md`) exactly as written, nothing else | `b4_gonogo.py decide` on the clean tree at commit 1; `b4_gonogo.py verify` deep, fresh process: clean (`gonogo_verify.txt`) | Git-blob check 2 / 2 equal (`blob_digest_check_commit2.txt`) |
| commit 3 (this directory) | the unit record: this README, the run and decision headers / outputs / exit records, the operator's stop script and output, the inventory re-run at the start, the two verification outputs, the two blob checks, the owner's review of `ae7fc35` byte for byte (`SOURCE.txt`) | — | — |
| the documentation commit after it | `docs/b4_architecture.md` §13 / §14 and the plan's status note with the owner's three non-blocking precisions (section 7; the review's section 3 says they go into the executed unit's ordinary documentation, after the execution) | — | — |

**Two HEADs, kept apart (plan §1.2, §5.4).** The batch's `manifest.json` and `sim_report.json` record `head = ae7fc35…` (what the batch read).
The decision's `gonogo.json` records `head = d1e0e2c…` (commit 1 — the policy tool refuses a dirty tree, and an uncommitted archive is an
untracked entry, so the archive is committed before `decide`); its `batch.head` is `ae7fc35…`. Neither replaces the other. The decision
timestamp (`17:13:42Z`) is not the batch timestamp (`17:06:05Z`). The commit count is the precedent's, not a gate (the ruling).

## 2. The timeline (UTC, 2026-10-27) — every number from the files in this directory

| step | start | end | record |
|---|---|---|---|
| the operator's stop, of record | 17:05:53 | — | `operator_stop_check.txt`: **20 rows OK, 0 DIFF, exit 0**; `inventory_at_start.txt` (the plan unit's read-only inventory re-run) |
| the batch `python3 -B b4/host/b4_sim.py --label b4-sim-5 --seeds 32 --deadline-s 3600` (`run_batch.sh`) | 17:06:04 | 17:11:54 | `run_header.txt`, `run_stdout.txt` (status complete, exit 0, the `out` path), `run_stderr.txt` (empty), `run_exit.txt` (EXIT 0) |
| fresh `b4_sim_verify.py` deep | 17:12:09 | 17:13:23 | `sim_verify.txt`: `findings {}`, `clean true`, EXIT 0 |
| commit 1 and its blob check | — | 17:13:35 | `blob_digest_check_commit1.txt`: EQUAL |
| `python3 -B b4/host/b4_gonogo.py decide evidence/b4/sim/b4-sim-5_20261027T170605Z` | 17:13:42 | 17:14:57 | `decide_header.txt`, `decide_stdout.txt` (status no-go, exit 0, the `gonogo_out` path), `decide_stderr.txt` (empty), `decide_exit.txt` (EXIT 0) |
| fresh `b4_gonogo.py verify` deep | 17:15:05 | 17:16:20 | `gonogo_verify.txt`: `findings {}`, `clean true`, EXIT 0 |
| commit 2 and its blob check | — | 17:16:33 | `blob_digest_check_commit2.txt`: EQUAL |

Wall time from the batch start to the second blob check: ≈ 10.5 min (17:06:04Z → 17:16:33Z); the batch itself 349.419 s of the 3 600 s
soft deadline (52 779 deadline checks, `expired false`). The batch was **within the plan's estimated range** (5.8 min against ≈ 3–10 min;
slower than `b4-sim-4`'s 199 s on the same host, which has no bearing on the evidence); each fresh verification 74–75 s and the decision 75 s
(≈ 1–3 min estimated); the file count 771 and 200.3 MB against ≈ 770 / ≈ 200 MB. One worker; no competing b4 process (checked by the stop
script). The actual `out` / `gonogo_out` paths the tools returned are the ones used.

## 3. The operator's stop (plan §2.3; `operator_stop_check.py`, reads only — `master_seed` / `pair_seeds` never called, no seed printed)

All rows equal at 17:05:53Z (no calendar-date gate; the UTC time recorded): HEAD `ae7fc3547e1f9271a430b38ffee7fd469b89a7ee`; branch
`b4-sim-5-execution` (organisational); `main` still `a243ee8`; porcelain (untracked = all) empty; `git diff --stat e20e12b HEAD -- b4/` empty;
`b4/IMPORT.json` 59 entries, sha256 `9de52e257e2b5c733118b097ffdb5ba69b941726b815bace302a6d1d8eecf02b`, `import_check.py` all digests equal
and no untabled file; `protocol_sha256` `5bba53c78d08f3ad32e41a90ef37d2639ea584e97fbf74996d941cec4fe14e7f` (`architecture_revision` v0.3.0
informational) with the identity's `task` component task-v0.3 / ce 2 / sr 4 / broadcast {0: 0, 1: 255}; the landscape constants and the
table's task block (draw order ce, sr, d; salt 1413567047; two setup observations; ceilings 64 / 80); labels exploration `b4-sim-5` / gate
`b4-gate-2` / retired `b4-sim-1`, `b4-sim-2` / consumed `b4-gate-1`, `b4-sim-3`, `b4-sim-4` (the table agreeing); the §9.4 policy S 32 / B_go 64 /
`p_max_go` 0.2 (no `alpha_go`) / K9 min 0.5 / `applies_to` `b4-sim-5`; receipt `68764bbc1a51ec2506bf9d9bcbb3f55f88f3d7642b5eb46c6fd3dd39f8dae146`,
66 values, pinned 66; registry exactly `b4-gate-1_20261020T102526Z` (`seeds`, `785e76988d4e6ec4…`, 401), `b4-sim-3_20261019T121833Z` (`seeds`,
`1a0d1e7b91132ed6…`, 65) and `b4-sim-4_20261021T065339Z` (`seeds`, `ae179c376282ae61…`, 65) and nothing else under `evidence/b4/sim/`; pooled
exclusion 2 690 values from 38 historical sources; `evidence/b4/gonogo/` holding exactly `b4-sim-4_20261021T065857Z`; no `b4-sim-5_*`
directory; 483.3 GB free; no competing b4 process. Nothing was repaired to make a row fit; nothing differed.

## 4. The identity the batch recorded (from `manifest.json` / `sim_report.json` / `seeds.json`, read, not derived)

| field | value |
|---|---|
| `head` | `ae7fc3547e1f9271a430b38ffee7fd469b89a7ee` |
| `label` / `count` / `deadline_s` / `fixture` | `b4-sim-5` / 32 / 3600 / false |
| `generated_utc` (manifest / report) | `2026-10-27T17:06:05Z` / `2026-10-27T17:11:54Z` |
| `protocol.identity.protocol_sha256` | `5bba53c78d08f3ad32e41a90ef37d2639ea584e97fbf74996d941cec4fe14e7f` (`architecture_revision` v0.3.0) |
| identity components (as recorded) | `hypothesis_sha256 59948f9be3b4516547fbf039556d4aa6a4afd0b2dda2324619e4d40ef0651ed8`, `certificate_sha256 c69e419f836684872c9edb3754cdb7c76591aaabf69859dab448454c6d78ceef`, `exposure_receipt_sha256 68764bbc…`, `import_table_sha256 3f79eefa725414bb942587436e99063498f323b540216a31d0d79eaa6d99ffbe` (the identity's canonical digest of the table; the file's own sha256 is `9de52e25…`), engine `b4-es-v0.1` (arms R F O X, μ 4, λ 8, kmax 4), cartographer `b4-obs-carto-v0.1`, the `task` component with the task-v0.3 stimulus rule, the per-file `inventory` of `b4/host/` |
| `constants.stimulus` | the task-v0.3 rule, `ce_high_one_in` 2, `sr_high_one_in` 4, `broadcast {0: 0, 1: 255}`, the model input contract |
| `exclusion` | receipt 66 values (`68764bbc…`); `registry_snapshot` the three historical directories above with their `seeds` digests; `historical_sources` 38; `pooled_total` 2 690 |
| `seeds.json` | `count` 32, `label b4-sim-5`; sha256 `b638d300c815d0907ec0c66a61c1e82607400ca74c1fe6cf8e1953dab1523bba` (the decision's evidence binding); **no seed value is reproduced here** |
| `manifest.json` / `sim_report.json` sha256 (the decision's evidence binding) | `be28f4e64bf082bb3509e0a9a428837807f29fe9167c75609d573a820336178d` / `54613dabd94a4e73aff81ce179f17f8c4b78a41601f9b10b78abe69b43fc5e8c` |
| report | `status complete`, `pairs` 32, `missing []`, `stopped` none, `self_validation {}`, `deadline {elapsed_s 349.419, seconds 3600, expired false, checks 52779}`; `candidate_B_star` null (the budget rule's candidate does not exist on this S; not invented), `eligible_budgets []` |
| the archive | 771 files, 200 300 381 bytes; no `*.QUARANTINE.json`, no `STOPPED.json`, no `INIT_FAILED.json`, no `.part` |

From this point on `b4-sim-5`'s master and pairs are in the registry and in the pooled exclusion of every later derivation (plan §3.2,
"the label, in every row"): the label is consumed by its records. **The actual pool after this batch (the owner's precision 2, read by set
arithmetic from the committed registry, no derivation, no value printed): the registry holds four sets; the new set has 65 distinct values,
0 of them in the other three registry sets and 0 in the receipt; `load_exclusion_set` gives 2 755 = 2 690 + 65.** The arithmetic held; had it
not, the actual union would have been reported and nothing redrawn.

## 5. The decision and both statistics — copied from `gonogo.json` / `gonogo.md`, not summarised

**`decision = "no-go"`, `formal = true`, `formal_reasons []`, `contract_findings []`, `self_validation {}`, `clean_tree true`, `head d1e0e2c…`.**
`reason`: "no-go: at B = 64 the one-sided sign-test p 0.4018096923828125 > the cost threshold p_max_go 0.2 — the exploration is archived as a
result; what follows needs its own ruling (no automatic successor)".

Precondition: `S_is_32 true`, `every_pair_complete true`, `status_complete true`, `summary_present true`.

**Statistic 1 — Ω − R at B_go = 64:** positives **9**, negatives **7**, ties **16**, mean **0.03125**, Cohen's d **0.011027027284780772**,
one-sided sign-test p **0.4018096923828125**; `positives_gt_negatives true`, `p_le_p_max_go false` (`p_max_go` 0.2, "an engineering cost
threshold on the sign test's p, not the alpha of a formal scientific test").

**Statistic 2 — K9, `judged_estimand = conditional_sr_driven`, `min 0.5`, `all_ge_min true`:**

| semantic | (b′) conditional median (judged) | (b) all-panel median (descriptive, carried) | seeds with a positive control (b′ / b) |
|---|---|---|---|
| ce_mode | 0.875 | 0.875 | 32 / 32 |
| clock_mode | 1.0 | 1.0 | 32 / 32 |
| ff_init | 1.0 | 1.0 | 32 / 32 |
| ff_srval | **0.8333333333333334** | 0.4166666666666667 | 29 / 29 |
| sr_kind | **0.5** | 0.25 | 25 / 25 |
| sr_mode | 0.875 | 0.875 | 29 / 29 |
| storage_kind | 1.0 | 1.0 | 32 / 32 |

(`k9.fraction_of_S 0.78125`, `seeds_with_all_seven_positive_controls` 25; 0 not-assessable seeds in every semantic; `k10`: 32 / 32 interacting,
τ = 2, 0 not assessable.)

**Ω − R at every budget (descriptive; B = 64 is the policy's only budget, none other is picked):**

| B | positives | negatives | ties | mean | d | sign-test p |
|---|---|---|---|---|---|---|
| 8 | 4 | 15 | 13 | −3.40625 | −0.2624524482470899 | 0.9977874755859375 |
| 16 | 4 | 15 | 13 | −4.34375 | −0.39083241881612885 | 0.9977874755859375 |
| 24 | 8 | 14 | 10 | −4.71875 | −0.38102793517998595 | 0.9330997467041016 |
| 32 | 9 | 11 | 12 | −3.65625 | −0.37060675543468613 | 0.7482776641845703 |
| 48 | 8 | 11 | 13 | −1.5 | −0.3516677590652254 | 0.8203582763671875 |
| **64** | **9** | **7** | **16** | **0.03125** | **0.011027027284780772** | **0.4018096923828125** |
| 96 | 9 | 2 | 21 | 0.3125 | 0.14455534152860666 | 0.03271484375 |
| 128 | 6 | 3 | 23 | 0.46875 | 0.24029162745540172 | 0.25390625 |
| 192 | 7 | 3 | 22 | 0.5625 | 0.28846459742239733 | 0.171875 |
| 256 | 4 | 4 | 24 | 0.34375 | 0.16459062535345328 | 0.63671875 |

(n = 32 and median 0.0 at every budget; the population variances are in `gonogo.json`.)

**What these numbers are and are not.** The sign test is the fixed policy statistic at one pre-named budget; the per-budget rows are
descriptive and none of them is a second test — in particular the p 0.0327 at B = 96 is **not** a result and no budget is re-picked (plan
§3.1, §9.4). The K9 (b′) medians ≥ 0.50 mean the conditional-coverage precondition of the policy was met, under the v0.3.0 applicability —
`sr_kind` at exactly the threshold 0.5 with 25 of 32 seeds carrying a positive control; they are not a result about the all-panel coverage:
the all-panel medians `ff_srval` 0.4167 and `sr_kind` 0.25 are below 0.5. This is the first archive under task-v0.3 and the first with a
positive mean and positives > negatives at B = 64 (`b4-sim-3` 10 / 12 / 10, p 0.738; `b4-gate-1` 56 / 95 / 49, p 0.9995; `b4-sim-4` 7 / 13 / 12,
p 0.9423 — all under other tasks and refused by name by this tool); the plan predicted no outcome and this README draws no conclusion from
the four beyond what the policy wrote. No production / exploration estimate of coverage is claimed by this unit either: the K9 medians are
the policy's precondition values of one S = 32 archive.

## 6. The disposition (plan §3.1 row "complete", §3.2 row "no-go")

The batch is archived as a result; the decision is archived as a result; **the exploration stops here.** What follows — a different grouping
shape, a different operator, a different stimulus, or stopping — needs its own argument and its own ruling. On this unit's authority there
is no tuning, no automatic retry, no replacement seed or label (`b4-sim-6` is a name nobody has proposed), no second exploration, no next
protocol version, and nothing of the carrier, the board or the routing line moves. `b4-gate-2` remains a reserved name of which no value
exists; a go would not have authorised it either.

## 7. The owner's three non-blocking precisions of the review of `ae7fc35` (section 3), folded in as the ruling directs

1. **Plan §5 step 1 — "an `invalid` or `incomplete` batch is still … decided (→ `no_decision`)" is conditional** on the policy's record writer
   accepting the batch's records: a malformed report is **refused without a decision directory** (exit 2, nothing written); an internally
   inconsistent archive can yield a self-invalidating `no_decision` record whose fresh verification is **not clean**. Either output is kept,
   the unit stops and reports; a clean decision is never manufactured and the work never continues as if a valid result existed (the plan's
   §3.2 refusal and `self_validation` rows; `b4_gonogo.py`). Not exercised by this run (the batch was complete and the decision clean).
2. **Plan §7's future pool "2 755"** assumed the 65 new registry values to be new and distinct; pair generation screens the 64 pair values
   against the pool and each other but the master is a separate deterministic hash not screened there. The actual union is reported in
   section 4 (2 755, with 0 collisions); the rule stands: report the actual union, never redraw to make the arithmetic.
3. **`docs/b4_architecture.md` §13's `b4-gate-2` row** said "the S = 200 gate under v0.2.0"; the documentation commit after this unit aligns the
   reserved row with the accepted v0.3.0 route, retaining `b4-sim-4`'s historical v0.2.0 no-go. Not a permission to execute `b4-gate-2`.

Also noted by the review: the task-v0.3 closure README's "74 payload files incl. `SHA256SUMS`" is precisely 74 checksummed files plus
`SHA256SUMS`; the bytes and checksums are correct. The documentation commit corrects that wording.

## 8. What this unit does not do

No push, no merge (`main` is still `a243ee8`; `b4-task-v03` is still `ae7fc35`); no second batch, no smoke, no retry, no replacement label;
no change to any program, table, threshold, hypothesis, old archive, receipt, seed record or verdict (`b4/` is byte-identical to `e20e12b`
at every commit of this unit); no `b4-gate-2` plan; no RTL, 2d, routing, purchasing or board work. The unit is returned whole for the
owner's review.

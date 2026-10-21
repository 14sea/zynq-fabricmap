# B4 — the executed unit of the exploration `b4-sim-4` (one batch, one decision: **complete, no-go**; 2026-10-21)

**What this unit is.** The one execution of the S = 32 exploration `b4-sim-4` under protocol v0.2.0 that the owner's review of `495cc36`
(PASS, 2026-10-21, section 3 — archived in `owner_review_495cc36_PASS/`) authorised, run as `docs/b4_sim4_execution_plan.md` (DRAFT v0.1)
says, with the owner's same-day correction of the start date (`owner_date_correction_2026_10_21.txt`: 2026-10-21 **or** 2026-10-22 UTC
instead of 2026-10-22 only; HEAD, S, deadline and every other bound unchanged). **The batch completed (32 / 32 pairs, 199.256 s of 3 600,
no quarantine, no stop record, self-validation empty); the fixed §9.4 policy decided no-go at B = 64 (positives 7, negatives 13, ties 12,
one-sided sign-test p 0.9423408508300781); the seven conditional K9 medians were all ≥ 0.50.** Both records were fresh-process verified
clean before their commits and their committed bytes equal the verified files. **A no-go is the cost policy's stop — not a scientific
negative conclusion, not evidence about the fabric, not a statement that the class is indistinguishable — and nothing follows from it
automatically** (plan §3.2, §7). Not done: no push, no merge, no second batch, no replacement label, no tuning, no gate, no RTL or board work.

## 1. The three commits of this unit (branch `b4-sim-4-execution`, created from the execution HEAD; nothing pushed, nothing merged)

| commit | content | before it | after it |
|---|---|---|---|
| execution HEAD **`495cc360c97aba58bda959a2e867e6b43dbf4f7f`** | the tree the batch read (the plan's closure on `b4-protocol-v2`; `b4/` byte-identical to the accepted tool baseline `21db2de`) | the operator's stop (section 3) | — |
| commit 1 **`580c0e5d06079dfe9ad885e69aaec23ff13ffcaa`** | the archive `evidence/b4/sim/b4-sim-4_20261021T065339Z/` exactly as the tool wrote it: 771 files, 200 674 002 bytes, nothing else | `b4_sim_verify.py` deep, fresh process: clean (`sim_verify.txt`) | Git-blob check 771 / 771 equal (`blob_digest_check_commit1.txt`) |
| commit 2 **`adce0275e20681e1309f5719b2365e0c2ee631d3`** | the decision `evidence/b4/gonogo/b4-sim-4_20261021T065857Z/` (`gonogo.json`, `gonogo.md`) exactly as written, nothing else | `b4_gonogo.py decide` on the clean tree at commit 1; `b4_gonogo.py verify` deep, fresh process: clean (`gonogo_verify.txt`) | Git-blob check 2 / 2 equal (`blob_digest_check_commit2.txt`) |
| commit 3 (this directory) | the unit record: this README, the run and decision headers / outputs / exit records, the operator's stop script and both of its outputs, the two verification outputs, the two blob checks, the owner's review of `495cc36` byte-for-byte and the date correction | — | — |

**Two HEADs, kept apart (plan §1.2, §5.4).** The batch's `manifest.json` and `sim_report.json` record `head = 495cc36…` (what the batch read).
The decision's `gonogo.json` records `head = 580c0e5…` (commit 1 — the policy tool refuses a dirty tree, and an uncommitted archive is an
untracked entry, so the archive is committed before `decide`); its `batch.head` is `495cc36…`. Neither replaces the other. The decision
timestamp (`06:58:57Z`) is not the batch timestamp (`06:53:39Z`), as the owner's review notes it need not be.

## 2. The timeline (UTC, 2026-10-21) — every number from the files in this directory

| step | start | end | record |
|---|---|---|---|
| the operator's stop, dry pre-check (the day before the ruling's original date; only the date row differed) | 06:38:55 | — | `operator_stop_precheck_2026_10_21.txt` (DIFF on the date only; the other 19 rows OK) |
| the owner's date correction received; the guard in the ignored script changed to "2026-10-21 or 2026-10-22" | — | — | `owner_date_correction_2026_10_21.txt` |
| the operator's stop, of record | 06:53:35 | — | `operator_stop_check.txt`: **20 rows OK, 0 DIFF, exit 0** |
| the batch `python3 -B b4/host/b4_sim.py --label b4-sim-4 --seeds 32 --deadline-s 3600` | 06:53:39 | 06:56:58 | `run_header.txt`, `run_stdout.txt` (status complete, exit 0, the `out` path), `run_stderr.txt` (empty), `run_exit.txt` (EXIT 0) |
| fresh `b4_sim_verify.py` deep | 06:57:15 | 06:58:29 | `sim_verify.txt`: `findings {}`, `clean true`, EXIT 0 |
| commit 1 and its blob check | — | 06:58:48 | `blob_digest_check_commit1.txt`: EQUAL |
| `python3 -B b4/host/b4_gonogo.py decide evidence/b4/sim/b4-sim-4_20261021T065339Z` | 06:58:57 | 07:00:11 | `decide_header.txt`, `decide_stdout.txt` (status no-go, exit 0, the `gonogo_out` path), `decide_stderr.txt` (empty), `decide_exit.txt` (EXIT 0) |
| fresh `b4_gonogo.py verify` deep | 07:00:17 | 07:01:31 | `gonogo_verify.txt`: `findings {}`, `clean true`, EXIT 0 |
| commit 2 and its blob check | — | 07:01:47 | `blob_digest_check_commit2.txt`: EQUAL |

Wall time from the batch start to the second blob check: ≈ 8.1 min (06:53:39Z → 07:01:47Z); the batch itself 199.256 s of the 3 600 s
soft deadline (52 779 deadline checks, `expired false`). The plan's estimates (batch ≈ 4–10 min, each verification ≈ 1.5–3 min, ≈ 770
files / ≈ 200 MB) held: 3.3 min, 74 s and 74 s, 771 files / 200.7 MB. One worker; no competing b4 process (checked by the stop script).

## 3. The operator's stop (plan §2.3; `operator_stop_check.py`, reads only — `master_seed` / `pair_seeds` never called, no seed printed)

All rows equal at 06:53:35Z: date within the corrected ruling; HEAD `495cc360c97aba58bda959a2e867e6b43dbf4f7f`; branch `b4-sim-4-execution`;
`main` still `a243ee8`; porcelain (untracked = all) empty; `git diff --stat 21db2de HEAD -- b4/` empty; `b4/IMPORT.json` 59 entries, sha256
`a6af67efd18d47829a91f6041a53b98a240d2d16802cda8f45f233f7fbe91b4e`, `import_check.py` all digests equal and no untabled file; `protocol_sha256`
`2f096d4adbd83e0ec6350e6da2942cc862e99df4e81539719fa7261dad5a258c` (`architecture_revision` v0.2.0 informational); labels exploration
`b4-sim-4` / gate `b4-gate-2` / retired `b4-sim-1`, `b4-sim-2` / consumed `b4-gate-1`, `b4-sim-3`; the §9.4 policy S 32 / B_go 64 / α_go 0.2 /
K9 min 0.5; receipt `68764bbc1a51ec2506bf9d9bcbb3f55f88f3d7642b5eb46c6fd3dd39f8dae146`, 66 values, pinned 66; registry exactly
`b4-gate-1_20261020T102526Z` (`seeds`, `785e76988d4e6ec4…`, 401) and `b4-sim-3_20261019T121833Z` (`seeds`, `1a0d1e7b91132ed6…`, 65) and nothing
else under `evidence/b4/sim/`; pooled exclusion 2 625 values from 38 historical sources; `evidence/b4/gonogo/` absent; no `b4-sim-4_*`
directory; 511.9 GB free; no competing b4 process. Nothing was repaired to make a row fit; nothing differed.

## 4. The identity the batch recorded (from `manifest.json` / `sim_report.json` / `seeds.json`, read, not derived)

| field | value |
|---|---|
| `head` | `495cc360c97aba58bda959a2e867e6b43dbf4f7f` |
| `label` / `count` / `deadline_s` / `fixture` | `b4-sim-4` / 32 / 3600 / false |
| `generated_utc` (manifest / report) | `2026-10-21T06:53:39Z` / `2026-10-21T06:56:58Z` |
| `protocol.identity.protocol_sha256` | `2f096d4adbd83e0ec6350e6da2942cc862e99df4e81539719fa7261dad5a258c` (`architecture_revision` v0.2.0) |
| identity components (as recorded) | `hypothesis_sha256 59948f9be3b4516547fbf039556d4aa6a4afd0b2dda2324619e4d40ef0651ed8`, `certificate_sha256 c69e419f836684872c9edb3754cdb7c76591aaabf69859dab448454c6d78ceef`, `exposure_receipt_sha256 68764bbc…`, `import_table_sha256 73ea4f3e142daa74be079ed8be7dba0e82bffd32429968ec8e6b1c838e526f31` (the identity's canonical digest of the table; the file's own sha256 is `a6af67ef…`), engine `b4-es-v0.1` (arms R F O X, μ 4, λ 8, kmax 4), cartographer `b4-obs-carto-v0.1`, the per-file `inventory` of `b4/host/` |
| `exclusion` | receipt 66 values (`68764bbc…`); `registry_snapshot` the two historical directories above with their `seeds` digests; `historical_sources` 38; `pooled_total` 2 625 |
| `seeds.json` | `count` 32, `label b4-sim-4`; sha256 `ae179c376282ae61f7057765a061105badee5e0d576a161af5fa43dd6c7e0296` (the decision's evidence binding); **no seed value is reproduced here** |
| `manifest.json` / `sim_report.json` sha256 (the decision's evidence binding) | `70a435824c1677473c34f761a0b88636835c84d1bee9754bea7a79bd91a6676b` / `01744b39598b10bbf7d4371be1e5b9355c08fc39a8877ef6957866ac8178f1fa` |
| report | `status complete`, `pairs` 32, `missing []`, `stopped` none, `self_validation {}`, `deadline {elapsed_s 199.256, seconds 3600, expired false, checks 52779}` |
| the archive | 771 files, 200 674 002 bytes; no `*.QUARANTINE.json`, no `STOPPED.json`, no `INIT_FAILED.json`, no `.part` |

From this point on `b4-sim-4`'s master and pairs are in the registry and in the pooled exclusion of every later derivation (plan §3.2,
"the label, in every row"): the label is consumed by its records.

## 5. The decision and both statistics — copied from `gonogo.json` / `gonogo.md`, not summarised

**`decision = "no-go"`, `formal = true`, `formal_reasons []`, `contract_findings []`, `self_validation {}`, `clean_tree true`, `head 580c0e5…`.**
`reason`: "no-go: at B = 64 positives 7 are not more than negatives 13; at B = 64 the one-sided sign-test p 0.9423408508300781 > 0.2 — the
exploration is archived as a result; what follows needs its own ruling (no automatic successor)".

Precondition: `S_is_32 true`, `every_pair_complete true`, `status_complete true`, `summary_present true`.

**Statistic 1 — Ω − R at B_go = 64:** positives **7**, negatives **13**, ties **12**, mean **−1.71875**, Cohen's d **−0.3531074633217678**,
one-sided sign-test p **0.9423408508300781**; `positives_gt_negatives false`, `p_le_alpha_go false` (α_go 0.2).

**Statistic 2 — K9, `judged_estimand = conditional_sr_driven`, `min 0.5`, `all_ge_min true`:**

| semantic | (b′) conditional median (judged) | (b) all-panel median (descriptive, carried) |
|---|---|---|
| ce_mode | 1.0 | 1.0 |
| clock_mode | 1.0 | 1.0 |
| ff_init | 1.0 | 1.0 |
| ff_srval | **0.8125** | 0.40625 |
| sr_kind | **0.875** | 0.4375 |
| sr_mode | 1.0 | 1.0 |
| storage_kind | 1.0 | 1.0 |

(`k9.fraction_of_S 1.0`; every semantic 32 seeds with a positive control, 0 not assessable; `k10`: 32 / 32 interacting, τ = 2.)

**Ω − R at every budget (descriptive; B = 64 is the policy's only budget, none other is picked):**

| B | positives | negatives | ties | mean | d | sign-test p |
|---|---|---|---|---|---|---|
| 8 | 7 | 13 | 12 | −1.84375 | −0.16670022639547 | 0.9423408508300781 |
| 16 | 6 | 14 | 12 | −3.875 | −0.3359847412190017 | 0.9793052673339844 |
| 24 | 7 | 12 | 13 | −0.84375 | −0.09757025178093509 | 0.9164657592773438 |
| 32 | 5 | 14 | 13 | −1.5 | −0.19230973161493153 | 0.9903945922851562 |
| 48 | 7 | 11 | 14 | −0.875 | −0.1257263280188742 | 0.8810577392578125 |
| **64** | **7** | **13** | **12** | **−1.71875** | **−0.3531074633217678** | **0.9423408508300781** |
| 96 | 9 | 10 | 13 | −1.25 | −0.28556017368430914 | 0.6761970520019531 |
| 128 | 5 | 10 | 17 | −1.1875 | −0.30865070014336937 | 0.940765380859375 |
| 192 | 6 | 6 | 20 | 0.40625 | 0.09754311729437715 | 0.61279296875 |
| 256 | 7 | 5 | 20 | 0.34375 | 0.11536778241162536 | 0.38720703125 |

(n = 32 and median 0.0 at every budget; the population variances are in `gonogo.json`.)

**What these numbers are and are not.** The sign test is the fixed policy statistic at one pre-named budget; the per-budget rows are
descriptive and none of them is a second test. The K9 (b′) medians ≥ 0.50 mean the conditional-coverage precondition of the policy was
met, under the v0.2.0 applicability — they are not a result about the all-panel coverage, whose medians for `ff_srval` and `sr_kind`
remain below 0.5 as they were in `b4-sim-3` and `b4-gate-1` (plan §4). Beside the known records (plan §4: `b4-sim-3` at B = 64
positives 10 / negatives 12 / ties 10 / p 0.738; `b4-gate-1` 56 / 95 / 49 / p 0.9995) this batch is a third record with the same sign of
Ω − R at B = 64; the plan predicted no outcome and this README draws no conclusion from the three beyond what the policy wrote.

## 6. The disposition (plan §3.1 row "complete", §3.2 row "no-go")

The batch is archived as a result; the decision is archived as a result; **the exploration stops here.** What follows — a different
grouping shape, a different operator, a different stimulus, or stopping — needs its own argument and its own ruling. On this unit's
authority there is no tuning, no automatic retry, no replacement seed or label (`b4-sim-5` is a name nobody has proposed), no second
exploration, no next protocol version, and nothing of the carrier, the board or the routing line moves. `b4-gate-2` remains a reserved
name of which no value exists; a go would not have authorised it either.

## 7. The three P3 wording corrections of the owner's review of `495cc36` (section 2), folded in here as the ruling directs

The plan document `docs/b4_sim4_execution_plan.md` is not edited by this unit (the ruling permits the three commits above and the
corrections "in the eventual execution-unit record or another appropriate documentation commit"); the corrected statements are these,
and they govern over the plan's wording where the two differ:

1. **Plan §1.2 — `main`'s label handling.** `main` (`a243ee8`, the v0.1.16 tool) **accepts** the syntax `b4-sim-4` (`LABEL_RE
   ^b4-sim-[1-9][0-9]*$`); its retirement list holds `b4-sim-1` / `b4-sim-2` only. The plan's "refuses the label by nothing but its grammar"
   is wrong. A run on `main` is unauthorised because `main` is the wrong HEAD and the wrong method — no task-v0.2, no protocol identity,
   no §9.4 policy — and what prevents it is the operator's exact-HEAD, `b4/`-bytes and full-protocol-digest checks (section 3), not a
   presumed label refusal. The owner's read-only source excerpts are in `owner_review_495cc36_PASS/main_label_source.txt`.
2. **Plan §1.1 and §2.4 — the target's verification and what is stored.** `setup_findings` checks the retained target grids, provenance and
   digests and **rebuilds the task** from them; it does **not** re-execute the two target observations through a replay port (the arm
   engines are what re-execute against the ledger observations). A valid target record keeps the complete `q_grid`, the provenance and the
   commitments: it is a **projection** of the port trace, not every field of the original port object. A refused return keeps the original
   returned object through the quarantine representation. Neither path proves the source's truth. Read the plan's "every raw target
   return … kept" with these distinctions: the retained grids are complete, the trace is retained as its projection, nothing is
   replay-executed for the target.
3. **Plan §4 — the historical K9 values.** `b4-sim-3`: `ff_srval` 0.4270833333333333, `sr_kind` 0.5, the **other five 1.0**. `b4-gate-1`:
   `ff_srval` 0.40625, `sr_kind` 0.5, **`sr_mode` 0.96875**, the other four 1.0. The two low values were copied correctly in the plan; the
   remaining medians are completed here from the owner's independent extraction `owner_review_495cc36_PASS/known_archive_values.json`.

Two further notes from the same review, now applied: the actual `out` / `gonogo_out` returned by the tools are the paths used
(`b4-sim-4_20261021T065339Z`, `b4-sim-4_20261021T065857Z`); the decision timestamp need not equal the batch timestamp.

## 8. What this unit does not do

No push, no merge (`main` is still `a243ee8`; `b4-protocol-v2` is still `495cc36`); no second batch, no smoke, no retry, no replacement
label; no change to any program, table, threshold, hypothesis, old archive, receipt, seed record or verdict (`b4/` is byte-identical to
`21db2de` at every commit of this unit); the plan document and `docs/b4_architecture.md` §13 are not edited here (a routine documentation
commit after the owner's review of this unit may record the executed status); no `b4-gate-2` plan; no RTL, 2d, routing, purchasing or
board work. The unit is returned whole for the owner's review.

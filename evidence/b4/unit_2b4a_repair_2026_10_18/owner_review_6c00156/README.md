# Owner review of 33c1739 / 6c00156 — HOLD

Reviewed 2026-10-18. `b4-prework` is `6c001562e4283a5b27374fcfbd3a744631b7832a`, 26 local commits above main;
main remains `d5bf81569140482bded46138a7bdf896eff63bd7`. No tracked file, ref, production exploration namespace,
ruling or board was changed. These review files are ignored.

The preceding concrete probes are now rejected and runtime publication checks work. **The batch still needs repair:**
complete status is not bound to a diagnostic's actual completion, some nested types remain permissive, and the offline
deadline record can contradict both its manifest and its own elapsed time. These are recorded-contract checks; they do
not require proving the observation source's truthfulness or the actual passage of wall-clock time offline.

## Independent verification and scope

- Reviewed code extracted with `git archive 6c00156` into `/tmp/b4_owner_6c00156_3mc7z1rw`; 51 B4/document files
  compared byte-for-byte to the live tree, no differences (`scope_check.json`).
- Full B4 discovery in that snapshot: **240 tests, OK, 193.724 s**, no skip/failure/error (`tests.txt`). As in the previous
  review, an outer mock rejects a production `b4-sim-*` / `b4-gate-*` master derivation, while the integration tests guard
  both production seed functions. Outer guard calls: **[]**. Command: `python3 -B` bootstrap with
  `unittest.TestLoader().discover('b4/tests', pattern='test_b4_*.py')` and `TextTestRunner(verbosity=2)`.
- The delivered 57-mutant battery independently reran in the snapshot: **57 / 57 killed, 661 s**, each `Ran N > 0 / FAILED`,
  no survival, baseline failure, edit miss or no-run (`mutants.txt`). Exact command from the snapshot:
  `python3 -B evidence/b4/unit_2b4a_repair_2026_10_18/b4_2b4a_mutants.py /tmp/b4_owner_6c00156_mutants.txt`.
- IMPORT: **49 entries match**, base/function digests match, no unregistered tracked B4 file (`import_check.txt`). Also
  independently hashed all **6 external + 14 repository sources**, no differences (`scope_check.json`).
- Model, hypothesis files, engine, cartographer, replay, execution, landscape, RNG, statistics primitives, seed module
  and thresholds are byte-identical to `f2c4bca`. Scope remains host-only and no threshold/grid/tau/anchor was altered.
- The three renamed `round1_*` verification files are byte-identical to their `f2c4bca` versions. The 239-vs-240 commit
  message discrepancy is disclosed and is not a new finding.
- Exposure disposition is unchanged. This review derives no production seed, reconstructs no missing production set
  and does not claim the historical exclusion set complete.

## What the second round fixed

`probes_results.json` re-runs the previously preserved negative archives with the reviewed verifier:

| previous probe | new result |
|---|---|
| R recorded written / audit missing, including flipped RNG | refused by complete-pair invariant |
| self-consistent R under exposed seed 12 in plan saying 11 | refused by planned wrapper binding |
| wrapper pair 99 / role O | refused by role and planned binding |
| manifest dropout descriptor / 21 null addresses | refused by full formal source descriptor checks |
| observation id false | refused by exact integer check |
| floating interaction index | refused by exact integer check |

The new defence-in-depth path was inspected: when record validators are mocked away it still re-audits complete-pair
arms. The M52 test deliberately exercises that layer instead of mistaking an earlier refusal for proof of the deep check.

`finalisation.py` independently runs **full `run_batch`** twice on a hermetic tree, literal exposed mechanics schedule
`((7,11),)` and guards on both production seed functions:

| event after the real final verifier returns clean | observed result |
|---|---|
| clock advances 10,000 s beyond a 60-s deadline | **incomplete / exit 3**, kind deadline, stage publication; current expired-time record, no pooled summary |
| architecture input changes | **invalid / exit 1**, kind input_drift, stage publication; no pooled summary |

Both stopped archives verify cleanly as stopped archives (`finalisation_results.json`). Thus the previous runtime R4/R5
paths are fixed; the deadline issue below is a remaining *offline record-consistency* gap, not a recurrence of runtime
success publication after the final verifier.

## 1. P1 — R1 residual: a genuine partial K10 can still belong to a complete batch

Locations: `b4_sim_verify.py:102`, `:338`–`:352`; complete-state declarations in `b4_sim_schema.py:680`.

The report validator now requires the planned K10 state to say complete. The verifier never binds that declaration to
`k10.json.complete`, `stopped`, `invalid` or the actual number of completed units before treating the pair as complete.

Reproduction (`probes.py`, `probes_results.json:partial_k10_complete_batch`):

1. Build a **fresh complete mechanics S=1 baseline using the reviewed code**, exposed pair (7,11); independent deep
   verification returns `{}`. Its path and all modified-archive paths are recorded in the JSON.
2. Use production `k10.seed_k10`, the same task and formal fabric, and a check that raises `StopWork` before unit 2.
   This yields a genuine valid partial: **1 / 420 units**, `complete:false`, a stopped record, no per-seed max/outcome.
3. Replace only `k10.json` with that partial, preserving the wrapper; leave report/pair status and planned K10 state
   complete. Recompute the pooled summary and every file digest/index.
4. K10's typed validator returns `[]`; **archive-wide deep verification returns `{}`**. The complete batch now publishes
   the missing K10 measurement as one not-assessable seed in its pooled summary.

This is not legitimate all-S accounting of an incomplete batch: the fixed policy says the batch must stop, keep partials
and publish no pooled numeric summary. The plan's state must be confirmed by the evidence, not be its own authority.

Required fix: enforce the diagnostic state-to-file contract for K7/K9/K10 before pooled-row construction. A complete pair
requires actual complete diagnostic documents, no stopped/invalid state and the full fixed comparison set. Valid partials
must remain valid under an appropriately stopped/partial batch. Add a negative with a **valid production partial and all
hashes/summary recomputed**; testing only a changed planned-state string is not enough.

## 2. P2 — R3 residual: remaining counts and corner genomes are not type-exact

Locations: `b4_sim_schema.py:560`; `b4_k9.canonical_findings`; `b4_k10.py:171`.

Independent one-change archives (`types_probe.py`, `types_results.json`), every digest refreshed:

- `k9.json.pairs_total`: integer 1184 -> floating-point **1184.0**.
- `k10.json.units_total`: integer 420 -> floating-point **420.0**.
- first K10 unit's corner `00.genome`: integer 0 -> boolean **false**.

For all three, the typed validator returns `[]` and the deep verifier returns `{}`. The checks still rely on Python numeric
equality for these fields. The canonical comparisons added to other paths do not cover them. These mutations preserve
the numeric conclusion; the issue is malformed data admitted under the promised exact-type contract.

Required fix: exact integer/range checks on the remaining total counts and corner genomes before equality, arithmetic
or references; use the existing `_int` / `_genome` helpers consistently. Extend focused negatives beyond the particular
id/index fields from the previous review; preserve total validators and valid partials.

## 3. P2 — R2/R4 residual: offline deadline copies and arithmetic can contradict each other

Locations: `b4_sim_verify.py:157`–`:183`, `b4_sim_schema.py:722`.

The manifest records the pre-observation deadline. The report's deadline is only required to be a dict with `expired:false`
for complete status; neither the manifest binding nor basic elapsed-time consistency is checked.

Two independent archives from the fresh reviewed-code baseline:

- Change manifest `deadline_s` to **1**, update its hash/identity/index. The report still says **3600 s** and its recorded
  elapsed time is already greater than 1 s. **Deep verifier returns `{}`** (`probes_results.json:manifest_deadline_mismatch`).
- Leave manifest/report deadline at **3600 s**, change report `elapsed_s` to **10000**, leave `expired:false` and complete
  status. **Deep verifier returns `{}`** (`deadline_archive_results.json`).

No claim is made that offline verification can reconstruct the actual monotonic clock. It can and should refuse a record
whose own declared duration/elapsed/expiry fields disagree, and bind the duration to the manifest written before work.

Required fix: validate the complete deadline record's field types/ranges and self-consistency; bind report and STOPPED
duration to manifest `deadline_s`; complete status cannot carry an elapsed time unambiguously beyond that bound. Retain the soft-unit overrun
policy: valid late stopped archives must remain acceptable and keep their observations. Add negatives reindexed so that
hash checking cannot be mistaken for the time-contract check.
Make the timing snapshot and its published precision consistent: elapsed time is currently rounded to milliseconds, so
the boundary rule must be explicit about that precision rather than accidentally rejecting an otherwise valid sub-ms
boundary record. The reproduced 10,000-vs-3,600-second contradiction is far outside any rounding boundary.

## Probe provenance

Scripts and JSON/stdout are beside this report. Commands are `python3 -B build/wip/owner_review_6c00156_2026_10_18/` plus
`probes.py`, `types_probe.py`, `deadline_archive.py` and `finalisation.py`. They import the reviewed snapshot and forbid
both production seed functions. Only literal, previously exposed mechanics pair **(7,11)** is executed. The extra K10
diagnostic uses the same exposed task seed and is deliberately stopped at one unit. There is no seed scan, threshold
selection, S=32 exploration, gate result or inferred arm advantage.

The first probe iteration used the previous review's already verified complete archive. To remove version/context doubt,
all new residual probes were repeated from a **fresh complete baseline generated with this reviewed code**; the first
script/results are retained as `probes_attempt1*`. The final JSON records the fresh baseline and its verification.

## Disposition

**HOLD on the repair batch**, with three residual findings above. The original concrete seed/role/source/type negatives
and runtime publication regressions are now fixed. Keep all commits and raw records. No implementation was silently
changed by this review. Exposure disposition remains separate; S=32, gate, full proof, push/merge and board work remain
unauthorised.

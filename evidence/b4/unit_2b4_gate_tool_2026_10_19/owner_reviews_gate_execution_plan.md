# The owner's reviews of the gate execution plan (2026-10-20), as relayed by the user — 6d4b339 HOLD, then b15a572 PASS with two P3 wording corrections folded into this closure (build/wip/owner_review_6d4b339_2026_10_20/README.md and build/wip/owner_review_b15a572_2026_10_20/README.md; their raw artifacts stay in those ignored directories)

## The review of 6d4b339 (HOLD; also the merge-timing decision)

# Owner review: merge timing and gate execution plan 6d4b339

Date: 2026-10-20. Reviewed branch: `b4-prework`, HEAD `6d4b339`.
This review was read-only apart from this ignored report directory. No branch switch, merge, push, deletion,
simulation, test, seed derivation or board operation was performed.

## 1. Merge strategy decision

**Recommended integration boundary: merge B4 prework after the execution-plan document is corrected and accepted,
before production gate execution. There is no need to wait for the scientific gate outcome to integrate this accepted
host-tool milestone. Actual push/merge remains a separately named action, not authorized by this timing decision.**

| branch | disposition |
|---|---|
| `b4-prework` | appropriate next integration candidate after the plan corrections below; preserve an engineering milestone independently of the eventual gate outcome |
| `b3-pinned-test-repair` | retain as the isolated, accepted repair tree; **do not directly merge it into current main** |
| `wip/stage5-stack-followup2` | do not merge the RED WIP branch; retain it for now; no deletion or new tag is authorized here |

### Why the proposed repair-first merge is wrong

The repair branch does not change only documents and tests. Its 47-file difference includes the header generator,
firmware header/import inventory, ELF/build evidence, canonical plan, pin table and manifest.

| current path / state | main d5bf815 | repair 4db22e5 |
|---|---|---|
| B3 manifest | S3 PLANNED, qualified=true, plan bound; SHA 258bb14c… | S0 INIT, qualified=false, plan=null; SHA aae789aa… |
| B3 pin table | 73cec93a… | fa5a06c8… |
| canonical B3 plan | b202a280… (determined split) | fbd922ba… (rate-less) |
| ELF / build evidence | historical lifecycle-2 bytes | repair build bytes |

A direct merge would replace main's default historical S3 identity with a new S0 identity, while the eight completed ruling
pairs and result still bind the historical S3 manifest. It does not delete the evidence or invalidate history at its original
commit, but it changes what the default current paths mean. That migration was never part of the repair-tree acceptance.
Being conflict-free in Git does not make it the correct integration.

B4's accepted cross-branch references explicitly say those repair documents are on `b3-pinned-test-repair` at `4db22e5`,
not merged. They are valid provenance references already; they do not require merging the repair tree. Future integration
of the repair must preserve historical B3 identities under an explicitly reviewed version/lifecycle arrangement, rather than
overwrite them as incidental housekeeping.

Independent checks: main is an ancestor of current B4; main has no branch-only commits relative to B4; the B4 branch has
**zero differences** in `b3/`, `host/`, `tests/`, `firmware/`, `manifests/`, `evidence/b3/` versus main.
See `read_only_checks.json` for exact refs and digests. Hence B4 does not depend on merging the repair first.

When a final candidate is accepted, use a separately authorized `--no-ff` merge, preserve the accepted checkpoint,
verify the merged content against that candidate and verify the B3 historical identities remain unchanged. Commit count
alone is not a reason to integrate. Large evidence size should be disclosed, but ordinary clones already fetch advertised
remote branches by default; the change in transfer size depends on clone/fetch options, not merely whether main is merged.

## 2. Execution-plan review: HOLD for document corrections only

The fixed S, unchanged methods/model/thresholds, no pre-draw, valid FAIL disposition, no automatic rerun, version-coupling
boundary and separate execution authorization are appropriate. The remaining issues are in the plan, not new tool repairs.
Fix them together in a document-only follow-up; do not run tests, production preflight, simulation or seed derivation.

### P2-A: correct the start ordering and distinguish operator rules from tool enforcement

`docs/b4_gate_execution_plan.md:52` says derivation occurs after seeds.json is written. Production
`b4/host/b4_sim.py:412` and `:426` instead do:

**derive master/pairs in memory -> write seeds.json as the first output file -> write manifest.json -> observations**.

Correct that order. The important guarantee is persistence before the first observation, not persistence before derivation.
Also correct section 2's claim that every checklist item is tool-enforced. No prior smoke/no prior derivation, keeping the
computer awake and the owner's authorized identity/registry expectations are operator obligations; they are not all checked
by the tool. The tool snapshots the registry it actually reads and holds it during the batch; it does not know a separately
approved expected snapshot.

State an explicit operator stop if the actual HEAD/tool bytes, receipt or registry/exclusion identity differs from the
execution authorization; do not silently accept a newly pooled registry. Keep `00336d0` as the accepted tool baseline and
separately record the **actual authorized execution HEAD**, which will differ after a document commit or merge. Do not
substitute the baseline hash for what the manifest reads. The operator checks must not derive or print new seeds.

### P2-B: include refusal, initialization failure and abrupt termination in the disposition

The current four-row table only covers outputs after initialization succeeds. `b4_sim.run_batch` also returns:

- `refused`, exit 2, possibly no output directory, before initialization;
- `init_failed`, exit 2, with an output directory but potentially only INIT_FAILED.json / partial files, no sim_report,
  no STOPPED and no gate directory (`b4/host/b4_sim.py:890–911`);
- an abrupt process/machine failure can leave only the durable prefix and external stdout/stderr/exit information.

Add these paths. Capture stdout/stderr and exit status from the command, preserve every existing file, inventory which
expected files are absent, stop and report, and do not try to manufacture a valid report or demand both normal archive
verifiers exit 0 where the required documents do not exist. A CLI exit alone does not distinguish a valid FAIL from a
contract failure; the actual documents/status must decide.

Crucially, `INIT_FAILED.seeds_derived` is populated from `batch.seeds_sha is not None`, i.e. whether a successful seeds.json
write was recorded. **false does not prove that no in-memory derivation occurred**: derivation precedes that write.
For initialization/write failure or an uncertain interruption, retain the label as consumed or exposure-uncertain pending
owner adjudication; no automatic retry or label release. This unit should disclose that limitation, not edit the tool.

## 3. Additional document corrections, in the same follow-up

### Costs and verification count

- The committed S=32 elapsed value is 209.702 seconds **after batch finish/self-verification**, not an arms-and-statistics
  subtotal. `Batch.finish` performs the batch deep verification before recording the final elapsed value. Do not add another
  full scaled batch self-verification to the 209.7-second extrapolation without accounting for this inclusion.
- K5's S/N scan is not linearly scaled by 6.25, so retain an explicit uncertainty range; the runtime estimate is not a proof
  of a 1.5x deadline margin. Deadline 3600 remains the recommendation, for the execution ruling to name; a larger deadline
  is not an operator-selectable "harmless" extension of the authorization.
- Owner choice for this plan: **one fresh-process batch verifier plus one fresh-process gate verifier, before committing the
  raw archive; after commit, compare Git-blob digests with the verified files.** No second full deep-verification round is
  required solely because bytes were committed unchanged. Align sections 1.1 and 5 with those two fresh processes. If a new
  mutation/failure justifies another run, record its reason separately.
- Keep all estimates labeled as estimates, including storage/pack size. An increase in git pack size from several different
  units is not a measurement of the next archive's compressibility.

### Known-risk wording

Section 4 groups K7 with rows showing no deficit, but this sample has B*=null. K7's at-B* criterion is therefore
**not assessable**; prefix medians from 2 to 21 are descriptive and include values below 11. Report its actual status and
prefix values separately, without implying a passed K7 criterion. Preserve the correct K9 equality/101-seed discussion
and the cautious K5 interpretation.

### Versioning options and dependency diagram

- Scheme B is not safely implemented by changing two threshold comparisons. Schema validation, summary recomputation and
  gate judgement also use the current module table/method. Reword its cost as version selection across the applicable
  verification/judgement stack, under a separate design; do not implement it here. Old archives and their bindings stay intact.
- The ASCII diagram currently draws G -> 2c-obs, contradicting the correct bullet that only 2c-rest depends on G. Correct the
  arrow. Keep the already accepted observation-contract -> carrier design order and unresolved full-freeze placement.
- Do not commit a B4 stage equivalence by saying B4Q "is the S2-equivalent" while B4's stage contract is unresolved. Call it
  the qualification/calibration node, with any mapping to stages still to be ruled.
- Independent B4-R preregistration does not remove common prerequisites or the standing roadmap ordering. Replace "shares
  nothing" with its own R1–R7 plus shared provisioning/power dependencies and existing roadmap interlocks; FF completion
  does not satisfy those conditions. No new routing authorization is implied.

## 4. Next boundary

Complete these document corrections in one follow-up, retain 6d4b339, and submit the final tip for one review. The B4
engineering milestone can then be the next main integration **before** the production gate; the execution plan must be
updated to use the final execution ref named by a later ruling. This review authorizes neither the actual merge/push nor
production execution. The repair and RED WIP branches remain unmerged and undeleted.


## The review of b15a572 (PASS)

# Owner review of b15a572 — execution plan v0.2

Date: 2026-10-20. Verdict: PASS for the execution-plan document unit, with the two P3 wording corrections below to accompany closure. They do not require another engineering review or a test rerun.

Scope: read-only review of the full plan, its diff from 6d4b339, the preceding owner checklist, and relevant production code. No tests, simulations, production preflight, seed derivation, branch switch, push, merge or board operation performed. Only this ignored review directory was written.

## Accepted corrections

- In-memory derivation precedes seeds.json, then manifest.json, then observations. Persistence before observation is the guarantee.
- Tool enforcement and operator obligations are separated. Execution HEAD and accepted tool baseline 00336d0 are distinct. A mismatch in the authorized identities or registry/exclusion stops execution.
- Refusal, init_failed and abrupt termination are separately retained and reported. INIT_FAILED.seeds_derived=false is not evidence of no derivation, and cannot release a potentially exposed label.
- Runtime estimates include the harness's own deep verification; the deadline margin remains unproved. The verification of record is one fresh-process batch verifier and one fresh-process gate verifier before committing, with committed-byte checks afterwards.
- K7 at B* is not assessable without B*. The version-selection options remain future design, and the dependency diagram no longer makes the observation contract depend on the gate or assign B4 stages prematurely.
- Model, methods, thresholds, architecture, programs and archives are unchanged. The only tracked difference from 00336d0 is docs/b4_gate_execution_plan.md. git diff --check is clean.

## P3 corrections to fold into the document-only closure commit

1. K7 counting correction, including correction of my preceding review: the ten listed prefix medians are 2, 3, 4, 5, 7, 9, 13.5, 16, 19, 21. SIX, not five, are below 11 (budgets 8 through 64). The first value above 11 remains at B=96. The preceding owner review incorrectly said five; the implementation agent followed that error. Correct the plan's revision note and section 4 together, and record this owner correction without rewriting history. No archive or statistic changes.

2. Narrow the deep-verification wording in section 1.1 and section 5: each arm is re-executed against ReplayPort's recorded ledger observations and re-audited; it is not re-observed on Fabric. K7 and summaries are recomputed; K9 also uses the formal model for its applicable-semantics calculation, and K9/K10 conclusions are recomputed from retained grids. A clean verification establishes internal execution/derived-result consistency and source binding, not the truth of the observation source. See b4_replay.py's authenticity limit and b4_sim_verify.py's deep path. Replace 'every arm re-executed on the model' and 'archive re-executed on the formal model' accordingly. No program change.

These are documentation corrections, not grounds for another HOLD or a new tool repair. They may be combined with closure archiving in one commit, without rerunning tests or deriving any seed.

## Boundary

Acceptance of this plan is not a gate outcome or an execution authorization. The next suitable integration milestone is b4-prework after the document-only closure corrections. Actual push/merge remains separately authorized; no merge or push permission is granted here. b3-pinned-test-repair and the RED WIP branch remain separate and undeleted. No production b4-gate-1 execution, seed derivation, RTL, 2d, routing or board work is authorized by this review.

# Owner review of the 2b-4a batch, cdf2c53 (2026-10-18)

**Verdict: HOLD.** A 8939fb9, B feda985, C edfc93c and evidence cdf2c53 are retained. No implementation, threshold, hypothesis, main ref, ruling, board input or tracked file changed in this review. No S=32 batch was launched. See probes.py/probes.json and probes_more.py/probes_more.json for independently reproduced counterexamples; all custom runtime probes use an explicitly mocked seed schedule (landscape=7, operator=11) and mocked master, never a newly derived production set. Their directories under /tmp are retained in probe_roots*.json.

## Validation and its limits

- Read all 12 newly delivered host modules, relevant tests, archived mutant definitions and authorised scope. Old engine/carto/replay/execution/landscape/stats/RNG/ff-model/ff-loader/mapping production modules remain unchanged relative to 740d92c.
- 48 IMPORT entries, all file/base/copied-function digests independently match; registration exactly covers the tracked B4 surface. The copied statistics retain B2 arithmetic and random.Random behaviour.
- Independently completed **207 tests, OK** (safe_tests.txt): the suite excluding the unsafe integration class paths, plus pure summary/validator tests. This is not claimed as 218/218.
- Independently re-ran **21/21 mutants**, green baselines and actual named-test failures, using the archived battery on snapshot cdf2c53. safe_mutants.txt. The other 11 were inspected, not re-run, because their targets may derive production exploration seeds. The author's archived 32/32 result is retained as author evidence, not relabelled independent validation.
- An initial attempted full-suite rerun was interrupted with exit130 after finding the seed problem below. It had already entered integration tests and run some same production-derived pairs on /tmp copies. original_suite_interrupted.txt is preserved; this review does not claim those observations did not happen. Subsequent probes explicitly substitute the fixed exposed seed schedule, and do not assess arm advantage or print K distributions as findings.
- Scope/import checks in scope_import_check.txt. git diff --check 740d92c..cdf2c53 flags ONE trailing space in the raw tests.txt command header. This is a raw-log formatting note, not a code blocker; keep the raw log untouched and correct the claim rather than editing original evidence.

## F1 — P1: integration tests derive and observe production exploration sets; evidence says otherwise

Locations: b4/tests/test_b4_sim.py:45, :149, :193; b4/host/b4_sim.py:252; evidence/b4/unit_2b4a_2026_10_18/README.md verification paragraphs.

build_hermetic copies the real formal hypothesis and historical exclusion sources, including the actual pinned hypothesis digest. CompleteBatch invokes run_batch with label b4-sim-1, S=2, real master_seed/pair_seeds and no seed substitution. It even asserts equality with master_seed('b4-sim-1', HYPOTHESIS_SHA256). Other integration cases repeatedly generate production-derived sets; archiving earlier test batches changes subsequent exclusions. The b4-sim-2 case also derives an actual label-2 set. Using a different filesystem root does not make the seed values fake.

This violates the authorised fixed-exposed-seed mechanics boundary and contradicts the README assertions that only a master was printed, no pair derived and integration tests used fake anchors. The seed unit tests use fake anchors; that fact does not extend to test_b4_sim. Mutant baselines that run these tests do it again. It is NOT evidence that the author intentionally selected outcomes; it IS prior exposure and an incomplete record.

Fix: isolate integration tests with explicit fixed fixture seed schedules/anchors or a hermetic fixture input strategy; prove no production pair derivation is reached. No production CLI bypass. Preserve current logs and correct the history. Recover all available test seed records and label/anchor/exclusion snapshots, including failed/mutant attempts; list uncertainty where temp directories were deleted. Do not silently change the anchor/label, redraw or declare exclusions complete. The treatment of this prior exposure must be settled before authorising actual exploration. My interrupted rerun must be included in that account; later custom probes only use already-exposed 7/11.

## F2 — P1: validate_run_dir validates surviving file shapes, not the archive or its conclusions

Location: b4/host/b4_sim_schema.py:446; b4/host/b4_sim.py:455.

Independently, each of these returns {} from validate_run_dir(task_of=...):
1. Change pair_000/curves.json O curve to all zero, without repairing any hash list.
2. Delete pair_000/arm_R.result.json from a complete batch.
3. Change the pooled Delta1 mean at B=8 to 999.

The implementation enumerates whatever files remain, does not require the planned file set, verify recorded size/sha lists or manifest/seeds linkage, or re-run numerical audits. No driver calls k9.recompute/k10.recompute on archived output; the dedicated functions exist but are not wired into an archive-wide verifier.

Fix: verify complete/status-specific required files, exclusive relative paths, absence of extra/duplicate files, hashes/sizes and all identity/index references. Reconstruct tasks/plans from frozen inputs; replay arm records; verify controls and prefix maps; recompute K9/K10 and curves/summary from raw readouts. Missing/corrupt/changed files and invented statistics need named findings. Preserve replay's authenticity limit: consistency is not proof the source told the truth.

## F3 — P1: comparison-set completeness and diagnostic types are not enforced

Locations: b4/host/b4_k9.py:206; b4/host/b4_k10.py:121; b4/host/b4_sim_schema.py:243, :277.

Independent results:
- A complete K9 record changed to pairs=[], pairs_done=0 and summarise([]) is accepted by both k9.recompute ([]) and the directory validator ({}), while still declaring pairs_total=1184 and complete=True.
- Repeat the FIRST K10 unit 420 times, update max/count/outcome to the repeated data: k10.recompute returns [] and directory validation {}. No check requires the exact two-background x 210 unique unordered pairs.
- A K9 observation with q=2 is accepted by k9_findings. In an actual fixed-seed mechanics batch, an injecting port changes that one value to 2: the harness saves it and returns complete/0 with self_validation={}. This is a runtime contract hole, not just malicious archive editing.
- manifest_findings with arm_order=None raises uncaught TypeError instead of named findings.

Fix: total/type-exact nested validation before arithmetic/indexing; 0/1/None q cells, exact dimensions and bindings, integer-not-bool checks, unique observation IDs, exact canonical forced-pair/unit coverage when complete and valid prefixes when partial. Validate task/stimulus/provenance against the declared task/source, not merely another user-supplied string. The denominator, applicability and observed separations are distinct. Complete diagnostics cannot omit or duplicate fixed comparisons. All malformed cases must produce findings, never an unhandled exception.

## F4 — P1: final validation/report failures can still return complete and exit 0

Location: b4/host/b4_sim.py:435-467.

Independent fault injections show:
- report_findings returns an error: no sim_report.json is written, only sim_report.ERROR.txt, yet run_batch returns status complete and exit_code 0.
- validate_run_dir returns {'file':['injected corruption']}: final report still has complete, summary present and exit0.

Fix: final archive validation, report validation/write and publication are conditions of success. Findings or inability to persist the required report must make the batch invalid/nonzero with no successful pooled summary publication. A diagnostic error file is useful but cannot preserve a success status. Preserve the original failure even if STOPPED/report fallback also fails; do not let finish exceptions hide the batch state.

## F5 — P2: K10 observes more corners after DOMAIN

Location: b4/host/b4_k10.py:86, through unchanged b4_stats.four_corner.

On refusal at port call1, the driver returns invalid only after port calls reach4, saving3 subsequent successful observations. four_corner catches DomainRefusal and continues its remaining corners before the driver sees comparable=False. This contradicts the driver's 'nothing continues' statement and the intended immediate fail-closed behaviour. A soft-deadline indivisible work unit is not a reason to continue model observations after an invalid-domain event.

Clarification/fix: terminate further observations on the first refusal, preserve already obtained corners and the refused attempt, and carry that partial outward. A local wrapper exception can escape four_corner without modifying the existing stats primitive. Test call count at the FIRST invalid corner, not only whether the final record is invalid.

## F6 — P1: errors can discard the very evidence that triggered the stop

Locations: b4/host/b4_k9.py:193-203; b4/host/b4_sim.py:332-338, :376-382; non-DOMAIN K10 paths similarly.

- Inject DOMAIN at the second K9 observation. Batch is invalid/k9_invalid but no k9.json exists: the first successful observation and partial pair are lost when coverage raises without carrying its memo. KeyboardInterrupt/SourceRefusal/unexpected failures have the same missing partial-data pattern.
- Let a returned engine result have completed=1 (invalid type). The pre-write validator rejects it, no arm_R.result.json exists, and the plan still says in_flight, although the engine returned. The invalid returned object is not preserved anywhere.

Fix: preserve returned raw data and diagnostic memo/partial work on every failure route, including current attempt/context and true vs unavailable results. Use a typed quarantine/error envelope for malformed returned data rather than silently dropping it or pretending it is valid. Do not weaken ordinary schemas. Interrupted calls with no returned result must remain explicitly result_unavailable, never fabricated complete results.

## F7 — P1: a symlinked exploration namespace escapes the allowed output root

Location: b4/host/b4_sim.py:208-218.

With a clean hermetic repo whose evidence/b4/sim is a tracked symlink to another /tmp directory, preflight accepts a new output under that target. The two resolve() operands compare the same followed symlink, so the namespace is not actually confined. Probe confirms accepted=True and resolved output outside repo root (no write to that target was performed by this probe).

Fix: check the entire existing ancestor chain against the canonical allowed root without accepting symlink ancestors; revalidate at creation or use directory-relative no-follow/exclusive operations. Test symlinked evidence, b4 and sim ancestors, as well as the final leaf, with external sentinel unchanged. Keep normal no-clobber/exclusive final-file behaviour.

## F8 — P2: the final stages can complete after the soft deadline expires

Locations: b4/host/b4_sim.py:629-666 and finish().

A fake clock crossing 60s at final input validation yields complete/exit0, summary present, and deadline.expired=True with elapsed10000s. There is no check after final statistics, during final validation boundaries or before successful publication. This is not a demand for a hard wall-clock bound: a started unit may overrun, but a new finalisation/publication unit must not start after expiry and report an on-time complete batch.

Fix: explicit monotonic checks at final work-unit boundaries and before success publication, without discarding already returned results; keep enough deadline-independent failure finalisation to persist incomplete/STOPPED. Preserve the soft-overrun limit and test expiration at the LAST bootstrap/statistics/validation unit, not only between arms.

## F9 — P2: checkpoint input coverage omits external sources and exclusion snapshots

Locations: b4/host/b4_sim.py:128-151, :284-295.

input_snapshot includes selected repo sources and tools, but none of the six vendor source paths and none of the 38 historical exclusion source paths. Initial load/source hashes are checked; the checkpoint hold_inputs only loops the smaller dictionaries. Dirty-tree checking may later catch many tracked historical edits, but is not the promised per-checkpoint source-hash audit and cannot cover external vendor files or untracked registry changes.

Fix: bind the complete declared repo/external input list and frozen historical/archived seed source snapshots at start and checkpoint/end. External roots plus path plus digest; avoid writing external sources in tests, use copied vendor fixtures. Detect source disappearance/mutation and registry snapshot drift explicitly. Also distinguish model code root from input root in hermetic tests so code-root cleanliness is not accidentally assumed from a different Git tree.

## Disposition and follow-up scope

- This review changes no implementation. The existing 22 commits remain, main stays d5bf815, no reset/rebase/push/merge.
- Authorise a focused B4 follow-up for these reproduced issues: new harness/diagnostic/validation/seed modules, their tests/helpers, IMPORT, architecture wording and new evidence. No threshold/grid/tau/hypothesis change, no old engine/carto/replay/stat primitive logic change, no formal seed generation or model exploration. If an old production module must change, report before widening scope.
- Fix the unsafe tests first, record their past exposure, then rerun the B4 suite and necessary mutants with explicit safe fixture schedules. Archive failed results untouched and make the corrected claims precise. No need rerun B1/B2/B3 full proof.
- The exact treatment of already observed production-derived seeds remains pending before actual exploration. Do not auto-change label/anchor or silently select replacement sets.
- **Data volume: retain the full raw readouts. About190MB for S=32 is acceptable here; do not remove fields/observations to make it smaller. No compression implementation is needed for this repair.** A future lossless archive must preserve bytes, hash list, required files and restore/recompute checks; decide that separately after the tool is correct.
- S=32 exploration, formal gate, 2c/2d, board work, procurement, push/merge remain unauthorised.

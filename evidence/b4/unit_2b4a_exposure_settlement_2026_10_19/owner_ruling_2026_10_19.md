# B4 prior seed exposure — owner ruling, 2026-10-19

Standing: issued after acceptance of `82e863e`, before any new exploration. This ruling authorizes a bounded exposure-settlement unit. It does not start an exploration or gate run. Current branch: b4-prework; main remains d5bf815. Existing commits and original evidence are retained.

## 1. Disposition of prior runs and labels

Retire `b4-sim-1` and `b4-sim-2` for all future production derivations under this B4 protocol. Keep their historical records readable; retirement must not make the archive reader discard their seeds. Classify the old smoke, test and mutant batches as development exposure. They cannot count toward a new exploration sample, gate population, PASS/FAIL result, or power estimate, regardless of whether a particular batch completed.

Reserve `b4-sim-3` as the next exploration label. It is chosen here, before deriving or examining its values, solely because the first two labels were consumed. Keep the formal hypothesis digest `59948f9be3b4516547fbf039556d4aa6a4afd0b2dda2324619e4d40ef0651ed8`, master derivation formula, control formulas, thresholds, tau, budget grid and incomplete-run policy unchanged. Update the document and machine table's exploration-label field consistently. Do not derive the new master/pairs during this settlement unit, even for a smoke test. `b4-gate-1` remains reserved and unexecuted; discovery of evidence that it was already derived requires a new owner decision.

## 2. Preserve originals and distinguish recovery from execution

The preserved exposure directory, inventory, failure/stop records, previous summaries and correction notes remain byte-identical. An independent read of the present archive finds 22 preserved seeds.json documents representing six distinct master/pair sets, all b4-sim-1, under the current hypothesis anchor. These counts describe preserved records, not all historical attempts.

Deleted raw observations cannot be recovered by generating fresh ones. Never recreate a missing manifest, timestamp, readout, run log or verdict and present it as historical evidence. Do not rerun engine, fabric observations, cartography, K9/K10 or summary statistics to reconstruct lost results.

Authorize seed-only forensic reconstruction from the historical, fixed recipes. This is explicitly allowed despite the previous ban on re-derivation: its sole purpose is conservative exclusion, not another scientific attempt or an opportunity to select a result. Mark outputs as reconstructed, with reconstruction time and historical inputs; never as recovered original execution records.

## 3. Fix the finite reconstruction envelope before deriving values

First record the recipe inventory from historical source, archived commands and mutant scripts, with source commits/digests, S, labels, historical exclusion snapshots, registry sequence and derivation-changing edits. Do not run the old test suites to recover it.

The documented envelope to check is: b4-sim-1 S=2, sequential sets 1 through 7 under the historical registry updates; b4-sim-2 S=2 with the first b4-sim-1 set in its registry; and the M1 variant ignoring registry values (including its b4-sim-2 branch). The smoke and repeated fresh trees are covered by their recipes, not counted as new independent sets. Audit other historical edits/call sites for additional seed-affecting branches before claiming this envelope covers them. Preserve all variants without selecting one from their values or outcomes.

Use historical exclusion contents, not today's expanded exclusion set, to reproduce these historical recipes. Each preserved seed record's master/pairs and documented derivation inputs must agree with the corresponding reconstructed recipe. Any mismatch, unsupported extra call pattern or inability to bound a seed-affecting branch stops this unit with a named uncertainty; do not silently replace the recipe or guess a convenient number of draws.

A reconstruction envelope may conservatively include values that were potentially drawn but cannot be shown to have been used. Distinguish `observed`, `reconstructed_recipe`, and `conservative_superset`. It does not establish a complete execution history, the exact number of attempts, or that deleted outcomes were never inspected.

## 4. Make the exclusion effective

Create a dedicated, versioned exposure receipt under `evidence/b4/` outside the production sim-run namespace. It must enumerate all retained/reconstructed variants, original source references and digests, the finite-envelope rationale and residual uncertainty, and a sorted pooled integer exclusion list with count and digest. Include masters, both pair positions, and observed or conservatively derived historical X/D/control-seed variants. Existing source and fixture exclusions remain in force. Retain duplicates' provenance even when the pooled integers are deduplicated.

The present loader reads 38 historical sources, exposed literals and the sim registry; it does not read the preserved exposure directory. Therefore copying evidence or changing a label alone is insufficient. Authorize a narrow B4-only change to load and validate this exposure receipt, pin its digest, pool its values into BOTH pair positions, and bind it into the normal manifest/input checkpoint and verification contracts. Missing, malformed or rehashed receipt must be a named preflight refusal, never skipped. Do not fabricate a modern seeds.json inside evidence/b4/sim to make the original incomplete legacy archives look like current-schema runs.

Retired labels must be refused on the new-production-derivation path before master/pair generation or writes; historical archive ingestion must continue to include them. Exclusion growth and label retirement are pre-result administrative corrections documented by this ruling, not a claim that a changed label guarantees unseen or independent data.

## 5. Bounded implementation and validation authorization

Authorize this settlement unit on b4-prework: seed-only forensic script/receipt, narrowly necessary B4 loader/preflight/schema/verification integration, document/machine-table label consistency, IMPORT refresh, mechanics tests and relevant mutants, and an English evidence README with this ruling. No changes to old pinned B1/B2/B3 files, model behavior, domain, hypothesis, numeric thresholds or task/search algorithms.

Tests must use existing mechanics schedules or hand-made non-production receipts. Preserve guards against production derivation except inside the explicitly bounded historical seed-only reconstruction. Cover pooled exclusion at both positions, receipt tampering/missing/type failures, archived retired-label ingestion, pre-derivation refusal of retired labels, checkpoint binding and drift, and consistency of b4-sim-3 in the document/table. Run the B4 suite and affected mutants, not full B1/B2/B3 proof. Do not use the new exploration or gate labels to create a test batch.

Deliver the frozen receipt, reconstruction comparison, code/docs, raw validation and local commits together for review. Push is not automatically authorized by the earlier push permission.

## 6. Exploration remains a separate execution authorization

After settlement acceptance, the next proposed exploration is one b4-sim-3 batch with S=32. The exclusion receipt must already be committed and bound before deriving that set. Use the existing freeze-before-first-observation and fail-closed rules. Retain all seeds and every partial/invalid result; do not redraw, replace a seed or silently extend S. A stopped or invalid batch does not automatically license b4-sim-4. No gate PASS can be inferred from this exploration.

This ruling does not authorize that S=32 run today. Formal gate tooling/runs, 2c/2d, full proof, merge, procurement and board work remain outside this unit. Do not call the historical exclusion complete merely because surviving files agree with a reconstruction; the accepted claim must state the bounded-recipe coverage and the irrecoverable raw-evidence loss.
